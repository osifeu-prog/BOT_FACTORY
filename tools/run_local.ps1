[CmdletBinding()]
param(
  [int]$Port = 8080,
  [switch]$NoBot,
  [switch]$Reload,
  [switch]$PatchMain,
  [switch]$Push
)

$ErrorActionPreference = "Stop"

# repo root = parent of tools\
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> Repo: $root" -ForegroundColor Cyan

# Ensure venv exists
if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "==> Creating venv (.venv)..." -ForegroundColor Cyan
  python -m venv .venv
}

# Activate venv
. .\.venv\Scripts\Activate.ps1

Write-Host "==> Python:" -ForegroundColor Cyan
python -V
python -c "import sys; print(sys.executable)"

Write-Host "==> Installing deps..." -ForegroundColor Cyan
python -m pip install -U pip | Out-Host
python -m pip install -U openai "python-telegram-bot>=22" fastapi uvicorn | Out-Host

Write-Host "==> Versions:" -ForegroundColor Cyan
python -m pip list | Select-String -Pattern "openai|python-telegram-bot|fastapi|uvicorn" | Out-Host

# Patch main.py (optional)
if ($PatchMain) {
  $mainPath = Join-Path $root "app\main.py"
  if (!(Test-Path $mainPath)) { throw "app\main.py not found: $mainPath" }

  Write-Host "==> Patching app\main.py (safe startup)..." -ForegroundColor Yellow

  $patched = @"
import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.database import init_db
from app.core.telegram_updates import ensure_telegram_updates_table, register_update_once
from app.core.ledger import ensure_ledger_tables
from app.bot.investor_wallet_bot import initialize_bot, process_webhook
from app.monitoring import run_selftest

BUILD_ID = os.getenv("BUILD_ID", "local-dev")
log = logging.getLogger("slhnet")
app = FastAPI(title="SLH Investor Gateway")


def _slh_is_private_update(payload: Dict[str, Any]) -> bool:
    try:
        msg = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
        )
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            return chat.get("type") == "private"

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = (m2.get("chat") or {}) if isinstance(m2, dict) else {}
            return chat.get("type") == "private"

        return True
    except Exception:
        return True


def _slh_chat_fingerprint(payload: Dict[str, Any]) -> Tuple[str, str]:
    try:
        msg = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
        )
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            return str(chat.get("type") or "?"), str(chat.get("id") or "?")

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = (m2.get("chat") or {}) if isinstance(m2, dict) else {}
            return str(chat.get("type") or "?"), str(chat.get("id") or "?")

        return "?", "?"
    except Exception:
        return "?", "?"


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _bot_token_looks_valid(token: str) -> bool:
    t = (token or "").strip()
    if len(t) < 35 or ":" not in t:
        return False
    left, right = t.split(":", 1)
    return left.isdigit() and len(right) >= 20


@app.on_event("startup")
async def startup_event():
    init_db()
    ensure_telegram_updates_table()
    ensure_ledger_tables()

    if _truthy(os.getenv("DISABLE_TELEGRAM_BOT")):
        log.warning("Telegram bot disabled via DISABLE_TELEGRAM_BOT=1 -> starting API only")
        return

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token or not _bot_token_looks_valid(bot_token):
        log.warning("BOT_TOKEN missing/invalid -> starting API only")
        return

    try:
        await initialize_bot()
        log.info("Telegram bot initialized successfully")
    except Exception:
        log.exception("Telegram bot initialization failed -> starting API only")


@app.get("/")
async def root():
    return {"message": "SLH Investor Gateway is running", "build_id": BUILD_ID}


@app.get("/health")
async def health():
    return {"status": "ok", "build_id": BUILD_ID}


@app.get("/__whoami")
async def whoami(request: Request):
    now = datetime.now(timezone.utc).isoformat()
    env_keys = [
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_NAME",
        "RAILWAY_GIT_REPO_NAME",
        "RAILWAY_GIT_BRANCH",
        "RAILWAY_GIT_COMMIT_SHA",
        "PORT",
    ]
    env = {k: os.getenv(k) for k in env_keys if os.getenv(k) is not None}
    return {
        "ok": True,
        "time_utc": now,
        "build_id": BUILD_ID,
        "env": env,
        "client": {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    }


@app.get("/ready")
async def ready():
    result = run_selftest(quick=True)
    return {"status": result.get("status"), "checks": result.get("checks")}


@app.get("/selftest")
async def selftest():
    return run_selftest(quick=False)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update_dict = await request.json()

    if not _slh_is_private_update(update_dict):
        chat_type, chat_id = _slh_chat_fingerprint(update_dict)
        update_id = str(update_dict.get("update_id") or "?")
        try:
            log.info(
                f"SLH SAFETY: ignored non-private update_id={update_id} chat_type={chat_type} chat_id={chat_id}"
            )
        except Exception:
            pass
        return JSONResponse(
            {"ok": True, "ignored": "non-private", "chat_type": chat_type, "chat_id": chat_id},
            status_code=status.HTTP_200_OK,
        )

    try:
        is_new = register_update_once(update_dict)
        if not is_new:
            return JSONResponse({"ok": True, "duplicate": True}, status_code=status.HTTP_200_OK)
    except Exception:
        pass

    await process_webhook(update_dict)
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)
"@
  [System.IO.File]::WriteAllText($mainPath, $patched, (New-Object System.Text.UTF8Encoding($false)))
  Write-Host "==> Patched $mainPath" -ForegroundColor Green
}

# Env for run
$env:PORT = "$Port"

# If DATABASE_URL is missing locally, default to sqlite (so server won't crash)
if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
  $env:DATABASE_URL = "sqlite+pysqlite:///./local.db"
  Write-Host "==> DATABASE_URL missing -> using sqlite local.db" -ForegroundColor Yellow
}
if ($NoBot) { $env:DISABLE_TELEGRAM_BOT = "1" }

Write-Host "==> Starting uvicorn..." -ForegroundColor Green
$reloadArg = ""
if ($Reload) { $reloadArg = "--reload" }

python -m uvicorn app.main:app --host 127.0.0.1 --port $Port $reloadArg

