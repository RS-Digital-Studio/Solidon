"""Langlöcher als Merkmal (§21.1).

Ein Langloch ist keine Grundform: Die Einpassung findet darin zwei
Zylinderausschnitte und nennt sie Verrundungen. Was sie zu einem Loch macht,
ist die Nachbarschaft — und genau die wird hier gemessen, an beiden Enden:
dass ein Langloch eines wird, und dass etwas, das nur so aussieht, keines
wird.

**Nicht ``test_slots.py``**, und der Name ist eine Warnung: Dort geht es um
**Material**slots (§20), und im Deutschen heißt beides „Slot". Das
Filament-Konzept führt den Fall ausdrücklich als Falschtreffer; am 10.09.2026
ist er trotzdem einmal zugeschnappt.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import drill, shortest_slot, slot_profile
from app.core.perceive.digest import _feature_line
from app.core.perceive.features import _fitted, _one_body, detect
from app.core.perceive.slots import find_slots
from app.core.registry import REGISTRY
from app.core.types import Feature, Finding, OpContext, Profile, Quality, Scene, SceneObject


def plate() -> MeshData:
    """60 x 40 x 10 mm, wasserdicht."""
    return MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))


def _inside(mesh: MeshData, points: list[tuple[float, float, float]]) -> np.ndarray:
    """Innen/Außen aus der Summe der orientierten Raumwinkel — ohne ``rtree``."""
    inside = []
    for point in points:
        directions = np.asarray(mesh.raw.triangles) - np.asarray(point)
        directions /= np.linalg.norm(directions, axis=2)[:, :, None]
        first, second, third = directions.transpose(1, 0, 2)
        numerator = np.einsum("ij,ij->i", first, np.cross(second, third))
        denominator = (
            1.0
            + np.einsum("ij,ij->i", first, second)
            + np.einsum("ij,ij->i", second, third)
            + np.einsum("ij,ij->i", third, first)
        )
        angle = 2.0 * np.arctan2(numerator, denominator).sum()
        inside.append(abs(angle) > 2.0 * np.pi)
    return np.asarray(inside)


def slotted(profile: Profile, **values: float | str) -> MeshData:
    """Eine Platte mit einem gebohrten Langloch."""
    settings: dict[str, object] = {
        "position": (0.0, 0.0, 5.0),
        "axis": "z",
        "diameter": 5.0,
        "compensate": False,
        "slot_length": 20.0,
    }
    settings.update(values)
    return drill(plate(), profile=profile, **settings).mesh  # type: ignore[arg-type]


@pytest.mark.parametrize(("angle", "expected"), [(0.4, True), (0.6, False)])
def test_slot_pair_axis_agreement_has_a_boundary(profile, angle, expected) -> None:
    """Gemessene Bogenachsen dürfen nur innerhalb einer halben Gradabweichung paaren."""
    import numpy as np

    mesh = _one_body(slotted(profile, diameter=10.0, slot_length=25.0))
    arcs = _fitted(mesh).fillets
    assert len(arcs) == 2
    fit, patch = arcs[1]
    turn = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 0.0, 0.0))[:3, :3]
    measured = dataclasses.replace(fit, axis=tuple(turn @ np.asarray(fit.axis)))
    assert bool(find_slots(mesh, [arcs[0], (measured, patch)])) is expected


@pytest.mark.parametrize(("ratio", "expected"), [(1.008, True), (1.012, False)])
def test_slot_pair_radius_agreement_has_a_boundary(profile, ratio, expected) -> None:
    """Die zwei gemessenen Endradien dürfen sich nur um ein Prozent unterscheiden."""
    mesh = _one_body(slotted(profile, diameter=10.0, slot_length=25.0))
    arcs = _fitted(mesh).fillets
    assert len(arcs) == 2
    fit, patch = arcs[1]
    measured = dataclasses.replace(fit, radius=fit.radius * ratio)
    assert bool(find_slots(mesh, [arcs[0], (measured, patch)])) is expected


@pytest.mark.parametrize(("angle", "expected"), [(0.8, True), (1.2, False)])
def test_slot_shell_has_a_boundary_for_sloping_walls(angle, expected) -> None:
    """An einer echten schrägen Wand endet der quer zur Bohrachse erreichbare Mantel."""
    import numpy as np

    from app.core.perceive.slots import _neighbourhood, _shells_for

    body = trimesh.creation.box(extents=(20.0, 10.0, 2.0))
    body.vertices[:, 1] += body.vertices[:, 2] * math.tan(math.radians(angle))
    graph = _neighbourhood(body.face_adjacency, len(body.faces))
    mask, _labels, _touched, _reached = _shells_for(
        body.face_normals, np.array((0.0, 0.0, 1.0)), graph, {}
    )
    sloped = np.flatnonzero(np.abs(body.face_normals[:, 1]) > 0.9)
    assert len(sloped) == 4
    assert all(bool(mask[index]) is expected for index in sloped)


@pytest.mark.parametrize(("offset", "expected"), [(0.075, True), (0.125, False)])
def test_slot_flanks_have_a_boundary_for_distance_from_the_end_radius(offset, expected) -> None:
    """Echte Flankendreiecke 1,5 bzw. 2,5 Prozent neben dem Radius halten die 2-Prozent-Grenze."""
    import numpy as np

    from app.core.perceive.slots import _flanks_are_flat

    body = trimesh.creation.box(extents=(20.0, 10.0 + 2.0 * offset, 2.0))
    sides = set(np.flatnonzero(np.abs(body.face_normals[:, 1]) > 0.9).tolist())
    assert (
        _flanks_are_flat(body, sides, set(), np.zeros(3), np.array((0.0, 1.0, 0.0)), 5.0)
        is expected
    )


@pytest.mark.parametrize("axis", [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 2.0, 3.0)])
def test_several_slots_keep_their_ids_with_permuted_triangles_and_pair_order(profile, axis) -> None:
    """Drei unabhängige Mündungen bleiben nach schräger Lage und anderer Fleckenfolge dieselben."""
    import numpy as np

    from app.core.perceive.features import forget_cache

    mesh = plate()
    for x, y, diameter, length in (
        (-15.0, -9.0, 3.0, 10.0),
        (0.0, 9.0, 4.0, 12.0),
        (15.0, -9.0, 5.0, 14.0),
    ):
        mesh = drill(
            mesh,
            profile=profile,
            position=(x, y, 5.0),
            axis="z",
            diameter=diameter,
            compensate=False,
            slot_length=length,
        ).mesh
    raw = mesh.raw.copy()
    raw.apply_transform(trimesh.transformations.rotation_matrix(math.radians(37.0), axis))
    turned = _one_body(MeshData.of(raw))
    arcs = _fitted(turned).fillets
    forward = find_slots(turned, arcs)
    backward = find_slots(turned, list(reversed(arcs)))
    assert len(forward) == len(backward) == 3

    def locations(slots):
        return sorted((slot.centre, slot.diameter) for slot in slots)

    for first, second in zip(locations(forward), locations(backward), strict=True):
        assert first[0] == pytest.approx(second[0], abs=1e-9)
        assert first[1] == pytest.approx(second[1], abs=1e-9)
    forget_cache()
    before = {name: value for name, value in detect(turned).items() if value.kind == "slot"}
    rng = np.random.default_rng(51)
    permuted = MeshData.of(
        trimesh.Trimesh(raw.vertices, raw.faces[rng.permutation(len(raw.faces))])
    )
    forget_cache()
    after = {name: value for name, value in detect(permuted).items() if value.kind == "slot"}
    assert before.keys() == after.keys()
    for name in before:
        assert before[name].params["centre"] == pytest.approx(
            after[name].params["centre"], abs=1e-9
        )
        assert before[name].params["diameter"] == pytest.approx(
            after[name].params["diameter"], abs=1e-9
        )


def test_open_slot_search_checks_only_adjacent_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Viele Taschenecken prüfen nur ihre Nachbarn; die echte Randöffnung bleibt."""
    import numpy as np

    from app.core.geom.boolean import boolean
    from app.core.perceive.features import _fitted
    from app.core.perceive.slots import slots_instead_of_half_bores
    from tests.test_performance import pocketed_plate

    plate = pocketed_plate(16)
    cutter = trimesh.creation.cylinder(radius=3.0, height=24.0, sections=64)
    cutter.apply_translation((plate.bounds.maximum[0] - 1.0, 0.0, 0.0))
    mesh = boolean("difference", [plate, MeshData.of(cutter)]).mesh
    fitted = _fitted(mesh)
    assert sum(fit.inward for fit, _patch in fitted.fillets) >= 50
    original = np.einsum
    checked = 0

    def counted(expression, *values, **kwargs):
        nonlocal checked
        if expression == "ijk,ik->ij":
            checked += len(values[0])
        return original(expression, *values, **kwargs)

    monkeypatch.setattr(np, "einsum", counted)
    found = slots_instead_of_half_bores(mesh, {}, fitted.fillets, stadiums=fitted.stadiums)
    openings = [feature for feature in found.values() if feature.kind == "slot"]

    assert len(openings) == 1
    assert openings[0].params["open"] is True
    assert openings[0].params["diameter"] == pytest.approx(6.0, abs=0.01)
    assert openings[0].params["depth"] == pytest.approx(20.0, abs=0.01)
    assert checked < 8 * mesh.triangle_count, (
        f"{checked} triangle distance tests for {mesh.triangle_count} triangles"
    )


def test_unconnected_arcs_need_no_slot_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Getrennte Taschen werden abgewiesen, bevor ihre Querrichtungen gerechnet werden."""
    import numpy as np

    from tests.test_performance import pocketed_plate

    mesh = _one_body(pocketed_plate(16))
    fitted = _fitted(mesh)
    original = np.cross
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(np, "cross", counted)

    assert find_slots(mesh, fitted.fillets) == []
    assert calls < 8 * len(fitted.fillets), "fremde Mantelstücke brauchen keine Querrichtung"


def test_only_arcs_on_a_shared_shell_are_paired_one_by_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Paarsuche wächst mit den Bögen je Mantel, nicht mit dem Quadrat aller Bögen.

    Sechzehn Taschen mit je vier Eckrundungen sind 64 Bögen und 2 016 Paare;
    einen Mantel teilen nur die vier Ecken einer Tasche, also sechs Paare je
    Tasche. Bis zum 22.09.2026 ging jedes der 2 016 Paare einzeln durch
    ``_slot_from`` — bei 200 Taschen 319 600 Paare und 7,7 von 12 Sekunden
    der Erkennung. Die Vorauswahl (``_PairPlan``) lässt nur durch, was ein
    Langloch ergeben kann; dass sie keines verliert, prüfen die Tests mit
    echten Langlöchern in dieser Datei.
    """
    from app.core.perceive import slots as slot_module
    from tests.test_performance import pocketed_plate

    pockets = 16
    mesh = _one_body(pocketed_plate(pockets))
    fitted = _fitted(mesh)
    inward = sum(bool(getattr(fit, "inward", False)) for fit, _patch in fitted.fillets)
    assert inward == 4 * pockets, f"expected four corner arcs per pocket, got {inward}"
    original = slot_module._slot_from
    pairs = 0

    def counted(*args, **kwargs):
        nonlocal pairs
        pairs += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(slot_module, "_slot_from", counted)

    assert find_slots(mesh, fitted.fillets) == []
    assert pairs <= 6 * pockets, f"{pairs} pairs checked one by one for {pockets} pockets"


def only_slot(mesh: MeshData) -> Feature:
    """Das eine erkannte Langloch — und die Zusicherung, dass es eines ist."""
    found = [entry for entry in detect(mesh).values() if entry.kind == "slot"]
    assert len(found) == 1, f"genau ein Langloch erwartet, gefunden: {len(found)}"
    return found[0]


def test_open_slot_search_can_stop_inside_a_single_wall(profile: Profile) -> None:
    """Auch die Nachbarsuche einer einzelnen Öffnung lässt sich abbrechen."""
    from app.core.perceive.slots import open_slots_instead_of_fillets

    class StopHereError(RuntimeError):
        pass

    mesh = drill(
        plate(),
        position=(29.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        slot_length=18.0,
        profile=profile,
        compensate=False,
    ).mesh
    fillets = [entry for entry in _fitted(mesh).fillets if entry[0].inward]
    assert len(fillets) == 1
    calls = 0

    def stop() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise StopHereError

    with pytest.raises(StopHereError):
        open_slots_instead_of_fillets(mesh, {}, fillets, check_cancelled=stop)
    assert calls == 3


# --- Was ein Langloch ist ---------------------------------------------------------


def test_a_slot_is_one_feature_and_not_two_fillets(profile: Profile) -> None:
    """Der Anlass: Im Objektbaum standen zwei Hohlkehlen, wo eine Öffnung ist.

    Gemessen an einer Platte mit einem Langloch Ø 5 auf 20 mm — vor dieser
    Erkennung ``fillet_1`` und ``fillet_2``, sonst nichts. Wer darauf klickte,
    fand die Handlungen einer Verrundung: keine.
    """
    mesh = slotted(profile)
    found = detect(mesh)

    assert [entry.kind for entry in found.values()].count("slot") == 1
    assert not [entry for entry in found.values() if entry.kind == "fillet"], (
        "die zwei Bögen sind im Langloch aufgegangen"
    )
    assert not [entry for entry in found.values() if entry.kind == "hole"]


@pytest.mark.parametrize("angle", [0.0, 31.0, 90.0])
def test_a_slot_width_is_the_distance_between_its_flat_flanks(
    angle: float, profile: Profile
) -> None:
    """Die ebenen Wände liefern die Breite ohne Sehnenverlust der Bogenfacetten."""
    mesh = slotted(profile, diameter=6.0, slot_length=20.0, slot_angle=angle)
    slot = only_slot(mesh)

    assert float(slot.params["diameter"]) == pytest.approx(6.0, abs=0.0001)


@pytest.mark.parametrize("angle", [0.0, 31.0, 90.0])
def test_coarse_slot_walls_keep_their_whole_opening(angle: float) -> None:
    """Grobe Bögen und Tangentenstücke sind zusammen zwei Öffnungen.

    Die eigene Korpusplatte hält den Fehler der Schwammablage fest: Die
    Einpassung lieferte einzelne Hohlkehlen, die Flankenprüfung verwarf das
    Langloch. Acht Segmente je Halbkreis belegen die Kontur trotzdem.
    """
    source = Path(__file__).parent / "data" / "meshes" / "plate_coarse_slots.stl"
    body = trimesh.load_mesh(source, process=True)
    assert body.is_watertight and body.is_winding_consistent
    removed_area = 3.8 * (3.8 + 21.0) + 2.0 * 8.0 * 1.9**2 * math.sin(math.pi / 8.0)
    assert body.volume == pytest.approx(70.0 * 24.0 * 2.0 - 2.0 * removed_area, abs=0.0001)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle), (1, 2, 3)))
    body.apply_translation((103.0, -27.0, 48.0))

    found = detect(MeshData.of(body))
    openings = sorted(
        (feature for feature in found.values() if feature.kind == "slot"),
        key=lambda feature: float(feature.params["length"]),
    )

    assert len(openings) == 2
    assert not any(feature.kind == "fillet" for feature in found.values())
    for slot, length in zip(openings, (7.6, 24.8), strict=True):
        assert float(slot.params["diameter"]) == pytest.approx(3.8, abs=0.001)
        assert float(slot.params["length"]) == pytest.approx(length, abs=0.001)
        assert float(slot.params["depth"]) == pytest.approx(2.0, abs=0.001)
        assert slot.params["through"]
        assert len(slot.face_indices) == 36


