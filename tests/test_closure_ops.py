"""*Verschluss ändern*: Spiel und Drehweg eines Bajonetts oder einer Rastung als Ganzes (RM-184).

Der Dateiaudit (§7) verlangt für Bajonett und Rastverschluss „Spiel und
Drehweg ändern“. Die Sollwerte folgen aus der Konstruktion:

* Am Bajonettdeckel des Korpus (``data/meshes/recognition_bayonet_lid.npz``)
  stehen drei Nocken mit je zwei Flanken von 6 × 0,5 mm². Mehr Spiel um
  1 mm nimmt je Flanke 0,5 mm weg: 3 × 2 × 3 mm² × 0,5 mm = 9 mm³.
* Das Rohr mit drei L-Wegen (:func:`_ring_with_paths`, gebaut wie der
  Filterkäfig aus dem Audit) hat nur radiale Flanken auf ganzen Graden eines
  360-Ecks: je Stellung Einführwände von 12 und 14 mm², das Ende des
  Drehschlitzes 7 mm², den Anschlag 9 mm² — 42 mm² je Stellung.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data, face_components
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.perceive.groups import (
    NOT_A_CLOSURE,
    FunctionalGroup,
    closure_flanks,
    closure_pairs,
    closure_stops,
    functional_groups,
    reason_against_closure,
    reason_against_play,
)
from app.core.types import Feature
from tests.helpers import feature_operation

#: Wand des Rohrs mit Wegen: innen 37,5, außen 39,5 mm.
INNER, OUTER = 37.5, 39.5


@pytest.fixture(autouse=True)
def operations() -> None:
    load_operations()


def _corpus(name: str) -> MeshData:
    path = Path(__file__).parent / "data" / "meshes" / f"recognition_{name}.npz"
    with np.load(path, allow_pickle=False) as data:
        return MeshData(raw=trimesh.Trimesh(data["vertices"], data["faces"], process=False))


def _closure(mesh: MeshData) -> tuple[FunctionalGroup, dict[str, Feature]]:
    features = detect(mesh)
    closures = [group for group in functional_groups(features, mesh) if group.kind == "closure"]
    assert len(closures) == 1, closures
    return closures[0], features


def _changed(mesh: MeshData, **params: float) -> MeshData:
    group, features = _closure(mesh)
    result = feature_operation(
        "resize_closure",
        mesh,
        dict(features),
        features[group.anchor],
        profiles.make_profile("centauri-carbon-2", "petg"),
        **params,
    )
    return as_mesh_data(result.outputs[0].mesh)


def _sector(start: int, end: int, low: float, high: float) -> MeshData:
    """Ein Tortenstück von ``start`` bis ``end`` Grad, radial bis 42 mm, zwischen zwei Höhen."""
    import shapely.geometry

    points = [(0.0, 0.0)] + [
        (42.0 * math.cos(math.radians(angle)), 42.0 * math.sin(math.radians(angle)))
        for angle in range(start, end + 1)
    ]
    prism = trimesh.creation.extrude_polygon(shapely.geometry.Polygon(points), high - low)
    prism.apply_translation((0.0, 0.0, low))
    return MeshData.of(prism)


def _ring_with_paths(stations: tuple[int, ...] = (0, 120, 240)) -> MeshData:
    """Ein Rohr 20 hoch mit L-Wegen wie am Filterkäfig, alle Flanken radial.

    Je Stellung ein Einführweg von −5° bis +5° (z 13 bis über den Rand) und ein
    Drehschlitz von −19° bis +4° (z 9,5 bis 14). Die linke Einführwand steht
    über dem Drehschlitz (z 14 bis 20, 12 mm²), die rechte von z 13 an (14 mm²),
    das Ende des Drehschlitzes bei +4° darunter (z 9,5 bis 13, 7 mm²), der
    Anschlag bei −19° (z 9,5 bis 14, 9 mm²). Ganze Grade eines 360-Ecks: Jede
    Flanke reicht genau von Ecke zu Ecke des Mantels, 2 mm breit.
    """
    outer = trimesh.creation.cylinder(radius=OUTER, height=20.0, sections=360)
    inner = trimesh.creation.cylinder(radius=INNER, height=22.0, sections=360)
    outer.apply_translation((0.0, 0.0, 10.0))
    inner.apply_translation((0.0, 0.0, 10.0))
    body = boolean("difference", [MeshData.of(outer), MeshData.of(inner)]).mesh
    cutters = []
    for station in stations:
        cutters.append(_sector(station - 5, station + 5, 13.0, 21.0))
        cutters.append(_sector(station - 19, station + 4, 9.5, 14.0))
    return boolean("difference", [body, *cutters]).mesh


def _swept_wall(degrees: float, height: float) -> float:
    """Was ein Anschlag über ``degrees`` ganze Grade des 360-Ecks überstreicht, je Stellung.

    Je Grad ein Trapez zwischen den Sehnen von Innen- und Außenmantel:
    ½ · sin 1° · (R² − r²), mal die Höhe des Drehschlitzes.
    """
    return degrees * 0.5 * math.sin(math.radians(1.0)) * (OUTER * OUTER - INNER * INNER) * height


def _socket(**values: float) -> MeshData:
    """Die Aufnahme des Bajonettbausteins — L-Schlitze aus Quader und Keil."""
    from app.core.knowledge.parts import builtin

    bayonet = builtin.load().get("bayonet")
    chosen: dict[str, float] = {"diameter": 75.0, "turn": 13.0, "play": 0.25, **values}
    return as_mesh_data(bayonet.fn(bayonet.params(kind="socket", **chosen)).mesh)


def _angle(feature: Feature) -> float:
    centre = feature.params["centre"]
    return math.degrees(math.atan2(float(centre[1]), float(centre[0])))


def test_more_play_narrows_every_lug_by_the_same_amount() -> None:
    """Drei Nocken, sechs Flanken, je 0,5 mm nach innen: 9 mm³ weniger, ein dichter Körper."""
    lid = _corpus("bayonet_lid")
    group, features = _closure(lid)
    assert (group.variant, group.count) == ("bayonet", 3)
    assert len(closure_flanks(group, features)) == 6
    changed = _changed(lid, play=1.0)
    assert changed.volume == pytest.approx(lid.volume - 9.0, abs=1e-6)
    assert changed.is_watertight
    assert len(face_components(changed.raw)) == 1
    # Und das Bajonett bleibt eines: drei Stellungen, 120 Grad.
    after, _features = _closure(changed)
    assert (after.variant, after.count) == ("bayonet", 3)
    assert after.measure("spacing") == pytest.approx(120.0, abs=0.5)


def test_less_play_widens_the_lugs() -> None:
    """Negativ heißt strammer: 0,6 mm weniger Spiel setzt 3 × 2 × 3 × 0,3 = 5,4 mm³ an."""
    lid = _corpus("bayonet_lid")
    assert _changed(lid, play=-0.6).volume == pytest.approx(lid.volume + 5.4, abs=1e-6)


def test_lugs_set_into_a_plate_change_without_skins() -> None:
    """Nocken, die in eine Ringplatte eingesetzt sind wie am Kartuschendeckel aus dem Audit.

    Jede Nocke reicht 0,4 mm in die Platte (r = 37,2) und steht über ihr; ihre
    Flanken sind L-förmig. Eingelesen als STL wie der Deckel selbst: Begann das
    Werkzeug bündig an der Flanke, blieb an den gedrehten Nocken eine Haut von
    einem Zehntelmikrometer stehen — als eigenes Stück, und die Operation sagte
    ab. Gefordert: ein dichtes Stück in beide Richtungen, und je Flanke genau,
    was ihr Umriss überstreicht. Unten endet sie am Plattenmantel bei
    x = √(R² − y²) — die Ecke gleitet an ihm entlang —, oben an der Innenseite
    der Nocke bei 36,8 mm. Die Vielecke der Platte (360 Ecken) weichen um
    höchstens R·(1 − cos 0,5°) = 0,0014 mm vom Kreis ab, die STL um float32.
    """
    from app.core.ingest.loader import normalise, read_model

    radius, top, lug_top = 37.2, 2.4, 3.5
    plate = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.cylinder(radius=radius, height=top, sections=360)),
            MeshData.of(trimesh.creation.cylinder(radius=15.0, height=top + 2.0, sections=360)),
        ],
    ).mesh
    plate = MeshData.of(plate.raw.copy().apply_translation((0.0, 0.0, top / 2.0)))
    lugs = []
    for angle in (0.0, 120.0, 240.0):
        lug = trimesh.creation.box(extents=(3.8, 6.0, lug_top))
        lug.apply_translation((38.7, 0.0, lug_top / 2.0))
        lug.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle), [0, 0, 1]))
        lugs.append(MeshData.of(lug))
    built = boolean("union", [plate, *lugs]).mesh
    lid = normalise(read_model(trimesh.exchange.stl.export_stl(built.raw), ".stl"), "mm").mesh
    group, features = _closure(lid)
    assert group.variant == "bayonet"
    assert len(closure_flanks(group, features)) == 6

    def under_the_mantle(y: float) -> float:
        return 0.5 * (
            y * math.sqrt(radius * radius - y * y) + radius * radius * math.asin(y / radius)
        )

    def swept(near: float, far: float) -> float:
        """Was eine Flanke zwischen y = near und y = far überstreicht."""
        lower = top * (40.6 * (far - near) - (under_the_mantle(far) - under_the_mantle(near)))
        return lower + (lug_top - top) * 3.8 * (far - near)

    for play, expected in ((0.6, -6.0 * swept(2.7, 3.0)), (-0.6, 6.0 * swept(3.0, 3.3))):
        changed = _changed(lid, play=play)
        assert changed.volume - lid.volume == pytest.approx(expected, abs=0.01), play
        assert changed.is_watertight, play
        assert len(face_components(changed.raw)) == 1, play


def test_more_play_widens_the_notches_of_a_detent() -> None:
    """Drei Mulden 3 × 3 im Rand eines Rings, 1 mm tief: Ihre Wände rücken je 0,2 mm ins Material.

    Je Mulde zwei Flanken quer zur Umfangsrichtung, je 3 × 1 mm², dazu je
    eine Fläche nach außen und innen, die nicht wandert:
    3 × 2 × 3 mm² × 0,2 mm = 3,6 mm³ weniger.
    """
    ring = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.cylinder(radius=20.0, height=10.0, sections=96)),
            MeshData.of(trimesh.creation.cylinder(radius=15.0, height=12.0, sections=96)),
        ],
    ).mesh
    ring = MeshData.of(ring.raw.copy().apply_translation((0.0, 0.0, 5.0)))
    notches = []
    for angle in (0.0, 122.5, 240.0):
        notch = trimesh.creation.box(extents=(3.0, 3.0, 2.0))
        notch.apply_translation((17.5, 0.0, 10.0))
        notch.apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(angle), [0, 0, 1])
        )
        notches.append(MeshData.of(notch))
    body = boolean("difference", [ring, *notches]).mesh
    group, features = _closure(body)
    assert group.variant == "detent"
    assert closure_stops(group, features, body) == ()
    assert _changed(body, play=0.4).volume == pytest.approx(body.volume - 3.6, abs=1e-6)


def test_the_paths_of_a_ring_take_play_and_turn_together() -> None:
    """Spiel, Drehweg und beides am Rohr mit Wegen — je Stellung genau, was die Konstruktion sagt.

    Spiel 0,6 mm: je Flanke 0,3 mm, 42 mm² je Stellung — 3 × 42 × 0,3 =
    37,8 mm³ weniger. Drehweg 3°: je Anschlag drei Trapeze über 4,5 mm Höhe.
    Beides zusammen ist die Summe: Der Anschlag schwenkt von dort, wo ihn das
    Spiel hingesetzt hat, und überstreicht dieselbe Fläche. Ein ansetzendes
    Werkzeug greift um ``BOOLEAN_OVERLAP`` (0,01 mm) zurück ins Material; dort
    darf es an den Mänteln um deren Sehne über ein 0,01 mm kurzes Stück
    hinausstehen — zusammen unter 1e-4 mm³.
    """
    ring = _ring_with_paths()
    group, features = _closure(ring)
    assert (group.variant, group.count) == ("bayonet", 3)
    assert sorted(features[name].params["area"] for name in closure_flanks(group, features)) == (
        pytest.approx([7.0] * 3 + [9.0] * 3 + [12.0] * 3 + [14.0] * 3, abs=1e-6)
    )
    played = -3 * 42.0 * 0.3
    turned = -3 * _swept_wall(3.0, 4.5)
    for params, expected in (
        ({"play": 0.6}, played),
        ({"turn": 3.0}, turned),
        ({"play": 0.6, "turn": 3.0}, played + turned),
        ({"turn": -3.0}, -turned),
    ):
        changed = _changed(ring, **params)
        assert changed.volume - ring.volume == pytest.approx(expected, abs=1e-4), params
        assert changed.is_watertight, params
        assert len(face_components(changed.raw)) == 1, params
        after, _features = _closure(changed)
        assert (after.variant, after.count) == ("bayonet", 3), params


def test_the_stop_is_the_closed_end_of_each_path() -> None:
    """Der Anschlag ist die Flanke, über die Boden und Dach reichen — 9 mm² bei −19°.

    Die Einführwände reichen bis zum Rand und sind offen; die Nocken des
    Deckels zeigen ihre Flanken nach außen und haben keinen.
    """
    ring = _ring_with_paths()
    group, features = _closure(ring)
    stops = closure_stops(group, features, ring)
    assert len(stops) == 3
    assert all(stop.sense == -1.0 for stop in stops)
    assert [features[stop.flank].params["area"] for stop in stops] == pytest.approx([9.0] * 3)
    assert sorted(round(_angle(features[stop.flank])) % 360 for stop in stops) == [101, 221, 341]
    lid = _corpus("bayonet_lid")
    lid_group, lid_features = _closure(lid)
    assert closure_stops(lid_group, lid_features, lid) == ()


def test_a_longer_turn_moves_the_stop_of_the_bayonet_part() -> None:
    """Die Aufnahme des Bajonettbausteins: Der Anschlag schwenkt um genau 2° weiter.

    Gemessen an der neu erkannten Flanke selbst, nicht am Volumen: Ihre Mitte
    steht 2° weiter, ihre Fläche bleibt bis auf das, was die Vielecke der
    Mäntel hergeben — sie haben 48 Ecken, und zwischen zwei Ecken ist die Wand
    um bis zu (R − r)(1 − cos 3,75°) = 0,0043 mm schmaler, auf 3,75 mm Höhe
    also 0,016 mm². Das Spiel sagt dort ab: Die Einführwand, die bündig in
    den Drehschlitz übergeht, ist keine eigene Fläche, und einseitig ändert
    sich nichts.
    """
    socket = _socket()
    group, features = _closure(socket)
    before = sorted(
        (_angle(features[stop.flank]) % 360.0, features[stop.flank].params["area"])
        for stop in closure_stops(group, features, socket)
    )
    assert len(before) == 3
    changed = _changed(socket, turn=2.0)
    group_after, features_after = _closure(changed)
    after = sorted(
        (_angle(features_after[stop.flank]) % 360.0, features_after[stop.flank].params["area"])
        for stop in closure_stops(group_after, features_after, changed)
    )
    assert [angle for angle, _area in after] == pytest.approx(
        [angle + 2.0 for angle, _area in before], abs=1e-6
    )
    assert [area for _angle, area in after] == pytest.approx(
        [area for _angle, area in before], abs=0.02
    )
    refusal = reason_against_play(group, features, socket)
    assert refusal is not None and "Gegenüber" in refusal
    with pytest.raises(GeometryError) as refused:
        _changed(socket, play=0.4)
    assert str(refused.value.detail) == refusal


def test_a_turn_into_the_next_station_is_refused() -> None:
    """Sechs Wege im Abstand von 60°: 45° weiter, und der Anschlag liefe in den nächsten Weg.

    Der Anschlag steht bei −19°, die nächste Stellung reicht mit Einführwand und
    Drehschlitz bis −55° — 36° Luft. Das Werkzeug träfe dahinter Luft, die
    Wirkung verfehlte die Rechnung: eine Absage mit Satz, kein halber Weg.
    """
    ring = _ring_with_paths((0, 60, 120, 180, 240, 300))
    assert _changed(ring, turn=30.0).volume < ring.volume
    with pytest.raises(GeometryError) as refused:
        _changed(ring, turn=45.0)
    assert "Nachbarstellung" in str(refused.value.detail)
    assert refused.value.suggestions


def test_a_lid_has_no_stop_and_says_so() -> None:
    """Nocken tragen ihren Drehweg am Gegenstück: Am Deckel sagt *Verschluss ändern* das."""
    with pytest.raises(GeometryError) as refused:
        _changed(_corpus("bayonet_lid"), turn=2.0)
    assert "Anschlag" in str(refused.value.detail)
    assert refused.value.suggestions


def test_too_much_play_is_refused_with_a_sentence() -> None:
    """Nocken 3,8 breit, 4 mm mehr Spiel: Die Nocke würde schmaler als null — Absage, kein Rest."""
    with pytest.raises(GeometryError) as refused:
        _changed(_corpus("bayonet_lid"), play=4.0)
    assert refused.value.suggestions
    assert "schmaler als null" in str(refused.value.detail)
    assert refused.value.values["width_mm"] == pytest.approx(3.8, abs=1e-3)


def test_too_little_play_closes_a_path() -> None:
    """Die Einführwege sind gut 6,7 mm weit: 7 mm weniger Spiel schlössen sie."""
    ring = _ring_with_paths()
    group, features = _closure(ring)
    narrowest = min(pair.gap for pair in closure_pairs(group, features, ring) if pair.gap > 0.0)
    assert narrowest == pytest.approx(2.0 * 38.5 * math.sin(math.radians(5.0)), abs=0.05)
    with pytest.raises(GeometryError) as refused:
        _changed(ring, play=-7.0)
    assert "ganz zu" in str(refused.value.detail)


def test_no_change_and_no_closure_are_refused() -> None:
    """Null ändert nichts, eine Fläche ohne Verschluss ist keiner — beides mit Satz."""
    lid = _corpus("bayonet_lid")
    with pytest.raises(GeometryError) as nothing:
        _changed(lid)
    assert "stehen auf null" in str(nothing.value.detail)
    features = detect(lid)
    group, _same = _closure(lid)
    outside = next(
        name
        for name, feature in features.items()
        if name not in group.members and feature.kind == "face"
    )
    with pytest.raises(GeometryError) as elsewhere:
        feature_operation(
            "resize_closure",
            lid,
            dict(features),
            features[outside],
            profiles.make_profile("centauri-carbon-2", "petg"),
            play=0.5,
        )
    assert str(elsewhere.value.detail) == str(NOT_A_CLOSURE)


def test_round_notches_have_no_flanks_and_say_where_to_go() -> None:
    """Die Rastmulden des Gewürzdeckels sind Rundungen — ihr Radius ändert das Spiel."""
    base = _corpus("spice_base")
    group, features = _closure(base)
    assert closure_flanks(group, features) == ()
    reason = reason_against_closure(group, features)
    assert reason is not None and "runde Mulden" in reason


def test_the_feature_panel_offers_what_the_operation_computes() -> None:
    """Das Merkmalfenster bietet je Teil die Felder an, die *Verschluss ändern* dort rechnet.

    Am Rohr mit Wegen Spiel und Drehweg, am Deckel mit Nocken nur das Spiel —
    der Satz zum Drehweg steht in der Notiz —, an der Bausteinaufnahme nur den
    Drehweg, und an den runden Mulden des Gewürzdeckels eine graue Zeile mit
    dem Satz der Operation. Dieselben Fragen wie die Operation, keine zweite
    Fassung (``groups.reason_against_play``, ``reason_against_turn``).
    """
    from app.core.perceive.actions import actions_for

    def offered(mesh: MeshData) -> tuple[str | None, tuple[str, ...], str, str]:
        group, features = _closure(mesh)
        member = next(name for name in group.members if name != group.anchor)
        row = next(
            entry
            for entry in actions_for(features[member], features, mesh=mesh)
            if str(entry.title) == "Verschluss ändern"
        )
        return row.op, tuple(field.name for field in row.fields), str(row.note), str(row.reason)

    op, fields, _note, _reason = offered(_ring_with_paths())
    assert (op, fields) == ("resize_closure", ("play", "turn"))
    op, fields, note, _reason = offered(_corpus("bayonet_lid"))
    assert (op, fields) == ("resize_closure", ("play",))
    assert "Anschlag" in note
    op, fields, note, _reason = offered(_socket())
    assert (op, fields) == ("resize_closure", ("turn",))
    assert "Gegenüber" in note
    op, fields, _note, reason = offered(_corpus("spice_base"))
    assert (op, fields) == (None, ())
    assert "runde Mulden" in reason
