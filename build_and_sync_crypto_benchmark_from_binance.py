#!/usr/bin/env python3
# coding: utf-8
# build_and_sync_crypto_benchmark_from_binance.py
# בונה בנצ'מרק BTC יומי מ-btc_5m_binance_clean.csv ומסנכרן ל-crypto_paper_equity.csv

import sys
from pathlib import Path

import pandas as pd


def build_daily_btc_equity_from_5m(src_path: Path) -> pd.DataFrame:
    """לוקח BTC 5m מ-binance ומחזיר daily equity מנורמל ל-100,000."""
    if not src_path.exists():
        raise FileNotFoundError(f"5m BTC file not found: {src_path}")

    df = pd.read_csv(src_path)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
    elif "unix_ms" in df.columns:
        df["time"] = pd.to_datetime(df["unix_ms"], unit="ms")
    else:
        raise ValueError("btc_5m file must have 'time' or 'unix_ms' column.")

    df["date"] = df["time"].dt.date
    if "Close" not in df.columns:
        raise ValueError("btc_5m file must have 'Close' column.")

    # סגירה יומית – ניקח את close האחרון בכל יום
    daily = (
        df.sort_values("time")
        .groupby("date")
        .agg(price=("Close", "last"))
        .reset_index()
    )

    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").reset_index(drop=True)

    if daily.empty:
        raise ValueError("No daily data built from 5m BTC file.")

    start_price = float(daily["price"].iloc[0])
    if start_price == 0:
        raise ValueError("Start price is zero, cannot normalize benchmark.")

    daily["equity"] = 100_000.0 * daily["price"] / start_price
    return daily[["date", "equity"]]


def main() -> int:
    base_dir = Path(".").resolve()
    results_dir = base_dir / "results_multi"

    btc_5m_path = base_dir / "btc_5m_binance_clean.csv"
    crypto_paper_path = results_dir / "crypto_paper_equity.csv"
    crypto_bench_curve_path = results_dir / "crypto_equity_curve.csv"

    print("=" * 80)
    print("Crypto benchmark build & sync (BTC/USDT from Binance)")
    print(f"Base dir:      {base_dir}")
    print(f"results_multi: {results_dir}")
    print("=" * 80)

    if not results_dir.exists() or not results_dir.is_dir():
        print(f"ERROR: results_multi folder not found at: {results_dir}")
        return 1

    # 1. בונים בנצ'מרק יומי מ-5m
    print(f"Building daily BTC equity from: {btc_5m_path}")
    daily_btc = build_daily_btc_equity_from_5m(btc_5m_path)
    print(
        f"Daily BTC equity built: {len(daily_btc)} rows, "
        f"{daily_btc['date'].min().date()} -> {daily_btc['date'].max().date()}"
    )

    # 2. טוענים crypto_paper_equity.csv
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

    # 3. ממזגים את הבנצ'מרק לפי תאריך
    merged = crypto_paper.merge(
        daily_btc.rename(columns={"equity": "benchmark_equity_new"}),
        on="date",
        how="left",
    )

    total_rows = len(merged)
    with_bm = merged["benchmark_equity_new"].notna().sum()
    print(f"Rows with BTC benchmark: {with_bm}/{total_rows}")

    if with_bm == 0:
        print("ERROR: no overlapping dates between crypto_paper_equity and BTC daily benchmark.")
        return 1

    # זורקים benchmark_equity ישן אם קיים
    if "benchmark_equity" in merged.columns:
        merged.drop(columns=["benchmark_equity"], inplace=True)

    merged.rename(columns={"benchmark_equity_new": "benchmark_equity"}, inplace=True)

    # שומרים את crypto_paper_equity.csv המעודכן
    merged_out = merged.sort_values("date").reset_index(drop=True)
    merged_out.to_csv(crypto_paper_path, index=False)
    print(f"Updated crypto_paper_equity.csv with BTC benchmark_equity.")

    # 4. בונים crypto_equity_curve.csv – בנצ'מרק נקי
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
