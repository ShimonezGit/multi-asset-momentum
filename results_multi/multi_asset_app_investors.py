# coding: utf-8

import os
from datetime import date
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st

# -------------------------------------------------------
# קונפיגורציה בסיסית – מיקומי קבצים ושמות
# -------------------------------------------------------

RESULTS_DIR = "results_multi"

# קבצי אסטרטגיה (paper)
CRYPTO_STRAT_FILE = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_STRAT_FILE = os.path.join(RESULTS_DIR, "us_paper_equity.csv")
MULTI_ADAPTIVE_FILE = os.path.join(RESULTS_DIR, "multi_adaptive_paper_equity.csv")

# קבצי בנצ'מרק (Buy & Hold)
CRYPTO_BENCH_FILE = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_BENCH_FILE = os.path.join(RESULTS_DIR, "us_equity_curve.csv")

# ההון ההתחלתי לנרמול התצוגה
INITIAL_CAPITAL = 100000.0


# -------------------------------------------------------
# פונקציות עזר – טעינת קובצי equity
# -------------------------------------------------------

def load_equity_csv(path: str) -> Optional[pd.DataFrame]:
    """
    טוען קובץ equity בפורמט:
    date,equity

    מחזיר DataFrame עם date כ־datetime ו‑equity כ־float.
    אם הקובץ לא קיים או בפורמט שגוי – מחזיר None.
    """
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
    """
    מחזיר DataFrame עם:
    date, Strategy_raw, Benchmark_raw
    על בסיס inner join בין אסטרטגיה לבנצ'מרק לפי תאריך.
    """
    if strat_df is None or strat_df.empty:
        return None

    df = strat_df[["date", "equity"]].rename(columns={"equity": "Strategy_raw"})

    if bench_df is not None and not bench_df.empty:
        b = bench_df[["date", "equity"]].rename(columns={"equity": "Benchmark_raw"})
        df = df.merge(b, on="date", how="inner")

    return df


def get_global_range(dfs: List[Optional[pd.DataFrame]]) -> Tuple[date, date]:
    """
    מחזיר את תאריך ההתחלה והמקסימום הגלובלי בין כל ה‑DF שקיבל.
    אם אין כלום – מחזיר היום.
    """
    dates: List[pd.Timestamp] = []
    for df in dfs:
        if df is not None and not df.empty:
            dates.append(df["date"].min())
            dates.append(df["date"].max())

    if not dates:
        today = date.today()
        return today, today

    return min(dates).date(), max(dates).date()


def compute_metrics_from_series(equity_raw: pd.Series) -> Dict[str, float]:
    """
    מחשב מדדים בסיסיים מסדרת equity:
    - total_return (%)
    - multiple (x)
    - max_dd (%)
    - Sharpe (שנתי, 252 ימים)
    """
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


def normalize_series(equity_raw: pd.Series) -> pd.Series:
    """
    מנרמל equity כך שהערך הראשון יהיה INITIAL_CAPITAL.
    """
    eq = equity_raw.astype(float)
    start_val = float(eq.iloc[0])
    if start_val == 0:
        return eq
    factor = INITIAL_CAPITAL / start_val
    return eq * factor


