#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import numpy as np
import pandas as pd
import streamlit as st  # pip install streamlit pandas

RESULTS_DIR = "results_multi"


def load_equity_curve(name: str) -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, f"{name}_equity_curve.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
    else:
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        df.set_index(df.columns[0], inplace=True)
    return df


def load_summary() -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, "multi_summary.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df


def compute_window_metrics(equity: pd.Series, benchmark_close: pd.Series | None = None) -> dict:
    """חישוב מדדים על חלון זמן נתון (equity כבר מסונן לתקופה)."""
    metrics = {
        "total_return_pct": np.nan,
        "multiple": np.nan,
        "max_dd_pct": np.nan,
        "benchmark_return_pct": np.nan,
        "benchmark_multiple": np.nan,
    }
    if equity is None or equity.empty:
        return metrics

    eq = equity.dropna()
    if eq.empty:
        return metrics

    start_val = eq.iloc[0]
    end_val = eq.iloc[-1]
    metrics["multiple"] = float(end_val / start_val)
    metrics["total_return_pct"] = float((end_val / start_val - 1.0) * 100.0)

    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    metrics["max_dd_pct"] = float(dd.min() * 100.0)

    if benchmark_close is not None and not benchmark_close.empty:
        b = benchmark_close.dropna()
        if not b.empty:
            b_start = b.iloc[0]
            b_end = b.iloc[-1]
            metrics["benchmark_multiple"] = float(b_end / b_start)
            metrics["benchmark_return_pct"] = float((b_end / b_start - 1.0) * 100.0)

    return metrics


