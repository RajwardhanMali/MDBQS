from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    message: str
    source_ids: List[str] = Field(default_factory=list)


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    chat_service = request.app.state.chat_service
    return await chat_service.chat(
        session_id=req.session_id,
        user_id=req.user_id,
        message=req.message,
        source_ids=req.source_ids,
    )


class SessionCreateRequest(BaseModel):
    user_id: str
    title: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)


@router.post("/sessions")
async def create_session(req: SessionCreateRequest, request: Request):
    chat_service = request.app.state.chat_service
    session = await chat_service.create_session(
        user_id=req.user_id,
        title=req.title,
        source_ids=req.source_ids or None,
    )
    return session.model_dump()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    chat_service = request.app.state.chat_service
    session = await chat_service.get_session(session_id)
    return session.model_dump() if session else {"detail": "not found"}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    chat_service = request.app.state.chat_service
    messages = await chat_service.list_messages(session_id)
    return {"session_id": session_id, "messages": [message.model_dump() for message in messages]}


@router.get("/runs/{message_id}")
async def get_run_trace(message_id: str, request: Request):
    chat_service = request.app.state.chat_service
    trace = await chat_service.get_trace(message_id)
    return trace.model_dump() if trace else {"detail": "not found"}
