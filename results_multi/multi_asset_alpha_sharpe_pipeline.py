import os
import sys
import pandas as pd
import numpy as np

US_DAILY_FILE = "us_daily_summary_pretty.csv"
US_EQUITY_FILE = "us_paper_equity.csv"
CRYPTO_DAILY_FILE = "crypto_daily_summary_pretty.csv"
CRYPTO_EQUITY_FILE = "crypto_paper_equity.csv"
IL_EQUITY_FILE = "il_paper_equity.csv"
MULTI_SUMMARY_FILE = "multi_asset_summary.csv"

US_INVESTOR_FILE = "us_investor_summary.csv"
CRYPTO_INVESTOR_FILE = "crypto_investor_summary.csv"
IL_INVESTOR_FILE = "il_investor_summary.csv"
MULTI_SUMMARY_EXTENDED_FILE = "multi_asset_summary_extended.csv"


def ensure_file(path: str):
    if not os.path.isfile(path):
        print(f"⚠️ קובץ לא נמצא: {path}")
        sys.exit(1)


def clean_dollar_column(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace("", np.nan)
        .astype(float)
    )


def compute_daily_returns_from_dollar_cols(df: pd.DataFrame,
                                           total_col: str,
                                           bench_col: str) -> pd.DataFrame:
    out = df.copy()
    out[total_col + "_clean"] = clean_dollar_column(out[total_col])
    out[bench_col + "_clean"] = clean_dollar_column(out[bench_col])
    out = out.sort_values("date").reset_index(drop=True)
    out["strategy_ret"] = out[total_col + "_clean"].pct_change()
    out["benchmark_ret"] = out[bench_col + "_clean"].pct_change()
    out = out.dropna(subset=["strategy_ret", "benchmark_ret"])
    return out[["date", "strategy_ret", "benchmark_ret"]]


def compute_alpha_sharpe(daily_ret: pd.DataFrame,
                         start_date: pd.Timestamp,
                         end_date: pd.Timestamp,
                         periods_per_year: int = 252) -> dict:
    window = daily_ret[(daily_ret["date"] >= start_date) & (daily_ret["date"] <= end_date)].copy()
    if window.empty:
        return {"alpha_pct": np.nan, "sharpe": np.nan}

    strategy = window["strategy_ret"].values
    benchmark = window["benchmark_ret"].values
    excess = strategy - benchmark

    mean_excess = np.nanmean(excess)
    std_excess = np.nanstd(excess, ddof=1)
    alpha_annual = mean_excess * periods_per_year
    alpha_pct = alpha_annual * 100.0 if not np.isnan(alpha_annual) else np.nan

    mean_strategy = np.nanmean(strategy)
    std_strategy = np.nanstd(strategy, ddof=1)
    sharpe = (
        mean_strategy / std_strategy * np.sqrt(periods_per_year)
        if std_strategy not in (0, np.nan)
        else np.nan
    )

    return {
        "alpha_pct": float(alpha_pct) if not np.isnan(alpha_pct) else np.nan,
        "sharpe": float(sharpe) if not np.isnan(sharpe) else np.nan,
    }


def load_us_investor_summary() -> pd.DataFrame:
    ensure_file(US_INVESTOR_FILE)
    df = pd.read_csv(
        US_INVESTOR_FILE,
        parse_dates=["start_date", "end_date", "deploy_start_date", "deploy_end_date"],
    )
    return df


def compute_us_alpha_sharpe():
    ensure_file(US_DAILY_FILE)
    ensure_file(US_EQUITY_FILE)

    us_daily = pd.read_csv(US_DAILY_FILE)
    us_daily["date"] = pd.to_datetime(us_daily["date"], errors="coerce")
    us_ret = compute_daily_returns_from_dollar_cols(
        us_daily, total_col="us_total", bench_col="us_benchmark"
    )

    us_inv = load_us_investor_summary()
    start_date = us_inv["start_date"].iloc[0]
    end_date = us_inv["end_date"].iloc[0]
    deploy_start = us_inv["deploy_start_date"].iloc[0]
    deploy_end = us_inv["deploy_end_date"].iloc[0]

    overall_metrics = compute_alpha_sharpe(us_ret, start_date, end_date)
    deploy_metrics = compute_alpha_sharpe(us_ret, deploy_start, deploy_end)

    us_inv["overall_alpha_pct"] = overall_metrics["alpha_pct"]
    us_inv["overall_sharpe"] = overall_metrics["sharpe"]
    us_inv["deploy_alpha_pct"] = deploy_metrics["alpha_pct"]
    us_inv["deploy_sharpe"] = deploy_metrics["sharpe"]

    us_inv.to_csv(US_INVESTOR_FILE, index=False)
    print("✅ עודכן US עם Alpha ו‑Sharpe ב-us_investor_summary.csv")
    print(
        us_inv[
            [
                "total_return_pct",
                "benchmark_total_return_pct",
                "overall_alpha_pct",
                "overall_sharpe",
                "deploy_return_pct",
                "deploy_benchmark_return_pct",
                "deploy_alpha_pct",
                "deploy_sharpe",
            ]
        ].T
    )
    return us_inv


