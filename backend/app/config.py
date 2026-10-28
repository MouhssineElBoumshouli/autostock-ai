"""Settings read from environment variables (see .env.example)."""

import os

DATABASE_URL = os.environ["DATABASE_URL"]

# The address people use to open the website. Requests that change data must come from it.
APP_URL = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")

# Cookies are only sent over HTTPS when the site runs on HTTPS (not on a local computer).
COOKIES_SECURE = APP_URL.startswith("https://")

# Optional local AI (Ollama). Empty or unreachable = "AI is off" and the app works without it.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")

# Optional cloud writer (Groq, free tier): only used when the owner turns it on in Settings.
# Empty = the app writes every answer itself, and the setting can't be turned on.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
