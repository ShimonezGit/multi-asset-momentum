#!/usr/bin/env python3
# coding: utf-8
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd
import ccxt

LOOKBACK_DAYS = 30
today_utc = datetime.now().date()
start_dt = today_utc - timedelta(days=LOOKBACK_DAYS)
end_dt = today_utc

START_DATE = start_dt.strftime("%Y-%m-%d")
END_DATE = end_dt.strftime("%Y-%m-%d")
TIMEFRAME_CRYPTO = "1d"

CRYPTO_BENCHMARK = "BTC/USDT"
CRYPTO_ALT_SYMBOLS = ["ETH/USDT", "SOL/USDT"]

MOMENTUM_LOOKBACK = 20
ENTRY_MOMENTUM_THRESHOLD = 0.02
EXIT_MOMENTUM_THRESHOLD = -0.03
MIN_HOLDING_DAYS = 3
MAX_HOLDING_DAYS = 15
MAX_POSITIONS = 2
MAX_POSITION_SIZE_USDT = 1500.0

RESULTS_DIR = "results_multi"
SANDBOX_TRADES_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_trades.csv")
SANDBOX_EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_equity.csv")

BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
BINANCE_TESTNET_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY")


@dataclass
class SandboxTradeLog:
    timestamp: int
    datetime: str
    symbol: str
    side: str
    amount: float
    price: float
    cost: float
    info_id: str


@dataclass
class PositionState:
    symbol: str
    amount: float
    entry_price: float
    entry_date: datetime


def init_binance_real():
    return ccxt.binance({"enableRateLimit": True})


def init_binance_testnet():
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        raise RuntimeError("חסר API keys")
    exchange = ccxt.binance({
        "apiKey": BINANCE_TESTNET_API_KEY,
        "secret": BINANCE_TESTNET_SECRET_KEY,
        "enableRateLimit": True,
    })
    exchange.set_sandbox_mode(True)
    return exchange


def fetch_testnet_usdt(exchange):
    try:
        balance = exchange.fetch_balance()
        return float(balance["free"].get("USDT", 0.0))
    except Exception as e:
        print(f"שגיאה בקריאת balance: {e}")
        return 0.0


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
    return df[["close", "volume"]].copy()


def fetch_crypto_universe(exchange):
    markets = exchange.load_markets()
    available = set(markets.keys())
    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)
    
    universe = {}
    for sym in [CRYPTO_BENCHMARK] + CRYPTO_ALT_SYMBOLS:
        if sym not in available:
            continue
        print(f"מוריד {sym}...")
        df = fetch_ohlcv_for_symbol(exchange, sym, TIMEFRAME_CRYPTO, start_ms, end_ms)
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


def place_market_order(exchange, symbol, side, amount):
    if amount <= 0:
        return None
    try:
        binance_symbol = symbol.replace("/", "")
        order = exchange.create_order(symbol=binance_symbol, type="market", side=side, amount=amount)
        ts = int(order.get("timestamp") or int(time.time() * 1000))
        dt = exchange.iso8601(ts)
        price = float(order.get("price") or 0.0)
        if price == 0.0:
            fills = order.get("info", {}).get("fills") or order.get("fills") or []
            if fills:
                price = float(fills[0].get("price") or 0.0)
        cost = float(order.get("cost") or (price * amount))
        return SandboxTradeLog(ts, dt, symbol, side.upper(), amount, price, cost, str(order.get("id")))
    except Exception as e:
        print(f"שגיאה order {symbol}: {e}")
        return None


def append_trade_log(log_entry):
    if not log_entry:
        return
    os.makedirs(RESULTS_DIR, exist_ok=True)
    row = pd.DataFrame([asdict(log_entry)])
    if not os.path.exists(SANDBOX_TRADES_FILE):
        row.to_csv(SANDBOX_TRADES_FILE, index=False)
    else:
        row.to_csv(SANDBOX_TRADES_FILE, mode="a", header=False, index=False)


def should_exit_position(pos: PositionState, current_dt, momentum: float) -> bool:
    days_held = (current_dt.date() - pos.entry_date.date()).days
    
    # יציאה חובה אם מומנטום שלילי חזק
    if momentum < EXIT_MOMENTUM_THRESHOLD:
        return True
    
    # יציאה אחרי holding period מקסימלי
    if days_held >= MAX_HOLDING_DAYS:
        return True
    
    # לא לצאת לפני holding period מינימלי אלא אם כן הפסד גדול
    if days_held < MIN_HOLDING_DAYS:
        return False
    
    # יציאה אם מומנטום הפך שלילי אחרי holding מינימלי
    if momentum < 0:
        return True
    
    return False


