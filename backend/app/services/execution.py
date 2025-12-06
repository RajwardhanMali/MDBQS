# app/services/execution.py
import json
import uuid
import logging
from typing import List, Dict, Any, Optional

from app.models.state import PlanNode, ExecutionTask
from app.services import mcp_manager

logger = logging.getLogger("execution")
logger.setLevel(logging.INFO)


def _resolve_ref(results_by_id: Dict[str, ExecutionTask], ref: str) -> Any:
    """
    Resolve a reference like "p1.embedding" or "p1.customer.embedding"
    into an actual value from previous ExecutionTask results.
    """
    if not ref:
        return None

    parts = ref.split(".")
    step_id = parts[0]
    task = results_by_id.get(step_id)
    if not task or not task.result:
        logger.warning(f"Cannot resolve ref {ref}: step {step_id} not found or has no results")
        return None

    value: Any = task.result[0] if task.result else None
    if value is None:
        logger.warning(f"Cannot resolve ref {ref}: step {step_id} has empty results")
        return None
    
    for key in parts[1:]:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                logger.warning(f"Cannot resolve ref {ref}: key '{key}' not found")
                return None
        else:
            logger.warning(f"Cannot resolve ref {ref}: value is not a dict at key '{key}'")
            return None
    
    logger.info(f"Resolved ref {ref} to value of type {type(value)}")
    return value


def _extract_rows(res: Any) -> List[Dict[str, Any]]:
    """
    Normalize different MCP result shapes into a list[dict].
    Expected typical shapes:
      { "rows": [...], "meta": {...} }
      { "docs": [...], "meta": {...} }
      { "matches": [...], "meta": {...} }
      { "data": [...], "meta": {...} }
      or just a list.
    """
    if isinstance(res, list):
        return res

    if not isinstance(res, dict):
        return []

    if "rows" in res:
        return res["rows"]
    if "docs" in res:
        return res["docs"]
    if "matches" in res:
        return res["matches"]
    if "data" in res:
        return res["data"]
    return []


def _extract_meta(res: Any) -> Dict[str, Any]:
    if isinstance(res, dict):
        return res.get("meta", {}) or {}
    return {}


