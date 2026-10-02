"""Reparatur gegen die kaputten Dateien im Korpus (Bauplan §25, §34)."""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
from app.core.geom.mesh import MeshCodec, MeshData, edge_table, read_mesh
from app.core.geom.repair import (
    _first_crossing_between,
    branching_edge_count,
    fill_boundary_loops,
    fill_holes,
    merge_vertices,
    open_edge_count,
    parts_that_cross,
    remove_degenerate_faces,
    remove_small_components,
    repair,
    resolve_branching_edges,
    self_intersecting_faces,
    split_pinched_vertices,
    stitch_t_junctions,
    unify_normals,
)
from app.core.perceive.features import forget_cache
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import CancelToken, Document, Profile, Quality, Source
from app.core.units import weld_digits, weld_tolerance
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def raw(name: str):
    """Direkt aus der Datei — unverschweißt, so wie STL sie liefert."""
    return read_mesh((MESHES / name).read_bytes(), ".stl")


def test_welding_turns_loose_triangles_into_a_body() -> None:
    mesh, removed = merge_vertices(raw("cube_clean.stl"))

    assert removed == 28, "36 STL vertices become 8"
    assert mesh.is_watertight


def test_a_doubled_triangle_leaves_as_a_pair_and_closes_the_body() -> None:
    """Zwei deckungsgleiche Dreiecke sind eine Tasche ohne Volumen.

    **Und wer nur eine Kopie streicht, macht es schlimmer.** Die übrigen
    Kanten des Paares haben danach je eine Fläche, also zwei offene Ränder, wo
    vorher keiner war. Genau das tat ``unique_faces`` in
    ``remove_degenerate_faces``, und deshalb steht der neue Schritt davor.

    Gemessen am 16.09.2026 an einer heruntergeladenen Waschschüssel
    (215 074 Dreiecke): eine verzweigte Kante mit vier Flächen, zwei davon
    deckungsgleich. Nur eine entfernt — zwei Ränder, weiter offen. Das Paar
    entfernt — geschlossen, Volumen unverändert.
    """
    from app.core.geom.repair import branching_edge_count, remove_doubled_faces

    cube = trimesh.creation.box((10.0, 10.0, 10.0))
    # Ein Dreieck ein zweites Mal, **andersherum umlaufen**: dieselben Ecken,
    # dieselbe Stelle — die Tasche der Waschschüssel war genau so ein Paar
    # (Flächen 165 437 und 180 933, gegenläufig; nachgemessen am 23.09.2026).
    doubled = trimesh.Trimesh(
        vertices=cube.vertices.copy(),
        faces=trimesh.util.vstack_empty([cube.faces, cube.faces[:1, ::-1]]),
        process=False,
    )
    before = MeshData.of(doubled)
    assert not before.is_watertight, "die zweite Kopie macht eine Kante vierfach"
    assert branching_edge_count(before) > 0
    assert open_edge_count(before) == 0, "verzweigt ist nicht dasselbe wie offen"

    after, removed = remove_doubled_faces(before)

    assert removed == 2, "beide Kopien, nicht eine"
    assert after.triangle_count == 11, "von dreizehn bleiben elf"
    assert branching_edge_count(after) == 0, "die vierfache Kante ist aufgelöst"

    # **Und hier hängt die Kopie an einer tragenden Wand**, anders als an der
    # Waschschüssel: Sie teilt ihre drei Kanten mit dem Würfel, nicht mit
    # ihrem Zwilling. Das Paar zu streichen nimmt die Wand mit — der Schritt
    # ist richtig gezählt und trotzdem schädlich, und genau dafür steht der
    # Schutz in ``repair`` (der Test darunter).
    assert open_edge_count(after) == 3, "drei Kanten stehen jetzt allein"

    # **Und die ganze Kette macht daraus wieder einen Würfel.** Das Paar fällt,
    # das Loch dahinter schließt der Schritt danach — eine Verzweigung kann
    # niemand schließen, ein Loch schon. Deshalb wiegt der Schutz die Summe
    # beider Defekte und nicht jeden für sich: Hier bleibt sie gleich (drei
    # Verzweigungen gegen drei Ränder), und der Tausch lohnt sich.
    healed = repair(before)
    codes = {entry.code for entry in healed.findings}

    assert "repair.doubled_removed" in codes
    assert "repair.holes_filled" in codes
    assert healed.mesh.triangle_count == 12, "der Würfel ist wieder heil"
    assert healed.mesh.is_watertight
    assert healed.mesh.raw.volume == pytest.approx(1000.0), "und sein Volumen stimmt"


def test_three_identical_triangles_keep_one() -> None:
    """Drei deckungsgleiche sind eine Tasche **und** eine Fläche.

    Die Gegenprobe zum Test darüber: Entfernt würde hier das Paar, die dritte
    Kopie wird gebraucht — sonst fehlt dem Würfel eine Wand.
    """
    from app.core.geom.repair import remove_doubled_faces

    cube = trimesh.creation.box((10.0, 10.0, 10.0))
    tripled = trimesh.Trimesh(
        vertices=cube.vertices.copy(),
        faces=trimesh.util.vstack_empty([cube.faces, cube.faces[:1], cube.faces[:1]]),
        process=False,
    )

    after, removed = remove_doubled_faces(MeshData.of(tripled))

    assert removed == 2, "zwei von dreien"
    assert after.triangle_count == 12, "der Würfel behält seine zwölf"
    assert after.is_watertight


def test_degenerate_triangles_go_away() -> None:
    mesh, removed = remove_degenerate_faces(merge_vertices(raw("degenerate.stl"))[0])

    assert removed > 0
    assert mesh.triangle_count == 12, "the cube stays, the junk goes"


def _with_a_torn_triangle(box: trimesh.Trimesh, upwards: bool) -> trimesh.Trimesh:
    """Der Würfel mit einem abgerissenen Dreieck seiner Ober- oder Unterseite.

    Das Dreieck bekommt eigene Ecken an derselben Stelle — ein Riss, wie ihn
    ein Export hinterlässt: drei offene Kanten auf jeder Seite.
    """
    vertices = np.asarray(box.vertices, dtype=float)
    faces = np.asarray(box.faces, dtype=np.int64).copy()
    side = 1.0 if upwards else -1.0
    row = int(np.flatnonzero(np.asarray(box.face_normals)[:, 2] * side > 0.9)[0])
    copies = vertices[faces[row]]
    faces[row] = len(vertices) + np.arange(3)
    return trimesh.Trimesh(vertices=np.vstack([vertices, copies]), faces=faces, process=False)


def _soup(body: trimesh.Trimesh) -> trimesh.Trimesh:
    """Dasselbe Netz, wie eine STL es speichert: jede Ecke je Dreieck einmal."""
    corners = np.asarray(body.vertices)[np.asarray(body.faces)].reshape(-1, 3)
    return trimesh.Trimesh(
        vertices=corners, faces=np.arange(len(corners)).reshape(-1, 3), process=False
    )


def _torn_where_they_touch() -> trimesh.Trimesh:
    """Zwei Würfel, die sich an einer Fläche berühren, beide an genau dieser Fläche gerissen.

    Die Ecken der Berührfläche stehen damit an offenen Rändern beider
    Würfel, und jede Punktgruppe dort trägt Kopien von beiden (RM-239).
    """
    lower = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    upper = lower.copy()
    upper.apply_translation((0.0, 0.0, 10.0))
    return trimesh.util.concatenate(
        [_with_a_torn_triangle(lower, upwards=True), _with_a_torn_triangle(upper, upwards=False)]
    )


def _corner_to_corner() -> trimesh.Trimesh:
    """Zwei Würfel, die sich an einer Ecke fast berühren (10⁻⁸ mm), der erste mit Riss."""
    first = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second = first.copy()
    second.apply_translation((10.0 + 1e-8, 10.0, 10.0))
    return trimesh.util.concatenate([_with_a_torn_triangle(first, upwards=True), second])


@pytest.mark.parametrize("offset", [0.0, 1e7], ids=["ursprung", "weit-verschoben"])
def test_a_differently_split_touching_edge_is_not_a_crossing(offset: float) -> None:
    """Ein Eckpunkt auf der fremden Kante bleibt Kantenkontakt (RM-319)."""
    first = trimesh.creation.box(extents=(1.0, 1.0, 10.0))
    first.apply_translation((0.5, 0.5, 5.0))
    second = trimesh.creation.box(extents=(1.0, 1.0, 5.0))
    second.apply_translation((-0.5, -0.5, 2.5))
    shift = np.array([offset, -offset, offset])
    first.apply_translation(shift)
    second.apply_translation(shift)
    touching_edge = trimesh.util.concatenate([first, second])

    assert parts_that_cross(touching_edge) is None
    assert parts_that_cross(touching_edge, include_face_contacts=True) is None


def test_aligned_triangle_edges_do_not_hide_a_real_crossing() -> None:
    """Eine echte Volumenüberschneidung bleibt bei gemeinsamer Kante sichtbar."""
    first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second.apply_translation((1.0, 1.0, 0.0))
    crossing = trimesh.util.concatenate([first, second])

    assert parts_that_cross(crossing) is not None
    assert parts_that_cross(crossing, include_face_contacts=True) is not None
    assert parts_that_cross(crossing, max_pairs=None, require_complete=True) is not None


def test_required_crossing_search_rejects_an_exhausted_pair_budget() -> None:
    """Ein abgebrochener Paarlauf darf bei einer Booleschen Op nicht wie Entwarnung aussehen."""
    first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second = first.copy()
    second.apply_translation((1.0, 1.0, 0.0))
    crossing = trimesh.util.concatenate([first, second])

    assert parts_that_cross(crossing, max_pairs=1) is None
    with pytest.raises(GeometryError, match="nicht vollständig") as error:
        parts_that_cross(crossing, max_pairs=1, require_complete=True)

    assert [action.id for action in error.value.suggestions] == [
        CORRECT_INPUT.id,
        CANCEL.id,
    ]


def test_unbounded_crossing_search_scans_past_the_diagnostic_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die vollständige Vorprüfung darf an der Diagnosegrenze nicht früh abbrechen."""
    from app.core.geom import intersections

    triangle = np.asarray([[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]])
    triangles = np.repeat(triangle, 40, axis=0)
    faces = np.tile(np.asarray([[0, 1, 2]], dtype=np.int64), (len(triangles), 1))
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    one = np.arange(20, dtype=np.int64)
    other = np.arange(20, 40, dtype=np.int64)
    checked: list[int] = []

    def no_crossing(
        first: np.ndarray, *_args: object, **_kwargs: object
    ) -> tuple[np.ndarray, np.ndarray]:
        checked.append(len(first))
        empty = np.zeros(len(first), dtype=bool)
        return empty, empty

    monkeypatch.setattr(intersections, "crossing_pairs", no_crossing)

    bounded = _first_crossing_between(triangles, faces, low, high, one, other, budget=1)
    assert bounded == (None, 1, False)
    assert checked == []

    unbounded = _first_crossing_between(triangles, faces, low, high, one, other, budget=None)
    assert unbounded == (None, 400, True)
    assert checked == [400]


def test_crossing_search_splits_one_high_degree_row_into_bounded_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch eine Dreiecksfläche mit sehr vielen Partnern bleibt im Blocklimit."""
    from app.core.geom import intersections
    from app.core.geom.repair import CROSSING_BLOCK

    triangle = np.asarray([[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]])
    triangles = np.repeat(triangle, 100_001, axis=0)
    faces = np.tile(np.asarray([[0, 1, 2]], dtype=np.int64), (len(triangles), 1))
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    one = np.asarray([0], dtype=np.int64)
    other = np.arange(1, len(triangles), dtype=np.int64)
    checked: list[int] = []

    def no_crossing(
        first: np.ndarray, *_args: object, **_kwargs: object
    ) -> tuple[np.ndarray, np.ndarray]:
        checked.append(len(first))
        empty = np.zeros(len(first), dtype=bool)
        return empty, empty

    monkeypatch.setattr(intersections, "crossing_pairs", no_crossing)

    result = _first_crossing_between(triangles, faces, low, high, one, other, budget=None)

    assert result == (None, 100_000, True)
    assert checked == [CROSSING_BLOCK, 100_000 - CROSSING_BLOCK]


