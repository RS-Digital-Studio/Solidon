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

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
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
from app.ui.session import Session
from app.ui.style import NORMAL, TIGHT


class StepLabel(QLabel):
    """Eine Schrittzeile, die umbricht oder mit Auslassung endet.

    Qt schneidet eine zu lange Zeile stumpf ab — „…Transaktionen: Bode" liest
    sich nicht wie eine Kürzung, sondern wie ein Fehler. Ein Widget, das beides
    kann, hält die Entscheidung an einer Stelle: gekürzt wird beim Zeichnen,
    also auch nach jeder Änderung der Spaltenbreite.

    Welche der beiden Formen gilt, entscheidet nicht dieses Widget, sondern
    :meth:`TourPanel._update_marks`. Dort stehen heute alle Schritte auf
    Umbruch — die Kürzung machte vier von fünf unlesbar, während unter ihnen
    Platz frei war. Sie bleibt, weil eine schmale Spalte sie wieder braucht.
    """

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

    def _show(self) -> None:
        if self.wordWrap():
            super().setText(self._full)
            return
        super().setText(
            self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width())
        )


class TourPanel(QWidget):
    """Führt durch ein Beispiel: erklärt, wartet, erkennt, schaltet weiter."""

    closed = Signal()
    pointsAt = Signal(str)
    followRequested = Signal(str)
    """Das nächste Beispiel, wenn die Tour zu Ende ist und jemand weitermachen
    will — trägt seine Kennung."""
    """Wovon der aktuelle Schritt spricht — „history", „parameters", „report",
    „tree" oder „viewport". Das Fenster lässt den Bereich kurz aufleuchten."""
    """Die Tour wurde beendet — das Fenster nimmt den Reiter weg."""

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
        self._already: set[int] = set()
        """Schritte, deren Erkennung schon beim Start zutraf. Sie zählen nicht
        als getan — der Nutzer hat sie nicht getan."""
        self._rows: list[tuple[QLabel, StepLabel]] = []
        self._row_hosts: list[QWidget] = []
        """Ein Trägerwidget je Schrittzeile. Aufgeräumt wird über genau ein
        ``deleteLater`` auf dem Träger — Marker und Text sterben als seine
        Kinder mit. Die erste Fassung nahm die Zeilen-Layouts mit ``takeAt``
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
        heading = QFont(self.title.font())
        heading.setBold(True)
        self.title.setFont(heading)

        self.intro = QLabel("", self)
        self.intro.setWordWrap(True)

        self.progress = QLabel("", self)

        steps_host = QWidget(self)
        self._steps_layout = QVBoxLayout(steps_host)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.setSpacing(NORMAL)
        self._steps_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(steps_host)

        self.closing = QLabel("", self)
        self.closing.setWordWrap(True)
        self.closing.setVisible(False)

        self.next_button = QPushButton(tr("Weiter"), self)
        self.next_button.setToolTip(
            tr("Schaltet zum nächsten Schritt — auch, wenn der aktuelle nicht gemacht wurde.")
        )
        self.next_button.clicked.connect(self.advance)
        # Am Ende der Tour steht eine Frage, die vorher niemand beantwortet
        # hat: und jetzt? Der Abschlusstext sagte, was man gelernt hat, und
        # führte nirgendwohin — die übrigen sechs Beispiele fand nur, wer den
        # Startbildschirm wiederzufinden wusste.
        self.follow_button = QPushButton("", self)
        self.follow_button.setVisible(False)
        self.follow_button.clicked.connect(self._follow)
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
        self._document = self._session.project.document
        self._example = example
        self._current = 0
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
            host = QWidget(self)
            marker = QLabel("", host)
            marker.setFixedWidth(self.fontMetrics().height() + 4)
            marker.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            text = StepLabel(f"{index + 1}. {step.text}", host)
            text.setWordWrap(True)
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
        """„Weiter": quittiert den aktuellen Schritt von Hand."""
        if self._tour is None or self._current >= len(self._tour.steps):
            return
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

        advanced = False
        while self._current < len(tour.steps):
            if tour.steps[self._current].done is not None:
                if not done(self._current):
                    break
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
            self._current += 1
            advanced = True
        if advanced:
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
            text.setEnabled(index <= self._current)
            # **Jeder Schritt bricht um.** Nur der aktuelle tat es, die übrigen
            # endeten mit einer Auslassung auf ihrer Zeile — bei fünf Schritten
            # waren vier davon unlesbar („Öffnen Sie den letzten Schritt
            # „Bohrung setze…"), und unter ihnen standen hundertfünfzig
            # Bildpunkte leer. Die Kürzung sparte Platz, den es nicht zu sparen
            # gab. Der Schrittbereich liegt in einer ``QScrollArea``, eine lange
            # Tour rollt also, statt die Knöpfe hinauszuschieben.
            #
            # ``StepLabel`` behält beide Fähigkeiten: eine schmale Spalte
            # braucht die Auslassung weiter, und was sie kann, prüft
            # ``tests/test_style.py`` am Widget.
            text.set_wrapped(True)
            if index < self._current:
                marker.setPixmap(self._mark("done"))
            elif index == self._current:
                marker.setPixmap(self._mark("step"))
            else:
                marker.clear()
        self._point_at_current()

        finished = self._current >= len(tour.steps)
        self.closing.setVisible(finished)
        self.next_button.setVisible(not finished)
        following = self._next_example() if finished else None
        self.follow_button.setVisible(following is not None)
        if following is not None:
            self.follow_button.setText(f"{tr('Weiter mit')}: {following.title}")
        self.progress.setText(
            tr("Tour abgeschlossen.")
            if finished
            else f"{tr('Schritt')} {self._current + 1} / {len(tour.steps)}"
        )

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
        if tour is None or self._current >= len(tour.steps):
            self._pointed_at = None
            return
        target = tour.steps[self._current].shows
        if target == self._pointed_at:
            return
        self._pointed_at = target
        if target is not None:
            self.pointsAt.emit(target)

    def _clear_rows(self) -> None:
        # Das Panel-Layout vergisst ein zerstörtes Widget von selbst — mehr
        # als das eine ``deleteLater`` je Zeile wäre schon wieder ein zweiter
        # Besitzer.
        for host in self._row_hosts:
            host.deleteLater()
        self._row_hosts.clear()
        self._rows.clear()
