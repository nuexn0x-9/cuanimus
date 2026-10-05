"""
Test Suite for CUANIMUS Model Context Protocol (MCP) Server and Tool Suites.
"""
import unittest
import json
import threading
import time
import urllib.request
import urllib.error

from cuanimus.mcp.server import McpServer
from cuanimus.mcp.protocol import (
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    PERMISSION_DENIED,
)
from cuanimus.agent.identity import (
    AgentIdentity,
    AgentRole,
    AgentPermission,
    AgentIdentityRegistry,
)


class TestMcpServerAndTools(unittest.TestCase):
    def setUp(self):
        self.server = McpServer()

    def test_jsonrpc_initialize_handshake(self):
        """MCP server responds to standard 'initialize' handshake with protocol version and capabilities."""
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        resp = self.server.handle_message(req)
        self.assertEqual(resp["id"], 1)
        self.assertIn("serverInfo", resp["result"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "cuanimus-mcp-server")
        self.assertIn("capabilities", resp["result"])
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_jsonrpc_tools_list(self):
        """MCP server enumerates all registered tools across all 8 suites."""
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        resp = self.server.handle_message(req)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        self.assertGreaterEqual(len(tools), 40)
        self.assertIn("system.get_status", tool_names)
        self.assertIn("config.get_schema", tool_names)
        self.assertIn("market.get_snapshot", tool_names)
        self.assertIn("portfolio.get_balance", tool_names)
        self.assertIn("strategy.list", tool_names)
        self.assertIn("risk.get_status", tool_names)
        self.assertIn("trading.create_intent", tool_names)
        self.assertIn("session.create", tool_names)

    def test_tool_call_system_get_version(self):
        """Invoking system.get_version returns structured platform metadata."""
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "system.get_version", "arguments": {}},
        }
        resp = self.server.handle_message(req)
        self.assertFalse(resp["result"]["isError"])
        content_text = resp["result"]["content"][0]["text"]
        data = json.loads(content_text)
        self.assertEqual(data["platform"], "CUANIMUS")
        self.assertEqual(data["safety_invariant"], "LIVE_CAPITAL_STRICTLY_DISABLED")

    def test_tool_call_permission_denied_enforcement(self):
        """Calling a mutation tool without assigned permission returns PERMISSION_DENIED (-32001)."""
        advisory_agent = AgentIdentity(
            agent_id="advisory_only",
            name="Advisor",
            role=AgentRole.ADVISORY,
        )
        req = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "trading.execute_intent",
                "arguments": {"intent_id": "sim_1", "idempotency_key": "k_1"},
            },
        }
        resp = self.server.handle_message(req, agent=advisory_agent)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], PERMISSION_DENIED)
        self.assertIn("Permission denied", resp["error"]["message"])

    def test_jsonrpc_resources_read(self):
        """Resources endpoint exposes configuration schema and system status."""
        req = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "resources/read",
            "params": {"uri": "cuanimus://config/schema"},
        }
        resp = self.server.handle_message(req)
        self.assertIn("contents", resp["result"])
        schema_json = resp["result"]["contents"][0]["text"]
        parsed = json.loads(schema_json)
        self.assertIn("$schema", parsed)
        self.assertIn("properties", parsed)

    def test_jsonrpc_prompts_get(self):
        """Prompts endpoint provides assisted configuration system prompt."""
        req = {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "prompts/get",
            "params": {"name": "assisted-configuration", "arguments": {"goal": "Optimize for BTC futures"}},
        }
        resp = self.server.handle_message(req)
        self.assertIn("messages", resp["result"])
        sys_msg = resp["result"]["messages"][0]["content"]["text"]
        self.assertIn("CUANIMUS Quantitative Configuration Assistant", sys_msg)
        self.assertIn("Live real-capital trading is STRICTLY DISABLED", sys_msg)

    def test_jsonrpc_error_codes(self):
        """Invalid method and invalid parameters produce standard JSON-RPC 2.0 error codes."""
        # Method not found
        req1 = {"jsonrpc": "2.0", "id": 51, "method": "non_existent_method", "params": {}}
        resp1 = self.server.handle_message(req1)
        self.assertEqual(resp1["error"]["code"], METHOD_NOT_FOUND)

        # Missing tool name
        req2 = {"jsonrpc": "2.0", "id": 52, "method": "tools/call", "params": {}}
        resp2 = self.server.handle_message(req2)
        self.assertEqual(resp2["error"]["code"], INVALID_PARAMS)

    def test_http_transport_endpoint(self):
        """MCP server can serve JSON-RPC requests over standard HTTP POST transport."""
        port = 8765
        server = McpServer()

        t = threading.Thread(target=server.run_http, kwargs={"host": "127.0.0.1", "port": port}, daemon=True)
        t.start()
        time.sleep(0.3)  # Allow socket to bind

        try:
            req_data = json.dumps({
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/call",
                "params": {"name": "system.get_version", "arguments": {}},
            }).encode("utf-8")

            http_req = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(http_req, timeout=2.0) as response:
                self.assertEqual(response.status, 200)
                body = json.loads(response.read().decode("utf-8"))
                self.assertEqual(body["id"], 100)
                self.assertFalse(body["result"]["isError"])
        finally:
            server.is_running = False