def test_unbounded_crossing_search_checks_cancellation_between_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine laufende vollständige Suche reagiert nach dem ersten Kandidatenblock auf Abbruch."""
    from app.core.errors import OperationCancelled
    from app.core.geom import intersections
    from app.core.geom.repair import CROSSING_BLOCK

    class Signal:
        cancelled = False

        @property
        def is_cancelled(self) -> bool:
            return self.cancelled

        def raise_if_cancelled(self) -> None:
            if self.cancelled:
                raise OperationCancelled()

    signal = Signal()
    triangle = np.asarray([[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]])
    triangles = np.repeat(triangle, 100_001, axis=0)
    faces = np.tile(np.asarray([[0, 1, 2]], dtype=np.int64), (len(triangles), 1))
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    one = np.asarray([0], dtype=np.int64)
    other = np.arange(1, len(triangles), dtype=np.int64)
    checked: list[int] = []

    def cancel_after_block(
        first: np.ndarray, *_args: object, **_kwargs: object
    ) -> tuple[np.ndarray, np.ndarray]:
        checked.append(len(first))
        signal.cancelled = True
        empty = np.zeros(len(first), dtype=bool)
        return empty, empty

    monkeypatch.setattr(intersections, "crossing_pairs", cancel_after_block)

    with pytest.raises(OperationCancelled):
        _first_crossing_between(
            triangles, faces, low, high, one, other, budget=None, cancelled=signal
        )

    assert checked == [CROSSING_BLOCK]


def test_crossing_preflight_uses_the_axis_with_fewer_candidates() -> None:
    """Eine lockere X-Vorauswahl darf eine vollständige, enge Y-Suche nicht abbrechen."""
    triangles = []
    for base in range(10):
        y = 3.0 * base
        triangles.append([(0.0, y, 0.0), (1.0, y, 0.0), (0.0, y + 1.0, 0.0)])
    for base in range(10):
        y = 100.0 + 3.0 * base
        triangles.append([(0.0, y, 0.0), (1.0, y, 0.0), (0.0, y + 1.0, 0.0)])
    values = np.asarray(triangles, dtype=np.float64)
    faces = np.arange(values.shape[0] * 3, dtype=np.int64).reshape(-1, 3)
    low, high = values.min(axis=1), values.max(axis=1)

    found, spent, complete = _first_crossing_between(
        values,
        faces,
        low,
        high,
        np.arange(10, dtype=np.int64),
        np.arange(10, 20, dtype=np.int64),
        budget=1,
    )

    assert found is None
    assert spent == 0
    assert complete


def test_required_crossing_search_rejects_too_many_components() -> None:
    """Die Teilegrenze ist ein abgebrochener Lauf, keine belegte Entwarnung."""
    first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second = first.copy()
    second.apply_translation((1.0, 1.0, 0.0))
    distant = []
    for index in range(255):
        piece = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        piece.apply_translation((100.0 + 3.0 * index, 0.0, 0.0))
        distant.append(piece)
    body = trimesh.util.concatenate([first, second, *distant])

    assert parts_that_cross(body) is None
    with pytest.raises(GeometryError, match="nicht vollständig"):
        parts_that_cross(body, require_complete=True)


def test_required_crossing_search_accepts_a_complete_no_contact_result() -> None:
    """Vollständig getrennte Hüllkörper bleiben eine belegte Antwort."""
    first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second = first.copy()
    second.apply_translation((3.0, 0.0, 0.0))
    separated = trimesh.util.concatenate([first, second])

    assert parts_that_cross(separated, max_pairs=None, require_complete=True) is None


@pytest.mark.parametrize("as_soup", [False, True], ids=["indexed", "soup"])
def test_welding_closes_the_tears_and_leaves_two_touching_bodies_two(as_soup: bool) -> None:
    """Zwei Würfel, die sich berühren, bleiben zwei — auch wo beide gerissen sind (RM-239).

    Bis dahin legte das Verschweißen jede Punktgruppe als Ganzes zusammen: Die
    Risse schlossen sich, und die Berührfläche wurde dabei zu Kanten mit vier
    Flächen. In der Summe der offenen und verzweigten Kanten war das eine
    Verbesserung, also wurde es übernommen.
    """
    body = _torn_where_they_touch()
    if as_soup:
        body = _soup(body)

    welded, removed = merge_vertices(MeshData.of(body))

    assert removed > 0
    assert open_edge_count(welded) == 0
    assert branching_edge_count(welded) == 0
    assert welded.is_watertight
    assert welded.component_count == 2, "zwei Körper, die sich berühren"
    assert welded.triangle_count == 24, "kein Dreieck fällt"
    assert len(welded.raw.vertices) == 16, "jeder Würfel mit seinen acht Ecken"
    assert float(welded.volume) == pytest.approx(2000.0)


def test_welding_keeps_two_corners_on_two_sheets_apart() -> None:
    """Die Abnahme aus dem Register: Riss geschlossen, Ecken getrennt, Dreieckszahl gleich.

    Die zwei Würfel berühren sich an einer Ecke, 10⁻⁸ mm auseinander, tief
    unter der Schweißtoleranz. Zusammengelegt würde daraus eine Sanduhr-Ecke,
    an der zwei Körper hängen — und die Datei sagt, dass es zwei Ecken sind.
    """
    welded, _removed = merge_vertices(MeshData.of(_corner_to_corner()))

    assert welded.is_watertight
    assert welded.component_count == 2
    assert welded.triangle_count == 24
    assert len(welded.raw.vertices) == 16, "die zwei Ecken bleiben zwei"


def test_in_a_soup_two_corners_closer_than_eps_geom_are_one_point() -> None:
    """Die Gegenprobe als Dreieckssuppe: Unter ``EPS_GEOM`` ist ein Ort ein Ort.

    Eine Suppe hat keine Eckennummern, die zwei Ecken auseinanderhielten; was
    auf ``EPS_GEOM`` zusammenfällt, liest der Import als eine Ecke. Die zwei
    Würfel bleiben trotzdem zwei geschlossene Körper — sie teilen einen Punkt,
    keine Kante.
    """
    welded, _removed = merge_vertices(MeshData.of(_soup(_corner_to_corner())))

    assert welded.is_watertight
    assert welded.component_count == 2
    assert welded.triangle_count == 24
    assert len(welded.raw.vertices) == 15, "die Ecke, die beide berühren, ist ein Punkt"


@pytest.mark.parametrize("name", ["cube_clean.stl", "plate_holes.stl", "plate_countersunk.stl"])
def test_welding_a_clean_soup_gives_what_trimesh_gives(name: str) -> None:
    """Wo keine zwei Blätter aufeinanderliegen, verschweißt es wie bisher — Ecke für Ecke."""
    body = raw(name).raw
    reference = body.copy()
    diagonal = float(np.linalg.norm(body.extents))
    reference.merge_vertices(digits_vertex=weld_digits(weld_tolerance(diagonal)))

    welded, _removed = merge_vertices(MeshData.of(body))

    np.testing.assert_array_equal(welded.raw.vertices, reference.vertices)
    np.testing.assert_array_equal(welded.raw.faces, reference.faces)


def test_welding_keeps_a_texture_seam_open_like_trimesh() -> None:
    """Zwei Ecken an derselben Stelle mit verschiedenen Texturkoordinaten bleiben zwei.

    Dieselbe Regel wie in trimesh: Zusammengelegt verlöre eine Seite ihre
    Textur. Die Texturkoordinaten reisen mit den Ecken, die bleiben.
    """
    soup = _soup(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    uv = np.zeros((len(soup.vertices), 2))
    uv[: len(uv) // 2, 0] = 0.25  # die erste Hälfte der Dreiecke auf einer anderen Kachel
    soup.visual = trimesh.visual.TextureVisuals(uv=uv)
    reference = soup.copy()
    reference.merge_vertices(digits_vertex=weld_digits(weld_tolerance(20.0)))

    welded, _removed = merge_vertices(MeshData.of(soup), tolerance=weld_tolerance(20.0))

    np.testing.assert_array_equal(welded.raw.vertices, reference.vertices)
    np.testing.assert_array_equal(welded.raw.faces, reference.faces)
    np.testing.assert_array_equal(welded.raw.visual.uv, reference.visual.uv)


def test_welding_leaves_its_edge_count_in_the_cache_of_the_mesh() -> None:
    """Die Zählung, die das Verschweißen ohnehin braucht, ist die des Ergebnisses."""
    welded, _removed = merge_vertices(MeshData.of(_torn_where_they_touch()))
    fresh = trimesh.Trimesh(
        vertices=welded.raw.vertices.copy(), faces=welded.raw.faces.copy(), process=False
    )

    kept, counted = edge_table(welded.raw), edge_table(fresh)

    np.testing.assert_array_equal(kept.unique, counted.unique)
    np.testing.assert_array_equal(kept.inverse, counted.inverse)
    np.testing.assert_array_equal(kept.counts, counted.counts)
    assert welded.raw.is_watertight == fresh.is_watertight
    assert welded.raw.is_winding_consistent == fresh.is_winding_consistent


def test_repair_and_import_weld_the_same_way(document: Document, profile: Profile) -> None:
    """Import und Reparatur fragen dieselbe Funktion (RM-239) — und kommen zum selben Netz."""
    body = _soup(_torn_where_they_touch())
    repaired = repair(MeshData.of(body), holes=False)

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/wuerfel.stl", sha256=""
    )
    project.sources["src_1"] = body.export(file_type="stl")
    History(document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(document, profile, sources=ProjectSources(project))
    (loaded,) = result.scene.objects.values()

    for mesh in (repaired.mesh, loaded.mesh):
        assert mesh.is_watertight
        assert mesh.component_count == 2
        assert branching_edge_count(mesh) == 0
        assert mesh.triangle_count == 24


@pytest.mark.parametrize("holes", [False, True])
@pytest.mark.parametrize("damage", ["touching_shells", "collapsed_face"])
def test_repair_preserves_closed_topology_and_face_slots(damage: str, holes: bool) -> None:
    """Aufräumen darf geschlossene Schalen weder verbinden noch aufreißen."""
    import numpy as np

    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    if damage == "touching_shells":
        second = body.copy()
        second.apply_translation((0.0, 0.0, 10.0))
        body = trimesh.util.concatenate([body, second])
        silent_code = "repair.weld_skipped"
    else:
        first, second, third = body.faces[0]
        body.vertices[first] = (body.vertices[second] + body.vertices[third]) / 2.0
        silent_code = "repair.degenerate_kept"
    original = MeshData.of(body, slots=tuple(range(len(body.faces))))
    vertices, faces = body.vertices.copy(), body.faces.copy()
    assert original.is_watertight

    result = repair(original, holes=holes)

    assert result.mesh.is_watertight
    assert not result.changed
    assert result.mesh.volume == pytest.approx(original.volume)
    assert result.mesh.slots == original.slots
    np.testing.assert_array_equal(result.mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(result.mesh.raw.faces, faces)
    np.testing.assert_array_equal(original.raw.vertices, vertices)
    np.testing.assert_array_equal(original.raw.faces, faces)
    codes = {finding.code for finding in result.findings}
    # Stehen gelassen ist keine Zeile im Bericht (Bedienweg A4, 25.09.2026).
    assert silent_code not in codes
    assert not codes.intersection(
        {"repair.welded", "repair.degenerate_removed", "repair.still_open"}
    )


def test_removing_degenerate_triangles_keeps_the_slots_of_surviving_faces() -> None:
    """Eine entfernte Fläche darf die Farben der übrigen nicht löschen."""
    body = trimesh.Trimesh(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0)),
        faces=((0, 1, 2), (1, 1, 3)),
        process=False,
    )

    fixed, removed = remove_degenerate_faces(MeshData.of(body, slots=(4, 9)))

    assert removed == 1
    assert fixed.slots == (4,)


def test_filling_closes_a_single_missing_triangle() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    with_hole = body.replacing(body.raw.submesh([range(1, 12)], append=True))
    assert not with_hole.is_watertight

    closed, worked = fill_holes(with_hole)

    assert worked
    assert closed.is_watertight
    assert closed.volume == pytest.approx(8000.0, rel=1e-6)


def test_filling_a_hole_keeps_existing_face_slots() -> None:
    """Die neue Deckfläche darf die Zuweisung der alten Flächen nicht leeren."""
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    opened = body.raw.submesh([range(1, body.triangle_count)], append=True)
    with_hole = MeshData.of(opened, slots=(7,) * len(opened.faces))

    closed, worked = fill_holes(with_hole)

    assert worked
    assert len(closed.slots) == closed.triangle_count
    assert closed.slots[: with_hole.triangle_count] == with_hole.slots


@pytest.mark.parametrize("neighbour", [False, True])
def test_every_filled_triangle_inherits_material_and_colour_from_its_hole(
    neighbour: bool,
) -> None:
    """Auch innere Deckeldiagonalen gehören zum Loch, nicht zum ersten Material."""
    opened, _welded = merge_vertices(raw("broken_open.stl"))
    opened.raw.visual.face_colors = (210, 40, 25, 255)
    slots = (6,) * opened.triangle_count
    body = opened.raw
    if neighbour:
        separate, _welded = merge_vertices(raw("cube_clean.stl"))
        separate.raw.apply_translation((60.0, 0.0, 0.0))
        separate.raw.visual.face_colors = (20, 45, 220, 255)
        body = trimesh.util.concatenate([separate.raw, body])
        slots = (2,) * separate.triangle_count + slots
    source = MeshData.of(body, slots=slots)
    old_colours = body.visual.face_colors.copy()

    closed, changed = fill_holes(source)

    assert changed and closed.is_watertight
    assert closed.slots[: source.triangle_count] == source.slots
    assert set(closed.slots[source.triangle_count :]) == {6}
    np.testing.assert_array_equal(
        closed.raw.visual.face_colors[: source.triangle_count], old_colours
    )
    assert np.all(closed.raw.visual.face_colors[source.triangle_count :] == (210, 40, 25, 255))


@pytest.mark.parametrize("way", ["import", "repair", "stitch"])
def test_a_body_without_colours_gets_none_from_its_repair(way: str) -> None:
    """Ein farbloses Netz bleibt farblos, auch wenn die Reparatur es neu baut.

    ``_carried_colours`` las ``visual.face_colors`` — und trimesh erfindet dort
    für ein Netz ohne Farben ein Grau je Dreieck (102, 102, 102). Das wurde
    auf das reparierte Netz geschrieben, als wäre es eine Farbe der Datei:
    Der Laptopständer und ``broken_open.stl`` kamen nach dem Einlesen grau
    statt in der Körperfarbe ins Bild (``viewport.source_colours``), und
    *Farben zu Filamenten* machte daraus ein graues Filament, wo ein graues
    STL ein graues STL bleiben soll (``texture.to_slots``). Durchsicht 0.5.1.
    """
    from app.core.geom import texture
    from app.core.ingest.loader import normalise

    if way == "stitch":
        body = t_junction()
        assert getattr(body.raw.visual, "kind", None) is None, "die Voraussetzung: farblos"
        result, seams = stitch_t_junctions(body)
        assert seams, "sonst prüft der Test nichts"
    else:
        opened, _welded = merge_vertices(raw("broken_open.stl"))
        assert getattr(opened.raw.visual, "kind", None) is None, "die Voraussetzung: farblos"
        result = normalise(opened, "mm").mesh if way == "import" else repair(opened).mesh
        assert result.is_watertight, "sonst prüft der Test nichts"

    assert getattr(result.raw.visual, "kind", None) is None
    assert texture.face_colours(result.raw) is None


def _cube_with_a_hole(missing: int) -> MeshData:
    """Ein zweimal unterteilter Würfel, dem oben ``missing`` Dreiecke fehlen."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide().subdivide()
    top = np.flatnonzero(body.triangles_center[:, 2] > 9.9)[:missing]
    body.update_faces(~np.isin(np.arange(len(body.faces)), top))
    body.remove_unreferenced_vertices()
    return MeshData.of(body)


@pytest.mark.parametrize("missing", [1, 2, 4, 8])
def test_the_ring_filler_closes_a_hole_of_any_size(missing: int) -> None:
    """Der Füller verkettet die Randkanten selbst und schließt jeden Ring.

    ``trimesh.repair.fill_holes`` schließt Ringe aus drei und vier Kanten und
    lehnt alles darüber ab — ein Loch aus acht fehlenden Dreiecken blieb damit
    offen, und im Prüfbericht stand „kann fehlende Wände nicht ersetzen" über
    einer Lücke von drei Millimetern.

    Das Volumen belegt, dass nichts Neues entstanden ist: Die Füllung liegt in
    der Fläche, die vorher dort war.
    """
    mesh = _cube_with_a_hole(missing)
    assert not mesh.is_watertight

    filled, closed, _wide = fill_boundary_loops(mesh)

    assert closed >= 1
    assert filled.is_watertight, f"{missing} fehlende Dreiecke bleiben offen"
    assert filled.volume == pytest.approx(8000.0, rel=1e-9)


def test_the_ring_filler_keeps_the_winding_of_its_neighbours() -> None:
    """Ein Deckel, der falsch herum liegt, halbiert das Volumen.

    Gemessen am 22.09.2026: Der Ring wird ungerichtet verkettet — sonst
    scheitert die Kette dort, wo die Wicklung des Netzes uneinheitlich ist —,
    und seine Richtung kommt danach aus dem Dreieck an der ersten Kante.
    Ohne diesen Schritt kam der Würfel mit 4 000 mm³ statt 8 000 zurück.
    """
    filled, _closed, _wide = fill_boundary_loops(_cube_with_a_hole(1))

    assert filled.volume == pytest.approx(8000.0, rel=1e-9)
    assert filled.raw.volume > 0.0, "die Füllung zeigt nach außen wie ihre Nachbarn"


def test_the_ring_filler_never_makes_a_branching_edge() -> None:
    """Eine Füllung darf keine Fläche auf eine Kante legen, die schon zwei trägt.

    Der Fall stammt von einer heruntergeladenen Katze (452 314 Dreiecke): Die
    Ecken mancher Randringe sind anderswo bereits verbunden, und die
    Ohren-Triangulierung legte ihre Sehne genau darauf — aus fünfzehn
    geschlossenen Ringen wurden neun Kanten mit drei Flächen. Wo das droht,
    tritt der Fächer über die Ringmitte an ihre Stelle.
    """
    mesh = _cube_with_a_hole(8)

    filled, closed, _wide = fill_boundary_loops(mesh)

    assert closed >= 1
    assert branching_edge_count(filled) == 0, "geschlossen heißt nicht verzweigt"


def test_a_wide_opening_is_filled_and_counted() -> None:
    """Der halbe Würfel: Die Öffnung wird geschlossen und als groß gezählt."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    body.update_faces(body.triangles_center[:, 2] < 9.9)
    body.remove_unreferenced_vertices()

    filled, closed, wide = fill_boundary_loops(MeshData.of(body))

    assert closed == 1 and wide == 1, "geschlossen, und als große Öffnung gezählt"
    assert filled.is_watertight


def test_branching_edges_are_resolved_by_dropping_the_smallest_face() -> None:
    """Zwei Flächen übereinander an einer Kante — die kleinere geht.

    Gemessen an Roberts Waschschüssel (215 073 Dreiecke): eine verzweigte
    Kante, drei Flächen, zwei davon mit **null Grad** zueinander und
    0,0003 mm² gegen 0,27 mm². Ohne diesen Schritt meldete der Bericht „das ist
    kein Loch, sondern eine Verzweigung" und bot keine Handlung an.
    """
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    extra = np.asarray(body.faces[:1])
    doubled = trimesh.Trimesh(
        vertices=body.vertices.copy(),
        faces=np.vstack([np.asarray(body.faces), extra]),
        process=False,
    )
    mesh = MeshData.of(doubled)
    assert branching_edge_count(mesh) > 0

    resolved, edges = resolve_branching_edges(mesh)

    assert edges > 0
    assert branching_edge_count(resolved) == 0
    assert resolved.triangle_count == mesh.triangle_count - 1


def test_a_pinched_vertex_is_split_so_its_rings_can_close() -> None:
    """Zwei Löcher, die sich in einer Ecke berühren, sind zwei Ringe.

    An einer solchen Ecke laufen vier Randkanten zusammen; welcher Rand zu
    welchem gehört, ist der Kette nicht ablesbar, und beide Löcher blieben
    offen. Die Flächen wissen es: Ihre Fächer an der Ecke bekommen je eine
    eigene Kopie — am selben Ort, also ändert sich nichts an der Form.
    """
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    centres = body.triangles_center
    top = np.flatnonzero(centres[:, 2] > 9.9)
    # Zwei Dreiecke der Deckfläche, die sich nur in einer Ecke berühren.
    corners = [set(map(int, body.faces[index])) for index in top]
    pair = next(
        (first, second)
        for position, first in enumerate(top)
        for second in top[position + 1 :]
        if len(corners[list(top).index(first)] & corners[list(top).index(second)]) == 1
    )
    body.update_faces(~np.isin(np.arange(len(body.faces)), np.asarray(pair)))
    body.remove_unreferenced_vertices()
    mesh = MeshData.of(body)
    assert not mesh.is_watertight

    split, count = split_pinched_vertices(mesh)

    assert count >= 1, "die Ecke wurde aufgetrennt"
    filled, _closed, _wide = fill_boundary_loops(split)
    assert filled.is_watertight, "und danach schließen beide Löcher"
    assert filled.volume == pytest.approx(8000.0, rel=1e-9)


def test_two_holes_touching_in_one_face_close_without_a_fold() -> None:
    """Zwei fehlende Deckdreiecke mit gemeinsamer Ecke sind zwei Löcher, keine Acht.

    Die Ecke wurde aufgetrennt, und weil beide Löcher in derselben Fläche
    liegen, trug jede Kopie je eine Kante beider: Der Ring lief als Acht, der
    Fächer über seine Mitte faltete sich, und die Reparatur meldete „dicht"
    über sieben Durchdringungen. Die Erkennung fand danach die Deckfläche
    nicht mehr (Durchsicht 24.09.2026). Geschlossen wird jetzt jede Schlaufe
    für sich — mit genau den zwei Dreiecken, die fehlten.
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    faces = np.asarray(whole.raw.faces)
    top = np.flatnonzero(whole.raw.face_normals[:, 2] > 0.99)
    corners = [set(faces[index].tolist()) for index in top]
    pair = next(
        (int(top[first]), int(top[second]))
        for first in range(len(top))
        for second in range(first + 1, len(top))
        if len(corners[first] & corners[second]) == 1
    )
    keep = np.setdiff1d(np.arange(len(faces)), pair)
    broken = MeshData.of(whole.raw.submesh([keep], append=True, repair=False))
    assert not broken.is_watertight, "otherwise this test proves nothing"

    result = repair(broken)

    assert result.mesh.is_watertight
    assert self_intersecting_faces(result.mesh) == (), "keine Faltung über der Ecke"
    assert result.mesh.triangle_count == whole.triangle_count, "genau die zwei fehlenden"
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    # 80 mal 50 ohne vier Bohrungen Ø 5,2 (tests/data/README.md); die Vielecke
    # der Bohrungen sind eingeschrieben, die Fläche also ein wenig größer.
    expected = 80.0 * 50.0 - 4.0 * np.pi * 2.6 * 2.6
    upper = [
        feature
        for feature in detect(result.mesh).values()
        if feature.kind == "face" and feature.params.get("normal", (0.0, 0.0, 0.0))[2] > 0.99
    ]
    assert len(upper) == 1, "die Deckfläche ist wieder eine Fläche"
    assert upper[0].params["area"] == pytest.approx(expected, rel=1e-3)


def test_a_fold_is_never_taken_as_a_fill() -> None:
    """Ein Ring, der von seiner Mitte aus nicht ganz zu sehen ist, bleibt offen.

    Der Fächer über die Mitte klappt dort rückwärts über seine Nachbarn — ein
    geschlossenes Netz mit einer Durchdringung, das der Bericht als gefülltes
    Loch zählte. Ein U-förmiger Ring in der Ebene: Die Ohren schließen ihn,
    der Fächer allein nicht.
    """
    from app.core.geom.repair import _folds, _loop_fan, _ring_normal

    ring = np.asarray(
        [
            [0, 0, 0],
            [30, 0, 0],
            [30, 30, 0],
            [20, 30, 0],
            [20, 5, 0],
            [10, 5, 0],
            [10, 30, 0],
            [0, 30, 0],
        ],
        dtype=float,
    )
    loop = list(range(len(ring)))
    centre = ring.mean(axis=0)
    normal = _ring_normal(ring, centre)
    assert normal is not None
    reachable = np.vstack([ring, centre[None, :]])

    assert _folds(reachable[_loop_fan(loop, len(ring))], normal), "der Fächer klappt um"
    from app.core.geom.repair import _loop_triangles

    ears = _loop_triangles(ring, loop)
    assert len(ears) == len(ring) - 2
    assert not _folds(reachable[ears], normal), "die Ohren liegen richtig"


