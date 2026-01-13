import os
import sys
import pandas as pd

DAILY_FILE = "crypto_daily_summary.csv"
TRADES_FILE = "crypto_trades_clean.csv"
OUT_FILE = "crypto_daily_summary_trimmed.csv"

def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)

def main():
    ensure_file(DAILY_FILE)
    ensure_file(TRADES_FILE)

    daily = pd.read_csv(DAILY_FILE)
    trades = pd.read_csv(TRADES_FILE)

    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")

    first_trade = trades["date"].min()

    trimmed = daily[daily["date"] >= first_trade].copy()
    trimmed = trimmed.sort_values("date").reset_index(drop=True)

    print(f"טרייד ראשון: {first_trade}")
    print(f"מספר שורות לפני חיתוך: {len(daily)}, אחרי חיתוך: {len(trimmed)}")

    trimmed.to_csv(OUT_FILE, index=False)
    print(f"✅ נשמר קובץ equity חתוך ל-{OUT_FILE}")

if __name__ == "__main__":
    main()
