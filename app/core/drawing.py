"""Zeichnen ohne Qt — SVG für Handbuch und Katalog (Bauplan §2.6, §24.3).

Zwei Sorten Bild entstehen hier, und beide sind erzeugt statt gepflegt.

**Körper werden projiziert.** Ein Netz wird gedreht, nach Tiefe sortiert und
als Dreiecksfläche gezeichnet. Das reicht für ein Vorschaubild, es läuft auf
einem Bauserver ohne Bildschirm, und es kostet keine Abhängigkeit (§36).

**Schemata werden gezeichnet.** Ein Fensteraufbau, ein Stapel, ein Spiel
zwischen Zapfen und Loch — dafür gibt es keinen Körper, den man rendern
könnte. Also gibt es hier Linien, Pfeile, Maßlinien und Beschriftungen, aus
denen sich eine technische Skizze zusammensetzt.

Warum überhaupt SVG und nicht ein fertiges Bild: Beschriftungen bleiben Text.
Sie sind übersetzbar (Regel 20), sie skalieren auf jedem Bildschirm, und sie
lassen sich in beiden Themen unterschiedlich einfärben, ohne dass jemand ein
zweites Bild pflegen muss.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    # Nur für die Typprüfung: zur Laufzeit werden ``numpy`` und ``trimesh``
    # erst in den Funktionen importiert, die sie brauchen. So bleibt das Modul
    # auch dort importierbar, wo die Geometriepakete nicht installiert sind.
    import numpy as np
    import trimesh

Theme = Literal["light", "dark"]

#: Woher das Licht kommt — über die linke Schulter, wie in jeder technischen
#: Zeichnung.
LIGHT: Final = (-0.4, -0.6, 0.7)

#: Kantenlänge eines Vorschaubildes in Pixeln.
THUMBNAIL: Final = 160


@dataclass(frozen=True, slots=True)
class Palette:
    """Die Farben einer Zeichnung, je Thema.

    Getrennt gehalten und nicht aus ``app.ui.theme`` gelesen: der Kern kennt
    kein Qt, und eine Abbildung muss auch dort entstehen können, wo nie ein
    Fenster geöffnet wird — im Test, in der Kommandozeile, auf dem Bauserver.
    Die Werte sind auf dieselben Hintergründe abgestimmt.
    """

    paper: str
    """Hintergrund der Zeichnung."""
    ink: str
    """Linien und Schrift — der Normalfall."""
    muted: str
    """Was da ist, aber nicht gemeint ist: Raster, Hilfslinien, Rahmen."""
    accent: str
    """Worum es auf diesem Bild geht. Nie die einzige Kodierung (Regel 18)."""
    warn: str
    """Die Stelle, an der etwas schiefgeht."""
    fill: str
    """Flächen, die etwas enthalten — Felder, Kästen, Zonen."""
    solid: tuple[float, float, float]
    """Grundfarbe eines Körpers beim Projizieren."""
    subtractive: tuple[float, float, float]
    """Grundfarbe eines Körpers, der Material wegnimmt statt hinzuzufügen."""


#: Beide Themen. Kontraste gegen den jeweiligen Fensterhintergrund geprüft.
#:
#: **Diese Werte sehen aus wie Dubletten der Rollen in ``app/ui/palette.py``
#: und sind keine.** Nachgemessen: der Warnton der Oberfläche (``#e0a33c``)
#: bringt auf weißem Papier 2,22 Kontrast und liegt damit unter der
#: AA-Schwelle; ``#b4611c`` bringt dort 4,50. Zeichnungen liegen auf Papier
#: oder auf dunklem Grund, die Oberfläche nur auf letzterem — dieselbe Rolle,
#: drei Hintergründe, drei Werte. Wer sie gleichzieht, macht eine der drei
#: unlesbar.
#:
#: Aus demselben Grund liest der Kern die Rollen nicht: er darf nichts aus
#: ``app/ui`` importieren, und er bräuchte sie auch nicht — was hier steht,
#: gilt für Papier.
PALETTES: Final[dict[Theme, Palette]] = {
    "light": Palette(
        paper="#ffffff",
        ink="#1c2026",
        muted="#8b929b",
        accent="#2f6fb0",
        warn="#b4611c",
        fill="#e9ebee",
        solid=(0.72, 0.77, 0.82),
        subtractive=(0.88, 0.66, 0.36),
    ),
    "dark": Palette(
        paper="#1b1f25",
        ink="#e6e9ee",
        muted="#7c848f",
        accent="#6ba3dd",
        warn="#d99048",
        fill="#262b33",
        solid=(0.62, 0.68, 0.75),
        subtractive=(0.82, 0.62, 0.34),
    ),
}


def palette(theme: Theme = "light") -> Palette:
    return PALETTES[theme]


# --- Schemazeichnungen ---------------------------------------------------------------


@dataclass
class Canvas:
    """Eine Zeichenfläche, auf der Elemente in Reihenfolge landen.

    Absichtlich schlicht: es gibt kein Layout und keine Gruppen, weil jede
    Abbildung des Handbuchs ihre Maße ohnehin selbst kennt. Was fehlt, würde
    nur eine zweite Sprache neben SVG erfinden.
    """

    width: float
    height: float
    theme: Theme = "light"
    _body: list[str] = field(default_factory=list, init=False)
    _defs: dict[str, str] = field(default_factory=dict, init=False)

    @property
    def colours(self) -> Palette:
        return PALETTES[self.theme]

    # --- Flächen und Linien ---

    def background(self) -> None:
        """Papier unterlegen — sonst steht die Zeichnung auf durchsichtig."""
        self._body.append(
            f'<rect x="0" y="0" width="{_n(self.width)}" height="{_n(self.height)}" '
            f'fill="{self.colours.paper}" />'
        )

    def box(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        stroke: str | None = None,
        fill: str | None = None,
        dashed: bool = False,
        radius: float = 3.0,
        weight: float = 1.4,
    ) -> None:
        """Ein Kasten. Die Grundform jedes Schemas."""
        self._body.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(width)}" height="{_n(height)}" '
            f'rx="{_n(radius)}" fill="{fill or "none"}" '
            f'stroke="{stroke or self.colours.ink}" stroke-width="{_n(weight)}"'
            f"{_dash(dashed)} />"
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str | None = None,
        dashed: bool = False,
        weight: float = 1.4,
    ) -> None:
        self._body.append(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{stroke or self.colours.ink}" stroke-width="{_n(weight)}"'
            f'{_dash(dashed)} stroke-linecap="round" />'
        )

    def polygon(
        self,
        points: list[tuple[float, float]],
        *,
        stroke: str | None = None,
        fill: str | None = None,
        weight: float = 1.4,
    ) -> None:
        corners = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
        self._body.append(
            f'<polygon points="{corners}" fill="{fill or "none"}" '
            f'stroke="{stroke or self.colours.ink}" stroke-width="{_n(weight)}" />'
        )

    def circle(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        stroke: str | None = None,
        fill: str | None = None,
        dashed: bool = False,
        weight: float = 1.4,
    ) -> None:
        self._body.append(
            f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(radius)}" '
            f'fill="{fill or "none"}" stroke="{stroke or self.colours.ink}" '
            f'stroke-width="{_n(weight)}"{_dash(dashed)} />'
        )

    def arc(
        self,
        x: float,
        y: float,
        radius: float,
        degrees: float,
        *,
        stroke: str | None = None,
        weight: float = 1.2,
    ) -> None:
        """Ein Winkelbogen, von der Senkrechten aus im Uhrzeigersinn.

        Ein Winkel, der nur als Zahl danebensteht, lässt offen, wovon aus
        gemessen wurde — bei Überhängen ist genau das die Verwechslung, die man
        einmal macht und danach nie wieder: 45 Grad gegen die Senkrechte sind
        45 Grad gegen die Waagerechte, aber 30 Grad sind es eben nicht.
        """
        turn = math.radians(degrees)
        end_x = x + radius * math.sin(turn)
        end_y = y - radius * math.cos(turn)
        large = 1 if abs(degrees) > 180 else 0
        sweep = 1 if degrees > 0 else 0
        self._body.append(
            f'<path d="M {_n(x)} {_n(y - radius)} '
            f'A {_n(radius)} {_n(radius)} 0 {large} {sweep} {_n(end_x)} {_n(end_y)}" '
            f'fill="none" stroke="{stroke or self.colours.accent}" '
            f'stroke-width="{_n(weight)}" />'
        )

    def hatched(self, x: float, y: float, width: float, height: float, *, angle: int = 45) -> None:
        """Eine schraffierte Fläche.

        Der Grund steht in Regel 18: eine Zone, die sich nur durch ihre Farbe
        von der Nachbarzone unterscheidet, verschwindet für jeden Vierzehnten
        unter den Lesern. Schraffur ist die zweite Kodierung, die daneben
        stehen bleibt.
        """
        name = f"hatch{angle}"
        self._defs[name] = (
            f'<pattern id="{name}" width="6" height="6" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate({angle})">'
            f'<line x1="0" y1="0" x2="0" y2="6" stroke="{self.colours.muted}" '
            f'stroke-width="1.2" /></pattern>'
        )
        self._body.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(width)}" height="{_n(height)}" '
            f'fill="url(#{name})" />'
        )

    # --- Pfeile und Maße ---

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str | None = None,
        dashed: bool = False,
        weight: float = 1.4,
    ) -> None:
        """Ein Pfeil von der ersten zur zweiten Stelle."""
        colour = stroke or self.colours.ink
        self._marker(colour)
        self._body.append(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{colour}" stroke-width="{_n(weight)}"{_dash(dashed)} '
            f'marker-end="url(#{_marker_id(colour)})" />'
        )

    def dimension(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        label: str,
        *,
        offset: float = 0.0,
        stroke: str | None = None,
    ) -> None:
        """Eine Maßlinie mit Pfeilen an beiden Enden und der Zahl darüber.

        Das Element, an dem sich eine technische Skizze von einer Illustration
        unterscheidet: sie behauptet nicht, dass da ein Spiel ist, sie sagt wie
        groß.
        """
        colour = stroke or self.colours.accent
        self._marker(colour)
        marker = f"url(#{_marker_id(colour)})"
        self._body.append(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{colour}" stroke-width="1.1" marker-start="{marker}" '
            f'marker-end="{marker}" />'
        )
        middle_x = (x1 + x2) / 2.0
        middle_y = (y1 + y2) / 2.0
        # Neun Pixel, nicht fünf: bei elf Pixeln Schrifthöhe säße der Text sonst
        # auf der Maßlinie statt darüber.
        self.label(middle_x, middle_y - 9.0 + offset, label, anchor="middle", colour=colour)

    def tick(self, x: float, y: float, length: float = 6.0, *, stroke: str | None = None) -> None:
        """Ein kurzer Strich quer — das Ende einer Maßlinie sichtbar machen."""
        self.line(x, y - length / 2, x, y + length / 2, stroke=stroke or self.colours.muted)

    # --- Schrift ---

    def label(
        self,
        x: float,
        y: float,
        text: str,
        *,
        anchor: Literal["start", "middle", "end"] = "start",
        size: float = 11.0,
        colour: str | None = None,
        bold: bool = False,
    ) -> None:
        """Ein Text. Bleibt Text — deshalb übersetzbar und suchbar."""
        weight = ' font-weight="600"' if bold else ""
        self._body.append(
            f'<text x="{_n(x)}" y="{_n(y)}" fill="{colour or self.colours.ink}" '
            f'font-size="{_n(size)}" font-family="system-ui, -apple-system, '
            f'Segoe UI, sans-serif" text-anchor="{anchor}"{weight}>'
            f"{escape(text)}</text>"
        )

    def caption(
        self,
        x: float,
        y: float,
        text: str,
        *,
        size: float = 10.0,
        anchor: Literal["start", "middle", "end"] = "start",
    ) -> None:
        """Eine Nebenbemerkung im Bild — kleiner und zurückgenommen."""
        self.label(x, y, text, size=size, colour=self.colours.muted, anchor=anchor)

    def wrapped(
        self,
        x: float,
        y: float,
        text: str,
        *,
        width: int = 34,
        size: float = 10.0,
        line_height: float = 13.0,
        anchor: Literal["start", "middle", "end"] = "start",
        colour: str | None = None,
    ) -> float:
        """Mehrzeiliger Text. Gibt die Höhe zurück, damit darunter weitergeht.

        SVG bricht nicht selbst um, also wird hier nach Wörtern umbrochen. Die
        Breite ist in Zeichen angegeben und nicht in Pixeln: bei
        Proportionalschrift wäre eine Pixelbreite ohnehin geraten, und der
        Umbruch soll in beiden Sprachen halten.
        """
        line: list[str] = []
        lines: list[str] = []
        for word in text.split():
            candidate = [*line, word]
            if len(" ".join(candidate)) > width and line:
                lines.append(" ".join(line))
                line = [word]
            else:
                line = candidate
        if line:
            lines.append(" ".join(line))
        for index, content in enumerate(lines):
            self.label(x, y + index * line_height, content, size=size, anchor=anchor, colour=colour)
        return len(lines) * line_height

    # --- Ausgabe ---

    def svg(self) -> str:
        defs = "".join(self._defs.values())
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {_n(self.width)} {_n(self.height)}" '
            f'width="{_n(self.width)}" height="{_n(self.height)}">'
        )
        parts = [head]
        if defs:
            parts.append(f"<defs>{defs}</defs>")
        parts.extend(self._body)
        parts.append("</svg>")
        return "".join(parts)

    def _marker(self, colour: str) -> None:
        name = _marker_id(colour)
        self._defs[name] = (
            f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
            f'<path d="M 0 1 L 9 5 L 0 9 z" fill="{colour}" /></marker>'
        )


def _marker_id(colour: str) -> str:
    return "arrow" + colour.lstrip("#")


def _dash(dashed: bool) -> str:
    return ' stroke-dasharray="5 4"' if dashed else ""


def _n(value: float) -> str:
    """Zahlen kurz halten — ein SVG mit sechs Nachkommastellen je Punkt wird
    unnötig groß, und angezeigt wird ohnehin auf ein Pixel genau."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


