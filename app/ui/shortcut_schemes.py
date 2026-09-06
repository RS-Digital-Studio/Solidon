"""Zwei Kürzelbelegungen, eine Quelle (Konzept P15 §7 Etappe 8, E7).

Das Kürzel einer Operation steht im Register (§10, Leitprinzip 3). Diese
Tabelle legt sich darüber, so wie die Menügruppen aus P14 sich über die
Kategorien legen: sie erfindet nichts, sie ordnet um.

**Warum überhaupt zwei.** Wer aus Fusion, Onshape oder SolidWorks kommt, hat
`E` für Extrudieren und `F` für Verrunden in den Fingern; ihn zu zwingen,
`Strg+B` zu lernen, kostet ihn bei jedem Griff eine Zehntelsekunde und uns den
Satz „fühlt sich fremd an". Wer von Solidon kommt, will das Gegenteil. Beide
zu bedienen ist eine Tabelle, keine Weltanschauung.

Die Vorgabe bleibt die heutige. Eine Umstellung ist eine Einstellung, kein
Modus (§2.5) — sie ändert nur, welche Taste welchen Menüeintrag auslöst.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QLineEdit,
    QPlainTextEdit,
)

from app.i18n import TranslatableText, _

#: Der Fusion-nahe Satz: einzelne Buchstaben für das, was man dauernd tut.
#: Nur Operationen stehen darin — die Fensterbefehle (Speichern, Öffnen,
#: Rückgängig) sind überall dieselben und werden nicht angefasst.
FUSION: Final[dict[str, str]] = {
    "sketch_extrude": "E",
    "push_face": "Q",
    "fillet_edges": "F",
    "chamfer_edges": "C",
    "translate_object": "M",
    "rotate_object": "R",
    "drill_hole": "H",
    "duplicate_object": "Ctrl+D",
    "mirror_object": "Ctrl+M",
    "pattern": "P",
}

#: Die Belegungen mit ihrem Namen. ``default`` ist leer: dort gilt, was im
#: Register steht, und eine Tabelle, die es abschreibt, wäre eine zweite
#: Wahrheit.
SCHEMES: Final[dict[str, tuple[TranslatableText, dict[str, str]]]] = {
    "default": (_("Solidon"), {}),
    "fusion": (_("Wie Fusion und Onshape"), FUSION),
}


def shortcut_for(name: str, declared: str | None, scheme: str) -> str | None:
    """Welche Taste diese Operation in dieser Belegung führt.

    Was die Belegung nicht nennt, behält sein Kürzel aus dem Register — eine
    Belegung ist eine Änderung an einzelnen Tasten, keine vollständige zweite
    Liste, die beim nächsten neuen Kürzel auseinanderläuft.
    """
    table = SCHEMES.get(scheme, SCHEMES["default"])[1]
    return table.get(name, declared)


#: Tasten, die dem Bedienelement mit dem Fokus gehören, nicht dem Fenster.
#:
#: Pos1 ist der Fall, an dem es auffiel: Als Menükürzel („Einpassen")
#: fensterweit gebunden, feuert es auch dann, wenn der Fokus im Objektbaum oder
#: im Verlauf steht — dort ist Pos1 die Taste, mit der jede Liste dieser Welt an
#: ihren Anfang springt. Gemessen: sechs Drücke im Baum, sechsmal die Kamera,
#: nie die Liste.
#:
#: **Nur die vier.** Der naheliegende Fix — jede Sequenz ohne Zusatztaste
#: gehört dem Bedienelement — nähme den Ziffern 1 bis 6 ihre Wirkung, sobald
#: eine Liste den Fokus hat, und das ist der Normalfall: Die Darstellungsarten
#: sind Fensterbefehle und sollen es bleiben. Die Grenze verläuft zwischen
#: *Bewegen im Inhalt* und *Befehl an das Fenster*, und dafür gibt es genau
#: diese vier Tasten.
NAVIGATION_KEYS: Final[frozenset[int]] = frozenset(
    {
        int(Qt.Key.Key_Home),
        int(Qt.Key.Key_End),
        int(Qt.Key.Key_PageUp),
        int(Qt.Key.Key_PageDown),
    }
)


def belongs_to_the_focus(key: int, widget: object) -> bool:
    """Ob diese Taste jetzt dem Bedienelement gehört und nicht dem Fenster.

    Zwei Bedingungen, beide nötig: die Taste bewegt sich im Inhalt (siehe
    :data:`NAVIGATION_KEYS`), und im Fokus steht etwas, das einen Inhalt hat,
    in dem man sich bewegen kann — eine Liste, ein Baum, ein Textfeld, ein
    Zahlenfeld oder Regler.

    Als reine Funktion, damit die Regel prüfbar bleibt, ohne Tasten zu
    simulieren: Was Qt aus einem Tastendruck macht, hängt an der Fensterhülle,
    die Entscheidung darin nicht.
    """
    if int(key) not in NAVIGATION_KEYS:
        return False
    return isinstance(
        widget, (QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QLineEdit, QPlainTextEdit)
    )


class NavigationKeys(QObject):
    """Der Filter, der die vier Tasten dem Fokus überlässt.

    Ein eigenes Objekt und keine Methode am Fenster: Das ``ShortcutOverride``
    geht an das Bedienelement mit dem Fokus, also muss der Filter an der
    **Anwendung** hängen — und dort genau einmal. Je Fenster installiert wuchs
    die Filterkette mit jedem gebauten Fenster, und jedes Ereignis der
    Anwendung lief durch alle: In der Suite, die über zweihundert Fenster in
    einem Prozess baut, blieb der Lauf bei 97 % stehen. Gemessen, zweimal, nach
    zehn Minuten abgebrochen — kein Fehler, nur Sirup.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Nimmt das ``ShortcutOverride`` an, wo die Taste dem Inhalt gehört.

        Gefragt wird ``watched`` und nicht der Fokus der Anwendung: Das
        Ereignis geht an das Bedienelement, das die Taste bekäme, und das ist
        genau die Frage. Über den Fokus gefragt hinge die Antwort daran, ob das
        Fenster gerade sichtbar ist — in der Suite ist es das nicht.

        Und ``watched`` wird geprüft, bevor irgendwer damit rechnet: Beim
        Abbau einer GL-Fläche mitten in der Suite (QPlatformSurfaceEvent)
        kann shiboken unter einem recycelten Zeiger einen fremden Wrapper
        liefern — ein ``QWidgetItem`` ist kein ``QObject``, und der
        ``super()``-Aufruf platzte daran mit einer TypeError-Kaskade durch
        jede Python-Override auf dem Stapel (gemessen am 25.08.2026 in
        test_ui.py). Nicht unser Ereignis; es wird durchgereicht.
        """
        if not isinstance(watched, QObject):  # laut Signatur unmöglich — siehe oben
            return False  # type: ignore[unreachable]
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and isinstance(event, QKeyEvent)
            and belongs_to_the_focus(event.key(), watched)
        ):
            event.accept()
            return True
        handled: bool = super().eventFilter(watched, event)
        return handled


#: Der eine Filter der Anwendung. Ein zweiter täte dasselbe zweimal.
_INSTALLED: NavigationKeys | None = None


def install_navigation_keys() -> NavigationKeys | None:
    """Hängt den Filter an die Anwendung — beim zweiten Aufruf nichts mehr.

    Gibt ihn zurück, damit ein Test ihn fragen kann, ohne Tasten zu
    simulieren: Was Qt aus einem Tastendruck macht, hängt an der Fensterhülle,
    die Entscheidung darin nicht.
    """
    global _INSTALLED
    application = QCoreApplication.instance()
    if application is None:
        return None
    if _INSTALLED is None:
        _INSTALLED = NavigationKeys(application)
        application.installEventFilter(_INSTALLED)
    return _INSTALLED
