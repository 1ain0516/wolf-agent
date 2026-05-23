# Wolf Agent v2.2 启动脚本
$env:DEEPSEEK_API_KEY = "REDACTED_API_KEY"
$PY = "C:\Users\24485\AppData\Local\Programs\Python\Python312\python.exe"
$port = if ($args[0]) { $args[0] } else { 5001 }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Wolf Agent v2.2" -ForegroundColor Cyan
Write-Host "  http://localhost:$port" -ForegroundColor Green
Write-Host "  Mode: Stub(free) / Real(API)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

& $PY -m wolf_agent web --port $port
