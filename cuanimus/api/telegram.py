"""
CUANIMUS Telegram Notification & Mobile Interactive Bot Service.
Provides zero-dependency event alerts, status inspection, and two-way interactive
mobile menu control over Telegram Bot API.

Features:
- Outbound trading notifications (Fills, SL/TP, Vetoes, Emergency Stop)
- Interactive Mobile Keyboard Menu (ReplyKeyboardMarkup) for quick one-tap actions
- Real-time command processor (/status, /market, /positions, /signal, /agents, /db, /emergency_stop)
- Single-operator RBAC security check (strictly authorized chat ID)
- Native Telegram Menu command registration (setMyCommands)
"""
import os
import json
import time
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from cuanimus.config.env import load_env_file

logger = logging.getLogger(__name__)

# Compact Dropdown & Category Keyboards (InlineKeyboardMarkup prevents filling up phone screen)
MAIN_DROPDOWN_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "📊 Portofolio & Pasar ▾", "callback_data": "menu:market"},
            {"text": "⚡ Sinyal & Strategi ▾", "callback_data": "menu:strategy"},
        ],
        [
            {"text": "🤖 AI Copilot & Agent ▾", "callback_data": "menu:ai"},
            {"text": "🛡️ Risiko & Proteksi ▾", "callback_data": "menu:risk"},
        ],
        [
            {"text": "🗄️ Database & Sistem ▾", "callback_data": "menu:system"},
            {"text": "ℹ️ Panduan Singkat", "callback_data": "menu:help"},
        ],
        [
            {"text": "🛑 EMERGENCY KILL SWITCH", "callback_data": "action:kill"},
        ],
    ]
}

MARKET_CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "📊 Status Platform", "callback_data": "view:status"},
            {"text": "💰 Saldo & Equity", "callback_data": "view:balance"},
        ],
        [
            {"text": "📈 Live Watchlist", "callback_data": "view:market"},
            {"text": "💼 Posisi Terbuka", "callback_data": "view:positions"},
        ],
        [
            {"text": "📅 Kinerja Harian", "callback_data": "view:daily"},
            {"text": "📋 Riwayat Order", "callback_data": "view:orders"},
        ],
        [
            {"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"},
        ],
    ]
}

STRATEGY_CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "⚡ Sinyal ETH/USDT", "callback_data": "view:signal:ETH"},
            {"text": "⚡ Sinyal BTC/USDT", "callback_data": "view:signal:BTC"},
        ],
        [
            {"text": "⚡ Sinyal SOL/USDT", "callback_data": "view:signal:SOL"},
            {"text": "⚙️ Katalog Strategi", "callback_data": "view:strategy"},
        ],
        [
            {"text": "🚀 Autonomous Engine", "callback_data": "view:auto_engine"},
            {"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"},
        ],
    ]
}

AI_CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🤖 Status AI & MCP Tools", "callback_data": "view:agents"},
        ],
        [
            {"text": "🧠 Panduan Tanya Copilot", "callback_data": "view:ai_help"},
        ],
        [
            {"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"},
        ],
    ]
}

RISK_CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🛡️ Status Risk Engine", "callback_data": "view:risk"},
        ],
        [
            {"text": "🛑 Aktifkan Kill Switch", "callback_data": "action:kill"},
            {"text": "🔄 Reset Kill Switch", "callback_data": "action:reset_stop"},
        ],
        [
            {"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"},
        ],
    ]
}

SYSTEM_CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🗄️ Status Database", "callback_data": "view:db"},
        ],
        [
            {"text": "🔄 Switch ke SQLite", "callback_data": "action:db:sqlite"},
            {"text": "🔄 Switch ke Postgres", "callback_data": "action:db:postgres"},
        ],
        [
            {"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"},
        ],
    ]
}

INLINE_BACK_HOME = {
    "inline_keyboard": [
        [{"text": "📂 Buka Menu Dropdown", "callback_data": "menu:root"}]
    ]
}

# Backward compatibility alias
MAIN_MENU_KEYBOARD = MAIN_DROPDOWN_KEYBOARD


