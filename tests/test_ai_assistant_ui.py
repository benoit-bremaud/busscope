from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from busscope.ai_assistant import LlmProvider, ProviderError
from busscope.ai_assistant_ui import (
    AssistantWidget,
    _Job,
    _Signals,
    ask_confirmation,
    thread_pool_runner,
)
from busscope.analysis import CapturedFrame
from busscope.protocol import CanFrame, ProtocolDecoder

ANTHROPIC_KEY = "sk-ant-" + "k" * 30


@pytest.fixture
def qt_application() -> QApplication:
    application = QApplication.instance()
    if application is None or not isinstance(application, QApplication):
        application = QApplication([])
    return application


class FakeKeys:
    def __init__(self, keys: dict[str, str] | None = None, broken: bool = False) -> None:
        self.keys = dict(keys or {})
        self.broken = broken

    def get(self, provider_id: str) -> str | None:
        if self.broken:
            raise ProviderError("OS keyring unavailable")
        return self.keys.get(provider_id)

    def set(self, provider_id: str, key: str) -> None:
        if self.broken:
            raise ProviderError("Cannot store the key")
        self.keys[provider_id] = key

    def delete(self, provider_id: str) -> None:
        if self.broken:
            raise ProviderError("Cannot delete the key")
        self.keys.pop(provider_id, None)


class FakeProvider:
    def __init__(self, answer: str = "<b>Module M1 is fine</b>", fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str, model: str, key: str | None) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise ProviderError("HTTP 401: invalid key")
        return self.answer


class Harness:
    def __init__(self, tmp_path: Path, keys: FakeKeys, provider: FakeProvider) -> None:
        self.settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        self.frames: list[CapturedFrame] = []
        self.confirm_answer = True
        self.confirm_messages: list[str] = []
        self.endpoints: list[tuple[str, str]] = []
        self.provider = provider
        self.keys = keys

    def factory(self, provider_id: str, endpoint: str) -> LlmProvider:
        self.endpoints.append((provider_id, endpoint))
        return self.provider

    def confirm(self, parent: QWidget, message: str) -> bool:
        self.confirm_messages.append(message)
        return self.confirm_answer

    @staticmethod
    def runner(
        work: Callable[[], str], done: Callable[[str], None], error: Callable[[str], None]
    ) -> None:
        try:
            done(work())
        except ProviderError as failure:
            error(str(failure))

    def widget(self) -> AssistantWidget:
        return AssistantWidget(
            self.keys,
            self.factory,
            self.settings,
            lambda: self.frames,
            runner=self.runner,
            confirm=self.confirm,
        )


def frame() -> CapturedFrame:
    return CapturedFrame(1.0, ProtocolDecoder().decode(CanFrame(0x0283F05, bytes(8))))


def select(widget: AssistantWidget, provider_id: str) -> None:
    widget.provider_input.setCurrentIndex(widget.provider_input.findData(provider_id))


