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
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.texture_ops import PATTERNS, wrap_pitch
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
    Quality,
    Scene,
    SceneObject,
)
from app.core.units import EPS_GEOM

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


def run_op(
    op: str, entry: SceneObject, *, quality: Quality = "fine", **params: object
) -> tuple[SceneObject, list[Finding]]:
    """Eine Operation fahren und danach neu erkennen, wie die Auswertung es tut."""
    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=PROFILE,
            quality=quality,
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


def _lid_end_face_centres(features: Mapping[FeatureId, Feature]) -> list[float]:
    """Die Höhen der beiden zusammenhängenden, ebenen Deckelflächen."""
    centres = []
    for feature in features.values():
        if feature.kind != "face":
            continue
        normal = np.asarray(feature.params["normal"], dtype=float)
        if (
            abs(abs(float(normal[2])) - 1.0) <= EPS_GEOM
            and float(np.linalg.norm(normal[:2])) <= EPS_GEOM
        ):
            centres.append(float(feature.params["centre"][2]))
    return sorted(centres)


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
        "dimple": 4.0 * 0.8,
    }
    for pattern, width in expected.items():
        read = only_pattern(textured(pattern, "engraved").features)
        assert math.isclose(read.params["cell_width"], width, rel_tol=0.01), (pattern, read.params)


