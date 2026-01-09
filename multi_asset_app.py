#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_asset_app.py
דשבורד רב-נכסי לניתוח ביצועי אסטרטגיות קריפטו / ארה"ב / ישראל
מתאים ל-Streamlit Cloud כאפליקציה חיה.
"""

import os
from datetime import date
from typing import Dict, Optional

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
            date_col = "date"
        else:
            return df
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col).reset_index(drop=True)
    df = df.rename(columns={date_col: "date"})
    return df

def filter_by_date_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    filtered = df.loc[mask].copy()
    return filtered

def compute_window_metrics(equity_df: pd.DataFrame) -> Dict[str, float]:
    metrics = {
        "total_return_pct": np.nan,
        "pnl_factor": np.nan,
        "max_drawdown_pct": np.nan,
    }
    if equity_df is None or equity_df.empty:
        return metrics
    if "equity" not in equity_df.columns:
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
    metrics["total_return_pct"] = float(total_return)
    metrics["pnl_factor"] = float(pnl_factor)
    metrics["max_drawdown_pct"] = float(max_dd)
    return metrics

def load_summary(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        st.error(f"שגיאה בטעינת summary: {path} - {e}")
        return None

def render_segment_block(name: str, df: Optional[pd.DataFrame], start_date: date, end_date: date) -> None:
    st.subheader(f"{name}")
    if df is None or df.empty:
        st.warning(f"אין דאטה זמין ל-{name}.")
        return
    filtered = filter_by_date_range(df, start_date, end_date)
    if filtered.empty:
        st.warning("אין נתונים בטווח התאריכים שנבחר.")
        return
    if "equity" in filtered.columns:
        st.line_chart(filtered.set_index("date")["equity"], height=250)
    else:
        st.warning("לא נמצאה עמודת equity - לא ניתן להציג עקומת הון.")
    metrics = compute_window_metrics(filtered)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="תשואה כוללת בטווח (%)",
            value=f"{metrics['total_return_pct']:.1f}" if not np.isnan(metrics["total_return_pct"]) else "N/A",
        )
    with col2:
        st.metric(
            label="PnL Factor",
            value=f"{metrics['pnl_factor']:.2f}" if not np.isnan(metrics["pnl_factor"]) else "N/A",
        )
    with col3:
        st.metric(
            label="Max Drawdown (%)",
            value=f"{metrics['max_drawdown_pct']:.1f}" if not np.isnan(metrics["max_drawdown_pct"]) else "N/A",
        )

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
    
    start_date, end_date = st.sidebar.date_input(
        "בחר טווח תאריכים:",
        value=(global_min, global_max),
        min_value=global_min,
        max_value=global_max,
    )
    
    if isinstance(start_date, (list, tuple)):
        start_date, end_date = start_date
    
    if start_date > end_date:
        st.sidebar.error("תאריך ההתחלה גדול מתאריך הסיום. תקן את הטווח.")
        st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"**טווח גלובלי בדאטה:** {global_min} עד {global_max}")
    st.sidebar.write(f"**טווח נבחר:** {start_date} עד {end_date}")
    
    st.markdown("### סיכום כללי לפי סגמנט")
    
    if summary_df is not None and not summary_df.empty:
        cols_map = {}
        for col in summary_df.columns:
            low = col.lower()
            if "segment" in low or "market" in low or "asset" in low:
                cols_map[col] = "segment"
            elif "total_return" in low or "return_pct" in low:
                cols_map[col] = "total_return"
            elif "pnl_factor" in low or "multiplier" in low or "multiple" in low:
                cols_map[col] = "pnl_factor"
            elif "drawdown" in low:
                cols_map[col] = "max_drawdown"
            elif "win_rate" in low or "winrate" in low:
                cols_map[col] = "win_rate"
        
        summary = summary_df.rename(columns=cols_map).copy()
        summary = summary.loc[:, ~summary.columns.duplicated()]
        
        display_cols = []
        for c in ["segment", "total_return", "pnl_factor", "max_drawdown", "win_rate"]:
            if c in summary.columns:
                display_cols.append(c)
        
        if display_cols:
            st.dataframe(summary[display_cols])
        else:
            st.info("לא נמצאו עמודות מוכרות ל-summary, מציג טבלה מלאה:")
            st.dataframe(summary)
    else:
        st.info("לא נמצא קובץ multi_summary.csv או שהוא ריק.")
    
    st.markdown("---")
    
    if "קריפטו" in selected_segments:
        render_segment_block("קריפטו (Crypto)", crypto_df, start_date, end_date)
    
    if "ארה\"ב" in selected_segments:
        render_segment_block("שוק אמריקאי (US)", us_df, start_date, end_date)
    
    if "ישראל" in selected_segments:
        render_segment_block("שוק ישראלי (IL)", il_df, start_date, end_date)
    
    st.markdown("---")
    st.caption("דשבורד חיי – תצוגת ביצועים בלבד, ללא ביצוע פקודות מסחר מהענן.")

if __name__ == "__main__":
    main()

