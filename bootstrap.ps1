[CmdletBinding()]
param(
    [switch]$SkipChecks = $false,
    [switch]$SkipPreCommit = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[bootstrap] $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Exe,
        [string[]]$Args
    )
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($Args -join ' ')"
    }
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Step "Project root: $ProjectRoot"

$HostPython = $null
$HostPythonArgs = @()

if (Get-Command python -ErrorAction SilentlyContinue) {
    $HostPython = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $HostPython = "py"
    $HostPythonArgs = @("-3")
} else {
    throw "Python 3.9+ was not found in PATH. Install Python and try again."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating virtual environment (.venv)"
    Invoke-Checked -Exe $HostPython -Args (@($HostPythonArgs) + @("-m", "venv", ".venv"))
} else {
    Write-Step "Virtual environment already exists"
}

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment was not created successfully: $VenvPython"
}

Write-Step "Upgrading pip"
Invoke-Checked -Exe $VenvPython -Args @("-m", "pip", "install", "--upgrade", "pip")

Write-Step "Installing project dependencies (editable + dev extras)"
Invoke-Checked -Exe $VenvPython -Args @("-m", "pip", "install", "-e", ".[dev]")

$templates = @(
    @{ Source = ".env.local.example"; Target = ".env.local" },
    @{ Source = "fish_intel_mvp/.env.example"; Target = "fish_intel_mvp/.env" }
)

foreach ($pair in $templates) {
    $src = Join-Path $ProjectRoot $pair.Source
    $dst = Join-Path $ProjectRoot $pair.Target

    if (-not (Test-Path $src)) {
        Write-Host "[bootstrap] Skip missing template: $($pair.Source)" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $dst) {
        Write-Host "[bootstrap] Keep existing file: $($pair.Target)" -ForegroundColor Yellow
        continue
    }

    Copy-Item -Path $src -Destination $dst
    Write-Step "Created $($pair.Target) from template"
}

if (-not $SkipPreCommit) {
    Write-Step "Installing pre-commit hooks"
    Invoke-Checked -Exe $VenvPython -Args @("-m", "pre_commit", "install")
} else {
    Write-Host "[bootstrap] Skip pre-commit install" -ForegroundColor Yellow
}

if (-not $SkipChecks) {
    Write-Step "Running ruff"
    Invoke-Checked -Exe $VenvPython -Args @("-m", "ruff", "check", ".")

    Write-Step "Running black --check"
    Invoke-Checked -Exe $VenvPython -Args @("-m", "black", "--check", ".")

    Write-Step "Running pytest"
    Invoke-Checked -Exe $VenvPython -Args @("-m", "pytest")
} else {
    Write-Host "[bootstrap] Skip lint/test checks" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Bootstrap completed successfully." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1) Review and edit .env.local and fish_intel_mvp/.env"
Write-Host "  2) Create a feature branch before coding"
Write-Host "  3) Push changes via PR and wait for CI"

