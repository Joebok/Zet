$ErrorActionPreference = "Stop"

$zetRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ollamaWorkerRoot = "C:\Users\Joe\Ollama"

Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "call run_proxy_worker.bat" -WorkingDirectory $ollamaWorkerRoot
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "call run_auto_harvest.bat" -WorkingDirectory $zetRoot

Write-Host "Started Zet Proxy Worker and Zet Auto Harvest."
