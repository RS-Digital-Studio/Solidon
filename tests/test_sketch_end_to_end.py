"""Das Referenzteil aus §40 zu P13: ein Gehäuse mit passendem Deckel,
von der leeren Szene bis zur Exportdatei, ohne ein fremdes CAD.

Vier Operationen, jede aus dem Register, jede über den Stapel: Grundform
extrudieren, Kanten verrunden, exakt aushöhlen, Deckel erzeugen. Jede Zahl
dazwischen ist von Hand nachrechenbar — die Wand aus dem Versatz, die
Eckradien aus der Differenz, und der Beweis für den Deckel ist, dass er mit
dem Gehäuse kein Volumen teilt.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.core.brep.kernel import available
from app.core.export.writer import plan_export, write_plan
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import as_mesh_data
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Profile

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

OUTER = (60.0, 40.0, 30.0)
WALL = 3.0
CORNER = 5.0


def rounded_rect_area(width: float, depth: float, radius: float) -> float:
    """Fläche eines Rechtecks mit vier Viertelkreis-Ecken — die Handrechnung."""
    return width * depth - (4.0 - math.pi) * radius**2


def test_the_reference_part_runs_from_empty_scene_to_export(
    profile: Profile, tmp_path: Path
) -> None:
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    sources = ProjectSources(project)

    # 1. Grundform aufziehen — die Skizze läuft durch Solver und Kern.
    history.apply(
        "Gehäuse aufziehen",
        [
            OperationDraft(
                op="sketch_extrude",
                params={
                    "shape": "rectangle",
                    "length": OUTER[0],
                    "width": OUTER[1],
                    "height": OUTER[2],
                    "name": "Gehäuse",
                },
            )
        ],
    )

    # 2. Kanten verrunden — exakt, weil die Kante eine Kurve ist (§30).
    history.apply(
        "Verrunden",
        [
            OperationDraft(
                op="fillet_edges",
                inputs=("obj_1",),
                params={"radius": CORNER, "edges": "vertical"},
            )
        ],
    )

    # 3. Exakt aushöhlen — Wand und Boden aus dem Versatz, Oberseite offen.
    history.apply(
        "Aushöhlen",
        [OperationDraft(op="shell_exact", inputs=("obj_1",), params={"wall": WALL})],
    )

    # 4. Deckel aus der Öffnung — das Spiel kommt aus dem Materialprofil (§12).
    history.apply(
        "Deckel",
        [
            OperationDraft(
                op="create_lid",
                inputs=("obj_1",),
                params={"thickness": 2.4, "collar": 4.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=sources)
    assert result.complete, [finding.message for finding in result.scene.report.findings]

    # Gehäuse und Deckel stehen beide in der Szene.
    bodies = result.scene.objects
    housing = next(entry for entry in bodies.values() if entry.name == "Gehäuse")
    lid = next(entry for entry in bodies.values() if "Deckel" in str(entry.name))
    assert housing.kind == "brep"

    # Die Wand ist eine Handrechnung: außen 60 x 40, Ecken r5, innen um die
    # Wand versetzt — 54 x 34 mit Ecken r2, Boden 3 mm.
    outer = rounded_rect_area(OUTER[0], OUTER[1], CORNER) * OUTER[2]
    cavity = rounded_rect_area(OUTER[0] - 2 * WALL, OUTER[1] - 2 * WALL, CORNER - WALL) * (
        OUTER[2] - WALL
    )
    assert housing.mesh.volume == pytest.approx(outer - cavity, rel=1e-6)

    # Der Deckel ist dicht, und er geht hinein: kein gemeinsames Volumen.
    assert lid.mesh.is_watertight
    assert shared_volume(as_mesh_data(lid.mesh).raw, as_mesh_data(housing.mesh).raw) < 1e-6

    # Export beider Körper — das Ende des Weges ist eine Datei.
    plan = plan_export(
        list(bodies.values()), project_name="gehaeuse", profile=profile, export_format="3mf"
    )
    written = write_plan(plan, tmp_path / "export", "3mf")
    assert written and written[0].is_file()


def test_the_reference_part_survives_an_undo(profile: Profile) -> None:
    """§15.5: der Deckel ist eine Transaktion — ein Undo nimmt genau ihn zurück."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    sources = ProjectSources(project)

    history.apply(
        "Gehäuse aufziehen",
        [
            OperationDraft(
                op="sketch_extrude",
                params={
                    "shape": "rectangle",
                    "length": OUTER[0],
                    "width": OUTER[1],
                    "height": OUTER[2],
                    "name": "Gehäuse",
                },
            )
        ],
    )
    history.apply(
        "Aushöhlen",
        [OperationDraft(op="shell_exact", inputs=("obj_1",), params={"wall": WALL})],
    )
    history.apply(
        "Deckel",
        [
            OperationDraft(
                op="create_lid",
                inputs=("obj_1",),
                params={"thickness": 2.4, "collar": 4.0},
            )
        ],
    )

    with_lid = evaluate(project.document, profile, sources=sources)
    assert with_lid.complete
    count_with_lid = len(with_lid.scene.objects)

    history.undo()
    without = evaluate(project.document, profile, sources=sources)
    assert without.complete
    assert len(without.scene.objects) == count_with_lid - 1
