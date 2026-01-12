#!/usr/bin/env python3
# coding: utf-8

import os
from typing import Optional

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

# קבצי equity בפורמט snake_case
CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")

CRYPTO_OUTPUT_FILE = os.path.join(RESULTS_DIR, "crypto_daily_summary.csv")
US_OUTPUT_FILE = os.path.join(RESULTS_DIR, "us_daily_summary.csv")


def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
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
    return equity.diff().fillna(0.0)


def build_crypto_daily() -> None:
    print("\n[INFO] === Building CRYPTO daily summary ===")

    strat = load_equity_csv(CRYPTO_STRAT_FILE, "crypto_strategy")
    bench = load_equity_csv(CRYPTO_BENCH_FILE, "crypto_benchmark")

    if strat is None and bench is None:
        print("[WARN] no crypto equity data found, skipping crypto_daily_summary.")
        return

    # טווח תאריכים לפי הנתונים
    dates = []
    for df in [strat, bench]:
        if df is not None and not df.empty:
            dates.append(df["date"].min())
            dates.append(df["date"].max())

    if not dates:
        print("[WARN] no crypto dates, skipping.")
        return

    start = min(dates)
    end = max(dates)
    all_dates = pd.date_range(start=start, end=end, freq="D")

    df_out = pd.DataFrame({"date": all_dates})

    if strat is not None:
        tmp = strat.rename(columns={"equity": "crypto_total"})
        df_out = df_out.merge(tmp, on="date", how="left")
        df_out["crypto_pnl"] = compute_daily_pnl(df_out["crypto_total"])
    else:
        df_out["crypto_total"] = np.nan
        df_out["crypto_pnl"] = np.nan

    if bench is not None:
        tmp = bench.rename(columns={"equity": "crypto_benchmark"})
        df_out = df_out.merge(tmp, on="date", how="left")
    else:
        df_out["crypto_benchmark"] = np.nan

    df_out = df_out.sort_values("date").reset_index(drop=True)

    # גיבוי
    if os.path.exists(CRYPTO_OUTPUT_FILE):
        bak = CRYPTO_OUTPUT_FILE + ".bak"
        try:
            os.replace(CRYPTO_OUTPUT_FILE, bak)
            print(f"[INFO] backup written: {bak}")
        except Exception as e:
            print(f"[WARN] failed to create backup for {CRYPTO_OUTPUT_FILE}: {e}")

    print(f"[INFO] writing crypto daily to {CRYPTO_OUTPUT_FILE}")
    df_out.to_csv(CRYPTO_OUTPUT_FILE, index=False)
    print(f"[INFO] rows: {len(df_out)}, date range: {df_out['date'].min()} -> {df_out['date'].max()}")


def build_us_daily() -> None:
    print("\n[INFO] === Building US daily summary ===")

    strat = load_equity_csv(US_STRAT_FILE, "us_strategy")
    bench = load_equity_csv(US_BENCH_FILE, "us_benchmark")

    if strat is None and bench is None:
        print("[WARN] no US equity data found, skipping us_daily_summary.")
        return

    dates = []
    for df in [strat, bench]:
        if df is not None and not df.empty:
            dates.append(df["date"].min())
            dates.append(df["date"].max())

    if not dates:
        print("[WARN] no US dates, skipping.")
        return

    start = min(dates)
    end = max(dates)
    all_dates = pd.date_range(start=start, end=end, freq="D")

    df_out = pd.DataFrame({"date": all_dates})

    if strat is not None:
        tmp = strat.rename(columns={"equity": "us_total"})
        df_out = df_out.merge(tmp, on="date", how="left")
        df_out["us_pnl"] = compute_daily_pnl(df_out["us_total"])
    else:
        df_out["us_total"] = np.nan
        df_out["us_pnl"] = np.nan

    if bench is not None:
        tmp = bench.rename(columns={"equity": "us_benchmark"})
        df_out = df_out.merge(tmp, on="date", how="left")
    else:
        df_out["us_benchmark"] = np.nan

    df_out = df_out.sort_values("date").reset_index(drop=True)

    if os.path.exists(US_OUTPUT_FILE):
        bak = US_OUTPUT_FILE + ".bak"
        try:
            os.replace(US_OUTPUT_FILE, bak)
            print(f"[INFO] backup written: {bak}")
        except Exception as e:
            print(f"[WARN] failed to create backup for {US_OUTPUT_FILE}: {e}")

    print(f"[INFO] writing US daily to {US_OUTPUT_FILE}")
    df_out.to_csv(US_OUTPUT_FILE, index=False)
    print(f"[INFO] rows: {len(df_out)}, date range: {df_out['date'].min()} -> {df_out['date'].max()}")


def main() -> None:
    build_crypto_daily()
    build_us_daily()


if __name__ == "__main__":
    main()
