from __future__ import annotations

import pytest

from busscope.ai_assistant import (
    PROVIDERS,
    SYSTEM_PROMPT,
    DiagnosisRequest,
    DiagnosisService,
    ProviderError,
    RedactionOptions,
    Redactor,
    endpoint_is_local,
    provider_by_id,
)
from busscope.analysis import CapturedFrame
from busscope.protocol import CanFrame, ProtocolDecoder


def captured(arbitration_id: int, data: bytes, at: float, error: bool = False) -> CapturedFrame:
    frame = CanFrame(
        arbitration_id, data, is_extended_id=arbitration_id > 0x7FF, is_error_frame=error
    )
    return CapturedFrame(at, ProtocolDecoder().decode(frame))


def infypower_id(command: int, destination: int, source: int) -> int:
    return (command << 16) | (destination << 8) | source | (0x0A << 22)


class FakeKeys:
    def __init__(self, keys: dict[str, str] | None = None) -> None:
        self.keys = dict(keys or {})

    def get(self, provider_id: str) -> str | None:
        return self.keys.get(provider_id)

    def set(self, provider_id: str, key: str) -> None:
        self.keys[provider_id] = key

    def delete(self, provider_id: str) -> None:
        self.keys.pop(provider_id, None)


class FakeProvider:
    def __init__(self, answer: str = "answer") -> None:
        self.answer = answer
        self.calls: list[tuple[str, str, str, str | None]] = []

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        self.calls.append((system, prompt, model, key))
        return self.answer


# --- ProviderSpec -----------------------------------------------------------------


def test_registry_has_cloud_and_local_providers_with_claude_default() -> None:
    assert [spec.id for spec in PROVIDERS] == ["anthropic", "openai", "mistral", "google", "local"]
    assert provider_by_id("anthropic").default_model == "claude-opus-5-5"
    assert not provider_by_id("local").needs_key


def test_unknown_provider_raises() -> None:
    with pytest.raises(KeyError):
        provider_by_id("nope")


@pytest.mark.parametrize(
    ("provider_id", "key", "valid"),
    [
        ("anthropic", "sk-ant-" + "a" * 30, True),
        ("anthropic", "sk-" + "a" * 30, False),
        ("openai", "sk-proj-" + "A1_" * 10, True),
        ("mistral", "a1" * 16, True),
        ("mistral", "a1" * 15, False),
        ("google", "AIza" + "x" * 35, True),
        ("google", "AIza" + "x" * 10, False),
        ("anthropic", "  sk-ant-" + "a" * 30 + "  ", True),
        ("anthropic", "", False),
        ("local", "", True),
    ],
)
def test_key_format_check(provider_id: str, key: str, valid: bool) -> None:
    assert provider_by_id(provider_id).key_looks_valid(key) is valid


@pytest.mark.parametrize(
    ("endpoint", "local"),
    [
        ("http://localhost:11434/v1", True),
        ("http://127.0.0.1:8080/v1", True),
        ("http://[::1]:8080/v1", True),
        ("http://192.168.1.10:11434/v1", False),
        ("https://api.example.com/v1", False),
        ("not a url", False),
    ],
)
def test_endpoint_locality(endpoint: str, local: bool) -> None:
    assert endpoint_is_local(endpoint) is local


# --- Redactor ---------------------------------------------------------------------


def test_redaction_pseudonymises_addresses_consistently_and_keeps_broadcast() -> None:
    frames = [
        captured(infypower_id(0x03, 0x3F, 0x05), bytes(8), 100.0),
        captured(infypower_id(0x03, 0x05, 0x3F), bytes(8), 100.5),
        captured(infypower_id(0x03, 0xFF, 0x07), bytes(8), 101.0),
    ]
    text = Redactor().redact(frames, RedactionOptions())
    lines = text.splitlines()
    assert "dst=M1 src=M2" in lines[0]
    assert "dst=M2 src=M1" in lines[1]
    assert "dst=ALL src=M3" in lines[2]
    assert lines[0].startswith("t=+0.000s")
    assert lines[2].startswith("t=+1.000s")
    assert "0x3F" not in text and "0x05" not in text


