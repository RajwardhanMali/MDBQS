Write-Host "Launching MCP services with .venv..." -ForegroundColor Cyan

# Absolute path to venv activation
$VENV_PATH = Join-Path (Get-Location) ".venv\Scripts\Activate.ps1"

function Launch-Service ($title, $port, $appPath, $reload=$false) {

    if ($reload) {
        $cmd = "& '$VENV_PATH'; uvicorn $appPath --port $port --reload"
    }
    else {
        $cmd = "& '$VENV_PATH'; uvicorn $appPath --port $port"
    }

    Start-Process wt -ArgumentList @(
        "nt",
        "--title", $title,
        "-d", (Get-Location),
        "powershell",
        "-NoExit",
        "-Command", $cmd
    )
}

# Launch services
Launch-Service "SQL_MCP"    8001 "app.mcp_plugins.mcp_sql_sample.main:app"
Launch-Service "NoSQL_MCP"  8002 "app.mcp_plugins.mcp_nosql_sample.main:app"
Launch-Service "Graph_MCP"  8003 "app.mcp_plugins.mcp_graph_sample.main:app"
Launch-Service "Vector_MCP" 8004 "app.mcp_plugins.mcp_vector_sample.main:app"
Launch-Service "Backend"    8000 "app.main:app" $true

Write-Host "Done. Check the new Terminal tabs." -ForegroundColor Green