# coding: utf-8

import os
from datetime import date
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st

RESULTS_DIR = "results_multi"

# קבצי אסטרטגיה / בנצ'מרק קיימים בפועל
CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_equity.csv")           # מה-backtest
CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")     # BTC Buy&Hold
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")             # US Benchmark

INITIAL_CAPITAL = 100000.0


# ---------- עזר לטעינה/מדדים ----------

def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        st.warning(f"{label}: file not found: {path}")
        return None

    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"{label}: failed to read CSV: {e}")
        return None

    if "date" not in df.columns or "equity" not in df.columns:
        st.error(f"{label}: CSV must have 'date' and 'equity' columns.")
        return None

    df["date"] = pd.to_datetime(df["date"])
    df["equity"] = df["equity"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_global_range(dfs: List[Optional[pd.DataFrame]]) -> Tuple[date, date]:
    dates: List[pd.Timestamp] = []
    for df in dfs:
        if df is not None and not df.empty:
            dates.append(df["date"].min())
            dates.append(df["date"].max())

    if not dates:
        today = date.today()
        return today, today

    return min(dates).date(), max(dates).date()


def compute_metrics(equity: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {
        "total_return": np.nan,
        "multiple": np.nan,
        "max_dd": np.nan,
        "sharpe": np.nan,
    }

    if equity is None or len(equity) < 2:
        return out

    eq = equity.astype(float)
    start_val = float(eq.iloc[0])
    end_val = float(eq.iloc[-1])

    if start_val <= 0:
        return out

    total_ret = end_val / start_val - 1.0
    out["total_return"] = total_ret * 100.0
    out["multiple"] = end_val / start_val

    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    out["max_dd"] = float(dd.min() * 100.0)

    rets = eq.pct_change().dropna()
    if len(rets) > 0 and rets.std() != 0:
        out["sharpe"] = float(rets.mean() / rets.std() * np.sqrt(252.0))

    return out


def normalize_equity(equity: pd.Series) -> pd.Series:
    eq = equity.astype(float)
    start_val = float(eq.iloc[0])
    if start_val <= 0:
        return eq
    factor = INITIAL_CAPITAL / start_val
    return eq * factor


# ---------- אפליקציה ----------

def main() -> None:
    st.set_page_config(page_title="Crypto Momentum – Investor View", layout="wide")

    st.title("Crypto Momentum – Investor View")
    st.caption(
        "Momentum strategy on top-10 alts vs BTC Buy&Hold, 1D, 100K, Binance data."
    )

    crypto_strat = load_equity_csv(CRYPTO_STRAT_FILE, "Crypto Strategy")
    crypto_bench = load_equity_csv(CRYPTO_BENCH_FILE, "BTC Benchmark")
    us_bench = load_equity_csv(US_BENCH_FILE, "US Benchmark")

    gmin, gmax = get_global_range([crypto_strat, crypto_bench, us_bench])
    st.write(f"Loaded date range: {gmin} → {gmax}")
    st.markdown("---")

    tab_overview, tab_equity, tab_details = st.tabs(
        ["Overview", "Equity Curves", "Raw Data"]
    )

    # ---------- Overview ----------
    with tab_overview:
        st.subheader("Metrics")

        rows = []

        if crypto_strat is not None and not crypto_strat.empty:
            m = compute_metrics(crypto_strat["equity"])
            rows.append(
                {
                    "Instrument": "Crypto Momentum Strategy",
                    "Type": "Strategy",
                    "Total Return %": m["total_return"],
                    "Multiple (x)": m["multiple"],
                    "Max DD %": m["max_dd"],
                    "Sharpe": m["sharpe"],
                }
            )

        if crypto_bench is not None and not crypto_bench.empty:
            m = compute_metrics(crypto_bench["equity"])
            rows.append(
                {
                    "Instrument": "BTC Benchmark",
                    "Type": "Benchmark",
                    "Total Return %": m["total_return"],
                    "Multiple (x)": m["multiple"],
                    "Max DD %": m["max_dd"],
                    "Sharpe": m["sharpe"],
                }
            )

        if us_bench is not None and not us_bench.empty:
            m = compute_metrics(us_bench["equity"])
            rows.append(
                {
                    "Instrument": "US Benchmark",
                    "Type": "Benchmark",
                    "Total Return %": m["total_return"],
                    "Multiple (x)": m["multiple"],
                    "Max DD %": m["max_dd"],
                    "Sharpe": m["sharpe"],
                }
            )

        if rows:
            df = pd.DataFrame(rows)
            styled = df.style.format(
                {
                    "Total Return %": "{:.1f}",
                    "Multiple (x)": "{:.2f}",
                    "Max DD %": "{:.1f}",
                    "Sharpe": "{:.2f}",
                }
            )
            st.dataframe(styled, use_container_width=True)
        else:
            st.warning("No data loaded for any instrument.")

    # ---------- Equity Curves ----------
    with tab_equity:
        st.subheader("Equity Curves – Normalized to 100,000")

        merged = pd.DataFrame()

        # ציר זמן – לפי האסטרטגיה אם קיימת, אחרת לפי BTC
        if crypto_strat is not None and not crypto_strat.empty:
            merged["date"] = crypto_strat["date"]
        elif crypto_bench is not None and not crypto_bench.empty:
            merged["date"] = crypto_bench["date"]
        elif us_bench is not None and not us_bench.empty:
            merged["date"] = us_bench["date"]

        if merged.empty:
            st.info("No data to plot.")
        else:
            if crypto_strat is not None and not crypto_strat.empty:
                merged = merged.merge(
                    pd.DataFrame(
                        {
                            "date": crypto_strat["date"],
                            "Crypto Momentum Strategy": normalize_equity(
                                crypto_strat["equity"]
                            ),
                        }
                    ),
                    on="date",
                    how="left",
                )

            if crypto_bench is not None and not crypto_bench.empty:
                merged = merged.merge(
                    pd.DataFrame(
                        {
                            "date": crypto_bench["date"],
                            "BTC Benchmark": normalize_equity(
                                crypto_bench["equity"]
                            ),
                        }
                    ),
                    on="date",
                    how="left",
                )

            if us_bench is not None and not us_bench.empty:
                merged = merged.merge(
                    pd.DataFrame(
                        {
                            "date": us_bench["date"],
                            "US Benchmark": normalize_equity(us_bench["equity"]),
                        }
                    ),
                    on="date",
                    how="left",
                )

            merged = merged.sort_values("date").set_index("date")
            st.line_chart(merged, use_container_width=True, height=380)

    # ---------- Raw Data ----------
    with tab_details:
        st.subheader("Raw Data")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Crypto Momentum Strategy")
            if crypto_strat is not None and not crypto_strat.empty:
                st.dataframe(crypto_strat, use_container_width=True, height=300)
            else:
                st.info("No crypto strategy equity file.")

            st.markdown("#### BTC Benchmark")
            if crypto_bench is not None and not crypto_bench.empty:
                st.dataframe(crypto_bench, use_container_width=True, height=300)
            else:
                st.info("No BTC benchmark file.")

        with col2:
            st.markdown("#### US Benchmark")
            if us_bench is not None and not us_bench.empty:
                st.dataframe(us_bench, use_container_width=True, height=300)
            else:
                st.info("No US benchmark file.")


if __name__ == "__main__":
    main()
