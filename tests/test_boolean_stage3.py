"""Stufe 3 der Rückfallkette bleibt unter der Zugabe (``boolean.JITTER_REACH_LIMIT``).

Ihr Stups schob Werkzeuge unter die Fläche, über die sie um ``BOOLEAN_OVERLAP``
reichen, und ließ über Öffnungen eine Haut stehen (Durchsicht welle4-b); die
Grenze hält auch längs einer schrägen Normale (Durchsicht über fix/review-kern).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pytest
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData


def _opening_skin(mesh: MeshData, inside: Callable[[np.ndarray], np.ndarray]) -> float:
    """Die Fläche waagrechter Dreiecke in einer Öffnung — eine Haut, die dort nicht hingehört."""
    raw = mesh.raw
    flat = np.abs(np.asarray(raw.face_normals)[:, 2]) > 0.9
    skin = flat & inside(np.asarray(raw.triangles_center))
    return float(np.asarray(raw.area_faces)[skin].sum())


def test_the_jitter_stage_leaves_no_skin_where_a_tool_reaches_past() -> None:
    """Beobachtung der Durchsicht welle4-b: Stufe 3 schob ein Werkzeug unter die
    Fläche, über die es um ``BOOLEAN_OVERLAP`` hinausreicht.

    Der Stups wuchs mit der Diagonale: am Behältergehäuse (108 mm) bis
    0,019 mm, fast das Doppelte der Zugabe von 0,01 mm. Wo Werkzeugdeckel und
    Körperdeckel gegeneinander rückten, blieb über der Öffnung eine Haut stehen
    — in 15 von 20 Startwerten, und an einer Platte mit Bohrung Ø 5 in 3 von 20
    (einmal die ganze Mündung zu). Der Steckdeckel stieß darauf und meldete
    „Der Kragen stößt unter dem Rand auf die Wand“, ein Schraubdeckel hätte die
    Haut still mitgenommen. Jetzt bleibt jeder Eckpunkt innerhalb eines
    Viertels der Zugabe (``JITTER_REACH_LIMIT``).
    """
    from app.core.geom import boolean as chain

    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    bore = trimesh.creation.cylinder(
        radius=2.5, height=8.0 + 2 * chain.BOOLEAN_OVERLAP, sections=48
    )
    outside = trimesh.creation.box(extents=(80.0, 60.0, 40.0))
    outside.apply_translation((0.0, 0.0, 20.0))
    height = 40.0 - 2.0 + chain.BOOLEAN_OVERLAP
    cavity = trimesh.creation.box(extents=(74.0, 54.0, height))
    cavity.apply_translation((0.0, 0.0, 2.0 + height / 2.0))
    cases = (
        ("Platte mit Bohrung", plate, bore, lambda c: np.hypot(c[:, 0], c[:, 1]) < 2.4),
        (
            "Behältergehäuse",
            outside,
            cavity,
            lambda c: (np.abs(c[:, 0]) < 36.9) & (np.abs(c[:, 1]) < 26.9) & (c[:, 2] > 39.0),
        ),
    )

    skins: list[str] = []
    for name, body, tool, inside in cases:
        for seed in range(20):
            result = boolean(
                "difference",
                [MeshData.of(body), MeshData.of(tool)],
                stages=("jittered",),
                seed=seed,
            )
            area = _opening_skin(result.mesh, inside)
            if area > 0.0:
                skins.append(f"{name}, Startwert {seed}: {area:.2f} mm²")
    assert not skins, "Haut über der Öffnung: " + "; ".join(skins)


def test_the_jitter_limit_holds_the_overlap_along_any_normal() -> None:
    """Die Grenze der dritten Stufe hält die Zugabe auch längs einer schrägen Normale.

    Je Koordinate bewegt der Stups einen Eckpunkt höchstens um die Grenze r.
    Längs einer Achse rücken zwei Eckpunkte um höchstens 2r aufeinander zu,
    längs (1, 1, 1)/√3 aber um 2·√3·r, denn alle drei Koordinaten dürfen voll
    ausschlagen (Durchsicht über fix/review-kern, L4). Zufallsfrei gesagt.
    """
    from app.core.geom import boolean as chain

    closest = 2 * math.sqrt(3.0) * chain.JITTER_REACH_LIMIT
    assert closest < chain.BOOLEAN_OVERLAP, (
        f"zwei Eckpunkte rücken bis {closest:.5f} mm zusammen, die Zugabe ist "
        f"{chain.BOOLEAN_OVERLAP} mm"
    )


@pytest.mark.parametrize(
    "normal", [(0.0, 0.0, 1.0), (1.0, 1.0, 1.0)], ids=["achsparallel", "schraeg"]
)
def test_the_farthest_jitter_keeps_a_slanted_bore_open(normal: tuple[float, float, float]) -> None:
    """Der äußerste Stups, den die Grenze zulässt, schließt keine Mündung — auch schräg.

    Zufallsfrei nachgestellt: Platte 80 × 50 × 8 mit Bohrung Ø 5, das Werkzeug
    um ``BOOLEAN_OVERLAP`` über beiden Flächen, gedreht, bis die Plattennormale
    ``normal`` ist. Die Platte rückt je Achse um +r, das Werkzeug um −r — so
    weit, wie Stufe 3 jeden Eckpunkt höchstens bewegt —, gerechnet über
    *direkt*. Schräg sind das 0,87 der Zugabe; schon r = 2,9 µm schloss die
    Mündung ganz (19,58 mm², Durchsicht über fix/review-kern, L4).
    """
    from app.core.geom import boolean as chain

    reach = chain.JITTER_REACH_LIMIT
    turn = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], list(normal))
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    bore = trimesh.creation.cylinder(
        radius=2.5, height=8.0 + 2 * chain.BOOLEAN_OVERLAP, sections=48
    )
    for part, sign in ((plate, 1.0), (bore, -1.0)):
        part.apply_transform(turn)
        part.apply_translation((sign * reach, sign * reach, sign * reach))

    result = boolean("difference", [MeshData.of(plate), MeshData.of(bore)], stages=("direct",))
    back = result.mesh.raw.copy()
    back.apply_transform(np.linalg.inv(turn))

    area = _opening_skin(MeshData.of(back), lambda c: np.hypot(c[:, 0], c[:, 1]) < 2.4)
    assert area == 0.0, f"Haut über der Mündung: {area:.2f} mm²"
