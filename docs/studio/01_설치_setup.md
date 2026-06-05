# 01 · 설치 (setup.bat)

## 준비물
- **Python 3.11~3.13** ([python.org](https://www.python.org/downloads/)). 설치 시 **"Add Python to PATH"** 체크 필수.
- **인터넷 연결** + 공급자 1개 이상의 계정 (둘 중 편한 쪽, 화면에서 토글):
  - **Gemini** → **Google 계정** (Antigravity CLI `agy`). 대량 생성은 Google AI Pro/Ultra 권장.
  - **OpenAI** → **ChatGPT 계정** (Codex CLI `codex`, Node.js 필요). 대량은 ChatGPT Plus/Pro 권장.
- (선택) HWPX 네이티브 생성을 원하면 **한컴 한글** 설치.

## 설치 방법 — `setup.bat` 더블클릭
탐색기에서 `setup.bat` 을 더블클릭하면 검은 창이 뜨고 자동으로 진행됩니다.

`setup.bat` 이 하는 일(순서대로):
1. Python 확인 (`py` 또는 `python`).
2. 가상환경 `venv\` 생성. (프로젝트만의 독립 공간 — PC 전체에 영향 없음)
3. 라이브러리 설치 (`pip install -r requirements.txt`). **처음엔 몇 분** 걸립니다.
4. **CLI 설치** — 인터넷에서 자동 설치 시도:
   - **Antigravity CLI(`agy`)** — Gemini용. (실패 시 [Antigravity 설치](../antigravity/install.md) 참고)
   - **Codex CLI(`codex`)** — OpenAI용. npm 이 있으면 `npm i -g @openai/codex` 자동 시도. (실패 시 [Codex 설치](../openai-codex/install.md) 참고)
5. 최초 설정(`setup.py`) — 데이터 폴더/DB 초기화. (질문 없이 진행)

마지막에 **"SETUP COMPLETE"** 가 보이면 성공입니다. 창은 아무 키나 누르면 닫힙니다.

> **로그인(최초 1회)**: 쓰려는 공급자에 한 번만 로그인하면 됩니다(둘 다 해두고 토글해도 됨).
> - **Gemini**: 터미널/내장터미널에서 `agy` 실행 → 브라우저로 **Google 로그인**.
> - **OpenAI**: `codex login` 실행 → 브라우저로 **ChatGPT 로그인**.
>
> 앱의 **[로그인 관리]** 화면에서 공급자를 고르고 **[로그인]** 버튼만 눌러도 해당 명령이 터미널로 떠요.
> **API 키 입력은 필요 없습니다.** → [Antigravity/Google](../antigravity/install.md) · [OpenAI/Codex](../openai-codex/install.md)

## 정상 동작 확인 포인트
- "라이브러리 설치" 단계에서 빨간 오류 없이 끝났는가.
- `venv\Scripts\python sanity-check-agy.py` 로 agy 설치/로그인/모델호출이 통과하는가. (로그인 전이면 안내가 나옵니다)

## 다시 실행해도 안전
`setup.bat` 은 여러 번 눌러도 됩니다. 이미 만들어진 것은 건너뛰고, 라이브러리만 최신으로 맞춥니다.

## 자주 나는 문제
- **"Python 3.11 이상이 필요합니다"** → Python 미설치 또는 PATH 누락. 재설치 시 PATH 체크.
- **설치가 느리다/멈춘 듯하다** → 첫 설치는 수 분 정상. 네트워크 상태 확인.
- **agy 자동설치 실패** → 인터넷/프록시 확인 후 수동 설치. → [Antigravity 설치](../antigravity/install.md)
- **codex 자동설치 실패** → Node.js(npm) 설치 여부 확인 후 `npm i -g @openai/codex`. → [Codex 설치](../openai-codex/install.md)
- **로그인이 안 됨** → 쓰려는 공급자에 로그인했는지 확인: Gemini는 `agy`(설치확인 `agy --version`),
  OpenAI는 `codex login`(상태확인 `codex login status`).

설치가 끝나면 → [02 · 실행](02_실행_run.md)
