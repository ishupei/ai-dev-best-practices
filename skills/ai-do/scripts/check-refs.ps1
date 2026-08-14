# ============================================================
# ai-do section reference checker for Windows.
# Usage:
#   .\check-refs.ps1
#   .\check-refs.ps1 -Text "checklist text"
#   .\check-refs.ps1 -File .\checklist.txt
#   .\check-refs.ps1 -StandardsPath .\references\core-standards.md
# Exit code: 0 = pass; 1 = missing or dangling refs.
# Keep this file ASCII-only for Windows PowerShell 5.1.
# ============================================================

param(
    [string]$Text,
    [string]$File,
    [string]$SkillPath = "",
    [string]$StandardsPath = ""
)

$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent $PSScriptRoot
if (-not $SkillPath) { $SkillPath = Join-Path $SkillRoot "SKILL.md" }
if (-not $StandardsPath) { $StandardsPath = Join-Path $SkillRoot "references" }

function Log-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }
function Log-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }

function Get-StandardFiles($path) {
    if (-not (Test-Path $path)) {
        Log-Err "Standards path does not exist: $path"
        exit 1
    }
    $item = Get-Item $path
    if ($item.PSIsContainer) {
        return @(Get-ChildItem -Path $path -Filter "*.md" | Where-Object { -not $_.PSIsContainer } | Sort-Object Name)
    }
    return @($item)
}

$standardFiles = Get-StandardFiles $StandardsPath
$defined = @{}
foreach ($sf in $standardFiles) {
    $standardsText = Get-Content -Raw -Encoding UTF8 -Path $sf.FullName
    foreach ($m in [regex]::Matches($standardsText, '(?m)^##\s+(\d+(?:\.\d+)*)')) {
        $defined[$m.Groups[1].Value] = $sf.FullName
    }
    foreach ($m in [regex]::Matches($standardsText, '(?m)^-\s+(\d+(?:\.\d+)*)\s')) {
        $defined[$m.Groups[1].Value] = $sf.FullName
    }
}
if ($defined.Keys.Count -eq 0) {
    Log-Err "No section ids parsed from: $StandardsPath"
    exit 1
}
Log-Info "Parsed $($standardFiles.Count) standard file(s), $($defined.Keys.Count) section id(s)"

if ($Text) {
    $target = $Text
    $sourceDesc = "inline text"
} elseif ($File) {
    if (-not (Test-Path $File)) { Log-Err "File does not exist: $File"; exit 1 }
    $target = Get-Content -Raw -Encoding UTF8 -Path $File
    $sourceDesc = $File
} else {
    if (-not (Test-Path $SkillPath)) { Log-Err "SKILL.md does not exist: $SkillPath"; exit 1 }
    $target = Get-Content -Raw -Encoding UTF8 -Path $SkillPath
    $sourceDesc = $SkillPath
}

$sectionMark = [string][char]0x00A7
$refPattern = [regex]::Escape($sectionMark) + '\s*([0-9][0-9.\s/]*)'
$refs = @()
foreach ($m in [regex]::Matches($target, $refPattern)) {
    $token = $m.Groups[1].Value.Trim()
    foreach ($part in ($token -split '[\s/]+')) {
        if ($part -match '^\d+(\.\d+)*$') { $refs += $part }
    }
}
$refs = @($refs | Sort-Object -Unique)
Log-Info "Source: $sourceDesc"
Log-Info "Found $($refs.Count) ref(s): $($refs -join ', ')"

if ($refs.Count -eq 0) {
    if ($Text -or $File) {
        Log-Err "No section refs found. A checklist must include section ids."
        exit 1
    }
    Log-Warn "No section refs found in SKILL.md"
    exit 0
}

$good = @()
$bad = @()
foreach ($r in $refs) {
    $valid = $defined.ContainsKey($r)
    if (-not $valid) {
        foreach ($k in $defined.Keys) {
            if ($k -like "$r.*") { $valid = $true; break }
        }
    }
    if ($valid) { $good += $r } else { $bad += $r }
}

if ($good.Count -gt 0) { Log-Ok "Valid refs $($good.Count): $($good -join ', ')" }
if ($bad.Count -gt 0) {
    foreach ($b in $bad) { Log-Err "Dangling ref: section $b" }
    exit 1
}

Log-Ok "Reference check passed"
exit 0
