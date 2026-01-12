#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_benchmarks.py
מוריד נתוני Benchmark ומשלב אותם עם equity curves קיימים
"""

import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

RESULTS_DIR = "results_multi"

def load_equity_curve(name: str) -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, f"{name}_equity_curve.csv")
    if not os.path.exists(path):
        print(f"❌ לא נמצא קובץ: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    else:
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        df = df.rename(columns={df.columns[0]: "date"})
    df = df.sort_values("date").reset_index(drop=True)
    return df

def download_benchmark(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """מוריד נתוני benchmark מ-yfinance"""
    print(f"📥 מוריד {ticker} מ-{start_date} עד {end_date}...")
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            print(f"⚠️  לא נמצאו נתונים ל-{ticker}")
            return pd.DataFrame()
        df = data[["Close"]].reset_index()
        df.columns = ["date", "close"]
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"❌ שגיאה בהורדת {ticker}: {e}")
        return pd.DataFrame()

def merge_benchmark_to_equity(equity_df: pd.DataFrame, benchmark_df: pd.DataFrame, market_name: str) -> pd.DataFrame:
    """משלב נתוני benchmark עם equity curve"""
    if equity_df.empty or benchmark_df.empty:
        print(f"⚠️  {market_name}: אין נתונים למיזוג")
        return equity_df
    
    # מיזוג לפי תאריך
    merged = equity_df.merge(benchmark_df, on="date", how="left", suffixes=("", "_bench"))
    merged["close"] = merged["close"].fillna(method="ffill").fillna(method="bfill")
    
    # נרמול: benchmark_equity מתחיל מאותו הון כמו equity
    if "equity" in merged.columns and not merged["close"].isna().all():
        first_equity = merged["equity"].iloc[0]
        first_close = merged["close"].iloc[0]
        if first_close > 0:
            merged["benchmark_equity"] = (merged["close"] / first_close) * first_equity
        else:
            merged["benchmark_equity"] = first_equity
    else:
        merged["benchmark_equity"] = np.nan
    
    # הסרת עמודות מיותרות
    if "close" in merged.columns:
        merged = merged.drop(columns=["close"])
    
    print(f"✅ {market_name}: הוסף benchmark_equity")
    return merged

def main():
    print("=" * 60)
    print("הוספת נתוני Benchmark לעקומות ההון")
    print("=" * 60)
    
    # 1. קריפטו (BTC)
    print("\n📊 קריפטו (BTC)...")
    crypto_df = load_equity_curve("crypto")
    if not crypto_df.empty:
        start = crypto_df["date"].min().strftime("%Y-%m-%d")
        end = crypto_df["date"].max().strftime("%Y-%m-%d")
        btc_df = download_benchmark("BTC-USD", start, end)
        crypto_df = merge_benchmark_to_equity(crypto_df, btc_df, "CRYPTO")
        crypto_df.to_csv(os.path.join(RESULTS_DIR, "crypto_equity_curve.csv"), index=False)
        print(f"💾 נשמר: crypto_equity_curve.csv")
    
    # 2. ארה"ב (S&P500)
    print("\n📊 ארה\"ב (S&P500)...")
    us_df = load_equity_curve("us")
    if not us_df.empty:
        start = us_df["date"].min().strftime("%Y-%m-%d")
        end = us_df["date"].max().strftime("%Y-%m-%d")
        sp500_df = download_benchmark("^GSPC", start, end)
        us_df = merge_benchmark_to_equity(us_df, sp500_df, "US")
        us_df.to_csv(os.path.join(RESULTS_DIR, "us_equity_curve.csv"), index=False)
        print(f"💾 נשמר: us_equity_curve.csv")
    
    # 3. ישראל (TA-125)
    print("\n📊 ישראל (TA-125)...")
    il_df = load_equity_curve("il")
    if not il_df.empty:
        start = il_df["date"].min().strftime("%Y-%m-%d")
        end = il_df["date"].max().strftime("%Y-%m-%d")
        ta125_df = download_benchmark("^TA125.TA", start, end)
        il_df = merge_benchmark_to_equity(il_df, ta125_df, "IL")
        il_df.to_csv(os.path.join(RESULTS_DIR, "il_equity_curve.csv"), index=False)
        print(f"💾 נשמר: il_equity_curve.csv")
    
    print("\n" + "=" * 60)
    print("✅ סיום! כל הקבצים עודכנו עם נתוני Benchmark")
    print("=" * 60)

if __name__ == "__main__":
    main()

