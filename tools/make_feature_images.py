"""Textfreie Funktionsbilder aus echten Operationen und dem Solidon-Renderer.

Jeder Aufruf erzeugt genau ein Motiv in einem eigenen nativen Prozess.
Zuerst in einen Prüfungsordner schreiben und die Bilder ansehen; danach die
WebP-Dateien in ``website/bilder/`` übernehmen. Der JSON-Beleg bleibt intern.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SIZE = (1200, 800)
SEED = 20260915
MOTIFS = ("organizer", "bore-edit", "textures", "fields")
OPERATIONS: list[dict[str, Any]] = []


def operation(name: str, source: Any = None, **values: Any) -> Any:
    """Den registrierten Vertrag fahren; jede Rückfrage hält die Produktion an."""
    from app.core.knowledge import profiles
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    def refuse(question: Any, choices: Any) -> str:
        raise RuntimeError(f"Bild benötigt eine eindeutige Parametrierung: {question}; {choices}")

    spec = REGISTRY.get(name)
    inputs = [] if source is None else [source]
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in inputs}),
            inputs=inputs,
            params=spec.params(**values),
            profile=profiles.make_profile(),
            quality="fine",
            seed=SEED,
            progress=lambda fraction, text: None,
            ask=refuse,
            cancelled=NeverCancelled(),
        )
    )
    if len(result.outputs) != 1 or any(f.severity == "error" for f in result.findings):
        raise RuntimeError(
            f"{name} liefert kein eindeutiges fehlerfreies Modell: {result.findings}"
        )
    OPERATIONS.append(
        {
            "operation": name,
            "parameters": values,
            "solver": result.solver.strategy if result.solver else None,
            "findings": [str(f.message) for f in result.findings],
        }
    )
    return replace(result.outputs[0], id="model")


def models(motif: str) -> list[tuple[str, Any, str, tuple[float, float, float]]]:
    """Eigene parametrisierte Körper; Versätze dienen allein der Bildanordnung."""
    if motif == "organizer":
        from app.core.organizer.serialize import grid_layout, layout_to_text

        layout = grid_layout(2, 3, wall=3, radius=0)
        row = replace(layout.root.children[0], heights=((1, 22.0), (2, 34.0)))
        layout = replace(layout, root=replace(layout.root, heights=((1, 28.0),), children=(row,)))
        model = operation(
            "create_organizer",
            width=160,
            depth=110,
            height=48,
            wall=3,
            floor=3,
            radius=8,
            layout=layout_to_text(layout),
        )
        return [("organizer", model, "#e4ac59", (0, 0, 0))]

    if motif == "bore-edit":
        from app.core.perceive.features import detect

        plate = operation("create_box", width=50, depth=42, height=9)
        plate = operation(
            "drill_hole",
            plate,
            diameter=10,
            widening_diameter=18,
            widening_depth=0,
            transition_angle=90,
            z=plate.mesh.bounds.maximum[2],
            compensate=False,
        )
        plate = replace(plate, features=detect(plate.mesh))
        holes = [feature for feature in plate.features.values() if feature.kind == "hole"]
        if len(holes) != 1:
            raise RuntimeError(f"Erwartet wird genau eine erkannte Bohrung, gefunden: {len(holes)}")
        changed = operation(
            "resize_hole",
            plate,
            at_feature=holes[0].id,
            diameter=18,
            entrance_mode="follow",
            compensate=False,
        )
        return [
            ("before", plate, "#a9b7c9", (-33, 0, 0)),
            ("after", changed, "#5bc6cd", (33, 0, 0)),
        ]

    if motif == "fields":
        from app.core.sketch import shapes
        from app.core.sketch.serialize import sketch_to_text

        plate = operation("create_box", width=120, depth=86, height=4)
        opened = operation(
            "field_cut",
            plate,
            region_sketch=sketch_to_text(shapes.rectangle(112, 78)),
            exclusion_sketch=sketch_to_text(shapes.circle(28)),
            shape="hexagon",
            diameter=7,
            spacing=10,
            pattern="staggered",
            margin=2,
            web=1,
            through=True,
        )
        return [("hexagonal-field", opened, "#5bc6cd", (0, 0, 0))]

    results: list[tuple[str, Any, str, tuple[float, float, float]]] = []
    for index, (pattern, colour) in enumerate(
        (("knurl_diamond", "#e4ac59"), ("hexagon", "#5bc6cd"), ("rib", "#ad9bdb"))
    ):
        plate = operation("create_box", width=42, depth=48, height=5)
        textured = operation(
            "apply_texture",
            plate,
            pattern=pattern,
            width=37,
            height=43,
            pitch=5,
            depth=1.2,
            z=plate.mesh.bounds.maximum[2],
        )
        results.append((pattern, textured, colour, ((index - 1) * 51, 0, 0)))
    return results


def render(motif: str, output: Path) -> None:
    """Native pygfx-Fläche wie in der Galerie aufnehmen, ohne UI-Überlagerungen."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    from app.core.bootstrap import load_operations
    from app.ui.render.api import CameraPose, SurfaceStyle
    from app.ui.render.factory import available, make_renderer
    from tools.make_figures import settle

    load_operations()
    built = models(motif)
    evidence: dict[str, Any] = {
        "motif": motif,
        "size": SIZE,
        "seed": SEED,
        "models": [],
        "operations": OPERATIONS,
    }
    for name, body, _colour, offset in built:
        mesh = body.mesh
        if not mesh.is_watertight or mesh.component_count != 1 or mesh.volume <= 0:
            raise RuntimeError(f"{name}: kein geschlossener, zusammenhängender Körper")
        evidence["models"].append(
            {
                "name": name,
                "volume_mm3": mesh.volume,
                "bounds_mm": list(mesh.bounds.size),
                "triangles": mesh.triangle_count,
                "watertight": mesh.is_watertight,
                "components": mesh.component_count,
                "display_offset_mm": offset,
                "features": {
                    key: {"kind": feature.kind, "params": feature.params}
                    for key, feature in body.features.items()
                },
            }
        )
    app = QApplication(sys.argv[:1])
    if not available():
        raise RuntimeError(
            "Kein Grafikadapter verfügbar. Grafiktreiber prüfen und erneut aufnehmen."
        )
    window = QWidget()
    window.setWindowTitle("Solidon3D — Funktionsbild")
    window.setFixedSize(*SIZE)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    renderer = make_renderer(window, size=SIZE)
    layout.addWidget(renderer.widget)
    try:
        renderer.set_background("#111b2b", "#202f46")
        renderer.set_headlight(0.5)
        renderer.set_anti_aliasing(True)
        renderer.set_ambient_occlusion(True, radius=12, bias=0.04)
        for name, body, colour, offset in built:
            mesh = body.mesh.raw
            item = renderer.add_surface(
                np.asarray(mesh.vertices),
                np.asarray(mesh.faces),
                name=name,
                style=SurfaceStyle(colour=colour, smooth=False, specular=0.25),
            )
            item.set_position(offset)
        direction = (0.7, -1.0, 1.05) if motif == "organizer" else (0.15, -1.0, 1.25)
        renderer.set_camera_pose(CameraPose(direction, (0, 0, 0), (0, 0, 1)))
        renderer.set_parallel_projection(True)
        window.show()
        window.raise_()
        window.activateWindow()
        settle(app, 15)
        renderer.reset_camera()
        renderer.dolly(1.13)
        renderer.render()
        settle(app, 15)
        screen = renderer.widget.screen()
        shot = screen.grabWindow(renderer.widget.winId()).toImage()
        shot = shot.scaled(
            *SIZE, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        path = output / f"feature-{motif}.webp"
        if not shot.save(str(path), "WEBP", 90):
            raise RuntimeError(f"{path} ließ sich nicht speichern. Zielordner prüfen.")
        evidence["camera"] = {"direction": direction, "parallel": True}
        (output / f"feature-{motif}.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"{path}: {SIZE[0]}x{SIZE[1]}, {path.stat().st_size} Bytes", flush=True)
    finally:
        renderer.close()
        window.close()
        app.processEvents()


def main() -> int:
    """Genau ein Motiv im eigenen Profil erzeugen; kein Schreiben in Nutzerordner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motif", choices=MOTIFS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    with tempfile.TemporaryDirectory(prefix="solidon-feature-image-") as directory:
        for name, child in (
            ("APPDATA", "roaming"),
            ("LOCALAPPDATA", "local"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_CACHE_HOME", "cache"),
        ):
            target = Path(directory) / child
            target.mkdir()
            os.environ[name] = str(target)
        os.environ.pop("QT_QPA_PLATFORM", None)
        render(args.motif, args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
