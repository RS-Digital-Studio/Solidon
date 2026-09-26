"""The difference view (Bauplan §18.7)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.difference import compare, compare_scenes
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.types import Profile, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


def cube(size: float = 20.0) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(size, size, size)))


def plate() -> MeshData:
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_body_that_grew_shows_the_added_volume() -> None:
    difference = compare(cube(20.0), cube(24.0))

    assert difference.added_volume == pytest.approx(24.0**3 - 20.0**3, rel=0.02)
    assert difference.removed_volume < 1.0
    assert difference.changed


def test_a_body_that_shrank_shows_the_removed_volume() -> None:
    difference = compare(cube(24.0), cube(20.0))

    assert difference.removed_volume == pytest.approx(24.0**3 - 20.0**3, rel=0.02)
    assert difference.added_volume < 1.0


def test_a_local_change_is_compared_inside_its_box_with_the_same_answer(monkeypatch) -> None:
    """Der Vergleich beschneidet beide Körper auf die Änderungsbox — und die
    Volumina sind dieselben wie am ganzen Körper.

    An 204 000 Dreiecken kostete der Vergleich zweier Bohrdurchmesser 0,64 s,
    zwei Boolesche Differenzen über die ganze Platte für 1 148 Dreiecke
    Unterschied; beschnitten sind es 0,25 s (22.09.2026). Ob wirklich
    beschnitten wurde, sagt die Zahl der Booleschen Aufrufe: vier statt zwei.
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.geom.prepare import drill
    from app.core.knowledge.profiles import make_profile

    load_operations()
    difference_module = import_module("app.core.geom.difference")
    profile = make_profile("centauri-carbon-2", "petg")
    # Zweimal unterteilt, damit die Bohrung nur ihre Umgebung neu vernetzt:
    # An der groben Platte reichen die Fächer um das Loch bis zum Rand, jedes
    # Deckdreieck gilt als geändert, und die Box ist die ganze Platte.
    raw = plate().raw
    for _step in range(2):
        vertices, faces = trimesh.remesh.subdivide(raw.vertices, raw.faces)
        raw = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body = MeshData.of(raw)
    top = float(body.bounds.maximum[2])
    before = drill(body, position=(0.0, 0.0, top), axis="z", diameter=4.0, profile=profile).mesh
    after = drill(body, position=(0.0, 0.0, top), axis="z", diameter=5.0, profile=profile).mesh

    calls: list[str] = []
    original = difference_module.boolean

    def counted(kind, bodies, **kwargs):
        calls.append(kind)
        return original(kind, bodies, **kwargs)

    monkeypatch.setattr(difference_module, "boolean", counted)
    clipped = compare(before, after, profile=profile)
    assert calls.count("intersection") == 2, "beide Körper werden auf die Änderungsbox beschnitten"

    monkeypatch.setattr(difference_module, "_changed_region", lambda *_args: None)
    whole = compare(before, after, profile=profile)

    assert clipped.removed_volume == pytest.approx(whole.removed_volume, rel=1e-6)
    assert clipped.added_volume == pytest.approx(whole.added_volume, rel=1e-6)
    assert clipped.removed_volume > 1.0, "eine Bohrung von 4 auf 5 mm nimmt Material"
    assert clipped.changed


def test_a_change_over_half_the_body_is_compared_whole(monkeypatch) -> None:
    """Wächst der Körper überall, spart die Box nichts — dann bleibt es beim ganzen."""
    from importlib import import_module

    difference_module = import_module("app.core.geom.difference")
    calls: list[str] = []
    original = difference_module.boolean

    def counted(kind, bodies, **kwargs):
        calls.append(kind)
        return original(kind, bodies, **kwargs)

    monkeypatch.setattr(difference_module, "boolean", counted)
    difference = compare(cube(20.0), cube(24.0))

    assert "intersection" not in calls
    assert difference.added_volume == pytest.approx(24.0**3 - 20.0**3, rel=0.02)


