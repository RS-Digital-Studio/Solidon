"""Der Analyse-Schneider gegen Körper mit bekannten Zahlen (§22, §40).

Ein Würfel, ein Zylinder und ein Kegel haben Querschnitte, die sich mit einem
Bleistift ausrechnen lassen — der Schneider lässt sich also auf ein Prozent
festnageln statt auf ein Gefühl.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import place_on_bed
from app.core.ingest.loader import normalise
from app.core.slice.analysis import (
    WIDTH_INTERESTING,
    cross_section,
    island_layers,
    minimum_width,
    narrowest,
    narrowest_measured,
    slice_body,
    total_overhang,
)
from app.core.slice.orientation import search

MESHES = Path(__file__).parent / "data" / "meshes"

#: Was §40 verlangt: Fläche und Stützvolumen auf ein Prozent genau.
TOLERANCE = 0.01


def on_bed(body: trimesh.Trimesh) -> MeshData:
    return place_on_bed(MeshData.of(body))


def corpus(name: str) -> MeshData:
    return place_on_bed(normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh)


# --- against analytically known bodies ------------------------------------------


def test_a_cube_has_the_same_cross_section_all_the_way_up() -> None:
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.2)

    assert len(result.layers) == pytest.approx(100, abs=1)
    for layer in result.layers:
        assert layer.area == pytest.approx(400.0, rel=TOLERANCE)
    assert result.first_layer_area == pytest.approx(400.0, rel=TOLERANCE)


def test_a_cylinder_matches_pi_r_squared() -> None:
    body = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=256)
    result = slice_body(on_bed(body), 0.2)

    expected = math.pi * 10.0**2
    for layer in result.layers:
        assert layer.area == pytest.approx(expected, rel=TOLERANCE)


def test_a_cone_narrows_the_way_geometry_says() -> None:
    """Spitze nach oben: der Radius schrumpft linear, die Fläche also
    quadratisch.
    """
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=256)
    result = slice_body(on_bed(body), 0.5)

    for layer in result.layers:
        radius = 10.0 * (1.0 - layer.z / 20.0)
        assert layer.area == pytest.approx(math.pi * radius**2, rel=0.03, abs=0.5)


def test_a_straight_body_needs_no_support() -> None:
    """Die erste Schicht liegt auf der Platte, alles darüber auf der Schicht
    darunter.
    """
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.2)

    assert total_overhang(result) == pytest.approx(0.0, abs=1.0)
    assert result.support_volume == pytest.approx(0.0, abs=1.0)


def test_a_shallow_cone_needs_no_support_even_on_its_tip() -> None:
    """Eine Wand mit 27 Grad druckt sich selbst — die 45-Grad-Regel aus §39."""
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=128)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))

    assert slice_body(on_bed(body), 0.5).support_volume == pytest.approx(0.0, abs=1.0)


def test_a_steep_cone_on_its_tip_costs_support() -> None:
    """Eine Wand mit 63 Grad nicht — und für diesen Unterschied gibt es §22."""
    steep = trimesh.creation.cone(radius=20.0, height=10.0, sections=128)
    steep.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    upright = trimesh.creation.cone(radius=20.0, height=10.0, sections=128)

    on_tip = slice_body(on_bed(steep), 0.5)
    standing = slice_body(on_bed(upright), 0.5)

    assert on_tip.support_volume > 100.0
    assert standing.support_volume == pytest.approx(0.0, abs=1.0)


# --- das Stützvolumen (§22.2) ---------------------------------------------------


def mushroom() -> MeshData:
    """Ein Pilz: ein Stiel 10 × 10 × 20, darauf ein Hut 40 × 40 × 5.

    Der Körper, an dem sich das Stützvolumen mit einem Bleistift ausrechnen
    lässt: Der Hut kragt auf 40 · 40 − 10 · 10 = 1 500 mm² frei aus, und
    darunter stehen 20 mm Luft bis zur Platte. Die Säule misst also
    30 000 mm³.
    """
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 5.0))
    cap.apply_translation((0.0, 0.0, 22.5))
    return MeshData.of(trimesh.boolean.union([stem, cap]))


#: Was die Säule unter dem Pilzhut analytisch misst, in mm³.
MUSHROOM_SUPPORT = (40.0 * 40.0 - 10.0 * 10.0) * 20.0


def test_the_support_volume_is_the_column_and_not_the_overhanging_shell() -> None:
    """Gestützt wird der Raum **unter** dem Überhang, nicht der Überhang selbst.

    Gerechnet wurde ``Überhangfläche × Schichthöhe`` — das ist das Volumen der
    auskragenden Schale, also des Materials, das der Drucker dort ablegt. Was
    eine Stütze kostet, ist der Raum darunter: bei diesem Pilz 79 mm³ gegen
    30 000, ein Faktor von fast vierhundert. Auf dieser Zahl steht die
    Kostenschätzung, die Orientierungssuche und die Gegenprobe gegen den
    G-Code — die dadurch bei jedem Lauf Alarm schlug.
    """
    result = slice_body(place_on_bed(mushroom()), 0.2)

    assert result.support_volume == pytest.approx(MUSHROOM_SUPPORT, rel=0.05)


def test_the_support_volume_does_not_depend_on_the_layer_height() -> None:
    """Dieselbe Säule, doppelt so fein geschnitten — dieselbe Zahl.

    Die Probe, die den alten Fehler nicht überleben konnte: Über die Schale
    gerechnet skalierte das Ergebnis linear mit der Schichthöhe (79 mm³ bei
    0,2 mm, 385 bei 1,0). Eine Kennzahl, die sich mit der Auflösung ändert, mit
    der man sie misst, ist keine Eigenschaft des Körpers.
    """
    body = place_on_bed(mushroom())

    fine = slice_body(body, 0.2).support_volume
    coarse = slice_body(body, 0.4).support_volume

    assert fine == pytest.approx(coarse, rel=0.1), (
        f"{fine:.0f} mm³ bei 0,2 mm gegen {coarse:.0f} mm³ bei 0,4 mm"
    )


def test_the_support_volume_stops_at_the_material_below() -> None:
    """Eine Säule endet, wo sie auf das Teil trifft — nicht erst auf der Platte.

    Zwei Stufen: Der Hut sitzt hier auf einem Sockel, der die Hälfte des
    Überhangs auffängt. Ohne diese Prüfung ginge auch eine Rechnung durch, die
    schlicht jede Überhangfläche bis zum Bett verlängert.
    """
    base = trimesh.creation.box(extents=(30.0, 40.0, 10.0))
    base.apply_translation((-5.0, 0.0, 5.0))
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 5.0))
    cap.apply_translation((0.0, 0.0, 22.5))
    body = MeshData.of(trimesh.boolean.union([base, stem, cap]))

    result = slice_body(place_on_bed(body), 0.2)

    # Über dem Sockel (30 auf 40, abzüglich des Stiels) fällt der Hut nur
    # 10 mm, daneben (10 auf 40) volle 20 mm.
    over_base = (30.0 * 40.0 - 10.0 * 10.0) * 10.0
    beside_base = 10.0 * 40.0 * 20.0
    assert result.support_volume == pytest.approx(over_base + beside_base, rel=0.08)


#: Was PrusaSlicer 2.9.6 für denselben Pilz an Stützmaterial gemessen hat, in
#: mm³ — Lauf vom 25.08.2026, 0,2 mm, Stützen an, sonst Vorgaben.
#: (``prusa-slicer-console --export-gcode --support-material``, Typkommentare
#: über ``gcode.parse`` ausgezählt.)
MEASURED_SUPPORT = 3990.6


def test_the_cross_check_against_a_real_sliced_file_passes() -> None:
    """§28.2: Die Gegenprobe feuerte bei jedem Lauf — und hatte recht.

    Verglichen wurde ein **Rauminhalt** mit einer gemessenen **Fadenmenge**.
    Zwei verschiedene Größen liegen immer auseinander; die Schwelle von 15 %
    war dabei nie erreichbar, und eine Warnung, die immer kommt, liest nach
    dem dritten Mal niemand mehr.

    Der Drucker füllt die Säule nicht aus, er stellt ein Muster hinein —
    ``support.density``, hier fünfzehn Prozent. Mit dieser einen Umrechnung
    (:func:`estimate.support_material`) liegt die Gegenprobe innerhalb ihrer
    Schwelle.
    """
    from app.core.knowledge import print_settings, profiles
    from app.core.slice import estimate, gcode

    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "grid"
    )
    column = slice_body(place_on_bed(mushroom()), 0.2).support_volume

    check = gcode.compare(estimate.support_material(column, settings), MEASURED_SUPPORT, "support")

    assert check.within_limit, f"{check.deviation:+.0%} gegen einen echten Lauf"
    assert not check.findings
    # Und die Gegenrichtung: ohne die Umrechnung schlägt derselbe Lauf an.
    assert not gcode.compare(column, MEASURED_SUPPORT, "support").within_limit


def test_without_supports_the_column_costs_nothing() -> None:
    """Kein Muster, kein Material — und das ist keine Schätzung von null."""
    from app.core.knowledge import print_settings, profiles
    from app.core.slice import estimate

    settings = print_settings.resolve(profiles.make_profile())

    assert settings.support.style == "none"
    assert estimate.support_material(30000.0, settings) == 0.0


# --- islands --------------------------------------------------------------------


def test_the_island_tower_is_recognised() -> None:
    """§40: island_tower.stl is recognised."""
    result = slice_body(corpus("island_tower.stl"), 0.5)
    heights = island_layers(result)

    assert heights, "the floating block starts in mid-air and has to be found"
    # Der Block spannt von 20 bis 30 mm; die Brücke erreicht ihn erst bei 25 mm,
    # sie hängt also fünf Millimeter frei.
    assert min(heights) == pytest.approx(20.0, abs=1.0)
    assert max(heights) < 26.0, "from the bridge upwards it is carried"
    assert result.support_volume > 0.0


def test_a_solid_body_has_no_islands_above_the_plate() -> None:
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.5)
    # Die Schichten sind die Grundmenge, nicht die Inseln: Schneidet der Körper
    # gar nicht, hat er auch keine Inseln, und der Verbotstest unten ist grün.
    assert len(result.layers) > 10, f"nur {len(result.layers)} Schichten aus 20 mm"
    above = [z for z in island_layers(result) if z > 1.0]

    assert not above, "nothing starts in mid-air in a cube"


def test_a_contour_touching_only_at_a_corner_is_an_island() -> None:
    """Eine Ecke traegt nichts, und eine Kante auch nicht (§22.2).

    Hier entschied ``intersects``, und das ist in Shapely auch bei einer
    Beruehrung wahr — bei einer Ueberlappungsflaeche von exakt null. Zwei
    Wuerfel, die sich in einer Kante treffen, galten damit als verbunden;
    physikalisch liegt der obere auf einer Linie ohne Breite und faellt im
    Druck ab. Umgekehrt wurde eine Luecke von einem hundertstel Millimeter
    korrekt gemeldet — die Erkennung war also genauer beim Getrennten als beim
    Beruehrenden.

    Der Fall entsteht nicht nur im Testkoerper: Eine Sanduhr, eine Pyramide
    auf der Spitze, zwei Kegel Spitze an Spitze. Ueberall dort verjuengt sich
    der Querschnitt auf einen Punkt, und darueber beginnt neues Material.

    Getragen wird, was eine **Flaeche** gemeinsam hat. Die Grenze dafuer ist
    ``EPS_GEOM`` und keine eigene Zahl (Regel 7).
    """
    from shapely.geometry import box as shapely_box

    from app.core.slice.analysis import _islands

    below = shapely_box(0.0, 0.0, 10.0, 10.0)

    edge = _islands(shapely_box(10.0, 0.0, 20.0, 10.0), below)
    corner = _islands(shapely_box(10.0, 10.0, 20.0, 20.0), below)
    overlapping = _islands(shapely_box(5.0, 5.0, 15.0, 15.0), below)

    assert not edge.is_empty, "eine Kante ohne Breite traegt nichts"
    assert not corner.is_empty, "eine Ecke noch weniger"
    assert overlapping.is_empty, "fuenf Millimeter Ueberlappung tragen"


# --- widths ---------------------------------------------------------------------


def test_the_smallest_structure_width_is_measured() -> None:
    from shapely.geometry import box as shapely_box

    assert minimum_width(shapely_box(0.0, 0.0, 10.0, 0.6)) == pytest.approx(0.6, rel=0.05)
    assert minimum_width(shapely_box(0.0, 0.0, 10.0, 2.0)) == pytest.approx(2.0, rel=0.05)


def test_above_the_interesting_width_it_stops_measuring() -> None:
    """§22.2 fragt, ob etwas zu dünn ist, nicht wie dick eine dicke Wand ist.

    Die Suche dort oben kostete mehr als der Rest der Schichtanalyse zusammen —
    eine breite Schicht wird also als „mindestens das" gemeldet, und das steht
    da, statt wie eine Messung auszusehen.
    """
    from shapely.geometry import box as shapely_box

    from app.core.slice.analysis import WIDTH_INTERESTING

    wide = minimum_width(shapely_box(0.0, 0.0, 40.0, 30.0))

    assert wide == pytest.approx(WIDTH_INTERESTING), "a lower bound, not the real 30 mm"
    assert minimum_width(shapely_box(0.0, 0.0, 40.0, 30.0), interesting_below=0.0) > 20.0


def test_a_thin_wall_is_found_across_the_body() -> None:
    wall = trimesh.creation.box(extents=(40.0, 0.8, 20.0))
    result = slice_body(on_bed(wall), 0.5)

    assert narrowest(result) == pytest.approx(0.8, rel=0.1)


def test_a_wall_above_the_cap_is_measured_when_the_question_reaches_higher() -> None:
    """Der Fund: zwischen Deckel und Frage lag ein Bereich ohne Antwort.

    ``WIDTH_INTERESTING`` deckelt bei 2,0 mm, die Frage daneben lautet „geht
    die Wand auf drei Bahnen auf" — an einer 0,8er-Düse sind das 2,55 mm. Eine
    Wand von 2,3 mm bekam damit weder eine Messung noch eine Antwort: gemeldet
    wurde der Deckel, und auf den Deckel wird zu Recht nicht gerechnet.

    Gefragt wird deshalb mit der Grenze, um die es geht — eine Zuordnung, kein
    toter Bereich.
    """
    wall = trimesh.creation.box(extents=(40.0, 2.3, 20.0))
    result = slice_body(on_bed(wall), 0.5)

    assert narrowest(result) == pytest.approx(WIDTH_INTERESTING), "gedeckelt, nicht gemessen"
    assert narrowest_measured(result) is None, "über dem Deckel gibt es keine Aussage"
    thin = narrowest_measured(result, interesting_below=3.0 * 0.85)
    assert thin is not None, "mit der gefragten Grenze ist die Wand messbar"
    assert thin == pytest.approx(2.3, rel=0.05)


def test_a_body_thicker_than_the_question_keeps_its_silence() -> None:
    """Die Gegenprobe: Die höhere Grenze macht aus einem Klotz keine dünne
    Stelle. Was auch dort oben nur den Deckel trifft, bleibt ohne Aussage."""
    block = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    result = slice_body(on_bed(block), 0.5)

    assert narrowest_measured(result, interesting_below=3.0 * 0.85) is None


def test_the_wall_generator_is_advised_for_a_wall_of_two_point_three() -> None:
    """Und dieselbe Wand an der Stelle, an der der Kunde es merkt (§29).

    2,3 mm gehen bei 0,85 mm Bahnbreite auf 2,7 Bahnen auf — der klassische
    Generator lässt dort eine Lücke, die nur Lückenfüllung schließt. Der
    Vorschlag blieb aus, weil die Messung vorher endete.
    """
    from app.core.knowledge import print_settings, profiles
    from app.core.slice import advise

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "layers.line_width", 0.85)
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    result = slice_body(on_bed(trimesh.creation.box(extents=(40.0, 2.3, 20.0))), 0.5)

    entries = advise.advise(settings, profile, result)

    assert "shell.wall_generator" in {entry.path for entry in entries}


# --- der Vertrag ----------------------------------------------------------------


def test_every_figure_is_marked_as_internal() -> None:
    """§22.5: nie mit einer aus G-Code gemessenen Größe vermischt."""
    result = slice_body(on_bed(trimesh.creation.box(extents=(10.0, 10.0, 10.0))), 0.5)
    assert result.source == "internal"


def test_the_contours_carry_their_holes() -> None:
    result = slice_body(corpus("plate_holes.stl"), 1.0)
    layer = result.layers[len(result.layers) // 2]

    assert layer.contours
    assert sum(len(contour.holes) for contour in layer.contours) == 4, "four bores, four holes"
    assert layer.area == pytest.approx(80.0 * 50.0 - 4 * math.pi * 2.6**2, rel=0.02)


def test_an_empty_body_slices_to_nothing() -> None:
    result = slice_body(MeshData.of(trimesh.Trimesh()), 0.2)
    assert result.layers == ()
    assert result.support_volume == 0.0


# --- Ein Teil dünner als eine Schichthöhe (§22.3) -------------------------------


def test_a_plate_thinner_than_a_layer_still_reports_its_footprint() -> None:
    """Der Fund aus dem Gesamtreview: eine flache Karte wurde hochkant gestellt.

    ``np.arange(low + layer_height/2, high, layer_height)`` ist leer, sobald ein
    Teil dünner als eine halbe Schichthöhe ist — ``low + layer_height/2`` liegt
    dann schon über ``high``. Ohne Schnitt gab es keine Schicht,
    ``first_layer_area`` fiel auf 0, und die Orientierungssuche verwirft eine
    Lage mit 0 mm² Grundfläche (§22.3). Bei der groben Suchschichthöhe von
    1,0 mm zeigt sich der Fehler: die 0,4-mm-Karte bekam nur hochkant überhaupt
    Schichten. Ihre Grundfläche muss die echten 1200 mm² tragen, nicht 0.
    """
    plate = trimesh.creation.box(extents=(40.0, 30.0, 0.4))
    result = slice_body(on_bed(plate), 1.0)

    assert result.layers, "ein Teil über EPS_GEOM bekommt mindestens einen Schnitt"
    assert result.first_layer_area == pytest.approx(1200.0, rel=TOLERANCE)
    assert result.support_volume == pytest.approx(0.0, abs=1.0)


def test_a_part_exactly_half_a_layer_thick_is_the_boundary() -> None:
    """Genau an der Schwelle: ``high - low == layer_height/2`` lässt das
    ``arange`` leer werden — ``low + layer_height/2 == high``, und die obere
    Grenze ist offen. Auch dieses Teil ist genau eine gedruckte Lage und muss
    seine Fläche melden.
    """
    plate = trimesh.creation.box(extents=(20.0, 20.0, 0.5))
    result = slice_body(on_bed(plate), 1.0)  # 0,5 == layer_height / 2

    assert result.layers
    assert result.first_layer_area == pytest.approx(400.0, rel=TOLERANCE)


def test_a_normal_part_keeps_its_first_cut_half_a_layer_up() -> None:
    """Gegenprobe: ein hohes Teil geht unverändert den gewöhnlichen Weg — viele
    Schichten, der erste Schnitt eine halbe Schicht über dem Boden.
    """
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 1.0)

    assert len(result.layers) == pytest.approx(20, abs=1)
    assert result.first_layer_area == pytest.approx(400.0, rel=TOLERANCE)
    assert result.layers[0].z == pytest.approx(0.5, abs=0.01), "erster Schnitt bei layer_height/2"


def test_the_search_lays_a_flat_plate_down_instead_of_standing_it_up() -> None:
    """Der Fund Ende zu Ende (§22.3): Mit ``first_layer_area == 0`` gewann die
    einzige Lage mit nicht-leerer Schichtliste — die hochkante. Jetzt trägt die
    liegende Lage ihre 1200 mm² und gewinnt gegen die 30-mm-hohe Kante.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 0.4)))
    found = search(plate, count=60, seed=3)

    assert found.mesh.bounds.size[2] == pytest.approx(0.4, abs=0.1), "flach auf der Platte"
    assert found.best.first_layer_area == pytest.approx(1200.0, rel=0.05)


