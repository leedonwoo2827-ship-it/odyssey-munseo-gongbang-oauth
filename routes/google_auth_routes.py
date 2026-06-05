"""Google 로그인 라우트 — 비밀번호 로그인 전면 대체.

로그인 자체는 구글 공식 CLI(`agy`)가 처리한다(사용자가 터미널/내장터미널에서 `agy` 로그인).
이 라우트는 agy 에 로그인된 Google email 을 읽어 앱 계정을 프로비저닝하고 세션을 발급한다.
앱 자체 OAuth 클라이언트를 두지 않으므로 추가 등록/미검증 경고가 없다.
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
        return True  # 제한 없음 — 모든 Google 계정 허용(기본)
    dom = email.rsplit("@", 1)[-1].lower()
    return dom in domains


def setup_google_auth_routes(auth_manager: AuthManager) -> APIRouter:
    router = APIRouter(prefix="/api/auth/google", tags=["auth-google"])

    @router.get("/status")
    async def google_status(request: Request):
        """agy 설치/로그인 상태 + 현재 앱 세션 사용자."""
        from services.agy import auth as agy_auth
        st = agy_auth.status()
        session_user = auth_manager.get_username_for_token(request.cookies.get(SESSION_COOKIE))
        return {
            "agy_installed": st["installed"],
            "agy_authenticated": st["authenticated"],
            "agy_email": st["email"],
            "allowed_domains": _allowed_domains(),
            "session_user": session_user,
        }

    @router.post("/login")
    async def google_login(request: Request, response: Response):
        """agy 인증을 근거로 앱 세션 발급. 미인증/도메인불가 시 안내 반환."""
        from services.agy import auth as agy_auth

        if not agy_auth.is_installed():
            return {
                "ok": False, "reason": "agy_not_installed",
                "message": ("Antigravity CLI(agy)가 설치되어 있지 않습니다. "
                            "내장 터미널을 열어 설치/로그인하세요."),
            }
        email = await asyncio.to_thread(agy_auth.get_account_email)
        authed = await asyncio.to_thread(agy_auth.is_authenticated)
        if not email and not authed:
            return {
                "ok": False, "reason": "agy_not_authenticated",
                "message": ("agy 에 Google 로그인이 필요합니다. 내장 터미널에서 `agy` 를 실행해 "
                            "Google 계정으로 로그인한 뒤 다시 시도하세요."),
            }
        # 로그인은 됐지만 토큰이 불투명해 이메일을 못 읽는 경우 → 대체 신원으로 진행
        _FALLBACK = "agy-user@local"
        if not email:
            email = _FALLBACK
        # 실제 이메일일 때만 도메인 제한 적용(대체 신원은 예외)
        if email != _FALLBACK and not _domain_ok(email):
            raise HTTPException(403, f"허용되지 않은 도메인입니다: {email}")

        is_admin = bool(_admin_email()) and email == _admin_email()
        # 관리자 미지정 시 첫 사용자에게 admin 부여
        if not _admin_email() and not auth_manager.is_configured:
            is_admin = True

        username = await asyncio.to_thread(auth_manager.ensure_oauth_user, email, is_admin)
        if not username:
            raise HTTPException(400, f"계정 생성에 실패했습니다: {email}")

        token = await asyncio.to_thread(auth_manager.create_session_for_user, username)
        if not token:
            raise HTTPException(500, "세션 발급에 실패했습니다")

        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            httponly=True,
            samesite="lax",
            secure=os.getenv("SECURE_COOKIES", "false").lower() == "true",
            path="/",
            max_age=60 * 60 * 24 * 7,
        )
        return {"ok": True, "username": username, "email": email, "is_admin": is_admin}

    return router
