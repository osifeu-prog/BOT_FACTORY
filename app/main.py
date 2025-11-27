import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.bot.investor_wallet_bot import initialize_bot, process_webhook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown lifecycle.
    כאן אנחנו מעלים את הבוט פעם אחת בזמן עליית השרת.
    """
    logger.info("Starting SLH Manager - Investor Gateway")
    await initialize_bot()
    logger.info("Telegram bot initialized from main.py")
    yield
    logger.info("Shutting down SLH Manager - Investor Gateway")


app = FastAPI(
    title="SLH Investor Gateway",
    version="0.1.0",
    # חשוב: אלה PATHS פנימיים, חייבים להתחיל ב-"/"
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "slh_investor_gateway"}


@app.get("/")
async def root():
    """
    דף בית פשוט – אפשר לשפר בעתיד להצגת לינק ל-DOCS למשקיעים.
    """
    msg = "SLH Investor Gateway API is running."
    if settings.DOCS_URL:
        msg += f" Investor docs: {settings.DOCS_URL}"
    return {"message": msg}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    נקודת Webhook לבוט המשקיעים.
    """
    data = await request.json()
    await process_webhook(data)
    return JSONResponse({"ok": True})
