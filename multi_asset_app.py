#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

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

    if summary_df.empty:
        st.warning("לא נמצא multi_summary.csv – סיכום מדדים יהיה חלקי.")

    # ===== בחירת שווקים (מסננים) =====
    st.sidebar.header("בחירת שווקים")
    show_crypto = st.sidebar.checkbox("קריפטו", value=not crypto_eq.empty)
    show_us = st.sidebar.checkbox("מניות ארה\"ב", value=not us_eq.empty)
    show_il = st.sidebar.checkbox("מניות ישראל", value=not il_eq.empty)

    # ===== כרטיסי מדדים למשקיעים =====
    st.subheader("סיכום ביצועים – Strategy מול Benchmark")

    col_crypto, col_us, col_il = st.columns(3)

    def metric_block(col, label, market_name):
        if summary_df.empty:
            col.metric(label, "N/A")
            return
        row = summary_df[summary_df["market"] == market_name]
        if row.empty:
            col.metric(label, "N/A")
            return
        r = row.iloc[0]
        value = f"{r['total_return_pct']:.1f}% ({r['multiple']:.2f}x)"
        delta = f"CAGR {r['cagr_pct']:.1f}% | Sharpe {r['sharpe']:.2f} | Calmar {r['calmar']:.2f}"
        col.metric(label, value, delta=delta)

    if show_crypto:
        metric_block(col_crypto, "קריפטו – אלטים", "CRYPTO")
    if show_us:
        metric_block(col_us, "מניות ארה\"ב", "US")
    if show_il:
        metric_block(col_il, "מניות ישראל", "IL")

    # ===== גרף עקומות הון – Strategy + Benchmark =====
    st.subheader("עקומות הון – Strategy מול Benchmark")

    equity_chart_df = pd.DataFrame()

    if show_crypto and not crypto_eq.empty:
        equity_chart_df["Crypto Strategy"] = crypto_eq["equity"]
        if "benchmark_equity" in crypto_eq.columns:
            equity_chart_df["Crypto Benchmark"] = crypto_eq["benchmark_equity"]

    if show_us and not us_eq.empty:
        if equity_chart_df.empty:
            equity_chart_df["US Strategy"] = us_eq["equity"]
            if "benchmark_equity" in us_eq.columns:
                equity_chart_df["US Benchmark"] = us_eq["benchmark_equity"]
        else:
            equity_chart_df["US Strategy"] = us_eq["equity"].reindex(equity_chart_df.index)
            if "benchmark_equity" in us_eq.columns:
                equity_chart_df["US Benchmark"] = us_eq["benchmark_equity"].reindex(equity_chart_df.index)

    if show_il and not il_eq.empty:
        if equity_chart_df.empty:
            equity_chart_df["IL Strategy"] = il_eq["equity"]
            if "benchmark_equity" in il_eq.columns:
                equity_chart_df["IL Benchmark"] = il_eq["benchmark_equity"]
        else:
            equity_chart_df["IL Strategy"] = il_eq["equity"].reindex(equity_chart_df.index)
            if "benchmark_equity" in il_eq.columns:
                equity_chart_df["IL Benchmark"] = il_eq["benchmark_equity"].reindex(equity_chart_df.index)

    if equity_chart_df.empty:
        st.warning("לא נבחרו שווקים להצגה.")
    else:
        equity_chart_df = equity_chart_df.ffill()
        st.line_chart(equity_chart_df)

    # ===== טבלת מדדים מלאה =====
    st.subheader("טבלת מדדים למשקיעים")

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
                "cagr_pct": "{:.2f}",
                "sharpe": "{:.2f}",
                "calmar": "{:.2f}",
                "max_drawdown_pct": "{:.2f}",
                "win_rate_pct": "{:.2f}",
                "benchmark_return_pct": "{:.2f}",
                "benchmark_multiple": "{:.2f}",
                "benchmark_cagr_pct": "{:.2f}",
            }))
        else:
            st.write("לא נבחרו שווקים להצגה בטבלה.")
    else:
        st.write("אין סיכום זמין.")

    # ===== הורדת קבצים =====
    st.subheader("הורדת קבצי Backtest")

    col1, col2, col3, col4 = st.columns(4)

    if not crypto_eq.empty:
        crypto_csv = crypto_eq.to_csv().encode("utf-8")
        col1.download_button(
            "הורד Crypto (Strategy+Benchmark)",
            data=crypto_csv,
            file_name="crypto_equity_curve.csv",
            mime="text/csv"
        )

    if not us_eq.empty:
        us_csv = us_eq.to_csv().encode("utf-8")
        col2.download_button(
            "הורד US (Strategy+Benchmark)",
            data=us_csv,
            file_name="us_equity_curve.csv",
            mime="text/csv"
        )

    if not il_eq.empty:
        il_csv = il_eq.to_csv().encode("utf-8")
        col3.download_button(
            "הורד IL (Strategy+Benchmark)",
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