# --- Körper projizieren --------------------------------------------------------------


def camera(around_degrees: float = -35.0, down_degrees: float = 25.0) -> np.ndarray:
    """Die Blickrichtung: gedreht und geneigt, wie eine Isometrie.

    Als ``object`` deklariert, weil ``numpy`` erst hier importiert wird — der
    Kern soll auch ohne die Geometrie-Zusatzpakete importierbar bleiben.
    """
    import numpy as np

    around = math.radians(around_degrees)
    down = math.radians(down_degrees)
    turn = np.array(
        [
            [math.cos(around), -math.sin(around), 0.0],
            [math.sin(around), math.cos(around), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    tilt = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(down), -math.sin(down)],
            [0.0, math.sin(down), math.cos(down)],
        ]
    )
    return np.asarray(tilt @ turn, dtype=float)


#: Ab diesem Winkel zwischen zwei Nachbarflächen wird eine Kante gezeichnet.
#: Flacher heißt: dieselbe Fläche, nur feiner vernetzt.
EDGE_ANGLE: Final = 25.0


def project(
    mesh: trimesh.Trimesh,
    size: int = THUMBNAIL,
    colour: tuple[float, float, float] | None = None,
    *,
    theme: Theme = "light",
    background: bool = False,
    edges: bool = False,
    around: float = -35.0,
    down: float = 25.0,
) -> str:
    """Ein Netz als SVG, von schräg vorn gesehen.

    ``mesh`` ist ein ``trimesh.Trimesh``. Die Dreiecke werden nach Tiefe
    sortiert und von hinten nach vorn gezeichnet — der Malerlgorithmus, der
    bei einem geschlossenen Körper genau das Richtige tut und ohne
    Tiefenpuffer auskommt.

    Mit ``edges`` kommen Kantenlinien dazu, und abgewandte Flächen fallen weg.
    Beides zusammen ist der Unterschied zwischen einem Bild und einem grauen
    Fleck: eine Rastnase besteht aus achtundzwanzig Dreiecken, und ohne Kanten
    ist auf einem schattierten Körper aus achtundzwanzig Dreiecken nichts zu
    erkennen. Für ein Vorschaubild im Katalog reicht die Schattierung, für eine
    Abbildung, an der etwas erklärt wird, nicht.

    ``around`` und ``down`` drehen die Kamera. Der Dreiviertelwinkel ist eine
    gute Vorgabe und für manche Teile die falsche: eine Mutternfalle, die man
    von schräg vorn sieht, zeigt alles außer ihrem Sechskant. Was ein Bild
    erklären soll, bestimmt, von wo es aufgenommen wird.
    """
    import numpy as np

    body = mesh
    tone = colour or PALETTES[theme].solid
    if not len(body.faces):
        return _empty(size, theme, background)

    matrix = camera(around, down)
    points = np.asarray(body.vertices, dtype=float) @ matrix.T
    normals = np.asarray(body.face_normals, dtype=float) @ matrix.T

    flat = points[:, :2]
    low, high = flat.min(axis=0), flat.max(axis=0)
    span = float(max(high - low)) or 1.0
    scale = (size - 16) / span
    offset = (np.array([size, size]) - (high - low) * scale) / 2.0

    screen = (flat - low) * scale + offset
    screen[:, 1] = size - screen[:, 1]

    light = np.array(LIGHT)
    light = light / float(np.linalg.norm(light))
    faces = np.asarray(body.faces)
    depth = points[faces, 2].mean(axis=1)
    order = np.argsort(depth)
    if edges:
        # Abgewandte Flächen weglassen. Bei einem geschlossenen Körper sind sie
        # ohnehin verdeckt; sichtbar wird nur, dass das SVG halb so groß ist.
        order = order[normals[order, 2] > 0.0]

    outlines = _edges_by_face(body, normals, depth) if edges else {}
    ink = PALETTES[theme].ink

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">'
    ]
    if background:
        lines.append(
            f'<rect x="0" y="0" width="{size}" height="{size}" fill="{PALETTES[theme].paper}" />'
        )
    for index in order:
        triangle = faces[index]
        shade = _shade(float(normals[index] @ light))
        red, green, blue = (int(255 * value * shade) for value in tone)
        fill = f"#{red:02x}{green:02x}{blue:02x}"
        corners = " ".join(f"{screen[point][0]:.1f},{screen[point][1]:.1f}" for point in triangle)
        # Der Rand in der Füllfarbe: benachbarte Dreiecke stoßen sonst mit einer
        # haarfeinen hellen Naht aneinander, weil die Kantenglättung beide
        # Ränder halbdurchsichtig zeichnet. Ein halber Pixel Überlappung
        # schließt sie, ohne dass sich die Form ändert.
        lines.append(
            f'<polygon points="{corners}" fill="{fill}" stroke="{fill}" stroke-width="0.6" />'
        )
        # Die Kanten dieser Fläche direkt danach: so verdecken spätere, weiter
        # vorn liegende Flächen die Kanten dahinter — ohne Tiefenpuffer.
        for first, second in outlines.get(int(index), ()):
            lines.append(
                f'<line x1="{screen[first][0]:.1f}" y1="{screen[first][1]:.1f}" '
                f'x2="{screen[second][0]:.1f}" y2="{screen[second][1]:.1f}" '
                f'stroke="{ink}" stroke-width="0.9" stroke-linecap="round" />'
            )
    lines.append("</svg>")
    return "\n".join(lines)


