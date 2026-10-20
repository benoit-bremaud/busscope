"""Offline loading and deterministic replay of exported CAN captures."""

import csv
import math
from collections.abc import Iterable
from dataclasses import replace
from io import StringIO
from pathlib import Path

from busscope.analysis import CapturedFrame
from busscope.protocol import CanFrame, ProtocolDecoder


class CsvCaptureLoader:
    """Load the CSV format produced by :class:`CsvExporter`."""

    _HEADERS = (
        "timestamp_seconds",
        "arbitration_id",
        "is_extended_id",
        "is_error_frame",
        "data",
        "description",
        "decoded_values",
        "diagnostics",
    )

    @classmethod
    def load(cls, path: Path) -> tuple[CapturedFrame, ...]:
        """Load and validate a capture file from disk."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"Cannot read capture file: {path}") from error
        return cls.from_csv(content)

    @classmethod
    def from_csv(cls, content: str) -> tuple[CapturedFrame, ...]:
        """Load and validate CSV content without filesystem access."""
        reader = csv.DictReader(StringIO(content))
        if tuple(reader.fieldnames or ()) != cls._HEADERS:
            raise ValueError("CSV header does not match the BusScope export format")

        records: list[CapturedFrame] = []
        previous_timestamp = 0.0
        decoder = ProtocolDecoder()
        for row_number, row in enumerate(reader, start=2):
            try:
                timestamp = float(row["timestamp_seconds"] or "")
                arbitration_id = int(row["arbitration_id"] or "", 0)
                is_extended_id = cls._parse_bool(row["is_extended_id"], "is_extended_id")
                is_error_frame = cls._parse_bool(row["is_error_frame"], "is_error_frame")
                data = bytes.fromhex(row["data"] or "")
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid CSV row {row_number}: {error}") from error
            if not math.isfinite(timestamp):
                raise ValueError(f"Timestamp must be finite on CSV row {row_number}")
            if timestamp < 0 or timestamp < previous_timestamp:
                raise ValueError(f"Timestamp is not monotonic on CSV row {row_number}")
            if not 0 <= arbitration_id <= (1 << 29) - 1:
                raise ValueError(f"CAN identifier is outside the 29-bit range on row {row_number}")
            if not is_extended_id and arbitration_id > 0x7FF:
                raise ValueError(f"Standard CAN identifier exceeds 11 bits on row {row_number}")
            if len(data) > 8:
                raise ValueError(f"CAN payload exceeds 8 bytes on CSV row {row_number}")
            description = row["description"] or ""
            diagnostics = tuple(
                diagnostic.strip()
                for diagnostic in (row["diagnostics"] or "").split(";")
                if diagnostic.strip()
            )
            decoded = decoder.decode(CanFrame(arbitration_id, data, is_extended_id, is_error_frame))
            result = replace(
                decoded,
                description=description,
                diagnostics=tuple(dict.fromkeys((*decoded.diagnostics, *diagnostics))),
            )
            records.append(CapturedFrame(timestamp, result))
            previous_timestamp = timestamp
        return tuple(records)

    @staticmethod
    def _parse_bool(value: str | None, field: str) -> bool:
        """Accept only the exact 'true'/'false' tokens the exporter writes."""
        if value == "true":
            return True
        if value == "false":
            return False
        raise ValueError(f"Invalid boolean field: {field}")


class ReplayController:
    """Control deterministic local playback of captured records."""

    def __init__(self) -> None:
        """Start empty and paused at the beginning of the timeline."""
        self._records: tuple[CapturedFrame, ...] = ()
        self._next_index = 0
        self._elapsed_seconds = 0.0
        self._playing = False

    def load(self, records: Iterable[CapturedFrame]) -> None:
        """Load records and reset playback to the beginning."""
        self._records = tuple(records)
        self.reset()

    def play(self) -> None:
        """Start or resume playback."""
        if self._next_index < len(self._records):
            self._playing = True

    def pause(self) -> None:
        """Pause playback at the current position."""
        self._playing = False

    def stop(self) -> None:
        """Stop playback while preserving the current playback position."""
        self._playing = False

    @property
    def is_playing(self) -> bool:
        """Return whether playback is currently active."""
        return self._playing

    @property
    def has_records(self) -> bool:
        """Return whether a capture has been loaded for replay."""
        return bool(self._records)

    def reset(self) -> None:
        """Stop playback and return to the beginning."""
        self._next_index = 0
        self._elapsed_seconds = 0.0
        self._playing = False

    def advance(self, elapsed_seconds: float) -> tuple[CapturedFrame, ...]:
        """Advance playback and return records whose scheduled time has arrived."""
        if elapsed_seconds < 0:
            raise ValueError("Replay time increment must not be negative")
        if not self._playing or not self._records:
            return ()
        self._elapsed_seconds += elapsed_seconds
        origin = self._records[0].timestamp_seconds
        due: list[CapturedFrame] = []
        while self._next_index < len(self._records):
            record = self._records[self._next_index]
            if record.timestamp_seconds - origin > self._elapsed_seconds:
                break
            due.append(record)
            self._next_index += 1
        if self._next_index == len(self._records):
            self._playing = False
        return tuple(due)
