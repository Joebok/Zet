copy /y c:\Users\Joe\Projects\Zet\AI_Manager\*.py .

@echo off
cd /d "%~dp0"
python3 -B proxy_worker.py --proxy-root "C:\Users\Joe\Library\CloudStorage\Dropbox\AI_Queue\Ollama_Proxy"
