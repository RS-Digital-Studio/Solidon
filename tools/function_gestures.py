"""Überfahren und Ziehen im Bild: I1 und Z1 eines Funktionsfalls (D0-P, RM-737).

Aus ``function_bench`` gelöst, damit der Fall unter der Größengrenze der
Codestruktur bleibt (Regel 6, 2 000 Zeilen). :class:`GesturePhases` trägt die
zwei Phasen, die die Maus über der Ansicht führen, ohne zu klicken
(:meth:`~GesturePhases.phase_hover`) oder mit gedrückter Taste
(:meth:`~GesturePhases.phase_drag`); ``FunctionFlow`` erbt sie.

Falle: **Je Art ein Merkmal, das der Kamera zugewandt ist.** Das erste
Merkmal einer Art kann auf der abgewandten Seite liegen; ``point_for`` findet
dann keine Stelle, und ein leerer Hinweis hieß „ohne Name und Maß“
(Probelauf F-28). Gefahren wird das erste mit einer Stelle; hat keines eine,
ist die Art nicht gemessen — und das steht in ``unmeasured``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any, Final, Protocol

from tools.function_checks import COVERED
from tools.function_machine import SETTLE_MS, BenchFinding, Step, StepMachine, until_step
from tools.function_protocol import drag_frames, unmeasured
from tools.function_setup import walk_target

#: I1: Wie lange nach der Suchfrist der Ansicht (``viewport.HOVER_DELAY_MS``) auf ihren
#: Hinweis gewartet wird — ein Bild und die Suche unter dem Zeiger (Sekunden).
HOVER_READ_S: Final = 1.0

#: Z1: Bewegungen eines Zugs und ihr Takt — 60 je Sekunde wie eine Hand an der
#: Maus (Review L11), nicht so schnell, wie die Schleife sie senden kann.
DRAG_MOVES: Final = 20

DRAG_TICK_S: Final = 1 / 60

#: Das Bild im gehaltenen Zug, vor dem Loslassen (FD-73): Griffmaß und Geist,
#: wie der Kunde sie sieht, solange er die Taste hält.
HELD_PICTURE: Final = "05-zug-gehalten"

#: Die Meldungen der Ansicht während eines Zugs am Griff: Geist, Zahl am Zeiger,
#: verschobener Körper. Kommt keine, hat der Zug den Griff nicht gefasst.
DRAG_SIGNALS: Final[tuple[str, ...]] = (
    "transformDragged",
    "placementDragged",
    "previewDragged",
    "gizmoStatus",
    "featureMoved",
    "featureMoveProposed",
    "faceDragged",
    "scaleDragged",
    "slotDragged",
)


def hover_steps(
    move: Callable[[], None],
    tooltip: Callable[[], str],
    sink: list[str],
    clock: Callable[[], float],
    delay_s: float,
) -> list[Step]:
    """I1 an einer Art: hinfahren, auf den Hinweis der Ansicht warten, ihn lesen (Review S3).

    ``move`` fährt die Maus über das Merkmal, ``tooltip`` liest den Hinweis der
    Ansicht. Gelesen wird, wenn er steht — frühestens dann, und spätestens
    ``delay_s`` (Suchfrist der Ansicht) plus :data:`HOVER_READ_S` nach dem
    Hinfahren; ``sink`` bekommt den Text.
    """

    def read(machine: StepMachine) -> None:
        sink[:] = [tooltip()]

    return [
        Step("hin", lambda machine: move()),
        until_step("hinweis", lambda: bool(tooltip()), delay_s + HOVER_READ_S, clock),
        Step("lesen", read),
    ]


class _Flow(Protocol):
    """Was die Phasen am Funktionsfall brauchen (``FunctionFlow``)."""

    application: Any
    window: Any
    session: Any
    ports: Any
    data: dict[str, Any]
    row: dict[str, Any]
    spec: dict[str, Any]
    frames: Any
    frames_wrapped: bool
    reference_factor: float
    variant: Any

    def run_steps(self, label: str, steps: Sequence[Step], timeout_s: float = ...) -> bool: ...
    def until_step(
        self, name: str, condition: Callable[[], bool], at_most_s: float = ...
    ) -> Step: ...
    def path_steps(self) -> list[Step]: ...
    def away_point(self) -> Any: ...
    def picture(self, label: str) -> None: ...


class GesturePhases:
    """Überfahren (I1) und Ziehen (Z1) — Phasen von ``FunctionFlow``."""

    def phase_hover(self: _Flow) -> None:
        """I1: Name und Maß beim Überfahren je erkannter Art (``view:``), ohne Klick (Review S3).

        Die Ansicht sucht das Merkmal unter dem Zeiger erst nach
        ``viewport.HOVER_DELAY_MS`` und nur mit Renderer; Name und Maß stehen dann
        in ihrem Tooltip (``Viewport._refresh_feature_hint``) — keine Beschriftung
        als ``QLabel``. Gelesen wird also der Tooltip der Ansicht, und erst, wenn
        er steht oder :data:`HOVER_READ_S` nach der Frist der Ansicht vergangen
        ist. Ohne Renderer gibt es nichts zu überfahren: ungemessen statt leer.
        Je Art das erste Merkmal mit einer zugewandten Stelle; eine Art ohne
        Stelle oder ein Überfahren, das scheiterte, ist nicht gemessen (F-28).
        """
        from app.ui.viewport import HOVER_DELAY_MS

        result = self.session.last_result
        if result is None or not any(entry.features for entry in result.scene.objects.values()):
            unmeasured(self.data, "hover_labels", "die Startszene trägt kein Merkmal")
            return
        kinds: dict[str, list[str]] = {}
        for key, entry in result.scene.objects.items():
            for name, feature in entry.features.items():
                kinds.setdefault(feature.kind, []).append(f"view:{key}.{name}")
        # Was die Erkennung an der Szene liefert, neben dem, was überfahren
        # wurde: Erst so ist „jede Art“ prüfbar (FD-152).
        self.data["recognized_kinds"] = sorted(kinds)
        view = self.window.viewport
        if getattr(view, "renderer", None) is None:
            unmeasured(self.data, "hover_labels", "kein Renderer — die Ansicht sucht nichts")
            return
        labels: list[dict[str, Any]] = []
        missed: list[str] = []
        for kind, targets in kinds.items():
            target = next((name for name in targets if _reachable(self.ports, name)), None)
            if target is None:
                missed.append(f"{kind}: kein Merkmal mit zugewandter Stelle")
                continue
            texts: list[str] = []

            def hover(target: str = target) -> None:
                click = self.ports.next_click(target)
                self.ports.move(self.ports.centre(click.rect))

            done = self.run_steps(
                f"überfahren {target}",
                [
                    Step("weg vom bild", lambda machine: self.ports.move(self.away_point())),
                    self.until_step("ohne hinweis", lambda: not view.toolTip()),
                    *hover_steps(
                        hover, view.toolTip, texts, time.perf_counter, HOVER_DELAY_MS / 1000
                    ),
                ],
            )
            if done:
                labels.append({"kind": kind, "label": " ".join(texts)})
            else:
                missed.append(f"{kind}: das Überfahren von {target} scheiterte")
        if missed:
            unmeasured(self.data, "hover_labels", "; ".join(missed))
        self.data["hover_labels"] = labels

    def away_point(self: _Flow) -> Any:
        """Eine Stelle außerhalb der Ansicht, damit ein neuer Hinweis neu entsteht."""
        from PySide6.QtCore import QPoint

        return self.window.mapToGlobal(QPoint(2, 2))

    def phase_drag(self: _Flow) -> None:
        """Z1: ein Zug am Griff der Zeile, je Bewegung die rohe Zeit bis zum nächsten Bild.

        Der Griff ist das Ziel der Zeile — oder ``spec.drag``, wenn erst die
        Handlung der Zeile ihn zeigt (*Zum Langloch ziehen*: ``handle:slot.end``);
        dann geht der Weg bis zur Handlung, und der Zug folgt. Vor dem Loslassen
        nimmt der Fall das Fenster auf (:data:`HELD_PICTURE`, FD-73). Außer im
        Satz ``basis`` zieht nur eine Zeile mit ``spec.drag`` (``dunkel``: das
        Griffmaß im dunklen Thema).
        """
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        named = str(self.spec.get("drag") or "")
        target = named or walk_target(self.row)
        if not named and self.variant.set != "basis":
            return
        if not target.startswith("handle:") and "Z1" not in (self.spec.get("criteria") or ()):
            unmeasured(self.data, "frames.raw_drag_ms", "kein Griff an dieser Zeile")
            return
        if not self.frames_wrapped:
            unmeasured(self.data, "frames.raw_drag_ms", "kein Renderer, kein Bildzähler")
            return
        moves: list[float] = []
        gripped = {"signals": 0}

        def noticed(*_values: object) -> None:
            gripped["signals"] += 1

        # Gefasst ist der Griff, wenn die Ansicht während des Zugs einen ihrer
        # Zugwerte meldet — Geist, Zahl am Zeiger, verschobener Körper (Review L11).
        listened = [
            getattr(self.window.viewport, name)
            for name in DRAG_SIGNALS
            if hasattr(self.window.viewport, name)
        ]
        for signal in listened:
            signal.connect(noticed)

        def pull(machine: StepMachine) -> None:
            click = self.ports.next_click(target)
            point = self.ports.centre(click.rect)
            hit = self.ports.widget_under(point)
            if hit is None or not self.ports.covers(click, hit):
                raise BenchFinding(COVERED, target, "der Griff liegt unter etwas anderem")
            local = hit.mapFromGlobal(point)
            QTest.mousePress(hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)
            for number in range(1, DRAG_MOVES + 1):
                moves.append(time.perf_counter())
                QTest.mouseMove(hit, local + QPoint(4 * number, 0))
                # Im Takt einer Hand an der Maus, nicht so schnell die Schleife kann.
                until = time.perf_counter() + DRAG_TICK_S
                while time.perf_counter() < until:
                    self.application.processEvents()
            # Gehalten, noch nicht losgelassen: Griffmaß und Geist im Bild (FD-73).
            self.picture(HELD_PICTURE)
            QTest.mouseRelease(
                hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local
            )

        try:
            path = self.path_steps() if named else self.path_steps()[:-1]
            self.run_steps("zug", [*path, Step("ziehen", pull, settle_ms=SETTLE_MS)])
        finally:
            for signal in listened:
                signal.disconnect(noticed)
        if not gripped["signals"]:
            unmeasured(self.data, "frames.raw_drag_ms", "der Zug fasste keinen Griff")
            return
        self.data["frames"] = drag_frames(self.frames.latencies(moves), self.reference_factor)


def _reachable(ports: Any, name: str) -> bool:
    """Ob ``next_click`` eine Stelle für das Merkmal nennt — ohne zu klicken."""
    try:
        ports.next_click(name)
    except LookupError:
        return False
    return True