def test_the_changed_region_of_identical_bodies_is_none() -> None:
    from importlib import import_module

    difference_module = import_module("app.core.geom.difference")
    body = plate()
    assert difference_module._changed_region(body, body) is None
    moved = apply(body, translation((0.0, 0.0, 30.0)))
    low, high = difference_module._changed_region(body, moved)
    assert np.all(low <= body.bounds.minimum) and np.all(high >= moved.bounds.maximum)


def test_a_body_that_did_not_change_is_not_a_failed_computation() -> None:
    """Ein Vergleich, der nichts findet, hat nichts zu melden.

    Aus dem Protokoll des ersten Kunden mit 0.1.3: zwölfmal
    ``difference could not be computed: Es bleibt kein Körper übrig`` und ein
    Befund im Prüfbericht daneben — für zwei Zustände, zwischen denen sich
    schlicht nichts geändert hatte. Die Rechnung war nie gescheitert; sie war
    leer, und leer ist hier die richtige Antwort.

    Ohne ``allow_empty`` in :func:`_cut` wirft die Boolesche Kette an dieser
    Stelle, und der Vergleich meldet einen Fehlschlag, den es nicht gab.
    """
    difference = compare(cube(20.0), cube(20.0))

    assert not difference.changed
    assert difference.added_volume < 1.0
    assert difference.removed_volume < 1.0
    assert not difference.findings, [str(entry.message) for entry in difference.findings]


def test_a_body_that_moved_shows_both_sides() -> None:
    """Bewegen ist hier Entfernen und dort Hinzufügen — und die Ansicht sagt
    das.
    """
    moved = apply(cube(20.0), translation((10.0, 0.0, 0.0)))
    difference = compare(cube(20.0), moved)

    assert difference.added_volume > 0.0
    assert difference.removed_volume > 0.0


def test_an_unchanged_body_is_not_a_change() -> None:
    difference = compare(cube(20.0), cube(20.0))

    assert not difference.changed


def test_the_solver_stage_is_kept(profile: Profile) -> None:
    """§17.2: welche Stufe die Differenz getragen hat, ist Teil der Antwort."""
    difference = compare(cube(20.0), cube(24.0))

    assert difference.solvers
    assert difference.solvers[0].strategy in ("direct", "welded", "jittered", "voxel")


def test_unchanged_overlapping_letters_do_not_appear_as_removed_material() -> None:
    """Ein Loch ändert sich; sechs unverschnitten aufliegende Marken bleiben gleich."""
    from app.core.geom.boolean import boolean

    meshes = []
    for radius in (2.0, 4.0):
        stock = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 10.0)))
        tool = trimesh.creation.cylinder(radius=radius, height=12.0, sections=96)
        tool.apply_translation((-10.0, 0.0, 0.0))
        drilled = boolean("difference", [stock, MeshData.of(tool)], quality="fine").mesh
        marks = []
        for x in (4.0, 10.0, 16.0):
            for y in (-8.0, 8.0):
                mark = trimesh.creation.annulus(r_min=1.0, r_max=2.0, height=2.0, sections=32)
                # Eine Hälfte liegt im Grundkörper. Nach einer booleschen
                # Operation dürfen reine Rundungsreste keine Schriftflecken erzeugen.
                mark.apply_translation((x, y, 5.0))
                if radius > 3.0:
                    mark.vertices = np.nextafter(mark.vertices, np.inf)
                marks.append(mark)
        meshes.append(MeshData.of(trimesh.util.concatenate([drilled.raw, *marks])))
    result = compare(*meshes)
    assert not result.findings
    assert result.added_volume < result.noise_volume
    expected = 0.5 * 96 * np.sin(2.0 * np.pi / 96) * (4.0**2 - 2.0**2) * 10.0
    assert result.removed_volume == pytest.approx(expected, abs=1e-5)
    assert result.removed is not None
    assert result.removed.bounds.maximum[0] < -5.0


