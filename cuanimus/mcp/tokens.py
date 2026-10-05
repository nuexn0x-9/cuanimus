"""
CUANIMUS Production MCP Scoped Token & Rate Limiting Engine.
Manages scoped bearer tokens for external AI agents (Antigravity, Codex, Hermes),
domain-based request rate limiting, token rotation, and instant revocation.
Tokens and policies are securely isolated in .cuanimus/mcp_tokens.json.
"""
import os
import json
import time
import secrets
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Domain rate limits (requests per minute)
DOMAIN_RATE_LIMITS: Dict[str, int] = {
    "READ": 60,
    "ANALYZE": 30,
    "CONFIG": 15,
    "EXECUTE": 5,  # Strictest ceiling to prevent runaway trade execution
}

# Mapping of MCP tools to domains
TOOL_DOMAIN_MAP: Dict[str, str] = {
    # READ
    "system.get_version": "READ",
    "system.get_safety_status": "READ",
    "market.get_ticker": "READ",
    "market.get_candles": "READ",
    "market.get_regime": "READ",
    "market.get_orderbook": "READ",
    "portfolio.get_balance": "READ",
    "portfolio.get_positions": "READ",
    "portfolio.get_orders": "READ",
    "strategy.list": "READ",
    "strategy.inspect": "READ",
    "risk.get_limits": "READ",
    "session.get_status": "READ",
    "config.get_schema": "READ",
    "config.get_current": "READ",
    "doctor.run_diagnostics": "READ",

    # ANALYZE
    "strategy.evaluate": "ANALYZE",
    "strategy.explain_signal": "ANALYZE",
    "market.analyze_order_blocks": "ANALYZE",
    "trading.simulate_fill": "ANALYZE",
    "risk.assess_trade": "ANALYZE",

    # CONFIG
    "config.validate": "CONFIG",
    "config.preview": "CONFIG",
    "config.apply": "CONFIG",
    "config.explain": "CONFIG",

    # EXECUTE (Requires PaperAuto or TestnetAuto permission)
    "trading.create_intent": "EXECUTE",
    "trading.validate_intent": "EXECUTE",
    "trading.execute_intent": "EXECUTE",
    "trading.cancel_order": "EXECUTE",
    "session.start": "EXECUTE",
    "session.pause": "EXECUTE",
    "session.stop": "EXECUTE",
    "emergency_stop": "EXECUTE",
}


