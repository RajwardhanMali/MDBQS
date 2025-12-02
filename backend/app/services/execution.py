# app/services/execution.py
import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.models.state import PlanNode, ExecutionTask, SourceMeta
from app.services import mcp_manager

logger = logging.getLogger("execution")


async def execute_plan(plan_nodes: List[PlanNode]) -> List[ExecutionTask]:
    """
    Execute the given plan nodes by calling the appropriate MCP servers.
    Only executes what the planner returns (no hardcoded calls).
    """
    tasks: List[ExecutionTask] = []
    # to handle depends_on: store tasks by plan_node_id
    results_by_id: Dict[str, ExecutionTask] = {}

    async def run_node(node: PlanNode) -> ExecutionTask:
        logger.info(
            "Executing node %s (type=%s capability=%s preferred=%s depends_on=%s)",
            node.id, node.type, node.capability, node.preferred, node.depends_on
        )

        # resolve dependency, if any
        dep_task: Optional[ExecutionTask] = None
        if node.depends_on:
            dep_task = results_by_id.get(node.depends_on)
            logger.info("Node %s depends_on %s -> %s", node.id, node.depends_on, dep_task)

        capability = node.capability
        mcp_id = node.preferred
        native = node.subquery_nl

        payload: Dict[str, Any] = {}

        # Very simple patterns: you can get fancy later with placeholders / templates
        if capability == "query.sql":
            # For now, we assume subquery_nl already contains a valid SQL string
            payload = {"query": native, "params": {}}
            op = "execute_sql"

        elif capability == "query.document":
            # Example: if depends_on returned a customer_id, use it
            filt: Dict[str, Any] = {}
            if dep_task and dep_task.result:
                # assume first row has "id"
                first = dep_task.result[0]
                cust_id = first.get("id") or first.get("customer_id")
                if cust_id:
                    filt["customer_id"] = cust_id
            payload = {"filter": filt, "limit": 5}
            op = "find"

        elif capability == "query.graph":
            # simple graph traversal: from a customer id if we have one
            start_id = None
            if dep_task and dep_task.result:
                first = dep_task.result[0]
                start_id = first.get("id") or first.get("customer_id")
            payload = {"start_id": start_id, "max_depth": 2}
            op = "traverse"

        elif capability == "query.vector":
            # vector search using embedding from dep_task if available
            emb = None
            if dep_task and dep_task.result:
                first = dep_task.result[0]
                emb = first.get("embedding")
            payload = {"index": "customer_embeddings", "embedding": emb, "top_k": 3}
            op = "search"

        else:
            logger.warning("Unknown capability %s for node %s", capability, node.id)
            return ExecutionTask(
                task_id=str(uuid.uuid4()),
                plan_node_id=node.id,
                source=mcp_id or "",
                native_query=native,
                result=[],
                meta=None,
            )

        # call MCP via manager
        res = await mcp_manager.call_execute(mcp_id, op, payload)
        # normalize possible shapes (rows/docs/matches)
        result = res.get("rows") or res.get("docs") or res.get("matches") or res.get("data") or []
        meta_raw = res.get("meta", {})

        meta = SourceMeta(
            source_id=meta_raw.get("source_id", mcp_id or ""),
            source_type=meta_raw.get("source_type", capability),
            extra=meta_raw,
        )

        task = ExecutionTask(
            task_id=str(uuid.uuid4()),
            plan_node_id=node.id,
            source=mcp_id or "",
            native_query=native,
            result=result,
            meta=meta,
        )
        logger.info("Node %s executed: %d rows", node.id, len(result))
        results_by_id[node.id] = task
        return task

    # run sequentially to keep dependency handling simple
    for node in plan_nodes:
        t = await run_node(node)
        tasks.append(t)

    return tasks
