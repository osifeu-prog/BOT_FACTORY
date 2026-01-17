from __future__ import annotations

import hmac
from app.routers.public_stats import router as public_stats_router
from app.routers.admin_accrual import router as admin_accrual_router

from app.routers.staking import router as staking_router
import os
import sys
import traceback
import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
app.include_router(investments_router)

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
    return {
"ok": True,
        "bot_token_present": bool(env_str("BOT_TOKEN")),
        "database_url_present": bool(env_str("DATABASE_URL")),
        "telegram_webhook_secret_present": bool(env_str("TELEGRAM_WEBHOOK_SECRET")),
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
    # --- Telegram webhook secret validation (optional) ---
    expected = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if expected:
        got = (request.headers.get("x-telegram-bot-api-secret-token") or "").strip()
        if (not got) or (not hmac.compare_digest(got, expected)):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
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
@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import HTMLResponse
    import html as _html
    import os

    # Pull stats via internal function (no network, no JS)
    stats = {}
    try:
        from app.routers.public_stats import stats as stats_fn  # type: ignore
        stats = stats_fn() or {}
    except Exception as ex:
        stats = {"ok": False, "error": str(ex), "db": {"connected": False}, "staking": {}}

    db_ok = bool((stats.get("db") or {}).get("connected"))
    staking = stats.get("staking") or {}

    def g(key: str, default="0"):
        v = staking.get(key, default)
        return _html.escape(str(v if v is not None else default))

    tvl = g("tvl_principal", "0")
    active = g("positions_active", "0")
    rewards = g("rewards_rows", "0")
    events = g("events_rows", "0")

    sha = _html.escape(str(stats.get("git_sha") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA") or ""))
    env = _html.escape(str(stats.get("env") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT_NAME") or ""))
    db_txt = "connected" if db_ok else "offline"

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>BOT_FACTORY</title>
  <style>
    :root {{
      --bg:#0b0f19; --fg:#e8eefc; --mut:#a7b0c6;
      --card: rgba(255,255,255,.05); --bd: rgba(255,255,255,.12);
    }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      margin:0; padding:24px; background:var(--bg); color:var(--fg);
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; }}
    .hero {{
      border:1px solid var(--bd);
      border-radius: 16px;
      padding: 18px;
      background: var(--card);
    }}
    .row {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; }}
    .pill {{
      font-size: 12px; padding: 4px 10px; border-radius: 999px;
      border:1px solid rgba(255,255,255,.18); color: var(--mut);
    }}
    .grid {{
      display:grid; grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px; margin-top: 14px;
    }}
    .card {{
      background: rgba(255,255,255,.03);
      border:1px solid rgba(255,255,255,.10);
      border-radius: 14px;
      padding: 12px;
    }}
    .k {{ opacity:.75; font-size: 12px; }}
    .v {{ font-size: 20px; font-weight: 900; margin-top: 4px; }}
    a.btn {{
      display:inline-block; margin-right:10px; margin-top:10px;
      padding:10px 14px; border-radius: 12px; text-decoration:none;
      background:#e8eefc; color:#0b0f19; font-weight:900;
    }}
    a.ghost {{
      background: transparent; color: var(--fg);
      border:1px solid rgba(255,255,255,.18);
    }}
    code {{
      background: rgba(255,255,255,.06);
      padding:2px 6px; border-radius: 8px;
      border:1px solid rgba(255,255,255,.12);
    }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 520px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="row">
        <h1 style="margin:0;">BOT_FACTORY</h1>
        <div class="pill">DB: {db_txt}  env: {env}  sha: {sha[:7]}</div>
      </div>

      <div class="grid">
        <div class="card"><div class="k">TVL</div><div class="v">{tvl}</div></div>
        <div class="card"><div class="k">Active</div><div class="v">{active}</div></div>
        <div class="card"><div class="k">Rewards Rows</div><div class="v">{rewards}</div></div>
        <div class="card"><div class="k">Events Rows</div><div class="v">{events}</div></div>
      </div>

      <div style="margin-top:10px; opacity:.85">
        <a class="btn" href="/docs">API Docs</a>
        <a class="btn ghost" href="/stats">Stats</a>
        <a class="btn ghost" href="/ready">Ready</a>
        <a class="btn ghost" href="/health">Health</a>
        <a class="btn ghost" href="/version">Build</a>
      </div>

      <p style="opacity:.75; margin-top:14px;">
        Tip: <code>GET /</code> returns HTML and <code>HEAD /</code> returns 200.
      </p>
    </div>
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
from app.routers.investments import router as investments_router






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