def test_a_missing_wall_is_closed_and_said_so() -> None:
    """§34: ``broken_open.stl`` fehlen drei Flächen — eine Wand, kein Loch.

    **Bis zum 22.09.2026 blieb sie offen**, und der Befund sagte, warum. Das
    war der falsche Dienst: Der Kunde will drucken, und ein Modell, das die
    Reparatur mit einem Loch zurückgibt, hilft ihm nicht (Entscheidung Robert:
    „alles bei der Reparatur beheben"). Geschlossen wird jetzt auch die Wand —
    und weil dort eine Fläche entsteht, die im Modell nicht war, sagt es eine
    **Warnung**, die den Blick darauf lenkt; zurücknehmen lässt sich der
    Schritt mit Strg+Z.
    """
    body, _welded = merge_vertices(raw("broken_open.stl"))
    assert open_edge_count(body) > 0

    result = repair(body)

    assert result.mesh.is_watertight, "der Körper kommt geschlossen zurück"
    codes = {finding.code for finding in result.findings}
    assert "repair.wide_hole_filled" in codes, "und die große Öffnung steht als Warnung da"
    assert "repair.still_open" not in codes
    wide = next(f for f in result.findings if f.code == "repair.wide_hole_filled")
    assert wide.severity == "warning"
    # Der Klick auf die Zeile fliegt zur Öffnung, *Stelle zeigen* sagt es
    # sichtbar, und der Rückweg ist ein Knopf (Entscheidung Robert,
    # 24.09.2026): „Offen lassen".
    assert [action.id for action in wide.suggestions] == ["show_location", "leave_open"]
    assert wide.location is not None
    low, high = body.bounds.minimum, body.bounds.maximum
    assert all(low[axis] - 1e-6 <= wide.location[axis] <= high[axis] + 1e-6 for axis in range(3))


@pytest.mark.parametrize("name", ["partially_open.stl", "broken_open.stl"])
def test_a_closed_opening_carries_its_rim_for_the_view(name: str) -> None:
    """*Stelle zeigen* kann die neue Fläche umranden, weil der Befund ihren Rand trägt.

    Vorher trug er nur die Mitte: Die Ansicht setzte einen Ring in der
    Auswahlfarbe auf einen Körper in der Auswahlfarbe, und die neue Fläche war
    nicht zu erkennen (Handbuchbild *Ein Modell reparieren*, 3). Der Sollwert
    kommt aus dem Eingang, nicht aus der Reparatur: Jede Randkante des Befunds
    ist eine offene Kante des gelesenen Netzes, und zusammen schließen sie
    einen Ring um die Mitte.
    """
    body, _welded = merge_vertices(raw(name))
    points = np.asarray(body.raw.vertices, dtype=float)
    table = edge_table(body.raw)
    pairs = np.asarray(body.raw.edges, dtype=np.int64)[table.rows(1)]
    open_edges = {
        tuple(sorted((tuple(points[first].tolist()), tuple(points[second].tolist()))))
        for first, second in pairs.tolist()
    }

    result = repair(body)
    wide = next(f for f in result.findings if f.code == "repair.wide_hole_filled")

    assert wide.outline, "der Befund trägt den Rand der geschlossenen Öffnung"
    rim = {tuple(sorted((tuple(map(float, a)), tuple(map(float, b))))) for a, b in wide.outline}
    assert rim <= open_edges, "jede Randkante war vorher offen"
    corners: dict[tuple[float, ...], int] = {}
    for first, second in rim:
        corners[first] = corners.get(first, 0) + 1
        corners[second] = corners.get(second, 0) + 1
    assert set(corners.values()) == {2}, "ein geschlossener Ring, keine losen Enden"
    assert wide.location is not None
    middle = np.mean(np.asarray(list(corners), dtype=float), axis=0)
    span = float(np.ptp(np.asarray(list(corners), dtype=float), axis=0).max())
    assert float(np.linalg.norm(middle - np.asarray(wide.location))) <= 0.5 * span, (
        "der Ring liegt um die Stelle, zu der die Kamera fliegt"
    )


def test_filling_a_closed_body_changes_nothing() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    same, worked = fill_holes(body)

    assert not worked
    assert same is body


def test_unifying_normals_reports_only_a_real_change() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    _mesh, flipped = unify_normals(body)
    assert not flipped, "a clean cube has nothing to correct"


def test_a_reversed_top_triangle_is_corrected_even_when_volume_stays_the_same() -> None:
    """Eine +Z-Fläche ändert beim Umdrehen den Volumenbeitrag entlang X nicht."""
    source, _welded = merge_vertices(raw("cube_clean.stl"))
    body = source.raw.copy()
    top = int(np.flatnonzero(body.face_normals[:, 2] > 0.5)[0])
    faces = body.faces.copy()
    faces[top] = faces[top, ::-1]
    body.faces = faces
    broken = MeshData.of(body, slots=tuple(range(len(faces))))
    assert not broken.raw.is_winding_consistent
    assert float(broken.raw.volume) == pytest.approx(20.0**3)

    result = repair(broken)

    assert result.changed, "the operation must keep the corrected mesh"
    assert result.mesh.raw.is_winding_consistent
    assert result.mesh.volume == pytest.approx(20.0**3)
    assert result.mesh.slots == broken.slots
    assert "repair.normals_flipped" in {finding.code for finding in result.findings}
    np.testing.assert_array_equal(broken.raw.faces, faces)


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


def test_removing_small_components_keeps_the_surviving_face_slots() -> None:
    body, _welded = merge_vertices(raw("two_components.stl"))
    coloured = MeshData.of(body.raw, slots=tuple(range(body.triangle_count)))

    mesh, dropped = remove_small_components(coloured)

    assert dropped == 1
    assert len(mesh.slots) == mesh.triangle_count
    assert set(mesh.slots) < set(coloured.slots)


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
    assert "repair.wide_hole_filled" in codes, "die geschlossene Wand steht im Bericht"
    assert result.scene.objects["obj_1"].created_by == 2, "the repair produced the object"


def test_the_repair_operation_is_registered_completely() -> None:
    spec = REGISTRY.get("repair")
    assert spec.category == "repair"
    assert (spec.consumes, spec.produces) == (1, 1)
    front = [entry.name for entry in spec.params.spec() if entry.placement == "front"]
    # Was nach dem Einlesen noch etwas ändert (Durchsicht 24.09.2026): Der
    # Import verschweißt, räumt leere Dreiecke und gleicht Außenseiten an.
    assert front == ["fill_holes", "self_intersections", "small_components"], (
        "§2.4: the front side holds what people actually change"
    )
    defaults = spec.params()
    assert defaults.self_intersections, "Entscheidung Robert, 24.09.2026: Vorgabe an"


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


def t_junctions_on_one_edge(points: int) -> MeshData:
    """Wie :func:`t_junction`, nur sitzen ``points`` Punkte auf derselben Kante.

    So sieht es an einer CAD-Ausgabe aus, deren Nachbarfläche feiner geteilt
    ist: Die lange Kante auf der einen Seite kennt keinen der Punkte, die auf
    der anderen Seite an ihr liegen.
    """
    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    vertices = [list(map(float, point)) for point in body.vertices]
    faces = [list(map(int, face)) for face in body.faces]
    first, second, third = faces.pop()
    chain = [first]
    for step in range(1, points + 1):
        share = step / (points + 1)
        chain.append(len(vertices))
        vertices.append(
            [
                vertices[first][axis] + share * (vertices[second][axis] - vertices[first][axis])
                for axis in range(3)
            ]
        )
    chain.append(second)
    faces.extend([start, end, third] for start, end in itertools.pairwise(chain))
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


@pytest.mark.parametrize("points", [2, 3, 7])
def test_every_vertex_on_one_edge_is_stitched(points: int) -> None:
    """Ein Durchgang teilt eine Fläche an einem Punkt; der Rest blieb offen.

    Der Lochfüller schloss den Spalt über den übrigen kollinearen Punkten
    danach mit Dreiecken ohne Fläche — dicht, aber mit Nullflächen, die der
    Bericht als geschlossenes Loch zählte (Sonde 24.09.2026).
    """
    broken = t_junctions_on_one_edge(points)
    assert not broken.is_watertight, "otherwise this test proves nothing"

    fixed, seams = stitch_t_junctions(broken)

    assert seams == points, "die Nachbarfläche wird an jedem Punkt geteilt"
    assert fixed.is_watertight
    assert fixed.volume == pytest.approx(8000.0, abs=1e-9), "20³ — die Oberfläche bleibt"
    assert not (fixed.raw.area_faces < 1e-12).any()

    outcome = repair(broken)
    assert outcome.mesh.is_watertight
    assert not (outcome.mesh.raw.area_faces < 1e-12).any(), "kein Loch über kollinearen Punkten"
    codes = [finding.code for finding in outcome.findings]
    assert "repair.t_junctions" in codes
    assert "repair.holes_filled" not in codes, "eine Naht ist kein Loch"


def test_stitching_keeps_the_source_of_a_split_face() -> None:
    """Beide Hälften erben die Flächenattribute des geteilten Dreiecks."""
    import numpy as np

    broken = t_junction()
    source = np.arange(broken.triangle_count, dtype=np.int64)
    broken.raw.face_attributes["source"] = source
    colours = np.column_stack((source * 10, source * 3, source * 7, np.full(len(source), 255)))
    broken.raw.visual.face_colors = colours

    fixed, seams = stitch_t_junctions(broken)

    assert seams == 1
    arrived = np.asarray(fixed.raw.face_attributes["source"], dtype=np.int64)
    assert len(arrived) == fixed.triangle_count
    counts = np.bincount(arrived, minlength=broken.triangle_count)
    assert sorted(counts) == [1] * (broken.triangle_count - 1) + [2], (
        "nur das geteilte Dreieck kommt zweimal zurück"
    )
    np.testing.assert_array_equal(fixed.raw.visual.face_colors, colours[arrived])


def test_stitching_keeps_the_slot_of_a_split_face() -> None:
    """Beide neuen Hälften tragen den Slot ihres gemeinsamen Vorgängers."""
    broken = t_junction()
    coloured = MeshData.of(broken.raw, slots=tuple(range(broken.triangle_count)))

    fixed, seams = stitch_t_junctions(coloured)

    assert seams == 1
    assert len(fixed.slots) == fixed.triangle_count
    counts = [fixed.slots.count(slot) for slot in coloured.slots]
    assert sorted(counts) == [1] * (broken.triangle_count - 1) + [2]


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


@pytest.mark.performance
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


@pytest.mark.parametrize("offset", [0.0, 1_000_000.125])
def test_a_closed_body_still_gets_resolved(offset: float) -> None:
    """Die Vereinigung enthält das gemeinsame Volumen genau einmal, auch weit vom Ursprung."""
    from app.core.geom.repair import resolve_self_intersections

    # Verschweißt, weil die Kette das zuerst tut: Aus der Datei kommt dieses
    # Netz mit 72 losen Punkten und ist deshalb noch nicht wasserdicht — der
    # Schritt sieht es immer erst nach ``merge_vertices``.
    body, _ = merge_vertices(raw("broken_selfint.stl"))
    body.raw.apply_translation((offset, offset, offset))
    assert body.raw.is_volume, "die Vorbedingung des Tests"

    got, changed = resolve_self_intersections(body)

    assert changed, "an einem geschlossenen Körper arbeitet er weiter"
    assert got.is_watertight
    # Zwei Würfel mit Kantenlänge 20, Versatz 8 auf jeder Achse: 12³ überlappen.
    assert float(got.raw.volume) == pytest.approx(2 * 20.0**3 - 12.0**3)
    assert self_intersecting_faces(got) == ()


def test_import_closes_open_crossing_shells_without_starting_an_intersection_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Import schließt Ränder, ohne die Diagnose des Reparaturschritts zu übernehmen."""
    from app.core.geom import repair as repair_module
    from app.core.ingest.loader import normalise

    body, _ = merge_vertices(raw("broken_selfint.stl"))
    top = int(np.flatnonzero(body.raw.face_normals[:, 2] > 0.5)[0])
    opened = MeshData.of(
        trimesh.Trimesh(
            vertices=body.raw.vertices.copy(),
            faces=np.delete(body.raw.faces, top, axis=0),
            process=False,
        )
    )
    assert not opened.is_watertight
    original = repair_module.self_intersection_check
    inspected: list[MeshData] = []

    def counted(
        mesh: MeshData, cancelled: CancelToken | None = None
    ) -> tuple[tuple[int, ...], bool]:
        inspected.append(mesh)
        return original(mesh, cancelled)

    monkeypatch.setattr(repair_module, "self_intersection_check", counted)

    result = normalise(opened, "mm")

    assert not inspected, "automatic import repair must not start the intersection scan"
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(2 * 20.0**3)
    assert "repair.holes_filled" in {finding.code for finding in result.findings}
    assert not any(
        action.id == "correct_input"
        for finding in result.findings
        for action in finding.suggestions
    ), "the import settings have no intersection-repair switch"


def test_default_repair_explains_how_to_resolve_crossing_faces(
    document: Document,
    profile: Profile,
) -> None:
    """Der Reparaturschritt bietet die Schnittreparatur an seinen eigenen Einstellungen an."""
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/broken_selfint.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "broken_selfint.stl").read_bytes()
    history = History(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    history.apply(
        _("Reparieren"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"self_intersections": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    found = next(
        finding
        for finding in result.scene.report.findings
        if finding.code == "repair.self_intersections_detected"
    )
    assert found.op_id == document.ops[-1].id
    assert found.object_id == "obj_1"
    assert found.severity == "warning"
    # Ein Knopf, der den Schritt mit dem Haken neu rechnet — statt eines
    # Menüwegs im Satz und eines Dialogs, der die Klappe zu lässt.
    assert [action.id for action in found.suggestions] == [
        "resolve_intersections",
        "show_locations",
    ]


def test_enabling_intersection_repair_leaves_a_clean_cavity_alone() -> None:
    """Eine intakte Innenschale bleibt Hohlraum und braucht keine Neuvernetzung."""
    outer, _ = merge_vertices(raw("cube_clean.stl"))
    inner = outer.raw.copy()
    inner.apply_scale(0.5)
    inner.invert()
    body = MeshData.of(trimesh.util.concatenate([outer.raw, inner]))
    assert body.raw.is_volume

    result = repair(body, self_intersections=True)

    assert not result.changed
    assert result.findings == []
    assert result.mesh.volume == pytest.approx(20.0**3 - 10.0**3)
    np.testing.assert_array_equal(result.mesh.raw.faces, body.raw.faces)


def test_intersection_repair_keeps_ambiguous_cavity_shells_and_names_the_limit() -> None:
    """Innenschalen sind kein Materialstück, das separat vereinigt werden darf."""
    crossing, _ = merge_vertices(raw("broken_selfint.stl"))
    inner, _ = merge_vertices(raw("cube_clean.stl"))
    inner.raw.apply_scale(0.1)
    inner.raw.apply_translation((-5.0, -5.0, -5.0))
    inner.raw.invert()
    body = MeshData.of(trimesh.util.concatenate([crossing.raw, inner.raw]))
    assert body.raw.is_volume

    result = repair(body, self_intersections=True)

    assert not result.changed
    np.testing.assert_array_equal(result.mesh.raw.faces, body.raw.faces)
    unresolved = next(
        finding
        for finding in result.findings
        if finding.code == "repair.self_intersections_unresolved"
    )
    assert unresolved.severity == "warning"
    assert [action.id for action in unresolved.suggestions] == ["show_locations"]
    assert "repair.self_intersections" not in {finding.code for finding in result.findings}


@pytest.mark.parametrize("failure", ["exception", "unchanged", "unchecked"])
def test_an_unsuccessful_intersection_repair_never_reports_success(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Kernaufruf allein beweist weder Wirkung noch ein geprüftes Ergebnis."""
    from app.core.geom import boolean as boolean_module
    from app.core.geom import repair as repair_module
    from app.core.types import SolverInfo

    body, _ = merge_vertices(raw("broken_selfint.stl"))
    original = boolean_module.boolean

    def unsuccessful(*args: object, **kwargs: object) -> boolean_module.BooleanOutcome:
        if failure == "exception":
            raise ValueError("no usable volume")
        if failure == "unchanged":
            return boolean_module.BooleanOutcome(body, SolverInfo(strategy="direct"))
        result = original(*args, **kwargs)
        monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)
        return result

    monkeypatch.setattr(boolean_module, "boolean", unsuccessful)

    result = repair(body, self_intersections=True)

    assert not result.changed
    assert result.solver is None
    np.testing.assert_array_equal(result.mesh.raw.faces, body.raw.faces)
    codes = {finding.code for finding in result.findings}
    assert "repair.self_intersections_unresolved" in codes
    assert "repair.self_intersections" not in codes


def test_an_incomplete_intersection_check_is_not_a_clean_bill_of_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch ohne bisherigen Treffer ist eine abgebrochene Suche unvollständig."""
    from app.core.geom import repair as repair_module

    body, _ = merge_vertices(raw("cube_clean.stl"))
    monkeypatch.setattr(repair_module, "intersection_budget", lambda _triangles: 0)

    result = repair(body, inspect_intersections=True)

    assert not result.changed
    assert [finding.code for finding in result.findings] == ["repair.self_intersections_incomplete"]
    # Ein Hinweis ohne Knopf: Es gibt keine markierten Stellen, zu denen er
    # führen könnte, und eine Warnung im Normalfall wäre keine mehr.
    incomplete = result.findings[0]
    assert incomplete.severity == "info"
    assert incomplete.suggestions == ()


def test_the_intersection_budget_grows_with_the_mesh() -> None:
    """Das Budget reißt an gewöhnlichen Teilen nicht und bleibt linear.

    Gezählt werden die Paare nach dem Achsenfilter — sie kosten die Zeit. Die
    Sollwerte sind am Korpus gemessen (Durchsicht 24.09.2026, Sonde
    ``s12_budget_groessen``): Besteckkorb 8 672 Dreiecke 0,82 Millionen Paare,
    Spiderman 885 570 Dreiecke 5,91 Millionen, Drache 2 330 374 Dreiecke 14,45
    Millionen — alle drei laufen vollständig.
    """
    from app.core.geom.repair import (
        INTERSECTION_PAIRS_PER_TRIANGLE,
        MAX_INTERSECTION_PAIRS,
        intersection_budget,
    )

    assert intersection_budget(10) == MAX_INTERSECTION_PAIRS
    assert intersection_budget(8_672) >= 820_000, "der Besteckkorb wird ganz geprüft"
    assert intersection_budget(885_570) >= 5_910_000, "der Spiderman auch"
    assert intersection_budget(2_330_374) >= 14_450_000, "und der Drache"
    assert intersection_budget(1_000_000) == INTERSECTION_PAIRS_PER_TRIANGLE * 1_000_000


def test_cancelling_during_intersection_repair_keeps_the_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Abbruch nach dem nativen Rechenschritt wird nicht als Reparaturfehler verschluckt."""
    from app.core.errors import OperationCancelled
    from app.core.geom import boolean as boolean_module
    from app.core.scene.cancel import CancelSignal

    body, _ = merge_vertices(raw("broken_selfint.stl"))
    faces = body.raw.faces.copy()
    cancelled = CancelSignal()
    original = boolean_module.boolean

    def cancel_after_calculation(*args: object, **kwargs: object) -> boolean_module.BooleanOutcome:
        result = original(*args, **kwargs)
        cancelled.cancel()
        return result

    monkeypatch.setattr(boolean_module, "boolean", cancel_after_calculation)
    with pytest.raises(OperationCancelled):
        repair(body, self_intersections=True, cancelled=cancelled)
    np.testing.assert_array_equal(body.raw.faces, faces)


