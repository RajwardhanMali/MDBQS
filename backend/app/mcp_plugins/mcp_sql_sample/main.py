import json
import os
from time import perf_counter

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.services.mcp_runtime import make_resource_result, normalize_legacy_result

app = FastAPI()
load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_DSN")
SERVER_ID = "sql_customers"

TOOLS = [
    {
        "name": "query.sql",
        "description": "Execute a read-only SQL query against the structured database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["query"],
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
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)


def schema_payload():
    return {
        "mcp_id": SERVER_ID,
        "db_type": "sql",
        "metadata": {"primary_tool": "query.sql"},
        "entities": [
            {
                "name": "customers",
                "kind": "table",
                "semantic_tags": ["entity:customer", "canonical", "contact"],
                "default_id_field": "id",
                "fields": [
                    {"name": "id", "type": "text", "semantic_tags": ["id", "customer_id"]},
                    {"name": "name", "type": "text", "semantic_tags": ["name", "customer_name"]},
                    {"name": "email", "type": "text", "semantic_tags": ["email", "contact", "primary_email"]},
                    {"name": "embedding", "type": "vector", "semantic_tags": ["embedding", "similarity"]},
                ],
            }
        ],
    }


def normalize_embedding(emb_value):
    if emb_value is None:
        return None
    if isinstance(emb_value, str):
        try:
            emb_value = json.loads(emb_value)
        except json.JSONDecodeError:
            return None
    if isinstance(emb_value, dict):
        for key in ("vector", "values", "data"):
            if key in emb_value:
                emb_value = emb_value[key]
                break
    if isinstance(emb_value, (list, tuple)):
        try:
            return [float(x) for x in emb_value]
        except (TypeError, ValueError):
            return None
    return None


async def run_sql_query(payload: dict):
    started = perf_counter()
    query = payload.get("query")
    params = payload.get("params")
    if params is None:
        params = []
    elif isinstance(params, dict):
        params = list(params.values())

    if not query or not isinstance(query, str):
        return [], {"source_id": SERVER_ID, "source_type": "query.sql", "error": "Missing or invalid query"}

    if not query.strip().lower().startswith("select"):
        return [], {"source_id": SERVER_ID, "source_type": "query.sql", "error": "Only SELECT allowed in MVP"}

    if params and "?" in query:
        rebuilt = []
        idx = 1
        for ch in query:
            if ch == "?":
                rebuilt.append(f"${idx}")
                idx += 1
            else:
                rebuilt.append(ch)
        query = "".join(rebuilt)

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(query, *params) if params else await conn.fetch(query)
    result = []
    for row in rows:
        item = dict(row)
        if "embedding" in item:
            item["embedding"] = normalize_embedding(item["embedding"])
        result.append(item)
    meta = {
        "source_id": SERVER_ID,
        "source_type": "query.sql",
        "raw_query": query,
        "row_count": len(result),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }
    return result, meta


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
    if name != "query.sql":
        raise HTTPException(status_code=404, detail=f"Unknown tool {name}")
    items, meta = await run_sql_query(arguments)
    return normalize_legacy_result(items, meta, is_error=bool(meta.get("error"))).model_dump()


@app.post("/mcp/resources/read")
async def mcp_read_resource(payload: dict):
    uri = payload.get("uri")
    if uri == f"schema://{SERVER_ID}":
        return make_resource_result(uri, schema_payload()).model_dump()
    if uri == f"metadata://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "db_type": "sql", "transport": "http"}).model_dump()
    if uri == f"health://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "status": "ok"}).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown resource {uri}")


@app.post("/get_schema")
async def get_schema():
    return schema_payload()


@app.post("/execute_sql")
async def execute_sql(payload: dict):
    try:
        rows, meta = await run_sql_query(payload)
        return {"rows": rows, "meta": meta}
    except Exception as exc:
        return {"rows": [], "meta": {"source_id": SERVER_ID, "source_type": "query.sql", "error": str(exc)}}
