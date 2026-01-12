#!/usr/bin/env python3
# coding: utf-8

# adaptive_allocation_paper.py
# Multi-Engine Paper: הקצאה אדפטיבית דו-שבועית בין Crypto ו-US בלבד (IL בחוץ)
# מבוסס על equity curves קיימות:
# - results_multi/crypto_paper_equity.csv
# - results_us_il_voo_ta125/us_voo_paperequity.csv
# יוצא:
# - results_multi/multi_adaptive_paper_equity.csv
# - results_multi/multi_adaptive_paper_summary.csv

import os
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd

# נתיבי תיקיות
RESULTS_DIR_MULTI = "results_multi"
RESULTS_DIR_US_IL = "results_us_il_voo_ta125"

# קבצי input בפועל אצלך
CRYPTO_EQUITY_FILE = os.path.join(RESULTS_DIR_MULTI, "crypto_paper_equity.csv")
US_EQUITY_FILE = os.path.join(RESULTS_DIR_US_IL, "us_voo_paperequity.csv")

# קבצי output – סנייק-קייס
ADAPTIVE_EQUITY_FILE = os.path.join(RESULTS_DIR_MULTI, "multi_adaptive_paper_equity.csv")
ADAPTIVE_SUMMARY_FILE = os.path.join(RESULTS_DIR_MULTI, "multi_adaptive_paper_summary.csv")

INITIAL_CAPITAL_PER_BOT = 100000.0
TOTAL_PORTFOLIO = 100000.0
LOOKBACK_DAYS_ALLOC = 20
REBALANCE_EVERY_N_DAYS = 10

WINNER_WEIGHT = 0.7
LOSER_WEIGHT = 0.3

@dataclass
class StrategyStats:
    name: str
    startequity: float
    endequity: float
    totalreturnpct: float
    cagrpct: float
    maxdrawdownpct: float