def test_unchanged_overlap_still_masks_material_removed_from_another_shell() -> None:
    """Gemeinsames Material bleibt auch dort erhalten, wo ein anderer Körper schrumpft."""
    first = trimesh.creation.box(extents=(20, 20, 20))
    second = trimesh.creation.box(extents=(10, 20, 20))
    shield = trimesh.creation.box(extents=(4, 20, 20))
    shield.apply_translation((8, 0, 0))
    before = MeshData.of(trimesh.util.concatenate([first, shield]))
    after = MeshData.of(trimesh.util.concatenate([second, shield]))
    result = compare(before, after)
    # Linker Streifen 5 mm, rechter Streifen nur 1 mm; der Schild hält 4 mm.
    assert not result.findings
    assert result.removed_volume == pytest.approx((5 + 1) * 20 * 20)
    assert result.added_volume < result.noise_volume


def test_negative_inner_shell_stays_a_cavity_in_the_comparison() -> None:
    """Eine negative Innenschale wird nie als positive Komponente vereinigt."""
    inside = trimesh.creation.box(extents=(10, 10, 10))
    inside.invert()
    hollow = MeshData.of(trimesh.util.concatenate([cube().raw, inside]))
    result = compare(hollow, cube())
    assert not result.findings
    assert result.added_volume == pytest.approx(10**3)
    assert result.removed_volume < result.noise_volume


# --- whole scenes -----------------------------------------------------------------


def scene_with(**objects: MeshData) -> Scene:
    return Scene(
        objects={name: SceneObject(id=name, name=name, mesh=mesh) for name, mesh in objects.items()}
    )


def test_a_transaction_is_compared_body_by_body() -> None:
    before = scene_with(obj_1=cube(20.0), obj_2=plate())
    after = scene_with(obj_1=cube(24.0), obj_2=plate())

    difference = compare_scenes(before, after)

    assert set(difference.entries) == {"obj_1"}, "an untouched body is not compared at all"
    assert difference.changed
    assert difference.added_volume > 0.0


def test_new_and_gone_objects_are_named() -> None:
    before = scene_with(obj_1=cube(20.0))
    after = scene_with(obj_1=cube(20.0), obj_2=cube(10.0))

    difference = compare_scenes(before, after)

    assert difference.created == ("obj_2",)
    assert difference.deleted == ()
    assert difference.changed


def test_a_recolouring_is_a_preview_without_volume() -> None:
    """RM-169: *Filament zuweisen* ändert keinen Eckpunkt — ``compare_scenes``
    übersprang den Körper, und im Bild blieb die alte Farbe, bis übernommen
    war. Jetzt trägt der Eintrag den Körper danach; die Ansicht zeichnet ihn
    mit seinen Farben, das Volumen bleibt null."""
    from app.core.types import MaterialSlot

    plain = cube(20.0)
    painted = MeshData.of(plain.raw, slots=(1,) * len(plain.raw.faces))
    before = scene_with(obj_1=plain)
    after = scene_with(obj_1=painted)
    after.objects["obj_1"].material_slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0))
    ]

    difference = compare_scenes(before, after)

    assert set(difference.entries) == {"obj_1"}
    assert not difference.changed, "kein Volumen kommt dazu oder fällt weg"
    assert difference.recoloured
    assert difference.entries["obj_1"].recoloured is after.objects["obj_1"]
    assert difference.entries["obj_1"].retriangulated is None

    # Dieselben Farben sind keine Änderung — sonst zeichnete jede Vorschau
    # jeden Körper noch einmal.
    assert not compare_scenes(after, after).entries


def test_new_triangles_at_the_same_volume_are_a_preview() -> None:
    """RM-169: *Dreiecke angleichen* und *Fläche unterteilen* tauschen jedes
    Dreieck und kein Volumen — die Zahl sagt „nichts", das Netz sagt etwas.
    Der Eintrag trägt den Körper danach, und die Ansicht zeigt seine Kanten."""
    plain = cube(20.0)
    finer = MeshData.of(plain.raw.subdivide())
    assert finer.triangle_count > plain.triangle_count, "die Voraussetzung des Falls"

    difference = compare_scenes(scene_with(obj_1=plain), scene_with(obj_1=finer))

    assert not difference.changed
    assert difference.reshaped
    assert difference.entries["obj_1"].retriangulated is finer
    assert not difference.recoloured


