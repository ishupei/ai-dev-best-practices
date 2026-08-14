# ============================================================
# ai-do report completeness checker for Windows.
# Usage:
#   .\check-report.ps1 -File .\report.md
#   .\check-report.ps1 -Text "final report text"
# Exit code: 0 = pass; 1 = required block missing.
# Keep this file ASCII-only for Windows PowerShell 5.1.
# ============================================================

param(
    [string]$Text,
    [string]$File
)

$ErrorActionPreference = "Stop"

function Log-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }
function Log-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function U($codes) {
    return -join (($codes -split ' ') | ForEach-Object { [char][Convert]::ToInt32($_, 16) })
}
function AnyOf($patterns) {
    return ($patterns | ForEach-Object { [regex]::Escape($_) }) -join "|"
}

if ($Text) {
    $target = $Text
    $sourceDesc = "inline text"
} elseif ($File) {
    if (-not (Test-Path $File)) { Log-Err "File does not exist: $File"; exit 1 }
    $target = Get-Content -Raw -Encoding UTF8 -Path $File
    $sourceDesc = $File
} else {
    Log-Err "Provide -Text or -File"
    exit 1
}

Log-Info "Source: $sourceDesc"

# Keyword map for required Chinese report headings. Values are encoded as
# Unicode code points so this script stays ASCII-only and remains parseable
# by Windows PowerShell 5.1. Each key names the report block being checked.
$required = [ordered]@{
    "execution contract" = AnyOf @((U "6267 884C 5951 7EA6"), (U "6267 884C 5951 7EA6 6458 8981"))
    "completed scope" = AnyOf @((U "5B8C 6210 8303 56F4"))
    "changed files" = AnyOf @((U "53D8 66F4 6587 4EF6"), (U "6539 52A8 6587 4EF6"))
    "validation level" = AnyOf @((U "9A8C 8BC1 7B49 7EA7"), (U "9759 6001 81EA 68C0"))
    "diff review" = "diff|Diff"
    "build or command" = AnyOf @((U "6784 5EFA"), (U "7F16 8BD1"), (U "547D 4EE4"))
    "test execution" = AnyOf @((U "6D4B 8BD5 6267 884C"), (U "6D4B 8BD5"))
    "tech stack" = AnyOf @((U "6280 672F 6808 5224 5B9A"), (U "6280 672F 6808"))
    "standards check" = AnyOf @((U "89C4 8303 68C0 67E5"))
    "skipped validation" = AnyOf @((U "672A 6267 884C 9A8C 8BC1"), (U "672A 6267 884C"))
    "standards receipt" = AnyOf @((U "89C4 8303 8BFB 53D6 51ED 8BC1"), (U "5DF2 8BFB 89C4 8303"), (U "8BFB 53D6 51ED 8BC1"))
}

$missing = @()
foreach ($name in $required.Keys) {
    if ($target -notmatch $required[$name]) {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    foreach ($m in $missing) { Log-Err "Missing required block: $m" }
    exit 1
}

Log-Ok "Report completeness check passed"
exit 0
