"""Aufnahmen am Fenster für das Messprotokoll eines Funktionsfalls (D0, RM-737).

Jede Aufnahme liest, was die Oberfläche gerade zeigt, und gibt reine Daten für
ein Feld des Protokolls zurück (Bauplan D0 §2.7): Herzschlag des Hauptfadens,
Bildzähler der Ansicht, modale und rohe Qt-Fenster, Texte mit ihrem Platzbedarf,
Felder, Tab-Kette, Layoutmaße, Schriften, Zustandsbilder, Kontraste, Symbole,
Animationen, Rollleisten, leere Zustände und Meldungen samt Handlungen. Was die
Aufnahme dazu tun muss — eine Taste drücken, mit der Maus darüberfahren —, sind
Eingabeereignisse; keine Aufnahme ruft eine Handlung direkt auf (Wächter in
``tests/test_function_bench.py``, :data:`function_bench.FORBIDDEN_CALLS`).

Die Rechnung hinter jeder Aufnahme ist ohne Fenster prüfbar: :class:`Heartbeat`,
:class:`FrameCounter`, :func:`chain_breaks`, :func:`overflowing` und
:func:`duplicate_names` bekommen Zahlen und Namen, keine Widgets. Gemessen wird
an der echten Plattform; offscreen hat keine Schrift (``tests.md``, „Isolation
heißt Betriebslage“), dort sind Breiten und Kontraste nur Platzhalter.

Geurteilt wird hier nicht. Die Schwellen und Urteile stehen in
``tools/function_checks.py``; diese Datei sagt nur, was zu sehen war.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Final

#: Takt des Herzschlags in Millisekunden. Eine Lücke weit darüber heißt: Der
#: Hauptfaden war besetzt (Prüfpunkt 6, Schwelle 100 ms in ``function_checks``).
HEARTBEAT_MS: Final = 10

#: Wie oft die Wache nach modalen Fenstern sieht (Millisekunden).
MODAL_POLL_MS: Final = 50

#: Rohe Qt-Fenster im Kundenweg (Z5). ``QFileDialog`` ist erlaubt, die übrigen nicht.
RAW_WINDOWS: Final[tuple[str, ...]] = ("QMessageBox", "QInputDialog", "QColorDialog", "QFileDialog")

#: Was als Text gilt, den der Kunde liest — Beschriftungen, Knöpfe, Haken, Reiter.
TEXT_CLASSES: Final[tuple[str, ...]] = ("QLabel", "QAbstractButton", "QGroupBox")

#: Wie viele Tabdrücke eine Kette höchstens bekommt, bevor sie als offen gilt.
MOST_TABS: Final = 60

#: Die Zustände eines Bedienelements, die als Bild aufgenommen werden (G5).
STATES: Final[tuple[str, ...]] = ("ruhe", "darueber", "fokus", "gedrueckt")


# --- Herzschlag (Prüfpunkt 6) -------------------------------------------------------------


class Heartbeat:
    """Die größte Lücke zwischen zwei Schlägen des Hauptfadens in einem Messfenster.

    Ein Zeitgeber schlägt alle :data:`HEARTBEAT_MS` Millisekunden; rechnet der
    Hauptfaden, kommt der nächste Schlag zu spät. Gemessen wird nur zwischen
    :meth:`open` und :meth:`close` — die Zeit, in der die geprüfte Handlung läuft.
    Auch eine modale Schleife lässt den Zeitgeber schlagen; eine Lücke ist
    deshalb immer eine Blockade.
    """

    def __init__(self) -> None:
        self._last: float | None = None
        self._largest_ms = 0.0
        self._open = False
        self.beats = 0

    def open(self, now: float) -> None:
        self._open = True
        self._last = now
        self._largest_ms = 0.0
        self.beats = 0

    def beat(self, now: float) -> None:
        if not self._open or self._last is None:
            return
        self._largest_ms = max(self._largest_ms, (now - self._last) * 1000.0)
        self._last = now
        self.beats += 1

    def close(self, now: float) -> float:
        """Schließt das Messfenster; die Zeit bis jetzt zählt als letzte Lücke."""
        self.beat(now)
        self._open = False
        return round(self._largest_ms, 1)

    @property
    def largest_ms(self) -> float:
        return round(self._largest_ms, 1)


def start_heartbeat(owner: Any, heartbeat: Heartbeat) -> Any:
    """Der Zeitgeber, der :class:`Heartbeat` schlagen lässt; gehört ``owner``."""
    from PySide6.QtCore import QTimer

    timer = QTimer(owner)
    timer.setInterval(HEARTBEAT_MS)
    timer.timeout.connect(lambda: heartbeat.beat(time.perf_counter()))
    timer.start()
    return timer


# --- Bildzähler (Z1, B11) ------------------------------------------------------------------


class FrameCounter:
    """Zeitpunkte, zu denen die Ansicht ein Bild gemalt hat.

    Die Ansicht hat keinen eigenen Zähler (B11); wie in ``window_bench`` wird im
    Kindprozess ``render`` des Renderers umwickelt — eine Messung, kein App-Code.
    :meth:`latencies` sagt je Eingabeereignis, wann das nächste Bild kam.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self.clock = clock
        self.times: list[float] = []

    def wrap(self, renderer: Any) -> bool:
        """Umwickelt ``renderer.render``; ``False``, wenn es keinen Renderer gibt."""
        if renderer is None or not callable(getattr(renderer, "render", None)):
            return False
        original = renderer.render

        def counted(*args: Any, **kwargs: Any) -> Any:
            try:
                return original(*args, **kwargs)
            finally:
                self.times.append(self.clock())

        renderer.render = counted
        return True

    def first_after(self, moment: float) -> float | None:
        return next((stamp for stamp in self.times if stamp >= moment), None)

    def latencies(self, events: Sequence[float]) -> list[float | None]:
        """Je Ereignis die Millisekunden bis zum nächsten Bild; ``None`` ohne Bild."""
        found: list[float | None] = []
        for moment in events:
            frame = self.first_after(moment)
            found.append(None if frame is None else round((frame - moment) * 1000.0, 1))
        return found


