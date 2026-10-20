$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$base = 'http://127.0.0.1:8010'
$healthy = $false
try { $health=Invoke-RestMethod "$base/api/health" -TimeoutSec 2; $healthy=$health.code -eq 0 } catch {}
if (!$healthy) {
    $deploymentFile = Join-Path $projectRoot 'runtime\deployment.json'
    if (Test-Path -LiteralPath $deploymentFile) {
        $deployment=Get-Content -LiteralPath $deploymentFile -Raw | ConvertFrom-Json
        if (Test-Path -LiteralPath $deployment.python) {
            & (Join-Path $PSScriptRoot 'start-local.ps1') -ExistingPython $deployment.python -SkipInstall -NoSeed
        } else { & (Join-Path $PSScriptRoot 'start-local.ps1') }
    } else { & (Join-Path $PSScriptRoot 'start-local.ps1') }
}
Start-Process $base
