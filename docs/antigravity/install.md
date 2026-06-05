# Antigravity CLI(`agy`) 설치 가이드 (Windows / macOS)

이 앱은 LLM 호출을 구글 공식 **Antigravity CLI(`agy`)** 에 위임한다. API 키가 필요 없고,
`agy` 에 Google 계정으로 한 번 로그인하면 그 계정의 할당량으로 Gemini 모델을 사용한다.

> 명령어는 **PowerShell 이 아니라 cmd / Git Bash** 기준이다.

## 공식 링크
- 메인: https://antigravity.google
- CLI 문서: https://antigravity.google/docs/cli-using
- GitHub: https://github.com/google-antigravity/antigravity-cli

## 설치

### Windows — cmd (명령 프롬프트)
```cmd
curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd && install.cmd && del install.cmd
agy --version
```

### Windows — Git Bash
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
agy --version
```
- `agy: command not found` 이면 새 Git Bash 창을 열거나, 설치 경로
  `%LOCALAPPDATA%\Antigravity\agy.exe` 를 PATH 에 추가한다.

### macOS — 터미널 (bash/zsh)
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
agy --version
```
- 설치 위치: `~/.local/bin/agy`

> npm / Homebrew 설치는 없다(Go 단일 바이너리).

## 로그인 (최초 1회)
```bash
agy                  # 첫 실행 시 로그인 마법사 → 브라우저에서 Google 로그인(Desktop OAuth)
```
- 대량 문서 생성에는 **Google AI Pro/Ultra 구독 계정** 로그인을 권장(무료는 하루 ~20건 수준).
- 계정 전환: 앱 터미널의 **[로그아웃]** 버튼(저장된 자격증명 삭제) 후 다시 `agy` 로그인.

## 동작 확인
```bash
agy --print "say OK"
```
JSON 응답이 나오면 정상. 이후 앱(로그인 화면의 "Google로 로그인" 또는 우측 상단 메뉴)에서
바로 사용할 수 있다. 앱에는 **내장 터미널**(`/terminal`)도 있어 브라우저 안에서 위 명령들을
그대로 실행할 수 있다(로그인·계정전환·모델변경·사용량 조회).

## 앱과의 연동(요약)
- 앱은 `agy` 인증정보(`~/.antigravity/oauth_creds.json`)에서 로그인 email 을 읽어 앱 세션을 만든다.
- LLM 호출은 `agy --print "<프롬프트>"` 형태(평문 응답)로 이뤄진다. 모델 지정은 `agy models` 로 확인 후 `--model`.
- 관련 환경변수: `AGY_BIN`, `AGY_PRINT_TIMEOUT`, `STUDIO_DEFAULT_MODEL`, `STUDIO_LONG_MODEL`.
