"""Funktionale Gruppen: Kammer, Nut, Kanal, Gewinde, Verschluss, Scharnier, Schrift, Aufnahme.

Jede Gruppe wird an einem Körper geprüft, dessen Soll aus seiner Konstruktion
folgt (Bauplan §21, Dateiaudit §7). Die Gegenproben stehen daneben: Was einer
Gruppe nur ähnlich sieht — ein Block, ein Schraubenloch, vier gleiche Füße,
ein gespiegelter Griffsteg —, bekommt keine.

Die echten Auditdateien (Kammer am 1x1-bin, Bajonett am Kartuschenkäfig,
Schrift am Drillholder …) liegen außerhalb des Repositorys; ihr Lauf steht im
Bericht von RM-184 (Sonde ``groups-corpus``). Hier stehen die Formen, die
denselben Befund an nachvollziehbarer Geometrie zeigen.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.perceive.groups import (
    GROUP_KINDS,
    FunctionalGroup,
    GroupEvidence,
    evidence_texts,
    functional_groups,
    functional_title,
    group_of,
    numbered_titles,
)
from tests.helpers import walled_bin


def _box(size: tuple[float, float, float], centre: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.box(extents=size)
    body.apply_translation(centre)
    return MeshData.of(body)


def _cylinder(
    radius: float,
    height: float,
    centre: tuple[float, float, float],
    axis: str = "z",
    sections: int = 48,
) -> MeshData:
    body = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    if axis == "x":
        body.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif axis == "y":
        body.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    body.apply_translation(centre)
    return MeshData.of(body)


def _minus(body: MeshData, *tools: MeshData) -> MeshData:
    for tool in tools:
        body = boolean("difference", [body, tool]).mesh
    return body


def _plus(body: MeshData, *parts: MeshData) -> MeshData:
    for part in parts:
        body = boolean("union", [body, part]).mesh
    return body


def _groups(mesh: MeshData) -> tuple[FunctionalGroup, ...]:
    return functional_groups(detect(mesh), mesh)


def _only(groups: tuple[FunctionalGroup, ...], kind: str) -> FunctionalGroup:
    found = [group for group in groups if group.kind == kind]
    assert len(found) == 1, [(group.kind, group.variant) for group in groups]
    return found[0]


def _bin() -> MeshData:
    """Ein Kasten 40 × 30 × 20 mit 2 mm Wand und Boden, oben offen."""
    return walled_bin()


# --- Kammer, Nut, Kanal -----------------------------------------------------


def test_an_open_box_is_a_closed_chamber_with_its_inner_measures() -> None:
    """Boden und vier Wände: Innenmaß 36 × 26, Tiefe 18 — aus der Konstruktion."""
    chamber = _only(_groups(_bin()), "chamber")
    assert chamber.variant == "closed"
    assert chamber.planar_rim
    sizes = sorted((chamber.measure("width") or 0.0, chamber.measure("length") or 0.0))
    assert sizes == pytest.approx([26.0, 36.0], abs=1e-6)
    assert chamber.measure("depth") == pytest.approx(18.0, abs=1e-6)
    roles = dict(chamber.roles)
    assert roles[chamber.anchor] == "floor"
    assert sum(1 for role in roles.values() if role == "wall") == 4


def test_a_notch_in_the_rim_keeps_the_chamber_but_says_the_rim_is_open() -> None:
    """Eine Aussparung im Rand (Auffangwanne, Fall 267) ist keine geschlossene Kammer."""
    notched = _minus(_bin(), _box((10.0, 4.0, 10.0), (0.0, 14.0, 20.0)))
    chamber = _only(_groups(notched), "chamber")
    assert chamber.variant == "open_rim"
    assert not chamber.planar_rim


def test_a_u_profile_open_at_both_ends_is_a_channel() -> None:
    """Zwei Wände gegenüber, offene Enden: ein Kanal, 26 breit, 18 tief, 100 lang."""
    trough = _minus(
        _box((100.0, 30.0, 20.0), (0.0, 0.0, 10.0)), _box((120.0, 26.0, 20.0), (0.0, 0.0, 12.0))
    )
    channel = _only(_groups(trough), "channel")
    assert channel.variant == "trough"
    assert channel.measure("width") == pytest.approx(26.0, abs=1e-6)
    assert channel.measure("depth") == pytest.approx(18.0, abs=1e-6)
    assert channel.measure("length") == pytest.approx(100.0, abs=1e-6)


def test_a_ring_groove_is_a_groove_with_its_width() -> None:
    """Eine umlaufende Nut, Ring 20 bis 24 mm, 3 mm tief: Breite 2A/U = 4."""
    plate = _box((60.0, 60.0, 10.0), (0.0, 0.0, 5.0))
    ring = boolean(
        "difference",
        [
            _cylinder(24.0, 3.0, (0.0, 0.0, 8.5), sections=96),
            _cylinder(20.0, 3.2, (0.0, 0.0, 8.5), sections=96),
        ],
    ).mesh
    groove = _only(_groups(_minus(plate, ring)), "channel")
    assert groove.variant == "groove"
    assert groove.measure("depth") == pytest.approx(3.0, abs=1e-6)
    assert groove.measure("width") == pytest.approx(4.0, abs=0.02)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(lambda: _box((40.0, 30.0, 20.0), (0.0, 0.0, 10.0)), id="block"),
        pytest.param(
            lambda: _minus(
                _box((40.0, 30.0, 10.0), (0.0, 0.0, 5.0)), _cylinder(5.0, 20.0, (0.0, 0.0, 5.0))
            ),
            id="through-hole",
        ),
        pytest.param(
            lambda: _minus(
                _box((40.0, 30.0, 10.0), (0.0, 0.0, 5.0)), _cylinder(5.0, 10.0, (0.0, 0.0, 10.0))
            ),
            id="shallow-blind-hole",
        ),
        pytest.param(
            lambda: _plus(
                _box((40.0, 30.0, 10.0), (0.0, 0.0, 5.0)),
                _box((20.0, 30.0, 5.0), (10.0, 0.0, 12.5)),
            ),
            id="step",
        ),
    ],
)
def test_what_only_looks_like_a_pocket_gets_no_group(body: object) -> None:
    """Block, Durchgang, flaches Sackloch und Stufe tragen keine Gruppe."""
    assert callable(body)
    assert _groups(body()) == ()


def test_a_slot_through_a_wall_is_not_a_channel() -> None:
    """Ein Schlitz durch eine Wand hat eine Gegenfläche über jeder Flanke (Fall 162)."""
    wall = _minus(
        _box((40.0, 4.0, 30.0), (0.0, 0.0, 15.0)), _box((3.0, 10.0, 20.0), (0.0, 0.0, 15.0))
    )
    assert [group.kind for group in _groups(wall)] == []


# --- Steckaufnahme ------------------------------------------------------------


def test_deep_blind_bores_of_one_size_are_one_socket_group() -> None:
    """Zwei Sacklöcher Ø 8 auf 20 mm: eine Gruppe, zwei Aufnahmen, zwei Anschläge."""
    block = _minus(
        _box((60.0, 30.0, 30.0), (0.0, 0.0, 15.0)),
        _cylinder(4.0, 20.0, (-15.0, 0.0, 20.0)),
        _cylinder(4.0, 20.0, (15.0, 0.0, 20.0)),
    )
    socket = _only(_groups(block), "socket")
    assert socket.count == 2
    assert socket.measure("diameter") == pytest.approx(8.0, abs=0.05)
    assert socket.measure("depth") == pytest.approx(20.0, abs=1e-6)
    roles = [role for _member, role in socket.roles]
    assert roles.count("socket") == 2
    assert roles.count("stop") == 2


def test_a_screw_hole_is_no_socket() -> None:
    """Ø 4,5 auf 5 mm ist ein Schraubenloch (Wasserfalldeckel), keine Steckaufnahme."""
    block = _minus(_box((30.0, 30.0, 10.0), (0.0, 0.0, 5.0)), _cylinder(2.25, 5.0, (0.0, 0.0, 7.5)))
    assert all(group.kind != "socket" for group in _groups(block))


# --- Scharnier ----------------------------------------------------------------


def _eyes(gap: float) -> MeshData:
    """Eine Platte mit zwei Augen auf der x-Achse, Bohrung Ø 3, Spalt dazwischen."""
    plate = _box((40.0, 20.0, 3.0), (0.0, 0.0, 1.5))
    left = _cylinder(4.0, 8.0, (-(gap / 2.0 + 4.0), 12.0, 4.0), axis="x")
    right = _cylinder(4.0, 8.0, (gap / 2.0 + 4.0, 12.0, 4.0), axis="x")
    lugs = (
        _box((8.0, 6.0, 4.0), (-(gap / 2.0 + 4.0), 9.0, 2.0)),
        _box((8.0, 6.0, 4.0), (gap / 2.0 + 4.0, 9.0, 2.0)),
    )
    body = _plus(plate, left, right, *lugs)
    return _minus(body, _cylinder(1.5, 60.0, (0.0, 12.0, 4.0), axis="x"))


def test_two_eyes_on_one_axis_are_a_hinge_with_their_gap() -> None:
    """Zwei Augen, eine Bohrung Ø 3 auf einer Achse, 6 mm Spalt — Glasdeckel, Fall 149."""
    hinge = _only(_groups(_eyes(6.0)), "hinge")
    assert hinge.variant == "axis"
    assert hinge.count == 2
    assert hinge.measure("diameter") == pytest.approx(3.0, abs=0.05)
    assert hinge.measure("gap") == pytest.approx(6.0, abs=1e-6)


def test_a_bolt_hole_through_two_walls_is_no_hinge() -> None:
    """Ein U-Bügel, die Schraube durch beide Schenkel: zwei Löcher auf einer Achse, kein Knöchel.

    Die Gegenprobe zu den Augen darüber — so lagen die Klemmschelle (Ø 5,5 über
    den Klemmspalt) und die Lüftungslöcher des Filterballs im Korpus.
    """
    base = _box((30.0, 20.0, 3.0), (0.0, 0.0, 1.5))
    legs = (_box((3.0, 20.0, 20.0), (-10.0, 0.0, 11.0)), _box((3.0, 20.0, 20.0), (10.0, 0.0, 11.0)))
    bracket = _minus(_plus(base, *legs), _cylinder(1.5, 40.0, (0.0, 0.0, 14.0), axis="x"))
    assert all(group.kind != "hinge" for group in _groups(bracket))


# --- Gewinde mit Einlauf ------------------------------------------------------


def test_a_thread_on_a_shoulder_carries_the_shoulder() -> None:
    """Ein Gewinde M6 auf einem Bund: die Schulter am Ende gehört zur Gruppe."""
    from app.core.knowledge.parts import build

    built = build.threaded(6.0, 1.0, 8.0)
    assert isinstance(built, MeshData)
    rod = MeshData(
        raw=trimesh.Trimesh(
            vertices=np.asarray(built.raw.vertices), faces=np.asarray(built.raw.faces)
        )
    )
    low = float(rod.bounds.minimum[2])
    body = _plus(rod, _cylinder(6.0, 4.0, (0.0, 0.0, low - 2.0 + 0.01), sections=64))
    thread = _only(_groups(body), "thread")
    assert thread.variant == "outer"
    assert thread.measure("pitch") == pytest.approx(1.0, abs=1e-3)
    assert "shoulder" in {role for _member, role in thread.roles}


# --- Bajonett und Rastung -----------------------------------------------------


def _ring() -> MeshData:
    return _minus(
        _cylinder(20.0, 10.0, (0.0, 0.0, 5.0), sections=96),
        _cylinder(15.0, 12.0, (0.0, 0.0, 5.0), sections=96),
    )


def _around(part: MeshData, degrees: float) -> MeshData:
    body = part.raw.copy()
    body.apply_transform(trimesh.transformations.rotation_matrix(math.radians(degrees), [0, 0, 1]))
    return MeshData.of(body)


def test_three_lugs_on_a_ring_are_a_bayonet() -> None:
    """Drei gleiche Nocken außen am Ring, 120 Grad auseinander (Kartuschendeckel, Fall 159)."""
    lug = _box((4.0, 6.0, 3.0), (21.5, 0.0, 6.0))
    body = _plus(_ring(), *(_around(lug, angle) for angle in (0.0, 120.0, 240.0)))
    closure = _only(_groups(body), "closure")
    assert closure.variant == "bayonet"
    assert closure.count == 3
    assert closure.measure("spacing") == pytest.approx(120.0, abs=0.5)


def test_notches_at_uneven_positions_are_a_detent() -> None:
    """Drei Mulden bei 0, 122,5 und 240 Grad (Gewürzdeckel, Fall 175): Rastung ohne Teilung."""
    notch = _box((3.0, 3.0, 2.0), (17.5, 0.0, 10.0))
    body = _minus(_ring(), *(_around(notch, angle) for angle in (0.0, 122.5, 240.0)))
    closure = _only(_groups(body), "closure")
    assert closure.variant == "detent"
    assert closure.count == 3
    assert closure.measure("spacing") is None


def test_two_mirrored_halves_are_no_closure() -> None:
    """Zwei gleiche Stege gegenüber hat jedes gespiegelte Teil — kein Verschluss."""
    lug = _box((4.0, 6.0, 3.0), (21.5, 0.0, 6.0))
    body = _plus(_ring(), lug, _around(lug, 180.0))
    assert all(group.kind != "closure" for group in _groups(body))


# --- Schrift ------------------------------------------------------------------


def _letter(index: float, x: float, base: float, height: float) -> MeshData:
    """Ein „L“ als Buchstabe: Stamm und Fuß, je Nummer anders groß.

    Fläche zu Hüllfläche liegt um 0,6 — so füllt ein Buchstabe seine Hülle,
    eine Noppe dagegen ganz (``GLYPH_SOLIDITY``).
    """
    stem = _box((1.0 + 0.2 * index, 6.0 + index, height), (x, 0.0, base + height / 2.0))
    foot = _box(
        (3.0 + 0.5 * index, 1.0, height),
        (
            x + (3.0 + 0.5 * index) / 2.0 - (1.0 + 0.2 * index) / 2.0,
            -(3.0 + index / 2.0) + 0.5,
            base + height / 2.0,
        ),
    )
    return _plus(stem, foot)


def test_raised_letters_of_different_sizes_are_one_lettering() -> None:
    """Sechs verschiedene Buchstaben 0,7 mm über der Platte (WC-Schild, Fall 247)."""
    plate = _box((120.0, 40.0, 3.0), (0.0, 0.0, 1.5))
    letters = [_letter(index, -45.0 + 16.0 * index, 3.0, 0.7) for index in range(6)]
    lettering = _only(_groups(_plus(plate, *letters)), "lettering")
    assert lettering.variant == "raised"
    assert lettering.count == 6
    assert lettering.measure("height") == pytest.approx(0.7, abs=1e-6)


def test_a_grid_of_equal_crosses_is_no_lettering() -> None:
    """Sechs gleiche Kreuze auf einer Platte: geformt wie Buchstaben, aber eine Form.

    So lag die Spielplatte im Korpus (Carcassonne-Raster); Schrift hat viele
    Formen (``GLYPH_SHAPES``).
    """
    plate = _box((120.0, 40.0, 3.0), (0.0, 0.0, 1.5))
    crosses = [
        _plus(
            _box((6.0, 1.5, 1.0), (-45.0 + 16.0 * index, 0.0, 3.5)),
            _box((1.5, 6.0, 1.0), (-45.0 + 16.0 * index, 0.0, 3.5)),
        )
        for index in range(6)
    ]
    assert all(group.kind != "lettering" for group in _groups(_plus(plate, *crosses)))


def test_equal_feet_are_no_lettering() -> None:
    """Vier gleiche Füße auf einer Platte sind keine Schrift."""
    plate = _box((60.0, 60.0, 3.0), (0.0, 0.0, 1.5))
    feet = [_box((6.0, 6.0, 2.0), (x, y, 4.0)) for x in (-20.0, 20.0) for y in (-20.0, 20.0)]
    body = _plus(plate, *feet)
    assert all(group.kind != "lettering" for group in _groups(body))


def test_separate_flat_parts_on_a_carrier_are_lettering() -> None:
    """Eigene flache Buchstaben auf einer Trägerplatte (Drillholder, Fall 303)."""
    plate = _box((120.0, 30.0, 4.0), (0.0, 0.0, 2.0))
    letters = [_letter(index, -45.0 + 16.0 * index, 4.0, 0.5).raw for index in range(6)]
    combined = trimesh.util.concatenate([plate.raw, *letters])
    lettering = _only(_groups(MeshData.of(combined)), "lettering")
    assert lettering.variant == "separate"
    assert lettering.count == 6
    assert lettering.measure("height") == pytest.approx(0.5, abs=1e-6)


def test_equal_separate_parts_are_no_lettering() -> None:
    """Zehn gleiche Clips auf der Platte sind ein Satz Teile (Korpus: Filamentclips)."""
    plate = _box((120.0, 30.0, 4.0), (0.0, 0.0, 2.0))
    clips = [_letter(2, -45.0 + 16.0 * index, 4.0, 0.5).raw for index in range(6)]
    combined = trimesh.util.concatenate([plate.raw, *clips])
    assert all(group.kind != "lettering" for group in _groups(MeshData.of(combined)))


# --- Verträge -----------------------------------------------------------------


def test_groups_do_not_change_the_features() -> None:
    """Eine Gruppe liest die Merkmalsliste nur — Namen, Arten und Dreiecke bleiben."""
    mesh = _bin()
    features = detect(mesh)
    before = {name: dataclasses.replace(feature) for name, feature in features.items()}
    functional_groups(features, mesh)
    assert features == before


def test_a_moved_copy_has_the_same_groups() -> None:
    """Verschiebung ändert Lage, nicht Art und Maß (Audit §4: verschiebungsstabil)."""
    mesh = _bin()
    moved = mesh.raw.copy()
    moved.apply_translation((123.4, -56.7, 8.9))
    first = _groups(mesh)
    second = _groups(MeshData.of(moved))
    assert [(group.kind, group.variant) for group in first] == [
        (group.kind, group.variant) for group in second
    ]
    for one, other in zip(first, second, strict=True):
        for a, b in zip(one.measures, other.measures, strict=True):
            assert a.name == b.name
            assert a.value == pytest.approx(b.value, abs=1e-6)


def test_generated_features_belong_to_their_part_not_to_a_group() -> None:
    """Was ein Baustein gebaut hat, steht unter seinem Schritt — keine zweite Gruppe."""
    mesh = _bin()
    features = {
        name: dataclasses.replace(feature, provenance="generated", created_by=3)
        for name, feature in detect(mesh).items()
    }
    assert functional_groups(features, mesh) == ()


def test_every_evidence_and_title_has_a_sentence() -> None:
    """Jeder Nachweis hat seinen Satz; jede Art einen Namen im Baum."""
    from typing import get_args

    assert set(evidence_texts()) == set(get_args(GroupEvidence))
    assert GROUP_KINDS == (
        "chamber",
        "channel",
        "thread",
        "closure",
        "hinge",
        "lettering",
        "socket",
    )
    chamber = _only(_groups(_bin()), "chamber")
    assert functional_title(chamber) == "Kammer"
    assert numbered_titles((chamber, dataclasses.replace(chamber, anchor="face_99"))) == {
        chamber.key: "Kammer 1",
        "chamber:face_99": "Kammer 2",
    }
    assert group_of(chamber.anchor, (chamber,)) is chamber
    assert group_of("nothing", (chamber,)) is None


# --- Der Referenzkorpus -------------------------------------------------------
#
# ``tests/data/meshes/recognition_*.npz`` sind die eigenen Nachbauten der
# Auditfälle (``data/make_recognition_corpus.py``); die Sollwerte folgen aus
# ihrer Konstruktion dort.


def _corpus(name: str, *, internal: bool = False) -> MeshData:
    """Ein Korpusnetz ohne Neubau oder STL-Rundung."""
    from pathlib import Path

    path = Path(__file__).parent / "data" / "meshes" / f"recognition_{name}.npz"
    with np.load(path, allow_pickle=False) as data:
        prefix = "inner_" if internal else ""
        return MeshData(
            raw=trimesh.Trimesh(data[f"{prefix}vertices"], data[f"{prefix}faces"], process=False)
        )


def _measures(group: FunctionalGroup) -> dict[str, float]:
    return {entry.name: entry.value for entry in group.measures}


def test_the_cage_of_the_corpus_is_a_chamber_with_pierced_walls() -> None:
    """Schachtel 80 × 80 × 20 minus 72 × 72 ab z = 2: innen 72 × 72 × 18.

    Drei Tunnel durch die Wände (5 × 4 mm bei z = 8 bis 12) durchbrechen sie —
    die Gruppe heißt deshalb Tasche mit offenem Rand, und *Kammer ändern* sagt
    ab, statt um die Tunnel herum zu strecken.
    """
    chamber = _only(_groups(_corpus("bayonet_cage")), "chamber")
    assert chamber.variant == "open_rim"
    measures = _measures(chamber)
    assert measures["width"] == pytest.approx(72.0, abs=1e-6)
    assert measures["length"] == pytest.approx(72.0, abs=1e-6)
    assert measures["depth"] == pytest.approx(18.0, abs=1e-6)


def test_the_lid_of_the_corpus_carries_a_bayonet_of_three_lugs() -> None:
    """Drei Nocken 6 × 3,8 × 0,6 auf r = 30 bei 0°, 120° und 240°."""
    closure = _only(_groups(_corpus("bayonet_lid")), "closure")
    assert closure.variant == "bayonet"
    assert closure.count == 3
    measures = _measures(closure)
    assert measures["spacing"] == pytest.approx(120.0, abs=1e-6)
    # Flächengewichtete Lage der Nockenflächen: Ober- und Unterseite auf r = 30,
    # die Seiten auf r = 27, 33 und √(30² + 1,9²) — gemittelt knapp über 30.
    assert measures["radius"] == pytest.approx(30.0, abs=0.1)


@pytest.mark.parametrize(
    ("internal", "variant", "diameter", "turns"),
    [(False, "outer", 34.0, 4.0), (True, "inner", 34.9, 3.0)],
)
def test_the_short_threads_of_the_corpus_are_threads_with_their_turns(
    internal: bool, variant: str, diameter: float, turns: float
) -> None:
    """Außen Ø 34 über vier Windungen, innen Ø 34,9 über drei, Steigung 3,5."""
    thread = _only(_groups(_corpus("short_thread", internal=internal)), "thread")
    assert thread.variant == variant
    measures = _measures(thread)
    assert measures["diameter"] == pytest.approx(diameter, abs=1e-6)
    assert measures["pitch"] == pytest.approx(3.5, abs=1e-6)
    assert measures["turns"] == pytest.approx(turns, abs=0.01)


def test_round_notches_in_the_collar_of_the_corpus_are_a_detent() -> None:
    """Drei Mulden R 1,1 auf r = 16 im Innenmantel r = 16,4, alle 120 Grad.

    Der runde Kragen mit Rastmulden des Gewürzdeckels (Audit §7: „ist kein
    Langloch“) — als Gruppe eine Rastung aus der Mittelachse und den drei
    Mulden.
    """
    closure = _only(_groups(_corpus("spice_base")), "closure")
    assert closure.variant == "detent"
    assert closure.count == 3
    measures = _measures(closure)
    assert measures["spacing"] == pytest.approx(120.0, abs=1e-6)
    assert measures["radius"] == pytest.approx(16.0, abs=1e-6)
    assert sorted(role for _member, role in closure.roles) == ["core", "notch", "notch", "notch"]


def test_a_wall_with_a_lip_is_no_group() -> None:
    """Die Wasserfallwand mit Lippe hat weder Boden noch Gegenwand — keine Gruppe."""
    assert _groups(_corpus("waterfall")) == ()
