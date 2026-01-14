from __future__ import annotations

from app.routers.public_stats import router as public_stats_router
from app.routers.admin_accrual import router as admin_accrual_router

from app.routers.staking import router as staking_router
import os
import sys
import traceback
import asyncio
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import PlainTextResponse, JSONResponse

# -----------------------
# Helpers (safe env)
# -----------------------
def env_str(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def _client_ip(request: Request) -> str:
    # Minimal. If behind CF/proxy and you later want trust logic, add it here.
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"

# -----------------------
# App
# -----------------------
app = FastAPI()
app.include_router(public_stats_router)

app.include_router(admin_accrual_router)
app.include_router(staking_router)

# -----------------------
# Noise reducers
# -----------------------
@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nDisallow: /\n"

# -----------------------
# Health / Status (never depends on DB/Telegram)
# -----------------------
@app.get("/health")
async def health():
    # Don't touch DB/Telegram here. Just confirm process is alive.
    return {"ok": True}

@app.get("/status")
async def status():
    # Light visibility only; still no hard deps.
    # If you want later: expose bot/db readiness flags here.
    return {
        "ok": True,
        "bot_token_present": bool(env_str("BOT_TOKEN")),
        "database_url_present": bool(env_str("DATABASE_URL")),
    }

# -----------------------
# Debug Telegram (LAZY import)
# -----------------------


@app.get("/version")
async def version():
    return {
        "ok": True,
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT"),
        "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
        "railway_project": os.getenv("RAILWAY_PROJECT_NAME"),
        "git_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA"),
    }

@app.get("/debug/telegram")
async def debug_telegram():
    token_present = bool(env_str("BOT_TOKEN"))
    info = None
    err = None

    if token_present:
        try:
            # Lazy import - must never break startup if telegram libs mismatch
            from telegram import Bot  # type: ignore
            b = Bot(token=env_str("BOT_TOKEN"))
            # run blocking call in a thread
            info = await asyncio.to_thread(b.get_webhook_info)
        except Exception as e:
            err = str(e)

    return {
        "bot_token_present": token_present,
        "webhook_info": (info.to_dict() if info else None),
        "error": err,
    }

# -----------------------
# Telegram Webhook (LAZY import per-request)
# -----------------------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        update_dict: Any = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    try:
        # LAZY import so a broken bot file doesn't kill the server
        from app.bot.investor_wallet_bot import process_webhook  # type: ignore
        await process_webhook(update_dict)
    except Exception as e:
        # Never crash server; return ok to avoid Telegram retry storm, log for debugging
        print(f"process_webhook: {e}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"ok": True, "error": "process_webhook_failed"}, status_code=200)

    return {"ok": True}

# --- Basic endpoints to reduce 404 noise ---
try:
    from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
except Exception:  # pragma: no cover
    HTMLResponse = JSONResponse = Response = RedirectResponse = None  # type: ignore

# Root: show a tiny landing (or redirect to /docs if enabled)
@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import HTMLResponse

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>BOT_FACTORY</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:0; padding:24px; background:#0b0f19; color:#e8eefc; }
    .card { max-width: 980px; margin: 0 auto; border:1px solid rgba(255,255,255,.12); border-radius: 16px; padding: 18px; background: rgba(255,255,255,.04); }
    a { color:#e8eefc; }
    .btn { display:inline-block; margin-right:10px; margin-top:10px; padding:10px 14px; border-radius: 12px; text-decoration:none; background:#e8eefc; color:#0b0f19; font-weight:800; }
    .ghost { background: transparent; border:1px solid rgba(255,255,255,.18); color:#e8eefc; }
    code { background: rgba(255,255,255,.06); padding:2px 6px; border-radius: 8px; border:1px solid rgba(255,255,255,.12); }
  </style>
</head>
<body>
  <div class="card">
    <h1 style="margin:0 0 6px 0;">BOT_FACTORY</h1>
    <div style="opacity:.85">Landing page (no redirect). Live endpoints:</div>

    <div>
      <a class="btn" href="/docs">API Docs</a>
      <a class="btn ghost" href="/stats">Stats</a>
      <a class="btn ghost" href="/ready">Ready</a>
      <a class="btn ghost" href="/health">Health</a>
      <a class="btn ghost" href="/version">Build</a>
    </div>

    <p style="opacity:.75; margin-top:14px;">
      Tip: <code>GET /</code> returns HTML. We also implement <code>HEAD /</code> so <code>curl -I /</code> returns 200.
    </p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)

@app.head("/", include_in_schema=False)
def root_head():
    from starlette.responses import Response
    return Response(status_code=200)
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    if Response is not None:
        return Response(status_code=204)
    return {"ok": True}

# Some scanners/bots hit these; return helpful JSON instead of 404
@app.get("/getInfo", include_in_schema=False)
def get_info():
    if JSONResponse is not None:
        return JSONResponse({"ok": True, "service": "BOT_FACTORY", "endpoints": ["/health", "/webhook/telegram", "/docs"]})
    return {"ok": True}

@app.get("/getWebhookInfo", include_in_schema=False)
def get_webhook_info_hint():
    # NOTE: Telegram getWebhookInfo is on api.telegram.org; this is just a local hint endpoint.
    if JSONResponse is not None:
        return JSONResponse({"ok": True, "hint": "Use Telegram API getWebhookInfo via https://api.telegram.org/bot<TOKEN>/getWebhookInfo"})
    return {"ok": True}
from app.routers.staking import router as staking_router






@app.get("/routes/admin")
async def routes_admin():
    # helps verify router wiring in production
    out = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if "/admin" in path:
            out.append(path)
    out.sort()
    return {"ok": True, "admin_routes": out, "count": len(out)}
@app.get("/ready")
def ready():
    from sqlalchemy import create_engine, text
    from starlette.responses import JSONResponse

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        return JSONResponse({"ok": False, "ready": False, "reason": "DATABASE_URL_missing"}, status_code=503)
    try:
        e = create_engine(db, pool_pre_ping=True)
        with e.begin() as c:
            c.execute(text("select 1"))
        return {"ok": True, "ready": True}
    except Exception as ex:
        return JSONResponse({"ok": False, "ready": False, "reason": str(ex)}, status_code=503)



@app.head("/", include_in_schema=False)
def root_head():
    from starlette.responses import Response
    return Response(status_code=200)
