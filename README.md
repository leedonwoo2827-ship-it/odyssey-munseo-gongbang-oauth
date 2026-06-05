# 📑 오디세이 문서공방 (AIM N팀 · Odyssey Studio)

여러 자료를 끌어다 넣고 버튼 하나면, 보고서·계획서·발표자료 **초안**이 완성됩니다.
NotebookLM 스튜디오처럼 쉽게 — 입력은 드래그로, 다듬기는 채팅으로.
결과는 한글(HWPX)·워드·PPT·엑셀로 바로 받아, **검토만 하면 끝**입니다.

---

## ✅ 설치 권장 사양

| 항목 | 최소 | 권장 |
|---|---|---|
| 운영체제 | Windows 10 (64bit) | Windows 11 (64bit) |
| Python | 3.11 | 3.12 ([python.org](https://www.python.org/downloads/) · 설치 시 **Add Python to PATH** 체크) |
| 메모리(RAM) | 8 GB | 16 GB |
| 디스크 여유 | 3 GB | 5 GB 이상 |
| 네트워크 | **인터넷 연결** (Google 로그인 / Antigravity CLI) | |
| 로그인 | **Google 계정** (대량 생성은 Google AI Pro/Ultra 권장) | |
| 브라우저 | Chrome / Edge 최신 | |
| 한글 산출물(.hwpx) 네이티브 생성 | (선택) **한컴 한글 2014+** 설치 + `pywin32` | 한글 미설치 시 자동으로 DOCX/Markdown 으로 대체 |

> **API 키가 필요 없습니다.** LLM 호출은 구글 공식 **Antigravity CLI(`agy`)** 에 위임하며,
> `agy` 에 Google 계정으로 한 번 로그인하면 그 계정 할당량으로 Gemini 를 사용합니다.
> 자세한 설치는 [docs/antigravity/install.md](docs/antigravity/install.md) 참고.

---

## 🚀 시작하기

기본은 **더블클릭 2번**이고, 여기에 **Google 로그인 최초 1회**만 추가됩니다.

### A. 더블클릭으로 (권장)

1. **`setup.bat` 더블클릭** — 처음 한 번. (가상환경 + 라이브러리 + `agy` 설치, 몇 분 소요)
2. **Google 로그인(최초 1회)** — 아래 중 편한 방법:
   - `run.bat` 실행 후 로그인 화면에서 **🖥️ agy 터미널 열기** → 터미널에 `agy` 입력 → 브라우저에서 Google 로그인
   - 또는 검은 콘솔/터미널에 직접 `agy` 입력 후 Google 로그인
3. **`run.bat` 더블클릭** — 실행. 브라우저가 열리면 **Google로 로그인** 버튼을 누릅니다.

종료하려면 검은 콘솔 창을 닫으면 됩니다. **계정 전환**은 터미널에서 `agy logout` 후 다시 `agy` 로그인.

### B. 터미널에서 직접 (cmd / Git Bash — PowerShell 아님)

> 한 줄씩 차례대로 실행하세요.

```bash
REM 1) (Windows cmd) Antigravity CLI 설치
curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd && install.cmd && del install.cmd

REM    (macOS / Git Bash) 는 아래
REM    curl -fsSL https://antigravity.google/cli/install.sh | bash

REM 2) agy 에 Google 로그인 (브라우저가 열립니다 — 최초 1회)
agy

REM 3) 정상 동작 확인
agy --version
agy --print "say OK"

REM 4) 파이썬 가상환경 + 라이브러리 설치 (프로젝트 폴더에서)
py -3 -m venv venv
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt

REM 5) 최초 데이터/DB 초기화
venv\Scripts\python setup.py

REM 6) 연동 점검 (agy 설치/로그인/모델호출)
venv\Scripts\python sanity-check-agy.py

REM 7) 실행
venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port 7000
```

실행 후 브라우저에서 `http://127.0.0.1:7000` → **Google로 로그인**.

> 계정 전환: `agy logout` 후 다시 `agy`. 모델/사용량 등은 같은 `agy` 명령으로 확인합니다(`agy --help`).

---

## 🧭 사용 흐름

1. 왼쪽에서 만들 **산출물 유형**(버튼)을 고릅니다.
2. 가운데에 필요한 **입력 문서를 끌어다 놓습니다**. (입력이 없는 유형은 건너뜀)
3. 필요하면 **추가 지시/메모**를 적습니다. 예) "10차 일정만 강조", "표는 빼고 서술형으로".
   - 입력 없이 **지시만으로도** 생성할 수 있습니다.
4. **생성하기**를 누르면 초안과 다운로드 버튼이 나옵니다.
5. 미리보기 아래 **채팅으로 수정**을 지시하면 초안이 다시 만들어집니다.

---

## 📚 더 알아보기 (자세한 설명서)

자세한 내용은 [`docs/studio/`](docs/studio/) 폴더에 주제별로 정리되어 있습니다.

- [00 · 개요](docs/studio/00_개요.md)
- [01 · 설치 (setup.bat)](docs/studio/01_설치_setup.md)
- [02 · 실행 (run.bat)](docs/studio/02_실행_run.md)
- [03 · 문서 생성 사용법](docs/studio/03_문서_생성_사용법.md)
- [04 · 새 유형(레시피) 추가하기](docs/studio/04_레시피_추가하기.md)
- [05 · 회사 양식(HWPX·PPTX) 만들기](docs/studio/05_양식_만들기.md)
- [07 · 문제 해결 FAQ](docs/studio/07_문제해결_FAQ.md)
- **LLM/로그인(Antigravity·Google)**: [설치](docs/antigravity/install.md) · [agy 명령어 모음](docs/antigravity/commands.md) · [비용·할당량 비교](docs/antigravity/비용_할당량_비교.md) · [분량·품질 올리기 팁](docs/antigravity/팁_분량과_품질_올리기.md) · [아키텍처](docs/antigravity/architecture.md) · [조사](docs/antigravity/research.md)

> 레시피는 [`knowledge/recipes/`](knowledge/recipes/), 회사 양식은 [`assets/`](assets/) 폴더에 있습니다.
> 각 폴더에는 그 자리에서 읽을 수 있는 `_README.md` 가 있습니다.

---

*이 도구는 오픈소스 [odysseus](https://github.com/pewdiepie-archdaemon/odysseus) 위에 AIM N팀 전용
"문서 생산 스튜디오" 모듈(`/studio`)을 얹은 것입니다. 원본 odysseus README 는
[docs/odysseus_원본_README.md](docs/odysseus_원본_README.md) 에 보관되어 있습니다.
LLM 호출은 API 키 없이 구글 공식 Antigravity CLI(`agy`)에 위임하며, 로그인한 Google 계정의
할당량으로 동작합니다. 로그인은 Google 계정으로 전환되었습니다.*
