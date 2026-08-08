@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Install it from https://python.org and enable Add Python to PATH.
  pause
  exit /b 1
)
py -m pip install -e .
if errorlevel 1 (
  echo Installation failed.
  pause
  exit /b 1
)
browser-bookmark-tool --gui
