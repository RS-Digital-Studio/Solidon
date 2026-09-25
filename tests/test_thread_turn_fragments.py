"""Überlappende Zylinderreste sind noch kein Gewinde."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread
from app.core.perceive.features import CylinderFit, _fitted, _without_thread_turns


def _fits_for(
    entries: tuple[tuple[float, tuple[float, float]], ...],
    *,
    connected: bool = False,
) -> tuple[trimesh.Trimesh, list[tuple[CylinderFit, list[int]]]]:
    """Zylinderfits mit echten, getrennten axialen Patch-Ausdehnungen.

    Ohne ``connected`` ist jedes Dreieck ein Teil für sich; mit verbinden zwei
    Brückendreiecke je Nachbarpaar alle zu einem Körper, wie die Gänge eines
    Gewindes auf einer Fläche liegen.
    """
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    found: list[tuple[CylinderFit, list[int]]] = []
    for radius, (low, high) in entries:
        offset = len(vertices)
        vertices.extend(((radius, 0.0, low), (0.0, radius, high), (-radius, 0.0, low)))
        if connected and offset:
            faces.append((offset - 2, offset - 1, offset))
            faces.append((offset, offset + 1, offset - 1))
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
        ),
        connected=True,
    )

    assert _without_thread_turns(body, found) == []


def test_turns_on_separate_parts_are_no_thread() -> None:
    """Derselbe fortschreitende Lauf, aber jeder Abschnitt auf einem eigenen Teil.

    Ein Gewinde ist eine zusammenhängende Fläche; Abschnitte getrennter Teile
    können keine Gänge einer Wendel sein. Der Besenhalter
    (``broomholdervcd_d35mm.stl``) besteht aus drei Teilen übereinander, die
    sich in der Höhe um 0,48 mm überlappen: Vier koaxiale Bögen R 5,10 aus
    zwei Teilen ergaben einen Lauf aus drei Abschnitten, und mit ihm verwarf
    die Erkennung 30 von 45 Zylindern — darunter zwölf Bohrungen Ø 6,12 und
    Ø 5,44, die durch alle drei Teile gehen (25.09.2026, RM-219).
    """
    body, found = _fits_for(
        (
            (2.457, (0.0, 1.20)),
            (2.458, (1.00, 4.40)),
            (2.457, (4.20, 8.00)),
            (2.994, (0.20, 8.00)),
        )
    )

    assert _without_thread_turns(body, found) == found


def test_pieces_of_one_wall_that_start_hundredths_apart_are_no_thread() -> None:
    """Die Stücke einer Wand teilen fast ihre ganze Höhe und bringen kaum Neues.

    Am Flaschenhalter begannen die Stücke der Flaschentaschen R 49 bei −0,05,
    −0,03 und 0,00 mm und endeten bei 159,96 bis 160,00; jede Verschiebung über
    der Schweißtoleranz zählte als Gang, und die Regel verwarf die Taschen
    (25.09.2026, RM-219).
    """
    body, found = _fits_for(
        ((49.0, (-0.05, 159.96)), (48.999, (-0.03, 159.97)), (48.993, (0.0, 160.0))),
        connected=True,
    )

    assert _without_thread_turns(body, found) == found


def test_sections_that_only_touch_are_no_thread() -> None:
    """Aufeinandergesetzte Absätze laufen nicht ineinander, wie Gänge es tun.

    Die abgesetzten Ränder des Screen-Covers: R 24,867, 24,975 und 25,084 mm,
    jeder genau auf dem vorigen.
    """
    body, found = _fits_for(
        ((24.867, (0.0, 1.0)), (24.975, (1.0, 2.0)), (25.084, (2.0, 3.0))), connected=True
    )

    assert _without_thread_turns(body, found) == found


def test_turns_facing_both_ways_are_no_thread() -> None:
    """Die Gänge eines Gewindes tragen alle dieselbe Materialseite."""
    body, found = _fits_for(
        ((2.457, (0.0, 1.20)), (2.458, (1.00, 4.40)), (2.457, (4.20, 8.00))), connected=True
    )
    mixed = [found[0], (replace(found[1][0], inward=False), found[1][1]), found[2]]

    assert _without_thread_turns(body, mixed) == mixed


def test_a_pin_joint_of_separate_parts_keeps_its_cylinders() -> None:
    """Zapfen, Rohr, Zapfen — drei Teile, alle Ø 6, in der Höhe je 0,2 mm überlappend.

    Am Netz derselbe Aufbau wie am Besenhalter: koaxial, gleicher Radius, und
    jede Spanne verlängert den Lauf. Zusammengelegt wird nichts — Zapfen und
    Bohrung sind verschiedene Flächen, die Zapfen berühren sich nicht —, und
    jedes Stück ist ein eigener Teil, also keine Wendel.
    """
    pins = [trimesh.creation.cylinder(radius=3.0, height=10.0, sections=64) for _ in range(2)]
    tube = trimesh.creation.annulus(r_min=3.0, r_max=6.0, height=10.0, sections=64)
    for number, part in enumerate((pins[0], tube, pins[1])):
        part.apply_translation((0.0, 0.0, 5.0 + number * 9.8))
    mesh = MeshData.of(trimesh.util.concatenate([*pins, tube]))

    fits = sorted((round(fit.radius, 2), fit.inward) for fit, _patch in _fitted(mesh).cylinders)

    # Zwei Zapfen und die Bohrung R 3, dazu der Mantel des Rohrs R 6.
    assert fits == [(3.0, False), (3.0, False), (3.0, True), (6.0, False)]


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
