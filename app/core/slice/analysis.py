"""Der Analyse-Schneider (Bauplan §22).

Mit Absicht **kein** G-Code-Slicer. Perimeter, Nähte, Kühlung, Retraktion und
Maschinengrenzen sind fünfzehn Jahre Arbeit anderer Leute, und eine schlechtere
Antwort kostete das Vertrauen in die ganze Anwendung. Die Datei, die zum
Drucker geht, kommt weiterhin aus dem externen Slicer (§28).

Zur *Analyse* zu schneiden ist eine andere Sache, und der größere Hebel: mit
Zahlen je Schicht in Millisekunden kann die Orientierungssuche hunderte
Drehungen an echtem Stützvolumen messen statt an einer Faustregel (§22.3).

Jede Zahl hier ist ``internal``. Sie wird nie mit einer aus G-Code gemessenen
Größe vermischt (§22.5) — ein geschätztes Stützvolumen und ein gemessenes sind
verschiedene Dinge, und der Bericht sagt, welches welches ist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import shapely
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import LayerInfo, Polygon, SliceResult
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Die übersetzte Konturverkettung (§22.1), oder ``None``.
#:
#: Optional wie der B-Rep-Kern: fehlt sie, geht derselbe Schnitt über GEOS und
#: liefert dasselbe Ergebnis — nur langsamer. Gebaut wird sie mit
#: ``tools/build_slice_core.py``.
#:
#: ``Any`` und nicht der Modultyp aus ``_chain.pyi``: Die Erweiterung ist auf
#: der Maschine da oder nicht, und ``warn_unreachable`` hielte die Abfrage
#: darauf sonst für toten Code — auf genau der Maschine, auf der gerade gebaut
#: wurde. Geprüft wird die Signatur trotzdem, nämlich am Import darunter.
_chain: Any
try:
    from app.core.slice import _chain as _compiled_chain
except ImportError:  # pragma: no cover — hängt daran, ob gebaut wurde
    _chain = None
else:
    _chain = _compiled_chain

#: Der kleinste Überhang, der nicht bloß Vernetzungsrauschen ist.
OVERHANG_MARGIN = 0.05

#: Eine Schicht darf um eine Schichthöhe seitlich wachsen und bleibt
#: druckbar — das sind genau 45 Grad, der Winkel, an dem die Regelsammlung die
#: Linie zieht (§39, §18.4).
#: Nur was weiter reicht, zählt als Überhang.
OVERHANG_ANGLE_FACTOR = 1.0

#: Schritte der binären Suche nach der kleinsten Strukturbreite. Sechs
#: Halbierungen einer ohnehin engen Klammer lassen unter zwei Prozent übrig.
WIDTH_STEPS = 6

#: Wie weit die Kontur vor dieser Suche vereinfacht werden darf — ein
#: hundertstel Millimeter ist ein Zehntel dessen, was die feinste Düse
#: ablegen kann.
WIDTH_SIMPLIFY = 0.01

#: Über dieser Breite ist eine Struktur schlicht „dick" und wird nicht weiter
#: gemessen. Zwei Millimeter sind fünf Düsendurchmesser — keine Warnung in
#: §22.2 schaut darüber, und die Suche nach einem exakten Wert dort oben
#: kostete mehr als alles andere zusammen.
WIDTH_INTERESTING = 2.0

#: Ab welcher Breite eine ungestützte Fläche als Brücke zählt und nicht mehr
#: als Überhang.
#:
#: Darunter kragt die Wandlinie selbst vor und liegt zur Hälfte auf der Schicht
#: darunter — das trägt sich. Darüber muss der Slicer die Fläche füllen, und
#: dafür legt er gerade Bahnen, die er quer über die Öffnung spannt statt
#: entlang der Kontur. Ein Millimeter sind zwei Bahnen einer 0,4er-Düse; das
#: ist die Grenze, an der aus Vorkragen ein Überspannen wird.
BRIDGE_FROM = 1.0

#: Unter so vielen Schichten kostet das Auffächern mehr, als es spart — acht
#: Threads für zwanzig Polygone zu starten ist reiner Verwaltungsaufwand.
PARALLEL_FROM = 40

#: Obergrenze der Threads. Darüber sind die Schichten zu klein, um sie zu
#: füllen.
MAX_WORKERS = 8

Detail = Literal["full", "support"]
"""Wie viel einer Schicht vermessen wird. ``support`` lässt alles aus, was die
Orientierungssuche nicht liest (§28.2)."""


@dataclass(frozen=True, slots=True)
class LayerMetrics:
    """Was eine Schicht zum Urteil beiträgt (§22.2)."""

    z: float
    area: float
    overhang_area: float
    island_area: float
    min_width: float
    bridge_width: float
    contour_count: int
    overhang: ShapelyPolygon | None = None
    """Der ungestützte Bereich selbst — die Stützkarte braucht den Ort, nicht die Zahl."""


def slice_body(mesh: MeshData, layer_height: float = 0.2, detail: Detail = "full") -> SliceResult:
    """Schneidet den Körper in Schichten und misst jede (§22.1, §22.2).

    ``detail="support"`` misst nur, was die Stützen brauchen: Überhänge,
    Inseln und die Flächen. Die Orientierungssuche ruft das zweihundertmal auf
    und liest genau eine Zahl daraus (§28.2) — Strukturbreiten für einen
    Körper zu rechnen, der gleich wieder gedreht wird, ist Arbeit, die niemand
    ansieht.
    """
    if layer_height <= EPS_GEOM:
        # Kein nackter ``ValueError``: Die Schichthöhe kommt aus dem
        # Druckerprofil, und ein eigenes ``printers.toml`` bringt diesen Fall
        # bis in die Oberfläche. Dort stand ein englischer Satz ohne
        # Handlungsvorschlag (Regel 17).
        raise ValidationError(
            "layer_height",
            _("Die Schichthöhe muss größer als null sein."),
            value=layer_height,
            constraint="layer_height",
        )

    bounds = mesh.bounds
    low, high = bounds.minimum[2], bounds.maximum[2]
    if high - low <= EPS_GEOM:
        return SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")

    layers: list[LayerInfo] = []

    # Eine halbe Schicht über dem Boden: der erste Schnitt muss Material treffen.
    heights = np.arange(low + layer_height / 2.0, high, layer_height)
    if not len(heights):
        # Ist das Teil dünner als eine halbe Schichthöhe, liegt ``low +
        # layer_height/2`` schon über ``high``, und ``arange`` bleibt leer.
        # Ohne Schnitt gäbe es keine Schicht und ``first_layer_area`` fiele auf
        # 0 — für die Orientierungssuche fatal: Sie verwirft jede Lage mit 0 mm²
        # Grundfläche (§22.3). So wurde eine liegende 0,4-mm-Karte 54 mm
        # hochkant gestellt, weil bei der groben Suchschichthöhe (1,0 mm) nur die
        # hochkante Lage überhaupt eine nicht-leere Schichtliste hatte. Ein Teil
        # oberhalb von EPS_GEOM ist genau eine gedruckte Lage; ihr Schnitt liegt
        # in der Mitte, wo er sicher Material trifft.
        heights = np.array([(low + high) / 2.0], dtype=float)
    sections = cross_sections(mesh, heights)
    measured = _measure_all(sections, layer_height, detail)
    support = _support_volume(sections, measured, layer_height)

    previous: ShapelyPolygon | None = None
    for z, shape, metrics in zip(heights, sections, measured, strict=True):
        if shape is None or shape.is_empty or metrics is None:
            previous = None
            continue

        layers.append(
            LayerInfo(
                z=float(z),
                contours=_to_polygons(shape),
                area=metrics.area,
                overhang_area=metrics.overhang_area,
                islands=()
                if metrics.island_area <= EPS_GEOM
                else _to_polygons(_islands(shape, previous)),
                min_width=metrics.min_width,
                overhangs=()
                if metrics.overhang is None or metrics.overhang.is_empty
                else _to_polygons(metrics.overhang),
                bridge_width=metrics.bridge_width,
            )
        )
        previous = shape

    return SliceResult(
        layers=tuple(layers),
        support_volume=float(support),
        first_layer_area=layers[0].area if layers else 0.0,
        source="internal",
    )


def _support_volume(
    sections: list[ShapelyPolygon | None],
    measured: list[LayerMetrics | None],
    layer_height: float,
) -> float:
    """Das Volumen der **Stützsäulen** unter allen Überhängen, in mm³ (§22.2).

    Gerechnet wurde hier ``Überhangfläche mal Schichthöhe``, aufsummiert. Das ist
    das Volumen der auskragenden **Schale** — des Materials, das der Drucker
    dort oben ablegt — und nicht das, was eine Stütze kostet. Zwei Dinge waren
    daran falsch, und das zweite ist das schlimmere: Die Zahl war an einem Pilz
    (Hut 40 auf 40 über einem Stiel 10 auf 10, 20 mm hoch) um den Faktor 380 zu
    klein, **und** sie hing an der Schichthöhe: 79 mm³ bei 0,2 mm, 385 bei 1,0.
    Eine Eigenschaft des Körpers, die sich mit der Auflösung ändert, mit der man
    sie misst, ist keine.

    Gestützt wird der Raum **unter** dem Überhang, bis zum nächsten Material
    oder bis zur Platte. Gerechnet wird das in einem Durchgang von oben nach
    unten: ``pending`` ist die Fläche, die auf dieser Höhe noch von unten
    getragen werden muss. Sie wächst um den Überhang jeder Schicht und schrumpft
    um alles, was die Schicht darunter an Material bietet — je Schichtabstand
    kommt ihre Fläche mal der Fallhöhe dazu. Damit ist das Ergebnis von der
    Schichthöhe unabhängig: halb so hohe Schichten sind doppelt so viele.

    **Unter der untersten Schicht bleibt eine halbe Schichthöhe.** Der erste
    Schnitt liegt eine halbe Schicht über der Unterkante des Körpers, und ob
    dort die Platte steht, weiß der Schneider nicht — er kennt nur den Körper.
    Der Term geht mit der Schichthöhe gegen null und ist damit kein Beitrag,
    der eine Aussage trägt.

    **Die Säulen werden nie vereinigt, und das ist der Unterschied zwischen
    37 Millisekunden und 6,7 Sekunden.** Sie können sich nicht überschneiden:
    Ein Überhang gehört zum Material seiner eigenen Schicht, und was von oben
    kommt, ist eine Schicht vorher an genau diesem Material zerteilt worden.
    Der erste Anlauf rief trotzdem ``unary_union`` — an einer Kugel mit
    327 000 Dreiecken kostete das 33 ms je Schicht, weil das Verschneiden
    hunderter schmaler Ringe genau die Arbeit ist, die eine Vereinigung teuer
    macht. Gehalten wird deshalb eine **Liste** überschneidungsfreier Teile;
    ihre Flächen addieren sich, und der räumliche Index sagt in einem Aufruf,
    welche davon die Schicht darunter überhaupt berührt. Beide Wege ergeben
    dieselbe Zahl (4016,6 mm³ an derselben Kugel), einer davon in einem
    Hundertachtzigstel der Zeit.
    """
    pending: list[ShapelyPolygon] = []
    volume = 0.0
    for index in range(len(sections) - 1, -1, -1):
        metrics = measured[index]
        region = None if metrics is None else metrics.overhang
        if region is not None and not region.is_empty:
            pending += _areas_of(region)
        if not pending:
            continue
        below = sections[index - 1] if index else None
        if below is not None and not below.is_empty:
            pending = _above_material(pending, below)
            if not pending:
                continue
        volume += float(shapely.area(np.asarray(pending, dtype=object)).sum()) * (
            layer_height if index else layer_height / 2.0
        )
    return volume


def _areas_of(shape: ShapelyPolygon) -> list[ShapelyPolygon]:
    """Die flächigen Teile einer Geometrie, einzeln.

    Eine Differenz kann Linien zurückgeben, wo zwei Flächen sich nur berühren.
    Die tragen keine Fläche und keine Säule.
    """
    parts = getattr(shape, "geoms", [shape])
    return [part for part in parts if part.geom_type == "Polygon" and not part.is_empty]


def _above_material(pending: list[ShapelyPolygon], below: ShapelyPolygon) -> list[ShapelyPolygon]:
    """Was von den Säulen übrig bleibt, wenn die Schicht darunter trägt.

    Geschnitten wird nur, was sich überhaupt berührt, und gefragt wird das
    **vektorisiert**: ein Aufruf über alle Teile, nicht einer je Teil. Ein
    räumlicher Index stand hier zuerst und war die schlechtere Wahl — er will
    je Schicht neu gebaut werden, und bei hundert Teilen kostet der Bau mehr
    als die Fragen, die er spart. An der Orientierungssuche über 200
    Kandidaten gemessen: 27,4 s mit Baum, 19,1 s ohne.
    """
    parts = np.asarray(pending, dtype=object)
    touching = np.nonzero(shapely.intersects(parts, below))[0].tolist()
    if not touching:
        return pending
    hit = set(touching)
    kept = [part for number, part in enumerate(pending) if number not in hit]
    for number in touching:
        kept += _areas_of(pending[number].difference(below))
    return kept


def _measure_all(
    sections: list[ShapelyPolygon | None], layer_height: float, detail: Detail
) -> list[LayerMetrics | None]:
    """Misst jede Schicht, auf so vielen Threads wie die Maschine hat.

    Das ist einen Absatz wert. Eine Schicht wird gegen die darunter gemessen,
    die Schleife *sieht* also sequenziell aus — aber das Paar ist alles, was
    sie braucht, und die Paare stehen fest, sobald die Schnitte gemacht sind.
    Also fächert die Arbeit auf.

    Threads, keine Prozesse: gemessen wird in GEOS, und GEOS gibt den
    Interpreter-Lock frei, während es arbeitet. Gemessen an einem Körper mit
    328 000 Dreiecken: 0,81 s auf einem Thread, 0,15 s auf acht. Prozesse
    müssten jedes Polygon zweimal kopieren und wären langsamer als die
    sequenzielle Schleife.

    ``on_plate`` ist das eine, womit das Auffächern vorsichtig sein muss: die
    erste Schicht mit Material liegt auf der Platte und braucht keine Stütze.
    Die erste nach einer **Lücke** braucht sehr wohl eine — sie beginnt in der
    Luft, und genau das ist eine Insel (:func:`_islands`); ``on_plate`` gilt
    deshalb nur der untersten Schicht des Körpers. Das wird hier entschieden,
    bevor irgendetwas beginnt.
    """
    from concurrent.futures import ThreadPoolExecutor

    jobs: list[tuple[int, ShapelyPolygon, ShapelyPolygon | None, bool]] = []
    previous: ShapelyPolygon | None = None
    on_plate = True
    for index, shape in enumerate(sections):
        if shape is None or shape.is_empty:
            previous = None
            continue
        jobs.append((index, shape, previous, on_plate))
        previous = shape
        on_plate = False

    results: list[LayerMetrics | None] = [None] * len(sections)
    if not jobs:
        return results
    if len(jobs) < PARALLEL_FROM:
        for index, shape, below, plate in jobs:
            results[index] = _measure(shape, below, plate, layer_height, detail)
        return results

    def one(job: tuple[int, ShapelyPolygon, ShapelyPolygon | None, bool]) -> None:
        index, shape, below, plate = job
        results[index] = _measure(shape, below, plate, layer_height, detail)

    with ThreadPoolExecutor(max_workers=_workers()) as pool:
        list(pool.map(one, jobs))
    return results


def _workers() -> int:
    """Ein Thread je Kern, in Maßen. Mehr fügt nur Umschalten hinzu."""
    import os

    return max(1, min(MAX_WORKERS, (os.cpu_count() or 2)))


def cross_section(mesh: MeshData, z: float) -> ShapelyPolygon | None:
    """Eine Ebene durch das Netz, als Polygon mit Löchern (§22.1).

    Öffentlich, weil die Analysekarten den Körper aus diesen Schnitten rastern
    (§18.4) — derselbe Schnitt, zweimal benutzt.
    """
    return cross_sections(mesh, np.array([z], dtype=float))[0]


def cross_sections(mesh: MeshData, heights: Any) -> list[ShapelyPolygon | None]:
    """Viele Ebenen auf einmal — der Grund, warum die Schichtanalyse
    überhaupt brauchbar ist.

    Ebene für Ebene zu schneiden heißt, jedes Dreieck für jede Schicht
    abzulaufen, und ein Körper aus zweihunderttausend Dreiecken in
    vierhundert Schichten läuft achtzig Millionen davon ab. Hier wird jedes
    Dreieck in die Schichten einsortiert, die seine eigene Höhe erreicht —
    jede Schicht sieht also nur, was sie wirklich kreuzt.

    Die Koordinaten bleiben auf jeder Höhe X und Y der Welt. Das ist kein
    Detail: eine Schicht mit der darunter zu vergleichen bedeutet nur etwas,
    wenn beide auf dieselbe Karte gezeichnet sind.
    """
    heights = np.asarray(heights, dtype=float)
    empty: list[ShapelyPolygon | None] = [None] * len(heights)
    if not len(heights) or not len(mesh.raw.faces):
        return empty

    points, layers, nodes = _plane_segments(mesh, heights)
    if not len(points):
        return empty

    order = np.argsort(layers, kind="stable")
    points, layers, nodes = points[order], layers[order], nodes[order]
    starts = np.searchsorted(layers, np.arange(len(heights)), side="left")
    ends = np.searchsorted(layers, np.arange(len(heights)), side="right")

    # Probiert und wieder herausgenommen: diese Schleife über Threads
    # aufzufächern, wie ``_measure_all`` es tut, machte sie langsamer — 0,758 s
    # gegen 0,714 s an einem Körper mit 328 000 Dreiecken. Ein Polygon nach dem
    # anderen zu bauen hält den Interpreter-Lock, anders als die vektorisierten
    # Prädikate, die das Messen benutzt — übrig bleibt also nur der Aufwand,
    # vierhundert kleine Aufträge herumzureichen. Die Messung steht hier, damit
    # niemand den Nachmittag noch einmal verbringt.
    #
    # Mit ``_chain`` gilt der Grund nicht mehr: die Verkettung gibt den Lock
    # frei. Aufgefächert wird trotzdem nicht — sie kostet dann 11 ms für alle
    # vierhundert Schichten, und das Herumreichen der Aufträge wäre wieder
    # teurer als die Arbeit (gemessen: 23 ms auf vier Threads).
    result: list[ShapelyPolygon | None] = []
    for start, end in zip(starts, ends, strict=True):
        result.append(_polygon_from(points[start:end], nodes[start:end]) if end > start else None)
    return result


def _plane_segments(mesh: MeshData, heights: Any) -> tuple[Any, Any, Any]:
    """Wo jedes Dreieck jede Ebene kreuzt, die es erreicht.

    Liefert die Segmente als ``(n, 2, 2)`` Punkte in XY, die Schicht, zu der
    jedes gehört, und je Segmentende die **Kante**, auf der es liegt.
    ``heights`` muss aufsteigend sein; der Abstand darf beliebig sein.

    Die Kantennummer ist die eigentliche Identität eines Schnittpunkts, und
    zwar eine exakte: Eine Kante gehört in einem geschlossenen Netz genau zwei
    Dreiecken, beide schneiden sie an derselben Stelle, und beide bekommen
    damit dieselbe Nummer. Wer die Enden stattdessen über ihre gerundeten
    Koordinaten zusammenführt, rechnet dieselbe Auskunft aus Fließkommazahlen
    nach — teurer und angreifbarer (siehe den Absatz zur kanonischen
    Kantenrichtung weiter unten).
    """
    triangles = np.asarray(mesh.raw.triangles, dtype=float)

    vertical = triangles[:, :, 2]
    # Welche Ebenen ein Dreieck erreicht, nachgeschlagen statt aus einem
    # Abstand gerechnet: die Schichtanalyse fragt nach gleichmäßigen Höhen, die
    # Trennebenensuche (§22.3) nicht — und Arithmetik auf einem angenommenen
    # Schritt gibt diesem zweiten Aufrufer still leere Schichten.
    first = np.searchsorted(heights, vertical.min(axis=1) - EPS_GEOM, side="left")
    last = np.searchsorted(heights, vertical.max(axis=1) + EPS_GEOM, side="right") - 1
    np.clip(first, 0, len(heights) - 1, out=first)
    np.clip(last, 0, len(heights) - 1, out=last)
    counts = np.maximum(last - first + 1, 0)
    counts[vertical.min(axis=1) > heights[-1]] = 0
    counts[vertical.max(axis=1) < heights[0]] = 0
    if not counts.sum():
        return _no_segments()

    faces = np.repeat(np.arange(len(triangles)), counts)
    within = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
    layers = np.repeat(first, counts) + within
    z = heights[layers]

    corners = triangles[faces]
    height_above = corners[:, :, 2] - z[:, None]
    # Die drei Kanten eines Dreiecks, als „von Ecke i nach Ecke i+1".
    above = height_above > 0.0
    crossing = above != above[:, [1, 2, 0]]

    keep = crossing.sum(axis=1) == 2
    if not keep.any():
        return _no_segments()

    corners, height_above, crossing = corners[keep], height_above[keep], crossing[keep]
    rows = np.arange(len(corners))[:, None]
    # Die zwei kreuzenden Kanten, in der Reihenfolge, in der das Dreieck sie
    # benennt.
    #
    # **Ohne Sortierung.** ``keep`` hat gerade dafür gesorgt, dass jede Zeile
    # genau zwei Kreuzungen trägt — und wo die Zahl feststeht, ist ein Sort über
    # drei Spalten Arbeit für nichts: ``nonzero`` gibt die Spalten zeilenweise
    # aufsteigend zurück, also dasselbe Ergebnis. Gemessen an 600 000 Zeilen:
    # 50,9 ms mit ``argsort``, 11,5 ms so. Auf dem Netz des Leistungstests
    # (328 000 Dreiecke, 0,2 mm) sind das rund drei Prozent der ganzen
    # Schichtanalyse — nicht die Rettung des §31-Ziels, aber der billigste Teil
    # davon.
    edges = np.nonzero(crossing)[1].reshape(-1, 2)

    start = corners[rows, edges]
    end = corners[rows, (edges + 1) % 3]
    start_height = height_above[rows, edges]
    end_height = height_above[rows, (edges + 1) % 3]

    # Jede Kante gehört zwei Dreiecken, und jedes benennt sie in seiner eigenen
    # Richtung. ``A + (B-A)*f`` und ``B + (A-B)*f'`` sind dieselbe Stelle —
    # aber nicht dasselbe Fließkommamuster, und der Unterschied wächst, je
    # näher die Ebene an einer Ecke liegt. Zwei Enden, die sich um mehr als die
    # sechste Nachkommastelle unterscheiden, führt das Runden in
    # :func:`_polygon_from` nicht mehr zusammen: der Ring bleibt offen,
    # ``polygonize`` lässt ihn fallen, und ein Fach verschwindet als Loch aus
    # der Schicht. Gemessen an einem Behälter mit drei Fächern: 31 von 800
    # Schichten meldeten die fünffache Querschnittsfläche und daraus 9 463 mm²
    # Überhang, den es nicht gibt — genug, dass die Beratung Stützen für einen
    # Kasten mit senkrechten Wänden vorschlug.
    #
    # Also wird jede Kante kanonisch orientiert, bevor interpoliert wird: von
    # der lexikografisch kleineren Ecke zur größeren. Beide Dreiecke rechnen
    # damit denselben Ausdruck und bekommen bitgleich denselben Punkt.
    swap = _lexicographically_after(start, end)
    start, end = np.where(swap[..., None], end, start), np.where(swap[..., None], start, end)
    start_height, end_height = (
        np.where(swap, end_height, start_height),
        np.where(swap, start_height, end_height),
    )

    span = start_height - end_height
    fraction = np.where(
        np.abs(span) > EPS_GEOM, start_height / np.where(span == 0.0, 1.0, span), 0.0
    )
    points = start[:, :, :2] + (end[:, :, :2] - start[:, :, :2]) * fraction[:, :, None]

    # Dieselbe Auswahl noch einmal, aber auf den Kanten. Die Nummer wird
    # gerechnet, nicht nachgeschlagen: ``kleinere Ecke * Eckenzahl + größere``
    # ist für dieselbe Kante in beiden Dreiecken dieselbe Zahl, weil beide
    # dieselben zwei Eckennummern nennen. Spalte i ist dabei die Kante „von
    # Ecke i nach Ecke i+1" — die Zählweise, nach der ``edges`` gebildet wurde.
    #
    # ``mesh.raw.faces_unique_edges`` gäbe dieselbe Auskunft, baut dafür aber
    # eine Kantentabelle über das ganze Netz: 467 ms auf einem Körper mit
    # 327 680 Dreiecken, gegen 16 ms hier. Beim einmaligen Schneiden ist das
    # der Unterschied zwischen schneller und langsamer als vorher.
    #
    # Gerechnet wird nur für die zwei kreuzenden Kanten, nicht für alle drei:
    # ein Drittel weniger Arbeit, und das Zwischenfeld über alle Ecken
    # entsteht gar nicht erst.
    corner_ids = np.asarray(mesh.raw.faces, dtype=np.int64)[faces[keep]]
    corner_from = corner_ids[rows, edges]
    corner_to = corner_ids[rows, (edges + 1) % 3]
    nodes = np.minimum(corner_from, corner_to) * len(mesh.raw.vertices) + np.maximum(
        corner_from, corner_to
    )
    return points, layers[keep], nodes


def _no_segments() -> tuple[Any, Any, Any]:
    """Die leere Antwort von :func:`_plane_segments`, an einer Stelle."""
    return np.empty((0, 2, 2)), np.empty(0, dtype=np.int64), np.empty((0, 2), dtype=np.int64)


def _lexicographically_after(first: Any, second: Any) -> Any:
    """Wo ``first`` in der Reihenfolge (x, y, z) hinter ``second`` liegt.

    Verglichen wird exakt, nicht auf Toleranz: beide Ecken stammen aus
    derselben Punktliste des Netzes, sind für dieselbe Ecke also bitgleich.
    Eine Toleranz würde hier nur zwei benachbarte Ecken verwechseln.
    """
    delta_x = first[..., 0] - second[..., 0]
    delta_y = first[..., 1] - second[..., 1]
    delta_z = first[..., 2] - second[..., 2]
    return (delta_x > 0.0) | (
        (delta_x == 0.0) & ((delta_y > 0.0) | ((delta_y == 0.0) & (delta_z > 0.0)))
    )


def _rings_from(points: Any, nodes: Any) -> tuple[Any, Any] | None:
    """Die geschlossenen Ringe einer Schicht, aus den Kantennummern verkettet.

    Ein Schnittpunkt gehört genau einer Kante, und eine Kante genau zwei
    Dreiecken. Damit trägt jeder Knoten genau zwei Segmente, und die Ringe
    sind schlicht die Zyklen dieser Zuordnung — kein Noden, keine
    Fließkommaentscheidung, keine Toleranz.

    ``None`` heißt „nicht hier entschieden" und hat zwei Gründe. Der erste:
    ``_chain`` ist nicht gebaut. Der Weg lohnt sich nur übersetzt — als
    Python-Schleife kostet derselbe Durchlauf 608 ms, wo GEOS für die
    schwerere Aufgabe 826 ms braucht, und die Verkettung wäre ein Umbau ohne
    Gewinn. Der zweite: Die Voraussetzung trägt nicht, weil ein Knoten einen
    Grad ungleich zwei hat — eine offene Kante im Netz, oder eine Ebene genau
    durch eine Ecke. Dann ist GEOS die richtige Antwort, denn es kommt auch
    mit dem zurecht, was hier nicht mehr eindeutig ist.

    Zurück kommen die Koordinaten in Ringreihenfolge und je Koordinate die
    Nummer ihres Rings — genau die Form, die ``shapely.linearrings`` erwartet.
    """
    if _chain is None:
        return None

    ends = np.asarray(nodes, dtype=np.int64).reshape(-1)
    if len(ends) < 6:
        return None

    # Knotennummern dicht machen: die Kantennummer ist aus Eckennummern
    # gerechnet und damit beliebig groß; ``bincount`` darüber wäre je Schicht
    # ein Feld über das Quadrat der Eckenzahl.
    unique, dense = np.unique(ends, return_inverse=True)
    dense = np.ascontiguousarray(np.asarray(dense, dtype=np.int64).reshape(-1, 2))

    degree = np.bincount(dense.reshape(-1), minlength=len(unique))
    if degree.min() != 2 or degree.max() != 2:
        return None

    # Je Knoten die beiden Segmente, die an ihm hängen. ``argsort`` über die
    # Knotennummern legt die beiden Vorkommen nebeneinander.
    order = np.argsort(dense.reshape(-1), kind="stable")
    incident = np.ascontiguousarray((order // 2).reshape(-1, 2))

    walk = np.empty(len(dense), dtype=np.int64)
    ring_of = np.empty(len(dense), dtype=np.int64)
    rings, written = _chain.chain_rings(dense, incident, walk, ring_of)
    if rings < 1:
        return None

    # Gerundet wird trotzdem — auf dieselben sechs Stellen wie der GEOS-Weg.
    #
    # Zum Schließen der Ringe braucht es das hier nicht mehr; die Identität
    # kommt aus der Kante. Aber ungerundet käme aus demselben Körper ein um
    # 10⁻⁹ anderer Querschnitt heraus, und das bleibt nicht folgenlos:
    # `compensate_elephant_foot` zieht ihn mit `buffer` ein, extrudiert die
    # Differenz und schneidet sie ab — und eine Boolesche Operation macht aus
    # einer Abweichung in der neunten Stelle eine andere Topologie. Gemessen an
    # einem ausgehöhlten Quader: 17 erkannte Merkmale statt 14, darunter ein
    # Stift, den es nicht gibt.
    #
    # Zwei Wege durch dieselbe Rechnung dürfen sich nicht in der letzten
    # Stelle unterscheiden. Der übersetzte ist der schnellere, nicht der
    # genauere — und das ist Absicht.
    return np.round(points.reshape(-1, 2), 6)[walk[:written]], ring_of[:written]


def _polygon_from(points: Any, nodes: Any) -> ShapelyPolygon | None:
    """Baut die gefüllte Fläche einer Schicht aus ihren losen Segmenten.

    Zuerst über die Kantennummern verkettet (:func:`_rings_from`); trägt deren
    Voraussetzung nicht, schließt GEOS die Ringe selbst aus den gerundeten
    Koordinaten. Beide Wege enden an derselben Stelle: Zurück kommen Ringe,
    keine Flächen — ein Außenring und der Ring einer Bohrung sehen gleich aus.
    Was was ist, folgt daraus, wie tief ein Ring in den anderen sitzt — gerade
    ist Material, ungerade ein Loch.
    """
    chained = _rings_from(points, nodes)
    if chained is not None:
        coordinates, ring_of = chained
        edges = shapely.linearrings(coordinates, indices=ring_of)
    else:
        rounded = np.round(points.reshape(-1, 2), 6)
        lengths = np.linalg.norm(rounded[1::2] - rounded[0::2], axis=1)
        usable = np.repeat(lengths > 0.0, 2)
        if not usable.any():
            return None
        kept = rounded[usable]
        edges = shapely.linestrings(kept, indices=np.repeat(np.arange(len(kept) // 2), 2))

    built = shapely.polygonize(edges)
    parts = [part for part in getattr(built, "geoms", []) if not part.is_empty]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]

    # Nur die Außenlinien zählen als Behälter. GEOS gibt die Bohrung einer
    # Platte zweimal zurück — einmal als Loch der Platte und einmal als
    # eigene Scheibe — und zu fragen, ob die Scheibe in der *Platte* liegt,
    # antwortete Nein, denn in der Platte ist die Bohrung ein Loch.
    #
    # Was gefragt wird, muss dagegen ein Punkt des Teils selbst sein, nicht
    # seiner Außenlinie: bei einer Box ist die Außenlinie das äußere
    # Rechteck, und dessen Mitte liegt im Hohlraum. Von dort genommen
    # erklären Wand und Hohlraum einander zum jeweiligen Loch, beide kommen
    # ungerade heraus, und ein Schnitt, den es offensichtlich gibt, kommt
    # als gar nichts zurück.
    shells = [ShapelyPolygon(part.exterior) for part in parts]
    samples = [part.representative_point() for part in parts]
    # Wer in wem liegt, beantwortet ein räumlicher Index in einem Aufruf.
    # Paarweise gefragt („liegt Punkt i in Hülle j?") sind es n² einzelne
    # Prädikate durch den Python-Umweg — eine Rändel-Schicht mit 2 898 Ringen
    # stellte die Frage 8,4 Millionen Mal und brauchte dafür knapp zwei
    # Sekunden, je Schicht. Der Baum liefert dieselben Paare in Millisekunden.
    inside: list[list[int]] = [[] for _ in shells]
    if shells:
        held, holder = shapely.STRtree(shells).query(samples, predicate="within")
        for index, container in zip(held.tolist(), holder.tolist(), strict=True):
            # Der Musterpunkt eines Teils liegt immer auch in dessen eigener
            # Hülle — das Teil ist sein eigener Behälter aber nicht.
            if index != container:
                inside[index].append(container)
    solids = []
    for index, containers in enumerate(inside):
        if len(containers) % 2:
            continue
        holes = [
            shells[other].exterior
            for other, others in enumerate(inside)
            if len(others) == len(containers) + 1 and index in others
        ]
        solids.append(_repaired(ShapelyPolygon(shells[index].exterior, holes)))
    if not solids:
        return None
    return unary_union(solids)


def _repaired(shape: ShapelyPolygon) -> ShapelyPolygon:
    """Ein Ring und sein Loch dürfen sich berühren, und dann ist das Polygon
    ungültig.

    Echte Modelle tun das: eine Tasche, die exakt bis an die Außenwand reicht,
    lässt ein Loch, dessen Rand die Hülle in einem Punkt trifft. GEOS baut das
    Polygon ohne Klage und wirft bei der nächsten Operation darüber — also wird
    hier repariert statt drei Aufrufebenen weiter, wo die Meldung eine
    Koordinate nennte und sonst nichts.

    ``buffer(0)`` ist die Reparatur, weil die gesuchte Antwort eine Fläche ist:
    es lässt die entartete Naht fallen und behält das Material.
    """
    return shape if shape.is_valid else shape.buffer(0)


def _measure(
    shape: ShapelyPolygon,
    previous: ShapelyPolygon | None,
    on_plate: bool = False,
    layer_height: float = 0.2,
    detail: Detail = "full",
) -> LayerMetrics:
    area = float(shape.area)
    region: ShapelyPolygon | None = None
    if on_plate:
        # Auf der Druckplatte aufzuliegen ist die eine Stützart, die nichts kostet.
        overhang = 0.0
        islands = 0.0
    elif previous is None or previous.is_empty:
        overhang = area
        islands = area
        region = shape
    else:
        reach = max(layer_height * OVERHANG_ANGLE_FACTOR, OVERHANG_MARGIN)
        supported = previous.buffer(reach)
        region = shape.difference(supported)
        overhang = float(region.area)
        islands = float(_islands(shape, previous).area)

    if detail == "support":
        # Alles darunter geht um die gedruckte Struktur, nicht um Stützen.
        return LayerMetrics(
            z=0.0,
            area=area,
            overhang_area=overhang,
            island_area=islands,
            min_width=0.0,
            bridge_width=0.0,
            contour_count=0,
            overhang=region,
        )

    return LayerMetrics(
        z=0.0,
        area=area,
        overhang_area=overhang,
        island_area=islands,
        min_width=minimum_width(shape),
        bridge_width=_bridge_width(shape, previous),
        contour_count=_contour_count(shape),
        overhang=region,
    )


def _islands(shape: ShapelyPolygon, previous: ShapelyPolygon | None) -> ShapelyPolygon:
    """Konturen ohne Verbindung nach unten — die brauchen Stützen,
    immer (§22.2).

    **Getragen wird, was eine Fläche gemeinsam hat.** Hier stand
    ``intersects``, und das ist auch bei einer Berührung wahr — bei einer
    Überlappung von exakt null. Zwei Konturen, die sich in einer Kante oder
    einer Ecke treffen, galten damit als verbunden; der obere Teil liegt dann
    auf einer Linie ohne Breite und fällt im Druck ab. Eine Lücke von einem
    hundertstel Millimeter wurde dagegen richtig gemeldet — die Erkennung war
    also genauer beim Getrennten als beim Berührenden.

    Der Fall ist keiner aus dem Testkörper: Eine Sanduhr, eine Pyramide auf
    der Spitze, zwei Kegel Spitze an Spitze — überall verjüngt sich der
    Querschnitt auf einen Punkt, und darüber beginnt neues Material.

    Die Grenze ist ``EPS_GEOM`` und keine eigene Zahl (Regel 7). Sie steht auf
    der Fläche, nicht auf einer Länge: Zwei Konturen mit weniger als einem
    Quadrat von EPS_GEOM Kantenlänge gemeinsam berühren sich, statt zu tragen.
    """
    if previous is None or previous.is_empty:
        return shape
    parts = getattr(shape, "geoms", [shape])
    floating = [part for part in parts if part.intersection(previous).area <= EPS_GEOM * EPS_GEOM]
    return unary_union(floating) if floating else ShapelyPolygon()


def minimum_width(shape: ShapelyPolygon, interesting_below: float = WIDTH_INTERESTING) -> float:
    """Die kleinste Strukturbreite, gefunden durch Erodieren, bis nichts mehr
    übrig ist.

    Prüfbar gegen den Düsendurchmesser, und dafür ist sie da (§22.2).

    Drei Freiheiten werden fürs Tempo genommen, und keine davon ändert eine
    Antwort, auf die jemand handelt. Die Kontur wird zuerst um einen
    hundertstel Millimeter vereinfacht, und die Erosion benutzt gefaste statt
    gerundeter Ecken — beides bleibt weit unter dem, was ein Drucker auflöst.
    Und eine Schicht, die eine Erosion um die Hälfte von ``interesting_below``
    übersteht, wird als genau diese Breite gemeldet und nicht weiter gemessen:
    ob eine Wand vier oder neun Millimeter dick ist, fragt der Bericht nicht,
    und die Suche danach kostete mehr als der Rest der Analyse zusammen.
    """
    if shape.is_empty or shape.length <= EPS_GEOM:
        return 0.0
    coarse = shape.simplify(WIDTH_SIMPLIFY)
    if coarse.is_empty:
        coarse = shape
    # Die doppelte Fläche über dem Umfang ist der größte Kreis, der überhaupt
    # hineinpasst — bei einer Scheibe und bei einem Quadrat ist es genau der
    # einbeschriebene. Dort zu beginnen statt bei der Diagonale hält jeden
    # Versuch klein, und eine kleine Erosion auf einer vereinfachten Kontur ist
    # das, was das hier überhaupt bezahlbar macht.
    high = 2.0 * float(shape.area) / float(shape.length)
    if interesting_below > 0.0:
        if high <= interesting_below / 2.0:
            # Dicker kann sie ohnehin nicht sein; jetzt ordentlich messen.
            pass
        elif not coarse.buffer(-interesting_below / 2.0, quad_segs=1, join_style="mitre").is_empty:
            return float(interesting_below)
        else:
            high = min(high, interesting_below / 2.0)

    low = 0.0
    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        if coarse.buffer(-middle, quad_segs=1, join_style="mitre").is_empty:
            high = middle
        else:
            low = middle
    return float(low * 2.0)


def _bridge_width(shape: ShapelyPolygon, previous: ShapelyPolygon | None) -> float:
    """Die längste freie Spannweite dieser Schicht — was überbrückt werden
    muss (§22.2).

    Zwei Fragen, in dieser Reihenfolge. Erst: ist die ungestützte Fläche
    überhaupt breiter als zwei Bahnen? Ein Kegel unter 45 Grad legt je Schicht
    einen halben Millimeter frei, und der trägt sich selbst — das ist ein
    Überhang und keine Brücke. Dann: wie weit hängen die Bahnen frei?

    Das ist nicht die Ausdehnung der ungestützten Fläche. Eine Ringschulter um
    eine Öffnung ist selbst nur drei Millimeter breit; frei hängt eine Bahn
    über der **Öffnung**, die sie umschließt. Genau diese Zahl war beim
    Gewürzbehälter der Schaden: eine 3-mm-Schulter, deren Bahnen 24 mm frei
    quer über den Becher liefen.

    **Und es ist auch nicht die längere Seite des Hüllrechtecks.** Gemessen
    wurde die größere Ausdehnung der Öffnung, und damit stand über einem
    Kabelkanal von 30 auf 8 mm eine Brücke von 30 mm im Bericht. Der Slicer
    legt seine Bahnen quer über die **schmale** Seite — acht Millimeter, die
    jede Düse überspannt. Gefragt ist die kürzeste freie Weite, und die misst
    :func:`minimum_width` ohnehin schon, nur zwei Funktionen weiter oben:
    erodieren, bis nichts mehr übrig ist. Ohne Deckel gerufen
    (``interesting_below=0.0``), denn hier ist die Zahl selbst die Antwort und
    nicht die Frage „dünner als eine Bahn?".
    """
    if previous is None or previous.is_empty:
        return 0.0
    free = shape.difference(previous.buffer(OVERHANG_MARGIN))
    # Brücken werden gegen die Schicht selbst gemessen, nicht gegen die
    # 45-Grad-Zugabe: was durch freie Luft spannt, ist eine Brücke, egal in
    # welchem Winkel.
    if free.is_empty:
        return 0.0
    # Eine einzelne Erosion statt einer Suche: gefragt ist nicht, wie breit die
    # Fläche ist, sondern ob sie über der Grenze liegt.
    if free.buffer(-BRIDGE_FROM / 2.0, quad_segs=1, join_style="mitre").is_empty:
        return 0.0

    widest = 0.0
    for part in getattr(free, "geoms", [free]):
        if part.is_empty or not hasattr(part, "exterior"):
            continue
        # Umschließt der ungestützte Bereich eine Öffnung, ist deren Weite die
        # freie Spannweite; ist er selbst eine Fläche (eine Decke über einem
        # Hohlraum), zählt seine eigene.
        spans = [ShapelyPolygon(ring) for ring in part.interiors] or [part]
        for span in spans:
            widest = max(widest, minimum_width(span, interesting_below=0.0))
    return float(widest)


def _contour_count(shape: ShapelyPolygon) -> int:
    return len(getattr(shape, "geoms", [shape]))


def _to_polygons(shape: ShapelyPolygon) -> tuple[Polygon, ...]:
    """Shapely zum eigenen Konturtyp des Kerns — der Kern behält sein eigenes
    Vokabular.
    """
    if shape.is_empty:
        return ()
    parts = getattr(shape, "geoms", [shape])
    return tuple(
        Polygon(
            outline=_ring(part.exterior),
            holes=tuple(_ring(ring) for ring in part.interiors),
        )
        # Eine Differenz kann Linien zurückgeben, wo zwei Flächen sich nur
        # berühren. Die tragen keine Fläche, sind also keine Konturen — sie
        # wegzulassen hält den Typ ehrlich.
        for part in parts
        if not part.is_empty and part.geom_type == "Polygon"
    )


def _ring(ring: Any) -> tuple[tuple[float, float], ...]:
    """Eine Kontur als nackte Zahlen. Eine detaillierte Schicht bringt
    tausende Punkte, die Koordinaten werden also in einem Aufruf herausgeholt
    statt einzeln.
    """
    return tuple(map(tuple, shapely.get_coordinates(ring).tolist()))


# --- Urteile über den ganzen Körper ---------------------------------------------


def total_overhang(result: SliceResult) -> float:
    return float(sum(layer.overhang_area for layer in result.layers))


def worst_overhang(result: SliceResult) -> float:
    """Die größte Überhangfläche, die auf **einer** Schicht anfängt.

    Die Summe allein sagt zu wenig, und der Unterschied entscheidet über
    Stützen. Ein Becher mit dreihundertachtunddreißig Schichten sammelt
    zweihundertvierzig Quadratmillimeter, von denen keine Schicht mehr als
    knapp vier trägt — jede Wand fängt das in sich auf. Ein Deckel, dessen
    Lochplatte über der Gewindebohrung beginnt, hat achthundertfünfundvierzig
    auf einmal, und die hängen durch.

    Beide lösten dieselbe Warnung aus, solange nur summiert wurde.
    """
    return float(max((layer.overhang_area for layer in result.layers), default=0.0))


def island_layers(result: SliceResult) -> tuple[float, ...]:
    """Höhen, auf denen eine Kontur in der Luft beginnt (§22.2)."""
    return tuple(layer.z for layer in result.layers if layer.islands)


def narrowest(result: SliceResult) -> float:
    """Die dünnste Struktur irgendwo im Körper.

    Exakt unterhalb von :data:`WIDTH_INTERESTING`, wo die Frage gestellt wird
    (§22.2). Ein Körper, dessen dünnste Stelle dicker ist, meldet genau diese
    Grenze — „mindestens zwei Millimeter", keine Messung. Was diese Zahl zeigt,
    muss das sagen.

    **Wer auf ihr rechnet, nimmt :func:`narrowest_measured`.** Dort ist der
    Deckel ``None`` und keine Zahl.
    """
    widths = [layer.min_width for layer in result.layers if layer.min_width > EPS_GEOM]
    return min(widths) if widths else 0.0


def narrowest_measured(
    result: SliceResult, interesting_below: float = WIDTH_INTERESTING
) -> float | None:
    """Dieselbe Zahl, aber nur wo sie eine **Messung** ist — sonst ``None``.

    Der Deckel aus :data:`WIDTH_INTERESTING` ist eine untere Schranke und wurde
    trotzdem weiterverrechnet. An einer 0,8er-Düse ist das teuer: Drei
    Linienbreiten sind dort 2,55 mm, der Deckel liegt bei 2,00, und damit
    meldete ein massiver Klotz „die schmalste Stelle geht auf keine ganze Zahl
    von Bahnen auf" — eine Warnung über eine Stelle, die niemand gemessen hat.

    ``None`` heißt „keine Aussage", und darauf lässt sich nichts falsch
    rechnen. Null bleibt Null: ein Körper ohne messbare Schicht hat keine
    dünnste Stelle.

    **Und die Grenze, um die es geht, kommt herein.** Der Deckel allein ließ
    zwischen sich und der Frage einen Bereich ohne Antwort: Eine Wand von
    2,3 mm geht bei 0,85 mm Bahnbreite auf keine ganze Zahl von Bahnen auf,
    wurde aber als „mindestens 2,0" gemeldet und damit übergangen — der Deckel
    beantwortete eine Frage, die niemand gestellt hatte. Wer eine höhere Grenze
    braucht, sagt sie hier, und die gedeckelten Schichten werden mit ihr noch
    einmal gemessen. Eine Grenze *unter* dem Deckel ändert nichts: so weit ist
    ohnehin exakt gemessen.

    Was das kostet, ist gemessen: 4 ms an einem Klotz, 26 ms an der
    Lochplatte, 56 ms an der Figur, 0,9 s an einer Kugel mit 1,3 Millionen
    Dreiecken — und nur, wenn die Frage überhaupt über den Deckel reicht, also
    ab einer Bahnbreite von 0,67 mm. Mit den mitgelieferten Druckerprofilen
    (0,4er-Düse, 1,26 mm für drei Bahnen) läuft der zweite Durchgang nie.
    """
    thin = narrowest(result)
    if thin <= EPS_GEOM:
        return None
    if thin < WIDTH_INTERESTING - EPS_GEOM:
        return thin
    if interesting_below <= WIDTH_INTERESTING + EPS_GEOM:
        return None
    # Jede Schicht steht auf dem Deckel — sonst wäre ``thin`` kleiner. Also
    # wird jede noch einmal gemessen, und was auch dort oben nur den neuen
    # Deckel trifft, bleibt ohne Aussage.
    widths = [
        minimum_width(_layer_shape(layer), interesting_below=interesting_below)
        for layer in result.layers
        if layer.min_width > EPS_GEOM
    ]
    narrow = min(widths, default=interesting_below)
    return None if narrow >= interesting_below - EPS_GEOM else narrow


def _layer_shape(layer: LayerInfo) -> ShapelyPolygon:
    """Die Konturen einer Schicht wieder als GEOS-Fläche.

    Der Rückweg zu :func:`_to_polygons`: dieselbe Fläche, mit denselben
    Koordinaten, denn dort sind sie unverändert herausgeschrieben worden.
    """
    parts = [ShapelyPolygon(contour.outline, contour.holes) for contour in layer.contours]
    if not parts:
        return ShapelyPolygon()
    return parts[0] if len(parts) == 1 else unary_union(parts)
