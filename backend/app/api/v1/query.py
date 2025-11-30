# app/api/v1/query.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
from app.services import planner, execution, fusion
from typing import Any, Dict

router = APIRouter(prefix="/api/v1", tags=["query"])

class QueryRequest(BaseModel):
    user_id: str
    nl_query: str
    context: Dict[str, Any] = {}

@router.post("/query")
async def query_endpoint(req: QueryRequest):
    request_id = str(uuid.uuid4())
    plan_nodes = await planner.plan(req.nl_query)
    # execute
    exec_tasks = await execution.execute_plan(plan_nodes)
    # fuse
    fused = fusion.fuse(exec_tasks)
    return {
        "request_id": request_id,
        "status": "COMPLETE",
        "fused_data": fused,
        "explain": fused.get("explain", [])
    }
