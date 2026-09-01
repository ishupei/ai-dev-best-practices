param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CliArgs
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "tianyin_wiki.py"

function Test-Python3 {
    param(
        [string] $Executable,
        [string[]] $PrefixArgs = @()
    )
    try {
        & $Executable @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$PythonExe = $null
$PythonPrefixArgs = @()

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher -and (Test-Python3 -Executable $PyLauncher.Source -PrefixArgs @("-3"))) {
    $PythonExe = $PyLauncher.Source
    $PythonPrefixArgs = @("-3")
}

if (-not $PythonExe) {
    $PythonCommands = Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and ($_.Source -notlike "*\Microsoft\WindowsApps\python.exe") }
    foreach ($Command in $PythonCommands) {
        if (Test-Python3 -Executable $Command.Source) {
            $PythonExe = $Command.Source
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Error "Python 3.8+ is required before running Tianyin Wiki CLI. Install Python first, then re-run this command. On Windows, prefer installing the official Python launcher so `py -3` works. Slow from python.org? Use a China mirror: https://mirrors.huaweicloud.com/python/ (tick 'Add python.exe to PATH' during install)."
    exit 1
}

& $PythonExe @PythonPrefixArgs $ScriptPath @CliArgs
exit $LASTEXITCODE
