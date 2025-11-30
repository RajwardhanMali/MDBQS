# app/services/fusion.py
from typing import List, Dict, Any
from app.models.state import ExecutionTask
import uuid

def fuse(execution_tasks: List[ExecutionTask]) -> Dict[str, Any]:
    fused = {"customer": {}, "recent_orders": [], "referrals": [], "similar_customers": [], "explain": []}
    # locate tasks by capability via their plan_node_id or source
    for t in execution_tasks:
        if t.source and "sql" in t.source:
            rows = t.result or []
            if rows:
                r = rows[0]
                fused["customer"] = {
                    "id": r.get("id"),
                    "name": {"value": r.get("name"), "provenance": [{"source": t.source, "field": "name"}]},
                    "email": {"value": r.get("email"), "provenance": [{"source": t.source, "field": "email"}]},
                }
                fused["explain"].append(f"Customer info from {t.source}")
        elif t.source and "orders" in t.source:
            fused["recent_orders"] = t.result or []
            fused["explain"].append(f"Orders from {t.source}")
        elif t.source and "graph" in t.source:
            fused["referrals"] = t.result or []
            fused["explain"].append(f"Referrals from {t.source}")
        elif t.source and "vector" in t.source:
            fused["similar_customers"] = t.result or []
            fused["explain"].append(f"Similar customers from {t.source}")

    return fused