def test_cloud_provider_without_key_shows_only_guided_setup(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    widget = Harness(tmp_path, FakeKeys(), FakeProvider()).widget()
    assert widget.spec.id == "anthropic"
    assert widget.model_input.text() == "claude-opus-5-5"
    assert not widget.key_setup.isHidden()
    assert widget.endpoint_row.isHidden()
    url = "https://console.anthropic.com/settings/keys"
    assert widget.key_link.text() == (
        f'Create a key at <a href="{url}">{url}</a> — Starts with sk-ant-'
    )
    assert widget.test_button.isHidden()
    assert widget.diagnosis.isHidden()
    assert widget.forget_key_button.isHidden()
    assert widget.waiting_label.text() == "Set up the provider to ask questions."


def test_key_format_check_gates_saving_and_key_goes_to_keyring_only(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider())
    widget = harness.widget()
    widget.key_input.setText("wrong")
    assert not widget.save_key_button.isEnabled()
    assert widget.key_state.text() == "Unexpected format"
    widget.save_key()
    assert harness.keys.keys == {}
    widget.key_input.setText(ANTHROPIC_KEY)
    assert widget.save_key_button.isEnabled()
    widget.save_key_button.click()
    assert harness.keys.keys == {"anthropic": ANTHROPIC_KEY}
    assert widget.key_input.text() == ""
    assert widget.key_state.text() == "Key stored in the OS keyring"
    assert not widget.test_button.isHidden()
    harness.settings.sync()
    assert ANTHROPIC_KEY not in (tmp_path / "s.ini").read_text()
    widget.key_input.setText("x")
    widget.key_input.setText("")
    assert widget.key_state.text() == "Key stored in the OS keyring"


def test_forget_key_hides_ready_controls(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    widget = harness.widget()
    assert not widget.forget_key_button.isHidden()
    widget.forget_key_button.click()
    assert harness.keys.keys == {}
    assert widget.status_label.text() == "Key forgotten"
    assert widget.test_button.isHidden()


def test_keyring_failures_are_shown(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application
    widget = Harness(tmp_path, FakeKeys(broken=True), FakeProvider()).widget()
    assert widget.status_label.text() == "Error: OS keyring unavailable"
    widget.key_input.setText(ANTHROPIC_KEY)
    widget.save_key()
    assert widget.status_label.text() == "Error: Cannot store the key"
    assert widget.key_input.text() == ""
    widget.forget_key()
    assert widget.status_label.text() == "Error: Cannot delete the key"


def test_test_connection_reports_success_and_failure(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    widget = harness.widget()
    widget.test_button.click()
    assert widget.status_label.text() == "Connection OK"
    harness.provider.fail = True
    widget.test_connection()
    assert widget.status_label.text() == "Error: HTTP 401: invalid key"


def test_local_provider_shows_endpoint_and_needs_no_key(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider())
    widget = harness.widget()
    select(widget, "local")
    assert widget.key_setup.isHidden()
    assert not widget.endpoint_row.isHidden()
    assert not widget.test_button.isHidden()
    assert widget.diagnosis.isHidden()
    assert widget.waiting_label.text() == "Capture or load frames to ask questions."
    widget.endpoint_input.setText("http://127.0.0.1:9000/v1")
    widget.test_connection()
    assert harness.endpoints[-1] == ("local", "http://127.0.0.1:9000/v1")


def test_choices_persist_without_secrets(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider())
    widget = harness.widget()
    select(widget, "local")
    widget.model_input.setText("qwen")
    widget.endpoint_input.setText("http://localhost:1/v1")
    widget.model_input.editingFinished.emit()
    widget.endpoint_input.editingFinished.emit()
    again = harness.widget()
    assert again.spec.id == "local"
    assert again.model_input.text() == "qwen"
    assert again.endpoint_input.text() == "http://localhost:1/v1"


def test_full_diagnosis_flow_previews_confirms_and_renders_plain_text(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    harness.frames.append(frame())
    widget = harness.widget()
    assert not widget.diagnosis.isHidden()
    assert widget.send_button.isHidden()
    widget.question_input.setPlainText("Is the module healthy?")
    widget.prepare_button.click()
    assert not widget.send_button.isHidden()
    assert "dst=M1" in widget.preview.toPlainText()
    assert "leave this PC" in widget.destination_label.text()
    preview = widget.preview.toPlainText()
    assert preview.startswith("Model: claude-opus-5-5\n\nSystem:\n")
    widget.send_button.click()
    assert preview.endswith(harness.provider.prompts[0])
    assert "leave this PC" in harness.confirm_messages[0]
    assert widget.answer.toPlainText() == "<b>Module M1 is fine</b>"
    assert widget.status_label.text() == "Answer received"


def test_send_can_be_cancelled_and_errors_are_shown(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider(fail=True))
    harness.frames.append(frame())
    widget = harness.widget()
    select(widget, "local")
    widget.send()  # nothing prepared yet: no-op
    assert harness.confirm_messages == []
    widget.question_input.setPlainText("why?")
    widget.prepare()
    assert "nothing leaves it" in widget.destination_label.text()
    harness.confirm_answer = False
    widget.send()
    assert widget.status_label.text() == "Send cancelled"
    assert harness.provider.prompts == []
    harness.confirm_answer = True
    widget.send()
    assert widget.status_label.text() == "Error: HTTP 401: invalid key"
    assert widget.send_button.isEnabled()


def test_remote_local_endpoint_is_treated_as_leaving_the_pc(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider())
    harness.frames.append(frame())
    widget = harness.widget()
    select(widget, "local")
    widget.endpoint_input.setText("https://10.0.0.5:11434/v1")
    widget.question_input.setPlainText("why?")
    widget.prepare()
    assert widget.destination_label.text().startswith("Warning:")


def test_blank_question_is_refused(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    harness.frames.append(frame())
    widget = harness.widget()
    widget.prepare()
    assert widget.status_label.text() == "Error: Ask a question first"
    assert widget.send_button.isHidden()


def test_ask_confirmation_maps_dialog_answer(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    for answer, expected in (
        (QMessageBox.StandardButton.Yes, True),
        (QMessageBox.StandardButton.No, False),
    ):
        monkeypatch.setattr(QMessageBox, "question", lambda *_args, a=answer: a)
        assert ask_confirmation(QWidget(), "send?") is expected


def test_thread_pool_runner_delivers_result_and_error(qt_application: QApplication) -> None:
    results: list[str] = []
    thread_pool_runner(lambda: "ok", results.append, results.append)

    def failing() -> str:
        raise ProviderError("boom")

    thread_pool_runner(failing, results.append, results.append)
    QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(50):
        qt_application.processEvents()
        if len(results) == 2:
            break
    assert sorted(results) == ["boom", "ok"]


def test_job_emits_answer_or_key_free_error(qt_application: QApplication) -> None:
    del qt_application
    signals = _Signals()
    seen: list[str] = []
    signals.done.connect(lambda text: seen.append(f"done:{text}"))
    signals.failed.connect(lambda text: seen.append(f"failed:{text}"))

    def failing() -> str:
        raise ProviderError("boom")

    _Job(lambda: "ok", signals).run()
    _Job(failing, signals).run()
    assert seen == ["done:ok", "failed:boom"]


def test_editing_model_or_endpoint_invalidates_preview(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = Harness(tmp_path, FakeKeys(), FakeProvider())
    harness.frames.append(frame())
    widget = harness.widget()
    select(widget, "local")
    for field in (widget.model_input, widget.endpoint_input):
        widget.question_input.setPlainText("why?")
        widget.prepare()
        assert not widget.send_button.isHidden()
        field.textEdited.emit("x")
        assert widget.send_button.isHidden()
        widget.send()
        assert harness.confirm_messages == []


def test_keyring_is_read_once_per_provider(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application

    class CountingKeys(FakeKeys):
        reads = 0

        def get(self, provider_id: str) -> str | None:
            CountingKeys.reads += 1
            return super().get(provider_id)

    widget = Harness(tmp_path, CountingKeys(), FakeProvider()).widget()
    for _ in range(3):
        widget.refresh()
    assert CountingKeys.reads == 1


def test_job_reports_unexpected_errors_without_details(qt_application: QApplication) -> None:
    del qt_application
    signals = _Signals()
    seen: list[str] = []
    signals.failed.connect(seen.append)

    def crashing() -> str:
        raise RuntimeError("secret detail")

    _Job(crashing, signals).run()
    assert seen == ["Unexpected error while contacting the provider"]


class DeferredHarness(Harness):
    """Holds callbacks back, like a slow network, until the test releases them."""

    def __init__(self, tmp_path: Path, keys: FakeKeys, provider: FakeProvider) -> None:
        super().__init__(tmp_path, keys, provider)
        self.pending: list[Callable[[], None]] = []

    def runner(  # type: ignore[override]  # instance method: it records pending replies
        self, work: Callable[[], str], done: Callable[[str], None], error: Callable[[str], None]
    ) -> None:
        answer = work()
        self.pending.append(lambda: done(answer))

    def widget(self) -> AssistantWidget:
        return AssistantWidget(
            self.keys,
            self.factory,
            self.settings,
            lambda: self.frames,
            runner=self.runner,
            confirm=self.confirm,
        )


def test_late_replies_are_dropped_after_a_provider_change(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    keys = FakeKeys({"anthropic": ANTHROPIC_KEY})
    harness = DeferredHarness(tmp_path, keys, FakeProvider("late"))
    harness.frames.append(frame())
    widget = harness.widget()
    widget.test_connection()
    assert not widget.test_button.isEnabled()
    widget.question_input.setPlainText("why?")
    widget.prepare()
    widget.send()
    assert not widget.send_button.isEnabled()
    select(widget, "local")
    assert widget.test_button.isEnabled() and widget.send_button.isEnabled()
    for release in harness.pending:
        release()
    assert widget.answer.toPlainText() == ""
    assert widget.status_label.text() == ""


def test_test_button_is_reenabled_after_the_reply(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = DeferredHarness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    widget = harness.widget()
    widget.test_connection()
    harness.pending[0]()
    assert widget.test_button.isEnabled()
    assert widget.status_label.text() == "Connection OK"


def test_keyring_failure_is_cached_as_no_key(qt_application: QApplication, tmp_path: Path) -> None:
    del qt_application

    class BrokenCounting(FakeKeys):
        reads = 0

        def get(self, provider_id: str) -> str | None:
            BrokenCounting.reads += 1
            raise ProviderError("OS keyring unavailable")

    widget = Harness(tmp_path, BrokenCounting(), FakeProvider()).widget()
    for _ in range(3):
        widget.refresh()
    assert BrokenCounting.reads == 1
    assert widget.key_state.text() == "No key stored"


def test_editing_the_model_drops_a_reply_in_flight(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    harness = DeferredHarness(tmp_path, FakeKeys({"anthropic": ANTHROPIC_KEY}), FakeProvider())
    widget = harness.widget()
    widget.test_connection()
    widget.model_input.textEdited.emit("other-model")
    assert widget.test_button.isEnabled()
    harness.pending[0]()
    assert widget.status_label.text() == "Testing…"
