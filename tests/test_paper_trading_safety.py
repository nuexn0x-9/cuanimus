"""
Tests for CUANIMUS Paper Trading Safety Guard.
Enforces:
- PAPER MODE -> NEVER CALL REAL ORDER SUBMIT
- Exception thrown on any attempted live capital submission
- Telemetry tracking and metrics aggregation
"""
import unittest
from cuanimus.execution.paper_safety import (
    PaperExecutionSafetyGuard,
    FatalSafetyViolationError,
)


class TestPaperTradingSafety(unittest.TestCase):
    def test_paper_safety_guard_blocks_live_order_submission(self):
        """If dry_run is disabled without live clearance, execution MUST throw FatalSafetyViolationError."""
        unsafe_guard = PaperExecutionSafetyGuard(dry_run=False)

        with self.assertRaises(FatalSafetyViolationError) as ctx:
            unsafe_guard.assert_paper_safety("exchange_order_create")

        self.assertIn("FATAL RISK BREACH", str(ctx.exception))

    def test_paper_order_execution_and_telemetry(self):
        """Paper execution simulates orders safely and accumulates execution telemetry."""
        guard = PaperExecutionSafetyGuard(dry_run=True)

        res = guard.execute_paper_order(
            symbol="ADA/USDT:USDT",
            side="buy",
            amount=100.0,
            price=0.4500,
            order_type="limit",
        )

        self.assertTrue(res["is_paper"])
        self.assertEqual(res["status"], "simulated")

        summary = guard.generate_telemetry_summary()
        self.assertTrue(summary["dry_run"])
        self.assertTrue(summary["safety_active"])
        self.assertEqual(summary["order_lifecycle"]["submitted"], 1)


if __name__ == "__main__":
    unittest.main()
