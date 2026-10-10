<#
.SYNOPSIS
    Copies all files from a source library to a destination while preserving its folder structure.

.DESCRIPTION
    Recursively copies the contents of the source path to the destination path, preserving the relative
    directory structure beneath the source root.

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

    Get-ChildItem -LiteralPath $resolvedSourceRoot -Force -Directory -Recurse | ForEach-Object {
        $relativePath = $_.FullName.Substring($resolvedSourceRoot.Length).TrimStart('\', '/')
        $targetPath = Join-Path -Path $resolvedDestinationRoot -ChildPath $relativePath
        if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        }
    }

    Get-ChildItem -LiteralPath $resolvedSourceRoot -Force -File -Recurse | ForEach-Object {
        $relativePath = $_.FullName.Substring($resolvedSourceRoot.Length).TrimStart('\', '/')
        $targetPath = Join-Path -Path $resolvedDestinationRoot -ChildPath $relativePath
        $targetDirectory = Split-Path -Parent $targetPath

        if (-not (Test-Path -LiteralPath $targetDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }

        Write-Host "[INFO] Copying $($_.FullName) -> $targetPath" -ForegroundColor Green

        if ($Overwrite) {
            Copy-Item -LiteralPath $_.FullName -Destination $targetPath -Force
        }
        else {
            Copy-Item -LiteralPath $_.FullName -Destination $targetPath -ErrorAction Stop
        }
    }
}

Copy-LibraryFiles -SourceRoot $SourcePath -DestinationRoot $DestinationPath -Overwrite:$OverwriteFiles
