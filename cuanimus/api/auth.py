"""
CUANIMUS Web Authentication, RBAC & Session Security Engine.
Provides enterprise authentication without external third-party dependencies:
- Salted PBKDF2-HMAC-SHA256 password hashing (100,000 rounds)
- Role-Based Access Control (ADMIN, OPERATOR, VIEWER)
- Cryptographic session tokens (secrets.token_urlsafe)
- Session lifecycle expiration and revocation
- Anti-brute force rate limiting (5 attempts / 60s lockout)
- Anti-CSRF protection tokens
- Isolated local credential quarantine (.cuanimus/auth_users.json)
"""
import os
import json
import time
import secrets
import hashlib
import logging
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


# Permission Matrix
ROLE_PERMISSIONS: Dict[UserRole, List[str]] = {
    UserRole.VIEWER: [
        "view:read",
    ],
    UserRole.OPERATOR: [
        "view:read",
        "trading:session:control",
        "trading:paper:execute",
    ],
    UserRole.ADMIN: [
        "view:read",
        "trading:session:control",
        "trading:paper:execute",
        "config:write",
        "risk:override",
        "system:emergency_stop",
        "auth:manage",
    ],
}


def hash_password(password: str) -> str:
    """Hashes password using salted PBKDF2-HMAC-SHA256 (100k rounds)."""
    salt = secrets.token_bytes(16)
    iterations = 100000
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}:{salt.hex()}:{hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification of salted PBKDF2 hash."""
    try:
        parts = password_hash.split(":")
        if len(parts) != 5 or parts[0] != "pbkdf2" or parts[1] != "sha256":
            return False
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_hash = bytes.fromhex(parts[4])
        computed_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


class AuthManager:
    """Manages users, authentication sessions, rate limiting, and RBAC."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = os.path.abspath(base_dir)
        self.store_dir = os.path.join(self.base_dir, ".cuanimus")
        os.makedirs(self.store_dir, exist_ok=True)
        self.users_file = os.path.join(self.store_dir, "auth_users.json")
        self.sessions_file = os.path.join(self.store_dir, "auth_sessions.json")

        self.session_ttl_seconds = 8 * 3600  # 8 hours

        # In-memory rate limiting: {ip_or_user: [timestamps]}
        self._failed_attempts: Dict[str, List[float]] = {}
        self._lockout_until: Dict[str, float] = {}

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read auth_users.json: {e}")
        return {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]):
        with open(self.users_file, "w") as f:
            json.dump(users, f, indent=2)

    def _load_sessions(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read auth_sessions.json: {e}")
        return {}

    def _save_sessions(self, sessions: Dict[str, Dict[str, Any]]):
        with open(self.sessions_file, "w") as f:
            json.dump(sessions, f, indent=2)

    def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        """Checks if IP/username is locked out from too many failed logins."""
        now = time.time()
        lock_until = self._lockout_until.get(identifier, 0)
        if now < lock_until:
            return True, int(lock_until - now)
        return False, 0

    def record_failed_login(self, identifier: str):
        """Records failed login and triggers 60s lockout if >= 5 attempts within 60s."""
        now = time.time()
        attempts = self._failed_attempts.get(identifier, [])
        # Keep attempts from last 60 seconds
        attempts = [t for t in attempts if now - t < 60]
        attempts.append(now)
        self._failed_attempts[identifier] = attempts

        if len(attempts) >= 5:
            self._lockout_until[identifier] = now + 60
            logger.warning(f"Rate limit triggered for {identifier}: Locked out for 60 seconds")

    def clear_failed_logins(self, identifier: str):
        self._failed_attempts.pop(identifier, None)
        self._lockout_until.pop(identifier, None)

    def create_user(self, username: str, password: str, role: UserRole = UserRole.OPERATOR) -> Dict[str, Any]:
        """Creates a new user with salted password hash and role."""
        users = self._load_users()
        if username in users:
            raise ValueError(f"User '{username}' already exists")

        users[username] = {
            "username": username,
            "password_hash": hash_password(password),
            "role": role.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
        }
        self._save_users(users)
        logger.info(f"User '{username}' created with role {role.value}")
        return {"username": username, "role": role.value}

    def authenticate_user(self, username: str, password: str, client_ip: str = "127.0.0.1") -> Dict[str, Any]:
        """Verifies credentials, handles rate limiting, and issues secure session."""
        id_key = f"{client_ip}:{username}"
        is_locked, remaining = self.is_locked_out(id_key)
        if is_locked:
            raise PermissionError(f"Too many failed login attempts. Locked out for {remaining} seconds.")

        users = self._load_users()
        user = users.get(username)

        if not user or not verify_password(password, user["password_hash"]):
            self.record_failed_login(id_key)
            raise PermissionError("Invalid username or password")

        self.clear_failed_logins(id_key)

        # Issue secure session
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(16)
        now = time.time()

        sessions = self._load_sessions()
        # Clean expired sessions
        sessions = {
            k: v for k, v in sessions.items()
            if now - v.get("created_at_epoch", 0) < self.session_ttl_seconds
        }

        sessions[session_token] = {
            "username": username,
            "role": user["role"],
            "csrf_token": csrf_token,
            "created_at_epoch": now,
            "expires_at_epoch": now + self.session_ttl_seconds,
            "client_ip": client_ip,
        }
        self._save_sessions(sessions)

        # Update last login
        user["last_login"] = datetime.now(timezone.utc).isoformat()
        users[username] = user
        self._save_users(users)

        return {
            "authenticated": True,
            "username": username,
            "role": user["role"],
            "session_token": session_token,
            "csrf_token": csrf_token,
            "expires_in_seconds": self.session_ttl_seconds,
        }

    def validate_session(self, session_token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Validates session token and returns user details if active."""
        if not session_token:
            return None

        sessions = self._load_sessions()
        sess = sessions.get(session_token)
        if not sess:
            return None

        now = time.time()
        if now > sess.get("expires_at_epoch", 0):
            # Expired
            sessions.pop(session_token, None)
            self._save_sessions(sessions)
            return None

        return {
            "username": sess["username"],
            "role": sess["role"],
            "csrf_token": sess["csrf_token"],
            "permissions": ROLE_PERMISSIONS.get(UserRole(sess["role"]), []),
        }

    def revoke_session(self, session_token: str) -> bool:
        """Logs out user by destroying session token."""
        sessions = self._load_sessions()
        if session_token in sessions:
            sessions.pop(session_token, None)
            self._save_sessions(sessions)
            return True
        return False

    def has_permission(self, session_token: Optional[str], required_permission: str) -> bool:
        """Enforces RBAC permissions for a given session."""
        user = self.validate_session(session_token)
        if not user:
            return False
        return required_permission in user["permissions"]

    def bootstrap_admin(self, force: bool = False) -> Dict[str, Any]:
        """
        Creates or resets the initial secure Admin user with a cryptographically
        generated password. Never uses hardcoded admin/admin!
        """
        users = self._load_users()
        if "admin" in users and not force:
            return {
                "status": "ALREADY_INITIALIZED",
                "message": "Admin user already exists. Use force=True to reset.",
                "username": "admin",
            }

        generated_password = secrets.token_urlsafe(16)
        users["admin"] = {
            "username": "admin",
            "password_hash": hash_password(generated_password),
            "role": UserRole.ADMIN.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
        }
        self._save_users(users)

        return {
            "status": "INITIALIZED",
            "username": "admin",
            "temporary_password": generated_password,
            "role": UserRole.ADMIN.value,
            "credential_file": self.users_file,
            "note": "Change this password immediately upon first login.",
        }
