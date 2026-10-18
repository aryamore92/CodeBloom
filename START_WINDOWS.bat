@echo off
cd /d "%~dp0"
py -3 --version >nul 2>&1
if %errorlevel%==0 (
  py -3 server.py
) else (
  python --version >nul 2>&1
  if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer and add it to PATH.
    echo Then open this folder in VS Code and run: python server.py
  ) else (
    python server.py
  )
)
pause
