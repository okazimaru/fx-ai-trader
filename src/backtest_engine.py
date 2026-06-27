from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.ai_copilot import create_ai_decision
from src.risk_gate import risk_gate_allows_trade
from src.strategy import judge_signal


def create_run_metadata(
    take_profit_pips: float,
    stop_loss_pips: float,
    unit_jpy_per_pip: float,
) -> dict:
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
    run_id = now_jst.strftime("%Y%m%d_%H%M%S")

    return {
        "run_id": run_id,
        "run_started_at_jst": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
        "take_profit_pips": float(take_profit_pips),
        "stop_loss_pips": float(stop_loss_pips),
        "unit_jpy_per_pip": float(unit_jpy_per_pip),
    }


def add_run_metadata(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    df = df.copy()

    for key, value in metadata.items():
        df[key] = value

    # QuickSightで見やすいように、run_id系を先頭へ寄せる
    preferred_order = [
        "run_id",
        "run_started_at_jst",
        "take_profit_pips",
        "stop_loss_pips",
        "unit_jpy_per_pip",
    ]

    ordered_columns = [c for c in preferred_order if c in df.columns] + [
        c for c in df.columns if c not in preferred_order
    ]

    return df[ordered_columns]


def run_backtest(
    df: pd.DataFrame,
    macro_events: pd.DataFrame,
    take_profit_pips: float = 10.0,
    stop_loss_pips: float = 7.0,
    unit_jpy_per_pip: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    run_metadata = create_run_metadata(
        take_profit_pips=take_profit_pips,
        stop_loss_pips=stop_loss_pips,
        unit_jpy_per_pip=unit_jpy_per_pip,
    )

    trades = []
    ai_decisions = []

    position = None
    daily_pnl = 0.0
    current_trade_date = None
    consecutive_losses = 0

    for _, row in df.iterrows():
        now = pd.Timestamp(row["timestamp"])
        trade_date = now.date()

        if current_trade_date != trade_date:
            current_trade_date = trade_date
            daily_pnl = 0.0
            consecutive_losses = 0

        price = float(row["close"])
        spread = float(row["spread"])

        side, signal_reason = judge_signal(row)

        risk_allowed, risk_reason = risk_gate_allows_trade(
            now_jst=now,
            spread=spread,
            daily_pnl=daily_pnl,
            consecutive_losses=consecutive_losses,
            macro_events=macro_events,
        )

        ai_decision = create_ai_decision(
            timestamp_jst=now,
            symbol=row["symbol"],
            suggested_side=side,
            signal_reason=signal_reason,
            risk_allowed=risk_allowed,
            risk_reason=risk_reason,
            rsi=row["rsi"],
            ma_short=row["ma_short"],
            ma_long=row["ma_long"],
        )
        ai_decisions.append(ai_decision)

        if position is None:
            if side in ["long", "short"] and risk_allowed:
                position = {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": row["symbol"],
                    "strategy_name": "ma_rsi_v1",
                    "side": side,
                    "entry_time": now,
                    "entry_price": price,
                    "entry_reason": signal_reason,
                    "ai_decision_id": ai_decision["decision_id"],
                }
            continue

        if position is not None:
            if position["side"] == "long":
                pnl_pips = (price - position["entry_price"]) * 100
            else:
                pnl_pips = (position["entry_price"] - price) * 100

            exit_reason = None
            if pnl_pips >= take_profit_pips:
                exit_reason = "take_profit"
            elif pnl_pips <= -stop_loss_pips:
                exit_reason = "stop_loss"

            if exit_reason:
                pnl_jpy = pnl_pips * unit_jpy_per_pip
                daily_pnl += pnl_jpy

                if pnl_jpy < 0:
                    consecutive_losses += 1
                    result = "lose"
                elif pnl_jpy > 0:
                    consecutive_losses = 0
                    result = "win"
                else:
                    result = "breakeven"

                trades.append(
                    {
                        **position,
                        "exit_time": now,
                        "exit_price": price,
                        "pips": pnl_pips,
                        "pnl_jpy": pnl_jpy,
                        "result": result,
                        "exit_reason": exit_reason,
                    }
                )

                position = None

    trades_df = pd.DataFrame(trades)
    ai_df = pd.DataFrame(ai_decisions)

    if not trades_df.empty:
        daily_summary = (
            trades_df.assign(trade_date=trades_df["entry_time"].dt.date)
            .groupby("trade_date")
            .agg(
                trade_count=("trade_id", "count"),
                total_pnl=("pnl_jpy", "sum"),
                win_count=("result", lambda s: (s == "win").sum()),
                lose_count=("result", lambda s: (s == "lose").sum()),
                avg_pnl=("pnl_jpy", "mean"),
            )
            .reset_index()
        )
        daily_summary["win_rate"] = daily_summary["win_count"] / daily_summary["trade_count"]
    else:
        daily_summary = pd.DataFrame()

    trades_df = add_run_metadata(trades_df, run_metadata) if not trades_df.empty else trades_df
    ai_df = add_run_metadata(ai_df, run_metadata) if not ai_df.empty else ai_df
    daily_summary = add_run_metadata(daily_summary, run_metadata) if not daily_summary.empty else daily_summary

    return trades_df, ai_df, daily_summary


def save_outputs(
    trades_df: pd.DataFrame,
    ai_df: pd.DataFrame,
    daily_summary: pd.DataFrame,
    output_dir: str = "data/output",
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    trades_df.to_csv(path / "trades.csv", index=False)
    ai_df.to_csv(path / "ai_decisions.csv", index=False)
    daily_summary.to_csv(path / "daily_summary.csv", index=False)

    if not trades_df.empty:
        trades_df.to_parquet(path / "trades.parquet", index=False)
    if not ai_df.empty:
        ai_df.to_parquet(path / "ai_decisions.parquet", index=False)
    if not daily_summary.empty:
        daily_summary.to_parquet(path / "daily_summary.parquet", index=False)
