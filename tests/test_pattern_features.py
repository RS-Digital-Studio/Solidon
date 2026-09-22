"""Muster: viele gleiche Zellen auf einer Fläche werden ein Merkmal (§21.1, RM-207).

Roberts Schraubendreherhalter (22.09.2026) trug 195 sechseckige Zellen — 1 199
ebene Flächen im Objektbaum, keine davon hieß Wabe. Die Zahlen des Halters
stehen hier als synthetische Platte nach: 220 × 114 × 20 mm, Sechsecke mit
9 mm Schlüsselweite in einem Gitter mit 10,4 mm Teilung, durchgehend. Dazu
die acht Muster, die ``apply_texture`` selbst zeichnet — jedes einmal
erkannt, entfernt und geändert, mit dem Volumen der Platte als Sollwert.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.texture_ops import PATTERNS
from app.core.perceive import patterns
from app.core.perceive.actions import actions_for
from app.core.perceive.digest import _feature_line
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    Feature,
    FeatureId,
    Finding,
    OpContext,
    PrinterProfile,
    Profile,
    Scene,
    SceneObject,
)

NOZZLE = PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0))
PROFILE = Profile(printer=NOZZLE, material=None)

#: Die Platte, auf die die Texturen kommen — wie in ``test_texture_ops``.
PLATE = (40.0, 30.0, 6.0)
PLATE_VOLUME = PLATE[0] * PLATE[1] * PLATE[2]

#: Der Halter in Zahlen: Schlüsselweite, Teilung, Dicke.
HOLDER_WIDTH = 9.0
HOLDER_PITCH = 10.4
HOLDER_THICKNESS = 20.0


def plate() -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=PLATE))


def hexagon(across_flats: float, height: float, centre: tuple[float, float, float]) -> MeshData:
    """Ein Sechseckprisma, flache Seiten in ±Y wie am Halter."""
    radius = across_flats / math.sqrt(3.0)
    corners = [
        (
            centre[0] + radius * math.cos(math.radians(60.0 * index)),
            centre[1] + radius * math.sin(math.radians(60.0 * index)),
        )
        for index in range(6)
    ]
    from shapely.geometry import Polygon

    prism = trimesh.creation.extrude_polygon(Polygon(corners), height=height)
    prism.apply_translation((0.0, 0.0, centre[2]))
    return MeshData.of(prism)


def honeycomb_plate(
    *,
    columns: int = 6,
    rows: int = 4,
    across_flats: float = HOLDER_WIDTH,
    pitch: float = HOLDER_PITCH,
    thickness: float = HOLDER_THICKNESS,
    through: bool = True,
) -> tuple[MeshData, int]:
    """Eine Platte mit Sechseckzellen im Wabengitter — und wie viele es sind."""
    # Bis an den Rand wie am Halter: eine Dreiviertelteilung Wand ringsum.
    width = columns * pitch + 1.5 * pitch
    height = rows * pitch * math.sqrt(3.0) / 2.0 + 1.5 * pitch
    body = MeshData.of(trimesh.creation.box(extents=(width, height, thickness)))
    cells: list[MeshData] = []
    step_y = pitch * math.sqrt(3.0) / 2.0
    depth = thickness + 2.0 if through else thickness / 2.0
    start = thickness / 2.0 - depth + (1.0 if through else 0.0)
    for row in range(rows):
        offset = pitch / 2.0 if row % 2 else 0.0
        for column in range(columns):
            x = (column - (columns - 1) / 2.0) * pitch + offset
            y = (row - (rows - 1) / 2.0) * step_y
            cells.append(hexagon(across_flats, depth, (x, y, start)))
    tools = MeshData.of(trimesh.util.concatenate([cell.raw for cell in cells]))
    outcome = boolean("difference", [body, tools], quality="fine", cancelled=NeverCancelled())
    return outcome.mesh, len(cells)


def run_op(op: str, entry: SceneObject, **params: object) -> tuple[SceneObject, list[Finding]]:
    """Eine Operation fahren und danach neu erkennen, wie die Auswertung es tut."""
    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=PROFILE,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    out = result.outputs[0]
    return dataclasses.replace(out, features=detect(as_mesh_data(out.mesh))), list(result.findings)


def textured(pattern: str, mode: str, pitch: float = 4.0, depth: float = 1.0) -> SceneObject:
    """Die Platte mit einer Textur von ``apply_texture`` und frischer Erkennung."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern=pattern,
        pitch=pitch,
        depth=depth,
        mode=mode,
        width=30.0,
        height=20.0,
        z=PLATE[2] / 2.0,
        nz=1.0,
    )
    return out


