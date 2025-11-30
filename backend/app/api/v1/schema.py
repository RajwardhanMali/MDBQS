# app/api/v1/schema.py
from fastapi import APIRouter, Query
from app.services.schema_index import schema_index

router = APIRouter(prefix="/api/v1", tags=["schema"])

@router.get("/schema/search")
async def schema_search(q: str = Query(..., description="Search query")):
    hits = schema_index.search_fields(q)
    return {"q": q, "hits": hits}
