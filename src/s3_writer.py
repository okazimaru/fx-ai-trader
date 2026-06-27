from __future__ import annotations

from pathlib import Path

import boto3
import pandas as pd

from src.config import AWS_REGION, S3_BUCKET_NAME


def get_latest_run_id(local_path: str = "data/output/daily_summary.parquet") -> str:
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"run_id確認用ファイルが見つかりません: {local_path}")

    df = pd.read_parquet(path)

    if "run_id" not in df.columns:
        raise ValueError("出力ファイルに run_id がありません。疑似売買を再実行してください。")

    run_ids = df["run_id"].dropna().unique()
    if len(run_ids) == 0:
        raise ValueError("run_id が空です。")

    return str(run_ids[0])


def upload_file_to_s3(local_path: str, s3_key: str) -> str:
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME が .env に設定されていません。")

    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {local_path}")

    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.upload_file(str(path), S3_BUCKET_NAME, s3_key)

    return f"s3://{S3_BUCKET_NAME}/{s3_key}"


def upload_outputs_to_s3() -> list[str]:
    run_id = get_latest_run_id()

    uploads = [
        ("data/output/trades.parquet", f"curated/trades/trades_{run_id}.parquet"),
        ("data/output/ai_decisions.parquet", f"curated/ai_decisions/ai_decisions_{run_id}.parquet"),
        ("data/output/daily_summary.parquet", f"curated/daily_summary/daily_summary_{run_id}.parquet"),
        ("data/sample/macro_events.csv", "curated/macro_events/macro_events.csv"),
    ]

    ai_report_path = Path("data/output/ai_report.parquet")
    if ai_report_path.exists():
        uploads.append(
            ("data/output/ai_report.parquet", f"curated/ai_reports/ai_report_{run_id}.parquet")
        )

    uploaded_paths = []
    for local_path, s3_key in uploads:
        uploaded_paths.append(upload_file_to_s3(local_path, s3_key))

    return uploaded_paths
