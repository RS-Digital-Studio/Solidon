"""*Stift für Bohrung* baut das Gegenstück zu Senkung, Ansenkung und Gewinde (RM-536).

Kundenwunsch aus dem Fragebogen S-20261006-5be329: „… wenn man ein Gewinde bei
der Bohrung oder Senkung hat, dass man dafür auch das passende Gegenstück mit
der Funktion erzeugen könnte“. Bis dahin entstand an jeder Bohrung ein glatter
Zylinder, so lang wie der Zylinder der Bohrung — an einer Senkbohrung ein
Stift, der unter der Senkung aufhört.

Die Sollwerte kommen von außen: die Maße der Korpusplatten aus
``tests/data/make_corpus.py`` (``plate_countersunk``: Ø 5,2 durch 8 mm, 90° auf
Ø 10 an der Deckfläche z = 4; ``plate_countersunk_blind``: derselbe Kegel, Boden
bei z = -2; ``plate_counterbored``: Ø 5,5 durch 10 mm, Ansenkung Ø 10 × 5), die
Bohrparameter der exakten Quader und das Regelgewinde M6 × 1 nach ISO 261. Das
Spiel ist das des PETG-Profils; der Stift hält überall die Hälfte davon Abstand
zur Wand — senkrecht zur Wand gemessen, auch an der Flanke der Senkung, deren
Mündung deshalb um ``Spiel · √2`` enger ist als die Senkung.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any, Final

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom import bore_pin
from app.core.geom.boolean import shared_volume
from app.core.geom.lid_hinge import BORE_PIN_FEATURE, BORE_PIN_THREAD_FEATURE
from app.core.geom.measure import surface_gap
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.actions import not_offered_at
from app.core.perceive.helix import find_helices
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.project import ProjectSources, load, new_project
from app.core.types import Profile, SceneObject, Source
from app.core.units import MAX_FACET_SAG
from tests.helpers import exact_kernel
from tests.helpers import run_operation as run

MESHES: Final = Path(__file__).parent / "data" / "meshes"
PROJECTS: Final = Path(__file__).parent / "data" / "projects"

#: Die Ringe des Korpus und des Stifts am Netz sind 48-Ecke mit den Ecken auf dem
#: Halbmesser; jede Querschnittsfläche ist um diesen Faktor kleiner als der Kreis.
POLYGON: Final = 48.0 / (2.0 * math.pi) * math.sin(2.0 * math.pi / 48.0)

#: Wie weit der gemessene Abstand unter dem halben Spiel liegen darf: die
#: Facettengrenze (``units.MAX_FACET_SAG``) — Ecken und Sehnen zweier Netze, am
#: exakten Kern die Vernetzung für die Messung.
TOLERANCE: Final = MAX_FACET_SAG


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


def _frustum(low: float, high: float, bottom: float, top: float) -> float:
    return math.pi * (high - low) / 3.0 * (bottom**2 + bottom * top + top**2)


def _cylinder(low: float, high: float, radius: float) -> float:
    return math.pi * radius**2 * (high - low)


def _evaluated(project: Any, profile: Profile) -> SceneObject:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, result.scene.report.findings
    return next(iter(result.scene.objects.values()))


def _plate(
    name: str, profile: Profile, *drafts: OperationDraft, raw: bytes | None = None
) -> SceneObject:
    """Eine Korpusplatte über den Ladeweg der Anwendung, mit erkannten Merkmalen."""
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = raw if raw is not None else (MESHES / name).read_bytes()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    if drafts:
        history.apply("Vorbereiten", list(drafts))
    return _evaluated(project, profile)


def _box(kind: str, profile: Profile, *drafts: OperationDraft) -> SceneObject:
    """Ein Quader 30 × 30 × 12 mm, auf z = 0 stehend, in dem gewählten Kern."""
    if kind == "brep":
        exact_kernel()
    project = new_project("centauri-carbon-2", "petg")
    first = OperationDraft(
        op="create_box" if kind == "mesh" else "create_brep_box",
        params={"width": 30.0, "depth": 30.0, "height": 12.0},
    )
    History(project.document).apply("Quader", [first, *drafts])
    return _evaluated(project, profile)


def _threaded(kind: str, profile: Profile) -> SceneObject:
    """Der Quader mit Ø 5 durch und einem gedruckten M6 von oben, 8 mm lang (z = 4 … 12)."""
    return _box(
        kind,
        profile,
        OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M6", "length": 8.0, "internal": True, "at_feature": "hole_1"},
        ),
    )


def _thread_of(carrier: SceneObject) -> str:
    (name,) = [key for key, entry in carrier.features.items() if entry.kind == "thread"]
    return name


def _gap(pin: SceneObject, carrier: SceneObject) -> float:
    gap = surface_gap(as_mesh_data(pin.mesh), as_mesh_data(carrier.mesh), 2.0)
    assert gap is not None, "der Stift steht weiter als 2 mm von jeder Wand"
    return gap


def _loose(pin: SceneObject, carrier: SceneObject, clearance: float) -> None:
    """Wasserdicht, ohne gemeinsames Volumen, und überall mindestens das halbe Spiel entfernt."""
    mesh = as_mesh_data(pin.mesh)
    assert mesh.raw.is_watertight
    assert shared_volume(mesh.raw, as_mesh_data(carrier.mesh).raw) <= 1e-6, "er steckt lose"
    assert _gap(pin, carrier) >= clearance / 2.0 - TOLERANCE


def _rings(mesh: MeshData) -> dict[float, float]:
    """Je Höhe der größte Abstand einer Ecke von der Z-Achse."""
    vertices = np.asarray(mesh.raw.vertices)
    radii = np.hypot(vertices[:, 0], vertices[:, 1])
    rings: dict[float, float] = {}
    for height, radius in zip(np.round(vertices[:, 2], 6), radii, strict=True):
        rings[float(height)] = max(rings.get(float(height), 0.0), float(radius))
    return rings


def _made(result: Any) -> Any:
    (made,) = [entry for entry in result.findings if entry.code == "pin_for_bore.made"]
    return made


# --- Senkung, Ansenkung -------------------------------------------------------------


def test_a_countersunk_bore_gets_a_flush_countersunk_head(profile: Profile) -> None:
    """``plate_countersunk.stl``: Schaft Ø 5,2 − Spiel, Senkkopf 90°, oben bündig, unten bündig.

    Bis RM-536 endete der Stift bei z = 1,6, wo die Senkung beginnt (Länge 5,6).
    """
    carrier = _plate("plate_countersunk.stl", profile)
    clearance = profile.material.clearance
    gap = clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature="hole_1")
    kept, pin = result.outputs
    assert kept is carrier, "der Träger bleibt unverändert"
    mesh = as_mesh_data(pin.mesh)

    shaft = 2.6 - gap
    top = 5.0 - gap * math.sqrt(2.0)
    corner = 1.6 + gap * (math.sqrt(2.0) - 1.0)
    expected = _cylinder(-4.0, corner, shaft) + _frustum(corner, 4.0, shaft, top)
    assert mesh.volume == pytest.approx(POLYGON * expected, rel=1e-4)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([-4.0, 4.0], abs=1e-6)
    rings = _rings(mesh)
    assert rings[4.0] == pytest.approx(top, abs=1e-6), "Mündung Ø 10 − Spiel · √2"
    flank = math.degrees(2.0 * math.atan((rings[4.0] - shaft) / (4.0 - corner)))
    assert flank == pytest.approx(90.0, abs=0.5), "Kopfwinkel wie die Senkung"
    _loose(pin, carrier, clearance)
    made = _made(result)
    assert made.values["countersink_angle_deg"] == pytest.approx(90.0, abs=0.5)
    assert made.values["head_diameter_mm"] == pytest.approx(2.0 * top, abs=1e-3)
    assert "Senkkopf 90°" in str(made.message)
    assert pin.features[BORE_PIN_FEATURE].params["depth"] == pytest.approx(8.0)


def test_a_blind_countersunk_bore_keeps_the_pin_off_its_floor(profile: Profile) -> None:
    """``plate_countersunk_blind.stl``: Boden bei z = -2 — der Stift endet das halbe Spiel davor."""
    carrier = _plate("plate_countersunk_blind.stl", profile)
    clearance = profile.material.clearance
    gap = clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature="hole_1")
    pin = result.outputs[1]
    mesh = as_mesh_data(pin.mesh)

    shaft = 2.6 - gap
    top = 5.0 - gap * math.sqrt(2.0)
    corner = 1.6 + gap * (math.sqrt(2.0) - 1.0)
    expected = _cylinder(-2.0 + gap, corner, shaft) + _frustum(corner, 4.0, shaft, top)
    assert mesh.volume == pytest.approx(POLYGON * expected, rel=1e-4)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([-2.0 + gap, 4.0], abs=1e-6)
    _loose(pin, carrier, clearance)

    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature="hole_1", length=20.0)
    assert caught.value.constraint == "maximum"
    assert caught.value.values["maximum"] == pytest.approx(6.0 - gap, abs=1e-3)
    assert caught.value.suggestions


def test_a_counterbore_gets_a_cylinder_head_above_its_shoulder(profile: Profile) -> None:
    """``plate_counterbored.stl``: Schaft Ø 5,5 − Spiel, Kopf Ø 10 − Spiel ab Stufe + Spiel/2."""
    carrier = _plate("plate_counterbored.stl", profile)
    clearance = profile.material.clearance
    gap = clearance / 2.0
    narrow = min(
        (entry for entry in carrier.features.values() if entry.kind == "hole"),
        key=lambda entry: entry.params["diameter"],
    )
    result = run("pin_for_bore", carrier, profile, at_feature=narrow.id)
    pin = result.outputs[1]
    mesh = as_mesh_data(pin.mesh)

    expected = _cylinder(-5.0, gap, 2.75 - gap) + _cylinder(gap, 5.0, 5.0 - gap)
    assert mesh.volume == pytest.approx(POLYGON * expected, rel=1e-4)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([-5.0, 5.0], abs=1e-6)
    rings = _rings(mesh)
    assert rings[5.0] == pytest.approx(5.0 - gap, abs=1e-6)
    assert rings[round(gap, 6)] == pytest.approx(5.0 - gap, abs=1e-6), "Kopf über der Stufe"
    _loose(pin, carrier, clearance)
    made = _made(result)
    assert "countersink_angle_deg" not in made.values, "ein Zylinderkopf"
    assert "Zylinderkopf" in str(made.message)
    assert made.values["head_diameter_mm"] == pytest.approx(10.0 - clearance, abs=1e-3)


@pytest.mark.parametrize("angle", [90.0, 180.0])
def test_the_exact_kernel_builds_the_same_heads(angle: float, profile: Profile) -> None:
    """Exakt gebohrt: Ø 5,2 durch 12 mm, Aufweitung Ø 10 (90° Senkung, 180° Ansenkung 4 mm)."""
    widening = {"widening_diameter": 10.0, "transition_angle": angle, "compensate": False}
    if angle == 180.0:
        widening["widening_depth"] = 4.0
    carrier = _box(
        "brep",
        profile,
        OperationDraft(
            op="drill_hole", inputs=("obj_1",), params={"diameter": 5.2, "z": 12.0, **widening}
        ),
    )
    clearance = profile.material.clearance
    gap = clearance / 2.0
    narrow = min(
        (entry for entry in carrier.features.values() if entry.kind == "hole"),
        key=lambda entry: entry.params["diameter"],
    )
    result = run("pin_for_bore", carrier, profile, at_feature=narrow.id)
    pin = result.outputs[1]
    assert pin.kind == "brep", "der exakte Träger bekommt einen exakten Stift"
    shaft = 2.6 - gap
    if angle == 90.0:
        corner = 9.6 + gap * (math.sqrt(2.0) - 1.0)
        top = 5.0 - gap * math.sqrt(2.0)
        expected = _cylinder(0.0, corner, shaft) + _frustum(corner, 12.0, shaft, top)
    else:
        top = 5.0 - gap
        expected = _cylinder(0.0, 8.0 + gap, shaft) + _cylinder(8.0 + gap, 12.0, top)
    assert pin.mesh.volume == pytest.approx(expected, rel=1e-6)
    assert _made(result).values["head_diameter_mm"] == pytest.approx(2.0 * top, abs=1e-3)
    _loose(pin, carrier, clearance)


def test_the_plain_pin_is_the_cylinder_from_before(profile: Profile) -> None:
    """„Glatter Stift“ an der Senkbohrung: Ø 5,2 − Spiel, 5,6 lang — wie vor RM-536."""
    carrier = _plate("plate_countersunk.stl", profile)
    gap = profile.material.clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature="hole_1", shape="plain_pin")
    mesh = as_mesh_data(result.outputs[1].mesh)
    assert mesh.volume == pytest.approx(POLYGON * _cylinder(-4.0, 1.6, 2.6 - gap), rel=1e-4)
    assert "dick" in str(_made(result).message)


# --- Gewinde ------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_an_inner_thread_gets_an_outer_thread_of_the_same_size(kind: str, profile: Profile) -> None:
    """Gedrucktes M6 (z = 4 … 12) über Ø 5,2: Gewindestift M6 × 1 (ISO 261), Kamm 6 − Spiel.

    Unten endet er das halbe Spiel vor dem Absatz, an dem die Gänge der Bohrung
    in die engere Bohrung übergehen; oben an der offenen Mündung bündig.
    """
    carrier = _threaded(kind, profile)
    clearance = profile.material.clearance
    gap = clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier))
    pin = result.outputs[1]
    assert pin.kind == kind
    mesh = as_mesh_data(pin.mesh)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([4.0 + gap, 12.0], abs=1e-3)
    radii = np.hypot(mesh.raw.vertices[:, 0], mesh.raw.vertices[:, 1])
    assert float(radii.max()) == pytest.approx((6.0 - clearance) / 2.0, abs=2e-3)
    helices = find_helices(mesh)
    assert helices, "der Stift trägt eine Wendel"
    assert helices[0].pitch == pytest.approx(1.0, abs=0.02), "Steigung M6 nach ISO 261"
    _loose(pin, carrier, clearance)
    made = _made(result)
    assert (made.values["thread"], made.values["pitch_mm"]) == ("M6 × 1", 1.0)
    assert "M6 × 1" in str(made.message)
    thread = pin.features[BORE_PIN_THREAD_FEATURE]
    assert thread.params["internal"] is False
    assert thread.params["nominal"] == pytest.approx(6.0)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_printed_blind_inner_thread_gets_its_pin(kind: str, profile: Profile) -> None:
    """*Druckbares Gewinde* innen, frei gesetzt in den vollen Quader (z = 4 … 12), ohne Bohrung.

    Der Weg, den die Karte am gedruckten Innengewinde jetzt anbietet (RM-536,
    Entscheidung Robert 07.10.2026): Gewindestift M6 × 1, Kamm 6 − Spiel, unten
    das halbe Spiel über dem Grund des Sacklochs, oben an der Mündung bündig.
    """
    carrier = _box(
        kind,
        profile,
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M6", "length": 8.0, "internal": True, "z": 12.0},
        ),
    )
    clearance = profile.material.clearance
    gap = clearance / 2.0
    name = _thread_of(carrier)
    assert carrier.features[name].created_by is not None, "ein gedrucktes Gewinde"
    result = run("pin_for_bore", carrier, profile, at_feature=name)
    pin = result.outputs[1]
    assert pin.kind == kind
    mesh = as_mesh_data(pin.mesh)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([4.0 + gap, 12.0], abs=1e-3)
    radii = np.hypot(mesh.raw.vertices[:, 0], mesh.raw.vertices[:, 1])
    assert float(radii.max()) == pytest.approx((6.0 - clearance) / 2.0, abs=2e-3)
    helices = find_helices(mesh)
    assert helices and helices[0].pitch == pytest.approx(1.0, abs=0.02)
    _loose(pin, carrier, clearance)
    assert _made(result).values["thread"] == "M6 × 1"


def test_the_bolt_is_turned_into_the_grooves_it_finds(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Derselbe Träger, um 100° um seine Gewindeachse gedreht: Die Gänge stehen anders.

    Gemessen wird die Lage an den Ecken des Trägers (``bore_pin.thread_turn``);
    ohne sie stünde der Gang des Stifts im Gang der Bohrung — die Gegenprobe.
    """
    carrier = _threaded("mesh", profile)
    turned = carrier.mesh.raw.copy()
    turned.apply_transform(trimesh.transformations.rotation_matrix(math.radians(100.0), (0, 0, 1)))
    carrier = dataclasses.replace(carrier, mesh=MeshData.of(turned))
    clearance = profile.material.clearance
    pin = run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier)).outputs[1]
    _loose(pin, carrier, clearance)

    monkeypatch.setattr(bore_pin, "thread_turn", lambda *args, **kwargs: (0.0, 0.0))
    blind = run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier)).outputs[1]
    assert shared_volume(as_mesh_data(blind.mesh).raw, turned) > 1.0, "ungedreht im Gang"


