$ErrorActionPreference = 'Stop'

$RuntimeRoot = & (Join-Path $PSScriptRoot 'runtime_path.ps1')
$RuntimePython = & (Join-Path $PSScriptRoot 'runtime_path.ps1') -Python
$RuntimeMetadata = Join-Path $RuntimeRoot 'runtime.json'
if (-not (Test-Path -LiteralPath $RuntimePython) -or -not (Test-Path -LiteralPath $RuntimeMetadata)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1') -RuntimeRoot $RuntimeRoot 2>&1 | ForEach-Object {
        [Console]::Error.WriteLine($_.ToString())
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:PYTHONNOUSERSITE = '1'
& $RuntimePython -m origin_com_automation.server
exit $LASTEXITCODE
