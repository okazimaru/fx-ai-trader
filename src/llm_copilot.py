from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from openai import OpenAI

from src.config import OPENAI_API_KEY, OPENAI_MODEL


AI_REPORT_SCHEMA = {
    "name": "fx_ai_report",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "market_summary": {
                "type": "string",
                "description": "現在の相場状況の要約"
            },
            "trade_permission": {
                "type": "string",
                "enum": ["entry_allowed", "wait", "risk_stop"],
                "description": "AIとしての取引可否"
            },
            "suggested_side": {
                "type": "string",
                "enum": ["long", "short", "none"],
                "description": "AIが示唆する方向"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"]
            },
            "main_reasons": {
                "type": "array",
                "items": {"type": "string"}
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"}
            },
            "next_action": {
                "type": "string",
                "description": "次に取るべき行動。発注指示ではなく運用上の提案。"
            }
        },
        "required": [
            "market_summary",
            "trade_permission",
            "suggested_side",
            "confidence",
            "risk_level",
            "main_reasons",
            "warnings",
            "next_action"
        ]
    },
    "strict": True
}


def _safe_tail_records(df: pd.DataFrame, columns: list[str], n: int = 5) -> list[dict]:
    if df.empty:
        return []

    existing_columns = [c for c in columns if c in df.columns]
    if not existing_columns:
        return []

    return (
        df[existing_columns]
        .tail(n)
        .astype(str)
        .to_dict(orient="records")
    )


def _get_run_info(daily_summary: pd.DataFrame) -> dict:
    if daily_summary.empty:
        return {
            "run_id": "unknown",
            "run_started_at_jst": "",
            "take_profit_pips": None,
            "stop_loss_pips": None,
            "unit_jpy_per_pip": None,
        }

    row = daily_summary.tail(1).iloc[0].to_dict()

    return {
        "run_id": str(row.get("run_id", "unknown")),
        "run_started_at_jst": str(row.get("run_started_at_jst", "")),
        "take_profit_pips": row.get("take_profit_pips"),
        "stop_loss_pips": row.get("stop_loss_pips"),
        "unit_jpy_per_pip": row.get("unit_jpy_per_pip"),
    }


def build_ai_context(
    price_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    ai_df: pd.DataFrame,
    daily_summary: pd.DataFrame,
    macro_events: pd.DataFrame,
) -> dict:
    latest_price = price_df.tail(1).to_dict(orient="records")[0] if not price_df.empty else {}

    context = {
        "run_info": _get_run_info(daily_summary),
        "symbol": latest_price.get("symbol", "USDJPY"),
        "latest_price": latest_price,
        "recent_trades": _safe_tail_records(
            trades_df,
            ["run_id", "entry_time", "symbol", "side", "entry_price", "exit_price", "pips", "pnl_jpy", "result", "exit_reason"],
            n=10,
        ),
        "daily_summary": _safe_tail_records(
            daily_summary,
            ["run_id", "trade_date", "trade_count", "total_pnl", "win_count", "lose_count", "win_rate", "take_profit_pips", "stop_loss_pips"],
            n=5,
        ),
        "recent_ai_decisions": _safe_tail_records(
            ai_df,
            ["timestamp_jst", "market_regime", "suggested_side", "confidence", "risk_level", "entry_permission", "final_decision", "risk_reason"],
            n=20,
        ),
        "macro_events": _safe_tail_records(
            macro_events,
            ["event_time_jst", "country", "currency", "event_name", "speaker", "importance", "status", "no_trade_before_min", "no_trade_after_min"],
            n=20,
        ),
    }

    return context


def save_ai_report_outputs(report: dict, daily_summary: pd.DataFrame) -> pd.DataFrame:
    run_info = _get_run_info(daily_summary)
    generated_at_jst = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "run_id": run_info["run_id"],
        "run_started_at_jst": run_info["run_started_at_jst"],
        "generated_at_jst": generated_at_jst,
        "model_name": OPENAI_MODEL,
        "trade_permission": report["trade_permission"],
        "suggested_side": report["suggested_side"],
        "confidence": float(report["confidence"]),
        "risk_level": report["risk_level"],
        "market_summary": report["market_summary"],
        "main_reasons_text": "\n".join(report["main_reasons"]),
        "warnings_text": "\n".join(report["warnings"]),
        "next_action": report["next_action"],
        "take_profit_pips": run_info["take_profit_pips"],
        "stop_loss_pips": run_info["stop_loss_pips"],
        "unit_jpy_per_pip": run_info["unit_jpy_per_pip"],
    }

    output_path = Path("data/output")
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "ai_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_df = pd.DataFrame([row])
    report_df.to_csv(output_path / "ai_report.csv", index=False)
    report_df.to_parquet(output_path / "ai_report.parquet", index=False)

    return report_df


def generate_ai_report(
    price_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    ai_df: pd.DataFrame,
    daily_summary: pd.DataFrame,
    macro_events: pd.DataFrame,
) -> dict:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY が .env に設定されていません。")

    client = OpenAI(api_key=OPENAI_API_KEY)
    context = build_ai_context(price_df, trades_df, ai_df, daily_summary, macro_events)

    system_prompt = """
あなたはFXデイトレード用のAI Copilotです。
目的は、売買を直接実行することではなく、相場環境・リスク・バックテスト結果をもとに運用判断を補助することです。

厳守事項:
- 絶対に「必ず勝てる」「全資金投入」「損切り不要」といった表現をしない。
- 実注文の直接指示ではなく、運用上の提案として出す。
- 経済イベント前後や損失が悪化している場合は、積極的に wait または risk_stop を選ぶ。
- confidence は過信せず、根拠が弱い場合は低めにする。
- 出力は指定されたJSON Schemaに完全準拠する。
"""

    user_prompt = f"""
以下は現在のFX AI Trader MVPの状態です。
この情報をもとに、AI相場レビューを作成してください。

データ:
{json.dumps(context, ensure_ascii=False, default=str)}
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": AI_REPORT_SCHEMA["name"],
                "schema": AI_REPORT_SCHEMA["schema"],
                "strict": True,
            }
        },
    )

    report = json.loads(response.output_text)
    save_ai_report_outputs(report, daily_summary)

    return report
