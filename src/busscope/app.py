"""Application composition root for the CAN Sniffer desktop application."""

import sys

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

from can_sniffer.capture import PythonCanAdapter
from can_sniffer.protocol import ProtocolDecoder
from can_sniffer.qt_settings import QtSettingsRepository
from can_sniffer.session import CaptureSession
from can_sniffer.settings_ui import SettingsWidget
from can_sniffer.socketcan_transmission import (
    IpLinkCanInterfaceInspector,
    SocketCanTransmitter,
)
from can_sniffer.transmission_ui import TransmissionWidget
from can_sniffer.ui import CaptureWindow


def create_application(arguments: list[str] | None = None) -> QApplication:
    """Return the existing Qt application or create one for the current process."""
    QCoreApplication.setOrganizationName("benoit-bremaud")
    QCoreApplication.setApplicationName("can-sniffer")
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
    return CaptureWindow(session, preferences, settings_widget, transmission_widget)


def main() -> int:
    """Start the CAN Sniffer desktop application."""
    application = create_application()
    window = create_capture_window()
    window.show()
    return application.exec()