def test_an_open_slot_on_the_exact_core_carries_native_measures_where_it_can() -> None:
    """Was ein nativer Träger belegt, heißt ``native`` — der Rest bleibt ``fit`` (P1.5).

    Am exakten Kern kommt ein offenes Langloch über den Netzweg, aber sein
    Bogen ist ein nativer Zylinder und seine Flanken sind native Ebenen:
    Durchmesser, Achse, Bogenmitte und Richtung sind damit exakt belegt.
    Mündung, Weg und Länge hängen am Rand des Netzes und bleiben ``fit``;
    am reinen Netz bleibt alles ``fit``. Keine pauschale Hochstufung.
    """
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    body = edit.slot_bore(
        edit.box(60.0, 30.0, 8.0),
        position=(0.0, 8.0, 4.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=8.0,
        length=26.0,
        angle_deg=90.0,
        overlap=0.0,
    )
    native = [f for f in features_of(body).values() if f.kind == "slot"]
    assert len(native) == 1 and native[0].params["open"] is True
    slot = native[0]
    assert {
        key: slot.measure_sources[key] for key in ("diameter", "axis", "arc_centre", "direction")
    } == {
        "diameter": "native",
        "axis": "native",
        "arc_centre": "native",
        "direction": "native",
    }
    assert {
        slot.measure_sources[key] for key in ("length", "travel", "mouth_centre", "centre")
    } == {"fit"}
    assert slot.measure_sources["depth"] == "facets"
    assert slot.params["diameter"] == 6.0, "exakt, nicht eingepasst"
    assert tuple(slot.params["axis"]) == (0.0, 0.0, 1.0)
    # Das Langloch liegt bei y = 8 ± 13; die Platte endet bei y = 15, also
    # liegt die Mündung dort und der geschlossene Bogen um y = -5 + 3.
    assert slot.params["arc_centre"][0] == pytest.approx(0.0, abs=1e-9)
    assert slot.params["arc_centre"][1] == pytest.approx(-2.0, abs=1e-9)
    assert slot.params["direction"][1] == pytest.approx(1.0, abs=1e-12), "zur Mündung hin"
    assert {patch.source for patch in slot.surface_patches} == {"native"}

    meshed = [f for f in detect(body.to_mesh(deflection=0.05)).values() if f.kind == "slot"]
    assert len(meshed) == 1 and meshed[0].params["open"] is True
    assert {
        meshed[0].measure_sources[key] for key in ("diameter", "axis", "arc_centre", "direction")
    } == {"fit"}
    assert meshed[0].params["diameter"] == pytest.approx(6.0, abs=0.02)


def _open_slot_with_a_native_arc(axis: tuple[float, ...], radius: float) -> Feature:
    """Ein offenes Langloch Ø 6 mit einem nativen Zylinderträger der gegebenen Achse und Größe."""
    from app.core.types import SurfacePatch

    return Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "open": True,
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (0.0, 1.0, 0.0),
            "arc_centre": (0.0, -2.0, 4.0),
        },
        measure_sources={"diameter": "fit", "axis": "fit", "arc_centre": "fit"},
        surface_patches=(
            SurfacePatch(
                kind="cylinder",
                params={"axis": axis, "centre": (0.0, -2.0, 0.0), "radius": radius},
                face_indices=(0, 1, 2),
                source="native",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("axis", "radius", "promoted"),
    [
        ((0.0, 0.0, 1.0), 3.0, True),
        ((0.0, math.sin(math.radians(2.0)), math.cos(math.radians(2.0))), 3.0, False),
        ((0.0, 0.0, 1.0), 3.75, False),
    ],
    ids=["trifft", "zwei Grad gekippt", "anderthalb Millimeter größer"],
)
def test_a_native_arc_carrier_must_hit_the_measured_arc_to_count(
    axis: tuple[float, ...], radius: float, promoted: bool
) -> None:
    """Ein nativer Zylinder beschriftet das Langloch nur, wenn er dessen Bogen ist.

    Bis zum 21.09.2026 genügte ein Skalarprodukt der Achsen ungleich null
    (Regel 6): Ein um zwei Grad gekippter oder anderthalb Millimeter größerer
    nativer Zylinder hätte Durchmesser, Achse und Bogenmitte als ``native``
    ausgewiesen. Achse und Radius müssen den gemessenen Bogen im Vertrag von
    ``PARALLEL_AXES`` und ``SAME_RADIUS`` treffen.
    """
    from app.core.perceive.slots import native_open_slot_measures

    slot = native_open_slot_measures(_open_slot_with_a_native_arc(axis, radius))
    expected = "native" if promoted else "fit"
    assert {slot.measure_sources[key] for key in ("diameter", "axis", "arc_centre")} == {expected}
    assert slot.params["diameter"] == (6.0 if not promoted else radius * 2.0)


def test_a_slot_carries_the_measures_it_was_cut_with(profile: Profile) -> None:
    slot = only_slot(slotted(profile, diameter=5.0, slot_length=20.0))

    assert float(slot.params["diameter"]) == pytest.approx(5.0, abs=0.01)
    assert float(slot.params["length"]) == pytest.approx(20.0, abs=0.01)
    assert float(slot.params["travel"]) == pytest.approx(15.0, abs=0.01)
    assert float(slot.params["depth"]) == pytest.approx(10.0, abs=0.01)
    assert slot.params["through"]
    assert slot.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)
    assert slot.params["centre"] == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_a_blind_slot_says_it_does_not_go_through(profile: Profile) -> None:
    slot = only_slot(slotted(profile, depth=4.0))

    assert not slot.params["through"]
    assert float(slot.params["depth"]) == pytest.approx(4.0, abs=0.01)
    # Die Mitte liegt auf halber Tiefe unter der Oberseite, nicht in der Mitte
    # der Platte — sonst zeigte ein Klick darauf ins Material daneben.
    assert float(slot.params["centre"][2]) == pytest.approx(3.0, abs=0.01)


@pytest.mark.parametrize("angle", [0.0, 30.0, 90.0, -45.0])
def test_a_slot_knows_which_way_it_lies(angle: float, profile: Profile) -> None:
    """Die Richtung ist der Grund, aus dem es Langlöcher gibt.

    Ohne sie wüsste weder der Kunde noch der Agent, wohin sich das Teil
    verschieben lässt. Gemessen gegen den Winkel, mit dem gebohrt wurde —
    und ohne Vorzeichen: Ein Langloch hat keine Vorder- und keine Rückseite.
    """
    slot = only_slot(slotted(profile, slot_angle=angle))

    along = slot.params["direction"]
    wanted = (math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0.0)
    parallel = abs(sum(a * b for a, b in zip(along, wanted, strict=True)))
    assert parallel == pytest.approx(1.0, abs=1e-6)


def test_a_slot_cut_by_two_booleans_is_found_as_well(profile: Profile) -> None:
    """Der eigentliche Kundenfall: ein **eingelesenes** Modell.

    Wer eine Datei aus dem Netz öffnet, hat kein Solidon-Langloch, sondern ein
    Netz, in das jemand anders eine Nut geschnitten hat. Diese hier entsteht
    aus einem Quader und zwei Zylindern und nie aus ``drill`` — sonst prüfte
    der Test seinen eigenen Erzeuger.
    """
    del profile
    body = MeshData.of(trimesh.creation.box(extents=(80.0, 40.0, 20.0)))
    middle = trimesh.creation.box(extents=(22.0, 8.0, 8.0))
    middle.apply_translation((0.0, 0.0, 8.0))
    tool = MeshData.of(middle)
    for x in (-11.0, 11.0):
        cap = trimesh.creation.cylinder(radius=4.0, height=8.0, sections=64)
        cap.apply_translation((x, 0.0, 8.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    cut = boolean("difference", [body, tool]).mesh

    slot = only_slot(cut)

    assert float(slot.params["diameter"]) == pytest.approx(8.0, abs=0.05)
    assert float(slot.params["length"]) == pytest.approx(30.0, abs=0.05)
    assert not slot.params["through"], "die Nut ist 5 mm tief, die Platte 20 mm dick"


# --- Und was keines ist -----------------------------------------------------------


def pocket_with_rounded_corners(length: float, width: float, radius: float) -> MeshData:
    """Eine rechteckige Tasche mit vier verrundeten Ecken.

    Die härteste Gegenprobe, die es gibt: vier Innenverrundungen mit gleichem
    Radius und paralleler Achse, über die geraden Wände verbunden. Zwei
    benachbarte davon plus die Wand dazwischen sehen einem Langloch zum
    Verwechseln ähnlich — und sind keines, weil der Mantel weiterläuft.
    """
    block = trimesh.creation.box(extents=(length + 30.0, width + 30.0, 20.0))
    outline = (
        Polygon(
            [
                (-length / 2, -width / 2),
                (length / 2, -width / 2),
                (length / 2, width / 2),
                (-length / 2, width / 2),
            ]
        )
        .buffer(-radius)
        .buffer(radius, quad_segs=16)
    )
    tool = trimesh.creation.extrude_polygon(outline, height=8.0)
    tool.apply_translation((0.0, 0.0, 4.0))
    return boolean("difference", [MeshData.of(block), MeshData.of(tool)]).mesh


@pytest.mark.parametrize(("length", "width"), [(40.0, 24.0), (30.0, 30.0)])
def test_a_pocket_with_rounded_corners_is_not_a_slot(length: float, width: float) -> None:
    mesh = pocket_with_rounded_corners(length, width, 6.0)
    body = _one_body(mesh)
    rounded = [entry for entry in _fitted(body).fillets if entry[0].inward]

    assert len(rounded) == 4, (
        "die Vorbedingung: vier Innenverrundungen, sonst prüft die Gegenprobe nichts"
    )
    assert find_slots(body, _fitted(body).fillets) == []
    assert not [entry for entry in detect(mesh).values() if entry.kind == "slot"]


def test_two_separate_bores_are_not_a_slot(profile: Profile) -> None:
    """Zwei Löcher nebeneinander bleiben zwei Löcher."""
    first = drill(
        plate(),
        position=(-6.0, 0.0, 5.0),
        axis="z",
        diameter=5.0,
        profile=profile,
        compensate=False,
    )
    both = drill(
        first.mesh,
        position=(6.0, 0.0, 5.0),
        axis="z",
        diameter=5.0,
        profile=profile,
        compensate=False,
    )
    found = detect(both.mesh)

    assert [entry.kind for entry in found.values()].count("hole") == 2
    assert not [entry for entry in found.values() if entry.kind == "slot"]


# --- Wie der Kunde es sieht -------------------------------------------------------


def test_the_object_tree_names_a_slot_and_shows_both_measures(profile: Profile) -> None:
    """Ein Merkmal ohne Namen steht als englische Kennung im Baum (Regel 20).

    Das Komma kommt aus ``QLocale``, nicht aus der Sprache — ``labels.length``
    fragt dieselbe Quelle wie die Eingabefelder. Ohne die Zeile prüfte der
    Test die Sprache des Rechners: hier ein deutsches Windows, auf dem Runner
    ein englisches, und dort stand „Ø5.00 mm × 20.00 mm" (Tag-Lauf v0.4.1).
    """
    from PySide6.QtCore import QLocale

    from app.i18n import set_language
    from app.ui import labels

    before = QLocale()
    QLocale.setDefault(QLocale("de"))
    try:
        set_language("de")
        slot = only_slot(slotted(profile))

        assert "Langloch" in labels.feature_name(slot.id, slot)
        measure = labels.feature_measure(slot)
        assert "5,0" in measure and "20,0" in measure, (
            f"Breite und Länge stehen beide da, gelesen wurde {measure!r}"
        )
    finally:
        QLocale.setDefault(before)


def test_the_digest_tells_the_agent_where_a_slot_points(profile: Profile) -> None:
    """Der Agent sieht nur diesen Text (§26.1)."""
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=90.0))

    line = _feature_line(slot.id, slot)
    assert "Langloch" in line
    assert "+Y" in line, f"die Richtung steht darin, gelesen wurde {line!r}"


# --- Und was sich daran noch tun lässt ---------------------------------------------


def run_op(op: str, entry: SceneObject, profile: Profile, **params: object) -> SceneObject:
    """Nur den Körper zurückgeben, wenn der Test keine Befunde braucht."""
    return run_op_with_findings(op, entry, profile, **params)[0]


def run_op_with_findings(
    op: str,
    entry: SceneObject,
    profile: Profile,
    *,
    quality: Quality = "fine",
    **params: object,
) -> tuple[SceneObject, list[Finding]]:
    """Eine Operation fahren und danach neu erkennen, wie die Auswertung es tut."""
    from app.core.scene.cancel import NeverCancelled

    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    out = result.outputs[0]
    return dataclasses.replace(out, features=detect(as_mesh_data(out.mesh))), list(result.findings)


