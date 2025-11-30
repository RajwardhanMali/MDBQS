# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import query as query_router, schema as schema_router
from app.services import mcp_manager
from app.services.mcp_manager import register_mcp
import os

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


register_mcp({"id":"sql_customers","host":"http://localhost:8001", "capabilities":["query.sql"]})
register_mcp({"id":"orders_mongo","host":"http://localhost:8002", "capabilities":["query.document"]})
register_mcp({"id":"graph_referrals","host":"http://localhost:8003", "capabilities":["query.graph"]})
register_mcp({"id":"vector_customers","host":"http://localhost:8004", "capabilities":["query.vector"]})


@app.on_event("startup")
async def startup():
    # initialize MCP manager (does minimal work)
    await mcp_manager.init_managers(settings)

@app.get("/")
async def root():
    return {"message": "MDBS Backend running"}
