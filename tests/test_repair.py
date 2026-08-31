"""Reparatur gegen die kaputten Dateien im Korpus (Bauplan §25, §34)."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.repair import (
    fill_holes,
    merge_vertices,
    open_edge_count,
    remove_degenerate_faces,
    remove_small_components,
    repair,
    stitch_t_junctions,
    unify_normals,
)
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def raw(name: str):
    """Direkt aus der Datei — unverschweißt, so wie STL sie liefert."""
    return read_mesh((MESHES / name).read_bytes(), ".stl")


def test_welding_turns_loose_triangles_into_a_body() -> None:
    mesh, removed = merge_vertices(raw("cube_clean.stl"))

    assert removed == 28, "36 STL vertices become 8"
    assert mesh.is_watertight


def test_degenerate_triangles_go_away() -> None:
    mesh, removed = remove_degenerate_faces(merge_vertices(raw("degenerate.stl"))[0])

    assert removed > 0
    assert mesh.triangle_count == 12, "the cube stays, the junk goes"


def test_filling_closes_a_single_missing_triangle() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    with_hole = body.replacing(body.raw.submesh([range(1, 12)], append=True))
    assert not with_hole.is_watertight

    closed, worked = fill_holes(with_hole)

    assert worked
    assert closed.is_watertight
    assert closed.volume == pytest.approx(8000.0, rel=1e-6)


def test_filling_reaches_its_limit_on_a_missing_wall() -> None:
    """§34: broken_open.stl fehlen drei Flächen — das ist eine Wand, kein Loch.

    Dreiecksgroße Löcher werden geschlossen; eine fehlende Wand ist das, wofür
    die Voxelstufe der Rückfallkette da ist (§17.2). Bis dahin sagt der Befund
    es klar.
    """
    body, _welded = merge_vertices(raw("broken_open.stl"))
    assert open_edge_count(body) > 0

    result = repair(body)

    assert not result.mesh.is_watertight
    assert "repair.still_open" in {finding.code for finding in result.findings}


def test_filling_a_closed_body_changes_nothing() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    same, worked = fill_holes(body)

    assert not worked
    assert same is body


def test_unifying_normals_reports_only_a_real_change() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    _mesh, flipped = unify_normals(body)
    assert not flipped, "a clean cube has nothing to correct"


def test_small_components_go_only_when_asked() -> None:
    body, _welded = merge_vertices(raw("two_components.stl"))
    assert body.component_count == 2

    kept = repair(body)
    assert kept.mesh.component_count == 2, "nothing is deleted unasked (§17.1)"

    dropped = repair(body, small_components=True)
    assert dropped.mesh.component_count == 1
    assert "repair.components_removed" in {finding.code for finding in dropped.findings}


def test_removing_small_components_keeps_the_big_one() -> None:
    body, _welded = merge_vertices(raw("two_components.stl"))
    mesh, dropped = remove_small_components(body)

    assert dropped == 1
    assert mesh.volume == pytest.approx(8000.0, rel=1e-3)


def test_repair_reports_every_step_it_took() -> None:
    result = repair(raw("degenerate.stl"))

    codes = {finding.code for finding in result.findings}
    assert "repair.welded" in codes
    assert "repair.degenerate_removed" in codes
    assert result.changed


def test_repair_says_when_it_could_not_close_the_body() -> None:
    """Ein ehrliches „immer noch offen" schlägt eine stille halbe Reparatur."""
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    half = body.replacing(body.raw.submesh([range(6)], append=True))

    result = repair(half, holes=False)
    codes = {finding.code for finding in result.findings}
    assert "repair.still_open" in codes
    assert "repair.holes_filled" not in codes, "ohne Reparatur gibt es keine Erfolgsmeldung"
    remaining = next(finding for finding in result.findings if finding.code == "repair.still_open")
    assert remaining.values["open_edges"] == open_edge_count(result.mesh) > 0
    assert "Kanten verfeinern" not in str(remaining.message)


# --- Als Operation ---------------------------------------------------------------


