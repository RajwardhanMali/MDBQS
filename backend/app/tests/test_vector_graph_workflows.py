import os

import requests

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")


def create_session(user_id: str = "workflow_user") -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/sessions",
        json={"user_id": user_id, "title": "workflow tests"},
        timeout=15,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def chat(session_id: str, message: str, user_id: str = "workflow_user"):
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "source_ids": [],
        },
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_vector_similarity_workflow_returns_rows_and_formatted_answer():
    session_id = create_session()
    body = chat(session_id, "show me similar customers to customer id cust020")

    similar_sets = [rs for rs in body["result_sets"] if rs["key"] == "similar_customers"]
    assert similar_sets, body
    assert len(similar_sets[0]["items"]) > 0, body
    assert "No matching data was found" not in body["answer"]
    assert any("similar_customers" in line for line in body["explain"])


def test_graph_referral_workflow_returns_rows_and_formatted_answer():
    session_id = create_session()
    body = chat(session_id, "show me all referals of cust048")

    referral_sets = [rs for rs in body["result_sets"] if rs["key"] == "referrals"]
    assert referral_sets, body
    assert len(referral_sets[0]["items"]) > 0, body
    assert "No matching data was found" not in body["answer"]
    assert any("referrals" in line for line in body["explain"])
