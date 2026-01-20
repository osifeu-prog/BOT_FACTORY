from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    env: str = os.getenv("ENV", "development")

settings = Settings()