def test_resolving_self_intersections_transfers_material_slots() -> None:
    """Eine Neuvernetzung behält die nächstgelegene Quellfarbe."""
    from app.core.geom.repair import resolve_self_intersections

    body, _ = merge_vertices(raw("broken_selfint.stl"))
    coloured = MeshData.of(body.raw, slots=(6,) * body.triangle_count)

    got, changed = resolve_self_intersections(coloured)

    assert changed
    assert len(got.slots) == got.triangle_count
    assert set(got.slots) == {6}


def test_a_skipped_step_says_so_in_the_report() -> None:
    """**Was nicht getan wurde, gehört in den Bericht** (§2.7).

    Vorher stand nichts davon im Prüfbericht — wer ihn las, musste annehmen,
    dass geprüft wurde, was übersprungen worden war. Danach behauptete der
    Satz, Kanten verfeinern schließe den Körper zuverlässig, obwohl genau
    diese Operation ein offenes Netz zurückweist und Reparieren empfiehlt.

    Gefahren wird das mit abgeschaltetem Löcherschließen, denn seit dem
    22.09.2026 schließt die Kette auch eine fehlende Wand (siehe
    ``test_a_missing_wall_is_closed_and_said_so``) — und ein geschlossener
    Körper überspringt nichts mehr. Wer die Löcher auslässt, hat den Fall, um
    den es hier geht: ein offenes Netz, dessen Selbstdurchdringungen nicht
    geprüft werden können.
    """
    crossing, _ = merge_vertices(raw("broken_selfint.stl"))
    opened = MeshData.of(
        crossing.raw.submesh([range(1, crossing.triangle_count)], append=True, repair=False)
    )
    result = repair(opened, holes=False, self_intersections=True)

    by_code = {finding.code: finding for finding in result.findings}
    assert "repair.self_intersections_skipped" in by_code
    assert "repair.still_open" in by_code, "übersprungene Prüfung und Rest sind zwei Aussagen"
    skipped = by_code["repair.self_intersections_skipped"]
    assert "reason" not in skipped.values, "der Grund steht im Satz, nicht als Kennung"
    assert "geschlossenen Modell" in str(skipped.message)
    assert "Kanten verfeinern" not in str(skipped.message)
    assert str(skipped.message) != str(by_code["repair.still_open"].message), (
        "Prüfung übersprungen und Rest offen dürfen sich nicht doppeln"
    )

    # **Und über nichts wird nichts gesagt**: Ein offenes Netz ohne eine
    # Überschneidung bekommt keine Zeile über einen Schritt, der nichts zu
    # tun gehabt hätte — sie schickte den Kunden auf eine Suche.
    quiet = repair(raw("broken_open.stl"), holes=False, self_intersections=True)
    assert "repair.self_intersections_skipped" not in {f.code for f in quiet.findings}


def test_the_step_runs_last_so_that_it_can_run_at_all() -> None:
    """Schließen und Ausrichten müssen vor der Vereinigung der überlappenden Würfel laufen."""
    body, _ = merge_vertices(raw("broken_selfint.stl"))
    faces = body.raw.faces.copy()
    # Die fehlende +Z-Fläche muss zuerst geschlossen werden. Eine weitere
    # umgedrehte Fläche verlangt danach eine einheitliche Wicklung.
    top = int(np.flatnonzero(body.raw.face_normals[:, 2] > 0.5)[0])
    faces[1] = faces[1, ::-1]
    opened = MeshData.of(
        trimesh.Trimesh(
            vertices=body.raw.vertices.copy(), faces=np.delete(faces, top, axis=0), process=False
        )
    )
    result = repair(opened, self_intersections=True)

    codes = {finding.code for finding in result.findings}
    assert "repair.self_intersections" in codes, "der Schritt hat gearbeitet"
    assert "repair.self_intersections_skipped" not in codes
    assert result.mesh.raw.is_volume, "und das Ergebnis ist ein Volumen"
    assert result.mesh.volume == pytest.approx(2 * 20.0**3 - 12.0**3)
    assert self_intersecting_faces(result.mesh) == ()


def test_watertight_alone_is_not_enough_for_the_boolean_kernel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    faces = gefuellt.raw.faces.copy()
    faces[1] = faces[1, ::-1]
    gefuellt = MeshData.of(
        trimesh.Trimesh(vertices=gefuellt.raw.vertices.copy(), faces=faces, process=False)
    )
    assert gefuellt.is_watertight and not gefuellt.raw.is_winding_consistent
    from app.core.geom import boolean as boolean_module
    from app.core.geom.repair import resolve_self_intersections

    def must_not_run(*args: object, **kwargs: object) -> None:
        pytest.fail("inconsistent winding must not enter the volume solver")

    monkeypatch.setattr(boolean_module, "boolean", must_not_run)
    unchanged, worked = resolve_self_intersections(gefuellt)
    assert not worked and unchanged is gefuellt


def test_a_closed_body_gets_no_skip_note() -> None:
    """Kein Befund über etwas, das gelaufen ist."""
    result = repair(raw("cube_clean.stl"), self_intersections=True)

    codes = {finding.code for finding in result.findings}
    assert "repair.self_intersections_skipped" not in codes


@pytest.mark.performance
def test_a_mesh_written_twice_loses_its_copies_in_linear_time() -> None:
    """Eine Schale, die ein Export zweimal schrieb, ist eine Gruppe je Dreieck.

    ``remove_doubled_faces`` suchte je Gruppe ihre Mitglieder über alle
    Dreiecke — quadratisch: An einer Kugel mit 327 680 Dreiecken, zweimal
    geschrieben, waren das 2·10¹¹ Vergleiche und Minuten beim Import (Review
    22.09.2026). Jetzt sortiert es einmal. Die Schranke ist grob, damit sie
    auf einer belasteten Maschine hält; die alte Fassung lag weit darüber.
    """
    import time

    from app.core.geom.repair import remove_doubled_faces

    ball = trimesh.creation.icosphere(subdivisions=7, radius=40.0)
    twice = trimesh.Trimesh(
        vertices=ball.vertices.copy(),
        faces=np.vstack([np.asarray(ball.faces), np.asarray(ball.faces)]),
        process=False,
    )

    started = time.perf_counter()
    after, removed = remove_doubled_faces(MeshData.of(twice))
    elapsed = time.perf_counter() - started

    assert removed == len(ball.faces), "je Paar die Kopie, nicht die Kugel"
    assert after.triangle_count == len(ball.faces)
    assert elapsed < 30.0, f"{elapsed:.1f} s für {len(twice.faces)} Dreiecke"


def test_a_copy_in_the_same_direction_is_a_duplicate_not_a_pocket() -> None:
    """Gleich umlaufen heißt: dieselbe Fläche zweimal — eine bleibt.

    Eine Tasche entsteht aus zwei **gegenläufigen** Flächen; ihre Kanten tragen
    je eine Fläche in jede Richtung, und beide zu streichen schließt das Netz
    (die Waschschüssel). Zwei gleich umlaufende Kopien sind dagegen dieselbe
    Fläche doppelt geschrieben. Bis zum 23.09.2026 fielen auch sie paarweise:
    Die Wand ging mit, und *Reparieren* musste ein Loch stopfen, das es selbst
    gerissen hatte.
    """
    from app.core.geom.repair import remove_doubled_faces

    cube = trimesh.creation.box((10.0, 10.0, 10.0))
    doubled = trimesh.Trimesh(
        vertices=cube.vertices.copy(),
        faces=trimesh.util.vstack_empty([cube.faces, cube.faces[:1]]),
        process=False,
    )

    after, removed = remove_doubled_faces(MeshData.of(doubled))

    assert removed == 1, "die Kopie, nicht die Wand"
    assert after.triangle_count == 12
    assert after.is_watertight
    assert open_edge_count(after) == 0


def _written_twice(inverted: bool) -> MeshData:
    ball = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    second = np.asarray(ball.faces)[:, ::-1] if inverted else np.asarray(ball.faces)
    return MeshData.of(
        trimesh.Trimesh(
            vertices=ball.vertices.copy(),
            faces=np.vstack([np.asarray(ball.faces), second]),
            process=False,
        )
    )


@pytest.mark.parametrize("inverted", [False, True], ids=["same", "inverted"])
def test_repairing_a_shell_written_twice_keeps_one_shell(inverted: bool) -> None:
    """*Reparieren* ließ von einer doppelt geschriebenen Schale nichts übrig.

    Gemessen am 23.09.2026: Eine Kugel, deren 1280 Dreiecke ein Export zweimal
    schrieb, kam aus *Reparieren* mit **null** Dreiecken zurück und dem Satz,
    das Modell sei noch offen — jedes Dreieck war die Hälfte eines Paares,
    und jedes Paar fiel. Das Einlesen tat es nicht (dort behält
    ``unique_faces`` eine Kopie), nur der Knopf.

    Gleich umlaufende Kopien sind Doppelungen und behalten eine. Gegenläufige
    sind Taschen — außer wenn mit ihnen ein ganzes Teil verschwände: Dann ist
    es kein Rest einer Tasche, sondern das Teil selbst, und eine Kopie bleibt.
    """
    body = _written_twice(inverted)

    healed = repair(body)

    assert healed.mesh.triangle_count == 1280
    assert healed.mesh.is_watertight
    assert float(healed.mesh.raw.volume) == pytest.approx(
        float(trimesh.creation.icosphere(subdivisions=3, radius=20.0).volume), rel=1e-12
    )


# --- Durchsicht 24.09.2026: was die Reparatur nicht tun darf -------------------


