import os
import sys
import pandas as pd
import numpy as np

US_TRADES_FILE = "us_trades.csv"
US_DAILY_FILE = "us_daily_summary_pretty.csv"
US_EQUITY_FILE = "us_paper_equity.csv"

US_EQUITY_TRIMMED_FILE = "us_equity_curve_trimmed.csv"
US_INVESTOR_FILE = "us_investor_summary.csv"
US_COMPARISON_ROW_FILE = "us_comparison_row.csv"


def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)


def load_us_data():
    ensure_file(US_TRADES_FILE)
    ensure_file(US_DAILY_FILE)
    ensure_file(US_EQUITY_FILE)

    trades = pd.read_csv(US_TRADES_FILE)
    daily = pd.read_csv(US_DAILY_FILE)
    equity = pd.read_csv(US_EQUITY_FILE)

    for df, col in [(trades, "date"), (daily, "date"), (equity, "date")]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    return trades, daily, equity


def clean_dollar_column(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace("", np.nan)
        .astype(float)
    )


def parse_us_daily_equity(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.copy()
    required_cols = ["us_total", "us_benchmark"]
    for col in required_cols:
        if col not in daily.columns:
            print(f"⚠️ חסרה עמודה בקובץ היומי: {col}")
            print(f"עמודות קיימות: {list(daily.columns)}")
            sys.exit(1)

    daily["us_total_clean"] = clean_dollar_column(daily["us_total"])
    daily["us_benchmark_clean"] = clean_dollar_column(daily["us_benchmark"])

    if daily["us_total_clean"].isna().all():
        print("⚠️ אחרי ניקוי, כל ערכי us_total_clean הם NaN – בדוק פורמט.")
        print(daily[["us_total"]].head())
        sys.exit(1)

    daily["equity"] = daily["us_total_clean"]
    daily["benchmark_equity"] = daily["us_benchmark_clean"]
    return daily


def build_full_equity(equity: pd.DataFrame) -> pd.DataFrame:
    equity = equity.copy().sort_values("date").reset_index(drop=True)
    if equity.empty:
        print("⚠️ us_paper_equity.csv ריק אחרי סידור תאריכים.")
        sys.exit(1)

    equity.to_csv(US_EQUITY_TRIMMED_FILE, index=False)
    print(f"✅ נשמר קובץ עקומת הון (מלא) ל-{US_EQUITY_TRIMMED_FILE}")
    print(
        f"מספר נקודות בעקומה: {len(equity)} | טווח תאריכים: "
        f"{equity['date'].min()} -> {equity['date'].max()}"
    )
    return equity


def compute_us_investor_summary(trades: pd.DataFrame,
                                daily_raw: pd.DataFrame,
                                full_equity: pd.DataFrame) -> pd.DataFrame:
    stats = {}

    full_equity = full_equity.sort_values("date").reset_index(drop=True)

    # טווח כולל (Backtest מלא)
    stats["start_date"] = full_equity["date"].min()
    stats["end_date"] = full_equity["date"].max()

    # הון כולל – מהעמודה equity
    start_eq = float(full_equity["equity"].iloc[0])
    end_eq = float(full_equity["equity"].iloc[-1])
    stats["start_equity"] = start_eq
    stats["end_equity"] = end_eq
    stats["total_return_pct"] = (end_eq / start_eq - 1.0) * 100.0 if start_eq != 0 else np.nan

    # בנצ'מרק כולל מתוך us_paper_equity.csv (benchmark_equity)
    if "benchmark_equity" in full_equity.columns:
        # לוודא שאין NaN בשורה האחרונה – אם כן, לקחת את הערך האחרון שלא NaN
        b_series = full_equity["benchmark_equity"].dropna()
        if b_series.empty:
            stats["benchmark_start"] = np.nan
            stats["benchmark_end"] = np.nan
            stats["benchmark_total_return_pct"] = np.nan
        else:
            b_start = float(b_series.iloc[0])
            b_end = float(b_series.iloc[-1])
            stats["benchmark_start"] = b_start
            stats["benchmark_end"] = b_end
            stats["benchmark_total_return_pct"] = (
                (b_end / b_start - 1.0) * 100.0 if b_start != 0 else np.nan
            )
    else:
        stats["benchmark_start"] = np.nan
        stats["benchmark_end"] = np.nan
        stats["benchmark_total_return_pct"] = np.nan

    # Drawdown – אסטרטגיה ובנצ׳מרק מתוך היומי
    daily = parse_us_daily_equity(daily_raw)
    daily = daily.sort_values("date").reset_index(drop=True)

    daily["equity_cum_max"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / daily["equity_cum_max"] - 1.0
    stats["max_drawdown_pct"] = float(daily["drawdown"].min() * 100.0)
    dd_idx = daily["drawdown"].idxmin()
    stats["max_dd_date"] = daily.loc[dd_idx, "date"]
    stats["max_dd_equity"] = float(daily.loc[dd_idx, "equity"])

    daily["bench_cum_max"] = daily["benchmark_equity"].cummax()
    daily["bench_drawdown"] = daily["benchmark_equity"] / daily["bench_cum_max"] - 1.0
    stats["benchmark_max_drawdown_pct"] = float(daily["bench_drawdown"].min() * 100.0)

    # תקופת Deployment – מ-2024-01-02
    deploy_start = pd.Timestamp("2024-01-02")
    deploy_eq = full_equity[full_equity["date"] >= deploy_start].copy()
    if not deploy_eq.empty:
        d_s = float(deploy_eq["equity"].iloc[0])
        d_e = float(deploy_eq["equity"].iloc[-1])
        stats["deploy_start_date"] = deploy_eq["date"].iloc[0]
        stats["deploy_end_date"] = deploy_eq["date"].iloc[-1]
        stats["deploy_start_equity"] = d_s
        stats["deploy_end_equity"] = d_e
        stats["deploy_return_pct"] = (d_e / d_s - 1.0) * 100.0 if d_s != 0 else np.nan

        if "benchmark_equity" in deploy_eq.columns:
            deploy_b_series = deploy_eq["benchmark_equity"].dropna()
            if deploy_b_series.empty:
                stats["deploy_benchmark_start"] = np.nan
                stats["deploy_benchmark_end"] = np.nan
                stats["deploy_benchmark_return_pct"] = np.nan
            else:
                db_s = float(deploy_b_series.iloc[0])
                db_e = float(deploy_b_series.iloc[-1])
                stats["deploy_benchmark_start"] = db_s
                stats["deploy_benchmark_end"] = db_e
                stats["deploy_benchmark_return_pct"] = (
                    (db_e / db_s - 1.0) * 100.0 if db_s != 0 else np.nan
                )
        else:
            stats["deploy_benchmark_start"] = np.nan
            stats["deploy_benchmark_end"] = np.nan
            stats["deploy_benchmark_return_pct"] = np.nan
    else:
        stats["deploy_start_date"] = pd.NaT
        stats["deploy_end_date"] = pd.NaT
        stats["deploy_start_equity"] = np.nan
        stats["deploy_end_equity"] = np.nan
        stats["deploy_return_pct"] = np.nan
        stats["deploy_benchmark_start"] = np.nan
        stats["deploy_benchmark_end"] = np.nan
        stats["deploy_benchmark_return_pct"] = np.nan

    # סטטיסטיקות טריידים – כל התקופה
    trades = trades.copy()
    if "pnl" not in trades.columns:
        print("⚠️ בעיית דאטה: חסרה עמודת pnl ב-us_trades.csv")
        sys.exit(1)

    valid_trades = trades.dropna(subset=["pnl"])
    wins = valid_trades[valid_trades["pnl"] > 0]
    losses = valid_trades[valid_trades["pnl"] < 0]

    stats["num_trades"] = int(len(valid_trades))
    stats["num_wins"] = int(len(wins))
    stats["num_losses"] = int(len(losses))
    stats["win_rate_pct"] = (
        float(len(wins) / len(valid_trades) * 100.0) if len(valid_trades) > 0 else 0.0
    )
    stats["avg_win"] = float(wins["pnl"].mean()) if len(wins) > 0 else 0.0
    stats["avg_loss"] = float(losses["pnl"].mean()) if len(losses) > 0 else 0.0
    stats["total_pnl"] = float(valid_trades["pnl"].sum())

    stats_df = pd.DataFrame([stats])

    cols_order = [
        "start_date",
        "end_date",
        "start_equity",
        "end_equity",
        "total_return_pct",
        "benchmark_start",
        "benchmark_end",
        "benchmark_total_return_pct",
        "max_drawdown_pct",
        "benchmark_max_drawdown_pct",
        "max_dd_date",
        "max_dd_equity",
        "deploy_start_date",
        "deploy_end_date",
        "deploy_start_equity",
        "deploy_end_equity",
        "deploy_return_pct",
        "deploy_benchmark_start",
        "deploy_benchmark_end",
        "deploy_benchmark_return_pct",
        "num_trades",
        "num_wins",
        "num_losses",
        "win_rate_pct",
        "avg_win",
        "avg_loss",
        "total_pnl",
    ]

    stats_df = stats_df[cols_order]
    stats_df.to_csv(US_INVESTOR_FILE, index=False)
    print(f"✅ נשמר קובץ סיכום למשקיעים: {US_INVESTOR_FILE}")
    print(stats_df.T)
    return stats_df


def build_us_comparison_row(investor_df: pd.DataFrame) -> pd.DataFrame:
    df = investor_df.copy()
    df["asset_class"] = "US"
    df["strategy_name"] = "US MeanReversion / ORB"
    df["env"] = "Paper"

    cols_order = [
        "asset_class",
        "strategy_name",
        "env",
        "start_date",
        "end_date",
        "start_equity",
        "end_equity",
        "total_return_pct",
        "benchmark_total_return_pct",
        "max_drawdown_pct",
        "benchmark_max_drawdown_pct",
        "deploy_start_date",
        "deploy_end_date",
        "deploy_start_equity",
        "deploy_end_equity",
        "deploy_return_pct",
        "deploy_benchmark_return_pct",
        "num_trades",
        "win_rate_pct",
        "avg_win",
        "avg_loss",
        "total_pnl",
    ]

    row = df[cols_order].copy()
    row.to_csv(US_COMPARISON_ROW_FILE, index=False)
    print(f"✅ נשמר קובץ שורה ל-comparison: {US_COMPARISON_ROW_FILE}")
    print(row.T)
    return row


def main():
    trades, daily, equity = load_us_data()
    full_equity = build_full_equity(equity)
    investor_df = compute_us_investor_summary(trades, daily, full_equity)
    build_us_comparison_row(investor_df)


if __name__ == "__main__":
    main()
