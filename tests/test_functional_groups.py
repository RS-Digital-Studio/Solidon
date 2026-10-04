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
from collections.abc import Callable

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


def test_a_trough_changes_only_over_two_flat_walls_and_says_so_beforehand() -> None:
    """Ein offener Kanal ändert sich über genau zwei ebene Wände — und das Fenster weiß es vorher.

    Am 1x1-tray aus dem Audit hat der Kanal eine dritte, kleine Wand am Ende;
    das Merkmalfenster bot *Kammer ändern* an, und erst die Operation sagte ab
    (``chamber_ops._trough``). Dieselbe Frage steht jetzt in
    ``reason_against_group``: an der U-Rinne frei, mit einer dritten Wand oder
    einer gekrümmten Wand die Absage der Operation.
    """
    from app.core.perceive.groups import TROUGH_WALLS, reason_against_group

    trough = _minus(
        _box((100.0, 30.0, 20.0), (0.0, 0.0, 10.0)), _box((120.0, 26.0, 20.0), (0.0, 0.0, 12.0))
    )
    features = detect(trough)
    channel = _only(_groups(trough), "channel")
    assert reason_against_group(channel, features) is None
    third = next(name for name in features if name not in channel.members)
    stepped = dataclasses.replace(channel, roles=(*channel.roles, (third, "wall")))
    assert reason_against_group(stepped, features) == str(TROUGH_WALLS)
    wall = next(member for member, role in channel.roles if role == "wall")
    curved = {**features, wall: dataclasses.replace(features[wall], kind="curved_face")}
    assert reason_against_group(channel, curved) == str(TROUGH_WALLS)


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


def _two_sockets() -> MeshData:
    return _minus(
        _box((60.0, 30.0, 30.0), (0.0, 0.0, 15.0)),
        _cylinder(4.0, 20.0, (-15.0, 0.0, 20.0)),
        _cylinder(4.0, 20.0, (15.0, 0.0, 20.0)),
    )


@pytest.mark.parametrize(
    ("build", "kind"), [(lambda: _eyes(6.0), "hinge"), (_two_sockets, "socket")]
)
def test_the_bores_of_a_hinge_or_a_socket_change_together(
    build: Callable[[], MeshData], kind: str
) -> None:
    """§7: Scharnier „Größe gemeinsam ändern“, Steckaufnahme „Gegenstückmaß gemeinsam einstellen“.

    Die Bohrungen einer solchen Gruppe sind für *Bohrung ändern* und
    *Verschieben* gleichartig — das Merkmalfenster bietet „Auf alle
    gleichartigen anwenden“ an, und eine Handlung ändert sie zusammen.
    """
    from app.core.perceive.relations import alike_for_actions

    mesh = build()
    features = detect(mesh)
    group = _only(functional_groups(features, mesh), kind)
    bores = sorted(member for member in group.members if features[member].kind == "hole")
    assert len(bores) == 2
    for action in ("resize_hole", "move_feature"):
        alike = alike_for_actions([action], bores[0], features, mesh)[0]
        assert {member.target for member in alike.members} >= set(bores), action


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


