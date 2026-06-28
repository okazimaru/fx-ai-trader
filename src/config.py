from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


AWS_REGION = get_setting("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = get_setting("S3_BUCKET_NAME", "")

OPENAI_API_KEY = get_setting("OPENAI_API_KEY", "")
OPENAI_MODEL = get_setting("OPENAI_MODEL", "gpt-5.5")

APP_PASSWORD = get_setting("APP_PASSWORD", "")

AWS_ACCESS_KEY_ID = get_setting("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = get_setting("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = get_setting("AWS_SESSION_TOKEN", "")

if AWS_ACCESS_KEY_ID:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID)

if AWS_SECRET_ACCESS_KEY:
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY)

if AWS_SESSION_TOKEN:
    os.environ.setdefault("AWS_SESSION_TOKEN", AWS_SESSION_TOKEN)

if AWS_REGION:
    os.environ.setdefault("AWS_DEFAULT_REGION", AWS_REGION)