def test_a_part_that_already_stands_without_support_is_not_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Steht die Ausgangslage schon stützfrei, schneidet die Suche keine zweite Lage.

    Der Filamenthalter (offener Kasten, 260 988 Dreiecke nach dem Aushöhlen)
    meldete am 06.09.2026 in jeder der 200 Lagen null Stützraum — und die
    Suche verglich eine halbe Stunde lang Nullen, während der Kunde auf das
    Öffnen wartete. Gezählt wird, wie oft geschnitten wird.
    """
    from app.core.slice import orientation

    calls: list[object] = []
    original = orientation.judge

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(orientation, "judge", counting)
    box = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 20.0)))
    found = search(box, count=200, seed=1)

    assert len(calls) == 1, "nur die Ausgangslage wurde geschnitten"
    assert found.tried == 1
    assert found.best.support_volume == 0.0
    searched = next(f for f in found.findings if f.code == "orient.searched")
    assert searched.values["sliced"] == 1


def test_the_search_slices_only_the_finalists_of_the_footprint_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Heuristik sortiert vor, die Schichtanalyse sieht nur noch die Finalisten.

    „Meistens entscheidet die unterste Schicht" (Robert, 06.09.2026): Standfläche
    und Überhang aus den Flächennormalen ordnen alle Richtungen, geschnitten
    werden höchstens ``FINALISTS`` plus die Ausgangslage — statt aller 200.
    """
    from app.core.slice import orientation

    calls: list[object] = []
    original = orientation.judge

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(orientation, "judge", counting)
    # Ein Pilz: Hut oben auf dem Stiel, also braucht die Ausgangslage Stützen.
    cap = trimesh.creation.box(extents=(40.0, 40.0, 4.0))
    cap.apply_translation((0.0, 0.0, 22.0))
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    mushroom = MeshData.of(trimesh.util.concatenate([cap, stem]))
    found = search(mushroom, count=200, seed=2)

    assert 1 < len(calls) <= orientation.FINALISTS + 1
    searched = next(f for f in found.findings if f.code == "orient.searched")
    assert searched.values["candidates"] > searched.values["sliced"]
    assert found.best.support_volume < found.baseline.support_volume, "der Hut liegt jetzt unten"


