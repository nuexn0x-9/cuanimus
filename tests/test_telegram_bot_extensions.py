import unittest
from unittest.mock import MagicMock, patch
from cuanimus.api.telegram import TelegramBotListener, TelegramNotifier


class TestTelegramBotExtensions(unittest.TestCase):
    def setUp(self):
        self.mock_notifier = MagicMock(spec=TelegramNotifier)
        self.mock_notifier.chat_id = "123456"
        self.mock_notifier.bot_token = "mock_token"

        self.mock_api = MagicMock()
        self.poller = TelegramBotListener(notifier=self.mock_notifier, api_service=self.mock_api)

    def test_make_positions_markup(self):
        self.mock_api.get_positions.return_value = [
            {"id": 101, "symbol": "BTC/USDT:USDT", "side": "LONG"},
            {"id": 102, "symbol": "ETH/USDT:USDT", "side": "SHORT"},
        ]
        markup = self.poller._make_positions_markup()
        buttons = markup.get("inline_keyboard", [])
        self.assertTrue(any("action:close_pos:101" in btn.get("callback_data", "") for row in buttons for btn in row))
        self.assertTrue(any("action:close_all_pos" in btn.get("callback_data", "") for row in buttons for btn in row))

    def test_make_auto_engine_markup(self):
        self.mock_api.get_autonomous_engine_status.return_value = {
            "running_profiles": [{"profile_id": "prof_btc"}]
        }
        self.mock_api.list_trading_profiles.return_value = [
            {"profile_id": "prof_btc", "symbol": "BTC/USDT:USDT"},
            {"profile_id": "prof_eth", "symbol": "ETH/USDT:USDT"},
        ]
        markup = self.poller._make_auto_engine_markup()
        buttons = markup.get("inline_keyboard", [])
        # Inactive profile should have start button
        self.assertTrue(any("action:auto:start:prof_eth" in btn.get("callback_data", "") for row in buttons for btn in row))
        # Active profile should have stop button
        self.assertTrue(any("action:auto:stop:prof_btc" in btn.get("callback_data", "") for row in buttons for btn in row))

    def test_close_command_single_position(self):
        self.mock_api.get_positions.return_value = [
            {"id": 101, "symbol": "BTC/USDT:USDT"}
        ]
        self.mock_api.close_position.return_value = {
            "symbol": "BTC/USDT:USDT",
            "exit_price": 60000.0,
            "profit_abs": 150.0,
            "profit_pct": 2.5,
        }
        self.poller._route_command("/close 101", "123456")
        self.mock_api.close_position.assert_called_once_with(trade_id=101, reason="telegram_operator")
        self.mock_notifier.send_message.assert_called()

    def test_buy_command(self):
        self.mock_api.create_manual_order.return_value = {
            "trade_id": 202,
            "price": 3000.0,
            "stop_loss": 2950.0,
            "status": "FILLED",
        }
        self.poller._route_command("/buy ETH 0.05 3000", "123456")
        self.mock_api.create_manual_order.assert_called_once_with(
            symbol="ETH/USDT:USDT",
            side="BUY",
            order_type="LIMIT",
            amount=0.05,
            price=3000.0,
            stop_loss_pct=1.5,
            take_profit_pct=3.0,
            leverage=3.0,
        )

    def test_auto_start_and_stop_commands(self):
        self.poller._route_command("/auto_start prof_test", "123456")
        self.mock_api.start_trading_profile.assert_called_once_with("prof_test")

        self.poller._route_command("/auto_stop prof_test", "123456")
        self.mock_api.stop_trading_profile.assert_called_once_with("prof_test")


if __name__ == "__main__":
    unittest.main()
