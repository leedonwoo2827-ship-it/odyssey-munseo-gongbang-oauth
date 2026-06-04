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
| 네트워크 | **사내망/VPN 연결 필수** (회사 liteLLM 프록시 접근) | |
| 브라우저 | Chrome / Edge 최신 | |
| 한글 산출물(.hwpx) 네이티브 생성 | (선택) **한컴 한글 2014+** 설치 + `pywin32` | 한글 미설치 시 자동으로 DOCX/Markdown 으로 대체 |

> 한컴 한글이 없어도 사용 가능합니다. 이때 `.hwpx` 대신 **DOCX**(한글에서 열어 .hwpx 저장 가능) 또는
> **Markdown** 으로 제공되며, `assets/hwpx_template.hwpx` 회사 양식이 있으면 한글 없이도 .hwpx 가 생성됩니다.

---

## 🚀 시작하기 (딱 2단계)

탐색기에서 더블클릭만 하면 됩니다.

1. **`setup.bat` 더블클릭** — 처음 한 번. (가상환경 + 라이브러리 설치, 몇 분 소요)
2. **`run.bat` 더블클릭** — 실행. 브라우저가 `http://127.0.0.1:7000/studio` 로 자동으로 열립니다.

종료하려면 검은 콘솔 창을 닫으면 됩니다.

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
- [06 · liteLLM 연결과 모델 선택](docs/studio/06_liteLLM_연결과_모델.md)
- [07 · 문제 해결 FAQ](docs/studio/07_문제해결_FAQ.md)

> 레시피는 [`knowledge/recipes/`](knowledge/recipes/), 회사 양식은 [`assets/`](assets/) 폴더에 있습니다.
> 각 폴더에는 그 자리에서 읽을 수 있는 `_README.md` 가 있습니다.

---

*이 도구는 오픈소스 [odysseus](https://github.com/pewdiepie-archdaemon/odysseus) 위에 AIM N팀 전용
"문서 생산 스튜디오" 모듈(`/studio`)을 얹은 것입니다. 원본 odysseus README 는
[docs/odysseus_원본_README.md](docs/odysseus_원본_README.md) 에 보관되어 있습니다.
모든 LLM 호출은 회사 방침에 따라 사내 liteLLM 프록시로 라우팅됩니다.*
