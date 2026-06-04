#!/usr/bin/env python
"""
Ubion LiteLLM 마이그레이션 sanity check (Python)

사용:
    python Ubion_liteLLM_Migration_Kit/sanity-check.py

3가지 검증:
    1. 환경변수 등록
    2. 프록시 도달성 (HTTPS 인증)
    3. 가장 싼 모델 한 번 호출 (openai SDK)

의존성: openai (3 검증용)
    설치 안 되어 있으면 해당 단계는 SKIP.

(Vercel AI SDK는 TypeScript 전용 — Python 프로젝트는 openai SDK 직접 사용 기준)
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request

OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m⊘\033[0m"

stats = {"pass": 0, "fail": 0, "skip": 0}


def step(label: str, status: str, detail: str = "") -> None:
    marker = OK if status == "ok" else FAIL if status == "fail" else SKIP
    suffix = f" — {detail}" if detail else ""
    print(f"{marker} {label}{suffix}")
    stats[{"ok": "pass", "fail": "fail", "skip": "skip"}[status]] += 1


# ---------------------------------------------------------------------------
# 1. 환경변수
# ---------------------------------------------------------------------------
url = os.environ.get("UBION_LITELLM_URL")
key = os.environ.get("UBION_LITELLM_KEY")

if not url or not key:
    step(
        "환경변수",
        "fail",
        f"UBION_LITELLM_URL={'set' if url else 'MISSING'}, "
        f"UBION_LITELLM_KEY={'set' if key else 'MISSING'}",
    )
    print("\n  → Ubion_liteLLM_Migration_Kit/bootstrap.sh 또는 bootstrap.ps1 실행 권장")
    sys.exit(1)

step("환경변수", "ok", f"URL={url}")


# ---------------------------------------------------------------------------
# 2. 도달성 (HTTPS health)
# ---------------------------------------------------------------------------
try:
    req = urllib.request.Request(
        f"{url}/health/liveliness",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status == 200:
            step("프록시 도달성", "ok", f"HTTP {resp.status}")
        else:
            step("프록시 도달성", "fail", f"HTTP {resp.status} — 키 또는 URL 확인")
            sys.exit(1)
except urllib.error.HTTPError as e:
    step("프록시 도달성", "fail", f"HTTP {e.code} — 키 또는 URL 확인")
    sys.exit(1)
except Exception as e:
    step("프록시 도달성", "fail", str(e))
    print("\n  → 사내망(WiFi/유선) 연결 상태 확인: 회사 liteLLM 호스트 ping")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 3. 가장 싼 모델 호출 (openai SDK)
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=f"{url}/v1")
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model="gemini-3.1-flash-lite",
        messages=[{"role": "user", "content": "Say 'ok' in one word."}],
        max_tokens=10,
    )
    text = (resp.choices[0].message.content or "").strip()
    elapsed = int((time.monotonic() - t0) * 1000)
    step("openai SDK 호출", "ok", f"{elapsed}ms, {text!r}")
except ModuleNotFoundError:
    step("openai SDK 호출", "skip", "openai 패키지 없음 (pip install openai)")
except Exception as e:
    step("openai SDK 호출", "fail", str(e)[:200])


# ---------------------------------------------------------------------------
# 4. 구조화 출력 (response_format=json_schema)
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI  # 이미 위에서 import 시도

    client = OpenAI(api_key=key, base_url=f"{url}/v1")
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=200,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "integer"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["answer", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    content = resp.choices[0].message.content
    step("구조화 출력 (json_schema)", "ok", f"{elapsed}ms, {content[:80]!r}")
except ModuleNotFoundError:
    step("구조화 출력 (json_schema)", "skip", "openai 패키지 없음")
except Exception as e:
    step("구조화 출력 (json_schema)", "fail", str(e)[:200])


# ---------------------------------------------------------------------------
# 종합
# ---------------------------------------------------------------------------
print(f"\n결과: 성공 {stats['pass']}  실패 {stats['fail']}  스킵 {stats['skip']}")
if stats["fail"] > 0:
    print("\n→ docs.litellm.ai 또는 fedu@ubion.co.kr 문의")
    sys.exit(1)
print("\n→ 마이그레이션 완료. 비용은 ${UBION_LITELLM_URL}/ui/ 에서 추적")
