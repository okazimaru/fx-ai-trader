from __future__ import annotations

import pandas as pd

from src.trading_config import StrategyConfig, load_trading_config


def judge_signal(
    row: pd.Series,
    config: StrategyConfig | None = None,
) -> tuple[str, str]:
    """
    return:
      side: long / short / none
      reason: 判断理由
    """
    strategy = config or load_trading_config().strategy
    rsi = float(row["rsi"])

    if (
        row["ma_short"] > row["ma_long"]
        and strategy.long_rsi_min <= rsi <= strategy.long_rsi_max
    ):
        return (
            "long",
            "短期MAが長期MAを上回り、"
            f"RSIがロング許容範囲({strategy.long_rsi_min:.0f}〜{strategy.long_rsi_max:.0f})",
        )

    if (
        row["ma_short"] < row["ma_long"]
        and strategy.short_rsi_min <= rsi <= strategy.short_rsi_max
    ):
        return (
            "short",
            "短期MAが長期MAを下回り、"
            f"RSIがショート許容範囲({strategy.short_rsi_min:.0f}〜{strategy.short_rsi_max:.0f})",
        )

    return "none", "設定された売買条件に未達"
