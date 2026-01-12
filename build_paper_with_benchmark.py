#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_paper_with_benchmark.py

מוסיף עקומת benchmark לקבצי ה-Paper:
- crypto_paper_equity.csv
- us_paper_equity.csv
- il_paper_equity.csv

על בסיס קבצי ה-Backtest/Benchmark:
- crypto_equity_curve.csv
- us_equity_curve.csv
- il_equity_curve.csv

התוצאה: אותם קבצי paper ייכתבו מחדש עם העמודות:
date,equity,benchmark_equity
"""

import os
import pandas as pd

RESULTS_DIR = "results_multi"

PAPER_FILES = {
    "CRYPTO": os.path.join(RESULTS_DIR, "crypto_paper_equity.csv"),
    "US": os.path.join(RESULTS_DIR, "us_paper_equity.csv"),
    "IL": os.path.join(RESULTS_DIR, "il_paper_equity.csv"),
}

BENCHMARK_FILES = {
    "CRYPTO": os.path.join(RESULTS_DIR, "crypto_equity_curve.csv"),
    "US": os.path.join(RESULTS_DIR, "us_equity_curve.csv"),
    "IL": os.path.join(RESULTS_DIR, "il_equity_curve.csv"),
}

def load_csv(path: str, name: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"לא נמצא קובץ {name}: {path}")
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"קובץ {name} חייב לכלול עמודה 'date'. ({path})")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df

def build_single(market: str, paper_path: str, bench_path: str) -> None:
    print("=" * 80)
    print(f"Building PAPER+BENCH for {market}")
    print(f"Paper file:      {paper_path}")
    print(f"Benchmark file:  {bench_path}")

    paper_df = load_csv(paper_path, f"{market} PAPER")
    bench_df = load_csv(bench_path, f"{market} BENCH")

    if "equity" not in paper_df.columns:
        raise ValueError(f"{market} PAPER missing 'equity' column.")
    if "benchmark_equity" not in bench_df.columns:
        raise ValueError(f"{market} BENCH missing 'benchmark_equity' column. Columns={list(bench_df.columns)}")

    bench_small = bench_df[["date", "benchmark_equity"]].copy()

    merged = paper_df.merge(bench_small, on="date", how="left")

    if merged["benchmark_equity"].isna().all():
        raise RuntimeError(
            f"{market}: אחרי המיזוג כל benchmark_equity הוא NaN. כנראה שטווח התאריכים של paper ו-benchmark לא חופף."
        )

    print("Preview merged head:")
    print(merged.head(5))

    out_cols = ["date", "equity", "benchmark_equity"]
    merged[out_cols].to_csv(paper_path, index=False)

    print(f"✔ {market} updated with benchmark_equity and written back to:")
    print(f"  {paper_path}")
    print("=" * 80)
    print()

def main() -> None:
    for mkt in ["CRYPTO", "US", "IL"]:
        build_single(mkt, PAPER_FILES[mkt], BENCHMARK_FILES[mkt])

if __name__ == "__main__":
    main()
