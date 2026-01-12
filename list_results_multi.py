# coding: utf-8

import os

RESULTS_DIR = "results_multi"

def main() -> None:
    print(f"Listing files in: {RESULTS_DIR}")
    if not os.path.isdir(RESULTS_DIR):
        print("Directory does not exist.")
        return

    for name in sorted(os.listdir(RESULTS_DIR)):
        path = os.path.join(RESULTS_DIR, name)
        size = os.path.getsize(path)
        print(f"{name:35s}  {size:10d} bytes")

if __name__ == "__main__":
    main()
