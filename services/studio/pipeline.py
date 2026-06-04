"""파이프라인 — 입력 추출 → 프롬프트 조립 → LLM → 렌더 → 저장.

채팅(지시)을 3곳에서 받는다:
  - 생성 전 메모(instruction)  → 첫 프롬프트의 {{instruction}}
  - 입력 없이 메모만으로도 생성 가능
  - 생성 후 refine(채팅)        → 초안 재생성

job 은 메모리에 보관(서버 재시작 시 초기화). 산출물 파일은 디스크에 영구 저장.
"""
from __future__ import annotations

import datetime
import os
import re
import threading
import uuid
from typing import Any, Dict, List, Optional

from . import config, extractors, llm, recipes
from . import generators
from .generators import md_gen, hwpx_gen

# job_id → job dict
_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def _now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _date() -> str:
    return datetime.datetime.now().strftime("%Y%m%d")


def _safe_name(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return name or "output"


def _build_prompt(recipe: Dict[str, Any], input_texts: List[Dict[str, str]],
                  instruction: str) -> str:
    """레시피 prompt 템플릿에 입력/지시 주입. {{inputs}}/{{instruction}} 치환."""
    inputs_block = ""
    for it in input_texts:
        inputs_block += f"\n### [{it['label']}] ({it['filename']})\n{it['text']}\n"
    if not inputs_block:
        inputs_block = "(첨부된 입력 문서 없음 — 아래 지시만으로 작성)"

    instr_block = instruction.strip() or "(추가 지시 없음)"

    tmpl = recipe.get("prompt") or (
        "아래 입력 자료를 바탕으로 한국어 문서를 작성하세요.\n{{inputs}}\n\n[추가 지시]\n{{instruction}}"
    )
    if "{{inputs}}" in tmpl:
        tmpl = tmpl.replace("{{inputs}}", inputs_block)
    else:
        tmpl += "\n\n[입력 자료]\n" + inputs_block
    if "{{instruction}}" in tmpl:
        tmpl = tmpl.replace("{{instruction}}", instr_block)
    elif instruction.strip():
        tmpl += "\n\n[추가 지시]\n" + instr_block

    mode = recipe["output"]["mode"]
    if mode == "slides":
        tmpl += (
            '\n\n출력 형식: JSON. {"title": 표지제목, "subtitle": 부제, '
            '"slides": [{"title": 슬라이드제목, "bullets": [불릿 3~5개]}]} 만 출력.'
        )
    elif mode == "table":
        tmpl += (
            '\n\n출력 형식: JSON. {"title": 제목, "columns": [열이름...], '
            '"rows": [[셀...], ...]} 만 출력.'
        )
    else:
        tmpl += ("\n\n출력 형식: 잘 구조화된 Markdown (제목 #, 소제목 ##/###, 불릿 -, 강조 **굵게**, 표는 | a | b | 형식)."
                 " 셀 안에서 줄을 나눌 때 <br> 등 HTML 태그는 쓰지 말고 쉼표나 ' / '로 구분하세요.")
    return tmpl


def _generate_content(recipe: Dict[str, Any], prompt: str) -> Any:
    model = recipe.get("model") or config.DEFAULT_MODEL
    mode = recipe["output"]["mode"]
    if mode in ("slides", "table"):
        return llm.generate_json(prompt, model=model, max_tokens=6000)
    return llm.generate_text(prompt, model=model, max_tokens=8000)


def _render_outputs(recipe: Dict[str, Any], content: Any, job_id: str) -> Dict[str, Any]:
    """산출물 파일 + 미리보기(md) 생성. 반환: {files, preview, warnings}."""
    config.ensure_dirs()
    fmt = recipe["output"]["format"]
    base = _safe_name(recipe["output"]["filename"].replace("{date}", _date()))
    stem = f"{base}_{job_id[:8]}"
    out_dir = config.OUTPUTS_DIR
    template = config.template_for(fmt, recipe["output"].get("template"))

    warnings: List[str] = []
    files: List[Dict[str, str]] = []

    # 항상 .md 미리보기/백업 저장
    preview_md = md_gen.to_markdown(content)
    md_path = os.path.join(out_dir, f"{stem}.md")
    md_gen.render(content, md_path)
    files.append({"format": "md", "path": md_path, "name": os.path.basename(md_path)})

    # 주 산출물
    if fmt != "md":
        main_path = os.path.join(out_dir, f"{stem}.{fmt}")
        try:
            generators.render(fmt, content, main_path, template=template)
            files.insert(0, {"format": fmt, "path": main_path,
                             "name": os.path.basename(main_path)})
        except hwpx_gen.HwpxUnavailable as e:
            warnings.append(str(e))
            # HWPX 불가 시 DOCX 폴백(어디서나 열림)
            try:
                docx_path = os.path.join(out_dir, f"{stem}.docx")
                generators.render("docx", content, docx_path,
                                  template=config.template_for("docx"))
                files.insert(0, {"format": "docx", "path": docx_path,
                                 "name": os.path.basename(docx_path)})
                warnings.append("→ 대신 DOCX 로 생성했습니다(한글에서 열어 .hwpx 로 저장 가능).")
            except Exception as de:
                warnings.append(f"DOCX 폴백도 실패: {de}")
        except ModuleNotFoundError as e:
            warnings.append(f"{fmt} 생성에 필요한 라이브러리({e.name})가 없습니다. setup.bat 재실행 필요.")
        except Exception as e:
            warnings.append(f"{fmt} 생성 실패: {type(e).__name__}: {e} (Markdown 으로 대체 제공)")

    return {"files": files, "preview": preview_md, "warnings": warnings, "template": template}


# ── 공개 API ─────────────────────────────────────────────────────────
def create_job(recipe_id: str, saved_inputs: List[Dict[str, str]],
               instruction: str = "") -> Dict[str, Any]:
    """동기 실행(생성). saved_inputs: [{key,label,filename,path}]."""
    recipe = recipes.get(recipe_id)
    if not recipe:
        raise ValueError(f"레시피를 찾을 수 없습니다: {recipe_id}")

    # 필수 입력 검증
    provided = {i["key"] for i in saved_inputs}
    missing = [i["label"] for i in recipe["inputs"]
               if i["required"] and i["key"] not in provided]
    if missing and not instruction.strip():
        raise ValueError("필수 입력이 비었습니다: " + ", ".join(missing))

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id, "recipe_id": recipe_id, "recipe_name": recipe["name"],
        "status": "running", "created": _now_stamp(),
        "instruction": instruction, "inputs": saved_inputs,
        "content": None, "files": [], "preview": "", "warnings": [],
        "chat": [], "error": None,
    }
    with _LOCK:
        _JOBS[job_id] = job

    try:
        # 입력 추출
        input_texts = []
        for it in saved_inputs:
            text = extractors.extract(it["path"])
            input_texts.append({"label": it["label"], "filename": it["filename"], "text": text})
        job["_input_texts"] = input_texts

        prompt = _build_prompt(recipe, input_texts, instruction)
        content = _generate_content(recipe, prompt)
        job["content"] = content

        result = _render_outputs(recipe, content, job_id)
        job.update(status="done", files=result["files"],
                   preview=result["preview"], warnings=result["warnings"])
        if instruction.strip():
            job["chat"].append({"role": "user", "text": instruction})
        job["chat"].append({"role": "assistant", "text": "초안을 생성했습니다."})
    except llm.LLMConfigError as e:
        job.update(status="error", error=str(e))
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")
    return public_view(job)


