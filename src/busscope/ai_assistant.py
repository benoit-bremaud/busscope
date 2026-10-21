"""Qt-free, network-free domain of the AI diagnosis assistant (issue #83).

The assistant only reads a capture and returns text: it has no path to transmission.
Concrete HTTP and keyring adapters live in ``ai_providers`` and ``ai_keystore``.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from busscope.analysis import CapturedFrame

#: Infypower commands whose payload busscope decodes into measurements or state. Any other
#: payload is unknown to us and may carry identity data (serial numbers), so it is masked.
DECODED_COMMANDS = frozenset({0x01, 0x02, 0x03, 0x04, 0x06, 0x0A, 0x0C})
_BROADCAST_ADDRESS = 0xFF

SYSTEM_PROMPT = (
    "You are a CAN bus diagnosis assistant for EV-charger power modules (Infypower "
    "protocol, CAN 2.0B extended frames at 125 kbit/s). The operator gives you a "
    "listen-only capture excerpt and a question. Module addresses are pseudonymised "
    "(M1, M2...). Answer in plain text, state your uncertainty, and never suggest "
    "transmitting frames on a live charger bus."
)


class ProviderError(RuntimeError):
    """A provider call failed; the message is safe to show and never contains the key."""


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Static description of one AI provider, driving the guided setup panel."""

    id: str
    label: str
    default_model: str
    default_endpoint: str
    needs_key: bool = True
    key_url: str = ""
    key_hint: str = ""
    key_pattern: str = ""

    def key_looks_valid(self, key: str) -> bool:
        """Cheap local format check before any network call; keyless providers accept ''."""
        if not self.needs_key:
            return True
        return re.fullmatch(self.key_pattern, key.strip()) is not None


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="anthropic",
        label="Anthropic (Claude)",
        default_model="claude-opus-5-5",
        default_endpoint="https://api.anthropic.com",
        key_url="https://console.anthropic.com/settings/keys",
        key_hint="Starts with sk-ant-",
        key_pattern=r"sk-ant-[A-Za-z0-9_\-]{20,}",
    ),
    ProviderSpec(
        id="openai",
        label="OpenAI",
        default_model="gpt-5",
        default_endpoint="https://api.openai.com/v1",
        key_url="https://platform.openai.com/api-keys",
        key_hint="Starts with sk-",
        key_pattern=r"sk-[A-Za-z0-9_\-]{20,}",
    ),
    ProviderSpec(
        id="mistral",
        label="Mistral",
        default_model="mistral-large-latest",
        default_endpoint="https://api.mistral.ai/v1",
        key_url="https://console.mistral.ai/api-keys",
        key_hint="32 letters and digits",
        key_pattern=r"[A-Za-z0-9]{32}",
    ),
    ProviderSpec(
        id="google",
        label="Google (Gemini)",
        default_model="gemini-2.5-pro",
        default_endpoint="https://generativelanguage.googleapis.com/v1beta",
        key_url="https://aistudio.google.com/apikey",
        key_hint="Starts with AIza",
        key_pattern=r"AIza[A-Za-z0-9_\-]{35}",
    ),
    ProviderSpec(
        id="local",
        label="Local model (Ollama / OpenAI-compatible)",
        default_model="llama3.1",
        default_endpoint="http://localhost:11434/v1",
        needs_key=False,
    ),
)


def provider_by_id(provider_id: str) -> ProviderSpec:
    """Return the registered provider, raising KeyError for an unknown id."""
    for spec in PROVIDERS:
        if spec.id == provider_id:
            return spec
    raise KeyError(provider_id)


def endpoint_is_local(endpoint: str) -> bool:
    """True only when the endpoint host is a loopback address, so no data leaves the PC."""
    host = urlsplit(endpoint).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class LlmProvider(Protocol):
    """Port implemented by each vendor adapter."""

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        """Return the model's text answer or raise ProviderError."""


class KeyStore(Protocol):
    """Port to the OS secret store; keys never reach files, env or logs."""

    def get(self, provider_id: str) -> str | None:
        """Return the stored key, or None when absent."""

    def set(self, provider_id: str, key: str) -> None:
        """Store or replace the key."""

    def delete(self, provider_id: str) -> None:
        """Forget the key; no error when absent."""