def test_a_turned_dimple_field_is_one_pattern_and_not_bores_and_slots() -> None:
    """Die Noppen der Vorgabe berührten sich; gedreht zerfiel die Deckfläche in Inseln.

    Gemessen im Review (22.09.2026): ``dimple`` mit ``angle=90`` auf 30 mal
    20 ergab 35 Bohrungen, 5 Langlöcher und 16 Rundungen. Seit die Noppe eine
    Wand hat (``DIMPLE_FILL``), ist es ein Muster — unter jedem Winkel.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern="dimple",
        pitch=4.0,
        depth=1.0,
        mode="engraved",
        width=30.0,
        height=20.0,
        angle=90.0,
        z=PLATE[2] / 2.0,
        nz=1.0,
    )
    read = only_pattern(out.features)
    assert read.params["style"] == "dimple"
    assert kinds(out.features) == {"face": 6, "pattern": 1}, kinds(out.features)


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


def test_change_at_a_foreign_pattern_offers_a_style_with_the_measured_pitch() -> None:
    """Ein fremdes Muster lässt sich ändern: mit einem eigenen Stil und der gemessenen Teilung.

    Bis zum 22.09.2026 stand *Merkmal ändern* an einem Muster, das Solidon
    nicht selbst zeichnet, grau — ein fremdes Gitter war nur entfernbar. Die
    Presse verspricht das Gegenteil („beliebiges Modell mit Rändel
    herunterladen, Teilung ändern"). Jetzt bietet die Zeile den Stil an,
    vorbelegt mit „fremdes Muster", und die Teilung mit dem gemessenen Wert.
    """
    mesh = oblong_pockets()
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    actions = actions_for(read, entry.features, mesh=as_mesh_data(entry.mesh))
    change = next(action for action in actions if str(action.title) == "Merkmal ändern")
    assert change.op == "resize_feature", change.reason
    fields = {field.name: field for field in change.fields}
    assert fields["style"].value == "other"
    assert math.isclose(float(fields["pitch"].value), float(read.params["pitch"]), abs_tol=1e-6)
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
    """Begrenzt heißt: so breit, dass die Wand dazwischen noch druckt — eine Bahn breit."""
    mesh, _count = honeycomb_plate()
    entry = SceneObject(id="obj_1", name="Halter", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    out, _findings = run_op("resize_feature", entry, at_feature=read.id, pitch=6.0)
    after = only_pattern(out.features)
    wall = 6.0 - after.params["cell_width"]
    assert math.isclose(wall, NOZZLE.smallest_detail, abs_tol=0.02), wall


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

    monkeypatch.setattr(module, "plug_for", lambda mesh, feature, features=None: None)
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


def test_a_grid_of_oblongs_is_a_pattern_of_its_own_kind_removable_and_restyled() -> None:
    """Ein fremdes Gitter wird entfernt — oder mit einem eigenen Stil ersetzt, in einem Schritt.

    Ohne gewählten Stil sagt die Operation, was fehlt (Regel 21: kein Stil
    wird geraten). Mit Stil schließt sie die fremden Zellen und zeichnet das
    Muster auf derselben Fläche neu — dieselbe Operation, also ein Schritt und
    ein Undo.
    """
    mesh = oblong_pockets()
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    assert read.params["style"] == "other"
    assert read.params["count"] == 9
    with pytest.raises(ValidationError) as refused:
        run_op("resize_feature", entry, at_feature=read.id, pitch=8.0)
    assert refused.value.field == "style"
    assert refused.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“"
    out, _findings = run_op("remove_feature", entry, at_feature=read.id)
    assert math.isclose(out.mesh.volume, 60.0 * 40.0 * 6.0, abs_tol=0.05)

    # Auf dem Feld der neun Taschen (25 auf 28 mm) haben Waben mit 5 mm
    # Teilung Platz genug, um wieder ein Muster zu sein.
    restyled, findings = run_op(
        "resize_feature", entry, at_feature=read.id, style="hexagon", pitch=5.0
    )
    assert as_mesh_data(restyled.mesh).is_watertight
    after = only_pattern(restyled.features)
    assert after.params["style"] == "hexagon", after.params
    assert after.params["count"] >= 9
    assert math.isclose(float(after.params["pitch"]), 5.0, abs_tol=0.05)
    assert after.params["mode"] == "engraved"
    assert "resize_feature.pattern" in [finding.code for finding in findings]
    # Die fremden Taschen sind zu: Unter den neuen Waben steht kein Rechteck mehr.
    assert not [
        f
        for f in restyled.features.values()
        if f.kind == "pattern" and f.params.get("style") == "other"
    ]


# --- Was der Kunde und der Agent lesen --------------------------------------------


def test_the_panel_offers_change_and_remove_with_the_patterns_own_fields() -> None:
    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    actions = actions_for(read, entry.features, mesh=as_mesh_data(entry.mesh))
    offered = {action.title: action for action in actions}
    change = next(action for action in offered.values() if action.op == "resize_feature")
    assert [field.name for field in change.fields] == [
        "pitch",
        "cell_width",
        "cell_depth",
        "style",
    ], [field.name for field in change.fields]
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


def _field_axis(feature: Feature) -> np.ndarray:
    """Die erste Achse des Feldes in der Welt — aus Normale und Feldwinkel."""
    from app.core import units

    axes = units.plane_axes(feature.params["normal"])
    assert axes is not None
    first, second = (np.asarray(axis, dtype=float) for axis in axes)
    angle = math.radians(float(feature.params["angle"]))
    return math.cos(angle) * first + math.sin(angle) * second


@pytest.mark.parametrize(("degrees", "axis"), [(30.0, (0.0, 0.0, 1.0)), (90.0, (1.0, 0.0, 0.0))])
def test_a_turned_body_carries_the_field_of_its_pattern_along(
    degrees: float, axis: tuple[float, float, float]
) -> None:
    """Der Feldwinkel dreht mit, wenn die Erkennung mitgeführt statt neu gerechnet wird.

    ``angle`` steht gegen die erste Achse der Trägerebene, und die hängt allein
    an der Normalen (``units.plane_axes``). Eine Drehung um die Normale lässt
    die Normale, wie sie war — und ließ bis zum 22.09.2026 auch den Winkel
    stehen: Am Halter mit Wabenmuster trug die mitgeführte Erkennung nach 30
    Grad weiter 90, die frische 120. *Merkmal ändern* zeichnete das Muster dann
    im alten Winkel neu, um 30 Grad verdreht gegen seine Zellen.
    """
    from app.core.perceive.matching import transformed_features

    entry = textured("hexagon", "engraved")
    read = only_pattern(entry.features)
    turn = trimesh.transformations.rotation_matrix(math.radians(degrees), axis)
    body = entry.mesh.raw.copy()
    body.apply_transform(turn)
    moved = MeshData.of(body)

    carried = transformed_features(entry.features, turn, mesh=moved).candidates[read.id]
    fresh = only_pattern(detect(moved))

    assert np.allclose(carried.params["normal"], fresh.params["normal"], atol=1e-9)
    along = abs(float(_field_axis(carried) @ _field_axis(fresh)))
    assert along == pytest.approx(1.0, abs=1e-9), (
        f"das Feld liegt um {math.degrees(math.acos(min(along, 1.0))):.1f} Grad verdreht"
    )
    assert 0.0 <= float(carried.params["angle"]) < 180.0


def test_overlapping_noise_blobs_leave_one_clean_top_face() -> None:
    """Ohne Vereinigung der Streuflecken hatte die Deckfläche doppelte Dreiecke."""
    entry = textured("noise", "engraved", pitch=2.0, depth=0.6)
    faces = [feature for feature in entry.features.values() if feature.kind == "face"]
    top = [face for face in faces if face.params["normal"][2] > 0.99]
    assert len(top) == 1, [face.params["area"] for face in top]
    assert top[0].params["area"] < PLATE[0] * PLATE[1]


# --- Um einen Zylinder ---------------------------------------------------------------

#: Der Griff: Ø 30, 30 lang, in 96 Facetten — die Sehnenabweichung liegt unter
#: der Erkennungsauflösung, wie bei jedem Zylinder, den der Kern selbst baut.
CYLINDER_DIAMETER = 30.0
CYLINDER_LENGTH = 30.0
CIRCUMFERENCE = math.pi * CYLINDER_DIAMETER

#: Vier Muster um den Griff: Kreuzrändel und Noppen erhaben, Rippen und Waben
#: vertieft — drei einmal ganz herum, die Noppen als Feld von 40 mm Breite.
AROUND = [
    ("knurl_diamond", "raised", CIRCUMFERENCE),
    ("rib", "engraved", CIRCUMFERENCE),
    ("hexagon", "engraved", CIRCUMFERENCE),
    ("dimple", "raised", 40.0),
]


def cylinder() -> MeshData:
    return MeshData.of(
        trimesh.creation.cylinder(
            radius=CYLINDER_DIAMETER / 2.0, height=CYLINDER_LENGTH, sections=96
        )
    )


def wrapped(
    pattern: str, mode: str, width: float, *, pitch: float = 3.0, depth: float = 0.8
) -> tuple[SceneObject, list[Finding]]:
    """Ein Muster um den Griff, wie ``apply_texture`` es mit ``wrap="cylinder"`` legt."""
    entry = SceneObject(id="obj_1", name="Griff", mesh=cylinder())
    return run_op(
        "apply_texture",
        entry,
        pattern=pattern,
        pitch=pitch,
        depth=depth,
        mode=mode,
        width=width,
        height=20.0,
        wrap="cylinder",
        wrap_diameter=CYLINDER_DIAMETER,
        z=0.0,
    )


@pytest.mark.parametrize("pattern,mode,width", AROUND)
def test_a_texture_around_a_cylinder_is_one_pattern_on_the_pin(
    pattern: str, mode: str, width: float
) -> None:
    """Der Träger ist ein Stift, das Gitter liegt in seiner Abwicklung, die Zahlen stimmen."""
    out, _findings = wrapped(pattern, mode, width)
    read = only_pattern(out.features)
    params = read.params
    assert params["style"] == pattern
    assert params["mode"] == mode
    assert params["carrier"] == "cylinder"
    assert math.isclose(params["carrier_diameter"], CYLINDER_DIAMETER, abs_tol=0.05)
    assert np.allclose(np.abs(params["carrier_axis"]), (0.0, 0.0, 1.0), atol=1e-3)
    assert math.isclose(
        params["pitch"], wrap_pitch(pattern, 3.0, CYLINDER_DIAMETER, width), abs_tol=0.02
    )
    assert math.isclose(params["cell_depth"], 0.8, abs_tol=0.02)
    assert math.isclose(params["height"], 20.0, abs_tol=0.5)
    # Die Mitte liegt auf dem Zylinder, die Normale zeigt dort radial nach außen.
    centre = np.asarray(params["centre"], dtype=float)
    assert math.isclose(math.hypot(centre[0], centre[1]), CYLINDER_DIAMETER / 2.0, abs_tol=0.02)
    radial = np.array([centre[0], centre[1], 0.0]) / math.hypot(centre[0], centre[1])
    assert np.allclose(params["normal"], radial, atol=1e-3)
    # Die Zellen gehen im Muster auf; der Stift und die zwei Stirnflächen bleiben.
    assert kinds(out.features) == {"pin": 1, "face": 2, "pattern": 1}, kinds(out.features)
    carrier = patterns.carrier_of(read, out.features)
    assert carrier is not None and carrier.kind == "pin"


def test_a_full_turn_closes_at_the_seam_with_a_pitch_that_fits_and_says_so() -> None:
    """31 Rillen um Ø 30: die Teilung rückt von 3 auf 3,04, und keine Zelle ist angeschnitten."""
    out, findings = wrapped("rib", "engraved", CIRCUMFERENCE)
    said = [finding for finding in findings if finding.code == "texture.pitch_wrapped"]
    assert said, [finding.code for finding in findings]
    assert math.isclose(said[0].values["pitch_mm"], CIRCUMFERENCE / 31, abs_tol=1e-3)
    read = only_pattern(out.features)
    assert read.params["count"] == 31
    assert read.params["partial"] == 0
    assert math.isclose(read.params["pitch"], CIRCUMFERENCE / 31, abs_tol=0.01)


def test_a_field_that_does_not_reach_around_keeps_its_pitch() -> None:
    out, findings = wrapped("dimple", "raised", 40.0)
    assert not any(finding.code == "texture.pitch_wrapped" for finding in findings)
    read = only_pattern(out.features)
    assert math.isclose(read.params["pitch"], 3.0, abs_tol=0.01)
    assert math.isclose(read.params["width"], 40.0, abs_tol=0.5)


@pytest.mark.parametrize("pattern,mode,width", AROUND)
def test_removing_a_wrapped_pattern_gives_the_plain_cylinder_back(
    pattern: str, mode: str, width: float
) -> None:
    """Die Stopfen liegen auf den Facetten des Mantels — danach ist er wieder ein Zylinder."""
    out, _findings = wrapped(pattern, mode, width)
    read = only_pattern(out.features)
    plain, findings = run_op("remove_feature", out, at_feature=read.id)
    # Das Vieleck, nicht der Kreis: 96 Facetten haben ein Volumen, und das kommt zurück.
    assert math.isclose(plain.mesh.volume, cylinder().volume, abs_tol=0.05), plain.mesh.volume
    assert kinds(plain.features) == {"pin": 1, "face": 2}, kinds(plain.features)
    assert read.id not in plain.features
    gone = [finding for finding in findings if finding.code == "remove_feature.gone"]
    assert gone and gone[0].values["cells"] == read.params["count"] + read.params["partial"]


@pytest.mark.parametrize(
    "pattern,mode,width,new_pitch",
    [
        ("rib", "engraved", CIRCUMFERENCE, 4.0),
        ("hexagon", "engraved", CIRCUMFERENCE, 4.0),
        ("dimple", "raised", 40.0, 4.0),
    ],
)
def test_resizing_a_wrapped_pattern_redraws_around_the_cylinder(
    pattern: str, mode: str, width: float, new_pitch: float
) -> None:
    """Neu gezeichnet um dieselbe Achse: derselbe Stil, die neue Teilung, der Stift bleibt."""
    out, _findings = wrapped(pattern, mode, width)
    read = only_pattern(out.features)
    redrawn, findings = run_op("resize_feature", out, at_feature=read.id, pitch=new_pitch)
    after = only_pattern(redrawn.features)
    assert after.params["style"] == pattern
    assert after.params["carrier"] == "cylinder"
    expected = wrap_pitch(pattern, new_pitch, CYLINDER_DIAMETER, width)
    assert math.isclose(after.params["pitch"], expected, abs_tol=0.02), after.params["pitch"]
    assert math.isclose(after.params["cell_width"], read.params["cell_width"], abs_tol=0.02)
    assert math.isclose(after.params["cell_depth"], read.params["cell_depth"], abs_tol=0.02)
    assert after.params["count"] < read.params["count"], "weiter auseinander heißt weniger"
    assert kinds(redrawn.features)["pin"] == 1, kinds(redrawn.features)
    assert any(finding.code == "resize_feature.pattern" for finding in findings)


@pytest.mark.parametrize(
    "pattern,mode",
    [("rib", "engraved"), ("knurl_diamond", "raised"), ("knurl_diamond", "engraved")],
)
@pytest.mark.parametrize("new_pitch", [4.0, 5.9])
def test_a_changed_pattern_around_a_handle_is_read_as_that_pattern_again(
    pattern: str, mode: str, new_pitch: float
) -> None:
    """Was Solidon um den Griff neu zeichnet, liest die Erkennung wieder als dieses Muster.

    Sonst lässt es sich kein zweites Mal ändern. Ein Kreuzrändel auf 4 oder
    5,9 mm geändert stand danach als Stift und zwei Flächen im Baum: Seine
    Dreiecke tragen keinen Namen, der Stift hatte sie beim Einpassen
    mitgenommen, und die Suche endete an der Zahl der kleinen Merkmale, bevor
    sie sie ihm wieder abnahm (Fund aus „formops", 23.09.2026).
    """
    out, _findings = wrapped(pattern, mode, CIRCUMFERENCE)
    read = only_pattern(out.features)
    redrawn, _findings = run_op("resize_feature", out, at_feature=read.id, pitch=new_pitch)
    after = only_pattern(redrawn.features)
    assert after.params["style"] == pattern
    assert after.params["mode"] == mode
    assert after.params["carrier"] == "cylinder"
    assert math.isclose(after.params["carrier_diameter"], CYLINDER_DIAMETER, abs_tol=0.05)
    expected = wrap_pitch(pattern, new_pitch, CYLINDER_DIAMETER, CIRCUMFERENCE)
    assert math.isclose(after.params["pitch"], expected, abs_tol=0.02), after.params["pitch"]
    assert kinds(redrawn.features)["pin"] == 1, kinds(redrawn.features)


@pytest.mark.parametrize(
    "pattern,mode",
    [
        ("rib", "engraved"),
        ("rib", "raised"),
        ("knurl_diamond", "raised"),
        ("knurl_diamond", "engraved"),
    ],
)
def test_a_coarse_pattern_around_a_handle_is_one_pattern_on_the_handle(
    pattern: str, mode: str
) -> None:
    """Teilung 5,9 um Ø 30: Der Boden der Rillen ist Zelle, nicht ein zweiter Stift.

    Vertiefte Rillen mit dieser Teilung haben einen Boden, der breit genug für
    eine Zylindereinpassung ist — sechzehn Streifen Ø 28,4, zu einem Stift so
    groß wie der Mantel zusammengelegt. Jede Rille berührte danach zwei Träger,
    und die Suche fand null Zellen (Fund aus „formops", 23.09.2026).
    """
    out, _findings = wrapped(pattern, mode, CIRCUMFERENCE, pitch=5.9)
    read = only_pattern(out.features)
    assert read.params["style"] == pattern
    assert read.params["mode"] == mode
    assert math.isclose(read.params["carrier_diameter"], CYLINDER_DIAMETER, abs_tol=0.05)
    expected = wrap_pitch(pattern, 5.9, CYLINDER_DIAMETER, CIRCUMFERENCE)
    assert math.isclose(read.params["pitch"], expected, abs_tol=0.02), read.params["pitch"]
    assert math.isclose(read.params["cell_depth"], 0.8, abs_tol=0.02)
    assert kinds(out.features) == {"pin": 1, "face": 2, "pattern": 1}, kinds(out.features)


def grooved_to_end_face(pattern: str, *, z: float = 8.0, pitch: float = 3.0) -> SceneObject:
    """Ein Griff mit einem vertieften Muster, dessen Feld über eine Stirnfläche hinausreicht."""
    entry = SceneObject(id="obj_1", name="Griff", mesh=cylinder())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern=pattern,
        pitch=pitch,
        depth=0.8,
        mode="engraved",
        width=CIRCUMFERENCE,
        height=20.0,
        wrap="cylinder",
        wrap_diameter=CYLINDER_DIAMETER,
        z=z,
    )
    return out


@pytest.mark.parametrize("pattern", ["rib", "knurl_diamond"])
def test_grooves_running_out_of_the_end_face_are_one_pattern_around_the_handle(
    pattern: str,
) -> None:
    """Rillen, die oben aus dem Griff laufen, sind ein Muster — obwohl jede Zelle ein Randstück ist.

    Am Deckel des Gewürzregals aus dem Korpus grenzen 24 Mulden um Ø 40 an den
    Mantel **und** an die Deckfläche. Die Suche fand sieben Zellen, 25
    Randstücke und kein Muster: Ein Randstück wird erst gemessen, wenn ein
    Muster aus ganzen Zellen es nachfragt, und ganze Zellen gab es keine
    (23.09.2026). Dasselbe hier mit einem Feld, das oben über den Griff
    hinausreicht. Entfernt kommt der Stift wieder: Die fehlenden Facetten unter
    den Rillen ergänzt das regelmäßige Vieleck des Trägers.
    """
    out = grooved_to_end_face(pattern)
    read = only_pattern(out.features)
    assert read.params["style"] == pattern
    assert read.params["mode"] == "engraved"
    assert read.params["carrier"] == "cylinder"
    expected = wrap_pitch(pattern, 3.0, CYLINDER_DIAMETER, CIRCUMFERENCE)
    assert math.isclose(read.params["pitch"], expected, abs_tol=0.02), read.params["pitch"]
    assert kinds(out.features)["pin"] == 1, kinds(out.features)
    plain, _findings = run_op("remove_feature", out, at_feature=read.id)
    # Die Stopfen schließen auch die Kerben in der Deckfläche — bündig mit ihr.
    # Bis zum 23.09.2026 ragten sie um ihren Saum darüber hinaus: Jede Kerbe
    # blieb als eigene Fläche stehen (31 am Griff), und es kamen 1,7 mm³ dazu,
    # mit dem in beiden Achsen gestreckten Taschenboden 12,7. Danach gilt
    # dasselbe Maß wie für ein Muster mitten auf dem Griff.
    assert kinds(plain.features) == {"pin": 1, "face": 2}, kinds(plain.features)
    assert math.isclose(plain.mesh.volume, cylinder().volume, abs_tol=0.05), plain.mesh.volume


def _reference(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mitte, Richtung und Anker des einen Musters — frisch erkannt."""
    params = only_pattern(detect(MeshData.of(mesh))).params
    return (
        np.asarray(params["centre"], dtype=float),
        np.asarray(params["direction"], dtype=float),
        np.asarray(params["anchor"], dtype=float),
    )


def _reordered(mesh: trimesh.Trimesh, seed: int) -> trimesh.Trimesh:
    """Dasselbe Netz mit anderer Ecken- und Dreiecksfolge, jede Ecke eines Dreiecks gedreht."""
    rng = np.random.default_rng(seed)
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    order = rng.permutation(len(vertices))
    inverse = np.empty_like(order)
    inverse[order] = np.arange(len(order))
    faces = inverse[faces][rng.permutation(len(faces))]
    faces = np.stack(
        [
            np.roll(row, int(shift))
            for row, shift in zip(faces, rng.integers(0, 3, len(faces)), strict=True)
        ]
    )
    return trimesh.Trimesh(vertices[order], faces, process=False)


#: Muster ganz um den Griff: aus ganzen Zellen und aus Randstücken wie am
#: Deckel des Gewürzregals, je mit ungerader Zellenzahl (31, die Mitte liegt
#: auf einer Zelle) und gerader (24 wie am Deckel, die Mitte liegt zwischen
#: zwei Zellen).
FULL_TURNS = {
    "ganze-zellen-31": ("whole", 3.0),
    "ganze-zellen-24": ("whole", 3.9),
    "randstuecke-31": ("rim", 3.0),
    "randstuecke-24": ("rim", 3.9),
}


def _full_turn(name: str) -> trimesh.Trimesh:
    cells, pitch = FULL_TURNS[name]
    if cells == "whole":
        out, _findings = wrapped("rib", "engraved", CIRCUMFERENCE, pitch=pitch)
    else:
        out = grooved_to_end_face("rib", pitch=pitch)
    return as_mesh_data(out.mesh).raw


def _cells_around(pitch: float) -> int:
    return round(CIRCUMFERENCE / wrap_pitch("rib", pitch, CYLINDER_DIAMETER, CIRCUMFERENCE))


def _turned(angle: float) -> float:
    """Ein Winkel auf (-π, π]."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


@pytest.mark.parametrize("name", list(FULL_TURNS))
def test_the_middle_of_a_full_turn_lies_opposite_the_gap_at_the_fixed_direction(
    name: str,
) -> None:
    """Welche der gleichen Zellen Mitte und Anker stellt, sagt eine feste Weltrichtung (RM-275).

    Um einen Träger herum sind alle Zellen gleich. Am Deckel des Gewürzregals
    entschied die Naht der Abwicklung — die größte von 24 gleich großen
    Lücken, oder die Mulde, die der ersten Ebenenachse gegenüberlag, je nach
    dem Vorzeichen einer Summe nahe null —, und nach einem Schritt weit weg
    vom Muster stand seine Mitte eine Zelle weiter, seine Richtung gespiegelt.
    Jetzt trägt die Naht die Lücke, deren Mitte ``SEAM_DIRECTION`` am nächsten
    liegt; die Mitte des Feldes liegt ihr gegenüber, und von zwei gleich nahen
    Zellen ist die weiter in dieser Richtung der Anker. Der Sollwert kommt aus
    der Lage der Zellen, nicht aus der Erkennung.
    """
    params = only_pattern(detect(MeshData.of(_full_turn(name)))).params
    count = _cells_around(FULL_TURNS[name][1])
    assert params["count"] + params["partial"] == count
    step = 2.0 * math.pi / count
    anchor = np.asarray(params["anchor"], dtype=float)
    first = math.atan2(anchor[1], anchor[0])
    towards = np.asarray(patterns.SEAM_DIRECTION, dtype=float)
    toward = math.atan2(towards[1], towards[0])
    gaps = [first + (index + 0.5) * step for index in range(count)]
    seam = min(gaps, key=lambda gap: abs(_turned(gap - toward)))
    middle = seam + math.pi
    centre = np.asarray(params["centre"], dtype=float)
    assert abs(_turned(math.atan2(centre[1], centre[0]) - middle)) < 1e-3, (
        math.degrees(math.atan2(centre[1], centre[0])),
        math.degrees(middle),
    )
    # Der Anker: die Zelle in der Mitte, oder von den zwei gleich nahen die
    # weiter in der festen Richtung.
    if count % 2:
        expected = middle
    else:
        expected = max(
            (middle - step / 2.0, middle + step / 2.0),
            key=lambda angle: math.cos(angle) * towards[0] + math.sin(angle) * towards[1],
        )
    assert abs(_turned(first - expected)) < 1e-3, (math.degrees(first), math.degrees(expected))


@pytest.mark.parametrize("name", list(FULL_TURNS))
def test_the_reference_of_a_full_turn_does_not_hang_on_the_order_of_the_mesh(name: str) -> None:
    """Dieselbe Geometrie in anderer Ecken- und Dreiecksfolge ergibt denselben Bezug (RM-275)."""
    mesh = _full_turn(name)
    centre, direction, anchor = _reference(mesh)
    for seed in (1, 2, 3):
        again = _reference(_reordered(mesh, seed))
        np.testing.assert_allclose(again[0], centre, atol=1e-6)
        np.testing.assert_allclose(again[1], direction, atol=1e-6)
        np.testing.assert_allclose(again[2], anchor, atol=1e-6)


def _around_z(sign: float) -> patterns.Frame:
    return patterns.Frame.cylinder(
        np.array([0.0, 0.0, sign]), np.zeros(3), 20.0, reference=np.array([1.0, 0.0, 0.0]), sag=0.0
    )


def _seam_in_the_world(frame: patterns.Frame, angles: np.ndarray) -> np.ndarray:
    """Wohin die Naht zeigt, in der Welt — der ersten Achse gegenüber."""
    reference = patterns._seam_reference(angles, patterns._seam_toward(frame))
    return -(frame.x_axis * math.cos(reference) + frame.y_axis * math.sin(reference))


def test_equal_gaps_choose_the_seam_by_the_fixed_direction_not_by_rounding() -> None:
    """Gleich große Lücken wählt nicht der Rundungsrest, eine größere bleibt die Naht (RM-275)."""
    step = 2.0 * math.pi / 24
    regular = np.arange(24) * step
    frame = _around_z(1.0)
    seams = [
        _seam_in_the_world(frame, regular + noise)
        for noise in (
            np.zeros(24),
            np.linspace(-1e-12, 1e-12, 24),
            np.linspace(1e-12, -1e-12, 24),
            np.random.default_rng(275).normal(0.0, 1e-10, 24),
        )
    ]
    for seam in seams[1:]:
        np.testing.assert_allclose(seam, seams[0], atol=1e-9)
    # Die Lücke, deren Mitte der festen Richtung am nächsten liegt: 52,5 Grad.
    np.testing.assert_allclose(
        seams[0], (math.cos(math.radians(52.5)), math.sin(math.radians(52.5)), 0.0), atol=1e-9
    )
    # Die andersherum eingepasste Achse zählt die Winkel andersherum und wählt
    # dieselbe Lücke am Mantel.
    np.testing.assert_allclose(_seam_in_the_world(_around_z(-1.0), -regular), seams[0], atol=1e-9)
    # Ein Feld, das nicht herumreicht: Die Naht liegt in seiner einen großen
    # Lücke, gleich wo die feste Richtung steht.
    partial = np.arange(12) * step
    widest = (11 * step + 2.0 * math.pi) / 2.0
    np.testing.assert_allclose(
        _seam_in_the_world(frame, partial), (math.cos(widest), math.sin(widest), 0.0), atol=1e-9
    )


def test_a_regular_polygon_gets_back_the_facets_a_pattern_cut_away() -> None:
    """Fehlen einem regelmäßigen Vieleck Facetten, kommen sie an ihren Platz — sonst nichts."""
    angles = np.radians(np.arange(96) * 3.75 - 180.0 + 1.875)
    kept = np.delete(np.arange(96), np.arange(0, 96, 4))
    completed, offsets = patterns._regular_polygon(angles[kept], np.full(len(kept), 19.99))
    assert len(completed) == 96
    np.testing.assert_allclose(np.sort(completed), np.sort(angles), atol=1e-9)
    assert np.allclose(offsets, 19.99)
    uneven = np.radians(np.array([-170.0, -100.0, -20.0, 45.0, 130.0]))
    same, _offsets = patterns._regular_polygon(uneven, np.full(5, 10.0))
    np.testing.assert_array_equal(same, uneven)


def test_a_regular_polygon_keeps_the_facets_it_has_measured() -> None:
    """Ergänzt werden nur die fehlenden Facetten; die gefundenen behalten Winkel und Abstand.

    Der Mantel wird vor dem Schließen auf seine gemessenen Facetten gelegt
    (``prepare_ops._aligned_facets``). Legte sich der Stopfen auf das ideale
    Vieleck, läge er um das Rauschen der STL daneben, und die Vereinigung
    schnitte Splitter in den Mantel (RM-404).
    """
    angles = np.radians(np.arange(96) * 3.75 - 180.0 + 1.875)
    kept = np.delete(np.arange(96), np.arange(0, 96, 4))
    measured = angles[kept] + 1e-7 * np.sin(np.arange(len(kept)))
    distances = 19.99 + 1e-6 * np.cos(np.arange(len(kept)))
    completed, offsets = patterns._regular_polygon(measured, distances)
    assert len(completed) == 96
    found = np.isin(completed, measured)
    assert int(found.sum()) == len(kept)
    np.testing.assert_array_equal(completed[found], measured)
    np.testing.assert_array_equal(offsets[found], distances)
    # Die fehlenden kommen auf das Raster, mit dem Median der Abstände.
    np.testing.assert_allclose(np.sort(completed[~found]), np.sort(angles[::4]), atol=1e-6)
    assert np.all(offsets[~found] == float(np.median(distances)))


def _folded_edges(body: trimesh.Trimesh) -> int:
    """Kanten, an denen zwei Dreiecke fast aufeinanderliegen — eine Finne."""
    normals = np.asarray(body.face_normals)
    pairs = np.asarray(body.face_adjacency)
    return int(((normals[pairs[:, 0]] * normals[pairs[:, 1]]).sum(axis=1) < -0.9).sum())


def _read_volume(body: trimesh.Trimesh) -> float:
    """Das Volumen, das ``manifold3d`` liest — wie die Vereinigung danach."""
    import manifold3d

    return float(
        manifold3d.Manifold(
            manifold3d.Mesh64(
                np.array(body.vertices, dtype=np.float64, order="C"),
                np.array(body.faces, dtype=np.uint64, order="C"),
            )
        ).volume()
    )


def test_aligning_pattern_facets_keeps_untouched_refinement_and_slots() -> None:
    """Eine Korrektur am Mantel darf den fernen verfeinerten Quader nicht entkernen."""
    from app.core.geom.mesh import refined_units
    from app.core.geom.prepare_ops import _aligned_facets
    from tests.helpers import rounded_pattern_carrier

    source = rounded_pattern_carrier()
    before = as_mesh_data(source.mesh)
    coordinates = before.raw.vertices.copy()
    changed, refused = _aligned_facets(source, source.features["pattern_1"])
    assert not refused
    assert changed is not source, "die Herkunftsprobe muss den Ausrichtungspfad erreichen"
    after = as_mesh_data(changed.mesh)
    untouched = np.all(before.raw.triangles[:, :, 0] > 40.0, axis=1)
    previous_origins = refined_units(before.raw)
    next_origins = refined_units(after.raw)
    assert previous_origins is not None and next_origins is not None
    assert untouched.any()
    assert np.array_equal(next_origins[untouched], previous_origins[untouched])
    assert np.array_equal(after.raw.triangles[untouched], before.raw.triangles[untouched])
    assert after.slots == before.slots
    assert np.array_equal(before.raw.vertices, coordinates), "der Eingang bleibt nur lesend"
    moved = np.any(after.raw.triangles != before.raw.triangles, axis=(1, 2))
    assert moved.any()
    assert np.all(next_origins[moved] < 0), "geänderte Dreiecke erben keine Verfeinerungsherkunft"


def test_three_noisy_pattern_facets_cannot_move_a_vertex_along_the_carrier_axis() -> None:
    """Drei nahezu achsparallele Ebenen dürfen Rundungsreste nicht in 5 mm Hub übersetzen.

    Der offene Prüffächer isoliert den gemeinsamen Eckpunkt dreier Facetten.
    Je eine Ecke liegt um 0,8 nm neben ihrer Ebene, also noch im Messrauschen;
    axial ist kein Punkt zu korrigieren. Eine dreidimensionale Lösung bewegte
    die gemeinsame Ecke trotzdem um 5 mm, weil sie einen Rang drei vermutete.
    """
    from app.core import units
    from app.core.geom.prepare_ops import _aligned_facets

    origin = np.array([20.0, 0.0, 0.0])
    vertices = [origin]
    faces = []
    for index in range(3):
        x, y = units.circle_point(3, index)
        normal = np.array([x, y, 0.0])
        tangent = np.array([-y, x, 0.0])
        base = len(vertices)
        vertices.extend(
            [
                origin + tangent * 10.0 + normal * 0.8e-6,
                origin + tangent * 10.0 + np.array([0.0, 0.0, 10.0]),
                origin + np.array([0.0, 0.0, 10.0]),
            ]
        )
        faces.extend([(0, base, base + 1), (0, base + 1, base + 2)])
    carrier = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        face_indices=tuple(range(6)),
        params={"axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 5.0), "diameter": 40.0},
    )
    pattern = Feature(
        id="pattern_1",
        kind="pattern",
        provenance="detected",
        params={
            "carrier": "cylinder",
            "carrier_axis": (0.0, 0.0, 1.0),
            "carrier_diameter": 40.0,
            "normal": (1.0, 0.0, 0.0),
            "centre": (20.0, 0.0, 5.0),
        },
    )
    source = SceneObject(
        id="fan",
        name="Prüffächer",
        mesh=MeshData.of(trimesh.Trimesh(vertices, faces, process=False)),
        features={carrier.id: carrier, pattern.id: pattern},
    )
    changed, refused = _aligned_facets(source, pattern)
    assert not refused
    assert changed is not source, "die Ausrichtung findet statt"
    assert np.allclose(
        changed.mesh.raw.vertices[:, 2], np.asarray(vertices)[:, 2], rtol=0.0, atol=EPS_GEOM
    )
    # Und sie wirkt quer zur Achse: Ecken bewegen sich in der Ebene senkrecht
    # zu ihr (RM-404: die Identität wäre hier grün geblieben).
    moved = np.asarray(changed.mesh.raw.vertices) - np.asarray(vertices)
    assert float(np.max(np.hypot(moved[:, 0], moved[:, 1]))) > 0.0


def test_pattern_facet_alignment_invalidates_previous_cavity_geometry() -> None:
    """Ein Innenraumbeleg der alten Koordinaten gilt nach der Ausrichtung nicht weiter."""
    from app.core.geom.prepare_ops import _aligned_facets
    from tests.helpers import rounded_pattern_carrier

    source = rounded_pattern_carrier()
    mesh = as_mesh_data(source.mesh)
    inner = MeshData.of(trimesh.creation.box(extents=(2.0, 2.0, 2.0)))
    source = dataclasses.replace(source, mesh=dataclasses.replace(mesh, cavity=inner))
    changed, refused = _aligned_facets(source, source.features["pattern_1"])
    assert not refused
    assert changed is not source
    assert as_mesh_data(changed.mesh).cavity is None
    assert as_mesh_data(source.mesh).cavity is inner


def test_pattern_facet_alignment_does_not_flatten_a_nonplanar_carrier() -> None:
    """Eine echte Beule am Träger ist keine zu korrigierende STL-Rundung — und das wird gesagt."""
    from app.core.geom.prepare_ops import _aligned_facets
    from tests.helpers import rounded_pattern_carrier

    source = rounded_pattern_carrier()
    body = source.mesh.raw.copy()
    vertices = np.array(body.vertices)
    # Eine Ecke des Zwischenrings bewegt sich 0,01 mm nach außen. Ihre
    # Nachbarfacetten sind danach nachweislich nicht mehr eben.
    candidate = int(
        np.flatnonzero((np.abs(vertices[:, 2] - 8.0) < EPS_GEOM) & (vertices[:, 0] > 19.0))[0]
    )
    vertices[candidate, 0] += 0.01
    body.vertices = vertices
    source = dataclasses.replace(source, mesh=MeshData.of(body))
    aligned, refused = _aligned_facets(source, source.features["pattern_1"])
    assert aligned is source
    assert refused, "eine Ablehnung trägt ihren Befund (pattern.facets_unaligned)"


def test_pattern_facets_join_the_same_plane_across_the_angle_seam() -> None:
    """Die beiden Normalen um ±180° tragen eine Facette und genau eine Ebene."""
    frame = patterns.Frame.cylinder(
        np.array([0.0, 0.0, 1.0]),
        np.zeros(3),
        20.0,
        reference=np.array([1.0, 0.0, 0.0]),
        sag=0.0,
    )
    normals = np.array(
        [[-1.0, -1e-6, 0.0], [-1.0, 1e-6, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]
    )
    angles, groups = patterns.cylinder_facet_groups(frame, normals)
    assert len(angles) == len(groups) == 4
    assert any(set(group) == {0, 1} for group in groups)
    points = np.array(
        [
            normal * 20.0 + shift
            for normal in normals
            for shift in (
                np.array([0.0, 0.0, -1.0]),
                np.array([0.0, 0.0, 1.0]),
                np.cross(normal, [0.0, 0.0, 1.0]),
            )
        ]
    )
    planes = patterns._facet_planes(frame, points, np.arange(len(points)).reshape(-1, 3), normals)
    assert planes is not None and len(planes[0]) == 4, "der Stopfen liest dieselben vier Facetten"


@pytest.mark.parametrize("phase", ["facets", "vertices"])
def test_pattern_facet_alignment_can_cancel_without_changing_the_source(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    """Abbrechen greift während beider Ausrichtungsschleifen vor der Booleschen Rechnung."""
    from app.core import units
    from app.core.errors import OperationCancelled
    from app.core.geom.prepare_ops import _aligned_facets
    from app.core.scene.cancel import CancelSignal
    from tests.helpers import rounded_pattern_carrier

    source = rounded_pattern_carrier()
    original = source.mesh.raw.vertices.copy()
    cancelled = CancelSignal()
    # Je Facette eine Gerade, je Gruppe gemeinsamer Ecken eine Eigenzerlegung —
    # abgebrochen wird nach der ersten von beiden.
    owner, method = (patterns, "_facet_line") if phase == "facets" else (units, "symmetric_eigen3")
    calculate = getattr(owner, method)

    def stop_during_alignment(*args: object, **kwargs: object) -> object:
        answer = calculate(*args, **kwargs)
        cancelled.cancel()
        return answer

    monkeypatch.setattr(owner, method, stop_during_alignment)
    with pytest.raises(OperationCancelled):
        _aligned_facets(source, source.features["pattern_1"], cancelled=cancelled)
    assert np.array_equal(source.mesh.raw.vertices, original)


def _stl_rounded_fluted_lid(
    offset: tuple[float, float] = (0.0, 0.0),
    radius: float = 20.0,
    sections: int = 96,
    count: int = 24,
) -> tuple[SceneObject, float]:
    """Ein facettierter Deckel mit ``count`` Randrillen nach dem binären STL-Weg.

    ``offset`` legt ihn dorthin, wo er in der Datei steht — die Rundung auf
    ``float32`` geschieht dort (RM-404). Die Rillen laufen durch die Unterseite
    und enden 3,1 mm unter der Oberseite.
    """
    from app.core.ingest.loader import normalise, read_model

    cancel = NeverCancelled()
    body = trimesh.creation.cylinder(radius=radius, height=16.0, sections=sections)
    body.apply_translation((offset[0], offset[1], 8.0))
    smooth_carrier_volume = float(body.volume)
    for index in range(count):
        angle = math.radians(index * 360.0 / count)
        groove = trimesh.creation.cylinder(radius=1.1, height=13.0, sections=14)
        groove.apply_translation(
            (offset[0] + radius * math.cos(angle), offset[1] + radius * math.sin(angle), 6.4)
        )
        body = boolean(
            "difference",
            [MeshData.of(body), MeshData.of(groove)],
            quality="fine",
            seed=7,
            cancelled=cancel,
        ).mesh.raw

    imported = read_model(trimesh.exchange.stl.export_stl(body), ".stl")
    mesh = normalise(
        imported,
        "mm",
        weld_is_reading=True,
        mend=False,
        cancelled=cancel,
    ).mesh
    return (
        SceneObject(id="obj_1", name="Deckel", mesh=mesh, features=detect(mesh)),
        smooth_carrier_volume,
    )


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("operation", ["remove_feature", "resize_feature"])
@pytest.mark.parametrize(
    ("offset", "radius", "sections", "count"),
    [
        # Mitte bei x = y = 110 mm: Das float32-Raster misst dort 7,6 nm, und
        # die gemessene Achse steht 1,9·10⁻⁸ rad schräg. Vier Selbstschnitte an
        # den Rillen bei 15° und 165°, und die Unterseite zerfiel in 25 Flächen.
        ((110.0, 110.0), 20.0, 96, 24),
        # Ø 80 mit 48 Rillen am Ursprung (Review-Fall C): zwei Selbstschnitte
        # an der Unterseite, obwohl die Ausrichtung gelang — still.
        ((0.0, 0.0), 40.0, 96, 48),
        # CAD-Nullpunkt in der Ecke.
        ((20.0, 20.0), 20.0, 96, 24),
        # Ein feiner geteilter Mantel: 384 Facetten unter denselben Rillen.
        # Er braucht die Ausrichtung nicht — er hält den Stopfen an einem
        # feinen Vieleck fest, nicht die Grenze der Ausrichtung (die hält
        # ``test_a_finely_meshed_carrier_is_aligned_onto_the_facets_the_plug_reads``).
        ((0.0, 0.0), 20.0, 384, 24),
    ],
    ids=["bett-110", "d80-48-rillen", "cad-ecke", "384-facetten"],
)
def test_stl_rounded_lids_anywhere_keep_pattern_edits_free_of_self_intersections(
    operation: str,
    quality: Quality,
    offset: tuple[float, float],
    radius: float,
    sections: int,
    count: int,
) -> None:
    """Muster an verschobenen und größeren STL-Deckeln schließen ohne Selbstschnitt (RM-404).

    Zwei Ursachen lagen hinter der Ausrichtung. Mantel und Stopfen lasen ihre
    Facetten verschieden — die Ausrichtung als Ebene durch alle Ecken, um
    10⁻⁷ rad gegen die Achse geneigt, der Stopfen achsparallel aus einem
    Dreieck, mit den Grenzen auf der Winkelhalbierenden statt am Schnitt der
    Facetten —, und sie lagen bis 1,5·10⁻⁶ mm auseinander. Und die Stirnenden
    des Stopfens standen quer zur gemessenen Achse statt in der Stirnfläche:
    Bei (110, 110) blieb unter jeder Rille eine eigene Fläche stehen.
    """
    from app.core.geom.repair import self_intersection_check

    source, carrier_volume = _stl_rounded_fluted_lid(offset, radius, sections, count)
    pattern = only_pattern(source.features)
    assert pattern.params["count"] == count
    params: dict[str, object] = {"at_feature": pattern.id}
    if operation == "resize_feature":
        params["pitch"] = 5.9
    changed, findings = run_op(operation, source, quality=quality, **params)

    assert "pattern.facets_unaligned" not in {finding.code for finding in findings}
    assert changed.mesh.raw.is_watertight
    assert changed.mesh.component_count == 1
    assert self_intersection_check(as_mesh_data(changed.mesh), NeverCancelled()) == ((), True)
    # Unter- und Oberseite bleiben je eine ganze Fläche.
    assert np.allclose(
        _lid_end_face_centres(changed.features), [0.0, 16.0], rtol=0.0, atol=EPS_GEOM
    )
    pin = next(feature for feature in changed.features.values() if feature.kind == "pin")
    assert math.isclose(float(pin.params["diameter"]), 2.0 * radius, abs_tol=1e-3)
    if operation == "remove_feature":
        assert kinds(changed.features) == {"pin": 1, "face": 2}
        # Bis auf die float32-Rundung des Mantels das Vieleck ohne Rillen.
        assert math.isclose(changed.mesh.raw.volume, carrier_volume, abs_tol=0.02)
    else:
        assert kinds(changed.features) == {"pin": 1, "face": 2, "pattern": 1}
        after = only_pattern(changed.features)
        assert after.params["style"] == pattern.params["style"]
        # Einmal ganz herum, die Teilung auf den Umfang gerückt.
        assert after.params["partial"] == 0
        assert math.isclose(
            after.params["count"] * after.params["pitch"], 2.0 * math.pi * radius, rel_tol=1e-3
        )


def _subdivided_pattern_carrier(subdivisions: int) -> SceneObject:
    """96 Mantelfacetten, ``subdivisions``-mal geteilt und auf float32 gerundet wie in einer STL.

    Fünfmal geteilt trägt der Mantel 101 376 Ecken — so viele, wie ein fein
    exportierter oder nach *Kanten verfeinern* geteilter Mantel hat. Das Muster
    nennt nur seine Lage; die Ausrichtung braucht keine Zellen.
    """
    from app.core.geom import lathe
    from app.core.geom.mesh import stable_normals

    cylinder = lathe.cylinder(radius=20.0, height=16.0, sections=96)
    vertices = np.asarray(cylinder.vertices) + np.array([0.0, 0.0, 8.0])
    faces = np.asarray(cylinder.faces)
    for _ in range(subdivisions):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    body = trimesh.Trimesh(vertices.astype(np.float32).astype(np.float64), faces, process=False)
    side = np.flatnonzero(np.abs(stable_normals(body)[0][:, 2]) < 0.5)
    pin = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        face_indices=tuple(int(index) for index in side),
        params={"axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 8.0), "diameter": 40.0},
    )
    pattern = Feature(
        id="pattern_1",
        kind="pattern",
        provenance="detected",
        params={
            "carrier": "cylinder",
            "carrier_axis": (0.0, 0.0, 1.0),
            "carrier_diameter": 40.0,
            "normal": (1.0, 0.0, 0.0),
            "centre": (20.0, 0.0, 8.0),
        },
    )
    return SceneObject(
        id="obj_1",
        name="Träger",
        mesh=MeshData.of(body),
        features={pin.id: pin, pattern.id: pattern},
    )


def _off_the_plug_facets(body: SceneObject) -> float:
    """Wie weit eine Trägerecke höchstens neben der Facette liegt, auf die der Stopfen sich legt."""
    mesh = as_mesh_data(body.mesh)
    pattern = body.features["pattern_1"]
    frame = patterns.frame_for(pattern, mesh, body.features)
    carrier = patterns.carrier_of(pattern, body.features)
    assert carrier is not None and frame.facets is not None
    corners = np.unique(np.asarray(mesh.raw.faces)[np.asarray(carrier.face_indices)])
    developed, heights = frame.developed(np.asarray(mesh.raw.vertices)[corners])
    # Je Ecke einzeln: ``developed`` wickelt um das Mittel der Punkte ab.
    theta = (developed[:, 0] / frame.radius + math.pi) % (2.0 * math.pi) - math.pi
    reach = heights + frame.radius
    return float(np.max(np.abs(reach - frame._facet_radius(theta))))


@pytest.mark.parametrize("subdivisions", [1, 5])
def test_a_finely_meshed_carrier_is_aligned_onto_the_facets_the_plug_reads(
    subdivisions: int,
) -> None:
    """Auch am fein geteilten Mantel liegt jede Ecke danach auf der Facette des Stopfens (RM-404).

    Mit der festen Grenze von 1 nm lehnte die Ausrichtung den fünfmal geteilten
    Träger ab — eine seiner 101 376 Ecken lag 1,01·10⁻⁶ mm neben ihrer Ebene.
    Und die Ebenen, auf die sie ausrichtete, waren nicht die, auf die sich der
    Stopfen legt: Ohne Ausrichtung liegen die Ecken einige 10⁻⁶ mm daneben,
    nach ihr innerhalb der Rundung der Koordinaten.
    """
    from app.core.geom.prepare_ops import _aligned_facets

    source = _subdivided_pattern_carrier(subdivisions)
    before = _off_the_plug_facets(source)
    aligned, refused = _aligned_facets(source, source.features["pattern_1"])

    assert not refused
    assert aligned is not source
    after = _off_the_plug_facets(aligned)
    # Was die Rundung in doppelter Genauigkeit übrig lässt: tausend Schritte
    # der Zahl 24 (größte Koordinate) sind 3,6·10⁻¹² mm — sechs Größenordnungen
    # unter dem float32-Raster, das der Eingang trägt.
    reach = float(np.max(np.abs(np.asarray(source.mesh.raw.vertices))))
    assert before > 1e3 * float(np.spacing(reach)), "der Eingang muss das Raster tragen"
    assert after <= 1e3 * float(np.spacing(reach))


def test_a_plug_ends_in_an_end_face_only_where_the_shell_ends_in_it() -> None:
    """Die Stirnfläche, in der ein Stopfen endet, muss den Mantel abschließen (RM-404).

    Ein Stopfen durch eine Stirnfläche endet in deren gemessener Ebene
    (``Frame.ends``). Unter einer Fase von 0,02 mm liegt die Unterseite noch
    innerhalb der Grenze, mit der das Muster fragt, was am Ende des Stifts
    liegt (``MAX_FACET_SAG``) — aber der Mantel endet nicht in ihr, und ein
    Stopfen bis dorthin legte Material über die Fase. Oben ohne Fase gilt die
    Deckfläche.
    """
    from app.core import units

    sections = 96
    ring = np.array([units.circle_point(sections, index) for index in range(sections)])
    rows = [(19.98, 0.0), (20.0, 0.02), (20.0, 16.0)]
    vertices = np.vstack(
        [np.column_stack((ring * radius, np.full(sections, z))) for radius, z in rows]
        + [np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 16.0]])]
    )
    bottom, top = 3 * sections, 3 * sections + 1
    bands = [
        (row * sections + index, row * sections + nxt, (row + 1) * sections + nxt)
        for row in range(2)
        for index in range(sections)
        for nxt in [(index + 1) % sections]
    ] + [
        (row * sections + index, (row + 1) * sections + nxt, (row + 1) * sections + index)
        for row in range(2)
        for index in range(sections)
        for nxt in [(index + 1) % sections]
    ]
    caps = [(bottom, (index + 1) % sections, index) for index in range(sections)] + [
        (top, 2 * sections + index, 2 * sections + (index + 1) % sections)
        for index in range(sections)
    ]
    body = trimesh.Trimesh(vertices, bands + caps, process=False)
    assert body.is_watertight and body.is_winding_consistent and body.volume > 0.0
    mantle = [
        number
        for number, face in enumerate(bands)
        if min(vertices[corner][2] for corner in face) >= 0.02
    ]
    first_cap = len(bands)
    carrier = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        face_indices=tuple(mantle),
        params={"axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 8.0), "diameter": 40.0},
    )
    underside = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        face_indices=tuple(range(first_cap, first_cap + sections)),
        params={"normal": (0.0, 0.0, -1.0), "centre": (0.0, 0.0, 0.0), "area": 1254.0},
    )
    lid = Feature(
        id="face_2",
        kind="face",
        provenance="detected",
        face_indices=tuple(range(first_cap + sections, first_cap + 2 * sections)),
        params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 16.0), "area": 1255.7},
    )
    pattern = Feature(
        id="pattern_1",
        kind="pattern",
        provenance="detected",
        params={
            "carrier": "cylinder",
            "carrier_axis": (0.0, 0.0, 1.0),
            "carrier_diameter": 40.0,
            "normal": (1.0, 0.0, 0.0),
            "centre": (20.0, 0.0, 8.0),
        },
    )
    features = {item.id: item for item in (carrier, underside, lid, pattern)}
    frame = patterns.frame_for(pattern, MeshData.of(body), features)

    assert frame.span is not None and frame.ends is not None
    below, above = frame.ends
    assert below is None, "die Unterseite liegt 0,02 mm unter dem Ende des Mantels"
    assert above is not None and math.isclose(above.offset, 16.0)
    # Und ohne Fase gilt auch die Unterseite.
    flush = dataclasses.replace(
        carrier, face_indices=tuple(range(len(bands))), params={**carrier.params}
    )
    frame = patterns.frame_for(pattern, MeshData.of(body), {**features, flush.id: flush})
    assert frame.ends is not None and frame.ends[0] is not None
    assert math.isclose(frame.ends[0].offset, 0.0, abs_tol=EPS_GEOM)


def test_the_plug_turns_from_facet_to_facet_where_the_facets_meet() -> None:
    """Die Grenze zwischen zwei Facetten liegt an ihrem Schnitt, nicht auf der Winkelhalbierenden.

    Ein Vieleck aus einer STL hat Facetten verschiedenen Abstands von der
    Achse. Auf der Winkelhalbierenden springt der Stopfen dann um den
    Unterschied der Abstände von einer Facette auf die andere, und seine
    Ecke dort liegt neben der Ecke des Mantels (RM-404). Zwölf Facetten mit
    Abständen, die um bis zu 0,01 mm auseinanderliegen.
    """
    from app.core import units

    sections = 12
    offsets = 10.0 + 0.01 * np.array([0, 3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]) / 9.0
    normals = [units.circle_point(sections, index) for index in range(sections)]
    corners = []
    for index in range(sections):
        (x1, y1), (x2, y2) = normals[index], normals[(index + 1) % sections]
        o1, o2 = offsets[index], offsets[(index + 1) % sections]
        det = x1 * y2 - y1 * x2
        corners.append(((o1 * y2 - o2 * y1) / det, (x1 * o2 - x2 * o1) / det))
    ring = np.array(corners)
    body = trimesh.Trimesh(
        np.vstack(
            [
                np.column_stack((ring, np.zeros(sections))),
                np.column_stack((ring, np.full(sections, 6.0))),
            ]
        ),
        [
            face
            for index in range(sections)
            for face in (
                (index, (index + 1) % sections, sections + (index + 1) % sections),
                (index, sections + (index + 1) % sections, sections + index),
            )
        ],
        process=False,
    )
    carrier = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        face_indices=tuple(range(2 * sections)),
        params={"axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 3.0), "diameter": 20.0},
    )
    pattern = Feature(
        id="pattern_1",
        kind="pattern",
        provenance="detected",
        params={
            "carrier": "cylinder",
            "carrier_axis": (0.0, 0.0, 1.0),
            "carrier_diameter": 20.0,
            "normal": (1.0, 0.0, 0.0),
            "centre": (10.0, 0.0, 3.0),
        },
    )
    frame = patterns.frame_for(
        pattern, MeshData.of(body), {carrier.id: carrier, pattern.id: pattern}
    )
    assert frame.facets is not None and len(frame.facets[0]) == sections
    borders = frame._facet_borders(np.array([-math.pi * frame.radius, math.pi * frame.radius]))
    assert len(borders) == sections
    placed = frame.world(np.column_stack((borders, np.zeros(sections))), 0.0, faceted=True)
    # Jede Grenze trifft eine Ecke des Vielecks, auf ein paar Rundungsschritte genau.
    nearest = np.min(np.linalg.norm(placed[:, None, :2] - ring[None, :, :], axis=2), axis=1)
    assert float(np.max(nearest)) <= 1e3 * float(np.spacing(10.0))


def test_a_refused_facet_alignment_is_said_with_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lehnt die Ausrichtung ab, steht es im Bericht — mit *Reparieren* (RM-404).

    Dreizehn Wege führten still zur Quelle zurück, und die Selbstschnitte danach
    standen ohne Satz da; im Bericht stand nur „entfernt“.
    """
    from app.core.geom import prepare_ops

    source, _carrier_volume = _stl_rounded_fluted_lid()
    pattern = only_pattern(source.features)
    monkeypatch.setattr(
        prepare_ops, "_aligned_facets", lambda body, feature, cancelled=None: (body, True)
    )

    _changed, findings = run_op("remove_feature", source, quality="fine", at_feature=pattern.id)

    refused = [finding for finding in findings if finding.code == "pattern.facets_unaligned"]
    assert len(refused) == 1
    assert refused[0].severity == "warning"
    assert "repair_and_retry" in {action.id for action in refused[0].suggestions}


@pytest.mark.parametrize("operation", ["remove_feature", "resize_feature"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_stl_rounded_fluted_lid_keeps_pattern_edits_free_of_self_intersections(
    operation: str,
    quality: Quality,
) -> None:
    """STL-Rundung darf Musterstopfen am Vieleckträger nicht selbst schneiden lassen."""
    from app.core.geom.repair import self_intersection_check

    source, carrier_volume = _stl_rounded_fluted_lid()
    pattern = only_pattern(source.features)
    assert pattern.params["count"] == 24
    assert self_intersection_check(as_mesh_data(source.mesh), NeverCancelled()) == ((), True)

    params: dict[str, object] = {"at_feature": pattern.id}
    if operation == "resize_feature":
        params["pitch"] = 5.9
    changed, _findings = run_op(operation, source, quality=quality, **params)

    assert changed.mesh.raw.is_watertight
    assert changed.mesh.component_count == 1
    assert self_intersection_check(as_mesh_data(changed.mesh), NeverCancelled()) == ((), True)
    assert np.allclose(
        _lid_end_face_centres(changed.features), [0.0, 16.0], rtol=0.0, atol=EPS_GEOM
    )
    pin = next(feature for feature in changed.features.values() if feature.kind == "pin")
    assert math.isclose(float(pin.params["diameter"]), 40.0, abs_tol=1e-3)
    if operation == "remove_feature":
        assert kinds(changed.features) == {"pin": 1, "face": 2}
        assert math.isclose(changed.mesh.raw.volume, carrier_volume, abs_tol=0.01)
    else:
        assert kinds(changed.features) == {"pin": 1, "face": 2, "pattern": 1}
        after = only_pattern(changed.features)
        assert after.params["count"] == 21
        assert after.params["style"] == pattern.params["style"]
        assert math.isclose(after.params["pitch"], 2.0 * math.pi * 20.0 / 21.0, abs_tol=1e-3)


@pytest.mark.parametrize("pattern", ["rib", "knurl_diamond"])
@pytest.mark.parametrize("pitch", [4.0, 5.9])
@pytest.mark.parametrize("z", [-8.0, 8.0])
def test_redrawing_grooves_through_the_end_face_leaves_no_fins(
    pattern: str, pitch: float, z: float
) -> None:
    """Ein neues Muster läuft durch dieselbe Stirnfläche und lässt dort keine Nullhaut.

    Die sieben Faltungen des Kreuzrändels mit 4 mm Teilung waren am Netz
    wasserdicht, machten aber aus der oberen Stirnfläche 16 Verrundungen.
    Die Zahl der Komponenten allein hätte den Fehler nicht festgehalten.
    """
    source = grooved_to_end_face(pattern, z=z)
    read = only_pattern(source.features)
    redrawn, _findings = run_op("resize_feature", source, at_feature=read.id, pitch=pitch)
    body = redrawn.mesh.raw
    assert body.is_watertight and body.is_winding_consistent
    assert redrawn.mesh.component_count == 1
    assert _folded_edges(body) == 0
    assert math.isclose(_read_volume(body), body.volume, rel_tol=1e-9)
    assert kinds(redrawn.features) == {"pin": 1, "face": 2, "pattern": 1}
    after = only_pattern(redrawn.features)
    assert after.params["style"] == pattern
    expected = wrap_pitch(pattern, pitch, CYLINDER_DIAMETER, CIRCUMFERENCE)
    assert math.isclose(after.params["pitch"], expected, abs_tol=0.02)
    np.testing.assert_allclose(
        body.bounds[:, 2], [-CYLINDER_LENGTH / 2.0, CYLINDER_LENGTH / 2.0], atol=EPS_GEOM, rtol=0.0
    )


def test_a_facet_border_beside_a_corner_of_the_plug_splits_without_fins() -> None:
    """Eine Facettengrenze 10⁻¹⁴ neben einer Ecke des Stopfens teilt ihn sauber.

    ``refined_for_bending`` teilt die Kanten einer Mündung gleichmäßig; sitzt
    die Zelle mittig auf einer Kante des Vielecks, fällt eine Ecke auf die
    Facettengrenze — bis auf die letzte Stelle. Der Schnitt über
    ``split_by_plane`` und ``batch_boolean`` ließ dort Finnen stehen, und
    ``manifold3d`` las den Stopfen danach mit 0,1 mm³ weniger: Nach dem
    Entfernen von 48 Taschen um einen Griff blieben vier Hohlräume im Körper
    (23.09.2026). Der Quader hat die Maße eines solchen Stopfens, die
    Kantenlänge ist eine Facettenbreite an Ø 30 mit 96 Facetten.
    """
    from app.core.geom.mesh_ops import refined

    box = MeshData.of(trimesh.creation.box(extents=(3.08, 5.08, 1.0257)))
    body = refined(box, 15.0 * 2.0 * math.pi / 96).raw
    assert (np.asarray(body.vertices)[:, 0] == 0.0).any(), "der Fall braucht eine Ecke bei x = 0"
    for position in (0.0, 3.6e-15, 2e-14, -2e-14):
        split = patterns._split_along(body, np.array([position]))
        assert _folded_edges(split) == 0, position
        assert math.isclose(_read_volume(split), body.volume, rel_tol=1e-9), position
        assert split.is_watertight and split.is_winding_consistent, position
        assert math.isclose(split.volume, body.volume, rel_tol=1e-12), position
        offset = np.asarray(split.vertices)[np.asarray(split.faces)][:, :, 0] - position
        across = (offset.min(axis=1) < -EPS_GEOM) & (offset.max(axis=1) > EPS_GEOM)
        assert not across.any(), position


def test_splitting_at_many_positions_keeps_the_body_closed_and_its_volume() -> None:
    """Die Eigenschaften des Schnitts an einem Körper ohne Sonderlage.

    Jede Lage, auch eine genau auf einer Ecke: dicht, gleich orientiert,
    dasselbe Volumen, kein Dreieck quer zu einer Lage — und keine neuen Ecken
    neben einer Lage, nur auf ihr.
    """
    body = trimesh.creation.icosphere(subdivisions=2, radius=10.0)
    xs = np.asarray(body.vertices)[:, 0]
    positions = np.array([-7.3, -2.0, float(xs[5]), 1.0 / 3.0, 6.5])
    split = patterns._split_along(body, positions)
    assert split.is_watertight and split.is_winding_consistent
    assert math.isclose(split.volume, body.volume, rel_tol=1e-12)
    assert math.isclose(_read_volume(split), body.volume, rel_tol=1e-9)
    corners = np.asarray(split.vertices)[np.asarray(split.faces)][:, :, 0]
    for position in positions:
        offset = corners - position
        across = (offset.min(axis=1) < -EPS_GEOM) & (offset.max(axis=1) > EPS_GEOM)
        assert not across.any(), position
    # Genau auf der Lage, nicht ein ulp daneben: Genau das ließ die Finnen entstehen.
    added = np.asarray(split.vertices)[len(body.vertices) :, 0]
    assert len(added) and np.isin(added, positions).all()


def test_a_full_turn_redrawn_has_no_seam() -> None:
    """24 Rillen mit 3,93 — und an der Naht keine halbe, keine doppelte."""
    out, _findings = wrapped("rib", "engraved", CIRCUMFERENCE)
    read = only_pattern(out.features)
    redrawn, _findings = run_op("resize_feature", out, at_feature=read.id, pitch=4.0)
    after = only_pattern(redrawn.features)
    assert after.params["count"] == 24
    assert after.params["partial"] == 0


def test_no_strip_of_the_shell_stays_behind_as_a_face() -> None:
    """Ein Mantelstück zwischen zwei Rillen ist Mantel, keine Fläche.

    Es hat zu beiden Seiten eine Nut und damit keine Naht mehr zu einer
    Nachbarfacette — die Rundung erkennt es nicht mehr an ihr, und es stand
    nach dem Neuzeichnen als Fläche von 10 mm² im Baum (RM-207).
    """
    out, _findings = wrapped("rib", "engraved", CIRCUMFERENCE)
    read = only_pattern(out.features)
    redrawn, _findings = run_op("resize_feature", out, at_feature=read.id, pitch=4.0)
    # Der Stift und die zwei Stirnflächen — mehr steht am Rohr nicht.
    assert kinds(redrawn.features) == {"pin": 1, "face": 2, "pattern": 1}, kinds(redrawn.features)
    faces = [f for f in redrawn.features.values() if f.kind == "face"]
    assert all(abs(f.params["normal"][2]) > 0.99 for f in faces), [f.params for f in faces]


def test_a_flat_on_a_cylinder_stays_a_face() -> None:
    """Die Gegenprobe: Eine Abflachung hat ihre Ecken auf dem Mantel und bleibt trotzdem.

    Ihr Rand **ist** der Schnittkreis, also liegt jede Ecke auf dem Radius —
    erst ihre Mitte sagt, dass sie Millimeter darunter liegt.
    """
    shape = trimesh.creation.cylinder(radius=15.0, height=30.0, sections=96)
    cut = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    cut.apply_translation((0.0, 33.0, 0.0))
    flattened = MeshData.of(trimesh.boolean.difference([shape, cut]))
    found = detect(flattened)
    flat = [
        feature
        for feature in found.values()
        if feature.kind == "face" and abs(feature.params["normal"][1] - 1.0) < 0.01
    ]
    assert len(flat) == 1, kinds(found)
    assert flat[0].params["area"] > 100.0


def test_a_wrapped_pattern_travels_with_its_axis_when_moved() -> None:
    """Achse und Mitte reisen mit der Bewegung (§21.2), der Durchmesser bleibt."""
    from app.core.perceive.matching import moved_features

    out, _findings = wrapped("dimple", "raised", 40.0)
    read = only_pattern(out.features)
    turn = np.eye(4)
    turn[:3, :3] = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
    turn[:3, 3] = (5.0, -2.0, 9.0)
    after = moved_features(out.features, turn)[read.id]
    assert np.allclose(np.abs(after.params["carrier_axis"]), (0.0, 1.0, 0.0), atol=1e-6)
    expected = turn[:3, :3] @ np.asarray(read.params["centre"]) + turn[:3, 3]
    assert np.allclose(after.params["centre"], expected)
    assert np.allclose(after.params["normal"], turn[:3, :3] @ np.asarray(read.params["normal"]))
    assert math.isclose(after.params["carrier_diameter"], read.params["carrier_diameter"])


def test_the_digest_names_the_cylinder_a_wrapped_pattern_runs_around() -> None:
    out, _findings = wrapped("rib", "engraved", CIRCUMFERENCE)
    read = only_pattern(out.features)
    line = _feature_line(read.id, read)
    assert "Rippenmuster" in line
    assert "Ø 30.00 mm" in line, line
    assert "Achse" in line


def pocketed_grip() -> MeshData:
    """Der Griff mit 48 Taschen, die kein Solidon-Stil sind: 3 auf 5 mm, parallele Wände.

    Gefräst wie in einer heruntergeladenen Datei — der Boden eben, die Wände
    parallel statt radial. In der Abwicklung ist eine solche Tasche am Boden
    breiter als an der Mündung (``R / (R - Tiefe)``), und das ist der Fall,
    den ein gerades Prisma nicht füllt.
    """
    tools = []
    for i in range(16):
        angle = 2.0 * math.pi * i / 16
        for z in (-8.0, 0.0, 8.0):
            box = trimesh.creation.box(extents=(2.0, 3.0, 5.0))
            box.apply_translation((CYLINDER_DIAMETER / 2.0, 0.0, z))
            box.apply_transform(trimesh.transformations.rotation_matrix(angle, (0, 0, 1)))
            tools.append(box)
    return boolean(
        "difference",
        [cylinder(), MeshData.of(trimesh.util.concatenate(tools))],
        quality="fine",
        cancelled=NeverCancelled(),
    ).mesh


def test_removing_foreign_pockets_around_a_grip_leaves_no_voids() -> None:
    """Entfernen füllt jede Tasche ganz — auch die, deren Wände nicht radial stehen.

    Das Prisma über der Mündung wurde gerade um den Zylinder gebogen und blieb
    in der Abwicklung so breit wie die Mündung. Eine Tasche mit parallelen
    Wänden ist am Boden aber breiter: Bis zum 22.09.2026 blieben an jedem
    Taschenboden zwei eingeschlossene Hohlräume von 0,07 mm³ stehen — 96
    Schalen im Körper, der Slicer druckt sie als Luftblasen.
    """
    mesh = pocketed_grip()
    entry = SceneObject(id="obj_1", name="Griff", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    assert read.params["style"] == "other" and read.params["carrier"] == "cylinder"
    plain, _findings = run_op("remove_feature", entry, at_feature=read.id)
    body = as_mesh_data(plain.mesh)
    assert body.component_count == 1, f"{body.component_count} Schalen, eingeschlossene Hohlräume"
    assert math.isclose(body.volume, cylinder().volume, abs_tol=0.05), body.volume


@pytest.mark.parametrize("style", ["hexagon", "rib", "knurl_diamond"])
def test_a_foreign_pattern_around_a_grip_is_replaced_by_an_own_style(style: str) -> None:
    """Ein fremdes Muster um einen Griff bekommt einen eigenen Stil — in einem Schritt."""
    mesh = pocketed_grip()
    entry = SceneObject(id="obj_1", name="Griff", mesh=mesh, features=detect(mesh))
    read = only_pattern(entry.features)
    restyled, findings = run_op("resize_feature", entry, at_feature=read.id, style=style)
    body = as_mesh_data(restyled.mesh)
    assert body.is_watertight
    assert body.component_count == 1, body.component_count
    assert "resize_feature.pattern" in [finding.code for finding in findings]
    assert body.volume < cylinder().volume - 50.0, "die neuen Zellen sind eingeschnitten"
    after = [f for f in restyled.features.values() if f.kind == "pattern"]
    if style == "hexagon":
        # Rippen und Kreuzrändel mit 5,9 mm Teilung um Ø 30 liest die Erkennung
        # heute nicht als Muster zurück (gemessen 23.09.2026: 34 Flächen bzw.
        # der blanke Stift) — das ist eine Frage an die Erkennung, nicht an das
        # Zeichnen; die Geometrie darüber ist geprüft.
        assert after and after[0].params["carrier"] == "cylinder"
        assert after[0].params["style"] == "hexagon"


def _imported_texture_fields(style: str, angle: float, mode: str, path: Path) -> SceneObject:
    """Zwei Felder über STL einlesen, ohne die Herkunft ihrer Erzeugung."""
    entry = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(90.0, 60.0, 6.0))),
    )
    for x, turn in ((-23.0, 0.0), (23.0, angle)):
        entry, _ = run_op(
            "apply_texture",
            entry,
            pattern=style,
            mode=mode,
            pitch=4.0,
            depth=0.6,
            width=30.0,
            height=20.0,
            x=x,
            z=3.0,
            nz=1.0,
            angle=turn,
        )
    mesh = as_mesh_data(entry.mesh).raw.copy()
    mesh.apply_transform(trimesh.transformations.rotation_matrix(math.radians(17.0), (0, 0, 1)))
    mesh.export(path)
    imported = MeshData.of(trimesh.load_mesh(path, process=True))
    return dataclasses.replace(entry, mesh=imported, features=detect(imported))


@pytest.mark.parametrize("style", ["rib", "hexagon", "dimple"])
@pytest.mark.parametrize("angle", [0.0, 45.0, 90.0])
@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_separate_imported_texture_fields_remain_separate(
    style: str, angle: float, mode: str, tmp_path: Path
) -> None:
    """Zwei getrennte Felder überstehen STL-Rundung und gemeinsame Drehung."""
    found = _imported_texture_fields(style, angle, mode, tmp_path / "two_fields.stl").features
    fields = [feature for feature in found.values() if feature.kind == "pattern"]
    assert len(fields) == 2, kinds(found)
    assert {feature.params["style"] for feature in fields} == {style}
    assert all(float(feature.params["width"]) < 35.0 for feature in fields)
    assert not set(fields[0].face_indices).intersection(fields[1].face_indices)
    assert kinds(found) == {"face": 6, "pattern": 2}, kinds(found)


@pytest.mark.parametrize("style", ["rib", "hexagon"])
@pytest.mark.parametrize("mode", ["raised", "engraved"])
@pytest.mark.parametrize("operation", ["remove_feature", "resize_feature"])
def test_editing_one_imported_field_preserves_the_other(
    style: str, mode: str, operation: str, tmp_path: Path
) -> None:
    """Entfernen und Ändern treffen weder das zweite Feld noch den Zwischenraum."""
    entry = _imported_texture_fields(style, 45.0, mode, tmp_path / "two_fields.stl")
    fields = sorted(
        (feature for feature in entry.features.values() if feature.kind == "pattern"),
        key=lambda feature: float(feature.params["centre"][0]),
    )
    assert len(fields) == 2
    params = {"cell_depth": 0.9} if operation == "resize_feature" else {}
    changed, _ = run_op(operation, entry, at_feature=fields[0].id, **params)
    original_mesh, changed_mesh = as_mesh_data(entry.mesh), as_mesh_data(changed.mesh)
    preserved = patterns.surface_triangles(
        original_mesh, changed_mesh, candidates=fields[1].face_indices
    )
    assert set(preserved) == set(fields[1].face_indices)
    after = [feature for feature in changed.features.values() if feature.kind == "pattern"]
    assert len(after) == (2 if operation == "resize_feature" else 1)
    right = max(after, key=lambda feature: float(feature.params["centre"][0]))
    assert right.params["style"] == fields[1].params["style"]
    assert right.params["cell_depth"] == pytest.approx(fields[1].params["cell_depth"])
    unturned = changed_mesh.raw.copy()
    unturned.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(-17.0), (0, 0, 1))
    )
    middle = trimesh.intersections.mesh_plane(unturned, (1, 0, 0), (0, 0, 0))
    assert len(middle)
    assert np.max(np.abs(middle[:, :, 2])) <= 3.0 + EPS_GEOM
    assert np.linalg.norm(middle[:, 1] - middle[:, 0], axis=1).sum() == pytest.approx(132.0)


def test_pattern_cell_folding_requires_full_containment_in_one_pattern() -> None:
    """Teilflächen, fremde Bohrungen und leere Belege bleiben unverändert."""

    def feature(name: str, kind: str, faces: tuple[int, ...]) -> Feature:
        return Feature(id=name, kind=kind, provenance="detected", params={}, face_indices=faces)

    found = {
        "p1": feature("p1", "pattern", (1, 2, 3)),
        "p2": feature("p2", "pattern", (4, 5, 6)),
        "cell": feature("cell", "face", (1, 2)),
        "crossing": feature("crossing", "face", (3, 4)),
        "carrier": feature("carrier", "face", (2, 7)),
        "hole": feature("hole", "hole", (8, 9)),
        "empty": feature("empty", "face", ()),
        "unknown_pattern": dataclasses.replace(
            feature("unknown_pattern", "pattern", (8, 9)), recognised=False
        ),
    }
    folded = patterns.without_pattern_cells(found)
    assert set(folded) == set(found) - {"cell"}
    assert all(folded[name] is found[name] for name in folded)


def test_a_short_separate_rib_field_stays_unclassified() -> None:
    """Ein belegtes Feld macht drei entfernte Rippen nicht zur selben Textur."""
    entry = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box(extents=(90.0, 60.0, 6.0))),
    )
    for x, width in ((-23.0, 30.0), (23.0, 12.0)):
        entry, _ = run_op(
            "apply_texture",
            entry,
            pattern="rib",
            mode="raised",
            pitch=4.0,
            depth=0.6,
            width=width,
            height=20.0,
            x=x,
            z=3.0,
            nz=1.0,
        )
    found = detect(as_mesh_data(entry.mesh))
    field = only_pattern(found)
    assert float(field.params["centre"][0]) < 0.0
    assert float(field.params["width"]) < 35.0
    assert any(
        feature.kind == "face"
        and float(feature.params["centre"][0]) > 20.0
        and float(feature.params["centre"][2]) > 3.0
        for feature in found.values()
    )


