import logging
import os
import re
from time import perf_counter
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.services.mcp_runtime import make_resource_result, normalize_legacy_result

try:
    from neo4j import AsyncGraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

load_dotenv()
logger = logging.getLogger("mcp_graph_sample")
logging.basicConfig(level=logging.INFO)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")
SERVER_ID = "graph_referrals"


class StartNode(BaseModel):
    property: str
    value: Any


class TraversePayload(BaseModel):
    start: Optional[StartNode] = None
    rel: str = "REFERRED"
    depth: int = 1
    start_id: Optional[str] = None
    max_depth: Optional[int] = None
    cypher: Optional[str] = None


app = FastAPI(title="Graph Database Plugin (Neo4j)")

TOOLS = [
    {
        "name": "query.graph",
        "description": "Query or traverse the graph source.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cypher": {"type": "string"},
                "start": {"type": "object"},
                "start_id": {"type": "string"},
                "depth": {"type": "integer"},
                "rel": {"type": "string"},
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
    if not NEO4J_AVAILABLE:
        app.state.driver = None
        return
    try:
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        await driver.verify_connectivity()
        app.state.driver = driver
    except Exception:
        logger.exception("Failed to connect to Neo4j at startup")
        app.state.driver = None


@app.on_event("shutdown")
async def shutdown():
    if getattr(app.state, "driver", None):
        await app.state.driver.close()


def schema_payload():
    return {
        "mcp_id": SERVER_ID,
        "db_type": "graph",
        "metadata": {"primary_tool": "query.graph"},
        "entities": [
            {
                "name": "customers",
                "kind": "node",
                "semantic_tags": ["entity:customer", "referral_graph"],
                "default_id_field": "id",
                "fields": [
                    {"name": "id", "type": "text", "semantic_tags": ["id", "customer_id"]},
                    {"name": "name", "type": "text", "semantic_tags": ["name", "customer_name"]},
                    {"name": "email", "type": "text", "semantic_tags": ["email"]},
                ],
            },
            {
                "name": "REFERRED",
                "kind": "relationship",
                "semantic_tags": ["referral"],
                "fields": [{"name": "since", "type": "date", "semantic_tags": ["since_date"]}],
            },
        ],
    }


def _sanitize_name(name: str, type_name: str):
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise HTTPException(status_code=400, detail=f"Invalid {type_name}: '{name}'")
    return name


def _normalize_cypher(cypher: str) -> str:
    normalized = cypher

    # Normalize common label drift from the LLM.
    normalized = re.sub(r":customers\b", ":Customer", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r":customer\b", ":Customer", normalized, flags=re.IGNORECASE)

    # If the query references REFERRED.since without binding a relationship variable,
    # bind it as `r` on simple outgoing referral edges.
    if "REFERRED.since" in normalized and "-[:REFERRED]->" in normalized:
        normalized = normalized.replace("-[:REFERRED]->", "-[r:REFERRED]->")
        normalized = normalized.replace("REFERRED.since", "r.since")

    return normalized


async def run_graph_query(payload: dict):
    started = perf_counter()
    if not app.state.driver:
        return [], {"source_id": SERVER_ID, "source_type": "query.graph", "error": "Neo4j driver not initialized"}

    try:
        if payload.get("cypher") or payload.get("query"):
            cypher = _normalize_cypher(payload.get("cypher") or payload.get("query"))
            params = payload.get("params") or {}
        else:
            start = payload.get("start") or {}
            start_value = start.get("value") or payload.get("start_id")
            if not start_value:
                return [], {
                    "source_id": SERVER_ID,
                    "source_type": "query.graph",
                    "error": "Missing start.value or start_id",
                }

            prop = _sanitize_name(start.get("property", "id"), "property")
            rel = _sanitize_name(payload.get("rel", "REFERRED"), "relationship")
            depth = max(int(payload.get("depth", payload.get("max_depth", 1))), 1)
            path_expr = "" if depth == 1 else f"*1..{depth}"
            cypher = f"""
            MATCH (a:Customer)-[r:{rel}{path_expr}]->(b:Customer)
            WHERE a.{prop} = $start_value
            RETURN DISTINCT b.id AS id,
                            b.name AS name,
                            b.email AS email,
                            '{rel}' AS relationship
            """
            params = {"start_value": start_value}

        async with app.state.driver.session() as session:
            result = await session.run(cypher, params)
            records = await result.data()

        rows = [
            {
                "id": rec.get("id") or rec.get("b.id"),
                "name": rec.get("name") or rec.get("b.name"),
                "email": rec.get("email") or rec.get("b.email"),
                "relationship": rec.get("relationship", payload.get("rel", "REFERRED")),
            }
            for rec in records
        ]
        meta = {
            "source_id": SERVER_ID,
            "source_type": "query.graph",
            "raw_query": cypher.strip(),
            "row_count": len(rows),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }
        return rows, meta
    except HTTPException as exc:
        return [], {
            "source_id": SERVER_ID,
            "source_type": "query.graph",
            "error": exc.detail,
        }
    except Exception as exc:
        logger.exception("Graph MCP query failed")
        return [], {
            "source_id": SERVER_ID,
            "source_type": "query.graph",
            "error": str(exc),
        }


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
    if name != "query.graph":
        raise HTTPException(status_code=404, detail=f"Unknown tool {name}")
    items, meta = await run_graph_query(arguments)
    return normalize_legacy_result(items, meta, is_error=bool(meta.get("error"))).model_dump()


@app.post("/mcp/resources/read")
async def mcp_read_resource(payload: dict):
    uri = payload.get("uri")
    if uri == f"schema://{SERVER_ID}":
        return make_resource_result(uri, schema_payload()).model_dump()
    if uri == f"metadata://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "db_type": "graph", "transport": "http"}).model_dump()
    if uri == f"health://{SERVER_ID}":
        status = "ok" if getattr(app.state, "driver", None) else "error"
        return make_resource_result(uri, {"server_id": SERVER_ID, "status": status}).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown resource {uri}")


@app.post("/get_schema")
async def get_schema():
    return schema_payload()


@app.post("/traverse")
async def traverse(payload: TraversePayload):
    rows, meta = await run_graph_query(payload.model_dump(exclude_none=True))
    return {"rows": rows, "meta": meta, "data": {"items": rows, "meta": meta}}
