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
    ``779 · 0,2 / 0,5`` mm je Schicht bei 40 mm/s.

    Die Mindestschichtzeit bremst und zählt die Stütze nicht: Gemessen am Pilz
    lag die Rechnung mit Abbremsen 19 % (PrusaSlicer) und 11 % (CuraEngine)
    unter der Druckdatei, ohne 0 und 11 % (04.10.2026). Deshalb ist der Zuschlag
    mit 5 s Mindestzeit derselbe wie ohne.
    """
    result = _mushroom()
    motion = _motion(support_speed=40.0)
    per_layer = (30.0 * 30.0 - 11.0 * 11.0) * 0.2 / 0.5 / 40.0
    for minimum in (0.0, 5.0):
        settings = _supported(cooling__minimum_layer_time=minimum)
        added = _support_seconds(result, settings, motion)
        assert added == pytest.approx(_under_the_cap(result) * per_layer, rel=1e-3), minimum
    assert _under_the_cap(result) == 50


def test_the_contact_layers_under_the_overhang_print_dense_at_their_own_speed() -> None:
    """Zwei Kontaktschichten direkt unter dem Hut: dort die volle Fläche mit der
    Kontaktdichte des Profils und dem Kontakttempo, darunter das Muster."""
    result = _mushroom()
    ring = 30.0 * 30.0 - 11.0 * 11.0
    motion = _motion(
        support_speed=40.0, support_interface_speed=20.0, support_interface_density=0.5
    )
    layers = _under_the_cap(result)
    expected = (layers - 2) * ring * 0.2 / 0.5 / 40.0 + 2 * ring * 0.5 / 0.5 / 20.0

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
