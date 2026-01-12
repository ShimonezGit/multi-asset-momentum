import pandas as pd
import ccxt

# בדוק מה בפועל יש בדאטה
exchange = ccxt.binance({"enableRateLimit": True})

# DOGE - היום הראשון
print("=== בדיקת DOGE/USDT ===")
start_ms = int(pd.Timestamp("2024-04-08").timestamp() * 1000)
ohlcv = exchange.fetch_ohlcv("DOGE/USDT", timeframe="1d", since=start_ms, limit=5)

for candle in ohlcv:
    dt = pd.to_datetime(candle[0], unit="ms")
    close = candle[4]
    print(f"{dt.date()}: close=${close:.5f}")

# בדוק מה הבקטסט ראה
print("\n=== מה הבקטסט צריך לראות ===")
bt_eq = pd.read_csv('results_multi/crypto_equity_curve.csv')
bt_eq['date'] = pd.to_datetime(bt_eq['date'])
print(f"Backtest מתחיל: {bt_eq['date'].min()}")
print(f"Backtest מסיים: {bt_eq['date'].max()}")
print(f"ימים ראשונים עם equity=100K: {len(bt_eq[bt_eq['equity'] == 100000.0])}")

# אותו דבר Paper
print("\n=== מה ה-Paper צריך לראות ===")
paper_eq = pd.read_csv('results_multi/crypto_paper_equity.csv')
paper_eq['date'] = pd.to_datetime(paper_eq['date'])
print(f"Paper מתחיל: {paper_eq['date'].min()}")
print(f"Paper מסיים: {paper_eq['date'].max()}")
print(f"ימים ראשונים עם equity=100K: {len(paper_eq[paper_eq['equity'] == 100000.0])}")
