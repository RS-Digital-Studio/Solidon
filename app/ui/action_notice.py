"""Die Quittung einer Handlung über der Ansicht — nie über einer Karte (FD-108, FD-162).

``MainWindow.announce`` sagt das Ergebnis einer Handlung in der Statuszeile
und zeigt es zusätzlich als passive Blase am Ort der Handlung. Die Blase stand
am Zeiger und lag damit über dem, was dort gerade bedient wurde: „Die Kette
hält an — siehe Prüfbericht.“ acht Sekunden über Hauptknopf und Befundzeilen,
die Rücknahme-Quittung über der Sammelzeile der Maßkarte. Und nach dem
nächsten Schritt meldete die Statuszeile weiter „zurückgenommen“.

Eine Regel für beide:

- **Nie über einer Karte.** Hindernis ist alles, was über dem Bild schwebt:
  die Zonen und Einladungen über der Ansicht und die frei gesetzten Kinder der
  Ansicht selbst (Maßkarte, Leisten, Felder) — nicht, was ihr Layout trägt
  (die Zeichenfläche), und nicht ein Schleier über allem. Gesucht wird die
  freie Stelle, die dem Ort der Handlung am nächsten liegt
  (:func:`free_spot`); gibt es keine, steht der Satz nur in der Statuszeile.
  Kommt eine Karte dazu oder wandert eine, rückt die Blase nach.
- **Weg mit dem nächsten Schritt.** Die Quittung merkt sich, nach welchem
  Dokumentstand sie gesagt wurde (:meth:`ActionNotice.remember`); ein späterer
  Schritt ohne eigene Quittung nimmt sie mit (:meth:`ActionNotice.outlived_by`).
  Was in derselben Runde der Ereignisschleife gesagt wird wie der Schritt,
  gehört zu ihm und bleibt.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtWidgets import QWidget

from app.ui.app_events import forget, listen
from app.ui.leash import stop_watching_the_dying
from app.ui.style import ROOMY
from app.ui.viewport import SketchSelectionBadge

#: Das Raster der Fernsuche, wenn neben Zeiger und Karten nichts frei ist.
SEARCH_STEP = 24

#: Wie tief unter der Ansicht noch Flächen liegen, deren Kinder schweben:
#: Stapel, Seite, Zeichenfläche.
SURFACE_DEPTH = 3

Rect = tuple[int, int, int, int]
"""Ein Rechteck als ``(links, oben, Breite, Höhe)``."""


def _overlaps(first: Rect, second: Rect) -> bool:
    return (
        first[0] < second[0] + second[2]
        and second[0] < first[0] + first[2]
        and first[1] < second[1] + second[3]
        and second[1] < first[1] + first[3]
    )


def free_spot(
    size: tuple[int, int],
    anchor: tuple[int, int],
    room: tuple[int, int],
    obstacles: Sequence[Rect],
    *,
    gap: int = ROOMY,
) -> tuple[int, int] | None:
    """Die freie Stelle für eine Blase von ``size`` — am nächsten an ``anchor``, oder keine.

    ``room`` ist die Fläche darunter, ``obstacles`` sind die Karten darauf. Ein
    Platz hält ``gap`` Abstand zum Rand und zu jeder Karte. Versucht werden
    zuerst die Stellen unter und über dem Ort der Handlung und an den vier
    Seiten jeder Karte auf seiner Höhe, dann ein grobes Raster über die ganze
    Fläche. Gewonnen hat der kleinste Abstand vom Ort zur Blase.
    """
    width, height = size
    room_width, room_height = room
    if width + 2 * gap > room_width or height + 2 * gap > room_height:
        return None
    padded = [
        (left - gap, top - gap, wide + 2 * gap, tall + 2 * gap)
        for left, top, wide, tall in obstacles
    ]
    x, y = anchor
    near: list[tuple[int, int]] = [(x, y + gap), (x, y - gap - height), (x - width // 2, y + gap)]
    for left, top, wide, tall in obstacles:
        near.extend(
            (
                (left - gap - width, y - height // 2),
                (left + wide + gap, y - height // 2),
                (x - width // 2, top + tall + gap),
                (x - width // 2, top - gap - height),
            )
        )
    far = (
        (column, row)
        for row in range(gap, room_height - height - gap + 1, SEARCH_STEP)
        for column in range(gap, room_width - width - gap + 1, SEARCH_STEP)
    )
    best: tuple[int, tuple[int, int]] | None = None
    for left, top in (*near, *far):
        left = min(max(gap, left), room_width - width - gap)
        top = min(max(gap, top), room_height - height - gap)
        candidate = (left, top, width, height)
        if any(_overlaps(candidate, obstacle) for obstacle in padded):
            continue
        reach = gap - 1
        if left - reach <= x < left + width + reach and top - reach <= y < top + height + reach:
            # Nicht über der Stelle, an der gerade gehandelt wurde.
            continue
        distance = max(left - x, x - (left + width), 0) + max(top - y, y - (top + height), 0)
        if best is None or distance < best[0]:
            best = (distance, (left, top))
    return best[1] if best is not None else None


class ActionNotice(SketchSelectionBadge):
    """Dieselbe passive Quittung wie in der Skizze, am Ort der letzten Handlung."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._anchor = QPoint()
        self._wanted = False
        """Ob gerade eine Quittung gilt — gezeigt wird sie nur an freier Stelle."""
        self._steps: Hashable | None = None
        self._hosts: tuple[QWidget, ...] = ()
        """Fläche und Ansicht, deren schwebende Kinder zuletzt Hindernis waren."""
        self._expiry = QTimer(self)
        self._expiry.setSingleShot(True)
        self._expiry.timeout.connect(self.clear)
        self._turn = QTimer(self)
        """Läuft, solange die Runde der Ereignisschleife dauert, in der gesagt wurde."""
        self._turn.setSingleShot(True)
        self._turn.setInterval(0)
        parent.installEventFilter(self)

    # --- Was gesagt wurde und wann ----------------------------------------------------

    def remember(self, steps: Hashable) -> None:
        """Nach welchem Dokumentstand gesagt wurde — die Runde gehört der Quittung."""
        self._steps = steps
        self._turn.start()

    def outlived_by(self, steps: Hashable) -> bool:
        """Ob ein späterer Schritt die gesagte Quittung überholt hat.

        Nicht in derselben Runde: Wer erst ansagt und dann im selben Zug den
        Schritt anlegt, spricht über diesen Schritt.
        """
        return self._steps is not None and steps != self._steps and not self._turn.isActive()

    # --- Zeigen -------------------------------------------------------------------------

    def show_message(self, text: str, anchor: QPoint) -> None:
        """Ersetzt die alte Meldung; Fortschritt besitzt weder Text noch Zeitgeber."""
        self.clear()
        if not text:
            return
        self._anchor = anchor
        self._wanted = True
        self.setText(text)
        # Solange sie gilt, hört sie auf jede Karte, die kommt, geht oder
        # wandert — über den einen Filter der Anwendung und nur so lange.
        listen(self, _MOVES)
        self.place()
        # Der volle Text bleibt zusätzlich in der Statuszeile. Hier reichen
        # kurze Sätze mindestens acht Sekunden, lange bekommen mehr Lesezeit.
        self._expiry.start(max(8000, len(text) * 60))

    def clear(self) -> None:
        """Projektwechsel und Fensterabbau nehmen auch den Zeitgeber mit."""
        self._expiry.stop()
        self._wanted = False
        forget(self)
        self._hosts = ()
        super().clear()
        self.hide()

    def place(self) -> None:
        """An der freien Stelle nächst dem gemerkten Ort — oder gar nicht (FD-108)."""
        parent = self.parentWidget()
        if parent is None or not self._wanted:
            return
        available = max(1, parent.width() - 2 * ROOMY)
        self.setMaximumWidth(min(available, max(1, self.fontMetrics().averageCharWidth() * 60)))
        self.adjustSize()
        spot = free_spot(
            (self.width(), self.height()),
            (self._anchor.x(), self._anchor.y()),
            (parent.width(), parent.height()),
            [_as_tuple(rect) for rect in self.obstacles()],
        )
        if spot is None:
            # Kein freier Platz über dem Bild: Der Satz steht in der Statuszeile.
            self.hide()
            return
        self.move(*spot)
        self.show()
        self.raise_()

    def obstacles(self) -> list[QRect]:
        """Was über dem Bild schwebt, in Koordinaten der Fläche unter der Blase."""
        parent = self.parentWidget()
        if parent is None:
            return []
        self._hosts = self._surfaces()
        found: list[QRect] = []
        for host in self._hosts:
            layout = host.layout()
            for child in host.children():
                if (
                    not isinstance(child, QWidget)
                    or child is self
                    or child in self._hosts
                    or child.isWindow()
                    or child.isHidden()
                    or not child.isVisibleTo(parent)
                    or (layout is not None and layout.indexOf(child) >= 0)
                ):
                    continue
                corner = child.pos() if host is parent else host.mapTo(parent, child.pos())
                rect = QRect(corner, child.size())
                if rect.isEmpty() or rect.contains(parent.rect()):
                    # Ein Schleier über allem ist keine Karte, neben die man rückt.
                    continue
                found.append(rect)
        return found

    def _surfaces(self) -> tuple[QWidget, ...]:
        """Die Fläche und die Ansicht samt den Seiten, die ihr Layout trägt.

        Die Ansicht ist ein Stapel, die 3D-Ansicht eine seiner Seiten; ihre frei
        gesetzten Kinder — Maßkarte, Leisten, Felder — schweben über dem Bild
        wie die Zonen über der Ansicht. Hinab geht es nur über Kinder, die ein
        Layout trägt: Das sind Flächen, keine Karten.
        """
        parent = self.parentWidget()
        if parent is None:
            return ()
        view = getattr(parent, "view", None)
        found: list[QWidget] = [parent]
        level = [view] if isinstance(view, QWidget) else []
        for _depth in range(SURFACE_DEPTH):
            following: list[QWidget] = []
            for host in level:
                if host.isHidden():
                    continue
                found.append(host)
                layout = host.layout()
                if layout is None:
                    continue
                following.extend(
                    child
                    for child in host.children()
                    if isinstance(child, QWidget) and layout.indexOf(child) >= 0
                )
            level = following
        return tuple(found)

    # --- Nachrücken -----------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        """Größe, Schrift und jede schwebende Karte dürfen die Blase nicht verdecken."""
        if stop_watching_the_dying(self, watched, event):
            return False
        kind = event.type()
        parent = self.parentWidget()
        if watched is parent:
            if kind == QEvent.Type.Hide:
                self.clear()
            elif self._wanted and kind in _MOVES:
                self.place()
        elif (
            self._wanted
            and kind in _MOVES
            and watched is not self
            and isinstance(watched, QWidget)
            and watched.parent() in self._hosts
        ):
            self.place()
        return False


_MOVES = frozenset(
    {
        QEvent.Type.Resize,
        QEvent.Type.Move,
        QEvent.Type.Show,
        QEvent.Type.Hide,
        QEvent.Type.FontChange,
        QEvent.Type.StyleChange,
    }
)


def _as_tuple(rect: QRect) -> Rect:
    return rect.x(), rect.y(), rect.width(), rect.height()
