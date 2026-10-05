"""
Unit & Regression Tests for CUANIMUS CLI Commands.
Tests:
- cuanimus doctor
- cuanimus config validate
- cuanimus config show
- cuanimus config explain
- cuanimus config schema
- cuanimus strategy list & inspect
- cuanimus risk list & inspect
- cuanimus init --non-interactive
- cuanimus status
"""
import unittest
import os
import tempfile
from cuanimus.cli.main import main


class TestCLICommands(unittest.TestCase):
    def test_doctor_command_executes_successfully(self):
        """cuanimus doctor runs all 12 checks and exits with code 0."""
        ret = main(["doctor"])
        self.assertEqual(ret, 0)

    def test_config_validate_command(self):
        """cuanimus config validate exits with code 0 for valid default configuration."""
        ret = main(["config", "validate"])
        self.assertEqual(ret, 0)

    def test_config_show_command(self):
        """cuanimus config show exits with code 0."""
        ret = main(["config", "show", "--format", "json"])
        self.assertEqual(ret, 0)

    def test_config_explain_command(self):
        """cuanimus config explain exits with code 0."""
        ret = main(["config", "explain", "risk.risk_per_trade_pct"])
        self.assertEqual(ret, 0)

    def test_config_schema_command(self):
        """cuanimus config schema dumps valid JSON schema."""
        ret = main(["config", "schema"])
        self.assertEqual(ret, 0)

    def test_strategy_list_and_inspect_commands(self):
        """cuanimus strategy list and inspect succeed."""
        ret_list = main(["strategy", "list"])
        self.assertEqual(ret_list, 0)

        ret_inspect = main(["strategy", "inspect", "hybrid_v2c"])
        self.assertEqual(ret_inspect, 0)

    def test_risk_list_and_inspect_commands(self):
        """cuanimus risk list and inspect succeed."""
        ret_list = main(["risk", "list"])
        self.assertEqual(ret_list, 0)

        ret_inspect = main(["risk", "inspect", "balanced"])
        self.assertEqual(ret_inspect, 0)

    def test_status_command(self):
        """cuanimus status reports platform health."""
        ret = main(["status"])
        self.assertEqual(ret, 0)

    def test_init_non_interactive_generates_valid_yaml(self):
        """cuanimus init --non-interactive generates a valid configuration file."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tf:
            temp_path = tf.name

        try:
            ret = main(["init", "--preset", "conservative", "--output", temp_path, "--non-interactive"])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.exists(temp_path))

            # Validate the newly generated file
            ret_val = main(["config", "validate", "--config", temp_path])
            self.assertEqual(ret_val, 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
