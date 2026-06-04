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

        valid_keys = {i["key"]: i for i in recipe["inputs"]}
        saved = []
        for field, value in form.multi_items():
            if field in ("recipe_id", "instruction"):
                continue
            filename = getattr(value, "filename", None)
            if not filename:
                continue  # 일반 텍스트 필드는 무시
            safe = os.path.basename(filename).replace("\\", "_")
            dest = os.path.join(updir, f"{field}__{safe}")
            with open(dest, "wb") as f:
                f.write(await value.read())
            meta = valid_keys.get(field, {"label": field})
            saved.append({"key": field, "label": meta.get("label", field),
                          "filename": safe, "path": dest})

        try:
            result = pipeline.create_job(recipe_id, saved, instruction)
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
            return pipeline.refine_job(job_id, instruction)
        except ValueError as e:
            raise HTTPException(404, str(e))

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
        """현재 연결 설정(키는 마스킹). 첫 화면에서 안내/자동표시에 사용."""
        url, key = config.get_litellm()
        s = config.load_settings()
        source = "saved" if s.get("litellm_key") else ("env" if key else "none")
        return {
            "url": url,
            "key_set": bool(key),
            "key_masked": config.mask_key(key),
            "source": source,
            "default_url": config.DEFAULT_LITELLM_URL,
        }

    @router.post("/settings")
    async def save_settings(request: Request):
        """화면에서 입력한 URL/키 저장 → 즉시 적용 후 연결 점검 결과 반환."""
        body = await request.json()
        config.save_settings(body.get("url"), body.get("key"))
        return {"saved": True, "health": llm.health(),
                "settings": await get_settings()}

    @router.get("/health")
    async def health():
        return JSONResponse({
            "llm": llm.health(),
            "hancom_hwpx": hwpx_gen.hancom_available(),
            "supported_inputs": extractors.SUPPORTED_EXTS,
            "recipes": len(recipes.load_all()),
        })

    return router
