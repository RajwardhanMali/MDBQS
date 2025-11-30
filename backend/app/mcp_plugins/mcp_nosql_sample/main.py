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
    coll = app.state.db["orders"]
    # seed if empty
    if await coll.count_documents({}) == 0:
        docs = [
            {"order_id":"o1","customer_id":"cust1","amount":120.0,"order_date": "2025-10-01"},
            {"order_id":"o2","customer_id":"cust1","amount":30.0,"order_date": "2025-09-01"},
            {"order_id":"o3","customer_id":"cust2","amount":75.0,"order_date": "2025-10-05"},
        ]
        await coll.insert_many(docs)

@app.get("/schema")
async def get_schema():
    return {"mcp_id": "orders_mongo", "collections":[{"collection":"orders","fields":["order_id","customer_id","amount","order_date"]}]}

@app.post("/find")
async def find(payload: dict):
    filter_ = payload.get("filter", {})
    limit = int(payload.get("limit", 5))
    docs = []
    async for d in app.state.db["orders"].find(filter_).limit(limit):
        d["_id"] = str(d.get("_id"))
        docs.append(d)
    return {"docs": docs, "meta": {"source_id": "orders_mongo", "source_type": "NoSQL"}}
