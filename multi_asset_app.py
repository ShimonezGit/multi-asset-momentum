#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_asset_app.py
דשבורד רב-נכסי - קריפטו / ארה"ב / ישראל עם Benchmark
"""

import os
from datetime import date
from typing import Dict, Optional, List

import pandas as pd
import numpy as np
import streamlit as st

RESULTS_DIR = "results_multi"
CRYPTO_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")
IL_FILE = os.path.join(RESULTS_DIR, "il_equity_curve.csv")
SUMMARY_FILE = os.path.join(RESULTS_DIR, "multi_summary.csv")

DATE_COL_CANDIDATES = ["date", "datetime", "time", "timestamp"]

def load_csv_with_date(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"שגיאה בטעינת קובץ: {path}")
        return None
    date_col = None
    for cand in DATE_COL_CANDIDATES:
        if cand in df.columns:
            date_col = cand
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "date"})
    elif "index" in df.columns:
        df["date"] = pd.to_datetime(df["index"])
    else:
        return df
    df = df.sort_values(by="date").reset_index(drop=True)
    return df

def filter_by_date_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df is None or df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df.loc[mask].copy()

def compute_window_metrics(equity_df: pd.DataFrame, col_name: str = "equity") -> Dict[str, float]:
    metrics = {"total_return_pct": np.nan, "pnl_factor": np.nan, "max_drawdown_pct": np.nan, "sharpe": np.nan}
    if equity_df is None or equity_df.empty or col_name not in equity_df.columns:
        return metrics
    eq = equity_df[col_name].astype(float)
    if len(eq) < 2:
        return metrics
    start_val = eq.iloc[0]
    end_val = eq.iloc[-1]
    if start_val <= 0:
        return metrics
    total_return = (end_val / start_val - 1.0) * 100.0
    pnl_factor = end_val / start_val
    cum_max = eq.cummax()
    drawdown = (eq / cum_max - 1.0) * 100.0
    max_dd = drawdown.min()
    daily_returns = eq.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = np.nan
    metrics["total_return_pct"] = float(total_return)
    metrics["pnl_factor"] = float(pnl_factor)
    metrics["max_drawdown_pct"] = float(max_dd)
    metrics["sharpe"] = float(sharpe)
    return metrics

def load_summary(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except:
        return None

def compute_dynamic_summary(segments: List[str], crypto_df, us_df, il_df, summary_df, start_date: date, end_date: date) -> pd.DataFrame:
    rows = []
    segment_map = {"קריפטו": ("CRYPTO", crypto_df, "BTC"), "ארה\"ב": ("US", us_df, "S&P500"), "ישראל": ("IL", il_df, "TA-125")}
    for seg_name in segments:
        if seg_name not in segment_map:
            continue
        market_code, df, bench_name = segment_map[seg_name]
        if df is None or df.empty:
            continue
        filtered = filter_by_date_range(df, start_date, end_date)
        strat_metrics = compute_window_metrics(filtered, "equity")
        bench_metrics = {"total_return_pct": np.nan, "pnl_factor": np.nan, "max_drawdown_pct": np.nan}
        if "benchmark_equity" in filtered.columns:
            bench_metrics = compute_window_metrics(filtered, "benchmark_equity")
        elif summary_df is not None and not summary_df.empty:
            bench_row = summary_df[summary_df["market"] == market_code]
            if not bench_row.empty:
                r = bench_row.iloc[0]
                bench_metrics["total_return_pct"] = r.get("benchmark_return_pct", np.nan)
                bench_metrics["pnl_factor"] = r.get("benchmark_multiple", np.nan)
        alpha = strat_metrics["total_return_pct"] - bench_metrics["total_return_pct"]
        rows.append({"סגמנט": seg_name, "Strategy תשואה": strat_metrics["total_return_pct"], "Strategy מכפיל": strat_metrics["pnl_factor"], "Strategy Max DD": strat_metrics["max_drawdown_pct"], "Strategy Sharpe": strat_metrics["sharpe"], f"{bench_name} תשואה": bench_metrics["total_return_pct"], f"{bench_name} מכפיל": bench_metrics["pnl_factor"], "Alpha": alpha})
    return pd.DataFrame(rows)

def render_segment_block(name: str, df, start_date: date, end_date: date, benchmark_name: str) -> None:
    st.subheader(f"{name}")
    if df is None or df.empty:
        st.warning(f"אין דאטה זמין ל-{name}.")
        return
    filtered = filter_by_date_range(df, start_date, end_date)
    if filtered.empty:
        st.warning("אין נתונים בטווח התאריכים שנבחר.")
        return
    chart_mode = st.radio(f"הצג עבור {name}:", options=["Strategy בלבד", f"{benchmark_name} בלבד", "שניהם"], index=2, key=f"chart_{name}", horizontal=True)
    strat_metrics = compute_window_metrics(filtered, "equity")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("תשואה", f"{strat_metrics['total_return_pct']:.1f}%" if not np.isnan(strat_metrics["total_return_pct"]) else "N/A")
    with col2:
        st.metric("מכפיל", f"{strat_metrics['pnl_factor']:.2f}x" if not np.isnan(strat_metrics["pnl_factor"]) else "N/A")
    with col3:
        st.metric("Max DD", f"{strat_metrics['max_drawdown_pct']:.1f}%" if not np.isnan(strat_metrics["max_drawdown_pct"]) else "N/A")
    with col4:
        st.metric("Sharpe", f"{strat_metrics['sharpe']:.2f}" if not np.isnan(strat_metrics["sharpe"]) else "N/A")
    chart_df = pd.DataFrame()
    if "equity" not in filtered.columns:
        st.warning("לא נמצאה עמודת equity.")
        return
    if chart_mode == "Strategy בלבד":
        chart_df["Strategy"] = filtered.set_index("date")["equity"]
    elif chart_mode == f"{benchmark_name} בלבד":
        if "benchmark_equity" in filtered.columns:
            chart_df[benchmark_name] = filtered.set_index("date")["benchmark_equity"]
        else:
            st.warning(f"אין נתוני {benchmark_name}.")
            return
    else:
        chart_df["Strategy"] = filtered.set_index("date")["equity"]
        if "benchmark_equity" in filtered.columns:
            chart_df[benchmark_name] = filtered.set_index("date")["benchmark_equity"]
    if not chart_df.empty:
        st.line_chart(chart_df, height=300)

def main() -> None:
    st.set_page_config(page_title="Multi-Asset Strategy Dashboard", layout="wide")
    st.title("Multi-Asset Strategy Dashboard")
    st.caption("קריפטו מול BTC | ארה\"ב מול S&P500 | ישראל מול TA-125")
    crypto_df = load_csv_with_date(CRYPTO_FILE)
    us_df = load_csv_with_date(US_FILE)
    il_df = load_csv_with_date(IL_FILE)
    summary_df = load_summary(SUMMARY_FILE)
    all_dates = []
    for df in [crypto_df, us_df, il_df]:
        if df is not None and not df.empty and "date" in df.columns:
            all_dates.append(df["date"])
    if all_dates:
        global_min = min(s.min() for s in all_dates).date()
        global_max = max(s.max() for s in all_dates).date()
    else:
        global_max = date.today()
        global_min = date(global_max.year - 1, global_max.month, global_max.day)
    st.sidebar.header("מסננים")
    selected_segments = st.sidebar.multiselect("בחר סגמנטים:", options=["קריפטו", "ארה\"ב", "ישראל"], default=["קריפטו", "ארה\"ב", "ישראל"])
    date_input_val = st.sidebar.date_input("טווח תאריכים:", value=(global_min, global_max), min_value=global_min, max_value=global_max)
    if isinstance(date_input_val, tuple):
        start_date, end_date = date_input_val
    else:
        start_date = end_date = date_input_val
    if start_date > end_date:
        st.sidebar.error("תאריך התחלה גדול מתאריך סיום.")
        st.stop()
    st.sidebar.markdown("---")
    st.sidebar.write(f"טווח גלובלי: {global_min} – {global_max}")
    st.sidebar.write(f"טווח נבחר: {start_date} – {end_date}")
    st.markdown("### סיכום דינמי – Strategy מול Benchmark")
    if selected_segments:
        dynamic_summary = compute_dynamic_summary(selected_segments, crypto_df, us_df, il_df, summary_df, start_date, end_date)
        if not dynamic_summary.empty:
            display_df = dynamic_summary.copy()
            pct_cols = ["Strategy תשואה", "Strategy Max DD", "Alpha", "BTC תשואה", "S&P500 תשואה", "TA-125 תשואה"]
            for col in pct_cols:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
            mult_cols = ["Strategy מכפיל", "BTC מכפיל", "S&P500 מכפיל", "TA-125 מכפיל"]
            for col in mult_cols:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A")
            if "Strategy Sharpe" in display_df.columns:
                display_df["Strategy Sharpe"] = display_df["Strategy Sharpe"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
            st.dataframe(display_df)
        else:
            st.info("אין נתונים לטווח הנבחר.")
    else:
        st.info("בחר לפחות סגמנט אחד.")
    st.markdown("---")
    if "קריפטו" in selected_segments:
        render_segment_block("קריפטו (Crypto)", crypto_df, start_date, end_date, "BTC")
    if "ארה\"ב" in selected_segments:
        render_segment_block("שוק אמריקאי (US)", us_df, start_date, end_date, "S&P500")
    if "ישראל" in selected_segments:
        render_segment_block("שוק ישראלי (IL)", il_df, start_date, end_date, "TA-125")
    st.markdown("---")
    st.caption("דשבורד חיי – Strategy vs Benchmark")

if __name__ == "__main__":
    main()