def a_slotted_plate(profile: Profile) -> SceneObject:
    mesh = slotted(profile)
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_an_imported_slot_can_be_shortened_without_changing_its_neighbour(
    profile: Profile, quality: Quality
) -> None:
    """Die Korpusplatte bekommt Material an den alten Enden zurück, das Nachbarloch bleibt."""
    from app.core.geom.prepare_ops import slot_angle_of

    source = Path(__file__).parent / "data" / "meshes" / "plate_coarse_slots.stl"
    body = MeshData.of(trimesh.load_mesh(source, process=True))
    before = detect(body)
    slots = sorted(
        (feature for feature in before.values() if feature.kind == "slot"),
        key=lambda feature: float(feature.params["length"]),
    )
    assert len(slots) == 2
    chosen = slots[1]
    assert body.raw.is_watertight and body.raw.is_winding_consistent
    assert body.raw.body_count == 1
    assert chosen.params["length"] == pytest.approx(24.8, abs=0.001)
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=before)

    result, findings = run_op_with_findings(
        "slot_hole",
        entry,
        profile,
        quality=quality,
        at_feature=chosen.id,
        slot_length=12.0,
        slot_angle=slot_angle_of(chosen, chosen.params["axis"]),
    )

    changed = as_mesh_data(result.mesh)
    found = sorted(
        (feature for feature in result.features.values() if feature.kind == "slot"),
        key=lambda feature: float(feature.params["length"]),
    )
    assert changed.raw.is_watertight and changed.raw.is_winding_consistent
    assert changed.raw.body_count == 1
    assert len(found) == 2
    assert found[0].params["length"] == pytest.approx(7.6, abs=0.001)
    assert found[0].params["centre"] == pytest.approx(slots[0].params["centre"], abs=0.001)
    assert found[1].params["length"] == pytest.approx(12.0, abs=0.01)
    assert found[1].params["diameter"] == pytest.approx(3.8, abs=0.001)
    assert found[1].params["centre"] == pytest.approx(chosen.params["centre"], abs=0.001)
    original_arc_area = 8.0 * 1.9**2 * math.sin(math.pi / 8.0)
    expected_gain = ((24.8 - 12.0) * 3.8 + original_arc_area - math.pi * 1.9**2) * 2.0
    assert changed.volume - body.volume == pytest.approx(expected_gain, abs=0.1)
    assert not any(finding.code == "slot_hole.feature_lost" for finding in findings)


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("depth", [0.0, 4.0])
@pytest.mark.parametrize(("diameter", "length"), [(6.0, 12.0), (4.0, 5.0)])
@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_slot_can_be_shortened_and_narrowed_in_both_kernels(
    profile: Profile, quality: Quality, depth: float, diameter: float, length: float, kernel: str
) -> None:
    """Beide Maße ändern gemeinsam, auch unter die alte Mindestlänge; der Boden bleibt."""
    exact = kernel == "brep"
    if exact:
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
        from app.core.brep import edit
        from app.core.brep.features import features_of

        body = edit.box(60.0, 40.0, 10.0)
    else:
        body = plate()
        body.raw.apply_translation((0.0, 0.0, 5.0))

    def recognised(result: SceneObject) -> dict[str, Feature]:
        return features_of(result.mesh) if exact else detect(as_mesh_data(result.mesh))

    entry = SceneObject(id="obj_1", name="Platte", mesh=body, kind=kernel)
    drilled = run_op(
        "drill_hole",
        entry,
        profile,
        diameter=6.0,
        slotted=True,
        slot_length=24.0,
        slot_angle=31.0,
        x=0.0,
        y=0.0,
        z=10.0,
        axis="normal",
        nx=0.0,
        ny=0.0,
        nz=1.0,
        depth=depth,
        compensate=False,
    )
    drilled = dataclasses.replace(drilled, features=recognised(drilled))
    before = next(feature for feature in drilled.features.values() if feature.kind == "slot")
    original_volume = drilled.mesh.volume
    cut_depth = depth or 10.0
    assert original_volume == pytest.approx(
        24000.0 - (math.pi * 9.0 + 6.0 * 18.0) * cut_depth, abs=1e-6 if exact else 0.5
    )

    result, findings = run_op_with_findings(
        "slot_hole",
        drilled,
        profile,
        quality=quality,
        at_feature=before.id,
        slot_length=length,
        slot_angle=31.0,
        diameter=diameter,
        compensate=False,
    )

    assert result.kind == kernel
    changed = as_mesh_data(result.mesh)
    assert changed.raw.is_watertight and changed.raw.is_winding_consistent
    assert changed.raw.body_count == 1
    if exact:
        assert result.mesh.is_closed
    assert result.mesh.volume == pytest.approx(
        24000.0 - (math.pi * (diameter / 2.0) ** 2 + diameter * (length - diameter)) * cut_depth,
        abs=1e-6 if exact else 0.5,
    )
    assert drilled.mesh.volume == pytest.approx(original_volume, abs=1e-6)
    after = next(feature for feature in recognised(result).values() if feature.kind == "slot")
    assert after.params["length"] == pytest.approx(length, abs=1e-6 if exact else 0.001)
    assert after.params["diameter"] == pytest.approx(diameter, abs=1e-6 if exact else 0.001)
    assert after.params["depth"] == pytest.approx(cut_depth, abs=1e-6 if exact else 0.001)
    assert after.params["through"] is (depth == 0.0)
    assert after.params["centre"] == pytest.approx(
        before.params["centre"], abs=1e-6 if exact else 0.001
    )
    assert _direction_angle(after) == pytest.approx(31.0, abs=1e-6 if exact else 0.001)
    assert not any(finding.code == "slot_hole.feature_lost" for finding in findings)


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("depth", [0.0, 4.0])
@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_slot_pulled_back_to_its_width_is_a_round_bore_again(
    profile: Profile, quality: Quality, depth: float, kernel: str
) -> None:
    """Genau die Breite als Länge heißt: wieder rund (Robert, 24.09.2026).

    Langloch Ø 6 auf 24 mm in einer Platte 60 x 40 x 10, auf die Länge 6
    zurückgezogen. Übrig bleibt eine runde Bohrung Ø 6 an der Mitte des
    Langlochs, so tief wie vorher: am exakten Körper π · 3² · Tiefe
    abgetragen, am Netz das 48-Eck der Bohrwerkzeuge (``BORE_SECTIONS``),
    also 24 · 3² · sin(2π / 48) · Tiefe.
    """
    exact = kernel == "brep"
    if exact:
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
        from app.core.brep import edit
        from app.core.brep.features import features_of

        body = edit.box(60.0, 40.0, 10.0)
    else:
        body = plate()
        body.raw.apply_translation((0.0, 0.0, 5.0))

    def recognised(result: SceneObject) -> dict[str, Feature]:
        return features_of(result.mesh) if exact else detect(as_mesh_data(result.mesh))

    entry = SceneObject(id="obj_1", name="Platte", mesh=body, kind=kernel)
    drilled = run_op(
        "drill_hole",
        entry,
        profile,
        diameter=6.0,
        slotted=True,
        slot_length=24.0,
        slot_angle=31.0,
        x=0.0,
        y=0.0,
        z=10.0,
        axis="normal",
        nx=0.0,
        ny=0.0,
        nz=1.0,
        depth=depth,
        compensate=False,
    )
    drilled = dataclasses.replace(drilled, features=recognised(drilled))
    before = next(feature for feature in drilled.features.values() if feature.kind == "slot")

    result, findings = run_op_with_findings(
        "slot_hole",
        drilled,
        profile,
        quality=quality,
        at_feature=before.id,
        slot_length=float(before.params["diameter"]),
        slot_angle=31.0,
    )

    cut_depth = depth or 10.0
    area = math.pi * 9.0 if exact else 24.0 * 9.0 * math.sin(2.0 * math.pi / 48.0)
    assert result.kind == kernel
    changed = as_mesh_data(result.mesh)
    assert changed.raw.is_watertight and changed.raw.is_winding_consistent
    assert changed.raw.body_count == 1
    assert result.mesh.volume == pytest.approx(
        24000.0 - area * cut_depth, abs=1e-6 if exact else 0.05
    )
    after = recognised(result)
    assert not any(feature.kind == "slot" for feature in after.values())
    bores = [feature for feature in after.values() if feature.kind == "hole"]
    assert len(bores) == 1
    assert bores[0].params["diameter"] == pytest.approx(6.0, abs=1e-6 if exact else 0.01)
    assert bores[0].params["centre"][:2] == pytest.approx(
        before.params["centre"][:2], abs=1e-6 if exact else 0.001
    )
    assert bores[0].params["depth"] == pytest.approx(cut_depth, abs=1e-6 if exact else 0.001)
    assert any(finding.code == "slot_hole.round_again" for finding in findings)
    assert not any(finding.severity == "warning" for finding in findings)


