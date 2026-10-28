"""The one door to the optional local language model (Ollama): free, runs on this computer.

Nothing here decides anything: callers get the model's JSON, check it themselves, and fall back
to their non-AI way when the answer is None (Ollama off, model missing, slow or broken answer).
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from app.config import OLLAMA_MODEL, OLLAMA_URL

CHECK_SECONDS = 1
ANSWER_SECONDS = 90  # the first question after a restart also loads the model onto the graphics card
CHAT_SECONDS = 120


class ModelFailed(Exception):
    """Ollama stopped answering or sent something unreadable in the middle of a chat."""


def is_on(model: str = OLLAMA_MODEL) -> bool:
    """True when Ollama answers and has the model downloaded."""
    if not OLLAMA_URL:
        return False
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=CHECK_SECONDS) as response:
            models = json.load(response).get("models", [])
    except (OSError, ValueError):
        return False
    return any(found.get("name") in (model, f"{model}:latest") for found in models)


def ask_json(instructions: str, text: str, schema: dict, model: str = OLLAMA_MODEL) -> object | None:
    """The model's answer as parsed JSON, shaped by `schema`, or None if anything goes wrong."""
    if not OLLAMA_URL:
        return None
    body = {
        "model": model,
        "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": text}],
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=ANSWER_SECONDS) as response:
            return json.loads(json.load(response)["message"]["content"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def chat(messages: list[dict], model: str = OLLAMA_MODEL, longest: int = 300) -> Iterator[dict]:
    """The model's reply as it is written, in {"text": "..."} pieces, at most `longest` word pieces
    (tokens). Raises ModelFailed if anything goes wrong."""
    if not OLLAMA_URL:
        raise ModelFailed("AI is off.")
    body = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,  # models that can "think out loud" first would make people wait much longer
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": longest},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=CHAT_SECONDS) as response:
            for line in response:
                message = json.loads(line).get("message", {})
                if message.get("content"):
                    yield {"text": message["content"]}
    except (OSError, ValueError, AttributeError) as error:
        raise ModelFailed(str(error)) from error
