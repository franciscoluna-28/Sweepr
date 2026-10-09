@echo off
cd /d "%~dp0"
if "%MEOWLESS_PORT%"=="" set "MEOWLESS_PORT=8765"
echo Starting API on http://127.0.0.1:%MEOWLESS_PORT% ...
start "Meowless API" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port %MEOWLESS_PORT%"
echo Starting UI dev server (HMR) on http://127.0.0.1:5173 ...
start "Meowless UI" cmd /k "pnpm --dir app/ui dev --open"
