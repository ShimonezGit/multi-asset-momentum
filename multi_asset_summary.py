#!/usr/bin/env python3
# coding: utf-8

"""
multi_asset_summary.py

סקריפט שמייצר טבלת Summary אחת ל-4 מנועים:
- CRYPTO Paper
- US Paper
- IL Paper
- MULTI (תיק מנועים משולב)

קורא קבצי equity קיימים ושומר results_multi/multi_asset_summary.csv
עם מדדים: Start, End, Total Return, CAGR, MaxDD.
"""

import os
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


RESULTS_DIR = "results_multi"

CRYPTO_EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_EQUITY_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
IL_EQUITY_FILE = os.path.join(RESULTS_DIR, "il_paper_equity.csv")
MULTI_EQUITY_FILE = os.path.join(RESULTS_DIR, "multi_asset_paper_equity.csv")

SUMMARY_FILE = os.path.join(RESULTS_DIR, "multi_asset_summary.csv")


@dataclass
class StrategyStats:
    name: str
    start_date: str
    end_date: str
    start_equity: float
    end_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float


def compute_max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min() * 100.0)


def compute_cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    start_val = float(equity.iloc[0])
    end_val = float(equity.iloc[-1])
    if start_val <= 0.0:
        return 0.0
    num_days = (equity.index[-1] - equity.index[0]).days
    if num_days <= 0:
        return 0.0
    years = num_days / 365.25
    cagr = (end_val / start_val) ** (1.0 / years) - 1.0
    return float(cagr * 100.0)


def load_equity(path: str, name: str) -> pd.Series:
    if not os.path.exists(path):
        raise FileNotFoundError(f"לא נמצא קובץ equity ל-{name}: {path}")
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError(f"קובץ equity ל-{name} חייב לכלול עמודות 'date' ו-'equity'.")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df = df.set_index("date")
    return df["equity"].astype(float)


def analyze_equity(equity: pd.Series, name: str) -> StrategyStats:
    start_eq = float(equity.iloc[0])
    end_eq = float(equity.iloc[-1])
    total_return_pct = (end_eq / start_eq - 1.0) * 100.0 if start_eq > 0 else 0.0
    max_dd = compute_max_drawdown(equity)
    cagr = compute_cagr(equity)
    start_date = equity.index[0].date().isoformat()
    end_date = equity.index[-1].date().isoformat()
    return StrategyStats(
        name=name,
        start_date=start_date,
        end_date=end_date,
        start_equity=start_eq,
        end_equity=end_eq,
        total_return_pct=total_return_pct,
        cagr_pct=cagr,
        max_drawdown_pct=max_dd,
    )


def main():
    print("=" * 60)
    print("Multi-Asset Summary – CRYPTO / US / IL / MULTI")
    print("=" * 60)

    crypto_eq = load_equity(CRYPTO_EQUITY_FILE, "CRYPTO")
    us_eq = load_equity(US_EQUITY_FILE, "US")
    il_eq = load_equity(IL_EQUITY_FILE, "IL")
    multi_eq = load_equity(MULTI_EQUITY_FILE, "MULTI")

    stats: List[StrategyStats] = []
    stats.append(analyze_equity(crypto_eq, "CRYPTO"))
    stats.append(analyze_equity(us_eq, "US"))
    stats.append(analyze_equity(il_eq, "IL"))
    stats.append(analyze_equity(multi_eq, "MULTI"))

    rows = []
    for s in stats:
        rows.append(
            {
                "name": s.name,
                "start_date": s.start_date,
                "end_date": s.end_date,
                "start_equity": s.start_equity,
                "end_equity": s.end_equity,
                "total_return_pct": s.total_return_pct,
                "cagr_pct": s.cagr_pct,
                "max_drawdown_pct": s.max_drawdown_pct,
            }
        )

    out_df = pd.DataFrame(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_df.to_csv(SUMMARY_FILE, index=False)

    print("\nSummary:")
    print("-" * 60)
    print(out_df.to_string(index=False))
    print("\nנשמר:", SUMMARY_FILE)
    print("=" * 60)


if __name__ == "__main__":
    main()
