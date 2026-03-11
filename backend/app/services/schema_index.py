from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("schema_index")


@dataclass
class FieldInfo:
    name: str
    type: str
    description: Optional[str] = None
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class EntityInfo:
    name: str
    kind: str
    fields: List[FieldInfo]
    semantic_tags: List[str] = field(default_factory=list)
    default_id_field: Optional[str] = None


@dataclass
class SourceSchema:
    mcp_id: str
    db_type: str
    entities: List[EntityInfo]
    metadata: Dict[str, Any] = field(default_factory=dict)


class SchemaIndex:
    def __init__(self):
        self.schemas: Dict[str, SourceSchema] = {}

    def register_schema(self, schema: SourceSchema) -> None:
        logger.info("Registering schema for MCP %s (db_type=%s)", schema.mcp_id, schema.db_type)
        self.schemas[schema.mcp_id] = schema

    def clear(self) -> None:
        self.schemas.clear()

    def discover_candidates(self, nl_query: str) -> List[Dict[str, Any]]:
        q = nl_query.lower()
        matches: List[Dict[str, Any]] = []

        for source in self.schemas.values():
            for ent in source.entities:
                score = 0
                if ent.name.lower() in q:
                    score += 4

                for tag in ent.semantic_tags:
                    if tag.replace("entity:", "").replace("_", " ") in q:
                        score += 3

                matching_fields = []
                for field in ent.fields:
                    if field.name.lower() in q:
                        score += 2
                        matching_fields.append(field.name)
                    elif any(tag.replace("_", " ") in q for tag in field.semantic_tags):
                        score += 1
                        matching_fields.append(field.name)

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
                            "matching_fields": matching_fields,
                            "score": score,
                        }
                    )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def build_sources_for_llm(self) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for schema in self.schemas.values():
            tools = [schema.metadata.get("primary_tool")] if schema.metadata.get("primary_tool") else []
            if not tools:
                if schema.db_type == "sql":
                    tools = ["query.sql"]
                elif schema.db_type == "nosql":
                    tools = ["query.document"]
                elif schema.db_type == "graph":
                    tools = ["query.graph"]
                elif schema.db_type == "vector":
                    tools = ["query.vector"]

            sources.append(
                {
                    "mcp_id": schema.mcp_id,
                    "db_type": schema.db_type,
                    "tools": tools,
                    "entities": [
                        {
                            "name": ent.name,
                            "kind": ent.kind,
                            "semantic_tags": ent.semantic_tags,
                            "default_id_field": ent.default_id_field,
                            "fields": [
                                {
                                    "name": field.name,
                                    "type": field.type,
                                    "description": field.description,
                                    "semantic_tags": field.semantic_tags,
                                }
                                for field in ent.fields
                            ],
                        }
                        for ent in schema.entities
                    ],
                }
            )
        return sources

    def search_fields(self, q: str) -> List[Dict[str, Any]]:
        needle = q.lower()
        hits: List[Dict[str, Any]] = []
        for schema in self.schemas.values():
            for entity in schema.entities:
                parent_hit = needle in entity.name.lower() or any(needle in tag.lower() for tag in entity.semantic_tags)
                for field in entity.fields:
                    score = 0.0
                    if needle in field.name.lower():
                        score += 1.0
                    if any(needle in tag.lower() for tag in field.semantic_tags):
                        score += 0.8
                    if parent_hit:
                        score += 0.2
                    if score <= 0:
                        continue
                    hits.append(
                        {
                            "id": f"{schema.mcp_id}.{entity.name}.{field.name}",
                            "mcp": schema.mcp_id,
                            "parent": entity.name,
                            "field": field.name,
                            "field_type": field.type,
                            "score": round(score, 2),
                        }
                    )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits


schema_index = SchemaIndex()


def source_schema_from_dict(d: Dict[str, Any]) -> SourceSchema:
    entities: List[EntityInfo] = []
    for e in d.get("entities", []):
        fields = [
            FieldInfo(
                name=f["name"],
                type=f.get("type", "text"),
                description=f.get("description"),
                semantic_tags=f.get("semantic_tags", []),
            )
            for f in e.get("fields", [])
        ]
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
        metadata=d.get("metadata", {}),
    )
