#!/usr/bin/env python3
# coding: utf-8
# multi_asset_app.py
# Streamlit Dashboard – Paper Trading 2022-2025
# Four tabs: Overview, Crypto, US, Multi-Adaptive
# Date range is applied only when pressing "Apply filters"
# Summary tables appear at the top of Overview
# All charts show Strategy + Benchmark together when available

import os
from datetime import date
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# Configuration – file paths (original structure from your project)
# ---------------------------------------------------------------------

RESULTS_DIR = "resultsmulti"

CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "cryptopaperequity.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "uspaperequity.csv")
MULTI_ADAPTIVE_FILE = os.path.join(RESULTS_DIR, "multiadaptivepaperequity.csv")

CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "cryptoequitycurve.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "usequitycurve.csv")

MULTI_SUMMARY_FILE = os.path.join(RESULTS_DIR, "multiassetsummary.csv")
MULTI_ADAPTIVE_SUMMARY_FILE = os.path.join(RESULTS_DIR, "multiadaptivepapersummary.csv")

INITIAL_CAPITAL = 100000.0

# ---------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------


def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError(
            f"equity - {label} must have 'date','equity' columns in {path}"
        )
    df["date"] = pd.to_datetime(df["date"])
    df["equity"] = df["equity"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def align_strategy_benchmark_raw(
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


# ---------------------------------------------------------------------
# Metrics and normalization
# ---------------------------------------------------------------------


def compute_metrics_from_raw(equity_raw: pd.Series) -> Dict[str, float]:
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


def make_normalized_for_chart(df_raw_window: pd.DataFrame) -> pd.DataFrame:
    df = df_raw_window.copy()
    # Strategy normalized
    if "Strategy_raw" in df.columns:
        s0 = float(df["Strategy_raw"].iloc[0])
        if s0 != 0:
            df["Strategy"] = df["Strategy_raw"] * (INITIAL_CAPITAL / s0)
        else:
            df["Strategy"] = df["Strategy_raw"]
    # Benchmark normalized
    if "Benchmark_raw" in df.columns:
        b0 = float(df["Benchmark_raw"].iloc[0])
        if b0 != 0:
            df["Benchmark"] = df["Benchmark_raw"] * (INITIAL_CAPITAL / b0)
        else:
            df["Benchmark"] = df["Benchmark_raw"]
    return df


# ---------------------------------------------------------------------
# Summary formatting
# ---------------------------------------------------------------------


def load_summary_csv(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def format_legacy_summary_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["total_return_pct", "cagr_pct", "max_drawdown_pct"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) and not np.isnan(x) else ""
            )
    for col in ["start_equity", "end_equity"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) and not np.isnan(x) else ""
            )
    return out


def format_adaptive_summary_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["totalreturnpct", "cagrpct", "maxdrawdownpct"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) and not np.isnan(x) else ""
            )
    for col in ["startequity", "endequity"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) and not np.isnan(x) else ""
            )
    return out


# ---------------------------------------------------------------------
# UI components – reusable blocks
# ---------------------------------------------------------------------


