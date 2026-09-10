"""Optional Langfuse tracing. The system runs identically without it."""
from __future__ import annotations

import functools

from screening.config import Secrets

_client = None
_enabled = False

try:
    s = Secrets()
    if s.langfuse_enabled:
        from langfuse import Langfuse
        _client = Langfuse(public_key=s.langfuse_public_key,
                           secret_key=s.langfuse_secret_key, host=s.langfuse_host)
        _enabled = True
except Exception:
    _client, _enabled = None, False


def enabled() -> bool:
    return _enabled


def trace_node(name: str):
    """No-op decorator when Langfuse is not configured."""
    def deco(fn):
        if not _enabled:
            return fn

        @functools.wraps(fn)
        def wrapper(*a, **kw):
            span = _client.trace(name=name)
            try:
                out = fn(*a, **kw)
                span.update(output={"ok": True})
                return out
            except Exception as e:
                span.update(output={"ok": False, "error": str(e)[:300]})
                raise
        return wrapper
    return deco


def flush() -> None:
    if _enabled and _client:
        try:
            _client.flush()
        except Exception:
            pass
