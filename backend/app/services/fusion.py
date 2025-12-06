from typing import List, Dict, Any, Optional
from app.models.state import ExecutionTask
import datetime
import logging

logger = logging.getLogger("fusion")


def _get_meta_dict(meta: Any) -> Dict[str, Any]:
    """Normalize t.meta (dict or object) into a plain dict-like view."""
    if isinstance(meta, dict):
        return meta
    # fallback for object-style meta
    return {
        "source_id": getattr(meta, "source_id", None),
        "source_type": getattr(meta, "source_type", None),
        "last_updated": getattr(meta, "last_updated", None),
        "output_alias": getattr(meta, "output_alias", None),
        "extra": getattr(meta, "extra", None) or {},
    }


def fuse(tasks: List[ExecutionTask], nl_query: Optional[str] = None) -> Dict[str, Any]:
    """
    Fuse execution tasks into a single response shape expected by tests:
      {
        "customer": {...},
        "customers": [...],
        "recent_orders": [...],
        "referrals": [...],
        "similar_customers": [...],
        "explain": [...],
        "provenance": {...}
      }
    """
    fused: Dict[str, Any] = {
        "customer": {},
        "customers": [],
        "recent_orders": [],
        "referrals": [],
        "similar_customers": [],
        "explain": [],
        "provenance": {},
    }

    q = (nl_query or "").lower()
    is_list_customers = any(
        phrase in q
        for phrase in [
            "list of all customers",
            "all customers",
            "list all customers",
            "give me a list of all customers",
            "show all customers",
            "list customers",
            "list clients",
        ]
    )

    # Index tasks by alias and by coarse source_type
    tasks_by_alias: Dict[str, List[ExecutionTask]] = {}
    sql_tasks: List[ExecutionTask] = []
    nosql_tasks: List[ExecutionTask] = []
    graph_tasks: List[ExecutionTask] = []
    vector_tasks: List[ExecutionTask] = []

    for t in tasks:
        meta = _get_meta_dict(t.meta)
        src_type = (meta.get("source_type") or "").lower()
        alias = (meta.get("output_alias") or "").lower()
        extra = meta.get("extra") or {}

        if alias:
            tasks_by_alias.setdefault(alias, []).append(t)

        # coarse classification by source_type / source id
        src_id = (meta.get("source_id") or t.source or "").lower()

        if src_type.startswith("query.sql") or "sql" in src_id:
            sql_tasks.append(t)
        elif src_type.startswith("query.document") or "orders" in src_id or "mongo" in src_id:
            nosql_tasks.append(t)
        elif src_type.startswith("query.graph") or "graph" in src_id or "neo4j" in src_id:
            graph_tasks.append(t)
        elif src_type.startswith("query.vector") or "vector" in src_id or "milvus" in src_id:
            vector_tasks.append(t)

    # 1) Customers list for "list all customers" queries
    # Prefer tasks with alias "customers"
    customers_tasks = tasks_by_alias.get("customers") or sql_tasks
    if is_list_customers and customers_tasks:
        rows = customers_tasks[0].result or []
        fused["customers"] = rows
        fused["explain"].append(f"Customers from {customers_tasks[0].source}")
        fused["provenance"]["customers"] = {
            "source": customers_tasks[0].source,
            "meta": _get_meta_dict(customers_tasks[0].meta).get("extra", {}),
        }
        return fused

    # 2) Primary single customer
    primary_customer = None

    # Prefer a task explicitly labeled as "customer"
    customer_tasks = tasks_by_alias.get("customer") or []
    if customer_tasks and customer_tasks[0].result:
        primary_customer = customer_tasks[0].result[0]
        fused["customer"] = primary_customer
        fused["explain"].append(f"Customer from {customer_tasks[0].source}")
        fused["provenance"]["customer"] = {
            "source": customer_tasks[0].source,
            "meta": _get_meta_dict(customer_tasks[0].meta).get("extra", {}),
        }
    elif sql_tasks and sql_tasks[0].result:
        # Fallback: first SQL task's first row
        primary_customer = sql_tasks[0].result[0]
        fused["customer"] = primary_customer
        fused["explain"].append(f"Customer from {sql_tasks[0].source}")
        fused["provenance"]["customer"] = {
            "source": sql_tasks[0].source,
            "meta": _get_meta_dict(sql_tasks[0].meta).get("extra", {}),
        }

    # 3) Recent orders (NoSQL)
    orders_tasks = tasks_by_alias.get("recent_orders") or nosql_tasks
    for t in orders_tasks:
        fused["recent_orders"].extend(t.result or [])
    if orders_tasks:
        fused["explain"].append(
            f"Orders from {', '.join(sorted({t.source for t in orders_tasks}))}"
        )
        fused["provenance"]["recent_orders"] = [
            {
                "source": t.source,
                "meta": _get_meta_dict(t.meta).get("extra", {}),
            }
            for t in orders_tasks
        ]

    # 4) Referrals (graph)
    referrals_tasks = tasks_by_alias.get("referrals") or graph_tasks
    for t in referrals_tasks:
        fused["referrals"].extend(t.result or [])
    if referrals_tasks:
        fused["explain"].append(
            f"Referrals from {', '.join(sorted({t.source for t in referrals_tasks}))}"
        )
        fused["provenance"]["referrals"] = [
            {
                "source": t.source,
                "meta": _get_meta_dict(t.meta).get("extra", {}),
            }
            for t in referrals_tasks
        ]

    # 5) Similar customers (vector)
    similars_tasks = tasks_by_alias.get("similar_customers") or vector_tasks
    for t in similars_tasks:
        fused["similar_customers"].extend(t.result or [])
    if similars_tasks:
        fused["explain"].append(
            f"Similar customers from {', '.join(sorted({t.source for t in similars_tasks}))}"
        )
        fused["provenance"]["similar_customers"] = [
            {
                "source": t.source,
                "meta": _get_meta_dict(t.meta).get("extra", {}),
            }
            for t in similars_tasks
        ]

    # 6) Fallback: infer primary customer from orders if none set
    if not primary_customer and fused["recent_orders"]:
        first_order = fused["recent_orders"][0]
        cid = first_order.get("customer_id") or first_order.get("cust_id")
        if cid:
            fused["customer"] = {"id": cid}
            fused["explain"].append("Inferred primary customer from recent orders")
            fused["provenance"]["customer"] = {
                "inferred_from": "orders",
                "sample_order": first_order,
            }

    return fused
