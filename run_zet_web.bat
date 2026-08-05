@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Zet virtual environment is missing. Run setup_venv.bat first.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b %errorlevel%
for /f "usebackq tokens=*" %%p in (`powershell -NoProfile -Command "$listener = Get-NetTCPConnection -LocalAddress 0.0.0.0 -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue; if ($listener) { $listener.OwningProcess }"`) do set "ZET_WEB_PID=%%p"
if defined ZET_WEB_PID (
  echo Zet Web is already listening on http://0.0.0.0:8080/ with PID %ZET_WEB_PID%.
  echo Close that process before starting another instance.
  exit /b 0
)
python -B -m zet.web.app --config config.toml --host 0.0.0.0 --port 8080
