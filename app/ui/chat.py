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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.agent.context import is_discarded
from app.core.types import ChatEntry, Document
from app.i18n import tr

#: Wie ein Beitrag markiert wird, damit die Rollen ohne Farbe
#: auseinanderbleiben (§19.1).
ROLE_MARKER = {"user": ">", "agent": "*"}

DISCARDED_COLOUR = "#7a828c"


class ChatPanel(QWidget):
    """Gespräch, Eingabezeile, und die zwei Knöpfe, die ein Vorschlag braucht."""

    requestSent = Signal(str)
    accepted = Signal()
    discarded = Signal()
    setupRequested = Signal()
    """Der Benutzer will den fehlenden Zugang einrichten (§2.7)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.turns = QListWidget(self)
        self.turns.setWordWrap(True)
        self.turns.setAlternatingRowColors(False)

        self.hint = QLabel("", self)
        self.hint.setWordWrap(True)
        # §2.7: ein Hinweis, der nur feststellt, was fehlt, lässt den
        # Benutzer stehen. Der Knopf daneben führt dorthin, wo es behoben
        # wird — sichtbar nur, solange etwas zu beheben ist.
        self.setup = QPushButton(tr("Zugang einrichten …"), self)
        self.setup.clicked.connect(self.setupRequested)
        self.setup.setVisible(False)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText(tr("Was soll geändert werden?"))
        self.input.returnPressed.connect(self._send)
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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.hint)
        layout.addWidget(self.setup)
        layout.addWidget(self.turns, stretch=1)
        layout.addWidget(self.decision)
        layout.addLayout(entry_row)

        self._available = False
        self._busy = False
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

    def set_busy(self, busy: bool) -> None:
        """Während das Modell denkt, wird nichts weiter gesendet — ein Zug nach
        dem anderen.
        """
        self._busy = busy
        self._update_enabled()

    def _update_enabled(self) -> None:
        usable = self._available and not self._busy
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

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.requestSent.emit(text)


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


def describe(preview: Any) -> str:
    """Was der Vorschlag täte, in einer lesbaren Zeile."""
    proposal = preview.proposal
    parts: list[str] = []
    if proposal.drafts:
        parts.append(f"{len(proposal.drafts)} × {tr('Operation')}")
    if proposal.parameters:
        parts.append(f"{len(proposal.parameters)} × {tr('Parameter')}")
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
