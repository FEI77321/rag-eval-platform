param([string]$Python = 'python', [string]$ExistingPython = '', [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$portProbe = [System.Net.Sockets.TcpClient]::new()
try {
    $portTask = $portProbe.ConnectAsync('127.0.0.1',8010)
    if ($portTask.Wait(800) -and $portProbe.Connected) { throw '8010端口已被占用，请先停止已有本地服务或使用正在运行的页面。' }
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
    & $runtimePython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python依赖安装失败' }
    & npm.cmd --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Node依赖安装失败' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
}
if (!(Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
New-Item -ItemType Directory -Force -Path 'runtime' | Out-Null
& $runtimePython -m app.seed
if ($LASTEXITCODE -ne 0) { throw '数据库初始化失败' }
$taskApi = Start-Process -FilePath $runtimePython -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'runtime\api.out.log') -RedirectStandardError (Join-Path $projectRoot 'runtime\api.err.log')
$taskWorker = Start-Process -FilePath $runtimePython -ArgumentList @('-m','app.worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'runtime\worker.out.log') -RedirectStandardError (Join-Path $projectRoot 'runtime\worker.err.log')
@{ api=$taskApi.Id; worker=$taskWorker.Id; python=$runtimePython; project=$projectRoot } | ConvertTo-Json | Set-Content -LiteralPath 'runtime\local-processes.json'
Write-Host 'RAG Lab 已启动：http://127.0.0.1:8010；日志位于 runtime。'
