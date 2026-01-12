#!/usr/bin/env python3
# coding: utf-8

"""
sync_time_formats_strict.py

סקריפט לסנכרון פורמט הזמן בכל קבצי ה-CSV בפרויקט,
בהנחה שכל שמות הקבצים הם snake_case בלבד.

אתה שולט ברשימת הקבצים כאן, אין ניחושים.
"""

import os
from typing import Optional, List
from datetime import datetime

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# CONFIG – עדכן פה פעם אחת את שמות הקבצים בפועל (snake_case בלבד)
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# אם התיקייה שלך נקראת "resultsmulti" ולא "results_multi" – עדכן כאן.
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

CSV_FILES: List[str] = [
    # equity יומיים / עקומות
    "crypto_paper_equity.csv",
    "us_paper_equity.csv",
    "multi_adaptive_paper_equity.csv",
    "crypto_equity_curve.csv",
    "us_equity_curve.csv",

    # trades / paper trades / sandbox
    "crypto_trades.csv",
    "crypto_paper_trades.csv",
    "crypto_trades_2022_2025.csv",
    "us_paper_trades.csv",
    "il_paper_trades.csv",
    "us_trades.csv",
    "il_trades.csv",

    # summaries / daily
    "multi_asset_summary.csv",
    "multi_adaptive_paper_summary.csv",
    "daily_summary.csv",
]

# ---------------------------------------------------------------------
# עזרי זמן
# ---------------------------------------------------------------------

def parse_epoch(value) -> Optional[pd.Timestamp]:
    """ממיר timestamp בשניות / מילישניות ל-Timestamp."""
    try:
        if pd.isna(value):
            return None
        if isinstance(value, str) and value.strip().isdigit():
            value = float(value.strip())
        if isinstance(value, (int, float)):
            # פחות מ-1e11 -> שניות, אחרת מילישניות
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
        # ניסיון כללי
        try:
            ts = pd.to_datetime(s, errors="coerce")
            if pd.notna(ts):
                return ts
        except Exception:
            pass
        # אם רק ספרות – ננסה כ-timestamp
        if s.isdigit():
            return parse_epoch(float(s))
    return None


def build_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    דואג שתהיה עמודת date אחידה.

    סדר העדיפויות:
    1. אם יש 'date' / 'Date' – ממירים ומנקים.
    2. אחרת אם יש 'datetime' – נגזור.
    3. אחרת אם יש 'timestamp' – נגזור.
    אם אין שום דבר – מחזירים כמו שהוא.
    """
    df = df.copy()

    # 1. date/Date
    if "date" in df.columns or "Date" in df.columns:
        src = "date" if "date" in df.columns else "Date"
        if src != "date":
            df.rename(columns={src: "date"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        mask_bad = df["date"].isna()
        if mask_bad.any():
            parsed = df.loc[mask_bad, "date"].apply(parse_date_or_timestamp)
            df.loc[mask_bad, "date"] = parsed
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    # 2. datetime
    if "datetime" in df.columns:
        df["date"] = df["datetime"].apply(parse_date_or_timestamp)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    # 3. timestamp
    if "timestamp" in df.columns:
        df["date"] = df["timestamp"].apply(parse_date_or_timestamp)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    return df


# ---------------------------------------------------------------------
# IO על קבצים
# ---------------------------------------------------------------------

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


def normalize_one_file(filename: str) -> None:
    path = os.path.join(RESULTS_DIR, filename)
    print(f"\n--- {filename} ---")
    df = load_csv_safe(path)
    if df is None or df.empty:
        return

    print(f"[DEBUG] columns: {list(df.columns)}")
    df = build_date_column(df)

    if "date" not in df.columns:
        print(f"[WARN] no date/datetime/timestamp column detected in {filename}, skipping.")
        return

    before_len = len(df)
    df = df[df["date"].notna()].copy()
    after_len = len(df)
    if after_len < before_len:
        print(f"[INFO] dropped {before_len - after_len} rows with invalid date")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    print(f"[DEBUG] date range: {df['date'].min()} -> {df['date'].max()}")
    save_with_backup(df, path)


def run_all() -> None:
    print(f"[INFO] base dir   : {BASE_DIR}")
    print(f"[INFO] results dir: {RESULTS_DIR}")

    if not os.path.isdir(RESULTS_DIR):
        print("[ERROR] results directory does not exist. fix RESULTS_DIR.")
        return

    print("\n[INFO] will try to normalize these files (snake_case):")
    for name in CSV_FILES:
        print(f"   - {name}")

    for name in CSV_FILES:
        normalize_one_file(name)

    print("\n[INFO] finished strict time normalization.")
    

def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
