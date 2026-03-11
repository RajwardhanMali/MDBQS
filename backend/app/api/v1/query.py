import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.models.state import ExecutionResultSet
from app.services import fusion

router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    user_id: str
    nl_query: str
    context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


@router.post("/query")
async def query_endpoint(req: QueryRequest, request: Request):
    chat_service = request.app.state.chat_service
    session_id = req.session_id
    if not session_id:
        session = await chat_service.create_session(
            user_id=req.user_id,
            title=req.nl_query[:40] or "Query session",
            source_ids=req.context.get("source_ids"),
        )
        session_id = session.session_id

    response = await chat_service.chat(
        session_id=session_id,
        user_id=req.user_id,
        message=req.nl_query,
        source_ids=req.context.get("source_ids"),
    )
    result_sets = [ExecutionResultSet(**item) for item in response["result_sets"]]
    fused = fusion.compatibility_fused_data(result_sets, nl_query=req.nl_query)
    return {
        "request_id": str(uuid.uuid4()),
        "status": "COMPLETE",
        "fused_data": fused,
        "explain": response["explain"],
        "answer": response["answer"],
        "result_sets": response["result_sets"],
        "citations": response["citations"],
        "session_id": response["session_id"],
        "message_id": response["message_id"],
    }
