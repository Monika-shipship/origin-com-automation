$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$Python = Get-Command python -ErrorAction Stop
$VenvPython = Join-Path $PluginRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python.Source -m venv (Join-Path $PluginRoot '.venv')
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $VenvPython -m pip install -e "$PluginRoot[test]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Origin COM Automation runtime is ready: $VenvPython"
