import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.models.state import ExecutionResultSet, ExecutionTask, PlanNode, PlanStep, SourceMeta
from app.services import mcp_manager

logger = logging.getLogger("execution")
logger.setLevel(logging.INFO)


def _resolve_ref(results_by_id: Dict[str, ExecutionResultSet], ref: str) -> Any:
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

        for key, value in list(arguments.items()):
            if key.endswith("_from"):
                resolved = _resolve_ref(results_by_id, _normalize_ref(value, output_keys_by_step_id))
                arguments[key[:-5]] = resolved
                arguments.pop(key)

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
                error_code="INVALID_VECTOR_INPUT" if step.tool_name == "query.vector" and "dimension 3" in meta["error"] else "EXECUTION_ERROR",
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
