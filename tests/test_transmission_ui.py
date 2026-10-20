import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from busscope.transmission import ManualTransmission
from busscope.transmission_ui import TransmissionWidget


class FakeTransmitter:
    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[ManualTransmission] = []
        self.error = error

    def send(self, request: ManualTransmission) -> None:
        self.requests.append(request)
        if self.error is not None:
            raise self.error


@pytest.fixture
def qt_application() -> QApplication:
    application = QApplication.instance()
    if application is None or not isinstance(application, QApplication):
        application = QApplication([])
    return application


def valid_widget(transmitter: FakeTransmitter) -> TransmissionWidget:
    widget = TransmissionWidget(transmitter)
    widget.identifier_input.setText("0x1abcde")
    widget.payload_input.setText("01 02 03 04 05 06 07 08")
    return widget


def test_transmission_starts_disabled_and_enablement_does_not_send(
    qt_application: QApplication,
) -> None:
    del qt_application
    transmitter = FakeTransmitter()
    widget = valid_widget(transmitter)

    assert widget.enable_transmission.isChecked() is False
    assert widget.send_button.isEnabled() is False
    widget.enable_transmission.setChecked(True)

    assert widget.send_button.isEnabled() is True
    assert transmitter.requests == []


def test_disabled_or_invalid_request_never_reaches_port(
    qt_application: QApplication,
) -> None:
    del qt_application
    transmitter = FakeTransmitter()
    widget = valid_widget(transmitter)

    widget.send_once()
    widget.enable_transmission.setChecked(True)
    widget.payload_input.setText("01")
    widget.send_once()

    assert transmitter.requests == []
    assert widget.status_label.text().startswith("Error:")


def test_cancelled_confirmation_never_reaches_port(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    transmitter = FakeTransmitter()
    widget = valid_widget(transmitter)
    widget.enable_transmission.setChecked(True)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: QMessageBox.StandardButton.Cancel,
    )

    widget.send_once()

    assert transmitter.requests == []
    assert widget.status_label.text() == "Transmission cancelled"


def test_confirmation_displays_and_sends_same_normalized_request(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    transmitter = FakeTransmitter()
    widget = valid_widget(transmitter)
    widget.enable_transmission.setChecked(True)
    confirmation: list[str] = []
    confirmed_requests: list[ManualTransmission] = []

    def confirmation_text(request: ManualTransmission) -> str:
        confirmed_requests.append(request)
        return TransmissionWidget._confirmation_text(request)

    def confirm(*args: object) -> QMessageBox.StandardButton:
        confirmation.append(str(args[2]))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(widget, "_confirmation_text", confirmation_text)
    monkeypatch.setattr(QMessageBox, "warning", confirm)
    widget.send_once()

    assert confirmation == [
        "Channel: can0\n"
        "Extended identifier: 0x001ABCDE\n"
        "Payload: 01 02 03 04 05 06 07 08\n"
        "Frames to send: 1"
    ]
    assert transmitter.requests == [
        ManualTransmission("can0", 0x1ABCDE, bytes.fromhex("01 02 03 04 05 06 07 08"))
    ]
    assert transmitter.requests[0] is confirmed_requests[0]
    assert widget.status_label.text() == "One CAN transmission attempt completed"


def test_adapter_failure_is_not_reported_as_success(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    transmitter = FakeTransmitter(OSError("CAN unavailable"))
    widget = valid_widget(transmitter)
    widget.enable_transmission.setChecked(True)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    widget.send_once()

    assert len(transmitter.requests) == 1
    assert widget.status_label.text() == "Error: CAN unavailable"


def test_disabling_transmission_restores_fail_closed_state(
    qt_application: QApplication,
) -> None:
    del qt_application
    widget = valid_widget(FakeTransmitter())
    widget.enable_transmission.setChecked(True)
    widget.enable_transmission.setChecked(False)

    assert widget.send_button.isEnabled() is False
    assert widget.status_label.text() == "Manual transmission is disabled"
