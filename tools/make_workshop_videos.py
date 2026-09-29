"""Fünf STL-Tutorials über den einfachen Kundenweg, mit Nahaufnahmen und Bildnachweis.

    .venv\\Scripts\\python.exe tools/make_workshop_videos.py bohrung-anpassen --language de

Je Film und Sprache läuft genau ein Prozess. Erst ``main`` isoliert APPDATA,
LOCALAPPDATA und die XDG-Verzeichnisse, danach importiert es die Anwendung.
Ein Import dieses Moduls verändert weder die Umgebung noch Nutzerdaten.
``--capture-only`` behält Bilder, Schnittplan, Projekte und Short-Bildquellen;
``--encode-only`` kodiert einen bereits abgeschlossenen Aufnahmelauf.

**Gezeigt wird der Weg, den ein Kunde nimmt** (Entscheidung Robert, 13.09.2026:
nicht über die Befehlspalette): Eine Bohrung wird angeklickt und bekommt ihre
neue Zahl in der Karte rechts, der Knopf *Übernehmen* darunter führt sie aus.
Verrunden und Fase kommen aus der Handlungsliste zur Auswahl, das Verschieben
aus der Bewegen-Leiste unten, ein benanntes Maß aus dem Doppelklick auf den
Schritt im Verlauf. Jedes Ergebnis bekommt eine Nahaufnahme und eine kurze
Kamerafahrt, damit man sieht, was sich geändert hat.

Die Oberfläche stammt aus dem Entwicklungsstand und wird als Vorschau benannt.
Die eigenen Ausgangs-STLs entstehen vor dem Film über registrierte Operationen.
Die Aufnahmetechnik und Musik kommen aus ``make_longform_video``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "marketing" / "video" / "workshop-2026-09"
STORIES = {
    "bohrung-anpassen": (
        "STL bearbeiten: Löcher passend machen",
        "Edit an STL: make the holes fit",
    ),
    "langloch": ("STL bearbeiten: Aus Loch wird Langloch", "Edit an STL: turn a hole into a slot"),
    "stl-kanten": ("STL bearbeiten: Kanten abrunden", "Edit an STL: round the edges"),
    "stl-varianten": (
        "STL bearbeiten: Zahl ändern, Löcher folgen",
        "Edit an STL: change one number, both holes follow",
    ),
    "gegenstuecke": (
        "Zwei Teile verbinden: Stift und Loch",
        "Connect two parts: pin and matching hole",
    ),
}
lf: Any = None
LANGUAGE = "de"
MUSIC_STYLES = {
    "bohrung-anpassen": "Montagehalter aus Skizze",
    "stl-varianten": "Elektronikgehäuse",
    "langloch": "SKÅDIS-Besenhalter",
    "stl-kanten": "Montagehalter aus Skizze",
    "gegenstuecke": "Elektronikgehäuse",
}
Point = tuple[float, float, float]


def words(de: str, en: str) -> str:
    """Filmtexte stehen vollständig in beiden Sprachen neben ihrem Einsatz."""
    return en if LANGUAGE == "en" else de


def write_json(path: Path, value: Any) -> None:
    """Lesbare Belege ohne absolute Bildpfade schreiben."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def typed(value: float) -> str:
    """Eine Zahl so, wie der Kunde sie in ein Feld der Oberfläche tippt."""
    from PySide6.QtCore import QLocale

    return f"{value:g}".replace(".", QLocale().decimalPoint())


def unit(vector: Sequence[float]) -> Point:
    """Ein Vektor der Länge eins."""
    length = math.sqrt(sum(component * component for component in vector)) or 1.0
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def geometry(result: Any, context: str) -> list[dict[str, Any]]:
    """Reale Ergebnisnetze prüfen; vollständige Auswertung allein genügt nicht."""
    from app.core.geom.mesh import as_mesh_data

    errors = [str(f.message) for f in result.scene.report.findings if f.severity == "error"]
    if not result.complete or errors:
        raise RuntimeError(f"{context}: unvollständig oder Fehlerbefunde: {errors}")
    checks = []
    for object_id, body in result.scene.objects.items():
        mesh = as_mesh_data(body.mesh).raw
        components = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight or components != 1 or mesh.volume <= 0:
            raise RuntimeError(f"{context}: {object_id} ist kein einzelner geschlossener Körper.")
        checks.append(
            {
                "id": object_id,
                "watertight": bool(mesh.is_watertight),
                "components": components,
                "volume_mm3": float(mesh.volume),
                "bounds_mm": mesh.bounds.tolist(),
                "extents_mm": mesh.extents.tolist(),
                "holes": [
                    {"id": key, "kind": f.kind, "params": dict(f.params)}
                    for key, f in body.features.items()
                    if f.kind in ("hole", "slot")
                ],
            }
        )
    return checks


