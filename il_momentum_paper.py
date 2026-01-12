#!/usr/bin/env python3
# coding: utf-8

"""
il_momentum_paper.py
Paper Trading למומנטום על מניות ישראל (TA-35 + 10 מניות) בסגנון ה-US bot.
Universe ופרמטרים זהים ל-backtest הרב-נכסי.
"""

import os
from dataclasses import dataclass, asdict
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf


# -----------------------
# קונפיגורציה
# -----------------------

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"
INITIAL_CAPITAL = 100000.0

IL_BENCHMARK = "TA35.TA"
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

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
EXIT_LOOKBACK = 10
MOMENTUM_THRESHOLD = 0.10
MAX_POSITIONS = 5

RESULTS_DIR = "results_multi"
PAPER_TRADES_FILE = os.path.join(RESULTS_DIR, "il_paper_trades.csv")
PAPER_EQUITY_FILE = os.path.join(RESULTS_DIR, "il_paper_equity.csv")


# -----------------------
# דאטהקלאסים
# -----------------------

@dataclass
class TradeRecord:
    date: str
    symbol: str
    side: str
    qty: float
    price: float
    value: float
    pnl: float
    pnl_pct: float


@dataclass
class PositionState:
    symbol: str
    amount: float
    cost_basis: float  # סך עלות דולרית היסטורית (לא מחיר ממוצע)


# -----------------------
# פונקציות דאטה ואינדיקטורים
# -----------------------

