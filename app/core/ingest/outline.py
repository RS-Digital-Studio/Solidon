"""Flache Umrisse mit einer Höhe (Bauplan §25, „SVG und DXF mit
Extrusion").

Ein Logo, eine Dichtung, eine Frontplatte, eine von einem Foto abgezeichnete
Schablone: zwei Dimensionen plus eine Dicke sind ein großer Teil dessen, was
gedruckt wird, und der übliche Weg dahin ist ein Umweg über ein
Modellierprogramm. Das hier ist der kurze Weg.

Löcher kommen als Löcher heraus. Das klingt selbstverständlich und ist der
Teil, der in naiven Umsetzungen schiefgeht — eine Kontur in einer anderen
Kontur ist ein Loch, und das entscheidet die Verschachtelung, nicht die
Reihenfolge, in der die Datei sie aufzählt. Gelesen wird die Zeichnung von
trimesh; verschachtelt wird seit dem 24.08.2026 hier, über shapely — trimeshs
eigener Weg (``polygons_full``) läuft durch ``rtree``, und warum das Paket den
Prozess nicht mehr betreten darf, steht an
:func:`app.core.geom.mesh.on_surface`.

**Einheiten.** SVG hat keine verlässliche: eine Datei sagt 100 und meint
Pixel, Millimeter oder Punkt, je nachdem wer sie geschrieben hat. Also werden
die Koordinaten als Millimeter gelesen, und es gibt eine Zielbreite, um es
anders zu sagen — eine als Erkennung verkleidete Vermutung wäre schlechter als
eine Zahl, die jemand sieht und ändern kann (§11.1).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS, ValidationError
from app.core.geom.mesh import MeshData, concatenated
from app.core.log import get_logger
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Was sich hier lesen lässt. Beides kommt aus den Pfad-Ladern von trimesh.
OUTLINE_SUFFIXES: tuple[str, ...] = (".svg", ".dxf")


@dataclass(frozen=True, slots=True)
class OutlineResult:
    """Der extrudierte Körper und wie der Umriss aussah."""

    mesh: MeshData
    contours: int
    width: float
    """Breite des Umrisses vor dem Skalieren, in den Zahlen der Datei selbst."""


def is_outline(suffix: str) -> bool:
    return suffix.lower() in OUTLINE_SUFFIXES


def nested_polygons(rings: list[np.ndarray]) -> list[Any]:
    """Geschlossene Ringe nach ihrer Verschachtelung zu Flächen mit Löchern.

    Ringreparatur und Aufbau sind die von trimeshs ``polygons_full``
    (``paths_to_polygons``, Löcher gedreht, das Ergebnis noch einmal
    repariert); die Verschachtelung selbst kommt aus
    :func:`app.core.geom.enclosure.enclosure_tree` — **eine** Fassung für
    Zeichnung und Schnittdeckel, damit die beiden nicht auseinanderdriften.
    Warum sie ``rtree`` ersetzt, steht dort und an
    :func:`app.core.geom.mesh.on_surface`.

    Ein erster eigener Versuch mit inneren Punkten und ``buffer(0)`` ist an
    der Messung gescheitert — 295 statt 407 Konturen an einer der drei
    Beispielzeichnungen. Wer nur den Index tauscht, aber anders repariert
    oder anders enthält, bekommt andere Flächen; deshalb hier Zeile für
    Zeile trimeshs Weg. An allen drei Beispiel-SVGs sind Konturen,
    Dreieckszahlen und Volumina identisch mit ``polygons_full``, gemessen
    ohne ``rtree`` im Prozess.
    """
    from shapely.geometry import Polygon
    from trimesh.path.polygons import paths_to_polygons, repair_invalid

    from app.core.geom.enclosure import enclosure_tree

    closed = list(paths_to_polygons(rings))
    roots, tree = enclosure_tree(closed)
    result = []
    for root in roots:
        if closed[root] is None:
            continue
        holes = [
            np.array(closed[child].exterior.coords)[::-1]
            for child in tree[root]
            if closed[child] is not None
        ]
        repaired = repair_invalid(Polygon(shell=closed[root].exterior, holes=holes))
        if repaired is not None:
            result.append(repaired)
    return result


def extrude(payload: bytes, suffix: str, height: float, width: float = 0.0) -> OutlineResult:
    """Liest eine flache Zeichnung und gibt ihr eine Dicke.

    ``width`` skaliert den ganzen Umriss so, dass er diese Breite bekommt;
    null nimmt die Zahlen in der Datei als Millimeter.
    """
    if height <= EPS_GEOM:
        raise ValueError("an extrusion needs a positive height")
    if not is_outline(suffix):
        raise ValidationError(
            field="file",
            detail=_("Dieses Format ist keine flache Zeichnung."),
            value=suffix,
            constraint="not_outline",
        )

    try:
        path = trimesh.load_path(io.BytesIO(payload), file_type=suffix.lower().lstrip("."))
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # jeder Parser scheitert auf seine eigene Art
        raise ValidationError(
            field="file",
            detail=_("Die Zeichnung ließ sich nicht lesen."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    rings = [np.asarray(entry, dtype=float) for entry in getattr(path, "discrete", ())]
    polygons = nested_polygons(rings)
    if not polygons:
        raise ValidationError(
            field="file",
            detail=_("In dieser Zeichnung ist keine geschlossene Fläche."),
            constraint="no_area",
            values={"suffix": suffix},
        )

    bounds = path.bounds
    actual = float(bounds[1][0] - bounds[0][0])
    scale = (width / actual) if width > EPS_GEOM and actual > EPS_GEOM else 1.0

    parts = [trimesh.creation.extrude_polygon(entry, height=height) for entry in polygons]
    body = parts[0] if len(parts) == 1 else concatenated(parts)
    if abs(scale - 1.0) > EPS_GEOM:
        # Nur in der Ebene: die Höhe wurde in Millimetern verlangt und schrumpft
        # nicht, weil die Zeichnung auf eine Breite skaliert wurde.
        body.apply_scale([scale, scale, 1.0])
    # Auf die Platte und zentriert: ein Umriss, gezeichnet um irgendeine Ecke
    # eines Zeichenblatts, landete sonst dort, wo diese Ecke war.
    body.apply_translation(-body.bounds[0] * [0, 0, 1] - [*body.centroid[:2], 0.0])

    _log.info("extruded %d contour(s) from %s", len(polygons), suffix)
    return OutlineResult(mesh=MeshData.of(body), contours=len(polygons), width=actual)
