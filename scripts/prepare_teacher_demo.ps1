param(
    [int]$PdfCount = 3,
    [switch]$IncludeExistingMarkdown
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$stageDir = Join-Path $distRoot "ubuntu24-teacher-demo"
$zipPath = Join-Path $distRoot "ubuntu24-teacher-demo.zip"

function Reset-Dir {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Copy-FileIfExists {
    param(
        [string]$Source,
        [string]$TargetDir
    )
    if (Test-Path $Source) {
        Copy-Item $Source -Destination $TargetDir -Force
    }
}

Reset-Dir $distRoot
Reset-Dir $stageDir

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
    "run_ocr_demo.sh"
)

foreach ($file in $scriptFiles) {
    Copy-FileIfExists -Source (Join-Path $root "scripts\$file") -TargetDir (Join-Path $stageDir "scripts")
}

Copy-FileIfExists -Source (Join-Path $root "docs\ubuntu24_teacher_demo.md") -TargetDir (Join-Path $stageDir "docs")

$pdfFiles = Get-ChildItem (Join-Path $root "test_pdfs") -File | Sort-Object Name | Select-Object -First $PdfCount
foreach ($pdf in $pdfFiles) {
    Copy-Item $pdf.FullName -Destination (Join-Path $stageDir "test_pdfs") -Force
}

Copy-FileIfExists -Source (Join-Path $root "results\summary.json") -TargetDir (Join-Path $stageDir "results_examples")
Copy-FileIfExists -Source (Join-Path $root "results\comparison_table.csv") -TargetDir (Join-Path $stageDir "results_examples")

if ($IncludeExistingMarkdown) {
    $mdTarget = Join-Path $stageDir "results_examples\markdown"
    New-Item -ItemType Directory -Path $mdTarget | Out-Null
    Get-ChildItem (Join-Path $root "results\markdown") -File | Sort-Object Name | Select-Object -First $PdfCount | ForEach-Object {
        Copy-Item $_.FullName -Destination $mdTarget -Force
    }
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Demo package prepared successfully." -ForegroundColor Green
Write-Host "Folder: $stageDir"
Write-Host "Zip:    $zipPath"
Write-Host ""
Write-Host "Included PDFs:" -ForegroundColor Cyan
$pdfFiles | ForEach-Object { Write-Host " - $($_.Name)" }