async def execute_plan(plan_nodes: List[PlanNode]) -> List[ExecutionTask]:
    """
    Execute LLM-native plan nodes with comprehensive logging.
    """
    tasks: List[ExecutionTask] = []
    results_by_id: Dict[str, ExecutionTask] = {}

    logger.info("=" * 70)
    logger.info(f"EXECUTION START: {len(plan_nodes)} plan nodes to execute")
    logger.info("=" * 70)

    for idx, node in enumerate(plan_nodes):
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP {idx+1}/{len(plan_nodes)}: Processing node {node.id}")
        logger.info(f"{'='*70}")
        
        try:
            step = json.loads(node.subquery_nl) if node.subquery_nl else {}
            logger.info(f"Parsed step: {json.dumps(step, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse step JSON for node {node.id}: {e}")
            step = {}
        
        step_id = step.get("id", node.id)
        mcp_id = step.get("mcp_id") or node.preferred
        tool = step.get("tool", "")
        db_type = (step.get("db_type") or "").lower()
        input_payload: Dict[str, Any] = step.get("input") or {}
        depends_on = step.get("depends_on") or node.depends_on
        output_alias = step.get("output_alias")
        is_optional = step.get("optional", False)

        logger.info(f"Step details:")
        logger.info(f"  - step_id: {step_id}")
        logger.info(f"  - mcp_id: {mcp_id}")
        logger.info(f"  - tool: {tool}")
        logger.info(f"  - db_type: {db_type}")
        logger.info(f"  - depends_on: {depends_on}")
        logger.info(f"  - optional: {is_optional}")
        logger.info(f"  - output_alias: {output_alias}")

        # Check dependency BEFORE resolving references
        if depends_on:
            dep_task = results_by_id.get(depends_on)
            if not dep_task:
                logger.warning(f"⚠️  Dependency {depends_on} not found in results")
                if is_optional:
                    logger.info(f"⏭️  Skipping optional step {step_id}")
                    continue
                else:
                    logger.error(f"❌ Required dependency {depends_on} missing!")
                    task = ExecutionTask(
                        task_id=str(uuid.uuid4()),
                        plan_node_id=step_id,
                        source=mcp_id,
                        native_query=str(input_payload),
                        result=[],
                        meta={
                            "source_id": mcp_id,
                            "source_type": node.capability,
                            "last_updated": None,
                            "output_alias": output_alias,
                            "extra": {"error": f"Dependency {depends_on} not found"},
                        },
                    )
                    tasks.append(task)
                    results_by_id[step_id] = task
                    continue
            
            if not dep_task.result:
                logger.warning(f"⚠️  Dependency {depends_on} has no results")
                if is_optional:
                    logger.info(f"⏭️  Skipping optional step {step_id}")
                    continue
                else:
                    logger.warning(f"⚠️  Proceeding despite empty dependency")

        # Resolve any *_from references in input
        input_payload_copy = input_payload.copy()
        resolved_refs = []
        
        for key, value in input_payload.items():
            if isinstance(key, str) and key.endswith("_from"):
                ref_value = _resolve_ref(results_by_id, value)
                actual_key = key[:-5]  # Remove "_from" suffix
                if ref_value is not None:
                    input_payload_copy[actual_key] = ref_value
                    resolved_refs.append(f"{key}={value} -> {actual_key}={type(ref_value).__name__}")
                else:
                    logger.warning(f"⚠️  Could not resolve reference {key}={value}")
                input_payload_copy.pop(key)
        
        if resolved_refs:
            logger.info(f"✅ Resolved references:")
            for ref in resolved_refs:
                logger.info(f"   - {ref}")
        
        input_payload = input_payload_copy

        # Infer tool if not specified
        if not tool:
            cap = (node.capability or "").lower()
            if cap == "query.sql" or db_type == "sql":
                tool = "execute_sql"
            elif cap == "query.document" or db_type == "nosql":
                tool = "find"
            elif cap == "query.graph" or db_type == "graph":
                tool = "traverse"
            elif cap == "query.vector" or db_type == "vector":
                tool = "search"
            else:
                tool = "execute_sql"
            logger.info(f"🔧 Inferred tool={tool} from capability={cap}, db_type={db_type}")

        # Execute the MCP call
        logger.info(f"📞 Calling MCP: {mcp_id}.{tool}")
        logger.info(f"📦 Payload: {json.dumps(input_payload, indent=2)}")
        
        try:
            res = await mcp_manager.call_execute(mcp_id, tool, input_payload)
            logger.info(f"✅ MCP call succeeded, response type: {type(res)}")
        except Exception as e:
            logger.exception(f"❌ MCP call failed: {e}")
            task = ExecutionTask(
                task_id=str(uuid.uuid4()),
                plan_node_id=step_id,
                source=mcp_id,
                native_query=str(input_payload),
                result=[],
                meta={
                    "source_id": mcp_id,
                    "source_type": node.capability,
                    "last_updated": None,
                    "output_alias": output_alias,
                    "extra": {"error": str(e)},
                },
            )
            tasks.append(task)
            results_by_id[step_id] = task
            continue

        rows = _extract_rows(res)
        meta = _extract_meta(res)
        
        logger.info(f"📊 Extracted {len(rows)} rows from response")
        if rows:
            logger.info(f"📝 First row sample: {json.dumps(rows[0], default=str)[:200]}...")

        native_query = input_payload.get("query") or f"{tool}({json.dumps(input_payload)})"

        # Merge meta information
        meta_source_id = meta.get("source_id") or mcp_id
        meta_source_type = meta.get("source_type") or node.capability
        meta_last_updated = meta.get("last_updated")
        extra_meta = {k: v for k, v in meta.items() 
                     if k not in ("source_id", "source_type", "last_updated")}
        
        if extra_meta.get("error"):
            logger.error(f"❌ MCP returned error in meta: {extra_meta['error']}")

        task = ExecutionTask(
            task_id=str(uuid.uuid4()),
            plan_node_id=step_id,
            source=mcp_id,
            native_query=native_query,
            result=rows,
            meta={
                "source_id": meta_source_id,
                "source_type": meta_source_type,
                "last_updated": meta_last_updated,
                "output_alias": output_alias,
                "extra": extra_meta,
            },
        )

        tasks.append(task)
        results_by_id[step_id] = task
        logger.info(f"✅ Step {step_id} completed: {len(rows)} results stored")

    logger.info("\n" + "=" * 70)
    logger.info(f"EXECUTION COMPLETE: {len(tasks)}/{len(plan_nodes)} tasks executed")
    logger.info("=" * 70 + "\n")
    
    return tasks