# app/services/planner.py
import uuid
from app.core.llm.gemini_client import GeminiClient
from app.models.state import PlanNode
from typing import List, Dict, Any
from app.services.schema_index import schema_index

gemini = GeminiClient()

async def plan(nl_query: str) -> List[PlanNode]:
    resp = await gemini.plan_query(nl_query)
    plan_nodes = []
    for node in resp.get("plan", []):
        pn = PlanNode(
            id=node.get("id") or str(uuid.uuid4()),
            type=node.get("type", "lookup"),
            subquery_nl=node.get("subquery_nl", ""),
            capability=node.get("capability", "query.sql"),
            target_candidates=node.get("target_candidates", []),
            preferred=node.get("preferred")
        )
        plan_nodes.append(pn)
    # If no plan nodes, try a fallback: simple heuristic
    if not plan_nodes:
        if "customer" in nl_query.lower():
            plan_nodes.append(PlanNode(id="p1", type="lookup", subquery_nl="Find customer", capability="query.sql", preferred="sql_customers"))
    return plan_nodes
