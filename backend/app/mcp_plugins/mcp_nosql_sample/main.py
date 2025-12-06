# app/mcp_plugins/mcp_nosql_sample/main.py
from dotenv import load_dotenv
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime

load_dotenv()
app = FastAPI()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mdbs")

@app.on_event("startup")
async def startup():
    app.state.client = AsyncIOMotorClient(MONGO_URI)
    app.state.db = app.state.client[MONGO_DB]

@app.post("/get_schema")
async def get_schema():
    return {
        "mcp_id": "orders_mongo",
        "db_type": "nosql",
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

@app.post("/find")
async def find(payload: dict):
    print(payload)
    filter_ = payload.get("filter", {})
    limit = int(payload.get("limit", 5))
    docs = []
    async for d in app.state.db["orders"].find(filter_).limit(limit):
        d["_id"] = str(d.get("_id"))
        docs.append(d)
    return {"docs": docs, "meta": {"source_id": "orders_mongo", "source_type": "NoSQL"}}
