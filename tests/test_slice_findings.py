"""Was die Schichtanalyse aus einem Körper schließt — gegen Körper, deren
Zahlen sich ausrechnen lassen (§22.2, §40).

Jeder Fall hier stand einmal falsch im Bericht: eine Rippe, die in keiner Zahl
vorkam; eine Brücke über einem tragenden Stiel; eine Stützsäule, die auf dem
Modell endet und als „erreicht das Bett" gemeldet wurde.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
import trimesh
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.geom.mesh import MeshData
from app.core.geom.transform import place_on_bed
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.slice.analysis import (
    WIDTH_INTERESTING,
    minimum_width,
    narrowest,
    slice_body,
    spanning_width,
    support_on_model,
)
from app.core.types import Profile, SliceResult


def on_bed(*parts: trimesh.Trimesh) -> MeshData:
    body = parts[0] if len(parts) == 1 else trimesh.boolean.union(list(parts))
    return place_on_bed(MeshData.of(body))


def brick(x: float, y: float, z: float, at: tuple[float, float, float]) -> trimesh.Trimesh:
    body: trimesh.Trimesh = trimesh.creation.box(extents=(x, y, z))
    body.apply_translation(at)
    return body


def petg() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


# --- Die kleinste Strukturbreite ist die kleinste, nicht die größte -------------


def ribbed_plate() -> MeshData:
    """Eine Platte 20 auf 20 auf 5 mit einer 0,3 mm dünnen Rippe daran.

    Der Querschnitt ist ein Quadrat von 20 mm mit einem Fortsatz von 0,3 auf
    10 mm — die dünnste Struktur des Körpers misst also 0,3 mm, und genau das
    soll dastehen.
    """
    return on_bed(
        brick(20.0, 20.0, 5.0, (0.0, 0.0, 2.5)),
        brick(11.0, 0.3, 5.0, (14.5, 0.0, 2.5)),
    )


def test_a_thin_rib_beside_a_thick_plate_is_the_measured_width() -> None:
    """Gemessen wurde der größte einbeschriebene Kreis statt der dünnsten
    Stelle.

    ``shape.buffer(-r).is_empty`` wird erst wahr, wenn auch die **dickste**
    Stelle weg ist. Die Platte meldete damit die Berichtsgrenze von 2,0 mm —
    die Rippe, um die es geht, kam in keiner Zahl vor.
    """
    result = slice_body(ribbed_plate(), 0.5)

    assert narrowest(result) == pytest.approx(0.3, abs=0.05)
    assert narrowest(result) < WIDTH_INTERESTING, "der Deckel ist keine Messung"


def test_the_same_plate_without_the_rib_stays_thick() -> None:
    """Die Gegenprobe: Ohne Rippe ist an der Platte nichts dünn, und dann steht
    die Berichtsgrenze da — so wie vorher.
    """
    result = slice_body(on_bed(brick(20.0, 20.0, 5.0, (0.0, 0.0, 2.5))), 0.5)

    assert narrowest(result) == pytest.approx(WIDTH_INTERESTING)


def test_the_rib_reaches_the_report() -> None:
    """Unter der angesetzten Mindestbahnbreite steht ein Hinweis zur Prüfung."""
    profile = petg()
    settings = print_settings.resolve(profile)
    result = slice_body(ribbed_plate(), 0.5)

    codes = {entry.code for entry in advise.warnings_for(settings, profile, result)}

    assert "settings.wall_below_nozzle" in codes


def test_a_convex_body_measures_exactly_as_before() -> None:
    """Bei einer konvexen Form ist die Öffnung die Identität, bis die Erosion
    sie ganz auflöst — die neue Rechnung gibt dort dieselbe alte Antwort.
    """
    assert minimum_width(box(0.0, 0.0, 10.0, 0.6)) == pytest.approx(0.6, rel=0.05)
    assert minimum_width(box(0.0, 0.0, 40.0, 30.0), interesting_below=0.0) == pytest.approx(
        30.0, rel=0.05
    )


# --- Die Klammer der Spannweitensuche muss tragen -------------------------------


def keyhole() -> BaseGeometry:
    """Eine Öffnung Ø 40 mit einem 0,2 mm schmalen Schlitz daran.

    Der Schlitz treibt den Umfang hoch, ohne Fläche zu bringen: ``2A/L`` fällt
    von 20 auf 7,8 und liegt damit **unter** dem gesuchten Radius. Zu
    überbrücken sind trotzdem 40 mm — ein Ausläufer von zwei Zehnteln macht
    keine Öffnung leichter.
    """
    return unary_union([Point(0.0, 0.0).buffer(20.0, quad_segs=64), box(0.0, -0.1, 100.0, 0.1)])


def test_a_slotted_opening_is_still_measured_across() -> None:
    """Die Klammer ``2A/L`` ist nur bei konvexen Formen eine obere Schranke.

    Fiel sie darunter, lief die Halbierung bis an ihren eigenen Anfang und
    meldete ihn: 17,5 mm statt 40 — und die Warnung über die Brücke blieb aus.
    """
    shape = keyhole()
    coarse = 2.0 * float(shape.area) / float(shape.length)

    assert coarse < 20.0, "sonst trägt die alte Klammer und der Fall prüft nichts"
    assert spanning_width(shape) == pytest.approx(40.0, rel=0.05)


def test_a_plain_disc_is_unchanged() -> None:
    """Die Gegenprobe ohne Schlitz: dort trug die Klammer schon immer."""
    assert spanning_width(Point(0.0, 0.0).buffer(20.0, quad_segs=64)) == pytest.approx(
        40.0, rel=0.05
    )


# --- Ein Ring über Material ist keine Öffnung ----------------------------------


def test_a_mushroom_on_a_solid_stem_spans_nothing() -> None:
    """Gezählt wurde jedes Loch der ungestützten Fläche — auch eines, unter dem
    massives Material steht.

    Ein Pilz mit tragendem Stiel (Hut 100 auf 100, Stiel 30 auf 30) meldete
    eine Brücke von 29,7 mm über genau dem Stiel, der sie trägt.
    """
    body = on_bed(
        brick(30.0, 30.0, 20.0, (0.0, 0.0, 10.0)),
        brick(100.0, 100.0, 5.0, (0.0, 0.0, 22.5)),
    )

    result = slice_body(body, 0.5)

    assert max(layer.bridge_width for layer in result.layers) == pytest.approx(0.0, abs=0.5)
    assert "slice.long_bridge" not in {
        entry.code for entry in advise.warnings_for(print_settings.resolve(petg()), petg(), result)
    }


def test_a_shoulder_over_a_real_hollow_still_speaks() -> None:
    """Die Gegenprobe, damit der Filter nicht alles verschluckt: Über einem
    offenen Becher hängt die Bahn wirklich frei.
    """
    outer = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=64)
    outer.apply_translation((0.0, 0.0, 20.0))
    wide = trimesh.creation.cylinder(radius=16.0, height=20.0, sections=64)
    wide.apply_translation((0.0, 0.0, 12.0))
    narrow = trimesh.creation.cylinder(radius=10.0, height=22.0, sections=64)
    narrow.apply_translation((0.0, 0.0, 31.0))
    body = MeshData.of(trimesh.boolean.difference([outer, wide, narrow]))

    result = slice_body(body, 0.2)

    assert max(layer.bridge_width for layer in result.layers) == pytest.approx(20.0, rel=0.1)


# --- Stützen enden nicht überall auf dem Bett ----------------------------------


def table() -> MeshData:
    """Bodenplatte 40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte.

    Keine Insel, 1 500 mm² Überhang auf einer Schicht — und jede Stütze
    darunter endet auf der Bodenplatte, nicht auf dem Bett.
    """
    return on_bed(
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 2.5)),
        brick(10.0, 10.0, 20.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 27.5)),
    )


def bracket() -> MeshData:
    """Ein Kragarm: eine Wand vom Bett hoch, oben eine Platte quer darauf.

    Derselbe Überhang, aber unter ihm steht nichts — die Stütze reicht bis auf
    die Platte.
    """
    return on_bed(
        brick(10.0, 40.0, 30.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 32.5)),
    )


def test_a_column_that_lands_on_the_model_is_seen() -> None:
    result = slice_body(table(), 0.5)

    assert not result.layers[0].islands, "der Tisch hat keine Insel — das war der Trugschluss"
    assert support_on_model(result), "die Säule endet auf der Bodenplatte"


def test_a_cantilever_reaches_the_bed() -> None:
    result = slice_body(bracket(), 0.5)

    assert not support_on_model(result)


def placement_advice(body: MeshData) -> str | None:
    settings = print_settings.resolve(petg())
    entries = advise.advise(settings, petg(), slice_body(body, 0.5))
    for entry in entries:
        if entry.path == "support.placement":
            return str(entry.value)
    return None


def test_the_table_keeps_supports_everywhere() -> None:
    """Der Vorschlag ``build_plate`` ließ die Tischplatte absacken: Er wurde aus
    „keine Insel" geschlossen, und das ist etwas anderes als „alles erreicht
    das Bett".
    """
    assert placement_advice(table()) is None, "everywhere bleibt stehen"


def test_the_cantilever_may_stay_on_the_plate() -> None:
    """Die Gegenprobe, sonst wäre die Regel nur abgeschaltet."""
    assert placement_advice(bracket()) == "build_plate"


# --- Die Aufstandsfläche gehört dem Drucker, nicht der Suche --------------------


def test_the_footing_does_not_depend_on_the_search_resolution() -> None:
    """Eine Kugel mit R = 20 stand bei 1,0 mm Suchhöhe auf 54 mm² und bei
    0,2 mm auf 4,6 — dieselbe Kugel, dieselbe Lage, zwei Antworten auf „kann
    das stehen".
    """
    ball = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0)))
    printed = petg().printer.layer_height / 2.0

    coarse = slice_body(ball, 1.0, footing_height=printed)
    fine = slice_body(ball, 0.2, footing_height=printed)

    assert coarse.first_layer_area == pytest.approx(fine.first_layer_area, rel=0.02)
    # Und die Zahl ist die des Drucks: Ein Kugelabschnitt von 0,1 mm Höhe.
    expected = math.pi * (20.0**2 - (20.0 - printed) ** 2)
    assert coarse.first_layer_area == pytest.approx(expected, rel=0.2)


def test_without_the_printer_height_nothing_changes() -> None:
    """Ohne Angabe bleibt es beim ersten Schnitt — kein Aufrufer bekommt
    stillschweigend eine andere Zahl.
    """
    ball = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0)))

    result: SliceResult = slice_body(ball, 1.0)

    assert result.first_layer_area == pytest.approx(result.layers[0].area)


@pytest.mark.parametrize("style", ["none", "grid"])
def test_supports_above_a_base_plate_must_be_allowed_on_the_model(style: str) -> None:
    """Eingeschaltete Stützen allein erreichen den Tischdeckel noch nicht."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", style)
    settings = print_settings.with_path(settings, "support.placement", "build_plate")
    entries = advise.advise(settings, petg(), slice_body(table(), 0.5))
    changed = advise.apply(settings, entries)
    assert changed.support.style != "none"
    assert changed.support.placement == "everywhere"