def test_a_widened_bore_takes_material_and_adds_none_even_where_the_cut_cannot(
    profile: Profile,
) -> None:
    """Was eine Bohrung aufweitet, fällt weg — und dazu kommt nichts, auch wenn
    der Schnitt „danach minus davor" am Kern scheitert.

    Die Senkplatte, einmal unterteilt, Bohrung Ø 5,2 auf Ø 6: Der Körper danach
    liegt ganz im Körper davor, und ihre ebenen Flächen decken sich mit
    verschiedenen Dreiecken. Genau dort liefert der Kern für „danach minus
    davor" Splitter: hier zehn Dreiecke mit 3·10⁻¹² mm³, die die Vorschau als
    hinzugekommenes Material zeigte; auf dem Weg der Sitzung Splitter mit
    negativem Volumen, die beide Stufen der Entwurfskette ablehnten — die
    Vorschau hieß unvollständig, an der Senkplatte mit 311 296 Dreiecken bei
    Ø 6 und Ø 6,5 (26.09.2026, RM-212). Die Antwort steht aber fest, sobald
    der andere Schnitt gerechnet hat: |A − B| − |B − A| ist |A| − |B|.

    Erwartet (``data/README.md``): Zylinder Ø 5,2 auf 5,6 mm Tiefe, darüber
    die 90°-Senkung. Aufgeweitet wird der Zylinder zum Ring
    π/4 · (6² − 5,2²) · 5,6 und der Kegel zwischen Ø 5,2 und Ø 6 auf 0,4 mm
    Höhe zum Ring π · (3² · 0,4 − 0,4/3 · (2,6² + 2,6 · 3 + 3²)).
    """
    import math

    from app.core.bootstrap import load_operations
    from app.core.perceive.features import detect
    from tests.helpers import feature_operation

    load_operations()
    # Wie die Sonde: erst unterteilen, dann einlesen, wie ein Kunde die Datei öffnet.
    raw = read_mesh((MESHES / "plate_countersunk.stl").read_bytes(), ".stl").raw
    vertices, faces = trimesh.remesh.subdivide(raw.vertices, raw.faces)
    finer = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
    before = normalise(finer, "mm").mesh
    features = detect(before)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    after = (
        feature_operation(
            "resize_hole",
            before,
            features,
            hole,
            profile,
            diameter=6.0,
            compensate=False,
            quality="draft",
        )
        .outputs[0]
        .mesh
    )

    difference = compare(before, after, profile=profile)

    ring = math.pi / 4.0 * (6.0**2 - 5.2**2) * 5.6
    cone = math.pi * (3.0**2 * 0.4 - 0.4 / 3.0 * (2.6**2 + 2.6 * 3.0 + 3.0**2))
    assert not difference.findings, [finding.code for finding in difference.findings]
    assert difference.removed_volume == pytest.approx(ring + cone, rel=0.02)
    assert difference.removed_volume == pytest.approx(before.volume - after.volume, rel=1e-6)
    assert difference.added_volume == 0.0
    assert difference.added is not None and difference.added.triangle_count == 0


