#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from datetime import date, datetime
from typing import Dict, Optional, List
import pandas as pd
import numpy as np
import streamlit as st

RESULTS_DIR = "results_multi"
CRYPTO_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")
IL_FILE = os.path.join(RESULTS_DIR, "il_equity_curve.csv")
SUMMARY_FILE = os.path.join(RESULTS_DIR, "multi_summary.csv")

def load_csv_with_date(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        for cand in ["date", "datetime", "time", "timestamp"]:
            if cand in df.columns:
                df[cand] = pd.to_datetime(df[cand])
                df = df.rename(columns={cand: "date"})
                break
        if "date" not in df.columns and "index" in df.columns:
            df["date"] = pd.to_datetime(df["index"])
        return df.sort_values(by="date").reset_index(drop=True) if "date" in df.columns else df
    except:
        return None

def filter_by_date_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df is None or df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df.loc[mask].copy()

def compute_window_metrics(equity_df: pd.DataFrame, col_name: str = "equity") -> Dict[str, float]:
    m = {"total_return_pct": np.nan, "pnl_factor": np.nan, "max_drawdown_pct": np.nan, "sharpe": np.nan}
    if equity_df is None or equity_df.empty or col_name not in equity_df.columns:
        return m
    eq = equity_df[col_name].astype(float)
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return m
    s, e = eq.iloc[0], eq.iloc[-1]
    m["total_return_pct"] = float((e / s - 1.0) * 100.0)
    m["pnl_factor"] = float(e / s)
    dd = (eq / eq.cummax() - 1.0) * 100.0
    m["max_drawdown_pct"] = float(dd.min())
    dr = eq.pct_change().dropna()
    if len(dr) > 1 and dr.std() > 0:
        m["sharpe"] = float((dr.mean() / dr.std()) * np.sqrt(252))
    return m

def compute_dynamic_summary(segments: List[str], crypto_df, us_df, il_df, start_date: date, end_date: date) -> pd.DataFrame:
    rows = []
    smap = {"קריפטו": (crypto_df, "BTC"), "ארה\"ב": (us_df, "S&P500"), "ישראל": (il_df, "TA-125")}
    for seg in segments:
        if seg not in smap:
            continue
        df, bn = smap[seg]
        if df is None or df.empty:
            continue
        filt = filter_by_date_range(df, start_date, end_date)
        sm = compute_window_metrics(filt, "equity")
        bm = compute_window_metrics(filt, "benchmark_equity") if "benchmark_equity" in filt.columns else {"total_return_pct": np.nan, "pnl_factor": np.nan}
        alpha = sm["total_return_pct"] - bm["total_return_pct"]
        rows.append({"סגמנט": seg, "Strategy תשואה": sm["total_return_pct"], "Strategy מכפיל": sm["pnl_factor"], "Strategy Sharpe": sm["sharpe"], f"{bn} תשואה": bm["total_return_pct"], f"{bn} מכפיל": bm["pnl_factor"], "Alpha": alpha})
    return pd.DataFrame(rows)

def render_colored_metric(label: str, value: str, color: str):
    st.markdown(f'<div style="text-align:center;"><div style="font-size:14px;color:#888;">{label}</div><div style="font-size:28px;font-weight:bold;color:{color};">{value}</div></div>', unsafe_allow_html=True)

def render_segment_block(name: str, df, start_date: date, end_date: date, bn: str):
    st.subheader(f"{name}")
    if df is None or df.empty:
        st.warning(f"אין דאטה זמין ל-{name}.")
        return
    filt = filter_by_date_range(df, start_date, end_date)
    if filt.empty:
        st.warning("אין נתונים בטווח התאריכים שנבחר.")
        return
    cm = st.radio("הצג:", ["Strategy בלבד", f"{bn} בלבד", "שניהם"], index=2, key=f"c_{name}", horizontal=True)
    sm = compute_window_metrics(filt, "equity")
    bm = compute_window_metrics(filt, "benchmark_equity") if "benchmark_equity" in filt.columns else {"total_return_pct": np.nan, "pnl_factor": np.nan, "max_drawdown_pct": np.nan, "sharpe": np.nan}
    st.markdown("**Strategy (אסטרטגיה)**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_colored_metric("תשואה", f"{sm['total_return_pct']:.1f}%" if not np.isnan(sm['total_return_pct']) else "N/A", "#1f77b4")
    with c2:
        render_colored_metric("מכפיל", f"{sm['pnl_factor']:.2f}x" if not np.isnan(sm['pnl_factor']) else "N/A", "#1f77b4")
    with c3:
        render_colored_metric("Max DD", f"{sm['max_drawdown_pct']:.1f}%" if not np.isnan(sm['max_drawdown_pct']) else "N/A", "#1f77b4")
    with c4:
        render_colored_metric("Sharpe", f"{sm['sharpe']:.2f}" if not np.isnan(sm['sharpe']) else "N/A", "#1f77b4")
    st.markdown(f"**{bn} (מדד)**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_colored_metric("תשואה", f"{bm['total_return_pct']:.1f}%" if not np.isnan(bm['total_return_pct']) else "N/A", "#17becf")
    with c2:
        render_colored_metric("מכפיל", f"{bm['pnl_factor']:.2f}x" if not np.isnan(bm['pnl_factor']) else "N/A", "#17becf")
    with c3:
        render_colored_metric("Max DD", f"{bm['max_drawdown_pct']:.1f}%" if not np.isnan(bm['max_drawdown_pct']) else "N/A", "#17becf")
    with c4:
        render_colored_metric("Sharpe", f"{bm['sharpe']:.2f}" if not np.isnan(bm['sharpe']) else "N/A", "#17becf")
    st.markdown("---")
    cdf = pd.DataFrame()
    if "equity" not in filt.columns:
        return
    if cm == "Strategy בלבד":
        cdf["Strategy"] = filt.set_index("date")["equity"]
    elif cm == f"{bn} בלבד" and "benchmark_equity" in filt.columns:
        cdf[bn] = filt.set_index("date")["benchmark_equity"]
    else:
        cdf["Strategy"] = filt.set_index("date")["equity"]
        if "benchmark_equity" in filt.columns:
            cdf[bn] = filt.set_index("date")["benchmark_equity"]
    if not cdf.empty:
        st.line_chart(cdf, height=350)

def main():
    st.set_page_config(page_title="Multi-Asset Dashboard", layout="wide")
    st.title("Multi-Asset Strategy Dashboard")
    st.caption("קריפטו מול BTC | ארה\"ב מול S&P500 | ישראל מול TA-125")
    with st.expander("📖 מדריך מהיר"):
        st.markdown("**תשואה** – אחוז גידול. **מכפיל** – הון סופי/התחלתי. **Max DD** – ירידה מקסימלית. **Sharpe** – תשואה מתואמת סיכון (>2 מצוין). **Alpha** – יתרון על המדד.")
    crypto_df = load_csv_with_date(CRYPTO_FILE)
    us_df = load_csv_with_date(US_FILE)
    il_df = load_csv_with_date(IL_FILE)
    all_dates = []
    for df in [crypto_df, us_df, il_df]:
        if df is not None and not df.empty and "date" in df.columns:
            all_dates.append(df["date"])
    if all_dates:
        gmin = min(s.min() for s in all_dates).date()
        gmax = max(s.max() for s in all_dates).date()
    else:
        gmax = date.today()
        gmin = date(gmax.year - 1, gmax.month, gmax.day)
    
    st.sidebar.header("מסננים")
    segs = st.sidebar.multiselect("בחר סגמנטים:", ["קריפטו", "ארה\"ב", "ישראל"], default=["קריפטו", "ארה\"ב", "ישראל"])
    
    st.sidebar.markdown("### טווח תאריכים")
    years = list(range(gmin.year, gmax.year + 1))
    months = list(range(1, 13))
    month_names = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
    
    c1, c2 = st.sidebar.columns(2)
    with c1:
        sy = st.selectbox("שנת התחלה", years, index=0)
        sm = st.selectbox("חודש התחלה", months, format_func=lambda x: month_names[x-1], index=0)
    with c2:
        ey = st.selectbox("שנת סיום", years, index=len(years)-1)
        em = st.selectbox("חודש סיום", months, format_func=lambda x: month_names[x-1], index=len(months)-1)
    
    if st.sidebar.button("🔍 חפש", type="primary"):
        st.session_state["custom_range"] = (date(sy, sm, 1), date(ey, em, 28))
    
    if "custom_range" in st.session_state:
        sd, ed = st.session_state["custom_range"]
    else:
        sd, ed = gmin, gmax
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"**טווח נבחר:** {sd} – {ed}")
    
    st.markdown("### סיכום דינמי")
    if segs:
        ds = compute_dynamic_summary(segs, crypto_df, us_df, il_df, sd, ed)
        if not ds.empty:
            dd = ds.copy()
            for col in ["Strategy תשואה", "BTC תשואה", "S&P500 תשואה", "TA-125 תשואה", "Alpha"]:
                if col in dd.columns:
                    dd[col] = dd[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
            for col in ["Strategy מכפיל", "BTC מכפיל", "S&P500 מכפיל", "TA-125 מכפיל"]:
                if col in dd.columns:
                    dd[col] = dd[col].apply(lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A")
            if "Strategy Sharpe" in dd.columns:
                dd["Strategy Sharpe"] = dd["Strategy Sharpe"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
            st.dataframe(dd)
    
    st.markdown("---")
    if "קריפטו" in segs:
        render_segment_block("קריפטו (Crypto)", crypto_df, sd, ed, "BTC")
    if "ארה\"ב" in segs:
        render_segment_block("שוק אמריקאי (US)", us_df, sd, ed, "S&P500")
    if "ישראל" in segs:
        render_segment_block("שוק ישראלי (IL)", il_df, sd, ed, "TA-125")
    
    st.markdown("---")
    st.caption("דשבורד חיי – Strategy vs Benchmark")

if __name__ == "__main__":
    main()
