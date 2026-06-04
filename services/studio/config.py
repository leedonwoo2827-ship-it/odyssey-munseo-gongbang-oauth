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

# ── liteLLM (회사 프록시) ────────────────────────────────────────────
# 보안: 내부 주소/키는 코드에 하드코딩하지 않는다(공개 저장소 안전).
# 화면 '연결 설정'(settings.json)에서 입력한 값이 최우선, 그다음 환경변수/.env.
DEFAULT_LITELLM_URL = ""
LITELLM_URL = os.environ.get("UBION_LITELLM_URL", DEFAULT_LITELLM_URL)
LITELLM_KEY = os.environ.get("UBION_LITELLM_KEY")

# 사용자가 화면에서 입력한 연결 설정 저장 파일
SETTINGS_FILE = os.path.join(STUDIO_DATA, "settings.json")

# 기본 모델 (레시피에서 override 가능)
DEFAULT_MODEL = os.environ.get("STUDIO_DEFAULT_MODEL", "claude-sonnet-4-6")
# 긴 입력 요약 등에 쓰는 대용량 컨텍스트 모델
LONG_MODEL = os.environ.get("STUDIO_LONG_MODEL", "gemini-3.1-pro-preview")

# 입력 텍스트 한 파일당 추출 상한 (토큰 폭주 방지) — 문자 수 기준
MAX_CHARS_PER_INPUT = int(os.environ.get("STUDIO_MAX_CHARS_PER_INPUT", "40000"))


def ensure_dirs() -> None:
    """런타임 디렉터리 생성 (모듈 로드 시/생성 직전 호출)."""
    for d in (RECIPES_DIR, ASSETS_DIR, STUDIO_DATA, OUTPUTS_DIR, UPLOADS_DIR):
        os.makedirs(d, exist_ok=True)


def load_settings() -> dict:
    """화면에서 저장한 연결 설정(settings.json) 로드. 없으면 빈 dict."""
    import json
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_settings(url: str | None, key: str | None) -> dict:
    """연결 설정 저장. 빈 키는 기존 값 유지(마스킹된 값 재전송 시 보호)."""
    import json
    ensure_dirs()
    data = load_settings()
    if url is not None and url.strip():
        data["litellm_url"] = url.strip().rstrip("/")
    if key is not None and key.strip() and "•" not in key:
        data["litellm_key"] = key.strip()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def get_litellm() -> tuple[str, str | None]:
    """실제 사용할 (url, key). 우선순위: 화면 설정 > 환경변수/.env > 기본값."""
    s = load_settings()
    url = s.get("litellm_url") or os.environ.get("UBION_LITELLM_URL") or DEFAULT_LITELLM_URL
    key = s.get("litellm_key") or os.environ.get("UBION_LITELLM_KEY")
    return url, key


def mask_key(key: str | None) -> str:
    """UI 표시용 키 마스킹: sk-••••WWw 형태."""
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return key[:3] + "••••" + key[-3:]


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
