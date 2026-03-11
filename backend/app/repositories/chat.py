from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional

import asyncpg

from app.models.state import ChatMessageRecord, ChatSessionRecord, RunTraceRecord, utc_now

logger = logging.getLogger("repositories.chat")


class SessionRepository(ABC):
    @abstractmethod
    async def create_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSessionRecord]:
        raise NotImplementedError

    @abstractmethod
    async def update_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        raise NotImplementedError


class MessageRepository(ABC):
    @abstractmethod
    async def add_message(self, message: ChatMessageRecord) -> ChatMessageRecord:
        raise NotImplementedError

    @abstractmethod
    async def list_messages(self, session_id: str, limit: int = 20) -> List[ChatMessageRecord]:
        raise NotImplementedError


class TraceRepository(ABC):
    @abstractmethod
    async def add_trace(self, trace: RunTraceRecord) -> RunTraceRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_trace_by_message(self, message_id: str) -> Optional[RunTraceRecord]:
        raise NotImplementedError


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSessionRecord] = {}

    async def create_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSessionRecord]:
        return self._sessions.get(session_id)

    async def update_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        session.updated_at = utc_now()
        self._sessions[session.session_id] = session
        return session


class InMemoryMessageRepository(MessageRepository):
    def __init__(self) -> None:
        self._messages: list[ChatMessageRecord] = []

    async def add_message(self, message: ChatMessageRecord) -> ChatMessageRecord:
        self._messages.append(message)
        return message

    async def list_messages(self, session_id: str, limit: int = 20) -> List[ChatMessageRecord]:
        messages = [m for m in self._messages if m.session_id == session_id]
        return messages[-limit:]


class InMemoryTraceRepository(TraceRepository):
    def __init__(self) -> None:
        self._traces: dict[str, RunTraceRecord] = {}

    async def add_trace(self, trace: RunTraceRecord) -> RunTraceRecord:
        self._traces[trace.message_id] = trace
        return trace

    async def get_trace_by_message(self, message_id: str) -> Optional[RunTraceRecord]:
        return self._traces.get(message_id)


class PostgresSessionRepository(SessionRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        query = """
        INSERT INTO chat_sessions (session_id, user_id, title, summary, active_server_ids, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                session.session_id,
                session.user_id,
                session.title,
                session.summary,
                session.active_server_ids,
                session.created_at,
                session.updated_at,
            )
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSessionRecord]:
        query = "SELECT * FROM chat_sessions WHERE session_id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id)
        if not row:
            return None
        return ChatSessionRecord(**dict(row))

    async def update_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        session.updated_at = utc_now()
        query = """
        UPDATE chat_sessions
        SET title = $2, summary = $3, active_server_ids = $4, updated_at = $5
        WHERE session_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                session.session_id,
                session.title,
                session.summary,
                session.active_server_ids,
                session.updated_at,
            )
        return session


class PostgresMessageRepository(MessageRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def add_message(self, message: ChatMessageRecord) -> ChatMessageRecord:
        query = """
        INSERT INTO chat_messages (message_id, session_id, role, content, answer_payload, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                message.message_id,
                message.session_id,
                message.role,
                message.content,
                json.dumps(message.answer_payload),
                message.created_at,
            )
        return message

    async def list_messages(self, session_id: str, limit: int = 20) -> List[ChatMessageRecord]:
        query = """
        SELECT * FROM chat_messages
        WHERE session_id = $1
        ORDER BY created_at ASC
        LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, limit)
        return [
            ChatMessageRecord(
                **{
                    **dict(row),
                    "answer_payload": row["answer_payload"] if isinstance(row["answer_payload"], dict) else json.loads(row["answer_payload"] or "{}"),
                }
            )
            for row in rows
        ]


class PostgresTraceRepository(TraceRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def add_trace(self, trace: RunTraceRecord) -> RunTraceRecord:
        query = """
        INSERT INTO run_traces (trace_id, session_id, message_id, plan, tool_calls, errors, timings, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                trace.trace_id,
                trace.session_id,
                trace.message_id,
                json.dumps(trace.plan),
                json.dumps(trace.tool_calls),
                json.dumps(trace.errors),
                json.dumps(trace.timings),
                trace.created_at,
            )
        return trace

    async def get_trace_by_message(self, message_id: str) -> Optional[RunTraceRecord]:
        query = "SELECT * FROM run_traces WHERE message_id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, message_id)
        if not row:
            return None
        return RunTraceRecord(
            trace_id=row["trace_id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            plan=json.loads(row["plan"] or "[]"),
            tool_calls=json.loads(row["tool_calls"] or "[]"),
            errors=json.loads(row["errors"] or "[]"),
            timings=json.loads(row["timings"] or "{}"),
            created_at=row["created_at"],
        )


class ChatPersistence:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        trace_repo: TraceRepository,
    ) -> None:
        self.sessions = session_repo
        self.messages = message_repo
        self.traces = trace_repo


async def create_chat_persistence() -> ChatPersistence:
    mode = os.getenv("CHAT_STORAGE_MODE")
    dsn = os.getenv("POSTGRES_DSN")
    preferred = mode or ("postgres" if dsn else "memory")

    if preferred == "postgres" and dsn:
        try:
            pool = await asyncpg.create_pool(dsn)
            await _ensure_postgres_schema(pool)
            return ChatPersistence(
                PostgresSessionRepository(pool),
                PostgresMessageRepository(pool),
                PostgresTraceRepository(pool),
            )
        except Exception:
            logger.exception("Failed to initialize Postgres chat persistence; falling back to memory.")

    return ChatPersistence(
        InMemorySessionRepository(),
        InMemoryMessageRepository(),
        InMemoryTraceRepository(),
    )


async def _ensure_postgres_schema(pool: asyncpg.Pool) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        active_server_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
        message_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        answer_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
        created_at TIMESTAMPTZ NOT NULL
    );

    CREATE TABLE IF NOT EXISTS run_traces (
        trace_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
        message_id TEXT NOT NULL REFERENCES chat_messages(message_id) ON DELETE CASCADE,
        plan JSONB NOT NULL DEFAULT '[]'::JSONB,
        tool_calls JSONB NOT NULL DEFAULT '[]'::JSONB,
        errors JSONB NOT NULL DEFAULT '[]'::JSONB,
        timings JSONB NOT NULL DEFAULT '{}'::JSONB,
        created_at TIMESTAMPTZ NOT NULL
    );
    """
    async with pool.acquire() as conn:
        await conn.execute(ddl)
