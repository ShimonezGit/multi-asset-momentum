#!/usr/bin/env python3
# coding: utf-8
# sync_us_benchmark_from_spy.py
# לוקח את us_benchmark_equity_from_spy.csv, מיישר מול us_paper_equity.csv
# וכותב:
# 1) results_multi/us_equity_curve.csv (benchmark נקי)
# 2) results_multi/us_paper_equity.csv מעודכן עם benchmark_equity מלא

import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    base_dir = Path(".").resolve()
    results_dir = base_dir / "results_multi"

    spy_bench_path = base_dir / "us_benchmark_equity_from_spy.csv"
    us_paper_path = results_dir / "us_paper_equity.csv"
    us_benchmark_curve_path = results_dir / "us_equity_curve.csv"

    print("=" * 80)
    print("US benchmark sync – SPY -> results_multi")
    print(f"Base dir:      {base_dir}")
    print(f"results_multi: {results_dir}")
    print("=" * 80)

    # בדיקה בסיסית ש-results_multi קיים
    if not results_dir.exists() or not results_dir.is_dir():
        print(f"ERROR: results_multi folder not found at: {results_dir}")
        return 1

    # טעינת benchmark מה-SPY
    if not spy_bench_path.exists():
        print(f"ERROR: benchmark file not found: {spy_bench_path}")
        return 1

    spy_df = pd.read_csv(spy_bench_path)
    if "date" not in spy_df.columns or "equity" not in spy_df.columns:
        print("ERROR: us_benchmark_equity_from_spy.csv must have columns 'date','equity'")
        return 1

    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy_df = spy_df.sort_values("date").reset_index(drop=True)
    print(f"Loaded SPY benchmark: {len(spy_df)} rows, "
          f"{spy_df['date'].min().date()} -> {spy_df['date'].max().date()}")

    # טעינת us_paper_equity.csv
    if not us_paper_path.exists():
        print(f"ERROR: us_paper_equity.csv not found at: {us_paper_path}")
        return 1

    us_df = pd.read_csv(us_paper_path)
    if "date" not in us_df.columns or "equity" not in us_df.columns:
        print("ERROR: us_paper_equity.csv must have at least 'date','equity' columns")
        return 1

    us_df["date"] = pd.to_datetime(us_df["date"])
    us_df = us_df.sort_values("date").reset_index(drop=True)
    print(f"Loaded US paper equity: {len(us_df)} rows, "
          f"{us_df['date'].min().date()} -> {us_df['date'].max().date()}")

    # מיזוג לפי תאריך כדי ליישר benchmark לטווח של ה-papers
    merged = us_df.merge(
        spy_df[["date", "equity"]].rename(columns={"equity": "benchmark_equity_new"}),
        on="date",
        how="left",
    )

    # הדפסת סטטוס על כמה שורות קיבלו benchmark
    total_rows = len(merged)
    with_bm = merged["benchmark_equity_new"].notna().sum()
    print(f"Rows with benchmark_equity_new: {with_bm}/{total_rows}")

    if with_bm == 0:
        print("ERROR: no overlapping dates between us_paper_equity and SPY benchmark.")
        return 1

    # אם יש עמודה ישנה benchmark_equity – נזרוק או נדרוס
    if "benchmark_equity" in merged.columns:
        merged.drop(columns=["benchmark_equity"], inplace=True)

    # נקריא לעמודה החדשה בשם benchmark_equity
    merged.rename(columns={"benchmark_equity_new": "benchmark_equity"}, inplace=True)

    # נשמור חזרה את us_paper_equity.csv (sorted, בלי אינדקס)
    merged_out = merged.sort_values("date").reset_index(drop=True)
    merged_out.to_csv(us_paper_path, index=False)
    print(f"Updated us_paper_equity.csv with benchmark_equity (aligned to SPY)")

    # יצירת us_equity_curve.csv – benchmark נקי בפורמט date,equity
    # לפי אותו טווח שיש לנו ב-us_paper_equity
    bench_curve = merged_out[["date", "benchmark_equity"]].copy()
    bench_curve = bench_curve.dropna(subset=["benchmark_equity"])
    bench_curve.rename(columns={"benchmark_equity": "equity"}, inplace=True)
    bench_curve = bench_curve.sort_values("date").reset_index(drop=True)

    bench_curve.to_csv(us_benchmark_curve_path, index=False)
    print(f"Wrote US benchmark equity curve to: {us_benchmark_curve_path}")
    print(f"Rows: {len(bench_curve)}, "
          f"Range: {bench_curve['date'].min().date()} -> {bench_curve['date'].max().date()}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
