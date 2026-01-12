#!/usr/bin/env python3
# coding: utf-8

import pandas as pd

# קרא טריידים מבקטסט
backtest_trades = pd.read_csv('results_multi/crypto_trades.csv')

# קרא טריידים מpaper
paper_trades = pd.read_csv('results_multi/crypto_paper_trades.csv')

# סינון רק 2024
backtest_trades['datetime'] = pd.to_datetime(backtest_trades['datetime'])
backtest_2024 = backtest_trades[backtest_trades['datetime'].dt.year == 2024]

paper_trades['datetime'] = pd.to_datetime(paper_trades['datetime'])
paper_2024 = paper_trades[paper_trades['datetime'].dt.year == 2024]

print("=== השוואת טריידים 2024 ===")
print(f"Backtest: {len(backtest_2024)} טריידים")
print(f"Paper: {len(paper_2024)} טריידים")
print(f"הפרש: {len(backtest_2024) - len(paper_2024)} טריידים\n")

# סימבולים שנסחרו
backtest_symbols = set(backtest_2024['symbol'].unique())
paper_symbols = set(paper_2024['symbol'].unique())

print("סימבולים בבקטסט:", sorted(backtest_symbols))
print("\nסימבולים ב-Paper:", sorted(paper_symbols))
print("\nרק בבקטסט:", sorted(backtest_symbols - paper_symbols))
print("רק ב-Paper:", sorted(paper_symbols - backtest_symbols))

# פילוח לפי סימבול
print("\n=== פילוח טריידים לפי סימבול ===")
print("\nBacktest:")
print(backtest_2024['symbol'].value_counts())
print("\nPaper:")
print(paper_2024['symbol'].value_counts())
