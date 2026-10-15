"""Fragen ohne Ort im Hausstil — statt ``QInputDialog`` (FD-22, Z5).

``QInputDialog.getText`` und ``getItem`` bauen ein Fenster ohne Raster, mit
Qts Knöpfen *OK* und *Cancel* und einer Beschriftung, die als Doppelpunkt über
dem Feld klebt. Hier steht die Frage in der Form der Meldungen
(:mod:`app.ui.message_dialog`): der Titel als Überschrift, ein Satz, darunter
das Feld, ein Hauptknopf, der sagt, was er tut, und *Abbrechen*. Enter löst den
Hauptknopf aus, Escape bricht ab, Tab geht vom Feld zu den Knöpfen.

Eine Prüfung (``check``) hält den Dialog offen und sagt den Grund unter dem
Feld; die getippte Eingabe bleibt stehen. Eine Wahl unter Gleichwertigem ist
die Rückfrage nach Regel 21 (``dialogs.AskDialog``), mit Titel und Kennzeichen
der Frage (:func:`ask_choice`). Wo die Eingabe einen Ort hat — eine Farbe am
Farbknopf, ein Maß an seiner Karte —, steht sie dort (:mod:`app.ui.place_popup`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.core import guides
from app.i18n import tr
from app.ui.leash import weak_slot
from app.ui.message_dialog import TEXT_WIDTH, MessageDialog
from app.ui.style import set_role


class InputDialog(MessageDialog):
    """Titel, ein Satz, ein Feld, *Hauptknopf* und *Abbrechen*.

    ``check`` bekommt den Text beim Bestätigen und gibt den Grund zurück, der
    dagegen spricht, oder einen leeren Satz. Ein Grund steht unter dem Feld,
    der Dialog bleibt offen und das Feld behält, was getippt ist.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        sentence: str,
        target: str,
        accept: str,
        text: str = "",
        check: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent, title=title, headline=title, body=sentence, target=target)
        # Kein Symbol der Schwere: Eine Frage nach einem Wert ist keine Meldung.
        # Auch nicht für den Bildschirmleser — kein „Hinweis“, und der Satz steht
        # schon am Feld.
        self.symbol.hide()
        self.setAccessibleDescription("")
        self._check = check
        self.field = QLineEdit(text, self)
        self.field.setMinimumWidth(TEXT_WIDTH)
        self.field.setAccessibleName(title)
        self.field.setAccessibleDescription(sentence)
        self.problem = QLabel(self)
        self.problem.setWordWrap(True)
        self.problem.setTextFormat(Qt.TextFormat.PlainText)
        self.problem.hide()
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        # Zwischen Satz und Knöpfen, wo sonst die Einzelheiten stehen.
        layout.insertWidget(1, self.field)
        layout.insertWidget(2, self.problem)
        holder = target.partition(":")[2] or "input"
        self.accept_button = self.add_action(
            accept, f"message.button:{holder}.accept", lead=True, closes=False
        )
        self.accept_button.clicked.connect(weak_slot(self, InputDialog.submit))
        self.add_exit(tr("Abbrechen"), f"message.button:{holder}.cancel")

    def submit(self) -> None:
        """Der Hauptknopf: prüfen, dann schließen — oder den Grund unter dem Feld nennen."""
        problem = self._check(self.field.text()) if self._check is not None else ""
        if problem:
            set_role(self.problem, "warning", problem)
            self.problem.show()
            self.field.setAccessibleDescription(problem)
            self.field.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._clicked = self.accept_button
        self.accept()

    def showEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        """Der Fokus steht im Feld, der Text ist markiert — wer tippt, ersetzt ihn."""
        super().showEvent(event)
        self.field.setFocus(Qt.FocusReason.OtherFocusReason)
        self.field.selectAll()


def ask_text(
    parent: QWidget | None,
    *,
    title: str,
    sentence: str,
    target: str,
    accept: str,
    text: str = "",
    check: Callable[[str], str] | None = None,
) -> str | None:
    """Fragt nach einem Text; ``None`` heißt abgebrochen. Ersetzt ``QInputDialog.getText``."""
    dialog = InputDialog(
        parent,
        title=title,
        sentence=sentence,
        target=target,
        accept=accept,
        text=text,
        check=check,
    )
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.field.text()
    finally:
        dialog.deleteLater()


def ask_choice(
    parent: QWidget | None,
    *,
    title: str,
    question: str,
    choices: Sequence[str],
    target: str,
    icons: Sequence[QIcon] = (),
) -> int | None:
    """Welche der Zeilen gemeint ist — die Nummer, oder ``None`` nach Abbruch.

    Eine Wahl unter Gleichwertigem ist die Rückfrage nach Regel 21: Solidon
    rät nicht, welches Filament ersetzt wird oder welche Gewindereihe gemeint
    ist. Gebaut wird darum ``AskDialog`` — dieselbe Liste, derselbe Knopf, der
    die Antwort nennt, wie bei jeder Frage des Kerns —, mit dem Titel der Sache
    statt „Rückfrage“ und dem Kennzeichen im Wortschatz.
    """
    from app.ui.dialogs import AskDialog

    dialog = AskDialog(question, list(choices), parent)
    dialog.setWindowTitle(title)
    dialog.setProperty(guides.TARGET_PROPERTY, target)
    for row, icon in enumerate(icons):
        item = dialog.list.item(row)
        if item is not None:
            item.setIcon(icon)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        row = dialog.list.currentRow()
        return row if 0 <= row < len(choices) else None
    finally:
        dialog.deleteLater()
