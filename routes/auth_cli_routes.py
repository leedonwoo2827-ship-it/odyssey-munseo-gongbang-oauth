"""공급자 무관 로그인 라우트 — /api/auth/cli/*

로그인은 활성 공급자의 CLI(agy=Google / codex=ChatGPT)가 처리한다. 이 라우트는
그 CLI 의 인증 상태를 읽어 앱 세션을 발급한다. (앱 자체 OAuth 클라이언트 없음)
"""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Request, Response, HTTPException

from core.auth import AuthManager
from routes.auth_routes import SESSION_COOKIE

logger = logging.getLogger(__name__)


def _allowed_domains() -> list[str]:
    raw = os.getenv("GOOGLE_ALLOWED_DOMAINS", "") or ""
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _admin_email() -> str:
    return (os.getenv("ODYSSEUS_ADMIN_EMAIL", "") or "").strip().lower()


def _domain_ok(email: str) -> bool:
    domains = _allowed_domains()
    if not domains:
        return True
    return email.rsplit("@", 1)[-1].lower() in domains


def setup_auth_cli_routes(auth_manager: AuthManager) -> APIRouter:
    router = APIRouter(prefix="/api/auth/cli", tags=["auth-cli"])

    @router.get("/status")
    async def cli_status(request: Request):
        from services import llm_backend
        st = await asyncio.to_thread(llm_backend.status_all)
        active = st["active"]
        session_user = auth_manager.get_username_for_token(request.cookies.get(SESSION_COOKIE))
        return {
            "provider": st["provider"],
            "label": active["label"],
            "installed": active["installed"],
            "authenticated": active["authenticated"],
            "email": active["email"],
            "session_user": session_user,
            "providers": st["providers"],
        }

    @router.post("/login")
    async def cli_login(request: Request, response: Response):
        from services import llm_backend
        auth = llm_backend.active_auth()
        provider = llm_backend.get_provider()
        if not auth.is_installed():
            return {"ok": False, "reason": "not_installed",
                    "message": ("codex 가 설치되어 있지 않습니다. docs/openai-codex/install.md 참고."
                                if provider == "codex" else
                                "agy 가 설치되어 있지 않습니다. docs/antigravity/install.md 참고.")}
        email = await asyncio.to_thread(auth.get_account_email)
        authed = await asyncio.to_thread(auth.is_authenticated)
        if not email and not authed:
            return {"ok": False, "reason": "not_authenticated",
                    "message": ("ChatGPT 로그인이 필요합니다. 터미널에서 `codex login`."
                                if provider == "codex" else
                                "Google 로그인이 필요합니다. 터미널에서 `agy`.")}
        # 토큰이 불투명해 email 못 읽으면 공급자별 대체 신원
        fallback = f"{provider}-user@local"
        if not email:
            email = fallback
        if email != fallback and not _domain_ok(email):
            raise HTTPException(403, f"허용되지 않은 도메인입니다: {email}")

        is_admin = bool(_admin_email()) and email == _admin_email()
        if not _admin_email() and not auth_manager.is_configured:
            is_admin = True

        username = await asyncio.to_thread(auth_manager.ensure_oauth_user, email, is_admin)
        if not username:
            raise HTTPException(400, f"계정 생성 실패: {email}")
        token = await asyncio.to_thread(auth_manager.create_session_for_user, username)
        if not token:
            raise HTTPException(500, "세션 발급 실패")

        response.set_cookie(
            key=SESSION_COOKIE, value=token, httponly=True, samesite="lax",
            secure=os.getenv("SECURE_COOKIES", "false").lower() == "true",
            path="/", max_age=60 * 60 * 24 * 7,
        )
        return {"ok": True, "username": username, "email": email, "provider": provider}

    return router
