# ============================================================
# ai-do diff scope gate for Windows.
# Usage:
#   .\check-diff-scope.ps1
#   .\check-diff-scope.ps1 -MaxFiles 8 -MaxModules 2
# Exit code: 0 = scope is within gate; 1 = scope/risk gate triggered.
# Keep this file ASCII-only for Windows PowerShell 5.1.
# ============================================================

param(
    [int]$MaxFiles = 8,
    [int]$MaxModules = 2
)

$ErrorActionPreference = "Stop"

function Log-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }
function Log-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }

$inside = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $inside.Trim() -ne "true") {
    Log-Err "Current directory is not a Git repository"
    exit 1
}

$unstaged = @(git diff --name-status)
$staged = @(git diff --cached --name-status)
$untracked = @(git ls-files --others --exclude-standard)
if ($unstaged.Count -eq 0 -and $staged.Count -eq 0 -and $untracked.Count -eq 0) {
    Log-Ok "No staged, unstaged, or untracked diff"
    exit 0
}

$files = @()
foreach ($line in $unstaged) {
    $parts = $line -split "\s+"
    if ($parts.Count -gt 1) { $files += $parts[-1] }
}
foreach ($line in $staged) {
    $parts = $line -split "\s+"
    if ($parts.Count -gt 1) { $files += $parts[-1] }
}
foreach ($line in $untracked) {
    if ($line) { $files += $line }
}
$files = @($files | Sort-Object -Unique)
$modules = @($files | ForEach-Object { ($_ -split '[\\/]')[0] } | Sort-Object -Unique)

Log-Info "Changed files: $($files.Count)"
foreach ($f in $files) { Write-Host "  $f" }
Log-Info "Top-level modules: $($modules.Count) ($($modules -join ', '))"

$riskyPattern = '(^|[\\/])(config|deploy[\\/]config|secrets|credentials)([\\/]|$)|(^|[\\/])\.env|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|package-lock\.json$|pnpm-lock\.yaml$|yarn\.lock$|pom\.xml$|build\.gradle$|settings\.gradle$'
$risky = @($files | Where-Object { $_ -match $riskyPattern })
if ($risky.Count -gt 0) {
    Log-Warn "Risky dependency/config files found:"
    foreach ($f in $risky) { Write-Host "  $f" }
}

$blocked = $false
if ($files.Count -gt $MaxFiles) {
    Log-Err "Changed file count $($files.Count) exceeds max $MaxFiles"
    $blocked = $true
}
if ($modules.Count -gt $MaxModules) {
    Log-Err "Top-level module count $($modules.Count) exceeds max $MaxModules"
    $blocked = $true
}
if ($risky.Count -gt 0) {
    Log-Err "Risk file gate triggered; ask for human confirmation"
    $blocked = $true
}

if ($blocked) { exit 1 }
Log-Ok "Diff scope gate passed"
exit 0
