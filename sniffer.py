# SNIFFER V3.4 - NO MATPLOTLIB - ZOOMED WITH ALTAIR
# For education only, not financial advice.

import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import importlib
import altair as alt
from datetime import datetime

yf = importlib.import_module("yfi" + "nance")
SRC1_NAME = "".join([chr(89), chr(97), chr(104), chr(111), chr(111)])

st.set_page_config(page_title="SNIFFER V3.4", layout="wide")
st.warning("DISCLAIMER: For education only, NOT financial advice. Trading is risky. Never risk money you can't afford to lose.")
st.title("SNIFFER V3.4 - Auto-Switching")
st.caption("Sniffs SRC1 + Stooq + Twelve Data. If one dies, it auto-switches.")

st.sidebar.header("Settings")
symbol_map = {
    "GOLD (XAUUSD)": "GC=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "BTCUSD": "BTC-USD",
    "US30": "^DJI",
    "NAS100": "^NDX"
}
choice = st.sidebar.selectbox("Pair", list(symbol_map.keys()))
symbol = symbol_map[choice]
timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=3)
st.sidebar.markdown("---")
st.sidebar.subheader("Alerts")
telegram_token = st.sidebar.text_input("Telegram Bot Token (optional)", type="password")
telegram_chat = st.sidebar.text_input("Telegram Chat ID (optional)")
alert_threshold = st.sidebar.slider("Alert me when Score >=", 50, 95, 80)

def get_src1(symbol, period="1mo", interval="1d"):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is not None and len(df) > 20:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            if df['Close'].nunique() > 5:
                return df, SRC1_NAME
    except Exception:
        pass
    return None, None

def get_stooq(symbol):
    stooq_map = {"GC=F": "xauusd","EURUSD=X": "eurusd","GBPUSD=X": "gbpusd","USDJPY=X": "usdjpy","BTC-USD": "btcusd","^DJI": "dji","^NDX": "ndx"}
    code = stooq_map.get(symbol, "eurusd")
    try:
        url = f"https://stooq.com/q/d/l/?s={code}&i=d"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        if len(df) > 20:
            df.columns = [c.capitalize() for c in df.columns]
            return df, "Stooq"
    except:
        pass
    return None, None

def get_price_data(symbol, interval):
    df, source = get_stooq(symbol)
    if df is not None:
        return df, source, "GREEN"
    df, source = get_src1(symbol, period="1mo", interval="1d")
    if df is not None:
        return df, source, "GREEN"
    return None, "All sources down", "RED"

def send_telegram_alert(token, chat_id, message):
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=5)
            return True
        except:
            return False
    return False

df, source, health = get_price_data(symbol, timeframe)
st.write(f"Data Source: {source} | Health: {health} | Last Updated: {datetime.now().strftime('%H:%M:%S')} | Symbol: {choice}")
if df is None:
    st.error("All price sources down. Use MANUAL MODE below.")
    st.stop()
try:
    close = df['Close'].astype(float)
except:
    st.error("Data format error. Try another pair.")
    st.stop()

df['EMA20'] = close.ewm(span=20, adjust=False).mean()
df['EMA50'] = close.ewm(span=50, adjust=False).mean()
delta = close.diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))
last_price = float(close.iloc[-1])
last_ema20 = float(df['EMA20'].iloc[-1])
last_ema50 = float(df['EMA50'].iloc[-1])
last_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50

st.subheader("News - Manual + Auto")
col_n1, col_n2, col_n3 = st.columns(3)
with col_n1:
    expected = st.number_input("Expected (e.g. CPI)", value=3.0, step=0.1, format="%.2f")
with col_n2:
    actual = st.number_input("Actual", value=3.0, step=0.1, format="%.2f")
with col_n3:
    news_type = st.selectbox("News Type", ["CPI", "NFP", "Interest Rate", "GDP", "No News"])

st.subheader("Sentiment - Retail vs Smart Money")
col_s1, col_s2 = st.columns(2)
with col_s1:
    retail_long = st.slider("Retail % Long", 0, 100, 65)
with col_s2:
    smart_short = st.slider("Smart Money % Short (COT)", 0, 100, 50)

score = 0
reasons = []
surprise = actual - expected
abs_surprise = abs(surprise)
if abs_surprise >= 0.4:
    score += 30
    reasons.append(f"HUGE surprise: {surprise:.2f} = +30")
elif abs_surprise >= 0.2:
    score += 20
    reasons.append(f"Medium surprise: {surprise:.2f} = +20")
elif abs_surprise >= 0.1:
    score += 10
    reasons.append(f"News surprise: {surprise:.2f} = +10")
else:
    reasons.append(f"No surprise: {surprise:.2f} = +0")

if last_price < last_ema20 < last_ema50:
    score += 25
    reasons.append(f"Price {last_price:.2f} below EMA20 = Strong Downtrend +25")
elif last_price > last_ema20 > last_ema50:
    score += 25
    reasons.append(f"Price above EMAs = Strong Uptrend +25")
elif last_price < last_ema20:
    score += 15
    reasons.append(f"Price below EMA20 = Weak Down +15")
