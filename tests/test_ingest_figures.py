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
    calls: list[int] = []
    original = trimesh.graph.is_watertight

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(trimesh.graph, "is_watertight", counted)
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    assert mesh.raw.vertices.shape[0] == 3 * mesh.raw.faces.shape[0], (
        "eine Suppe, wie STL sie speichert"
    )
    result = normalise(mesh, "mm", weld_is_reading=True)
    assert result.mesh.is_watertight
    assert len(calls) == 1, (
        "einmal nach dem Verschweißen, nicht davor und nicht am Ende noch einmal"
    )


def test_the_figures_the_window_reads_are_already_known_after_normalise() -> None:
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    result = normalise(mesh, "mm", weld_is_reading=True)
    figures = result.mesh.raw._cache
    for name in ("is_watertight", "solidon_volume", "area", "solidon_component_count"):
        assert name in figures, f"{name} gehört in den Arbeiter, nicht ins Fenster"
    assert result.mesh.component_count == 1
    assert result.mesh.volume > 0.0


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
