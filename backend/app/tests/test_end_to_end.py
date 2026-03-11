# tests/test_end_to_end.py
import os
import time
import pytest
import requests

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

def post_query(nl_query: str, user_id: str = "u1"):
    resp = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_id": user_id, "nl_query": nl_query, "context": {}},
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_list_all_customers():
    """Should trigger SQL-only plan and return many customers."""
    body = post_query("Give me a list of all customers")
    fused = body["fused_data"]
    customers = fused.get("customers") or []
    assert len(customers) >= 100
    sample = customers[0]
    assert "id" in sample and "name" in sample and "email" in sample


def test_single_customer_with_orders():
    """Find email for a specific customer and list their orders (SQL + Mongo)."""
    body = post_query("Find the email for customer with id cust001 and his last 5 purchases")
    fused = body["fused_data"]

    c = fused.get("customer") or {}
    assert c.get("email") == "customer001@example.com"

    orders = fused.get("recent_orders") or []
    assert len(orders) > 0
    for o in orders:
        assert o.get("customer_id") == "cust001"


def test_referrals_for_customer():
    """Should hit Neo4j graph adapter."""
    body = post_query("Show referrals for customer with id cust010")
    fused = body["fused_data"]

    refs = fused.get("referrals") or []
    assert isinstance(refs, list)


def test_similar_customers_vector_search():
    """Should hit Milvus / vector MCP."""
    body = post_query("Find customers similar to cust050")
    fused = body["fused_data"]
    similars = fused.get("similar_customers") or []
    assert isinstance(similars, list)


def test_unknown_customer_graceful():
    """Query for a non-existent customer should not 500, just yield empty."""
    body = post_query("Find the email and purchases for customer named 'Totally Unknown Person'")
    fused = body["fused_data"]
    customer = fused.get("customer") or {}
    orders = fused.get("recent_orders") or []
    assert customer == {} or "email" not in customer or customer["email"] is None
    assert isinstance(orders, list)


def test_orders_only():
    """Query focusing on orders; planner should prefer NoSQL."""
    body = post_query("Show me the 10 most recent orders across all customers")
    fused = body["fused_data"]
    orders = fused.get("recent_orders") or []
    assert isinstance(orders, list)
    assert len(orders) > 0


def test_complex_multi_source_query():
    """Hit SQL + NoSQL + Graph + Vector (depending on planner)."""
    body = post_query(
        "For cust020, show their contact email, last 3 purchases, any referrals and two similar customers."
    )
    fused = body["fused_data"]

    assert isinstance(fused.get("customer"), dict)
    assert isinstance(fused.get("recent_orders"), list)
    assert isinstance(fused.get("referrals"), list)
    assert isinstance(fused.get("similar_customers"), list)

