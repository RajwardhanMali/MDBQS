# app/services/planner.py
import json
import logging
from typing import List, Dict, Any

from app.core.llm.gemini_client import GeminiClient
from app.models.state import PlanNode
from app.services.schema_index import schema_index, source_schema_from_dict
from app.services import mcp_manager

logger = logging.getLogger("planner")
logger.setLevel(logging.INFO)

gemini = GeminiClient(api_key=None, mock_mode=False)

_SCHEMAS_LOADED = False  # module-level flag


async def _ensure_schemas_loaded() -> None:
    """
    Lazy-load schemas from all registered MCPs into schema_index.

    If MCP_REGISTRY is empty (common when running scripts like test.py
    without FastAPI startup), we also register default MCP manifests here.
    """
    global _SCHEMAS_LOADED

    if _SCHEMAS_LOADED and schema_index.schemas:
        return

    # If no MCPs registered yet, register some defaults (for local dev)
    if not mcp_manager.MCP_REGISTRY:
        logger.info("MCP_REGISTRY is empty; registering default local MCPs...")
        DEFAULT_MCPS = [
            {"id": "sql_customers", "host": "http://localhost:8001", "capabilities": ["query.sql"]},
            {"id": "orders_mongo", "host": "http://localhost:8002", "capabilities": ["query.document"]},
            {"id": "graph_referrals", "host": "http://localhost:8003", "capabilities": ["query.graph"]},
            {"id": "vector_customers", "host": "http://localhost:8004", "capabilities": ["query.vector"]},
        ]
        for manifest in DEFAULT_MCPS:
            mcp_manager.register_mcp(manifest)

    if not mcp_manager.MCP_REGISTRY:
        logger.warning("MCP_REGISTRY still empty; no schemas to load.")
        _SCHEMAS_LOADED = True
        return

    logger.info("Loading schemas from MCPs into schema_index...")
    for mcp_id in mcp_manager.MCP_REGISTRY.keys():
        try:
            logger.info("Fetching schema from MCP %s", mcp_id)
            schema_json = await mcp_manager.call_execute(mcp_id, "get_schema", {})
            logger.info("Schema from %s: %s", mcp_id, schema_json)
            schema = source_schema_from_dict(schema_json)
            schema_index.register_schema(schema)
        except Exception as e:
            logger.exception("Failed to fetch schema for %s: %s", mcp_id, e)

    _SCHEMAS_LOADED = True
    logger.info("Schema loading complete. Schemas: %s", list(schema_index.schemas.keys()))


def _capability_from_tool(db_type: str, tool: str) -> str:
    """
    Map (db_type, tool) to the legacy capability string used by PlanNode.
    """
    tool = (tool or "").lower()
    db_type = (db_type or "").lower()

    if tool == "execute_sql" or db_type == "sql":
        return "query.sql"
    if tool == "find" or db_type == "nosql":
        return "query.document"
    if tool == "traverse" or db_type == "graph":
        return "query.graph"
    if tool == "search" or db_type == "vector":
        return "query.vector"
    return "query.sql"


async def plan(nl_query: str) -> List[PlanNode]:
    """
    Dynamic planner:
    1) Ensure schemas are loaded from MCPs (lazy).
    2) Build 'sources' description for Gemini.
    3) Ask Gemini for a JSON list of steps (LLM-native plan).
    4) Map each step into a PlanNode (store full step JSON in subquery_nl).
    """
    # 1) make sure we have schema metadata
    if not schema_index.schemas:
        await _ensure_schemas_loaded()

    # 2) build sources for LLM
    sources = schema_index.build_sources_for_llm()
    logger.info("Planner LLM sources: %s", json.dumps(sources, indent=2))

    # Also build simple candidates for heuristic fallback
    candidates = schema_index.discover_candidates(nl_query)

    # 3) get plan from Gemini / heuristic
    resp = await gemini.plan_query(nl_query, entity_candidates=candidates, sources=sources)
    raw_steps = resp.get("plan", []) if isinstance(resp, dict) else []
    logger.info("LLM plan steps: %s", json.dumps(raw_steps, indent=2))

    plan_nodes: List[PlanNode] = []

    for step in raw_steps:
        try:
            step_id = step["id"]
            mcp_id = step["mcp_id"]
            db_type = step.get("db_type", "")
            tool = step.get("tool", "")
            desc = step.get("description") or step.get("intent") or "step"

            capability = _capability_from_tool(db_type, tool)

            # Store the entire step JSON in subquery_nl so execution can see tool/input/etc.
            step_json = json.dumps(step)

            pn = PlanNode(
                id=step_id,
                type=desc,
                subquery_nl=step_json,
                capability=capability,
                target_candidates=[],
                preferred=mcp_id,
                depends_on=step.get("depends_on"),
            )
            plan_nodes.append(pn)
        except Exception as e:
            logger.exception("Invalid plan step from LLM, skipping: %s", e)

    logger.info("Final PlanNodes: %s", [p.model_dump() for p in plan_nodes])
    return plan_nodes
