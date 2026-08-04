@echo off
setlocal

set "ZET_ROOT=%~dp0"
set "FILE_PROXY_ROOT=C:\Users\Joe\Projects\AI_Proxy"

start "File Proxy" /D "%FILE_PROXY_ROOT%" cmd /k call run_file_proxy.bat
start "Zet Auto Harvest" /D "%ZET_ROOT%" cmd /k call run_auto_harvest.bat

echo Started File Proxy and Zet Auto Harvest.
