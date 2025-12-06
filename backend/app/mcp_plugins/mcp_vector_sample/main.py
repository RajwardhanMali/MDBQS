# app/mcp_plugins/mcp_vector_sample/main.py
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import os

# --- Import Milvus components ---
try:
    from pymilvus import (
        connections,
        utility,
        Collection,
        MilvusException,
    )
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    print("WARNING: pymilvus not installed. Vector operations will fail.")
# --------------------------------

load_dotenv()

# --- Configuration ---
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "customer_embeddings"
VECTOR_DIM = 3  # must match your seeding script

app = FastAPI()


@app.on_event("startup")
async def startup():
    """Initializes the Milvus connection on startup."""
    if not MILVUS_AVAILABLE:
        app.state.milvus_ready = False
        return

    try:
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        app.state.milvus_ready = True
    except Exception as e:
        print(f"Milvus connection error: {e}")
        app.state.milvus_ready = False


# --------------------------------------------------------------------
# NEW: /get_schema endpoint used by planner via mcp_manager.call_execute
# --------------------------------------------------------------------
@app.post("/get_schema")
async def get_schema():
    return {
        "mcp_id": "vector_customers",
        "db_type": "vector",
        "entities": [
            {
                "name": "customer_embeddings",
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

# --------------------------------------------------------------------
# Vector similarity search
# --------------------------------------------------------------------
@app.post("/search")
async def search(payload: dict):
    print(payload)
    if not MILVUS_AVAILABLE:
        raise HTTPException(status_code=500, detail="pymilvus not installed in this environment.")

    if not getattr(app.state, "milvus_ready", False):
        err = getattr(app.state, "milvus_error", None)
        raise HTTPException(
            status_code=503,
            detail=f"Milvus connection not active. Last error: {err}",
        )

    emb = payload.get("embedding")
    top_k = int(payload.get("top_k", 3))

    if not emb or len(emb) != VECTOR_DIM:
        raise HTTPException(
            status_code=400,
            detail=f"Embedding vector must be provided and have dimension {VECTOR_DIM}. Got: {len(emb) if emb else 'None'}",
        )

    try:
        if not utility.has_collection(COLLECTION_NAME):
            raise HTTPException(
                status_code=500,
                detail=f"Milvus collection '{COLLECTION_NAME}' does not exist.",
            )

        coll = Collection(COLLECTION_NAME)
        coll.load()  # <- FIXED: no is_loaded

        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10},
        }

        results = coll.search(
            data=[emb],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["cust_id", "name", "email"],
        )

        matches = []
        if results and len(results) > 0:
            for hit in results[0]:
                matches.append(
                    {
                        "id": hit.entity.get("cust_id"),
                        "score": 1 / (1 + hit.distance),
                        "distance": hit.distance,
                        "metadata": {
                            "customer_id": hit.entity.get("cust_id"),
                            "name": hit.entity.get("name"),
                            "email": hit.entity.get("email"),
                        },
                    }
                )

        return {
            "matches": matches,
            "meta": {"source_id": "vector_customers", "source_type": "vector"},
        }

    except HTTPException:
        raise
    except MilvusException as e:
        print(f"Milvus search execution error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Milvus search execution error: {e}",
        )
    except Exception as e:
        print(f"Unexpected Milvus error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Milvus error: {e}",
        )


@app.post("/get_metadata")
async def get_metadata(payload: dict):
    cid = payload.get("customer_id")
    if not cid:
        return {"embedding": None, "metadata": None}

    if not MILVUS_AVAILABLE:
        raise HTTPException(status_code=500, detail="pymilvus not installed in this environment.")

    if not getattr(app.state, "milvus_ready", False):
        err = getattr(app.state, "milvus_error", None)
        raise HTTPException(
            status_code=503,
            detail=f"Milvus connection not active. Last error: {err}",
        )

    try:
        if not utility.has_collection(COLLECTION_NAME):
            raise HTTPException(
                status_code=500,
                detail=f"Milvus collection '{COLLECTION_NAME}' does not exist.",
            )

        coll = Collection(COLLECTION_NAME)
        coll.load()  # <- FIXED: no is_loaded

        results = coll.query(
            expr=f"cust_id == '{cid}'",
            output_fields=["cust_id", "name", "email", "embedding"],
        )
        if not results:
            return {"embedding": None, "metadata": None}

        rec = results[0]
        return {
            "embedding": rec.get("embedding"),
            "metadata": {
                "customer_id": rec.get("cust_id"),
                "name": rec.get("name"),
                "email": rec.get("email"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Metadata fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Metadata fetch error: {e}")
