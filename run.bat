@echo off
rem Starts Waypoints at http://127.0.0.1:8000
rem First run creates a Python environment in .venv and installs what's needed.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up Waypoints for the first time...
  python -m venv .venv || (echo Python wasn't found. Install Python 3.11+ from python.org, then run this again. & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || (echo Installing packages failed. & pause & exit /b 1)
)
if not exist ".env" copy ".env.example" ".env" >nul

echo Waypoints is running at http://127.0.0.1:8000  (close this window to stop it)
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
