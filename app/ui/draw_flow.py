"""Das Werkzeug *Zeichnen* in der Ansicht: drei Klicks, ein Schritt (RM-559, RM-561).

Die Bedeutung jedes Klicks steht in ``draw_tool.py`` und ist dort ohne Fenster
geprüft; hier steht, wie Mausstellen, Tasten und Felder zu diesen Aufrufen
werden, was im Bild steht und wie der fertige Schritt in den Verlauf kommt.

**Kein Moduswechsel.** Ansicht, Projektion und Nachbarn bleiben, wie sie sind;
unten steht nur eine schmale Leiste. Rechte Taste, Rad und Tasten bewegen
die Kamera, die linke Taste gehört dem Entwurf (``Viewport.set_placement_pointer``,
dieselbe Vorfahrt wie bei der Platzierung). **Kein Dialog nach dem dritten
Klick** (Regel 19): Er legt den Schritt an, das Werkzeug schließt, der Körper
ist gewählt. Escape verwirft das Unfertige, Strg+Z im Entwurf nimmt den
letzten Klick, danach den ganzen Schritt. Ein Umriss aus dem Editor ist kein
Unfertiges: Strg+Z führt ihn zurück in den Editor, Escape legt ihn wie eine
verworfene Zeichnung beiseite, und Strg+Z holt ihn von dort (H2).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from app.core.log import get_logger
from app.core.registry import REGISTRY
from app.core.scene.cancel import CancelSignal
from app.core.scene.history import OperationDraft
from app.core.sketch.planes import axis_hit, feature_plane_parts, ray_hit, to_plane
from app.core.sketch.serialize import sketch_to_text
from app.core.types import ObjectId, PlaneFrame, Point2, Sketch
from app.core.units import EPS_DISPLAY, EPS_GEOM, to_mm
from app.i18n import tr
from app.ui.draw_tool import (
    EXTRUDE_OP,
    JOIN_OP,
    MARK_REACH_PIXELS,
    POCKET_OP,
    SHAPE_KEYS,
    DrawDraft,
    DrawSurface,
    Lift,
    bed_surface,
    depth_limits,
    face_outline,
    face_surface,
    height_limits,
    lifted,
    operation_limits,
    picture,
    sentence,
    snapped,
)
from app.ui.labels import circle_word, display_unit, length, limit_sentence, read_number
from app.ui.leash import Worker, stop_watching_the_dying
from app.ui.render.api import PointerEvent
from app.ui.style import ROOMY, TIGHT

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

_log = get_logger(__name__)

#: Wie lange der Zeiger in Phase 0 ruhen muss, bevor die Fläche darunter gesucht
#: wird. Die Suche liest den Kennungspuffer (``Viewport._world_at``); je
#: Mausereignis wäre das die teuerste Stelle der Bewegung, nach dieser Pause
#: ist sie eine.
HOVER_MS: Final = 40

#: Wie weit der Treffer einer Bildstelle neben den Dreiecken einer Fläche liegen
#: darf, als Anteil der Körperdiagonale. Der Punkt kommt aus dem Tiefenpuffer
#: (``Viewport.placement_hit``), und dessen Auflösung ist ein Bruchteil der
#: Szenengröße, keine feste Länge (F-b).
FACE_GAP_SHARE: Final = 1e-3

#: Ab welchem Volumen zwei Körper sich überdecken (F-g): ein Würfel mit der
#: Kantenlänge der Anzeigegenauigkeit. Eine Längentoleranz wäre die falsche
#: Einheit, und was kleiner ist als das, was die Anzeige auflöst, ist eine
#: Berührung, keine Überdeckung.
OVERLAP_VOLUME: Final = EPS_DISPLAY**3

#: Ab welchem Winkel zwischen Blick und Normale die Höhe der senkrechten
#: Mausbewegung folgt statt der Achse — dieselben zehn Grad, unter denen die
#: Skizzenansicht einrastet (``Viewport._settle_sketch_view``).
STEEP_DEGREES: Final = 10.0


class DrawEntry(QFrame):
    """Die Maße am Zeiger — getippt statt geklickt (Muster E19).

    Ein oder zwei Felder: Breite und Tiefe am Rechteck, das Kreismaß am
    Kreis, Höhe oder Tiefe nach Klick 2. Die erste Ziffer öffnet es ohne
    Klick, Tab wechselt das Feld, die Eingabetaste übernimmt.
    """

    committed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("drawEntry")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        layout.setSpacing(TIGHT)
        self.names: list[QLabel] = []
        self.fields: list[QLineEdit] = []
        for _index in range(2):
            name = QLabel("", self)
            field = QLineEdit(self)
            field.setFixedWidth(72)
            field.setAlignment(Qt.AlignmentFlag.AlignRight)
            name.setBuddy(field)
            layout.addWidget(name)
            layout.addWidget(field)
            self.names.append(name)
            self.fields.append(field)
            field.installEventFilter(self)
        self.unit = QLabel("", self)
        layout.addWidget(self.unit)
        self.hide()

    def open(self, titles: list[str], anchor: QPoint, first: str) -> None:
        """Mit diesen Feldern am Zeiger öffnen, die erste Taste schon im ersten Feld."""
        unit = display_unit()
        for index, (name, field) in enumerate(zip(self.names, self.fields, strict=True)):
            shown = index < len(titles)
            name.setVisible(shown)
            field.setVisible(shown)
            field.clear()
            field.setStyleSheet("")
            if shown:
                name.setText(titles[index])
                field.setAccessibleName(titles[index])
        self.unit.setText(unit)
        self.adjustSize()
        self._place(anchor)
        self.show()
        self.raise_()
        self.fields[0].setText(first)
        self.fields[0].setFocus(Qt.FocusReason.OtherFocusReason)
        self.fields[0].setCursorPosition(len(first))

    def _place(self, anchor: QPoint) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        gap = 14
        left, top = anchor.x() + gap, anchor.y() + gap
        if left + self.width() > parent.width():
            left = anchor.x() - gap - self.width()
        if top + self.height() > parent.height():
            top = anchor.y() - gap - self.height()
        self.move(max(left, 0), max(top, 0))

    def values(self) -> list[float | None]:
        """Die getippten Zahlen in Millimetern — ``None``, wo keine steht."""
        unit = display_unit()
        read: list[float | None] = []
        for field in self.fields:
            if not field.isVisible():
                continue
            number = read_number(field.text())
            read.append(None if number is None else to_mm(number, unit))
        return read

    def refuse(self, index: int, reason: str) -> None:
        """Die abgelehnte Zahl bleibt markiert stehen, der Satz nennt die Grenze (F-d)."""
        field = self.fields[index]
        field.setStyleSheet("border: 2px dashed palette(highlight);")
        field.setToolTip(reason)
        field.setFocus()
        field.selectAll()

    def close_entry(self) -> None:
        for field in self.fields:
            field.clearFocus()
        self.hide()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.committed.emit()
            return True
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            shown = [field for field in self.fields if field.isVisible()]
            if len(shown) > 1:
                index = shown.index(watched) if watched in shown else 0
                step = -1 if key == Qt.Key.Key_Backtab else 1
                target = shown[(index + step) % len(shown)]
                target.setFocus(Qt.FocusReason.TabFocusReason)
                target.selectAll()
            return True
        return False


class _OverlapWorker(Worker):
    """Ob der neue Körper einen anderen mit Volumen überdeckt (F-g) — abseits des Hauptfadens.

    Die Hüllquader sind nur der Vorfilter: Ein Quader im Loch eines Rahmens
    liegt in dessen Hülle und berührt ihn nicht. Gerechnet wird die echte
    Schnittmenge (``geom.measure.body_overlap``) an **eigenen** Kopien
    (:func:`_private_body`): Die geteilten Arbeiterkopien aus
    ``placement_flow.for_a_worker`` gelten nur unter ihrem Schloss, und die
    Boolesche Rechnung schreibt in die Merker des Netzes (N3). Exakte Körper
    bleiben exakt — eine Sehnenfläche ergäbe an einem Stift im Loch ein
    Volumen, das es nicht gibt.
    """

    done = Signal(object)
    """Die Kennung des ersten überdeckten Körpers — oder ``None``."""

    def __init__(self, made: Any, others: list[tuple[ObjectId, Any]]) -> None:
        super().__init__()
        self._made = made
        self._others = others
        self.cancelled = CancelSignal()

    def work(self) -> None:
        from app.core.errors import OperationCancelled
        from app.core.geom.measure import body_overlap

        try:
            for object_id, other in self._others:
                try:
                    volume = body_overlap(self._made, other, cancelled=self.cancelled)
                except ValueError, RuntimeError:
                    # Ein offener oder kaputter Körper hat kein Innen; eine
                    # Überdeckung zu behaupten wäre geraten (Regel 21). Die
                    # Zeile im Protokoll zeigt einen Kern, der immer scheitert.
                    _log.info("overlap with %s not decided", object_id, exc_info=True)
                    continue
                if volume > OVERLAP_VOLUME:
                    self.done.emit(object_id)
                    return
        except OperationCancelled:
            return
        self.done.emit(None)


class DrawFlow(QObject):
    """Der Ablauf des Aufziehens: Zeiger, Klicks, Felder, Schritt (RM-559)."""

    closed = Signal()
    """Das Werkzeug ist zu — die Leiste geht, die Werkzeugzeile kommt zurück."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.view = window
        self.viewport = window.viewport
        self.bar = window.draw_bar
        self.draft: DrawDraft | None = None
        self.free = False
        """*Freie Form …*: Der nächste Klick öffnet den Skizzeneditor auf seiner Fläche."""
        self.pointer_at: Point2 | None = None
        """Wohin ein Klick in Phase 1 fällt — schon gefangen, auf der Ebene."""
        self.lift: Lift | None = None
        """Die Höhe, die ein Klick in Phase 2 setzt."""
        self._hover: tuple[DrawSurface, Point2, tuple[float, float, float]] | None = None
        self._hover_face: tuple[Any, Any] | None = None
        """Füllung (Ecken, Dreiecke) und Umriss der ebenen Fläche unter dem Zeiger."""
        self._last: tuple[int, int] | None = None
        self._press: tuple[int, int] | None = None
        self._steep_from: int | None = None
        self._unknown: tuple[str, Any, int, Any] | None = None
        """Die Stelle eines Netzes ohne erkannte Fläche (F-b), für die Erkennung dort."""
        self._resume_at: tuple[ObjectId, tuple[float, float, float], bool] | None = None
        """Stelle, Punkt und *Freie Form …* für das Weiter nach der Erkennung (Abnahme 10)."""
        self._watching: tuple[tuple[ObjectId, ...], str, frozenset[ObjectId], str] | None = None
        self._watched_step: int | None = None
        """Der Schritt, den der dritte Klick anlegte — hält die Kette an ihm, ist es F-i."""
        self.intent = ""
        """Die gewählte Art (M4, N1): Tasche und Anfügen brauchen die Fläche eines Körpers,
        und bei der Tasche ist getippt die Tiefe, bis der Zeiger eine Richtung zeigt."""
        self._kept: tuple[DrawDraft, Lift, Any, str] | None = None
        """Entwurf, Höhe, Herkunft und Art des letzten dritten Klicks — für F-i."""
        self._failed: tuple[int, Any] | None = None
        """Der gescheiterte Schritt und sein Befund (F-i): Der Entwurf steht wieder im Bild."""
        self._undo_depth = 0
        """Wie viele Züge der gescheiterte Schritt im Verlauf hat: er selbst und jede Reparatur."""
        self._typed_inward: bool | None = None
        """Die Richtung beim Öffnen des Höhenfelds — der Zeiger ändert sie nicht mehr (M3)."""
        self.origin: Any = None
        """Woher ein Umriss aus dem Editor kam — der Weg zurück für Strg+Z und Escape (H2)."""
        self._overlap: _OverlapWorker | None = None
        self._before_step: Any = None
        """Das Ergebnis vor dem Schritt: Eine Tasche behält die Kennung ihres Körpers,
        und an ihm ist noch nichts geschnitten (F-h)."""
        self.entry = DrawEntry(self.viewport)
        self.entry.committed.connect(self._commit_entry)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(HOVER_MS)
        self._hover_timer.timeout.connect(self._look)
        self.bar.shapeChosen.connect(self.choose)
        self.bar.freeRequested.connect(self.arm_free)
        self.bar.recognitionRequested.connect(self._recognise_here)
        self.bar.closeRequested.connect(self.discard)
        self.bar.repairRequested.connect(self._repair_failed)
        self.bar.placesRequested.connect(self._show_failed_places)
        window.session.sceneChanged.connect(self._scene_changed)
        self._generation = window.session.project_generation
        """Zu welchem Projekt der Entwurf gehört — ein anderes kennt seine Fläche nicht."""
        self._filtered: QObject | None = None

    # --- Ein- und Ausgang ---------------------------------------------------------

    @property
    def active(self) -> bool:
        return self.draft is not None

    @property
    def inward_first(self) -> bool:
        """Die gewählte Tasche: Eine getippte Zahl ist die Tiefe (M4)."""
        return self.intent == POCKET_OP

    @property
    def failed(self) -> bool:
        """Ob der Entwurf nach einer gescheiterten Rechnung wieder im Bild steht (F-i)."""
        return self._failed is not None

    def start(self, shape: str = "", *, intent: str = "") -> None:
        """Das Werkzeug öffnen — Phase 0, die gewählte Form bleibt vom letzten Mal.

        ``intent`` ist die gewählte Art aus Menü oder Palette: Tasche und
        Anfügen nehmen nur die Fläche eines Körpers an, und bei der Tasche ist
        eine getippte Zahl die Tiefe (M4, N1, Regel 21).
        """
        self.draft = DrawDraft(shape or "rectangle")
        self.free = False
        self._unknown = None
        self.intent = intent
        self.origin = None
        self._begin()

    def start_with_outline(
        self,
        outline: Sketch,
        surface: DrawSurface,
        shift: tuple[float, float, float],
        *,
        intent: str = "",
        origin: Any = None,
    ) -> None:
        """Ein Umriss aus dem Skizzeneditor kommt zurück: Es fehlt nur die Höhe (RM-561).

        ``origin`` beschreibt den Editor, aus dem er kam — Strg+Z führt dorthin
        zurück, Escape legt ihn als verworfene Zeichnung ab (H2).
        """
        self.draft = DrawDraft()
        self.draft.with_outline(outline, surface)
        self.draft.shift = shift
        self.free = False
        self._unknown = None
        self.intent = intent
        self.origin = origin
        self._begin()

    def _begin(self) -> None:
        self._generation = self.view.session.project_generation
        self.pointer_at = None
        self.lift = None
        self._hover = None
        self._hover_face = None
        self._steep_from = None
        self._typed_inward = None
        self.viewport.set_placement_pointer(self.pointer)
        self.viewport.set_drawing(True)
        widget = getattr(self.viewport.renderer, "widget", None)
        if widget is not None and self._filtered is not widget:
            widget.installEventFilter(self)
            self._filtered = widget
        if widget is not None:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh()

    def close(self) -> None:
        """Das Werkzeug schließen — ohne Schritt, falls keiner angelegt wurde."""
        if self.draft is None:
            return
        self.draft = None
        self.free = False
        self.pointer_at = None
        self.lift = None
        self._hover = None
        self._hover_face = None
        self._unknown = None
        self._typed_inward = None
        self.intent = ""
        self.origin = None
        self._failed = None
        self._hover_timer.stop()
        self.entry.close_entry()
        self.viewport.set_placement_pointer(None)
        self.viewport.set_drawing(False)
        self.viewport.clear_draw()
        if self._filtered is not None:
            self._filtered.removeEventFilter(self)
            self._filtered = None
        self.closed.emit()

    def escape(self) -> bool:
        """Escape: erst das offene Feld, dann der Entwurf samt Werkzeug (E7)."""
        if self.draft is None:
            return False
        if self.entry.isVisibleTo(self.viewport):
            self.entry.close_entry()
            self._refocus()
            return True
        if self._failed is not None:
            self._abandon_failed(keep_draft=False)
            return True
        self.discard()
        return True

    def discard(self) -> None:
        """Das Werkzeug schließen; ein Umriss aus dem Editor bleibt für Strg+Z (H2).

        Escape nimmt nur Unfertiges (§25). Wer im Editor *Fertig* gedrückt hat,
        hält Fertiges in der Hand — eine halbe Stunde Bedingungsarbeit wäre
        sonst mit einem Tastendruck weg. Dieselbe Zusage wie *Verwerfen* im
        Editor: „Zeichnung verworfen — Strg+Z holt sie zurück.“
        """
        draft = self.draft
        if draft is None:
            return
        outline, origin = draft.outline, self.origin
        self.close()
        if outline is not None and origin is not None:
            self.view.return_the_outline(origin, sketch_to_text(outline), now=False)

    def undo(self) -> bool:
        """Strg+Z im Entwurf: den letzten Klick zurück — nie einen Schritt im Verlauf.

        Mit einem Umriss aus dem Editor geht es zurück in den Editor (H2); in
        Phase 0 gibt es nichts zurückzunehmen, und der Satz sagt, wie es
        weitergeht, statt still zu bleiben (G10). Falsch heißt: kein Entwurf.
        """
        draft = self.draft
        if draft is None:
            return False
        if self.entry.isVisibleTo(self.viewport):
            self.entry.close_entry()
            self._refocus()
            return True
        if self._failed is not None:
            self._abandon_failed(keep_draft=True)
            return True
        if draft.outline is not None and self.origin is not None:
            outline, origin = draft.outline, self.origin
            self.close()
            self.view.return_the_outline(origin, sketch_to_text(outline), now=True)
            return True
        if not draft.back():
            self.view.announce(tr("Erst den Körper fertig aufziehen oder mit Escape abbrechen."))
            return True
        self.lift = None
        self._steep_from = None
        self._refresh()
        return True

    def can_undo(self) -> bool:
        """Solange das Werkzeug offen ist, gehört Strg+Z ihm — auch ohne Klick (G10)."""
        return self.draft is not None

    def unsaved(self) -> bool:
        """Ein Umriss aus dem Editor ist Arbeit ohne Schritt; einzelne Klicks sind es nicht (G3)."""
        draft = self.draft
        return draft is not None and draft.outline is not None

    def choose(self, shape: str) -> None:
        """Rechteck oder Kreis — per Knopf oder Taste, solange die Grundfläche nicht steht."""
        if self.draft is not None and self.draft.choose(shape):
            self.free = False
        self._refresh()

    def arm_free(self) -> None:
        """*Freie Form …*: mit Ebene sofort in den Editor, sonst beim nächsten Klick."""
        draft = self.draft
        if draft is None:
            return
        if draft.surface is not None and draft.first is not None:
            surface, start, shift = draft.surface, draft.first, draft.shift
            self.close()
            self.view.draw_freely(surface, start, shift)
            return
        self.free = True
        self._refresh()

    # --- Zeiger -------------------------------------------------------------------

    def pointer(self, event: PointerEvent) -> bool:
        """Die linke Taste gehört dem Entwurf; Kamera und Rad bleiben, wo sie waren."""
        if self.draft is None:
            return False
        if event.kind == "leave":
            self._hover_timer.stop()
            self.pointer_at = None
            self._show()
            return False
        if event.kind == "move":
            if event.buttons and "left" not in event.buttons:
                return False
            self.move_to(event.x, event.y)
            return True
        if event.button != "left":
            return False
        if event.kind == "press":
            self._press = (event.x, event.y)
            return True
        if event.kind == "release":
            self._press = None
            self.click_at(event.x, event.y)
            return True
        return False

    def move_to(self, x: int, y: int) -> None:
        """Der Zeiger bewegt sich: Phase 0 sucht die Fläche, 1 folgt der Ecke, 2 der Höhe."""
        draft = self.draft
        if draft is None:
            return
        self._last = (x, y)
        if draft.phase == 0:
            self._hover_timer.start()
            return
        if draft.phase == 1:
            point = self._plane_point(x, y)
            if point is not None:
                self.aim(point)
            return
        if self.entry.isVisibleTo(self.viewport):
            # **Eine getippte Zahl ersetzt Zeiger samt Richtung** (M3): Was
            # beim Öffnen des Felds galt, gilt, bis es übernommen ist.
            return
        raw = self._height_at(x, y)
        if raw is not None:
            self.lift_to(raw)

    def click_at(self, x: int, y: int) -> None:
        """Ein Klick an dieser Bildstelle — je Phase seine Bedeutung."""
        draft = self.draft
        if draft is None:
            return
        self._last = (x, y)
        if draft.phase == 0:
            self._hover_timer.stop()
            self._look()
            target = self._target_at(x, y)
            self.take(target)
            return
        if draft.phase == 1:
            point = self._plane_point(x, y)
            if point is not None:
                self.aim(point)
                self.place()
                self._steep_from = y
            return
        if self._failed is not None:
            self._show_failure()
            return
        raw = self._height_at(x, y)
        if raw is not None:
            self.lift_to(raw)
        self.settle()

    # --- Bedeutung, ohne Bildpunkte prüfbar ----------------------------------------

    def take(self, target: tuple[str, Any, Any, Any] | None) -> None:
        """Klick 1 auf ein Ziel aus :meth:`_target_at`: Fläche, Bett oder ein Satz."""
        draft = self.draft
        if draft is None:
            return
        if target is None:
            self.view.announce(tr("Auf das Bett oder eine ebene Fläche klicken."))
            return
        kind, surface, point, shift = target
        if kind == "curved":
            self.view.announce(
                tr(
                    "Auf einer gewölbten Fläche lässt sich nichts aufziehen. "
                    "Eine ebene Fläche oder das Bett anklicken."
                )
            )
            return
        if kind == "unknown":
            self._unknown = surface
            self._refresh()
            self.view.announce(tr("Diese Stelle ist noch nicht als Fläche erkannt."))
            return
        self._unknown = None
        if self.intent in (JOIN_OP, POCKET_OP) and surface.body is None:
            # **Die gewählte Art gilt** (N1, Regel 21): Eine Tasche auf dem Bett
            # würde still ein neuer Körper.
            self.view.announce(
                tr("Für eine Tasche auf eine Fläche eines Körpers klicken.")
                if self.intent == POCKET_OP
                else tr("Zum Anfügen auf eine Fläche eines Körpers klicken.")
            )
            return
        if self.free:
            self.close()
            self.view.draw_freely(surface, point, shift)
            return
        draft.begin(surface, point)
        draft.shift = shift
        self.pointer_at = None
        self._refresh()

    def aim(self, point: Point2) -> None:
        """Phase 1: Die Gegenecke folgt dem gefangenen Zeiger."""
        draft = self.draft
        if draft is None or draft.surface is None:
            return
        self.pointer_at = self._snap(point, draft.surface)
        draft.aim(self.pointer_at)
        self._show()

    def place(self) -> None:
        """Klick 2 an der gefangenen Stelle — oder der Satz, warum nicht (F-c)."""
        draft = self.draft
        if draft is None or self.pointer_at is None:
            return
        refusal = draft.place(self.pointer_at)
        if refusal:
            self.view.announce(refusal)
            return
        self.lift = None
        self._refresh()

    def lift_to(self, raw: float) -> None:
        """Phase 2: die Höhe am Zeiger, gefangen, geklemmt, mit Richtung."""
        draft = self.draft
        if draft is None or draft.surface is None:
            return
        self.lift = lifted(raw, self._step(draft.surface.frame), draft.surface, *self._limits())
        if self.lift.note:
            self.bar.state.setText(self.lift.note)
        self._show()

    def settle(self) -> bool:
        """Klick 3: Der Schritt entsteht, das Werkzeug schließt (E5, E6)."""
        draft = self.draft
        lift = self.lift
        if draft is None or lift is None or self._failed is not None:
            return False
        if lift.note:
            # **Null bleibt null** (F-e): Der Satz steht schon in der Leiste;
            # der Klick sagt ihn noch einmal und baut keinen Splitter.
            self.view.announce(lift.note)
            return False
        step = draft.step(lift)
        if step is None:
            return False
        result = self.view.session.last_result
        before = frozenset(result.scene.objects) if result is not None else frozenset()
        name = draft.surface.name if draft.surface is not None else ""
        spec = REGISTRY.get(step.op)
        applied = self.view.session.apply(
            spec.title, [OperationDraft(op=step.op, inputs=step.inputs, params=step.params)]
        )
        if not applied:
            # Die Absage steht in der Statuszeile (``failed``); der Entwurf
            # bleibt im Bild, damit ein zweiter Versuch nicht neu zeichnet.
            return False
        outputs = self._outputs_of_the_last_step()
        self._watching = (outputs, step.op, before, name)
        self._watched_step = self.view.session.project.document.ops[-1].id
        self._before_step = result
        self._kept = (draft, lift, self.origin, self.intent)
        self._undo_depth = 1
        self.close()
        self._scene_changed(self.view.session.last_result)
        return True

    def press_enter(self) -> None:
        """Die Eingabetaste ohne Feld: In Phase 0 beginnt der Entwurf in der Mitte (Abnahme 9)."""
        draft = self.draft
        if draft is None or draft.phase != 0:
            return
        surface = self.view.drawn_face_of_the_selection() or bed_surface()
        # Auf Platte 2 steht der Körper versetzt im Bild (G4).
        self.take(("face", surface, (0.0, 0.0), self.viewport.view_offset_of(surface.body)))

    def type_first(self, text: str) -> bool:
        """Die erste Ziffer öffnet das Maßfeld am Zeiger (Muster E19)."""
        draft = self.draft
        if draft is None or draft.phase == 0:
            return False
        if draft.phase == 1:
            titles = (
                [circle_word()]
                if draft.shape == "circle"
                else [str(tr("Breite")), str(tr("Tiefe"))]
            )
        else:
            inward = self._direction()
            self._typed_inward = inward
            titles = [str(tr("Tiefe") if inward else tr("Höhe"))]
        ratio = self.viewport._device_ratio()
        spot = self._last or (self.viewport.width() // 2, self.viewport.height() // 2)
        anchor = QPoint(int(spot[0] / ratio), int(spot[1] / ratio))
        self.entry.open(titles, anchor, text)
        return True

    def type_values(self, values: list[float | None]) -> bool:
        """Getippte Maße übernehmen — Grundfläche oder Höhe; falsch bei abgelehnter Zahl."""
        draft = self.draft
        if draft is None or not values or values[0] is None:
            return False
        if draft.phase == 1:
            limits = operation_limits(EXTRUDE_OP, "length")
            for index, value in enumerate(values):
                if value is not None and not self._accepts(index, value, limits):
                    return False
            if draft.shape == "circle":
                refusal = draft.type_size(float(values[0]))
            else:
                second = values[1] if len(values) > 1 else None
                refusal = draft.type_size(float(values[0]), second, self.pointer_at)
            if refusal:
                self.view.announce(refusal)
                return False
            self.entry.close_entry()
            self._refocus()
            self.lift = None
            self._refresh()
            return True
        if draft.phase != 2 or draft.surface is None:
            return False
        typed = float(values[0])
        inward = self._typed_inward if self._typed_inward is not None else self._direction()
        # **Ein Betrag in der gezeigten Richtung** (E8): Der Kunde tippt die
        # Zahl, die er liest; ein Minus kehrt die Richtung um.
        height = -typed if inward else typed
        surface = draft.surface
        if height < 0.0 and surface.cuts:
            if not self._accepts(0, -height, depth_limits()):
                return False
            through = -height >= surface.through_depth - EPS_GEOM
            self.lift = Lift(-surface.through_depth if through else height, through=through)
        elif height < 0.0:
            self.entry.refuse(0, lifted(-1.0, 0.0, surface, *self._limits()).note)
            return False
        else:
            if not self._accepts(0, height, height_limits()):
                return False
            self.lift = Lift(height)
        self.entry.close_entry()
        self._typed_inward = None
        return self.settle()

    def _direction(self) -> bool:
        """Ob eine getippte Zahl nach innen zählt: was der Zeiger zeigt, sonst die gewählte Art."""
        if self.lift is not None and abs(self.lift.height) > EPS_GEOM:
            return self.lift.height < 0.0
        draft = self.draft
        surface = draft.surface if draft is not None else None
        return self.inward_first and surface is not None and surface.cuts

    # --- Rückmeldung nach dem Schritt ------------------------------------------

    def _outputs_of_the_last_step(self) -> tuple[ObjectId, ...]:
        operations = self.view.session.project.document.ops
        return tuple(operations[-1].outputs) if operations else ()

    def _scene_changed(self, result: Any) -> None:
        """Der Körper wird gewählt, sobald er im Bild steht; Überdeckung und Zerfall sagen es."""
        if result is None:
            return
        if self.view.session.project_generation != self._generation:
            # Ein anderes Projekt: Entwurf, wartende Wahl und Wiederaufnahme
            # gehören dem vorigen.
            self._generation = self.view.session.project_generation
            self._resume_at = None
            self._watching = None
            self._watched_step = None
            self._kept = None
            self.cancel_overlap()
            self.close()
            return
        self._drop_a_lost_target(result)
        if self._resume_at is not None and self.draft is None:
            self.resume_after_recognition(result)
        watching = self._watching
        if watching is None or result is self._before_step:
            return
        step = self._watched_step
        if step is not None and result.stopped_at == step:
            # **F-i:** Die Kette hält am neuen Schritt an. Der Entwurf kommt
            # zurück ins Bild, die Leiste nennt die Ursache und die Auswege.
            self._watching = None
            self._watched_step = None
            self._before_step = None
            self._come_back_failed(step, result)
            return
        outputs, op, before, name = watching
        if not outputs or not set(outputs) <= set(result.scene.objects):
            return
        self._watching = None
        self._watched_step = None
        self._before_step = None
        self._kept = None
        self._undo_depth = 0
        if self._failed is not None:
            # Nach der Reparatur rechnet derselbe Schritt: Der Entwurf geht.
            self._failed = None
            self.close()
        made = outputs[0]
        self.view.object_tree.select_object(made)
        entry = result.scene.objects[made]
        if op == EXTRUDE_OP:
            candidates = _overlapped(
                entry, [result.scene.objects[key] for key in before if key in result.scene.objects]
            )
            if candidates:
                self._check_overlap(entry, candidates)
        elif op == POCKET_OP and (pieces := _pieces(entry)) > 1:
            label = str(entry.name or name or made)
            self.view.announce(
                tr("{name} besteht jetzt aus {count} Teilen.").format(name=label, count=pieces)
            )
            split = REGISTRY.get("split_bodies")
            self.view.offer_after_drawing([(str(split.title), split.name, (made,))])

    # --- F-i: die Boolesche Rechnung des neuen Schritts scheitert -------------------

    def _come_back_failed(self, step: int, result: Any) -> None:
        """Der Entwurf kommt zurück ins Bild, die Leiste nennt Ursache und Auswege (F-i)."""
        kept = self._kept
        if kept is None:
            return
        finding = next(
            (
                entry
                for entry in result.scene.report.findings
                if entry.op_id == step and entry.severity == "error"
            ),
            None,
        )
        self._failed = (step, finding)
        draft, lift, origin, intent = kept
        if self.draft is None:
            self.view.open_draw_bar()
            self.draft = draft
            self.free = False
            self._unknown = None
            self.intent = intent
            self.origin = origin
            self._begin()
            self.view._show_invitation()
        self.lift = lift
        self._show_failure()

    def _show_failure(self) -> None:
        """Die Ursache mit Stellenzahl in der Leiste, dazu Reparieren und Stellen zeigen."""
        from app.core.errors import REPAIR_AND_RETRY, SHOW_LOCATIONS
        from app.core.scene.history import repair_is_available

        failed = self._failed
        draft = self.draft
        if failed is None or draft is None:
            return
        step, finding = failed
        cause = str(finding.message) if finding is not None else ""
        places = _places(finding)
        text = (
            tr("Der Schritt hält an: {cause} Betroffen sind {count} Stellen.").format(
                cause=cause, count=places
            )
            if places
            else tr("Der Schritt hält an: {cause}").format(cause=cause)
        )
        offered = {action.id for action in finding.suggestions} if finding is not None else set()
        result = self.view.session.last_result
        body = draft.surface.body if draft.surface is not None else None
        repair = REPAIR_AND_RETRY.id in offered and repair_is_available(
            self.view.session.project.document,
            stopped_at=result.stopped_at if result is not None else None,
            op_id=step,
            object_id=finding.object_id if finding is not None else None,
            live_objects=frozenset(result.scene.objects) if result is not None else None,
        )
        shown = body is not None and SHOW_LOCATIONS.id in offered
        self.bar.show_failure(str(text), repair=repair, places=shown)
        self.view.announce(str(text))
        self._show()

    def _repair_failed(self) -> None:
        """*Reparieren und erneut versuchen*: derselbe Schritt rechnet ohne neuen Klick."""
        failed = self._failed
        kept = self._kept
        if failed is None or kept is None:
            return
        step, _finding = failed
        before = self.view.session.last_result
        if not self.view.session.repair_and_retry(step):
            return
        self._undo_depth += 1
        operations = self.view.session.project.document.ops
        draft = kept[0]
        name = draft.surface.name if draft.surface is not None else ""
        known = frozenset(before.scene.objects) if before is not None else frozenset()
        self._watching = (tuple(operations[-1].outputs), operations[-1].op, known, name)
        self._watched_step = operations[-1].id
        self._before_step = before
        self.bar.show_failure(
            str(tr("Wird repariert und neu gerechnet …")), repair=False, places=False
        )

    def _show_failed_places(self) -> None:
        """*Stellen zeigen*: Der Schritt bleibt, wie er ist, die Karte zeigt die Stellen."""
        draft = self.draft
        body = draft.surface.body if draft is not None and draft.surface is not None else None
        self._kept = None
        self._undo_depth = 0
        self.close()
        if body is not None:
            self.view.show_places_of(body)

    def _abandon_failed(self, *, keep_draft: bool) -> None:
        """Den gescheiterten Schritt zurücknehmen — samt seinen Reparaturen, nichts Fremdes.

        Strg+Z (``keep_draft``) lässt den Entwurf mit seiner Höhe stehen; Escape
        legt den Umriss ab wie nach H2, und Strg+Z holt ihn in den Editor.
        """
        draft = self.draft
        for _turn in range(self._undo_depth):
            self.view.session.undo()
        self._undo_depth = 0
        self._failed = None
        self._kept = None
        self._watching = None
        self._watched_step = None
        if draft is None:
            return
        if keep_draft:
            self._refresh()
            return
        drawing = draft.outline if draft.outline is not None else draft.sketch()
        origin = self.origin
        if origin is None and draft.surface is not None:
            origin = self.view.outline_origin(draft.surface)
        self.close()
        if drawing is not None and origin is not None:
            self.view.return_the_outline(origin, sketch_to_text(drawing), now=False)

    def _check_overlap(self, made: Any, candidates: list[Any]) -> None:
        """F-g: die echte Schnittmenge im Arbeiter; der Satz kommt erst mit ihr."""
        self.cancel_overlap()
        worker = _OverlapWorker(
            _private_body(made.mesh),
            [(other.id, _private_body(other.mesh)) for other in candidates],
        )
        names = {other.id: str(other.name or other.id) for other in candidates}
        generation = self.view.session.project_generation
        made_id = made.id

        def arrived(found: Any) -> None:
            if self._overlap is worker:
                self._overlap = None
            if found is None or worker.cancelled.is_cancelled:
                return
            result = self.view.session.last_result
            if (
                self.view.session.project_generation != generation
                or result is None
                or made_id not in result.scene.objects
                or found not in result.scene.objects
            ):
                return
            self.view.announce(
                tr("Der neue Körper überdeckt {name}.").format(name=names.get(found, found))
            )
            self.view.offer_after_drawing(
                [
                    (str(REGISTRY.get("union_objects").title), "union_objects", (found, made_id)),
                    (str(tr("Davon abziehen")), "subtract_objects", (found, made_id)),
                ]
            )

        worker.done.connect(arrived)
        worker.crashed.connect(lambda _detail: None)
        self._overlap = worker
        self.view._leash.start(worker)

    def cancel_overlap(self) -> None:
        """Eine laufende Überdeckungsprüfung gilt nicht mehr."""
        worker = self._overlap
        self._overlap = None
        if worker is not None:
            worker.cancelled.cancel()

    def wait_for_overlap(self, timeout_ms: int = 30_000) -> bool:
        """Für Prüfstände: warten, bis die Überdeckung entschieden und zugestellt ist."""
        from PySide6.QtCore import QCoreApplication

        worker = self._overlap
        if worker is None:
            return True
        done = worker.wait(timeout_ms)
        QCoreApplication.processEvents()
        return bool(done)

    def _drop_a_lost_target(self, result: Any) -> None:
        """F-k: Verschwindet das Ziel während des Entwurfs, fällt der Entwurf mit Satz."""
        draft = self.draft
        if draft is None or draft.surface is None or draft.surface.body is None:
            return
        if draft.surface.body in result.scene.objects:
            return
        if draft.outline is not None:
            # Der Umriss bleibt für Strg+Z, wie nach Escape (H2).
            self.discard()
            return
        else:
            draft.surface = None
            draft.first = None
            draft.second = None
            self.lift = None
            self._refresh()
        self.view.announce(tr("Der Körper ist nicht mehr da. Der Entwurf ist verworfen."))

    def resume_after_recognition(self, result: Any) -> None:
        """Nach der Erkennung weiter mit Klick 1 an derselben Stelle (F-b)."""
        resume = self._resume_at
        recognising = self.view._local_features
        if resume is None or result is None or (recognising is not None and recognising.active):
            return
        # Ein Versuch, und nur nach der Erkennung: Danach gilt die Stelle nicht mehr.
        self._resume_at = None
        object_id, point, free = resume
        entry = result.scene.objects.get(object_id)
        feature = _face_at(entry, point) if entry is not None else None
        if entry is None or feature is None:
            return
        surface = face_surface(entry, feature)
        if surface is None:
            return
        self.view.start_drawing()
        if self.draft is not None:
            # *Freie Form …* gilt weiter, und Platte 2 steht versetzt (G4).
            self.free = free
            shift = self.viewport.view_offset_of(surface.body)
            start = self._snap(to_plane(surface.frame, point), surface)
            self.take(("face", surface, start, shift))

    def _recognise_here(self) -> None:
        unknown = self._unknown
        if unknown is None:
            return
        self._resume_at = (unknown[0], unknown[1], self.free)
        self.close()
        flow = self.view.local_features()
        flow.begin(unknown)
        if flow.dialog is not None:
            flow.dialog.finished.connect(self._recognition_closed)
        else:
            self._resume_at = None

    def _recognition_closed(self, code: int) -> None:
        """Abgebrochen heißt: Die Stelle gilt nicht mehr, kein späteres Bild öffnet das Werkzeug."""
        from PySide6.QtWidgets import QDialog

        if code != QDialog.DialogCode.Accepted:
            self._resume_at = None

    # --- Rechnung zwischen Bild und Ebene -----------------------------------------

    def _target_at(self, x: int, y: int) -> tuple[str, Any, Any, Any] | None:
        """Was unter dem Zeiger liegt: ``face``, ``bed``, ``curved``, ``unknown`` — oder nichts."""
        hit = self.viewport.surface_under(x, y)
        result = self.view.session.last_result
        if hit is not None and result is not None:
            object_id, scene_point, view_point, feature_id = hit
            entry = result.scene.objects.get(object_id)
            shift = _minus(view_point, scene_point)
            if entry is not None and feature_id is not None:
                surface = face_surface(entry, feature_id)
                if surface is not None:
                    point = self._snap(to_plane(surface.frame, scene_point), surface)
                    return ("face", surface, point, shift)
                return ("curved", None, None, None)
            if entry is not None and entry.kind == "mesh":
                placed = self.viewport.placement_hit(x, y)
                if placed is not None:
                    return ("unknown", placed, None, None)
            return ("curved", None, None, None)
        bed = self.viewport.bed_point_at(x, y)
        if bed is None:
            return None
        scene, view = bed
        surface = bed_surface()
        shift = _minus(view, scene)
        return ("bed", surface, self._snap((scene[0], scene[1]), surface), shift)

    def _look(self) -> None:
        """Phase 0: die Fläche unter dem ruhenden Zeiger aufleuchten lassen."""
        draft = self.draft
        if draft is None or draft.phase != 0 or self._last is None:
            return
        target = self._target_at(*self._last)
        self._hover = None
        self._hover_face = None
        if target is not None and target[0] in ("face", "bed"):
            _kind, surface, point, shift = target
            self._hover = (surface, point, shift)
            if target[0] == "face":
                self._hover_face = self._face_patch(surface)
        self._show()

    def _face_patch(self, surface: DrawSurface) -> tuple[Any, Any] | None:
        """Füllung und Umriss der Fläche, die aufleuchtet — aus dem Anzeigenetz des Körpers.

        Füllung **und** Umriss: Eine Tönung allein ist Farbe (Regel 18). Welche
        Dreiecke gelten, fragt dieselbe Stelle wie die Merkmalsmarkierung
        (``Viewport._face_indices``).
        """
        result = self.view.session.last_result
        if result is None or surface.body is None:
            return None
        entry = result.scene.objects.get(surface.body)
        if entry is None:
            return None
        _object, feature_id = feature_plane_parts(surface.plane)
        chosen = self.viewport._face_indices(surface.body, feature_id)
        raw = getattr(entry.mesh, "raw", None)
        if raw is None or not chosen:
            return None
        import numpy as np

        faces = np.asarray(raw.faces)[list(chosen)]
        patch = (np.asarray(raw.vertices, dtype=float), faces)
        return patch, face_outline(entry.mesh, chosen)

    def _plane_point(self, x: int, y: int) -> Point2 | None:
        draft = self.draft
        ray = self.viewport.ray_at(x, y)
        if draft is None or draft.surface is None or ray is None:
            return None
        return ray_hit(draft.surface.frame, _minus(ray[0], draft.shift), ray[1])

    def _height_at(self, x: int, y: int) -> float | None:
        """Das Rohmaß entlang der Normalen: über die Achse, steil gesehen über die Maus."""
        draft = self.draft
        if draft is None or draft.surface is None:
            return None
        frame = draft.surface.frame
        view = self.viewport.view_direction()
        along = abs(sum(a * b for a, b in zip(view, frame.normal, strict=True)))
        steep = along >= math.cos(math.radians(STEEP_DEGREES))
        if not steep:
            ray = self.viewport.ray_at(x, y)
            base = _centre_of(draft)
            if ray is not None and base is not None:
                reach = axis_hit(frame, base, _minus(ray[0], draft.shift), ray[1])
                if reach is not None:
                    return reach
        if self._steep_from is None:
            self._steep_from = y
        scale = self.viewport.pixels_per_mm(frame)
        if scale <= EPS_GEOM:
            return None
        return (self._steep_from - y) / scale

    def _step(self, frame: PlaneFrame) -> float:
        from app.ui.sketch_editor import grid_step_for

        return grid_step_for(self.viewport.pixels_per_mm(frame))

    def _snap(self, point: Point2, surface: DrawSurface) -> Point2:
        scale = self.viewport.pixels_per_mm(surface.frame)
        reach = (
            MARK_REACH_PIXELS * self.viewport._device_ratio() / scale if scale > EPS_GEOM else 0.0
        )
        return snapped(point, self._step(surface.frame), surface.marks, reach)

    def _limits(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return height_limits(), depth_limits()

    def _accepts(self, index: int, value: float, limits: tuple[float, float]) -> bool:
        least, most = limits
        if value < least or (most > least and value > most):
            above = most > least and value > most
            limit = length(most if above else least)
            self.entry.refuse(index, limit_sentence(length(value), limit, above=above))
            self.view.announce(limit_sentence(length(value), limit, above=above))
            return False
        return True

    def _commit_entry(self) -> None:
        self.type_values(self.entry.values())

    def _refocus(self) -> None:
        widget = getattr(self.viewport.renderer, "widget", None)
        if widget is not None:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)

    # --- Bild und Leiste ----------------------------------------------------------

    def _refresh(self) -> None:
        draft = self.draft
        if draft is None:
            return
        self.bar.show_state(
            sentence(draft, free=self.free, inward=self.inward_first),
            draft.shape,
            shaping=draft.phase < 2 and draft.outline is None,
            recognise=self._unknown is not None,
        )
        self.view.drawing_changed()
        self._show()

    def _show(self) -> None:
        """Den Entwurf ins Bild — in Phase 0 die Fläche unter dem Zeiger samt Fangmarke."""
        draft = self.draft
        if draft is None:
            self.viewport.clear_draw()
            return
        from app.ui.viewport import sketch_cursor

        if draft.phase == 0:
            hover = self._hover
            if hover is None:
                self.viewport.clear_draw()
                return
            surface, point, shift = hover
            size = self._mark_size(surface.frame)
            marks = sketch_cursor(surface.frame, point, size)
            patch, outline = self._hover_face or (None, ())
            self.viewport.show_draw([*marks, *outline], patch=patch, shift=shift)
            return
        shown = picture(draft, self.pointer_at, self.lift)
        solid = list(shown.solid)
        if shown.mark is not None and self.pointer_at is not None and draft.surface is not None:
            solid.extend(
                sketch_cursor(
                    draft.surface.frame, self.pointer_at, self._mark_size(draft.surface.frame)
                )
            )
        self.viewport.show_draw(
            solid, shown.dashed, shown.labels, inward=shown.inward, shift=draft.shift
        )

    def _mark_size(self, frame: PlaneFrame) -> float:
        from app.ui.viewport import CURSOR_PIXELS

        scale = self.viewport.pixels_per_mm(frame)
        return self.viewport._device_ratio() * CURSOR_PIXELS / max(scale, EPS_GEOM)

    # --- Tasten -------------------------------------------------------------------

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        """R, C, Ziffern und die Eingabetaste gehören dem Entwurf, solange er läuft."""
        if stop_watching_the_dying(self, watched, event):
            if watched is self._filtered:
                self._filtered = None
            return False
        if self.draft is None:
            return False
        kind = event.type()
        if kind not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return False
        text = str(event.text()).upper()
        key = event.key()
        ours = (
            text in SHAPE_KEYS
            or (text[:1].isdigit() or text in ("-", ",", "."))
            or key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        )
        if not ours:
            return False
        if kind == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if text in SHAPE_KEYS:
            self.choose(SHAPE_KEYS[text])
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.press_enter()
            return True
        return self.type_first(str(event.text()))


def _minus(
    point: tuple[float, float, float], shift: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Ein Ansichtspunkt in der Szene: der Versatz des Bildes abgezogen."""
    return (point[0] - shift[0], point[1] - shift[1], point[2] - shift[2])


def _centre_of(draft: DrawDraft) -> Point2 | None:
    """Die Mitte des Umrisses — durch sie läuft die Achse der Höhe."""
    drawing = draft.sketch()
    if drawing is None:
        return None
    points = [point for element in drawing.elements for point in element.points]
    if draft.shape == "circle" and draft.outline is None and draft.first is not None:
        return draft.first
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _face_at(entry: Any, point: tuple[float, float, float]) -> str | None:
    """Die ebene Fläche, deren Dreiecke ``point`` tragen — die nächste, wenn mehrere es tun.

    Gefragt wird der Abstand zu den Dreiecken der Fläche, nicht zu ihrer
    Ebene: Zwei gleich hohe Deckflächen teilen die Ebene, aber nur eine trägt
    den Punkt (F-b, Abnahme 10).
    """
    raw = getattr(entry.mesh, "raw", None)
    if raw is None:
        return None
    from collections.abc import Callable

    import numpy as np
    from trimesh.triangles import closest_point

    nearest_of: Callable[[Any, Any], Any] = closest_point

    faces = np.asarray(raw.faces)
    vertices = np.asarray(raw.vertices, dtype=float)
    low, high = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
    reach = max(EPS_GEOM, FACE_GAP_SHARE * math.dist(low, high))
    best: tuple[float, str] | None = None
    for key, feature in entry.features.items():
        if feature.kind != "face" or feature.params.get("normal") is None:
            continue
        chosen = [index for index in feature.face_indices if 0 <= index < len(faces)]
        if not chosen:
            continue
        triangles = vertices[faces[chosen]]
        nearest = nearest_of(triangles, np.repeat([point], len(chosen), axis=0))
        gap = float(np.min(np.linalg.norm(nearest - np.asarray(point), axis=1)))
        if gap <= reach and (best is None or gap < best[0]):
            best = (gap, key)
    return best[1] if best is not None else None


def _private_body(mesh: Any) -> Any:
    """Eine eigene Kopie für den Überdeckungsarbeiter (N3) — exakt bleibt exakt.

    Gebildet im Hauptfaden: Eine Kopie, die selbst schon nebenläufig liest,
    verschöbe nur das Problem (``placement_flow.for_a_worker``).
    """
    from app.core.brep.kernel import Solid
    from app.core.geom.mesh import as_mesh_data

    if isinstance(mesh, Solid):
        return Solid(mesh.shape, deflection=mesh.deflection)
    source = as_mesh_data(mesh)
    return source.replacing(source.raw.copy())


def _places(finding: Any) -> int:
    """Wie viele Stellen ein Befund nennt — offene Kanten, Löcher oder eine Anzahl."""
    if finding is None:
        return 0
    for key in ("open_edges", "holes", "places", "count"):
        # Die Auswertung legt die Werte eines Fehlers als Text ab.
        try:
            value = int(float(str(finding.values.get(key, ""))))
        except ValueError:
            continue
        if value > 0:
            return value
    return 0


def _overlapped(entry: Any, others: list[Any]) -> list[Any]:
    """Die anderen Körper, deren Hülle die des neuen mit Volumen schneidet — der Vorfilter (F-g).

    Ob sie sich wirklich überdecken, entscheidet :class:`_OverlapWorker`.
    """
    box = entry.mesh.bounds
    found: list[Any] = []
    for other in others:
        if other.id == entry.id:
            continue
        theirs = other.mesh.bounds
        overlap = [
            min(box.maximum[axis], theirs.maximum[axis])
            - max(box.minimum[axis], theirs.minimum[axis])
            for axis in range(3)
        ]
        if all(amount > EPS_GEOM for amount in overlap):
            found.append(other)
    return found


def _pieces(entry: Any) -> int:
    """Wie viele Stücke ein Körper hat — exakt über den Kern, am Netz über die Fakten."""
    from app.core.brep.kernel import Solid
    from app.ui.labels import body_facts

    mesh = entry.mesh
    if isinstance(mesh, Solid):
        return int(mesh.solid_count)
    pieces = body_facts(entry).pieces
    return int(pieces or 1)
