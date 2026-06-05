@echo off
REM ASCII-only on purpose: Korean text in a .bat breaks on CP949 consoles.
REM Keep the window open even when double-clicked, so output/errors stay visible.
if not defined _ODY_KEEPOPEN (
  set "_ODY_KEEPOPEN=1"
  cmd /k ""%~f0""
  exit /b
)
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [NOTE] Not installed yet. Please double-click setup.bat first.
  pause & exit /b 1
)

REM Self-heal: ensure embedded-terminal backend (pywinpty) exists (older venvs)
venv\Scripts\python -c "import winpty" 2>nul
if errorlevel 1 (
  echo [NOTE] Installing missing components pywinpty ... first time only.
  venv\Scripts\python -m pip install -r requirements.txt
)

where agy >nul 2>nul
if errorlevel 1 (
  echo [NOTE] agy ^(Antigravity CLI^) not found.
  echo        Run setup.bat again, or see docs\antigravity\install.md
  echo        You can also just open the agy terminal from the login page and install/sign in there.
)

echo ============================================================
echo   Odyssey Studio - running
echo   URL: http://127.0.0.1:7000   (sign in, then /studio)
echo   (Close this black window to stop. Stop: Ctrl+C)
echo ============================================================
echo.

REM Open the browser ~3s after start (give the server time to boot)
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:7000/"

venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port 7000

echo.
echo Server stopped.
pause
