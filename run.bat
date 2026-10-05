@echo off
cd /d "%~dp0"
if not exist "app\ui\dist\index.html" (
  echo Building UI...
  call pnpm --dir app/ui build
)
".venv\Scripts\python.exe" start.py
pause