class McpTokenManager:
    """Manages scoped AI agent tokens, rotation, revocation, and per-domain rate limits."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = os.path.abspath(base_dir)
        self.store_dir = os.path.join(self.base_dir, ".cuanimus")
        os.makedirs(self.store_dir, exist_ok=True)
        self.tokens_file = os.path.join(self.store_dir, "mcp_tokens.json")

        # In-memory rate limiting sliding window: {(agent_id, domain): [timestamps]}
        self._request_history: Dict[Tuple[str, str], List[float]] = {}

        self._ensure_default_agent_tokens()

    def _load_tokens(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read mcp_tokens.json: {e}")
        return {}

    def _save_tokens(self, tokens: Dict[str, Dict[str, Any]]):
        with open(self.tokens_file, "w") as f:
            json.dump(tokens, f, indent=2)

    def _ensure_default_agent_tokens(self):
        """Initializes default agent tokens for Antigravity, Codex, and Hermes if not present."""
        tokens = self._load_tokens()
        modified = False

        default_agents = [
            ("antigravity-agent", "paper_auto", ["READ", "ANALYZE", "CONFIG", "EXECUTE"]),
            ("codex-agent", "advisory", ["READ", "ANALYZE", "CONFIG"]),
            ("hermes-agent", "paper_auto", ["READ", "ANALYZE", "EXECUTE"]),
        ]

        for agent_id, preset, perms in default_agents:
            if agent_id not in tokens:
                token_val = f"cnms_agent_{secrets.token_urlsafe(32)}"
                tokens[agent_id] = {
                    "agent_id": agent_id,
                    "token": token_val,
                    "preset": preset,
                    "allowed_domains": perms,
                    "environment": "paper",
                    "status": "ACTIVE",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_used": None,
                }
                modified = True

        if modified:
            self._save_tokens(tokens)

    def authenticate_token(self, token_header: Optional[str]) -> Optional[Dict[str, Any]]:
        """Validates bearer token header and returns agent identity if valid and active."""
        if not token_header:
            return None

        clean_token = token_header.replace("Bearer ", "").strip() if token_header.startswith("Bearer ") else token_header.strip()
        tokens = self._load_tokens()

        for agent_id, record in tokens.items():
            if record.get("status") == "ACTIVE" and secrets.compare_digest(record.get("token", ""), clean_token):
                # Update last_used
                record["last_used"] = datetime.now(timezone.utc).isoformat()
                tokens[agent_id] = record
                self._save_tokens(tokens)
                return {
                    "agent_id": agent_id,
                    "preset": record.get("preset"),
                    "allowed_domains": record.get("allowed_domains", []),
                    "environment": record.get("environment", "paper"),
                }
        return None

    def check_rate_limit(self, agent_id: str, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        Enforces domain-specific sliding window rate limit.
        Returns (is_allowed, error_message).
        """
        domain = TOOL_DOMAIN_MAP.get(tool_name, "READ")
        limit = DOMAIN_RATE_LIMITS.get(domain, 30)

        now = time.time()
        key = (agent_id, domain)
        history = self._request_history.get(key, [])
        # Keep calls within last 60 seconds
        history = [t for t in history if now - t < 60]

        if len(history) >= limit:
            return False, f"Rate limit exceeded for domain '{domain}': Max {limit} req/min. Please back off."

        history.append(now)
        self._request_history[key] = history
        return True, None

    def is_tool_allowed(self, agent_identity: Dict[str, Any], tool_name: str) -> bool:
        """Verifies if the agent has permissions to invoke this tool category."""
        domain = TOOL_DOMAIN_MAP.get(tool_name, "READ")
        allowed_domains = agent_identity.get("allowed_domains", [])
        return domain in allowed_domains

    def rotate_token(self, agent_id: str) -> Dict[str, Any]:
        """Revokes existing token and issues a new high-entropy token."""
        tokens = self._load_tokens()
        if agent_id not in tokens:
            raise KeyError(f"Agent '{agent_id}' not found")

        new_token = f"cnms_agent_{secrets.token_urlsafe(32)}"
        record = tokens[agent_id]
        record["token"] = new_token
        record["status"] = "ACTIVE"
        record["created_at"] = datetime.now(timezone.utc).isoformat()
        record["last_used"] = None
        tokens[agent_id] = record
        self._save_tokens(tokens)

        logger.info(f"Rotated MCP token for agent '{agent_id}'")
        return {
            "agent_id": agent_id,
            "status": "ROTATED",
            "token": new_token,
            "created_at": record["created_at"],
        }

    def revoke_token(self, agent_id: str) -> bool:
        """Revokes an agent's MCP token immediately."""
        tokens = self._load_tokens()
        if agent_id not in tokens:
            return False

        tokens[agent_id]["status"] = "REVOKED"
        self._save_tokens(tokens)
        logger.warning(f"Revoked MCP token for agent '{agent_id}'")
        return True

    def list_tokens(self) -> List[Dict[str, Any]]:
        """Lists registered agent tokens with token values safely masked."""
        tokens = self._load_tokens()
        res = []
        for agent_id, r in tokens.items():
            t_val = r.get("token", "")
            masked = f"{t_val[:12]}...{t_val[-6:]}" if len(t_val) > 18 else "[MASKED]"
            res.append({
                "agent_id": agent_id,
                "preset": r.get("preset"),
                "environment": r.get("environment"),
                "allowed_domains": r.get("allowed_domains"),
                "status": r.get("status"),
                "token_masked": masked,
                "created_at": r.get("created_at"),
                "last_used": r.get("last_used"),
            })
        return res
