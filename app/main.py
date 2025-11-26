from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from app.core.config import settings
from app.database import engine, Base
from app.bot import initialize_bot, process_webhook

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Create DB tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SLH Manager - Investor Gateway")
    try:
        await initialize_bot()
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
    yield
    logger.info("Shutting down SLH Manager")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=settings.DOCS_URL,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "SLH Manager - Investor Gateway & Wallet",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "slh-manager",
        "time": datetime.utcnow().isoformat(),
    }


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    await process_webhook(data)
    return JSONResponse({"ok": True})
