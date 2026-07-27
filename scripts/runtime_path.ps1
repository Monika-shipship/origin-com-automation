param([switch]$Python)
$ErrorActionPreference = 'Stop'
$PluginRoot = Split-Path -Parent $PSScriptRoot
$Manifest = Get-Content -LiteralPath (Join-Path $PluginRoot '.codex-plugin\plugin.json') -Raw | ConvertFrom-Json
$RuntimeRoot = Join-Path (Join-Path $env:LOCALAPPDATA 'OriginComAutomation\runtime') ([string]$Manifest.version)
if ($Python) {
    Write-Output (Join-Path $RuntimeRoot '.venv\Scripts\python.exe')
} else {
    Write-Output $RuntimeRoot
}