def _shade(towards_light: float) -> float:
    """Wie hell eine Fläche wird, je nachdem wie sie zum Licht steht.

    Neben dem Hauptlicht steht ein schwaches Gegenlicht. Ohne das läuft jede
    Fläche, die vom Licht wegzeigt, auf denselben dunklen Wert — bei einem Teil
    aus einer Handvoll Flächen ist das dann eine große schwarze Fläche, auf der
    nichts mehr zu erkennen ist. Ein Aufheller von hinten kostet nichts und
    hält die Form lesbar.
    """
    front = max(towards_light, 0.0)
    back = max(-towards_light, 0.0)
    return min(0.62 + 0.38 * front + 0.14 * back, 1.0)


def _edges_by_face(
    body: trimesh.Trimesh, normals: np.ndarray, depth: np.ndarray
) -> dict[int, list[tuple[int, int]]]:
    """Welche Kante an welcher Fläche gezeichnet wird.

    Gezeichnet werden zwei Sorten: **Feature-Kanten**, an denen sich die
    Richtung deutlich ändert, und **Silhouettenkanten**, an denen eine Fläche
    zur Kamera zeigt und die andere weg. Jede Kante hängt an der *vorderen*
    ihrer beiden Flächen, damit sie erst gezeichnet wird, wenn beide Flächen
    stehen — sonst überdeckte die vordere Fläche ihre eigene Kante.
    """
    import numpy as np

    pairs = np.asarray(body.face_adjacency)
    if not len(pairs):
        return {}
    shared = np.asarray(body.face_adjacency_edges)
    angles = np.degrees(np.asarray(body.face_adjacency_angles))

    towards = np.asarray(normals)[:, 2] > 0.0
    silhouette = towards[pairs[:, 0]] != towards[pairs[:, 1]]
    wanted = (angles >= EDGE_ANGLE) | silhouette

    depths = np.asarray(depth)
    front = np.where(depths[pairs[:, 0]] >= depths[pairs[:, 1]], pairs[:, 0], pairs[:, 1])

    by_face: dict[int, list[tuple[int, int]]] = {}
    for owner, edge in zip(front[wanted], shared[wanted], strict=True):
        by_face.setdefault(int(owner), []).append((int(edge[0]), int(edge[1])))
    return by_face


