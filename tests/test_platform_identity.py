"""Dieselbe Geometrie auf jeder Maschine — Bit für Bit (RM-187).

**Der Anlass, gemessen am 17.09.2026.** Derselbe Körper trug 1226 Dreiecke auf
Windows, 1224 auf Ubuntu und 1228 auf macOS, mit demselben Python, demselben
NumPy und demselben Quelltext. Die Ursache lag vor dem Booleschen Kern:
``np.cos`` wählt seine Implementierung nach den Fähigkeiten der CPU — AVX-512,
AVX2, NEON —, und die drei runden die letzte Stelle verschieden. Ein Kunde auf
dem Mac konnte eine Bohrungskette nicht bearbeiten, die auf Windows
bearbeitbar war.

**Was diese Datei ist: der Wächter, der sagt, wann es behoben bleibt.** Sie
schreibt für eine Reihe typischer Körper die Bits fest. Läuft sie auf allen
drei Plattformen grün, gilt die Zusage; wird sie auf einer rot, rechnet dort
etwas anders — und zwar an genau der Stelle, die der Testname nennt.

**Regel 6 gilt hier ausdrücklich nicht.** Die Zusage *ist* die bitgenaue
Gleichheit; ein Vergleich mit Toleranz würde genau den Unterschied
verschlucken, um den es geht. Genau deshalb hat ihn jahrelang niemand gesehen.

**Und die Sollwerte kommen aus einem Lauf.** Das ist erlaubt, weil dies ein
Determinismusnachweis ist und der Test das sagt (`.claude/rules/tests.md`,
„Korpus"). Ein einzelner grüner Lauf auf einer Maschine belegt dabei **nichts**
— die Aussage entsteht erst daraus, dass dieselben Zahlen auf drei
verschiedenen Rechenwerken herauskommen.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from app.core import units
from app.core.geom import lathe


def fingerprint(values: object) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    raw = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(raw.tobytes()).hexdigest()[:16]


@pytest.mark.parametrize(
    ("sections", "digest"),
    [
        (3, "8499ba0788b12dea"),
        (4, "35051fd2bf2a3d2f"),
        (32, "fe8488d27a898c06"),
        (120, "169ba88212acfdba"),
        (192, "5d81998cecab205a"),
    ],
)
def test_a_circle_has_the_same_corners_everywhere(sections: int, digest: str) -> None:
    """Die Ecken eines regelmäßigen Vielecks, festgeschrieben.

    Der unterste Baustein: Steht er, kann jede Geometrie darauf stehen. Fällt
    er, ist alles darüber Zufall.
    """
    values = units.circle_cos_sin(sections)

    assert len(values) == sections
    assert fingerprint(values) == digest


def test_a_cylinder_has_the_same_corners_everywhere() -> None:
    """Der Drehkörper, an dem der Befund hing.

    ``trimesh`` erzeugt die Topologie weiter; ersetzt sind nur die Ecken
    (:mod:`app.core.geom.lathe`). Dieser Test hält fest, dass das reicht.
    """
    body = lathe.cylinder(radius=4.5, height=10.0, sections=120)

    assert len(body.faces) == 480
    assert len(body.vertices) == 242
    assert fingerprint(body.vertices) == "6e428c71b58c4961"


def test_a_tube_has_the_same_corners_everywhere() -> None:
    """Dasselbe für das Rohr — es hat vier Ringe statt zweien."""
    body = lathe.annulus(r_min=3.0, r_max=5.0, height=8.0, sections=120)

    assert len(body.faces) == 960
    assert fingerprint(body.vertices) == "7cc06943c202be2b"


def test_a_revolved_outline_has_the_same_corners_everywhere() -> None:
    """Eine Kontur, die nicht von einem Primitiv kommt — der allgemeine Fall."""
    outline = np.array(
        [[2.0, 0.0], [5.0, 0.0], [5.0, 3.0], [3.5, 4.5], [2.0, 4.5], [2.0, 0.0]],
        dtype=np.float64,
    )
    body = lathe.revolve(outline, sections=64)

    assert fingerprint(body.vertices) == "9eae755372735f95"


def test_a_plain_circle_outline_has_the_same_points_everywhere() -> None:
    """Der Umriss zum Extrudieren — kein Drehkörper, derselbe Anspruch."""
    points = lathe.circle_points(sections=64, radius=7.5, centre=(1.25, -2.5))

    assert points.shape == (64, 2)
    assert fingerprint(points) == "b71ac55dd467e8cf"
