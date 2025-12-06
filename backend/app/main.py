# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI, logger
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import query as query_router, schema as schema_router
from app.services import mcp_manager
from app.services.mcp_manager import register_mcp
import os

from app.services.schema_index import SchemaIndex, source_schema_from_dict

load_dotenv()

class Settings:
    app_name: str = "test"
    POSTGRES_DSN: str = os.getenv("POSTGRES_DSN")
    MONGO_URI: str =  os.getenv("MONGO_URI")
    MONGO_DB: str = os.getenv("MONGO_DB", "mdbs")
    NEO4J_URI: str = os.getenv("NEO4J_URI")
    NEO4J_USER: str = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD")
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# register routers
app.include_router(query_router.router)
app.include_router(schema_router.router)
schema_index = SchemaIndex()

@app.on_event("startup")
async def startup():
    # initialize MCP manager (does minimal work)
    DEFAULT_MCPS = [
        {"id": "sql_customers", "host": "http://localhost:8001", "capabilities": ["query.sql"]},
        {"id": "orders_mongo", "host": "http://localhost:8002", "capabilities": ["query.document"]},
        {"id": "graph_referrals", "host": "http://localhost:8003", "capabilities": ["query.graph"]},
        {"id": "vector_customers", "host": "http://localhost:8004", "capabilities": ["query.vector"]},
    ]
    for manifest in DEFAULT_MCPS:
        if manifest["id"] not in mcp_manager.MCP_REGISTRY:
            mcp_manager.register_mcp(manifest)

    # Fetch schemas from each MCP
        async def fetch_all_schemas():
            for mcp_id in mcp_manager.MCP_REGISTRY.keys():
                try:
                    schema_json = await mcp_manager.call_execute(mcp_id, "get_schema", {})
                    schema = source_schema_from_dict(schema_json)
                    schema_index.register_schema(schema)
                except Exception as e:
                    print(e)

        await fetch_all_schemas()

@app.get("/")
async def root():
    return {"message": "MDBS Backend running"}
