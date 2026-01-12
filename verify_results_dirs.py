#!/usr/bin/env python3
# coding: utf-8

import os
import sys
from pathlib import Path
from typing import List, Tuple

# הנחת עבודה: הסקריפט רץ מתוך:
# /Users/zoharkalev/Desktop/trading_python/multi_asset_project
BASE_DIR = Path(__file__).resolve().parent

# תחת הפרויקט יש כרגע results_multi (עם קו תחתון)
RESULTS_UNDERSCORE = BASE_DIR / "results_multi"
# הקוד מחפש RESULTSDIR = "resultsmulti" (בלי קו תחתון)
RESULTS_NOSCORE = BASE_DIR / "resultsmulti"

# קבצים קריטיים שהדאשבורד מצפה להם
REQUIRED_FILES = [
    "cryptopaperequity.csv",
    "uspaperequity.csv",
    "multiadaptivepaperequity.csv",
    "cryptoequitycurve.csv",
    "usequitycurve.csv",
    "multiassetsummary.csv",
    "multiadaptivepapersummary.csv",
]


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def list_dir_safe(path: Path) -> List[str]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(p.name for p in path.iterdir())


def print_table(rows: List[Tuple[str, str]]) -> None:
    if not rows:
        print("אין שורות להציג.")
        return
    col1_width = max(len(r[0]) for r in rows) + 2
    for left, right in rows:
        print(left.ljust(col1_width) + right)


def check_results_multi() -> None:
    print_header("מצב תיקיות התוצאות בפרויקט")

    rows: List[Tuple[str, str]] = []
    rows.append(("BASE_DIR", str(BASE_DIR)))
    rows.append(("results_multi path", str(RESULTS_UNDERSCORE)))
    rows.append(("resultsmulti path", str(RESULTS_NOSCORE)))

    if RESULTS_UNDERSCORE.exists() and RESULTS_UNDERSCORE.is_dir():
        rows.append(("results_multi קיימת?", "כן (תיקייה)"))
    else:
        rows.append(("results_multi קיימת?", "לא"))

    if RESULTS_NOSCORE.exists():
        if RESULTS_NOSCORE.is_dir():
            kind = "תיקייה רגילה"
        elif RESULTS_NOSCORE.is_symlink():
            try:
                target = os.readlink(str(RESULTS_NOSCORE))
            except OSError:
                target = "UNKNOWN"
            kind = f"symlink -> {target}"
        else:
            kind = "קובץ רגיל"
        rows.append(("resultsmulti קיימת?", "כן (" + kind + ")"))
    else:
        rows.append(("resultsmulti קיימת?", "לא"))

    print_table(rows)

    print_header("תכולת results_multi (אם קיימת)")
    if RESULTS_UNDERSCORE.exists() and RESULTS_UNDERSCORE.is_dir():
        files = list_dir_safe(RESULTS_UNDERSCORE)
        if not files:
            print("results_multi קיימת אך ריקה.")
        else:
            for name in files:
                print(f"  - {name}")
    else:
        print("results_multi לא קיימת.")


def ensure_resultsmulti_link() -> None:
    print_header("יישור RESULTSDIR = 'resultsmulti' לשטח")

    if not RESULTS_UNDERSCORE.exists() or not RESULTS_UNDERSCORE.is_dir():
        print("אין results_multi, אין למה לקשר. קודם צריך שהתוצאות יישבו שם.")
        return

    if RESULTS_NOSCORE.exists():
        # כבר יש משהו בשם resultsmulti – לא ניגע, רק נציג
        if RESULTS_NOSCORE.is_symlink():
            target = os.readlink(str(RESULTS_NOSCORE))
            print(f"resultsmulti כבר קיים כ-symlink -> {target}")
        elif RESULTS_NOSCORE.is_dir():
            print("resultsmulti כבר קיים כתיקייה רגילה. הקוד אמור לעבוד עם זה.")
        else:
            print("יש אובייקט בשם resultsmulti שאינו תיקייה/קישור. עדיף לנקות ידנית אם זה לא בשימוש.")
        return

    # אין resultsmulti – ניצור symlink שמצביע על results_multi
    try:
        # חשוב: היעד הוא שם יחסי, כך שהתיקייה נשארת ניידת
        os.symlink("results_multi", str(RESULTS_NOSCORE))
        print("נוצר symlink בשם 'resultsmulti' שמצביע על 'results_multi'.")
        print("עכשיו כל קוד עם RESULTSDIR = 'resultsmulti' יראה את אותם קבצים.")
    except OSError as e:
        print("שגיאה ביצירת symlink:")
        print(e)
        print("אם symlink לא עובד בסביבה שלך, אפשר במקום זה פשוט לשנות בקוד את RESULTSDIR ל-'results_multi'.")


def validate_required_files() -> None:
    print_header("בדיקה שהקבצים הקריטיים קיימים")

    if not RESULTS_UNDERSCORE.exists() or not RESULTS_UNDERSCORE.is_dir():
        print("results_multi לא קיימת – אי אפשר לבדוק קבצים.")
        return

    rows: List[Tuple[str, str]] = []
    for fname in REQUIRED_FILES:
        full = RESULTS_UNDERSCORE / fname
        status = "OK" if full.exists() else "חסר"
        rows.append((fname, status))

    print_table(rows)
    print("\nאם משהו מסומן 'חסר' – הדאשבורדים (multi_asset_app / multi_asset_app_investors) לא יצליחו לטעון אותו.")


def main() -> None:
    check_results_multi()
    ensure_resultsmulti_link()
    validate_required_files()
    print_header("סיום")
    print("אם כל הקבצים מסומנים כ-OK ויש resultsmulti (כתיקייה או symlink), אפשר להריץ Streamlit בבטחה.")


if __name__ == "__main__":
    sys.exit(main())
