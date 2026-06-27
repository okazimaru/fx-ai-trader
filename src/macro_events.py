from __future__ import annotations

from pathlib import Path
import pandas as pd


def create_sample_macro_events(output_path: str = "data/sample/macro_events.csv") -> pd.DataFrame:
    events = [
        {
            "event_id": "US_CPI_20260601",
            "event_time_jst": "2026-06-01 21:30:00+09:00",
            "country": "US",
            "currency": "USD",
            "category": "indicator",
            "event_name": "US CPI",
            "speaker": "",
            "importance": "high",
            "forecast": "",
            "previous": "",
            "actual": "",
            "status": "scheduled",
            "no_trade_before_min": 60,
            "no_trade_after_min": 90,
        },
        {
            "event_id": "FOMC_20260604",
            "event_time_jst": "2026-06-04 03:00:00+09:00",
            "country": "US",
            "currency": "USD",
            "category": "central_bank",
            "event_name": "FOMC Rate Decision",
            "speaker": "Fed Chair",
            "importance": "high",
            "forecast": "",
            "previous": "",
            "actual": "",
            "status": "scheduled",
            "no_trade_before_min": 120,
            "no_trade_after_min": 120,
        },
    ]

    df = pd.DataFrame(events)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return df


def load_macro_events(path: str = "data/sample/macro_events.csv") -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return create_sample_macro_events(path)

    df = pd.read_csv(csv_path)
    df["event_time_jst"] = pd.to_datetime(df["event_time_jst"])
    return df
