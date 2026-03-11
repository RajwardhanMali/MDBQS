from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.models.state import (
    McpResourceContent,
    McpResourceDescriptor,
    McpResourceReadResult,
    McpServerDescriptor,
    McpToolCall,
    McpToolDescriptor,
    McpToolResult,
    McpToolResultContent,
)

logger = logging.getLogger("mcp_runtime")


class McpRegistry:
    def __init__(self) -> None:
        self._servers: Dict[str, McpServerDescriptor] = {}

    def register(self, server: McpServerDescriptor) -> McpServerDescriptor:
        self._servers[server.server_id] = server
        return server

    def get(self, server_id: str) -> Optional[McpServerDescriptor]:
        return self._servers.get(server_id)

    def list(self) -> List[McpServerDescriptor]:
        return list(self._servers.values())

    def clear(self) -> None:
        self._servers.clear()


class McpTransport:
    async def list_tools(self, server: McpServerDescriptor) -> List[McpToolDescriptor]:
        raise NotImplementedError

    async def list_resources(self, server: McpServerDescriptor) -> List[McpResourceDescriptor]:
        raise NotImplementedError

    async def invoke_tool(self, server: McpServerDescriptor, tool_name: str, arguments: Dict[str, Any]) -> McpToolResult:
        raise NotImplementedError

    async def read_resource(self, server: McpServerDescriptor, uri: str) -> McpResourceReadResult:
        raise NotImplementedError


class HttpMcpLikeTransport(McpTransport):
    async def list_tools(self, server: McpServerDescriptor) -> List[McpToolDescriptor]:
        payload = await self._get_json(f"{server.base_url.rstrip('/')}/mcp/tools")
        return [McpToolDescriptor(**item) for item in payload.get("tools", [])]

    async def list_resources(self, server: McpServerDescriptor) -> List[McpResourceDescriptor]:
        payload = await self._get_json(f"{server.base_url.rstrip('/')}/mcp/resources")
        return [McpResourceDescriptor(**item) for item in payload.get("resources", [])]

    async def invoke_tool(self, server: McpServerDescriptor, tool_name: str, arguments: Dict[str, Any]) -> McpToolResult:
        url = f"{server.base_url.rstrip('/')}/mcp/tools/call"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json={"name": tool_name, "arguments": arguments})
            resp.raise_for_status()
            payload = resp.json()
        return McpToolResult(**payload)

    async def read_resource(self, server: McpServerDescriptor, uri: str) -> McpResourceReadResult:
        url = f"{server.base_url.rstrip('/')}/mcp/resources/read"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json={"uri": uri})
            resp.raise_for_status()
            payload = resp.json()
        return McpResourceReadResult(**payload)

    async def _get_json(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()


class McpRuntime:
    def __init__(self, registry: Optional[McpRegistry] = None, transport: Optional[McpTransport] = None) -> None:
        self.registry = registry or McpRegistry()
        self.transport = transport or HttpMcpLikeTransport()

    async def hydrate_server(self, server_id: str) -> McpServerDescriptor:
        server = self.require_server(server_id)
        last_exc: Optional[Exception] = None
        for attempt in range(1, 6):
            try:
                server.tools = await self.transport.list_tools(server)
                server.resources = await self.transport.list_resources(server)
                server.health = "ok"
                return server
            except Exception as exc:
                last_exc = exc
                if attempt < 5:
                    await asyncio.sleep(0.75)
                else:
                    logger.exception("Failed to hydrate MCP server %s", server_id)
                    server.health = "error"
        return server

    async def hydrate_all(self) -> List[McpServerDescriptor]:
        servers = self.registry.list()
        for server in servers:
            await self.hydrate_server(server.server_id)
        return servers

    def register_server(self, descriptor: McpServerDescriptor) -> McpServerDescriptor:
        return self.registry.register(descriptor)

    def require_server(self, server_id: str) -> McpServerDescriptor:
        server = self.registry.get(server_id)
        if not server:
            raise RuntimeError(f"MCP server {server_id} not registered")
        return server

    def list_servers(self) -> List[McpServerDescriptor]:
        return self.registry.list()

    async def list_tools(self, server_id: str) -> List[McpToolDescriptor]:
        server = self.require_server(server_id)
        if not server.tools:
            await self.hydrate_server(server_id)
        return server.tools

    async def list_resources(self, server_id: str) -> List[McpResourceDescriptor]:
        server = self.require_server(server_id)
        if not server.resources:
            await self.hydrate_server(server_id)
        return server.resources

    async def invoke_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> McpToolResult:
        server = self.require_server(server_id)
        return await self.transport.invoke_tool(server, tool_name, arguments)

    async def read_resource(self, server_id: str, uri: str) -> McpResourceReadResult:
        server = self.require_server(server_id)
        return await self.transport.read_resource(server, uri)

    async def read_json_resource(self, server_id: str, uri: str) -> Dict[str, Any]:
        resource = await self.read_resource(server_id, uri)
        if not resource.contents:
            return {}
        return json.loads(resource.contents[0].text)


def normalize_legacy_result(
    items: List[Dict[str, Any]],
    meta: Dict[str, Any],
    *,
    is_error: bool = False,
) -> McpToolResult:
    structured = {"items": items, "meta": meta}
    return McpToolResult(
        is_error=is_error,
        content=[McpToolResultContent(json_payload=structured)],
        structured_content=structured,
    )


def make_resource_result(uri: str, payload: Dict[str, Any], mime_type: str = "application/json") -> McpResourceReadResult:
    return McpResourceReadResult(
        contents=[McpResourceContent(uri=uri, mimeType=mime_type, text=json.dumps(payload))]
    )