def test_a_countersunk_thread_gets_a_countersunk_screw(profile: Profile) -> None:
    """Senkung + Gewinde: ``plate_countersunk.stl`` mit M6 auf 4 mm unter der Senkung.

    ``insert_printed_thread`` nimmt die Bohrung heraus (``hole_1`` fehlt danach),
    gewählt wird das Gewinde. Senkkopf 90° wie oben, Gewinde von z = -2,4 + Spiel/2
    bis an die Senkung.
    """
    carrier = _plate(
        "plate_countersunk.stl",
        profile,
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M6", "length": 4.0, "internal": True, "at_feature": "hole_1"},
        ),
    )
    assert "hole_1" not in carrier.features
    clearance = profile.material.clearance
    gap = clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier))
    pin = result.outputs[1]
    mesh = as_mesh_data(pin.mesh)
    assert mesh.raw.bounds[:, 2].tolist() == pytest.approx([-2.4 + gap, 4.0], abs=1e-3)
    assert _rings(mesh)[4.0] == pytest.approx(5.0 - gap * math.sqrt(2.0), abs=1e-6)
    _loose(pin, carrier, clearance)
    made = _made(result)
    assert made.values["countersink_angle_deg"] == pytest.approx(90.0, abs=0.5)
    assert made.values["thread"] == "M6 × 1"
    assert "Senkkopf 90°" in str(made.message) and "M6 × 1" in str(made.message)


