"""Settings read from environment variables (see .env.example)."""

import os

DATABASE_URL = os.environ["DATABASE_URL"]

# "production" on a shop's computer (docker-compose.prod.yml): no developer pages (/api/docs).
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"

# Addresses that may change data besides the one a page was opened at (app/origin_check.py),
# separated by commas. The first is the main one. Only needed behind a proxy; https:// here makes
# login cookies HTTPS-only.
def read_addresses(text: str) -> list[str]:
    """'http://localhost:8080, http://PC-NAME:8080/' -> ['http://localhost:8080', 'http://pc-name:8080']"""
    return [url.strip().rstrip("/").lower() for url in text.split(",") if url.strip()]


APP_URLS = read_addresses(os.environ.get("APP_URL", "http://localhost:5173"))
APP_URL = APP_URLS[0]

# Cookies are only sent over HTTPS when the site runs on HTTPS (not on a local computer).
COOKIES_SECURE = all(url.startswith("https://") for url in APP_URLS)

# The shop's time zone: "today" is the shop's day, not the server's (a sale at 00:30 belongs to that day).
SHOP_TIMEZONE = os.environ.get("TZ", "Africa/Casablanca")

# Folder of the daily backups (docker-compose.prod.yml). Empty while developing: no backups then.
BACKUP_DIR = os.environ.get("BACKUP_DIR", "")

# Optional local AI (Ollama). Empty or unreachable = "AI is off" and the app works without it.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")

# Optional cloud writer (Groq, free tier): only used when the owner turns it on in Settings.
# Empty = the app writes every answer itself, and the setting can't be turned on.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# The built website (production image only). Empty while developing: Vite serves it then.
WEBSITE_DIR = os.environ.get("WEBSITE_DIR", "")
