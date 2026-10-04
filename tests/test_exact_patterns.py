"""Muster am exakten Körper: dieselben Felder wie am Netzzwilling (RM-504).

Der native STEP-Leser bildete keine Muster. Eine Wabenplatte aus STEP stand
mit 90 Flächen im Objektbaum, ihr Netzzwilling mit einem Muster, und der Weg
zu den Musterhandlungen führte über *Flächenbearbeitung beenden*.
``brep.features.features_of`` fragt jetzt dieselbe Mustersuche an den
Dreiecken der Tessellierung — mit denselben Schwellen und derselben
Nummerierung.

Gegenprobe je Feld: dieselbe Konstruktion einmal als STEP-Datei, einmal als
binäre STL ihrer Tessellierung, beide über den echten Einleseweg
(Importplan, Verlauf, Auswertung). Die Sollwerte kommen aus der Konstruktion:
Schlüsselweite, Teilung und Tiefe der Waben, Teilung und Breite der Rillen.
Gegenproben ohne Muster — Lochblech und ein Feld unter der Mindestzahl —
bleiben an beiden Kernen, was sie sind.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from tests.helpers import exact_kernel

edit = exact_kernel()

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut  # noqa: E402
from OCP.BRepBuilderAPI import (  # noqa: E402
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.brep import step  # noqa: E402
from app.core.brep.kernel import Solid  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.scene.project import Project, ProjectSources, new_project  # noqa: E402
from app.core.types import (  # noqa: E402
    Feature,
    FeatureId,
    OpContext,
    Profile,
    Scene,
    SceneObject,
    Source,
)

#: Die Waben des Halters (``test_pattern_features``): Schlüsselweite, Teilung.
ACROSS = 9.0
PITCH = 10.4
THICKNESS = 8.0

#: Was zwei gleich gemessene Muster beider Kerne trennen darf: die float32-
#: Rundung der STL (Koordinaten bis 30 mm, sieben Stellen) — ein Tausendstel
#: liegt darüber und unter jedem Maß, das ein Kunde ändert.
SAME = 1e-3


def _cut(shape: Any, tool: Any) -> Any:
    cut = BRepAlgoAPI_Cut(shape, tool)
    cut.Build()
    assert cut.IsDone()
    return cut.Shape()


def _prism(corners: Sequence[tuple[float, float]], bottom: float, height: float) -> Any:
    polygon = BRepBuilderAPI_MakePolygon()
    for x, y in corners:
        polygon.Add(gp_Pnt(x, y, bottom))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, height)).Shape()


def _hexagon(x: float, y: float, bottom: float, height: float) -> Any:
    radius = ACROSS / math.sqrt(3.0)
    corners = [
        (
            x + radius * math.cos(math.radians(60.0 * index)),
            y + radius * math.sin(math.radians(60.0 * index)),
        )
        for index in range(6)
    ]
    return _prism(corners, bottom, height)


def _lattice(columns: int, rows: int, pitch: float) -> list[tuple[float, float]]:
    """Die Mitten eines Wabengitters, versetzt in jeder zweiten Reihe."""
    step_y = pitch * math.sqrt(3.0) / 2.0
    return [
        (
            (column - (columns - 1) / 2.0) * pitch + (pitch / 2.0 if row % 2 else 0.0),
            (row - (rows - 1) / 2.0) * step_y,
        )
        for row in range(rows)
        for column in range(columns)
    ]


def _plate(columns: int, rows: int, pitch: float) -> tuple[Any, float, float]:
    width = columns * pitch + 1.5 * pitch
    depth = rows * pitch * math.sqrt(3.0) / 2.0 + 1.5 * pitch
    return edit.box(width, depth, THICKNESS).shape, width, depth


def honeycomb(*, columns: int = 4, rows: int = 3, through: bool = True) -> Solid:
    """Eine Platte mit Sechseckzellen: durchgehend oder halb so tief wie die Platte."""
    shape, _width, _depth = _plate(columns, rows, PITCH)
    bottom, height = (-1.0, THICKNESS + 2.0) if through else (THICKNESS / 2.0, THICKNESS)
    for x, y in _lattice(columns, rows, PITCH):
        shape = _cut(shape, _hexagon(x, y, bottom, height))
    return Solid(shape)


#: Sechs Rillen, 2 mm breit, 1 mm tief, Teilung 5 mm — die Mindestzahl einer
#: Reihe (``patterns.MIN_STRIPS``).
GROOVES, GROOVE_WIDTH, GROOVE_DEPTH, GROOVE_PITCH = 6, 2.0, 1.0, 5.0


def grooved() -> Solid:
    shape = edit.box(50.0, 30.0, THICKNESS).shape
    for index in range(GROOVES):
        x = (index - (GROOVES - 1) / 2.0) * GROOVE_PITCH
        half = GROOVE_WIDTH / 2.0
        corners = [(x - half, -10.0), (x + half, -10.0), (x + half, 10.0), (x - half, 10.0)]
        shape = _cut(shape, _prism(corners, THICKNESS - GROOVE_DEPTH, 2.0))
    return Solid(shape)


#: Ein Lochblech: 25 durchgehende Bohrungen Ø 3 im Raster von 6 mm.
def perforated() -> Solid:
    shape = edit.box(40.0, 40.0, 4.0).shape
    for i in range(5):
        for j in range(5):
            axis = gp_Ax2(gp_Pnt((i - 2) * 6.0, (j - 2) * 6.0, -1.0), gp_Dir(0.0, 0.0, 1.0))
            shape = _cut(shape, BRepPrimAPI_MakeCylinder(axis, 1.5, 6.0).Shape())
    return Solid(shape)


def _loaded(name: str, payload: bytes, profile: Profile) -> SceneObject:
    """Der echte Einleseweg: Importplan, Verlauf, Auswertung."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    plan = import_plan("src_1", name, payload)
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=ResultCache()
    )
    assert result.complete, result.scene.report.findings
    return result.scene.objects["obj_1"]


