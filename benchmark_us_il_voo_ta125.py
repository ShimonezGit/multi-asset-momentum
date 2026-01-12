#!/usr/bin/env python3
# coding: utf-8

import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"
INITIAL_CAPITAL = 100000.0

RESULTS_DIR = "results_us_il_voo_ta125"

US_BENCHMARK = "VOO"
US_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "TSLA", "GOOGL", "AVGO", "AMD", "NFLX",
]

IL_BENCHMARK = "^TA125.TA"
IL_STOCKS = [
    "TEVA.TA", "LUMI.TA", "POLI.TA", "BEZQ.TA", "ICL.TA",
    "NVMI.TA", "MZTF.TA", "ENLT.TA", "ESLT.TA", "HARL.TA",
]

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
EXIT_LOOKBACK = 10
MOMENTUM_THRESHOLD = 0.10
MAX_POSITIONS = 5
MIN_TRADE_VALUE = 10.0

@dataclass
class TradeRecord:
    date: str
    symbol: str
    side: str
    qty: float
    price: float
    value: float
    pnl: float
    pnlpct: float

@dataclass
class PositionState:
    symbol: str
    amount: float
    costbasis: float

def fetch_yf_history(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    start = pd.to_datetime(START_DATE)
    end = (pd.to_datetime(END_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for ticker in tickers:
        print(f"Downloading {ticker} ...")
        try:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
        except Exception as e:
            print(f"{ticker}: שגיאה בהורדה ({e}), מדלג.")
            continue
        if df is None or df.empty:
            print(f"{ticker}: אין דאטה, מדלג.")
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "datetime"
        data[ticker] = df
    return data

def add_trend_and_momentum(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["matrend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trendup"] = out["close"] > out["matrend"]
    out["retmom"] = out["close"].pct_change(MOMENTUM_LOOKBACK)
    out["retexit"] = out["close"].pct_change(EXIT_LOOKBACK)
    return out

def build_calendar(benchmark_df: pd.DataFrame, assets: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    idx = benchmark_df.index
    for df in assets.values():
        idx = idx.union(df.index)
    idx = idx.sort_values()
    idx = idx[(idx >= pd.to_datetime(START_DATE)) & (idx <= pd.to_datetime(END_DATE))]
    return idx

def build_matrix(calendar: pd.DatetimeIndex, data: Dict[str, pd.DataFrame], col: str) -> pd.DataFrame:
    series_map = {}
    for sym, df in data.items():
        if col in df.columns:
            series_map[sym] = df[col].reindex(calendar).ffill()
    return pd.DataFrame(series_map, index=calendar)

def run_momentum_paper(
    market_name: str,
    benchmark_symbol: str,
    universe_symbols: List[str],
    benchmark_label: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("-" * 60)
    print(f"{market_name} Momentum Paper Trading {START_DATE} - {END_DATE}")
    print(f"Benchmark: {benchmark_symbol}, Universe size target: {len(universe_symbols)}")
    print("-" * 60)

    tickers = [benchmark_symbol] + universe_symbols
    data = fetch_yf_history(tickers)

    bench_df = data.get(benchmark_symbol)
    if bench_df is None or bench_df.empty:
        raise RuntimeError(f"Benchmark {benchmark_symbol} לא חזר מ-yfinance או ריק.")

    bench_df = add_trend_and_momentum(bench_df)

    asset_data: Dict[str, pd.DataFrame] = {}
    for sym in universe_symbols:
        df = data.get(sym)
        if df is None or df.empty:
            print(f"{sym}: אין דאטה, מדלג מה-universe.")
            continue
        asset_data[sym] = add_trend_and_momentum(df)

    if not asset_data:
        raise RuntimeError(f"{market_name}: אין universe לשחק איתו.")

    calendar = build_calendar(bench_df, asset_data)
    closes = build_matrix(calendar, asset_data, "close")
    mom = build_matrix(calendar, asset_data, "retmom")
    exit_ret = build_matrix(calendar, asset_data, "retexit")

    bench_close = bench_df["close"].reindex(calendar).ffill()
    if bench_close.isna().all():
        raise RuntimeError(f"{market_name}: benchmark close כולו NaN.")

    first_price = bench_close.dropna().iloc[0]
    bench_shares = INITIAL_CAPITAL / first_price
    bench_equity_series = bench_shares * bench_close

    trend_series = bench_df["trendup"].reindex(calendar).ffill().fillna(False)

    cash = INITIAL_CAPITAL
    positions: Dict[str, PositionState] = {}
    trades: List[TradeRecord] = []
    equity_records: List[Dict[str, float]] = []

    print(f"{market_name}: trading over {len(calendar)} days ...")

    for current_dt in calendar:
        prices = closes.loc[current_dt] if not closes.empty else pd.Series(dtype=float)

        for sym in list(positions.keys()):
            if sym not in prices or np.isnan(prices[sym]):
                continue
            pos = positions[sym]
            exitsignal = exit_ret.get(sym, pd.Series(dtype=float)).get(current_dt, 0.0)
            if exitsignal <= 0.0:
                continue
            sell_value = pos.amount * prices[sym]
            pnl = sell_value - pos.costbasis
            pnlpct = pnl / pos.costbasis if pos.costbasis != 0 else 0.0
            trades.append(
                TradeRecord(
                    date=current_dt.date().isoformat(),
                    symbol=sym,
                    side="SELLEXIT",
                    qty=float(pos.amount),
                    price=float(prices[sym]),
                    value=float(sell_value),
                    pnl=float(pnl),
                    pnlpct=float(pnlpct),
                )
            )
            cash += sell_value
            positions.pop(sym)

        port_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + port_value
        bench_equity_val = float(bench_equity_series.get(current_dt, np.nan))

        if not trend_series.loc[current_dt]:
            equity_records.append(
                {
                    "date": current_dt.date(),
                    "equity": total_equity,
                    "benchmarkequity": bench_equity_val,
                }
            )
            continue

        if mom.empty:
            equity_records.append(
                {
                    "date": current_dt.date(),
                    "equity": total_equity,
                    "benchmarkequity": bench_equity_val,
                }
            )
            continue

        mom_today = mom.loc[current_dt]
        candidates = mom_today[mom_today > MOMENTUM_THRESHOLD].sort_values(ascending=False)
        desired_set = set(list(candidates.index[:MAX_POSITIONS]))

        for sym in list(positions.keys()):
            if (sym not in desired_set) or (sym not in prices) or np.isnan(prices[sym]):
                pos = positions[sym]
                sell_value = pos.amount * prices.get(sym, 0.0)
                pnl = sell_value - pos.costbasis
                pnlpct = pnl / pos.costbasis if pos.costbasis != 0 else 0.0
                trades.append(
                    TradeRecord(
                        date=current_dt.date().isoformat(),
                        symbol=sym,
                        side="SELLTRIM",
                        qty=float(pos.amount),
                        price=float(prices.get(sym, 0.0)),
                        value=float(sell_value),
                        pnl=float(pnl),
                        pnlpct=float(pnlpct),
                    )
                )
                cash += sell_value
                positions.pop(sym)

        port_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + port_value

        if not desired_set:
            equity_records.append(
                {
                    "date": current_dt.date(),
                    "equity": total_equity,
                    "benchmarkequity": bench_equity_val,
                }
            )
            continue

        target_per_position = total_equity / len(desired_set)

        for sym in desired_set:
            if sym not in prices or np.isnan(prices[sym]) or prices[sym] <= 0.0:
                continue

            current_value = 0.0
            if sym in positions:
                current_value = positions[sym].amount * prices[sym]

            delta_value = target_per_position - current_value
            if abs(delta_value) < MIN_TRADE_VALUE:
                continue

            if delta_value > 0:
                buy_value = min(delta_value, cash * 0.99)
                if buy_value < MIN_TRADE_VALUE:
                    continue
                buy_amount = buy_value / prices[sym]
                cash -= buy_value
                if sym in positions:
                    pos = positions[sym]
                    new_amount = pos.amount + buy_amount
                    new_cost = pos.costbasis + buy_value
                    positions[sym] = PositionState(sym, new_amount, new_cost)
                else:
                    positions[sym] = PositionState(sym, buy_amount, buy_value)
                trades.append(
                    TradeRecord(
                        date=current_dt.date().isoformat(),
                        symbol=sym,
                        side="BUY",
                        qty=float(buy_amount),
                        price=float(prices[sym]),
                        value=float(buy_value),
                        pnl=0.0,
                        pnlpct=0.0,
                    )
                )
            elif delta_value < 0 and sym in positions:
                pos = positions[sym]
                sell_value = min(-delta_value, pos.amount * prices[sym])
                if sell_value < MIN_TRADE_VALUE:
                    continue
                sell_amount = sell_value / prices[sym]
                portion_sold = sell_amount / pos.amount if pos.amount > 0 else 0.0
                cost_sold = pos.costbasis * portion_sold
                pnl = sell_value - cost_sold
                pnlpct = pnl / cost_sold if cost_sold != 0 else 0.0
                cash += sell_value
                new_amount = pos.amount - sell_amount
                new_cost = pos.costbasis - cost_sold
                if new_amount < 1e-4:
                    positions.pop(sym)
                else:
                    positions[sym] = PositionState(sym, new_amount, new_cost)
                trades.append(
                    TradeRecord(
                        date=current_dt.date().isoformat(),
                        symbol=sym,
                        side="SELLREBAL",
                        qty=float(sell_amount),
                        price=float(prices[sym]),
                        value=float(sell_value),
                        pnl=float(pnl),
                        pnlpct=float(pnlpct),
                    )
                )

        port_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + port_value
        equity_records.append(
            {
                "date": current_dt.date(),
                "equity": total_equity,
                "benchmarkequity": bench_equity_val,
            }
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    equity_df = pd.DataFrame(equity_records)
    equity_path = os.path.join(RESULTS_DIR, f"{market_name.lower()}_paperequity.csv")
    equity_df.to_csv(equity_path, index=False)

    trades_df = pd.DataFrame(asdict(t) for t in trades)
    trades_path = os.path.join(RESULTS_DIR, f"{market_name.lower()}_papertrades.csv")
    trades_df.to_csv(trades_path, index=False)

    print(f"{market_name}: כתבנו {equity_path} ו-{trades_path}")
    return equity_df, trades_df

def compute_max_drawdown(equity: pd.Series) -> float:
    rollmax = equity.cummax()
    dd = (equity - rollmax) / rollmax
    return float(dd.min() * 100.0)

def compute_winrate(trades_df: pd.DataFrame) -> float:
    if trades_df.empty or "pnl" not in trades_df.columns or "side" not in trades_df.columns:
        return 0.0
    closed = trades_df[trades_df["side"].str.startswith("SELL")]
    if closed.empty:
        return 0.0
    wins = (closed["pnl"] > 0).sum()
    return float(wins / len(closed) * 100.0)

def summarize_market(market_name: str, equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> None:
    eq = equity_df["equity"].astype(float)
    start_equity = float(eq.iloc[0])
    end_equity = float(eq.iloc[-1])
    total_return_pct = (end_equity / start_equity - 1.0) * 100.0 if start_equity != 0 else 0.0
    max_dd_pct = compute_max_drawdown(eq)
    winrate_pct = compute_winrate(trades_df)
    n_trades = len(trades_df)

    print("=" * 60)
    print(f"{market_name} SUMMARY")
    print(f"Start Equity: {start_equity:,.2f}")
    print(f"End   Equity: {end_equity:,.2f}")
    print(f"Total Return: {total_return_pct:.2f}%")
    print(f"Max Drawdown: {max_dd_pct:.2f}%")
    print(f"Winrate:      {winrate_pct:.2f}%")
    print(f"#Trades:      {n_trades}")
    print("=" * 60)

def main() -> None:
    print(f"Running Momentum Paper Trading with US vs VOO, IL vs TA-125 ({IL_BENCHMARK})")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Initial capital per market: {INITIAL_CAPITAL:,.0f}")
    print("-" * 60)

    us_equity, us_trades = run_momentum_paper(
        market_name="US_VOO",
        benchmark_symbol=US_BENCHMARK,
        universe_symbols=US_STOCKS,
        benchmark_label="VOO",
    )

    il_equity, il_trades = run_momentum_paper(
        market_name="IL_TA125",
        benchmark_symbol=IL_BENCHMARK,
        universe_symbols=IL_STOCKS,
        benchmark_label="TA125",
    )

    summarize_market("US_VOO", us_equity, us_trades)
    summarize_market("IL_TA125", il_equity, il_trades)

    print("CSV files written under:", RESULTS_DIR)
    print("US: us_voo_paperequity.csv, us_voo_papertrades.csv")
    print("IL: il_ta125_paperequity.csv, il_ta125_papertrades.csv")
    print("סיימנו את הריצה המלאה מול הבנצ׳מרקים VOO / TA-125.")

if __name__ == "__main__":
    main()
