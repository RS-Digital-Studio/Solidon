"""Aufnahmen am Fenster für das Messprotokoll eines Funktionsfalls (D0, RM-737).

Jede Aufnahme liest, was die Oberfläche gerade zeigt, und gibt die Einträge
eines Felds im Messprotokoll zurück — in der Form, die das Schema von D0-U
vorgibt (``tools/function_checks.PROTOCOL_SCHEMA``): Herzschlag des
Hauptfadens, Bildzähler der Ansicht, modale, rohe und alle Fenster, Texte mit
ihrem Platzbedarf, Felder, Tab-Kette, Layoutmaße, Schriften, Zustandsbilder,
Kontraste, Symbole, Animationen, Rollleisten, leere Zustände und Meldungen samt
Handlungen. Was die Aufnahme dazu tun muss — eine Taste drücken, mit der Maus
darüberfahren —, sind Eingabeereignisse; keine Aufnahme ruft eine Handlung
direkt auf (Wächter in ``tests/test_function_bench.py``,
:data:`function_bench.FORBIDDEN_CALLS`).

Die Rechnung hinter den Aufnahmen ist ohne Fenster prüfbar: :class:`Heartbeat`,
:class:`FrameCounter`, :func:`chain_breaks`, :func:`overflowing`,
:func:`duplicate_names` und :func:`modal_allowed` bekommen Zahlen, Namen und
Aufrufer, keine Widgets. Gemessen wird an der echten Plattform; offscreen hat
keine Schrift (``tests.md``, „Isolation heißt Betriebslage“), dort sind Breiten
und Kontraste nur Platzhalter.

Geurteilt wird hier nicht. Die Schwellen und Urteile stehen in
``tools/function_checks.py`` und ``tools/function_judges.py``; diese Datei sagt
nur, was zu sehen war.
"""

from __future__ import annotations

import hashlib
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Final

#: Takt des Herzschlags in Millisekunden. Eine Lücke weit darüber heißt: Der
#: Hauptfaden war besetzt (Prüfpunkt 6, ``function_checks.MAIN_GAP_MS``).
HEARTBEAT_MS: Final = 10

#: Wie oft die Wache nach modalen Fenstern sieht (Millisekunden).
MODAL_POLL_MS: Final = 50

#: Wie viele Tabdrücke eine Kette höchstens bekommt, bevor sie als offen gilt.
MOST_TABS: Final = 60

#: Die Zustände eines Bedienelements, die als Bild aufgenommen werden (G5) —
#: die Namen des Schemas. *Deaktiviert*, *beschäftigt* und *Fehler* lassen sich
#: nicht über Ereignisse herstellen; sie fehlen, und das Urteil sagt es.
STATES: Final[tuple[str, ...]] = ("rest", "hover", "focus", "pressed")

#: Dialogklassen, die als Fenster erlaubt sind (Konzept §4, Z2 und Z5): die
#: Dateidialoge, der KI- und der Druckhinweis und die Rückfrage nach Regel 21
#: (``AskDialog``, auch die Frage vor der Vollerkennung, Regel 19).
ALLOWED_CLASSES: Final[frozenset[str]] = frozenset(
    {"QFileDialog", "AiDisclosureDialog", "PrintDisclosureDialog", "AskDialog"}
)

#: Funktionen, aus denen eine Rückfrage erlaubt ist (Regel 19 und ihre Ausnahmen,
#: ``fenster.md`` „Rückfragen“): Speicherfrage, verworfene Schritte, Export,
#: Übergabe, Löschen im Verlauf. Erkannt am Aufrufstapel des ``exec()`` — so
#: hängt die Zuordnung an keiner Übersetzung. Ein Wächter hält, dass jede
#: dieser Funktionen in ``app/ui`` steht.
ALLOWED_CALLERS: Final[frozenset[str]] = frozenset(
    {
        "confirm_unsaved",
        "confirm_discard",
        "confirm_export",
        "confirm_handover",
        "remove_history_operations",
    }
)

#: Rohe Qt-Fenster: Klassen, an denen Z5 zählt (``function_checks.RAW_CLASSES``
#: und der erlaubte Dateidialog).
RAW_BASES: Final[tuple[str, ...]] = ("QMessageBox", "QInputDialog", "QColorDialog", "QFileDialog")


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


