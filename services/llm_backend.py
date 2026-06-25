"""LLM 공급자 디스패처 — 현재 OpenAI(codex) 단일 공급자.

상위(studio/llm.py, 라우트)에서 공급자와 무관하게 active_* 로 접근한다.

과거엔 Gemini(agy)↔OpenAI(codex) 토글이 있었으나, agy(Antigravity CLI)를 앱이 자동
호출한 것이 Google ToS("제3자 도구로 OAuth 자원 접근") 위반으로 계정이 차단되어 제거했다.
codex 는 공식 비대화 모드 `codex exec` 라 약관상 안전하다(→ docs/openai-codex 참고).
추상화 구조는 유지하여 향후 다른 공급자 추가 여지를 남긴다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID = ("codex",)
LABELS = {"codex": "OpenAI (ChatGPT)"}

_PROVIDER_FILE = Path(__file__).resolve().parents[1] / "data" / "llm_provider.json"
_DEFAULT = "codex"


def get_provider() -> str:
    """활성 공급자(현재 codex 단일). 파일/환경값이 있어도 유효 공급자로만 한정."""
    try:
        if _PROVIDER_FILE.is_file():
            p = json.loads(_PROVIDER_FILE.read_text(encoding="utf-8")).get("provider", "")
            if p in VALID:
                return p
    except Exception:
        pass
    return _DEFAULT


def set_provider(name: str) -> bool:
    name = (name or "").strip()
    if name not in VALID:
        return False
    try:
        _PROVIDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PROVIDER_FILE.write_text(json.dumps({"provider": name}, ensure_ascii=False),
                                  encoding="utf-8")
        return True
    except Exception:
        return False


def _modules(name: str):
    """(runner, auth, login_cmd) 반환. 지연 import."""
    from services.codex import runner as r
    from services.codex import auth as a
    return r, a, a.login_terminal_cmd()


def active_client():
    r, _a, _c = _modules(get_provider())
    return r.client


def active_runner():
    r, _a, _c = _modules(get_provider())
    return r


def active_auth():
    _r, a, _c = _modules(get_provider())
    return a


def login_cmd(name: Optional[str] = None) -> List[str]:
    _r, _a, c = _modules(name or get_provider())
    return c


def _status_one(name: str) -> Dict[str, Any]:
    try:
        _r, a, _c = _modules(name)
        installed = a.is_installed()
        authed = a.is_authenticated() if installed else False
        email = a.get_account_email() if authed else None
    except Exception:
        installed = authed = False
        email = None
    return {"provider": name, "label": LABELS.get(name, name),
            "installed": installed, "authenticated": authed, "email": email}


def status_all() -> Dict[str, Any]:
    """공급자 상태 + 현재 활성 공급자(단일이지만 구조 유지)."""
    cur = get_provider()
    return {
        "provider": cur,
        "label": LABELS.get(cur, cur),
        "providers": {n: _status_one(n) for n in VALID},
        "active": _status_one(cur),
    }


# 활성 공급자 기준 모델 목록/선택
def list_models() -> List[str]:
    return active_runner().list_models()


def get_model() -> str:
    return active_runner().get_model()


def set_model(name: str) -> None:
    active_runner().set_model(name)
