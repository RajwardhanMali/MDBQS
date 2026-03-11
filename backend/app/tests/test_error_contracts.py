import pytest

from app.core.llm.groq_client import GroqClient
from app.models.state import PlanStep
from app.services.execution import execute_plan_steps


@pytest.mark.asyncio
async def test_vector_invalid_embedding_is_short_circuited():
    steps = [
        PlanStep(
            id="p1",
            description="invalid vector step",
            server_id="vector_customers",
            tool_name="query.vector",
            arguments={"top_k": 3},
            output_key="similar_customers",
            optional=False,
        )
    ]

    result_sets, tool_calls = await execute_plan_steps(steps)
    assert len(result_sets) == 1
    assert result_sets[0].items == []
    assert result_sets[0].meta["error_code"] == "INVALID_VECTOR_INPUT"
    assert result_sets[0].meta["recoverable"] is True
    assert tool_calls[0]["meta"]["error_code"] == "INVALID_VECTOR_INPUT"


def test_answer_mentions_partial_failure():
    client = GroqClient(mock_mode=True)
    answer = client.summarize_answer(
        "find similar customers",
        [
            {
                "key": "customer",
                "server_id": "sql_customers",
                "items": [{"id": "cust020"}],
                "meta": {},
            },
            {
                "key": "similar_customers",
                "server_id": "vector_customers",
                "items": [],
                "meta": {
                    "error": "Embedding must have dimension 3",
                    "error_code": "INVALID_VECTOR_INPUT",
                    "recoverable": True,
                },
            },
        ],
        [],
    )
    assert "some steps failed" in answer.lower()
    assert "Embedding must have dimension 3" in answer