def _box(size: float = 20.0, at: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(at)
    return body


def test_a_fin_on_an_edge_goes_and_the_wall_stays() -> None:
    """Eine Flosse — ein drittes Dreieck an einer Würfelkante — ist die
    überzählige Fläche, nicht die Wand darunter.

    Bis zur Durchsicht entschied allein die Fläche, und die Flosse war größer
    als das Wanddreieck: Die Wand ging, die Lochfüllung schloss aus den übrigen
    Rändern, und der Würfel kam mit 7 000 statt 8 000 mm³ zurück (Sonde
    ``geometrie_nach_import`` vom 24.09.2026). Jetzt geht zuerst, was an seinen
    übrigen Kanten lose hängt.
    """
    body = _box()
    edge = body.edges_unique[0]
    tip = (body.vertices[edge[0]] + body.vertices[edge[1]]) / 2.0 + np.array([15.0, 15.0, 0.0])
    finned = trimesh.Trimesh(
        vertices=np.vstack([body.vertices, tip]),
        faces=np.vstack([body.faces, [edge[0], edge[1], len(body.vertices)]]),
        process=False,
    )
    mesh = MeshData.of(finned)
    assert branching_edge_count(mesh) == 1, "sonst prüft der Test nichts"

    result = repair(mesh)

    assert result.mesh.is_watertight
    assert result.mesh.triangle_count == 12, "die Flosse ist weg, die Wand steht"
    assert result.mesh.volume == pytest.approx(8000.0, rel=1e-12)
    codes = {finding.code for finding in result.findings}
    assert "repair.branching_resolved" in codes
    assert "repair.wide_hole_filled" not in codes, "kein Loch, also keine neue Fläche"


def test_a_sheet_stays_a_sheet_and_the_report_says_what_helps() -> None:
    """Eine Fläche ohne Dicke wird nicht zu einem Körper mit null Volumen.

    Bis zur Durchsicht schloss die Lochfüllung das Quadrat mit seiner eigenen
    Rückseite: vier Dreiecke, „geschlossen", Volumen null, vier Durchdringungen
    (Sonde vom 24.09.2026). Kein Slicer druckt das. Die Fläche bleibt offen,
    und der Bericht nennt den Weg, der hilft (Entscheidung Robert,
    24.09.2026): „Dicke geben".
    """
    sheet = trimesh.Trimesh(
        vertices=[[0, 0, 0], [30, 0, 0], [30, 30, 0], [0, 30, 0]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )

    result = repair(MeshData.of(sheet))

    assert result.mesh.triangle_count == 2, "nichts dazugelegt"
    assert not result.mesh.is_watertight
    by_code = {finding.code: finding for finding in result.findings}
    assert "repair.holes_filled" not in by_code
    assert "repair.still_open" not in by_code, "die Ränder nennt der Befund zur Fläche"
    flat = by_code["repair.no_thickness"]
    assert str(flat.message) == "Das Modell ist eine Fläche ohne Dicke."
    assert [action.id for action in flat.suggestions] == ["give_thickness", "show_locations"]


def test_a_lone_triangle_is_not_closed_with_its_back() -> None:
    """Das kleinste Blatt: ein Dreieck. Sein Ring hat drei Kanten, und ein
    Deckel darauf wäre das Dreieck noch einmal, andersherum."""
    alone = trimesh.Trimesh(
        vertices=[[0, 0, 0], [10, 0, 0], [0, 10, 0]], faces=[[0, 1, 2]], process=False
    )

    result = repair(MeshData.of(alone))

    assert result.mesh.triangle_count == 1
    assert {finding.code for finding in result.findings} >= {"repair.no_thickness"}


def test_a_splinter_beside_a_body_goes_and_is_no_sheet() -> None:
    """Ein loses Splitterdreieck neben einem Würfel ist Schmutz, kein Blatt.

    Die Lochfüllung schloss es früher mit seiner Rückseite zur Tasche ohne
    Volumen; offen gelassen hielte es jede Boolesche Operation an, und
    *Reparieren und erneut versuchen* bekäme das Aushöhlen der erzeugten Figur
    aus Weg 3 nie durch. Unter dem Anteil der Kleinstteile
    (``SMALL_COMPONENT_SHARE``) geht es, und ein Hinweis sagt es; ein Blatt
    darüber bleibt und bekommt „Dicke geben".
    """
    body = _box()
    splinter = trimesh.Trimesh(
        vertices=[[30, 0, 0], [30.1, 0, 0], [30, 0.1, 0]], faces=[[0, 1, 2]], process=False
    )
    both = MeshData.of(trimesh.util.concatenate([body, splinter]))

    result = repair(both)

    assert result.mesh.triangle_count == 12, "der Splitter ist weg, der Würfel steht"
    assert result.mesh.is_watertight
    by_code = {finding.code: finding for finding in result.findings}
    assert str(by_code["repair.splinters_removed"].message) == "Ein loser Splitter wurde entfernt."
    assert by_code["repair.splinters_removed"].severity == "info"
    assert "repair.no_thickness" not in by_code
    assert "repair.still_open" not in by_code


def test_a_sheet_beside_a_body_stays_and_is_named() -> None:
    """Die Gegenprobe: Ein Blatt, das kein Splitter ist, bleibt und wird genannt."""
    body = _box()
    sheet = trimesh.Trimesh(
        vertices=[[30, 0, 0], [45, 0, 0], [45, 15, 0], [30, 15, 0]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )

    result = repair(MeshData.of(trimesh.util.concatenate([body, sheet])))

    assert result.mesh.triangle_count == 14
    flat = next(f for f in result.findings if f.code == "repair.no_thickness")
    assert str(flat.message) == "Ein Teil des Modells ist eine Fläche ohne Dicke."


def test_an_inverted_cube_beside_a_right_one_is_turned_outward() -> None:
    """Zwei getrennte Würfel, einer innen-außen verkehrt: zusammen Volumen null.

    Bis zur Durchsicht fragte die Reparatur nur das Vorzeichen des ganzen
    Körpers, fand es nicht negativ und sagte nichts — über einem Teil, das
    jeder Slicer je nach Füllregel als Loch liest. Jede Schale, die frei
    steht, ist Material und muss positiv sein.
    """
    right = _box()
    wrong = _box(at=(40.0, 0.0, 0.0))
    wrong.invert()
    assert wrong.volume == pytest.approx(-8000.0, rel=1e-12), "sonst prüft der Test nichts"
    pair = MeshData.of(trimesh.util.concatenate([right, wrong]))

    result = repair(pair)

    assert result.mesh.raw.volume == pytest.approx(16000.0, rel=1e-12)
    assert "repair.normals_flipped" in {finding.code for finding in result.findings}


def test_a_right_hollow_body_stays_beside_an_inverted_cube() -> None:
    """Ein verkehrter Würfel wird gedreht — der richtige Hohlraum daneben nicht.

    Die Gesamtumkehr nach dem Vorzeichen des ganzen Netzes kippte ihn mit:
    Summe −3 648, alles gedreht, der freie Würfel zurück — und der Hohlraum
    stand auf +1 000, 19 648 statt 17 648 mm³ (Review R3, 24.09.2026).
    """
    from app.core.geom.repair import turn_shells_outward

    cavity = _box(10.0)
    cavity.invert()
    apart = _box(22.0, at=(60.0, 0.0, 0.0))
    apart.invert()
    body = trimesh.util.concatenate([_box(20.0), cavity, apart])

    assert turn_shells_outward(body)

    assert body.volume == pytest.approx(8000.0 - 1000.0 + 22.0**3, rel=1e-12)


def test_a_cavity_keeps_facing_inward() -> None:
    """Die Gegenprobe: Eine negative Schale **in** einer positiven ist ein
    Hohlraum und bleibt, wie sie ist."""
    from app.core.geom.repair import turn_shells_outward

    outer = _box(20.0)
    inner = _box(10.0)
    inner.invert()
    hollow = trimesh.util.concatenate([outer, inner])
    assert hollow.volume == pytest.approx(7000.0, rel=1e-12)

    turned = turn_shells_outward(hollow)

    assert not turned
    assert hollow.volume == pytest.approx(7000.0, rel=1e-12)


def test_winding_follows_the_majority_not_the_first_triangle() -> None:
    """Liegt gerade das Startdreieck verkehrt, dreht sich trotzdem nur die Minderheit.

    trimesh behielt die Richtung des ersten Dreiecks, das es fand, und drehte
    alles andere danach; an einer offenen Kuppel kam so die ganze Fläche
    innen-außen an (Befund B12 der Durchsicht 24.09.2026, dort wegen der
    Laufzeit ersetzt).
    """
    from app.core.geom.repair import wind_consistently

    dome = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    dome.update_faces(np.asarray(dome.triangles_center)[:, 2] > 0.0)
    dome.remove_unreferenced_vertices()
    first = int(np.asarray(dome.face_adjacency)[0, 0])
    picked = sorted({first, *range(0, len(dome.faces), 9)})
    wrong = np.asarray(dome.faces).copy()
    wrong[picked] = wrong[picked][:, ::-1]
    body = trimesh.Trimesh(vertices=np.asarray(dome.vertices), faces=wrong, process=False)

    wind_consistently(body)

    assert np.array_equal(np.asarray(body.faces), np.asarray(dome.faces))


def test_a_part_inside_a_part_is_named_and_left_as_it_is() -> None:
    """Eine nach außen gewickelte Schale in einer anderen wird gemeldet, nicht geraten.

    Hohlraum verkehrt herum oder doppeltes Teil — das weiß nur der Kunde, und
    Slicer drucken es je nach Füllregel hohl oder voll (Rest von Befund B9 der
    Durchsicht 24.09.2026: kein Befund, 9 000 statt 7 000 mm³).
    """
    both = MeshData.of(trimesh.util.concatenate([_box(20.0), _box(10.0, at=(2.0, 1.0, 0.5))]))

    result = repair(both)

    inside = [entry for entry in result.findings if entry.code == "repair.part_inside"]
    assert len(inside) == 1 and inside[0].severity == "warning"
    assert inside[0].location == pytest.approx((2.0, 1.0, 0.5))
    assert [action.id for action in inside[0].suggestions] == ["split_bodies"]
    assert inside[0].values["components"] == 2, "der Knopf plant seine Ausgänge daraus"
    assert result.mesh.volume == pytest.approx(9000.0, rel=1e-12)


@pytest.mark.parametrize("case", ["buried", "apart", "cavity", "rattle", "undecided"])
def test_the_nested_parts_question_keeps_material_and_uncertainty_apart(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Nur ein entschiedenes Nein belegt freie Teile; eine Rassel liegt in Luft."""
    from app.core.geom import repair as repair_module
    from app.core.geom.repair import has_nested_parts, parts_inside_parts

    inner = _box(10.0, at=(2.0, 1.0, 0.5))
    pieces = [_box(20.0), inner]
    if case == "apart":
        inner.apply_translation((40.0, 0.0, 0.0))
    elif case == "cavity":
        inner.invert()
    elif case == "rattle":
        inner.invert()
        pieces.append(_box(2.0, at=(2.0, 1.0, 0.5)))
    elif case == "undecided":
        monkeypatch.setattr(repair_module._Shells, "inside", lambda *args: None)
    body = trimesh.util.concatenate(pieces)
    expected = None if case == "undecided" else case == "buried"

    assert has_nested_parts(body) is expected
    assert len(parts_inside_parts(body)) == int(case == "buried")


@pytest.mark.parametrize(
    "case",
    ["cavity", "rattle", "negative_root", "negative_child", "positive_child", "undecided"],
)
def test_material_families_assign_only_direct_void_skins(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Innenhaut und Materialinsel bleiben getrennt; ungültige Elternketten sperren."""
    from app.core.geom import repair as repair_module

    outer = _box(20.0)
    cavity = _box(10.0, at=(2.0, 1.0, 0.5))
    cavity.invert()
    island = _box(2.0, at=(2.0, 1.0, 0.5))
    pieces = [outer, cavity]
    if case == "rattle":
        pieces.append(island)
    elif case == "negative_root":
        cavity.apply_translation((40.0, 0.0, 0.0))
    elif case == "negative_child":
        island.invert()
        pieces.append(island)
    elif case == "positive_child":
        cavity.invert()
    elif case == "undecided":
        monkeypatch.setattr(repair_module._Shells, "inside", lambda *args: None)
    body = trimesh.util.concatenate(pieces)

    families = repair_module.material_part_families(body)

    if case not in ("cavity", "rattle"):
        assert families is None
        return
    assert families is not None
    assert len(families) == (2 if case == "rattle" else 1)
    assert sorted(np.concatenate(families).tolist()) == list(range(len(body.faces)))
    volumes = sorted(
        float(
            trimesh.Trimesh(vertices=body.vertices, faces=body.faces[faces], process=False).volume
        )
        for faces in families
    )
    expected = [2.0**3, 20.0**3 - 10.0**3] if case == "rattle" else [20.0**3 - 10.0**3]
    assert volumes == pytest.approx(expected, abs=1e-9)


def test_material_families_cancel_while_assigning_a_negative_skin(monkeypatch):
    """Auch die neu befragte negative Innenhaut bekommt den Schalter des Aufrufers."""
    from app.core.errors import OperationCancelled
    from app.core.geom import repair as repair_module
    from app.core.scene.cancel import CancelSignal

    cavity = _box(10.0, at=(2.0, 1.0, 0.5))
    cavity.invert()
    body = trimesh.util.concatenate([_box(20.0), cavity])
    token = CancelSignal()
    original = repair_module._Shells.inside
    calls = 0

    def stop_at_the_inner_skin(shells, inner, outer):
        nonlocal calls
        calls += 1
        assert shells.volumes[inner] < 0.0
        assert shells._cancelled is token
        token.cancel()
        return original(shells, inner, outer)

    monkeypatch.setattr(repair_module._Shells, "inside", stop_at_the_inner_skin)
    with pytest.raises(OperationCancelled):
        repair_module.material_part_families(body, cancelled=token)
    assert calls == 1


@pytest.mark.parametrize("phase", ["shells", "ray", "certificate", "crossing"])
def test_the_nested_parts_question_can_cancel_during_its_geometric_proof(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """Schalenaufbau, Strahl, Gitterzertifikat und genaue Suche tragen den Abbruch."""
    from app.core.errors import OperationCancelled
    from app.core.geom import repair as repair_module
    from app.core.perceive import features
    from app.core.scene.cancel import CancelSignal

    body = trimesh.util.concatenate([_box(20.0), _box(10.0, at=(2.0, 1.0, 0.5))])
    token = CancelSignal()
    if phase == "shells":
        module, name = repair_module, "_labelled_shells"
    elif phase == "ray":
        module, name = features, "_point_inside_shell"
    else:
        crossing, _plate_faces = _block_across_a_bore(inverted=False)
        body = crossing.raw
        if phase == "certificate":
            module, name = features, "_shells_do_not_cross"
        else:
            module, name = repair_module, "_first_crossing_between"
            monkeypatch.setattr(features, "_shells_do_not_cross", lambda *args, **kwargs: False)
    original = getattr(module, name)
    calls = 0
    certificate_checks = 0

    def stopped(*args, **kwargs):
        nonlocal calls, certificate_checks
        calls += 1
        if phase == "certificate":
            supplied_check = kwargs.get("check_cancelled")

            def cancelled_during_grid():
                nonlocal certificate_checks
                certificate_checks += 1
                if certificate_checks == 2:
                    token.cancel()
                if supplied_check is not None:
                    supplied_check()

            kwargs["check_cancelled"] = cancelled_during_grid
            original(*args, **kwargs)
            pytest.fail("Das Gitterzertifikat lief trotz Abbruch bis zu seiner Antwort.")
        if phase == "crossing":
            assert kwargs["cancelled"] is token
        result = original(*args, **kwargs)
        token.cancel()
        return result

    monkeypatch.setattr(module, name, stopped)
    with pytest.raises(OperationCancelled):
        repair_module.has_nested_parts(body, cancelled=token)
    assert calls == 1, "Der Abbruch muss an der gewählten Geometriephase ankommen."
    if phase == "certificate":
        assert certificate_checks == 2, "Der Abbruch muss während der Gitterprüfung erfolgen."


def test_parts_that_all_face_outward_shoot_no_ray_to_be_turned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lauter richtig gewickelte Teile: Beim Ausrichten fliegt kein Strahl.

    ``turn_shells_outward`` dreht nur, was frei steht und verkehrt ist. Sind
    alle Schalen positiv, gibt es nichts zu drehen — gefragt wurde trotzdem
    jede gegen jede, über Hüllquader und Strahl, und 16 000 getrennte Würfel
    kosteten 18,6 s für „nichts zu tun" (Review 25.09.2026). Ein einzelner
    Körper brauchte schon keinen Strahl (Review R20), viele richtige auch
    nicht. Das Teil im Teil bleibt gemeldet: Das fragt ``parts_inside_parts``.
    """
    import app.core.perceive.features as features
    from app.core.geom.repair import parts_inside_parts, turn_shells_outward

    rays: list[int] = []
    real = features._point_inside_shell

    def counted(*args, **kwargs):  # type: ignore[no-untyped-def]
        rays.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(features, "_point_inside_shell", counted)
    inner = [_box(2.0, at=(-6.0 + 4.0 * step, 0.0, 0.0)) for step in range(4)]
    body = trimesh.util.concatenate([_box(20.0), *inner])

    assert not turn_shells_outward(body)
    assert rays == [], "nichts zu drehen, nichts zu fragen"
    assert len(parts_inside_parts(body)) == 4, "das Teil im Teil meldet die andere Frage"


@pytest.mark.performance
def test_many_separate_parts_are_asked_about_their_shells_quickly() -> None:
    """16 000 getrennte Würfel: Ausrichten und Teil-im-Teil-Frage bleiben kurz.

    Jede Schale fragte die Hüllquader aller anderen einzeln ab — quadratisch,
    18,6 s für ``turn_shells_outward`` und 24,9 s für ``parts_inside_parts``
    an einem Netz, an dem nichts zu tun war (Review 25.09.2026). Beim Import
    lief das ohne Fortschritt. Die Schranke ist bewusst grob.
    """
    import time

    from app.core.geom.repair import parts_inside_parts, turn_shells_outward

    side = 26
    cubes = [
        _box(1.0, at=(2.0 * (index % side), 2.0 * (index // side % side), 2.0 * (index // side**2)))
        for index in range(16_000)
    ]
    body = trimesh.util.concatenate(cubes)

    started = time.perf_counter()
    turned = turn_shells_outward(body)
    nested = parts_inside_parts(body)
    elapsed = time.perf_counter() - started

    assert not turned and nested == []
    assert elapsed < 12.0, f"{elapsed:.1f} s — die Schalen dürfen sich nicht paarweise fragen"


@pytest.mark.parametrize("case", ["cavity", "apart", "rattle"])
def test_a_cavity_or_a_part_beside_is_no_part_inside(case: str) -> None:
    """Die Gegenproben: ein richtiger Hohlraum, zwei Teile nebeneinander — und eine Rassel.

    Die Kugel frei im Hohlraum liegt in zwei Schalen, der positiven außen und
    der negativen des Hohlraums; dort ist Luft, und jede Füllregel druckt sie
    voll (Review R4, 24.09.2026).
    """
    if case == "rattle":
        outer = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
        hollow = trimesh.creation.icosphere(subdivisions=3, radius=15.0)
        hollow.invert()
        ball = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
        both = MeshData.of(trimesh.util.concatenate([outer, hollow, ball]))
    else:
        inner = _box(10.0) if case == "cavity" else _box(10.0, at=(40.0, 0.0, 0.0))
        if case == "cavity":
            inner.invert()
        both = MeshData.of(trimesh.util.concatenate([_box(20.0), inner]))

    result = repair(both)

    assert "repair.part_inside" not in {entry.code for entry in result.findings}


def _block_across_a_bore(*, inverted: bool) -> tuple[MeshData, int]:
    """Die Lochplatte mit einem Klotz quer durch die Wand ihrer ersten Bohrung.

    Der Klotz 8 × 8 × 4 steht mittig auf der Bohrung Ø 5,2: Seine Ecken liegen
    5,66 mm von der Achse im Material, seine Mitte in der Bohrung, und seine
    Hülle liegt ganz in der Hülle der Platte. Zurück kommen das Netz und die
    Zahl der Plattendreiecke — dahinter beginnt der Klotz.
    """
    from app.core.perceive.features import detect

    plate, _welded = merge_vertices(raw("plate_holes.stl"))
    bore = min(
        (feature for feature in detect(plate).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )
    block = trimesh.creation.box(extents=(8.0, 8.0, 4.0))
    block.apply_translation(bore.params["centre"])
    if inverted:
        block.invert()
    joined = trimesh.util.concatenate([plate.raw, block])
    return MeshData.of(joined), plate.triangle_count


@pytest.mark.parametrize("inverted", [False, True], ids=["right", "inverted"])
def test_a_part_through_the_wall_of_another_is_not_inside_it(inverted: bool) -> None:
    """Ein Teil, das durch die Wand eines anderen läuft, liegt nicht „ganz darin".

    Gefragt wurde an einer einzigen Ecke: Lag sie im anderen Teil und die
    Hülle in dessen Hülle, hieß das Teil „ganz in einem anderen", und der
    Bericht sagte, Slicer druckten es hohl oder voll. Am Bohrmaschinenhalter
    aus ``F:\\3D Dateien`` waren das fünf Teile, am Laptopständer zwei, an der
    Bildschirmabdeckung eines — alle acht schnitten die Wand ihres
    „Behälters" (Durchsicht 0.5.1). Solche Teile stecken ineinander; das sagt
    der andere Satz, mit *Überschneidungen auflösen*. Die Hohlraumerkennung
    fragt dafür seit je zuerst, ob sich die Schalen schneiden
    (``perceive.features._shells_do_not_cross``).

    Und ein verkehrt gewickeltes Teil in dieser Lage ist frei, nicht
    umschlossen: Es wird nach außen gedreht wie jedes freie.
    """
    from app.core.geom.mesh import signed_volume

    body, plate_faces = _block_across_a_bore(inverted=inverted)

    result = repair(body, self_intersections=False, inspect_intersections=True)

    codes = {entry.code for entry in result.findings}
    assert "repair.part_inside" not in codes
    assert "repair.self_intersections_detected" in codes, "gesagt wird die Überschneidung"
    block = result.mesh.raw.submesh([np.arange(plate_faces, result.mesh.triangle_count)])[0]
    assert signed_volume(block) == pytest.approx(8.0 * 8.0 * 4.0, rel=1e-9), "nach außen"


@pytest.mark.parametrize("far", [0.0, 1e4, 1e5])
def test_a_skin_without_thickness_goes_far_from_the_origin_too(far: float) -> None:
    """Eine Haut ohne Dicke fällt auch zehn Meter vom Ursprung entfernt.

    ``remove_hollow_shells`` summierte das Volumen je Teil über den Ursprung —
    derselbe Fehler wie Befund B16 der Durchsicht 24.09.2026, dessen Behebung
    (``_shell_volumes``, ``mesh.signed_volume``) an dieser dritten Stelle
    vorbeiging. Ab zehn Metern bestand das Volumen der Haut aus Rundung, lag
    über ``EPS_GEOM``, und der Körper behielt drei Teile statt einem (Review
    25.09.2026). Die Bereinigung läuft nach Verrunden und Flächenoperationen,
    also dort, wo der Körper gerade steht.
    """
    from app.core.geom.repair import remove_hollow_shells

    # Ein Viereck, beidseitig belegt: dicht, Volumen null — zwei Teile, weil die
    # Diagonale vier Flächen trägt.
    skin = trimesh.Trimesh(
        vertices=[[20.0, 0.0, 0.0], [21.3, 0.0, 0.0], [21.3, 0.7, 0.3], [20.0, 0.7, 0.3]],
        faces=[[0, 1, 2], [0, 2, 3], [2, 1, 0], [3, 2, 0]],
        process=False,
    )
    both = trimesh.util.concatenate([_box(10.0), skin])
    both.vertices = np.asarray(both.vertices) + np.array([far, 0.7 * far, 0.3 * far])
    body = MeshData.of(both)
    assert body.component_count == 3, "sonst prüft der Test die falsche Ausgangslage"

    cleaned, dropped = remove_hollow_shells(body)

    assert dropped == 2, "beide Hälften der Haut"
    assert cleaned.component_count == 1
    assert cleaned.triangle_count == 12, "der Würfel bleibt ganz"


@pytest.mark.parametrize("far", [1e8, 1e9])
def test_a_small_body_far_from_the_origin_stays_the_right_way_out(far: float) -> None:
    """Ein Würfel von 1 mm bei 10⁸ mm wird nicht umgestülpt.

    Auf den Ursprung bezogen bestand sein Volumen aus Rundung, bei 10⁸ mm
    minus 5·10⁷ mm³, und die Reparatur drehte einen richtigen Würfel auf links
    (Befund B16 der Durchsicht 24.09.2026). Gerechnet wird jetzt nahe an der
    Schale.
    """
    from app.core.geom.mesh import signed_volume

    box = _box(1.0)
    box.vertices = np.asarray(box.vertices) + far
    mesh = MeshData.of(box)

    fixed, changed = unify_normals(mesh)
    result = repair(mesh)

    assert not changed
    assert np.array_equal(np.asarray(fixed.raw.faces), np.asarray(box.faces))
    assert signed_volume(result.mesh.raw) == pytest.approx(1.0, rel=1e-9)
    assert result.findings == []


def test_crossed_edges_are_counted_not_just_detected() -> None:
    """``is_winding_consistent`` sagt ja oder nein; der Bericht braucht die Zahl.

    Ein Würfel mit einem umgedrehten Dreieck: dessen drei Kanten laufen je
    gleich herum wie ihr Nachbar. Die Reparatur richtet sie und meldet danach
    keine mehr — die Zeile bleibt für Nähte, die ``fix_winding`` nicht lösen
    kann.
    """
    from app.core.geom.repair import _crossed_edge_count

    body = _box()
    faces = np.asarray(body.faces).copy()
    faces[0] = faces[0][::-1]
    turned = MeshData.of(trimesh.Trimesh(vertices=body.vertices, faces=faces, process=False))

    assert _crossed_edge_count(MeshData.of(_box())) == 0
    assert _crossed_edge_count(turned) == 3

    result = repair(turned)

    assert _crossed_edge_count(result.mesh) == 0
    assert "repair.normals_inconsistent" not in {finding.code for finding in result.findings}


def test_a_cut_sphere_shell_closes_where_its_chords_are_taken() -> None:
    """Eine unter dem Äquator abgeschnittene Kugelschale schließt — ohne Falte.

    Die Ecken ihres Randrings sind an vier Stellen schon anders verbunden. Bis
    zur Durchsicht prüfte erst die fertige Füllung diese Kanten, verwarf alle
    Ohren und fiel auf den Fächer, der rückwärts klappte: Die Schale blieb
    offen, obwohl 92 gültige Ohren sie schlossen (Befund B14 der Durchsicht
    24.09.2026). Jetzt überspringt das Ohrenschneiden eine belegte Sehne wie
    eine reflexe Ecke.
    """
    sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    keep = ~(sphere.triangles_center[:, 2] > -2.0)
    shell = MeshData.of(
        trimesh.Trimesh(vertices=sphere.vertices.copy(), faces=sphere.faces[keep], process=False)
    )

    result = repair(shell)

    assert result.mesh.is_watertight
    assert result.mesh.raw.is_winding_consistent
    assert self_intersecting_faces(result.mesh) == (), "kein Fächer, der umklappt"
    assert result.mesh.raw.volume > 0.0


def test_a_window_around_a_cylinder_stays_open() -> None:
    """Die Gegenprobe: Ein Fenster über gut 240° des Umfangs ist kein Loch.

    Ein flacher Deckel darüber läge als Membran quer durch das Innere — HEAD
    schloss es so, mit 7 656 statt rund 9 425 mm³. Offen und gesagt ist die
    ehrliche Antwort.
    """
    cylinder = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=64)
    cylinder = cylinder.subdivide().subdivide()
    centres = cylinder.triangles_center
    side = np.abs(np.hypot(centres[:, 0], centres[:, 1]) - 10.0) < 1.0
    window = side & (centres[:, 0] > -5.0) & (np.abs(centres[:, 2]) < 8.0)
    opened = MeshData.of(
        trimesh.Trimesh(vertices=cylinder.vertices.copy(), faces=cylinder.faces[~window])
    )

    result = repair(opened)

    assert not result.mesh.is_watertight
    assert "repair.still_open" in {finding.code for finding in result.findings}


def test_a_fill_takes_the_slot_of_its_own_rim() -> None:
    """Ein Fülldreieck mit einer Randkante trägt den Slot, den diese Kante trägt.

    An einem Loch zwischen zwei Filamenten trugen Fülldreiecke einen Slot, den
    keine ihrer Randkanten trug: Eine Diagonale erbte den Slot ihres ersten
    Dreiecks und stand vor der eigenen Randkante (Befund B10 der Durchsicht
    24.09.2026) — im Druck ein Filamentwechsel mitten im Deckel. Am offenen
    Zylinder, halb in jedem Filament, lag die alte Wahl an 16 von 30
    Fülldreiecken daneben (Mutationsprobe vom 24.09.2026).
    """
    cylinder = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=32)
    top = cylinder.triangles_center[:, 2] > 9.99
    body = trimesh.Trimesh(
        vertices=cylinder.vertices.copy(), faces=cylinder.faces[~top], process=False
    )
    slots = np.where(body.triangles_center[:, 0] < 0.0, 1, 2)
    source = MeshData.of(body, slots=tuple(int(slot) for slot in slots))
    owners: dict[tuple[int, int], list[int]] = {}
    for index, face in enumerate(np.asarray(body.faces).tolist()):
        for first, second in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            owners.setdefault((min(first, second), max(first, second)), []).append(index)
    rim = {edge: int(slots[faces[0]]) for edge, faces in owners.items() if len(faces) == 1}

    filled, closed, _wide = fill_boundary_loops(source)

    assert closed == 1 and filled.is_watertight
    added = np.asarray(filled.raw.faces)[source.triangle_count :]
    assert len(added) == 30, "32 Randkanten, ein Ring, Ohren"
    wrong = 0
    for position, face in enumerate(added.tolist()):
        own = {
            rim[(min(first, second), max(first, second))]
            for first, second in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))
            if (min(first, second), max(first, second)) in rim
        }
        if own and filled.slots[source.triangle_count + position] not in own:
            wrong += 1
    assert wrong == 0


def test_filling_stops_when_asked_to() -> None:
    """Ein Abbruch greift während der Lochfüllung, nicht erst danach.

    Ein gewellter Ring aus 8 000 Kanten kostete 12,8 s, und ein nach einer
    halben Sekunde angeforderter Abbruch griff nach 11,9 (Befund B13 der
    Durchsicht 24.09.2026). Das Ohrenschneiden fragt jetzt je tausend
    Versuche, der Füller je Ring.
    """
    from app.core.errors import OperationCancelled
    from app.core.geom.repair import _fill_loops

    class Signal:
        """Meldet den Abbruch ab der zweiten Frage — mitten in der Füllung."""

        asked = 0

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked > 1:
                raise OperationCancelled()

    signal = Signal()
    with pytest.raises(OperationCancelled):
        _fill_loops(_cube_with_a_hole(8), signal)  # type: ignore[arg-type]
    assert signal.asked >= 2


def _crossing_itself() -> MeshData:
    """Ein unterteilter Würfel, dessen obere Ecke durch den Boden gestoßen ist.

    Eine Schale, geschlossen und einheitlich gewickelt, und doch laufen 18
    Dreieckspaare schräg durcheinander — die Eigenkreuzung in klein, wie sie
    an Spiderman und Piratenschiff zu Hunderten vorkommt.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    corners = np.asarray(box.vertices).copy()
    top = np.flatnonzero(np.all(np.abs(corners - 10.0) < 1e-9, axis=1))
    corners[top[0]] = (0.0, 0.0, -18.0)
    return MeshData.of(trimesh.Trimesh(vertices=corners, faces=box.faces.copy(), process=False))


@pytest.mark.parametrize("resolve", [True, False], ids=["resolving", "old_step"])
def test_a_shell_crossing_itself_is_named_and_not_united(
    resolve: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Eigenkreuzung einer Schale löst keine Vereinigung — also kein Versuch.

    Am Korpus scheiterte sie ausnahmslos (Achterröhre, Spiderman,
    Piratenschiff), nach 13 bis 49 Sekunden und mit „ließen sich nicht sicher
    auflösen"; an einem alten Schritt riet der Befund sogar dazu (Befund B18
    und B4 der Durchsicht 24.09.2026). Jetzt steht ein eigener Satz da, ohne
    Knopf zum Auflösen, gleich wie der Schritt eingestellt ist.
    """
    import app.core.geom.boolean as boolean_module

    body = _crossing_itself()
    assert body.is_watertight and body.component_count == 1, "sonst prüft der Test nichts"
    united: list[object] = []
    original = boolean_module.boolean

    def counted(*args: object, **kwargs: object) -> object:
        united.append(args)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(boolean_module, "boolean", counted)

    result = repair(body, self_intersections=resolve, inspect_intersections=True)

    assert united == [], "keine Vereinigung, die nicht tragen kann"
    assert not result.changed
    crossing = next(f for f in result.findings if f.code == "repair.self_crossing")
    assert str(crossing.message) == (
        "Die Oberfläche kreuzt sich selbst. Viele Slicer drucken solche Stellen trotzdem richtig."
    )
    assert [action.id for action in crossing.suggestions] == ["show_locations"]
    assert not {
        "repair.self_intersections_detected",
        "repair.self_intersections_unresolved",
    } & {finding.code for finding in result.findings}


def test_a_shell_known_to_cross_itself_is_not_searched_again_in_another_mesh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dieselbe Schale in einem neuen Netz: dasselbe „geht nicht", ohne zweite Suche.

    *Modell teilen* schneidet probeweise an mehreren Nähten, setzt Stifte und
    prüft die Einbaulage, und jede Boolesche Rechnung darin versucht zuerst,
    ineinandersteckende Teile zu vereinigen — an jeder Hälfte, und jede Hälfte
    ist ein neues Netz. Am Laptopständer aus ``F:\\3D Dateien`` kreuzt sich
    eine Schale selbst, und siebenmal lief die volle Suche über 172 000
    Dreiecke bis zum selben Nein (KUNDE-10, Durchsicht 0.5.1). Die Schalen,
    die der Schnitt nicht trifft, sind in jeder Hälfte dieselben Dreiecke — in
    anderer Reihenfolge und mit anderen Eckennummern.
    """
    import app.core.geom.repair as module
    from app.core.geom import intersections

    monkeypatch.setattr(module, "_SELF_CROSSING", {})
    searched: list[int] = []
    original = intersections.crossing_face_pairs

    def counted(vertices, faces, *args, **kwargs):  # type: ignore[no-untyped-def]
        searched.append(len(faces))
        return original(vertices, faces, *args, **kwargs)

    monkeypatch.setattr(intersections, "crossing_face_pairs", counted)
    itself = _crossing_itself().raw
    first = MeshData.of(
        trimesh.util.concatenate(
            [itself, _box(20.0, (100.0, 0.0, 0.0)), _box(20.0, (108.0, 5.0, 3.0))]
        )
    )
    # Dieselbe Schale rückwärts und mit vertauschten Ecken, daneben ein anderes Paar.
    turned = np.arange(len(itself.vertices))[::-1]
    renumbered = np.empty_like(turned)
    renumbered[turned] = np.arange(len(turned))
    again = trimesh.Trimesh(
        vertices=np.asarray(itself.vertices)[turned],
        faces=renumbered[np.asarray(itself.faces)[::-1]],
        process=False,
    )
    second = MeshData.of(
        trimesh.util.concatenate(
            [again, _box(20.0, (100.0, 0.0, 0.0)), _box(20.0, (106.0, 4.0, 2.0))]
        )
    )
    moved = itself.copy()
    moved.apply_translation((0.5, 0.0, 0.0))
    third = MeshData.of(
        trimesh.util.concatenate(
            [moved, _box(20.0, (100.0, 0.0, 0.0)), _box(20.0, (106.0, 4.0, 2.0))]
        )
    )

    one, worked_once = module.resolve_self_intersections(first)
    assert (one, worked_once) == (first, False), "eine Eigenkreuzung wird nicht vereinigt"
    assert searched == [first.triangle_count], "das erste Mal wird gesucht"

    two, worked_twice = module.resolve_self_intersections(second)
    assert (two, worked_twice) == (second, False)
    assert searched == [first.triangle_count], "dieselbe Schale wird nicht noch einmal gesucht"

    module.resolve_self_intersections(third)
    assert searched[-1] == third.triangle_count, "eine andere Schale wird gesucht"


def test_the_crossing_search_runs_once_per_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reparatur, Vorschau und Netzfehlerkarte fragen dasselbe Netz einmal.

    Die Suche kostet am Drachen 27 Sekunden, und jede Stelle rechnete sie für
    sich (Befund B11 der Durchsicht 24.09.2026).
    """
    from app.core.geom import intersections
    from app.core.geom.repair import crossings_of

    calls: list[int] = []
    original = intersections.crossing_face_pairs

    def counted(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(intersections, "crossing_face_pairs", counted)
    body, _welded = merge_vertices(raw("broken_selfint.stl"))

    first = crossings_of(body)
    second = crossings_of(body)
    faces = self_intersecting_faces(body)

    assert calls == [1]
    assert first is second
    assert faces == first.faces and faces, "und die Karte liest dieselbe Antwort"


def test_the_search_says_how_far_it_is() -> None:
    """Die Suche meldet Fortschritt, mit einem Satz, den der Kunde liest."""
    seen: list[tuple[float, str]] = []
    body, _welded = merge_vertices(raw("broken_selfint.stl"))

    repair(body, inspect_intersections=True, progress=lambda part, text: seen.append((part, text)))

    texts = {text for _part, text in seen}
    assert "Überschneidungen suchen" in texts
    assert all(0.0 <= part <= 1.0 for part, _text in seen)


def test_a_missing_face_with_holes_closes_as_one_face() -> None:
    """Fehlt einer Lochplatte die ganze Oberseite, kommt sie mit Löchern zurück.

    Der Füller schloss den Außenrand und jede Bohrungsmündung für sich: Die
    große Scheibe lag über den Mündungen, jede Mündung bekam einen eigenen
    Deckel — 570 Durchdringungen, und aus vier Durchgangsbohrungen wurden
    Sacklöcher (Befund B4 der Durchsicht 24.09.2026). Außenring und Lochringe
    derselben Ebene sind eine Fläche mit Löchern.
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    top = np.asarray(whole.raw.face_normals)[:, 2] > 0.99
    cut = MeshData.of(whole.raw.submesh([np.flatnonzero(~top)], append=True, repair=False))
    assert open_edge_count(cut) > 0, "sonst prüft der Test nichts"

    result = repair(cut)

    assert result.mesh.is_watertight
    assert self_intersecting_faces(result.mesh) == ()
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9), (
        "kein Deckel in den Bohrungen"
    )
    bores = [feature for feature in detect(result.mesh).values() if feature.kind == "hole"]
    assert len(bores) == 4
    assert all(bore.params.get("through") for bore in bores), "Durchgänge bleiben Durchgänge"


def _loaded(document: Document, name: str, **load: object):
    """Ein Projekt mit der Korpusdatei ``name`` als Quelle und ihr Verlauf."""
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{name}", sha256="")
    project.sources["src_1"] = (MESHES / name).read_bytes()
    history = History(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm", **load})],
    )
    return project, history


def test_a_body_closed_later_is_no_longer_called_open(document: Document, profile: Profile) -> None:
    """„Das Modell ist nicht geschlossen" steht im Präsens — am Endstand gefragt.

    Welcher Schritt schließt, weiß keine Tabelle: hier *Offene Fläche
    schließen* nach einem Laden ohne „Offene Stellen schließen". Bis zur
    Durchsicht (Befund B6, 24.09.2026) stand der Satz des Ladeschritts
    weiter im Bericht, über einem geschlossenen Körper.
    """
    project, history = _loaded(document, "broken_open.stl", mend=False)
    first = evaluate(document, profile, sources=ProjectSources(project))
    assert "ingest.not_watertight" in {f.code for f in first.scene.report.findings}

    history.apply(_("Dicke geben"), [OperationDraft(op="thicken", inputs=("obj_1",))])
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    body = result.scene.objects["obj_1"].mesh
    assert body is not None and body.is_watertight
    assert "ingest.not_watertight" not in {f.code for f in result.scene.report.findings}


def test_a_body_made_one_piece_is_no_longer_called_several(
    document: Document, profile: Profile
) -> None:
    """„Besteht aus mehreren Teilen" fällt, sobald der Körper eines ist."""
    project, history = _loaded(document, "two_components.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    assert "ingest.multiple_components" in {f.code for f in first.scene.report.findings}

    history.apply(
        _("Reparieren"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"small_components": True})],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    codes = {f.code for f in result.scene.report.findings}
    assert "ingest.multiple_components" not in codes
    assert "ingest.small_components" not in codes


def test_a_part_count_a_later_step_changed_is_no_longer_said(
    document: Document, profile: Profile
) -> None:
    """„Besteht aus 69 Teilen, von denen manche ineinanderstecken" über einem Körper mit vier.

    Der Satz des Ladeschritts nennt die Teilezahl, die er gemessen hat. Nach
    *Überschneidungen auflösen* am Bohrmaschinenhalter stand er weiter im
    Bericht, über „Überschneidungen wurden aufgelöst." und unter „4 Teile" im
    Kopf — der Kunde wusste nicht, ob das Auflösen gewirkt hatte (KUNDE-13).
    Aus einem Stück ist der Körper danach nicht, der Filter für „aus
    mehreren Teilen" griff also nicht. Gefragt wird dieselbe Sache: am
    Endstand, ob die genannte Zahl noch stimmt. Und *In Einzelteile zerlegen*
    am alten Satz plante 69 Ausgänge für einen Körper mit vier.
    """
    project, history = _loaded(document, "crossing_and_apart.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    said = next(f for f in first.scene.report.findings if f.code == "ingest.multiple_components")
    assert said.values["components"] == 3
    assert "resolve_intersections" in {action.id for action in said.suggestions}

    history.apply(
        _("Überschneidungen auflösen"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"self_intersections": True})],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    body = result.scene.objects["obj_1"].mesh
    assert body is not None and body.component_count == 2
    assert body.volume == pytest.approx(2.0 * 8000.0 - 12.0**3 + 8000.0, rel=1e-9)
    codes = [f.code for f in result.scene.report.findings]
    assert "repair.self_intersections" in codes, "der Schritt sagt, was er getan hat"
    assert "ingest.multiple_components" not in codes, "drei Teile gibt es nicht mehr"


def test_the_count_of_tiny_parts_is_taken_at_the_end(document: Document, profile: Profile) -> None:
    """„Es gibt sehr kleine Einzelteile" zählt am Endstand, nicht beim Einlesen (KUNDE-13).

    Am Bohrmaschinenhalter stand nach *Überschneidungen auflösen* weiter
    „Anzahl 57" unter „4 Teile" im Kopf: Die Buchstaben, die in der Wand
    steckten, waren im Körper aufgegangen, und der Satz des Ladeschritts zählte
    sie noch. Hier zwei Würfel ineinander, ein Krümel halb in der Wand des
    ersten und einer daneben: vier Teile, zwei davon klein; nach dem Auflösen
    zwei Teile, einer klein.
    """
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((8.0, 8.0, 8.0))
    in_the_wall = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    in_the_wall.apply_translation((-10.0, 0.0, 0.0))
    beside = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    beside.apply_translation((60.0, 0.0, 0.0))
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/crumbs.stl", sha256=""
    )
    project.sources["src_1"] = trimesh.util.concatenate(
        [first, second, in_the_wall, beside]
    ).export(file_type="stl")
    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    loaded = evaluate(document, profile, sources=ProjectSources(project))
    tiny = next(f for f in loaded.scene.report.findings if f.code == "ingest.small_components")
    assert tiny.values["count"] == 2, "die Voraussetzung: zwei Krümel"

    history.apply(
        _("Überschneidungen auflösen"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"self_intersections": True})],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.scene.objects["obj_1"].mesh.component_count == 2
    counts = [
        f.values["count"]
        for f in result.scene.report.findings
        if f.code == "ingest.small_components"
    ]
    assert counts == [1], "einer ist im Würfel aufgegangen, einer steht daneben"


def test_a_later_repair_settles_the_earlier_crossing_finding(
    document: Document, profile: Profile
) -> None:
    """Der spätere Satz über die Überschneidungen ersetzt den früheren."""
    project, history = _loaded(document, "broken_selfint.stl")
    history.apply(
        _("Reparieren"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"self_intersections": False})],
    )
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    result = evaluate(document, profile, sources=ProjectSources(project))

    codes = [f.code for f in result.scene.report.findings]
    assert "repair.self_intersections" in codes
    assert "repair.self_intersections_detected" not in codes
    assert "ingest.multiple_components" not in codes, "die Vereinigung macht ein Teil daraus"


