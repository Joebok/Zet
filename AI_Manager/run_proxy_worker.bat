copy /y c:\Users\Joe\Projects\Zet\AI_Manager\*.py .

@echo off
cd /d "%~dp0"
set "ZET_PROJECT_ROOT=C:\Users\Joe\Projects\Zet"
set "PYTHONPATH=C:\Users\Joe\Projects\Zet;C:\Users\Joe\Projects\Zet\Scripts;%PYTHONPATH%"
python3 -B proxy_worker.py --proxy-root "C:\Users\Joe\Library\CloudStorage\Dropbox\AI_Queue\Ollama_Proxy"
