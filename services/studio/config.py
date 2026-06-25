"""스튜디오 모듈 경로/환경 설정."""
import os

try:
    # odysseus 코어 상수 (BASE_DIR, DATA_DIR)
    from core.constants import BASE_DIR, DATA_DIR
except Exception:  # pragma: no cover - 단독 테스트 폴백
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ) + os.sep
    DATA_DIR = os.path.join(BASE_DIR, "data")

# ── 레시피 / 템플릿 위치 ─────────────────────────────────────────────
RECIPES_DIR = os.path.join(BASE_DIR, "knowledge", "recipes")
# 회사 디자인팀이 양식을 떨궈 두는 곳 (스펙: assets/hwpx_template.hwpx 등)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# 포맷별 기본 회사 템플릿 (있으면 자동 적용, 없으면 내장 기본)
DEFAULT_TEMPLATES = {
    "hwpx": os.environ.get("HWPX_TEMPLATE_PATH", os.path.join(ASSETS_DIR, "hwpx_template.hwpx")),
    "pptx": os.environ.get("PPTX_TEMPLATE_PATH", os.path.join(ASSETS_DIR, "pptx_template.pptx")),
    "docx": os.environ.get("DOCX_TEMPLATE_PATH", os.path.join(ASSETS_DIR, "docx_template.docx")),
}

# ── 산출물 / 업로드 저장 위치 ────────────────────────────────────────
STUDIO_DATA = os.path.join(DATA_DIR, "studio")
OUTPUTS_DIR = os.path.join(STUDIO_DATA, "outputs")
UPLOADS_DIR = os.path.join(STUDIO_DATA, "uploads")
# 근거 기반 워크플로(자료학습/검수)용 잡별 근거 청크 저장 위치
EVIDENCE_DIR = os.path.join(STUDIO_DATA, "evidence")

# ── LLM 백엔드 ───────────────────────────────────────────────────────
# OpenAI Codex CLI(`codex`)로 호출한다. API 키/URL 설정이 없다(인증·할당량은 codex 가
# 담당; 사용자가 `codex login` 으로 1회 ChatGPT 로그인). → services/codex 참고.

# 기본 모델 (비우면 codex 자체 기본 모델; 화면/레시피에서 override 가능)
DEFAULT_MODEL = os.environ.get("STUDIO_DEFAULT_MODEL", "")
# 긴 입력 요약 등에 쓰는 모델 (비우면 기본 모델)
LONG_MODEL = os.environ.get("STUDIO_LONG_MODEL", "")

# 입력 텍스트 한 파일당 추출 상한 (토큰 폭주 방지) — 문자 수 기준
MAX_CHARS_PER_INPUT = int(os.environ.get("STUDIO_MAX_CHARS_PER_INPUT", "40000"))


def ensure_dirs() -> None:
    """런타임 디렉터리 생성 (모듈 로드 시/생성 직전 호출)."""
    for d in (RECIPES_DIR, ASSETS_DIR, STUDIO_DATA, OUTPUTS_DIR, UPLOADS_DIR, EVIDENCE_DIR):
        os.makedirs(d, exist_ok=True)


def template_for(fmt: str, override: str | None = None) -> str | None:
    """포맷에 적용할 회사 템플릿 경로 반환 (존재할 때만, 없으면 None)."""
    candidates = []
    if override:
        # 레시피의 output.template 은 BASE_DIR 또는 ASSETS_DIR 기준 상대경로 허용
        candidates += [
            override,
            os.path.join(BASE_DIR, override),
            os.path.join(ASSETS_DIR, override),
        ]
    default = DEFAULT_TEMPLATES.get(fmt)
    if default:
        candidates.append(default)
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None
