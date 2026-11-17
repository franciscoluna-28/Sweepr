<#
.SYNOPSIS
  Install and start Sweepr on Windows (x64).

.DESCRIPTION
  Downloads a pinned copy of uv (checksum verified) into
  %LOCALAPPDATA%\Sweepr\bootstrap, creates a Start Menu shortcut, and runs
  `uvx --from sweepr-app==<version> sweepr`. No admin rights, no installer,
  and no changes to PATH or the PowerShell execution policy.

  Run it with:
    irm https://github.com/franciscoluna-28/sweepr/releases/latest/download/install.ps1 | iex

  To pass options, download first:
    & ([scriptblock]::Create((irm <url>))) -NoShortcut

.PARAMETER Version
  Sweepr version to install (default: the version this script was released with).

.PARAMETER NoLaunch
  Install only; do not start Sweepr.

.PARAMETER NoShortcut
  Do not create a Start Menu shortcut.

.PARAMETER Uninstall
  Remove the shortcut and bootstrap files. Your jobs and the downloaded engine are kept.

.PARAMETER Purge
  With -Uninstall, also remove all Sweepr data (asks first).
#>
[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [switch]$NoLaunch,
    [switch]$NoShortcut,
    [switch]$Uninstall,
    [switch]$Purge
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Pinned uv release (checksums from the GitHub release digests).
$UvVersion = '0.13.8'
$UvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
$UvSha256 = '529e78a9cec6cd7e3e014f7ecd8bda0c113969d4ed0f2efeedb85c30943325b8'

$SweeprHome = Join-Path $env:LOCALAPPDATA 'Sweepr'
$Bootstrap = Join-Path $SweeprHome 'bootstrap'
$UvDir = Join-Path $Bootstrap 'uv'
$Uvx = Join-Path $UvDir 'uvx.exe'
$Launcher = Join-Path $Bootstrap 'Sweepr.cmd'
$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Sweepr.lnk'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Remove-Install {
    Write-Step 'Removing the Start Menu shortcut and bootstrap files'
    Remove-Item -LiteralPath $Shortcut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Bootstrap -Recurse -Force -ErrorAction SilentlyContinue
    if ($Purge -and (Test-Path -LiteralPath $SweeprHome)) {
        $answer = Read-Host "Delete all Sweepr data (jobs and the downloaded engine) in $SweeprHome? [y/N]"
        if ($answer -match '^(y|yes)$') {
            Remove-Item -LiteralPath $SweeprHome -Recurse -Force
            Write-Step 'Sweepr data removed'
        } else {
            Write-Step 'Data kept'
        }
    }
    Write-Step 'Sweepr uninstalled'
}

function Assert-Platform {
    if ($PSVersionTable.PSVersion.Major -lt 5) { throw 'PowerShell 5.1 or newer is required.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Sweepr needs 64-bit Windows.' }
    if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw "Windows on $($env:PROCESSOR_ARCHITECTURE) is not supported yet (x64 only)."
    }
}

function Install-Uv {
    if (Test-Path -LiteralPath $Uvx) { return }
    Write-Step "Downloading uv $UvVersion (checksum verified)"
    New-Item -ItemType Directory -Force -Path $UvDir | Out-Null
    $zip = Join-Path ([IO.Path]::GetTempPath()) "sweepr-uv-$UvVersion.zip"
    Invoke-WebRequest -Uri $UvUrl -OutFile $zip -UseBasicParsing
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
    if ($actual -ne $UvSha256) {
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        throw "uv checksum mismatch (expected $UvSha256, got $actual). Nothing was installed."
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $UvDir -Force
    Remove-Item -LiteralPath $zip -Force
    if (-not (Test-Path -LiteralPath $Uvx)) { throw "uv did not unpack to $UvDir" }
}

function Write-Launcher {
    $lines = @(
        '@echo off',
        ('"%LOCALAPPDATA%\Sweepr\bootstrap\uv\uvx.exe" --from sweepr-app==' + $Version + ' sweepr %*')
    )
    Set-Content -LiteralPath $Launcher -Value $lines -Encoding ASCII
}

function New-StartMenuShortcut {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Shortcut)
    $link.TargetPath = $env:ComSpec
    $link.Arguments = "/c `"$Launcher`""
    $link.WorkingDirectory = $env:USERPROFILE
    $link.Description = 'Sweepr: remove background noise from audio and video, locally'
    $link.Save()
    Write-Step 'Added Sweepr to the Start Menu'
}

function Install-Sweepr {
    if ($Uninstall) { Remove-Install; return }

    Assert-Platform
    Install-Uv
    Write-Launcher
    if (-not $NoShortcut) { New-StartMenuShortcut }

    if ($NoLaunch) {
        Write-Step "Installed. Start Sweepr from the Start Menu, or run: `"$Launcher`""
        return
    }

    Write-Step "Starting Sweepr $Version (the first run downloads the engine, about 100 MB)"
    Write-Host 'Keep this window open while you use Sweepr. Press Ctrl+C here to stop it.'
    & $Uvx --from "sweepr-app==$Version" sweepr
}

Install-Sweepr
