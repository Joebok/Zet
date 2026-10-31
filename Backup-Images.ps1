<#
.SYNOPSIS
    Copies images, templates, and prompts from a source library to a destination.

.DESCRIPTION
    Copies metadata-selected Inventory images and locked Final outputs, plus Markdown/text
    templates and prompts, preserving their relative directory structure. SQLite databases,
    JSON metadata, and other file types are excluded. Only folders containing copied files are created. This is a limited Dropbox copy,
    not a full library backup; existing destination files are not deleted.

.EXAMPLE
    .\Backup-Images.ps1 -Source "C:\Projects\Zet_Library" -Dest "D:\Backups\Zet_Library"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias('Source', 'Src')]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [Alias('Dest', 'Destination')]
    [string]$DestinationPath,

    [switch]$OverwriteFiles
)

$ErrorActionPreference = 'Stop'

function Copy-LibraryFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot,

        [switch]$Overwrite
    )

    $resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
    $resolvedDestinationRoot = $DestinationRoot

    if (-not (Test-Path -LiteralPath $resolvedDestinationRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $resolvedDestinationRoot -Force | Out-Null
    }

    $python = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    $pythonArgs = @()
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
        $pythonArgs = @('-3')
    }
    if (-not $python) { throw 'Python 3 is required to enumerate library image metadata.' }
    & $python.Source @pythonArgs -c 'import sys; assert sys.version_info.major == 3'
    if ($LASTEXITCODE -ne 0) { throw 'The selected command is not a working Python 3 interpreter.' }
    $manifestScript = Join-Path $PSScriptRoot 'zet/scripts/backup_image_manifest.py'
    $manifest = & $python.Source @pythonArgs -B $manifestScript $resolvedSourceRoot
    if ($LASTEXITCODE -ne 0) { throw 'Image metadata enumeration failed; no files were copied.' }
    $imagePaths = @(foreach ($item in (ConvertFrom-Json -InputObject ($manifest -join "`n"))) { [string]$item })
    $textPaths = @(Get-ChildItem -LiteralPath $resolvedSourceRoot -Force -File -Recurse |
        Where-Object { $_.Extension -in @('.md', '.txt') } | ForEach-Object { $_.FullName })

    @($imagePaths + $textPaths | Select-Object -Unique) | ForEach-Object {
        $filePath = $_
        $relativePath = $filePath.Substring($resolvedSourceRoot.Length).TrimStart('\', '/')
        $targetPath = Join-Path -Path $resolvedDestinationRoot -ChildPath $relativePath
        $targetDirectory = Split-Path -Parent $targetPath

        if (-not (Test-Path -LiteralPath $targetDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }

        Write-Host "[INFO] Copying $filePath -> $targetPath" -ForegroundColor Green

        if ($Overwrite) {
            Copy-Item -LiteralPath $filePath -Destination $targetPath -Force
        }
        else {
            Copy-Item -LiteralPath $filePath -Destination $targetPath -ErrorAction Stop
        }
    }
}

Copy-LibraryFiles -SourceRoot $SourcePath -DestinationRoot $DestinationPath -Overwrite:$OverwriteFiles
