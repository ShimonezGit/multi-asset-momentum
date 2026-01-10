#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import ccxt           # pip install ccxt
import yfinance as yf # pip install yfinance

# =========================
# קונפיגורציה כללית
# =========================

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"
TIMEFRAME_CRYPTO = "1d"

# הון התחלתי – 100,000$
INITIAL_CAPITAL = 100_000.0

# קריפטו – סל אלטים
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
CRYPTO_BENCHMARK = "BTC/USDT"

# מניות ארה"ב
US_STOCKS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
    "GOOGL",
    "AVGO",
    "AMD",
    "NFLX",
]
US_BENCHMARK = "SPY"

# מניות ישראל
IL_STOCKS = [
    "TEVA.TA",
    "LUMI.TA",
    "POLI.TA",
    "BEZQ.TA",
    "ICL.TA",
    "NVMI.TA",
    "MZTF.TA",
    "ENLT.TA",
    "ESLT.TA",
    "HARL.TA",
]
IL_BENCHMARK = "TA35.TA"

# פרמטרי אסטרטגיה
TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
MOMENTUM_THRESHOLD = 0.10
EXIT_LOOKBACK = 10
MAX_POSITIONS = 5

RESULTS_DIR = "results_multi"


# =========================
# מודלים
# =========================

@dataclass
class TradeRecord:
    date: datetime.date
    symbol: str
    side: str
    qty: float
    price: float
    value: float
    pnl: float
    pnl_pct: float


@dataclass
class SummaryRecord:
    market: str
    total_return_pct: float
    multiple: float
    max_drawdown_pct: float
    win_rate_pct: float
    num_trades: int
    benchmark_return_pct: float
    benchmark_multiple: float


# =========================
# דאטה – קריפטו
# =========================

