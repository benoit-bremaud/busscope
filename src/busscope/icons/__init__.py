"""Load the bundled Lucide icons (ISC, see icons/LICENSE) as palette-coloured Qt icons."""

from importlib.resources import files

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QIcon, QPixmap

_ICON_SIZE = 48


def load_icon(name: str, color: QColor) -> QIcon:
    """Return the named icon stroked with ``color``.

    Qt's SVG renderer ignores ``currentColor``, so the stroke is substituted before
    rendering; otherwise the icons would stay black on a dark palette.
    """
    svg = files(__name__).joinpath(f"{name}.svg").read_text(encoding="utf-8")
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    if not pixmap.loadFromData(QByteArray(svg.replace("currentColor", color.name()).encode())):
        raise ValueError(f"Cannot render icon {name!r}")
    return QIcon(pixmap)