def only_pattern(features: Mapping[FeatureId, Feature]) -> Feature:
    found = [feature for feature in features.values() if feature.kind == "pattern"]
    assert len(found) == 1, f"genau ein Muster, gefunden {[f.id for f in found]}"
    return found[0]


def kinds(features: Mapping[FeatureId, Feature]) -> dict[str, int]:
    counted: dict[str, int] = {}
    for feature in features.values():
        counted[feature.kind] = counted.get(feature.kind, 0) + 1
    return counted


# --- Der Halter -------------------------------------------------------------------


def test_a_honeycomb_plate_is_one_pattern_with_the_holders_numbers() -> None:
    """195 Zellen waren 1 199 Flächen; jetzt sind sie ein Merkmal mit Maßen."""
    mesh, count = honeycomb_plate()
    found = detect(mesh)
    pattern = only_pattern(found)
    params = pattern.params
    assert params["style"] == "hexagon"
    assert params["lattice"] == "hexagonal"
    assert params["count"] == count
    assert params["partial"] == 0
    assert math.isclose(params["pitch"], HOLDER_PITCH, abs_tol=1e-3)
    assert math.isclose(params["cell_width"], HOLDER_WIDTH, abs_tol=1e-3)
    assert math.isclose(params["cell_depth"], HOLDER_THICKNESS, abs_tol=1e-3)
    assert params["through"] is True
    assert params["mode"] == "engraved"
    assert np.allclose(params["normal"], (0.0, 0.0, 1.0)), "die Vorderseite weist nach oben"
    # Die Wände gehen im Muster auf; die Platte behält ihre sechs Seiten.
    assert kinds(found) == {"face": 6, "pattern": 1}, kinds(found)
    assert len(pattern.face_indices) == count * 6 * 2, "sechs Wände zu zwei Dreiecken je Zelle"
    assert pattern.measure_sources["pitch"] == "facets"
    carrier = patterns.carrier_of(pattern, found)
    assert carrier is not None and carrier.params["normal"][2] > 0.99


def test_a_blind_honeycomb_is_engraved_and_not_through() -> None:
    mesh, count = honeycomb_plate(through=False)
    pattern = only_pattern(detect(mesh))
    assert pattern.params["through"] is False
    assert pattern.params["count"] == count
    assert math.isclose(pattern.params["cell_depth"], HOLDER_THICKNESS / 2.0, abs_tol=1e-3)


def test_eight_cells_are_not_a_pattern() -> None:
    """Weniger als MIN_CELLS bleiben, was sie sind: Flächen — Wände, an denen etwas geht."""
    mesh, count = honeycomb_plate(columns=4, rows=2)
    assert count == patterns.MIN_CELLS - 1
    found = detect(mesh)
    assert "pattern" not in kinds(found)
    assert kinds(found)["face"] == 6 + count * 6


# --- Die acht Muster von apply_texture -------------------------------------------


@pytest.mark.parametrize("mode", ["engraved", "raised"])
@pytest.mark.parametrize("pattern", PATTERNS)
def test_every_texture_is_recognised_as_its_own_style(pattern: str, mode: str) -> None:
    """Was Solidon zeichnet, liest es auch — unter demselben Namen."""
    pitch = 2.0 if pattern == "noise" else 4.0
    depth = 0.6 if pattern == "noise" else 1.0
    entry = textured(pattern, mode, pitch=pitch, depth=depth)
    found = entry.features
    read = only_pattern(found)
    assert read.params["style"] == pattern
    assert read.params["mode"] == mode
    assert math.isclose(read.params["cell_depth"], depth, abs_tol=1e-3)
    if pattern in {"voronoi", "noise"}:
        assert read.params["lattice"] == "none"
        assert read.params["count"] >= patterns.MIN_SCATTER
    else:
        assert read.params["lattice"] != "none"
        assert math.isclose(read.params["pitch"], pitch, abs_tol=0.01), read.params["pitch"]
    # Nichts bleibt neben dem Muster übrig: keine Wand, keine Bohrung, keine Rundung.
    assert kinds(found) == {"face": 6, "pattern": 1}, kinds(found)


