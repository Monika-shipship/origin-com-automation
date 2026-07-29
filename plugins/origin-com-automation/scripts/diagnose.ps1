$ErrorActionPreference = 'Stop'
$RuntimeRoot = & (Join-Path $PSScriptRoot 'runtime_path.ps1')
$RuntimePython = & (Join-Path $PSScriptRoot 'runtime_path.ps1') -Python
$RuntimeMetadata = Join-Path $RuntimeRoot 'runtime.json'
if (-not (Test-Path -LiteralPath $RuntimePython) -or -not (Test-Path -LiteralPath $RuntimeMetadata)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1') -RuntimeRoot $RuntimeRoot
}
& $RuntimePython -c "import json; from origin_com_automation.tools.health import health_check; print(json.dumps(health_check().to_dict(), indent=2))"
exit $LASTEXITCODE
