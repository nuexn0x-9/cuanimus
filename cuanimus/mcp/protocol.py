"""
CUANIMUS Model Context Protocol (MCP) JSON-RPC 2.0 Specification Engine.
Standard protocol structures for requests, responses, notifications, and error codes.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union, List
import json


# Standard JSON-RPC 2.0 & MCP Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
PERMISSION_DENIED = -32001
SAFETY_VETO = -32002
IDEMPOTENCY_CONFLICT = -32003


@dataclass
class JsonRpcRequest:
    jsonrpc: str
    method: str
    params: Optional[Dict[str, Any]]
    id: Optional[Union[str, int]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcRequest":
        if not isinstance(data, dict):
            raise ValueError("JSON-RPC request must be an object")
        if data.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC protocol version (must be '2.0')")
        if "method" not in data or not isinstance(data["method"], str):
            raise ValueError("JSON-RPC request must contain a string 'method'")
        return cls(
            jsonrpc=data["jsonrpc"],
            method=data["method"],
            params=data.get("params", {}),
            id=data.get("id"),
        )


def success_response(req_id: Optional[Union[str, int]], result: Any) -> Dict[str, Any]:
    """Generates standard JSON-RPC 2.0 success response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def error_response(
    req_id: Optional[Union[str, int]],
    code: int,
    message: str,
    data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generates standard JSON-RPC 2.0 error response."""
    err_body: Dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if data is not None:
        err_body["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err_body,
    }


def mcp_tool_result(content: Any, is_error: bool = False) -> Dict[str, Any]:
    """Wraps result into standard MCP tool response structure."""
    if isinstance(content, (dict, list)):
        text_content = json.dumps(content, indent=2)
    else:
        text_content = str(content)

    return {
        "content": [
            {
                "type": "text",
                "text": text_content,
            }
        ],
        "isError": is_error,
    }
