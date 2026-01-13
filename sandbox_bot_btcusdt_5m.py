import os
import time
import hmac
import hashlib
import requests
import urllib.parse
from datetime import datetime
import pandas as pd
import numpy as np

# --------------------------------------------------
# קונפיגורציה כללית
# --------------------------------------------------

BINANCE_TESTNET_BASE_URL = "https://testnet.binance.vision"  # Spot Testnet [web:7][web:10][web:16]
SYMBOL = "BTCUSDT"
TIMEFRAME = "5m"
INITIAL_CAPITAL = 100000.0  # הון התחלתי 100K
RISK_PER_TRADE = 0.01       # 1% מההון
SL_PCT = 0.01               # 1% Stop Loss
TP_PCT = 0.02               # 2% Take Profit
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
DATA_LIMIT = 500            # כמה נרות למשיכה מה־API
RESULTS_CSV = "sandbox_results_btcusdt_5m.csv"
LOG_CSV = "sandbox_trade_log_btcusdt_5m.csv"

API_KEY = os.environ.get("BINANCETESTNETAPIKEY", "")
API_SECRET = os.environ.get("BINANCETESTNETSECRETKEY", "")

# --------------------------------------------------
# לוגים בסיסיים
# --------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

# --------------------------------------------------
# עזר – חתימה וקריאות API חתומות
# --------------------------------------------------

def _sign_params(params: dict) -> str:
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return query_string + "&signature=" + signature

def _request(method: str, path: str, signed: bool = False, params: dict | None = None) -> dict:
    if params is None:
        params = {}
    headers = {"X-MBX-APIKEY": API_KEY} if signed else {}
    if signed:
        params["timestamp"] = int(time.time() * 1000)
        query = _sign_params(params)
    else:
        query = urllib.parse.urlencode(params)
    url = BINANCE_TESTNET_BASE_URL + path
    if query:
        url += "?" + query
    resp = requests.request(method, url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
    return resp.json()

# --------------------------------------------------
# משיכת דאטה – נרות 5 דקות
# --------------------------------------------------

def fetch_klines(symbol: str, interval: str = TIMEFRAME, limit: int = DATA_LIMIT) -> pd.DataFrame:
    path = "/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = _request("GET", path, signed=False, params=params)
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]
    df = pd.DataFrame(data, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df[["open", "high", "low", "close", "volume"]]

# --------------------------------------------------
# אינדיקטורים – RSI
# --------------------------------------------------

def compute_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    gain = pd.Series(gain, index=series.index)
    loss = pd.Series(loss, index=series.index)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

# --------------------------------------------------
# ניהול סיכון – חישוב גודל פוזיציה
# --------------------------------------------------

def calculate_position_size(capital: float, entry_price: float, sl_pct: float = SL_PCT) -> float:
    risk_amount = capital * RISK_PER_TRADE
    per_unit_risk = entry_price * sl_pct
    if per_unit_risk <= 0:
        return 0.0
    size = risk_amount / per_unit_risk
    return max(size, 0.0)

# --------------------------------------------------
# ביצוע – הזמנות טסטנט
# --------------------------------------------------

def place_order(symbol: str, side: str, quantity: float) -> dict:
    path = "/api/v3/order"
    params = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "MARKET",
        "quantity": float(f"{quantity:.6f}")
    }
    data = _request("POST", path, signed=True, params=params)
    return data

def get_account_balance(asset: str = "USDT") -> float:
    path = "/api/v3/account"
    data = _request("GET", path, signed=True, params={})
    balances = data.get("balances", [])
    for b in balances:
        if b.get("asset") == asset:
            return float(b.get("free", 0.0))
    return 0.0

# --------------------------------------------------
# לוגיקת אסטרטגיה – Mean Reversion עם RSI
# --------------------------------------------------

def generate_signal(df: pd.DataFrame) -> str:
    """
    מחזיר "LONG", "FLAT" או "EXIT_LONG"
    """
    if df.empty:
        return "FLAT"
    last = df.iloc[-1]
    rsi = last["rsi"]
    if rsi < RSI_OVERSOLD:
        return "LONG"
    if rsi > RSI_OVERBOUGHT:
        return "EXIT_LONG"
    return "FLAT"

# --------------------------------------------------
# לוגיקה – הרצת סשן קצר בסנדבוקס
# --------------------------------------------------

