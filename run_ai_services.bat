@echo off
setlocal

set "ZET_ROOT=%~dp0"
set "OLLAMA_WORKER_ROOT=C:\Users\Joe\Ollama"

start "Zet Proxy Worker" /D "%OLLAMA_WORKER_ROOT%" cmd /k call run_proxy_worker.bat
start "Zet Auto Harvest" /D "%ZET_ROOT%" cmd /k call run_auto_harvest.bat
start "Zet Render Console" /D "%ZET_ROOT%" cmd /k call run_render_console.bat

echo Started Zet Proxy Worker, Zet Auto Harvest, and Zet Render Console.
