from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SLH Manager - Investor Gateway"
    VERSION: str = "1.0.0"

    DATABASE_URL: Optional[str] = None

    SECRET_KEY: str = "change-me"

    BOT_TOKEN: Optional[str] = None
    ADMIN_USER_ID: Optional[str] = None

    WEBHOOK_URL: Optional[str] = None

    DOCS_URL: str = "/docs"

    COMMUNITY_WALLET_ADDRESS: Optional[str] = None
    SLH_TOKEN_ADDRESS: Optional[str] = None
    SLH_PRICE_NIS: float = 444.0
    BSC_RPC_URL: Optional[str] = None
    BSC_SCAN_BASE: str = "https://bscscan.com"
    BUY_BNB_URL: Optional[str] = None
    STAKING_INFO_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
