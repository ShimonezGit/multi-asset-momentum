#!/usr/bin/env python3
# coding: utf-8

"""
test_testnet_data.py
בודק כמה ברים בפועל יש בטסטנט לכל סימבול
"""

import os
import time
from datetime import datetime, timedelta
import ccxt
import pandas as pd


def main():
    BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
    BINANCE_TESTNET_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY")

    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        print("שגיאה: חסרים מפתחות API ב-environment variables")
        print("הרץ: export BINANCE_TESTNET_API_KEY=...")
        print("      export BINANCE_TESTNET_SECRET_KEY=...")
        return

    LOOKBACK_DAYS = 150  # מנסים 150 יום
    today = datetime.utcnow().date()
    start_dt = today - timedelta(days=LOOKBACK_DAYS)
    end_dt = today

    START_DATE = start_dt.strftime("%Y-%m-%d")
    END_DATE = end_dt.strftime("%Y-%m-%d")

    exchange = ccxt.binance({
        "apiKey": BINANCE_TESTNET_API_KEY,
        "secret": BINANCE_TESTNET_SECRET_KEY,
        "enableRateLimit": True,
    })
    exchange.set_sandbox_mode(True)

    print(f"בודק היסטוריה לטווח: {START_DATE} עד {END_DATE}")
    print("=" * 60)

    symbols_to_test = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
    ]

    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)

    for symbol in symbols_to_test:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", since=start_ms, limit=1000)
            if not ohlcv:
                print(f"{symbol}: אין נתונים")
                continue
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            
            print(f"{symbol}:")
            print(f"  סה״כ ברים שהתקבלו: {len(df)}")
            print(f"  תאריך ראשון: {df['datetime'].min()}")
            print(f"  תאריך אחרון: {df['datetime'].max()}")
            print()
            
            time.sleep(exchange.rateLimit / 1000.0)
            
        except Exception as e:
            print(f"{symbol}: שגיאה - {e}")
            print()

    print("=" * 60)
    print("סיכום:")
    print("אם יש פחות מ-100 ברים, אי אפשר לחשב MA100")
    print("אם יש פחות מ-20 ברים, אי אפשר לחשב מומנטום 20")


if __name__ == "__main__":
    main()
