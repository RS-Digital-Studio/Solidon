"""The chat (Bauplan §26.3, §2.5).

The right-hand side of the window, next to the report. What matters here is not
the bubbles but the coupling: every turn shows which transaction it produced,
and a turn whose transaction was taken back is greyed out rather than deleted —
it happened, it just does not hold any more.

A proposal is never applied by itself. It arrives, the viewport shows what would
change (§18.7), and two buttons decide. Without a key the whole panel says so in
one line and stays out of the way (§27).
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

#: How a turn is marked, so the roles stay apart without colour (§19.1).
ROLE_MARKER = {"user": ">", "agent": "*"}

DISCARDED_COLOUR = "#7a828c"


class ChatPanel(QWidget):
    """Conversation, input line, and the two buttons a proposal needs."""

    requestSent = Signal(str)
    accepted = Signal()
    discarded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.turns = QListWidget(self)
        self.turns.setWordWrap(True)
        self.turns.setAlternatingRowColors(False)

        self.hint = QLabel("", self)
        self.hint.setWordWrap(True)

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
        layout.addWidget(self.turns, stretch=1)
        layout.addWidget(self.decision)
        layout.addLayout(entry_row)

        self._available = False
        self._busy = False
        self.set_available(False)

    # --- state ------------------------------------------------------------------

    def set_available(self, available: bool, backend: str = "") -> None:
        """§27: without a key the chat is off and says so, once, without nagging."""
        self._available = available
        self.hint.setText(
            f"{tr('Modell')}: {backend}"
            if available
            else tr(
                "Der Chat braucht einen Zugang zu einem Sprachmodell. "
                "Alles andere funktioniert ohne."
            )
        )
        self._update_enabled()

    def set_busy(self, busy: bool) -> None:
        """While the model is thinking nothing more is sent — one turn at a time."""
        self._busy = busy
        self._update_enabled()

    def _update_enabled(self) -> None:
        usable = self._available and not self._busy
        self.input.setEnabled(usable)
        self.send.setEnabled(usable)

    def show_document(self, document: Document) -> None:
        """Redraw the conversation, greying out what was taken back (§26.3)."""
        self.turns.clear()
        for entry in document.chat:
            self.turns.addItem(_item(entry, is_discarded(entry, document)))
        self.turns.scrollToBottom()

    def show_proposal(self, preview: Any | None) -> None:
        """Offer the decision, with what would change in numbers (§18.7)."""
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
        # Not deleted: the turn happened. It just does not hold any more (§26.3).
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
    """What the proposal would do, in one readable line."""
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
