# VS Code Setup Script for pythonAquaculture Project
# This script automates the setup of the VS Code development environment

param(
    [switch]$InstallExtensions = $false,
    [switch]$SetupVenv = $false,
    [switch]$All = $false
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = $scriptPath

Write-Host "===========================================" -ForegroundColor Green
Write-Host "VS Code Setup for pythonAquaculture" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""

# Recommended VS Code Extensions
$extensions = @(
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.debugpy",
    "ms-python.black-formatter",
    "charliermarsh.ruff",
    "ms-toolsai.jupyter",
    "qwtel.sqlite-viewer"
)

# Install VS Code Extensions
function Install-Extensions {
    Write-Host "Installing VS Code extensions..." -ForegroundColor Cyan

    if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
        Write-Host "VS Code CLI not found. Please install VS Code and add it to PATH." -ForegroundColor Red
        return $false
    }

    foreach ($ext in $extensions) {
        Write-Host "Installing $ext..."
        code --install-extension $ext
    }

    Write-Host "Extensions installed successfully!" -ForegroundColor Green
    return $true
}

# Setup Virtual Environment
function Setup-VirtualEnvironment {
    Write-Host "Setting up virtual environment..." -ForegroundColor Cyan

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Python not found. Please install Python and add it to PATH." -ForegroundColor Red
        return $false
    }

    $venvPath = Join-Path $projectRoot ".venv"

    if (Test-Path $venvPath) {
        Write-Host "Virtual environment already exists at $venvPath" -ForegroundColor Yellow
    } else {
        Write-Host "Creating virtual environment..."
        python -m venv $venvPath
        Write-Host "Virtual environment created at $venvPath" -ForegroundColor Green
    }

    # Activate virtual environment
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Host "Activating virtual environment..."
        & $activateScript
    }

    # Install dependencies
    $pyprojectPath = Join-Path $projectRoot "pyproject.toml"
    $requirementsPath = Join-Path $projectRoot "fish_intel_mvp" "requirements.txt"

    if (Test-Path $requirementsPath) {
        Write-Host "Installing requirements from requirements.txt..."
        pip install -r $requirementsPath
        Write-Host "Dependencies installed!" -ForegroundColor Green
    } elseif (Test-Path $pyprojectPath) {
        Write-Host "Installing dependencies from pyproject.toml..."
        pip install -e .
        Write-Host "Dependencies installed!" -ForegroundColor Green
    }

    return $true
}

# Configure Pip Mirror
function Set-PipMirror {
    Write-Host "Configuring pip to use Tsinghua University mirror..." -ForegroundColor Cyan

    $pipConfigPath = Join-Path $env:APPDATA "pip\pip.ini"
    $pipConfigDir = Split-Path $pipConfigPath -Parent

    if (-not (Test-Path $pipConfigDir)) {
        New-Item -ItemType Directory -Force -Path $pipConfigDir | Out-Null
    }

    $pipConfigContent = @"
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
[install]
trusted-host = pypi.tuna.tsinghua.edu.cn
"@

    Set-Content -Path $pipConfigPath -Value $pipConfigContent
    Write-Host "Pip mirror set to Tsinghua University!" -ForegroundColor Green
}

# Print configuration summary
function Print-Summary {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Green
    Write-Host "Configuration Complete!" -ForegroundColor Green
    Write-Host "===========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "VS Code Configuration Files:" -ForegroundColor Cyan
    Write-Host "  • .vscode/settings.json - Python environment and formatting settings"
    Write-Host "  • .vscode/launch.json - Debug configurations"
    Write-Host "  • .vscode/tasks.json - Build and run tasks"
    Write-Host "  • .vscode/extensions.json - Recommended extensions"
    Write-Host ""
    Write-Host "Quick Actions:" -ForegroundColor Cyan
    Write-Host "  • Press F5 to start debugging"
    Write-Host "  • Press F11 to run Streamlit app"
    Write-Host "  • Press Ctrl+Shift+B to run build tasks"
    Write-Host "  • Press Ctrl+Shift+D to open debug view"
    Write-Host ""
    Write-Host "Installed Extensions:" -ForegroundColor Cyan
    foreach ($ext in $extensions) {
        Write-Host "  • $ext"
    }
    Write-Host ""
    Write-Host "Virtual Environment Location:" -ForegroundColor Cyan
    Write-Host "  $projectRoot\.venv"
    Write-Host ""
}

# Main execution
Write-Host "Choose setup options:" -ForegroundColor Yellow
Write-Host "  1. Install extensions only"
Write-Host "  2. Setup virtual environment only"
Write-Host "  3. Do all setup"
Write-Host "  4. Skip setup"
Write-Host ""

if ($All) {
    Write-Host "Running complete setup..." -ForegroundColor Green
    Set-PipMirror | Out-Null
    Install-Extensions | Out-Null
    Setup-VirtualEnvironment | Out-Null
} elseif ($InstallExtensions -and -not $SetupVenv) {
    Install-Extensions | Out-Null
} elseif ($SetupVenv -and -not $InstallExtensions) {
    Setup-VirtualEnvironment | Out-Null
} else {
    $choice = Read-Host "Enter your choice (1-4)"

    switch ($choice) {
        "1" { Install-Extensions | Out-Null }
        "2" { Setup-VirtualEnvironment | Out-Null }
        "3" {
            Set-PipMirror | Out-Null
            Install-Extensions | Out-Null
            Setup-VirtualEnvironment | Out-Null
        }
        "4" { Write-Host "Skipping setup..." }
        default { Write-Host "Invalid choice. Skipping setup..." }
    }
}

Print-Summary

Write-Host "Setup completed! Open the project in VS Code to continue." -ForegroundColor Green