def test_close_irregular_ribs_do_not_become_a_pattern() -> None:
    """Nahe Nachbarn belegen noch keine regelmäßige Teilung."""
    body = plate()
    ribs = []
    for x in (-14.0, -9.8, -6.4, -2.0, 1.3, 6.0, 9.4, 14.0):
        rib = trimesh.creation.box(extents=(2.0, 20.0, 1.2))
        rib.apply_translation((x, 0.0, 3.0))
        ribs.append(rib)
    tool = MeshData.of(trimesh.util.concatenate(ribs))
    out = boolean("union", [body, tool], quality="fine", cancelled=NeverCancelled())
    assert "pattern" not in kinds(detect(out.mesh))


def test_separate_rib_fields_can_have_different_pitch_with_the_same_cell_width() -> None:
    """Gleiche Zellbreite bindet zwei getrennte Teilungen nicht an einen Median."""
    body = MeshData.of(trimesh.creation.box(extents=(90.0, 40.0, 6.0)))
    ribs = []
    for start, pitch in ((-37.0, 4.0), (8.0, 5.0)):
        for index in range(7):
            rib = trimesh.creation.box(extents=(2.0, 20.0, 1.2))
            rib.apply_translation((start + index * pitch, 0.0, 3.0))
            ribs.append(rib)
    out = boolean(
        "union",
        [body, MeshData.of(trimesh.util.concatenate(ribs))],
        quality="fine",
        cancelled=NeverCancelled(),
    )
    fields = [feature for feature in detect(out.mesh).values() if feature.kind == "pattern"]
    assert len(fields) == 2
    assert sorted(float(feature.params["pitch"]) for feature in fields) == pytest.approx([4.0, 5.0])


