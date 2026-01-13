#!/usr/bin/env python3
# coding: utf-8
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
import ccxt

LOOKBACK_DAYS = 120
today_utc = datetime.now().date()
start_dt = today_utc - timedelta(days=LOOKBACK_DAYS)
end_dt = today_utc

START_DATE = start_dt.strftime("%Y-%m-%d")
END_DATE = end_dt.strftime("%Y-%m-%d")
TIMEFRAME = "1d"

INITIAL_CAPITAL = 100000.0
CRYPTO_BENCHMARK = "BTC/USDT"
CRYPTO_ALT_SYMBOLS = [
    "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", 
    "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "LINK/USDT", "OP/USDT"
]

MOMENTUM_LOOKBACK = 20
ENTRY_MOMENTUM_THRESHOLD = 0.02
EXIT_MOMENTUM_THRESHOLD = -0.03
MIN_HOLDING_DAYS = 3
MAX_HOLDING_DAYS = 15
MAX_POSITIONS = 5

SLIPPAGE_BPS = 5
COMMISSION_BPS = 10

RESULTS_DIR = "results_multi"
TRADES_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_backtest_trades.csv")
EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_backtest_equity.csv")


@dataclass
class Trade:
    date: datetime
    symbol: str
    side: str
    amount: float
    price: float
    cost: float
    commission: float


@dataclass
class Position:
    symbol: str
    amount: float
    entry_price: float
    entry_date: datetime


def init_binance():
    return ccxt.binance({"enableRateLimit": True})


def fetch_ohlcv(exchange, symbol, timeframe, since_ms, until_ms):
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
    if not all_data:
        return pd.DataFrame()
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df[["open", "high", "low", "close", "volume"]].copy()


def fetch_universe(exchange):
    markets = exchange.load_markets()
    available = set(markets.keys())
    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)
    
    universe = {}
    for sym in [CRYPTO_BENCHMARK] + CRYPTO_ALT_SYMBOLS:
        if sym not in available:
            continue
        print(f"מוריד {sym}...")
        df = fetch_ohlcv(exchange, sym, TIMEFRAME, start_ms, end_ms)
        if df.empty:
            continue
        df["ret_mom"] = df["close"].pct_change(MOMENTUM_LOOKBACK)
        universe[sym] = df
    
    if CRYPTO_BENCHMARK not in universe:
        raise RuntimeError("אין BTC/USDT")
    return universe


def build_calendar(universe):
    idx = pd.DatetimeIndex([])
    for df in universe.values():
        idx = idx.union(df.index)
    return idx.sort_values()


def build_matrix(calendar, universe, col):
    data = {}
    for sym, df in universe.items():
        if col in df.columns:
            data[sym] = df[col].reindex(calendar).ffill()
    return pd.DataFrame(data, index=calendar)


def simulate_fill(price: float, side: str, amount: float):
    slippage_factor = 1 + (SLIPPAGE_BPS / 10000.0) if side == "buy" else 1 - (SLIPPAGE_BPS / 10000.0)
    fill_price = price * slippage_factor
    cost = fill_price * amount
    commission = cost * (COMMISSION_BPS / 10000.0)
    return fill_price, cost, commission


def should_exit(pos: Position, current_dt, momentum: float) -> bool:
    days_held = (current_dt.date() - pos.entry_date.date()).days
    if momentum < EXIT_MOMENTUM_THRESHOLD:
        return True
    if days_held >= MAX_HOLDING_DAYS:
        return True
    if days_held < MIN_HOLDING_DAYS:
        return False
    if momentum < 0:
        return True
    return False


