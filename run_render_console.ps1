$ErrorActionPreference = "Stop"

$zetRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $zetRoot

python3 -B -m zet.render_console.app --config config.toml