def reference_factor() -> float:
    """Wie schnell dieser Rechner gegen die Referenzmaschine ist (§31).

    Dieselbe Probe wie die Zeitschätzung der Vollerkennung
    (``perceive.recognition_time``): Referenzzeit durch die Zeit hier. Eine
    gemessene Dauer mal diesem Faktor ist die Dauer auf der Referenz.
    """
    from app.core.perceive import recognition_time

    return recognition_time.PROBE_REFERENCE_SECONDS / recognition_time.calibrate()


# --- Modale und rohe Fenster (E6, Z2, Z5) ------------------------------------------------------


def window_record(widget: Any, moment: float) -> dict[str, Any]:
    """Klasse, Titel, Knöpfe und Kennzeichen eines Fensters, ohne es anzufassen."""
    from PySide6.QtWidgets import QAbstractButton, QLabel

    classes = [cls.__name__ for cls in type(widget).__mro__]
    raw = next((name for name in RAW_WINDOWS if name in classes), "")
    return {
        "class": type(widget).__name__,
        "raw": raw,
        "title": widget.windowTitle(),
        "text": [label.text() for label in widget.findChildren(QLabel) if label.text()][:6],
        "buttons": [
            button.text() for button in widget.findChildren(QAbstractButton) if button.text()
        ],
        "t": round(moment, 4),
    }


class ModalWatch:
    """Notiert jedes modale Fenster und jedes Aufklappmenü, das im Lauf erscheint.

    Nur lesend: Die Wache schließt nichts. Was ein Fall öffnet und bedient,
    bedient er selbst über Eingabeereignisse; was liegen bleibt, räumt der Fall
    am Ende seiner Phase mit Escape ab und vermerkt es.
    """

    def __init__(self, began: float) -> None:
        self.began = began
        self.modals: list[dict[str, Any]] = []
        self.raw_windows: list[dict[str, Any]] = []
        self.windows: list[dict[str, Any]] = []
        self._seen: set[int] = set()
        self._windows_seen: set[int] = set()

    def poll(self) -> None:
        from PySide6.QtWidgets import QApplication

        now = time.perf_counter() - self.began
        for widget in (QApplication.activeModalWidget(), QApplication.activePopupWidget()):
            if widget is None or id(widget) in self._seen:
                continue
            self._seen.add(id(widget))
            record = window_record(widget, now)
            self.modals.append(record)
            if record["raw"]:
                self.raw_windows.append(record)
        for widget in QApplication.topLevelWidgets():
            if not widget.isVisible() or id(widget) in self._windows_seen:
                continue
            self._windows_seen.add(id(widget))
            record = window_record(widget, now)
            self.windows.append(
                {"class": record["class"], "title": record["title"], "t": record["t"]}
            )
            if record["raw"] and id(widget) not in self._seen:
                self._seen.add(id(widget))
                self.raw_windows.append(record)

    def opened(self, class_name: str) -> bool:
        """Ob ein Fenster dieser Klasse im Lauf erschien — das Handbuch für V6."""
        return any(entry["class"] == class_name for entry in self.windows)

    def start(self, owner: Any) -> Any:
        from PySide6.QtCore import QTimer

        timer = QTimer(owner)
        timer.setInterval(MODAL_POLL_MS)
        timer.timeout.connect(self.poll)
        timer.start()
        return timer


