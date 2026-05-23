# Wolf Agent v2.2 启动脚本
$PROJECT = "D:\agent project\wolf-agent"
$PY = "C:\Users\24485\AppData\Local\Programs\Python\Python312\python.exe"
$port = if ($args[0]) { $args[0] } else { 5001 }

Set-Location -Path $PROJECT -ErrorAction Stop
$env:PYTHONPATH = $PROJECT

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "提示: DEEPSEEK_API_KEY 未设置，Real 模式将不可用" -ForegroundColor Yellow
    Write-Host "设置方式: `$env:DEEPSEEK_API_KEY=`"sk-xxx`"" -ForegroundColor Gray
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Wolf Agent v2.2" -ForegroundColor Cyan
Write-Host "  http://localhost:$port" -ForegroundColor Green
Write-Host "  Stub(免费) / Real(需 API Key)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

& $PY -m wolf_agent web --port $port

if ($LASTEXITCODE -ne 0) {
    Write-Host "启动失败! 错误码: $LASTEXITCODE" -ForegroundColor Red
    Read-Host
}