def test_repair_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/broken_open.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "broken_open.stl").read_bytes()

    history = History(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert "repair.still_open" in codes, "the missing wall is reported, not glossed over"
    assert result.scene.objects["obj_1"].created_by == 2, "the repair produced the object"


def test_the_repair_operation_is_registered_completely() -> None:
    spec = REGISTRY.get("repair")
    assert spec.category == "repair"
    assert (spec.consumes, spec.produces) == (1, 1)
    front = [entry.name for entry in spec.params.spec() if entry.placement == "front"]
    assert front == ["fill_holes"], "§2.4: the front side holds what people actually change"


# --- Ein Punkt auf einer Kante ist kein Loch (§25) -------------------------------


def t_junction() -> MeshData:
    """Eine Box, auf deren Oberseite ein Punkt auf einer ihrer Kanten sitzt.

    Der Defekt, den ein echter Download mitbringt: ein Eiffelturm mit 312 000
    Dreiecken hatte genau einen, drei offene Kanten über drei kollinearen
    Punkten. Die Nachbarfläche wurde beim Bau an diesem Punkt geteilt, und der
    Fläche auf der anderen Seite hat es nie jemand gesagt.
    """
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    vertices = [list(map(float, point)) for point in body.vertices]
    faces = [list(map(int, face)) for face in body.faces]

    # Eine Fläche nehmen und ihre längste Kante in der Mitte teilen — nur auf
    # dieser Seite. Die Nachbarin behält die ungeteilte Kante, und die Lücke
    # dazwischen ist ein Dreieck mit drei kollinearen Ecken.
    victim = faces.pop()
    first, second, third = victim
    middle = len(vertices)
    vertices.append([(vertices[first][axis] + vertices[second][axis]) / 2.0 for axis in range(3)])
    faces.extend([[first, middle, third], [middle, second, third]])
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


def test_a_vertex_on_an_edge_is_stitched() -> None:
    broken = t_junction()
    assert not broken.is_watertight, "otherwise this test proves nothing"

    fixed, seams = stitch_t_junctions(broken)

    assert seams == 1
    assert fixed.is_watertight
    assert fixed.volume == pytest.approx(broken.volume, abs=1e-9), "the surface does not move"
    assert fixed.triangle_count == broken.triangle_count + 1, "one face became two"


def test_stitching_keeps_the_source_of_a_split_face() -> None:
    """Beide Hälften erben die Flächenattribute des geteilten Dreiecks."""
    import numpy as np

    broken = t_junction()
    source = np.arange(broken.triangle_count, dtype=np.int64)
    broken.raw.face_attributes["source"] = source

    fixed, seams = stitch_t_junctions(broken)

    assert seams == 1
    arrived = np.asarray(fixed.raw.face_attributes["source"], dtype=np.int64)
    assert len(arrived) == fixed.triangle_count
    counts = np.bincount(arrived, minlength=broken.triangle_count)
    assert sorted(counts) == [1] * (broken.triangle_count - 1) + [2], (
        "nur das geteilte Dreieck kommt zweimal zurück"
    )


def test_stitching_ignores_scalar_metadata_instead_of_crashing() -> None:
    """Nur ein Wert je Fläche kann beim Teilen eindeutig weiterreisen."""
    broken = t_junction()
    broken.raw.face_attributes["revision"] = 7

    fixed, seams = stitch_t_junctions(broken)

    assert seams == 1
    assert fixed.is_watertight
    assert "revision" not in fixed.raw.face_attributes


def test_the_hole_filler_alone_cannot_do_it() -> None:
    """Warum es das hier gibt: ein Dreieck über drei kollinearen Punkten hat
    keine Fläche.

    ``trimesh.repair.fill_holes`` lehnt ab, und zu Recht — einen Körper mit
    einer Fläche zu schließen, die nicht da ist, ist kein Schließen.
    """
    body = t_junction().raw.copy()

    trimesh.repair.fill_holes(body)

    assert not body.is_watertight


def test_a_stitched_body_has_no_zero_area_faces() -> None:
    """Der andere Weg, ihn zu „schließen", und der Grund, warum dieser Weg
    falsch ist.
    """
    fixed, _seams = stitch_t_junctions(t_junction())

    assert not (fixed.raw.area_faces < 1e-12).any()


def test_a_sound_body_is_left_alone() -> None:
    sound = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    fixed, seams = stitch_t_junctions(sound)

    assert seams == 0
    assert fixed is sound


def test_repair_reports_the_seam_separately_from_a_hole() -> None:
    """Eine Naht und ein Loch sind verschiedene Defekte und bekommen
    verschiedene Sätze.
    """
    outcome = repair(t_junction(), holes=True)

    codes = [finding.code for finding in outcome.findings]
    assert "repair.t_junctions" in codes
    assert outcome.mesh.is_watertight


def test_many_boundary_edges_stay_fast() -> None:
    """Die vollständige Paarung war quadratisch: elf Sekunden bei 2 100
    Randkanten, hochgerechnet vierzig am eigenen Deckel — und das im
    Normalfall „Reparieren an einem Download". Der Baum-Vorfilter hält es
    flach; die Schranke ist bewusst grob, damit Fremdlast sie nicht reißt."""
    import time

    import numpy as np

    count = 400  # 1 200 Randkanten, unter MAX_STITCH_EDGES
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    for index in range(count):
        base = index * 3.0
        vertices += [[base, 0.0, 0.0], [base + 1.0, 0.0, 0.0], [base, 1.0, 0.0]]
        faces.append([3 * index, 3 * index + 1, 3 * index + 2])
    body = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)

    started = time.perf_counter()
    _mesh, seams = stitch_t_junctions(MeshData.of(body))

    assert seams == 0, "lauter getrennte Dreiecke — nichts sitzt auf einer Kante"
    assert time.perf_counter() - started < 5.0, "die Paarung darf nicht quadratisch sein"


