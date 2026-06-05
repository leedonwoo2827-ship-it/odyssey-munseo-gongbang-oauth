"""
문서 생산 스튜디오 (Odysseus Studio) — AIM 해외사업부 N팀 문서 생산 모듈.

NotebookLM 스튜디오처럼 "버튼"으로 동작한다:
  1) 만들 산출물 유형(레시피)을 고르고
  2) 필요한 입력 문서를 끌어다 넣고 (+ 추가 지시/메모를 채팅으로 입력)
  3) "생성"을 누르면 → 산출물(docx/hwpx/pptx/xlsx/md)이 나온다.
  4) 이후 채팅으로 초안을 수정(refine)할 수 있다.

지시(채팅)는 세 군데에서 받는다:
  - 생성 전 메모(initial instruction) → 첫 프롬프트에 포함
  - 입력 없이 메모만으로도 생성 가능
  - 생성 후 채팅(refine) → 초안 재생성

레시피 = knowledge/recipes/*.yaml (필요 입력 + 프롬프트 + 출력형식).
LLM 호출은 구글 공식 Antigravity CLI(`agy`, services/agy)로 라우팅한다(API 키 불필요).
"""

from . import config  # noqa: F401

__all__ = ["config"]
