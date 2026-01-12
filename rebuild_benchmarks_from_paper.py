# coding: utf-8

import os
import pandas as pd

RESULTS_DIR = "results_multi"

CRYPTO_PAPER = os.path.join(RESULTS_DIR, "crypto_paper_equity.csv")
US_PAPER = os.path.join(RESULTS_DIR, "us_paper_equity.csv")

CRYPTO_BENCH_OUT = os.path.join(RESULTS_DIR, "crypto_equity_curve.csv")
US_BENCH_OUT = os.path.join(RESULTS_DIR, "us_equity_curve.csv")


def rebuild_crypto_benchmark() -> None:
    if not os.path.exists(CRYPTO_PAPER):
        print(f"[CRYPTO] Missing file: {CRYPTO_PAPER}")
        return

    df = pd.read_csv(CRYPTO_PAPER)
    if "date" not in df.columns or "benchmark_equity" not in df.columns:
        print("[CRYPTO] crypto_paper_equity.csv must have 'date' and 'benchmark_equity' columns.")
        return

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    out = pd.DataFrame(
        {
            "date": df["date"],
            "equity": df["benchmark_equity"].astype(float),
        }
    )
    out.to_csv(CRYPTO_BENCH_OUT, index=False)
    print(f"[CRYPTO] Wrote BTC benchmark equity (full range) to: {CRYPTO_BENCH_OUT}")
    print(f"         Range: {out['date'].min()} -> {out['date'].max()}, rows={len(out)}")


def rebuild_us_benchmark() -> None:
    if not os.path.exists(US_PAPER):
        print(f"[US] Missing file: {US_PAPER}")
        return

    df = pd.read_csv(US_PAPER)
    if "date" not in df.columns or "benchmark_equity" not in df.columns:
        print("[US] us_paper_equity.csv must have 'date' and 'benchmark_equity' columns.")
        return

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    out = pd.DataFrame(
        {
            "date": df["date"],
            "equity": df["benchmark_equity"].astype(float),
        }
    )
    out.to_csv(US_BENCH_OUT, index=False)
    print(f"[US] Wrote US benchmark equity (full range) to: {US_BENCH_OUT}")
    print(f"     Range: {out['date'].min()} -> {out['date'].max()}, rows={len(out)}")


def main() -> None:
    print(f"Rebuilding benchmarks from paper equity in: {RESULTS_DIR}")
    rebuild_crypto_benchmark()
    rebuild_us_benchmark()


if __name__ == "__main__":
    main()
