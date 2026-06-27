from __future__ import annotations

from datetime import timedelta
import pandas as pd


def is_macro_event_blocked(now_jst: pd.Timestamp, macro_events: pd.DataFrame) -> tuple[bool, str | None]:
    if macro_events.empty:
        return False, None

    for _, event in macro_events.iterrows():
        if event.get("importance") != "high":
            continue

        event_time = pd.Timestamp(event["event_time_jst"])
        before = int(event.get("no_trade_before_min", 60))
        after = int(event.get("no_trade_after_min", 60))

        start = event_time - timedelta(minutes=before)
        end = event_time + timedelta(minutes=after)

        if start <= now_jst <= end:
            return True, f"重要イベント前後のため停止: {event['event_name']}"

    return False, None


def risk_gate_allows_trade(
    now_jst: pd.Timestamp,
    spread: float,
    daily_pnl: float,
    consecutive_losses: int,
    macro_events: pd.DataFrame,
    max_spread: float = 0.03,
    max_daily_loss: float = -3000,
    max_consecutive_losses: int = 3,
) -> tuple[bool, str]:
    if spread > max_spread:
        return False, f"スプレッド拡大のため停止: {spread:.4f}"

    if daily_pnl <= max_daily_loss:
        return False, f"日次最大損失に到達: {daily_pnl:.0f}円"

    if consecutive_losses >= max_consecutive_losses:
        return False, f"連敗停止: {consecutive_losses}連敗"

    blocked, reason = is_macro_event_blocked(now_jst, macro_events)
    if blocked:
        return False, reason or "重要イベント前後のため停止"

    return True, "取引許可"
