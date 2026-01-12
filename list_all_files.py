#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
list_all_files.py

סריקה רקורסיבית של כל הקבצים תחת תיקיית הפרויקט,
עם נתיב יחסי מגג הפרויקט + גודל בבתים.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main() -> None:
    print("Project root:", BASE_DIR)
    print()
    print("All files under project:")
    print("=" * 80)

    for root, dirs, files in os.walk(BASE_DIR):
        # דילוג על venv כדי לא להציף זבל
        if os.path.basename(root) in {"venv", ".git", "__pycache__"}:
            continue
        for f in sorted(files):
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, BASE_DIR)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = -1
            print(f"{rel_path:80s}  {size:10d} bytes")

    print("=" * 80)

if __name__ == "__main__":
    main()