# --- Fenster: modal, roh, alle (E6, Z2, Z5, V6) -----------------------------------------------


def callers() -> list[str]:
    """Die Python-Funktionen auf dem Stapel, von innen nach außen.

    Läuft die Wache in der Schleife eines ``exec()``, steht die Funktion, die
    den Dialog geöffnet hat, darunter — auch über die Qt-Schleife hinweg.
    """
    names: list[str] = []
    frame = sys._getframe(1)
    while frame is not None:
        names.append(frame.f_code.co_name)
        frame = frame.f_back
    return names


def modal_allowed(classes: Sequence[str], stack: Sequence[str]) -> bool:
    """Ob ein Fenster zu den erlaubten gehört: Klasse oder öffnende Funktion (Z2, E6)."""
    return bool(ALLOWED_CLASSES & set(classes)) or bool(ALLOWED_CALLERS & set(stack))


def is_question(class_name: str, buttons: Sequence[str]) -> bool:
    """Eine Nachfrage (E6) statt einer Meldung (Z2): eine Wahl zwischen mindestens zwei Knöpfen."""
    return class_name == "AskDialog" or len([text for text in buttons if text]) >= 2


def _classes(widget: Any) -> list[str]:
    return [cls.__name__ for cls in type(widget).__mro__]


def _buttons(widget: Any) -> list[str]:
    from PySide6.QtWidgets import QAbstractButton

    return [button.text() for button in widget.findChildren(QAbstractButton) if button.text()]


def modal_now() -> dict[str, Any] | None:
    """Das modale Fenster jetzt, oder keins — Z2 fragt es nach jeder geprüften Handlung."""
    from PySide6.QtWidgets import QApplication

    widget = QApplication.activeModalWidget()
    return (
        None if widget is None else {"class": type(widget).__name__, "title": widget.windowTitle()}
    )


class ModalWatch:
    """Notiert jedes modale Fenster, jedes rohe Qt-Fenster und jedes Fenster des Laufs.

    Nur lesend: Die Wache schließt nichts. Was ein Fall öffnet und bedient,
    bedient er selbst über Eingabeereignisse; was liegen bleibt, räumt der Fall
    am Ende seiner Phase mit Escape ab. ``own`` nennt Klassen, die die Zeile
    selbst öffnet (ihre Bedienfläche) — sie zählen als erlaubt.
    """

    def __init__(self, began: float) -> None:
        self.began = began
        self.modals: list[dict[str, Any]] = []
        self.raw_windows: list[dict[str, Any]] = []
        self.windows: list[dict[str, Any]] = []
        self.own: set[str] = set()
        self.after: dict[str, dict[str, Any] | None] = {}
        self._seen: set[int] = set()
        self._windows_seen: set[int] = set()

    def poll(self) -> None:
        from PySide6.QtWidgets import QApplication

        stack = callers()
        widget = QApplication.activeModalWidget()
        if widget is not None and id(widget) not in self._seen:
            self._seen.add(id(widget))
            classes = _classes(widget)
            allowed = modal_allowed(classes, stack) or type(widget).__name__ in self.own
            buttons = _buttons(widget)
            self.modals.append(
                {
                    "class": type(widget).__name__,
                    "title": widget.windowTitle(),
                    "allowed": allowed,
                    "question": is_question(type(widget).__name__, buttons),
                }
            )
            raw = next((name for name in RAW_BASES if name in classes), "")
            if raw:
                self.raw_windows.append(
                    {
                        "class": raw,
                        "title": widget.windowTitle(),
                        "allowed": allowed,
                        "own_class": type(widget).__name__,
                    }
                )
        for widget in QApplication.topLevelWidgets():
            if not widget.isVisible() or id(widget) in self._windows_seen:
                continue
            self._windows_seen.add(id(widget))
            self.windows.append({"class": type(widget).__name__, "title": widget.windowTitle()})
            classes = _classes(widget)
            raw = next((name for name in RAW_BASES if name in classes), "")
            if raw and id(widget) not in self._seen:
                self._seen.add(id(widget))
                self.raw_windows.append(
                    {
                        "class": raw,
                        "title": widget.windowTitle(),
                        "allowed": modal_allowed(classes, stack),
                        "own_class": type(widget).__name__,
                    }
                )

    def note_after(self, label: str) -> None:
        """Z2: das modale Fenster nach einer geprüften Handlung, oder keins."""
        self.after[label] = modal_now()

    def modal_entries(self) -> list[dict[str, Any]]:
        """``modals`` fürs Protokoll; die eigene Bedienfläche der Zeile zählt als erlaubt.

        Erst am Ende steht fest, welche Klasse die Zeile selbst öffnet
        (``own``) — ihr Dialog ist die Funktion, keine Nachfrage und keine Meldung.
        """
        return [
            {**entry, "allowed": entry["allowed"] or entry["class"] in self.own}
            for entry in self.modals
        ]

    def raw_entries(self) -> list[dict[str, Any]]:
        """``raw_windows`` fürs Protokoll, mit derselben Ausnahme für die eigene Fläche."""
        return [
            {
                "class": entry["class"],
                "title": entry["title"],
                "allowed": entry["allowed"] or entry["own_class"] in self.own,
            }
            for entry in self.raw_windows
        ]

    def start(self, owner: Any) -> Any:
        from PySide6.QtCore import QTimer

        timer = QTimer(owner)
        timer.setInterval(MODAL_POLL_MS)
        timer.timeout.connect(self.poll)
        timer.start()
        return timer


