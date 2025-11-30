from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_query_endpoint():
    resp = client.post("/api/v1/query", json={"query": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data and "result" in data
