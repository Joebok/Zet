@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The development Python 3 environment is missing. Run setup_venv.bat first.
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -c "import sys; assert sys.version_info.major == 3"
if errorlevel 1 exit /b %errorlevel%
"%~dp0.venv\Scripts\python.exe" -B -m zet.scripts.launch_runtime --runtime-root "%~dp0..\Zet_Runtime"
