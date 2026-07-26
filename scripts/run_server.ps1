$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $PluginRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
& $VenvPython -m origin_com_automation.server
exit $LASTEXITCODE
