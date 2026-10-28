"""The one door to the optional cloud writer: Groq's free tier, plain HTTP, no extra library.

Used only when the shop owner turned it on in Settings and GROQ_API_KEY is set. It only ever receives
the labeled facts of one answer and writes sentences from them; it never reads the database and never
decides anything. Groq does not train on what it is sent. Any failure (no internet, the daily free
limit reached, a slow or broken reply) raises WriterFailed, and the app writes the answer itself.
"""

import json
import urllib.request
from collections.abc import Iterator

from app.config import GROQ_API_KEY, GROQ_MODEL

URL = "https://api.groq.com/openai/v1/chat/completions"
SECONDS = 20
# Groq's firewall refuses Python's default name ("Python-urllib", error 1010), so the app says its own.
USER_AGENT = "AutoStock-AI/1.0"
# gpt-oss "thinks" before writing; low effort keeps it quick, and the thinking counts in this limit.
LONGEST = 1500


class WriterFailed(Exception):
    """Groq could not be reached, refused (limit reached) or sent something unreadable."""


def is_ready() -> bool:
    """True when a Groq key is set, so the owner may turn the cloud writer on."""
    return bool(GROQ_API_KEY)


def chat(messages: list[dict]) -> Iterator[dict]:
    """The reply as it is written, in {"text": "..."} pieces. Raises WriterFailed if anything goes wrong."""
    if not GROQ_API_KEY:
        raise WriterFailed("No GROQ_API_KEY.")
    body = {
        "model": GROQ_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.2,
        "max_completion_tokens": LONGEST,
        "reasoning_effort": "low",
        "include_reasoning": False,
    }
    request = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}", "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=SECONDS) as response:
            for line in response:
                data = line.decode().strip().removeprefix("data:").strip()
                if not data or data == "[DONE]":
                    continue
                choice = json.loads(data)["choices"][0]
                text = choice.get("delta", {}).get("content")
                if text:
                    yield {"text": text}
    except (OSError, ValueError, KeyError, IndexError, AttributeError) as error:
        raise WriterFailed(str(error)) from error
