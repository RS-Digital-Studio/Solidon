"""Meldungen im Hausstil — statt eines rohen ``QMessageBox`` (FD-21, Z5).

Ein ``QMessageBox`` zeichnet das Warndreieck des Betriebssystems, ordnet seine
Knöpfe nach Qts Regeln und hält sich an kein Raster: Mitten im Fenster stand
damit ein fremdes Programm, ausgerechnet dort, wo etwas nicht ging. Hier
steht die Meldung in der Form der übrigen Dialoge — Symbol aus dem eigenen
Satz in der Farbe der Schwere, Titel, Ursache, Handlungen als Knöpfe mit
genau einem Hauptknopf (Regel 17, 18), und was ein ``QMessageBox`` schon
konnte, kann sie auch: Escape schließt, Enter löst den Hauptknopf aus, Tab
geht die Knöpfe ab, Strg+C kopiert den ganzen Text.

Fragen (Regel 19, Speicherfrage) bleiben, was sie sind; dieses Modul ist für
Meldungen. Welche Fenster es zeigen, steht im Wortschatz unter ihrem
Kennzeichen (``message:<sache>``, ``window_names``).
"""

from __future__ import annotations

from typing import Final, Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import guides
from app.i18n import tr
from app.ui.icons import svg_pixmap, svg_source
from app.ui.leash import weak_slot
from app.ui.palette import text_colour
from app.ui.style import (
    NORMAL,
    ROOMY,
    SPACE,
    TIGHT,
    WIDE,
    make_primary,
    no_primary,
    set_level,
)
from app.ui.window_names import name_button

MessageKind = Literal["error", "warning", "info"]

#: Wie groß das Symbol der Schwere steht, in logischen Punkten: so hoch wie
#: Überschrift und erste Zeile zusammen, kleiner als das Dreieck des Systems.
SYMBOL_SIZE: Final = 32

#: Wie breit der Text mindestens läuft — ein Satz in einer Zeile von 20
#: Zeichen liest sich wie eine Liste.
TEXT_WIDTH: Final = 360

#: Wie viele Zeilen der Einzelheiten ohne Rollen dastehen.
DETAIL_LINES: Final = 14

#: Der Name des Symbols je Schwere — das Wort ist die zweite Kodierung neben
#: Form und Farbe (Regel 18).
_KIND_WORDS: Final[dict[str, str]] = {
    "error": "Fehler",
    "warning": "Warnung",
    "info": "Hinweis",
}


