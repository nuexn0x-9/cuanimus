"""
Unit tests for CUANIMUS Super Admin from .env and Manual Trading features.
"""
import os
import unittest
import tempfile
import shutil
from unittest.mock import patch

from cuanimus.api.auth import AuthManager, UserRole
from cuanimus.engine.position_manager import PositionManager
from cuanimus.api.control_plane import ControlPlaneAPI
from cuanimus.core.database import DatabaseManager


class TestSuperAdminAndManualTrading(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.auth = AuthManager(base_dir=self.test_dir)
        self.db = DatabaseManager.get_instance(base_dir=self.test_dir)
        self.pos_mgr = PositionManager(db=self.db)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_env_admin(self):
        # Mock environment variables
        with patch.dict(os.environ, {
            "API_SERVER_USERNAME": "test_superadmin",
            "API_SERVER_PASSWORD": "SecretAdminPassword123!",
        }):
            res = self.auth.sync_env_admin()
            self.assertIsNotNone(res)
            self.assertEqual(res["username"], "test_superadmin")
            self.assertEqual(res["role"], UserRole.ADMIN.value)

            # Authenticate with credentials
            auth_res = self.auth.authenticate_user("test_superadmin", "SecretAdminPassword123!")
            self.assertTrue(auth_res["authenticated"])
            self.assertEqual(auth_res["role"], "ADMIN")

            # Check list users
            users = self.auth.list_users()
            self.assertTrue(any(u["username"] == "test_superadmin" for u in users))

    def test_update_password(self):
        self.auth.create_user("operator_test", "OldPass123!", role=UserRole.OPERATOR)
        # Verify old password works
        self.assertTrue(self.auth.authenticate_user("operator_test", "OldPass123!")["authenticated"])

        # Update password
        self.auth.update_password("operator_test", "OldPass123!", "NewPass123!")

        # Old password should fail
        with self.assertRaises(PermissionError):
            self.auth.authenticate_user("operator_test", "OldPass123!")

        # New password succeeds
        self.assertTrue(self.auth.authenticate_user("operator_test", "NewPass123!")["authenticated"])

    def test_manual_close_position(self):
        # Record open position
        tid = self.pos_mgr.record_entry(
            symbol="BTC/USDT:USDT",
            side="LONG",
            amount=0.1,
            price=50000.0,
            stop_loss=49000.0,
            take_profit=53000.0,
            strategy_id="manual_test",
        )
        self.assertTrue(tid > 0)
        open_pos = self.pos_mgr.get_open_positions()
        self.assertEqual(len(open_pos), 1)

        # Manually close position
        close_res = self.pos_mgr.close_position_by_id(trade_id=tid, exit_price=52000.0, reason="test_close")
        self.assertEqual(close_res["status"], "CLOSED")
        self.assertAlmostEqual(close_res["profit_abs"], 200.0)

        # Ensure no open positions
        self.assertEqual(len(self.pos_mgr.get_open_positions()), 0)


if __name__ == "__main__":
    unittest.main()
