#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_asset_app.py
דשבורד רב-נכסי לניתוח ביצועי אסטרטגיות קריפטו / ארה"ב / ישראל
מתאים ל-Streamlit Cloud כאפליקציה חיה.
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
        st.error(f"שגיאה בטעינת הקובץ: {path} - {e}")
        return None
    date_col = None
    for cand in DATE_COL_CANDIDATES:
        if cand in df.columns:
            date_col = cand
            break
    if date_col is None:
        if "index" in df.columns:
            df["date"] = pd.to_datetime(df["index"])
        else:
            return df
    else:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "date"})
    df = df.sort_values(by="date").reset_index(drop=True)
    return df

def filter_by_date_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df.loc[mask].copy()

def compute_window_metrics(equity_df: pd.DataFrame) -> Dict[str, float]:
    metrics = {
        "total_return_pct": np.nan,
        "pnl_factor": np.nan,
        "max_drawdown_pct": np.nan,
        "sharpe": np.nan,
    }
    if equity_df is None or equity_df.empty or "equity" not in equity_df.columns:
        return metrics
    
    eq = equity_df["equity"].astype(float)
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
    
    # Sharpe Ratio (תשואות יומיות)
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
    except Exception as e:
        st.error(f"שגיאה בטעינת summary: {path} - {e}")
        return None

def compute_dynamic_summary(
    segments: List[str],
    crypto_df: Optional[pd.DataFrame],
    us_df: Optional[pd.DataFrame],
    il_df: Optional[pd.DataFrame],
    summary_df: Optional[pd.DataFrame],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """מחשב טבלת summary דינמית לפי הטווח שנבחר."""
    rows = []
    
    segment_map = {
        "קריפטו": ("CRYPTO", crypto_df),
        "ארה\"ב": ("US", us_df),
        "ישראל": ("IL", il_df),
    }
    
    for seg_name in segments:
        if seg_name not in segment_map:
            continue
        market_code, df = segment_map[seg_name]
        if df is None or df.empty:
            continue
        
        filtered = filter_by_date_range(df, start_date, end_date)
        metrics = compute_window_metrics(filtered)
        
        # נתוני benchmark מה-summary הסטטי (אם יש)
        bench_return = np.nan
        bench_multiple = np.nan
        if summary_df is not None and not summary_df.empty:
            bench_row = summary_df[summary_df["market"] == market_code]
            if not bench_row.empty:
                r = bench_row.iloc[0]
                bench_return = r.get("benchmark_return_pct", np.nan)
                bench_multiple = r.get("benchmark_multiple", np.nan)
        
        # Alpha = תשואת האסטרטגיה - תשואת הבנצ'מרק
        alpha = metrics["total_return_pct"] - bench_return if not np.isnan(bench_return) else np.nan
        
        rows.append({
            "segment": seg_name,
            "strategy_return_pct": metrics["total_return_pct"],
            "strategy_multiple": metrics["pnl_factor"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "sharpe_ratio": metrics["sharpe"],
            "benchmark_return_pct": bench_return,
            "benchmark_multiple": bench_multiple,
            "alpha_pct": alpha,
        })
    
    return pd.DataFrame(rows)

def render_segment_block(
    name: str,
    df: Optional[pd.DataFrame],
    start_date: date,
    end_date: date
) -> None:
    st.subheader(f"{name}")
    if df is None or df.empty:
        st.warning(f"אין דאטה זמין ל-{name}.")
        return
    
    filtered = filter_by_date_range(df, start_date, end_date)
    if filtered.empty:
        st.warning("אין נתונים בטווח התאריכים שנבחר.")
        return
    
    metrics = compute_window_metrics(filtered)
    
    # KPI למעלה
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="תשואה (%)",
            value=f"{metrics['total_return_pct']:.1f}" if not np.isnan(metrics["total_return_pct"]) else "N/A",
        )
    with col2:
        st.metric(
            label="PnL Factor",
            value=f"{metrics['pnl_factor']:.2f}" if not np.isnan(metrics["pnl_factor"]) else "N/A",
        )
    with col3:
        st.metric(
            label="Max DD (%)",
            value=f"{metrics['max_drawdown_pct']:.1f}" if not np.isnan(metrics["max_drawdown_pct"]) else "N/A",
        )
    with col4:
        st.metric(
            label="Sharpe",
            value=f"{metrics['sharpe']:.2f}" if not np.isnan(metrics["sharpe"]) else "N/A",
        )
    
    # גרף למטה
    if "equity" in filtered.columns:
        st.line_chart(filtered.set_index("date")["equity"], height=250)
    else:
        st.warning("לא נמצאה עמודת equity.")

def main() -> None:
    st.set_page_config(page_title="Multi-Asset Strategy Dashboard", layout="wide")
    st.title("Multi-Asset Strategy Dashboard")
    st.caption("קריפטו / שוק אמריקאי / שוק ישראלי – מבוסס תוצאות קיימות")
    
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
    selected_segments = st.sidebar.multiselect(
        "בחר סגמנטים להצגה:",
        options=["קריפטו", "ארה\"ב", "ישראל"],
        default=["קריפטו", "ארה\"ב", "ישראל"],
    )
    
    date_input_val = st.sidebar.date_input(
        "בחר טווח תאריכים:",
        value=(global_min, global_max),
        min_value=global_min,
        max_value=global_max,
    )
    
    if isinstance(date_input_val, tuple):
        start_date, end_date = date_input_val
    else:
        start_date = end_date = date_input_val
    
    if start_date > end_date:
        st.sidebar.error("תאריך ההתחלה גדול מתאריך הסיום.")
        st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"**טווח גלובלי:** {global_min} – {global_max}")
    st.sidebar.write(f"**טווח נבחר:** {start_date}