def test_repair_stitches_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """`repair()` vernähte zweimal: einmal selbst, einmal in `fill_holes` —
    gemessener Faktor 2,1 auf demselben Netz."""
    from app.core.geom import repair as repair_module

    calls: list[int] = []
    original = repair_module.stitch_t_junctions

    def counted(mesh: MeshData) -> tuple[MeshData, int]:
        calls.append(1)
        return original(mesh)

    monkeypatch.setattr(repair_module, "stitch_t_junctions", counted)
    body, _welded = merge_vertices(raw("broken_open.stl"))

    repair_module.repair(body, holes=True)

    assert len(calls) == 1, "einmal vernähen, nicht doppelt zahlen"


def test_a_body_that_is_no_volume_never_asks_the_boolean_kernel() -> None:
    """**Der Schritt wurde an einem offenen Netz versucht und musste
    scheitern.**

    Die Booleschen Kerne rechnen mit Volumina; ein Netz mit Löchern ist keines.
    Der Aufruf endete in „Not all meshes are volumes!" — einer Fremdmeldung im
    Protokoll, die niemand liest. Gefunden beim Öffnen von
    ``weg3-generiert-aufbereiten``, also am Beispielprojekt für genau diesen
    Fall: Der Kunde klickt es an, um zu lernen, wie man erzeugte Netze
    aufbereitet.

    Geprüft wird, dass der Kern **nicht gefragt** wird — nicht bloß, dass es
    kein Ergebnis gibt. Sonst bliebe der teure Aufruf stehen und nur seine
    Meldung verschwände.
    """
    from app.core.geom import repair as repair_module

    body = raw("broken_open.stl")
    assert not body.raw.is_volume, "die Vorbedingung des Tests"

    gefragt: list[object] = []

    def zaehlen(meshes: object, **kwargs: object) -> object:
        gefragt.append(meshes)
        raise AssertionError("der Kern darf hier nicht gefragt werden")

    original = trimesh.boolean.union
    trimesh.boolean.union = zaehlen  # type: ignore[assignment]
    try:
        got, changed = repair_module.resolve_self_intersections(body)
    finally:
        trimesh.boolean.union = original  # type: ignore[assignment]

    assert not gefragt, "an einem offenen Netz wird der Kern nicht gerufen"
    assert not changed
    assert got is body, "und das Netz kommt unverändert zurück"


def test_a_closed_body_still_gets_resolved() -> None:
    """Die Vorprüfung darf den Schritt nicht abschalten, nur abkürzen."""
    from app.core.geom.repair import resolve_self_intersections

    # Verschweißt, weil die Kette das zuerst tut: Aus der Datei kommt dieses
    # Netz mit 72 losen Punkten und ist deshalb noch nicht wasserdicht — der
    # Schritt sieht es immer erst nach ``merge_vertices``.
    body, _ = merge_vertices(raw("broken_selfint.stl"))
    assert body.raw.is_volume, "die Vorbedingung des Tests"

    got, changed = resolve_self_intersections(body)

    assert changed, "an einem geschlossenen Körper arbeitet er weiter"
    assert got.is_watertight


