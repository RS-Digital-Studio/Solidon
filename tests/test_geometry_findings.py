"""Die Fehlerbilder aus der zweiten Durchsicht von ``app/core/geom/`` (02.09.2026).

Sie haben dieselbe Eigenschaft wie die der ersten Durchsicht
(``test_geometry_review.py``): Keiner wirft, keiner meldet etwas, jeder
liefert ein Ergebnis. Der Unterschied zum Versprochenen steht in den
Kennzahlen — an einer Wand, die dünner ist als die eingetragene, an einer
Bohrung, deren Fase am falschen Ende sitzt, an einem Stift, für den weder Wand
noch Einbindung geprüft wurden.

Darum misst hier jeder Test Zahlen und nicht „läuft durch": Alle diese Fälle
liefen durch.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import _plausible
from app.core.geom.hollow import hollow
from app.core.geom.measure import angle_between
from app.core.geom.mesh import MeshData, ray_hit_distances
from app.core.geom.pins import PIN_MIN_ENGAGEMENT, PIN_WALL, add_pins, plan_pins
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import SectionPlane
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.slice.analysis import cross_section
from app.core.types import Finding, OpContext, Profile, Quality, Scene, SceneObject, Vec3
from app.core.units import EPS_GEOM

load_operations()


# --- Werkzeuge ------------------------------------------------------------------


def run(
    op: str,
    entry: SceneObject | None = None,
    profile: Profile | None = None,
    *,
    quality: Quality = "fine",
    **params: Any,
) -> Any:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    spec = REGISTRY.get(op)
    scene = Scene(objects={entry.id: entry} if entry is not None else {})
    return spec.fn(
        OpContext(
            scene=scene,
            inputs=[entry] if entry is not None else [],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def turned_cube(size: float = 40.0, angle: float = 45.0) -> MeshData:
    """Ein Würfel, um die Hochachse gedreht — seine Seitenflächen stehen damit
    schräg zum Raster, an dem das Aushöhlen misst."""
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle), [0, 0, 1]))
    body.apply_translation((0.0, 0.0, size / 2.0))
    return MeshData.of(body)


def plate(width: float, depth: float, height: float) -> MeshData:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(body)


def surface_hits(mesh: MeshData, origin: Vec3, direction: Vec3) -> list[float]:
    """Die Tiefen, in denen ein Strahl auf Oberfläche trifft — der Reihe nach.

    Zwei Dreiecke teilen sich eine Kante, und ein Strahl durch sie zählt
    denselben Treffer zweimal; zusammengefasst wird deshalb, was näher
    beieinanderliegt als die Rechengenauigkeit.
    """
    triangles = np.asarray(mesh.raw.triangles, dtype=float)
    distances = np.sort(
        ray_hit_distances(
            triangles, np.asarray(origin, dtype=float), np.asarray(direction, dtype=float)
        )
    )
    hits: list[float] = []
    for value in distances:
        if not hits or float(value) - hits[-1] > EPS_GEOM:
            hits.append(float(value))
    return hits


def wall_across(mesh: MeshData, origin: Vec3, direction: Vec3) -> float:
    """Wie dick die Wand ist, die ein Strahl von außen als Erstes durchquert."""
    hits = surface_hits(mesh, origin, direction)
    assert len(hits) >= 2, f"der Strahl fand keine Wand: {hits}"
    return hits[1] - hits[0]


def bore_radius(mesh: MeshData, height: float, centre: Vec3) -> float | None:
    """Der Radius des Lochs um ``centre``, auf dieser Höhe gemessen."""
    shape = cross_section(mesh, height)
    if shape is None:
        return None
    for part in getattr(shape, "geoms", [shape]):
        for ring in part.interiors:
            if abs(ring.centroid.x - centre[0]) < 4.0 and abs(ring.centroid.y - centre[1]) < 4.0:
                low_x, _low_y, high_x, _high_y = ring.bounds
                return (high_x - low_x) / 2.0
    return None


def value_of(findings: list[Finding], code: str, key: str) -> float:
    entry = next(finding for finding in findings if finding.code == code)
    return float(entry.values[key])


# --- G-1: die schräge Wand blieb dünner als die eingetragene --------------------


def test_a_hollow_wall_holds_where_the_face_stands_slanted() -> None:
    """Erodiert wurde mit dem Kreuz, also entlang der L1-Norm: Senkrecht zu
    einer 45°-Fläche blieb davon nur ``n·pitch/√2``.

    Gemessen am 40er Würfel, um 45° gedreht, mit 3 mm Wand: 2,371 mm standen an
    der schrägen Seite, während der Befund 3,0 ± 0,5 mm meldete. Die Decke war
    mit 3,5 mm richtig — und genau deshalb fiel es nicht auf.
    """
    result = hollow(turned_cube(), 3.0, vents=0)
    eroded = value_of(result.findings, "hollow.done", "eroded_mm")
    tolerance = value_of(result.findings, "hollow.done", "tolerance_mm")

    slant = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
    standing = wall_across(result.mesh, tuple(slant * 30.0 + np.array([0.0, 0.0, 20.0])), -slant)

    assert abs(standing - eroded) <= tolerance + 0.001, (
        f"schräge Wand {standing:.3f} gegen gemeldete {eroded} ± {tolerance}"
    )


def test_the_flat_ceiling_stays_where_it_was() -> None:
    """Die Gegenprobe zur Kugelerosion: Achsparallel darf sich nichts ändern.

    Dort war das Kreuz schon richtig — eine Wand, die mit der neuen Rechnung
    plötzlich anders herauskäme, wäre kein Fortschritt, sondern ein zweiter
    Fehler.
    """
    result = hollow(turned_cube(angle=0.0), 3.0, vents=0)

    ceiling = wall_across(result.mesh, (0.0, 0.0, 60.0), (0.0, 0.0, -1.0))

    assert ceiling == pytest.approx(3.5, abs=0.001), "a + eroded - pitch/2 = 1,0 + 3,0 - 0,5"


# --- G-2: die Passbohrung saß verkehrt herum -----------------------------------


def pinned_plate(profile: Profile, shape: str = "round") -> tuple[Any, Any]:
    """Ein Quader, an der Mitte geteilt und verstiftet — Plan und Paar."""
    mesh = plate(60.0, 40.0, 40.0)
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=20.0)
    first, second, _findings = split_at_plane(mesh, plane)
    plan = plan_pins(mesh, plane, count=2, shape=shape)
    return plan, add_pins(first, second, plan, profile)


def test_the_bore_opens_at_the_seam_and_not_at_its_bottom(profile: Profile) -> None:
    """Die Bohrung wächst unter ihren Ursprung, ``_along_normal`` erwartet
    einen Körper auf +Z — versetzt statt gewendet landete die Mündung am tiefen
    Ende.

    Gemessen an der geteilten 40er Platte: an der Naht 2,525 mm Radius, am
    Grund 2,775. Das ist ein Hinterschnitt im Sackloch, die Einführfase liegt
    dort, wo der Stift nie hinkommt, und an der Naht bricht die Kante
    ungefast ab.
    """
    plan, pair = pinned_plate(profile)
    centre = plan.positions[0]
    depth = plan.length / 2.0

    at_seam = bore_radius(pair.second, 20.0 + 0.05, centre)
    at_bottom = bore_radius(pair.second, 20.0 + depth, centre)

    assert at_seam is not None and at_bottom is not None
    assert at_seam > at_bottom + 0.1, (
        f"die Fase gehört an die Mündung: Naht {at_seam:.3f}, Grund {at_bottom:.3f}"
    )


def test_the_bore_never_widens_towards_its_bottom(profile: Profile) -> None:
    """Ein Sackloch, das nach unten weiter wird, ist ein Hinterschnitt — es
    lässt sich weder sauber drucken noch wieder verlassen."""
    plan, pair = pinned_plate(profile)
    centre = plan.positions[0]

    radii = [
        bore_radius(pair.second, 20.0 + step, centre)
        for step in np.linspace(0.05, plan.length / 2.0, 12)
    ]
    measured = [value for value in radii if value is not None]

    assert len(measured) >= 8, "die Bohrung war auf ihrer Tiefe nicht zu finden"
    assert all(later <= earlier + EPS_GEOM for earlier, later in pairwise(measured)), (
        f"die Bohrung wird nach unten weiter: {[round(value, 3) for value in measured]}"
    )


def test_the_catch_of_a_snap_pocket_sits_at_the_seam(profile: Profile) -> None:
    """Die Rastkante gehört zwischen Mündung und Haken (§24.1).

    Der Baustein legt sie dorthin — ``tests/test_split_line.py`` misst das —,
    und das Setzen der Tasche nahm sie wieder mit ans tiefe Ende: Der Arm fand
    beim Einrasten keine Kante, hinter die er springen konnte. Die Tasche ist
    an der Kante schmaler als im freien Teil dahinter; gemessen wird also die
    Breite quer zur Rastrichtung.
    """
    plan, pair = pinned_plate(profile, shape="snap")
    assert plan.shape == "snap", "sonst prüft dieser Test etwas anderes"

    pocket = pair.second
    hollow_near = cross_section(pocket, 20.0 + 0.2)
    hollow_deep = cross_section(pocket, 20.0 + plan.length / 2.0 - 0.2)
    near = next(part for part in getattr(hollow_near, "geoms", [hollow_near]) if part.interiors)
    deep = next(part for part in getattr(hollow_deep, "geoms", [hollow_deep]) if part.interiors)

    def widest(part: Any) -> float:
        return max(ring.bounds[3] - ring.bounds[1] for ring in part.interiors)

    assert widest(near) < widest(deep), (
        "die Rastkante engt die Tasche an der Mündung ein, nicht am Grund: "
        f"{widest(near):.3f} gegen {widest(deep):.3f}"
    )


# --- G-3: der erzwungene Durchmesser umging jede Prüfung ------------------------


def test_a_forced_pin_diameter_still_has_to_fit_the_seam(profile: Profile) -> None:
    """``dataclasses.replace`` tauschte das Feld und ließ Sitz, Wand und Tiefe
    stehen, wie sie für den abgeleiteten Durchmesser gerechnet waren.

    Gemessen an einer 10 mm starken Platte mit 8 mm Wunschstift: 0,875 mm Wand
    blieben stehen statt der geforderten 1,6, die Einbindung lag bei 4,5 mm je
    Hälfte statt der nötigen 6,0 — und kein Befund sagte ein Wort.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate(10.0, 100.0, 40.0))

    result = run("split_pinned", entry, profile, axis="z", position=20.0, pins=2, diameter=8.0)

    codes = [finding.code for finding in result.findings]
    assert "split.face_too_small" in codes, codes
    assert not [key for key in result.outputs[1].features if key.startswith("bore")], (
        "8 mm brauchen 11,2 mm Naht — dort darf keine Bohrung stehen"
    )


