import secrets
from decimal import Decimal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str | None = None
    DATABASE_URL: str | None = None
    SECRET_KEY: str = secrets.token_urlsafe(32)

    ADMIN_USER_ID: str | None = None
    WEBHOOK_URL: str | None = None

    COMMUNITY_WALLET_ADDRESS: str | None = None
    SLH_TOKEN_ADDRESS: str | None = None
    SLH_PRICE_NIS: Decimal | int | float = 444

    BSC_RPC_URL: str | None = None
    BSC_SCAN_BASE: str | None = "https://bscscan.com"

    BUY_BNB_URL: str | None = None
    STAKING_INFO_URL: str | None = None
    DOCS_URL: str | None = None

    SLH_TOKEN_DECIMALS: int = 18

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
