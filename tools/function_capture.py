"""Aufnahmen am Fenster für das Messprotokoll eines Funktionsfalls (D0, RM-737).

Jede Aufnahme liest, was die Oberfläche gerade zeigt, und gibt die Einträge
eines Felds im Messprotokoll zurück — in der Form, die das Schema von D0-U
vorgibt (``tools/function_checks.PROTOCOL_SCHEMA``): Herzschlag des
Hauptfadens, Bildzähler der Ansicht, modale, rohe und alle Fenster, Texte mit
ihrem Platzbedarf, Felder, Tab-Kette, Layoutmaße, Schriften, Zustandsbilder,
Kontraste, Symbole, Animationen, Rollleisten, leere Zustände und Meldungen samt
Handlungen. Was die Aufnahme dazu tun muss — eine Taste drücken, mit der Maus
darüberfahren —, sind Eingabeereignisse; keine Aufnahme ruft eine Handlung
direkt auf (Wächter in ``tests/test_function_guard.py``,
:data:`function_guard.FORBIDDEN_CALLS`).

Die Rechnung hinter den Aufnahmen ist ohne Fenster prüfbar: :class:`Heartbeat`,
:class:`FrameCounter` und :func:`modal_allowed` bekommen Zahlen, Namen und
Aufrufer, keine Widgets. Gemessen wird an der echten Plattform; offscreen hat
keine Schrift (``tests.md``, „Isolation heißt Betriebslage“), dort sind Breiten
und Kontraste nur Platzhalter.

Geurteilt wird hier über die Prüfpunkte nicht: Rücksprünge der Tab-Kette,
abgeschnittene Texte, doppelte Namen und gleiche Zustandsbilder rechnet D0-U
aus diesen Rohdaten (``tools/function_judges.py``), mit den Schwellen aus
``tools/function_checks.py``. Einige Felder des Schemas sind selbst eine
kleine Einordnung dessen, was zu sehen war — ``allowed`` (Fenster der Ausnahmeliste
oder aus einer erlaubten Funktion), ``question`` (eine Wahl zwischen
mindestens zwei Knöpfen), ``large`` (große Schrift nach WCAG) und ``cut`` (der
Text braucht mehr Platz, als er hat); die Regel dafür steht je an der Funktion.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
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
#: Dateidialoge und der KI- und der Druckhinweis. Eine Rückfrage über
#: ``ctx.ask`` (``AskDialog``) ist keine Ausnahme — nur die vor der Vollerkennung
#: (:data:`FULL_RECOGNITION_ANSWER`).
ALLOWED_CLASSES: Final[frozenset[str]] = frozenset(
    {"QFileDialog", "AiDisclosureDialog", "PrintDisclosureDialog"}
)

#: Funktionen, aus denen eine Rückfrage erlaubt ist — die Rückfragen aus
#: ``fenster.md`` und die Speicherfrage, wie Konzept Z2 sie nennt: Löschen im
#: Verlauf, Export und Übergabe trotz Befunden, Verwerfen zurückgenommener
#: Schritte, Wiederherstellen nach einem Absturz, Verlust einer Generierung,
#: Speicherfrage. Erkannt am Aufrufstapel des ``exec()`` — so hängt die
#: Zuordnung an keiner Übersetzung. Ein Wächter hält, dass jede dieser
#: Funktionen in ``app/ui`` steht.
ALLOWED_CALLERS: Final[frozenset[str]] = frozenset(
    {
        "remove_history_operations",
        "confirm_export",
        "confirm_handover",
        "confirm_discard",
        "_ask_recovery",
        "confirm_generation_loss",
        "confirm_unsaved",
    }
)

#: Die Frage vor der Vollerkennung (§21.1) stellt der Kern im Arbeiter über
#: ``ctx.ask``; im Aufrufstapel des Dialogs steht er nicht. Erkannt wird sie an
#: ihrer Antwort (``scene.evaluate._asked_about_recognition``), übersetzt wie im
#: Fenster. Ein Wächter hält, dass die Anwendung den Satz noch führt.
FULL_RECOGNITION_ANSWER: Final = "Mit Merkmalserkennung laden"

#: Meldungen und Fragen sind nie die Bedienfläche einer Zeile: die Meldung im
#: Hausstil (``message_dialog.MessageDialog``, FD-21) und die Rückfrage
#: (``AskDialog``); dazu die rohen Qt-Fenster (``function_checks.RAW_CLASSES``).
MESSAGE_CLASSES: Final[frozenset[str]] = frozenset({"MessageDialog", "AskDialog"})


def _raw_bases() -> tuple[str, ...]:
    """Die rohen Qt-Fensterklassen, die aufgenommen werden — aus D0-U (``RAW_BASES``).

    Spät importiert: ``function_checks`` zieht die Oberfläche nach, und dieses
    Modul misst im Elternprozess eines Laufs auch den Referenzfaktor, ohne sie.
    """
    from tools.function_checks import RAW_BASES

    return tuple(RAW_BASES)


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
    """Wie schnell dieser Rechner gegen den Referenzrechner ist (Bauplan §31).

    Die Kalibrierung, mit der §31 jede Messung auf einem anderen Rechner
    umrechnet: die Rechenprobe aus ``perceive.recognition_time`` — „Messzeit
    mal 18 ms durch die Probe des Laufs“. Eine gemessene Dauer mal diesem Faktor
    ist die Dauer auf der Referenz; umgerechnet wird bei D0-U, einmal.
    """
    from app.core.perceive import recognition_time

    return recognition_time.PROBE_REFERENCE_SECONDS / recognition_time.calibrate()


#: Wo ein Lauf seinen Referenzfaktor ablegt — einer je ``run``, für alle Fälle.
REFERENCE_FILE: Final = "reference.json"


def measure_reference(out: Path) -> float:
    """Misst den Referenzfaktor einmal für einen ganzen Lauf und legt ihn nach ``out``."""
    factor = round(reference_factor(), 4)
    out.mkdir(parents=True, exist_ok=True)
    (out / REFERENCE_FILE).write_text(json.dumps({"reference_factor": factor}), encoding="utf-8")
    return factor


def run_reference_factor(out: Path) -> float:
    """Der Referenzfaktor dieses Laufs; fehlt er (Fall ohne ``run``), wird er hier gemessen."""
    try:
        return float(
            json.loads((out / REFERENCE_FILE).read_text(encoding="utf-8"))["reference_factor"]
        )
    except OSError, ValueError, KeyError, TypeError:
        return measure_reference(out)


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


def modal_allowed(
    classes: Sequence[str], stack: Sequence[str], buttons: Sequence[str] = ()
) -> bool:
    """Ob ein Fenster zu den erlaubten gehört (Konzept Z2, E6).

    Erlaubt nach Klasse (Dateidialog, KI- und Druckhinweis), nach öffnender
    Funktion (:data:`ALLOWED_CALLERS`) oder als die Frage vor der Vollerkennung,
    an ihrer Antwort erkannt. Jede andere modale Frage ist ein Fund.
    """
    from app.i18n import tr

    if ALLOWED_CLASSES & set(classes) or ALLOWED_CALLERS & set(stack):
        return True
    answer = str(tr(FULL_RECOGNITION_ANSWER))
    return "AskDialog" in classes and any(text.replace("&", "") == answer for text in buttons)


def is_question(class_name: str, buttons: Sequence[str]) -> bool:
    """Eine Nachfrage (E6) statt einer Meldung (Z2): eine Wahl zwischen mindestens zwei Knöpfen.

    Die Meldung im Hausstil (``MessageDialog``) ist nie eine Frage, auch mit
    Handlung und Ausgang: Fragen bleiben ``QMessageBox`` oder ``AskDialog``
    (``fenster.md``, „Rückfragen“).
    """
    if class_name == "MessageDialog":
        return False
    return class_name == "AskDialog" or len([text for text in buttons if text]) >= 2


def message_window(widget: Any) -> bool:
    """Ob ein Fenster eine Meldung oder Frage ist — roh oder im Hausstil, nie eine Fläche."""
    from tools.function_checks import RAW_CLASSES

    return bool(set(_classes(widget)) & (MESSAGE_CLASSES | set(RAW_CLASSES)))


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
            buttons = _buttons(widget)
            allowed = modal_allowed(classes, stack, buttons) or type(widget).__name__ in self.own
            self.modals.append(
                {
                    "class": type(widget).__name__,
                    "title": widget.windowTitle(),
                    "allowed": allowed,
                    "question": is_question(type(widget).__name__, buttons),
                }
            )
            raw = next((name for name in _raw_bases() if name in classes), "")
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
            raw = next((name for name in _raw_bases() if name in classes), "")
            if raw and id(widget) not in self._seen:
                self._seen.add(id(widget))
                self.raw_windows.append(
                    {
                        "class": raw,
                        "title": widget.windowTitle(),
                        "allowed": modal_allowed(classes, stack, _buttons(widget)),
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


def vocabulary_name(widget: Any) -> str:
    """Das Wortschatzkennzeichen eines Widgets, wenn es ein Name aus dem Wortschatz ist, sonst leer.

    Nur damit geht ein Klick über ``next_click`` (Review M11); ein ``objectName``
    ist keiner.
    """
    from app.core import guides

    mark = widget.property(guides.TARGET_PROPERTY)
    return str(mark) if mark and guides.is_target(str(mark)) else ""


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
    umbrechender Text braucht nur sein längstes Wort. Ein Knopf oder Haken
    braucht dazu Kästchen, Symbol und Polsterung (:func:`_button_need`) und hat
    seine ganze Breite (Review M12); Rich Text zählt mit seinem sichtbaren Text.
    ``cut`` heißt Bedarf über der Breite (Prüfpunkt 9), ``lead``: steht über dem
    ersten Feld (E5). Reiter einer Leiste stehen mit ihrem eigenen Rechteck da,
    Zeilen sichtbarer Listen und Bäume mit ihrer Zelle (:func:`_item_texts`).
    """
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabBar

    fields = [field for field in _input_widgets(root) if _visible(field)]
    first_field = min((_top(field, root) for field in fields), default=None)
    found: list[dict[str, Any]] = []
    carriers = root.findChildren(QLabel) + root.findChildren(QAbstractButton)
    for widget in carriers + root.findChildren(QGroupBox):
        if not _visible(widget):
            continue
        text = _plain(_text_of(widget))
        if not text.strip():
            continue
        metrics = widget.fontMetrics()
        lines = text.splitlines() or [text]
        wraps = bool(getattr(widget, "wordWrap", lambda: False)())
        pieces = [word for line in lines for word in line.split()] if wraps else lines
        need = max((metrics.horizontalAdvance(piece) for piece in pieces), default=0)
        width = widget.contentsRect().width()
        contents = _indicator_contents(widget)
        if contents is not None:
            # Ein Haken gibt seinem Text, was sein Stil ihm lässt (F-16: vorher
            # rechnete der Prüfstand das Kästchen selbst und kam 2 px zu breit).
            icon = widget.iconSize().width() + 4 if not widget.icon().isNull() else 0
            need, width = need + icon, contents
        elif isinstance(widget, QAbstractButton):
            need, width = _button_need(widget, need), widget.width()
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
            if not bar.isTabVisible(index):
                # Ein verborgener Reiter hat kein Rechteck — nicht abgeschnitten (F-14).
                continue
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
    found += _item_texts(root)
    return found


