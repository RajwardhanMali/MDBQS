# app/services/planner.py
import uuid
import json
import logging
from typing import List, Dict, Any
from app.core.llm.gemini_client import GeminiClient
from app.models.state import PlanNode
from app.services.schema_index import schema_index
from app.services import mcp_manager

logger = logging.getLogger("planner")
logger.setLevel(logging.INFO)

# Initialize Gemini client (mock_mode=False to use actual Gemini if configured)
gemini = GeminiClient(api_key=None, mock_mode=False)

async def plan(nl_query: str) -> List[PlanNode]:
    """
    Create a plan for the natural language query.
    Steps:
      1) Get schema hints from schema_index (top fields & mcp ids)
      2) Call GeminiClient.plan_query(...) to get a structured plan (or fallback)
      3) Validate and enrich plan nodes: map capabilities -> preferred MCP ids
      4) Return list[PlanNode]
    """
    # 1) schema hints
    # use schema_index.search_fields with top-k tokens from query for hints
    # very simple: ask schema_index for fields matching important tokens
    hints = []
    # take a few keywords (split, remove stopwords minimal)
    tokens = [t for t in nl_query.lower().split() if len(t) > 2]
    seen_mcp = set()
    for tok in tokens[:6]:
        hits = schema_index.search_fields(tok, top_k=3)
        for h in hits:
            mcp = h.get("mcp")
            if mcp and mcp not in seen_mcp:
                seen_mcp.add(mcp)
                hints.append({"mcp_id": mcp, "field": h.get("field"), "parent": h.get("parent")})
    logger.info("Schema hints for planner: %s", hints)

    # 2) call LLM planner
    resp = await gemini.plan_query(nl_query, schema_hints=hints)
    raw_plan = resp.get("plan", []) if isinstance(resp, dict) else []
    logger.info("Raw plan from Gemini/heuristic: %s", json.dumps(raw_plan, indent=2))

    plan_nodes = []
    id_map = {}  # map returned id to PlanNode id
    # prefer mapping from capability -> registered MCP ids
    capability_to_mcp = _map_capability_to_mcp()

    for node in raw_plan:
        # basic validation
        capability = node.get("capability")
        if capability not in {"query.sql","query.document","query.graph","query.vector"}:
            logger.warning("Skipping unsupported capability: %s", capability)
            continue
        nid = node.get("id") or f"p{len(plan_nodes)+1}"
        preferred = node.get("preferred") or capability_to_mcp.get(capability)
        pn = PlanNode(
            id=nid,
            type=node.get("intent","lookup"),
            subquery_nl=node.get("native_query", node.get("intent","")),
            capability=capability,
            target_candidates=[],
            preferred=preferred,
            depends_on=node.get("depends_on")
        )
        plan_nodes.append(pn)
        id_map[nid] = pn

    # If no nodes returned, fallback: if schema hints suggest SQL, create SQL node
    if not plan_nodes:
        logger.info("No plan nodes returned by LLM; using fallback heuristics.")
        # fallback uses heuristic planner to generate conservative SQL lookup
        fallback = gemini._heuristic_plan(nl_query, hints)
        for node in fallback:
            capability = node.get("capability")
            preferred = capability_to_mcp.get(capability)
            pn = PlanNode(
                id=node.get("id","p1"),
                type=node.get("intent","lookup"),
                subquery_nl=node.get("native_query",""),
                capability=capability,
                preferred=preferred
            )
            plan_nodes.append(pn)

    logger.info("Final plan nodes: %s", [p.model_dump() for p in plan_nodes])
    return plan_nodes

def _map_capability_to_mcp() -> Dict[str,str]:
    """
    Map capabilities to available registered MCP ids (preferred).
    This uses the in-memory mcp_manager registry to find best candidate.
    """
    mapping = {}
    registry = mcp_manager.MCP_REGISTRY
    for mcp_id, manifest in registry.items():
        caps = manifest.get("capabilities", [])
        for c in caps:
            # Normalize: convert "query.sql" to "query.sql"
            mapping[c] = mcp_id
    # Provide reasonable defaults if not present
    if "query.sql" not in mapping:
        # try common ids
        for candidate in ["sql_customers","postgres","mysql","sql_db"]:
            if candidate in registry:
                mapping["query.sql"] = candidate
                break
    return mapping