def test_both_kernels_report_the_same_when_a_slot_snaps_round_with_tolerance(
    profile: Profile,
) -> None:
    """Zurück auf rund mit Materialtoleranz: beide Kerne sagen dasselbe.

    Am Netz fehlte im runden Zweig ``bore.compensated``, der exakte Kern
    meldete ihn (Review 24.09.2026). Die Zwillingsregel verlangt dieselbe
    Antwort auf dieselbe Frage.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    codes: dict[str, set[str]] = {}
    for kernel in ("mesh", "brep"):
        if kernel == "brep":
            entry = SceneObject(
                id="obj_1", name="Platte", mesh=edit.box(60.0, 40.0, 10.0), kind="brep"
            )
        else:
            mesh = plate()
            mesh.raw.apply_translation((0.0, 0.0, 5.0))
            entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, kind="mesh")
        drilled = run_op(
            "drill_hole",
            entry,
            profile,
            diameter=6.0,
            slotted=True,
            slot_length=24.0,
            slot_angle=31.0,
            x=0.0,
            y=0.0,
            z=10.0,
            axis="normal",
            nx=0.0,
            ny=0.0,
            nz=1.0,
            depth=0.0,
            compensate=False,
        )
        found = (
            features_of(drilled.mesh) if kernel == "brep" else detect(as_mesh_data(drilled.mesh))
        )
        drilled = dataclasses.replace(drilled, features=found)
        slot = next(feature for feature in drilled.features.values() if feature.kind == "slot")
        _result, findings = run_op_with_findings(
            "slot_hole",
            drilled,
            profile,
            at_feature=slot.id,
            slot_length=6.0,
            slot_angle=31.0,
            diameter=6.0,
            compensate=True,
        )
        codes[kernel] = {finding.code for finding in findings}
    assert {"bore.compensated", "slot_hole.round_again"} <= codes["mesh"], codes
    assert codes["mesh"] == codes["brep"], codes


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_wider_round_bore_warns_about_its_neighbour_like_resize_hole(
    profile: Profile, kernel: str
) -> None:
    """Rund und breiter über *Zum Langloch ziehen* prüft die Nachbarwand wie *Bohrung ändern*.

    Zwei Durchgangsbohrungen Ø 5 im Abstand 8 in einer Platte 60 x 40 x 10.
    Die linke auf Ø 10 gebracht, lässt 0,5 mm Wand zur rechten. *Bohrung
    ändern* sagte das, derselbe Weg über Länge = Breite = 10 nicht (Review
    24.09.2026).
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    plate = edit.box(60.0, 40.0, 10.0)
    for x in (0.0, 8.0):
        plate = edit.cut_bore(
            plate, position=(x, 0.0, 5.0), direction=(0.0, 0.0, 1.0), diameter=5.0, depth=12.0
        )
    if kernel == "brep":
        entry = SceneObject("plate", "Platte", plate, kind="brep", features=features_of(plate))
    else:
        mesh = as_mesh_data(plate)
        entry = SceneObject("plate", "Platte", mesh, features=detect(mesh))
    left = next(
        feature
        for feature in entry.features.values()
        if feature.kind == "hole" and abs(float(feature.params["centre"][0])) < 0.5
    )

    def codes(op: str, **params: object) -> set[str]:
        _result, findings = run_op_with_findings(op, entry, profile, at_feature=left.id, **params)
        return {finding.code for finding in findings}

    resized = codes("resize_hole", diameter=10.0, compensate=False)
    rounded = codes("slot_hole", slot_length=10.0, slot_angle=0.0, diameter=10.0, compensate=False)
    wall = {"bore.neighbour_wall_thin", "bore.neighbour_opened"}
    assert resized & wall, resized
    assert rounded & wall == resized & wall, (rounded, resized)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_moved_round_bore_is_not_reported_as_cutting_nothing(
    profile: Profile, kernel: str
) -> None:
    """Versetzt trägt die Bohrung so viel ab, wie sie füllt — und das ist kein „nichts".

    Am exakten Kern prüfte ``without_effect`` gegen den ungefüllten Körper:
    Gleiches Volumen vorher und nachher hieß dort „Der Schnitt hat nichts
    abgetragen", am Netz nicht (Review 24.09.2026).
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    plate = edit.cut_bore(
        edit.box(60.0, 40.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=5.0,
        depth=12.0,
    )
    if kernel == "brep":
        entry = SceneObject("plate", "Platte", plate, kind="brep", features=features_of(plate))
    else:
        mesh = as_mesh_data(plate)
        entry = SceneObject("plate", "Platte", mesh, features=detect(mesh))
    bore = next(feature for feature in entry.features.values() if feature.kind == "hole")
    centre = [float(value) for value in bore.params["centre"]]

    _result, findings = run_op_with_findings(
        "slot_hole",
        entry,
        profile,
        at_feature=bore.id,
        slot_length=float(bore.params["diameter"]),
        slot_angle=0.0,
        x=centre[0] + 12.0,
        y=centre[1],
        z=centre[2],
    )
    assert "boolean.without_effect" not in {finding.code for finding in findings}


def test_a_round_bore_pulled_to_its_own_width_stays_as_it_is(profile: Profile) -> None:
    """An einer runden Bohrung ändert die Länge ihres Durchmessers nichts — und sagt es."""
    mesh = drill(
        plate(), profile=profile, position=(0.0, 0.0, 5.0), axis="z", diameter=5.0, compensate=False
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    bore = next(feature for feature in entry.features.values() if feature.kind == "hole")

    result, findings = run_op_with_findings(
        "slot_hole",
        entry,
        profile,
        at_feature=bore.id,
        slot_length=float(bore.params["diameter"]),
        slot_angle=0.0,
    )

    assert result.mesh is entry.mesh, "nichts geschnitten, nichts gefüllt"
    assert [finding.code for finding in findings] == ["slot_hole.already_round"]
    assert findings[0].severity == "info"
    # Regel 17: Der Satz sagt „Ziehen Sie sie länger", und der Knopf öffnet den
    # Schritt mit dem Cursor in der Länge.
    assert [action.id for action in findings[0].suggestions] == ["correct_input"]
    assert findings[0].values["field"] == "slot_length"


@pytest.mark.parametrize("beyond", [-0.5, 0.2])
def test_between_round_and_slot_there_is_no_length(profile: Profile, beyond: float) -> None:
    """Kürzer als die Breite oder zwischen Breite und Mindestlänge bleibt eine Absage.

    Ø 5: rund heißt genau 5, ein Langloch beginnt bei ``shortest_slot(5)`` = 5,5.
    """
    entry = a_slotted_plate(profile)
    slot = next(feature for feature in entry.features.values() if feature.kind == "slot")
    width = float(slot.params["diameter"])
    assert shortest_slot(width) > width + 0.2

    with pytest.raises(ValidationError) as caught:
        run_op_with_findings(
            "slot_hole",
            entry,
            profile,
            at_feature=slot.id,
            slot_length=width + beyond,
            slot_angle=0.0,
        )
    assert caught.value.field == "slot_length"
    # Der Satz nennt beide Auswege mit ihren Zahlen, und eine Handlung steht
    # daneben (Regel 17) — so viel prüfte der ersetzte Test auch.
    assert caught.value.constraint == "slot_proportion"
    assert caught.value.suggestions
    assert {"diameter", "shortest"} <= set(caught.value.values)


def test_pulling_an_existing_slot_keeps_its_direction(profile: Profile) -> None:
    """Ohne diese Vorgabe stellte ein Zug an der Länge das Loch quer.

    Das Feld *Richtung* steht auf null, und null heißt an einer **Bohrung**
    „die erste Achse der Fläche". An einem Langloch, das schon irgendwo liegt,
    hieße es „dreh es dorthin" — und aus einem Zug an der Länge würde ein
    Kreuz.
    """
    entry = a_slotted_plate(profile)
    slot = next(name for name, f in entry.features.items() if f.kind == "slot")
    before = entry.features[slot].params["direction"]

    longer = run_op("slot_hole", entry, profile, at_feature=slot, slot_length=28.0)

    after = only_slot(as_mesh_data(longer.mesh))
    assert float(after.params["length"]) == pytest.approx(28.0, abs=0.05)
    parallel = abs(sum(a * b for a, b in zip(before, after.params["direction"], strict=True)))
    assert parallel == pytest.approx(1.0, abs=1e-6), "dieselbe Richtung wie vorher"


def test_turning_a_slot_closes_its_old_direction(profile: Profile) -> None:
    """Ein Langloch in neuer Richtung ist ein gedrehtes Langloch — kein Kreuz.

    Bis zum 15.09.2026 schnitt der Zug mit anderem Winkel ein zweites Langloch
    quer über das erste; die Warnung ``slot_hole.crosses`` sagte es, und das
    Ergebnis war trotzdem das Gegenteil dessen, was der Ring am Griff
    verspricht (Robert: „habe ich 2 langlöcher"). Jetzt schließt die Operation
    die alte Öffnung, wie beim Versetzen, und schneidet die neue.
    """
    entry = a_slotted_plate(profile)
    slot = next(name for name, f in entry.features.items() if f.kind == "slot")
    before = entry.features[slot].params["direction"]

    output, findings = run_op_with_findings(
        "slot_hole", entry, profile, at_feature=slot, slot_length=24.0, slot_angle=90.0
    )

    found = detect(as_mesh_data(output.mesh))
    kinds = [feature.kind for feature in found.values()]
    assert kinds.count("slot") == 1, f"genau ein Langloch, kein Kreuz: {kinds}"
    turned = next(feature for feature in found.values() if feature.kind == "slot")
    across = abs(sum(a * b for a, b in zip(before, turned.params["direction"], strict=True)))
    assert across == pytest.approx(0.0, abs=1e-3), "und es liegt quer zur alten Richtung"
    assert float(turned.params["length"]) == pytest.approx(24.0, abs=0.1)

    codes = {finding.code for finding in findings}
    assert "slot_hole.turned" in codes, "die Drehung sagt sich an"
    assert "slot_hole.crosses" not in codes
    assert "slot_hole.feature_renamed" not in codes, (
        "aus einem Langloch wird kein Langloch — es wird gedreht"
    )


def test_a_slot_offers_the_one_operation_that_fits_it() -> None:
    """Ein Merkmal ohne Handlung ist eine Sackgasse (§2.6).

    Gemessen am Weg: An einem erkannten Langloch standen fünf ausgegraute
    Zeilen und **null** Knöpfe — die Operation gab es im Register längst, die
    Oberfläche bot sie nur nicht an.

    **Seit dem 10.09.2026 steht sie eine Karte höher**, als Zeile mit Feldern
    im Merkmalsfenster (``perceive.actions.ACTION_ORDER``): Der Knopf allein
    ließ den Kunden die Maße sehen und keines davon ändern (Robert: „langloch
    merkmale hat noch in der auswahl keine einstellungen"). Was dort als Feld
    steht, bekommt in der Auswahlkarte darunter **keinen zweiten Knopf** —
    dieselbe Regel, an der schon *Bohrung ändern* hängt. Der Test prüft
    deshalb beide Seiten: dass die Zeile mit ihren zwei Maßen dasteht, und dass
    die Karte darunter schweigt.
    """
    from app.core.perceive.actions import actions_for
    from app.ui.selection_operations import quick_names

    load_operations()
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 5.0,
            "length": 20.0,
            "travel": 15.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 0.0),
            "depth": 10.0,
            "through": True,
        },
    )

    assert "slot_hole" in {spec.name for spec in REGISTRY.for_feature("slot")}
    zeile = next(action for action in actions_for(slot) if action.op == "slot_hole")
    # Länge, Richtung — **und die Stelle**: Seit dem 10.09.2026 führt
    # ``slot_hole`` seine Mitte selbst, damit es dieselbe Flächenplatzierung
    # bekommt wie *Bohrung setzen* (Robert: „einfach wie wenn ich eine bohrung
    # setze"). Die drei Felder tragen den gemessenen Ort. **Und die Breite**
    # (22.09.2026, Entscheidung Robert: Zug und neuer Durchmesser sind ein
    # Schritt): vorbelegt mit der gemessenen, damit Übernehmen ohne Hinsehen
    # nichts ändert; der Toleranzausgleich dazu wie bei *Bohrung ändern*.
    assert {field.name for field in zeile.fields} == {
        "slot_length",
        "slot_angle",
        "x",
        "y",
        "z",
        "diameter",
        "compensate",
    }
    werte = {field.name: field.value for field in zeile.fields}
    assert (werte["x"], werte["y"], werte["z"]) == pytest.approx((0.0, 0.0, 0.0)), (
        "die Stelle steht auf der gemessenen Mitte, nicht auf dem Ursprung von irgendwo"
    )
    assert werte["diameter"] == pytest.approx(float(slot.params["diameter"]))
    # Seit P6.7 (23.09.2026) steht dort *Merkmal vervielfachen* — es hat keine
    # gemessenen Werte und damit keine Zeile im Merkmalfenster. Was als Feld
    # dasteht, bleibt ohne zweiten Knopf.
    assert quick_names(1, "slot") == ("pattern_feature",), (
        "was als Feld dasteht, wird kein zweiter Knopf"
    )


def test_a_slot_takes_the_four_generic_actions(profile: Profile) -> None:
    """Versetzen, Drehen, Verdoppeln, Entfernen — am Langloch wie an der Bohrung.

    Bis zum 11.09.2026 stand hier das Gegenteil: ``NOT_APPLICABLE`` führte das
    Langloch mit dem Satz „die Handlungen hier rechnen mit einem Durchmesser
    und träfen seine Flanken nicht". Der Satz war schon einen Tag lang nicht
    mehr wahr — den Werkzeugkörper zog ``_feature_solid`` seit dem Morgen auf
    wie beim Schneiden —, und was wirklich fehlte, war eine Antwort:
    ``is_a_cavity`` kannte das Langloch nicht und hielt es für Materie.
    *Merkmal verschieben* trug damit an der alten Stelle ab statt zu füllen
    und setzte an der neuen an statt zu schneiden, das Volumen blieb gleich,
    und das Merkmal wanderte im Baum an eine Stelle ohne Loch (RM-153).

    Gemessen wird jede der vier am Ergebnis, nicht am Register.
    """
    from app.core.perceive.actions import NOT_APPLICABLE, actions_for

    assert "slot" not in NOT_APPLICABLE
    for op in ("move_feature", "rotate_feature", "duplicate_feature", "remove_feature"):
        assert "slot" in REGISTRY.get(op).applies_to, op

    mesh = drill(
        plate(),
        profile=profile,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
        slot_length=20.0,
        slot_angle=30.0,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    slot = next(feature for feature in entry.features.values() if feature.kind == "slot")
    whole = plate().volume
    assert {action.op for action in actions_for(slot)} >= {
        "move_feature",
        "rotate_feature",
        "duplicate_feature",
        "remove_feature",
    }

    # Die Mitte liegt auf halber Tiefe: z bleibt, x und y wandern.
    depth_mid = float(slot.params["centre"][2])
    moved = run_op("move_feature", entry, profile, at_feature=slot.id, x=15.0, y=8.0, z=depth_mid)
    kinds = [feature for feature in moved.features.values() if feature.kind == "slot"]
    assert len(kinds) == 1
    assert kinds[0].params["centre"] == pytest.approx((15.0, 8.0, depth_mid), abs=0.05)
    assert moved.mesh.volume == pytest.approx(entry.mesh.volume, rel=1e-3), (
        "versetzt, nicht verdoppelt"
    )

    turned = run_op("rotate_feature", entry, profile, at_feature=slot.id, axis="z", angle=45.0)
    kinds = [feature for feature in turned.features.values() if feature.kind == "slot"]
    assert len(kinds) == 1, "gedreht steht ein Langloch da, kein Kreuz"
    direction = kinds[0].params["direction"]
    assert math.degrees(math.atan2(direction[1], direction[0])) % 180.0 == pytest.approx(
        75.0, abs=0.5
    )
    assert turned.mesh.volume == pytest.approx(entry.mesh.volume, rel=1e-3)

    doubled = run_op(
        "duplicate_feature", entry, profile, at_feature=slot.id, x=15.0, y=-10.0, z=depth_mid
    )
    assert sum(1 for feature in doubled.features.values() if feature.kind == "slot") == 2
    assert doubled.mesh.volume < entry.mesh.volume - 1000.0, "die Kopie ist ein zweites Loch"

    removed = run_op("remove_feature", entry, profile, at_feature=slot.id)
    assert not any(feature.kind == "slot" for feature in removed.features.values())
    assert removed.mesh.volume == pytest.approx(whole, rel=1e-4), "die Platte ist wieder voll"


def slot_in_a_plate(width: float, length: float) -> MeshData:
    """80 x 40 x 10 mit einem durchgehenden Langloch, gebaut aus Booleschen.

    Nicht über ``drill``: Dieser Abschnitt prüft, was die Erkennung an einem
    fremden Netz liest, und ein Werkzeug, das seinen eigenen Erzeuger misst,
    prüft die Absicht statt der Sache.
    """
    body = MeshData.of(trimesh.creation.box(extents=(80.0, 40.0, 10.0)))
    travel = length - width
    tool = MeshData.of(trimesh.creation.box(extents=(travel, width, 20.0)))
    for x in (-travel / 2.0, travel / 2.0):
        cap = trimesh.creation.cylinder(radius=width / 2.0, height=20.0, sections=64)
        cap.apply_translation((x, 0.0, 0.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    return boolean("difference", [body, tool]).mesh


def with_a_bridge(mesh: MeshData, thickness: float, at: float, width: float) -> MeshData:
    """Ein schmaler Steg quer über das Loch, im oberen Drittel."""
    bridge = trimesh.creation.box(extents=(thickness, width + 2.0, 3.0))
    bridge.apply_translation((at, 0.0, 3.5))
    return boolean("union", [mesh, MeshData.of(bridge)]).mesh


@pytest.mark.parametrize(("thickness", "at"), [(0.42, 7.7), (0.5, 3.0), (1.0, 3.125), (1.3, 3.125)])
def test_a_bridge_across_a_slot_takes_its_through(thickness: float, at: float) -> None:
    """Wer hindurchsieht, sieht hindurch — und wer nicht, nicht.

    **Der Fall, der die Abtastung abgelöst hat.** ``_reaches_through`` prüfte
    die Mittellinie in Schritten von einem halben Radius und begründete das
    mit „schmaler als jedes Stück Material, das ein Drucker legen kann". Bei
    Ø 5 sind das 1,25 mm; eine Extrusionsbahn ist 0,42 mm breit. Gemessen kamen
    Brücken von 0,5 und 1,0 mm als „Durchgang" zurück, eine von 1,3 mm nicht —
    es entschied, ob der Steg zufällig auf einen Abtastpunkt fiel.

    Die vier Fälle hier liegen absichtlich **zwischen** den alten Punkten
    (0 · ±1,25 · ±2,5 · ±3,75 …).
    """
    open_slot = slot_in_a_plate(5.0, 40.0)
    assert only_slot(open_slot).params["through"], "die Vorbedingung: offen ist offen"

    blocked = with_a_bridge(open_slot, thickness, at, 5.0)

    assert not only_slot(blocked).params["through"]


def test_a_slot_without_a_bridge_still_goes_through() -> None:
    """Die Gegenprobe zur Gegenprobe: Der strengere Test darf nicht alles zumachen."""
    assert only_slot(slot_in_a_plate(8.0, 30.0)).params["through"]


# --- Was der Agent liest ----------------------------------------------------------


@pytest.mark.parametrize("angle", [15.0, 30.0, 45.0, -45.0])
def test_the_digest_does_not_round_a_slanted_slot_onto_an_axis(
    angle: float, profile: Profile
) -> None:
    """Eine Rundung, die als Tatsache dasteht, ist eine stille Wahl (Regel 21).

    ``_axis_name`` nimmt die größte Komponente. Für die **Achse** einer Bohrung
    ist das richtig; die **Richtung** eines Langlochs ist ein stetiger Wert, und
    gemessen sagten 0, 15, 30, 44, 45 und minus 45 Grad alle sechs „+X".
    """
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=angle))

    line = _feature_line(slot.id, slot)
    assert "+X" not in line and "+Y" not in line, (
        f"eine schräge Richtung bekommt keinen Achsennamen — gelesen wurde {line!r}"
    )


@pytest.mark.parametrize(("angle", "wanted"), [(0.0, "+X"), (90.0, "+Y"), (0.3, "+X")])
def test_the_digest_names_the_axis_where_it_really_is_one(
    angle: float, wanted: str, profile: Profile
) -> None:
    """Und die andere Richtung: Wo eine Achse ist, steht ihr Name.

    0,3 Grad ist die Rundung, mit der eine gemessene Richtung aus dem Netz
    kommt — dort einen Vektor zu drucken wäre genauso falsch wie umgekehrt.
    """
    from app.i18n import set_language

    set_language("de")
    slot = only_slot(slotted(profile, slot_angle=angle))

    assert wanted in _feature_line(slot.id, slot)


def test_the_wall_around_a_slot_reaches_the_agent() -> None:
    """Der Steckbrief nennt die Wand — und zwar die dünnste (RM-152).

    Hier stand bis zum 12.09.2026 das Gegenteil: ``sleeve_at`` schwieg am
    Langloch, weil der halbe Unterschied zweier Durchmesser an einem Zapfen
    Ø 20 mit einem Langloch Ø 8 auf 14 mm **6 mm** ergab, wo die dünnste
    Stelle 3 misst — und eine zu dicke Wandangabe ist schlimmer als keine.
    Der Test schrieb dieses Schweigen fest; abgelöst wird er von der Zusage,
    die an seine Stelle tritt.

    **Und geprüft wird am Steckbrief und nicht an der Rechnung.** Die misst
    ``test_relations.py``; hier zählt, dass der Satz beim Agenten ankommt — er
    hat genau diesen Text und sonst nichts (§26.1), und ohne ihn liest er zwei
    unabhängige Zahlen und zieht das Langloch auf, bis von der Wand nichts
    übrig ist.
    """
    pin = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)
    tool = MeshData.of(trimesh.creation.box(extents=(6.0, 8.0, 40.0)))
    for x in (-3.0, 3.0):
        cap = trimesh.creation.cylinder(radius=4.0, height=40.0, sections=64)
        cap.apply_translation((x, 0.0, 0.0))
        tool = boolean("union", [tool, MeshData.of(cap)]).mesh
    body = boolean("difference", [MeshData.of(pin), tool]).mesh
    found = detect(body)
    slot = next(entry for entry in found.values() if entry.kind == "slot")

    from app.core.perceive.digest import _wall_note
    from app.core.perceive.relations import sleeves_of

    line = _feature_line(slot.id, slot) + _wall_note(slot, sleeves_of(found).get(slot.id))

    assert "Wand" in line, f"der Steckbrief nennt keine Wand: {line}"
    # Der Steckbrief schreibt für das Modell und nicht für den Kunden — dort
    # steht der Punkt, und ``localised`` hat hier nichts zu suchen.
    assert "Wand 3.00 mm" in line, (
        f"genannt wird die dünnste Stelle, nicht die Flanke (6,0): {line}"
    )


def test_the_slot_defaults_make_a_slot_and_not_an_error(profile: Profile) -> None:
    """Ein Feld, das mit einer Absage begrüßt, ist keine Vorgabe (Regel 17).

    Die Vorgabe der Länge stand auf 5,0 — dem Durchmesser einer gewöhnlichen
    Bohrung —, und ein Langloch muss länger sein als seiner. Wer den Dialog
    öffnete und übernahm, legte damit einen Schritt an, der bei **jeder**
    Auswertung anhält, auch bei jedem späteren Öffnen des Projekts (gefahren
    am 10.09.2026 an Roberts `weg1-halterung-anpassen.p3d`, Protokoll:
    „evaluation stopped at op 5").

    Gefahren wird hier der Weg ohne Merkmalsvorbelegung — Kommandozeile, Chat,
    Palette: nur ``at_feature``, alles andere aus dem Schema.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate(), features={})
    gebohrt = run_op(
        "drill_hole", entry, profile, x=0.0, y=0.0, z=5.0, axis="z", diameter=5.0, depth=0.0
    )
    bore = next(name for name, f in gebohrt.features.items() if f.kind == "hole")

    longer = run_op("slot_hole", gebohrt, profile, at_feature=bore)

    assert any(feature.kind == "slot" for feature in longer.features.values()), (
        "aus der Vorgabe entsteht ein Langloch und keine Absage"
    )


def test_a_slot_moves_and_closes_the_place_it_came_from(profile: Profile) -> None:
    """Wer versetzt, schließt die alte Stelle — sonst stehen zwei Löcher da.

    *Zum Langloch ziehen* führt seit dem 10.09.2026 seine eigene Mitte, damit es
    dieselbe Flächenplatzierung bekommt wie *Bohrung setzen* (Robert: „einfach
    wie wenn ich eine bohrung setze"). Gemessen ohne das Schließen: `hole_1`
    und `slot_1` im selben Körper, die alte Bohrung unverändert offen.

    Drei Nullen heißen dabei „lass es, wo es ist" — der Weg über Chat und
    Kommandozeile nennt keine Stelle, und der Ursprung wäre dort die falsche
    Antwort.
    """
    mesh = drill(
        plate(),
        profile=profile,
        position=(10.0, 5.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")

    versetzt = run_op(
        "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, x=-10.0, y=-8.0, z=0.0
    )

    arten = [feature.kind for feature in versetzt.features.values()]
    assert arten.count("slot") == 1, "genau ein Langloch"
    assert "hole" not in arten, "und die alte Bohrung ist zu"
    slot = next(feature for feature in versetzt.features.values() if feature.kind == "slot")
    assert slot.params["centre"] == pytest.approx((-10.0, -8.0, 0.0), abs=0.05)

    # Und ohne Stelle bleibt es, wo es war.
    geblieben = run_op("slot_hole", entry, profile, at_feature=bore, slot_length=20.0)
    stehend = next(feature for feature in geblieben.features.values() if feature.kind == "slot")
    assert stehend.params["centre"] == pytest.approx((10.0, 5.0, 0.0), abs=0.05)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("width", [8.0, 4.0], ids=["breiter", "schmaler"])
def test_a_slot_can_be_pulled_and_widened_in_one_step(
    profile: Profile, kind: str, width: float
) -> None:
    """Zug und neue Breite sind **ein** Schritt (Entscheidung Robert, 22.09.2026:
    „Ja eine transaktion").

    Wer an den Knöpfen zieht und daneben einen neuen Durchmesser eintippt,
    bekam erst den Durchmesser und musste danach neu ziehen — zwei Schritte
    gingen nicht, weil das Langloch nach dem ersten Zug neu heißt. Jetzt nimmt
    *Zum Langloch ziehen* die Breite selbst: Die alte Öffnung wird
    geschlossen, das Langloch in der neuen Breite geschnitten — auch in einer
    schmaleren, wo sonst die weitere Bohrung um das schmale Langloch stünde.

    Sollwerte aus dem Aufbau: Bohrung Ø 6 bei (0, 0), Gesamtlänge 20 über
    beide runden Enden (x = ±10), Breite 8 beziehungsweise 4; das Volumen
    ist 24 000 − 10 · (Breite · (20 − Breite) + π · Breite² / 4).
    """
    if kind == "brep":
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
        from app.core.brep import edit
        from app.core.brep.features import features_of
        from app.core.geom.mesh import as_mesh_data

        solid = edit.cut_bore(
            edit.box(90.0, 60.0, 10.0),
            position=(0.0, 0.0, 5.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=10.0,
        )
        entry = SceneObject(
            id="obj_1", name="Platte", mesh=solid, kind="brep", features=features_of(solid)
        )
        body_of = as_mesh_data
    else:
        mesh = drill(
            plate(),
            profile=profile,
            position=(0.0, 0.0, 5.0),
            axis="z",
            diameter=6.0,
            compensate=False,
        ).mesh
        entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))

        def body_of(value):
            return value

    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")

    pulled, findings = run_op_with_findings(
        "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, diameter=width
    )

    codes = [found.code for found in findings]
    assert "slot_hole.feature_lost" not in codes, codes
    slots = [feature for feature in pulled.features.values() if feature.kind == "slot"]
    assert len(slots) == 1 and "hole" not in [f.kind for f in pulled.features.values()]
    slot = slots[0]
    assert slot.params["diameter"] == pytest.approx(width, abs=0.05)
    assert slot.params["length"] == pytest.approx(20.0, abs=0.1)
    # Die Geometrie: an den Enden und quer offen in der neuen Breite, daneben
    # Material — auch dort, wo die alte Bohrung Ø 6 weiter war als das
    # schmale Langloch.
    body = body_of(pulled.mesh)
    half = width / 2.0
    mid = (float(body.bounds.minimum[2]) + float(body.bounds.maximum[2])) / 2.0
    open_points = [(10.0 - 0.3, 0.0, mid), (0.0, half - 0.2, mid), (0.0, 0.0, mid)]
    solid_points = [(0.0, half + 0.3, mid), (10.0 + 0.4, 0.0, mid)]
    assert not _inside(body, open_points).any(), "offen in der neuen Breite"
    assert _inside(body, solid_points).all(), "daneben Material"
    expected = float(np.prod(body.bounds.size)) - 10.0 * (
        width * (20.0 - width) + math.pi * width**2 / 4.0
    )
    assert body.raw.volume == pytest.approx(expected, rel=0.01)


@pytest.mark.parametrize("diameter", [2.0, 5.0, 12.0, 20.0, 40.0])
def test_a_length_the_recognition_cannot_hold_is_refused(diameter: float, profile: Profile) -> None:
    """Was hinterher kein Merkmal mehr wäre, wird vorher abgelehnt (Regel 17).

    **Der Anlass ist gemessen** (11.09.2026, Ø 2 bis Ø 40 in beiden
    Qualitätsstufen). Direkt über der alten Grenze — „länger als der
    Durchmesser" — liegt ein Streifen, in dem die Erkennung das Ergebnis nicht
    mehr als Langloch liest: erst als **Bohrung**, weil ein Zylinder auf den
    Mantel noch passt, und darüber als **gar nichts**, weil weder Zylinder noch
    Bogenpaar greifen. Ø 12 mit der Länge 12,5 ergab null Merkmale: kein
    Eintrag im Objektbaum, keine Maße im Bild, nichts zum Anklicken (Robert:
    „es gibt noch Fälle, wo das Langloch keine Maße im Viewport hat, nicht
    wählbar ist, im Objektbaum verschwindet").

    Der Griff im Bild rastet an :func:`prepare.shortest_slot`; über den Dialog,
    den Chat und die Kommandozeile kommt aber jede Zahl herein. Also fragt die
    Operation, und zwar gegen den **gemessenen** Durchmesser — gegen ihn misst
    auch die Erkennung.
    """
    entry = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 12.0))),
        features={},
    )
    drilled = run_op(
        "drill_hole", entry, profile, x=0.0, y=0.0, z=6.0, axis="z", diameter=diameter, depth=0.0
    )
    bore = next(feature for feature in drilled.features.values() if feature.kind == "hole")
    measured = float(bore.params["diameter"])
    shortest = shortest_slot(measured)

    # Eine Länge aus dem Streifen: über dem Durchmesser, unter der Grenze.
    with pytest.raises(ValidationError) as refused:
        run_op(
            "slot_hole",
            drilled,
            profile,
            at_feature=bore.id,
            slot_length=(measured + shortest) / 2.0,
        )
    assert refused.value.field == "slot_length"
    assert "shortest" in refused.value.values, (
        "die Absage nennt die Länge, die geht — sonst ist sie keine Handlungsanweisung"
    )

    # Und die Grenze selbst trägt: dort steht hinterher ein Langloch.
    pulled = run_op("slot_hole", drilled, profile, at_feature=bore.id, slot_length=shortest)
    arten = [feature.kind for feature in pulled.features.values()]
    assert arten.count("slot") == 1, f"Ø {diameter}: gefunden {arten}"


