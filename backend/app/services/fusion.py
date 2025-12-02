# app/services/fusion.py
from typing import List, Dict, Any, Optional
from app.models.state import ExecutionTask  # adapt import to your model location
import datetime
import logging
logger = logging.getLogger("fusion")

# Conflict resolution helper functions

def choose_by_source_priority(values_with_meta, priority_order):
    """
    values_with_meta: list of (value, meta) tuples where meta contains 'source_id' or source info.
    priority_order: list of source_ids in descending priority (first = most authoritative)
    """
    if not values_with_meta:
        return None, None
    # If any value comes from a priority source, choose the most-prioritized one
    src_to_items = {}
    for val, meta in values_with_meta:
        src = (meta or {}).get("source_id") or (meta or {}).get("source") or "unknown"
        src_to_items.setdefault(src, []).append((val, meta))
    for src in priority_order:
        if src in src_to_items:
            chosen_val, chosen_meta = src_to_items[src][0]
            return chosen_val, chosen_meta
    # else fallback: return first
    return values_with_meta[0]


def choose_by_recency(values_with_meta):
    """
    Choose value whose meta.last_updated is newest (expects ISO timestamp or None).
    meta may contain last_updated key.
    """
    def parse_date(d):
        if not d:
            return datetime.datetime.min
        try:
            return datetime.datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            return datetime.datetime.min
    best = None
    best_meta = None
    best_date = datetime.datetime.min
    for val, meta in values_with_meta:
        date = parse_date((meta or {}).get("last_updated"))
        if date > best_date:
            best = val
            best_meta = meta
            best_date = date
    if best_meta is None and values_with_meta:
        return values_with_meta[0]
    return best, best_meta


def choose_by_voting(values_with_meta):
    """
    For simple strings/numerics: choose the mode (most common); tie-breaker first.
    """
    counts = {}
    for val, meta in values_with_meta:
        key = repr(val)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None, None
    # get key with max count
    best_key = max(counts.items(), key=lambda kv: kv[1])[0]
    # get first occurrence of that repr and return original value+meta
    for val, meta in values_with_meta:
        if repr(val) == best_key:
            return val, meta
    return None, None


# Main fuse function
def fuse(tasks: List[ExecutionTask], nl_query: Optional[str] = None) -> Dict[str, Any]:
    """
    tasks: list of ExecutionTask (must include: plan_node_id, source, native_query, result(list), meta(SourceMeta-like))
    Returns a dict with fused outputs and provenance.
    """
    fused: Dict[str, Any] = {
        "customer": {},
        "customers": [],  # for list queries
        "recent_orders": [],
        "referrals": [],
        "similar_customers": [],
        "explain": [],
        "provenance": {}
    }

    # Map tasks by plan_node_id and by source
    tasks_by_id = {t.plan_node_id: t for t in tasks}
    tasks_by_source = {}
    for t in tasks:
        tasks_by_source.setdefault(t.source, []).append(t)

    # Determine if query is a 'list customers' style
    q = (nl_query or "").lower()
    is_list_customers = any(phrase in q for phrase in [
        "list of all customers", "all customers", "list all customers", "give me a list of all customers",
        "show all customers", "list customers", "list clients"
    ])

    # Heuristic: find SQL task(s)
    sql_tasks = [t for t in tasks if (t.meta and ((t.meta.source_type or "").lower().startswith("query.sql") or (t.meta.extra or {}).get("source_type","").lower()=="sql")) or (t.source and "sql" in t.source)]
    # fallback by capability detection in meta.extra if present
    if not sql_tasks:
        for t in tasks:
            extra = getattr(t.meta, "extra", None) if t.meta else None
            if extra and extra.get("source_type") and extra.get("source_type").lower().startswith("query.sql"):
                sql_tasks.append(t)

    # If list query and we have a SQL task -> return customers list
    if is_list_customers and sql_tasks:
        rows = sql_tasks[0].result or []
        fused["customers"] = rows
        fused["explain"].append(f"Customers from {sql_tasks[0].source or 'sql'}")
        # provenance: record that entire list came from that source
        fused["provenance"]["customers"] = {
            "source": sql_tasks[0].source,
            "meta": getattr(sql_tasks[0].meta, "extra", {}) if sql_tasks[0].meta else {}
        }
        return fused

    # Otherwise, try to build a canonical single customer (if present)
    primary_customer = None
    if sql_tasks and sql_tasks[0].result:
        primary_customer = sql_tasks[0].result[0]
        fused["customer"] = primary_customer
        fused["explain"].append(f"Customer from {sql_tasks[0].source}")
        fused["provenance"]["customer"] = {"source": sql_tasks[0].source, "meta": getattr(sql_tasks[0].meta, "extra", {}) if sql_tasks[0].meta else {}}

    # Add recent orders from NoSQL tasks
    nosql_tasks = [t for t in tasks if (t.meta and ((t.meta.source_type or "").lower().startswith("query.document") or (t.meta.extra or {}).get("source_type","").lower()=="nosql")) or (t.source and "mongo" in t.source.lower() or "orders" in t.source.lower())]
    for t in nosql_tasks:
        fused["recent_orders"].extend(t.result or [])
    if nosql_tasks:
        fused["explain"].append(f"Orders from {', '.join([t.source for t in nosql_tasks])}")
        fused["provenance"]["recent_orders"] = [{"source": t.source, "meta": getattr(t.meta, "extra", {}) if t.meta else {}} for t in nosql_tasks]

    # Graph referrals
    graph_tasks = [t for t in tasks if (t.meta and ((t.meta.source_type or "").lower().startswith("query.graph") or (t.meta.extra or {}).get("source_type","").lower()=="graph")) or (t.source and "graph" in t.source.lower() or "neo4j" in t.source.lower())]
    for t in graph_tasks:
        fused["referrals"].extend(t.result or [])
    if graph_tasks:
        fused["explain"].append(f"Referrals from {', '.join([t.source for t in graph_tasks])}")
        fused["provenance"]["referrals"] = [{"source": t.source, "meta": getattr(t.meta, "extra", {}) if t.meta else {}} for t in graph_tasks]

    # Vector similar customers
    vector_tasks = [t for t in tasks if (t.meta and ((t.meta.source_type or "").lower().startswith("query.vector") or (t.meta.extra or {}).get("source_type","").lower()=="vector")) or (t.source and "vector" in t.source.lower() or "milvus" in t.source.lower())]
    for t in vector_tasks:
        fused["similar_customers"].extend(t.result or [])
    if vector_tasks:
        fused["explain"].append(f"Similar customers from {', '.join([t.source for t in vector_tasks])}")
        fused["provenance"]["similar_customers"] = [{"source": t.source, "meta": getattr(t.meta, "extra", {}) if t.meta else {}} for t in vector_tasks]

    # If no primary_customer but there are referrals or orders, attempt to infer a primary customer
    if not primary_customer:
        # try orders -> customer_id -> lookup
        if fused["recent_orders"]:
            first_order = fused["recent_orders"][0]
            cid = first_order.get("customer_id") or first_order.get("cust_id")
            if cid:
                fused["customer"] = {"id": cid}
                fused["explain"].append("Inferred primary customer from recent orders")
                fused["provenance"]["customer"] = {"inferred_from": "orders", "sample_order": first_order}
    # Final cleanup: remove empty explain entries or ensure keys exist
    fused["explain"] = fused["explain"]
    return fused
