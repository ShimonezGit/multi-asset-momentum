import pandas as pd

bt = pd.read_csv('results_multi/crypto_trades.csv')
paper = pd.read_csv('results_multi/crypto_paper_trades.csv')

print("=== Backtest - פילוח לפי סימבול ===")
print(bt['symbol'].value_counts().sort_index())

print("\n=== Paper - פילוח לפי סימבול ===")
print(paper['symbol'].value_counts().sort_index())

print("\n=== Backtest - פילוח לפי Side ===")
print(bt['side'].value_counts())

print("\n=== Paper - פילוח לפי Side ===")
print(paper['side'].value_counts())

print("\n=== סיכום ===")
print(f"Backtest: {len(bt)} טריידים")
print(f"Paper: {len(paper)} טריידים")
print(f"הפרש: {len(paper) - len(bt)} טריידים")
