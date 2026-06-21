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


def _safe_name(name: str, max_len: int = 80) -> str:
    # 경로 구분 문자 제거 + 길이 제한(Windows 260자 경로 한계 방어 — 긴 한글 파일명 대비).
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip(" ._-")
    return name or "output"


_GROUNDING_RULES = (
    "\n\n[정확성·환각 방지 규칙 — 반드시 준수]\n"
    "- 첨부 입력 자료에 실제로 있는 사실만 단정한다.\n"
    "- 입력에 없거나 불확실한 정보(수치·일정·인명·기관명·금액·출처 등)는 임의로 지어내지 말고 '[확인 필요]'로 표시한다.\n"
    "- 입력의 수치·고유명사·날짜는 표기 그대로 사용한다(임의 변환·반올림 금지).\n"
    "- 입력이 부족하면 그럴듯하게 채우지 말고, 무엇이 빠졌는지 '[확인 필요: …]'로 남긴다.\n"
    "- 첨부 입력이 전혀 없으면 일반적인 양식·목차만 제시하고 구체 내용은 모두 '[확인 필요]'로 둔다.\n"
    "- 출처가 있는 수치·인용은 가능하면 출처를 함께 표기한다."
)


def _build_prompt(recipe: Dict[str, Any], input_texts: List[Dict[str, str]],
                  instruction: str, *, brief: str = "", evidence_ctx: str = "",
                  style_ctx: str = "") -> str:
    """레시피 prompt 템플릿에 입력/지시 주입. {{inputs}}/{{instruction}} 치환.

    근거 기반 워크플로가 켜져 있으면 brief(리서치 브리프)·evidence_ctx(데이터 근거)·
    style_ctx(문체 앵커)를 추가로 주입한다. 모두 빈 값이면 기존 단발 경로와 동일.
    """
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

    # 근거 기반 워크플로 주입(있을 때만). 데이터는 사실 근거, 문체 앵커는 톤/구성만 참고.
    if brief.strip():
        tmpl += "\n\n[리서치 브리프 — 이 설계를 따르라]\n" + brief
    if evidence_ctx.strip():
        tmpl += ("\n\n[데이터 근거 — 이 발췌만 사실 근거로 사용, 없는 내용은 지어내지 말 것]\n"
                 + evidence_ctx)
    if style_ctx.strip():
        tmpl += ("\n\n[문체·품질 참고 — 지난 산출물. 톤·구성·완성도만 참고하고 사실 근거로 쓰지 말 것]\n"
                 + style_ctx)

    # 옵션 A(전역 환각 방지): 레시피 프롬프트가 약해도 항상 근거 규율을 강제한다.
    # 포맷(JSON/Markdown) 지시는 이 뒤에 와서 마지막에 위치하도록 둔다.
    tmpl += _GROUNDING_RULES

    mode = recipe["output"]["mode"]
    if mode == "design_deck":
        tmpl += (
            "\n\n출력 형식: JSON 만 출력(설명·코드펜스 금지). 도형 조립형 발표 덱을 설계한다.\n"
            '{"slides":[\n'
            '  {"type":"cover","title":표지제목,"subtitle":"사업명·기간·발표자"},\n'
            '  {"type":"toc","chapter":"OVERVIEW","title":"목차","items":[{"no":"01","part":"Part I","title":섹션명}]},\n'
            '  {"type":"divider","no":"01","part":"PART I","title":섹션명},\n'
            '  {"type":"content","chapter":"PART I · 섹션명","title":결론문장,"subtitle":뒷받침 한 줄,'
            '"blocks":[블록 1~2개]}\n'
            "]}\n"
            "블록 종류(필요한 것만):\n"
            '- {"kind":"progress","header":제목,"items":[{"label":라벨,"sub":보조,"pct":숫자|null}]}  // 진행률 막대. 모르면 pct:null\n'
            '- {"kind":"kpi_cards","cards":[{"header":제목,"value":"34%","desc":설명}]}  // 핵심 수치 카드(슬라이드 오른쪽)\n'
            '- {"kind":"timeline","header":제목,"items":[{"date":날짜,"text":내용}]}  // 일정·경과\n'
            '- {"kind":"bullets","header":제목,"items":["요점", ...]}\n'
            '- {"kind":"table","header":제목,"unit":"단위: %","headers":[열...],"rows":[[셀...]]}\n'
            "규칙: 각 Part 는 divider 1장 + content 1~3장. content 의 title 은 토픽이 아니라 '결론 문장'. "
            "수치·고유명사는 근거에 있는 것만 쓰고, 없으면 값에 '[확인 필요]'(progress 는 pct:null). "
            "표지+목차+Part별 divider 포함 15장 내외. 한국어."
        )
    elif mode == "mckinsey_deck":
        tmpl += (
            "\n\n출력 형식: JSON 만 출력(설명·코드펜스 금지). 아래 스키마를 따른다.\n"
            '{"title":표지제목,"subtitle":부제,'
            '"slides":[{"template":"A"|"B","chapter":"01  도입","title":결론문장,"subtitle":한줄부연,'
            '"boxes":[{"header":박스헤더,"unit":"단위: %","kind":"column|bar|line|doughnut|table|kpi",'
            '"categories":[...],"series":[{"name":계열명,"values":[수치...]}],'
            '"labels":[...],"values":[...],'           # doughnut 용
            '"headers":[...],"rows":[[...]],'           # table 용
            '"kpis":[{"value":"34%","label":"라벨","desc":"한 줄"}],'  # kpi 용
            '"number_format":"0","insight":한줄인사이트,"source":"Source: 기관, 보고서, 연도"}]}]}\n'
            "규칙: 템플릿 A=박스1개(boxes 길이 1), B=박스2개(boxes 길이 2). "
            "각 박스는 kind 에 맞는 데이터 필드만 채운다. 모든 슬라이드에 최소 1개 차트/표/KPI. "
            "슬라이드 10장 이상. 수치엔 출처. 한국어."
        )
    elif mode == "slides":
        tmpl += (
            '\n\n출력 형식: JSON 만 출력. '
            '{"title": 발표 제목(한 줄, 25자 이내), '
            '"subtitle": 사업명·기간·발표자 등 부가정보(한 줄), '
            '"slides": [{"title": 슬라이드 제목(짧게), "bullets": [핵심 불릿 3~5개]}]}. '
            '불릿은 문장이 아니라 키워드 중심 구로 한 줄씩 간결하게(각 40자 이내). '
            '표지 정보를 title 에 몰아넣지 말고 subtitle 로 분리. 수치·고유명사는 근거에 있는 것만.'
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
    # 모델은 레시피가 명시한 경우만 전달(대부분 미지정 → None). 공급자 무관 기본값
    # (gemini-3-pro)을 강제하지 않는다 — codex 에 gemini 모델을 넘기면 실패한다.
    # 최종 모델 선택은 llm.chat 이 활성 공급자의 선택값(get_model)으로 결정한다.
    model = recipe.get("model")
    mode = recipe["output"]["mode"]
    if mode in ("slides", "table", "mckinsey_deck", "design_deck"):
        max_tokens = 12000 if mode in ("mckinsey_deck", "design_deck") else 6000
        return llm.generate_json(prompt, model=model, max_tokens=max_tokens)
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
            generators.render(fmt, content, main_path, template=template,
                              mode=recipe["output"]["mode"])
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
def _get(job_id: str) -> Dict[str, Any]:
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise ValueError("작업을 찾을 수 없습니다(서버 재시작 시 초기화됩니다).")
    return job


def _collect_texts(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for it in items:
        text = extractors.extract(it["path"])
        out.append({"label": it["label"], "filename": it["filename"],
                    "text": text, "role": it.get("role", "data")})
    return out


def _new_job(recipe_id: str, saved_inputs: List[Dict[str, str]], instruction: str,
             style_inputs: Optional[List[Dict[str, str]]] = None,
             defer: bool = False) -> Dict[str, Any]:
    """검증 후 작업 레코드 생성. 검증 실패 시 ValueError.

    defer=True 면 즉시 생성하지 않고 'ready' 상태로 둔다(근거 기반 5단계 진행용).
    """
    recipe = recipes.get(recipe_id)
    if not recipe:
        raise ValueError(f"레시피를 찾을 수 없습니다: {recipe_id}")
    if not defer:
        provided = {i["key"] for i in saved_inputs}
        missing = [i["label"] for i in recipe["inputs"]
                   if i["required"] and i["key"] not in provided]
        if missing and not instruction.strip():
            raise ValueError("필수 입력이 비었습니다: " + ", ".join(missing))
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id, "recipe_id": recipe_id, "recipe_name": recipe["name"],
        "status": "ready" if defer else "running", "created": _now_stamp(),
        "instruction": instruction, "inputs": saved_inputs,
        "style_inputs": style_inputs or [],
        "content": None, "files": [], "preview": "", "warnings": [],
        "chat": [], "error": None,
        # 근거 기반 워크플로 상태
        "stage_status": {}, "research_brief": "", "review_report": "",
        "evidence_indexed": False,
    }
    with _LOCK:
        _JOBS[job_id] = job
    return job


def _run_create(job: Dict[str, Any], saved_inputs: List[Dict[str, str]], instruction: str) -> None:
    """무거운 생성 작업(추출→프롬프트→LLM→렌더). job 상태를 in-place 갱신.

    근거가 학습돼 있거나 리서치 브리프가 있으면 데이터/문체 근거를 함께 주입한다.
    아무것도 없으면 기존 단발 경로와 동일.
    """
    recipe = recipes.get(job["recipe_id"])
    try:
        input_texts = job.get("_input_texts")
        if input_texts is None:
            input_texts = _collect_texts(saved_inputs)
            job["_input_texts"] = input_texts

        brief = job.get("research_brief", "") or ""
        evidence_ctx = ""
        style_ctx = ""
        # 데이터 근거는 학습/브리프가 있을 때만(입력 전문은 이미 {{inputs}}에 들어감).
        # 문체 앵커(지난 산출물)는 첨부돼 있으면 '항상' 반영한다 — 5단계를 안 거쳐도.
        need_data = bool(brief or job.get("evidence_indexed"))
        need_style = bool(job.get("style_inputs"))
        if need_data or need_style:
            from . import enrich, evidence as ev
            try:
                if not ev.load_chunks(job["id"]):
                    _build_evidence_index(job)
                if need_data:
                    qs = enrich.auto_queries(recipe["name"], instruction,
                                             [t["filename"] for t in input_texts])
                    evidence_ctx = enrich.gather_context(job["id"], qs, k=6,
                                                         max_chars=16000, role="data")
                if need_style:
                    style_ctx = enrich.gather_context(
                        job["id"], enrich.auto_queries(recipe["name"], "", []),
                        k=4, max_chars=5000, role="style")
            except Exception:
                pass  # 근거 조립 실패해도 기본 생성은 진행

        prompt = _build_prompt(recipe, input_texts, instruction,
                               brief=brief, evidence_ctx=evidence_ctx, style_ctx=style_ctx)
        content = _generate_content(recipe, prompt)
        job["content"] = content

        result = _render_outputs(recipe, content, job["id"])
        job.update(status="done", files=result["files"],
                   preview=result["preview"], warnings=result["warnings"])
        if instruction.strip():
            job["chat"].append({"role": "user", "text": instruction})
        job["chat"].append({"role": "assistant", "text": "초안을 생성했습니다."})
    except llm.LLMConfigError as e:
        job.update(status="error", error=str(e))
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")


def create_job(recipe_id: str, saved_inputs: List[Dict[str, str]],
               instruction: str = "") -> Dict[str, Any]:
    """동기 실행(생성). saved_inputs: [{key,label,filename,path}]."""
    job = _new_job(recipe_id, saved_inputs, instruction)
    _run_create(job, saved_inputs, instruction)
    return public_view(job)


def start_job(recipe_id: str, saved_inputs: List[Dict[str, str]],
              instruction: str = "",
              style_inputs: Optional[List[Dict[str, str]]] = None,
              defer: bool = False) -> Dict[str, Any]:
    """비동기 생성: 'running' 작업을 즉시 반환하고 백그라운드 스레드에서 생성.
    프론트는 GET /jobs/{id} 를 폴링한다(긴 agy 호출이 HTTP 타임아웃에 안 걸리게).

    defer=True 면 생성하지 않고 'ready' 작업만 만든다(근거 기반 5단계 진행용)."""
    job = _new_job(recipe_id, saved_inputs, instruction, style_inputs, defer)
    if defer:
        return public_view(job)
    threading.Thread(target=_run_create, args=(job, saved_inputs, instruction),
                     daemon=True, name="studio-create").start()
    return public_view(job)


# ── 근거 기반 5단계 (자료학습 → 딥리서치 → 생성 → 검수 → 검수반영) ──────
def _build_evidence_index(job: Dict[str, Any]) -> Dict[str, Any]:
    """job 의 입력(데이터)+지난 산출물(문체)을 추출·청킹해 근거 색인 저장."""
    from . import evidence as ev
    data_texts = job.get("_input_texts")
    if data_texts is None:
        data_texts = _collect_texts(job.get("inputs", []))
        job["_input_texts"] = data_texts
    style_texts = job.get("_style_texts")
    if style_texts is None:
        style_texts = _collect_texts(job.get("style_inputs", []))
        job["_style_texts"] = style_texts

    sources: List[tuple] = [(t["filename"], t["text"], "data")
                            for t in data_texts if (t["text"] or "").strip()]
    sources += [(t["filename"], t["text"], "style")
                for t in style_texts if (t["text"] or "").strip()]
    if not sources:
        raise ValueError("학습할 입력 자료가 없습니다. 먼저 파일을 첨부하세요.")
    stat = ev.build_index(job["id"], sources)
    job["evidence_indexed"] = True
    return stat


def _run_stage(job: Dict[str, Any], stage: str, fn, final_status: str) -> None:
    """단계 작업을 공통 처리(상태/오류). fn 은 무인자 콜러블."""
    job["status"] = "running"
    job["error"] = None
    job["stage_status"][stage] = "running"
    try:
        fn()
        job["stage_status"][stage] = "done"
        job["status"] = final_status
    except llm.LLMConfigError as e:
        job["stage_status"][stage] = "error"
        job.update(status="error", error=str(e))
    except Exception as e:
        job["stage_status"][stage] = "error"
        job.update(status="error", error=f"{type(e).__name__}: {e}")


def _spawn(job: Dict[str, Any], stage: str, fn, final_status: str) -> Dict[str, Any]:
    job["status"] = "running"
    job["error"] = None
    job["stage_status"][stage] = "running"
    threading.Thread(target=_run_stage, args=(job, stage, fn, final_status),
                     daemon=True, name=f"studio-{stage}").start()
    return public_view(job)


def start_learn(job_id: str) -> Dict[str, Any]:
    """① 자료학습 — 입력/지난 산출물 추출·색인(비동기)."""
    job = _get(job_id)
    return _spawn(job, "learn", lambda: _build_evidence_index(job), "ready")


def start_research(job_id: str, topic: str = "") -> Dict[str, Any]:
    """② 딥리서치 — 자료 심층분석 → 리서치 브리프(비동기)."""
    job = _get(job_id)

    def _do():
        from . import enrich, evidence as ev
        if not ev.load_chunks(job["id"]):
            _build_evidence_index(job)
        recipe = recipes.get(job["recipe_id"])
        t = (topic or "").strip() or recipe["name"]
        qs = enrich.auto_queries(recipe["name"], job.get("instruction", ""),
                                 [i["filename"] for i in job.get("inputs", [])])
        ctx = enrich.gather_context(job["id"], qs, k=6, max_chars=18000, role="data")
        model = recipe.get("model")
        job["research_brief"] = llm.generate_text(
            enrich.build_research_prompt(t, ctx), model=model, max_tokens=4000)

    return _spawn(job, "research", _do, "ready")


def set_brief(job_id: str, brief: str) -> Dict[str, Any]:
    """편집된 리서치 브리프 저장(③ 생성이 이 브리프를 따른다)."""
    job = _get(job_id)
    job["research_brief"] = brief or ""
    return public_view(job)


def start_generate(job_id: str) -> Dict[str, Any]:
    """③ 문서 생성 — 브리프+근거를 주입해 레시피 포맷으로 산출(비동기)."""
    job = _get(job_id)

    def _gen():
        _run_create(job, job.get("inputs", []), job.get("instruction", ""))
        if job["status"] == "error":
            raise RuntimeError(job.get("error") or "생성 실패")

    return _spawn(job, "generate", _gen, "done")


def start_review(job_id: str) -> Dict[str, Any]:
    """④ 자동 검수 — 생성물을 근거와 대조(비동기)."""
    job = _get(job_id)

    def _do():
        if job.get("content") is None and not (job.get("preview") or "").strip():
            raise ValueError("먼저 문서를 생성하세요.")
        from . import enrich, evidence as ev
        recipe = recipes.get(job["recipe_id"])
        doc_md = job.get("preview", "") or md_gen.to_markdown(job.get("content"))
        ctx = ""
        if ev.load_chunks(job["id"]):
            ctx = enrich.gather_context(job["id"], enrich.review_queries(doc_md),
                                        k=8, max_chars=22000, role="data")
        model = recipe.get("model")
        job["review_report"] = llm.generate_text(
            enrich.build_review_prompt(doc_md, ctx), model=model, max_tokens=4000)

    return _spawn(job, "review", _do, "ready")


def start_revise(job_id: str) -> Dict[str, Any]:
    """⑤ 검수 반영 — 검수 결과를 반영해 문서 수정·재렌더(비동기)."""
    job = _get(job_id)

    def _do():
        report = (job.get("review_report") or "").strip()
        if not report:
            raise ValueError("먼저 자동 검수를 실행하세요.")
        if job.get("content") is None:
            raise ValueError("먼저 문서를 생성하세요.")
        from . import enrich, evidence as ev
        recipe = recipes.get(job["recipe_id"])
        mode = recipe["output"]["mode"]
        model = recipe.get("model")
        ctx = ""
        if ev.load_chunks(job["id"]):
            ctx = enrich.gather_context(job["id"],
                                        enrich.review_queries(job.get("preview", "")),
                                        k=6, max_chars=12000, role="data")
        if mode in ("slides", "table", "mckinsey_deck"):
            new_content = llm.refine_json(job["content"], report, model=model, context=ctx)
        else:
            cur = job["content"] if isinstance(job["content"], str) \
                else md_gen.to_markdown(job["content"])
            sections = enrich.doc_sections(cur)
            parts = []
            for sec in sections:
                p = enrich.build_revise_prompt(sec, report, ctx)
                parts.append(llm.generate_text(p, model=model, max_tokens=8000))
            new_content = "\n\n".join(parts)
        job["content"] = new_content
        result = _render_outputs(recipe, new_content, job["id"])
        job.update(files=result["files"], preview=result["preview"],
                   warnings=result["warnings"])
        job["chat"].append({"role": "assistant", "text": "검수 결과를 반영했습니다."})

    return _spawn(job, "revise", _do, "done")


def _prep_refine(job_id: str, instruction: str):
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise ValueError("작업을 찾을 수 없습니다(서버 재시작 시 초기화됩니다).")
    recipe = recipes.get(job["recipe_id"])
    if not recipe:
        raise ValueError("레시피를 찾을 수 없습니다.")
    job["status"] = "running"
    job["error"] = None
    job["chat"].append({"role": "user", "text": instruction})
    return job, recipe


def _run_refine(job: Dict[str, Any], recipe: Dict[str, Any], instruction: str) -> None:
    try:
        ctx = ""
        for it in job.get("_input_texts", [])[:3]:
            ctx += f"[{it['label']}]\n{it['text'][:4000]}\n\n"
        model = recipe.get("model")  # 미지정이면 활성 공급자의 선택 모델 사용(llm.chat)
        mode = recipe["output"]["mode"]
        if mode in ("slides", "table", "mckinsey_deck"):
            new_content = llm.refine_json(job["content"], instruction, model=model, context=ctx)
        else:
            new_content = llm.refine_text(job["content"], instruction, model=model, context=ctx)
        job["content"] = new_content
        result = _render_outputs(recipe, new_content, job["id"])
        job.update(status="done", files=result["files"],
                   preview=result["preview"], warnings=result["warnings"])
        job["chat"].append({"role": "assistant", "text": "수정 반영했습니다."})
    except llm.LLMConfigError as e:
        job.update(status="error", error=str(e))
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")


def refine_job(job_id: str, instruction: str) -> Dict[str, Any]:
    """생성된 초안을 채팅 지시로 수정 → 재렌더 (동기)."""
    job, recipe = _prep_refine(job_id, instruction)
    _run_refine(job, recipe, instruction)
    return public_view(job)


def start_refine(job_id: str, instruction: str) -> Dict[str, Any]:
    """비동기 refine: 'running' 즉시 반환 + 백그라운드 처리. 프론트는 폴링."""
    job, recipe = _prep_refine(job_id, instruction)
    threading.Thread(target=_run_refine, args=(job, recipe, instruction),
                     daemon=True, name="studio-refine").start()
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
    from . import evidence as ev
    if job.get("evidence_indexed"):
        evd = ev.index_status(job["id"])
    else:
        evd = {"indexed": False, "chunks": 0, "sources": [],
               "retriever": ev.get_retriever().name}
    return {
        "id": job["id"], "recipe_id": job["recipe_id"], "recipe_name": job["recipe_name"],
        "status": job["status"], "error": job.get("error"),
        "preview": job.get("preview", ""), "warnings": job.get("warnings", []),
        "chat": job.get("chat", []),
        "files": [{"format": f["format"], "name": f["name"]} for f in job.get("files", [])],
        "inputs": [{"key": i["key"], "label": i["label"], "filename": i["filename"]}
                   for i in job.get("inputs", [])],
        # 근거 기반 워크플로 상태
        "stage_status": job.get("stage_status", {}),
        "research_brief": job.get("research_brief", ""),
        "review_report": job.get("review_report", ""),
        "evidence": evd,
    }