def test_a_standing_plate_is_laid_down_by_the_search() -> None:
    """Die Vorauswahl findet die flache Lage — und die Schichtanalyse bestätigt sie."""
    plate = trimesh.creation.box(extents=(40.0, 30.0, 0.4))
    plate.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    standing = MeshData.of(plate)
    assert standing.bounds.size[2] > 20.0, "sie steht wirklich"

    found = search(standing, count=60, seed=3)

    assert found.mesh.bounds.size[2] == pytest.approx(0.4, abs=0.1), "flach auf der Platte"
    assert found.best.first_layer_area == pytest.approx(1200.0, rel=0.05)


def test_a_dense_body_is_judged_on_a_smaller_twin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Über der Dreiecksgrenze urteilt die Suche an einem dezimierten Netz, dreht aber das echte."""
    from app.core.slice import orientation

    seen: list[int] = []
    original = orientation.decimate

    def recording(mesh: MeshData, target: int) -> MeshData:
        seen.append(mesh.triangle_count)
        return original(mesh, target)

    monkeypatch.setattr(orientation, "decimate", recording)
    dense = trimesh.creation.icosphere(subdivisions=5, radius=15.0)
    dense = trimesh.util.concatenate([dense, trimesh.creation.box(extents=(60.0, 60.0, 2.0))])
    body = MeshData.of(dense)
    assert body.triangle_count > orientation.SEARCH_TRIANGLES

    found = search(body, count=24, seed=4)

    assert seen and seen[0] == body.triangle_count, "das volle Netz ging in die Dezimierung"
    assert found.mesh.triangle_count == body.triangle_count, "gedreht wird das echte Netz"


def test_a_layer_height_of_zero_is_refused() -> None:
    """Und zwar mit einem Satz, den ein Kunde lesen kann (Regel 17).

    Hier stand ``ValueError("layer height has to be positive")`` — englisch,
    ohne Handlungsvorschlag, und erreichbar: Die Schichthöhe kommt aus dem
    Druckerprofil, und ein eigenes ``printers.toml`` bringt sie bis hierher.
    """
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        slice_body(on_bed(trimesh.creation.box(extents=(10.0, 10.0, 10.0))), 0.0)

    assert raised.value.suggestions, "jede Ausnahme trägt einen Handlungsvorschlag"
    assert "Schichthöhe" in str(raised.value.detail)


# --- Ein Schnitt mit einem Loch mitten darin ------------------------------------


def hollow_box() -> MeshData:
    """Eine oben offene Box: 60 × 40 × 30 außen, 3 mm Wände, 1,5 mm Boden."""
    outer = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    inner = trimesh.creation.box(extents=(54.0, 34.0, 27.0))
    inner.apply_translation((0.0, 0.0, 16.5))
    return MeshData.of(trimesh.boolean.difference([outer, inner]))


def test_a_wall_ring_is_a_section_and_not_nothing() -> None:
    """Die Regression: ein zentrierter Hohlraum ließ den ganzen Schnitt
    verschwinden.

    Die Verschachtelung fragte, ob ein Stück in einem anderen liegt, indem sie
    einen Punkt seiner *Außenlinie* nahm. Bei einer Box ist diese Außenlinie
    das äußere Rechteck, und dessen Mitte liegt im Hohlraum — Wand und Hohlraum
    erklärten einander also zum jeweiligen Loch, beide zählten als Loch, und
    ein Schnitt, den es offensichtlich gibt, kam als ``None`` zurück. Jede
    Schicht jedes hohlen Körpers war betroffen; der bestehende Korpus verbarg
    es, weil seine Bohrungen außermittig sitzen.
    """
    box = hollow_box()

    for z in (5.0, 15.0, 29.9):
        section = cross_section(box, z)
        assert section is not None, f"the wall at z={z} is material"
        assert section.area == pytest.approx(60.0 * 40.0 - 54.0 * 34.0, rel=TOLERANCE)
        assert len(section.interiors) == 1, "the cavity is the hole of the ring"


def test_a_solid_layer_stays_solid() -> None:
    """Unter dem Hohlraum ist derselbe Körper ein volles Rechteck — kein Loch
    erfunden.
    """
    section = cross_section(hollow_box(), 1.0)

    assert section is not None
    assert section.area == pytest.approx(2400.0, rel=TOLERANCE)
    assert not section.interiors


def test_a_centred_bore_is_a_hole_not_a_disappearance() -> None:
    """Derselbe Fehler in seiner kleinsten Form: eine Platte, eine Bohrung, in
    der Mitte.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 8.0))
    bore = trimesh.creation.cylinder(radius=5.0, height=20.0, sections=128)
    body = MeshData.of(trimesh.boolean.difference([plate, bore]))

    section = cross_section(body, 0.0)

    assert section is not None
    assert section.area == pytest.approx(1600.0 - math.pi * 25.0, rel=0.02)