def test_struts_far_along_the_axis_of_a_bore_are_no_closure() -> None:
    """Ein Verschluss sitzt am Rundkörper, nicht irgendwo auf seiner Achse.

    Am Eiffelturm aus dem Korpus steht unter der Spitzenbohrung Ø 3,4 ein
    Kreuz aus vier dünnen Streben: je zwei Flächen auf r ≈ 1,3, um 90 Grad
    versetzt. An der Bohrung wären sie eine Rastung; 10 mm darunter sind
    sie keine. Gebaut aus Merkmalen, damit nur die Lage entlang der Achse
    sich ändert.
    """
    from app.core.types import Feature

    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 30.0), "diameter": 3.4, "depth": 4.0},
    )

    def struts(height: float) -> dict[str, Feature]:
        found: dict[str, Feature] = {"hole_1": bore}
        for index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
            turn = math.radians(angle)
            out = (math.cos(turn), math.sin(turn))
            side = (-out[1], out[0])
            for sign in (1.0, -1.0):
                name = f"face_{2 * index + (1 if sign > 0 else 2)}"
                found[name] = Feature(
                    id=name,
                    kind="face",
                    provenance="detected",
                    params={
                        "centre": (
                            1.3 * out[0] + 0.15 * sign * side[0],
                            1.3 * out[1] + 0.15 * sign * side[1],
                            height,
                        ),
                        "normal": (sign * side[0], sign * side[1], 0.0),
                        "area": 1.5,
                    },
                )
        return found

    at_the_bore = [g for g in functional_groups(struts(30.0), None) if g.kind == "closure"]
    assert [(group.variant, group.count) for group in at_the_bore] == [("detent", 4)]
    below = [g for g in functional_groups(struts(18.0), None) if g.kind == "closure"]
    assert below == []


def test_two_facets_of_one_wall_are_no_station() -> None:
    """Eine Stellung trägt verschieden gerichtete Flächen, nicht zwei Facetten einer Wand.

    Am Mini-Golf-Schläger aus dem Korpus lagen an vier Stellen je zwei
    benachbarte Streifen derselben 200 mm langen Wand, 3,2 Grad gegeneinander
    geneigt (Kosinus 0,9985), auf r ≈ 11,1 um den Zapfen Ø 25 — und galten
    als Rastung. Gebaut aus Merkmalen, damit sich nur die Richtung der
    zweiten Fläche ändert: um 90 Grad weiter gedreht ist sie eine Flanke, und
    dieselben vier Stellungen sind eine Rastung.
    """
    from app.core.types import Feature

    pin = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        params={
            "axis": (0.0, 0.0, 1.0),
            "centre": (0.0, 0.0, 10.0),
            "diameter": 25.0,
            "depth": 20.0,
        },
    )

    def stations(turn: float) -> dict[str, Feature]:
        found: dict[str, Feature] = {"pin_1": pin}
        for index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
            # Je Stellung zwei Flächen 3,2 Grad auseinander, ihre Normalen
            # 120 Grad gegen die eigene Lage gedreht wie am Schläger.
            for second, (offset, facing) in enumerate(((0.0, 120.0), (3.2, 120.0 + turn))):
                where = math.radians(angle + offset)
                towards = math.radians(angle + offset + facing)
                name = f"face_{2 * index + second + 1}"
                found[name] = Feature(
                    id=name,
                    kind="face",
                    provenance="detected",
                    params={
                        "centre": (11.14 * math.cos(where), 11.14 * math.sin(where), 10.0),
                        "normal": (math.cos(towards), math.sin(towards), 0.0),
                        "area": 40.0,
                    },
                )
        return found

    facets = [g for g in functional_groups(stations(0.0), None) if g.kind == "closure"]
    assert facets == []
    flanks = [g for g in functional_groups(stations(90.0), None) if g.kind == "closure"]
    assert [(group.variant, group.count) for group in flanks] == [("detent", 4)]


def _tube_with_round_notches(spots: tuple[tuple[float, float, float], ...]) -> MeshData:
    """Ein Rohr r 22 / 16,4, 18 hoch, mit Mulden R 1,1 im Innenmantel.

    ``spots`` nennt je Mulde Winkel, Höhe ihrer Mitte und Länge entlang der Achse.
    """
    tube = _minus(
        _cylinder(22.0, 18.0, (0.0, 0.0, 9.0), sections=192),
        _cylinder(16.4, 20.0, (0.0, 0.0, 9.0), sections=192),
    )
    notches = [
        _cylinder(
            1.1,
            length,
            (16.4 * math.cos(math.radians(angle)), 16.4 * math.sin(math.radians(angle)), height),
        )
        for angle, height, length in spots
    ]
    return _minus(tube, *notches)


