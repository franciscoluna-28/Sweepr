@echo off
cd /d "%~dp0"
echo Starting host audio bridge (record mode) in a new window...
start "Meowless audio bridge" cmd /k ".venv\Scripts\python.exe audio_bridge.py"
echo Starting Docker stack...
docker compose up --build
pause