# -------------------------------------------------------
# אפליקציית Streamlit
# -------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Multi-Asset Investor Dashboard", layout="wide")

    # טעינת קבצים
    crypto_strat = load_equity_csv(CRYPTO_STRAT_FILE)
    us_strat = load_equity_csv(US_STRAT_FILE)
    multi_adapt = load_equity_csv(MULTI_ADAPTIVE_FILE)

    crypto_bench = load_equity_csv(CRYPTO_BENCH_FILE)
    us_bench = load_equity_csv(US_BENCH_FILE)

    # חיבור אסטרטגיה + בנצ'מרק לניתוח
    crypto_merge = align_raw(crypto_strat, crypto_bench)
    us_merge = align_raw(us_strat, us_bench)

    # טווח תאריכים גלובלי לכל מה שיש
    gmin, gmax = get_global_range([crypto_merge, us_merge, multi_adapt])

    st.title("Paper Trading – Investor View")
    st.caption(
        "Crypto Strategy, US Strategy, Multi-Adaptive (Crypto+US). "
        "All results are from systematic paper trading on 5-minute bars."
    )

    st.write(f"Full backtest range (data loaded): {gmin} → {gmax}")
    st.markdown("---")

    # ---------------------------------------------------
    # טאב 1 – Overview (מדדים מספריים)
    # ---------------------------------------------------
    tab_overview, tab_equity, tab_details = st.tabs(
        ["Overview", "Equity Curves", "Details"]
    )

    with tab_overview:
        st.subheader("High-Level Metrics")

        rows = []

        # Crypto + BTC benchmark
        if crypto_merge is not None and not crypto_merge.empty:
            m_strat = compute_metrics_from_series(crypto_merge["Strategy_raw"])
            m_bench = compute_metrics_from_series(crypto_merge["Benchmark_raw"])

            rows.append(
                {
                    "Segment": "Crypto Strategy",
                    "Type": "Strategy",
                    "Total Return %": m_strat["total_return"],
                    "Multiple (x)": m_strat["multiple"],
                    "Max DD %": m_strat["max_dd"],
                    "Sharpe": m_strat["sharpe"],
                }
            )
            rows.append(
                {
                    "Segment": "Crypto Strategy",
                    "Type": "BTC benchmark",
                    "Total Return %": m_bench["total_return"],
                    "Multiple (x)": m_bench["multiple"],
                    "Max DD %": m_bench["max_dd"],
                    "Sharpe": m_bench["sharpe"],
                }
            )

        # US + US benchmark
        if us_merge is not None and not us_merge.empty:
            m_strat = compute_metrics_from_series(us_merge["Strategy_raw"])
            m_bench = compute_metrics_from_series(us_merge["Benchmark_raw"])

            rows.append(
                {
                    "Segment": "US Strategy",
                    "Type": "Strategy",
                    "Total Return %": m_strat["total_return"],
                    "Multiple (x)": m_strat["multiple"],
                    "Max DD %": m_strat["max_dd"],
                    "Sharpe": m_strat["sharpe"],
                }
            )
            rows.append(
                {
                    "Segment": "US Strategy",
                    "Type": "US benchmark",
                    "Total Return %": m_bench["total_return"],
                    "Multiple (x)": m_bench["multiple"],
                    "Max DD %": m_bench["max_dd"],
                    "Sharpe": m_bench["sharpe"],
                }
            )

        # Multi-Adaptive
        if multi_adapt is not None and not multi_adapt.empty:
            m_multi = compute_metrics_from_series(multi_adapt["equity"])
            rows.append(
                {
                    "Segment": "Multi-Adaptive (Crypto+US)",
                    "Type": "Portfolio",
                    "Total Return %": m_multi["total_return"],
                    "Multiple (x)": m_multi["multiple"],
                    "Max DD %": m_multi["max_dd"],
                    "Sharpe": m_multi["sharpe"],
                }
            )

        if rows:
            overview_df = pd.DataFrame(rows)
            styled = overview_df.style.format(
                {
                    "Total Return %": "{:.1f}",
                    "Multiple (x)": "{:.2f}",
                    "Max DD %": "{:.1f}",
                    "Sharpe": "{:.2f}",
                }
            )
            st.dataframe(styled, use_container_width=True)
        else:
            st.warning("No data loaded for any strategy.")

        st.markdown("---")
        st.markdown(
            "קריפטו אמור להכות את ביטקוין, "
            "US אמורה להכות את המדד, "
            "והתיק המולטי‑אדפטיב מחבר ביניהם ל‑Portfolio אחד."
        )

    # ---------------------------------------------------
    # טאב 2 – גרפי Equity מנורמלים
    # ---------------------------------------------------
    with tab_equity:
        st.subheader("Equity Curves – Normalized to 100,000")

        merged_for_plot = pd.DataFrame()

        # ציר X – נבחר את הראשון שקיים
        if crypto_strat is not None and not crypto_strat.empty:
            merged_for_plot["date"] = crypto_strat["date"]
        elif us_strat is not None and not us_strat.empty:
            merged_for_plot["date"] = us_strat["date"]
        elif multi_adapt is not None and not multi_adapt.empty:
            merged_for_plot["date"] = multi_adapt["date"]

        if merged_for_plot.empty:
            st.info("No equity data to plot.")
        else:
            # Crypto Strategy
            if crypto_strat is not None and not crypto_strat.empty:
                crypto_norm = normalize_series(crypto_strat["equity"])
                merged_for_plot = merged_for_plot.merge(
                    pd.DataFrame(
                        {"date": crypto_strat["date"], "Crypto Strategy": crypto_norm}
                    ),
                    on="date",
                    how="left",
                )

            # BTC benchmark
            if crypto_bench is not None and not crypto_bench.empty:
                bench_norm = normalize_series(crypto_bench["equity"])
                merged_for_plot = merged_for_plot.merge(
                    pd.DataFrame(
                        {"date": crypto_bench["date"], "BTC benchmark": bench_norm}
                    ),
                    on="date",
                    how="left",
                )

            # US Strategy
            if us_strat is not None and not us_strat.empty:
                us_norm = normalize_series(us_strat["equity"])
                merged_for_plot = merged_for_plot.merge(
                    pd.DataFrame(
                        {"date": us_strat["date"], "US Strategy": us_norm}
                    ),
                    on="date",
                    how="left",
                )

            # US benchmark
            if us_bench is not None and not us_bench.empty:
                us_bench_norm = normalize_series(us_bench["equity"])
                merged_for_plot = merged_for_plot.merge(
                    pd.DataFrame(
                        {"date": us_bench["date"], "US benchmark": us_bench_norm}
                    ),
                    on="date",
                    how="left",
                )

            # Multi-Adaptive
            if multi_adapt is not None and not multi_adapt.empty:
                multi_norm = normalize_series(multi_adapt["equity"])
                merged_for_plot = merged_for_plot.merge(
                    pd.DataFrame(
                        {"date": multi_adapt["date"], "Multi-Adaptive": multi_norm}
                    ),
                    on="date",
                    how="left",
                )

            merged_for_plot = merged_for_plot.sort_values("date").set_index("date")
            st.line_chart(merged_for_plot, use_container_width=True, height=380)

    # ---------------------------------------------------
    # טאב 3 – טבלאות raw
    # ---------------------------------------------------
    with tab_details:
        st.subheader("Raw Equity Data")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Crypto Strategy – Paper Equity")
            if crypto_strat is not None and not crypto_strat.empty:
                st.dataframe(crypto_strat, use_container_width=True, height=220)
            else:
                st.info("No crypto strategy equity file.")

            st.markdown("#### US Strategy – Paper Equity")
            if us_strat is not None and not us_strat.empty:
                st.dataframe(us_strat, use_container_width=True, height=220)
            else:
                st.info("No US strategy equity file.")

        with col2:
            st.markdown("#### BTC Benchmark – Buy & Hold")
            if crypto_bench is not None and not crypto_bench.empty:
                st.dataframe(crypto_bench, use_container_width=True, height=220)
            else:
                st.info("No BTC benchmark equity file.")

            st.markdown("#### US Benchmark – Buy & Hold")
            if us_bench is not None and not us_bench.empty:
                st.dataframe(us_bench, use_container_width=True, height=220)
            else:
                st.info("No US benchmark equity file.")

            st.markdown("#### Multi-Adaptive Portfolio – Equity")
            if multi_adapt is not None and not multi_adapt.empty:
                st.dataframe(multi_adapt, use_container_width=True, height=220)
            else:
                st.info("No multi-adaptive equity file.")


if __name__ == "__main__":
    main()
