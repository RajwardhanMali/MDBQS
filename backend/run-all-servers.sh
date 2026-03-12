#!/bin/bash

# --- Configuration ---
PORTS=(8000 8001 8002 8003 8004)
VENV_PATH=".venv/bin/activate"

# --- Logic: Stop Services ---
if [ "$1" == "stop" ]; then
    echo "Stopping MCP services on ports: ${PORTS[*]}..."

    for port in "${PORTS[@]}"; do
        PID=$(lsof -ti:$port)

        if [ -n "$PID" ]; then
            kill -9 $PID
            echo "Terminated process on port $port"
        fi
    done

    echo "All specified services stopped."
    exit 0
fi


# --- Function: Launch Service ---
launch_service () {
    TITLE=$1
    PORT=$2
    APP_PATH=$3
    RELOAD=$4

    RELOAD_FLAG=""
    if [ "$RELOAD" = true ]; then
        RELOAD_FLAG="--reload"
    fi

    CMD="source $VENV_PATH && uvicorn $APP_PATH --port $PORT $RELOAD_FLAG"

    # Try opening in new terminal tab (Linux GNOME)
    if command -v gnome-terminal &> /dev/null
    then
        gnome-terminal --tab --title="$TITLE" -- bash -c "$CMD; exec bash"
    else
        # fallback: run in background
        echo "Launching $TITLE on port $PORT"
        bash -c "$CMD" &
    fi
}


# --- Execution ---
echo "Launching MCP services with .venv..."

launch_service "SQL_MCP"    8001 "app.mcp_plugins.mcp_sql_sample.main:app" true
launch_service "NoSQL_MCP"  8002 "app.mcp_plugins.mcp_nosql_sample.main:app" true
launch_service "Graph_MCP"  8003 "app.mcp_plugins.mcp_graph_sample.main:app" true
launch_service "Vector_MCP" 8004 "app.mcp_plugins.mcp_vector_sample.main:app" true
launch_service "Backend"    8000 "app.main:app" true

echo "Done. Services started."