import os
import sys
import pandas as pd
import numpy as np

TRIMMED_DAILY_FILE = "crypto_daily_summary_trimmed.csv"
TRIMMED_EQUITY_FILE = "crypto_equity_curve_trimmed.csv"
TRADES_FILE = "crypto_trades_clean.csv"
OUT_SUMMARY_FILE = "crypto_investor_summary.csv"

def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)

def load_data():
    ensure_file(TRIMMED_DAILY_FILE)
    ensure_file(TRIMMED_EQUITY_FILE)
    ensure_file(TRADES_FILE)

    daily = pd.read_csv(TRIMMED_DAILY_FILE)
    equity = pd.read_csv(TRIMMED_EQUITY_FILE)
    trades = pd.read_csv(TRADES_FILE)

    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    equity["date"] = pd.to_datetime(equity["date"], errors="coerce")
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")

    return daily, equity, trades

def compute_stats(daily: pd.DataFrame, equity: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    stats = {}

    # טווח תאריכים
    stats["start_date"] = equity["date"].min()
    stats["end_date"] = equity["date"].max()

    # הון
    start_eq = equity["equity"].iloc[0]
    end_eq = equity["equity"].iloc[-1]
    stats["start_equity"] = start_eq
    stats["end_equity"] = end_eq
    stats["total_return_pct"] = (end_eq / start_eq - 1.0) * 100.0 if start_eq != 0 else np.nan

    # drawdown מתוך daily_trimmed
    daily = daily.copy()
    daily["equity"] = daily["crypto_total"]
    daily["cum_max"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / daily["cum_max"] - 1.0
    stats["max_drawdown_pct"] = daily["drawdown"].min() * 100.0

    dd_idx = daily["drawdown"].idxmin()
    stats["max_dd_date"] = daily.loc[dd_idx, "date"]
    stats["max_dd_equity"] = daily.loc[dd_idx, "equity"]

    # סטטיסטיקות טריידים
    valid_trades = trades.dropna(subset=["pnl"])
    wins = valid_trades[valid_trades["pnl"] > 0]
    losses = valid_trades[valid_trades["pnl"] < 0]

    stats["num_trades"] = len(valid_trades)
    stats["num_wins"] = len(wins)
    stats["num_losses"] = len(losses)
    stats["win_rate_pct"] = (len(wins) / len(valid_trades) * 100.0) if len(valid_trades) > 0 else 0.0
    stats["avg_win"] = wins["pnl"].mean() if len(wins) > 0 else 0.0
    stats["avg_loss"] = losses["pnl"].mean() if len(losses) > 0 else 0.0
    stats["total_pnl"] = valid_trades["pnl"].sum()

    stats_df = pd.DataFrame([stats])
    return stats_df

def main():
    daily, equity, trades = load_data()
    stats_df = compute_stats(daily, equity, trades)

    stats_df.to_csv(OUT_SUMMARY_FILE, index=False)
    print(f"✅ נשמר קובץ סיכום למשקיעים: {OUT_SUMMARY_FILE}")
    print(stats_df.T)

if __name__ == "__main__":
    main()
