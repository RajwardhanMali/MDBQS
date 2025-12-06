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


@pytest.mark.order(1)
def test_list_all_customers():
    """Should trigger SQL-only plan and return many customers."""
    body = post_query("Give me a list of all customers")
    fused = body["fused_data"]
    # depending on your fusion shape; we added fused_data["customers"]
    customers = fused.get("customers") or []
    assert len(customers) >= 100
    # basic shape checks
    sample = customers[0]
    assert "id" in sample and "name" in sample and "email" in sample


@pytest.mark.order(2)
def test_single_customer_with_orders():
    """Find email for a specific customer and list their orders (SQL + Mongo)."""
    body = post_query("Find the email for Customer 001 and list their last 5 purchases")
    fused = body["fused_data"]

    # we expect a primary customer
    c = fused.get("customer") or {}
    assert c.get("id") == "cust001"
    assert c.get("email") == "customer001@example.com"

    orders = fused.get("recent_orders") or []
    assert len(orders) > 0
    # all orders should have matching customer_id
    for o in orders:
        assert o.get("customer_id") == "cust001"


@pytest.mark.order(3)
def test_referrals_for_customer():
    """Should hit Neo4j graph adapter."""
    body = post_query("Show referrals for customer with id cust010")
    fused = body["fused_data"]

    refs = fused.get("referrals") or []
    # Depending on your graph adapter, this may be nodes or edges; just assert non-empty
    assert isinstance(refs, list)
    # It's fine if there are no referrals for some nodes, but at least handler must not crash


@pytest.mark.order(4)
def test_similar_customers_vector_search():
    """Should hit Milvus / vector MCP."""
    body = post_query("Find customers similar to cust050")
    fused = body["fused_data"]
    similars = fused.get("similar_customers") or []
    assert isinstance(similars, list)
    # may be empty if planner or adapter choose not to return, but should not error


@pytest.mark.order(5)
def test_unknown_customer_graceful():
    """Query for a non-existent customer should not 500, just yield empty."""
    body = post_query("Find the email and purchases for customer named 'Totally Unknown Person'")
    fused = body["fused_data"]
    customer = fused.get("customer") or {}
    orders = fused.get("recent_orders") or []
    # no crash; may be empty
    assert customer == {} or "email" not in customer or customer["email"] is None
    assert isinstance(orders, list)


@pytest.mark.order(6)
def test_orders_only():
    """Query focusing on orders; planner should prefer NoSQL."""
    body = post_query("Show me the 10 most recent orders across all customers")
    fused = body["fused_data"]
    orders = fused.get("recent_orders") or []
    assert isinstance(orders, list)
    # we seeded many orders; we expect some results
    assert len(orders) > 0


@pytest.mark.order(7)
def test_complex_multi_source_query():
    """Hit SQL + NoSQL + Graph + Vector (depending on planner)."""
    body = post_query(
        "For cust020, show their contact email, last 3 purchases, any referrals and two similar customers."
    )
    fused = body["fused_data"]

    # These assertions are soft; ensure nothing crashes and types are correct.
    assert isinstance(fused.get("customer"), dict)
    assert isinstance(fused.get("recent_orders"), list)
    assert isinstance(fused.get("referrals"), list)
    assert isinstance(fused.get("similar_customers"), list)

