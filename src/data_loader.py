from __future__ import annotations

from pathlib import Path
from typing import IO

import numpy as np
import pandas as pd


REQUIRED_PRICE_COLUMNS = ["timestamp", "open", "high", "low", "close"]


def generate_sample_usdjpy_5m(output_path: str = "data/sample/usdjpy_5m.csv") -> pd.DataFrame:
    np.random.seed(42)

    start = pd.Timestamp("2026-06-01 09:00:00", tz="Asia/Tokyo")
    periods = 12 * 24 * 10
    timestamps = pd.date_range(start=start, periods=periods, freq="5min")

    base_price = 160.0
    returns = np.random.normal(loc=0.00001, scale=0.0006, size=periods)
    close = base_price + np.cumsum(returns)

    high = close + np.random.uniform(0.005, 0.03, size=periods)
    low = close - np.random.uniform(0.005, 0.03, size=periods)
    open_ = close + np.random.uniform(-0.01, 0.01, size=periods)
    spread = np.random.uniform(0.002, 0.02, size=periods)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": "USDJPY",
            "timeframe": "5m",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread": spread,
        }
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    return df


def normalize_price_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "価格CSVに必須列がありません: "
            + ", ".join(missing)
            + "。必要列は timestamp, open, high, low, close です。"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    if df["timestamp"].isna().any():
        raise ValueError("timestamp を日時として読み取れない行があります。")

    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Tokyo")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Tokyo")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("open/high/low/close に数値変換できない値があります。")

    if "symbol" not in df.columns:
        df["symbol"] = "USDJPY"

    if "timeframe" not in df.columns:
        df["timeframe"] = "5m"

    if "spread" not in df.columns:
        df["spread"] = 0.01
    else:
        df["spread"] = pd.to_numeric(df["spread"], errors="coerce").fillna(0.01)

    df = df.sort_values("timestamp").reset_index(drop=True)

    return df[
        [
            "timestamp",
            "symbol",
            "timeframe",
            "open",
            "high",
            "low",
            "close",
            "spread",
        ]
    ]


def load_price_data(path: str = "data/sample/usdjpy_5m.csv") -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        df = generate_sample_usdjpy_5m(path)
    else:
        df = pd.read_csv(csv_path)

    return normalize_price_data(df)


def load_uploaded_price_data(uploaded_file: IO[bytes]) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    return normalize_price_data(df)


def get_price_data_quality(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "row_count": 0,
            "start_time": "",
            "end_time": "",
            "latest_age_minutes": None,
            "freshness_status": "no_data",
            "message": "価格データがありません。",
        }

    now_jst = pd.Timestamp.now(tz="Asia/Tokyo")
    start_time = pd.Timestamp(df["timestamp"].min())
    end_time = pd.Timestamp(df["timestamp"].max())

    latest_age_minutes = (now_jst - end_time).total_seconds() / 60

    if latest_age_minutes <= 15:
        freshness_status = "fresh"
        message = "価格データは新鮮です。"
    elif latest_age_minutes <= 60:
        freshness_status = "slightly_old"
        message = "価格データはやや古いです。短期売買では注意してください。"
    else:
        freshness_status = "stale"
        message = "価格データが古いです。現在相場の判断には使いすぎないでください。"

    return {
        "row_count": int(len(df)),
        "start_time": str(start_time),
        "end_time": str(end_time),
        "latest_age_minutes": round(latest_age_minutes, 1),
        "freshness_status": freshness_status,
        "message": message,
    }