# --- Bausteinbohrungen (RM-552) ----------------------------------------------------


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("part", ["screw_hole", "screw_hole_head_room", "heatset_m4"])
def test_a_part_bore_that_runs_through_its_countersink_gets_its_pin(
    kind: str, part: str, profile: Profile
) -> None:
    """RM-552: Die Bausteinbohrung läuft durch ihre Senkung — der Stift baut trotzdem.

    Am Schraubenloch reicht die Bohrung Ø 3,4 bis zur Mündung z 12, die Senkung
    beginnt bei z 10,7; an der Einpressbuchse ebenso durch die Einführfase.
    ``bore_pin._following`` verlangte, dass ein Abschnitt am Ende des vorigen
    beginnt, und sagte über einen Hohlraum, den Solidon selbst gebaut hat,
    „lässt sich hier nicht eindeutig lesen“. Die Senkung des Bausteins nennt
    dazu ihre Mitte und Höhe statt ihres weiten Rands.

    Sollwerte aus der Normteiltabelle und den Bausteinmaßen: M3 durch Ø 3,4,
    Senkung 90° auf Ø 6, Tiefe 10 im Quader 12 hoch (Boden z 2), mit Kopftiefe
    2 die Senkung 2 mm tiefer und darüber die Kopfaussparung Ø 6 bis zur
    Mündung; Einpressbuchse M3 Loch Ø 4, Länge 5,7 plus Zusatztiefe 0,5 (Boden
    z 5,8), Einführfase 0,5 mm unter 45° (``fasteners.INSERT_LEAD_IN``). Der
    Stift hält überall das halbe Spiel, an der Flanke senkrecht zu ihr, und
    steht vor dem Boden um dasselbe ab.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import INSERT_LEAD_IN

    room = 2.0 if part == "screw_hole_head_room" else 0.0
    if part.startswith("screw_hole"):
        screw = standards.screw("M3")
        bore, sink = screw.clearance / 2.0, screw.countersink / 2.0
        floor = 12.0 - 10.0
        op, name = "insert_screw_hole", "screw_hole_bore_1"
        params: dict[str, Any] = {"size": "M3", "depth": 10.0, "head_room": room}
    else:
        insert = standards.insert("M3")
        bore, sink = insert.hole / 2.0, insert.hole / 2.0 + INSERT_LEAD_IN
        floor = 12.0 - (insert.length + 0.5)
        op, name = "insert_heatset_m4", "heatset_m4_bore_1"
        params = {"size": "M3", "extra_depth": 0.5, "lead_in": True}
    carrier = _box(
        kind, profile, OperationDraft(op=op, inputs=("obj_1",), params={"z": 12.0, **params})
    )
    clearance = profile.material.clearance
    gap = clearance / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature=name)
    kept, pin = result.outputs
    assert kept is carrier
    assert pin.kind == kind
    shaft = bore - gap
    rim = 12.0 - room
    corner = rim - (sink - bore) + gap * (math.sqrt(2.0) - 1.0)
    expected = _cylinder(floor + gap, corner, shaft)
    if room:
        upper = rim + gap * (math.sqrt(2.0) - 1.0)
        expected += _frustum(corner, upper, shaft, sink - gap)
        expected += _cylinder(upper, 12.0, sink - gap)
    else:
        top = sink - gap * math.sqrt(2.0)
        expected += _frustum(corner, 12.0, shaft, top)
    volume = float(pin.mesh.volume if kind == "brep" else as_mesh_data(pin.mesh).volume)
    assert volume == pytest.approx((1.0 if kind == "brep" else POLYGON) * expected, rel=1e-4)
    bounds = as_mesh_data(pin.mesh).raw.bounds
    assert bounds[:, 2].tolist() == pytest.approx([floor + gap, 12.0], abs=1e-3)
    _loose(pin, carrier, clearance)
    made = _made(result)
    if room:
        # Der weiteste Abschnitt ist die Kopfaussparung: ein Zylinderkopf darüber.
        assert made.values["head_diameter_mm"] == pytest.approx(2.0 * (sink - gap), abs=1e-3)
    else:
        assert made.values["countersink_angle_deg"] == pytest.approx(90.0, abs=0.5)
        assert made.values["head_diameter_mm"] == pytest.approx(2.0 * top, abs=1e-3)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_magnet_pocket_from_a_part_still_has_a_narrowing_mouth(
    kind: str, profile: Profile
) -> None:
    """RM-552, Gegenfall: Die Lippe der Magnettasche ist enger als die Tasche — der Stift
    passender Form käme nicht hinein, auch wenn überlappende Glieder jetzt gekürzt werden."""
    carrier = _box(
        kind,
        profile,
        OperationDraft(op="insert_magnet_pocket", inputs=("obj_1",), params={"z": 12.0}),
    )
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature="magnet_pocket_pocket_1")
    assert caught.value.constraint == "narrowing_mouth"
    assert caught.value.suggestions


# --- Absagen ------------------------------------------------------------------------


def _both_sides_sunk() -> bytes:
    """Die Platte aus ``plate_countersunk`` mit derselben Senkung auch unten."""
    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
    upper = trimesh.creation.cone(radius=5.0, height=5.0, sections=48)
    upper.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0)))
    upper.apply_translation((0.0, 0.0, 4.0))
    lower = trimesh.creation.cone(radius=5.0, height=5.0, sections=48)
    lower.apply_translation((0.0, 0.0, -4.0))
    body = trimesh.boolean.difference([plate, drill, upper, lower])
    return bytes(trimesh.exchange.stl.export_stl(body))


def test_a_bore_sunk_at_both_ends_refuses_a_head(profile: Profile) -> None:
    carrier = _plate("both_sides.stl", profile, raw=_both_sides_sunk())
    (hole,) = [key for key, entry in carrier.features.items() if entry.kind == "hole"]
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature=hole)
    assert caught.value.constraint == "two_heads"
    assert caught.value.suggestions
    plain = run("pin_for_bore", carrier, profile, at_feature=hole, shape="plain_pin")
    assert as_mesh_data(plain.outputs[1].mesh).volume > 0.0, "der Ausweg aus dem Satz geht"


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        ({"internal": False}, "not_a_bore"),
        ({"handedness": "left"}, "left_handed"),
        ({"starts": 2}, "multi_start"),
        ({"taper": 1.79}, "thread_shape"),
    ],
)
def test_a_thread_without_a_counterpart_says_why(
    change: dict[str, Any], constraint: str, profile: Profile
) -> None:
    """Dieselben Absagen wie das Gegenstück zum Gewinde, dazu das Außengewinde."""
    carrier = _threaded("mesh", profile)
    name = _thread_of(carrier)
    feature = carrier.features[name]
    altered = dataclasses.replace(feature, params={**feature.params, **change})
    carrier = dataclasses.replace(carrier, features={**carrier.features, name: altered})
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature=name)
    assert caught.value.constraint == constraint
    assert caught.value.suggestions


def _short_thread(profile: Profile, length: float) -> SceneObject:
    """Der Quader mit Ø 5 durch und einem gedruckten M6 von oben, ``length`` lang."""
    return _box(
        "mesh",
        profile,
        OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M6", "length": length, "internal": True, "at_feature": "hole_1"},
        ),
    )


def test_a_thread_too_short_for_a_printed_pin_opens_its_own_step(profile: Profile) -> None:
    """Ein gedrucktes M6 von 2 mm lässt dem Stift 2 − Spiel/2: zu kurz, mit eigenem Satz.

    Der Gewindebaustein druckt ab 2 mm (``ThreadParams.length``). Unter der Mündung
    endet der Bolzen um das halbe Spiel vor der engeren Bohrung; bis Review P2
    (Bausteine, M2) kam die Grenzmeldung des Bausteins am Feld *Länge* des Stifts
    durch, und keine Länge half. Die Absage nennt beide Zahlen und öffnet den
    Gewindeschritt am Feld *Länge*; an 2,2 mm baut der Stift.
    """
    gap = profile.material.clearance / 2.0
    carrier = _short_thread(profile, 2.0)
    name = _thread_of(carrier)
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature=name)
    error = caught.value
    assert error.constraint == "thread_too_short"
    assert error.suggestions[0].id == "change_creating_step"
    assert error.values["creating_step"] == carrier.features[name].created_by is not None
    assert error.values["field"] == "length"
    assert error.values["room"] == pytest.approx(2.0 - gap, abs=1e-3)
    assert "Mindestwert" not in str(error.detail) and "zu kurz" in str(error.detail)

    longer = _short_thread(profile, 2.2)
    result = run("pin_for_bore", longer, profile, at_feature=_thread_of(longer))
    assert _made(result).values["length_mm"] == pytest.approx(2.2 - gap, abs=1e-3)
    assert not [entry for entry in result.findings if entry.code == "pin_for_bore.lengthened"]


@pytest.mark.parametrize("length", [1.0, 2.0, 3.0])
def test_a_short_countersunk_screw_gets_the_shortest_printable_thread(
    length: float, profile: Profile
) -> None:
    """Senkung + M6 × 4 mit eingetragener Länge 1–3 mm: Das Gewinde wird 2 mm, gesagt.

    Unter dem Senkkopf bliebe dem Gewinde bei 1 und 2 mm nichts, bei 3 mm 0,6 mm;
    die Bohrung reicht für die kürzeste druckbare Länge 2 mm, also bekommt der
    Stift sie (Review P2 Bausteine, M2). Das Gewinde endet unter der Senkung um
    das halbe Spiel früher (``_thread_top``) — dort, wo es im Test ohne Länge
    endet; der Stift reicht 2 mm darunter.
    """
    carrier = _plate(
        "plate_countersunk.stl",
        profile,
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M6", "length": 4.0, "internal": True, "at_feature": "hole_1"},
        ),
    )
    name = _thread_of(carrier)
    whole = run("pin_for_bore", carrier, profile, at_feature=name)
    thread_top = whole.outputs[1].features[BORE_PIN_THREAD_FEATURE]
    end = float(thread_top.params["centre"][2]) + float(thread_top.params["length"]) / 2.0
    result = run("pin_for_bore", carrier, profile, at_feature=name, length=length)
    pin = result.outputs[1]
    bounds = as_mesh_data(pin.mesh).raw.bounds[:, 2]
    assert bounds[0] == pytest.approx(end - 2.0, abs=1e-3)
    assert bounds[1] == pytest.approx(4.0, abs=1e-3)
    (said,) = [entry for entry in result.findings if entry.code == "pin_for_bore.lengthened"]
    assert said.severity == "warning" and said.values["field"] == "length"
    assert _made(result).values["length_mm"] == pytest.approx(4.0 - (end - 2.0), abs=1e-3)
    _loose(pin, carrier, profile.material.clearance)


def test_a_measured_thread_rounded_to_its_size_says_so_at_the_pin(profile: Profile) -> None:
    """Gemessen 6,0 x 1,03, gebaut M6 x 1: Der Stift sagt es wie das Gegenstück (Review P2, G4).

    Dieselbe Entscheidung (``counterpart._matched_thread``) liefert Maß und Satz;
    der Stift nahm das Maß und schwieg. Der Satz nennt den Träger.
    """
    carrier = _threaded("mesh", profile)
    name = _thread_of(carrier)
    feature = carrier.features[name]
    measured = dataclasses.replace(
        feature,
        provenance="native",
        params={**feature.params, "pitch": 1.03, "uncertainty": 0.05, "handedness": "right"},
    )
    carrier = dataclasses.replace(carrier, features={**carrier.features, name: measured})
    result = run("pin_for_bore", carrier, profile, at_feature=name)
    assert _made(result).values["thread"] == "M6 × 1"
    (note,) = [
        entry for entry in result.findings if entry.code == "parts.counterpart_standard_size"
    ]
    assert note.values["size"] == "M6" and note.object_ids == (carrier.id,)


def _altered(carrier: SceneObject, name: str, **params: Any) -> SceneObject:
    """Der Träger mit geänderten Kennzahlen eines Merkmals — der Fall ohne eigenes Netz."""
    feature = carrier.features[name]
    altered = dataclasses.replace(feature, params={**feature.params, **params})
    return dataclasses.replace(carrier, features={**carrier.features, name: altered})


def _cone_of(carrier: SceneObject) -> str:
    (name,) = [key for key, entry in carrier.features.items() if entry.kind == "cone"]
    return name


def _tilted(vector: Any, degrees: float) -> tuple[float, float, float]:
    """``vector`` um ``degrees`` zur x-Achse hin gekippt (für eine Achse längs z)."""
    sign = 1.0 if float(vector[2]) >= 0.0 else -1.0
    angle = math.radians(degrees)
    return (math.sin(angle), 0.0, sign * math.cos(angle))


def test_a_countersink_slightly_off_the_axis_still_reads_like_the_recognition(
    profile: Profile,
) -> None:
    """Eine Senkung 1,5° schräg und 0,1 mm daneben ist dieselbe Kette (Review P2, G3).

    Die Erkennung nimmt bis ``SINK_AXIS_LIMIT`` (2°) und ``r · SINK_FIT_LIMIT``
    quer; der Stift prüfte mit 0,29° und 0,05 mm und sagte zu einer Kette, die
    der Bericht eben noch nannte, „lässt sich nicht eindeutig lesen“. Jenseits
    von 2° bleibt die Absage.
    """
    carrier = _plate("plate_countersunk.stl", profile)
    cone = _cone_of(carrier)
    feature = carrier.features[cone]
    centre = [float(value) for value in feature.params["centre"]]
    near = _altered(
        carrier,
        cone,
        axis=_tilted(feature.params["axis"], 1.5),
        centre=(centre[0] + 0.1, centre[1], centre[2]),
    )
    result = run("pin_for_bore", near, profile, at_feature="hole_1")
    assert _made(result).values["countersink_angle_deg"] == pytest.approx(90.0, abs=0.5)

    far = _altered(carrier, cone, axis=_tilted(feature.params["axis"], 10.0))
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", far, profile, at_feature="hole_1")
    assert caught.value.constraint == "chain_unreadable"
    assert caught.value.suggestions


def _plate_with_a_shifted_countersink(shift: float, profile: Profile) -> SceneObject:
    """Platte 30 x 30 x 8, Bohrung Ø 5,2 durch, Senkung 90° bis Ø 10,4, um ``shift`` in x versetzt.

    Geladen über den Ladeweg der Anwendung, damit die Erkennung die Kette liest.
    """
    import io as buffers

    box = trimesh.creation.box(extents=(30.0, 30.0, 8.0))
    box.apply_translation((0.0, 0.0, 4.0))
    bore = trimesh.creation.cylinder(radius=2.6, height=20.0, sections=96)
    bore.apply_translation((0.0, 0.0, 4.0))
    cone = trimesh.creation.cone(radius=5.2 + 1.0, height=(10.4 - 5.2) / 2.0 + 1.0, sections=96)
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0)))
    cone.apply_translation((shift, 0.0, 9.0))
    buffer = buffers.BytesIO()
    box.difference(bore).difference(cone).export(buffer, file_type="stl")
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = buffer.getvalue()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/versatz.stl", sha256=""
    )
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return next(iter(result.scene.objects.values()))


def test_a_countersink_beside_the_axis_keeps_the_clearance_all_round(profile: Profile) -> None:
    """Eine Senkung 0,15 mm neben der Bohrung: Der Kopf hält rundum das halbe Spiel (Review P2 N7).

    Die Kette liest sie als gleichachsig (``r · SINK_FIT_LIMIT``), gebaut wird
    der Stift um die Achse der Bohrung. Vorher stand der Kopf auf der einen
    Seite 0,05 mm vor der Wand statt 0,125 mm — am echten Netz gemessen, denn
    an den Kennzahlen allein sieht man es nicht.
    """
    carrier = _plate_with_a_shifted_countersink(0.15, profile)
    holes = [name for name, entry in carrier.features.items() if entry.kind == "hole"]
    cones = [name for name, entry in carrier.features.items() if entry.kind == "cone"]
    assert len(holes) == 1 and len(cones) == 1, "sonst liest die Erkennung keine Kette"
    beside = math.hypot(*carrier.features[cones[0]].params["centre"][:2])
    assert beside > 0.1, "die Senkung sitzt erkennbar neben der Achse"
    result = run("pin_for_bore", carrier, profile, at_feature=holes[0])
    _loose(result.outputs[1], carrier, profile.material.clearance)


def test_a_countersink_narrower_than_its_bore_is_a_narrowing_mouth(profile: Profile) -> None:
    """Eine „Senkung“ enger als die Bohrung ist eine Verengung: Der Stift sagt es ab (G6)."""
    carrier = _plate("plate_countersunk.stl", profile)
    narrow = _altered(carrier, _cone_of(carrier), diameter=4.0)
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", narrow, profile, at_feature="hole_1")
    assert caught.value.constraint == "narrowing_mouth"
    assert caught.value.suggestions


def test_a_bore_narrower_above_its_thread_refuses_the_pin() -> None:
    """Über dem Gewinde eine engere Bohrung: Durch sie käme der Stift nicht (G6).

    Ein M6 auf z = 0 … 5 und darüber die gewählte Bohrung Ø 5 auf z = 4 … 12,
    in ihrem eigenen Rahmen (``_threaded_bore``); eine weite Bohrung Ø 8
    darüber ist die Gegenprobe.
    """
    origin = np.zeros(3)
    axis = np.array([0.0, 0.0, 1.0])
    zone = bore_pin.ThreadZone(0.0, 5.0, 6.0, 1.0, {"size": "M6"}, "thread_1")
    narrow = [bore_pin.Section(4.0, 12.0, 2.5, 2.5, "hole_1")]
    with pytest.raises(ValidationError) as caught:
        bore_pin._threaded_bore(origin, axis, narrow, zone, "hole_1")
    assert caught.value.constraint == "narrow_above_thread"
    assert caught.value.suggestions
    wide = [bore_pin.Section(4.0, 12.0, 4.0, 4.0, "hole_1")]
    cavity = bore_pin._threaded_bore(origin, axis, wide, zone, "hole_1")
    assert [(entry.start, entry.end) for entry in cavity.sections] == [(5.0, 12.0)]


def test_a_clearance_as_wide_as_the_bore_leaves_no_pin() -> None:
    """Ein Spiel, das den Schaft auf null bringt, sagt ``CLEARANCE_TOO_LARGE`` am Feld Spiel (G6).

    Bohrung Ø 2 mit Senkung bis Ø 6 und das größte Spiel 2 mm: Vom Schaft bliebe
    Halbmesser 0. Mit 1 mm Spiel bleibt er (Gegenprobe).
    """
    sections = [
        bore_pin.Section(0.0, 8.0, 1.0, 1.0, "hole_1"),
        bore_pin.Section(8.0, 10.0, 1.0, 3.0, "cone_1"),
    ]
    with pytest.raises(ValidationError) as caught:
        bore_pin.outline(sections, 0.0, 10.0, 1.0)
    assert caught.value.detail == bore_pin.CLEARANCE_TOO_LARGE
    assert caught.value.field == "clearance" and caught.value.suggestions
    assert bore_pin.outline(sections, 0.0, 10.0, 0.5)[1][0] == pytest.approx(0.5)


def test_a_thread_whose_turn_cannot_be_measured_says_so(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Messung der Gänge baut der Stift und warnt, mit dem Träger im Befund (G6)."""
    monkeypatch.setattr(bore_pin, "thread_turn", lambda *args, **kwargs: None)
    carrier = _threaded("mesh", profile)
    result = run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier))
    (said,) = [entry for entry in result.findings if entry.code == "pin_for_bore.thread_unmeasured"]
    assert said.severity == "warning" and said.suggestions
    assert said.object_ids == (carrier.id,)


