#!/usr/bin/env python3
# coding: utf-8

import os
from datetime import date
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st

RESULTS_DIR = "results_multi"

CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
MULTI_ADAPTIVE_FILE = os.path.join(RESULTS_DIR, "multi_adaptive_paper_equity.csv")

CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")

INITIAL_CAPITAL = 100000.0


def load_equity_csv(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df["equity"] = df["equity"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def align_raw(
    strat_df: Optional[pd.DataFrame],
    bench_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    if strat_df is None or strat_df.empty:
        return None
    df = strat_df[["date", "equity"]].rename(columns={"equity": "Strategy_raw"})
    if bench_df is not None and not bench_df.empty:
        b = bench_df[["date", "equity"]].rename(columns={"equity": "Benchmark_raw"})
        df = df.merge(b, on="date", how="inner")
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


def compute_metrics(equity_raw: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {
        "total_return": np.nan,
        "multiple": np.nan,
        "max_dd": np.nan,
        "sharpe": np.nan,
    }
    if equity_raw is None or len(equity_raw) < 2:
        return out

    eq = equity_raw.astype(float)
    start_val = float(eq.iloc[0])
    end_val = float(eq.iloc[-1])
    if start_val == 0:
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


def slice_raw(df_raw: Optional[pd.DataFrame], start: date, end: date) -> Optional[pd.DataFrame]:
    if df_raw is None or df_raw.empty:
        return df_raw
    mask = (df_raw["date"].dt.date >= start) & (df_raw["date"].dt.date <= end)
    return df_raw.loc[mask].copy()


def normalize_for_chart(df_raw_window: pd.DataFrame) -> pd.DataFrame:
    df = df_raw_window.copy()
    if "Strategy_raw" in df.columns:
        s0 = float(df["Strategy_raw"].iloc[0])
        df["Strategy"] = df["Strategy_raw"] * (INITIAL_CAPITAL / s0) if s0 != 0 else df["Strategy_raw"]
    if "Benchmark_raw" in df.columns:
        b0 = float(df["Benchmark_raw"].iloc[0])
        df["Benchmark"] = df["Benchmark_raw"] * (INITIAL_CAPITAL / b0) if b0 != 0 else df["Benchmark_raw"]
    return df


def normalize_single_for_chart(df_raw_window: pd.DataFrame) -> pd.DataFrame:
    df = df_raw_window.copy()
    if "equity" in df.columns:
        e0 = float(df["equity"].iloc[0])
        df["Strategy"] = df["equity"] * (INITIAL_CAPITAL / e0) if e0 != 0 else df["equity"]
    return df


def render_comparison_block(
    title: str,
    raw_df: Optional[pd.DataFrame],
    start: date,
    end: date,
    key_suffix: str,
) -> None:
    st.subheader(title)

    if raw_df is None or raw_df.empty:
        st.info("No data available for this strategy.")
    else:
        window_raw = slice_raw(raw_df, start, end)
        if window_raw is None or window_raw.empty:
            st.info("No data in selected date range.")
        else:
            strat_metrics = compute_metrics(window_raw["Strategy_raw"])
            bench_metrics = (
                compute_metrics(window_raw["Benchmark_raw"])
                if "Benchmark_raw" in window_raw.columns else None
            )

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Strategy Total Return", f"{strat_metrics['total_return']:.1f}%")
            with col2:
                st.metric("Strategy Multiple", f"{strat_metrics['multiple']:.2f}x")
            with col3:
                st.metric("Strategy Max DD", f"{strat_metrics['max_dd']:.1f}%")
            with col4:
                sharpe = strat_metrics["sharpe"]
                st.metric("Strategy Sharpe", "n/a" if np.isnan(sharpe) else f"{sharpe:.2f}")

            if bench_metrics is not None:
                colb1, colb2, colb3, colb4 = st.columns(4)
                with colb1:
                    st.metric("Benchmark Total Return", f"{bench_metrics['total_return']:.1f}%")
                with colb2:
                    st.metric("Benchmark Multiple", f"{bench_metrics['multiple']:.2f}x")
                with colb3:
                    st.metric("Benchmark Max DD", f"{bench_metrics['max_dd']:.1f}%")
                with colb4:
                    bsharpe = bench_metrics["sharpe"]
                    st.metric("Benchmark Sharpe", "n/a" if np.isnan(bsharpe) else f"{bsharpe:.2f}")

            st.markdown("---")

            norm_df = normalize_for_chart(window_raw).set_index("date")
            choice = st.radio(
                "Equity curves",
                options=["Strategy", "Benchmark", "Both"],
                index=2,
                horizontal=True,
                key=f"radio_{key_suffix}",
            )
            if choice == "Strategy":
                st.line_chart(norm_df[["Strategy"]], use_container_width=True, height=280)
            elif choice == "Benchmark" and "Benchmark" in norm_df.columns:
                st.line_chart(norm_df[["Benchmark"]], use_container_width=True, height=280)
            else:
                cols = ["Strategy"]
                if "Benchmark" in norm_df.columns:
                    cols.append("Benchmark")
                st.line_chart(norm_df[cols], use_container_width=True, height=280)

            st.markdown(
                f"אם משקיע היה שם 100,000 בתחילת התקופה, האסטרטגיה הייתה מגיעה ל־"
                f"{strat_metrics['multiple'] * 100000:,.0f} בערך, לעומת הבנצ'מרק "
                f"שהיה מגיע ל־{(bench_metrics['multiple'] * 100000 if bench_metrics else np.nan):,.0f}."
            )


def render_single_block(
    title: str,
    df_raw: Optional[pd.DataFrame],
    start: date,
    end: date,
    key_suffix: str,
) -> None:
    st.subheader(title)

    if df_raw is None or df_raw.empty:
        st.info("No data available for this portfolio.")
        return

    window_raw = slice_raw(df_raw, start, end)
    if window_raw is None or window_raw.empty:
        st.info("No data in selected date range.")
        return

    metrics = compute_metrics(window_raw["equity"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Return", f"{metrics['total_return']:.1f}%")
    with col2:
        st.metric("Multiple", f"{metrics['multiple']:.2f}x")
    with col3:
        st.metric("Max DD", f"{metrics['max_dd']:.1f}%")
    with col4:
        sharpe = metrics["sharpe"]
        st.metric("Sharpe", "n/a" if np.isnan(sharpe) else f"{sharpe:.2f}")

    st.markdown("---")

    norm_df = normalize_single_for_chart(window_raw).set_index("date")
    st.line_chart(norm_df[["Strategy"]], use_container_width=True, height=280)

    st.markdown(
        f"100,000 בתחילת התקופה גדלו לכ־{metrics['multiple'] * 100000:,.0f} בתיק המולטי‑אדפטיב, "
        f"עם Drawdown מקסימלי סביב {metrics['max_dd']:.1f}%."
    )


def main() -> None:
    st.set_page_config(page_title="Investor Paper Dashboard", layout="wide")

    crypto_strat = load_equity_csv(CRYPTO_STRAT_FILE)
    us_strat = load_equity_csv(US_STRAT_FILE)
    multi_adapt = load_equity_csv(MULTI_ADAPTIVE_FILE)

    crypto_bench = load_equity_csv(CRYPTO_BENCH_FILE)
    us_bench = load_equity_csv(US_BENCH_FILE)

    crypto_merge = align_raw(crypto_strat, crypto_bench)
    us_merge = align_raw(us_strat, us_bench)

    gmin, gmax = get_global_range([crypto_merge, us_merge, multi_adapt])

    if "filter_start" not in st.session_state:
        st.session_state["filter_start"] = gmin
    if "filter_end" not in st.session_state:
        st.session_state["filter_end"] = gmax

    with st.sidebar:
        st.header("Filters")
        temp_start = st.date_input(
            "Start date",
            value=st.session_state["filter_start"],
            min_value=gmin,
            max_value=gmax,
            key="temp_start",
        )
        temp_end = st.date_input(
            "End date",
            value=st.session_state["filter_end"],
            min_value=gmin,
            max_value=gmax,
            key="temp_end",
        )
        if st.button("Apply"):
            if temp_start > temp_end:
                st.error("Start date must be before end date.")
            else:
                st.session_state["filter_start"] = temp_start
                st.session_state["filter_end"] = temp_end

        st.markdown("---")
        st.header("Sections")
        show_crypto = st.checkbox("Crypto Strategy", value=True, key="sec_crypto")
        show_us = st.checkbox("US Strategy", value=True, key="sec_us")
        show_multi = st.checkbox("Multi-Adaptive Portfolio", value=True, key="sec_multi")

    start_sel = st.session_state["filter_start"]
    end_sel = st.session_state["filter_end"]

    st.title("Paper Trading Results – Investor View")
    st.caption(
        "כל המספרים מבוססים על Paper Trading בוטים אוטומטיים (ללא החלקת ביצועים). "
        "הדגש: תשואה מול בנצ'מרק תחת שליטה ב‑Drawdown."
    )
    st.write(f"Range: {start_sel} → {end_sel}")
    st.markdown("---")

    tab_overview, tab_crypto, tab_us, tab_multi = st.tabs(
        ["Overview", "Crypto", "US", "Multi-Adaptive"]
    )

    with tab_overview:
        st.subheader("High-Level Snapshot")
        cols = st.columns(3)

        if crypto_merge is not None and not crypto_merge.empty:
            w = slice_raw(crypto_merge, start_sel, end_sel)
            ms = compute_metrics(w["Strategy_raw"])
            mb = compute_metrics(w["Benchmark_raw"])
            with cols[0]:
                st.metric("Crypto vs BTC (Strategy)", f"{ms['total_return']:.0f}%")
                st.metric("BTC Benchmark", f"{mb['total_return']:.0f}%")

        if us_merge is not None and not us_merge.empty:
            w = slice_raw(us_merge, start_sel, end_sel)
            ms = compute_metrics(w["Strategy_raw"])
            mb = compute_metrics(w["Benchmark_raw"])
            with cols[1]:
                st.metric("US vs Benchmark (Strategy)", f"{ms['total_return']:.0f}%")
                st.metric("US Benchmark", f"{mb['total_return']:.0f}%")

        if multi_adapt is not None and not multi_adapt.empty:
            w = slice_raw(multi_adapt, start_sel, end_sel)
            ms = compute_metrics(w["equity"])
            with cols[2]:
                st.metric("Multi-Adaptive Portfolio", f"{ms['total_return']:.0f}%")
                st.metric("Max DD", f"{ms['max_dd']:.0f}%")

        st.markdown("---")
        st.markdown(
            "המשמעות: אנחנו מכים את הבנצ'מרק בקריפטו (בערך 10x מול ~3x ב‑BTC) "
            "וב‑US (בערך 3.6x מול ~2.7x), ומעמיסים אותם לתיק אחד שמאזן ביניהם."
        )

    with tab_crypto:
        if show_crypto:
            render_comparison_block(
                "Crypto Strategy vs BTC",
                crypto_merge,
                start_sel,
                end_sel,
                key_suffix="crypto",
            )

    with tab_us:
        if show_us:
            render_comparison_block(
                "US Strategy vs US Benchmark",
                us_merge,
                start_sel,
                end_sel,
                key_suffix="us",
            )

    with tab_multi:
        if show_multi:
            render_single_block(
                "Multi-Adaptive Portfolio (Crypto + US)",
                multi_adapt,
                start_sel,
                end_sel,
                key_suffix="multi",
            )


if __name__ == "__main__":
    main()