def render_big_numbers_block(
    title: str,
    raw_df: Optional[pd.DataFrame],
    start: date,
    end: date,
    key_suffix: str,
) -> None:
    st.subheader(title)
    if raw_df is None or raw_df.empty:
        st.info("No data available for this engine.")
        return

    window_raw = slice_raw(raw_df, start, end)
    if window_raw is None or window_raw.empty:
        st.info("No data in selected date range.")
        return

    strat_metrics = compute_metrics_from_raw(window_raw["Strategy_raw"])
    bench_metrics = (
        compute_metrics_from_raw(window_raw["Benchmark_raw"])
        if "Benchmark_raw" in window_raw.columns
        else None
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
        st.metric("Strategy Sharpe", "na" if np.isnan(sharpe) else f"{sharpe:.2f}")

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
            st.metric(
                "Benchmark Sharpe",
                "na" if np.isnan(bsharpe) else f"{bsharpe:.2f}",
            )

    st.markdown("---")

    # Always show Strategy + Benchmark together when available
    norm_df = make_normalized_for_chart(window_raw).set_index("date")
    cols = ["Strategy"]
    if "Benchmark" in norm_df.columns:
        cols.append("Benchmark")
    st.line_chart(norm_df[cols], use_container_width=True, height=300)


def render_multi_adaptive_block(
    title: str,
    raw_df: Optional[pd.DataFrame],
    start: date,
    end: date,
    key_suffix: str,
) -> None:
    st.subheader(title)
    if raw_df is None or raw_df.empty:
        st.info("No data available for Multi-Adaptive.")
        return

    df = raw_df[["date", "equity"]].rename(columns={"equity": "Strategy_raw"})
    window_raw = slice_raw(df, start, end)
    if window_raw is None or window_raw.empty:
        st.info("No data in selected date range.")
        return

    metrics = compute_metrics_from_raw(window_raw["Strategy_raw"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Return", f"{metrics['total_return']:.1f}%")
    with col2:
        st.metric("Multiple", f"{metrics['multiple']:.2f}x")
    with col3:
        st.metric("Max DD", f"{metrics['max_dd']:.1f}%")
    with col4:
        sharpe = metrics["sharpe"]
        st.metric("Sharpe", "na" if np.isnan(sharpe) else f"{sharpe:.2f}")

    st.markdown("---")

    norm_df = make_normalized_for_chart(window_raw).set_index("date")
    st.line_chart(norm_df["Strategy"], use_container_width=True, height=300)


# ---------------------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Multi-Asset Paper Dashboard",
        layout="wide",
    )

    # Load raw equity curves
    crypto_strat_raw = load_equity_csv(CRYPTO_STRAT_FILE, "CRYPTO_STRATEGY")
    us_strat_raw = load_equity_csv(US_STRAT_FILE, "US_STRATEGY")
    multi_adapt_raw = load_equity_csv(MULTI_ADAPTIVE_FILE, "MULTI_ADAPTIVE")

    crypto_bench_raw = load_equity_csv(CRYPTO_BENCH_FILE, "CRYPTO_BENCH")
    us_bench_raw = load_equity_csv(US_BENCH_FILE, "US_BENCH")

    crypto_merge_raw = align_strategy_benchmark_raw(crypto_strat_raw, crypto_bench_raw)
    us_merge_raw = align_strategy_benchmark_raw(us_strat_raw, us_bench_raw)
    multi_merge_raw = align_strategy_benchmark_raw(multi_adapt_raw, None)

    gmin, gmax = get_global_range([crypto_merge_raw, us_merge_raw, multi_merge_raw])

    # Session state for date filters
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
            key="temp_start_date",
        )
        temp_end = st.date_input(
            "End date",
            value=st.session_state["filter_end"],
            min_value=gmin,
            max_value=gmax,
            key="temp_end_date",
        )
        if st.button("Apply filters", key="apply_filters"):
            if temp_start > temp_end:
                st.error("Start date must be before end date.")
            else:
                st.session_state["filter_start"] = temp_start
                st.session_state["filter_end"] = temp_end
        st.markdown("---")
        st.header("Sections")
        show_crypto = st.checkbox("Crypto", value=True, key="chk_crypto")
        show_us = st.checkbox("US", value=True, key="chk_us")
        show_multi = st.checkbox("Multi-Adaptive", value=True, key="chk_multi")

    start_sel = st.session_state["filter_start"]
    end_sel = st.session_state["filter_end"]

    st.title("Multi-Asset Strategy Dashboard – Paper Trading")
    st.caption(
        "Crypto, US, Multi-Adaptive (Crypto+US). Israel segment excluded. "
        "Metrics on raw equity, charts normalized to 100,000. "
        "Date range updates only when pressing Apply filters."
    )
    st.write(f"Selected range: {start_sel} to {end_sel}")
    st.markdown("---")

    tab_overview, tab_crypto, tab_us, tab_multi = st.tabs(
        ["Overview", "Crypto", "US", "Multi-Adaptive"]
    )

    # ---------------------- Overview tab ----------------------
    with tab_overview:
        st.subheader("Summary tables")

        multisummary = load_summary_csv(MULTI_SUMMARY_FILE)
        if multisummary is not None and not multisummary.empty:
            # keep only CRYPTO and US for legacy summary
            if "name" in multisummary.columns:
                filtered = multisummary[multisummary["name"].isin(["CRYPTO", "US"])]
                filtered = filtered.reset_index(drop=True)
            else:
                filtered = multisummary
            if not filtered.empty:
                st.markdown("Legacy Multi-Engine Summary (Crypto and US only)")
                st.dataframe(
                    format_legacy_summary_df(filtered),
                    use_container_width=True,
                )
            else:
                st.info("No CRYPTO/US rows in multiassetsummary.csv.")
        else:
            st.info("multiassetsummary.csv not found (optional).")

        multiadaptive_summary = load_summary_csv(MULTI_ADAPTIVE_SUMMARY_FILE)
        if multiadaptive_summary is not None and not multiadaptive_summary.empty:
            st.markdown("Multi-Adaptive Portfolio Summary (Crypto+US)")
            st.dataframe(
                format_adaptive_summary_df(multiadaptive_summary),
                use_container_width=True,
            )
        else:
            st.info("multiadaptivepapersummary.csv not found (optional).")

        st.markdown("---")
        st.subheader("Overview – Strategy vs Benchmark")

        if show_crypto:
            render_big_numbers_block(
                "Crypto Strategy vs BTC",
                crypto_merge_raw,
                start_sel,
                end_sel,
                key_suffix="overview_crypto",
            )
        if show_us:
            render_big_numbers_block(
                "US Strategy vs Benchmark",
                us_merge_raw,
                start_sel,
                end_sel,
                key_suffix="overview_us",
            )
        if show_multi:
            render_multi_adaptive_block(
                "Multi-Adaptive Portfolio (Crypto+US)",
                multi_adapt_raw,
                start_sel,
                end_sel,
                key_suffix="overview_multi",
            )

    # ---------------------- Crypto tab ----------------------
    with tab_crypto:
        st.subheader("Crypto Engine – Strategy vs BTC Benchmark")
        render_big_numbers_block(
            "Crypto Strategy vs BTC",
            crypto_merge_raw,
            start_sel,
            end_sel,
            key_suffix="crypto_tab",
        )

    # ---------------------- US tab ----------------------
    with tab_us:
        st.subheader("US Engine – Strategy vs US Benchmark")
        render_big_numbers_block(
            "US Strategy vs Benchmark",
            us_merge_raw,
            start_sel,
            end_sel,
            key_suffix="us_tab",
        )

    # ---------------------- Multi-Adaptive tab ----------------------
    with tab_multi:
        st.subheader("Multi-Adaptive Portfolio (Crypto+US)")
        render_multi_adaptive_block(
            "Multi-Adaptive Portfolio (Crypto+US)",
            multi_adapt_raw,
            start_sel,
            end_sel,
            key_suffix="multi_tab",
        )


if __name__ == "__main__":
    main()
