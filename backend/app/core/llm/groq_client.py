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

Return ONLY JSON: an array of plan steps.

Each step must contain:
- id
- description
- server_id
- tool_name
- arguments
- depends_on
- output_key
- optional

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

        return {"plan": self._heuristic_plan(nl_query, sources, recent_messages), "raw": None}

    def summarize_answer(self, user_message: str, result_sets: List[Dict[str, Any]], explain: List[str]) -> str:
        if not result_sets:
            return f"No matching data was found for: {user_message}"

        error_sets = [result_set for result_set in result_sets if (result_set.get("meta") or {}).get("error")]
        success_sets = [
            result_set
            for result_set in result_sets
            if len(result_set.get("items", [])) > 0 and not (result_set.get("meta") or {}).get("error")
        ]

        if error_sets and not success_sets:
            first_error = (error_sets[0].get("meta") or {}).get("error", "The query failed.")
            return f"Some steps failed: {first_error}"

        if error_sets and success_sets:
            total = sum(len(rs.get("items", [])) for rs in success_sets)
            first_error = (error_sets[0].get("meta") or {}).get("error", "A secondary step failed.")
            return f"Found {total} records, but some steps failed: {first_error}"

        first = result_sets[0]
        count = len(first.get("items", []))
        if count == 0:
            return f"No matching data was found for: {user_message}"

        if count == 1:
            item = first["items"][0]
            formatted = ", ".join(
                f"{key}={value}"
                for key, value in item.items()
                if value is not None and not isinstance(value, (list, dict))
            )
            if formatted:
                return formatted
            return f"Found 1 result from {first['server_id']} for: {user_message}"
        return f"Found {sum(len(rs.get('items', [])) for rs in result_sets)} records across {len(result_sets)} result sets."

    def _heuristic_plan(
        self,
        nl_query: str,
        sources: List[Dict[str, Any]],
        recent_messages: List[ChatMessageRecord],
    ) -> List[Dict[str, Any]]:
        q = nl_query.lower()
        node_id = 1
        plan: List[Dict[str, Any]] = []

        def next_id() -> str:
            nonlocal node_id
            value = f"p{node_id}"
            node_id += 1
            return value

        def source_by_tool(tool_name: str) -> Optional[Dict[str, Any]]:
            for source in sources:
                if tool_name in source.get("tools", []):
                    return source
            return None

        recent_text = " ".join(message.content.lower() for message in recent_messages[-4:])
        merged_q = f"{recent_text} {q}".strip()

        if "similar" in merged_q or "embedding" in merged_q:
            vector_source = source_by_tool("query.vector")
            sql_source = source_by_tool("query.sql")
            if sql_source and vector_source:
                step1 = next_id()
                customer_id = _extract_identifier(merged_q) or "cust001"
                plan.append(
                    {
                        "id": step1,
                        "description": "Fetch reference entity for vector similarity",
                        "server_id": sql_source["mcp_id"],
                        "tool_name": "query.sql",
                        "arguments": {
                            "query": "SELECT id,name,email,embedding FROM customers WHERE id = ? LIMIT 1",
                            "params": {"id": customer_id},
                        },
                        "depends_on": None,
                        "output_key": "customer",
                        "optional": False,
                    }
                )
                plan.append(
                    {
                        "id": next_id(),
                        "description": "Search similar entities",
                        "server_id": vector_source["mcp_id"],
                        "tool_name": "query.vector",
                        "arguments": {"embedding_from": f"{step1}.embedding", "top_k": 3},
                        "depends_on": step1,
                        "output_key": "similar_customers",
                        "optional": True,
                    }
                )
                return plan

        if any(word in merged_q for word in ["referral", "referrals", "referal", "referals", "referred"]):
            graph_source = source_by_tool("query.graph")
            if graph_source:
                customer_id = _extract_identifier(merged_q) or "cust010"
                plan.append(
                    {
                        "id": next_id(),
                        "description": "Traverse graph referrals",
                        "server_id": graph_source["mcp_id"],
                        "tool_name": "query.graph",
                        "arguments": {"start": {"property": "id", "value": customer_id}, "depth": 2},
                        "depends_on": None,
                        "output_key": "referrals",
                        "optional": False,
                    }
                )
                return plan

        mentions_orders = any(word in merged_q for word in ["order", "purchase"])
        mentions_customer = any(word in merged_q for word in ["customer", "client", "email", "contact", "cust"])
        mentions_all = "all customers" in merged_q or "list customers" in merged_q or "list of all customers" in merged_q

        sql_source = source_by_tool("query.sql")
        doc_source = source_by_tool("query.document")

        if mentions_customer and sql_source:
            customer_id = _extract_identifier(merged_q)
            person_name = _extract_quoted_name(nl_query)
            query = "SELECT id,name,email,embedding FROM customers LIMIT 1"
            params: Dict[str, Any] = {}
            output_key = "customer"
            if mentions_all:
                query = "SELECT id,name,email FROM customers ORDER BY id"
                output_key = "customers"
            elif customer_id:
                query = "SELECT id,name,email,embedding FROM customers WHERE id = ? LIMIT 1"
                params = {"id": customer_id}
            elif person_name:
                query = "SELECT id,name,email,embedding FROM customers WHERE name ILIKE ? LIMIT 1"
                params = {"name": person_name}

            sql_step = next_id()
            plan.append(
                {
                    "id": sql_step,
                    "description": "Fetch matching structured records",
                    "server_id": sql_source["mcp_id"],
                    "tool_name": "query.sql",
                    "arguments": {"query": query, "params": params},
                    "depends_on": None,
                    "output_key": output_key,
                    "optional": False,
                }
            )
            if mentions_orders and doc_source and not mentions_all:
                plan.append(
                    {
                        "id": next_id(),
                        "description": "Fetch related documents",
                        "server_id": doc_source["mcp_id"],
                        "tool_name": "query.document",
                        "arguments": {"collection": "orders", "customer_id_from": f"{sql_step}.id", "limit": 5},
                        "depends_on": sql_step,
                        "output_key": "recent_orders",
                        "optional": True,
                    }
                )
            return plan

        if mentions_orders and doc_source:
            plan.append(
                {
                    "id": next_id(),
                    "description": "Fetch documents",
                    "server_id": doc_source["mcp_id"],
                    "tool_name": "query.document",
                    "arguments": {"collection": "orders", "filter": {}, "limit": 10},
                    "depends_on": None,
                    "output_key": "recent_orders",
                    "optional": False,
                }
            )
            return plan

        if sql_source:
            plan.append(
                {
                    "id": next_id(),
                    "description": "Fallback structured lookup",
                    "server_id": sql_source["mcp_id"],
                    "tool_name": "query.sql",
                    "arguments": {"query": "SELECT id,name,email FROM customers LIMIT 5", "params": {}},
                    "depends_on": None,
                    "output_key": "results",
                    "optional": False,
                }
            )
        return plan


def _extract_identifier(text: str) -> Optional[str]:
    match = re.search(r"\bcust\d+\b", text)
    return match.group(0) if match else None


def _extract_quoted_name(text: str) -> Optional[str]:
    if "'" in text:
        parts = text.split("'")
        if len(parts) >= 3:
            return parts[1]
    return None
