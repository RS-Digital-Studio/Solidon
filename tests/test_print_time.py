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
