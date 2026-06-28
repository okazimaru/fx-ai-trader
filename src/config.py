from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

APP_PASSWORD = os.getenv("APP_PASSWORD", "")
