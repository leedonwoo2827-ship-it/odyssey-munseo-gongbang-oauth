# OpenAI Codex CLI(`codex`) 명령어 모음

> `codex` = OpenAI **Codex CLI**. ChatGPT 로그인(OAuth)으로 API 키 없이 GPT 사용.

## 자주 쓰는 명령

| 목적 | 명령 | 설명 |
|---|---|---|
| **ChatGPT 로그인** | `codex login` | 브라우저 OAuth. 헤드리스는 `codex login --device-auth` |
| **로그인 상태** | `codex login status` | 로그인돼 있으면 exit 0 |
| **로그아웃 / 계정 전환** | `codex logout` | 자격증명 삭제 후 다시 `codex login` |
| **단발 질의(비대화식)** | `codex exec "프롬프트"` | 최종 답을 **stdout** 으로 출력(진행상황은 stderr). 앱이 이렇게 호출 |
| **모델 지정** | `codex exec "..." -m <model>` | 예: `-m gpt-5.4` (정확한 ID는 `codex debug models`) |
| **모델 목록** | `codex debug models` | 사용 가능한 모델 카탈로그 |
| **파일 저장** | `codex exec "..." -o out.txt` | 최종 메시지를 파일로 |
| **안전 모드(읽기전용)** | `codex exec "..." -s read-only -a never` | 파일변경·승인프롬프트 없이(문서생성용, 앱 기본) |

## 앱 내부 호출
앱은 문서 생성 시 다음과 같이 호출한다(파일변경/도구사용 차단 + 가드 프롬프트):
```
codex exec "<프롬프트>" -m <선택모델> -s read-only -a never
```
→ stdout(최종 메시지)을 캡처해 산출물로 렌더한다.

## 참고
- 로그인/모델 선택은 앱의 **[⚙ 연결 상태]** 와 **[로그인 관리]** 화면에서 버튼으로 할 수 있다.
- 비용·할당량 비교: [../antigravity/비용_할당량_비교.md](../antigravity/비용_할당량_비교.md)