def compute_crypto_alpha_sharpe():
    # אם אין קובץ – נזרוק SystemExit ונטפל בזה ב-main
    ensure_file(CRYPTO_DAILY_FILE)
    ensure_file(CRYPTO_EQUITY_FILE)
    ensure_file(CRYPTO_INVESTOR_FILE)

    crypto_daily = pd.read_csv(CRYPTO_DAILY_FILE)
    crypto_daily["date"] = pd.to_datetime(crypto_daily["date"], errors="coerce")
    crypto_ret = compute_daily_returns_from_dollar_cols(
        crypto_daily, total_col="crypto_total", bench_col="crypto_benchmark"
    )

    cr_inv = pd.read_csv(CRYPTO_INVESTOR_FILE)
    # parse_dates גמיש – לא מניחים שיש deploy
    for col in ["start_date", "end_date", "deploy_start_date", "deploy_end_date"]:
        if col in cr_inv.columns:
            cr_inv[col] = pd.to_datetime(cr_inv[col], errors="coerce")

    start_date = cr_inv["start_date"].iloc[0]
    end_date = cr_inv["end_date"].iloc[0]
    overall_metrics = compute_alpha_sharpe(crypto_ret, start_date, end_date)

    cr_inv["overall_alpha_pct"] = overall_metrics["alpha_pct"]
    cr_inv["overall_sharpe"] = overall_metrics["sharpe"]

    # Deploy – רק אם שני העמודות קיימות ולא כולן NaT
    if "deploy_start_date" in cr_inv.columns and "deploy_end_date" in cr_inv.columns:
        deploy_start = cr_inv["deploy_start_date"].iloc[0]
        deploy_end = cr_inv["deploy_end_date"].iloc[0]
        if pd.notna(deploy_start) and pd.notna(deploy_end):
            deploy_metrics = compute_alpha_sharpe(crypto_ret, deploy_start, deploy_end)
            cr_inv["deploy_alpha_pct"] = deploy_metrics["alpha_pct"]
            cr_inv["deploy_sharpe"] = deploy_metrics["sharpe"]
        else:
            cr_inv["deploy_alpha_pct"] = np.nan
            cr_inv["deploy_sharpe"] = np.nan
    else:
        cr_inv["deploy_alpha_pct"] = np.nan
        cr_inv["deploy_sharpe"] = np.nan

    cr_inv.to_csv(CRYPTO_INVESTOR_FILE, index=False)
    print("✅ עודכן CRYPTO עם Alpha ו‑Sharpe ב-crypto_investor_summary.csv")
    cols_to_show = [
        c
        for c in [
            "total_return_pct",
            "benchmark_total_return_pct",
            "overall_alpha_pct",
            "overall_sharpe",
            "deploy_return_pct",
            "deploy_benchmark_return_pct",
            "deploy_alpha_pct",
            "deploy_sharpe",
        ]
        if c in cr_inv.columns
    ]
    print(cr_inv[cols_to_show].T)
    return cr_inv


def load_il_investor_summary() -> pd.DataFrame:
    if not os.path.isfile(IL_INVESTOR_FILE):
        print("⚠️ il_investor_summary.csv לא נמצא – IL לא יופיע עם Alpha/Sharpe.")
        return pd.DataFrame()
    df = pd.read_csv(IL_INVESTOR_FILE)
    return df


