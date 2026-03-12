import pytest

from app.core.llm.groq_client import GroqClient
from app.models.state import McpToolResult
from app.models.state import PlanStep
from app.services.execution import execute_plan_steps
from app.services import fusion, mcp_manager
from app.models.state import ExecutionResultSet


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


@pytest.mark.asyncio
async def test_nested_sql_placeholders_resolve_to_dependency_values(monkeypatch):
    captured_arguments = {}

    async def fake_invoke_tool(server_id, tool_name, arguments):
        nonlocal captured_arguments
        if tool_name == "query.document":
            return McpToolResult(
                structured_content={
                    "items": [
                        {"customer_id": "cust001"},
                        {"customer_id": "cust002"},
                    ],
                    "meta": {"source_id": server_id, "source_type": tool_name},
                }
            )
        captured_arguments = arguments
        return McpToolResult(
            structured_content={
                "items": [
                    {"id": "cust001", "name": "Customer 001"},
                    {"id": "cust002", "name": "Customer 002"},
                ],
                "meta": {"source_id": server_id, "source_type": tool_name},
            }
        )

    monkeypatch.setattr(mcp_manager.runtime, "invoke_tool", fake_invoke_tool)

    steps = [
        PlanStep(
            id="p1",
            description="find customers with more than 5 orders",
            server_id="orders_mongo",
            tool_name="query.document",
            arguments={"collection": "orders"},
            output_key="cust_ids",
            optional=False,
        ),
        PlanStep(
            id="p2",
            description="load customer details",
            server_id="sql_customers",
            tool_name="query.sql",
            arguments={
                "query": "SELECT id, name FROM customers WHERE id = ANY(?)",
                "params": {"ids": "{{cust_ids}}"},
            },
            depends_on="p1",
            output_key="customer_details",
            optional=False,
        ),
    ]

    result_sets, tool_calls = await execute_plan_steps(steps)
    assert len(result_sets) == 2
    assert captured_arguments["params"]["ids"] == ["cust001", "cust002"]
    assert tool_calls[1]["arguments"]["params"]["ids"] == ["cust001", "cust002"]


@pytest.mark.asyncio
async def test_sql_from_arguments_are_merged_into_params(monkeypatch):
    captured_arguments = {}

    async def fake_invoke_tool(server_id, tool_name, arguments):
        nonlocal captured_arguments
        if tool_name == "query.document":
            return McpToolResult(
                structured_content={
                    "items": [{"id": "cust001"}, {"id": "cust002"}],
                    "meta": {"source_id": server_id, "source_type": tool_name},
                }
            )
        captured_arguments = arguments
        return McpToolResult(
            structured_content={
                "items": [],
                "meta": {"source_id": server_id, "source_type": tool_name},
            }
        )

    monkeypatch.setattr(mcp_manager.runtime, "invoke_tool", fake_invoke_tool)

    steps = [
        PlanStep(
            id="p1",
            description="seed ids",
            server_id="orders_mongo",
            tool_name="query.document",
            arguments={"collection": "orders"},
            output_key="orders",
            optional=False,
        ),
        PlanStep(
            id="p2",
            description="lookup matching rows",
            server_id="sql_customers",
            tool_name="query.sql",
            arguments={
                "query": "SELECT id FROM customers WHERE id IN (?)",
                "record_ids_from": "p1.id",
            },
            depends_on="p1",
            output_key="customers",
            optional=False,
        ),
    ]

    _result_sets, tool_calls = await execute_plan_steps(steps)
    assert captured_arguments["params"]["record_ids"] == ["cust001", "cust002"]
    assert tool_calls[1]["arguments"]["params"]["record_ids"] == ["cust001", "cust002"]


def test_schema_grounded_heuristic_plan_is_not_hardcoded_to_customers():
    client = GroqClient(mock_mode=True)
    sources = [
        {
            "mcp_id": "sql_library",
            "db_type": "sql",
            "tools": ["query.sql"],
            "entities": [
                {
                    "name": "books",
                    "kind": "table",
                    "default_id_field": "book_id",
                    "semantic_tags": ["entity:book", "catalog"],
                    "fields": [
                        {"name": "book_id", "type": "text", "semantic_tags": ["id"]},
                        {"name": "title", "type": "text", "semantic_tags": ["title"]},
                        {"name": "author", "type": "text", "semantic_tags": ["author"]},
                    ],
                }
            ],
        }
    ]

    plan = client._heuristic_plan("list books", sources)
    assert len(plan) == 1
    assert plan[0]["server_id"] == "sql_library"
    assert "FROM books" in plan[0]["arguments"]["query"]
    assert "customers" not in plan[0]["arguments"]["query"].lower()


def test_fused_data_keeps_generic_result_keys():
    result_sets = [
        ExecutionResultSet(
            key="books",
            server_id="sql_library",
            tool_name="query.sql",
            items=[{"book_id": "b1", "title": "Example"}],
            meta={},
        )
    ]

    fused_data = fusion.compatibility_fused_data(result_sets, nl_query="list books")
    assert fused_data["books"] == [{"book_id": "b1", "title": "Example"}]