@pytest.mark.parametrize(
    ("kind", "values"),
    [
        ("über den Rand", {"slot_length": 20.0, "x": 38.0, "y": 0.0, "z": 5.0}),
        ("quer über sich selbst", {"slot_length": 26.0, "slot_angle": 90.0}),
    ],
)
def test_a_slot_that_is_no_longer_one_says_so(
    kind: str, values: dict[str, float], profile: Profile
) -> None:
    """Ein Merkmal, das verschwindet, verschwindet nicht schweigend (Regel 17).

    Zwei Wege führten dahin, beide gemessen (11.09.2026): Wer über den Rand
    des Körpers zieht, bekam einen offenen Schlitz und danach eine bis drei
    Verrundungen; wer quer über das eigene Langloch zieht, ein Kreuz und vier.
    Im Objektbaum standen danach Verrundungen, die Auswahl zeigte ins Leere,
    und gesagt wurde nichts (Robert: „auf einem langloch 2 werden und nicht
    mehr wählbar").

    **Beide Wege sind seither keine Verluste mehr**: Über den Rand bleibt ein
    offenes Langloch erkennbar, und ein Zug quer über sich selbst **dreht** das
    Langloch seit dem 15.09.2026, statt es zu kreuzen (Robert: „habe ich 2
    langlöcher"). Der Befund ``slot_hole.feature_lost`` bleibt für den Fall,
    den keiner der beiden mehr erzeugt — und hier steht, dass er hier nicht
    kommt.
    """
    mesh = drill(
        plate(),
        profile=profile,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    started = (
        run_op("slot_hole", entry, profile, at_feature=bore, slot_length=20.0)
        if "sich selbst" in kind
        else entry
    )
    chosen = (
        next(name for name, feature in started.features.items() if feature.kind == "slot")
        if started is not entry
        else bore
    )

    pulled, findings = run_op_with_findings(
        "slot_hole", started, profile, at_feature=chosen, **values
    )

    codes = [entry.code for entry in findings]
    assert "slot_hole.feature_lost" not in codes, f"{kind}: {codes}"
    slots = [feature for feature in pulled.features.values() if feature.kind == "slot"]
    assert len(slots) == 1, f"{kind}: genau ein Langloch, gefunden {codes}"
    if kind == "über den Rand":
        assert slots[0].params.get("open"), "ein offenes Langloch bleibt erkennbar"
        return
    assert "slot_hole.turned" in codes, f"{kind}: die Drehung sagt sich an"
    before = started.features[chosen].params["direction"]
    across = abs(sum(a * b for a, b in zip(before, slots[0].params["direction"], strict=True)))
    assert across == pytest.approx(0.0, abs=1e-3), "und das eine liegt quer zur alten Richtung"


def test_the_same_word_comes_from_the_exact_kernel(profile: Profile) -> None:
    """„Zwischen den beiden soll es keinen unterschied geben" (Robert, 10.09.2026).

    Der exakte Zweig erkennt seine Merkmale über die Topologie
    (``brep.features.features_of``) und lief deshalb an der Prüfung des
    Netz-Zweigs vorbei: dieselbe Geste, dasselbe Ergebnis, kein Wort dazu.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    solid = edit.cut_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
    )
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=solid, kind="brep", features=features_of(solid)
    )
    bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")

    _output, findings = run_op_with_findings(
        "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, x=38.0, y=0.0, z=5.0
    )

    codes = [found.code for found in findings]
    assert "slot_hole.feature_lost" not in codes, codes
    assert "bore.over_the_edge" in codes


def _two_slots_side_by_side(profile: Profile) -> tuple[SceneObject, str, str]:
    """Eine Platte mit zwei Langlöchern dicht nebeneinander — und ihren Kennungen.

    **Groß genug, dass die Zuordnung sie verwechseln kann.** ``match`` nimmt
    Lage bis acht Prozent der Modelldiagonale an; an 160 x 120 x 10 sind das
    sechzehn Millimeter, und die zwei Löcher stehen zwölf auseinander.
    """
    mesh = MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 10.0)))
    for y in (-6.0, 6.0):
        mesh = drill(
            mesh,
            profile=profile,
            position=(0.0, y, 5.0),
            axis="z",
            diameter=4.0,
            compensate=False,
            slot_length=14.0,
        ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    names = sorted(name for name, feature in entry.features.items() if feature.kind == "slot")
    assert len(names) == 2, names
    lower = min(names, key=lambda name: float(entry.features[name].params["centre"][1]))
    upper = max(names, key=lambda name: float(entry.features[name].params["centre"][1]))
    return entry, lower, upper


def test_a_turned_slot_does_not_borrow_its_neighbour(profile: Profile) -> None:
    """Das gedrehte Langloch behält seinen Namen — und das daneben seinen.

    ``match`` nimmt ein Merkmal an, solange Lage und Durchmesser unter seiner
    Schwelle liegen — acht Prozent der Modelldiagonale, an dieser Platte
    sechzehn Millimeter. Zwei Langlöcher zwölf Millimeter auseinander, das
    obere quer über sich selbst gezogen: Bis zum 15.09.2026 wurde es ein Kreuz
    und war verloren, und ohne Nachprüfung träfe die Zuordnung das **untere**
    (gemessen: Kosten 0,75 unter der Schwelle 1,0), das bekäme die Kennung des
    oberen (Fund des Reviews, 11.09.2026). Seit die Drehung die alte Richtung
    schließt, steht das obere gedreht an seiner Stelle — und die Zuordnung muss
    genau dieses treffen, nicht das Nachbarloch.
    """
    entry, lower, upper = _two_slots_side_by_side(profile)

    # Sechzehn quer: von y = -2 bis 14, das untere Loch endet bei -4.
    pulled, findings = run_op_with_findings(
        "slot_hole", entry, profile, at_feature=upper, slot_length=16.0, slot_angle=90.0
    )

    codes = [found.code for found in findings]
    assert "slot_hole.feature_lost" not in codes, codes
    assert "slot_hole.turned" in codes, codes
    remaining = sorted(name for name, feature in pulled.features.items() if feature.kind == "slot")
    assert remaining == sorted([lower, upper]), remaining
    # Das untere heißt weiter, wie es hieß, und liegt, wo es lag …
    assert float(pulled.features[lower].params["centre"][1]) == pytest.approx(-6.0, abs=0.05)
    # … und das obere liegt gedreht an seiner alten Mitte.
    turned = pulled.features[upper]
    assert float(turned.params["centre"][1]) == pytest.approx(6.0, abs=0.05)
    assert abs(float(turned.params["direction"][1])) == pytest.approx(1.0, abs=1e-3), (
        "es liegt jetzt längs Y"
    )


def test_the_exact_kernel_looks_for_the_one_slot_and_not_for_any(profile: Profile) -> None:
    """Am exakten Körper steht ein zweites Langloch — und das gezogene dreht sich.

    Hier stand ``any(kind == "slot")``: Ein zweites Langloch im Körper, und die
    Ansage blieb aus, obwohl aus dem gezogenen ein Kreuz geworden war (Fund des
    Reviews, 11.09.2026). Seit dem 15.09.2026 gibt es das Kreuz nicht mehr —
    der exakte Kern schließt die alte Richtung wie das Netz (``fill_bore`` mit
    Länge und Winkel) —, und gesucht wird weiter **das eine** Langloch: das
    gedrehte an seiner Stelle, nicht irgendeines.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    solid = edit.box(160.0, 120.0, 10.0)
    for y in (-6.0, 6.0):
        solid = edit.slot_bore(
            solid,
            position=(0.0, y, 5.0),
            direction=(0.0, 0.0, 1.0),
            diameter=4.0,
            depth=10.0,
            length=14.0,
            angle_deg=0.0,
            overlap=0.1,
        )
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=solid, kind="brep", features=features_of(solid)
    )
    upper = max(
        (name for name, feature in entry.features.items() if feature.kind == "slot"),
        key=lambda name: float(entry.features[name].params["centre"][1]),
    )

    output, findings = run_op_with_findings(
        "slot_hole", entry, profile, at_feature=upper, slot_length=16.0, slot_angle=90.0
    )

    codes = [found.code for found in findings]
    assert "slot_hole.feature_lost" not in codes, codes
    assert "slot_hole.turned" in codes, codes
    found = features_of(output.mesh)
    slots = {name: feature for name, feature in found.items() if feature.kind == "slot"}
    assert len(slots) == 2, sorted(slots)
    turned = max(slots.values(), key=lambda feature: float(feature.params["centre"][1]))
    assert float(turned.params["centre"][1]) == pytest.approx(6.0, abs=0.05)
    assert abs(float(turned.params["direction"][1])) == pytest.approx(1.0, abs=1e-3), (
        "das obere liegt jetzt längs Y"
    )


