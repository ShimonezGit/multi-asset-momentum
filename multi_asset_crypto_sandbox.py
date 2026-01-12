#!/usr/bin/env python3
# coding: utf-8

"""
multi_asset_crypto_sandbox.py

Sandbox למסחר יומי בקריפטו (BTC + אלטים זמינים) על Binance Spot Testnet,
עם לוגיקת מומנטום/טרנד זהה רעיונית לבקטסט multi_asset_momentum_backtest.py:
- MA 100 כסינון טרנד
- מומנטום 20 ימים
- EXIT 10 ימים
- TOP N נכסים לפי מומנטום
- הקצאה שווה בין פוזיציות

היוניברס נבנה דינמית לפי מה שקיים בפועל ב-Binance Spot Testnet
(סימבולים שלא קיימים / ללא נתונים – נזרקים).

טווח הנתונים: 60 ימים אחורה מהיום (UTC), טיימפריים יומי.
"""

import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import ccxt


# ========================
# קונפיגורציה בסיסית
# ========================

# טווח יחסי – 60 ימים אחורה מהיום (UTC)
LOOKBACK_DAYS = 60
_today_utc = datetime.utcnow().date()
_start_dt = _today_utc - timedelta(days=LOOKBACK_DAYS)
_end_dt = _today_utc

START_DATE = _start_dt.strftime("%Y-%m-%d")
END_DATE = _end_dt.strftime("%Y-%m-%d")
TIMEFRAME_CRYPTO = "1d"

INITIAL_CAPITAL = 100000.0

# Benchmark
CRYPTO_BENCHMARK = "BTC/USDT"

# רשימת אלטים רצויה – בפועל נסנן לפי מה שקיים במרקטים של הטסטנט
CRYPTO_ALT_SYMBOLS_CANDIDATES = [
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "MATIC/USDT",
    "OP/USDT",
]

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
EXIT_LOOKBACK = 10
MOMENTUM_THRESHOLD = 0.10  # 10%
MAX_POSITIONS = 5

RESULTS_DIR = "results_multi"
SANDBOX_TRADES_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_trades.csv")
SANDBOX_EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_equity.csv")

EXECUTE_ON_TESTNET = True

BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
BINANCE_TESTNET_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY")


# ========================
# מבני נתונים
# ========================

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


# ========================
# יוטיליטי – Binance Testnet
# ========================

def init_binance_testnet() -> ccxt.binance:
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        raise RuntimeError(
            "חסר BINANCE_TESTNET_API_KEY או BINANCE_TESTNET_SECRET_KEY ב-env. "
            "שים export לפני הרצה."
        )

    exchange = ccxt.binance({
        "apiKey": BINANCE_TESTNET_API_KEY,
        "secret": BINANCE_TESTNET_SECRET_KEY,
        "enableRateLimit": True,
    })
    exchange.set_sandbox_mode(True)
    return exchange


