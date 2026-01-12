#!/usr/bin/env python3
# coding: utf-8

import os
import sys
from pathlib import Path
from typing import Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results_multi"

# מיפוי בין השמות הקיימים לשמות שה-Streamlit מצפה להם
FILE_MAP: Dict[str, str] = {
    # Strategy equity (Paper)
    "crypto_paper_equity.csv":          "cryptopaperequity.csv",
    "us_paper_equity.csv":              "uspaperequity.csv",
    "multi_adaptive_paper_equity.csv":  "multiadaptivepaperequity.csv",
    # Benchmarks equity curves
    "crypto_equity_curve.csv":          "cryptoequitycurve.csv",
    "us_equity_curve.csv":              "usequitycurve.csv",
    # Summary tables
    "multi_asset_summary.csv":          "multiassetsummary.csv",
    "multi_adaptive_paper_summary.csv": "multiadaptivepapersummary.csv",
}

def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def sync_files() -> None:
    print_header(f"סנכרון קבצי results_multi ל-Streamlit (בסיס: {RESULTS_DIR})")

    if not RESULTS_DIR.exists() or not RESULTS_DIR.is_dir():
        print(f"תיקיית התוצאות לא נמצאה: {RESULTS_DIR}")
        sys.exit(1)

    rows: list[Tuple[str, str]] = []

    for src_name, dst_name in FILE_MAP.items():
        src_path = RESULTS_DIR / src_name
        dst_path = RESULTS_DIR / dst_name

        if not src_path.exists():
            rows.append((dst_name, f"חסר מקור ({src_name} לא קיים)"))
            continue

        # אם קובץ היעד כבר קיים, נדלג אבל נדווח
        if dst_path.exists():
            rows.append((dst_name, f"כבר קיים (נשאר כמו שהוא)"))
            continue

        try:
            # העתקה בינארית פשוטה 1:1 – בלי שינוי תוכן
            with src_path.open("rb") as f_src, dst_path.open("wb") as f_dst:
                f_dst.write(f_src.read())
            rows.append((dst_name, f"נוצר מתוך {src_name}"))
        except Exception as e:
            rows.append((dst_name, f"שגיאה ביצירה מתוך {src_name}: {e}"))

    # הדפסה מסודרת
    col1_width = max(len(r[0]) for r in rows) + 2 if rows else 30
    print("\nתוצאות מיפוי:")
    if not rows:
        print("לא בוצע שום מיפוי (כנראה שאין מיפוי מוגדר או הכל כבר קיים).")
    else:
        for left, right in rows:
            print(left.ljust(col1_width) + right)


def main() -> None:
    print_header("בדיקת נתיב בסיס")
    print(f"BASE_DIR:   {BASE_DIR}")
    print(f"RESULTS_DIR: {RESULTS_DIR}")

    sync_files()

    print_header("סיום")
    print("אם כל השורות מעל מראות 'נוצר מתוך ...' או 'כבר קיים', אפשר להריץ Streamlit והקוד ימצא את הקבצים.")


if __name__ == "__main__":
    sys.exit(main())
