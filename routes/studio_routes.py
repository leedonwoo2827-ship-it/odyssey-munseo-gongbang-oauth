"""문서 생산 스튜디오 라우터 — /api/studio/*

odysseus 라우터 컨벤션(setup_*_routes 팩토리 + APIRouter)을 따른다.
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)


def setup_studio_routes():
    from services.studio import config, recipes, pipeline, llm, extractors
    from services.studio.generators import hwpx_gen

    router = APIRouter(prefix="/api/studio", tags=["studio"])

    @router.get("/recipes")
    async def list_recipes():
        items = recipes.load_all()
        # 카테고리별 그룹 + 안전 필드만
        out = [{
            "id": r["id"], "name": r["name"], "category": r["category"],
            "description": r["description"], "format": r["output"]["format"],
            "workflow": r.get("workflow", "simple"),
            "inputs": r["inputs"],
        } for r in items]
        return {"recipes": out, "count": len(out)}

    @router.get("/recipes/{recipe_id}")
    async def get_recipe(recipe_id: str):
        r = recipes.get(recipe_id)
        if not r:
            raise HTTPException(404, "레시피를 찾을 수 없습니다")
        return r

    @router.post("/recipes")
    async def create_recipe(request: Request):
        """앱 내 폼 빌더(2차) — JSON 바디로 레시피 저장."""
        data = await request.json()
        try:
            res = recipes.save_from_form(data)
        except Exception as e:
            raise HTTPException(400, f"레시피 저장 실패: {e}")
        return res

    @router.post("/jobs")
    async def create_job(request: Request):
        """multipart/form-data: recipe_id, instruction, 그리고 입력파일들(필드명=input key)."""
        form = await request.form()
        recipe_id = (form.get("recipe_id") or "").strip()
        instruction = (form.get("instruction") or "").strip()
        if not recipe_id:
            raise HTTPException(400, "recipe_id 가 필요합니다")
        recipe = recipes.get(recipe_id)
        if not recipe:
            raise HTTPException(404, "레시피를 찾을 수 없습니다")

        config.ensure_dirs()
        token = uuid.uuid4().hex[:12]
        updir = os.path.join(config.UPLOADS_DIR, token)
        os.makedirs(updir, exist_ok=True)

        defer = (form.get("defer_generate") or "").strip() == "1"
        valid_keys = {i["key"]: i for i in recipe["inputs"]}
        saved = []
        style = []
        for field, value in form.multi_items():
            if field in ("recipe_id", "instruction", "defer_generate"):
                continue
            filename = getattr(value, "filename", None)
            if not filename:
                continue  # 일반 텍스트 필드는 무시
            safe = os.path.basename(filename).replace("\\", "_")
            # 경로 길이(Windows 260자) 초과 방지: 파일명 본체를 제한하고 확장자는 보존.
            stem_, ext_ = os.path.splitext(safe)
            if len(stem_) > 60:
                stem_ = stem_[:60].rstrip(" ._-")
            safe = (stem_ + ext_) or "input"
            dest = os.path.join(updir, f"{field}__{safe}")
            try:
                with open(dest, "wb") as f:
                    f.write(await value.read())
            except OSError as e:
                raise HTTPException(
                    400,
                    f"입력 파일을 저장하지 못했습니다(파일명이 너무 길거나 경로 문제일 수 있습니다): "
                    f"{safe} — {type(e).__name__}",
                )
            if field == "__style__":
                # 지난 산출물(문체·품질 앵커) — 데이터가 아니라 톤/구성 참고용
                style.append({"key": "__style__", "label": "지난 산출물",
                              "filename": safe, "path": dest, "role": "style"})
            else:
                meta = valid_keys.get(field, {"label": field})
                saved.append({"key": field, "label": meta.get("label", field),
                              "filename": safe, "path": dest, "role": "data"})

        try:
            # 비동기: 'running' 즉시 반환 → 프론트가 GET /jobs/{id} 폴링(긴 LLM 호출 타임아웃 회피)
            # defer=1 이면 생성하지 않고 'ready' 작업만 만든다(근거 기반 5단계 진행용).
            result = pipeline.start_job(recipe_id, saved, instruction,
                                        style_inputs=style, defer=defer)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return result

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = pipeline.get_job(job_id)
        if not job:
            raise HTTPException(404, "작업을 찾을 수 없습니다")
        return job

    @router.post("/jobs/{job_id}/refine")
    async def refine_job(job_id: str, request: Request):
        body = await request.json()
        instruction = (body.get("instruction") or "").strip()
        if not instruction:
            raise HTTPException(400, "수정 지시(instruction)가 필요합니다")
        try:
            return pipeline.start_refine(job_id, instruction)
        except ValueError as e:
            raise HTTPException(404, str(e))

    # ── 근거 기반 5단계 (자료학습 → 딥리서치 → 생성 → 검수 → 검수반영) ──────
    @router.post("/jobs/{job_id}/learn")
    async def learn_job(job_id: str):
        """① 자료학습 — 입력/지난 산출물을 추출·색인(비동기)."""
        try:
            return pipeline.start_learn(job_id)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.post("/jobs/{job_id}/research")
    async def research_job(job_id: str, request: Request):
        """② 딥리서치 — 자료 심층분석 → 리서치 브리프(비동기)."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        topic = (body.get("topic") or "").strip()
        try:
            return pipeline.start_research(job_id, topic)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.put("/jobs/{job_id}/brief")
    async def set_brief_job(job_id: str, request: Request):
        """편집된 리서치 브리프 저장(③ 생성이 이 브리프를 따른다)."""
        body = await request.json()
        try:
            return pipeline.set_brief(job_id, (body.get("brief") or ""))
        except ValueError as e:
            raise HTTPException(404, str(e))

    @router.post("/jobs/{job_id}/generate")
    async def generate_job(job_id: str):
        """③ 문서 생성 — 브리프+근거를 주입해 생성(비동기)."""
        try:
            return pipeline.start_generate(job_id)
        except ValueError as e:
            raise HTTPException(404, str(e))

    @router.post("/jobs/{job_id}/review")
    async def review_job(job_id: str):
        """④ 자동 검수 — 생성물을 근거와 대조(비동기)."""
        try:
            return pipeline.start_review(job_id)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.post("/jobs/{job_id}/revise")
    async def revise_job(job_id: str):
        """⑤ 검수 반영 — 검수 결과를 반영해 문서 수정(비동기)."""
        try:
            return pipeline.start_revise(job_id)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/jobs/{job_id}/download/{filename}")
    async def download(job_id: str, filename: str):
        path = pipeline.find_file(job_id, filename)
        if not path or not os.path.exists(path):
            raise HTTPException(404, "파일을 찾을 수 없습니다")
        return FileResponse(path, filename=filename)

    @router.get("/outputs")
    async def list_outputs():
        """이 PC(data/studio/outputs)에 저장된 산출물 목록(최신순). DB 불필요."""
        import datetime
        d = config.OUTPUTS_DIR
        items = []
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.startswith("_"):
                    continue
                fp = os.path.join(d, fn)
                if not os.path.isfile(fp):
                    continue
                st = os.stat(fp)
                items.append({
                    "name": fn,
                    "format": os.path.splitext(fn)[1].lstrip(".").lower(),
                    "size_kb": round(st.st_size / 1024, 1),
                    "_mtime": st.st_mtime,
                })
        items.sort(key=lambda x: x["_mtime"], reverse=True)
        for it in items:
            it["modified"] = datetime.datetime.fromtimestamp(it.pop("_mtime")).strftime("%Y-%m-%d %H:%M")
        return {"outputs": items[:300], "count": len(items)}

    @router.get("/outputs/{filename}")
    async def download_output(filename: str):
        """산출물 폴더에서 파일명으로 직접 다운로드(경로 이탈 방지)."""
        safe = os.path.basename(filename)
        fp = os.path.join(config.OUTPUTS_DIR, safe)
        if not os.path.isfile(fp):
            raise HTTPException(404, "파일을 찾을 수 없습니다")
        return FileResponse(fp, filename=safe)

    @router.get("/settings")
    async def get_settings():
        """LLM 연결 상태(활성 공급자 기준). API 키 입력 없음 — CLI 로그인 여부를 표시."""
        from services import llm_backend
        st = llm_backend.status_all()
        active = st["active"]
        return {
            "backend": st["provider"],
            "provider": st["provider"],
            "label": active["label"],
            "installed": active["installed"],
            "authenticated": active["authenticated"],
            "email": active["email"],
            "selected_model": llm_backend.get_model(),
        }

    @router.get("/health")
    async def health():
        return JSONResponse({
            "llm": llm.health(),
            "hancom_hwpx": hwpx_gen.hancom_available(),
            "supported_inputs": extractors.SUPPORTED_EXTS,
            "recipes": len(recipes.load_all()),
        })

    return router
