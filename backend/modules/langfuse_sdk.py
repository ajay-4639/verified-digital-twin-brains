"""Langfuse compatibility helpers for SDK v2 and v3.

This module normalizes imports and common operations across Langfuse versions:
- tracing decorator/context (`observe`, `langfuse_context`)
- client initialization (`get_client`)
- score logging (`log_score`)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _has_credentials() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _host() -> str:
    return os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"


class _NoopLangfuseContext:
    def update_current_trace(self, *args, **kwargs):
        return None

    def update_current_observation(self, *args, **kwargs):
        return None

    def get_current_trace_id(self):
        return None

    @property
    def current_trace_id(self):
        return None


_observe_impl = None
_get_client_impl = None
_propagate_impl = None
_langfuse_context_impl: Any = _NoopLangfuseContext()
_langfuse_mode = "none"


def _build_v2_client():
    from langfuse import Langfuse

    if not _has_credentials():
        return None
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=_host(),
    )


try:
    # Langfuse v3+ style imports.
    from langfuse import get_client as _get_client_v3
    from langfuse import observe as _observe_v3

    _observe_impl = _observe_v3
    _get_client_impl = _get_client_v3
    _langfuse_mode = "v3"

    try:
        from langfuse import propagate_attributes as _propagate_v3

        _propagate_impl = _propagate_v3
    except Exception:
        _propagate_impl = None

    class _V3LangfuseContext:
        def _client(self):
            return get_client()

        def update_current_trace(self, *args, **kwargs):
            client = self._client()
            if not client:
                return None
            updater = getattr(client, "update_current_trace", None)
            if callable(updater):
                return updater(*args, **kwargs)
            return None

        def update_current_observation(self, *args, **kwargs):
            client = self._client()
            if not client:
                return None
            updater = getattr(client, "update_current_observation", None)
            if callable(updater):
                return updater(*args, **kwargs)
            # v3 naming uses "span" terminology.
            span_updater = getattr(client, "update_current_span", None)
            if callable(span_updater):
                return span_updater(*args, **kwargs)
            return None

        def get_current_trace_id(self):
            client = self._client()
            if not client:
                return None
            getter = getattr(client, "get_current_trace_id", None)
            if callable(getter):
                return getter()
            return None

        @property
        def current_trace_id(self):
            return self.get_current_trace_id()

    _langfuse_context_impl = _V3LangfuseContext()
except Exception:
    try:
        # Langfuse v2 style imports.
        from langfuse.decorators import langfuse_context as _ctx_v2
        from langfuse.decorators import observe as _observe_v2

        _observe_impl = _observe_v2
        _langfuse_context_impl = _ctx_v2
        _langfuse_mode = "v2"

        try:
            from langfuse import get_client as _get_client_v2

            _get_client_impl = _get_client_v2
        except Exception:
            _get_client_impl = _build_v2_client
    except Exception:
        _observe_impl = None
        _get_client_impl = None
        _langfuse_context_impl = _NoopLangfuseContext()
        _langfuse_mode = "none"


def is_installed() -> bool:
    return _langfuse_mode in {"v2", "v3"}


def has_credentials() -> bool:
    return _has_credentials()


def is_enabled() -> bool:
    return is_installed() and has_credentials()


def observe(*args, **kwargs):
    if _observe_impl is None:
        def _decorator(func):
            return func

        return _decorator
    return _observe_impl(*args, **kwargs)


langfuse_context = _langfuse_context_impl


def get_client():
    # Avoid repeated auth errors from the SDK when env vars are missing.
    if _get_client_impl is None or not _has_credentials():
        return None
    try:
        return _get_client_impl()
    except Exception as e:
        logger.debug(f"Langfuse client initialization failed: {e}")
        return None


@contextmanager
def propagate_attributes(**kwargs):
    if callable(_propagate_impl):
        with _propagate_impl(**kwargs):
            yield
        return

    try:
        langfuse_context.update_current_trace(
            user_id=kwargs.get("user_id"),
            session_id=kwargs.get("session_id"),
            metadata=kwargs.get("metadata") or {},
        )
    except Exception:
        pass
    yield


def _score_payload(name: str, value: Any, comment: Optional[str], data_type: Optional[str]) -> dict:
    payload = {"name": name, "value": value}
    if comment is not None:
        payload["comment"] = comment
    if data_type is not None:
        payload["data_type"] = data_type
    return payload


def log_score(
    client: Any,
    *,
    name: str,
    value: Any,
    trace_id: Optional[str] = None,
    comment: Optional[str] = None,
    data_type: Optional[str] = None,
) -> bool:
    """Log a score on either v2 or v3 clients/trace objects."""
    if client is None:
        return False

    payload = _score_payload(name=name, value=value, comment=comment, data_type=data_type)

    # v3 client API.
    create_score = getattr(client, "create_score", None)
    if callable(create_score):
        try:
            if trace_id:
                create_score(trace_id=trace_id, **payload)
            else:
                create_score(**payload)
            return True
        except Exception:
            pass

    # v2 client / trace API.
    score = getattr(client, "score", None)
    if callable(score):
        try:
            if trace_id:
                score(trace_id=trace_id, **payload)
            else:
                score(**payload)
            return True
        except Exception:
            pass

    return False


def flush_client(client: Any) -> None:
    if client is None:
        return
    flush = getattr(client, "flush", None)
    if callable(flush):
        try:
            flush()
        except Exception:
            pass


def runtime_status() -> dict:
    """Return non-sensitive runtime diagnostics for Langfuse integration."""
    client = get_client()
    return {
        "mode": _langfuse_mode,
        "installed": is_installed(),
        "credentials_configured": has_credentials(),
        "enabled": is_enabled(),
        "host": _host(),
        "client_ready": bool(client),
    }


if _langfuse_mode == "none":
    logger.warning("Langfuse SDK unavailable - tracing disabled")
elif not _has_credentials():
    logger.warning(
        "Langfuse SDK loaded (mode=%s) but credentials are missing; tracing export disabled",
        _langfuse_mode,
    )
else:
    logger.info("Langfuse SDK ready (mode=%s, host=%s)", _langfuse_mode, _host())
