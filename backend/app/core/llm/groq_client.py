import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from app.models.state import ChatMessageRecord

logger = logging.getLogger("groq_client")

load_dotenv()

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False


PLAN_PROMPT_TEMPLATE = """
You are a planning agent for a multi-source query system.

You must ground every plan in the provided source schemas. Do not assume an e-commerce
domain, "customers", "orders", or any table/collection/index unless those names appear
in the provided schemas or the user explicitly mentions them.

Return ONLY JSON: an array of plan steps. No markdown, no extra text.

Each step must contain:
- id          : "p1", "p2", ... (string)
- description : short human-readable label
- server_id   : which MCP to call
- tool_name   : e.g. "query.sql", "query.document", "query.graph", "query.vector"
- arguments   : JSON object with the tool payload (see rules below)
- depends_on  : id of a prior step this step requires, or null
- output_key  : alias for this step's result set
- optional    : true if the step may be skipped when its dependency has no results

## Cross-step references
When a later step needs values produced by an earlier step, use a dedicated
"<field>_from" key in arguments, not a {{...}} template inside "params".

Examples:
  {{ "record_id_from": "p1.id" }}
  {{ "record_ids_from": "p1.id" }}

The execution engine will resolve *_from keys automatically:
- A single-row reference like "p1.id" resolves to a scalar.
- A multi-row reference like "p1.id" may resolve to a list when used for ids_from/list_from.

## SQL steps (tool_name = "query.sql")
- Use only "?" as positional placeholders.
- Put literal param values in "params" as a flat object: {{"name": "Alice"}}.
- For IN clauses driven by a prior step, use "ids_from" or another *_from key outside params. Example:
    arguments: {{
      "query": "SELECT id, title FROM records WHERE id IN (?)",
      "record_ids_from": "p1.id"
    }}

## NoSQL steps (tool_name = "query.document")
- Use "filter" for document filters.

## Vector steps (tool_name = "query.vector")
- Use "embedding_from": "p1.embedding" only when a prior step actually returns an embedding field.

## General rules
- Use the minimum number of steps needed.
- Only call sources relevant to the query.
- Use entity names and field names exactly as provided in the schemas.
- If the query is broad or generic, prefer a small schema-valid exploratory step over inventing domain entities.
- Never emit {{...}} template strings anywhere in the JSON output.

Available sources:
{sources_json}

Session summary:
{session_summary}

Recent messages:
{recent_messages_json}

User message:
{nl_query}
"""


