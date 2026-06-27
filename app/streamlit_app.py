from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.data_loader import load_price_data
from src.indicators import add_indicators
from src.macro_events import load_macro_events
from src.backtest_engine import run_backtest, save_outputs


st.set_page_config(
    page_title="FX AI Trader MVP",
    page_icon="📈",
    layout="wide",
)

st.title("FX AI Trader MVP")
st.caption("疑似デイトレード × AI判断ログ × QuickSight連携用データ出力")

with st.sidebar:
    st.header("Backtest Settings")
    take_profit_pips = st.number_input("Take Profit pips", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
    stop_loss_pips = st.number_input("Stop Loss pips", min_value=1.0, max_value=50.0, value=7.0, step=1.0)
    unit_jpy_per_pip = st.number_input("1 pipあたり損益円", min_value=1.0, max_value=10000.0, value=100.0, step=50.0)
    run_button = st.button("疑似売買を実行", type="primary")

price_df = load_price_data()
price_df = add_indicators(price_df)
macro_events = load_macro_events()

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Trades", "AI Decisions", "Macro Events"])

if run_button:
    trades_df, ai_df, daily_summary = run_backtest(
        price_df,
        macro_events,
        take_profit_pips=take_profit_pips,
        stop_loss_pips=stop_loss_pips,
        unit_jpy_per_pip=unit_jpy_per_pip,
    )

    save_outputs(trades_df, ai_df, daily_summary)

    st.session_state["trades_df"] = trades_df
    st.session_state["ai_df"] = ai_df
    st.session_state["daily_summary"] = daily_summary

trades_df = st.session_state.get("trades_df", pd.DataFrame())
ai_df = st.session_state.get("ai_df", pd.DataFrame())
daily_summary = st.session_state.get("daily_summary", pd.DataFrame())

with tab1:
    st.subheader("運用サマリー")

    if trades_df.empty:
        st.info("左のボタンから疑似売買を実行してください。")
    else:
        total_pnl = trades_df["pnl_jpy"].sum()
        trade_count = len(trades_df)
        win_rate = (trades_df["result"].eq("win").sum() / trade_count) if trade_count else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("総損益", f"{total_pnl:,.0f} 円")
        c2.metric("取引回数", f"{trade_count}")
        c3.metric("勝率", f"{win_rate:.1%}")

        if not daily_summary.empty:
            fig = px.bar(daily_summary, x="trade_date", y="total_pnl", title="日次損益")
            st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(price_df.tail(300), x="timestamp", y="close", title="USD/JPY Close")
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("取引ログ")
    if trades_df.empty:
        st.info("取引ログはまだありません。")
    else:
        st.dataframe(trades_df, use_container_width=True)

with tab3:
    st.subheader("AI判断ログ")
    if ai_df.empty:
        st.info("AI判断ログはまだありません。")
    else:
        st.dataframe(ai_df.tail(200), use_container_width=True)

        fig = px.histogram(ai_df, x="confidence", title="AI Confidence分布")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("経済イベント")
    st.dataframe(macro_events, use_container_width=True)