def test_one_missing_rib_does_not_split_an_imported_field() -> None:
    """Eine ausgelassene Zelle bleibt der erlaubte Ausreißer im Gitter."""
    body = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 6.0)))
    ribs = []
    for index in range(13):
        if index == 6:
            continue
        rib = trimesh.creation.box(extents=(2.0, 20.0, 1.2))
        rib.apply_translation(((index - 6) * 4.0, 0.0, 3.0))
        ribs.append(rib)
    out = boolean(
        "union",
        [body, MeshData.of(trimesh.util.concatenate(ribs))],
        quality="fine",
        cancelled=NeverCancelled(),
    )
    field = only_pattern(detect(out.mesh))
    assert field.params["count"] == 12
    assert float(field.params["pitch"]) == pytest.approx(4.0)


@pytest.mark.parametrize("count", [6, 12])
def test_slender_triangular_openings_are_not_waves(count: int) -> None:
    """Längliche Dreiecke im Ornament belegen keinen Rippen- oder Wellenquerschnitt."""
    from shapely.geometry import Polygon

    body = MeshData.of(trimesh.creation.box(extents=(count * 6.0 + 4.0, 12.0, 6.0)))
    triangles = []
    for index in range(count):
        triangle = trimesh.creation.extrude_polygon(
            Polygon(((0.0, 0.0), (1.0, 0.0), (0.0, 3.0))), height=8.0
        )
        triangle.apply_translation(((index - (count - 1) / 2.0) * 6.0, -1.5, -4.0))
        triangles.append(triangle)
    out = boolean(
        "difference",
        [body, MeshData.of(trimesh.util.concatenate(triangles))],
        quality="fine",
        cancelled=NeverCancelled(),
    )
    fields = [feature for feature in detect(out.mesh).values() if feature.kind == "pattern"]
    if count < patterns.MIN_CELLS:
        assert fields == []
    else:
        assert len(fields) == 1
        assert fields[0].params["style"] == "other"
        assert fields[0].params["count"] == count