def test_partial_cells_at_the_field_edge_belong_to_the_pattern() -> None:
    """Ein Feld endet an seinem Rechteck; die abgeschnittenen Sechsecke gehören dazu."""
    read = only_pattern(textured("hexagon", "engraved").features)
    assert read.params["partial"] > 0
    assert read.params["count"] > read.params["partial"]
    assert read.params["coverage"] == "rectangle"
    assert math.isclose(read.params["width"], 30.0, abs_tol=0.05)
    assert math.isclose(read.params["height"], 20.0, abs_tol=0.05)


def test_a_texture_over_the_whole_face_is_read_as_such() -> None:
    """Bis zum Rand gezeichnet heißt bis zum Rand gelesen — und nur dann.

    Der Halter mit seinen Rändern von einer Dreiviertelteilung ist ein Feld:
    Eine halbe Teilung Wand ist die Grenze, sonst kerbt ein Neuzeichnen mit
    weiterer Teilung die Seitenwände an (Review, 22.09.2026).
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    entry = dataclasses.replace(entry, features=detect(entry.mesh))
    top = next(
        f for f in entry.features.values() if f.kind == "face" and f.params["normal"][2] > 0.99
    )
    out, _findings = run_op(
        "apply_texture",
        entry,
        coverage="whole_face",
        face=top.id,
        pattern="hexagon",
        pitch=4.0,
        depth=1.0,
        mode="engraved",
    )
    read = only_pattern(out.features)
    assert read.params["coverage"] == "whole_face"
    mesh, _count = honeycomb_plate()
    assert only_pattern(detect(mesh)).params["coverage"] == "rectangle"


def test_the_cell_width_is_what_the_generator_drew() -> None:
    """Schlüsselweite der Wabe, Breite der Raute, Durchmesser der Noppe — wie gezeichnet."""
    expected = {
        "hexagon": 4.0 / 2.0 * 0.85 * math.sqrt(3.0),
        "knurl_diamond": 4.0 * 0.5,
        "rib": 4.0 * 0.5,
        "dimple": 4.0,
    }
    for pattern, width in expected.items():
        read = only_pattern(textured(pattern, "engraved").features)
        assert math.isclose(read.params["cell_width"], width, rel_tol=0.01), (pattern, read.params)


def test_a_straight_knurl_keeps_its_field_and_its_angle() -> None:
    """Die Rippen laufen unter 45 Grad, das Feld liegt gerade — wie gezeichnet."""
    read = only_pattern(textured("knurl_straight", "raised").features)
    assert read.params["style"] == "knurl_straight"
    assert math.isclose(read.params["angle"], 0.0, abs_tol=0.01)
    direction = np.asarray(read.params["direction"])
    assert math.isclose(abs(float(direction[0])), math.sqrt(0.5), abs_tol=0.01)


def turned(pattern: str, angle: float, width: float, height: float, pitch: float = 4.0) -> Feature:
    """Ein Muster in einem gedrehten Feld — klein genug, dass es in der Platte bleibt."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern=pattern,
        pitch=pitch,
        depth=1.0,
        mode="engraved",
        width=width,
        height=height,
        z=PLATE[2] / 2.0,
        nz=1.0,
        angle=angle,
    )
    return only_pattern(out.features)


@pytest.mark.parametrize("pattern,pitch", [("hexagon", 4.0), ("dimple", 3.0)])
def test_a_hexagonal_lattice_turned_by_ninety_degrees_keeps_its_field(
    pattern: str, pitch: float
) -> None:
    """Das Wabengitter sieht alle sechzig Grad gleich aus, das Feld nicht.

    Unter neunzig Grad gezeichnet meldete die Erkennung die Gitterrichtung 30
    und ein Feld von 25,6 auf 28,3 statt 24 auf 16 — die um dreißig Grad
    gedrehte Hülle des geraden Rechtecks. Neu gezeichnet hätte das Muster
    dieses größere Feld bekommen (Review, 22.09.2026).
    """
    read = turned(pattern, 90.0, 24.0, 16.0, pitch=pitch)
    assert read.params["style"] == pattern
    assert math.isclose(read.params["angle"] % 90.0, 0.0, abs_tol=0.01), read.params["angle"]
    assert {round(read.params["width"]), round(read.params["height"])} == {24, 16}


