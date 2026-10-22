"""HTTP adapters for the AI providers, using only the standard library (issue #83).

No vendor SDK: each adapter is one JSON POST. Error messages are built from the HTTP
status and the provider's error text, never from the request, so the key cannot leak.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.parse import quote, urlsplit

from busscope.ai_assistant import LlmProvider, ProviderError, endpoint_is_local

_TIMEOUT_SECONDS = 60.0
_MAX_TOKENS = 4096
_ANTHROPIC_VERSION = "2023-06-01"
_UNEXPECTED_REPLY = "Unexpected reply format from the provider"


class _Response(Protocol):
    """The slice of an HTTP response the adapters use."""

    def read(self) -> bytes:
        """Response body."""

    def __enter__(self) -> _Response:
        """Context manager entry."""

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""


Opener = Callable[[urllib.request.Request, float], _Response]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would replay the auth headers, possibly over cleartext."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        """Surface any redirect as an HTTPError instead of following it."""
        return None


# Local endpoints bypass environment proxies so "nothing leaves this PC" stays true.
_LOCAL_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))
_REMOTE_OPENER = urllib.request.build_opener(_NoRedirect)


def _default_opener(request: urllib.request.Request, timeout: float) -> _Response:
    """Production opener: no redirects, no proxy for loopback, explicit timeout."""
    opener = _LOCAL_OPENER if endpoint_is_local(request.full_url) else _REMOTE_OPENER
    response: _Response = opener.open(request, timeout=timeout)
    return response


def _post_json(
    opener: Opener, url: str, headers: Mapping[str, str], body: object, timeout: float
) -> object:
    """POST a JSON body and return the decoded JSON reply, or raise a key-free error."""
    # Cleartext HTTP only to this PC (local models); anything that leaves it must use TLS.
    scheme = urlsplit(url).scheme.lower()
    if not (scheme == "https" or (scheme == "http" and endpoint_is_local(url))):
        raise ProviderError("Endpoint must use https unless it is on this PC")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with opener(request, timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise ProviderError(f"HTTP {error.code}: {_error_text(error)}") from None
    except urllib.error.URLError as error:
        raise ProviderError(f"Cannot reach the provider: {error.reason}") from None
    except TimeoutError:
        raise ProviderError("The provider did not answer in time") from None
    except ValueError:  # malformed JSON or non-UTF-8 bytes
        raise ProviderError("The provider sent an invalid reply") from None
    except OSError as error:  # dropped connection, TLS failure while reading
        raise ProviderError(f"Connection error: {type(error).__name__}") from None


def _error_text(error: urllib.error.HTTPError) -> str:
    """Best-effort provider message; vendors put it under error.message."""
    try:
        payload = json.loads(error.read())
    except (OSError, ValueError):
        return error.reason or "request failed"
    if isinstance(payload, dict):
        inner = payload.get("error")
        if isinstance(inner, dict) and isinstance(inner.get("message"), str):
            return str(inner["message"])
        if isinstance(inner, str):
            return inner
    return error.reason or "request failed"


def _dig(payload: object, *path: str | int) -> str:
    """Walk a JSON path and return the text found there, or raise ProviderError."""
    node = payload
    for step in path:
        if isinstance(step, int) and isinstance(node, list) and len(node) > step:
            node = node[step]
        elif isinstance(step, str) and isinstance(node, dict) and step in node:
            node = node[step]
        else:
            raise ProviderError(_UNEXPECTED_REPLY)
    if not isinstance(node, str):
        raise ProviderError(_UNEXPECTED_REPLY)
    return node


def _peek(payload: object, *path: str | int) -> str | None:
    """Like _dig, but an absent or non-text value is just None (optional metadata)."""
    try:
        return _dig(payload, *path)
    except ProviderError:
        return None


_DECLINED = "The model declined to answer"
_GEMINI_COMPLETE = frozenset({"STOP", "MAX_TOKENS"})


def _mark_truncated(answer: str, truncated: bool) -> str:
    """Tell the operator when the model stopped at the output limit."""
    return f"{answer}\n\n[answer truncated]" if truncated else answer


class AnthropicProvider:
    """Claude Messages API."""

    def __init__(self, base_url: str, opener: Opener = _default_opener) -> None:
        """Bind the API root and the injectable HTTP opener."""
        self._base_url = base_url.rstrip("/")
        self._opener = opener

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        """Return the concatenated text blocks of the answer."""
        reply = _post_json(
            self._opener,
            f"{self._base_url}/v1/messages",
            {"x-api-key": key or "", "anthropic-version": _ANTHROPIC_VERSION},
            {
                "model": model,
                "max_tokens": _MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            _TIMEOUT_SECONDS,
        )
        blocks = reply.get("content") if isinstance(reply, dict) else None
        if not isinstance(blocks, list):
            raise ProviderError(_UNEXPECTED_REPLY)
        texts = [
            block["text"]
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        stop = _peek(reply, "stop_reason")
        if stop == "refusal":
            raise ProviderError(_DECLINED)
        if not texts:
            raise ProviderError("The provider returned no text answer")
        return _mark_truncated("".join(texts), stop == "max_tokens")


class OpenAiCompatibleProvider:
    """Chat Completions wire format: OpenAI, Mistral and local Ollama ``/v1``."""

    def __init__(self, base_url: str, opener: Opener = _default_opener) -> None:
        """Bind the API root (ending in /v1) and the injectable HTTP opener."""
        self._base_url = base_url.rstrip("/")
        self._opener = opener

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        """Return the first choice's message content."""
        headers = {"authorization": f"Bearer {key}"} if key else {}
        reply = _post_json(
            self._opener,
            f"{self._base_url}/chat/completions",
            headers,
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            _TIMEOUT_SECONDS,
        )
        finish = _peek(reply, "choices", 0, "finish_reason")
        # A filtered completion omits content: partial text must not pass as an answer.
        if finish == "content_filter":
            raise ProviderError(_DECLINED)
        answer = _dig(reply, "choices", 0, "message", "content")
        return _mark_truncated(answer, finish == "length")


class GoogleProvider:
    """Gemini generateContent API."""

    def __init__(self, base_url: str, opener: Opener = _default_opener) -> None:
        """Bind the API root and the injectable HTTP opener."""
        self._base_url = base_url.rstrip("/")
        self._opener = opener

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        """Return the first candidate's first text part."""
        reply = _post_json(
            self._opener,
            f"{self._base_url}/models/{quote(model, safe='')}:generateContent",
            {"x-goog-api-key": key or ""},
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            },
            _TIMEOUT_SECONDS,
        )
        finish = _peek(reply, "candidates", 0, "finishReason")
        # Any other reason (SAFETY, RECITATION, BLOCKLIST, SPII...) is a filter: partial
        # text must not pass as an answer.
        if finish is not None and finish not in _GEMINI_COMPLETE:
            raise ProviderError(_DECLINED)
        answer = _dig(reply, "candidates", 0, "content", "parts", 0, "text")
        return _mark_truncated(answer, finish == "MAX_TOKENS")


def build_provider(
    provider_id: str, endpoint: str, opener: Opener = _default_opener
) -> LlmProvider:
    """Return the adapter for a provider id at the given endpoint."""
    if provider_id == "anthropic":
        return AnthropicProvider(endpoint, opener)
    if provider_id == "google":
        return GoogleProvider(endpoint, opener)
    return OpenAiCompatibleProvider(endpoint, opener)