def main():
    st.set_page_config(
        page_title="Multi-Asset Momentum Dashboard",
        layout="wide"
    )

    st.title("Multi-Asset Momentum – Crypto / US / IL")
    st.caption("דשבורד מבוסס תוצאות Backtest 2022–2025. אין כאן מסחר אמיתי, רק סימולציה.")

    # טעינת נתונים
    crypto_eq = load_equity_curve("crypto")
    us_eq = load_equity_curve("us")
    il_eq = load_equity_curve("il")
    summary_df = load_summary()

    if crypto_eq.empty and us_eq.empty and il_eq.empty:
        st.error("לא נמצאו קבצי עקומת הון ב-results_multi. ודא שהרצת את multi_asset_momentum_backtest.py קודם.")
        return

    # טווח תאריכים מלא
    all_dates = pd.Index([])
    for df in [crypto_eq, us_eq, il_eq]:
        if not df.empty:
            all_dates = all_dates.union(df.index)
    all_dates = all_dates.sort_values()
    min_date = all_dates.min()
    max_date = all_dates.max()

    # ===== Sidebar – שווקים + טווח זמן =====
    st.sidebar.header("מסננים")

    show_crypto = st.sidebar.checkbox("קריפטו", value=not crypto_eq.empty)
    show_us = st.sidebar.checkbox("מניות ארה\"ב", value=not us_eq.empty)
    show_il = st.sidebar.checkbox("מניות ישראל", value=not il_eq.empty)

    st.sidebar.markdown("---")
    st.sidebar.subheader("טווח זמן")

    start_default = min_date.to_pydatetime().date() if pd.notna(min_date) else None
    end_default = max_date.to_pydatetime().date() if pd.notna(max_date) else None

    date_range = st.sidebar.date_input(
        "בחר טווח תאריכים",
        value=(start_default, end_default),
        min_value=start_default,
        max_value=end_default
    )

    if isinstance(date_range, tuple):
        start_date, end_date = date_range
    else:
        start_date = date_range
        end_date = end_default

    if start_date is None or end_date is None:
        st.error("טווח תאריכים לא תקין.")
        return

    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    # סינון עקומות הון לפי טווח
    def filter_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        return df[(df.index >= start_ts) & (df.index <= end_ts)]

    crypto_eq_f = filter_df(crypto_eq)
    us_eq_f = filter_df(us_eq)
    il_eq_f = filter_df(il_eq)

    # ===== כרטיסי מדדים – מחושבים לפי טווח =====
    st.subheader("סיכום ביצועים על הטווח הנבחר")

    col_crypto, col_us, col_il = st.columns(3)

    def card_for_market(col, label, market_name, eq_df: pd.DataFrame):
        if eq_df.empty:
            col.metric(label, "N/A")
            return

        # מוצא נתוני בנצ'מרק מה-summary אם יש
        bench_return = np.nan
        bench_mult = np.nan
        if not summary_df.empty:
            row = summary_df[summary_df["market"] == market_name]
            if not row.empty:
                r = row.iloc[0]
                bench_return = r.get("benchmark_return_pct", np.nan)
                bench_mult = r.get("benchmark_multiple", np.nan)

        metrics = compute_window_metrics(eq_df["equity"])

        value = f"{metrics['total_return_pct']:.1f}% ({metrics['multiple']:.2f}x)"
        if not np.isnan(bench_return):
            delta = f"Benchmark {bench_return:.1f}% ({bench_mult:.2f}x)"
        else:
            delta = None
        col.metric(label, value, delta=delta)

    if show_crypto:
        card_for_market(col_crypto, "קריפטו – אלטים", "CRYPTO", crypto_eq_f)
    if show_us:
        card_for_market(col_us, "מניות ארה\"ב", "US", us_eq_f)
    if show_il:
        card_for_market(col_il, "מניות ישראל", "IL", il_eq_f)

    # ===== גרף עקומות הון – Strategy בלבד כרגע =====
    st.subheader("עקומות הון – Strategy (טווח מסונן)")

    equity_chart_df = pd.DataFrame()

    if show_crypto and not crypto_eq_f.empty:
        equity_chart_df["Crypto Strategy"] = crypto_eq_f["equity"]

    if show_us and not us_eq_f.empty:
        if equity_chart_df.empty:
            equity_chart_df["US Strategy"] = us_eq_f["equity"]
        else:
            equity_chart_df["US Strategy"] = us_eq_f["equity"].reindex(equity_chart_df.index)

    if show_il and not il_eq_f.empty:
        if equity_chart_df.empty:
            equity_chart_df["IL Strategy"] = il_eq_f["equity"]
        else:
            equity_chart_df["IL Strategy"] = il_eq_f["equity"].reindex(equity_chart_df.index)

    if equity_chart_df.empty:
        st.warning("לא נבחרו שווקים להצגה.")
    else:
        equity_chart_df = equity_chart_df.ffill()
        st.line_chart(equity_chart_df)

    # ===== טבלת מדדים – סטטית מה-summary, אבל מסוננת לפי שווקים =====
    st.subheader("טבלת מדדים (על התקופה המלאה)")

    if not summary_df.empty:
        markets_to_show = []
        if show_crypto:
            markets_to_show.append("CRYPTO")
        if show_us:
            markets_to_show.append("US")
        if show_il:
            markets_to_show.append("IL")

        if markets_to_show:
            filtered = summary_df[summary_df["market"].isin(markets_to_show)].copy()
            st.dataframe(filtered.style.format({
                "total_return_pct": "{:.2f}",
                "multiple": "{:.2f}",
                "max_drawdown_pct": "{:.2f}",
                "win_rate_pct": "{:.2f}",
                "benchmark_return_pct": "{:.2f}",
                "benchmark_multiple": "{:.2f}",
            }))
        else:
            st.write("לא נבחרו שווקים להצגה בטבלה.")
    else:
        st.write("אין סיכום זמין.")

    # ===== הורדת קבצי Backtest =====
    st.subheader("הורדת קבצי Backtest")

    col1, col2, col3, col4 = st.columns(4)

    if not crypto_eq.empty:
        crypto_csv = crypto_eq.to_csv().encode("utf-8")
        col1.download_button(
            "הורד Crypto Equity (CSV)",
            data=crypto_csv,
            file_name="crypto_equity_curve.csv",
            mime="text/csv"
        )

    if not us_eq.empty:
        us_csv = us_eq.to_csv().encode("utf-8")
        col2.download_button(
            "הורד US Equity (CSV)",
            data=us_csv,
            file_name="us_equity_curve.csv",
            mime="text/csv"
        )

    if not il_eq.empty:
        il_csv = il_eq.to_csv().encode("utf-8")
        col3.download_button(
            "הורד IL Equity (CSV)",
            data=il_csv,
            file_name="il_equity_curve.csv",
            mime="text/csv"
        )

    if not summary_df.empty:
        summary_csv = summary_df.to_csv(index=False).encode("utf-8")
        col4.download_button(
            "הורד Summary (CSV)",
            data=summary_csv,
            file_name="multi_summary.csv",
            mime="text/csv"
        )

    st.caption("האפליקציה מציגה תוצאות Backtest בלבד. כדי לעדכן את הנתונים, הרץ שוב את multi_asset_momentum_backtest.py ולאחר מכן דחוף ל-GitHub ותרענן את האפליקציה.")


if __name__ == "__main__":
    main()