# --- Texte und Felder (Prüfpunkt 8, 9; V1 bis V3, E5) -------------------------------------


def mark_of(widget: Any) -> str:
    """Das Wortschatzkennzeichen eines Widgets, sonst sein ``objectName``."""
    from app.core.guides import TARGET_PROPERTY

    mark = widget.property(TARGET_PROPERTY)
    return str(mark) if mark else widget.objectName()


def name_of(widget: Any) -> str:
    """Wie ein Widget im Protokoll heißt: sichtbarer Text, sonst Name, Kennzeichen, Klasse."""
    return _text_of(widget) or widget.accessibleName() or mark_of(widget) or type(widget).__name__


def _visible(widget: Any) -> bool:
    return bool(widget.isVisible()) and widget.width() > 0 and widget.height() > 0


def _text_of(widget: Any) -> str:
    from PySide6.QtWidgets import QGroupBox

    if isinstance(widget, QGroupBox):
        return str(widget.title())
    text = widget.text() if callable(getattr(widget, "text", None)) else ""
    return str(text or "").replace("&", "")


def _top(widget: Any, root: Any) -> int:
    from PySide6.QtCore import QPoint

    return int(widget.mapTo(root, QPoint(0, 0)).y()) if root.isAncestorOf(widget) else 0


def _input_widgets(root: Any) -> list[Any]:
    """Die sichtbaren Eingabefelder unter ``root``, ohne die Textzeile in einer Zahl."""
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    found: list[Any] = []
    seen: set[int] = set()
    for kind in (QAbstractSpinBox, QLineEdit, QComboBox, QCheckBox, QPlainTextEdit, QTextEdit):
        for widget in root.findChildren(kind):
            if id(widget) in seen:
                continue
            seen.add(id(widget))
            parent = widget.parentWidget()
            if isinstance(widget, QLineEdit) and isinstance(parent, (QAbstractSpinBox, QComboBox)):
                continue
            found.append(widget)
    return found


def text_entries(root: Any) -> list[dict[str, Any]]:
    """Jeder sichtbare Text unter ``root`` mit Bedarf und Breite in Pixeln (Schema ``texts``).

    Der Bedarf ist die Breite der längsten Zeile in der Schrift des Trägers; ein
    umbrechender Text braucht nur sein längstes Wort. ``cut`` heißt Bedarf über
    der Breite (Prüfpunkt 9). ``lead`` heißt: steht über dem ersten Feld (E5).
    Reiter einer Leiste stehen mit ihrem eigenen Rechteck da.
    """
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabBar

    fields = [field for field in _input_widgets(root) if _visible(field)]
    first_field = min((_top(field, root) for field in fields), default=None)
    found: list[dict[str, Any]] = []
    carriers = root.findChildren(QLabel) + root.findChildren(QAbstractButton)
    for widget in carriers + root.findChildren(QGroupBox):
        if not _visible(widget):
            continue
        text = _text_of(widget)
        if not text.strip() or text.lstrip().startswith("<"):
            continue
        metrics = widget.fontMetrics()
        lines = text.splitlines() or [text]
        wraps = bool(getattr(widget, "wordWrap", lambda: False)())
        pieces = [word for line in lines for word in line.split()] if wraps else lines
        need = max((metrics.horizontalAdvance(piece) for piece in pieces), default=0)
        width = widget.contentsRect().width()
        bottom = _top(widget, root) + widget.height()
        found.append(
            {
                "text": text,
                "carrier": type(widget).__name__,
                "need_px": need,
                "width_px": width,
                "cut": need > width,
                "lead": first_field is not None and bottom <= first_field,
            }
        )
    for bar in root.findChildren(QTabBar):
        if not _visible(bar):
            continue
        metrics = bar.fontMetrics()
        for index in range(bar.count()):
            text = bar.tabText(index).replace("&", "")
            width = bar.tabRect(index).width()
            need = metrics.horizontalAdvance(text)
            found.append(
                {
                    "text": text,
                    "carrier": "QTabBar",
                    "need_px": need,
                    "width_px": width,
                    "cut": need > width,
                    "lead": False,
                }
            )
    return found