# --- RM-155: der Mantel aus einem Stück ------------------------------------------------


def a_foreign_slot(diameter: float, travel: float) -> MeshData:
    """Ein Langloch, wie es ein eingelesenes Netz hat — ohne Solidon-Operation.

    ``drill`` lässt seit dem 11.09.2026 kein so knappes Langloch mehr zu
    (:func:`app.core.geom.prepare.shortest_slot`); wer den Streifen darunter
    prüfen will, muss schneiden wie ein fremdes Programm: Quader minus
    aufgezogenes Stadion.
    """
    from app.core.geom.sketch_solid import extrude_profile
    from app.core.types import PlaneFrame

    plate_body = MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 12.0)))
    outline = slot_profile(radius=diameter / 2.0, travel=travel, angle_deg=0.0)
    frame = PlaneFrame(
        origin=(0.0, 0.0, -10.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    tool = extrude_profile(outline, 20.0, frame)
    return boolean("difference", [plate_body, MeshData.of(tool)]).mesh


@pytest.mark.parametrize(
    ("diameter", "travel"),
    [(12.0, 0.5), (20.0, 0.5), (40.0, 0.8), (40.0, 1.0), (5.0, 0.3)],
)
def test_a_barely_pulled_slot_in_a_foreign_mesh_is_still_one(
    diameter: float, travel: float
) -> None:
    """RM-155: Zwischen „ein Zylinder passt" und „zwei Bögen" stand nichts.

    Gemessen am 11.09.2026 über Ø 2 bis Ø 40: Unter rund fünf Prozent Weg
    hält die Einpassung den Mantel für einen Zylinder; knapp darüber passt
    weder Zylinder noch Bogenpaar, weil die Flanken für die Krümmungstrennung
    zu schmal sind — Ø 12 auf 12,5 mm ergab **kein** Merkmal, Ø 20 auf 20,5
    ebenso, Ø 40 auf 40,8. Kein Eintrag im Objektbaum, nichts zum Anklicken.
    Solidon schneidet seit demselben Tag nicht mehr so knapp; ein eingelesenes
    Netz kommt trotzdem dorthin.

    :func:`perceive.features.fit_stadium` misst den ganzen Fleck: ein Prisma
    über einem Stadion. Die Abnahme aus dem Register ist der erste Fall; die
    vier großen fallen ohne den Auffangweg (Gegenprobe 11.09.2026). Ø 5 auf
    0,3 geht weiter über die zwei Bögen und steht hier dafür, dass der alte
    Weg bleibt.
    """
    mesh = a_foreign_slot(diameter, travel)

    slot = only_slot(mesh)

    assert float(slot.params["diameter"]) == pytest.approx(diameter, abs=0.05)
    assert float(slot.params["length"]) == pytest.approx(diameter + travel, abs=0.05)
    assert float(slot.params["travel"]) == pytest.approx(travel, abs=0.05)
    assert slot.params["through"], "die Platte ist 12 mm dick, das Werkzeug 20"
    assert len(slot.face_indices) >= 6, "und der ganze Mantel ist anklickbar"


def test_the_stadium_fit_lies_on_the_cut_contour() -> None:
    """Die Ecken eines geschnittenen Langlochs liegen auf dem Stadion — auf ein Promille.

    Das ist die Begründung für die strenge Toleranz: Was ein Langloch ist,
    hat hier einen Rückstand von einem Promille (gemessen 0,0011 an Ø 12 auf
    12,5 mm; der Rest ist die Richtung aus zwei Scheiteln, die nicht auf die
    Stelle genau am Scheitel des Bogens abgetastet sind) — und was zwei
    Prozent daneben liegt, ist etwas anderes.
    """
    from app.core.perceive.features import (
        _connected_patches,
        _large_facet_faces,
        _one_body,
        fit_stadium,
    )

    body = _one_body(a_foreign_slot(12.0, 0.5)).raw
    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    mantle = max(_connected_patches(body, curved), key=len)

    fit = fit_stadium(body, mantle)

    assert fit is not None and fit.good and fit.inward
    assert fit.residual < 0.002
    assert fit.radius == pytest.approx(6.0, abs=0.01)
    assert fit.travel == pytest.approx(0.5, abs=0.02)
    # Die Platte ist um den Ursprung gebaut; halbe Tiefe ist z = 0.
    assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=0.05)
    assert fit.depth == pytest.approx(12.0, abs=0.05)


@pytest.mark.parametrize("corners", [6, 8])
def test_a_coarse_polygon_prism_is_not_a_stadium(corners: int) -> None:
    """Ein Sechs- oder Achteck ist weder Zylinder noch Stadion — und bleibt es.

    Genau davor warnt §41: Ein Verfahren, das Grundformen sucht, findet auch
    welche, die niemand gemeint hat. Ein Achteck hat eine Richtung, in der es
    länger ist als quer — um 8 Prozent —, und läge auf einem Stadion mit
    diesem Weg trotzdem 4 Prozent daneben. Die Toleranz hält es draußen.
    """
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    tool = trimesh.creation.cylinder(radius=5.0, height=20.0, sections=corners)
    mesh = boolean("difference", [block, MeshData.of(tool)]).mesh

    kinds = [feature.kind for feature in detect(mesh).values()]

    assert "slot" not in kinds, kinds


def test_a_stretched_hexagon_is_not_a_stadium() -> None:
    """Ein gestrecktes Sechseck hat Weg und Breite — und keine Bögen."""
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    hexagon = Polygon([(-8, -4), (0, -6), (8, -4), (8, 4), (0, 6), (-8, 4)])
    tool = trimesh.creation.extrude_polygon(hexagon, height=20.0)
    tool.apply_translation((0.0, 0.0, -10.0))
    mesh = boolean("difference", [block, MeshData.of(tool)]).mesh

    kinds = [feature.kind for feature in detect(mesh).values()]

    assert "slot" not in kinds, kinds


def a_bore_with_three_lugs(
    diameter: float = 57.4, lug_depth: float = 1.42, lug_width_deg: float = 25.0
) -> MeshData:
    """Die Bohrung eines Bajonettrings: drei Nasen mit Anlaufschrägen in der Wand.

    Nachgebaut nach dem Ring eines Kunden (Siebhalter, 15.09.2026): Bohrung
    Ø 57,4 durch einen Block, darin drei Nasen 1,42 mm nach innen, je 25 Grad
    breit und um 120 Grad versetzt, kürzer als die Wand und an beiden Enden
    über acht Grad angeschrägt — so gleitet der Gegenring hinein. Die Schrägen
    sind der Punkt: Sie verbinden Nasenkamm und Wand ohne Knick zu **einem**
    Fleck, auf den kein Zylinder passt.
    """
    block = MeshData.of(trimesh.creation.box(extents=(90.0, 90.0, 10.0)))
    bore = trimesh.creation.cylinder(radius=diameter / 2.0, height=20.0, sections=360)
    ring = boolean("difference", [block, MeshData.of(bore)]).mesh
    wall = diameter / 2.0
    crest = wall - lug_depth
    ramp_deg = 8.0
    lugs: list[MeshData] = []
    for start in (47.5, 167.5, 287.5):
        inner: list[tuple[float, float]] = []
        for step in range(int(lug_width_deg + 2 * ramp_deg) + 1):
            offset = step - (lug_width_deg / 2.0 + ramp_deg)
            outside = max(0.0, abs(offset) - lug_width_deg / 2.0)
            radius = crest + lug_depth * min(1.0, outside / ramp_deg)
            angle = math.radians(start + offset)
            inner.append((radius * math.cos(angle), radius * math.sin(angle)))
        outer = [
            (
                (wall + 1.0) * math.cos(math.radians(start + offset)),
                (wall + 1.0) * math.sin(math.radians(start + offset)),
            )
            for offset in (lug_width_deg / 2.0 + ramp_deg, -(lug_width_deg / 2.0 + ramp_deg))
        ]
        lug = trimesh.creation.extrude_polygon(Polygon(inner + outer), height=3.0)
        lug.apply_translation((0.0, 0.0, -1.5))
        lugs.append(MeshData.of(lug))
    return boolean("union", [ring, *lugs]).mesh


def test_a_bore_with_three_lugs_is_a_bore_and_no_slot() -> None:
    """Ein Kreis, den der Zylinderfit ablehnt, wird kein Langloch mit Weg null.

    Gemessen am Ring eines Kunden (15.09.2026): Die Wand Ø 57,4 mit drei
    Nasen fiel am Zylinderfit durch (Streuung 0,186 gegen 0,02), und die
    Langlochsuche belegte danach den ganzen Mantel als Stadion — Weg
    0,00005 mm, Rückstand 0,0077, angenommen. Im Objektbaum stand „Langloch
    Ø 57,39 auf 57,39 mm" mit sechs Handlungen, und jede davon hätte die
    Nasen still weggeschnitten. Ein Weg innerhalb der Toleranz des Fits
    ist keine Messung (§41); die Wand ist eine Bohrung, die Nasen sind, was
    sie sind.

    **Was dieser Test hält und was nicht:** das Ergebnis am Nachbau. Den
    alten Weg erreicht der Nachbau nicht — ein gerechneter Kreis hat den
    Weg exakt null, und ``fit_stadium`` gibt dann nichts zurück; die 0,00005
    mm der Kundendatei waren ihre Facettierung. Die Regel selbst hält
    :func:`test_a_stadium_within_its_own_tolerance_is_a_circle` an der Zahl.
    """
    found = detect(a_bore_with_three_lugs())

    kinds = [feature.kind for feature in found.values()]
    assert "slot" not in kinds, kinds
    holes = [feature for feature in found.values() if feature.kind == "hole"]
    assert len(holes) == 1, kinds
    assert float(holes[0].params["diameter"]) == pytest.approx(57.4, abs=0.05)


def test_a_stadium_within_its_own_tolerance_is_a_circle() -> None:
    """Die Zusicherung an der Zahl: Unter zwei Prozent des Radius gibt es keinen Weg."""
    from app.core.perceive.features import STADIUM_TOLERANCE, StadiumFit

    def stadium(travel: float) -> StadiumFit:
        return StadiumFit(
            axis=(0.0, 0.0, 1.0),
            centre=(0.0, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=10.0,
            travel=travel,
            depth=5.0,
            residual=0.001,
            inward=True,
        )

    assert not stadium(0.0001).good
    assert not stadium(10.0 * STADIUM_TOLERANCE).good
    assert stadium(10.0 * STADIUM_TOLERANCE * 1.5).good


def test_a_small_pocket_with_rounded_corners_is_still_not_a_slot() -> None:
    """Die Tasche aus der Gegenprobe oben, nur so klein, dass ihre Wände im Mantel liegen.

    Bei 40 x 24 sind die Wände große Facetten und die vier Ecken vier Flecken;
    bei 12 x 8 mit r = 3 ist der ganze Mantel **ein** Fleck — genau der, an
    dem der Stadion-Fit gefragt würde. Ihre geraden Kurzseiten liegen neben
    dem Bogen, den ein Stadion dort verlangt, und das sieht der Rückstand.
    """
    mesh = pocket_with_rounded_corners(12.0, 8.0, 3.0)

    kinds = [feature.kind for feature in detect(mesh).values()]

    assert "slot" not in kinds, kinds
    assert kinds.count("fillet") == 4, kinds


# --- Beide Kerne, derselbe Winkel, dieselbe Breite ---------------------------------


def _direction_angle(feature: Feature) -> float:
    """Die Richtung eines Langlochs als Winkel gegen X, ohne Vorder- und Rückseite."""
    along = feature.params["direction"]
    return math.degrees(math.atan2(along[1], along[0])) % 180.0


def _exact_plate_with_a_bore(direction: tuple[float, float, float], at: float = 0.0) -> SceneObject:
    from app.core.brep import edit
    from app.core.brep.features import features_of

    solid = edit.cut_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(at, 0.0, 5.0),
        direction=direction,
        diameter=6.0,
        depth=10.0,
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=solid, kind="brep", features=features_of(solid)
    )


def _mesh_plate_with_a_bore(
    profile: Profile, normal: tuple[float, float, float], at: float = 0.0
) -> SceneObject:
    mesh = drill(
        MeshData.of(trimesh.creation.box(extents=(90.0, 60.0, 10.0))),
        position=(at, 0.0, 5.0),
        axis="z",
        normal=normal,
        diameter=6.0,
        depth=0.0,
        anchor="centre",
        profile=profile,
        compensate=False,
    ).mesh
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


def test_both_kernels_pull_the_same_angle_from_a_bore_drilled_from_below(profile: Profile) -> None:
    """„Zwischen den beiden soll es keinen Unterschied geben" — auch im Vorzeichen.

    Gemessen 11.09.2026: Eine Bohrung von unten trug am Netz die Achse plus Z
    und am exakten Körper minus Z. ``frame_of`` spiegelt seine erste Achse mit
    der Normalen, also lag derselbe Winkel 45 an den zwei Kernen gespiegelt —
    45 Grad am Netz, 135 am exakten Körper (Fund des Reviews).
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")

    on_the_mesh = _mesh_plate_with_a_bore(profile, (0.0, 0.0, -1.0))
    exact = _exact_plate_with_a_bore((0.0, 0.0, -1.0))
    angles: dict[str, float] = {}
    for entry in (on_the_mesh, exact):
        bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
        pulled = run_op(
            "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, slot_angle=45.0
        )
        angles[entry.kind] = _direction_angle(only_slot(as_mesh_data(pulled.mesh)))

    assert angles["mesh"] == pytest.approx(45.0, abs=0.5), angles
    assert angles["brep"] == pytest.approx(45.0, abs=0.5), angles


def test_pulling_twice_with_the_same_angle_lengthens_on_both_kernels(profile: Profile) -> None:
    """Wer nach dem ersten Zug im Feld *Richtung* liest, was er eingetragen hat,
    und es noch einmal einträgt, bekommt ein längeres Langloch — kein Kreuz.

    Am exakten Körper kippte die Achse des Langlochs nach dem ersten Zug auf
    minus Z; das Feld zeigte minus 45, und die zweite 45 schnitt quer
    (gemessen 11.09.2026: ``slot_hole.crosses``, danach vier Verrundungen und
    kein Langloch mehr — Fund des Reviews).
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep.features import features_of
    from app.core.geom.prepare_ops import slot_angle_of

    for entry in (
        _mesh_plate_with_a_bore(profile, (0.0, 0.0, 1.0)),
        _exact_plate_with_a_bore((0.0, 0.0, 1.0)),
    ):
        bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
        first = run_op(
            "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, slot_angle=45.0
        )
        # ``run_op`` erkennt am Netz neu; am exakten Körper liest das Merkmal die Topologie.
        found = (
            features_of(first.mesh) if entry.kind == "brep" else detect(as_mesh_data(first.mesh))
        )
        slot = next(feature for feature in found.values() if feature.kind == "slot")
        shown = slot_angle_of(slot, tuple(float(value) for value in slot.params["axis"]))
        assert shown == pytest.approx(45.0, abs=0.5), f"{entry.kind}: das Feld zeigt {shown}"

        again = dataclasses.replace(first, features=found)
        second, findings = run_op_with_findings(
            "slot_hole", again, profile, at_feature=slot.id, slot_length=26.0, slot_angle=45.0
        )

        codes = [finding.code for finding in findings]
        assert "slot_hole.crosses" not in codes, f"{entry.kind}: {codes}"
        longer = only_slot(as_mesh_data(second.mesh))
        assert float(longer.params["length"]) == pytest.approx(26.0, abs=0.1), entry.kind


def _unit(values: Iterable[float]) -> tuple[float, float, float]:
    """Die Achse eines Merkmals als Einheitsvektor, damit ein Skalarprodukt sie vergleicht."""
    x, y, z = (float(value) for value in values)
    length = math.sqrt(x * x + y * y + z * z)
    return (x / length, y / length, z / length)


def test_a_tilted_bore_keeps_its_axis_when_pulled_to_a_slot(profile: Profile) -> None:
    """Ein Langloch an einer schrägen Bohrung folgt ihrer Achse, nicht der Z-Achse.

    Alle Langlochtests zogen bis zum 13.09.2026 entlang plus Z — gemessen über
    eine Mitschrift an ``slot_bore``: 138 Schnitte in acht Testdateien, keiner
    gekippt (Fund des Reviews). Die *Erkennung* war gekippt geprüft, die
    *Operation* nicht. Hier steht die Achse 17,5 Grad schräg, an beiden Kernen.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")

    tilted = (0.3, 0.0, math.sqrt(1.0 - 0.09))
    for entry in (_mesh_plate_with_a_bore(profile, tilted), _exact_plate_with_a_bore(tilted)):
        bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
        along = _unit(entry.features[bore].params["axis"])
        assert abs(sum(a * b for a, b in zip(along, tilted, strict=True))) == pytest.approx(
            1.0, abs=0.01
        ), f"{entry.kind}: die Bohrung liegt nicht auf der gebohrten Achse — {along}"

        pulled = run_op(
            "slot_hole", entry, profile, at_feature=bore, slot_length=20.0, slot_angle=0.0
        )
        slot = only_slot(as_mesh_data(pulled.mesh))
        found = _unit(slot.params["axis"])
        assert abs(sum(a * b for a, b in zip(found, tilted, strict=True))) == pytest.approx(
            1.0, abs=0.01
        ), f"{entry.kind}: das Langloch kippte auf {found}"
        assert float(slot.params["length"]) == pytest.approx(20.0, abs=0.1), entry.kind


def test_a_slot_that_cuts_the_body_in_two_says_so(profile: Profile) -> None:
    """Zerfällt der Körper, steht das im Bericht — nicht nur „über die Kante".

    Gemessen am 11.09.2026 und am 13.09.2026 nachgestellt: ein Langloch von
    100 mm durch einen 20-mm-Würfel ließ zwei Teile zurück, und der einzige
    Befund war ``bore.over_the_edge`` mit seiner offenen Flanke. Beide Kerne
    kennen ihre Teilezahl; hier sagen beide dasselbe.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")

    cube = SceneObject(
        id="obj_1",
        name="Würfel",
        mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0))),
    )
    through: dict[str, object] = {
        "x": 0.0,
        "y": 0.0,
        "z": 10.0,
        "axis": "z",
        "diameter": 5.0,
        "depth": 0.0,
        "anchor": "mouth",
    }
    cut_through, findings = run_op_with_findings(
        "drill_hole", cube, profile, slotted=True, slot_length=100.0, slot_angle=0.0, **through
    )
    codes = [finding.code for finding in findings]
    assert as_mesh_data(cut_through.mesh).component_count == 2
    assert "bore.splits_the_body" in codes, codes
    split = next(finding for finding in findings if finding.code == "bore.splits_the_body")
    assert split.values["count"] == 2

    kept, findings = run_op_with_findings(
        "drill_hole", cube, profile, slotted=True, slot_length=15.0, slot_angle=0.0, **through
    )
    assert as_mesh_data(kept.mesh).component_count == 1
    assert "bore.splits_the_body" not in [finding.code for finding in findings]

    # Der exakte Zwilling: 70 mm quer durch eine 60 mm breite Platte.
    exact = _exact_plate_with_a_bore((0.0, 0.0, 1.0))
    bore = next(name for name, feature in exact.features.items() if feature.kind == "hole")
    halves, findings = run_op_with_findings(
        "slot_hole", exact, profile, at_feature=bore, slot_length=70.0, slot_angle=90.0
    )
    assert halves.mesh.component_count == 2
    assert "bore.splits_the_body" in [finding.code for finding in findings]


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("bridged", [True, False], ids=["wieder-ein-stueck", "bleibt-zerfallen"])
def test_the_report_forgets_the_split_once_the_body_is_one_piece_again(
    profile: Profile, kernel: str, bridged: bool
) -> None:
    """„Er zerfällt in mehrere Teile" gilt nur, solange der Körper zerfallen ist.

    Gemessen am 29.09.2026: Würfel 20 mm, Langloch 100 mm quer durch (zwei
    Teile), danach ein Quader darüber vereinigt — am Endstand ein Stück, an
    beiden Kernen, und im Bericht standen weiter zwei Sätze vom Zerfall.
    ``bore.splits_the_body`` und der allgemeine ``feature.body_split`` der
    Auswertung fehlten in ``evaluate.ONE_PIECE_CODES``, wo ihr Zwilling
    ``mesh.components_split`` steht (``.claude/rules/operationen.md``,
    „Befunde statt Protokoll"). Die Gegenrichtung: Bleibt der Körper in zwei
    Teilen, bleibt auch der Satz.
    """
    if kernel == "brep":
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    load_operations()
    box = "create_brep_box" if kernel == "brep" else "create_box"
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Würfel und Langloch",
        [
            OperationDraft(op=box, params={"width": 20.0, "depth": 20.0, "height": 20.0}),
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={
                    "diameter": 5.0,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 20.0,
                    "axis": "z",
                    "depth": 0.0,
                    "anchor": "mouth",
                    "slotted": True,
                    "slot_length": 100.0,
                },
            ),
        ],
    )
    split = evaluate(project.document, profile, quality="fine")
    assert split.scene.objects["obj_1"].mesh.component_count == 2, "die Vorbedingung"
    if bridged:
        history.apply(
            "Brücke",
            [OperationDraft(op=box, params={"width": 20.0, "depth": 20.0, "height": 4.0})],
        )
        history.apply("Vereinigen", [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))])

    result = evaluate(project.document, profile, quality="fine")

    assert result.stopped_at is None
    parts = result.scene.objects["obj_1"].mesh.component_count
    assert parts == (1 if bridged else 2), "die Vorbedingung: der Endstand, den der Test meint"
    codes = [finding.code for finding in result.scene.report.findings]
    if bridged:
        assert not {"bore.splits_the_body", "feature.body_split"} & set(codes), codes
    else:
        assert "bore.splits_the_body" in codes, codes


