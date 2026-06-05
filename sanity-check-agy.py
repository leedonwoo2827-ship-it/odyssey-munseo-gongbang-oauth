#!/usr/bin/env python3
"""sanity-check-agy.py — Antigravity CLI(agy) 연동 점검.

프로젝트 루트(odysseus/)에서 실행:
    python sanity-check-agy.py

점검 항목:
  1) agy 설치 여부
  2) agy 에 로그인된 Google 계정(email)
  3) 모델 1회 호출(가장 가벼운 프롬프트)
모두 통과하면 문서 생성에 사용할 준비가 된 것이다.
"""
import sys

OK, BAD = "✅", "❌"


def main() -> int:
    try:
        from services.agy import auth as agy_auth
        from services.agy import AgyClient, AgyError
        from services.agy.runner import agy_path
    except Exception as e:
        print(f"{BAD} services.agy import 실패: {e}")
        print("   → odysseus/ 디렉터리에서 실행하세요.")
        return 2

    # 1) 설치
    path = agy_path()
    if not path:
        print(f"{BAD} agy 미설치 — docs/antigravity/install.md 참고")
        return 1
    print(f"{OK} agy 설치 확인: {path}")

    # 2) 로그인 email
    email = agy_auth.get_account_email()
    if not email:
        print(f"{BAD} agy 미로그인 — 터미널에서 `agy` 실행 후 Google 로그인하세요")
        return 1
    print(f"{OK} 로그인 계정: {email}")

    # 3) 모델 호출
    model = None
    try:
        import os
        model = os.environ.get("STUDIO_DEFAULT_MODEL", "gemini-3-pro")
        client = AgyClient()
        text = client.quick("Reply with exactly: OK", model=model)
        print(f"{OK} 모델 호출 성공({model}): {text.strip()[:60]!r}")
    except AgyError as e:
        print(f"{BAD} 모델 호출 실패({model}): {e}")
        return 1
    except Exception as e:
        print(f"{BAD} 예기치 못한 오류: {type(e).__name__}: {e}")
        return 1

    print("\n→ 모든 점검 통과. 문서 생성 준비 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
