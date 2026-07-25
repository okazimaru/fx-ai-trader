from __future__ import annotations

import unittest

import pandas as pd

from src.strategy import judge_signal
from src.trading_config import load_trading_config


class TradingConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        config = load_trading_config()

        self.assertEqual(config.version, 2)
        self.assertEqual(config.market.symbol, "USDJPY")
        self.assertEqual(config.market.timeframe, "5m")
        self.assertEqual(config.risk.max_daily_loss_jpy, 5000.0)
        self.assertGreater(config.execution.take_profit_pips, 0)
        self.assertGreater(config.execution.stop_loss_pips, 0)

    def test_long_signal_uses_configured_rsi_range(self) -> None:
        config = load_trading_config()
        row = pd.Series({"ma_short": 151.0, "ma_long": 150.0, "rsi": 55.0})

        side, reason = judge_signal(row, config.strategy)

        self.assertEqual(side, "long")
        self.assertIn("ロング許容範囲", reason)

    def test_short_signal_uses_configured_rsi_range(self) -> None:
        config = load_trading_config()
        row = pd.Series({"ma_short": 149.0, "ma_long": 150.0, "rsi": 45.0})

        side, reason = judge_signal(row, config.strategy)

        self.assertEqual(side, "short")
        self.assertIn("ショート許容範囲", reason)

    def test_signal_is_none_outside_configured_range(self) -> None:
        config = load_trading_config()
        row = pd.Series({"ma_short": 151.0, "ma_long": 150.0, "rsi": 85.0})

        side, _ = judge_signal(row, config.strategy)

        self.assertEqual(side, "none")


if __name__ == "__main__":
    unittest.main()