def run_backtest():
    print("=== Crypto Sandbox Backtest ===")
    print(f"טווח: {START_DATE} -> {END_DATE}")
    print(f"פרמטרים: Entry>{ENTRY_MOMENTUM_THRESHOLD}, Exit<{EXIT_MOMENTUM_THRESHOLD}")
    print(f"Holding: {MIN_HOLDING_DAYS}-{MAX_HOLDING_DAYS} days, Max Positions: {MAX_POSITIONS}")
    print(f"Slippage: {SLIPPAGE_BPS}bps, Commission: {COMMISSION_BPS}bps\n")
    
    exchange = init_binance()
    universe = fetch_universe(exchange)
    calendar = build_calendar(universe)
    closes = build_matrix(calendar, universe, "close")
    momentum = build_matrix(calendar, universe, "ret_mom")
    
    cash = INITIAL_CAPITAL
    positions: Dict[str, Position] = {}
    trades: List[Trade] = []
    equity_records = []
    
    print(f"מתחיל backtest על {len(calendar)} ימים...\n")
    
    for i, current_dt in enumerate(calendar):
        if i % 10 == 0:
            print(f"  יום {i+1}/{len(calendar)}: {current_dt.date()}")
        
        prices = closes.loc[current_dt]
        
        # יציאות
        for sym in list(positions.keys()):
            pos = positions[sym]
            price = prices.get(sym, np.nan)
            if np.isnan(price):
                continue
            
            current_momentum = momentum.loc[current_dt].get(sym, 0.0)
            
            if should_exit(pos, current_dt, current_momentum):
                days_held = (current_dt.date() - pos.entry_date.date()).days
                fill_price, cost, commission = simulate_fill(price, "sell", pos.amount)
                cash += cost - commission
                
                pnl = (fill_price - pos.entry_price) * pos.amount - commission
                trades.append(Trade(current_dt, sym, "SELL", pos.amount, fill_price, cost, commission))
                print(f"    EXIT {sym} אחרי {days_held} ימים, PnL: {pnl:.2f}")
                positions.pop(sym)
        
        # כניסות
        if len(positions) < MAX_POSITIONS:
            mom = momentum.loc[current_dt]
            candidates = mom[mom > ENTRY_MOMENTUM_THRESHOLD].sort_values(ascending=False)
            
            for sym in candidates.index:
                if sym in positions:
                    continue
                if len(positions) >= MAX_POSITIONS:
                    break
                
                price = prices.get(sym, np.nan)
                if np.isnan(price) or price <= 0:
                    continue
                
                # גודל פוזיציה: equity / max_positions
                portfolio_value = sum(pos.amount * prices.get(s, 0) for s, pos in positions.items())
                equity = cash + portfolio_value
                position_size = equity / MAX_POSITIONS
                
                if position_size < 100:
                    continue
                
                amount = position_size / price
                fill_price, cost, commission = simulate_fill(price, "buy", amount)
                
                if cost + commission > cash:
                    continue
                
                cash -= (cost + commission)
                positions[sym] = Position(sym, amount, fill_price, current_dt)
                trades.append(Trade(current_dt, sym, "BUY", amount, fill_price, cost, commission))
                print(f"    ENTER {sym}, momentum={mom[sym]:.3f}, size={position_size:.0f}")
        
        # equity
        portfolio_value = sum(pos.amount * prices.get(sym, 0) for sym, pos in positions.items())
        equity = cash + portfolio_value
        equity_records.append({
            "date": current_dt.date(),
            "equity": equity,
            "cash": cash,
            "positions": portfolio_value,
            "num_positions": len(positions)
        })
    
    # שמירה
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    if trades:
        trades_df = pd.DataFrame([
            {
                "date": t.date.date(),
                "symbol": t.symbol,
                "side": t.side,
                "amount": t.amount,
                "price": t.price,
                "cost": t.cost,
                "commission": t.commission
            }
            for t in trades
        ])
        trades_df.to_csv(TRADES_FILE, index=False)
    
    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(EQUITY_FILE, index=False)
    
    # סיכום
    print("\n=== סיכום ===")
    print(f"✅ {EQUITY_FILE}")
    if trades:
        print(f"✅ {TRADES_FILE} ({len(trades)} עסקאות)")
        buy_trades = [t for t in trades if t.side == "BUY"]
        sell_trades = [t for t in trades if t.side == "SELL"]
        total_commissions = sum(t.commission for t in trades)
        print(f"   BUY: {len(buy_trades)}, SELL: {len(sell_trades)}")
        print(f"   עמלות: {total_commissions:.2f}")
    else:
        print("⚠️ אין עסקאות")
    
    final_equity = eq_df["equity"].iloc[-1]
    total_return = (final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    max_equity = eq_df["equity"].max()
    max_dd = ((eq_df["equity"] / eq_df["equity"].cummax()) - 1).min() * 100
    
    print(f"\nהון התחלתי: {INITIAL_CAPITAL:,.0f}")
    print(f"הון סופי: {final_equity:,.2f}")
    print(f"תשואה: {total_return:.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")


def main():
    run_backtest()


if __name__ == "__main__":
    main()
