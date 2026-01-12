#!/usr/bin/env python3
# coding: utf-8

"""
multi_asset_paper.py

השוואת 3 מנועי Paper (Crypto / US / IL) כל אחד על 100K,
ובתוך אותו סקריפט – סימולציה של תיק מנועים משולב (99K, 33K לכל מנוע)
עם אלוקציה חכמה דו-שבועית על בסיס ביצועי 20 הימים האחרונים.

נתוני ה-Paper לפי השמות הבאים:
- Crypto: results_multi/crypto_paper_equity.csv
- US:     results_multi/us_paper_equity.csv
- IL:     results_multi/il_paper_equity.csv
"""

import os
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


# -----------------------
# קונפיגורציה
# -----------------------

RESULTS_DIR = "results_multi"

CRYPTO_EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_EQUITY_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
IL_EQUITY_FILE = os.path.join(RESULTS_DIR, "il_paper_equity.csv")

# הון התחלתי לכל מנוע בבדיקת ההשוואה (זה כבר baked in בקבצי ה-Equity)
INITIAL_CAPITAL_PER_BOT = 100000.0

# תיק משולב
TOTAL_PORTFOLIO = 99000.0
LOOKBACK_DAYS_ALLOC = 20        # ביצוע חישוב ביצועי 20 ימים אחרונים
REBALANCE_EVERY_N_DAYS = 10     # ריבאלנס דו-שבועי (בערך)

MULTI_EQUITY_FILE = os.path.join(RESULTS_DIR, "multi_asset_paper_equity.csv")


@dataclass
class StrategyStats:
    name: str
    start_equity: float
    end_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float


# -----------------------
# פונקציות עזר למדדים
# -----------------------

def compute_max_drawdown(equity: pd.Series) -> float:
    """חישוב Max Drawdown באחוזים."""
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min() * 100.0)


def compute_cagr(equity: pd.Series) -> float:
    """חישוב CAGR באחוזים."""
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


