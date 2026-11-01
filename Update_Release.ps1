<#
.SYNOPSIS
Validate and deploy the latest merged origin/main, then restart Zet and its harvester.
.DESCRIPTION
Uses the configured active production runtime and this checkout's deployment
controller. Requires a running managed Zet release. Does not commit or push changes.
.PARAMETER RuntimeRoot
Override Runtime.Root from the project's config.toml.
.PARAMETER StageOnly
Run release validation without stopping or promoting production.
.EXAMPLE
.\Update_Release.ps1
.EXAMPLE
.\Update_Release.ps1 -StageOnly
#>
[CmdletBinding()]
param(
    [string]$RuntimeRoot,
    [switch]$StageOnly
)

$ErrorActionPreference = "Stop"
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Zet Python environment not found at '$pythonPath'. Run setup_venv.bat first."
}
& $pythonPath -c "import sys; assert sys.version_info.major == 3"
if ($LASTEXITCODE -ne 0) {
    throw "The Zet environment must use Python 3."
}

$updateArguments = @("-B", "-u", "-m", "zet.scripts.update_release")
if ($RuntimeRoot) { $updateArguments += @("--runtime-root", $RuntimeRoot) }
if ($StageOnly) { $updateArguments += "--stage-only" }

Push-Location $PSScriptRoot
try {
    & $pythonPath @updateArguments
    $updateExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $updateExitCode
