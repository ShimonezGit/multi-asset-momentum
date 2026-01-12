#!/usr/bin/env python3
# coding: utf-8
"""
US Momentum Paper Trading
אותה אסטרטגיה מנצחת על מניות ארה"ב
"""

import os
from dataclasses import dataclass, asdict
from typing import Dict, List
import numpy as np
import pandas as pd
import yfinance as yf

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"
INITIAL_CAPITAL = 100000.0

US_BENCHMARK = "SPY"
US_STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL", "AVGO", "AMD", "NFLX"]

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
EXIT_LOOKBACK = 10
MOMENTUM_THRESHOLD = 0.10
MAX_POSITIONS = 5

RESULTS_DIR = "results_multi"
PAPER_TRADES_FILE = os.path.join(RESULTS_DIR, "us_paper_trades.csv")
PAPER_EQUITY_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")

@dataclass
class PaperTradeLog:
    timestamp: int
    datetime: str
    symbol: str
    side: str
    amount: float
    price: float
    cost: float

@dataclass
class PositionState:
    symbol: str
    amount: float
    cost_basis: float

def fetch_yf_data(ticker: str):
    df = yf.download(ticker, start=START_DATE, end=pd.to_datetime(END_DATE) + pd.Timedelta(days=1), 
                     interval="1d", progress=False, auto_adjust=False)
    if df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "datetime"
    return df

def add_indicators(df):
    out = df.copy()
    out["ma_trend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trend_up"] = out["close"] > out["ma_trend"]
    out["ret_mom"] = out["close"].pct_change(MOMENTUM_LOOKBACK)
    out["ret_exit"] = out["close"].pct_change(EXIT_LOOKBACK)
    return out

def build_calendar(benchmark_df, stock_data):
    idx = benchmark_df.index
    for df in stock_data.values():
        idx = idx.union(df.index)
    return idx.sort_values()

def build_matrix(calendar, data, col):
    series_map = {}
    for sym, df in data.items():
        if col in df.columns:
            series_map[sym] = df[col].reindex(calendar).ffill()
    return pd.DataFrame(series_map, index=calendar)

def log_trade(timestamp, dt, symbol, side, amount, price):
    log = PaperTradeLog(timestamp, dt, symbol, side, amount, price, amount * price)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    row_df = pd.DataFrame([asdict(log)])
    if not os.path.exists(PAPER_TRADES_FILE):
        row_df.to_csv(PAPER_TRADES_FILE, index=False)
    else:
        row_df.to_csv(PAPER_TRADES_FILE, mode="a", header=False, index=False)

