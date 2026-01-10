#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import date
from typing import Dict, Optional, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# =========================================================
# קונפיגורציה
# =========================================================

RESULTS_DIR = "results_multi"
CRYPTO_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")
IL_FILE = os.path.join(RESULTS_DIR, "il_equity_curve.csv")

INITIAL_CAPITAL = 100000.0

MONTH_NAMES_HE = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]
MONTH_NAMES_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# =========================================================
# תמיכה בשפות – טקסטים לפי language
# =========================================================

def get_texts(language: str) -> Dict[str, str]:
    """מחזיר מילון טקסטים לפי שפה."""
    if language == "HE":
        return {
            "app_title": "Multi-Asset Strategy Dashboard",
            "app_caption": "Backtest 2022–2025, הון התחלתי לניתוח: 100,000$ לכל בוט.",
            "filters_header": "פילטרים",
            "mode_range": "טווח תאריכים חופשי",
            "mode_ym": "שנה/חודש עם חפש",
            "start_date": "תאריך התחלה",
            "end_date": "תאריך סיום",
            "selected_range": "טווח נבחר",
            "search_button": "חפש",
            "summary_intro": (
                "**סיכום:**  \n"
                "לכל בוט מוצגת טבלת ביצועים נפרדת הכוללת Strategy ו-Benchmark בלבד,  \n"
                "יחד עם Opening/Closing/Net P&L על בסיס 100,000$."
            ),
            "crypto_summary_title": "סיכום קריפטו (BTC בלבד)",
            "us_summary_title": "סיכום ארה\"ב (S&P500 בלבד)",
            "il_summary_title": "סיכום ישראל (TA-125 בלבד)",
            "no_backtest_files": "לא נמצאו קבצי backtest בתקייה results_multi. ודא שהרצת את ה-Backtest.",
            "invalid_range": "תאריך התחלה חייב להיות לפני תאריך סיום.",
            "no_data_market": "לא נמצאו נתונים עבור",
            "no_data_range": "אין נתונים בטווח התאריכים הנבחר.",
            "no_equity_chart": "אין עקומת הון להצגה.",
            "mode_label": "מצב בחירת טווח",
            "segment_curve_choice": "בחירת עקומת הון להצגה",
            "metric_total_return": "תשואה כוללת",
            "metric_multiple": "מכפיל",
            "metric_max_dd": "Max DD",
            "metric_sharpe": "Sharpe",
            "strategy_label": "Strategy",
            "benchmark_label": "מדד",
            "footer_caption": (
                "Backtest בלבד. הסכומים הכספיים מחושבים ביחס ל-100,000$ הון התחלתי לכל בוט."
            ),
            "curve_both": "שניהם",
            "crypto_name": "קריפטו",
            "us_name": "ארה\"ב",
            "il_name": "ישראל",
        }
    else:
        return {
            "app_title": "Multi-Asset Strategy Dashboard",
            "app_caption": "Backtest 2022–2025, analysis based on initial capital of $100,000 per bot.",
            "filters_header": "Filters",
            "mode_range": "Free date range",
            "mode_ym": "Year/Month with Search",
            "start_date": "Start date",
            "end_date": "End date",
            "selected_range": "Selected range",
            "search_button": "Search",
            "summary_intro": (
                "**Summary:**  \n"
                "Each bot has its own performance table with Strategy and Benchmark only,  \n"
                "plus Opening/Closing/Net P&L based on $100,000 initial capital."
            ),
            "crypto_summary_title": "Crypto Summary (BTC only)",
            "us_summary_title": "US Summary (S&P500 only)",
            "il_summary_title": "Israel Summary (TA-125 only)",
            "no_backtest_files": "No backtest CSV files found in results_multi. Make sure you ran the backtest script.",
            "invalid_range": "Start date must be before end date.",
            "no_data_market": "No data found for",
            "no_data_range": "No data in selected date range.",
            "no_equity_chart": "No equity curve to display.",
            "mode_label": "Date range mode",
            "segment_curve_choice": "Select equity curve to display",
            "metric_total_return": "Total return",
            "metric_multiple": "Multiple",
            "metric_max_dd": "Max DD",
            "metric_sharpe": "Sharpe",
            "strategy_label": "Strategy",
            "benchmark_label": "Benchmark",
            "footer_caption": (
                "Backtest only. Monetary figures are computed relative to $100,000 initial capital per bot."
            ),
            "curve_both": "Both",
            "crypto_name": "Crypto",
            "us_name": "US",
            "il_name": "Israel",
        }


