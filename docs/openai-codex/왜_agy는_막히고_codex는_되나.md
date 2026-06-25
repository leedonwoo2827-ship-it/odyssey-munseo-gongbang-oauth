# 왜 agy(Antigravity)는 막히고, codex(OpenAI)는 되나

> 요약: **Gemini를 agy(Antigravity CLI)의 "제품 로그인(OAuth)"으로 자동 호출**하는 것은 Google
> 약관 위반이라 계정이 차단된다. 반면 **codex의 `codex exec`는 공식 "비대화(non-interactive)
> 자동화" 모드**라 같은 방식이 약관상 허용된다. 그래서 이 앱은 **agy를 떼고 codex 전용**으로 간다.

## 무슨 일이 있었나
- 이 앱은 LLM을 **사람이 직접 치는 대화형이 아니라 프로그램이 자동으로** 호출한다.
- 초기엔 Gemini를 **agy(Antigravity CLI)** 로 호출했다(`agy --print … --dangerously-skip-permissions`).
- 사용 계정이 갑자기 **403 PERMISSION_DENIED — "This service has been disabled in this account for
  violation of Terms of Service"** 로 차단됐다(eligibility check 실패).

## 핵심 차이 — "제품 로그인 자동화" vs "공식 비대화 모드"

| 구분 | agy (Antigravity / Gemini CLI) | codex (OpenAI Codex CLI) |
|---|---|---|
| 로그인 | **제품 로그인(OAuth)** — 본래 IDE/CLI를 **사람이 대화형으로** 쓰라고 만든 인증 | **`codex login`(ChatGPT OAuth)** |
| 자동/비대화 호출 | **약관상 금지** — "제3자 도구로 OAuth 자원·할당량 접근" | **`codex exec` = 공식 비대화 모드**(자동화 정식 지원) |
| 우리 앱의 사용 | 제3자(우리 앱)가 OAuth 로그인을 프로그램으로 구동 → **위반** | 공식 exec를 프로그램으로 호출 → **허용** |
| 결과 | 계정 **차단(ToS)** | 정상 동작 |

## Google이 직접 명시한 위반 사유
Antigravity 계정 정지 **이의신청 폼**과 공지가 위반 행위를 이렇게 적시한다:
- *"Using third-party software, tools, or services to access Antigravity / Gemini CLI / Gemini Code
  Assist (e.g. OpenCode, Claude Code, OpenClaw with the product OAuth login)."*
- *"제3자 코딩 에이전트로 Gemini를 쓰려면 **product 로그인이 아니라 Vertex/AI Studio API 키**를 써라."*

→ 즉 우리 앱이 agy로 한 일(제3자 도구가 제품 로그인을 자동 사용)이 **정확히 금지 대상**이었다.
혼자 쓸 땐 한동안 안 걸리다가, 호출량이 늘면(예: 여러 사람·반복 자동 호출) 플래그가 걸려 차단된다.

## 왜 codex는 괜찮나
- `codex exec "<프롬프트>"` 는 OpenAI가 **비대화(헤드리스) 자동 실행용으로 공식 제공**하는 모드다
  (문서: https://developers.openai.com/codex/noninteractive). 진행상황은 stderr, 최종 답은 stdout.
- 즉 "프로그램이 codex를 자동 호출"하는 것은 **설계된 사용 방식**이라 약관 충돌이 없다.
- 인증도 `codex login`(ChatGPT)으로 그 구독 할당량을 정상 경로로 사용한다.

## Gemini를 꼭 쓰고 싶다면(참고)
- 합법 경로는 **API 키**(AI Studio / Vertex)로 호출하는 것이다. 단 이는 "키 없는 OAuth"라는
  본 앱의 전제와 어긋나고 사용량 과금이 붙을 수 있다. 그래서 현재는 채택하지 않는다.
- 차단된 개인 계정 복원은 별개 트랙(이의신청 폼/포럼). **복원돼도 그 계정에 agy 자동 사용을
  재개하면 영구 차단**될 수 있으니, 앱에서는 쓰지 않는다.

## 이 저장소의 결론
- `services/agy/`·agy 라우트·내장 터미널·관련 설정/문서를 **제거**했다.
- LLM은 **codex 단일 공급자**(`services/codex`, `services/llm_backend`)로만 동작한다.
- 설치·로그인·생성은 [install.md](install.md) / [commands.md](commands.md) 참고.
