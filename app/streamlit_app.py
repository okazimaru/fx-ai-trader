from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.data_loader import (
    get_price_data_quality,
    load_price_data,
    load_uploaded_price_data,
)
from src.indicators import add_indicators
from src.macro_events import load_macro_events
from src.backtest_engine import run_backtest, save_outputs
from src.s3_writer import upload_outputs_to_s3
from src.llm_copilot import generate_ai_report


st.set_page_config(
    page_title="FX AI Trader MVP",
    page_icon="📈",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    div.stButton > button {
        width: 100%;
        min-height: 3rem;
        font-weight: 700;
        border-radius: 0.8rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.7rem;
    }

    .mobile-card {
        border: 1px solid rgba(49, 51, 63, 0.15);
        border-radius: 1rem;
        padding: 1rem;
        margin-bottom: 1rem;
        background: rgba(250, 250, 250, 0.8);
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 800;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    .subtle-text {
        color: #6b7280;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def status_icon(status: str) -> str:
    if status == "fresh":
        return "🟢"
    if status == "slightly_old":
        return "🟡"
    if status == "stale":
        return "🔴"
    return "⚪"


def permission_label(value: str) -> str:
    labels = {
        "entry_allowed": "エントリー許可",
        "wait": "見送り",
        "risk_stop": "リスク停止",
    }
    return labels.get(value, value)


def side_label(value: str) -> str:
    labels = {
        "long": "ロング",
        "short": "ショート",
        "none": "方向なし",
    }
    return labels.get(value, value)


st.title("FX AI Trader MVP")
st.caption("疑似デイトレード × AI判断ログ × QuickSight連携用データ出力")


with st.sidebar:
    st.header("詳細設定")

    take_profit_pips = st.number_input(
        "Take Profit pips",
        min_value=1.0,
        max_value=50.0,
        value=10.0,
        step=1.0,
    )

    stop_loss_pips = st.number_input(
        "Stop Loss pips",
        min_value=1.0,
        max_value=50.0,
        value=7.0,
        step=1.0,
    )

    unit_jpy_per_pip = st.number_input(
        "1 pipあたり損益円",
        min_value=1.0,
        max_value=10000.0,
        value=100.0,
        step=50.0,
    )

    st.divider()
    st.caption("スマホではメイン画面上部の操作パネルを使う想定です。")


st.markdown("## 今日の操作")

with st.container(border=True):
    data_source = st.radio(
        "価格データ",
        ["サンプルデータ", "CSVアップロード"],
        index=0,
        horizontal=True,
    )

    uploaded_file = None
    if data_source == "CSVアップロード":
        uploaded_file = st.file_uploader(
            "価格CSVをアップロード",
            type=["csv"],
            help="必要列: timestamp, open, high, low, close。任意列: symbol, timeframe, spread",
        )

    with st.expander("バックテスト設定を確認する", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("TP", f"{take_profit_pips:.1f} pips")
        c2.metric("SL", f"{stop_loss_pips:.1f} pips")
        c3.metric("損益単価", f"{unit_jpy_per_pip:.0f} 円/pip")
        st.caption("設定変更は左サイドバーから行います。スマホでは左上メニューから開けます。")


try:
    if data_source == "CSVアップロード":
        if uploaded_file is None:
            price_df = pd.DataFrame()
        else:
            price_df = load_uploaded_price_data(uploaded_file)
    else:
        price_df = load_price_data()

    if not price_df.empty:
        price_df = add_indicators(price_df)

except Exception as e:
    st.error(f"価格データの読み込みに失敗しました: {e}")
    price_df = pd.DataFrame()


macro_events = load_macro_events()

quality = get_price_data_quality(price_df)

with st.container(border=True):
    st.markdown("### データ状態")

    qc1, qc2, qc3 = st.columns(3)
    qc1.metric("鮮度", f"{status_icon(quality['freshness_status'])} {quality['freshness_status']}")
    qc2.metric("行数", quality["row_count"])
    qc3.metric("最新経過分", "-" if quality["latest_age_minutes"] is None else quality["latest_age_minutes"])

    st.caption(quality["message"])


run_col, review_col, upload_col = st.columns(3)

run_button = run_col.button("① 疑似売買を実行", type="primary")
review_button = review_col.button("② AIレビュー生成")
upload_button = upload_col.button("③ S3へアップロード")


if run_button:
    if price_df.empty:
        st.error("価格データがないため、疑似売買を実行できません。")
    else:
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
        st.session_state.pop("ai_report", None)

        st.success("疑似売買を実行し、ローカルに出力しました。")


trades_df = st.session_state.get("trades_df", pd.DataFrame())
ai_df = st.session_state.get("ai_df", pd.DataFrame())
daily_summary = st.session_state.get("daily_summary", pd.DataFrame())


if review_button:
    if trades_df.empty or ai_df.empty or daily_summary.empty:
        st.error("まず「① 疑似売買を実行」を押してください。")
    elif price_df.empty:
        st.error("価格データがないため、AIレビューを生成できません。")
    else:
        try:
            report = generate_ai_report(
                price_df=price_df,
                trades_df=trades_df,
                ai_df=ai_df,
                daily_summary=daily_summary,
                macro_events=macro_events,
            )

            st.session_state["ai_report"] = report
            st.success("AI相場レビューを生成しました。")

        except Exception as e:
            st.error(f"AI相場レビュー生成に失敗しました: {e}")


if upload_button:
    try:
        uploaded_paths = upload_outputs_to_s3()
        st.success("S3アップロードが完了しました。")
        with st.expander("アップロード先"):
            for path in uploaded_paths:
                st.write(path)
    except Exception as e:
        st.error(f"S3アップロードに失敗しました: {e}")


report = st.session_state.get("ai_report")


if report:
    st.markdown("## 最新AIレビュー")

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("取引可否", permission_label(report["trade_permission"]))
    rc2.metric("示唆方向", side_label(report["suggested_side"]))
    rc3.metric("信頼度", f'{report["confidence"]:.0%}')

    with st.container(border=True):
        st.markdown("### 相場要約")
        st.write(report["market_summary"])

    with st.container(border=True):
        st.markdown("### 次の行動")
        st.write(report["next_action"])


tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Summary", "AI Review", "Trades", "AI Logs", "Events", "Data"]
)


with tab1:
    st.subheader("運用サマリー")

    if trades_df.empty:
        st.info("上の「① 疑似売買を実行」から開始してください。")
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

        if not price_df.empty:
            fig2 = px.line(price_df.tail(300), x="timestamp", y="close", title="USD/JPY Close")
            st.plotly_chart(fig2, use_container_width=True)


with tab2:
    st.subheader("AIレビュー詳細")

    if not report:
        st.info("上の「② AIレビュー生成」を押すと、ここに詳細が表示されます。")
    else:
        st.markdown("### 主な理由")
        for reason in report["main_reasons"]:
            st.write(f"- {reason}")

        st.markdown("### 警告")
        for warning in report["warnings"]:
            st.write(f"- {warning}")

        with st.expander("JSON出力"):
            st.code(json.dumps(report, ensure_ascii=False, indent=2), language="json")


with tab3:
    st.subheader("取引ログ")

    if trades_df.empty:
        st.info("取引ログはまだありません。")
    else:
        display_cols = [
            c for c in [
                "run_id",
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
            if c in trades_df.columns
        ]
        st.dataframe(trades_df[display_cols], use_container_width=True)


with tab4:
    st.subheader("AI判断ログ")

    if ai_df.empty:
        st.info("AI判断ログはまだありません。")
    else:
        st.dataframe(ai_df.tail(100), use_container_width=True)

        if "confidence" in ai_df.columns:
            fig = px.histogram(ai_df, x="confidence", title="AI Confidence分布")
            st.plotly_chart(fig, use_container_width=True)


with tab5:
    st.subheader("経済イベント")
    st.dataframe(macro_events, use_container_width=True)


with tab6:
    st.subheader("データ品質")

    if price_df.empty:
        st.info("価格データがありません。")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("行数", quality["row_count"])
        c2.metric("開始時刻", quality["start_time"])
        c3.metric("終了時刻", quality["end_time"])
        c4.metric("最新データ経過分", quality["latest_age_minutes"])

        st.write(f"鮮度ステータス: **{quality['freshness_status']}**")
        st.info(quality["message"])

        st.markdown("### 価格データプレビュー")
        st.dataframe(price_df.tail(20), use_container_width=True)