def get_month_names(language: str) -> List[str]:
    return MONTH_NAMES_HE if language == "HE" else MONTH_NAMES_EN


# =========================================================
# טעינת דאטה
# =========================================================

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
        if "date" in df.columns:
            df = df.sort_values(by="date").reset_index(drop=True)
        return df
    except Exception:
        return None


def filter_by_date_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df is None or df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df.loc[mask].copy()


# =========================================================
# חישובי מדדים
# =========================================================

def compute_window_metrics(equity_df: pd.DataFrame,
                           col_name: str = "equity") -> Dict[str, float]:
    m = {
        "total_return_pct": np.nan,
        "pnl_factor": np.nan,
        "max_drawdown_pct": np.nan,
        "sharpe": np.nan,
    }

    if equity_df is None or equity_df.empty or col_name not in equity_df.columns:
        return m

    eq = equity_df[col_name].astype(float)
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return m

    start_val, end_val = eq.iloc[0], eq.iloc[-1]
    m["total_return_pct"] = float((end_val / start_val - 1.0) * 100.0)
    m["pnl_factor"] = float(end_val / start_val)

    dd_series = (eq / eq.cummax() - 1.0) * 100.0
    m["max_drawdown_pct"] = float(dd_series.min())

    dr = eq.pct_change().dropna()
    if len(dr) > 1 and dr.std() > 0:
        m["sharpe"] = float((dr.mean() / dr.std()) * np.sqrt(252))

    return m


