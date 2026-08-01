"""Flache Umrisse mit einer Höhe (Bauplan §25, „SVG und DXF mit
Extrusion").

Ein Logo, eine Dichtung, eine Frontplatte, eine von einem Foto abgezeichnete
Schablone: zwei Dimensionen plus eine Dicke sind ein großer Teil dessen, was
gedruckt wird, und der übliche Weg dahin ist ein Umweg über ein
Modellierprogramm. Das hier ist der kurze Weg.

Löcher kommen als Löcher heraus. Das klingt selbstverständlich und ist der
Teil, der in naiven Umsetzungen schiefgeht — eine Kontur in einer anderen
Kontur ist ein Loch, und das entscheidet die Verschachtelung, nicht die
Reihenfolge, in der die Datei sie aufzählt. Diese Arbeit gehört hier trimesh,
und es macht sie richtig.

**Einheiten.** SVG hat keine verlässliche: eine Datei sagt 100 und meint
Pixel, Millimeter oder Punkt, je nachdem wer sie geschrieben hat. Also werden
die Koordinaten als Millimeter gelesen, und es gibt eine Zielbreite, um es
anders zu sagen — eine als Erkennung verkleidete Vermutung wäre schlechter als
eine Zahl, die jemand sieht und ändern kann (§11.1).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import trimesh

from app.core.errors import PROGRAMMING_ERRORS, ValidationError
from app.core.geom.mesh import MeshData
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
    """Width of the outline before scaling, in the file's own numbers."""


def is_outline(suffix: str) -> bool:
    return suffix.lower() in OUTLINE_SUFFIXES


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

    polygons = list(getattr(path, "polygons_full", ()) or ())
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
    body = parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)
    if abs(scale - 1.0) > EPS_GEOM:
        # Nur in der Ebene: die Höhe wurde in Millimetern verlangt und schrumpft
        # nicht, weil die Zeichnung auf eine Breite skaliert wurde.
        body.apply_scale([scale, scale, 1.0])
    # Auf die Platte und zentriert: ein Umriss, gezeichnet um irgendeine Ecke
    # eines Zeichenblatts, landete sonst dort, wo diese Ecke war.
    body.apply_translation(-body.bounds[0] * [0, 0, 1] - [*body.centroid[:2], 0.0])

    _log.info("extruded %d contour(s) from %s", len(polygons), suffix)
    return OutlineResult(mesh=MeshData.of(body), contours=len(polygons), width=actual)
