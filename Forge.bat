@echo off
title Character Forge - launcher
cd /d "%~dp0"
if exist ".venv_forge\Scripts\python.exe" (
  ".venv_forge\Scripts\python.exe" "launch_forge.py"
) else (
  python "launch_forge.py"
)
echo.
echo (launcher closed)
pause
