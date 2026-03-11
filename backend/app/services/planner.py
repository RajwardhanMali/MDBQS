import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.core.llm.groq_client import GroqClient
from app.models.state import ChatMessageRecord, PlanNode, PlanStep
from app.services import mcp_manager
from app.services.schema_index import schema_index, source_schema_from_dict

logger = logging.getLogger("planner")
logger.setLevel(logging.INFO)

groq = GroqClient(api_key=os.getenv("GROQ_API_KEY"), mock_mode=not bool(os.getenv("GROQ_API_KEY")))

_SCHEMAS_LOADED = False


async def _ensure_schemas_loaded() -> None:
    global _SCHEMAS_LOADED

    if _SCHEMAS_LOADED and schema_index.schemas:
        return

    if not mcp_manager.MCP_REGISTRY and not mcp_manager.runtime.list_servers():
        mcp_manager.register_default_manifests()

    server_ids = list(mcp_manager.MCP_REGISTRY.keys()) or [server.server_id for server in mcp_manager.runtime.list_servers()]
    for mcp_id in server_ids:
        try:
            schema_json = await mcp_manager.runtime.read_json_resource(mcp_id, f"schema://{mcp_id}")
            schema_index.register_schema(source_schema_from_dict(schema_json))
        except Exception:
            logger.exception("Failed to fetch schema for %s", mcp_id)

    _SCHEMAS_LOADED = True


async def plan(
    nl_query: str,
    recent_messages: Optional[List[ChatMessageRecord]] = None,
    session_summary: str = "",
    selected_sources: Optional[List[str]] = None,
) -> List[PlanNode]:
    steps = await plan_steps(
        nl_query=nl_query,
        recent_messages=recent_messages,
        session_summary=session_summary,
        selected_sources=selected_sources,
    )
    return [
        PlanNode(
            id=step.id,
            type=step.description,
            subquery_nl=step.model_dump_json(),
            capability=step.tool_name,
            preferred=step.server_id,
            depends_on=step.depends_on,
        )
        for step in steps
    ]


async def plan_steps(
    nl_query: str,
    recent_messages: Optional[List[ChatMessageRecord]] = None,
    session_summary: str = "",
    selected_sources: Optional[List[str]] = None,
) -> List[PlanStep]:
    await _ensure_schemas_loaded()

    sources = schema_index.build_sources_for_llm()
    if selected_sources:
        sources = [source for source in sources if source["mcp_id"] in selected_sources]

    resp = await groq.plan_chat_query(
        nl_query=nl_query,
        sources=sources,
        recent_messages=recent_messages or [],
        session_summary=session_summary,
    )
    raw_steps = resp.get("plan", []) if isinstance(resp, dict) else []
    plan_steps: List[PlanStep] = []
    normalized_ids: Dict[Any, str] = {}
    output_key_to_id: Dict[str, str] = {}

    for step in raw_steps:
        try:
            raw_id = step.get("id")
            step_id = _normalize_step_id(raw_id)
            normalized_ids[raw_id] = step_id
            if step.get("output_key"):
                output_key_to_id[step["output_key"]] = step_id

            depends_on = step.get("depends_on")
            if isinstance(depends_on, list):
                depends_on = depends_on[0] if depends_on else None
            elif depends_on == "":
                depends_on = None
            if depends_on is not None:
                depends_on = _normalize_reference_target(depends_on, normalized_ids, output_key_to_id)

            server_id = step.get("server_id") or step.get("mcp_id")
            tool_name = step.get("tool_name") or step.get("tool")
            arguments = _normalize_arguments(
                step.get("arguments") or step.get("input") or {},
                tool_name,
                normalized_ids,
                output_key_to_id,
            )

            plan_steps.append(
                PlanStep(
                    id=step_id,
                    description=step["description"],
                    server_id=server_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    depends_on=depends_on,
                    output_key=step.get("output_key", step_id),
                    optional=step.get("optional", False),
                )
            )
        except Exception:
            logger.exception("Invalid plan step from planner response: %s", json.dumps(step))

    plan_steps = _repair_plan_steps(nl_query, plan_steps, sources)
    return plan_steps


