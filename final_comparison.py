import pandas as pd

# טען נתונים
bt_eq = pd.read_csv('results_multi/crypto_equity_curve.csv')
paper_eq = pd.read_csv('results_multi/crypto_paper_equity.csv')
bt_trades = pd.read_csv('results_multi/crypto_trades.csv')
paper_trades = pd.read_csv('results_multi/crypto_paper_trades.csv')

print("="*60)
print("השוואה סופית: Backtest vs Paper (ללא BTC)")
print("="*60)

print("\n📊 Equity:")
print(f"  Backtest: ${bt_eq['equity'].iloc[0]:,.0f} → ${bt_eq['equity'].iloc[-1]:,.0f}")
print(f"  Paper:    ${paper_eq['equity'].iloc[0]:,.0f} → ${paper_eq['equity'].iloc[-1]:,.0f}")

bt_return = (bt_eq['equity'].iloc[-1] / bt_eq['equity'].iloc[0] - 1) * 100
paper_return = (paper_eq['equity'].iloc[-1] / paper_eq['equity'].iloc[0] - 1) * 100

print(f"\n📈 Return:")
print(f"  Backtest: +{bt_return:.2f}%")
print(f"  Paper:    +{paper_return:.2f}%")
print(f"  הפרש:    {paper_return - bt_return:+.2f}%")

print(f"\n🔄 Trades:")
print(f"  Backtest: {len(bt_trades)} טריידים")
print(f"  Paper:    {len(paper_trades)} טריידים")
print(f"  הפרש:    +{len(paper_trades) - len(bt_trades)} טריידים")

print("\n" + "="*60)