def test_first_layer_flow_is_corrected_without_heating_other_layers() -> None:
    """Nur die erste Schicht überschreitet den Volumenstrom: ihr Tempo zählt."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "speed.first_layer", 200.0)
    entries = advise.advise(settings, profile)
    changed = advise.apply(settings, entries)
    assert changed.temperature == settings.temperature
    assert (
        advise.flow_of(changed, changed.speed.first_layer, first_layer=True)
        <= settings.filament.max_flow
    )
    assert not advise.advise(changed, profile)


def test_draft_flow_advice_reaches_a_stable_setting_in_one_step() -> None:
    """Mehrfaches Übernehmen darf die Düse nicht bis zur Maschinengrenze heizen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "draft")
    changed = advise.apply(settings, advise.advise(settings, profile))
    assert changed.temperature == settings.temperature
    assert advise.flow_of(changed, changed.speed.infill) <= changed.filament.max_flow
    assert not advise.advise(changed, profile)


def test_a_flow_below_the_smallest_print_speed_requires_a_correction() -> None:
    """Eine leere Vorschlagsliste darf keinen unerfüllbaren Volumenstrom verschweigen."""
    from app.core.errors import ValidationError

    profile = profiles.make_profile("prusa-mk4s", "pla")
    profile = replace(profile, printer=replace(profile.printer, nozzle_diameter=1.0))
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        layers=replace(
            settings.layers,
            layer_height=0.8,
            first_layer_height=0.8,
            line_width=1.2,
            first_layer_line_width=1.2,
        ),
        filament=replace(settings.filament, max_flow=0.5),
    )
    with pytest.raises(ValidationError) as error:
        advise.advise(settings, profile)
    assert error.value.field == "filament.max_flow"
    assert error.value.suggestions


