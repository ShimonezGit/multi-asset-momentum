#!/usr/bin/env python3
# coding: utf-8

import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

CRYPTO_RAW = os.path.join(RESULTS_DIR, "crypto_daily_summary.csv")
US_RAW = os.path.join(RESULTS_DIR, "us_daily_summary.csv")

CRYPTO_PRETTY = os.path.join(RESULTS_DIR, "crypto_daily_summary_pretty.csv")
US_PRETTY = os.path.join(RESULTS_DIR, "us_daily_summary_pretty.csv")


def format_dollar(x: float) -> str:
    if pd.isna(x):
        return ""
    return f"${x:,.2f}"


def build_crypto_pretty() -> None:
    if not os.path.exists(CRYPTO_RAW):
        print(f"[INFO] crypto raw file not found, skipping: {CRYPTO_RAW}")
        return

    df = pd.read_csv(CRYPTO_RAW)
    if "date" not in df.columns:
        print("[WARN] crypto_daily_summary missing 'date', skipping.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    # forward-fill totals/benchmark לתצוגה חלקה
    for col in ["crypto_total", "crypto_benchmark"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
            df[col] = df[col].ffill()

    # PnL יומי + מצטבר
    if "crypto_pnl" in df.columns:
        df["crypto_pnl"] = df["crypto_pnl"].astype(float).fillna(0.0)
        df["crypto_pnl_cum"] = df["crypto_pnl"].cumsum()
    else:
        df["crypto_pnl"] = 0.0
        df["crypto_pnl_cum"] = 0.0

    out = pd.DataFrame()
    out["date"] = df["date"].dt.date

    # totals
    if "crypto_total" in df.columns:
        out["crypto_total"] = df["crypto_total"].apply(format_dollar)
    # pnl יומי + מצטבר
    out["crypto_pnl_daily"] = df["crypto_pnl"].apply(format_dollar)
    out["crypto_pnl_cum"] = df["crypto_pnl_cum"].apply(format_dollar)
    # benchmark
    if "crypto_benchmark" in df.columns:
        out["crypto_benchmark"] = df["crypto_benchmark"].apply(format_dollar)

    out.to_csv(CRYPTO_PRETTY, index=False)
    print(f"[INFO] wrote crypto pretty daily to {CRYPTO_PRETTY}")


def build_us_pretty() -> None:
    if not os.path.exists(US_RAW):
        print(f"[INFO] US raw file not found, skipping: {US_RAW}")
        return

    df = pd.read_csv(US_RAW)
    if "date" not in df.columns:
        print("[WARN] us_daily_summary missing 'date', skipping.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    for col in ["us_total", "us_benchmark"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
            df[col] = df[col].ffill()

    if "us_pnl" in df.columns:
        df["us_pnl"] = df["us_pnl"].astype(float).fillna(0.0)
        df["us_pnl_cum"] = df["us_pnl"].cumsum()
    else:
        df["us_pnl"] = 0.0
        df["us_pnl_cum"] = 0.0

    out = pd.DataFrame()
    out["date"] = df["date"].dt.date

    if "us_total" in df.columns:
        out["us_total"] = df["us_total"].apply(format_dollar)
    out["us_pnl_daily"] = df["us_pnl"].apply(format_dollar)
    out["us_pnl_cum"] = df["us_pnl_cum"].apply(format_dollar)
    if "us_benchmark" in df.columns:
        out["us_benchmark"] = df["us_benchmark"].apply(format_dollar)

    out.to_csv(US_PRETTY, index=False)
    print(f"[INFO] wrote US pretty daily to {US_PRETTY}")


def main() -> None:
    build_crypto_pretty()
    build_us_pretty()


if __name__ == "__main__":
    main()
