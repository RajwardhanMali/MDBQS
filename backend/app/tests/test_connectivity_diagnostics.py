import os

import requests

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
SQL_URL = os.getenv("SQL_MCP_URL", "http://127.0.0.1:8001")
GRAPH_URL = os.getenv("GRAPH_MCP_URL", "http://127.0.0.1:8003")
VECTOR_URL = os.getenv("VECTOR_MCP_URL", "http://127.0.0.1:8004")


def test_sql_embedding_lookup_connectivity():
    resp = requests.post(
        f"{SQL_URL}/mcp/tools/call",
        json={
            "name": "query.sql",
            "arguments": {"query": "SELECT embedding FROM customers WHERE id = ? LIMIT 1", "params": {"id": "cust020"}},
        },
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["structured_content"]["items"]
    assert len(items) == 1
    assert isinstance(items[0]["embedding"], list)
    assert len(items[0]["embedding"]) == 3


def test_vector_similarity_search_connectivity():
    resp = requests.post(
        f"{VECTOR_URL}/mcp/tools/call",
        json={
            "name": "query.vector",
            "arguments": {"collection": "customer_embeddings", "embedding": [0.9565, 0.704, 0.0], "top_k": 3},
        },
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["structured_content"]["items"]
    assert len(items) > 0


def test_graph_referral_traverse_connectivity():
    resp = requests.post(
        f"{GRAPH_URL}/mcp/tools/call",
        json={
            "name": "query.graph",
            "arguments": {"start": {"property": "id", "value": "cust020"}, "depth": 2},
        },
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_error"] is False
    assert isinstance(body["structured_content"]["items"], list)


def test_vector_filter_lookup_shape_is_supported():
    resp = requests.post(
        f"{VECTOR_URL}/mcp/tools/call",
        json={
            "name": "query.vector",
            "arguments": {
                "filter": {"cust_id": "cust048"},
                "fields": ["cust_id", "embedding", "name", "email"],
                "limit": 1,
                "collection": "customer_embeddings",
            },
        },
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["structured_content"]["items"]
    assert len(items) == 1
    assert items[0]["cust_id"] == "cust048"
    assert isinstance(items[0]["embedding"], list)


def test_graph_query_key_shape_is_supported():
    resp = requests.post(
        f"{GRAPH_URL}/mcp/tools/call",
        json={
            "name": "query.graph",
            "arguments": {
                "query": "MATCH (c:Customer {id: 'cust048'})-[r:REFERRED]->(referred:Customer) RETURN referred.id AS id, referred.name AS name, referred.email AS email"
            },
        },
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_error"] is False
    assert isinstance(body["structured_content"]["items"], list)


def test_backend_chat_vector_query_returns_results():
    session = requests.post(
        f"{BASE_URL}/api/v1/sessions",
        json={"user_id": "diag_user", "title": "diagnostics"},
        timeout=15,
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["session_id"]

    resp = requests.post(
        f"{BASE_URL}/api/v1/chat",
        json={
            "session_id": session_id,
            "user_id": "diag_user",
            "message": "show me people with same liking as customer with id cust048",
            "source_ids": [],
        },
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    vector_steps = [step for step in body["trace"]["plan"] if step["tool_name"] == "query.vector"]
    assert len(vector_steps) >= 1
    assert any(rs["key"] == "similar_customers" and len(rs["items"]) > 0 for rs in body["result_sets"])
