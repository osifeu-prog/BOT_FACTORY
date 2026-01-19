import os
import asyncio
import redis
import random
import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
REDIS_URL = os.getenv("REDIS_URL") or "redis://redis.railway.internal:6379"
db = redis.from_url(REDIS_URL, decode_responses=True)

logging.basicConfig(level=logging.INFO)

def get_bal(uid): return int(db.get(f"bal:{uid}") or 1000)
def set_bal(uid, amt): db.set(f"bal:{uid}", amt)

def get_menu(uid):
    is_happy = db.get("happy_hour") == "1"
    slot_text = " Spin (Happy Hour! )" if is_happy else " Spin"
    keyboard = [
        [InlineKeyboardButton(slot_text, callback_data='v_slots'), InlineKeyboardButton(" גלגל המזל", callback_data='wheel')],
        [InlineKeyboardButton(" ארקייד", callback_data='v_arcade'), InlineKeyboardButton(" בונוס יומי", callback_data='daily')],
        [InlineKeyboardButton(" טבלה", callback_data='leader'), InlineKeyboardButton(" פרופיל", callback_data='prof')],
        [InlineKeyboardButton(" קופון", callback_data='promo')]
    ]
    if str(uid) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton(" Admin Panel", callback_data='admin')])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bal = get_bal(user.id)
    db.sadd("all_users", user.id)
    db.zadd("leaderboard", {user.first_name: bal})
    
    msg = f" <b>NFTY CASINO V29</b> \n\n שחקן: <b>{user.first_name}</b>\n יתרה: <b>{bal:,} </b>\n"
    if db.get("happy_hour") == "1": msg += "\n <b>HAPPY HOUR: זכיות כפולות!</b>"
    
    if update.message: await update.message.reply_text(msg, reply_markup=get_menu(user.id), parse_mode='HTML')
    else: await update.callback_query.edit_message_text(msg, reply_markup=get_menu(user.id), parse_mode='HTML')

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    bal = get_bal(uid)
    await query.answer()

    if context.user_data.get('lock'): return

    if query.data == 'v_slots':
        kb = [[InlineKeyboardButton("הימור 50", callback_data='b_50'), InlineKeyboardButton("הימור 100", callback_data='b_100')], [InlineKeyboardButton(" חזור", callback_data='home')]]
        await query.edit_message_text(" בחר סכום הימור:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('b_'):
        amt = int(query.data.split('_')[1])
        if bal < amt:
            await query.message.reply_text(" אין לך מספיק כסף!")
            return
        context.user_data['lock'] = True
        set_bal(uid, bal - amt)
        try: await query.delete_message()
        except: pass
        m = await query.message.reply_dice(emoji='')
        await asyncio.sleep(4)
        if m.dice.value in [1, 22, 43, 64]:
            mult = 20 if db.get("happy_hour") == "1" else 10
            win = amt * mult
            set_bal(uid, get_bal(uid) + win)
            await query.message.reply_text(f" <b>זכית ב-{win:,}!</b>", reply_markup=get_menu(uid), parse_mode='HTML')
        else:
            await query.message.reply_text("לא הפעם... נסה שוב!", reply_markup=get_menu(uid))
        context.user_data['lock'] = False

    elif query.data == 'daily':
        today = datetime.now().strftime("%d%m")
        if db.get(f"d:{uid}") == today:
            await query.message.reply_text(" כבר אספת היום!")
        else:
            db.set(f"d:{uid}", today)
            set_bal(uid, bal + 250)
            await query.message.reply_text(" קיבלת 250 מטבעות!", reply_markup=get_menu(uid))

    elif query.data == 'home': await start(update, context)

async def promo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() == "GIFT2026":
        uid = update.effective_user.id
        if not db.get(f"up:{uid}"):
            db.set(f"up:{uid}", "1")
            set_bal(uid, get_bal(uid) + 500)
            await update.message.reply_text(" קופון נוצל! +500 ")
        else: await update.message.reply_text(" כבר נוצל.")
    await start(update, context)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, promo_handler))
    
    if random.random() < 0.2: db.setex("happy_hour", 3600, "1")
    else: db.delete("happy_hour")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()