#!/usr/bin/env python3
# coding: utf-8

import os
from datetime import date
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

RESULTS_DIR = "results_multi"

CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
MULTI_ADAPTIVE_FILE = os.path.join(RESULTS_DIR, "multi_adaptive_paper_equity.csv")

CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")

MULTI_SUMMARY_FILE = os.path.join(RESULTS_DIR, "multi_asset_summary.csv")
MULTI_ADAPTIVE_SUMMARY_FILE = os.path.join(RESULTS_DIR, "multi_adaptive_paper_summary.csv")

INITIAL_CAPITAL = 100_000.0


def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if "date" not in df.columns or "equity" not in df.columns:
        raise ValueError(f"equity - {label} חייב לכלול עמודות date,equity בקובץ {path}")
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
    dd = eq - roll_max
    dd_pct = dd / roll_max
    out["max_dd"] = float(dd_pct.min() * 100.0)

    rets = eq.pct_change().dropna()
    if len(rets) > 0 and rets.std() != 0:
        out["sharpe"] = float(rets.mean() / rets.std() * np.sqrt(252.0))

    return out


def slice_raw_df(
    df_raw: Optional[pd.DataFrame],
    start: date,
    end: date,
) -> Optional[pd.DataFrame]:
    if df_raw is None or df_raw.empty:
        return df_raw
    mask = (df_raw["date"].dt.date >= start) & (df_raw["date"].dt.date <= end)
    sub = df_raw.loc[mask].copy()
    if sub.empty:
        return None
    return sub


def make_normalized_for_chart(df_raw_window: pd.DataFrame) -> pd.DataFrame:
    df = df_raw_window.copy()
    if "Strategy_raw" in df.columns:
        s0 = float(df["Strategy_raw"].iloc[0])
        if s0 != 0:
            df["Strategy"] = df["Strategy_raw"] * INITIAL_CAPITAL / s0
        else:
            df["Strategy"] = df["Strategy_raw"]
    if "Benchmark_raw" in df.columns:
        b0 = float(df["Benchmark_raw"].iloc[0])
        if b0 != 0:
            df["Benchmark"] = df["Benchmark_raw"] * INITIAL_CAPITAL / b0
        else:
            df["Benchmark"] = df["Benchmark_raw"]
    return df


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


def plot_equity_curves(norm_df: pd.DataFrame, show_cols: List[str], key: str) -> None:
    if norm_df.empty:
        st.info("No data to plot.")
        return

    df = norm_df.reset_index().copy()
    df["date"] = pd.to_datetime(df["date"])

    long_rows = []
    for col in show_cols:
        if col in df.columns:
            tmp = df[["date", col]].rename(columns={col: "equity"})
            tmp["curve"] = col
            long_rows.append(tmp)
    if not long_rows:
        st.info("No selected curves to plot.")
        return

    plot_df = pd.concat(long_rows, ignore_index=True)

    fig = px.line(
        plot_df,
        x="date",
        y="equity",
        color="curve",
        title=None,
        labels={"equity": "Equity", "date": "Date", "curve": "Curve"},
    )

    fig.update_layout(
        xaxis=dict(
            tickformat="%Y-%m",
            showgrid=True,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=10, r=10, t=10, b=40),
        height=320,
    )

    st.plotly_chart(fig, use_container_width=True, key=key)


def render_strategy_benchmark_summary_table(
    label: str,
    merge_df: Optional[pd.DataFrame],
    start: date,
    end: date,
) -> None:
    if merge_df is None or merge_df.empty:
        st.info(f"No data for {label} summary.")
        return

    window = slice_raw_df(merge_df, start, end)
    if window is None or window.empty:
        st.info(f"No data for {label} in selected range.")
        return

    rows = []
    strat = compute_metrics_from_raw(window["Strategy_raw"])
    rows.append(
        {
            "Segment": label,
            "Type": "Strategy",
            "Total Return %": strat["total_return"],
            "Multiple x": strat["multiple"],
            "Max DD %": strat["max_dd"],
            "Sharpe": strat["sharpe"],
        }
    )
    if "Benchmark_raw" in window.columns:
        bench = compute_metrics_from_raw(window["Benchmark_raw"])
        rows.append(
            {
                "Segment": label,
                "Type": "Benchmark",
                "Total Return %": bench["total_return"],
                "Multiple x": bench["multiple"],
                "Max DD %": bench["max_dd"],
                "Sharpe": bench["sharpe"],
            }
        )

    df = pd.DataFrame(rows)
    df = df.round(
        {
            "Total Return %": 1,
            "Multiple x": 2,
            "Max DD %": 1,
            "Sharpe": 2,
        }
    )
    st.dataframe(df, use_container_width=True)


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

    window_raw = slice_raw_df(raw_df, start, end)
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
        with col4:
            bsharpe = bench_metrics["sharpe"]
            st.metric(
                "Benchmark Sharpe",
                "na" if np.isnan(bsharpe) else f"{bsharpe:.2f}",
            )

    st.markdown("---")

    norm_df = make_normalized_for_chart(window_raw).set_index("date")

    choice = st.radio(
        "Select equity curve to display",
        options=["Strategy", "Benchmark", "Both"],
        index=2,
        horizontal=True,
        key=f"radio_{key_suffix}",
    )

    if choice == "Strategy":
        cols = ["Strategy"]
    elif choice == "Benchmark" and "Benchmark" in norm_df.columns:
        cols = ["Benchmark"]
    else:
        cols = ["Strategy"]
        if "Benchmark" in norm_df.columns:
            cols.append("Benchmark")

    plot_equity_curves(norm_df, cols, key=f"plot_{key_suffix}")


