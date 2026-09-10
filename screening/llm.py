"""Groq client: JSON output, repair retries, rate limiting, usage accounting.

Groq's free tier allows roughly 30 requests/minute and the system makes two
calls per CV, so a 40-CV batch WILL hit the limit. That is paced here rather
than left to fail, and the limiter is what makes the batch-isolation failure
case reproducible instead of hypothetical.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field

from groq import APIConnectionError, APIStatusError, Groq, RateLimitError

from screening.config import SETTINGS, Secrets


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def _is_daily_cap(err: Exception) -> bool:
    """Groq exposes the per-minute budget in headers but NOT the per-day one.
    The daily cap only appears in the 429 body, which is why a run can fail
    while every rate-limit header still looks healthy."""
    return "tokens per day" in str(err).lower() or "(tpd)" in str(err).lower()


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    retries: int = 0
    est_cost_usd: float = 0.0
    model_used: str = ""

    def add(self, other: "Usage") -> None:
        if other.model_used:
            self.model_used = other.model_used
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls
        self.retries += other.retries
        self.est_cost_usd = round(self.est_cost_usd + other.est_cost_usd, 6)


class _RateLimiter:
    """Paces on TOKENS per minute, not requests per minute.

    The first version limited requests (25/min) and a 12-case evaluation run
    failed with 10 of 12 rate-limited. The headers explain why:

        x-ratelimit-limit-requests: 1000    (per day - never the constraint)
        x-ratelimit-limit-tokens:   8000    (per MINUTE - the real ceiling)

    A CV costs roughly 2,500-5,000 tokens across two calls, so the true limit
    is about two CVs a minute. Limiting the wrong dimension meant the limiter
    happily let through requests that could not possibly fit in the budget.
    """

    def __init__(self, rpm: int, tpm: int):
        self.rpm = max(1, rpm)
        self.tpm = max(1000, tpm)
        self._events: list[tuple[float, int]] = []   # (when, tokens)
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        self._events = [(t, n) for t, n in self._events if now - t < 60]

    def acquire(self, estimated_tokens: int = 2000) -> float:
        """Block until this call fits inside both budgets."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.time()
                self._prune(now)
                used = sum(n for _, n in self._events)
                if (len(self._events) < self.rpm
                        and used + estimated_tokens <= self.tpm):
                    self._events.append((now, estimated_tokens))
                    return waited
                oldest = self._events[0][0] if self._events else now
                sleep_for = max(0.5, 60 - (now - oldest) + 0.2)
            time.sleep(sleep_for)
            waited += sleep_for

    def record_actual(self, estimated: int, actual: int) -> None:
        """Replace the estimate with what the call really cost."""
        with self._lock:
            for i in range(len(self._events) - 1, -1, -1):
                if self._events[i][1] == estimated:
                    self._events[i] = (self._events[i][0], actual)
                    return


_limiter = _RateLimiter(SETTINGS.get("requests_per_minute", 25),
                        SETTINGS.get("tokens_per_minute", 7000))


# gpt-oss-120b is a reasoning model: it emits well over a thousand reasoning
# tokens per call, and those count against the same per-minute budget. The first
# fix estimated input only, so it still reserved about half of what a call
# actually cost and kept tripping the limit.
EXPECTED_OUTPUT_TOKENS = 2000


def estimate_tokens(*texts: str) -> int:
    """Deliberately generous. Under-estimating costs a 429; over-estimating
    only costs a little throughput."""
    return int(sum(len(t) for t in texts) / 3.2) + 400 + EXPECTED_OUTPUT_TOKENS
_client: Groq | None = None


def client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=Secrets().groq_api_key)
    return _client


def _cost(model: str, inp: int, out: int) -> float:
    rates = SETTINGS.get("pricing", {}).get(model)
    if not rates:
        return 0.0
    return round(inp / 1e6 * rates["input"] + out / 1e6 * rates["output"], 6)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_json(system: str, user: str, *, model: str | None = None,
              max_retries: int | None = None, temperature: float = 0.0,
              validate=None, trace_name: str = "llm") -> tuple[dict, Usage]:
    """One JSON call with repair retries.

    `validate` is an optional callable that raises on a bad payload; its error
    text is fed back to the model as the repair instruction. Malformed output is
    retried because it is a transient formatting failure - unlike a fabricated
    quote, which is never retried (see verify.py).
    """
    model = model or SETTINGS["model"]
    max_retries = SETTINGS.get("max_repair_retries", 2) if max_retries is None else max_retries
    usage = Usage()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_error = ""

    estimate = estimate_tokens(system, user)
    for attempt in range(max_retries + 1):
        _limiter.acquire(estimate)
        try:
            resp = client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
        except RateLimitError as e:
            # A per-DAY cap cannot be waited out, so retrying is pointless.
            # Fall back to a model with its own separate daily budget instead.
            if _is_daily_cap(e):
                fallback = SETTINGS.get("fallback_model")
                if fallback and model != fallback:
                    model = fallback
                    usage.retries += 1
                    continue
                raise LLMError(
                    "DAILY_LIMIT_REACHED",
                    "Today's free usage allowance for this AI provider is used up "
                    "(200,000 tokens per day). Everything already screened is saved. "
                    "It resets in a few hours - or add a different model under "
                    "'fallback_model' in config.yaml.") from e

            wait = min(30, 5 * (attempt + 1))
            if attempt < max_retries:
                usage.retries += 1
                time.sleep(wait)
                continue
            raise LLMError("RATE_LIMITED",
                           "Hit the per-minute usage limit and the retries ran out. "
                           "Wait a minute and run again - completed candidates are "
                           "already saved.") from e
        except APIConnectionError as e:
            raise LLMError("NO_CONNECTION",
                           "Couldn't reach Groq. Check your internet connection "
                           "and try again.") from e
        except APIStatusError as e:
            if e.status_code in (401, 403):
                raise LLMError("BAD_API_KEY",
                               "Groq rejected the API key. Open .env and check "
                               "GROQ_API_KEY. Get a free key at "
                               "https://console.groq.com/keys") from e
            if e.status_code == 404:
                raise LLMError("BAD_MODEL",
                               f"The model '{model}' isn't available on your Groq "
                               f"account. Change 'model' in config.yaml.") from e
            raise LLMError("API_ERROR", f"Groq returned an error ({e.status_code}).") from e

        u = resp.usage
        _limiter.record_actual(estimate, u.total_tokens)
        usage.calls += 1
        usage.input_tokens += u.prompt_tokens
        usage.output_tokens += u.completion_tokens
        usage.est_cost_usd = round(
            usage.est_cost_usd + _cost(model, u.prompt_tokens, u.completion_tokens), 6)

        raw = _strip_fences(resp.choices[0].message.content or "")
        try:
            payload = json.loads(raw)
            if validate:
                validate(payload)
            usage.model_used = model
            return payload, usage
        except Exception as e:
            last_error = str(e)[:400]
            if attempt >= max_retries:
                break
            usage.retries += 1
            messages = messages[:2] + [
                {"role": "assistant", "content": raw[:2000]},
                {"role": "user", "content":
                    f"That response was rejected: {last_error}\n"
                    f"Return ONLY valid JSON matching the requested shape. "
                    f"No prose, no markdown fences."},
            ]

    raise LLMError("INVALID_OUTPUT",
                   f"The model returned output that couldn't be read after "
                   f"{max_retries + 1} attempts. Last problem: {last_error}")
