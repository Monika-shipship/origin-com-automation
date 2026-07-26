$paramLive = $false
if ($args -contains '-Live') {
    $paramLive = $true
}
$allowExisting = $args -contains '-AllowExisting'
$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $PluginRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
if ($paramLive) {
    $env:ORIGIN_LIVE_SMOKE = '1'
}
if ($allowExisting) {
    $env:ORIGIN_ALLOW_EXISTING = '1'
}
# Origin terminates its COM local server during Exit; pytest's Windows
# faulthandler reports that handled RPC disconnect as a fatal-looking trace.
& $VenvPython -m pytest -q -p no:faulthandler -m smoke
exit $LASTEXITCODE
