"""Netz → exakter Körper ohne Verlauf (P4.0).

Die Abnahme aus dem Konzept am Korpus: gültiger Körper, Flächenarten und
-zahlen, Volumen und Bohrungsmaße gegen Sollwerte aus der Konstruktion der
Datei (``tests/data/make_corpus.py``), beidseitige Abweichung unter der
Sehnenhöhe, die das Netz selbst hat, STEP-Rundreise und danach *Bohrung
ändern* am exakten Ergebnis. Dazu jede Absage mit ihrem Ausweg, der Abbruch
und die Einzelbefunde, die beim Bau an Kundenmodellen gefunden wurden — mit
nachgebauter Geometrie, denn Kundenmodelle gehören nicht in den Korpus.
"""

# ruff: noqa: E402

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from tests.helpers import exact_kernel

exact_kernel()

from app.core.brep.kernel import Solid
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.types import Profile

MESHES = Path(__file__).parent / "data" / "meshes"


def _sag(radius: float, sections: int) -> float:
    """Wie weit die Sehne eines regelmäßigen Vielecks mitten zwischen zwei Ecken vom Kreis liegt."""
    return radius * (1.0 - math.cos(math.pi / sections))


#: Je Korpusdatei: Flächen nach Art, Volumen aus der Konstruktion und die
#: Sehnenhöhen, die das Netz selbst gegen seine Sollform hat — als Summe über
#: seine Rundungen die Obergrenze, als größte einzelne der Wert, den die
#: Messung mindestens finden muss. Der Körper darf beidseitig nicht weiter
#: weg liegen, sonst hätte die Umwandlung etwas verschoben; näher auch nicht,
#: sonst hätte die Messung die Rundung verfehlt.
CORPUS: dict[str, tuple[dict[str, int], float, tuple[float, float]]] = {
    # Platte 80 mal 50 mal 8, vier Bohrungen R 2,6 aus 48-Ecken.
    "plate_holes.stl": (
        {"plane": 6, "cylinder": 4},
        80.0 * 50.0 * 8.0 - 4.0 * math.pi * 2.6**2 * 8.0,
        (_sag(2.6, 48), _sag(2.6, 48)),
    ),
    # Quader 40 mal 30 mal 20, eine Kante mit R 3 aus einem 96-Eck gerundet.
    "block_with_rounded_edge.stl": (
        {"plane": 6, "cylinder": 1},
        24000.0 - (9.0 - 9.0 * math.pi / 4.0) * 30.0,
        (_sag(3.0, 96), _sag(3.0, 96)),
    ),
    # Platte 60 mal 60 mal 6, Säule R 6 mal 30, Kehle R 3 (Pappus: Quadrat minus
    # Viertelkreis um die Achse gedreht), alles aus 96-Ecken, der Ring 96 mal 48.
    "post_with_fillet.stl": (
        {"plane": 7, "cylinder": 1, "torus": 1},
        21600.0
        + math.pi * 36.0 * 30.0
        + 2.0 * math.pi * (9.0 * 7.5 - 9.0 * math.pi / 4.0 * (9.0 - 4.0 / math.pi)),
        (_sag(12.0, 96) + _sag(3.0, 48), _sag(12.0, 96)),
    ),
    # Ring 20 / 5 aus 48 mal 24 Vierecken.
    "torus_ring.stl": (
        {"torus": 1},
        2.0 * math.pi**2 * 20.0 * 5.0**2,
        (_sag(25.0, 48) + _sag(5.0, 24), _sag(25.0, 48)),
    ),
    # Zylinder R 2,5 mal 40 aus einem 360-Eck.
    "dense_cylinder.stl": (
        {"plane": 2, "cylinder": 1},
        math.pi * 2.5**2 * 40.0,
        (_sag(2.5, 360), _sag(2.5, 360)),
    ),
}


def _mesh(name: str) -> MeshData:
    path = MESHES / name
    return normalise(read_mesh(path.read_bytes(), path.suffix), "mm", weld_is_reading=True).mesh


def _converted(name: str, tolerance: float | None = None) -> Any:
    from app.core.brep import from_mesh
    from app.core.perceive.features import detect

    mesh = _mesh(name)
    return from_mesh.convert(mesh, detect(mesh), tolerance=tolerance or from_mesh.DEFAULT_TOLERANCE)


