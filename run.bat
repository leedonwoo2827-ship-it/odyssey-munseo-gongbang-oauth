@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [안내] 아직 설치되지 않았습니다. 먼저 setup.bat 을 더블클릭해 주세요.
  pause & exit /b 1
)

REM 필수 구성요소(내장 터미널 PTY 백엔드) 자동 점검 — 구버전 venv 자동 보강
venv\Scripts\python -c "import winpty" 2>nul
if errorlevel 1 (
  echo [안내] 내장 터미널 구성요소(pywinpty)가 없어 설치합니다... 최초 1회, 잠시 걸립니다.
  venv\Scripts\python -m pip install -r requirements.txt
)

REM Antigravity CLI(agy) 설치 확인 — 없으면 안내(설치/로그인은 한 번만)
where agy >nul 2>nul
if errorlevel 1 (
  echo [안내] agy(Antigravity CLI)가 없습니다. setup.bat 을 다시 실행하거나
  echo        docs\antigravity\install.md 를 참고해 설치 후 `agy` 로 Google 로그인하세요.
)

echo ============================================================
echo   문서 생산 스튜디오 실행
echo   주소: http://127.0.0.1:7000   (로그인 후 /studio)
echo   (이 검은 창을 닫으면 종료됩니다. 중지: Ctrl+C)
echo ============================================================
echo.

REM 3초 뒤 브라우저 자동 오픈(서버 기동 대기)
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:7000/"

venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port 7000

echo.
echo 서버가 종료되었습니다.
pause
