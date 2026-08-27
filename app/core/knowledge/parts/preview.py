"""Vorschaubilder für den Katalog (Bauplan §24.3).

„Eine Bibliothek, die man nicht sieht, existiert für den Nutzer nicht." Also
zeigt der Katalog Bilder — und sie sind **aus den Bausteinen selbst
gerendert**, nicht von Hand gepflegt. Eine gezeichnete Vorschau ist an dem Tag
falsch, an dem sich ein Baustein ändert, und niemand merkt es, bis jemand den
falschen Baustein wählt.

Gezeichnet wird über :mod:`app.core.drawing`, dieselbe Projektion, aus der
auch die Abbildungen des Handbuchs entstehen: ein zweiter Renderweg wäre
einer, der irgendwann anders aussieht als der erste.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core import drawing
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.parts.registry import PartSpec
from app.core.types import BaseParams

#: Kantenlänge eines Vorschaubildes in Pixeln.
SIZE = drawing.THUMBNAIL


@dataclass(frozen=True, slots=True)
class Preview:
    """Ein gerendertes Vorschaubild."""

    svg: str
    triangles: int

    def write(self, path: object) -> None:
        from pathlib import Path

        Path(str(path)).write_text(self.svg, encoding="utf-8")


def render(
    spec: PartSpec,
    params: BaseParams | None = None,
    size: int = SIZE,
    *,
    theme: drawing.Theme = "light",
    edges: bool = False,
    around: float = -35.0,
    down: float = 25.0,
) -> Preview:
    """Ein Baustein als Vorschaubild, aus dem üblichen Dreiviertelwinkel.

    ``edges`` zeichnet Kantenlinien dazu. Im Katalog bleibt es aus — dort steht
    das Bild neben seinem Namen und muss nur wiedererkennbar sein. Für die
    Abbildungen des Handbuchs, an denen etwas erklärt wird, ist es an.

    ``around`` und ``down`` drehen die Kamera, falls die Vorgabe gerade das
    Merkmal verdeckt, auf das es bei diesem Teil ankommt.
    """
    mesh = as_mesh_data(spec.fn(params or spec.params()).mesh)
    colours = drawing.palette(theme)
    tone = colours.subtractive if spec.subtractive else colours.solid
    return Preview(
        svg=drawing.project(
            mesh.raw, size, tone, theme=theme, edges=edges, around=around, down=down
        ),
        triangles=mesh.triangle_count,
    )
