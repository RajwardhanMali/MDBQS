Write-Host "Starting all MCP services and backend..."

Start-Job -Name sql_mcp      -ScriptBlock { uvicorn app.mcp_plugins.mcp_sql_sample.main:app --port 8001 }
Start-Job -Name nosql_mcp    -ScriptBlock { uvicorn app.mcp_plugins.mcp_nosql_sample.main:app --port 8002 }
Start-Job -Name graph_mcp    -ScriptBlock { uvicorn app.mcp_plugins.mcp_graph_sample.main:app --port 8003 }
Start-Job -Name vector_mcp   -ScriptBlock { uvicorn app.mcp_plugins.mcp_vector_sample.main:app --port 8004 }
Start-Job -Name backend      -ScriptBlock { uvicorn app.main:app --port 8000 --reload }

Write-Host "All services started as background jobs."

# Show job details
Get-Job

Write-Host "`nUse 'Receive-Job -Name jobname' to view logs."
Write-Host "Use 'Stop-Job -Name jobname' to stop a service."
