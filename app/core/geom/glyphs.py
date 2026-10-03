"""Schriftzüge aus den mitgelieferten Schriftdateien — Satz und Umrisse über HarfBuzz (RM-471).

Bis RM-471 stand hier matplotlib: ``font_manager`` suchte die Datei, ``TextPath``
setzte und zerlegte die Glyphen, ``to_polygons`` flachte die Kurven ab. Gesetzt
hat matplotlib 3.11 dabei schon über libraqm und damit HarfBuzz; dieselbe
Maschine steckt in uharfbuzz, das mit pygfx ohnehin im Paket liegt. Die
Umrisse zeichnet HarfBuzz selbst aus der Datei, in Schrifteinheiten und ohne
die Rundung auf 1/64 Pixel, die FreeType unter ``TextPath`` legte.

**Die Kurven werden hier abgeflacht**, mit einem Sehnenfehler von höchstens
einem Tausendstel der Schriftgröße und nie mehr als ``units.MAX_FACET_SAG``
(:func:`sag_for`). ``to_polygons`` wich an Liberation Sans bei 10 mm um bis zu
0,19 mm von den Kurven ab, bei 50 mm um 0,24 mm; seine Fläche lag bei 10 mm
bis 1,5 % unter der exakten Glyphenfläche.

**Eine Schriftsuche gibt es nicht**, und das ist die Zusage: Zur Wahl stehen nur
Familien, deren Dateien beiliegen (:data:`FONT_FILES`). Ein Projekt sieht damit
auf jedem Rechner gleich aus, und eine fehlende Datei ist ein Paketfehler, den
:func:`font_file` laut meldet, statt still auf eine andere Schrift zu fallen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np

from app.core.errors import ValidationError
from app.core.types import Point2
from app.core.units import MAX_FACET_SAG
from app.i18n import _

#: Wo die mitgelieferten Schriften liegen.
FONT_FOLDER: Final[Path] = Path(__file__).parent / "data" / "fonts"

#: Welche Datei zu welcher Familie und welchem Schnitt gehört. Dieselbe Wahl,
#: die matplotlibs ``findfont`` bis RM-471 traf: DejaVu führt geneigte Schnitte
#: (``Oblique``), DejaVu Serif und Liberation echte kursive.
FONT_FILES: Final[dict[tuple[str, str], str]] = {
    ("DejaVu Sans", "regular"): "DejaVuSans.ttf",
    ("DejaVu Sans", "bold"): "DejaVuSans-Bold.ttf",
    ("DejaVu Sans", "italic"): "DejaVuSans-Oblique.ttf",
    ("DejaVu Sans", "bold_italic"): "DejaVuSans-BoldOblique.ttf",
    ("DejaVu Serif", "regular"): "DejaVuSerif.ttf",
    ("DejaVu Serif", "bold"): "DejaVuSerif-Bold.ttf",
    ("DejaVu Serif", "italic"): "DejaVuSerif-Italic.ttf",
    ("DejaVu Serif", "bold_italic"): "DejaVuSerif-BoldItalic.ttf",
    ("DejaVu Sans Mono", "regular"): "DejaVuSansMono.ttf",
    ("DejaVu Sans Mono", "bold"): "DejaVuSansMono-Bold.ttf",
    ("DejaVu Sans Mono", "italic"): "DejaVuSansMono-Oblique.ttf",
    ("DejaVu Sans Mono", "bold_italic"): "DejaVuSansMono-BoldOblique.ttf",
    ("Liberation Sans", "regular"): "LiberationSans-Regular.ttf",
    ("Liberation Sans", "bold"): "LiberationSans-Bold.ttf",
    ("Liberation Sans", "italic"): "LiberationSans-Italic.ttf",
    ("Liberation Sans", "bold_italic"): "LiberationSans-BoldItalic.ttf",
    ("Liberation Serif", "regular"): "LiberationSerif-Regular.ttf",
    ("Liberation Serif", "bold"): "LiberationSerif-Bold.ttf",
    ("Liberation Serif", "italic"): "LiberationSerif-Italic.ttf",
    ("Liberation Serif", "bold_italic"): "LiberationSerif-BoldItalic.ttf",
    ("Liberation Mono", "regular"): "LiberationMono-Regular.ttf",
    ("Liberation Mono", "bold"): "LiberationMono-Bold.ttf",
    ("Liberation Mono", "italic"): "LiberationMono-Italic.ttf",
    ("Liberation Mono", "bold_italic"): "LiberationMono-BoldItalic.ttf",
    ("Comfortaa", "regular"): "Comfortaa.ttf",
    ("Dancing Script", "regular"): "DancingScript.ttf",
}

#: Welcher Anteil der Schriftgröße als Sehnenfehler erlaubt ist. Eine feste
#: Grenze allein flachte kleine Schrift relativ gröber ab als große: Bei 3 mm
#: wären 0,05 mm fast zwei Prozent der Glyphe.
SAG_PER_EM: Final = 0.001

#: Wie lang eine Sehne höchstens wird, als Anteil der Schriftgröße. Die Grenze
#: des Sehnenfehlers allein ließe auf der fast geraden Strecke einer Kurve lange
#: Sehnen stehen, und ihre Streifen liest die Merkmalserkennung als Ebene:
#: Der untere Bogen einer „3“ in DejaVu Sans Mono auf 60 mm zerfiel so in zwei
#: gekrümmte Stücke und eine Fläche (gemessen am 03.10.2026; mit drei Prozent
#: wieder ein Bogen). Echte Strecken der Schrift bleiben ungeteilt.
CHORD_PER_EM: Final = 0.03

#: Ein Stück einer Kontur als Polpunkte: zwei für eine Strecke, drei für eine
#: quadratische, vier für eine kubische Bézier-Kurve.
Piece = tuple[Point2, ...]


def font_file(font: str, style: str) -> Path:
    """Die Datei zu Familie und Schnitt — oder eine Absage, die sagt, was hilft."""
    known = {family for family, _style in FONT_FILES}
    if font not in known:
        raise _missing_font(font)
    name = FONT_FILES.get((font, style))
    if name is None:
        raise ValidationError(
            field="style",
            detail=_(
                "„{font}“ gibt es nur in einem Schnitt. Wählen Sie „Normal“, oder "
                "nehmen Sie eine Schrift, die fett und kursiv mitbringt.",
                font=font,
            ),
            value=style,
            constraint="missing_style",
        )
    path = FONT_FOLDER / name
    if not path.is_file():
        raise _missing_font(font)
    return path


def _missing_font(font: str) -> ValidationError:
    return ValidationError(
        field="font",
        detail=_(
            "Die Schrift „{font}“ ist auf diesem Rechner nicht zu finden. "
            "Wählen Sie eine der mitgelieferten — dann sieht das Projekt "
            "überall gleich aus.",
            font=font,
        ),
        value=font,
        constraint="missing_font",
    )


def contours(text: str, size: float, font: str, style: str) -> list[tuple[Piece, ...]]:
    """Die Konturen des gesetzten Textes in Millimetern, die Grundlinie auf y = 0.

    ``size`` ist die Schriftgröße (ein Geviert), wie bei ``TextPath``. Jede
    Kontur ist geschlossen: Das letzte Stück endet am Anfang des ersten.
    """
    import uharfbuzz as hb

    face = hb.Face(hb.Blob.from_file_path(str(font_file(font, style))))
    shaper = hb.Font(face)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(shaper, buffer, {})
    scale = size / float(face.upem)
    found: list[tuple[Piece, ...]] = []
    advance = 0.0
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions, strict=True):
        pen = _Pen(scale, advance + position.x_offset, float(position.y_offset))
        shaper.draw_glyph_with_pen(info.codepoint, pen)
        pen.closePath()
        found.extend(pen.found)
        advance += position.x_advance
    return found


class _Pen:
    """Nimmt HarfBuzz' Zeichenaufrufe als Stücke entgegen, schon verschoben und skaliert."""

    def __init__(self, scale: float, dx: float, dy: float) -> None:
        self.scale = scale
        self.dx = dx
        self.dy = dy
        self.found: list[tuple[Piece, ...]] = []
        self.pieces: list[Piece] = []
        self.start: Point2 | None = None
        self.last: Point2 | None = None

    def _point(self, point: Sequence[float]) -> Point2:
        return ((float(point[0]) + self.dx) * self.scale, (float(point[1]) + self.dy) * self.scale)

    def moveTo(self, point: Sequence[float]) -> None:  # noqa: N802 — Schnittstelle der Pens
        self.closePath()
        self.start = self.last = self._point(point)

    def lineTo(self, point: Sequence[float]) -> None:  # noqa: N802
        end = self._point(point)
        if self.last is not None:
            self.pieces.append((self.last, end))
        self.last = end

    def qCurveTo(self, *points: Sequence[float]) -> None:  # noqa: N802
        # HarfBuzz ruft je quadratischem Stück einmal: Kontrollpunkt, Ende.
        control, end = (self._point(point) for point in points)
        if self.last is not None:
            self.pieces.append((self.last, control, end))
        self.last = end

    def curveTo(self, *points: Sequence[float]) -> None:  # noqa: N802
        first, second, end = (self._point(point) for point in points)
        if self.last is not None:
            self.pieces.append((self.last, first, second, end))
        self.last = end

    def closePath(self) -> None:  # noqa: N802
        if self.start is not None and self.last is not None and self.last != self.start:
            self.pieces.append((self.last, self.start))
        if self.pieces:
            self.found.append(tuple(self.pieces))
        self.pieces = []
        self.start = self.last = None


