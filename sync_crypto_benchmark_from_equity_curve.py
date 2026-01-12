#!/usr/bin/env python3
# coding: utf-8
# sync_crypto_benchmark_from_equity_curve.py

import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    base_dir = Path(".").resolve()
    results_dir = base_dir / "results_multi"

    source_curve_2022_path = results_dir / "crypto_equity_curve_2022-2025.csv"
    crypto_paper_path = results_dir / "crypto_paper_equity.csv"
    crypto_benchmark_curve_path = results_dir / "crypto_equity_curve.csv"

    print("=" * 80)
    print("Crypto benchmark sync – from crypto_equity_curve_2022-2025.csv")
    print(f"Base dir:      {base_dir}")
    print(f"results_multi: {results_dir}")
    print("=" * 80)

    if not results_dir.exists() or not results_dir.is_dir():
        print(f"ERROR: results_multi folder not found at: {results_dir}")
        return 1

    if not source_curve_2022_path.exists():
        print(f"ERROR: crypto_equity_curve_2022-2025.csv not found at: {source_curve_2022_path}")
        return 1

    bench_src = pd.read_csv(source_curve_2022_path)
    if "date" not in bench_src.columns:
        print("ERROR: crypto_equity_curve_2022-2025.csv must have 'date' column.")
        return 1

    value_col = None
    for cand in ["equity", "Equity", "price", "close", "Close"]:
        if cand in bench_src.columns:
            value_col = cand
            break

    if value_col is None:
        print(
            "ERROR: could not find value column in crypto_equity_curve_2022-2025.csv "
            "(expected one of: equity, Equity, price, close, Close)."
        )
        print(f"Columns: {list(bench_src.columns)}")
        return 1

    bench_src["date"] = pd.to_datetime(bench_src["date"])
    bench_src[value_col] = bench_src[value_col].astype(float)
    bench_src = bench_src.sort_values("date").reset_index(drop=True)

    print(
        f"Loaded crypto_equity_curve_2022-2025: {len(bench_src)} rows, "
        f"{bench_src['date'].min().date()} -> {bench_src['date'].max().date()}, "
        f"value column: {value_col}"
    )

    bench_df = bench_src[["date", value_col]].rename(columns={value_col: "equity"})

    if not crypto_paper_path.exists():
        print(f"ERROR: crypto_paper_equity.csv not found at: {crypto_paper_path}")
        return 1

    crypto_paper = pd.read_csv(crypto_paper_path)
    if "date" not in crypto_paper.columns or "equity" not in crypto_paper.columns:
        print("ERROR: crypto_paper_equity.csv must have 'date','equity' columns.")
        return 1

    crypto_paper["date"] = pd.to_datetime(crypto_paper["date"])
    crypto_paper = crypto_paper.sort_values("date").reset_index(drop=True)

    print(
        f"Loaded crypto_paper_equity: {len(crypto_paper)} rows, "
        f"{crypto_paper['date'].min().date()} -> {crypto_paper['date'].max().date()}"
    )

    merged = crypto_paper.merge(
        bench_df.rename(columns={"equity": "benchmark_equity_new"}),
        on="date",
        how="left",
    )

    total_rows = len(merged)
    with_bm = merged["benchmark_equity_new"].notna().sum()
    print(f"Rows with BTC benchmark: {with_bm}/{total_rows}")

    if with_bm == 0:
        print("ERROR: no overlapping dates between crypto_paper_equity and crypto_equity_curve_2022-2025.")
        return 1

    if "benchmark_equity" in merged.columns:
        merged.drop(columns=["benchmark_equity"], inplace=True)

    merged.rename(columns={"benchmark_equity_new": "benchmark_equity"}, inplace=True)

    merged_out = merged.sort_values("date").reset_index(drop=True)
    merged_out.to_csv(crypto_paper_path, index=False)
    print(f"Updated crypto_paper_equity.csv with BTC benchmark_equity.")

    bench_curve = merged_out[["date", "benchmark_equity"]].dropna().copy()
    bench_curve.rename(columns={"benchmark_equity": "equity"}, inplace=True)
    bench_curve = bench_curve.sort_values("date").reset_index(drop=True)

    bench_curve.to_csv(crypto_benchmark_curve_path, index=False)
    print(
        f"Wrote crypto_equity_curve.csv to: {crypto_benchmark_curve_path}\n"
        f"Rows: {len(bench_curve)}, "
        f"Range: {bench_curve['date'].min().date()} -> {bench_curve['date'].max().date()}"
    )

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
