from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from busscope import ai_providers
from busscope.ai_assistant import ProviderError
from busscope.ai_keystore import KeyringKeyStore
from busscope.ai_providers import (
    AnthropicProvider,
    GoogleProvider,
    OpenAiCompatibleProvider,
    _default_opener,
    build_provider,
)

SECRET = "sk-ant-THIS-MUST-NEVER-LEAK-0123456789"  # noqa: S105 - fake key, leak sentinel


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class RecordingOpener:
    def __init__(self, reply: object = None, error: BaseException | None = None) -> None:
        self.reply = reply
        self.error = error
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        raw = self.reply if isinstance(self.reply, bytes) else json.dumps(self.reply).encode()
        return FakeResponse(raw)

    def body(self) -> dict[str, object]:
        data = self.requests[0].data
        assert isinstance(data, bytes)
        loaded = json.loads(data)
        assert isinstance(loaded, dict)
        return loaded


def http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "Reason", Message(), io.BytesIO(body))


def test_anthropic_request_shape_and_answer() -> None:
    opener = RecordingOpener({"content": [{"type": "thinking"}, {"type": "text", "text": "A"}]})
    answer = AnthropicProvider("https://api.anthropic.com/", opener).complete(
        "sys", "prompt", "claude-opus-5-5", SECRET
    )
    request = opener.requests[0]
    assert answer == "A"
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.get_header("X-api-key") == SECRET
    assert request.get_header("Anthropic-version") == "2023-06-01"
    assert opener.body()["system"] == "sys"
    assert opener.timeouts == [60.0]


@pytest.mark.parametrize("reply", [{"content": []}, {"content": "x"}, ["x"]])
def test_anthropic_without_text_is_an_error(reply: object) -> None:
    with pytest.raises(ProviderError):
        AnthropicProvider("https://a", RecordingOpener(reply)).complete("s", "p", "m", SECRET)


def test_openai_compatible_request_shape_with_and_without_key() -> None:
    reply = {"choices": [{"message": {"content": "B"}}]}
    opener = RecordingOpener(reply)
    assert (
        OpenAiCompatibleProvider("https://api.openai.com/v1", opener).complete(
            "sys", "p", "gpt", "sk-x"
        )
        == "B"
    )
    assert opener.requests[0].full_url == "https://api.openai.com/v1/chat/completions"
    assert opener.requests[0].get_header("Authorization") == "Bearer sk-x"
    assert opener.body()["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "p"},
    ]
    local = RecordingOpener(reply)
    OpenAiCompatibleProvider("http://localhost:11434/v1", local).complete("s", "p", "m", None)
    assert local.requests[0].get_header("Authorization") is None


def test_google_request_shape() -> None:
    opener = RecordingOpener({"candidates": [{"content": {"parts": [{"text": "C"}]}}]})
    answer = GoogleProvider("https://g/v1beta", opener).complete("s", "p", "gem/../x?a", "AIzaK")
    assert answer == "C"
    assert opener.requests[0].full_url == "https://g/v1beta/models/gem%2F..%2Fx%3Fa:generateContent"
    assert opener.requests[0].get_header("X-goog-api-key") == "AIzaK"


@pytest.mark.parametrize("reply", [{}, {"choices": []}, {"choices": [{"message": {"content": 3}}]}])
def test_unexpected_reply_format(reply: object) -> None:
    with pytest.raises(ProviderError, match="Unexpected"):
        OpenAiCompatibleProvider("https://o", RecordingOpener(reply)).complete("s", "p", "m", "k")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            http_error(401, b'{"error": {"message": "invalid x-api-key"}}'),
            "HTTP 401: invalid x-api-key",
        ),
        (http_error(404, b'{"error": "model not found"}'), "HTTP 404: model not found"),
        (http_error(500, b"<html>"), "HTTP 500: Reason"),
        (http_error(502, b"[1]"), "HTTP 502: Reason"),
        (urllib.error.URLError("refused"), "Cannot reach the provider: refused"),
        (TimeoutError(), "did not answer in time"),
        (ConnectionResetError(), "Connection error: ConnectionResetError"),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), "invalid reply"),
    ],
)
def test_transport_errors_are_key_free(error: BaseException, expected: str) -> None:
    with pytest.raises(ProviderError, match=expected) as caught:
        AnthropicProvider("https://a", RecordingOpener(error=error)).complete("s", "p", "m", SECRET)
    assert SECRET not in str(caught.value)
    assert caught.value.__cause__ is None


def test_invalid_json_reply() -> None:
    with pytest.raises(ProviderError, match="invalid reply"):
        AnthropicProvider("https://a", RecordingOpener(b"not json")).complete("s", "p", "m", "k")


@pytest.mark.parametrize(
    ("provider", "reply", "expected"),
    [
        (
            AnthropicProvider,
            {"content": [{"type": "text", "text": "A"}], "stop_reason": "max_tokens"},
            "A\n\n[answer truncated]",
        ),
        (
            AnthropicProvider,
            {"content": [{"type": "text", "text": "A"}], "stop_reason": "end_turn"},
            "A",
        ),
        (
            OpenAiCompatibleProvider,
            {"choices": [{"message": {"content": "B"}, "finish_reason": "length"}]},
            "B\n\n[answer truncated]",
        ),
        (
            OpenAiCompatibleProvider,
            {"choices": [{"message": {"content": "B"}, "finish_reason": "stop"}]},
            "B",
        ),
        (
            GoogleProvider,
            {"candidates": [{"content": {"parts": [{"text": "C"}]}, "finishReason": "MAX_TOKENS"}]},
            "C\n\n[answer truncated]",
        ),
        (
            GoogleProvider,
            {"candidates": [{"content": {"parts": [{"text": "C"}]}, "finishReason": "STOP"}]},
            "C",
        ),
    ],
)
def test_truncated_answers_are_flagged(provider: type, reply: object, expected: str) -> None:
    assert provider("https://x", RecordingOpener(reply)).complete("s", "p", "m", "k") == expected


