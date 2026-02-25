[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Rollback,
    [string]$BackupFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Apply -and $Rollback) {
    throw "Use only one mode at a time: -Apply or -Rollback."
}

$script:RunPaths = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
)

$script:StartupPatterns = @(
    "onedrive",
    "atrust",
    "sysdiag",
    "huorong",
    "hipstray",
    "nvidia.*share",
    "shadowplay",
    "nvbackend"
)

$script:RegistryTweaks = @(
    @{ Path = "HKCU:\System\GameConfigStore"; Name = "GameDVR_Enabled"; Type = "DWord"; Value = 0 },
    @{ Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"; Name = "AppCaptureEnabled"; Type = "DWord"; Value = 0 },
    @{ Path = "HKCU:\Software\Microsoft\GameBar"; Name = "UseNexusForGameBarEnabled"; Type = "DWord"; Value = 0 }
)

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Write-Plan {
    param([string]$Message)
    Write-Host "[PLAN] $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[ OK ] $Message"
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host "[WARN] $Message"
}

function Test-IsAdmin {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-PowerSchemeGuid {
    param([string]$Guid)
    if (-not $Guid) { return $false }
    powercfg /query $Guid 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-ActivePowerSchemeGuid {
    $line = (powercfg /getactivescheme 2>$null | Select-Object -First 1)
    if (-not $line) { return $null }
    if ($line -match "([0-9a-fA-F-]{36})") { return $Matches[1].ToLowerInvariant() }
    return $null
}

function Get-HighPerformanceGuid {
    $lines = powercfg /list 2>$null
    foreach ($line in $lines) {
        if ($line -match "([0-9a-fA-F-]{36})") {
            $guid = $Matches[1].ToLowerInvariant()
            if ($line -match "High performance|Ultimate Performance|高性能|卓越性能") {
                return $guid
            }
        }
    }
    $builtinHighPerf = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    if (Test-PowerSchemeGuid -Guid $builtinHighPerf) {
        return $builtinHighPerf
    }
    return $null
}

function Get-StartupEntriesToDisable {
    $entries = New-Object System.Collections.Generic.List[object]
    foreach ($path in $script:RunPaths) {
        if (-not (Test-Path $path)) { continue }
        try {
            $item = Get-ItemProperty -Path $path -ErrorAction Stop
            foreach ($prop in $item.PSObject.Properties) {
                if ($prop.Name -in @("PSPath", "PSParentPath", "PSChildName", "PSDrive", "PSProvider")) {
                    continue
                }
                $name = [string]$prop.Name
                $value = [string]$prop.Value
                $text = "$name $value".ToLowerInvariant()
                $matched = $false
                foreach ($pattern in $script:StartupPatterns) {
                    if ($text -match $pattern) {
                        $matched = $true
                        break
                    }
                }
                if ($matched) {
                    $entries.Add([pscustomobject]@{
                            Path  = $path
                            Name  = $name
                            Value = $value
                        })
                }
            }
        }
        catch {
            Write-WarnLine ("Cannot read startup path {0}: {1}" -f $path, $_.Exception.Message)
        }
    }
    return $entries
}

function Get-RegistryValueSnapshot {
    param(
        [string]$Path,
        [string]$Name
    )
    $snapshot = [ordered]@{
        Path   = $Path
        Name   = $Name
        Exists = $false
        Type   = $null
        Value  = $null
    }

    if (-not (Test-Path $Path)) {
        return [pscustomobject]$snapshot
    }

    try {
        $item = Get-ItemProperty -Path $Path -Name $Name -ErrorAction Stop
        $snapshot.Exists = $true
        $snapshot.Value = $item.$Name
        $snapshot.Type = (Get-Item -Path $Path).GetValueKind($Name).ToString()
    }
    catch {
        $snapshot.Exists = $false
    }

    return [pscustomobject]$snapshot
}

function Set-RegistryDword {
    param(
        [string]$Path,
        [string]$Name,
        [int]$Value
    )
    if (-not (Test-Path $Path)) {
        New-Item -Path $Path -Force | Out-Null
    }
    New-ItemProperty -Path $Path -Name $Name -PropertyType DWord -Value $Value -Force | Out-Null
}

function Restore-RegistryValue {
    param([psobject]$Entry)
    $path = [string]$Entry.Path
    $name = [string]$Entry.Name
    $exists = [bool]$Entry.Exists

    if ($exists) {
        if (-not (Test-Path $path)) {
            New-Item -Path $path -Force | Out-Null
        }
        $type = if ($Entry.Type) { [string]$Entry.Type } else { "String" }
        New-ItemProperty -Path $path -Name $name -PropertyType $type -Value $Entry.Value -Force | Out-Null
    }
    else {
        if (Test-Path $path) {
            Remove-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-BackupFile {
    param(
        [string]$Candidate,
        [switch]$ForRollback
    )
    if ($Candidate) { return $Candidate }

    if ($ForRollback) {
        $latest = Get-ChildItem -Path $PSScriptRoot -Filter "windows_optimize_backup_*.json" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $latest) {
            throw "No backup file found under $PSScriptRoot."
        }
        return $latest.FullName
    }

    return (Join-Path $PSScriptRoot ("windows_optimize_backup_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss")))
}

if ($Rollback) {
    $resolvedBackup = Resolve-BackupFile -Candidate $BackupFile -ForRollback
    Write-Info "Rollback mode. Backup file: $resolvedBackup"
    $backup = Get-Content -Raw -Path $resolvedBackup | ConvertFrom-Json

    if ($backup.Original.PowerSchemeGuid) {
        try {
            powercfg /setactive $backup.Original.PowerSchemeGuid | Out-Null
            Write-Ok "Power scheme restored to $($backup.Original.PowerSchemeGuid)"
        }
        catch {
            Write-WarnLine ("Failed to restore power scheme: {0}" -f $_.Exception.Message)
        }
    }

    foreach ($entry in $backup.Original.RegistryTweaks) {
        try {
            Restore-RegistryValue -Entry $entry
            Write-Ok ("Registry restored: {0}\{1}" -f $entry.Path, $entry.Name)
        }
        catch {
            Write-WarnLine ("Failed to restore registry value {0}\{1}: {2}" -f $entry.Path, $entry.Name, $_.Exception.Message)
        }
    }

    foreach ($startupEntry in $backup.Original.StartupEntries) {
        if (($startupEntry.Path -like "HKLM:*") -and (-not (Test-IsAdmin))) {
            Write-WarnLine ("Skipped restoring startup entry {0} because admin permission is required." -f $startupEntry.Name)
            continue
        }
        try {
            if (-not (Test-Path $startupEntry.Path)) {
                New-Item -Path $startupEntry.Path -Force | Out-Null
            }
            New-ItemProperty -Path $startupEntry.Path -Name $startupEntry.Name -PropertyType String -Value $startupEntry.Value -Force | Out-Null
            Write-Ok ("Startup entry restored: {0} ({1})" -f $startupEntry.Name, $startupEntry.Path)
        }
        catch {
            Write-WarnLine ("Failed to restore startup entry {0}: {1}" -f $startupEntry.Name, $_.Exception.Message)
        }
    }

    Write-Info "Rollback completed."
    return
}

$activeGuid = Get-ActivePowerSchemeGuid
$highPerfGuid = Get-HighPerformanceGuid
$startupEntries = Get-StartupEntriesToDisable
$isAdmin = Test-IsAdmin
$regSnapshots = @()
foreach ($t in $script:RegistryTweaks) {
    $regSnapshots += Get-RegistryValueSnapshot -Path $t.Path -Name $t.Name
}

if (-not $Apply) {
    Write-Info "Preview mode (no changes)."

    if ($highPerfGuid -and $activeGuid -and $activeGuid -ne $highPerfGuid) {
        Write-Plan "Switch active power plan to High Performance: $highPerfGuid"
    }
    else {
        Write-Plan "Power plan change not needed or High Performance plan not found."
    }

    foreach ($snap in $regSnapshots) {
        $current = if ($snap.Exists) { "$($snap.Value)" } else { "<not-set>" }
        Write-Plan ("Set registry {0}\{1} => 0 (current: {2})" -f $snap.Path, $snap.Name, $current)
    }

    if ($startupEntries.Count -eq 0) {
        Write-Plan "No matched startup items to disable."
    }
    else {
        foreach ($entry in $startupEntries) {
            if (($entry.Path -like "HKLM:*") -and (-not $isAdmin)) {
                Write-Plan ("Skip startup entry (admin required): {0} ({1})" -f $entry.Name, $entry.Path)
            }
            else {
                Write-Plan ("Disable startup entry: {0} ({1})" -f $entry.Name, $entry.Path)
            }
        }
    }

    Write-Info "Run with -Apply to execute. Example: .\windows_optimize.ps1 -Apply"
    Write-Info "After apply, rollback with: .\windows_optimize.ps1 -Rollback -BackupFile <path>"
    return
}

$resolvedBackup = Resolve-BackupFile -Candidate $BackupFile
$backupObject = [ordered]@{
    CreatedAt = (Get-Date).ToString("s")
    Computer  = $env:COMPUTERNAME
    Original  = [ordered]@{
        PowerSchemeGuid = $activeGuid
        RegistryTweaks  = $regSnapshots
        StartupEntries  = $startupEntries
    }
}

$backupDir = Split-Path -Parent $resolvedBackup
if (-not (Test-Path $backupDir)) {
    New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
}
$backupObject | ConvertTo-Json -Depth 8 | Set-Content -Path $resolvedBackup -Encoding UTF8
Write-Info "Backup saved: $resolvedBackup"

if ($highPerfGuid -and $activeGuid -and $activeGuid -ne $highPerfGuid) {
    try {
        powercfg /setactive $highPerfGuid | Out-Null
        Write-Ok "Power plan switched to High Performance ($highPerfGuid)"
    }
    catch {
        Write-WarnLine ("Failed to switch power plan: {0}" -f $_.Exception.Message)
    }
}
else {
    Write-Info "Power plan unchanged."
}

foreach ($t in $script:RegistryTweaks) {
    try {
        Set-RegistryDword -Path $t.Path -Name $t.Name -Value $t.Value
        Write-Ok ("Registry set: {0}\{1} = {2}" -f $t.Path, $t.Name, $t.Value)
    }
    catch {
        Write-WarnLine ("Failed to set registry {0}\{1}: {2}" -f $t.Path, $t.Name, $_.Exception.Message)
    }
}

if ($startupEntries.Count -eq 0) {
    Write-Info "No matched startup entries found."
}
else {
    foreach ($entry in $startupEntries) {
        if (($entry.Path -like "HKLM:*") -and (-not $isAdmin)) {
            Write-WarnLine ("Skipped startup entry {0} because admin permission is required." -f $entry.Name)
            continue
        }
        try {
            Remove-ItemProperty -Path $entry.Path -Name $entry.Name -ErrorAction Stop
            Write-Ok ("Startup entry disabled: {0} ({1})" -f $entry.Name, $entry.Path)
        }
        catch {
            Write-WarnLine ("Failed to disable startup entry {0}: {1}" -f $entry.Name, $_.Exception.Message)
        }
    }
}

Write-Info "Optimization apply completed."
Write-Info ("Rollback command: .\windows_optimize.ps1 -Rollback -BackupFile `"{0}`"" -f $resolvedBackup)
