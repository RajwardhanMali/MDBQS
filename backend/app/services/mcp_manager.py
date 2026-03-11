from __future__ import annotations

from typing import Any, Dict, List

from app.models.state import McpServerDescriptor
from app.services.mcp_runtime import McpRuntime

MCP_REGISTRY: Dict[str, Dict[str, Any]] = {}

DEFAULT_MCP_MANIFESTS: List[Dict[str, Any]] = [
    {"id": "sql_customers", "host": "http://localhost:8001", "capabilities": ["query.sql"]},
    {"id": "orders_mongo", "host": "http://localhost:8002", "capabilities": ["query.document"]},
    {"id": "graph_referrals", "host": "http://localhost:8003", "capabilities": ["query.graph"]},
    {"id": "vector_customers", "host": "http://localhost:8004", "capabilities": ["query.vector"]},
]

AUTO_REGISTER_DEFAULTS_ON_IMPORT = True

runtime = McpRuntime()

LEGACY_OPERATION_TO_TOOL = {
    "execute_sql": "query.sql",
    "find": "query.document",
    "traverse": "query.graph",
    "search": "query.vector",
}


def _descriptor_from_manifest(manifest: Dict[str, Any]) -> McpServerDescriptor:
    return McpServerDescriptor(
        server_id=manifest["id"],
        base_url=manifest["host"],
        capabilities=manifest.get("capabilities", []),
        metadata={k: v for k, v in manifest.items() if k not in {"id", "host", "capabilities"}},
    )


def register_mcp(manifest: Dict[str, Any]):
    MCP_REGISTRY[manifest["id"]] = manifest
    runtime.register_server(_descriptor_from_manifest(manifest))
    return manifest


def register_default_manifests():
    for manifest in DEFAULT_MCP_MANIFESTS:
        if manifest["id"] not in MCP_REGISTRY:
            register_mcp(manifest)


async def init_managers(settings=None, register_defaults: bool = False):
    if register_defaults:
        register_default_manifests()
    await runtime.hydrate_all()


async def fetch_schema(manifest: Dict[str, Any]):
    server_id = manifest["id"]
    return await runtime.read_json_resource(server_id, f"schema://{server_id}")


async def call_execute(mcp_id: str, operation: str, payload: Dict[str, Any]):
    if operation == "get_schema":
        return await runtime.read_json_resource(mcp_id, f"schema://{mcp_id}")

    tool_name = LEGACY_OPERATION_TO_TOOL.get(operation, operation)
    result = await runtime.invoke_tool(mcp_id, tool_name, payload)
    structured = result.structured_content
    items = structured.get("items", [])
    meta = structured.get("meta", {})

    if tool_name == "query.document":
        return {"docs": items, "meta": meta}
    if tool_name == "query.vector":
        return {"matches": items, "meta": meta}
    return {"rows": items, "meta": meta, "data": {"items": items, "meta": meta}}


if AUTO_REGISTER_DEFAULTS_ON_IMPORT:
    register_default_manifests()
