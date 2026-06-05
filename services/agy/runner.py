"""AgyClient — 구글 공식 Antigravity CLI(`agy`) 를 subprocess 로 호출하는 LLM 래퍼.

설계 의도(중요):
- API 키를 쓰지 않는다. 인증/할당량은 전적으로 `agy` 가 담당한다(사용자가 `agy` 에 1회
  Google 로그인). 우리 앱은 비대화식 호출(`agy --print ... --output-format json`)의 결과만 받는다.
- 회사 LiteLLM 프록시(ubion_llm.UbionClient)의 `.chat(model, messages, max_tokens)` 시그니처를
  그대로 재현하여, services/studio/llm.py 의 호출부를 거의 손대지 않고 교체할 수 있게 한다.

agy 는 본래 "코딩 에이전트" 이므로, 문서/텍스트 생성 용도로 쓸 때는 파일 수정·도구 실행을
하지 않고 요청한 내용만 출력하도록 가드 프롬프트를 앞에 붙인다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

# ── 설정(.env 로 덮어쓰기 가능) ──────────────────────────────────────────────
AGY_BIN = os.environ.get("AGY_BIN", "agy")
# agy --print 단일 호출 타임아웃(초). agy 자체 --print-timeout 과 wall-clock 양쪽에 적용.
AGY_TIMEOUT = int(os.environ.get("AGY_PRINT_TIMEOUT", "300"))
DEFAULT_MODEL = os.environ.get("STUDIO_DEFAULT_MODEL", "gemini-3-pro")

# 문서 생성기로 쓰기 위한 가드(코딩 에이전트의 도구사용/파일조작 억제).
_GUARD_SYSTEM = (
    "You are a text and document generation assistant. "
    "Do NOT run shell commands, do NOT read or write files, do NOT use any tools, "
    "and do NOT perform any coding or repository actions. "
    "Respond with ONLY the requested content as your message — nothing else."
)


class AgyError(RuntimeError):
    """agy 호출 일반 오류."""


class AgyNotInstalled(AgyError):
    """`agy` 실행 파일을 찾을 수 없음."""


class AgyNotAuthenticated(AgyError):
    """agy 에 Google 로그인이 안 되어 있음."""


class AgyQuotaExceeded(AgyError):
    """Google 계정 할당량(quota) 초과."""


class AgyResult:
    """ubion_llm 의 응답 객체와 호환되도록 `.text` 만 제공."""

    __slots__ = ("text", "raw")

    def __init__(self, text: str, raw: Any = None):
        self.text = text
        self.raw = raw


def agy_path() -> Optional[str]:
    """PATH 또는 AGY_BIN 으로 agy 실행 파일 경로를 찾는다. 없으면 None."""
    # 절대경로를 직접 지정한 경우
    if os.path.sep in AGY_BIN or (os.path.altsep and os.path.altsep in AGY_BIN):
        return AGY_BIN if os.path.isfile(AGY_BIN) else None
    return shutil.which(AGY_BIN)


def is_installed() -> bool:
    return agy_path() is not None


def _compose_prompt(messages: List[Dict[str, str]]) -> str:
    """OpenAI 형식 messages 를 agy --print 용 단일 프롬프트 문자열로 합성."""
    parts: List[str] = [_GUARD_SYSTEM]
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if not content:
            continue
        if role == "system":
            parts.append(f"[지침]\n{content}")
        elif role == "assistant":
            parts.append(f"[이전 답변]\n{content}")
        else:  # user
            parts.append(f"[요청]\n{content}")
    return "\n\n".join(parts)


def _classify_error(stdout: str, stderr: str, returncode: int) -> AgyError:
    blob = f"{stdout}\n{stderr}".lower()
    if any(k in blob for k in ("not authenticated", "not logged in", "login required",
                               "please log in", "unauthenticated", "sign in", "auth")):
        # 인증 관련 키워드가 보이면 로그인 문제로 안내(오탐 허용 — 메시지가 친절함)
        if "auth" in blob or "login" in blob or "sign in" in blob:
            return AgyNotAuthenticated(
                "agy 에 Google 로그인이 필요합니다. 터미널에서 `agy` 를 한 번 실행해 "
                "Google 계정으로 로그인한 뒤 다시 시도하세요."
            )
    if any(k in blob for k in ("quota", "resource_exhausted", "rate limit",
                               "429", "too many requests", "exceeded")):
        return AgyQuotaExceeded(
            "Google 계정의 사용 할당량(quota)을 초과했습니다. 잠시 후 다시 시도하거나, "
            "더 큰 할당량의 Google AI Pro/Ultra 계정으로 `agy` 에 로그인하세요."
        )
    snippet = (stderr or stdout or "").strip()[:300]
    return AgyError(f"agy 호출 실패(exit={returncode}): {snippet}")


def _extract_text(stdout: str) -> str:
    """agy --output-format json stdout 에서 모델 응답 텍스트를 추출.

    agy 출력 스키마가 신생 기능이라 변동 가능 → 여러 후보 키를 관용적으로 탐색하고,
    JSON 파싱이 안 되면 stdout 자체를 텍스트로 사용(--output-format 미지원/버그 폴백).
    """
    raw = (stdout or "").strip()
    if not raw:
        return ""
    # 1) 전체가 JSON 인 경우
    try:
        obj = json.loads(raw)
        return _text_from_obj(obj) or raw
    except Exception:
        pass
    # 2) 마지막 줄이 JSON(JSONL) 인 경우 — 뒤에서부터 탐색
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line or line[0] not in "{[":
            continue
        try:
            obj = json.loads(line)
            t = _text_from_obj(obj)
            if t:
                return t
        except Exception:
            continue
    # 3) JSON 이 아니면 plain text 로 간주
    return raw


def _text_from_obj(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in ("response", "output", "text", "result", "content", "message"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, dict):
                inner = _text_from_obj(v)
                if inner:
                    return inner
    return ""


class AgyClient:
    """ubion_llm.UbionClient 드롭인 대체.

    사용:
        client = AgyClient()
        resp = client.chat("gemini-3-pro", messages, max_tokens=4000)
        text = resp.text
    """

    def __init__(self, bin_path: Optional[str] = None,
                 default_model: Optional[str] = None,
                 timeout: Optional[int] = None):
        self.bin = bin_path or AGY_BIN
        self.default_model = default_model or DEFAULT_MODEL
        self.timeout = timeout or AGY_TIMEOUT

    def chat(self, model: Optional[str], messages: List[Dict[str, str]],
             max_tokens: int = 4000) -> AgyResult:
        # max_tokens 는 agy 가 자체 제어하므로 인터페이스 호환용으로만 받는다.
        prompt = _compose_prompt(messages)
        text = self._run(prompt, model or self.default_model)
        return AgyResult(text)

    # 단순 텍스트 1회 호출(헬스체크 등)
    def quick(self, prompt: str, model: Optional[str] = None) -> str:
        return self._run(_compose_prompt([{"role": "user", "content": prompt}]),
                         model or self.default_model)

    def _run(self, prompt: str, model: str) -> str:
        path = agy_path() if self.bin == AGY_BIN else (
            self.bin if os.path.isfile(self.bin) else shutil.which(self.bin))
        if not path:
            raise AgyNotInstalled(
                "Antigravity CLI(`agy`)가 설치되어 있지 않습니다. "
                "docs/antigravity/install.md 를 참고해 설치 후 `agy` 로 Google 로그인하세요."
            )
        cmd = [
            path, "--print", prompt,
            "--output-format", "json",
            "--model", model,
            "--print-timeout", f"{self.timeout}s",
            "--dangerously-skip-permissions",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout + 30,
            )
        except FileNotFoundError as e:
            raise AgyNotInstalled(f"agy 실행 실패: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise AgyError(f"agy 응답 시간 초과({self.timeout}s). 모델/프롬프트를 줄여보세요.") from e

        if proc.returncode != 0:
            raise _classify_error(proc.stdout or "", proc.stderr or "", proc.returncode)

        text = _extract_text(proc.stdout or "")
        if not text.strip():
            # 정상 종료인데 본문이 비면 인증/할당량 문제일 수 있음 → 단서 분류
            raise _classify_error(proc.stdout or "", proc.stderr or "", proc.returncode)
        return text


# 모듈 전역 싱글톤(가벼우므로 import 시 생성해도 무방 — 실제 호출 전엔 agy 를 건드리지 않음)
client = AgyClient()
