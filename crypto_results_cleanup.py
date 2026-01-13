import os
import sys
import pandas as pd
import numpy as np

# --------------------------------------------------
# קונפיגורציה בסיסית
# --------------------------------------------------
TRADES_FILE = "crypto_trades_2022-2025.csv"
DAILY_FILE = "crypto_daily_summary.csv"

CLEAN_TRADES_FILE = "crypto_trades_clean.csv"
CLEAN_DAILY_FILE = "crypto_daily_summary_clean.csv"
STATS_FILE = "crypto_stats_summary.csv"


def ensure_file_exists(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)


def parse_trades_csv(path: str) -> pd.DataFrame:
    """
    טוען את קובץ הטריידים ומחזיר DataFrame עם עמודות נורמליות:
    date, symbol, side, qty, price, value, pnl, pnlpct
    """
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()

    if "," in first_line:
        df = pd.read_csv(path)
    else:
        df = pd.read_fwf(path, header=0)
        rename_dict = {}
        for c in df.columns:
            low = str(c).lower().strip()
            if "date" in low and "symbol" not in low:
                rename_dict[c] = "date"
            elif "symbol" in low:
                rename_dict[c] = "symbol"
            elif "side" in low:
                rename_dict[c] = "side"
            elif "qty" in low or "quantity" in low:
                rename_dict[c] = "qty"
            elif "price" in low:
                rename_dict[c] = "price"
            elif "value" in low:
                rename_dict[c] = "value"
            elif low.startswith("pnlpct") or "pnlpct" in low:
                rename_dict[c] = "pnlpct"
            elif low.startswith("pnl") and "pct" not in low:
                rename_dict[c] = "pnl"
        df = df.rename(columns=rename_dict)

    required_cols = ["date", "symbol", "side", "qty", "price", "value", "pnl", "pnlpct"]
    for col in required_cols:
        if col not in df.columns:
            print(f"⚠️ חסרה עמודה בטריידים: {col}")
            print(f"עמודות קיימות: {list(df.columns)}")
            sys.exit(1)

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    df["pnlpct"] = pd.to_numeric(df["pnlpct"], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    return df


def parse_daily_csv(path: str) -> pd.DataFrame:
    """
    טוען את crypto_daily_summary.csv ומחזיר:
    date, crypto_total, crypto_pnl, crypto_benchmark
    """
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()

    if "," in first_line:
        df = pd.read_csv(path)
    else:
        df = pd.read_fwf(path, header=0)

    rename_dict = {}
    for c in df.columns:
        low = str(c).lower().strip()
        if low.startswith("date"):
            rename_dict[c] = "date"
        elif "cryptototal" in low or ("total" in low and "crypto" in low):
            rename_dict[c] = "crypto_total"
        elif "cryptopnl" in low or ("pnl" in low and "crypto" in low):
            rename_dict[c] = "crypto_pnl"
        elif "cryptobenchmark" in low or ("benchmark" in low and "crypto" in low):
            rename_dict[c] = "crypto_benchmark"

    df = df.rename(columns=rename_dict)

    rename_if_needed = {
        "cryptototal": "crypto_total",
        "cryptopnl": "crypto_pnl",
        "cryptobenchmark": "crypto_benchmark",
    }
    df = df.rename(columns=rename_if_needed)

    required_cols = ["date", "crypto_total", "crypto_pnl", "crypto_benchmark"]
    for col in required_cols:
        if col not in df.columns:
            print(f"⚠️ חסרה עמודה בדיילי סאמרי: {col}")
            print(f"עמודות קיימות: {list(df.columns)}")
            sys.exit(1)

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["crypto_total"] = pd.to_numeric(df["crypto_total"], errors="coerce")
    df["crypto_pnl"] = pd.to_numeric(df["crypto_pnl"], errors="coerce")
    df["crypto_benchmark"] = pd.to_numeric(df["crypto_benchmark"], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    return df


def compute_equity_stats(trades: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """
    סטטיסטיקות בסיסיות לקריפטו:
    win rate, avg win/loss, total pnl, max drawdown, total return.
    """
    stats = {}

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

    daily = daily.dropna(subset=["crypto_total"]).copy()
    daily["equity"] = daily["crypto_total"]
    daily["cum_max"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / daily["cum_max"] - 1.0
    max_dd = daily["drawdown"].min() if len(daily) > 0 else 0.0
    stats["max_drawdown_pct"] = max_dd * 100.0

    if len(daily) > 0:
        dd_idx = daily["drawdown"].idxmin()
        stats["max_dd_date"] = daily.loc[dd_idx, "date"]
        stats["max_dd_equity"] = daily.loc[dd_idx, "equity"]
    else:
        stats["max_dd_date"] = pd.NaT
        stats["max_dd_equity"] = np.nan

    stats["start_date"] = daily["date"].iloc[0] if len(daily) > 0 else pd.NaT
    stats["end_date"] = daily["date"].iloc[-1] if len(daily) > 0 else pd.NaT
    stats["start_equity"] = daily["equity"].iloc[0] if len(daily) > 0 else np.nan
    stats["end_equity"] = daily["equity"].iloc[-1] if len(daily) > 0 else np.nan
    stats["total_return_pct"] = (
        (stats["end_equity"] / stats["start_equity"] - 1.0) * 100.0
        if len(daily) > 0 and pd.notna(stats["start_equity"]) and stats["start_equity"] != 0
        else np.nan
    )

    stats_df = pd.DataFrame([stats])
    return stats_df


def main():
    print("🔧 טוען נתונים קיימים של קריפטו...")

    ensure_file_exists(TRADES_FILE)
    ensure_file_exists(DAILY_FILE)

    trades = parse_trades_csv(TRADES_FILE)
    daily = parse_daily_csv(DAILY_FILE)

    print(f"✅ נטענו {len(trades)} טריידים ו-{len(daily)} שורות דיילי.")

    trades.to_csv(CLEAN_TRADES_FILE, index=False)
    daily.to_csv(CLEAN_DAILY_FILE, index=False)

    stats_df = compute_equity_stats(trades, daily)
    stats_df.to_csv(STATS_FILE, index=False)

    print("✅ נשמרו קבצים נקיים:")
    print(f"   - {CLEAN_TRADES_FILE}")
    print(f"   - {CLEAN_DAILY_FILE}")
    print(f"   - {STATS_FILE}")
    print("🎯 מוכן לשלב הבא.")
    

if __name__ == "__main__":
    main()