def overflowing(entries: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Die Texte, deren Bedarf über ihrer Breite liegt."""
    return [
        entry for entry in entries if int(entry.get("need_px", 0)) > int(entry.get("width_px", 0))
    ]


def _caption_map(root: Any) -> dict[int, str]:
    from PySide6.QtWidgets import QFormLayout

    captions: dict[int, str] = {}
    for form in root.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label is None or field is None or label.widget() is None or field.widget() is None:
                continue
            captions[id(field.widget())] = _text_of(label.widget())
    return captions


def field_entries(root: Any) -> list[dict[str, Any]]:
    """Jedes Eingabefeld unter ``root``: Beschriftung, Name, Beschreibung, Kurzhilfe, vorn.

    *Vorn* heißt sichtbar, ohne eine Klappe zu öffnen — E5 zählt diese Felder.
    Die Beschriftung kommt aus dem Formular, in dem das Feld steht; ein Haken
    beschriftet sich selbst.
    """
    from PySide6.QtWidgets import QCheckBox

    captions = _caption_map(root)
    return [
        {
            "label": captions.get(
                id(widget), _text_of(widget) if isinstance(widget, QCheckBox) else ""
            ),
            "accessible_name": widget.accessibleName(),
            "description": widget.accessibleDescription(),
            "tooltip": widget.toolTip(),
            "front": bool(widget.isVisible()),
        }
        for widget in _input_widgets(root)
    ]


def field_values(root: Any) -> dict[str, Any]:
    """Was die Felder unter ``root`` zeigen, nach ihrem Kennzeichen (Prüfpunkt 12).

    Längen in Millimetern über ``value_mm``, wie der Kern sie hat; andere Zahlen
    über ``value``, Haken als wahr oder falsch, Auswahl und Text als Text.
    """
    from PySide6.QtWidgets import QAbstractSpinBox, QCheckBox, QComboBox, QLineEdit

    values: dict[str, Any] = {}
    for widget in _input_widgets(root):
        name = mark_of(widget)
        if not name:
            continue
        name = name.partition(":")[2] if ":" in name else name
        if callable(getattr(widget, "value_mm", None)):
            values[name] = round(float(widget.value_mm()), 4)
        elif isinstance(widget, QAbstractSpinBox) and callable(getattr(widget, "value", None)):
            values[name] = widget.value()
        elif isinstance(widget, QCheckBox):
            values[name] = bool(widget.isChecked())
        elif isinstance(widget, QComboBox):
            values[name] = widget.currentText()
        elif isinstance(widget, QLineEdit):
            values[name] = widget.text()
    return values


def duplicate_names(names: Iterable[str]) -> list[str]:
    """Zugängliche Namen, die mehr als einmal vorkommen (Prüfpunkt 10)."""
    counted: dict[str, int] = {}
    for name in names:
        if name:
            counted[name] = counted.get(name, 0) + 1
    return sorted(name for name, count in counted.items() if count > 1)


# --- Tab-Kette (Prüfpunkt 10) ---------------------------------------------------------------


def focus_entry(widget: Any, root: Any) -> dict[str, Any]:
    """Das Fokuswidget als Kettenglied: Name und Rechteck relativ zu ``root``."""
    from PySide6.QtCore import QPoint

    inside = root is widget or root.isAncestorOf(widget)
    corner = widget.mapTo(root, QPoint(0, 0)) if inside and root is not widget else QPoint(0, 0)
    if not inside:
        corner = widget.mapToGlobal(QPoint(0, 0))
    return {
        "name": widget.accessibleName() or name_of(widget),
        "rect": [corner.x(), corner.y(), widget.width(), widget.height()],
    }


def tab_chain(
    root: Any, press_tab: Callable[[], None], limit: int = MOST_TABS
) -> list[dict[str, Any]]:
    """Die Tab-Kette ab dem Fokus: je Druck das Fokuswidget, bis sie sich schließt.

    ``press_tab`` drückt Tab am Fokuswidget (``QtPorts.keys``) — die Kette wird
    gedrückt, nicht aus ``nextInFocusChain`` gelesen: Gemessen wird, was die
    Tastatur tut. Die Kette endet, wenn ein Widget wiederkommt oder der Fokus
    ``root`` verlässt; das Glied, das hinausführt, steht noch darin.
    """
    from PySide6.QtWidgets import QApplication

    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    first = QApplication.focusWidget()
    if first is not None:
        seen.add(id(first))
        chain.append(focus_entry(first, root))
    for _ in range(limit):
        press_tab()
        QApplication.processEvents()
        current = QApplication.focusWidget()
        if current is None:
            break
        chain.append(focus_entry(current, root))
        if id(current) in seen or not (root is current or root.isAncestorOf(current)):
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
    for index in range(1, len(chain)):
        before, after = chain[index - 1]["rect"], chain[index]["rect"]
        if index == len(chain) - 1 and chain[index]["rect"] == chain[0]["rect"]:
            break
        rises = int(after[1]) < int(before[1]) - SAME_LINE_PX
        same_line = abs(int(after[1]) - int(before[1])) <= SAME_LINE_PX
        if rises or (same_line and int(after[0]) < int(before[0])):
            breaks.append(index)
    return breaks


# --- Layout, Schrift, Kontrast, Symbole, Animationen, Rollleisten (G1 bis G8, Z6) ---------


def layout_entries(root: Any) -> list[dict[str, Any]]:
    """Hauptknöpfe und Akzente (G1), Abstände je Gruppe (G2), Kanten der Formulare (G3)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QAbstractSpinBox, QFormLayout, QLayout, QPushButton, QWidget

    surface = type(root).__name__
    buttons = [button for button in root.findChildren(QPushButton) if _visible(button)]
    found: list[dict[str, Any]] = [
        {
            "kind": "primary",
            "surface": surface,
            "primary": sum(1 for button in buttons if button.isDefault()),
            "accents": sum(
                1
                for button in buttons
                if button.isDefault() or button.font().weight() >= QFont.Weight.DemiBold
            ),
        }
    ]
    # Jedes Layout, auch die geschachtelten: widget.layout() nennt nur das
    # oberste eines Widgets, ein Formular steht meist darin.
    layouts: list[Any] = []
    for widget in [root, *root.findChildren(QWidget)]:
        top = widget.layout()
        if isinstance(top, QLayout) and _visible(widget):
            layouts += [top, *(item for item in top.findChildren(QLayout) if item not in layouts)]
    for layout in dict.fromkeys(layouts):
        widget = layout.parentWidget() or root
        margins = layout.contentsMargins()
        found.append(
            {
                "kind": "spacing",
                "surface": surface,
                "group": mark_of(widget) or type(widget).__name__,
                "spacing": layout.spacing(),
                "margins": [margins.left(), margins.top(), margins.right(), margins.bottom()],
            }
        )
        if not isinstance(layout, QFormLayout):
            continue
        labels: list[int] = []
        fields: list[int] = []
        values: list[dict[str, Any]] = []
        for row in range(layout.rowCount()):
            label = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            editor = field.widget() if field is not None else None
            if editor is None or not editor.isVisible():
                continue
            if label is not None and label.widget() is not None:
                labels.append(label.widget().x())
            fields.append(editor.x())
            if isinstance(editor, QAbstractSpinBox):
                right = bool(editor.alignment() & Qt.AlignmentFlag.AlignRight)
                suffix = callable(getattr(editor, "suffix", None)) and bool(editor.suffix())
                values.append({"alignment": "right" if right else "left", "unit": suffix})
        found.append(
            {
                "kind": "form",
                "surface": surface,
                "label_edges": labels,
                "field_edges": fields,
                "values": values,
            }
        )
    return found


def font_entries(root: Any) -> list[dict[str, Any]]:
    """Stufe und Stylesheet je Textträger (G4)."""
    from PySide6.QtWidgets import QAbstractButton, QLabel

    surface = type(root).__name__
    return [
        {
            "surface": surface,
            "widget": name_of(widget),
            "level": str(widget.property("level") or ""),
            "stylesheet": widget.styleSheet(),
        }
        for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton)
        if _visible(widget) and _text_of(widget).strip()
    ]


