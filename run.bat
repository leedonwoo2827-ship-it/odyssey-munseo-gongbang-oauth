@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [안내] 아직 설치되지 않았습니다. 먼저 setup.bat 을 더블클릭해 주세요.
  pause & exit /b 1
)

echo ============================================================
echo   문서 생산 스튜디오 실행
echo   주소: http://127.0.0.1:7000/studio
echo   (이 검은 창을 닫으면 종료됩니다. 중지: Ctrl+C)
echo ============================================================
echo.

REM 3초 뒤 브라우저 자동 오픈(서버 기동 대기)
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:7000/studio"

venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 7000

echo.
echo 서버가 종료되었습니다.
pause