class CryptoDataFetcher:
    def __init__(self):
        self.exchange = ccxt.binance()
        self.exchange.enableRateLimit = True

    def fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
        end_ms = int(pd.Timestamp(END_DATE).timestamp() * 1000)
        all_data = []
        since = start_ms

        while True:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME_CRYPTO, since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            last_ts = ohlcv[-1][0]
            if last_ts >= end_ms:
                break
            since = last_ts + 1

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(
            all_data,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("datetime", inplace=True)
        df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
        return df


# =========================
# דאטה – מניות (US & IL)
# =========================

def fetch_yf_history(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=(pd.to_datetime(END_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=False,
        )
        if df.empty:
            print(f"אזהרה: אין נתונים עבור {ticker}, מדלג.")
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "datetime"
        data[ticker] = df
    return data


# =========================
# אינדיקטורים
# =========================

def add_trend_and_momentum(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma_trend"] = df["close"].rolling(TREND_MA_WINDOW).mean()
    df["trend_up"] = df["close"] > df["ma_trend"]
    df["ret_1d"] = df["close"].pct_change()
    df["ret_mom"] = df["close"].pct_change(MOMENTUM_LOOKBACK)
    df["ret_exit"] = df["close"].pct_change(EXIT_LOOKBACK)
    return df


# =========================
# Generic Momentum Strategy
# =========================

class GenericMomentumStrategy:
    def __init__(
        self,
        benchmark_df: pd.DataFrame,
        asset_data: Dict[str, pd.DataFrame],
        market_name: str,
    ):
        self.benchmark_df = benchmark_df
        self.asset_data = asset_data
        self.market_name = market_name

        self.calendar = self._build_calendar()
        self.asset_closes = self._build_matrix("close")
        self.asset_mom = self._build_matrix("ret_mom")
        self.asset_exit = self._build_matrix("ret_exit")
        self.trend_series = self.benchmark_df["trend_up"].reindex(self.calendar).ffill().fillna(False)

    def _build_calendar(self) -> pd.DatetimeIndex:
        idx = self.benchmark_df.index
        for df in self.asset_data.values():
            idx = idx.union(df.index)
        idx = idx.sort_values()
        idx = idx[(idx >= START_DATE) & (idx <= END_DATE)]
        return idx

    def _build_matrix(self, col: str) -> pd.DataFrame:
        data = {}
        for sym, df in self.asset_data.items():
            ser = df[col].reindex(self.calendar).ffill()
            data[sym] = ser
        return pd.DataFrame(data, index=self.calendar)

    def run(self) -> Tuple[pd.DataFrame, List[TradeRecord]]:
        trades: List[TradeRecord] = []
        equity_records = []

        cash = INITIAL_CAPITAL
        positions: Dict[str, float] = {sym: 0.0 for sym in self.asset_data.keys()}
        entry_price: Dict[str, float] = {sym: 0.0 for sym in self.asset_data.keys()}

        for current_dt in self.calendar:
            prices_today = self.asset_closes.loc[current_dt]

            # יציאות על שבירת מומנטום
            portfolio_value = 0.0
            for sym in list(positions.keys()):
                qty = positions[sym]
                if qty == 0:
                    continue
                price = prices_today.get(sym, np.nan)
                if np.isnan(price):
                    continue
                ret_exit = self.asset_exit.loc[current_dt].get(sym, 0.0)
                if ret_exit <= 0.0:
                    ep = entry_price[sym] if entry_price[sym] > 0 else price
                    value = qty * price
                    pnl = (price - ep) * qty
                    pnl_pct = (price / ep - 1.0) if ep > 0 else 0.0

                    trades.append(TradeRecord(
                        date=current_dt.date(),
                        symbol=sym,
                        side="SELL_EXIT",
                        qty=qty,
                        price=price,
                        value=value,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                    ))

                    cash += value
                    positions[sym] = 0.0
                    entry_price[sym] = 0.0
                else:
                    portfolio_value += qty * price

            # כניסות/איזון רק אם טרנד חיובי
            if self.trend_series.loc[current_dt]:
                mom_today = self.asset_mom.loc[current_dt]
                candidates = mom_today[mom_today >= MOMENTUM_THRESHOLD].sort_values(ascending=False)
                selected = list(candidates.index)[:MAX_POSITIONS]
                desired = set(selected)

                # סגירת נכסים שלא ברשימה
                for sym in list(positions.keys()):
                    if sym not in desired and positions[sym] > 0:
                        price = prices_today.get(sym, np.nan)
                        if np.isnan(price):
                            continue
                        qty = positions[sym]
                        ep = entry_price[sym] if entry_price[sym] > 0 else price
                        value = qty * price
                        pnl = (price - ep) * qty
                        pnl_pct = (price / ep - 1.0) if ep > 0 else 0.0

                        trades.append(TradeRecord(
                            date=current_dt.date(),
                            symbol=sym,
                            side="SELL_TRIM",
                            qty=qty,
                            price=price,
                            value=value,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                        ))

                        cash += value
                        positions[sym] = 0.0
                        entry_price[sym] = 0.0

                portfolio_value = 0.0
                for sym in positions.keys():
                    qty = positions[sym]
                    if qty == 0:
                        continue
                    price = prices_today.get(sym, np.nan)
                    if np.isnan(price):
                        continue
                    portfolio_value += qty * price
                total_equity = cash + portfolio_value

                capital_per_position = total_equity / len(desired) if len(desired) > 0 else 0.0

                for sym in desired:
                    price = prices_today.get(sym, np.nan)
                    if np.isnan(price) or price <= 0:
                        continue
                    target_qty = capital_per_position / price
                    current_qty = positions.get(sym, 0.0)
                    delta_qty = target_qty - current_qty

                    if abs(delta_qty) * price < 1.0:
                        continue

                    if delta_qty > 0:
                        cost = delta_qty * price
                        if cost > cash:
                            continue
                        cash -= cost
                        new_qty = current_qty + delta_qty
                        if current_qty == 0:
                            new_ep = price
                        else:
                            old_value = current_qty * entry_price[sym]
                            new_value = old_value + cost
                            new_ep = new_value / new_qty
                        positions[sym] = new_qty
                        entry_price[sym] = new_ep

                        trades.append(TradeRecord(
                            date=current_dt.date(),
                            symbol=sym,
                            side="BUY",
                            qty=delta_qty,
                            price=price,
                            value=cost,
                            pnl=0.0,
                            pnl_pct=0.0,
                        ))
                    elif delta_qty < 0:
                        sell_qty = -delta_qty
                        if sell_qty > current_qty:
                            sell_qty = current_qty
                        revenue = sell_qty * price
                        cash += revenue
                        positions[sym] = current_qty - sell_qty
                        ep = entry_price[sym] if entry_price[sym] > 0 else price
                        pnl = (price - ep) * sell_qty
                        pnl_pct = (price / ep - 1.0) if ep > 0 else 0.0

                        trades.append(TradeRecord(
                            date=current_dt.date(),
                            symbol=sym,
                            side="SELL_REBAL",
                            qty=sell_qty,
                            price=price,
                            value=revenue,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                        ))

                        if positions[sym] <= 0:
                            positions[sym] = 0.0
                            entry_price[sym] = 0.0

            # equity יומי
            portfolio_value = 0.0
            for sym in positions.keys():
                qty = positions[sym]
                if qty == 0:
                    continue
                price = prices_today.get(sym, np.nan)
                if np.isnan(price):
                    continue
                portfolio_value += qty * price
            total_equity = cash + portfolio_value
            equity_records.append({"date": current_dt.date(), "equity": total_equity})

        equity_df = pd.DataFrame(equity_records)
        equity_df.set_index("date", inplace=True)
        return equity_df, trades


# =========================
# מדדים
# =========================

def compute_max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min() * 100.0)


def compute_trade_stats(trades: List[TradeRecord]) -> Tuple[float, float, int]:
    if not trades:
        return 0.0, 0.0, 0
    realized = [t.pnl for t in trades if t.pnl != 0.0]
    if not realized:
        return 0.0, 0.0, 0
    wins = [p for p in realized if p > 0]
    win_rate = len(wins) / len(realized) * 100.0
    total_pnl = sum(realized)
    return total_pnl, win_rate, len(realized)


def build_benchmark_equity(bench_close: pd.Series) -> pd.Series:
    bench_equity = (bench_close / bench_close.iloc[0]) * INITIAL_CAPITAL
    bench_equity.index = bench_close.index
    return bench_equity


def build_summary(
    market_name: str,
    equity_df: pd.DataFrame,
    trades: List[TradeRecord],
    benchmark_df: pd.DataFrame,
) -> SummaryRecord:
    equity = equity_df["equity"]
    final_equity = equity.iloc[-1]
    total_return_pct = (final_equity / INITIAL_CAPITAL - 1.0) * 100.0
    multiple = final_equity / INITIAL_CAPITAL
    max_dd_pct = compute_max_drawdown(equity)
    _, win_rate_pct, num_trades = compute_trade_stats(trades)

    bench_close = benchmark_df["close"]
    bench_start = bench_close.iloc[0]
    bench_end = bench_close.iloc[-1]
    bench_return_pct = (bench_end / bench_start - 1.0) * 100.0
    bench_mult = bench_end / bench_start

    return SummaryRecord(
        market=market_name,
        total_return_pct=total_return_pct,
        multiple=multiple,
        max_drawdown_pct=max_dd_pct,
        win_rate_pct=win_rate_pct,
        num_trades=num_trades,
        benchmark_return_pct=bench_return_pct,
        benchmark_multiple=bench_mult,
    )


# =========================
# שמירת תוצאות
# =========================

def save_equity_curve(name: str, equity_df: pd.DataFrame, bench_equity: pd.Series):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    df = equity_df.copy()
    df = df.sort_index()
    bench_equity = bench_equity.reindex(df.index).ffill()
    df["benchmark_equity"] = bench_equity
    path = os.path.join(RESULTS_DIR, f"{name}_equity_curve.csv")
    df.to_csv(path)
    print(f"נשמר קובץ עקומת הון ({name}): {path}")


def save_summary(summaries: List[SummaryRecord]):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, "multi_summary.csv")
    df = pd.DataFrame([asdict(s) for s in summaries])
    df.to_csv(path, index=False)
    print(f"נשמר קובץ סיכום: {path}")


# =========================
# main – שלושת השווקים
# =========================

def main():
    print("מתחיל Multi-Asset Momentum Backtest (100K initial capital)...")

    summaries: List[SummaryRecord] = []

    # --- קריפטו ---
    print("\n=== קריפטו – Binance ===")
    crypto_fetcher = CryptoDataFetcher()
    btc_raw = crypto_fetcher.fetch_ohlcv(CRYPTO_BENCHMARK)
    if btc_raw.empty:
        print("שגיאה: אין נתוני BTC/USDT.")
    else:
        btc_df = add_trend_and_momentum(btc_raw)

        alt_data: Dict[str, pd.DataFrame] = {}
        for sym in CRYPTO_ALT_SYMBOLS:
            print(f"מוריד נתוני אלט: {sym} ...")
            df = crypto_fetcher.fetch_ohlcv(sym)
            if df.empty:
                print(f"אזהרה: אין נתונים עבור {sym}, מדלג.")
                continue
            df = add_trend_and_momentum(df)
            key = sym.replace("/", "")
            alt_data[key] = df

        if alt_data:
            strat = GenericMomentumStrategy(btc_df, alt_data, "CRYPTO")
            crypto_equity, crypto_trades = strat.run()
            crypto_summary = build_summary("CRYPTO", crypto_equity, crypto_trades, btc_df)
            crypto_bench_eq = build_benchmark_equity(btc_df["close"])
            summaries.append(crypto_summary)
            print(
                f"CRYPTO תשואה: {crypto_summary.total_return_pct:.2f}% "
                f"(Multiple {crypto_summary.multiple:.2f}x), "
                f"MaxDD {crypto_summary.max_drawdown_pct:.2f}%"
            )
            save_equity_curve("crypto", crypto_equity, crypto_bench_eq)

    # --- US ---
    print("\n=== מניות ארה\"ב – Yahoo Finance ===")
    us_data = fetch_yf_history([US_BENCHMARK] + US_STOCKS)
    if US_BENCHMARK not in us_data:
        print("שגיאה: אין נתונים ל-SPY.")
    else:
        spy_df = add_trend_and_momentum(us_data[US_BENCHMARK])
        us_assets: Dict[str, pd.DataFrame] = {}
        for ticker in US_STOCKS:
            df = us_data.get(ticker)
            if df is None or df.empty:
                print(f"אזהרה: אין נתונים עבור {ticker}, מדלג.")
                continue
            df = add_trend_and_momentum(df)
            us_assets[ticker] = df

        if us_assets:
            strat = GenericMomentumStrategy(spy_df, us_assets, "US")
            us_equity, us_trades = strat.run()
            us_summary = build_summary("US", us_equity, us_trades, spy_df)
            us_bench_eq = build_benchmark_equity(spy_df["close"])
            summaries.append(us_summary)
            print(
                f"US תשואה: {us_summary.total_return_pct:.2f}% "
                f"(Multiple {us_summary.multiple:.2f}x), "
                f"MaxDD {us_summary.max_drawdown_pct:.2f}%"
            )
            save_equity_curve("us", us_equity, us_bench_eq)

    # --- IL ---
    print("\n=== מניות ישראל – Yahoo Finance ===")
    il_data = fetch_yf_history([IL_BENCHMARK] + IL_STOCKS)
    if IL_BENCHMARK not in il_data:
        print("שגיאה: אין נתונים ל-TA35.TA.")
    else:
        ta_df = add_trend_and_momentum(il_data[IL_BENCHMARK])
        il_assets: Dict[str, pd.DataFrame] = {}
        for ticker in IL_STOCKS:
            df = il_data.get(ticker)
            if df is None or df.empty:
                print(f"אזהרה: אין נתונים עבור {ticker}, מדלג.")
                continue
            df = add_trend_and_momentum(df)
            il_assets[ticker] = df

        if il_assets:
            strat = GenericMomentumStrategy(ta_df, il_assets, "IL")
            il_equity, il_trades = strat.run()
            il_summary = build_summary("IL", il_equity, il_trades, ta_df)
            il_bench_eq = build_benchmark_equity(ta_df["close"])
            summaries.append(il_summary)
            print(
                f"IL תשואה: {il_summary.total_return_pct:.2f}% "
                f"(Multiple {il_summary.multiple:.2f}x), "
                f"MaxDD {il_summary.max_drawdown_pct:.2f}%"
            )
            save_equity_curve("il", il_equity, il_bench_eq)

    if summaries:
        save_summary(summaries)

    print("\nסיום Multi-Asset Backtest (100K).")


if __name__ == "__main__":
    main()