def test_a_short_straight_knurl_is_one_row_and_not_two() -> None:
    """Ob eine Reihe Rippen sind, entscheidet die Reihe — nicht der Stummel am Rand.

    Auf 28 auf 16 sind zwei der acht Streifen so kurz, dass ihre Stirnwände
    mehr Fläche haben als ein Fünftel ihrer Wand; einzeln beurteilt hießen
    sie Welle, die Reihe zerfiel in vier und zwei, und es gab kein Muster
    (Review, 22.09.2026). Gewichtet mit der Wandfläche sind es Rippen.
    """
    read = turned("knurl_straight", 0.0, 28.0, 16.0)
    assert read.params["style"] == "knurl_straight"
    assert read.params["count"] >= patterns.MIN_STRIPS
    assert math.isclose(read.params["width"], 28.0, abs_tol=0.05)


def test_a_straight_knurl_turned_by_ninety_degrees_keeps_its_hand() -> None:
    """Die Rippen laufen nach dem Ändern in derselben Richtung wie vorher — nicht gespiegelt."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern="knurl_straight",
        pitch=4.0,
        depth=1.0,
        mode="engraved",
        width=28.0,
        height=16.0,
        z=PLATE[2] / 2.0,
        nz=1.0,
        angle=90.0,
    )
    read = only_pattern(out.features)
    assert read.params["style"] == "knurl_straight"
    redrawn, _findings = run_op("resize_feature", out, at_feature=read.id, cell_depth=0.5)
    after = only_pattern(redrawn.features)
    assert np.allclose(after.params["direction"], read.params["direction"], atol=0.01), (
        after.params["direction"],
        read.params["direction"],
    )


# --- Was keine Textur ist ------------------------------------------------------------


def bored_plate(count_x: int, count_y: int, diameter: float, depth: float | None) -> MeshData:
    """Eine Platte mit runden Bohrungen im Raster — durch oder blind."""
    body = trimesh.creation.box(extents=(60.0, 40.0, 6.0))
    drills = []
    for i in range(count_x):
        for j in range(count_y):
            height = 8.0 if depth is None else depth + 1.0
            drill = trimesh.creation.cylinder(radius=diameter / 2.0, height=height, sections=24)
            z = 0.0 if depth is None else 3.0 - depth + height / 2.0
            x = (i - (count_x - 1) / 2.0) * 6.0
            y = (j - (count_y - 1) / 2.0) * 6.0
            drill.apply_translation((x, y, z))
            drills.append(drill)
    tools = MeshData.of(trimesh.util.concatenate(drills))
    return boolean(
        "difference", [MeshData.of(body), tools], quality="fine", cancelled=NeverCancelled()
    ).mesh


def test_a_grid_of_through_bores_stays_bores() -> None:
    """Ein Lochblech ist Bohrungen — an ihnen gelten die Bohrungshandlungen."""
    found = detect(bored_plate(5, 5, 3.0, None))
    assert "pattern" not in kinds(found)
    assert kinds(found)["hole"] == 25


def test_a_dozen_magnet_pockets_stay_bores() -> None:
    """Zwölf flache Taschen sind kein Noppenmuster — dafür sind es zu wenige."""
    found = detect(bored_plate(4, 3, 6.0, 3.0))
    assert "pattern" not in kinds(found)
    assert kinds(found)["hole"] == 12


def test_deep_blind_bores_on_a_lattice_stay_bores() -> None:
    """Kernlöcher, tiefer als das Doppelte ihrer Breite, sind keine Noppen."""
    found = detect(bored_plate(5, 5, 2.0, 5.0))
    assert "pattern" not in kinds(found)
    assert kinds(found)["hole"] == 25


def test_shallow_bores_in_a_square_grid_stay_bores() -> None:
    """25 Magnettaschen in fünf Reihen zu fünf sind kein Noppenmuster.

    Flach, blind und mehr als zwanzig — alles, was eine Noppe braucht, bis auf
    das Gitter: ``apply_texture`` setzt Noppen im Wabengitter, nie im
    Quadratraster. Runde Zellen außerhalb des Wabengitters sind Bohrungen im
    Raster, und an denen bleiben die Bohrungshandlungen (Review, 22.09.2026:
    vorher ein „Noppenmuster“ mit ``lattice == "square"``, das *Merkmal
    ändern* als Wabengitter neu gezeichnet hätte).
    """
    found = detect(bored_plate(5, 5, 4.0, 2.0))
    assert "pattern" not in kinds(found)
    assert kinds(found)["hole"] == 25


def test_a_wall_nobody_owns_never_swallows_a_foreign_face() -> None:
    """Die Wände einer Welle gehören keinem Merkmal — und ziehen kein fremdes mit.

    Ein unbesessenes Dreieck trägt den Besitzer -1, und ``names[-1]`` war das
    letzte Merkmal der Liste: die kleinste Fläche des Körpers. Mit einer
    Tasche von 1,2 mm neben dem Feld war das eine Taschenwand, und sie
    verschwand mit dem Muster aus dem Baum (Review, 22.09.2026).
    """
    entry = textured("wave", "engraved")
    pocket = trimesh.creation.box(extents=(1.2, 1.2, 2.0))
    pocket.apply_translation((17.0, 12.0, PLATE[2] / 2.0))
    mesh = boolean(
        "difference",
        [as_mesh_data(entry.mesh), MeshData.of(pocket)],
        quality="fine",
        cancelled=NeverCancelled(),
    ).mesh
    found = detect(mesh)
    assert kinds(found) == {"face": 6 + 5, "pattern": 1}, kinds(found)
    pattern = only_pattern(found)
    swallowed = set(pattern.face_indices)
    walls = [
        feature
        for feature in found.values()
        if feature.kind == "face" and abs(float(feature.params["centre"][0]) - 17.0) < 1.0
    ]
    assert len(walls) == 5, "Boden und vier Wände der Tasche stehen im Baum"
    assert all(not swallowed & set(feature.face_indices) for feature in walls)


# --- Entfernen --------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["engraved", "raised"])
@pytest.mark.parametrize("pattern", PATTERNS)
def test_removing_a_pattern_gives_the_plain_plate_back(pattern: str, mode: str) -> None:
    """Vertieft gefüllt, erhaben abgetragen — das Volumen ist wieder das der Platte."""
    pitch = 2.0 if pattern == "noise" else 4.0
    entry = textured(pattern, mode, pitch=pitch, depth=0.6 if pattern == "noise" else 1.0)
    read = only_pattern(entry.features)
    out, findings = run_op("remove_feature", entry, at_feature=read.id)
    assert math.isclose(out.mesh.volume, PLATE_VOLUME, abs_tol=0.05), out.mesh.volume
    assert kinds(out.features) == {"face": 6}, kinds(out.features)
    assert read.id not in out.features
    gone = [finding for finding in findings if finding.code == "remove_feature.gone"]
    assert gone and gone[0].values["cells"] == read.params["count"] + read.params["partial"]


def test_removing_the_honeycomb_fills_every_cell_flush_on_both_sides() -> None:
    """Durchgehende Zellen sind auf beiden Seiten bündig — keine Haut auf der Rückseite."""
    mesh, count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, _findings = run_op("remove_feature", entry, at_feature=read.id)
    cell_area = 3.0 * math.sqrt(3.0) / 2.0 * (HOLDER_WIDTH / math.sqrt(3.0)) ** 2
    expected = mesh.volume + count * cell_area * HOLDER_THICKNESS
    assert math.isclose(out.mesh.volume, expected, rel_tol=1e-6), (out.mesh.volume, expected)
    assert kinds(out.features) == {"face": 6}, kinds(out.features)


# --- Ändern -----------------------------------------------------------------------


def test_resizing_redraws_with_the_new_pitch_and_the_old_cell_width() -> None:
    """Teilung 4 → 5: mehr Abstand, dieselben Waben, dieselbe Tiefe."""
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    out, findings = run_op("resize_feature", entry, at_feature=read.id, pitch=5.0)
    after = only_pattern(out.features)
    assert after.params["style"] == "hexagon"
    assert math.isclose(after.params["pitch"], 5.0, abs_tol=0.01)
    assert math.isclose(after.params["cell_width"], read.params["cell_width"], abs_tol=0.01)
    assert math.isclose(after.params["cell_depth"], read.params["cell_depth"], abs_tol=1e-3)
    assert after.params["count"] < read.params["count"], "weiter auseinander heißt weniger"
    assert any(finding.code == "resize_feature.pattern" for finding in findings)


def test_the_operation_carries_the_set_numbers_as_parameters() -> None:
    """Was die Operation weiterreicht, trägt die gesetzten Zahlen — als Vorgabe, nicht gemessen.

    Vor der Neuerkennung: ``run_op`` ersetzt die Merkmale durch eine frische
    Erkennung, und die sagt nichts darüber, was die Operation ausgegeben hat.
    """
    load_operations()
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    spec = REGISTRY.get("resize_feature")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(at_feature=read.id, pitch=5.0),
            profile=PROFILE,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    carried = result.outputs[0].features[read.id]
    assert carried.kind == "pattern"
    assert math.isclose(carried.params["pitch"], 5.0)
    assert carried.measure_sources["pitch"] == "parameter"
    assert carried.measure_sources["cell_depth"] == "parameter"
    assert carried.face_indices == (), "Dreiecksnummern gehören dem alten Netz"


def test_resizing_the_depth_alone_keeps_pitch_and_width() -> None:
    entry = textured("knurl_diamond", "raised")
    read = only_pattern(entry.features)
    out, _findings = run_op("resize_feature", entry, at_feature=read.id, cell_depth=0.5)
    after = only_pattern(out.features)
    assert math.isclose(after.params["cell_depth"], 0.5, abs_tol=1e-3)
    assert math.isclose(after.params["pitch"], read.params["pitch"], abs_tol=0.01)
    assert math.isclose(after.params["cell_width"], read.params["cell_width"], abs_tol=0.01)
    assert after.params["mode"] == "raised"


def test_redrawing_keeps_every_rib_where_it_was() -> None:
    """Nur die Tiefe ändern heißt: dieselben Rippen an derselben Stelle.

    Ohne Anker begann das Raster am Feldrand neu, die Streifen rückten um
    einen Bruchteil der Teilung, und aus sechs Rippen wurden fünf und zwei
    Stummel — kein Muster mehr (Review, 22.09.2026).
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern="rib",
        pitch=4.0,
        depth=1.0,
        mode="engraved",
        width=26.0,
        height=14.0,
        z=PLATE[2] / 2.0,
        nz=1.0,
    )
    read = only_pattern(out.features)
    before = read.params["count"] + read.params["partial"]
    redrawn, _findings = run_op("resize_feature", out, at_feature=read.id, cell_depth=0.5)
    after = only_pattern(redrawn.features)
    assert after.params["count"] + after.params["partial"] == before
    assert after.params["count"] == read.params["count"]
    assert np.allclose(after.params["anchor"], read.params["anchor"], atol=0.05)
    assert np.allclose(after.params["centre"], read.params["centre"], atol=0.1)


