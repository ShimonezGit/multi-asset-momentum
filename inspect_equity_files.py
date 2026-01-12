# coding: utf-8

import os
from typing import List

import pandas as pd

RESULTS_DIR = "results_multi"

FILES: List[str] = [
    "crypto_paper_equity.csv",
    "us_paper_equity.csv",
    "multi_adaptive_paper_equity.csv",
    "crypto_equity_curve.csv",
    "us_equity_curve.csv",
]

def inspect_file(path: str) -> None:
    full_path = os.path.join(RESULTS_DIR, path)
    if not os.path.exists(full_path):
        print(f"[MISSING] {path}")
        return

    try:
        df = pd.read_csv(full_path)
    except Exception as e:
        print(f"[ERROR] {path} – failed to read CSV: {e}")
        return

    cols = list(df.columns)
    print(f"\n===== {path} =====")
    print(f"Columns: {cols}")

    if "date" not in df.columns:
        print("No 'date' column – cannot inspect range.")
        return

    try:
        df["date"] = pd.to_datetime(df["date"])
    except Exception as e:
        print(f"Failed to parse 'date' in {path}: {e}")
        return

    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    dmin = df["date"].min()
    dmax = df["date"].max()
    print(f"Rows: {n}")
    print(f"Start date: {dmin}")
    print(f"End   date: {dmax}")


def main() -> None:
    print(f"Inspecting equity files in: {RESULTS_DIR}")
    for fname in FILES:
        inspect_file(fname)


if __name__ == "__main__":
    main()