def test_an_incomplete_difference_is_not_a_reshaped_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review 14.09.2026: Scheitert ``_cut`` in beiden Richtungen, sind beide
    Volumina null und ``changed`` ist falsch — der Eintrag behauptete dann
    „neue Dreiecke, gleiches Volumen", wo über das Volumen nichts bekannt ist,
    und ``reshaped`` unterdrückte die Warnung der Operation im Band."""
    from app.core.geom import difference as module

    monkeypatch.setattr(module, "_cut", lambda before, after, quality: None)
    plain = cube(20.0)
    finer = MeshData.of(plain.raw.subdivide())

    difference = compare_scenes(scene_with(obj_1=plain), scene_with(obj_1=finer))

    entry = difference.entries["obj_1"]
    assert "difference.incomplete" in {finding.code for finding in entry.findings}
    assert not difference.changed
    assert entry.retriangulated is None, "unvollständig bleibt unvollständig"
    assert not difference.reshaped


def test_a_scene_that_did_not_change_says_so() -> None:
    before = scene_with(obj_1=plate())
    after = scene_with(obj_1=plate())

    assert not compare_scenes(before, after).changed


def test_a_changed_scene_keeps_the_complete_result_for_the_preview() -> None:
    """Auch die entfernte Bohrungswand muss im dargestellten Körper verschwinden."""
    before = scene_with(obj_1=cube(20.0))
    after = scene_with(obj_1=cube(16.0))
    entry = compare_scenes(before, after).entries["obj_1"]
    assert entry.result is after.objects["obj_1"]


def test_a_failed_volume_comparison_still_keeps_the_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein nicht berechenbarer Vergleich darf den Nachherkörper nicht verstecken."""
    from app.core.geom import difference as module

    monkeypatch.setattr(module, "_cut", lambda before, after, quality: None)
    after = scene_with(obj_1=cube(16.0))
    entry = compare_scenes(scene_with(obj_1=cube(20.0)), after).entries["obj_1"]
    assert entry.result is after.objects["obj_1"]
    assert "difference.incomplete" in {finding.code for finding in entry.findings}


def test_an_exact_body_shows_its_difference_too() -> None:
    """Der Zwilling des Analysekarten-Absturzes (27.08.2026), nur still.

    ``compare_scenes`` übersprang jeden Körper, der kein ``MeshData`` ist —
    ein STEP-Import also, und alles aus dem exakten Kern. Kein Absturz, keine
    Meldung: Die Differenzansicht blieb nach jeder Änderung an einem exakten
    Körper einfach leer, und §18.7 verspricht genau sie. Wer sich fragt, was
    ein Schritt getan hat, bekam bei der einen Körperart eine Antwort und bei
    der anderen nichts, ohne zu erfahren, warum.

    Dieselbe Auflösung wie dort: Der Weg von B-Rep zu Mesh steht jederzeit
    offen (§30), verglichen wird auf der Tessellation.
    """
    from app.core.brep.kernel import Solid, available

    if not available():
        pytest.skip("OpenCASCADE is an optional dependency")

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    def scene_of(mesh: object) -> Scene:
        return Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=mesh)})

    before = scene_of(Solid(BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()))
    after = scene_of(Solid(BRepPrimAPI_MakeBox(30.0, 30.0, 30.0).Shape()))

    result = compare_scenes(before, after)

    assert "obj_1" in result.entries, "auch ein exakter Körper zeigt, was sich geändert hat"
    assert result.entries["obj_1"].added_volume > 0.0


def test_a_body_that_did_not_exist_before_is_shown_as_added() -> None:
    """Ein neu erzeugter Körper ist die Differenz — die ganze.

    **Gemessen an der Live-Vorschau, und dort fällt es beim Kunden auf:** Wer
    eine Skizze extrudiert, einen Quader anlegt oder einen Zylinder erzeugt,
    tippt eine Höhe und sieht nichts. Der Dialog rechnet die Vorschau, die
    Ansicht zeichnet ``entries`` — und ein neuer Körper stand allein in
    ``created``, ohne Geometrie daneben.

    Das trifft **jede erzeugende Operation**, also genau den Anfang von Weg 2:
    neu konstruieren. Robert hat danach gefragt („in die Seitenansicht gehen
    und nach oben ziehen") — was fehlte, war nicht der Griff, sondern das Bild.

    Und die zweite Hälfte ist die Zahl: ``added_volume`` meldete null, während
    achttausend Kubikmillimeter entstanden. Eine Differenz, die ihr eigenes
    Ergebnis nicht mitzählt, ist als Auskunft falsch, nicht nur als Bild leer.
    """
    before = Scene(objects={})
    body = cube(20.0)
    after = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=body)})

    difference = compare_scenes(before, after)

    assert difference.created == ("obj_1",), "die Liste der Neuen bleibt, wie sie war"
    assert "obj_1" in difference.entries, "und er steht jetzt auch als Geometrie da"
    entry = difference.entries["obj_1"]
    assert entry.added is not None, "sein Netz ist das Hinzugekommene"
    assert entry.added_volume == pytest.approx(8000.0, rel=1e-6), "der ganze Körper"
    assert entry.removed_volume == 0.0, "weggenommen wurde nichts"
    assert difference.added_volume == pytest.approx(8000.0, rel=1e-6)