def modal_now() -> dict[str, Any] | None:
    """Das modale Fenster jetzt — Z2 fragt es nach jeder geprüften Handlung."""
    from PySide6.QtWidgets import QApplication

    widget = QApplication.activeModalWidget()
    return None if widget is None else window_record(widget, 0.0)


# --- Texte und Felder (Prüfpunkt 8, 9; V1 bis V3, E5) -------------------------------------


def mark_of(widget: Any) -> str:
    """Das Wortschatzkennzeichen eines Widgets, sonst sein ``objectName``."""
    from app.core.guides import TARGET_PROPERTY  # type: ignore[attr-defined]

    mark = widget.property(TARGET_PROPERTY)
    return str(mark) if mark else widget.objectName()


def _visible(widget: Any) -> bool:
    return bool(widget.isVisible()) and widget.width() > 0 and widget.height() > 0


def _text_of(widget: Any) -> str:
    from PySide6.QtWidgets import QGroupBox

    if isinstance(widget, QGroupBox):
        return str(widget.title())
    text = widget.text() if callable(getattr(widget, "text", None)) else ""
    return str(text or "")


def text_entries(root: Any) -> list[dict[str, Any]]:
    """Jeder sichtbare Text unter ``root`` mit Bedarf und verfügbarer Breite in Pixeln.

    Der Bedarf ist die Breite der längsten Zeile in der Schrift des Trägers; ein
    umbrechender Text braucht nur sein längstes Wort. Abgeschnitten heißt: Bedarf
    über dem Platz (Prüfpunkt 9, Konzept §4). Reiter einer Leiste stehen mit
    ihrem eigenen Rechteck da.
    """
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabBar

    found: list[dict[str, Any]] = []
    for widget in (
        root.findChildren(QLabel)
        + root.findChildren(QAbstractButton)
        + root.findChildren(QGroupBox)
    ):
        if not _visible(widget):
            continue
        text = _text_of(widget).replace("&", "")
        if not text.strip() or text.lstrip().startswith("<"):
            continue
        metrics = widget.fontMetrics()
        lines = text.splitlines() or [text]
        wraps = bool(getattr(widget, "wordWrap", lambda: False)())
        pieces = [word for line in lines for word in line.split()] if wraps else lines
        needed = max((metrics.horizontalAdvance(piece) for piece in pieces), default=0)
        available = widget.contentsRect().width()
        found.append(
            {
                "text": text,
                "carrier": type(widget).__name__,
                "mark": mark_of(widget),
                "needed": needed,
                "available": available,
                "wraps": wraps,
                "cut": needed > available,
            }
        )
    for bar in root.findChildren(QTabBar):
        if not _visible(bar):
            continue
        metrics = bar.fontMetrics()
        for index in range(bar.count()):
            text = bar.tabText(index).replace("&", "")
            available = bar.tabRect(index).width()
            needed = metrics.horizontalAdvance(text)
            found.append(
                {
                    "text": text,
                    "carrier": "QTabBar",
                    "mark": mark_of(bar),
                    "needed": needed,
                    "available": available,
                    "wraps": False,
                    "cut": needed > available,
                }
            )
    return found


