#!/usr/bin/env python3
# coding: utf-8

# crypto_dashboard_app.py
# דשבורד מינימלי לקריפטו בלבד – Strategy מתוך crypto_paper_equity.csv
# מטריקות מחושבות על כל ההיסטוריה; הגרף יכול להיחתך לפי תאריכים.

import os
from datetime import date
from typing import Optional, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st

RESULTS_DIR = "results_multi"
CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")

def load_crypto_equity() -> pd.DataFrame:
    if not os.path.exists(CRYPTO_STRAT_FILE):
        raise FileNotFoundError(f"missing {CRYPTO_STRAT_FILE}")
    df = pd.read_csv(CRYPTO_STRAT_FILE)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError("crypto_paper_equity.csv must have columns: date,equity")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df

def compute_metrics_full(equity: pd.Series) -> Dict[str, float]:
    out = {"total_return": np.nan, "multiple": np.nan, "max_dd": np.nan, "sharpe": np.nan}
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
    rollmax = eq.cummax()
    dd = (eq - rollmax) / rollmax
    out["max_dd"] = float(dd.min() * 100.0)
    rets = eq.pct_change().dropna()
    if len(rets) > 0 and rets.std() > 0:
        out["sharpe"] = float((rets.mean() / rets.std()) * np.sqrt(252.0))
    return out

def get_global_range(df: pd.DataFrame) -> Tuple[date, date]:
    dmin = df["date"].min().date()
    dmax = df["date"].max().date()
    return dmin, dmax

def main() -> None:
    st.set_page_config(page_title="Crypto Paper Dashboard", layout="wide")

    crypto_df = load_crypto_equity()
    gmin, gmax = get_global_range(crypto_df)

    with st.sidebar:
        st.header("Filters")
        start_sel = st.date_input("Start date (for chart)", value=gmin, min_value=gmin, max_value=gmax, key="start")
        end_sel = st.date_input("End date (for chart)", value=gmax, min_value=gmin, max_value=gmax, key="end")
        if start_sel > end_sel:
            st.error("Start date must be before end date.")
            return

    st.title("Crypto – Strategy only (Paper)")
    st.caption("Metrics on full backtest from crypto_paper_equity.csv; chart respects selected window.")
    st.write(f"Chart window: {start_sel} → {end_sel}")
    st.markdown("---")

    # מטריקות – על כל ההיסטוריה
    metrics = compute_metrics_full(crypto_df["equity"])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Strategy Total return (full period)", f"{metrics['total_return']:.1f}%")
    with col2:
        st.metric("Strategy Multiple (full period)", f"{metrics['multiple']:.2f}x")
    with col3:
        st.metric("Strategy Max DD (full period)", f"{metrics['max_dd']:.1f}%")
    with col4:
        s = metrics["sharpe"]
        st.metric("Strategy Sharpe (full period)", "n/a" if np.isnan(s) else f"{s:.2f}")

    st.markdown("---")

    # גרף – לפי החלון
    window = crypto_df[(crypto_df["date"].dt.date >= start_sel) & (crypto_df["date"].dt.date <= end_sel)].copy()
    if window.empty:
        st.info("No data in selected range.")
    else:
        window = window.set_index("date")
        st.line_chart(window[["equity"]], use_container_width=True, height=350)

    st.markdown("---")
    st.subheader("Raw crypto_paper_equity.csv")
    st.dataframe(crypto_df, use_container_width=True, height=300)

if __name__ == "__main__":
    main()
