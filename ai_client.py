"""Shared plumbing for both AI providers: timeouts, retries, rate limits, and strict JSON validation."""
import json
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..core.config import get_settings
from ..core.errors import ApiError
from ..core.logging import log

T = TypeVar("T", bound=BaseModel)


class ProviderError(ApiError):
    def __init__(self, provider: str, message: str):
        super().__init__("AI_PROVIDER_ERROR", message, 503)
        self.provider = provider


def parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in a code fence or a sentence. Recover the object if it is there."""
    # strict=False: raw line breaks inside strings (common in code answers) are accepted
    text = text.strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    # only a fence around the WHOLE reply is a wrapper; answers with code in them have fences of their own
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1], strict=False)
        raise


class JsonChatClient:
    """A chat-completions client that only ever returns validated, structured output."""

    provider = "ai"
    base_url = ""
    unavailable = "The AI service is temporarily unavailable."

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _post(self, path: str, payload: dict) -> dict:
        """One HTTP call with retry on rate limits, server errors and timeouts. Overridden in tests."""
        s = get_settings()
        if not self.configured:
            raise ProviderError(self.provider, f"{self.unavailable} (no API key configured)")
        last = "no response"
        for attempt in range(s.ai_max_retries + 1):
            try:
                r = httpx.post(f"{self.base_url}{path}", json=payload, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=s.ai_timeout_seconds)
                if r.status_code == 429 and r.headers.get("x-ratelimit-limit-req-minute") == "0":
                    # not a busy moment: this model is simply not included in the account's plan
                    log.warning("%s: the model for %s is not available on this plan", self.provider, path)
                    raise ProviderError(self.provider, self.unavailable)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                    # rate limits on free tiers clear within seconds: back off 2s, 5s, 10s unless told otherwise
                    wait = float(r.headers.get("retry-after", 0) or 0) or (2, 5, 10)[min(attempt, 2)]
                    time.sleep(min(wait, 15))
                    continue
                if r.status_code == 400 and "json_validate_failed" in r.text:
                    # the model's own JSON came out malformed (it happens on long replies): asking again usually works
                    last = "malformed JSON from the model"
                    continue
                if r.status_code >= 400:
                    # never log the request: it carries the key
                    log.error("%s rejected the request: HTTP %s %s", self.provider, r.status_code, r.text[:300])
                    raise ProviderError(self.provider, self.unavailable)
                return r.json()
            except httpx.HTTPError as e:
                last = type(e).__name__
                time.sleep(1.0 * (attempt + 1))
        log.error("%s failed after retries: %s", self.provider, last)
        raise ProviderError(self.provider, self.unavailable)

    def chat_json(self, prompt: str, schema: type[T], system: str = "You reply with a single JSON object and nothing else.") -> T:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        problem = ""
        for _ in range(2):  # one retry when the reply is not valid for the schema
            data = self._post("/chat/completions", payload)
            try:
                content = data["choices"][0]["message"]["content"]
                return schema.model_validate(parse_json(content))
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as e:
                problem = str(e)[:200]
                log.warning("%s returned output that does not fit %s: %s", self.provider, schema.__name__, problem)
        raise ProviderError(self.provider, f"{self.unavailable} (unusable response)")

    def chat_text(self, content) -> str:
        """A plain-text reply (used for transcribing images). `content` may be a string or a list of content parts."""
        data = self._post("/chat/completions", {"model": self.model, "messages": [{"role": "user", "content": content}], "temperature": 0})
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError):
            raise ProviderError(self.provider, f"{self.unavailable} (unusable response)")