def twins(solid: Solid, profile: Profile) -> tuple[SceneObject, SceneObject]:
    """Derselbe Körper als STEP und als binäre STL seiner Tessellierung."""
    exact = _loaded("teil.step", step.write(solid, "Teil"), profile)
    assert exact.kind == "brep"
    mesh = _loaded("teil.stl", as_mesh_data(solid).raw.export(file_type="stl"), profile)
    assert mesh.kind == "mesh"
    return exact, mesh


def kinds(features: Mapping[FeatureId, Feature]) -> Counter[str]:
    return Counter(feature.kind for feature in features.values())


def the_pattern(entry: SceneObject) -> Feature:
    (pattern,) = [feature for feature in entry.features.values() if feature.kind == "pattern"]
    return pattern


def assert_same_pattern(one: Feature, other: Feature) -> None:
    """Art, Maße, Lage und Kennung — was beide Kerne gleich sagen müssen."""
    assert one.id == other.id
    for key in ("style", "lattice", "count", "partial", "mode", "through", "coverage"):
        assert one.params[key] == other.params[key], key
    for key in ("pitch", "cell_width", "cell_depth", "width", "height", "angle"):
        assert one.params[key] == pytest.approx(other.params[key], abs=SAME), key
    for key in ("centre", "normal"):
        assert one.params[key] == pytest.approx(other.params[key], abs=SAME), key


@pytest.mark.parametrize("through", [True, False])
def test_a_step_honeycomb_is_the_same_pattern_as_its_stl_twin(
    profile: Profile, through: bool
) -> None:
    exact, mesh = twins(honeycomb(through=through), profile)
    assert kinds(exact.features) == kinds(mesh.features) == {"face": 6, "pattern": 1}
    pattern = the_pattern(exact)
    assert pattern.params["style"] == "hexagon" and pattern.params["lattice"] == "hexagonal"
    assert pattern.params["count"] == 12
    assert pattern.params["pitch"] == pytest.approx(PITCH, abs=SAME)
    assert pattern.params["cell_width"] == pytest.approx(ACROSS, abs=SAME)
    expected_depth = THICKNESS if through else THICKNESS / 2.0
    assert pattern.params["cell_depth"] == pytest.approx(expected_depth, abs=SAME)
    assert pattern.params["through"] is through
    assert pattern.provenance == "detected"
    assert_same_pattern(pattern, the_pattern(mesh))


