import pandas as pd
import numpy as np

# טען את הדאטה המלא
print("=== בדיקת 09/04/2024 - למה Paper נכנס והBacktest לא? ===\n")

# סימולציה של הבדיקות באותו יום
# צריך לבדוק:
# 1. BTC מעל MA100? (trend_up)
# 2. DOGE momentum > 10%?

# בואו נראה מה היה במחירי BTC סביב התאריך הזה
btc_dates = [
    "2024-03-10", "2024-03-20", "2024-03-31",  # לחישוב MA100
    "2024-04-08", "2024-04-09", "2024-04-10"   # הימים הקריטיים
]

print("BTC צריך להיות מעל MA100 ב-09/04 כדי שהטרייד יקרה")
print("DOGE צריך momentum > 10% (שינוי 20 יום)")
print()

# בדוק את קבצי ה-equity
bt_eq = pd.read_csv('results_multi/crypto_equity_curve.csv')
bt_eq['date'] = pd.to_datetime(bt_eq['date'])

paper_eq = pd.read_csv('results_multi/crypto_paper_equity.csv')
paper_eq['date'] = pd.to_datetime(paper_eq['date'])

# מצא מתי התחיל לזוז
first_bt_change = bt_eq[bt_eq['equity'] != 100000.0]['date'].min()
first_paper_change = paper_eq[paper_eq['equity'] != 100000.0]['date'].min()

print(f"Backtest - equity ראשון שונה מ-100K: {first_bt_change.date()}")
print(f"Paper - equity ראשון שונה מ-100K: {first_paper_change.date()}")
print(f"\nהפרש: {(first_bt_change - first_paper_change).days} יום")

# בדוק את ה-benchmark equity
print(f"\nBacktest benchmark (BTC) equity ב-09/04: ${bt_eq[bt_eq['date'] == '2024-04-09']['benchmark_equity'].values[0]:,.2f}")
print(f"Backtest benchmark (BTC) equity ב-10/04: ${bt_eq[bt_eq['date'] == '2024-04-10']['benchmark_equity'].values[0]:,.2f}")

print("\n" + "="*60)
print("מסקנה:")
print("Paper נכנס ב-09/04, Backtest ב-10/04")
print("זה אומר שהסיגנל של Paper היה מוקדם ביום אחד.")
print("זה יכול להיות בגלל:")
print("  1. הבדל בחישוב MA100 (rounding/precision)")
print("  2. הבדל בחישוב Momentum")
print("  3. הבדל בסדר החישובים")
