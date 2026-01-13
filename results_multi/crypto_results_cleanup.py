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


def load_raw_trades(path: str) -> pd.DataFrame:
    """
    טוען את קובץ הטריידים בפורמט:
    ['timestamp', 'datetime', 'symbol', 'side', 'amount', 'price', 'cost']
    ומחזיר DataFrame נקי, עם datetime כ- datetime64.
    """
    df = pd.read_csv(path)
    expected = ["timestamp", "datetime", "symbol", "side", "amount", "price", "cost"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        print(f"⚠️ חסרות עמודות בקובץ טריידים: {missing}")
        print(f"עמודות קיימות: {list(df.columns)}")
        sys.exit(1)

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def build_pnl_from_trades(raw: pd.DataFrame) -> pd.DataFrame:
    """
    לוקח DataFrame בפורמט (timestamp, datetime, symbol, side, amount, price, cost)
    ובונה:
    - position, avg_price
    - pnl לכל שורת טרייד (רק בעת סגירת חלק מפוזיציה)
    - pnlpct = pnl / notional_closed
    שימו לב: זה חישוב פשוט per-symbol על בסיס FIFO ממוצע.
    """
    records = []
    # נרוץ סימבול-סימבול
    for symbol, g in raw.groupby("symbol", sort=False):
        pos = 0.0
        avg_price = 0.0

        for _, row in g.iterrows():
            side = str(row["side"]).upper()
            qty = float(row["amount"])
            price = float(row["price"])
            ts = row["timestamp"]
            dt = row["datetime"]
            cost = float(row["cost"]) if not pd.isna(row["cost"]) else qty * price

            trade_pnl = 0.0
            trade_pnlpct = 0.0

            # לונג/שורט לפי side
            if side == "BUY":
                # אם הפוזיציה הייתה שורט (pos < 0) – אנחנו סוגרים/מקטינים שורט
                if pos < 0:
                    # כמה נסגר?
                    close_size = min(abs(pos), qty)
                    # רווח בשורט: (entry_price - cover_price) * גודל
                    trade_pnl += (avg_price - price) * close_size
                    notional = close_size * abs(avg_price)
                    trade_pnlpct = trade_pnl / notional if notional != 0 else 0.0

                    pos += close_size  # פחות שורט
                    qty -= close_size

                    # אם נשאר עוד קנייה אחרי שסגרנו שורט, נפתח לונג על היתרה
                    if qty > 0:
                        # פותחים פוזיציה חדשה (לונג)
                        pos += qty
                        avg_price = price
                else:
                    # פוזיציה קיימת לונג או 0 – ממוצע מחיר
                    new_pos = pos + qty
                    if new_pos != 0:
                        avg_price = (avg_price * pos + price * qty) / new_pos
                    pos = new_pos

            elif side == "SELL":
                # אם הפוזיציה הייתה לונג (pos > 0) – אנחנו סוגרים/מקטינים לונג
                if pos > 0:
                    close_size = min(pos, qty)
                    trade_pnl += (price - avg_price) * close_size
                    notional = close_size * avg_price
                    trade_pnlpct = trade_pnl / notional if notional != 0 else 0.0

                    pos -= close_size
                    qty -= close_size

                    # אם נשארה כמות מעבר לסגירה – נפתח שורט על ההפרש
                    if qty > 0:
                        pos -= qty
                        avg_price = price
                else:
                    # פוזיציה 0 או שורט – נפתח/נגדיל שורט
                    new_pos = pos - qty
                    if new_pos != 0:
                        avg_price = (avg_price * abs(pos) + price * qty) / abs(new_pos)
                    pos = new_pos
            else:
                # לא BUY/SELL – מתעלמים
                pass

            records.append(
                {
                    "timestamp": ts,
                    "date": dt,
                    "symbol": symbol,
                    "side": side,
                    "qty": row["amount"],
                    "price": price,
                    "value": cost,
                    "position": pos,
                    "avg_price": avg_price,
                    "pnl": trade_pnl,
                    "pnlpct": trade_pnlpct,
                }
            )

    df = pd.DataFrame(records)
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

    raw_trades = load_raw_trades(TRADES_FILE)
    trades = build_pnl_from_trades(raw_trades)
    daily = parse_daily_csv(DAILY_FILE)

    print(f"✅ נטענו {len(raw_trades)} שורות מקור ו-{len(trades)} טריידים עם PnL, ו-{len(daily)} שורות דיילי.")

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
