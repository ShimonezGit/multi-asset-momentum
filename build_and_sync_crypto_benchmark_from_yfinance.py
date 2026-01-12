#!/usr/bin/env python3
# coding: utf-8
# build_and_sync_crypto_benchmark_from_yfinance.py
# מוריד BTC-USD מ-yahoo, בונה benchmark מנורמל ל-100k ומסנכרן ל-crypto_paper_equity.csv

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf


def build_btc_daily_equity(start_date: str, end_date: str) -> pd.DataFrame:
    ticker = "BTC-USD"
    print(f"Downloading {ticker} from yfinance: {start_date} -> {end_date}")
    data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False)
    if data.empty:
        raise RuntimeError("No data returned from yfinance for BTC-USD.")

    df = data.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(c) for c in col if c != ""]) for col in df.columns]

    # כאן מעדכנים לרשימת העמודות הנכונה
    candidates = [
        "Adj Close_BTC-USD",
        "Close_BTC-USD",
        "Adj Close",
        "Adj_Close",
        "Close",
    ]
    price_col = None
    for c in candidates:
        if c in df.columns:
            price_col = c
            break

    if price_col is None:
        raise RuntimeError(f"Could not find price column in BTC-USD data. Columns: {list(df.columns)}")

    close = df[price_col].reset_index()
    close.columns = ["date", "price"]
    close["date"] = pd.to_datetime(close["date"])
    close = close.sort_values("date").reset_index(drop=True)

    start_price = float(close["price"].iloc[0])
    if start_price == 0:
        raise RuntimeError("Start price is zero, cannot normalize.")

    close["equity"] = 100_000.0 * close["price"] / start_price
    return close[["date", "equity"]]


def main() -> int:
    base_dir = Path(".").resolve()
    results_dir = base_dir / "results_multi"

    crypto_paper_path = results_dir / "crypto_paper_equity.csv"
    crypto_bench_curve_path = results_dir / "crypto_equity_curve.csv"

    print("=" * 80)
    print("Crypto benchmark build & sync – BTC-USD from Yahoo Finance")
    print(f"Base dir:      {base_dir}")
    print(f"results_multi: {results_dir}")
    print("=" * 80)

    if not results_dir.exists() or not results_dir.is_dir():
        print(f"ERROR: results_multi folder not found at: {results_dir}")
        return 1

    if not crypto_paper_path.exists():
        print(f"ERROR: crypto_paper_equity.csv not found at: {crypto_paper_path}")
        return 1

    crypto_paper = pd.read_csv(crypto_paper_path)
    if "date" not in crypto_paper.columns or "equity" not in crypto_paper.columns:
        print("ERROR: crypto_paper_equity.csv must have 'date','equity' columns.")
        return 1

    crypto_paper["date"] = pd.to_datetime(crypto_paper["date"])
    crypto_paper = crypto_paper.sort_values("date").reset_index(drop=True)

    start_date = crypto_paper["date"].min().strftime("%Y-%m-%d")
    end_date = (crypto_paper["date"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    print(
        f"Loaded crypto_paper_equity: {len(crypto_paper)} rows, "
        f"{start_date} -> {(pd.to_datetime(end_date) - pd.Timedelta(days=1)).date()}"
    )

    btc_daily = build_btc_daily_equity(start_date, end_date)
    print(
        f"BTC-USD daily equity: {len(btc_daily)} rows, "
        f"{btc_daily['date'].min().date()} -> {btc_daily['date'].max().date()}"
    )

    merged = crypto_paper.merge(
        btc_daily.rename(columns={"equity": "benchmark_equity_new"}),
        on="date",
        how="left",
    )

    total_rows = len(merged)
    with_bm = merged["benchmark_equity_new"].notna().sum()
    print(f"Rows with BTC benchmark: {with_bm}/{total_rows}")

    if with_bm == 0:
        print("ERROR: no overlapping dates between crypto_paper_equity and BTC-USD benchmark.")
        return 1

    if "benchmark_equity" in merged.columns:
        merged.drop(columns=["benchmark_equity"], inplace=True)

    merged.rename(columns={"benchmark_equity_new": "benchmark_equity"}, inplace=True)

    merged_out = merged.sort_values("date").reset_index(drop=True)
    merged_out.to_csv(crypto_paper_path, index=False)
    print("Updated crypto_paper_equity.csv with BTC-USD benchmark_equity.")

    bench_curve = merged_out[["date", "benchmark_equity"]].dropna().copy()
    bench_curve.rename(columns={"benchmark_equity": "equity"}, inplace=True)
    bench_curve = bench_curve.sort_values("date").reset_index(drop=True)

    bench_curve.to_csv(crypto_bench_curve_path, index=False)
    print(
        f"Wrote crypto_equity_curve.csv to: {crypto_bench_curve_path}\n"
        f"Rows: {len(bench_curve)}, "
        f"Range: {bench_curve['date'].min().date()} -> {bench_curve['date'].max().date()}"
    )

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
