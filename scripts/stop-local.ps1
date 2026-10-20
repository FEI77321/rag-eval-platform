param([ValidateRange(1024,65535)][int]$Port = 8010)
$projectRoot = Split-Path -Parent $PSScriptRoot
$processFile = if ($Port -eq 8010) { 'runtime\local-processes.json' } else { "runtime\local-processes-$Port.json" }
$pidFile = Join-Path $projectRoot $processFile
if (Test-Path -LiteralPath $pidFile) {
    $taskPids = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    foreach ($taskProcessId in @($taskPids.api, $taskPids.worker)) {
        $taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $taskProcessId" -ErrorAction SilentlyContinue
        if ($taskProcess -and $taskPids.project -eq $projectRoot -and $taskProcess.ExecutablePath -eq $taskPids.python -and $taskProcess.CommandLine -match 'uvicorn|app.worker') {
            # Windows venv launcher可能有同命令的Python子进程，先停受控子进程。
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $taskProcessId -and $_.Name -eq 'python.exe' -and $_.CommandLine -match 'uvicorn|app.worker' } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
            Stop-Process -Id $taskProcessId
        }
    }
    Remove-Item -LiteralPath $pidFile
}
Write-Host '本项目本地进程已停止。运行中的任务可在下次启动后断点恢复。'
