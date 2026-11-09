"""The one door to Groq, the free online model that thinks for "Ask your shop" (plain HTTP, no extra library).

Used only for Ask, when GROQ_API_KEY is set and the owner hasn't turned it off in Settings. Groq never reads
the database: it receives the question, the conversation so far and the results of the read-only tools it
asked for (app/ask/data_tools), nothing else. Groq does not train on what it is sent.

Any failure raises GroqFailed with a reason the page can say in one line: "offline" (no internet or Groq
down), "daily_limit" (the free daily allowance is used up), "busy" (too many questions this minute), "error".
"""

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.config import GROQ_API_KEY, GROQ_MODEL

URL = "https://api.groq.com/openai/v1/chat/completions"
SECONDS = 25
# Groq's firewall refuses Python's default name ("Python-urllib", error 1010), so the app says its own.
USER_AGENT = "AutoStock-AI/1.0"
LONGEST = 1200  # word pieces (tokens) for one reply, its thinking included
LONGEST_WAIT = 20  # seconds waited in all for "too many this minute" refusals, then "busy"
# Groq's free limit in tokens a day (requests a day come in each reply). Both measured on 2026-11-08: the
# allowance ran out after about 200,000 tokens.
TOKENS_PER_DAY = {"openai/gpt-oss-120b": 200_000, "openai/gpt-oss-20b": 200_000, "qwen/qwen3.8-27b": 200_000}


class GroqFailed(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason


@dataclass
class Reply:
    message: dict  # {"content": ..., "tool_calls": [...]}
    tokens: int
    limits: dict = field(default_factory=dict)


# What Groq said about the allowance in its last reply: requests left today, out of how many.
last_limits: dict = {}


def is_ready() -> bool:
    """True when a Groq key is set."""
    return bool(GROQ_API_KEY)


def complete(messages: list[dict], tools: list[dict], model: str = GROQ_MODEL) -> Reply:
    """One step of the conversation: the model's reply, which may ask for tools. Raises GroqFailed."""
    if not GROQ_API_KEY:
        raise GroqFailed("offline", "No GROQ_API_KEY.")
    body = {"model": model, "messages": messages, "temperature": 0.2, "max_completion_tokens": LONGEST}
    if tools:
        body["tools"] = tools
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"  # thinking counts in the limits: low keeps answers quick and cheap
    waited = 0.0
    while True:
        try:
            return _sent(body)
        except urllib.error.HTTPError as error:
            failure, wait = _refusal(error)
            if failure.reason != "busy" or waited + wait > LONGEST_WAIT:
                raise failure from error
            time.sleep(wait)  # the page keeps showing "thinking" meanwhile
            waited += wait
        except (OSError, ValueError, KeyError, IndexError) as error:
            raise GroqFailed("offline" if isinstance(error, OSError) else "error", str(error)) from error


def _sent(body: dict) -> Reply:
    request = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}", "User-Agent": USER_AGENT,
    })
    with urllib.request.urlopen(request, timeout=SECONDS) as response:
        _remember_limits(response.headers)
        data = json.load(response)
    return Reply(data["choices"][0]["message"], int(data.get("usage", {}).get("total_tokens", 0)), dict(last_limits))


def _remember_limits(headers) -> None:
    left, per_day = headers.get("x-ratelimit-remaining-requests"), headers.get("x-ratelimit-limit-requests")
    if left and per_day and left.isdigit() and per_day.isdigit():
        last_limits.update(requests_left_today=int(left), requests_per_day=int(per_day), seen_at=time.time())


def _refusal(error: urllib.error.HTTPError) -> tuple[GroqFailed, float]:
    """Why Groq refused, and how long to wait if it's only "too many this minute"."""
    try:
        text = error.read().decode(errors="replace")
    except OSError:
        text = ""
    if error.code == 429:
        if re.search(r"per day|\(TPD\)|\(RPD\)", text):
            return GroqFailed("daily_limit", text[:300]), 0
        wait = max(1.0, float(error.headers.get("retry-after") or 5))
        return GroqFailed("busy", text[:300]), wait
    if error.code >= 500:
        return GroqFailed("offline", text[:300]), 0
    return GroqFailed("error", f"{error.code} {text[:300]}"), 0