def test_a_pin_that_fits_keeps_its_wall_and_its_engagement(profile: Profile) -> None:
    """Die Gegenprobe: Ein Wunschdurchmesser, für den Platz ist, wird gesetzt —
    mit der Wand und der Einbindung, die die Planung für ihn verlangt."""
    width, wish = 10.0, 4.0
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate(width, 100.0, 40.0))

    result = run("split_pinned", entry, profile, axis="z", position=20.0, pins=2, diameter=wish)

    bores = [
        feature for key, feature in result.outputs[1].features.items() if key.startswith("bore")
    ]
    assert len(bores) == 2, [finding.code for finding in result.findings]
    for bore in bores:
        wall = (width - float(bore.params["diameter"])) / 2.0
        assert wall >= PIN_WALL - EPS_GEOM, f"Restwand {wall:.3f}"
        assert float(bore.params["depth"]) >= wish * PIN_MIN_ENGAGEMENT, bore.params


def test_a_wish_that_gets_thinner_says_so_and_a_derived_one_stays_silent() -> None:
    """Dünner statt gar nicht ist richtig — aber nicht stillschweigend.

    Eine 100 auf 100 mm große Naht in einem 12 mm starken Teil trägt keinen
    8-mm-Stift: 4,0 mm Einbindung stehen zur Verfügung, 6,0 wären nötig. Die
    Planung nimmt ihn deshalb auf 5,33 mm zurück. Wer diese acht selbst
    eingetragen hat, erfährt das jetzt; wo die Planung ihr eigenes Maß
    korrigiert, bleibt es stumm wie bisher.
    """
    mesh = plate(100.0, 100.0, 12.0)
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=6.0)

    wished = plan_pins(mesh, plane, count=2, diameter=8.0)
    derived = plan_pins(mesh, plane, count=2)

    assert wished.diameter < 8.0 - EPS_GEOM, "sonst prüft dieser Test nichts"
    assert [finding.code for finding in wished.findings] == ["split.pin_thinner"]
    assert derived.diameter == pytest.approx(wished.diameter)
    assert [finding.code for finding in derived.findings] == []


