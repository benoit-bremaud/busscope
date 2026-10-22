"""PySide6 panel of the AI diagnosis assistant (issue #83).

Progressive disclosure: provider choice first; key setup only for cloud providers; the
question area only once the provider is ready and a capture exists; the send button only
after a preview. Every send is confirmed. Answers are rendered as plain text.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, QRunnable, QSettings, QSignalBlocker, Qt, QThreadPool, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from busscope.ai_assistant import (
    PROVIDERS,
    SYSTEM_PROMPT,
    DiagnosisRequest,
    DiagnosisService,
    KeyStore,
    LlmProvider,
    ProviderError,
    ProviderSpec,
    RedactionOptions,
    endpoint_is_local,
)
from busscope.analysis import CapturedFrame

ProviderFactory = Callable[[str, str], LlmProvider]
Runner = Callable[[Callable[[], str], Callable[[str], None], Callable[[str], None]], None]
Confirm = Callable[[QWidget, str], bool]


class _Signals(QObject):
    """Carries one job's outcome back to the GUI thread."""

    done = Signal(str)
    failed = Signal(str)


_PENDING: set[_Signals] = set()


class _Job(QRunnable):
    """Run one provider call off the GUI thread and report through queued signals."""

    def __init__(self, work: Callable[[], str], signals: _Signals) -> None:
        """Keep the work and the signals carrier for run()."""
        super().__init__()
        self._work = work
        self._signals = signals

    def run(self) -> None:
        """Emit the answer, or the key-free error message."""
        try:
            self._signals.done.emit(self._work())
        except ProviderError as error:
            self._signals.failed.emit(str(error))
        except Exception:  # noqa: BLE001 - any escape would leave the UI waiting forever
            self._signals.failed.emit("Unexpected error while contacting the provider")


def thread_pool_runner(
    work: Callable[[], str], on_done: Callable[[str], None], on_error: Callable[[str], None]
) -> None:
    """Default runner: QThreadPool worker, results delivered back on the GUI thread."""
    signals = _Signals()
    # The QObject must outlive the worker until its queued signal reaches the GUI thread.
    _PENDING.add(signals)
    signals.done.connect(on_done)
    signals.failed.connect(on_error)
    for signal in (signals.done, signals.failed):
        signal.connect(lambda _text: _PENDING.discard(signals))
    QThreadPool.globalInstance().start(_Job(work, signals))


def ask_confirmation(parent: QWidget, message: str) -> bool:
    """Default confirmation dialog; defaults to No."""
    answer = QMessageBox.question(
        parent,
        "Send to AI provider?",
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


class _MessageLabel(QLabel):
    """A label that takes no room while it has nothing to say."""

    def __init__(self) -> None:
        super().__init__()
        self.setWordWrap(True)
        self.setVisible(False)

    def setText(self, text: str) -> None:  # noqa: N802  # Qt override
        """Show the label only when the text is not empty."""
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self) -> None:
        """Clearing hides the label."""
        super().clear()
        self.setVisible(False)


