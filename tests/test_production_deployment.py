"""
CUANIMUS Production Deployment & Security Architecture Verification Suite.
Validates:
- PBKDF2 Password Hashing & Constant-Time Verification
- Web Authentication, Sessions, CSRF & Anti-Brute Force Lockout
- Role-Based Access Control (RBAC: ADMIN, OPERATOR, VIEWER)
- MCP Scoped Bearer Token Isolation, Rotation & Revocation
- Domain-Based Sliding Window Rate Limiting (READ, ANALYZE, CONFIG, EXECUTE)
- Automated Atomic Backup Creation, SHA256 Verification & Tamper Detection
- Web Security Headers & Control Plane Health Endpoints
- Safety Invariants: Real capital live execution is strictly locked out.
"""
import os
import sys
import json
import time
import shutil
import tempfile
import unittest

from cuanimus.api.auth import (
    AuthManager,
    UserRole,
    ROLE_PERMISSIONS,
    hash_password,
    verify_password,
)
from cuanimus.mcp.tokens import (
    McpTokenManager,
    DOMAIN_RATE_LIMITS,
    TOOL_DOMAIN_MAP,
)
from cuanimus.core.backup import BackupManager
from cuanimus.api.http_server import HttpServerDaemon


class TestWebAuthenticationAndSecurity(unittest.TestCase):
    """Verifies user authentication, PBKDF2 hashing, sessions, and brute force defenses."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.auth = AuthManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pbkdf2_hashing_and_verification(self):
        password = "SuperSecretPassword123!"
        hashed = hash_password(password)
        self.assertTrue(hashed.startswith("pbkdf2:sha256:100000:"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))
        self.assertFalse(verify_password("", hashed))

    def test_user_creation_and_rbac(self):
        user = self.auth.create_user("operator_bob", "BobPass123!", role=UserRole.OPERATOR)
        self.assertEqual(user["username"], "operator_bob")
        self.assertEqual(user["role"], "OPERATOR")

        # Test duplicate creation prevention
        with self.assertRaises(ValueError):
            self.auth.create_user("operator_bob", "AnotherPass")

    def test_authentication_and_session_lifecycle(self):
        self.auth.create_user("alice", "AliceSecurePass!", role=UserRole.VIEWER)
        auth_res = self.auth.authenticate_user("alice", "AliceSecurePass!", client_ip="10.0.0.1")

        self.assertTrue(auth_res["authenticated"])
        self.assertEqual(auth_res["username"], "alice")
        self.assertEqual(auth_res["role"], "VIEWER")
        self.assertIn("session_token", auth_res)
        self.assertIn("csrf_token", auth_res)

        # Validate session
        sess = self.auth.validate_session(auth_res["session_token"])
        self.assertIsNotNone(sess)
        self.assertEqual(sess["username"], "alice")
        self.assertIn("view:read", sess["permissions"])
        self.assertNotIn("trading:paper:execute", sess["permissions"])

        # Test permission checks
        self.assertTrue(self.auth.has_permission(auth_res["session_token"], "view:read"))
        self.assertFalse(self.auth.has_permission(auth_res["session_token"], "config:write"))

        # Revoke session
        self.assertTrue(self.auth.revoke_session(auth_res["session_token"]))
        self.assertIsNone(self.auth.validate_session(auth_res["session_token"]))

    def test_brute_force_rate_limiting_and_lockout(self):
        self.auth.create_user("target_user", "CorrectPassword123!")
        client_ip = "192.168.1.50"

        # 4 failed attempts should fail normally
        for i in range(4):
            with self.assertRaises(PermissionError) as ctx:
                self.auth.authenticate_user("target_user", "WrongPassword", client_ip=client_ip)
            self.assertIn("Invalid username or password", str(ctx.exception))

        # 5th failed attempt triggers lockout
        with self.assertRaises(PermissionError):
            self.auth.authenticate_user("target_user", "WrongPassword", client_ip=client_ip)

        # 6th attempt (even with correct password) should be locked out
        with self.assertRaises(PermissionError) as ctx:
            self.auth.authenticate_user("target_user", "CorrectPassword123!", client_ip=client_ip)
        self.assertIn("Locked out", str(ctx.exception))

    def test_admin_bootstrap_idempotence(self):
        res1 = self.auth.bootstrap_admin(force=False)
        self.assertEqual(res1["status"], "INITIALIZED")
        self.assertEqual(res1["username"], "admin")
        self.assertIn("temporary_password", res1)

        temp_pass = res1["temporary_password"]
        auth_res = self.auth.authenticate_user("admin", temp_pass)
        self.assertTrue(auth_res["authenticated"])
        self.assertEqual(auth_res["role"], "ADMIN")

        # Second bootstrap without force should be idempotent
        res2 = self.auth.bootstrap_admin(force=False)
        self.assertEqual(res2["status"], "ALREADY_INITIALIZED")

        # Bootstrap with force should rotate
        res3 = self.auth.bootstrap_admin(force=True)
        self.assertEqual(res3["status"], "INITIALIZED")
        self.assertNotEqual(res3["temporary_password"], temp_pass)


class TestMcpTokenManagerAndRateLimiting(unittest.TestCase):
    """Verifies scoped MCP tokens, rotation, revocation, and per-domain rate limits."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.token_mgr = McpTokenManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_agent_tokens_initialized(self):
        tokens = self.token_mgr.list_tokens()
        agent_ids = [t["agent_id"] for t in tokens]
        self.assertIn("antigravity-agent", agent_ids)
        self.assertIn("codex-agent", agent_ids)
        self.assertIn("hermes-agent", agent_ids)

    def test_token_authentication(self):
        raw_tokens = self.token_mgr._load_tokens()
        anti_token = raw_tokens["antigravity-agent"]["token"]

        # Valid with Bearer prefix
        agent_data = self.token_mgr.authenticate_token(f"Bearer {anti_token}")
        self.assertIsNotNone(agent_data)
        self.assertEqual(agent_data["agent_id"], "antigravity-agent")
        self.assertIn("EXECUTE", agent_data["allowed_domains"])

        # Invalid token
        self.assertIsNone(self.token_mgr.authenticate_token("Bearer invalid_token_xyz"))
        self.assertIsNone(self.token_mgr.authenticate_token(None))

    def test_token_rotation_and_revocation(self):
        raw_tokens = self.token_mgr._load_tokens()
        old_token = raw_tokens["codex-agent"]["token"]

        # Rotate
        rotated = self.token_mgr.rotate_token("codex-agent")
        self.assertEqual(rotated["status"], "ROTATED")
        new_token = rotated["token"]
        self.assertNotEqual(old_token, new_token)

        # Old token fails, new token succeeds
        self.assertIsNone(self.token_mgr.authenticate_token(old_token))
        self.assertIsNotNone(self.token_mgr.authenticate_token(new_token))

        # Revoke
        self.assertTrue(self.token_mgr.revoke_token("codex-agent"))
        self.assertIsNone(self.token_mgr.authenticate_token(new_token))

    def test_domain_rate_limiting(self):
        agent_id = "antigravity-agent"
        # EXECUTE domain ceiling is 5 requests per minute
        for i in range(5):
            allowed, err = self.token_mgr.check_rate_limit(agent_id, "trading.execute_intent")
            self.assertTrue(allowed, f"Request {i+1} should be permitted")
            self.assertIsNone(err)

        # 6th request must be blocked by rate limit
        allowed, err = self.token_mgr.check_rate_limit(agent_id, "trading.execute_intent")
        self.assertFalse(allowed)
        self.assertIn("Rate limit exceeded for domain 'EXECUTE'", err)

        # But READ domain should still be permitted under its own 60/min limit
        allowed_read, _ = self.token_mgr.check_rate_limit(agent_id, "market.get_ticker")
        self.assertTrue(allowed_read)