def run_us_paper():
    print("מוריד SPY (benchmark)...")
    spy_df = fetch_yf_data(US_BENCHMARK)
    if spy_df.empty:
        raise RuntimeError("לא נמצא SPY")
    
    spy_df = add_indicators(spy_df)
    
    stock_data = {}
    for stock in US_STOCKS:
        print(f"מוריד {stock}...")
        df = fetch_yf_data(stock)
        if not df.empty:
            stock_data[stock] = add_indicators(df)
    
    if not stock_data:
        raise RuntimeError("לא נמצאו מניות")
    
    calendar = build_calendar(spy_df, stock_data)
    closes = build_matrix(calendar, stock_data, "close")
    momentum = build_matrix(calendar, stock_data, "ret_mom")
    exit_ret = build_matrix(calendar, stock_data, "ret_exit")
    trend_series = spy_df["trend_up"].reindex(calendar).ffill().fillna(False)
    
    cash = INITIAL_CAPITAL
    positions = {}
    equity_records = []
    
    print(f"מריץ Paper Trading על {len(calendar)} ימים...")
    
    for current_dt in calendar:
        prices = closes.loc[current_dt]
        
        for sym in list(positions.keys()):
            if sym not in prices or np.isnan(prices[sym]):
                continue
            pos = positions[sym]
            exit_signal = exit_ret.get(sym, pd.Series(dtype=float)).get(current_dt, 0.0)
            if exit_signal <= 0.0:
                sell_value = pos.amount * prices[sym]
                cash += sell_value
                log_trade(int(current_dt.timestamp() * 1_000_000_000), current_dt.isoformat(), 
                         sym, "SELL", pos.amount, prices[sym])
                positions.pop(sym)
        
        portfolio_value = sum(pos.amount * prices.get(sym, 0) for sym, pos in positions.items() 
                             if sym in prices and not np.isnan(prices[sym]))
        total_equity = cash + portfolio_value
        
        if not trend_series.loc[current_dt]:
            equity_records.append({"date": current_dt.date(), "equity": total_equity})
            continue
        
        mom_today = momentum.loc[current_dt]
        candidates = mom_today[mom_today > MOMENTUM_THRESHOLD].sort_values(ascending=False)
        desired_set = set(list(candidates.index[:MAX_POSITIONS]))
        
        for sym in list(positions.keys()):
            if sym not in desired_set and sym in prices and not np.isnan(prices[sym]):
                pos = positions[sym]
                sell_value = pos.amount * prices[sym]
                cash += sell_value
                log_trade(int(current_dt.timestamp() * 1_000_000_000), current_dt.isoformat(),
                         sym, "SELL", pos.amount, prices[sym])
                positions.pop(sym)
        
        portfolio_value = sum(pos.amount * prices.get(sym, 0) for sym, pos in positions.items()
                             if sym in prices and not np.isnan(prices[sym]))
        total_equity = cash + portfolio_value
        
        if not desired_set:
            equity_records.append({"date": current_dt.date(), "equity": total_equity})
            continue
            
        target_value_per_position = total_equity / len(desired_set)
        
        for sym in desired_set:
            if sym not in prices or np.isnan(prices[sym]) or prices[sym] <= 0:
                continue
                
            current_value = 0
            if sym in positions:
                current_value = positions[sym].amount * prices[sym]
            
            delta_value = target_value_per_position - current_value
            
            if abs(delta_value) < 10:
                continue
            
            if delta_value > 0:
                buy_value = min(delta_value, cash * 0.99)
                if buy_value < 10:
                    continue
                buy_amount = buy_value / prices[sym]
                cash -= buy_value
                
                if sym in positions:
                    pos = positions[sym]
                    new_amount = pos.amount + buy_amount
                    new_cost = pos.cost_basis + buy_value
                    positions[sym] = PositionState(sym, new_amount, new_cost)
                else:
                    positions[sym] = PositionState(sym, buy_amount, buy_value)
                
                log_trade(int(current_dt.timestamp() * 1_000_000_000), current_dt.isoformat(),
                         sym, "BUY", buy_amount, prices[sym])
            
            elif delta_value < 0 and sym in positions:
                pos = positions[sym]
                sell_value = min(-delta_value, pos.amount * prices[sym])
                sell_amount = sell_value / prices[sym]
                
                cash += sell_value
                new_amount = pos.amount - sell_amount
                new_cost = pos.cost_basis * (new_amount / pos.amount) if pos.amount > 0 else 0
                
                if new_amount < 0.0001:
                    positions.pop(sym)
                else:
                    positions[sym] = PositionState(sym, new_amount, new_cost)
                
                log_trade(int(current_dt.timestamp() * 1_000_000_000), current_dt.isoformat(),
                         sym, "SELL", sell_amount, prices[sym])
        
        portfolio_value = sum(pos.amount * prices.get(sym, 0) for sym, pos in positions.items()
                             if sym in prices and not np.isnan(prices[sym]))
        total_equity = cash + portfolio_value
        equity_records.append({"date": current_dt.date(), "equity": total_equity})
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(PAPER_EQUITY_FILE, index=False)
    
    print(f"\n{'='*60}")
    print(f"נשמר: {PAPER_EQUITY_FILE}")
    if os.path.exists(PAPER_TRADES_FILE):
        trades_df = pd.read_csv(PAPER_TRADES_FILE)
        print(f"נשמר: {PAPER_TRADES_FILE}")
        print(f"\nסטטיסטיקות US:")
        print(f"  טריידים: {len(trades_df)}")
        print(f"  Equity התחלתי: ${INITIAL_CAPITAL:,.2f}")
        print(f"  Equity סופי: ${total_equity:,.2f}")
        pnl = total_equity - INITIAL_CAPITAL
        pnl_pct = (total_equity / INITIAL_CAPITAL - 1) * 100
        print(f"  רווח/הפסד: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        eq_df['peak'] = eq_df['equity'].cummax()
        eq_df['dd'] = (eq_df['equity'] - eq_df['peak']) / eq_df['peak']
        max_dd = eq_df['dd'].min() * 100
        print(f"  Max Drawdown: {max_dd:.2f}%")
    print(f"{'='*60}")

def main():
    print("=== US Momentum Paper Trading (2022-2025) ===")
    print(f"Universe: SPY + {len(US_STOCKS)} מניות\n")
    run_us_paper()
    print("\n✅ הסתיים!")

if __name__ == "__main__":
    main()
