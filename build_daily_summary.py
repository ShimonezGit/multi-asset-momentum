#!/usr/bin/env python3
# coding: utf-8

import os
from typing import Optional

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

# שמות הקבצים עם "_" (snake_case)
CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")
MULTI_STRAT_FILE = os.path.join(RESULTS_DIR, "multi_adaptive_paper_equity.csv")
# אם בעתיד יהיה benchmark ל-Multi-Adaptive:
MULTI_BENCH_FILE = None  # כרגע אין קובץ כזה

OUTPUT_FILE = os.path.join(RESULTS_DIR, "daily_summary.csv")


def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
    """
    טוען קובץ equity עם עמודות date,equity ומחזיר DataFrame נקי.
    """
    if path is None:
        return None

    if not os.path.exists(path):
        print(f"[INFO] {label}: file not found, skipping: {path}")
        return None

    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"[WARN] {label}: failed to read {path}: {e}")
        return None

    if "date" not in df.columns or "equity" not in df.columns:
        print(f"[WARN] {label}: missing 'date'/'equity' columns in {path}, skipping.")
        return None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)

    try:
        df["equity"] = df["equity"].astype(float)
    except Exception:
        df["equity"] = (
            df["equity"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )
        df["equity"] = pd.to_numeric(df["equity"], errors="coerce")

    df = df[df["equity"].notna()].copy()
    return df[["date", "equity"]]


def compute_daily_pnl(equity: pd.Series) -> pd.Series:
    """
    PnL יומי: שינוי ב-equity ביחידות כסף (לא אחוז).
    """
    pnl = equity.diff().fillna(0.0)
    return pnl


def build_daily_summary() -> None:
    print(f"[INFO] base dir   : {BASE_DIR}")
    print(f"[INFO] results dir: {RESULTS_DIR}")

    crypto_strat = load_equity_csv(CRYPTO_STRAT_FILE, "crypto_strategy")
    crypto_bench = load_equity_csv(CRYPTO_BENCH_FILE, "crypto_benchmark")
    us_strat = load_equity_csv(US_STRAT_FILE, "us_strategy")
    us_bench = load_equity_csv(US_BENCH_FILE, "us_benchmark")
    multi_strat = load_equity_csv(MULTI_STRAT_FILE, "multi_adaptive")
    multi_bench = load_equity_csv(MULTI_BENCH_FILE, "multi_benchmark") if MULTI_BENCH_FILE else None

    # טווח תאריכים מלא 2022-01-01 עד 2025-12-31
    start = pd.Timestamp("2022-01-01")
    end = pd.Timestamp("2025-12-31")
    all_dates = pd.date_range(start=start, end=end, freq="D")

    summary = pd.DataFrame({"date": all_dates})

    # CRYPTO
    if crypto_strat is not None:
        tmp = crypto_strat.rename(columns={"equity": "crypto_total"})
        summary = summary.merge(tmp, on="date", how="left")
        summary["crypto_pnl"] = compute_daily_pnl(summary["crypto_total"])
    else:
        summary["crypto_total"] = np.nan
        summary["crypto_pnl"] = np.nan

    if crypto_bench is not None:
        tmp = crypto_bench.rename(columns={"equity": "crypto_benchmark"})
        summary = summary.merge(tmp, on="date", how="left")
    else:
        summary["crypto_benchmark"] = np.nan

    # US
    if us_strat is not None:
        tmp = us_strat.rename(columns={"equity": "us_total"})
        summary = summary.merge(tmp, on="date", how="left")
        summary["us_pnl"] = compute_daily_pnl(summary["us_total"])
    else:
        summary["us_total"] = np.nan
        summary["us_pnl"] = np.nan

    if us_bench is not None:
        tmp = us_bench.rename(columns={"equity": "us_benchmark"})
        summary = summary.merge(tmp, on="date", how="left")
    else:
        summary["us_benchmark"] = np.nan

    # Multi-Adaptive
    if multi_strat is not None:
        tmp = multi_strat.rename(columns={"equity": "multi_total"})
        summary = summary.merge(tmp, on="date", how="left")
        summary["multi_pnl"] = compute_daily_pnl(summary["multi_total"])
    else:
        summary["multi_total"] = np.nan
        summary["multi_pnl"] = np.nan

    if multi_bench is not None:
        tmp = multi_bench.rename(columns={"equity": "multi_benchmark"})
        summary = summary.merge(tmp, on="date", how="left")
    else:
        summary["multi_benchmark"] = np.nan

    # עמודות sandbox/instrument לתאימות לדשבורד
    for col in [
        "crypto_sandbox",
        "crypto_instrument",
        "us_sandbox",
        "us_instrument",
        "multi_sandbox",
        "multi_instrument",
    ]:
        if col not in summary.columns:
            summary[col] = np.nan

    # סדר עמודות
    cols = [
        "date",
        "crypto_pnl",
        "crypto_total",
        "crypto_benchmark",
        "crypto_sandbox",
        "crypto_instrument",
        "us_pnl",
        "us_total",
        "us_benchmark",
        "us_sandbox",
        "us_instrument",
        "multi_pnl",
        "multi_total",
        "multi_benchmark",
        "multi_sandbox",
        "multi_instrument",
    ]
    # לוודא שכל העמודות קיימות, גם אם NaN
    for c in cols:
        if c not in summary.columns:
            summary[c] = np.nan

    summary = summary[cols]
    summary = summary.sort_values("date").reset_index(drop=True)

    # גיבוי אם יש קובץ קיים
    if os.path.exists(OUTPUT_FILE):
        bak = OUTPUT_FILE + ".bak"
        try:
            os.replace(OUTPUT_FILE, bak)
            print(f"[INFO] backup written: {bak}")
        except Exception as e:
            print(f"[WARN] failed to create backup for {OUTPUT_FILE}: {e}")

    print(f"[INFO] writing daily summary (clean numeric) to {OUTPUT_FILE}")
    summary.to_csv(OUTPUT_FILE, index=False)
    print(f"[INFO] total rows: {len(summary)}")
    print(f"[INFO] date range: {summary['date'].min()} -> {summary['date'].max()}")


def main() -> None:
    build_daily_summary()


if __name__ == "__main__":
    main()