def load_equity_file(path: str, name: str) -> pd.Series:
    """טעינת קובץ equity פשוט (date,equity) לסדרה עם אינדקס datetime."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"לא נמצא קובץ equity ל-{name}: {path}")
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError(f"קובץ equity ל-{name} חייב לכלול עמודות 'date' ו-'equity'.")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df = df.set_index("date")
    return df["equity"].astype(float)


def analyze_single_strategy(equity: pd.Series, name: str) -> StrategyStats:
    """חישוב מדדים למנוע אחד."""
    start_eq = float(equity.iloc[0])
    end_eq = float(equity.iloc[-1])
    total_return_pct = (end_eq / start_eq - 1.0) * 100.0 if start_eq > 0 else 0.0
    max_dd = compute_max_drawdown(equity)
    cagr = compute_cagr(equity)
    return StrategyStats(
        name=name,
        start_equity=start_eq,
        end_equity=end_eq,
        total_return_pct=total_return_pct,
        cagr_pct=cagr,
        max_drawdown_pct=max_dd,
    )


# -----------------------
# אלוקציה דו-שבועית בין מנועים
# -----------------------

def compute_biweekly_allocation(
    combined_df: pd.DataFrame,
    equity_cols: Tuple[str, str, str],
    lookback_days: int,
    rebalance_every_n_days: int,
    starting_capitals: Dict[str, float],
) -> pd.DataFrame:
    """
    סימולציה של תיק מנועים משולב:
    - combined_df: DataFrame עם עמודות equity לכל מנוע.
    - equity_cols: שמות העמודות (Crypto, US, IL).
    - starting_capitals: dict עם equity התחלתי לכל מנוע בתיק (לדוגמה 33,000).
    """
    crypto_col, us_col, il_col = equity_cols

    dates = combined_df.index
    # compute daily returns לכל מנוע
    rets_crypto = combined_df[crypto_col].pct_change().fillna(0.0)
    rets_us = combined_df[us_col].pct_change().fillna(0.0)
    rets_il = combined_df[il_col].pct_change().fillna(0.0)

    # מצב התיק ברמת מנוע
    bot_weights = {"CRYPTO": 1.0/3.0, "US": 1.0/3.0, "IL": 1.0/3.0}
    bot_equity = {
        "CRYPTO": starting_capitals["CRYPTO"],
        "US": starting_capitals["US"],
        "IL": starting_capitals["IL"],
    }

    portfolio_records = []

    for i, dt in enumerate(dates):
        # ריבאלנס דו-שבועי: כל N ימים אחרי שיש מספיק היסטוריה
        if i > lookback_days and (i % rebalance_every_n_days == 0):
            window_slice = slice(dates[i - lookback_days], dates[i - 1])

            # חישוב ביצועי תקופה לכל מנוע
            def period_return(series: pd.Series) -> float:
                sub = series.loc[window_slice]
                if len(sub) == 0:
                    return 0.0
                # compound return over window
                return float((1.0 + sub).prod() - 1.0)

            cr_ret = period_return(rets_crypto)
            us_ret = period_return(rets_us)
            il_ret = period_return(rets_il)

            perf = {
                "CRYPTO": cr_ret,
                "US": us_ret,
                "IL": il_ret,
            }
            ranked = sorted(perf.items(), key=lambda x: x[1], reverse=True)

            # הקצאה 50/30/20 לפי ביצועי חלון
            bot_weights = {
                ranked[0][0]: 0.5,
                ranked[1][0]: 0.3,
                ranked[2][0]: 0.2,
            }

        # עדכון equity לכל מנוע לפי daily return שלו
        bot_equity["CRYPTO"] *= (1.0 + float(rets_crypto.iloc[i]))
        bot_equity["US"] *= (1.0 + float(rets_us.iloc[i]))
        bot_equity["IL"] *= (1.0 + float(rets_il.iloc[i]))

        # סך הון
        total_equity = bot_equity["CRYPTO"] + bot_equity["US"] + bot_equity["IL"]

        portfolio_records.append(
            {
                "date": dt.date().isoformat(),
                "equity": total_equity,
                "crypto_equity": bot_equity["CRYPTO"],
                "us_equity": bot_equity["US"],
                "il_equity": bot_equity["IL"],
                "w_crypto": bot_weights["CRYPTO"],
                "w_us": bot_weights["US"],
                "w_il": bot_weights["IL"],
            }
        )

    out_df = pd.DataFrame(portfolio_records)
    out_df["date"] = pd.to_datetime(out_df["date"])
    out_df = out_df.set_index("date").sort_index()
    return out_df


# -----------------------
# main
# -----------------------

def main():
    print("=" * 60)
    print("Multi-Asset Paper Analysis – Crypto / US / IL")
    print("=" * 60)

    # טעינת עקומות הון לכל מנוע
    crypto_eq = load_equity_file(CRYPTO_EQUITY_FILE, "CRYPTO")
    us_eq = load_equity_file(US_EQUITY_FILE, "US")
    il_eq = load_equity_file(IL_EQUITY_FILE, "IL")

    # יישור תאריכים (אינטרסקציה בלבד – ימים שיש לכולם)
    combined = pd.DataFrame(
        {
            "crypto_equity": crypto_eq,
            "us_equity": us_eq,
            "il_equity": il_eq,
        }
    ).dropna()

    if combined.empty:
        raise RuntimeError("אין חיתוך משותף של תאריכים בין שלושת המנועים.")

    # אנליזה לכל מנוע ב-100K (מהקבצים הקיימים)
    stats_crypto = analyze_single_strategy(crypto_eq, "CRYPTO")
    stats_us = analyze_single_strategy(us_eq, "US")
    stats_il = analyze_single_strategy(il_eq, "IL")

    print("\nסיכום מנועים (100K כל אחד, לפי קבצי ה-Equity שלהם):")
    print("-" * 60)
    header = f"{'Name':<8} {'Start':>12} {'End':>12} {'Return%':>10} {'CAGR%':>10} {'MaxDD%':>10}"
    print(header)
    print("-" * 60)
    for s in [stats_crypto, stats_us, stats_il]:
        print(
            f"{s.name:<8} "
            f"{s.start_equity:>12,.0f} "
            f"{s.end_equity:>12,.0f} "
            f"{s.total_return_pct:>10.2f} "
            f"{s.cagr_pct:>10.2f} "
            f"{s.max_drawdown_pct:>10.2f}"
        )

    # תיק מנועים משולב – 33K לכל מנוע
    starting_capitals = {
        "CRYPTO": TOTAL_PORTFOLIO / 3.0,
        "US": TOTAL_PORTFOLIO / 3.0,
        "IL": TOTAL_PORTFOLIO / 3.0,
    }

    multi_df = compute_biweekly_allocation(
        combined_df=combined,
        equity_cols=("crypto_equity", "us_equity", "il_equity"),
        lookback_days=LOOKBACK_DAYS_ALLOC,
        rebalance_every_n_days=REBALANCE_EVERY_N_DAYS,
        starting_capitals=starting_capitals,
    )

    # שמירת עקומת הון של התיק המשולב
    os.makedirs(RESULTS_DIR, exist_ok=True)
    multi_df[["equity"]].to_csv(MULTI_EQUITY_FILE, index=True)

    # מדדים לתיק המשולב
    multi_stats = analyze_single_strategy(multi_df["equity"], "MULTI")

    print("\n" + "=" * 60)
    print("תיק מנועים משולב – 99K (33K לכל מנוע)")
    print("=" * 60)
    print(f"תקופה: {multi_df.index[0].date()} עד {multi_df.index[-1].date()}")
    print(f"Equity התחלתי: {multi_stats.start_equity:,.2f}")
    print(f"Equity סופי:   {multi_stats.end_equity:,.2f}")
    print(f"Total Return:  {multi_stats.total_return_pct:.2f}%")
    print(f"CAGR:          {multi_stats.cagr_pct:.2f}%")
    print(f"Max Drawdown:  {multi_stats.max_drawdown_pct:.2f}%")
    print(f"\nנשמר: {MULTI_EQUITY_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