def run_crypto_sandbox():
    print("=== Crypto Sandbox ===")
    print(f"טווח: {START_DATE} -> {END_DATE}")
    print(f"פרמטרים: Entry>{ENTRY_MOMENTUM_THRESHOLD}, Exit<{EXIT_MOMENTUM_THRESHOLD}, Hold {MIN_HOLDING_DAYS}-{MAX_HOLDING_DAYS} days")
    
    exchange_data = init_binance_real()
    exchange_exec = init_binance_testnet()
    
    universe = fetch_crypto_universe(exchange_data)
    calendar = build_calendar(universe)
    closes = build_matrix(calendar, universe, "close")
    momentum = build_matrix(calendar, universe, "ret_mom")
    
    positions: Dict[str, PositionState] = {}
    equity_records = []
    
    initial_usdt = fetch_testnet_usdt(exchange_exec)
    print(f"יתרת USDT התחלתית: {initial_usdt:.2f}")
    
    print(f"מתחיל לולאה על {len(calendar)} ימים...")
    for i, current_dt in enumerate(calendar):
        if i % 5 == 0:
            print(f"  יום {i+1}/{len(calendar)}: {current_dt.date()}")
        
        prices = closes.loc[current_dt]
        
        # בדיקת יציאות - רק לפי קריטריונים חכמים
        for sym in list(positions.keys()):
            pos = positions[sym]
            price = prices.get(sym, np.nan)
            if np.isnan(price):
                continue
            
            current_momentum = momentum.loc[current_dt].get(sym, 0.0)
            
            if should_exit_position(pos, current_dt, current_momentum):
                days_held = (current_dt.date() - pos.entry_date.date()).days
                print(f"    EXIT {sym} אחרי {days_held} ימים, momentum={current_momentum:.3f}")
                log = place_market_order(exchange_exec, sym, "sell", pos.amount)
                if log:
                    append_trade_log(log)
                    positions.pop(sym, None)
        
        # בדיקת כניסות - רק אם יש מקום
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
                
                # חישוב כמה USDT יש זמין
                current_usdt = fetch_testnet_usdt(exchange_exec)
                
                # גודל פוזיציה: מינימום בין MAX_POSITION_SIZE לבין 40% מהיתרה
                position_size_usdt = min(MAX_POSITION_SIZE_USDT, current_usdt * 0.4)
                
                if position_size_usdt < 100:
                    continue
                
                amount = position_size_usdt / price
                
                print(f"    ENTER {sym}, momentum={mom[sym]:.3f}, size={position_size_usdt:.0f} USDT")
                log = place_market_order(exchange_exec, sym, "buy", amount)
                if log:
                    append_trade_log(log)
                    positions[sym] = PositionState(sym, log.amount, log.price, current_dt)
        
        # חישוב equity
        current_usdt = fetch_testnet_usdt(exchange_exec)
        portfolio_val = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
        )
        equity = current_usdt + portfolio_val
        equity_records.append({"date": current_dt.date(), "equity": equity, "cash": current_usdt, "positions": portfolio_val})
    
    # סיכום
    os.makedirs(RESULTS_DIR, exist_ok=True)
    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(SANDBOX_EQUITY_FILE, index=False)
    
    print("\n=== סיכום ===")
    print(f"✅ {SANDBOX_EQUITY_FILE}")
    if os.path.exists(SANDBOX_TRADES_FILE):
        trades_df = pd.read_csv(SANDBOX_TRADES_FILE)
        num_trades = len(trades_df)
        print(f"✅ {SANDBOX_TRADES_FILE} ({num_trades} עסקאות)")
    else:
        print("⚠️ אין טריידים")
    
    final_equity = eq_df["equity"].iloc[-1]
    total_return = (final_equity - initial_usdt) / initial_usdt * 100
    print(f"הון התחלתי: {initial_usdt:.2f} USDT")
    print(f"הון סופי: {final_equity:.2f} USDT")
    print(f"תשואה: {total_return:.2f}%")


def main():
    run_crypto_sandbox()


if __name__ == "__main__":
    main()
