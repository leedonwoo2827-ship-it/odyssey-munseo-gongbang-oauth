@echo off
REM ASCII-only on purpose: Korean text in a .bat breaks on CP949 consoles.
REM Keep the window open even when double-clicked, so output/errors stay visible.
if not defined _ODY_KEEPOPEN (
  set "_ODY_KEEPOPEN=1"
  cmd /k ""%~f0""
  exit /b
)
cd /d "%~dp0"
set "LOG=%~dp0setup_log.txt"
echo setup start > "%LOG%"

echo ============================================================
echo   Odyssey Studio (AIM N-team) - SETUP
echo ============================================================
echo.

REM 1) Python (prefer the py launcher)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [ERROR] Python 3.11+ required.
  echo         Install from https://www.python.org/downloads/
  echo         Tick "Add Python to PATH" during install, then re-run.
  echo python-missing >> "%LOG%"
  goto end
)
echo [OK] Python: %PY%
echo step:python-ok >> "%LOG%"

REM 2) Virtual environment
if not exist "venv\Scripts\python.exe" (
  echo [1/3] Creating venv ...
  %PY% -m venv venv
) else (
  echo [1/3] venv already exists - skip
)
set "VPY=venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo [ERROR] venv creation failed. Reinstall Python and retry.
  echo venv-fail >> "%LOG%"
  goto end
)
echo step:venv-ok >> "%LOG%"

REM 3) Libraries
echo [2/3] Installing libraries ... (first time takes a few minutes)
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. See the red messages above.
  echo pip-fail >> "%LOG%"
  goto end
)
echo step:pip-ok >> "%LOG%"

REM    Embedded-terminal PTY backend (pywinpty) - install if missing
"%VPY%" -c "import winpty" 2>nul
if errorlevel 1 (
  echo       Installing embedded-terminal backend pywinpty ...
  "%VPY%" -m pip install pywinpty
)
"%VPY%" -c "import winpty" 2>nul
if errorlevel 1 (
  echo       [NOTE] pywinpty not installed - the in-page terminal will fall back to a real cmd window.
) else (
  echo       [OK] embedded-terminal backend ready
)
echo step:pywinpty-done >> "%LOG%"

REM 4) Antigravity CLI (agy) - best effort, isolated with cmd /c
echo [3/3] Checking Antigravity CLI (agy) ...
where agy >nul 2>nul
if errorlevel 1 (
  echo       agy not found - trying to install ^(needs internet^) ...
  curl -fsSL https://antigravity.google/cli/install.cmd -o "%TEMP%\agy_install.cmd"
  if exist "%TEMP%\agy_install.cmd" cmd /c "%TEMP%\agy_install.cmd"
  del "%TEMP%\agy_install.cmd" >nul 2>nul
)
where agy >nul 2>nul
if errorlevel 1 (
  echo       [NOTE] agy not installed yet - install later, see docs\antigravity\install.md
) else (
  echo       [OK] agy installed
)
echo step:agy-done >> "%LOG%"

REM 4b) OpenAI Codex CLI (optional, for OpenAI/ChatGPT provider) - best effort via npm
echo       Checking OpenAI Codex CLI (codex) ...
set "CODEX_NPM=%APPDATA%\npm\codex.cmd"
where codex >nul 2>nul
if errorlevel 1 (
  where npm >nul 2>nul
  if not errorlevel 1 (
    echo       codex not found on PATH - trying npm i -g @openai/codex ^(needs internet^) ...
    cmd /c npm i -g @openai/codex
  )
)
REM Detect codex on PATH first; if missing there, check the npm global bin
REM ^(the app uses the same fallback, so it can find codex even without PATH^).
set "CODEX_ON_PATH="
where codex >nul 2>nul && set "CODEX_ON_PATH=1"
if defined CODEX_ON_PATH (
  echo       [OK] codex installed ^(on PATH^)
) else (
  if exist "%CODEX_NPM%" (
    echo       [OK] codex installed at "%CODEX_NPM%"
    echo       [WARN] the npm global folder is NOT on your PATH:
    echo                %APPDATA%\npm
    echo              The app's [Login] button still works ^(it uses the full path^),
    echo              but a plain `codex` typed in a new cmd window will fail.
    echo              To fix permanently, add that folder to your PATH.
  ) else (
    echo       [NOTE] codex not installed - OpenAI provider optional, see docs\openai-codex\install.md
  )
)
echo step:codex-done >> "%LOG%"

REM 5) First-time setup - data dirs / DB (no prompt)
set "ODYSSEUS_SKIP_ADMIN_PROMPT=1"
"%VPY%" setup.py
echo step:setup-py-done >> "%LOG%"

echo.
echo ============================================================
echo   SETUP COMPLETE.  Next:  double-click run.bat
echo.
echo   Sign in once (pick a provider on screen: Gemini or OpenAI):
echo     - Gemini : open the login terminal and type   agy          (Google sign-in)
echo     - OpenAI : open the login terminal and run     codex login  (ChatGPT sign-in)
echo   Tip: on the page, use the provider toggle + [Login] button - it opens
echo        the right terminal for you. Then click [Refresh status].
echo   No API key needed (uses your account quota).
echo ============================================================

:end
echo.
echo --- If you can read this line, the script finished. (log: setup_log.txt) ---
echo setup end >> "%LOG%"
pause
