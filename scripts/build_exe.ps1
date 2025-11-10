# Build script for Windows PowerShell to create a standalone .exe for the PsychoPy task
# Usage:
#   pwsh -File scripts/build_exe.ps1
# Notes:
# - Run this inside the intended Python environment where PsychoPy is installed.
# - The script will install PyInstaller if it is missing.

param(
    [switch]$Console = $false,           # use --console to show a console window
    [switch]$OneFile = $false,           # use --onefile to package into a single exe
    [string]$Name = "RavenTask",       # output executable name
    [string]$Icon = "",                # optional .ico path
    [string]$CondaEnv = "psychopy-dev" # conda environment name
)

$ErrorActionPreference = 'Stop'

Write-Host "[Preflight] Using conda environment: $CondaEnv"
conda run -n $CondaEnv python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('psychopy') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Conda env '$CondaEnv' 未安装 psychopy，请先执行: conda activate $CondaEnv && pip install -r requirements.txt"
    exit 1
}

function Install-PackageIfMissing($pkg) {
    conda run -n $CondaEnv python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$pkg') else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $pkg into $CondaEnv ..."
        conda run -n $CondaEnv pip install $pkg
        if ($LASTEXITCODE -ne 0) { throw "Failed to install $pkg in $CondaEnv" }
    } else { Write-Host "$pkg already installed in $CondaEnv" }
}

Write-Host "Checking PyInstaller availability ..."
Install-PackageIfMissing -pkg "pyinstaller"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

# Paths
$entry = Join-Path $root "scripts/run_raven.py"
$dist = Join-Path $root "dist"
$build = Join-Path $root "build"

# Clean previous build artifacts (optional)
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
if (Test-Path $dist)  { Remove-Item $dist  -Recurse -Force }

# Compose PyInstaller args
$argList = @()
if ($Console) { $argList += "--console" } else { $argList += "--noconsole" }
if ($OneFile) { $argList += "--onefile" }
$argList += @("--clean", "--name", $Name)
if ($Icon) { $argList += @("--icon", $Icon) }

# Hidden imports commonly required by PsychoPy
$argList += @(
    "--hidden-import", "psychopy",
    "--hidden-import", "psychopy.visual",
    "--hidden-import", "psychopy.visual.line",
    "--hidden-import", "psychopy.event",
    "--hidden-import", "psychopy.core",
    "--hidden-import", "psychopy.gui",
    "--hidden-import", "psychopy.plugins",
    "--hidden-import", "psychopy.visual.backends.pygletbackend",
    "--hidden-import", "pyglet",
    "--hidden-import", "pyglet.gl",
    "--hidden-import", "pyglet.window",
    "--hidden-import", "pyglet.window.win32",
    "--hidden-import", "pyglet.canvas",
    "--hidden-import", "pyglet.graphics",
    "--hidden-import", "PIL"
)

# On Windows, --add-data uses source;dest (semicolon)
$datas = @(
    "configs;configs",
    "stimuli;stimuli"
)
foreach ($d in $datas) { $argList += @("--add-data", $d) }

# Collect submodules to cover lazy imports within PsychoPy
$argList += @(
    "--collect-submodules", "psychopy",
    "--collect-submodules", "psychopy.visual",
    "--collect-submodules", "psychopy.tools"
)

$argList += $entry

Write-Host "Running PyInstaller ..."
Write-Host "Running PyInstaller inside conda env '$CondaEnv' ..."
conda run -n $CondaEnv pyinstaller $argList

if ($LASTEXITCODE -eq 0) {
    Write-Host "\nBuild succeeded. Output is in: $dist"
    if ($OneFile) {
        Get-ChildItem (Join-Path $dist "$Name.exe") -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "Created: $($_.FullName)" }
    } else {
        Get-ChildItem (Join-Path $dist $Name) -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "Output folder: $($_.FullName)" }
    }
} else {
    Write-Error "Build failed with exit code $LASTEXITCODE"
}

Pop-Location
