@echo off
cd /d "%~dp0"
for /f "usebackq tokens=*" %%p in (`powershell -NoProfile -Command "$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue; if ($listener) { $listener.OwningProcess }"`) do set "ZET_WEB_PID=%%p"
if defined ZET_WEB_PID (
  echo Zet Web is already listening on http://127.0.0.1:8080/ with PID %ZET_WEB_PID%.
  echo Close that process before starting another instance.
  exit /b 0
)
python3 -B -m zet.web.app --config config.toml --host 127.0.0.1 --port 8080