def fetch_ohlcv_for_symbol(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    since_ms: int,
    until_ms: int,
) -> pd.DataFrame:
    all_data: List[List[float]] = []
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

    df = pd.DataFrame(
        all_data,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df[["open", "high", "low", "close", "volume"]].copy()


def fetch_crypto_universe(
    exchange: ccxt.binance,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    בונה Universe קריפטו דינמי לפי מה שקיים ב-Binance Spot Testnet:
    - BTC/USDT (חובה)
    - כל אלט מ-CRYPTO_ALT_SYMBOLS_CANDIDATES שקיים ב-exchange.markets
      ויש לו נתוני OHLCV בטווח.
    """
    print("טוען רשימת מרקטים מה-Binance Spot Testnet...")
    markets = exchange.load_markets()
    available_symbols = set(markets.keys())

    if CRYPTO_BENCHMARK not in available_symbols:
        raise RuntimeError(f"Benchmark {CRYPTO_BENCHMARK} לא קיים ב-Testnet markets.")

    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)

    print(f"מוריד נתוני BTC/Benchmark מה-API לטווח {START_DATE} עד {END_DATE}...")
    btc_df = fetch_ohlcv_for_symbol(
        exchange, CRYPTO_BENCHMARK, TIMEFRAME_CRYPTO, start_ms, end_ms
    )
    if btc_df.empty:
        raise RuntimeError("לא נמצאו נתוני OHLCV עבור BTC/USDT בטווח המבוקש.")

    alt_data: Dict[str, pd.DataFrame] = {}

    for alt in CRYPTO_ALT_SYMBOLS_CANDIDATES:
        if alt not in available_symbols:
            print(f"{alt} – לא קיים במרקטים של הטסטנט. מדלג.")
            continue
        print(f"מוריד נתונים עבור {alt} לטווח {START_DATE} עד {END_DATE}...")
        df = fetch_ohlcv_for_symbol(
            exchange, alt, TIMEFRAME_CRYPTO, start_ms, end_ms
        )
        if df.empty:
            print(f"{alt} – אין נתוני OHLCV בטווח. מדלג.")
            continue
        alt_data[alt] = df

    if not alt_data:
        print("אזהרה: לא נמצאו אלטים עם נתונים. הסנדבוקס יעבוד רק על BTC/USDT.")

    return btc_df, alt_data


# ========================
# אינדיקטורים ואסטרטגיה
# ========================

def add_trend_and_momentum(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ma_trend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trend_up"] = out["close"] > out["ma_trend"]
    out["ret_1d"] = out["close"].pct_change()
    out["ret_mom"] = out["close"].pct_change(MOMENTUM_LOOKBACK)
    out["ret_exit"] = out["close"].pct_change(EXIT_LOOKBACK)
    return out


def build_calendar(
    benchmark_df: pd.DataFrame,
    alt_data: Dict[str, pd.DataFrame],
) -> pd.DatetimeIndex:
    idx = benchmark_df.index
    for df in alt_data.values():
        idx = idx.union(df.index)
    idx = idx.sort_values()
    idx = idx[(idx >= START_DATE) & (idx <= END_DATE)]
    return idx


def build_matrix(
    calendar: pd.DatetimeIndex,
    data: Dict[str, pd.DataFrame],
    col: str,
) -> pd.DataFrame:
    series_map = {}
    for sym, df in data.items():
        if col not in df.columns:
            continue
        ser = df[col].reindex(calendar).ffill()
        series_map[sym] = ser
    return pd.DataFrame(series_map, index=calendar)


# ========================
# ביצוע – Binance Orders
# ========================

def place_market_order(
    exchange: ccxt.binance,
    symbol: str,
    side: str,
    amount: float,
) -> Optional[SandboxTradeLog]:
    if amount <= 0:
        return None

    if not EXECUTE_ON_TESTNET:
        now_ms = int(time.time() * 1000)
        dt = pd.to_datetime(now_ms, unit="ms").isoformat()
        return SandboxTradeLog(
            timestamp=now_ms,
            datetime=dt,
            symbol=symbol,
            side=side.upper(),
            amount=amount,
            price=0.0,
            cost=0.0,
            info_id="SIMULATED",
        )

    try:
        binance_symbol = symbol.replace("/", "")
        order = exchange.create_order(
            symbol=binance_symbol,
            type="market",
            side=side,
            amount=amount,
        )
        ts = int(order.get("timestamp") or int(time.time() * 1000))
        dt = exchange.iso8601(ts)
        price = float(order.get("price") or 0.0)
        if price == 0.0:
            fills = (
                order.get("info", {}).get("fills")
                or order.get("fills")
                or []
            )
            if fills:
                price = float(fills[0].get("price") or 0.0)
        cost = float(order.get("cost") or (price * amount))
        return SandboxTradeLog(
            timestamp=ts,
            datetime=dt,
            symbol=symbol,
            side=side.upper(),
            amount=amount,
            price=price,
            cost=cost,
            info_id=str(order.get("id")),
        )
    except Exception as e:
        print(f"שגיאה בביצוע order עבור {symbol}: {e}")
        return None


def append_trade_log(log: SandboxTradeLog) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    row_df = pd.DataFrame([asdict(log)])
    if not os.path.exists(SANDBOX_TRADES_FILE):
        row_df.to_csv(SANDBOX_TRADES_FILE, index=False)
    else:
        row_df.to_csv(SANDBOX_TRADES_FILE, mode="a", header=False, index=False)


# ========================
# לוגיקת Sandbox – ניהול תיק
# ========================

def run_crypto_sandbox() -> None:
    print("מתחבר ל-Binance Spot Testnet...")
    exchange = init_binance_testnet()

    print("מוריד Universe קריפטו (דינמי לפי מרקטים קיימים)...")
    btc_df_raw, alt_data_raw = fetch_crypto_universe(exchange)

    btc_df = add_trend_and_momentum(btc_df_raw)
    alt_data: Dict[str, pd.DataFrame] = {}
    for sym, df in alt_data_raw.items():
        alt_data[sym] = add_trend_and_momentum(df)

    universe_data: Dict[str, pd.DataFrame] = {CRYPTO_BENCHMARK: btc_df, **alt_data}
    calendar = build_calendar(btc_df, alt_data)
    closes = build_matrix(calendar, universe_data, "close")
    momentum = build_matrix(calendar, universe_data, "ret_mom")
    exit_ret = build_matrix(calendar, universe_data, "ret_exit")

    trend_series = btc_df["trend_up"].reindex(calendar).ffill().fillna(False)

    equity = INITIAL_CAPITAL
    positions: Dict[str, PositionState] = {}
    equity_records: List[Dict[str, float]] = []

    print("מתחיל לולאת ימים (Sandbox על טווח יחסי)...")
    for current_dt in calendar:
        prices_today = closes.loc[current_dt]

        # יציאות לפי EXIT
        for sym in list(positions.keys()):
            pos = positions[sym]
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount <= 0:
                continue
            sym_exit = exit_ret.get(sym, pd.Series(dtype=float)).get(current_dt, 0.0)
            if sym_exit <= 0.0:
                side = "sell"
                amount = pos.amount
                trade_log = place_market_order(exchange, sym, side, amount)
                if trade_log:
                    append_trade_log(trade_log)
                    equity += (trade_log.price - pos.entry_price) * trade_log.amount
                positions.pop(sym, None)

        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount <= 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value

        # ללא טרנד למעלה – לא פותחים פוזיציות חדשות
        if not trend_series.loc[current_dt]:
            equity_records.append(
                {"date": current_dt.date(), "equity": float(total_equity)}
            )
            continue

        # בחירת נכסים לפי מומנטום
        mom_today = momentum.loc[current_dt]
        candidates = mom_today[mom_today > MOMENTUM_THRESHOLD].sort_values(ascending=False)
        selected = list(candidates.index[:MAX_POSITIONS])
        desired_set = set(selected)

        # סגירת נכסים שאינם רצויים (שלא נסגרו ב-EXIT)
        for sym in list(positions.keys()):
            if sym not in desired_set:
                pos = positions[sym]
                price = prices_today.get(sym, np.nan)
                if np.isnan(price) or pos.amount <= 0:
                    continue
                side = "sell"
                amount = pos.amount
                trade_log = place_market_order(exchange, sym, side, amount)
                if trade_log:
                    append_trade_log(trade_log)
                    equity += (trade_log.price - pos.entry_price) * trade_log.amount
                positions.pop(sym, None)

        # חישוב מחדש של ערך התיק אחרי סגירות
        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount <= 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value

        if len(desired_set) > 0:
            capital_per_position = total_equity / float(len(desired_set))
        else:
            capital_per_position = 0.0

        # פתיחה / Rebalance
        for sym in desired_set:
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or price <= 0:
                continue

            current_amount = positions.get(sym, PositionState(sym, 0.0, 0.0)).amount
            target_amount = capital_per_position / price
            delta_amount = target_amount - current_amount

            if abs(delta_amount * price) < 1.0:
                continue

            if delta_amount > 0:
                side = "buy"
                amount = delta_amount
                cost_est = amount * price
                if cost_est > equity:
                    continue
                trade_log = place_market_order(exchange, sym, side, amount)
                if trade_log:
                    append_trade_log(trade_log)
                    equity -= trade_log.price * trade_log.amount
                    new_amount = current_amount + trade_log.amount
                    if current_amount <= 0:
                        new_entry = trade_log.price
                    else:
                        old_value = current_amount * positions[sym].entry_price
                        new_value = old_value + trade_log.price * trade_log.amount
                        new_entry = new_value / new_amount
                    positions[sym] = PositionState(sym, new_amount, new_entry)

            elif delta_amount < 0:
                side = "sell"
                amount = -delta_amount
                if sym not in positions or positions[sym].amount <= 0:
                    continue
                if amount > positions[sym].amount:
                    amount = positions[sym].amount
                trade_log = place_market_order(exchange, sym, side, amount)
                if trade_log:
                    append_trade_log(trade_log)
                    pos = positions[sym]
                    equity += (trade_log.price - pos.entry_price) * trade_log.amount
                    new_amount = pos.amount - trade_log.amount
                    if new_amount <= 0:
                        positions.pop(sym, None)
                    else:
                        positions[sym] = PositionState(sym, new_amount, pos.entry_price)

        # עדכון Equity ליום
        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount <= 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value

        equity_records.append(
            {"date": current_dt.date(), "equity": float(total_equity)}
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(SANDBOX_EQUITY_FILE, index=False)
    print(f"נשמר קובץ עקומת הון של הסנדבוקס: {SANDBOX_EQUITY_FILE}")
    print(f"נשמר קובץ טריידים: {SANDBOX_TRADES_FILE}")


# ========================
# main
# ========================

def main() -> None:
    print("=== Multi-Asset Crypto Sandbox (Binance Spot Testnet, 1D, 100K) ===")
    print(f"EXECUTE_ON_TESTNET = {EXECUTE_ON_TESTNET}")
    print(f"טווח נתונים: {START_DATE} עד {END_DATE} (UTC)")
    run_crypto_sandbox()
    print("הסנדבוקס הסתיים. בדוק את קבצי ה-CSV בתיקיית results_multi.")


if __name__ == "__main__":
    main()
