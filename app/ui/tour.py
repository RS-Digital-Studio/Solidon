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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.examples import Example
from app.core.tour import Tour
from app.core.types import Document
from app.i18n import tr
from app.ui.icons import icon
from app.ui.session import Session


class TourPanel(QWidget):
    """Führt durch ein Beispiel: erklärt, wartet, erkennt, schaltet weiter."""

    closed = Signal()
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
        self._rows: list[tuple[QLabel, QLabel]] = []
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
        self._steps_layout.setSpacing(8)
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
        self.stop_button = QPushButton(tr("Tour beenden"), self)
        self.stop_button.clicked.connect(self.stop)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.next_button)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
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
        self._current = 0

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
            text = QLabel(f"{index + 1}. {step.text}", host)
            text.setWordWrap(True)
            row = QHBoxLayout(host)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
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

        In einer Schleife, nicht einmal: wer die Handlung eines späteren
        Schritts schon vorweggenommen hat, soll ihn nicht noch einmal tun
        müssen.
        """
        tour = self._tour
        if tour is None or self._session.project.document is not self._document:
            return

        advanced = False
        while self._current < len(tour.steps):
            step = tour.steps[self._current]
            if step.done is None or not step.done(
                self._session.project.document, self._session.history
            ):
                break
            self._current += 1
            advanced = True
        if advanced:
            self._update_marks()

    # --- Darstellung ------------------------------------------------------------

    def _mark(self, name: str) -> QPixmap:
        pixmap = self._marks.get(name)
        if pixmap is None:
            size = self.fontMetrics().height()
            pixmap = icon(name, self).pixmap(size, size)
            self._marks[name] = pixmap
        return pixmap

    def _update_marks(self) -> None:
        tour = self._tour
        if tour is None:
            return
        for index, (marker, text) in enumerate(self._rows):
            body = QFont(text.font())
            body.setBold(index == self._current)
            text.setFont(body)
            text.setEnabled(index <= self._current)
            if index < self._current:
                marker.setPixmap(self._mark("done"))
            elif index == self._current:
                marker.setPixmap(self._mark("step"))
            else:
                marker.clear()

        finished = self._current >= len(tour.steps)
        self.closing.setVisible(finished)
        self.next_button.setVisible(not finished)
        self.progress.setText(
            tr("Tour abgeschlossen.")
            if finished
            else f"{tr('Schritt')} {self._current + 1} / {len(tour.steps)}"
        )

    def _clear_rows(self) -> None:
        # Das Panel-Layout vergisst ein zerstörtes Widget von selbst — mehr
        # als das eine ``deleteLater`` je Zeile wäre schon wieder ein zweiter
        # Besitzer.
        for host in self._row_hosts:
            host.deleteLater()
        self._row_hosts.clear()
        self._rows.clear()
