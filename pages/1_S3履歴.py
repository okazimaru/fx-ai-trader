from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.auth import require_login
from src.s3_history import load_daily_summary_history, load_run_dataset


st.set_page_config(
    page_title="FX AI Trader 履歴",
    page_icon="🗂️",
    layout="wide",
)

st.title("S3運用履歴")
st.caption("S3に保存したバックテスト結果とAIレビューをrun_id単位で確認します。")

require_login()


@st.cache_data(ttl=300, show_spinner=False)
def get_summary_history() -> pd.DataFrame:
    return load_daily_summary_history(max_runs=100)


@st.cache_data(ttl=300, show_spinner=False)
def get_run_dataset(dataset: str, run_id: str) -> pd.DataFrame:
    return load_run_dataset(dataset, run_id)


if st.button("履歴を再読み込み"):
    st.cache_data.clear()
    st.rerun()

try:
    with st.spinner("S3から履歴を読み込んでいます..."):
        history_df = get_summary_history()
except Exception as exc:
    st.error(f"S3履歴の読み込みに失敗しました: {exc}")
    st.stop()

if history_df.empty:
    st.info("S3にdaily_summary履歴がありません。メイン画面で疑似売買を実行し、S3へアップロードしてください。")
    st.stop()

run_ids = history_df["run_id"].dropna().astype(str).drop_duplicates().tolist()

if not run_ids:
    st.warning("履歴ファイルにrun_idがありません。")
    st.stop()

run_count = len(run_ids)
total_trade_count = int(history_df.get("trade_count", pd.Series(dtype=float)).fillna(0).sum())
total_pnl = float(history_df.get("total_pnl", pd.Series(dtype=float)).fillna(0).sum())

m1, m2, m3 = st.columns(3)
m1.metric("保存run数", f"{run_count}")
m2.metric("累計取引回数", f"{total_trade_count:,}")
m3.metric("累計損益", f"{total_pnl:,.0f} 円")

st.subheader("run別損益")
run_summary = (
    history_df.groupby("run_id", as_index=False)
    .agg(
        run_started_at_jst=("run_started_at_jst", "max"),
        trade_count=("trade_count", "sum"),
        total_pnl=("total_pnl", "sum"),
        win_count=("win_count", "sum"),
        lose_count=("lose_count", "sum"),
        take_profit_pips=("take_profit_pips", "first"),
        stop_loss_pips=("stop_loss_pips", "first"),
    )
)
run_summary["win_rate"] = run_summary["win_count"] / run_summary["trade_count"].replace(0, pd.NA)
run_summary = run_summary.sort_values("run_started_at_jst", ascending=False)

fig = px.bar(
    run_summary.head(30).sort_values("run_started_at_jst"),
    x="run_id",
    y="total_pnl",
    title="直近30runの損益",
)
st.plotly_chart(fig, width="stretch")

summary_columns = [
    "run_id",
    "run_started_at_jst",
    "trade_count",
    "total_pnl",
    "win_rate",
    "take_profit_pips",
    "stop_loss_pips",
]
st.dataframe(run_summary[summary_columns], width="stretch", hide_index=True)

st.divider()
st.subheader("run詳細")

selected_run_id = st.selectbox(
    "確認するrun_id",
    options=run_ids,
    index=0,
)

selected_summary = history_df[history_df["run_id"].astype(str) == selected_run_id].copy()
selected_trade_count = int(selected_summary["trade_count"].fillna(0).sum())
selected_total_pnl = float(selected_summary["total_pnl"].fillna(0).sum())
selected_win_count = int(selected_summary["win_count"].fillna(0).sum())
selected_win_rate = selected_win_count / selected_trade_count if selected_trade_count else 0.0

s1, s2, s3 = st.columns(3)
s1.metric("損益", f"{selected_total_pnl:,.0f} 円")
s2.metric("取引回数", f"{selected_trade_count}")
s3.metric("勝率", f"{selected_win_rate:.1%}")

try:
    trades_df = get_run_dataset("trades", selected_run_id)
    report_df = get_run_dataset("ai_reports", selected_run_id)
    decisions_df = get_run_dataset("ai_decisions", selected_run_id)
except Exception as exc:
    st.error(f"run詳細の読み込みに失敗しました: {exc}")
    st.stop()

summary_tab, report_tab, trades_tab, decisions_tab = st.tabs(
    ["日次集計", "AIレビュー", "取引明細", "AI判断ログ"]
)

with summary_tab:
    st.dataframe(selected_summary, width="stretch", hide_index=True)

with report_tab:
    if report_df.empty:
        st.info("このrunにはAIレビューが保存されていません。")
    else:
        report = report_df.iloc[-1]
        r1, r2, r3 = st.columns(3)
        r1.metric("取引可否", str(report.get("trade_permission", "-")))
        r2.metric("示唆方向", str(report.get("suggested_side", "-")))

        confidence = report.get("confidence")
        confidence_label = "-" if pd.isna(confidence) else f"{float(confidence):.0%}"
        r3.metric("信頼度", confidence_label)

        st.markdown("### 相場要約")
        st.write(report.get("market_summary", "-"))

        st.markdown("### 主な理由")
        st.write(report.get("main_reasons_text", "-"))

        st.markdown("### 警告")
        st.write(report.get("warnings_text", "-"))

        st.markdown("### 次の行動")
        st.write(report.get("next_action", "-"))

        with st.expander("AIレビュー保存データ"):
            st.dataframe(report_df, width="stretch", hide_index=True)

with trades_tab:
    if trades_df.empty:
        st.info("このrunには取引明細がありません。")
    else:
        display_columns = [
            column
            for column in [
                "entry_time",
                "side",
                "entry_price",
                "exit_time",
                "exit_price",
                "pips",
                "pnl_jpy",
                "result",
                "exit_reason",
            ]
            if column in trades_df.columns
        ]
        st.dataframe(trades_df[display_columns], width="stretch", hide_index=True)

with decisions_tab:
    if decisions_df.empty:
        st.info("このrunにはAI判断ログがありません。")
    else:
        st.dataframe(decisions_df.tail(200), width="stretch", hide_index=True)
