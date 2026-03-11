import os
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.services.mcp_runtime import make_resource_result, normalize_legacy_result

load_dotenv()
app = FastAPI()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mdbs")
SERVER_ID = "orders_mongo"

TOOLS = [
    {
        "name": "query.document",
        "description": "Query documents from the configured MongoDB collection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string"},
                "filter": {"type": "object"},
                "sort": {"type": "object"},
                "limit": {"type": "integer"},
                "projection": {"type": "object"},
                "customer_id": {"type": "string"},
            },
        },
    }
]

RESOURCES = [
    {"uri": f"schema://{SERVER_ID}", "name": "Schema", "description": "Normalized source schema"},
    {"uri": f"metadata://{SERVER_ID}", "name": "Metadata", "description": "Server metadata"},
    {"uri": f"health://{SERVER_ID}", "name": "Health", "description": "Server health"},
]


@app.on_event("startup")
async def startup():
    app.state.client = AsyncIOMotorClient(MONGO_URI)
    app.state.db = app.state.client[MONGO_DB]


def schema_payload():
    return {
        "mcp_id": SERVER_ID,
        "db_type": "nosql",
        "metadata": {"primary_tool": "query.document"},
        "entities": [
            {
                "name": "orders",
                "kind": "collection",
                "semantic_tags": ["entity:order"],
                "default_id_field": "order_id",
                "fields": [
                    {"name": "order_id", "type": "text", "semantic_tags": ["id", "order_id"]},
                    {"name": "customer_id", "type": "text", "semantic_tags": ["customer_id"]},
                    {"name": "amount", "type": "number", "semantic_tags": ["amount", "order_amount"]},
                    {"name": "order_date", "type": "date", "semantic_tags": ["order_date", "timestamp"]},
                ],
            }
        ],
    }


async def run_document_query(payload: dict):
    started = perf_counter()
    collection = payload.get("collection", "orders")
    filter_ = dict(payload.get("filter") or {})
    if payload.get("customer_id"):
        filter_["customer_id"] = payload["customer_id"]
    limit = int(payload.get("limit", 5))
    projection = payload.get("projection")
    sort = payload.get("sort") or {}

    cursor = app.state.db[collection].find(filter_, projection)
    if sort:
        cursor = cursor.sort(list(sort.items()))
    docs = []
    async for doc in cursor.limit(limit):
        doc["_id"] = str(doc.get("_id"))
        docs.append(doc)

    meta = {
        "source_id": SERVER_ID,
        "source_type": "query.document",
        "row_count": len(docs),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }
    return docs, meta


@app.get("/mcp/tools")
async def list_tools():
    return {"tools": TOOLS}


@app.get("/mcp/resources")
async def list_resources():
    return {"resources": RESOURCES}


@app.post("/mcp/tools/call")
async def mcp_call_tool(payload: dict):
    name = payload.get("name")
    arguments = payload.get("arguments") or {}
    if name != "query.document":
        raise HTTPException(status_code=404, detail=f"Unknown tool {name}")
    items, meta = await run_document_query(arguments)
    return normalize_legacy_result(items, meta, is_error=bool(meta.get("error"))).model_dump()


@app.post("/mcp/resources/read")
async def mcp_read_resource(payload: dict):
    uri = payload.get("uri")
    if uri == f"schema://{SERVER_ID}":
        return make_resource_result(uri, schema_payload()).model_dump()
    if uri == f"metadata://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "db_type": "nosql", "transport": "http"}).model_dump()
    if uri == f"health://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "status": "ok"}).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown resource {uri}")


@app.post("/get_schema")
async def get_schema():
    return schema_payload()


@app.post("/find")
async def find(payload: dict):
    docs, meta = await run_document_query(payload)
    return {"docs": docs, "meta": meta}
