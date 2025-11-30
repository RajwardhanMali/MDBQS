# app/core/llm/gemini_client.py
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Try to import official client
try:
    from google import genai
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

# A lightweight wrapper
class GeminiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if GENAI_AVAILABLE:
            # client will pick up API key from env or ADC
            self.client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        else:
            self.client = None

    async def plan_query(self, nl_query: str, schema_hints: List[str] | None = None) -> Dict[str, Any]:
        """Return a plan dict with nodes describing required capabilities.
        If the Gemini client is available, call it; otherwise use deterministic rules."""
        if self.client:
            # Use the client synchronously since the SDK may be blocking; wrap in coroutine where needed
            # We call a basic generate_content with a prompt that asks for JSON plan.
            prompt = (
                "You are a planner. Given a user's natural-language query, output a JSON array of plan nodes. "
                "Each node: {id, type, subquery_nl, capability, preferred, depends_on}. "
                f"User query: '''{nl_query}'''\n"
            )
            response = self.client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            # genai returns objects with .text or similar; adapt
            text = getattr(response, "text", None) or response
            # Try to parse JSON in text
            import json
            try:
                parsed = json.loads(text)
                return {"plan": parsed, "raw": text}
            except Exception:
                # fallback to mock rules
                pass

        # Deterministic mock planner
        plan = []
        idc = 1
        q = nl_query.lower()
        # Always create SQL customer lookup if 'customer' or 'email' mentioned
        if "customer" in q or "email" in q or "name" in q:
            plan.append({
                "id": f"p{idc}", "type": "lookup",
                "subquery_nl": "Find customer by name or id",
                "capability": "query.sql", "preferred": "sql_customers"
            })
            idc += 1
        if "order" in q or "purchase" in q or "purchases" in q:
            plan.append({
                "id": f"p{idc}", "type": "lookup",
                "subquery_nl": "Find recent orders for customer_id",
                "capability": "query.document", "preferred": "orders_mongo", "depends_on": "p1"
            })
            idc += 1
        if "refer" in q or "referral" in q or "friend" in q or "connection" in q:
            plan.append({
                "id": f"p{idc}", "type": "traverse",
                "subquery_nl": "Find referral neighbors for customer_id",
                "capability": "query.graph", "preferred": "graph_referrals", "depends_on": "p1"
            })
            idc += 1
        if "similar" in q or "similar customers" in q or "similar customers" in q:
            plan.append({
                "id": f"p{idc}", "type": "similarity",
                "subquery_nl": "Find top-2 similar customers by embedding",
                "capability": "query.vector", "preferred": "vector_customers", "depends_on": "p1"
            })
            idc += 1

        return {"plan": plan, "raw": None}
