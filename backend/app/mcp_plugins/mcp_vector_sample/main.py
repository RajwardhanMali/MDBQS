import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.services.mcp_runtime import make_resource_result, normalize_legacy_result

try:
    from pymilvus import Collection, MilvusException, connections, utility

    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

load_dotenv()

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "customer_embeddings"
VECTOR_DIM = 3
SERVER_ID = "vector_customers"

app = FastAPI()

TOOLS = [
    {
        "name": "query.vector",
        "description": "Perform vector similarity search or fetch vector metadata by customer id/filter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string"},
                "embedding": {"type": "array"},
                "query_vector": {"type": "array"},
                "top_k": {"type": "integer"},
                "cust_id": {"type": "string"},
                "filter": {"type": "object"},
                "limit": {"type": "integer"},
                "fields": {"type": "array"},
                "exclude_ids": {"type": "array"},
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
    if not MILVUS_AVAILABLE:
        app.state.milvus_ready = False
        return
    try:
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        app.state.milvus_ready = True
    except Exception as exc:
        app.state.milvus_ready = False
        app.state.milvus_error = str(exc)


def schema_payload():
    return {
        "mcp_id": SERVER_ID,
        "db_type": "vector",
        "metadata": {"primary_tool": "query.vector"},
        "entities": [
            {
                "name": COLLECTION_NAME,
                "kind": "index",
                "semantic_tags": ["entity:customer", "similarity_index"],
                "default_id_field": "cust_id",
                "fields": [
                    {"name": "cust_id", "type": "text", "semantic_tags": ["id", "customer_id"]},
                    {"name": "embedding", "type": "vector", "semantic_tags": ["embedding", "similarity"]},
                    {"name": "name", "type": "text", "semantic_tags": ["name"]},
                    {"name": "email", "type": "text", "semantic_tags": ["email"]},
                ],
            }
        ],
    }


async def run_vector_query(payload: dict):
    if not MILVUS_AVAILABLE:
        return [], {"source_id": SERVER_ID, "source_type": "query.vector", "error": "pymilvus not installed"}
    if not getattr(app.state, "milvus_ready", False):
        return [], {"source_id": SERVER_ID, "source_type": "query.vector", "error": "Milvus connection not active"}

    collection_name = payload.get("collection", COLLECTION_NAME)

    try:
        if not utility.has_collection(collection_name):
            return [], {"source_id": SERVER_ID, "source_type": "query.vector", "error": f"Collection {collection_name} does not exist"}

        coll = Collection(collection_name)
        coll.load()

        metadata_lookup_fields = payload.get("fields") or ["cust_id", "name", "email", "embedding"]
        cust_id = payload.get("cust_id")
        filter_ = payload.get("filter") or {}
        if not cust_id and filter_.get("cust_id"):
            cust_id = filter_["cust_id"]

        if cust_id:
            results = coll.query(
                expr=f"cust_id == '{cust_id}'",
                output_fields=metadata_lookup_fields,
            )
            items = []
            for rec in results:
                item = {
                    "id": rec.get("cust_id"),
                    "cust_id": rec.get("cust_id"),
                    "name": rec.get("name"),
                    "email": rec.get("email"),
                }
                if "embedding" in rec:
                    item["embedding"] = rec.get("embedding")
                items.append(item)
            return items, {"source_id": SERVER_ID, "source_type": "query.vector", "row_count": len(items)}

        emb = payload.get("embedding") or payload.get("query_vector")
        top_k = int(payload.get("top_k", payload.get("limit", 3)))
        if not emb or len(emb) != VECTOR_DIM:
            return [], {"source_id": SERVER_ID, "source_type": "query.vector", "error": f"Embedding must have dimension {VECTOR_DIM}"}

        output_fields = ["cust_id", "name", "email"]
        requested_fields = payload.get("fields") or payload.get("include_fields")
        if requested_fields:
            output_fields = list({*output_fields, *requested_fields})

        search_limit = max(top_k + len(payload.get("exclude_ids") or []), top_k)
        results = coll.search(
            data=[emb],
            anns_field="embedding",
            param={"metric_type": "L2", "params": {"nprobe": 10}},
            limit=search_limit,
            output_fields=output_fields,
        )
        exclude_ids = set(payload.get("exclude_ids") or [])
        matches = []
        if results and len(results) > 0:
            for hit in results[0]:
                hit_id = hit.entity.get("cust_id")
                if hit_id in exclude_ids:
                    continue
                matches.append(
                    {
                        "id": hit_id,
                        "score": 1 / (1 + hit.distance),
                        "distance": hit.distance,
                        "metadata": {
                            "customer_id": hit_id,
                            "name": hit.entity.get("name"),
                            "email": hit.entity.get("email"),
                        },
                    }
                )
                if len(matches) >= top_k:
                    break
        return matches, {"source_id": SERVER_ID, "source_type": "query.vector", "row_count": len(matches)}
    except MilvusException as exc:
        return [], {"source_id": SERVER_ID, "source_type": "query.vector", "error": str(exc)}


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
    if name != "query.vector":
        raise HTTPException(status_code=404, detail=f"Unknown tool {name}")
    items, meta = await run_vector_query(arguments)
    return normalize_legacy_result(items, meta, is_error=bool(meta.get("error"))).model_dump()


@app.post("/mcp/resources/read")
async def mcp_read_resource(payload: dict):
    uri = payload.get("uri")
    if uri == f"schema://{SERVER_ID}":
        return make_resource_result(uri, schema_payload()).model_dump()
    if uri == f"metadata://{SERVER_ID}":
        return make_resource_result(uri, {"server_id": SERVER_ID, "db_type": "vector", "transport": "http"}).model_dump()
    if uri == f"health://{SERVER_ID}":
        status = "ok" if getattr(app.state, "milvus_ready", False) else "error"
        return make_resource_result(uri, {"server_id": SERVER_ID, "status": status}).model_dump()
    raise HTTPException(status_code=404, detail=f"Unknown resource {uri}")


@app.post("/get_schema")
async def get_schema():
    return schema_payload()


@app.post("/search")
async def search(payload: dict):
    matches, meta = await run_vector_query(payload)
    return {"matches": matches, "meta": meta}