def run_sandbox_session() -> None:
    """
    מושך 5m קליינס, מחשב RSI, מחליט אם לפתוח/לסגור לונג יחיד,
    מבצע הזמנות טסטנט, ומעדכן CSV של Equity + לוגים.
    """
    log("מתחיל סשן Sandbox BTCUSDT 5m על Binance Spot Testnet")
    if not API_KEY or not API_SECRET:
        raise RuntimeError("חסר API KEY או SECRET ל-Binance Spot Testnet (BINANCETESTNETAPIKEY / BINANCETESTNETSECRETKEY).")

    # סימולציה: הון מקומי + בדיקה מול יתרת USDT בטסטנט
    capital = INITIAL_CAPITAL
    position_qty = 0.0
    entry_price = 0.0

    # משיכת דאטה
    df = fetch_klines(SYMBOL, TIMEFRAME, DATA_LIMIT)
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)

    # סיגנל אחרון
    signal = generate_signal(df)
    last_price = df["close"].iloc[-1]
    log(f"סיגנל אחרון: {signal}, מחיר: {last_price:.2f}, RSI: {df['rsi'].iloc[-1]:.2f}")

    # קריאה ליתרת USDT בטסטנט (לא חובה אבל שימושי)
    try:
        usdt_balance = get_account_balance("USDT")
        log(f"יתרת USDT בטסטנט: {usdt_balance:.2f}")
    except Exception as e:
        log(f"שגיאה בקריאת יתרה: {e}")
        usdt_balance = capital

    trades_log_rows = []
    equity_rows = []

    # החלטה: אם אין פוזיציה ואנחנו LONG -> פותחים
    if position_qty == 0.0 and signal == "LONG":
        qty = calculate_position_size(capital, last_price, SL_PCT)
        if qty > 0:
            try:
                order = place_order(SYMBOL, "BUY", qty)
                fills = order.get("fills", [])
                exec_price = last_price
                if fills:
                    exec_price = float(fills[0].get("price", last_price))
                position_qty = qty
                entry_price = exec_price
                cost = exec_price * qty
                capital -= cost  # יוצא מההון המזומן
                log(f"נפתחה פוזיציית לונג: כמות {qty:.6f}, מחיר {exec_price:.2f}, עלות {cost:.2f}")
                trades_log_rows.append({
                    "time": datetime.utcnow().isoformat(),
                    "symbol": SYMBOL,
                    "side": "BUY",
                    "qty": qty,
                    "price": exec_price,
                    "notional": cost
                })
            except Exception as e:
                log(f"שגיאה בפתיחת לונג: {e}")

    # אם יש פוזיציה וסיגנל EXIT_LONG -> סוגרים
    elif position_qty > 0.0 and signal == "EXIT_LONG":
        try:
            order = place_order(SYMBOL, "SELL", position_qty)
            fills = order.get("fills", [])
            exec_price = last_price
            if fills:
                exec_price = float(fills[0].get("price", last_price))
            revenue = exec_price * position_qty
            pnl = revenue - (entry_price * position_qty)
            capital += revenue
            log(f"סגירת לונג: כמות {position_qty:.6f}, מחיר {exec_price:.2f}, PnL {pnl:.2f}")
            trades_log_rows.append({
                "time": datetime.utcnow().isoformat(),
                "symbol": SYMBOL,
                "side": "SELL",
                "qty": position_qty,
                "price": exec_price,
                "notional": revenue,
                "pnl": pnl
            })
            position_qty = 0.0
            entry_price = 0.0
        except Exception as e:
            log(f"שגיאה בסגירת לונג: {e}")
    else:
        log("אין שינוי בפוזיציה בסשן הזה.")

    # חישוב Equity נוכחי (הון מזומן + שווי פוזיציה פתוחה)
    position_value = position_qty * last_price
    equity = capital + position_value
    equity_rows.append({
        "time": datetime.utcnow().isoformat(),
        "equity": equity,
        "cash": capital,
        "position_value": position_value,
        "position_qty": position_qty,
        "last_price": last_price
    })
    log(f"Equity נוכחי: {equity:.2f} (מזומן {capital:.2f}, פוזיציה {position_value:.2f})")

    # שמירת CSV – append
    if trades_log_rows:
        trades_df = pd.DataFrame(trades_log_rows)
        if not os.path.exists(LOG_CSV):
            trades_df.to_csv(LOG_CSV, index=False)
        else:
            trades_df.to_csv(LOG_CSV, mode="a", header=False, index=False)

    equity_df = pd.DataFrame(equity_rows)
    if not os.path.exists(RESULTS_CSV):
        equity_df.to_csv(RESULTS_CSV, index=False)
    else:
        equity_df.to_csv(RESULTS_CSV, mode="a", header=False, index=False)

    log(f"נשמרו לוגים ל-{LOG_CSV} ו-Equity ל-{RESULTS_CSV}")

# --------------------------------------------------
# main / entry point
# --------------------------------------------------

def main() -> None:
    log("Sandbox BTCUSDT 5m Bot – התחלה")
    log(f"INITIAL_CAPITAL: {INITIAL_CAPITAL}, RISK_PER_TRADE: {RISK_PER_TRADE}")
    run_sandbox_session()
    log("סיום סשן Sandbox")

if __name__ == "__main__":
    main()
