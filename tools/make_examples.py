"""Build the three example projects (Bauplan §37.2, §2.2).

They are documentation, acceptance test and start screen content at once, so
they are built the way everything else is built: as operations on a stack. A
folder of hand-exported files would drift from the application the first time an
operation changed.

    python tools/make_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.bootstrap import load_operations
from app.core.examples import directory
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project, save
from app.core.types import Parameter, Source

CORPUS = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"


def with_source(project: Project, name: str, mesh: str, kind: str = "import") -> None:
    project.document.sources[name] = Source(id=name, kind=kind, path=f"sources/{mesh}", sha256="")
    project.sources[name] = (CORPUS / mesh).read_bytes()


def way_one() -> Project:
    """Adapting a foreign model: import, repair, on the bed, drill (§2.2)."""
    project = new_project("centauri-carbon-2", "petg")
    with_source(project, "src_1", "plate_holes.stl")
    history = History(project.document)
    history.apply(
        "Modell laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    history.apply("Reparieren", [OperationDraft(op="repair", inputs=("obj_1",), params={})])
    history.apply("Auf das Bett", [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    history.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.2, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    return project


def way_two() -> Project:
    """Building new: parameters, a body, parts from the library (§2.2)."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["breite"] = Parameter(name="breite", value=60.0, unit="mm", title="Breite")
    document.parameters["tiefe"] = Parameter(name="tiefe", value=40.0, unit="mm", title="Tiefe")
    document.parameters["staerke"] = Parameter(name="staerke", value=6.0, unit="mm", title="Stärke")

    history = History(document)
    history.apply(
        "Grundkörper",
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": "=@breite",
                    "depth": "=@tiefe",
                    "height": "=@staerke",
                    "name": "Halter",
                },
            )
        ],
    )
    history.apply(
        "Schraubenlöcher",
        [
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M4", "depth": 6.0, "x": -20.0, "z": "=@staerke"},
            ),
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M4", "depth": 6.0, "x": 20.0, "z": "=@staerke"},
            ),
        ],
    )
    history.apply(
        "Versteifung",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"length": 30.0, "height": 5.0, "wall": 6.0, "z": "=@staerke"},
            )
        ],
    )
    return project


def way_three() -> Project:
    """Preparing a generated mesh: repair chain, then split (§2.2).

    The generator is P9. What travels with the example is a finished mesh —
    marked as generated, so the project says where the geometry came from
    rather than pretending it was drawn.
    """
    project = new_project("centauri-carbon-2", "petg")
    with_source(project, "src_1", "broken_open.stl", kind="generated")
    history = History(project.document)
    history.apply(
        "Erzeugtes Mesh laden",
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    history.apply(
        "Reparaturkette",
        [
            OperationDraft(
                op="repair",
                inputs=("obj_1",),
                params={"fill_holes": True, "weld": True, "degenerate": True},
            )
        ],
    )
    history.apply("Auf das Bett", [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    return project


def main() -> int:
    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    target = directory()
    target.mkdir(parents=True, exist_ok=True)

    from app.core.examples import EXAMPLES

    builders = {"1": way_one, "2": way_two, "3": way_three}
    for example in EXAMPLES:
        project = builders[example.way]()
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        if not result.complete:
            print(f"-- {example.id}: Kette hält an")
            for finding in result.scene.report.findings:
                print(f"   {finding.code}: {finding.message}")
            return 1

        path = save(project, target / example.filename)
        objects = ", ".join(
            f"{entry.name} {entry.mesh.volume / 1000.0:.1f} cm3"
            for entry in result.scene.objects.values()
        )
        print(f"ok {path.name}: {objects}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