def render_multi_adaptive_block_with_underlying(
    multi_raw: Optional[pd.DataFrame],
    crypto_raw: Optional[pd.DataFrame],
    us_raw: Optional[pd.DataFrame],
    start: date,
    end: date,
    key_suffix: str,
) -> None:
    if multi_raw is None or multi_raw.empty:
        st.info("No data available for Multi-Adaptive.")
        return

    multi_df = multi_raw[["date", "equity"]].rename(columns={"equity": "Multi_raw"})
    multi_window = slice_raw_df(multi_df, start, end)
    crypto_window = slice_raw_df(crypto_raw, start, end) if crypto_raw is not None else None
    us_window = slice_raw_df(us_raw, start, end) if us_raw is not None else None

    if multi_window is None or multi_window.empty:
        st.info("No Multi-Adaptive data in selected range.")
        return

    merged = multi_window[["date", "Multi_raw"]]
    if crypto_window is not None and "Strategy_raw" in crypto_window.columns:
        merged = merged.merge(
            crypto_window[["date", "Strategy_raw"]].rename(
                columns={"Strategy_raw": "Crypto_raw"}
            ),
            on="date",
            how="left",
        )
    if us_window is not None and "Strategy_raw" in us_window.columns:
        merged = merged.merge(
            us_window[["date", "Strategy_raw"]].rename(
                columns={"Strategy_raw": "US_raw"}
            ),
            on="date",
            how="left",
        )

    merged = merged.sort_values("date").reset_index(drop=True)

    for col in ["Multi_raw", "Crypto_raw", "US_raw"]:
        if col in merged.columns and merged[col].notna().any():
            start_val = float(merged[col].dropna().iloc[0])
            if start_val != 0:
                merged[col.replace("_raw", "")] = (
                    merged[col] * INITIAL_CAPITAL / start_val
                )

    merged = merged.set_index("date")

    available = [c for c in ["Multi", "Crypto", "US"] if c in merged.columns]

    st.subheader("Multi-Adaptive Portfolio vs Crypto & US (Strategy curves only)")

    col_multi, col_crypto, col_us = st.columns(3)
    with col_multi:
        show_multi = st.checkbox("Show Multi", value=True, key=f"chk_multi_{key_suffix}")
    with col_crypto:
        show_crypto = st.checkbox("Show Crypto", value=True, key=f"chk_crypto_{key_suffix}")
    with col_us:
        show_us_curve = st.checkbox("Show US", value=True, key=f"chk_us_{key_suffix}")

    show_cols = []
    if show_multi and "Multi" in available:
        show_cols.append("Multi")
    if show_crypto and "Crypto" in available:
        show_cols.append("Crypto")
    if show_us_curve and "US" in available:
        show_cols.append("US")

    if not show_cols:
        show_cols = available  # אם המשתמש כיבה הכל – נציג הכל כדי שלא יהיה גרף ריק.

    plot_equity_curves(merged, show_cols, key=f"plot_multi_underlying_{key_suffix}")


