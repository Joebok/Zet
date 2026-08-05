@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Zet virtual environment is missing. Run setup_venv.bat first.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b %errorlevel%
python -B -m zet.scripts.auto_harvest_ai_answers --config config.toml