def fetch_yf_history(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """הורדת נתונים מ-Yahoo Finance לכל הטיקרים ברשימה."""
    data: Dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        print(f"מוריד {ticker}...")
        df = yf.download(
            ticker,
            start=START_DATE,
            end=(pd.to_datetime(END_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=False,
        )
        if df.empty:
            print(f"{ticker} ריק, מדלג.")
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "datetime"
        data[ticker] = df
    return data


def add_trend_and_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """הוספת MA100, טרנד, מומנטום ו-exit."""
    out = df.copy()
    out["ma_trend"] = out["close"].rolling(TREND_MA_WINDOW).mean()
    out["trend_up"] = out["close"] > out["ma_trend"]
    out["ret_mom"] = out["close"].pct_change(MOMENTUM_LOOKBACK)
    out["ret_exit"] = out["close"].pct_change(EXIT_LOOKBACK)
    return out


def build_calendar(benchmark_df: pd.DataFrame, assets: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    idx = benchmark_df.index
    for df in assets.values():
        idx = idx.union(df.index)
    idx = idx.sort_values()
    idx = idx[(idx >= pd.to_datetime(START_DATE)) & (idx <= pd.to_datetime(END_DATE))]
    return idx


def build_matrix(calendar: pd.DatetimeIndex,
                 data: Dict[str, pd.DataFrame],
                 col: str) -> pd.DataFrame:
    series_map = {}
    for sym, df in data.items():
        if col in df.columns:
            series_map[sym] = df[col].reindex(calendar).ffill()
    return pd.DataFrame(series_map, index=calendar)


# -----------------------
# Paper Trading לישראל
# -----------------------

def run_il_paper():
    # מחיקת קבצי תוצאות קודמים כדי שלא יתערבבו
    if os.path.exists(PAPER_TRADES_FILE):
        os.remove(PAPER_TRADES_FILE)
    if os.path.exists(PAPER_EQUITY_FILE):
        os.remove(PAPER_EQUITY_FILE)

    # דאטה
    tickers = [IL_BENCHMARK] + IL_STOCKS
    data = fetch_yf_history(tickers)

    if IL_BENCHMARK not in data:
        raise RuntimeError("TA35.TA לא חזר מ-Yahoo Finance, אי אפשר להמשיך.")

    bench_df = add_trend_and_momentum(data[IL_BENCHMARK])
    asset_data: Dict[str, pd.DataFrame] = {}
    for sym in IL_STOCKS:
        df = data.get(sym)
        if df is None or df.empty:
            print(f"{sym} – אין דאטה, מדלג.")
            continue
        asset_data[sym] = add_trend_and_momentum(df)

    if not asset_data:
        raise RuntimeError("אין אף מניה ישראלית עם דאטה, עצירה.")

    calendar = build_calendar(bench_df, asset_data)
    closes = build_matrix(calendar, asset_data, "close")
    mom = build_matrix(calendar, asset_data, "ret_mom")
    exit_ret = build_matrix(calendar, asset_data, "ret_exit")
    trend_series = bench_df["trend_up"].reindex(calendar).ffill().fillna(False)

    cash = INITIAL_CAPITAL
    positions: Dict[str, PositionState] = {}
    trades: List[TradeRecord] = []
    equity_records: List[Dict[str, float]] = []

    print(f"\nמריץ IL Paper Trading על {len(calendar)} ימים...")

    for current_dt in calendar:
        prices = closes.loc[current_dt]

        # סגירת פוזיציות לפי exit
        for sym in list(positions.keys()):
            if sym not in prices or np.isnan(prices[sym]):
                continue
            pos = positions[sym]
            exitsignal = exit_ret.get(sym, pd.Series(dtype=float)).get(current_dt, 0.0)
            if exitsignal <= 0.0:
                continue
            sell_value = pos.amount * prices[sym]
            pnl = sell_value - pos.cost_basis
            pnl_pct = pnl / pos.cost_basis if pos.cost_basis != 0 else 0.0
            trades.append(
                TradeRecord(
                    date=current_dt.date().isoformat(),
                    symbol=sym,
                    side="SELLEXIT",
                    qty=pos.amount,
                    price=float(prices[sym]),
                    value=float(sell_value),
                    pnl=float(pnl),
                    pnl_pct=float(pnl_pct),
                )
            )
            cash += sell_value
            positions.pop(sym)

        # ערך פורטפוליו
        portfolio_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + portfolio_value

        # אם אין טרנד – מחזיקים רק cash
        if not trend_series.loc[current_dt]:
            equity_records.append({"date": current_dt.date(), "equity": total_equity})
            continue

        # בחירת מועמדי מומנטום
        mom_today = mom.loc[current_dt]
        candidates = mom_today[mom_today > MOMENTUM_THRESHOLD].sort_values(ascending=False)
        desired_set = set(list(candidates.index[:MAX_POSITIONS]))

        # סגירת מניות שלא ברשימת desired
        for sym in list(positions.keys()):
            if sym not in desired_set or sym not in prices or np.isnan(prices[sym]):
                pos = positions[sym]
                sell_value = pos.amount * prices.get(sym, 0.0)
                pnl = sell_value - pos.cost_basis
                pnl_pct = pnl / pos.cost_basis if pos.cost_basis != 0 else 0.0
                trades.append(
                    TradeRecord(
                        date=current_dt.date().isoformat(),
                        symbol=sym,
                        side="SELLTRIM",
                        qty=pos.amount,
                        price=float(prices.get(sym, 0.0)),
                        value=float(sell_value),
                        pnl=float(pnl),
                        pnl_pct=float(pnl_pct),
                    )
                )
                cash += sell_value
                positions.pop(sym)

        # עדכון equity אחרי הטרימינג
        portfolio_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + portfolio_value

        if not desired_set:
            equity_records.append({"date": current_dt.date(), "equity": total_equity})
            continue

        # equal weight allocation
        target_value_per_position = total_equity / len(desired_set)

        for sym in desired_set:
            if sym not in prices or np.isnan(prices[sym]) or prices[sym] <= 0:
                continue

            current_value = 0.0
            if sym in positions:
                current_value = positions[sym].amount * prices[sym]

            delta_value = target_value_per_position - current_value

            if abs(delta_value) < 10:  # פילטר לרעש קטן
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

                trades.append(
                    TradeRecord(
                        date=current_dt.date().isoformat(),
                        symbol=sym,
                        side="BUY",
                        qty=float(buy_amount),
                        price=float(prices[sym]),
                        value=float(buy_value),
                        pnl=0.0,
                        pnl_pct=0.0,
                    )
                )

            elif delta_value < 0 and sym in positions:
                pos = positions[sym]
                sell_value = min(-delta_value, pos.amount * prices[sym])
                sell_amount = sell_value / prices[sym]

                # חישוב חלק יחסי מה-cost לצורך PnL
                portion_sold = sell_amount / pos.amount if pos.amount > 0 else 0.0
                cost_sold = pos.cost_basis * portion_sold
                pnl = sell_value - cost_sold
                pnl_pct = pnl / cost_sold if cost_sold != 0 else 0.0

                cash += sell_value
                new_amount = pos.amount - sell_amount
                new_cost = pos.cost_basis - cost_sold

                if new_amount < 0.0001:
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
                        pnl_pct=float(pnl_pct),
                    )
                )

        # עדכון equity בסוף היום
        portfolio_value = sum(
            pos.amount * prices.get(sym, 0.0)
            for sym, pos in positions.items()
            if sym in prices and not np.isnan(prices[sym])
        )
        total_equity = cash + portfolio_value
        equity_records.append({"date": current_dt.date(), "equity": total_equity})

    # שמירת תוצאות
    os.makedirs(RESULTS_DIR, exist_ok=True)

    eq_df = pd.DataFrame(equity_records)
    eq_df.to_csv(PAPER_EQUITY_FILE, index=False)

    trades_df = pd.DataFrame(asdict(t) for t in trades)
    trades_df.to_csv(PAPER_TRADES_FILE, index=False)

    # חישוב סטטיסטיקות
    print("\n" + "=" * 60)
    print(f"נשמר: {PAPER_EQUITY_FILE}")
    print(f"נשמר: {PAPER_TRADES_FILE}")
    print("\nסטטיסטיקות IL:")
    print(f"  טריידים: {len(trades_df)}")
    print(f"  Equity התחלתי: ${INITIAL_CAPITAL:,.2f}")
    final_equity = eq_df["equity"].iloc[-1]
    print(f"  Equity סופי: ${final_equity:,.2f}")
    pnl = final_equity - INITIAL_CAPITAL
    pnl_pct = (final_equity / INITIAL_CAPITAL - 1.0) * 100.0
    print(f"  רווח/הפסד: ${pnl:,.2f} ({pnl_pct:+.2f}%)")

    eq_df["peak"] = eq_df["equity"].cummax()
    eq_df["dd"] = (eq_df["equity"] - eq_df["peak"]) / eq_df["peak"]
    max_dd = eq_df["dd"].min() * 100.0
    print(f"  Max Drawdown: {max_dd:.2f}%")
    print("=" * 60)


def main():
    print("=== IL Momentum Paper Trading (2022-2025) ===")
    print(f"Universe: TA35.TA + {len(IL_STOCKS)} מניות\n")
    run_il_paper()
    print("\n✅ IL Paper הסתיים!")


if __name__ == "__main__":
    main()
