import pandas as pd
import numpy as np

bt_eq = pd.read_csv('results_multi/crypto_equity_curve.csv')
paper_eq = pd.read_csv('results_multi/crypto_paper_equity.csv')

bt_eq['date'] = pd.to_datetime(bt_eq['date'])
paper_eq['date'] = pd.to_datetime(paper_eq['date'])

# מיזוג
merged = bt_eq[['date', 'equity']].merge(paper_eq[['date', 'equity']], on='date', suffixes=('_bt', '_paper'))
merged['diff'] = merged['equity_paper'] - merged['equity_bt']
merged['month'] = merged['date'].dt.to_period('M')

# סוף כל חודש
monthly = merged.groupby('month').last()

print("=== התפתחות ההפרש חודש אחר חודש ===\n")
print(f"{'חודש':<10} {'Backtest':>12} {'Paper':>12} {'הפרש':>12} {'% יתרון':>10}")
print("="*60)

for month in monthly.index:
    bt = monthly.loc[month, 'equity_bt']
    paper = monthly.loc[month, 'equity_paper']
    diff = monthly.loc[month, 'diff']
    pct = (paper / bt - 1) * 100
    print(f"{month!s:<10} ${bt:>11,.0f} ${paper:>11,.0f} ${diff:>11,.0f} {pct:>9.1f}%")

print("\n" + "="*60)
print("איפה הפער גדל הכי הרבה?")

monthly['diff_change'] = monthly['diff'].diff()
biggest_gap_month = monthly['diff_change'].idxmax()
biggest_gap = monthly.loc[biggest_gap_month, 'diff_change']

print(f"חודש עם הגידול הגדול ביותר בפער: {biggest_gap_month}")
print(f"הפער גדל ב: ${biggest_gap:,.0f}")