def test_change_stands_grey_at_a_pattern_solidon_does_not_draw() -> None:
    """Der Satz steht im Panel, bevor jemand übernimmt — nicht erst danach."""
    mesh = oblong_pockets()
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    actions = actions_for(read, entry.features, mesh=as_mesh_data(entry.mesh))
    change = next(action for action in actions if str(action.title) == "Merkmal ändern")
    assert change.op is None and "zeichnet" in str(change.reason)
    remove = next(action for action in actions if action.op == "remove_feature")
    assert remove.op == "remove_feature"


def test_a_cell_width_the_pitch_cannot_hold_is_limited_and_said() -> None:
    """9 mm Waben bei 6 mm Teilung gibt es nicht; die Grenze wird genannt, nicht verschwiegen."""
    mesh, _count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, findings = run_op("resize_feature", entry, at_feature=read.id, pitch=6.0)
    limited = [f for f in findings if f.code == "resize_feature.cell_width_limited"]
    assert limited, [finding.code for finding in findings]
    after = only_pattern(out.features)
    assert after.params["cell_width"] < HOLDER_WIDTH
    assert math.isclose(after.params["cell_width"], limited[0].values["cell_width"], abs_tol=0.02)


def test_the_holders_own_cells_are_not_limited() -> None:
    """9 mm Waben bei 10,4 mm Teilung haben 1,4 mm Wand — und bleiben 9 mm.

    Die Grenze lag als Anteil an der Teilung, und für die Wabe misst der
    Anteil über die Flächen nur √3/2 davon: 9 von 10,4 hieß 0,999, wurde auf
    0,98 begrenzt, und der Halter bekam 8,83 mm Waben samt dem Satz, es
    bliebe sonst keine Wand (Review, 22.09.2026).
    """
    mesh, _count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, findings = run_op("resize_feature", entry, at_feature=read.id, cell_depth=10.0)
    assert not [f for f in findings if f.code == "resize_feature.cell_width_limited"]
    after = only_pattern(out.features)
    assert math.isclose(after.params["cell_width"], HOLDER_WIDTH, abs_tol=0.02)
    # Eine gesetzte Tiefe an einem durchgehenden Muster macht es blind — und
    # zwar genau so tief, nicht um den Überlapp der Rechnung tiefer.
    assert math.isclose(after.params["cell_depth"], 10.0, abs_tol=1e-3)
    assert after.params["through"] is False


