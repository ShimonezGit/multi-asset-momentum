#!/usr/bin/env python3
# coding: utf-8
"""
compare_data_sources.py
משווה את הדאטה של הבקטסט מול דאטה חדש מ-Binance
"""

import ccxt
import pandas as pd
import time

def main():
    # משיכת דאטה FRESH מ-Binance
    print("מושך דאטה חדש מ-Binance...")
    exchange = ccxt.binance({"enableRateLimit": True})

    # BTC לדוגמה
    symbol = "BTC/USDT"
    
    # 10 ימים אחרונים
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=10)
    fresh_df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    fresh_df["date"] = pd.to_datetime(fresh_df["timestamp"], unit="ms")

    print("\n=== 10 ימים אחרונים מ-Binance (FRESH) ===")
    print(fresh_df[["date", "close"]])

    # טעינת דאטה מהבקטסט
    try:
        print("\n=== 10 ימים אחרונים מהבקטסט (EXISTING) ===")
        backtest_eq = pd.read_csv("results_multi/crypto_equity_curve.csv")
        backtest_eq["date"] = pd.to_datetime(backtest_eq["date"])
        print(backtest_eq[["date", "equity"]].tail(10))
        
        print("\n=== השוואה ===")
        print(f"תאריך אחרון ב-Binance FRESH: {fresh_df['date'].max()}")
        print(f"תאריך אחרון בבקטסט: {backtest_eq['date'].max()}")
    except FileNotFoundError:
        print("לא נמצא קובץ crypto_equity_curve.csv")

    # בדיקה ספציפית - מחיר BTC ב-01/01/2024
    time.sleep(1)  # rate limit
    start_2024_ms = int(pd.Timestamp("2024-01-01").timestamp() * 1000)
    start_2024 = exchange.fetch_ohlcv("BTC/USDT", timeframe="1d", since=start_2024_ms, limit=1)
    
    if start_2024:
        btc_jan1 = start_2024[0][4]  # close
        print(f"\n=== מחיר BTC ב-01/01/2024 ===")
        print(f"Binance FRESH: ${btc_jan1:,.2f}")
        print(f"מהקובץ שלך: $92,575.64")
        diff = abs(btc_jan1 - 92575.64)
        print(f"הפרש: ${diff:,.2f}")
        
        if diff < 1:
            print("✅ הדאטה זהה!")
        else:
            print("⚠️ יש הבדל בדאטה!")

    # השוואה של כמה אלטים
    print("\n=== בדיקת אלטים (5 ראשונים של 2024) ===")
    alts = ["ETH/USDT", "BNB/USDT", "SOL/USDT"]
    
    for alt in alts:
        time.sleep(1)
        try:
            alt_data = exchange.fetch_ohlcv(alt, timeframe="1d", since=start_2024_ms, limit=5)
            if alt_data:
                print(f"\n{alt}:")
                print(f"  יש דאטה: ✅")
                print(f"  מחיר ראשון ב-2024: ${alt_data[0][4]:,.2f}")
            else:
                print(f"{alt}: אין דאטה ❌")
        except Exception as e:
            print(f"{alt}: שגיאה - {e}")

    print("\n" + "="*60)
    print("סיכום:")
    print("1. אם הדאטה זהה - הבעיה היא בלוגיקה")
    print("2. אם הדאטה שונה - צריך להריץ את הבקטסט מחדש")
    print("3. אם חסרים אלטים - זה מסביר הפרשים")

if __name__ == "__main__":
    main()
