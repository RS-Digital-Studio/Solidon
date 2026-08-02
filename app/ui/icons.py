"""Symbole für die Oberfläche (Bauplan §19.3, AGENTS.md Regel 18).

**Symbole ergänzen Text, sie ersetzen ihn nicht.** Ein unbeschriftetes Zeichen
wird geraten, und bei einer Anwendung, die jemand alle paar Wochen öffnet, ist
Wiedererkennen mehr wert als Kompaktheit. „Schnitt", „Explosion" und „Passung"
sind keine Begriffe mit einem Bild, auf das sich die Welt geeinigt hat. Was ein
Symbol hier leistet, ist Unterscheidbarkeit auf einen Blick — sieben Knöpfe mit
Text sehen alle gleich aus, sieben Knöpfe mit Text und Zeichen nicht.

Von Hand geschriebene Pfade und nicht aus :mod:`app.core.drawing` gerechnet:
das Modul zeichnet Maßlinien und Schemata, deren Form aus Zahlen folgt. Ein
Symbol ist eine gestaltete Form, und die entsteht nicht aus einer Formel.

Zwei Dinge halten sie brauchbar:

* **``currentColor`` statt fester Farben.** Qt löst das nicht selbst auf, also
  wird es beim Laden gegen die Textfarbe ersetzt — ein Satz Symbole für beide
  Themen, keiner, der im dunklen unsichtbar wird.
* **Größe an der Schrift, nicht an Pixeln.** Wer die Schrift größer stellt,
  bekommt größere Symbole; sonst schrumpfen sie neben dem Text zu Punkten.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

#: Wie viel größer als die Zeilenhöhe ein Symbol gezeichnet wird, bevor es
#: verkleinert wird — sonst franst es auf HiDPI aus.
OVERSAMPLING: Final = 2

_HEAD: Final = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

#: Die Symbole der Werkzeugzeile. Bewusst in einem Strichstil gehalten: ein
#: gefülltes und ein gestricheltes Zeichen nebeneinander sehen aus wie zwei
#: verschiedene Programme.
PATHS: Final[dict[str, str]] = {
    # Ein Körper, den eine Ebene durchtrennt.
    "section": (
        '<path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5z" />'
        '<path d="M2.5 13.5h19" stroke-dasharray="3 2.5" />'
    ),
    # Maßlinie mit Endstrichen — das Zeichen jeder technischen Zeichnung.
    "measure": (
        '<path d="M4 12h16" /><path d="M7 9l-3 3 3 3" /><path d="M17 9l3 3-3 3" />'
        '<path d="M4 6v3" /><path d="M20 6v3" />'
    ),
    # Vier Richtungen: das eine Zeichen fürs Bewegen, auf das sich alle geeinigt haben.
    "move": (
        '<path d="M12 3v18" /><path d="M3 12h18" />'
        '<path d="M9 6l3-3 3 3" /><path d="M9 18l3 3 3-3" />'
        '<path d="M6 9l-3 3 3 3" /><path d="M18 9l3 3-3 3" />'
    ),
    # Eine Karte über einer Fläche: ungleich gefüllte Felder.
    "analysis": (
        '<rect x="3.5" y="3.5" width="17" height="17" rx="2" />'
        '<path d="M3.5 12h17" /><path d="M12 3.5v17" />'
        '<path d="M3.5 8h8.5" stroke-width="3" opacity="0.45" />'
        '<path d="M12 16h8.5" stroke-width="3" opacity="0.8" />'
    ),
    # Gestapelte Schichten.
    "layers": (
        '<path d="M12 3.5 21 8l-9 4.5L3 8z" />'
        '<path d="M3 12.5 12 17l9-4.5" opacity="0.75" />'
        '<path d="M3 16.5 12 21l9-4.5" opacity="0.5" />'
    ),
    # Auseinandergezogen: zwei Hälften, die voneinander wegwandern. Die erste
    # Fassung verband sie mit gestrichelten Linien — die verschwanden bei
    # Symbolgröße, und übrig blieben zwei Quadrate ohne Aussage.
    "explode": (
        '<rect x="3" y="3" width="8" height="8" rx="1" />'
        '<rect x="13" y="13" width="8" height="8" rx="1" />'
        '<path d="M13.5 10.5 10.5 13.5" />'
        '<path d="M13.5 10.5h-3v3" />'
    ),
    # Die Schweregrade des Prüfberichts. Hier ist Ikonografie ausnahmsweise
    # etabliert: Dreieck warnt, Kreis erklärt, Achteck hält an — die Form trägt
    # allein, auch wo die Farbe wegfällt (Regel 18).
    "severity-info": (
        '<circle cx="12" cy="12" r="8.5" /><path d="M12 11.2v5" /><path d="M12 8.2v.6" />'
    ),
    "severity-warning": (
        '<path d="M12 4 21 19.5H3z" /><path d="M12 10v4.5" /><path d="M12 17.2v.6" />'
    ),
    "severity-error": (
        '<path d="M8.6 3.5h6.8L20.5 8.6v6.8L15.4 20.5H8.6L3.5 15.4V8.6z" />'
        '<path d="M9.4 9.4l5.2 5.2" /><path d="M14.6 9.4l-5.2 5.2" />'
    ),
    # Ein Pinsel, der eine Fläche einfärbt.
    "paint": (
        '<path d="M5 13.5 13.5 5a2.5 2.5 0 0 1 3.5 3.5L8.5 17z" />'
        '<path d="M5 13.5 8.5 17l-3 2.5-2-2z" />'
        '<path d="M14 6.5 17.5 10" />'
    ),
    # Ein leeres Blatt mit umgeknickter Ecke.
    "new": ('<path d="M6 3h7l5 5v13H6z" /><path d="M13 3v5h5" />'),
    # Ein Ordner, halb geöffnet.
    "open": ('<path d="M3 6.5h6l2 2.5h10v9.5H3z" /><path d="M3 9h18" />'),
    # Eine Diskette — das Zeichen fürs Speichern, auf das sich die Welt
    # tatsächlich geeinigt hat.
    "save": ('<path d="M4 4h12l4 4v12H4z" /><path d="M8 4v6h7V4" /><path d="M7 20v-6h10v6" />'),
    # Ein Körper mit einem Pfeil hinein.
    "import": (
        '<path d="M13 4.5 20 8.5v7l-7 4-7-4v-7z" stroke-dasharray="3 2" />'
        '<path d="M2.5 12h7" /><path d="M6.5 9l3 3-3 3" />'
    ),
    # Ein durchgestrichenes Auge für einen Körper, der da ist und nicht
    # gezeichnet wird. Das Wort „ausgeblendet" steht daneben (Regel 18) — das
    # Zeichen unterscheidet die Zeile auf einen Blick, es trägt sie nicht.
    "hidden": (
        '<path d="M3 12s3.6-6 9-6c1.4 0 2.7.4 3.8 1" />'
        '<path d="M19.4 9.1c.9.9 1.6 1.9 1.6 2.9 0 0-3.6 6-9 6-1.5 0-2.8-.5-4-1.1" />'
        '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />'
        '<path d="M4 20 20 4" />'
    ),
}


def svg_source(name: str, colour: str) -> str:
    """Das SVG eines Symbols, in einer Farbe statt ``currentColor``."""
    body = PATHS.get(name)
    if body is None:
        return ""
    return f"{_HEAD}{body}</svg>".replace("currentColor", colour)


def icon(name: str, widget: QWidget, *, scale: float = 1.35, colour: QColor | None = None) -> QIcon:
    """Ein Symbol in der Textfarbe und in der Größe der Schrift des Widgets.

    ``scale`` ist der Faktor auf die Zeilenhöhe: etwas größer als die Schrift,
    sonst verschwindet ein Strichsymbol neben dem Wort daneben.
    """
    tone = colour or widget.palette().windowText().color()
    source = svg_source(name, tone.name())
    if not source:
        return QIcon()
    size = max(int(widget.fontMetrics().height() * scale), 12)
    return QIcon(_pixmap(source, size, tone))


def _pixmap(source: str, size: int, colour: QColor) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()
    image = QImage(QSize(size, size) * OVERSAMPLING, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(float(OVERSAMPLING))
    return QPixmap.fromImage(image)


def known() -> tuple[str, ...]:
    """Welche Symbole es gibt — der Test liest das."""
    return tuple(PATHS)


#: Die Größen, in denen das Fenster-Symbol vorgehalten wird — dieselbe Reihe
#: fragt Windows für Taskleiste, Alt-Tab und Titelzeile ab.
APPLICATION_ICON_SIZES: Final = (16, 24, 32, 48, 64, 128, 256)


def application_icon() -> QIcon:
    """Das Anwendungssymbol, zur Laufzeit aus seiner SVG-Quelle gerastert.

    Die Quelle liegt in ``app/images/icon/formwerk.svg`` und ist dieselbe,
    aus der ``tools/make_icon.py`` die ICO für exe und Installer baut — ein
    Bild, drei Abnehmer. Fehlt die Datei, gibt es ein leeres Symbol und die
    Plattform zeigt ihr Standardbild; ein Start scheitert daran nicht.
    """
    source = Path(__file__).resolve().parent.parent / "images" / "icon" / "formwerk.svg"
    try:
        data = source.read_bytes()
    except OSError:
        return QIcon()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return QIcon()
    result = QIcon()
    for size in APPLICATION_ICON_SIZES:
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        result.addPixmap(QPixmap.fromImage(image))
    return result
