"""Der Chat (Bauplan §26.3, §2.5).

Die rechte Seite des Fensters, neben dem Prüfbericht. Worauf es hier ankommt,
sind nicht die Sprechblasen, sondern die Kopplung: jeder Beitrag zeigt, welche
Transaktion er erzeugt hat, und ein Beitrag, dessen Transaktion zurückgenommen
wurde, wird ausgegraut statt gelöscht — er ist passiert, er gilt nur nicht
mehr.

Ein Vorschlag aus eindeutig umkehrbaren Operationen wird ohne Nachfrage
übernommen (§26.5, Regel 19) — die Leiste wird dann zur Übernommen-Leiste
mit dem einen Knopf zurück. Alles andere wartet: der Viewport zeigt, was
sich ändern würde (§18.7), und zwei Knöpfe entscheiden. Ohne Schlüssel sagt
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
from app.i18n import TranslatableText, _, tr
from app.ui.labels import localised
from app.ui.leash import weak_slot
from app.ui.style import NORMAL, set_level

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

#: Was im leeren Gespräch als Beispiel dasteht — anklickbar, nicht abschickbar.
#:
#: Der Chat ist das Versprechen, mit dem die Anwendung antritt, und im leeren
#: Zustand stand dort eine schwarze Fläche mit „Was soll geändert werden?"
#: darunter. Der Erststart-Dialog wirbt für ihn, das Handbuch hat ein Kapitel,
#: die Website zeigt ihn — und die Stelle selbst sagte nichts darüber, was man
#: hier eigentlich schreiben kann.
#:
#: Vier Sätze, je einer aus einer anderen Ecke: etwas Neues, ein Baustein, eine
#: Änderung am Vorhandenen, die Druckvorbereitung. Sie sind absichtlich so
#: geschrieben, wie jemand wirklich tippt — mit Maßen, nicht in Befehlsform.
#:
#: Ein Klick setzt den Satz ins Eingabefeld und schickt ihn **nicht** ab: Was
#: der Agent tut, kostet Zeit und womöglich Geld, und ein Beispiel ist ein
#: Anfang zum Weiterschreiben, kein Knopf.
STARTERS: tuple[TranslatableText, ...] = (
    _("Halter, 60 × 40 mm, zwei M4-Löcher"),
    _("Setz eine M3-Mutternfalle in die Unterseite"),
    _("Mach die Wandstärke 3 mm"),
    _("Teile das Teil, damit es auf das Bett passt"),
)


class ChatPanel(QWidget):
    """Gespräch, Eingabezeile, und die zwei Knöpfe, die ein Vorschlag braucht."""

    requestSent = Signal(str)
    accepted = Signal()
    discarded = Signal()
    undoRequested = Signal()
    """Der eine Knopf der Übernommen-Leiste (§26.5): ein automatisch
    übernommener Vorschlag braucht keine Entscheidung mehr, nur den Weg
    zurück."""
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
        self.turns.setAccessibleName(tr("Gesprächsverlauf"))
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
        # **Wörtlich derselbe Text wie im Menü** (`Bearbeiten → Chat
        # einrichten …`) und derselbe Dialog dahinter. Vorher hieß er anders
        # und führte woandershin: in die „Zusätzlichen Programme", wo man ein
        # lokales Modell installiert — aber nicht seinen Schlüssel einträgt.
        # Wer keinen Zugang hatte, bekam damit den einen von zwei Wegen aus
        # §27 angeboten, und den anderen fand er von dort aus nicht.
        self.setup = QPushButton(tr("Chat einrichten …"), self)
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
        self.input.setAccessibleName(tr("Nachricht an den Chat"))
        self.input.setTabChangesFocus(True)
        self.input.setFixedHeight(self.input.fontMetrics().lineSpacing() * 3 + 12)
        self.input.installEventFilter(self)
        self.send = QPushButton(tr("Senden"), self)
        self.send.clicked.connect(self._send)

        entry_row = QHBoxLayout()
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.addWidget(self.input, stretch=1)
        entry_row.addWidget(self.send)

        # Die Beispielanfragen für das leere Gespräch — siehe :data:`STARTERS`.
        self.starters = QWidget(self)
        starters_layout = QVBoxLayout(self.starters)
        starters_layout.setContentsMargins(0, 0, 0, 0)
        starters_layout.setSpacing(0)
        starters_lead = QLabel(tr("Zum Beispiel:"), self.starters)
        set_level(starters_lead, "caption")
        starters_layout.addWidget(starters_lead)
        for starter in STARTERS:
            button = QPushButton(str(starter), self.starters)
            button.setFlat(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            # Linksbündig wie ein Vorschlag, nicht mittig wie ein Knopf: was
            # hier steht, ist ein Satz zum Weiterschreiben.
            button.setStyleSheet("text-align: left;")
            # Der Ring aus der Schleife: Das Lambda hielte ``self``, der Knopf
            # hielte das Lambda, und ``self`` hält den Knopf. Zehn losgelassene
            # ``ChatPanel`` überlebten damit alle zehn.
            button.clicked.connect(weak_slot(self, ChatPanel._take_starter, str(starter)))
            starters_layout.addWidget(button)

        self.summary = QLabel("", self)
        self.summary.setWordWrap(True)

        # Konzept Agent-Vertiefung 4.2: der Vorschlag zeigt seine Kosten. Der
        # Zug zählt Schritte und Token längst — sie nicht zu zeigen machte den
        # harten Deckel aus §26.5 unsichtbar, und einen Abbruch an der Grenze
        # gab es nur als zwei Worte.
        self.cost_line = QLabel("", self)
        self.cost_line.setWordWrap(True)
        # Gedämpft über die Stilstufe, nicht von Hand: ``caption`` setzt
        # Größe und die themenabhängige Farbe — eine feste Farbe ignorierte
        # das Thema und unterlief auf hellem Grund den Kontrast. Gedämpft ist
        # Stil, nicht Bedeutung (Regel 18): die Auskunft steht im Text.
        set_level(self.cost_line, "caption")

        # Die Rückfragen samt Antworten sind Teil der Begründung des
        # Vorschlags — aufklappbar, nicht immer offen: wer sie gestellt
        # bekam, kennt sie schon.
        self.questions_toggle = QPushButton("", self)
        self.questions_toggle.setCheckable(True)
        self.questions_toggle.setFlat(True)
        self.questions_toggle.setVisible(False)
        self.questions_view = QLabel("", self)
        self.questions_view.setWordWrap(True)
        self.questions_view.setVisible(False)
        self.questions_toggle.toggled.connect(self.questions_view.setVisible)

        self.accept_button = QPushButton(tr("Übernehmen"), self)
        self.accept_button.clicked.connect(self.accepted)
        self.discard_button = QPushButton(tr("Verwerfen"), self)
        self.discard_button.clicked.connect(self.discarded)
        self.undo_button = QPushButton(tr("Rückgängig"), self)
        self.undo_button.clicked.connect(self.undoRequested)
        self.undo_button.setVisible(False)

        decision_row = QHBoxLayout()
        decision_row.setContentsMargins(0, 0, 0, 0)
        decision_row.addWidget(self.accept_button)
        decision_row.addWidget(self.discard_button)
        decision_row.addWidget(self.undo_button)
        decision_row.addStretch(1)

        self.decision = QWidget(self)
        decision_layout = QVBoxLayout(self.decision)
        decision_layout.setContentsMargins(0, 0, 0, 0)
        decision_layout.addWidget(self.summary)
        decision_layout.addWidget(self.cost_line)
        decision_layout.addWidget(self.questions_toggle)
        decision_layout.addWidget(self.questions_view)
        decision_layout.addLayout(decision_row)
        self.decision.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.addWidget(self.hint)
        layout.addWidget(self.notice)
        layout.addWidget(self.setup)
        layout.addWidget(self.unlock)
        layout.addWidget(self.turns, stretch=1)
        layout.addWidget(self.starters)
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
        # Die Beispiele gelten dem leeren Gespräch. Sobald etwas darin steht,
        # weiß der Nutzer, wofür der Chat da ist.
        self.starters.setVisible(not document.chat)

    def show_applied(self, preview: Any, transaction_id: str) -> None:
        """Die Übernommen-Leiste (§26.5): der Vorschlag ist schon angewandt,
        es bleibt der Weg zurück.

        Regel 19 rückwärts gelesen: was rücknehmbar ist, braucht keine
        Bestätigung — aber es braucht die Auskunft, dass es passiert ist,
        und einen Knopf, der es ungeschehen macht.
        """
        self.show_proposal(preview)
        marker = f" ({transaction_id})" if transaction_id else ""
        self.summary.setText(
            f"{tr('Übernommen')}{marker}: {describe(preview)} — "
            + tr("Rückgängig nimmt alles zurück.")
        )
        self.accept_button.setVisible(False)
        self.discard_button.setVisible(False)
        self.undo_button.setVisible(True)

    def show_proposal(self, preview: Any | None) -> None:
        """Bietet die Entscheidung an, mit dem, was sich änderte, in
        Zahlen (§18.7).
        """
        self.accept_button.setVisible(True)
        self.discard_button.setVisible(True)
        self.undo_button.setVisible(False)
        if preview is None:
            self.decision.setVisible(False)
            self.summary.setText("")
            self.cost_line.setText("")
            self.questions_toggle.setVisible(False)
            self.questions_view.setVisible(False)
            return
        proposal = preview.proposal
        self.summary.setText(describe(preview))
        self.cost_line.setText(costs(proposal))
        questions = list(proposal.questions)
        self.questions_toggle.setChecked(False)
        self.questions_toggle.setText(f"{tr('Rückfragen')} ({len(questions)}) …")
        self.questions_toggle.setVisible(bool(questions))
        self.questions_view.setVisible(False)
        self.questions_view.setText(
            "\n".join(
                f"? {entry.text}\n→ {entry.answer or tr('ohne Antwort')}" for entry in questions
            )
        )
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

    def _take_starter(self, text: str) -> None:
        """Ein Beispiel ins Eingabefeld übernehmen — und dort stehen lassen.

        Nicht abschicken: Was der Agent tut, kostet Zeit und womöglich Geld,
        und ein Beispiel ist ein Anfang zum Weiterschreiben. Der Zeiger steht
        danach am Ende des Satzes, wo weitergetippt wird.
        """
        self.input.setPlainText(text)
        self.input.setFocus()
        cursor = self.input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input.setTextCursor(cursor)

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
    if proposal.print_target:
        printer, material = proposal.print_target
        parts.append(f"{tr('Druckziel')} {printer} / {material}")
    if proposal.undo_of:
        parts.append(f"{tr('Rücknahme')} {proposal.undo_of}")

    difference = getattr(preview, "difference", None)
    if difference is not None and difference.changed:
        parts.append(
            localised(
                f"+{difference.added_volume / 1000.0:.2f} cm³ / "
                f"-{difference.removed_volume / 1000.0:.2f} cm³"
            )
        )
    return " · ".join(parts) or tr("Keine Änderung")


def costs(proposal: Any) -> str:
    """Schritte, Token und — ausgeschrieben — eine erreichte Grenze (§26.5).

    „Grenze erreicht" stand als zwei Worte in der Zusammenfassung; was für
    eine Grenze und was das für den Vorschlag heißt, stand nirgends. Jetzt
    steht es hier, und die Kosten daneben machen den Deckel sichtbar, bevor
    er greift.
    """
    # Eigene Schlüssel statt des Worts „Schritt": das teilte sich seinen
    # Katalogeintrag mit dem Satzanfang der Statuszeile („Step 3/8"), und
    # eine der beiden Stellen las zwangsläufig die falsche Schreibung.
    steps = tr("1 Schritt") if proposal.steps == 1 else tr("{n} Schritte").format(n=proposal.steps)
    parts = [steps]
    if proposal.input_tokens or proposal.output_tokens:
        parts.append(f"{proposal.input_tokens} → {proposal.output_tokens} {tr('Token')}")
    text = " · ".join(parts)
    if proposal.stopped == "steps":
        text += "\n" + tr(
            "Nach {n} Schritten angehalten — der Vorschlag zeigt den Stand bis hierhin."
        ).format(n=proposal.steps)
    elif proposal.stopped == "tokens":
        text += "\n" + tr(
            "Das Tokenbudget ist erreicht — der Vorschlag zeigt den Stand bis hierhin."
        )
    return text
