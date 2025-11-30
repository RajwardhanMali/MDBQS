# app/services/schema_index.py
from typing import List, Dict, Any
import re

class SchemaIndex:
    def __init__(self):
        # simple in-memory registry
        self.index = {}

    def register(self, mcp_id: str, snapshot: Dict[str, Any]):
        self.index[mcp_id] = snapshot

    def search_fields(self, q: str, top_k: int = 5):
        # simple substring match and score
        qlow = q.lower()
        hits = []
        for mcp_id, snap in self.index.items():
            # flatten fields from common keys
            fields = []
            if "tables" in snap:
                for t in snap["tables"]:
                    for f in t.get("fields", []):
                        fields.append((mcp_id, t.get("table", ""), f))
            if "collections" in snap:
                for c in snap["collections"]:
                    for f in c.get("fields", []):
                        fields.append((mcp_id, c.get("collection", ""), f))
            if "node_properties" in snap:
                for label, props in snap["node_properties"].items():
                    for p in props:
                        fields.append((mcp_id, label, p))
            if "indices" in snap:
                for idx in snap.get("indices", []):
                    for mf in snap.get("metadata_fields", []):
                        fields.append((mcp_id, idx, mf))

            for mcp, parent, f in fields:
                score = 0.0
                if qlow in f.lower():
                    score += 1.0
                if qlow in parent.lower():
                    score += 0.5
                if score > 0:
                    hits.append({"id": f"{mcp}.{parent}.{f}", "mcp": mcp, "parent": parent, "field": f, "score": score})

        hits = sorted(hits, key=lambda x: -x["score"])
        return hits[:top_k]

# singleton instance
schema_index = SchemaIndex()