def _surface_kinds(body: Solid) -> Counter[str]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Torus

    names = {
        GeomAbs_Plane: "plane",
        GeomAbs_Cylinder: "cylinder",
        GeomAbs_Cone: "cone",
        GeomAbs_Torus: "torus",
    }
    return Counter(names.get(BRepAdaptor_Surface(face).GetType(), "other") for face in body.faces())


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_the_corpus_becomes_a_valid_exact_body_of_the_designed_shape(name: str) -> None:
    """Gültig, geschlossen, die Flächen der Konstruktion und ihr Volumen — beidseitig nah."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    kinds, volume, (sag, single) = CORPUS[name]
    result = _converted(name)
    body = result.solid

    assert BRepCheck_Analyzer(body.shape).IsValid()
    assert body.is_closed and body.solid_count == 1
    assert dict(result.faces) == kinds
    assert _surface_kinds(body) == Counter(kinds)
    assert body.volume == pytest.approx(volume, rel=1e-6)
    assert result.freeform_share == 0.0 and result.freeform_triangles == 0
    # Beide Richtungen, jede für sich: höchstens die Sehnenhöhe des Netzes.
    assert result.mesh_to_body <= sag * 1.001 + 1e-6
    assert result.body_to_mesh <= sag * 1.001 + 1e-6
    # Und nicht still null: Die Rückrichtung maß bis zum Bau der Operation an
    # Knoten, die alle auf den Deckflächen lagen (7,9e-7 statt 0,0056 mm).
    if single > 1e-3:
        assert result.body_to_mesh >= 0.8 * single
        assert result.mesh_to_body >= 0.8 * single


def test_the_holes_keep_their_constructed_diameter() -> None:
    """Die Merkmale des exakten Körpers (P2.3) messen die Konstruktion, nicht das Vieleck."""
    from app.core.brep.features import features_of

    body = _converted("plate_holes.stl").solid
    holes = sorted(
        (feature for feature in features_of(body).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )
    assert len(holes) == 4
    for hole, (x, y) in zip(
        holes, sorted([(-25.0, -15.0), (-25.0, 15.0), (25.0, -15.0), (25.0, 15.0)]), strict=True
    ):
        assert hole.params["diameter"] == pytest.approx(5.2, abs=1e-4)
        assert hole.params["centre"][:2] == pytest.approx((x, y), abs=1e-4)
        assert hole.params["through"] is True


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_the_result_survives_a_step_round_trip(name: str) -> None:
    """STEP schreiben, lesen: dieselben Flächenarten und dasselbe Volumen."""
    from app.core.brep import step

    body = _converted(name).solid
    again = step.read(step.write(body))

    assert _surface_kinds(again) == _surface_kinds(body)
    assert again.volume == pytest.approx(body.volume, rel=1e-7)


def test_a_torus_face_without_edges_has_its_volume() -> None:
    """Befund 1: Eine natürlich begrenzte Fläche ergab das Volumen null.

    ``BRepGProp_Vinert`` ohne Gebiet rechnet an einer Fläche, deren Grenzen
    die ihrer Fläche selbst sind, null — mit dem Fehler null. Der Ring aus
    ``torus_ring.stl`` ist genau eine solche Fläche, und der Kunde sah
    „Volumen 0“. Rot vor dem Fix: gemessen mit der Fassung aus HEAD (0,0 für
    Ring und Kugel).
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.Geom import Geom_SphericalSurface, Geom_ToroidalSurface
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Shell, TopoDS_Solid

    from app.core.brep.properties import properties

    frame = gp_Ax3(gp_Pnt(3.0, -2.0, 7.0), gp_Dir(0.0, 0.0, 1.0))
    for surface, expected in (
        (Geom_ToroidalSurface(frame, 20.0, 5.0), 2.0 * math.pi**2 * 20.0 * 25.0),
        (Geom_SphericalSurface(frame, 10.0), 4.0 / 3.0 * math.pi * 1000.0),
    ):
        builder = BRep_Builder()
        shell = TopoDS_Shell()
        builder.MakeShell(shell)
        builder.Add(shell, BRepBuilderAPI_MakeFace(surface, 1e-7).Face())
        solid = TopoDS_Solid()
        builder.MakeSolid(solid)
        builder.Add(solid, shell)
        assert properties(solid, "volume").mass == pytest.approx(expected, rel=1e-9)


