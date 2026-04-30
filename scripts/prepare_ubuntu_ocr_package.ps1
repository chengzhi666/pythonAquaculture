param(
    [int]$PdfCount = 3,
    [switch]$IncludeExistingMarkdown,
    [string]$PackageName = "ubuntu-ocr-teacher-demo"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$stageDir = Join-Path $distRoot $PackageName
$zipPath = Join-Path $distRoot "$PackageName.zip"

function Reset-Dir {
    param(
        [string]$Path,
        [string]$AllowedParent
    )

    $parentFull = [System.IO.Path]::GetFullPath($AllowedParent)
    $targetFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $targetFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset path outside allowed parent: $targetFull"
    }

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Copy-FileIfExists {
    param(
        [string]$Source,
        [string]$TargetDir
    )
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $TargetDir -Force
    }
}

New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
Reset-Dir -Path $stageDir -AllowedParent $distRoot

$dirsToCreate = @(
    "scripts",
    "docs",
    "test_pdfs",
    "results_examples"
)

foreach ($dir in $dirsToCreate) {
    New-Item -ItemType Directory -Path (Join-Path $stageDir $dir) | Out-Null
}

$rootFiles = @(
    "mineru_parser.py",
    "run_mineru_comparison.py",
    "requirements-ocr.txt"
)

foreach ($file in $rootFiles) {
    Copy-FileIfExists -Source (Join-Path $root $file) -TargetDir $stageDir
}

$scriptFiles = @(
    "setup_ubuntu24_ocr.sh",
    "run_ocr_demo.sh",
    "download_mineru_models.py"
)

foreach ($file in $scriptFiles) {
    Copy-FileIfExists -Source (Join-Path $root "scripts\$file") -TargetDir (Join-Path $stageDir "scripts")
}

$docFiles = @(
    "ubuntu_ocr_deployment_guide.md",
    "ubuntu_ocr_wsl_verification.md",
    "ubuntu24_teacher_demo.md"
)

foreach ($file in $docFiles) {
    Copy-FileIfExists -Source (Join-Path $root "docs\$file") -TargetDir (Join-Path $stageDir "docs")
}

$pdfFiles = Get-ChildItem (Join-Path $root "test_pdfs") -File | Sort-Object Name | Select-Object -First $PdfCount
$pdfIndex = 1
foreach ($pdf in $pdfFiles) {
    $targetName = "sample_{0:D2}.pdf" -f $pdfIndex
    Copy-Item -LiteralPath $pdf.FullName -Destination (Join-Path $stageDir "test_pdfs\$targetName") -Force
    $pdfIndex += 1
}

Copy-FileIfExists -Source (Join-Path $root "results\summary.json") -TargetDir (Join-Path $stageDir "results_examples")
Copy-FileIfExists -Source (Join-Path $root "results\comparison_table.csv") -TargetDir (Join-Path $stageDir "results_examples")

if ($IncludeExistingMarkdown) {
    $mdTarget = Join-Path $stageDir "results_examples\markdown"
    New-Item -ItemType Directory -Path $mdTarget | Out-Null
    $mdIndex = 1
    Get-ChildItem (Join-Path $root "results\markdown") -File | Sort-Object Name | Select-Object -First $PdfCount | ForEach-Object {
        $targetName = "example_{0:D2}.md" -f $mdIndex
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $mdTarget $targetName) -Force
        $mdIndex += 1
    }
}

$pythonCandidates = @(
    (Join-Path $root ".venv\Scripts\python.exe"),
    (Join-Path $root ".venv311\Scripts\python.exe"),
    "py",
    "python"
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    try {
        if ($candidate -like "*\python.exe") {
            if (-not (Test-Path -LiteralPath $candidate)) {
                continue
            }
            & $candidate --version *> $null
        } else {
            & $candidate --version *> $null
        }
        $pythonExe = $candidate
        break
    } catch {
        continue
    }
}

if (-not $pythonExe) {
    throw "Could not find Python to create Linux-friendly zip."
}

& $pythonExe (Join-Path $root "scripts\create_linux_friendly_zip.py") $stageDir $zipPath | Out-Null

Write-Host ""
Write-Host "Ubuntu OCR package prepared successfully." -ForegroundColor Green
Write-Host "Folder: $stageDir"
Write-Host "Zip:    $zipPath"
Write-Host ""
Write-Host "Included PDFs:" -ForegroundColor Cyan
$pdfFiles | ForEach-Object { Write-Host " - $($_.Name)" }
