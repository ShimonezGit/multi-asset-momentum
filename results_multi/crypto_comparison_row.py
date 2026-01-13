import os
import sys
import pandas as pd

INVESTOR_FILE = "crypto_investor_summary.csv"
OUT_FILE = "crypto_comparison_row.csv"

def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)

def main():
    ensure_file(INVESTOR_FILE)
    stats = pd.read_csv(INVESTOR_FILE)

    # מוסיפים מטא-דאטה בסיסית להשוואה
    stats["asset_class"] = "Crypto"
    stats["strategy_name"] = "Multi-Asset Crypto Core"
    stats["env"] = "Backtest"

    # מסדרים עמודות ל-comparison
    cols_order = [
        "asset_class",
        "strategy_name",
        "env",
        "start_date",
        "end_date",
        "start_equity",
        "end_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "num_trades",
        "win_rate_pct",
        "avg_win",
        "avg_loss",
        "total_pnl",
    ]

    # דואג שכל העמודות קיימות (אם נוספו עוד שדות בעתיד – פשוט יתעלמו כאן)
    for c in cols_order:
        if c not in stats.columns:
            print(f"⚠️ חסרה עמודה ב-investor summary: {c}")
            print(f"עמודות קיימות: {list(stats.columns)}")
            sys.exit(1)

    row = stats[cols_order].copy()
    row.to_csv(OUT_FILE, index=False)
    print(f"✅ נשמר קובץ שורה ל-comparison: {OUT_FILE}")
    print(row.T)

if __name__ == "__main__":
    main()