def test_an_inner_seam_is_counted_and_not_called_deviation() -> None:
    """Befund: eine nicht verschmolzene Naht liegt im Körper, nicht neben ihm.

    ``post_with_fillet.stl`` ist eine Vereinigung, deren Säulenmantel und
    Innenwand des Kehlrings zwischen z = 0 und 3 aufeinanderliegen. Gegen
    ihren Zylinder gemessen liegen diese Dreiecke auf der Fläche, gegen den
    Körper 3√2 − 3 = 1,24 mm unter seiner Kehle. Das ist keine Abweichung der
    Form — der Körper übernimmt die Naht nicht —, und es wird eigens gezählt.
    """
    result = _converted("post_with_fillet.stl")

    assert result.inner_walls == 3
    assert result.mesh_to_body < 0.02


def test_the_deviation_map_of_a_converted_body_measures_against_its_mesh() -> None:
    """Die Karte „Formabweichung“ (P1.6) misst den Körper gegen das Netz davor."""
    from app.core.perceive import maps
    from app.core.types import SceneObject

    result = _converted("plate_holes.stl")
    entry = SceneObject(id="obj_1", name="Platte", mesh=result.solid, kind="brep")

    analysis = maps.build("deviation", entry)

    values = np.asarray(analysis.values)
    assert len(values) == result.solid.mesh.triangle_count
    assert not np.isnan(values).any()
    assert float(values.max()) == pytest.approx(_sag(2.6, 48), rel=0.02)
    assert analysis.maximum_interval is None, "gemessen, nicht eingeschlossen"
    assert analysis.witness_point is not None
    assert "Umwandlung" in str(analysis.note)


def test_a_moved_body_forgets_its_mesh() -> None:
    """Nach einer Bewegung gilt der Bezug nicht mehr — er wurde nicht mitbewegt."""
    from app.core.brep import edit
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import translation

    body = _converted("dense_cylinder.stl").solid
    assert body.source_deviation() is not None

    moved = edit.transformed(body, as_transform(translation((5.0, 0.0, 0.0))))

    assert moved.source_deviation() is None


def _flat_noise(count: int) -> MeshData:
    """Eine geschlossene, zerbeulte Kugel: keine Fläche trägt mehr als zufällig ein Dreieck."""
    body = trimesh.creation.icosphere(subdivisions=count, radius=10.0)
    rng = np.random.default_rng(1234)
    direction = body.vertices / np.linalg.norm(body.vertices, axis=1)[:, None]
    body.vertices = body.vertices + direction * rng.uniform(-0.6, 0.6, (len(body.vertices), 1))
    return MeshData.of(body)


