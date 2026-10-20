param([string]$Python = 'python', [string]$ExistingPython = '', [switch]$SkipInstall, [switch]$NoSeed, [ValidateRange(1024,65535)][int]$Port = 8010)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$portProbe = [System.Net.Sockets.TcpClient]::new()
try {
    $portTask = $portProbe.ConnectAsync('127.0.0.1',$Port)
    if ($portTask.Wait(800) -and $portProbe.Connected) { throw "$Port 端口已被占用，请先停止已有本地服务或使用正在运行的页面。" }
} catch [System.AggregateException] {
    # 端口无人监听，继续启动。
} finally { $portProbe.Dispose() }
if ($ExistingPython) {
    $runtimePython = (Resolve-Path -LiteralPath $ExistingPython).Path
} else {
    if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & $Python -m venv '.venv'
        if ($LASTEXITCODE -ne 0) { throw '创建Python环境失败' }
    }
    $runtimePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
}
if (!$SkipInstall) {
    $requirements = if (Test-Path -LiteralPath 'requirements-lock.txt') { 'requirements-lock.txt' } else { 'requirements.txt' }
    & $runtimePython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Python依赖安装失败' }
    & npm.cmd --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Node依赖安装失败' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
}
if (!(Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
New-Item -ItemType Directory -Force -Path 'runtime' | Out-Null
if (!$NoSeed) {
    & $runtimePython -m app.seed
    if ($LASTEXITCODE -ne 0) { throw '数据库初始化失败' }
}
$taskApi = Start-Process -FilePath $runtimePython -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'runtime\api.out.log') -RedirectStandardError (Join-Path $projectRoot 'runtime\api.err.log')
$taskWorker = Start-Process -FilePath $runtimePython -ArgumentList @('-m','app.worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'runtime\worker.out.log') -RedirectStandardError (Join-Path $projectRoot 'runtime\worker.err.log')
$processFile = if ($Port -eq 8010) { 'runtime\local-processes.json' } else { "runtime\local-processes-$Port.json" }
@{ api=$taskApi.Id; worker=$taskWorker.Id; python=$runtimePython; project=$projectRoot; port=$Port } | ConvertTo-Json | Set-Content -LiteralPath $processFile
$ready = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try { $response=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2; if($response.code -eq 0) { $ready=$true; break } } catch {}
    Start-Sleep -Milliseconds 500
}
if (!$ready) { throw 'API健康检查失败；请检查runtime中的日志。进程记录已保留，可用stop-local.ps1停止。' }
Write-Host "RAG Lab 已就绪：http://127.0.0.1:$Port；数据库：$($response.data.database)；日志位于runtime。"
