# app/mcp_plugins/mcp_sql_sample/main.py
from fastapi import FastAPI
import asyncpg
import os
import json
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_DSN")

@app.on_event("startup")
async def startup():
    print(DATABASE_URL)
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)
    # seed table if not present
    async with app.state.pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            embedding JSONB
        )
        """)
        # insert sample records if not present
        rec = await conn.fetchrow("SELECT id FROM customers LIMIT 1")
        if not rec:
            await conn.execute("INSERT INTO customers(id,name,email,embedding) VALUES($1,$2,$3,$4)",
                               "cust1","Alice Kumar","alice@example.com", json.dumps([0.1,0.2,0.3]))
            await conn.execute("INSERT INTO customers(id,name,email,embedding) VALUES($1,$2,$3,$4)",
                               "cust2","Bob Singh","bob@example.com", json.dumps([0.0,0.2,0.7]))

@app.get("/schema")
async def get_schema():
    return {"mcp_id": "sql_customers", "tables": [{"table":"customers","fields":["id","name","email","embedding"]}]}

@app.post("/execute_sql")
async def execute_sql(payload: dict):
    query = payload.get("query")
    # VERY SIMPLE: only allow SELECT for MVP
    if not query.strip().lower().startswith("select"):
        return {"rows": [], "meta": {"error": "Only SELECT allowed in MVP"}}
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(query)
        # convert to dicts
        result = [dict(r) for r in rows]
        return {"rows": result, "meta": {"source_id": "sql_customers", "source_type": "SQL"}}