def test_the_derived_diameter_stays_what_it_was() -> None:
    """Ohne Wunsch bleibt alles beim Alten: Der Durchmesser kommt aus der
    schmalsten Richtung der Schnittfläche."""
    mesh = plate(10.0, 100.0, 40.0)
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=20.0)

    assert plan_pins(mesh, plane, count=2).diameter == pytest.approx(3.0)


# --- G-4: die Kugel mit 128 Segmenten -------------------------------------------


def test_a_sphere_at_the_top_of_its_range_stays_a_body_and_not_a_swarm() -> None:
    """``segments // 12`` ging als Unterteilungstiefe in die Icosphere, und die
    wächst mit ``20 · 4ⁿ``: 128 Segmente ergaben 20 971 520 Dreiecke.

    Das ist kein langsamer Körper, das ist einer, der die Sitzung anhält —
    gerechnet, gespeichert und gezeichnet wird er in jedem Schritt danach
    wieder.
    """
    result = run("create_sphere", diameter=20.0, segments=128)

    assert result.outputs[0].mesh.triangle_count <= 21_000


def test_more_segments_never_make_the_sphere_coarser() -> None:
    """Was der Regler verspricht, gilt bis zu seiner Grenze — und darüber
    bleibt die Kugel, wie sie ist, statt zu explodieren."""
    counts = [
        run("create_sphere", diameter=20.0, segments=segments).outputs[0].mesh.triangle_count
        for segments in (8, 24, 60, 128)
    ]

    assert counts == sorted(counts)
    assert counts[2] == counts[3], "ab 60 Segmenten ist die Grenze erreicht"


