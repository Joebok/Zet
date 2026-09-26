$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$configPath = Join-Path $projectRoot "config.toml"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Zet Python environment not found at '$pythonPath'. Run setup_venv.bat first."
}

Push-Location $projectRoot
try {
    & $pythonPath -B -m zet.scripts.archive_harvested_answers --config $configPath
    if ($LASTEXITCODE -ne 0) {
        throw "Archive process failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
