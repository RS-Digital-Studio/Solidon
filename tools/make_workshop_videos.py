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
import sys
from collections.abc import Sequence
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

    def __init__(self, app: Any, folder: Path, story: str) -> None:
        self.folder, self.story = folder, story
        self.title = words(*STORIES[story])
        self.session, self.window, self.recorder = lf._begin_video(
            app, self.title, folder / "frames"
        )
        self.shots: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []
        self._pending_detail: str | None = None
        self.folder.joinpath("shots").mkdir(parents=True, exist_ok=True)

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
        renderer.render()
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
    ) -> None:
        """Eine ruhige Kamerafahrt um den aktuellen Blickpunkt — ohne neu einzupassen."""
        recorder = self.recorder
        viewport = self.window.viewport
        renderer = viewport.renderer
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
        start = math.atan2(offset_y, offset_x)
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
            renderer.render()
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
    ) -> None:
        """Das ganze Teil einpassen und einmal kurz drehen."""
        lf._fit(self.window, self.recorder.app)
        self.turn(title_de, title_en, detail_de, detail_en, seconds, degrees)

    # --- Dialoge --------------------------------------------------------------

    def modal(self, action: Any, fill: Any) -> None:
        """Einen wirklichen modalen Dialog innerhalb seiner Ereignisschleife bedienen."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog

        failures: list[BaseException] = []

        def visit() -> None:
            dialog = QApplication.activeModalWidget()
            try:
                if dialog is None:
                    raise RuntimeError("Die echte Aktion hat keinen modalen Dialog geöffnet.")
                fill(dialog)
            except BaseException as error:
                failures.append(error)
                if isinstance(dialog, QDialog):
                    dialog.reject()

        QTimer.singleShot(350, visit)
        action()
        if failures:
            raise failures[0]

    def file_dialog(self, action: Any, path: Path, *, save: bool = False) -> None:
        """Den durch die App geöffneten Dateidialog auswählen und bestätigen."""
        from PySide6.QtWidgets import QDialogButtonBox, QFileDialog, QLineEdit

        def fill(dialog: Any) -> None:
            if not isinstance(dialog, QFileDialog):
                raise RuntimeError(f"Dateidialog erwartet, erhalten: {type(dialog).__name__}")
            dialog.setDirectory(str(path.parent))
            self.settle(12)
            filename = dialog.findChild(QLineEdit, "fileNameEdit")
            if filename is None:
                raise RuntimeError("Das Dateinamensfeld des geöffneten Dialogs fehlt.")
            filename.setFocus()
            filename.setText(str(path.resolve()))
            self.settle(12)
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
            self.add(
                "Datei speichern"
                if save
                else "Projektdatei auswählen"
                if project_file
                else "Die STL-Datei auswählen",
                "Save the file"
                if save
                else "Select the project file"
                if project_file
                else "Select the STL file",
                "Das Projekt bewahrt alle Bearbeitungsschritte."
                if save or project_file
                else "Die STL enthält nur die Form — keine Maße, keine Schritte. "
                "Die kommen jetzt dazu.",
                "The project keeps every editing step."
                if save or project_file
                else "The STL contains only the shape — no dimensions, no steps. Those come next.",
                8.0,
                dialog=dialog,
                target=button,
            )
            button.click()

        self.modal(action, fill)

    def import_file(self, path: Path) -> str:
        """Der Film benutzt den echten Dateimenüeintrag, einschließlich Dateiöffnung."""
        before = set(self.session.last_result.scene.objects)
        lf._show_action_path(
            self.recorder,
            self.window.import_action,
            words(
                "Datei → Modell einfügen öffnet die Dateiauswahl.",
                "File → Insert model opens the file chooser.",
            ),
        )
        self.file_dialog(self.window.import_action.trigger, path)
        self.checked("STL-Import")
        lf._fit(self.window, self.recorder.app)
        added = set(self.session.last_result.scene.objects) - before
        if len(added) != 1:
            raise RuntimeError(f"Import sollte genau einen Körper hinzufügen: {added}")
        return str(added.pop())

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

    def select_feature(self, body: str, feature: str, title_de: str, title_en: str) -> None:
        """Die echte Merkmalszeile sichtbar auswählen, wie ein Klick im Objektbaum."""
        # Nach einer Nahaufnahme erst wieder das ganze Teil zeigen — der Klick gilt dem Überblick.
        lf._fit(self.window, self.recorder.app)
        self.window.object_tree.select_feature(body, feature)
        self.settle(12)
        self.add(
            title_de,
            title_en,
            "Im Objektbaum links oder direkt im Bild anklicken. Rechts stehen die Maße dazu.",
            "Click it in the object tree on the left or directly in the view. "
            "Its dimensions appear on the right.",
            8.0,
            target=self.window.feature_panel,
        )

    # --- Die Kundenwege -----------------------------------------------------------

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
        self.detail_shot(panel, "card")
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
        raw = self.recorder.app.primaryScreen().grabWindow(dialog.winId())
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
        if button is None or not button.isVisible() or not button.isEnabled():
            raise RuntimeError(f"Die Handlungsliste bietet {op} für diese Auswahl nicht an.")
        panel.scroller.ensureWidgetVisible(button, 40, 80)
        self.settle(10)
        before = len(self.session.project.document.ops)
        self.add(
            f"Rechts: „{button.text()}“",
            f"On the right: “{button.text()}”",
            hint_de,
            hint_en,
            7.0,
            target=button,
        )
        button.click()
        self.settle(15)
        dialog = self.window._op_dialog
        if dialog is None:
            raise RuntimeError(f"{op}: der Knopf hat keinen Dialog geöffnet.")
        self.dialog_values(dialog, values)
        self.confirm_dialog(
            dialog, title_de, title_en, detail_de, detail_en, values, before, new_step=True
        )

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

    def history(self, redo: bool = False) -> None:
        """Tatsächliche Menüaktion, danach überprüftes Ergebnis."""
        action = self.window.redo_action if redo else self.window.undo_action
        lf._show_action_path(
            self.recorder,
            action,
            words(
                "Rückgängig nimmt genau den letzten Schritt zurück — auch Strg+Z tut das.",
                "Undo reverses exactly the last step — Ctrl+Z does the same.",
            ),
        )
        if not action.isEnabled():
            raise RuntimeError("Die erwartete Verlaufshandlung ist nicht freigegeben.")
        action.trigger()
        self.checked("Wiederholen" if redo else "Rücknahme")
        lf._fit(self.window, self.recorder.app)
        self.add(
            "Wiederhergestellt" if redo else "Zurückgenommen",
            "Restored" if redo else "Undone",
            "Das Teil wird aus den verbleibenden Schritten neu berechnet — nichts geht verloren.",
            "The part is rebuilt from the remaining steps — nothing is lost.",
            8.0,
        )

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
            self.window.resize(1120, 1120)
            lf.video_base.settle_resize(self.window, self.recorder.app)
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
                renderer.render()
                self.settle(18)
            captured = self.recorder.app.primaryScreen().grabWindow(self.window.winId()).toImage()
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

    def finish(self) -> None:
        """Projekt durch den echten Speicherdialog sichern, dann Ergebnisse belegen."""
        from app.core.geom.mesh import as_mesh_data

        self.window.object_tree.tree.clearSelection()
        lf._show_action_path(
            self.recorder,
            self.window.save_action,
            words(
                "Datei → Speichern sichert Original-STL, Maße und alle Schritte zusammen.",
                "File → Save keeps the original STL, the dimensions and every step together.",
            ),
        )
        self.file_dialog(
            self.window.save_action.trigger, self.folder / f"{self.story}.p3d", save=True
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
        lf._show_action_path(
            self.recorder,
            self.window.open_action,
            words(
                "Datei → Öffnen holt das Projekt zurück — mit allen Maßen und Schritten.",
                "File → Open brings the project back — with all dimensions and steps.",
            ),
        )
        self.file_dialog(self.window.open_action.trigger, self.folder / f"{self.story}.p3d")
        self.checked("Gespeichertes Projekt erneut geöffnet")
        lf._fit(self.window, self.recorder.app)
        self.add(
            "Alles wieder da",
            "Everything is back",
            "Verlauf und Maße sind erhalten. Jede Zahl lässt sich später wieder ändern.",
            "History and dimensions are preserved. Any number can be changed again later.",
            9.0,
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
        if self.recorder.seconds < 180.0:
            raise RuntimeError(f"Der vollständige Ablauf ist zu kurz: {self.recorder.seconds}s.")
        write_json(
            self.folder / "short_shots.json",
            {
                "story": self.story,
                "language": LANGUAGE,
                "title": self.title,
                "preview": True,
                "version": "0.4.1",
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
    tutorial.add(
        "Der Prüfbericht",
        "The report",
        "Rechts oben steht das Ergebnis: Der Weg ist frei. "
        "Beim Drucken zählt dann noch das Material.",
        "The result is at the top right: the path is clear. "
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


def main() -> int:
    """Aufnahmeprofil zuerst isolieren, danach Anwendung und Recorder laden."""
    global lf, LANGUAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", choices=STORIES)
    parser.add_argument("--language", choices=("de", "en"), default="de")
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--encode-only", action="store_true")
    parser.add_argument("--inputs-only", action="store_true")
    args = parser.parse_args()
    if (OUTPUT / "pause-production").exists():
        print("Produktionspause: zuerst den laufenden App-Prüflauf abschließen.", flush=True)
        return 75
    LANGUAGE = args.language
    folder = OUTPUT / args.story / LANGUAGE
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
        paths = make_inputs(folder / "sources", args.story)
        tutorial = Tutorial(app, folder, args.story)
        try:
            run_story(tutorial, paths)
            recorder = tutorial.recorder
        except BaseException:
            import traceback

            app.primaryScreen().grabWindow(tutorial.window.winId()).save(
                str(folder / "failed-state.png")
            )
            (folder / "failed-run.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            lf._finish_video(tutorial.session, tutorial.window)
    if not args.capture_only:
        recorder.chapter = MUSIC_STYLES[args.story]
        lf._encode(recorder, folder / f"solidon3d-{args.story}-{LANGUAGE}.mp4")
    print(f"Fertig: {folder} ({recorder.seconds:.1f} Sekunden)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
