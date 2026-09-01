# Python probe launcher for the ai-db skill.
# Detects a suitable Python 3.7+ interpreter, in this order:
#   1. AI_DB_PYTHON environment variable (explicit, most reliable);
#   2. py -3 launcher;
#   3. python on PATH (skipping the Microsoft Store stub).
# Then forwards all arguments to db_query.py.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CliArgs
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "db_query.py"

function Test-Python3 {
    param(
        [string] $Executable,
        [string[]] $PrefixArgs = @()
    )
    try {
        & $Executable @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 7) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$PythonExe = $null
$PythonPrefixArgs = @()

$EnvPython = $env:AI_DB_PYTHON
if ($EnvPython) {
    $EnvPython = $EnvPython.Trim().Trim('"').Trim("'")
    if (Test-Python3 -Executable $EnvPython) {
        $PythonExe = $EnvPython
    } else {
        Write-Error "AI_DB_PYTHON is set to '$EnvPython' but it is not a usable Python 3.7+ interpreter. Fix the variable or unset it, then re-run this command."
        exit 1
    }
}

if (-not $PythonExe) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher -and (Test-Python3 -Executable $PyLauncher.Source -PrefixArgs @("-3"))) {
        $PythonExe = $PyLauncher.Source
        $PythonPrefixArgs = @("-3")
    }
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
    Write-Error "Python 3.7+ is required before running the ai-db CLI. Install Python first, then re-run this command. On Windows, prefer installing the official Python launcher so `py -3` works, or set the AI_DB_PYTHON environment variable to the interpreter path. Slow from python.org? Use a China mirror: https://mirrors.huaweicloud.com/python/ (tick 'Add python.exe to PATH' during install)."
    exit 1
}

& $PythonExe @PythonPrefixArgs $ScriptPath @CliArgs
exit $LASTEXITCODE
