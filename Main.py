import os
import asyncio
import redis
import random
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Health Check for Railway
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online")

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL") or "redis://redis.railway.internal:6379"
db = redis.from_url(REDIS_URL, decode_responses=True)
logging.basicConfig(level=logging.INFO)

def get_bal(uid):
    try: return int(db.get(f"bal:{uid}") or 1000)
    except: return 1000

def set_bal(uid, amt):
    try: db.set(f"bal:{uid}", amt)
    except: pass

def main_menu():
    keyboard = [
        [InlineKeyboardButton(" Spin", callback_data='slots'), InlineKeyboardButton(" גלגל המזל", callback_data='wheel')],
        [InlineKeyboardButton(" בונוס יומי", callback_data='daily'), InlineKeyboardButton(" פרופיל", callback_data='profile')],
        [InlineKeyboardButton(" טבלה", callback_data='leaderboard')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bal = get_bal(user.id)
    text = (f" <b>NFTY CASINO V34</b> \n"
            f"\n"
            f" שחקן: <b>{user.first_name}</b>\n"
            f" יתרה: <b>{bal:,} </b>\n"
            f"")
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu(), parse_mode='HTML')

async def handle_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data == 'slots':
        kb = [[InlineKeyboardButton("הימור 50", callback_data='bet_50'), 
               InlineKeyboardButton("הימור 100", callback_data='bet_100')],
              [InlineKeyboardButton(" חזור", callback_data='home')]]
        await query.edit_message_text(" בחר סכום הימור:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('bet_'):
        amt = int(query.data.split('_')[1])
        bal = get_bal(uid)
        if bal < amt:
            await query.message.reply_text(" אין לך מספיק מטבעות!")
            return
        
        set_bal(uid, bal - amt)
        try: await query.delete_message()
        except: pass
        
        m = await query.message.reply_dice(emoji='')
        await asyncio.sleep(4)
        
        if m.dice.value in [1, 22, 43, 64]:
            win = amt * 10
            set_bal(uid, get_bal(uid) + win)
            await query.message.reply_text(f" זכית ב-{win:,} מטבעות!", reply_markup=main_menu())
        else:
            await query.message.reply_text("הפסדת... נסה שוב! ", reply_markup=main_menu())

    elif query.data == 'home':
        await start(update, context)

def main():
    Thread(target=run_health_server, daemon=True).start()
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_clicks))
    print(" V34 DEPLOYED")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
# VERSION_TAG: 34.0.1