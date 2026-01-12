#!/usr/bin/env python3
# coding: utf-8

import os
from typing import Optional, List
from datetime import datetime

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

# שמות קבצים אך ורק עם "_"
TRADE_FILES: List[str] = [
    "crypto_trades.csv",
    "crypto_paper_trades.csv",
    "crypto_trades_2022_2025.csv",
    "us_trades.csv",
    "us_paper_trades.csv",
    "il_trades.csv",
    "il_paper_trades.csv",
]

DAILY_FILE = "daily_summary.csv"


def parse_epoch(value) -> Optional[pd.Timestamp]:
    """ממיר timestamp בשניות / מילישניות ל-Timestamp."""
    try:
        if pd.isna(value):
            return None
        if isinstance(value, str) and value.strip().isdigit():
            value = float(value.strip())
        if isinstance(value, (int, float)):
            if value < 1e11:
                return pd.to_datetime(value, unit="s")
            else:
                return pd.to_datetime(value, unit="ms")
    except Exception:
        return None
    return None


def parse_date_or_timestamp(val) -> Optional[pd.Timestamp]:
    """parser כללי: string, datetime, timestamp (s/ms)."""
    if isinstance(val, pd.Timestamp):
        return val
    if isinstance(val, datetime):
        return pd.Timestamp(val)
    if isinstance(val, (int, float)):
        return parse_epoch(val)
    if isinstance(val, str):
        s = val.strip()
        if s == "":
            return None
        try:
            ts = pd.to_datetime(s, errors="coerce")
            if pd.notna(ts):
                return ts
        except Exception:
            pass
        if s.isdigit():
            return parse_epoch(float(s))
    return None


def load_csv_safe(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        print(f"[INFO] file not found, skipping: {path}")
        return None
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"[WARN] failed to read {path}: {e}")
        return None


def save_with_backup(df: pd.DataFrame, path: str) -> None:
    """שומר df ויוצר גיבוי path.bak אם צריך."""
    if os.path.exists(path):
        bak = path + ".bak"
        try:
            os.replace(path, bak)
            print(f"[INFO] backup written: {bak}")
        except Exception as e:
            print(f"[WARN] failed to create backup for {path}: {e}")
    try:
        df.to_csv(path, index=False)
        print(f"[OK]   saved normalized file: {path}")
    except Exception as e:
        print(f"[ERROR] failed to save {path}: {e}")


def normalize_trades_file(filename: str) -> None:
    path = os.path.join(RESULTS_DIR, filename)
    print(f"\n--- normalizing trades file: {filename} ---")
    df = load_csv_safe(path)
    if df is None or df.empty:
        return

    print(f"[DEBUG] columns: {list(df.columns)}")

    has_ts = "timestamp" in df.columns
    has_dt = "datetime" in df.columns

    if not has_ts and not has_dt:
        print(f"[WARN] no timestamp/datetime column in {filename}, skipping.")
        return

    if has_dt:
        df["datetime_norm"] = df["datetime"].apply(parse_date_or_timestamp)
    else:
        df["datetime_norm"] = df["timestamp"].apply(parse_date_or_timestamp)

    df["datetime_norm"] = pd.to_datetime(df["datetime_norm"], errors="coerce")

    before_len = len(df)
    df = df[df["datetime_norm"].notna()].copy()
    after_len = len(df)
    if after_len < before_len:
        print(f"[INFO] dropped {before_len - after_len} rows with invalid datetime")

    df["date"] = df["datetime_norm"].dt.date

    df = df.sort_values("datetime_norm").reset_index(drop=True)

    print(f"[DEBUG] datetime range: {df['datetime_norm'].min()} -> {df['datetime_norm'].max()}")
    print(f"[DEBUG] date range    : {df['date'].min()} -> {df['date'].max()}")

    save_with_backup(df, path)


def normalize_daily_summary() -> None:
    path = os.path.join(RESULTS_DIR, DAILY_FILE)
    print(f"\n--- normalizing daily summary: {DAILY_FILE} ---")
    df = load_csv_safe(path)
    if df is None or df.empty:
        return

    print(f"[DEBUG] columns: {list(df.columns)}")

    if "date" not in df.columns:
        print(f"[WARN] no 'date' column in {DAILY_FILE}, skipping.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    before_len = len(df)
    df = df[df["date"].notna()].copy()
    after_len = len(df)
    if after_len < before_len:
        print(f"[INFO] dropped {before_len - after_len} rows with invalid date in daily summary")

    df = df.sort_values("date").reset_index(drop=True)

    print(f"[DEBUG] date range in daily summary: {df['date'].min()} -> {df['date'].max()}")

    save_with_backup(df, path)


def run_all() -> None:
    print(f"[INFO] base dir   : {BASE_DIR}")
    print(f"[INFO] results dir: {RESULTS_DIR}")

    if not os.path.isdir(RESULTS_DIR):
        print("[ERROR] results directory does not exist. fix RESULTS_DIR.")
        return

    print("\n[INFO] normalizing trades files:")
    for name in TRADE_FILES:
        print(f"   - {name}")

    for name in TRADE_FILES:
        normalize_trades_file(name)

    normalize_daily_summary()

    print("\n[INFO] finished trade + daily summary time normalization.")


def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
