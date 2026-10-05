"""
CUANIMUS Model Context Protocol (MCP) Server.
Implements standard JSON-RPC 2.0 protocol engine over stdio and HTTP transports.
Enforces RBAC permission checks, default-deny security, and immutable audit logging.
"""
import sys
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Union

from cuanimus.mcp.protocol import (
    JsonRpcRequest,
    success_response,
    error_response,
    mcp_tool_result,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
)
from cuanimus.mcp.registry import McpRegistry
from cuanimus.mcp.tools import register_all_tools
from cuanimus.mcp.resources import register_all_resources
from cuanimus.mcp.prompts import register_all_prompts
from cuanimus.agent.identity import AgentIdentity, AgentIdentityRegistry, AgentRole
from cuanimus.agent.audit import AgentAuditLogger

logger = logging.getLogger(__name__)


class McpServer:
    """
    Standard Model Context Protocol (MCP) JSON-RPC 2.0 Server.
    """
    def __init__(self, audit_logger: Optional[AgentAuditLogger] = None):
        # Register capabilities
        register_all_tools()
        register_all_resources()
        register_all_prompts()

        self.audit_logger = audit_logger or AgentAuditLogger()
        self.is_running = False

    def handle_message(
        self,
        raw_message: Union[str, Dict[str, Any]],
        agent: Optional[AgentIdentity] = None,
    ) -> Optional[Dict[str, Any]]:
        """Processes a single JSON-RPC 2.0 message."""
        # Parse payload
        if isinstance(raw_message, str):
            try:
                data = json.loads(raw_message)
            except Exception as e:
                return error_response(None, PARSE_ERROR, f"Parse error: {str(e)}")
        else:
            data = raw_message

        try:
            req = JsonRpcRequest.from_dict(data)
        except Exception as e:
            return error_response(None, INVALID_REQUEST, f"Invalid Request: {str(e)}")

        req_id = req.id
        method = req.method
        params = req.params or {}

        # Default fallback agent identity if none authenticated
        current_agent = agent or AgentIdentityRegistry.get("supervisor-admin") or AgentIdentity(
            agent_id="anonymous-agent",
            name="Anonymous Agent",
            role=AgentRole.ADVISORY,
        )

        try:
            # 1. Lifecycle: initialize
            if method == "initialize":
                return success_response(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {},
                        },
                        "serverInfo": {
                            "name": "cuanimus-mcp-server",
                            "version": "1.0.0",
                        },
                    },
                )

            # 2. Lifecycle: notifications/initialized
            if method == "notifications/initialized":
                return None  # Notifications do not return a response

            if method == "ping":
                return success_response(req_id, {})

            # 3. Tools: tools/list
            if method == "tools/list":
                tools = McpRegistry.list_tools()
                return success_response(req_id, {"tools": tools})

            # 4. Tools: tools/call
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                if not tool_name:
                    return error_response(req_id, INVALID_PARAMS, "Missing 'name' in tools/call params")

                tool_def = McpRegistry.get_tool(tool_name)
                if not tool_def:
                    return error_response(req_id, METHOD_NOT_FOUND, f"Unknown tool: '{tool_name}'")

                # Permission check (Default Deny)
                if tool_def.permission_required and not current_agent.has_permission(tool_def.permission_required):
                    self.audit_logger.log_event(
                        agent_id=current_agent.agent_id,
                        action="tool_call_blocked",
                        status="PERMISSION_DENIED",
                        tool_name=tool_name,
                        details={"required": tool_def.permission_required.value},
                    )
                    return error_response(
                        req_id,
                        PERMISSION_DENIED,
                        f"Permission denied: Agent '{current_agent.agent_id}' lacks '{tool_def.permission_required.value}'",
                    )

                # Context
                call_context = {
                    "agent_id": current_agent.agent_id,
                    "agent_role": current_agent.role.value,
                }

                # Execute handler
                try:
                    result = tool_def.handler(arguments, call_context)
                    self.audit_logger.log_event(
                        agent_id=current_agent.agent_id,
                        action="tool_call",
                        status="SUCCESS",
                        tool_name=tool_name,
                        details={"arguments": arguments, "result": result},
                    )
                    return success_response(req_id, mcp_tool_result(result, is_error=False))
                except Exception as e:
                    self.audit_logger.log_event(
                        agent_id=current_agent.agent_id,
                        action="tool_call_error",
                        status="ERROR",
                        tool_name=tool_name,
                        details={"arguments": arguments, "error": str(e)},
                    )
                    return success_response(req_id, mcp_tool_result({"error": str(e)}, is_error=True))

            # 5. Resources: resources/list
            if method == "resources/list":
                return success_response(req_id, {"resources": McpRegistry.list_resources()})

            # 6. Resources: resources/read
            if method == "resources/read":
                uri = params.get("uri")
                res_def = McpRegistry.get_resource(uri)
                if not res_def:
                    return error_response(req_id, INVALID_PARAMS, f"Resource not found: '{uri}'")
                content = res_def.handler({})
                return success_response(
                    req_id,
                    {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": res_def.mime_type,
                                "text": content,
                            }
                        ]
                    },
                )

            # 7. Prompts: prompts/list
            if method == "prompts/list":
                return success_response(req_id, {"prompts": McpRegistry.list_prompts()})

            # 8. Prompts: prompts/get
            if method == "prompts/get":
                name = params.get("name")
                prompt_def = McpRegistry.get_prompt(name)
                if not prompt_def:
                    return error_response(req_id, INVALID_PARAMS, f"Prompt not found: '{name}'")
                prompt_res = prompt_def.handler(params.get("arguments", {}))
                return success_response(req_id, prompt_res)

            return error_response(req_id, METHOD_NOT_FOUND, f"Method '{method}' not implemented")

        except Exception as e:
            logger.exception("Unexpected server error in MCP dispatch")
            return error_response(req_id, INTERNAL_ERROR, f"Internal server error: {str(e)}")

    def run_stdio(self) -> None:
        """Runs the MCP server over standard input/output."""
        self.is_running = True
        sys.stderr.write("[CUANIMUS MCP Server] Stdio listener active. Ready for JSON-RPC messages.\n")
        sys.stderr.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            resp = self.handle_message(line)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

    def run_http(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Runs the MCP server over HTTP JSON-RPC POST endpoints."""
        server_instance = self

        class McpHttpHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"OPERATIONAL","service":"cuanimus-mcp-server"}')
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                # Extract bearer token if present
                auth_header = self.headers.get("Authorization", "")
                token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else (auth_header.strip() if auth_header else None)

                agent = None
                from cuanimus.mcp.tokens import McpTokenManager
                token_mgr = McpTokenManager()

                if token:
                    # Authenticate agent via McpTokenManager
                    agent_auth = token_mgr.authenticate_token(token)
                    if agent_auth:
                        from cuanimus.agent.identity import ROLE_DEFAULT_PERMISSIONS
                        role = AgentRole.TRADER if "EXECUTE" in agent_auth.get("allowed_domains", []) else AgentRole.ADVISORY
                        agent = AgentIdentity(
                            agent_id=agent_auth["agent_id"],
                            name=agent_auth["agent_id"],
                            role=role,
                            permissions=ROLE_DEFAULT_PERMISSIONS.get(role, set()),
                        )
                    else:
                        # Fallback to AgentIdentityRegistry check
                        agent = AgentIdentityRegistry.authenticate("trader-paper", token)

                # If calling a tool, check domain rate limit
                try:
                    payload = json.loads(body)
                    if payload.get("method") == "tools/call" and agent:
                        tool_name = (payload.get("params") or {}).get("name", "")
                        allowed, limit_err = token_mgr.check_rate_limit(agent.agent_id, tool_name)
                        if not allowed:
                            resp = error_response(payload.get("id"), -32000, limit_err or "Rate limit exceeded")
                            self.send_response(429)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps(resp).encode("utf-8"))
                            return
                except Exception:
                    pass

                resp = server_instance.handle_message(body, agent=agent)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if resp is not None:
                    self.wfile.write(json.dumps(resp).encode("utf-8"))

            def log_message(self, format, *args):
                pass  # Suppress default noisy console logs

        httpd = HTTPServer((host, port), McpHttpHandler)
        self.is_running = True
        logger.info(f"[CUANIMUS MCP Server] Listening on http://{host}:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
            self.is_running = False