def test_a_body_that_vanished_is_shown_as_removed() -> None:
    """Die Gegenrichtung, damit die Auskunft in beide Richtungen stimmt.

    Ein gelöschter Körper ist genauso eine Differenz wie ein neuer — und ohne
    diesen Fall bliebe die Hälfte der Zusage unbewiesen.
    """
    body = cube(20.0)
    before = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=body)})
    after = Scene(objects={})

    difference = compare_scenes(before, after)

    assert difference.deleted == ("obj_1",)
    assert "obj_1" in difference.entries, "auch das Verschwundene hat Geometrie"
    entry = difference.entries["obj_1"]
    assert entry.removed_volume == pytest.approx(8000.0, rel=1e-6)
    assert entry.added_volume == 0.0


# --- was als Änderung zählt, sagt der Drucker (RM-097) ----------------------------


def _box(height: float) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, height)))


def test_a_change_below_what_the_printer_leaves_is_no_change(profile: Profile) -> None:
    """AGENTS.md Regel 7: die Grenze lebt im Profil, nicht im Code (RM-097).

    ``NOISE_VOLUME = 1e-3`` war die Untergrenze der **Rechnung** und wurde als
    Untergrenze der **Änderung** gelesen. Zwischen beiden liegt der Fall, den
    der Kunde sieht: Ein Quader, der um zwei Zehntausendstel Millimeter
    wächst, ändert 0,02 mm³ — mehr als das Rauschen und ein Fünfzehntel
    dessen, was der Centauri überhaupt hinterlässt. Die Differenzansicht
    meldete das als Änderung, und im Chat stand „+0,00 cm³".

    Dieselbe Grenze und dieselbe Begründung wie bei
    :func:`boolean.without_effect`; ohne Profil bleibt es beim Rauschen — wer
    keinen Drucker kennt, soll keinen erfinden.
    """
    winzig = compare(_box(10.0), _box(10.0002), profile=profile)

    assert winzig.added_volume == pytest.approx(0.02, abs=0.005), "die Zahl, um die es geht"
    assert not winzig.changed, (
        "0,02 mm³ sind ein Fünfzehntel dessen, was diese Düse legt — das sieht niemand"
    )
    assert compare(_box(10.0), _box(10.0002)).changed, (
        "ohne Profil bleibt es beim Rauschen, und das ist die Antwort, die belegt ist"
    )


def test_the_same_change_reads_differently_on_a_coarser_nozzle(profile: Profile) -> None:
    """Die Gegenrichtung, und sie ist der Grund für Regel 7.

    Ein Zehntel Kubikmillimeter ist am Centauri (0,42 mm Bahn, 0,2 mm Schicht)
    das Dreifache einer Bahnportion und damit eine Änderung. An einer 0,8er
    Düse sind es 0,28 mm³ je Portion, und dieselbe Änderung verschwindet
    darin. Dieselbe Geometrie, zwei Drucker, zwei richtige Antworten — eine
    Zahl im Code kann nur eine davon geben.
    """
    grob = replace(
        profile,
        printer=replace(
            profile.printer, nozzle_diameter=0.8, extrusion_width=0.84, layer_height=0.4
        ),
    )

    assert compare(_box(10.0), _box(10.001), profile=profile).changed
    assert not compare(_box(10.0), _box(10.001), profile=grob).changed