def test_the_exact_kernel_warns_at_the_edge_as_well(profile: Profile) -> None:
    """An beiden Enden wird gefragt — an beiden Kernen.

    Eine Bohrung neun Millimeter vor der Kante, auf 20 gezogen, meldete am Netz
    ``bore.over_the_edge`` und am exakten Körper nichts (gemessen 11.09.2026,
    Fund des Reviews). Der Netz-Zwilling steht als Gegenprobe daneben.
    """
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")

    codes: dict[str, set[str]] = {}
    for entry in (
        _mesh_plate_with_a_bore(profile, (0.0, 0.0, 1.0), at=36.0),
        _exact_plate_with_a_bore((0.0, 0.0, 1.0), at=36.0),
    ):
        bore = next(name for name, feature in entry.features.items() if feature.kind == "hole")
        _output, findings = run_op_with_findings(
            "slot_hole", entry, profile, at_feature=bore, slot_length=20.0
        )
        codes[entry.kind] = {finding.code for finding in findings}

    assert "bore.over_the_edge" in codes["mesh"], codes
    assert "bore.over_the_edge" in codes["brep"], codes


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize(
    ("at", "length", "said"),
    [(36.0, 20.0, 1), (-36.0, 20.0, 1), (30.0, 20.0, 0), (0.0, 96.0, 1)],
    ids=["rechtes-ende", "linkes-ende", "innen", "beide-enden"],
)
def test_setting_a_slot_asks_at_both_ends_on_both_kernels(
    profile: Profile, kernel: str, at: float, length: float, said: int
) -> None:
    """*Bohrung setzen* mit dem Haken *Langloch* fragt an beiden Bogenmitten nach
    der Kante — an beiden Kernen, und über beide Enden mit einem Satz.

    Der exakte Zweig (``drill_brep_hole``) fragt so seit dem 12.09.2026, aber kein
    Test hielt es: Mit ``slot_ends`` auf die Mitte verkürzt blieben alle 559
    Langloch-, Bohr- und Vorschaufälle grün (Gegenprobe 29.09.2026). Der einzige
    Fall über das Register lag mitten in der Platte (Übergabe der Durchsicht vom
    11.09.2026).

    Soll von außen: Platte 90 mm breit, Kante bei 45; Langloch Ø 6 auf ``length``,
    Mitte bei ``at``. Das Stadion reicht bis ``|at| + (length - 6) / 2 + 3``, die
    runde Bohrung an derselben Mitte bis ``|at| + 3``: bei 36 also 46 gegen 39 mm
    — ein Ende steht über, die Mitte nicht. Bei 30 bleiben es 40 mm.
    """
    if kernel == "brep":
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
        from app.core.brep import edit

        entry = SceneObject(id="obj_1", name="Platte", mesh=edit.box(90.0, 60.0, 10.0), kind="brep")
        top = 10.0
    else:
        entry = SceneObject(
            id="obj_1",
            name="Platte",
            mesh=MeshData.of(trimesh.creation.box(extents=(90.0, 60.0, 10.0))),
        )
        top = 5.0
    reach = abs(at) + (length - 6.0) / 2.0 + 3.0
    assert (reach > 45.0) is (said == 1), "die Vorbedingung: das Soll kommt aus dem Umriss"
    assert abs(at) + 3.0 < 45.0, "die Vorbedingung: die Mitte allein bleibt im Material"

    _output, findings = run_op_with_findings(
        "drill_hole",
        entry,
        profile,
        x=at,
        y=0.0,
        z=top,
        axis="z",
        diameter=6.0,
        depth=0.0,
        anchor="mouth",
        compensate=False,
        slotted=True,
        slot_length=length,
    )

    over = [finding for finding in findings if finding.code == "bore.over_the_edge"]
    assert len(over) == said, [finding.code for finding in findings]