def refine_job(job_id: str, instruction: str) -> Dict[str, Any]:
    """생성된 초안을 채팅 지시로 수정 → 재렌더."""
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise ValueError("작업을 찾을 수 없습니다(서버 재시작 시 초기화됩니다).")
    recipe = recipes.get(job["recipe_id"])
    if not recipe:
        raise ValueError("레시피를 찾을 수 없습니다.")

    job["status"] = "running"
    job["chat"].append({"role": "user", "text": instruction})
    try:
        # 참고 자료(입력 텍스트 일부)
        ctx = ""
        for it in job.get("_input_texts", [])[:3]:
            ctx += f"[{it['label']}]\n{it['text'][:4000]}\n\n"

        model = recipe.get("model") or config.DEFAULT_MODEL
        mode = recipe["output"]["mode"]
        if mode in ("slides", "table"):
            new_content = llm.refine_json(job["content"], instruction, model=model, context=ctx)
        else:
            new_content = llm.refine_text(job["content"], instruction, model=model, context=ctx)
        job["content"] = new_content

        result = _render_outputs(recipe, new_content, job_id)
        job.update(status="done", files=result["files"],
                   preview=result["preview"], warnings=result["warnings"])
        job["chat"].append({"role": "assistant", "text": "수정 반영했습니다."})
    except llm.LLMConfigError as e:
        job.update(status="error", error=str(e))
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")
    return public_view(job)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
    return public_view(job) if job else None


def find_file(job_id: str, filename: str) -> Optional[str]:
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return None
    for f in job["files"]:
        if f["name"] == filename:
            return f["path"]
    return None


def public_view(job: Dict[str, Any]) -> Dict[str, Any]:
    """프론트에 보낼 안전한 dict(내부 텍스트 캐시 제외)."""
    return {
        "id": job["id"], "recipe_id": job["recipe_id"], "recipe_name": job["recipe_name"],
        "status": job["status"], "error": job.get("error"),
        "preview": job.get("preview", ""), "warnings": job.get("warnings", []),
        "chat": job.get("chat", []),
        "files": [{"format": f["format"], "name": f["name"]} for f in job.get("files", [])],
        "inputs": [{"key": i["key"], "label": i["label"], "filename": i["filename"]}
                   for i in job.get("inputs", [])],
    }
