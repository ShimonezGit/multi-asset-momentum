import pandas as pd

bt = pd.read_csv('results_multi/crypto_trades.csv')
paper = pd.read_csv('results_multi/crypto_paper_trades.csv')

# קח את 5 ה-BUY הראשונים של כל אחד
print("=== 5 קניות ראשונות - Backtest ===")
bt_buys = bt[bt['side'] == 'BUY'].head(5)
print(bt_buys[['date', 'symbol', 'qty', 'price', 'value']].to_string(index=False))

print("\n=== 5 קניות ראשונות - Paper ===")
paper_buys = paper[paper['side'] == 'BUY'].head(5)
print(paper_buys[['datetime', 'symbol', 'amount', 'price', 'cost']].to_string(index=False))

# בדוק את הסכום הממוצע
print("\n=== סכום ממוצע לקניה ===")
bt_avg = bt[bt['side'] == 'BUY']['value'].mean()
paper_avg = paper[paper['side'] == 'BUY']['cost'].mean()

print(f"Backtest: ${bt_avg:,.2f} בממוצע לקניה")
print(f"Paper:    ${paper_avg:,.2f} בממוצע לקניה")
print(f"הפרש:    ${paper_avg - bt_avg:,.2f} ({(paper_avg/bt_avg - 1)*100:+.1f}%)")

# בדוק את הסכום המקסימלי
print("\n=== קניה מקסימלית ===")
bt_max = bt[bt['side'] == 'BUY']['value'].max()
paper_max = paper[paper['side'] == 'BUY']['cost'].max()

print(f"Backtest: ${bt_max:,.2f}")
print(f"Paper:    ${paper_max:,.2f}")

print("\n" + "="*60)
print("אם Paper קונה בממוצע יותר בכל טרייד - זה מסביר את ההפרש!")
