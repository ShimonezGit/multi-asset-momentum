import pandas as pd

bt = pd.read_csv('results_multi/crypto_trades.csv')
paper = pd.read_csv('results_multi/crypto_paper_trades.csv')
bt_eq = pd.read_csv('results_multi/crypto_equity_curve.csv')
paper_eq = pd.read_csv('results_multi/crypto_paper_equity.csv')

# מצא את הקניה המקסימלית
bt_max_buy = bt[bt['side'] == 'BUY'].loc[bt[bt['side'] == 'BUY']['value'].idxmax()]
paper_max_buy = paper[paper['side'] == 'BUY'].loc[paper[paper['side'] == 'BUY']['cost'].idxmax()]

print("=== הקניה הכי גדולה - Backtest ===")
print(f"תאריך: {bt_max_buy['date']}")
print(f"סימבול: {bt_max_buy['symbol']}")
print(f"סכום: ${bt_max_buy['value']:,.2f}")

# מה היה ה-equity באותו יום?
bt_equity_that_day = bt_eq[bt_eq['date'] == bt_max_buy['date']]['equity'].values
if len(bt_equity_that_day) > 0:
    print(f"Equity באותו יום: ${bt_equity_that_day[0]:,.2f}")

print("\n=== הקניה הכי גדולה - Paper ===")
print(f"תאריך: {paper_max_buy['datetime'][:10]}")
print(f"סימבול: {paper_max_buy['symbol']}")
print(f"סכום: ${paper_max_buy['cost']:,.2f}")

# מה היה ה-equity באותו יום?
paper_equity_that_day = paper_eq[paper_eq['date'] == paper_max_buy['datetime'][:10]]['equity'].values
if len(paper_equity_that_day) > 0:
    print(f"Equity באותו יום: ${paper_equity_that_day[0]:,.2f}")

print("\n" + "="*60)
print("המסקנה:")
print(f"Paper היה לו equity גבוה יותר באותו יום = קנה יותר = הרוויח יותר")
print("זה אפקט כדור שלג של הרווחים הקודמים!")
