"""
CUANIMUS Web Control Center HTTP Server Daemon.
Multi-threaded HTTP/1.1 service powered exclusively by Python's standard library.
Provides:
- Non-blocking REST API routing for all ControlPlaneAPI services
- Static asset serving for CUANIMUS single-page web application
- Robust Web Authentication (Salted PBKDF2, sessions, anti-brute force, anti-CSRF)
- Scoped Remote MCP Protocol Endpoint (/mcp) with domain rate limiting
- Server-Sent Events (SSE) real-time event streaming (/api/events/stream)
- Strict Security Headers & CORS Enforcement
- Health Check (/health)
"""
import os
import sys
import json
import time
import mimetypes
import logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

from cuanimus.api.control_plane import ControlPlaneAPI
from cuanimus.api.auth import AuthManager, UserRole
from cuanimus.mcp.tokens import McpTokenManager
from cuanimus.mcp.server import McpServer

logger = logging.getLogger(__name__)


class CuanimusHttpHandler(BaseHTTPRequestHandler):
    """Handles REST API, Auth, Remote MCP, and static Web UI HTTP requests."""

    server_version = "CUANIMUS-ControlPlane/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def api(self) -> ControlPlaneAPI:
        return self.server.api_service

    @property
    def auth(self) -> AuthManager:
        return self.server.auth_manager

    @property
    def token_mgr(self) -> McpTokenManager:
        return self.server.token_manager

    @property
    def mcp_server(self) -> McpServer:
        return self.server.mcp_server

    @property
    def web_dir(self) -> str:
        return self.server.web_static_dir

    def _extract_session_token(self) -> Optional[str]:
        # 1. Check Authorization header
        auth_hdr = self.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            return auth_hdr.replace("Bearer ", "").strip()

        # 2. Check Cookie header
        cookie_hdr = self.headers.get("Cookie", "")
        if "cnms_session=" in cookie_hdr:
            for part in cookie_hdr.split(";"):
                part = part.strip()
                if part.startswith("cnms_session="):
                    return part.replace("cnms_session=", "").strip()
        return None

    def _get_authenticated_user(self) -> Optional[Dict[str, Any]]:
        token = self._extract_session_token()
        return self.auth.validate_session(token)

    def _send_security_headers(self):
        # Strict Security Headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';"
        )
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")

    def _send_cors_headers(self):
        origin = self.headers.get("Origin", "")
        # Allow same host origin
        self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def _send_json(self, status_code: int, data: Any, extra_headers: Optional[Dict[str, str]] = None):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_security_headers()
        self._send_cors_headers()
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body_bytes = self.rfile.read(content_length)
                return json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to parse JSON body: {e}")
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # Health Check Endpoint
        if path == "/health":
            self._send_json(200, {
                "status": "HEALTHY",
                "service": "cuanimus-web",
                "environment": "PAPER",
                "timestamp": time.time(),
            })
            return

        # 1. API Endpoints
        if path.startswith("/api"):
            self._handle_api_get(path, query)
            return

        # 2. Static File Serving
        self._serve_static_file(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json_body()

        # Remote MCP Protocol endpoint (/mcp)
        if path == "/mcp":
            self._handle_mcp_post(body)
            return

        if path.startswith("/api"):
            self._handle_api_post(path, body)
            return

        self._send_json(404, {"error": "Not Found", "path": path})

    def _handle_mcp_post(self, body: Dict[str, Any]):
        """Executes authenticated MCP JSON-RPC messages with token authentication and rate limits."""
        auth_header = self.headers.get("Authorization", "")
        agent = self.token_mgr.authenticate_token(auth_header)

        if not agent:
            self._send_json(401, {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32002, "message": "Unauthorized: Valid MCP Bearer token required"},
            })
            return

        # Check rate limit if calling a tool
        method = body.get("method")
        if method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name", "")

            # Verify tool is allowed for this agent preset
            if not self.token_mgr.is_tool_allowed(agent, tool_name):
                self._send_json(403, {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32001,
                        "message": f"Permission denied: Agent '{agent['agent_id']}' cannot execute '{tool_name}'",
                    },
                })
                return

            # Check rate limit
            allowed, limit_err = self.token_mgr.check_rate_limit(agent["agent_id"], tool_name)
            if not allowed:
                self._send_json(429, {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32000, "message": limit_err},
                })
                return

        # Dispatch via MCP Server
        msg_str = json.dumps(body)
        resp = self.mcp_server.handle_message(msg_str)
        self._send_json(200, resp or {})

    def _handle_api_get(self, path: str, query: Dict[str, Any]):
        try:
            # Authentication session query
            if path == "/api/auth/me":
                user = self._get_authenticated_user()
                has_users = bool(self.auth._load_users())
                if user:
                    self._send_json(200, {
                        "authenticated": True,
                        "username": user["username"],
                        "role": user["role"],
                        "permissions": user["permissions"],
                        "csrf_token": user["csrf_token"],
                        "auth_configured": has_users,
                    })
                else:
                    self._send_json(200, {
                        "authenticated": False,
                        "auth_configured": has_users,
                    })
                return

            if path == "/api/system/status":
                self._send_json(200, self.api.get_system_status())
            elif path == "/api/doctor":
                self._send_json(200, {"checks": self.api.run_doctor_diagnostics()})
            elif path == "/api/trading/positions":
                self._send_json(200, {"positions": self.api.get_positions()})
            elif path == "/api/trading/orders":
                self._send_json(200, {"orders": self.api.get_orders()})
            elif path == "/api/trading/trades":
                limit = int(query.get("limit", [50])[0])
                self._send_json(200, {"trades": self.api.get_trades(limit=limit)})
            elif path == "/api/trading/decision-traces":
                trade_id = query.get("trade_id", [None])[0]
                self._send_json(200, {"traces": self.api.get_decision_traces(trade_id=trade_id)})
            elif path == "/api/markets/watchlist":
                self._send_json(200, {"watchlist": self.api.get_market_watchlist()})
            elif path == "/api/markets/regimes":
                self._send_json(200, self.api.get_market_regimes())
            elif path == "/api/markets/candles":
                sym = query.get("symbol", ["ETH/USDT:USDT"])[0]
                tf = query.get("timeframe", ["15m"])[0]
                lim = int(query.get("limit", [80])[0])
                self._send_json(200, self.api.get_candles(symbol=sym, timeframe=tf, limit=lim))
            elif path == "/api/risk/status":
                self._send_json(200, self.api.get_risk_status())
            elif path == "/api/risk/profiles":
                self._send_json(200, {"profiles": self.api.list_risk_profiles()})
            elif path == "/api/strategies":
                self._send_json(200, {"strategies": self.api.list_strategies()})
            elif path.startswith("/api/strategies/signal/"):
                strat_id = path.replace("/api/strategies/signal/", "")
                sym = query.get("symbol", ["ETH/USDT:USDT"])[0]
                self._send_json(200, self.api.inspect_strategy_signal(strat_id, sym))
            elif path.startswith("/api/strategies/"):
                strat_id = path.replace("/api/strategies/", "")
                self._send_json(200, self.api.inspect_strategy(strat_id))
            elif path == "/api/research/experiments":
                self._send_json(200, {"experiments": self.api.list_experiments()})
            elif path.startswith("/api/research/experiments/"):
                exp_id = path.replace("/api/research/experiments/", "")
                self._send_json(200, self.api.get_experiment_detail(exp_id))
            elif path == "/api/agents":
                self._send_json(200, {"agents": self.api.list_agents()})
            elif path == "/api/agents/sessions":
                self._send_json(200, {"sessions": self.api.list_agent_sessions()})
            elif path == "/api/agents/audit":
                self._send_json(200, {"audit_logs": self.api.get_agent_audit_logs()})
            elif path == "/api/config/schema":
                self._send_json(200, self.api.get_config_schema())
            elif path == "/api/config/current":
                self._send_json(200, self.api.get_current_configuration())
            elif path == "/api/data/datasets":
                self._send_json(200, {"datasets": self.api.get_datasets()})
            elif path == "/api/logs/events":
                self._send_json(200, {"events": self.api.get_system_events()})
            elif path == "/api/telegram/status":
                self._send_json(200, self.api.get_telegram_status())
            elif path in ("/api/database/status", "/api/system/database"):
                self._send_json(200, self.api.get_database_status())
            elif path == "/api/settings":
                self._send_json(200, self.api.get_settings())
            elif path == "/api/events/stream":
                self._handle_sse_stream()
            else:
                self._send_json(404, {"error": "API route not found", "path": path})
        except Exception as e:
            logger.exception(f"Error handling GET {path}: {e}")
            self._send_json(500, {"error": str(e), "path": path})

    def _handle_api_post(self, path: str, body: Dict[str, Any]):
        try:
            # 1. Auth routes (open for credentials validation)
            if path == "/api/auth/login":
                user = body.get("username", "")
                pwd = body.get("password", "")
                client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
                try:
                    auth_res = self.auth.authenticate_user(user, pwd, client_ip=client_ip)
                    cookie_val = f"cnms_session={auth_res['session_token']}; HttpOnly; SameSite=Lax; Path=/; Max-Age={auth_res['expires_in_seconds']}"
                    self._send_json(200, auth_res, extra_headers={"Set-Cookie": cookie_val})
                except PermissionError as pe:
                    self._send_json(401, {"authenticated": False, "error": str(pe)})
                return

            if path == "/api/auth/logout":
                token = self._extract_session_token()
                if token:
                    self.auth.revoke_session(token)
                cookie_val = "cnms_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"
                self._send_json(200, {"authenticated": False, "message": "Logged out successfully"}, extra_headers={"Set-Cookie": cookie_val})
                return

            # RBAC Enforcement Check
            has_users = bool(self.auth._load_users())
            if has_users:
                user = self._get_authenticated_user()
                # Mutating operations require at least OPERATOR or ADMIN
                if not user:
                    self._send_json(401, {"error": "Authentication required. Please log in."})
                    return

                if path in ["/api/system/emergency-stop", "/api/system/reset-emergency-stop"]:
                    if user["role"] not in ["ADMIN", "OPERATOR"]:
                        self._send_json(403, {"error": "Insufficient permissions for emergency action"})
                        return

                if path in ["/api/config/save", "/api/settings"]:
                    if user["role"] != "ADMIN":
                        self._send_json(403, {"error": "Only ADMIN role may update configurations"})
                        return

            # Handlers
            if path == "/api/system/emergency-stop":
                reason = body.get("reason", "Operator Triggered Web Kill Switch")
                self._send_json(200, self.api.trigger_emergency_stop(reason=reason))
            elif path == "/api/system/reset-emergency-stop":
                self._send_json(200, self.api.reset_emergency_stop())
            elif path.startswith("/api/agents/sessions/") and path.endswith("/action"):
                sess_id = path.split("/")[4]
                action = body.get("action", "")
                self._send_json(200, self.api.manage_agent_session(sess_id, action))
            elif path == "/api/agents/sessions/create-paper":
                agent_id = body.get("agent_id", "antigravity-copilot")
                max_dur = int(body.get("max_duration_seconds", 7200))
                max_trd = int(body.get("max_trades", 20))
                self._send_json(200, self.api.create_paper_session(agent_id, max_dur, max_trd))
            elif path == "/api/agents/propose-config":
                prompt = body.get("prompt", "")
                self._send_json(200, self.api.propose_agent_config(prompt))
            elif path == "/api/config/validate":
                self._send_json(200, self.api.validate_configuration(body))
            elif path == "/api/config/save":
                filename = body.get("filename", "cuanimus.user.yaml")
                cfg = body.get("config", {})
                self._send_json(200, self.api.save_configuration(cfg, filename))
            elif path == "/api/research/backtest/run":
                self._send_json(200, self.api.run_backtest(body))
            elif path == "/api/telegram/test":
                self._send_json(200, self.api.send_telegram_test())
            elif path == "/api/settings":
                self._send_json(200, self.api.update_settings(body))
            elif path == "/api/database/switch":
                target = body.get("target", "sqlite")
                url = body.get("url")
                self._send_json(200, self.api.switch_database_backend(target, url))
            elif path == "/api/database/migrate":
                self._send_json(200, self.api.migrate_database())
            else:
                self._send_json(404, {"error": "API route not found", "path": path})
        except Exception as e:
            logger.exception(f"Error handling POST {path}: {e}")
            self._send_json(500, {"error": str(e), "path": path})

    def _serve_static_file(self, rel_path: str):
        if not rel_path or rel_path == "/":
            rel_path = "/index.html"

        safe_path = os.path.normpath(rel_path.lstrip("/"))
        file_path = os.path.join(self.web_dir, safe_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(self.web_dir, "index.html")

        if not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found - CUANIMUS Web UI files missing")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self._send_security_headers()
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"500 Internal Error: {e}".encode("utf-8"))

    def _handle_sse_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_security_headers()
        self._send_cors_headers()
        self.end_headers()

        try:
            status = self.api.get_system_status()
            self.wfile.write(f"data: {json.dumps(status)}\n\n".encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def log_message(self, format, *args):
        pass


class HttpServerDaemon:
    """Manages the lifecycle of the CUANIMUS Web Control Center HTTP Server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8888, base_dir: str = "."):
        from cuanimus.config.env import load_env_file
        load_env_file()

        self.host = host
        self.port = port
        self.base_dir = os.path.abspath(base_dir)
        self.web_static_dir = os.path.join(self.base_dir, "cuanimus", "web")
        self.api_service = ControlPlaneAPI(base_dir=self.base_dir)
        self.auth_manager = AuthManager(base_dir=self.base_dir)
        self.token_manager = McpTokenManager(base_dir=self.base_dir)
        self.mcp_server = McpServer()
        self._httpd: Optional[ThreadingHTTPServer] = None
        self.is_running = False

    def start(self, blocking: bool = True):
        server_address = (self.host, self.port)
        self._httpd = ThreadingHTTPServer(server_address, CuanimusHttpHandler)
        self._httpd.api_service = self.api_service
        self._httpd.auth_manager = self.auth_manager
        self._httpd.token_manager = self.token_manager
        self._httpd.mcp_server = self.mcp_server
        self._httpd.web_static_dir = self.web_static_dir
        self.is_running = True

        logger.info(f"CUANIMUS Web Control Center running on http://{self.host}:{self.port}/")
        print("\n" + "=" * 70)
        print("          CUANIMUS PRODUCTION WEB CONTROL CENTER & MCP DAEMON")
        print("=" * 70)
        print(f" Web UI:         http://{self.host}:{self.port}/")
        print(f" Remote MCP:     http://{self.host}:{self.port}/mcp")
        print(f" Health Check:   http://{self.host}:{self.port}/health")
        print(" Authentication: Salted PBKDF2 Session Security + Scoped MCP Tokens")
        print(" Environment:    PAPER / TESTNET SAFE (Real Capital Strictly Locked)")
        print(" Emergency Stop: Global Human Kill-Switch Armed")
        print("=" * 70 + "\n")

        if blocking:
            try:
                self._httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self.is_running = False
            logger.info("CUANIMUS Web Control Center stopped.")
