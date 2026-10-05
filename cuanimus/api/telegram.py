"""
CUANIMUS Telegram Notification & Integration Service.
Provides zero-dependency event alerts, status inspection, and test dispatch
via Telegram Bot API over standard HTTP.
Supports formatting trading events:
- Order Fills
- Stop Loss & Take Profit Triggered
- Risk Engine Vetoes & Cooldowns
- Emergency Stop Activated
- Daily Loss Limit Approaching
- Agent Session Started / Stopped
"""
import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Manages Telegram bot alert dispatching and status inspection."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        # Resolve credentials from arguments, environment variables, or defaults
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

        env_enabled = os.environ.get("TELEGRAM_ENABLED", "").lower() in ("true", "1", "yes")
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = env_enabled or bool(self.bot_token and self.chat_id)

        self.last_dispatch_status: Optional[str] = None
        self.last_dispatch_time: Optional[str] = None
        self.last_error_message: Optional[str] = None

    def get_status(self) -> Dict[str, Any]:
        """Returns connection and configuration status without leaking secret token."""
        is_configured = bool(self.bot_token and self.chat_id)
        masked_token = (
            f"{self.bot_token[:4]}...{self.bot_token[-4:]}"
            if len(self.bot_token) > 8
            else ("[CONFIGURED]" if is_configured else "[NOT_CONFIGURED]")
        )

        return {
            "enabled": self.enabled,
            "is_configured": is_configured,
            "bot_token_masked": masked_token,
            "chat_id": self.chat_id if self.chat_id else None,
            "last_dispatch_status": self.last_dispatch_status,
            "last_dispatch_time": self.last_dispatch_time,
            "last_error_message": self.last_error_message,
            "api_endpoint": "https://api.telegram.org/bot<TOKEN>/sendMessage",
        }

    def send_message(self, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """Dispatches text notification to configured Telegram chat."""
        now_str = datetime.now(timezone.utc).isoformat()
        if not self.enabled:
            self.last_dispatch_status = "SKIPPED_DISABLED"
            self.last_dispatch_time = now_str
            return {"success": False, "reason": "Telegram integration is disabled in configuration"}

        if not self.bot_token or not self.chat_id:
            self.last_dispatch_status = "SKIPPED_NOT_CONFIGURED"
            self.last_dispatch_time = now_str
            self.last_error_message = "Missing bot_token or chat_id"
            return {"success": False, "reason": "Telegram bot_token or chat_id is missing"}

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                resp_body = resp.read().decode("utf-8")
                res_json = json.loads(resp_body)
                if res_json.get("ok"):
                    self.last_dispatch_status = "SUCCESS"
                    self.last_dispatch_time = now_str
                    self.last_error_message = None
                    logger.info("Telegram notification successfully dispatched.")
                    return {"success": True, "timestamp": now_str, "response": res_json}
                else:
                    self.last_dispatch_status = "API_ERROR"
                    self.last_dispatch_time = now_str
                    self.last_error_message = res_json.get("description", "Unknown error")
                    return {"success": False, "error": self.last_error_message}

        except urllib.error.HTTPError as e:
            err_msg = f"HTTP {e.code}: {e.reason}"
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                err_msg = f"{err_msg} - {err_json.get('description', '')}"
            except Exception:
                pass
            self.last_dispatch_status = "HTTP_ERROR"
            self.last_dispatch_time = now_str
            self.last_error_message = err_msg
            logger.warning(f"Telegram dispatch failed: {err_msg}")
            return {"success": False, "error": err_msg}

        except Exception as e:
            err_msg = str(e)
            self.last_dispatch_status = "NETWORK_ERROR"
            self.last_dispatch_time = now_str
            self.last_error_message = err_msg
            logger.warning(f"Telegram dispatch failed with network error: {err_msg}")
            return {"success": False, "error": err_msg}

    def send_test_alert(self) -> Dict[str, Any]:
        """Dispatches test ping alert to verify bot configuration."""
        msg = (
            "🔔 <b>CUANIMUS Web Control Center</b>\n\n"
            "✅ <b>Telegram Integration Verified</b>\n"
            f"• <b>Timestamp:</b> <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n"
            "• <b>Status:</b> Control plane alerts active\n"
            "• <b>Environment:</b> PAPER / TESTNET SAFE\n\n"
            "<i>Trading notifications, risk vetoes, and emergency stops will be reported here.</i>"
        )
        return self.send_message(msg)

    def notify_order_filled(self, symbol: str, side: str, amount: float, price: float, pnl: Optional[float] = None) -> Dict[str, Any]:
        pnl_str = f"\n• <b>PnL:</b> <code>{pnl:+.2f} USDT</code>" if pnl is not None else ""
        msg = (
            f"⚡ <b>CUANIMUS ORDER FILLED</b>\n\n"
            f"• <b>Symbol:</b> <code>{symbol}</code>\n"
            f"• <b>Side:</b> <b>{side.upper()}</b>\n"
            f"• <b>Amount:</b> <code>{amount:.4f}</code>\n"
            f"• <b>Fill Price:</b> <code>{price:.2f}</code>"
            f"{pnl_str}\n"
            f"• <b>Time:</b> <code>{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</code>"
        )
        return self.send_message(msg)

    def notify_emergency_stop(self, reason: str, halted_sessions: list) -> Dict[str, Any]:
        msg = (
            "🚨 <b>CUANIMUS EMERGENCY STOP ACTIVATED</b>\n\n"
            f"• <b>Reason:</b> <i>{reason}</i>\n"
            f"• <b>Halted Sessions:</b> <code>{', '.join(halted_sessions) if halted_sessions else 'None'}</code>\n"
            f"• <b>Risk Engine:</b> 🔒 LOCKED\n"
            f"• <b>Timestamp:</b> <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n\n"
            "<b>All automated order generation halted.</b>"
        )
        return self.send_message(msg)
