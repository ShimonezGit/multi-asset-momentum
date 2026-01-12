import pandas as pd

bt = pd.read_csv('results_multi/crypto_trades.csv')
paper = pd.read_csv('results_multi/crypto_paper_trades.csv')

# סנן רק נובמבר
bt['date'] = pd.to_datetime(bt['date'])
paper['datetime'] = pd.to_datetime(paper['datetime'])

bt_nov = bt[bt['date'].dt.month == 11]
paper_nov = paper[paper['datetime'].dt.month == 11]

print("=== נובמבר 2024 - החודש שעשה את ההפרש ===\n")

print(f"טריידים בנובמבר:")
print(f"  Backtest: {len(bt_nov)}")
print(f"  Paper:    {len(paper_nov)}")

print(f"\nסימבולים בנובמבר - Backtest:")
print(bt_nov['symbol'].value_counts())

print(f"\nסימבולים בנובמבר - Paper:")
print(paper_nov['symbol'].value_counts())

# בדוק PnL של מכירות בנובמבר
bt_sells = bt_nov[bt_nov['side'].isin(['SELL_EXIT', 'SELL_TRIM', 'SELL_REBAL'])]
paper_sells = paper_nov[paper_nov['side'] == 'SELL']

if 'pnl' in bt_sells.columns:
    bt_pnl = bt_sells['pnl'].sum()
    print(f"\nBacktest PnL בנובמבר: ${bt_pnl:,.2f}")

print(f"\n=== סיכום ===")
print("Paper סחר יותר ב:")
for sym in paper_nov['symbol'].value_counts().index[:5]:
    paper_count = len(paper_nov[paper_nov['symbol'] == sym])
    bt_sym_clean = sym.replace('/', '')
    bt_count = len(bt_nov[bt_nov['symbol'] == bt_sym_clean])
    diff = paper_count - bt_count
    if diff > 5:
        print(f"  {sym}: Paper {paper_count} vs Backtest {bt_count} (הפרש: +{diff})")
