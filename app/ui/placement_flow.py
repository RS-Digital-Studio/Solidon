"""Werte eingeben, auf eine Fläche zeigen und einen einzelnen Schritt übernehmen.

Die Oberfläche hält ausschließlich eine vergängliche Raumlage. Bezugskanten,
Abstände und Werkzeugkörper berechnet der Kern; die vorhandene Operation
bleibt der einzige Weg ins Dokument.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import pairwise, product
from typing import Any, Final, Protocol, cast, runtime_checkable

import numpy as np
from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSignalBlocker,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QPolygonF
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.core import expressions
from app.core.errors import AppError, ValidationError
from app.core.geom.mesh import as_mesh_data, ray_hit_distances
from app.core.geom.transform import snap_to_marks
from app.core.knowledge.parts.ops import depth_field, normal_fields, placement_fields
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.scene import placement
from app.core.sketch.profile import strictly_crossing
from app.core.types import Feature, SceneObject, Vec3
from app.core.units import EPS_GEOM
from app.i18n import tr
from app.ui.icons import icon
from app.ui.labels import LengthSpin, feature_name, length, wheel_needs_focus
from app.ui.leash import stop_watching_the_dying
from app.ui.palette import DIFF_PALETTES
from app.ui.render.api import Item, PointerEvent, Renderer, SurfaceStyle
from app.ui.style import NORMAL, ROOMY, SPACE

#: Wie nah der Zeiger einer Marke kommen muss, damit sie ihn hält — in
#: Bildpunkten, wie jede Fangweite der Oberfläche (siehe ansicht.md,
#: "Die Fangweite gehört in Bildpunkte").
SNAP_PIXELS = 12.0

#: Die flachste Tiefe, auf die der Zug fallen darf. **Nicht null**, denn dort
#: kippt die Bedeutung: ``depth = 0`` heißt „durch das ganze Teil" (siehe das
#: Schema von ``drill_hole``). Wer nach oben zieht, um flacher zu werden, führe
#: sonst am Ende des Wegs geradewegs hindurch. Ein Zehntelmillimeter ist unter
#: jeder Schichthöhe und damit ohne eigene Wirkung; die Null bleibt über das
#: Maßfeld erreichbar, wo sie ausgeschrieben dasteht.
LEAST_DEPTH_MM = 0.1

_log = get_logger(__name__)


#: Der Eintrag „Im Modell wählen“ in der Bezugsauswahl trägt diesen Wert statt
#: einer Kante — ein Zeichen für den Code, kein Text für den Nutzer.
_PICK_IN_MODEL: Final = "pick"


@runtime_checkable
class PlacementHost(Protocol):
    """Woran eine Platzierung hängt — und das ist weniger als ein Dialog.

    `PlacementFlow` war an einen `OperationDialog` gebunden: Er war sein
    Qt-Elternteil, lieferte die Werte, nahm sie zurück und führte am Ende die
    Operation aus. Am gewählten Merkmal soll kein Dialog mehr aufgehen — seine
    Zahlen stehen schon im Merkmalfenster (Robert, 11.09.2026: „werte im
    dialog und in der rechten merkmalleiste doppelt, sehr verwirrend für den
    Kunden").

    **Der Vertrag ist erhoben, nicht entworfen.** Er zählt genau die Member
    auf, die der Fluss am 11.09.2026 tatsächlich ansprach; die Namen bleiben
    die des Dialogs, damit der Rebind mechanisch wird und kein Aufrufer
    umdenken muss.

    Die vier Fensterfragen (`show`, `raise_`, `activateWindow`, `isVisible`)
    gehören dazu, obwohl ein Träger ohne Fenster sie leer beantwortet: Sie
    sind der Rückweg aus der Platzierung (:meth:`PlacementFlow.back`), und
    wer sie wegließe, müsste ihn an vier Stellen mit Fallunterscheidungen
    pflastern.

    **Aus demselben Grund steht `show_placement_hint` hier** und nicht hinter
    einem `getattr`. Nur der Dialog trägt den Satz; der stille Träger
    beantwortet die Frage leer. Eine Frage nach der Methode statt nach dem
    Vertrag sieht aus wie Vorsicht und ist eine Lücke: Sie geht an mypy
    vorbei, und ein Tippfehler im Namen bliebe für immer still (Fund der
    Durchsicht, 18.09.2026).
    """

    surfaceRequested: Any
    valuesChanged: Any
    finished: Any

    values_stand_elsewhere: bool
    """Ob die Werte dieses Trägers schon woanders zu sehen sind.

    Entscheidet über die **Leiste** unten im Bild: Sie trägt Hinweis, „Werte
    bearbeiten" und „Position übernehmen" — alles drei Dinge, die am
    gewählten Merkmal rechts im Merkmalfenster stehen, samt einem eigenen
    Übernehmen (Robert, 11.09.2026: „auch 2 mal übernehmen einmal unten und
    einmal rechts … die untere leiste uns sparen und nur die rechte
    verwenden"). Beim Dialog ist sie die einzige Bedienstelle im Bild und
    bleibt."""

    def values(self) -> Mapping[str, Any]: ...

    def take_placement(self, values: Mapping[str, Any]) -> None: ...

    preview_required: bool
    """Ob Übernehmen erst nach der aktuell angezeigten Vorschau erlaubt ist."""
    requires_displayed_preview: bool
    """Ob dieser Eingabeweg unabhängig von der Körperart eine Vorschau verlangt."""
    preview_check: Callable[[], bool] | None
    preview_defer: Callable[[], None] | None
    """Ein Klick auf Übernehmen **vor** der Vorschau wartet auf sie.

    ``can_accept`` verneint, solange die erwartete Vorschau nicht steht; ohne
    diesen Haken ging der Klick stumm verloren, und wer nach dem Tippen sofort
    übernahm, musste ein zweites Mal klicken (Review Fenster, 22.09.2026).
    Das Fenster hängt hier den wartenden Klick an die Freigabe
    (``_PreviewApproval.pending_click``); ``None`` heißt: kein Warten."""

    def block_apply(self, reason: str | None) -> None: ...

    def can_accept(self) -> bool: ...

    def accept(self) -> None: ...

    def show(self) -> None: ...

    def raise_(self) -> None: ...

    def activateWindow(self) -> None: ...  # noqa: N802 — Qt-Name

    def isVisible(self) -> bool: ...  # noqa: N802 — Qt-Name

    def show_placement_hint(self, on: bool, *, paused: bool = False) -> None: ...


class QuietHost(QObject):
    """Ein Träger ohne Fenster — die Platzierung allein im Bild.

    Er erfüllt :class:`PlacementHost` und zeigt nichts: Die Werte hält er
    selbst, das Übernehmen reicht er an einen Rückruf weiter. Gedacht für das
    **gewählte Merkmal**, wo die Zahlen rechts im Merkmalfenster stehen und
    ein Dialog daneben sie ein zweites Mal zeigte.

    **Sichtbar ist er nie**, und die vier Fensterfragen sagen das auch so:
    ``isVisible()`` bleibt falsch, die drei anderen tun nichts. Ein Träger,
    der auf ``show()`` doch etwas zeigte, wäre der Dialog unter neuem Namen.
    """

    surfaceRequested = Signal()
    valuesChanged = Signal()
    finished = Signal(int)
    editStarted = Signal()
    commitStarted = Signal()
    commitFinished = Signal(bool)
    applyStateChanged = Signal()
    cancelled = Signal()
    """Nach :meth:`cancel` — der Kunde hat *Abbrechen* gedrückt, nicht Escape."""

    values_stand_elsewhere = True
    """Sie stehen im Merkmalfenster — deshalb gibt es ihn überhaupt."""

    preview_required = False
    requires_displayed_preview = False

    def __init__(
        self,
        values: Mapping[str, Any],
        accepted: Callable[[Mapping[str, Any]], bool],
        parent: QObject | None = None,
        *,
        known: Iterable[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._values = dict(values)
        self._accepted = accepted
        self.begun = False
        self.committing = False
        self._finished = False
        self._blocked_reason: str | None = None
        self.preview_check: Callable[[], bool] | None = None
        self.preview_defer: Callable[[], None] | None = None
        self._known = frozenset(known) if known is not None else None
        """Welche Namen die Operation kennt — oder ``None`` für alle.

        **Der Dialog filterte das zufällig mit.** ``take_placement`` setzt dort
        nur Editoren, und für einen Namen ohne Feld gibt es keinen; was die
        Platzierung darüber hinaus zurückgab, fiel still weg. Ein Träger, der
        alles annimmt, reicht es weiter — und die Operation lehnt mit „Diesen
        Parameter gibt es bei dieser Operation nicht" ab, gemessen am
        11.09.2026 an ``resize_hole`` und den Normalenfeldern ``nx``/``ny``/
        ``nz`` (die Absage landete offscreen in einem modalen Dialog, und der
        Lauf stand)."""

    def values(self) -> Mapping[str, Any]:
        return dict(self._values)

    def begin_edit(self) -> None:
        """Die erste echte Feld- oder Griffbetätigung bindet den Entwurf."""
        if self.begun or self.committing or self._finished:
            return
        self.begun = True
        self.editStarted.emit()

    def take_placement(self, values: Mapping[str, Any]) -> None:
        """Ort und Maße zurück in den Träger — und die Runde ist gemeldet.

        Geänderte Werte lösen ``valuesChanged`` aus; daran hängen Vorschau
        und Maßlinien. Identische Werte lassen die Vorschaufreigabe stehen.
        **Und dieselbe Grenze:**
        Was die Operation nicht kennt, kommt nicht herein (:attr:`_known`).
        """
        accepted = (
            values
            if self._known is None
            else {name: value for name, value in values.items() if name in self._known}
        )
        updated = {**self._values, **accepted}
        if updated == self._values:
            return
        self._values = updated
        self.valuesChanged.emit()

    def block_apply(self, reason: str | None) -> None:
        """Übernahme sperren oder freigeben; die Vorschau verwaltet das Fenster."""
        if reason == self._blocked_reason:
            return
        self._blocked_reason = reason
        self.applyStateChanged.emit()

    @property
    def blocked_reason(self) -> str | None:
        """Der gesetzte Sperrgrund, ohne eine neue Vorschauprüfung auszulösen."""
        return self._blocked_reason

    def can_accept(self) -> bool:
        """Ob der Träger die aktuellen Werte übernehmen darf."""
        if self._finished or self.committing:
            return False
        current = self.preview_check is None or self.preview_check()
        return current and self._blocked_reason is None

    def accept(self) -> None:
        """Die Platzierung ist übernommen — was daraus wird, weiß der Rückruf.

        **Der Träger führt nichts aus.** Er kennt weder Register noch Sitzung;
        die Operation legt an, wer ihn gebaut hat. Ohne diese Trennung wäre er
        eine zweite Stelle, an der Schritte entstehen (Regel 2).
        """
        if not self.can_accept():
            return
        succeeded = False
        self.committing = True
        self.commitStarted.emit()
        try:
            succeeded = self._accepted(self.values())
        finally:
            self.committing = False
            self.commitFinished.emit(succeeded)
        if not succeeded or self._finished:
            return
        self._finished = True
        self.begun = False
        # Dieselbe Zahl, die ein angenommener `QDialog` sendet — wer an
        # `finished` hängt, soll den Träger nicht am Code erkennen müssen.
        self.finished.emit(int(QDialog.DialogCode.Accepted))

    def reject(self) -> None:
        """Escape oder Abbrechen verwirft den Entwurf genau einmal."""
        if self._finished:
            return
        self._finished = True
        self.begun = False
        self.finished.emit(int(QDialog.DialogCode.Rejected))

    def cancel(self) -> None:
        """*Abbrechen*: verwirft wie :meth:`reject` und sagt es danach eigens.

        ``cancelled`` kommt nach ``finished``: Wer den Träger gebaut hat,
        räumt ihn zuerst ab und entscheidet dann, was aus der Auswahl wird.
        Escape in der Maßgruppe kommt ebenfalls hierher
        (``PlacementFlow.step_back``); ein Kontextwechsel geht weiter über
        :meth:`reject`.
        """
        if self._finished:
            return
        self.reject()
        self.cancelled.emit()

    # --- die vier Fensterfragen, alle ohne Fenster --------------------------------

    def show(self) -> None:
        return None

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:  # noqa: N802 — Qt-Name
        return None

    def isVisible(self) -> bool:  # noqa: N802 — Qt-Name
        return False

    def show_placement_hint(self, on: bool, *, paused: bool = False) -> None:
        """Kein Fenster, kein Satz — die Werte stehen rechts im Merkmalfenster."""
        return None


#: Ab welcher Neigung eine Fläche als „nach oben" gilt, wenn ein Baustein von
#: selbst eine sucht (:meth:`PlacementFlow._face_to_seat_on`) — die Normale
#: gegen z; 0,7 ist rund 45 Grad.
UPWARD_FACE: Final = 0.7


def for_a_worker(mesh: Any) -> Any:
    """Eine eigene Kopie eines Szenennetzes für den Nebenthread.

    **Dieselbe Entscheidung wie beim Szenenarbeiter** (``viewport._detached``,
    12.09.2026): Solange der Arbeiter rechnet, bleibt die Auswertung stehen,
    und der Hauptthread liest an **demselben** ``MeshData`` weiter — Hüllquader
    beim Zeigerhalt, Dreiecke beim Merkmalsfleck, Kanten beim Klick.
    ``prepare_surface``, ``seat_of`` und ``original_surface_hit`` füllen dabei
    im Nebenthread dieselben trägen trimesh-Caches (Flächennormalen,
    Dreiecke, Nachbarschaft). Der Cache ist nicht threadsicher.

    Kopiert wird **hier**, im Hauptthread, und nicht im Arbeiter: Eine Kopie,
    die selbst schon nebenläufig liest, verschöbe das Problem nur. Gemessen am
    13.09.2026: 0,20 ms bei 3372 Dreiecken.

    Ein exakter Körper gibt seine Anzeigetessellation ab — genau das tat der
    Aufruf ``as_mesh_data(entry.mesh)`` vorher an dieser Stelle auch, nur eben
    im falschen Thread.
    """
    source = as_mesh_data(mesh)
    return source.replacing(source.raw.copy())


def starts_by_itself(spec: OperationSpec) -> bool:
    """Ob dieser Dialog von selbst in die Platzierung geht.

    **Wer eine Fläche braucht, bekommt sie sofort** — ein Baustein, eine
    Beschriftung, eine Bohrung sitzen auf etwas, und ein zweiter Klick bot nur
    an, was die Operation ohnehin verlangt (Robert, 09.09.2026: „man soll
    keinen extra Button klicken müssen"). Der Knopf, der das tat, ist am
    11.09.2026 gefallen.

    **Ein Erzeuger braucht keine.** Quader, Zylinder, Kegel, Kugel und Ring
    entstehen aus ihren eigenen Maßen an ihren eigenen Koordinaten; die
    Platzierung ist dort ein Angebot und keine Bedingung. Startet sie von
    selbst, verschwindet der Dialog — und mit ihm Breite, Tiefe und Höhe, die
    nirgends sonst stehen. Wer die Maße ändern wollte, musste Escape drücken,
    tippen und neu platzieren (Robert, 09.09.2026: „wer nur Maße tippen will,
    ignoriert ihn").

    Stattdessen zeigt dort die Live-Vorschau den Körper, sobald der Dialog
    offen ist — sie rechnet ihn ohnehin (``Session.preview_async``), und
    ``OperationDialog.request`` überspringt sie nur, solange die Platzierung
    läuft. Der Knopf bleibt: Wer den Quader auf eine Fläche setzen will,
    findet den Weg an derselben Stelle wie zuvor.

    Gefragt wird nach ``consumes``, nicht nach einer Namensliste: Was nichts
    verbraucht, hat nichts, worauf es sitzen könnte.
    """
    return spec.consumes != 0 or spec.takes_whole_scene


def _grips_its_preview(spec: OperationSpec) -> bool:
    """Ob die Vorschau dieser Operation einen Griff bekommt.

    Genau dort, wo der Dialog offen bleibt und die Live-Vorschau den Körper
    zeigt: an den Erzeugern. Wer in die Platzierung geht, zielt mit dem
    Fadenkreuz — zwei Gesten für dieselbe Stelle wären eine zu viel.

    Und nur, wo es Felder gibt, in die der Zug schreiben kann: ``x/y/z`` für
    den Ort, ``nx/ny/nz`` für die Richtung, ``angle`` für die Drehung. Ein
    Griff über einem Körper, dessen Lage nirgends steht, bewegte ein Bild.
    """
    if starts_by_itself(spec):
        return False
    names = {entry.name for entry in spec.params.spec()}
    return {"x", "y", "z", "nx", "ny", "nz", "angle"} <= names


def _crosses(a: tuple[QPointF, QPointF], b: tuple[QPointF, QPointF]) -> bool:
    """Ob zwei Strecken einander schneiden — echte Kreuzung, keine Berührung.

    Die Rechnung steht im Kern (`profile.strictly_crossing`, mit der Toleranz
    der Skizzenprofile); hier wird nur von ``QPointF`` übersetzt.
    """
    return strictly_crossing(
        (a[0].x(), a[0].y()), (a[1].x(), a[1].y()), (b[0].x(), b[0].y()), (b[1].x(), b[1].y())
    )


def _fits(
    widget: QWidget,
    rect: QRect,
    layout: Mapping[QWidget, QRect],
    bounds: QRect,
    obstacles: Sequence[QRect],
) -> bool:
    """Ob ein Feld an diesem Platz steht: im Bild, keinem Hindernis und keinem
    anderen Feld der Anordnung zu nahe — die eine Prüfung für Platzsuche,
    Stehregel und Entwirren."""
    if not bounds.contains(rect):
        return False
    grown = rect.adjusted(-SPACE, -SPACE, SPACE, SPACE)
    if any(grown.intersects(taken) for taken in obstacles):
        return False
    return not any(grown.intersects(other) for key, other in layout.items() if key is not widget)


def _places_that_still_serve(
    previous: Mapping[QWidget, QRect],
    fresh: Mapping[QWidget, QRect],
    pending: Sequence[tuple[QWidget, QPointF, QPointF]],
    bounds: QRect,
    obstacles: Sequence[QRect],
    ink: Sequence[tuple[QPointF, QPointF]],
) -> dict[QWidget, QRect]:
    """Die Plätze des letzten Aufbaus, die ein Feld behalten darf — je Feld.

    Dasselbe Feld in derselben Größe, im Bild, keinem Hindernis und keinem
    anderen **behaltenen** Feld zu nahe, nicht weiter von seinem Maß entfernt
    als der neue Platz plus :data:`STICKY_FIELDS` Feldhöhen — und nicht über
    einer fremden Maßlinie, wenn der neue Platz frei davon wäre. Entschieden wird je
    Feld: Bis zum 22.09.2026 verwarf ein einziger getroffener Platz alle, und
    dann tauschte das Entwirren (Review: +1,2 mm am Setzpunkt, zwei Felder
    391 und 409 Punkte gesprungen). Die Felder, die nicht bleiben dürfen,
    sucht der Aufbau um die behaltenen herum neu.
    """
    wanted = {widget: want for widget, want, _anchor in pending}
    anchors = {widget: anchor for widget, _want, anchor in pending}
    kept: dict[QWidget, QRect] = {}
    for widget, _want, _anchor in pending:
        rect = previous.get(widget)
        new = fresh.get(widget)
        if rect is None or new is None or rect.size() != new.size():
            continue
        if not _fits(widget, rect, kept, bounds, obstacles):
            continue
        leeway = (QPointF(new.center()) - wanted[widget]).manhattanLength() + (
            STICKY_FIELDS * rect.height()
        )
        if (QPointF(rect.center()) - wanted[widget]).manhattanLength() > leeway:
            continue
        foreign = [
            line
            for line in ink
            if ((line[0] + line[1]) / 2 - anchors[widget]).manhattanLength() > 1.0
        ]
        if not _clear_of_lines(rect, foreign) and _clear_of_lines(new, foreign):
            continue
        kept[widget] = rect
    return kept


def _clear_of_lines(rect: QRect, lines: Sequence[tuple[QPointF, QPointF]]) -> bool:
    """Ob kein Strich der Tinte durch das um ``SPACE`` gewachsene Feld läuft.

    Ein Feld über einer Maßlinie verdeckt, was es beschriftet — und über der
    Verbindung eines anderen, wohin jenes gehört. Geprüft wird die Strecke
    gegen das Rechteck: ein Endpunkt darin, oder ein Schnitt mit einer seiner
    vier Kanten. Gemieden werden die **Maßlinien und Verbindungen**, nicht
    die Bezugskanten und Verlängerungen: Die laufen über die ganze
    Plattenkante, und ein Feld, das breiter ist als der Abstand der Bohrung
    zur Kante, träfe sie an jedem nahen Platz — dann gewann ein ferner freier
    Platz, dreihundert Punkte vom Maß weg (Review 22.09.2026).
    """
    grown = QRectF(rect.adjusted(-SPACE, -SPACE, SPACE, SPACE))
    corners = (
        grown.topLeft(),
        grown.topRight(),
        grown.bottomRight(),
        grown.bottomLeft(),
    )
    edges = tuple(zip(corners, (*corners[1:], corners[0]), strict=True))
    for start, end in lines:
        if grown.contains(start) or grown.contains(end):
            return False
        if any(_crosses((start, end), edge) for edge in edges):
            return False
    return True


def _holds_focus(field: QWidget, focused: QWidget | None) -> bool:
    """Ob das Feld oder eines seiner Kinder (das Eingabefeld der Drehbox) den Fokus hat."""
    return focused is not None and (focused is field or field.isAncestorOf(focused))


def _leaders_of(
    layout: Mapping[QWidget, QRect], pending: Sequence[tuple[QWidget, QPointF, QPointF]]
) -> list[tuple[QPointF, QPointF]]:
    """Die Verbindungen einer Anordnung — von der Feldmitte zum Anker des Maßes."""
    return [
        (QPointF(layout[widget].center()), anchor)
        for widget, _wanted, anchor in pending
        if widget in layout
    ]


def _crossings(
    layout: Mapping[QWidget, QRect], pending: Sequence[tuple[QWidget, QPointF, QPointF]]
) -> int:
    """Wie oft sich die Zuordnungslinien einer Anordnung kreuzen."""
    lines = _leaders_of(layout, pending)
    return sum(
        1
        for index, first in enumerate(lines)
        for second in lines[index + 1 :]
        if _crosses(first, second)
    )


def _untangle(
    positions: dict[QWidget, QRect],
    pending: Sequence[tuple[QWidget, QPointF, QPointF]],
    bounds: QRect,
    obstacles: Sequence[QRect],
) -> None:
    """Zwei Felder tauschen die Plätze, wenn ihre Zuordnungslinien einander kreuzen.

    Robert, 21.09.2026: „aufpassen dass sich die maßlinien nicht kreuzen".
    Die Platzsuche setzt jedes Feld für sich an den nächsten freien Ort; stehen
    mehrere gestapelt neben dem Körper, laufen ihre Linien fächerförmig zu den
    Maßlinien und schneiden sich. Getauscht wird paarweise und nur, wenn beide
    Felder an den fremden Plätzen ins Bild passen, keinem Hindernis und keinem
    dritten Feld zu nahe kommen und danach weniger Kreuzungen stehen — so lange,
    bis kein Tausch mehr etwas bringt. Fünf Felder sind zehn Paare; das kostet
    nichts. Wo die Linie eines Feldes endet, sagt ``pending`` — dieselbe
    Stelle, an der ``redraw`` sie zeichnet, nicht eine zweite Herleitung.
    """
    widgets = [widget for widget, _wanted, _anchor in pending if widget in positions]

    for _round in range(len(widgets) * len(widgets)):
        now = _crossings(positions, pending)
        if now == 0:
            return
        improved = False
        for index, first in enumerate(widgets):
            for second in widgets[index + 1 :]:
                a, b = positions[first], positions[second]
                swapped = dict(positions)
                swapped[first] = QRect(b.topLeft(), a.size())
                swapped[second] = QRect(a.topLeft(), b.size())
                if not _fits(first, swapped[first], swapped, bounds, obstacles) or not _fits(
                    second, swapped[second], swapped, bounds, obstacles
                ):
                    continue
                if _crossings(swapped, pending) < now:
                    positions.update(swapped)
                    improved = True
                    break
            if improved:
                break
        if not improved:
            return


class _Dimensions:
    """Maßtinte im Bildraum — gezeichnet im Renderer vor dem Material.

    Bis zum 21.09.2026 war das ein Qt-Widget über der Renderfläche, das über
    eine Fenstermaske nur seine Linien belegte. Die Maske hatte je schräger
    Linie ein Rechteck je Bildzeile, und bei 1682 Rechtecken verlor der
    Vulkan-Treiber der RTX 4080 das Gerät — „Parent device is lost" im
    nächsten ``submit``, ohne Fehler davor; 1380 liefen, unter D3D12 lief
    alles (RM-198, gemessen an Weg 1, dreimal je Stand). Ein gerastertes
    Ersatzbild kostete eine gestufte graue Unterlage und je Bild vier
    Durchläufe über alle Rechtecke (Robert: „performancetechnisch auch ganz
    schlecht").

    Die Tinte geht seither denselben Weg wie die Merkmalslinien der Ansicht:
    ``renderer.add_lines`` und ``add_surface`` mit ``keep_in_front`` — kein
    Widget, keine Maske, nichts, was ein Treiber zerlegen müsste. Die
    Zahlenfelder bleiben Qt-Fenster und liegen ohnehin über dem Bild.

    Die Listen tragen Bildkoordinaten in logischen Bildpunkten; ``refresh``
    legt sie über ``display_to_world`` auf eine Tiefe vor der Kamera und
    schreibt sie in **acht dauerhafte Elemente** des Renderers — fünf
    Linien (Unterlage, Striche, Zuordnungen, Umriss, das leuchtende Maß) und
    drei Flächen (Markenrand, Pfeile, Marken), jedes mit fester Kapazität
    (``Renderer.add_lines(capacity=…)``). Bis zum 21.09.2026 räumte jeder
    Aufbau zehn Elemente ab und legte zehn neue an; pygfx baut je neuem
    Element eine Pipeline, und das kostete zwölf von zweiundzwanzig
    Millisekunden je Kamerageste, Radraste und Tastendruck in einem Feld
    (Sonde ``measure_ink_churn.py``). Jetzt tauscht ``update_points`` nur die
    Zahlen; neu entstehen die Elemente erst, wenn eine Kapazität reißt — dann
    alle acht zusammen, damit ihre Reihenfolge bleibt.

    Innerhalb der Tinte ist die Reihenfolge die Zeichenreihenfolge — was
    zuerst angelegt wird, liegt unten. Gegen Griff und Knöpfe trägt sie
    ``DRAW_ORDER``: pygfx sortiert die Deckschicht nach Ordnung und dann nach
    dem Abstand des Objektursprungs zur Kamera, und der Ursprung der Tinte
    ist die Welt — ob sie über oder unter einem Knopf läge, hinge sonst davon
    ab, wo die Platte im Bauraum steht.
    """

    #: Wo die Tinte im Tiefenbereich liegt — mitten drin, weit weg von beiden
    #: Klippen; die Tiefenprüfung ist für sie ohnehin aus.
    DEPTH: Final = 0.5
    #: Gestrichelt heißt: so viele Bildpunkte Strich, so viele Lücke.
    DASH: Final = (8.0, 4.0)
    #: Die Marke an beiden Enden einer Zuordnungslinie und ihr Rand.
    MARK: Final = 3.5
    MARK_RIM: Final = 1.5
    #: Unter Griff, Knöpfen und Umriss des Griffs, die bei 0 liegen.
    DRAW_ORDER: Final = -1
    #: Ein Stück Maßlinie, das kürzer ist als sein Pfeil, ist kein Maß mehr.
    LEAST_PIECE: Final = 2 * SPACE
    #: Die Linienelemente in Zeichenreihenfolge, mit Breite und Anfangsplatz
    #: in Punkten. Die Unterlage trägt alle Striche, die Zuordnungen sind
    #: gestrichelt und darum viele kurze Stücke; die Kapazität ist so
    #: bemessen, dass eine gewöhnliche Platzierung nie neu anlegt.
    LINE_ELEMENTS: Final = (
        ("dimension_backdrop", 4.0, 2048),
        ("dimension_lines", 2.0, 256),
        ("dimension_leaders", 1.5, 2048),
        ("dimension_outline", 2.0, 256),
        ("dimension_focus", 3.5, 256),
    )
    #: Die Flächenelemente in Zeichenreihenfolge, mit Anfangsplatz in Ecken —
    #: drei je Dreieck, jede Marke ein Fächer aus vierzehn Dreiecken.
    SURFACE_ELEMENTS: Final = (
        ("dimension_mark_rim", 768),
        ("dimension_arrowheads", 96),
        ("dimension_marks", 768),
    )

    def __init__(self, viewport: QWidget) -> None:
        self._viewport = viewport
        self.lines: list[tuple[QPointF, QPointF]] = []
        self.leaders: list[tuple[QPointF, QPointF]] = []
        self.references: list[tuple[QPointF, QPointF]] = []
        self.extensions: list[tuple[QPointF, QPointF]] = []
        #: Was zum Maß gehört, dessen Feld gerade den Fokus hat — seine
        #: Maßlinie, seine Bezugskante, seine Verbindung —, in der Akzentfarbe
        #: über allem anderen (Robert, 22.09.2026: „ich hab hier auch keine
        #: ahnung wo welcher wert hingeht"). Wer in ein Feld klickt, sieht im
        #: Bild, was er ändert.
        self.focus: list[tuple[QPointF, QPointF]] = []
        #: Der Umriss, mit dem das Werkzeug die Oberfläche trifft — ein
        #: geschlossener Zug in Bildkoordinaten. Bei einer Bohrung der Kreis
        #: ihrer Mündung (Befund Robert, 09.09.2026: „es reicht mir, wenn ich
        #: den Kreis auf der Oberfläche in Orange sehe").
        self.outline: list[QPointF] = []
        #: Seine Farbe. Sie kommt aus derselben Palette wie der abgetragene
        #: Anteil der Vorschau — was hier verschwinden wird, ist dort schon
        #: orange, und zwei Farben für dieselbe Aussage wären eine zu viel.
        self.outline_colour: QColor | None = None
        #: Wo der Bewegungsgriff steht — Mitte und Radius in Bildpunkten. Die
        #: Maßlinien werden dort ausgespart: Sie laufen alle in der Mitte des
        #: Merkmals zusammen, und genau dort sitzen Pfeile und Ringe. Vier
        #: Linien mit Unterlage darüber, und der Griff ist nicht zu sehen und
        #: kaum zu treffen (Robert, 11.09.2026: „das verschieben ist auch schwer
        #: durch die maßlinien zu treffen/sehen"). Der Umriss bleibt: Er zeigt
        #: das Loch, und das gehört unter den Griff.
        self.clearing: tuple[QPointF, float] | None = None
        #: Was zuletzt wirklich gezeichnet wurde: die Striche in
        #: Bildkoordinaten, nach Aussparung und Strichelung — für Tests, die
        #: fragen, wo Tinte liegt, ohne ein Bild aufzunehmen.
        self.segments: list[tuple[QPointF, QPointF]] = []
        #: Die dauerhaften Elemente je Name, ihre Kapazität und ihre Farbe —
        #: leer, bis der erste Aufbau sie anlegt.
        self._items: dict[str, Item] = {}
        self._capacities: dict[str, int] = {
            **{name: capacity for name, _width, capacity in self.LINE_ELEMENTS},
            **dict(self.SURFACE_ELEMENTS),
        }
        self._colours: dict[str, str] = {}
        self._shown = False

    # --- Zustand, wie ihn der Fluss braucht -----------------------------------------

    @property
    def shown(self) -> bool:
        """Ob gerade Tinte im Bild steht."""
        return self._shown

    @property
    def items(self) -> tuple[Item, ...]:
        """Die dauerhaften Elemente in Zeichenreihenfolge — für Tests."""
        return tuple(self._items.values())

    def hide(self) -> None:
        """Alle Elemente ausblenden — sie bleiben im Renderer, die Listen bleiben."""
        for item in self._items.values():
            item.set_visible(False)
        self._shown = False
        self.segments = []

    def dispose(self) -> None:
        """Beim Abbau des Flusses — nichts bleibt im Renderer zurück."""
        self.hide()
        renderer = getattr(self._viewport, "renderer", None)
        if renderer is not None:
            for item in self._items.values():
                renderer.remove(item)
        self._items = {}
        self._colours = {}

    # --- Geometrie in Bildkoordinaten ------------------------------------------------

    @staticmethod
    def _arrowheads(start: QPointF, end: QPointF) -> tuple[QPolygonF, ...]:
        """Beide Pfeilspitzen einer Maßlinie als gefüllte Dreiecke."""
        vector = end - start
        size = math.hypot(vector.x(), vector.y())
        if size < 1.0:
            return ()
        unit = vector / size
        sideways = QPointF(-unit.y(), unit.x())
        heads = []
        for point, direction in ((start, unit), (end, -unit)):
            base = point + direction * (2 * SPACE)
            heads.append(QPolygonF([point, base + sideways * SPACE, base - sideways * SPACE]))
        return tuple(heads)

    @staticmethod
    def _disc(centre: QPointF, radius: float, sides: int = 16) -> QPolygonF:
        return QPolygonF(
            [
                centre
                + QPointF(
                    math.cos(2.0 * math.pi * index / sides) * radius,
                    math.sin(2.0 * math.pi * index / sides) * radius,
                )
                for index in range(sides)
            ]
        )

    def _outside_the_clearing(self, start: QPointF, end: QPointF) -> list[tuple[QPointF, QPointF]]:
        """Das Stück Strecke, das nicht im Griff liegt — ein oder zwei Teile.

        **Eine Strecke, die ganz im Griff läge, kommt ganz.** Die Aussparung
        ist Kosmetik — die Tinte nimmt keinen Klick an —, und ein Maß, dessen
        Linie fehlt, sagt nicht mehr, wohin es geht: Nach dem Zug zum Langloch
        greift der Griff über Knöpfe und Umriss hinaus, und die 10 mm zur
        Außenkante lagen ganz darin (Robert, 21.09.2026: „manche maßlinien
        fehlen aber"). **Und ganz heißt: bis auf einen Pfeil.** Ein Stück
        kürzer als ``LEAST_PIECE`` wäre ein Stummel ohne Pfeil — bei etwas
        anderem Zoom dieselbe Lage —, also kommt auch dann die ganze Linie.
        """
        if self.clearing is None:
            return [(start, end)]
        centre, radius = self.clearing
        vector = end - start
        square = QPointF.dotProduct(vector, vector)
        if square < EPS_GEOM:
            return []
        offset = start - centre
        # |offset + t·vector|² = r² — quadratisch in t
        b = 2.0 * QPointF.dotProduct(offset, vector)
        c = QPointF.dotProduct(offset, offset) - radius * radius
        discriminant = b * b - 4.0 * square * c
        if discriminant <= 0.0:
            return [(start, end)]
        root = math.sqrt(discriminant)
        first = (-b - root) / (2.0 * square)
        second = (-b + root) / (2.0 * square)
        pieces: list[tuple[QPointF, QPointF]] = []
        if first > 0.0:
            pieces.append((start, start + vector * min(first, 1.0)))
        if second < 1.0:
            pieces.append((start + vector * max(second, 0.0), end))
        least = self.LEAST_PIECE * self.LEAST_PIECE
        kept = [
            (head, tail)
            for head, tail in pieces
            if QPointF.dotProduct(tail - head, tail - head) >= least
        ]
        return kept or [(start, end)]

    def _in_the_clearing(self, point: QPointF) -> bool:
        if self.clearing is None:
            return False
        centre, radius = self.clearing
        return math.hypot(point.x() - centre.x(), point.y() - centre.y()) < radius

    @classmethod
    def _dashed(cls, start: QPointF, end: QPointF) -> list[tuple[QPointF, QPointF]]:
        vector = end - start
        length = math.hypot(vector.x(), vector.y())
        if length < 1.0:
            return []
        unit = vector / length
        on, off = cls.DASH
        pieces = []
        at = 0.0
        while at < length:
            stop = min(at + on, length)
            pieces.append((start + unit * at, start + unit * stop))
            at = stop + off
        return pieces

    # --- Zeichnen ---------------------------------------------------------------------

    def refresh(self) -> None:
        """Die Listen in die Elemente des Renderers schreiben.

        Unterlage zuerst, dann die Striche, dann Pfeile und Marken: eine
        helle beziehungsweise dunkle Unterlage hält dieselbe Linie auf dem
        Modell und auf dem Hintergrund lesbar, ohne Farbe als einzige
        Kodierung. Zuordnungslinien sind gestrichelt und tragen an beiden
        Enden eine Marke, Maßlinien sind durchgezogen und tragen Pfeile — so
        bleiben sie ohne Farbe unterscheidbar (Regel 18). Gezeichnet wird
        nach Aussparung des Griffs.
        """
        renderer = cast("Renderer | None", getattr(self._viewport, "renderer", None))
        if renderer is None:
            self.hide()
            return
        solid: list[tuple[QPointF, QPointF]] = []
        heads: list[QPolygonF] = []
        for start, end in self.lines:
            pieces = self._outside_the_clearing(start, end)
            solid.extend(pieces)
            # Eine Linie, die ganz kommt, bringt beide Pfeile mit — auch dort,
            # wo sie im Griff stehen; sonst nur die außerhalb.
            whole = pieces == [(start, end)]
            heads.extend(
                polygon
                for polygon in self._arrowheads(start, end)
                if whole or not self._in_the_clearing(polygon.toList()[0])
            )
        for start, end in self.references:
            solid.extend(self._outside_the_clearing(start, end))
        dashed: list[tuple[QPointF, QPointF]] = []
        for start, end in (*self.leaders, *self.extensions):
            for piece in self._outside_the_clearing(start, end):
                dashed.extend(self._dashed(*piece))
        ring: list[tuple[QPointF, QPointF]] = []
        if len(self.outline) >= 3 and self.outline_colour is not None:
            ring = list(zip(self.outline, [*self.outline[1:], self.outline[0]], strict=True))
        lit: list[tuple[QPointF, QPointF]] = []
        for start, end in self.focus:
            lit.extend(self._outside_the_clearing(start, end))
        marks = [
            point
            for start, end in self.leaders
            for point in (start, end)
            if not self._in_the_clearing(point)
        ]
        self.segments = [*solid, *dashed, *ring]
        if not self.segments and not heads and not marks:
            self.hide()
            return
        # **Drei Aufrufe statt zweitausend.** In einer festen Tiefe ist der
        # Weltpunkt hinter einem Bildpunkt affin in den Bildkoordinaten (die
        # Tiefenebene liegt parallel zum Bild, und dort bildet die Projektion
        # linear ab — `Renderer.display_to_world` sagt das zu); je Punkt die
        # Kameramatrix zu invertieren kostete 15 ms je Aufbau, und der läuft
        # bei jeder Radraste und jedem Tastendruck in einem Feld.
        ratio = renderer.device_ratio()
        step = 256.0
        basis = [
            renderer.display_to_world(x, y, self.DEPTH)
            for x, y in ((0.0, 0.0), (step, 0.0), (0.0, step))
        ]
        if any(point is None for point in basis):
            self.hide()
            return
        origin = np.asarray(basis[0], dtype=np.float64)
        along_x = (np.asarray(basis[1], dtype=np.float64) - origin) / step
        along_y = (np.asarray(basis[2], dtype=np.float64) - origin) / step

        def world_of(points: Sequence[QPointF]) -> np.ndarray:
            if not points:
                return np.zeros((0, 3), dtype=np.float64)
            screen = np.asarray([(point.x(), point.y()) for point in points], dtype=np.float64)
            screen *= ratio
            return origin + screen[:, :1] * along_x + screen[:, 1:] * along_y

        def line_points(segments: Sequence[tuple[QPointF, QPointF]]) -> np.ndarray:
            return world_of([point for start, end in segments for point in (start, end)])

        def corners(polygons: Sequence[QPolygonF]) -> np.ndarray:
            # Jedes Dreieck mit eigenen drei Ecken: So bleibt die Topologie
            # der Fläche fest (Dreieck *k* nutzt die Ecken 3k bis 3k+2), und
            # der Renderer zeichnet genau so viele, wie Ecken kommen.
            flat: list[QPointF] = []
            for polygon in polygons:
                ring_points = polygon.toList()
                for index in range(1, len(ring_points) - 1):
                    flat.extend((ring_points[0], ring_points[index], ring_points[index + 1]))
            return world_of(flat)

        palette = self._viewport.palette()
        colour = palette.text().color().name()
        backdrop = palette.window().color().name()
        outline_colour = self.outline_colour.name() if self.outline_colour is not None else colour
        accent = palette.highlight().color().name()
        wanted: dict[str, tuple[np.ndarray, str]] = {
            "dimension_backdrop": (line_points(self.segments), backdrop),
            "dimension_lines": (line_points(solid), colour),
            "dimension_leaders": (line_points(dashed), colour),
            "dimension_outline": (line_points(ring), outline_colour),
            "dimension_focus": (line_points(lit), accent),
            # Der Rand der Marke kommt nach den Linien: Er deckt das Ende der
            # Zuordnungslinie ab, damit die Marke frei steht und der Strich
            # nicht bis in sie hineinläuft.
            "dimension_mark_rim": (
                corners([self._disc(point, self.MARK + self.MARK_RIM) for point in marks]),
                backdrop,
            ),
            "dimension_arrowheads": (corners(heads), colour),
            "dimension_marks": (corners([self._disc(point, self.MARK) for point in marks]), colour),
        }
        # **Reißt eine Kapazität, entstehen alle sieben neu** — auf das
        # Doppelte des Bedarfs, und in ihrer Reihenfolge: Ein einzelnes neues
        # Element käme im Renderer ans Ende und läge über allem, was nach ihm
        # gedacht war.
        if not self._items or any(
            len(points) > self._capacities[name] for name, (points, _tint) in wanted.items()
        ):
            for name, (points, _tint) in wanted.items():
                self._capacities[name] = max(self._capacities[name], 2 * len(points))
            self._rebuild(renderer, wanted)
        else:
            for name, (points, tint) in wanted.items():
                item = self._items[name]
                if self._colours[name] != tint:
                    item.set_colour(tint)
                    self._colours[name] = tint
                item.update_points(points)
                item.set_visible(len(points) > 0)
        self._shown = True

    def _rebuild(self, renderer: Renderer, wanted: Mapping[str, tuple[np.ndarray, str]]) -> None:
        """Alle Elemente neu anlegen — in Zeichenreihenfolge, mit den heutigen Kapazitäten."""
        for item in self._items.values():
            renderer.remove(item)
        self._items = {}
        self._colours = {}
        for name, width, _capacity in self.LINE_ELEMENTS:
            points, tint = wanted[name]
            self._items[name] = renderer.add_lines(
                points,
                name=name,
                colour=tint,
                width=width,
                keep_in_front=True,
                draw_order=self.DRAW_ORDER,
                capacity=self._capacities[name],
            )
            self._colours[name] = tint
            self._items[name].set_visible(len(points) > 0)
        for name, _capacity in self.SURFACE_ELEMENTS:
            points, tint = wanted[name]
            self._items[name] = self._surface(
                renderer, name, points, tint, capacity=self._capacities[name]
            )
            self._colours[name] = tint
            self._items[name].set_visible(len(points) > 0)

    @classmethod
    def _surface(
        cls, renderer: Renderer, name: str, corners: np.ndarray, tint: str, *, capacity: int
    ) -> Item:
        # Ein Vielfaches von drei — je Dreieck eigene Ecken (``corners``).
        capacity = 3 * max(1, -(-capacity // 3))
        faces = np.arange(capacity, dtype=np.int64).reshape(-1, 3)
        return renderer.add_surface(
            corners,
            faces,
            name=name,
            style=SurfaceStyle(
                colour=tint,
                lighting=False,
                show_edges=False,
                pickable=False,
                keep_in_front=True,
                draw_order=cls.DRAW_ORDER,
            ),
            capacity=capacity,
        )


#: Um wie viel näher ein neuer Platz am Maß liegen muss, bevor ein Maßfeld
#: seinen alten verlässt — in Vielfachen der Feldhöhe (``PlacementFlow``).
STICKY_FIELDS: Final = 2.0


class PlacementFlow(QObject):
    """Eine laufende Platzierung gehört genau einem vorhandenen Träger.

    Der Träger war bis zum 11.09.2026 immer ein `OperationDialog`. Er ist es
    weiterhin, wo eine Operation ihre Werte in einem Dialog erfragt — am
    gewählten Merkmal dagegen stehen sie rechts, und dort trägt ein
    :class:`QuietHost` ohne Fenster. Was der Fluss davon braucht, steht in
    :class:`PlacementHost`.
    """

    def __init__(
        self,
        dialog: PlacementHost,
        window: Any,
        spec_of: Callable[[], Any],
        inputs_of: Callable[[], tuple[str, ...]],
        *,
        change_op: int | None = None,
    ) -> None:
        # Jeder Träger ist ein ``QObject`` — das Protokoll kann es nicht
        # verlangen (ein ``Protocol`` erbt nicht von Qt), also steht es hier.
        super().__init__(cast(QObject, dialog))
        self.dialog = dialog
        self.window = window
        self.viewport = window.viewport
        self.session = window.session
        self.spec_of = spec_of
        self.inputs_of = inputs_of
        self._change_op = change_op
        self._supported = False
        """Ob diese Operation ihre Stelle auf einer Fläche einstellen lässt.

        Die fachliche Hälfte von :meth:`can_place`; ``refresh_available``
        holt sie aus dem Kern. Getrennt geführt, weil sie sich nur mit der
        Operation ändert, die andere Hälfte dagegen mit jeder Auswertung."""
        self._result: Any = None
        self._showing_input = False
        self._epoch = 0
        self.active = False
        self._disposed = False
        self._watched: list[QObject] = []
        self._field_targets: list[QObject] = []
        self._measure_targets: list[QObject] = []
        self._committing_document: Any = None
        self._deferred_document_change = False
        overlay = getattr(window, "overlay", None)
        self._overlay_zones = tuple(
            zone
            for role in ("left", "right", "bottom")
            if isinstance(zone := getattr(overlay, role, None), QWidget)
        )
        for zone in self._overlay_zones:
            self._watch(zone)
        self._serial = 0
        self._pending: tuple[int, int, bool] | None = None
        #: Wo jedes Maßfeld beim letzten Aufbau stand — der Platz bleibt, solange
        #: er frei ist und das Maß nicht weit gewandert ist (``STICKY_FIELDS``).
        self._field_slots: dict[QWidget, QRect] = {}
        self._surface_busy = False
        self._tool_busy = False
        self._tool_again = False
        self._tool: Item | None = None
        self._addition: Item | None = None
        self._tool_context: placement.PlacementTool | None = None
        self._tool_key = ""
        self._prepared: Any = None
        self._prepared_mesh: Any = None
        self._patch_faces: frozenset[int] = frozenset()
        #: Das Szenennetz und seine eine Kopie für die Flächenfrage im
        #: Arbeiter (:meth:`_next_surface`). Die Kopie bleibt, solange das
        #: Netz bleibt: Ihre trägen Merker — Nachbarschaft, Normalen,
        #: Dreiecke — füllt die erste Frage, und jede weitere liest sie.
        self._surface_mesh: tuple[Any, Any] | None = None
        #: Die zuletzt im Arbeiter vorbereitete Fläche, gleich ob ihre Antwort
        #: noch galt: Eine überholte Frage hat die Fläche trotzdem richtig
        #: vorbereitet, und die nächste Bewegung trifft meist dieselbe.
        self._surface_known: tuple[Any, Any, frozenset[int]] | None = None
        #: Wo die linke Taste für den Rückweg aus dem Dialog gedrückt wurde
        #: (:meth:`_resume`) — ``None`` ohne solchen Druck.
        self._resume_press: tuple[int, int] | None = None
        self._surface: Any = None
        self._object_id = ""
        self._centre_id = ""
        self._frozen = False
        self._position_edited = False
        self._measure_without_surface = False
        self._distance_valid = True
        self._commit_pending = False
        self._accept_pending = False
        self._updating = False
        #: Ob die Tiefenstufe läuft — Stufe 2 der Platzierung. Der Klick legt
        #: die Stelle fest, danach zieht die Maus die Tiefe (Robert,
        #: 09.09.2026: „wenn wir klicken wollen wir die bohrung von der
        #: seitenansicht sehen und dann die tiefe runterziehen").
        self._seated_by_default = False
        """Ob die Stelle **von selbst** gewählt wurde — noch von niemandem geklickt.

        Ein Baustein sitzt seit dem 11.09.2026 sofort auf der gewählten oder
        der obersten Fläche (:meth:`_begin_on_a_face`), damit Vorschau und
        Griff da sind, bevor jemand zielt (Robert: „im viewport gab es weder
        vorschau, noch das gizmo dazu"). Der Zeiger zielt dann nicht mehr —
        aber ein Klick ins Bild **setzt um**, statt zu übernehmen: Wer nie
        geklickt hat, hat die Stelle nie bestätigt, und ein Klick auf das Teil
        darf keinen Schritt auslösen. Nach dem ersten Klick gilt, was immer
        galt: Der nächste übernimmt."""
        self._seated_at_feature = False
        """Ob die Stelle einem vorhandenen Merkmal gehört.

        **Dann zielt der Zeiger nicht.** Wer ein Loch anklickt, will seine Maße
        sehen und ändern; die Stelle steht schon, und eine Mausbewegung darüber
        verschob sie samt aller Maßlinien unter der Hand (Robert, 11.09.2026:
        „die maße im viewport gehen beim bearbeiten von dem loch jetzt von dem
        mauszeiger aus, wir wollen aber bei der bohrung das mittelloch").

        Der Merker beginnt beim Rechnen der Trägerfläche und fällt erst bei
        einem **Klick** — der ist die ausdrückliche Ansage, das Loch woanders
        hinzusetzen. Beim Setzen einer neuen Bohrung wird er nie gesetzt, dort
        ändert sich nichts."""
        self._deepening = False
        #: Ob die Tiefe angehalten ist. Der Klick in der Tiefenstufe friert sie
        #: ein, damit die Maus sie nicht weiter verstellt, während man zum Knopf
        #: fährt oder die Zahl nachbessert.
        self._depth_set = False
        #: Der Bildpunkt, an dem das Ziehen begann, und der Wert dazu. Gemessen
        #: wird die Strecke von dort, nicht von Bild zu Bild: Eine Summe aus
        #: Schritten driftet, sobald ein Ereignis ausfällt.
        #: Wie viele Millimeter ein Bildpunkt Zug bedeutet. Wird beim Beginn
        #: aus dem Maßstab der Ansicht gesetzt, damit der Zug am kleinen wie am
        #: großen Teil dasselbe Gefühl hat.
        self._depth_per_pixel = 0.1
        #: Wo die linke Taste in der Tiefenstufe gedrückt wurde — die Strecke
        #: bis zum Loslassen entscheidet, ob es ein Klick war oder ein Zug an
        #: der Kamera.
        self._pressed_at: tuple[int, int] | None = None
        #: Die Darstellungsart vor der Tiefenstufe — geliehen, nicht gesetzt.
        self._display_before: str | None = None
        #: Und die Kamerastellung davor, aus demselben Grund: Der Schwenk quer
        #: zur Werkzeugachse gehört der Stufe, nicht dem Kunden.
        self._camera_before: tuple[Any, Any, Any, float | None] | None = None
        self._canvas = _Dimensions(self.viewport)
        self._bar = QFrame(self.viewport)
        self._bar.setObjectName("surface_placement_bar")
        self._bar.setAutoFillBackground(True)
        layout = QHBoxLayout(self._bar)
        layout.setContentsMargins(ROOMY, NORMAL, ROOMY, NORMAL)
        self._title = QLabel(str(self.spec_of().title), self._bar)
        layout.addWidget(self._title)
        self._note = QLabel(tr("Auf eine Oberfläche zeigen."), self._bar)
        self._note.setWordWrap(True)
        layout.addWidget(self._note, 1)
        self._tool_legend = QLabel(self._bar)
        self._tool_legend.hide()
        layout.addWidget(self._tool_legend)
        self._back = QPushButton(tr("Werte bearbeiten"), self._bar)
        self._back.clicked.connect(self.back)
        layout.addWidget(self._back)
        self._accept = QPushButton(tr("Position übernehmen"), self._bar)
        self._accept.clicked.connect(self.accept)
        layout.addWidget(self._accept)
        self._bar.hide()
        self._measure_group: QWidget | None = None
        self._measure_scope: QWidget | None = None
        self._measure_interpret: Callable[[], bool] | None = None
        self._measure_refresh: Callable[[Mapping[str, Any]], None] | None = None
        self._interpreting_fields = False
        self._measure_box = QFrame(self.viewport)
        self._measure_box.setObjectName("placement_measure_fields")
        self._measure_box.setAutoFillBackground(True)
        measure_layout = QVBoxLayout(self._measure_box)
        measure_layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        measure_layout.setSpacing(NORMAL)
        self._measure_scroll = QScrollArea(self._measure_box)
        self._measure_scroll.setWidgetResizable(True)
        self._measure_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._measure_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        measure_layout.addWidget(self._measure_scroll)
        self._measure_note = QLabel(self._measure_box)
        self._measure_note.setWordWrap(True)
        self._measure_note.hide()
        measure_layout.addWidget(self._measure_note)
        measure_actions = QHBoxLayout()
        measure_actions.addStretch()
        self._measure_accept = QPushButton(tr("Übernehmen"), self._measure_box)
        self._measure_accept.setObjectName("placement_measure_accept")
        self._measure_accept.setIcon(icon("done", self._measure_accept))
        self._measure_accept.clicked.connect(self.accept)
        measure_actions.addWidget(self._measure_accept)
        self._measure_cancel = QPushButton(tr("Abbrechen"), self._measure_box)
        self._measure_cancel.setObjectName("placement_measure_cancel")
        self._measure_cancel.setIcon(icon("cancel", self._measure_cancel))
        self._measure_cancel.clicked.connect(self._cancel_measures)
        measure_actions.addWidget(self._measure_cancel)
        measure_layout.addLayout(measure_actions)
        self._measure_scope_box = QWidget(self._measure_box)
        self._measure_scope_layout = QVBoxLayout(self._measure_scope_box)
        self._measure_scope_layout.setContentsMargins(0, 0, 0, 0)
        self._measure_scope_box.hide()
        measure_layout.addWidget(self._measure_scope_box)
        self._measure_box.hide()
        self._measures = [LengthSpin(self.viewport), LengthSpin(self.viewport)]
        for index, field in enumerate(self._measures):
            field.setObjectName(f"placement_distance_{index + 1}")
            field.setAccessibleName(
                tr("Abstand zu Kante {number}").replace("{number}", str(index + 1))
            )
            field.setToolTip(tr("Abstand ändern; die Position bleibt dabei auf dieser Fläche."))
            self._watch_field(field)
            # **Das Rad dreht ein Feld erst mit Fokus** — nach dem eigenen
            # Filter angemeldet, damit es vor ihm gefragt wird: Die Felder
            # schweben über dem Bild, und eine Radraste darüber meinte bis zum
            # 21.09.2026 den Zoom, verstellte aber das Maß und band den
            # Entwurf (Sonde ``probe_wheel_over_field.py``).
            wheel_needs_focus(field)
            field.valueChangedMm.connect(self._distance_changed)
            field.hide()
        #: Die Tiefe als Zahl — dasselbe Feld wie die Kantenabstände, damit
        #: Ausdruck und Einheitenumschaltung mitkommen. Sie steht in Stufe 3 an
        #: der Stelle der Kantenmaße: Die zeigen die Fläche, auf der gesetzt
        #: wurde, und die ist dort entschieden (Robert, 09.09.2026: „die maße
        #: fehlen auch bzw zeigen noch die von der Fläche wo wir die Bohrung
        #: gesetzt haben").
        self._depth_measure = LengthSpin(self.viewport)
        self._depth_measure.setObjectName("placement_depth")
        self._depth_measure.setAccessibleName(tr("Tiefe der Bohrung"))
        self._depth_measure.setToolTip(tr("Tiefe eintippen oder mit der Maus ziehen."))
        self._watch_field(self._depth_measure)
        wheel_needs_focus(self._depth_measure)
        self._depth_measure.valueChangedMm.connect(self._depth_typed)
        self._depth_measure.hide()
        #: Was an Wand stehen bleibt — das Gegenstück zur Tiefe. Eine Zahl und
        #: kein Feld: Sie folgt aus Tiefe und Materialstärke und ist nichts,
        #: was man eintippt.
        self._rest = QLabel(self.viewport)
        self._rest.setObjectName("placement_rest")
        self._rest.setAutoFillBackground(True)
        self._rest.hide()
        self._centre = QLabel(self.viewport)
        self._centre.setAutoFillBackground(True)
        self._centre.hide()
        self._centre_measures = [LengthSpin(self.viewport), LengthSpin(self.viewport)]
        for index, field in enumerate(self._centre_measures):
            field.setObjectName(f"placement_centre_distance_{index + 1}")
            field.setAccessibleName(
                tr("Abstand zum Mittelpunkt – Richtung {number}").format(number=index + 1)
            )
            field.setPrefix(tr("Mitte {number}: ").format(number=index + 1))
            field.setToolTip(tr("Der Maßpfeil zeigt die Richtung auf dieser Fläche."))
            self._watch_field(field)
            wheel_needs_focus(field)
            field.valueChangedMm.connect(self._centre_changed)
            field.hide()
        self._reference_pick: int | None = None
        self._held_references: tuple[placement.EdgeReference, ...] | None = None
        self._held_centre = ""
        self._reference_message = ""
        self._distance_message = ""
        """Warum der Abstand gerade nicht gilt — gezeigt nur, solange er nicht gilt.

        Ein eigenes Feld und nicht der Bezugshinweis: Jeder Weg, der den
        Abstand wieder gültig macht (Griff, neue Stelle, Neuaufbau), setzt
        ``_distance_valid``; der Hinweis daneben blieb sonst mit „außerhalb"
        stehen, während Übernehmen längst frei war (Review 24.09.2026)."""
        self._reference_boxes: list[QWidget] = []
        # **Der Bezugswechsel steht nicht im Bild** (Robert, 21.09.2026,
        # RM-197: „das mit bezug ändern hintendran brauche ich garnicht").
        # Bis dahin trug jedes Kantenmaß ein Auswahlfeld *Bezug ändern* hinter
        # sich — die doppelte Breite je Beschriftung, mitten über der Platte.
        # Die Wahl bleibt erreichbar, wo sie niemanden stört: als Kontextmenü
        # des Maßes (Rechtsklick oder Menütaste, `_reference_menu`), gebaut je
        # Aufruf und danach weggeräumt. Der Rahmen um das Feld bleibt: Er ist,
        # was `redraw` an die Maßlinie legt und die Verteilung freihält.
        for index, reference_field in enumerate((*self._measures, self._centre)):
            box = QWidget(self.viewport)
            layout = QHBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(SPACE)
            layout.addWidget(reference_field)
            reference_field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            reference_field.customContextMenuRequested.connect(
                lambda at, slot=index: self._reference_menu(slot, at)
            )
            self._reference_boxes.append(box)
            box.hide()
        # **Die Tabulatortaste geht denselben Weg wie das Auge** (`oberflaeche.md`):
        # erst die zwei Kantenmaße, dann die Mitten.
        ordered = [*self._measures, *self._centre_measures]
        for earlier, later in pairwise(ordered):
            QWidget.setTabOrder(earlier, later)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._next_surface)
        # **Ein Bild je Ereignisrunde, nicht je Neuzeichnung** (22.09.2026).
        # Ein Anschlag im Maßfeld zeichnete den Fluss drei Mal neu — über
        # ``_distance_changed``, über die Wertemeldung des Trägers und über
        # den fertigen Werkzeugbau —, und jedes Mal ein ganzes Bild: an der
        # Senkplatte bei 3163 mal 1259 Bildpunkten 14 ms je Bild, 43 bis 107 ms
        # je Anschlag. Die Lage der Felder und Linien entsteht weiter sofort;
        # das Bild dazu einmal, wenn die Runde leer ist.
        self._frame = QTimer(self)
        self._frame.setSingleShot(True)
        self._frame.setInterval(0)
        self._frame.timeout.connect(self._draw_now)
        dialog.surfaceRequested.connect(self.start)
        dialog.valuesChanged.connect(self._values_changed)
        dialog.finished.connect(self.dispose)
        if isinstance(dialog, QuietHost):
            dialog.editStarted.connect(self._refresh_measure_actions)
            dialog.commitStarted.connect(self._commit_started)
            dialog.commitFinished.connect(self._commit_finished)
            dialog.applyStateChanged.connect(self.redraw)
        self._watch(self.viewport)
        render_widget = getattr(self.viewport.renderer, "widget", None)
        if render_widget is not None:
            self._watch(render_widget)
        self.viewport.cameraMoved.connect(self._camera_moved)
        # **Der Langlochzug endet mit einem Aufbau.** Sein Umriss ersetzt den
        # runden der Mündung, und die Maßlinien bleiben — ohne diesen Aufbau
        # stand der runde Umriss neben dem gezogenen, bis die Kamera das
        # nächste Mal zeichnete.
        self.viewport.slotProposed.connect(self._after_slot_proposal)
        self.session.sceneChanged.connect(self._scene_changed)
        self.session.projectChanged.connect(self._document_changed)
        self.viewport.sceneApplied.connect(self._scene_applied)
        self.viewport.previewDragged.connect(self._dragged_in_preview)
        self.viewport.placementDragged.connect(self._dragged_at_the_tool)
        self.viewport.placementDragStarted.connect(self._drag_started_in_the_view)
        self.viewport.set_preview_gizmo(_grips_its_preview(self.spec_of()))
        self.refresh_available()
        # **Wer eine platzierbare Operation wählt, will platzieren.** Der Weg
        # dorthin war ein zweiter Klick auf „Im Modell platzieren" — ein Knopf,
        # der genau das anbietet, was die Operation ohnehin verlangt (Befund
        # Robert, 09.09.2026: „man soll keinen extra Button klicken müssen").
        #
        # **Und seit dem 11.09.2026 ist der Knopf ganz weg** (Robert: „im
        # dialog das im modell platzieren brauchen wir auch nicht"). Escape
        # bringt den Dialog weiterhin zurück; der Rückweg von dort in die
        # Platzierung führt über ``surfaceRequested``, und wer ihn sendet,
        # entscheidet die Oberfläche — heute niemand mehr, nach §2.4 des
        # Konzepts ein Knopf im Merkmalfenster.
        #
        # **Nicht beim Ändern eines Schritts.** Dort ist die Stelle längst
        # gewählt, und wer den Durchmesser nachbessert, will kein Fadenkreuz.
        # Und nicht sofort, sondern eine Runde später: Der Dialog ist hier
        # noch nicht gezeigt, und ``start`` versteckt ihn.
        if starts_by_itself(self.spec_of()) and self._change_op is None and self.can_place():
            QTimer.singleShot(0, self._start_if_still_possible)

    def _watch(self, widget: QObject) -> None:
        """Den Filter einmal anmelden und bis zum Abbau zuordnen."""
        if widget not in self._watched:
            self._watched.append(widget)
            widget.installEventFilter(self)

    def _watch_field(self, field: QWidget) -> list[QObject]:
        """Auch die inneren Texteingaben eines zusammengesetzten Feldes beobachten."""
        targets: list[QObject] = [field, *field.findChildren(QWidget)]
        for target in targets:
            self._watch(target)
            if target not in self._field_targets:
                self._field_targets.append(target)
        return targets

    def set_measure_fields(
        self,
        group: QWidget,
        *,
        editors: Iterable[QWidget],
        interpret: Callable[[], bool],
        refresh: Callable[[Mapping[str, Any]], None],
        scope: QWidget | None = None,
    ) -> None:
        """Gemeinsame Fachfelder anzeigen; alle Werte bleiben ausschließlich beim Träger.

        Der Erzeuger liefert dieselben Felder und Leser wie das Merkmalfenster.
        Der Fluss besitzt ihre Lebensdauer, Anordnung und das gemeinsame Ende.
        ``refresh`` schreibt nur Anzeige und erhält noch nicht gelesene Texte.
        """
        if self._disposed:
            group.deleteLater()
            return
        for target in self._measure_targets:
            if isValid(target):
                target.removeEventFilter(self)
            if target in self._watched:
                self._watched.remove(target)
            if target in self._field_targets:
                self._field_targets.remove(target)
        self._measure_targets = []
        previous = self._measure_scroll.takeWidget()
        if previous is not None and previous is not group:
            previous.hide()
            previous.deleteLater()
        self._measure_group = group
        previous_scope = self._measure_scope
        if previous_scope is not None and previous_scope is not scope:
            self._measure_scope_layout.removeWidget(previous_scope)
            previous_scope.hide()
            previous_scope.deleteLater()
        self._measure_scope = scope
        if scope is not None:
            self._measure_scope_layout.addWidget(scope)
            self._measure_targets.extend(self._watch_field(scope))
        self._measure_scope_box.setVisible(scope is not None)
        self._measure_interpret = interpret
        self._measure_refresh = refresh
        self.dialog.requires_displayed_preview = True
        self._measure_scroll.setWidget(group)
        self._watch(group)
        self._measure_targets.append(group)
        for field in editors:
            self._measure_targets.extend(self._watch_field(field))
        self._refresh_measure_fields()
        self._refresh_measure_actions()
        self.redraw()

    def _refresh_measure_fields(self) -> None:
        """Geänderte Trägerwerte spiegeln, ohne eine laufende Textlesung zu unterbrechen."""
        if (
            not self._disposed
            and not self._interpreting_fields
            and self._measure_refresh is not None
        ):
            self._measure_refresh(self.dialog.values())

    def _pulled_slot(self) -> tuple[float, float] | None:
        """Länge und Richtung des Langlochzugs, der am gebundenen Merkmal wartet.

        Die Maßgruppe an einer Bohrung ist an *Bohrung ändern* gebunden; die
        Knöpfe zum Langloch gehören zum selben Loch. Wartet dort ein Zug, meint
        das Übernehmen der Gruppe ihn (Robert, 22.09.2026: „warum geht zum
        langloch nicht mehr").
        """
        if not isinstance(self.dialog, QuietHost):
            return None
        feature_id = self.dialog.values().get("at_feature")
        if not feature_id:
            return None
        pulled = self.viewport.waiting_slot_drag(str(feature_id))
        return None if pulled is None else (float(pulled[0]), float(pulled[1]))

    def _slot_drag_takes_the_accept(self) -> bool:
        """Ob Übernehmen der Maßgruppe das gezogene Langloch meint — die Frage des Fensters."""
        takes = getattr(self.window, "slot_drag_takes_the_accept", None)
        if takes is None:
            return False
        return bool(takes(self.spec_of().name, self.dialog.values()))

    def _refresh_measure_actions(self) -> None:
        """Die gesetzte Sperre darstellen, ohne den Vorschauwächter erneut aufzurufen."""
        if self._disposed:
            return
        host = self.dialog
        reason = host.blocked_reason if isinstance(host, QuietHost) else None
        begun = not isinstance(host, QuietHost) or host.begun
        # Ein wartender Langlochzug macht den Knopf frei — die Sperre gilt der
        # gebundenen Handlung, und die läuft dann nicht. Ob Übernehmen den Zug
        # meint, sagt **eine** Stelle (``MainWindow.slot_drag_takes_the_accept``):
        # nicht, wenn die Gruppe selbst an *Zum Langloch ziehen* gebunden ist,
        # und nicht, wenn die Felder einen anderen Durchmesser tragen — dann
        # kommt erst der Durchmesser, und der Zug ist danach zu wiederholen.
        pulled = self._slot_drag_takes_the_accept()
        if pulled:
            reason = None
            begun = True
        allowed = (
            self.active
            and (
                self._measure_without_surface
                or (
                    self._surface is not None
                    and self._tool_context is not None
                    and not self._tool_busy
                )
            )
            and self._distance_valid
            and self._reference_pick is None
            and self.session.result_current
            and self._display_ready()
            and begun
            and reason is None
            and (not isinstance(host, QuietHost) or not host.committing)
        )
        self._measure_accept.setEnabled(allowed)
        for setter in (
            self._measure_accept.setToolTip,
            self._measure_accept.setStatusTip,
            self._measure_accept.setAccessibleDescription,
        ):
            setter(reason or "")
        information = (
            tr(
                "Die ursprünglichen Maße bleiben bearbeitbar. "
                "Für diese Stelle sind keine eindeutigen Flächenmaße verfügbar."
            )
            if self._measure_without_surface
            else ""
        )
        # Sperre, Bezugshinweis und Auskunft stehen **zusammen**: Eine wartende
        # Vorschau verdrängte bis zum 21.09.2026 den Satz, dass es an dieser
        # Stelle keine Flächenmaße gibt — und der erklärt, warum die Felder
        # rechts die einzigen sind.
        if pulled:
            information = tr("Übernehmen zieht die Bohrung zum Langloch.")
        elif self._pulled_slot() is not None and self.spec_of().name != "slot_hole":
            # Zug und neuer Durchmesser: eine Transaktion aus zwei Schritten
            # (Entscheidung Robert, 22.09.2026).
            information = tr("Übernehmen zieht die Bohrung zum Langloch und ändert die Breite.")
        distance = "" if self._distance_valid else self._distance_message
        self._measure_note.setText(
            "\n".join(filter(None, (reason, distance, self._reference_message, information)))
        )
        self._measure_note.setVisible(
            (bool(reason) and begun)
            or bool(distance)
            or bool(self._reference_message)
            or bool(information)
        )

    def _size_measure_fields(self, room: QRect) -> None:
        """Die Fachgruppe bleibt im freien Bildraum; bei Platzmangel rollt ihr Inhalt."""
        group = self._measure_group
        if group is None:
            self._measure_box.hide()
            return
        group.ensurePolished()
        width = min(
            max(room.width(), 1),
            max(
                group.sizeHint().width() + 4 * NORMAL,
                self._measure_accept.sizeHint().width()
                + self._measure_cancel.sizeHint().width()
                + 3 * NORMAL,
            ),
        )
        content_width = max(width - 4 * NORMAL, 1)
        group.setMaximumWidth(content_width)
        layout = group.layout()
        height = (
            layout.heightForWidth(content_width)
            if layout is not None and layout.hasHeightForWidth()
            else group.sizeHint().height()
        )
        chrome = self._measure_accept.sizeHint().height() + 3 * NORMAL
        if not self._measure_note.isHidden():
            chrome += max(self._measure_note.heightForWidth(content_width), 0) + NORMAL
        if self._measure_scope is not None:
            self._measure_scope.setMaximumWidth(content_width)
            chrome += self._measure_scope.sizeHint().height() + NORMAL
        # Eine weitere Zeile bleibt für die vorhandenen Kantenabstände frei.
        distances = self._measures[0].sizeHint().height() + SPACE
        self._measure_scroll.setFixedHeight(max(1, min(height, room.height() - chrome - distances)))
        self._measure_box.setMaximumSize(max(width, 1), max(room.height(), 1))
        self._measure_box.adjustSize()
        self._measure_box.show()

    def _begin_edit(self) -> None:
        """Eine Nutzergeste beginnt den stillen Entwurf, nie seine bloße Anzeige."""
        if not self._disposed and self.active and isinstance(self.dialog, QuietHost):
            self.dialog.begin_edit()

    def _grip_belongs_to_another_flow(self) -> bool:
        """Ob der Platzierungsgriff der Ansicht an einem fremden Werkzeug hängt.

        Die Signale der Ansicht sind ungerichtet: ``placementDragged`` und
        ``placementDragStarted`` kommen bei jedem Fluss an, der an derselben
        Ansicht hängt. Stehen zwei — die stillen Maße einer Bohrung und ein
        Baustein aus dem Dialog, der in ihr sitzt —, verschob ein Zug am
        Bausteingriff bis zum 21.09.2026 auch den stillen Fluss und band den
        Bohrungsentwurf an eine fremde Stelle (Sonde ``probe_two_flows.py``).
        Der Griff sagt, wessen Werkzeug er trägt; ohne Griff (Knopf oder
        Griff der Auswahl) gehört die Geste jedem.
        """
        gripped = getattr(self.viewport, "_placement_grip_item", None)
        return gripped is not None and gripped is not self._tool

    def _drag_started_in_the_view(self) -> None:
        """Ein Zug an Griff oder Knopf beginnt den Entwurf — den eigenen."""
        if self._grip_belongs_to_another_flow():
            return
        self._begin_edit()

    def _show_input_for_edit(self) -> None:
        """Bei erneuter Feldbetätigung die belegte historische Eingabe zurückholen."""
        if (
            self.active
            and self._change_op is not None
            and self._measure_group is not None
            and self._result is not None
            and not self._showing_input
            and self.session.result_current
        ):
            self._showing_input = True
            self.window._clear_preview()
            self.viewport.show_scene(self._result)
            self.redraw()

    def _interpret_active_fields(self) -> bool:
        """Vor Übernehmen jeden sichtbaren Zahlentext lesen, nicht nur das Fokusfeld."""
        if self._interpreting_fields:
            return False
        self._interpreting_fields = True
        valid = True
        try:
            for field in (*self._measures, *self._centre_measures, self._depth_measure):
                if not field.isVisibleTo(self.viewport):
                    continue
                if field.hasAcceptableInput():
                    field.interpretText()
                else:
                    valid = False
            if self._measure_interpret is not None:
                valid = self._measure_interpret() and valid
        finally:
            self._interpreting_fields = False
        if valid:
            self._refresh_measure_fields()
        return valid

    def _keep_field_text(self, field: LengthSpin) -> bool:
        """Eine Neuzeichnung überschreibt keinen aktiven oder noch ungelesenen Zahlentext."""
        return self._interpreting_fields or field.hasFocus() or field.lineEdit().isModified()

    def _commit_started(self) -> None:
        """Nur die eigene synchrone Dokumentmeldung bis zum Callback-Ergebnis halten."""
        self._committing_document = self.session.project.document
        self._deferred_document_change = False
        self._refresh_measure_actions()

    def _commit_finished(self, succeeded: bool) -> None:
        """Erfolg beendet über finished; eine trotz Absage erfolgte Änderung entwertet."""
        changed = self._deferred_document_change
        self._committing_document = None
        self._deferred_document_change = False
        if self._disposed:
            return
        if changed and not succeeded:
            self._document_changed()
        else:
            self._refresh_measure_actions()

    @property
    def target(self) -> str:
        """Der Körper, auf dem die zuletzt übernommenen Zahlen liegen."""
        return self._object_id

    @property
    def measure_group(self) -> QWidget | None:
        """Die Fachfelder der Maßgruppe im Bild — ``None`` ohne Maßgruppe."""
        return self._measure_group

    def can_place(self) -> bool:
        """Ob hier und jetzt platziert werden darf.

        **Die Frage gehört dem Fluss, nicht einem Knopf.** Sie stand bis zum
        11.09.2026 als ``surface_button.isEnabled()`` im Dialog, und drei
        Stellen lasen sie von dort. Ein Widget als Zustandsspeicher hält nur,
        solange es das Widget gibt — und der Knopf fällt (§2.5 des Konzepts).
        Er zeigt seither an, was hier steht, statt es zu sein.

        Zwei Hälften, und beide sind nötig: Die Operation muss ihre Stelle
        überhaupt auf einer Fläche einstellen lassen (**fachlich**), und es
        muss etwas da sein, worauf man zeigt (**jetzt**) — ein gerechnetes
        Ergebnis mit Körpern, oder ein Schritt, den jemand ändert.
        """
        result = self.session.last_result
        return bool(
            self._supported
            and self.viewport.renderer is not None
            and self.session.result_current
            and result is not None
            and (self._change_op is not None or (result.complete and bool(result.scene.objects)))
        )

    def refresh_available(self) -> None:
        """Nur fachlich platzierbare Operationen bieten den Einstieg an."""
        self._supported = placement.supports_surface_placement(self.spec_of())
        if self.active and not self._supported:
            self.back()

    def _start_if_still_possible(self) -> None:
        """Der Selbststart eine Ereignisrunde später — falls er dann noch gilt.

        Zwischen dem Aufbau und dieser Runde kann alles passiert sein: Der
        Dialog wurde geschlossen, die Auswertung lief neu, jemand hat schon
        selbst geklickt. Geprüft wird deshalb erneut, statt sich auf den
        Zustand von vorhin zu verlassen.
        """
        if self._disposed or self.active or not isValid(self):
            return
        if not self.dialog.isVisible():
            return
        self.start()

    def start(self) -> None:
        self.refresh_available()
        if self._disposed or not self.can_place():
            return
        self.active = True
        self.viewport.clear_placement_resume(self._resume)
        self._resume_press = None
        # Der Satz im Dialog gilt der laufenden Platzierung, nicht dem
        # Registereintrag (siehe `OperationDialog.show_placement_hint`).
        self._tell_the_host_we_aim(True)
        self._epoch += 1
        self._result = self.session.last_result if self._change_op is None else None
        self._frozen = False
        self._position_edited = False
        self._measure_without_surface = False
        self._seated_by_default = False
        self._distance_valid = True
        self._commit_pending = False
        self._accept_pending = False
        self._surface = None
        self._serial += 1
        # **Und der Knopf sagt wieder, was er tut.** Zurückgesetzt wurde sein
        # Text nur beim Verlassen der Tiefenstufe; wer sie über Escape verließ
        # und neu begann, las „Weiter zur Tiefe" über einer Fläche, auf der
        # noch nichts steht.
        self._accept.setText(tr("Weiter zur Tiefe") if self.deepens() else tr("Übernehmen"))
        # **Der Dialog bleibt stehen** (Robert, 09.09.2026: „wenn ich auf
        # bohrung setzen klicke sollte der dialog übrigens da bleiben"). Er
        # trug bis dahin die Maße, die man beim Platzieren braucht, und
        # verschwand genau dann, wenn man sie sehen wollte; wer den
        # Durchmesser nachbessern wollte, musste Escape drücken, tippen und
        # neu zielen.
        self.window._clear_preview()
        self.viewport.set_placement_pointer(self.pointer)
        self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
        self._show_bar()
        self._accept.setEnabled(False)
        self.viewport.setFocus(Qt.FocusReason.OtherFocusReason)
        if self._change_op is None:
            self._request_tool()
            self._begin_at_feature()
        else:
            epoch = self._epoch
            self._note.setText(tr("Die Oberfläche vor diesem Schritt wird vorbereitet …"))

            def ready(result: Any) -> None:
                if not isValid(self) or self._disposed or not self.active or epoch != self._epoch:
                    return
                if result is None or not result.complete:
                    self._invalid(tr("Die Eingabe dieses Schritts prüfen und erneut platzieren."))
                    return
                self._result = result
                self._showing_input = True
                self.viewport.show_scene(result)
                self._request_tool()
                if self._measure_group is not None:
                    self._begin_at_bore_step()

            self.session.placement_before(self._change_op, ready, lambda _detail: ready(None))
        self.redraw()

    def _tell_the_host_we_aim(self, on: bool, *, paused: bool = False) -> None:
        """Dem Träger Zielen oder die mögliche Rückkehr aus der Pause melden.

        Nur der Operationsdialog trägt den Satz; der stille Träger am
        gewählten Merkmal (`QuietHost`) hat kein Fenster und beantwortet die
        Frage leer. Beide stehen im Vertrag (:class:`PlacementHost`) — ein
        `getattr` stand hier und sah aus wie Vorsicht: Es ging an mypy vorbei,
        und ein Tippfehler im Namen wäre nie aufgefallen.
        """
        self.dialog.show_placement_hint(on, paused=paused)

    def show_preview_base(self) -> bool:
        """Die vollständige Ergebnisszene zeigen, den historischen Eingang behalten.

        Die Endvorschau vergleicht mit dem aktuellen Ergebnis einschließlich
        späterer Körper. Flächentreffer und Maße bleiben dagegen auf den
        Eingang vor dem bearbeiteten Schritt bezogen. Erst ``sceneApplied``
        bestätigt eine gegebenenfalls im Arbeiter vorbereitete Grundszene.
        """
        if not self.active or self._change_op is None:
            return True
        if self._result is None or not self.session.result_current:
            return False
        if self._showing_input:
            self._showing_input = False
            self.viewport.show_scene(self.session.last_result)
        return bool(self.viewport.is_scene_applied(self.session.last_result))

    def _display_ready(self) -> bool:
        """Ob die gerade angeforderte Platzierungsansicht wirklich dargestellt ist."""
        result = (
            self.session.last_result
            if self._change_op is not None and not self._showing_input
            else self._result
        )
        return self._result is not None and self.viewport.is_scene_applied(result)

    def step_back(self) -> None:
        """Escape: genau eine Stufe zurück, mit allen Werten (RM-205).

        Die Platzierung hat drei Stufen (Robert, 09.09.2026): zielen, die Maße
        an der geklickten Stelle einstellen, die Tiefe ziehen. Bis zum
        22.09.2026 führte Escape aus jeder davon in den Dialog — aus der
        Tiefe also über die Maße hinweg, und wer nur die Stelle neu wählen
        wollte, fing im Dialog wieder an. Jetzt:

        * **Tiefe → Maße.** Ansicht und Kamera kommen zurück, die gezogene
          Tiefe bleibt als Zahl stehen.
        * **Maße → Zielen.** Die Stelle folgt wieder dem Zeiger; die Felder
          behalten ihre Werte, bis ein Klick eine neue Stelle setzt.
        * **Zielen → Dialog** (:meth:`back`), wie bisher. Von dort führt ein
          Klick auf das Modell wieder hierher (:meth:`_resume`).

        Zuerst nimmt Escape einen offenen Bezugswahlmodus zurück, sonst
        nichts. Beim Ändern eines Schritts gibt es nur eine Stufe, dort geht
        es wie bisher ganz zurück. **Am gewählten Merkmal (``QuietHost``) tut
        Escape, was Abbrechen tut** (Entscheidung Robert, 25.09.2026: „wie
        abbrechen zurücknehmen und abwählen"): :meth:`_cancel_measures`.
        """
        if self._disposed or self._cancel_reference_pick():
            return
        if isinstance(self.dialog, QuietHost):
            self._cancel_measures()
            return
        if not self.active:
            self.back()
            return
        if self._deepening:
            self._leave_depth()
            self._settle()
            return
        if (
            self._frozen
            and self._surface is not None
            and self._change_op is None
            and self._measure_group is None
            and not isinstance(self.dialog, QuietHost)
        ):
            self._frozen = False
            self._seated_by_default = False
            self._commit_pending = False
            self._accept_pending = False
            self._pending = None
            self._serial += 1
            self._accept.setText(tr("Weiter zur Tiefe") if self.deepens() else tr("Übernehmen"))
            self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
            self.redraw()
            return
        self.back()

    def _resume(self, event: PointerEvent) -> bool:
        """Ein Klick auf das Modell holt die pausierte Platzierung zurück.

        Gesendet wird dabei ``surfaceRequested`` — derselbe Eingang, den der
        Knopf *Stelle im Bild wählen* im Dialog für die Tastatur bedient
        (``OperationDialog.aim_again``) —, und derselbe Klick setzt die
        Stelle: Wer ins Modell klickt, meint diese Stelle und nicht „bitte
        gleich zielen lassen". Ein Druck neben dem Körper und jeder Zug
        gehören weiter der Kamera.
        """
        if self._disposed or self.active or not self.dialog.isVisible():
            return False
        if event.kind == "press" and event.button == "left":
            self._resume_press = None
            hit = self.viewport.placement_hit(event.x, event.y)
            inputs = self.inputs_of()
            if hit is None or (inputs and hit[0] not in inputs) or not self.can_place():
                return False
            self._resume_press = (event.x, event.y)
            return True
        if event.kind == "release" and event.button == "left" and self._resume_press is not None:
            pressed, self._resume_press = self._resume_press, None
            away = max(abs(event.x - pressed[0]), abs(event.y - pressed[1]))
            threshold = float(QApplication.startDragDistance()) * self.viewport._device_ratio()
            if away > threshold:
                return True
            self.dialog.surfaceRequested.emit()
            # ``start`` hat ``active`` gesetzt, wenn es starten konnte — frisch
            # gelesen, nicht aus der Prüfung oben.
            if cast("bool", self.active):
                self.pointer(event)
            return True
        return False

    def _cancel_measures(self) -> None:
        """*Abbrechen* der Maßgruppe — am gewählten Merkmal ein eigener Weg.

        Dort verwirft der Knopf den Entwurf und hebt die Auswahl auf (Robert,
        24.09.2026: „abbrechen = deselektieren"); das entscheidet, wer den
        Träger gebaut hat (``QuietHost.cancelled``). Im Dialogweg geht er
        zurück wie Escape (:meth:`back`).
        """
        if isinstance(self.dialog, QuietHost) and not self._disposed:
            self.dialog.cancel()
            return
        self.back()

    def back(self) -> None:
        """Escape behält alle Werte, übernimmt aber keinen Schritt.

        Auch kein Ziel: ``run_chosen`` verzweigt an :attr:`target`, und ein
        stehen gebliebener Körper machte aus drei gewählten Körpern still
        einen — der Dialog bohrte dann nur ihn. Nur :meth:`accept` trägt das
        Ziel bis zum Dialog.
        """
        if self._disposed:
            return
        if isinstance(self.dialog, QuietHost):
            self.dialog.reject()
            return
        self._stop()
        self._object_id = ""
        # **Und der Weg zurück steht offen** (RM-205): Ein Klick auf das Modell
        # holt die Platzierung wieder, und der Satz im Dialog sagt es — er ist
        # derselbe wie beim Zielen, weil der Klick dasselbe tut.
        resumes_on_click = starts_by_itself(self.spec_of()) and self._change_op is None
        if resumes_on_click:
            self.viewport.set_placement_resume(self._resume)
        self._tell_the_host_we_aim(resumes_on_click, paused=True)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        self.dialog.valuesChanged.emit()

    def _stop(self) -> None:
        self.active = False
        self.viewport.clear_placement_resume(self._resume)
        self._resume_press = None
        self._reference_pick = None
        self._held_references = None
        self._held_centre = ""
        self._tell_the_host_we_aim(False)
        self._epoch += 1
        self._serial += 1
        self._pending = None
        self._commit_pending = False
        self._accept_pending = False
        self._leave_depth()
        self._timer.stop()
        self.viewport.set_placement_pointer(None)
        for widget in self._widgets():
            widget.hide()
        self._canvas.hide()
        self.viewport.grip_placement(None)
        self._remove_tools()
        self._tool_context = None
        self._tool_key = ""
        if self._showing_input:
            self._showing_input = False
            self.viewport.show_scene(self.session.last_result)
        self._result = None
        self.viewport._draw()

    def _leave_depth(self) -> None:
        """Die Tiefenstufe verlassen und die geliehene Ansicht zurückgeben.

        Die Darstellungsart ist eine Einstellung des Nutzers (`ansicht.md`,
        „Was die Ansicht sich merkt"); durchscheinend war sie hier geliehen,
        und wer leiht, gibt zurück — auch beim Abbruch über Escape.
        """
        if not self._deepening:
            return
        self._deepening = False
        self._depth_set = False
        if self._display_before is not None:
            self.viewport.set_display_mode(self._display_before)
        self._display_before = None
        # **Und die Kamera genauso.** Sie war ebenso geliehen — der Schwenk
        # quer zur Achse gehört der Stufe, nicht dem Kunden. Der Docstring
        # versprach das von Anfang an („auch beim Abbruch über Escape"), und
        # zurückgestellt wurde nur die Darstellungsart: Nach Escape blieb die
        # Ansicht im Seitenschwenk stehen.
        if self._camera_before is not None and self.viewport.renderer is not None:
            position, focus, up, scale = self._camera_before
            self.viewport.set_camera_pose(position, focus, up, scale)
            self.viewport.settle_camera()
        self._camera_before = None
        self._accept.setText(tr("Position übernehmen"))

    def _remove_tools(self) -> None:
        """Schnitt und Anbau gehören demselben vorübergehenden Werkzeug."""
        renderer = self.viewport.renderer
        if renderer is not None:
            for item in (self._tool, self._addition):
                if item is not None:
                    renderer.remove(item)
        self._tool = None
        self._addition = None
        self._tool_legend.hide()

    def dispose(self, _code: int = 0) -> None:
        if self._disposed:
            return
        self._stop()
        # **Der Griff der Vorschau gehört diesem Dialog.** Ohne diese Zeile
        # blieb er im Bild stehen, und schlimmer: ``_preview_gizmo_wanted``
        # blieb gesetzt, sodass ihn jede künftige Vorschau neu anhängte — auch
        # an einer Bohrung, wo er nicht hingehört.
        self.viewport.set_preview_gizmo(False)
        self._disposed = True
        for target in self._watched:
            if isValid(target):
                target.removeEventFilter(self)
        self._watched.clear()
        self._field_targets.clear()
        self._measure_targets.clear()
        self._measure_interpret = None
        self._measure_refresh = None
        if isValid(self.viewport):
            # **Alle Verbindungen zur Ansicht, nicht nur eine.** Bis zum
            # 21.09.2026 löste der Abbau allein ``placementDragStarted``; die
            # fünf anderen hielten den Fluss am Leben und riefen ``redraw``
            # bei jeder Kamerageste in einen Fluss, der sich für abgebaut
            # hielt — die Wache ``_disposed`` fing es, aber der Aufruf blieb.
            self.viewport.cameraMoved.disconnect(self._camera_moved)
            self.viewport.slotProposed.disconnect(self._after_slot_proposal)
            self.viewport.sceneApplied.disconnect(self._scene_applied)
            self.viewport.previewDragged.disconnect(self._dragged_in_preview)
            self.viewport.placementDragged.disconnect(self._dragged_at_the_tool)
            self.viewport.placementDragStarted.disconnect(self._drag_started_in_the_view)
        self.session.sceneChanged.disconnect(self._scene_changed)
        self.session.projectChanged.disconnect(self._document_changed)
        if isinstance(self.dialog, QuietHost):
            self.dialog.reject()
        for widget in self._widgets():
            widget.deleteLater()
        self._canvas.dispose()

    def _after_slot_proposal(self, *_args: object) -> None:
        """Ein gezogenes Langloch wartet — die Maße bleiben und zeichnen neu."""
        self.redraw()

    def _show_bar(self) -> None:
        """Die Leiste unten zeigen — außer der Träger trägt seine Werte schon.

        **Eine Stelle für zwei Aufrufe**, damit die Frage nicht an einem von
        beiden vergessen wird: Was hier hängt, ist nicht die Sichtbarkeit
        eines Widgets, sondern ob es im Bild eine zweite Bedienstelle gibt.
        """
        self._bar.setVisible(not self.dialog.values_stand_elsewhere)

    def _widgets(self) -> tuple[QWidget, ...]:
        return (
            self._bar,
            self._depth_measure,
            self._rest,
            self._measure_box,
            *self._reference_boxes,
            *self._centre_measures,
        )

    def pointer(self, event: PointerEvent) -> bool:
        """Linksklick gehört der Platzierung, alle Kameragesten bleiben frei."""
        if not self.active or self.viewport.slot_drag_waits():
            return False
        if self._reference_pick is not None:
            if event.kind == "press" and event.button == "left":
                self._pressed_at = (event.x, event.y)
                return True
            if event.kind == "release" and event.button == "left" and self._barely_moved(event):
                self._pick_reference(event.x, event.y)
                return True
            return event.kind == "move" and not event.buttons
        if self._seated_at_feature:
            # **Die Stelle steht am Merkmal, nicht am Zeiger** — aber nur die
            # freie Bewegung gehört dieser Zusage. Ein Zug mit gedrückter
            # Taste ist eine Kamerageste, und die bleibt frei (Regel dieser
            # Datei: „Was die Platzierung nicht nimmt, gehört der Kamera").
            # Ohne die Tastenfrage waren Drehen und Schieben mit rechter und
            # mittlerer Taste tot, solange eine Bohrung gewählt war.
            #
            # **Am Merkmal zielt die Platzierung nie.** Bis zum Abend des
            # 11.09.2026 war ein Klick neben dem Griff die Ansage, „woanders
            # hinzuwollen": Die Platzierung löste sich vom Merkmal und zielte
            # mit dem Zeiger — die Bohrungsvorschau klebte daran, als setze man
            # eine neue, und der Weg heraus war nicht zu finden (Robert: „auf
            # einmal war ich im modus eine neue Bohrung zu setzen … er sollte
            # an der stelle ja nichtmal kommen"). Wohin ein vorhandenes Loch
            # soll, sagen der Bewegungsgriff und die Felder rechts; ein Klick
            # ins Bild gehört der Auswahl, wie ohne Platzierung auch. Trifft er
            # etwas anderes, wechselt die Auswahl, und die Platzierung geht mit
            # ihr (``MainWindow._on_feature_selected``).
            #
            # **Und die freie Bewegung nimmt sie auch nicht.** Bis zum
            # 21.09.2026 gab sie dafür ``True`` zurück — nichts geschah damit,
            # aber der Viewport hielt die Bewegung für verbraucht und fragte
            # nie, was unter dem Zeiger liegt: Bei gewählter Bohrung gab es
            # keinen Hover und keinen Tooltip mehr (``_note_pointer`` kam nie
            # an die Reihe). Die Platzierung will hier nichts von der Maus;
            # also sagt sie es.
            return False
        if event.kind == "leave":
            return True
        confirm = event.kind == "release" and event.button == "left"
        # **In der Tiefenstufe zieht die Maus, sie zielt nicht mehr.** Die
        # Stelle steht seit dem ersten Klick; was jetzt zählt, ist die Strecke
        # nach unten, und der nächste Klick bestätigt.
        #
        # **Und diese Frage steht vor allen anderen.** Darüber stand die Zeile
        # aus Stufe 1, die jeden Linksklick für die Platzierung nahm — sie
        # schluckte den Beginn jedes Kamerazugs, bevor die Tiefenstufe
        # überhaupt gefragt wurde. Gemessen am Protokoll: ``press left`` bei
        # 1933,731 und ``release left`` bei 864,809, über tausend Bildpunkte
        # Zug, und die Kamera stand still (Robert, 09.09.2026: „verschieben
        # geht immer noch nicht").
        if self._deepening:
            if self._depth_set:
                # **Steht die Tiefe, gehört die Maus wieder ganz der Ansicht.**
                # Auch der Linksklick: Er hat seine Aufgabe erfüllt, und im
                # ``solidon``-Schema schiebt er die Kamera. Ihn weiter
                # abzufangen nahm dem Navigator den Beginn des Zugs, und
                # Schieben ging nicht mehr (Robert, 09.09.2026: „schieben kann
                # ich die kamera nicht nach dem setzen der tiefe"). Bestätigt
                # wird am Knopf.
                return False
            if event.kind == "move" and not event.buttons:
                self._deepen_to(event.x, event.y)
                return True
            if confirm:
                # **Ein Zug ist kein Klick.** Im ``solidon``-Schema schiebt die
                # linke Taste die Kamera; wer in dieser Stufe schiebt, hat die
                # Tiefe nicht gemeint — und sie stand danach still fest, weil
                # jedes Loslassen als Bestätigung zählte. Gemessen wird wie
                # überall an der Zugschwelle des Systems (`kamera.md`, „Ein
                # Klick ist ein Klick, auch mit Zittern").
                if not self._barely_moved(event):
                    return False
                # **Der Klick hält die Tiefe an, er setzt sie nicht.** Sonst
                # entscheidet dieselbe Geste zweimal — einmal die Stelle, einmal
                # das ganze Loch —, und wer nach dem Ziehen die Zahl nachbessern
                # will, hat schon gebohrt. Bestätigt wird über den Knopf
                # (Robert, 09.09.2026: „am ende über den dialog zu bestätigen").
                self._depth_set = True
                self._note.setText(
                    tr("Tiefe steht · Übernehmen: ausführen · Maßfeld: Zahl ändern · Esc: zurück")
                )
                self.redraw()
                return True
            # **Alles andere gehört der Kamera** (Robert, 09.09.2026: „hier
            # sollte ich dann auch wieder drehen und allen können"). Der erste
            # Anlauf schluckte jede Geste, die keine Tiefe war — Drehen, Zoomen
            # und Kippen waren in der Stufe tot, in der man sie am ehesten
            # braucht: Wer eine Tiefe beurteilt, dreht das Teil dazu. Nur der
            # Druck der linken Taste bleibt hier, weil sein Loslassen übernimmt.
            if event.kind == "press" and event.button == "left":
                self._pressed_at = (event.x, event.y)
                return True
            return False
        # In den Stufen davor gehört der Linksklick der Platzierung — sein
        # Loslassen setzt die Stelle beziehungsweise übernimmt sie.
        if event.kind == "press" and event.button == "left":
            return True
        if confirm or (event.kind == "move" and not event.buttons):
            if self._commit_pending:
                # **Die Sperre gilt dem laufenden Klick, nicht dem Modus.** Sie
                # verhindert, dass ein zweiter Klick zwischen dem ersten und
                # seiner Ausführung eine zweite Bohrung setzt — und blieb
                # stehen, sobald der gemerkte Klick nicht zum Setzen führte.
                # Danach lief jeder weitere Klick hier hinein und kam nie bei
                # der Fläche an: der Platzierungsmodus war stumm (Befund
                # Robert, 09.09.2026: „einmal hat es geklappt von 20 klicks").
                if self._still_committing():
                    return True
                self._commit_pending = False
            if self._frozen and not confirm:
                return True
            if (
                self._frozen
                and confirm
                and not self._seated_by_default
                and not self.dialog.requires_displayed_preview
            ):
                self.accept()
                return True
            # Eine von selbst gewählte Stelle bestätigt kein Klick, er setzt
            # um (siehe :attr:`_seated_by_default`) — und ab hier hat jemand
            # geklickt.
            self._seated_by_default = False
            self._pending = event.x, event.y, confirm
            self._commit_pending = confirm
            self._serial += 1
            # **Der Takt fragt höchstens alle 16 ms, er wartet nicht auf
            # Stillstand** (RM-203). Bis zum 22.09.2026 startete jede Bewegung
            # den Zeitgeber neu: Bei einer Maus mit 125 Hz kam die Frage erst,
            # wenn der Zeiger ruhte, und die Vorschau folgte ihm nicht. Eine
            # Frage zur Zeit bleibt (``_surface_busy``); ihr Ende nimmt gleich
            # die jüngste Stelle. Ein Klick wartet nie auf den Takt davor.
            if confirm or not self._timer.isActive():
                self._timer.start()
            return True
        return event.buttons == frozenset({"left"})

    def _barely_moved(self, event: PointerEvent) -> bool:
        """War das ein Klick oder das Ende eines Zugs?

        Dieselbe Frage wie im Navigator (`kamera.md`, „Ein Klick ist ein
        Klick, auch mit Zittern"), und dieselbe Antwort: die Zugschwelle des
        Systems. Ohne gemerkten Druck — etwa wenn die Stufe zwischen Druck und
        Loslassen begann — gilt es als Klick, denn ein verschlucktes Loslassen
        wäre der schlechtere Fehler.
        """
        if self._pressed_at is None:
            return True
        away = max(abs(event.x - self._pressed_at[0]), abs(event.y - self._pressed_at[1]))
        self._pressed_at = None
        threshold = float(QApplication.startDragDistance()) * self.viewport._device_ratio()
        return bool(away <= threshold)

    def _still_committing(self) -> bool:
        """Steht wirklich noch ein Klick aus, der gesetzt werden will?

        Drei Zustände, und jeder einzelne bedeutet „gleich passiert es": Die
        Stelle ist gemerkt und wartet auf den Timer, die Flächensuche läuft,
        oder der Werkzeugbau läuft. Steht keiner davon, ist der gemerkte Klick
        verfallen — und dann darf er den nächsten nicht aussperren.

        Ein vierter stand hier: ein Merker, der den zu frühen Klick vormerkte,
        damit der fertige Werkzeugbau ihn nachholt. Den Weg gibt es seit dem
        dreistufigen Ablauf nicht mehr — er läuft über ``_pending`` und den
        Timer —, und ein Zustand, der nie eintritt, macht aus einer Aufzählung
        eine Behauptung.
        """
        return bool(self._pending is not None or self._surface_busy or self._tool_busy)

    def _next_surface(self) -> None:
        if self._surface_busy or self._pending is None or not self.active:
            return
        if self._change_op is not None and self._result is not None:
            if not self._showing_input and self.session.result_current:
                # Zellnummern der Endvorschau gehören nicht zum historischen
                # Eingang. Den Treffer erst nach dessen Darstellung lesen.
                self._showing_input = True
                self.window._clear_preview()
                self.viewport.show_scene(self._result)
                return
            if self.session.result_current and not self._display_ready():
                # Die Flächengeste bleibt bis sceneApplied erhalten; eine
                # Übernahme wird hier weder vorgemerkt noch ausgelöst.
                return
        if not self.session.result_current or not self.viewport.is_scene_applied(self._result):
            self._pending = None
            self._invalid(tr("Die Oberfläche wird noch vorbereitet. Einen Moment warten."))
            return
        x, y, confirm = self._pending
        self._pending = None
        hit = self.viewport.placement_hit(x, y)
        if hit is None:
            self._invalid(tr("Auf eine sichtbare Oberfläche zeigen."))
            return
        object_id, point, cell, ray = hit
        result = self._result
        entry = result.scene.objects.get(object_id) if result is not None else None
        inputs = self.inputs_of()
        if entry is None or (inputs and object_id not in inputs):
            self._invalid(tr("Auf die Oberfläche des gewählten Körpers zeigen."))
            return
        clip_planes = tuple(plane for plane in self.viewport._section_planes() if plane is not None)
        stamp = self._serial
        # **Die Fläche von eben gilt, solange der Treffer auf ihr liegt** —
        # auch wenn er erst im Arbeiter feststeht. Ein dezimiert oder
        # geschnitten gezeigter Körper meldet keine Originalzelle (``cell``
        # ist -1), und bis zum 22.09.2026 bereitete dann jede Frage die
        # ganze Fläche neu vor, an einer Kopie ohne Merker: an der Senkplatte
        # (311 000 Dreiecke) eine Sekunde je Mausbewegung (RM-203).
        known, known_faces = None, frozenset[int]()
        if self._prepared is not None and self._prepared_mesh is entry.mesh:
            known, known_faces = self._prepared, self._patch_faces
        elif self._surface_known is not None and self._surface_known[0] is entry.mesh:
            known, known_faces = self._surface_known[1], self._surface_known[2]
        self._surface_busy = True
        if self._surface_mesh is None or self._surface_mesh[0] is not entry.mesh:
            self._surface_mesh = (entry.mesh, for_a_worker(entry.mesh))
        mesh = self._surface_mesh[1]

        def compute() -> Any:
            at, face = point, cell
            if face < 0 or clip_planes:
                if ray is None:
                    return None
                original = placement.original_surface_hit(mesh, *ray, clip_planes=clip_planes)
                if original is None:
                    return None
                face, at = original
            context = (
                known
                if known is not None and face in known_faces
                else placement.prepare_surface(mesh, face, entry.features)
            )
            return context, placement.at_point(context, at)

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed:
                return
            self._surface_busy = False
            if value is not None:
                self._surface_known = (
                    entry.mesh,
                    value[0],
                    frozenset(value[0].face_indices),
                )
            if self.active and stamp == self._serial:
                if value is None:
                    self._invalid(
                        tr(
                            "Diese Stelle lässt sich nicht sicher zuordnen. "
                            "Eine andere Fläche wählen."
                        )
                    )
                else:
                    self._prepared, self._surface = value
                    self._centre_id = (
                        self._surface.centres[0].feature_id if self._surface.centres else ""
                    )
                    self._prepared_mesh = entry.mesh
                    self._patch_faces = frozenset(self._surface.face_indices)
                    previous_object = self._object_id
                    self._object_id = object_id
                    self._distance_valid = True
                    if previous_object != object_id:
                        self._request_tool()
                    self._set_values()
                    self._note.setText(
                        tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück")
                        if self._surface.planar
                        else tr(
                            "Gekrümmte Fläche: lokale Ausrichtung, keine ebenen Kantenabstände."
                        )
                    )
                    self.redraw()
                    if confirm:
                        self._settle()
            self._next_surface()

        def failed(detail: str) -> None:
            done(None)
            if self.active and stamp == self._serial:
                self._note.setText(
                    tr("Andere Fläche wählen oder die Werte bearbeiten.") + " " + detail
                )

        self.session.placement_async(compute, done, failed)

    def _begin_at_bore_step(self) -> None:
        """Die ursprüngliche Bohrstelle ausschließlich am historischen Eingang ablesen."""
        entry, _feature = self._source_feature()
        spec = self.spec_of()
        if entry is None or spec.name not in {"drill_hole", "drill_brep_hole"}:
            return
        stamp = self._serial
        mesh = for_a_worker(entry.mesh)
        values = dict(self.dialog.values())
        parameters = dict(self.session.project.document.parameters)
        references = self._held_references
        centre_id = self._held_centre

        def compute() -> Any:
            resolved = expressions.resolve_params(values, expressions.resolve(parameters))
            seat = placement.seat_for_bore_step(mesh, spec, resolved, entry.features)
            if seat is None:
                return None
            prepared, mouth = seat
            return prepared, placement.at_point(prepared, mouth, references=references)

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed or not self.active or stamp != self._serial:
                return
            if value is None:
                self._measure_without_surface = True
                self._seated_at_feature = True
                self.redraw()
                return
            self._prepared, self._surface = value
            self._prepared_mesh = entry.mesh
            self._patch_faces = frozenset(self._surface.face_indices)
            self._object_id = entry.id
            self._centre_id = (
                centre_id
                if references is not None
                else self._surface.centres[0].feature_id
                if self._surface.centres
                else ""
            )
            self._seated_at_feature = True
            self._distance_valid = True
            self._settle()

        self.session.placement_async(compute, done, lambda _detail: done(None))

    def _begin_at_feature(self) -> None:
        """Beginnt dort, wo das gewählte Merkmal schon sitzt — ohne Klick (§18.5).

        **Wer ein bestehendes Merkmal bewegt, hat die Stelle nicht zu suchen.**
        Die Platzierung fing bis zum 10.09.2026 immer bei „Auf eine Oberfläche
        zeigen" an — richtig für ein Werkzeug, das noch nirgends sitzt, falsch
        für eine Bohrung, die schon da ist: Ihre Maße stehen fest, und der
        Kunde will sie sehen und ändern, nicht neu zielen (Robert, 10.09.2026:
        „die maße beim langloch ziehen und verschieben sind immer noch nicht da
        zu anderen merkmalen kanten mitten wie beim bohrung setzen").

        Was dafür fehlte, war die Fläche ohne Klick — ``placement.seat_of``
        liefert sie samt Mündung. Der Rest ist derselbe Weg wie nach einem
        Treffer (:meth:`_next_surface`), und er endet gleich in Stufe zwei: Die
        Stelle steht ja, offen sind die **Maße**.

        Wo es kein solches Merkmal gibt — jede Operation, die etwas Neues setzt
        —, geschieht hier nichts, und es bleibt beim Zeigen.
        """
        entry, feature = self._source_feature()
        if entry is None or self._surface is not None:
            return
        if feature is None:
            self._begin_on_a_face(entry)
            return
        stamp = self._serial
        object_id = entry.id
        # **Hier zielt der Zeiger nicht, und zwar von jetzt an.** Zwei Gründe,
        # und der zweite ist der dauerhafte: Bis die Fläche gerechnet ist,
        # verwirft jede Mausbewegung sie mit „Auf eine sichtbare Oberfläche
        # zeigen" wieder (gefunden am laufenden Fenster, 10.09.2026: Dialog
        # offen, Leiste „zeigen", kein Maß im Bild). Und danach gehört die
        # Stelle dem Merkmal — sie steht schon, offen sind die **Maße**. Wer
        # sie doch woanders hinsetzen will, klickt; siehe
        # :attr:`_seated_at_feature`.
        self._seated_at_feature = True
        mesh = for_a_worker(entry.mesh)
        values = self.dialog.values()
        target = None
        if self.spec_of().name in {"slot_hole", "resize_hole"} and all(
            isinstance(values.get(axis), int | float) for axis in ("x", "y", "z")
        ):
            target = np.asarray([values[axis] for axis in ("x", "y", "z")], dtype=float)

        def compute() -> Any:
            seat = placement.seat_of(mesh, feature, entry.features)
            if seat is None:
                return None
            prepared, mouth = seat
            if target is not None:
                # Die Fläche stammt vom bestehenden Loch; ein übergebener
                # Entwurf kann seine Mitte bereits versetzt haben. Die neue
                # Mündung behält denselben Abstand zur Mitte wie das Merkmal —
                # **in der Ebene der Fläche**: Ein Rest entlang der Normalen
                # (eine gerundete Feldzahl) hebt den Punkt von ihr ab, und
                # ``at_point`` sagte dann ab, als gäbe es keine Fläche.
                shift = target - np.asarray(feature.params["centre"], dtype=float)
                normal = np.asarray(prepared.frame.normal, dtype=float)
                point = np.asarray(mouth) + shift - normal * float(shift @ normal)
                mouth = (float(point[0]), float(point[1]), float(point[2]))
            return prepared, placement.at_point(prepared, mouth)

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed or not self.active or stamp != self._serial:
                return
            if value is None:
                self._no_seat_at_feature()
                return
            self._prepared, self._surface = value
            self._centre_id = self._surface.centres[0].feature_id if self._surface.centres else ""
            self._prepared_mesh = entry.mesh
            self._patch_faces = frozenset(self._surface.face_indices)
            self._object_id = object_id
            self._distance_valid = True
            self._set_values()
            self._settle()

        def failed(_detail: str) -> None:
            if isValid(self) and not self._disposed and self.active and stamp == self._serial:
                self._no_seat_at_feature()

        self.session.placement_async(compute, done, failed)

    def _no_seat_at_feature(self) -> None:
        """Zum vorhandenen Merkmal gibt es keine ebene Trägerfläche — und dann?

        **Im Dialog ein Rückfall auf den gewohnten Weg**: Eine Verrundung hat
        keine Trägerfläche, und ein Merkmal auf einer gekrümmten Fläche gibt
        keine ebenen Maße her; dort bleibt es beim Zeigen, statt eine Absage
        zu melden — und dann zielt wieder der Zeiger.

        **An der Maßgruppe im Bild nicht** (24.09.2026). Dort gehört die Stelle
        dem Merkmal (:attr:`_seated_at_feature`), und ein Zeiger, der zielt,
        verschob Bohrung und Langloch bei jeder Mausbewegung über dem Teil: am
        Schaber rückte die Magnettasche beim Zug an einem Langlochknopf um
        4,6 mm zur Seite und 3,5 mm in die Höhe, und *Übernehmen* blieb danach
        grau, ohne einen Satz. Die Felder bleiben dann die Bedienung, wie an
        einem Verlaufsschritt ohne belegten Sitz (:meth:`_begin_at_bore_step`),
        und der Hinweis sagt, dass es hier keine Flächenmaße gibt.
        """
        if not isinstance(self.dialog, QuietHost):
            self._seated_at_feature = False
            return
        self._measure_without_surface = True
        self._seated_at_feature = True
        self._refresh_measure_actions()
        self.redraw()

    def _begin_on_a_face(self, entry: SceneObject) -> None:
        """Ein Baustein sitzt sofort auf einer Fläche — ohne Klick, mit Griff.

        **Wer einen Baustein wählt, soll ihn sehen.** Bis zum 11.09.2026 zeigte
        die Platzierung ihn erst, wenn der Zeiger über einer Fläche stand; mit
        einem gewählten Körper und der Maus neben dem Teil stand nichts im
        Bild, und *Übernehmen* im Dialog schrieb einen roten Schritt („Es ist
        auch keine Position eingetragen"; Robert: „im viewport gab es weder
        vorschau, noch das gizmo dazu, kontrolliere mal alle Bausteine
        darauf"). Gemessen an allen 24 einsetzbaren Bausteinen — jeder verhielt
        sich so.

        Gesetzt wird auf die **gewählte** Fläche, wenn eine gewählt ist (sie
        steht als ``at_feature`` im Dialog), sonst auf die größte Fläche, die
        nach oben zeigt — die Oberseite einer Platte, der häufigste Ort. Die
        Stelle ist die Mitte der Fläche; liegt sie in einer Aussparung, ein
        Punkt daneben, der sicher auf ihr liegt. Was daraus wird, ist derselbe
        Weg wie nach einem Klick (:meth:`_settle`): Maßlinien, Felder, und der
        Griff am Körper (``viewport.grip_placement``) — nur dass ein Klick
        danach umsetzt statt zu übernehmen (:attr:`_seated_by_default`).

        **Nur für Bausteine.** Eine Bohrung wird gezielt gesetzt, und dieser
        Weg ist über Tage eingespielt; ein Baustein hat eine Grundfläche, die
        man sehen will, bevor man ihn irgendwohin schiebt. Ohne Körper mit
        einer solchen Fläche bleibt es beim Zeigen — der Rückfall, kein Fehler.
        """
        from app.core.knowledge.parts.ops import part_of

        if part_of(self.spec_of().name) is None:
            return
        # **Eine gewählte Bohrung geht vor der Fläche.** Vier Bausteine werden
        # *in* eine Bohrung gesetzt — Einpressbuchse, Mutternfalle, Lagersitz,
        # Gewinde —, und die gedruckte Schraube nirgends sonst. Wer eine
        # Bohrung anklickte und einen davon wählte, bekam ihn bis zum
        # 14.09.2026 trotzdem auf die Mitte der Deckfläche gesetzt, und
        # ``at_feature`` war dabei stumm geräumt: ``_face_to_seat_on`` fragt
        # nur nach Flächen, und eine Bohrung ist keine (gemessen an allen fünf
        # mit gewählter ``hole_1``, Sonde vom 14.09.2026). Die Fläche ohne
        # Klick liefert für ein Loch ``placement.seat_of`` — derselbe Weg, den
        # *Bohrung ändern* an einem vorhandenen Loch geht.
        hole = self._hole_to_seat_in(entry)
        face = self._face_to_seat_on(entry)
        if hole is None and (face is None or not face.face_indices):
            return
        stamp = self._serial
        object_id = entry.id
        first = int(face.face_indices[0]) if face is not None and face.face_indices else -1
        features = entry.features
        mesh = for_a_worker(entry.mesh)

        def compute() -> Any:
            from shapely.geometry import Point

            from app.core.sketch.planes import to_plane, to_world

            if hole is not None:
                seated = placement.seat_of(mesh, hole, features)
                if seated is not None:
                    prepared, mouth = seated
                    return prepared, placement.at_point(prepared, mouth), True
            # Ohne Trägerfläche an der Mündung (ein Loch in einer gewölbten
            # Wand) bleibt es bei der Fläche — der Rückfall, kein Fehler.
            if face is None or first < 0:
                return None
            prepared = placement.prepare_surface(mesh, first, features)
            area = prepared.area
            middle = area.centroid
            if not area.contains(middle):
                middle = area.representative_point()
            centre = face.params["centre"]
            flat = to_plane(prepared.frame, (float(centre[0]), float(centre[1]), float(centre[2])))
            if area.contains(Point(flat)):
                middle = Point(flat)
            seat = to_world(prepared.frame, (float(middle.x), float(middle.y)))
            return prepared, placement.at_point(prepared, seat), False

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed or not self.active or stamp != self._serial:
                return
            if value is None or self._surface is not None:
                return
            self._prepared, self._surface, in_the_hole = value
            self._centre_id = ""
            self._prepared_mesh = entry.mesh
            self._patch_faces = frozenset(self._surface.face_indices)
            self._object_id = object_id
            self._distance_valid = True
            self._seated_by_default = True
            self._set_values()
            self._settle()
            # Der Satz sagt, was hier anders ist als nach einem Klick: Der
            # Griff verschiebt, der Klick setzt um — und übernimmt nicht.
            self._note.setText(
                tr(
                    "Sitzt in der Bohrung · Griff: verschieben · Klick: umsetzen · "
                    "Übernehmen: ausführen · Esc: zurück"
                )
                if in_the_hole
                else tr(
                    "Sitzt auf der Fläche · Griff: verschieben · Klick: umsetzen · "
                    "Übernehmen: ausführen · Esc: zurück"
                )
            )

        def failed(_detail: str) -> None:
            # Eine Fläche, auf der nichts sitzen kann, ist kein Fehler: Dann
            # zielt der Zeiger, wie vor diesem Weg auch.
            return

        self.session.placement_async(compute, done, failed)

    def _hole_to_seat_in(self, entry: SceneObject) -> Feature | None:
        """Die Bohrung, in die ein Baustein von selbst gesetzt wird — sonst ``None``.

        Nur, wenn der Baustein in Bohrungen gehört (``PartSpec.at_hole``) und
        der Dialog eine als ``at_feature`` trägt: die angeklickte. Ein
        Schraubenloch auf eine Bohrung zu setzen ergäbe ein Loch im Loch, dort
        bleibt es bei der Fläche.
        """
        from app.core.knowledge.parts.ops import part_of

        part = part_of(self.spec_of().name)
        if part is None or not part.at_hole:
            return None
        wanted = str(self.dialog.values().get("at_feature") or "")
        chosen = entry.features.get(wanted)
        return chosen if chosen is not None and chosen.kind == "hole" else None

    def _face_to_seat_on(self, entry: SceneObject) -> Feature | None:
        """Die Fläche, auf die ein Baustein von selbst gesetzt wird.

        Die gewählte, wenn eine gewählt ist — der Dialog trägt sie als
        ``at_feature``. Sonst die größte, die nach oben zeigt: auf einer Platte
        die Oberseite. Zeigt keine nach oben (eine Kugel, ein Zylinder auf der
        Seite), gibt es keine — und der Zeiger zielt.
        """
        wanted = str(self.dialog.values().get("at_feature") or "")
        chosen = entry.features.get(wanted)
        if chosen is not None and chosen.kind == "face" and chosen.face_indices:
            return chosen
        best: Feature | None = None
        best_area = 0.0
        for feature in entry.features.values():
            if feature.kind != "face" or not feature.face_indices:
                continue
            normal = feature.params.get("normal")
            if normal is None or float(normal[2]) < UPWARD_FACE:
                continue
            area = float(feature.params.get("area") or 0.0)
            if best is None or area > best_area:
                best, best_area = feature, area
        return best

    def _dragged_at_the_tool(self, matrix: Any) -> None:
        """Ein Zug am Griff des Werkzeugkörpers setzt die Stelle um.

        Die Matrix ist die des Körpers **nach** dem Zug; ihre Verschiebung ist
        sein Ursprung, und der sitzt im Bild an der Stelle der Platzierung
        (``redraw`` legt ihn dorthin). Zurück in die Szene (§25), dann derselbe
        Weg wie vom Bewegungsgriff am Merkmal: :meth:`move_to` lotet in die
        Fläche und setzt Maßlinien und Felder nach. Liegt die Stelle neben der
        Fläche, springt der Körper zurück — gezeichnet wird, was gilt.
        """
        if self._disposed or not self.active or self._surface is None or self._deepening:
            return
        if self._grip_belongs_to_another_flow():
            return
        self._begin_edit()
        shown = np.asarray(matrix, dtype=np.float64)[:3, 3]
        point = self.viewport.scene_point_of(
            (float(shown[0]), float(shown[1]), float(shown[2])), self._object_id
        )
        if not self.move_to(point):
            self.redraw()

    def _invalid(self, message: str) -> None:
        self._surface = None
        self._commit_pending = False
        self._accept_pending = False
        self._note.setText(message)
        self._accept.setEnabled(False)
        self.redraw()

    def _set_values(self) -> bool:
        """Nur die vorberechnete Raumlage übertragen; im Qt-Thread keine Geometrie bauen."""
        if (
            self._change_op is not None
            and self._measure_group is not None
            and (not self._position_edited or self._measure_without_surface)
        ):
            # Die Mündung ist ein Maßbezug. Sie ersetzt weder ursprüngliche
            # Ausdrücke noch die Ankerlage einer durchgehenden Bohrung.
            return True
        if self._surface is None or self._tool_context is None:
            return False
        self._updating = True
        try:
            source, feature = self._source_feature()
            self.dialog.take_placement(
                placement.surface_values(
                    self.spec_of(),
                    self._surface,
                    feature=feature,
                    source=source,
                    prepared_tool=self._tool_context,
                )
            )
            return True
        finally:
            self._updating = False

    def _source_feature(self) -> tuple[SceneObject | None, Feature | None]:
        """Ein vorhandenes Merkmal gehört eindeutig zu einem Eingangskörper."""
        result = self._result
        if result is None:
            return None, None
        candidates = [
            entry
            for object_id, entry in result.scene.objects.items()
            if object_id in self.inputs_of()
        ]
        # **Und *Zum Langloch ziehen* gehört dazu** (10.09.2026): Es sitzt auf
        # einem Loch, das es schon gibt, führt dessen Mitte in x, y, z und
        # bekommt damit dieselbe Platzierung wie *Bohrung setzen* — mit
        # Maßfeldern zu Kanten und Mitten, und einer Änderung, die wirkt.
        if self.spec_of().name not in {
            "move_feature",
            "duplicate_feature",
            "slot_hole",
            "resize_hole",
        }:
            chosen = result.scene.objects.get(self._object_id)
            return chosen or (candidates[0] if len(candidates) == 1 else None), None
        feature_id = self.dialog.values().get("at_feature")
        found = [
            (entry, entry.features[feature_id])
            for entry in candidates
            if feature_id in entry.features
        ]
        return found[0] if len(found) == 1 else (None, None)

    def _dragged_in_preview(self, matrix: Any) -> None:
        """Ein Zug am Griff der Vorschau wird zu Zahlen im offenen Dialog.

        Der Griff liefert die Matrix **des Zugs** — was sich gegenüber der
        Lage beim Anhängen geändert hat. Die neue Lage ist deshalb der Zug
        über der alten, und aus ihr rechnet der Kern wieder Ort, Richtung und
        Winkel (:func:`~app.core.geom.primitive_ops.placement_values_of`, die
        Umkehrung von ``placement_transform``).

        **Beide Richtungen aus einer Quelle.** Der Hinweg legt die Querachse
        über ``frame_of`` fest; wer sie hier anders wählte, verdrehte den
        Körper bei jedem Zug ein Stück weiter. Der Test dazu ist eine
        Rundreise, kein Vergleich mit ausgerechneten Zahlen.
        """
        from app.core.geom.primitive_ops import placement_transform, placement_values_of

        spec = self.spec_of()
        if self._disposed or not _grips_its_preview(spec):
            return
        self._begin_edit()
        try:
            entered = expressions.resolve_params(
                self.dialog.values(), expressions.resolve(self.session.project.document.parameters)
            )
            before = np.asarray(placement_transform(spec.params(**entered)), dtype=float)
        except AppError, TypeError, ValueError:
            # **Ein unlesbarer Wert verwirft den Zug, er verschiebt nichts.**
            # Ohne die alte Lage gibt es keine neue: Der Griff meldet nur, was
            # sich geändert hat. Hier stand eine Einheitsmatrix als Rückfall —
            # sie hätte den Körper bei einem halb getippten Ausdruck in den
            # Nullpunkt gesetzt, und der Kommentar daneben behauptete das
            # Gegenteil. Der Zug geht verloren; der Körper bleibt, wo er ist.
            return
        values = placement_values_of(np.asarray(matrix, dtype=float) @ before)
        self._updating = True
        try:
            self.dialog.take_placement(values)
        finally:
            self._updating = False

    def cancel_pending_accept(self) -> None:
        """Eine jüngere Handlung verwirft den noch wartenden Übernehmen-Klick."""
        self._accept_pending = False

    def _values_changed(self) -> None:
        self._refresh_measure_fields()
        if not self._disposed and not self._updating:
            self._accept_pending = False
            self.refresh_available()
            if self.active:
                historical_measures = (
                    self._change_op is not None and self._measure_group is not None
                )
                if historical_measures:
                    # Eine neue Tiefe verschiebt bei Mittenanker die Mündung.
                    # Bis der aktuelle Sitz belegt ist, steht keine alte Hilfe.
                    if self._surface is not None:
                        self._held_references = self._surface.edges
                        self._held_centre = self._centre_id
                    self._serial += 1
                    self._surface = None
                    self._prepared = None
                    self._prepared_mesh = None
                    self._patch_faces = frozenset()
                    self._measure_without_surface = False
                    self._show_input_for_edit()
                self._request_tool()
                if historical_measures:
                    self._begin_at_bore_step()

    def _request_tool(self) -> None:
        if self._tool_busy:
            self._tool_again = True
            self._tool_context = None
            self.redraw()
            return
        spec = self.spec_of()
        source, feature = self._source_feature()
        # **Eine eigene Kopie**, denn gleich werden Achsen und Ort auf null
        # gesetzt: Der Schlüssel soll dieselbe Form beschreiben, gleich wo sie
        # steht. Der Träger gibt ein ``Mapping`` zurück — er verspricht nicht,
        # dass man hineinschreiben darf, und beim Dialog wäre es die Rechnung
        # eines fremden Feldes.
        values = dict(self.dialog.values())
        placed = placement_fields(spec.params)
        for name in (*(placed[axis] for axis in ("x", "y", "z")), *normal_fields(spec.params)):
            if name in values:
                values[name] = 0.0
        if placed["at_feature"] in values and feature is None:
            values[placed["at_feature"]] = ""
        if placed["axis"] in values:
            values[placed["axis"]] = "z"
        profile = for_object(self.session.profile, source)
        parameters = dict(self.session.project.document.parameters)
        key = repr(
            (
                spec.name,
                values,
                parameters,
                profile,
                id(source.mesh) if source is not None else None,
            )
        )
        if key == self._tool_key and self._tool_context is not None:
            return
        epoch = self._epoch
        self._tool_busy = True
        self._tool_again = False
        self._tool_context = None
        self.redraw()

        def compute() -> Any:
            resolved = expressions.resolve(parameters)
            entered = expressions.resolve_params(values, resolved)
            return placement.prepare_tool(
                spec, entered, profile, source=source, feature=feature, parameters=resolved
            )

        def done(context: placement.PlacementTool | None) -> None:
            if not isValid(self) or self._disposed:
                return
            self._tool_busy = False
            if self.active and epoch == self._epoch and not self._tool_again:
                renderer = self.viewport.renderer
                if renderer is not None:
                    self._remove_tools()
                    # **Wo ein Umriss die Stelle zeigt, tritt der Körper
                    # zurück.** Er bleibt für alles, was keinen hat — ein
                    # Baustein, dessen Mündung nicht in der Fläche liegt —,
                    # und für die Tiefe: die sieht man nur an ihm, und
                    # eingestellt wird sie im Dialog, nicht hier (Robert,
                    # 09.09.2026: „höchstens dann, wenn man die Tiefe noch
                    # einstellt, wäre die andere Ansicht interessant").
                    if context is not None:
                        mesh = context.mesh
                        addition = context.addition
                        colours = DIFF_PALETTES[
                            getattr(self.viewport, "_diff_palette", "blue_orange")
                        ]
                        self._tool = renderer.add_surface(
                            np.asarray(mesh.raw.vertices, dtype=np.float64),
                            np.asarray(mesh.raw.faces, dtype=np.int64),
                            name="surface_placement_tool",
                            style=SurfaceStyle(
                                colour=colours.removed.colour
                                if addition is not None
                                else self.viewport._object_colour,
                                opacity=0.45,
                                show_edges=False,
                                pickable=False,
                                keep_in_front=True,
                            ),
                        )
                        if addition is not None:
                            self._addition = renderer.add_surface(
                                np.asarray(addition.raw.vertices, dtype=np.float64),
                                np.asarray(addition.raw.faces, dtype=np.int64),
                                name="surface_placement_addition",
                                style=SurfaceStyle(
                                    colour=colours.added.colour,
                                    opacity=0.85,
                                    show_edges=False,
                                    pickable=False,
                                    keep_in_front=True,
                                ),
                            )
                            self._tool_legend.setText(f"+ {tr('Hinzugefügt')} · - {tr('Entfernt')}")
                            self._tool_legend.show()
                        self._tool_context = context
                        self._tool_key = key
                        self._set_values()
                    else:
                        self._note.setText(
                            tr(
                                "Vorschau nicht verfügbar. "
                                "Die Werte bearbeiten und erneut platzieren."
                            )
                        )
                self.redraw()
            if self._tool_again and self.active:
                self._request_tool()
            elif self._accept_pending and self.active:
                self._accept_pending = False
                if not self.dialog.preview_required and not self.dialog.requires_displayed_preview:
                    self.accept()

        self.session.placement_async(compute, done, lambda _detail: done(None))

    def _reference_entries(self, index: int) -> list[tuple[str, tuple[str, str]]]:
        """Menü und Modellwahl verwenden dieselben belegten Referenzen."""
        if self._surface is None or self._prepared is None:
            return []
        entries = (
            [(identifier, "centre") for identifier, _ in self._prepared.centres]
            if index == 2
            else [(edge.id, edge.kind) for edge in self._prepared.edges]
        )
        return [
            (self._reference_name(kind, number), (identifier, kind))
            for number, (identifier, kind) in enumerate(entries, 1)
        ]

    def _reference_field(self, index: int) -> QWidget:
        """Das Maß, an dem der Bezug mit dem Index hängt: zwei Kanten, eine Mitte."""
        return (*self._measures, self._centre)[index]

    def _reference_menu(self, index: int, at: QPoint | None = None) -> QMenu | None:
        """Rechtsklick oder Menütaste auf einem Maß: den Bezug wechseln (RM-197).

        Ein Zahlenfeld behält dabei sein gewohntes Menü — Kopieren, Einfügen,
        Schritt auf und ab —, die Bezüge stehen darunter. Gebaut je Aufruf,
        gezeigt über ``popup`` statt ``exec``: Ein ``exec`` hielte die
        Ereignisschleife des Flusses an, und offscreen wartete es auf einen
        Klick, den es nie gibt. Weggeräumt, sobald es zugeht
        (`app/ui/CLAUDE.md`, „Ein Kontextmenü gehört seinem Klick").
        """
        entries = self._reference_entries(index)
        if not entries or not self.active:
            return None
        field = self._reference_field(index)
        line = field.lineEdit() if isinstance(field, QAbstractSpinBox) else None
        menu = line.createStandardContextMenu() if line is not None else QMenu(field)
        if line is not None:
            menu.addSeparator()
        menu.addSection(tr("Bezug ändern"))
        pick = menu.addAction(tr("Im Modell wählen"))
        pick.setData(_PICK_IN_MODEL)
        for label, data in entries:
            menu.addAction(label).setData(data)
        menu.triggered.connect(
            lambda action, slot=index: self._reference_selected(slot, action.data())
        )
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(field.mapToGlobal(at if at is not None else QPoint(0, field.height())))
        return menu

    @staticmethod
    def _reference_name(kind: str, number: int) -> str:
        names = {
            "outer": tr("Außenkante {number}"),
            "inner": tr("Innenkante {number}"),
            "axis": tr("Achse {number}"),
            "centre": tr("Mitte {number}"),
        }
        return names[kind].format(number=number)

    def _reference_selected(self, index: int, data: object) -> None:
        """Eine bewusste Wahl ändert nur den Bezug, niemals die Geometrie."""
        if data is None or self._surface is None or self._prepared is None:
            return
        self._begin_edit()
        self._accept_pending = False
        if data == _PICK_IN_MODEL:
            self._pending = None
            self._serial += 1
            self._reference_pick = index
            self._reference_message = tr(
                "Auf den gewünschten Bezug dieser Fläche klicken "
                "oder ihn mit Rechtsklick auf das Maß wählen."
            )
            self._show_input_for_edit()
            self.redraw()
            return
        if isinstance(data, tuple) and len(data) == 2:
            self._choose_reference(index, str(data[0]), str(data[1]))

    def _choose_reference(self, index: int, identifier: str, kind: str) -> None:
        if self._surface is None or self._prepared is None:
            return
        try:
            if kind == "centre":
                if not any(centre.feature_id == identifier for centre in self._surface.centres):
                    return
                self._centre_id = identifier
            else:
                self._surface = placement.with_reference(
                    self._prepared, self._surface, index, identifier
                )
        except ValidationError as problem:
            # Der Satz kommt aus dem Kern (`placement._reference_error`), damit
            # Bild, Kommandozeile und Agent dieselbe Absage lesen.
            self._reference_message = str(problem.detail or problem.title)
            self.redraw()
            return
        self._reference_pick = None
        self._reference_message = tr("Bezug geändert; die Position bleibt unverändert.")
        self._frozen = True
        self._pending = None
        self._serial += 1
        self.redraw()
        # Der historische Eingangswechsel hat die vorige Anzeige entwertet.
        # Derselbe unveränderte Wertauftrag fordert wieder seine volle Vorschau.
        self.dialog.valuesChanged.emit()

    def _cancel_reference_pick(self) -> bool:
        """Den Bezugswahlmodus verlassen, ohne den Entwurf zu verwerfen — wahr, wenn einer lief.

        Der Modus wartet auf einen Klick auf den gewünschten Bezug
        (:meth:`_reference_selected` mit ``_PICK_IN_MODEL``). Ein Escape darin
        meint „doch nicht" und nicht „alles zurück": Die Maße, die Stelle und
        der bisherige Bezug bleiben, nur die Wartestellung geht.
        """
        if self._reference_pick is None:
            return False
        self._reference_pick = None
        self._reference_message = tr("Bezugswahl abgebrochen; der bisherige Bezug bleibt.")
        self.redraw()
        return True

    def _pick_reference(self, x: int, y: int) -> None:
        """Nur die sichtbare ursprüngliche Trägerfläche ist ein zulässiger Treffer."""
        if self._reference_pick is None or self._prepared is None or not self._display_ready():
            return
        hit = self.viewport.placement_hit(x, y)
        if hit is None:
            return
        object_id, point, cell, ray = hit
        if object_id != self._object_id or (
            ray is None and cell not in self._prepared.face_indices
        ):
            self._reference_message = tr(
                "Auf den gewünschten Bezug dieser Fläche klicken "
                "oder ihn mit Rechtsklick auf das Maß wählen."
            )
            self.redraw()
            return
        index = self._reference_pick
        prepared = self._prepared
        # Logikpunkte mal Millimeter je Gerätepixel: Dazwischen steht das
        # Geräteverhältnis, sonst fängt der Bezug bei 200 Prozent Skalierung
        # nur halb so weit wie beim Tiefenfang weiter unten.
        distance = SNAP_PIXELS * self.viewport._device_ratio() * self._millimetres_per_pixel()
        if ray is None:
            self._reference_hit_ready(
                index, placement.reference_candidates(prepared, point, distance)
            )
            return
        entry = self._result.scene.objects.get(object_id)
        if entry is None:
            return
        mesh = for_a_worker(entry.mesh)
        clip_planes = tuple(plane for plane in self.viewport._section_planes() if plane is not None)
        self._serial += 1
        stamp = self._serial

        def compute() -> Any:
            original = placement.original_surface_hit(mesh, *ray, clip_planes=clip_planes)
            return (
                ()
                if original is None
                else placement.reference_candidates(prepared, original[1], distance, ray=ray)
            )

        def done(candidates: Any) -> None:
            if (
                isValid(self)
                and not self._disposed
                and self.active
                and stamp == self._serial
                and self._reference_pick == index
            ):
                self._reference_hit_ready(index, candidates)

        self.session.placement_async(compute, done, lambda _detail: done(()))

    def _reference_hit_ready(self, index: int, candidates: tuple[tuple[str, str], ...]) -> None:
        """Eine belegte Modellwahl abschließen, niemals den Maßentwurf übernehmen."""
        candidates = tuple(
            (identifier, kind)
            for identifier, kind in candidates
            if (kind == "centre") == (index == 2)
        )
        if len(candidates) == 1:
            self._choose_reference(index, *candidates[0])
        else:
            # Kein nächster Kandidat gewinnt eine Gleichlage. Der Satz nennt
            # den Weg zur vollständigen Liste; von selbst öffnet sich kein
            # Menü — ein ``exec`` aus einem Arbeiterrückruf hielte den Fluss
            # an, und die Modellwahl bleibt scharf.
            self._reference_message = tr(
                "Hier ist kein eindeutiger Bezug getroffen. "
                "Näher heranzoomen oder mit Rechtsklick auf das Maß auswählen."
            )
            self.redraw()

    def _invalid_distance(self, message: str) -> None:
        """Ungültige Abstände erklären und beide Abschlüsse unmittelbar sperren."""
        self._distance_valid = False
        self._distance_message = message
        self._note.setText(message)
        self._accept.setEnabled(False)
        self._refresh_measure_actions()

    def _distance_changed(self, _value: float) -> None:
        self._reference_message = ""
        self._reference_pick = None
        self._accept_pending = False
        if not self.active or self._surface is None or len(self._surface.edges) < 2:
            return
        try:
            changed = placement.point_with_distances(
                self._prepared,
                self._surface,
                (self._measures[0].value_mm(), self._measures[1].value_mm()),
            )
        except ValidationError, ValueError, ArithmeticError:
            self._invalid_distance(
                tr("Diese Abstände liegen außerhalb der Fläche. Kleinere Werte eingeben.")
            )
            return
        self._frozen = True
        self._distance_valid = True
        self._pending = None
        self._serial += 1
        self._surface = changed
        self._position_edited = True
        self._set_values()
        self._note.setText(tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten."))
        self.redraw()

    def _centre_changed(self, _value: float) -> None:
        """Beide signierten Maße halten dieselbe gewählte Mitte als Bezug."""
        self._accept_pending = False
        self._reference_message = ""
        self._reference_pick = None
        if not self.active or self._surface is None or not self._centre_id:
            return
        try:
            changed = placement.point_with_centre(
                self._prepared,
                self._surface,
                self._centre_id,
                (self._centre_measures[0].value_mm(), self._centre_measures[1].value_mm()),
            )
        except ValidationError, ValueError, ArithmeticError:
            self._invalid_distance(
                tr("Diese Abstände liegen außerhalb der Fläche. Andere Werte eingeben.")
            )
            return
        self._frozen = True
        self._distance_valid = True
        self._pending = None
        self._serial += 1
        self._surface = changed
        self._position_edited = True
        self._set_values()
        self._note.setText(tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten."))
        self.redraw()

    def move_to(self, point: Vec3, *, on_plane_only: bool = False) -> bool:
        """Die Platzierung an einen Punkt setzen — von außen, etwa vom Griff.

        **Der Zug am Bewegungsgriff und die Maßlinien meinen dieselbe Stelle.**
        Er schlägt eine Mitte vor (``viewport.featureMoveProposed``), die
        Felder rechts nehmen sie — und die Maßlinien im Bild sollen sie
        zeigen, nicht die Stelle von vorher. Der Punkt wird in die Ebene der
        Fläche gelotet: Der Griff sitzt auf halber Tiefe des Lochs, die
        Maßlinien auf seiner Mündung, und ein Zug entlang der Achse hat auf
        der Fläche keinen Ort (die Felder rechts tragen ihn trotzdem).

        Liegt die Stelle nicht auf der Fläche, bleibt alles, wie es war;
        gesagt hat es dann schon der Griff mit seinem Schatten.

        Bei ``on_plane_only`` bleibt die getippte Tiefe verbindlich. Eine
        Änderung entlang der Flächennormalen übernimmt die normale Feldvorschau.
        """
        self._accept_pending = False
        if not self.active or self._surface is None or self._prepared is None:
            return False
        frame = self._prepared.frame
        origin = np.asarray(frame.origin, dtype=np.float64)
        normal = np.asarray(frame.normal, dtype=np.float64)
        given = np.asarray(point, dtype=np.float64)
        if on_plane_only:
            fields = placement_fields(self.spec_of().params)
            values = self.dialog.values()
            current = np.asarray([values[fields[axis]] for axis in ("x", "y", "z")], dtype=float)
            if abs(float(np.dot(given - current, normal))) > EPS_GEOM:
                return False
        levelled = given - float(np.dot(given - origin, normal)) * normal
        try:
            changed = placement.at_point(
                self._prepared,
                (float(levelled[0]), float(levelled[1]), float(levelled[2])),
                references=self._surface.edges,
            )
        except ValidationError, ValueError, ArithmeticError:
            return False
        self._frozen = True
        self._distance_valid = True
        self._pending = None
        self._serial += 1
        self._surface = changed
        self._position_edited = True
        self._set_values()
        self._note.setText(tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten."))
        self.redraw()
        return True

    def _settle(self) -> None:
        """Der Klick legt die Stelle fest — und danach stehen die Maße offen.

        **Drei Stufen statt zweier** (Robert, 09.09.2026: „beim klick sollte
        man die maße dann einstellen die man sieht, dann in die seitenansicht
        erst nachdem man das bestätigt hat und die tiefe einstellen"). Der
        Klick war bis dahin die ganze Platzierung: Er nahm die Stelle **und**
        schloss ab, mit allen Vorgaben, die daran hingen — bei einer Bohrung
        also mit ``depth = 0``, was durch das ganze Teil heißt.

        Jetzt hält er an. Die Abstände zu den Kanten stehen als Zahlenfelder da
        und lassen sich eintippen; erst das Übernehmen führt weiter — zur
        Tiefe, wo es eine gibt, und sonst zum Ergebnis.
        """
        self._frozen = True
        self._commit_pending = False
        self._pending = None
        self._serial += 1
        self._accept.setText(tr("Weiter zur Tiefe") if self.deepens() else tr("Übernehmen"))
        self._note.setText(
            tr("Maße einstellen · Übernehmen: weiter zur Tiefe · Esc: zurück")
            if self.deepens()
            else tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten.")
        )
        self.redraw()

    def deepens(self) -> bool:
        """Ob nach dem Klick noch eine Tiefe einzustellen ist.

        Zwei Bedingungen, und beide sind nötig. **Das Werkzeug muss auf etwas
        sitzen**: Ein Quader trägt ein Feld namens ``depth``, und das ist seine
        Bauteiltiefe und keine Eindringtiefe — genau die Verwechslung, vor der
        ``placement_fields`` warnt. **Und es muss eine Tiefe führen**: Ein
        Lochwand-Einhänger hat keine und ist mit dem Ort fertig.
        """
        spec = self.spec_of()
        return starts_by_itself(spec) and self._depth_name() is not None

    def _depth_name(self) -> str | None:
        """Das Feld der Eindringtiefe — oder ``None``, wo es keine gibt.

        Vier Stellen stellen dieselbe Frage; gestellt wird sie einmal, mit den
        **Werten des Dialogs**. Die zählen: Ob eine Beschriftung erhaben oder
        eingelassen ist, entscheidet ihr ``mode``, und nur im zweiten Fall geht
        der Zug nach unten ins Material.
        """
        spec = self.spec_of()
        try:
            values = spec.params(**self.dialog.values())
        except TypeError, ValueError, ValidationError:
            # Ein halb ausgefüllter Dialog ist der Normalfall, solange jemand
            # tippt — dann entscheidet die Vorgabe, nicht ein Fehler.
            values = None
        return depth_field(spec.name, spec.params, values)

    def accept(self) -> None:
        """Der gemeinsame Knopf liest alle Felder und versucht den Abschluss."""
        self._accept_values(allow_pending=True)

    def _accept_values(self, *, allow_pending: bool) -> None:
        """Ein früher Tastendruck wird unter keinen Umständen nachgeholt."""
        self._accept_pending = False
        if (
            self._disposed
            or not self.active
            or self._reference_pick is not None
            or not self._interpret_active_fields()
        ):
            return
        if (
            not self.active
            or not self.session.result_current
            or not self._display_ready()
            or (self._surface is None and not self._measure_without_surface)
        ):
            return
        if self._tool_busy and not self._measure_without_surface:
            # Der Knopf im Merkmalfenster bleibt erreichbar, während eine
            # neue Maßangabe ihr Werkzeug vorbereitet. Sein Klick gehört dem
            # fertigen Werkzeug; Abbruch und neuere Eingaben löschen ihn.
            self._accept_pending = (
                allow_pending
                and self.dialog.values_stand_elsewhere
                and self._distance_valid
                and not self.dialog.preview_required
                and not self.dialog.requires_displayed_preview
            )
            return
        if not self._measure_without_surface and (
            self._tool is None or self._tool_context is None or not self._accept.isEnabled()
        ):
            return
        self._accept_pending = False
        # **Ein wartender Langlochzug geht vor.** Die Gruppe ist an *Bohrung
        # ändern* gebunden; der Zug wird über denselben Weg eingelöst wie das
        # Übernehmen im Merkmalfenster (``MainWindow._apply_placed_feature``),
        # mit der Stelle aus den Feldern — die Sperre der gebundenen Handlung
        # („hat bereits diesen Durchmesser") gilt ihm nicht.
        apply_placed = getattr(self.window, "_apply_placed_feature", None)
        if apply_placed is not None and self._slot_drag_takes_the_accept():
            # Die Stelle kommt aus der Fläche, ohne den Träger zu beschreiben:
            # ``take_placement`` meldete Werte, und die Meldung band die
            # gebundene Handlung neu — nach dem Langlochauftrag, über ihn.
            values = dict(self.dialog.values())
            if self._surface is not None and self._tool_context is not None:
                source, feature = self._source_feature()
                placed = placement.surface_values(
                    self.spec_of(),
                    self._surface,
                    feature=feature,
                    source=source,
                    prepared_tool=self._tool_context,
                )
                # Nur, was die Operation kennt — dieselbe Grenze wie
                # ``QuietHost.take_placement``: ``surface_values`` liefert auch
                # ``nx``/``ny``/``nz``, und *Bohrung ändern* lehnt sie ab
                # („Diesen Parameter gibt es bei dieser Operation nicht",
                # Review 22.09.2026).
                known = {entry.name for entry in self.spec_of().params.spec()}
                values.update({name: value for name, value in placed.items() if name in known})
            # Während des Abschlusses sind Befehle erlaubt, wie beim Übernehmen
            # des Trägers selbst (``MainWindow._quiet_selection_allowed``) —
            # sonst hielte die begonnene Änderung ihren eigenen Langlochschritt an.
            host = self.dialog
            was_committing = getattr(host, "committing", False)
            if isinstance(host, QuietHost):
                host.committing = True
            try:
                apply_placed(self.spec_of().name, values)
            finally:
                if isinstance(host, QuietHost):
                    host.committing = was_committing
            return
        # **Der Klick legt die Stelle fest, nicht das ganze Loch.** Wer eine
        # Bohrung setzt, hat danach noch eine Tiefe einzustellen; bis zum
        # 09.09.2026 wurde sie mit der Vorgabe gesetzt — bei ``depth = 0``
        # heißt das durch das ganze Teil, ohne dass jemand gefragt hätte
        # (Robert: „oder ich bohr komplett durch ohne die tiefenbearbeitung").
        if self.deepens() and not self._deepening and self._measure_group is None:
            self._begin_depth()
            return
        if not self._set_values():
            return
        # Die endgültigen Werte können gerade eine neue Vorschau angefordert
        # haben. Ihre Sperre wird geprüft, bevor die Platzierung verschwindet.
        if not self.dialog.can_accept():
            # **Der frühe Klick hängt an der Vorschau, statt zu verfallen.**
            # Der Träger meldet ihn dem Fenster (``preview_defer``), und das
            # übernimmt, sobald das Bild steht — genau einmal.
            defer = getattr(self.dialog, "preview_defer", None)
            if defer is not None:
                defer()
            return
        self.dialog.accept()

    # --- Stufe 2: die Tiefe ----------------------------------------------------

    def _begin_depth(self) -> None:
        """Die Stelle steht; jetzt zieht die Maus die Tiefe.

        **Was die zweite Stufe zeigt, kann die erste nicht.** Der Umriss auf
        der Fläche sagt, *wo* das Loch hinkommt, und über die Tiefe schweigt
        er; deshalb tritt hier der Werkzeugkörper wieder vor, und das Modell
        wird durchscheinend, damit man ihn darin sieht (Robert, 09.09.2026:
        „wenn wir klicken wollen wir die bohrung von der seitenansicht sehen
        und dann die tiefe runterziehen").

        Der gemerkte Klick ist damit verbraucht: ``_commit_pending`` fällt,
        sonst wäre der bestätigende Klick der Stufe ausgesperrt.
        """
        self._deepening = True
        self._depth_set = False
        self._commit_pending = False
        self._pending = None
        self._frozen = True
        self._show_the_body_from_the_side()
        # **Der Maßstab wird nach dem Schwenk gemessen, nicht davor.** Die
        # Ansicht rechnet perspektivisch, der Maßstab hängt also am Abstand zur
        # Kamera — und ``_look_along_the_surface`` stellt sie gerade erst auf
        # ihren neuen Abstand. Davor gemessen war der Faktor von der ersten
        # Bewegung an falsch.
        self._depth_per_pixel = self._millimetres_per_pixel()
        # **Und die Stufe beginnt mit einer Tiefe.** Stand im Feld die Null,
        # hieße „übernehmen, ohne zu ziehen" wieder: durch das ganze Teil, und
        # genau das sollte diese Stufe abschaffen (Robert, 09.09.2026: „die
        # bohrung ist aber sofort komplett durch"). Vorbelegt wird mit dem
        # Material unter der Mündung — dieselbe Wirkung wie bisher, aber als
        # Zahl, die dasteht und die man hochziehen kann.
        if self._depth_now(self._depth_name()) <= EPS_GEOM:
            self._set_depth(max(LEAST_DEPTH_MM, self._material_below()))
        self._note.setText(
            tr("Maus bewegen: Tiefe · Klick: übernehmen · Maßfeld: Zahl eingeben · Esc: zurück")
        )
        # Nicht „Bohrung": Acht Operationen erreichen diese Stufe, darunter
        # eine eingelassene Beschriftung und eine Tasche. Das Wort benennt,
        # worum es hier geht, und das ist die Tiefe.
        self._accept.setText(tr("Tiefe übernehmen"))
        self.redraw()

    def _millimetres_per_pixel(self) -> float:
        """Wie viele Millimeter ein Bildpunkt Zug bedeutet.

        Aus dem Maßstab der Ansicht, damit der Zug am kleinen wie am großen
        Teil dasselbe Gefühl hat: Ein fester Faktor zöge bei einem Teil von
        zehn Millimetern durch das ganze Stück, während er an einem von
        dreihundert kaum etwas täte. Findet die Ansicht keinen Maßstab, bleibt
        ein Zehntelmillimeter je Punkt — die Zahl steht daneben und lässt sich
        eintippen.
        """
        if self._surface is None or self.viewport.renderer is None:
            return 0.1
        # **`_pixels_per_mm_at` und nicht `pixels_per_mm`.** Die zweite nimmt
        # einen ``PlaneFrame`` und ist die des Skizzeneditors; mit einem Punkt
        # gefüttert wirft sie. Der erste Anlauf fing das mit ``except
        # Exception`` ab und fiel auf einen Zehntelmillimeter je Bildpunkt
        # zurück — an einem 20-mm-Teil bei zwölf Punkten je Millimeter das
        # Hundertfache dessen, was der Zeiger anzeigt (Robert, 09.09.2026:
        # „bei weiter zur tiefe passt wohl die mausposition zur darstellung
        # noch nicht ganz"). Ein stiller Rückfall verschluckt genau solche
        # Fehler; gefragt wird deshalb ohne ihn.
        scale = self.viewport._pixels_per_mm_at(tuple(self._surface.point))
        if scale is None or scale <= 1e-9:
            return 0.1
        return 1.0 / float(scale)

    def _show_the_body_from_the_side(self) -> None:
        """Modell durchscheinend, Werkzeug sichtbar — der Blick in das Loch.

        Zurückgestellt wird beides in :meth:`_stop`; die Darstellungsart ist
        eine Einstellung des Nutzers (`ansicht.md`, „Was die Ansicht sich
        merkt"), und eine geliehene Ansicht gibt man zurück.
        """
        # Direkt gefragt, nicht über ``getattr`` mit stillem Rückfall: Fehlte
        # der Setzer, bliebe die Ansicht wortlos für immer durchscheinend.
        self._display_before = self.viewport.display_mode
        self.viewport.set_display_mode("transparent")
        for item in (self._tool, self._addition):
            if item is not None:
                item.set_visible(True)
        self._look_along_the_surface()

    def _look_along_the_surface(self) -> None:
        """Die Kamera quer zur Werkzeugachse — der Blick von der Seite.

        Robert, 09.09.2026: „wenn wir klicken wollen wir die bohrung von der
        seitenansicht sehen und dann die tiefe runterziehen". Von vorn auf die
        Mündung gesehen ist eine Tiefe nicht zu beurteilen; quer dazu ist sie
        die Länge, die man zieht.

        Gedreht wird **um die Stelle**, und Abstand wie Bildausschnitt bleiben:
        Wer auf ein Detail gezoomt hat, will es weiter sehen — dieselbe Zusage
        wie bei den Kameravorgaben (`ansicht.md`, „Eine Kameravorgabe dreht um
        den Blickpunkt, sie passt nicht ein").
        """
        if self._surface is None or self.viewport.renderer is None:
            return
        axis = np.asarray(self._surface.frame.normal, dtype=np.float64)
        length_of = float(np.linalg.norm(axis))
        if length_of < 1e-9:
            return
        axis = axis / length_of
        spot = np.asarray(self.viewport.view_point_of(self._surface.point, self._object_id))
        # **Vier Werte, nicht drei.** ``camera_pose`` gibt zusätzlich den
        # Parallelmaßstab zurück, und der wird unverändert weitergereicht —
        # sonst springt in orthografischer Projektion der Bildausschnitt.
        found = self.viewport.camera_pose()
        if self._camera_before is None:
            self._camera_before = found
        position = np.asarray(found[0], dtype=np.float64)
        focus = np.asarray(found[1], dtype=np.float64)
        scale = found[3]
        away = float(np.linalg.norm(position - focus))
        if away < 1e-9:
            return
        # **Die Blickrichtung steht senkrecht auf der Achse und waagerecht in
        # der Welt.** Von der bisherigen Sicht bleibt nur, *von welcher Seite*
        # man schaut — der Anteil entlang der Achse fällt weg, und damit die
        # Schräge von oben. Der erste Anlauf zog nur die Achse ab und ließ die
        # Kamera dort, wo sie war; im Bild war das eine leicht gekippte
        # Draufsicht und keine Seitenansicht (Robert, 09.09.2026:
        # „seitenansicht ist das auch nicht ganz").
        sideways = position - focus
        sideways = sideways - axis * float(sideways @ axis)
        if float(np.linalg.norm(sideways)) < 1e-6:
            # Der Blick steht genau auf der Achse: irgendeine Querrichtung tut es.
            helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            sideways = np.cross(axis, helper)
        # Und waagerecht: Steht die Achse aufrecht, liegt die Kamera auf
        # Augenhöhe der Mündung — sonst bliebe die Schräge, aus der man die
        # Tiefe nicht ablesen kann.
        upright = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if abs(float(axis @ upright)) > 0.9:
            sideways[2] = 0.0
            if float(np.linalg.norm(sideways)) < 1e-6:
                sideways = np.array([0.0, -1.0, 0.0], dtype=np.float64)
        sideways = sideways / float(np.linalg.norm(sideways)) * away
        at = spot + sideways
        self.viewport.set_camera_pose(
            (float(at[0]), float(at[1]), float(at[2])),
            (float(spot[0]), float(spot[1]), float(spot[2])),
            (float(axis[0]), float(axis[1]), float(axis[2])),
            scale,
        )
        self.viewport.settle_camera()

    def _deepen_to(self, x: int, y: int) -> None:
        """Die Tiefe aus der Zeigerstrecke — gemessen vom Beginn, nicht summiert.

        Eine Summe aus Einzelschritten driftet, sobald ein Ereignis ausfällt;
        die Strecke vom Startpunkt kann das nicht. Nach unten heißt tiefer, wie
        Robert es beschrieben hat („die tiefe runterziehen").
        """
        # **Nicht am Werkzeugkörper hängen.** Jede gesetzte Tiefe stößt einen
        # Neubau der Vorschau an, und der setzt ``_tool_context`` für seine
        # Dauer auf ``None``: Mit ihm in dieser Bedingung fiel jede zweite
        # Bewegung aus, die Zahl blieb stehen und der Zug ruckelte. Gerechnet
        # wird aus der Fläche und der Kamera — der Werkzeugkörper ist das Bild
        # dazu und keine Voraussetzung.
        if self._surface is None:
            return
        name = self._depth_name()
        if name is None:
            return
        renderer = self.viewport.renderer
        if renderer is None:
            return
        # **Die Spitze liegt unter dem Zeiger, nicht irgendwo.** Der erste
        # Anlauf zählte die Strecke seit dem Beginn des Zugs zusammen; wo der
        # Zeiger stand, hatte damit nichts mit der Tiefe zu tun, und man zog am
        # unteren Rand, während die Bohrung kaum begonnen hatte (Robert,
        # 09.09.2026: „ich hab den mauszeiger kurz über den unteren panel aber
        # eigentlich müsste ich viel weiter oben sein"). Gemessen wird deshalb
        # **absolut**: der Abstand des Zeigers von der Mündung, im Bild,
        # entlang der Bohrachse.
        mouth = renderer.world_to_display(
            tuple(self.viewport.view_point_of(self._surface.point, self._object_id))
        )
        along = self._axis_on_screen()
        if along is None:
            return
        # **Der Maßstab wird je Bewegung neu gemessen, nicht einmal beim
        # Betreten.** Zoomen bleibt in dieser Stufe frei (`app/ui/CLAUDE.md`,
        # „Drehen, Zoomen und Kippen bleiben frei"), und die Ansicht rechnet
        # perspektivisch: Nach einem Zoom um den Faktor k wäre eine eingefrorene
        # Zahl um k daneben, und die Spitze läge nicht mehr unter dem Zeiger.
        # Die Bildrichtung der Achse (``_axis_on_screen``) wird aus demselben
        # Grund schon immer hier gerechnet; der Maßstab war die Hälfte, die
        # stehen geblieben ist.
        self._depth_per_pixel = self._millimetres_per_pixel()
        # Die Strecke vom Mündungspunkt zum Zeiger, auf die Bildrichtung der
        # Achse projiziert: So weit ist die Spitze unter dem Zeiger.
        #
        # **Alles hier zählt in Gerätepixeln, und zwar durchgehend.**
        # ``PointerEvent.x/y`` kommen bereits so (der Renderer multipliziert
        # beim Erzeugen), ``world_to_display`` liefert sie ebenso, und
        # ``_pixels_per_mm_at`` misst darin. Der erste Anlauf rechnete das
        # Verhältnis an dieser Zeile noch einmal hinein und danach wieder
        # heraus — bei einem Bildschirm ohne Skalierung fällt das nie auf, bei
        # 125 Prozent bleibt ein Versatz, der von der Bildlage der Bohrung
        # abhängt (`ansicht.md`, „Wer die Umrechnung an einer Zeichenstelle
        # wiederholt, rechnet doppelt").
        reach = (x - float(mouth[0])) * along[0] + (y - float(mouth[1])) * along[1]
        # **Nicht bis auf null.** Bei ``depth = 0`` bohrt die Operation durch
        # das ganze Teil (`prepare_ops.py`, „Null bohrt durch das ganze Teil") —
        # wer den Zeiger nach oben zieht, um die Bohrung *flacher* zu machen,
        # bekäme am Ende des Wegs das Gegenteil. Der Zug hält deshalb bei einem
        # zehntel Millimeter an; wer wirklich durch will, zieht nach unten oder
        # tippt die Null ins Feld.
        wanted = max(LEAST_DEPTH_MM, reach * self._depth_per_pixel)
        # **Kurzes Einrasten an den Stellen, die etwas bedeuten** (Robert,
        # 09.09.2026). Die Zone steht in logischen Bildpunkten wie jede
        # Fangweite der Oberfläche und wird über das Geräteverhältnis in
        # Millimeter gebracht — dieselbe Rechnung wie in
        # ``Viewport._snap_radius_at``.
        zone = SNAP_PIXELS * self.viewport._device_ratio() * self._depth_per_pixel
        self._set_depth(snap_to_marks(wanted, self._depth_marks(), zone))

    def _depth_marks(self) -> tuple[float, ...]:
        """Die Tiefen, die etwas bedeuten: Mitte und Rückseite des Materials.

        Mehr nicht — eine lange Liste machte aus dem freien Zug eine Auswahl,
        und genau das soll das kurze Einrasten nicht sein. Was der Kunde selbst
        eintippt, geht ohnehin nicht durch den Magneten (:meth:`_depth_typed`).
        """
        below = self._material_below()
        if below <= EPS_GEOM:
            return ()
        return (below / 2.0, below)

    def _axis_on_screen(self) -> tuple[float, float] | None:
        """Die Bohrachse als Einheitsrichtung im Bild — von der Mündung ins Material.

        Sie sagt, welche Zeigerbewegung „tiefer" bedeutet. Nach dem Schwenk in
        die Seitenansicht steht sie senkrecht, aber die Kamera darf danach
        weitergedreht werden; gerechnet wird deshalb aus der Projektion und
        nicht aus der Annahme.
        """
        renderer = self.viewport.renderer
        if renderer is None or self._surface is None:
            return None
        axis = np.asarray(self._surface.frame.normal, dtype=np.float64)
        span = float(np.linalg.norm(axis))
        if span < 1e-9:
            return None
        axis = axis / span
        point = np.asarray(self._surface.point, dtype=np.float64)
        # Ins Material hinein ist die Gegenrichtung der Flächennormalen.
        mouth = renderer.world_to_display(
            tuple(self.viewport.view_point_of(tuple(point), self._object_id))
        )
        inside = renderer.world_to_display(
            tuple(self.viewport.view_point_of(tuple(point - axis), self._object_id))
        )
        step = np.array([inside[0] - mouth[0], inside[1] - mouth[1]], dtype=np.float64)
        length_of = float(np.linalg.norm(step))
        if length_of < 1e-6:
            return None
        step = step / length_of
        return float(step[0]), float(step[1])

    def _depth_typed(self, millimetres: float) -> None:
        """Eine eingetippte Tiefe zählt wie eine gezogene — und hält den Zug an.

        **Wer eine Zahl eingibt, hat entschieden**, und der Zeiger hat danach
        nichts mehr zu sagen. Der Zug misst absolut von der Mündung: Ohne diese
        Sperre überschriebe die nächste Bewegung über der Renderfläche den
        getippten Wert vollständig — und der Weg zum Knopf führt genau darüber
        (Robert, 09.09.2026: „wenn ich die tiefe setz, komm ich nicht in das
        bearbeitenfeld von der maßeinheit"). ``_depth_set`` ist dieselbe Sperre,
        die auch der bestätigende Klick setzt; von hier führt derselbe Weg
        weiter — Ansicht frei, Knopf übernimmt.
        """
        if self._updating or not self._deepening:
            return
        self._set_depth(max(0.0, millimetres))
        self._depth_set = True

    def _depth_now(self, name: str | None) -> float:
        """Die eingestellte Tiefe in Millimetern — auch wenn dort ein Ausdruck steht.

        ``OperationDialog.values`` gibt zurück, was im Feld steht: eine Zahl
        **oder** einen Parameterausdruck (`=@wand`). Ein ``float()`` darauf
        wirft, und weil ``redraw`` aus einem Qt-Slot läuft, riss die Ausnahme
        die ganze Tiefenstufe mit — noch bevor die erste Mausbewegung kam. Der
        Ausdruck wird deshalb aufgelöst, mit denselben Projektparametern, die
        auch ``_request_tool`` benutzt.

        Was sich nicht auflösen lässt, gilt als null: Die Tiefenstufe ist eine
        Anzeige, und ein unvollständiger Ausdruck ist ein Fall für den Dialog,
        nicht für einen Absturz (Regel 17).
        """
        if name is None:
            return 0.0
        found = self.dialog.values().get(name, 0.0)
        if expressions.is_expression(found):
            parameters = expressions.resolve(dict(self.session.project.document.parameters))
            try:
                found = expressions.resolve_params({name: found}, parameters).get(name, 0.0)
            except AppError:
                return 0.0
        try:
            return float(found or 0.0)
        except TypeError, ValueError:
            return 0.0

    def _material_below(self) -> float:
        """Wie viel Material unter der Mündung liegt, entlang der Werkzeugachse.

        Das Bezugsmaß der Tiefenstufe: Wer bohrt, will wissen, wie viel Wand
        stehen bleibt und wo die Mitte liegt (Robert, 09.09.2026: „bei der
        tiefe fehlen die maße, außenkannten, innenkannten, mitte von
        irgendwas").

        **Gemessen wird mit einem Strahl, nicht am Hüllquader.** Der fernste
        Punkt des Körpers in Bohrrichtung ist bei einem massiven Klotz die
        richtige Antwort und bei einem hohlen die falsche — und hohl ist im
        Druck der Normalfall. In die zwei Millimeter starke Decke einer Box
        gebohrt stand „Wand: 18,0 mm" im Bild, die Mitte-Marke lag in der Luft,
        und das Einrasten hielt an beiden falschen Werten. Der Strahl nimmt den
        **ersten Austritt**, also die Wand, die der Bohrer wirklich vor sich
        hat; dieselbe Rechnung, mit der die Stifte ihre Materialtiefe suchen
        (``geom.pins``).

        Findet der Strahl nichts — die Fläche zeigt nach außen, dahinter ist
        Luft —, bleibt der Hüllquader als Rückfall: Ein Maß von null verböte
        jede Tiefe, und die Marken verschwänden ganz.
        """
        result = self._result
        entry = result.scene.objects.get(self._object_id) if result is not None else None
        if entry is None or self._surface is None:
            return 0.0
        along = np.asarray(self._surface.frame.normal, dtype=np.float64)
        span = float(np.linalg.norm(along))
        if span < 1e-9:
            return 0.0
        along = along / span
        mesh = as_mesh_data(entry.mesh)
        origin = np.asarray(self._surface.point, dtype=np.float64)
        distances = ray_hit_distances(
            np.asarray(mesh.raw.triangles, dtype=np.float64), origin, -along
        )
        # Der Mündungspunkt liegt auf der Fläche selbst; ein Treffer im Abstand
        # null ist sie und nicht die Gegenwand.
        ahead = distances[distances > EPS_GEOM]
        if len(ahead):
            return float(ahead.min())
        points = np.asarray(mesh.raw.vertices, dtype=np.float64)
        if not points.size:
            return 0.0
        mouth = float(origin @ along)
        return max(0.0, mouth - float((points @ along).min()))

    def _set_depth(self, millimetres: float) -> None:
        """Trägt die Tiefe in den Dialog und zeichnet das Werkzeug neu."""
        name = self._depth_name()
        if name is None or self._updating:
            return
        self._updating = True
        try:
            self.dialog.take_placement({name: millimetres})
        finally:
            self._updating = False
        self._request_tool()
        self.redraw()

    def _scene_changed(self, _result: Any) -> None:
        if self._disposed:
            return
        if (
            isinstance(self.dialog, QuietHost)
            and self.dialog.committing
            and self._deferred_document_change
            and self.session.project.document is self._committing_document
        ):
            return
        # Eine fremde Operation oder Undo entwertet die alte Oberfläche.
        if self.active:
            self.back()
        self.refresh_available()

    def _scene_applied(self) -> None:
        """Erst der tatsächlich gezeichnete Eingang erlaubt ein neues Ziel."""
        if self.active and self._display_ready():
            self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
            if self._change_op is None or self._showing_input:
                self._next_surface()
            self.redraw()

    def _document_changed(self) -> None:
        """Undo und andere Eingriffe entwerten den Bezug vor der nächsten Auswertung."""
        if self._disposed:
            return
        if (
            isinstance(self.dialog, QuietHost)
            and self.dialog.committing
            and self.session.project.document is self._committing_document
        ):
            self._deferred_document_change = True
            return
        self._prepared = None
        self._prepared_mesh = None
        self._patch_faces = frozenset()
        if self.active:
            self.back()
        self.refresh_available()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        # Der Fluss hängt an Zonen, Feldern, dem Viewport und dessen
        # Zeichenfläche — alles sterbliche Widgets. Stirbt eines davon, läuft
        # der Filter sonst in den Abbau hinein (``leash.stop_watching_the_dying``).
        if stop_watching_the_dying(self, watched, event):
            for targets in (self._watched, self._field_targets, self._measure_targets):
                while watched in targets:
                    targets.remove(watched)
            if watched is self._measure_group:
                self._measure_group = None
                self._measure_interpret = None
                self._measure_refresh = None
            if watched is self._measure_scope:
                self._measure_scope = None
            return False
        if self.active:
            if self.viewport.slot_drag_waits() and self._measure_group is None:
                return False
            if watched in self._overlay_zones and event.type() in (
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
            ):
                # Die Karte beendet zuerst ihren Layoutschritt; dann liest die
                # Platzierung die wirkliche Geometrie statt eines Zwischenstands.
                QTimer.singleShot(0, self.redraw)
                return False
            if isinstance(event, QKeyEvent) and event.key() in (
                Qt.Key.Key_Escape,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                if event.type() == QEvent.Type.ShortcutOverride:
                    event.accept()
                    return True
                if event.type() == QEvent.Type.KeyPress:
                    if event.key() == Qt.Key.Key_Escape:
                        # **Das erste Escape nimmt nur den Bezugswahlmodus
                        # zurück.** Wer einen Bezug wählen wollte und es sich
                        # anders überlegt, verliert damit nicht den ganzen
                        # Entwurf: ``back`` verwarf ihn (``reject``), und die
                        # Maße waren weg (Review Ansicht #10). Steht kein
                        # Pickmodus, geht Escape wie bisher zurück.
                        self.step_back()
                    else:
                        if watched in self._field_targets:
                            self._begin_edit()
                        self._accept_values(allow_pending=False)
                    return True
            # **Eine Radraste beginnt den Entwurf nur an einem Feld mit
            # Fokus.** Die Editoren aus ``set_measure_fields`` tragen ihren
            # ``wheel_needs_focus``-Filter seit dem Merkmalfenster — aber
            # der kam vor diesem hier und wird deshalb nach ihm gefragt; ohne
            # die Frage war der Entwurf begonnen, bevor die Raste zum Zoom
            # weiterging.
            if watched in self._field_targets and (
                event.type() == QEvent.Type.MouseButtonPress
                or (
                    event.type() == QEvent.Type.Wheel
                    and isinstance(watched, QWidget)
                    and watched.hasFocus()
                )
                or (
                    isinstance(event, QFocusEvent)
                    and event.type() == QEvent.Type.FocusIn
                    and event.reason()
                    in (
                        Qt.FocusReason.MouseFocusReason,
                        Qt.FocusReason.TabFocusReason,
                        Qt.FocusReason.BacktabFocusReason,
                        Qt.FocusReason.ShortcutFocusReason,
                    )
                )
                or (isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress)
            ):
                self._begin_edit()
                self._show_input_for_edit()
            if event.type() == QEvent.Type.FocusIn and (
                watched is self._depth_measure
                or (isinstance(watched, QWidget) and self._depth_measure.isAncestorOf(watched))
            ):
                # Dieselbe Zusage wie bei den Kantenmaßen darunter, nur für die
                # Tiefe: Wer in das Feld klickt, will tippen und nicht ziehen.
                self._depth_set = True
            if event.type() == QEvent.Type.FocusIn and any(
                watched is field or (isinstance(watched, QWidget) and field.isAncestorOf(watched))
                for field in (*self._measures, *self._centre_measures)
            ):
                self._frozen = True
                self._pending = None
                self._commit_pending = False
                self._serial += 1
            if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut) and any(
                watched is field or (isinstance(watched, QWidget) and field.isAncestorOf(watched))
                for field in (*self._measures, *self._centre_measures, self._depth_measure)
            ):
                # Das Maß zum Feld leuchtet, solange das Feld den Fokus hat —
                # der Fokus ist nach dem Ereignis gesetzt, das Bild folgt.
                QTimer.singleShot(0, self._redraw_for_focus)
            if event.type() == QEvent.Type.Resize and (
                watched is self.viewport
                or watched is getattr(self.viewport.renderer, "widget", None)
            ):
                # Nur die Ansichtsfläche bestimmt das Layout. adjustSize der
                # eigenen Maßfelder löst ebenfalls Resize aus; ein Rückruf
                # mitten im Aufbau würde mehrere Linienlisten vermischen.
                self.redraw()
        return super().eventFilter(watched, event)

    def _redraw_for_focus(self) -> None:
        """Die Tinte nach einem Fokuswechsel nachziehen — ohne toten Fluss."""
        if self.active and not self._disposed:
            self.redraw()

    def _body_on_screen(
        self, screen: Callable[[Vec3], QPointF], bounds: QRect, margin: int
    ) -> QRect | None:
        """Die projizierte Hülle des Trägers, um ``margin`` erweitert — oder
        ``None``, sobald der Körper über das Bild hinausragt.

        **Neben dem Körper, solange man ihn ganz sieht** (Robert, 22.09.2026).
        Ein Körper, der ins Bild passt, lässt ringsum Platz, und dort stehen die
        Felder besser als auf ihm (RM-197). Ragt er hinaus — der Halter mit
        220 mm, nah herangezoomt —, gibt es dieses Ringsum nicht mehr, und
        die Felder gehören an ihre Maßlinien, auf den Körper; die Linien
        selbst bleiben frei.

        Acht Ecken des Hüllquaders, geklemmt wie der Setzpunkt: Eine sehr nahe
        Kamera projiziert jenseits von int32.
        """
        mesh = self._prepared_mesh
        if mesh is None or mesh.triangle_count == 0:
            return None
        low, high = mesh.bounds.minimum, mesh.bounds.maximum
        xs: list[int] = []
        ys: list[int] = []
        for corner in product((low[0], high[0]), (low[1], high[1]), (low[2], high[2])):
            shown = screen(corner)
            if not math.isfinite(shown.x()) or not math.isfinite(shown.y()):
                return None
            xs.append(max(bounds.left() - margin, min(round(shown.x()), bounds.right() + margin)))
            ys.append(max(bounds.top() - margin, min(round(shown.y()), bounds.bottom() + margin)))
        hull = QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))
        if not bounds.contains(hull):
            return None
        body = hull.adjusted(-margin, -margin, margin, margin)
        # Lässt der Freiraum um den Körper nirgends Platz im Bild — der Körper
        # passt gerade so hinein —, gilt die alte Regel weiter: Ein Feld
        # außerhalb des Bildes ist keines. Ohne diesen Ausgang standen beim
        # Heranzoomen alle Felder in der Notreihe oben links (Review 22.09.2026).
        if body.contains(bounds):
            return None
        return body

    def _camera_moved(self) -> None:
        """Die Kamera steht anders: Felder und Tinte neu legen — das Bild zeichnet die Ansicht.

        Wer ``cameraMoved`` sendet, zeichnet danach genau einmal
        (``kamera.md``). Bis zum 21.09.2026 zeichnete der Fluss hier selbst,
        und je Radraste kamen zwei Bilder und je Zugende drei.
        """
        self.redraw(draw=False)

    def redraw(self, *, draw: bool = True) -> None:
        if not self.active or self._disposed:
            return
        # Ohne gemeinsame Fachgruppe hat die Langlochvorschau ihren eigenen
        # Übernehmen-Weg. Die gebundene Gruppe behält dagegen ihren Abschluss.
        if self.viewport.slot_drag_waits() and self._measure_group is None:
            for widget in self._widgets():
                widget.hide()
            self._canvas.hide()
            for item in (self._tool, self._addition):
                if item is not None:
                    item.set_visible(False)
            self.viewport.grip_placement(None)
            if draw:
                self._draw_soon()
            return
        self._show_bar()
        area = self.viewport.rect()
        room = area.adjusted(ROOMY, ROOMY, -ROOMY, -ROOMY)
        overlay = getattr(self.window, "overlay", None)
        for role in ("left", "right", "bottom"):
            zone = getattr(overlay, role, None)
            if (
                not isinstance(overlay, QWidget)
                or not isinstance(zone, QWidget)
                or not isValid(zone)
                or not zone.isVisibleTo(overlay)
            ):
                continue
            obstacle = QRect(self.viewport.mapFromGlobal(zone.mapToGlobal(QPoint())), zone.size())
            if role == "left":
                room.setLeft(max(room.left(), obstacle.right() + NORMAL + 1))
            elif role == "right":
                room.setRight(min(room.right(), obstacle.left() - NORMAL - 1))
            else:
                room.setBottom(min(room.bottom(), obstacle.top() - NORMAL - 1))
        self._bar.setMaximumWidth(max(room.width(), 1))
        self._bar.adjustSize()
        # **Unten mittig, über der Werkzeugzeile** (Robert, 09.09.2026: „das
        # fenster weiter zur tiefe am besten unten mittig über das panel mit
        # schnitt, messen usw setzen"). Oben links lag sie im Weg des Modells
        # und weit weg von dem Ort, an dem beim Platzieren ohnehin jeder
        # hinsieht: der Zeile mit Schnitt, Messen und Bewegen. ``room`` hat die
        # verdeckten Zonen schon abgezogen, die untere Kante ist damit die
        # Oberkante dieser Zeile.
        self._bar.move(
            room.left() + max(0, (room.width() - self._bar.width()) // 2),
            max(room.top(), room.bottom() - self._bar.height()),
        )
        self._bar.raise_()
        measure_room = QRect(room)
        if self._bar.isVisibleTo(self.viewport):
            measure_room.setBottom(self._bar.geometry().top() - NORMAL - 1)
        self._refresh_measure_actions()
        self._size_measure_fields(measure_room)
        surface = self._surface
        renderer = self.viewport.renderer
        valid = (
            surface is not None
            and renderer is not None
            and self.session.result_current
            and self._display_ready()
        )
        tool_valid = valid and self._tool_context is not None and not self._tool_busy
        # **Ein wartender Langlochzug nimmt der gebundenen Maßgruppe nichts.**
        # Die Länge wächst um die Mitte, die Kantenmaße gelten ihr weiter, und
        # der Zug am Bewegungsgriff führt sie danach mit (`move_to`). Bis zum
        # 21.09.2026 blendete der wartende Zug Felder und Linien aus, sobald
        # irgendetwas neu zeichnete — nach dem Zug standen sie noch, und die
        # nächste Kameradrehung nahm sie mit (Robert: „wenn wir das langloch
        # ziehen und dann die ansicht drehen sind die maße weg"). Ohne
        # Maßgruppe — die Platzierung eines neuen Werkzeugs aus dem Dialog —
        # tritt sie weiter zurück; das entscheidet der Beginn von ``redraw``.
        slot_waits = self.viewport.slot_drag_waits()
        local_visible = (
            valid
            and (self._change_op is None or self._showing_input)
            and (not slot_waits or self._measure_group is not None)
        )
        # **Gefragt wird das vorbereitete Werkzeug, nicht der gezeichnete
        # Körper.** Ob gesetzt werden kann, hängt daran, dass die Geometrie
        # steht — nicht daran, wie sie gerade angezeigt wird. Seit der Umriss
        # den Körper an einer Bohrung ersetzt, ist ``_tool`` dort ``None``,
        # und der Knopf blieb grau, obwohl alles bereit war. ``tool_valid``
        # trägt die eigentliche Bedingung (``_tool_context is not None``)
        # bereits.
        self._accept.setEnabled(tool_valid and self._distance_valid)
        self._canvas.lines = []
        self._canvas.leaders = []
        self._canvas.references = []
        self._canvas.extensions = []
        self._canvas.focus = []
        focused = QApplication.focusWidget()
        self._canvas.outline = []
        # **Jede Stufe zeigt ihr eigenes Maß.** Die Kantenabstände gehören der
        # Fläche, auf der gesetzt wird — in der Tiefenstufe ist die entschieden,
        # und dort steht die Tiefe an ihrer Stelle.
        for index, field in enumerate(self._measures):
            field.setVisible(local_visible and not self._deepening and index < len(surface.edges))
            self._reference_boxes[index].setVisible(
                local_visible and not self._deepening and index < len(surface.edges)
            )
        self._centre.hide()
        self._reference_boxes[2].hide()
        for field in self._centre_measures:
            field.setVisible(local_visible and not self._deepening and bool(self._centre_id))
        self._depth_measure.setVisible(local_visible and self._deepening)
        # **Wo ein Umriss die Stelle zeigt, tritt der Körper zurück.** Der
        # halbtransparente Zylinder steht auch außerhalb des Materials, und
        # beim Drehen der Ansicht war schwer zu sehen, wo das Loch hinkommt
        # (Befund Robert, 09.09.2026). Gebaut wird er weiter — er trägt die
        # Geometrie, an der das Setzen hängt —, gezeigt nur, wo er die
        # einzige Auskunft ist: bei einem Werkzeug ohne Mündung in der Fläche,
        # und für die Tiefe, die man allein an ihm sieht.
        # **In der Tiefenstufe kehrt sich das um.** Dort ist der Körper die
        # einzige Auskunft, die es gibt — der Umriss sagt nichts über die
        # Tiefe, und wer sie zieht, muss sehen, wie weit der Zylinder reicht
        # (Robert, 09.09.2026: „bei weiter zur tiefe sehe ich den zylinder für
        # die bohrung nicht").
        has_outline = (
            not self._deepening
            and self._tool_context is not None
            and bool(placement.mouth_outline(self._tool_context))
        )
        for item in (self._tool, self._addition):
            if item is not None:
                item.set_visible(tool_valid and local_visible and not has_outline)
        if not local_visible:
            self._canvas.hide()
            if self._measure_group is not None:
                self._measure_box.move(
                    max(measure_room.left(), measure_room.right() - self._measure_box.width() + 1),
                    measure_room.top(),
                )
                self._measure_box.raise_()
            self.viewport.grip_placement(None)
            if draw:
                self._draw_soon()
            return
        point = np.asarray(surface.point, dtype=np.float64)
        if self._tool is not None:
            matrix = np.eye(4, dtype=np.float64)
            matrix[:3, :3] = np.asarray(
                [surface.frame.x_axis, surface.frame.y_axis, surface.normal], dtype=np.float64
            ).T
            matrix[:3, 3] = self.viewport.view_point_of(surface.point, self._object_id)
            self._tool.set_matrix(matrix)
            if self._addition is not None:
                self._addition.set_matrix(matrix)
        # **Steht die Stelle, steht der Griff am Körper** — für einen
        # Baustein, der gesetzt ist und noch nicht übernommen (Robert,
        # 11.09.2026: „noch das gizmo dazu"). Nicht in der Tiefenstufe, dort
        # zieht die Maus die Tiefe; nicht am vorhandenen Merkmal, dort steht
        # der Griff der Auswahl; und nicht, wo die Werte ohnehin im
        # Merkmalfenster stehen. Frisch angehängt bei jedem Zeichnen, weil der
        # Körper eben neu gesetzt wurde.
        gripped = (
            tool_valid
            and self._frozen
            and not self._deepening
            and self._tool is not None
            and (
                (self._measure_group is not None and self.spec_of().name != "slot_hole")
                or (not self._seated_at_feature and not self.dialog.values_stand_elsewhere)
            )
        )
        self.viewport.grip_placement(
            self._tool if gripped else None, rotation=self._measure_group is None
        )
        ratio = self.viewport._device_ratio()

        def screen(at: Vec3) -> QPointF:
            shown = self.viewport.view_point_of(at, self._object_id)
            x, y, _depth = renderer.world_to_display(shown)
            return QPointF(x / ratio, y / ratio)

        # **Der Umriss der Mündung, dort wo das Werkzeug die Fläche trifft.**
        # Er beantwortet die Frage, die der halbtransparente Körper offenließ:
        # wo genau das Loch hinkommt. Der Körper zeigte dazu den ganzen
        # Zylinder, auch außerhalb des Materials, und beim Drehen der Ansicht
        # war beides schwer auseinanderzuhalten (Befund Robert, 09.09.2026).
        #
        # Gerechnet wird nichts: Der Umriss steht im vorbereiteten Werkzeug,
        # und hier wird er nur in die Ebene der Fläche gelegt und projiziert.
        outline = (
            placement.mouth_outline(self._tool_context) if self._tool_context is not None else ()
        )
        # Wartet ein Langlochzug, steht sein Umriss im Bild (`SlotHandle`);
        # der runde der Mündung sagte daneben etwas Falsches.
        if outline and not slot_waits:
            axis_u = np.asarray(surface.frame.x_axis, dtype=np.float64)
            axis_v = np.asarray(surface.frame.y_axis, dtype=np.float64)
            self._canvas.outline = [
                screen(tuple(point + axis_u * u + axis_v * v)) for u, v in outline
            ]
            self._canvas.outline_colour = QColor(
                DIFF_PALETTES[getattr(self.viewport, "_diff_palette", "blue_orange")].removed.colour
            )

        pending: list[tuple[QWidget, QPointF, QPointF]] = []

        def place(widget: QWidget, start: QPointF, end: QPointF) -> None:
            # **In der Tiefenstufe steht kein Kantenmaß mehr.** Die Schleife
            # unten ruft für jedes gesammelte Feld ``show()`` — eine
            # Sichtbarkeit, die vorher gesetzt wurde, hebt sie damit wieder
            # auf. Wer ein Feld ausblenden will, sammelt es nicht ein (Befund
            # aus Roberts Bild, 09.09.2026: die Abstände der Fläche standen
            # noch da, während unten schon „Maus bewegen: Tiefe" stand).
            if self._deepening and widget not in (self._depth_measure, self._measure_box):
                return
            if widget is not self._measure_box:
                widget.setMaximumWidth(max(room.width(), 1))
            if isinstance(widget, QLabel):
                widget.setWordWrap(True)
            widget.adjustSize()
            # **Die Verbindung geht zur Mitte der Maßlinie** (Robert, 21.09.2026:
            # „schöner wäre noch wenn die linien von den maßen zu den
            # mittellinien jeweils gehen"). Bis dahin endete sie am
            # nächstgelegenen Punkt der Linie — bei einem Feld neben dem Körper
            # ist das ihr Ende, und zwei Felder zeigten auf denselben Eckpunkt.
            # Der Anker steht hier einmal; ``_untangle`` und die Schleife unten
            # lesen ihn, statt ihn je neu herzuleiten.
            anchor = (start + end) / 2
            pending.append((widget, anchor, anchor))

        if self._measure_group is not None:
            place(self._measure_box, screen(surface.point), screen(surface.point))

        if self._deepening and valid:
            # **Die Bezugsmaße der Tiefe** (Robert, 09.09.2026: „bei der tiefe
            # fehlen die maße, außenkannten, innenkannten, mitte von
            # irgendwas"). Von der Mündung zur Spitze steht die Tiefe, von der
            # Spitze zur Rückseite die Wand, die stehen bleibt; die Mitte ist
            # eine eigene Marke, weil an ihr eingerastet wird.
            name = self._depth_name()
            depth = self._depth_now(name)
            below = self._material_below()
            axis = np.asarray(surface.frame.normal, dtype=np.float64)
            span = float(np.linalg.norm(axis))
            if span > EPS_GEOM:
                axis = axis / span
                mouth = screen(surface.point)
                tip = screen(tuple(point - axis * depth))
                self._canvas.lines.append((mouth, tip))
                if _holds_focus(self._depth_measure, focused):
                    self._canvas.focus.append((mouth, tip))
                # **An seiner Maßlinie, wie jedes Kantenmaß.** Über der Leiste
                # allein stand es als Fremdkörper da: Dieselbe Rolle, dieselbe
                # Gestalt (Robert, 09.09.2026: „das maßfeld ist immer noch
                # nicht so wie wenn ich die bohrung auf der oberfläche setze").
                # ``QSignalBlocker`` und nicht zwei Aufrufe: Wirft
                # ``set_value_mm`` dazwischen, bliebe das Feld für immer
                # stumm — es nähme danach keine Eingabe mehr an, ohne dass
                # etwas danach aussieht.
                if not self._keep_field_text(self._depth_measure):
                    with QSignalBlocker(self._depth_measure):
                        self._depth_measure.set_value_mm(depth)
                place(self._depth_measure, mouth, tip)
                if below > depth + EPS_GEOM:
                    self._canvas.lines.append((tip, screen(tuple(point - axis * below))))
                    self._rest.setText(
                        tr("Wand: {value}").replace("{value}", length(below - depth))
                    )
                    self._rest.adjustSize()
                    self._rest.move(round(tip.x()) + ROOMY, round(tip.y()))
                    self._rest.show()
                    self._rest.raise_()
                else:
                    self._rest.hide()
                middle = screen(tuple(point - axis * (below / 2.0)))
                self._canvas.leaders.append((middle, middle))
        else:
            self._rest.hide()

        for index, edge in enumerate(surface.edges[:2]):
            reference = (screen(edge.start), screen(edge.end))
            self._canvas.references.append(reference)
            extension = placement.reference_extension(edge, surface.point)
            if extension is not None:
                self._canvas.extensions.append((screen(extension[0]), screen(extension[1])))
            foot = point - np.asarray(edge.inward, dtype=np.float64) * edge.distance
            start, end = screen(tuple(foot)), screen(surface.point)
            self._canvas.lines.append((start, end))
            field = self._measures[index]
            if _holds_focus(field, focused):
                self._canvas.focus.extend((reference, (start, end)))
            number = next(
                number
                for number, reference in enumerate(self._prepared.edges, 1)
                if reference.id == edge.id
            )
            reference_name = self._reference_name(edge.kind, number)
            field.setPrefix(reference_name + ": ")
            # **Der Name für den Bildschirmleser zieht mit.** Er stand einmalig
            # als „Abstand zu Kante 1/2" im Aufbau der Felder; das Präfix nennt
            # aber den wirklichen Bezug (Außenkante 3, Achse 2 …) und wechselt
            # mit ihm (Review Ansicht #12). Ohne Nachziehen sagte die
            # Vorlesehilfe etwas anderes als das Bild.
            field.setAccessibleName(tr("Abstand zu {reference}").format(reference=reference_name))
            if not self._keep_field_text(field):
                with QSignalBlocker(field):
                    bound = max(self._prepared_mesh.bounds.diagonal, abs(edge.distance), 1.0)
                    field.set_range_mm(-bound, bound)
                    field.set_value_mm(edge.distance)
            field.setToolTip(
                tr("Signierter Abstand der Zielmitte zum Bezug; kein Wandabstand.")
                + " "
                + tr("Rechtsklick: Bezug ändern.")
            )
            place(self._reference_boxes[index], start, end)
        centre = next(
            (entry for entry in surface.centres if entry.feature_id == self._centre_id), None
        )
        if centre is not None:
            corner = np.asarray(centre.point) + np.asarray(surface.frame.x_axis) * centre.offset[0]
            vertices = (centre.point, tuple(corner), surface.point)
            for index, field in enumerate(self._centre_measures):
                start, end = screen(vertices[index]), screen(vertices[index + 1])
                self._canvas.lines.append((start, end))
                if _holds_focus(field, focused):
                    self._canvas.focus.append((start, end))
                if not self._keep_field_text(field):
                    with QSignalBlocker(field):
                        bound = max(self._prepared_mesh.bounds.diagonal, 1.0)
                        field.set_range_mm(-bound, bound)
                        field.set_value_mm(centre.offset[index])
                place(field, start, end)
            source = self._result.scene.objects.get(self._object_id)
            feature = source.features.get(centre.feature_id) if source is not None else None
            name = feature_name(centre.feature_id, feature) if feature is not None else tr("Mitte")
            self._centre.setText(
                tr("{feature} · Abstand: {distance}").format(
                    feature=name, distance=length(centre.distance)
                )
            )
            self._centre.setToolTip(tr("Rechtsklick: Bezug ändern."))
            self._centre.show()
            place(self._reference_boxes[2], screen(centre.point), screen(centre.point))
        # Der Platz für die Maßfelder ist der Raum **über** der Leiste, seit
        # sie unten mittig steht. Vorher lag sie oben und der Raum darunter;
        # wer nur die Leiste verschiebt und diese Rechnung stehen lässt, drückt
        # jedem Feld den Boden weg — die Zahlen rutschten aus dem Bild.
        bounds = measure_room
        # **Der Setzpunkt ist das erste Hindernis, noch vor jedem Feld.** Jedes
        # Maßfeld will in die Mitte seiner eigenen Maßlinie, und die Linien
        # laufen von den Kanten auf genau diesen Punkt zu — je kürzer der
        # Abstand zur Kante, desto näher rückt die Mitte an ihn heran, bis das
        # Feld verdeckt, wohin der Kunde gerade setzt (Befund Robert,
        # 09.09.2026). Als belegtes Rechteck geführt, weicht die Suche ihm nicht
        # nur aus, sondern erzeugt daneben auch die Ausweichplätze — dieselbe
        # Mechanik, mit der die Felder einander schon aus dem Weg gehen.
        # **Und gesperrt wird, was man sieht, nicht ein Punkt.** Ein fester
        # Abstand ließe das Feld neun Bildpunkte neben der Mitte stehen und
        # damit über der Werkzeugvorschau: Eine Bohrung Ø5 mm ist bei zwölf
        # Bildpunkten je Millimeter sechzig breit. Die Sperrfläche kommt
        # deshalb aus der **projizierten** Ausdehnung des Werkzeugs; ohne
        # vorbereitetes Werkzeug bleibt es beim Mindestabstand.
        spot = screen(surface.point)
        # **Und der Mindestabstand ist eine Zeilenhöhe, keine vier Bildpunkte.**
        # Bei einem Merkmal, das schon sitzt, fallen alle Bezugspunkte auf seine
        # Mitte: Die Abstände zur eigenen Stelle sind null, und die drei Felder
        # standen als Stapel auf dem Loch (Robert, 10.09.2026: „dass die maße …
        # ein bisschen entfernt stehen ähnlich wie die angaben mit dem
        # volumen"). Gemessen wird in Zeilenhöhen und nicht in Pixeln, damit der
        # Abstand bei jeder Anzeigeskalierung und Schriftgröße gleich aussieht.
        room_around = max(SPACE, self._centre.sizeHint().height() * 2)
        reach = room_around
        if self._tool_context is not None:
            half = float(np.max(self._tool_context.mesh.bounds.size[:2])) / 2.0
            edge = screen(tuple(point + np.asarray(surface.frame.x_axis) * half))
            reach = max(
                room_around,
                round(math.hypot(edge.x() - spot.x(), edge.y() - spot.y())) + ROOMY,
            )
        # Geklemmt, bevor daraus ein ``QRect`` wird: Eine Projektion aus einer
        # sehr nahen Kamera liefert Werte jenseits von int32, und die Ausnahme
        # führe aus einem Qt-Slot heraus.
        blocked = QRect(
            max(bounds.left() - reach, min(round(spot.x()), bounds.right() + reach)),
            max(bounds.top() - reach, min(round(spot.y()), bounds.bottom() + reach)),
            1,
            1,
        ).adjusted(-reach, -reach, reach, reach)
        occupied: list[QRect] = [blocked]
        # **Der Bewegungsgriff bleibt frei.** Er hängt am selben Merkmal und
        # greift weiter als das Werkzeug; ein Feld darüber nimmt die
        # Zeigerereignisse an, und dann sind Pfeile und Ringe sichtbar und tot
        # (Robert, 10.09.2026). Als eigenes Rechteck und nicht als größeres
        # ``reach``, weil der Griff an der Mitte der Bohrung sitzt und der
        # Setzpunkt an ihrer Mündung.
        handle = self.viewport.gizmo_reach()
        self._canvas.clearing = None
        if handle is not None:
            origin, span = handle
            middle = screen(origin)
            rim = screen(tuple(np.asarray(origin) + np.asarray(surface.frame.x_axis) * span))
            around = max(
                SPACE, round(math.hypot(rim.x() - middle.x(), rim.y() - middle.y())) + ROOMY
            )
            # Dieselbe Spanne nimmt die Maßfläche aus ihren Linien heraus.
            self._canvas.clearing = (middle, float(around))
            occupied.append(
                QRect(
                    max(bounds.left() - around, min(round(middle.x()), bounds.right() + around)),
                    max(bounds.top() - around, min(round(middle.y()), bounds.bottom() + around)),
                    1,
                    1,
                ).adjusted(-around, -around, around, around)
            )
        # **Der Körper bleibt frei, solange man ihn ganz sieht.** Jedes Feld
        # wollte in die Mitte seiner Maßlinie, und die läuft über die Platte:
        # Drei Beschriftungen standen auf dem Teil, zwei davon aufeinander
        # (Robert, 21.09.2026, RM-197: „einen weiteren abstand zum modell und
        # linien … damit es nicht stört und ich auch weiß wo etwas hingeht").
        # Die projizierte Hülle des Trägers ist deshalb ein Hindernis, mit
        # demselben Abstand wie um den Setzpunkt — aber nur, solange der Körper
        # ganz im Bild steht und ringsum Platz lässt (Robert, 22.09.2026, am
        # Schraubendreherhalter: „wo welches maß hinkommt seh ich immer noch
        # nicht" — „solange man den körper vollständig sieht"). Ragt er hinaus
        # oder füllt er das Bild, stehen die Felder an ihrer Maßlinie, auf dem
        # Körper — und möglichst nicht über einer Maßlinie oder fremden
        # Verbindung (``_clear_of_lines``): Das war der Grund für den Abstand.
        body = self._body_on_screen(screen, bounds, room_around)
        if body is not None:
            occupied.append(body)
        # Das Vorschauband oben deckt sonst zwei Felder zu.
        banner = getattr(self.viewport, "banner", None)
        if isinstance(banner, QWidget) and banner.isVisibleTo(self.viewport):
            occupied.append(banner.geometry())
        obstacles = list(occupied)
        ink: list[tuple[QPointF, QPointF]] = list(self._canvas.lines)

        def find_places(
            targets: Sequence[tuple[QWidget, QPointF, QPointF]],
            taken: Sequence[QRect],
            drawn: Sequence[tuple[QPointF, QPointF]],
        ) -> dict[QWidget, QRect] | None:
            """Jedem Feld den nächsten freien Platz — oder nichts, wenn eines
            nirgends steht. Die Verbindung eines gesetzten Feldes ist für die
            nächsten Tinte, damit keines über ihr steht."""
            taken = list(taken)
            drawn = list(drawn)
            found: dict[QWidget, QRect] = {}
            for widget, wanted, anchor in sorted(targets, key=lambda entry: -entry[0].width()):
                width, height = widget.width(), widget.height()
                left, right = bounds.left(), bounds.right() - width + 1
                top, bottom = bounds.top(), bounds.bottom() - height + 1
                middle_x = max(left, min(round(wanted.x() - width / 2), right))
                middle_y = max(top, min(round(wanted.y() - height / 2), bottom))
                xs = {left, right, middle_x}
                ys = {top, bottom, middle_y}
                # Die Plätze unmittelbar neben der Linienmitte — darüber,
                # darunter, links, rechts, und je ein, zwei Feldhöhen weiter —
                # sind die ersten Kandidaten: Dort steht ein Maß, wie man es von
                # einer Zeichnung kennt, und dort findet es einen Platz neben
                # den Linien.
                for step in (1, 2, 3):
                    xs.update(
                        (
                            round(wanted.x()) - step * (width + SPACE),
                            round(wanted.x()) + (step - 1) * (width + SPACE) + SPACE + 1,
                        )
                    )
                    ys.update(
                        (
                            round(wanted.y()) - step * (height + SPACE),
                            round(wanted.y()) + (step - 1) * (height + SPACE) + SPACE + 1,
                        )
                    )
                for rect in taken:
                    xs.update((rect.left() - width - SPACE, rect.right() + SPACE + 1))
                    ys.update((rect.top() - height - SPACE, rect.bottom() + SPACE + 1))
                admissible = [
                    QRect(x, y, width, height)
                    for x in xs
                    for y in ys
                    if left <= x <= right
                    and top <= y <= bottom
                    and not any(
                        QRect(x, y, width, height).intersects(
                            rect.adjusted(-SPACE, -SPACE, SPACE, SPACE)
                        )
                        for rect in taken
                    )
                ]
                if not admissible:
                    return None

                def rank(rect: QRect, wanted: QPointF = wanted) -> tuple[float, int, int]:
                    return ((QPointF(rect.center()) - wanted).manhattanLength(), rect.y(), rect.x())

                # Frei von fremder Tinte, wenn es nicht zu weit führt: Ein
                # linienfreier Platz gewinnt nur, wenn er höchstens
                # ``STICKY_FIELDS`` Feldhöhen weiter vom Maß liegt als der
                # nächste zulässige — sonst stand ein Feld dreihundert Punkte
                # von seiner Linie weg, nur um einen Strich nicht zu decken
                # (Review 22.09.2026). Ein Feld über einem Strich ist besser als
                # eines, das nirgends steht.
                nearest = min(admissible, key=rank)
                chosen = nearest
                # Die eigene Maßlinie zählt nicht: Auf einer Zeichnung sitzt die
                # Zahl auf ihrer Linie; gemieden wird, was ein anderes Maß
                # beschriftet. Die eigene ist die, deren Mitte der Anker ist.
                foreign = [
                    line
                    for line in drawn
                    if ((line[0] + line[1]) / 2 - anchor).manhattanLength() > 1.0
                ]
                clear = [rect for rect in admissible if _clear_of_lines(rect, foreign)]
                if clear:
                    best = min(clear, key=rank)
                    if rank(best)[0] <= rank(nearest)[0] + STICKY_FIELDS * height:
                        chosen = best
                found[widget] = chosen
                taken.append(chosen)
                drawn.append((QPointF(chosen.center()), anchor))
            return found

        def emergency_rows() -> dict[QWidget, QRect]:
            """Fünf Felder passen im unterstützten Desktopbereich in wenige
            Zeilen. Diese feste Anordnung löst einen ungünstigen früheren
            Platz, statt ein weiteres Feld am unteren Rand zu stapeln."""
            rows: dict[QWidget, QRect] = {}
            x, y, row_height = bounds.left(), bounds.top(), 0
            for pending_widget, _wanted, _anchor in pending:
                if x > bounds.left() and x + pending_widget.width() > bounds.right() + 1:
                    x, y, row_height = bounds.left(), y + row_height + SPACE, 0
                slot = QRect(x, y, pending_widget.width(), pending_widget.height())
                # **Auch die Notlage weicht dem Setzpunkt aus — solange danach
                # noch Platz ist.** Sonst gälte die Zusage „man sieht, wohin
                # man setzt" genau dort nicht, wo es eng wird. Die Grenze ist
                # keine Feinheit: Bei starkem Zoom füllt die Vorschau das ganze
                # Bild, und ein Ausweichen darunter schöbe die Felder aus der
                # Ansicht heraus (gemessen an
                # ``test_dimension_fields_do_not_overlap_at_zoomed_view_edges``:
                # y = 20009 bei 600 px Höhe). Dann ist Überdecken das kleinere
                # Übel — ein Feld außerhalb des Bildes ist keines.
                below = blocked.bottom() + SPACE + 1
                if slot.intersects(blocked) and (
                    below + pending_widget.height() - 1 <= bounds.bottom()
                ):
                    x, y, row_height = bounds.left(), below, 0
                    slot = QRect(x, y, pending_widget.width(), pending_widget.height())
                rows[pending_widget] = slot
                x += pending_widget.width() + SPACE
                row_height = max(row_height, pending_widget.height())
            return rows

        fresh = find_places(pending, occupied, ink)
        if fresh is None:
            positions = emergency_rows()
        else:
            _untangle(fresh, pending, bounds, obstacles)
            positions = fresh
            # **Die Felder bleiben stehen, wo sie standen** (Robert, 22.09.2026:
            # „danach springen sie auch alle und tauschen sich"). Jeder Aufbau
            # suchte jedem Feld den nächsten freien Platz neu, und nach jedem
            # getippten Wert — die Bohrung einen Millimeter weiter — lagen die
            # Kandidaten anders, die Felder sprangen, ``_untangle`` tauschte.
            # Der Platz des letzten Aufbaus gilt je Feld weiter, solange er
            # frei und im Bild ist, dem Maß nicht deutlich ferner liegt als der
            # neue und keine Maßlinie deckt, die der neue freiließe; die
            # übrigen Felder finden um die stehenden herum ihren Platz. Nur
            # wenn das mehr Kreuzungen brächte als die frische Anordnung, gilt
            # die frische: Wer Zahlen tippt, will die Felder wiederfinden,
            # nicht suchen.
            kept = _places_that_still_serve(
                self._field_slots, fresh, pending, bounds, obstacles, ink
            )
            if kept:
                rest = [entry for entry in pending if entry[0] not in kept]
                standing = [*obstacles, *kept.values()]
                placed = (
                    find_places(
                        rest, [*occupied, *kept.values()], [*ink, *_leaders_of(kept, pending)]
                    )
                    if rest
                    else {}
                )
                if placed is not None:
                    _untangle(placed, rest, bounds, standing)
                    merged = {**kept, **placed}
                    if _crossings(merged, pending) <= _crossings(fresh, pending):
                        positions = merged
        self._field_slots = dict(positions)
        for widget, _wanted, anchor in pending:
            rect = positions[widget]
            widget.move(rect.topLeft())
            widget.show()
            widget.raise_()
            middle = QPointF(rect.center())
            direction = anchor - middle
            ratios = [1.0]
            if direction.x():
                ratios.append(rect.width() / (2 * abs(direction.x())))
            if direction.y():
                ratios.append(rect.height() / (2 * abs(direction.y())))
            self._canvas.leaders.append((middle + direction * min(ratios), anchor))
        # **Die Felder der Tiefenstufe werden nach der Leiste gehoben**, damit
        # sie erreichbar bleiben: Sie steht unten mittig, und das Tiefenfeld
        # sitzt darüber (Robert, 09.09.2026: „wenn ich die tiefe setz, komm
        # ich nicht in das bearbeitenfeld von der maßeinheit").
        shown = [widget for widget in (self._depth_measure, self._rest) if widget.isVisible()]
        self._canvas.refresh()
        self._bar.raise_()
        for widget in (*self._measures, *self._centre_measures, self._centre, *shown):
            widget.raise_()
        if draw:
            self._draw_soon()

    def _draw_soon(self) -> None:
        """Das Bild zu dieser Neuzeichnung bestellen — eines je Ereignisrunde."""
        if not self._frame.isActive():
            self._frame.start()

    def _draw_now(self) -> None:
        """Das bestellte Bild zeichnen, falls es den Fluss noch gibt."""
        if not self._disposed and isValid(self):
            self.viewport._draw()
