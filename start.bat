@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [ERROR] Virtual environment not found.
  echo.
  echo Please run these two commands first:
  echo     python -m venv .venv
  echo     .venv\Scripts\pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo ============================================================
echo   AI Job Matcher  -  Resume / JD Match Analyzer
echo ============================================================
echo.
echo   URL  : http://127.0.0.1:5000
echo   Stop : press Ctrl + C in this window
echo ============================================================
echo.

start /b cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"

".venv\Scripts\python.exe" app.py

echo.
echo Service stopped.
pause
