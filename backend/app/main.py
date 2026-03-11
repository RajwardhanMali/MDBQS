import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat as chat_router
from app.api.v1 import query as query_router
from app.api.v1 import schema as schema_router
from app.api.v1 import sources as sources_router
from app.repositories.chat import create_chat_persistence
from app.services import mcp_manager
from app.services.chat_service import ChatService
from app.services.schema_index import schema_index, source_schema_from_dict

load_dotenv()

logger = logging.getLogger("app.main")

app = FastAPI(title="MDBQS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router.router)
app.include_router(chat_router.router)
app.include_router(schema_router.router)
app.include_router(sources_router.router)


@app.on_event("startup")
async def startup():
    mcp_manager.register_default_manifests()
    await mcp_manager.init_managers(register_defaults=False)

    schema_index.clear()
    for server in mcp_manager.runtime.list_servers():
        try:
            schema_json = await mcp_manager.runtime.read_json_resource(server.server_id, f"schema://{server.server_id}")
            schema_index.register_schema(source_schema_from_dict(schema_json))
        except Exception:
            logger.exception("Failed to load schema for %s during startup", server.server_id)

    app.state.mcp_runtime = mcp_manager.runtime
    app.state.chat_persistence = await create_chat_persistence()
    app.state.chat_service = ChatService(app.state.chat_persistence)


@app.get("/")
async def root():
    return {"message": "MDBQS Backend running"}
