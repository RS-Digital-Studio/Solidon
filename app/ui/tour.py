"""Die Tour durch ein Beispielprojekt (Bauplan §37.2).

Die Beispiele sind laut §37.2 auch Dokumentation — aber ein fertiges Projekt
sagt einem Neuling nicht, was er damit tun soll. Dieses Panel sagt es: es
zeigt die Schritte der Tour aus :mod:`app.core.tour`, erkennt nach jeder
Änderung am Dokument, ob der aktuelle getan ist, und schaltet dann weiter.

Zwei Grundsätze:

* **Eine Tour ist ein Angebot, keine Sperre.** „Weiter" schaltet jeden
  Schritt auch ohne Erkennung — wer nur lesen will, liest; wer hängt, hängt
  nicht fest (Regel 19 im Geiste: keine Sackgassen).
* **Zustand nie allein über Farbe** (Regel 18): erledigte Schritte tragen
  einen Haken, der aktuelle einen Pfeil und Fettschrift, kommende sind
  ausgegraut *und* ohne Zeichen.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import examples
from app.core.examples import Example
from app.core.tour import Tour
from app.core.types import Document
from app.i18n import tr
from app.ui.icons import icon
from app.ui.leash import weak_slot
from app.ui.overlay import ContentScroller, tell_the_zone
from app.ui.session import Session
from app.ui.style import NORMAL, TIGHT, make_primary, set_level


class StepLabel(QLabel):
    """Eine Schrittzeile, die umbricht oder mit Auslassung endet.

    Qt schneidet eine zu lange Zeile stumpf ab — „…Transaktionen: Bode" liest
    sich nicht wie eine Kürzung, sondern wie ein Fehler. Ein Widget, das beides
    kann, hält die Entscheidung an einer Stelle: gekürzt wird beim Zeichnen,
    also auch nach jeder Änderung der Spaltenbreite.

    Welche der beiden Formen gilt, entscheidet nicht dieses Widget, sondern
    :meth:`TourPanel._update_marks`: Der aktuelle Schritt und jeder
    aufgeklappte bricht um, die übrigen enden mit Auslassung.
    """

    clicked = Signal()
    """Ein Klick auf die Zeile; eine eingeklappte klappt damit auf (RM-553)."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full = text

    def setText(self, text: str) -> None:  # noqa: N802 — Qt-Name
        self._full = text
        self._show()

    def full_text(self) -> str:
        """Der ungekürzte Text — was der Test prüft."""
        return self._full

    def set_wrapped(self, wrapped: bool) -> None:
        self.setWordWrap(wrapped)
        self._show()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self._show()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        # Den Druck annehmen: Ein ``QLabel`` reicht ihn sonst an die Eltern
        # weiter, und das Loslassen kommt nicht sicher bei ihm an.
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Name
        """Leertaste und Eingabetaste klappen auf wie der Klick (Review U1, Fund 5)."""
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show(self) -> None:
        if self.wordWrap():
            super().setText(self._full)
            return
        super().setText(
            self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width())
        )


