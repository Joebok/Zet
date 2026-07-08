<#
.SYNOPSIS
    Copies image files from a source directory to a destination while preserving their folder structure.

.DESCRIPTION
    Recursively copies image files from the source path to the destination path, preserving the relative
    directory structure beneath the source root.

.EXAMPLE
    .\Backup-Images.ps1 -Source "C:\Projects\ImageSet" -Dest "D:\Backups\ImageSet"
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

function Copy-ImageFiles {
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

    $allowedExtensions = @('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico')

    Get-ChildItem -LiteralPath $resolvedSourceRoot -File -Recurse | ForEach-Object {
        $extension = $_.Extension.ToLowerInvariant()
        if ($extension -notin $allowedExtensions) {
            return
        }

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

Copy-ImageFiles -SourceRoot $SourcePath -DestinationRoot $DestinationPath -Overwrite:$OverwriteFiles
