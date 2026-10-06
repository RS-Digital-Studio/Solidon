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

**Linien zählen mit** (RM-512). Kartenränder und die Kante des aktiven Reiters
standen in Bernstein, und die Flächenmessung sah sie nicht: Ein Rand ist kein
Drittel seines Widgets, und er gehört einem Elternteil, nicht einem Blatt.
Gezählt wird deshalb zusätzlich jeder zusammenhängende Strich in einer der
beiden Akzentfarben (``highlight``, ``accent_line``), der mindestens
:data:`LINE_LENGTH` Punkte lang ist — am Bild des ganzen Fensters.

Ein offener Fehler oder eine Warnung mit empfohlener Handlung ist kein
Ruhezustand. Ein Hinweis ist es: Er wird nicht vorgewählt und leuchtet nicht.
Der Prüfbericht meldet auch unkalibriertes Material; die ruhige Probe benutzt
deshalb ein kalibriertes Profil. Das eine Element mit Akzent ist der Knopf
*Bausteine* — der Hauptweg, wenn nichts gewählt ist (Entscheidung Robert,
``.claude/rules/grenzen.md``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget
from scipy import ndimage

from app.core.bootstrap import load_operations
from app.core.knowledge import calibration, profiles
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

#: Ab welcher Länge ein Strich in der Akzentfarbe als Akzent zählt. Kürzer
#: sind Schriftzeichen, Symbole und die Ecken eines Fokusrings — länger ist
#: eine Kante, die das Auge als Linie liest: Kartenrand, Reiterkante,
#: Akzentkante einer gewählten Zeile.
LINE_LENGTH = 40

#: Wie weit zwei Stücke derselben Linie auseinander liegen dürfen. Eine runde
#: Ecke zeichnet Qt geglättet, und ihre Mischfarbe liegt außerhalb der
#: Toleranz — mit zwei Punkten Brücke zerfiel jeder Kartenrand noch in zwei
#: Linien, mit sechs ist er eine. Was so nah beieinander liegt, liest das Auge
#: ohnehin als ein Licht.
LINE_GAP = 6


def _accent_mask(image: QImage, theme: str) -> np.ndarray:
    """Welche Bildpunkte in einer der beiden Akzentfarben stehen."""
    image = image.convertToFormat(QImage.Format.Format_RGB32)
    width, height = image.width(), image.height()
    raw = np.frombuffer(image.constBits(), dtype=np.uint8, count=image.sizeInBytes())
    # RGB32 liegt im Speicher als B, G, R, A.
    pixels = raw.reshape(height, image.bytesPerLine() // 4, 4)[:, :width, :3].astype(np.int16)
    mask = np.zeros((height, width), dtype=bool)
    for token in ("highlight", "accent_line"):
        colour = QColor(THEMES[theme][token])
        mask |= (
            (np.abs(pixels[..., 2] - colour.red()) <= TOLERANCE)
            & (np.abs(pixels[..., 1] - colour.green()) <= TOLERANCE)
            & (np.abs(pixels[..., 0] - colour.blue()) <= TOLERANCE)
        )
    return mask


def accent_lines(window: QWidget, theme: str) -> list[QRect]:
    """Die Striche in Akzentfarbe ab :data:`LINE_LENGTH`, in Fensterkoordinaten."""
    image = window.grab().toImage()
    ratio = image.devicePixelRatio() or 1.0
    mask = _accent_mask(image, theme)
    joined = ndimage.binary_dilation(mask, iterations=LINE_GAP)
    labels, _count = ndimage.label(joined, structure=np.ones((3, 3), dtype=bool))
    found: list[QRect] = []
    for part in ndimage.find_objects(labels):
        if part is None:
            continue
        rows, columns = part
        # Die Ausdehnung ohne den Saum, den das Verbinden angelegt hat.
        width = columns.stop - columns.start - 2 * LINE_GAP
        height = rows.stop - rows.start - 2 * LINE_GAP
        if max(width, height) / ratio < LINE_LENGTH:
            continue
        found.append(
            QRect(
                int((columns.start + LINE_GAP) / ratio),
                int((rows.start + LINE_GAP) / ratio),
                max(1, int(width / ratio)),
                max(1, int(height / ratio)),
            )
        )
    return found


def accent_elements(window: MainWindow, theme: str) -> list[str]:
    """Was im Fenster die Akzentfarbe trägt: Flächen und Linien.

    Eine Fläche ist ein Blattelement, das zu einem Drittel in der Akzentfarbe
    steht (:func:`accent_areas`). Eine Linie zählt dazu, sofern sie nicht in
    einer schon gezählten Fläche liegt — ein Hauptknopf ist ein Element, nicht
    eine Fläche und drei Kanten.
    """
    areas = accent_areas(window, theme)
    found = [label for label, _rect in areas]
    for line in accent_lines(window, theme):
        if any(
            rect.adjusted(-LINE_GAP, -LINE_GAP, LINE_GAP, LINE_GAP).contains(line)
            for _label, rect in areas
        ):
            continue
        found.append(f"Linie {line.width()} × {line.height()} bei ({line.x()}, {line.y()})")
    return found


def accent_areas(window: MainWindow, theme: str) -> list[tuple[str, QRect]]:
    """Die sichtbaren Blattelemente, die überwiegend in der Akzentfarbe stehen."""
    accent = QColor(THEMES[theme]["highlight"])

    def close_enough(value: int) -> bool:
        one = QColor(value)
        return (
            abs(one.red() - accent.red()) <= TOLERANCE
            and abs(one.green() - accent.green()) <= TOLERANCE
            and abs(one.blue() - accent.blue()) <= TOLERANCE
        )

    found: list[tuple[str, QRect]] = []
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
            found.append(
                (element_name(widget), QRect(widget.mapTo(window, QPoint(0, 0)), widget.size()))
            )
    return found


def element_name(widget: QWidget) -> str:
    """Wie ein Element in der Meldung heißt: Art, Objektname, Beschriftung."""
    label = ""
    if hasattr(widget, "text"):
        try:
            label = str(widget.text())[:34]
        except Exception:  # pragma: no cover — ein Widget ohne lesbaren Text
            label = ""
    return f"{type(widget).__name__}({widget.objectName() or '-'}) {label}"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    load_operations()
    return MainWindow(Session(), UiSettings())


@pytest.fixture
def calibrated_material(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ein echtes kalibriertes Profil, ohne Daten anderer Tests zu verändern."""
    with monkeypatch.context() as patch:
        patch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
        profiles.reload()
        material = profiles.material(profiles.DEFAULT_MATERIAL)
        calibration.apply(
            calibration.from_measurements(material.id, clearance=material.clearance),
            directory=tmp_path,
        )
        yield
    profiles.reload()


def _settle(window: MainWindow, rounds: int) -> None:
    for _ in range(rounds):
        QApplication.processEvents()


def _shown(qt_app: QApplication, window: MainWindow, theme: str) -> None:
    apply_theme(qt_app, theme)
    window.resize(1280, 800)
    window.show()
    _settle(window, 30)
    window.action_theme(theme)


def _with_a_hint(window: MainWindow) -> None:
    """Ein zweites Modell unter der Platte: ein Hinweis mit Handlung im Bericht.

    Das erste Modell kommt aufgesetzt herein, das zweite an eine freie Stelle;
    mit ausgeschalteten Haken am Ladeschritt behält es die Lage aus der Datei,
    Z -10 bis +10. Die Auswertung meldet ``arrange.below_bed`` als Hinweis mit
    *Auf das Bett setzen* — vor RM-512 vorgewählt, mit Akzentkante an der
    Zeile und Hauptknopf darunter.
    """
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    assert window.session.wait_for_idle()
    step = window.session.history.operations[-1]
    assert window.session.change_params(step.id, {"place_on_bed": False, "free_spot": False})
    assert window.session.wait_for_idle()
    # Der Bericht steht vorn: Wer auf ihn sieht, ruht noch, und genau dort
    # leuchtete die vorgewählte Zeile.
    window.right.setCurrentWidget(window.report)
    # Und aufgeklappt: Ein Hinweis allein klappt die Liste nicht auf, und
    # zugeklappt sähe die Messung weder Zeile noch Knopf.
    window.report.list_toggle.setChecked(True)


@pytest.mark.parametrize("scene", ["clean", "hint"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_at_rest_only_one_element_carries_the_accent(
    qt_app: QApplication, calibrated_material: None, window: MainWindow, theme: str, scene: str
) -> None:
    """Im Ruhezustand leuchtet genau eine Stelle — Flächen und Linien zusammen.

    **Der Ruhezustand ist der Normalfall**, und genau dort wurde die Farbe
    verschwendet: Vier Elemente trugen sie gleichzeitig, bevor die
    Werkzeugdämpfung fiel; danach noch drei Kartenränder, die Kante des
    aktiven Reiters und eine vorgewählte Hinweiszeile mit Hauptknopf neben
    *Bausteine* (RM-512). Wer dann ein echtes Signal setzen will, hat keine
    Farbe mehr übrig, die auffiele.

    Ruhezustand heißt: Modell geladen, kein Werkzeug offen, nichts gewählt,
    nichts läuft, kein Fehler und keine Warnung. Ein Hinweis darf dastehen —
    die Probe ``hint`` zeigt den Bericht mit einem, samt Handlung.
    """
    _shown(qt_app, window, theme)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    if scene == "hint":
        _with_a_hint(window)
    _settle(window, 60)
    worker = window._print_findings.worker
    if worker is not None:
        assert worker.wait(10_000), "die Druckanalyse muss vor der Ruhemessung enden"
    window.tools.activate(None)
    window.object_tree.tree.clearSelection()
    _settle(window, 20)

    assert window.session.profile.material.calibrated
    assert not window.session.busy
    assert window._print_findings.worker is None
    assert not window.object_tree.selected_objects()
    findings = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(window.report.list.count())
    ]
    assert not [entry for entry in findings if entry.severity in ("error", "warning")], (
        f"ein Fehler oder eine Warnung ist kein Ruhezustand: {[entry.code for entry in findings]}"
    )
    if scene == "hint":
        assert any(entry.code == "arrange.below_bed" for entry in findings), (
            "ohne den Hinweis prüft diese Probe nichts"
        )
        assert window.report.isVisible(), "der Bericht steht vorn"
    # Das eine Licht ist *Bausteine*, wo es zu sehen ist. Steht der Bericht
    # vorn, liegt der Knopf hinter dem Reiter, und dann leuchtet nichts.
    catalog = window.selection_operations.catalog_button
    if scene == "clean":
        assert catalog.isVisible(), "ohne Auswahl steht Bausteine vorn"
    expected = [element_name(catalog)] if catalog.isVisible() else []
    lit = accent_elements(window, theme)
    assert lit == expected, (
        f"{len(lit)} Elemente tragen im Ruhezustand die Akzentfarbe, erlaubt ist "
        f"{expected or 'keines'}: {lit}. Ein Signal, das an mehreren Stellen "
        "zugleich leuchtet, ist keines mehr — welches davon soll der Kunde "
        "zuerst ansehen?"
    )


def test_the_measurement_would_notice_a_second_light(
    qt_app: QApplication, window: MainWindow
) -> None:
    """Die Gegenprobe zur Zusage darüber: Die Messung sieht ein zweites Licht.

    **Ohne diese Prüfung wäre der Wächter wertlos.** Eine Zählung, die aus
    einem falschen Farbton oder einem zu engen Filter immer null liefert, ist
    von einer erfüllten Zusage nicht zu unterscheiden — beide melden „alles in
    Ordnung". Hier wird ein zweites Element absichtlich eingefärbt, einmal als
    Fläche und einmal als Linie; findet die Messung es nicht, misst sie nichts.
    """
    _shown(qt_app, window, "dark")
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    _settle(window, 60)

    before = len(accent_elements(window, "dark"))

    accent = THEMES["dark"]["highlight"]
    # **Mit Text, nicht nur mit Farbe.** Ein leeres ``QLabel`` ist wenige
    # Punkte breit und fällt durch den Mindestgrößen-Filter — die erste
    # Fassung färbte es ein und die Messung sah nichts, was aussah, als
    # zähle sie falsch. Sie zählte richtig; das Element war zu klein.
    window.status_message.setText("Gegenprobe: ein zweites Licht")
    window.status_message.setStyleSheet(f"background: {accent};")
    _settle(window, 20)
    area = len(accent_elements(window, "dark"))

    # Und als Linie: zwei Punkte Kante über einem Schriftzug, weit unter dem
    # Drittel, das eine Fläche braucht — so stand ein Kartenrand da.
    line = THEMES["dark"]["accent_line"]
    window.status_message.setStyleSheet(f"border-top: 2px solid {line};")
    _settle(window, 20)
    lined = len(accent_elements(window, "dark"))
    width = window.status_message.width()
    window.status_message.setStyleSheet("")
    window.status_message.setText("")

    assert area > before, (
        f"die Messung hat eine absichtlich eingefärbte Fläche nicht bemerkt "
        f"({before} vorher, {area} nachher) — dann sagt ihre Null nichts aus"
    )
    assert width >= LINE_LENGTH, f"die Probe ist mit {width} Punkten kürzer als eine Linie"
    assert lined > before, (
        f"die Messung hat eine absichtlich eingefärbte Linie nicht bemerkt "
        f"({before} vorher, {lined} nachher) — Kartenränder gingen ihr wieder durch"
    )
