# 아키텍처: Google 로그인 + agy LLM 백엔드

## 한 줄 요약
하나의 Google 로그인(`agy`)이 **앱 신원**과 **LLM 할당량**을 동시에 담당한다. API 키 없음.

## 구성도
```
[브라우저]
  │  ① "Google로 로그인" 또는 내장 터미널(/terminal)
  ▼
[Odysseus FastAPI]
  ├─ routes/google_auth_routes.py
  │     /api/auth/google/status  → agy 설치/로그인 email 조회
  │     /api/auth/google/login   → email 프로비저닝 + 세션 쿠키 발급
  │
  ├─ routes/agy_terminal_routes.py  (WebSocket, loopback 전용)
  │     /api/agy/terminal/ws  ↔  services/agy/pty_terminal.PtySession  ↔  셸(cmd/bash)
  │            └ 사용자가 `agy` 로그인/로그아웃·모델변경·사용량조회를 직접 입력
  │
  └─ services/studio (문서 생성)
        llm.py → services/agy/AgyClient.chat()
                    └ subprocess: agy --print "<prompt>" --output-format json --model <m>
                                       │ 인증·할당량은 agy 가 담당
                                       ▼
                              [agy] → Google 계정 할당량으로 Gemini 응답
```

## 신원/세션
- 로그인 = `agy` 의 Google 계정. 앱은 `~/.antigravity/oauth_creds.json` 에서 email 을 읽는다
  (id_token JWT 디코드 → 실패 시 userinfo). → `core/auth.py:ensure_oauth_user(email)` 로 계정 생성,
  `create_session_for_user()` 로 비밀번호 없는 세션 발급. email 이 곧 username·owner 키.
- 비밀번호 로그인은 비활성(`ALLOW_PASSWORD_LOGIN=true` 로 복구 가능).
- 도메인 제한: `GOOGLE_ALLOWED_DOMAINS` (비우면 모든 Google 계정). `ODYSSEUS_ADMIN_EMAIL` 은 admin.

## LLM 호출
- `services/agy/runner.py:AgyClient` 가 과거 `ubion_llm.UbionClient` 의 `.chat(model, messages, max_tokens)`
  시그니처를 그대로 재현(드롭인). studio 의 `llm.py`/`pipeline.py` 호출부는 거의 무수정.
- 모델: `STUDIO_DEFAULT_MODEL`(기본 gemini-3-pro), `STUDIO_LONG_MODEL`(기본 gemini-3-flash).

## 터미널(agy 로그인 UI) 설계 — 2단 폴백

로그인/계정전환/모델·사용량 조회는 터미널에서 `agy` 명령으로 한다. 두 가지 방식을 둔다:

1. **브라우저 내장 터미널(기본)** — `/terminal` 페이지(xterm.js) ↔ WebSocket `/api/agy/terminal/ws`
   ↔ PtySession(pywinpty/ptyprocess). 새 탭에서 바로 입력. (pywinpty 설치 필요)
2. **실제 OS cmd 창(폴백)** — `POST /api/agy/open-terminal` 이 진짜 cmd/터미널 창을 띄워 그 안에서 `agy`
   실행. pywinpty 가 없거나 내장 터미널이 안 될 때 사용(추가 의존성 없음). `/terminal` 페이지의
   **[🪟 실제 cmd 창 열기]** 버튼, 또는 진단(`/api/agy/terminal/diag`)에서 `pty_available=false` 면 안내.

명령어 목록은 [commands.md](commands.md). 둘 다 loopback(127.0.0.1) 전용 + 인증 예외(최초 로그인용).

> 주의: `.bat` 파일은 **ASCII(영문)만** 사용한다. 한글을 넣으면 CP949 콘솔에서 줄이 깨져
> "내부/외부 명령이 아닙니다"로 실패한다(한글 안내는 README·화면에만 둔다).

## 전제 / 보안
- 각 PC = 단일 사용자 / 단일 `agy` 계정. 내장 터미널 WS 는 loopback(127.0.0.1) 직접 연결만 허용.
- 최초 `agy` 로그인을 위해 `/terminal`, `/api/auth/google/*` 는 인증 예외(app.py AUTH_EXEMPT).
- 네트워크 노출 배포에서는 `LOCALHOST_BYPASS=false` 유지(loopback 도 로그인 강제) + 내장 터미널 노출 주의.
```
```