def test_redaction_masks_undecoded_payloads_but_keeps_decoded_ones() -> None:
    frames = [
        captured(infypower_id(0x03, 0x01, 0x02), bytes(range(8)), 0.0),
        captured(infypower_id(0x0B, 0x01, 0x02), b"SERIAL01", 0.1),
        captured(0x123, b"\x01\x02", 0.2),
    ]
    lines = Redactor().redact(frames, RedactionOptions()).splitlines()
    assert "data=00 01 02 03 04 05 06 07" in lines[0]
    assert "<8 bytes masked>" in lines[1] and "SERIAL" not in lines[1]
    assert lines[2].endswith("id=<undecoded> data=<2 bytes masked>")
    assert "0x123" not in lines[2]


def test_redaction_can_be_disabled() -> None:
    frames = [captured(infypower_id(0x0B, 0x3F, 0x05), b"\xaa" * 8, 12.5)]
    options = RedactionOptions(
        anonymise_addresses=False, relative_time=False, mask_undecoded_payloads=False
    )
    line = Redactor().redact(frames, options)
    assert line.startswith("t=+12.500s")
    assert "dst=0x3F src=0x05" in line
    raw = Redactor().redact([captured(0x123, b"", 0.0)], options)
    assert "id=0x123" in raw
    assert "AA AA AA AA AA AA AA AA" in line


def test_redaction_keeps_only_most_recent_frames_and_flags_error_frames() -> None:
    frames = [captured(0x100 + index, b"", float(index)) for index in range(5)]
    frames.append(captured(0x200, b"", 9.0, error=True))
    lines = Redactor().redact(frames, RedactionOptions(max_frames=2)).splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("t=+0.000s id=<undecoded>")
    assert lines[1].endswith("ERROR-FRAME")


@pytest.mark.parametrize("max_frames", [0, -1])
def test_redaction_of_nothing(max_frames: int) -> None:
    assert Redactor().redact([], RedactionOptions()) == "(no frames)"
    frames = [captured(0x1, b"", 0.0)]
    assert Redactor().redact(frames, RedactionOptions(max_frames=max_frames)) == "(no frames)"


# --- DiagnosisService -------------------------------------------------------------


def test_prepare_builds_previewable_request() -> None:
    service = DiagnosisService({}, FakeKeys())
    request = service.prepare("  why?  ", [captured(0x1, b"", 0.0)], RedactionOptions())
    assert request.question == "why?"
    assert "Capture excerpt:\n" in request.prompt()
    assert request.prompt().endswith("Question:\nwhy?")


def test_prepare_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        DiagnosisService({}, FakeKeys()).prepare("   ", [], RedactionOptions())


def test_ask_passes_key_model_and_system_prompt() -> None:
    provider = FakeProvider("diagnosis")
    service = DiagnosisService({"anthropic": provider}, FakeKeys({"anthropic": "secret"}))
    answer = service.ask(DiagnosisRequest("q", "ctx"), provider_by_id("anthropic"), " m ")
    assert answer == "diagnosis"
    assert provider.calls == [
        (SYSTEM_PROMPT, "Capture excerpt:\nctx\n\nQuestion:\nq", "m", "secret")
    ]


def test_blank_model_falls_back_to_default_and_local_needs_no_key() -> None:
    provider = FakeProvider()
    service = DiagnosisService({"local": provider}, FakeKeys())
    service.test_connection(provider_by_id("local"), "")
    assert provider.calls[0][2:] == ("llama3.1", None)


def test_missing_key_is_reported_without_calling_provider() -> None:
    provider = FakeProvider()
    service = DiagnosisService({"openai": provider}, FakeKeys())
    with pytest.raises(ProviderError, match="No API key"):
        service.test_connection(provider_by_id("openai"), "gpt")
    assert provider.calls == []


def test_missing_adapter_is_reported() -> None:
    with pytest.raises(ProviderError, match="No adapter"):
        DiagnosisService({}, FakeKeys()).test_connection(provider_by_id("local"), "")
