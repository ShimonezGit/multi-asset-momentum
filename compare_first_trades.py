import pandas as pd

bt = pd.read_csv('results_multi/crypto_trades.csv')
paper = pd.read_csv('results_multi/crypto_paper_trades.csv')

print("=== 10 טריידים ראשונים - Backtest ===")
print(bt[['date', 'symbol', 'side', 'qty', 'price', 'value']].head(10).to_string(index=False))

print("\n=== 10 טריידים ראשונים - Paper ===")
print(paper[['datetime', 'symbol', 'side', 'amount', 'price', 'cost']].head(10).to_string(index=False))

# בדיקת היום הראשון עם טרייד
print(f"\n=== יום ראשון עם טרייד ===")
print(f"Backtest: {bt['date'].iloc[0]}")
print(f"Paper:    {paper['datetime'].iloc[0][:10]}")

# סיכום לפי חודש
bt['month'] = pd.to_datetime(bt['date']).dt.to_period('M')
paper['month'] = pd.to_datetime(paper['datetime']).dt.to_period('M')

print(f"\n=== טריידים לפי חודש ===")
print("Backtest:")
print(bt.groupby('month').size())
print("\nPaper:")
print(paper.groupby('month').size())
