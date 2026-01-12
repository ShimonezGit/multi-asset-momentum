#!/usr/bin/env python3
# coding: utf-8

import os
from datetime import date
from typing import Optional, Dict, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# קונפיגורציה
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsmulti")

CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")

US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")

CRYPTO_DAILY_FILE = os.path.join(RESULTS_DIR, "crypto_daily_summary.csv")
CRYPTO_DAILY_PRETTY_FILE = os.path.join(RESULTS_DIR, "crypto_daily_summary_pretty.csv")

US_DAILY_FILE = os.path.join(RESULTS_DIR, "us_daily_summary.csv")
US_DAILY_PRETTY_FILE = os.path.join(RESULTS_DIR, "us_daily_summary_pretty.csv")

INITIAL_CAPITAL = 100000.0


# ---------------------------------------------------------------------
# טעינת דאטה – Equity
# ---------------------------------------------------------------------

def load_equity_csv(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        st.warning(f"{label}: הקובץ לא נמצא: {path}")
        return None
    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"{label}: כשל בקריאת הקובץ {path}: {e}")
        return None
    if "date" not in df.columns or "equity" not in df.columns:
        st.error(f"{label}: חסרות עמודות date/equity בקובץ {path}")
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)
    df["equity"] = df["equity"].astype(float)
    return df[["date", "equity"]]


