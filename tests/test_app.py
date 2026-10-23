from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from busscope.app import create_application, create_capture_window
from busscope.transmission_ui import TransmissionWidget

pytestmark = pytest.mark.usefixtures("isolated_settings")


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Never touch the developer's real settings file.
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("busscope.app.QSettings", lambda: settings)
    create_application([])


def _tab_titles() -> list[str]:
    window = create_capture_window()
    return [window.tabs.tabText(index) for index in range(window.tabs.count())]


@pytest.mark.parametrize("value", [None, "0", "true"])
def test_production_window_omits_transmission_when_switch_is_not_on(
    value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is None:
        monkeypatch.delenv("BUSSCOPE_ENABLE_TRANSMISSION", raising=False)
    else:
        monkeypatch.setenv("BUSSCOPE_ENABLE_TRANSMISSION", value)

    assert _tab_titles() == ["Capture", "Settings", "AI assistant"]


def test_production_window_builds_transmission_when_switch_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUSSCOPE_ENABLE_TRANSMISSION", "1")

    window = create_capture_window()

    assert isinstance(window.transmission_widget, TransmissionWidget)
    titles = [window.tabs.tabText(index) for index in range(window.tabs.count())]
    assert titles == ["Capture", "Transmission", "Settings", "AI assistant"]
