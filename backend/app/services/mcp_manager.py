import httpx
from typing import Dict, Any, List

MCP_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Defaults you asked to add — safe static manifests for local/dev testing
DEFAULT_MCP_MANIFESTS: List[Dict[str, Any]] = [
    {"id": "sql_customers", "host": "http://localhost:8001", "capabilities": ["query.sql"]},
    {"id": "orders_mongo", "host": "http://localhost:8002", "capabilities": ["query.document"]},
    {"id": "graph_referrals", "host": "http://localhost:8003", "capabilities": ["query.graph"]},
    {"id": "vector_customers", "host": "http://localhost:8004", "capabilities": ["query.vector"]},
]

# If you want the defaults to be registered automatically on import, set this to True.
# WARNING: enabling auto-registration on import can create side-effects in tests/REPLs.
AUTO_REGISTER_DEFAULTS_ON_IMPORT = True


def register_mcp(manifest: Dict[str, Any]):
    """
    Register a single MCP manifest into the shared MCP_REGISTRY.

    manifest: { id, host, capabilities: [] }
    """
    MCP_REGISTRY[manifest["id"]] = manifest
    return manifest


def register_default_manifests():
    """Register all DEFAULT_MCP_MANIFESTS that are not already present."""
    for m in DEFAULT_MCP_MANIFESTS:
        if m["id"] not in MCP_REGISTRY:
            register_mcp(m)


async def init_managers(settings, register_defaults: bool = False):
    """Initialises managers. Keep heavy I/O out of import-time.

    If `register_defaults` is True, default manifests will be registered as well.
    """
    # For now, we don't auto-register; keep the registry empty until user registers adapters or you configure defaults
    if register_defaults:
        register_default_manifests()
    return


async def fetch_schema(manifest: Dict[str, Any]):
    url = manifest["host"].rstrip("/") + "/schema"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def call_execute(mcp_id: str, operation: str, payload: Dict[str, Any]):
    manifest = MCP_REGISTRY.get(mcp_id)
    if not manifest:
        raise RuntimeError(f"MCP {mcp_id} not registered")
    host = manifest["host"].rstrip("/")
    url = f"{host}/{operation.lstrip('/') }"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


# Optionally register defaults on import (left off by default to avoid side-effects)
if AUTO_REGISTER_DEFAULTS_ON_IMPORT:
    register_default_manifests()
