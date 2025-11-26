import logging
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import Bot

from app.core.config import settings
from app.database import SessionLocal
from app import crud, models

logger = logging.getLogger(__name__)

STATE_AWAITING_BNB_ADDRESS = "AWAITING_BNB_ADDRESS"
STATE_AWAITING_TRANSFER_TARGET = "AWAITING_TRANSFER_TARGET"
STATE_AWAITING_TRANSFER_AMOUNT = "AWAITING_TRANSFER_AMOUNT"


class InvestorWalletBot:
    def __init__(self):
        self.application: Application | None = None
        self.bot: Bot | None = None

    def _db(self):
        return SessionLocal()

    async def initialize(self):
        if not settings.BOT_TOKEN:
            logger.warning("BOT_TOKEN is not set, skipping Telegram bot initialization")
            return

        self.application = Application.builder().token(settings.BOT_TOKEN).build()
        self.bot = self.application.bot

        # Commands
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("wallet", self.cmd_wallet))
        self.application.add_handler(CommandHandler("link_wallet", self.cmd_link_wallet))
        self.application.add_handler(CommandHandler("balance", self.cmd_balance))
        self.application.add_handler(CommandHandler("transfer", self.cmd_transfer))

        # Admin-only command
        self.application.add_handler(CommandHandler("admin_credit", self.cmd_admin_credit))

        # Callback for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.cb_wallet_menu, pattern="^WALLET_"))

        # Generic text handler (for address / amounts / usernames)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )

        # Webhook mode
        if settings.WEBHOOK_URL:
            webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}/webhook/telegram"
            await self.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            logger.info("No WEBHOOK_URL set - you can run in polling mode locally")

        logger.info("InvestorWalletBot initialized")

    # Helpers

    def _ensure_user(self, update: Update) -> models.User:
        db = self._db()
        try:
            tg_user = update.effective_user
            return crud.get_or_create_user(
                db, telegram_id=tg_user.id, username=tg_user.username
            )
        finally:
            db.close()

    async def _send_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        buttons = [
            [
                InlineKeyboardButton("Balance", callback_data="WALLET_BALANCE"),
                InlineKeyboardButton("Wallet", callback_data="WALLET_DETAILS"),
            ],
            [
                InlineKeyboardButton("Buy BNB", callback_data="WALLET_BUY_BNB"),
            ],
        ]
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # Commands

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._ensure_user(update)

        min_invest = 100_000
        text = (
            "Welcome to the SLH Investor Gateway.\n\n"
            f"This bot is intended for strategic investors (minimum {min_invest:,.0f} ILS).\n\n"
            "You can:\n"
            "- Link your personal BNB address (BSC)\n"
            "- View your off-chain SLH balance\n"
            "- Transfer SLH units to other users (off-chain)\n"
            "- Get external links for buying BNB / staking info\n\n"
            "Use /wallet to see details and options."
        )
        await update.message.reply_text(text)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "SLH Wallet Bot - Help\n\n"
            "/start - Intro screen\n"
            "/wallet - Wallet details and links\n"
            "/link_wallet - Link your personal BNB address\n"
            "/balance - View SLH off-chain balance\n"
            "/transfer - Internal off-chain transfer to another user\n\n"
            "No redemption at this stage - only usage of SLH wallet. "
            "BNB and gas are handled by you through external providers."
        )
        await update.message.reply_text(text)

    async def cmd_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._ensure_user(update)
        addr = settings.COMMUNITY_WALLET_ADDRESS or "<community wallet not set>"
        token_addr = settings.SLH_TOKEN_ADDRESS or "<SLH token not set>"

        user_addr = user.bnb_address or "You have not linked a BNB address yet (see /link_wallet)."

        text = (
            "SLH Wallet Overview\n\n"
            f"Your BNB address (BSC):\n"
            f"{user_addr}\n\n"
            f"Community wallet address (for deposits / tracking):\n"
            f"`{addr}`\n\n"
            f"SLH token address:\n"
            f"`{token_addr}`\n\n"
            f"Each SLH nominally represents {settings.SLH_PRICE_NIS:.0f} ILS.\n"
        )

        if settings.BSC_SCAN_BASE and addr and not addr.startswith("<"):
            text += (
                f"\nView community wallet on BscScan:\n"
                f"{settings.BSC_SCAN_BASE.rstrip('/')}/address/{addr}\n"
            )
        if settings.BSC_SCAN_BASE and token_addr and not token_addr.startswith("<"):
            text += (
                f"View SLH token on BscScan:\n"
                f"{settings.BSC_SCAN_BASE.rstrip('/')}/token/{token_addr}\n"
            )
        if settings.BUY_BNB_URL:
            text += f"\nExternal BNB purchase link (optional):\n{settings.BUY_BNB_URL}\n"
        if settings.STAKING_INFO_URL:
            text += f"\nBNB staking info:\n{settings.STAKING_INFO_URL}\n"

        await update.message.reply_text(text, parse_mode="Markdown")

    async def cmd_link_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._ensure_user(update)
        context.user_data["state"] = STATE_AWAITING_BNB_ADDRESS
        await update.message.reply_text(
            "Send your BNB address (BSC network, usually starts with 0x...)."
        )

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db = self._db()
        try:
            tg_user = update.effective_user
            user = crud.get_or_create_user(db, telegram_id=tg_user.id, username=tg_user.username)
            balance = user.balance_slh or Decimal("0")
            text = (
                "SLH Off-Chain Balance\n\n"
                f"Current balance: {balance:.4f} SLH\n\n"
                "This reflects allocations recorded for you inside the system.\n"
                "No redemption yet - only future usage inside the ecosystem."
            )
            await update.message.reply_text(text)
        finally:
            db.close()

    async def cmd_transfer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._ensure_user(update)
        await update.message.reply_text(
            "Type the target username you want to transfer to (e.g. @username)."
        )
        context.user_data["state"] = STATE_AWAITING_TRANSFER_TARGET

    async def cmd_admin_credit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_id = settings.ADMIN_USER_ID
        if not admin_id or str(update.effective_user.id) != str(admin_id):
            await update.message.reply_text("This command is admin-only.")
            return

        parts = (update.message.text or "").split()
        if len(parts) != 3:
            await update.message.reply_text("Usage: /admin_credit <telegram_id> <amount_slh>")
            return

        try:
            target_id = int(parts[1])
            amount = float(parts[2])
        except ValueError:
            await update.message.reply_text("Invalid parameters. Check ID and amount.")
            return

        db = self._db()
        try:
            user = crud.get_or_create_user(db, telegram_id=target_id, username=None)
            tx = crud.change_balance(
                db,
                user=user,
                delta_slh=amount,
                tx_type="admin_credit",
                from_user=None,
                to_user=target_id,
            )
            await update.message.reply_text(
                f"Credited {amount:.4f} SLH to user {target_id}.\nTransaction ID: {tx.id}"
            )
        finally:
            db.close()

    # Callbacks

    async def cb_wallet_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "WALLET_BALANCE":
            fake_update = Update(update.update_id, message=query.message)
            await self.cmd_balance(fake_update, context)
        elif data == "WALLET_DETAILS":
            fake_update = Update(update.update_id, message=query.message)
            await self.cmd_wallet(fake_update, context)
        elif data == "WALLET_BUY_BNB":
            if settings.BUY_BNB_URL:
                await query.edit_message_text(
                    f"Suggested BNB provider:\n{settings.BUY_BNB_URL}"
                )
            else:
                await query.edit_message_text("BUY_BNB_URL not set in environment variables.")

    # Text handler

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = context.user_data.get("state")
        text = (update.message.text or "").strip()
        db = self._db()
        try:
            tg_user = update.effective_user
            user = crud.get_or_create_user(db, telegram_id=tg_user.id, username=tg_user.username)

            if state == STATE_AWAITING_BNB_ADDRESS:
                context.user_data["state"] = None
                if not text.startswith("0x") or len(text) < 20:
                    await update.message.reply_text("Address seems invalid. Try again with /link_wallet.")
                    return
                crud.set_bnb_address(db, user, text)
                await update.message.reply_text(
                    f"Your BNB address was saved:\n{text}"
                )
                return

            elif state == STATE_AWAITING_TRANSFER_TARGET:
                if not text.startswith("@"):
                    await update.message.reply_text("Send a username starting with @username")
                    return
                context.user_data["transfer_target_username"] = text[1:]
                context.user_data["state"] = STATE_AWAITING_TRANSFER_AMOUNT
                await update.message.reply_text(
                    f"Great. Now type the SLH amount you want to transfer to {text}."
                )
                return

            elif state == STATE_AWAITING_TRANSFER_AMOUNT:
                context.user_data["state"] = None
                try:
                    amount = float(text.replace(",", ""))
                except ValueError:
                    await update.message.reply_text("Could not read amount. Try again with /transfer.")
                    return

                if amount <= 0:
                    await update.message.reply_text("Amount must be greater than zero.")
                    return

                target_username = context.user_data.get("transfer_target_username")
                if not target_username:
                    await update.message.reply_text("Target not found. Try again with /transfer.")
                    return

                receiver = (
                    db.query(models.User)
                    .filter(models.User.username == target_username)
                    .first()
                )
                if not receiver:
                    await update.message.reply_text(
                        "No user with that username in the system. "
                        "They must send /start once before receiving transfers."
                    )
                    return

                try:
                    tx = crud.internal_transfer(db, sender=user, receiver=receiver, amount_slh=amount)
                except ValueError:
                    await update.message.reply_text("Insufficient balance for this transfer.")
                    return

                await update.message.reply_text(
                    f"Transfer completed:\n"
                    f"{amount:.4f} SLH -> @{receiver.username or receiver.telegram_id}\n"
                    f"Transaction ID: {tx.id}"
                )
                return

            # Default
            await update.message.reply_text(
                "Command not recognized. Use /help to see available commands."
            )

        finally:
            db.close()


_bot_instance = InvestorWalletBot()


async def initialize_bot():
    await _bot_instance.initialize()


async def process_webhook(update_dict: dict):
    if not _bot_instance.application:
        logger.error("Application is not initialized")
        return
    update = Update.de_json(update_dict, _bot_instance.application.bot)
    await _bot_instance.application.process_update(update)