def contrast_entries(root: Any, theme: str) -> list[dict[str, Any]]:
    """Schrift gegen Hintergrund je Textträger als ``#rrggbb`` (G6).

    Die Farben kommen aus der Palette des Trägers, die das Stylesheet beim
    Polieren setzt; das Verhältnis rechnet U mit ``theme.contrast_ratio``.
    """
    from PySide6.QtWidgets import QAbstractButton, QLabel

    surface = type(root).__name__
    found: list[dict[str, Any]] = []
    for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton):
        if not _visible(widget):
            continue
        text = _text_of(widget).strip()
        symbol = not text and isinstance(widget, QAbstractButton) and not widget.icon().isNull()
        if not text and not symbol:
            continue
        palette = widget.palette()
        font = widget.font()
        found.append(
            {
                "surface": surface,
                "widget": name_of(widget),
                "theme": theme,
                "foreground": palette.color(widget.foregroundRole()).name(),
                "background": palette.color(widget.backgroundRole()).name(),
                "large": font.pointSizeF() >= 14 or (font.pointSizeF() >= 11 and font.bold()),
                "symbol": symbol,
            }
        )
    return found


def icon_entries(root: Any) -> list[dict[str, Any]]:
    """Bedienelemente ohne Text: Symbol, Kurzhilfe, Kürzel, Bildschärfe (G7, Z6).

    Ob ein Symbol aus dem eigenen Satz stammt und welchen Stil es hat, sieht man
    einem ``QIcon`` nicht an — ``own`` und ``style`` bleiben offen für Stufe B.
    """
    from PySide6.QtWidgets import QAbstractButton, QToolButton

    surface = type(root).__name__
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
                "surface": surface,
                "widget": button.accessibleName() or mark_of(button) or type(button).__name__,
                "text": "",
                "icon": "" if icon.isNull() else (icon.name() or "eigen"),
                "own": None,
                "tooltip": button.toolTip(),
                "shortcut": shortcut,
                "style": None,
                "scale": ratio,
                "pixmap_ratio": float(pixmap.devicePixelRatio()) if pixmap is not None else None,
            }
        )
    return found


