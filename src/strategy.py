from __future__ import annotations

import pandas as pd


def judge_signal(row: pd.Series) -> tuple[str, str]:
    """
    return:
      side: long / short / none
      reason: 判断理由
    """
    if row["ma_short"] > row["ma_long"] and 40 <= row["rsi"] <= 70:
        return "long", "短期MAが長期MAを上回り、RSIが許容範囲"

    if row["ma_short"] < row["ma_long"] and 30 <= row["rsi"] <= 60:
        return "short", "短期MAが長期MAを下回り、RSIが許容範囲"

    return "none", "条件未達"
