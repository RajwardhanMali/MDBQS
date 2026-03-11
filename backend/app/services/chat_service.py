from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.llm.groq_client import GroqClient
from app.models.state import ChatMessageRecord, ChatSessionRecord, ExecutionResultSet, PlanStep, RunTraceRecord
from app.repositories.chat import ChatPersistence
from app.services import execution, fusion, mcp_manager, planner

logger = logging.getLogger("chat_service")

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    END = "__end__"
    StateGraph = None


class ChatService:
    def __init__(self, persistence: ChatPersistence, llm_client: Optional[GroqClient] = None) -> None:
        self.persistence = persistence
        self.llm_client = llm_client or GroqClient()
        self.graph = self._build_graph() if LANGGRAPH_AVAILABLE else None

    def _build_graph(self):
        graph = StateGraph(dict)
        graph.add_node("load_session", self._load_session)
        graph.add_node("load_recent_messages", self._load_recent_messages)
        graph.add_node("load_source_context", self._load_source_context)
        graph.add_node("plan_turn", self._plan_turn)
        graph.add_node("execute_plan", self._execute_plan)
        graph.add_node("synthesize_response", self._synthesize_response)
        graph.add_node("persist_turn", self._persist_turn)
        graph.set_entry_point("load_session")
        graph.add_edge("load_session", "load_recent_messages")
        graph.add_edge("load_recent_messages", "load_source_context")
        graph.add_edge("load_source_context", "plan_turn")
        graph.add_edge("plan_turn", "execute_plan")
        graph.add_edge("execute_plan", "synthesize_response")
        graph.add_edge("synthesize_response", "persist_turn")
        graph.add_edge("persist_turn", END)
        return graph.compile()

    async def create_session(
        self,
        user_id: str,
        title: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
    ) -> ChatSessionRecord:
        active_source_ids = source_ids or [server.server_id for server in mcp_manager.runtime.list_servers()]
        session = ChatSessionRecord(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title or "New chat session",
            active_server_ids=active_source_ids,
        )
        return await self.persistence.sessions.create_session(session)

    async def get_session(self, session_id: str) -> Optional[ChatSessionRecord]:
        return await self.persistence.sessions.get_session(session_id)

    async def list_messages(self, session_id: str, limit: int = 20) -> List[ChatMessageRecord]:
        return await self.persistence.messages.list_messages(session_id, limit=limit)

    async def get_trace(self, message_id: str) -> Optional[RunTraceRecord]:
        return await self.persistence.traces.get_trace_by_message(message_id)

    async def chat(
        self,
        session_id: str,
        user_id: str,
        message: str,
        source_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        state = {
            "request_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "user_message": message,
            "selected_server_ids": source_ids or [],
            "available_servers": [],
            "source_resources": {},
            "query_plan": [],
            "tool_calls": [],
            "result_sets": [],
            "answer": "",
            "citations": [],
            "explain": [],
            "status": "PENDING",
            "errors": [],
            "trace": {},
        }

        if self.graph:
            result = await self.graph.ainvoke(state)
        else:
            result = await self._run_without_langgraph(state)

        return {
            "session_id": session_id,
            "message_id": result["message_id"],
            "answer": result["answer"],
            "result_sets": [item.model_dump() if hasattr(item, "model_dump") else item for item in result["result_sets"]],
            "citations": result["citations"],
            "explain": result["explain"],
            "trace": result["trace"],
        }

    async def _run_without_langgraph(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for node in (
            self._load_session,
            self._load_recent_messages,
            self._load_source_context,
            self._plan_turn,
            self._execute_plan,
            self._synthesize_response,
            self._persist_turn,
        ):
            state.update(await node(state))
        return state

    async def _load_session(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        session = await self.persistence.sessions.get_session(state["session_id"])
        if not session:
            session = await self.create_session(
                user_id=state["user_id"],
                title=state["user_message"][:40] or "Chat session",
                source_ids=state.get("selected_server_ids") or None,
            )
            updated["session_id"] = session.session_id

        selected_server_ids = state.get("selected_server_ids") or session.active_server_ids
        updated["session"] = session
        updated["session_summary"] = session.summary
        updated["selected_server_ids"] = selected_server_ids
        return updated

    async def _load_recent_messages(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        messages = await self.persistence.messages.list_messages(state["session_id"], limit=8)
        updated["recent_messages"] = messages
        return updated

    async def _load_source_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        available_servers = [
            server
            for server in mcp_manager.runtime.list_servers()
            if not state["selected_server_ids"] or server.server_id in state["selected_server_ids"]
        ]
        source_resources: Dict[str, Dict[str, Any]] = {}
        for server in available_servers:
            schema = {}
            metadata = {}
            try:
                schema = await mcp_manager.runtime.read_json_resource(server.server_id, f"schema://{server.server_id}")
            except Exception:
                logger.exception("Failed to load schema resource for %s", server.server_id)
            try:
                metadata = await mcp_manager.runtime.read_json_resource(server.server_id, f"metadata://{server.server_id}")
            except Exception:
                logger.exception("Failed to load metadata resource for %s", server.server_id)
            source_resources[server.server_id] = {"schema": schema, "metadata": metadata}
        updated["available_servers"] = available_servers
        updated["source_resources"] = source_resources
        return updated

    async def _plan_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        steps = await planner.plan_steps(
            nl_query=state["user_message"],
            recent_messages=state.get("recent_messages", []),
            session_summary=state.get("session_summary", ""),
            selected_sources=state.get("selected_server_ids"),
        )
        updated["query_plan"] = steps
        return updated

    async def _execute_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        result_sets, tool_calls = await execution.execute_plan_steps(state.get("query_plan", []))
        updated["result_sets"] = result_sets
        updated["tool_calls"] = tool_calls
        return updated

    async def _synthesize_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        result_sets: List[ExecutionResultSet] = state.get("result_sets", [])
        explain = [
            f"{result_set.key} from {result_set.server_id} via {result_set.tool_name}"
            for result_set in result_sets
        ]
        for result_set in result_sets:
            if result_set.meta.get("error"):
                explain.append(
                    f"{result_set.key} failed on {result_set.server_id}: {result_set.meta['error']}"
                )
        answer = self.llm_client.summarize_answer(
            state["user_message"],
            [result.model_dump() for result in result_sets],
            explain,
        )
        trace = {
            "plan": [step.model_dump() if hasattr(step, "model_dump") else step for step in state.get("query_plan", [])],
            "tool_calls": state.get("tool_calls", []),
            "errors": state.get("errors", []),
        }
        generic = fusion.build_generic_response(result_sets, answer=answer, explain=explain, trace=trace)
        updated.update(generic)
        return updated

    async def _persist_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(state)
        user_message = ChatMessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=state["session_id"],
            role="user",
            content=state["user_message"],
        )
        await self.persistence.messages.add_message(user_message)

        assistant_payload = {
            "answer": state["answer"],
            "result_sets": [result.model_dump() if hasattr(result, "model_dump") else result for result in state["result_sets"]],
            "citations": state["citations"],
            "explain": state["explain"],
            "trace": state["trace"],
        }
        assistant_message = ChatMessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=state["session_id"],
            role="assistant",
            content=state["answer"],
            answer_payload=assistant_payload,
        )
        await self.persistence.messages.add_message(assistant_message)

        session: ChatSessionRecord = state["session"]
        session.summary = _build_summary(state.get("recent_messages", []), state["user_message"], state["answer"])
        if state.get("selected_server_ids"):
            session.active_server_ids = state["selected_server_ids"]
        await self.persistence.sessions.update_session(session)

        trace = RunTraceRecord(
            trace_id=str(uuid.uuid4()),
            session_id=state["session_id"],
            message_id=assistant_message.message_id,
            plan=[step.model_dump() if hasattr(step, "model_dump") else step for step in state.get("query_plan", [])],
            tool_calls=state.get("tool_calls", []),
            errors=state.get("errors", []),
            timings={},
        )
        await self.persistence.traces.add_trace(trace)
        updated["message_id"] = assistant_message.message_id
        return updated


def _build_summary(recent_messages: List[ChatMessageRecord], user_message: str, answer: str) -> str:
    snippets = [f"{msg.role}: {msg.content}" for msg in recent_messages[-4:]]
    snippets.extend([f"user: {user_message}", f"assistant: {answer}"])
    summary = " | ".join(snippets)
    return summary[:1500]
