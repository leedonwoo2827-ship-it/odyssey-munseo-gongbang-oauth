# OpenAI Codex CLI(`codex`) 설치 · 로그인

이 앱은 OpenAI도 **API 키 없이** 쓸 수 있게 **Codex CLI**의 **"Sign in with ChatGPT"(OAuth)** 를
사용한다. `codex` 에 ChatGPT 계정으로 로그인하면 그 **구독 할당량**으로 GPT 모델을 호출한다.
(공급자 선택은 앱의 [⚙ 연결 상태] 또는 로그인 화면의 **공급자 토글**에서.)

> `codex` = OpenAI **Codex CLI** 실행 명령어. agy(Gemini)와 같은 "키 없는 로그인" 패턴이다.

## 공식 링크
- 인증: https://developers.openai.com/codex/auth
- 비대화식(exec): https://developers.openai.com/codex/noninteractive
- GitHub: https://github.com/openai/codex

## 설치
Codex CLI는 npm(또는 Homebrew/바이너리)로 설치한다.

### Windows / macOS / Linux (npm)
```bash
npm install -g @openai/codex
codex --version
```
(Node.js 필요. 본 앱 `setup.bat` 이 npm 이 있으면 자동 설치를 시도한다.)

## 로그인 (최초 1회)
```bash
codex login
```
- 브라우저가 열리며 **ChatGPT 계정으로 로그인** → 완료.
- 헤드리스/원격: `codex login --device-auth` (코드 입력 방식).
- 자격증명은 `~/.codex/auth.json`(또는 OS 키링)에 저장된다. **토큰이므로 비밀로 취급**.

## 동작 확인
```bash
codex login status        # 로그인돼 있으면 exit 0
codex debug models        # 제공 모델 목록(JSON): gpt-5.5 / gpt-5.4 / gpt-5.4-mini
codex exec "say OK" -m gpt-5.5   # 최종 답이 stdout 으로 출력
```

## 계정 전환 / 로그아웃
```bash
codex logout   # 자격증명 삭제 → 다시 codex login 으로 다른 계정
```

## 앱과의 연동(요약)
- 로그인 판정: `codex login status` exit 코드.
- 문서 생성: `codex exec "<프롬프트>" -m <model> -s read-only -a never` → stdout 캡처.
- 모델 목록: `codex debug models`(JSON). 앱이 파싱해 [⚙ 연결 상태] 드롭다운에 표시(현재 gpt-5.5/5.4/5.4-mini).
- 대량 사용은 **ChatGPT Plus/Pro** 등 상위 구독 권장(등급별 할당량 상이). 비용 비교 → [비용표](../antigravity/비용_할당량_비교.md)