def test_the_scene_hands_its_printer_to_the_difference(profile: Profile) -> None:
    """Die Szene bringt den Drucker mit — sonst käme die Zahl nie an.

    ``compare_scenes`` ist der Weg, den die Anwendung geht (``Session``), und
    ohne diese eine Zeile bliebe die Profilgrenze eine Möglichkeit, die
    niemand benutzt — die Sorte Lücke, die Testart „Anschluss" meint.
    """

    def scene_with(height: float, *, with_printer: bool) -> Scene:
        entry = SceneObject(id="obj_1", name="Klotz", mesh=_box(height))
        return Scene(objects={"obj_1": entry}, profile=profile if with_printer else None)

    assert not compare_scenes(
        scene_with(10.0, with_printer=True), scene_with(10.0002, with_printer=True)
    ).changed
    assert compare_scenes(
        scene_with(10.0, with_printer=False), scene_with(10.0002, with_printer=False)
    ).changed


def _cube_with_a_void(bore: float) -> MeshData:
    """Würfel 10 mit einer Bohrung ``bore`` durch die Mitte und einem
    eingeschlossenen Hohlraum 1 × 1 × 1 in einer Ecke — eine zweite Schale mit
    negativem Volumen, wie die acht Kanäle im Gartenschlauchhalter."""
    from app.core.geom.boolean import boolean

    block = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    tool = MeshData.of(trimesh.creation.cylinder(radius=bore / 2.0, height=14.0, sections=48))
    bored = boolean("difference", [block, tool]).mesh.raw
    void = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    void.apply_translation((4.0, 4.0, 0.0))
    void.invert()
    return MeshData.of(trimesh.util.concatenate([bored, void]))


def test_a_widened_bore_beside_an_enclosed_void_is_measured_by_the_balance(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Bilanz |A − B| − |B − A| = |A| − |B| gilt auch mit Hohlräumen, und
    die genaue Vorschau nennt sich nicht mehr unvollständig (Durchsicht 0.5.1,
    BOHRUNG-11).

    Am Gartenschlauchhalter (392 532 Dreiecke) trägt der Körper acht
    eingeschlossene Kanäle; Bohrung Ø 6 auf 7 aufgeweitet, schnitt der Kern
    „danach minus davor" nicht, und weil der Körper mehr als eine Schale hatte,
    galt die Bilanz nicht: `difference.incomplete`, obwohl |davor| − |danach|
    genau das Abgetragene war (60,715 mm³). Eine Schale mit negativem Volumen
    liegt im Material und zählt richtig ab; nur Schalen mit Material, die sich
    überdecken, zählten doppelt. Hier: ein Schnitt, und nichts hinzu.
    """
    from app.core.geom import difference as module

    before, after = _cube_with_a_void(7.0), _cube_with_a_void(8.0)
    calls = []
    real = module._cut

    def counted(first: MeshData, second: MeshData, quality: object) -> object:
        calls.append(1)
        return real(first, second, quality)

    monkeypatch.setattr(module, "_cut", counted)
    difference = compare(before, after, profile=profile)

    assert not difference.findings, [finding.code for finding in difference.findings]
    assert difference.removed_volume == pytest.approx(before.volume - after.volume, rel=1e-6)
    assert difference.added_volume == 0.0
    assert len(calls) == 1, "die Gegenseite steht aus der Bilanz fest"


def test_shells_with_material_that_overlap_keep_the_two_cuts() -> None:
    """Zwei Schalen mit Material, die sich überdecken, zählen im Netz doppelt —
    dort gilt die Bilanz nicht, und beide Seiten werden geschnitten."""
    from app.core.geom import difference as module

    first = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second.apply_translation((5.0, 0.0, 0.0))
    overlapping = MeshData.of(trimesh.util.concatenate([first, second]))

    assert not module._shells_apart(overlapping)
    assert module._shells_apart(_cube_with_a_void(7.0))
