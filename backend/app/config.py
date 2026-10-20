"""Settings read from environment variables (see .env.example)."""

import os

DATABASE_URL = os.environ["DATABASE_URL"]

# The address people use to open the website. Requests that change data must come from it.
APP_URL = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")

# Cookies are only sent over HTTPS when the site runs on HTTPS (not on a local computer).
COOKIES_SECURE = APP_URL.startswith("https://")

# Optional local AI (Ollama). Empty or unreachable = "AI is off" and the app works without it.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
