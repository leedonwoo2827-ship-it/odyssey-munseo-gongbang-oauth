"""agy(Antigravity CLI) 인증 상태 헬퍼.

agy 가 Google OAuth 를 전담하고 토큰을 `~/.antigravity/oauth_creds.json` 에 저장한다.
앱은 이 파일에서 로그인된 Google email 을 읽어 앱 신원/세션의 근거로 삼는다.
(앱 자체 OAuth 클라이언트를 만들지 않으므로 추가 등록/미검증 경고가 없다.)
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from .runner import is_installed  # re-export 편의

# agy 인증정보 위치(환경변수로 덮어쓰기 가능)
CREDS_PATH = os.environ.get(
    "AGY_CREDS_PATH",
    str(Path.home() / ".antigravity" / "oauth_creds.json"),
)


def creds_exist() -> bool:
    return os.path.isfile(CREDS_PATH)


def _load_creds() -> Optional[dict]:
    try:
        with open(CREDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _decode_jwt_email(id_token: str) -> Optional[str]:
    """id_token(JWT) payload 에서 email 추출(서명 검증 없이 디코드만)."""
    try:
        payload_b64 = id_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)  # base64url padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        email = payload.get("email")
        return email.strip().lower() if isinstance(email, str) and email else None
    except Exception:
        return None


def _userinfo_email(access_token: str) -> Optional[str]:
    """access_token 으로 Google userinfo 조회(표준 라이브러리만 사용)."""
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        email = data.get("email")
        return email.strip().lower() if isinstance(email, str) and email else None
    except Exception:
        return None


def get_account_email() -> Optional[str]:
    """agy 에 로그인된 Google 계정 email. 미로그인/실패 시 None.

    우선순위: creds 의 직접 email 필드 → id_token JWT → access_token userinfo.
    agy creds 스키마가 확정 공개되지 않아 여러 후보를 관용적으로 탐색한다.
    """
    creds = _load_creds()
    if not creds:
        return None

    # 1) 평문 email 필드(있다면)
    for key in ("email", "account", "user_email"):
        v = creds.get(key)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()

    # 중첩(예: {"tokens": {...}} / {"credentials": {...}})
    nested = {}
    for k in ("tokens", "credentials", "token", "oauth"):
        if isinstance(creds.get(k), dict):
            nested.update(creds[k])
    merged = {**creds, **nested}

    # 2) id_token JWT
    for key in ("id_token", "idToken"):
        tok = merged.get(key)
        if isinstance(tok, str) and tok.count(".") >= 2:
            email = _decode_jwt_email(tok)
            if email:
                return email

    # 3) access_token → userinfo
    for key in ("access_token", "accessToken"):
        tok = merged.get(key)
        if isinstance(tok, str) and tok:
            email = _userinfo_email(tok)
            if email:
                return email

    return None


def is_authenticated() -> bool:
    """agy 설치 + 로그인 email 확인 가능 여부."""
    return is_installed() and get_account_email() is not None


def status() -> dict:
    """UI/진단용 상태 요약."""
    installed = is_installed()
    email = get_account_email() if installed else None
    return {
        "installed": installed,
        "authenticated": bool(email),
        "email": email,
        "creds_path": CREDS_PATH,
    }
