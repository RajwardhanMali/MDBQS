# app/models/state.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class SourceMeta(BaseModel):
    source_id: str
    source_type: str
    last_updated: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = {}

class ExecutionTask(BaseModel):
    task_id: str
    plan_node_id: str
    source: str
    native_query: str
    result: List[Dict[str, Any]] = []
    meta: Optional[SourceMeta] = None

class PlanNode(BaseModel):
    id: str
    type: str
    subquery_nl: str
    capability: str
    target_candidates: List[str] = []
    preferred: Optional[str] = None
    depends_on: Optional[str] = None
    status: str = "PLANNED"

class LangGraphState(BaseModel):
    request_id: str
    user_id: str
    nl_query: str
    query_plan: List[PlanNode] = []
    execution_tasks: List[ExecutionTask] = []
    db_results: Dict[str, List[Dict[str, Any]]] = {}
    fused_data: Dict[str, Any] = {}
    status: str = "PENDING"
    timing: Dict[str, Optional[datetime]] = {}