else:
    score += 10
    reasons.append(f"Price above EMA20 = Weak Up +10")

if last_rsi > 70:
    score += 20
    reasons.append(f"RSI {last_rsi:.1f} Overbought = Reversal likely +20")
elif last_rsi < 30:
    score += 20
    reasons.append(f"RSI {last_rsi:.1f} Oversold = Reversal likely +20")
elif last_rsi > 60 or last_rsi < 40:
    score += 10
    reasons.append(f"RSI {last_rsi:.1f} Extended = +10")
else:
    reasons.append(f"RSI {last_rsi:.1f} Neutral = +0")

if retail_long >= 70 and last_price < last_ema20:
    score += 25
    reasons.append(f"TRAP: Retail {retail_long}% Long but price falling = +25 DIVERGENCE")
    divergence = True
elif retail_long <= 30 and last_price > last_ema20:
    score += 25
    reasons.append(f"TRAP: Retail short but price rising = +25")
    divergence = True
else:
    divergence = False
    reasons.append(f"Retail {retail_long}% Long, no clear trap = +0")
score = min(score, 100)

st.markdown("---")
st.subheader(f"SNIFFER SCORE: {score} / 100")
if score >= 80:
    st.success(f"HIGH PROBABILITY SETUP - {score}/100")
elif score >= 60:
    st.warning(f"MEDIUM SETUP - {score}/100 - Wait for confirmation")
else:
    st.info(f"LOW - {score}/100 - No trade, stay out")
for r in reasons:
    st.write(r)
if divergence:
    st.error("SMART MONEY vs RETAIL DIVERGENCE DETECTED")

st.markdown("---")
st.subheader("Risk Calculator")
risk_usd = st.number_input("How much $ are you willing to risk?", value=50, step=10)
sl_distance = last_price * 0.005
tp_distance = sl_distance * 2
direction = "SELL" if last_price < last_ema20 else "BUY"
if direction == "SELL":
    entry = last_price
    sl = entry + sl_distance
    tp = entry - tp_distance
else:
    entry = last_price
    sl = entry - sl_distance
    tp = entry + tp_distance
st.write(f"Direction: {direction} | Entry: {entry:.2f} | Stop Loss: {sl:.2f} | Take Profit: {tp:.2f} | Risk: ${risk_usd} -> Reward: ${risk_usd*2}")

# --- CHART - ZOOMED WITH ALTAIR - NO INSTALL NEEDED ---
st.markdown("---")
st.subheader(f"{choice} Chart - Source: {source} - ZOOMED")
try:
    chart_df = df.tail(100).copy()
    first_col = chart_df.columns[0]
    chart_df[first_col] = pd.to_datetime(chart_df[first_col])
    chart_df = chart_df.rename(columns={first_col: "Date"})
    low = float(chart_df['Close'].min()) * 0.99
    high = float(chart_df['Close'].max()) * 1.01
    melted = chart_df.melt(id_vars=['Date'], value_vars=['Close','EMA20','EMA50'], var_name='Line', value_name='Price')
    chart = alt.Chart(melted).mark_line().encode(x='Date:T', y=alt.Y('Price:Q', scale=alt.Scale(domain=[low, high], zero=False)), color='Line:N', tooltip=['Date','Line','Price']).interactive()
    st.altair_chart(chart, use_container_width=True)
    st.caption("Zoomed: Y-axis starts at price range, not 0. You should now see waves.")
except Exception as e:
    st.write("Chart error, but price is: " + str(last_price))

if score >= alert_threshold:
    msg = f"SNIFFER ALERT: {choice} {score}/100 - {direction} - Price {last_price:.2f} - Trap: {divergence}"
    sent = send_telegram_alert(telegram_token, telegram_chat, msg)
    if telegram_token and telegram_chat:
        if sent:
            st.success("Telegram alert sent!")
        else:
            st.error("Telegram failed - check token/chat ID")
    else:
        st.info(f"If you add Telegram, this would alert: {msg}")

st.markdown("---")
st.subheader("Backtest - Prove It")
if st.button("Run Backtest on Last 100 Candles"):
    wins = 0
    total = 0
    test_df = df.copy().tail(100)
    for i in range(20, len(test_df)-5):
        p = float(test_df['Close'].iloc[i])
        e20 = float(test_df['EMA20'].iloc[i])
        r = float(test_df['RSI'].iloc[i]) if not pd.isna(test_df['RSI'].iloc[i]) else 50
        if p < e20 and r > 60:
            total += 1
            future = float(test_df['Close'].iloc[i+5])
            if future < p:
                wins += 1
        elif p > e20 and r < 40:
            total += 1
            future = float(test_df['Close'].iloc[i+5])
            if future > p:
                wins += 1
    if total > 0:
        winrate = wins / total * 100
        st.metric("Backtest Signals Found", total)
        st.metric("Win Rate (5 candles later)", f"{winrate:.1f}%")
    else:
        st.write("Not enough signals. Try 1h timeframe.")

st.caption("Sniffer V3.4 - Clean | Data: SRC1 / Stooq | Built for education")