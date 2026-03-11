from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceMeta(BaseModel):
    source_id: str
    source_type: str
    last_updated: Optional[datetime] = None
    output_alias: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTask(BaseModel):
    task_id: str
    plan_node_id: str
    source: str
    native_query: str
    result: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[SourceMeta] = None


class PlanNode(BaseModel):
    id: str
    type: str
    subquery_nl: str
    capability: str
    target_candidates: List[str] = Field(default_factory=list)
    preferred: Optional[str] = None
    depends_on: Optional[str] = None
    status: str = "PLANNED"


class McpToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class McpResourceDescriptor(BaseModel):
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class McpServerDescriptor(BaseModel):
    server_id: str
    transport: str = "http"
    base_url: str
    capabilities: List[str] = Field(default_factory=list)
    tools: List[McpToolDescriptor] = Field(default_factory=list)
    resources: List[McpResourceDescriptor] = Field(default_factory=list)
    health: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class McpToolCall(BaseModel):
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class McpToolResultContent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: str = "json"
    json_payload: Dict[str, Any] = Field(default_factory=dict, alias="json")


class McpToolResult(BaseModel):
    is_error: bool = False
    content: List[McpToolResultContent] = Field(default_factory=list)
    structured_content: Dict[str, Any] = Field(default_factory=dict)


class McpResourceContent(BaseModel):
    uri: str
    mimeType: str = "application/json"
    text: str


class McpResourceReadResult(BaseModel):
    contents: List[McpResourceContent] = Field(default_factory=list)


class PlanStep(BaseModel):
    id: str
    description: str
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    depends_on: Optional[str] = None
    output_key: str
    optional: bool = False


class ExecutionResultSet(BaseModel):
    key: str
    server_id: str
    tool_name: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChatSessionRecord(BaseModel):
    session_id: str
    user_id: str
    title: str
    summary: str = ""
    active_server_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChatMessageRecord(BaseModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    answer_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class RunTraceRecord(BaseModel):
    trace_id: str
    session_id: str
    message_id: str
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    timings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class OrchestrationState(BaseModel):
    request_id: str
    session_id: str
    user_id: str
    user_message: str
    recent_messages: List[ChatMessageRecord] = Field(default_factory=list)
    session_summary: str = ""
    selected_server_ids: List[str] = Field(default_factory=list)
    available_servers: List[McpServerDescriptor] = Field(default_factory=list)
    source_resources: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    query_plan: List[PlanStep] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    result_sets: List[ExecutionResultSet] = Field(default_factory=list)
    answer: str = ""
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    explain: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)


class LangGraphState(OrchestrationState):
    nl_query: str = ""
    query_plan_legacy: List[PlanNode] = Field(default_factory=list)
    execution_tasks: List[ExecutionTask] = Field(default_factory=list)
    db_results: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    fused_data: Dict[str, Any] = Field(default_factory=dict)
    timing: Dict[str, Optional[datetime]] = Field(default_factory=dict)
