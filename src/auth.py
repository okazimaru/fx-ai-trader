from __future__ import annotations

import hmac

import streamlit as st

from src.config import APP_PASSWORD


def require_login() -> None:
    """
    個人用アプリ向けの簡易ログイン。
    APP_PASSWORD が一致するまで、アプリ本体を表示しない。
    """
    if st.session_state.get("authenticated", False):
        with st.sidebar:
            st.success("ログイン中")
            if st.button("ログアウト"):
                st.session_state["authenticated"] = False
                st.rerun()
        return

    st.markdown("## ログイン")
    st.caption("FX AI Trader を使うにはパスワードを入力してください。")

    if not APP_PASSWORD:
        st.error("APP_PASSWORD が設定されていません。.env に APP_PASSWORD を追加してください。")
        st.stop()

    with st.form("login_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", type="primary")

    if submitted:
        if hmac.compare_digest(password, APP_PASSWORD):
            st.session_state["authenticated"] = True
            st.success("ログインしました。")
            st.rerun()
        else:
            st.error("パスワードが違います。")

    st.stop()
