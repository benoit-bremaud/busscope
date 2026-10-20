"""PySide6 panel for deliberate one-attempt CAN transmission."""

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from busscope.transmission import CanTransmissionPort, ManualTransmission


class TransmissionWidget(QWidget):
    """Validate, confirm, and submit one manual transmission request."""

    def __init__(self, transmitter: CanTransmissionPort) -> None:
        """Build the form; sending stays disabled until the operator enables it."""
        super().__init__()
        self._transmitter = transmitter

        self.channel_input = QLineEdit("can0")
        self.channel_input.setAccessibleName("Transmission CAN channel")
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("0x001ABCDE")
        self.identifier_input.setAccessibleName("Extended CAN identifier")
        self.payload_input = QLineEdit()
        self.payload_input.setPlaceholderText("01 02 03 04 05 06 07 08")
        self.payload_input.setAccessibleName("CAN payload")
        self.enable_transmission = QCheckBox("Enable manual transmission")
        self.send_button = QPushButton("Send once")
        self.send_button.setAccessibleName("Send one CAN frame")
        self.send_button.setEnabled(False)
        self.status_label = QLabel("Manual transmission is disabled")

        form = QFormLayout()
        form.addRow("Channel:", self.channel_input)
        form.addRow("Extended identifier:", self.identifier_input)
        form.addRow("Payload (8 bytes):", self.payload_input)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.enable_transmission)
        layout.addWidget(self.send_button)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.enable_transmission.toggled.connect(self._set_enabled)
        self.send_button.clicked.connect(self.send_once)

    def send_once(self) -> None:
        """Send only after session enablement, validation, and confirmation."""
        if not self.enable_transmission.isChecked():
            self.status_label.setText("Error: manual transmission is disabled")
            return
        try:
            request = ManualTransmission.from_text(
                self.channel_input.text(),
                self.identifier_input.text(),
                self.payload_input.text(),
            )
        except ValueError as error:
            self.status_label.setText(f"Error: {error}")
            return

        answer = QMessageBox.warning(
            self,
            "Confirm CAN transmission",
            self._confirmation_text(request),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Transmission cancelled")
            return

        try:
            self._transmitter.send(request)
        except Exception as error:
            self.status_label.setText(f"Error: {error}")
            return
        self.status_label.setText("One CAN transmission attempt completed")

    def _set_enabled(self, enabled: bool) -> None:
        """Toggle the send button and tell the operator the current state."""
        self.send_button.setEnabled(enabled)
        self.status_label.setText(
            "Manual transmission enabled" if enabled else "Manual transmission is disabled"
        )

    @staticmethod
    def _confirmation_text(request: ManualTransmission) -> str:
        """Describe exactly the one frame the operator is about to confirm."""
        return (
            f"Channel: {request.channel}\n"
            f"Extended identifier: {request.identifier_hex}\n"
            f"Payload: {request.payload_hex}\n"
            "Frames to send: 1"
        )
