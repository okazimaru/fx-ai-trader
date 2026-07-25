from __future__ import annotations

from io import BytesIO
from typing import Final

import boto3
import pandas as pd

from src.config import AWS_REGION, S3_BUCKET_NAME


DATASET_CONFIG: Final[dict[str, tuple[str, str]]] = {
    "daily_summary": ("curated/daily_summary/", "daily_summary_{run_id}.parquet"),
    "trades": ("curated/trades/", "trades_{run_id}.parquet"),
    "ai_decisions": ("curated/ai_decisions/", "ai_decisions_{run_id}.parquet"),
    "ai_reports": ("curated/ai_reports/", "ai_report_{run_id}.parquet"),
}


def _get_s3_client():
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME が設定されていません。")
    return boto3.client("s3", region_name=AWS_REGION)


def list_s3_objects(prefix: str) -> list[dict]:
    """指定prefix配下のS3オブジェクトを全件取得する。"""
    s3 = _get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")

    objects: list[dict] = []
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
        objects.extend(page.get("Contents", []))

    return sorted(
        objects,
        key=lambda item: item.get("LastModified"),
        reverse=True,
    )


def read_parquet_from_s3(key: str) -> pd.DataFrame:
    """S3上のParquetをDataFrameとして読み込む。"""
    s3 = _get_s3_client()
    response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
    return pd.read_parquet(BytesIO(response["Body"].read()))


def build_dataset_key(dataset: str, run_id: str) -> str:
    if dataset not in DATASET_CONFIG:
        raise ValueError(f"未対応のデータセットです: {dataset}")

    prefix, filename_template = DATASET_CONFIG[dataset]
    return f"{prefix}{filename_template.format(run_id=run_id)}"


def load_run_dataset(dataset: str, run_id: str) -> pd.DataFrame:
    """run_idを指定して1つのデータセットを読み込む。存在しない場合は空DataFrame。"""
    key = build_dataset_key(dataset, run_id)

    try:
        return read_parquet_from_s3(key)
    except _get_s3_client().exceptions.NoSuchKey:
        return pd.DataFrame()
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404"}:
            return pd.DataFrame()
        raise


def load_daily_summary_history(max_runs: int = 100) -> pd.DataFrame:
    """最新のrunから順にdaily_summaryを結合して返す。"""
    prefix = DATASET_CONFIG["daily_summary"][0]
    objects = [
        item
        for item in list_s3_objects(prefix)
        if str(item.get("Key", "")).endswith(".parquet")
    ][:max_runs]

    frames: list[pd.DataFrame] = []
    for item in objects:
        frame = read_parquet_from_s3(str(item["Key"]))
        if frame.empty:
            continue

        frame = frame.copy()
        frame["s3_last_modified"] = item.get("LastModified")
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    history = pd.concat(frames, ignore_index=True)

    if "run_started_at_jst" in history.columns:
        history["run_started_at_jst"] = pd.to_datetime(
            history["run_started_at_jst"],
            errors="coerce",
        )

    if "trade_date" in history.columns:
        history["trade_date"] = pd.to_datetime(
            history["trade_date"],
            errors="coerce",
        ).dt.date

    sort_columns = [
        column
        for column in ["run_started_at_jst", "trade_date"]
        if column in history.columns
    ]
    if sort_columns:
        history = history.sort_values(sort_columns, ascending=False)

    return history.reset_index(drop=True)