def make_inputs(folder: Path, story: str) -> list[Path]:
    """Eigene, rechtlich eindeutige Ausgangsdateien über die Operations-API bauen."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    load_operations()
    project = new_project()
    history = History(project.document)
    if story == "gegenstuecke":
        for x in (-20.0, 20.0):
            history.apply(
                "Verbindungsblock",
                [
                    OperationDraft(
                        op="create_box",
                        params={
                            "width": 20.0,
                            "depth": 36.0,
                            "height": 24.0,
                            "x": x,
                        },
                    )
                ],
            )
    else:
        history.apply(
            "Montageplatte",
            [
                OperationDraft(
                    op="create_box",
                    params={
                        "width": 100.0,
                        "depth": 55.0,
                        "height": 8.0,
                    },
                )
            ],
        )
        hole_positions = () if story == "stl-kanten" else (-28.0, 28.0)
        for x in hole_positions:
            history.apply(
                "Ausgangsbohrung",
                [
                    OperationDraft(
                        op="drill_hole",
                        inputs=("obj_1",),
                        params={
                            "diameter": 6.0,
                            "depth": 0.0,
                            "x": x,
                            "y": 0.0,
                            "z": 8.0,
                            "axis": "z",
                            "compensate": False,
                        },
                    )
                ],
            )
    result = evaluate(project.document, profiles.make_profile())
    checks = geometry(result, "Eigene Ausgangsdateien")
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, body in enumerate(result.scene.objects.values(), 1):
        path = folder / f"workshop-source-{index}.stl"
        as_mesh_data(body.mesh).raw.export(path)
        paths.append(path)
    write_json(
        folder / "source-evidence.json",
        {
            "author": "Robert Schneider / RS Digital",
            "origin": "registered Solidon operations",
            "source_files": [path.name for path in paths],
            "geometry": checks,
        },
    )
    return paths


class Tutorial:
    """Fachlicher Ablauf auf dem vorhandenen Recorder und den echten Widgets."""

    def __init__(
        self,
        app: Any,
        folder: Path,
        story: str,
        *,
        raw: bool = False,
        screen: Any = None,
        native_resolution: bool = False,
    ) -> None:
        self.folder, self.story = folder, story
        self.raw = raw
        self.title = words(*STORIES[story])
        self.session, self.window, self.recorder = lf._begin_video(
            app,
            self.title,
            folder / "frames",
            screen=screen,
            native_resolution=native_resolution,
        )
        self.shots: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []
        self.import_scenes: list[dict[str, Any]] = []
        self.finish_scenes: list[dict[str, Any]] = []
        self.redactions: list[dict[str, Any]] = []
        self._file_capture: dict[str, Any] = {}
        self._menu_capture: dict[str, Any] = {}
        self._pending_detail: str | None = None
        self.folder.joinpath("shots").mkdir(parents=True, exist_ok=True)
        if raw:
            # Der Schnitt bekommt unverdeckte App-Pixel. Text und Untertitel
            # entstehen später zusammen mit der gemessenen Sprecherlänge.
            self.recorder._paint_caption = lambda *args, **kwargs: None
            self.recorder.activate_windows = False

    # --- Aufnahme -------------------------------------------------------------

    def add(
        self, de: str, en: str, detail_de: str, detail_en: str, seconds: float = 8.0, **kwargs: Any
    ) -> None:
        """Lesbare zweisprachige Einblendung aufnehmen."""
        print(f"{self.recorder.seconds:6.1f}s · {words(de, en)}", flush=True)
        self.recorder.add(words(de, en), words(detail_de, detail_en), seconds, **kwargs)

    def checked(self, context: str) -> None:
        """Jeden fachlichen Schritt abwarten und an seinen realen Netzen prüfen."""
        lf._verify(self.session, context)
        self.checks.append(
            {"context": context, "geometry": geometry(self.session.last_result, context)}
        )
        write_json(self.folder / "geometry-evidence.json", self.checks)
        print(f"Geometrie geprüft: {context}", flush=True)

    def settle(self, frames: int = 12) -> None:
        """Die Ereignisschleife laufen lassen, bis die Oberfläche steht."""
        lf.video_base.settle(self.recorder.app, frames)

    def detail_shot(self, widget: Any, name: str) -> None:
        """Ein Bedienelement für die Hochformatfassung festhalten."""
        path = self.folder / "shots" / f"{name}-{len(self.checks):02d}.png"
        if not widget.grab().save(str(path)):
            raise RuntimeError(f"{name} ließ sich nicht aufnehmen.")
        self._pending_detail = path.relative_to(self.folder).as_posix()

    # --- Kamera ---------------------------------------------------------------

    def close_up(
        self,
        point: Point,
        distance: float,
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        seconds: float = 7.0,
        *,
        steep: float = 0.45,
        mirror: bool = False,
        keep_selection: bool = False,
    ) -> None:
        """Nah an ein Detail heran: Blickpunkt auf den Punkt, Abstand in Millimetern.

        Die Richtung bleibt die der aktuellen Kamera, nur etwas steiler von
        oben, damit ein Loch als Loch zu sehen ist. ``mirror`` blickt von der
        gegenüberliegenden Seite, für die zweite Hälfte einer Verbindung.
        """
        viewport = self.window.viewport
        renderer = viewport.renderer
        if not keep_selection:
            self.window.object_tree.tree.clearSelection()
            self.settle(8)
        pose = renderer.camera_pose()
        direction = unit(tuple(pose.position[axis] - pose.focal_point[axis] for axis in range(3)))
        if mirror:
            direction = (-direction[0], -direction[1], direction[2])
        direction = unit((direction[0], direction[1], direction[2] + steep))
        position = tuple(point[axis] + direction[axis] * distance for axis in range(3))
        scale = distance * 0.3 if renderer.parallel_projection() else None
        viewport.set_camera_pose(position, point, (0.0, 0.0, 1.0), parallel_scale=scale)
        viewport.settle_camera()
        renderer.render_now()
        self.settle(18)
        self.add(title_de, title_en, detail_de, detail_en, seconds)

    def turn(
        self,
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        seconds: float,
        degrees: float,
        start_degrees: float = 0.0,
    ) -> None:
        """Eine ruhige Kamerafahrt um den aktuellen Blickpunkt — ohne neu einzupassen."""
        recorder = self.recorder
        viewport = self.window.viewport
        renderer = viewport.renderer
        if not self.raw:
            self.window.raise_()
            self.window.activateWindow()
        title, detail = words(title_de, title_en), words(detail_de, detail_en)
        print(f"{recorder.seconds:6.1f}s · {title} (Kamerafahrt {degrees:g}°)", flush=True)
        recorder.events.append(
            {"start": recorder.seconds, "duration": seconds, "title": title, "detail": detail}
        )
        pose = renderer.camera_pose()
        focal, position = pose.focal_point, pose.position
        offset_x, offset_y = position[0] - focal[0], position[1] - focal[1]
        radius = math.hypot(offset_x, offset_y)
        start = math.atan2(offset_y, offset_x) + math.radians(start_degrees)
        count = max(2, round(seconds * 20.0))
        for index in range(1, count + 1):
            phase = index / count
            eased = phase * phase * (3.0 - 2.0 * phase)
            angle = start + math.radians(degrees) * eased
            renderer.set_camera_pose(
                lf.CameraPose(
                    (
                        focal[0] + radius * math.cos(angle),
                        focal[1] + radius * math.sin(angle),
                        position[2],
                    ),
                    focal,
                    pose.view_up,
                )
            )
            redraw = getattr(viewport, "_redraw_shadows", None)
            if callable(redraw):
                redraw()
            renderer.render_now()
            recorder.app.processEvents()
            recorder._store(
                recorder._capture_frame(title, detail, settle_frames=0), seconds / count
            )
        recorder._pointer = None

    def overview(
        self,
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        seconds: float = 5.0,
        degrees: float = 40.0,
        start_degrees: float = 0.0,
    ) -> None:
        """Das ganze Teil einpassen und einmal kurz drehen."""
        lf._fit(self.window, self.recorder.app)
        self.turn(title_de, title_en, detail_de, detail_en, seconds, degrees, start_degrees)

    # --- Dialoge --------------------------------------------------------------

    def modal(self, action: Any, fill: Any, *, prelude: Any = None) -> None:
        """Einen wirklichen modalen Dialog innerhalb seiner Ereignisschleife bedienen."""
        from time import monotonic

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog

        failures: list[BaseException] = []
        deadline = monotonic() + 60

        def visit() -> None:
            dialog = QApplication.activeModalWidget()
            if dialog is None and monotonic() < deadline:
                QTimer.singleShot(100, visit)
                return
            try:
                if dialog is None:
                    raise RuntimeError("Die echte Aktion hat keinen modalen Dialog geöffnet.")
                print(f"Dialog bereit: {dialog.windowTitle()}", flush=True)
                if prelude is not None and prelude(dialog):
                    QTimer.singleShot(150, visit)
                    return
                fill(dialog)
            except BaseException as error:
                failures.append(error)
                if isinstance(dialog, QDialog):
                    dialog.reject()

        QTimer.singleShot(350, visit)
        action()
        if failures:
            raise failures[0]

    def menu_action(self, action: Any) -> None:
        """Einen Menüweg mit wirklichen Mausereignissen öffnen und den Eintrag anklicken."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        path = lf._menu_path(self.window, action)
        if not path or not action.isEnabled():
            raise RuntimeError("Die gewünschte Menühandlung ist nicht erreichbar.")
        bar = self.window.menuBar()
        root = path[0][0].menuAction()
        point = bar.actionGeometry(root).center()
        first = len(self.recorder.slides)
        self.recorder.add("", "", 1.0, target=bar.mapToGlobal(point))
        action_first = len(self.recorder.slides)
        QTest.mouseMove(bar, point, 100)
        self.recorder.click("", "", target=bar.mapToGlobal(point))
        QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=point, delay=100)
        self.settle(8)
        visible = []
        for index, (menu, chosen) in enumerate(path):
            if not menu.isVisible():
                raise RuntimeError("Das tatsächliche Menü ist nicht aufgeklappt.")
            visible.append(menu)
            point = menu.actionGeometry(chosen).center()
            QTest.mouseMove(menu, point, 100)
            QTest.qWait(400)
            self.recorder.add("", "", 3.0, target=menu.mapToGlobal(point), overlays=tuple(visible))
            if index == len(path) - 1:
                self.recorder.add(
                    "",
                    "",
                    0.35,
                    target=menu.mapToGlobal(point),
                    click=True,
                    overlays=tuple(visible),
                )
                self._menu_capture = {
                    "first_slide": first,
                    "last_slide": len(self.recorder.slides),
                    "action_first_slide": action_first,
                    "action_last_slide": len(self.recorder.slides),
                }
                QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=point, delay=100)
            else:
                QTest.qWait(300)

    def file_dialog(self, action: Any, path: Path, *, save: bool = False) -> None:
        """Den durch die App geöffneten Dateidialog auswählen und bestätigen."""
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import (
            QComboBox,
            QDialogButtonBox,
            QFileDialog,
            QLineEdit,
            QListView,
        )

        from tools.workshop_inventory_capture import _click, _frame, _type

        def bounds(widget: Any) -> list[int]:
            origin = widget.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            width, height = self.recorder.frame_size
            return [
                round(origin.x() * width / self.window.width()),
                round(origin.y() * height / self.window.height()),
                round(widget.width() * width / self.window.width()),
                round(widget.height() * height / self.window.height()),
            ]

        def fill(dialog: Any) -> None:
            if not isinstance(dialog, QFileDialog):
                raise RuntimeError(f"Dateidialog erwartet, erhalten: {type(dialog).__name__}")
            dialog.setDirectory(str(path.parent))
            self.settle(12)
            filename = dialog.findChild(QLineEdit, "fileNameEdit")
            if filename is None:
                raise RuntimeError("Das Dateinamensfeld des geöffneten Dialogs fehlt.")
            first_slide = len(self.recorder.slides)
            _frame(self, dialog=dialog, seconds=3.0)
            action_first = len(self.recorder.slides)
            _type(self, filename, path.name, dialog=dialog)
            box = dialog.findChild(QDialogButtonBox)
            button = (
                box.button(
                    QDialogButtonBox.StandardButton.Save
                    if save
                    else QDialogButtonBox.StandardButton.Open
                )
                if box is not None
                else None
            )
            if button is None or not button.isEnabled():
                raise RuntimeError(
                    f"Dateiauswahl nicht bereit: {filename.text()}, "
                    f"Auswahl {dialog.selectedFiles()}, Knopf {button}."
                )
            project_file = path.suffix.lower() == ".p3d"
            image_file = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            self.add(
                "Datei speichern"
                if save
                else "Projektdatei auswählen"
                if project_file
                else "Die Bildvorlage auswählen"
                if image_file
                else "Die STL-Datei auswählen",
                "Save the file"
                if save
                else "Select the project file"
                if project_file
                else "Select the reference image"
                if image_file
                else "Select the STL file",
                "Das Projekt bewahrt alle Bearbeitungsschritte."
                if save or project_file
                else "Die Bildvorlage bleibt unverändert."
                if image_file
                else "Die STL enthält nur die Form — keine Maße, keine Schritte. "
                "Die kommen jetzt dazu.",
                "The project keeps every editing step."
                if save or project_file
                else "The reference image remains unchanged."
                if image_file
                else "The STL contains only the shape — no dimensions, no steps. Those come next.",
                8.0,
                dialog=dialog,
                target=button,
            )
            _click(self, button, dialog=dialog)
            action_last = len(self.recorder.slides)
            _frame(self, seconds=2.0)
            self._file_capture = {
                "first_slide": first_slide,
                "last_slide": len(self.recorder.slides),
                "action_first_slide": action_first,
                "action_last_slide": action_last,
                "model_crop": bounds(dialog),
                "after_model_crop": [0, 0, *self.recorder.frame_size],
            }
            boxes = [
                bounds(widget)
                for widget in (
                    dialog.findChild(QComboBox, "lookInCombo"),
                    dialog.findChild(QListView, "sidebar"),
                )
                if widget is not None
            ]
            self.redactions.append(
                {
                    **self._file_capture,
                    "last_slide": action_last,
                    "boxes": boxes,
                    "reason": "Lokalen Ordner und Benutzerbereich ausblenden; "
                    "Datei und Öffnen bleiben sichtbar.",
                }
            )

        self.modal(action, fill)

    def import_file(self, path: Path, *, unit: str | None = None) -> str:
        """Der Film benutzt den echten Dateimenüeintrag, einschließlich Dateiöffnung."""
        from time import monotonic

        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QApplication

        from app.ui.dialogs import AskDialog

        before = (
            set(self.session.last_result.scene.objects)
            if self.session.last_result is not None
            else set()
        )
        timer = QTimer()
        unit_scenes: list[dict[str, Any]] = []
        prefix = f"import-{len(self.import_scenes) + 1}"

        def scene(key: str, **values: Any) -> dict[str, Any]:
            return {
                "key": f"{prefix}-{key}",
                "action": "import",
                "short": False,
                "short_voice": "",
                "focus": None,
                **values,
            }

        def answer_units() -> None:
            dialog = QApplication.activeModalWidget()
            if not isinstance(dialog, AskDialog):
                return
            choices = [
                dialog.list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(dialog.list.count())
            ]
            if unit not in choices or set(choices) != {"mm", "cm", "in"}:
                return
            timer.stop()
            index = choices.index(unit)
            from tools.workshop_inventory_capture import _click

            button = dialog._answers[index] if dialog._answers else dialog._accept
            if not dialog._answers:
                dialog.list.setCurrentRow(index)
            unit_scenes.append(
                self.control_scene(
                    f"{prefix}-units",
                    (
                        "Die Einheit bewusst wählen",
                        "Die Quelle nennt keine feste Einheit. "
                        "Hier stehen die drei möglichen Größen. "
                        "Ich wähle Millimeter als Ausgangspunkt.",
                        "Die gewünschte Zielhöhe lege ich im nächsten Schritt selbst fest.",
                    ),
                    (
                        "Choose the unit explicitly",
                        "The source does not specify a physical unit. "
                        "These are the three possible sizes. "
                        "I choose millimetres as the starting point.",
                        "I will set the intended height myself in the next step.",
                    ),
                    action=lambda: _click(self, button, dialog=dialog),
                    dialog=dialog,
                    minimum_seconds=10,
                )
            )

        if unit is not None:
            timer.timeout.connect(answer_units)
            timer.start(150)
        try:
            self.file_dialog(lambda: self.menu_action(self.window.import_action), path)
            deadline = monotonic() + 180
            while (
                self.session.last_result is None
                or set(self.session.last_result.scene.objects) == before
                or self.session.busy
            ):
                if monotonic() > deadline:
                    raise RuntimeError(
                        "Das Modell ist noch nicht geladen; sichtbare Rückfrage prüfen."
                    )
                self.settle(5)
        finally:
            timer.stop()
        self.checked("STL-Import")
        lf._fit(self.window, self.recorder.app)
        self.import_scenes.extend(
            [
                scene(
                    "menu",
                    **self._menu_capture,
                    title=words("Das Modell einfügen", "Insert the model"),
                    detail=words("Datei → Modell einfügen", "File → Insert model"),
                    voice=words(
                        "Über Datei und Modell einfügen öffne ich die Dateiauswahl.",
                        "I open the file chooser using File and Insert model.",
                    ),
                    minimum_seconds=6,
                    model_crop=[0, 0, 900, 900],
                ),
                scene(
                    "file",
                    **self._file_capture,
                    title=words("Die vorhandene Datei wählen", "Select the existing file"),
                    detail=words(
                        "Dateinamen prüfen, dann Öffnen.", "Check the file name, then Open."
                    ),
                    voice=words(
                        "Ich wähle meine Modelldatei. Ich prüfe den Dateinamen "
                        "und klicke auf Öffnen.",
                        "I select my model file. I check the file name and click Open.",
                    ),
                    minimum_seconds=8,
                ),
                *unit_scenes,
            ]
        )
        added = set(self.session.last_result.scene.objects) - before
        if len(added) != 1:
            raise RuntimeError(f"Import sollte genau einen Körper hinzufügen: {added}")
        return str(added.pop())

    def control_scene(
        self,
        key: str,
        de: tuple[str, str, str],
        en: tuple[str, str, str],
        *,
        action: Any = None,
        dialog: Any = None,
        target: Any = None,
        minimum_seconds: float = 0,
        short: bool = False,
    ) -> dict[str, Any]:
        """Ansage, wirkliche Bedienhandlung und Ergebnis mit ihren Rohbildgrenzen erfassen."""
        from PySide6.QtCore import QPoint
        from shiboken6 import isValid

        first = len(self.recorder.slides)
        self.recorder.add(
            "", "", 2.0 if action else max(2.0, minimum_seconds), dialog=dialog, target=target
        )
        crop = [0, 0, *self.recorder.frame_size]
        target_bounds = None
        if target is not None and hasattr(target, "rect"):
            point = target.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            target_bounds = [point.x(), point.y(), target.width(), target.height()]
        if dialog is not None:
            point = dialog.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            crop = [point.x(), point.y(), dialog.width(), dialog.height()]
        action_first = len(self.recorder.slides)
        if action is not None:
            action()
        action_last = len(self.recorder.slides)
        visible = dialog is not None and isValid(dialog) and dialog.isVisible()
        if action is not None:
            self.recorder.add("", "", 3.0, dialog=dialog if visible else None)
        after_crop = [0, 0, *self.recorder.frame_size]
        after_target_bounds = None
        if visible:
            point = dialog.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            after_crop = [point.x(), point.y(), dialog.width(), dialog.height()]
        if target is not None and isValid(target) and hasattr(target, "rect"):
            point = target.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            after_target_bounds = [point.x(), point.y(), target.width(), target.height()]
        title, before, after = en if LANGUAGE == "en" else de
        return {
            "key": key,
            "title": title,
            "voice": " ".join(value for value in (before, after) if value),
            "voice_before": before,
            "voice_after": after,
            "short_voice_before": before if short else "",
            "short_voice_after": after if short else "",
            "short": short,
            "first_slide": first,
            "last_slide": len(self.recorder.slides),
            "action_first_slide": action_first,
            "action_last_slide": action_last,
            "model_crop": crop,
            "after_model_crop": after_crop,
            "focus": None,
            "target_bounds": target_bounds,
            "after_target_bounds": after_target_bounds,
            "minimum_seconds": minimum_seconds,
            "minimum_after_action_seconds": 2.0,
        }

    def print_settings(self, step: dict[str, Any]) -> list[dict[str, Any]]:
        """Den Druckdialog über den echten Einstieg bedienen und seine Vorschläge belegen."""
        from dataclasses import asdict
        from time import monotonic

        from PySide6.QtWidgets import QDialogButtonBox

        from app.ui.print_disclosure import PrintDisclosureDialog
        from app.ui.print_settings_dialog import PrintSettingsDialog
        from tools.workshop_inventory_capture import _choose, _click, _frame, _type

        titles = (step["de"]["title"], step["en"]["title"])
        scenes: list[dict[str, Any]] = []
        snapshots: list[dict[str, Any]] = []
        entry_end: int | None = None

        def note(
            key: str, de: tuple[str, str, str], en: tuple[str, str, str], **kwargs: Any
        ) -> None:
            scenes.append(self.control_scene(f"{step['key']}-{key}", de, en, **kwargs))

        def opened(dialog: Any) -> None:
            nonlocal entry_end
            if entry_end is None:
                _frame(self, dialog=dialog, seconds=1.5)
                entry_end = len(self.recorder.slides)

        def ready(dialog: Any) -> None:
            deadline = monotonic() + 120
            while (
                self.session.busy
                or dialog._advice_pending
                or dialog._profiles_pending
                or dialog._slicers_pending
            ):
                if monotonic() > deadline:
                    raise RuntimeError("Druckvorschläge werden nicht fertig; Aufnahme anhalten.")
                self.settle(5)

        def snapshot(dialog: Any, stage: str) -> None:
            snapshots.append(
                {
                    "stage": stage,
                    "slide": len(self.recorder.slides) - 1,
                    "printer": self.session.profile.printer.id,
                    "slicer": str(dialog._slicer_path),
                    "machine": dialog.machine_choice.currentText(),
                    "process": dialog.process_choice.currentText(),
                    "foundation": dialog.foundation_note.text(),
                    "state": dialog.state.text(),
                    "advice": [asdict(entry) for entry in dialog._advice_entries],
                    "settings": asdict(dialog.settings),
                }
            )

        def fill(dialog: Any) -> None:
            if not isinstance(dialog, PrintSettingsDialog):
                raise RuntimeError("Der Druckdialog ist nicht offen; vorherige Meldung prüfen.")
            dialog.setMinimumWidth(1000)
            opened(dialog)
            note(
                "overview",
                (
                    "Die Druckeinstellungen",
                    "Hier stehen das gewählte Druckerprofil und die Druckwerte.",
                    "",
                ),
                (
                    "Print settings",
                    "This is where I check the selected printer profile and print settings.",
                    "",
                ),
                dialog=dialog,
                minimum_seconds=10,
            )
            if step.get("printer"):
                choice = dialog.printer_choice
                index = choice.findData(step["printer"])
                if index < 0:
                    raise RuntimeError(f"Druckerprofil fehlt: {step['printer']}")
                note(
                    "printer",
                    (
                        titles[0],
                        step["de"].get("voice_before", step["de"]["voice"]),
                        "Die gewählte Druckerkennung steht jetzt im Projekt.",
                    ),
                    (
                        titles[1],
                        step["en"].get("voice_before", step["en"]["voice"]),
                        "The selected printer is now stored in the project.",
                    ),
                    dialog=dialog,
                    target=choice,
                    action=lambda: _choose(self, choice, step["printer"], dialog=dialog),
                    short=bool(step.get("short")),
                )
                if choice.currentData() != step["printer"]:
                    raise RuntimeError("Die sichtbare Druckerwahl hat das Profil nicht übernommen.")
            ready(dialog)
            if step.get("slicer_match"):
                picker = dialog.slicer_choice
                needle = str(step["slicer_match"]).casefold()
                matches = [
                    index
                    for index in range(picker.count())
                    if needle in picker.itemText(index).casefold()
                ]
                if len(matches) != 1 or not picker.isVisible():
                    raise RuntimeError("Die gewünschte Slicerauswahl ist nicht eindeutig sichtbar.")
                chosen_slicer = picker.itemData(matches[0])
                note(
                    "slicer",
                    (
                        "Den Slicer wählen",
                        "Im Feld Slicer wähle ich ElegooSlicer.",
                        "",
                    ),
                    ("Choose the slicer", "In the Slicer field, select ElegooSlicer.", ""),
                    dialog=dialog,
                    target=picker,
                    action=lambda: _choose(self, picker, chosen_slicer, dialog=dialog),
                )
                ready(dialog)
            if step.get("manufacturer_machine_match"):
                if dialog.slicer_toggle is None:
                    raise RuntimeError("Der Abschnitt für Slicerprofile fehlt.")
                note(
                    "profiles-open",
                    ("Die Slicerprofile öffnen", "Ich öffne Profile des Slicers.", ""),
                    ("Open the slicer profiles", "Open Slicer profiles.", ""),
                    dialog=dialog,
                    target=dialog.slicer_toggle,
                    action=lambda: (
                        _click(self, dialog.slicer_toggle, dialog=dialog)
                        if not dialog.slicer_toggle.isChecked()
                        else None
                    ),
                )
                ready(dialog)
                needle = str(step["manufacturer_machine_match"]).casefold()
                picker = dialog.machine_choice
                matches = [
                    index
                    for index in range(picker.count())
                    if needle in picker.itemText(index).casefold()
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        f"Das Herstellerprofil ist nicht eindeutig vorhanden: "
                        f"{[picker.itemText(index) for index in range(picker.count())]}"
                    )
                chosen = picker.itemData(matches[0])
                note(
                    "manufacturer",
                    (
                        "Das Herstellerprofil wählen",
                        "Unter Profile des Slicers wähle ich meinen Drucker.",
                        "",
                    ),
                    (
                        "Choose the manufacturer profile",
                        "Under Slicer profiles, select the printer model.",
                        "",
                    ),
                    dialog=dialog,
                    target=picker,
                    action=lambda: _choose(self, picker, chosen, dialog=dialog),
                )
                ready(dialog)
                note(
                    "profile-baseline",
                    (
                        "Die tatsächliche Grundlage",
                        "Darunter stehen das zugehörige Grundprofil und die Filamentvorgabe.",
                        "",
                    ),
                    (
                        "The actual baseline",
                        "The process profile and filament default appear underneath.",
                        "",
                    ),
                    dialog=dialog,
                    target=dialog.slicer_inner,
                    minimum_seconds=8,
                )
                note(
                    "profiles-close",
                    ("Zurück zu den Druckwerten", "Ich klappe den Profilabschnitt wieder zu.", ""),
                    ("Return to the print values", "I collapse the profile section again.", ""),
                    dialog=dialog,
                    target=dialog.slicer_toggle,
                    action=lambda: _click(self, dialog.slicer_toggle, dialog=dialog),
                )
            snapshot(dialog, "baseline")
            for path, value in step.get("values", {}).items():
                editor = dialog._editors[path]
                spin = getattr(editor, "spin", editor)
                if not spin.isVisible():
                    raise RuntimeError(f"Das Druckfeld ist nicht sichtbar: {path}")
                note(
                    "value-" + path.replace(".", "-"),
                    (titles[0], step["de"]["voice"], "Der eigene Wert ist markiert."),
                    (titles[1], step["en"]["voice"], "The custom value is marked."),
                    dialog=dialog,
                    target=spin,
                    action=lambda spin=spin, value=value: _type(
                        self, spin, typed(float(value)), dialog=dialog
                    ),
                )
                snapshot(dialog, "custom-" + path)
            if step.get("reset"):
                reset = dialog._resets[step["reset"]]
                if not reset.isVisible() or not reset.isEnabled():
                    raise RuntimeError("Der eigene Druckwert lässt sich nicht zurücksetzen.")
                note(
                    "reset",
                    (
                        "Zur Profilvorgabe zurück",
                        "Ich setze den eigenen Wert auf die Vorgabe zurück.",
                        "",
                    ),
                    (
                        "Return to the profile value",
                        "I reset the custom value to the profile default.",
                        "",
                    ),
                    dialog=dialog,
                    target=reset,
                    action=lambda: _click(self, reset, dialog=dialog),
                )
                snapshot(dialog, "reset-" + step["reset"])
            if step.get("advice") or step.get("apply_advice"):
                if dialog.advice_toggle is None:
                    raise RuntimeError("Die Druckvorschläge sind in diesem Dialog nicht verfügbar.")
                note(
                    "advice-open",
                    (
                        "Druckvorschläge einblenden",
                        "Ich öffne die Vorschläge für dieses Modell.",
                        "",
                    ),
                    ("Show print suggestions", "I open the suggestions for this model.", ""),
                    dialog=dialog,
                    target=dialog.advice_toggle,
                    action=lambda: (
                        _click(self, dialog.advice_toggle, dialog=dialog)
                        if not dialog.advice_toggle.isChecked()
                        else None
                    ),
                )
                ready(dialog)
                snapshot(dialog, "before-advice")
                note(
                    "advice-results",
                    (
                        "Vorschlag und Grund zusammen lesen",
                        "Ich lese den vorgeschlagenen Wert und den Grund daneben. "
                        "Die Vorschläge gehören zu genau diesem Modell.",
                        "",
                    ),
                    (
                        "Read each suggestion with its reason",
                        "Read the suggested value and the reason beside it. "
                        "These suggestions are for this specific model.",
                        "",
                    ),
                    dialog=dialog,
                    target=dialog.advice_view,
                    minimum_seconds=12,
                )
                from PySide6.QtCore import QPoint, Qt

                for explanation in step.get("advice_explanations", []):
                    view = dialog.advice_view
                    matching_rows = [
                        item
                        for index in range(view.topLevelItemCount())
                        if (item := view.topLevelItem(index)) is not None
                        and item.data(0, Qt.ItemDataRole.UserRole) == explanation["path"]
                    ]
                    if len(matching_rows) != 1:
                        raise RuntimeError(
                            "Der erklärte Druckvorschlag ist nicht sichtbar vorhanden."
                        )
                    row = view.visualItemRect(matching_rows[0])
                    origin = view.viewport().mapToGlobal(row.topLeft())
                    origin -= self.window.mapToGlobal(QPoint(0, 0))
                    note(
                        "reason-" + explanation["path"].replace(".", "-"),
                        (explanation["de"]["title"], explanation["de"]["voice"], ""),
                        (explanation["en"]["title"], explanation["en"]["voice"], ""),
                        dialog=dialog,
                        minimum_seconds=6,
                    )
                    scenes[-1]["row_bounds"] = [origin.x(), origin.y(), row.width(), row.height()]
            self.settle(15)
            note(
                "review",
                (
                    "Die tatsächlichen Werte prüfen",
                    "Ich prüfe die angezeigten Werte vor dem nächsten Schritt.",
                    "",
                ),
                ("Check the actual values", "I check the displayed values before continuing.", ""),
                dialog=dialog,
                minimum_seconds=12,
            )
            if step.get("apply_advice"):
                if not dialog._advice_entries or not dialog.apply_button.isEnabled():
                    raise RuntimeError("Keine anwendbaren Druckvorschläge; Geschichte anpassen.")
                note(
                    "apply-advice",
                    (
                        "Vorschläge bewusst übernehmen",
                        "Mit Vorschläge übernehmen wende ich die gezeigten Änderungen an.",
                        "",
                    ),
                    (
                        "Apply the suggestions deliberately",
                        "I click Apply suggestions to use the displayed changes.",
                        "",
                    ),
                    dialog=dialog,
                    target=dialog.apply_button,
                    action=lambda: _click(self, dialog.apply_button, dialog=dialog),
                    short=True,
                )
                ready(dialog)
                snapshot(dialog, "after-advice")
                note(
                    "applied-results",
                    (
                        "Die übernommenen Vorschläge kontrollieren",
                        "Die Werte sind übernommen. Die erneute Prüfung zeigt, "
                        "ob noch Vorschläge offen sind.",
                        "",
                    ),
                    (
                        "Check the applied suggestions",
                        "The values are applied. The new check shows "
                        "whether any suggestions remain.",
                        "",
                    ),
                    dialog=dialog,
                    target=dialog.advice_view,
                    minimum_seconds=6,
                )
            proof = {
                "printer": self.session.profile.printer.id,
                "foundation": dialog.foundation_note.text(),
                "state": dialog.state.text(),
                "advice": [asdict(entry) for entry in dialog._advice_entries],
                "settings": asdict(dialog.settings),
                "snapshots": snapshots,
            }
            (self.folder / f"print-{step['key']}.json").write_text(
                json.dumps(proof, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            box = dialog.findChild(QDialogButtonBox)
            close = box.button(QDialogButtonBox.StandardButton.Close) if box else None
            if close is None:
                raise RuntimeError("Schließen fehlt im Druckdialog.")
            note(
                "close",
                (
                    "Zum Modell zurückkehren",
                    "Ich schließe die Druckeinstellungen und kontrolliere das Modell.",
                    "",
                ),
                ("Return to the model", "I close the print settings and check the model.", ""),
                dialog=dialog,
                target=close,
                action=lambda: _click(self, close, dialog=dialog),
            )

        def prelude(dialog: Any) -> bool:
            if not isinstance(dialog, PrintDisclosureDialog):
                return False
            from PySide6.QtWidgets import QLabel

            dialog.setMinimumWidth(900)
            self.settle(12)
            opened(dialog)
            reading_seconds = max(
                12, sum(len(label.text().split()) for label in dialog.findChildren(QLabel)) / 3
            )
            note(
                "notice",
                (
                    "Druckeinstellungen und Verantwortung",
                    "Dieser Hinweis erklärt, wie die Druckwerte entstehen und wann sie in "
                    "Dateien mitgegeben werden. Ich lese ihn, bevor ich weitergehe.",
                    "",
                ),
                (
                    "Print settings and responsibility",
                    "This notice explains how the print settings are calculated and when "
                    "they are included in files. I read it before continuing.",
                    "",
                ),
                dialog=dialog,
                minimum_seconds=reading_seconds,
            )
            share = bool(step.get("share", False))
            change_share = dialog.share.isChecked() != share
            if change_share:
                choice_de = (
                    "Ich setze den Haken, damit die Werte beim Speichern und Übergeben mitreisen."
                    if share
                    else (
                        "Die Werte sollen hier nicht mitgegeben werden. Ich nehme den Haken heraus."
                    )
                )
                choice_en = (
                    "I check this to include the values when saving or handing over the project."
                    if share
                    else "I do not include the values here, so I clear the checkbox."
                )
            else:
                choice_de = (
                    "Ich lasse den Haken gesetzt. Die Werte werden beim Speichern mitgegeben."
                    if share
                    else "Ich lasse die Übergabe der Werte hier ausgeschaltet."
                )
                choice_en = (
                    "I leave this checked. The values are included when saving."
                    if share
                    else "I leave the option to include these values switched off."
                )
            note(
                "share",
                (
                    "Werte mitgeben bewusst wählen",
                    choice_de,
                    "Die Einstellung kann ich später im Druckdialog wieder ändern.",
                ),
                (
                    "Choose whether to include settings",
                    choice_en,
                    "I can change this later in the print settings.",
                ),
                dialog=dialog,
                target=dialog.share,
                action=(lambda: _click(self, dialog.share, dialog=dialog))
                if change_share
                else None,
            )
            if dialog.share.isChecked() != share:
                raise RuntimeError("Die gezeigte Übergabeoption stimmt nicht mit der Wahl überein.")
            box = dialog.findChild(QDialogButtonBox)
            if box is None:
                raise RuntimeError("Der Druckhinweis hat keine Schaltflächen.")
            accept = box.button(QDialogButtonBox.StandardButton.Ok)
            if accept is None:
                raise RuntimeError("Verstanden fehlt im Druckhinweis.")
            note(
                "notice-accept",
                ("Den Hinweis bestätigen", "Mit Verstanden öffne ich die Druckeinstellungen.", ""),
                (
                    "Acknowledge the notice",
                    "I acknowledge the notice to open the print settings.",
                    "",
                ),
                dialog=dialog,
                target=accept,
                action=lambda: _click(self, accept, dialog=dialog),
            )
            return True

        if self.window.settings.right_panel_visible:
            self.window.action_toggle_right()
        first = len(self.recorder.slides)
        self.recorder.add("", "", 3.0, target=self.window.header.printer_button)
        action_first = len(self.recorder.slides)
        self.modal(lambda: _click(self, self.window.header.printer_button), fill, prelude=prelude)
        if entry_end is None:
            raise RuntimeError("Der Druckdialog wurde nicht sichtbar aufgenommen.")
        scenes.insert(
            0,
            {
                "key": f"{step['key']}-entry",
                "title": words("Druckeinstellungen öffnen", "Open print settings"),
                "voice_before": words(
                    "Oben rechts öffne ich Drucker.", "I open Printer at the top right."
                ),
                "voice_after": "",
                "first_slide": first,
                "last_slide": entry_end,
                "action_first_slide": action_first,
                "action_last_slide": entry_end - 1,
                "model_crop": [1600, 0, 960, 600],
                "after_model_crop": [0, 0, *self.recorder.frame_size],
                "focus": None,
                "short": False,
            },
        )
        self.checked(titles[0])
        return scenes

    def first_steps(self, setup: dict[str, Any]) -> list[dict[str, Any]]:
        """Die wirkliche Ersteinrichtung mit fertiger Programmsuche und bewusster Wahl zeigen."""
        from time import monotonic

        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QDialogButtonBox

        from app.i18n import tr
        from app.ui.first_run import FirstRunDialog
        from tools.workshop_inventory_capture import _choose, _click, _frame

        scenes: list[dict[str, Any]] = []

        def record(
            dialog: Any,
            key: str,
            *,
            target: Any = None,
            action: Any = None,
            first_slide: int | None = None,
        ) -> None:
            stage = setup[key]
            start = len(self.recorder.slides) if first_slide is None else first_slide
            event_start = len(self.recorder.events)
            self.add(
                stage["de"]["title"],
                stage["en"]["title"],
                stage["de"]["detail"],
                stage["en"]["detail"],
                4.0 if action else float(stage.get("minimum_seconds", 12)),
                dialog=dialog,
                target=target,
            )
            action_first = len(self.recorder.slides)
            if action is not None:
                action()
            action_last = len(self.recorder.slides)
            if action is not None:
                self.recorder.add("", "", 6.0, dialog=dialog if dialog.isVisible() else None)
            region = dialog
            if stage.get("view") == "basics":
                region = dialog.printer.parentWidget()
            elif stage.get("view") == "footer":
                region = target.parentWidget()
            elif stage.get("view") == "extensions":
                region = dialog.tools.parentWidget()
            origin = region.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            scale_x = self.recorder.frame_size[0] / self.window.width()
            scale_y = self.recorder.frame_size[1] / self.window.height()
            crop = [
                max(0, round(origin.x() * scale_x)),
                max(0, round(origin.y() * scale_y)),
                round(region.width() * scale_x),
                round(region.height() * scale_y),
            ]
            scenes.append(
                {
                    "key": "setup-" + key,
                    **stage[LANGUAGE],
                    "action": "first_steps",
                    "first_slide": start,
                    "last_slide": len(self.recorder.slides),
                    "action_first_slide": action_first,
                    "action_last_slide": action_last,
                    "events": self.recorder.events[event_start:],
                    "short": False,
                    "minimum_seconds": stage.get("minimum_seconds", 12),
                    "model_crop": crop,
                    "after_model_crop": crop
                    if dialog.isVisible()
                    else [0, 0, *self.recorder.frame_size],
                    "focus": None,
                }
            )

        def wait(dialog: Any, *, record_wait: bool = False) -> None:
            deadline = monotonic() + 120
            while any(
                worker is not None and worker.isRunning()
                for worker in (dialog._survey, dialog._printer_survey)
            ):
                if monotonic() > deadline:
                    raise RuntimeError(
                        "Die Ersteinrichtung wartet noch auf Programme; Aufnahme anhalten."
                    )
                self.settle(5)
                if record_wait:
                    _frame(self, dialog=dialog, seconds=0.25)
            self.settle(15)
            dialog._grow_to_content()
            self.settle(8)

        def fill(dialog: Any) -> None:
            if not isinstance(dialog, FirstRunDialog):
                raise RuntimeError("Die echte Ersteinrichtung ist nicht geöffnet.")
            dialog.setMinimumWidth(960)
            overview_first = len(self.recorder.slides)
            _frame(self, dialog=dialog, seconds=1.0)
            wait(dialog, record_wait=True)
            if len(self.recorder.slides):
                scenes.append(
                    {
                        "key": "setup-menu",
                        "action": "first_steps",
                        "short": False,
                        "title": words("Erste Schritte öffnen", "Open First steps"),
                        "detail": words("Hilfe → Erste Schritte", "Help → First steps"),
                        "voice": words(
                            "Unter Hilfe öffne ich Erste Schritte.",
                            "I open First steps from the Help menu.",
                        ),
                        **self._menu_capture,
                        "minimum_seconds": 6,
                        "focus": None,
                        "model_crop": [0, 0, 900, 900],
                    }
                )
            record(dialog, "overview", first_slide=overview_first)
            wanted = str(setup["slicer_contains"]).casefold()
            index = next(
                (
                    i
                    for i in range(dialog.slicer.count())
                    if wanted in str(dialog.slicer.itemData(i)).casefold()
                ),
                -1,
            )
            if index < 0:
                raise RuntimeError(
                    "Der benannte installierte Slicer fehlt; Ersteinrichtung prüfen."
                )
            wanted_slicer = dialog.slicer.itemData(index)

            def choose_slicer() -> None:
                _choose(self, dialog.slicer, wanted_slicer, dialog=dialog)
                wait(dialog)

            record(dialog, "slicer", target=dialog.slicer, action=choose_slicer)
            index = dialog.printer.findData(setup["printer_id"])
            if index < 0:
                write_json(
                    self.folder / "first-steps-missing-printer.json",
                    {
                        "slicer": dialog.slicer.currentData(),
                        "printers": [
                            (dialog.printer.itemText(i), dialog.printer.itemData(i))
                            for i in range(dialog.printer.count())
                        ],
                        "state": dialog.printer_state.text(),
                    },
                )
                raise RuntimeError("Das gewünschte Druckerprofil fehlt in der Ersteinrichtung.")

            def choose_printer() -> None:
                _choose(self, dialog.printer, setup["printer_id"], dialog=dialog)
                wait(dialog)

            record(dialog, "printer", target=dialog.printer, action=choose_printer)
            if "extensions" in setup:
                record(dialog, "extensions", target=dialog.chat_button)
            box = dialog.findChild(QDialogButtonBox)
            if box is None:
                raise RuntimeError("Der Einrichtungsdialog hat keine Schaltflächen.")
            button = next(
                (
                    button
                    for button in box.buttons()
                    if box.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole
                ),
                None,
            )
            if button is None:
                raise RuntimeError("Speichern und starten fehlt in der Ersteinrichtung.")
            write_json(
                self.folder / "first-steps-evidence.json",
                {
                    "language": dialog.language.currentData(),
                    "slicer": dialog.slicer.currentData(),
                    "printer": dialog.printer.currentData(),
                    "program_survey_complete": True,
                },
            )
            record(
                dialog, "save", target=button, action=lambda: _click(self, button, dialog=dialog)
            )

        action = next(
            (
                action
                for menu in self.window._menus
                for action in menu.actions()
                if action.text().replace("&", "") == tr("Erste Schritte …")
            ),
            None,
        )
        if action is None:
            raise RuntimeError("Der echte Menüeintrag Erste Schritte fehlt.")
        self.modal(lambda: self.menu_action(action), fill)
        if self.session.profile.printer.id != setup["printer_id"]:
            raise RuntimeError(
                "Der Projekt-Drucker entspricht nicht der gezeigten Ersteinrichtung."
            )
        return scenes

    def toggle_step(
        self, op_id: int, titles: tuple[str, str], details: tuple[str, str]
    ) -> dict[str, int]:
        """Den gewählten Verlaufsschritt mit dem angebotenen Tastaturweg schalten."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from tools.workshop_inventory_capture import _frame

        history = self.window.history_panel
        item = next(
            (
                history.list.item(row)
                for row in range(history.list.count())
                if history.list.item(row).data(Qt.ItemDataRole.UserRole) == op_id
            ),
            None,
        )
        if item is None:
            raise RuntimeError("Der zu schaltende Verlaufsschritt fehlt.")
        history.list.scrollToItem(item)
        self.settle(10)
        self.add(*titles, *details, 2.0, target=history.list)
        action_first = len(self.recorder.slides)
        point = history.list.visualItemRect(item).center()
        self.recorder.click("", "", target=history.list.viewport().mapToGlobal(point))
        QTest.mouseClick(history.list.viewport(), Qt.MouseButton.LeftButton, pos=point, delay=100)
        self.settle(8)
        _frame(self, seconds=0.8)
        QTest.keyClick(history.list, Qt.Key.Key_Space)
        self.checked(titles[0])
        _frame(self, seconds=1.0)
        action_last = len(self.recorder.slides)
        self.add(*titles, *details, 3.0, target=history.list)
        return {"action_first_slide": action_first, "action_last_slide": action_last}

    def parameter(
        self,
        name: str,
        value: float,
        title_de: str,
        title_en: str,
        minimum: float = 1.0,
        maximum: float = 100.0,
    ) -> None:
        """Der Parameterknopf öffnet den echten Parameterdialog der Anwendung."""
        lf._fit(self.window, self.recorder.app)
        self.add(
            "Ein Maß mit Namen anlegen",
            "Create a named dimension",
            "Links unter „Parameter“: Ein Maß, das später mehrere Stellen steuert.",
            "On the left under “Parameters”: one dimension that later drives several places.",
            6.0,
            target=self.window.parameters.add_button,
        )

        def fill(dialog: Any) -> None:
            dialog.name_field.setText(name)
            dialog.value_field.setValue(value)
            dialog.minimum_field.setText(f"{minimum:g}")
            dialog.maximum_field.setText(f"{maximum:g}")
            self.add(
                title_de,
                title_en,
                f"{name} = {value:g} mm. Der Name lässt sich überall mit @{name} verwenden.",
                f"{name} = {value:g} mm. Use the name anywhere as @{name}.",
                9.0,
                dialog=dialog,
                target=dialog.value_field,
            )
            lf._button(dialog).click()

        self.modal(self.window.parameters.add_button.click, fill)
        self.checked(f"Parameter {name}")

    def change_parameter(self, name: str, value: float, title_de: str, title_en: str) -> None:
        """Ein reales Seitenfeld ändern und die tatsächliche Neuauswertung abwarten."""
        lf._fit(self.window, self.recorder.app)
        field = self.window.parameters._editors[name]
        self.add(
            title_de,
            title_en,
            f"Links im Feld: {name} wird {value:g} mm. Alles, was den Namen benutzt, folgt.",
            f"In the field on the left: {name} becomes {value:g} mm. "
            "Everything using the name follows.",
            8.0,
            target=field,
        )
        field.setValue(value)
        self.settle(12)
        self.checked(f"Variante {name}={value}")
        self.detail_shot(self.window.parameters, "parameter")

    def select_feature(
        self, body: str, feature: str, title_de: str, title_en: str
    ) -> dict[str, int]:
        """Den Baum wirklich aufklappen und die sichtbare Merkmalszeile anklicken."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from app.ui.panels import _feature_item
        from tools.workshop_inventory_capture import _frame

        # Nach einer Nahaufnahme erst wieder das ganze Teil zeigen — der Klick gilt dem Überblick.
        lf._fit(self.window, self.recorder.app)
        tree = self.window.object_tree.tree
        parent = next(
            (
                tree.topLevelItem(index)
                for index in range(tree.topLevelItemCount())
                if tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole) == body
            ),
            None,
        )
        item = _feature_item(parent, feature) if parent is not None else None
        if item is None:
            raise RuntimeError("Das Merkmal fehlt im Objektbaum; Aufnahme anhalten.")
        self.recorder.add("", "", 2.0)
        first = len(self.recorder.slides)

        def click_item(target: Any) -> None:
            tree.scrollToItem(target)
            self.settle(8)
            point = tree.visualItemRect(target).center()
            self.recorder.click("", "", target=tree.viewport().mapToGlobal(point))
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point, delay=100)
            self.settle(8)
            _frame(self, seconds=0.8)

        ancestors = []
        ancestor = item.parent()
        while ancestor is not None:
            ancestors.append(ancestor)
            ancestor = ancestor.parent()
        for ancestor in reversed(ancestors):
            if not ancestor.isExpanded():
                click_item(ancestor)
                QTest.keyClick(tree, Qt.Key.Key_Right)
                self.settle(8)
                _frame(self, seconds=0.8)
        click_item(item)
        last = len(self.recorder.slides)
        if self.window.object_tree.selected_features() != ((body, feature),):
            raise RuntimeError("Der echte Baumklick hat nicht das geplante Merkmal gewählt.")
        self.add(
            title_de,
            title_en,
            "Im Objektbaum links oder direkt im Bild anklicken. Rechts stehen die Maße dazu.",
            "Click it in the object tree on the left or directly in the view. "
            "Its dimensions appear on the right.",
            8.0,
            target=self.window.feature_panel,
        )
        return {"action_first_slide": first, "action_last_slide": last}

    # --- Die Kundenwege -----------------------------------------------------------

    def drag_slot(self, step: dict[str, Any], body: str) -> list[dict[str, Any]]:
        """Den sichtbaren L-Griff mit echten Qt-Mausereignissen ziehen und übernehmen."""
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication, QToolTip

        from tools.workshop_inventory_capture import _click, _type

        titles = (step["de"]["title"], step["en"]["title"])
        details = (step["de"]["detail"], step["en"]["detail"])
        if self.window.object_tree.selected_features() != ((body, step["feature"]),):
            self.select_feature(body, step["feature"], *titles)
        if self.window.settings.right_panel_visible:
            self.window.action_toggle_right()
        if self.window.settings.bed_visible:
            self.window.action_toggle_bed()
        self.window.action_shading("flat")
        scenes: list[dict[str, Any]] = []
        viewport = self.window.viewport
        renderer = viewport.renderer
        feature = self.session.last_result.scene.objects[body].features[step["feature"]]
        centre = tuple(float(value) for value in feature.params["centre"])
        if step.get("camera"):
            camera = step["camera"]
            viewport.set_camera_pose(
                tuple(camera["position"]),
                tuple(camera["focal"]),
                tuple(camera["up"]),
                parallel_scale=camera.get("scale"),
            )
            viewport.settle_camera()
        self.settle(20)
        renderer.render_now()
        QToolTip.hideText()
        handle = viewport._slot_handle
        if handle is None:
            raise RuntimeError("Der Langlochgriff fehlt; die sichtbare Auswahl prüfen.")
        index = int(step.get("knob", 0))
        seat = handle.knob_seats[index]
        start = renderer.world_to_display(seat)
        # Die eigene Darstellung wird wirklich getroffen; keine Attrappe für die Auswahl.
        if renderer.pick_item(round(start[0]), round(start[1])) is not handle.knobs[index]:
            raise RuntimeError("Der sichtbare Langlochgriff ist verdeckt; Kamera korrigieren.")
        length = float(step["length"])
        mouth, _ = handle.clearance
        target = tuple(
            mouth[axis] + (seat[axis] - mouth[axis]) * length / handle.length for axis in range(3)
        )
        finish = renderer.world_to_display(target)
        widget = renderer.widget
        ratio = renderer.device_ratio()
        start_pos = QPointF(start[0] / ratio, start[1] / ratio)
        end_pos = QPointF(finish[0] / ratio, finish[1] / ratio)
        first = len(self.recorder.slides)
        self.add(*titles, *details, 4.0, target=widget.mapToGlobal(start_pos.toPoint()))
        action_first = len(self.recorder.slides)
        before = len(self.session.project.document.ops)

        def mouse(kind: Any, point: QPointF, button: Any, buttons: Any) -> None:
            event = QMouseEvent(
                kind,
                point,
                QPointF(widget.mapToGlobal(point.toPoint())),
                button,
                buttons,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(widget, event)
            self.recorder.app.processEvents()

        mouse(QEvent.Type.MouseMove, start_pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton)
        mouse(
            QEvent.Type.MouseButtonPress,
            start_pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
        self.recorder.events.append(
            {
                "start": self.recorder.seconds,
                "duration": 2.4,
                "title": words(*titles),
                "detail": words(*details),
            }
        )
        for index in range(1, 31):
            phase = index / 30
            point = start_pos + (end_pos - start_pos) * phase
            mouse(QEvent.Type.MouseMove, point, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
            renderer.render_now()
            frame = self.recorder._capture_frame(words(*titles), words(*details), settle_frames=0)
            pointer = self.recorder._point_for(widget.mapToGlobal(point.toPoint()))
            lf.video_base._paint_pointer(frame, (float(pointer.x()), float(pointer.y()), True))
            self.recorder._store(frame, 0.08)
        mouse(
            QEvent.Type.MouseButtonRelease,
            end_pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
        self.settle(20)
        action_last = len(self.recorder.slides)
        if not viewport.slot_drag_waits() or len(self.session.project.document.ops) != before:
            raise RuntimeError(
                "Der Griffzug hat keinen wartenden Entwurf erzeugt; Aufnahme prüfen."
            )
        self.add(*titles, *details, 7.0)
        flow = self.window._quiet_placement
        if flow is None or flow.spec_of().name != "slot_hole":
            raise RuntimeError("Der Langlochzug hat keine passenden Maßfelder geöffnet.")
        origin = flow._measure_box.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
        focus = [
            origin.x() - 7,
            origin.y() - 7,
            flow._measure_box.width() + 14,
            flow._measure_box.height() + 14,
        ]
        crop = [500, 120, 1700, 1160]

        def row_focus(control: Any) -> list[int]:
            point = control.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
            return [focus[0], point.y() - 12, focus[2], control.height() + 24]

        def scene(
            key: str,
            begin: int,
            action_begin: int,
            action_end: int,
            *,
            applied: bool = False,
            close_focus: list[int] | None = None,
        ) -> None:
            text = step["stages"][key][LANGUAGE]
            scenes.append(
                {
                    "key": f"{step['key']}-{key}",
                    **text,
                    "action": "drag_slot",
                    "first_slide": begin,
                    "last_slide": len(self.recorder.slides),
                    "action_first_slide": action_begin,
                    "action_last_slide": action_end,
                    "short": bool(step.get("short")),
                    "model_crop": crop,
                    "focus": None if key == "drag" else focus,
                    "after_focus": None if applied else focus,
                    "minimum_after_action_seconds": 2,
                }
            )
            if close_focus is not None:
                scenes[-1].update(
                    short_before_focus=close_focus,
                    short_action_focus=close_focus,
                    short_after_focus=None if applied else close_focus,
                )

        scene("drag", first, action_first, action_last)
        write_json(
            self.folder / f"gesture-{step['key']}.json",
            {
                "input": "Qt-Mausereignisse auf dem nativen Render-Widget",
                "feature": step["feature"],
                "original_centre": centre,
                "requested_length": length,
                "start_pixel": [start_pos.x(), start_pos.y()],
                "end_pixel": [end_pos.x(), end_pos.y()],
                "preview": viewport.waiting_slot_drag(step["feature"]),
                "document_unchanged_until_accept": True,
            },
        )
        group = self.window.feature_panel._measure_groups.get(id(flow.measure_group))
        if group is None:
            raise RuntimeError("Die Langlochmaßfelder fehlen; Aufnahme anhalten.")
        for key, value in (("slot_length", length), ("slot_angle", float(step.get("angle", 0.0)))):
            editor = group.widgets[key]
            spin = getattr(editor, "spin", editor)
            first = len(self.recorder.slides)
            self.recorder.add("", "", 2.0, target=spin)
            action_first = len(self.recorder.slides)
            _type(self, spin, typed(value))
            action_last = len(self.recorder.slides)
            if not math.isclose(float(spin.value()), value, abs_tol=1e-6):
                raise RuntimeError("Der getippte Langlochwert stimmt nicht; Eingabe prüfen.")
            self.recorder.add("", "", 3.0, target=spin)
            scene(key, first, action_first, action_last, close_focus=row_focus(spin))
        import time

        deadline = time.monotonic() + 120
        while not flow._measure_accept.isEnabled():
            if time.monotonic() > deadline:
                raise RuntimeError("Der Langlochentwurf lässt sich noch nicht übernehmen.")
            self.settle(5)
        first = len(self.recorder.slides)
        accept_focus = row_focus(flow._measure_accept)
        self.recorder.add("", "", 2.0, target=flow._measure_accept)
        action_first = len(self.recorder.slides)
        _click(self, flow._measure_accept)
        self.checked("Langloch über den wirklichen Übernehmen-Knopf bestätigt")
        action_last = len(self.recorder.slides)
        expected = before + int(step.get("expected_operation_delta", 1))
        if len(self.session.project.document.ops) != expected:
            raise RuntimeError("Der Langlochzug hat den geplanten Verlauf nicht hergestellt.")
        self.window.object_tree.tree.clearSelection()
        self.settle(12)
        self.recorder.add("", "", 4.0)
        scene("apply", first, action_first, action_last, applied=True, close_focus=accept_focus)
        return scenes

    def card(
        self,
        op: str,
        steps: Sequence[tuple[str, Any, str, str, str, str]],
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        *,
        body: str,
        feature: str,
    ) -> None:
        """Eine Handlung an einem Merkmal: Zahl in die Karte rechts tippen, Übernehmen.

        Das ist der Weg, den die Oberfläche einem Kunden zuerst anbietet: Die
        Karte zeigt die Felder der Handlung mit den gemessenen Werten, der eine
        Knopf unten nennt die Handlung, an der zuletzt getippt wurde.
        """
        from PySide6.QtCore import QCoreApplication, QEvent, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDoubleSpinBox,
            QScrollArea,
            QWidget,
        )

        if self.window.object_tree.selected_features() != ((body, feature),):
            self.window.object_tree.select_feature(body, feature)
            self.settle(12)
        # Eine neu gebaute Karte löscht ihre alten Zeilen erst mit der nächsten
        # Zustellung von DeferredDelete; bis dahin fände die Suche jedes Feld doppelt.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.settle(6)
        panel = self.window.feature_panel
        flow = getattr(self.window, "_quiet_placement", None)
        group = None
        if flow is not None and flow.spec_of().name == op:
            group = panel._measure_groups.get(id(flow.measure_group))
        if group is not None and flow is not None:
            import time

            before = len(self.session.project.document.ops)
            for name, value, step_de, step_en, note_de, note_en in steps:
                editor = group.widgets[name]
                spin = getattr(editor, "spin", editor)
                if isinstance(spin, QDoubleSpinBox):
                    line = spin.lineEdit()
                    line.setFocus()
                    line.selectAll()
                    QTest.keyClicks(line, typed(float(value)))
                    QTest.keyClick(line, Qt.Key.Key_Tab)
                else:
                    set_field(editor, value)
                self.settle(12)
                self.add(step_de, step_en, note_de, note_en, 7.0, target=spin)
            button = flow._measure_accept
            deadline = time.monotonic() + 120.0
            while not button.isEnabled() and time.monotonic() < deadline:
                self.settle(10)
            if not button.isEnabled():
                raise RuntimeError("Die Vorschau gibt Übernehmen nicht frei; Befunde prüfen.")
            self.detail_shot(flow._measure_box, "measure")
            self.add(title_de, title_en, detail_de, detail_en, 5.0, target=button)
            button.click()
            self.checked(f"{op}: " + ", ".join(f"{name}={value}" for name, value, *_ in steps))
            if len(self.session.project.document.ops) <= before:
                raise RuntimeError(f"{op}: Übernehmen hat keinen Schritt angelegt.")
            self.window.object_tree.tree.clearSelection()
            self.settle(8)
            return
        key = next((entry for entry, run in panel._runs.items() if run.op == op), None)
        if key is None:
            raise RuntimeError(f"Die Karte bietet {op} an diesem Merkmal nicht an: {panel._runs}")
        declared = {entry.name: entry for entry in lf.REGISTRY.get(op).params.spec()}
        editors = [
            widget
            for widget in panel.findChildren(QWidget)
            if widget.property("handlingKey") == key
            and isinstance(widget, (QDoubleSpinBox, QCheckBox, QComboBox))
            and widget.isVisibleTo(panel)
        ]

        def editor_for(name: str) -> Any:
            label = str(declared[name].title)
            found = [w for w in editors if w.accessibleName().endswith(f" — {label}")]
            if len(found) != 1:
                raise RuntimeError(
                    f"{op}: Feld {name} ({label}) nicht eindeutig in der Karte: "
                    f"{[w.accessibleName() for w in editors]}"
                )
            return found[0]

        def reveal(widget: Any) -> None:
            parent = widget.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    parent.ensureWidgetVisible(widget, 40, 60)
                    break
                parent = parent.parentWidget()
            self.settle(8)

        before = len(self.session.project.document.ops)
        for name, value, step_de, step_en, note_de, note_en in steps:
            editor = editor_for(name)
            reveal(editor)
            if isinstance(editor, QDoubleSpinBox):
                line = editor.lineEdit()
                line.setFocus()
                line.selectAll()
                QTest.keyClicks(line, typed(float(value)))
                self.settle(6)
                actual = editor.value_mm() if hasattr(editor, "value_mm") else editor.value()
                if abs(float(actual) - float(value)) > 1e-6:
                    raise RuntimeError(f"{op}: Feld {name} zeigt {actual} statt {value}.")
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(value))
            else:
                index = editor.findData(value)
                if index < 0:
                    raise RuntimeError(f"{op}: Auswahlwert {value} fehlt in {name}.")
                editor.setCurrentIndex(index)
            self.settle(10)
            self.add(step_de, step_en, note_de, note_en, 7.0, target=editor)
        if panel._armed != key:
            raise RuntimeError(f"Der Knopf unten nennt {panel._armed}, erwartet {key}.")
        button = panel._apply
        self.add(title_de, title_en, detail_de, detail_en, 9.0, target=button)
        # Für den Short nur die Handlungsgruppe (Überschrift und Felder), nicht die ganze Karte.
        self.detail_shot(editor_for(steps[0][0]).parentWidget(), "card")
        button.click()
        # Der Beleg nennt Handlung und Werte — „Übernehmen" allein wäre mehrdeutig.
        self.checked(
            f"{panel._runs[key].title}: "
            + ", ".join(f"{name}={value}" for name, value, *_ in steps)
        )
        if len(self.session.project.document.ops) <= before:
            raise RuntimeError(f"{op}: Übernehmen hat keinen Schritt angelegt.")
        self.window.object_tree.tree.clearSelection()
        self.settle(6)
        QTest.keyClick(self.window.viewport, Qt.Key.Key_Escape)
        self.settle(6)

    def dialog_values(self, dialog: Any, values: dict[str, Any]) -> None:
        """Werte in einen offenen Operationsdialog eintragen — Zahlen wie Ausdrücke."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        placement = getattr(dialog, "placement_flow", None)
        if placement is not None and placement.active:
            self.add(
                "Die Werte im Dialog eintragen",
                "Enter the values in the dialog",
                "Esc beendet das Ziehen im Bild. Der Dialog bleibt für genaue Zahlen offen.",
                "Esc ends dragging in the view. The dialog stays open for exact numbers.",
                7.0,
                dialog=dialog,
                target=self.window.viewport,
            )
            self.window.viewport.setFocus()
            QTest.keyClick(self.window.viewport, Qt.Key.Key_Escape)
            self.settle(12)
            if placement.active or not dialog.isVisible():
                raise RuntimeError("Esc hat die Platzierung nicht zum Werte-Dialog verlassen.")
        declared = {entry.name: entry for entry in dialog.spec.params.spec()}
        if any(declared[key].placement == "advanced" for key in values if key in declared):
            advanced = getattr(dialog, "advanced", None)
            if advanced is not None and not advanced.isChecked():
                advanced.click()
        for key, value in values.items():
            field = dialog._editors.get(key)
            if field is None:
                raise RuntimeError(f"{dialog.spec.name}: kein Eingabefeld {key}")
            set_field(field, value)
        dialog.valuesChanged.emit()
        self.settle(20)
        current = dialog.values()
        for key, value in values.items():
            if isinstance(value, str) and value.startswith("=") and current.get(key) != value:
                raise RuntimeError(f"Der Dialog hat den Ausdruck {key}={value} nicht behalten.")

    def confirm_dialog(
        self,
        dialog: Any,
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        values: dict[str, Any],
        before: int,
        *,
        new_step: bool,
    ) -> None:
        """Den offenen Dialog aufnehmen, über seinen Knopf bestätigen und das Ergebnis prüfen."""
        self.add(
            title_de, title_en, detail_de, detail_en, 11.0, dialog=dialog, target=lf._button(dialog)
        )
        raw = dialog.screen().grabWindow(dialog.winId())
        path = self.folder / "shots" / f"dialog-{len(self.checks):02d}.png"
        if not raw.save(str(path)):
            raise RuntimeError("Der geöffnete Werte-Dialog ließ sich nicht aufnehmen.")
        self._pending_detail = path.relative_to(self.folder).as_posix()
        lf._button(dialog).click()
        self.checked(title_de)
        count = len(self.session.project.document.ops)
        if new_step and count <= before:
            raise RuntimeError(f"{dialog.spec.name}: der Knopf hat keinen Schritt übernommen.")
        if not new_step and count != before:
            raise RuntimeError("Das Bearbeiten eines Schritts hat einen zweiten angelegt.")
        actual = self.session.project.document.ops[-1].params
        for key, value in values.items():
            if isinstance(value, str) and value.startswith("=") and actual.get(key) != value:
                raise RuntimeError(f"Der gespeicherte Schritt hat {key}={value} nicht behalten.")

    def listed(
        self,
        op: str,
        values: dict[str, Any],
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        *,
        bodies: Sequence[str],
        hint_de: str,
        hint_en: str,
    ) -> None:
        """Eine Handlung aus der Liste zur Auswahl: Körper wählen, Knopf rechts, Dialog."""
        lf._fit(self.window, self.recorder.app)
        self.window.object_tree.select_objects(tuple(bodies))
        self.settle(12)
        panel = self.window.selection_operations
        button = panel._quick_buttons.get(op) or panel._buttons.get(op)
        before = len(self.session.project.document.ops)
        if button is not None and button.isVisible() and button.isEnabled():
            panel.scroller.ensureWidgetVisible(button, 40, 80)
            self.settle(10)
            self.add(
                f"Rechts: „{button.text()}“",
                f"On the right: “{button.text()}”",
                hint_de,
                hint_en,
                7.0,
                target=button,
            )
            button.click()
        else:
            action = lf._operation_action(self.window, op)
            if action is None or not action.isEnabled():
                raise RuntimeError(f"Kein sichtbarer Kundenweg für {op}; Aufnahmeplan prüfen.")
            lf._show_action_path(self.recorder, action, words(hint_de, hint_en))
            action.trigger()
        self.settle(15)
        dialog = self.window._op_dialog
        if dialog is None:
            raise RuntimeError(f"{op}: der Knopf hat keinen Dialog geöffnet.")
        self.dialog_values(dialog, values)
        self.confirm_dialog(
            dialog, title_de, title_en, detail_de, detail_en, values, before, new_step=True
        )

    def operation_dialog_scenes(self, step: dict[str, Any], dialog: Any) -> list[dict[str, Any]]:
        """Alle verlangten Werte und die Bestätigung über wirkliche Dialoggesten aufnehmen."""
        from functools import partial
        from time import monotonic

        from PySide6.QtWidgets import QCheckBox, QComboBox

        from tools.workshop_inventory_capture import _choose, _click, _type

        before = len(self.session.project.document.ops)
        scenes: list[dict[str, Any]] = []

        def record(key: str, action: Any = None, target: Any = None) -> None:
            stage = step["stages"][key]
            scenes.append(
                self.control_scene(
                    f"{step['key']}-{key}",
                    tuple(stage["de"][name] for name in ("title", "voice_before", "voice_after")),
                    tuple(stage["en"][name] for name in ("title", "voice_before", "voice_after")),
                    action=action,
                    target=target,
                    dialog=dialog,
                    minimum_seconds=stage.get("minimum_seconds", 0),
                    short=bool(stage.get("short", step.get("short", False))),
                )
            )

        dialog.setMinimumWidth(840)
        self.settle(12)
        placement = getattr(dialog, "placement_flow", None)
        if placement is not None and placement.active:
            back = placement._back
            if not back.isVisible() or not back.isEnabled():
                raise RuntimeError("Werte bearbeiten ist nicht sichtbar; Platzierungsweg prüfen.")
            record(
                "placement",
                lambda: _click(self, back, dialog=dialog),
                back,
            )
            if placement.active or not dialog.isVisible():
                raise RuntimeError("Die direkte Platzierung bleibt aktiv; Werte noch nicht ändern.")
        declared = {entry.name: entry for entry in dialog.spec.params.spec()}
        if (
            any(declared[name].placement == "advanced" for name in step["values"])
            and not dialog.advanced.isChecked()
        ):
            record("advanced", lambda: _click(self, dialog.advanced, dialog=dialog))
        for name, value in step["values"].items():
            field = dialog._editors.get(name)
            if field is None:
                raise RuntimeError(f"Das tatsächliche Feld {name} fehlt im Werte-Dialog.")
            if isinstance(field, QComboBox):
                gesture: Any = partial(_choose, self, field, value, dialog=dialog)
            elif isinstance(field, QCheckBox):
                gesture = (
                    (lambda field=field: _click(self, field, dialog=dialog))
                    if field.isChecked() != bool(value)
                    else None
                )
            else:
                spin = getattr(field, "spin", field)
                text = typed(float(value)) if isinstance(value, (int, float)) else str(value)
                gesture = partial(_type, self, spin, text, dialog=dialog)
            record(name, gesture, field)
        current = dialog.values()
        for name, value in step["values"].items():
            actual = current.get(name)
            matches = (
                math.isclose(float(actual), value, abs_tol=1e-6)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else actual == value
            )
            if not matches:
                raise RuntimeError(f"Die wirkliche Eingabe für {name} stimmt nicht: {actual}")
        accept = lf._button(dialog)
        deadline = monotonic() + 120
        while not accept.isEnabled():
            if monotonic() > deadline:
                raise RuntimeError("Der Entwurf ist nicht übernehmbar; Aufnahme anhalten.")
            self.settle(5)
        if "preview" in step["stages"]:
            record("preview", target=accept)

        def apply_and_wait() -> None:
            _click(self, accept, dialog=dialog)
            self.checked("Operation mit sichtbaren Dialoggesten übernommen")

        record("apply", apply_and_wait, accept)
        if len(self.session.project.document.ops) != before + 1:
            raise RuntimeError("Übernehmen hat nicht genau einen Verlaufsschritt erzeugt.")
        write_json(
            self.folder / f"operation-{step['key']}.json",
            {
                "operation": step["op"],
                "chosen_values": current,
                "stored_values": dict(self.session.project.document.ops[-1].params),
            },
        )
        return scenes

    def operation_scenes(self, step: dict[str, Any], bodies: Sequence[str]) -> list[dict[str, Any]]:
        """Körper, Operation, einzelne Felder und Übernehmen als wirklichen Kundenweg erfassen."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        from tools.workshop_inventory_capture import _click, _frame, _type

        tree = self.window.object_tree.tree

        def select() -> None:
            for number, body in enumerate(bodies):
                item = next(
                    tree.topLevelItem(index)
                    for index in range(tree.topLevelItemCount())
                    if tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole) == body
                )
                tree.scrollToItem(item)
                self.settle(8)
                point = tree.visualItemRect(item).center()
                self.recorder.click("", "", target=tree.viewport().mapToGlobal(point))
                QTest.mouseClick(
                    tree.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.ControlModifier
                    if number
                    else Qt.KeyboardModifier.NoModifier,
                    pos=point,
                    delay=100,
                )
                self.settle(8)
                _frame(self, seconds=1.0)

        stage = step["stages"]["select"]
        scenes = [
            self.control_scene(
                f"{step['key']}-select",
                tuple(stage["de"][name] for name in ("title", "voice_before", "voice_after")),
                tuple(stage["en"][name] for name in ("title", "voice_before", "voice_after")),
                action=select,
                target=tree,
                short=bool(stage.get("short", False)),
            )
        ]
        if self.window.settings.right_panel_visible:
            self.window.action_toggle_right()
        self.settle(10)
        panel = self.window.selection_operations
        button = panel._quick_buttons.get(step["op"]) or panel._buttons.get(step["op"])
        if button is not None and not button.isVisible() and panel.search.isVisible():
            stage = step["stages"]["search"]
            query = str(button.property("operationTitle") or button.text())
            scenes.append(
                self.control_scene(
                    f"{step['key']}-search",
                    tuple(stage["de"][name] for name in ("title", "voice_before", "voice_after")),
                    tuple(stage["en"][name] for name in ("title", "voice_before", "voice_after")),
                    action=lambda: _type(self, panel.search, query),
                    target=panel.search,
                    short=bool(stage.get("short", False)),
                )
            )
        first = len(self.recorder.slides)
        if button is not None and button.isVisible() and button.isEnabled():
            panel.scroller.ensureWidgetVisible(button, 40, 80)
            self.settle(10)
            self.recorder.add("", "", 2.0, target=button)
            action_first = len(self.recorder.slides)
            _click(self, button)
        else:
            action = lf._operation_action(self.window, step["op"])
            if action is None or not action.isEnabled():
                raise RuntimeError(
                    "Die registrierte Operation ist über kein echtes Menü erreichbar."
                )
            self.menu_action(action)
            action_first = self._menu_capture["action_first_slide"]
        self.settle(15)
        dialog = self.window._op_dialog
        if dialog is None or not dialog.isVisible():
            raise RuntimeError("Die Operation hat keinen sichtbaren Werte-Dialog geöffnet.")
        dialog.setMinimumWidth(840)
        _frame(self, dialog=dialog, seconds=1.0)
        action_last = len(self.recorder.slides)
        self.recorder.add("", "", 6.0, dialog=dialog)
        point = dialog.mapToGlobal(QPoint(0, 0)) - self.window.mapToGlobal(QPoint(0, 0))
        stage = step["stages"]["entry"]
        scenes.append(
            {
                "key": f"{step['key']}-entry",
                **stage[LANGUAGE],
                "first_slide": first,
                "last_slide": len(self.recorder.slides),
                "action_first_slide": action_first,
                "action_last_slide": action_last,
                "model_crop": [0, 0, *self.recorder.frame_size],
                "after_model_crop": [point.x(), point.y(), dialog.width(), dialog.height()],
                "minimum_seconds": 8,
                "short": bool(stage.get("short", step.get("short", False))),
            }
        )
        scenes.extend(self.operation_dialog_scenes(step, dialog))
        return scenes

    def edit_step(
        self,
        op_id: int,
        values: dict[str, Any],
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
    ) -> None:
        """Einen Schritt im Verlauf per Doppelklick öffnen und ihm andere Werte geben."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        lf._fit(self.window, self.recorder.app)
        history = self.window.history_panel
        item = next(
            (
                history.list.item(row)
                for row in range(history.list.count())
                if history.list.item(row).data(Qt.ItemDataRole.UserRole) == op_id
            ),
            None,
        )
        if item is None:
            raise RuntimeError(f"Der Verlauf zeigt keinen Schritt mit der Kennung {op_id}.")
        history.list.scrollToItem(item)
        self.settle(8)
        centre = history.list.visualItemRect(item).center()
        before = len(self.session.project.document.ops)
        self.add(
            "Im Verlauf den Schritt doppelt anklicken",
            "Double-click the step in the history",
            "Jeder Schritt lässt sich später wieder öffnen und mit anderen Werten ausführen.",
            "Any step can be reopened later and run again with different values.",
            8.0,
            target=history.list.viewport().mapToGlobal(centre),
        )
        QTest.mouseDClick(
            history.list.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            centre,
        )
        self.settle(15)
        if self.window._op_dialog is None:
            # Ein synthetischer Doppelklick erreicht die Liste nicht in jeder Lage;
            # ``_on_activated`` ist genau der Slot, an dem der echte Doppelklick hängt.
            history._on_activated(item)
            self.settle(15)
        dialog = self.window._op_dialog
        if dialog is None:
            raise RuntimeError("Der Doppelklick im Verlauf hat keinen Dialog geöffnet.")
        self.dialog_values(dialog, values)
        self.confirm_dialog(
            dialog, title_de, title_en, detail_de, detail_en, values, before, new_step=False
        )

    def move(
        self, body: str, dx: float, title_de: str, title_en: str, detail_de: str, detail_en: str
    ) -> None:
        """Ein Teil über die Bewegen-Leiste unten um einen genauen Betrag verschieben."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        lf._fit(self.window, self.recorder.app)
        self.window.object_tree.select_object(body)
        self.settle(10)
        strip = self.window.tools
        button = strip._buttons["transform"]
        self.add(
            "Unten: Bewegen",
            "Bottom bar: Move",
            "Das Werkzeug öffnet eine Leiste mit X, Y und Z in Millimetern.",
            "The tool opens a bar with X, Y and Z in millimetres.",
            6.0,
            target=button,
        )
        button.click()
        self.settle(12)
        bar = self.window.transform_bar
        if not bar.isVisible() or bar.role() != "move":
            raise RuntimeError("Die Bewegen-Leiste ist nach dem Klick nicht offen.")
        line = bar.dx.lineEdit()
        line.setFocus()
        line.selectAll()
        QTest.keyClicks(line, typed(dx))
        self.settle(6)
        if abs(bar.dx.value_mm() - dx) > 1e-6:
            raise RuntimeError(f"Das X-Feld zeigt {bar.dx.value_mm()} statt {dx}.")
        before = len(self.session.project.document.ops)
        self.add(title_de, title_en, detail_de, detail_en, 8.0, target=bar.dx)
        self.detail_shot(bar, "move")
        QTest.keyClick(line, Qt.Key.Key_Return)
        self.checked(title_de)
        if len(self.session.project.document.ops) <= before:
            raise RuntimeError("Enter in der Bewegen-Leiste hat keinen Schritt angelegt.")
        button.click()
        self.settle(8)
        self.window.object_tree.tree.clearSelection()
        self.settle(6)

    def history(self, redo: bool = False) -> dict[str, int]:
        """Tatsächliche Menüaktion, danach überprüftes Ergebnis."""
        action = self.window.redo_action if redo else self.window.undo_action
        if not action.isEnabled():
            raise RuntimeError("Die erwartete Verlaufshandlung ist nicht freigegeben.")
        self.recorder.add("", "", 1.0)
        action_first = len(self.recorder.slides)
        self.menu_action(action)
        self.checked("Wiederholen" if redo else "Rücknahme")
        action_last = len(self.recorder.slides)
        self.add(
            "Wiederhergestellt" if redo else "Zurückgenommen",
            "Restored" if redo else "Undone",
            "Das Teil wird aus den verbleibenden Schritten neu berechnet — nichts geht verloren.",
            "The part is rebuilt from the remaining steps — nothing is lost.",
            8.0,
        )
        return {"action_first_slide": action_first, "action_last_slide": action_last}

    def shot(
        self,
        key: str,
        title_de: str,
        title_en: str,
        detail_de: str,
        detail_en: str,
        *,
        cover: bool = False,
        focus: tuple[Point, float] | None = None,
        mirror: bool = False,
    ) -> None:
        """Sauberen echten Viewport ohne Filmtext und überlagernde Karten bewahren."""
        from PySide6.QtCore import QPoint

        panels = [getattr(self.window.overlay, name) for name in ("left", "right", "bottom")]
        panels.append(self.window.tools)
        visibility = [panel.isVisible() for panel in panels]
        selected = self.window.object_tree.selected_objects()
        features = self.window.object_tree.selected_features()
        original_size = self.window.size()
        viewport = self.window.viewport
        renderer = viewport.renderer
        original_pose = renderer.camera_pose()
        try:
            lf.video_base.show_panels(self.window, False)
            if not self.raw:
                self.window.resize(1120, 1120)
                lf.video_base.settle_resize(self.window, self.recorder.app)
            if not self.raw:
                lf._fit(self.window, self.recorder.app)
            if focus is not None or mirror:
                pose = renderer.camera_pose()
                direction = unit(
                    tuple(pose.position[axis] - pose.focal_point[axis] for axis in range(3))
                )
                if mirror:
                    direction = (-direction[0], -direction[1], direction[2])
                point, distance = focus if focus is not None else (pose.focal_point, None)
                if distance is None:
                    distance = math.dist(pose.position, pose.focal_point)
                else:
                    direction = unit((direction[0], direction[1], direction[2] + 0.45))
                position = tuple(point[axis] + direction[axis] * distance for axis in range(3))
                scale = distance * 0.3 if renderer.parallel_projection() else None
                viewport.set_camera_pose(position, point, (0.0, 0.0, 1.0), parallel_scale=scale)
                viewport.settle_camera()
                renderer.render_now()
                self.settle(18)
            captured = self.window.screen().grabWindow(self.window.winId()).toImage()
            origin = viewport.mapTo(self.window, QPoint(0, 0))
            scale_factor = captured.width() / self.window.width()
            image = captured.copy(
                round(origin.x() * scale_factor),
                round(origin.y() * scale_factor),
                round(viewport.width() * scale_factor),
                round(viewport.height() * scale_factor),
            )
            path = self.folder / "shots" / f"{key}.png"
            if image.isNull() or not image.save(str(path)):
                raise RuntimeError(f"Kein echter Viewport für {key}")
        finally:
            self.window.resize(original_size)
            for panel, visible in zip(panels, visibility, strict=True):
                panel.setVisible(visible)
            if features:
                self.window.object_tree.select_features(features)
            else:
                self.window.object_tree.select_objects(selected)
            renderer.set_camera_pose(original_pose)
            self.settle(12)
        self.shots.append(
            {
                "key": key,
                "title": words(title_de, title_en),
                "detail": words(detail_de, detail_en),
                "viewport_path": path.relative_to(self.folder).as_posix(),
                "duration": 5.0,
                "cover": cover,
                "detail_path": self._pending_detail,
            }
        )
        self._pending_detail = None

    def finish(self, *, minimum_seconds: float = 180.0) -> None:
        """Projekt durch den echten Speicherdialog sichern, dann Ergebnisse belegen."""
        from app.branding import APP_VERSION
        from app.core.geom.mesh import as_mesh_data

        self.window.object_tree.tree.clearSelection()
        save_first = len(self.recorder.slides)
        self.file_dialog(
            lambda: self.menu_action(self.window.save_action),
            self.folder / f"{self.story}.p3d",
            save=True,
        )
        self.finish_scenes.extend(
            [
                {
                    "key": "save-menu",
                    "action": "save",
                    "short": False,
                    "title": words("Das Projekt speichern", "Save the project"),
                    "detail": words("Datei → Speichern", "File → Save"),
                    "voice": words(
                        "Ich speichere jetzt das Projekt über Datei und Speichern.",
                        "I save the project using File and Save.",
                    ),
                    "first_slide": save_first,
                    "last_slide": self._file_capture["first_slide"],
                    "minimum_seconds": 6,
                    "model_crop": [0, 0, 900, 900],
                    "focus": None,
                },
                {
                    "key": "save-file",
                    "action": "save",
                    "short": False,
                    "title": words(
                        "Name und Projektdatei prüfen", "Check the name and project file"
                    ),
                    "detail": words(
                        "Das Projekt enthält den Verlauf.", "The project includes the history."
                    ),
                    "voice": words(
                        "Ich gebe einen Namen ein und klicke auf Speichern. Die Projektdatei "
                        "enthält die ursprüngliche Form und alle Bearbeitungsschritte.",
                        "I enter a name and click Save. The project file keeps the original shape "
                        "and every editing step.",
                    ),
                    **self._file_capture,
                    "minimum_seconds": 10,
                    "focus": None,
                },
            ]
        )
        self.checked("Gespeichertes Endergebnis")
        for index, body in enumerate(self.session.last_result.scene.objects.values(), 1):
            as_mesh_data(body.mesh).raw.export(self.folder / f"result-{index}.stl")
        self.add(
            "Projekt gespeichert",
            "Project saved",
            "Zum Drucken exportiert man eine STL; das Projekt bleibt zum Weiterändern.",
            "For printing, export an STL; the project stays editable for later changes.",
            8.0,
        )
        self.file_dialog(
            lambda: self.menu_action(self.window.open_action), self.folder / f"{self.story}.p3d"
        )
        self.checked("Gespeichertes Projekt erneut geöffnet")
        lf._fit(self.window, self.recorder.app)
        restore_first = len(self.recorder.slides)
        self.add(
            "Alles wieder da",
            "Everything is back",
            "Verlauf und Maße sind erhalten. Jede Zahl lässt sich später wieder ändern.",
            "History and dimensions are preserved. Any number can be changed again later.",
            9.0,
        )
        self.finish_scenes.append(
            {
                "key": "saved-result",
                "action": "save",
                "short": False,
                "title": words("Das Projekt bleibt änderbar", "The project stays editable"),
                "detail": words(
                    "Projekt zum Weiterarbeiten, STL für die Form.",
                    "Project for editing, STL for the shape.",
                ),
                "voice": words(
                    "Die Änderung ist gespeichert. Zum Weiterarbeiten behalte ich das Projekt. "
                    "Eine STL enthält nur die fertige Form.",
                    "The change is saved. I keep the project for further editing. "
                    "An STL contains only the finished shape.",
                ),
                "first_slide": restore_first,
                "last_slide": len(self.recorder.slides),
                "minimum_seconds": 9,
                "focus": None,
                "model_crop": [0, 0, *self.recorder.frame_size],
            }
        )
        self.shot(
            "final",
            self.title,
            self.title,
            "Fertige STL, neue Maße, jeder Schritt nachvollziehbar.",
            "Original STL, new dimensions, every step traceable.",
            cover=True,
        )
        self.recorder.orbit(
            words("Das fertige Ergebnis", "The finished result"),
            words(
                "Solidon3D · Entwicklungsvorschau · solidon3d.de",
                "Solidon3D · Development preview · solidon3d.de",
            ),
            seconds=6.0,
            degrees=35.0,
        )
        if self.recorder.seconds < minimum_seconds:
            raise RuntimeError(f"Der vollständige Ablauf ist zu kurz: {self.recorder.seconds}s.")
        write_json(
            self.folder / "short_shots.json",
            {
                "story": self.story,
                "language": LANGUAGE,
                "title": self.title,
                "preview": True,
                "version": APP_VERSION,
                "shots": self.shots,
            },
        )
        write_json(self.folder / f"{self.story}.timeline.json", self.recorder.events)
        write_json(
            self.folder / "capture.json",
            {
                "complete": True,
                "story": self.story,
                "language": LANGUAGE,
                "chapter": self.title,
                "seconds": self.recorder.seconds,
                "slides": [
                    {
                        "path": slide.path.relative_to(self.folder).as_posix(),
                        "seconds": slide.seconds,
                    }
                    for slide in self.recorder.slides
                ],
            },
        )


def set_field(field: Any, value: Any) -> None:
    """Vorhandene Eingabetypen benutzen; unbekannte Felder nie still überspringen."""
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

    if isinstance(field, QComboBox):
        index = field.findData(value)
        if index < 0:
            raise RuntimeError(f"Auswahlwert nicht vorhanden: {value}")
        field.setCurrentIndex(index)
    elif isinstance(field, QCheckBox):
        field.setChecked(bool(value))
    elif isinstance(value, str) and value.startswith("=") and hasattr(field, "toggle"):
        from PySide6.QtTest import QTest

        if not field.toggle.isChecked():
            field.toggle.click()
        field.text.setFocus()
        field.text.selectAll()
        QTest.keyClicks(field.text, value)
    elif hasattr(field, "set_value"):
        field.set_value(value)
    elif isinstance(field, QLineEdit):
        field.setText(str(value))
    elif hasattr(field, "setValue"):
        field.setValue(value)
    else:
        raise RuntimeError(f"Nicht unterstützter echter Feldtyp: {type(field).__name__}")


def hole_at(tutorial: Tutorial, body: str, *, left: bool) -> tuple[str, Any]:
    """Bohrung aus real erkannter Lage bestimmen, nicht aus vermuteter Nummer."""
    features = tutorial.session.last_result.scene.objects[body].features
    holes = [(key, f) for key, f in features.items() if f.kind == "hole"]
    if not holes:
        raise RuntimeError("Keine Bohrung erkannt; keine Merkmalsbearbeitung filmbar.")
    return sorted(holes, key=lambda pair: pair[1].params["centre"][0])[0 if left else -1]


def last_op_id(tutorial: Tutorial) -> int:
    """Die Kennung des zuletzt angelegten Schritts, für den Doppelklick im Verlauf."""
    return int(tutorial.session.project.document.ops[-1].id)


def opening(tutorial: Tutorial, paths: list[Path]) -> list[str]:
    """Problem, Vorschaukennzeichnung und wirklich geöffnetes Ausgangsnetz zeigen."""
    tutorial.add(
        tutorial.title,
        tutorial.title,
        "Ein fertiges 3D-Modell anpassen, ohne es neu zu zeichnen.",
        "Adapt a finished 3D model without redrawing it.",
        8.0,
        title_card=True,
    )
    tutorial.add(
        "Entwicklungsvorschau",
        "Development preview",
        "Aufgenommen mit einem Entwicklungsstand. Die Oberfläche kann vom Download abweichen.",
        "Recorded with a development build. The interface may differ from the download.",
        9.0,
    )
    bodies = [tutorial.import_file(path) for path in paths]
    tutorial.overview(
        "Die STL ist drin",
        "The STL is loaded",
        "Solidon3D erkennt Löcher und Flächen von selbst. Das Original bleibt unangetastet.",
        "Solidon3D recognises holes and faces on its own. The original stays untouched.",
        seconds=6.0,
        degrees=45.0,
    )
    tutorial.shot(
        "source",
        "Ausgangs-STL",
        "Original STL",
        "So kommt das Modell aus dem Internet oder vom Slicer.",
        "This is how the model arrives from the internet or the slicer.",
    )
    return bodies


def story_holes(tutorial: Tutorial, paths: list[Path]) -> None:
    """Durchmesser und Lochabstand an einer echten Importdatei ändern — per Zahl in der Karte."""
    body = opening(tutorial, paths)[0]
    tutorial.add(
        "Das Problem",
        "The problem",
        "Die Löcher haben 6 mm und sitzen 56 mm auseinander. Gebraucht werden 9 mm und 48 mm.",
        "The holes are 6 mm and 56 mm apart. What is needed: 9 mm and 48 mm.",
        9.0,
    )
    for left in (True, False):
        key, feature = hole_at(tutorial, body, left=left)
        centre = feature.params["centre"]
        tutorial.select_feature(
            body,
            key,
            "Das linke Loch anklicken" if left else "Jetzt das rechte Loch",
            "Click the left hole" if left else "Now the right hole",
        )
        tutorial.close_up(
            (centre[0], centre[1], 8.0),
            110.0,
            "Die Maße stehen im Bild",
            "The dimensions are shown in the view",
            "6 mm Durchmesser, gemessen am Modell. Rechts lassen sie sich direkt ändern.",
            "6 mm in diameter, measured on the model. On the right they can be changed directly.",
            6.0,
            keep_selection=True,
        )
        target_x = -24.0 if left else 24.0
        tutorial.card(
            "resize_hole",
            [
                (
                    "diameter",
                    9.0,
                    "Durchmesser: 9 eintippen",
                    "Diameter: type 9",
                    "Das Feld „Durchmesser“ unter „Bohrung ändern“. "
                    "Die Vorschau im Bild folgt sofort.",
                    "The “Diameter” field under “Change hole”. "
                    "The preview in the view follows immediately.",
                ),
                (
                    "x",
                    target_x,
                    f"Position: X = {target_x:g}",
                    f"Position: X = {target_x:g}",
                    "Halber Abstand von 48 mm, mit Vorzeichen für links oder rechts.",
                    "Half of 48 mm, with the sign for left or right.",
                ),
            ],
            "Übernehmen",
            "Apply",
            "Der Knopf unten nennt die Handlung: „Bohrung ändern“. Ein Klick, fertig.",
            "The button at the bottom names the action: “Change hole”. One click, done.",
            body=body,
            feature=key,
        )
        tutorial.close_up(
            (target_x, 0.0, 8.0),
            120.0,
            "9 mm statt 6 mm" if left else "Beide Seiten passen",
            "9 mm instead of 6 mm" if left else "Both sides fit",
            "Das Loch ist größer und sitzt näher an der Mitte. Der Rand des Teils ist unverändert.",
            "The hole is larger and closer to the centre. The edge of the part is unchanged.",
            6.0,
        )
        tutorial.turn(
            "Von allen Seiten sauber",
            "Clean from every side",
            "Die Wand des Lochs ist durchgehend — kein Flicken, kein Rest vom alten Loch.",
            "The hole wall is continuous — no patch, no trace of the old hole.",
            5.0,
            50.0,
        )
        tutorial.shot(
            "left" if left else "pair",
            "Größer und verschoben" if left else "Beide Löcher passen",
            "Larger and moved" if left else "Both holes fit",
            "Das Teil selbst bleibt, wie es war.",
            "The part itself stays as it was.",
            focus=((target_x, 0.0, 8.0), 130.0),
        )
    checks = tutorial.checks[-1]["geometry"][0]
    if any(abs(a - b) > 0.01 for a, b in zip(checks["extents_mm"], (100, 55, 8), strict=True)):
        raise RuntimeError("Die Außenmaße wurden unerwartet verändert.")
    tutorial.overview(
        "100 x 55 x 8 mm — unverändert",
        "100 x 55 x 8 mm — unchanged",
        "Nur die Löcher sind neu. Das Teil musste nicht skaliert und nicht neu gezeichnet werden.",
        "Only the holes are new. The part was neither scaled nor redrawn.",
        seconds=7.0,
        degrees=60.0,
    )
    tutorial.history()
    tutorial.shot(
        "undo",
        "Rückgängig",
        "Undo",
        "Die letzte Änderung ist zurück — das rechte Loch wieder wie vorher.",
        "The last change is reverted — the right hole is as before.",
    )
    tutorial.history(redo=True)
    tutorial.shot(
        "redo",
        "Wiederholen",
        "Redo",
        "Und wieder da. Jeder Schritt bleibt im Verlauf.",
        "And back again. Every step stays in the history.",
    )


def story_slot(tutorial: Tutorial, paths: list[Path]) -> None:
    """Eine erkannte Importbohrung zum Langloch machen und den Schritt später ändern."""
    body = opening(tutorial, paths)[0]
    tutorial.add(
        "Neu in der Vorschau auf 0.4.1",
        "New in the 0.4.1 preview",
        "Die Schraube soll sich ein Stück verschieben lassen. Aus dem Loch wird ein Langloch.",
        "The screw should be adjustable. The hole becomes a slot.",
        9.0,
    )
    key, feature = hole_at(tutorial, body, left=True)
    centre = feature.params["centre"]
    tutorial.select_feature(body, key, "Das linke Loch anklicken", "Click the left hole")
    tutorial.close_up(
        (centre[0], centre[1], 8.0),
        110.0,
        "6 mm rund",
        "6 mm, round",
        "Rechts unter „Zum Langloch ziehen“ stehen Länge und Richtung.",
        "On the right under “Pull into a slot” there are length and direction.",
        6.0,
        keep_selection=True,
    )
    tutorial.card(
        "slot_hole",
        [
            (
                "slot_length",
                20.0,
                "Länge: 20 eintippen",
                "Length: type 20",
                "Die Gesamtlänge des Langlochs. Die Breite bleibt die des Lochs: 6 mm.",
                "The overall length of the slot. The width stays that of the hole: 6 mm.",
            ),
            (
                "slot_angle",
                0.0,
                "Richtung: 0 Grad",
                "Direction: 0 degrees",
                "0 Grad heißt entlang der X-Achse — quer zum Teil wären 90.",
                "0 degrees runs along the X axis — across the part would be 90.",
            ),
        ],
        "Übernehmen",
        "Apply",
        "„Zum Langloch ziehen“ ist die Handlung am Knopf. Ein Klick.",
        "“Pull into a slot” is the action on the button. One click.",
        body=body,
        feature=key,
    )
    tutorial.close_up(
        (centre[0], 0.0, 8.0),
        130.0,
        "Aus rund wird lang",
        "From round to slotted",
        "20 mm lang, 6 mm breit: Die Schraube hat 14 mm Spiel zum Verschieben.",
        "20 mm long, 6 mm wide: the screw can move by 14 mm.",
        7.0,
    )
    tutorial.turn(
        "Sauber durch das ganze Teil",
        "Clean through the whole part",
        "Die Enden sind rund, die Wände senkrecht — druckbar ohne Stützen.",
        "Rounded ends, vertical walls — printable without supports.",
        5.0,
        50.0,
    )
    tutorial.shot(
        "slot",
        "Ein Langloch statt des Lochs",
        "A slot instead of the hole",
        "Länge 20 mm, Breite wie das Loch.",
        "Length 20 mm, width as the hole.",
        focus=((centre[0], 0.0, 8.0), 140.0),
    )
    tutorial.add(
        "Doch länger?",
        "Longer after all?",
        "Kein Problem: Der Schritt im Verlauf lässt sich öffnen und ändern.",
        "No problem: the step in the history can be opened and changed.",
        7.0,
    )
    tutorial.edit_step(
        last_op_id(tutorial),
        {"slot_length": 28.0},
        "Länge auf 28 mm ändern",
        "Change the length to 28 mm",
        "Derselbe Schritt, eine andere Zahl. Es entsteht kein zweiter Schritt.",
        "The same step, a different number. No second step is created.",
    )
    tutorial.close_up(
        (centre[0], 0.0, 8.0),
        130.0,
        "28 mm — mehr Spielraum",
        "28 mm — more room",
        "Das zweite, runde Loch bleibt unverändert.",
        "The second, round hole stays unchanged.",
        7.0,
    )
    tutorial.shot(
        "variant",
        "Länger gemacht",
        "Made longer",
        "28 mm statt 20 mm — im Verlauf geändert.",
        "28 mm instead of 20 mm — changed in the history.",
        focus=((centre[0], 0.0, 8.0), 140.0),
    )
    tutorial.history()
    tutorial.shot(
        "undo",
        "Rückgängig: wieder 20 mm",
        "Undo: back to 20 mm",
        "Auch eine Änderung im Verlauf ist rücknehmbar.",
        "A change in the history can be undone as well.",
        focus=((centre[0], 0.0, 8.0), 140.0),
    )
    tutorial.history(redo=True)


def story_edges(tutorial: Tutorial, paths: list[Path]) -> None:
    """Erreichbare Kantengruppen am importierten Netz verrunden und fasen."""
    body = opening(tutorial, paths)[0]
    tutorial.add(
        "Scharfe Kanten",
        "Sharp edges",
        "Die Form passt, aber die Ecken sollen rund werden — direkt an der STL.",
        "The shape is right, but the corners should be rounded — directly on the STL.",
        8.0,
    )
    tutorial.parameter("radius", 3.0, "Radius der Ecken", "Corner radius", minimum=1.0, maximum=4.0)
    tutorial.listed(
        "fillet_edges",
        {"radius": "=@radius", "edges": "vertical"},
        "Radius aus dem Maß, Kanten: senkrecht",
        "Radius from the dimension, edges: vertical",
        "Über „fx“ nimmt das Feld den Namen @radius. "
        "Die Auswahl „Senkrecht“ trifft die vier Ecken.",
        "With “fx” the field takes the name @radius. The “Vertical” choice hits the four corners.",
        bodies=(body,),
        hint_de="Das Teil anklicken, dann rechts in der Liste „Verrunden“ wählen.",
        hint_en="Click the part, then choose “Fillet” in the list on the right.",
    )
    corner = (47.0, 24.5, 6.0)
    tutorial.close_up(
        corner,
        80.0,
        "Runde Ecke, 3 mm",
        "Rounded corner, 3 mm",
        "Aus der scharfen Ecke ist ein Bogen geworden — bei einer STL aus kleinen geraden Stücken.",
        "The sharp corner has become an arc — on an STL made of small straight segments.",
        7.0,
    )
    tutorial.turn(
        "Alle vier Ecken",
        "All four corners",
        "Die Handlung galt der ganzen Gruppe „senkrechte Kanten“ auf einmal.",
        "The action applied to the whole “vertical edges” group at once.",
        6.0,
        70.0,
    )
    tutorial.shot(
        "rounded",
        "Ecken abgerundet",
        "Corners rounded",
        "Direkt an der STL, ohne Neuzeichnen.",
        "Directly on the STL, without redrawing.",
        focus=(corner, 90.0),
    )
    tutorial.change_parameter("radius", 4.0, "Radius auf 4 mm", "Radius to 4 mm")
    tutorial.close_up(
        corner,
        80.0,
        "4 mm statt 3 mm",
        "4 mm instead of 3 mm",
        "Eine Zahl links geändert — die Rundung folgt an allen vier Ecken.",
        "One number changed on the left — the rounding follows at all four corners.",
        7.0,
    )
    tutorial.shot(
        "radius-variant",
        "Radius folgt der Zahl",
        "Radius follows the number",
        "Ein Maß, vier Ecken.",
        "One dimension, four corners.",
        focus=(corner, 90.0),
    )
    tutorial.listed(
        "chamfer_edges",
        {"distance": 0.8, "edges": "top"},
        "0,8 mm Fase, Kanten: oben",
        "0.8 mm chamfer, edges: top",
        "Die obere Kante wird unter 45 Grad gebrochen. Die Unterseite bleibt flach zum Drucken.",
        "The upper edge is broken at 45 degrees. The underside stays flat for printing.",
        bodies=(body,),
        hint_de="Wieder das Teil anklicken, rechts „Fase anbringen“.",
        hint_en="Click the part again, choose “Add a chamfer” on the right.",
    )
    tutorial.close_up(
        (30.0, 27.5, 8.0),
        60.0,
        "Die Fase an der Oberkante",
        "The chamfer on the upper edge",
        "Klein, aber sichtbar: Die Kante ist gebrochen, kein scharfer Grat mehr.",
        "Small but visible: the edge is broken, no sharp burr anymore.",
        7.0,
    )
    tutorial.turn(
        "Rundung und Fase zusammen",
        "Rounding and chamfer together",
        "Zwei getrennte Schritte im Verlauf — jeder für sich rücknehmbar.",
        "Two separate steps in the history — each can be undone on its own.",
        5.0,
        45.0,
    )
    tutorial.shot(
        "chamfer",
        "Fase an der Oberkante",
        "Chamfer on the upper edge",
        "Rundung und Fase sind getrennte Schritte.",
        "Rounding and chamfering are separate steps.",
        focus=((30.0, 27.5, 8.0), 75.0),
    )
    tutorial.history()
    tutorial.shot(
        "undo",
        "Nur die Fase zurück",
        "Only the chamfer undone",
        "Die runden Ecken bleiben.",
        "The rounded corners remain.",
        focus=((30.0, 27.5, 8.0), 75.0),
    )
    tutorial.history(redo=True)


def save_variant(tutorial: Tutorial, name: str) -> None:
    """Beigelegte Geometrievarianten außerhalb der gezeigten Bedienfolge bewahren."""
    from app.core.geom.mesh import as_mesh_data

    for index, body in enumerate(tutorial.session.last_result.scene.objects.values(), 1):
        as_mesh_data(body.mesh).raw.export(tutorial.folder / f"{name}-{index}.stl")
    write_json(tutorial.folder / f"{name}.json", geometry(tutorial.session.last_result, name))


def story_variants(tutorial: Tutorial, paths: list[Path]) -> None:
    """Zwei Lochvarianten mit benannten Maßen: erst die Zahl, dann der Name dafür."""
    body = opening(tutorial, paths)[0]
    tutorial.add(
        "Das Ziel",
        "The goal",
        "Beide Löcher sollen an zwei Zahlen hängen: Durchmesser und Abstand. "
        "Dann ist jede Variante ein Tippen.",
        "Both holes should depend on two numbers: diameter and spacing. "
        "Then every variant is one keystroke.",
        9.0,
    )
    tutorial.parameter(
        "diameter",
        7.0,
        "Durchmesser beider Löcher",
        "Diameter of both holes",
        minimum=5.0,
        maximum=12.0,
    )
    tutorial.parameter(
        "spacing", 56.0, "Abstand der Löcher", "Spacing of the holes", minimum=35.0, maximum=70.0
    )
    for left in (True, False):
        key, feature = hole_at(tutorial, body, left=left)
        centre = feature.params["centre"]
        tutorial.select_feature(
            body,
            key,
            "Das linke Loch anklicken" if left else "Das rechte Loch",
            "Click the left hole" if left else "The right hole",
        )
        tutorial.card(
            "resize_hole",
            [
                (
                    "diameter",
                    7.0,
                    "Erst einmal als Zahl: 7",
                    "First as a plain number: 7",
                    "Die Karte nimmt Zahlen. Den Namen bekommt der Schritt gleich im Verlauf.",
                    "The card takes numbers. The step gets its name in the history next.",
                ),
            ],
            "Übernehmen",
            "Apply",
            "„Bohrung ändern“ mit 7 mm. Position bleibt vorerst, wie sie ist.",
            "“Change hole” with 7 mm. The position stays as it is for now.",
            body=body,
            feature=key,
        )
        tutorial.edit_step(
            last_op_id(tutorial),
            {"diameter": "=@diameter", "x": "=-@spacing/2" if left else "=@spacing/2"},
            "Zahlen durch Namen ersetzen",
            "Replace the numbers with names",
            "„fx“ am Feld: Durchmesser = @diameter, X = halber Abstand mit Vorzeichen.",
            "“fx” at the field: diameter = @diameter, X = half the spacing with its sign.",
        )
        tutorial.close_up(
            (-28.0 if left else 28.0, centre[1], 8.0),
            120.0,
            "Dieses Loch hört auf die Namen",
            "This hole follows the names",
            "7 mm aus @diameter, Position aus @spacing. Die Zahl steht nur noch links.",
            "7 mm from @diameter, position from @spacing. The number lives only on the left now.",
            6.0,
        )
    save_variant(tutorial, "variant-a")
    tutorial.overview(
        "Variante A: 7 mm, 56 mm Abstand",
        "Variant A: 7 mm, 56 mm spacing",
        "Beide Löcher hängen an denselben zwei Zahlen. Jetzt kommt der Trick.",
        "Both holes depend on the same two numbers. Now for the trick.",
        seconds=6.0,
        degrees=40.0,
    )
    tutorial.shot(
        "variant-a",
        "Variante A: 7 mm / 56 mm",
        "Variant A: 7 mm / 56 mm",
        "Beide Löcher hängen an zwei Namen.",
        "Both holes depend on two names.",
    )
    tutorial.change_parameter("spacing", 64.0, "Abstand auf 64 mm", "Spacing to 64 mm")
    tutorial.overview(
        "Beide Löcher rücken nach außen",
        "Both holes move outwards",
        "Eine Zahl geändert, zwei Löcher folgen — symmetrisch, die Mitte bleibt.",
        "One number changed, two holes follow — symmetrically, the centre stays.",
        seconds=6.0,
        degrees=40.0,
    )
    tutorial.shot(
        "spacing",
        "64 mm Abstand",
        "64 mm spacing",
        "Links und rechts folgen gemeinsam.",
        "Left and right follow together.",
    )
    tutorial.change_parameter("diameter", 9.0, "Durchmesser auf 9 mm", "Diameter to 9 mm")
    save_variant(tutorial, "variant-b")
    tutorial.close_up(
        (32.0, 0.0, 8.0),
        120.0,
        "Variante B: 9 mm, 64 mm",
        "Variant B: 9 mm, 64 mm",
        "Zwei Zahlen getippt, fertig ist die zweite Ausführung derselben STL.",
        "Two numbers typed — the second version of the same STL is done.",
        7.0,
    )
    tutorial.turn(
        "Der Rand bleibt, wo er ist",
        "The edge stays where it is",
        "Das Teil ist noch 100 x 55 x 8 mm — nur die Löcher sind anders.",
        "The part is still 100 x 55 x 8 mm — only the holes differ.",
        5.0,
        50.0,
    )
    tutorial.shot(
        "variant-b",
        "Variante B: 9 mm / 64 mm",
        "Variant B: 9 mm / 64 mm",
        "Zwei Zahlen, zweite Ausführung.",
        "Two numbers, second version.",
    )
    tutorial.history()
    tutorial.shot(
        "undo",
        "Rückgängig: wieder 7 mm",
        "Undo: back to 7 mm",
        "Der Abstand bleibt bei 64, der Durchmesser springt zurück.",
        "Spacing stays at 64, the diameter jumps back.",
    )
    tutorial.history(redo=True)


def face_facing(tutorial: Tutorial, body: str, direction: float) -> str:
    """Eine reale ebene Verbindungsfläche aus Richtung und Lage bestimmen."""
    features = tutorial.session.last_result.scene.objects[body].features
    candidates = [
        (key, feature)
        for key, feature in features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[0] * direction > 0.99
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Verbindungsfläche an {body} ist nicht eindeutig: {candidates}")
    return str(candidates[0][0])


def story_counterparts(tutorial: Tutorial, paths: list[Path]) -> None:
    """Zwei Importkörper mit dem echten Paar-Dialog verbinden und den Fügeweg prüfen."""
    first, second = opening(tutorial, paths)
    tutorial.add(
        "Zwei Teile, die zusammengehören",
        "Two parts that belong together",
        "Beide sollen sich zusammenstecken lassen. "
        "Erst etwas Abstand, damit man beide Flächen sieht.",
        "They should plug together. First some distance, so both faces are visible.",
        9.0,
    )
    tutorial.move(
        first,
        -20.0,
        "X = -20 und Enter",
        "X = -20 and Enter",
        "Das linke Teil rückt 20 mm nach links. Enter übernimmt den Wert als Schritt.",
        "The left part moves 20 mm to the left. Enter applies the value as a step.",
    )
    tutorial.shots.clear()
    tutorial.overview(
        "Zwei importierte STL-Teile",
        "Two imported STL parts",
        "Die Seitenflächen stehen sich gegenüber — hier kommt die Verbindung hin.",
        "The side faces oppose each other — this is where the connection goes.",
        seconds=6.0,
        degrees=45.0,
    )
    tutorial.shot(
        "source-separated",
        "Zwei STL-Teile",
        "Two STL parts",
        "Die Seitenflächen stehen sich gegenüber.",
        "The side faces oppose each other.",
    )
    first_face = face_facing(tutorial, first, 1.0)
    second_face = face_facing(tutorial, second, -1.0)
    tutorial.select_feature(
        first,
        first_face,
        "Erste Fläche anklicken: hier kommt der Stift hin",
        "Click the first face: the pin goes here",
    )
    tutorial.window.object_tree.select_features([(first, first_face), (second, second_face)])
    tutorial.settle(15)
    tutorial.add(
        "Zweite Fläche mit Strg dazu",
        "Add the second face with Ctrl",
        "Die Reihenfolge entscheidet: erstes Teil bekommt den Stift, zweites das Loch.",
        "The order decides: the first part gets the pin, the second the hole.",
        9.0,
        target=tutorial.window.object_tree,
    )
    tutorial.shot(
        "targets",
        "Zwei Flächen gewählt",
        "Two faces selected",
        "Die gewählten Flächen bestimmen die Verbindung.",
        "The selected faces determine the connection.",
    )
    tutorial.window.object_tree.select_features([(first, first_face), (second, second_face)])
    tutorial.settle(12)
    action = tutorial.window.counterpart_action
    if not action.isEnabled():
        raise RuntimeError("Gegenstücke ist trotz zweier geeigneter Flächen nicht freigegeben.")
    lf._show_action_path(
        tutorial.recorder,
        action,
        words(
            "„Gegenstücke setzen“ macht aus zwei Flächen Stift und Loch — in einem Dialog.",
            "“Place counterparts” turns two faces into pin and hole — in one dialog.",
        ),
    )
    before = len(tutorial.session.project.document.ops)

    def fill(dialog: Any) -> None:
        from PySide6.QtCore import QPoint

        dialog.pairs.setCurrentIndex(dialog.pairs.findData("dowel"))
        for name, value in {"diameter": 6.0, "length": 8.0, "play": 0.2, "chamfer": 0.5}.items():
            set_field(dialog._fields[name], value)
        place_dialog = lf._place_dialog

        def place_counterpart(window: Any, opened: Any) -> None:
            """Den laufenden exec()-Dialog nur verschieben, ohne seine Modalität zu ändern."""
            if opened is not dialog:
                place_dialog(window, opened)
                return
            opened.adjustSize()
            origin = window.mapToGlobal(QPoint(0, 0))
            x = origin.x() + max(20, (window.width() - opened.width()) // 2)
            y = origin.y() + 175
            maximum_y = origin.y() + window.height() - opened.height() - 25
            opened.move(x, max(origin.y() + 165, min(y, maximum_y)))

        # Der alte Aufnahmehelper setzt setModal(False). Im bereits laufenden
        # exec()-Dialog bleiben Modalität und Fensterflags unverändert.
        lf._place_dialog = place_counterpart
        try:
            tutorial.add(
                "6 mm Stift, 8 mm lang, 0,2 mm Spiel",
                "6 mm pin, 8 mm long, 0.2 mm clearance",
                "Das Spiel gilt für das Paar: Der Stift wird 6 mm, das Loch 6,2 mm. "
                "Einmal eingeben.",
                "The clearance applies to the pair: the pin gets 6 mm, the hole 6.2 mm. "
                "Enter it once.",
                13.0,
                dialog=dialog,
                target=lf._button(dialog),
            )
        finally:
            lf._place_dialog = place_dialog
        tutorial.detail_shot(dialog, "counterpart-dialog")
        lf._button(dialog).click()

    tutorial.modal(action.trigger, fill)
    tutorial.checked("Gegenstücke als Paar")
    if len(tutorial.session.project.document.ops) - before != 2:
        raise RuntimeError("Das Gegenstückpaar hat nicht genau zwei Bausteinschritte erzeugt.")
    lf._fit(tutorial.window, tutorial.recorder.app)
    tutorial.add(
        "Stift und Loch in einem Schritt",
        "Pin and hole in one step",
        "Beide Hälften gehören zusammen — ein Rückgängig nimmt das Paar zurück.",
        "Both halves belong together — one undo removes the pair.",
        8.0,
    )
    pin_point = (-6.0, 0.0, 12.0)
    tutorial.close_up(
        pin_point,
        90.0,
        "Der Stift am linken Teil",
        "The pin on the left part",
        "6 mm dick, 8 mm lang, mit einer kleinen Fase vorn zum leichteren Einstecken.",
        "6 mm thick, 8 mm long, with a small chamfer at the tip for easier insertion.",
        7.0,
    )
    tutorial.shot(
        "pair",
        "Ein passendes Paar",
        "A matching pair",
        "Stift und Loch teilen dieselben Maße.",
        "Pin and hole share the same dimensions.",
        focus=(pin_point, 100.0),
    )
    tutorial.turn(
        "Auf die andere Seite drehen",
        "Turn to the other side",
        "Gegenüber sitzt das passende Loch — mit 0,2 mm mehr Durchmesser.",
        "Opposite sits the matching hole — with 0.2 mm more diameter.",
        10.0,
        180.0,
    )
    hole_point = (10.0, 0.0, 12.0)
    tutorial.close_up(
        hole_point,
        90.0,
        "Das Loch am rechten Teil",
        "The hole in the right part",
        "6,2 mm, gleiche Höhe, gleiche Lage — es kann gar nicht daneben sitzen.",
        "6.2 mm, same height, same position — it cannot be off.",
        7.0,
    )
    tutorial.shot(
        "counter-hole",
        "Auch das Loch passt",
        "The hole fits as well",
        "Die Gegenseite der Verbindung.",
        "The other half of the connection.",
        focus=(hole_point, 100.0),
        mirror=True,
    )
    tutorial.history()
    tutorial.shot(
        "undo",
        "Ein Rückgängig für beide",
        "One undo for both",
        "Stift und Loch verschwinden zusammen.",
        "Pin and hole disappear together.",
    )
    tutorial.history(redo=True)
    tutorial.move(
        first,
        20.0,
        "X = 20: zusammenschieben",
        "X = 20: push together",
        "Das linke Teil rückt zurück — der Stift steckt jetzt im Loch.",
        "The left part moves back — the pin now sits in the hole.",
    )
    tutorial.close_up(
        (0.0, 0.0, 12.0),
        110.0,
        "Zusammengesteckt",
        "Plugged together",
        "Kein Spalt, keine Überschneidung. "
        "Ob es so auch beim Einstecken klappt, prüft der nächste Schritt.",
        "No gap, no overlap. Whether it also works while inserting is checked next.",
        7.0,
    )
    tutorial.shot(
        "assembled",
        "Zusammengesteckt",
        "Plugged together",
        "Jetzt lässt sich der Weg dorthin prüfen.",
        "Now the path into this position can be checked.",
    )
    tutorial.listed(
        "check_join_path",
        {"axis": "x", "distance": 24.0, "steps": 24, "reverse": False},
        "Fügeweg: 24 mm entlang X",
        "Insertion path: 24 mm along X",
        "Solidon3D schiebt das erste Teil Schritt für Schritt hinein und sucht Kollisionen.",
        "Solidon3D moves the first part in step by step and looks for collisions.",
        bodies=(first, second),
        hint_de="Beide Teile wählen, rechts „Fügeweg prüfen“.",
        hint_en="Select both parts, choose “Check insertion path” on the right.",
    )
    # Seit RM-167 sagt der Bericht den freien Weg selbst (Befund
    # ``join.clear``); die Aufnahmen vom 13.09.2026 tragen noch den Satz
    # „Der Prüfbericht bleibt leer" und bleiben so.
    tutorial.add(
        "Der Prüfbericht sagt es",
        "The report says so",
        "Rechts oben steht der Befund: Der Fügeweg ist frei, 24 mm entlang X, keine "
        "Überschneidung. Beim Drucken zählt dann noch das Material.",
        "The finding is at the top right: the insertion path is clear, 24 mm along X, no overlap. "
        "When printing, the material still matters.",
        9.0,
        target=tutorial.window.report,
    )
    tutorial.history()
    tutorial.history()
    tutorial.overview(
        "Wieder getrennt",
        "Separated again",
        "Die Verbindung bleibt im Projekt — die Teile liegen getrennt zum Drucken.",
        "The connection stays in the project — the parts lie apart for printing.",
        seconds=6.0,
        degrees=40.0,
    )
    tutorial.shot(
        "separated",
        "Getrennt, aber verbunden",
        "Apart, yet connected",
        "Stift und Loch bleiben — zum Drucken liegen die Teile einzeln.",
        "Pin and hole remain — for printing the parts lie separately.",
    )


def run_story(tutorial: Tutorial, paths: list[Path]) -> None:
    """Genau ein Drehbuch im aktuellen Prozess ausführen."""
    if tutorial.story == "bohrung-anpassen":
        story_holes(tutorial, paths)
    elif tutorial.story == "langloch":
        story_slot(tutorial, paths)
    elif tutorial.story == "stl-kanten":
        story_edges(tutorial, paths)
    elif tutorial.story == "stl-varianten":
        story_variants(tutorial, paths)
    elif tutorial.story == "gegenstuecke":
        story_counterparts(tutorial, paths)
    else:
        raise RuntimeError(f"Drehbuch noch nicht bereit: {tutorial.story}")
    tutorial.finish()


def run_recipe(tutorial: Tutorial, recipe: dict[str, Any], recipe_path: Path) -> None:
    """Ein redaktionelles Rezept über die vorhandenen echten Kundenwege aufnehmen.

    Die JSON-Datei enthält lokale Quellen, Werte und benannte Aufnahmehandlungen,
    niemals auszuführenden Quelltext. Jeder Zustand bleibt an seine Rohbilder und
    die geprüften Ergebnisnetze gebunden.
    """
    import hashlib

    sources = tutorial.folder / "sources"
    sources.mkdir(exist_ok=True)
    bodies: list[str] = []
    source_proof = []
    scenes = tutorial.first_steps(recipe["setup"]) if recipe.get("setup") else []
    for index, entry in enumerate(recipe["sources"], 1):
        source = (recipe_path.parent / entry["path"]).resolve()
        if not source.is_file() or not entry.get("rights"):
            raise ValueError(f"Quelle oder Rechtebeleg fehlt; Rezept prüfen: {source.name}")
        target = sources / f"{index:02d}-{source.name}"
        shutil.copy2(source, target)
        bodies.append(tutorial.import_file(target, unit=entry.get("unit")))
        source_proof.append(
            {
                "file": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "rights": entry["rights"],
            }
        )
    if "import" in recipe[LANGUAGE]:
        scenes.extend(tutorial.import_scenes)
    for step in recipe["steps"]:
        captured_scenes = None
        action_bounds: dict[str, int] = {}
        start = len(tutorial.recorder.slides)
        event_start = len(tutorial.recorder.events)
        text = step[LANGUAGE]
        titles = (step["de"]["title"], step["en"]["title"])
        details = (step["de"]["detail"], step["en"]["detail"])
        action = step["action"]
        body = bodies[int(step.get("body", 0))] if bodies else None
        if action == "overview":
            tutorial.overview(
                *titles,
                *details,
                seconds=step.get("seconds", 7.0),
                degrees=step.get("degrees", 40.0),
                start_degrees=step.get("start_degrees", 0.0),
            )
        elif action == "view":
            lf._view(
                tutorial.window, tutorial.recorder.app, step["direction"], step.get("zoom", 1.0)
            )
            tutorial.add(*titles, *details, step.get("seconds", 7.0))
        elif action == "close_up":
            tutorial.close_up(
                tuple(step["point"]),
                step["distance"],
                *titles,
                *details,
                seconds=step.get("seconds", 7.0),
                steep=step.get("steep", 0.45),
                mirror=step.get("mirror", False),
            )
        elif action == "feature":
            if body is None:
                raise ValueError("Die Merkmalauswahl benötigt einen importierten Körper.")
            current = tutorial.session.last_result.scene.objects[body]
            feature_id = step["feature"]
            if feature_id not in current.features:
                raise ValueError(f"Merkmal {feature_id} fehlt; Quellenaufnahme prüfen.")
            action_bounds = tutorial.select_feature(body, feature_id, *titles)
        elif action == "card":
            if body is None:
                raise ValueError("Die Maßbearbeitung benötigt einen importierten Körper.")
            values = [
                (
                    value["field"],
                    value["value"],
                    value["de"]["title"],
                    value["en"]["title"],
                    value["de"]["detail"],
                    value["en"]["detail"],
                )
                for value in step["values"]
            ]
            tutorial.card(step["op"], values, *titles, *details, body=body, feature=step["feature"])
        elif action == "drag_slot":
            if body is None:
                raise ValueError("Das Langloch benötigt einen importierten Körper.")
            captured_scenes = tutorial.drag_slot(step, body)
        elif action == "operation":
            chosen_bodies = (
                tuple(tutorial.session.last_result.scene.objects)
                if step.get("all_bodies")
                else [bodies[index] for index in step.get("bodies", [0])]
            )
            if "stages" in step:
                captured_scenes = tutorial.operation_scenes(step, chosen_bodies)
            else:
                tutorial.listed(
                    step["op"],
                    step["values"],
                    *titles,
                    *details,
                    bodies=chosen_bodies,
                    hint_de=step["de"]["detail"],
                    hint_en=step["en"]["detail"],
                )
        elif action == "edit":
            tutorial.edit_step(last_op_id(tutorial), step["values"], *titles, *details)
        elif action == "parameter":
            tutorial.parameter(
                step[LANGUAGE]["name"],
                step["value"],
                *titles,
                minimum=step["minimum"],
                maximum=step["maximum"],
            )
        elif action == "change_parameter":
            tutorial.change_parameter(step[LANGUAGE]["name"], step["value"], *titles)
        elif action == "undo":
            action_bounds = tutorial.history()
        elif action == "redo":
            action_bounds = tutorial.history(redo=True)
        elif action == "move":
            if body is None:
                raise ValueError("Das Verschieben benötigt einen importierten Körper.")
            tutorial.move(body, step["dx"], *titles, *details)
        elif action == "print_settings":
            captured_scenes = tutorial.print_settings(step)
        elif action == "history_toggle":
            action_bounds = tutorial.toggle_step(last_op_id(tutorial), titles, details)
        elif action == "ai":
            from tools.workshop_ai_capture import capture_step as capture_ai_step

            captured_scenes = capture_ai_step(tutorial, step)
        elif action == "inventory":
            from tools.workshop_inventory_capture import capture_step as capture_inventory_step

            captured_scenes = capture_inventory_step(tutorial, step)
        elif action == "part_catalog":
            from tools.workshop_part_capture import capture_step as capture_part_step

            if body is None:
                raise ValueError("Der Baustein benötigt einen importierten Körper.")
            captured_scenes = capture_part_step(tutorial, step, body)
        elif action == "short_interaction":
            from tools.workshop_short_capture import capture_step as capture_short_step

            if body is None:
                raise ValueError("Die Bedienfolge benötigt einen importierten Körper.")
            capture_short_step(tutorial, step, body)
        else:
            raise ValueError(f"Unbekannte Aufnahmehandlung; Rezept prüfen: {action}")
        scene = {
            "key": step["key"],
            **text,
            "action": action,
            "first_slide": start,
            "last_slide": len(tutorial.recorder.slides),
            "events": tutorial.recorder.events[event_start:],
            "short": bool(step.get("short", False)),
            "focus": step.get("focus"),
            "model_crop": step.get("model_crop"),
            "minimum_seconds": step.get("minimum_seconds", 0.0),
            **action_bounds,
        }
        if captured_scenes is None:
            scenes.append(scene)
        else:
            scenes.extend(captured_scenes)
        if action != "inventory":
            tutorial.shot(step["key"], *titles, *details, cover=bool(step.get("cover")))
    tutorial.finish(minimum_seconds=0.0)
    scenes.extend(tutorial.finish_scenes)
    if any(step["action"] == "ai" for step in recipe["steps"]):
        from tools.workshop_ai_capture import finalize_evidence

        finalize_evidence(tutorial)
    write_json(
        tutorial.folder / "editorial.json",
        {
            "schema": 1,
            "story": recipe["id"],
            "language": LANGUAGE,
            "title": recipe[LANGUAGE]["title"],
            "series_label": recipe[LANGUAGE].get("series_label"),
            "hook": recipe[LANGUAGE]["hook"],
            "short_hook": recipe[LANGUAGE]["short_hook"],
            "thumbnail": recipe[LANGUAGE]["thumbnail"],
            "music": recipe["music"],
            "captured_at": datetime.now(UTC).isoformat(),
            "source_files": source_proof,
            "scenes": scenes,
            "hero": recipe["hero"],
            "redactions": tutorial.redactions,
        },
    )


def main() -> int:
    """Aufnahmeprofil zuerst isolieren, danach Anwendung und Recorder laden."""
    global lf, LANGUAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", nargs="?", choices=STORIES)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--language", choices=("de", "en"), default="de")
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--encode-only", action="store_true")
    parser.add_argument("--inputs-only", action="store_true")
    parser.add_argument("--screen-model")
    parser.add_argument("--screen-serial")
    parser.add_argument("--native-resolution", action="store_true")
    args = parser.parse_args()
    if args.native_resolution and (not args.recipe or not args.capture_only):
        parser.error("Native Bildschirmgröße benötigt --recipe und --capture-only.")
    recipe = json.loads(args.recipe.read_text("utf-8")) if args.recipe else None
    if recipe:
        args.story = recipe["id"]
        STORIES[args.story] = (recipe["de"]["title"], recipe["en"]["title"])
    elif args.story is None:
        parser.error("Ein Thema oder --recipe ist erforderlich.")
    if (args.output / "pause-production").exists():
        print("Produktionspause: zuerst den laufenden App-Prüflauf abschließen.", flush=True)
        return 75
    LANGUAGE = args.language
    folder = args.output.resolve() / args.story / LANGUAGE
    folder.mkdir(parents=True, exist_ok=True)
    profile = folder / "profile"
    for name, child in (
        ("APPDATA", "roaming"),
        ("LOCALAPPDATA", "local"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        target = profile / child
        target.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(target)
    os.environ.pop("QT_QPA_PLATFORM", None)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.inputs_only:
        print([str(path) for path in make_inputs(folder / "sources", args.story)], flush=True)
        return 0
    from tools import make_longform_video

    lf = make_longform_video
    lf._captions = (
        json.loads(Path(lf.__file__).with_name("longform_video_en.json").read_text("utf-8"))
        if LANGUAGE == "en"
        else {}
    )
    lf._captions["Dieser sichtbare Menüpunkt öffnet den nächsten gezeigten Dialog."] = words(
        "Jetzt wird genau diese Funktion gewählt.", "Select this function now."
    )
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    lf.install_catalog(LANGUAGE, lf.read_catalog(LANGUAGE))
    lf.set_language(LANGUAGE)
    lf.install_qt_translations(app, LANGUAGE)
    lf.apply_theme(app, "dark")
    if args.encode_only:
        capture = json.loads((folder / "capture.json").read_text("utf-8"))
        if not capture["complete"]:
            raise RuntimeError("Die Aufnahme ist nicht vollständig.")
        recorder = lf.Recorder(app, None, folder / "frames", capture["chapter"])
        recorder.slides = [
            lf.Slide(folder / entry["path"], entry["seconds"]) for entry in capture["slides"]
        ]
        recorder.events = json.loads((folder / f"{args.story}.timeline.json").read_text("utf-8"))
    else:
        write_json(folder / "capture.json", {"complete": False, "story": args.story})
        for stale in folder.glob("*.p3d"):
            # Ein neuer Take speichert unter freiem Namen, wie der gezeigte Erstaufruf —
            # und der Dateidialog im Film zeigt keine Reste älterer Takes.
            stale.unlink()
        for stale in (*folder.glob("*.stl"), *folder.glob("variant-*.json")):
            stale.unlink()
        lf.video_base.require_screen(app)
        paths = [] if recipe else make_inputs(folder / "sources", args.story)
        wanted_screen = None
        if args.screen_model or args.screen_serial:
            matching = [
                screen
                for screen in app.screens()
                if (not args.screen_model or screen.model() == args.screen_model)
                and (not args.screen_serial or screen.serialNumber() == args.screen_serial)
            ]
            if len(matching) != 1:
                raise RuntimeError(
                    "Der Aufnahmebildschirm ist nicht eindeutig; Modell und Seriennummer prüfen."
                )
            wanted_screen = matching[0]
        tutorial = Tutorial(
            app,
            folder,
            args.story,
            raw=recipe is not None,
            screen=wanted_screen,
            native_resolution=args.native_resolution,
        )
        actual_screen = tutorial.window.screen()
        if wanted_screen is not None and actual_screen is not wanted_screen:
            raise RuntimeError(
                "Das Aufnahmefenster steht auf dem falschen Monitor; Position prüfen: "
                f"{actual_screen.model()} / {actual_screen.serialNumber()}."
            )
        area = actual_screen.geometry()
        write_json(
            folder / "screen-evidence.json",
            {
                "model": actual_screen.model(),
                "serial": actual_screen.serialNumber(),
                "name": actual_screen.name(),
                "geometry": [area.x(), area.y(), area.width(), area.height()],
                "device_pixel_ratio": actual_screen.devicePixelRatio(),
                "window_position": [tutorial.window.x(), tutorial.window.y()],
                "window_size": [tutorial.window.width(), tutorial.window.height()],
                "capture_size": tutorial.recorder.frame_size,
                "native_resolution": args.native_resolution,
            },
        )
        try:
            if recipe:
                run_recipe(tutorial, recipe, args.recipe.resolve())
            else:
                run_story(tutorial, paths)
            recorder = tutorial.recorder
        except BaseException:
            import traceback

            tutorial.window.screen().grabWindow(tutorial.window.winId()).save(
                str(folder / "failed-state.png")
            )
            (folder / "failed-run.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            lf._finish_video(tutorial.session, tutorial.window)
    if not args.capture_only:
        if recipe:
            raise ValueError(
                "Rohaufnahme fertig; mit workshop_edit.py den gesprochenen Schnitt erzeugen."
            )
        recorder.chapter = MUSIC_STYLES[args.story]
        lf._encode(recorder, folder / f"solidon3d-{args.story}-{LANGUAGE}.mp4")
    print(f"Fertig: {folder} ({recorder.seconds:.1f} Sekunden)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