class GroqClient:
    def __init__(self, api_key: Optional[str] = None, mock_mode: bool = False):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.mock_mode = mock_mode or (not GROQ_AVAILABLE)
        self.client = Groq(api_key=self.api_key) if GROQ_AVAILABLE and not self.mock_mode else None
        logger.info(
            "GroqClient initialized (GROQ_AVAILABLE=%s, mock_mode=%s)",
            GROQ_AVAILABLE,
            self.mock_mode,
        )

    async def plan_chat_query(
        self,
        nl_query: str,
        sources: List[Dict[str, Any]],
        recent_messages: List[ChatMessageRecord],
        session_summary: str,
    ) -> Dict[str, Any]:
        prompt = PLAN_PROMPT_TEMPLATE.format(
            nl_query=nl_query,
            sources_json=json.dumps(sources, indent=2),
            session_summary=session_summary or "None",
            recent_messages_json=json.dumps(
                [{"role": msg.role, "content": msg.content} for msg in recent_messages[-6:]],
                indent=2,
            ),
        )

        if self.client and not self.mock_mode:
            try:
                resp = self.client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                text = resp.choices[0].message.content
                start = text.find("[")
                end = text.rfind("]")
                parsed = json.loads(text[start : end + 1] if start != -1 and end != -1 else text)
                return {"plan": parsed, "raw": text}
            except Exception:
                logger.exception("Groq planning failed, falling back to heuristic.")

        return {"plan": self._heuristic_plan(nl_query, sources), "raw": None}

    def _heuristic_plan(self, nl_query: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deterministic schema-grounded fallback plan when the LLM is unavailable."""
        q = nl_query.lower()
        plan: List[Dict[str, Any]] = []
        node_id = 1

        def next_id() -> str:
            nonlocal node_id
            nid = f"p{node_id}"
            node_id += 1
            return nid

        def score_entity(source: Dict[str, Any], entity: Dict[str, Any]) -> int:
            score = 0
            entity_name = (entity.get("name") or "").lower()
            if entity_name and entity_name in q:
                score += 6
            for tag in entity.get("semantic_tags") or []:
                normalized_tag = tag.replace("entity:", "").replace("_", " ").lower()
                if normalized_tag and normalized_tag in q:
                    score += 4
            for field in entity.get("fields") or []:
                field_name = (field.get("name") or "").lower()
                if field_name and field_name in q:
                    score += 2
                for tag in field.get("semantic_tags") or []:
                    normalized_tag = tag.replace("_", " ").lower()
                    if normalized_tag and normalized_tag in q:
                        score += 1
            if source.get("db_type") == "sql":
                score += 1
            return score

        ranked: List[tuple[int, Dict[str, Any], Dict[str, Any]]] = []
        for source in sources:
            for entity in source.get("entities") or []:
                ranked.append((score_entity(source, entity), source, entity))

        ranked.sort(key=lambda item: item[0], reverse=True)

        best: Optional[tuple[Dict[str, Any], Dict[str, Any]]] = None
        if ranked and ranked[0][0] > 0:
            best = (ranked[0][1], ranked[0][2])
        else:
            for source in sources:
                if source.get("db_type") == "sql" and source.get("entities"):
                    best = (source, source["entities"][0])
                    break
            if best is None:
                for source in sources:
                    if source.get("entities"):
                        best = (source, source["entities"][0])
                        break

        if best is None:
            return plan

        source, entity = best
        output_key = entity["name"]

        if source.get("db_type") == "sql":
            fields = entity.get("fields") or []
            default_id = entity.get("default_id_field")
            if not default_id:
                for field in fields:
                    field_name = (field.get("name") or "").lower()
                    if field_name == "id" or field_name.endswith("_id"):
                        default_id = field["name"]
                        break

            projection: List[str] = []
            for candidate in ("id", "name", "title", "email", "description"):
                for field in fields:
                    if field.get("name") == candidate and candidate not in projection:
                        projection.append(candidate)
            for field in fields:
                name = field.get("name")
                if name and name not in projection:
                    projection.append(name)
                if len(projection) >= 5:
                    break
            if not projection:
                projection = ["*"]

            identifier = _extract_identifier(q)
            query = f"SELECT {', '.join(projection)} FROM {entity['name']}"
            params: Dict[str, Any] = {}
            if identifier and default_id:
                query += f" WHERE {default_id} = ?"
                params = {default_id: identifier}
                if output_key.endswith("s"):
                    output_key = output_key[:-1]
            query += " LIMIT 10"

            plan.append(
                {
                    "id": next_id(),
                    "description": f"Fetch rows from {entity['name']}",
                    "server_id": source["mcp_id"],
                    "tool_name": "query.sql",
                    "arguments": {"query": query, "params": params},
                    "depends_on": None,
                    "output_key": output_key,
                    "optional": False,
                }
            )
            return plan

        if source.get("db_type") == "nosql":
            plan.append(
                {
                    "id": next_id(),
                    "description": f"Fetch documents from {entity['name']}",
                    "server_id": source["mcp_id"],
                    "tool_name": "query.document",
                    "arguments": {"collection": entity["name"], "filter": {}, "limit": 10},
                    "depends_on": None,
                    "output_key": output_key,
                    "optional": False,
                }
            )
            return plan

        if source.get("db_type") == "graph":
            identifier = _extract_identifier(q)
            if identifier:
                plan.append(
                    {
                        "id": next_id(),
                        "description": f"Traverse graph from {identifier}",
                        "server_id": source["mcp_id"],
                        "tool_name": "query.graph",
                        "arguments": {"start": {"property": "id", "value": identifier}, "depth": 2},
                        "depends_on": None,
                        "output_key": output_key,
                        "optional": False,
                    }
                )
            return plan

        return plan

    def summarize_answer(
        self,
        nl_query: str,
        result_sets: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
    ) -> str:
        """Produce a human-readable summary of execution results."""
        failed = [rs for rs in result_sets if rs.get("meta", {}).get("error")]
        total_rows = sum(len(rs.get("items", [])) for rs in result_sets)

        if failed and total_rows == 0:
            errors = "; ".join(rs["meta"]["error"] for rs in failed)
            return f"Query failed: {errors}"

        parts = [f"Found {total_rows} records"]
        if failed:
            parts.append("but some steps failed")
            for rs in failed:
                parts.append(rs["meta"]["error"])

        data_lines = []
        for rs in result_sets:
            items = rs.get("items") or rs.get("result", [])
            if not items:
                continue
            key = rs.get("key") or rs.get("plan_node_id", "result")
            server = rs.get("server_id", "")
            row_count = len(items)
            display = items[:3]
            data_lines.append(f"- {key} from {server} ({row_count} rows)")
            for item in display:
                data_lines.append("  " + ", ".join(f"{k}={v}" for k, v in item.items()))
            if row_count > 3:
                data_lines.append(f"  ... {row_count - 3} more rows")

        summary = ": ".join(parts)
        if data_lines:
            summary += "\nData:\n" + "\n".join(data_lines)

        explain_lines = []
        for rs in result_sets:
            key = rs.get("key") or rs.get("plan_node_id", "result")
            server = rs.get("server_id", "")
            tool = rs.get("tool_name") or (rs.get("meta") or {}).get("source_type", "")
            explain_lines.append(f"- {key} from {server} via {tool}")
            err = (rs.get("meta") or {}).get("error")
            if err:
                explain_lines.append(f"- {key} failed on {server}: {err}")

        if explain_lines:
            summary += "\nExplain:\n" + "\n".join(explain_lines)

        return summary


def _extract_identifier(text: str) -> Optional[str]:
    match = re.search(r"\b[a-z]{2,10}\d+\b", text)
    return match.group(0) if match else None
