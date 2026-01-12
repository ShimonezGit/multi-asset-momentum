#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd

RESULTS_DIR = "results_multi"

FILES = {
    "CRYPTO": os.path.join(RESULTS_DIR, "crypto_paper_equity.csv"),
    "US": os.path.join(RESULTS_DIR, "us_paper_equity.csv"),
    "IL": os.path.join(RESULTS_DIR, "il_paper_equity.csv"),
}

def debug_file(name: str, path: str) -> None:
    print("=" * 80)
    print(f"{name} :: {path}")
    if not os.path.exists(path):
        print("FILE NOT FOUND")
        return
    df = pd.read_csv(path)
    print("Columns:", list(df.columns))
    print("\nHead:")
    print(df.head(5))
    print("\nDtypes:")
    print(df.dtypes)
    print("=" * 80)
    print()

def main() -> None:
    for name, path in FILES.items():
        debug_file(name, path)

if __name__ == "__main__":
    main()
