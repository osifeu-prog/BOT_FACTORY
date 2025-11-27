from functools import lru_cache
from decimal import Decimal
from pydantic import BaseSettings


class Settings(BaseSettings):
    # --- Core ---
    BOT_TOKEN: str | None = None
    DATABASE_URL: str
    SECRET_KEY: str = "CHANGE_ME"

    # Admin
    ADMIN_USER_ID: str | None = None

    # Webhook base (ללא /webhook/telegram)
    WEBHOOK_URL: str | None = None

    # SLH / Wallet
    COMMUNITY_WALLET_ADDRESS: str | None = None
    SLH_TOKEN_ADDRESS: str | None = None

    # מחיר SLH בניס (יכול להגיע כמחרוזת / int מה־ENV)
    SLH_PRICE_NIS: Decimal | int | str = 444

    # כמה דצימלים יש ל־SLH בטוקן עצמו (לפי ההגדרה בקונטרקט)
    SLH_TOKEN_DECIMALS: int = 18

    # BSC / BscScan / קישורים חיצוניים
    BSC_RPC_URL: str | None = None
    BSC_SCAN_BASE: str = "https://bscscan.com"
    BUY_BNB_URL: str | None = None
    STAKING_INFO_URL: str | None = None

    # דף DOCS למשקיעים (GitHub Pages שלך)
    DOCS_URL: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
