@echo off
rem Production launcher: builds the UI if needed, then starts the single
rem Python process (serves the UI + API) and opens the browser.
rem For development with hot reload, use run-dev.bat instead.
setlocal
cd /d "%~dp0"
if "%SWEEPR_PORT%"=="" set "SWEEPR_PORT=8765"

if not exist "app\ui\dist\index.html" (
  echo Building UI ...
  call pnpm --dir app/ui install || goto :error
  call pnpm --dir app/ui build || goto :error
)

echo Starting Sweepr on http://127.0.0.1:%SWEEPR_PORT% ...
".venv\Scripts\python.exe" start.py
goto :eof

:error
echo.
echo Setup failed. See README.md ("Setup") for prerequisites.
pause
exit /b 1
