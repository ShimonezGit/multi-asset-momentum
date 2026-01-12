#!/usr/bin/env python3
# coding: utf-8

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "btc_usd_daily_2022_2025.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "results_multi")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "crypto_equity_curve.csv")

INITIAL_CAPITAL = 100000.0


def main() -> None:
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"btc price file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    # מניח שיש עמודות date ו-close או adj_close; אם השם שונה, צריך לעדכן כאן.
    price_col = None
    for cand in ["close", "Close", "adj_close", "Adj Close"]:
        if cand in df.columns:
            price_col = cand
            break
    if price_col is None:
        raise ValueError("Could not find price column (close/adj_close) in BTC file.")

    if "date" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    if "date" not in df.columns:
        raise ValueError("Could not find 'date' column in BTC file.")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # בונים עקומת Buy&Hold מ-100k
    prices = df[price_col].astype(float)
    start_price = float(prices.iloc[0])
    if start_price <= 0:
        raise ValueError("First BTC price is non-positive, cannot build benchmark.")

    units = INITIAL_CAPITAL / start_price
    equity = units * prices

    out = pd.DataFrame(
        {
            "date": df["date"],
            "equity": equity,
        }
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote BTC benchmark equity to: {OUTPUT_FILE}")
    print(
        f"Date range: {out['date'].min().date()} -> {out['date'].max().date()}, "
        f"start_equity={equity.iloc[0]:.2f}, end_equity={equity.iloc[-1]:.2f}"
    )


if __name__ == "__main__":
    main()