class MessageDialog(QDialog):
    """Titel, Ursache, Angaben und Handlungen — eine Meldung, die nach Solidon aussieht.

    ``headline`` ist die erste Zeile (was nicht ging), ``body`` die Sätze
    darunter (warum, was jetzt geht), ``details`` ein längerer Text zum
    Mitnehmen (Protokoll, Werte), der lesbar und kopierbar darunter steht.
    Knöpfe kommen über :meth:`add_action` und :meth:`add_exit`; welcher
    geklickt wurde, sagt :meth:`clicked_button` nach ``exec``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        headline: str,
        body: str = "",
        details: str = "",
        kind: MessageKind = "info",
        target: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        if target:
            self.setProperty(guides.TARGET_PROPERTY, target)
        self._clicked: QPushButton | None = None
        self._buttons: list[QPushButton] = []

        self.symbol = QLabel(self)
        background = self.palette().window().color().name()
        colour = text_colour(kind, background)
        self.symbol.setPixmap(svg_pixmap(svg_source(f"severity-{kind}", colour), SYMBOL_SIZE))
        self.symbol.setFixedSize(SYMBOL_SIZE, SYMBOL_SIZE)
        self.symbol.setAccessibleName(tr(_KIND_WORDS[kind]))

        # Text, den der Kunde liest, kommt teils aus seinen Dateien (Namen von
        # Schritten und Körpern, §32): nie als Auszeichnung gelesen.
        self.headline = QLabel(headline, self)
        self.headline.setTextFormat(Qt.TextFormat.PlainText)
        self.headline.setWordWrap(True)
        self.headline.setMinimumWidth(TEXT_WIDTH)
        set_level(self.headline, "section")
        self.body = QLabel(body, self)
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setWordWrap(True)
        self.body.setVisible(bool(body))
        for label in (self.headline, self.body):
            # Markieren mit der Maus, ohne den Tab-Weg über die Knöpfe zu
            # verlängern — Strg+C kopiert sonst alles (:meth:`copy_text`).
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setPlainText(details)
        self.details.setVisible(bool(details))
        # So hoch wie sein Text, bis :data:`DETAIL_LINES` Zeilen — zwei Werte
        # stehen nicht in einem Kasten für zwölf, ein Protokoll rollt.
        lines = min(max(details.count("\n") + 1, 2), DETAIL_LINES)
        frame = self.details.frameWidth() * 2 + int(self.details.document().documentMargin() * 2)
        fitted = self.details.fontMetrics().lineSpacing() * lines + frame + NORMAL
        self.details.setMinimumHeight(fitted)
        if lines < DETAIL_LINES:
            self.details.setMaximumHeight(fitted)
        self.details.setAccessibleName(tr("Einzelheiten"))

        words = QVBoxLayout()
        words.setContentsMargins(0, 0, 0, 0)
        words.setSpacing(TIGHT)
        words.addWidget(self.headline)
        words.addWidget(self.body)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(ROOMY)
        head.addWidget(self.symbol, 0, Qt.AlignmentFlag.AlignTop)
        head.addLayout(words, 1)

        self.button_box = QDialogButtonBox(self)
        button_layout = self.button_box.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addLayout(head)
        layout.addWidget(self.details, 1)
        layout.addWidget(self.button_box)

        copy = QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), self)
        copy.activated.connect(weak_slot(self, MessageDialog.copy_text))

    def add_action(
        self, label: str, name: str, *, lead: bool = False, closes: bool = True
    ) -> QPushButton:
        """Eine Handlung als Knopf; ``lead`` macht ihn zum Hauptknopf (``make_primary``).

        Mit ``closes=False`` bleibt das Fenster offen (*Kopieren*); was der
        Knopf tut, verbindet der Aufrufer.
        """
        button = QPushButton(label, self)
        role = (
            QDialogButtonBox.ButtonRole.AcceptRole
            if lead
            else QDialogButtonBox.ButtonRole.ActionRole
        )
        self.button_box.addButton(button, role)
        name_button(button, name)
        if lead:
            make_primary(button)
        else:
            button.setAutoDefault(False)
        if closes:
            self._wire(button, accepted=True)
        else:
            self._buttons.append(button)
        return button

    def add_exit(self, label: str, name: str) -> QPushButton:
        """Der Ausgang: nie Hauptknopf, Escape nimmt ihn."""
        button = QPushButton(label, self)
        self.button_box.addButton(button, QDialogButtonBox.ButtonRole.RejectRole)
        name_button(button, name)
        button.setAutoDefault(False)
        self._wire(button, accepted=False)
        return button

    def _wire(self, button: QPushButton, *, accepted: bool) -> None:
        self._buttons.append(button)
        button.clicked.connect(weak_slot(self, MessageDialog._chosen, button, accepted))

    def _chosen(self, button: QPushButton, accepted: bool) -> None:
        self._clicked = button
        self.done(QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected)

    def buttons(self) -> list[QPushButton]:
        """Die Knöpfe in der Reihenfolge, in der sie dazukamen."""
        return list(self._buttons)

    def clicked_button(self) -> QPushButton | None:
        """Welcher Knopf das Fenster schloss — ``None`` nach Escape oder Schließen."""
        return self._clicked

    def text(self) -> str:
        """Der ganze Text, wie Strg+C ihn kopiert: Titel, Meldung, Einzelheiten."""
        parts = [self.windowTitle(), self.headline.text()]
        if self.body.text():
            parts.append(self.body.text())
        if self.details.toPlainText():
            parts.append(self.details.toPlainText())
        return "\n\n".join(parts)

    def copy_text(self) -> None:
        """Legt den ganzen Text in die Zwischenablage — was ein ``QMessageBox`` auch tat."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.text())

    def showEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        """Ohne Handlung trägt kein Knopf den Akzent; der Fokus steht auf dem ersten."""
        if not any(button.isDefault() for button in self._buttons):
            no_primary(self)
        super().showEvent(event)  # type: ignore[arg-type]
        lead = next((button for button in self._buttons if button.isDefault()), None)
        first = lead or (self._buttons[0] if self._buttons else None)
        if first is not None:
            first.setFocus(Qt.FocusReason.OtherFocusReason)


def inform(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    target: str,
    kind: MessageKind = "info",
) -> None:
    """Ein Hinweis mit einem Knopf *Schließen* — der Ersatz für ``QMessageBox.information``."""
    dialog = MessageDialog(parent, title=title, headline=title, body=text, kind=kind, target=target)
    holder = target.partition(":")[2] or "message"
    dialog.add_exit(tr("Schließen"), f"message.button:{holder}.close")
    dialog.exec()
