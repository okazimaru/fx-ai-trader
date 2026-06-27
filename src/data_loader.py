from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def generate_sample_usdjpy_5m(output_path: str = "data/sample/usdjpy_5m.csv") -> pd.DataFrame:
    """
    USD/JPYの5分足サンプルデータを生成する。
    本番ではFX業者APIや取得済みCSVに差し替える。
    """
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


def load_price_data(path: str = "data/sample/usdjpy_5m.csv") -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return generate_sample_usdjpy_5m(path)

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