def test_the_plain_pin_does_not_go_into_a_thread(profile: Profile) -> None:
    carrier = _threaded("mesh", profile)
    with pytest.raises(ValidationError) as caught:
        run("pin_for_bore", carrier, profile, at_feature=_thread_of(carrier), shape="plain_pin")
    assert caught.value.constraint == "needs_a_bore"
    assert caught.value.suggestions


def test_an_outer_thread_does_not_offer_the_pin(profile: Profile) -> None:
    carrier = _threaded("mesh", profile)
    inner = carrier.features[_thread_of(carrier)]
    outer = dataclasses.replace(inner, params={**inner.params, "internal": False})
    assert "pin_for_bore" not in not_offered_at(inner)
    assert "pin_for_bore" in not_offered_at(outer)


# --- Projektdatei -------------------------------------------------------------------

#: Was der Stand vor RM-536 (``63d7a7826``, Format 46) aus ``pin_for_bore_v46.p3d``
#: rechnete, gemessen beim Schreiben: Volumen in mm³ und Höhe von unten nach oben.
#: ``obj_2`` steht in ``plate_countersunk.stl`` (Netz), ``obj_4`` in der Stufenbohrung
#: eines exakten Quaders bei x = 60.
SAVED_PIN_RESULT: Final = {
    "obj_2": (107.4601, (-4.0, 1.6)),
    "obj_4": (162.6896, (0.0, 7.0)),
}


