from __future__ import annotations

"""
MCP (Model Context Protocol) Server — JSON-RPC 2.0 implementation.

Makes AgentOS Semantic Bus actions available as MCP tools.
Any MCP client (Claude, OpenAI, external agents) can discover
and execute AgentOS actions through this standard protocol.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kernel.mcp")


class MCPServer:
    """MCP-compatible server exposing Semantic Bus actions as tools."""

    def __init__(self, semantic_bus):
        self.semantic_bus = semantic_bus
        self.server_info = {
            "name": "agentos",
            "version": "0.1.0",
        }

    async def handle_request(self, raw: str) -> str:
        """Handle a JSON-RPC 2.0 request and return response."""
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            return self._error_response(None, -32700, "Parse error")

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        handler = {
            "initialize": self._initialize,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "resources/list": self._resources_list,
            "ping": self._ping,
        }.get(method)

        if not handler:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

        try:
            result = await handler(params)
            return self._success_response(req_id, result)
        except Exception as e:
            logger.error(f"MCP error handling {method}: {e}")
            return self._error_response(req_id, -32603, str(e))

    async def _initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": self.server_info,
        }

    async def _tools_list(self, params: dict) -> dict:
        actions = self.semantic_bus.get_available_actions()
        tools = []
        for action in actions:
            properties = {}
            required = []
            for p in action.params:
                properties[p.name] = {
                    "type": self._param_type_to_json(p.type.value),
                    "description": p.description,
                }
                if p.default is not None:
                    properties[p.name]["default"] = p.default
                if p.enum_values:
                    properties[p.name]["enum"] = p.enum_values
                if p.required:
                    required.append(p.name)

            tools.append({
                "name": action.id,
                "description": action.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

        return {"tools": tools}

    async def _tools_call(self, params: dict) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = await self.semantic_bus.execute(
            action_id=tool_name,
            params=arguments,
            agent_id="mcp_client",
        )

        if result.success:
            return {
                "content": [
                    {"type": "text", "text": json.dumps(result.data, default=str)}
                ],
            }
        else:
            return {
                "content": [
                    {"type": "text", "text": f"Error: {result.error}"}
                ],
                "isError": True,
            }

    async def _resources_list(self, params: dict) -> dict:
        return {"resources": []}

    async def _ping(self, params: dict) -> dict:
        return {}

    def _param_type_to_json(self, ptype: str) -> str:
        mapping = {
            "string": "string", "number": "number", "boolean": "boolean",
            "enum": "string", "date": "string", "phone": "string",
            "email": "string", "url": "string", "contact": "string",
            "currency": "number", "location": "string", "file": "string",
        }
        return mapping.get(ptype, "string")

    def _success_response(self, req_id, result) -> str:
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error_response(self, req_id, code: int, message: str) -> str:
        return json.dumps({
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message},
        })