class AssistantWidget(QWidget):
    """Provider setup, payload preview and question/answer for one capture."""

    _PREFIX = "ai/"

    def __init__(
        self,
        keys: KeyStore,
        provider_factory: ProviderFactory,
        settings: QSettings,
        frames: Callable[[], Sequence[CapturedFrame]],
        capture_id: Callable[[], int] = lambda: 0,
        runner: Runner = thread_pool_runner,
        confirm: Confirm = ask_confirmation,
    ) -> None:
        """Wire the injected boundaries; nothing is sent until the operator confirms."""
        super().__init__()
        self._keys = keys
        self._provider_factory = provider_factory
        self._settings = settings
        self._frames = frames
        self._capture_id = capture_id
        self._runner = runner
        self._confirm = confirm
        self._request: DiagnosisRequest | None = None
        # Key presence per provider, read once: a locked keyring must not freeze each refresh.
        self._key_present: dict[str, bool] = {}
        # Bumped on provider change so a late reply never lands under another provider.
        self._generation = 0
        self._capture_marker: tuple[int, int] | None = None

        self.provider_input = QComboBox()
        self.provider_input.setAccessibleName("AI provider")
        for spec in PROVIDERS:
            self.provider_input.addItem(spec.label, spec.id)
        self.model_input = QLineEdit()
        self.model_input.setAccessibleName("AI model")
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setAccessibleName("Local model endpoint")
        self.endpoint_row = self._row("Endpoint:", self.endpoint_input)

        self.key_link = QLabel()
        self.key_link.setOpenExternalLinks(True)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setAccessibleName("API key")
        self.save_key_button = QPushButton("Save key")
        self.forget_key_button = QPushButton("Forget key")
        self.key_state = QLabel()
        self.key_setup = QWidget()
        key_layout = QVBoxLayout(self.key_setup)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.key_link)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input)
        key_row.addWidget(self.save_key_button)
        key_row.addWidget(self.forget_key_button)
        key_layout.addLayout(key_row)
        key_layout.addWidget(self.key_state)

        self.test_button = QPushButton("Test connection")
        self.status_label = _MessageLabel()

        self.question_input = QPlainTextEdit()
        self.question_input.setAccessibleName("Diagnosis question")
        self.question_input.setPlaceholderText("e.g. Why does module M2 report a fault?")
        self.anonymise_input = QCheckBox("Pseudonymise module addresses")
        self.relative_time_input = QCheckBox("Relative timestamps")
        self.mask_input = QCheckBox("Mask raw payload bytes (decoded values are still sent)")
        # Safe defaults: the options stay folded until the operator asks for them.
        self.privacy_toggle = QToolButton()
        self.privacy_toggle.setText("Privacy options")
        self.privacy_toggle.setCheckable(True)
        self.privacy_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.privacy_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.privacy_options = QWidget()
        privacy_layout = QVBoxLayout(self.privacy_options)
        privacy_layout.setContentsMargins(0, 0, 0, 0)
        for box in (self.anonymise_input, self.relative_time_input, self.mask_input):
            box.setChecked(True)
            privacy_layout.addWidget(box)
        self.privacy_options.setVisible(False)
        self.prepare_button = QPushButton("Prepare")
        self.prepare_button.setVisible(False)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Payload preview")
        self.destination_label = QLabel()
        self.destination_label.setWordWrap(True)
        self.send_button = QPushButton("Send")
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setAccessibleName("AI answer")
        self.diagnosis = QWidget()
        diagnosis_layout = QVBoxLayout(self.diagnosis)
        diagnosis_layout.setContentsMargins(0, 0, 0, 0)
        diagnosis_layout.addWidget(self.question_input)
        diagnosis_layout.addWidget(self.privacy_toggle)
        diagnosis_layout.addWidget(self.privacy_options)
        diagnosis_layout.addWidget(self.prepare_button)
        diagnosis_layout.addWidget(self.preview)
        diagnosis_layout.addWidget(self.destination_label)
        diagnosis_layout.addWidget(self.send_button)
        diagnosis_layout.addWidget(self.answer)
        self.waiting_label = _MessageLabel()

        form = QFormLayout()
        form.addRow("Provider:", self.provider_input)
        form.addRow("Model:", self.model_input)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.endpoint_row)
        layout.addWidget(self.key_setup)
        layout.addWidget(self.test_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.waiting_label)
        layout.addWidget(self.diagnosis)
        layout.addStretch()

        stored = self._settings.value(f"{self._PREFIX}provider")
        index = self.provider_input.findData(stored) if isinstance(stored, str) else -1
        self.provider_input.setCurrentIndex(max(index, 0))
        self.provider_input.currentIndexChanged.connect(self._on_provider_changed)
        self.model_input.editingFinished.connect(self._save_choices)
        self.endpoint_input.editingFinished.connect(self._save_choices)
        # A preview is only valid for the model and destination it was built for.
        self.model_input.textEdited.connect(lambda _text: self._on_setup_edited())
        self.endpoint_input.textEdited.connect(lambda _text: self._on_setup_edited())
        self.key_input.textChanged.connect(self._on_key_typed)
        self.save_key_button.clicked.connect(self.save_key)
        self.forget_key_button.clicked.connect(self.forget_key)
        self.test_button.clicked.connect(self.test_connection)
        self.prepare_button.clicked.connect(self.prepare)
        self.privacy_toggle.toggled.connect(self._on_privacy_toggled)
        self.question_input.textChanged.connect(self._on_question_edited)
        # A preview is only valid for the privacy options it was built with.
        for box in (self.anonymise_input, self.relative_time_input, self.mask_input):
            box.toggled.connect(lambda _checked: self._reset_preview())
        self.send_button.clicked.connect(self.send)
        self._show_provider_controls()

    @staticmethod
    def _row(label: str, field: QWidget) -> QWidget:
        """Group a label and its field so they hide together."""
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(label))
        row.addWidget(field)
        return widget

    @property
    def spec(self) -> ProviderSpec:
        """The provider currently selected."""
        return PROVIDERS[self.provider_input.currentIndex()]

    def _endpoint(self) -> str:
        """Endpoint in use: fixed for cloud providers, editable for local."""
        if self.spec.needs_key:
            return self.spec.default_endpoint
        return self.endpoint_input.text().strip() or self.spec.default_endpoint

    def _model(self) -> str:
        """Model actually used: the typed one, else the provider default."""
        return self.model_input.text().strip() or self.spec.default_model

    def _service(self) -> DiagnosisService:
        """Service bound to the adapter of the selected provider."""
        provider = self._provider_factory(self.spec.id, self._endpoint())
        return DiagnosisService({self.spec.id: provider}, self._keys)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802  # Qt override
        """Readiness (keyring, capture) is evaluated once the tab is shown, never at startup."""
        super().showEvent(event)
        self.refresh()

    def _on_provider_changed(self) -> None:
        """Show the controls of the newly chosen provider, then re-evaluate readiness."""
        self._show_provider_controls()
        self.refresh()

    def _show_provider_controls(self) -> None:
        """Show the controls of the chosen provider without touching the keyring."""
        spec = self.spec
        model = self._settings.value(f"{self._PREFIX}model/{spec.id}")
        self.model_input.setText(model if isinstance(model, str) else spec.default_model)
        endpoint = self._settings.value(f"{self._PREFIX}endpoint/{spec.id}")
        self.endpoint_input.setText(
            endpoint if isinstance(endpoint, str) else spec.default_endpoint
        )
        self.endpoint_row.setVisible(not spec.needs_key)
        self.key_setup.setVisible(spec.needs_key)
        self.key_input.clear()
        if spec.needs_key:
            self.key_link.setText(
                f'Create a key at <a href="{spec.key_url}">{spec.key_url}</a> — {spec.key_hint}'
            )
        self.status_label.clear()
        self._invalidate_pending()
        self._save_choices()

    def _on_setup_edited(self) -> None:
        """A new model or endpoint: drop the preview and any reply still in flight."""
        self._invalidate_pending()
        self._reset_preview()

    def _invalidate_pending(self) -> None:
        """Drop in-flight replies, the last answer and its status: they belong to the old setup."""
        self._generation += 1
        self.status_label.clear()
        self.answer.clear()
        self.answer.setVisible(False)
        self._set_busy(False)

    def _save_choices(self) -> None:
        """Persist non-secret choices; the key is never written here."""
        spec = self.spec
        self._settings.setValue(f"{self._PREFIX}provider", spec.id)
        self._settings.setValue(f"{self._PREFIX}model/{spec.id}", self.model_input.text())
        if not spec.needs_key:
            self._settings.setValue(f"{self._PREFIX}endpoint/{spec.id}", self.endpoint_input.text())

    def _has_key(self) -> bool:
        """Whether a key is stored; a keyring failure counts as no key."""
        provider_id = self.spec.id
        if provider_id not in self._key_present:
            try:
                self._key_present[provider_id] = bool(self._keys.get(provider_id))
            except ProviderError as error:
                self.status_label.setText(f"Error: {error}")
                self._key_present[provider_id] = False
        return self._key_present[provider_id]

    def refresh(self) -> None:
        """Re-evaluate what is shown: called on provider, key or capture changes."""
        frames = self._frames()
        has_frames = bool(frames)
        # Another capture, or more frames of this one, voids the answer: it described frames
        # no longer shown. The identity comes from the capture side, never from frame content.
        marker = (self._capture_id(), len(frames))
        if marker != self._capture_marker:
            self._capture_marker = marker
            self._invalidate_pending()
        ready = not self.spec.needs_key or self._has_key()
        if self.spec.needs_key:
            self.key_state.setText("Key stored in the OS keyring" if ready else "No key stored")
            self.forget_key_button.setVisible(ready)
        self.save_key_button.setVisible(False)
        self.test_button.setVisible(ready)
        self.diagnosis.setVisible(ready and has_frames)
        if not ready:
            self.waiting_label.setText("Set up the provider to ask questions.")
        elif not has_frames:
            self.waiting_label.setText("Capture or load frames to ask questions.")
        else:
            self.waiting_label.clear()
        self._reset_preview()

    def _on_privacy_toggled(self, unfolded: bool) -> None:
        """Fold or unfold the redaction options."""
        self.privacy_options.setVisible(unfolded)
        self.privacy_toggle.setArrowType(
            Qt.ArrowType.DownArrow if unfolded else Qt.ArrowType.RightArrow
        )

    def _on_question_edited(self) -> None:
        """Prepare is offered only once there is a question; an edit voids the preview.

        It also voids the answer and any reply in flight: they answer another question.
        """
        self.prepare_button.setVisible(bool(self.question_input.toPlainText().strip()))
        self._invalidate_pending()
        self._reset_preview()

    def _reset_preview(self) -> None:
        """Hide any stale preview so nothing unseen can be sent."""
        self._request = None
        self.preview.clear()
        self.preview.setVisible(False)
        self.destination_label.setVisible(False)
        self.send_button.setVisible(False)

    def _on_key_typed(self, text: str) -> None:
        """Live format feedback while the key is typed."""
        if not text:
            self.refresh()
            return
        valid = self.spec.key_looks_valid(text)
        self.save_key_button.setVisible(valid)
        self.key_state.setText("Format looks right" if valid else "Unexpected format")

    def save_key(self) -> None:
        """Move the typed key to the keyring and wipe it from the field."""
        key = self.key_input.text().strip()
        if not self.spec.key_looks_valid(key):
            return
        try:
            self._keys.set(self.spec.id, key)
        except ProviderError as error:
            self.status_label.setText(f"Error: {error}")
            return
        finally:
            # Silent clear: an error message must not be replaced by the refresh it triggers.
            blocker = QSignalBlocker(self.key_input)
            self.key_input.clear()
            del blocker
        self._key_present[self.spec.id] = True
        self._invalidate_pending()
        self.status_label.setText("Key saved")
        self.refresh()

    def forget_key(self) -> None:
        """Delete the provider's key from the keyring."""
        try:
            self._keys.delete(self.spec.id)
        except ProviderError as error:
            self.status_label.setText(f"Error: {error}")
            return
        self._key_present[self.spec.id] = False
        self._invalidate_pending()
        self.status_label.setText("Key forgotten")
        self.refresh()

    def test_connection(self) -> None:
        """Send a minimal request in the background."""
        service, spec, model = self._service(), self.spec, self.model_input.text()
        self.status_label.setText("Testing…")
        self._set_busy(True)
        self._runner(
            lambda: service.test_connection(spec, model),
            self._current(lambda _answer: self._test_done("Connection OK")),
            self._current(lambda message: self._test_done(f"Error: {message}")),
        )

    def _current(self, callback: Callable[[str], None]) -> Callable[[str], None]:
        """Wrap a callback so it is dropped if the provider changed meanwhile."""
        generation = self._generation

        def guarded(text: str) -> None:
            """Forward only while the same provider is selected."""
            if generation == self._generation:
                callback(text)

        return guarded

    def _test_done(self, status: str) -> None:
        """Show the test outcome and allow another request."""
        self.status_label.setText(status)
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        """One request at a time: a test and a diagnosis share the status line."""
        self.test_button.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        # Rebuilding the request meanwhile would show the reply under frames never sent.
        self.prepare_button.setEnabled(not busy)

    def _options(self) -> RedactionOptions:
        """Redaction options from the checkboxes."""
        return RedactionOptions(
            anonymise_addresses=self.anonymise_input.isChecked(),
            relative_time=self.relative_time_input.isChecked(),
            mask_raw_payloads=self.mask_input.isChecked(),
        )

    def prepare(self) -> None:
        """Build the exact payload and show it with its destination."""
        try:
            request = self._service().prepare(
                self.question_input.toPlainText(), self._frames(), self._options()
            )
        except ValueError as error:
            self.status_label.setText(f"Error: {error}")
            return
        self._request = request
        self.preview.setPlainText(
            f"Model: {self._model()}\n\nSystem:\n{SYSTEM_PROMPT}\n\n{request.prompt()}"
        )
        self.destination_label.setText(self._destination())
        for widget in (self.preview, self.destination_label, self.send_button):
            widget.setVisible(True)

    def _destination(self) -> str:
        """Where the payload goes, warning when it leaves the PC."""
        if not self.spec.needs_key and endpoint_is_local(self._endpoint()):
            return f"Destination: {self._endpoint()} (this PC — nothing leaves it)"
        return f"Warning: this text will be sent to {self._endpoint()} and leave this PC."

    def send(self) -> None:
        """Send the previewed request after explicit confirmation."""
        request = self._request
        if request is None:
            return
        if not self._confirm(self, self._destination() + "\n\nSend the previewed text?"):
            self.status_label.setText("Send cancelled")
            return
        service, spec, model = self._service(), self.spec, self.model_input.text()
        self.status_label.setText("Waiting for the answer…")
        self._set_busy(True)
        self._runner(
            lambda: service.ask(request, spec, model),
            self._current(self._on_answer),
            self._current(self._on_error),
        )

    def _on_answer(self, text: str) -> None:
        """Show the answer as plain text, never as rich text."""
        self.answer.setPlainText(text)
        self.answer.setVisible(True)
        self.status_label.setText("Answer received")
        self._set_busy(False)

    def _on_error(self, message: str) -> None:
        """Show a key-free error and allow a retry."""
        self.status_label.setText(f"Error: {message}")
        self._set_busy(False)