#: Wie viele Zellen sichtbarer Listen und Bäume je Fläche aufgenommen werden.
MOST_ITEM_TEXTS: Final = 200


def _plain(text: str) -> str:
    """Der sichtbare Text eines Trägers — Rich Text ohne seine Auszeichnung (Review M12)."""
    from PySide6.QtGui import Qt, QTextDocument

    if not Qt.mightBeRichText(text):
        return text
    document = QTextDocument()
    document.setHtml(text)
    return str(document.toPlainText())


def _indicator_contents(button: Any) -> int | None:
    """Die Breite, die ein Haken oder Optionsknopf seinem Text gibt; sonst ``None``.

    Aus dem Stil (``SE_CheckBoxContents``, ``SE_RadioButtonContents``): Er weiß,
    wo Kästchen und Abstand enden — auch unter dem Stylesheet.
    """
    from PySide6.QtWidgets import QCheckBox, QRadioButton, QStyle, QStyleOptionButton

    if isinstance(button, QCheckBox):
        element = QStyle.SubElement.SE_CheckBoxContents
    elif isinstance(button, QRadioButton):
        element = QStyle.SubElement.SE_RadioButtonContents
    else:
        return None
    option = QStyleOptionButton()
    button.initStyleOption(option)
    return int(button.style().subElementRect(element, option, button).width())


