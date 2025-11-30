# app/services/execution.py
import asyncio
import uuid
from typing import List, Dict, Any
from app.models.state import ExecutionTask
from app.services import mcp_manager
from app.services.schema_index import schema_index

async def execute_plan(plan_nodes: List[Dict[str, Any]]) -> List[ExecutionTask]:
    # find p1 (SQL) first if exists
    tasks: List[ExecutionTask] = []
    node_by_id = {n.id: n for n in plan_nodes}
    # execute nodes in order: those without depends_on first
    first_nodes = [n for n in plan_nodes if not getattr(n, "depends_on", None)]
    # For MVP: execute first_nodes sequentially then others in parallel
    # We'll always wait for the SQL (customer) node first to get customer_id
    sql_node = next((n for n in plan_nodes if n.capability == "query.sql"), None)
    customer = None
    if sql_node:
        # construct a safe SQL query using schema index
        # For MVP, we assume a customers table with name/email fields
        native = f"SELECT id, name, email, embedding FROM customers WHERE name ILIKE '%{sql_node.subquery_nl.split()[-1]}%' LIMIT 1"
        res = await mcp_manager.call_execute(sql_node.preferred or "sql_customers", "execute_sql", {"query": native, "params": {}})
        rows = res.get("rows", [])
        task = ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=sql_node.id, source=sql_node.preferred, native_query=native, result=rows, meta=None)
        tasks.append(task)
        if rows:
            customer = rows[0]
    # Now run dependent nodes in parallel
    async def run_node(n):
        if n.capability == "query.document":
            # orders: call find with customer_id
            if not customer:
                return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query="skip", result=[])
            payload = {"filter": {"customer_id": customer.get("id")}, "limit": 5}
            res = await mcp_manager.call_execute(n.preferred or "orders_mongo", "find", payload)
            rows = res.get("docs", [])
            return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query=str(payload), result=rows, meta=None)
        if n.capability == "query.graph":
            if not customer:
                return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query="skip", result=[])
            payload = {"start": {"property": "id", "value": customer.get("id")}, "rel": "REFERRED", "depth": 1}
            res = await mcp_manager.call_execute(n.preferred or "graph_referrals", "traverse", payload)
            return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query=str(payload), result=res.get("data", []), meta=None)
        if n.capability == "query.vector":
            # vector search: obtain embedding from customer or call vector metadata
            emb = None
            if customer and "embedding" in customer and customer["embedding"]:
                emb = customer["embedding"]
            else:
                # attempt to get metadata
                res = await mcp_manager.call_execute(n.preferred or "vector_customers", "get_metadata", {"customer_id": customer.get("id") if customer else None})
                emb = res.get("embedding")
            if not emb:
                return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query="no-embedding", result=[])
            payload = {"index": "customer_embeddings", "embedding": emb, "top_k": 2}
            res = await mcp_manager.call_execute(n.preferred or "vector_customers", "search", payload)
            return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query=str(payload), result=res.get("matches", []), meta=None)
        return ExecutionTask(task_id=str(uuid.uuid4()), plan_node_id=n.id, source=n.preferred, native_query="noop", result=[], meta=None)

    # gather all other nodes except the executed SQL node
    other_nodes = [n for n in plan_nodes if n is not sql_node]
    if other_nodes:
        results = await asyncio.gather(*(run_node(n) for n in other_nodes))
        tasks.extend(results)
    return tasks
