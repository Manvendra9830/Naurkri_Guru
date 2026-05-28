param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Naukri_Guru Windows setup"
$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$Version -lt [version]"3.10") {
    throw "Python 3.10+ is required. Found $Version"
}

if (!(Test-Path ".\venv\Scripts\python.exe")) {
    & $Python -m venv venv
}

.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe tools\validate_environment.py

Write-Host "Setup complete. Use .\venv\Scripts\python.exe runAiBot.py"
