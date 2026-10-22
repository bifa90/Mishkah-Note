<#
.SYNOPSIS
    Build the Windows installer (MSI) for Notepad.

.DESCRIPTION
    Freezes the application with PyInstaller (onedir, windowed) and wraps the
    result with WiX Toolset v4/v5. The MSI installs into Program Files, creates
    Start-menu and desktop shortcuts, and registers an "Open with" entry for
    .txt files. Nothing is bundled that requires Python on the target machine.

    Run it on Windows (or a windows-latest GitHub runner):

        pwsh scripts/build-msi.ps1 -Version 1.0.01

    Prerequisites (installed by the script when missing):
        * Python 3.9+ with pip
        * .NET 6+ (for `dotnet tool install --global wix`)

.PARAMETER Version
    Product version written into the MSI; defaults to pyproject.toml.

.PARAMETER SkipFreeze
    Reuse build/pyinstaller if it already exists (useful while iterating on
    the WiX file alone).

.PARAMETER OutputDirectory
    Where the .msi lands; defaults to dist/.
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$SkipFreeze,
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Get-ProjectVersion {
    $line = Select-String -Path "pyproject.toml" -Pattern '^version = "([^"]+)"' |
        Select-Object -First 1
    if (-not $line) { throw "version not found in pyproject.toml" }
    return $line.Matches[0].Groups[1].Value
}

if (-not $Version) { $Version = Get-ProjectVersion }
Write-Step "Notepad $Version — Windows MSI"

# ---------------------------------------------------------------------------
# 1. tooling
# ---------------------------------------------------------------------------
Write-Step "checking the build tools"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python was not found on PATH; install Python 3.9+ first"
}

python -m pip install --upgrade --quiet pip
python -m pip install --quiet "pyinstaller>=6.6" "PySide6>=6.5" "charset-normalizer>=3.0" build

if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
        throw "dotnet was not found; install the .NET SDK to get the WiX CLI"
    }
    dotnet tool install --global wix
    $env:PATH = "$env:PATH;$env:USERPROFILE\.dotnet\tools"
}
wix --version
wix extension add --global WixToolset.UI.wixext

# ---------------------------------------------------------------------------
# 2. freeze the application
# ---------------------------------------------------------------------------
$PyInstallerDir = Join-Path $Root "build/pyinstaller"
$SourceDir = Join-Path $PyInstallerDir "notepad"

if ($SkipFreeze -and (Test-Path $SourceDir)) {
    Write-Step "reusing $SourceDir"
} else {
    Write-Step "freezing the application with PyInstaller"
    if (Test-Path $PyInstallerDir) { Remove-Item -Recurse -Force $PyInstallerDir }

    python -m PyInstaller `
        --noconfirm --clean --onedir `
        --distpath $PyInstallerDir `
        --workpath (Join-Path $PyInstallerDir "work") `
        "packaging/windows/notepad.spec"

    if (-not (Test-Path (Join-Path $SourceDir "Notepad.exe"))) {
        throw "PyInstaller did not produce Notepad.exe"
    }
}

# ---------------------------------------------------------------------------
# 3. licence page: WiX needs RTF
# ---------------------------------------------------------------------------
Write-Step "converting LICENSE to RTF"
$LicenseRtf = Join-Path $Root "build/windows/LICENSE.rtf"
New-Item -ItemType Directory -Force -Path (Split-Path $LicenseRtf) | Out-Null
$license = Get-Content -Raw "LICENSE"
$escaped = $license.Replace('\', '\\').Replace('{', '\{').Replace('}', '\}')
$escaped = $escaped.Replace("`r`n", " \par ").Replace("`n", " \par ")
@"
{\rtf1\ansi\deff0{\fonttbl{\f0\fswiss Segoe UI;}}
\fs20 $escaped
}
"@ | Set-Content -Encoding ASCII $LicenseRtf

# ---------------------------------------------------------------------------
# 4. the MSI itself
# ---------------------------------------------------------------------------
Write-Step "building the MSI"
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Msi = Join-Path $OutputDirectory "Notepad-$Version-x64.msi"

wix build "packaging/windows/notepad.wxs" `
    -d "SourceDir=$SourceDir" `
    -d "Version=$Version" `
    -d "LicenseRtf=$LicenseRtf" `
    -arch x64 `
    -ext WixToolset.UI.wixext `
    -o $Msi

if (-not (Test-Path $Msi)) { throw "wix did not produce an MSI" }
$size = [math]::Round((Get-Item $Msi).Length / 1MB, 2)
Write-Step "done: $Msi ($size MB)"
Write-Host "Verify with:  msiexec /i `"$Msi`" /qb  (then uninstall from Settings)"