def _button_need(button: Any, text_px: int) -> int:
    """Was ein Knopf oder Haken für seinen Text braucht: Text, Kästchen, Symbol, Polsterung.

    Aus den Maßen seines Stils, nicht aus ``sizeHint`` — der hebt kurze Knöpfe
    auf die Mindestbreite des Stils, und „OK“ hieße dann abgeschnitten.
    """
    from PySide6.QtWidgets import QCheckBox, QRadioButton, QStyle

    style = button.style()

    def metric(which: QStyle.PixelMetric) -> int:
        return int(style.pixelMetric(which, None, button))

    if isinstance(button, QCheckBox):
        extra = metric(QStyle.PixelMetric.PM_IndicatorWidth) + metric(
            QStyle.PixelMetric.PM_CheckBoxLabelSpacing
        )
    elif isinstance(button, QRadioButton):
        extra = metric(QStyle.PixelMetric.PM_ExclusiveIndicatorWidth) + metric(
            QStyle.PixelMetric.PM_RadioButtonLabelSpacing
        )
    else:
        extra = 2 * metric(QStyle.PixelMetric.PM_ButtonMargin) + 2 * metric(
            QStyle.PixelMetric.PM_DefaultFrameWidth
        )
    if not button.icon().isNull():
        extra += button.iconSize().width() + 4
    return text_px + extra


def _columns(model: Any, parent: Any) -> int:
    """Spalten eines Modells; eine Liste (``QListWidget``) hält ihre Zählung privat — eine."""
    try:
        return int(model.columnCount(parent))
    except TypeError:
        return 1


