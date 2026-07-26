$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $PluginRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
& $VenvPython -c "import json; from origin_com_automation.tools.health import health_check; print(json.dumps(health_check().to_dict(), indent=2))"
exit $LASTEXITCODE
