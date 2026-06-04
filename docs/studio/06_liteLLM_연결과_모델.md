# 06 · liteLLM 연결과 모델 선택

회사 방침에 따라 **모든 LLM 호출은 사내 liteLLM 프록시로만** 나갑니다.
(개별 OpenAI/Anthropic 키를 직접 쓰지 않습니다. 비용 추적·폴백·캐시가 중앙에서 관리됨.)

## 연결 설정 (앱 화면에서 입력 — 권장)
보안을 위해 **주소와 키는 코드/문서에 적혀 있지 않습니다.** 회사에서 받은 값을 앱에서 직접 넣습니다.

1. `run.bat` 으로 앱을 켜면, 연결이 안 돼 있을 때 **'⚙ 연결 설정' 창이 자동으로** 뜹니다.
   (언제든 오른쪽 위 **⚙ 연결 설정** 버튼으로 다시 열 수 있습니다.)
2. **liteLLM 주소(URL)** 와 **API 키(virtual key)** 를 입력 → **저장하고 연결 확인**.
3. 입력값은 이 PC 의 `data/studio/settings.json` 에만 저장되고, 다음부터 자동 사용됩니다.
   (재시작 불필요, 즉시 적용)

- **사내망/VPN** 에 연결돼 있어야 프록시에 접속됩니다.
- URL/키를 모르면 담당자에게 **liteLLM 주소** 와 **API 키** 를 요청하세요.

> 고급: `.env` 의 `UBION_LITELLM_URL`/`UBION_LITELLM_KEY` 로 넣어도 됩니다(우선순위: 화면 설정 > .env).
> 단, `.env` 는 외부/깃허브에 공유하지 마세요(이미 `.gitignore` 처리).

## 연결 확인
- 화면 우측 상단 점: **🟢 연결됨** / **🔴 미연결**(마우스 올리면 원인).
- 콘솔/명령에서: `venv\Scripts\python sanity-check.py`
- API: 브라우저로 `http://127.0.0.1:7000/api/studio/health` → `llm.ok` 가 `true` 인지 확인.

## 모델 선택
기본값(레시피에서 `model:` 로 덮어쓸 수 있음):
- 본문 작성 기본: `claude-sonnet-4-6` — 한국어 보고서 품질 우수.
- 긴 입력/대량 요약: `gemini-3.1-pro-preview` — 큰 컨텍스트.
- 빠르고 저렴: `claude-haiku-4-5`, `gemini-3-flash-preview`.
- 코딩/정밀 추론: `claude-opus-4-7`.

`.env` 전역 기본값:
```
STUDIO_DEFAULT_MODEL=claude-sonnet-4-6
STUDIO_LONG_MODEL=gemini-3.1-pro-preview
```
레시피 개별 지정:
```yaml
model: gemini-3.1-pro-preview
```

## 비용/캐시 (참고)
- 동일 프롬프트는 프록시 캐시(약 10분)로 추가 비용이 들지 않을 수 있습니다.
- 사용량/비용은 회사 프록시 대시보드(`<프록시 주소>/ui/`)의 Spend Logs 에서 키별로 확인됩니다.

## 마이그레이션 키트
연결 래퍼(`ubion_llm.py`)와 점검 스크립트(`sanity-check.py`)는 회사
`Ubion_liteLLM_Migration_Kit` 에서 가져온 것입니다. 모델 quirk(예: 일부 모델의
`max_tokens` 처리)는 래퍼가 자동 처리합니다.