def test_a_step_row_of_grooves_is_the_same_rib_pattern_as_its_stl_twin(
    profile: Profile,
) -> None:
    exact, mesh = twins(grooved(), profile)
    assert kinds(exact.features)["pattern"] == kinds(mesh.features)["pattern"] == 1
    pattern = the_pattern(exact)
    assert pattern.params["style"] == "rib" and pattern.params["count"] == GROOVES
    assert pattern.params["pitch"] == pytest.approx(GROOVE_PITCH, abs=SAME)
    assert pattern.params["cell_width"] == pytest.approx(GROOVE_WIDTH, abs=SAME)
    assert pattern.params["cell_depth"] == pytest.approx(GROOVE_DEPTH, abs=SAME)
    assert pattern.params["mode"] == "engraved"
    assert_same_pattern(pattern, the_pattern(mesh))


def test_too_few_step_cells_stay_faces_like_their_twin(profile: Profile) -> None:
    """Acht Waben sind an beiden Kernen acht Waben — dieselbe Schwelle, kein Muster."""
    exact, mesh = twins(honeycomb(columns=4, rows=2), profile)
    assert "pattern" not in kinds(exact.features)
    assert kinds(exact.features) == kinds(mesh.features)


def test_a_perforated_step_plate_stays_bores(profile: Profile) -> None:
    """Ein Lochblech behält an beiden Kernen seine Bohrungshandlungen."""
    exact, mesh = twins(perforated(), profile)
    assert "pattern" not in kinds(exact.features)
    assert kinds(exact.features)["hole"] == kinds(mesh.features)["hole"] == 25


def test_removing_a_step_pattern_keeps_the_body_exact(profile: Profile) -> None:
    """*Merkmal entfernen* füllt alle Zellen am exakten Körper, ohne ihn zu vernetzen."""
    exact = _loaded("teil.step", step.write(honeycomb(through=False), "Teil"), profile)
    pattern = the_pattern(exact)
    spec = REGISTRY.get("remove_feature")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={exact.id: exact}, parameters={}),
            inputs=[exact],
            params=spec.params(at_feature=pattern.id),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    out = result.outputs[0]
    assert out.kind == "brep"
    _shape, width, depth = _plate(4, 3, PITCH)
    assert out.mesh.volume == pytest.approx(width * depth * THICKNESS, rel=1e-9)
    assert any(finding.code == "remove_feature.gone" for finding in result.findings)


def test_grouping_cells_on_a_step_body_lives_through_a_move(profile: Profile) -> None:
    """Acht Waben aus STEP, ausdrücklich zusammengefasst, bleiben ein Muster am exakten Körper."""
    from app.core.perceive import patterns

    load_operations()
    project: Project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = step.write(honeycomb(columns=4, rows=2), "Teil")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/teil.step", sha256=""
    )
    plan = import_plan("src_1", "teil.step", project.sources["src_1"])
    history = History(project.document)
    history.apply(plan.title, [plan.draft])

    def inspect() -> SceneObject:
        result = evaluate(
            project.document, profile, sources=ProjectSources(project), cache=ResultCache()
        )
        assert result.complete, result.scene.report.findings
        return result.scene.objects["obj_1"]

    loaded = inspect()
    walls = sorted(
        name
        for name, feature in loaded.features.items()
        if feature.kind == "face"
        and abs(float(feature.params["normal"][2])) < 0.5
        and float(feature.params["area"]) < ACROSS * THICKNESS
    )
    assert len(walls) == 8 * 6
    history.apply(
        "Als Muster zusammenfassen",
        [OperationDraft(op="group_pattern", inputs=("obj_1",), params={"at_features": walls})],
    )
    name = f"{patterns.GROUPED_PREFIX}_{project.document.ops[-1].id}"
    grouped = inspect()
    assert grouped.kind == "brep"
    assert grouped.features[name].params["count"] == 8
    assert grouped.features[name].params["style"] == "hexagon"
    history.apply(
        "Verschieben",
        [
            OperationDraft(
                op="translate_object", inputs=("obj_1",), params={"dx": 0.0, "dy": 7.0, "dz": 0.0}
            )
        ],
    )
    moved = inspect()
    assert moved.kind == "brep"
    assert moved.features[name].params["count"] == 8
    assert moved.features[name].params["centre"] == pytest.approx(
        (
            grouped.features[name].params["centre"][0],
            grouped.features[name].params["centre"][1] + 7.0,
            grouped.features[name].params["centre"][2],
        ),
        abs=1e-6,
    )
    assert not set(walls) & set(moved.features)
