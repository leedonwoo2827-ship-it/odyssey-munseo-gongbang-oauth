"""LLM 호출 래퍼 — 회사 방침에 따라 Ubion liteLLM 프록시로만 라우팅.

루트의 ubion_llm.py(UbionClient) 를 지연 로딩한다.
(ubion_llm 은 import 시점에 UBION_LITELLM_KEY 를 요구하므로 절대 모듈 최상위에서 import 하지 않는다.)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import config

_client = None
_client_sig = None  # (url, key) — 설정이 바뀌면 클라이언트 재생성


class LLMConfigError(RuntimeError):
    """프록시 키/URL 미설정 등 설정 문제."""


def _get_client():
    """UbionClient — 화면 '연결 설정'(settings.json) 값을 최우선으로 사용.

    설정(URL/키)이 바뀌면 재시작 없이 즉시 새 클라이언트로 교체한다.
    """
    global _client, _client_sig
    url, key = config.get_litellm()
    if not key:
        raise LLMConfigError(
            "liteLLM 연결이 아직 설정되지 않았습니다.\n"
            "화면 오른쪽 위 '⚙ 연결 설정'을 눌러, 회사에서 받은 URL과 API 키를 입력하세요."
        )
    sig = (url, key)
    if _client is not None and _client_sig == sig:
        return _client
    try:
        # 루트 ubion_llm.py 의 클래스를 직접 인스턴스화(모듈 로드 시 자동생성 client 회피)
        from ubion_llm import UbionClient
        _client = UbionClient(base_url=url, api_key=key)
        _client_sig = sig
    except Exception as e:
        raise LLMConfigError(f"liteLLM 클라이언트 초기화 실패: {e}") from e
    return _client


def chat(messages: List[Dict[str, str]], model: Optional[str] = None,
         max_tokens: int = 4000) -> str:
    """messages(OpenAI 형식) → 응답 텍스트."""
    client = _get_client()
    resp = client.chat(model or config.DEFAULT_MODEL, messages, max_tokens=max_tokens)
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
