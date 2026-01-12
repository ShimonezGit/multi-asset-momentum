#!/usr/bin/env python3
# coding: utf-8
# build_us_benchmark_from_yfinance.py
# מוריד SPY יומי מ-yfinance, ובונה עקומת benchmark מנורמלת ל-100,000

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf


def main() -> int:
    base_dir = Path(".").resolve()

    ticker = "SPY"
    start_date = "2022-01-03"
    end_date = "2025-12-31"

    print("=" * 80)
    print(f"Downloading {ticker} from yfinance")
    print(f"Range: {start_date} -> {end_date}")
    print("=" * 80)

    data = yf.download(ticker, start=start_date, end=end_date, group_by="ticker", auto_adjust=False)
    if data.empty:
        print("No data returned from yfinance. Check ticker / dates / network.")
        return 1

    raw_path = base_dir / f"{ticker.lower()}_historical_raw.csv"
    data.to_csv(raw_path)
    print(f"Saved raw data to: {raw_path}")

    df = data.copy()
    # אם העמודות הן MultiIndex, נשטיח
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(c) for c in col if c != ""]) for col in df.columns]

    print("Columns after flatten:", list(df.columns))

    # כאן מעדכנים לרשימה הנכונה לפי מה שראינו:
    candidates = [
        "SPY_Adj Close",
        "SPY_Adj_Close",
        "SPY_Close",
        "Adj Close",
        "Close",
    ]

    price_col = None
    for candidate in candidates:
        if candidate in df.columns:
            price_col = candidate
            break

    if price_col is None:
        print("Could not find a usable price column.")
        print(f"Columns: {list(df.columns)}")
        return 1

    print(f"Using price column: {price_col}")

    close = df[price_col].reset_index()
    close.columns = ["date", "price"]

    close["date"] = pd.to_datetime(close["date"])
    close = close.sort_values("date").reset_index(drop=True)

    start_price = float(close["price"].iloc[0])
    if start_price == 0:
        print("Start price is zero, cannot normalize.")
        return 1

    close["equity"] = 100_000.0 * (close["price"] / start_price)

    bench_path = base_dir / "us_benchmark_equity_from_spy.csv"
    close[["date", "equity"]].to_csv(bench_path, index=False)
    print(f"Saved normalized benchmark equity to: {bench_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
