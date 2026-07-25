from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.auth import require_login
from src.backtest_engine import run_backtest, save_outputs
from src.data_loader import get_price_data_quality, load_price_data, load_uploaded_price_data
from src.indicators import add_indicators
from src.llm_copilot import generate_ai_report
from src.macro_events import load_macro_events
from src.s3_writer import upload_outputs_to_s3
from src.trading_config import load_trading_config

st.set_page_config(
    page_title="FX AI Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 1.2rem; padding-bottom: 3rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    div.stButton > button {width: 100%; min-height: 3rem; font-weight: 700; border-radius: .75rem;}
    [data-testid="stMetric"] {border: 1px solid rgba(49,51,63,.12); border-radius: .9rem; padding: .8rem 1rem; background: rgba(250,250,250,.5);}
    [data-testid="stMetricValue"] {font-size: 1.45rem;}
    .hero {border: 1px solid rgba(49,51,63,.12); border-radius: 1rem; padding: 1rem 1.15rem; margin: .25rem 0 1.2rem; background: linear-gradient(135deg, rgba(35,99,235,.08), rgba(16,185,129,.05));}
    .hero-title {font-size: 1.05rem; font-weight: 800; margin-bottom: .25rem;}
    .muted {color: #6b7280; font-size: .9rem;}
    .step {font-size: .78rem; color: #6b7280; font-weight: 700; letter-spacing: .04em; margin-bottom: .25rem;}
    .chips {display: flex; flex-wrap: wrap; gap: .5rem; margin: .4rem 0 .8rem;}
    .chip {display: inline-flex; border-radius: 999px; padding: .35rem .7rem; font-size: .84rem; font-weight: 700; border: 1px solid rgba(49,51,63,.12); background: rgba(250,250,250,.72);}
    .ok {color: #047857;} .warn {color: #b45309;} .stop {color: #b91c1c;} .neutral {color: #4b5563;}
    @media (max-width: 700px) {[data-testid="stMetricValue"] {font-size: 1.2rem;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def freshness_display(status: str) -> tuple[str, str]:
    return {
        "fresh": ("正常", "ok"),
        "slightly_old": ("やや古い", "warn"),
        "stale": ("古い", "stop"),
        "empty": ("データなし", "neutral"),
    }.get(status, (status or "不明", "neutral"))


def permission_label(value: str) -> str:
    return {
        "entry_allowed": "エントリー許可",
        "wait": "見送り",
        "risk_stop": "リスク停止",
    }.get(value, value)


def side_label(value: str) -> str:
    return {"long": "ロング", "short": "ショート", "none": "方向なし"}.get(value, value)


def result_label(value: str) -> str:
    return {"win": "勝ち", "lose": "負け", "breakeven": "引き分け"}.get(value, value)


def first_value(df: pd.DataFrame, column: str, default: str = "-") -> str:
    if df.empty or column not in df.columns:
        return default
    values = df[column].dropna()
    return default if values.empty else str(values.iloc[0])


require_login()
config = load_trading_config()
execution = config.execution
risk = config.risk

st.title("FX AI Trader")
st.caption("確認 → 実行 → AIレビュー → 保存の順で、迷わずシミュレーションを進められます。")
st.markdown(
    """
    <div class="hero">
      <div class="hero-title">現在はシミュレーション環境です</div>
      <div class="muted">実口座への注文は行いません。Saxo接続後も、読み取り専用とSIM環境から段階的に移行します。</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("シミュレーション設定")
    st.caption(f"設定バージョン {config.version}")
    take_profit_pips = st.number_input(
        "利確幅（pips）", 1.0, 50.0, float(execution.take_profit_pips), 1.0,
        help="この値へ到達したら利益確定します。",
    )
    stop_loss_pips = st.number_input(
        "損切り幅（pips）", 1.0, 50.0, float(execution.stop_loss_pips), 1.0,
        help="この値まで逆行したら損切りします。",
    )
    unit_jpy_per_pip = st.number_input(
        "1 pipあたりの損益（円）", 1.0, 10000.0, float(execution.unit_jpy_per_pip), 10.0,
        help="100円/pipはUSD/JPYの約10,000通貨相当です。",
    )
    st.divider()
    st.subheader("固定リスクルール")
    st.write(f"日次損失上限：**{risk.max_daily_loss_jpy:,.0f}円**")
    st.write(f"最大連敗：**{risk.max_consecutive_losses}回**")
    st.write(f"1日最大取引：**{risk.max_trades_per_day}回**")
    st.write(f"最大スプレッド：**{risk.max_spread}**")
    st.info("固定ルールは画面では変更せず、設定ファイルで履歴管理します。")

st.markdown("## 1. データを確認")
with st.container(border=True):
    source_col, status_col = st.columns([1.1, 1.9])
    with source_col:
        data_source = st.radio(
            "価格データ", ["サンプルデータ", "CSVアップロード"],
            horizontal=True, label_visibility="collapsed",
        )
        uploaded_file = None
        if data_source == "CSVアップロード":
            uploaded_file = st.file_uploader(
                "価格CSV", type=["csv"],
                help="必須列: timestamp, open, high, low, close",
            )

    try:
        if data_source == "CSVアップロード":
            price_df = pd.DataFrame() if uploaded_file is None else load_uploaded_price_data(uploaded_file)
        else:
            price_df = load_price_data()
        if not price_df.empty:
            price_df = add_indicators(price_df)
    except Exception as exc:
        st.error(f"価格データの読み込みに失敗しました: {exc}")
        price_df = pd.DataFrame()

    macro_events = load_macro_events()
    quality = get_price_data_quality(price_df)
    freshness_text, freshness_class = freshness_display(str(quality.get("freshness_status", "empty")))
    latest_age = quality.get("latest_age_minutes")
    latest_age_text = "-" if latest_age is None else f"{latest_age}分"

    with status_col:
        st.markdown(
            f"""
            <div class="chips">
              <span class="chip {freshness_class}">● データ {freshness_text}</span>
              <span class="chip neutral">行数 {quality.get('row_count', 0):,}</span>
              <span class="chip neutral">最新経過 {latest_age_text}</span>
              <span class="chip neutral">{config.market.symbol} / {config.market.timeframe}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(str(quality.get("message", "")))

trades_df = st.session_state.get("trades_df", pd.DataFrame())
ai_df = st.session_state.get("ai_df", pd.DataFrame())
daily_summary = st.session_state.get("daily_summary", pd.DataFrame())
report = st.session_state.get("ai_report")

has_run = not daily_summary.empty
can_review = has_run and not trades_df.empty and not ai_df.empty
current_run_id = first_value(daily_summary, "run_id", "未実行")
uploaded_run_id = st.session_state.get("uploaded_run_id")

st.markdown("## 2. 実行する")
with st.container(border=True):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("現在のrun", current_run_id)
    m2.metric("データ", freshness_text)
    m3.metric("AIレビュー", "完了" if report else "未実施")
    m4.metric("S3保存", "完了" if has_run and uploaded_run_id == current_run_id else "未保存")
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="step">STEP 1</div>', unsafe_allow_html=True)
        run_button = st.button("シミュレーションを実行", type="primary", disabled=price_df.empty)
        st.caption("売買シグナルと固定リスク条件で検証します。")
    with c2:
        st.markdown('<div class="step">STEP 2</div>', unsafe_allow_html=True)
        review_button = st.button("AIレビューを生成", disabled=not can_review)
        st.caption("結果をAIが要約し、確認点を提示します。")
    with c3:
        st.markdown('<div class="step">STEP 3</div>', unsafe_allow_html=True)
        upload_button = st.button("結果をS3へ保存", disabled=not has_run)
        st.caption("履歴画面から確認できるように保存します。")

if run_button:
    try:
        trades_df, ai_df, daily_summary = run_backtest(
            price_df, macro_events,
            take_profit_pips=take_profit_pips,
            stop_loss_pips=stop_loss_pips,
            unit_jpy_per_pip=unit_jpy_per_pip,
            config=config,
        )
        save_outputs(trades_df, ai_df, daily_summary)
        st.session_state["trades_df"] = trades_df
        st.session_state["ai_df"] = ai_df
        st.session_state["daily_summary"] = daily_summary
        st.session_state.pop("ai_report", None)
        st.session_state.pop("uploaded_run_id", None)
        if daily_summary.empty:
            st.warning("実行は完了しましたが、今回の条件では決済済み取引がありませんでした。")
        else:
            st.success(f"シミュレーション完了：{first_value(daily_summary, 'run_id')}")
    except Exception as exc:
        st.error(f"シミュレーションに失敗しました: {exc}")

if review_button:
    try:
        report = generate_ai_report(
            price_df=price_df,
            trades_df=trades_df,
            ai_df=ai_df,
            daily_summary=daily_summary,
            macro_events=macro_events,
        )
        st.session_state["ai_report"] = report
        st.success("AIレビューを生成しました。")
    except Exception as exc:
        st.error(f"AIレビュー生成に失敗しました: {exc}")

if upload_button:
    try:
        uploaded_paths = upload_outputs_to_s3()
        current_run_id = first_value(daily_summary, "run_id", "")
        st.session_state["uploaded_run_id"] = current_run_id
        st.success(f"run {current_run_id} をS3へ保存しました。")
        with st.expander("保存先を確認"):
            for path in uploaded_paths:
                st.code(path)
    except Exception as exc:
        st.error(f"S3への保存に失敗しました: {exc}")

trades_df = st.session_state.get("trades_df", trades_df)
ai_df = st.session_state.get("ai_df", ai_df)
daily_summary = st.session_state.get("daily_summary", daily_summary)
report = st.session_state.get("ai_report", report)

st.markdown("## 3. 結果を見る")
if daily_summary.empty:
    st.info("「シミュレーションを実行」を押すと、損益・取引・AI判断がここに表示されます。")
else:
    total_pnl = float(trades_df["pnl_jpy"].sum()) if "pnl_jpy" in trades_df else 0.0
    trade_count = len(trades_df)
    win_rate = (
        float(trades_df["result"].eq("win").sum() / trade_count)
        if trade_count and "result" in trades_df else 0.0
    )
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("総損益", f"{total_pnl:,.0f}円")
    r2.metric("取引回数", f"{trade_count}回")
    r3.metric("勝率", f"{win_rate:.1%}")
    r4.metric("run ID", first_value(daily_summary, "run_id"))

    if report:
        st.markdown("### AIレビュー")
        ai_status, ai_body = st.columns([1, 2.2])
        with ai_status:
            st.metric("取引可否", permission_label(report["trade_permission"]))
            st.metric("示唆方向", side_label(report["suggested_side"]))
            st.metric("信頼度", f'{report["confidence"]:.0%}')
        with ai_body:
            with st.container(border=True):
                st.markdown("**相場要約**")
                st.write(report["market_summary"])
                st.markdown("**次の行動**")
                st.write(report["next_action"])

    overview_tab, trades_tab, details_tab = st.tabs(["概要", "取引履歴", "詳細・診断"])

    with overview_tab:
        chart1, chart2 = st.columns(2)
        with chart1:
            if not price_df.empty:
                fig = px.line(price_df.tail(300), x="timestamp", y="close", title=f"{config.market.symbol} 価格")
                fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, width="stretch")
        with chart2:
            pnl_df = daily_summary.copy()
            if "trade_date" in pnl_df.columns:
                pnl_df["trade_date"] = pd.to_datetime(pnl_df["trade_date"]).dt.strftime("%Y-%m-%d")
            fig = px.bar(pnl_df, x="trade_date", y="total_pnl", title="日次損益")
            fig.update_layout(
                margin=dict(l=10, r=10, t=50, b=10),
                xaxis_title=None, yaxis_title=None, xaxis_type="category",
            )
            st.plotly_chart(fig, width="stretch")

        if report:
            reasons_col, warnings_col = st.columns(2)
            with reasons_col:
                with st.container(border=True):
                    st.markdown("**AIの主な理由**")
                    for reason in report.get("main_reasons", []) or ["理由はありません。"]:
                        st.write(f"• {reason}")
            with warnings_col:
                with st.container(border=True):
                    st.markdown("**警告・注意点**")
                    for warning in report.get("warnings", []) or ["警告はありません。"]:
                        st.write(f"• {warning}")

    with trades_tab:
        columns = [
            col for col in [
                "entry_time", "side", "entry_price", "exit_time", "exit_price",
                "pips", "pnl_jpy", "result", "exit_reason",
            ] if col in trades_df.columns
        ]
        if not columns:
            st.info("取引履歴はありません。")
        else:
            display_df = trades_df[columns].copy()
            if "side" in display_df:
                display_df["side"] = display_df["side"].map(side_label)
            if "result" in display_df:
                display_df["result"] = display_df["result"].map(result_label)
            st.dataframe(display_df, width="stretch", hide_index=True)

    with details_tab:
        with st.expander("固定リスク設定", expanded=True):
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("日次損失上限", f"{risk.max_daily_loss_jpy:,.0f}円")
            d2.metric("最大連敗", f"{risk.max_consecutive_losses}回")
            d3.metric("1日最大取引", f"{risk.max_trades_per_day}回")
            d4.metric("最大スプレッド", f"{risk.max_spread}")
        with st.expander("AI判断ログ"):
            st.dataframe(ai_df.tail(100), width="stretch", hide_index=True)
        with st.expander("経済イベント"):
            st.dataframe(macro_events, width="stretch", hide_index=True)
        with st.expander("価格データと品質"):
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("行数", quality.get("row_count", 0))
            q2.metric("開始", quality.get("start_time", "-"))
            q3.metric("終了", quality.get("end_time", "-"))
            q4.metric("最新経過", latest_age_text)
            st.caption(str(quality.get("message", "")))
            st.dataframe(price_df.tail(20), width="stretch", hide_index=True)
        if report:
            with st.expander("AIレビューJSON"):
                st.code(json.dumps(report, ensure_ascii=False, indent=2), language="json")