# --- G-5: Kegel, Kegelstumpf und Ring direkt anlegen -----------------------------


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_a_created_frustum_has_its_measured_shape_and_is_recognised(quality: Quality) -> None:
    bottom, top, height = 20.0, 10.0, 12.0

    result = run(
        "create_cone",
        quality=quality,
        bottom_diameter=bottom,
        top_diameter=top,
        height=height,
        segments=96,
        name="",
    )
    mesh = result.outputs[0].mesh
    expected_volume = math.pi * height * (bottom**2 + bottom * top + top**2) / 12.0

    assert mesh.is_watertight and mesh.component_count == 1
    assert mesh.volume == pytest.approx(expected_volume, rel=0.005)
    assert mesh.bounds.minimum == pytest.approx((-bottom / 2.0, -bottom / 2.0, 0.0))
    assert mesh.bounds.maximum == pytest.approx((bottom / 2.0, bottom / 2.0, height))
    cones = [feature for feature in detect(mesh).values() if feature.kind == "cone"]
    assert len(cones) == 1
    assert cones[0].params["recess"] is False


@pytest.mark.parametrize(("bottom", "top"), [(18.0, 0.0), (0.0, 18.0)])
def test_a_created_cone_may_end_in_one_point(bottom: float, top: float) -> None:
    diameter, height = 18.0, 15.0

    result = run(
        "create_cone",
        bottom_diameter=bottom,
        top_diameter=top,
        height=height,
        segments=96,
        name="",
    )
    mesh = result.outputs[0].mesh

    assert mesh.is_watertight and mesh.component_count == 1
    assert mesh.volume == pytest.approx(math.pi * (diameter / 2.0) ** 2 * height / 3.0, rel=0.005)
    assert mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert mesh.bounds.maximum[2] == pytest.approx(height)
    assert any(feature.kind == "cone" for feature in detect(mesh).values())