def _pins(
    document: Any, project: Any, profile: Profile
) -> dict[str, tuple[float, tuple[float, float]]]:
    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete, result.scene.report.findings
    measured = {}
    for name in SAVED_PIN_RESULT:
        mesh = as_mesh_data(result.scene.objects[name].mesh)
        low, high = (float(value) for value in mesh.raw.bounds[:, 2])
        measured[name] = (float(mesh.volume), (low, high))
    return measured


def test_a_saved_pin_keeps_the_shape_it_was_saved_with(profile: Profile) -> None:
    """Format 46 → 48: Ein gespeicherter Stift bleibt der glatte Zylinder (RM-536).

    Mit der Form von heute bekäme der Stift in der Senkbohrung einen Senkkopf und
    reichte durch die ganze Platte — still, nach dem Update. Die Gegenprobe zeigt es.
    """
    exact_kernel()
    path = PROJECTS / "pin_for_bore_v46.p3d"
    project = load(path)
    assert project.document.format_version == FORMAT_VERSION
    pins = [entry for entry in project.document.ops if entry.op == "pin_for_bore"]
    assert [entry.params["shape"] for entry in pins] == ["plain_pin", "plain_pin"]
    measured = _pins(project.document, project, profile)
    for name, (volume, heights) in SAVED_PIN_RESULT.items():
        assert measured[name][0] == pytest.approx(volume, abs=1e-3), name
        assert measured[name][1] == pytest.approx(heights, abs=1e-3), name

    history = History(project.document)
    history.change_params(pins[0].id, {**pins[0].params, "shape": "to_the_bore"})
    today = _pins(project.document, project, profile)
    assert today["obj_2"][1] == pytest.approx((-4.0, 4.0), abs=1e-3), "mit Senkkopf bis oben"
    assert today["obj_2"][0] > SAVED_PIN_RESULT["obj_2"][0] + 50.0


