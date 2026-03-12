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

    server_ids = list(mcp_manager.MCP_REGISTRY.keys()) or [
        server.server_id for server in mcp_manager.runtime.list_servers()
    ]
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
        sources = [s for s in sources if s["mcp_id"] in selected_sources]

    resp = await groq.plan_chat_query(
        nl_query=nl_query,
        sources=sources,
        recent_messages=recent_messages or [],
        session_summary=session_summary,
    )
    raw_steps = resp.get("plan", []) if isinstance(resp, dict) else []
    steps_out: List[PlanStep] = []
    normalized_ids: Dict[Any, str] = {}
    output_key_to_id: Dict[str, str] = {}

    for step in raw_steps:
        try:
            raw_id = step.get("id")
            step_id = _normalize_step_id(raw_id)
            normalized_ids[raw_id] = step_id

            # Accept both "output_key" (code convention) and "output_alias" (LLM prompt convention).
            output_key = step.get("output_key") or step.get("output_alias") or step_id
            if output_key:
                output_key_to_id[output_key] = step_id
            alias = step.get("output_alias")
            if alias and alias != output_key:
                output_key_to_id[alias] = step_id

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

            steps_out.append(
                PlanStep(
                    id=step_id,
                    description=step["description"],
                    server_id=server_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    depends_on=depends_on,
                    output_key=output_key,
                    optional=step.get("optional", False),
                )
            )
        except Exception:
            logger.exception("Invalid plan step from planner response: %s", json.dumps(step))

    steps_out = _repair_plan_steps(nl_query, steps_out, sources)

    # ── CRITICAL: re-number all step IDs to p1, p2, … ────────────────────────
    # The LLM sometimes emits semantic IDs like "cust_embedding" or "step_sql".
    # execution.py keys results_by_id by step.id, and embedding_from references
    # must match those keys exactly.  By canonicalising IDs here we guarantee
    # that "p1.embedding" always resolves against results_by_id["p1"].
    steps_out = _renumber_steps(steps_out)

    return steps_out


def _renumber_steps(steps: List[PlanStep]) -> List[PlanStep]:
    """
    Replace all step IDs with sequential p1, p2, … and rewrite every
    depends_on and embedding_from / *_from reference to match.
    """
    if not steps:
        return steps

    # Already canonical?  Skip the rewrite to avoid pointless churn.
    already_canonical = all(
        re.fullmatch(r"p\d+(_similarity)?", step.id) for step in steps
    )
    if already_canonical:
        return steps

    # Build old→new id mapping.
    id_map: Dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        id_map[step.id] = f"p{i}"

    logger.info("Renumbering step IDs: %s", id_map)

    def remap_ref(ref: str) -> str:
        """Remap the step-id prefix of a dotted reference."""
        if not ref:
            return ref
        parts = ref.split(".", 1)
        new_prefix = id_map.get(parts[0], parts[0])
        return f"{new_prefix}.{parts[1]}" if len(parts) > 1 else new_prefix

    def remap_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for k, v in args.items():
            if k.endswith("_from") and isinstance(v, str):
                out[k] = remap_ref(v)
            else:
                out[k] = v
        return out

    new_steps = []
    for step in steps:
        new_id = id_map[step.id]
        new_dep = id_map.get(step.depends_on, step.depends_on) if step.depends_on else None
        new_steps.append(
            PlanStep(
                id=new_id,
                description=step.description,
                server_id=step.server_id,
                tool_name=step.tool_name,
                arguments=remap_arguments(step.arguments),
                depends_on=new_dep,
                output_key=step.output_key,
                optional=step.optional,
            )
        )
    return new_steps


def _repair_plan_steps(
    nl_query: str, steps: List[PlanStep], sources: List[Dict[str, Any]]
) -> List[PlanStep]:
    q = nl_query.lower()

    def source_by_tool(tool_name: str) -> Optional[str]:
        for source in sources:
            if tool_name in source.get("tools", []):
                return source["mcp_id"]
        return None

    is_similarity_query = any(term in q for term in ["similar", "alike", "closest"])
    is_referral_query = any(
        term in q for term in ["referral", "referrals", "referal", "referals", "referred"]
    )

    # ── Similarity query repair ───────────────────────────────────────────────
    if is_similarity_query:
        customer_id = _extract_identifier(q)
        sql_server = source_by_tool("query.sql")
        vector_server = source_by_tool("query.vector")

        if sql_server and vector_server and customer_id:
            sql_steps = [s for s in steps if s.tool_name == "query.sql"]
            vector_steps = [s for s in steps if s.tool_name == "query.vector"]

            # Correct plan: exactly one SQL step that selects embedding, and one
            # vector step that depends on it.
            plan_is_correct = (
                len(sql_steps) == 1
                and len(vector_steps) == 1
                and "embedding" in json.dumps(sql_steps[0].arguments).lower()
                and vector_steps[0].depends_on == sql_steps[0].id
                and "embedding_from" in vector_steps[0].arguments
            )

            if not plan_is_correct:
                logger.info(
                    "Rewriting similarity plan for %r — %d sql steps, %d vector steps",
                    customer_id, len(sql_steps), len(vector_steps),
                )
                other_steps = [
                    s for s in steps if s.tool_name not in ("query.sql", "query.vector")
                ]
                return _build_similarity_steps(customer_id, sql_server, vector_server) + other_steps

    # ── Referral query repair ─────────────────────────────────────────────────
    if is_referral_query:
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


