[CmdletBinding()]
param(
    [ValidateSet('Deploy', 'Start', 'Stop')]
    [string]$Action = 'Deploy'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonPath = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Zet Python environment not found at '$pythonPath'. Run setup_venv.bat first."
}
& $pythonPath -c "import sys; assert sys.version_info.major == 3"
if ($LASTEXITCODE -ne 0) { throw 'Zet Test requires Python 3.' }

Push-Location $root
try {
    & $pythonPath -B -u -m zet.scripts.manage_test_release $Action
    exit $LASTEXITCODE
}
finally { Pop-Location }
