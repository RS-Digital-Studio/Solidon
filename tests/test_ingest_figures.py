"""Das Einlesen fragt jede Kennzahl einmal — und lässt sie für das Fenster liegen.

`ingest.loader.normalise` fragte am 1,3-M-Netz zweimal nach der Dichtheit,
rechnete für ein Vorzeichen den ganzen Trägheitstensor und ließ Volumen,
Fläche und Teilezahl kalt zurück, sodass der Hauptthread sie beim ersten
Blick in den Objektbaum nachrechnete (Leistungsdurchsicht, 21.09.2026).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def test_a_triangle_soup_is_welded_before_anyone_asks_whether_it_is_closed(monkeypatch) -> None:
    """Eine STL speichert jedes Dreieck mit eigenen Ecken und ist vor dem Verschweißen
    nie dicht — das braucht keine Zählung über alle Kanten. Danach genügt eine."""
    calls = _counting_watertight(monkeypatch)
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    assert mesh.raw.vertices.shape[0] == 3 * mesh.raw.faces.shape[0], (
        "eine Suppe, wie STL sie speichert"
    )
    result = normalise(mesh, "mm", weld_is_reading=True)
    assert result.mesh.is_watertight
    assert len(calls) == 1, (
        "einmal nach dem Verschweißen, nicht davor und nicht am Ende noch einmal"
    )


def test_a_mesh_with_shared_corners_asks_once_whether_it_is_closed(monkeypatch) -> None:
    """Eine OBJ, PLY oder GLB bringt ihre Punkte geteilt mit: eine Frage nach der Dichtheit.

    Die Gegenprobe zu den zwei Fällen darunter (Durchsicht 0.5.0, Zusatz aus dem
    Paket „netzkern"): Legt das Verschweißen nichts zusammen, bleibt es bei
    einer Frage — auch nachdem das Einlesen nicht mehr vor dem Verschweißen
    fragt. Am 1,2-M-Netz kostet jede Frage eine halbe Sekunde.
    """
    from app.core.geom.mesh import MeshData

    calls = _counting_watertight(monkeypatch)
    ball = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    assert len(ball.vertices) < len(ball.faces), "geteilte Ecken, keine Suppe"

    result = normalise(MeshData.of(ball), "mm")

    assert result.mesh.is_watertight
    assert result.mesh.volume == ball.volume
    assert len(calls) == 1, f"{len(calls)} Fragen nach der Dichtheit"


def _counting_watertight(monkeypatch) -> list[int]:
    """Zählt jede Frage „dicht?" des Einlesens — an trimesh oder an die Kantenzählung.

    Seit RM-224 (25.09.2026) fragt ``normalise`` über ``repair.is_closed``: Die
    Kantenzählung legt die Antwort in trimeshs Cache, und trimesh selbst wird
    dafür gar nicht mehr gefragt. Gezählt werden beide Wege; eine Kantenzählung,
    die für die Teilezahl entsteht, ist keine Frage nach der Dichtheit. Nur, was
    in diesem Thread gefragt wird: Im geteilten Torlauf rechnet im selben
    Prozess mitunter noch ein Hintergrundthread eines früheren Tests an einem
    anderen Netz, und dessen Aufruf landete in dieser Zählung (``assert 2 == 1``
    am 23.09.2026, einzeln grün).
    """
    import threading

    from app.core.ingest import loader

    calls: list[int] = []
    here = threading.get_ident()
    original = trimesh.graph.is_watertight
    asked = loader.is_closed

    def counted(*args, **kwargs):
        if threading.get_ident() == here:
            calls.append(1)
        return original(*args, **kwargs)

    def counted_closed(body):
        if threading.get_ident() == here:
            calls.append(1)
        return asked(body)

    monkeypatch.setattr(trimesh.graph, "is_watertight", counted)
    monkeypatch.setattr(loader, "is_closed", counted_closed)
    return calls


def test_a_weld_that_closes_the_mesh_is_asked_about_once(monkeypatch) -> None:
    """Doppelte Punkte, die das Verschweißen schließt: eine Frage, nicht zwei.

    Gefragt wurde vorher am unverschweißten Netz, ob es dicht war — die
    Antwort zählt aber nur, wenn das Verschweißen das Netz aufreißt. Jetzt
    fragt das Einlesen erst am verschweißten Netz und nur bei „offen" noch
    einmal zurück (Durchsicht 0.5.0, Zusatz aus dem Paket „netzkern").
    """
    import numpy as np

    from app.core.geom.mesh import MeshData

    ball = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    # Die Hälfte der Dreiecke bekommt eigene Kopien ihrer Ecken: offen vor
    # dem Verschweißen, geschlossen danach.
    faces = np.asarray(ball.faces).copy()
    half = len(faces) // 2
    extra = np.asarray(ball.vertices)[faces[:half].ravel()]
    faces[:half] = np.arange(len(extra)).reshape(-1, 3) + len(ball.vertices)
    split = trimesh.Trimesh(vertices=np.vstack([ball.vertices, extra]), faces=faces, process=False)
    assert not split.is_watertight
    calls = _counting_watertight(monkeypatch)

    result = normalise(MeshData.of(split), "mm")

    assert result.mesh.is_watertight
    assert len(calls) == 1, f"{len(calls)} Fragen nach der Dichtheit"


def test_a_weld_that_is_taken_back_keeps_its_answer(monkeypatch) -> None:
    """Zurückgenommenes Verschweißen: Die Antwort des alten Netzes geht mit zurück.

    Das zurückgelegte Netz ist eine Kopie ohne Cache; die Frage „dicht?", deren
    Antwort gerade feststand, stellte ``fix_inversion`` am 1,2-M-Bett ein
    drittes Mal (Durchsicht 0.5.0).
    """
    from app.core.geom.mesh import MeshData

    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((10.0, 0.0, 0.0))
    touching = trimesh.util.concatenate([left, right])
    assert touching.is_watertight
    calls = _counting_watertight(monkeypatch)

    result = normalise(MeshData.of(touching), "mm")

    assert not result.info.welded, "das Verschweißen blieb aus"
    assert result.mesh.is_watertight
    assert len(calls) == 2, f"{len(calls)} Fragen nach der Dichtheit"


def test_the_figures_the_window_reads_are_already_known_after_normalise() -> None:
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    result = normalise(mesh, "mm", weld_is_reading=True)
    figures = result.mesh.raw._cache
    for name in ("is_watertight", "solidon_volume", "area", "solidon_component_count"):
        assert name in figures, f"{name} gehört in den Arbeiter, nicht ins Fenster"
    assert result.mesh.component_count == 1
    assert result.mesh.volume > 0.0


@pytest.mark.parametrize(
    ("place_on_bed", "centre"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_placing_an_import_keeps_its_winding_answer(place_on_bed: bool, centre: bool) -> None:
    """Dichtheit und Umlaufsinn bleiben nach dem Aufsetzen gemeinsam gültig.

    Die Verschiebung verwirft beide trimesh-Antworten. Nur Dichtheit wieder
    einzusetzen verhinderte deren gemeinsame Neuberechnung: eine gültige
    Lochplatte galt danach beim Merkmalsmuster als falsch orientiert.
    """
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    mesh.raw.apply_translation((10.0, -5.0, 0.0))
    result = normalise(mesh, "mm", place_on_bed=place_on_bed, centre=centre)

    assert result.mesh.raw.is_watertight
    assert result.mesh.raw.is_winding_consistent


def test_placing_without_normal_repair_does_not_invent_consistent_winding() -> None:
    """Die gemerkte Antwort ist eine Messung, keine Annahme über geschlossene Netze."""
    from app.core.geom.mesh import MeshData

    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    body.faces[0] = body.faces[0][::-1]
    result = normalise(MeshData.of(body), "mm", unify_normals=False, mend=False, place_on_bed=True)

    assert result.mesh.raw.is_watertight
    assert result.mesh.raw.is_winding_consistent is False


def test_an_inverted_mesh_still_says_its_faces_were_turned() -> None:
    """Der Befund kommt aus dem Vergleich der Dreiecke vorher und nachher, nicht mehr
    aus zwei Volumenrechnungen — und er kommt weiterhin."""
    body = trimesh.creation.box()
    body.invert()
    from app.core.geom.mesh import MeshData

    result = normalise(MeshData.of(body), "mm", weld_is_reading=True)
    assert "ingest.normals_flipped" in [finding.code for finding in result.findings]
    assert result.mesh.volume > 0.0
    plain = normalise(MeshData.of(trimesh.creation.box()), "mm", weld_is_reading=True)
    assert "ingest.normals_flipped" not in [finding.code for finding in plain.findings]


def test_the_volume_is_trimeshs_integral_without_the_inertia() -> None:
    """``MeshData.volume`` rechnet dasselbe Integral wie trimesh, nur ohne Trägheit (RM-208).

    Auch an einem offenen Netz dieselbe Zahl — sie hängt dort an der Lage, und
    so war sie es vorher. Und sie verfällt mit der Geometrie: Wer die Ecken
    verschiebt, bekommt das neue Volumen und nicht das gemerkte.
    """
    import numpy as np

    from app.core.geom.mesh import MeshData

    closed = trimesh.creation.torus(major_radius=20.0, minor_radius=5.0)
    closed.apply_translation((30.0, -10.0, 4.0))
    opened = trimesh.creation.box(extents=(10.0, 20.0, 30.0))
    opened.apply_translation((5.0, 7.0, 9.0))
    opened.update_faces(np.arange(len(opened.faces)) != 0)
    for body in (closed, opened):
        expected = float(body.copy().volume)
        assert MeshData.of(body).volume == pytest.approx(expected, rel=1e-12, abs=1e-9)

    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    data = MeshData.of(box)
    assert data.volume == pytest.approx(1000.0)
    box.vertices = box.vertices * 2.0
    assert MeshData.of(box).volume == pytest.approx(8000.0), "das Volumen verfällt mit dem Netz"