@pytest.mark.parametrize("saved", [40, 46])
def test_the_migration_marks_every_saved_pin_and_only_pins(saved: int) -> None:
    """Auch die Fassungen einer Änderung (``before``/``after``) — und eine eigene Wahl bleibt."""

    def pin_step(**params: Any) -> dict[str, Any]:
        return {
            "id": 2,
            "op": "pin_for_bore",
            "in": ["obj_1"],
            "out": ["obj_1", "obj_2"],
            "params": params,
        }

    data = {
        "format_version": saved,
        "ops": [
            {"id": 1, "op": "create_box", "in": [], "out": ["obj_1"], "params": {}},
            pin_step(at_feature="hole_1"),
            pin_step(at_feature="hole_2", shape="to_the_bore"),
        ],
        "transactions": [
            {
                "changes": {
                    "before": {"edited_ops": {"2": pin_step(at_feature="hole_1")}},
                    "after": None,
                }
            }
        ],
    }
    migrated = migrate(data)

    assert migrated["format_version"] == FORMAT_VERSION
    assert "shape" not in migrated["ops"][0]["params"]
    assert migrated["ops"][1]["params"]["shape"] == "plain_pin"
    assert migrated["ops"][2]["params"]["shape"] == "to_the_bore", "eine genannte Form bleibt"
    edited = migrated["transactions"][0]["changes"]["before"]["edited_ops"]["2"]
    assert edited["params"]["shape"] == "plain_pin"


