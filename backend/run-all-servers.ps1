# --- Configuration ---
$PORTS = @(8000, 8001, 8002, 8003, 8004)
$VENV_PATH = Join-Path (Get-Location) ".venv\Scripts\Activate.ps1"

# --- Logic: Stop Services ---
# We move this to the top so it executes INSTEAD of starting services
if ($args[0] -eq "stop") {
    Write-Host "Stopping MCP services on ports: $($PORTS -join ', ')..." -ForegroundColor Yellow
    foreach ($port in $PORTS) {
        $process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($process) {
            $process | ForEach-Object { 
                Stop-Process -Id $_.OwningProcess -Force 
                Write-Host "Terminated process on port $port" -ForegroundColor Gray
            }
        }
    }
    Write-Host "All specified services stopped." -ForegroundColor Green
    exit
}

# --- Function: Launch Service ---
function Launch-Service ($title, $port, $appPath, $reload=$false) {
    $reloadFlag = if ($reload) { "--reload" } else { "" }
    
    # We wrap the command in single quotes to ensure the internal & call works in the new tab
    $cmd = "& '.venv\Scripts\Activate.ps1'; uvicorn $appPath --port $port $reloadFlag"

    Start-Process wt -ArgumentList @(
        "nt",
        "--title", $title,
        "-d", (Get-Location),
        "powershell",
        "-Command", $cmd
    )
}

# --- Execution ---
Write-Host "Launching MCP services with .venv..." -ForegroundColor Cyan

Launch-Service "SQL_MCP"    8001 "app.mcp_plugins.mcp_sql_sample.main:app" $true
Launch-Service "NoSQL_MCP"  8002 "app.mcp_plugins.mcp_nosql_sample.main:app" $true
Launch-Service "Graph_MCP"  8003 "app.mcp_plugins.mcp_graph_sample.main:app" $true
Launch-Service "Vector_MCP" 8004 "app.mcp_plugins.mcp_vector_sample.main:app" $true
Launch-Service "Backend"    8000 "app.main:app" $true

Write-Host "Done. Check the new Terminal tabs." -ForegroundColor Green