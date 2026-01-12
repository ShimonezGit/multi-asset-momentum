#!/usr/bin/env python3
# coding: utf-8

"""
debug_paper_strategy.py
בודק למה האסטרטגיה לא פתחה פוזיציות
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np
import pandas as pd
import ccxt


# הגדרות זהות ל-paper
LOOKBACK_DAYS = 150
_today_utc = datetime.now(datetime.UTC).date() if hasattr(datetime, 'UTC') else datetime.utcnow().date()
_start_dt = _today_utc - timedelta(days=LOOKBACK_DAYS)
_end_dt = _today_utc

START_DATE = _start_dt.strftime("%Y-%m-%d")
END_DATE = _end_dt.strftime("%Y-%m-%d")
TIMEFRAME_CRYPTO = "1d"

CRYPTO_BENCHMARK = "BTC/USDT"
CRYPTO_ALT_SYMBOLS = [
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
]

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
MOMENTUM_THRESHOLD = 0.10


def fetch_ohlcv_for_symbol(exchange, symbol, timeframe, since_ms, until_ms):
    all_data = []
    limit = 1000
    since = since_ms

    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        if not ohlcv:
            break
        all_data.extend(ohlcv)
        last_ts = ohlcv[-1][0]
        if last_ts >= until_ms:
            break
        since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000.0)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df[["open", "high", "low", "close", "volume"]].copy()


def add_trend_and_momentum(df):
    out = df.copy()
    out["ma_trend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trend_up"] = out["close"] > out["ma_trend"]
    out["ret_mom"] = out["close"].pct_change(MOMENTUM_LOOKBACK)
    return out


def main():
    print(f"בודק אסטרטגיה לטווח {START_DATE} עד {END_DATE}")
    print("=" * 60)
    
    exchange = ccxt.binance({"enableRateLimit": True})
    
    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)
    
    # BTC
    print("מוריד BTC...")
    btc_df = fetch_ohlcv_for_symbol(exchange, CRYPTO_BENCHMARK, TIMEFRAME_CRYPTO, start_ms, end_ms)
    btc_df = add_trend_and_momentum(btc_df)
    
    print(f"\nBTC/USDT:")
    print(f"  סה״כ ברים: {len(btc_df)}")
    print(f"  ברים תקינים ל-MA100: {btc_df['ma_trend'].notna().sum()}")
    print(f"  ברים עם טרנד למעלה: {btc_df['trend_up'].sum()}")
    print(f"  % ימים עם טרנד למעלה: {btc_df['trend_up'].sum() / len(btc_df) * 100:.1f}%")
    
    # 5 ימים אחרונים
    print(f"\n5 ימים אחרונים:")
    last_5 = btc_df.tail(5)[['close', 'ma_trend', 'trend_up', 'ret_mom']]
    print(last_5)
    
    # בדיקת אלטים
    print(f"\n{'='*60}")
    print("בודק מומנטום של אלטים ב-5 הימים האחרונים:")
    print("(צריך > {:.1f}% כדי להיכנס)".format(MOMENTUM_THRESHOLD * 100))
    print("=" * 60)
    
    for alt in CRYPTO_ALT_SYMBOLS:
        print(f"\n{alt}:")
        df = fetch_ohlcv_for_symbol(exchange, alt, TIMEFRAME_CRYPTO, start_ms, end_ms)
        if df.empty:
            print("  אין נתונים")
            continue
        df = add_trend_and_momentum(df)
        last_5 = df.tail(5)[['close', 'ret_mom']]
        print(last_5)
        print(f"  מקסימום מומנטום ב-5 ימים אחרונים: {df.tail(5)['ret_mom'].max():.2%}")
        print(f"  עבר סף? {'כן' if df.tail(5)['ret_mom'].max() > MOMENTUM_THRESHOLD else 'לא'}")
    
    print(f"\n{'='*60}")
    print("סיכום:")
    print(f"  אם BTC trend_up=False ברוב הימים → לא פותחים פוזיציות")
    print(f"  אם אף אלט לא עבר {MOMENTUM_THRESHOLD:.0%} → לא נכנסים")


if __name__ == "__main__":
    main()
