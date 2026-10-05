"""
Test Suite for Agent Identity, RBAC Permissions, Trading Policies, and Secret Redaction.
"""
import unittest
from datetime import datetime, timezone

from cuanimus.agent.identity import (
    AgentIdentity,
    AgentRole,
    AgentPermission,
    AgentIdentityRegistry,
)
from cuanimus.agent.policy import (
    AgentTradingPolicy,
    PolicyViolationError,
)
from cuanimus.agent.audit import AgentAuditLogger, redact_sensitive_data


class TestAgentIdentityAndPolicy(unittest.TestCase):
    def setUp(self):
        AgentIdentityRegistry.clear()

    def test_agent_rbac_default_deny(self):
        """Agents only possess explicitly assigned permissions, defaulting to deny."""
        advisor = AgentIdentity(
            agent_id="advisory_agent",
            name="Advisor",
            role=AgentRole.ADVISORY,
        )
        self.assertTrue(advisor.has_permission(AgentPermission.READ_SYSTEM))
        self.assertTrue(advisor.has_permission(AgentPermission.ANALYZE))
        self.assertFalse(advisor.has_permission(AgentPermission.PAPER_TRADE))
        self.assertFalse(advisor.has_permission(AgentPermission.TESTNET_TRADE))
        self.assertFalse(advisor.has_permission(AgentPermission.MANAGE_SESSION))

    def test_inactive_agent_denied_all_permissions(self):
        """An inactive agent is denied all permissions regardless of role."""
        supervisor = AgentIdentity(
            agent_id="super_agent",
            name="Supervisor",
            role=AgentRole.SUPERVISOR,
            is_active=False,
        )
        self.assertFalse(supervisor.has_permission(AgentPermission.READ_SYSTEM))
        self.assertFalse(supervisor.has_permission(AgentPermission.PAPER_TRADE))

    def test_token_hashing_and_verification(self):
        """Tokens are verified against SHA-256 hashes without storing cleartext."""
        raw_secret = "secret-bearer-token-12345"
        token_hash = AgentIdentity.hash_token(raw_secret)
        agent = AgentIdentity(
            agent_id="secure_agent",
            name="Secure Agent",
            role=AgentRole.TRADER,
            auth_token_hash=token_hash,
        )
        AgentIdentityRegistry.register(agent)

        self.assertTrue(agent.verify_token(raw_secret))
        self.assertFalse(agent.verify_token("wrong-password"))
        self.assertIsNotNone(AgentIdentityRegistry.authenticate("secure_agent", raw_secret))
        self.assertIsNone(AgentIdentityRegistry.authenticate("secure_agent", "wrong-password"))

    def test_policy_instantiation_rejects_live_trading(self):
        """Policy rejects configuration that includes 'live' environment."""
        with self.assertRaises(PolicyViolationError) as ctx:
            AgentTradingPolicy(allowed_environments=["paper", "live"])
        self.assertIn("CRITICAL SAFETY INVARIANT", str(ctx.exception))

    def test_policy_instantiation_rejects_excessive_leverage(self):
        """Policy cannot exceed institutional platform ceiling of 10.0x leverage."""
        with self.assertRaises(PolicyViolationError) as ctx:
            AgentTradingPolicy(max_leverage=12.0)
        self.assertIn("exceeds institutional platform ceiling", str(ctx.exception))

    def test_policy_instantiation_rejects_disabling_stop_loss(self):
        """Agent policy cannot disable mandatory stop-loss."""
        with self.assertRaises(PolicyViolationError) as ctx:
            AgentTradingPolicy(require_mandatory_stop_loss=False)
        self.assertIn("Mandatory stop loss cannot be disabled", str(ctx.exception))

    def test_policy_evaluates_intent_boundaries(self):
        """Policy vetting rejects unwhitelisted symbols, strategies, and missing SL."""
        policy = AgentTradingPolicy(
            allowed_environments=["paper"],
            allowed_symbols=["ETH/USDT:USDT"],
            allowed_strategies=["v2_pullback"],
            max_leverage=3.0,
            require_mandatory_stop_loss=True,
        )

        # 1. Valid intent
        res = policy.evaluate_intent(
            symbol="ETH/USDT:USDT",
            strategy_id="v2_pullback",
            leverage=2.0,
            stop_loss=3000.0,
            environment="paper",
        )
        self.assertTrue(res.is_approved)

        # 2. Unwhitelisted symbol
        res = policy.evaluate_intent(
            symbol="DOGE/USDT:USDT",
            strategy_id="v2_pullback",
            leverage=2.0,
            stop_loss=3000.0,
        )
        self.assertFalse(res.is_approved)
        self.assertIn("not in policy whitelist", res.reason)

        # 3. Excessive leverage
        res = policy.evaluate_intent(
            symbol="ETH/USDT:USDT",
            strategy_id="v2_pullback",
            leverage=5.0,
            stop_loss=3000.0,
        )
        self.assertFalse(res.is_approved)
        self.assertIn("exceeds policy limit", res.reason)

        # 4. Missing stop loss
        res = policy.evaluate_intent(
            symbol="ETH/USDT:USDT",
            strategy_id="v2_pullback",
            leverage=2.0,
            stop_loss=None,
        )
        self.assertFalse(res.is_approved)
        self.assertIn("mandatory positive stop loss", res.reason)

    def test_audit_logger_redacts_sensitive_keys(self):
        """Audit logger recursively scrubs API keys, secrets, and bearer tokens."""
        raw_payload = {
            "symbol": "BTC/USDT:USDT",
            "binance_key": "raw_sensitive_key_abcdef12345",
            "api_secret": "ultra_secret_signing_passphrase",
            "nested": {
                "telegram_token": "99999:AAABBBCCCDDD",
                "normal_field": 42.5,
            },
        }

        redacted = redact_sensitive_data(raw_payload)
        self.assertEqual(redacted["binance_key"], "[REDACTED_SECRET]")
        self.assertEqual(redacted["api_secret"], "[REDACTED_SECRET]")
        self.assertEqual(redacted["nested"]["telegram_token"], "[REDACTED_SECRET]")
        self.assertEqual(redacted["nested"]["normal_field"], 42.5)

        logger = AgentAuditLogger(log_path=None)
        record = logger.log_event(
            agent_id="test_agent",
            action="api_auth",
            status="SUCCESS",
            details=raw_payload,
        )
        self.assertEqual(record.details["binance_key"], "[REDACTED_SECRET]")
