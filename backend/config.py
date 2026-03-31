"""Application configuration for IDO SKILLS News."""

import os

from dotenv import load_dotenv

load_dotenv()


def normalize_database_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return "sqlite:///database.db"

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]

    return url


def parse_cors_origins(raw_value: str):
    value = (raw_value or "*").strip()
    if value == "*":
        return "*"
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DATABASE_URL = normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///database.db")
    )
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()
    APP_HTTP_TITLE = os.getenv("APP_HTTP_TITLE", "IDO-SKILLS-News").strip()
    APP_SITE_URL = os.getenv("APP_SITE_URL", "https://idoskillsnews.local").strip()
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME", "IDO SKILLS News Bot").strip()
    TELEGRAM_BOT_TIMEOUT = int(os.getenv("TELEGRAM_BOT_TIMEOUT", "30"))
    BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
    LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
    NEWS_THRESHOLD = int(os.getenv("NEWS_THRESHOLD", "6"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5000"))
    AUTH_TOKEN_MAX_AGE = int(os.getenv("AUTH_TOKEN_MAX_AGE", str(60 * 60 * 24 * 7)))
    AUTH_TOKEN_SALT = os.getenv("AUTH_TOKEN_SALT", "ido-skills-auth")
    CORS_ORIGINS = parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))

    MAX_NEWS_PER_USER = 20
    SOURCES = [
        "https://rss.lenta.ru/rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
    ]


config = Config()
