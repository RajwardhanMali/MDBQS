import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.models.state import ExecutionResultSet, ExecutionTask, PlanNode, PlanStep, SourceMeta
from app.services import mcp_manager

logger = logging.getLogger("execution")
logger.setLevel(logging.INFO)

_TMPL_RE = re.compile(r"\{\{(.+?)\}\}")


def _resolve_ref(results_by_id: Dict[str, ExecutionResultSet], ref: str) -> Any:
    """Return a single value from the first row of a prior result set."""
    if not ref:
        return None

    parts = ref.split(".")
    result_set = results_by_id.get(parts[0])
    if not result_set or not result_set.items:
        return None

    value: Any = result_set.items[0]
    for key in parts[1:]:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _should_resolve_as_list(
    argument_name: str,
    ref: str,
    results_by_id: Dict[str, ExecutionResultSet],
) -> bool:
    if "[*]" in ref:
        return True

    lowered_name = argument_name.lower()
    if lowered_name.endswith("ids_from") or lowered_name.endswith("list_from"):
        return True

    parts = ref.replace("[*]", "").split(".")
    result_set = results_by_id.get(parts[0])
    return bool(result_set and len(result_set.items) > 1 and len(parts) > 1)


def _resolve_ref_list(results_by_id: Dict[str, ExecutionResultSet], ref: str) -> Any:
    """
    Return a list of values extracted from ALL rows of a prior result set.
    e.g. ref = "p1.customer_id"  →  [row["customer_id"] for row in p1.items]
    If ref has no field part, returns the full list of row dicts.
    """
    if not ref:
        return None

    # Strip [*] wildcard notation if present
    ref = ref.replace("[*]", "")

    parts = ref.split(".")
    result_set = results_by_id.get(parts[0])
    if not result_set or not result_set.items:
        return None

    if len(parts) == 1:
        if all(isinstance(row, dict) and len(row) == 1 for row in result_set.items):
            first_key = next(iter(result_set.items[0].keys()))
            return [row.get(first_key) for row in result_set.items]
        return result_set.items

    field = parts[1]
    return [
        row.get(field)
        for row in result_set.items
        if isinstance(row, dict) and field in row
    ]


def _expand_templates(value: Any, results_by_id: Dict[str, ExecutionResultSet]) -> Any:
    """
    Recursively walk an argument structure and resolve any {{step.field}} or
    {{step.field[*].col}} template expressions into real values.

    - A single-row reference (e.g. {{p1.id}}) resolves via _resolve_ref → scalar.
    - A multi-row / wildcard reference (e.g. {{p1.customer_id[*]}}) resolves via
      _resolve_ref_list → list, suitable for SQL IN clauses.
    """
    if isinstance(value, str):
        m = _TMPL_RE.fullmatch(value.strip())
        if m:
            ref = m.group(1).strip()
            if "[*]" in ref:
                return _resolve_ref_list(results_by_id, ref)
            # Heuristic: if the referenced step has multiple rows, return list
            parts = ref.replace("[*]", "").split(".")
            result_set = results_by_id.get(parts[0])
            if result_set and len(result_set.items) > 1:
                return _resolve_ref_list(results_by_id, ref)
            return _resolve_ref(results_by_id, ref)
        return value
    if isinstance(value, dict):
        return {k: _expand_templates(v, results_by_id) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_templates(v, results_by_id) for v in value]
    return value


def _normalize_error_meta(
    error: str,
    *,
    source_id: str,
    source_type: str,
    error_code: Optional[str] = None,
    recoverable: bool = True,
) -> Dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "error": error,
        "error_code": error_code or "EXECUTION_ERROR",
        "recoverable": recoverable,
    }