def test_the_wall_between_limited_cells_is_the_nozzle() -> None:
    """Begrenzt heißt: so breit, dass die Wand dazwischen noch druckt — eine Düse."""
    mesh, _count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, _findings = run_op("resize_feature", entry, at_feature=read.id, pitch=6.0)
    after = only_pattern(out.features)
    wall = 6.0 - after.params["cell_width"]
    assert math.isclose(wall, NOZZLE.nozzle_diameter, abs_tol=0.02), wall


def test_a_tighter_diamond_knurl_keeps_a_wall_between_its_cells() -> None:
    """Rauten berühren sich bei 1/√2 der Teilung — enger gestellt bleiben sie Rauten.

    Vorher galt für alle Muster dieselbe Grenze von 0,98: Bei 2 mm Rauten auf
    2,5 mm Teilung verschmolzen 253 Rauten zu einem Umriss, und das ohne ein
    Wort (Review, 22.09.2026).
    """
    entry = textured("knurl_diamond", "raised")
    read = only_pattern(entry.features)
    out, findings = run_op("resize_feature", entry, at_feature=read.id, pitch=2.5)
    assert any(f.code == "resize_feature.cell_width_limited" for f in findings)
    after = only_pattern(out.features)
    assert after.params["style"] == "knurl_diamond"
    assert after.params["count"] > read.params["count"]
    assert after.params["cell_width"] < 2.5 / math.sqrt(2.0)


