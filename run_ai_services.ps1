$ErrorActionPreference = "Stop"

$zetRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$fileProxyRoot = "C:\Users\Joe\Projects\AI_Proxy"

Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "call run_file_proxy.bat" -WorkingDirectory $fileProxyRoot
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "call run_auto_harvest.bat" -WorkingDirectory $zetRoot

Write-Host "Started File Proxy and Zet Auto Harvest."
