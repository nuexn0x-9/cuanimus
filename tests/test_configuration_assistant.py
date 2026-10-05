"""
Test Suite for Assisted Configuration Proposal Engine & Invariant Rejections.
"""
import unittest
import os
import tempfile
import yaml

from cuanimus.agent.proposal import (
    ProposalEngine,
    ProposalStatus,
    ConfigurationProposal,
)
from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator


class TestConfigurationAssistant(unittest.TestCase):
    def setUp(self):
        self.engine = ProposalEngine()

    def test_proposal_creation_and_diff_calculation(self):
        """Proposals generate structured deltas between base and proposed configs."""
        modifications = {
            "risk": {
                "risk_per_trade_pct": 0.75,
                "max_leverage": 3.0,
            },
            "market": {
                "base_timeframe": "1h",
            },
        }

        proposal = self.engine.create_proposal(
            agent_id="advisory_assistant",
            rationale="Tune risk parameters for conservative swing trading",
            modifications=modifications,
            base_profile="balanced",
        )

        self.assertEqual(proposal.status, ProposalStatus.VALID)
        self.assertTrue(proposal.validation_passed)
        self.assertEqual(proposal.safety_status, "PAPER_SAFE")

        # Verify deltas
        paths = [d.path for d in proposal.deltas]
        self.assertIn("risk.risk_per_trade_pct", paths)
        self.assertIn("risk.max_leverage", paths)
        self.assertIn("market.base_timeframe", paths)

        # Verify impact level
        for delta in proposal.deltas:
            if "risk" in delta.path:
                self.assertIn(delta.impact_level, ["NOTICE", "CRITICAL"])

    def test_proposal_rejects_live_trading_invariant(self):
        """Proposal attempting to enable live trading is rejected by safety invariants."""
        modifications = {
            "environment": {
                "live_trading_enabled": True,
                "dry_run": False,
            }
        }

        proposal = self.engine.create_proposal(
            agent_id="rogue_agent",
            rationale="Attempt to switch system to live capital",
            modifications=modifications,
        )

        self.assertEqual(proposal.status, ProposalStatus.INVALID)
        self.assertFalse(proposal.validation_passed)
        self.assertEqual(proposal.safety_status, "REJECTED_UNSAFE")
        self.assertTrue(any("live_trading_enabled" in err.lower() for err in proposal.validation_errors))

    def test_proposal_rejects_excessive_leverage(self):
        """Proposal attempting to set leverage > 10.0x is marked invalid."""
        modifications = {
            "risk": {
                "max_leverage": 20.0,
            }
        }

        proposal = self.engine.create_proposal(
            agent_id="risky_agent",
            rationale="Maximize leverage for high beta gains",
            modifications=modifications,
        )

        self.assertEqual(proposal.status, ProposalStatus.INVALID)
        self.assertFalse(proposal.validation_passed)
        self.assertTrue(any("leverage" in err.lower() for err in proposal.validation_errors))

    def test_proposal_rejects_disabling_stop_loss_precedence(self):
        """Proposal attempting to disable pessimistic stop loss is marked invalid."""
        modifications = {
            "execution": {
                "pessimistic_sl_precedence": False,
            }
        }

        proposal = self.engine.create_proposal(
            agent_id="careless_agent",
            rationale="Disable pessimistic SL",
            modifications=modifications,
        )

        self.assertEqual(proposal.status, ProposalStatus.INVALID)
        self.assertFalse(proposal.validation_passed)
        self.assertTrue(any("stop-loss" in err.lower() or "sl" in err.lower() for err in proposal.validation_errors))

    def test_proposal_approval_and_safe_application(self):
        """Valid proposal can be approved by human operator and applied to a dedicated user file."""
        modifications = {
            "risk": {
                "risk_per_trade_pct": 1.2,
            }
        }

        proposal = self.engine.create_proposal(
            agent_id="advisory_assistant",
            rationale="Adjust risk per trade slightly",
            modifications=modifications,
            base_profile="conservative",
        )

        self.assertEqual(proposal.status, ProposalStatus.VALID)

        # Human operator approves
        approved = self.engine.approve_proposal(proposal.proposal_id)
        self.assertEqual(approved.status, ProposalStatus.APPROVED)
        self.assertIsNotNone(approved.resolved_at)

        # Apply to a temporary user configuration file
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            apply_res = self.engine.apply_proposal(proposal.proposal_id, target_file_path=tmp_path)
            self.assertEqual(apply_res["status"], "APPLIED")
            self.assertEqual(approved.status, ProposalStatus.APPLIED)

            # Verify file contents
            with open(tmp_path, "r") as f:
                saved = yaml.safe_load(f)
            self.assertEqual(saved["risk"]["risk_per_trade_pct"], 1.2)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
