#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest מעודכן - חלק 1"""

import datetime
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import ccxt
import yfinance as yf

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"
TIMEFRAME_CRYPTO = "1d"
INITIAL_CAPITAL = 100_000.0

CRYPTO_ALT_SYMBOLS = ["ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "LINK/USDT", "MATIC/USDT", "OP/USDT"]
CRYPTO_BENCHMARK = "BTC/USDT"
US_STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL", "AVGO", "AMD", "NFLX"]
US_BENCHMARK = "SPY"
IL_STOCKS = ["TEVA.TA", "LUMI.TA", "POLI.TA", "BEZQ.TA", "ICL.TA", "NVMI.TA", "MZTF.TA", "ENLT.TA", "ESLT.TA", "HARL.TA"]
IL_BENCHMARK = "TA35.TA"

TREND_MA_WINDOW = 100
MOMENTUM_LOOKBACK = 20
MOMENTUM_THRESHOLD = 0.10
EXIT_LOOKBACK = 10
MAX_POSITIONS = 5
RESULTS_DIR = "results_multi"