def main() -> None:
    st.set_page_config(page_title="Multi-Asset Paper Dashboard", layout="wide")

    crypto_strat_raw = load_equity_csv(CRYPTO_STRAT_FILE, "CRYPTO_STRATEGY")
    us_strat_raw = load_equity_csv(US_STRAT_FILE, "US_STRATEGY")
    multi_adapt_raw = load_equity_csv(MULTI_ADAPTIVE_FILE, "MULTI_ADAPTIVE")

    crypto_bench_raw = load_equity_csv(CRYPTO_BENCH_FILE, "CRYPTO_BENCH")
    us_bench_raw = load_equity_csv(US_BENCH_FILE, "US_BENCH")

    crypto_merge_raw = align_strategy_benchmark_raw(crypto_strat_raw, crypto_bench_raw)
    us_merge_raw = align_strategy_benchmark_raw(us_strat_raw, us_bench_raw)
    multi_merge_raw = align_strategy_benchmark_raw(multi_adapt_raw, None)

    gmin, gmax = get_global_range([crypto_merge_raw, us_merge_raw, multi_merge_raw])

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
        apply_clicked = st.button("Apply filters", key="apply_filters")
        if apply_clicked:
            if temp_start > temp_end:
                st.error("Start date must be before end date.")
            else:
                st.session_state["filter_start"] = temp_start
                st.session_state["filter_end"] = temp_end

        st.markdown("---")
        st.header("Sections")
        show_crypto_tab = st.checkbox("Crypto", value=True, key="chk_crypto_tab")
        show_us_tab = st.checkbox("US", value=True, key="chk_us_tab")
        show_multi_tab = st.checkbox("Multi-Adaptive", value=True, key="chk_multi_tab")

    start_sel = st.session_state["filter_start"]
    end_sel = st.session_state["filter_end"]

    st.title("Multi-Asset Strategy Dashboard – Paper Trading")
    st.caption(
        "Crypto, US, Multi-Adaptive (Crypto+US). "
        "Israel segment excluded. Metrics from RAW equity, charts normalized to 100,000 per view."
    )
    st.write(f"Selected range: {start_sel} -> {end_sel}")
    st.markdown("---")

    tab_overview, tab_crypto, tab_us, tab_multi = st.tabs(
        ["Overview", "Crypto", "US", "Multi-Adaptive"]
    )

    with tab_overview:
        st.subheader("Summary tables")
        multi_summary = load_summary_csv(MULTI_SUMMARY_FILE)
        if multi_summary is not None and not multi_summary.empty:
            filtered = multi_summary[
                multi_summary["name"].isin(["CRYPTO", "US"])
            ].reset_index(drop=True)
            if not filtered.empty:
                st.markdown("Legacy Multi-Engine Summary – Crypto and US only")
                st.dataframe(
                    format_legacy_summary_df(filtered),
                    use_container_width=True,
                )
            else:
                st.info("No CRYPTO/US rows in multi_asset_summary.csv.")
        else:
            st.info("multi_asset_summary.csv not found (optional).")

        multi_adaptive_summary = load_summary_csv(MULTI_ADAPTIVE_SUMMARY_FILE)
        if multi_adaptive_summary is not None and not multi_adaptive_summary.empty:
            st.markdown("Multi-Adaptive Portfolio Summary (Crypto+US)")
            st.dataframe(
                format_adaptive_summary_df(multi_adaptive_summary),
                use_container_width=True,
            )
        else:
            st.info("multi_adaptive_paper_summary.csv not found.")

        st.markdown("---")
        st.subheader("Overview – Strategy vs Benchmark")
        if show_crypto_tab:
            render_big_numbers_block(
                "Crypto Strategy vs BTC-USD Benchmark",
                crypto_merge_raw,
                start_sel,
                end_sel,
                key_suffix="overview_crypto",
            )
        if show_us_tab:
            render_big_numbers_block(
                "US Strategy vs SPY Benchmark",
                us_merge_raw,
                start_sel,
                end_sel,
                key_suffix="overview_us",
            )
        if show_multi_tab:
            render_multi_adaptive_block_with_underlying(
                multi_adapt_raw,
                crypto_merge_raw,
                us_merge_raw,
                start_sel,
                end_sel,
                key_suffix="overview_multi",
            )

    with tab_crypto:
        st.subheader("Crypto Summary – Strategy vs Benchmark")
        render_strategy_benchmark_summary_table(
            "Crypto", crypto_merge_raw, start_sel, end_sel
        )
        st.markdown("---")
        st.subheader("Crypto Engine – Strategy vs BTC-USD Benchmark")
        render_big_numbers_block(
            "Crypto Strategy vs BTC-USD Benchmark",
            crypto_merge_raw,
            start_sel,
            end_sel,
            key_suffix="crypto_tab",
        )

    with tab_us:
        st.subheader("US Summary – Strategy vs Benchmark")
        render_strategy_benchmark_summary_table(
            "US", us_merge_raw, start_sel, end_sel
        )
        st.markdown("---")
        st.subheader("US Engine – Strategy vs SPY Benchmark")
        render_big_numbers_block(
            "US Strategy vs SPY Benchmark",
            us_merge_raw,
            start_sel,
            end_sel,
            key_suffix="us_tab",
        )

    with tab_multi:
        st.subheader("Multi-Adaptive Summary – Multi, Crypto, US (Strategy only)")
        rows = []
        for label, df in [
            ("Multi-Adaptive", multi_merge_raw),
            ("Crypto", crypto_merge_raw),
            ("US", us_merge_raw),
        ]:
            if df is None or df.empty:
                continue
            window = slice_raw_df(df, start_sel, end_sel)
            if window is None or window.empty:
                continue
            m = compute_metrics_from_raw(window["Strategy_raw"])
            rows.append(
                {
                    "Segment": label,
                    "Total Return %": m["total_return"],
                    "Multiple x": m["multiple"],
                    "Max DD %": m["max_dd"],
                    "Sharpe": m["sharpe"],
                }
            )
        if rows:
            tbl = pd.DataFrame(rows).round(
                {
                    "Total Return %": 1,
                    "Multiple x": 2,
                    "Max DD %": 1,
                    "Sharpe": 2,
                }
            )
            st.dataframe(tbl, use_container_width=True)
        else:
            st.info("No data for Multi/Crypto/US in selected range.")

        st.markdown("---")
        render_multi_adaptive_block_with_underlying(
            multi_adapt_raw,
            crypto_merge_raw,
            us_merge_raw,
            start_sel,
            end_sel,
            key_suffix="multi_tab",
        )


if __name__ == "__main__":
    main()
