from __future__ import annotations

import uuid
import pandas as pd


def create_ai_decision(
    timestamp_jst: pd.Timestamp,
    symbol: str,
    suggested_side: str,
    signal_reason: str,
    risk_allowed: bool,
    risk_reason: str,
    rsi: float,
    ma_short: float,
    ma_long: float,
) -> dict:
    if not risk_allowed:
        confidence = 0.0
        final_decision = "wait"
        risk_level = "high"
        entry_permission = False
    elif suggested_side in ["long", "short"]:
        confidence = 0.65
        final_decision = "entry_candidate"
        risk_level = "medium"
        entry_permission = True
    else:
        confidence = 0.2
        final_decision = "wait"
        risk_level = "low"
        entry_permission = False

    if ma_short > ma_long:
        market_regime = "uptrend"
    elif ma_short < ma_long:
        market_regime = "downtrend"
    else:
        market_regime = "range"

    return {
        "decision_id": str(uuid.uuid4()),
        "timestamp_jst": timestamp_jst,
        "symbol": symbol,
        "model_name": "rule_based_ai_stub",
        "model_version": "v0.1",
        "market_regime": market_regime,
        "suggested_side": suggested_side,
        "confidence": confidence,
        "risk_level": risk_level,
        "entry_permission": entry_permission,
        "signal_reason": signal_reason,
        "risk_reason": risk_reason,
        "rsi": float(rsi),
        "ma_short": float(ma_short),
        "ma_long": float(ma_long),
        "final_decision": final_decision,
    }
