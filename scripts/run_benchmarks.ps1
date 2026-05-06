param(
    [string]$OutputRoot = "",
    [int]$TimeoutSeconds = 1800
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Runner = Join-Path $RepoRoot "benchmarks\run_all_benchmarks.py"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $Python) {
    throw "Python was not found on PATH. Install Python or activate the project virtual environment."
}

$ArgsList = @($Runner, "--timeout-seconds", $TimeoutSeconds.ToString())
if ($OutputRoot.Trim()) {
    $ArgsList += @("--output-root", $OutputRoot)
}

Push-Location $RepoRoot
try {
    & $Python.Source @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
