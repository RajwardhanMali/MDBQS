import json
import os
import re
from time import perf_counter
from typing import Any, Dict, List

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
    app.state.schema_cache = None


def _semantic_tags_for_field(field_name: str, field_type: str) -> List[str]:
    lowered = field_name.lower()
    tags = [field_name]
    if lowered == "id" or lowered.endswith("_id"):
        tags.extend(["id", lowered])
    if "name" in lowered:
        tags.append("name")
    if "email" in lowered:
        tags.extend(["email", "contact"])
    if "date" in lowered or "time" in lowered:
        tags.append("timestamp")
    if field_type == "vector" or lowered == "embedding":
        tags.extend(["embedding", "similarity"])
    return list(dict.fromkeys(tags))


def _entity_tags(table_name: str) -> List[str]:
    singular = table_name[:-1] if table_name.endswith("s") else table_name
    return [f"entity:{singular}", table_name]


async def schema_payload() -> Dict[str, Any]:
    cached = getattr(app.state, "schema_cache", None)
    if cached:
        return cached

    entities: List[Dict[str, Any]] = []
    query = """
        SELECT
            c.table_name,
            c.column_name,
            c.data_type,
            c.udt_name,
            c.ordinal_position
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema
         AND t.table_name = c.table_name
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_name, c.ordinal_position
    """

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(query)

    by_table: Dict[str, List[asyncpg.Record]] = {}
    for row in rows:
        by_table.setdefault(row["table_name"], []).append(row)

    for table_name, columns in by_table.items():
        fields: List[Dict[str, Any]] = []
        default_id_field = None
        for column in columns:
            column_name = column["column_name"]
            column_type = "vector" if column["udt_name"] == "vector" else column["data_type"]
            if default_id_field is None and (column_name == "id" or column_name.endswith("_id")):
                default_id_field = column_name
            fields.append(
                {
                    "name": column_name,
                    "type": column_type,
                    "semantic_tags": _semantic_tags_for_field(column_name, column_type),
                }
            )

        entities.append(
            {
                "name": table_name,
                "kind": "table",
                "semantic_tags": _entity_tags(table_name),
                "default_id_field": default_id_field,
                "fields": fields,
            }
        )

    if not entities:
        entities = [
            {
                "name": "customers",
                "kind": "table",
                "semantic_tags": ["entity:customer", "customers"],
                "default_id_field": "id",
                "fields": [
                    {"name": "id", "type": "text", "semantic_tags": ["id", "customer_id"]},
                    {"name": "name", "type": "text", "semantic_tags": ["name", "customer_name"]},
                    {"name": "email", "type": "text", "semantic_tags": ["email", "contact", "primary_email"]},
                    {"name": "embedding", "type": "vector", "semantic_tags": ["embedding", "similarity"]},
                ],
            }
        ]

    payload = {
        "mcp_id": SERVER_ID,
        "db_type": "sql",
        "metadata": {"primary_tool": "query.sql"},
        "entities": entities,
    }
    app.state.schema_cache = payload
    return payload


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


def _flatten_params(payload: dict) -> List[Any]:
    params = payload.get("params")
    ordered: List[Any] = []
    if params is None:
        params = {}

    if isinstance(params, dict):
        ordered.extend(params.values())
    elif isinstance(params, list):
        ordered.extend(params)
    else:
        ordered.append(params)

    for key, value in payload.items():
        if key not in {"query", "params"}:
            ordered.append(value)

    return ordered


def _expand_sql_placeholders(query: str, params: List[Any]) -> tuple[str, List[Any], bool]:
    if "?" not in query:
        return query, params, False

    rebuilt: List[str] = []
    flat_params: List[Any] = []
    param_iter = iter(params)
    idx = 1
    replaced = 0
    empty_list_used = False

    for ch in query:
        if ch != "?":
            rebuilt.append(ch)
            continue

        replaced += 1
        val = next(param_iter, None)
        if isinstance(val, list):
            if not val:
                rebuilt.append("NULL")
                empty_list_used = True
            else:
                placeholders = ", ".join(f"${idx + k}" for k in range(len(val)))
                rebuilt.append(placeholders)
                flat_params.extend(val)
                idx += len(val)
        else:
            rebuilt.append(f"${idx}")
            flat_params.append(val)
            idx += 1

    remaining = list(param_iter)
    if remaining:
        flat_params.extend(remaining)
    if replaced != query.count("?"):
        raise ValueError("SQL placeholder expansion failed")
    return "".join(rebuilt), flat_params, empty_list_used


def _looks_like_read_only_select(query: str) -> bool:
    stripped = query.strip().lower()
    return stripped.startswith("select") or stripped.startswith("with")


def _validate_query_text(query: str) -> None:
    if ";" in query.strip().rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    forbidden = re.search(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", query, re.IGNORECASE)
    if forbidden:
        raise ValueError("Only read-only SELECT/CTE queries are allowed")


async def run_sql_query(payload: dict):
    started = perf_counter()
    query = payload.get("query")
    params = _flatten_params(payload)

    if not query or not isinstance(query, str):
        return [], {"source_id": SERVER_ID, "source_type": "query.sql", "error": "Missing or invalid query"}

    if not _looks_like_read_only_select(query):
        return [], {"source_id": SERVER_ID, "source_type": "query.sql", "error": "Only SELECT/CTE queries are allowed"}

    try:
        _validate_query_text(query)
        query, params, empty_list_used = _expand_sql_placeholders(query, params)
        if empty_list_used and re.search(r"\bIN\s*\(\s*NULL\s*\)", query, re.IGNORECASE):
            query = re.sub(r"\bIN\s*\(\s*NULL\s*\)", "IN (NULL)", query, flags=re.IGNORECASE)
    except ValueError as exc:
        return [], {"source_id": SERVER_ID, "source_type": "query.sql", "error": str(exc)}

    try:
        async with app.state.pool.acquire() as conn:
            rows = await conn.fetch(query, *params) if params else await conn.fetch(query)
    except Exception as exc:
        return [], {
            "source_id": SERVER_ID,
            "source_type": "query.sql",
            "raw_query": query,
            "error": str(exc),
        }

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
        return make_resource_result(uri, await schema_payload()).model_dump()
    if uri == f"metadata://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "db_type": "sql", "transport": "http"}).model_dump()
    if uri == f"health://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "status": "ok"}).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown resource {uri}")


@app.post("/get_schema")
async def get_schema():
    return await schema_payload()


@app.post("/execute_sql")
async def execute_sql(payload: dict):
    rows, meta = await run_sql_query(payload)
    return {"rows": rows, "meta": meta}
