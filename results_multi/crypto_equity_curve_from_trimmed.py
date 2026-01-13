import os
import sys
import pandas as pd

TRIMMED_DAILY_FILE = "crypto_daily_summary_trimmed.csv"
OUT_EQUITY_FILE = "crypto_equity_curve_trimmed.csv"

def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)

def main():
    ensure_file(TRIMMED_DAILY_FILE)

    daily = pd.read_csv(TRIMMED_DAILY_FILE)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")

    if "crypto_total" not in daily.columns:
        print(f"⚠️ בעיה: לא נמצאה עמודה crypto_total ב-{TRIMMED_DAILY_FILE}")
        print(f"עמודות קיימות: {list(daily.columns)}")
        sys.exit(1)

    equity = daily[["date", "crypto_total"]].copy()
    equity = equity.rename(columns={"crypto_total": "equity"})
    equity = equity.sort_values("date").reset_index(drop=True)

    equity.to_csv(OUT_EQUITY_FILE, index=False)
    print(f"✅ נשמר קובץ עקומת הון חתוכה ל-{OUT_EQUITY_FILE}")
    print(f"מספר נקודות בעקומה: {len(equity)}")
    print(f"טווח תאריכים: {equity['date'].min()} -> {equity['date'].max()}")

if __name__ == "__main__":
    main()
