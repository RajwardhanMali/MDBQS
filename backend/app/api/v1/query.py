# app/api/v1/query.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, List
import uuid
import logging

from app.services import planner, execution, fusion

logger = logging.getLogger("api.query")

router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    user_id: str
    nl_query: str
    context: Dict[str, Any] = {}


@router.post("/query")
async def query_endpoint(req: QueryRequest):
    request_id = str(uuid.uuid4())
    logger.info("Received /api/v1/query user=%s nl_query=%s", req.user_id, req.nl_query)

    # 1) PLAN (this is where your planner + Gemini/heuristics runs)
    plan_nodes = await planner.plan(req.nl_query)
    logger.info("Plan nodes: %s", [p.model_dump() for p in plan_nodes])

    # 2) EXECUTE
    exec_tasks = await execution.execute_plan(plan_nodes)
    logger.info(
        "Execution tasks: %s",
        [t.model_dump() for t in exec_tasks],
    )

    # 3) FUSE
    fused = fusion.fuse(exec_tasks, nl_query=req.nl_query)

    return {
        "request_id": request_id,
        "status": "COMPLETE",
        # "plan": [p.model_dump() for p in plan_nodes],
        # "execution_tasks": [t.model_dump() for t in exec_tasks],
        "fused_data": fused,
        "explain": fused.get("explain", []),
    }