def test_round_notches_above_each_other_are_one_position_and_no_detent() -> None:
    """Eine Stellung ist ein Winkel: Mulden übereinander am selben Winkel zählen einmal.

    Am Besenhalter aus dem Korpus standen drei Rundungen bei 90 Grad
    übereinander und galten als Rastung mit drei Stellungen. Dieselben drei
    Mulden auf drei Winkel verteilt bleiben eine (Gegenprobe).
    """
    stacked = _tube_with_round_notches(((90.0, 3.0, 4.0), (90.0, 9.0, 4.0), (90.0, 15.0, 4.0)))
    assert all(group.kind != "closure" for group in _groups(stacked))
    spread = _tube_with_round_notches(((0.0, 9.0, 18.0), (120.0, 9.0, 18.0), (240.0, 9.0, 18.0)))
    closure = _only(_groups(spread), "closure")
    assert (closure.variant, closure.count) == ("detent", 3)


def _disc_with_blocks(places: tuple[tuple[float, float], ...]) -> MeshData:
    """Eine Scheibe r 16, 3 hoch, mit Mittelloch r 3 und Klötzen 2 × 2 × 1 oben auf.

    ``places`` nennt je Klotz den Abstand seiner Mitte zur Achse und den Winkel.
    """
    disc = _minus(
        _cylinder(16.0, 3.0, (0.0, 0.0, 1.5), sections=96),
        _cylinder(3.0, 5.0, (0.0, 0.0, 1.5), sections=48),
    )
    blocks = [_around(_box((2.0, 2.0, 1.0), (radius, 0.0, 3.5)), angle) for radius, angle in places]
    return _plus(disc, *blocks)


def _closures_by_part(mesh: MeshData) -> list[tuple[int, str, int, float]]:
    """Je Verschluss: das Teil (nach x in 60er-Schritten), Variante, Stellungen, Radius."""
    features = detect(mesh)
    found = []
    for group in functional_groups(features, mesh):
        if group.kind != "closure":
            continue
        centre = features[group.anchor].params["centre"]
        found.append(
            (
                round(float(centre[0]) / 60.0),
                group.variant,
                group.count,
                round(group.measure("radius") or 0.0, 1),
            )
        )
    return sorted(found)


def test_a_print_plate_does_not_change_the_closures_of_its_parts() -> None:
    """Ein Teil auf einer großen Platte bekommt denselben Verschluss wie allein.

    Die Toleranz eines Rings misst sich an seinem Rundkörper, nicht an der
    Platte: Auf dem Gewürzdeckel-Druckbett (zwölf Deckel, 300 mm Diagonale)
    standen die Rastfedern der Drehscheibe 5 mm neben der Achse unter der
    Plattentoleranz und fielen weg, und Klötze auf 6,5 bis 14 mm Abstand
    lagen innerhalb von viermal 2,2 mm „auf einem Radius“ — eine erfundene
    Rastung. Allein: die Federn eine Rastung, die gestaffelten Klötze keine.
    """
    springs = _disc_with_blocks(((5.0, 0.0), (5.0, 120.0), (5.0, 240.0)))
    staggered = _disc_with_blocks(((6.5, 0.0), (9.0, 90.0), (11.5, 180.0), (14.0, 270.0)))
    alone = [
        (index, *entry[1:])
        for index, part in enumerate((springs, staggered))
        for entry in _closures_by_part(part)
    ]
    assert alone == [(0, "detent", 3, 5.0)]

    pieces = [springs.raw.copy(), staggered.raw.copy()]
    pieces[1].apply_translation((60.0, 0.0, 0.0))
    # Ein drittes Teil weit draußen macht die Platte groß, ohne Verschluss.
    far = trimesh.creation.box(extents=(20.0, 20.0, 2.0))
    far.apply_translation((300.0, 280.0, 1.0))
    plate = MeshData.of(trimesh.util.concatenate([*pieces, far]))
    assert float(np.linalg.norm(plate.bounds.size)) > 400.0
    assert _closures_by_part(plate) == alone


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
