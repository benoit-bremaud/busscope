"""Application use case for orchestrating a CAN capture session."""

import logging
from collections.abc import Iterator

from can_sniffer.capture import CanCapturePort, CaptureConfiguration
from can_sniffer.protocol import DecodeResult, ProtocolDecoder

logger = logging.getLogger(__name__)


class CaptureSession:
    """Open a CAN port, decode received frames, and close the port safely."""

    def __init__(self, port: CanCapturePort, decoder: ProtocolDecoder) -> None:
        """Bind the capture port and decoder; the session starts stopped."""
        self._port = port
        self._decoder = decoder
        self._capturing = False

    def start(self, configuration: CaptureConfiguration) -> None:
        """Open the capture port and mark the session as active."""
        if self._capturing:
            raise RuntimeError("CAN capture is already running")
        try:
            self._port.open(configuration)
        except Exception:
            try:
                self._port.close()
            except Exception:
                logger.warning("Failed to close CAN port after an open error", exc_info=True)
            raise
        self._capturing = True

    def poll(self, timeout: float | None = None) -> DecodeResult | None:
        """Decode one frame, or return None when polling times out."""
        if not self._capturing:
            raise RuntimeError("CAN capture is not running")
        frame = self._port.receive(timeout)
        if frame is None:
            return None
        return self._decoder.decode(frame)

    def capture(
        self, configuration: CaptureConfiguration, timeout: float | None = None
    ) -> Iterator[DecodeResult]:
        """Yield decoded frames until timeout, stop, or a port exception."""
        self.start(configuration)
        try:
            while self._capturing:
                frame = self._port.receive(timeout)
                if frame is None:
                    return
                yield self._decoder.decode(frame)
        finally:
            self.stop()

    def stop(self) -> None:
        """Request that the active capture loop stop after its current frame."""
        if self._capturing:
            self._capturing = False
            try:
                self._port.close()
            except Exception:
                logger.warning("Failed to close CAN port while stopping capture", exc_info=True)