def _build_similarity_steps(
    customer_id: str, sql_server: str, vector_server: str
) -> List[PlanStep]:
    """
    Canonical two-step plan for a vector similarity search.
    IDs are already p1/p2 so _renumber_steps will leave them untouched.
    """
    return [
        PlanStep(
            id="p1",
            description=f"Fetch embedding for customer {customer_id}",
            server_id=sql_server,
            tool_name="query.sql",
            arguments={
                "query": "SELECT id, name, email, embedding FROM customers WHERE id = ? LIMIT 1",
                "params": {"id": customer_id},
            },
            depends_on=None,
            output_key="cust_embedding",
            optional=False,
        ),
        PlanStep(
            id="p2",
            description="Search for similar customers using the retrieved embedding",
            server_id=vector_server,
            tool_name="query.vector",
            arguments={
                "embedding_from": "p1.embedding",
                "top_k": 3,
                "exclude_ids": [customer_id],
            },
            depends_on="p1",
            output_key="similar_customers",
            # optional=True: if the SQL lookup finds no customer, skip silently
            # rather than showing a confusing error card.
            optional=True,
        ),
    ]


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
        for alias in ("sql", "statement", "sql_query", "text", "query_text"):
            if alias in normalized and "query" not in normalized:
                normalized["query"] = normalized.pop(alias)
        for params_alias in ("parameters", "values", "args"):
            if params_alias in normalized and "params" not in normalized:
                normalized["params"] = normalized.pop(params_alias)
        if "params" not in normalized:
            normalized["params"] = {}

    if tool_name == "query.graph":
        if "query" in normalized and "cypher" not in normalized:
            normalized["cypher"] = normalized.pop("query")

    if tool_name == "query.vector":
        if (
            "query_vector" in normalized
            and "embedding" not in normalized
            and "embedding_from" not in normalized
        ):
            query_vector = normalized.pop("query_vector")
            if isinstance(query_vector, str):
                m = re.fullmatch(r"\$\{(.+)\}", query_vector.strip())
                if m:
                    normalized["embedding_from"] = _normalize_reference(
                        m.group(1).strip(), normalized_ids, output_key_to_id
                    )
                else:
                    normalized["embedding"] = query_vector
            else:
                normalized["embedding"] = query_vector

        if "vector" in normalized and "embedding" not in normalized:
            vector_value = normalized.pop("vector")
            if isinstance(vector_value, str):
                m = re.fullmatch(r"\{\{(.+)\}\}", vector_value.strip())
                if m:
                    normalized["embedding_from"] = _normalize_reference(
                        m.group(1).strip(), normalized_ids, output_key_to_id
                    )
                else:
                    normalized["embedding"] = vector_value
            else:
                normalized["embedding"] = vector_value

        if "index" in normalized and "collection" not in normalized:
            normalized["collection"] = normalized.pop("index")

    for key, value in list(normalized.items()):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            normalized[key] = _normalize_reference(
                value[2:-2].strip(), normalized_ids, output_key_to_id
            )

    return normalized


def _normalize_reference(
    value: str, normalized_ids: Dict[Any, str], output_key_to_id: Dict[str, str]
) -> str:
    if "." in value:
        prefix, suffix = value.split(".", 1)
        normalized_prefix = _normalize_reference_target(prefix, normalized_ids, output_key_to_id)
        return f"{normalized_prefix}.{suffix}"
    normalized_prefix = _normalize_reference_target(value, normalized_ids, output_key_to_id)
    return f"{normalized_prefix}.embedding"


def _normalize_reference_target(
    value: Any, normalized_ids: Dict[Any, str], output_key_to_id: Dict[str, str]
) -> str:
    if value in normalized_ids:
        return normalized_ids[value]
    if isinstance(value, str) and value in output_key_to_id:
        return output_key_to_id[value]
    if str(value).isdigit():
        return _normalize_step_id(int(value))
    return str(value)
