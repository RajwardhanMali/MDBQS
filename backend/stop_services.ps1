Write-Host "Stopping MCP services..." -ForegroundColor Yellow

$ports = @(8000,8001,8002,8003,8004)

foreach ($port in $ports) {

    $connections = netstat -ano | Select-String ":$port"

    foreach ($conn in $connections) {
        $parts = $conn -split "\s+"
        $pid = $parts[-1]

        if ($pid -match "^\d+$") {
            Write-Host "Killing process on port $port (PID $pid)"
            taskkill /PID $pid /F | Out-Null
        }
    }
}

Write-Host "All MCP services stopped." -ForegroundColor Green