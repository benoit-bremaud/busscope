from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from busscope import icons
from busscope.icons import load_icon

ICON_NAMES = sorted(path.stem for path in Path(icons.__file__).parent.glob("*.svg"))


@pytest.fixture
def qt_application() -> QApplication:
    application = QApplication.instance()
    if application is None or not isinstance(application, QApplication):
        application = QApplication([])
    return application


@pytest.mark.parametrize("name", ICON_NAMES)
def test_every_bundled_icon_renders(qt_application: QApplication, name: str) -> None:
    del qt_application
    assert load_icon(name, QColor("#ffffff")).isNull() is False


def test_icon_takes_the_requested_colour(qt_application: QApplication) -> None:
    del qt_application
    image = load_icon("square", QColor("#ff0000")).pixmap(48, 48).toImage()
    colours = {image.pixelColor(x, y).name() for x in range(48) for y in range(48)}

    assert "#ff0000" in colours


def test_unknown_icon_raises(qt_application: QApplication) -> None:
    del qt_application
    with pytest.raises(FileNotFoundError):
        load_icon("does-not-exist", QColor("#000000"))


def test_unrenderable_icon_raises(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    monkeypatch.setattr("busscope.icons.QPixmap.loadFromData", lambda *args: False)
    with pytest.raises(ValueError, match="Cannot render icon"):
        load_icon("play", QColor("#000000"))
