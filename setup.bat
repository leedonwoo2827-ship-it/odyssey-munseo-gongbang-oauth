@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   문서 생산 스튜디오 (AIM N팀) - 설치 setup
echo ============================================================
echo.

REM 1) Python 3.11+ 확인 (py 런처 우선)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [오류] Python 3.11 이상이 필요합니다.
  echo        https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.
  echo        설치 시 "Add Python to PATH" 체크를 꼭 해주세요.
  pause & exit /b 1
)
echo [확인] Python 사용: %PY%

REM 2) 가상환경 생성
if not exist "venv\Scripts\python.exe" (
  echo [1/3] 가상환경 venv 생성 중...
  %PY% -m venv venv
  if errorlevel 1 ( echo [오류] 가상환경 생성 실패 & pause & exit /b 1 )
) else (
  echo [1/3] 가상환경 이미 있음 - 건너뜀
)
set "VPY=venv\Scripts\python.exe"

REM 3) 라이브러리 설치
echo [2/4] 라이브러리 설치 중... 처음엔 몇 분 걸립니다
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [오류] 라이브러리 설치 실패. 위 빨간 메시지를 확인하세요.
  pause & exit /b 1
)
REM    내장 터미널 PTY 백엔드(pywinpty) 확인 — 없으면 명시 설치
"%VPY%" -c "import winpty" 2>nul
if errorlevel 1 (
  echo       내장 터미널 구성요소(pywinpty) 설치 중...
  "%VPY%" -m pip install pywinpty
)
"%VPY%" -c "import winpty" 2>nul && echo       [확인] 내장 터미널 구성요소 OK || echo       [경고] pywinpty 설치 실패 - 내장 터미널 대신 cmd 에서 agy 직접 실행하세요

REM 4) Antigravity CLI(agy) 설치 - LLM 호출 백엔드(키 불필요)
echo [3/4] Antigravity CLI(agy) 설치 확인...
where agy >nul 2>nul
if errorlevel 1 (
  echo       agy 가 없어 설치를 시도합니다 ^(인터넷 필요^)...
  curl -fsSL https://antigravity.google/cli/install.cmd -o "%TEMP%\agy_install.cmd" && call "%TEMP%\agy_install.cmd" & del "%TEMP%\agy_install.cmd" 2>nul
  where agy >nul 2>nul
  if errorlevel 1 (
    echo       [안내] agy 자동설치 실패. docs\antigravity\install.md 참고해 수동 설치하세요.
  ) else (
    echo       [확인] agy 설치됨
  )
) else (
  echo       [확인] agy 이미 설치됨
)

REM 5) 최초 설정 - 데이터 폴더 / DB 초기화 (프롬프트 없이)
echo [4/4] 최초 설정 - 데이터 폴더/DB 초기화...
set "ODYSSEUS_SKIP_ADMIN_PROMPT=1"
"%VPY%" setup.py

echo.
echo ============================================================
echo   설치 완료!  남은 건 'Google 로그인 최초 1회' 뿐입니다.
echo.
echo   아래 중 편한 방법으로 Google 로그인(브라우저에서 계정 선택):
echo     (A) run.bat 실행 후, 화면의 'agy 터미널 열기' 에서  agy  입력
echo     (B) 또는 이 창에 직접:   agy
echo.
echo   그다음 run.bat 더블클릭 -^> 브라우저에서 'Google로 로그인'.
echo   * API 키 입력 없음(Google 계정 할당량 사용).
echo   * 문서를 많이 뽑으려면 Google AI Pro/Ultra 계정 로그인 권장.
echo ============================================================
pause
