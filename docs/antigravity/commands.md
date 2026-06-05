# Antigravity CLI(`agy`) 명령어 모음

앱의 **🖥️ 터미널 열기**(브라우저 내장 터미널, 또는 실제 cmd 창)에서 아래 명령을 그대로 입력합니다.
API 키는 필요 없고, Google 계정 로그인으로 그 계정 할당량을 사용합니다.

> agy 는 비교적 신생 CLI라 일부 하위명령 이름이 바뀔 수 있습니다. **확실한 목록은 `agy --help`**.

## 자주 쓰는 명령

| 목적 | 명령 | 설명 |
|---|---|---|
| **Google 로그인** | `agy` | 첫 실행 시 로그인 마법사 → 브라우저에서 Google 계정 선택 |
| **로그아웃 / 계정 전환** | `agy logout` | 로그아웃 후 다시 `agy` 로 다른 계정 로그인 |
| **버전 확인** | `agy --version` | 설치/버전 확인 |
| **명령 목록(도움말)** | `agy --help` | 사용 가능한 모든 명령·옵션 (가장 정확한 출처) |
| **단발 질의(비대화식)** | `agy -p "프롬프트"` | 한 번 묻고 답만 출력. 스크립트/자동화용 |
| **JSON 출력** | `agy -p "프롬프트" --output-format json` | 결과를 JSON 으로 (앱이 내부적으로 이렇게 호출) |
| **모델 지정** | `agy -p "..." --model gemini-3-pro` | 모델 선택 (예: `gemini-3-pro`, `gemini-3-flash`) |
| **권한 자동승인** | `agy -p "..." --dangerously-skip-permissions` | 비대화식에서 확인 프롬프트 생략 |

> 화면의 버튼이 실제로 보내는 명령:
> - **agy 로그인** → `agy`
> - **로그아웃(계정전환)** → `agy logout`
> - **버전** → `agy --version`
> - **명령 목록(help)** → `agy --help`

## 사용량 / 할당량(quota) 확인
- 정확한 하위명령은 `agy --help` 에서 확인하세요(예: `agy usage` 류가 있을 수 있음).
- 무료 계정은 하루 ~20건 수준으로 작습니다. 많이 쓰려면 **Google AI Pro/Ultra 계정**으로 로그인하세요.
- 할당량 초과 시 앱에서 "할당량(quota)을 초과했습니다" 안내가 뜹니다 → 잠시 후 재시도 또는 상위 계정 로그인.

## 동작 확인 한 줄
```bash
agy -p "say OK" --output-format json
```
JSON 응답이 나오면 정상입니다.

## 설치
설치 방법은 [install.md](install.md) 참고. (Windows cmd / Git Bash / macOS)