def _item_texts(root: Any) -> list[dict[str, Any]]:
    """Die sichtbaren Zellen der Listen und Bäume unter ``root``: Text gegen Zellbreite (M12).

    Eine Ansicht kürzt mit „…“, statt umzubrechen — der Kunde sieht dann nur
    einen Teil. Bedarf ist Text, Symbol und der Innenrand der Zelle.
    """
    from PySide6.QtCore import QModelIndex, Qt
    from PySide6.QtWidgets import QAbstractItemView, QStyle

    found: list[dict[str, Any]] = []
    for view in root.findChildren(QAbstractItemView):
        model = view.model()
        if not _visible(view) or model is None:
            continue
        area = view.viewport().rect()
        metrics = view.fontMetrics()
        margin = 2 * (view.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1)
        # Eine Liste, die umbricht, braucht für ihre Zeile nur das längste Wort
        # (F-15: die Befundliste des Prüfberichts, ``setWordWrap(True)``).
        wraps = bool(getattr(view, "wordWrap", lambda: False)())
        pending = [QModelIndex()]
        while pending and len(found) < MOST_ITEM_TEXTS:
            parent = pending.pop(0)
            for row in range(model.rowCount(parent)):
                for column in range(_columns(model, parent)):
                    index = model.index(row, column, parent)
                    cell = view.visualRect(index)
                    text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
                    if not text or cell.isEmpty() or not area.intersects(cell):
                        continue
                    icon = index.data(Qt.ItemDataRole.DecorationRole)
                    pieces = text.split() if wraps else text.splitlines()[:1]
                    need = (
                        max((metrics.horizontalAdvance(piece) for piece in pieces), default=0)
                        + margin
                    )
                    if icon is not None and not (hasattr(icon, "isNull") and icon.isNull()):
                        need += view.iconSize().width() + 4
                    # Zu sehen ist die Zelle nur, soweit sie in der Sichtfläche liegt;
                    # eine Liste ohne Umbruch macht die Zelle so breit wie ihren Text.
                    shown = cell.intersected(area).width()
                    found.append(
                        {
                            "text": text,
                            "carrier": f"{type(view).__name__}.Zeile",
                            "need_px": need,
                            "width_px": shown,
                            "cut": need > shown,
                            "lead": False,
                        }
                    )
                # Nur ein Baum hat Kinder, und nur aufgeklappte sind zu sehen.
                expanded = getattr(view, "isExpanded", None)
                child = model.index(row, 0, parent)
                if expanded is not None and expanded(child) and model.rowCount(child) > 0:
                    pending.append(child)
    return found


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
    Die Beschriftung kommt aus dem Formular, in dem das Feld oder sein Behälter
    steht (``ValueField``, ``FeatureSetField``: gefunden wird das Drehfeld darin);
    ein Haken beschriftet sich selbst. Die Kurzhilfe ist die, die Qt zeigt: die
    eigene, sonst die des nächsten Elternteils bis zur Fläche (Probelauf F-9).
    Die zugängliche Beschreibung bleibt die des Felds selbst — die liest ein
    Bildschirmleser am fokussierten Feld.
    """
    from PySide6.QtWidgets import QCheckBox

    captions = _caption_map(root)

    def holders(widget: Any) -> list[Any]:
        chain = [widget]
        while chain[-1] is not root and chain[-1].parentWidget() is not None:
            if chain[-1].isWindow():
                break
            chain.append(chain[-1].parentWidget())
        return chain

    def caption(widget: Any) -> str:
        found = next(
            (captions[id(holder)] for holder in holders(widget) if id(holder) in captions), ""
        )
        return found or (_text_of(widget) if isinstance(widget, QCheckBox) else "")

    def tooltip(widget: Any) -> str:
        return next((str(holder.toolTip()) for holder in holders(widget) if holder.toolTip()), "")

    return [
        {
            "label": caption(widget),
            "accessible_name": widget.accessibleName(),
            "description": widget.accessibleDescription(),
            "tooltip": tooltip(widget),
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


# --- Tab-Kette (Prüfpunkt 10) ---------------------------------------------------------------


def _inside(widget: Any, root: Any) -> bool:
    return bool(widget is not None and (root is widget or root.isAncestorOf(widget)))


def focus_entry(widget: Any, root: Any) -> dict[str, Any]:
    """Das Fokuswidget als Kettenglied: Name, Rechteck relativ zu ``root``, drinnen oder nicht.

    Auch ein Glied außerhalb steht in Koordinaten von ``root`` (Review S4) —
    sonst verglichen die Urteile Lagen aus zwei Bezugssystemen.
    """
    from PySide6.QtCore import QPoint

    corner = root.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
    return {
        "name": widget.accessibleName() or name_of(widget),
        "rect": [corner.x(), corner.y(), widget.width(), widget.height()],
        "inside": _inside(widget, root),
    }


def first_tab_stop(root: Any) -> Any:
    """Das erste Widget der Fläche, das Tab erreicht — nur gelesen, nicht fokussiert.

    Folgt Qts Fokuskette ab ``root`` (``nextInFocusChain``) bis zum ersten
    sichtbaren, bedienbaren Kind, das Tab annimmt; ``None``, wenn es keines gibt.
    """
    from PySide6.QtCore import Qt

    probe = root.nextInFocusChain()
    for _ in range(MOST_TABS * 4):
        if probe is None or probe is root:
            return None
        if (
            root.isAncestorOf(probe)
            and probe.isVisible()
            and probe.isEnabled()
            and probe.focusPolicy() & Qt.FocusPolicy.TabFocus
        ):
            return probe
        probe = probe.nextInFocusChain()
    return None


def tab_chain(
    root: Any,
    press_tab: Callable[[], None],
    limit: int = MOST_TABS,
    on_focus: Callable[[Any], None] | None = None,
) -> list[dict[str, Any]]:
    """Die Tab-Kette der Fläche ``root``: zum ersten Feld mit Tab, dann je Druck das Fokuswidget.

    ``press_tab`` drückt Tab am Fokuswidget (``QtPorts.keys``) — die Kette wird
    gedrückt, nicht aus ``nextInFocusChain`` gelesen: Gemessen wird, was die
    Tastatur tut. Beginnen soll sie am ersten Feld der Fläche
    (:func:`first_tab_stop`, Review S4): Steht der Fokus woanders — außerhalb
    oder am Hauptknopf —, drückt der Prüfstand Tab, bis er dort ankommt, wie ein
    Kunde; kommt er nie dort an, beginnt die Kette, wo er in der Fläche steht.
    Sie endet mit dem Glied, das wiederkommt, oder mit dem, das die Fläche verlässt
    (``inside`` falsch) — dieses Schlussglied steht darin, und D0-U zählt es
    nicht mit (``function_judges._within_chain``). ``on_focus`` sieht jedes
    Fokuswidget, solange es da ist — für das Zustandsbild „Fokus“ (G5).
    """
    from PySide6.QtWidgets import QApplication

    def step() -> Any:
        press_tab()
        QApplication.processEvents()
        return QApplication.focusWidget()

    first = first_tab_stop(root)
    current = QApplication.focusWidget()
    presses = 0

    def arrived(widget: Any) -> bool:
        if first is None or widget is None:
            return _inside(widget, root)
        # Ein Zahlenfeld nimmt den Fokus über seine Textzeile an.
        return bool(widget is first or first.isAncestorOf(widget) or widget.isAncestorOf(first))

    while not arrived(current) and presses < limit:
        current = step()
        presses += 1
    if not _inside(current, root):
        return []
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    while presses <= limit:
        entry = focus_entry(current, root)
        chain.append(entry)
        if id(current) in seen or not entry["inside"]:
            break
        seen.add(id(current))
        if on_focus is not None:
            on_focus(current)
        current = step()
        presses += 1
        if current is None:
            break
    return chain


# --- Layout, Schrift, Kontrast, Symbole, Animationen, Rollleisten (G1 bis G8, Z6) ---------


def layout_entries(root: Any) -> list[dict[str, Any]]:
    """Hauptknöpfe und Akzente (G1), Abstände je Gruppe (G2), Kanten der Formulare (G3)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QFormLayout,
        QGridLayout,
        QLayout,
        QPushButton,
        QWidget,
    )

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
    # oberste eines Widgets, ein Formular steht meist darin. Qts eigene Layouts
    # (Hauptfenster, Leisten, Statuszeile, Reiterstapel) gestaltet nicht die
    # Anwendung (Probelauf F-8).
    layouts: list[Any] = []
    for widget in [root, *root.findChildren(QWidget)]:
        top = widget.layout()
        if isinstance(top, QLayout) and _visible(widget) and not _qt_own_layout(top, widget):
            layouts += [top, *(item for item in top.findChildren(QLayout) if item not in layouts)]
    for number, layout in enumerate(dict.fromkeys(layouts), 1):
        widget = layout.parentWidget() or root
        margins = layout.contentsMargins()
        grid = isinstance(layout, (QFormLayout, QGridLayout))
        found.append(
            {
                "kind": "spacing",
                "surface": surface,
                # Die Gruppe ist das eine Layout, nicht der Name seines Widgets: Alle
                # namenlosen hießen „QWidget“, und ein Zahlenfeld trägt zwei (F-6).
                "group": f"{mark_of(widget) or type(widget).__name__}#{number}",
                # Raster und Formular: senkrecht und waagerecht getrennt (F-7).
                "spacing": layout.verticalSpacing() if grid else layout.spacing(),
                "horizontal": layout.horizontalSpacing() if grid else None,
                "items": _shown_items(layout),
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


#: Was Qt an Layouts selbst baut und die Anwendung nicht gestaltet: Hauptfenster,
#: Leisten, Andockflächen — benannt nach ihrer Klasse im Metaobjekt.
QT_LAYOUTS: Final[frozenset[str]] = frozenset(
    {"QMainWindowLayout", "QToolBarLayout", "QDockAreaLayout", "QDockWidgetLayout"}
)


def _qt_own_layout(layout: Any, widget: Any) -> bool:
    """Ob ein Layout Qt gehört: eine eigene Klasse von Qt, das Layout einer
    Statuszeile, eines Stapels oder Reiters oder eines Widgets mit ``qt_``-Namen."""
    from PySide6.QtWidgets import QStackedWidget, QStatusBar, QToolBar

    return (
        layout.metaObject().className() in QT_LAYOUTS
        or isinstance(widget, (QStatusBar, QStackedWidget, QToolBar))
        or widget.objectName().startswith("qt_")
    )


def _shown_items(layout: Any) -> int:
    """Wie viele Elemente eines Layouts zu sehen sind — Widgets und Layouts mit solchen."""
    count = 0
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget() if item is not None else None
        inner = item.layout() if item is not None else None
        if (widget is not None and widget.isVisible()) or (
            inner is not None and _shown_items(inner)
        ):
            count += 1
    return count


def font_entries(root: Any) -> list[dict[str, Any]]:
    """Stufe, wirksame Schrift und Stylesheet je Textträger (G4).

    ``points`` und ``weight`` sind die Schrift, mit der der Text gezeichnet
    wird, ``base_points`` die Grundgröße der Anwendung, aus der
    ``style.type_scale`` die vier Stufen rechnet. Ohne gesetzte Eigenschaft
    ``level`` ist das die Grundschrift — keine fehlende Stufe (Probelauf F-4).
    """
    from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel

    surface = type(root).__name__
    base = QApplication.font().pointSize()
    return [
        {
            "surface": surface,
            "widget": name_of(widget),
            "level": str(widget.property("level") or ""),
            "stylesheet": widget.styleSheet(),
            "points": round(float(widget.font().pointSizeF()), 2),
            "weight": int(widget.font().weight().value),
            "base_points": base,
        }
        for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton)
        if _visible(widget) and _text_of(widget).strip()
    ]


def contrast_entries(root: Any, theme: str) -> list[dict[str, Any]]:
    """Schrift gegen Hintergrund je Textträger als ``#rrggbb`` (G6).

    Die Schrift kommt aus der Palette des Trägers, die das Stylesheet beim
    Polieren setzt; der Grund aus dem Bild, das der Kunde sieht — die häufigste
    Farbe am Rand des Trägers im gerenderten Fenster (:func:`_shown_background`).
    Die Palette nannte bei ``background: transparent`` Schwarz ohne Deckung, und
    ``.name()`` warf die Deckung weg: Kontrast 1,28 an jedem durchsichtigen
    Träger (Probelauf F-1, F-3). Das Verhältnis rechnet U mit
    ``theme.contrast_ratio``. Bei einem Symbolknopf ist die Vordergrundfarbe die
    des Symbols selbst — die häufigste deckende Farbe seines Bilds
    (:func:`_icon_colour`, Review L3). Gesperrte Bedienelemente fehlen: WCAG
    1.4.3 nimmt sie aus (F-2). ``large`` ist große Schrift nach WCAG: ab 18 pt,
    fett ab 14 pt.
    """
    from PySide6.QtWidgets import QAbstractButton, QLabel

    surface = type(root).__name__
    top = root.window()
    picture = top.grab().toImage()
    found: list[dict[str, Any]] = []
    for widget in root.findChildren(QLabel) + root.findChildren(QAbstractButton):
        if not _visible(widget) or not widget.isEnabled():
            continue
        text = _text_of(widget).strip()
        symbol = not text and isinstance(widget, QAbstractButton) and not widget.icon().isNull()
        if not text and not symbol:
            continue
        palette = widget.palette()
        font = widget.font()
        size = font.pointSizeF()
        background = _shown_background(picture, top, widget) or _opaque(
            palette.color(widget.backgroundRole()), None
        )
        foreground = (
            _icon_colour(widget)
            if symbol
            else _opaque(palette.color(widget.foregroundRole()), background)
        )
        found.append(
            {
                "surface": surface,
                "widget": name_of(widget),
                "theme": theme,
                "foreground": foreground,
                "background": background,
                "large": size >= LARGE_POINTS or (size >= LARGE_BOLD_POINTS and font.bold()),
                "symbol": symbol,
            }
        )
    return found


def _opaque(colour: Any, under: str | None) -> str:
    """Eine Farbe als ``#rrggbb``, über ``under`` gelegt, wenn sie durchscheint."""
    from PySide6.QtGui import QColor

    if colour.alpha() >= 255 or under is None:
        return str(colour.name())
    below = QColor(under)
    share = colour.alphaF()
    mixed = QColor(
        round(colour.red() * share + below.red() * (1 - share)),
        round(colour.green() * share + below.green() * (1 - share)),
        round(colour.blue() * share + below.blue() * (1 - share)),
    )
    return str(mixed.name())


def _shown_background(picture: Any, top: Any, widget: Any) -> str | None:
    """Die Farbe, die am Rand von ``widget`` im gerenderten Fenster am häufigsten steht.

    Gelesen wird ein Ring knapp innerhalb des Trägers, nur wo er sichtbar ist —
    dort liegt Grund, nicht Schrift. ``None``, wenn nichts davon zu sehen ist.
    """
    from collections import Counter

    from PySide6.QtCore import QPoint

    ratio = float(picture.devicePixelRatio()) or 1.0
    width, height = widget.width(), widget.height()
    inset = max(0, min(2, width // 4, height // 4))
    shown = widget.visibleRegion()
    corner = widget.mapTo(top, QPoint(0, 0))
    points = [(x, inset) for x in range(inset, width - inset)]
    points += [(x, height - 1 - inset) for x in range(inset, width - inset)]
    points += [(inset, y) for y in range(inset, height - inset)]
    points += [(width - 1 - inset, y) for y in range(inset, height - inset)]
    counted: Counter[int] = Counter()
    for x, y in points:
        if not shown.contains(QPoint(x, y)):
            continue
        px, py = int((corner.x() + x) * ratio), int((corner.y() + y) * ratio)
        if 0 <= px < picture.width() and 0 <= py < picture.height():
            counted[picture.pixelColor(px, py).rgb() & 0xFFFFFF] += 1
    if not counted:
        return None
    return f"#{counted.most_common(1)[0][0]:06x}"


#: Große Schrift nach WCAG 2.2 (1.4.3): ab 18 Punkt, fett ab 14 Punkt.
LARGE_POINTS: Final = 18.0
LARGE_BOLD_POINTS: Final = 14.0


def _icon_colour(button: Any) -> str:
    """Die häufigste deckende Farbe im Symbol eines Knopfs, als ``#rrggbb``."""
    from collections import Counter

    image = button.icon().pixmap(button.iconSize(), float(button.devicePixelRatioF())).toImage()
    counted: Counter[int] = Counter()
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() >= 200:
                counted[pixel.rgb() & 0xFFFFFF] += 1
    if not counted:
        return str(button.palette().color(button.foregroundRole()).name())
    return f"#{counted.most_common(1)[0][0]:06x}"


def icon_entries(root: Any) -> list[dict[str, Any]]:
    """Bedienelemente ohne Text: Symbol, Kurzhilfe, Kürzel, Bildschärfe (G7, Z6).

    ``own`` ist wahr, wenn das Bild eines der eigenen Symbole ist
    (``icons.ThemedIcon``, verglichen am gerasterten Bild), falsch bei einem
    Symbol aus dem Thema des Systems, sonst offen für Stufe B; ``style`` bleibt
    offen. Kein Symbolknopf ist ein Haken oder Optionsknopf ohne Text und ein
    Knopf, der seinen Inhalt selbst zeigt — Beschriftungen darin oder eigenes
    Zeichnen (Probelauf F-12: ``RowCheckBox``, der Zahlenknopf in ``facts``).
    """
    from PySide6.QtWidgets import QAbstractButton, QToolButton

    surface = type(root).__name__
    found: list[dict[str, Any]] = []
    for button in root.findChildren(QAbstractButton):
        if not _visible(button) or _text_of(button).strip() or _shows_itself(button):
            continue
        icon = button.icon()
        ratio = float(button.devicePixelRatioF())
        pixmap = icon.pixmap(button.iconSize(), ratio) if not icon.isNull() else None
        action = button.defaultAction() if isinstance(button, QToolButton) else None
        shortcut = action.shortcut().toString() if action is not None else ""
        own: bool | None = None
        if pixmap is not None:
            known = _own_symbols(button.iconSize().width(), button.iconSize().height(), ratio)
            digest = _pixmap_digest(pixmap)
            own = True if digest and digest in known else (False if icon.name() else None)
        found.append(
            {
                "surface": surface,
                "widget": button.accessibleName() or mark_of(button) or type(button).__name__,
                "text": "",
                "icon": "" if icon.isNull() else (icon.name() or "eigen"),
                "own": own,
                "tooltip": button.toolTip(),
                "shortcut": shortcut,
                "style": None,
                "scale": ratio,
                "pixmap_ratio": float(pixmap.devicePixelRatio()) if pixmap is not None else None,
            }
        )
    return found


def _shows_itself(button: Any) -> bool:
    """Ob ein Knopf ohne Text kein Symbolknopf ist: Haken, Optionsknopf, Beschriftungen
    darin oder ein eigenes ``paintEvent`` in der Anwendung."""
    from PySide6.QtWidgets import QCheckBox, QLabel, QRadioButton

    if isinstance(button, (QCheckBox, QRadioButton)):
        return True
    if any(_visible(label) and _text_of(label).strip() for label in button.findChildren(QLabel)):
        return True
    return button.icon().isNull() and any(
        "paintEvent" in vars(cls)
        for cls in type(button).__mro__
        if not cls.__module__.startswith(("PySide6", "shiboken6", "builtins"))
    )


def _pixmap_digest(pixmap: Any) -> str:
    """Der Abdruck eines Bilds; leer, wenn es keines ist."""
    image = pixmap.toImage()
    if image.isNull():
        return ""
    return hashlib.sha256(bytes(image.constBits())).hexdigest()[:16]


_OWN_SYMBOLS: dict[tuple[int, int, float, str], frozenset[str]] = {}


def _own_symbols(width: int, height: int, ratio: float) -> frozenset[str]:
    """Die Abdrücke aller eigenen Symbole in dieser Größe und Farbe — einmal gerastert."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app.ui.icons import ThemedIcon, known

    colour = QApplication.palette().windowText().color().name()
    key = (width, height, ratio, colour)
    if key not in _OWN_SYMBOLS:
        digests = {
            _pixmap_digest(QIcon(ThemedIcon(name)).pixmap(QSize(width, height), ratio))
            for name in known()
        }
        _OWN_SYMBOLS[key] = frozenset(digests - {""})
    return _OWN_SYMBOLS[key]


def animation_entries(root: Any) -> list[dict[str, Any]]:
    """Übergänge unter ``root`` mit Dauer, Ziel und Eigenschaft (G8).

    Ohne die Geometrie, die Qts Hauptfenster selbst animiert, wenn es Mittelteil,
    Leisten und Andockflächen neu legt (``QWidgetAnimator``, Dauer 0 ohne
    Animation): Sie ist kein Zustandswechsel der Anwendung (Probelauf F-13).
    """
    from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation
    from PySide6.QtWidgets import QDockWidget, QMainWindow, QToolBar

    surface = type(root).__name__
    found: list[dict[str, Any]] = []
    for animation in root.findChildren(QAbstractAnimation):
        owner = animation.parent()
        target = animation.targetObject() if isinstance(animation, QPropertyAnimation) else None
        prop = bytes(animation.propertyName()).decode() if target is not None else ""
        holder = target.parentWidget() if callable(getattr(target, "parentWidget", None)) else None
        laid_out_by_qt = prop == "geometry" and (
            isinstance(target, (QDockWidget, QToolBar))
            or (isinstance(holder, QMainWindow) and target is holder.centralWidget())
        )
        if laid_out_by_qt:
            continue
        found.append(
            {
                "surface": surface,
                "widget": name_of(owner)
                if hasattr(owner, "accessibleName")
                else type(owner).__name__,
                "duration_ms": float(animation.duration()),
                "target": type(target).__name__ if target is not None else "",
                "property": prop,
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


def picture_digest(widget: Any) -> str:
    """Der Abdruck des Bilds, das ein Widget gerade zeigt."""
    return _picture_digest(widget)


def _reacts_to_pressing(widget: Any) -> bool:
    """Ob an ``pressed`` etwas hängt — dann löste schon das Drücken eine Handlung aus."""
    from PySide6.QtCore import SIGNAL

    return bool(widget.receivers(SIGNAL("pressed()")) > 0)


def state_images(widget: Any, focus: str | None = None) -> dict[str, str]:
    """Ein Bildabdruck je Zustand, hergestellt über gesendete Ereignisse (G5, Plan 3.3).

    Ruhe: die Maus außerhalb. Darüber: die Maus fährt hinein. Fokus: der
    Abdruck, den die Tab-Kette aufnahm, als Tab den Knopf erreichte
    (``focus``, :func:`tab_chain` mit ``on_focus``) — nicht ``setFocus``
    (Review L2). Gedrückt: die Taste unten, dann außerhalb losgelassen — so
    löst der Knopf nicht aus; hängt schon an ``pressed`` eine Handlung, wird
    nicht gedrückt. Was nicht aufgenommen ist, fehlt im Ergebnis, und D0-U nennt
    es ungemessen.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    outside = QPoint(-widget.width(), -widget.height())
    QTest.mouseMove(widget, outside)
    QApplication.processEvents()
    images: dict[str, str] = {"rest": _picture_digest(widget)}
    centre = widget.rect().center()
    QTest.mouseMove(widget, centre)
    QApplication.processEvents()
    images["hover"] = _picture_digest(widget)
    if focus:
        images["focus"] = focus
    if not _reacts_to_pressing(widget):
        QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
        QApplication.processEvents()
        images["pressed"] = _picture_digest(widget)
        QTest.mouseMove(widget, outside)
        QTest.mouseRelease(
            widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, outside
        )
        QApplication.processEvents()
    return images


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
                        "target": vocabulary_name(button),
                        "clicked": False,
                        "effect": None,
                    }
                    for button in frame.findChildren(QAbstractButton)
                    if _visible(button) and _text_of(button) and button.isEnabled()
                ],
            }
        )
    for button in window.findChildren(QPushButton):
        # Die Kurzhilfe zuerst, wie ``function_surface.grey_reason``: Sie zeigt der
        # graue Knopf dem Kunden; die Beschreibung kann vom offenen stammen (F-34).
        reason = button.toolTip() or button.accessibleDescription()
        if _visible(button) and not button.isEnabled() and reason:
            found.append({"text": reason, "actions": []})
    return [*found, *_house_messages()]


def _house_messages() -> list[dict[str, Any]]:
    """Offene Meldungen im Hausstil (``MessageDialog``, FD-21) mit ihren Handlungen.

    Gelesen über das, was der Dialog öffentlich führt: ``text()`` wie Strg+C,
    ``buttons()`` und ihre Rolle. Der Ausgang (*Schließen*, Escape) ist keine
    Handlung, die das Problem löst — er zählte sonst als „ohne Wirkung“ (V5).
    """
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    found: list[dict[str, Any]] = []
    for dialog in QApplication.topLevelWidgets():
        if "MessageDialog" not in _classes(dialog) or not dialog.isVisible():
            continue
        exits = QDialogButtonBox.ButtonRole.RejectRole
        actions = [
            {
                "label": _text_of(button),
                "target": vocabulary_name(button),
                "clicked": False,
                "effect": None,
            }
            for button in dialog.buttons()
            if _visible(button)
            and button.isEnabled()
            and dialog.button_box.buttonRole(button) != exits
        ]
        found.append({"text": dialog.text(), "actions": actions})
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