def overflowing(entries: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Die Texte, deren Bedarf über ihrem Platz liegt."""
    return [
        entry for entry in entries if int(entry.get("needed", 0)) > int(entry.get("available", 0))
    ]


def field_entries(root: Any) -> list[dict[str, Any]]:
    """Jedes Eingabefeld unter ``root``: Beschriftung, Name, Beschreibung, Kurzhilfe, vorn.

    *Vorn* heißt sichtbar, ohne eine Klappe zu öffnen — E5 zählt diese Felder.
    Die Beschriftung kommt aus dem Formular, in dem das Feld steht.
    """
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QFormLayout,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    captions: dict[int, str] = {}
    for form in root.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label is None or field is None or label.widget() is None or field.widget() is None:
                continue
            captions[id(field.widget())] = _text_of(label.widget())
    found: list[dict[str, Any]] = []
    kinds = (QAbstractSpinBox, QLineEdit, QComboBox, QCheckBox, QPlainTextEdit, QTextEdit)
    seen: set[int] = set()
    for kind in kinds:
        for widget in root.findChildren(kind):
            if id(widget) in seen:
                continue
            seen.add(id(widget))
            # Das Textfeld in einer Zahl oder Auswahl ist kein eigenes Feld.
            parent = widget.parentWidget()
            if isinstance(widget, QLineEdit) and isinstance(parent, (QAbstractSpinBox, QComboBox)):
                continue
            found.append(
                {
                    "class": type(widget).__name__,
                    "mark": mark_of(widget),
                    "caption": captions.get(
                        id(widget), _text_of(widget) if isinstance(widget, QCheckBox) else ""
                    ),
                    "name": widget.accessibleName(),
                    "description": widget.accessibleDescription(),
                    "tooltip": widget.toolTip(),
                    "front": bool(widget.isVisible()),
                    "enabled": bool(widget.isEnabled()),
                }
            )
    return found


def duplicate_names(names: Iterable[str]) -> list[str]:
    """Zugängliche Namen, die mehr als einmal vorkommen (Prüfpunkt 10)."""
    counted: dict[str, int] = {}
    for name in names:
        if name:
            counted[name] = counted.get(name, 0) + 1
    return sorted(name for name, count in counted.items() if count > 1)


# --- Tab-Kette (Prüfpunkt 10) ---------------------------------------------------------------


def focus_record(widget: Any, root: Any) -> dict[str, Any]:
    """Das Fokuswidget: Klasse, Kennzeichen, Name und Lage relativ zu ``root``."""
    from PySide6.QtCore import QPoint

    corner = (
        widget.mapTo(root, QPoint(0, 0))
        if root.isAncestorOf(widget)
        else widget.mapToGlobal(QPoint(0, 0))
    )
    return {
        "class": type(widget).__name__,
        "mark": mark_of(widget),
        "name": widget.accessibleName(),
        "x": corner.x(),
        "y": corner.y(),
        "inside": bool(root is widget or root.isAncestorOf(widget)),
    }


def tab_chain(
    root: Any, press_tab: Callable[[], None], limit: int = MOST_TABS
) -> list[dict[str, Any]]:
    """Die Tab-Kette ab dem Fokus: je Druck das Fokuswidget, bis sie sich schließt.

    ``press_tab`` drückt Tab am Fokuswidget (``QtPorts.keys``) — die Kette wird
    gedrückt, nicht aus ``nextInFocusChain`` gelesen: Gemessen wird, was die
    Tastatur tut. Die Kette endet, wenn ein Widget wiederkommt oder der Fokus
    ``root`` verlässt.
    """
    from PySide6.QtWidgets import QApplication

    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    first = QApplication.focusWidget()
    if first is not None:
        seen.add(id(first))
        chain.append(focus_record(first, root))
    for _ in range(limit):
        press_tab()
        QApplication.processEvents()
        current = QApplication.focusWidget()
        if current is None:
            break
        record = focus_record(current, root)
        chain.append(record)
        if id(current) in seen or not record["inside"]:
            break
        seen.add(id(current))
    return chain


#: Wie weit ein Feld höher liegen darf als sein Vorgänger und doch als „weiter
#: unten“ gilt: Felder einer Zeile schwanken um ihre Mittellinie.
SAME_LINE_PX: Final = 8


def chain_breaks(chain: Sequence[Mapping[str, Any]]) -> list[int]:
    """Wo die Kette gegen die Lesefolge springt: Stellen, an denen es nach oben geht.

    Lesefolge heißt zeilenweise von oben, in der Zeile von links. Ein Sprung
    zurück an den Anfang am Ende der Kette ist ihr Schluss, kein Bruch.
    """
    breaks: list[int] = []
    inside = [entry for entry in chain if entry.get("inside", True)]
    for index in range(1, len(inside)):
        before, after = inside[index - 1], inside[index]
        if index == len(inside) - 1 and after.get("mark") == inside[0].get("mark"):
            break
        rises = int(after["y"]) < int(before["y"]) - SAME_LINE_PX
        same_line = abs(int(after["y"]) - int(before["y"])) <= SAME_LINE_PX
        if rises or (same_line and int(after["x"]) < int(before["x"])):
            breaks.append(index)
    return breaks


# --- Layout, Schrift, Kontrast, Symbole, Animationen, Rollleisten (G1 bis G8, Z6) ---------


def layout_entries(root: Any) -> list[dict[str, Any]]:
    """Abstände und Ränder jedes Layouts (G2), Kanten der Formularspalten (G3)."""
    from PySide6.QtWidgets import QFormLayout, QLayout, QWidget

    found: list[dict[str, Any]] = []
    for widget in [root, *root.findChildren(QWidget)]:
        layout = widget.layout()
        if not isinstance(layout, QLayout) or not _visible(widget):
            continue
        margins = layout.contentsMargins()
        entry: dict[str, Any] = {
            "owner": type(widget).__name__,
            "mark": mark_of(widget),
            "layout": type(layout).__name__,
            "spacing": layout.spacing(),
            "margins": [margins.left(), margins.top(), margins.right(), margins.bottom()],
        }
        if isinstance(layout, QFormLayout):
            edges: list[list[int]] = []
            for row in range(layout.rowCount()):
                label = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                field = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if field is None or field.widget() is None or not field.widget().isVisible():
                    continue
                label_x = (
                    label.widget().x() if label is not None and label.widget() is not None else -1
                )
                edges.append([label_x, field.widget().x()])
            entry["form_edges"] = edges
            entry["horizontal_spacing"] = layout.horizontalSpacing()
            entry["vertical_spacing"] = layout.verticalSpacing()
        found.append(entry)
    return found


def font_entries(root: Any) -> list[dict[str, Any]]:
    """Schriftgröße, Gewicht und Stufe je Textträger; Schrift im Stylesheet (G4)."""
    from PySide6.QtWidgets import QAbstractButton, QLabel

    found: list[dict[str, Any]] = []
    for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton):
        if not _visible(widget) or not _text_of(widget).strip():
            continue
        font = widget.font()
        sheet = widget.styleSheet().lower()
        found.append(
            {
                "mark": mark_of(widget),
                "carrier": type(widget).__name__,
                "point_size": round(font.pointSizeF(), 2),
                "weight": int(font.weight()),
                "level": str(widget.property("level") or ""),
                "sheet_font_size": "font-size" in sheet,
                "sheet_colour": "color:" in sheet.replace(" ", ""),
            }
        )
    return found


def contrast_entries(root: Any) -> list[dict[str, Any]]:
    """Schrift gegen Hintergrund je Textträger, gerechnet mit ``theme.contrast_ratio`` (G6).

    Die Farben kommen aus der Palette des Trägers, die das Stylesheet beim
    Polieren setzt; ein Bildpunkt wäre genauer, liegt aber unter Kantenglättung.
    """
    from PySide6.QtWidgets import QAbstractButton, QLabel

    from app.ui.theme import contrast_ratio

    found: list[dict[str, Any]] = []
    for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton):
        if not _visible(widget) or not _text_of(widget).strip():
            continue
        palette = widget.palette()
        foreground = palette.color(widget.foregroundRole()).name()
        background = palette.color(widget.backgroundRole()).name()
        font = widget.font()
        found.append(
            {
                "mark": mark_of(widget),
                "text": _text_of(widget)[:60],
                "foreground": foreground,
                "background": background,
                "ratio": round(contrast_ratio(foreground, background), 2),
                "large": font.pointSizeF() >= 14 or (font.pointSizeF() >= 11 and font.bold()),
                "enabled": bool(widget.isEnabled()),
            }
        )
    return found


def icon_entries(root: Any) -> list[dict[str, Any]]:
    """Bedienelemente ohne Text: Symbol, Kurzhilfe, Kürzel, Bildschärfe (G7, Z6)."""
    from PySide6.QtWidgets import QAbstractButton, QToolButton

    found: list[dict[str, Any]] = []
    for button in root.findChildren(QAbstractButton):
        if not _visible(button) or _text_of(button).strip():
            continue
        icon = button.icon()
        ratio = float(button.devicePixelRatioF())
        pixmap = icon.pixmap(button.iconSize(), ratio) if not icon.isNull() else None
        action = button.defaultAction() if isinstance(button, QToolButton) else None
        shortcut = action.shortcut().toString() if action is not None else ""
        found.append(
            {
                "mark": mark_of(button),
                "class": type(button).__name__,
                "has_icon": not icon.isNull(),
                "tooltip": button.toolTip(),
                "shortcut": shortcut,
                "shortcut_in_tooltip": bool(shortcut) and shortcut in button.toolTip(),
                "screen_ratio": ratio,
                "pixmap_ratio": float(pixmap.devicePixelRatio()) if pixmap is not None else None,
            }
        )
    return found


def animation_entries(root: Any) -> list[dict[str, Any]]:
    """Laufende und vorbereitete Übergänge unter ``root`` mit ihrer Dauer (G8)."""
    from PySide6.QtCore import QAbstractAnimation, QVariantAnimation

    found: list[dict[str, Any]] = []
    for animation in root.findChildren(QAbstractAnimation):
        duration = animation.duration()
        found.append(
            {
                "class": type(animation).__name__,
                "owner": type(animation.parent()).__name__
                if animation.parent() is not None
                else "",
                "duration_ms": duration,
                "running": animation.state() == QAbstractAnimation.State.Running,
                "property": (
                    bytes(animation.propertyName()).decode()
                    if isinstance(animation, QVariantAnimation)
                    and hasattr(animation, "propertyName")
                    else ""
                ),
            }
        )
    return found


def scrollbar_entries(root: Any) -> list[dict[str, Any]]:
    """Rollbereiche mit sichtbarer senkrechter Leiste — vorn braucht keiner eine (Z6)."""
    from PySide6.QtWidgets import QAbstractScrollArea

    found: list[dict[str, Any]] = []
    for area in root.findChildren(QAbstractScrollArea):
        if not _visible(area):
            continue
        bar = area.verticalScrollBar()
        found.append(
            {
                "mark": mark_of(area),
                "class": type(area).__name__,
                "vertical": bool(bar.isVisible()),
                "range": bar.maximum() - bar.minimum(),
                "height": area.height(),
            }
        )
    return found


def accent_count(root: Any) -> int:
    """Wie viele Hauptknöpfe im Ruhezustand sichtbar sind (G1, Z6 hell und dunkel)."""
    from PySide6.QtWidgets import QPushButton

    return sum(
        1 for button in root.findChildren(QPushButton) if _visible(button) and button.isDefault()
    )


def primary_entries(root: Any) -> list[dict[str, Any]]:
    """Hauptknöpfe mit Halbfett und Default je Fenster (G1)."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QPushButton

    return [
        {
            "mark": mark_of(button),
            "text": _text_of(button),
            "default": bool(button.isDefault()),
            "demibold": button.font().weight() >= QFont.Weight.DemiBold,
        }
        for button in root.findChildren(QPushButton)
        if _visible(button)
        and (button.isDefault() or button.font().weight() >= QFont.Weight.DemiBold)
    ]


# --- Zustandsbilder (G5) --------------------------------------------------------------------------


def _picture_digest(widget: Any) -> str:
    image = widget.grab().toImage()
    data = image.constBits()
    return hashlib.sha256(bytes(data)).hexdigest()[:16]


def state_images(widget: Any) -> dict[str, str]:
    """Ein Bildabdruck je Zustand, hergestellt über gesendete Ereignisse (G5).

    Darüber: die Maus fährt hinein. Fokus: wie ein Tab. Gedrückt: die Taste
    unten, dann außerhalb losgelassen — so löst der Knopf nicht aus. Gleiche
    Abdrücke zweier Zustände heißen: nicht unterscheidbar.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    images: dict[str, str] = {"ruhe": _picture_digest(widget)}
    centre = widget.rect().center()
    QTest.mouseMove(widget, centre)
    QApplication.processEvents()
    images["darueber"] = _picture_digest(widget)
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    images["fokus"] = _picture_digest(widget)
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    QApplication.processEvents()
    images["gedrueckt"] = _picture_digest(widget)
    outside = QPoint(-widget.width(), -widget.height())
    QTest.mouseMove(widget, outside)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, outside)
    QApplication.processEvents()
    return images


def alike_states(images: Mapping[str, str]) -> list[tuple[str, str]]:
    """Zustandspaare mit gleichem Abdruck — nicht unterscheidbar (G5)."""
    names = [name for name in STATES if name in images]
    return [
        (first, second)
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if images[first] == images[second]
    ]


# --- Leere Zustände, Meldungen, Handlungen (Z4, E7, Prüfpunkt 7) ---------------------------------


def empty_states(root: Any) -> list[dict[str, Any]]:
    """Sichtbare leere Listen und Bäume mit dem Text und den Knöpfen daneben (Z4, E7)."""
    from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QLabel

    found: list[dict[str, Any]] = []
    for view in root.findChildren(QAbstractItemView):
        model = view.model()
        if not _visible(view) or model is None or model.rowCount() > 0:
            continue
        parent = view.parentWidget()
        neighbours = parent.findChildren(QLabel) if parent is not None else []
        buttons = parent.findChildren(QAbstractButton) if parent is not None else []
        found.append(
            {
                "mark": mark_of(view),
                "class": type(view).__name__,
                "texts": [
                    _text_of(label) for label in neighbours if _visible(label) and _text_of(label)
                ],
                "buttons": [
                    {"text": _text_of(button), "mark": mark_of(button)}
                    for button in buttons
                    if _visible(button)
                ],
            }
        )
    return found


def message_entries(window: Any) -> list[dict[str, Any]]:
    """Was die Oberfläche gerade meldet: Statuszeile, Hinweise, gesperrte Knöpfe mit Grund.

    Je Meldung ihre Handlungen — die sichtbaren Knöpfe im selben Hinweis — mit
    Text und Kennzeichen; ob sie wirken, misst der Fall, der sie anklickt
    (Prüfpunkt 7, V5).
    """
    from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QPushButton

    found: list[dict[str, Any]] = []
    status = window.statusBar().currentMessage() if window.statusBar() is not None else ""
    if status:
        found.append({"carrier": "statusbar", "text": status, "actions": []})
    for frame in window.findChildren(QFrame):
        name = frame.objectName().lower()
        if not _visible(frame) or not any(
            word in name for word in ("notice", "hint", "error", "advice")
        ):
            continue
        texts = [
            _text_of(label)
            for label in frame.findChildren(QLabel)
            if _visible(label) and _text_of(label)
        ]
        if not texts:
            continue
        found.append(
            {
                "carrier": frame.objectName(),
                "text": " ".join(texts),
                "actions": [
                    {
                        "label": _text_of(button),
                        "target": mark_of(button),
                        "enabled": bool(button.isEnabled()),
                    }
                    for button in frame.findChildren(QAbstractButton)
                    if _visible(button) and _text_of(button)
                ],
            }
        )
    for button in window.findChildren(QPushButton):
        reason = button.accessibleDescription() or button.toolTip()
        if _visible(button) and not button.isEnabled() and reason:
            found.append(
                {
                    "carrier": "gesperrt",
                    "text": reason,
                    "target": mark_of(button),
                    "label": _text_of(button),
                    "actions": [],
                }
            )
    return found


def visible_texts(root: Any) -> list[str]:
    """Die sichtbaren Texte unter ``root`` — für Band, Beschriftung beim Überfahren, Hinweise."""
    from PySide6.QtWidgets import QLabel

    return [
        _text_of(label)
        for label in root.findChildren(QLabel)
        if _visible(label) and _text_of(label)
    ]


def sheet_snapshot(root: Any) -> dict[str, Any]:
    """Alles, was eine offene Fläche für G1 bis G8 und Z6 hergibt, in einem Zug."""
    return {
        "layout": layout_entries(root),
        "fonts": font_entries(root),
        "contrast": contrast_entries(root),
        "icons": icon_entries(root),
        "animations": animation_entries(root),
        "scrollbars": scrollbar_entries(root),
        "primaries": primary_entries(root),
        "accents": accent_count(root),
    }
