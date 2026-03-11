# app/core/llm/groq_client.py
import os
import json
import logging
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

logger = logging.getLogger("groq_client")

load_dotenv()

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False


PLAN_PROMPT_TEMPLATE = """
You are a query planning agent for a multi-database system.

You receive:
1. The user's natural language query.
2. A list of available data sources ("MCPs"). Each source has:
   - mcp_id: unique identifier
   - db_type: "sql" | "nosql" | "graph" | "vector"
   - tools: tools you can call, e.g. "execute_sql", "find", "traverse", "search"
   - entities: logical entities with tags and fields.

You must return ONLY JSON: an array of plan steps.

Each step MUST be a JSON object with:
- id: "p1", "p2", ...
- description: short human-readable description of the step.
- mcp_id: which MCP/source to call.
- db_type: copy of the source's db_type.
- tool: one of the tools exposed by that MCP. Examples:
    - SQL: "execute_sql"
    - NoSQL: "find"
    - Graph: "traverse"
    - Vector: "search"
- input: JSON object describing the payload for that tool.
  * For execute_sql: {{"query": "...", "params": {{...}}}}  (ONLY SELECT queries allowed).
  * For find: {{"filter": {{...}}, "limit": N, "sort": {{...}} }}.
  * For traverse: {{
        "start": {{
          "property": "id",
          "value": "<customer_id>"   // e.g. "cust010"
        }},
        "rel": "REFERRED",           // always use this unless explicitly stated
        "depth": 1                   // default traversal depth
      }}.
  * For search: {{"embedding": [0.1, 0.2, ...], "top_k": N}}  // embedding is an array of floats
    or {{"embedding_from": "p1.embedding", "top_k": N}}.
- depends_on: optional id of another step whose results are needed.
- output_alias: You MUST set output_alias for every step. Use values like "customers", "customer", "recent_orders", "referrals", "similar_customers" whenever appropriate.
- optional: optional boolean. If true and its dependency has no results, this step may be skipped.

Rules:
- Use the MINIMUM number of steps necessary to answer the query.
- Use only ? as a placeholder for sql queries.
- Only call sources that are relevant to the query.
- If the query only needs customer details, don't call orders or graph or vector.
- If the query needs similar customers, use the vector source if available.
- For vector search, you MUST provide a valid embedding array of floats, not strings or IDs.
- If you reference previous step results in input (e.g. "embedding_from"),
  use the pattern "p1.embedding" (step id followed by fields joined by dots).
- Always ensure the input matches the expected format for each tool.

User query:
{nl_query}

Available sources:
{sources_json}

Return ONLY a JSON array, no extra text.
"""

class GroqClient:
    def __init__(self, api_key: Optional[str] = None, mock_mode: bool = False):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.mock_mode = mock_mode or (not GROQ_AVAILABLE)
        if GROQ_AVAILABLE and not self.mock_mode:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None
        logger.info(
            "GroqClient initialized (GROQ_AVAILABLE=%s, mock_mode=%s)",
            GROQ_AVAILABLE,
            self.mock_mode,
        )

    async def plan_query(
        self,
        nl_query: str,
        entity_candidates: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for planning. Prefer 'sources' for the new dynamic planner.
        'entity_candidates' is kept only for backward-compat / fallback.
        """
        sources = sources or []
        prompt = PLAN_PROMPT_TEMPLATE.format(
            nl_query=nl_query,
            sources_json=json.dumps(sources, indent=2),
        )

        logger.info("Planning query via GroqClient (mock_mode=%s)", self.mock_mode)

        if self.client and not self.mock_mode:
            try:
                resp = self.client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                text = resp.choices[0].message.content

                import re
                m = re.search(r'(\[.*\])', text, re.S)
                json_text = m.group(1) if m else text
                parsed = json.loads(json_text)
                return {"plan": parsed, "raw": text}
            except Exception as e:
                logger.exception("Groq planning failed, falling back to heuristic. err=%s", e)

        # fallback: simple heuristic using entity_candidates, if provided
        return {"plan": self._heuristic_plan(nl_query, entity_candidates or []), "raw": None}

    def _heuristic_plan(self, nl_query: str, entity_candidates: List[Dict[str, Any]]):
        """
        Very simple deterministic fallback if Groq is unavailable.
        We keep this minimal: basic "list customers" or "find customer" in SQL.
        """
        q = nl_query.lower()
        plan: List[Dict[str, Any]] = []
        node_id = 1

        def next_id():
            nonlocal node_id
            nid = f"p{node_id}"
            node_id += 1
            return nid

        # crude intent detection
        mentions_customer = "customer" in q or "client" in q
        mentions_all = "all customers" in q or "list of all customers" in q

        # find any SQL customer candidate
        customer_sql = None
        for c in entity_candidates:
            if c.get("db_type") == "sql" and "entity:customer" in c.get("entity_tags", []):
                customer_sql = c
                break

        if mentions_customer and customer_sql:
            if mentions_all:
                plan.append(
                    {
                        "id": next_id(),
                        "description": "List all customers",
                        "mcp_id": customer_sql["mcp_id"],
                        "db_type": "sql",
                        "tool": "execute_sql",
                        "input": {
                            "query": f"SELECT id,name,email FROM {customer_sql['entity']} ORDER BY id",
                        },
                    }
                )
            else:
                plan.append(
                    {
                        "id": next_id(),
                        "description": "Get one customer",
                        "mcp_id": customer_sql["mcp_id"],
                        "db_type": "sql",
                        "tool": "execute_sql",
                        "input": {
                            "query": f"SELECT id,name,email FROM {customer_sql['entity']} LIMIT 1",
                        },
                    }
                )
        return plan