def animation_entries(root: Any) -> list[dict[str, Any]]:
    """Übergänge unter ``root`` mit ihrer Dauer (G8)."""
    from PySide6.QtCore import QAbstractAnimation

    surface = type(root).__name__
    found: list[dict[str, Any]] = []
    for animation in root.findChildren(QAbstractAnimation):
        owner = animation.parent()
        found.append(
            {
                "surface": surface,
                "widget": name_of(owner)
                if hasattr(owner, "accessibleName")
                else type(owner).__name__,
                "duration_ms": float(animation.duration()),
            }
        )
    return found


def scrollbar_entries(root: Any, window_size: Sequence[int]) -> list[dict[str, Any]]:
    """Rollbereiche vorn mit ihren Leisten — vorn braucht keiner eine (Z6)."""
    from PySide6.QtWidgets import QAbstractScrollArea

    surface = type(root).__name__
    return [
        {
            "surface": surface,
            "window_size": list(window_size),
            "front": True,
            "vertical": bool(area.verticalScrollBar().isVisible()),
            "horizontal": bool(area.horizontalScrollBar().isVisible()),
        }
        for area in root.findChildren(QAbstractScrollArea)
        if _visible(area)
    ]


# --- Zustandsbilder (G5) --------------------------------------------------------------------------


def _picture_digest(widget: Any) -> str:
    image = widget.grab().toImage()
    return hashlib.sha256(bytes(image.constBits())).hexdigest()[:16]


