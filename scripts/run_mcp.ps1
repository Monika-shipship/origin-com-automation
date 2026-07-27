$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = & (Join-Path $PSScriptRoot 'runtime_path.ps1')
$RuntimePython = & (Join-Path $PSScriptRoot 'runtime_path.ps1') -Python
if (-not (Test-Path -LiteralPath $RuntimePython)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1') -RuntimeRoot $RuntimeRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$env:PYTHONNOUSERSITE = '1'
& $RuntimePython -m origin_com_automation.server
exit $LASTEXITCODE