def compute_summary_for_single_market(
    df: Optional[pd.DataFrame],
    start_date: date,
    end_date: date,
    benchmark_label: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    filt = filter_by_date_range(df, start_date, end_date)
    if filt is None or filt.empty:
        return pd.DataFrame()

    sm = compute_window_metrics(filt, "equity")
    if "benchmark_equity" in filt.columns:
        bm = compute_window_metrics(filt, "benchmark_equity")
    else:
        bm = {"total_return_pct": np.nan, "pnl_factor": np.nan, "sharpe": np.nan}

    strat_ret = sm["total_return_pct"]
    bench_ret = bm["total_return_pct"]

    if not np.isnan(strat_ret):
        opening_capital = INITIAL_CAPITAL
        closing_capital = opening_capital * (1.0 + strat_ret / 100.0)
        net_pnl = closing_capital - opening_capital
    else:
        opening_capital = np.nan
        closing_capital = np.nan
        net_pnl = np.nan

    alpha = strat_ret - bench_ret if not np.isnan(strat_ret) and not np.isnan(bench_ret) else np.nan

    row = {
        "Strategy תשואה": strat_ret,
        f"{benchmark_label} תשואה": bench_ret,
        "Strategy מכפיל": sm["pnl_factor"],
        f"{benchmark_label} מכפיל": bm["pnl_factor"],
        "Strategy Sharpe": sm["sharpe"],
        "Alpha": alpha,
        "Opening Capital": opening_capital,
        "Closing Capital": closing_capital,
        "Net P&L": net_pnl,
    }

    return pd.DataFrame([row])


# =========================================================
# UI – מטריקות וגרפים
# =========================================================

def render_colored_metric(label: str, value: str, color: str) -> None:
    html = f"""
    <div style="text-align:center;">
      <div style="font-size:14px; color:#888;">{label}</div>
      <div style="font-size:28px; font-weight:bold; color:{color};">{value}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_segment_block(name: str,
                         df: Optional[pd.DataFrame],
                         start_date: date,
                         end_date: date,
                         benchmark_label: str,
                         texts: Dict[str, str]) -> None:
    st.subheader(name)

    if df is None or df.empty:
        st.warning(f"{texts['no_data_market']} {name}.")
        return

    filt = filter_by_date_range(df, start_date, end_date)
    if filt is None or filt.empty:
        st.warning(texts["no_data_range"])
        return

    cmode = st.radio(
        texts["segment_curve_choice"],
        options=[texts["strategy_label"], benchmark_label, texts["curve_both"]],
        index=2,
        key=f"curve_mode_{name}",
        horizontal=True,
    )

    sm = compute_window_metrics(filt, "equity")
    bm = compute_window_metrics(filt, "benchmark_equity") if "benchmark_equity" in filt.columns else {
        "total_return_pct": np.nan,
        "pnl_factor": np.nan,
        "max_drawdown_pct": np.nan,
        "sharpe": np.nan,
    }

    st.markdown(f"**{texts['strategy_label']}**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        val = f"{sm['total_return_pct']:.1f}%" if not np.isnan(sm["total_return_pct"]) else "NA"
        render_colored_metric(texts["metric_total_return"], val, "#1f77b4")
    with c2:
        val = f"{sm['pnl_factor']:.2f}x" if not np.isnan(sm["pnl_factor"]) else "NA"
        render_colored_metric(texts["metric_multiple"], val, "#1f77b4")
    with c3:
        val = f"{sm['max_drawdown_pct']:.1f}%" if not np.isnan(sm["max_drawdown_pct"]) else "NA"
        render_colored_metric(texts["metric_max_dd"], val, "#1f77b4")
    with c4:
        val = f"{sm['sharpe']:.2f}" if not np.isnan(sm["sharpe"]) else "NA"
        render_colored_metric(texts["metric_sharpe"], val, "#1f77b4")

    st.markdown(f"**{benchmark_label}**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        val = f"{bm['total_return_pct']:.1f}%" if not np.isnan(bm["total_return_pct"]) else "NA"
        render_colored_metric(texts["metric_total_return"], val, "#17becf")
    with c2:
        val = f"{bm['pnl_factor']:.2f}x" if not np.isnan(bm["pnl_factor"]) else "NA"
        render_colored_metric(texts["metric_multiple"], val, "#17becf")
    with c3:
        val = f"{bm['max_drawdown_pct']:.1f}%" if not np.isnan(bm["max_drawdown_pct"]) else "NA"
        render_colored_metric(texts["metric_max_dd"], val, "#17becf")
    with c4:
        val = f"{bm['sharpe']:.2f}" if not np.isnan(bm["sharpe"]) else "NA"
        render_colored_metric(texts["metric_sharpe"], val, "#17becf")

    st.markdown("---")

    chart_df = pd.DataFrame()
    if "equity" in filt.columns:
        chart_df[texts["strategy_label"]] = filt.set_index("date")["equity"]
    if "benchmark_equity" in filt.columns:
        chart_df[benchmark_label] = filt.set_index("date")["benchmark_equity"]

    if chart_df.empty:
        st.warning(texts["no_equity_chart"])
        return

    chart_df = chart_df.ffill()

    if cmode == texts["strategy_label"]:
        chart_df = chart_df[[texts["strategy_label"]]]
    elif cmode == benchmark_label:
        if benchmark_label in chart_df.columns:
            chart_df = chart_df[[benchmark_label]]
        else:
            chart_df = pd.DataFrame()

    if not chart_df.empty:
        st.line_chart(chart_df, height=350)


# =========================================================
# לוגיקת בחירת טווח תאריכים
# =========================================================

def get_global_date_bounds(dfs: List[Optional[pd.DataFrame]]) -> Tuple[date, date]:
    all_dates: List[pd.Series] = []
    for df in dfs:
        if df is not None and not df.empty and "date" in df.columns:
            all_dates.append(df["date"])
    if all_dates:
        mins = min(s.min() for s in all_dates)
        maxs = max(s.max() for s in all_dates)
        return mins.date(), maxs.date()
    today = date.today()
    return date(today.year - 1, today.month, today.day), today


def build_date_range_range_mode(
    global_min: date,
    global_max: date,
    texts: Dict[str, str],
) -> Tuple[date, date]:
    start_date_sel = st.sidebar.date_input(
        texts["start_date"],
        value=global_min,
        min_value=global_min,
        max_value=global_max,
        key="start_date_range",
    )
    end_date_sel = st.sidebar.date_input(
        texts["end_date"],
        value=global_max,
        min_value=global_min,
        max_value=global_max,
        key="end_date_range",
    )
    return start_date_sel, end_date_sel


def build_date_range_ym_mode(
    global_min: date,
    global_max: date,
    texts: Dict[str, str],
    language: str,
) -> Tuple[date, date]:
    years = list(range(global_min.year, global_max.year + 1))
    months = list(range(1, 13))
    month_names = get_month_names(language)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_year = st.selectbox("שנת פתיחה" if language == "HE" else "Start year",
                                  options=years, index=0, key="start_year")
        start_month = st.selectbox(
            "חודש פתיחה" if language == "HE" else "Start month",
            options=months,
            index=0,
            format_func=lambda m: month_names[m - 1],
            key="start_month",
        )
    with col2:
        end_year = st.selectbox("שנת סגירה" if language == "HE" else "End year",
                                options=years, index=len(years) - 1, key="end_year")
        end_month = st.selectbox(
            "חודש סגירה" if language == "HE" else "End month",
            options=months,
            index=11,
            format_func=lambda m: month_names[m - 1],
            key="end_month",
        )

    if "custom_range" not in st.session_state:
        st.session_state["custom_range"] = (global_min, global_max)

    if st.sidebar.button(texts["search_button"], type="primary"):
        start_dt = date(start_year, start_month, 1)
        end_dt = date(end_year, end_month, 28)
        st.session_state["custom_range"] = (start_dt, end_dt)

    return st.session_state["custom_range"]


# =========================================================
# main / entry point
# =========================================================

def main() -> None:
    st.set_page_config(page_title="Multi-Asset Strategy Dashboard", layout="wide")

    # בורר שפה בראש העמוד
    language = st.selectbox(
        "Language / שפה",
        options=["EN", "HE"],
        index=0,
        key="language_selector",
    )
    texts = get_texts(language)

    st.title(texts["app_title"])
    st.caption(texts["app_caption"])

    # טעינת דאטה
    crypto_df = load_csv_with_date(CRYPTO_FILE)
    us_df = load_csv_with_date(US_FILE)
    il_df = load_csv_with_date(IL_FILE)

    if (crypto_df is None or crypto_df.empty) and \
       (us_df is None or us_df.empty) and \
       (il_df is None or il_df.empty):
        st.error(texts["no_backtest_files"])
        return

    global_min, global_max = get_global_date_bounds([crypto_df, us_df, il_df])

    # Sidebar – בחירת טווח
    st.sidebar.header(texts["filters_header"])

    mode = st.sidebar.radio(
        texts["mode_label"],
        options=[texts["mode_range"], texts["mode_ym"]],
        index=0,
        key="range_mode",
    )

    if mode == texts["mode_range"]:
        start_date_sel, end_date_sel = build_date_range_range_mode(
            global_min, global_max, texts
        )
    else:
        start_date_sel, end_date_sel = build_date_range_ym_mode(
            global_min, global_max, texts, language
        )

    if start_date_sel > end_date_sel:
        st.sidebar.error(texts["invalid_range"])
        return

    st.sidebar.markdown("---")
    st.sidebar.write(f"{texts['selected_range']}: {start_date_sel} → {end_date_sel}")

    st.markdown(texts["summary_intro"])

    # 3 טבלאות – אחת לכל בוט
    crypto_summary = compute_summary_for_single_market(
        crypto_df, start_date_sel, end_date_sel, "BTC"
    )
    us_summary = compute_summary_for_single_market(
        us_df, start_date_sel, end_date_sel, "S&P500"
    )
    il_summary = compute_summary_for_single_market(
        il_df, start_date_sel, end_date_sel, "TA-125"
    )

    def format_summary(df: pd.DataFrame, benchmark_label: str) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        for col in ["Strategy תשואה", f"{benchmark_label} תשואה", "Alpha"]:
            if col in out.columns:
                out[col] = out[col].apply(
                    lambda x: f"{x:.1f}%" if pd.notna(x) and not np.isnan(x) else ""
                )
        for col in ["Strategy מכפיל", f"{benchmark_label} מכפיל"]:
            if col in out.columns:
                out[col] = out[col].apply(
                    lambda x: f"{x:.2f}x" if pd.notna(x) and not np.isnan(x) else ""
                )
        if "Strategy Sharpe" in out.columns:
            out["Strategy Sharpe"] = out["Strategy Sharpe"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) and not np.isnan(x) else ""
            )
        for col in ["Opening Capital", "Closing Capital", "Net P&L"]:
            if col in out.columns:
                out[col] = out[col].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) and not np.isnan(x) else ""
                )
        return out

    if not crypto_summary.empty:
        st.subheader(texts["crypto_summary_title"])
        st.dataframe(format_summary(crypto_summary, "BTC"), use_container_width=True)

    if not us_summary.empty:
        st.subheader(texts["us_summary_title"])
        st.dataframe(format_summary(us_summary, "S&P500"), use_container_width=True)

    if not il_summary.empty:
        st.subheader(texts["il_summary_title"])
        st.dataframe(format_summary(il_summary, "TA-125"), use_container_width=True)

    st.markdown("---")

    # בלוקים לגרפים
    if crypto_df is not None and not crypto_df.empty:
        render_segment_block(
            texts["crypto_name"], crypto_df, start_date_sel, end_date_sel, "BTC", texts
        )

    if us_df is not None and not us_df.empty:
        render_segment_block(
            texts["us_name"], us_df, start_date_sel, end_date_sel, "S&P500", texts
        )

    if il_df is not None and not il_df.empty:
        render_segment_block(
            texts["il_name"], il_df, start_date_sel, end_date_sel, "TA-125", texts
        )

    st.markdown("---")
    st.caption(texts["footer_caption"])


if __name__ == "__main__":
    main()