def state_images(widget: Any) -> dict[str, str]:
    """Ein Bildabdruck je Zustand, hergestellt über gesendete Ereignisse (G5).

    Darüber: die Maus fährt hinein. Fokus: wie ein Tab. Gedrückt: die Taste
    unten, dann außerhalb losgelassen — so löst der Knopf nicht aus. Gleiche
    Abdrücke zweier Zustände heißen: nicht unterscheidbar.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    images: dict[str, str] = {"rest": _picture_digest(widget)}
    centre = widget.rect().center()
    QTest.mouseMove(widget, centre)
    QApplication.processEvents()
    images["hover"] = _picture_digest(widget)
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    images["focus"] = _picture_digest(widget)
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    QApplication.processEvents()
    images["pressed"] = _picture_digest(widget)
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
    """Sichtbare leere Listen und Bäume mit dem Satz und dem Knopf daneben (Z4, E7).

    Ob ein leerer Zustand gewollt leer ist (Prüfbericht ohne Befund), urteilt
    Stufe B; ``intended`` bleibt offen.
    """
    from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QLabel

    found: list[dict[str, Any]] = []
    for view in root.findChildren(QAbstractItemView):
        model = view.model()
        if not _visible(view) or model is None or model.rowCount() > 0:
            continue
        parent = view.parentWidget()
        labels = parent.findChildren(QLabel) if parent is not None else []
        buttons = parent.findChildren(QAbstractButton) if parent is not None else []
        sentence = " ".join(
            _text_of(label) for label in labels if _visible(label) and _text_of(label)
        )
        button = next(
            (_text_of(item) for item in buttons if _visible(item) and _text_of(item)), None
        )
        found.append(
            {
                "surface": mark_of(view) or type(view).__name__,
                "sentence": sentence,
                "button": button,
                "intended": None,
            }
        )
    return found


def message_entries(window: Any) -> list[dict[str, Any]]:
    """Was die Oberfläche gerade meldet, mit den Handlungen dabei (Prüfpunkt 7, V5).

    Statuszeile, sichtbare Hinweise und gesperrte Knöpfe mit Grund. Je Meldung
    ihre Handlungen — die sichtbaren Knöpfe im selben Hinweis — mit
    ``clicked = False`` und ``effect = None``; der Fall, der eine anklickt, trägt
    beides nach.
    """
    from PySide6.QtWidgets import QAbstractButton, QFrame, QPushButton

    found: list[dict[str, Any]] = []
    status = window.statusBar().currentMessage() if window.statusBar() is not None else ""
    if status:
        found.append({"text": status, "actions": []})
    for frame in window.findChildren(QFrame):
        name = frame.objectName().lower()
        if not _visible(frame) or not any(
            word in name for word in ("notice", "hint", "error", "advice")
        ):
            continue
        texts = visible_texts(frame)
        if not texts:
            continue
        found.append(
            {
                "text": " ".join(texts),
                "actions": [
                    {
                        "label": _text_of(button),
                        "target": mark_of(button),
                        "clicked": False,
                        "effect": None,
                    }
                    for button in frame.findChildren(QAbstractButton)
                    if _visible(button) and _text_of(button) and button.isEnabled()
                ],
            }
        )
    for button in window.findChildren(QPushButton):
        reason = button.accessibleDescription() or button.toolTip()
        if _visible(button) and not button.isEnabled() and reason:
            found.append({"text": reason, "actions": []})
    return found


def visible_texts(root: Any) -> list[str]:
    """Die sichtbaren Texte unter ``root`` — für Band, Beschriftung beim Überfahren, Hinweise."""
    from PySide6.QtWidgets import QLabel

    return [
        _text_of(label)
        for label in root.findChildren(QLabel)
        if _visible(label) and _text_of(label)
    ]


def sheet_snapshot(
    root: Any, theme: str, window_size: Sequence[int]
) -> dict[str, list[dict[str, Any]]]:
    """Alles, was eine offene Fläche für G1 bis G8 und Z6 hergibt, in einem Zug."""
    return {
        "layout": layout_entries(root),
        "fonts": font_entries(root),
        "contrast": contrast_entries(root, theme),
        "icons": icon_entries(root),
        "animations": animation_entries(root),
        "scrollbars": scrollbar_entries(root, window_size),
    }
