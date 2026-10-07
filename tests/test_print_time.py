"""Druckzeit aus der Schichtanalyse (RM-465): Sollwerte aus der Konstruktion.

Die Zeitgegenprobe nach dem Slicen verglich die Schätzung aus Volumen und
Oberfläche mit der Druckdatei und warnte an Würfel und Pilz in sieben von acht
Läufen (60 bis 80 Prozent zu wenig). :mod:`app.core.slice.print_time` rechnet
je Schicht mit Mindestschichtzeit, Mindestdrucktempo, Ecken und Beschleunigung.
Hier stehen die Teilrechnungen gegen Werte, die man von Hand nachrechnet; die
Abnahme an vier echten Slicern steht im Bericht von RM-465.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.slice import print_time
from app.core.slice.analysis import slice_body
from app.core.types import PrintSettings, SliceResult
from tests.helpers import CountingToken

#: Eine Maschine ohne Trägheit: Beschleunigung so groß, dass jedes Trapez zu
#: Weg durch Tempo wird. Damit bleibt die Geometrie allein im Sollwert; übrig
#: bleibt je Leerfahrt ``v/a`` = 1e9/1e12 s, daher die Toleranz ``CLOSE``.
INSTANT = 1e12
CLOSE = 1e-4


def _settings(**changes: object) -> PrintSettings:
    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    speed = replace(
        settings.speed,
        outer_wall=50.0,
        inner_wall=100.0,
        infill=200.0,
        top_surface=50.0,
        first_layer=25.0,
        travel=1e9,
        bridge=20.0,
        acceleration=INSTANT,
        outer_wall_acceleration=INSTANT,
    )
    settings = replace(
        settings,
        speed=speed,
        layers=replace(
            settings.layers,
            layer_height=0.2,
            first_layer_height=0.2,
            line_width=0.5,
            first_layer_line_width=0.5,
        ),
        shell=replace(settings.shell, wall_count=2, top_layers=0, bottom_layers=0),
        infill=replace(settings.infill, density=0.0),
        cooling=replace(settings.cooling, minimum_layer_time=0.0),
        retraction=replace(settings.retraction, length=0.0, z_hop=0.0),
        filament=replace(settings.filament, max_flow=0.0),
    )
    for path, value in changes.items():
        settings = print_settings.with_path(settings, path.replace("__", "."), value)
    return settings


def _motion(**changes: object) -> print_time.Motion:
    return replace(print_time.Motion(nozzle=0.4, minimum_speed=1e-6), **changes)  # type: ignore[arg-type]


def _box(width: float, depth: float, height: float, at: float = 0.0) -> SliceResult:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((at, 0.0, height / 2.0))
    return slice_body(MeshData.of(body), 0.2, first_layer_height=0.2, support_volume=False)


def test_without_inertia_a_box_takes_its_wall_length_through_its_speeds() -> None:
    """Ein 20-mm-Würfel, zwei Wände, keine Füllung: je Schicht zwei Quadrate.

    Die Außenwand liegt eine halbe Bahn innen, die zweite anderthalb:
    ``4 · (20 − 0,5)`` mm bei 50 mm/s und ``4 · (20 − 1,5)`` mm bei 100 mm/s.
    Die erste Schicht fährt beide Wände mit 25 mm/s und füllt ihr Inneres
    ``(20 − 2)²`` mm² als Vollfläche mit Bahnen von 0,5 mm, auch mit 25 mm/s.
    Ohne Deckschicht kommt oben nichts dazu.
    """
    settings = _settings(shell__bottom_layers=1)
    result = _box(20.0, 20.0, 20.0)
    layers = sum(1 for layer in result.layers if layer.area > 1e-6)
    outer, inner = 4.0 * (20.0 - 0.5), 4.0 * (20.0 - 1.5)
    first = (outer + inner) / 25.0 + (20.0 - 2.0) ** 2 / 0.5 / 25.0
    expected = first + (layers - 1) * (outer / 50.0 + inner / 100.0)

    seconds = print_time.plate_seconds([(result, settings)], _motion())

    assert layers == 100
    assert seconds == pytest.approx(expected, rel=CLOSE)


def test_a_layer_is_slowed_to_the_minimum_time_but_not_below_the_minimum_speed() -> None:
    """Die Mindestschichtzeit ist keine garantierte Untergrenze (RM-465).

    Ein Stäbchen 4 × 4 mm, eine Wand bei 50 mm/s: ``4 · 3,5 / 50 = 0,28`` s je
    Schicht. Mit 5 s Mindestzeit und beliebig kleinem Mindesttempo dauert jede
    Schicht 5 s; mit 10 mm/s Mindesttempo höchstens ``14 / 10 = 1,4`` s.
    """
    settings = _settings(shell__wall_count=1, cooling__minimum_layer_time=5.0)
    result = _box(4.0, 4.0, 2.0)
    layers = sum(1 for layer in result.layers if layer.area > 1e-6)
    loop = 4.0 * (4.0 - 0.5)

    free = print_time.plate_seconds([(result, settings)], _motion(minimum_speed=1e-6))
    floored = print_time.plate_seconds([(result, settings)], _motion(minimum_speed=10.0))

    assert free == pytest.approx(layers * 5.0, rel=CLOSE)
    assert floored == pytest.approx(layers * loop / 10.0, rel=CLOSE)
    assert floored < free


def test_parts_printed_together_are_slowed_together() -> None:
    """Zwei Stäbchen auf einer Platte teilen sich die Mindestschichtzeit.

    Ein Slicer bremst die Schicht, nicht das Teil: Zusammen brauchen zwei
    gleiche Stäbchen dieselben 5 s je Schicht wie eines allein.
    """
    settings = _settings(shell__wall_count=1, cooling__minimum_layer_time=5.0)
    one = _box(4.0, 4.0, 2.0)
    other = _box(4.0, 4.0, 2.0, at=20.0)

    alone = print_time.plate_seconds([(one, settings)], _motion())
    together = print_time.plate_seconds([(one, settings), (other, settings)], _motion())

    assert together == pytest.approx(alone, rel=CLOSE)


def test_a_full_stop_at_every_corner_costs_the_trapezoid() -> None:
    """Ohne Junction-Deviation und Ruck hält die Maschine an jeder Ecke.

    Eine Seite der Länge ``L`` mit Tempo ``v`` und Beschleunigung ``a`` braucht
    dann ``L/v + v/a``, solange ``L ≥ v²/a`` (Trapez). Beim 20-mm-Würfel mit
    einer Wand bei 50 mm/s und 1000 mm/s² ist ``v²/a = 2,5`` mm.
    """
    accel = 1000.0
    settings = _settings(
        shell__wall_count=1,
        speed__outer_wall_acceleration=accel,
        speed__first_layer=50.0,
    )
    result = _box(20.0, 20.0, 1.0)
    layers = sum(1 for layer in result.layers if layer.area > 1e-6)
    side = 20.0 - 0.5
    per_layer = 4.0 * (side / 50.0 + 50.0 / accel)

    seconds = print_time.plate_seconds(
        [(result, settings)], _motion(first_layer_acceleration=accel)
    )

    assert seconds == pytest.approx(layers * per_layer, rel=1e-3)


@pytest.mark.parametrize(
    ("turn", "jd", "jerk", "expected"),
    [
        # Junction-Deviation, 90 Grad: v² = a·δ·sin45/(1 - sin45).
        (math.pi / 2, 0.01, 0.0, math.sqrt(5000.0 * 0.01 * math.sqrt(0.5) / (1 - math.sqrt(0.5)))),
        # Ruck, 90 Grad: Der Sprung 2·v·sin45 darf höchstens den Ruck erreichen.
        (math.pi / 2, 0.0, 8.0, 8.0 / (2.0 * math.sin(math.pi / 4))),
        # Ohne beides ein Halt.
        (math.pi / 2, 0.0, 0.0, 0.0),
        # Geradeaus keine Bremsung.
        (0.0, 0.01, 0.0, 200.0),
    ],
)
def test_corner_speeds_follow_the_machines_rule(
    turn: float, jd: float, jerk: float, expected: float
) -> None:
    roles = print_time._roles(
        _settings(), _motion(junction_deviation=jd or None, jerk=jerk or None)
    )
    assert print_time.corner_speed(200.0, 5000.0, turn, roles) == pytest.approx(expected)


def test_the_first_layer_keeps_its_two_manufacturer_speeds_until_one_is_chosen() -> None:
    """Getrennte Erstschichttempi aus dem Herstellerprofil (RM-465): Wände 50,
    Füllung 105 mm/s am Centauri Carbon 2 — Solidons eines Feld führt das
    schnellere. Wählt der Kunde ein Erstschichttempo, gilt es für beide."""
    settings = _settings(speed__first_layer=105.0)
    motion = _motion(first_layer_wall_speed=50.0, first_layer_infill_speed=105.0)

    roles = print_time._roles(settings, motion)
    assert (roles.first_wall, roles.first_infill) == (50.0, 105.0)

    chosen = print_settings.with_choice(settings, "speed.first_layer", 30.0)
    roles = print_time._roles(chosen, motion)
    assert (roles.first_wall, roles.first_infill) == (30.0, 30.0)


def test_the_rule_counts_layers_by_their_number_not_by_the_part() -> None:
    """Ein flaches und ein hohes Teil: Oberhalb des flachen läuft das hohe allein."""
    settings = _settings()
    flat = _box(20.0, 20.0, 1.0)
    tall = _box(20.0, 20.0, 4.0, at=40.0)

    together = print_time.plate_seconds([(flat, settings), (tall, settings)], _motion())
    apart = print_time.plate_seconds([(flat, settings)], _motion()) + print_time.plate_seconds(
        [(tall, settings)], _motion()
    )

    assert together == pytest.approx(apart, rel=CLOSE)


def test_the_calculation_can_be_cancelled() -> None:
    settings = _settings()
    with pytest.raises(OperationCancelled):
        print_time.plate_seconds(
            [(_box(20.0, 20.0, 20.0), settings)], _motion(), cancelled=CountingToken(3)
        )


# --- Was das Herstellerprofil über die Zeit sagt ---------------------------------------

#: Die Werte des Centauri Carbon 2 aus ElegooSlicer 1.5 (Konfigurationsblock
#: des Würfellaufs, RM-465): Anteile wie in Orcas Profilen.
_ELEGOO_PROCESS = {
    "default_acceleration": "10000",
    "outer_wall_acceleration": "5000",
    "inner_wall_acceleration": "0",
    "sparse_infill_acceleration": "100%",
    "internal_solid_infill_acceleration": "100%",
    "top_surface_acceleration": "2000",
    "bridge_acceleration": "50%",
    "initial_layer_acceleration": "500",
    "travel_acceleration": "0",
    "initial_layer_speed": "50",
    "initial_layer_infill_speed": "105",
    "sparse_infill_speed": "200",
    "internal_solid_infill_speed": "250",
    "bridge_speed": "50",
    "internal_bridge_speed": "150%",
}
_ELEGOO_MACHINE = {
    "machine_max_acceleration_extruding": ["20000", "20000"],
    "machine_max_junction_deviation": ["0.01"],
    "machine_max_speed_z": ["20", "20"],
    "retraction_speed": ["40"],
    "deretraction_speed": ["0"],
}


def test_orca_motion_reads_the_manufacturer_chain_with_its_shares() -> None:
    from app.core.export import manufacturer

    motion = manufacturer.orca_motion(
        _ELEGOO_PROCESS, _ELEGOO_MACHINE, {"slow_down_min_speed": ["20"]}, 0.4
    )

    assert motion is not None
    assert motion.minimum_speed == 20.0
    assert (motion.first_layer_wall_speed, motion.first_layer_infill_speed) == (50.0, 105.0)
    assert motion.solid_infill_speed == 250.0
    assert motion.internal_bridge_speed == pytest.approx(75.0)  # 150 % von 50
    assert motion.bridge_acceleration == pytest.approx(2500.0)  # 50 % der Außenwand
    assert motion.infill_acceleration == pytest.approx(10000.0)
    # Null heißt „wie die Vorgabe“, nicht „gar nicht“.
    assert motion.inner_wall_acceleration is None
    assert motion.travel_acceleration is None
    assert motion.junction_deviation == 0.01
    assert motion.acceleration_limit == 20000.0
    assert motion.deretraction_speed == 40.0


def test_without_a_minimum_speed_there_is_no_motion() -> None:
    """Ohne belegtes Mindestdrucktempo keine behauptete Mindestdauer (RM-465)."""
    from app.core.export import manufacturer

    assert manufacturer.orca_motion(_ELEGOO_PROCESS, _ELEGOO_MACHINE, {}, 0.4) is None
    assert manufacturer.prusa_motion({"perimeter_speed": "45"}, 0.4) is None


def test_prusa_motion_uses_jerk_and_only_limits_the_profile_hands_to_its_estimate() -> None:
    """PrusaSlicers Zeitrechnung kennt nur den Ruck je Achse (``GCodeProcessor.cpp``),
    und Maschinengrenzen nur mit ``machine_limits_usage`` zur Zeitrechnung."""
    from app.core.export import manufacturer

    values = {
        "min_print_speed": "15",
        "first_layer_speed": "20",
        "first_layer_infill_speed": "50%",
        "infill_speed": "80",
        "solid_infill_speed": "100%",
        "bridge_speed": "25",
        "bridge_speed_internal": "150%",
        "machine_max_jerk_x": "8,8",
        "machine_max_junction_deviation": "0.01,0.01",
        "machine_max_acceleration_extruding": "1250,1250",
        "retract_speed": "70",
        "deretract_speed": "40",
    }
    unused = manufacturer.prusa_motion({**values, "machine_limits_usage": "ignore"}, 0.4)
    used = manufacturer.prusa_motion({**values, "machine_limits_usage": "emit_to_gcode"}, 0.4)

    assert unused is not None and used is not None
    assert unused.minimum_speed == 15.0
    assert unused.first_layer_infill_speed == pytest.approx(10.0)
    assert unused.solid_infill_speed == pytest.approx(80.0)
    assert unused.internal_bridge_speed == pytest.approx(37.5)
    assert unused.junction_deviation is None and used.junction_deviation is None
    assert unused.jerk is None and unused.acceleration_limit is None
    assert used.jerk == 8.0 and used.acceleration_limit == 1250.0
    assert (used.retraction_speed, used.deretraction_speed) == (70.0, 40.0)


def test_the_plate_comparison_carries_the_time_only_with_motion() -> None:
    """Die Plattengegenprobe nimmt die Zeit aus demselben Schnitt; ohne
    :class:`Motion` steht dort keine (keine belegte Mindestdauer)."""
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SceneObject

    settings = _settings(shell__bottom_layers=1)
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    body.apply_translation((0.0, 0.0, 10.0))
    entry = SceneObject(id="cube", name="Würfel", mesh=MeshData.of(body))
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    parts = [(entry, entry.mesh, settings)]

    with_motion = plate_comparison(
        0, parts, profile, keep_arrangement=True, separate_objects=True, motion=_motion()
    )
    without = plate_comparison(0, parts, profile, keep_arrangement=True, separate_objects=True)

    expected = print_time.plate_seconds([(_box(20.0, 20.0, 20.0), settings)], _motion())
    assert with_motion.seconds == pytest.approx(expected, rel=CLOSE)
    assert without.seconds is None


# --- Stützen (RM-281 Paket 3, Nachtrag RM-465) ---------------------------------------


def _mushroom() -> SliceResult:
    """Ein Stiel 10 × 10 × 10 mm, darauf ein Hut 30 × 30 × 2 mm."""
    stem = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    stem.apply_translation((0.0, 0.0, 5.0))
    cap = trimesh.creation.box(extents=(30.0, 30.0, 2.0))
    cap.apply_translation((0.0, 0.0, 11.0))
    body = trimesh.boolean.union([stem, cap])
    return slice_body(MeshData.of(body), 0.2, first_layer_height=0.2, support_volume=False)


def _supported(**changes: object) -> PrintSettings:
    values: dict[str, object] = {
        "support__style": "grid",
        "support__density": 0.2,
        "support__xy_gap": 0.5,
        "support__interface_layers": 0,
    }
    return _settings(**{**values, **changes})


def _under_the_cap(result: SliceResult) -> int:
    return sum(1 for layer in result.layers if layer.area > 1e-6 and layer.z < 10.0)


def _support_seconds(
    result: SliceResult, settings: PrintSettings, motion: print_time.Motion
) -> float:
    bare = print_settings.with_path(settings, "support.style", "none")
    return print_time.plate_seconds([(result, settings)], motion) - print_time.plate_seconds(
        [(result, bare)], motion
    )


def test_supports_run_their_path_through_their_speed_outside_the_minimum_layer_time() -> None:
    """Unter dem Hut steht je Schicht der Ring ``30² − (10 + 2 · 0,5)²`` mm²
    (seitlicher Abstand zum Stiel), gefüllt mit 20 % Bahn von 0,5 mm Breite:
    ``779 · 0,2 / 0,5`` mm je Schicht, dazu die Verbindungen am Rand des
    Musters, ``SUPPORT_CONNECTION_SHARE`` seines Umfangs ``4 · 30 + 4 · 11`` mm,
    alles bei 40 mm/s.

    Die Mindestschichtzeit bremst und zählt die Stütze nicht: Gemessen am Pilz
    lag die Rechnung mit Abbremsen 19 % (PrusaSlicer) und 11 % (CuraEngine)
    unter der Druckdatei, ohne 0 und 11 % (04.10.2026). Deshalb ist der Zuschlag
    mit 5 s Mindestzeit derselbe wie ohne.
    """
    result = _mushroom()
    motion = _motion(support_speed=40.0)
    edge = print_time.SUPPORT_CONNECTION_SHARE * (4.0 * 30.0 + 4.0 * 11.0)
    per_layer = ((30.0 * 30.0 - 11.0 * 11.0) * 0.2 / 0.5 + edge) / 40.0
    for minimum in (0.0, 5.0):
        settings = _supported(cooling__minimum_layer_time=minimum)
        added = _support_seconds(result, settings, motion)
        assert added == pytest.approx(_under_the_cap(result) * per_layer, rel=1e-3), minimum
    assert _under_the_cap(result) == 50


def test_the_contact_layers_under_the_overhang_print_dense_at_their_own_speed() -> None:
    """Zwei Kontaktschichten direkt unter dem Hut: dort die volle Fläche mit der
    Kontaktdichte des Profils und dem Kontakttempo, ohne Randverbindungen,
    darunter das Muster mit ihnen."""
    result = _mushroom()
    ring = 30.0 * 30.0 - 11.0 * 11.0
    motion = _motion(
        support_speed=40.0, support_interface_speed=20.0, support_interface_density=0.5
    )
    layers = _under_the_cap(result)
    edge = print_time.SUPPORT_CONNECTION_SHARE * (4.0 * 30.0 + 4.0 * 11.0)
    expected = (layers - 2) * (ring * 0.2 / 0.5 + edge) / 40.0 + 2 * ring * 0.5 / 0.5 / 20.0

    added = _support_seconds(result, _supported(support__interface_layers=2), motion)

    assert added == pytest.approx(expected, rel=1e-3)


def test_a_tree_runs_the_same_path_slower_than_a_pattern() -> None:
    """Die Orca-Familie schreibt Äste als Zug kurzer Stücke; mit Ruck und
    Beschleunigung der Maschine dauert dieselbe Bahn länger als ein Muster aus
    langen Linien (Pilz: rund 27 s je Meter in ElegooSlicer und Bambu Studio)."""
    result = _mushroom()
    motion = _motion(support_speed=150.0, jerk=9.0)
    settings = _supported(speed__acceleration=10000.0)
    grid = _support_seconds(result, settings, motion)
    tree = _support_seconds(
        result, print_settings.with_path(settings, "support.style", "tree"), motion
    )
    automatic = _support_seconds(
        result,
        print_settings.with_path(settings, "support.style", "auto"),
        replace(motion, support_tree=True),
    )

    assert tree > grid * 1.5
    assert automatic == pytest.approx(tree, rel=CLOSE)


def test_without_supports_the_time_is_unchanged() -> None:
    """Ohne Stützen kommt nichts dazu, auch wenn das Profil Stütztempi nennt."""
    result = _mushroom()
    settings = print_settings.with_path(_supported(), "support.style", "none")

    plain = print_time.plate_seconds([(result, settings)], _motion())
    with_values = print_time.plate_seconds(
        [(result, settings)], _motion(support_speed=40.0, support_tree=True, support_closing=2.0)
    )

    assert with_values == pytest.approx(plain, rel=CLOSE)


def test_the_manufacturer_chain_names_speed_contact_and_kind_of_its_supports() -> None:
    """Orca: ``support_speed``, Kontakt über den Abstand, Bäume an ``support_type``;
    einen Anteil im Kontakttempo verwirft OrcaSlicer 2.4.2 und fährt 80 mm/s
    (Kobra 2). Prusa: Kontakttempo als Anteil des Stütztempos, ``organic`` ist Baum."""
    from app.core.export import manufacturer

    orca = manufacturer.orca_motion(
        {
            **_ELEGOO_PROCESS,
            "support_speed": "150",
            "support_interface_speed": "100%",
            "support_line_width": "0.42",
            "support_interface_spacing": "0.5",
            "support_type": "tree(auto)",
            "bridge_no_support": "1",
        },
        _ELEGOO_MACHINE,
        {"slow_down_min_speed": ["20"]},
        0.4,
    )
    prusa = manufacturer.prusa_motion(
        {
            "min_print_speed": "15",
            "support_material_speed": "120",
            "support_material_interface_speed": "50%",
            "support_material_extrusion_width": "0.4",
            "support_material_interface_spacing": "0.2",
            "support_material_style": "organic",
            "support_material_closing_radius": "2",
            "default_acceleration": "4000",
        },
        0.4,
    )

    assert orca is not None and prusa is not None
    assert orca.support_speed == 150.0
    assert orca.support_interface_speed == manufacturer.ORCA_SUPPORT_INTERFACE_SPEED
    assert orca.support_interface_density == pytest.approx(0.42 / 0.92)
    assert orca.support_acceleration == 10000.0
    assert orca.support_tree and orca.support_skips_bridges
    assert orca.support_closing == manufacturer.ORCA_SUPPORT_CLOSING
    assert prusa.support_speed == 120.0
    assert prusa.support_interface_speed == pytest.approx(60.0)
    assert prusa.support_interface_density == pytest.approx(0.4 / 0.6)
    assert prusa.support_tree and not prusa.support_skips_bridges
    assert prusa.support_closing == 2.0


def test_the_time_is_not_compared_when_the_slicer_supports_differently() -> None:
    """Die Zeit rechnet die Stützen mit, die die Schichtanalyse schätzt. Stützt
    der Slicer mehr als doppelt oder weniger als halb so viel, sagt eine
    Zeitwarnung nur, dass die Stützen andere sind (Waschschüssel: ein Viertel
    bis ein Drittel der gedruckten Stützmenge geschätzt, 04.10.2026)."""
    from app.core.slice.estimate import (
        SUPPORT_TIME_AGREEMENT,
        PlateComparison,
        time_comparison_blocked,
    )
    from app.core.slice.gcode import GcodeMetrics

    estimate = PlateComparison(0, 1000.0, 50)
    near = 1000.0 * SUPPORT_TIME_AGREEMENT * 0.9
    far = 1000.0 * SUPPORT_TIME_AGREEMENT * 1.1

    assert time_comparison_blocked([estimate], GcodeMetrics(support_mm3=near)) == ""
    assert time_comparison_blocked([estimate], GcodeMetrics(support_mm3=far))
    assert time_comparison_blocked(
        [estimate], GcodeMetrics(support_mm3=1000.0 / SUPPORT_TIME_AGREEMENT / 1.1)
    )
    assert (
        time_comparison_blocked([PlateComparison(0, 0.0, 50)], GcodeMetrics(support_mm3=0.0)) == ""
    ), "ohne Stützen bleibt der Vergleich"
    assert (
        time_comparison_blocked([PlateComparison(0, 0.0, 50)], GcodeMetrics(support_mm3=None)) == ""
    ), "ohne Stützen fehlt der Druckdatei nichts"
    assert time_comparison_blocked([estimate], GcodeMetrics(support_mm3=None))


def test_the_time_is_not_compared_where_curaengine_drives_its_own_travels() -> None:
    """CuraEngine fährt mit Combing, das Zeitmodell kennt das noch nicht (Review P2 Rest, Z1).

    An 46 Läufen trug CuraEngine vier der zwölf Zeitwarnungen über 15 %, auch
    ohne Stützen. Bis RM-281 die Leerfahrten baut, schweigt die Zeitgegenprobe
    dort mit Grund; ein anderer Slicer mit denselben Zahlen wird verglichen.
    """
    from app.core.slice.estimate import PlateComparison, time_comparison_blocked
    from app.core.slice.gcode import GcodeMetrics

    plain = PlateComparison(0, 0.0, 50)
    cura = GcodeMetrics(support_mm3=0.0, slicer="Cura_SteamEngine 5.8.1")
    prusa = GcodeMetrics(support_mm3=0.0, slicer="PrusaSlicer-2.9.2+win64")
    assert "CuraEngine" in str(time_comparison_blocked([plain], cura))
    assert time_comparison_blocked([plain], prusa) == ""


def test_the_time_is_not_compared_where_the_slicer_grows_trees() -> None:
    """Baumstützen fahren Bahnen, die das Zeitmodell noch nicht kennt (Review P2 Rest, Z1).

    Waschschüssel mit Baumstützen in ElegooSlicer und Bambu Studio: −18,8 und
    −18,5 % als Fehlalarm. ``plate_comparison`` sagt, ob ein Baum steht —
    gewählt oder als „automatisch“ eines Profils mit Bäumen —, und die
    Gegenprobe schweigt dort mit Grund; dieselbe Stützmenge als Raster wird
    verglichen.
    """
    from app.core.slice.estimate import (
        PlateComparison,
        plate_comparison,
        time_comparison_blocked,
    )
    from app.core.slice.gcode import GcodeMetrics
    from app.core.types import SceneObject

    printed = GcodeMetrics(support_mm3=1000.0)
    grid = PlateComparison(0, 1000.0, 50)
    trees = PlateComparison(0, 1000.0, 50, tree_supports=True)
    assert time_comparison_blocked([grid], printed) == ""
    assert "Baumstützen" in str(time_comparison_blocked([trees], printed))

    stem = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    stem.apply_translation((0.0, 0.0, 5.0))
    cap = trimesh.creation.box(extents=(30.0, 30.0, 2.0))
    cap.apply_translation((0.0, 0.0, 11.0))
    mesh = MeshData.of(trimesh.boolean.union([stem, cap]))
    entry = SceneObject(id="pilz", name="Pilz", mesh=mesh)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    supported = _supported()
    found: dict[tuple[str, bool], bool] = {}
    for style, profile_trees in (("tree", False), ("auto", True), ("auto", False)):
        settings = print_settings.with_path(supported, "support.style", style)
        comparison = plate_comparison(
            0,
            [(entry, mesh, settings)],
            profile,
            keep_arrangement=True,
            separate_objects=True,
            motion=_motion(support_tree=profile_trees),
        )
        found[(style, profile_trees)] = comparison.tree_supports
    assert found == {("tree", False): True, ("auto", True): True, ("auto", False): False}


def test_a_profile_without_bridge_supports_leaves_time_and_support_unchecked() -> None:
    """Kobra 2 (``bridge_no_support = 1``): OrcaSlicer las die Pilzunterseite als
    Brücke und stützte nur ihren Rand — mit Stützen +96 % gerechnet, ohne −32 %.
    Welche Decke das ist, weiß nur der Slicer; Zeit und Stützmenge bleiben offen,
    mit Grund, ohne Stützen wird verglichen wie immer."""
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SceneObject

    stem = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    stem.apply_translation((0.0, 0.0, 5.0))
    cap = trimesh.creation.box(extents=(30.0, 30.0, 2.0))
    cap.apply_translation((0.0, 0.0, 11.0))
    mesh = MeshData.of(trimesh.boolean.union([stem, cap]))
    entry = SceneObject(id="pilz", name="Pilz", mesh=mesh)
    profile = profiles.make_profile("anycubic-kobra-2", "pla")
    motion = _motion(support_skips_bridges=True)
    supported = _supported()
    bare = print_settings.with_path(supported, "support.style", "none")

    with_support = plate_comparison(
        0,
        [(entry, mesh, supported)],
        profile,
        keep_arrangement=True,
        separate_objects=True,
        motion=motion,
    )
    without = plate_comparison(
        0,
        [(entry, mesh, bare)],
        profile,
        keep_arrangement=True,
        separate_objects=True,
        motion=motion,
    )

    assert with_support.seconds is None and with_support.seconds_reason
    assert with_support.support_material_mm3 is None and with_support.support_reason
    assert without.seconds is not None and without.seconds > 0.0
    assert not without.seconds_reason


# --- Was der Slicer aus dem Herstellerprofil macht (RM-281, Zeitschätzung) ---------------


def _seconds(result: SliceResult, settings: PrintSettings, motion: print_time.Motion) -> float:
    return print_time.plate_seconds([(result, settings)], motion)


def test_neighbouring_lines_lie_a_flow_spacing_apart() -> None:
    """Orca und PrusaSlicer legen Vollbahnen ``Breite − Höhe · (1 − π/4)``
    auseinander (``Flow::spacing``), Cura eine Breite. Die erste Schicht des
    Würfels füllt ``18²`` mm² mit 25 mm/s; der Unterschied ist genau die
    Mehrlänge ``324 · (1/Abstand − 1/0,5)``."""
    settings = _settings(shell__bottom_layers=1)
    result = _box(20.0, 20.0, 20.0)
    gap = 0.5 - 0.2 * (1.0 - math.pi / 4.0)

    width = _seconds(result, settings, _motion())
    spaced = _seconds(result, settings, _motion(flow_spacing=True))

    assert print_time.spacing(0.5, 0.2, _motion(flow_spacing=True)) == pytest.approx(gap)
    assert spaced - width == pytest.approx(324.0 * (1.0 / gap - 1.0 / 0.5) / 25.0, rel=1e-3)


def test_a_shell_thickness_adds_layers_where_the_count_falls_short() -> None:
    """Orca ``bottom_shell_thickness`` (Kobra 2: 3 Schichten, 1,2 mm): Der
    Slicer legt weiter Vollschichten, bis die Dicke erreicht ist. Am Würfel mit
    einer Bodenschicht werden die Schichten 2 bis 6 voll statt leer:
    ``5 · 324 / 0,5 / 200`` s."""
    assert print_time.shell_layers(3, 1.2, 0.2) == 6
    assert print_time.shell_layers(5, 1.0, 0.2) == 5
    assert print_time.shell_layers(3, None, 0.2) == 3
    assert print_time.shell_layers(0, 1.0, 0.2) == 0
    settings = _settings(shell__bottom_layers=1)
    result = _box(20.0, 20.0, 4.0)

    plain = _seconds(result, settings, _motion())
    thick = _seconds(result, settings, _motion(bottom_shell_thickness=1.2))

    assert thick - plain == pytest.approx(5 * 324.0 / 0.5 / 200.0, rel=1e-3)


def _frustum() -> SliceResult:
    """Ein Pyramidenstumpf 20 × 20 unten, 8 × 8 oben, 6 mm hoch: 45° Wände."""
    body = trimesh.Trimesh(
        vertices=[
            (-10, -10, 0),
            (10, -10, 0),
            (10, 10, 0),
            (-10, 10, 0),
            (-4, -4, 6),
            (4, -4, 6),
            (4, 4, 6),
            (-4, 4, 6),
        ],
        faces=[
            (0, 2, 1),
            (0, 3, 2),
            (4, 5, 6),
            (4, 6, 7),
            (0, 1, 5),
            (0, 5, 4),
            (1, 2, 6),
            (1, 6, 5),
            (2, 3, 7),
            (2, 7, 6),
            (3, 0, 4),
            (3, 4, 7),
        ],
    )
    body.fix_normals()
    return slice_body(MeshData.of(body), 0.2, first_layer_height=0.2, support_volume=False)


def test_on_a_slope_the_fill_of_the_shell_layers_above_decides_what_stays_sparse() -> None:
    """``ensure_vertical_shell_thickness``: Dünn bleibt nur, was auch in den
    Deckschichten darüber Füllfläche ist. Am 45°-Stumpf weicht die Füllfläche
    je Schicht 0,2 mm je Seite zurück; mit drei Deckschichten wird ein Rand von
    zwei Schichten, 0,4 mm, voll, nach Orcas Glättung 0,2 Abstände mehr. Bei
    Dichte null kostet nur dieser Rand Zeit: ``(a² − (a − 2 · Rand)²) / 0,5 /
    200`` je Schicht mit Füllfläche ``a = 18 − 2 z``. Die innere Brücke unter
    der Deckschicht fährt hier wie die Vollfüllung, sonst verschöbe die
    kleinere dünne Fläche darunter auch sie."""
    settings = _settings(shell__top_layers=3, speed__bridge=200.0)
    result = _frustum()
    band = 0.4 + 0.2 * 1.05 * 0.5
    expected = 0.0
    for layer in result.layers[1:]:
        side = 18.0 - 2.0 * layer.z
        if layer.z < 6.0 - 3 * 0.2 and side > 2.0 * band:
            expected += (side * side - (side - 2.0 * band) ** 2) / 0.5 / 200.0

    plain = _seconds(result, settings, _motion(nozzle=0.5))
    shells = _seconds(result, settings, _motion(nozzle=0.5, vertical_shells=True))

    assert shells - plain == pytest.approx(expected, rel=0.05)


def test_sparse_lines_are_joined_along_the_wall_by_the_measured_share() -> None:
    """Orca verbindet die Enden der dünnen Füllung am Rand (``connect_infill``):
    beim Zickzack ``CONNECTION_SHARE["rectilinear"]`` des Umfangs ``4 · 18`` mm
    je Schicht über der ersten, bei 200 mm/s. Ein Muster ohne Messung und Cura
    (kein ``zig_zaggify_infill``) bekommen nichts."""
    settings = _settings(infill__density=0.2)
    result = _box(20.0, 20.0, 20.0)
    share = print_time.CONNECTION_SHARE["rectilinear"]

    unknown = _seconds(result, settings, _motion(flow_spacing=True, sparse_pattern="gyroid"))
    joined = _seconds(result, settings, _motion(flow_spacing=True, sparse_pattern="rectilinear"))
    cura = _seconds(result, settings, _motion(sparse_pattern="rectilinear"))

    assert joined - unknown == pytest.approx(99 * share * 72.0 / 200.0, rel=1e-3)
    assert cura == pytest.approx(_seconds(result, settings, _motion()), rel=CLOSE)


def test_the_next_wall_loop_of_an_island_starts_without_retraction() -> None:
    """Die Schleifen einer Insel liegen eine Bahn auseinander, unter
    ``retraction_minimum_travel``: Ein Würfel mit drei Wänden zieht je Schicht
    einmal zurück, nicht dreimal (1 mm mit 10 mm/s hin und zurück, 0,2 s)."""
    settings = _settings(shell__wall_count=3)
    result = _box(20.0, 20.0, 20.0)
    retracting = _settings(shell__wall_count=3, retraction__length=1.0, retraction__speed=10.0)

    added = _seconds(result, retracting, _motion()) - _seconds(result, settings, _motion())

    assert added == pytest.approx(100 * 0.2, rel=1e-3)


def _tube() -> SliceResult:
    outer = trimesh.creation.cylinder(radius=20.0, height=2.0, sections=128)
    inner = trimesh.creation.cylinder(radius=18.0, height=3.0, sections=128)
    body = outer.difference(inner)
    body.apply_translation((0.0, 0.0, 1.0))
    return slice_body(MeshData.of(body), 0.2, first_layer_height=0.2, support_volume=False)


def test_a_narrow_solid_runs_as_loops_along_its_shape() -> None:
    """Orca ``detect_narrow_internal_solid_infill``: Vollfüllung ohne Kern von
    vier Abständen läuft als Schleife entlang der Form statt in kurzen Bahnen
    quer. Ohne Trägheit derselbe Weg, also dieselbe Zeit; mit Beschleunigung
    und Halt an jeder Ecke (kein Ruck) ist die Schleife deutlich schneller."""
    result = _tube()
    settings = _settings(shell__wall_count=1, shell__bottom_layers=10)
    loops = _motion(narrow_solid_loops=True)
    assert _seconds(result, settings, loops) == pytest.approx(
        _seconds(result, settings, _motion()), rel=1e-3
    )
    braking = {
        "shell__wall_count": 1,
        "speed__acceleration": 1000.0,
        "speed__outer_wall_acceleration": 1000.0,
    }
    walls = _seconds(result, _settings(**braking), _motion())
    solid = _settings(shell__bottom_layers=10, **braking)

    across = _seconds(result, solid, _motion()) - walls
    along = _seconds(result, solid, loops) - walls

    assert along < 0.3 * across


def test_the_support_reaches_the_whole_overhang_not_only_beyond_the_angle() -> None:
    """Orca und Prusa weiten einen erkannten Überhang auf den ganzen Überstand
    über die Schicht darunter (``detect_overhangs``: „Offset the support regions
    back to a full overhang“). Ein Keil, der je 0,2-mm-Schicht 0,4 mm je Seite
    ausladet, bei 45° Grenze: Die Säulen füllen den Raum unter beiden Flanken,
    ``2 · ∫ (10 − 2 z) · 20 dz`` von 0 bis 5 = 1000 mm³. Vorher stützte jede
    Schicht nur den halben Überstand, und die Säulen standen in Streifen."""
    body = trimesh.Trimesh(
        vertices=[
            (-5, -10, 0),
            (5, -10, 0),
            (15, -10, 5),
            (-15, -10, 5),
            (-5, 10, 0),
            (5, 10, 0),
            (15, 10, 5),
            (-15, 10, 5),
        ],
        faces=[
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 4),
            (3, 4, 0),
        ],
    )
    body.fix_normals()
    result = slice_body(
        MeshData.of(body), 0.2, first_layer_height=0.2, overhang_angle=45.0, support_volume=False
    )
    settings = _supported(
        support__style="tree",
        support__density=1.0,
        support__xy_gap=0.0,
        support__threshold_angle=45.0,
    )

    volume = print_time.support_material(result, settings, _motion())

    assert volume == pytest.approx(1000.0, rel=0.05)


def test_the_plate_comparison_takes_its_support_from_the_columns_of_the_time() -> None:
    """Mit :class:`Motion` rechnet die Gegenprobe die Stützmenge aus denselben
    Säulen wie die Druckzeit (:func:`print_time.support_material`), nicht aus
    dem Rauminhalt mal Dichte."""
    from app.core.slice.estimate import plate_comparison
    from app.core.slice.findings import analysed
    from app.core.types import SceneObject

    stem = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    stem.apply_translation((0.0, 0.0, 5.0))
    cap = trimesh.creation.box(extents=(30.0, 30.0, 2.0))
    cap.apply_translation((0.0, 0.0, 11.0))
    mesh = MeshData.of(trimesh.boolean.union([stem, cap]))
    settings = _supported()
    entry = SceneObject(id="pilz", name="Pilz", mesh=mesh)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    motion = _motion(support_speed=40.0)

    compared = plate_comparison(
        0,
        [(entry, mesh, settings)],
        profile,
        keep_arrangement=True,
        separate_objects=True,
        motion=motion,
    )
    limits = profiles.analysis_limits(
        profiles.for_process(profile, settings, effective=True), entry
    )
    result = analysed(mesh, settings, settings.support.threshold_angle, limits[0])

    assert compared.support_material_mm3 == pytest.approx(
        print_time.support_material(result, settings, motion), rel=CLOSE
    )


def test_the_manufacturer_chain_names_what_the_slicer_makes_of_the_layers() -> None:
    """Orca: Bahnbreiten je Rolle (Anteile von der Düse), Mindestdicke der
    Schalen, ganze senkrechte Schalen, kleinste dünne Fläche, schmale
    Vollfüllung als Schleife, Füllmuster. Prusa: dieselben
    Fragen unter seinen Schlüsseln; beide legen Bahnen nach ``Flow::spacing``."""
    from app.core.export import manufacturer

    orca = manufacturer.orca_motion(
        {
            **_ELEGOO_PROCESS,
            "outer_wall_line_width": "0.42",
            "inner_wall_line_width": "0.45",
            "sparse_infill_line_width": "112.5%",
            "internal_solid_infill_line_width": "0.42",
            "top_surface_line_width": "0.42",
            "top_shell_thickness": "1.0",
            "bottom_shell_thickness": "1.2",
            "ensure_vertical_shell_thickness": "ensure_all",
            "minimum_sparse_infill_area": "15",
            "sparse_infill_pattern": "rectilinear",
        },
        _ELEGOO_MACHINE,
        {"slow_down_min_speed": ["20"]},
        0.4,
    )
    moderate = manufacturer.orca_motion(
        {
            **_ELEGOO_PROCESS,
            "ensure_vertical_shell_thickness": "ensure_moderate",
            "detect_narrow_internal_solid_infill": "0",
        },
        _ELEGOO_MACHINE,
        {"slow_down_min_speed": ["20"]},
        0.4,
    )
    prusa = manufacturer.prusa_motion(
        {
            "min_print_speed": "15",
            "external_perimeter_extrusion_width": "0.45",
            "perimeter_extrusion_width": "0.45",
            "infill_extrusion_width": "0.45",
            "solid_infill_extrusion_width": "0.45",
            "top_infill_extrusion_width": "0.42",
            "top_solid_min_thickness": "0.7",
            "bottom_solid_min_thickness": "0.5",
            "ensure_vertical_shell_thickness": "enabled",
            "solid_infill_below_area": "0",
            "fill_pattern": "grid",
        },
        0.4,
    )

    assert orca is not None and moderate is not None and prusa is not None
    assert (orca.outer_wall_width, orca.inner_wall_width) == (0.42, 0.45)
    assert orca.sparse_width == pytest.approx(0.45)
    assert (orca.solid_width, orca.top_width) == (0.42, 0.42)
    assert orca.flow_spacing and prusa.flow_spacing
    assert (orca.top_shell_thickness, orca.bottom_shell_thickness) == (1.0, 1.2)
    assert orca.vertical_shells and not moderate.vertical_shells
    assert orca.minimum_sparse_area == 15.0
    assert orca.narrow_solid_loops and not moderate.narrow_solid_loops
    assert orca.sparse_pattern == "rectilinear"
    assert (prusa.outer_wall_width, prusa.top_width) == (0.45, 0.42)
    assert (prusa.top_shell_thickness, prusa.bottom_shell_thickness) == (0.7, 0.5)
    assert prusa.vertical_shells
    assert prusa.minimum_sparse_area is None
    assert prusa.sparse_pattern == "grid"


def test_what_the_chain_leaves_open_comes_from_the_measured_program_defaults() -> None:
    """ElegooSlicer und OrcaSlicer fahren die innere Brücke mit 150 % der
    Brücke, auch wo die Kette des Herstellers den Schlüssel nicht nennt
    (Konfigurationsblock der Seitenablage, 06.10.2026); ohne den Wert rechnete
    die Zeitgegenprobe sie mit dem Brückentempo, 50 statt 75 mm/s."""
    from app.core.export import manufacturer

    process = {
        key: value for key, value in _ELEGOO_PROCESS.items() if key != "internal_bridge_speed"
    }
    for program in ("elegooslicer", "orcaslicer"):
        motion = manufacturer.orca_motion(
            {**manufacturer.PROGRAM_DEFAULTS[program], **process},
            _ELEGOO_MACHINE,
            {"slow_down_min_speed": ["20"]},
            0.4,
        )
        assert motion is not None
        assert motion.internal_bridge_speed == pytest.approx(75.0), program
    for program, value in (("orcaslicer", "ensure_all"), ("bambustudio", "enabled")):
        assert manufacturer.PROGRAM_DEFAULTS[program]["ensure_vertical_shell_thickness"] == value
    assert manufacturer.PRUSA_PROGRAM_DEFAULTS["ensure_vertical_shell_thickness"] == "enabled"


#: Wie weit Solidons Druckzeit am Quader (40, 40, 20 mm) von der Druckdatei des
#: Slicers abliegt, in Prozent — gemessen am Druckdialogweg mit dem
#: Herstellerprofil ohne Stützen (RM-281, 07.10.2026; Creality Print an 7.3
#: nachgemessen). Programm → (Drucker, Abweichung, gemessene Fassung). Die
#: Fassung steht hier, weil eine andere die Zeit verschiebt, ohne dass sich
#: Code ändert: Weicht die installierte ab,
#: überspringt der Test mit beiden Fassungen statt rot zu werden, und das
#: Nachmessen ist ein Release-Schritt (``schichtanalyse.md``, Review P2 Rest, Z2).
SLICER_DEVIATION: dict[str, tuple[str, float, str]] = {
    "elegooslicer": ("centauri-carbon-2", -5.7, "1.5.3.5"),
    "prusaslicer": ("prusa-mk4s", 1.4, "2.9.6"),
    "cura": ("sovol-sv06", -13.2, "5.13.0"),
    "orcaslicer": ("anycubic-kobra-2", -9.2, "2.4.2"),
    "bambustudio": ("bambu-p1s", 0.1, "02.08.02.61"),
    "crealityprint": ("creality-k1", -0.5, "7.3"),
}

#: Wie viele Prozentpunkte ein Lauf von der Messung abweichen darf: eine
#: andere Fassung des Slicers verschiebt seine Zeit, eine Rechenänderung in
#: Solidon soll es nicht unbemerkt tun.
SLICER_SPREAD = 3.0


def _same_version(generated: str, measured: str) -> bool:
    """Ob die Druckdatei (``GcodeMetrics.slicer``, „generated by …“) die gemessene Fassung nennt.

    Verglichen wird Stelle für Stelle so weit, wie die Messung sie nennt:
    „7.2“ trifft „7.2.0.4012“, aber nicht „7.20“.
    """
    import re

    found = re.search(r"\d+(?:\.\d+)+", generated)
    if found is None:
        return False
    wanted = measured.split(".")
    return found.group(0).split(".")[: len(wanted)] == wanted


def test_a_version_matches_digit_group_by_digit_group() -> None:
    """Die Fassungsprüfung des Slicer-Tests vergleicht Stellen, nicht Zeichen (Z2)."""
    assert _same_version("Cura_SteamEngine 5.13.0", "5.13.0")
    assert _same_version("PrusaSlicer-2.9.6+win64 on 2026-10-07", "2.9.6")
    assert _same_version("CrealityPrint 7.2.0.4012", "7.2")
    assert not _same_version("CrealityPrint 7.20.1", "7.2")
    assert not _same_version("OrcaSlicer 2.4.3", "2.4.2")
    assert not _same_version("", "2.4.2")


def _installed_slicer(program: str) -> object | None:
    from app.core import discover, tools
    from app.core.export import slicer_keys

    # Die Suite fragt die Maschine sonst nicht (``_machine_stays_out_of_it``);
    # dieser Test braucht genau den installierten Slicer.
    for path in discover.unpatched_find_programs("slicer", tools.SLICERS):  # type: ignore[attr-defined]
        if slicer_keys.program_of(path) == program:
            return path
    return None


def _setup_like_the_dialog(exe: object, profile: object) -> object:
    """Der Slicer, wie der Druckdialog ihn vorwählt (``tools/matrix_unit.prepared``):
    Druckerprofil, Prozess der Stufe und PLA-Filament des Herstellers."""
    from app.core.export import handover, manufacturer, slicer_profiles

    setup = handover.detect(exe)
    if setup.flavour not in ("orca", "prusa"):
        return setup
    found = list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process")))
    machine, process = slicer_profiles.match(found, profile.printer)
    if machine is None:
        pytest.fail(f"{exe} kennt kein Herstellerprofil für {profile.printer.id}")
    roots = slicer_profiles.profile_roots(setup.flavour, exe)
    filaments = list(slicer_profiles.find_profiles(exe, setup.flavour, ("filament",)))
    filament = slicer_profiles.match_filament(filaments, machine, "PLA", roots)
    setup = replace(
        setup,
        machine_profile=machine.name,
        base_process=process.name if process else "",
        base_filament=slicer_profiles.identity(filament) if filament else "",
    )
    staged = manufacturer.for_stage(setup, profile, print_settings.resolve(profile).quality)
    return staged if staged is not None else setup


@pytest.mark.parametrize("program", sorted(SLICER_DEVIATION))
def test_the_estimate_of_a_box_stays_where_the_installed_slicer_was_measured(
    program: str, tmp_path
) -> None:
    """Am echten Slicer: Quader 40 × 40 × 20 (``cube_clean`` aus dem Korpus,
    gestreckt) auf dem Weg des Druckdialogs, Druckzeit ab der ersten Schicht
    aus der Druckdatei gegen Solidons Schätzung. Die Abweichung bleibt
    innerhalb von :data:`SLICER_SPREAD` Punkten um die Messung; übersprungen
    wird ohne installierten Slicer und bei einer anderen Fassung als der
    gemessenen — so läuft der Test auch auf Linux und macOS, wo der Slicer
    liegt, und ein Rechner mit anderer Fassung wird nicht rot."""
    from pathlib import Path

    from app.core.export import handover, manufacturer
    from app.core.types import SceneObject
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    exe = _installed_slicer(program)
    if exe is None:
        pytest.skip(f"{program} ist hier nicht installiert")
    printer, measured, version = SLICER_DEVIATION[program]
    profile = profiles.make_profile(printer, "pla")
    setup = _setup_like_the_dialog(exe, profile)
    foundation = manufacturer.base_settings(profile, print_settings.resolve(profile).quality, setup)
    settings = print_settings.with_choice(
        manufacturer.effective(None, foundation), "support.style", "none"
    )
    cube = trimesh.load(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
    cube.apply_scale((2.0, 2.0, 1.0))
    cube.apply_translation((0.0, 0.0, -cube.bounds[0][2]))
    body = SceneObject(id="obj_1", name="Quader", mesh=MeshData.of(cube))
    job = _PlateJob(
        objects=(body,),
        plates=(0,),
        folder=tmp_path,
        name="quader",
        setup=setup,
        settings=settings,
        profile=profile,
        slot_profiles={},
        with_comparison=True,
    )
    run = _prepare_plate(job, 0)
    outcome = handover.slice_model(
        [run.model],
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        keep_arrangement=run.keep_arrangement,
        slots=run.slots,
        model_height=run.model_height,
        model_meshes=run.meshes,
        expected_tools=run.used_tools,
    )
    # Eine leere Kennung ist ein Rückschritt im G-Code-Leser, keine andere
    # Fassung: Sie verschwände sonst auf jedem Rechner im Übersprungenen
    # (Review P2 N9).
    assert outcome.metrics.slicer, f"{program}: die Kopfzeile der Druckdatei nennt keinen Slicer"
    if not _same_version(outcome.metrics.slicer, version):
        pytest.skip(
            f"{program}: gemessen an Fassung {version}, installiert ist "
            f"{outcome.metrics.slicer} — nachmessen (schichtanalyse.md)"
        )
    printed = outcome.metrics.printing_seconds
    estimated = run.comparison.seconds if run.comparison is not None else None
    assert printed and estimated, f"{program}: Druckdatei {printed}, Schätzung {estimated}"
    deviation = (estimated / printed - 1.0) * 100.0
    assert abs(deviation - measured) <= SLICER_SPREAD, (
        f"{program}: Schätzung {estimated / 60:.1f} min gegen Druckdatei "
        f"{printed / 60:.1f} min, {deviation:+.1f} % statt {measured:+.1f} %"
    )
