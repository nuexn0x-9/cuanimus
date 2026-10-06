"""
Unit tests for CUANIMUS Telegram Interactive Mobile Bot & Menu.
"""
import unittest
from unittest.mock import MagicMock, patch
from cuanimus.api.telegram import TelegramNotifier, TelegramBotListener, MAIN_MENU_KEYBOARD
from cuanimus.api.control_plane import ControlPlaneAPI


class TestTelegramInteractiveMenu(unittest.TestCase):
    """Verifies menu definitions, formatting, and command routing."""

    def setUp(self):
        self.api = ControlPlaneAPI(base_dir=".")
        self.notifier = TelegramNotifier()
        self.listener = TelegramBotListener(notifier=self.notifier, api_service=self.api)

    def test_main_menu_keyboard_structure(self):
        self.assertIn("inline_keyboard", MAIN_MENU_KEYBOARD)
        rows = MAIN_MENU_KEYBOARD["inline_keyboard"]
        self.assertGreaterEqual(len(rows), 4)
        btn_texts = [btn["text"] for row in rows for btn in row]
        self.assertTrue(any("Portofolio & Pasar" in t for t in btn_texts))
        self.assertTrue(any("Sinyal & Strategi" in t for t in btn_texts))
        self.assertTrue(any("AI Copilot" in t for t in btn_texts))
        self.assertTrue(any("Risiko" in t for t in btn_texts))
        self.assertTrue(any("KILL SWITCH" in t for t in btn_texts))

    @patch.object(TelegramNotifier, "edit_message_text")
    def test_route_dropdown_callbacks(self, mock_edit):
        mock_edit.return_value = {"success": True}
        # Test expanding categories and views
        self.listener._route_callback("menu:market", 100, self.listener.chat_id)
        self.assertTrue(mock_edit.called)
        self.assertIn("Kategori: Portofolio & Pasar", mock_edit.call_args[1]["text"])

        self.listener._route_callback("view:balance", 100, self.listener.chat_id)
        self.assertIn("SALDO & WALLET CUANIMUS", mock_edit.call_args[1]["text"])

        self.listener._route_callback("view:status", 100, self.listener.chat_id)
        self.assertIn("STATUS PLATFORM CUANIMUS", mock_edit.call_args[1]["text"])

        self.listener._route_callback("menu:root", 100, self.listener.chat_id)
        self.assertIn("CUANIMUS Mobile Control Center", mock_edit.call_args[1]["text"])

    @patch.object(TelegramNotifier, "send_message")
    def test_route_status_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("📊 Status", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("STATUS PLATFORM CUANIMUS", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_market_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("📈 Market", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("LIVE MARKET WATCHLIST", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_signal_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("⚡ Signal V2A", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("EVALUASI SINYAL STRATEGI", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_database_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("🗄️ Database", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("STATUS DATABASE CUANIMUS", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_balance_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("/balance", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("SALDO & WALLET CUANIMUS", sent_text)
        self.assertIn("Total Equity", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_daily_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("/daily", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("KINERJA HARIAN", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_strategy_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("⚙️ Strategi", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("STRATEGI TRADING KUANTITATIF", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_risk_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("🛡️ Risk", self.listener.chat_id)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("RISK ENGINE & CIRCUIT BREAKER", sent_text)

    @patch.object(TelegramNotifier, "send_message")
    def test_route_orders_command(self, mock_send):
        mock_send.return_value = {"success": True}
        self.listener._route_command("📋 Orders", self.listener.chat_id)
        self.assertTrue(mock_send.called)

    @patch.object(TelegramNotifier, "send_message")
    def test_unauthorized_sender_rejected(self, mock_send):
        mock_send.return_value = {"success": True}
        # Fake update from rogue sender
        rogue_update = {
            "message": {
                "chat": {"id": 999999999},
                "text": "/emergency_stop"
            }
        }
        self.listener._handle_update(rogue_update)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("Akses Ditolak", sent_text)


if __name__ == "__main__":
    unittest.main()
