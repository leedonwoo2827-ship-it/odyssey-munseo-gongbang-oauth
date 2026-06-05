"""공급자 무관 LLM 관리 API — /api/llm/*

활성 공급자(Gemini/agy ↔ OpenAI/codex)를 토글하고, 그 공급자의 로그인/로그아웃/모델을 다룬다.
로그인 자체는 각 CLI(`agy` / `codex login`)가 처리하므로, 여기서는 그 명령을 실제 OS 터미널
창에 띄워준다. (loopback 전용)
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_PROXY_FWD_HEADERS = (
    "cf-connecting-ip", "cf-ray", "cf-visitor",
    "x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded",
)


def _loopback(request: Request) -> bool:
    host = request.client.host if request.client else None
    if host not in ("127.0.0.1", "::1"):
        return False
    return not any(request.headers.get(h) for h in _PROXY_FWD_HEADERS)


def _launch_terminal(argv):
    """주어진 명령을 실제 OS 터미널 창에서 실행(로그인용). 성공 method 반환."""
    import subprocess
    import sys
    if sys.platform == "win32":
        # 새 콘솔에서 argv 실행 후 창 유지(/k)
        subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", *argv], close_fds=True)
        return "windows-cmd"
    if sys.platform == "darwin":
        joined = " ".join(argv)
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{joined}"'])
        return "macos-terminal"
    for term in (["x-terminal-emulator", "-e", *argv], ["gnome-terminal", "--", *argv],
                 ["konsole", "-e", *argv], ["xterm", "-e", *argv]):
        try:
            subprocess.Popen(term)
            return "linux-terminal"
        except FileNotFoundError:
            continue
    raise RuntimeError("터미널을 열지 못했습니다.")


def setup_llm_routes() -> APIRouter:
    router = APIRouter(prefix="/api/llm", tags=["llm"])

    @router.get("/status")
    async def llm_status():
        from services import llm_backend
        return await asyncio.to_thread(llm_backend.status_all)

    @router.post("/provider")
    async def set_provider(request: Request):
        if not _loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services import llm_backend
        body = await request.json()
        ok = llm_backend.set_provider((body.get("provider") or "").strip())
        if not ok:
            return JSONResponse(status_code=400, content={"ok": False, "message": "알 수 없는 공급자"})
        return {"ok": True, "status": await asyncio.to_thread(llm_backend.status_all)}

    @router.get("/models")
    async def llm_models():
        from services import llm_backend
        models = await asyncio.to_thread(llm_backend.list_models)
        return {"provider": llm_backend.get_provider(), "models": models,
                "selected": llm_backend.get_model()}

    @router.post("/model")
    async def llm_set_model(request: Request):
        if not _loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services import llm_backend
        body = await request.json()
        llm_backend.set_model((body.get("model") or "").strip())
        return {"ok": True, "selected": llm_backend.get_model()}

    @router.post("/open-terminal")
    async def llm_open_terminal(request: Request):
        """활성 공급자의 로그인 명령(`agy` / `codex login`)을 실제 터미널 창에서 실행."""
        if not _loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services import llm_backend
        cmd = llm_backend.login_cmd()
        try:
            method = _launch_terminal(cmd)
            return {"ok": True, "method": method, "cmd": " ".join(cmd),
                    "message": f"새 터미널에서 `{' '.join(cmd)}` 로 로그인하세요. 끝나면 [상태 새로고침]."}
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "ok": False, "message": f"터미널 열기 실패: {e}. 직접 `{' '.join(cmd)}` 를 실행하세요."})

    @router.post("/logout")
    async def llm_logout(request: Request):
        if not _loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services import llm_backend
        removed = await asyncio.to_thread(llm_backend.active_auth().logout)
        return {"ok": True, "removed": removed,
                "message": "로그아웃되었습니다. [로그인]으로 다른 계정 로그인하세요." if removed else "이미 로그아웃 상태입니다."}

    return router
