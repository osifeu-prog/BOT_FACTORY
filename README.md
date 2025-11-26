# SLH Manager – Investor Gateway + Minimal Wallet

This repo contains:

- SLH Investor Gateway Bot (Telegram) – for investors (100K ILS+)
- SLH Off-Chain Wallet – minimal wallet for SLH units
- FastAPI Service – `/health` endpoint and Telegram webhook

Designed to run on Railway (or any similar PaaS) with Postgres.

## Project structure

```text
slh_manager/
  app/
    core/
      config.py
    bot/
      investor_wallet_bot.py
    __init__.py
    main.py
    database.py
    models.py
    schemas.py
    crud.py
  requirements.txt
  README.md
  .env.example
  Dockerfile
```

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# create .env from .env.example or set env vars manually

uvicorn app.main:app --reload --port 8000
```

Telegram webhook URL:

`https://your-domain/webhook/telegram`