class TelegramNotifier:
    """Manages Telegram bot alert dispatching and status inspection."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        load_env_file()

        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

        # Fallback check in user_data/config.json
        if not self.bot_token or not self.chat_id:
            cfg_path = os.path.join(os.path.abspath("."), "user_data", "config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    tg = c_data.get("telegram", {})
                    token_candidate = tg.get("token", "").strip()
                    chat_candidate = str(tg.get("chat_id", "")).strip()
                    if not self.bot_token and token_candidate and not token_candidate.startswith("${"):
                        self.bot_token = token_candidate
                    if not self.chat_id and chat_candidate and not chat_candidate.startswith("${"):
                        self.chat_id = chat_candidate
                    if enabled is None and tg.get("enabled"):
                        self.enabled = bool(tg.get("enabled"))
                except Exception:
                    pass

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

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches text notification to configured Telegram chat."""
        now_str = datetime.now(timezone.utc).isoformat()
        if not self.enabled:
            self.last_dispatch_status = "SKIPPED_DISABLED"
            self.last_dispatch_time = now_str
            return {"success": False, "reason": "Telegram integration is disabled in configuration"}

        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            self.last_dispatch_status = "SKIPPED_NOT_CONFIGURED"
            self.last_dispatch_time = now_str
            self.last_error_message = "Missing bot_token or chat_id"
            return {"success": False, "reason": "Telegram bot_token or chat_id is missing"}

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

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

    def edit_message_text(
        self,
        text: str,
        message_id: int,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Edits an existing Telegram message in-place via editMessageText API."""
        now_str = datetime.now(timezone.utc).isoformat()
        if not self.enabled:
            return {"success": False, "reason": "Telegram integration disabled"}

        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            return {"success": False, "reason": "Missing bot_token or chat_id"}

        url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
        payload: Dict[str, Any] = {
            "chat_id": target_chat,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

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
                return {"success": bool(res_json.get("ok")), "response": res_json}
        except Exception as e:
            logger.warning(f"Telegram editMessageText failed: {e}")
            return {"success": False, "error": str(e)}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> Dict[str, Any]:
        """Acknowledges an incoming inline button callback query."""
        if not self.bot_token:
            return {"success": False}

        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp_body = resp.read().decode("utf-8")
                res_json = json.loads(resp_body)
                return {"success": bool(res_json.get("ok"))}
        except Exception as e:
            logger.warning(f"Telegram answerCallbackQuery failed: {e}")
            return {"success": False, "error": str(e)}

    def remove_sticky_keyboard(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Dismisses any persistent bottom-drawer keyboard from the user's mobile screen."""
        return self.send_message(
            "📂 <i>Menyesuaikan tampilan: Mengaktifkan mode dropdown inline hemat layar.</i>",
            reply_markup={"remove_keyboard": True},
            chat_id=chat_id,
        )

    def send_menu(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends the main interactive dropdown menu with inline buttons."""
        msg = (
            "🤖 <b>CUANIMUS Mobile Control Center</b>\n\n"
            "Pusat kendali trading kuantitatif & agen AI.\n"
            "Pilih kategori menu dari dropdown inline di bawah:"
        )
        return self.send_message(msg, reply_markup=MAIN_DROPDOWN_KEYBOARD, chat_id=chat_id)

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
        return self.send_message(msg, reply_markup=INLINE_BACK_HOME)

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
        return self.send_message(msg, reply_markup=INLINE_BACK_HOME)

    def notify_emergency_stop(self, reason: str, halted_sessions: list) -> Dict[str, Any]:
        msg = (
            "🚨 <b>CUANIMUS EMERGENCY STOP ACTIVATED</b>\n\n"
            f"• <b>Reason:</b> <i>{reason}</i>\n"
            f"• <b>Halted Sessions:</b> <code>{', '.join(halted_sessions) if halted_sessions else 'None'}</code>\n"
            f"• <b>Risk Engine:</b> 🔒 LOCKED\n"
            f"• <b>Timestamp:</b> <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n\n"
            "<b>All automated order generation halted.</b>"
        )
        return self.send_message(msg, reply_markup=MAIN_MENU_KEYBOARD)


class TelegramBotListener:
    """
    Background long-polling listener for Telegram Bot API.
    Enables two-way interactive mobile management:
    - Processes incoming text and keyboard commands from the user's smartphone.
    - Routes queries to ControlPlaneAPI.
    - Enforces strict operator authentication (only configured chat_id permitted).
    """

    def __init__(self, notifier: TelegramNotifier, api_service=None):
        self.notifier = notifier
        self.api = api_service
        self.bot_token = notifier.bot_token
        self.chat_id = str(notifier.chat_id).strip()
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._last_update_id = 0

    def start(self):
        """Starts the Telegram polling daemon thread."""
        if not self.bot_token or not self.chat_id or not self.notifier.enabled:
            logger.info("TelegramBotListener skipped (disabled or credentials missing).")
            return
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramBotListener")
        self._thread.start()
        threading.Thread(target=self.setup_bot_commands, daemon=True, name="TelegramBotCmdSetup").start()
        logger.info("TelegramBotListener background poller started.")

    def stop(self):
        """Stops the polling daemon."""
        self.is_running = False

    def setup_bot_commands(self):
        """Registers native bot menu commands via Telegram setMyCommands API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/setMyCommands"
        commands = [
            {"command": "menu", "description": "Tampilkan menu & tombol kontrol"},
            {"command": "status", "description": "Status platform & health check"},
            {"command": "balance", "description": "Saldo wallet, equity & margin"},
            {"command": "daily", "description": "Kinerja & PnL harian"},
            {"command": "market", "description": "Live watchlist & harga Binance"},
            {"command": "positions", "description": "Posisi trading & PnL aktual"},
            {"command": "orders", "description": "Daftar 5 order terakhir"},
            {"command": "signal", "description": "Evaluasi sinyal strategi V2A"},
            {"command": "strategy", "description": "Daftar strategi kuantitatif"},
            {"command": "risk", "description": "Parameter & status risk engine"},
            {"command": "agents", "description": "Status AI Agent & MCP tools"},
            {"command": "db", "description": "Status database SQLite / PostgreSQL"},
            {"command": "auto", "description": "Status Autonomous Trading Engine & Profil"},
            {"command": "emergency_stop", "description": "Aktifkan Kill Switch darurat"},
            {"command": "reset_stop", "description": "Reset Kill Switch darurat"},
        ]
        try:
            req_data = json.dumps({"commands": commands}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                pass
        except Exception as e:
            logger.warning(f"Could not register Telegram bot commands: {e}")

    def _poll_loop(self):
        logger.info("Telegram long-polling daemon active.")
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self._last_update_id + 1}&timeout=15"
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=25.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        for upd in data.get("result", []):
                            self._last_update_id = max(self._last_update_id, upd["update_id"])
                            if "callback_query" in upd:
                                self._handle_callback_query(upd["callback_query"])
                            elif "message" in upd:
                                self._handle_update(upd)
            except urllib.error.URLError:
                time.sleep(3.0)
            except Exception as e:
                logger.warning(f"Error in Telegram poller: {e}")
                time.sleep(2.0)

    def _handle_callback_query(self, cb_query: Dict[str, Any]):
        qid = cb_query.get("id")
        sender_id = str(cb_query.get("from", {}).get("id"))
        msg = cb_query.get("message", {})
        message_id = msg.get("message_id")
        data = (cb_query.get("data") or "").strip()

        # Strict security: Only allow authorized chat ID
        if sender_id != self.chat_id:
            logger.warning(f"Unauthorized callback from unknown chat ID {sender_id}")
            self.notifier.answer_callback_query(qid, text="⛔ Akses Ditolak: Bukan operator terdaftar.", show_alert=True)
            return

        self.notifier.answer_callback_query(qid)

        try:
            self._route_callback(data, message_id, sender_id)
        except Exception as e:
            logger.exception(f"Error handling callback query '{data}': {e}")

    def _route_callback(self, data: str, message_id: int, sender_id: str):
        if data in ("menu:root", "menu:main"):
            msg = (
                "🤖 <b>CUANIMUS Mobile Control Center</b>\n\n"
                "Pusat kendali trading kuantitatif & agen AI.\n"
                "Pilih kategori menu dari dropdown inline di bawah:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=MAIN_DROPDOWN_KEYBOARD,
            )
        elif data == "menu:market":
            msg = (
                "📊 <b>Kategori: Portofolio & Pasar</b>\n\n"
                "Pilih data yang ingin Anda inspeksi secara real-time:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=MARKET_CATEGORY_KEYBOARD,
            )
        elif data == "menu:strategy":
            msg = (
                "⚡ <b>Kategori: Sinyal & Strategi</b>\n\n"
                "Evaluasi sinyal strategi algoritma kuantitatif:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=STRATEGY_CATEGORY_KEYBOARD,
            )
        elif data == "menu:ai":
            msg = (
                "🤖 <b>Kategori: AI Copilot & Agent</b>\n\n"
                "Status AI model, sesi paper trading & MCP tools:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=AI_CATEGORY_KEYBOARD,
            )
        elif data == "menu:risk":
            msg = (
                "🛡️ <b>Kategori: Risiko & Proteksi</b>\n\n"
                "Pengawasan Risk Engine dan kontrol darurat:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=RISK_CATEGORY_KEYBOARD,
            )
        elif data == "menu:system":
            msg = (
                "🗄️ <b>Kategori: Database & Sistem</b>\n\n"
                "Status penyimpanan ledger dan pergantian database:"
            )
            self.notifier.edit_message_text(
                text=msg,
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=SYSTEM_CATEGORY_KEYBOARD,
            )
        elif data == "menu:help":
            self._edit_with_help(message_id, sender_id)
        elif data == "view:status":
            self.notifier.edit_message_text(
                text=self._format_status(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:status", "menu:market"),
            )
        elif data == "view:balance":
            self.notifier.edit_message_text(
                text=self._format_balance(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:balance", "menu:market"),
            )
        elif data == "view:market":
            self.notifier.edit_message_text(
                text=self._format_market(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:market", "menu:market"),
            )
        elif data == "view:positions":
            self.notifier.edit_message_text(
                text=self._format_positions(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:positions", "menu:market"),
            )
        elif data == "view:daily":
            self.notifier.edit_message_text(
                text=self._format_daily(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:daily", "menu:market"),
            )
        elif data == "view:orders":
            self.notifier.edit_message_text(
                text=self._format_orders(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:orders", "menu:market"),
            )
        elif data.startswith("view:signal:"):
            sym = data.split(":")[-1]
            self.notifier.edit_message_text(
                text=self._format_signal(sym),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup(f"view:signal:{sym}", "menu:strategy"),
            )
        elif data == "view:strategy":
            self.notifier.edit_message_text(
                text=self._format_strategy(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:strategy", "menu:strategy"),
            )
        elif data == "view:risk":
            self.notifier.edit_message_text(
                text=self._format_risk(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:risk", "menu:risk"),
            )
        elif data == "view:agents":
            self.notifier.edit_message_text(
                text=self._format_agents(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:agents", "menu:ai"),
            )
        elif data == "view:ai_help":
            self._edit_with_ai_help(message_id, sender_id)
        elif data == "view:db":
            self.notifier.edit_message_text(
                text=self._format_database(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:db", "menu:system"),
            )
        elif data == "view:auto_engine":
            self.notifier.edit_message_text(
                text=self._format_auto_engine(),
                message_id=message_id,
                chat_id=sender_id,
                reply_markup=self._make_nav_markup("view:auto_engine", "menu:strategy"),
            )
        elif data == "action:kill":
            self._execute_inline_emergency_stop(message_id, sender_id)
        elif data == "action:reset_stop":
            self._execute_inline_reset_stop(message_id, sender_id)
        elif data.startswith("action:db:"):
            target = data.split(":")[-1]
            self._execute_inline_db_switch(target, message_id, sender_id)

    def _make_nav_markup(self, refresh_cb: str, back_cb: str = "menu:root") -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "🔄 Refresh", "callback_data": refresh_cb},
                    {"text": "◀️ Kembali", "callback_data": back_cb},
                ],
                [
                    {"text": "🏠 Menu Utama", "callback_data": "menu:root"},
                ],
            ]
        }

    def _handle_update(self, update: Dict[str, Any]):
        msg = update.get("message")
        if not msg:
            return

        chat = msg.get("chat", {})
        sender_id = str(chat.get("id"))
        text = (msg.get("text") or "").strip()

        # Strict security: Only allow authorized chat ID
        if sender_id != self.chat_id:
            logger.warning(f"Unauthorized message from unknown chat ID {sender_id}")
            self.notifier.send_message(
                "⛔ <b>Akses Ditolak:</b> Akun Telegram Anda tidak terdaftar sebagai operator CUANIMUS.",
                chat_id=sender_id,
            )
            return

        if not text:
            return

        try:
            self._route_command(text, sender_id)
        except Exception as e:
            logger.exception(f"Error handling Telegram command '{text}': {e}")
            self.notifier.send_message(
                f"❌ Terjadi kesalahan saat memproses perintah <code>{text}</code>: {e}",
                reply_markup=INLINE_BACK_HOME,
                chat_id=sender_id,
            )

    def _route_command(self, text: str, sender_id: str):
        cmd = text.lower().strip()

        # 1. Main Menu
        if cmd in ("/start", "/menu", "/help", "menu", "help", "ℹ️ help & menu", "help & menu"):
            self.notifier.send_message(
                "📂 <i>Mode Dropdown Inline Aktif</i>",
                reply_markup={"remove_keyboard": True},
                chat_id=sender_id,
            )
            self.notifier.send_menu(chat_id=sender_id)

        # 2. System Status
        elif cmd in ("/status", "status", "📊 status"):
            self._handle_status(sender_id)

        # 3. Balance / Saldo
        elif cmd in ("/balance", "balance", "💰 saldo", "saldo", "/saldo"):
            self._handle_balance(sender_id)

        # 4. Market Watchlist
        elif cmd in ("/market", "market", "📈 market", "/watchlist", "watchlist"):
            self._handle_market(sender_id)

        # 5. Specific Ticker
        elif cmd.startswith("/ticker"):
            parts = text.split()
            sym = parts[1] if len(parts) > 1 else "ETH/USDT:USDT"
            self._handle_ticker(sym, sender_id)

        # 6. Positions
        elif cmd in ("/positions", "positions", "💼 positions", "posisi", "/posisi"):
            self._handle_positions(sender_id)

        # 7. Daily Performance
        elif cmd in ("/daily", "daily", "📅 kinerja", "kinerja", "kinerja harian", "/pnl", "pnl"):
            self._handle_daily(sender_id)

        # 8. Orders
        elif cmd in ("/orders", "orders", "📋 orders", "order", "/order", "riwayat order"):
            self._handle_orders(sender_id)

        # 9. Strategy Signal
        elif cmd.startswith("/signal") or cmd in ("signal", "⚡ signal v2a", "/signal_v2a", "signal v2a"):
            sym = "ETH/USDT:USDT"
            if cmd.startswith("/signal"):
                parts = text.split()
                if len(parts) > 1 and parts[1].upper() not in ("V2A", "V2B", "V2C"):
                    sym = parts[1]
            self._handle_signal(sym, sender_id)

        # 10. Quantitative Strategies List
        elif cmd in ("/strategy", "/strategies", "strategy", "strategies", "⚙️ strategi", "strategi", "strategi trading"):
            self._handle_strategy(sender_id)

        # 11. Risk Engine Status
        elif cmd in ("/risk", "risk", "🛡️ risk", "risiko", "manajemen risiko"):
            self._handle_risk(sender_id)

        # 12. AI & Agent Subsystem
        elif cmd in ("/agents", "agents", "🤖 ai & agents", "/ai_status", "ai", "agent"):
            self._handle_agents(sender_id)

        # 13. AI Query / Ask Copilot
        elif cmd.startswith("/ai"):
            prompt = text[3:].strip()
            self._handle_ai_query(prompt, sender_id)

        # 14. Database Status
        elif cmd in ("/db", "db", "🗄️ database", "/database", "database"):
            self._handle_database(sender_id)

        # 15. Database Switch
        elif cmd.startswith("/db_switch"):
            parts = text.split()
            target = parts[1] if len(parts) > 1 else "sqlite"
            self._handle_db_switch(target, sender_id)

        # 16. Autonomous Trading Engine
        elif cmd in ("/auto", "/autonomous", "auto", "autonomous", "🚀 autonomous", "🚀 auto engine", "auto trade"):
            self._handle_auto_engine(sender_id)

        # 17. Emergency Kill Switch
        elif cmd in ("/emergency_stop", "/kill", "🛑 kill switch", "kill switch", "kill"):
            self._handle_emergency_stop(sender_id)

        # 18. Reset Emergency Stop
        elif cmd in ("/reset_stop", "/reset", "🔄 reset stop", "reset stop", "reset"):
            self._handle_reset_stop(sender_id)

        else:
            self.notifier.send_message(
                f"❓ Perintah <code>{text}</code> tidak dikenali.\n\n"
                f"Ketik <code>/menu</code> untuk membuka panduan menu dropdown.",
                reply_markup=INLINE_BACK_HOME,
                chat_id=sender_id,
            )

    # -------------------------------------------------------------------------
    # FORMATTERS (Shared between Text Commands and Inline Dropdown Callbacks)
    # -------------------------------------------------------------------------

    def _format_status(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            status = self.api.get_system_status()
            env_str = status.get("environment", "PAPER").upper()
            safety = status.get("safety_status", "PAPER_SAFE")
            dry_run = "YA (Aman)" if status.get("dry_run") else "TIDAK"
            live_locked = "🔒 TERKUNCI" if not status.get("live_trading_enabled") else "⚠️ AKTIF"
            strat = status.get("active_strategy", "hybrid_v2c")
            risk = status.get("active_risk_profile", "balanced")
            health = status.get("platform_health", "HEALTHY")

            return (
                "📊 <b>STATUS PLATFORM CUANIMUS</b>\n\n"
                f"• <b>Kondisi Platform:</b> 🟢 {health}\n"
                f"• <b>Environment:</b> <code>{env_str}</code> (Dry-Run: {dry_run})\n"
                f"• <b>Real Capital LIVE:</b> {live_locked}\n"
                f"• <b>Safety Invariant:</b> <code>{safety}</code>\n"
                f"• <b>Strategi Aktif:</b> <code>{strat}</code>\n"
                f"• <b>Profil Risiko:</b> <code>{risk}</code>\n"
                f"• <b>Waktu Server:</b> <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>"
            )
        except Exception as e:
            return f"❌ Gagal mengambil status: {e}"

    def _format_balance(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            risk = self.api.get_risk_status()
            equity = risk.get("equity", 16.73)
            free_margin = risk.get("free_margin", 16.73)
            exp_info = risk.get("total_exposure", {})
            exposure = exp_info.get("current_usd", 0.0)
            exp_pct = exp_info.get("current_pct", 0.0)
            dd_info = risk.get("portfolio_drawdown", {})
            drawdown = dd_info.get("current_pct", 0.0)
            positions = self.api.get_positions()
            unrealized_pnl = sum(p.get("unrealized_pnl_usd", 0.0) for p in positions)

            pnl_bullet = "🟢" if unrealized_pnl >= 0 else "🔴"
            return (
                "💰 <b>SALDO & WALLET CUANIMUS</b>\n\n"
                f"• <b>Total Equity:</b> <code>${equity:,.2f} USDT</code>\n"
                f"• <b>Margin Bebas:</b> <code>${free_margin:,.2f} USDT</code>\n"
                f"• <b>Total Exposure:</b> <code>${exposure:,.2f} USDT</code> ({exp_pct:.1f}%)\n"
                f"• <b>Unrealized PnL:</b> {pnl_bullet} <code>{unrealized_pnl:+.2f} USDT</code>\n"
                f"• <b>Posisi Terbuka:</b> <code>{len(positions)} posisi</code>\n"
                f"• <b>Drawdown Portofolio:</b> <code>{drawdown:.2f}%</code>\n"
                "• <b>Mode Keamanan:</b> 🔒 <b>PAPER SAFE</b> (Simulasi Akurat)\n\n"
                f"<i>Diperbarui: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</i>"
            )
        except Exception as e:
            return f"❌ Gagal memuat saldo: {e}"

    def _format_market(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            wl = self.api.get_market_watchlist()
            lines = ["📈 <b>LIVE MARKET WATCHLIST (Binance Futures)</b>\n"]
            for item in wl:
                sym = item.get("symbol", "").split(":")[0]
                price = item.get("price")
                chg = item.get("change_24h_pct")
                regime = item.get("regime", "RANGING")

                if price is not None:
                    p_str = f"${price:,.4f}" if price < 1.0 else f"${price:,.2f}"
                    c_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                    bullet = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
                    lines.append(f"{bullet} <b>{sym}:</b> <code>{p_str}</code> ({c_str}) • <i>{regime}</i>")
                else:
                    lines.append(f"⚪ <b>{sym}:</b> <i>Sedang menghubungkan...</i>")

            lines.append(f"\n<i>Data Binance Futures aktual ({datetime.now(timezone.utc).strftime('%H:%M:%S UTC')})</i>")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal mengambil watchlist: {e}"

    def _format_ticker(self, symbol: str) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        sym_clean = symbol.upper().split("/")[0].split(":")[0].replace("USDT", "").strip()
        if not sym_clean:
            sym_clean = "ETH"
        full_sym = f"{sym_clean}/USDT:USDT"
        try:
            t = self.api.get_market_ticker(full_sym)
            if t.get("error"):
                return f"⚠️ Gagal mendapatkan ticker untuk <code>{symbol}</code>: {t['error']}"

            price = t.get("price", 0)
            chg = t.get("change_24h_pct", 0)
            high = t.get("high_24h", 0)
            low = t.get("low_24h", 0)
            vol = t.get("volume_24h_usd", 0)

            return (
                f"🎯 <b>TICKER DETAIL: {full_sym}</b>\n\n"
                f"• <b>Harga Terkini:</b> <code>${price:,.4f if price < 1.0 else price:,.2f}</code>\n"
                f"• <b>Perubahan 24 Jam:</b> <code>{chg:+.2f}%</code>\n"
                f"• <b>Tertinggi 24 Jam:</b> <code>${high:,.2f}</code>\n"
                f"• <b>Terendah 24 Jam:</b> <code>${low:,.2f}</code>\n"
                f"• <b>Volume 24 Jam:</b> <code>${vol:,.2f}</code>\n"
                "• <b>Bursa:</b> Binance Futures Perpetual"
            )
        except Exception as e:
            return f"❌ Error ticker: {e}"

    def _format_positions(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            positions = self.api.get_positions()
            if not positions:
                return (
                    "💼 <b>POSISI TRADING AKTIF</b>\n\n"
                    "Tidak ada posisi trading yang sedang terbuka (0 open positions).\n"
                    "Mode: <b>PAPER SAFE</b>."
                )

            lines = [f"💼 <b>POSISI TRADING AKTIF ({len(positions)})</b>\n"]
            for p in positions:
                sym = p.get("symbol", "").split(":")[0]
                side = (p.get("side") or "LONG").upper()
                entry = float(p.get("entry_price") or 0)
                mark = float(p.get("mark_price") or entry)
                pnl = float(p.get("unrealized_pnl") or 0)
                lev = p.get("leverage", 1)

                bullet = "🟢" if pnl >= 0 else "🔴"
                lines.append(
                    f"{bullet} <b>{sym} ({side} {lev}x)</b>\n"
                    f"  Entry: <code>${entry:,.2f}</code> | Mark: <code>${mark:,.2f}</code>\n"
                    f"  Unrealized PnL: <code>{pnl:+.2f} USDT</code>\n"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal mengambil posisi: {e}"

    def _format_daily(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            rows = []
            try:
                rows = self.api.db.query(
                    "SELECT * FROM trades WHERE is_open = 0 AND close_date >= ? ORDER BY id DESC",
                    (f"{today_str} 00:00:00",)
                )
            except Exception:
                rows = []

            total_today = len(rows)
            wins = sum(1 for r in rows if float(r.get("close_profit_abs") or 0.0) > 0)
            losses = sum(1 for r in rows if float(r.get("close_profit_abs") or 0.0) < 0)
            pnl_today_usd = sum(float(r.get("close_profit_abs") or 0.0) for r in rows)
            win_rate = (wins / total_today * 100.0) if total_today > 0 else 0.0

            risk = self.api.get_risk_status()
            daily_loss_info = risk.get("daily_loss", {})
            daily_loss_usd = daily_loss_info.get("current_usd", 0.0)
            limit_pct = daily_loss_info.get("limit_pct", 3.0)
            status_str = daily_loss_info.get("status", "NORMAL")

            pnl_bullet = "🟢" if pnl_today_usd >= 0 else "🔴"
            return (
                f"📅 <b>KINERJA HARIAN ({today_str} UTC)</b>\n\n"
                f"• <b>Total Trade Hari Ini:</b> <code>{total_today}</code>\n"
                f"• <b>Menang / Kalah:</b> 🟢 {wins}W / 🔴 {losses}L\n"
                f"• <b>Win Rate:</b> <code>{win_rate:.1f}%</code>\n"
                f"• <b>Realized PnL:</b> {pnl_bullet} <code>{pnl_today_usd:+.2f} USDT</code>\n"
                f"• <b>Kerugian Tercatat:</b> <code>${daily_loss_usd:.2f} USDT</code>\n"
                f"• <b>Batas Harian:</b> <code>{limit_pct:.1f}%</code> ({status_str})\n\n"
                "<i>Kinerja dihitung otomatis dari transaksi tertutup ledger database.</i>"
            )
        except Exception as e:
            return f"❌ Gagal memuat kinerja harian: {e}"

    def _format_orders(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            orders = self.api.get_orders()
            recent = orders[:5]
            if not recent:
                return "📋 Belum ada order yang tercatat."

            lines = ["📋 <b>RIWAYAT ORDER TERBARU</b>\n"]
            for o in recent:
                oid = o.get("client_order_id") or o.get("order_id") or "ORD"
                sym = o.get("symbol", "").split(":")[0]
                side = (o.get("side") or "buy").upper()
                status = (o.get("status") or "FILLED").upper()
                price = float(o.get("price") or 0)

                lines.append(f"• <b>{oid[:14]}</b>: {side} {sym} @ ${price:,.2f} [{status}]")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal mengambil order: {e}"

    def _format_signal(self, symbol: str) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        sym_clean = symbol.upper().split("/")[0].split(":")[0].replace("USDT", "").strip()
        if not sym_clean:
            sym_clean = "ETH"
        full_sym = f"{sym_clean}/USDT:USDT"
        try:
            res = self.api.inspect_strategy_signal("pullback_v2a", full_sym)
            sig = res.get("signal", "HOLD")
            strat = res.get("strategy_id", "pullback_v2a")
            sym = res.get("symbol", full_sym).split(":")[0]
            reason = res.get("reason", "Awaiting confirmation")
            score = float(res.get("confidence", res.get("confidence_score", 0.0)))

            emoji = "🟢" if sig == "LONG" else ("🔴" if sig == "SHORT" else "⚪")
            return (
                f"⚡ <b>EVALUASI SINYAL STRATEGI</b>\n\n"
                f"• <b>Strategi:</b> <code>{strat}</code>\n"
                f"• <b>Pair:</b> <code>{sym}</code> (15m Timeframe)\n"
                f"• <b>Sinyal:</b> {emoji} <b>{sig}</b>\n"
                f"• <b>Skor Keyakinan:</b> <code>{score:.1f}%</code>\n"
                f"• <b>Alasan:</b> <i>{res.get('conclusion', reason)}</i>\n\n"
                f"<i>Dihitung oleh engine teknikal CUANIMUS ({datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}).</i>"
            )
        except Exception as e:
            return f"❌ Gagal evaluasi sinyal: {e}"

    def _format_strategy(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            strats = self.api.list_strategies()
            lines = ["⚙️ <b>STRATEGI TRADING KUANTITATIF</b>\n"]
            for s in strats:
                sid = s.get("strategy_id", "")
                name = s.get("name", sid)
                desc = s.get("description", "")
                tf = s.get("timeframe", "15m")
                regimes = ", ".join(s.get("supported_regimes", []))
                lines.append(
                    f"• <b>{name}</b> (<code>{sid}</code>)\n"
                    f"  TF: <code>{tf}</code> | Regime: <i>{regimes}</i>\n"
                    f"  {desc[:65]}...\n"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal memuat strategi: {e}"

    def _format_risk(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            r = self.api.get_risk_status()
            cb = "🟢 ARMED & SAFE" if r.get("circuit_breaker_armed") else "🔒 EMERGENCY LOCKED"
            r_trade = r.get("risk_per_trade_pct", {}).get("current", 1.5)
            d_loss = r.get("daily_loss", {})
            d_pct = d_loss.get("current_pct", 0.0)
            d_lim = d_loss.get("limit_pct", 3.0)
            dd = r.get("portfolio_drawdown", {})
            dd_pct = dd.get("current_pct", 0.0)
            dd_lim = dd.get("limit_pct", 10.0)
            exp = r.get("total_exposure", {})
            exp_usd = exp.get("current_usd", 0.0)
            exp_lim = exp.get("limit_pct", 100.0)

            return (
                "🛡️ <b>RISK ENGINE & CIRCUIT BREAKER</b>\n\n"
                f"• <b>Circuit Breaker:</b> {cb}\n"
                f"• <b>Risk per Trade:</b> <code>{r_trade:.1f}%</code>\n"
                f"• <b>Daily Loss:</b> <code>{d_pct:.2f}% / {d_lim:.1f}%</code>\n"
                f"• <b>Portfolio Drawdown:</b> <code>{dd_pct:.2f}% / {dd_lim:.1f}%</code>\n"
                f"• <b>Total Exposure:</b> <code>${exp_usd:,.2f} ({exp.get('current_pct', 0.0):.1f}% / {exp_lim:.1f}%)</code>\n"
                f"• <b>Consecutive Losses:</b> <code>{r.get('consecutive_losses', {}).get('portfolio_current', 0)}</code>\n\n"
                "<i>Risk Engine memvalidasi seluruh order secara independen sebelum eksekusi.</i>"
            )
        except Exception as e:
            return f"❌ Gagal memuat status risiko: {e}"

    def _format_agents(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            agents = self.api.list_agents()
            ai_cfg = self.api.get_ai_config()
            mcp_tools = self.api.list_mcp_tools()
            sessions = self.api.list_agent_sessions()

            ai_active = "🟢 AKTIF" if ai_cfg.get("enabled") else "⚪ DETERMINISTIK (Off)"
            prov = ai_cfg.get("provider", "gemini").upper()
            model = ai_cfg.get("model_name", "gemini-2.5-flash")

            return (
                "🤖 <b>AI AGENT & MCP SUBSYSTEM</b>\n\n"
                f"• <b>AI Layer Status:</b> {ai_active}\n"
                f"• <b>Provider:</b> <code>{prov}</code>\n"
                f"• <b>Model:</b> <code>{model}</code>\n"
                f"• <b>Identitas Agent:</b> {len(agents)} terdaftar\n"
                f"• <b>Sesi Aktif:</b> {len(sessions)} sesi paper\n"
                f"• <b>Tools MCP:</b> {len(mcp_tools)} tools siap pakai di port :8889\n\n"
                "Gunakan <code>/ai [pertanyaan]</code> untuk berinteraksi langsung."
            )
        except Exception as e:
            return f"❌ Gagal memuat data AI Agent: {e}"

    def _format_database(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            db_stat = self.api.get_database_status()
            backend = db_stat.get("backend", "SQLITE").upper()
            connected = "🟢 TERHUBUNG" if db_stat.get("connected") else "🔴 TERPUTUS"
            counts = db_stat.get("counts", {})
            trades = counts.get("trades", 0)
            orders = counts.get("orders", 0)

            return (
                "🗄️ <b>STATUS DATABASE CUANIMUS</b>\n\n"
                f"• <b>Active Backend:</b> <b>{backend}</b>\n"
                f"• <b>Status Koneksi:</b> {connected}\n"
                f"• <b>Total Trades:</b> <code>{trades:,}</code> records\n"
                f"• <b>Total Orders:</b> <code>{orders:,}</code> records\n\n"
                "Gunakan tombol di dropdown untuk berpindah backend."
            )
        except Exception as e:
            return f"❌ Gagal mengambil status database: {e}"

    def _format_auto_engine(self) -> str:
        if not self.api:
            return "❌ Layanan Control Plane belum siap."
        try:
            status = self.api.get_autonomous_engine_status()
            eng_running = status.get("engine_running", False)
            eng_badge = "🟢 AKTIF" if eng_running else "⚪ NONAKTIF"
            emg_badge = "🚨 AKTIF" if status.get("emergency_stop_active") else "🛡️ NORMAL"
            active_cnt = status.get("active_profiles_count", 0)
            total_cnt = status.get("total_profiles_count", 0)
            open_pos = status.get("open_positions_count", 0)
            running_profiles = status.get("running_profiles", [])

            lines = [
                "🚀 <b>AUTONOMOUS TRADING ENGINE</b>",
                "━━━━━━━━━━━━━━━━━━━━━━",
                f"• <b>Engine Loop:</b> {eng_badge}",
                f"• <b>Emergency Stop:</b> {emg_badge}",
                f"• <b>Profil Aktif:</b> <code>{active_cnt} / {total_cnt}</code>",
                f"• <b>Posisi Terbuka:</b> <code>{open_pos}</code>",
                "",
                "📋 <b>Profil Trading Berjalan:</b>"
            ]

            if running_profiles:
                for p in running_profiles[:5]:
                    name = p.get("name", "Unknown")
                    pair = p.get("symbol", "-")
                    tf = p.get("timeframe", "-")
                    mode = p.get("decision_mode", "-").upper()
                    exec_mode = p.get("execution_mode", "-").upper()
                    lines.append(f"• <b>{name}</b> ({pair} • {tf})\n  Mode: <code>{mode}</code> | Exec: <code>{exec_mode}</code>")
            else:
                lines.append("<i>Belum ada profil trading yang sedang berjalan.</i>\n<i>Aktifkan profil melalui Web UI Control Center.</i>")

            lines.append("")
            lines.append("💡 <i>Mode: Strategy (A), AI Agent (B), Hybrid (C).</i>")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gagal mengambil status Autonomous Engine: {e}"

    # -------------------------------------------------------------------------
    # INLINE CALLBACK EDIT HELPERS
    # -------------------------------------------------------------------------

    def _edit_with_help(self, message_id: int, sender_id: str):
        msg = (
            "ℹ️ <b>Panduan Penggunaan Bot CUANIMUS</b>\n\n"
            "Gunakan tombol dropdown inline untuk navigasi cepat, atau gunakan perintah berikut:\n"
            "• <code>/status</code> — Status platform\n"
            "• <code>/balance</code> — Saldo equity & margin\n"
            "• <code>/market</code> — Live ticker Binance Futures\n"
            "• <code>/ticker [PAIR]</code> — Detail harga spesifik\n"
            "• <code>/positions</code> — Posisi trading aktif\n"
            "• <code>/daily</code> — Kinerja & PnL harian\n"
            "• <code>/orders</code> — 5 order terakhir\n"
            "• <code>/signal [PAIR]</code> — Sinyal strategi V2A\n"
            "• <code>/strategy</code> — Katalog strategi\n"
            "• <code>/risk</code> — Parameter risk engine\n"
            "• <code>/agents</code> — Status AI & MCP\n"
            "• <code>/ai [tanya]</code> — Tanya AI Copilot\n"
            "• <code>/db</code> — Status database\n"
            "• <code>/kill</code> — Emergency Stop seketika\n"
            "• <code>/reset</code> — Reset Emergency Stop\n"
            "• <code>/menu</code> — Tampilkan menu dropdown"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "◀️ Kembali ke Menu Utama", "callback_data": "menu:root"}],
            ]
        }
        self.notifier.edit_message_text(text=msg, message_id=message_id, chat_id=sender_id, reply_markup=markup)

    def _edit_with_ai_help(self, message_id: int, sender_id: str):
        msg = (
            "🧠 <b>Konsultasi AI Copilot</b>\n\n"
            "Kirim pertanyaan analisis trading langsung dari ponsel.\n\n"
            "<b>Format Perintah:</b>\n"
            "<code>/ai [pertanyaan Anda]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/ai analisa kondisi pasar ETH hari ini</code>\n"
            "• <code>/ai apakah market sedang trending atau ranging?</code>\n"
            "• <code>/ai jelaskan sinyal Pullback V2A terbaru</code>"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🤖 Status AI & MCP", "callback_data": "view:agents"}],
                [{"text": "◀️ Kategori AI", "callback_data": "menu:ai"}],
                [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
            ]
        }
        self.notifier.edit_message_text(text=msg, message_id=message_id, chat_id=sender_id, reply_markup=markup)

    def _execute_inline_emergency_stop(self, message_id: int, sender_id: str):
        if not self.api:
            return
        res = self.api.trigger_emergency_stop("Triggered via Telegram Bot Inline Menu")
        halted = res.get("halted_sessions", [])
        halted_str = ", ".join(halted) if halted else "Semua sesi dihentikan"
        msg = (
            "🚨 <b>EMERGENCY KILL SWITCH DIKIRIM!</b>\n\n"
            f"• <b>Status:</b> 🔒 EMERGENCY_STOP_ACTIVE\n"
            f"• <b>Sesi Dihentikan:</b> <code>{halted_str}</code>\n"
            "• <b>Aksi Eksekusi:</b> Semua pembuatan order baru di-veto seketika.\n\n"
            "Gunakan tombol di bawah untuk memulihkan operasi kembali normal."
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🔄 Reset Emergency Stop", "callback_data": "action:reset_stop"}],
                [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
            ]
        }
        self.notifier.edit_message_text(text=msg, message_id=message_id, chat_id=sender_id, reply_markup=markup)

    def _execute_inline_reset_stop(self, message_id: int, sender_id: str):
        if not self.api:
            return
        self.api.reset_emergency_stop()
        msg = (
            "🔄 <b>EMERGENCY STOP TELAH DIRESET</b>\n\n"
            "• <b>Status Sistem:</b> 🟢 NORMAL OPERATION\n"
            "• <b>Safety Invariant:</b> <code>PAPER_SAFE</code>\n"
            "• <b>Keterangan:</b> Sistem siap menerima perintah dan memantau sinyal kembali."
        )
        markup = {
            "inline_keyboard": [
                [{"text": "📊 Status Platform", "callback_data": "view:status"}],
                [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
            ]
        }
        self.notifier.edit_message_text(text=msg, message_id=message_id, chat_id=sender_id, reply_markup=markup)

    def _execute_inline_db_switch(self, target: str, message_id: int, sender_id: str):
        if not self.api:
            return
        tgt = target.lower().strip()
        res = self.api.switch_database_backend(tgt)
        new_backend = res.get("active_backend", tgt).upper()
        msg = (
            f"✅ <b>Database Berhasil Dialihkan!</b>\n\n"
            f"• <b>Backend Baru:</b> <code>{new_backend}</code>\n"
            f"• <b>Pesan:</b> {res.get('message', 'Koneksi aktif')}"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🗄️ Status Database", "callback_data": "view:db"}],
                [{"text": "◀️ Kategori Sistem", "callback_data": "menu:system"}],
                [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
            ]
        }
        self.notifier.edit_message_text(text=msg, message_id=message_id, chat_id=sender_id, reply_markup=markup)

    # -------------------------------------------------------------------------
    # COMMAND HANDLERS (Invoked by text commands)
    # -------------------------------------------------------------------------

    def _handle_status(self, sender_id: str):
        text = self._format_status()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:status", "menu:market"), chat_id=sender_id)

    def _handle_balance(self, sender_id: str):
        text = self._format_balance()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:balance", "menu:market"), chat_id=sender_id)

    def _handle_market(self, sender_id: str):
        text = self._format_market()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:market", "menu:market"), chat_id=sender_id)

    def _handle_ticker(self, symbol: str, sender_id: str):
        text = self._format_ticker(symbol)
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("menu:market", "menu:market"), chat_id=sender_id)

    def _handle_positions(self, sender_id: str):
        text = self._format_positions()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:positions", "menu:market"), chat_id=sender_id)

    def _handle_daily(self, sender_id: str):
        text = self._format_daily()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:daily", "menu:market"), chat_id=sender_id)

    def _handle_orders(self, sender_id: str):
        text = self._format_orders()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:orders", "menu:market"), chat_id=sender_id)

    def _handle_signal(self, symbol: str, sender_id: str):
        text = self._format_signal(symbol)
        sym_clean = symbol.upper().split("/")[0].split(":")[0].replace("USDT", "").strip() or "ETH"
        self.notifier.send_message(text, reply_markup=self._make_nav_markup(f"view:signal:{sym_clean}", "menu:strategy"), chat_id=sender_id)

    def _handle_strategy(self, sender_id: str):
        text = self._format_strategy()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:strategy", "menu:strategy"), chat_id=sender_id)

    def _handle_risk(self, sender_id: str):
        text = self._format_risk()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:risk", "menu:risk"), chat_id=sender_id)

    def _handle_agents(self, sender_id: str):
        text = self._format_agents()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:agents", "menu:ai"), chat_id=sender_id)

    def _handle_ai_query(self, prompt: str, sender_id: str):
        if not prompt:
            self.notifier.send_message(
                "💡 Format: <code>/ai [pertanyaan Anda]</code>\nContoh: <code>/ai evaluasi kondisi pasar ETH saat ini</code>",
                reply_markup=INLINE_BACK_HOME,
                chat_id=sender_id,
            )
            return

        self.notifier.send_message(f"🧠 <i>Menganalisis: \"{prompt}\"...</i>", chat_id=sender_id)
        try:
            test_res = self.api.test_ai_connection({"prompt": prompt})
            resp_msg = (
                f"🧠 <b>RESPONS AI COPILOT</b>\n\n"
                f"<b>Pertanyaan:</b> <i>{prompt}</i>\n\n"
                f"<b>Status:</b> {test_res.get('status', 'OK')}\n"
                f"<b>Pesan:</b> {test_res.get('message', 'Analisis selesai.')}\n"
                f"<b>Latency:</b> <code>{test_res.get('latency_ms', 0)}ms</code>"
            )
            self.notifier.send_message(resp_msg, reply_markup=INLINE_BACK_HOME, chat_id=sender_id)
        except Exception as e:
            self.notifier.send_message(f"❌ Gagal memproses AI: {e}", reply_markup=INLINE_BACK_HOME, chat_id=sender_id)

    def _handle_database(self, sender_id: str):
        text = self._format_database()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:db", "menu:system"), chat_id=sender_id)

    def _handle_db_switch(self, target: str, sender_id: str):
        if not self.api:
            return
        tgt = target.lower().strip()
        if tgt not in ("sqlite", "postgres", "postgresql"):
            self.notifier.send_message("⚠️ Target harus <code>sqlite</code> atau <code>postgres</code>.", reply_markup=INLINE_BACK_HOME, chat_id=sender_id)
            return

        try:
            res = self.api.switch_database_backend(tgt)
            new_backend = res.get("active_backend", tgt).upper()
            self.notifier.send_message(
                f"✅ <b>Database Berhasil Dialihkan!</b>\n\n"
                f"• <b>Backend Baru:</b> <code>{new_backend}</code>\n"
                f"• <b>Pesan:</b> {res.get('message', 'Koneksi aktif')}",
                reply_markup=self._make_nav_markup("view:db", "menu:system"),
                chat_id=sender_id,
            )
        except Exception as e:
            self.notifier.send_message(f"❌ Gagal alihkan database: {e}", reply_markup=INLINE_BACK_HOME, chat_id=sender_id)

    def _handle_emergency_stop(self, sender_id: str):
        if not self.api:
            return
        try:
            res = self.api.trigger_emergency_stop("Triggered via Telegram Bot Mobile Menu")
            halted = res.get("halted_sessions", [])
            halted_str = ", ".join(halted) if halted else "Semua sesi dihentikan"
            msg = (
                "🚨 <b>EMERGENCY KILL SWITCH DIKIRIM!</b>\n\n"
                f"• <b>Status:</b> 🔒 EMERGENCY_STOP_ACTIVE\n"
                f"• <b>Sesi Dihentikan:</b> <code>{halted_str}</code>\n"
                "• <b>Aksi Eksekusi:</b> Semua pembuatan order baru di-veto seketika.\n\n"
                "Gunakan tombol di bawah untuk memulihkan operasi kembali normal."
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "🔄 Reset Emergency Stop", "callback_data": "action:reset_stop"}],
                    [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
                ]
            }
            self.notifier.send_message(msg, reply_markup=markup, chat_id=sender_id)
        except Exception as e:
            self.notifier.send_message(f"❌ Gagal mengaktifkan Emergency Stop: {e}", reply_markup=INLINE_BACK_HOME, chat_id=sender_id)

    def _handle_reset_stop(self, sender_id: str):
        if not self.api:
            return
        try:
            res = self.api.reset_emergency_stop()
            msg = (
                "🔄 <b>EMERGENCY STOP TELAH DIRESET</b>\n\n"
                f"• <b>Status Sistem:</b> 🟢 NORMAL OPERATION\n"
                f"• <b>Safety Invariant:</b> <code>PAPER_SAFE</code>\n"
                f"• <b>Keterangan:</b> Sistem siap menerima perintah dan memantau sinyal kembali."
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "📊 Status Platform", "callback_data": "view:status"}],
                    [{"text": "🏠 Menu Utama", "callback_data": "menu:root"}],
                ]
            }
            self.notifier.send_message(msg, reply_markup=markup, chat_id=sender_id)
        except Exception as e:
            self.notifier.send_message(f"❌ Gagal mereset Emergency Stop: {e}", reply_markup=INLINE_BACK_HOME, chat_id=sender_id)

    def _handle_auto_engine(self, sender_id: str):
        text = self._format_auto_engine()
        self.notifier.send_message(text, reply_markup=self._make_nav_markup("view:auto_engine", "menu:strategy"), chat_id=sender_id)
