<#
.SYNOPSIS
    Copies images, templates, and prompts from a source library to a destination.

.DESCRIPTION
    Recursively copies common image formats and Markdown/text templates and prompts, preserving
    their relative directory structure. SQLite databases, JSON metadata, and other file types are
    excluded. Only folders containing copied files are created. This is a limited Dropbox copy,
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

    # Templates and compiled prompts use Markdown or plain text; structured metadata is excluded.
    $criticalExtensions = @(
        '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif', '.svg',
        '.heic', '.heif', '.md', '.txt'
    )

    Get-ChildItem -LiteralPath $resolvedSourceRoot -Force -File -Recurse |
        Where-Object { $_.Extension -in $criticalExtensions } | ForEach-Object {
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
