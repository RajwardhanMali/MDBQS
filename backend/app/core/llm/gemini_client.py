# app/core/llm/gemini_client.py
import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gemini_client")
logger.setLevel(logging.INFO)

# try to load google genai
try:
    from google import genai
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

# Example few-shot prompt for the LLM to output a JSON plan
PLAN_PROMPT_TEMPLATE = """
You are a planner that converts a user's natural language query into a structured JSON plan.
Return ONLY valid JSON (no surrounding explanation). The output should be an array of plan nodes.
Each node must include these fields:
- id: string (unique)
- intent: short description of the intent of this node (e.g., "list_customers", "get_recent_orders")
- capability: one of ["query.sql","query.document","query.graph","query.vector"]
- reason: short text why this capability is needed for the user's query
- confidence: number between 0.0 and 1.0 (assistant confidence the node is needed)
- native_query: OPTIONAL string describing the native query to run (e.g., "SELECT id,name FROM customers LIMIT 100")
- depends_on: OPTIONAL id of another node this node depends on

Examples:

#1
User: "Give me a list of all customers"
Plan:
[
  {{
    "id":"p1",
    "intent":"list_customers",
    "capability":"query.sql",
    "reason":"customers are stored in SQL table 'customers' with full records",
    "confidence":0.95,
    "native_query":"SELECT id,name,email FROM customers"
  }}
]

#2
User: "Find the email for 'Alice Kumar' and list her last 5 purchases"
Plan:
[
  {{
    "id":"p1",
    "intent":"find_customer_by_name",
    "capability":"query.sql",
    "reason":"customer identities and contact info are canonical in SQL",
    "confidence":0.95,
    "native_query":"SELECT id,name,email,embedding FROM customers WHERE name ILIKE '%Alice Kumar%' LIMIT 1"
  }},
  {{
    "id":"p2",
    "intent":"list_recent_orders",
    "capability":"query.document",
    "reason":"orders are stored in NoSQL collection 'orders' by customer_id",
    "confidence":0.9,
    "depends_on":"p1",
    "native_query":"find orders where customer_id = <p1.id> sort by order_date desc limit 5"
  }},
  {{
    "id":"p3",
    "intent":"similar_customers",
    "capability":"query.vector",
    "reason":"find similar customers using embeddings index",
    "confidence":0.65,
    "depends_on":"p1",
    "native_query":"vector search using embedding from p1"
  }}
]

Now produce a plan for this user query. Also include a short 'schema_hints' list argument that describes which MCPs (sql, nosql, graph, vector) and top fields we have available.
User: \"{nl_query}\"
Schema hints: {schema_hints}
Return JSON only.
"""

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, mock_mode: bool = False):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.mock_mode = mock_mode or (not GENAI_AVAILABLE)
        if GENAI_AVAILABLE and not mock_mode:
            self.client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        else:
            self.client = None
        logger.info("GeminiClient initialized (GENAI_AVAILABLE=%s, mock_mode=%s)", GENAI_AVAILABLE, self.mock_mode)

    async def plan_query(self, nl_query: str, schema_hints: List[Dict[str,Any]] | None = None) -> Dict[str, Any]:
        """
        Return a dict: { "plan": [ {..nodes..} ], "raw": raw_text }
        If Gemini is available, call it. Otherwise use deterministic fallback.
        """
        schema_hints = schema_hints or []
        prompt = PLAN_PROMPT_TEMPLATE.format(nl_query=nl_query, schema_hints=json.dumps(schema_hints))
        logger.debug("Planner prompt: %s", prompt)

        if self.client and not self.mock_mode:
            try:
                # Use model that supports text generation. We expect a JSON blob back.
                response = self.client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                # response handling depends on genai SDK version: try to extract text
                text = getattr(response, "text", None) or str(response)
                # Try to locate a JSON substring in the text
                import re
                m = re.search(r'(\[.*\])', text, re.S)
                json_text = m.group(1) if m else text
                parsed = json.loads(json_text)
                return {"plan": parsed, "raw": text}
            except Exception as e:
                logger.exception("Gemini planning failed, falling back to heuristic. err=%s", e)

        # Deterministic fallback: schema-aware heuristic planner
        return {"plan": self._heuristic_plan(nl_query, schema_hints), "raw": None}

    def _heuristic_plan(self, nl_query: str, schema_hints: List[Dict[str,Any]]):
        q = nl_query.lower()
        plan = []
        node_id = 1

        # simple intent detectors
        is_list_customers = any(phrase in q for phrase in ["list of all customers", "all customers", "list all customers", "give me a list of all customers"])
        mentions_customer = any(word in q for word in ["customer","customers","client","clients","email","name"])
        mentions_orders = any(word in q for word in ["order","orders","purchase","purchases"])
        mentions_graph = any(word in q for word in ["referral","referred","connections","friends"])
        mentions_similar = any(word in q for word in ["similar","similar customers","find similar"])

        # Schema-aware: check schema_hints to see where 'name' or 'email' lives
        has_sql_customer = False
        has_nosql_orders = False
        has_graph = False
        has_vector = False
        for s in schema_hints:
            stype = s.get("mcp_id","").lower()
            if "sql" in stype or "customers" in stype:
                has_sql_customer = True
            if "orders" in stype or "mongo" in stype:
                has_nosql_orders = True
            if "graph" in stype:
                has_graph = True
            if "vector" in stype or "emb" in stype:
                has_vector = True

        # Heuristics
        if is_list_customers or (mentions_customer and not mentions_orders and not mentions_graph):
            if has_sql_customer:
                plan.append({
                    "id": f"p{node_id}",
                    "intent": "list_customers",
                    "capability":"query.sql",
                    "reason":"SQL has canonical customers table",
                    "confidence": 0.95,
                    "native_query": "SELECT id,name,email FROM customers"
                })
                node_id += 1
                return plan
            # fallback to vector/graph if SQL absent
            if has_nosql_orders:
                plan.append({
                    "id": f"p{node_id}",
                    "intent": "list_customers_from_orders",
                    "capability":"query.document",
                    "reason":"No direct SQL; derive customer list from orders collection",
                    "confidence": 0.8,
                    "native_query":"distinct customer_id from orders"
                })
                node_id += 1
                return plan

        # If mentions orders explicitly
        if mentions_orders and has_nosql_orders:
            plan.append({
                "id": f"p{node_id}",
                "intent":"list_recent_orders",
                "capability":"query.document",
                "reason":"Orders stored in NoSQL",
                "confidence":0.9,
                "native_query":"find orders filter by customer_id if provided else recent orders limit 20"
            })
            node_id+=1

        if mentions_graph and has_graph:
            plan.append({
                "id": f"p{node_id}",
                "intent":"graph_traverse",
                "capability":"query.graph",
                "reason":"graph contains referrals/connections",
                "confidence":0.85,
                "native_query":"traverse referral edges for customer"
            })
            node_id+=1

        if mentions_similar and has_vector:
            plan.append({
                "id": f"p{node_id}",
                "intent":"vector_similarity",
                "capability":"query.vector",
                "reason":"vector embeddings exist for similarity searches",
                "confidence":0.7,
                "native_query":"vector search using customer embedding"
            })
            node_id+=1

        # if nothing matched, fallback to a conservative SQL lookup if available
        if not plan and has_sql_customer:
            plan.append({
                "id": "p1",
                "intent": "conservative_customer_lookup",
                "capability": "query.sql",
                "reason": "conservative default: look in SQL customers for anything related to users",
                "confidence": 0.5,
                "native_query": "SELECT id,name,email FROM customers LIMIT 50"
            })
        return plan
