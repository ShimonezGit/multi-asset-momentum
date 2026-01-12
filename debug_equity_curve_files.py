#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd

RESULTS_DIR = "results_multi"

FILES = {
    "CRYPTO_EQ": os.path.join(RESULTS_DIR, "crypto_equity_curve.csv"),
    "US_EQ": os.path.join(RESULTS_DIR, "us_equity_curve.csv"),
    "IL_EQ": os.path.join(RESULTS_DIR, "il_equity_curve.csv"),
}

def debug_file(name: str, path: str) -> None:
    print("=" * 80)
    print(f"{name} :: {path}")
    if not os.path.exists(path):
        print("FILE NOT FOUND")
        return
    df = pd.read_csv(path)
    print("Columns:", list(df.columns))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        print("Min date:", df["date"].min())
        print("Max date:", df["date"].max())
    print("=" * 80)
    print()

def main() -> None:
    for name, path in FILES.items():
        debug_file(name, path)

if __name__ == "__main__":
    main()