def load_equity_file(path: str, name: str) -> pd.Series:
    """טוען CSV עם date,equity ומחזיר Series של equity עם אינדקס תאריך."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"equity - {name} {path}")
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError(f"equity - {name} date/equity columns missing in {path}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df = df.set_index("date")
    return df["equity"].astype(float)

def compute_max_drawdown(equity: pd.Series) -> float:
    rollmax = equity.cummax()
    dd = (equity - rollmax) / rollmax
    return float(dd.min() * 100.0)

def compute_cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    startval = float(equity.iloc[0])
    endval = float(equity.iloc[-1])
    if startval == 0.0:
        return 0.0
    numdays = (equity.index[-1] - equity.index[0]).days
    if numdays <= 0:
        return 0.0
    years = numdays / 365.25
    cagr = (endval / startval) ** (1.0 / years) - 1.0
    return float(cagr * 100.0)

def analyze_single_strategy(equity: pd.Series, name: str) -> StrategyStats:
    starteq = float(equity.iloc[0])
    endeq = float(equity.iloc[-1])
    totalreturnpct = (endeq / starteq - 1.0) * 100.0 if starteq != 0 else 0.0
    maxdd = compute_max_drawdown(equity)
    cagr = compute_cagr(equity)
    return StrategyStats(
        name=name,
        startequity=starteq,
        endequity=endeq,
        totalreturnpct=totalreturnpct,
        cagrpct=cagr,
        maxdrawdownpct=maxdd,
    )

def compute_biweekly_adaptive_allocation(
    combined_df: pd.DataFrame,
    equity_cols: Tuple[str, str],
    lookback_days: int,
    rebalance_every_n_days: int,
    starting_capitals: Dict[str, float],
) -> pd.DataFrame:
    crypto_col, us_col = equity_cols
    dates = combined_df.index

    rets_crypto = combined_df[crypto_col].pct_change().fillna(0.0)
    rets_us = combined_df[us_col].pct_change().fillna(0.0)

    bot_weights = {"CRYPTO": 0.5, "US": 0.5}
    bot_equity = {
        "CRYPTO": float(starting_capitals["CRYPTO"]),
        "US": float(starting_capitals["US"]),
    }

    portfolio_records = []

    for i, dt in enumerate(dates):
        if i >= lookback_days and (i % rebalance_every_n_days == 0):
            window_slice = dates[i - lookback_days : i]

            def period_return(series: pd.Series) -> float:
                sub = series.loc[window_slice]
                if len(sub) == 0:
                    return 0.0
                return float((1.0 + sub).prod() - 1.0)

            cr_ret = period_return(rets_crypto)
            us_ret = period_return(rets_us)

            perf = {"CRYPTO": cr_ret, "US": us_ret}
            ranked = sorted(perf.items(), key=lambda x: x[1], reverse=True)

            winner_name = ranked[0][0]
            loser_name = ranked[1][0]
            bot_weights[winner_name] = WINNER_WEIGHT
            bot_weights[loser_name] = LOSER_WEIGHT

        bot_equity["CRYPTO"] *= float(1.0 + rets_crypto.iloc[i])
        bot_equity["US"] *= float(1.0 + rets_us.iloc[i])

        total_equity = bot_equity["CRYPTO"] + bot_equity["US"]

        portfolio_records.append(
            {
                "date": dt.date().isoformat(),
                "equity": total_equity,
                "cryptoequity": bot_equity["CRYPTO"],
                "usequity": bot_equity["US"],
                "w_crypto": bot_weights["CRYPTO"],
                "w_us": bot_weights["US"],
            }
        )

    out_df = pd.DataFrame(portfolio_records)
    out_df["date"] = pd.to_datetime(out_df["date"])
    out_df = out_df.set_index("date").sort_index()
    return out_df

def main() -> None:
    print("-" * 60)
    print("Adaptive Multi-Engine Paper: Crypto + US (IL excluded)")
    print("-" * 60)

    crypto_eq = load_equity_file(CRYPTO_EQUITY_FILE, "CRYPTO")
    us_eq = load_equity_file(US_EQUITY_FILE, "US_VOO")

    combined = pd.DataFrame(
        {
            "cryptoequity": crypto_eq,
            "usequity": us_eq,
        }
    ).dropna()

    if combined.empty:
        raise RuntimeError("אין חיתוך תאריכים משותף בין Crypto ל-US.")

    print(f"Date range: {combined.index[0].date()} to {combined.index[-1].date()}")
    print(f"Initial per-bot equity (logical): {INITIAL_CAPITAL_PER_BOT:,.0f}")
    print(f"Total portfolio used in adaptive layer: {TOTAL_PORTFOLIO:,.0f}")
    print("-" * 60)

    starting_capitals = {
        "CRYPTO": TOTAL_PORTFOLIO / 2.0,
        "US": TOTAL_PORTFOLIO / 2.0,
    }

    multi_df = compute_biweekly_adaptive_allocation(
        combined_df=combined,
        equity_cols=("cryptoequity", "usequity"),
        lookback_days=LOOKBACK_DAYS_ALLOC,
        rebalance_every_n_days=REBALANCE_EVERY_N_DAYS,
        starting_capitals=starting_capitals,
    )

    os.makedirs(RESULTS_DIR_MULTI, exist_ok=True)
    multi_df[["equity"]].to_csv(ADAPTIVE_EQUITY_FILE, index=True)

    stats_multi = analyze_single_strategy(multi_df["equity"], "MULTI_ADAPTIVE")
    rows = [
        {
            "name": stats_multi.name,
            "startequity": stats_multi.startequity,
            "endequity": stats_multi.endequity,
            "totalreturnpct": stats_multi.totalreturnpct,
            "cagrpct": stats_multi.cagrpct,
            "maxdrawdownpct": stats_multi.maxdrawdownpct,
        }
    ]
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(ADAPTIVE_SUMMARY_FILE, index=False)

    print("Adaptive Multi summary:")
    print(summary_df.to_string(index=False))
    print(f"Wrote equity to {ADAPTIVE_EQUITY_FILE}")
    print(f"Wrote summary to {ADAPTIVE_SUMMARY_FILE}")
    print("-" * 60)

if __name__ == "__main__":
    main()