@dataclass(frozen=True, slots=True)
class RedactionOptions:
    """What is removed from the capture before it is shown, then sent."""

    anonymise_addresses: bool = True
    relative_time: bool = True
    mask_undecoded_payloads: bool = True
    max_frames: int = 200


class Redactor:
    """Turn captured frames into a compact, pseudonymised text context."""

    def redact(self, frames: Iterable[CapturedFrame], options: RedactionOptions) -> str:
        """Render at most ``options.max_frames`` most recent frames, one per line."""
        selected = list(frames)[-options.max_frames :] if options.max_frames > 0 else []
        if not selected:
            return "(no frames)"
        origin = selected[0].timestamp_seconds if options.relative_time else 0.0
        aliases: dict[int, str] = {}
        return "\n".join(self._line(record, origin, options, aliases) for record in selected)

    def _line(
        self,
        record: CapturedFrame,
        origin: float,
        options: RedactionOptions,
        aliases: dict[int, str],
    ) -> str:
        """Render one frame; addresses go through the per-request alias table."""
        frame = record.result.frame
        identifier = record.result.identifier
        stamp = f"t={record.timestamp_seconds - origin:+.3f}s"
        if identifier is None:
            head = f"id=0x{frame.arbitration_id:X}"
            decoded = False
        else:
            address = self._address_namer(options, aliases)
            head = (
                f"cmd=0x{identifier.command_number:02X} dev={identifier.device_number} "
                f"err={identifier.error_code} "
                f"dst={address(identifier.destination_address)} "
                f"src={address(identifier.source_address)}"
            )
            decoded = identifier.command_number in DECODED_COMMANDS
        if options.mask_undecoded_payloads and not decoded:
            payload = f"<{len(frame.data)} bytes masked>"
        else:
            payload = frame.data.hex(" ").upper()
        flags = " ERROR-FRAME" if frame.is_error_frame else ""
        return f"{stamp} {head} data={payload}{flags}"

    @staticmethod
    def _address_namer(options: RedactionOptions, aliases: dict[int, str]) -> Callable[[int], str]:
        """Return the address formatter matching the options."""

        def name(address: int) -> str:
            """Broadcast stays readable; other addresses become stable aliases."""
            if address == _BROADCAST_ADDRESS:
                return "ALL"
            if not options.anonymise_addresses:
                return f"0x{address:02X}"
            return aliases.setdefault(address, f"M{len(aliases) + 1}")

        return name


@dataclass(frozen=True, slots=True)
class DiagnosisRequest:
    """Exactly what will be sent: shown to the operator before confirmation."""

    question: str
    context: str

    def prompt(self) -> str:
        """The user message sent to the provider."""
        return f"Capture excerpt:\n{self.context}\n\nQuestion:\n{self.question}"


class DiagnosisService:
    """Prepare, preview and send diagnosis questions through an injected provider."""

    def __init__(
        self,
        providers: Mapping[str, LlmProvider],
        keys: KeyStore,
        redactor: Redactor | None = None,
    ) -> None:
        """Keep the per-provider adapters and the key store behind their ports."""
        self._providers = providers
        self._keys = keys
        self._redactor = redactor or Redactor()

    def prepare(
        self, question: str, frames: Iterable[CapturedFrame], options: RedactionOptions
    ) -> DiagnosisRequest:
        """Build the request to preview; refuses an empty question."""
        if not question.strip():
            raise ValueError("Ask a question first")
        return DiagnosisRequest(question.strip(), self._redactor.redact(frames, options))

    def ask(self, request: DiagnosisRequest, spec: ProviderSpec, model: str) -> str:
        """Send a confirmed request and return the answer text."""
        return self._call(spec, model, request.prompt())

    def test_connection(self, spec: ProviderSpec, model: str) -> str:
        """Send a minimal request proving the key, endpoint and model work."""
        return self._call(spec, model, "Reply with the single word OK.")

    def _call(self, spec: ProviderSpec, model: str, prompt: str) -> str:
        """Resolve adapter and key, then call; the key never leaves this frame."""
        provider = self._providers.get(spec.id)
        if provider is None:
            raise ProviderError(f"No adapter for {spec.label}")
        key: str | None = None
        if spec.needs_key:
            key = self._keys.get(spec.id)
            if not key:
                raise ProviderError(f"No API key stored for {spec.label}")
        return provider.complete(SYSTEM_PROMPT, prompt, model.strip() or spec.default_model, key)