def test_a_skipped_step_says_so_in_the_report() -> None:
    """**Was nicht getan wurde, gehört in den Bericht** (§2.7).

    Vorher stand nichts davon im Prüfbericht — wer ihn las, musste annehmen,
    dass geprüft wurde, was übersprungen worden war. Danach behauptete der
    Satz, Kanten verfeinern schließe den Körper zuverlässig, obwohl genau
    diese Operation ein offenes Netz zurückweist und Reparieren empfiehlt.

    ``broken_open`` ist der Körper, den auch die ganze Kette nicht zu einem
    Volumen macht — gemessen an sechs Dateien des Korpus, und er ist die
    einzige davon.
    """
    result = repair(raw("broken_open.stl"), self_intersections=True)

    by_code = {finding.code: finding for finding in result.findings}
    assert "repair.self_intersections_skipped" in by_code
    assert "repair.still_open" in by_code, "übersprungene Prüfung und Rest sind zwei Aussagen"
    skipped = str(by_code["repair.self_intersections_skipped"].message)
    remaining = str(by_code["repair.still_open"].message)
    assert "nicht geprüft" in skipped
    assert "Kanten verfeinern" not in skipped
    assert skipped != remaining, "Prüfung übersprungen und Rest offen dürfen sich nicht doppeln"


def test_the_step_runs_last_so_that_it_can_run_at_all() -> None:
    """**Der Schritt stand vor dem Löcherschließen und war damit wirkungslos.**

    Gemessen am Beispielprojekt ``weg3-generiert-aufbereiten``: vor dem
    Schließen kein Volumen; nach dem Schließen wasserdicht, aber die Wicklung
    uneinheitlich — also weiter kein Volumen; erst nach ``unify_normals``
    beides. Ein Netz, das die Kette repariert, bekommt seine
    Selbstdurchdringungen deshalb nur aufgelöst, wenn dieser Schritt **zuletzt**
    läuft.

    Geprüft am Ergebnis und nicht an der Quelltextreihenfolge: Was zählt, ist
    dass der Befund „aufgelöst" kommt und nicht der Befund „übersprungen".
    """
    result = repair(raw("generated_figure.stl"), self_intersections=True)

    codes = {finding.code for finding in result.findings}
    assert "repair.self_intersections" in codes, "der Schritt hat gearbeitet"
    assert "repair.self_intersections_skipped" not in codes
    assert result.mesh.raw.is_volume, "und das Ergebnis ist ein Volumen"


def test_watertight_alone_is_not_enough_for_the_boolean_kernel() -> None:
    """**Der Unterschied, an dem der erste Anlauf gescheitert ist.**

    Eine Vorprüfung auf ``is_watertight`` hätte den Aufruf durchgelassen und
    dieselbe Fremdmeldung erzeugt: Nach dem Löcherschließen war das
    Beispielnetz wasserdicht und die Wicklung trotzdem uneinheitlich. Gefragt
    wird deshalb nach ``is_volume``, und das kostet an dieser Stelle gemessene
    0,1 bis 0,2 ms — dieselbe Kantentabelle, die die Kette ohnehin aufbaut.
    """
    body, _ = merge_vertices(raw("broken_open.stl"))
    genaeht, _ = stitch_t_junctions(body)
    gefuellt, _ = fill_holes(genaeht, stitch=False)

    if gefuellt.is_watertight and not gefuellt.raw.is_volume:
        # Der gemessene Fall: dicht, aber kein Volumen.
        assert not gefuellt.raw.is_winding_consistent
    # Und in jedem Fall gilt: Volumen ist die Bedingung, nicht Dichtheit.
    from app.core.geom.repair import resolve_self_intersections

    _, wirkte = resolve_self_intersections(gefuellt)
    assert wirkte == bool(gefuellt.raw.is_volume)


def test_a_closed_body_gets_no_skip_note() -> None:
    """Kein Befund über etwas, das gelaufen ist."""
    result = repair(raw("cube_clean.stl"), self_intersections=True)

    codes = {finding.code for finding in result.findings}
    assert "repair.self_intersections_skipped" not in codes
