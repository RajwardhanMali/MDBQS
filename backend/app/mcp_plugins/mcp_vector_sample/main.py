# app/mcp_plugins/mcp_vector_sample/main.py
from dotenv import load_dotenv
from fastapi import FastAPI
import numpy as np
import os
import json

load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup():
    # seed simple embeddings for customer ids
    # store dict: id -> (embedding, metadata)
    app.state.index = {
        "cust1": (np.array([0.1, 0.2, 0.3]), {"customer_id":"cust1","name":"Alice Kumar","email":"alice@example.com"}),
        "cust2": (np.array([0.0, 0.2, 0.7]), {"customer_id":"cust2","name":"Bob Singh","email":"bob@example.com"}),
        "cust3": (np.array([0.9, 0.1, 0.0]), {"customer_id":"cust3","name":"Charlie Rao","email":"charlie@example.com"}),
    }

@app.get("/schema")
async def get_schema():
    return {"mcp_id":"vector_customers","indices":["customer_embeddings"],"metadata_fields":["customer_id","name","email"]}

@app.post("/search")
async def search(payload: dict):
    emb = payload.get("embedding")
    top_k = int(payload.get("top_k", 2))
    if not emb:
        return {"matches": [], "meta": {"source_id": "vector_customers"}}
    vec = np.array(emb)
    results = []
    for cid, (e, meta) in app.state.index.items():
        score = float(np.dot(vec, e) / (np.linalg.norm(vec) * np.linalg.norm(e) + 1e-9))
        results.append((cid, score, meta))
    results.sort(key=lambda x: -x[1])
    matches = [{"id": r[0], "score": r[1], "metadata": r[2]} for r in results[:top_k]]
    return {"matches": matches, "meta":{"source_id":"vector_customers"}}

@app.post("/get_metadata")
async def get_metadata(payload: dict):
    cid = payload.get("customer_id")
    if not cid:
        return {"embedding": None}
    rec = app.state.index.get(cid)
    if not rec:
        return {"embedding": None}
    emb, meta = rec
    return {"embedding": emb.tolist(), "metadata": meta}