def _validate_tool_arguments(step: PlanStep, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if step.tool_name != "query.vector":
        return None

    embedding = arguments.get("embedding")
    if embedding is None:
        return _normalize_error_meta(
            "A valid embedding was not available for the vector search step.",
            source_id=step.server_id,
            source_type=step.tool_name,
            error_code="INVALID_VECTOR_INPUT",
            recoverable=True,
        )
    if not isinstance(embedding, list) or len(embedding) != 3:
        return _normalize_error_meta(
            "Embedding must have dimension 3",
            source_id=step.server_id,
            source_type=step.tool_name,
            error_code="INVALID_VECTOR_INPUT",
            recoverable=True,
        )
    return None


async def execute_plan_steps(plan_steps: List[PlanStep]) -> tuple[List[ExecutionResultSet], List[Dict[str, Any]]]:
    result_sets: List[ExecutionResultSet] = []
    results_by_id: Dict[str, ExecutionResultSet] = {}
    tool_calls: List[Dict[str, Any]] = []
    output_keys_by_step_id = {step.id: step.output_key for step in plan_steps}

    for step in plan_steps:
        arguments = dict(step.arguments)
        if step.depends_on and step.depends_on not in results_by_id:
            if step.optional:
                continue
            result_sets.append(
                ExecutionResultSet(
                    key=step.output_key,
                    server_id=step.server_id,
                    tool_name=step.tool_name,
                    items=[],
                    meta=_normalize_error_meta(
                        f"Dependency {step.depends_on} missing",
                        source_id=step.server_id,
                        source_type=step.tool_name,
                        error_code="MISSING_DEPENDENCY",
                        recoverable=False,
                    ),
                )
            )
            continue

        # Resolve *_from references (e.g. embedding_from, customer_id_from)
        for key, value in list(arguments.items()):
            if key.endswith("_from"):
                normalized_ref = _normalize_ref(value, output_keys_by_step_id)
                if _should_resolve_as_list(key, normalized_ref, results_by_id):
                    resolved = _resolve_ref_list(results_by_id, normalized_ref)
                else:
                    resolved = _resolve_ref(results_by_id, normalized_ref)
                target_key = key[:-5]
                arguments[target_key] = resolved
                arguments.pop(key)

        if step.tool_name == "query.sql":
            params = arguments.get("params")
            if not isinstance(params, dict):
                params = {}
            else:
                params = dict(params)

            for key in list(arguments.keys()):
                if key not in {"query", "params"}:
                    params[key] = arguments.pop(key)

            arguments["params"] = params

        # Resolve {{...}} template expressions anywhere in the arguments,
        # including inside nested "params" dicts produced by the LLM.
        arguments = _expand_templates(arguments, results_by_id)

        validation_error = _validate_tool_arguments(step, arguments)
        if validation_error:
            result_set = ExecutionResultSet(
                key=step.output_key,
                server_id=step.server_id,
                tool_name=step.tool_name,
                items=[],
                meta=validation_error,
            )
            result_sets.append(result_set)
            results_by_id[step.id] = result_set
            results_by_id[step.output_key] = result_set
            tool_calls.append(
                {
                    "step_id": step.id,
                    "server_id": step.server_id,
                    "tool_name": step.tool_name,
                    "arguments": arguments,
                    "item_count": 0,
                    "meta": validation_error,
                }
            )
            continue

        try:
            result = await mcp_manager.runtime.invoke_tool(step.server_id, step.tool_name, arguments)
            structured = result.structured_content
            items = structured.get("items", [])
            meta = structured.get("meta", {})
        except Exception as exc:
            logger.exception("MCP tool call failed for %s.%s", step.server_id, step.tool_name)
            items = []
            meta = _normalize_error_meta(
                str(exc),
                source_id=step.server_id,
                source_type=step.tool_name,
            )

        if meta.get("error") and "error_code" not in meta:
            meta = _normalize_error_meta(
                meta["error"],
                source_id=meta.get("source_id", step.server_id),
                source_type=meta.get("source_type", step.tool_name),
                error_code=(
                    "INVALID_VECTOR_INPUT"
                    if step.tool_name == "query.vector" and "dimension 3" in meta["error"]
                    else "EXECUTION_ERROR"
                ),
                recoverable=True,
            ) | {k: v for k, v in meta.items() if k not in {"error", "error_code", "recoverable", "source_id", "source_type"}}

        result_set = ExecutionResultSet(
            key=step.output_key,
            server_id=step.server_id,
            tool_name=step.tool_name,
            items=items,
            meta=meta,
        )
        result_sets.append(result_set)
        results_by_id[step.id] = result_set
        results_by_id[step.output_key] = result_set
        tool_calls.append(
            {
                "step_id": step.id,
                "server_id": step.server_id,
                "tool_name": step.tool_name,
                "arguments": arguments,
                "item_count": len(items),
                "meta": meta,
            }
        )

    return result_sets, tool_calls


def _normalize_ref(ref: str, output_keys_by_step_id: Dict[str, str]) -> str:
    if not ref:
        return ref
    parts = ref.split(".")
    if len(parts) == 2:
        step_id, field = parts
        output_key = output_keys_by_step_id.get(step_id)
        if output_key and field == output_key:
            return f"{step_id}.embedding"
    return ref


async def execute_plan(plan_nodes: List[PlanNode]) -> List[ExecutionTask]:
    plan_steps: List[PlanStep] = []
    for node in plan_nodes:
        step = json.loads(node.subquery_nl)
        plan_steps.append(
            PlanStep(
                id=step["id"],
                description=step["description"],
                server_id=step["server_id"],
                tool_name=step["tool_name"],
                arguments=step.get("arguments", {}),
                depends_on=step.get("depends_on"),
                output_key=step.get("output_key", step["id"]),
                optional=step.get("optional", False),
            )
        )

    result_sets, _tool_calls = await execute_plan_steps(plan_steps)
    tasks: List[ExecutionTask] = []
    for result_set in result_sets:
        tasks.append(
            ExecutionTask(
                task_id=str(uuid.uuid4()),
                plan_node_id=result_set.key,
                source=result_set.server_id,
                native_query=json.dumps({"tool": result_set.tool_name}),
                result=result_set.items,
                meta=SourceMeta(
                    source_id=result_set.server_id,
                    source_type=result_set.tool_name,
                    output_alias=result_set.key,
                    extra=result_set.meta,
                ),
            )
        )
    return tasks
