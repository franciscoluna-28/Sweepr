@echo off
cd /d "%~dp0"
if "%SWEEPR_PORT%"=="" set "SWEEPR_PORT=8765"
echo Starting API on http://127.0.0.1:%SWEEPR_PORT% ...
start "Sweepr API" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port %SWEEPR_PORT%"
echo Starting UI dev server (HMR) on http://127.0.0.1:5173 ...
start "Sweepr UI" cmd /k "pnpm --dir app/ui dev --open"