def test_pulling_a_slot_again_does_not_widen_it(profile: Profile) -> None:
    """Die Zugabe gilt dem ersten Zug — danach bleibt die Breite.

    Gemessen 11.09.2026 am Netz, Bohrung Ø 5 mit Materialtoleranz (5,1901):
    nach drei Zügen mit Zugabe 5,2057, 5,2213, 5,2371 — ein Sechzehntel
    Millimeter je Zug, ein Viertel der Materialtoleranz nach dreien. Ohne
    Zugabe am zweiten und dritten Zug bleibt die Änderung unter dem
    Messrauschen der Bogeneinpassung (Fund des Reviews).
    """
    mesh = drill(
        MeshData.of(trimesh.creation.box(extents=(80.0, 40.0, 10.0))),
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=5.0,
        depth=0.0,
        anchor="centre",
        profile=profile,
        compensate=True,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    chosen = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    widths: list[float] = []
    for length in (20.0, 24.0, 28.0):
        entry = run_op("slot_hole", entry, profile, at_feature=chosen, slot_length=length)
        slot = next(feature for feature in entry.features.values() if feature.kind == "slot")
        widths.append(float(slot.params["diameter"]))
        chosen = slot.id

    assert abs(widths[1] - widths[0]) < 0.006, widths
    assert abs(widths[2] - widths[0]) < 0.01, widths


def test_pulling_an_exact_slot_again_keeps_its_width_exactly(profile: Profile) -> None:
    """Am exakten Körper ist die Zugabe kein Messrauschen, sondern genau 0,02 je Zug."""
    pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
    from app.core.brep.features import features_of

    entry = _exact_plate_with_a_bore((0.0, 0.0, 1.0))
    chosen = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    widths: list[float] = []
    for length in (20.0, 24.0, 28.0):
        result = run_op("slot_hole", entry, profile, at_feature=chosen, slot_length=length)
        found = features_of(result.mesh)
        slot = next(feature for feature in found.values() if feature.kind == "slot")
        widths.append(float(slot.params["diameter"]))
        entry = dataclasses.replace(result, features=found)
        chosen = slot.id

    assert widths[1] == pytest.approx(widths[0], abs=1e-3), widths
    assert widths[2] == pytest.approx(widths[0], abs=1e-3), widths


def test_a_slot_length_beyond_the_body_is_refused_when_drilling_too(profile: Profile) -> None:
    """Dieselbe Schranke wie bei *Zum Langloch ziehen* — ``slot_length`` hat im
    Schema keine Obergrenze, und *Bohrung setzen* nahm hunderttausend
    Millimeter an (Übergabe der Durchsicht vom 11.09.2026).
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate(), features={})

    with pytest.raises(ValidationError) as refused:
        run_op(
            "drill_hole",
            entry,
            profile,
            x=0.0,
            y=0.0,
            z=5.0,
            axis="z",
            diameter=5.0,
            depth=0.0,
            slotted=True,
            slot_length=100000.0,
        )

    assert refused.value.field == "slot_length"
    assert refused.value.constraint == "maximum"


@pytest.mark.parametrize(
    ("angle", "says_so"),
    [(0.4, False), (1.0, True), (179.0, True), (180.4, False), (90.0, True)],
)
def test_the_turning_notice_starts_at_half_a_degree(angle: float, says_so: bool) -> None:
    """``SLOT_ACROSS_LIMIT`` ist als gemessen dokumentiert (0,5 Grad) und wurde
    bis zum 11.09.2026 nur bei 90 Grad gefahren. Seit dem 15.09.2026 kündigt
    dieselbe Grenze kein Kreuz mehr an, sondern die Drehung.
    """
    from app.core.geom.prepare_ops import _slot_turned as _slot_across_a_slot

    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 0.0),
            "depth": 10.0,
            "through": True,
        },
    )

    finding = _slot_across_a_slot(slot, (0.0, 0.0, 1.0), angle)

    assert (finding is not None) is says_so, (angle, finding)


# --- die Breite eines Langlochs (RM-156) ----------------------------------------------


def test_a_slot_gets_wider_and_keeps_its_travel(profile: Profile) -> None:
    """Ø 6 auf 20 wird zu Ø 8 auf 22 — der Weg bleibt, die Enden wachsen.

    Bis zum 12.09.2026 führte am Langloch kein Weg zu einer anderen Breite:
    ``resize_hole`` nahm nur die runde Bohrung, ``resize_feature`` nur Materie,
    und `NOT_APPLICABLE_HERE` sagte an beiden Zeilen „noch nicht gebaut"
    (RM-156).

    **Gemessen wird der Weg und nicht die Länge**, denn er ist der Grund, aus
    dem es Langlöcher gibt: Wer die Breite ändert und dabei den Verschiebeweg
    verlöre, bekäme ein anderes Bauteil. Die Länge folgt daraus — sie ist der
    Weg plus die neue Breite.
    """
    mesh = slotted(profile, diameter=6.0, slot_length=20.0)
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    before = only_slot(mesh)
    travel = float(before.params["travel"])

    wider = run_op("resize_hole", entry, profile, at_feature=before.id, diameter=8.0)

    slots = [feature for feature in wider.features.values() if feature.kind == "slot"]
    assert len(slots) == 1, f"ein Langloch erwartet, gefunden: {len(slots)}"
    assert slots[0].id == before.id, "die Kennung bleibt — jeder spätere Schritt hängt daran"
    assert float(slots[0].params["diameter"]) == pytest.approx(8.0, abs=0.2)
    assert float(slots[0].params["travel"]) == pytest.approx(travel, abs=0.2), (
        "der Verschiebeweg ist der Grund, aus dem es Langlöcher gibt"
    )
    assert float(slots[0].params["length"]) == pytest.approx(travel + 8.0, abs=0.3)


def test_a_slot_gets_narrower_again(profile: Profile) -> None:
    """Die Gegenrichtung: schmaler heißt, die alte Stelle geht zuerst zu.

    Beim Verbreitern deckt der neue Umriss den alten mit ab; beim Verschmälern
    bliebe ohne das Füllen die alte Breite stehen, und das Maß im Objektbaum
    wäre eine Behauptung über Material, das nicht mehr da ist.
    """
    mesh = slotted(profile, diameter=8.0, slot_length=22.0)
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    before = only_slot(mesh)

    narrower = run_op("resize_hole", entry, profile, at_feature=before.id, diameter=5.0)

    slots = [feature for feature in narrower.features.values() if feature.kind == "slot"]
    assert len(slots) == 1
    assert float(slots[0].params["diameter"]) == pytest.approx(5.0, abs=0.2)
    assert as_mesh_data(narrower.mesh).volume > as_mesh_data(mesh).volume, (
        "ein schmaleres Loch lässt mehr Material stehen"
    )


def test_the_panel_no_longer_says_the_width_is_unbuilt() -> None:
    """Was gebaut ist, steht nicht mehr unter „noch nicht gebaut" (Regel 17).

    Ein Satz, der eine Fähigkeit verneint, altert mit ihr — und ein
    ausgegrauter Knopf über einer Handlung, die es gibt, ist schlimmer als
    keiner.
    """
    from app.core.perceive.actions import NOT_APPLICABLE_HERE, reason_against

    assert ("slot", "resize_hole") not in NOT_APPLICABLE_HERE
    assert reason_against("resize_hole", "slot") is None, "die Operation nimmt das Langloch an"


def test_the_flanks_of_a_slot_are_no_faces_of_their_own(profile: Profile) -> None:
    """Am Drehteil eines Minigolf-Satzes (152 000 Dreiecke, 15.09.2026) standen die
    zwei ebenen Flanken eines Langlochs je einmal als Fläche und einmal als Teil
    des Langlochs im Baum. Was vollständig im Mantel liegt, gehört dem Langloch;
    Deckel, Boden und die vier Seiten der Platte bleiben Flächen."""
    body = _one_body(slotted(profile, diameter=6.0, slot_length=30.0))
    found = detect(body)
    slot = next(feature for feature in found.values() if feature.kind == "slot")
    inside = set(slot.face_indices)

    swallowed = [
        name
        for name, feature in found.items()
        if feature.kind == "face" and set(feature.face_indices) <= inside
    ]
    assert not swallowed, swallowed
    assert sum(feature.kind == "face" for feature in found.values()) >= 6


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_both_ways_to_a_slot_cut_the_same_slot(profile: Profile, kernel: str) -> None:
    """Bohren mit dem Haken *Langloch* und Bohren, dann *Zum Langloch ziehen*,
    sind derselbe Auftrag — und ergeben dasselbe Loch (Übertrag der Durchsicht
    v0.4.1, Punkt 2).

    Bis zum 22.09.2026 nicht: Der Zug an einer runden Bohrung legte die Zugabe
    aus §39 auf den Durchmesser, und aus 5,000 × 20,000 wurde 5,020 × 20,020 —
    an beiden Kernen, und ``BoreResult.diameter`` nannte dabei die 5,000. Die
    Zugabe hielt den Langlochkörper von der runden Wand fern; seit der Zug die
    alte Öffnung zuerst schließt, gibt es diese Wand nicht mehr, und der
    Schnitt geht in volles Material wie beim Bohren.
    """
    common = {
        "diameter": 5.0,
        "x": 0.0,
        "y": 0.0,
        "z": 5.0,
        "axis": "z",
        "nx": 0.0,
        "ny": 0.0,
        "nz": 1.0,
        "compensate": False,
    }
    if kernel == "brep":
        pytest.importorskip("OCP", reason="OpenCASCADE ist eine wahlweise Abhängigkeit")
        from app.core.brep import edit
        from app.core.brep.features import features_of

        body: object = edit.box(60.0, 40.0, 10.0)
    else:
        body = plate()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, kind=kernel)  # type: ignore[arg-type]

    def recognised(result: SceneObject) -> SceneObject:
        if kernel == "brep":
            return dataclasses.replace(result, features=features_of(result.mesh))
        return dataclasses.replace(result, features=detect(as_mesh_data(result.mesh)))

    drilled = recognised(
        run_op("drill_hole", entry, profile, slotted=True, slot_length=20.0, **common)
    )
    bored = recognised(run_op("drill_hole", entry, profile, **common))
    hole = next(name for name, feature in bored.features.items() if feature.kind == "hole")
    pulled = recognised(run_op("slot_hole", bored, profile, at_feature=hole, slot_length=20.0))

    exact = kernel == "brep"
    stadium = 24000.0 - (math.pi * 2.5**2 + 5.0 * 15.0) * 10.0
    for result in (drilled, pulled):
        slot = next(feature for feature in result.features.values() if feature.kind == "slot")
        assert slot.params["diameter"] == pytest.approx(5.0, abs=1e-6 if exact else 1e-3)
        assert slot.params["length"] == pytest.approx(20.0, abs=1e-6 if exact else 1e-3)
        if exact:
            assert result.mesh.volume == pytest.approx(stadium, rel=1e-9)
    assert pulled.mesh.volume == pytest.approx(drilled.mesh.volume, rel=1e-6 if exact else 2e-4)