def align_strategy_benchmark(strat: Optional[pd.DataFrame],
                             bench: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if strat is None or strat.empty:
        return None

    df = strat.copy()
    df = df.rename(columns={"equity": "Strategy"})

    if len(df) > 0:
        first = float(df["Strategy"].iloc[0])
        if first != 0:
            factor = INITIAL_CAPITAL / first
            df["Strategy"] = df["Strategy"].astype(float) * factor

    if bench is not None and not bench.empty:
        b = bench.copy()
        b = b.rename(columns={"equity": "Benchmark"})
        if len(b) > 0:
            firstb = float(b["Benchmark"].iloc[0])
            if firstb != 0:
                factorb = INITIAL_CAPITAL / firstb
                b["Benchmark"] = b["Benchmark"].astype(float) * factorb
        df = df.merge(b[["date", "Benchmark"]], on="date", how="inner")

    return df


def get_global_date_range(dfs: List[Optional[pd.DataFrame]]) -> Tuple[date, date]:
    dates: List[pd.Timestamp] = []
    for df in dfs:
        if df is not None and not df.empty and "date" in df.columns:
            dates.append(df["date"].min())
            dates.append(df["date"].max())
    if not dates:
        today = date.today()
        return today, today
    return min(dates).date(), max(dates).date()


# ---------------------------------------------------------------------
# מדדים ו-summary
# ---------------------------------------------------------------------

def compute_metrics(equity: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {
        "total_return": np.nan,
        "multiple": np.nan,
        "max_dd": np.nan,
        "sharpe": np.nan,
    }
    if equity is None or len(equity) < 2:
        return out
    eq = equity.astype(float)
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
    out["max_dd"] = float(dd_pct.min()) * 100.0

    rets = eq.pct_change().dropna()
    if len(rets) > 0 and rets.std() != 0:
        out["sharpe"] = float(rets.mean() / rets.std() * np.sqrt(252.0))
    return out


def compute_summary_row(name: str, df: Optional[pd.DataFrame]) -> Dict[str, object]:
    row: Dict[str, object] = {
        "name": name,
        "start_date": "",
        "end_date": "",
        "start_equity": np.nan,
        "end_equity": np.nan,
        "total_return_pct": np.nan,
        "cagr_pct": np.nan,
        "max_drawdown_pct": np.nan,
    }
    if df is None or df.empty:
        return row

    df = df.sort_values("date").reset_index(drop=True)
    start_date = df["date"].iloc[0]
    end_date = df["date"].iloc[-1]
    start_eq = float(df["equity"].iloc[0])
    end_eq = float(df["equity"].iloc[-1])

    years = max((end_date - start_date).days / 365.25, 1e-6)
    total_return = end_eq / start_eq - 1.0
    cagr = (end_eq / start_eq) ** (1.0 / years) - 1.0

    roll_max = df["equity"].cummax()
    dd = df["equity"] - roll_max
    dd_pct = dd / roll_max
    max_dd = float(dd_pct.min()) * 100.0

    row["start_date"] = start_date.date().isoformat()
    row["end_date"] = end_date.date().isoformat()
    row["start_equity"] = start_eq
    row["end_equity"] = end_eq
    row["total_return_pct"] = total_return * 100.0
    row["cagr_pct"] = cagr * 100.0
    row["max_drawdown_pct"] = max_dd
    return row


def format_summary_df(df: pd.DataFrame) -> pd.DataFrame:
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


# ---------------------------------------------------------------------
# טעינת דיילי
# ---------------------------------------------------------------------

def load_daily_raw(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        st.warning(f"{label}: קובץ דיילי RAW לא נמצא: {path}")
        return None
    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"{label}: כשל בקריאת daily raw: {e}")
        return None
    if "date" not in df.columns:
        st.error(f"{label}: חסרה עמודת date ב-daily raw")
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_daily_pretty(path: str, label: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        st.info(f"{label}: קובץ pretty לא נמצא (לא חובה): {path}")
        return None
    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"{label}: כשל בקריאת daily pretty: {e}")
        return None
    return df


# ---------------------------------------------------------------------
# UI – גרף Equity
# ---------------------------------------------------------------------

def render_equity_block(title: str,
                        merged: Optional[pd.DataFrame],
                        start_sel: date,
                        end_sel: date,
                        key_suffix: str) -> None:
    st.subheader(title)
    if merged is None or merged.empty:
        st.info("אין דאטה למנוע הזה.")
        return

    mask = (merged["date"].dt.date >= start_sel) & (merged["date"].dt.date <= end_sel)
    sub = merged.loc[mask].copy()
    if sub.empty:
        st.info("אין דאטה בטווח תאריכים שנבחר.")
        return

    strat_metrics = compute_metrics(sub["Strategy"])
    bench_metrics = compute_metrics(sub["Benchmark"]) if "Benchmark" in sub.columns else None

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
            st.metric("Benchmark Sharpe", "na" if np.isnan(bsharpe) else f"{bsharpe:.2f}")

    st.markdown("---")
    choice = st.radio(
        "איזו עקומה להציג?",
        options=["Strategy", "Benchmark", "Both"],
        index=2,
        horizontal=True,
        key=f"radio_equity_{key_suffix}",
    )

    chart_df = sub.set_index("date")
    if choice == "Strategy":
        st.line_chart(chart_df["Strategy"], use_container_width=True, height=320)
    elif choice == "Benchmark" and "Benchmark" in chart_df.columns:
        st.line_chart(chart_df["Benchmark"], use_container_width=True, height=320)
    else:
        cols = ["Strategy"]
        if "Benchmark" in chart_df.columns:
            cols.append("Benchmark")
        st.line_chart(chart_df[cols], use_container_width=True, height=320)


# ---------------------------------------------------------------------
# UI – גרף Daily PnL Strategy vs Benchmark
# ---------------------------------------------------------------------

def render_pnl_block(title: str,
                     daily_raw: Optional[pd.DataFrame],
                     bench_equity: Optional[pd.DataFrame],
                     prefix: str,
                     start_sel: date,
                     end_sel: date,
                     key_suffix: str) -> None:
    st.subheader(title)
    if daily_raw is None or daily_raw.empty:
        st.info("אין דיילי summary למנוע הזה.")
        return

    df = daily_raw.copy()
    df["date"] = pd.to_datetime(df["date"])

    mask = (df["date"].dt.date >= start_sel) & (df["date"].dt.date <= end_sel)
    df = df.loc[mask].copy()
    if df.empty:
        st.info("אין דאטה בטווח תאריכים שנבחר.")
        return

    pnl_col = f"{prefix}_pnl"
    if pnl_col not in df.columns:
        st.info("אין עמודת PnL RAW בקובץ.")
        return

    df[pnl_col] = df[pnl_col].astype(float).fillna(0.0)

    bench_pnl = None
    if bench_equity is not None and not bench_equity.empty:
        be = bench_equity.copy()
        be["date"] = pd.to_datetime(be["date"])
        be = be.sort_values("date").reset_index(drop=True)
        be["bench_pnl"] = be["equity"].astype(float).diff().fillna(0.0)
        bench_pnl = be[["date", "bench_pnl"]]
        df = df.merge(bench_pnl, on="date", how="left")
    else:
        df["bench_pnl"] = np.nan

    df = df.set_index("date")

    choice = st.radio(
        "איזה PnL להציג?",
        options=["Strategy", "Benchmark", "Both"],
        index=2,
        horizontal=True,
        key=f"radio_pnl_{key_suffix}",
    )

    chart_df = pd.DataFrame(index=df.index)
    if choice == "Strategy":
        chart_df["Strategy PnL"] = df[pnl_col]
    elif choice == "Benchmark":
        chart_df["Benchmark PnL"] = df["bench_pnl"]
    else:
        chart_df["Strategy PnL"] = df[pnl_col]
        chart_df["Benchmark PnL"] = df["bench_pnl"]

    st.bar_chart(chart_df, use_container_width=True, height=280)


# ---------------------------------------------------------------------
# UI – טבלאות סיכום
# ---------------------------------------------------------------------

def render_summary_table(title: str,
                         crypto_strat: Optional[pd.DataFrame],
                         us_strat: Optional[pd.DataFrame],
                         start_sel: date,
                         end_sel: date) -> None:
    st.subheader(title)

    rows: List[Dict[str, object]] = []

    for name, df in [("CRYPTO", crypto_strat), ("US", us_strat)]:
        if df is None or df.empty:
            rows.append(compute_summary_row(name, None))
        else:
            mask = (df["date"].dt.date >= start_sel) & (df["date"].dt.date <= end_sel)
            sub = df.loc[mask].copy()
            if sub.empty:
                rows.append(compute_summary_row(name, None))
            else:
                rows.append(compute_summary_row(name, sub))

    summary_df = pd.DataFrame(rows)
    st.dataframe(format_summary_df(summary_df), use_container_width=True)


def render_single_summary(title: str,
                          name: str,
                          df: Optional[pd.DataFrame],
                          start_sel: date,
                          end_sel: date) -> None:
    st.subheader(title)
    if df is None or df.empty:
        st.info("אין דאטה לטווח שנבחר.")
        return
    mask = (df["date"].dt.date >= start_sel) & (df["date"].dt.date <= end_sel)
    sub = df.loc[mask].copy()
    row = compute_summary_row(name, sub if not sub.empty else None)
    summary_df = pd.DataFrame([row])
    st.dataframe(format_summary_df(summary_df), use_container_width=True)


# ---------------------------------------------------------------------
# UI – גרף משולב Crypto+US
# ---------------------------------------------------------------------

def render_combined_equity(crypto_strat: Optional[pd.DataFrame],
                           us_strat: Optional[pd.DataFrame],
                           start_sel: date,
                           end_sel: date) -> None:
    st.subheader("Combined Equity – Crypto & US (Strategy only)")
    if (crypto_strat is None or crypto_strat.empty) and (us_strat is None or us_strat.empty):
        st.info("אין דאטה ל-Crypto או ל-US.")
        return

    series_list = []

    if crypto_strat is not None and not crypto_strat.empty:
        df_c = crypto_strat.copy()
        df_c["date"] = pd.to_datetime(df_c["date"])
        mask = (df_c["date"].dt.date >= start_sel) & (df_c["date"].dt.date <= end_sel)
        df_c = df_c.loc[mask].copy()
        if not df_c.empty:
            first = float(df_c["equity"].iloc[0])
            if first != 0:
                df_c["Crypto"] = df_c["equity"] * (INITIAL_CAPITAL / first)
                df_c = df_c[["date", "Crypto"]]
                series_list.append(df_c)

    if us_strat is not None and not us_strat.empty:
        df_u = us_strat.copy()
        df_u["date"] = pd.to_datetime(df_u["date"])
        mask = (df_u["date"].dt.date >= start_sel) & (df_u["date"].dt.date <= end_sel)
        df_u = df_u.loc[mask].copy()
        if not df_u.empty:
            first = float(df_u["equity"].iloc[0])
            if first != 0:
                df_u["US"] = df_u["equity"] * (INITIAL_CAPITAL / first)
                df_u = df_u[["date", "US"]]
                series_list.append(df_u)

    if not series_list:
        st.info("אין דאטה משני הצדדים בטווח שנבחר.")
        return

    merged = series_list[0]
    for extra in series_list[1:]:
        merged = merged.merge(extra, on="date", how="inner")

    if merged.empty:
        st.info("אין חיתוך תאריכים משותף בין Crypto ל-US.")
        return

    merged = merged.set_index("date")
    choice = st.radio(
        "איזה Strategy להציג?",
        options=["Crypto", "US", "Both"],
        index=2,
        horizontal=True,
        key="radio_combined_equity",
    )

    if choice == "Crypto":
        chart_df = merged[["Crypto"]] if "Crypto" in merged.columns else None
    elif choice == "US":
        chart_df = merged[["US"]] if "US" in merged.columns else None
    else:
        cols = [c for c in ["Crypto", "US"] if c in merged.columns]
        chart_df = merged[cols] if cols else None

    if chart_df is None or chart_df.empty:
        st.info("אין מספיק דאטה להצגה.")
        return

    st.line_chart(chart_df, use_container_width=True, height=320)


# ---------------------------------------------------------------------
# Main App – Paper Trading Dashboard
# ---------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Multi-Asset Paper Dashboard",
        layout="wide",
    )

    st.title("Multi-Asset Paper Trading Dashboard")
    st.caption("Crypto + US Paper Trading 2022–2025 – מוכן למשקיע, בלי בולשיט.")

    # טעינת Equity RAW
    crypto_strat = load_equity_csv(CRYPTO_STRAT_FILE, "Crypto Strategy")
    crypto_bench = load_equity_csv(CRYPTO_BENCH_FILE, "Crypto Benchmark")
    us_strat = load_equity_csv(US_STRAT_FILE, "US Strategy")
    us_bench = load_equity_csv(US_BENCH_FILE, "US Benchmark")

    crypto_merged = align_strategy_benchmark(crypto_strat, crypto_bench)
    us_merged = align_strategy_benchmark(us_strat, us_bench)

    # טעינת דיילי
    crypto_daily_raw = load_daily_raw(CRYPTO_DAILY_FILE, "Crypto Daily RAW")
    crypto_daily_pretty = load_daily_pretty(CRYPTO_DAILY_PRETTY_FILE, "Crypto Daily Pretty")
    us_daily_raw = load_daily_raw(US_DAILY_FILE, "US Daily RAW")
    us_daily_pretty = load_daily_pretty(US_DAILY_PRETTY_FILE, "US Daily Pretty")

    gmin, gmax = get_global_date_range([crypto_strat, us_strat])

    # Sidebar – פילטרים
    with st.sidebar:
        st.header("Filters")
        if "filter_start" not in st.session_state:
            st.session_state["filter_start"] = gmin
        if "filter_end" not in st.session_state:
            st.session_state["filter_end"] = gmax

        start_input = st.date_input("Start date", value=st.session_state["filter_start"],
                                    min_value=gmin, max_value=gmax, key="start_input")
        end_input = st.date_input("End date", value=st.session_state["filter_end"],
                                  min_value=gmin, max_value=gmax, key="end_input")

        if st.button("Apply filters"):
            st.session_state["filter_start"] = start_input
            st.session_state["filter_end"] = end_input

        start_sel = st.session_state["filter_start"]
        end_sel = st.session_state["filter_end"]
        if start_sel > end_sel:
            st.error("Start date חייב להיות לפני End date.")
            return

        st.markdown("---")
        st.header("Sections")
        show_crypto = st.checkbox("Crypto", value=True)
        show_us = st.checkbox("US", value=True)

    tab_overview, tab_crypto, tab_us = st.tabs(["Overview", "Crypto", "US"])

    # Overview – Summary למעלה, גרף משולב, אחר כך גרפים נפרדים
    with tab_overview:
        render_summary_table(
            "Summary tables – Crypto and US (Paper)",
            crypto_strat if show_crypto else None,
            us_strat if show_us else None,
            start_sel,
            end_sel,
        )
        st.markdown("---")

        render_combined_equity(
            crypto_strat if show_crypto else None,
            us_strat if show_us else None,
            start_sel,
            end_sel,
        )

        if show_crypto:
            st.markdown("---")
            render_equity_block(
                "Crypto – Equity (Paper vs BTC)",
                crypto_merged,
                start_sel,
                end_sel,
                key_suffix="overview_crypto",
            )
            render_pnl_block(
                "Crypto – Daily PnL (Strategy vs Benchmark)",
                crypto_daily_raw,
                crypto_bench,
                prefix="crypto",
                start_sel=start_sel,
                end_sel=end_sel,
                key_suffix="overview_crypto_pnl",
            )

        if show_us:
            st.markdown("---")
            render_equity_block(
                "US – Equity (Paper vs Benchmark)",
                us_merged,
                start_sel,
                end_sel,
                key_suffix="overview_us",
            )
            render_pnl_block(
                "US – Daily PnL (Strategy vs Benchmark)",
                us_daily_raw,
                us_bench,
                prefix="us",
                start_sel=start_sel,
                end_sel=end_sel,
                key_suffix="overview_us_pnl",
            )

    # Crypto tab – Summary למעלה
    with tab_crypto:
        if not show_crypto:
            st.info("Crypto כבוי בפילטרים של Sidebar.")
        else:
            render_single_summary(
                "Crypto Summary (Paper)",
                "CRYPTO",
                crypto_strat,
                start_sel,
                end_sel,
            )
            st.markdown("---")
            render_equity_block(
                "Crypto – Equity (Paper vs BTC)",
                crypto_merged,
                start_sel,
                end_sel,
                key_suffix="crypto_tab_eq",
            )
            render_pnl_block(
                "Crypto – Daily PnL (Strategy vs Benchmark)",
                crypto_daily_raw,
                crypto_bench,
                prefix="crypto",
                start_sel=start_sel,
                end_sel=end_sel,
                key_suffix="crypto_tab_pnl",
            )
            st.markdown("---")
            st.subheader("Crypto – Daily table (pretty)")
            if crypto_daily_pretty is not None and not crypto_daily_pretty.empty:
                st.dataframe(crypto_daily_pretty, use_container_width=True, height=300)
            else:
                st.info("No crypto pretty daily file found.")

    # US tab – Summary למעלה
    with tab_us:
        if not show_us:
            st.info("US כבוי בפילטרים של Sidebar.")
        else:
            render_single_summary(
                "US Summary (Paper)",
                "US",
                us_strat,
                start_sel,
                end_sel,
            )
            st.markdown("---")
            render_equity_block(
                "US – Equity (Paper vs Benchmark)",
                us_merged,
                start_sel,
                end_sel,
                key_suffix="us_tab_eq",
            )
            render_pnl_block(
                "US – Daily PnL (Strategy vs Benchmark)",
                us_daily_raw,
                us_bench,
                prefix="us",
                start_sel=start_sel,
                end_sel=end_sel,
                key_suffix="us_tab_pnl",
            )
            st.markdown("---")
            st.subheader("US – Daily table (pretty)")
            if us_daily_pretty is not None and not us_daily_pretty.empty:
                st.dataframe(us_daily_pretty, use_container_width=True, height=300)
            else:
                st.info("No US pretty daily file found.")


if __name__ == "__main__":
    main()