# --- Review G, F2: an jeder Bausteinbohrung ein Stift im Körper oder eine Absage ----------

#: Die abtragenden Bausteine, die Bohrungen erklären — jeder von Hand auf die Deckfläche.
_SUBTRACTIVE_PARTS: Final = (
    "bearing_seat",
    "cable_gland",
    "heatset_m4",
    "hose_barb",
    "keyhole",
    "magnet_pocket",
    "nut_trap",
    "screw_hole",
    "seal_groove",
)


def test_the_list_of_subtractive_parts_is_complete() -> None:
    """Die Liste oben ist die des Registers — ein neuer Baustein fällt hier auf."""
    from app.core.knowledge.parts.registry import PARTS

    assert {spec.name for spec in PARTS.all() if spec.subtractive} == set(_SUBTRACTIVE_PARTS)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("part", _SUBTRACTIVE_PARTS)
def test_every_offered_pin_at_a_part_bore_stands_in_the_body_or_says_why(
    profile: Profile, kind: str, part: str
) -> None:
    """Review G, F2: Die Karte bot *Stift für Bohrung* an Bausteinbohrungen an, an
    denen er Unsinn baute.

    An der Einführfase der Einpressbuchse eine Scheibe Ø 4,75 × 0,5, an
    Tasche und Schraubenloch einer Mutternfalle Stifte über dem Körper, 12,5 mm
    aus dem Teil heraus — ohne Befund. Soll: An jeder Bohrung, an der die Karte
    ihn anbietet, steht der Stift lose im Körper (dicht, ohne gemeinsames
    Volumen, überall das halbe Spiel entfernt, innerhalb seiner Grenzen),
    oder die Operation sagt ab, mit einem Weg.
    """
    from app.core.knowledge.profiles import for_object
    from app.core.perceive.actions import OFFERED_AT_A_PART

    if kind == "brep":
        exact_kernel()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [
            OperationDraft(
                op="create_box" if kind == "mesh" else "create_brep_box",
                params={"width": 30.0, "depth": 30.0, "height": 12.0},
            ),
            OperationDraft(op=f"insert_{part}", inputs=("obj_1",), params={"z": 12.0}),
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    if not result.complete:
        # Ein Baustein, der eine Stelle verlangt (die Dichtungsnut eine Kante),
        # sagt von Hand gesetzt mit Weg ab — dann gibt es keine Bohrung zu fragen.
        assert all(finding.suggestions for finding in result.scene.report.findings), part
        return
    carrier = next(iter(result.scene.objects.values()))
    clearance = for_object(profile, carrier).material.clearance
    body = as_mesh_data(carrier.mesh)
    offered = [
        name
        for name, feature in sorted(carrier.features.items())
        if feature.provenance == "generated"
        and feature.kind in OFFERED_AT_A_PART["pin_for_bore"]
        and "pin_for_bore" not in not_offered_at(feature)
    ]
    for name in offered:
        try:
            result = run("pin_for_bore", carrier, profile, at_feature=name)
        except ValidationError as refusal:
            assert refusal.suggestions, (part, name, refusal.constraint)
            continue
        pin = result.outputs[1]
        _loose(pin, carrier, clearance)
        made = as_mesh_data(pin.mesh)
        lowest = np.asarray(body.bounds.minimum) - 0.02
        highest = np.asarray(body.bounds.maximum) + 0.02
        assert (np.asarray(made.bounds.minimum) >= lowest).all(), (part, name)
        assert (np.asarray(made.bounds.maximum) <= highest).all(), (part, name)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_lead_in_of_an_insert_is_no_bore_for_a_pin(profile: Profile, kind: str) -> None:
    """Review G, F2: Die Einführfase der Einpressbuchse ist als Bohrung erklärt.

    Die Karte bot dort *Stift für Bohrung* an, und der Stift war eine Scheibe
    Ø 4,75 × 0,5 mm. Soll: Die Karte bietet ihn dort nicht an, und die
    Operation sagt mit dem Weg zur Bohrung darunter ab.
    """
    carrier = _box(
        kind,
        profile,
        OperationDraft(op="insert_heatset_m4", inputs=("obj_1",), params={"z": 12.0}),
    )
    (lead_in,) = [
        name
        for name, feature in carrier.features.items()
        if feature.kind == "hole" and feature.params.get("lead_in")
    ]
    assert "pin_for_bore" in not_offered_at(carrier.features[lead_in])
    with pytest.raises(ValidationError) as refusal:
        run("pin_for_bore", carrier, profile, at_feature=lead_in)
    assert refusal.value.constraint == "lead_in"
    assert [action.id for action in refusal.value.suggestions] == ["change_selection", "cancel"]


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_plain_pin_stands_off_the_floor_of_a_blind_bore(profile: Profile, kind: str) -> None:
    """Review G, F2: Der glatte Stift stand auf dem Boden eines Sacklochs, Abstand null.

    Gedruckt wären Stift und Boden eins. Soll wie beim Stift mit Kopf: vor
    Material um das halbe Spiel davor, an der offenen Mündung bündig — Sackloch
    Ø 6, 8 mm tief von oben, der Stift von z = 4 + c/2 bis z = 12.
    """
    from app.core.knowledge.profiles import for_object

    carrier = _box(
        kind,
        profile,
        OperationDraft(
            op="drill_hole",
            inputs=("obj_1",),
            params={"diameter": 6.0, "depth": 8.0, "z": 12.0, "compensate": False},
        ),
    )
    (bore,) = [name for name, feature in carrier.features.items() if feature.kind == "hole"]
    clearance = for_object(profile, carrier).material.clearance
    result = run("pin_for_bore", carrier, profile, at_feature=bore, shape=bore_pin.PLAIN_PIN)
    pin = result.outputs[1]
    made = as_mesh_data(pin.mesh)
    assert float(made.bounds.minimum[2]) == pytest.approx(4.0 + clearance / 2.0, abs=TOLERANCE)
    assert float(made.bounds.maximum[2]) == pytest.approx(12.0, abs=TOLERANCE)
    _loose(pin, carrier, clearance)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_bore_that_is_not_in_the_body_gets_no_pin(profile: Profile, kind: str) -> None:
    """Review G, F2: Der Stift fragte nicht, ob der gelesene Hohlraum im Körper liegt.

    Eine erklärte Bohrung Ø 4, die halb über die Deckfläche hinausreicht, und
    eine, die ganz im vollen Material liegt: Beide sind kein Hohlraum im
    Körper. Soll: Absage mit dem Weg, eine andere Bohrung zu wählen.
    """
    from app.core.types import Feature

    carrier = _box(kind, profile)
    for name, centre in (("oben_hinaus", (0.0, 0.0, 12.0)), ("im_material", (0.0, 0.0, 6.0))):
        declared = Feature(
            id=name,
            kind="hole",
            provenance="generated",
            params={
                "diameter": 4.0,
                "centre": centre,
                "axis": (0.0, 0.0, 1.0),
                "depth": 6.0,
                "through": False,
            },
        )
        entry = dataclasses.replace(carrier, features={**carrier.features, name: declared})
        with pytest.raises(ValidationError) as refusal:
            run("pin_for_bore", entry, profile, at_feature=name)
        assert refusal.value.constraint == "not_in_the_body", name
        assert [action.id for action in refusal.value.suggestions] == [
            "change_selection",
            "cancel",
        ]


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_screw_bore_of_a_nut_trap_ends_in_the_body_and_takes_a_pin(
    profile: Profile, kind: str
) -> None:
    """RM-598: Die erklärte Schraubenbohrung der Mutternfalle reichte 10 mm in die Luft.

    Der Baustein schneidet sein Schraubenloch 10 mm über die Tasche hinaus,
    damit es durch jede Wand geht, und erklärte die Bohrung über diese ganze
    Länge: auf der Deckfläche des 12 mm dicken Quaders von z = -0,5 bis
    z = 22, fast die Hälfte in der Luft. *Stift für Bohrung* sagte deshalb ab,
    an der Stelle sei kein Hohlraum im Körper (Review G). Soll: Die erklärte
    Bohrung endet an den Grenzen des Körpers, von z = 0 bis z = 12, und der
    Stift steht lose in ihr, innerhalb des Körpers.
    """
    from app.core.knowledge.profiles import for_object

    carrier = _box(
        kind,
        profile,
        OperationDraft(op="insert_nut_trap", inputs=("obj_1",), params={"z": 12.0}),
    )
    bore = carrier.features["nut_trap_bore_1"]
    axis = np.asarray(bore.params["axis"], dtype=float)
    axis /= float(np.linalg.norm(axis))
    centre = np.asarray(bore.params["centre"], dtype=float)
    ends = sorted(
        float(value)
        for value in (
            (centre + axis * float(bore.params["depth"]) / 2.0)[2],
            (centre - axis * float(bore.params["depth"]) / 2.0)[2],
        )
    )
    assert ends == pytest.approx([0.0, 12.0], abs=TOLERANCE), ends

    clearance = for_object(profile, carrier).material.clearance
    result = run("pin_for_bore", carrier, profile, at_feature="nut_trap_bore_1")
    pin = result.outputs[1]
    _loose(pin, carrier, clearance)
    made = as_mesh_data(pin.mesh)
    body = as_mesh_data(carrier.mesh)
    lowest = np.asarray(body.bounds.minimum, dtype=float) - TOLERANCE
    highest = np.asarray(body.bounds.maximum, dtype=float) + TOLERANCE
    assert (np.asarray(made.bounds.minimum, dtype=float) >= lowest).all()
    assert (np.asarray(made.bounds.maximum, dtype=float) <= highest).all()


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("part", ["fit_ladder", "bayonet", "hose_barb"])
def test_a_part_that_builds_material_keeps_the_length_of_its_bores(
    profile: Profile, kind: str, part: str
) -> None:
    """RM-598, Nachtrag: Die Begrenzung kürzte die Bohrungen anbauender Bausteine.

    Gemessen wurde am Träger vor dem Schritt. Eine Bohrung im eigenen Material
    eines Bausteins, der Material anbaut, liegt dort in der Luft, und übrig
    blieb das Hundertstel, mit dem er in den Träger sinkt: an Passungsleiter
    und Bajonett 0,01 mm statt 3 und 11,6 mm, am Schlauchanschluss, der seinen
    Stutzen aufbaut, 3 statt 30 mm. Soll: Jede Durchgangsbohrung eines solchen
    Bausteins behält die Länge, die er selbst erklärt.
    """
    from app.core.knowledge.parts.ops import _built_part
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    load_operations()
    placement = {"z": 12.0, "nx": 0.0, "ny": 0.0, "nz": 1.0}
    spec = PARTS.get(part)
    _values, produced = _built_part(
        spec, REGISTRY.get(f"insert_{part}").params(**placement), profile, "fine"
    )
    declared = {
        key: feature
        for key, feature in produced.features.items()
        if feature.kind == "hole" and feature.params.get("through")
    }
    assert declared, part
    carrier = _box(
        kind,
        profile,
        OperationDraft(op=f"insert_{part}", inputs=("obj_1",), params=placement),
    )
    for key, feature in declared.items():
        placed = carrier.features[f"{part}_{key}"]
        assert float(placed.params["depth"]) == pytest.approx(
            float(feature.params["depth"]), abs=TOLERANCE
        ), key