def test_two_zero_cone_diameters_are_rejected() -> None:
    with pytest.raises(ValidationError) as caught:
        run(
            "create_cone",
            bottom_diameter=0.0,
            top_diameter=0.0,
            height=10.0,
            segments=48,
            name="",
        )

    assert caught.value.field == "bottom_diameter"
    assert caught.value.constraint == "range"


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_a_created_torus_has_its_measured_shape_and_is_recognised(quality: Quality) -> None:
    outer, tube = 40.0, 8.0
    major_radius = (outer - tube) / 2.0
    minor_radius = tube / 2.0

    result = run(
        "create_torus",
        quality=quality,
        outer_diameter=outer,
        tube_diameter=tube,
        segments=64,
        name="",
    )
    mesh = result.outputs[0].mesh
    expected_volume = 2.0 * math.pi**2 * major_radius * minor_radius**2

    assert mesh.is_watertight and mesh.component_count == 1
    volume_tolerance = 0.02 if quality == "draft" else 0.005
    assert mesh.volume == pytest.approx(expected_volume, rel=volume_tolerance)
    assert mesh.bounds.minimum == pytest.approx((-outer / 2.0, -outer / 2.0, 0.0))
    assert mesh.bounds.maximum == pytest.approx((outer / 2.0, outer / 2.0, tube))
    rings = [feature for feature in detect(mesh).values() if feature.kind == "torus"]
    assert len(rings) == 1
    assert rings[0].params["diameter"] == pytest.approx(major_radius * 2.0, abs=0.2)
    assert rings[0].params["tube_diameter"] == pytest.approx(tube, abs=0.2)


def test_a_torus_that_reaches_its_axis_is_rejected() -> None:
    with pytest.raises(ValidationError) as caught:
        run(
            "create_torus",
            outer_diameter=20.0,
            tube_diameter=10.0,
            segments=48,
            name="",
        )

    assert caught.value.field == "tube_diameter"
    assert caught.value.constraint == "crosses_axis"


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_an_odd_torus_segment_count_keeps_the_declared_bounds(quality: Quality) -> None:
    outer, tube = 50.0, 10.0

    mesh = (
        run(
            "create_torus",
            quality=quality,
            outer_diameter=outer,
            tube_diameter=tube,
            segments=31,
            name="",
        )
        .outputs[0]
        .mesh
    )

    assert mesh.bounds.minimum == pytest.approx((-outer / 2.0, -outer / 2.0, 0.0))
    assert mesh.bounds.maximum == pytest.approx((outer / 2.0, outer / 2.0, tube))


@pytest.mark.parametrize(
    ("op", "params"),
    [
        (
            "create_cone",
            {"bottom_diameter": 20.0, "top_diameter": 8.0, "height": 12.0},
        ),
        ("create_torus", {"outer_diameter": 40.0, "tube_diameter": 8.0}),
    ],
)
def test_round_primitives_are_lighter_in_draft(op: str, params: dict[str, float]) -> None:
    draft = run(op, quality="draft", segments=96, name="", **params).outputs[0].mesh
    fine = run(op, quality="fine", segments=96, name="", **params).outputs[0].mesh

    assert draft.triangle_count < fine.triangle_count


# --- G-6: was als Ergebnis einer Booleschen durchging ---------------------------


def test_an_inverted_body_is_not_an_answer() -> None:
    """``_plausible`` versprach „leer oder umgestülpt ist keine Antwort" und
    prüfte den Betrag des Volumens — ein umgestülpter Körper hat davon reichlich.
    """
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    inside_out = body.copy()
    inside_out.invert()

    assert _plausible(MeshData.of(body))
    assert not _plausible(MeshData.of(inside_out))


def test_an_open_shell_is_not_an_answer() -> None:
    """Ein Körper mit einem Loch ist kein Körper: Sein Volumen ist eine Zahl,
    die aus einer Fläche gerechnet wurde, die keine Grenze zieht."""
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    open_shell = trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[:-2].copy())

    assert not open_shell.is_watertight, "sonst prüft dieser Test nichts"
    assert not _plausible(MeshData.of(open_shell))


def test_nothing_stays_an_answer_where_it_was_asked_for() -> None:
    """``allow_empty`` bleibt, wie es war — eine Verschneidung ohne
    gemeinsames Volumen ist eine Tatsache und kein Scheitern."""
    empty = MeshData.of(trimesh.Trimesh())

    assert _plausible(empty, allow_empty=True)
    assert not _plausible(empty)


# --- G-6: der Winkel und sein toter Zweig ---------------------------------------


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), 0.0),
        ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), 0.0),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 90.0),
        ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0), 45.0),
        ((1.0, 0.0, 0.0), (-1.0, 1.0, 0.0), 45.0),
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 0.0),
    ],
)
def test_the_angle_between_two_directions_is_always_the_smaller_one(
    first: Vec3, second: Vec3, expected: float
) -> None:
    """Der Winkel hatte zwei Zweige, die dasselbe rechneten. Diese Zahlen
    halten fest, dass das Zusammenlegen nichts verschoben hat."""
    assert angle_between(first, second) == pytest.approx(expected)
