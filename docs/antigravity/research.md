# 조사: API 키 없는 Google 로그인 LLM (gemini-cli → Antigravity)

문서 생성 기능을 회사 LiteLLM 프록시(API 키 방식)에서, **API 키 없이 Google 계정 할당량으로
Gemini 를 쓰는 방식**으로 전환하기 위한 기술 조사 기록.

## 1. 핵심 변화 — gemini-cli 종료, Antigravity 전환

- 처음 검토한 경로는 **gemini-cli 의 개인 OAuth**(키 없이 Google 로그인 → `cloudcode-pa.googleapis.com`
  Code Assist 내부 API 호출)였다.
- 그러나 **gemini-cli / Code Assist 개인 OAuth 는 2026-06-18 부로 서빙 중단**된다(무료·Google AI
  Pro·Ultra 모두). 후속은 **Google Antigravity** 로 통합.
- 따라서 **Antigravity CLI(`agy`)** 경로를 채택한다. `agy` 도 키 없이 Google 로그인으로 그 계정의
  할당량을 사용한다.

## 2. 왜 "직접 API 호출"이 아니라 "공식 CLI 호출"인가

- Antigravity 백엔드 API 를 직접 역공학해 호출하는 방식(서드파티 라이브러리들 존재)은 **Antigravity
  약관상 서드파티 제품 사용 금지**에 해당하고, 실제로 **계정 차단 보고**가 있었다.
- 그래서 우리 앱은 **공식 `agy` 바이너리를 subprocess 로 호출**한다. 인증·할당량·엔드포인트를 모두
  공식 클라이언트가 처리하므로 약관 위반/차단 위험이 없고, 6/18 이후에도 유지된다.

## 3. 동작 방식

- 인증: 사용자가 터미널(또는 앱 내장 터미널)에서 `agy` 1회 로그인 → 브라우저 Google OAuth.
  토큰은 `~/.antigravity/oauth_creds.json` 에 저장되고 자동 갱신된다(키 관리 불필요).
- 호출(비대화식):
  ```
  agy --print "<프롬프트>" --output-format json --model <모델> --print-timeout <t>s --dangerously-skip-permissions
  ```
  JSON `response` 필드에서 응답 텍스트를 추출한다. (신생 기능이라 stdout 스키마/버그 변동 가능 →
  관용적 파싱 + plain-text 폴백을 둔다.)
- 신원: 앱은 `oauth_creds.json` 의 id_token(JWT)/userinfo 로 로그인 email 을 읽어 앱 계정·세션으로 쓴다.
  하나의 Google 로그인이 **신원 + LLM 할당량**을 모두 담당한다.

## 4. 무료 vs Pro 할당량

| 경로 | 무료 | Google AI Pro($20/월) | Ultra | 비고 |
|---|---|---|---|---|
| (구) Gemini CLI OAuth | 1,000건/일 · 60건/분 | ~1,500건/일 | ~2,000건/일 | **2026-06-18 종료** |
| **Antigravity (agy) — 채택** | ~20건/일(주간 한도) 또는 24h 롤링 ~200건 | 가변·비공개: "가장 넉넉", **5시간마다 리필** + 주간 상한 | 최상위 한도 | 본 구현 |
| (참고) AI Studio API 키 | ~250~1,500건/일(Flash 중심) | — | — | 키 필요(미채택) |

- **Pro 정확한 건수는 Google 비공개**: 고정 건수 → "작업량(work done)" 기반 가변 할당량으로 변경,
  5시간마다 리필 + 주간 상한, 작업 복잡도에 비례 소모. 확실한 건 무료보다 훨씬 크다는 점.
- **대량 문서 생성**은 각 사용자가 **자기 Google AI Pro/Ultra 계정으로 `agy` 로그인**해야 충분하다.
  무료 계정이면 무료 한도로 제한된다.

## 5. 알려진 이슈 / 대응

- `agy --print` 의 stdout 출력 버그 사례가 보고됨 → 본 구현은 JSON 파싱 실패 시 plain-text/마지막 JSON
  라인 폴백으로 대응.
- `agy` 는 코딩 에이전트이므로, 문서 생성 시 "도구/파일조작 금지, 요청 텍스트/JSON만 출력" 가드 프롬프트를
  앞에 붙인다(services/agy/runner.py 의 `_GUARD_SYSTEM`).
- 하위명령(로그아웃/모델변경/사용량)의 정확한 이름은 설치 후 `agy --help` 로 확정한다.

## 6. 참고 링크
- https://antigravity.google · https://antigravity.google/docs/cli-using
- https://github.com/google-antigravity/antigravity-cli
- 전환 공지: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
