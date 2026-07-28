param(
    [string]$RuntimeRoot,
    [switch]$WithTestDeps
)
$ErrorActionPreference = 'Stop'

$PluginRoot = Split-Path -Parent $PSScriptRoot
$Python = Get-Command python -ErrorAction Stop
$Manifest = Get-Content -LiteralPath (Join-Path $PluginRoot '.codex-plugin\plugin.json') -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    $RuntimeRoot = Join-Path (Join-Path $env:LOCALAPPDATA 'OriginComAutomation\runtime') ([string]$Manifest.version)
}
$RuntimeRoot = [IO.Path]::GetFullPath($RuntimeRoot)
$RuntimePython = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'
$RuntimeMetadata = Join-Path $RuntimeRoot 'runtime.json'
$LockPath = Join-Path $RuntimeRoot '.bootstrap.lock'
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

$lock = $null
for ($attempt = 0; $attempt -lt 600 -and $null -eq $lock; $attempt++) {
    try {
        $lock = [IO.File]::Open(
            $LockPath,
            [IO.FileMode]::OpenOrCreate,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    } catch [IO.IOException] {
        Start-Sleep -Milliseconds 250
    }
}
if ($null -eq $lock) { throw "Could not acquire runtime bootstrap lock: $LockPath" }

try {
    if (-not (Test-Path -LiteralPath $RuntimePython)) {
        & $Python.Source -m venv (Join-Path $RuntimeRoot '.venv')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    & $RuntimePython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $InstallTarget = if ($WithTestDeps) { "$PluginRoot[test]" } else { $PluginRoot }
    & $RuntimePython -m pip install --upgrade $InstallTarget
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $Metadata = [ordered]@{
        plugin_version = [string]$Manifest.version
        runtime_root = $RuntimeRoot
        installed_at_utc = [DateTime]::UtcNow.ToString('o')
        editable = $false
    }
    $Metadata | ConvertTo-Json | Set-Content -LiteralPath $RuntimeMetadata -Encoding UTF8
} finally {
    $lock.Dispose()
}

Write-Output "Origin COM Automation external runtime is ready: $RuntimePython"
