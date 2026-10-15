"""Ob gerade geändert werden darf — die eine Auskunft für jeden Zugang (FD-5, FD-26).

Die Hürde liegt im Kern (``activation.require``, ``kern.md`` „Die
Lizenzgrenze“); die Oberfläche graut vorher aus und nennt den Grund. Menü,
Suche und Karte der Handlungen fragten den Freischaltzustand je für sich ab,
Prüfbericht, Merkmalfenster und Kontextmenüs gar nicht: In der Demo und ohne
Geräteaktivierung stand *Auf das Bett setzen* bedienbar da, und der Klick
endete im Meldungsfenster. Jeder Zugang, der eine ändernde Handlung anbietet,
fragt deshalb hier.

Nur Lesendes läuft weiter (Konzept §2 C). Was eine Handlung des Kerns ist
(``app.core.errors``), gilt als ändernd, solange sie nicht in
:data:`READING_ACTIONS` steht — eine neue Handlung ist im gesperrten Zustand
lieber grau als eine Sackgasse. Für die Fensterbefehle gilt dasselbe
(:data:`READING_COMMANDS`): *Parameter anlegen …* stand ohne Freischaltung
offen, weil das Fenster die Aktion nicht festhielt und niemand sie sperrte;
seither graut :func:`close_commands` jede Zeile aus, die nicht als lesend
geführt ist.

Grau heißt grau **mit Grund**: :func:`say_refusal` legt ihn in Kurzhilfe und
zugängliche Beschreibung (eine Aktion: Kurzhilfe und Statuszeile) und gibt
den eigenen Satz zurück, sobald die Sperre fällt (FD-27).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QScrollBar,
    QWidget,
)

from app.core import activation
from app.core.registry import REGISTRY
from app.core.types import Document, OpId
from app.i18n import tr
from app.ui.dialogs import licence_lock_line
from app.ui.labels import step_number

if TYPE_CHECKING:
    from app.ui.panels import HistoryPanel
    from app.ui.tool_strip import ToolStrip

#: Handlungen des Kerns, die nichts ändern und nichts herausgeben: zeigen,
#: erklären, einen Dialog zum Ansehen öffnen, freischalten, Hilfe holen. Sie
#: bleiben im gesperrten Zustand bedienbar; jede andere graut aus.
READING_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "activate_offline",
        "activate_online",
        "adopt_printer",
        "buy_licence",
        "cancel",
        "cancel_split",
        "check_profile",
        "check_updates",
        "choose_printer",
        "choose_slicer",
        "deactivate_device",
        "enter_licence_key",
        "install",
        "open_download_page",
        "open_in_browser",
        "open_print_settings",
        "open_settings",
        "report_error",
        "set_up_chat",
        "show_details",
        "show_feature",
        "show_history",
        "show_layers",
        "show_location",
        "show_locations",
        "show_output",
        "show_step_values",
        "show_support_need",
        "stop_inserting",
        "try_key_again",
    }
)

#: Menüs der Leiste, deren Zeilen nur zeigen: Darstellung, Kamera, Thema und
#: Navigation, Handbuch und Freischaltung. Gelesen am ``objectName`` des
#: Menüs (:func:`app.core.guides.menubar_name`), gleich in jeder Sprache.
READING_MENUS: Final[frozenset[str]] = frozenset({"menubar.ansicht", "menubar.hilfe"})

#: Fensterbefehle außerhalb dieser Menüs, die gesperrt offen bleiben — unter
#: dem Namen, unter dem Wortschatz und Suche sie führen: der ``objectName``
#: der Aktion oder, wo es keine gibt, die Kennung der Suche
#: (``MainWindow.window_commands``). Öffnen, Speichern, Ansehen, Einstellen
#: und Rückgängig (§2 C: „öffnen, drehen, messen, speichern“). *Material
#: kalibrieren* schreibt das Materialprofil und nicht das Dokument; *An den
#: Slicer übergeben* öffnet einen Dialog, dessen Slicen-Knopf selbst sperrt.
READING_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "menubar.an_den_slicer_uebergeben",
        "menubar.bausteinkatalog",
        "menubar.beenden",
        "menubar.chat_einrichten",
        "menubar.einstellungen",
        "menubar.filamentlager",
        "menubar.funktion_suchen",
        "menubar.g_code_gegenpruefen",
        "menubar.material_kalibrieren",
        "menubar.neu",
        "menubar.oeffnen",
        "menubar.rueckgaengig",
        "menubar.speichern",
        "menubar.speichern_unter",
        "menubar.wiederholen",
        "file.part_adopt",
        "file.part_share",
        "tool.analysis",
        "tool.explode",
        "tool.layers",
        "tool.measure",
        "tool.section",
    }
)

#: Kennungsfamilien der Suche, die nur einen Dialog an einer Stelle öffnen:
#: jede Einzeloption der Einstellungen (``settings.<option>``).
READING_FAMILIES: Final[tuple[str, ...]] = ("settings.",)

_CLOSED: Final = "change_lock_closed"
"""Merker an einer Aktion, die nur die Sperre grau hält (:func:`close_commands`)."""
_HELD: Final = "change_lock_enabled"
"""Ob ein Eingabefeld vor der Sperre bedienbar war (:func:`hold_inputs`)."""
_HOLDING: Final = "change_lock_holding"
"""Merker am Fenster: Es gibt gesperrte Fensterbefehle zurückzugeben."""
_SAID: Final = "change_lock_said"
_TIP: Final = "change_lock_tip"
_SECOND: Final = "change_lock_second"


def change_refusal() -> str:
    """Warum gerade nichts geändert werden darf — leer, wenn es geht.

    Der Satz kommt aus :func:`~app.ui.dialogs.licence_lock_line`, derselben
    Quelle wie Statuszeile und Freischaltdialog; er nennt je Zustand den
    nächsten Schritt (Schlüssel, Geräteaktivierung, Neuinstallation).
    """
    state = activation.state()
    return "" if state.unlocked else licence_lock_line(state)


def action_refusal(action_id: str, *, halt: str = "", at_halt: bool = False) -> str:
    """Warum diese Handlung eines Befunds oder Fehlers gerade nicht geht — oder leer.

    ``halt`` ist der Satz des Halts (:func:`halt_line`), wenn die Kette anhält:
    Eine ändernde Handlung geht dann nicht, und der Satz nennt den Schritt und
    den Weg weiter (FD-104). Vor dem Klick, nicht erst als Absage danach.

    **Ausgenommen sind die Wege des Halts selbst** (RA-3): ``at_halt`` sagt,
    dass die Handlung am haltenden Befund steht (``revision.halt_finding``) —
    demselben Befund, dessen Wege ``Session.halt_in_the_way`` als die des Halts
    anbietet. Eine Liste von Kennungen entschied das vorher, graute am Halt
    „braucht einen ausgeschalteten Schritt“ beide Wege und gab hinter einem
    fremden Halt Wege frei, die die Sitzung danach ablehnte.
    """
    if action_id in READING_ACTIONS:
        return ""
    return change_refusal() or ("" if at_halt else halt)


def halt_line(document: Document | None, stopped_at: OpId | None) -> str:
    """Warum gerade kein neuer Schritt geht — die Kette hält an (§15.3) — oder leer.

    Eine Quelle für Fensterbefehle (``MainWindow._halt_reason``) und
    Befundhandlungen (:func:`action_refusal`): Schrittnummer und Titel wie im
    Verlauf, und der Weg weiter steht im Prüfbericht.
    """
    if document is None or stopped_at is None:
        return ""
    step = next((entry for entry in document.ops if entry.id == stopped_at), None)
    title = (
        REGISTRY.get(step.op).title
        if step is not None and REGISTRY.has(step.op)
        else str(stopped_at)
    )
    return str(
        tr(
            "Die Kette hält an Schritt {number} ({step}) an — ein neuer Schritt dahinter "
            "würde nicht gerechnet. Der Weg weiter steht im Prüfbericht.",
            number=step_number(document, stopped_at),
            step=title,
        )
    )


def refused(say: Callable[[str], object]) -> bool:
    """Gesperrt: den Grund sagen und ``True`` — der Riegel hinter der grauen Zeile.

    Für die Wege an Menü und Knopf vorbei (Ablegen, Tour, ein Signal der
    Leiste): Sie hören denselben Satz, bevor ein Dialog aufgeht, statt danach
    im Meldungsfenster zu enden.
    """
    reason = change_refusal()
    if reason:
        say(reason)
    return bool(reason)


def command_refusal(name: str) -> str:
    """Warum dieser Fensterbefehl gerade nicht geht — oder leer (FD-26).

    ``name`` ist der ``objectName`` der Aktion oder die Kennung der Suche.
    Unbekanntes gilt als ändernd, wie bei :func:`action_refusal`.
    """
    if name in READING_COMMANDS or name.startswith(READING_FAMILIES):
        return ""
    return change_refusal()


def computing_refusal() -> str:
    """Warum eine Befundhandlung während der Rechnung wartet — mit dem Weg (FD-30).

    Der Befund gehört zum Stand vor der laufenden Berechnung; eine Handlung
    daran träfe ein Teil, das es gleich nicht mehr gibt (RM-534). Die Sperre
    fällt von selbst, und genau das ist der Ausweg, den der Satz nennt.
    """
    return str(
        tr(
            "Der Befund gehört zum vorigen Stand. Die Handlung ist wieder frei, "
            "sobald die Berechnung fertig ist."
        )
    )


def say_refusal(target: QWidget | QAction, reason: str) -> None:
    """Der Grund in Kurzhilfe und zugänglicher Beschreibung — oder zurück zum eigenen Satz.

    Ein Bildschirmleser las an einer grauen Befundhandlung, was sie täte,
    statt warum sie nicht geht (FD-27): gesetzt war nur die Kurzhilfe. Eine
    Aktion hat keine zugängliche Beschreibung; dort trägt die Statuszeile den
    zweiten Satz. Der eigene Satz wird gemerkt und kommt mit leerem
    ``reason`` zurück; hat jemand ihn während der Sperre neu geschrieben,
    gilt der neue. Freigeben und Sperren der Bedienung bleibt beim Aufrufer.
    """
    if reason:
        previous = target.property(_SAID)
        if target.toolTip() != previous:
            target.setProperty(_TIP, target.toolTip())
        if _second_text(target) != previous:
            target.setProperty(_SECOND, _second_text(target))
        target.setProperty(_SAID, reason)
        target.setToolTip(reason)
        _set_second_text(target, reason)
        return
    if target.property(_SAID) is not None:
        if target.toolTip() == target.property(_SAID):
            target.setToolTip(str(target.property(_TIP) or ""))
        if _second_text(target) == target.property(_SAID):
            _set_second_text(target, str(target.property(_SECOND) or ""))
        for name in (_SAID, _TIP, _SECOND):
            target.setProperty(name, None)


def _second_text(target: QWidget | QAction) -> str:
    return target.statusTip() if isinstance(target, QAction) else target.accessibleDescription()


def _set_second_text(target: QWidget | QAction, text: str) -> None:
    if isinstance(target, QAction):
        action = target
        action.setStatusTip(text)
    else:
        target.setAccessibleDescription(text)


def hold_inputs(root: QWidget, reason: str) -> None:
    """Jedes Feld und jeder Knopf unter ``root`` grau mit Grund — oder wie vorher (FD-28).

    Für Zugänge ohne eigene Sperre: die Maßgruppe im Bild und die
    Parameterleiste nahmen ohne Freischaltung Eingaben an, die erst beim
    Übernehmen scheiterten. Gemerkt wird, ob ein Feld vorher bedienbar war;
    eine Beschriftung mit Partnerfeld bekommt den Grund als Satz. Rollbalken
    bleiben, damit sich Gesperrtes weiter ansehen lässt. Gefragt wird jedes
    Kind und nicht ein Merker an ``root``: Die Felder der Maßgruppe wandern
    zwischen Merkmalfenster und Bild (``keep_measure_group``) und kämen sonst
    unter einer neuen Wurzel gesperrt an.
    """
    for widget in (root, *root.findChildren(QWidget)):
        if isinstance(widget, QLabel):
            if widget.buddy() is not None:
                say_refusal(widget, reason)
            continue
        if not _is_input(widget):
            continue
        if reason:
            if widget.property(_HELD) is None:
                # Der eigene Zustand, nicht der geerbte: Ein Feld in einem eben
                # gesperrten Behälter gälte sonst als vorher gesperrt.
                own = not widget.testAttribute(Qt.WidgetAttribute.WA_ForceDisabled)
                widget.setProperty(_HELD, own)
            widget.setEnabled(False)
        elif widget.property(_HELD) is not None:
            widget.setEnabled(bool(widget.property(_HELD)))
            widget.setProperty(_HELD, None)
        say_refusal(widget, reason)


def _is_input(widget: QWidget) -> bool:
    """Ob das Widget eine Eingabe annimmt — das Textfeld in einem Zahlenfeld zählt nicht extra."""
    if isinstance(widget, QScrollBar):
        return False
    if isinstance(widget, QLineEdit):
        return not isinstance(widget.parentWidget(), QAbstractSpinBox | QComboBox)
    return isinstance(widget, QAbstractButton | QAbstractSpinBox | QComboBox | QAbstractSlider)


def changing_commands(window: QMainWindow) -> list[QAction]:
    """Jede Aktion der Menüleiste und des Fensters, die nicht als lesend geführt ist.

    Die Menüleiste ohne :data:`READING_MENUS`, dazu die Aktionen am Fenster
    selbst (Operationen der Karte, *Automatisch teilen*) mit Namen. Eine Zeile
    ohne Namen gilt als ändernd — grau ist sie lieber als eine Sackgasse.
    """
    from app.ui.guide_targets import menu_entries

    found: dict[QAction, None] = {}
    for top in window.menuBar().actions():
        menu = top.menu()
        if not isinstance(menu, QMenu) or menu.objectName() in READING_MENUS:
            continue
        for name, _menus, action in menu_entries(menu):
            if not _reading(name):
                found[action] = None
    for action in window.actions():
        name = action.objectName()
        if name and not _reading(name):
            found[action] = None
    return list(found)


def _reading(name: str) -> bool:
    return bool(name) and (name in READING_COMMANDS or name.startswith(READING_FAMILIES))


def close_commands(window: QMainWindow) -> list[QAction]:
    """Gesperrt: jeden ändernden Fensterbefehl grau stellen — zurück kommen sie (FD-26).

    Läuft am Ende von ``MainWindow._update_actions``, nach den eigenen
    Bedingungen der Einträge. Zurück kommen alle gesperrten Änderungen: Auch
    ein bereits grauer Eintrag braucht den aktuellen Grund. Ohne Sperre
    geschieht nichts.
    """
    if not change_refusal():
        return []
    closed = []
    for action in changing_commands(window):
        closed.append(action)
        action.setEnabled(False)
        action.setProperty(_CLOSED, True)
    window.setProperty(_HOLDING, True)
    return closed


def reopen_commands(window: QMainWindow) -> list[QAction]:
    """Freigeschaltet: was nur die Sperre grau hielt, wieder freigeben — zurück kommen sie.

    Läuft am Anfang von ``MainWindow._update_actions``: Was danach eine eigene
    Bedingung hat, setzt sie dort neu. Gesperrt geschieht nichts, und ohne
    vorherige Sperre auch — dann ist der Aufruf frei.
    """
    if change_refusal() or window.property(_HOLDING) is None:
        return []
    window.setProperty(_HOLDING, None)
    reopened = [action for action in changing_commands(window) if action.property(_CLOSED)]
    for action in reopened:
        action.setEnabled(True)
        action.setProperty(_CLOSED, None)
    return reopened


def hold_history_preview(panel: HistoryPanel) -> None:
    """Der Vorschauknopf sperrt Änderungen, lässt den letzten Stand als Rückweg frei.

    Die Zielmenge des Verlaufs ist die Quelle: ``None`` beendet nur eine
    Einfügemarke. Zielwechsel und neue Freischaltung führen denselben Knopf
    nach, ohne die laufende Vergleichsvorschau neu anzufordern.
    """
    count = panel.timeline_slider.value()
    if not 1 <= count <= len(panel._timeline_targets):
        return
    before = panel._timeline_targets[count - 1]
    reason = change_refusal() if before is not None else ""
    panel.timeline_insert.setEnabled(not reason)
    say_refusal(panel.timeline_insert, reason)


def close_tools(strip: ToolStrip) -> None:
    """Gesperrt grauen die Werkzeuge, die ändern — *Bewegen* und *Teilen* —, mit Grund.

    Gefragt unter der Kennung der Suche (``tool.<name>``); Schnitt, Messen,
    Analyse, Schichten und Explosion lesen nur und bleiben.
    """
    for key in strip.tools():
        reason = command_refusal(f"tool.{key}")
        if reason:
            strip.set_tool_usable(key, False, reason)
