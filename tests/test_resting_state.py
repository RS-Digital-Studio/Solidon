"""Was das Fenster zeigt, wenn nichts passiert.

Ein Signal wirkt, solange es allein steht. Leuchten vier Stellen gleichzeitig
in der Akzentfarbe, ist keine davon mehr ein Signal — dann ist es eine Tapete,
und der Blick des Kunden hat keinen Anker mehr. Der Ruhezustand ist deshalb
eine eigene Zusage: **höchstens ein Element trägt eine Akzentfläche**, solange
die Anwendung nichts von ihm will.

Gemessen wird am **gerenderten Bild**, nicht an Palette oder Stylesheet-Text.
Die Akzentfläche entsteht hier aus dem Stylesheet (``background``), und davon
weiß ``widget.palette()`` nichts — eine Messung dort zählte null, wo das Auge
vier sieht. Was ein Kunde sieht, ist, was gemalt wird.

Die Zusage ist herstellbar: Am 30.08.2026 gemessen, in beiden Themen genau ein
Element (der Knopf „Auf das Bett setzen"). Vorher waren es vier — sie sind mit
der Werkzeugdämpfung gefallen.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from app.core.bootstrap import load_operations
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.theme import THEMES, apply_theme

MESHES = Path(__file__).parent / "data" / "meshes"

#: Ab welchem Flächenanteil ein Element als „trägt Akzentfläche" gilt. Ein
#: Rahmen von einem Punkt ist ein Akzent**strich** und keine Fläche; erst wer
#: ein Drittel seiner Fläche in der Signalfarbe zeigt, konkurriert um den Blick.
AREA_SHARE = 0.30

#: Wie weit eine gemalte Farbe vom Token abweichen darf und trotzdem als
#: dieselbe gilt. Ein Stylesheet mischt, ein Zustand hellt auf, und ein
#: Farbverlauf trifft den Token selten exakt.
TOLERANCE = 20


def accent_elements(window: MainWindow, theme: str) -> list[str]:
    """Die sichtbaren Blattelemente, die überwiegend in der Akzentfarbe stehen."""
    accent = QColor(THEMES[theme]["highlight"])

    def close_enough(value: int) -> bool:
        one = QColor(value)
        return (
            abs(one.red() - accent.red()) <= TOLERANCE
            and abs(one.green() - accent.green()) <= TOLERANCE
            and abs(one.blue() - accent.blue()) <= TOLERANCE
        )

    found: list[str] = []
    for widget in window.findChildren(QWidget):
        if not widget.isVisible() or widget.width() < 8 or widget.height() < 8:
            continue
        # Nur Blätter: Ein Elternteil malt die Fläche seines Kindes mit, und
        # dann zählte dieselbe Fläche fünfmal.
        if widget.findChildren(QWidget):
            continue
        image = widget.grab().toImage()
        step = max(1, min(image.width(), image.height()) // 12)
        hits = total = 0
        for x in range(0, image.width(), step):
            for y in range(0, image.height(), step):
                total += 1
                if close_enough(image.pixel(x, y)):
                    hits += 1
        if total and hits / total >= AREA_SHARE:
            label = ""
            if hasattr(widget, "text"):
                try:
                    label = str(widget.text())[:34]
                except Exception:  # pragma: no cover — ein Widget ohne lesbaren Text
                    label = ""
            found.append(f"{type(widget).__name__}({widget.objectName() or '-'}) {label}")
    return found


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    load_operations()
    return MainWindow(Session(), UiSettings())


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_at_rest_only_one_element_carries_the_accent(
    qt_app: QApplication, window: MainWindow, theme: str
) -> None:
    """Im Ruhezustand leuchtet höchstens eine Stelle.

    **Der Ruhezustand ist der Normalfall**, und genau dort wurde die Farbe
    verschwendet: Vier Elemente trugen sie gleichzeitig, bevor die
    Werkzeugdämpfung fiel. Wer dann ein echtes Signal setzen will, hat keine
    Farbe mehr übrig, die auffiele.

    Ruhezustand heißt: Modell geladen, kein Werkzeug offen, nichts gewählt,
    nichts läuft. Was in diesem Zustand leuchtet, leuchtet immer.
    """
    settings = UiSettings()
    settings.theme = theme
    apply_theme(qt_app, theme)
    window.resize(1280, 800)
    window.show()
    for _ in range(30):
        QApplication.processEvents()
    window.action_theme(theme)
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    for _ in range(60):
        QApplication.processEvents()
    window.tools.activate(None)
    for _ in range(20):
        QApplication.processEvents()

    lit = accent_elements(window, theme)
    assert len(lit) <= 1, (
        f"{len(lit)} Elemente tragen im Ruhezustand die Akzentfarbe, erlaubt ist "
        f"eines: {lit}. Ein Signal, das an mehreren Stellen zugleich leuchtet, "
        "ist keines mehr — welches davon soll der Kunde zuerst ansehen?"
    )


def test_the_measurement_would_notice_a_second_light(
    qt_app: QApplication, window: MainWindow
) -> None:
    """Die Gegenprobe zur Zusage darüber: Die Messung sieht ein zweites Licht.

    **Ohne diese Prüfung wäre der Wächter wertlos.** Eine Zählung, die aus
    einem falschen Farbton oder einem zu engen Filter immer null liefert, ist
    von einer erfüllten Zusage nicht zu unterscheiden — beide melden „alles in
    Ordnung". Hier wird ein zweites Element absichtlich eingefärbt; findet die
    Messung es nicht, misst sie nichts.
    """
    apply_theme(qt_app, "dark")
    window.resize(1280, 800)
    window.show()
    for _ in range(30):
        QApplication.processEvents()
    window.action_theme("dark")
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    for _ in range(60):
        QApplication.processEvents()

    before = len(accent_elements(window, "dark"))

    accent = THEMES["dark"]["highlight"]
    # **Mit Text, nicht nur mit Farbe.** Ein leeres ``QLabel`` ist wenige
    # Punkte breit und fällt durch den Mindestgrößen-Filter — die erste
    # Fassung färbte es ein und die Messung sah nichts, was aussah, als
    # zähle sie falsch. Sie zählte richtig; das Element war zu klein.
    window.status_message.setText("Gegenprobe: ein zweites Licht")
    window.status_message.setStyleSheet(f"background: {accent};")
    for _ in range(20):
        QApplication.processEvents()

    after = len(accent_elements(window, "dark"))
    window.status_message.setStyleSheet("")
    window.status_message.setText("")

    assert after > before, (
        f"die Messung hat ein absichtlich eingefärbtes Element nicht bemerkt "
        f"({before} vorher, {after} nachher) — dann sagt ihre Null nichts aus"
    )
