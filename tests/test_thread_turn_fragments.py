"""Überlappende Zylinderreste sind noch kein Gewinde."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread
from app.core.perceive.features import CylinderFit, _fitted, _without_thread_turns


def _fits_for(
    entries: tuple[tuple[float, tuple[float, float]], ...],
) -> tuple[trimesh.Trimesh, list[tuple[CylinderFit, list[int]]]]:
    """Zylinderfits mit echten, getrennten axialen Patch-Ausdehnungen."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    found: list[tuple[CylinderFit, list[int]]] = []
    for radius, (low, high) in entries:
        offset = len(vertices)
        vertices.extend(((radius, 0.0, low), (0.0, radius, high), (-radius, 0.0, low)))
        faces.append((offset, offset + 1, offset + 2))
        found.append(
            (
                CylinderFit(
                    axis=(0.0, 0.0, 1.0),
                    centre=(0.0, 0.0, (low + high) / 2.0),
                    radius=radius,
                    residual=0.0,
                    inward=True,
                ),
                [len(faces) - 1],
            )
        )
    body = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    return body, found


def test_nested_old_wall_fragments_do_not_hide_the_complete_new_bore() -> None:
    """Gleich beginnende Restflecken zählen nicht als Gewindegänge.

    Beim Verkleinern der Gartenhalter-Bohrung blieben schmale Stücke des alten
    Mantels stehen. Sie lagen axial ineinander und überlappten den neuen,
    vollständigen Mantel. Der Gewindefilter zählte die Stücke als Gänge und
    entfernte damit auch die korrekt erkannte neue Bohrung.
    """
    body, found = _fits_for(
        (
            (5.500, (0.0, 8.30)),
            (5.730, (0.0, 6.70)),
            (5.440, (0.0, 6.85)),
            (5.240, (0.0, 8.46)),
        )
    )

    assert _without_thread_turns(body, found) == found


def test_progressing_overlapping_turns_are_still_filtered() -> None:
    """Drei Gänge erweitern den Lauf nacheinander entlang der Achse."""
    body, found = _fits_for(
        (
            (2.457, (0.0, 1.20)),
            (2.458, (1.00, 4.40)),
            (2.457, (4.20, 8.00)),
            (2.994, (0.20, 8.00)),
        )
    )

    assert _without_thread_turns(body, found) == []


def test_an_overlapping_m3_thread_keeps_its_geometric_helix_proof() -> None:
    """Der zweite Filterweg bleibt am echten M3-Gewinde wirksam."""
    mesh = as_mesh_data(
        printed_thread(ThreadParams(size="M3", length=8.0, internal=False, play=0.0)).mesh
    )

    assert _fitted(mesh).cylinders == []


@pytest.mark.parametrize("count", [1, 2])
def test_a_geometrically_proven_thread_filters_even_one_or_two_fits(
    monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    """Eine gemessene Wendel belegt ihre Flächen unabhängig von der Zahl der Fitflecken."""
    from app.core.perceive import features

    mesh = as_mesh_data(
        printed_thread(ThreadParams(size="M3", length=8.0, internal=False, play=0.0)).mesh
    )
    monkeypatch.setattr(features, "_without_thread_turns", lambda _body, found, **_kwargs: found)
    fitted = _fitted(mesh)
    assert len(fitted.cylinders) >= count
    assert len(fitted.helices) == 1
    assert fitted.helices[0].pitch == pytest.approx(0.5, abs=0.02)

    assert _without_thread_turns(mesh.raw, fitted.cylinders[:count], helices=fitted.helices) == []
