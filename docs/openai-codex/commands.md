# OpenAI Codex CLI(`codex`) 명령어 모음

> `codex` = OpenAI **Codex CLI**. ChatGPT 로그인(OAuth)으로 API 키 없이 GPT 사용.

## 자주 쓰는 명령

| 목적 | 명령 | 설명 |
|---|---|---|
| **ChatGPT 로그인** | `codex login` | 브라우저 OAuth. 헤드리스는 `codex login --device-auth` |
| **로그인 상태** | `codex login status` | 로그인돼 있으면 exit 0 |
| **로그아웃 / 계정 전환** | `codex logout` | 자격증명 삭제 후 다시 `codex login` |
| **단발 질의(비대화식)** | `codex exec "프롬프트"` | 최종 답을 **stdout** 으로 출력(진행상황은 stderr). |
| **stdin 으로 프롬프트** | `... \| codex exec` (위치인자 생략) | 긴 프롬프트는 인자 길이 제한이 있어 **stdin** 권장. 앱이 이렇게 호출 |
| **모델 지정** | `codex exec "..." -m <model>` | 예: `-m gpt-5.5` (정확한 ID는 `codex debug models`) |
| **모델 목록** | `codex debug models` | 사용 가능한 모델 카탈로그 (**JSON** 출력) |

### 현재 제공 모델 (codex 로그인 경로)
`codex debug models` 가 노출하는 선택 가능한 모델은 다음과 같다(시점에 따라 변동):

| slug(`-m` 값) | 표시명 | 메모 |
|---|---|---|
| `gpt-5.5` | GPT-5.5 | frontier · 코딩/추론 강함 |
| `gpt-5.4` | GPT-5.4 | 상급 균형 |
| `gpt-5.4-mini` | GPT-5.4-Mini | 가볍고 저렴 |

- `codex debug models` 출력은 **JSON**(`{"models":[{"slug","display_name","visibility",...}]}`) 이다.
  앱은 이 JSON 을 파싱해 `visibility:"hide"` 인 내부 모델(예: `codex-auto-review`)을 빼고 위 목록만 보여준다.
- 각 모델은 추론 강도(low/medium/high/xhigh)를 갖지만, 그건 **모델이 아니라 옵션**이라 목록엔 안 나온다.
- OpenAI **API** 에는 더 많은 모델이 있지만, **키 없는 codex 로그인** 경로는 위 GPT-5.x 만 노출한다.
| **파일 저장** | `codex exec "..." -o out.txt` | 최종 메시지를 파일로 |
| **안전 모드(읽기전용)** | `codex exec ... -s read-only` | 파일변경 없이(문서생성용, 앱 기본). 값: `read-only`/`workspace-write`/`danger-full-access` |

> 참고: 이 버전 codex 에는 `-a/--ask-for-approval` 플래그가 없다. 비대화식 `exec` 는 승인 프롬프트가
> 없고, `-s read-only` 로 파일변경을 막는다. (예전 `-a never` 는 더 이상 유효하지 않음 → 제거)

## 앱 내부 호출
앱은 문서 생성 시 다음과 같이 호출한다(가드 프롬프트 + 읽기전용 샌드박스, 프롬프트는 **stdin**):
```
<프롬프트>  | codex exec --skip-git-repo-check -s read-only -m <선택모델> -o <임시파일>
```
- 프롬프트를 **stdin** 으로 넣는다(위치 인자로 주면 Windows 명령행 길이 제한(~32KB)에 걸려
  첨부가 많은 긴 프롬프트가 잘려 codex 가 빈 입력으로 되묻는다 — "What would you like me to generate?").
- 최종 메시지는 `-o <파일>` 로 받고(가장 깔끔), 비면 stdout 으로 폴백해 산출물로 렌더한다.

## 참고
- 로그인/모델 선택은 앱의 **[⚙ 연결 상태]** 와 **[로그인 관리]** 화면에서 버튼으로 할 수 있다.
- 대량 사용은 ChatGPT Plus/Pro 등 상위 구독 권장(등급별 할당량 상이).