def test_a_hole_touching_its_own_wall_does_not_stop_the_slicer() -> None:
    """Eine Tasche, die exakt bis an die Außenwand reicht.

    Das Loch trifft die Hülle dann in einem Punkt, das Polygon ist ungültig,
    und GEOS wirft bei der nächsten Operation darüber — nicht hier, sondern
    drei Ebenen höher, mit einer Koordinate und ohne Namen. Drei Modelle des
    Korpus tun genau das.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    pocket = trimesh.creation.box(extents=(20.0, 20.0, 6.0))
    # Ihre rechte Fläche sitzt exakt auf der rechten Fläche der Platte.
    pocket.apply_translation((10.0, 0.0, 7.0))
    body = MeshData.of(trimesh.boolean.difference([plate, pocket]))

    section = cross_section(body, 6.0)

    assert section is not None
    assert section.is_valid, "a section that cannot be measured is worse than none"
    assert section.area == pytest.approx(1600.0 - 20.0 * 20.0, rel=TOLERANCE)


def test_a_shared_edge_is_cut_at_the_same_point_from_both_sides() -> None:
    """Der Fall, der einem Besteckkorb Stützen verschrieben hätte.

    Eine Kante gehört zwei Dreiecken, und jedes benennt sie in seiner eigenen
    Richtung. ``A + (B-A)*f`` und ``B + (A-B)*f'`` sind dieselbe Stelle, aber
    nicht dasselbe Fließkommamuster — und wenn der Wert auf einer
    Rundungsgrenze liegt, kippen die beiden Ergebnisse auf verschiedene
    Seiten. Die Enden finden nicht mehr zusammen, der Ring bleibt offen,
    ``polygonize`` lässt ihn fallen, und das Fach, das er umschloss, fehlt der
    Schicht als Loch.

    Die Zahlen hier sind nicht erfunden: es ist die Trennwand eines
    eingelesenen Besteckkorbs, deren Diagonale bei z = 70,9 genau bei
    34,9796875 geschnitten wird. Vorwärts gerechnet endet das auf
    ...875, rückwärts auf ...8749999 — nach dem Runden auf sechs Stellen ein
    Unterschied von eins in der letzten. In dem Modell traf das 31 von 800
    Schichten, die daraufhin die fünffache Querschnittsfläche und 9 463 mm²
    Überhang meldeten, den es nicht gibt.
    """
    # Eine Wand in y = 52,7 — als Rechteck aus zwei Dreiecken, deren gemeinsame
    # Diagonale genau die kritische Kante ist.
    y_front, y_back = 52.70000076293945, 55.70000076293945
    x_left, x_right, z_low, z_high = 3.0, 108.5, 4.0, 100.0
    corners = np.array(
        [
            [x_right, y_front, z_low],  # 0 — Anfang der Diagonale
            [x_left, y_front, z_high],  # 1 — ihr Ende
            [x_left, y_front, z_low],
            [x_right, y_front, z_high],
            [x_right, y_back, z_low],
            [x_left, y_back, z_high],
            [x_left, y_back, z_low],
            [x_right, y_back, z_high],
        ]
    )
    faces = np.array(
        [
            [0, 1, 2],
            [1, 0, 3],  # Vorderseite, geteilt entlang der Diagonale 0-1
            [4, 6, 5],
            [5, 7, 4],  # Rückseite
            [2, 6, 4],
            [4, 0, 2],  # unten
            [1, 5, 6],
            [6, 2, 1],  # links
            [3, 7, 5],
            [5, 1, 3],  # oben
            [0, 4, 7],
            [7, 3, 0],  # rechts
        ]
    )
    wall = trimesh.Trimesh(vertices=corners, faces=faces, process=False)
    assert wall.is_watertight, "der Prüfkörper selbst muss geschlossen sein"

    section = cross_section(MeshData.of(wall), 70.9)

    assert section is not None, "eine Wand, die es gibt, kommt nicht als nichts zurück"
    breite = (y_back - y_front) * (x_right - x_left)
    assert section.area == pytest.approx(breite, rel=TOLERANCE)


# --- freie Spannweiten (§22.2) --------------------------------------------------


def test_a_shelf_over_a_hollow_reports_its_free_span() -> None:
    """Der Fall, der einen Satz Gewürzbehälter gekostet hat.

    Ein Becher, dessen Innenraum sich auf einer Höhe sprunghaft verengt, hat
    dort eine waagerechte Ringschulter. Der Slicer überspannt sie nicht entlang
    des Rings, sondern mit geraden Bahnen quer über die ganze Öffnung — beim
    Behälter waren das 24,7 mm frei hängender Faden. Die Zahl wurde gemessen
    und nirgends aufgehoben; jetzt steht sie in der Schicht.
    """
    outer = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=64)
    outer.apply_translation((0.0, 0.0, 20.0))
    wide = trimesh.creation.cylinder(radius=16.0, height=20.0, sections=64)
    wide.apply_translation((0.0, 0.0, 12.0))
    narrow = trimesh.creation.cylinder(radius=10.0, height=22.0, sections=64)
    narrow.apply_translation((0.0, 0.0, 31.0))
    body = MeshData.of(trimesh.boolean.difference([outer, wide, narrow]))

    result = slice_body(body, 0.2)
    spans = [layer for layer in result.layers if layer.bridge_width > 1.0]

    assert spans, "the shoulder at z=22 spans free air and has to be measured"
    worst = max(spans, key=lambda layer: layer.bridge_width)
    assert worst.z == pytest.approx(22.0, abs=0.3)
    # Frei hängt die Bahn über der Öffnung, die die Schulter umschließt — also
    # über deren Durchmesser, nicht über der Breite der Schulter selbst.
    assert worst.bridge_width == pytest.approx(20.0, rel=0.1)


def test_a_cable_duct_spans_its_narrow_side_not_its_long_one() -> None:
    """Gemessen wird die **kürzeste** freie Spannweite, nicht die Ausdehnung.

    Ein Kabelkanal, dessen Decke über einem Hohlraum von 30 auf 8 mm liegt,
    stand mit 30 mm im Bericht: Genommen wurde die größere Seite des
    Hüllrechtecks. Der Slicer legt seine Bahnen aber quer über die schmale
    Seite — acht Millimeter, und die überspannt jede Düse. Aus einer Decke, die
    problemlos druckt, wurde so eine Warnung, die zu Stützen riet.
    """
    outer = trimesh.creation.box(extents=(40.0, 20.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    cavity = trimesh.creation.box(extents=(30.0, 8.0, 8.0))
    cavity.apply_translation((0.0, 0.0, 6.0))
    body = MeshData.of(trimesh.boolean.difference([outer, cavity]))

    result = slice_body(body, 0.2)
    spans = [layer for layer in result.layers if layer.bridge_width > 1.0]

    assert spans, "die Decke über dem Kanal spannt frei und muss gemessen werden"
    worst = max(spans, key=lambda layer: layer.bridge_width)
    assert worst.z == pytest.approx(10.0, abs=0.3)
    assert worst.bridge_width == pytest.approx(8.0, rel=0.15)


def test_a_forty_five_degree_transition_spans_nothing() -> None:
    """Derselbe Becher mit kegeligem Übergang — die Zahl geht auf null.

    Das ist die Gegenprobe zum Test darüber und zugleich der Nachweis, dass
    die Änderung am Modell wirkt: bei 45 Grad kragt jede Schicht eine halbe
    Linienbreite vor und trägt sich selbst.
    """
    outer = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=64)
    outer.apply_translation((0.0, 0.0, 20.0))
    profile = np.array(
        [
            [0.0, 2.0],
            [16.0, 2.0],
            [16.0, 16.0],
            [10.0, 22.0],
            [10.0, 42.0],
            [0.0, 42.0],
        ]
    )
    cavity = trimesh.creation.revolve(profile, sections=64)
    body = MeshData.of(trimesh.boolean.difference([outer, cavity]))

    result = slice_body(body, 0.2)

    assert max(layer.bridge_width for layer in result.layers) < 1.0