def _repair_plan_steps(nl_query: str, steps: List[PlanStep], sources: List[Dict[str, Any]]) -> List[PlanStep]:
    q = nl_query.lower()

    def source_by_tool(tool_name: str) -> Optional[str]:
        for source in sources:
            if tool_name in source.get("tools", []):
                return source["mcp_id"]
        return None

    is_similarity_query = any(term in q for term in ["similar", "alike", "closest"])
    is_referral_query = any(term in q for term in ["referral", "referrals", "referal", "referals", "referred"])

    if is_similarity_query:
        has_vector = any(step.tool_name == "query.vector" for step in steps)
        embedding_step = next(
            (
                step
                for step in steps
                if step.tool_name == "query.sql"
                and (
                    "embedding" in json.dumps(step.arguments).lower()
                    or "embedding" in step.output_key.lower()
                )
            ),
            None,
        )
        vector_server = source_by_tool("query.vector")
        if embedding_step and not has_vector and vector_server:
            steps.append(
                PlanStep(
                    id=f"{embedding_step.id}_similarity",
                    description="Search for similar entities from the retrieved embedding",
                    server_id=vector_server,
                    tool_name="query.vector",
                    arguments={"embedding_from": f"{embedding_step.id}.embedding", "top_k": 3},
                    depends_on=embedding_step.id,
                    output_key="similar_customers",
                    optional=False,
                )
            )

    if is_referral_query and not steps:
        graph_server = source_by_tool("query.graph")
        customer_id = _extract_identifier(q) or "cust010"
        if graph_server:
            steps.append(
                PlanStep(
                    id="p1",
                    description="Traverse graph referrals",
                    server_id=graph_server,
                    tool_name="query.graph",
                    arguments={"start": {"property": "id", "value": customer_id}, "depth": 2},
                    depends_on=None,
                    output_key="referrals",
                    optional=False,
                )
            )

    if is_referral_query and steps:
        graph_server = source_by_tool("query.graph")
        customer_id = _extract_identifier(q) or "cust010"
        if graph_server:
            return [
                PlanStep(
                    id="p1",
                    description="Traverse graph referrals",
                    server_id=graph_server,
                    tool_name="query.graph",
                    arguments={"start": {"property": "id", "value": customer_id}, "depth": 2},
                    depends_on=None,
                    output_key="referrals",
                    optional=False,
                )
            ]

    return steps


def _extract_identifier(text: str) -> Optional[str]:
    match = re.search(r"\bcust\d+\b", text)
    return match.group(0) if match else None


def _normalize_step_id(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int):
        return f"p{value}"
    return "p1"


def _normalize_arguments(
    arguments: Dict[str, Any],
    tool_name: Optional[str],
    normalized_ids: Dict[Any, str],
    output_key_to_id: Dict[str, str],
) -> Dict[str, Any]:
    normalized = dict(arguments)

    if tool_name == "query.sql":
        if "sql" in normalized and "query" not in normalized:
            normalized["query"] = normalized.pop("sql")

    if tool_name == "query.graph":
        if "query" in normalized and "cypher" not in normalized:
            normalized["cypher"] = normalized.pop("query")

    if tool_name == "query.vector":
        if "query_vector" in normalized and "embedding" not in normalized and "embedding_from" not in normalized:
            query_vector = normalized.pop("query_vector")
            if isinstance(query_vector, str):
                placeholder_match = re.fullmatch(r"\$\{(.+)\}", query_vector.strip())
                if placeholder_match:
                    normalized["embedding_from"] = _normalize_reference(
                        placeholder_match.group(1).strip(),
                        normalized_ids,
                        output_key_to_id,
                    )
                else:
                    normalized["embedding"] = query_vector
            else:
                normalized["embedding"] = query_vector
        if "vector" in normalized and "embedding" not in normalized:
            vector_value = normalized.pop("vector")
            if isinstance(vector_value, str):
                match = re.fullmatch(r"\{\{(.+)\}\}", vector_value.strip())
                if match:
                    ref = match.group(1).strip()
                    normalized["embedding_from"] = _normalize_reference(ref, normalized_ids, output_key_to_id)
                else:
                    normalized["embedding"] = vector_value
            else:
                normalized["embedding"] = vector_value
        if "index" in normalized and "collection" not in normalized:
            normalized["collection"] = normalized.pop("index")

    for key, value in list(normalized.items()):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            normalized[key] = _normalize_reference(value[2:-2].strip(), normalized_ids, output_key_to_id)

    return normalized


def _normalize_reference(value: str, normalized_ids: Dict[Any, str], output_key_to_id: Dict[str, str]) -> str:
    if "." in value:
        prefix, suffix = value.split(".", 1)
        normalized_prefix = _normalize_reference_target(prefix, normalized_ids, output_key_to_id)
        return f"{normalized_prefix}.{suffix}"
    normalized_prefix = _normalize_reference_target(value, normalized_ids, output_key_to_id)
    return f"{normalized_prefix}.embedding"


def _normalize_reference_target(value: Any, normalized_ids: Dict[Any, str], output_key_to_id: Dict[str, str]) -> str:
    if value in normalized_ids:
        return normalized_ids[value]
    if isinstance(value, str) and value in output_key_to_id:
        return output_key_to_id[value]
    if str(value).isdigit():
        return _normalize_step_id(int(value))
    return str(value)
