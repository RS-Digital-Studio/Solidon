"""Der Funktionsfall am Fenster: der Kunde bedient eine Funktion, gemessen wird (D0, RM-737).

Kein eigener Einstieg. ``tools/file_acceptance.py`` legt die Fälle an
(``inventory --functions``), startet je Fall einen Prozess mit eigenem Profil
(``run``) und reicht ihn hierher weiter (``child`` → :class:`FunctionFlow`). Ein
drittes Fensterwerkzeug neben ``file_acceptance`` und ``make_guides`` gibt es
nicht (Konzept Funktionsdurchgang §12); ``tests/test_function_guard.py`` hält,
dass kein Modul des Prüfstands ``__main__`` oder ``argparse`` trägt.

:class:`FunctionFlow` fährt die Phasen einer Zeile — Hauptweg, Escape,
Überfahren, Zug, Abbruch, Halt, Projektwechsel, Lizenz, Oberflächensätze — mit
den Bausteinen der Nachbarmodule: Schrittautomat (``function_machine``), Weg
mit Probe (``function_walk``), Vorbereitung (``function_setup``), Protokoll
(``function_protocol``), Aufnahmen (``function_capture``); die Auswahlmatrix
erbt es aus ``function_matrix``. Startfall und Sprachfall stehen in
``function_start`` und ``function_language``.

**Abgelesen wird, was der Kunde sieht** — Vorschauband, Knopfzustand mit Grund,
Statuszeile —, dazu der Szenenabdruck, der sagt, ob Rückgängig wirklich
zurückkehrt. Gelesen wird erst nach der Wirkung (``function_machine``).
"""

from __future__ import annotations

import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from app.ui.motion import ACCENT_MS, MEDIUM_MS, SHORT_MS
from tools import function_prediction as prediction
from tools import function_surface as surfaces
from tools import function_tooltips as tooltips
from tools.function_capture import run_reference_factor
from tools.function_checks import (
    FAULT_PHASE,
    NO_DRAFT,
    NO_RESPONSE,
    WITHOUT_DIALOG,
)
from tools.function_fonts import FontPhase
from tools.function_gestures import GesturePhases
from tools.function_machine import (
    MOST_UNSTICKS,
    PHASE_TIMEOUT_S,
    SETTLE_MS,
    STEP_TIMEOUT_S,
    TICK_MS,
    BenchFinding,
    Step,
    StepMachine,
    drive,
    nested_since_now,
    qt_schedule,
    until_step,
)
from tools.function_matrix import MatrixPhase, is_window
from tools.function_protocol import (
    abort_entry,
    bodies_digest,
    cli_arguments,
    cli_command,
    compare_prints,
    result_metrics,
    scene_print,
    unmeasured,
)
from tools.function_revision import RevisionPhase
from tools.function_scenes import load_scenes
from tools.function_setup import (
    EMPTY_SCENE,
    PHASES,
    SLOW_SCENES,
    START_SCREEN,
    Variant,
    below_smallest,
    case_scene,
    default_apply_target,
    place_window,
    preparation_route,
    route_of,
    route_texts,
    scene_setup,
    selected_feature,
    walk_target,
)
from tools.function_spot import body_spot
from tools.function_switch import LATE_WINDOW_S, SwitchPhase
from tools.function_walk import (
    APPLY_PHASE,
    PATH_PHASE,
    STABLE_S,
    QtPorts,
    Walk,
    click_button,
    focus_check,
    place_of,
    typed_number,
    with_modifier,
)

#: Wie lange eine Fläche stillstehen muss, bevor sie aufgenommen wird (Sekunden):
#: die längste Bewegung der Oberfläche (``app.ui.motion``) und ein Takt mehr — eine
#: Aufnahme mitten im Übergang mäße Breiten und Rollleisten vom halben Weg.
STILL_S: Final = max(SHORT_MS, MEDIUM_MS, ACCENT_MS) / 1000 + STABLE_S

#: Ruhe nach dem Tippen einer Suchprobe, bevor die Treffer gelesen werden: Die
#: Suche filtert bei jedem Zeichen, und die Liste baut sich danach in einer
#: Ereignisrunde; eine Sekunde trägt beides auch unter Fremdlast.
SEARCH_SETTLE_MS: Final = 1000

#: Wie lange nach einem Klick auf eine Handlung auf ihre Wirkung gewartet wird.
EFFECT_WINDOW_S: Final = 2.0

#: Was eine Aufnahme der Fläche ins Protokoll schreibt (:meth:`FunctionFlow.capture_surface`):
#: die Felder aus ``function_capture.sheet_snapshot`` und Texte, Felder, leere Zustände.
SURFACE_FIELDS: Final = (
    "layout",
    "fonts",
    "contrast",
    "icons",
    "animations",
    "scrollbars",
    "texts",
    "fields",
    "empty_states",
)

#: Wie lange die Vorbereitung einer Szene auf ihre zugesagten Befunde im
#: Prüfbericht wartet: Die Berichtsanalyse liefert nach der Ruhe nach
#: (``tests.md``, ``wait_for_print_findings``), unter Fremdlast in Sekunden.
PREPARATION_S: Final = 60.0