def _without_faces(mesh: MeshData, faces: np.ndarray) -> MeshData:
    keep = np.setdiff1d(np.arange(mesh.triangle_count), faces)
    return MeshData.of(mesh.raw.submesh([keep], append=True, repair=False))


def test_a_missing_bore_wall_comes_back_as_a_wall() -> None:
    """Fehlt die Wand einer Bohrung, wird sie ergänzt — die Bohrung bleibt offen.

    Beide Mündungen zu deckeln machte die Bohrung zu: 4 → 3 Bohrungen und
    π·2,6²·8 mm³ Material mehr (Befund B4 der Durchsicht 24.09.2026). Die zwei
    Ringe sind koaxial, gleich geteilt und liegen je in einer ebenen Fläche;
    dazwischen fehlt ein Mantel, und genau der kommt zurück.
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    bores = sorted(
        (feature for feature in detect(whole).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )
    broken = _without_faces(whole, np.asarray(bores[0].face_indices))

    result = repair(broken)

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    assert self_intersecting_faces(result.mesh) == ()
    again = [feature for feature in detect(result.mesh).values() if feature.kind == "hole"]
    assert len(again) == 4 and all(bore.params.get("through") for bore in again)


def test_a_missing_countersink_comes_back_as_a_cone() -> None:
    """Fehlt der Kegel einer Senkung, kommt ein Kegelstumpf zurück, kein Deckel."""
    from app.core.ingest.loader import normalise
    from app.core.perceive.features import detect

    whole = normalise(raw("plate_countersunk.stl"), "mm").mesh
    cone = next(feature for feature in detect(whole).values() if feature.kind == "cone")
    broken = _without_faces(whole, np.asarray(cone.face_indices))

    result = repair(broken)

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    kinds = sorted(
        (feature.kind, feature.params.get("through"))
        for feature in detect(result.mesh).values()
        if feature.kind in ("hole", "cone")
    )
    assert kinds == [("cone", None), ("hole", True)]


@pytest.mark.parametrize("case", ["tube", "poles"])
def test_rings_joined_by_existing_walls_are_capped_not_tunnelled(case: str) -> None:
    """Die Gegenprobe: Wo die vorhandenen Wände die Ringe schon verbinden, kein Band.

    Ein Rohr ohne Deckel und eine Kugel ohne Pole tragen ebenfalls zwei
    koaxiale, gleich geteilte Ringe. Ein Band dazwischen wäre ein Tunnel —
    ihre Nachbarflächen liegen auf der Seite zum anderen Ring hin.
    """
    if case == "tube":
        body = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=48)
        gone = np.flatnonzero(np.abs(np.asarray(body.face_normals)[:, 2]) > 0.5)
    else:
        body = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
        gone = np.flatnonzero(np.abs(np.asarray(body.triangles_center)[:, 2]) > 9.0)
    whole = MeshData.of(body)

    result = repair(_without_faces(whole, gone))

    assert result.mesh.is_watertight
    assert result.mesh.component_count == 1
    # Mit Deckeln bleibt das Volumen beim Körper; ein Tunnel nähme ihm den Kern.
    assert result.mesh.volume == pytest.approx(whole.volume, rel=0.02)


def _peak_bytes[T](work: Callable[[], T]) -> tuple[T, int]:
    """Das Ergebnis von ``work()`` und der höchste Speicherstand dabei (``tracemalloc``)."""
    import tracemalloc

    tracemalloc.start()
    try:
        outcome = work()
        return outcome, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_a_fine_open_tube_is_capped_without_pairing_its_rings_corner_by_corner() -> None:
    """Ein fein geteiltes Rohr ohne Deckel wird gedeckelt, ohne Ecke gegen Ecke zu halten.

    ``_band_between`` verglich jede Ecke des einen Rings mit jeder des anderen
    und fragte erst danach, ob die vorhandenen Wände die Ringe schon verbinden
    (Review 25.09.2026): Am Rohr mit 4 096 Teilungen kostete die Paarung 3,0
    von 3,8 s und 411 MB — für einen Mantel, den die Seitenprobe danach
    verwarf. Mit 2 048 Teilungen waren es 105 MB.
    """
    tube = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=2048)
    tube.update_faces(np.abs(np.asarray(tube.face_normals)[:, 2]) < 0.5)
    tube.remove_unreferenced_vertices()
    rim = np.asarray(tube.vertices)[np.asarray(tube.vertices)[:, 2] < 0.0][:, :2]
    order = np.argsort(np.arctan2(rim[:, 1], rim[:, 0]))
    x, y = rim[order, 0], rim[order, 1]
    # Der Deckel ist das Vieleck der Randecken: Fläche nach der Gaußschen Formel.
    area = abs(float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))) / 2.0

    result, peak = _peak_bytes(lambda: repair(MeshData.of(tube)))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(area * 30.0, rel=1e-9), "Deckel, kein Mantel"
    assert peak < 32_000_000, f"{peak / 1e6:.0f} MB — kein Feld aus Ecken mal Ecken"


def test_a_band_between_two_fine_rings_needs_no_field_of_every_corner_pair() -> None:
    """Auch der Mantel, der entsteht, paart die Ecken ohne Feld aus Ecken mal Ecken.

    Zwei koaxiale Ringe zu je 2 048 Ecken, der zweite gegenläufig, die
    Nachbarflächen je auf der abgewandten Seite: Das ist die fehlende Wand
    einer fein geteilten Bohrung. Die Paarung hielt dafür drei Felder zu
    2 048 · 2 048 Zahlen, zusammen 100 MB (Review 25.09.2026).
    """
    from app.core.geom import lathe
    from app.core.geom.repair import _band_between

    count = 2048
    circle = lathe.circle_points(count, radius=5.0)
    lower = np.column_stack((circle, np.zeros(count)))
    upper = np.column_stack((circle, np.full(count, 10.0)))
    points = np.vstack((lower, upper))
    first = list(range(count))
    # Gegenläufig: dieselbe Richtung um die Achse, in umgekehrter Folge.
    second = [count + (-index) % count for index in range(count)]
    owner_of = {
        (
            min(ring[index], ring[(index + 1) % count]),
            max(ring[index], ring[(index + 1) % count]),
        ): (face)
        for face, ring in enumerate((first, second))
        for index in range(count)
    }
    # Die Nachbarn liegen unter dem unteren und über dem oberen Ring.
    centroids = np.asarray([[0.0, 0.0, -1.0], [0.0, 0.0, 11.0]])

    band, peak = _peak_bytes(
        lambda: _band_between(points, first, second, 1e-5, owner_of, centroids)
    )

    assert band is not None and len(band) == 2 * count, "der Mantel entsteht"
    assert peak < 16_000_000, f"{peak / 1e6:.0f} MB — kein Feld aus Ecken mal Ecken"


@pytest.mark.parametrize("pair", [(88, 64), (96, 72), (97, 74)])
def test_a_small_hole_in_a_rounding_gets_its_own_triangles_back(pair: tuple[int, int]) -> None:
    """Zwei fehlende Nachbardreiecke einer Verrundung kommen als dieselben zwei zurück.

    Das erste gültige Ohr legte die Diagonale quer zum Bogen; die Rundung las
    danach einen anderen Radius (am Rucksackhalter R 2,773 statt 3, Befund B3
    der Erkennungsdurchsicht, 24.09.2026). Die Füllung mit dem kleinsten
    größten Knick trifft die ursprüngliche Diagonale.
    """
    from app.core.ingest.loader import normalise
    from app.core.perceive.features import detect

    whole = normalise(raw("block_with_rounded_edge.stl"), "mm").mesh
    rounding = next(feature for feature in detect(whole).values() if feature.kind == "fillet")
    assert set(pair) <= set(rounding.face_indices)
    broken = _without_faces(whole, np.asarray(pair))

    result = repair(broken)

    def corners(mesh: MeshData, rows: np.ndarray) -> list[tuple[tuple[float, ...], ...]]:
        points = np.asarray(mesh.raw.vertices)
        return sorted(
            tuple(sorted(tuple(np.round(points[vertex], 6).tolist()) for vertex in row))
            for row in rows
        )

    added = np.asarray(result.mesh.raw.faces)[broken.triangle_count :]
    assert corners(result.mesh, added) == corners(whole, np.asarray(whole.raw.faces)[list(pair)])
    healed = next(feature for feature in detect(result.mesh).values() if feature.kind == "fillet")
    assert healed.params["radius"] == pytest.approx(rounding.params["radius"], rel=1e-9)


def test_two_missing_triangles_across_a_sharp_edge_bring_the_edge_back() -> None:
    """Fehlen die zwei Dreiecke an einer Würfelkante, kommt die Kante zurück, keine Fase.

    Das erste gültige Ohr legte die Diagonale quer über die Kante und nahm
    dem Würfel 21 mm³ (Durchsicht 24.09.2026).
    """
    cube = _box(20.0).subdivide().subdivide()
    pair = np.asarray(cube.face_adjacency)[
        int(np.flatnonzero(np.asarray(cube.face_adjacency_angles) > 1.5)[0])
    ]
    whole = MeshData.of(cube)

    result = repair(_without_faces(whole, pair))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(8000.0, rel=1e-12)


def test_a_quarter_of_a_bore_wall_comes_back_as_wall() -> None:
    """Fehlt ein Viertel der Bohrungswand, bleibt es eine Bohrung — kein Deckel quer hindurch.

    Der Ring hat 26 Ecken; mit der früheren Grenze von sechzehn für die glatte
    Füllung schloss das Ohrenschneiden ihn flach, und aus vier Bohrungen
    wurden drei und eine gerundete Seite (Befund B4 der Erkennungsdurchsicht,
    24.09.2026).
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    bore = min(
        (feature for feature in detect(whole).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )
    wall = np.asarray(bore.face_indices)
    offset = np.asarray(whole.raw.triangles_center)[wall] - np.asarray(bore.params["centre"])
    # Das Viertel zwischen minus x und minus y, ohne Winkelfunktion abgegrenzt.
    quarter = wall[(offset[:, 0] < 0.0) & (offset[:, 1] < 0.0)]
    assert len(quarter) == len(wall) // 4

    result = repair(_without_faces(whole, quarter))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    assert sum(1 for feature in detect(result.mesh).values() if feature.kind == "hole") == 4


def _part_of_the_wall(mesh: MeshData, feature, part: str) -> np.ndarray:
    """Die Dreiecke eines Stücks der Wand um die Achse, ohne Winkelfunktion abgegrenzt."""
    wall = np.asarray(feature.face_indices)
    offset = np.asarray(mesh.raw.triangles_center)[wall] - np.asarray(feature.params["centre"])
    if part == "quarter":
        return wall[(offset[:, 0] < 0.0) & (offset[:, 1] < 0.0)]
    if part == "half":
        return wall[offset[:, 0] < 0.0]
    return wall[~((offset[:, 0] >= 0.0) & (offset[:, 1] >= 0.0))]


@pytest.mark.parametrize("part", ["half", "three_quarters"])
def test_a_half_or_three_quarter_bore_wall_comes_back_as_wall(part: str) -> None:
    """Fehlt die halbe Wand oder drei Viertel, kommt sie als Wand zurück (RM-240).

    Der Rand ist ein Ring aus zwei Bögen und zwei Mantellinien. Die flachste,
    kleinste Schließung sind zwei Deckel über den Bögen — aus der halben Wand
    wurde so eine gerundete Seite, die Platte hatte drei Bohrungen und 25,9 mm³
    zu viel, die Dreiviertelwand blieb ganz offen. Die Mündungen der Restwand
    liegen in zwei parallelen Ebenen, und dazwischen fehlt ein Mantel.
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    bore = min(
        (feature for feature in detect(whole).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )

    result = repair(_without_faces(whole, _part_of_the_wall(whole, bore, part)))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    assert self_intersecting_faces(result.mesh) == ()
    bores = [feature for feature in detect(result.mesh).values() if feature.kind == "hole"]
    assert len(bores) == 4 and all(bore.params.get("through") for bore in bores)


@pytest.mark.parametrize("part", ["quarter", "half", "three_quarters"])
def test_a_part_of_a_countersink_comes_back_as_a_cone(part: str) -> None:
    """Dasselbe am Kegel einer Senkung: Er kommt als Kegel zurück, nicht als Stufe (RM-240).

    Und Teilung für Teilung: Am Viertel zog die glatteste Füllung schiefe
    Sprossen über mehrere Teilungen und ließ 0,105 mm³ stehen.
    """
    from app.core.ingest.loader import normalise
    from app.core.perceive.features import detect

    whole = normalise(raw("plate_countersunk.stl"), "mm").mesh
    cone = next(feature for feature in detect(whole).values() if feature.kind == "cone")

    result = repair(_without_faces(whole, _part_of_the_wall(whole, cone, part)))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(whole.volume, rel=1e-9)
    kinds = sorted(
        (feature.kind, feature.params.get("through"))
        for feature in detect(result.mesh).values()
        if feature.kind in ("hole", "cone")
    )
    assert kinds == [("cone", None), ("hole", True)]


def test_a_straight_wall_with_a_missing_strip_stays_flat() -> None:
    """Die Gegenprobe: Zwischen zwei geraden Mündungen ist der Mantel eben.

    Einem viermal unterteilten Würfel fehlt ein senkrechter Streifen seiner
    Vorderseite; der Rand liegt oben und unten auf den Kanten des Würfels. Was
    zurückkommt, liegt ganz in der Ebene der Vorderseite.
    """
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    for _round in range(2):
        box = box.subdivide()
    body = MeshData.of(box)
    centres = np.asarray(box.triangles_center)
    front = np.asarray(box.face_normals)[:, 1] < -0.9
    strip = np.flatnonzero(front & (np.abs(centres[:, 0]) < 1.5))
    assert len(strip), "die Voraussetzung: ein Streifen der Vorderseite"

    result = repair(_without_faces(body, strip))

    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(1000.0, rel=1e-9)
    added = np.asarray(result.mesh.raw.triangles_center)[len(box.faces) - len(strip) :]
    assert np.allclose(added[:, 1], -5.0), "jedes neue Dreieck liegt in der Vorderseite"


def test_splinters_that_go_leave_no_sheet_and_no_hidden_hole() -> None:
    """Was als Splitter geht, zählt nicht mehr als Fläche ohne Dicke (Review R5).

    Die Bilanz der flachen Ringe stammte aus dem Netz vor dem Entfernen: Ein
    geschlossener Würfel mit zwanzig losen Dreiecken hieß danach „Fläche ohne
    Dicke", und neben einem offenen Fenster wurden dessen Ränder abgezogen.
    """
    pieces = [_box(20.0)]
    for index in range(20):
        at = np.array([40.0 + 2.0 * index, 0.0, 0.0])
        pieces.append(
            trimesh.Trimesh(
                vertices=[at, at + np.array([1.5, 0.0, 0.0]), at + np.array([0.0, 1.5, 0.0])],
                faces=[[0, 1, 2]],
                process=False,
            )
        )
    result = repair(MeshData.of(trimesh.util.concatenate(pieces)))

    codes = {finding.code for finding in result.findings}
    assert "repair.splinters_removed" in codes
    assert "repair.no_thickness" not in codes
    assert result.mesh.is_watertight


def test_overlaps_in_a_body_turned_inside_out_are_still_named() -> None:
    """Gefundene Überschneidungen bekommen eine Zeile, auch wenn der Körper verkehrt steht.

    Verkehrt hieß „ohne Volumen", und dafür gab es keinen Befund — die
    Operation sagte danach „nichts zu reparieren" (Review R21, 24.09.2026).
    """
    body = trimesh.util.concatenate([_box(20.0), _box(20.0, at=(10.0, 5.0, 3.0))])
    body.invert()

    for resolve in (True, False):
        # Wie die Operation: Sie sucht bei jedem ausdrücklichen Reparieren.
        result = repair(
            MeshData.of(body),
            normals=False,
            self_intersections=resolve,
            inspect_intersections=True,
        )
        codes = {finding.code for finding in result.findings}
        assert codes & {"repair.self_intersections_skipped", "repair.self_intersections_detected"}


def test_outsides_facing_each_other_fall_once_the_body_is_wound_evenly() -> None:
    """„An N Kanten zeigen die Außenseiten gegeneinander" gilt nur, solange es stimmt.

    Heilt ein späterer Schritt die Wicklung, stand der Satz im Präsens weiter
    da (Review R19, 24.09.2026) — derselbe Endstandfilter wie für Dichtheit
    und Teilezahl.
    """
    from app.core.scene.evaluate import _without_outdated
    from app.core.types import Finding, Scene, SceneObject

    crossed = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    faces = np.asarray(crossed.faces).copy()
    faces[0] = faces[0][::-1]
    crossed = trimesh.Trimesh(vertices=crossed.vertices, faces=faces, process=False)
    said = Finding(
        code="repair.normals_inconsistent", severity="warning", message="", object_id="obj_1"
    )

    for body, stays in ((MeshData.of(_box(20.0)), False), (MeshData.of(crossed), True)):
        scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Würfel", mesh=body)})
        assert bool(_without_outdated([said], scene)) is stays


@pytest.mark.parametrize("case", ["open", "large", "plain"])
def test_the_search_goes_only_as_far_as_it_can_help(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offen oder über der Kartengrenze sucht die Reparatur mit dem Sockelbudget.

    Am offenen Netz löst sie ohnehin nichts auf, und über der Grenze wuchs das
    Budget mit dem Netz — am Drachen 70 s für „nichts zu tun" (Review R12,
    24.09.2026). Ein gewöhnliches Teil behält das mitwachsende Budget.
    """
    import app.core.geom.repair as module
    import app.core.perceive.maps as maps

    asked: list[int | None] = []
    real = module.crossings_of

    def recorded(mesh, cancelled=None, progress=None, *, budget=None):  # type: ignore[no-untyped-def]
        asked.append(budget)
        return real(mesh, cancelled, progress, budget=budget)

    monkeypatch.setattr(module, "crossings_of", recorded)
    body = _box(20.0).subdivide()
    if case == "open":
        body.update_faces(np.arange(len(body.faces)) != 0)
    if case == "large":
        monkeypatch.setattr(maps, "MAP_LIMIT_TRIANGLES", 10)

    repair(MeshData.of(body), holes=False, self_intersections=True)

    expected = None if case == "plain" else module.MAX_INTERSECTION_PAIRS
    assert asked == [expected]


def test_resolving_above_the_map_limit_searches_the_body_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Über der Kartengrenze sucht auch das Auflösen nur mit dem Sockelbudget.

    Die Diagnose hält sich dort an ``MAX_INTERSECTION_PAIRS`` (Review R12).
    ``resolve_self_intersections`` fragte die Suche danach aber mit dem
    mitwachsenden Budget noch einmal — die unvollständige Antwort im Cache galt
    für das größere Budget nicht —, und über der Grenze lief damit doch die
    volle Suche, die der Sockel sparen sollte (Review 25.09.2026: an zwei
    ineinandergesteckten Würfeln ein Lauf mit 1 000 Paaren, danach einer mit
    4 608). Aufgelöst wird, was gefunden war; der Hinweis daneben sagt, dass
    die Suche nicht alles sah.
    """
    import app.core.geom.repair as module
    import app.core.perceive.maps as maps
    from app.core.geom import intersections

    body = MeshData.of(
        trimesh.util.concatenate(
            [
                _box(20.0).subdivide().subdivide(),
                _box(20.0, (8.0, 5.0, 3.0)).subdivide().subdivide(),
            ]
        )
    )
    whole = (len(body.raw.vertices), body.triangle_count)
    searched: list[int | None] = []
    original = intersections.crossing_face_pairs

    def counted(vertices, faces, *args, **kwargs):  # type: ignore[no-untyped-def]
        if (len(vertices), len(faces)) == whole:
            searched.append(kwargs.get("max_pairs"))
        return original(vertices, faces, *args, **kwargs)

    monkeypatch.setattr(intersections, "crossing_face_pairs", counted)
    monkeypatch.setattr(maps, "MAP_LIMIT_TRIANGLES", 10)
    # Ein Sockel, der Schnitte findet, aber nicht alle (148 Paare schneiden,
    # bei 1 000 geprüften sind es 41).
    monkeypatch.setattr(module, "MAX_INTERSECTION_PAIRS", 1_000)

    result = repair(body, self_intersections=True)

    assert searched == [1_000], "der Körper wird einmal durchsucht, mit dem Sockel"
    codes = [finding.code for finding in result.findings]
    assert "repair.self_intersections" in codes, "aufgelöst ist, was gefunden war"
    assert "repair.self_intersections_incomplete" in codes
    # Zwei Würfel von 20 mm, um (8, 5, 3) versetzt: gemeinsam 12 · 15 · 17 mm³.
    assert result.mesh.volume == pytest.approx(2 * 8000.0 - 12.0 * 15.0 * 17.0, rel=1e-9)


def test_the_bridge_to_a_hole_hangs_on_no_platform_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Welche Randecke ein Loch als Brücke bekommt, entscheidet keine Bibliotheksfunktion.

    ``_bridged_holes`` maß die Abstände zum Anker über ``np.hypot``, und das
    rundet je Plattform verschieden (RM-187; ``test_platform_identity`` führt
    es unter den Rechnungen, die eine andere Maschine anders runden darf).
    Review R11 hatte den Ersatz verlangt; ``_band_between`` bekam ihn,
    ``_bridged_holes`` nicht (Review 25.09.2026). Zwei Randecken, deren
    Abstand zum Anker eine Stelle auseinanderliegt: Rundet ``hypot`` die
    nähere eine Stelle auf, bekam das Loch die andere Brücke und die Fläche
    andere Dreiecke. Der Fingerabdruck der Plattformprobe sah das nicht — er
    liest die Ecken, und eine Füllung legt keine neuen an.
    """
    from app.core.geom.repair import _bridged_holes

    points = np.asarray(
        [
            [-10.0, -10.0, 0.0],
            [10.0, -10.0, 0.0],
            [10.0, 10.0, 0.0],
            # hypot(10, 3,000000000000005) liegt genau eine Stelle über hypot(10, 3).
            [3.000000000000005, 10.0, 0.0],
            [-3.0, 10.0, 0.0],
            [-10.0, 10.0, 0.0],
            [0.0, 0.0, 0.0],
            [1.0, -2.0, 0.0],
            [-1.0, -2.0, 0.0],
        ]
    )
    outer, hole, normal = [0, 1, 2, 3, 4, 5], [6, 7, 8], np.array([0.0, 0.0, 1.0])
    quiet = _bridged_holes(points, outer, [hole], normal)
    assert quiet is not None
    real = np.hypot

    def rounded_up(*args, **kwargs):  # type: ignore[no-untyped-def]
        """``hypot`` einer Maschine, die den kleinsten Abstand eine Stelle höher rundet."""
        result = np.array(real(*args, **kwargs), dtype=np.float64)
        if result.size:
            nearest = np.unravel_index(int(np.argmin(result)), result.shape)
            result[nearest] = np.nextafter(result[nearest], np.inf)
        return result

    monkeypatch.setattr(np, "hypot", rounded_up)

    assert _bridged_holes(points, outer, [hole], normal) == quiet


def test_a_band_that_would_run_through_another_part_is_not_built() -> None:
    """Steht in der wandlosen Bohrung ein fremder Stift, gibt es kein Band quer hindurch.

    Die Sperre ``_band_crosses`` hatte keine Gegenprobe; alle Band- und
    Fülltests blieben grün, als sie nie sperrte (Review R22, 24.09.2026).
    """
    from app.core.perceive.features import detect

    whole, _welded = merge_vertices(raw("plate_holes.stl"))
    bore = min(
        (feature for feature in detect(whole).values() if feature.kind == "hole"),
        key=lambda feature: tuple(feature.params["centre"]),
    )
    broken = _without_faces(whole, np.asarray(bore.face_indices))
    centre = np.asarray(bore.params["centre"], dtype=float)
    radius = float(bore.params["diameter"]) / 2.0
    # Ein Stab quer durch die Bohrung, länger als ihr Durchmesser: Er ragt
    # durch den Mantel, den ein Band dort legen würde.
    rod = trimesh.creation.box(extents=(2.4 * radius, 0.6, 0.6))
    rod.apply_translation(centre)
    both = MeshData.of(trimesh.util.concatenate([broken.raw, rod]))

    result = repair(both)

    assert self_intersecting_faces(result.mesh) == (), "kein Band durch den Stab"


def test_leaving_the_wide_opening_open_still_closes_the_small_holes() -> None:
    """*Offen lassen* gilt der großen Öffnung, nicht jedem Loch (RM-241).

    Bis dahin schaltete der Knopf das Schließen ganz ab: Mit der großen
    Öffnung blieben auch die kleinen Löcher, Nähte und überzähligen Flächen
    offen. ``partially_open.stl`` hat beides — ein kleines Loch und eine
    fehlende Wand über ``FILL_LOOP_SHARE``.
    """
    body, _welded = merge_vertices(raw("partially_open.stl"))

    closed = repair(body)
    assert closed.mesh.is_watertight, "Gegenprobe: mit Vorgabe geht alles zu"
    assert "repair.wide_hole_filled" in {finding.code for finding in closed.findings}

    kept = repair(body, wide_holes=False)

    assert not kept.mesh.is_watertight, "die große Öffnung bleibt offen"
    codes = {finding.code for finding in kept.findings}
    assert "repair.wide_hole_filled" not in codes
    assert "repair.still_open" not in codes, "offen auf Wunsch ist kein Fehlschlag"
    filled = next(finding for finding in kept.findings if finding.code == "repair.holes_filled")
    assert filled.values["holes"] == 1, "das kleine Loch geht trotzdem zu"
    left = next(finding for finding in kept.findings if finding.code == "repair.wide_hole_kept")
    assert left.severity == "warning"
    assert left.values["openings"] == 1
    assert [action.id for action in left.suggestions] == ["give_thickness", "show_locations"]
    assert left.location is not None
    low, high = body.bounds.minimum, body.bounds.maximum
    assert all(low[axis] - 1e-6 <= left.location[axis] <= high[axis] + 1e-6 for axis in range(3))


def test_a_repair_says_nothing_about_lost_names_nobody_uses(
    document: Document, profile: Profile
) -> None:
    """Nach *Reparieren* steht kein Satz über verlorene Formdetails (Bedienweg C5).

    Zwei ineinandergeschobene Würfel: Das Auflösen der Überschneidung gibt den
    Flächen neue Grenzen, und an einem heruntergeladenen Netz hat sie niemand
    benannt. „Formdetails sind nicht mehr wiederzuerkennen" klang, als sei
    etwas kaputtgegangen. Ein Verlust mit Verweis bleibt ein eigener Befund.
    """
    project, history = _loaded(document, "broken_selfint.stl")
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    repaired = next(step.id for step in document.ops if step.op == "repair")
    codes = {finding.code for finding in result.scene.report.findings}
    assert "repair.self_intersections" in codes, "sonst prüft der Test nichts"
    lost = [
        finding
        for finding in result.scene.report.findings
        if finding.code in {"perceive.orphaned", "perceive.mended"} and finding.op_id == repaired
    ]
    assert not lost, [dict(finding.values) for finding in lost]


def _edge_count_cases() -> dict[str, trimesh.Trimesh]:
    """Die Grenzfälle der Kantenzählung: dicht, offen, verkehrt, verzweigt, Suppe."""
    closed = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    opened = closed.copy()
    opened.update_faces(np.arange(1, len(opened.faces)))
    flipped = closed.copy()
    faces = np.asarray(flipped.faces).copy()
    faces[0] = faces[0][::-1]
    flipped = trimesh.Trimesh(vertices=flipped.vertices, faces=faces, process=False)
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((10.0, 10.0, 0.0))
    branching = trimesh.util.concatenate([closed, right])
    branching.merge_vertices()
    soup = trimesh.Trimesh(
        vertices=np.asarray(closed.triangles).reshape(-1, 3),
        faces=np.arange(3 * len(closed.faces)).reshape(-1, 3),
        process=False,
    )
    plate = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl").raw
    welded = plate.copy()
    welded.merge_vertices()
    return {
        "dicht": closed,
        "offen": opened,
        "verkehrt": flipped,
        "verzweigt": branching,
        "Suppe": soup,
        "Platte roh": plate,
        "Platte verschweißt": welded,
    }


@pytest.mark.parametrize("case", list(_edge_count_cases()))
def test_the_edge_count_answers_like_trimesh(case: str) -> None:
    """Dichtheit, Umlaufsinn und Nachbarschaft aus einer Kantenzählung (RM-224).

    ``mesh.edge_table`` legt ``is_watertight`` und ``is_winding_consistent`` in
    trimeshs Cache und gibt ``face_components`` die Nachbarschaft — beides
    muss trimeshs Antwort sein, sonst sagt der Import „geschlossen" über ein
    offenes Netz. Am Korpus ``F:\\3D Dateien`` gegengeprüft (970 Vergleiche);
    hier die Grenzfälle, an denen die Zählung kippen könnte.
    """
    from app.core.geom.mesh import edge_table

    body = _edge_count_cases()[case]
    expected = trimesh.graph.is_watertight(edges=body.edges, edges_sorted=body.edges_sorted)
    pairs = {tuple(pair) for pair in np.asarray(body.face_adjacency, dtype=np.int64).tolist()}

    fresh = body.copy()
    table = edge_table(fresh)

    assert (fresh.is_watertight, fresh.is_winding_consistent) == (
        bool(expected[0]),
        bool(expected[1]),
    )
    assert {tuple(pair) for pair in table.face_pairs().tolist()} == pairs


def _is_the_counted_edge_table(derived_mesh: trimesh.Trimesh) -> None:
    """Die abgelegte Zählung ist die, die eine frische Zählung desselben Netzes ergäbe."""
    from app.core.geom import mesh as mesh_module

    assert mesh_module._EDGE_TABLE_KEY in derived_mesh._cache, "abgeleitet, nicht nachgezählt"
    derived = mesh_module.edge_table(derived_mesh)
    answers = (derived_mesh.is_watertight, derived_mesh.is_winding_consistent)
    counted_mesh = trimesh.Trimesh(
        vertices=np.asarray(derived_mesh.vertices),
        faces=np.asarray(derived_mesh.faces),
        process=False,
    )
    counted = mesh_module.edge_table(counted_mesh)
    np.testing.assert_array_equal(derived.unique, counted.unique)
    np.testing.assert_array_equal(derived.inverse, counted.inverse)
    np.testing.assert_array_equal(derived.counts, counted.counts)
    assert answers == (counted_mesh.is_watertight, counted_mesh.is_winding_consistent)


@pytest.mark.parametrize("case", list(_edge_count_cases()))
def test_a_derived_edge_count_is_the_counted_one(case: str) -> None:
    """Die Reparatur leitet die Kantenzählung ab, statt sie neu zu sortieren (RM-224).

    ``mesh.without_faces`` zieht gestrichene Dreiecke ab und nummeriert die
    Ecken neu, ``mesh.carry_appended_edges`` fügt angehängte Dreiecke samt
    neuer Ecke ein. Beides muss die Tabelle einer frischen Zählung ergeben —
    Kanten, Zeilen, Zähler — und dieselbe Dichtheit und denselben Umlaufsinn;
    sonst hieße ein offenes Netz nach dem Auflösen einer Verzweigung „dicht".
    Gestrichen wird jedes dritte Dreieck, so verlieren Ecken ihr letztes;
    angehängt werden Kopien mit Gegenlauf (Kanten mit drei und vier Dreiecken)
    und ein Dreieck an einer neuen Mitte.
    """
    from app.core.geom.mesh import carry_appended_edges, edge_table, without_faces

    body = _edge_count_cases()[case]
    edge_table(body)
    keep = np.ones(len(body.faces), dtype=bool)
    keep[::3] = False

    trimmed = without_faces(body, keep)

    assert len(trimmed.faces) == int(keep.sum())
    _is_the_counted_edge_table(trimmed)

    points = np.asarray(trimmed.vertices)
    rows = np.asarray(trimmed.faces, dtype=np.int64)[:4]
    extended = trimesh.Trimesh(
        vertices=np.vstack([points, points.mean(axis=0)]),
        faces=np.vstack(
            [trimmed.faces, rows[:, ::-1], rows[:2], [[rows[0, 0], rows[0, 1], len(points)]]]
        ),
        process=False,
    )

    carry_appended_edges(trimmed, extended)

    _is_the_counted_edge_table(extended)


# --- Reparierte Netze führen nur Merkmale ihrer verbliebenen Geometrie (§21) ----------


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_repair_removes_a_previously_edited_pin_from_features_and_cached_replay(
    profile: Profile, tmp_path: Path, quality: Quality
) -> None:
    """Ein geänderter Zapfen verschwindet auch als Merkmal, wenn sein Teilchen entfernt wird."""
    dimensions = json.loads((MESHES.parent / "repair_features.json").read_text(encoding="utf-8"))
    stock = trimesh.creation.box(extents=dimensions["stock_size"])
    pin = trimesh.creation.cylinder(
        radius=dimensions["pin_diameter"] / 2.0,
        height=dimensions["pin_depth"],
        sections=dimensions["pin_sections"],
    )
    pin.apply_translation(dimensions["pin_centre"])
    source = trimesh.util.concatenate([stock, pin])
    assert source.is_watertight and source.is_winding_consistent
    assert len(source.split(only_watertight=False)) == 2

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = source.export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/repair_features.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Prüfkörper laden",
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    loaded = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert loaded.complete
    original = loaded.scene.objects["obj_1"]
    feature = next(entry for entry in original.features.values() if entry.kind == "pin")
    assert feature.params["diameter"] == pytest.approx(dimensions["pin_diameter"], abs=1e-5)
    history.apply(
        "Zapfen ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=(original.id,),
                params={"at_feature": feature.id, "diameter": dimensions["changed_diameter"]},
                seed=20260924,
            )
        ],
    )
    altered = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert altered.complete
    generated = altered.scene.objects[original.id].features[feature.id]
    assert generated.provenance == "generated" and generated.recognised
    assert generated.params["diameter"] == pytest.approx(dimensions["changed_diameter"])
    history.apply(
        "Kleine Teile entfernen",
        [OperationDraft(op="repair", inputs=(original.id,), params={"small_components": True})],
    )

    def checked(current, remembered: ResultCache) -> None:
        """Die wirkliche Ausgabe bleibt ein Würfel mit gültigen aktuellen Merkmalsflächen."""
        result = evaluate(
            current.document,
            profile,
            sources=ProjectSources(current),
            cache=remembered,
            quality=quality,
        )
        assert result.complete
        body = result.scene.objects[original.id]
        assert body.mesh.is_watertight and body.mesh.component_count == 1
        assert body.mesh.volume == pytest.approx(math.prod(dimensions["stock_size"]))
        assert feature.id not in body.features
        assert feature.id in body.reserved_feature_ids
        assert {entry.kind for entry in body.features.values()} == {"face"}
        assert len(body.features) == 6
        for entry in body.features.values():
            assert entry.recognised
            assert entry.face_indices and max(entry.face_indices) < body.mesh.triangle_count
        assert "repair.components_removed" in {
            finding.code for finding in result.scene.report.findings
        }

    checked(project, cache)
    checked(project, cache)
    save(project, tmp_path / "repair.p3d")
    forget_cache()
    reopened = load(tmp_path / "repair.p3d")
    checked(reopened, ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory)))
    history.undo()
    restored = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert restored.complete
    assert restored.scene.objects[original.id].mesh.component_count == 2
    assert restored.scene.objects[original.id].features[feature.id].recognised
    history.redo()
    checked(project, cache)
    history.apply(
        "Entfernten Zapfen ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=(original.id,),
                params={"at_feature": feature.id, "diameter": dimensions["pin_diameter"]},
                seed=20260924,
            )
        ],
    )
    missing = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert missing.stopped_at == project.document.ops[-1].id
    blocker = next(
        finding
        for finding in missing.scene.report.findings
        if finding.op_id == missing.stopped_at and finding.severity == "error"
    )
    assert blocker.suggestions
    assert missing.scene.objects[original.id].mesh.volume == pytest.approx(
        math.prod(dimensions["stock_size"])
    )
