"""LLM 호출 래퍼 — 활성 공급자(Gemini/agy ↔ OpenAI/codex)로 라우팅.

API 키를 쓰지 않는다. 인증/할당량은 각 CLI(agy / codex)가 담당하며(1회 로그인),
services.llm_backend 디스패처를 통해 활성 공급자의 client 로 비대화식 호출한다.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import config


class LLMConfigError(RuntimeError):
    """공급자 CLI 미설치/미로그인 등 '설정' 성격의 문제(파이프라인이 친절히 표시)."""


def _get_client():
    """활성 공급자의 client. 미설치면 LLMConfigError 로 친절히 안내."""
    from services import llm_backend
    auth = llm_backend.active_auth()
    if not auth.is_installed():
        prov = llm_backend.get_provider()
        if prov == "codex":
            raise LLMConfigError(
                "OpenAI Codex CLI(`codex`)가 설치되어 있지 않습니다.\n"
                "docs/openai-codex/install.md 참고 → 설치 후 `codex login` 으로 로그인하세요."
            )
        raise LLMConfigError(
            "Antigravity CLI(`agy`)가 설치되어 있지 않습니다.\n"
            "docs/antigravity/install.md 참고 → 설치 후 터미널에서 `agy` 로 Google 로그인하세요."
        )
    return llm_backend.active_client()


def chat(messages: List[Dict[str, str]], model: Optional[str] = None,
         max_tokens: int = 4000) -> str:
    """messages(OpenAI 형식) → 응답 텍스트."""
    from services.llm_errors import LLMNotInstalled, LLMNotAuthenticated
    from services import llm_backend
    client = _get_client()
    # **활성 공급자의 선택 모델(UI)** 이 최우선. 화면 토글로 고른 모델이 레시피/호출자 인자보다
    # 우선해야 codex 에 gemini 모델이 새어들어가지 않는다. 둘 다 비면 CLI 자체 기본 모델.
    # (agy 는 원래 runner 가 자기 get_model 을 쓰므로 이 우선순위와 일관.)
    sel = llm_backend.get_model() or (model or "").strip()
    try:
        resp = client.chat(sel or None, messages, max_tokens=max_tokens)
    except (LLMNotInstalled, LLMNotAuthenticated) as e:
        # 설정 성격의 오류는 LLMConfigError 로 변환해 파이프라인이 안내문으로 표시
        raise LLMConfigError(str(e)) from e
    return resp.text or ""


def generate_text(prompt: str, model: Optional[str] = None,
                  system: Optional[str] = None, max_tokens: int = 4000) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, model=model, max_tokens=max_tokens)


def generate_json(prompt: str, model: Optional[str] = None,
                  system: Optional[str] = None, max_tokens: int = 4000) -> Any:
    """JSON 출력을 요구하고 파싱. 코드펜스/잡텍스트가 섞여도 최대한 복구."""
    sys = (system or "") + "\n반드시 유효한 JSON 만 출력하세요. 코드펜스나 설명 없이 JSON 그 자체만."
    raw = generate_text(prompt, model=model, system=sys.strip(), max_tokens=max_tokens)
    return _parse_json_loose(raw)


def _parse_json_loose(raw: str) -> Any:
    raw = (raw or "").strip()
    # ```json ... ``` 펜스 제거
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    # 첫 { 또는 [ 부터 마지막 } 또는 ] 까지 잘라서 재시도
    start = min([i for i in (raw.find("{"), raw.find("[")) if i != -1] or [-1])
    end = max(raw.rfind("}"), raw.rfind("]"))
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            pass
    raise ValueError(f"JSON 파싱 실패. 모델 응답 앞부분: {raw[:300]}")


def refine_text(current: str, instruction: str, model: Optional[str] = None,
                context: str = "", max_tokens: int = 4000) -> str:
    """생성된 초안(Markdown)을 채팅 지시로 수정."""
    system = (
        "당신은 한국어 문서 편집 전문가입니다. 사용자의 수정 지시에 따라 "
        "주어진 문서를 고쳐 전체 문서를 다시 출력하세요. 부분만 출력하지 말고 "
        "수정이 반영된 완성본 전체를 Markdown 으로 출력합니다."
    )
    prompt = (
        (f"[참고 자료]\n{context}\n\n" if context else "")
        + f"[현재 문서]\n{current}\n\n"
        + f"[수정 지시]\n{instruction}\n\n"
        + "위 지시를 반영한 전체 문서를 Markdown 으로 출력하세요."
    )
    return generate_text(prompt, model=model, system=system, max_tokens=max_tokens)


def refine_json(current: Any, instruction: str, model: Optional[str] = None,
                context: str = "", max_tokens: int = 4000) -> Any:
    """슬라이드/표 등 구조화 산출물을 채팅 지시로 수정."""
    system = (
        "당신은 문서 구조 편집기입니다. 주어진 JSON 문서를 수정 지시에 따라 고쳐 "
        "동일한 스키마의 완성본 JSON 전체를 출력하세요."
    )
    prompt = (
        (f"[참고 자료]\n{context}\n\n" if context else "")
        + f"[현재 JSON]\n{json.dumps(current, ensure_ascii=False, indent=2)}\n\n"
        + f"[수정 지시]\n{instruction}\n\n"
        + "수정 반영된 JSON 전체만 출력하세요."
    )
    return generate_json(prompt, model=model, system=system, max_tokens=max_tokens)


def health() -> Dict[str, Any]:
    """프록시 연결 상태 점검(가벼운 호출). UI 진단용."""
    try:
        txt = generate_text("OK 라고만 답하세요.", max_tokens=5)
        return {"ok": True, "sample": txt.strip()[:20]}
    except LLMConfigError as e:
        return {"ok": False, "error": str(e), "kind": "config"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "kind": "call"}
