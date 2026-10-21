"""Application composition root for the BusScope desktop application."""

import sys

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

from busscope.ai_assistant_ui import AssistantWidget
from busscope.ai_keystore import KeyringKeyStore
from busscope.ai_providers import build_provider
from busscope.capture import PythonCanAdapter
from busscope.protocol import ProtocolDecoder
from busscope.qt_settings import QtSettingsRepository
from busscope.session import CaptureSession
from busscope.settings_ui import SettingsWidget
from busscope.socketcan_transmission import (
    IpLinkCanInterfaceInspector,
    SocketCanTransmitter,
)
from busscope.transmission_ui import TransmissionWidget
from busscope.ui import CaptureWindow


def create_application(arguments: list[str] | None = None) -> QApplication:
    """Return the existing Qt application or create one for the current process."""
    QCoreApplication.setOrganizationName("benoit-bremaud")
    QCoreApplication.setApplicationName("busscope")
    application = QApplication.instance()
    if isinstance(application, QApplication):
        return application
    return QApplication(sys.argv if arguments is None else arguments)


def create_capture_window() -> CaptureWindow:
    """Build the production capture dependency graph."""
    session = CaptureSession(PythonCanAdapter(), ProtocolDecoder())
    repository = QtSettingsRepository(QSettings())
    preferences = repository.load()
    settings_widget = SettingsWidget(preferences, repository)
    transmitter = SocketCanTransmitter(IpLinkCanInterfaceInspector())
    transmission_widget = TransmissionWidget(transmitter)
    window = CaptureWindow(session, preferences, settings_widget, transmission_widget)
    assistant = AssistantWidget(
        KeyringKeyStore(), build_provider, QSettings(), window.captured_frames
    )
    window.tabs.addTab(assistant, "AI assistant")
    # Re-check readiness whenever the tab is opened: the capture may have changed meanwhile.
    window.tabs.currentChanged.connect(
        lambda index: assistant.refresh() if window.tabs.widget(index) is assistant else None
    )
    return window


def main() -> int:
    """Start the BusScope desktop application."""
    application = create_application()
    window = create_capture_window()
    window.show()
    return application.exec()
