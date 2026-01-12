#!/usr/bin/env python3
# coding: utf-8

"""
sync_time_formats.py

סקריפט עזר לסנכרון פורמט הזמן בכל קבצי הנתונים בתיקיית resultsmulti.
הוא:
- קורא כל CSV רלוונטי (equity, benchmark, trades, summaries).
- מאחד את פורמט הזמן לעמודת date מסוג datetime64[ns].
- מתמודד עם:
  * string בפורמט YYYY-MM-DD
  * string ISO כמו 2024-04-10T00:00:00
  * timestamp בשניות (10 ספרות) או מילישניות (13 ספרות).
- שומר את הקבצים המעודכנים, ויוצר קובץ גיבוי .bak לכל אחד.
"""

import os
from typing import Optional, List
from datetime import datetime

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# קונפיגורציה בסיסית
# ---------------------------------------------------------------------

BASEDIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASEDIR, "resultsmulti")

# רשימת קבצים צפוייה; אפשר להרחיב אם תוסיף עוד
EQUITY_FILES = [
    "cryptopaperequity.csv",
    "uspaperequity.csv",
    "multiadaptivepaperequity.csv",
    "cryptoequitycurve.csv",
    "usequitycurve.csv",
]

TRADES_FILES = [
    "cryptopapertrades.csv",
    "cryptotrades.csv",
    "cryptotrades2022-2025.csv",
    "uspapertrades.csv",
    "ilpapertrades.csv",
    "ustrades.csv",
    "iltrades.csv",
]

SUMMARY_FILES = [
    "multiassetsummary.csv",
    "multiadaptivepapersummary.csv",
    "dailysummary.csv",
]

ALL_FILES = EQUITY_FILES + TRADES_FILES + SUMMARY_FILES


# ---------------------------------------------------------------------
# פונקציות עזר – parsing של תאריכים / timestamps
# ---------------------------------------------------------------------

def parse_epoch(value: float) -> Optional[pd.Timestamp]:
    """
    מנסה להבין אם value הוא timestamp בשניות או במילישניות.
    מחזיר pd.Timestamp או None אם לא הצליח.
    """
    try:
        if pd.isna(value):
            return None
        # אם זה string של ספרות בלבד – נעשה cast ל-float
        if isinstance(value, str) and value.isdigit():
            value = float(value)

        if isinstance(value, (int, float)):
            # 10 ספרות בערך -> שניות; 13 -> מילישניות.
            # נבדוק לפי גודל.
            # פחות מ-1e11 – נתייחס כשניות (עד 5138).
            if value < 1e11:
                return pd.to_datetime(value, unit="s")
            else:
                return pd.to_datetime(value, unit="ms")
    except Exception:
        return None
    return None


def parse_date_or_timestamp(val) -> Optional[pd.Timestamp]:
    """
    parser כללי שמנסה:
    1. אם זה כבר Timestamp / datetime -> מחזיר כמות שהוא.
    2. אם זה מספר -> מנסה parse_epoch (שניות / מילישניות).
    3. אם זה string:
       - קודם ננסה ISO / פורמטים חופשיים via to_datetime(errors='coerce').
       - אם זה נפל, ננסה שוב כ-timestamp ספרתי.
    מחזיר Timestamp או None.
    """
    # כבר pd.Timestamp
    if isinstance(val, pd.Timestamp):
        return val

    # datetime מ-Python
    if isinstance(val, datetime):
        return pd.Timestamp(val)

    # מספרי (int/float)
    if isinstance(val, (int, float)):
        ts = parse_epoch(val)
        return ts

    # string
    if isinstance(val, str):
        s = val.strip()
        if s == "":
            return None

        # אם מכיל אות T או - ננסה ישר to_datetime על string
        try:
            ts = pd.to_datetime(s, errors="coerce")
            if pd.notna(ts):
                return ts
        except Exception:
            pass

        # אם זה רק ספרות – ננסה כ-timestamp
        if s.isdigit():
            try:
                num = float(s)
                ts = parse_epoch(num)
                return ts
            except Exception:
                return None

    return None


def build_date_column(df: pd.DataFrame,
                      date_col: str = "date",
                      datetime_col: str = "datetime",
                      timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    דואג שתהיה עמודת date מסוג datetime64[ns] ב-DataFrame.

    לוגיקה:
    - אם יש כבר עמודת date -> ננסה להמיר אותה ל-datetime.
    - אחרת אם יש datetime -> נבנה date ממנה.
    - אחרת אם יש timestamp -> נבנה date ממנה.
    """
    df = df.copy()

    # אם כבר יש date – ננקה ונמיר
    if date_col in df.columns:
        # ננסה כמה גישות
        try:
            # קודם – אם זו כבר datetime string "נקייה"
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        except Exception:
            pass

        # אם עדיין יש NaT, ננסה parsing פר-ערך עם הפונקציה הכללית
        mask_bad = df[date_col].isna()
        if mask_bad.any():
            parsed = df.loc[mask_bad, date_col].apply(parse_date_or_timestamp)
            df.loc[mask_bad, date_col] = parsed

        # לוודא טיפוס
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        return df

    # אין date, אבל יש datetime
    if datetime_col in df.columns:
        parsed = df[datetime_col].apply(parse_date_or_timestamp)
        df[date_col] = parsed
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        return df

    # אין date/ datetime, אבל יש timestamp
    if timestamp_col in df.columns:
        parsed = df[timestamp_col].apply(parse_date_or_timestamp)
        df[date_col] = parsed
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        return df

    # אין לנו שום עמודת זמן ברורה – מחזירים כמו שהוא
    return df


# ---------------------------------------------------------------------
# פונקציות עבודה על קבצים
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
    """
    שומר את df ל-path, יוצר קודם גיבוי path.bak אם הקובץ קיים.
    """
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


def normalize_file_time_columns(filename: str) -> None:
    path = os.path.join(RESULTS_DIR, filename)
    df = load_csv_safe(path)
    if df is None or df.empty:
        return

    print(f"\n--- Normalizing time columns for: {filename} ---")
    before_cols = df.columns.tolist()
    print(f"[DEBUG] columns before: {before_cols}")

    df = build_date_column(df)

    if "date" not in df.columns:
        print(f"[WARN] could not build 'date' column for {filename}, skipping save.")
        return

    # להסיר שורות שאין להן date
    before_len = len(df)
    df = df[df["date"].notna()].copy()
    after_len = len(df)
    if after_len < before_len:
        print(f"[INFO] dropped {before_len - after_len} rows with invalid date in {filename}")

    # למיין לפי date
    df = df.sort_values("date").reset_index(drop=True)

    # טיפוס יחיד
    df["date"] = pd.to_datetime(df["date"])

    print(f"[DEBUG] date range: {df['date'].min()} -> {df['date'].max()}")

    save_with_backup(df, path)


def run_all() -> None:
    print(f"[INFO] base dir: {BASEDIR}")
    print(f"[INFO] results dir: {RESULTS_DIR}")
    print("[INFO] starting time format normalization...")

    for fname in ALL_FILES:
        normalize_file_time_columns(fname)

    print("\n[INFO] finished time normalization for all configured files.")


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
