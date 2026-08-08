"""Der Chat (Bauplan §26.3, §2.5).

Die rechte Seite des Fensters, neben dem Prüfbericht. Worauf es hier ankommt,
sind nicht die Sprechblasen, sondern die Kopplung: jeder Beitrag zeigt, welche
Transaktion er erzeugt hat, und ein Beitrag, dessen Transaktion zurückgenommen
wurde, wird ausgegraut statt gelöscht — er ist passiert, er gilt nur nicht
mehr.

Ein Vorschlag wird nie von selbst angewandt. Er kommt an, der Viewport zeigt,
was sich ändern würde (§18.7), und zwei Knöpfe entscheiden. Ohne Schlüssel sagt
das ganze Panel das in einer Zeile und hält sich heraus (§27).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.agent.context import is_discarded
from app.core.types import ChatEntry, Document
from app.i18n import tr
from app.ui.style import NORMAL

#: Wie ein Beitrag markiert wird, damit die Rollen ohne Farbe
#: auseinanderbleiben (§19.1).
ROLE_MARKER = {"user": ">", "agent": "*"}

DISCARDED_COLOUR = "#7a828c"

#: Wie hoch der Gesprächsverlauf mindestens ist, auch wenn nichts darin steht.
#:
#: Die Karten der rechten Spalte sind so hoch wie ihr Inhalt, und das ist für
#: einen Bericht richtig: fünf Befunde brauchen den Platz für fünf Befunde. Ein
#: Gespräch ist etwas anderes — es ist ein Arbeitsbereich, und seine Höhe sagt,
#: wofür er gedacht ist. Ungefähr ein halbes Dutzend Zeilen: genug, dass eine
#: Antwort mit Begründung hineinpasst, ohne dass der leere Zustand die halbe
#: Ansicht verdeckt.
EMPTY_TURNS_HEIGHT = 190


class ChatPanel(QWidget):
    """Gespräch, Eingabezeile, und die zwei Knöpfe, die ein Vorschlag braucht."""

    requestSent = Signal(str)
    accepted = Signal()
    discarded = Signal()
    setupRequested = Signal()
    """Der Benutzer will den fehlenden Zugang einrichten (§2.7)."""
    unlockRequested = Signal()
    """Der Benutzer will nach Ablauf des Testlaufs freischalten (§2 C)."""
    imageDropped = Signal(str)
    """Ein Bild ist im Chatfenster gelandet — Pfad als Text (Konzept P15, E8).

    Ein Foto oder eine Skizze ist eine Eingabe wie ein Satz; das ist Meshys
    eine Bedienidee, die ohne Cloud nachbaubar ist. Was daraus wird,
    entscheidet das Fenster — das Panel weiß nichts von Generierung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self.turns = QListWidget(self)
        self.turns.setWordWrap(True)
        self.turns.setAlternatingRowColors(False)
        # Ein Gespräch ist ein Arbeitsbereich und kein Text: seine Höhe folgt
        # nicht dem, was schon darin steht. Ohne diese Zeile war die Karte im
        # leeren Zustand hundertsiebzig Pixel hoch — neben tausendzweihundert
        # freien —, und was hineinkam, hatte neunundvierzig Pixel Platz. Wer
        # den Reiter öffnet, sieht so nicht, wofür er gedacht ist.
        self.turns.setMinimumHeight(EMPTY_TURNS_HEIGHT)

        self.hint = QLabel("", self)
        self.hint.setWordWrap(True)
        # §2.7: ein Hinweis, der nur feststellt, was fehlt, lässt den
        # Benutzer stehen. Der Knopf daneben führt dorthin, wo es behoben
        # wird — sichtbar nur, solange etwas zu beheben ist.
        self.setup = QPushButton(tr("Zugang einrichten …"), self)
        self.setup.clicked.connect(self.setupRequested)
        self.setup.setVisible(False)

        # Der Knopf für die andere fehlende Sache: nicht das Modell, der
        # Schlüssel. Beide führen dorthin, wo es behoben wird (§2.7).
        self.unlock = QPushButton(tr("Solidon freischalten …"), self)
        self.unlock.clicked.connect(self.unlockRequested)
        self.unlock.setVisible(False)

        # §27, ohne zu nörgeln: ein Satz, wenn das lokale Modell zu klein ist
        # oder fehlt — einmal sichtbar, solange es gilt, sonst gar nicht.
        self.notice = QLabel("", self)
        self.notice.setWordWrap(True)
        self.notice.setVisible(False)

        # Mehrzeilig: „Halter, 60 auf 40, zwei M4-Löcher im Abstand von 45,
        # Wandstärke 3" ist die Art Anfrage, für die der Chat da ist, und in
        # einer Zeile sieht man davon ein Drittel. Die Eingabetaste sendet
        # weiter — Umschalt und Eingabe macht den Absatz (§26.3).
        self.input = QPlainTextEdit(self)
        self.input.setPlaceholderText(tr("Was soll geändert werden?"))
        self.input.setTabChangesFocus(True)
        self.input.setFixedHeight(self.input.fontMetrics().lineSpacing() * 3 + 12)
        self.input.installEventFilter(self)
        self.send = QPushButton(tr("Senden"), self)
        self.send.clicked.connect(self._send)

        entry_row = QHBoxLayout()
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.addWidget(self.input, stretch=1)
        entry_row.addWidget(self.send)

        self.summary = QLabel("", self)
        self.summary.setWordWrap(True)
        self.accept_button = QPushButton(tr("Übernehmen"), self)
        self.accept_button.clicked.connect(self.accepted)
        self.discard_button = QPushButton(tr("Verwerfen"), self)
        self.discard_button.clicked.connect(self.discarded)

        decision_row = QHBoxLayout()
        decision_row.setContentsMargins(0, 0, 0, 0)
        decision_row.addWidget(self.accept_button)
        decision_row.addWidget(self.discard_button)
        decision_row.addStretch(1)

        self.decision = QWidget(self)
        decision_layout = QVBoxLayout(self.decision)
        decision_layout.setContentsMargins(0, 0, 0, 0)
        decision_layout.addWidget(self.summary)
        decision_layout.addLayout(decision_row)
        self.decision.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.addWidget(self.hint)
        layout.addWidget(self.notice)
        layout.addWidget(self.setup)
        layout.addWidget(self.unlock)
        layout.addWidget(self.turns, stretch=1)
        layout.addWidget(self.decision)
        layout.addLayout(entry_row)

        self._available = False
        self._busy = False
        self._locked = False
        self.set_available(False)

    # --- state ------------------------------------------------------------------

    def set_available(self, available: bool, backend: str = "") -> None:
        """§27: ohne Schlüssel ist der Chat aus und sagt das — einmal, ohne zu
        nörgeln.
        """
        self._available = available
        self.hint.setText(
            f"{tr('Modell')}: {backend}"
            if available
            else tr(
                "Der Chat braucht einen Zugang zu einem Sprachmodell. "
                "Alles andere funktioniert ohne."
            )
        )
        self.setup.setVisible(not available)
        self._update_enabled()

    def set_notice(self, text: str) -> None:
        """Ein Hinweis unter dem Zustand — leer heißt: nichts zu sagen."""
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def set_locked(self, locked: bool) -> None:
        """§2 C: nach Ablauf des Testlaufs zählt der Chat zur schreibenden
        Seite — das Panel sagt es in einer Zeile mit dem Weg zurück und hält
        sich sonst heraus (§27).

        Wird nach :meth:`set_available` gerufen und überschreibt dessen
        Hinweis; beim Entsperren stellt der nächste ``set_available``-Lauf
        ihn wieder her.
        """
        self._locked = locked
        self.unlock.setVisible(locked)
        if locked:
            self.hint.setText(
                tr("Der Testzeitraum ist abgelaufen — der Chat braucht einen Lizenzschlüssel.")
            )
            self.setup.setVisible(False)
        self._update_enabled()

    def set_busy(self, busy: bool) -> None:
        """Während das Modell denkt, wird nichts weiter gesendet — ein Zug nach
        dem anderen.
        """
        self._busy = busy
        self._update_enabled()

    @property
    def busy(self) -> bool:
        return self._busy

    def _update_enabled(self) -> None:
        usable = self._available and not self._busy and not self._locked
        self.input.setEnabled(usable)
        self.send.setEnabled(usable)

    def show_document(self, document: Document) -> None:
        """Zeichnet das Gespräch neu und graut aus, was zurückgenommen
        wurde (§26.3).
        """
        self.turns.clear()
        for entry in document.chat:
            self.turns.addItem(_item(entry, is_discarded(entry, document)))
        self.turns.scrollToBottom()

    def show_proposal(self, preview: Any | None) -> None:
        """Bietet die Entscheidung an, mit dem, was sich änderte, in
        Zahlen (§18.7).
        """
        if preview is None:
            self.decision.setVisible(False)
            self.summary.setText("")
            return
        self.summary.setText(describe(preview))
        self.decision.setVisible(True)

    # --- input ------------------------------------------------------------------

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Eingabe sendet, Umschalt und Eingabe macht einen Absatz.

        Die verbreitete Aufteilung in jedem Chatfenster — und die einzige, bei
        der ein mehrzeiliges Feld nicht heißt, dass man zum Senden zur Maus
        greift.
        """
        if watched is self.input and event.type() == QEvent.Type.KeyPress:
            enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            if enter and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._send()
                return True
        handled: bool = super().eventFilter(watched, event)
        return handled

    def _send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.requestSent.emit(text)

    # --- ein Bild als Eingabe (Konzept P15, E8) ---------------------------------

    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Ein Bild darf hier landen, alles andere nicht.

        Geprüft wird die Endung und nicht der angebotene Typ: ein Dateimanager
        beschriftet Dateien unterschiedlich, die Endung ist überall dieselbe.
        """
        if _dropped_image(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        path = _dropped_image(event)
        if path is None:
            return
        event.acceptProposedAction()
        self.imageDropped.emit(path)


def _dropped_image(event: Any) -> str | None:
    """Der Pfad des abgelegten Bildes, oder ``None``.

    Was als Bild gilt, steht im Generierungsdialog — dort füllt dieselbe Liste
    auch den Dateidialog. Genommen werden die Endungen selbst und nicht der
    Filtertext: der ist übersetzt, und ein abgelegtes Bild in einer englischen
    Oberfläche wäre sonst keines mehr.
    """
    from app.ui.generate_dialog import IMAGE_SUFFIXES

    data = event.mimeData()
    if not data.hasUrls():
        return None
    endings = IMAGE_SUFFIXES
    for url in data.urls():
        name = url.toLocalFile()
        if name and name.lower().endswith(endings):
            return str(name)
    return None


def _item(entry: ChatEntry, discarded: bool) -> QListWidgetItem:
    marker = ROLE_MARKER.get(entry.role, "-")
    item = QListWidgetItem(f"{marker} {entry.text}")
    if discarded:
        # Nicht gelöscht: der Beitrag ist passiert. Er gilt nur nicht mehr (§26.3).
        item.setForeground(QColor(DISCARDED_COLOUR))
        font = QFont(item.font())
        font.setStrikeOut(True)
        item.setFont(font)
        item.setToolTip(tr("Zurückgenommen"))
    elif entry.transaction_id:
        item.setToolTip(f"{tr('Transaktion')} {entry.transaction_id}")
    if entry.origin is not None and entry.origin.model:
        existing = item.toolTip()
        item.setToolTip(f"{existing}\n{entry.origin.model}".strip())
    item.setData(Qt.ItemDataRole.UserRole, entry.id)
    return item


#: Wie viele Namen die Zusammenfassung aufzählt, bevor sie zählt.
NAMED_AT_MOST = 3


def _named(entries: list[Any], word: str) -> str:
    """Die Namen der Einträge, oder ihre Anzahl, wenn es zu viele werden."""
    if len(entries) > NAMED_AT_MOST:
        return f"{len(entries)} × {word}"
    names = [getattr(entry, "op", None) or str(entry) for entry in entries]
    return f"{word}: " + ", ".join(names)


def describe(preview: Any) -> str:
    """Was der Vorschlag täte, in einer lesbaren Zeile.

    Mit Namen, nicht nur mit Zahlen: eine Zeile, die „zwei Operationen" meldet,
    verlangt vom Nutzer, über etwas zu entscheiden, das er nicht gelesen hat.
    Ab vier Schritten wird gezählt — dann ist die Aufzählung länger als die
    Zeile und der Verlauf daneben die bessere Quelle.
    """
    proposal = preview.proposal
    parts: list[str] = []
    if proposal.drafts:
        parts.append(_named(proposal.drafts, tr("Operation")))
    if proposal.parameters:
        parts.append(_named(list(proposal.parameters), tr("Parameter")))
    if proposal.fits:
        parts.append(f"{len(proposal.fits)} × {tr('Passung')}")
    if proposal.undo_of:
        parts.append(f"{tr('Rücknahme')} {proposal.undo_of}")

    difference = getattr(preview, "difference", None)
    if difference is not None and difference.changed:
        parts.append(
            f"+{difference.added_volume / 1000.0:.2f} cm³ / "
            f"-{difference.removed_volume / 1000.0:.2f} cm³"
        )
    if proposal.stopped:
        parts.append(tr("Grenze erreicht"))
    return " · ".join(parts) or tr("Keine Änderung")
