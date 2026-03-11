from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["sources"])


@router.get("/sources")
async def list_sources(request: Request):
    runtime = request.app.state.mcp_runtime
    return {"sources": [server.model_dump() for server in runtime.list_servers()]}


@router.get("/sources/{server_id}")
async def get_source(server_id: str, request: Request):
    runtime = request.app.state.mcp_runtime
    server = runtime.require_server(server_id)
    return server.model_dump()
