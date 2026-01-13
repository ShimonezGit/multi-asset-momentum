#!/usr/bin/env python3
# coding: utf-8
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import ccxt

# =========================
# פרמטרים כלליים
# =========================

LOOKBACK_DAYS = 120
today_utc = datetime.utcnow().date()
start_dt = today_utc - timedelta(days=LOOKBACK_DAYS)
end_dt = today_utc

START_DATE = start_dt.strftime("%Y-%m-%d")
END_DATE = end_dt.strftime("%Y-%m-%d")
TIMEFRAME_CRYPTO = "1d"

INITIAL_CAPITAL = 100000.0
CRYPTO_BENCHMARK = "BTC/USDT"
CRYPTO_ALT_SYMBOLS = [
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
MOMENTUM_THRESHOLD = 0.02  # יותר אגרסיבי כדי שיווצרו עסקאות
MAX_POSITIONS = 5
SKIP_TREND_FILTER = True   # מתעלם מטרנד אם צריך פעילות

RESULTS_DIR = "results_multi"
SANDBOX_TRADES_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_trades.csv")
SANDBOX_EQUITY_FILE = os.path.join(RESULTS_DIR, "crypto_sandbox_equity.csv")

EXECUTE_ON_TESTNET = True
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


# =========================
# חיבור לבורסה
# =========================

def init_binance_real() -> ccxt.binance:
    # דאטה מ-Binance Real
    return ccxt.binance({"enableRateLimit": True})


def init_binance_testnet() -> ccxt.binance:
    # הזמנות ל-Binance Spot Testnet
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        raise RuntimeError("חסר BINANCE_TESTNET_API_KEY או BINANCE_TESTNET_SECRET_KEY ב-env.")
    exchange = ccxt.binance(
        {
            "apiKey": BINANCE_TESTNET_API_KEY,
            "secret": BINANCE_TESTNET_SECRET_KEY,
            "enableRateLimit": True,
        }
    )
    exchange.set_sandbox_mode(True)
    return exchange


# =========================
# משיכת OHLCV
# =========================

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
        all_data, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df[["open", "high", "low", "close", "volume"]].copy()


def fetch_crypto_universe(
    exchange: ccxt.binance,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    print("טוען רשימת מרקטים מ-Binance Real...")
    markets = exchange.load_markets()
    available_symbols = set(markets.keys())

    if CRYPTO_BENCHMARK not in available_symbols:
        raise RuntimeError(f"Benchmark {CRYPTO_BENCHMARK} לא קיים במרקטים.")

    start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
    end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)

    print(f"מוריד {CRYPTO_BENCHMARK} {START_DATE} -> {END_DATE}...")
    btc_df = fetch_ohlcv_for_symbol(
        exchange, CRYPTO_BENCHMARK, TIMEFRAME_CRYPTO, start_ms, end_ms
    )
    if btc_df.empty:
        raise RuntimeError("לא נמצאו נתוני OHLCV עבור BTC/USDT בטווח המבוקש.")

    alt_data: Dict[str, pd.DataFrame] = {}
    for alt in CRYPTO_ALT_SYMBOLS:
        if alt not in available_symbols:
            print(f"{alt} – לא קיים במרקטים. מדלג.")
            continue
        print(f"מוריד {alt}...")
        df = fetch_ohlcv_for_symbol(exchange, alt, TIMEFRAME_CRYPTO, start_ms, end_ms)
        if df.empty:
            print(f"{alt} – אין נתוני OHLCV בטווח. מדלג.")
            continue
        alt_data[alt] = df

    if not alt_data:
        print("אזהרה: אין אלטים עם נתונים. הסנדבוקס יעבוד רק על BTC/USDT.")
    return btc_df, alt_data


# =========================
# אינדיקטורים
# =========================

def add_trend_and_momentum(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ma_trend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trend_up"] = out["close"] > out["ma_trend"]
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


# =========================
# ביצוע הזמנות
# =========================

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


def append_trade_log(log_entry: SandboxTradeLog) -> None:
    if log_entry is None:
        return
    os.makedirs(RESULTS_DIR, exist_ok=True)
    row_df = pd.DataFrame([asdict(log_entry)])
    if not os.path.exists(SANDBOX_TRADES_FILE):
        row_df.to_csv(SANDBOX_TRADES_FILE, index=False)
    else:
        row_df.to_csv(SANDBOX_TRADES_FILE, mode="a", header=False, index=False)


# =========================
# לוגיקת סנדבוקס
# =========================

def run_crypto_sandbox() -> None:
    print("=== Crypto Sandbox: Real Data + Testnet Execution ===")
    print(f"טווח: {START_DATE} -> {END_DATE}")
    print(f"פרמטרים: MA{TREND_MA_WINDOW}, Mom{MOMENTUM_LOOKBACK}, Exit{EXIT_LOOKBACK}, Thresh{MOMENTUM_THRESHOLD}, Max{MAX_POSITIONS}")

    exchange_data = init_binance_real()
    exchange_exec = init_binance_testnet()

    print("טוען מרקטים מ-Binance Real...")
    btc_raw, alts_raw = fetch_crypto_universe(exchange_data)

    # הוספת אינדיקטורים
    btc = add_trend_and_momentum(btc_raw)
    alt_data: Dict[str, pd.DataFrame] = {}
    for sym, df in alts_raw.items():
        alt_data[sym] = add_trend_and_momentum(df)

    universe: Dict[str, pd.DataFrame] = {CRYPTO_BENCHMARK: btc}
    universe.update(alt_data)

    calendar = build_calendar(btc, alt_data)
    closes = build_matrix(calendar, universe, "close")
    momentum = build_matrix(calendar, universe, "ret_mom")
    exit_ret = build_matrix(calendar, universe, "ret_exit")
    trend_series = btc["trend_up"].reindex(calendar).ffill().fillna(False)

    equity = INITIAL_CAPITAL
    positions: Dict[str, PositionState] = {}
    equity_records: List[Dict[str, float]] = []

    print("מתחיל לולאה על הימים...")

    for current_dt in calendar:
        prices_today = closes.loc[current_dt]

        # יציאות (EXIT)
        for sym in list(positions.keys()):
            pos = positions[sym]
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount == 0:
                continue
            sym_exit = exit_ret.get(sym, pd.Series(dtype=float)).get(current_dt, 0.0)
            if sym_exit <= 0.0:
                continue
            side = "sell"
            amount = pos.amount
            log_entry = place_market_order(exchange_exec, sym, side, amount)
            if log_entry:
                append_trade_log(log_entry)
                equity += (log_entry.price - pos.entry_price) * log_entry.amount
                positions.pop(sym, None)

        # עדכון שווי תיק אחרי יציאות
        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount == 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value

        # פילטר טרנד – אם לא מדלגים ואם אין טרנד למעלה, מדלגים על כניסות
        if not SKIP_TREND_FILTER and not trend_series.loc[current_dt]:
            equity_records.append(
                {"date": current_dt.date(), "equity": float(total_equity)}
            )
            continue

        # כניסות/ריבאלנס
        mom_today = momentum.loc[current_dt]
        candidates = mom_today[mom_today > MOMENTUM_THRESHOLD].sort_values(ascending=False)
        selected = list(candidates.index[:MAX_POSITIONS])

        # אם אין בכלל פוזיציות ואין selected – נכנס ל-BTC כדי להכריח פעילות
        if len(positions) == 0 and len(selected) == 0 and CRYPTO_BENCHMARK in closes.columns:
            selected = [CRYPTO_BENCHMARK]

        desired_set = set(selected)

        # סגירת פוזיציות שלא ברשימה
        for sym in list(positions.keys()):
            if sym not in desired_set:
                pos = positions[sym]
                price = prices_today.get(sym, np.nan)
                if np.isnan(price) or pos.amount == 0:
                    continue
                side = "sell"
                amount = pos.amount
                log_entry = place_market_order(exchange_exec, sym, side, amount)
                if log_entry:
                    append_trade_log(log_entry)
                    equity += (log_entry.price - pos.entry_price) * log_entry.amount
                    positions.pop(sym, None)

        # עדכון אחרי יציאות "אילוציות"
        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount == 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value

        if len(desired_set) > 0:
            capital_per_position = total_equity / float(len(desired_set))
        else:
            capital_per_position = 0.0

        # ריבאלנס / כניסות
        for sym in desired_set:
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or price <= 0:
                continue
            current_amount = positions.get(sym, PositionState(sym, 0.0, 0.0)).amount
            target_amount = capital_per_position / price
            delta_amount = target_amount - current_amount

            # סף כדי לא לעשות פוזות מיקרוסקופיות
            if abs(delta_amount) * price < 10.0:
                continue

            if delta_amount > 0:
                side = "buy"
                amount = delta_amount
                est_cost = amount * price
                if est_cost > equity:
                    continue
                log_entry = place_market_order(exchange_exec, sym, side, amount)
                if log_entry:
                    append_trade_log(log_entry)
                    equity -= log_entry.price * log_entry.amount
                    new_amount = current_amount + log_entry.amount
                    if current_amount == 0:
                        new_entry = log_entry.price
                    else:
                        old_value = current_amount * positions[sym].entry_price
                        new_value = old_value + log_entry.price * log_entry.amount
                        new_entry = new_value / new_amount
                    positions[sym] = PositionState(sym, new_amount, new_entry)

            elif delta_amount < 0:
                side = "sell"
                amount = -delta_amount
                if sym not in positions or positions[sym].amount <= 0:
                    continue
                if amount > positions[sym].amount:
                    amount = positions[sym].amount
                log_entry = place_market_order(exchange_exec, sym, side, amount)
                if log_entry:
                    append_trade_log(log_entry)
                    pos = positions[sym]
                    equity += log_entry.price * log_entry.amount
                    new_amount = pos.amount - log_entry.amount
                    if new_amount <= 0:
                        positions.pop(sym, None)
                    else:
                        positions[sym] = PositionState(sym, new_amount, pos.entry_price)

        # עדכון equity יומי
        portfolio_value = 0.0
        for sym, pos in positions.items():
            price = prices_today.get(sym, np.nan)
            if np.isnan(price) or pos.amount == 0:
                continue
            portfolio_value += pos.amount * price
        total_equity = equity + portfolio_value
        equity_records.append(
            {"date": current_dt.date(), "equity": float(total_equity)}
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(SANDBOX_EQUITY_FILE, index=False)
    print(f"✅ נשמר: {SANDBOX_EQUITY_FILE}")
    if os.path.exists(SANDBOX_TRADES_FILE):
        print(f"✅ נשמר: {SANDBOX_TRADES_FILE}")
    else:
        print("⚠️ לא נוצר קובץ טריידים (אין עסקאות)")


def main() -> None:
    run_crypto_sandbox()


if __name__ == "__main__":
    main()
