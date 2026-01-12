#!/usr/bin/env python3
# coding: utf-8

import os
from pathlib import Path

def main() -> None:
    base = Path(".").resolve()
    print(f"Scanning repo at: {base}")
    print("Files > 5MB:\n")
    for root, _, files in os.walk(base):
        if ".git" in root:
            continue
        for name in files:
            path = Path(root) / name
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > 5:
                print(f"{size_mb:6.2f} MB  {path.relative_to(base)}")

if __name__ == "__main__":
    main()
