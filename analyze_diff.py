#!/usr/bin/env python3
# coding: utf-8
"""
analyze_diff.py
מנתח את ההפרשים בין Backtest ל-Paper
"""

import pandas as pd

def main():
    # טען שני הקבצים
    print("טוען קבצים...")
    backtest = pd.read_csv('results_multi/crypto_equity_curve.csv')
    paper = pd.read_csv('results_multi/crypto_paper_equity.csv')

    backtest['date'] = pd.to_datetime(backtest['date'])
    paper['date'] = pd.to_datetime(paper['date'])

    # מיזוג
    merged = backtest[['date', 'equity']].merge(
        paper[['date', 'equity']], 
        on='date', 
        suffixes=('_backtest', '_paper')
    )

    # הפרשים
    merged['diff'] = merged['equity_paper'] - merged['equity_backtest']
    merged['ratio'] = merged['equity_paper'] / merged['equity_backtest']

    print("\n" + "="*60)
    print("=== נקודות קיצון ===")
    print("="*60)
    
    max_bt_idx = merged['equity_backtest'].idxmax()
    max_paper_idx = merged['equity_paper'].idxmax()
    
    print(f"\nמקסימום Backtest: ${merged.loc[max_bt_idx, 'equity_backtest']:,.2f}")
    print(f"  תאריך: {merged.loc[max_bt_idx, 'date']}")
    
    print(f"\nמקסימום Paper: ${merged.loc[max_paper_idx, 'equity_paper']:,.2f}")
    print(f"  תאריך: {merged.loc[max_paper_idx, 'date']}")

    print("\n" + "="*60)
    print("=== 5 ימים עם הפרש הכי גדול ===")
    print("="*60)
    top_diff = merged.nlargest(5, 'diff')[['date', 'equity_backtest', 'equity_paper', 'diff']]
    print(top_diff.to_string(index=False))

    print("\n" + "="*60)
    print("=== מתי התחיל הפער (ratio > 1.1)? ===")
    print("="*60)
    big_gap = merged[merged['ratio'] > 1.1].head(10)
    if not big_gap.empty:
        print(big_gap[['date', 'equity_backtest', 'equity_paper', 'ratio']].to_string(index=False))
    else:
        print("אין ימים עם ratio > 1.1")
    
    print("\n" + "="*60)
    print("=== סטטיסטיקות ===")
    print("="*60)
    print(f"הפרש ממוצע: ${merged['diff'].mean():,.2f}")
    print(f"הפרש מקסימלי: ${merged['diff'].max():,.2f}")
    print(f"הפרש מינימלי: ${merged['diff'].min():,.2f}")
    print(f"Ratio ממוצע: {merged['ratio'].mean():.2f}x")
    
    # שמירה לקובץ
    merged.to_csv('results_multi/comparison.csv', index=False)
    print(f"\n✅ נשמר ל-results_multi/comparison.csv")

if __name__ == "__main__":
    main()
