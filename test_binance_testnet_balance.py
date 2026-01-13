#!/usr/bin/env python3
# coding: utf-8
import os
import ccxt

BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
BINANCE_TESTNET_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY")

def main():
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        raise RuntimeError("חסר BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_SECRET_KEY ב-env.")
    exchange = ccxt.binance({
        "apiKey": BINANCE_TESTNET_API_KEY,
        "secret": BINANCE_TESTNET_SECRET_KEY,
        "enableRateLimit": True,
    })
    exchange.set_sandbox_mode(True)
    balance = exchange.fetch_balance()
    print("=== SPOT TESTNET BALANCE ===")
    for asset, info in balance["total"].items():
        qty = float(info)
        if qty != 0.0:
            free = float(balance["free"].get(asset, 0.0))
            print(f"{asset}: total={qty}, free={free}")
    print("============================")

if __name__ == "__main__":
    main()