def surface_signature(root: Any) -> tuple[Any, ...]:
    """Wo eine Fläche und ihre sichtbaren Kinder gerade stehen — für ``still_step``."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget

    if root is None:
        return ()

    def place(widget: Any) -> tuple[int, int, int, int]:
        corner = widget.mapToGlobal(QPoint(0, 0))
        return (corner.x(), corner.y(), widget.width(), widget.height())

    shown = tuple(place(widget) for widget in root.findChildren(QWidget) if widget.isVisible())
    # Qt kann für denselben C++-Dialog neue Pythonhüllen liefern. Die lebende
    # Hülle halten: Identität bleibt stabil, ein echter Flächenwechsel sichtbar.
    return (root, place(root), shown)


class FunctionFlow(GesturePhases, SwitchPhase, RevisionPhase, MatrixPhase, FontPhase):
    """Ein Funktionsfall am echten Fenster: Phasen nach der Variante, jede mit Abdruck.

    Jede Phase beginnt an der Startszene (:meth:`reset`) und endet ohne offenes
    Fenster; scheitert eine, steht ihr Grund in ``errors`` oder ``findings``,
    und die nächste läuft trotzdem. Gemessen wird ins Protokoll ``data``,
    geschrieben nach jeder Phase (``persist``) — ein Absturz lässt stehen, was
    schon gemessen war. ``bench`` hält, was nur den Lauf betrifft (Phase,
    Ausnahme), getrennt vom Protokoll.
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        folder: Path,
        data: dict[str, Any],
        persist: Callable[[], None],
        row: Mapping[str, Any],
        variant: Variant,
        scenes: Path,
        bench: dict[str, Any] | None = None,
        out: Path | None = None,
    ) -> None:
        from tools.function_capture import FrameCounter, Heartbeat, ModalWatch

        self.application = application
        self.window = window
        self.session = window.session
        self.folder = folder
        self.out = out or folder.parent.parent
        self.data = data
        self.persist = persist
        self.bench = bench if bench is not None else {}
        self.row = dict(row)
        self.spec: dict[str, Any] = dict(row.get("spec") or {})
        self.variant = variant
        self.scenes = scenes
        self.began = time.perf_counter()
        self.ports = QtPorts(window, self.began)
        self.walker = Walk(self.ports, data["steps"], self.began)
        self.heartbeat = Heartbeat()
        self.frames = FrameCounter()
        self.frames_wrapped = False
        #: Warum dieser Fall kein Fall ist (``below_smallest``), sonst leer.
        self.not_a_case = ""
        self.watch = ModalWatch(self.began)
        self._timers: list[Any] = []
        self.scene_key = str(self.spec.get("start_scene") or row.get("start_scene") or EMPTY_SCENE)
        self.setup = scene_setup(self.scene_key)
        self.apply_target = default_apply_target(self.row)
        self.selected = selected_feature(self.row)
        #: Warum die Fläche zuletzt nicht stillstand, sonst ``None`` (:meth:`still_step`).
        self.restless: str | None = None
        #: Ein Referenzfaktor je Lauf (Bauplan §31, Entscheidung Koordinator 12.10.):
        #: aus dem Lauf (``reference.json``), sonst hier gemessen.
        self.reference_factor = float(
            self.bench.get("reference_factor") or run_reference_factor(self.out)
        )

    # --- Grundgerüst -----------------------------------------------------------------

    def pump(self) -> None:
        self.application.processEvents()
        time.sleep(0.005)

    def run_steps(self, label: str, steps: Sequence[Step], timeout_s: float | None = None) -> bool:
        """Fährt Schritte; ein Fund oder Fehler steht danach im Protokoll.

        ``label`` ist die Phase jedes Eintrags in ``steps``, den diese Schritte
        schreiben (``Walk.phase``). Tiefer als hier geschachtelte Ereignisschleifen
        gehören einem Fenster, das während ``pump`` aufging; der Automat schließt
        es wie eines aus seinen Schritten (``StepMachine.nested``). Ohne
        ``timeout_s`` gilt :data:`PHASE_TIMEOUT_S`, mit Vorhersagetor dazu seine
        Frist (``function_prediction.extra_s``).
        """
        if timeout_s is None:
            timeout_s = PHASE_TIMEOUT_S + prediction.extra_s(self.variant)
        self.walker.phase = label
        machine = StepMachine(
            qt_schedule,
            time.perf_counter,
            unstick=self.escape_modal,
            on_stuck=lambda: self.stuck_modal(label),
            nested=nested_since_now(),
        )
        drive(machine, steps, self.pump, time.perf_counter, timeout_s)
        ok = True
        if machine.finding is not None:
            self.data["findings"].append(
                {
                    "phase": label,
                    "kind": machine.finding.kind,
                    "target": machine.finding.target,
                    "detail": machine.finding.detail,
                }
            )
            ok = False
        if machine.error is not None:
            self.data["errors"].append(f"{label}: {machine.error}")
            ok = False
        if machine.unsticks:
            self.data["closed_by_escape"].append({"phase": label, "times": machine.unsticks})
        self.persist()
        return ok

    def escape_modal(self) -> None:
        """Escape an das modale Fenster oder das offene Menü — wie der Kunde, der abbricht."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        widget = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        if widget is not None:
            QTest.keyClick(widget, Qt.Key.Key_Escape)

    def stuck_modal(self, label: str) -> None:
        """Ein Fenster, das Escape nicht schließt: welches es ist, und ein Klick auf seinen Rückweg.

        Notiert Klasse und Titel in ``errors`` (Review L12) und klickt, wenn es
        einen gibt, den Knopf mit der Rolle „ablehnen“ oder *Schließen* — mit
        Probe (:func:`click_button`). Hilft auch das nicht, endet der Fall an der
        Frist des Elternprozesses, und das Protokoll sagt, woran.
        """
        from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

        from tools.function_capture import name_of

        widget = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        if widget is None:
            return
        self.data["errors"].append(
            f"{label}: {type(widget).__name__} „{widget.windowTitle()}“ ließ sich"
            f" {MOST_UNSTICKS}-mal nicht mit Escape schließen"
        )
        self.persist()
        rejecting: Any = None
        if isinstance(widget, QMessageBox):
            rejecting = widget.escapeButton() or next(
                (
                    button
                    for button in widget.buttons()
                    if widget.buttonRole(button) == QMessageBox.ButtonRole.RejectRole
                ),
                None,
            )
        for box in widget.findChildren(QDialogButtonBox):
            rejecting = rejecting or next(
                (
                    button
                    for button in box.buttons()
                    if box.buttonRole(button) == QDialogButtonBox.ButtonRole.RejectRole
                ),
                None,
            )
        if rejecting is not None:
            click_button(self.ports, self.walker, rejecting, name_of(rejecting))

    def idle(self) -> bool:
        return self.session.last_result is not None and not self.session.busy

    def wait_step(
        self, name: str, ready: Callable[[], bool], timeout_s: float = STEP_TIMEOUT_S
    ) -> Step:
        return Step(name, lambda machine: None, ready=ready, timeout_s=timeout_s)

    def until_step(
        self, name: str, condition: Callable[[], bool], at_most_s: float = EFFECT_WINDOW_S
    ) -> Step:
        """:func:`until_step` an der Uhr des Fensters."""
        return until_step(name, condition, at_most_s, time.perf_counter)

    def still_step(self, name: str, root: Callable[[], Any], at_most_s: float = 10.0) -> Step:
        """Warten, bis die Fläche :data:`STILL_S` lang stillsteht — Übergänge sind vorbei (M1).

        Still heißt: dieselbe Fläche, und sie und ihre sichtbaren Kinder haben
        dieselben Rechtecke (:func:`surface_signature`). Nach ``at_most_s`` geht es
        auch ohne Stillstand weiter; der Grund steht dann in ``unmeasured``, und
        die nächste Aufnahme der Fläche bleibt ungemessen (:attr:`restless`,
        :meth:`capture_surface`; Durchsicht welle4 C-L10).
        """
        seen: dict[str, Any] = {"key": None, "since": 0.0, "began": None}

        def ready() -> bool:
            now = time.perf_counter()
            if seen["began"] is None:
                seen["began"] = now
                self.restless = None
            key = tuple(
                surface_signature(part)
                for part in surfaces.surface_parts(self.window, walk_target(self.row), root())
            )
            if key != seen["key"]:
                seen["key"], seen["since"] = key, now
            if now - seen["since"] >= STILL_S:
                return True
            if now - seen["began"] >= at_most_s:
                self.restless = f"nach {at_most_s:.0f} s nicht still"
                unmeasured(self.data, f"still:{name}", self.restless)
                return True
            return False

        return Step(name, lambda machine: None, ready=ready, timeout_s=at_most_s + STEP_TIMEOUT_S)

    def do_step(self, name: str, action: Callable[[], object], settle_ms: int = TICK_MS) -> Step:
        return Step(name, lambda machine: action(), settle_ms=settle_ms)

    def key_step(self, sequence: Any, name: str) -> Step:
        def act(machine: StepMachine) -> None:
            text = sequence.toString() if hasattr(sequence, "toString") else str(sequence)
            self.walker.record({"target": name, "key": text, "button": None})
            self.ports.keys(sequence)

        return Step(f"taste {name}", act, settle_ms=SETTLE_MS)

    def undo_keys(self) -> Any:
        from PySide6.QtGui import QKeySequence

        return QKeySequence(QKeySequence.StandardKey.Undo)

    def redo_keys(self) -> Any:
        """Die Wiederholen-Taste aus ``shortcut_schemes.redo_keys`` — die, die im Menü steht."""
        from PySide6.QtGui import QKeySequence

        from app.ui.shortcut_schemes import redo_keys

        return redo_keys(sys.platform, QKeySequence(QKeySequence.StandardKey.Redo))[0]

    def scene_now(self) -> dict[str, Any]:
        """Der Abdruck jetzt (:func:`scene_print`)."""
        result = self.session.last_result
        tree = self.window.object_tree
        selection = [str(name) for name in tree.selected_objects()]
        selection += [f"{body}.{feature}" for body, feature in tree.selected_features()]
        return scene_print(
            self.session.project.document,
            result.scene if result is not None else None,
            selection=selection,
            # Ohne Renderer (offscreen) hat die Ansicht keine Kamera.
            camera=(
                self.window.viewport.camera_pose()
                if getattr(self.window.viewport, "renderer", None) is not None
                else None
            ),
        )

    def snapshot(self, label: str) -> dict[str, Any]:
        """Der Abdruck jetzt, unter ``states[label]`` (``function_checks.STATE_KEYS``)."""
        printed = self.scene_now()
        self.data["states"][label] = printed
        self.persist()
        return printed

    def picture(self, label: str) -> None:
        """Bild des Fensters und jedes offenen Dialogs, auch nichtmodal, relativ zu ``--out``."""
        shown = surfaces.windows_to_picture(self.window)
        for number, widget in enumerate([self.window, *shown]):
            suffix = "" if not number else "-dialog" if number == 1 else f"-dialog-{number}"
            picture = widget.screen().grabWindow(int(widget.winId()))
            path = self.folder / f"{label}{suffix}.png"
            if picture.save(str(path)):
                self.data["images"].append(path.relative_to(self.out).as_posix())

    def widget(self, name: str) -> Any | None:
        """Das Widget hinter einem Wortschatznamen, oder ``None`` — nur zum Ablesen."""
        from app.ui import guide_targets

        try:
            return guide_targets.widget_for(self.window, name)
        except LookupError:
            return None

    def surface(self) -> Any:
        """Die Fläche der Zeile nach der Art ihres Ziels (``function_surface.surface_for``)."""
        return surfaces.surface_for(self.window, walk_target(self.row))

    def window_size(self) -> list[int]:
        return [self.window.width(), self.window.height()]

    # --- Vorbereitung ------------------------------------------------------------------

    def prepare(self) -> None:
        """Wachen anlegen, Fenster auf den Schirm, Bildzähler um den Renderer."""
        from tools.function_capture import start_heartbeat

        self.session.failed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.session.importFailed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self._timers.append(start_heartbeat(self.window, self.heartbeat))
        self._timers.append(self.watch.start(self.window))
        placed = place_window(self.application, self.window, self.variant)
        self.not_a_case = below_smallest(placed, self.variant)
        for _ in range(20):
            self.pump()
        self.data["variant"] = self.variant.protocol(placed, self.window_size())
        self.frames_wrapped = self.frames.wrap(getattr(self.window.viewport, "renderer", None))
        # Der Faktor gilt für Zeiten (Prüfpunkt 6) und Bilder (Z1); die Ziehzeiten
        # trägt erst der Zug nach (:meth:`phase_drag`).
        self.data["frames"] = {"reference_factor": self.reference_factor}
        self.persist()

    def finish(self) -> None:
        """Was die Wachen gesehen haben, ins Protokoll; die gehaltenen Fenster frei (RC-11)."""
        from app.ui import guide_targets

        guide_targets.release_held()
        self.watch.poll()
        self.data["modals"] = self.watch.modal_entries()
        self.data["raw_windows"] = self.watch.raw_entries()
        self.data["windows"] = list(self.watch.windows)
        for timer in self._timers:
            timer.stop()
        self.persist()

    # --- Startszene ---------------------------------------------------------------------

    def scene_path(self, key: str) -> Path | None:
        """Die Kopie einer Szene im Fallordner (Review M6, :func:`case_scene`)."""
        return case_scene(self.folder, self.scenes, key)

    def new_project_line(self) -> str:
        """Der Wortschatzname von *Datei → Neu* in der Menüleiste, oder leer."""
        from app.ui import guide_targets

        return next(
            (
                str(name)
                for name, _menus, action in guide_targets.menubar_entries(self.window)
                if action is self.window.new_action
            ),
            "",
        )

    def reset(self) -> bool:
        """Zurück an die Startszene; die Vorbereitung ist nicht die geprüfte Handlung.

        Die Szene ``startbildschirm`` heißt: kein Projekt, der Fall beginnt dort;
        hat eine Phase ein Projekt geöffnet, führt *Datei → Neu* zurück (wie
        :meth:`phase_switch`). Die leere Szene beginnt beim ersten Mal mit einem
        Klick auf *Neues Projekt*. Sonst öffnet ``open_path`` die Kopie der
        Szenendatei im Fallordner (Konzept §5: „Nur die Startszene entsteht über
        ``open_path``“; :func:`case_scene`). Was die Phase davor geändert hat,
        wird verworfen, ohne die Speicherfrage zu stellen — sie gehört nicht zu
        dieser Zeile.
        """
        on_start = self.window.stack.currentWidget() is self.window.start_screen
        if self.scene_key == START_SCREEN:
            if self.data.get("scene") is None:
                self.data["scene"] = {
                    "key": START_SCREEN,
                    "triangles": 0,
                    "build_s": None,
                    "eval_s": 0.0,
                }
            if on_start:
                return True
            line = self.new_project_line()
            if not line:
                self.data["errors"].append("Datei → Neu trägt keinen Namen im Wortschatz")
                return False
            self.session.forget_changes()
            return self.run_steps(
                "startbildschirm",
                [
                    self.walker.step(f"menu:{line}"),
                    self.wait_step(
                        "startbildschirm steht",
                        lambda: self.window.stack.currentWidget() is self.window.start_screen,
                    ),
                ],
            )
        previous = self.session.last_result
        path = self.scene_path(self.scene_key)
        began = time.perf_counter()
        if self.scene_key == EMPTY_SCENE and on_start:
            steps = [self.walker.step("start.new")]
        elif path is not None:
            self.session.forget_changes()
            steps = [self.do_step("szene öffnen", lambda: self.window.open_path(path))]
        else:
            self.data["errors"].append(f"Startszene {self.scene_key} fehlt unter {self.scenes}")
            return False
        steps.append(
            self.wait_step(
                "szene steht",
                lambda: self.idle() and self.session.last_result is not previous,
            )
        )
        ok = self.run_steps(f"startszene {self.scene_key}", steps)
        if ok:
            ok = self.run_steps(f"vorbereitung {self.scene_key}", self.preparation_steps())
        self.session.forget_changes()
        if ok and self.data.get("scene") is None:
            result = self.session.last_result
            triangles = sum(entry.mesh.triangle_count for entry in result.scene.objects.values())
            self.data["scene"] = {
                "key": self.scene_key,
                "triangles": triangles,
                "build_s": None,
                "eval_s": round(time.perf_counter() - began, 3),
                # Körper und Projekt benennt die Szene, nicht die Anwendung (F-10).
                "names": surfaces.scene_names(self.session),
            }
        return ok

    def fault_scene(self, key: str) -> bool:
        """Die eigene Startszene des Fehlfalls, wenn er eine nennt (``fault_case.start_scene``)."""
        if not key or key == self.scene_key:
            return True
        main = (self.scene_key, self.setup)
        self.scene_key, self.setup = key, scene_setup(key)
        try:
            ok = self.reset()
        finally:
            self.scene_key, self.setup = main
        if not ok:
            self.data["errors"].append(f"{FAULT_PHASE}: Startszene {key} nicht herstellbar")
        return ok

    def preparation_steps(self) -> list[Step]:
        """Was nach dem Öffnen den Zustand der Szene herstellt (``preparation_route``).

        Klicks, Tippen und Tasten wie jeder Weg; danach wartet der Prüfstand, bis
        der Auslöser fertig ist. Die Rückfrage vor dem Export bricht er ab — der
        Bericht trägt die Befunde schon, und geschrieben werden soll nichts.
        """
        from PySide6.QtGui import QKeySequence
        from PySide6.QtWidgets import QApplication

        steps: list[Step] = []
        if self.setup.cause.get("kind") == "export":
            # Eine Kennung aus der vorigen Szene kann hier einen anderen Körper
            # meinen. Die Auslöserszene verlangt den Export der ganzen Szene.
            steps += [
                self.key_step(QKeySequence("Escape"), "auswahl leeren"),
                self.do_step(
                    "vollständige exportauswahl",
                    lambda: surfaces.require_full_export_scope(self.window),
                ),
            ]
        for entry in preparation_route(self.setup, self.folder / "ausloeser"):
            if "type" in entry:
                steps.append(self.typing_step(entry["type"]))
            elif "key" in entry:
                steps.append(self.key_step(QKeySequence(entry["key"]), entry["key"]))
            else:
                steps.append(self.walker.step(entry["target"], entry.get("button", "left")))
        kind = self.setup.cause.get("kind")
        if kind == "export":
            steps += [
                self.wait_step(
                    "rückfrage vor dem export",
                    lambda: QApplication.activeModalWidget() is not None,
                ),
                self.do_step("rückfrage abbrechen", self.escape_modal, settle_ms=SETTLE_MS),
            ]
        if steps:
            steps.append(
                self.wait_step(
                    "vorbereitung steht",
                    lambda: (
                        QApplication.activeModalWidget() is None
                        and not self.session.split_running
                        and self.idle()
                    ),
                )
            )
            # Mit Nachweis: Die zugesagten Befunde stehen im Prüfbericht, sonst
            # ist die Vorbereitung nicht hergestellt — kein Fund an der Anwendung
            # (Durchsicht welle4 C-L3).
            scene = load_scenes().get(self.setup.key)
            promised = tuple(scene.promises.get("findings", ())) if scene is not None else ()
            steps += [
                self.until_step(
                    "befunde der vorbereitung",
                    lambda: set(promised) <= surfaces.shown_findings(self.window),
                    PREPARATION_S,
                ),
                Step(
                    "vorbereitung geprüft",
                    lambda machine: surfaces.require_findings(self.window, promised),
                ),
            ]
        return steps

    def typing_step(self, text: str) -> Step:
        """Tippt in das Feld mit dem Fokus — den Dateinamen im Dateidialog."""

        def act(machine: StepMachine) -> None:
            self.walker.record({"target": "fokus", "typed": text, "button": None})
            self.ports.type_text(text)

        return Step("tippen dateiname", act, settle_ms=SETTLE_MS)

    # --- Wege, Eingaben, Vorschau --------------------------------------------------------------

    def path_steps(self) -> list[Step]:
        """Der Weg der Zeile als Schritte. Ein Fenster als Ziel ist erreicht, sobald es
        dasteht: Ein Klick in seine Mitte träfe ein Bedienelement darin (FD-101).
        Ein Wegziel davor, das grau steht, klickt der Kunde erst, wenn es frei ist;
        das Ziel der Zeile selbst nicht — sein Grau misst der Fehlfall (FD-175). Ein
        Wegziel mit ``text`` ist ein Feld: hinklicken, alles markieren, tippen."""
        target = walk_target(self.row)
        standing = target.partition(":")[0] in surfaces.OPENED_ELSEWHERE
        steps: list[Step] = []
        for (name, button), text in zip(route_of(self.row), route_texts(self.row), strict=True):
            if text and name != target:
                steps += self.typed_steps(name, text, number=False)
                continue
            steps.append(
                self.action_step(name)
                if name == target and name.startswith("feature:")
                else self.walker.step(
                    name,
                    button,
                    stop_before_target=standing and name == target,
                    when_enabled=name != target,
                )
            )
        return steps

    def action_step(self, target: str, *, stop_before: bool | Callable[[], bool] = False) -> Step:
        """Die Handlung am Merkmal: ihr Kopf im Merkmalfenster — oder schon offen im Bild.

        Mit Bild rückt das Fenster *Bohrung ändern* nach der Auswahl in die
        Maßgruppe über der Ansicht, und der Kopf im Merkmalfenster ist verborgen;
        der Kunde tippt dort, ohne zu klicken (Probelauf F-20: nach zwei
        Sekunden „nicht auffindbar“, offscreen ohne Bild war die Zeile da). Der
        Schritt steht dann ohne Klick als Ziel in ``steps``, Zone ``ansicht``.
        ``stop_before`` hält vor dem Klick auf den Kopf an (``Walk.step``).
        """
        inputs = list(self.spec.get("inputs") or {})
        since: dict[str, float] = {}

        def ready() -> bool:
            head = self.widget(target)
            waited = time.perf_counter() - since.setdefault("t", time.perf_counter())
            shown = head is not None and head.isVisible()
            return (
                shown
                or surfaces.feature_in_view(self.window, target)
                or surfaces.in_view(self.window, inputs)
                or waited >= EFFECT_WINDOW_S
            )

        wanted = target.partition(":")[2]

        def foreign_in_view() -> bool:
            group = self.widget("measure.apply")
            shown = surfaces.op_in_view(self.window)
            return bool(shown) and group is not None and group.isVisible() and shown != wanted

        def handed_over(machine: StepMachine) -> None:
            # Der Klick auf den Kopf übergibt die Maßgruppe oder schließt sie
            # (*Zum Langloch ziehen*, *Merkmal verschieben*): Steht danach keine
            # fremde Handlung mehr im Bild, gilt der Vermerk nicht (FD-101).
            if not foreign_in_view():
                self.data.get("unmeasured", {}).pop(f"im_bild:{target}", None)

        def act(machine: StepMachine) -> None:
            if not (
                surfaces.feature_in_view(self.window, target)
                or surfaces.in_view(self.window, inputs)
            ):
                if foreign_in_view():
                    # Im Bild steht eine andere Handlung — an einer gesetzten Bohrung
                    # *Bohrung im ursprünglichen Schritt ändern* (N5). Gemessen wird
                    # die Handlung der Zeile, nicht die im Bild.
                    unmeasured(
                        self.data,
                        f"im_bild:{target}",
                        f"die Maßgruppe im Bild trägt "
                        f"{surfaces.op_in_view(self.window)}, nicht {wanted}",
                    )
                machine.insert(
                    [
                        self.walker.step(target, stop_before_target=stop_before),
                        Step(f"im bild nach {target}", handed_over, settle_ms=SETTLE_MS),
                    ]
                )
                return
            if self.walker.before_target is not None:
                self.walker.before_target(target)
            detail = "steht nach der Auswahl in der Maßgruppe im Bild"
            self.walker.record(
                {"target": target, "why": "ziel", "button": None, "hit": True, "zone": "ansicht"}
                | {"decision": False, "detail": detail}
            )

        return Step(f"handlung {target}", act, ready=ready, settle_ms=SETTLE_MS)

    def apply_step(self) -> Step:
        """Übernehmen: der Hauptknopf — steht die Handlung im Bild, der der Maßgruppe.

        Mit Bild rückt die Handlung in die Maßgruppe über der Ansicht (F-20); ihr
        *Übernehmen* heißt im Wortschatz ``measure.apply`` (N2).
        """
        inputs = list(self.spec.get("inputs") or {})

        def act(machine: StepMachine) -> None:
            if self.apply_target == "feature.apply" and surfaces.in_view(self.window, inputs):
                machine.insert([self.walker.step("measure.apply")])
            elif self.apply_target is not None:
                machine.insert([self.walker.step(self.apply_target)])

        return Step("übernehmen", act)

    def input_steps(self, inputs: Mapping[str, Any]) -> list[Step]:
        """Je Feld: hinklicken, alles markieren, tippen; ohne Mitschreiben mit Tab bestätigen.

        Ein Haken wird geklickt; ein Text, der keine Zahl ist, ist eine Wahl
        (``decision``, E3) — getippt wie jede Eingabe. Welches Feld es ist,
        entscheidet sich erst, wenn es dran ist: im Merkmalfenster oder in der
        Maßgruppe im Bild (``function_surface.field_name``).
        """

        steps: list[Step] = []
        for target, value in inputs.items():
            if not isinstance(value, bool):
                number = isinstance(value, (int, float))
                text = typed_number(float(value), self.variant.unit) if number else str(value)
                steps.append(
                    Step(
                        f"feld {target}",
                        lambda machine, target=target, text=text, number=number: machine.insert(
                            self.typed_steps(surfaces.field_name(self.window, target), text, number)
                        ),
                    )
                )
                continue
            steps.append(self.walker.step(target))
            if isinstance(value, bool):
                steps.append(
                    Step(
                        f"haken {target}",
                        lambda machine, target=target, value=value: self._tick_box(
                            machine, target, value
                        ),
                        settle_ms=SETTLE_MS,
                    )
                )
        return steps

    def typed_steps(self, target: str, text: str, number: bool) -> list[Step]:
        """Hinklicken, alles markieren, tippen — in das Feld, das jetzt dasteht."""
        return [
            self.walker.step(target),
            self.mark_all_step(target),
            Step(
                f"tippen {target}",
                lambda machine: self._type(target, text, decision=not number),
                settle_ms=SETTLE_MS,
            ),
        ]

    def _tick_box(self, machine: StepMachine, target: str, value: bool) -> None:
        """Der Weg hat den Haken einmal geklickt; steht er falsch, kommt ein zweiter Klick."""
        box = self.widget(target)
        if box is not None and bool(box.isChecked()) != value:
            machine.insert([self.walker.step(target)])

    def mark_all_step(self, target: str) -> Step:
        """Alles markieren im Feld des Ziels — erst, wenn der Fokus dort liegt (Review M13)."""
        from PySide6.QtGui import QKeySequence

        keys = QKeySequence(QKeySequence.StandardKey.SelectAll)

        def act(machine: StepMachine) -> None:
            focus_check(self.widget(target), target)
            self.walker.record(
                {"target": "alles markieren", "key": keys.toString(), "button": None}
            )
            self.ports.keys(keys)

        return Step(f"alles markieren {target}", act, settle_ms=SETTLE_MS)

    def _type(self, target: str, text: str, *, decision: bool = False) -> None:
        """Tippt ins Feld des Ziels; eines, das erst beim Verlassen übernimmt, bekommt Tab.

        Getippt wird nur, wenn der Fokus im Feld liegt (:func:`focus_check`):
        Ein nie aktiviertes Fenster hat keinen, und die Ziffern landeten als
        Tasten anderswo, während ``steps`` „getippt“ sagte.
        """
        from PySide6.QtWidgets import QAbstractSpinBox, QApplication

        focus_check(self.widget(target), target)
        self.walker.record({"target": target, "typed": text, "button": None, "decision": decision})
        self.ports.type_text(text)
        focus = QApplication.focusWidget()
        spin = (
            focus
            if isinstance(focus, QAbstractSpinBox)
            else getattr(focus, "parentWidget", lambda: None)()
        )
        if isinstance(spin, QAbstractSpinBox) and not spin.keyboardTracking():
            self.walker.record({"target": target, "key": "Tab", "button": None})
            self.ports.keys("Tab")

    def preview_steps(self, triggering: Sequence[Step] = ()) -> list[Step]:
        """Warten, bis die Vorschau steht oder abgesagt ist — abgelesen, nicht erfragt.

        Steht: das Band zeigt die Legende einer neuen Differenz. Abgesagt: der
        Übernehmen-Knopf ist gesperrt und nennt seinen Grund (Tooltip und
        zugängliche Beschreibung). Beides sieht der Kunde. Eine Zeile ohne
        Vorschau — ein Fensterbefehl mit eigenem Dialog wie *Parameter anlegen* —
        wartet nur auf Ruhe; vorher wartete sie 180 s auf ein Band, das nie kam.
        """
        if not self.expects_preview():
            return [*triggering, self.wait_step("ruhe", self.idle)]
        shown = {"difference": self.window.viewport.difference}

        def remember(machine: StepMachine) -> None:
            shown["difference"] = self.window.viewport.difference

        def settled() -> bool:
            banner = self.widget("preview.banner")
            difference = self.window.viewport.difference
            fresh = difference is not None and difference is not shown["difference"]
            legend = getattr(banner, "legend", None)
            if (
                fresh
                and banner is not None
                and banner.isVisible()
                and legend is not None
                and legend.isVisible()
            ):
                return True
            button = self.widget(self.apply_target) if self.apply_target else None
            if button is not None and not button.isEnabled():
                return bool(button.accessibleDescription() or button.toolTip())
            return not self.apply_target and self.idle()

        return [
            Step("vorschau merken", remember),
            *triggering,
            self.wait_step("vorschau steht", settled),
        ]

    def expects_preview(self) -> bool:
        """Ob die Zeile eine Vorschau zeigt: eine Operation, eine Handlung des Merkmalfensters."""
        target = walk_target(self.row)
        return self.row.get("kind") == "operation" or target.startswith(("feature:", "edge:"))

    def preview_record(self) -> dict[str, Any]:
        """Band, Differenz und Kennzahlen der Vorschau (Prüfpunkt 3, I2; Schema ``preview``)."""
        from app.ui.session import COARSE_PREVIEW_ABOVE
        from tools.file_acceptance import body_digest
        from tools.function_capture import visible_texts

        banner = self.widget("preview.banner")
        difference = self.window.viewport.difference
        triangles = (self.data.get("scene") or {}).get("triangles") or 0
        entries = getattr(difference, "entries", {}) if difference is not None else {}
        shown = {key: entry for key, entry in entries.items() if entry.result is not None}
        metrics = result_metrics(_SceneOf(shown), self.session.project.document, None)
        return {
            "bodies": {str(key): body_digest(entry.result.mesh) for key, entry in shown.items()},
            "coarse": triangles > COARSE_PREVIEW_ABOVE,
            "banner_text": "\n".join(visible_texts(banner))
            if banner is not None and banner.isVisible()
            else "",
            "volume": metrics.get("volume"),
            "extent": metrics.get("extent"),
        }

    def capture_surface(self, root: Any) -> None:
        """G1 bis G8, Texte, Felder und Tab-Kette der offenen Fläche ins Protokoll.

        Stand die Fläche nicht still (:meth:`still_step`), bleiben die Felder
        ungemessen — eine Aufnahme mitten im Übergang ist keine Messung; leere
        Rollleisten zählten sonst die Fenstergröße als gemessen (Z6).
        """
        from tools import function_capture as capture

        if self.restless:
            for name in SURFACE_FIELDS:
                unmeasured(self.data, name, f"ohne Stillstand: {self.restless}")
            if not self.data.get("scrollbars"):
                self.data["scrollbars"] = None
            return
        system = surfaces.system_surface(root)
        if system:
            # Qts Ersatz für das Fenster des Systems ist nicht, was der Kunde sieht
            # (FD-122): keine Messung, Stufe C am echten System.
            for name in SURFACE_FIELDS:
                unmeasured(self.data, name, f"Systemfläche {system}: Stufe C am System")
            return
        theme = self.variant.theme
        for part in surfaces.surface_parts(self.window, walk_target(self.row), root):
            for name, entries in capture.sheet_snapshot(part, theme, self.window_size()).items():
                self.data[name] = [*(self.data.get(name) or []), *entries]
            self.data["texts"] = [*(self.data.get("texts") or []), *capture.text_entries(part)]
            self.data["fields"] = [*(self.data.get("fields") or []), *capture.field_entries(part)]
        self.data["empty_states"] = [
            *(self.data.get("empty_states") or []),
            *capture.empty_states(self.window),
        ]

    # --- Die Phasen ------------------------------------------------------------------------

    def run(self) -> None:
        """Die Phasen der Variante (:data:`PHASES`), jede an der Startszene (Review M5).

        Vor jeder Phase geht der Fall zurück an die Startszene — auch nach einer,
        die mit einer Ausnahme endete. Gelingt das nicht, läuft die Phase nicht:
        Sie stünde sonst an dem, was die vorige liegen ließ, und ihre Messung
        gälte einer anderen Lage. Der Grund steht in ``errors``.
        """
        if self.not_a_case:
            # Unter der kleinsten Fläche wird nichts gemessen — auch kein Fund.
            for name in ("scrollbars", "icons"):
                unmeasured(self.data, name, self.not_a_case)
            self.finish()
            return
        for name in self.variant.phases or PHASES[self.variant.set]:
            phase: Callable[[], None] = getattr(self, f"phase_{name}")
            self.bench["stage"] = name
            try:
                if not self.reset():
                    self.data["errors"].append(f"{name}: Startszene nicht herstellbar")
                    continue
                phase()
            except Exception:
                self.data["errors"].append(f"{name}: {traceback.format_exc()}")
            finally:
                self.persist()
        self.finish()

    def phase_search(self) -> None:
        """Prüfpunkt 1 und I6: jede Suchprobe getippt, der Rang aus ``search_hits``."""

        from app.ui import guide_targets

        probes = [{**probe, "question": False} for probe in self.spec.get("search_probes") or ()]
        probes += [
            {"word": text, "origin": "fragebogen", "question": True}
            for text in self.spec.get("questions") or ()
        ]
        if not probes:
            unmeasured(self.data, "search", "Spezifikation ohne Suchproben")
            return
        found: dict[str, Any] = {}
        for probe in probes:
            word = str(probe["word"])
            hits: list[str] = []
            # Gleichwertige Treffer zählen (F-27): die Operation einer
            # Befundhandlung, der Befehl hinter einer Menüzeile.
            meant: set[str] = set()

            def read(machine: StepMachine, hits: list[str] = hits, meant: set[str] = meant) -> None:
                hits[:] = list(guide_targets.search_hits(self.window))  # type: ignore[attr-defined]
                meant.update(surfaces.search_names(self.window, self.row))

            ok = self.run_steps(
                f"suche {word}",
                [
                    self.walker.step("search"),
                    self.mark_all_step("search"),
                    Step(
                        f"tippen {word}",
                        lambda machine, word=word: self._type("search", word),
                        settle_ms=SEARCH_SETTLE_MS,
                    ),
                    Step("treffer lesen", read),
                    self.key_step("Escape", "suche leeren"),
                ],
            )
            found[word] = {
                "rank": surfaces.search_rank(hits, frozenset(meant)) if ok else None,
                "hits": hits[:10],
                "origin": probe.get("origin"),
                "question": bool(probe["question"]),
            }
        self.data["search"] = found

    def phase_escape(self) -> None:
        """Prüfpunkt 5: Weg, Eingaben, Vorschau, dann Escape — der Stand ist der vorher."""
        inputs = self.spec.get("inputs") or {}
        before = self.scene_now()
        if not inputs:
            unmeasured(self.data, "states.escape", NO_DRAFT)
            return
        self.run_steps(
            "escape",
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                *self.preview_steps(),
                self.key_step("Escape", "entwurf verwerfen"),
                self.wait_step("ruhe", self.idle),
            ],
        )
        self.data["states"].setdefault("before", before)
        self.snapshot("escape")

    def phase_main(self) -> None:
        """Hauptweg: Ort, Weg, Eingaben, Vorschau, Fläche, Übernehmen, Rückgängig, Wiederholen."""
        from PySide6.QtWidgets import QApplication

        from tools import function_capture as capture

        inputs = self.spec.get("inputs") or {}
        target = walk_target(self.row)
        self.snapshot("before")
        self.picture("01-vorher")
        # Fokus vor dem Öffnen der Fläche: unmittelbar vor dem Klick auf das Ziel
        # (Review S4), nicht vor dem ganzen Weg.
        focus: dict[str, Any] = {"before": None, "taken": False, "dialog": False}

        def remember_focus(name: str) -> None:
            if name == target and not focus["taken"]:
                focus["before"], focus["taken"] = QApplication.focusWidget(), True

        def take_surface(machine: StepMachine) -> None:
            root = self.surface()
            # Zurückkehren kann der Fokus nur aus einem Dialog (F-29).
            focus["dialog"] = surfaces.open_dialog(self.window) is not None
            self.claim_surface(root)
            self.capture_surface(root)
            self.data["messages"] = capture.message_entries(self.window)
            apply_button = self.widget(self.apply_target) if self.apply_target else None
            # Erst die Kette, ab dem ersten Feld, in das Tab den Fokus bringt
            # (Review S4); erreicht sie den Hauptknopf, ist das sein Bild „Fokus“.
            focused: dict[str, str] = {}

            def on_focus(widget: Any) -> None:
                if apply_button is not None and widget is apply_button:
                    focused["digest"] = capture.picture_digest(apply_button)

            chain = capture.tab_chain(root, lambda: self.ports.keys("Tab"), on_focus=on_focus)
            self.data["tab_chain"] = chain
            self.data["names"] = [entry["name"] for entry in chain if entry["inside"]]
            if not chain:
                unmeasured(self.data, "tab_chain", "Tab brachte den Fokus nicht in die Fläche")
            if apply_button is not None and apply_button.isVisible():
                self.data["state_images"] = [
                    {
                        "surface": type(root).__name__,
                        "widget": capture.name_of(apply_button),
                        "states": capture.state_images(apply_button, focused.get("digest")),
                    }
                ]
            self.picture("02-flaeche")

        # Wirkt der Klick auf das Ziel selbst — ohne Übernehmen-Knopf und ohne
        # Eingaben, etwa eine Befundhandlung oder ein Fensterbefehl —, ist dieser
        # Klick das Übernehmen: Er fällt in der Phase Übernehmen, mit Uhr und
        # Herzschlag. Vorher stand er im Weg, und das Übernehmen wartete danach
        # auf ein Ergebnis, das schon da war (Probelauf, Befund B).
        route = self.path_steps()
        acting: Step | None = None
        direct = self.apply_target is None and not inputs and bool(route)
        if self.apply_target is not None:
            acting = self.apply_step()
        elif direct:
            route, acting = route[:-1], route[-1]

        def before_apply(machine: StepMachine) -> None:
            self.data["spot"] = self.spot()
            if inputs and self.expects_preview():
                self.data["preview"] = self.preview_record()
                self.snapshot("preview")
            elif inputs:
                unmeasured(self.data, "preview", "die Zeile zeigt keine Vorschau")

        applying, finish = self.apply_steps(acting)
        # V4: vor dem Klick, der übernimmt, eine Vorhersage binden (FD-168).
        gate = (
            prediction.gate_for(self, self.apply_target or target, folder=self.folder / "v4")
            if acting is not None and self.variant.predict
            else None
        )
        self.walker.before_target = remember_focus
        try:
            self.run_steps(
                PATH_PHASE,
                [
                    *route,
                    *self.input_steps(inputs),
                    *(self.preview_steps() if inputs else [self.wait_step("ruhe", self.idle)]),
                    self.still_step("fläche steht still", self.surface),
                    Step("fläche aufnehmen", take_surface),
                    Step("vor dem übernehmen", before_apply),
                    *(gate.before_steps() if gate is not None else ()),
                    *applying,
                    *(gate.after_steps() if gate is not None else ()),
                ],
            )
            finish()
        finally:
            self.walker.before_target = None
        self.data["place"] = place_of(self.data["steps"], target)
        if self.data["place"]["error"] is not None:
            unmeasured(self.data, "result", "der Hauptweg kam nicht an")
            return
        after = QApplication.focusWidget()
        if not focus["dialog"]:
            unmeasured(self.data, "focus_return", WITHOUT_DIALOG)
        elif focus["before"] is None or after is None:
            unmeasured(
                self.data,
                "focus_return",
                "kein Fokus vor dem Öffnen" if focus["before"] is None else "kein Fokus danach",
            )
        else:
            # Dasselbe Widget, nicht nur derselbe Name (Review S4).
            self.data["focus_return"] = after is focus["before"]
        self.undo_and_redo()

    def spot(self) -> dict[str, Any] | None:
        """E4: liegt über der bearbeiteten Stelle ein Fenster? Über ``view:`` und die Probe.

        Die bearbeitete Stelle ist das gewählte Merkmal oder die gewählte Kante
        (``view.edge:`` im Auswahlweg der Zeile, Durchsicht welle4 C-M4).
        """
        edges = [
            str(step.get("target"))
            for step in self.row.get("route") or ()
            if str(step.get("target") or "").startswith("view.edge:")
        ]
        if self.selected is not None:
            name = f"view:{self.selected[0]}.{self.selected[1]}"
        elif edges:
            name = edges[-1]
        else:
            return None
        try:
            click = self.ports.next_click(name)
        except LookupError as error:
            # Die gewählte Stelle ist die Stelle — kein Ersatz durch den Körper.
            unmeasured(self.data, "spot", str(error))
            return None
        point = self.ports.centre(click.rect)
        hit = self.ports.widget_under(point)
        covered = hit is not None and not self.ports.covers(click, hit)
        return {
            "point": self.ports.point_data(point),
            "covered_by": type(hit.window()).__name__ if covered and hit is not None else None,
        }

    def effect_steps(
        self,
        label: str,
        observe: Callable[[], None] | None = None,
        timeout_s: float = STEP_TIMEOUT_S,
    ) -> tuple[list[Step], dict[str, Any]]:
        """Erst die Wirkung, dann das Ergebnis — eine Handlung ohne Wirkung wartet keine Frist ab.

        Wirkung heißt: Die Sitzung rechnet, oder ein neues Ergebnis steht. Kommt
        binnen :data:`EFFECT_WINDOW_S` keine, ist das die Antwort
        (``effect`` falsch). Sonst wartet ein zweiter Schritt, bis die Sitzung
        ruht und ein neues Ergebnis trägt (``settled``, ``done`` die Uhrzeit).
        Läuft dessen Frist ab, bleibt ``settled`` falsch; der Aufrufer schreibt
        den Grund ins Protokoll (Probelauf, Befund B: vorher stand die Frist nur
        als Fehler da). ``observe`` läuft in jedem Takt mit. „Neu“ heißt: anders
        als das Ergebnis, das stand, als die Schritte begannen — nicht als beim
        Bauen der Schritte (Weg und Übernehmen laufen in einem Automaten).
        """
        state: dict[str, Any] = {"effect": False, "settled": False, "done": None, "was": None}

        def remember(machine: StepMachine) -> None:
            state["was"] = self.session.last_result

        def started() -> bool:
            if observe is not None:
                observe()
            return bool(self.session.busy or self.session.last_result is not state["was"])

        def landed() -> bool:
            if observe is not None:
                observe()
            if self.idle() and self.session.last_result is not state["was"]:
                state["settled"], state["done"] = True, time.perf_counter()
            return bool(state["settled"])

        def silent() -> BenchFinding:
            # Eine Frist ohne fertiges Ergebnis ist ein Fund an Prüfpunkt 6
            # (Entscheidung Koordinator), kein Fehler des Prüfstands.
            return BenchFinding(
                NO_RESPONSE, label, f"nach {timeout_s:.0f} s kein fertiges Ergebnis"
            )

        def follow(machine: StepMachine) -> None:
            state["effect"] = started()
            if state["effect"]:
                waiting = self.wait_step(f"{label} steht", landed, timeout_s=timeout_s)
                waiting.on_timeout = silent
                machine.insert([waiting])

        steps = [
            Step(f"{label} merken", remember),
            self.until_step(f"{label} wirkt", started),
            Step(f"{label} prüfen", follow),
        ]
        return steps, state

    def apply_steps(self, acting: Step | None) -> tuple[list[Step], Callable[[], None]]:
        """Übernehmen mit Herzschlag und Zeiten (Prüfpunkt 6), dann Ergebnis und Kommandozeile.

        ``acting`` ist der Klick, der übernimmt: der Übernehmen-Knopf, oder bei
        einer Zeile, deren Ziel selbst wirkt, der Klick auf das Ziel. Die
        Schritte laufen im selben Automaten wie der Weg: Ein modaler Dialog, den
        der Weg öffnete, schlösse ein Ende des Automaten mit Escape, und
        *Anlegen* fände ihn nicht mehr (Probelauf F-25). Der Abschluss danach
        schreibt Zeiten, Abdruck, Ergebnis und Kommandozeile.
        """
        from PySide6.QtWidgets import QApplication, QProgressBar

        previous: dict[str, Any] = {"result": None}
        timing: dict[str, Any] = {
            "total_s": None,
            "first_feedback_s": None,
            "progress_shown_s": None,
            "cancel_shown_s": None,
            "main_gap_ms": None,
            "budget_s": self.spec.get("budget_s"),
        }
        status_before = self.window.statusBar().currentMessage()
        moment = {"t0": 0.0}

        def start(machine: StepMachine) -> None:
            self.walker.phase = APPLY_PHASE
            previous["result"] = self.session.last_result
            moment["t0"] = time.perf_counter()
            self.heartbeat.open(moment["t0"])

        def observe() -> None:
            elapsed = round(time.perf_counter() - moment["t0"], 3)
            if timing["first_feedback_s"] is None and (
                QApplication.overrideCursor() is not None
                or self.session.busy
                or self.window.statusBar().currentMessage() != status_before
                or self.session.last_result is not previous["result"]
            ):
                timing["first_feedback_s"] = elapsed
            if timing["progress_shown_s"] is None and any(
                bar.isVisible() for bar in self.window.statusBar().findChildren(QProgressBar)
            ):
                timing["progress_shown_s"] = elapsed
            cancel = self.widget("progress.cancel")
            if timing["cancel_shown_s"] is None and cancel is not None and cancel.isVisible():
                timing["cancel_shown_s"] = elapsed

        effect, state = self.effect_steps("ergebnis", observe)
        steps = [Step("uhr", start), effect[0], *([acting] if acting else []), *effect[1:]]

        def finish() -> None:
            if not moment["t0"]:
                return
            self.measured_apply(timing, state, moment["t0"])

        return steps, finish

    def measured_apply(self, timing: dict[str, Any], state: Mapping[str, Any], t0: float) -> None:
        """Nach dem Übernehmen ins Protokoll: Zeiten, Abdruck, Ergebnis, Kommandozeile."""
        timing["main_gap_ms"] = self.heartbeat.close(time.perf_counter())
        if state["settled"]:
            timing["total_s"] = round(state["done"] - t0, 3)
        elif not state["effect"]:
            unmeasured(
                self.data,
                "timing",
                f"keine Wirkung binnen {EFFECT_WINDOW_S:g} s nach dem Klick — "
                "weder Rechnung noch neues Ergebnis",
            )
        else:
            unmeasured(
                self.data,
                "timing",
                f"keine Rückmeldung: nach {STEP_TIMEOUT_S:.0f} s kein fertiges Ergebnis",
            )
        self.data["timing"] = timing
        # Z2: Ein Fenster, das nach dem Übernehmen offen steht, hat die Wache
        # schon in modals notiert; hier steht es zum Lauf dazu.
        self.watch.note_after(APPLY_PHASE)
        self.watch.poll()
        applied = self.snapshot("applied")
        self.picture("03-uebernommen")
        # E4 an einer Handlung am ganzen Körper: ihr Rahmen im Ergebnisbild (FD-169).
        body_spot(self.window, self.data)
        result = self.session.last_result
        if result is not None:
            self.data["result"] = {
                "metrics": result_metrics(
                    result.scene, self.session.project.document, self.selected
                ),
                "digest": bodies_digest(applied["bodies"]),
            }
        self.data["cli"] = self.compare_with_cli()

    def undo_and_redo(self) -> None:
        """Rückgängig und Wiederholen über ihre Tasten (Prüfpunkt 5)."""
        for label, keys in (("undo", self.undo_keys()), ("redo", self.redo_keys())):
            # Wirkt die Taste nicht, ist das die Messung — der Abdruck sagt es
            # (Prüfpunkt 5), und gewartet wird nicht. Rechnet sie und wird nicht
            # fertig, steht der Grund im Protokoll.
            effect, state = self.effect_steps(label, timeout_s=60.0)
            self.run_steps(label, [effect[0], self.key_step(keys, label), *effect[1:]])
            if state["effect"] and not state["settled"]:
                unmeasured(
                    self.data,
                    f"states.{label}",
                    "keine Rückmeldung: nach 60 s kein fertiges Ergebnis",
                )
            self.snapshot(label)

    def compare_with_cli(self) -> dict[str, Any] | None:
        """Prüfpunkt 4: Dieselben Werte über die Kommandozeile ergeben ein druckgleiches Netz.

        Die Startszene wird kopiert, ``app.cli.main run`` legt den Schritt mit den
        Werten des übernommenen an, und beide Dokumente gehen in derselben Güte
        (fein) durch den einen Vergleich der Suite (``tests/print_equal``). Der
        Prozess erbt die umgebogenen Nutzerordner dieses Falls.
        """
        import os
        import shutil
        import subprocess
        from copy import deepcopy

        from app.core.scene.serialise import operation_to_data

        states = self.data["states"]
        document = self.session.project.document
        grown = len(states.get("applied", {}).get("ops", ())) > len(
            states.get("before", {}).get("ops", ())
        )
        if not document.ops or not grown:
            unmeasured(self.data, "cli", "kein neuer Schritt im Verlauf")
            return None
        scene = self.scenes / f"{self.scene_key}.p3d"
        if not scene.is_file():
            unmeasured(self.data, "cli", "Startszene ohne Datei")
            return None
        arguments = cli_arguments(operation_to_data(document.ops[-1]))
        if arguments is None:
            unmeasured(self.data, "cli", "Werte ohne Feld auf der Kommandozeile")
            return None
        copy = self.folder / "cli.p3d"
        shutil.copyfile(scene, copy)
        # Im Fallordner wie der Fall selbst (RC-10); ``app`` kommt dann über den
        # Pfad aus diesem Baum, nicht aus dem Arbeitsordner.
        tree = str(Path(__file__).resolve().parent.parent)
        finished = subprocess.run(
            [sys.executable, "-m", "app.cli.main", *cli_command(arguments, str(copy))],
            cwd=self.folder,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(filter(None, [tree, os.environ.get("PYTHONPATH")])),
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        if finished.returncode != 0:
            self.data["errors"].append(f"Kommandozeile: {finished.stderr[-2000:]}")
            unmeasured(self.data, "cli", "die Kommandozeile lehnte ab")
            return None
        from app.core.scene import project as projects
        from app.core.scene.evaluate import evaluate
        from tests import print_equal
        from tools.file_acceptance import body_digest

        loaded = projects.load(copy)
        profile = self.session.profile
        window_result = evaluate(
            deepcopy(document), profile, sources=projects.ProjectSources(self.session.project)
        )
        cli_result = evaluate(loaded.document, profile, sources=projects.ProjectSources(loaded))
        verdict = print_equal.compare(
            print_equal.shot(window_result, exports=()),
            print_equal.shot(cli_result, exports=()),
        )
        return {
            "digest": bodies_digest(
                {
                    str(key): body_digest(entry.mesh)
                    for key, entry in cli_result.scene.objects.items()
                }
            ),
            "max_deviation_mm": verdict.largest,
            "print_equal": verdict.print_equal,
        }

    def phase_fault(self) -> None:
        """Prüfpunkt 7: erzwungener Fehlfall, Meldung, erste Handlung und ihre Wirkung."""
        from tools import function_capture as capture

        fault = self.spec.get("fault_case")
        if not fault:
            unmeasured(self.data, "messages", "Spezifikation ohne Fehlfall")
            return
        if not self.fault_scene(str(fault.get("start_scene") or "")):
            return
        messages: list[dict[str, Any]] = []
        shown: dict[str, set[str]] = {"before": set()}
        findings_before = surfaces.report_findings(self.session)

        def in_dialog() -> list[dict[str, Any]]:
            # Ein Dialog sagt ab, wo er steht (``ParameterDialog.problem``): neu
            # sichtbarer Text nach dem Hauptknopf ist seine Meldung (F-24). Eine
            # Meldung im Hausstil liest ``message_entries`` samt Handlungen.
            dialog = surfaces.open_dialog(self.window)
            new = (
                [t for t in capture.visible_texts(dialog) if t not in shown["before"]]
                if dialog is not None and "MessageDialog" not in surfaces.classes_of(dialog)
                else []
            )
            return [{"text": " ".join(new), "actions": [], "kind": "meldung"}] if new else []

        def remember(machine: StepMachine) -> None:
            dialog = surfaces.open_dialog(self.window)
            shown["before"] = set(capture.visible_texts(dialog)) if dialog is not None else set()

        # Als Sperrgrund zählt nur der Grund an den Zielen der Zeile (C-L1).
        targets = [walk_target(self.row), *([self.apply_target] if self.apply_target else [])]

        def said() -> list[dict[str, Any]]:
            return [*surfaces.fault_messages(self.window, targets), *in_dialog()]

        def read(machine: StepMachine) -> None:
            messages.extend(said())
            messages.extend(
                {"text": text, "actions": [], "kind": "befund"}
                for code, text in surfaces.report_findings(self.session).items()
                if code not in findings_before
            )
            # Noch innerhalb der modalen Schleife: Nach run_steps hat der
            # Automat den Dialog bereits mit Escape geschlossen.
            self.picture("04-fehlfall")
            # Der Sperrgrund eines grauen Ziels steht nur in seiner Kurzhilfe:
            # als eigenes Bild, wie der Kunde ihn beim Überfahren sieht (FD-149);
            # grau ohne Kurzhilfe sagt das Protokoll (RC-7).
            self.data["images"].extend(
                tooltips.reason_pictures(
                    self.widget,
                    targets,
                    self.folder,
                    self.out,
                    silent=lambda target: unmeasured(
                        self.data, f"sperrgrund:{target}", tooltips.NO_VISIBLE_REASON
                    ),
                )
            )

        computed = {"seen": False}

        def busy() -> bool:
            computed["seen"] = computed["seen"] or surfaces.computing(self.window)
            return computed["seen"]

        def start(machine: StepMachine) -> None:
            if not computed["seen"] and surfaces.open_dialog(self.window) is not None:
                machine.insert(
                    [self.walker.step("dialog.accept"), self.until_step("rechnet", busy, 10.0)]
                )

        def seen_busy(machine: StepMachine) -> None:
            if not computed["seen"]:
                # Ohne sichtbare Rechnung ist „während der Rechnung“ nicht hergestellt
                # — Prüfpunkt 7 heißt dann nicht gelaufen, nicht „keine Meldung“.
                raise RuntimeError("keine sichtbare Rechnung nach den Eingaben des Fehlfalls")

        inputs = fault.get("inputs") or {}
        own = [
            self.walker.step(
                name,
                with_modifier(str(entry.get("button") or "left"), str(entry.get("modifier") or "")),
            )
            for entry in fault.get("route") or ()
            if (name := str(entry["target"]))
        ]
        if fault.get("during") == "rechnung":
            # Weg und Eingaben stoßen eine Rechnung an; während sie läuft, klickt
            # der Kunde die Handlung der Zeile (F-34: vorher fuhr der Prüfstand
            # Weg und Startszene des Fehlfalls gar nicht).
            steps = [
                *own,
                *self.input_steps(inputs),
                Step("dialog merken", remember),
                # Was der Kunde von der Rechnung sieht: Sitzung, Zeiger, Balken,
                # *Abbrechen* oder das Vorschauband (function_surface.computing).
                # Rechnet die Eingabe nur eine Schätzung, stößt der Hauptknopf des
                # offenen Dialogs die Rechnung an.
                self.until_step("rechnet", busy),
                Step("anstoßen", start),
                Step("rechnung gesehen", seen_busy),
                *self.path_steps(),
            ]
        else:
            steps = [
                *(own or self.path_steps()),
                *self.input_steps(inputs),
                Step("dialog merken", remember),
            ]
            if self.apply_target is not None and inputs:
                steps.append(self.apply_step())
            elif inputs:
                steps += self.preview_steps()
        self.run_steps(
            FAULT_PHASE,
            [
                *steps,
                # Die Meldung kommt nach der Absage — erst sie, dann lesen (Review M1).
                self.until_step("meldung", lambda: bool(said())),
                Step("meldung lesen", read),
            ],
        )
        actions = [action for message in messages for action in message.get("actions", ())]
        nameless = [str(action.get("label", "")) for action in actions if not action.get("target")]
        if nameless:
            # Eine Lücke im Wortschatz (W), kein Fund an der Anwendung (Review M11).
            unmeasured(self.data, "messages", f"Handlung ohne Wortschatzname: {nameless}")
        offered = [action for action in actions if action.get("target")]
        if offered:
            action = offered[0]
            before = self.scene_now()
            modal_before = len(self.watch.modals)
            self.run_steps(
                "handlung der meldung",
                [
                    self.walker.step(str(action["target"])),
                    self.wait_step("ruhe", self.idle, EFFECT_WINDOW_S * 30),
                ],
            )
            self.watch.poll()
            after = self.scene_now()
            action["clicked"] = True
            action["effect"] = (
                compare_prints(before, after)["same"] is False
                or len(self.watch.modals) > modal_before
                or surfaces.open_dialog(self.window) is not None
            )
        for message in messages:
            message["phase"] = FAULT_PHASE
        self.data["messages"] = [*(self.data.get("messages") or []), *messages]

    def mark_own(self, machine: StepMachine) -> None:
        """Der offene Dialog der Zeile ist ihre Fläche, keine fremde Nachfrage (F-26)."""
        dialog = surfaces.open_dialog(self.window)
        if dialog is not None:
            self.claim_surface(dialog)

    def claim_surface(self, root: Any) -> None:
        """Die Fläche der Zeile zählt nicht als fremdes Fenster — eine Meldung oder Frage
        schon, außer die Zeile ist sie selbst (``function_surface.own_surface``)."""
        if surfaces.own_surface(self.row, root):
            self.watch.own.add(type(root).__name__)

    def phase_abort(self) -> None:
        """Prüfpunkt 14: *Abbrechen* während der Rechnung, danach der Stand von vorher."""
        if self.scene_key not in SLOW_SCENES:
            unmeasured(self.data, "abort", "Startszene rechnet nicht lang genug")
            return
        inputs = self.spec.get("inputs") or {}
        before = self.scene_now()
        moment: dict[str, Any] = {"t0": 0.0, "shown": None}

        def start(machine: StepMachine) -> None:
            moment["t0"] = time.perf_counter()

        def cancel_visible() -> bool:
            cancel = self.widget("progress.cancel")
            if cancel is not None and cancel.isVisible():
                moment["shown"] = round(time.perf_counter() - moment["t0"], 3)
                return True
            return False

        steps = [*self.path_steps(), *self.input_steps(inputs), Step("uhr", start)]
        if self.apply_target:
            steps.append(self.apply_step())
        steps += [
            self.wait_step("abbrechen sichtbar", cancel_visible, timeout_s=30.0),
            self.walker.step("progress.cancel"),
            self.wait_step("ruhe", lambda: not self.session.busy, timeout_s=60.0),
        ]
        clicked = self.run_steps("abbruch", steps)
        # Späte Ereignisse nach dem Abbruch abwarten — im Automaten, damit ein
        # spätes Fenster mit Escape geschlossen wird, statt die Schleife zu halten.
        self.run_steps(
            "nach dem abbruch",
            [self.until_step("spätfenster", lambda: False, at_most_s=LATE_WINDOW_S)],
        )
        self.data["states"].setdefault("before", before)
        self.snapshot("aborted")
        # Wie lange die Rechnung dauert, die hier abgebrochen wurde: aus dem Lauf
        # ohne Abbruch an derselben Szene — dem Hauptweg (Review M4) —, roh auf
        # diesem Rechner; nicht die Ladezeit der Startszene.
        self.data["abort"] = abort_entry(self.data, moment["shown"], clicked)

    def phase_halt(self) -> None:
        """Prüfpunkt 15: Haltgrund mit Schrittnummer; Einfügen vor dem letzten Schritt.

        Die Marke steht vor dem letzten Schritt der Startszene. Entsteht erst dort,
        worüber der Weg der Zeile führt — die Bohrung von *Bohrung ändern*, der
        Befund des Körpers unter dem Bett —, gibt es den Weg am Stand davor nicht,
        und der Fall hieß „nicht auffindbar“, wo der Kunde nur nichts zu wählen
        hätte (Läufe 001, 002). Dann wendet der Fall die Zeile einmal an und setzt
        die Marke vor diesen Schritt: Der Stand davor ist die Startszene.
        """
        if self.scene_key == "halt":
            self.read_halt()
        else:
            unmeasured(self.data, "halt", "Startszene ohne angehaltene Kette")
        if len(self.session.project.document.ops) < 1:
            unmeasured(self.data, "insertion", "kein Schritt, vor dem eingefügt werden könnte")
            return
        record: dict[str, Any] = {"outcome": None, "text": "", "actions": []}
        absent: list[str] = []
        self.run_steps("einfügen", self.insertion_steps(record, absent))
        if absent and self.reset():
            first = list(absent)
            absent.clear()
            inputs = self.spec.get("inputs") or {}
            before = len(self.session.project.document.ops)
            self.run_steps(
                "einfügen",
                [
                    *self.path_steps(),
                    *self.input_steps(inputs),
                    *([self.apply_step()] if self.apply_target else []),
                    # Der Schritt der Zeile steht erst, wenn die Sitzung ihn
                    # angelegt hat — ein Augenblick Ruhe davor ist kein Beleg.
                    self.until_step(
                        "schritt der zeile",
                        lambda: len(self.session.project.document.ops) > before,
                    ),
                    self.wait_step("ruhe", self.settled),
                    *self.insertion_steps(record, absent),
                ],
            )
            if absent:
                unmeasured(
                    self.data,
                    "insertion",
                    f"vor dem letzten Schritt fehlt {', '.join(first)}, und die Zeile legt "
                    "keinen eigenen Schritt an, vor den die Marke könnte",
                )
                return
        self.data["insertion"] = record if record["outcome"] is not None else None
        if record["outcome"] is None:
            unmeasured(self.data, "insertion", "der Weg zur Einfügemarke kam nicht an")

    def settled(self) -> bool:
        """Gerechnet und gezeigt: Die Sitzung ruht, und ihr Ergebnis gilt dem Stand."""
        return self.idle() and bool(getattr(self.session, "result_current", True))

    def insertion_steps(self, record: dict[str, Any], absent: list[str]) -> list[Step]:
        """Marke vor den letzten Schritt, dann am Stand davor der Weg der Zeile und ihre Antwort.

        Fehlt am Stand davor ein Wegziel aus der Szene (``function_surface.SCENE_KINDS``),
        steht es in ``absent``, und der Weg wird nicht gegangen. Verglichen wird mit
        dem Ergebnis am Stand davor, nicht mit dem Endstand: Die Marke allein
        rechnet schon neu, und jede Absage hieß sonst „ergebnis“.
        """
        from tools import function_capture as capture

        previous: dict[str, Any] = {"result": None}
        began: dict[str, float | None] = {"t": None}

        def answered() -> bool:
            # Gelesen wird erst, wenn die Sitzung nicht mehr rechnet und ein
            # Ergebnis da ist — oder nach der Frist ohne eines (Review M1).
            now = time.perf_counter()
            if began["t"] is None:
                began["t"] = now
            if self.session.busy:
                return False
            return (
                self.session.last_result is not previous["result"]
                or now - began["t"] >= EFFECT_WINDOW_S
            )

        def read(machine: StepMachine) -> None:
            messages = capture.message_entries(self.window)
            record["text"] = " ".join(message["text"] for message in messages)
            record["actions"] = [
                {"label": action["label"], "target": action["target"]}
                for message in messages
                for action in message["actions"]
            ]
            changed = self.session.last_result is not previous["result"]
            record["outcome"] = "ergebnis" if changed else "absage"

        def marker(machine: StepMachine) -> None:
            length = len(self.session.project.document.ops)
            machine.insert(
                [
                    self.walker.step(f"history.row:{length}", "right"),
                    self.walker.step("menu:history.insert"),
                    self.wait_step("stand davor", self.settled),
                    Step("weg am stand davor", way),
                ]
            )

        def way(machine: StepMachine) -> None:
            previous["result"] = self.session.last_result
            absent[:] = surfaces.absent_on_the_way(
                self.window, [name for name, _button in route_of(self.row)]
            )
            if absent:
                return
            machine.insert(
                [
                    *self.path_steps(),
                    *self.input_steps(self.spec.get("inputs") or {}),
                    *([self.apply_step()] if self.apply_target else []),
                    Step("antwort", lambda machine: None, ready=answered),
                    Step("antwort lesen", read),
                ]
            )

        return [Step("marke", marker)]

    def read_halt(self) -> None:
        """Der Haltgrund dort, wo die Anwendung ihn zeigt (Review M10).

        Hält die Kette, nennt der Prüfbericht den Grund am angehaltenen Schritt
        (der Befund mit ``op_id == stopped_at``). Gelesen wird der Text seiner
        Zeile, wie der Kunde ihn liest; ``step`` ist die Nummer, die der Verlauf
        dem Schritt gibt (``labels.step_number``) — U prüft, ob der Text sie
        nennt. Gibt es den Befund nicht, ist der Halt nicht gemessen; ein
        beliebiger Text mit einer Zahl ist kein Ersatz.
        """
        from PySide6.QtCore import Qt

        from app.ui.labels import step_number as shown_number

        result = self.session.last_result
        stopped = getattr(result, "stopped_at", None)
        if stopped is None:
            unmeasured(self.data, "halt", "die Startszene hält nicht an")
            return
        listing = self.window.report.list
        for row in range(listing.count()):
            item = listing.item(row)
            finding = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if item is not None and getattr(finding, "op_id", None) == stopped:
                self.data["halt"] = {
                    "text": item.text(),
                    "step": shown_number(self.session.project.document, stopped),
                }
                return
        unmeasured(self.data, "halt", "der Prüfbericht nennt keinen Befund am angehaltenen Schritt")

    def phase_licence(self) -> None:
        """Prüfpunkt 18: Wie das Ziel im Lizenzzustand dasteht, und ob Schreiben gesperrt ist.

        Steht das Ziel offen, geht der Kunde den ganzen Weg — Eingaben,
        Übernehmen —, denn erst dort zeigt sich, ob die Funktion schreibt: Sie
        ändert das Dokument, oder der Kern lehnt an der Lizenzgrenze ab
        (``function_surface.licence_refusal``). Vorher klickte der Lauf nur das
        Ziel, und eine Befundhandlung, deren Absage als Meldungsfenster kam,
        galt als lesend (Probelauf F-35).

        Der Lauf trägt ``state`` — ``angeboten``, ``grau`` oder ``fehlt``
        (``function_points.LICENCE_RUN_STATES``) — und den Grund des grauen Ziels.
        """
        target = walk_target(self.row)
        inputs = list(self.spec.get("inputs") or {})
        before = self.scene_now()
        refused: list[str] = []

        def note(error: object) -> None:
            if surfaces.licence_refusal(error):
                refused.append(type(error).__name__)

        def standing() -> bool:
            head = self.widget(target)
            return (head is not None and head.isVisible()) or surfaces.in_view(self.window, inputs)

        selection = [
            self.walker.step(name, button) for name, button in route_of(self.row) if name != target
        ]
        read: dict[str, Any] = {}  # Ein Fenster als Ziel: gelesen, solange es steht (RC-4).
        if is_window(target):
            selection.append(self.window_step(target, read))
        if target.startswith("feature:"):
            # Die Handlung am Merkmal steht nach der Auswahl erst im Fenster oder
            # im Bild — gefragt wird danach, nicht im selben Augenblick (F-20).
            selection.append(self.until_step("handlung steht", standing))
        self.session.failed.connect(note)
        try:
            if not self.run_steps(PATH_PHASE, selection):
                unmeasured(
                    self.data, f"licence_runs.{self.variant.licence}", "Auswahlweg abgebrochen"
                )
                return
            state, reason = self.licence_state(target, inputs, read)
            if state == "angeboten" and not read:
                acting = [
                    self.action_step(target)
                    if target.startswith("feature:")
                    else self.walker.step(target),
                    Step("eigene fläche", self.mark_own),
                    *self.input_steps(self.spec.get("inputs") or {}),
                ]
                if self.apply_target is not None:
                    acting.append(self.apply_step())
                effect, _done = self.effect_steps("lizenz")
                if not self.run_steps("lizenz", [effect[0], *acting, *effect[1:]]):
                    unmeasured(
                        self.data,
                        f"licence_runs.{self.variant.licence}",
                        "Lizenzhandlung abgebrochen",
                    )
                    return
        finally:
            self.session.failed.disconnect(note)
        writes = (
            self.row.get("kind") == "operation"
            or bool(refused)
            or compare_prints(before, self.scene_now())["same"] is False
        )
        self.data["licence_runs"] = {
            self.variant.licence: {"writes": writes, "state": state, "reason": reason}
        }

    def phase_surface(self) -> None:
        """Zoll, Skalierung, Thema, Bewegung: Weg bis zur offenen Fläche, dann ihre Aufnahmen."""
        from copy import deepcopy

        from tools.file_acceptance import write_json
        from tools.function_protocol import safe_name

        before: dict[str, Any] = {}
        decided = {"at_once": False}

        def at_once() -> bool:
            # Gefragt, wenn das Ziel dasteht: Eine Merkmalshandlung zeigt erst
            # dann, ob ihr Kopf aufklappt (FD-115).
            decided["at_once"] = surfaces.acts_at_once(self.window, target)
            return decided["at_once"]

        def take(machine: StepMachine) -> None:
            root = self.surface()
            # Die eigene Fläche der Zeile ist kein fremdes Fenster (Review L13).
            self.claim_surface(root)
            self.capture_surface(root)
            # Ein Bild je Fläche, im Sprachfall mit Sprache und Zeile (F-31).
            self.picture(
                surfaces.picture_label(self.variant, str(self.row.get("id") or ""), "flaeche")
            )
            if decided["at_once"]:
                before.update(deepcopy(self.data))
                # V4 auch im Sprachfall: vor dem Klick der Soforthandlung (FD-168).
                row_id = str(self.row.get("id") or "")
                gate = (
                    prediction.gate_for(
                        self,
                        target,
                        folder=self.folder / "v4" / safe_name(row_id),
                        label=lambda name: surfaces.picture_label(self.variant, row_id, name),
                    )
                    if self.variant.predict
                    else None
                )
                machine.insert(
                    [
                        *(gate.before_steps() if gate is not None else ()),
                        self.walker.step(target),
                        self.still_step("geöffnete fläche steht still", self.surface),
                        Step("geöffnete fläche aufnehmen", opened),
                        *(gate.after_steps() if gate is not None else ()),
                    ]
                )

        def opened(machine: StepMachine) -> None:
            dialog = surfaces.open_dialog(self.window)
            if dialog is None:
                return
            # Zwei Flächen sind zwei Messungen, sonst zählt E5 Bericht und
            # Dialog zusammen. Der bestehende Berichtseinsammler liest beide.
            path = self.folder / "surfaces" / f"{safe_name(str(self.row['id']))}-vorher.json"
            write_json(path, before)
            for name in SURFACE_FIELDS:
                self.data[name] = None
                self.data["unmeasured"].pop(name, None)
            self.claim_surface(dialog)
            self.capture_surface(dialog)
            self.picture(
                surfaces.picture_label(self.variant, str(self.row["id"]), "flaeche-geoeffnet")
            )

        target = walk_target(self.row)
        route = self.path_steps()
        last, button = route_of(self.row)[-1] if route else ("", "left")
        if route and last == target and target.partition(":")[0] not in surfaces.OPENED_ELSEWHERE:
            # Wirkt die Handlung mit dem Klick, wird erst vor ihrer Wirkung
            # gemessen, dann wirklich geklickt (:func:`take`): Manche öffnen
            # weitere Eingaben, deren Fläche getrennt aufgenommen wird.
            route[-1] = (
                self.action_step(target, stop_before=at_once)
                if target.startswith("feature:")
                else self.walker.step(target, button, stop_before_target=at_once)
            )
        self.run_steps(
            PATH_PHASE,
            [
                *route,
                # Aufgenommen wird nach dem letzten Übergang (Review M1).
                self.still_step("fläche steht still", self.surface),
                Step("aufnehmen", take),
            ],
        )


class _SceneOf:
    """Die Einträge einer Vorschaudifferenz als Szene für :func:`result_metrics`."""

    def __init__(self, entries: Mapping[Any, Any]) -> None:
        self.objects = {
            key: _Body(entry.result.mesh, getattr(entry.result, "features", {}) or {})
            for key, entry in entries.items()
            if entry.result is not None
        }


@dataclass(slots=True)
class _Body:
    mesh: Any
    features: Mapping[str, Any]
