"""Analysekarten (Bauplan §18.4).

Jede Karte wird gegen einen Körper geprüft, dessen Antwort vorher feststeht —
eine Platte ist 8 mm dick, ein Würfel hat keinen Überhang, ein Kegel auf der
Seite reichlich.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom import repair as repair_module
from app.core.geom.measure import wall_thickness
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, place_on_bed, rotation
from app.core.ingest.loader import normalise
from app.core.perceive import maps
from app.core.perceive.features import detect
from app.core.types import (
    Feature,
    FeatureRef,
    Finding,
    Fit,
    Profile,
    Report,
    Scene,
    SceneObject,
    SurfacePatch,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def _deviation_entry() -> SceneObject:
    """Drei Originaldreiecke auf z=0/4/8; nur das erste und letzte sind zugeordnet."""
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=[(x, y, z) for z in (0.0, 4.0, 8.0) for x, y in ((0, 0), (2, 0), (0, 2))],
            faces=[(0, 1, 2), (3, 4, 5), (6, 7, 8)],
            process=False,
        )
    )
    patch = SurfacePatch(
        "plane", {"centre": (0.0, 0.0, 1.0), "axis": (0.0, 0.0, 1.0)}, (2, 0), "facets"
    )
    feature = Feature(
        "compound", "curved_face", "detected", {}, (0, 1, 2), surface_patches=(patch,)
    )
    return SceneObject("obj_1", "Prüfflächen", mesh, features={feature.id: feature})


def test_deviation_map_keeps_original_order_known_coverage_and_a_real_witness() -> None:
    """Die Formabweichung hält die Dreiecksreihenfolge, zählt Unbekanntes als NaN und zeigt auf ein
    wirkliches Dreieck: Zeuge, Ort und Abstand gehören zum größten belegten Wert, das Intervall
    umschließt ihn.
    """
    entry = _deviation_entry()
    before = entry.mesh.raw.vertices.copy(), entry.mesh.raw.faces.copy()
    updates = []
    analysis = maps.build(
        "deviation", entry, progress=lambda fraction, _text: updates.append(fraction)
    )
    assert analysis.values[0] == pytest.approx(1.0)
    assert math.isnan(analysis.values[1])
    assert analysis.values[2] == pytest.approx(7.0)
    assert analysis.unknown_count == 1
    assert analysis.maximum_interval[0] <= 7.0 <= analysis.maximum_interval[1]
    assert analysis.numerical_error < 1e-10
    assert analysis.witness_face == 2
    assert analysis.witness_point[2] == pytest.approx(8.0)
    assert analysis.witness_distance <= 7.0
    assert maps.focus_point(entry, analysis) == analysis.witness_point
    assert np.array_equal(entry.mesh.raw.vertices, before[0])
    assert np.array_equal(entry.mesh.raw.faces, before[1])
    assert updates[0] == pytest.approx(0.0) and updates[-1] == pytest.approx(1.0)
    assert updates == sorted(updates)


def test_conflicting_surface_claims_remain_unknown_and_identical_ones_do_not() -> None:
    """Zwei Flächen, die dasselbe Dreieck mit verschiedenen Ebenen beanspruchen, machen es
    unbekannt; zwei mit derselben Ebene nicht.
    """
    entry = _deviation_entry()
    original = entry.features["compound"]
    repeated = replace(original, id="same")
    conflict = SurfacePatch(
        "plane", {"centre": (0.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)}, (2,), "facets"
    )
    disputed = replace(original, id="different", face_indices=(2,), surface_patches=(conflict,))
    entry.features = {feature.id: feature for feature in (original, repeated, disputed)}
    analysis = maps.build("deviation", entry)
    assert analysis.values[0] == pytest.approx(1.0)
    assert analysis.unknown_count == 2
    assert analysis.witness_face == 0
    assert analysis.maximum_interval[0] <= 1.0 <= analysis.maximum_interval[1]


@pytest.mark.parametrize("missing", [True, False])
def test_unproved_surface_map_has_no_zero_claim_or_location(missing: bool) -> None:
    """Ohne belegte Fläche gibt es keine Null als Abweichung, kein Intervall, keinen Zeugen und
    keinen Ort, auf den ein Befund zeigen könnte — nur Unbekanntes.
    """
    entry = _deviation_entry()
    original = entry.features["compound"]
    invalid = replace(original.surface_patches[0], params={"centre": (0.0, 0.0, 0.0)})
    entry.features = {} if missing else {original.id: replace(original, surface_patches=(invalid,))}
    analysis = maps.build("deviation", entry)
    assert analysis.unknown_count == entry.mesh.triangle_count
    assert not analysis.known
    assert analysis.maximum_interval is None and analysis.numerical_error is None
    assert analysis.witness_point is None and analysis.witness_face is None
    assert maps.focus_point(entry, analysis) is None
    finding = Finding("perceive.deviation", "info", "Prüfen", object_id=entry.id)
    assert maps.map_for(finding) == "deviation"
    assert maps.location_of(entry, finding) is None


@pytest.mark.parametrize("source", ["native", "facets", "fit"])
def test_deviation_source_comes_from_evaluated_patch_not_body_kind(source: str) -> None:
    """Woher die Bezugsfläche stammt — exakte Fläche, eingepasste Fläche, geprüfte Ebene —, sagt
    die Fläche selbst, nicht die Bauart des Körpers; die Karte nennt es in ihrer Notiz.
    """
    entry = _deviation_entry()
    original = entry.features["compound"]
    entry.features = {
        original.id: replace(
            original, surface_patches=(replace(original.surface_patches[0], source=source),)
        )
    }
    analysis = maps.build("deviation", entry)
    expected = {
        "native": "ursprüngliche exakte Flächen",
        "facets": "geprüfte Ebenen der Originaldreiecke",
        "fit": "bereits eingepasste Flächen",
    }
    assert expected[source] in str(analysis.note)


def test_identical_carriers_keep_all_used_sources_and_ignore_only_unknown_sources() -> None:
    """Trägt ein Körper Flächen mehrerer Herkünfte, nennt die Notiz jede benutzte und keine
    unbenutzte; ein Dreieck ohne belegte Fläche bleibt das eine Unbekannte.
    """
    entry = _deviation_entry()
    original = entry.features["compound"]
    plane = original.surface_patches[0]
    native = replace(plane, face_indices=(0,), source="native")
    fitted = replace(plane, face_indices=(2,), source="fit")
    unknown = replace(plane, face_indices=(1,), source="facets")
    conflict = replace(
        unknown, source="fit", params={"centre": (0.0, 0.0, 3.0), "axis": (0.0, 0.0, 1.0)}
    )
    entry.features = {
        original.id: replace(original, surface_patches=(native, fitted, unknown, conflict))
    }
    analysis = maps.build("deviation", entry)
    assert analysis.unknown_count == 1
    assert "ursprüngliche exakte Flächen" in str(analysis.note)
    assert "bereits eingepasste Flächen" in str(analysis.note)
    assert "geprüfte Ebenen der Originaldreiecke" not in str(analysis.note)


def test_deviation_measures_the_filled_triangle_instead_of_its_vertices_or_centre() -> None:
    """Alle Ecken liegen auf R1; der größte Abstand 1 liegt auf der gefüllten Kante."""
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=[(1, 0, 0), (-1, 0, 0), (0, 1, 0)], faces=[(0, 1, 2)], process=False
        )
    )
    patch = SurfacePatch("sphere", {"centre": (0.0, 0.0, 0.0), "radius": 1.0}, (0,), "fit")
    feature = Feature("sphere", "sphere", "detected", {}, (0,), surface_patches=(patch,))
    entry = SceneObject("obj_1", "Kugelfacette", mesh, features={feature.id: feature})
    analysis = maps.build("deviation", entry)
    assert analysis.maximum_interval[0] <= 1.0 <= analysis.maximum_interval[1]
    assert analysis.values[0] == pytest.approx(1.0, abs=1e-8)
    assert analysis.witness_distance == pytest.approx(1.0, abs=1e-8)
    assert analysis.witness_point == pytest.approx((0.0, 0.0, 0.0), abs=1e-8)


def test_equal_deviation_extrema_never_point_between_disconnected_faces() -> None:
    """Zwei getrennte Flächen mit gleich großer Abweichung: Der Zeuge liegt auf einer von beiden,
    nie dazwischen — und der Kamerapunkt ist der Zeuge.
    """
    entry = _deviation_entry()
    feature = entry.features["compound"]
    patch = replace(
        feature.surface_patches[0], params={"centre": (0.0, 0.0, 4.0), "axis": (0.0, 0.0, 1.0)}
    )
    entry.features = {feature.id: replace(feature, surface_patches=(patch,))}
    analysis = maps.build("deviation", entry)
    assert analysis.witness_face in (0, 2)
    assert analysis.witness_point[2] == pytest.approx(0.0 if analysis.witness_face == 0 else 8.0)
    assert analysis.witness_distance == pytest.approx(4.0)
    assert maps.focus_point(entry, analysis) == analysis.witness_point


@pytest.mark.parametrize("when", [0.0, 0.1, 0.99, 1.0])
def test_deviation_progress_cancellation_never_returns_a_partial_map(when: float) -> None:
    """Ein Abbruch zu jedem Zeitpunkt des Fortschritts liefert keine halbe Karte, sondern die
    Ausnahme.
    """
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    token = CancelSignal()

    def progress(fraction: float, _text: str) -> None:
        if fraction >= when:
            token.cancel()

    with pytest.raises(OperationCancelled):
        maps.build("deviation", _deviation_entry(), cancelled=token, progress=progress)


def plate() -> MeshData:
    """80 × 50 × 8 mm mit vier Bohrungen."""
    return place_on_bed(
        normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    )


def cube() -> MeshData:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def object_with(mesh: MeshData) -> SceneObject:
    return SceneObject(id="obj_1", name="Prüfkörper", mesh=mesh, features=detect(mesh))


# --- wall thickness -------------------------------------------------------------


@pytest.mark.parametrize("kind", ["wall", "support"])
@pytest.mark.parametrize("width", [0.26, 0.84])
def test_distance_maps_sample_the_actual_printer_width(profile, kind, width) -> None:
    """Beide Karten nennen die Auflösung des wirklichen Druckerprofils."""
    mesh = cube()
    selected = replace(profile, printer=replace(profile.printer, extrusion_width=width))
    analysis = maps.build(kind, object_with(mesh), profile=selected)
    expected = max(width / 2.0, mesh.bounds.diagonal / maps.MAX_GRID_STEPS)
    assert analysis.resolution == pytest.approx(expected)


def test_a_profile_free_distance_grid_depends_on_geometry() -> None:
    """Ohne Drucker begrenzt die Modellgröße das Raster, keine angenommene Düse."""
    mesh = cube()
    assert maps.default_pitch(mesh) == pytest.approx(mesh.bounds.diagonal / maps.MAX_GRID_STEPS)


def test_the_wall_map_measures_the_plate(profile: Profile) -> None:
    """Die Wandstärkenkarte einer Platte trägt je Dreieck einen Wert in Millimetern, nennt ihre
    Auflösung und misst die Dicke der Platte darin.
    """
    entry = object_with(plate())
    analysis = maps.build("wall", entry, profile=profile)

    assert len(analysis.values) == entry.mesh.triangle_count
    assert analysis.unit == "mm"
    assert analysis.resolution is not None, "a sampled number says how fine it was sampled"
    # An der großen Fläche gemessen: 8 mm Material darunter. Die Toleranz ist ein
    # Rasterschritt, denn das ist, was das Raster unterscheiden kann.
    for index in entry.features["face_1"].face_indices:
        assert analysis.values[index] == pytest.approx(8.0, abs=analysis.resolution)


def test_the_wall_map_marks_what_is_too_thin(profile: Profile) -> None:
    """§39: zwei Extrusionsbreiten sind der Boden, und die Karte sagt, wo er
    unterschritten wird.
    """
    thin = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 0.5)))
    analysis = maps.build("wall", object_with(thin), profile=profile)

    assert analysis.threshold == pytest.approx(profile.minimum_wall_thickness)
    assert analysis.highlighted, "half a millimetre is below two extrusion widths"


def test_the_wall_scale_ends_where_the_question_ends(profile: Profile) -> None:
    """An einer Stirnfläche misst der Strahl quer durch das ganze Teil.

    Bei einem Brett von 8 mm Dicke und 80 mm Länge spannte die Legende damit
    über 80 mm — und der Bereich, um den es beim Drucken geht (unter zwei
    Extrusionsbreiten), fiel in eine einzige Farbstufe. Die Karte konnte ihre
    eigene Frage nicht beantworten.
    """
    long_plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    analysis = maps.build("wall", object_with(long_plate), profile=profile)

    assert max(analysis.known) > 40.0, "gemessen wird weiterhin, was da ist"
    assert analysis.high <= profile.minimum_wall_thickness * maps.WALL_SCALE_FACTOR
    assert analysis.high < max(analysis.known), "die Skala endet vor dem Höchstwert"
    assert "Skala" in str(analysis.note), "und sie sagt, dass sie das tut"


def test_a_map_explains_what_it_cannot_say(profile: Profile) -> None:
    """Die Fußzeile zählte sie („17 × nicht bestimmbar") und ließ die Zahl
    unerklärt stehen."""
    half = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    half.faces = half.faces[:6]
    analysis = maps.wall_thickness_map(MeshData.of(half))

    assert analysis.unknown_count, "sonst prüft dieser Test nichts"
    assert analysis.unknown_note, "und wer nichts sagen kann, sagt warum"


def test_an_open_body_says_it_cannot_say() -> None:
    """Eine halbe Box hat kein Innen — und keine Dicke. Null wäre eine Lüge."""
    open_body = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    open_body.raw.faces = open_body.raw.faces[:6]
    analysis = maps.wall_thickness_map(open_body)

    assert analysis.unknown_count > 0
    assert all(not math.isnan(value) for value in analysis.known)


def test_the_map_agrees_with_the_measuring_tool() -> None:
    """§18.3 und §18.4 müssen dieselbe Antwort geben, sonst lügt eine von
    beiden.
    """
    body = plate()
    analysis = maps.wall_thickness_map(body)
    assert analysis.resolution is not None

    centres = body.raw.triangles_center
    for index in (0, 5, 11):
        point = (float(centres[index][0]), float(centres[index][1]), float(centres[index][2]))
        measured = wall_thickness(body, point, direction=tuple(-body.raw.face_normals[index]))
        if measured is None or math.isnan(analysis.values[index]):
            continue
        assert analysis.values[index] == pytest.approx(measured, abs=2.0 * analysis.resolution)


def test_a_thick_block_is_thick_everywhere() -> None:
    """Ein massiver Klotz hat nirgends eine dünne Stelle."""
    block = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    analysis = maps.wall_thickness_map(block)

    assert analysis.resolution is not None
    assert min(analysis.known) == pytest.approx(20.0, abs=2.0 * analysis.resolution)


def test_inward_traces_finish_at_the_first_gap_or_the_step_limit() -> None:
    """Verschiedene Austritte werden einmal gezählt; Material hinter einer Lücke nicht."""
    from types import SimpleNamespace

    filled = np.zeros((6, 6, 3), dtype=bool)
    filled[1:6, 1, 1] = True
    filled[3:6, 2, 1] = True
    filled[1, 2, 1] = True  # hinter der Lücke: gehört nicht zur ersten Wand
    filled[:, 4, 1] = True  # bleibt bis zur Schrittgrenze im Material
    body = SimpleNamespace(
        triangles_center=np.asarray([[5.5, y, 1.0] for y in (1, 2, 3, 4)]),
        face_normals=np.asarray([[1.0, 0.0, 0.0]] * 4),
        scale=8.0,
    )
    field = maps.SolidField(filled=filled, origin=np.zeros(3), pitch=1.0)

    values = maps._inward_thickness(body, field)

    assert values[:2] == [5.0, 3.0]
    assert math.isnan(values[2]), "sofort außerhalb bleibt unbekannt statt null"
    assert values[3] == 10.0, "Skala 8 / Raster 1 plus die zwei Randabfragen"


# --- overhang -------------------------------------------------------------------


def test_a_cube_has_no_overhang_worth_the_name() -> None:
    """Senkrechte Wände und ein Boden auf der Platte: Die Überhangkarte eines Würfels hebt nichts
    hervor.
    """
    analysis = maps.overhang_map(cube())

    assert analysis.unit == "°"
    # The underside faces straight down, everything else stands vertical.
    assert {round(value) for value in analysis.values} <= {0, 90}
    assert analysis.threshold == 45.0
    assert analysis.highlighted == (), "der Boden liegt auf der Platte und braucht keine Stütze"


def test_a_finely_meshed_box_on_the_bed_needs_no_support_but_a_shelf_does() -> None:
    """Ein Boden aus vielen Dreiecken zählt so wenig wie einer aus zwei.

    Nach *Dreiecke angleichen* meldete die Formsitzung an einem schlichten
    Quader „454 Flächen brauchen möglicherweise Stützen“ — gezählt waren die
    Dreiecke seines Bodens (Fensterabnahme RM-366). Die Unterseite eines
    Kragarms über der Platte bleibt markiert.
    """
    import shapely.geometry

    box = trimesh.creation.box(extents=(200.0, 60.0, 20.0))
    box.apply_translation((0.0, 0.0, 10.0))
    for _ in range(4):
        box = box.subdivide()
    fine = maps.overhang_map(MeshData.of(box))
    bottom = np.isclose(np.asarray(box.triangles_center)[:, 2], 0.0)
    assert int(bottom.sum()) > 100, "der Boden besteht aus vielen Dreiecken"
    assert fine.highlighted == ()

    profile = shapely.geometry.Polygon(
        [(-5, 0), (5, 0), (5, 10), (20, 10), (20, 15), (-20, 15), (-20, 10), (-5, 10)]
    )
    tee = trimesh.creation.extrude_polygon(profile, 10.0)
    tee.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
    shelf = maps.overhang_map(MeshData.of(tee))
    centres = np.asarray(tee.triangles_center)[list(shelf.highlighted)]
    assert shelf.highlighted, "die Unterseite des Kragarms hängt über"
    assert np.allclose(centres[:, 2], 10.0), "markiert ist nur, was über der Platte hängt"


def test_the_overhang_legend_names_the_limit_it_highlights() -> None:
    """Die Legende nennt die Grenze, nach der die Karte wirklich hervorhebt.

    Die Grenze kommt aus dem Profil (``analysis_limits``): Ein kalibriertes
    Material trägt seinen gemessenen Überhangwinkel. Die Legende stand bis zum
    22.09.2026 fest auf „Über 45 Grad …“ — bei einem Material, das 55 Grad
    trägt, markierte die Karte ab 55 und die Zeile darunter sagte 45.
    """
    from app.i18n import format_decimal

    steep = maps.overhang_map(cube(), 55.0)
    assert steep.threshold == 55.0
    assert format_decimal(55.0, digits=0) in str(steep.note)
    assert "45" not in str(steep.note)
    assert format_decimal(45.0, digits=0) in str(maps.overhang_map(cube()).note)


def test_a_tilted_face_is_measured_not_guessed() -> None:
    """Um 30 Grad gedreht steht die Unterseite auf 60 und eine Seite auf 30."""
    tilted = apply(cube(), rotation("x", 30.0))
    analysis = maps.overhang_map(tilted)

    assert max(analysis.values) == pytest.approx(60.0, abs=0.5)
    assert any(value == pytest.approx(30.0, abs=0.5) for value in analysis.values)


def test_steep_faces_are_the_ones_highlighted() -> None:
    """Nur Flächen, die steiler nach unten zeigen als die Überhanggrenze, werden markiert — ein
    Kegel auf seiner Grundfläche hängt mit 63 Grad über.
    """
    cone = MeshData.of(trimesh.creation.cone(radius=20.0, height=10.0, sections=32))
    analysis = maps.overhang_map(apply(cone, rotation("x", 180.0)))

    assert analysis.highlighted, "a cone on its base overhangs at 63 degrees"
    for index in analysis.highlighted:
        assert analysis.values[index] > 45.0


# --- mesh defects ---------------------------------------------------------------


def test_the_defect_map_finds_the_open_edges() -> None:
    """Die Fehlerkarte markiert die Dreiecke an den offenen Kanten eines Netzes mit Loch."""
    broken = normalise(
        read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm", mend=False
    ).mesh
    analysis = maps.defect_map(broken)

    assert analysis.highlighted, "the missing wall leaves open edges behind"
    assert analysis.categories[1] == "Loch"


def test_a_clean_body_has_a_clean_map() -> None:
    """Ein geschlossener Körper ohne Fehler hat eine Fehlerkarte, die nichts hervorhebt."""
    analysis = maps.defect_map(cube())

    assert analysis.highlighted == ()
    assert set(analysis.values) == {0.0}
    # Einfarbig allein sagte nichts; die Leiste nennt das Ergebnis.
    assert str(analysis.note) == "Keine Netzfehler gefunden."


def test_an_incomplete_defect_search_does_not_clear_unchecked_faces(monkeypatch) -> None:
    """Eine begrenzte Suche ist keine Entwarnung für die restliche Oberfläche."""
    monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)
    analysis = maps.defect_map(cube())

    assert analysis.unknown_count == len(analysis.values)
    assert analysis.highlighted == ()
    assert analysis.note and analysis.unknown_note


def test_an_incomplete_defect_search_keeps_proven_boundary_errors(monkeypatch) -> None:
    """Ungeprüfte Durchdringungen verdecken keine belegten offenen Kanten."""
    monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)
    body = trimesh.creation.box()
    body.update_faces(np.arange(len(body.faces)) != 0)
    analysis = maps.defect_map(MeshData.of(body))

    assert analysis.highlighted
    assert all(analysis.values[index] >= 1.0 for index in analysis.highlighted)
    assert analysis.unknown_count > 0
    assert analysis.note


def test_a_partly_searched_defect_map_knows_what_it_checked(monkeypatch) -> None:
    """Unbekannt ist, was die Suche nicht erreicht hat — nicht alles.

    Bis zur Durchsicht färbte eine vorzeitig beendete Suche jede fehlerfreie
    Fläche grau, auch die schon geprüften (Befund B3 der Durchsicht
    24.09.2026). Eine Kugel aus 1 280 Dreiecken, mit einem Budget für einen
    Teil ihrer Paare: ein Teil geprüft, ein Teil unbekannt.
    """
    import math

    sphere = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 2000)

    analysis = maps.defect_map(MeshData.of(sphere))

    checked = sum(1 for value in analysis.values if not math.isnan(value))
    assert 0 < analysis.unknown_count < len(analysis.values)
    assert checked > 0, "was geprüft ist, steht als geprüft da"
    assert analysis.note


def test_the_defect_map_marks_where_the_body_runs_through_itself() -> None:
    """Bauplan §18.4 verspricht Durchdringungen, und die Karte fand keine (RM-143).

    Sie markierte offene und verzweigte Kanten — beides Topologie. Eine
    Selbstdurchdringung ist aber **räumlich**: Zwei Wände, die einander
    schneiden, haben lauter saubere Kanten mit je zwei Flächen, und die
    Kantentabelle sagt dazu gar nichts. `broken_selfint.stl` ist genau dieser
    Fall — zwei Quader, die durcheinanderlaufen, 24 Dreiecke, von keiner
    Booleschen angefasst.

    **Eine allgemeine Fehlermeldung ersetzt die Markierung nicht** (§18.4): Der
    Kunde soll die Stelle im Bild finden, nicht erfahren, dass es sie gibt.
    """
    broken = normalise(read_mesh((MESHES / "broken_selfint.stl").read_bytes(), ".stl"), "mm").mesh

    analysis = maps.defect_map(broken)

    durchdrungen = [index for index, value in enumerate(analysis.values) if value >= 3.0]
    assert durchdrungen, "die zwei Quader laufen durcheinander, und die Karte schweigt"
    assert set(durchdrungen) <= set(analysis.highlighted), "die Stellen sind nicht auffindbar"
    # Regel 18: Die Bedeutung steht als Wort daneben, nicht nur als Farbe.
    assert analysis.categories[3] == "Überschneidung"


def test_the_defect_map_pays_the_same_budget_as_the_repair(monkeypatch) -> None:
    """Karte und Reparatur sehen dasselbe, und die Suche läuft einmal (KUNDE-15).

    Die Karte deckelte ihre Überschneidungssuche fest bei zwei Millionen
    Paaren, die Reparatur bei einer Zahl je Dreieck. An den 358 Körpern aus
    ``F:\\3D Dateien`` bis zur Kartengrenze blieb die Karte deshalb an jedem ab
    349 000 Dreiecken unvollständig, während *Reparieren* dasselbe Netz ganz
    sah — und am Laptopständer stand in der Legende „33 140 × nicht
    bestimmbar". Jetzt fragt die Karte dasselbe Budget, und die Antwort liegt
    für die Reparatur danach im Cache des Netzes (``repair.crossings_of``).
    """
    from app.core.geom import intersections

    asked: list[int] = []
    budget = repair_module.intersection_budget

    def counted_budget(triangles: int) -> int:
        asked.append(triangles)
        return budget(triangles)

    searched: list[int | None] = []
    search = intersections.crossing_face_pairs

    def counted_search(*args, **kwargs):  # type: ignore[no-untyped-def]
        searched.append(kwargs.get("max_pairs"))
        return search(*args, **kwargs)

    monkeypatch.setattr(repair_module, "intersection_budget", counted_budget)
    monkeypatch.setattr(intersections, "crossing_face_pairs", counted_search)
    broken = normalise(read_mesh((MESHES / "broken_selfint.stl").read_bytes(), ".stl"), "mm").mesh

    analysis = maps.defect_map(broken)
    crossings = repair_module.crossings_of(broken)

    assert asked == [broken.triangle_count, broken.triangle_count], "dasselbe Budget"
    assert searched == [budget(broken.triangle_count)], "eine Suche für beide"
    assert crossings.complete and analysis.unknown_count == 0


def test_a_clean_body_is_not_called_self_intersecting() -> None:
    """Die Gegenprobe, und sie trägt den Wert des Ganzen.

    Ein Würfel schneidet sich nicht — würde die Prüfung ihn markieren, wäre
    die Karte Lärm statt Auskunft, und nach dem dritten Mal sieht niemand mehr
    hin.
    """
    analysis = maps.defect_map(cube())

    assert all(value < 3.0 for value in analysis.values)


# --- curvature ------------------------------------------------------------------


def test_the_curvature_map_shows_the_edges() -> None:
    """Ein Würfel hat nur Kanten und ebene Flächen — beide haben keinen Radius.

    Bis zum 22.08.2026 stand hier ``high == 90``, der Winkel einer Würfelkante
    in Grad. Die Karte misst jetzt den Radius, und die richtige Antwort für
    eine scharfe Kante ist **null** und nicht neunzig.
    """
    analysis = maps.curvature_map(cube())

    assert analysis.unit == "mm"
    assert analysis.high == pytest.approx(0.0, abs=0.01), "a cube edge is sharp"


def test_the_curvature_map_measures_the_fillet_and_not_the_mesh() -> None:
    """Die Frage aus §18.4 ist *wie* rund, nicht *dass* — und die alte Karte
    konnte sie nicht beantworten.

    Sie mass den schärfsten Winkel zu einem Nachbarn, und der wird kleiner, je
    feiner eine Verrundung vernetzt ist, obwohl ihr Radius derselbe bleibt.
    Gemessen wird hier deshalb an **zwei** Vernetzungen desselben Zylinders:
    Der Radius muss beide Male derselbe sein, der Winkel wäre es nicht.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    def radius_of(sections: int) -> float:
        body = trimesh.creation.cylinder(radius=5.0, height=20.0, sections=sections)
        analysis = maps.curvature_map(MeshData.of(body))
        known = [value for value in analysis.values if value == value]
        return sum(known) / len(known)

    coarse, fine = radius_of(32), radius_of(128)

    assert coarse == pytest.approx(5.0, rel=0.02), coarse
    assert fine == pytest.approx(5.0, rel=0.02), fine
    assert coarse == pytest.approx(fine, rel=0.02), "the mesh must not change the answer"


def test_the_curvature_map_finds_a_fillet_beside_its_cylinder() -> None:
    """Der Fall, für den die Karte gebaut wurde (§18.4, §41).

    Eine Säule Ø 12 auf einer Platte, der Fuß mit R 3 verrundet. Beide Flächen
    hängen **tangential** aneinander — die Merkmalserkennung liest sie deshalb
    als einen Fleck und findet dort weder Zylinder noch Torus. Die Karte trennt
    sie, weil sie nicht nach Knicken fragt, sondern nach Radien.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    plate = trimesh.creation.box(extents=(60.0, 60.0, 6.0))
    plate.apply_translation((0.0, 0.0, -3.0))
    post = trimesh.creation.cylinder(radius=6.0, height=30.0, sections=96)
    post.apply_translation((0.0, 0.0, 15.0))
    outer = trimesh.creation.cylinder(radius=9.0, height=3.0, sections=96)
    outer.apply_translation((0.0, 0.0, 1.5))
    inner = trimesh.creation.cylinder(radius=6.0, height=6.0, sections=96)
    inner.apply_translation((0.0, 0.0, 1.5))
    ring = trimesh.boolean.difference([outer, inner])
    torus = trimesh.creation.torus(
        major_radius=9.0, minor_radius=3.0, major_sections=96, minor_sections=48
    )
    torus.apply_translation((0.0, 0.0, 3.0))
    fillet = trimesh.boolean.difference([ring, torus])

    analysis = maps.curvature_map(MeshData.of(trimesh.boolean.union([plate, post, fillet])))
    found = {round(value, 1) for value in analysis.values if value == value}

    assert 3.0 in found, f"the fillet radius is 3 mm: {sorted(found)[:6]}"
    assert 6.0 in found, f"the post radius is 6 mm: {sorted(found)[:6]}"


# --- Features und Passungen -----------------------------------------------------


def test_every_feature_gets_its_own_level() -> None:
    """§18.4: "verstehen, was die KI sieht" — one colour per feature."""
    entry = object_with(plate())
    analysis = maps.build("features", entry)

    assert analysis.categories[0].startswith("ohne")
    assert "hole_1" in analysis.categories
    hole = entry.features["hole_1"]
    level = analysis.categories.index("hole_1")
    assert all(analysis.values[index] == float(level) for index in hole.face_indices)


def test_the_fit_map_marks_the_violated_pair(profile: Profile) -> None:
    """Die Passungskarte hebt genau das Paar hervor, dessen Passung verletzt ist, und lässt das
    gültige Paar in Ruhe.
    """
    entry = object_with(plate())
    scene = Scene(objects={"obj_1": entry}, profile=profile)
    scene.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="clearance",
        )
    )
    scene.report = Report(
        (
            Finding(
                code="fit.violated",
                severity="warning",
                message="zu eng",
                object_id="obj_1",
                feature_ids=("hole_1",),
            ),
        )
    )
    analysis = maps.build("fits", entry, scene=scene)

    assert analysis.highlighted, "the violated fit is the thing to look at"
    assert all(
        analysis.categories[int(analysis.values[index])] == "Passung verletzt"
        for index in analysis.highlighted
    )
    assert maps.fits_of(scene, "obj_1")


@pytest.mark.parametrize(
    ("code", "severity", "caption"),
    [
        ("fit.geometry_clear", "info", "Teil einer Passung"),
        ("fit.pose_unknown", "warning", "Passung prüfen"),
        ("fit.geometry_failed", "warning", "Passung prüfen"),
        ("fit.geometry_approximate", "warning", "Passung prüfen"),
        ("fit.press_unverified", "warning", "Passung prüfen"),
        ("fit.mesh_uncertain", "warning", "Passung prüfen"),
        ("fit.collision", "warning", "Passung verletzt"),
        ("fit.violated", "warning", "Passung verletzt"),
        ("fit.pitch_mismatch", "warning", "Passung verletzt"),
    ],
)
def test_fit_map_distinguishes_proof_and_uncertainty_for_both_partners(
    profile: Profile, code: str, severity: str, caption: str
) -> None:
    """Die Karte übernimmt den Bericht, einschließlich des nicht fokussierten Gegenstücks."""
    mesh = cube()
    feature = Feature("bore", "hole", "detected", {"diameter": 8.0}, face_indices=(0, 1))
    objects = {
        name: SceneObject(name, name, mesh=mesh, features={"bore": feature})
        for name in ("socket", "pin", "unrelated")
    }
    scene = Scene(
        objects=objects,
        profile=profile,
        fits=[Fit("connection", FeatureRef("socket", "bore"), FeatureRef("pin", "bore"))],
        report=Report(
            (
                Finding(
                    code=code,
                    severity=severity,  # type: ignore[arg-type]
                    message="Aus dem aktuellen Prüfbericht",
                    object_id="socket",
                    feature_ids=("bore",),
                    values={"fit": "connection"},
                ),
            )
        ),
    )
    for name in ("socket", "pin"):
        result = maps.build("fits", objects[name], scene=scene)
        assert result.categories[int(result.values[0])] == caption
        assert result.categories[int(result.values[1])] == caption
        assert bool(result.highlighted) is (severity != "info")
        assert set(result.values[2:]) == {0.0}
    assert set(maps.build("fits", objects["unrelated"], scene=scene).values) == {0.0}


def test_without_fits_the_map_stays_empty(profile: Profile) -> None:
    """Ohne Passungen gibt es nichts zu markieren."""
    entry = object_with(plate())
    scene = Scene(objects={"obj_1": entry}, profile=profile)

    assert set(maps.build("fits", entry, scene=scene).values) == {0.0}


# --- support --------------------------------------------------------------------


def test_the_support_map_comes_from_the_layer_analysis(profile: Profile) -> None:
    """§18.4: das Urteil gehört dem Schneider, keiner Faustregel über
    Normalenvektoren.
    """
    analysis = maps.build("support", object_with(_table()), profile=profile)

    assert analysis.highlighted, "the overhanging arm rests on nothing"
    assert max(analysis.values) == pytest.approx(20.0, abs=0.5), "that is how tall it grows"
    assert analysis.source == "internal"
    assert analysis.note is not None, "an estimate has to say that it is one (§22.5)"


def _table() -> MeshData:
    """Eine Säule auf der Platte mit einem Arm darauf, der über nichts
    hinausreicht.
    """
    post = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    post.apply_translation([0.0, 0.0, 10.0])
    arm = trimesh.creation.box(extents=(40.0, 10.0, 4.0))
    arm.apply_translation([0.0, 0.0, 22.0])
    return MeshData.of(trimesh.boolean.union([post, arm]))


def test_a_body_on_the_plate_needs_nothing(profile: Profile) -> None:
    """Ein Körper, der flach auf der Platte steht, braucht keine Stütze — die Stützkarte hebt
    nichts hervor.
    """
    analysis = maps.build("support", object_with(plate()), profile=profile)

    assert analysis.highlighted == ()


# --- Abbrechen ------------------------------------------------------------------


def test_a_map_stops_when_nobody_waits_for_it_any_more(profile: Profile) -> None:
    """§18.4 verspricht abbrechbare Karten, und keine war es.

    Wer die zweite Karte wählte, wartete erst die erste ab — bei 51 000
    Dreiecken 3,4 Sekunden, in denen das Fenster „wird berechnet …" für die
    falsche meldete. Gefragt wird am Eingang und in der teuersten Schleife.
    """
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        maps.build("support", object_with(_table()), profile=profile, cancelled=signal)


def test_the_expensive_loop_asks_too(profile: Profile) -> None:
    """Am Eingang zu fragen genügt nicht.

    Die Sekunden liegen in der Schleife über die Dreiecke, nicht davor — ein
    Abbruch, der nur beim Start greift, kommt genau dann nie an, wenn er
    gebraucht wird.
    """
    from app.core.errors import OperationCancelled

    class _AfterTheFirstLook:
        """Sagt beim zweiten Fragen ab — und das zweite Mal ist die Schleife."""

        def __init__(self) -> None:
            self.asked = 0

        @property
        def is_cancelled(self) -> bool:
            return self.asked > 1

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked > 1:
                raise OperationCancelled

    token = _AfterTheFirstLook()
    with pytest.raises(OperationCancelled):
        maps.build("support", object_with(_table()), profile=profile, cancelled=token)

    assert token.asked > 1, "die Schleife hat gefragt, nicht nur der Eingang"


@pytest.mark.parametrize("kind", ["wall", "curvature", "defects"])
def test_every_expensive_map_stops_when_the_next_one_is_chosen(
    kind: maps.MapKind, profile: Profile
) -> None:
    """Auch Wandstärke und Krümmung hören auf, wenn jemand die nächste Karte wählt.

    ``build`` reichte den Abbruch nur an Stütz-, Formabweichungs- und
    Netzfehlerkarte weiter. Die Wandstärke — die teuerste nach der Stützkarte,
    1,7 s an 885 570 Dreiecken — und die Krümmung liefen bis zum Ende durch,
    während das Fenster schon auf die nächste Karte wartete (§18.4, die Zusage
    am ``_MapWorker``).
    """
    from app.core.errors import OperationCancelled

    class _AfterTheFirstLook:
        """Sagt beim zweiten Fragen ab — das erste ist der Eingang von ``build``.

        **Jedes Fragen zählt, auch das Lesen von** ``is_cancelled``. Beide Wege
        gehören zum ``CancelToken``; die Durchdringungssuche der Netzfehlerkarte
        (``geom.intersections``) liest seit dem 23.09.2026 die Eigenschaft statt
        die Methode zu rufen. Zählte nur die Methode, hielt die Karte an einem
        echten Abbruch an und diese Attrappe sagte trotzdem nie ab.
        """

        def __init__(self) -> None:
            self.asked = 0

        @property
        def is_cancelled(self) -> bool:
            self.asked += 1
            return self.asked > 1

        def raise_if_cancelled(self) -> None:
            if self.is_cancelled:
                raise OperationCancelled

    token = _AfterTheFirstLook()
    with pytest.raises(OperationCancelled):
        maps.build(kind, object_with(_table()), profile=profile, cancelled=token)
    assert token.asked > 1


def test_a_map_runs_through_while_nobody_cancels(profile: Profile) -> None:
    """Der Schalter ist da und wird nicht gezogen — dann ändert er nichts."""
    from app.core.scene.cancel import CancelSignal

    analysis = maps.build(
        "support", object_with(_table()), profile=profile, cancelled=CancelSignal()
    )

    assert analysis.highlighted


# --- Der Weg von der Warnung zur Stelle -----------------------------------------


def test_a_finding_picks_its_map() -> None:
    """Jeder Befundcode führt zu der Karte, die seine Stelle zeigt — und ein Befund ohne Ort zu
    keiner.
    """
    assert maps.map_for(Finding(code="fit.violated", severity="warning", message="x")) == "fits"
    assert maps.map_for(Finding(code="perceive.orphaned", severity="info", message="x")) is None, (
        "ein verlorenes Merkmal hat im aktuellen Körper keine Fläche mehr, "
        "die eine Karte zeigen kann"
    )
    assert maps.map_for(Finding(code="perceive.mended", severity="info", message="x")) is None, (
        "eine geschlossene Fehlstelle ist ebenfalls keine Fläche des aktuellen Körpers mehr"
    )
    assert (
        maps.map_for(Finding(code="perceive.generated_lost", severity="warning", message="x"))
        is None
    ), "auch ein verlorenes erzeugtes Merkmal hat im aktuellen Körper keine Fläche mehr"
    assert (
        maps.map_for(Finding(code="perceive.referenced_lost", severity="warning", message="x"))
        is None
    ), "und ein verlorenes erkanntes, auf das eine Passung zeigte, ebenso wenig (RM-189)"
    assert maps.map_for(Finding(code="repair.still_open", severity="warning", message="x")) == (
        "defects"
    )
    assert maps.map_for(Finding(code="orient.heuristic", severity="info", message="x")) == (
        "overhang"
    )
    assert maps.map_for(Finding(code="etwas.anderes", severity="info", message="x")) is None


def test_the_camera_target_is_the_centre_of_what_is_marked(profile: Profile) -> None:
    """Der Kamerapunkt eines Befunds ist die Mitte der markierten Dreiecke, nicht die des Körpers;
    ohne Markierung gibt es keinen.
    """
    entry = object_with(plate())
    analysis = maps.build("wall", entry, profile=profile)
    assert maps.focus_point(entry, analysis) is None, "nothing marked, nowhere to fly"

    hole = entry.features["hole_1"]
    marked = maps.AnalysisMap(
        kind="wall",
        title="x",
        values=analysis.values,
        unit="mm",
        low=0.0,
        high=1.0,
        highlighted=hole.face_indices,
    )
    point = maps.focus_point(entry, marked)
    assert point is not None
    assert point[0] == pytest.approx(hole.params["centre"][0], abs=0.5)


def test_a_finding_without_a_place_falls_back_to_its_features() -> None:
    """Nennt ein Befund keine Dreiecke, zeigt die Kamera auf seine Merkmale."""
    entry = object_with(plate())
    finding = Finding(code="fit.violated", severity="warning", message="x", feature_ids=("hole_2",))

    point = maps.location_of(entry, finding)
    assert point is not None
    assert point[0] == pytest.approx(entry.features["hole_2"].params["centre"][0], abs=0.5)


def test_a_finding_that_points_nowhere_stays_that_way() -> None:
    """Ein Befund ohne Dreiecke und ohne Merkmale hat keinen Ort, und die Karte erfindet keinen."""
    entry = object_with(cube())
    assert maps.location_of(entry, Finding(code="x", severity="info", message="y")) is None


# --- limits ---------------------------------------------------------------------


def test_a_huge_body_is_refused_rather_than_ground_through(profile: Profile) -> None:
    """§31: eine Karte, die Minuten braucht, ist schlechter als eine, die Nein
    sagt.
    """
    dense = MeshData.of(trimesh.creation.icosphere(subdivisions=3))
    entry = SceneObject(id="obj_1", name="x", mesh=dense, features={})
    limit = maps.MAP_LIMIT_TRIANGLES
    try:
        maps.MAP_LIMIT_TRIANGLES = 10
        with pytest.raises(maps.MapTooLarge):
            maps.build("wall", entry, profile=profile)
    finally:
        maps.MAP_LIMIT_TRIANGLES = limit


def test_features_without_faces_do_not_fall_over() -> None:
    """Merkmale ohne Flächenindizes lassen die Ortsbestimmung nicht abstürzen."""
    entry = SceneObject(
        id="obj_1",
        name="x",
        mesh=cube(),
        features={"loop": Feature(id="loop", kind="edge_loop", provenance="detected", params={})},
    )
    analysis = maps.build("features", entry)

    assert set(analysis.values) == {0.0}


def test_a_sphere_takes_its_radius_from_the_recognition() -> None:
    """Auf einer Kugel liegt jede Nachbarschaft schräg — die Schätzung bricht weg.

    **Gemeldet von 3d-druck-64 am 23.08.2026, gemessen an ``sphere_socket.stl``:**
    Die Erkennung liest 7,969 mm, die Karte 7,211 — 9,5 % daneben, und zwar bei
    jeder Netzfeinheit gleich.

    Vier andere Merkmalsarten desselben Korpus lagen unter einem halben
    Prozent. Der Grund ist keine Diskretisierung, sondern die Vernetzung:
    Zylinder, Verrundung und Torus haben eine ausgezeichnete
    Hauptkrümmungsrichtung, und ihre Vernetzung folgt ihr — es gibt
    Nachbarschaften, die quer liegen und exakt ``r`` liefern. Eine Kugel hat
    keine solche Richtung, und ``_face_radii`` nimmt unter den Nachbarn das
    **Minimum**, greift also die schrägste.

    Deshalb konvergiert es auch nicht: An einer Icosphere bleibt der Fehler von
    Subdivision 2 bis 4 bei -12,8 %, an einer UV-Kugel schrumpft er dagegen von
    -1,1 auf -0,1 %. Eine Icosphere ist selbstähnlich verzerrt.
    """
    body = normalise(read_mesh((MESHES / "sphere_socket.stl").read_bytes(), ".stl"), "mm").mesh
    features = detect(body)
    sphere = next((f for f in features.values() if f.kind == "sphere"), None)
    assert sphere is not None, "ohne erkannte Kugel prüft der Test nichts"

    wanted = float(sphere.params["diameter"]) * 0.5
    faces = [int(index) for index in (sphere.face_indices or ())]
    assert faces, "die Kugel trägt keine Dreiecke — dann sagt der Test nichts"

    guessed = maps.curvature_map(body).values
    measured = maps.curvature_map(body, features).values

    rough = sorted(guessed[index] for index in faces)[len(faces) // 2]
    exact = sorted(measured[index] for index in faces)[len(faces) // 2]

    assert rough < wanted * 0.95, (
        f"die Schätzung trifft die Kugel plötzlich ({rough:.3f} gegen {wanted:.3f}) — "
        "dann misst dieser Test den Fehler nicht mehr, den er festhalten soll"
    )
    assert exact == pytest.approx(wanted, rel=1e-6), (
        f"die Karte nimmt das gemessene Maß nicht: {exact:.3f} statt {wanted:.3f}"
    )


def test_the_curvature_map_says_where_its_numbers_come_from() -> None:
    """Zwei Herkünfte in einer Karte werden ausgewiesen (§22.5).

    Ein Wert aus der Erkennung und einer aus der Schätzung stehen nebeneinander
    in derselben Karte, und der Kunde sieht ihnen nichts an. Gesagt wird es
    deshalb **in Worten** — nicht über einen Farbton, den niemand ohne Legende
    deutet (Regel 18).
    """
    body = normalise(read_mesh((MESHES / "sphere_socket.stl").read_bytes(), ".stl"), "mm").mesh

    plain = str(maps.curvature_map(body).note or "")
    mixed = str(maps.curvature_map(body, detect(body)).note or "")

    assert "Schätzung" not in plain, "ohne Merkmale gibt es nichts zu unterscheiden"
    assert "gemessenes Maß" in mixed and "Schätzung" in mixed, (
        f"die Karte weist ihre zwei Herkünfte nicht aus: {mixed!r}"
    )
    assert "{" not in mixed, "ein Platzhalter aus dem Kern erschiene mit geschweiften Klammern"


def test_every_radius_entry_finds_its_parameter() -> None:
    """Jeder Eintrag der Tabelle muss an einem echten Merkmal etwas finden.

    **Gefunden von 3d-druck-64 am 23.08.2026 beim Nachmessen, nicht von einem
    Test:** ``_FEATURE_RADIUS`` führte den Torus als ``("minor_radius", 1.0)``.
    Den Schlüssel gibt es nicht — das Merkmal trägt ``tube_diameter``. Der
    Eintrag lief ins ``continue`` und tat nichts.

    **Warum es keinem auffiel, ist der eigentliche Punkt.** Die Schätzung trifft
    einen Torus ohnehin auf 0,4 %, weil er eine ausgezeichnete
    Hauptkrümmungsrichtung hat und seine Vernetzung ihr folgt. Ein Eintrag, der
    nichts bewirkt, sieht dort aus wie einer, der wirkt: Alle Tests blieben
    grün, die gemessene Tabelle stimmte für die drei Arten, die gemessen worden
    waren, und die vierte war stumm.

    Geprüft wird deshalb nicht das Ergebnis, sondern die **Verbindung** — trägt
    das Merkmal den Parameter, den die Tabelle sucht. Das fängt auch eine
    Umbenennung in der Erkennung und den nächsten Eintrag, den jemand hinzufügt.
    """
    seen: dict[str, set[str]] = {}
    for path in sorted(MESHES.glob("*.stl")):
        try:
            body = normalise(read_mesh(path.read_bytes(), ".stl"), "mm").mesh
        except Exception:  # ein unlesbarer Korpuskörper ist hier kein Befund
            continue
        for feature in detect(body).values():
            seen.setdefault(feature.kind, set()).update(feature.params)

    checked = 0
    for kind, (name, factor) in maps._FEATURE_RADIUS.items():
        if kind not in seen:
            continue
        checked += 1
        assert name in seen[kind], (
            f"_FEATURE_RADIUS sucht bei {kind!r} den Parameter {name!r}, das Merkmal "
            f"führt aber {sorted(seen[kind])} — der Eintrag bewirkt nichts"
        )
        assert factor > 0.0, f"{kind}: ein Faktor von {factor} ergäbe keinen Radius"

    assert checked >= 4, (
        f"nur {checked} Einträge am Korpus geprüft — ohne die Merkmale prüft dieser "
        "Test seine eigene leere Menge"
    )


def test_an_analysis_map_works_on_an_exact_body(profile: Profile) -> None:
    """Roberts Absturzbericht vom 27.08.2026: „analysis maps need the trimesh
    backed mesh", als InternalError mit Fehlerbericht-Knopf.

    Ein STEP-Import ist ein **exakter** Körper (§30), und die Analysekarten
    rechnen auf Dreiecken. ``_mesh_of`` lehnte deshalb alles ab, was kein
    ``MeshData`` ist — mit einem ``TypeError`` und dem Kommentar „heute nur ein
    Kern" daneben. Der Satz war richtig, als er geschrieben wurde; seit dem
    zweiten Kern ist er still falsch, und der Kunde bekam für eine gewöhnliche
    Handlung einen Programmfehler.

    Der Weg von B-Rep zu Mesh steht jederzeit offen (``as_mesh_data`` über
    ``to_mesh``) — die Karte rechnet also auf der Tessellation, wie jede
    Mesh-Operation an einem exakten Körper.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from app.core.brep.kernel import Solid

    shape = BRepPrimAPI_MakeBox(20.0, 20.0, 5.0).Shape()
    exact = SceneObject(id="obj_1", name="shim", mesh=Solid(shape))

    for kind in ("curvature", "overhang", "wall"):
        card = maps.build(kind, exact, profile=profile)
        assert card.values is not None, f"die Karte {kind!r} rechnet auch am exakten Körper"


def test_the_support_map_is_not_refused_by_a_triangle_guess(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Kosten der Stützkarte lassen sich nicht an Dreiecken vorhersagen.

    **Gemessen am 04.09.2026 über fünf Kundendateien.** Sechs der sieben
    Karten bleiben selbst bei 885 570 Dreiecken unter 2,1 Sekunden, das Budget
    erlaubt drei (§31). Die Stützkarte reißt es als einzige — und sie hängt
    nicht an der Dreieckszahl: 8,33 s am Besenhalter mit 59 740 Dreiecken
    gegen 1,84 s am Segel mit 277 460, beim **kleineren** Modell also
    viermal so teuer. Sie rechnet eine Schichtanalyse; ihre Kosten stehen an
    Bauhöhe und Konturkomplexität.

    Eine gemeinsame Zahl für sieben Rechnungen ist damit entweder für sechs zu
    streng oder für eine zu großzügig. Hier stand sie zu streng: Zehn von
    neunzehn heruntergeladenen Kundendateien bekamen „zu groß" für Rechnungen,
    die in zwei Sekunden fertig gewesen wären.
    """
    dense = MeshData.of(trimesh.creation.icosphere(subdivisions=3))
    entry = SceneObject(id="obj_1", name="x", mesh=dense, features={})

    called: list[object] = []
    monkeypatch.setattr(
        maps,
        "support_map",
        lambda _mesh, _height, cancelled, overhang_angle, pitch: (
            called.append(cancelled)
            or maps.AnalysisMap(kind="support", title="x", values=(), unit="mm", low=0.0, high=0.0)
        ),
    )
    monkeypatch.setattr(maps, "MAP_LIMIT_TRIANGLES", 10)

    maps.build("support", entry, profile=profile)

    assert called, "support begins and judges its actual work instead of triangle count"


def test_the_support_budget_uses_an_injected_monotonic_clock() -> None:
    """Das Zeitbudget ist reproduzierbar geprüft, ohne Schlaf oder Last."""
    times = iter((100.0, 102.9, 103.0))
    deadline = maps._MapDeadline(None, 3.0, clock=lambda: next(times))

    deadline.raise_if_cancelled()
    with pytest.raises(maps.MapBudgetExceeded) as exceeded:
        deadline.raise_if_cancelled()

    assert exceeded.value.seconds == 3.0
    assert {suggestion.id for suggestion in exceeded.value.suggestions} >= {
        "decimate_mesh",
        "cancel",
    }


@pytest.mark.parametrize("phase", ["sections", "direct_sections", "raster"])
def test_support_budget_interrupts_inside_the_solid_field(
    phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach Ablauf im Schnitt oder ersten Rasterquerschnitt läuft kein Restfeld weiter."""
    from app.core.slice import analysis
    from app.core.types import SliceResult

    now = [0.0]
    deadline = maps._MapDeadline(None, 3.0, clock=lambda: now[0])
    monkeypatch.setattr(
        maps,
        "slice_body",
        lambda *_args, **_kwargs: SliceResult(
            layers=(), support_volume=0.0, first_layer_area=0.0, source="internal"
        ),
    )
    original_segments = analysis._plane_segments
    original_shape = analysis._shape_from_rings
    if phase == "sections":
        monkeypatch.setattr(analysis, "_solid_sections", lambda *_args, **_kwargs: None)
    original_contains = maps.shapely.contains_xy
    rastered = 0

    def expire_in_segments(*args, **kwargs):
        if phase == "sections":
            now[0] = 4.25
        return original_segments(*args, **kwargs)

    def expire_in_direct_section(*args, **kwargs):
        if phase == "direct_sections":
            now[0] = 4.25
        return original_shape(*args, **kwargs)

    def expire_in_raster(*args, **kwargs):
        nonlocal rastered
        answer = original_contains(*args, **kwargs)
        rastered += 1
        if phase == "raster":
            now[0] = 4.25
        return answer

    monkeypatch.setattr(analysis, "_plane_segments", expire_in_segments)
    monkeypatch.setattr(analysis, "_shape_from_rings", expire_in_direct_section)
    monkeypatch.setattr(maps.shapely, "contains_xy", expire_in_raster)
    with pytest.raises(maps.MapBudgetExceeded):
        maps.support_map(cube(), cancelled=deadline)

    assert rastered == (1 if phase == "raster" else 0), (
        f"{rastered} raster sections after the budget expired in {phase}"
    )


def test_support_checks_the_budget_after_an_atomic_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch ohne Überhangregion darf ein überzogener Teilpfad nicht Erfolg melden."""
    from app.core.types import SliceResult

    now = [0.0]
    deadline = maps._MapDeadline(None, 3.0, clock=lambda: now[0])
    monkeypatch.setattr(
        maps,
        "slice_body",
        lambda *_args, **_kwargs: SliceResult(
            layers=(), support_volume=0.0, first_layer_area=0.0, source="internal"
        ),
    )

    def slow_field(_mesh: MeshData, pitch=None, *, cancelled=None) -> object:
        now[0] = 4.25
        return object()

    monkeypatch.setattr(maps, "solid_field", slow_field)

    with pytest.raises(maps.MapBudgetExceeded) as exceeded:
        maps.support_map(cube(), cancelled=deadline)

    assert exceeded.value.seconds == pytest.approx(4.25), (
        "the message names the real wait including the indivisible stage"
    )


def test_the_support_map_marks_the_same_triangles_as_a_triangle_by_triangle_search(
    profile: Profile,
) -> None:
    """Der Umbau der teuersten Schleife darf keine andere Karte ergeben.

    **Was er ersetzt:** Vorher fragte die Karte je Dreieck einzeln — welche
    Schicht gehört dazu (lineare Suche über alle), und liegt der Punkt in einer
    ihrer Konturen (ein ``Point``-Objekt und ein ``intersects`` je Kontur).
    Gemessen am Spiderman mit 885 570 Dreiecken (04.09.2026): 85,3 s in
    ``_inside``, 38,5 s in ``_region_at``, darin 216 Millionen Aufrufe von
    ``abs``.

    Jetzt läuft es schichtweise: ``searchsorted`` findet die Gruppe, und
    ``shapely.intersects_xy`` prüft alle Punkte einer Schicht auf einmal. Die
    ganze Karte fiel damit von 45,44 s auf 7,07 s.

    **Geprüft wird nicht die Zeit, sondern die Gleichheit** — gegen eine
    wörtliche Nachbildung der alten Schleife. Eine schnellere Karte, die andere
    Dreiecke markiert, ist keine Optimierung.
    """
    from shapely.geometry import Point

    from app.core.slice.analysis import slice_body

    # **Der Prüfkörper muss die Auswahlregel treffen, nicht nur Überhänge
    # haben.** Ein Pilz hat welche, aber seine Überhangschichten zeigen alle
    # dieselbe Kontur — dort ist es gleich, welche von zwei benachbarten man
    # nimmt, und die Mutation „nächstgelegene statt unterste" blieb grün.
    # ``generated_figure`` hat 21 Überhangschichten, davon 14 näher als eine
    # Schichthöhe am Nachbarn; dort entscheidet die Regel.
    mesh = normalise(
        read_mesh(
            (Path(__file__).parent / "data" / "meshes" / "generated_figure.stl").read_bytes(),
            ".stl",
        ),
        "mm",
    ).mesh

    result = slice_body(mesh, profile.printer.layer_height, detail="support")
    regions = maps._overhang_regions(result)
    assert regions, "der Prüfkörper hat keine Überhänge — dann prüft der Test nichts"

    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    zu_fuss: list[int] = []
    for index, centre in enumerate(centres):
        region = next(
            (
                shapes
                for height, shapes in regions
                if abs(height - float(centre[2])) <= profile.printer.layer_height
            ),
            None,
        )
        if region is None:
            continue
        punkt = Point(float(centre[0]), float(centre[1]))
        if any(shape.intersects(punkt) for shape in region):
            zu_fuss.append(index)

    schichtweise = maps._marked_by_layer(regions, centres, profile.printer.layer_height, None)

    assert zu_fuss, "keine markierten Dreiecke — der Prüfkörper trägt den Fall nicht"
    assert set(zu_fuss) == set(schichtweise.tolist()), (
        f"schichtweise markiert {len(schichtweise)} Dreiecke, Dreieck für Dreieck {len(zu_fuss)}"
    )


def test_the_defect_map_shows_where_outsides_face_each_other() -> None:
    """„An 3 Kanten zeigen die Außenseiten gegeneinander" führt zu Stellen im Bild.

    Der Befund trug *Stellen zeigen*, und die Karte kannte diese Kanten nicht
    (Durchsicht 24.09.2026). Ein Würfel mit einem umgedrehten Dreieck: das
    Dreieck und seine drei Nachbarn tragen die vierte Stufe.
    """
    body = trimesh.creation.box()
    faces = np.asarray(body.faces).copy()
    faces[0] = faces[0][::-1]
    turned = MeshData.of(trimesh.Trimesh(vertices=body.vertices, faces=faces, process=False))

    analysis = maps.defect_map(turned)

    marked = {index for index, value in enumerate(analysis.values) if value == 4.0}
    assert 0 in marked and len(marked) == 4
    assert str(analysis.categories[4]) == "Außenseiten gegeneinander"
