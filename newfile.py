
!pip install nest_asyncio python-telegram-bot aiohttp

import nest_asyncio
nest_asyncio.apply()

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import matplotlib.pyplot as plt
import io
import aiohttp

# ⚙️ TOKENLAR
TOKEN = '8073094606:AAFC6tSJWVhhkfNbifYXVcZUgwZJ82QDU1o'
CHAT_ID = '636914093'
API_KEY = '1c10752e92ea481ca2992336e5700c74'
SYMBOL = 'XAU/USD, BTC/USD'

signal_active = True  # Faollik holati

# 📊 INDICATOR TEKSHIRISH
def check_indicators(df):
    df['EMA50'] = df['close'].ewm(span=50).mean()
    df['EMA200'] = df['close'].ewm(span=200).mean()
    df['MACD'] = df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()
    df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
    df['RSI'] = 100 - (100 / (1 + df['close'].pct_change().rolling(14).mean()))

    latest = df.iloc[-1]
    signal = None
    reasons = []

    # EMA trend
    if latest['EMA50'] > latest['EMA200']:
        reasons.append("✅ EMA50 > EMA200")
    else:
        reasons.append("❌ EMA50 < EMA200")

    # MACD crossover
    if latest['MACD'] > latest['MACD_signal']:
        reasons.append("✅ MACD crossover")
    else:
        reasons.append("❌ No MACD crossover")

    # RSI
    if latest['RSI'] < 30:
        signal = 'BUY'
        reasons.append("✅ RSI < 30 (Oversold)")
    elif latest['RSI'] > 70:
        signal = 'SELL'
        reasons.append("✅ RSI > 70 (Overbought)")
    else:
        reasons.append("❌ No RSI signal")

    if "✅" in ''.join(reasons) and signal:
        return signal, latest, reasons
    else:
        return None, latest, reasons

# 📈 GRAFIK CHIZISH
def plot_chart(df, symbol, signal):
    plt.figure(figsize=(8, 4))
    plt.plot(df['close'], label='Price', linewidth=1.5)
    plt.plot(df['EMA50'], label='EMA50')
    plt.plot(df['EMA200'], label='EMA200')
    plt.title(f'{symbol} - {signal}')
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# ✉️ SIGNAL YUBORISH
async def send_signal(bot, signal, last, reasons, df):
    sl = round(last['close'] - 5, 2) if signal == 'BUY' else round(last['close'] + 5, 2)
    tp1 = round(last['close'] + 10, 2) if signal == 'BUY' else round(last['close'] - 10, 2)
    tp2 = round(last['close'] + 20, 2) if signal == 'BUY' else round(last['close'] - 20, 2)
    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    message = f"""📊 {SYMBOL} (1H)
🔹 Trend: {signal}
📈 Entry: {last['close']}
⛔ SL: {sl}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
🧠 Confirmations:
{chr(10).join(reasons)}
🕐 Signal sent at: {time_now}
    """
    chart = plot_chart(df, SYMBOL, signal)
    await bot.send_photo(chat_id=CHAT_ID, photo=chart, caption=message)

# 📥 APIdan MA'LUMOT OLISH
async def fetch_data():
    url = f'https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval=1h&apikey={API_KEY}&outputsize=100'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if 'values' in data:
                df = pd.DataFrame(data['values'])
                df = df.iloc[::-1]
                df['close'] = df['close'].astype(float)
                return df
            else:
                return None

# 🟢 /start BUYRUG'I
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global signal_active
    signal_active = True
    await update.message.reply_text("✅ Signal yuborish faollashtirildi.")

# 🔴 /stop BUYRUG'I
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global signal_active
    signal_active = False
    await update.message.reply_text("🛑 Signal yuborish to‘xtatildi.")

# 🔁 DOIMIY TEKSHIRISH FUNKSIYASI
async def check_market(app):
    sent_today = 0
    last_day = datetime.now().date()
    bot = Bot(TOKEN)

    while True:
        now = datetime.now()
        if signal_active:
            if now.date() != last_day:
                sent_today = 0
                last_day = now.date()

            if sent_today < 3:
                df = await fetch_data()
                if df is not None:
                    signal, last, reasons = check_indicators(df)
                    if signal:
                        await send_signal(bot, signal, last, reasons, df)
                        sent_today += 1

        await asyncio.sleep(3600)  # Har soatda tekshiradi

# 🔧 ASOSIY FUNKSIYA
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    asyncio.create_task(check_market(app))
    await app.run_polling()

await main()