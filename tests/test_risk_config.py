from __future__ import annotations

import unittest

import pandas as pd

from src.backtest_engine import create_run_metadata
from src.risk_gate import risk_gate_allows_trade
from src.trading_config import load_trading_config


class RiskConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_trading_config()
        self.now = pd.Timestamp("2026-07-26 09:00:00")
        self.events = pd.DataFrame()

    def call_gate(
        self,
        *,
        spread: float = 0.01,
        daily_pnl: float = 0.0,
        consecutive_losses: int = 0,
        trades_today: int = 0,
    ) -> tuple[bool, str]:
        return risk_gate_allows_trade(
            now_jst=self.now,
            spread=spread,
            daily_pnl=daily_pnl,
            consecutive_losses=consecutive_losses,
            trades_today=trades_today,
            macro_events=self.events,
            config=self.config.risk,
        )

    def test_trade_is_allowed_below_all_limits(self) -> None:
        allowed, reason = self.call_gate()

        self.assertTrue(allowed)
        self.assertEqual(reason, "取引許可")

    def test_daily_loss_limit_uses_positive_config_value(self) -> None:
        allowed, reason = self.call_gate(
            daily_pnl=-self.config.risk.max_daily_loss_jpy,
        )

        self.assertFalse(allowed)
        self.assertIn("日次最大損失", reason)

    def test_consecutive_loss_limit_blocks_trade(self) -> None:
        allowed, reason = self.call_gate(
            consecutive_losses=self.config.risk.max_consecutive_losses,
        )

        self.assertFalse(allowed)
        self.assertIn("連敗停止", reason)

    def test_daily_trade_count_limit_blocks_trade(self) -> None:
        allowed, reason = self.call_gate(
            trades_today=self.config.risk.max_trades_per_day,
        )

        self.assertFalse(allowed)
        self.assertIn("1日最大取引回数", reason)

    def test_run_metadata_records_config_version_and_limits(self) -> None:
        metadata = create_run_metadata(
            take_profit_pips=10.0,
            stop_loss_pips=7.0,
            unit_jpy_per_pip=100.0,
            trading_config=self.config,
        )

        self.assertEqual(metadata["config_version"], self.config.version)
        self.assertEqual(
            metadata["max_trades_per_day"],
            self.config.risk.max_trades_per_day,
        )
        self.assertEqual(metadata["strategy_name"], self.config.strategy.name)


if __name__ == "__main__":
    unittest.main()
