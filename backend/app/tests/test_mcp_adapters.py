# tests/test_mcp_adapters.py
import requests
import os
import pytest

SQL_URL = os.getenv("SQL_MCP_URL", "http://127.0.0.1:8001")
NOSQL_URL = os.getenv("NOSQL_MCP_URL", "http://127.0.0.1:8002")
GRAPH_URL = os.getenv("GRAPH_MCP_URL", "http://127.0.0.1:8003")
VECTOR_URL = os.getenv("VECTOR_MCP_URL", "http://127.0.0.1:8004")


def test_sql_adapter():
    r = requests.post(
        f"{SQL_URL}/execute_sql",
        json={"query": "SELECT id,name,email FROM customers LIMIT 5", "params": {}},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    rows = r.json().get("rows") or []
    assert len(rows) > 0


def test_nosql_adapter():
    r = requests.post(
        f"{NOSQL_URL}/find",
        json={"filter": {}, "limit": 5},
        timeout=10,
    )
    assert r.status_code == 200
    docs = r.json().get("docs") or []
    assert len(docs) > 0


def test_graph_adapter():
    r = requests.post(
        f"{GRAPH_URL}/traverse",
        json={"start_id": "cust010", "max_depth": 2},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json().get("data") or {}
    # depending on your adapter shape, might be nodes/edges
    assert isinstance(data, dict)


def test_vector_adapter():
    # simple vector search with dummy embedding
    r = requests.post(
        f"{VECTOR_URL}/search",
        json={"index": "customer_embeddings", "embedding": [0.1, 0.2, 0.3], "top_k": 3},
        timeout=10,
    )
    assert r.status_code == 200
    matches = r.json().get("matches") or []
    assert isinstance(matches, list)