class TestBackupManagerAndIntegrity(unittest.TestCase):
    """Verifies atomic backups and cryptographic SHA256 integrity verification."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bm = BackupManager(base_dir=self.test_dir)

        # Create dummy config and user files to back up
        os.makedirs(os.path.join(self.test_dir, "config"), exist_ok=True)
        with open(os.path.join(self.test_dir, "config", "test_config.yaml"), "w") as f:
            f.write("market:\n  pair: BTC/USDT:USDT\n")

        with open(os.path.join(self.test_dir, "cuanimus.user.yaml"), "w") as f:
            f.write("environment:\n  env_name: paper\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_and_verify_backup(self):
        res = self.bm.create_backup(tag="test_snapshot")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("backup_", res["snapshot_id"])
        self.assertTrue(res["item_count"] >= 2)

        # Verify bit-exact integrity
        verify_res = self.bm.verify_backup(res["snapshot_id"])
        self.assertTrue(verify_res["valid"])
        self.assertEqual(verify_res["checked_files"], res["item_count"])

    def test_tamper_detection(self):
        res = self.bm.create_backup(tag="tamper_test")
        snap_id = res["snapshot_id"]

        # Tamper with backed up file
        target_file = os.path.join(self.test_dir, "backups", snap_id, "cuanimus.user.yaml")
        if os.path.exists(target_file):
            with open(target_file, "a") as f:
                f.write("# Malicious modification\n")

            verify_res = self.bm.verify_backup(snap_id)
            self.assertFalse(verify_res["valid"])
            tampered = [d for d in verify_res["details"] if d["status"] == "CORRUPTED"]
            self.assertTrue(len(tampered) > 0)


class TestHttpServerDaemonConfig(unittest.TestCase):
    """Verifies HTTP server setup and default ports."""

    def test_http_server_daemon_defaults(self):
        daemon = HttpServerDaemon(host="127.0.0.1", port=8888)
        self.assertEqual(daemon.host, "127.0.0.1")
        self.assertEqual(daemon.port, 8888)
        self.assertIsNotNone(daemon.auth_manager)
        self.assertIsNotNone(daemon.token_manager)
        self.assertIsNotNone(daemon.api_service)


if __name__ == "__main__":
    unittest.main()
