from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.bot.investor_wallet_bot import initialize_bot, process_webhook

app = FastAPI(title="SLH Investor Gateway")

@app.on_event("startup")
async def startup_event():
    await initialize_bot()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    await process_webhook(data)
    return JSONResponse({"ok": True})