def test_a_freeform_mesh_is_refused_with_the_way_out(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zu viel freie Form wird keine Wolke aus Dreiecksflächen, sondern eine Absage mit Ausweg."""
    from app.core.brep import from_mesh
    from app.core.brep.ops import MeshToExactParams, mesh_to_exact
    from app.core.errors import DECIMATE_MESH, GeometryError
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    monkeypatch.setattr(from_mesh, "MAX_FREEFORM_FACES", 50)
    source = SceneObject(id="obj_1", name="Beule", mesh=_flat_noise(2))
    context = OpContext(
        Scene(),
        [source],
        MeshToExactParams(),
        profile,
        "fine",
        None,
        lambda *_: None,
        lambda *_: pytest.fail("keine Rückfrage erwartet"),
        NeverCancelled(),
    )

    with pytest.raises(GeometryError) as refused:
        mesh_to_exact(context)

    assert refused.value.suggestions[0] == DECIMATE_MESH
    assert refused.value.values["limit"] == 50
    assert refused.value.object_id == "obj_1"


@pytest.mark.parametrize("stage", ["_build", "_checked_body"])
def test_an_exception_of_opencascade_becomes_the_refusal_with_its_way_out(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """Die Ausnahmen aus OpenCASCADE erben in OCP 8 nur von ``Exception``.

    ``GeomAPI_Interpolate`` warf an einem Fettpressenwerkzeug aus dem Korpus
    ``Standard_ConstructionError``, die Flächenreparatur an einem Minigolfteil
    ``StdFail_NotDone``; der Fang über ``RuntimeError`` ließ beide durch, und
    der Kunde las „Im Programm ist ein unerwarteter Fehler aufgetreten“.
    Nachgestellt mit derselben Ausnahmeart an beiden Baustufen.
    """
    from OCP.Standard import Standard_ConstructionError

    from app.core.brep import from_mesh
    from app.core.brep.ops import MeshToExactParams, mesh_to_exact
    from app.core.errors import GeometryError
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    def native(*_args: object, **_kwargs: object) -> None:
        raise Standard_ConstructionError("BSpline curve: # Poles and degree mismatch")

    monkeypatch.setattr(from_mesh, stage, native)
    source = SceneObject(id="obj_1", name="Platte", mesh=_mesh("plate_holes.stl"))
    context = OpContext(
        Scene(),
        [source],
        MeshToExactParams(),
        profile,
        "fine",
        None,
        lambda *_: None,
        lambda *_: pytest.fail("keine Rückfrage erwartet"),
        NeverCancelled(),
    )

    with pytest.raises(GeometryError) as refused:
        mesh_to_exact(context)

    assert refused.value.suggestions
    assert isinstance(refused.value.__cause__, from_mesh.ConversionRefusedError)


def test_an_open_mesh_is_refused_with_repair(profile: Profile) -> None:
    """Ein Netz mit Loch hat keine Hülle — die Absage schlägt die Reparatur vor."""
    from app.core.brep.ops import MeshToExactParams, mesh_to_exact
    from app.core.errors import REPAIR_AND_RETRY, NotManifoldError
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    box = trimesh.creation.box(extents=(20.0, 16.0, 10.0))
    box.update_faces(np.arange(len(box.faces)) != 0)
    source = SceneObject(id="obj_1", name="Offen", mesh=MeshData.of(box))
    context = OpContext(
        Scene(),
        [source],
        MeshToExactParams(),
        profile,
        "fine",
        None,
        lambda *_: None,
        lambda *_: pytest.fail("keine Rückfrage erwartet"),
        NeverCancelled(),
    )

    with pytest.raises(NotManifoldError) as refused:
        mesh_to_exact(context)

    assert refused.value.suggestions[0] == REPAIR_AND_RETRY


def test_cancelling_stops_the_conversion() -> None:
    """Abbrechen wirkt mitten in der Rechnung, nicht erst danach."""
    from app.core.brep import from_mesh
    from app.core.errors import OperationCancelled
    from app.core.perceive.features import detect

    mesh = _mesh("plate_holes.stl")
    features = detect(mesh)

    class AfterSome:
        """Sagt nach zwanzig Fragen „abgebrochen“."""

        def __init__(self) -> None:
            self.asked = 0

        def is_cancelled(self) -> bool:
            self.asked += 1
            return self.asked > 20

        def raise_if_cancelled(self) -> None:
            if self.is_cancelled():
                raise OperationCancelled

    token = AfterSome()
    with pytest.raises(OperationCancelled):
        from_mesh.convert(mesh, features, tolerance=0.01, cancelled=token)  # type: ignore[arg-type]
    assert token.asked > 20


# --- Der Weg des Kunden: STL rein, umwandeln, Bohrung ändern, speichern, zurück ----


def _plate_project(profile: Profile) -> tuple[Any, Any]:
    from app.core.bootstrap import load_operations
    from app.core.ingest.plan import import_plan
    from app.core.scene import History
    from app.core.scene.project import new_project
    from app.core.types import Source

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    payload = (MESHES / "plate_holes.stl").read_bytes()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    plan = import_plan("src_1", "plate_holes.stl", payload)
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    return project, history


def test_a_downloaded_stl_becomes_step_ready_and_its_hole_changes_exactly(
    tmp_path: Path, profile: Profile
) -> None:
    """Die Abnahme als Kundenweg: umwandeln, Bohrung exakt ändern, speichern, öffnen, Undo."""
    from app.core.brep import step
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, save

    project, history = _plate_project(profile)
    history.apply("Umwandeln", [OperationDraft(op="mesh_to_exact", inputs=("obj_1",))])
    converted = evaluate(project.document, profile, sources=ProjectSources(project))
    assert converted.complete, [
        (finding.code, str(finding.message)) for finding in converted.scene.report.findings
    ]
    entry = converted.scene.objects["obj_1"]
    assert entry.kind == "brep" and isinstance(entry.mesh, Solid)
    codes = {finding.code for finding in converted.scene.report.findings}
    assert {"brep.from_mesh", "brep.from_mesh.deviation"} <= codes
    assert "brep.from_mesh.freeform" not in codes
    done = next(f for f in converted.scene.report.findings if f.code == "brep.from_mesh")
    assert done.values == {"faces": 10, "planes": 6, "cylinders": 4}
    assert "Konstruktionsverlauf" in str(done.message)
    # STEP trägt es jetzt.
    again = step.read(step.write(entry.mesh))
    assert again.volume == pytest.approx(entry.mesh.volume, rel=1e-7)

    hole = next(
        feature
        for feature in entry.features.values()
        if feature.kind == "hole"
        and tuple(feature.params["centre"][:2]) == pytest.approx((-25.0, -15.0))
    )
    history.apply(
        "Bohrung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": hole.id, "diameter": 6.0, "compensate": False},
            )
        ],
    )
    resized = evaluate(project.document, profile, sources=ProjectSources(project))
    assert resized.complete
    after = resized.scene.objects["obj_1"]
    assert after.kind == "brep", "exakt geändert, nicht über das Netz"
    assert not any(finding.converts_exact_body for finding in resized.scene.report.findings)
    removed = math.pi * (3.0**2 - 2.6**2) * 8.0
    assert after.mesh.volume == pytest.approx(entry.mesh.volume - removed, rel=1e-7)

    reopened = load(save(project, tmp_path / "platte.solidon"))
    fresh = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert fresh.complete
    assert fresh.scene.objects["obj_1"].mesh.volume == pytest.approx(after.mesh.volume, rel=1e-9)

    history.undo()
    history.undo()
    back = evaluate(project.document, profile, sources=ProjectSources(project))
    assert back.scene.objects["obj_1"].kind == "mesh", "ein Undo, und das Netz ist zurück"


def test_the_refusals_of_tools_and_export_offer_the_conversion() -> None:
    """Wer am Netz STEP oder ein Werkzeug des exakten Kerns will, bekommt den Weg als Knopf."""
    from app.core.errors import CONVERT_TO_EXACT, EXPORT_AS_MESH, NeedsSolidError
    from app.core.export.writer import _needs_solid

    ways = [action.id for action in _needs_solid().suggestions]
    assert ways[:2] == [CONVERT_TO_EXACT.id, EXPORT_AS_MESH.id]
    assert NeedsSolidError().suggestions[0] == CONVERT_TO_EXACT
    assert CONVERT_TO_EXACT.id == "mesh_to_exact", "die Kennung ist der Name der Operation"


# --- Einzelbefunde aus dem Bau, an nachgebauter Geometrie -------------------------


def test_an_edge_across_the_seam_of_a_closed_spline_takes_the_short_way() -> None:
    """Befund: Die Kante lief den langen Weg um eine geschlossene Schnittkurve.

    ``GeomAPI_IntSS`` liefert den Schnitt eines Zylinders mit einem schräg
    stehenden Kegel als geschlossene, nicht periodische B-Spline. Lag deren
    Anfang mitten in der Kette, spannte die Kante die andere Seite: an einem
    Kundenmodell 36,6 mm Kante auf 16,8 mm Kette, beide Flächen ungültig.
    """
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAdaptor import GeomAdaptor_Curve
    from OCP.GeomAPI import GeomAPI_IntSS

    from app.core.brep import from_mesh

    # Die Maße des Kundenmodells: Zylinder R 8,5, Kegel knapp 45°, um 1,73°
    # gekippt. Um die x-Achse gekippt liefert ``GeomAPI_IntSS`` den oberen
    # Schnitt als **eine** geschlossene B-Spline (Nahtlücke unter 1e-6 mm).
    tilt = math.radians(1.73)
    cylinder = from_mesh.Carrier("cylinder", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), radius=8.5)
    cone = from_mesh.Carrier(
        "cone", (0.0, 0.0, -10.33), (math.sin(tilt), 0.0, math.cos(tilt)), angle=0.7841288
    )
    found = GeomAPI_IntSS(from_mesh._plain_surface(cylinder), from_mesh._plain_surface(cone), 1e-7)
    loops = [found.Line(number) for number in range(1, found.NbLines() + 1)]
    loop = next(
        curve
        for curve in loops
        if not curve.IsPeriodic()
        and curve.Value(curve.FirstParameter()).Distance(curve.Value(curve.LastParameter())) < 1e-6
    )
    first, last = loop.FirstParameter(), loop.LastParameter()
    total = GCPnts_AbscissaPoint.Length_s(GeomAdaptor_Curve(loop))
    span = last - first
    # Eine Kette über den Anfang der Kurve: das letzte Achtel und das erste.
    parameters = np.concatenate(
        (np.linspace(last - span / 8.0, last, 9)[:-1], np.linspace(first, first + span / 8.0, 9))
    )
    points = np.array(
        [(p.X(), p.Y(), p.Z()) for p in (loop.Value(float(value)) for value in parameters)]
    )

    curve = from_mesh.intersection_curve(points, (cylinder, cone), 0.01, closed=False)

    assert curve is not None and curve.kind == "occ"
    length = GCPnts_AbscissaPoint.Length_s(
        GeomAdaptor_Curve(curve.geometry), curve.first, curve.last
    )
    assert length == pytest.approx(total / 4.0, rel=0.01)


def test_a_grazing_plane_does_not_hand_over_the_apex_of_its_ellipse() -> None:
    """Befund: Zwei Kettenpunkte auf beiden Seiten eines Ellipsenscheitels.

    Eine Ebene lag 0,42° schräg zur Achse eines Zylinders R 3,888 und schnitt
    ihn knapp; die Schnittellipse hat dort Hunderte Millimeter Halbachse. Die
    zwei Punkte einer Kette lagen 0,5 mm auseinander auf ihr, aber auf zwei
    Seiten des Scheitels, gut einen Millimeter darunter — und die Kante lief
    um den Scheitel: 2,4 mm auf 0,5 mm Kette (am Kundenmodell). Eine
    Schnittkurve, die so viel länger ist als ihre Kette, gilt nicht.
    """
    from app.core.brep import from_mesh

    radius = 3.888
    inside = 0.02
    tilt = math.radians(0.42)
    cylinder = from_mesh.Carrier("cylinder", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), radius=radius)
    plane = from_mesh.Carrier(
        "plane", (radius - inside, 0.0, 0.0), (math.cos(tilt), 0.0, -math.sin(tilt))
    )

    def on_both(angle: float) -> tuple[float, float, float]:
        height = (inside - radius * (1.0 - math.cos(angle))) / math.tan(tilt)
        return (radius * math.cos(angle), radius * math.sin(angle), height)

    points = np.array([on_both(0.064), on_both(-0.064)])
    assert float(np.abs(plane.distances(points)).max()) < 1e-9
    assert float(np.abs(cylinder.distances(points)).max()) < 1e-9

    curve = from_mesh.intersection_curve(points, (cylinder, plane), 0.01, closed=False)

    chord = float(np.linalg.norm(points[1] - points[0]))
    assert curve is None or _curve_length(curve) <= 1.25 * chord


def _curve_length(curve: Any) -> float:
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAdaptor import GeomAdaptor_Curve

    return float(
        GCPnts_AbscissaPoint.Length_s(GeomAdaptor_Curve(curve.geometry), curve.first, curve.last)
    )


def test_a_corner_lands_exactly_where_its_curves_cross() -> None:
    """Befund: Gemittelte Projektionen blieben 1,7 µm neben dem Kreuzungspunkt.

    Unter 45 Grad nähern sie sich mit dem Faktor 0,85 je Schritt; nach 24
    Schritten schnitt die Parameterkurve der Ellipse die Gerade daneben
    knapp außerhalb der Eckentoleranz, und die Zylinderfläche war ungültig.
    Gauß-Newton trifft den Punkt auf Rundungsgenauigkeit.
    """
    from app.core.brep import from_mesh

    line = from_mesh.Curve(
        "line",
        np.zeros((2, 3)),
        centre=np.array((0.0, 0.0, 0.0)),
        normal=np.array((0.0, 0.0, 1.0)),
    )
    circle = from_mesh.Curve(
        "circle",
        np.zeros((2, 3)),
        centre=np.array((0.0, -5.0, 5.0)),
        normal=np.array((1.0, 0.0, 0.0)),
        radius=math.hypot(5.0, 5.0),
    )
    start = np.array((1e-4, 2e-4, -3e-4))

    corner = from_mesh._on_curves(start, (line, circle), (), start, 1.0)

    assert float(np.linalg.norm(corner - (0.0, 0.0, 0.0))) < 1e-10