def _empty(size: int, theme: Theme, background: bool) -> str:
    paper = (
        f'<rect x="0" y="0" width="{size}" height="{size}" fill="{PALETTES[theme].paper}" />'
        if background
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">{paper}</svg>'
    )


def side_by_side(
    left: str,
    right: str,
    *,
    gap: int = 24,
    theme: Theme = "light",
    labels: tuple[str, str] | None = None,
) -> str:
    """Zwei Projektionen nebeneinander — das Vorher und das Nachher.

    Die beiden SVG werden eingebettet statt neu gezeichnet: sie sind bereits
    fertig, und ein zweiter Renderweg wäre einer, der anders aussehen kann als
    der erste.

    ``labels`` schreibt unter jede Hälfte, welche sie ist. Ohne das muss der
    Leser raten, welche Seite vorher war — bei einem Vorher/Nachher ist das die
    einzige Information, auf die es ankommt.
    """
    left_size = _size_of(left)
    right_size = _size_of(right)
    width = left_size + gap + right_size
    height = max(left_size, right_size) + (24 if labels else 0)
    colours = PALETTES[theme]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{colours.paper}" />',
        f"<g>{_inner(left)}</g>",
        f'<g transform="translate({left_size + gap} 0)">{_inner(right)}</g>',
    ]
    if labels:
        font = 'font-size="11" font-family="system-ui, -apple-system, Segoe UI, sans-serif"'
        baseline = height - 7
        for text, centre in (
            (labels[0], left_size / 2),
            (labels[1], left_size + gap + right_size / 2),
        ):
            parts.append(
                f'<text x="{_n(centre)}" y="{baseline}" fill="{colours.ink}" {font} '
                f'text-anchor="middle">{escape(text)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _size_of(svg: str) -> int:
    marker = 'width="'
    start = svg.index(marker) + len(marker)
    return int(float(svg[start : svg.index('"', start)]))


def _inner(svg: str) -> str:
    return svg[svg.index(">") + 1 : svg.rindex("</svg>")]


#: Wie viele Dreiecke ein Vorschaubild höchstens zeichnet.
#:
#: Gemessen an einer feinen Kugel: 82 000 Dreiecke kosten 400 ms und ergeben
#: ein SVG von acht Megabyte — für ein Bild von zwanzig Pixeln neben einem
#: Namen. Auf 600 heruntergerechnet sind es 85 ms und 59 kB, und man sieht
#: keinen Unterschied, weil bei dieser Größe keiner zu sehen ist.
PREVIEW_FACES: Final = 600


def thumbnail(
    mesh: trimesh.Trimesh,
    size: int = 48,
    *,
    theme: Theme = "light",
    subtractive: bool = False,
) -> str:
    """Ein Netz als kleines Vorschaubild — dieselbe Projektion wie überall.

    Dezimiert vorher, und das ist der ganze Unterschied zu :func:`project`:
    Ein Vorschaubild wird nach Silhouette erkannt, nicht nach Dreiecken. Wer
    ein Bild von zwanzig Pixeln aus achtzigtausend Flächen zeichnet, bezahlt
    für Genauigkeit, die kein Bildschirm zeigt.
    """
    from app.core.geom.mesh import MeshData
    from app.core.geom.mesh_ops import decimate

    small = decimate(MeshData.of(mesh), PREVIEW_FACES)
    colours = palette(theme)
    tone = colours.subtractive if subtractive else colours.solid
    return project(small.raw, size, tone, theme=theme)