def build_multi_asset_extended(us_inv: pd.DataFrame,
                               cr_inv: pd.DataFrame,
                               il_inv: pd.DataFrame):
    ensure_file(MULTI_SUMMARY_FILE)
    base = pd.read_csv(MULTI_SUMMARY_FILE, parse_dates=["start_date", "end_date"])

    records = []

    # US
    if not us_inv.empty:
        rec = {
            "name": "US",
            "start_date": us_inv["start_date"].iloc[0],
            "end_date": us_inv["end_date"].iloc[0],
            "start_equity": us_inv["start_equity"].iloc[0],
            "end_equity": us_inv["end_equity"].iloc[0],
            "total_return_pct": us_inv["total_return_pct"].iloc[0],
            "max_drawdown_pct": us_inv["max_drawdown_pct"].iloc[0],
            "overall_alpha_pct": us_inv["overall_alpha_pct"].iloc[0],
            "overall_sharpe": us_inv["overall_sharpe"].iloc[0],
            "deploy_alpha_pct": us_inv["deploy_alpha_pct"].iloc[0],
            "deploy_sharpe": us_inv["deploy_sharpe"].iloc[0],
        }
        records.append(rec)

    # CRYPTO
    if cr_inv is not None and not cr_inv.empty:
        rec = {
            "name": "CRYPTO",
            "start_date": cr_inv["start_date"].iloc[0],
            "end_date": cr_inv["end_date"].iloc[0],
            "start_equity": cr_inv["start_equity"].iloc[0]
            if "start_equity" in cr_inv.columns
            else np.nan,
            "end_equity": cr_inv["end_equity"].iloc[0]
            if "end_equity" in cr_inv.columns
            else np.nan,
            "total_return_pct": cr_inv["total_return_pct"].iloc[0],
            "max_drawdown_pct": cr_inv["max_drawdown_pct"].iloc[0]
            if "max_drawdown_pct" in cr_inv.columns
            else np.nan,
            "overall_alpha_pct": cr_inv["overall_alpha_pct"].iloc[0],
            "overall_sharpe": cr_inv["overall_sharpe"].iloc[0],
            "deploy_alpha_pct": cr_inv["deploy_alpha_pct"].iloc[0],
            "deploy_sharpe": cr_inv["deploy_sharpe"].iloc[0],
        }
        records.append(rec)

    # IL
    if il_inv is not None and not il_inv.empty:
        rec = {
            "name": "IL",
            "start_date": il_inv["start_date"].iloc[0],
            "end_date": il_inv["end_date"].iloc[0],
            "start_equity": il_inv["start_equity"].iloc[0],
            "end_equity": il_inv["end_equity"].iloc[0],
            "total_return_pct": il_inv["total_return_pct"].iloc[0],
            "max_drawdown_pct": il_inv["max_drawdown_pct"].iloc[0]
            if "max_drawdown_pct" in il_inv.columns
            else np.nan,
            "overall_alpha_pct": il_inv["overall_alpha_pct"].iloc[0]
            if "overall_alpha_pct" in il_inv.columns
            else np.nan,
            "overall_sharpe": il_inv["overall_sharpe"].iloc[0]
            if "overall_sharpe" in il_inv.columns
            else np.nan,
            "deploy_alpha_pct": il_inv["deploy_alpha_pct"].iloc[0]
            if "deploy_alpha_pct" in il_inv.columns
            else np.nan,
            "deploy_sharpe": il_inv["deploy_sharpe"].iloc[0]
            if "deploy_sharpe" in il_inv.columns
            else np.nan,
        }
        records.append(rec)

    extended = pd.DataFrame(records)

    # MULTI מסכם – נשאר בלי Alpha בשלב זה
    multi_row = base[base["name"] == "MULTI"].copy()
    if not multi_row.empty:
        multi_rec = {
            "name": "MULTI",
            "start_date": multi_row["start_date"].iloc[0],
            "end_date": multi_row["end_date"].iloc[0],
            "start_equity": multi_row["start_equity"].iloc[0],
            "end_equity": multi_row["end_equity"].iloc[0],
            "total_return_pct": multi_row["total_return_pct"].iloc[0],
            "max_drawdown_pct": multi_row["max_drawdown_pct"].iloc[0],
            "overall_alpha_pct": np.nan,
            "overall_sharpe": np.nan,
            "deploy_alpha_pct": np.nan,
            "deploy_sharpe": np.nan,
        }
        extended = pd.concat([extended, pd.DataFrame([multi_rec])], ignore_index=True)

    extended.to_csv(MULTI_SUMMARY_EXTENDED_FILE, index=False)
    print(f"✅ נשמר קובץ טבלת השוואה מורחבת: {MULTI_SUMMARY_EXTENDED_FILE}")
    print(extended)
    return extended


def main():
    us_inv = compute_us_alpha_sharpe()
    try:
        cr_inv = compute_crypto_alpha_sharpe()
    except SystemExit:
        print("⚠️ לא עודכן CRYPTO (חסר קובץ יומי/סיכום). ממשיכים בלי קריפטו.")
        cr_inv = None
    il_inv = load_il_investor_summary()
    build_multi_asset_extended(us_inv, cr_inv, il_inv)


if __name__ == "__main__":
    main()