def sag_for(size: float) -> float:
    """Der erlaubte Sehnenfehler für Schrift dieser Größe, in Millimetern."""
    return min(MAX_FACET_SAG, size * SAG_PER_EM)


def chord_for(size: float) -> float:
    """Die längste erlaubte Sehne einer Kurve für Schrift dieser Größe, in Millimetern."""
    return size * CHORD_PER_EM


def rings(
    found: Sequence[tuple[Piece, ...]],
    sag: float = MAX_FACET_SAG,
    longest: float = math.inf,
) -> list[np.ndarray]:
    """Die Konturen als geschlossene Linienzüge, deren Sehnen höchstens ``sag`` abweichen."""
    result: list[np.ndarray] = []
    for contour in found:
        points: list[Point2] = []
        for poles in contour:
            points.extend(flattened(poles, sag, longest)[:-1])
        if points:
            points.append(points[0])
            result.append(np.asarray(points, dtype=float))
    return result


def flattened(poles: Piece, sag: float, longest: float = math.inf) -> list[Point2]:
    """Ein Stück als Punktfolge mit Anfang und Ende.

    Die Zahl der gleichmäßigen Teilstücke folgt der bekannten Schranke für
    Bézier-Kurven vom Grad n: Abstand zur Sehne höchstens
    ``n(n-1)/8 · max|P(i+2) - 2P(i+1) + P(i)| / k²``. Eine Kurve teilt sich
    zudem so oft, dass keine Sehne länger als ``longest`` wird; eine Strecke
    nie.
    """
    if len(poles) == 2:
        return [poles[0], poles[1]]
    array = np.asarray(poles, dtype=float)
    degree = len(poles) - 1
    bend = float(np.max(np.linalg.norm(array[2:] - 2.0 * array[1:-1] + array[:-2], axis=1)))
    count = max(1, math.ceil(math.sqrt(degree * (degree - 1) * bend / (8.0 * sag))))
    if math.isfinite(longest):
        # Die Bahngeschwindigkeit einer Bézier-Kurve ist höchstens n mal die
        # längste Kante ihres Kontrollpolygons; das begrenzt jede Sehne.
        edge = float(np.max(np.linalg.norm(np.diff(array, axis=0), axis=1)))
        count = max(count, math.ceil(degree * edge / longest))
    t = np.linspace(0.0, 1.0, count + 1)[:, None]
    weights = [math.comb(degree, k) * (1.0 - t) ** (degree - k) * t**k for k in range(degree + 1)]
    curve: Any = sum(weight * array[k] for k, weight in enumerate(weights))
    return [(float(x), float(y)) for x, y in curve]