@pytest.mark.parametrize(
    ("provider", "reply"),
    [
        (AnthropicProvider, {"content": [], "stop_reason": "refusal"}),
        (GoogleProvider, {"candidates": [{"finishReason": "SAFETY"}]}),
        (
            OpenAiCompatibleProvider,
            {"choices": [{"message": {"content": "partial"}, "finish_reason": "content_filter"}]},
        ),
    ],
)
def test_refusals_are_explicit(provider: type, reply: object) -> None:
    with pytest.raises(ProviderError, match="declined"):
        provider("https://x", RecordingOpener(reply)).complete("s", "p", "m", "k")


def test_scheme_check_is_case_insensitive() -> None:
    opener = RecordingOpener({"choices": [{"message": {"content": "ok"}}]})
    assert OpenAiCompatibleProvider("HTTPS://x/v1", opener).complete("s", "p", "m", "k") == "ok"
    local = RecordingOpener({"choices": [{"message": {"content": "ok"}}]})
    OpenAiCompatibleProvider("HTTP://localhost:1/v1", local).complete("s", "p", "m", None)


@pytest.mark.parametrize("endpoint", ["file:///etc", "http://192.168.1.5:11434/v1", "ftp://x"])
def test_unsafe_endpoint_is_refused_before_any_request(endpoint: str) -> None:
    opener = RecordingOpener({})
    with pytest.raises(ProviderError, match="https"):
        OpenAiCompatibleProvider(endpoint, opener).complete("s", "p", "m", None)
    assert opener.requests == []


@pytest.mark.parametrize(
    ("url", "local"), [("http://localhost:1/v1", True), ("https://api.example.com", False)]
)
def test_default_opener_picks_proxy_free_opener_for_local(
    monkeypatch: pytest.MonkeyPatch, url: str, local: bool
) -> None:
    seen: list[tuple[str, float]] = []

    def fake_open(name: str) -> Callable[..., FakeResponse]:
        def open_(request: urllib.request.Request, timeout: float) -> FakeResponse:
            seen.append((name, timeout))
            return FakeResponse(b"{}")

        return open_

    monkeypatch.setattr(ai_providers._LOCAL_OPENER, "open", fake_open("local"))
    monkeypatch.setattr(ai_providers._REMOTE_OPENER, "open", fake_open("remote"))
    assert _default_opener(urllib.request.Request(url), 5.0).read() == b"{}"  # noqa: S310 - fixed test URLs
    assert seen == [("local" if local else "remote", 5.0)]


def handlers(opener: urllib.request.OpenerDirector) -> list[urllib.request.BaseHandler]:
    found: list[urllib.request.BaseHandler] = vars(opener)["handlers"]
    return found


def test_local_opener_ignores_proxies_and_no_opener_follows_redirects() -> None:
    for opener in (ai_providers._LOCAL_OPENER, ai_providers._REMOTE_OPENER):
        redirects = [
            h for h in handlers(opener) if isinstance(h, urllib.request.HTTPRedirectHandler)
        ]
        assert redirects and all(isinstance(h, ai_providers._NoRedirect) for h in redirects)
    ai_providers._NoRedirect().redirect_request()  # returns None: the redirect is refused
    # An empty ProxyHandler registers no proxy routes, and it replaces the env-reading default.
    proxied = [
        h
        for h in handlers(ai_providers._LOCAL_OPENER)
        if isinstance(h, urllib.request.ProxyHandler)
    ]
    assert proxied == []


@pytest.mark.parametrize(
    ("provider_id", "kind"),
    [
        ("anthropic", AnthropicProvider),
        ("google", GoogleProvider),
        ("openai", OpenAiCompatibleProvider),
        ("mistral", OpenAiCompatibleProvider),
        ("local", OpenAiCompatibleProvider),
    ],
)
def test_build_provider(provider_id: str, kind: type) -> None:
    assert isinstance(build_provider(provider_id, "https://x"), kind)


# --- KeyringKeyStore --------------------------------------------------------------


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # keyring ships no annotations here
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise PasswordDeleteError("absent")
        del self.store[(service, username)]


def test_keystore_round_trip_in_keyring_only() -> None:
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    store = KeyringKeyStore()
    assert store.get("anthropic") is None
    store.set("anthropic", SECRET)
    assert store.get("anthropic") == SECRET
    assert backend.store == {("busscope-ai", "anthropic"): SECRET}
    store.delete("anthropic")
    store.delete("anthropic")
    assert backend.store == {}


def test_keystore_uses_the_busscope_service_name() -> None:
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    KeyringKeyStore().set("openai", "k")
    assert list(backend.store) == [("busscope-ai", "openai")]


def test_keystore_failures_are_key_free_provider_errors() -> None:
    store = KeyringKeyStore()  # conftest installs the fail backend
    with pytest.raises(ProviderError, match="unavailable"):
        store.get("anthropic")
    with pytest.raises(ProviderError, match="Cannot store") as caught:
        store.set("anthropic", SECRET)
    assert SECRET not in str(caught.value)
    with pytest.raises(ProviderError, match="Cannot delete"):
        store.delete("anthropic")