class _StepScroller(ContentScroller):
    """Die Schritte wünschen ihre ganze Höhe, und jeder Umbau sagt es bis zur Karte.

    Ein nackter ``QScrollArea`` merkt sich den Wunsch seines Inhalts beim
    Einsetzen, und da war die Liste leer: Die Tour-Karte stand bei 2000 x 816
    auf wenigen Zeilen, der aufgeklappte Schritt rollte neben freiem Platz
    (RM-553). Hier fragt der Rollbereich bei jedem Mal den Inhalt
    (:class:`~app.ui.overlay.ContentScroller`), und ein neu gelegter Inhalt —
    ein Schritt klappt auf, einer zu — meldet sich über
    :func:`~app.ui.overlay.tell_the_zone`, sonst wüchse die Karte erst mit dem
    nächsten fremden Anlass.
    """

    contentResized = Signal()
    """Die Schritte haben ihre neue Höhe — erst jetzt stimmt die Lage einer Zeile."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if watched is self.widget():
            if event.type() == QEvent.Type.LayoutRequest:
                tell_the_zone(self)
            elif event.type() == QEvent.Type.Resize:
                self.contentResized.emit()
        return super().eventFilter(watched, event)


class TourPanel(QWidget):
    """Führt durch ein Beispiel: erklärt, wartet, erkennt, schaltet weiter."""

    closed = Signal()
    """Die Tour wurde beendet — das Fenster nimmt den Reiter weg."""
    pointsAt = Signal(str)
    """Wovon der aktuelle Schritt spricht — „history", „parameters", „report",
    „tree", „toolbar", „tools" oder „viewport". Das Fenster lässt den Bereich
    kurz aufleuchten; einen Reiter derselben Karte rahmt es, ohne ihn nach
    vorn zu holen. Leer heißt: Der Schritt zeigt auf nichts mehr."""
    followRequested = Signal(str)
    """Das nächste Beispiel, wenn die Tour zu Ende ist und jemand weitermachen
    will — trägt seine Kennung."""

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._tour: Tour | None = None
        self._document: Document | None = None
        """Das Dokument, für das die Tour läuft. Die Sitzung feuert
        ``projectChanged`` auch beim Öffnen des nächsten Projekts — eine
        Erkennung auf einem fremden Dokument wäre ein geratener Fortschritt."""
        self._current = 0
        self._example: Example | None = None
        """Welches Beispiel läuft — für den Knopf, der auf das nächste führt."""
        self._pointed_at: str | None = None
        """Worauf zuletzt gezeigt wurde. Ein Rahmen, der bei jeder
        Neuberechnung aufblinkt, ist ein Flackern und kein Hinweis."""
        self._tab_names: dict[str, str] = {}
        """Welche Ziele Reiter derselben Karte sind, mit dem Namen am Reiter.

        Die Tour holt einen solchen Reiter nicht nach vorn, sie verschwände
        sonst unter ihm (RM-573); der Schritt sagt stattdessen, worauf zu
        klicken ist. Das Fenster kennt die Reiter und setzt sie
        (:meth:`set_tab_names`)."""
        self._already: set[int] = set()
        """Schritte, deren Erkennung schon beim Start zutraf. Sie zählen nicht
        als getan — der Nutzer hat sie nicht getan."""
        self._completed: set[int] = set()
        """Gelesene oder vom Dokument bestätigte Schritte."""
        self._skipped: set[int] = set()
        """Handlungsschritte, die der Nutzer bewusst ausgelassen hat."""
        self._unfolded: set[int] = set()
        """Eingeklappte Schritte, die der Nutzer mit einem Klick aufgeklappt hat."""
        self._in_view = 0
        """Der Schritt, den der Rollbereich nach dem Legen ins Bild holt."""
        self._rows: list[tuple[QLabel, StepLabel]] = []
        self._row_hosts: list[QWidget] = []
        """Ein Trägerwidget je Schrittzeile. Aufgeräumt wird über genau ein
        ``deleteLater`` auf dem Träger — Marker und Text sterben als seine
        Kinder mit. Die erste Version nahm die Zeilen-Layouts mit ``takeAt``
        aus dem Panel-Layout und rief zusätzlich ``deleteLater``: nach
        ``takeAt`` gehört das Layout aber dem Python-Wrapper, der es beim
        Verlassen der Schleife sofort zerstört — das nachlaufende Ereignis
        traf freigegebenen Speicher, und die Suite riss Tests später ohne
        eine Zeile Traceback ab."""
        self._marks: dict[str, QPixmap] = {}
        """Die zwei Zustandszeichen, einmal gerastert und wiederverwendet.
        ``_update_marks`` läuft bei jeder Dokumentänderung — jedes Mal einen
        QSvgRenderer anzuwerfen wäre Arbeit im Takt der Auswertung."""

        self.title = QLabel("", self)
        self.title.setWordWrap(True)
        set_level(self.title, "section")

        self.intro = QLabel("", self)
        self.intro.setWordWrap(True)

        self.progress = QLabel("", self)
        set_level(self.progress, "caption")

        steps_host = QWidget(self)
        self._steps_layout = QVBoxLayout(steps_host)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.setSpacing(NORMAL)
        self._steps_layout.addStretch(1)

        scroll = _StepScroller(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(steps_host)
        self._scroll = scroll
        # Nach dem Legen steht die Zeile erst an ihrem Platz; dann noch einmal ins Bild.
        scroll.contentResized.connect(self._show_row)

        self.closing = QLabel("", self)
        self.closing.setWordWrap(True)
        self.closing.setVisible(False)

        self.next_button = QPushButton(tr("Weiter"), self)
        # Als Beschreibung, nicht als Tooltip (RM-553): Über dem Knopf lief die
        # Sprechblase als eine Zeile quer über Ansicht und Kartentext, genau dort,
        # wohin der Zeiger zum Weiterlesen ohnehin geht.
        self.next_button.setAccessibleDescription(
            tr("Schaltet zum nächsten Schritt — auch, wenn der aktuelle nicht gemacht wurde.")
        )
        self.next_button.clicked.connect(self.advance)
        make_primary(self.next_button)
        # Am Ende der Tour steht eine Frage, die vorher niemand beantwortet
        # hat: und jetzt? Der Abschlusstext sagte, was man gelernt hat, und
        # führte nirgendwohin — die übrigen sechs Beispiele fand nur, wer den
        # Startbildschirm wiederzufinden wusste.
        self.follow_button = QPushButton("", self)
        self.follow_button.setVisible(False)
        self.follow_button.clicked.connect(self._follow)
        make_primary(self.follow_button)
        self.stop_button = QPushButton(tr("Tour beenden"), self)
        self.stop_button.clicked.connect(self.stop)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.follow_button)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.title)
        layout.addWidget(self.intro)
        layout.addWidget(self.progress)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(self.closing)
        layout.addLayout(buttons)

        # Jede Transaktion, jedes Undo und jede geänderte Zahl feuert dieses
        # Signal — genau die Momente, in denen ein Schritt getan sein kann.
        session.projectChanged.connect(self._check)

    # --- Zustand ----------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._tour is not None

    @property
    def current_index(self) -> int:
        """Der aktuelle Schritt; gleich der Schrittzahl, wenn alles durch ist."""
        return self._current

    # --- Steuerung --------------------------------------------------------------

    def start(self, example: Example, tour: Tour) -> None:
        """Baut die Schritte auf und beginnt vorn."""
        self._clear_rows()
        self._tour = tour
        self._pointed_at = None
        self._document = self._session.project.document
        self._example = example
        self._current = 0
        self._completed.clear()
        self._skipped.clear()
        self._unfolded.clear()
        # Was beim Öffnen schon zutrifft, hat der Nutzer nicht getan. Ein
        # Schritt, dessen Erkennung von Anfang an wahr ist — „im Prüfbericht
        # steht, was die Reparatur gefunden hat" —, würde die Tour sonst
        # überspringen, bevor sie begonnen hat.
        self._already = {
            index
            for index, step in enumerate(tour.steps)
            if step.done is not None
            and step.done(self._session.project.document, self._session.history)
        }

        self.title.setText(str(example.title))
        self.intro.setText(str(tour.intro))
        self.closing.setText(str(tour.closing))
        self.closing.setVisible(False)
        self.next_button.setVisible(True)

        for index, step in enumerate(tour.steps):
            host = QFrame(self)
            host.setObjectName("tourStepRow")
            marker = QLabel("", host)
            marker.setFixedWidth(self.fontMetrics().height() + 4)
            marker.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            line = f"{index + 1}. {step.text}"
            tab = self._tab_names.get(step.shows or "")
            if tab:
                line = tr(
                    "{step} Klicken Sie dazu oben auf den Reiter „{tab}“.", step=line, tab=tab
                )
            text = StepLabel(line, host)
            text.setObjectName("tourStepText")
            text.setWordWrap(True)
            text.clicked.connect(weak_slot(self, TourPanel._toggle, index))
            row = QHBoxLayout(host)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(TIGHT)
            row.addWidget(marker)
            row.addWidget(text, stretch=1)
            self._steps_layout.insertWidget(self._steps_layout.count() - 1, host)
            self._row_hosts.append(host)
            self._rows.append((marker, text))

        self._update_marks()
        # Falls der erste Schritt schon beim Öffnen als getan gälte, wäre die
        # Tour gegen das Beispiel gedriftet — die Prüfung läuft trotzdem, damit
        # sie nie stumm hängen bleibt.
        self._check()

    def advance(self) -> None:
        """Liest weiter oder lässt einen unerledigten Handlungsschritt aus."""
        if self._tour is None or self._current >= len(self._tour.steps):
            return
        step = self._tour.steps[self._current]
        if step.done is None or step.done(self._session.project.document, self._session.history):
            self._completed.add(self._current)
        else:
            self._skipped.add(self._current)
        self._current += 1
        self._update_marks()
        self._check()

    def stop(self) -> None:
        """Beendet die Tour auf Wunsch des Nutzers."""
        self.reset()
        self.closed.emit()

    def reset(self) -> None:
        """Vergisst die Tour, ohne ein Signal — für den Projektwechsel."""
        self._tour = None
        self._document = None
        # Vergessen, worauf gezeigt wurde: Die nächste Tour beginnt fast immer
        # beim Verlauf, und ein gemerktes „history" aus der abgebrochenen
        # hätte ihren ersten Hinweis verschluckt.
        self._pointed_at = None
        self._completed.clear()
        self._skipped.clear()
        self._unfolded.clear()
        self._clear_rows()

    # --- Erkennung --------------------------------------------------------------

    def _check(self) -> None:
        """Erkennt getane Schritte und schaltet weiter.

        Geprüft wird die **ganze** Liste, nicht nur der aktuelle Schritt. Fünf
        der sieben Touren beginnen mit einer Beobachtung — „Sehen Sie links in
        den Verlauf", „Links unter Parameter stehen breite, tiefe und stärke" —,
        und die trägt kein ``done``, weil Hinsehen nichts am Dokument ändert.
        Vorher hielt genau das die Erkennung an: wer den Durchmesser änderte,
        das Teil folgen sah und auf die Tour blickte, stand weiterhin auf
        Schritt 1 von 5. Die Handlung war getan, die Tour sagte es nur nicht.

        Der Stand rückt deshalb hinter den letzten erkannten Schritt. Wer die
        Handlung eines späteren vorweggenommen hat, muss sie nicht noch einmal
        tun, und ein Schritt, den man nur liest, hält niemanden auf. Rückwärts
        geht es nie: ein Undo nimmt die Geometrie zurück, nicht das Gelesene.
        """
        tour = self._tour
        if tour is None or self._session.project.document is not self._document:
            return

        document = self._session.project.document
        history = self._session.history

        def done(index: int) -> bool:
            step = tour.steps[index]
            return step.done is not None and bool(step.done(document, history))

        # Ein ausgelassener Schritt kann später doch noch getan werden. Das
        # passiert gerade Anfängern leicht: erst weiterlesen, dann verstehen,
        # was gemeint war, und die Handlung nachholen. Da ``_current`` schon
        # dahinter steht, würde die Schleife unten ihn nie wieder ansehen und
        # die Tour trotz erfüllter Prüfung weiter als „Übersprungen“ zeigen.
        # Erledigt bleibt danach erledigt — ein späteres Undo nimmt wie bei den
        # übrigen Schritten die Geometrie zurück, nicht das Gelernte.
        refreshed = False
        for index in tuple(self._skipped):
            if done(index):
                self._skipped.discard(index)
                self._completed.add(index)
                refreshed = True

        advanced = False
        while self._current < len(tour.steps):
            if tour.steps[self._current].done is not None:
                if not done(self._current):
                    break
                self._completed.add(self._current)
                self._skipped.discard(self._current)
                self._current += 1
                advanced = True
                continue
            # Ein Leseschritt hält nur auf, solange nichts dahinter geschehen
            # ist. Wurde die Handlung eines späteren Schritts erkannt, ist auch
            # dieser vorbei — sonst stünde die Tour auf „Schritt 1 von 5",
            # während der Nutzer längst Schritt 2 getan hat.
            ahead = range(self._current + 1, len(tour.steps))
            if not any(index not in self._already and done(index) for index in ahead):
                break
            self._completed.add(self._current)
            self._current += 1
            advanced = True
        if advanced or refreshed:
            self._update_marks()

    # --- Darstellung ------------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt-Name
        """Ein Themenwechsel macht jedes gespeicherte Pixmap falsch.

        Die Häkchen und der Pfeil liegen als Bild vor, nicht als Symbol — ein
        QLabel kann nur Pixmaps. Wer eines zwischenspeichert, muss darauf
        hören, wann seine Farbe nicht mehr stimmt; sonst standen sie nach dem
        Wechsel hell auf hell da und die Tour hatte keine Zeichen mehr.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._marks.clear()
            self._update_marks()

    def _mark(self, name: str) -> QPixmap:
        pixmap = self._marks.get(name)
        if pixmap is None:
            size = self.fontMetrics().height()
            pixmap = icon(name, self).pixmap(size, size)
            self._marks[name] = pixmap
        return pixmap

    def _update_marks(self) -> None:
        """Der aktuelle Schritt steht da, die übrigen sind eine Zeile.

        Vorher standen alle fünf in voller Länge untereinander, der aktuelle
        nur fett — eine Liste, keine Führung. Wer bei „Schritt 1 / 5" anfängt,
        liest fünf Absätze und weiß nicht, welcher gerade dran ist.

        Erledigtes und Kommendes bleibt sichtbar, nur eben einzeilig: eine
        Tour, die verbirgt, was noch kommt, macht aus Schritten
        Überraschungen.
        """
        tour = self._tour
        if tour is None:
            return
        for index, (marker, text) in enumerate(self._rows):
            body = QFont(text.font())
            body.setBold(index == self._current)
            text.setFont(body)
            # Kommende Schritte sind grau über das Stilblatt (``tourState``),
            # nicht gesperrt: Eine gesperrte Zeile nähme weder Klick noch
            # Tastatur an und ließe sich nie aufklappen (Review U1, Fund 5).
            text.setEnabled(True)
            # **Nur der Auftrag, der jetzt zählt, steht vollständig da.** Alle
            # kommenden Absätze zugleich zu zeigen machte aus der Führung eine
            # graue Textwand. Eine Zeile verrät weiterhin, was folgt; beim
            # Erreichen klappt der Schritt vollständig auf, vorher und danach
            # mit einem Klick auf die Zeile. **Kein Tooltip dafür** (RM-553):
            # Die Sprechblase lief als eine lange Zeile quer über die Ansicht
            # und verdeckte den Text der Karte. Die Hilfstechnik liest den
            # ganzen Satz aus der Beschreibung.
            is_current = index == self._current
            unfolded = is_current or index in self._unfolded
            text.set_wrapped(unfolded)
            text.setToolTip("")
            text.setAccessibleDescription("" if unfolded else text.full_text())
            text.setCursor(
                Qt.CursorShape.ArrowCursor if is_current else Qt.CursorShape.PointingHandCursor
            )
            # Mit der Tabulatortaste erreichbar ist, was ein Klick aufklappt.
            text.setFocusPolicy(Qt.FocusPolicy.NoFocus if is_current else Qt.FocusPolicy.TabFocus)
            host = self._row_hosts[index]
            if index in self._skipped:
                marker.clear()
                marker.setText(tr("—"))
                marker.setAccessibleName(tr("Übersprungen"))
                state = "skipped"
            elif index in self._completed:
                marker.setText("")
                marker.setPixmap(self._mark("done"))
                marker.setAccessibleName(tr("Erledigt"))
                state = "completed"
            elif index == self._current:
                marker.setText("")
                marker.setPixmap(self._mark("step"))
                marker.setAccessibleName(tr("Schritt"))
                state = "current"
            else:
                marker.clear()
                marker.setAccessibleName("")
                state = "upcoming"
            host.setProperty("tourState", state)
            style = host.style()
            if style is not None:
                # Die Schrift folgt dem Zustand der Zeile — die Zeile selbst neu
                # polieren genügt dafür nicht.
                for widget in (host, text):
                    style.unpolish(widget)
                    style.polish(widget)
        self._point_at_current()
        # Rollt die Liste, steht der aktuelle Schritt im Bild — erst nach dem
        # Legen, vorher kennt der Rollbereich seine neue Höhe nicht.
        self._in_view = self._current
        QTimer.singleShot(0, self, self._show_row)

        finished = self._current >= len(tour.steps)
        self.closing.setVisible(finished)
        self.next_button.setVisible(not finished)
        if not finished:
            current_step = tour.steps[self._current]
            exercise = current_step.done is not None
            self.next_button.setText(tr("Schritt überspringen") if exercise else tr("Weiter"))
            # Bei einer Übung ist die Handlung im Fenster dran, nicht das
            # Überspringen: ein normaler Knopf ohne Akzent. Beim Leseschritt
            # ist *Weiter* der eine Weg und bleibt Hauptknopf (RM-512).
            make_primary(self.next_button, leading=not exercise)
        following = self._next_example() if finished else None
        self.follow_button.setVisible(following is not None)
        if following is not None:
            self.follow_button.setText(tr("Weiter mit: {title}", title=following.title))
        self.progress.setText(
            tr("Tour abgeschlossen.")
            if finished
            else f"{tr('Schritt')} {self._current + 1} / {len(tour.steps)}"
        )

    def _toggle(self, index: int) -> None:
        """Klappt einen anderen als den aktuellen Schritt auf oder wieder zu."""
        if self._tour is None or index == self._current:
            return
        self._unfolded ^= {index}
        self._update_marks()
        self._in_view = index

    def _show_row(self) -> None:
        """Den Schritt ins Bild holen — einen zu hohen mit seinem Anfang.

        ``ensureWidgetVisible`` mittet ein Widget, das höher ist als der
        Ausschnitt; Nummer und erste Zeilen standen dann über dem Rand
        (Review U1, Fund 4).
        """
        if not 0 <= self._in_view < len(self._row_hosts):
            return
        host = self._row_hosts[self._in_view]
        viewport = self._scroll.viewport()
        if viewport is not None and host.height() > viewport.height():
            self._scroll.verticalScrollBar().setValue(host.y())
        else:
            self._scroll.ensureWidgetVisible(host, 0, 0)

    def _next_example(self) -> Example | None:
        """Das Beispiel nach diesem, in der Reihenfolge des Startbildschirms.

        Nach dem letzten kommt keines — dann steht dort nur der Abschluss, und
        das ist ehrlicher als ein Knopf, der zurück an den Anfang führt.
        """
        if self._example is None:
            return None
        ids = [entry.id for entry in examples.EXAMPLES]
        if self._example.id not in ids:
            return None
        position = ids.index(self._example.id) + 1
        return examples.EXAMPLES[position] if position < len(ids) else None

    def _follow(self) -> None:
        following = self._next_example()
        if following is not None:
            self.followRequested.emit(following.id)

    def _point_at_current(self) -> None:
        """Sagt dem Fenster, wovon der aktuelle Schritt spricht.

        „Sehen Sie links in den Verlauf" lässt vier Bereiche offen, und wer den
        Satz zum ersten Mal liest, sucht. Gemeldet wird nur der Name — wo der
        Bereich liegt und wie er aufleuchtet, weiß das Fenster.

        Gemeldet wird auch nur bei einem Wechsel: ein Rahmen, der bei jeder
        Neuberechnung aufblinkt, ist ein Flackern und kein Hinweis.
        """
        tour = self._tour
        target = (
            None
            if tour is None or self._current >= len(tour.steps)
            else tour.steps[self._current].shows
        )
        if target == self._pointed_at:
            return
        before, self._pointed_at = self._pointed_at, target
        if target is not None:
            self.pointsAt.emit(target)
        elif before is not None:
            # Ein leeres Ziel: Das Fenster nimmt den Hinweis am Reiter ab (RM-573).
            self.pointsAt.emit("")

    def set_tab_names(self, names: Mapping[str, str]) -> None:
        """Die Ziele, die Reiter derselben Karte sind, und ihr Name — vor :meth:`start`."""
        self._tab_names = dict(names)

    def _clear_rows(self) -> None:
        # Das Panel-Layout vergisst ein zerstörtes Widget von selbst — mehr
        # als das eine ``deleteLater`` je Zeile wäre schon wieder ein zweiter
        # Besitzer.
        # Aus dem Layout aber sofort: Bis zum Löschen läge die alte Liste sonst
        # noch einen Durchlauf über der neuen und zählte zu ihrer Höhe.
        for host in self._row_hosts:
            host.hide()
            self._steps_layout.removeWidget(host)
            host.deleteLater()
        self._row_hosts.clear()
        self._rows.clear()
