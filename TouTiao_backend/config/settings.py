import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    database_url = os.getenv(
        "DATABASE_URL",
        "mysql+aiomysql://root:YOUR_PASSWORD@localhost:3306/news_app?charset=utf8mb4",
    )
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    news_year = int(os.getenv("NEWS_YEAR", "2026"))
    news_sync_interval_minutes = int(os.getenv("NEWS_SYNC_INTERVAL_MINUTES", "360"))
    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]
    avatar_dir = BASE_DIR / "uploads" / "avatars"
    news_image_dir = BASE_DIR / "uploads" / "news"


settings = Settings()