def test_a_cell_narrower_than_the_nozzle_is_refused_with_a_way_out() -> None:
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    with pytest.raises(ValidationError) as refused:
        run_op("resize_feature", entry, at_feature=read.id, cell_width=0.3)
    assert refused.value.field == "cell_width"
    assert refused.value.suggestions


def test_an_unreadable_pattern_offers_the_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Satz nennt das Reparieren — dann steht es auch als Handlung da (Regel 17)."""
    from app.core.errors import REPAIR_AND_RETRY
    from app.core.perceive import patterns as module

    monkeypatch.setattr(module, "plug_for", lambda mesh, feature: None)
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    with pytest.raises(ValidationError) as refused:
        run_op("remove_feature", entry, at_feature=read.id)
    assert REPAIR_AND_RETRY in refused.value.suggestions


def test_resizing_the_honeycomb_keeps_only_whole_cells() -> None:
    """Eine durchgehende Zelle, die der Rand anschneidet, wäre eine Kerbe — es gibt keine."""
    mesh, _count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, _findings = run_op("resize_feature", entry, at_feature=read.id, pitch=12.0)
    after = only_pattern(out.features)
    assert after.params["partial"] == 0
    assert after.params["through"] is True
    assert math.isclose(after.params["pitch"], 12.0, abs_tol=0.01)
    assert kinds(out.features) == {"face": 6, "pattern": 1}, kinds(out.features)


def test_an_unchanged_measure_says_so() -> None:
    entry = textured("rib", "engraved")
    read = only_pattern(entry.features)
    out, findings = run_op("resize_feature", entry, at_feature=read.id)
    assert out.mesh is entry.mesh
    assert [finding.code for finding in findings] == ["resize_feature.unchanged"]


def oblong_pockets() -> MeshData:
    """Neun Taschen 5 auf 8 im Raster — ein Gitter, das Solidon so nicht zeichnet.

    Quadrate wären ein Kreuzrändel, von der Diagonalen aus gesehen; ein
    Rechteck unter der Streifenlänge ist keines der acht Muster.
    """
    body = trimesh.creation.box(extents=(60.0, 40.0, 6.0))
    tools = []
    for i in range(3):
        for j in range(3):
            pocket = trimesh.creation.box(extents=(5.0, 8.0, 3.0))
            pocket.apply_translation(((i - 1.0) * 10.0, (j - 1.0) * 10.0, 3.0))
            tools.append(pocket)
    return boolean(
        "difference",
        [MeshData.of(body), MeshData.of(trimesh.util.concatenate(tools))],
        quality="fine",
        cancelled=NeverCancelled(),
    ).mesh


def test_a_grid_of_oblongs_is_a_pattern_of_its_own_kind_removable_but_not_redrawable() -> None:
    mesh = oblong_pockets()
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    assert read.params["style"] == "other"
    assert read.params["count"] == 9
    with pytest.raises(ValidationError) as refused:
        run_op("resize_feature", entry, at_feature=read.id, pitch=8.0)
    assert refused.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“"
    out, _findings = run_op("remove_feature", entry, at_feature=read.id)
    assert math.isclose(out.mesh.volume, 60.0 * 40.0 * 6.0, abs_tol=0.05)


# --- Was der Kunde und der Agent lesen --------------------------------------------


def test_the_panel_offers_change_and_remove_with_the_patterns_own_fields() -> None:
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    actions = actions_for(read, entry.features, mesh=as_mesh_data(entry.mesh))
    offered = {action.title: action for action in actions}
    change = next(action for action in offered.values() if action.op == "resize_feature")
    assert [field.name for field in change.fields] == ["pitch", "cell_width", "cell_depth"], [
        field.name for field in change.fields
    ]
    assert math.isclose(float(change.fields[0].value), 4.0, abs_tol=0.01)
    remove = next(action for action in offered.values() if action.op == "remove_feature")
    assert remove.fields == ()
    declined = [action for action in offered.values() if action.op is None]
    assert declined, "Versetzen, Drehen und Verdoppeln stehen grau — mit Satz"
    assert all("Fläche" in str(action.reason) for action in declined)


def test_the_digest_and_the_tree_name_the_style_and_the_numbers() -> None:
    from app.i18n import set_language
    from app.ui.labels import feature_label

    set_language("de")
    mesh, count = honeycomb_plate()
    read = only_pattern(detect(mesh))
    line = _feature_line(read.id, read)
    assert "Wabenmuster" in line
    assert f"{count} Zellen" in line
    assert "10.40 mm" in line and "9.00 mm" in line and "durchgehend" in line
    label = feature_label(read.id, read)
    assert label.startswith("Wabenmuster 1")
    assert f"{count} Zellen" in label


def test_a_moved_body_keeps_its_pattern_under_the_same_name() -> None:
    """Die Zuordnung liest Mitte, Normale und Richtung — sie reisen mit (§21.2)."""
    from app.core.perceive.matching import moved_features

    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    shift = np.eye(4)
    shift[:3, 3] = (12.0, -7.0, 3.0)
    moved = moved_features(entry.features, shift)
    after = moved[read.id]
    assert np.allclose(after.params["centre"], np.asarray(read.params["centre"]) + shift[:3, 3])
    assert np.allclose(after.params["normal"], read.params["normal"])
    assert np.allclose(after.params["direction"], read.params["direction"])


def test_overlapping_noise_blobs_leave_one_clean_top_face() -> None:
    """Ohne Vereinigung der Streuflecken hatte die Deckfläche doppelte Dreiecke."""
    entry = textured("noise", "engraved", pitch=2.0, depth=0.6)
    faces = [feature for feature in entry.features.values() if feature.kind == "face"]
    top = [face for face in faces if face.params["normal"][2] > 0.99]
    assert len(top) == 1, [face.params["area"] for face in top]
    assert top[0].params["area"] < PLATE[0] * PLATE[1]
