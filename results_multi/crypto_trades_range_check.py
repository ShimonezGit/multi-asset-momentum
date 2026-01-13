import os
import sys
import pandas as pd

TRADES_FILE = "crypto_trades_clean.csv"
DAILY_FILE = "crypto_daily_summary.csv"

def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)

def main():
    ensure_file(TRADES_FILE)
    ensure_file(DAILY_FILE)

    trades = pd.read_csv(TRADES_FILE)
    daily = pd.read_csv(DAILY_FILE)

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")

    first_trade = trades["date"].min()
    last_trade = trades["date"].max()

    first_daily = daily["date"].min()
    last_daily = daily["date"].max()

    print("=== טווח תאריכים – טריידים ===")
    print(f"טרייד ראשון: {first_trade}")
    print(f"טרייד אחרון: {last_trade}")

    print("\n=== טווח תאריכים – דיילי ===")
    print(f"יום ראשון בדיילי: {first_daily}")
    print(f"יום אחרון בדיילי: {last_daily}")

    print("\nאם first_daily < first_trade זה אומר שהיו חודשים 'שקטים' בלי טריידים בתחילת התקופה.")

if __name__ == "__main__":
    main()
