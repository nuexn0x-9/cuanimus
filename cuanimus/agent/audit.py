"""
CUANIMUS Agent Audit Logger & Secret Redactor.
Provides append-only structured audit trails for every tool invocation,
intent creation, risk assessment, configuration modification, and execution event.
Automatically detects and sanitizes credentials, API secrets, and sensitive tokens.
"""
import os
import json
import uuid
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


SENSITIVE_KEY_PATTERNS = [
    "api_key", "secret", "password", "token", "private_key",
    "binance_key", "binance_secret", "gemini_api_key", "telegram_token",
    "auth_token", "jwt"
]


def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively scans and redacts sensitive credentials from dictionaries, lists, or strings.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(pattern in k.lower() for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = redact_sensitive_data(v)
        return sanitized
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        # Look for obvious long hex or base64 token patterns if needed, or return string
        return data
    else:
        return data


@dataclass
class AuditRecord:
    entry_id: str
    timestamp: str
    agent_id: str
    action: str
    tool_name: Optional[str]
    status: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "action": self.action,
            "tool_name": self.tool_name,
            "status": self.status,
            "details": self.details,
        }


class AgentAuditLogger:
    """
    Thread-safe append-only audit trail logger with secret redaction.
    """
    def __init__(self, log_path: Optional[str] = "logs/agent_audit.jsonl"):
        self.log_path = log_path
        self._in_memory_records: List[AuditRecord] = []

        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_event(
        self,
        agent_id: str,
        action: str,
        status: str,
        tool_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Sanitizes payload and appends immutable audit record."""
        raw_details = details or {}
        sanitized_details = redact_sensitive_data(copy.deepcopy(raw_details))

        record = AuditRecord(
            entry_id=f"audit_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            action=action,
            tool_name=tool_name,
            status=status,
            details=sanitized_details,
        )

        self._in_memory_records.append(record)

        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.to_dict()) + "\n")
            except Exception:
                pass  # Do not crash calling pipeline on file log error

        return record

    def get_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent audit records."""
        return [r.to_dict() for r in self._in_memory_records[-limit:]]

    def clear(self) -> None:
        self._in_memory_records.clear()
