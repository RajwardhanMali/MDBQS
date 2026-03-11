from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.state import ExecutionResultSet, ExecutionTask


def _get_meta_dict(meta: Any) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    return {
        "source_id": getattr(meta, "source_id", None),
        "source_type": getattr(meta, "source_type", None),
        "last_updated": getattr(meta, "last_updated", None),
        "output_alias": getattr(meta, "output_alias", None),
        "extra": getattr(meta, "extra", None) or {},
    }


def result_sets_from_tasks(tasks: List[ExecutionTask]) -> List[ExecutionResultSet]:
    return [
        ExecutionResultSet(
            key=(_get_meta_dict(task.meta).get("output_alias") or task.plan_node_id),
            server_id=task.source,
            tool_name=_get_meta_dict(task.meta).get("source_type") or "unknown",
            items=task.result or [],
            meta=_get_meta_dict(task.meta).get("extra", {}),
        )
        for task in tasks
    ]


def build_generic_response(
    result_sets: List[ExecutionResultSet],
    answer: str = "",
    explain: Optional[List[str]] = None,
    trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    explain = explain or []
    citations = [
        {
            "server_id": result_set.server_id,
            "tool_name": result_set.tool_name,
            "key": result_set.key,
            "count": len(result_set.items),
        }
        for result_set in result_sets
    ]
    return {
        "answer": answer,
        "result_sets": [result_set.model_dump() for result_set in result_sets],
        "citations": citations,
        "explain": explain,
        "trace": trace or {},
    }


def compatibility_fused_data(result_sets: List[ExecutionResultSet], nl_query: Optional[str] = None) -> Dict[str, Any]:
    fused: Dict[str, Any] = {
        "customer": {},
        "customers": [],
        "recent_orders": [],
        "referrals": [],
        "similar_customers": [],
        "explain": [],
        "provenance": {},
    }

    for result_set in result_sets:
        key = result_set.key
        if key == "customer" and result_set.items:
            fused["customer"] = result_set.items[0]
        elif key == "customers":
            fused["customers"].extend(result_set.items)
        elif key == "recent_orders":
            fused["recent_orders"].extend(result_set.items)
        elif key == "referrals":
            fused["referrals"].extend(result_set.items)
        elif key == "similar_customers":
            fused["similar_customers"].extend(result_set.items)
        elif key == "results" and not fused["customers"]:
            fused["customers"].extend(result_set.items)

        fused["provenance"][key] = {"source": result_set.server_id, "meta": result_set.meta}
        fused["explain"].append(f"{key} from {result_set.server_id}")

    q = (nl_query or "").lower()
    if "all customers" in q or "list customers" in q:
        if not fused["customers"] and fused["customer"]:
            fused["customers"] = [fused["customer"]]
    return fused


def fuse(tasks: List[ExecutionTask], nl_query: Optional[str] = None) -> Dict[str, Any]:
    return compatibility_fused_data(result_sets_from_tasks(tasks), nl_query=nl_query)