def test_the_first_line_obeys_the_same_nozzle_limit() -> None:
    """Die Nachbareinstellung ist im Dialog ebenfalls frei editierbar."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "layers.first_layer_line_width", 0.1
    )
    changed = advise.apply(settings, advise.advise(settings, profile))
    assert changed.layers.first_layer_line_width == pytest.approx(0.34)


def test_a_single_arachne_line_is_not_reported_as_impossible() -> None:
    """PrusaSlicer erzeugt für diese 0,5-mm-Wand fünfzig Materiallagen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "shell.wall_generator", "arachne"
    )
    body = on_bed(brick(20.0, 0.5, 10.0, (0.0, 0.0, 5.0)))
    result = slice_body(body, settings.layers.layer_height)
    assert "settings.wall_below_nozzle" not in {
        entry.code for entry in advise.warnings_for(settings, profile, result)
    }


def test_a_fully_filled_connector_does_not_ask_for_more_material() -> None:
    """Bei hundert Prozent Füllung ist der Kern bereits aus Material."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "infill.density", 1.0)
    entries = advise.advise(settings, petg(), connectors=(8.0,))
    assert not {"shell.wall_count", "infill.density"}.intersection(entry.path for entry in entries)


@pytest.mark.parametrize("bed", [85, 100])
def test_small_footprint_advice_keeps_the_filament_bed_temperature(bed: int) -> None:
    """Eine kleine Standfläche liefert keine neue Temperaturgrenze für die Spule."""
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "temperature.bed_first_layer", bed
    )
    body = on_bed(brick(5.0, 5.0, 10.0, (0.0, 0.0, 5.0)))
    result = slice_body(body, settings.layers.layer_height)
    changed = advise.apply(settings, advise.advise(settings, profile, result))
    assert changed.temperature.bed_first_layer == bed
    again = advise.advise(changed, profile, result)
    assert "temperature.bed_first_layer" not in {entry.path for entry in again}


def test_combined_advice_preserves_support_needed_by_another_body() -> None:
    """Ein Würfel darf die schon nötigen Stützen seines Nachbarn nicht abschalten."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", "grid")
    cube = slice_body(on_bed(brick(20.0, 20.0, 20.0, (0.0, 0.0, 10.0))), 0.5)
    top = slice_body(table(), 0.5)
    groups = [(settings, advise.advise(settings, petg(), result)) for result in (cube, top)]
    entries = advise.combine(settings, groups)
    assert "support.style" not in {entry.path for entry in entries}


def test_combined_advice_limits_speed_for_the_slowest_material() -> None:
    """Das gemeinsame Tempo bleibt für jeden beteiligten Materialslot tragbar."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)
    slow = replace(settings, speed=replace(settings.speed, outer_wall=20.0))
    groups = [(settings, advise.advise(settings, profile)), (slow, advise.advise(slow, profile))]
    changed = advise.apply(settings, advise.combine(settings, groups))
    assert changed.speed.outer_wall == pytest.approx(20.0)


def test_suggested_connector_infill_meets_the_announced_material_share() -> None:
    """Runden darf den versprochenen Materialanteil nicht wieder unterschreiten."""
    settings = print_settings.resolve(petg())
    changed = advise.apply(settings, advise.advise(settings, petg(), connectors=(60.0,)))
    diameter = 60.0
    core = diameter - 2.0 * changed.shell.wall_count * changed.layers.line_width
    solid_area = (diameter**2 - core**2) + changed.infill.density * core**2
    assert solid_area / diameter**2 >= 0.75
