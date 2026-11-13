"""Minimal Google Gemini client (REST, standard library only).

Why no SDK: one endpoint is all we use, and plain urllib keeps the dependency list short and
the HTTP call easy to replace with a fake in tests (see `services.ask(..., client=...)`).
"""

import json
import re
import urllib.error
import urllib.request

from django.conf import settings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL_NAME = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,63}$")


class AssistantUnavailable(Exception):
    """The AI service could not answer. The message is safe to show to the owner."""


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 25):
        self.api_key = api_key if api_key is not None else settings.ASSISTANT_API_KEY
        self.model = model or settings.ASSISTANT_MODEL
        self.timeout = timeout
        if not MODEL_NAME.match(self.model):
            raise AssistantUnavailable("ASSISTANT_MODEL is not a valid model name.")

    def generate(self, *, system: str, contents: list[dict], tools: list[dict]) -> dict:
        """One model turn. Returns the candidate's `content` ({"role": "model", "parts": [...]})."""
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": tools}],
            "generationConfig": {"temperature": 0.2},
        }
        request = urllib.request.Request(  # noqa: S310 - fixed https URL, model name validated
            ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise AssistantUnavailable(
                    "The free AI quota is used up for now. Try again in a little while."
                ) from exc
            detail = exc.read(2000).decode("utf-8", "replace") if exc.fp else ""
            if exc.code in (401, 403) or "API_KEY_INVALID" in detail or "API key" in detail:
                raise AssistantUnavailable(
                    "The AI service refused the API key. Check GEMINI_API_KEY."
                ) from exc
            if exc.code == 404:
                raise AssistantUnavailable(
                    "The AI model was not found. Check ASSISTANT_MODEL."
                ) from exc
            raise AssistantUnavailable("The AI service had a problem. Try again shortly.") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise AssistantUnavailable(
                "The AI service didn't answer in time. Try again shortly."
            ) from exc
        candidates = payload.get("candidates") or []
        content = candidates[0].get("content") if candidates else None
        if not content or not content.get("parts"):
            raise AssistantUnavailable("The AI couldn't answer that one. Try rephrasing it.")
        return content
