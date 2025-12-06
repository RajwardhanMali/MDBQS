# app/services/schema_index.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("schema_index")


@dataclass
class FieldInfo:
    name: str
    type: str
    description: Optional[str] = None
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class EntityInfo:
    name: str                      # e.g. "customers", "orders"
    kind: str                      # e.g. "table","collection","node","index"
    fields: List[FieldInfo]
    semantic_tags: List[str] = field(default_factory=list)  # e.g. ["entity:customer"]
    default_id_field: Optional[str] = None                  # e.g. "id","customer_id"


@dataclass
class SourceSchema:
    mcp_id: str                    # e.g. "sql_customers"
    db_type: str                   # "sql","nosql","graph","vector"
    entities: List[EntityInfo]


class SchemaIndex:
    """
    In-memory catalog of MCP schemas.
    This is what the planner consults to decide what exists.
    """

    def __init__(self):
        self.schemas: Dict[str, SourceSchema] = {}

    # -------- registration -------- #

    def register_schema(self, schema: SourceSchema) -> None:
        logger.info("Registering schema for MCP %s (db_type=%s)", schema.mcp_id, schema.db_type)
        self.schemas[schema.mcp_id] = schema

    def clear(self) -> None:
        self.schemas.clear()

    # -------- discovery / search -------- #

    def discover_candidates(self, nl_query: str) -> List[Dict[str, Any]]:
        """
        Given an NL query, return candidate (mcp_id, entity_name, fields, score, tags, db_type)
        that look relevant. (Used only by heuristic fallback now.)
        """
        q = nl_query.lower()
        matches: List[Dict[str, Any]] = []

        for source in self.schemas.values():
            for ent in source.entities:
                score = 0

                # very simple lexical scoring; you can improve later
                if "customer" in q and any("entity:customer" == t for t in ent.semantic_tags):
                    score += 5
                if "order" in q or "purchase" in q:
                    if any("entity:order" == t for t in ent.semantic_tags):
                        score += 5
                if "email" in q and any("email" in (f.semantic_tags or []) for f in ent.fields):
                    score += 3
                if "similar" in q or "embedding" in q:
                    if any("embedding" in (f.semantic_tags or []) for f in ent.fields):
                        score += 3
                if "referral" in q or "referred" in q:
                    if "referral" in (ent.semantic_tags or []):
                        score += 3

                if score > 0:
                    matches.append(
                        {
                            "mcp_id": source.mcp_id,
                            "db_type": source.db_type,
                            "entity": ent.name,
                            "entity_tags": ent.semantic_tags,
                            "fields": [f.name for f in ent.fields],
                            "field_tags": {f.name: f.semantic_tags for f in ent.fields},
                            "default_id_field": ent.default_id_field,
                            "score": score,
                        }
                    )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def build_sources_for_llm(self) -> List[Dict[str, Any]]:
        """
        Build a list of 'sources' for the LLM planning prompt.
        Each source describes an MCP, its db_type, tools, entities, and fields.
        """
        sources: List[Dict[str, Any]] = []

        for schema in self.schemas.values():
            if schema.db_type == "sql":
                tools = ["execute_sql", "get_schema"]
            elif schema.db_type == "nosql":
                tools = ["find", "get_schema"]
            elif schema.db_type == "graph":
                tools = ["traverse", "get_schema"]
            elif schema.db_type == "vector":
                tools = ["search", "get_schema"]
            else:
                tools = ["get_schema"]

            entities: List[Dict[str, Any]] = []
            for ent in schema.entities:
                entities.append(
                    {
                        "name": ent.name,
                        "semantic_tags": ent.semantic_tags,
                        "default_id_field": ent.default_id_field,
                        "fields": [
                            {
                                "name": f.name,
                                "type": f.type,
                                "semantic_tags": f.semantic_tags,
                            }
                            for f in ent.fields
                        ],
                    }
                )

            sources.append(
                {
                    "mcp_id": schema.mcp_id,
                    "db_type": schema.db_type,
                    "tools": tools,
                    "entities": entities,
                }
            )

        return sources


schema_index = SchemaIndex()


# utility parser (for MCP /get_schema responses)

def source_schema_from_dict(d: Dict[str, Any]) -> SourceSchema:
    entities: List[EntityInfo] = []
    for e in d.get("entities", []):
        fields: List[FieldInfo] = []
        for f in e.get("fields", []):
            fields.append(
                FieldInfo(
                    name=f["name"],
                    type=f.get("type", "text"),
                    description=f.get("description"),
                    semantic_tags=f.get("semantic_tags", []),
                )
            )
        entities.append(
            EntityInfo(
                name=e["name"],
                kind=e.get("kind", "table"),
                fields=fields,
                semantic_tags=e.get("semantic_tags", []),
                default_id_field=e.get("default_id_field"),
            )
        )
    return SourceSchema(
        mcp_id=d["mcp_id"],
        db_type=d.get("db_type", "sql"),
        entities=entities,
    )
