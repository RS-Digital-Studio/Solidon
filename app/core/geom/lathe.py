"""Drehkörper, deren Ecken auf jeder Maschine dieselben Bits tragen (RM-187).

**Der Anlass, gemessen am 17.09.2026.** Derselbe Körper trug 1226 Dreiecke auf
Windows, 1224 auf Ubuntu und 1228 auf macOS — mit demselben Python, demselben
NumPy und demselben Quelltext. Die Ursache liegt nicht im Booleschen Kern,
sondern davor: ``np.cos`` und ``np.sin`` wählen ihre Implementierung nach den
Fähigkeiten der CPU. Ubuntu rechnete mit AVX-512, Windows mit AVX2, macOS mit
NEON, und die drei runden die letzte Stelle verschieden. Der Kontrollversuch
steht daneben und ist eindeutig: Ein Klotz, der ohne eine einzige
transzendente Funktion entsteht, ist auf allen drei Plattformen bitgleich.

Drei Zehntel eines Billiardstels Millimeter sind für sich genommen nichts. Sie
bleiben es nicht: Eine Boolesche Operation entscheidet an solchen Stellen, ob
zwei Flächen koplanar sind, und aus der Entscheidung wird ein anderes Netz.
Aus dem anderen Netz wurde ein Rand, den die Merkmalserkennung nicht mehr als
zwei Ringe lesen konnte, und daraus eine Bohrungskette, die ein Kunde auf zwei
Plattformen bearbeiten konnte und auf der dritten nicht.

**Was dieses Modul tut und was es ausdrücklich nicht tut.** Es baut keinen
eigenen Drehalgorithmus. ``trimesh`` erzeugt die Topologie weiter — welche
Dreiecke entstehen, welche Nullflächen wegfallen, wie die Deckel sitzen —,
denn das hängt an ``sections`` und nicht an Fließkomma. Ersetzt werden nur die
**Ecken**, und zwar über :func:`app.core.units.circle_point`, das seine Winkel
aus Ganzzahlen und über ``decimal`` rechnet.

Möglich ist das, weil ``trimesh.creation.revolve`` mit ``process=False`` eine
vollkommen regelmäßige Ecke liefert: Punkt ``(i, j)`` ist die ``j``-te Stelle
der Kontur, gedreht um den ``i``-ten Winkel. Nachgemessen, bevor darauf gebaut
wurde — der Abstand zwischen trimeshs Ecken und dieser Struktur ist
``0,000e+00``, und nach dem Verschweißen kommt dieselbe Eckenzahl, dieselbe
Dreieckszahl und dasselbe Volumen heraus wie beim unveränderten Aufruf.

Die Prüfung steht in :func:`_replaced_rim` und läuft bei **jedem** Aufruf: Wo
die Struktur nicht passt, bleiben trimeshs Ecken stehen, statt dass falsche
hineingeschrieben werden. Ein stilles Falschergebnis wäre schlimmer als der
Plattformunterschied, den das Modul behebt.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core import units
from app.core.deferred import trimesh
from app.core.geom.transform import moved_points

#: Wie weit trimeshs Ecken von der erwarteten Struktur abweichen dürfen.
#:
#: Es ist keine Toleranz im Sinne von §11.2 und wird an keiner Geometrie
#: gemessen, sondern die Schranke einer **Selbstprüfung**: Passt die Struktur,
#: liegt der Abstand bei null; passt sie nicht, liegt er um Größenordnungen
#: darüber. Der Wert trennt diese beiden Fälle und sonst nichts.
STRUCTURE_LIMIT: float = 1e-9


def revolve(
    linestring: NDArray[np.float64] | Sequence[Sequence[float]],
    sections: int,
    transform: NDArray[np.float64] | None = None,
    **kwargs: Any,
) -> Any:
    """Eine Kontur um die Z-Achse drehen — mit plattformgleichen Ecken.

    Dieselbe Signatur wie ``trimesh.creation.revolve`` für die Fälle, die
    Solidon benutzt: volle Umdrehung, feste Sektionszahl. Eine Teilumdrehung
    (``angle``) geht unverändert an ``trimesh``, weil dort andere Winkel
    entstehen als die Ecken eines regelmäßigen Vielecks.
    """
    outline = np.asarray(linestring, dtype=np.float64)
    if "angle" in kwargs:
        # Teilumdrehung: nicht unser Fall, und stillschweigend raten wäre
        # schlimmer als der unveränderte Weg (Regel 21).
        return trimesh.creation.revolve(
            linestring=outline, sections=sections, transform=transform, **kwargs
        )
    raw = trimesh.creation.revolve(linestring=outline, sections=sections, process=False, **kwargs)
    body = _replaced_rim(raw, outline, int(sections))
    body.merge_vertices()
    if transform is not None:
        # ``moved_points`` und nicht ``apply_transform``: dieselbe Zusage wie
        # ueberall (RM-187). Der Parameter heisst ``transform`` wie bei
        # ``trimesh.creation.revolve``, deshalb der Namensimport.
        body.vertices = moved_points(
            np.asarray(body.vertices, dtype=np.float64),
            np.asarray(transform, dtype=np.float64),
        )
    return body


def cylinder(
    radius: float,
    height: float,
    sections: int,
    transform: NDArray[np.float64] | None = None,
    **kwargs: Any,
) -> Any:
    """Ein Zylinder um die Z-Achse, mittig im Ursprung — mit gleichen Ecken überall.

    ``trimesh.creation.cylinder`` baut seinen Zylinder selbst über ``revolve``
    aus genau dieser Kontur; hier steht sie, damit der deterministische Weg
    derselbe ist.
    """
    half = abs(float(height)) / 2.0
    outline = np.array(
        [[0.0, -half], [float(radius), -half], [float(radius), half], [0.0, half]],
        dtype=np.float64,
    )
    body = revolve(outline, sections=int(sections), transform=transform, **kwargs)
    body.metadata.update({"shape": "cylinder", "height": height, "radius": radius})
    return body


def annulus(
    r_min: float,
    r_max: float,
    height: float,
    sections: int,
    transform: NDArray[np.float64] | None = None,
    **kwargs: Any,
) -> Any:
    """Ein Rohr um die Z-Achse, mittig im Ursprung — mit gleichen Ecken überall."""
    half = abs(float(height)) / 2.0
    inner, outer = float(r_min), float(r_max)
    outline = np.array(
        [
            [inner, -half],
            [outer, -half],
            [outer, half],
            [inner, half],
            [inner, -half],
        ],
        dtype=np.float64,
    )
    body = revolve(outline, sections=int(sections), transform=transform, **kwargs)
    body.metadata.update({"shape": "annulus", "height": height, "r_min": inner, "r_max": outer})
    return body


def circle_points(
    sections: int, radius: float = 1.0, centre: tuple[float, float] = (0.0, 0.0)
) -> NDArray[np.float64]:
    """Die Ecken eines regelmäßigen Vielecks in der Ebene, gegen den Uhrzeigersinn.

    Für alles, was keinen Drehkörper baut, aber einen Kreis braucht — einen
    Umriss zum Extrudieren, eine Schnittkontur, ein Lochbild.
    """
    table = units.circle_cos_sin(int(sections))
    x, y = float(centre[0]), float(centre[1])
    return np.asarray(
        [(x + radius * cos, y + radius * sin) for cos, sin in table], dtype=np.float64
    )


def _replaced_rim(body: Any, outline: NDArray[np.float64], sections: int) -> Any:
    """Die Ecken durch plattformgleiche ersetzen — aber nur, wenn die Struktur passt.

    ``trimesh`` legt seine Ecken schnittweise ab: erst die ganze Kontur beim
    ersten Winkel, dann beim zweiten, und so fort. Punkt ``(i, j)`` ist damit
    ``(radius[j]·cos_i, radius[j]·sin_i, height[j])``.

    **Geprüft wird das bei jedem Aufruf**, und nicht einmal beim Schreiben
    dieses Moduls. Eine Bibliothek darf ihre innere Anordnung ändern; ein
    stilles Falschergebnis wäre der schlechteste Ausgang von allen, deutlich
    schlechter als der Plattformunterschied, um den es geht. Passt die
    Struktur nicht, bleiben trimeshs Ecken stehen.
    """
    per = len(outline)
    corners = np.asarray(body.vertices, dtype=np.float64)
    if len(corners) != sections * per:
        return body
    radius = outline[:, 0]
    height = outline[:, 1]
    table = np.asarray(units.circle_cos_sin(sections), dtype=np.float64)
    wanted = np.column_stack(
        (
            np.repeat(table[:, 0], per) * np.tile(radius, sections),
            np.repeat(table[:, 1], per) * np.tile(radius, sections),
            np.tile(height, sections),
        )
    )
    if float(np.max(np.abs(corners - wanted))) > STRUCTURE_LIMIT:
        return body
    body.vertices = wanted
    return body


def rigid_inverse(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """Die Inverse einer Starrkörpertransformation — analytisch statt über LAPACK.

    Eine Matrix aus Drehung ``R`` und Verschiebung ``t`` hat die Inverse
    ``[R^T | -R^T·t]``. Das ist exakt hinschreibbar, und ``np.linalg.inv``
    dafür zu rufen ist zweierlei Verschwendung: Es löst ein allgemeines
    Gleichungssystem, wo eine Transposition genügt, **und** es geht durch
    LAPACK, dessen Ergebnis von der Maschine abhängt (RM-187).

    Der Unterschied ist winzig und bleibt es nicht: Hier wird ein ganzes Netz
    damit hin- und zurückgedreht, bevor eine Boolesche Operation darauf
    entscheidet.

    Ist die obere linke 3x3 keine Drehung — ungleiche Skalierung, Scherung —,
    trägt die Formel nicht, und die Funktion gibt an ``np.linalg.inv`` ab,
    statt ein falsches Ergebnis zu liefern.
    """
    raw = np.asarray(matrix, dtype=np.float64)
    turn = raw[:3, :3]
    # Eine Drehung erfüllt R·R^T = I. Geprüft wird das, nicht angenommen.
    if not np.allclose(turn @ turn.T, np.eye(3), atol=1e-9) or raw.shape != (4, 4):
        return np.asarray(np.linalg.inv(raw), dtype=np.float64)
    if not np.allclose(raw[3], (0.0, 0.0, 0.0, 1.0), atol=1e-12):
        return np.asarray(np.linalg.inv(raw), dtype=np.float64)
    back = np.eye(4, dtype=np.float64)
    back[:3, :3] = turn.T
    back[:3, 3] = -(turn.T @ raw[:3, 3])
    return back
