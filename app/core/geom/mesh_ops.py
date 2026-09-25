"""Arbeit am Netz selbst (Bauplan §25, Kategorie „Netz").

Drei Operationen, die ändern, wie ein Körper beschrieben ist, ohne ändern zu
wollen, was er ist: weniger Dreiecke, glattere Dreiecke, gleichmäßigere
Dreiecke. Ihren Platz verdienen sie mit Säule B — ein erzeugtes Netz kommt mit
einer halben Million Dreiecken und den Treppenstufen des Rasters an, von dem
es stammt, und beides steht allem Folgenden im Weg.

Alle drei sind verlustbehaftet, und jede sagt, wie viel sie verloren hat. Eine
Dezimierung, die eine Bohrung still um einen Zehntelmillimeter verschiebt, ist
schlimmer als eine, die es sagt.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Final, Literal, cast

import manifold3d
import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, Action, NotManifoldError, ValidationError
from app.core.geom.attributes import transfer
from app.core.geom.mesh import (
    MeshData,
    as_mesh_data,
    face_components,
    max_distance_to_surface,
    stable_vertex_normals,
    unique_edges,
)
from app.core.geom.repair import merge_vertices
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    SceneObject,
    Severity,
)
from app.core.units import DEGREE_UNIT, VOLUME_SUM_NOISE
from app.i18n import _

_log = get_logger(__name__)

#: Unter so vielen Dreiecken wird nichts dezimiert. Bei einem so kleinen
#: Körper geht die Zeit nicht verloren, und jede Entfernung kostet Form.
DECIMATE_FLOOR = 500

#: Wie weit eine Dezimierung die Oberfläche verschieben darf, bevor es eine
#: Warnung wert ist — als Anteil der Modelldiagonale. Ein halbes Prozent auf
#: einem 100-mm-Teil sind 0,5 mm, mehr als eine Passung verträgt.
DEVIATION_WARN = 0.005

#: Wie oft das Neuvernetzen höchstens teilt. Jeder Durchgang vervierfacht die
#: Dreieckszahl; nach zwölf wäre aus einem Würfel eine Milliarde geworden,
#: lange bevor die Kantenlänge jemanden noch interessiert.
MAX_SUBDIVISIONS = 12

#: Und die harte Decke davor. Erreicht sie jemand, ist die Kantenlänge falsch
#: gewählt und nicht das Netz zu grob — die Meldung sagt genau das.
MAX_REMESH_TRIANGLES = 8_000_000

#: Ab welchem Zuwachs das Neuvernetzen sagt, was es gekostet hat. Ein Faktor
#: hundert ist kein Feinschliff mehr, sondern ein anderes Netz — und der Grund,
#: warum alles danach langsamer läuft.
DENSE_FACTOR = 100

#: Wie viel Volumen das Glätten kosten darf, bevor es das sagt. Ein Zehntel ist
#: an einer gescannten Oberfläche normal; ein Viertel heißt, dass der Körper
#: nicht mehr der ist, den jemand geglättet haben wollte.
SMOOTH_LOSS_WARN = 0.25

#: Schritte der Bisektion, die für den Rückfall die kleinste noch ausreichende
#: Oberflächenabweichung sucht. Das ist eine Rechengrenze, keine
#: Geometrietoleranz; die zulässige Abweichung bleibt :data:`DEVIATION_WARN`.
SIMPLIFY_SEARCH_STEPS = 32

#: Wann die Bisektion aufhört, bevor die Schritte aufgebraucht sind: sobald das
#: Intervall der Abweichung auf ein Tausendstel der zulässigen geschrumpft
#: ist. Feiner unterscheidet die Suche keine andere Dreieckszahl mehr — jeder
#: weitere Schritt wäre ein voller ``simplify``-Lauf über den ganzen Körper
#: für dasselbe Ergebnis. Auch das ist eine Rechengrenze, keine Toleranz.
SIMPLIFY_SEARCH_RESOLUTION = 1e-3

#: Wie nah am Ziel ein Bild aufhören darf, gröber zu werden
#: (:func:`_clustered_for_display`): beim Doppelten. Ein Vorschaubild von
#: 48 Pixeln unterscheidet 60 000 Dreiecke nicht von 30 000, und jeder
#: weitere Durchgang legt Ecken zusammen, die niemand zählt.
#:
#: **Für die Operation galt dieselbe Zahl, und dort war sie falsch.** Bis
#: zum 22.09.2026 entschied sie, wann der zweite Solver drankommt — der
#: Besenhalter blieb damit bei 59 100 statt 30 000 stehen, weil 59 100 knapp
#: unter dem Doppelten liegt, während der Rückfall daneben 29 094 erreicht
#: (RM-077). Die Operation fragt jetzt nach dem Ziel selbst.
DECIMATE_MISS = 2

#: Womit die Anzeige-Dezimierung beginnt: der Sehnenfehler, mit dem der
#: exakte Kern tesselliert (``units.MAX_FACET_SAG``) — ein Netz, das so
#: aussieht wie ein B-Rep-Körper auf dem Bildschirm. Reicht das nicht für das
#: Ziel, vervierfacht sich die Toleranz je Schritt; :data:`DISPLAY_SEARCH_STEPS`
#: begrenzt die Suche. Fünf Schritte tragen von 0,05 auf 51 mm — mehr Abweichung
#: sieht kein Bild von zwanzig Pixeln als Verlust.
DISPLAY_TOLERANCE_GROWTH = 4.0
DISPLAY_SEARCH_STEPS = 6

SimplificationSolver = Literal["none", "exact", "fast_simplification", "manifold"]
SimplificationDeviation = tuple[float, float]


def deviation(before: MeshData, after: MeshData, *, cancelled: CancelToken | None = None) -> float:
    """Wie weit die neue Oberfläche schlimmstenfalls von der alten sitzt, in mm.

    Gemessen, nicht geschätzt: jeder Eckpunkt des Ergebnisses wird nach seinem
    Abstand zur ursprünglichen Oberfläche gefragt. Das ist die Zahl, an der
    eine Passung lebt oder stirbt.
    """
    if not after.triangle_count or not before.triangle_count:
        return 0.0
    from scipy.spatial import cKDTree

    points = np.asarray(after.raw.vertices, dtype=float)
    # **Ein Punkt auf einer Ecke des alten Netzes hat Abstand null** — und
    # der exakte Kern lässt beim Vereinfachen Ecken weg, statt sie zu
    # verschieben: Jede Ecke des Ergebnisses ist eine des Ausgangs. Sie noch
    # gegen die Dreiecke zu messen kostete an der Lochplatte mit 204 000
    # Dreiecken drei Sekunden für lauter Nullen (gemessen am 22.09.2026).
    # Gemessen wird nur, was neben einer Ecke liegt; Rundungsrauschen der
    # Koordinaten ist der Maßstab, kein Fertigungsspiel.
    old_vertices = np.asarray(before.raw.vertices, dtype=float)
    roundoff = (
        8
        * np.finfo(np.float64).eps
        * max(float(np.max(np.abs(old_vertices))), float(np.max(np.abs(points))), 1.0)
    )
    to_vertex, _index = cKDTree(old_vertices).query(points)
    off_vertex = np.asarray(to_vertex, dtype=float) > roundoff
    if not off_vertex.any():
        return 0.0
    # Gefragt ist **eine** Zahl, das Maximum — und die kostet an Nadeldreiecken
    # nur dort, wo eine Ecke es noch heben kann (:func:`max_distance_to_surface`).
    return max_distance_to_surface(before.raw, points[off_vertex], cancelled=cancelled)


def decimate(mesh: MeshData, target: int) -> MeshData:
    """Weniger Dreiecke für dieselbe Form, soweit das möglich ist.

    Die Materialslots reisen mit (§20). Sie taten es nicht: Die Dreiecke, die
    herauskommen, sind nicht die, die hineingingen, und ``replacing`` lässt eine
    Zuweisung fallen, deren Länge nicht mehr passt — aus 20 480 Slots wurden
    keine. Ein zweifarbiges Schild kam einfarbig aus der Operation, und im
    Viewport verlor jedes große Modell beim Dezimieren für die Anzeige seine
    Farben.

    **Ohne Grenze übertragen**, anders als nach einer Booleschen Operation: Dort
    trennt die Toleranz die alten Oberflächen von den frisch geschnittenen, die
    zu keiner gehören. Beim Dezimieren gibt es keine frisch geschnittenen — jedes
    Dreieck stammt von der alten Haut, nur gröber. Eine Grenze könnte hier
    nichts richtig machen, aber einiges falsch: Wie weit die Oberfläche wandert,
    ist genau das, was die Dezimierung aushandelt.

    Kostenlos ist das nicht, aber es kostet nur, wo es etwas zu tragen gibt:
    Ohne Slots in der Quelle kehrt die Übertragung sofort zurück, ohne eine
    einzige Näherungsanfrage — und die allermeisten Körper haben ein
    Material. (Bis zum 24.08.2026 lief die Anfrage über einen ``rtree``-Index;
    warum er weg ist, steht an :func:`app.core.geom.mesh.on_surface`.)
    """
    return _decimate_with_solver(mesh, target)[0]


def _decimate_with_solver(
    mesh: MeshData,
    target: int,
    cancelled: CancelToken | None = None,
) -> tuple[MeshData, SimplificationSolver, SimplificationDeviation | None]:
    """Vereinfacht und nennt das tatsächlich verwendete Verfahren.

    Der öffentliche Helfer darüber behält seinen bisherigen Vertrag. Die
    Operation braucht zusätzlich den Namen, damit ein Rückfall nicht still als
    dasselbe Verfahren erscheint. ``"exact"`` heißt: Das Vorspiel
    (:func:`_exactly_flattened`) hat allein schon unter das Ziel geführt, und
    kein Solver hat die Form angefasst.
    """
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh, "none", None
    source = _welded_for_simplify(mesh)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # **Erst das Exakte, dann das Verlustbehaftete.** Ein CAD-Export mit
    # unterteilten Fächern trägt Ecken, die nichts beschreiben — sie liegen auf
    # einer ebenen oder geraden Nachbarschaft. Der exakte Kern nimmt sie ohne
    # jede Abweichung heraus, und was danach bleibt, ist klein genug für jeden
    # Solver: die viermal unterteilte Lochplatte 203 776 → 814 Dreiecke in
    # 110 ms, wo ``fast_simplification`` vier Sekunden stillstand und der
    # Rückfall danach elf brauchte (gemessen am 22.09.2026).
    flattened = _exactly_flattened(source, cancelled)
    if flattened is not None:
        _log.info(
            "removed %d redundant triangles exactly",
            source.triangle_count - flattened.triangle_count,
        )
        if flattened.triangle_count <= max(target, DECIMATE_FLOOR):
            # Gemessen wird die Richtung, die der Befund nennt — wie bei den
            # beiden Solvern. Die Gegenrichtung (jede alte Ecke gegen die neue
            # Fläche) belegen hier Bauart und Prüfung statt Messung: Der Kern
            # hat Ecken weggelassen und keine bewegt, und
            # :func:`_exactly_flattened` hat Volumen, Dichtheit und Teilzahl
            # verglichen. Sie zu messen kostete an der Lochplatte 1,2 der 1,5 s
            # für eine Zahl, die kein Befund liest.
            forward = deviation(source, flattened)
            return flattened, "exact", (forward, forward)
        source = flattened
    reduced = source.raw.simplify_quadric_decimation(face_count=target)
    # **Auch ein verfehltes Ziel ist ein Stillstand.** ``fast_simplification``
    # kommt an einem CAD-Export mit Nadeldreiecken nicht voran — an der
    # Lochplatte mit 203 776 Dreiecken blieben nach vier Sekunden 197 458
    # stehen, und weil das weniger als vorher war, galt es hier als Erfolg
    # (gemessen am 22.09.2026). Sein Flip-Schutz lehnt jeden Kollaps ab, der
    # ein spitzes Dreieck noch spitzer macht, und aus einer Fächerfläche um
    # eine Bohrung wird so nie etwas anderes.
    #
    # Gefragt wird nach dem **Ziel**, nicht nach einem Vielfachen davon: Der
    # Rückfall lehnt in einem einzigen ``simplify``-Lauf ab, wenn seine
    # Abweichungsgrenze das Ziel nicht trägt, und ein Netz, dessen Form nicht
    # weniger hergibt, bleibt damit weiter sein eigenes Ergebnis. Was die
    # frühere Schwelle kostete, steht an :data:`DECIMATE_MISS`.
    #
    # **Und die zweite Frage wurde nie gestellt: Ist das Ergebnis überhaupt
    # noch ein Körper?** Der erste Solver kennt keine Topologie. An der
    # erzeugten Eule kamen aus einem geschlossenen Einzelkörper zehn Teile mit
    # elf verzweigten Kanten heraus, am Voronoi-Spiderman zwölf statt zwei
    # (gemessen am 22.09.2026, RM-076) — und im Bericht stand dazu nur, dass
    # sich die Fläche kaum verschoben hat. Der Rückfall prüft Dichtheit,
    # Teilzahl, Volumen und Abweichung, bevor er etwas hergibt; wo er ein
    # Ergebnis hat, ist es heil. Die Eule rettet er bei 150 000 und 60 000
    # Dreiecken vollständig. Am Spiderman und am Kumiko-Gitter lehnt er ab —
    # dann bleibt das zerrissene Ergebnis stehen, und :func:`_deviation_findings`
    # sagt, was daraus geworden ist.
    if (
        len(reduced.faces) >= source.triangle_count
        or len(reduced.faces) > target
        or _lost_body(source, source.replacing(reduced))
    ):
        fallback = _manifold_decimation(source, target, cancelled)
        if fallback is not None:
            fallback_mesh, measured = fallback
            _log.info(
                "decimated %d to %d triangles with manifold fallback",
                mesh.triangle_count,
                fallback_mesh.triangle_count,
            )
            # ``_as_mesh`` hat die Slots schon übertragen; ein zweiter
            # ``transfer`` suchte dieselben nächsten Flächen noch einmal.
            return (
                fallback_mesh,
                "manifold",
                measured,
            )
    _log.info("decimated %d to %d triangles", mesh.triangle_count, len(reduced.faces))
    return (
        transfer(source.replacing(reduced), [mesh], tolerance=math.inf),
        "fast_simplification",
        None,
    )


def decimate_for_display(mesh: MeshData, target: int, *, sag: float | None = None) -> MeshData:
    """Weniger Dreiecke für ein Bild — in Millisekunden und an jedem Netz.

    ``sag`` ist der Sehnenfehler in Millimetern, mit dem der erste Weg
    beginnt; ohne Angabe der des exakten Kerns (``units.MAX_FACET_SAG``). Ein
    Vorschaubild von 48 Pixeln darf gröber anfangen als die Anzeige — was
    unter einem Viertel Pixel liegt, zeichnet kein Bild.

    Was hier herauskommt, sieht der Bildschirm: das Vorschaubild im
    Objektbaum, die Anzeige ab der Schwelle aus §31, die Beispielbilder, der
    Stellvertreter der Orientierungssuche. Keiner davon braucht die Zusagen
    von :func:`decimate` — Solvername, beidseitig gemessene Abweichung,
    Volumenprüfung —, jeder braucht eine Antwort, bevor der Kunde wartet.

    **Warum nicht derselbe Weg wie die Operation:** ``fast_simplification``
    steht an CAD-Exporten mit Nadeldreiecken still (siehe
    :func:`_decimate_with_solver`), und zwar erst nach hundert Durchgängen
    über das ganze Netz — an der Lochplatte mit 203 776 Dreiecken vier
    Sekunden für ein Vorschaubild, das danach aus 197 458 Dreiecken gezeichnet
    wurde (1,5 s SVG, 0,8 s Rendern im Hauptthread; gemessen am 22.09.2026,
    Robert: das Verschieben eines Körpers dauerte acht Sekunden).

    Zwei Wege, der Reihe nach:

    1. **Der exakte Kern nach Toleranz.** ``manifold3d`` vereinfacht ein
       geschlossenes Netz in einem Durchgang (78 ms an 203 776 Dreiecken) und
       garantiert die Abweichung statt einer Zahl. Begonnen wird mit dem
       Sehnenfehler, mit dem der Kern selbst tesselliert; reicht das nicht,
       wächst die Toleranz je Schritt (:data:`DISPLAY_TOLERANCE_GROWTH`).
    2. **Zusammenlegen im Raster**, wo der Kern das Netz nicht nimmt — offen,
       verschränkt, eine Dreieckssuppe: :func:`_clustered_for_display` legt
       Ecken derselben Rasterzelle zusammen, ein Gang über alle Punkte, ohne
       Schleife über Dreiecke. Der Rasterweg darf bis zum Doppelten der
       angeforderten Dreieckszahl behalten (:data:`DECIMATE_MISS`); für den
       Anzeigeaufbau gelten damit höchstens 400.000 Dreiecke nach §31.

    Die Slots reisen wie bei :func:`decimate` ohne Grenze mit (§20).
    """
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh
    reduced = _display_manifold_decimation(mesh, target, sag)
    if reduced is None:
        reduced = _clustered_for_display(mesh, target, sag)
    _log.info("display: %d to %d triangles", mesh.triangle_count, reduced.triangle_count)
    return reduced


def raster_for_display(mesh: MeshData, target: int, *, sag: float | None = None) -> MeshData:
    """Weniger Dreiecke für ein kleines Bild — nur über das Raster, nie über den Kern.

    Der Weg für die Vorschaubilder des Objektbaums (``drawing.thumbnail``),
    die neben dem Fenster in einem Arbeiter entstehen. :func:`decimate_for_display`
    fragt zuerst den exakten Kern, und ``manifold3d`` gibt den Interpreter
    während ``simplify`` nicht frei: Jeder Aufruf im Arbeiter hält das Fenster
    an. Gemessen am 22.09.2026 am Besenhalter aus dem Kundenbestand (59 740
    Dreiecke, belastete Maschine): 1,25 s für ein Bild von zwanzig Pixeln, das
    Fenster stand dabei bis zu 456 ms still, nach **jeder** Operation und
    jedem Undo — die Zeile rechnet ihr Bild zu jeder Auswertung neu. Das Raster
    (:func:`_clustered_for_display`) rechnet in numpy, gibt den Interpreter
    in seinen Sortierungen frei und braucht an demselben Netz 32 ms bei
    höchstens 4 ms Stillstand.

    Genauer ist es nicht, und das braucht es nicht: Eine Ecke wandert um
    höchstens eine Zelle, und die Zelle ist ein Viertel Pixel des Bildes
    (``sag``). Für die große Anzeige gilt weiter der Kern.
    """
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh
    return _clustered_for_display(mesh, target, sag)


def _display_manifold_decimation(mesh: MeshData, target: int, sag: float | None) -> MeshData | None:
    """Der erste Weg von :func:`decimate_for_display` — oder ``None``.

    ``None`` heißt: Der Kern nimmt das Netz nicht, oder es kommt in
    :data:`DISPLAY_SEARCH_STEPS` Schritten nicht unter das Ziel. Letzteres
    passiert an Netzen, die der Kern annimmt, obwohl sie nicht geschlossen
    sind — dort fällt die Dreieckszahl mit wachsender Toleranz nicht, sondern
    springt (gemessen an einer offenen Schüssel mit 215 074 Dreiecken: 12 614
    bei 0,67 mm, 78 740 bei 3,3 mm). Ein Schritt, der nichts einbringt, beendet
    die Suche deshalb sofort: Sechs vergebliche Läufe kosteten dort 600 ms,
    bevor der zweite Weg drankam.
    """
    from app.core.units import MAX_FACET_SAG

    try:
        solid = _as_solid(mesh)
    except NotManifoldError:
        return None
    tolerance = sag if sag is not None and sag > 0.0 else MAX_FACET_SAG
    best = None
    for _step in range(DISPLAY_SEARCH_STEPS):
        candidate = solid.simplify(tolerance)
        if candidate.is_empty():
            break
        if best is not None and candidate.num_tri() >= best.num_tri():
            break
        best = candidate
        if candidate.num_tri() <= target:
            break
        tolerance *= DISPLAY_TOLERANCE_GROWTH
    if best is None or best.num_tri() > target or best.num_tri() >= mesh.triangle_count:
        return None
    return _as_mesh(mesh, best)


def _clustered_for_display(mesh: MeshData, target: int, sag: float | None) -> MeshData:
    """Ecken derselben Rasterzelle werden eine — der zweite Weg von
    :func:`decimate_for_display`.

    Die Zellkante ist die Sehne, mit der der erste Weg begonnen hätte
    (``sag``, sonst ``units.MAX_FACET_SAG``), mindestens aber ein
    Vierhundertstel der längsten Seite — feiner unterscheidet kein Bild, und
    ein Raster ohne Untergrenze wäre an einem winzigen Netz keines. Jede Ecke
    wird durch die Mitte der **benutzten** Ecken ihrer Zelle ersetzt — Ecken,
    die kein Dreieck nennt, ziehen sonst die Mitte dorthin, wo keine Fläche
    ist —, Dreiecke mit zwei gleichen Ecken fallen, doppelte bleiben einmal.
    Liegt das Ergebnis noch weit über dem Ziel, verdoppelt sich die Zelle,
    bis sie ein Viertel des Körpers misst: Ein Gang kostet an 215 000
    Dreiecken 30 ms, der Quadrik-Solver blieb an derselben Schüssel bei 2 778
    Dreiecken stehen und brauchte dafür eine halbe Sekunde.

    Das ist kein Verfahren für Geometrie — eine Kante wandert um bis zu eine
    Zelle —, aber eines für ein Bild, dessen Pixel gröber sind.
    """
    from app.core.units import MAX_FACET_SAG

    body = mesh.raw
    faces = np.asarray(body.faces, dtype=np.int64)
    used, compact = np.unique(faces, return_inverse=True)
    vertices = np.asarray(body.vertices, dtype=float)[used]
    faces = compact.reshape(faces.shape)
    low = vertices.min(axis=0)
    span = float(np.max(vertices.max(axis=0) - low))
    cell = sag if sag is not None and sag > 0.0 else MAX_FACET_SAG
    cell = max(cell, span / 400.0, 1e-9)
    merged, mapped = _clustered_once(vertices, faces, low, cell)
    # Verdoppeln bis unter das Ziel — oder bis eine Zelle ein Viertel des
    # Körpers misst; gröber ist kein Bild mehr, sondern ein Klotz.
    while (
        len(mapped) > target * DECIMATE_MISS
        and len(mapped) > DECIMATE_FLOOR
        and cell * 2.0 <= span / 4.0
    ):
        cell *= 2.0
        merged, mapped = _clustered_once(vertices, faces, low, cell)
    reduced = trimesh.Trimesh(vertices=merged, faces=mapped, process=False)
    return transfer(MeshData.of(reduced), [mesh], tolerance=math.inf)


def _clustered_once(
    vertices: np.ndarray, faces: np.ndarray, low: np.ndarray, cell: float
) -> tuple[np.ndarray, np.ndarray]:
    """Ein Durchgang des Zusammenlegens: neue Ecken und die Dreiecke darauf."""
    grid = np.floor((vertices - low) / cell).astype(np.int64)
    # Eine Zellnummer statt dreier Koordinaten: ``np.unique`` über eine Achse
    # sortiert Zeilen als Strukturen und kostet an 107 000 Ecken 150 ms, die
    # eindimensionale Fassung ein Zehntel davon.
    extent = grid.max(axis=0) + 1
    cell_ids = grid[:, 0] + extent[0] * (grid[:, 1] + extent[1] * grid[:, 2])
    _cells, inverse, counts = np.unique(cell_ids, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    merged = np.zeros((len(counts), 3), dtype=float)
    np.add.at(merged, inverse, vertices)
    merged /= counts[:, None]
    mapped = inverse[faces]
    alive = (
        (mapped[:, 0] != mapped[:, 1])
        & (mapped[:, 1] != mapped[:, 2])
        & (mapped[:, 0] != mapped[:, 2])
    )
    mapped = mapped[alive]
    first = _first_of_each_triangle(np.sort(mapped, axis=1), len(counts))
    return merged, mapped[np.sort(first)]


#: Bis zu dieser Eckenzahl passt die Kennung eines Dreiecks — seine drei
#: Ecken als Stellen einer Zahl zur Basis der Eckenzahl — in eine 64-Bit-Zahl:
#: Die größte ist (2²¹)³ - 1 = 2⁶³ - 1.
PACKED_CORNERS = 2**21


def _first_of_each_triangle(ordered: np.ndarray, corners: int) -> np.ndarray:
    """Wo jedes Dreieck zum ersten Mal steht — ``ordered`` trägt je Zeile
    seine Ecken aufsteigend, ``corners`` ist die Zahl der Ecken.

    **Eine Zahl je Dreieck, solange sie passt.** Sie sortiert zehnmal
    schneller als die Zeilen selbst (siehe :func:`_clustered_once`); darüber
    liefe sie über, und zwei verschiedene Dreiecke trügen dieselbe Kennung —
    bei 2²² Ecken etwa ``(0, 1, 2)`` und ``(0, 1, 2 + 2²⁰)``, und eines davon
    fiele als „doppelt" aus dem Bild. Dann werden die Zeilen verglichen.
    """
    if corners <= PACKED_CORNERS:
        triangle_ids = ordered[:, 0] + corners * (ordered[:, 1] + corners * ordered[:, 2])
        _unique_ids, first = np.unique(triangle_ids, return_index=True)
    else:
        _unique_rows, first = np.unique(ordered, axis=0, return_index=True)
    return np.asarray(first)


#: Ab welchem Verhältnis Punkte zu Dreiecken ein Netz als unverschweißt gilt.
#: Ein geschlossenes Dreiecksnetz hat etwa halb so viele Punkte wie Dreiecke;
#: eine Dreieckssuppe, in der jedes Dreieck seine eigenen drei Punkte trägt,
#: hat dreimal so viele. Gemessen über den ganzen Korpus: jedes frisch gelesene
#: STL steht auf genau 3,00, ein verschweißter Körper auf 0,50 — dazwischen
#: liegt nichts, und die Eins ist deshalb keine Grenze, an der etwas kippt.
LOOSE_VERTEX_RATIO = 1.0


def _welded_for_simplify(mesh: MeshData) -> MeshData:
    """Verschweißt, falls nötig — die Vereinfachung verlangt geteilte Kanten.

    Quadrik-Dezimierung zieht Kanten zusammen. Wo keine Kante zwei Dreiecke
    verbindet, weil beide ihre eigenen Punkte tragen, zieht sie das Netz
    auseinander statt es zu vereinfachen: **eine Kugel aus 81 920 einzelnen
    Dreiecken kam als 12 450 Teile heraus, nicht wasserdicht.** Verschweißt
    ging dieselbe Kugel auf jedes Ziel als ein wasserdichtes Stück durch, bis
    hinunter zu 2 000 Dreiecken. Das ist der Fund „`decimate` zerlegt glatte
    Körper" (Vase 607 k → 200 k, 60 Teile) — nicht die Glätte war das
    Kennzeichen, sondern das unverschweißte Eingangsnetz, und ein Modell aus
    dem Erzeuger ist genau das.

    **Nur wenn nötig**, denn es ist nicht umsonst: Auf einem schon
    verschweißten Netz kostet `merge_vertices` 37 bis 43 Prozent der
    Vereinfachung obendrauf (103 ms zu 281 bei 328 k Dreiecken, 408 zu 951 bei
    1,3 Mio.) und bewegt dabei null Punkte. `decimate` läuft auch für die
    Anzeige im Viewport; ein Zuschlag von vierzig Prozent für nichts gehört
    dort nicht hin. Das Verhältnis Punkte zu Dreiecken beantwortet die Frage
    umsonst — es sind zwei Längen, keine Rechnung über die Geometrie.

    Die Reparaturkette danach hätte den Schaden nicht geheilt: Sie holt die
    Teilzahl zurück auf eins, die Wasserdichtheit nicht. Was zerrissen ist,
    lässt sich nicht wieder zunähen, ohne zu erfinden — also wird es nicht
    zerrissen.
    """
    if len(mesh.raw.vertices) <= mesh.triangle_count * LOOSE_VERTEX_RATIO:
        return mesh
    welded, gone = merge_vertices(mesh)
    _log.info("welded %d vertices before simplifying", gone)
    return welded


#: Unter welchem Anteil entfernter Dreiecke das exakte Vorspiel als
#: wirkungslos gilt und sein Ergebnis nicht weitergereicht wird. Der Kern
#: findet an fast jedem Netz ein paar exakt redundante Ecken (die Kugel aus
#: 81 920 Dreiecken: keine, ein Zylinder aus 2 048: vier); für vier Dreiecke
#: das Netz neu zu bauen und die Slots zu übertragen wäre Arbeit für nichts.
FLATTEN_MIN_SHARE = 0.05


def _exactly_flattened(mesh: MeshData, cancelled: CancelToken | None) -> MeshData | None:
    """Das Netz ohne seine exakt redundanten Ecken — oder ``None``.

    ``manifold3d.simplify(0)`` nimmt nur Ecken heraus, deren Nachbarschaft
    eben oder gerade ist: Die Oberfläche bleibt punktgleich, jede Ecke des
    Ergebnisses ist eine des Eingangs. Deshalb ist es kein Solver, sondern
    ein Vorspiel — es kostet keine Form und braucht keine Abweichungsgrenze.

    ``None`` heißt: kein geschlossener Körper, der Kern nimmt das Netz nicht,
    oder es gab weniger als :data:`FLATTEN_MIN_SHARE` zu holen.
    """
    if not mesh.raw.is_volume:
        return None
    try:
        solid = _as_solid(mesh)
    except NotManifoldError:
        return None
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    flat = solid.simplify(0.0)
    if flat.is_empty() or flat.num_tri() > mesh.triangle_count * (1.0 - FLATTEN_MIN_SHARE):
        return None
    result = _as_mesh(mesh, flat)
    if not result.is_watertight or result.component_count != mesh.component_count:
        return None
    # Punktgleiche Oberflächen haben dasselbe Volumen — bis auf das Rauschen
    # der Summe über hunderttausend Dreiecke. Ein Kern, der hier mehr als das
    # verlöre, hätte Form verloren, und das wäre kein Vorspiel mehr.
    if abs(result.volume - mesh.volume) > max(abs(mesh.volume), 1.0) * VOLUME_SUM_NOISE:
        return None
    return result


def _lost_body(before: MeshData, after: MeshData) -> bool:
    """Ob aus einem Körper etwas geworden ist, das keiner mehr ist.

    Zwei Achsen, und die zweite ist nicht die erste: Ein Netz, dessen Kanten
    nicht mehr genau zwei Flächen tragen, ist nicht mehr geschlossen — das
    deckt die verzweigten Kanten mit ab, denn ``trimesh`` nennt ein Netz mit
    einer dreifach belegten Kante nicht wasserdicht. Ein Körper kann aber
    auch in Teile zerfallen, die **je für sich** geschlossen sind; dann sagt
    die erste Frage nichts und die zweite alles.

    Dieselben zwei Fragen prüfen :func:`_exactly_flattened` und
    :func:`_manifold_decimation` an ihrem eigenen Ergebnis, bevor sie es
    hergeben.
    """
    if before.is_watertight and not after.is_watertight:
        return True
    return after.component_count > before.component_count


def _manifold_decimation(
    mesh: MeshData,
    target: int,
    cancelled: CancelToken | None,
) -> tuple[MeshData, SimplificationDeviation] | None:
    """Rückfall für geschlossene Körper, an denen der erste Solver stillsteht.

    ``manifold3d`` vereinfacht nach Oberflächenabweichung statt nach einer
    Dreieckszahl. Eine Bisektion sucht deshalb die kleinste Abweichung, die das
    Ziel erreicht. Ihre Obergrenze ist genau die vorhandene Warnschwelle; ein
    Ergebnis wird nur übernommen, wenn Wasserdichtheit, Komponentenzahl,
    Volumen und die beidseitig gemessene Oberflächenabweichung standhalten.
    """
    if not mesh.raw.is_volume:
        return None
    try:
        solid = _as_solid(mesh)
    except NotManifoldError:
        return None

    limit = max(mesh.bounds.diagonal, 1.0) * DEVIATION_WARN
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    best = solid.simplify(limit)
    if best.is_empty() or best.num_tri() > target:
        return None

    low = 0.0
    high = limit
    for _step in range(SIMPLIFY_SEARCH_STEPS):
        if high - low <= limit * SIMPLIFY_SEARCH_RESOLUTION:
            break
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        middle = (low + high) / 2.0
        candidate = solid.simplify(middle)
        if not candidate.is_empty() and candidate.num_tri() <= target:
            high = middle
            best = candidate
        else:
            low = middle

    result = _as_mesh(mesh, best)
    if not result.is_watertight or result.component_count != mesh.component_count:
        return None
    if not math.isfinite(result.volume) or result.volume <= 0.0:
        return None
    if abs(result.volume - mesh.volume) / mesh.volume > SMOOTH_LOSS_WARN:
        return None
    forward = deviation(mesh, result)
    bounded = max(forward, deviation(result, mesh))
    if bounded > limit:
        return None
    return result, (forward, bounded)


def smooth(mesh: MeshData, iterations: int) -> MeshData:
    """Nimmt das Rauschen von einer Oberfläche, ohne sie einzuziehen.

    Taubin statt Laplace: schlichtes Glätten schrumpft einen Körper mit jedem
    Durchgang ein wenig, und nach zehn Durchgängen passt ein 20-mm-Stift nicht
    mehr in ein 20-mm-Loch.
    """
    body = mesh.raw.copy()
    trimesh.smoothing.filter_taubin(body, iterations=iterations)
    return mesh.replacing(body)


def edge_lengths(mesh: MeshData) -> np.ndarray:
    """Die Länge jeder Kante des Netzes, in mm."""
    return np.asarray(mesh.raw.edges_unique_length, dtype=float)


def _subdivided_on_demand(mesh: MeshData, edge: float) -> MeshData:
    """Jedes Dreieck so oft geteilt, wie **seine** Kanten es verlangen.

    Der billige Weg, und der einzige, der die Zusage genau erfüllt statt sie zu
    übererfüllen. Er hat einen Haken: an der Naht zwischen zwei verschieden oft
    geteilten Flächen bleibt ein Punkt auf einer Kante liegen, die ihn nicht
    kennt — der Körper ist danach oft nicht mehr geschlossen. Ob er es ist,
    entscheidet der Aufrufer.
    """
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(mesh.raw.vertices, dtype=float),
        np.asarray(mesh.raw.faces, dtype=np.int64),
        max_edge=edge,
    )
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body.merge_vertices()
    return transfer(MeshData.of(body), [mesh], tolerance=math.inf)


def _subdivided_evenly(
    mesh: MeshData, edge: float, cancelled: CancelToken | None = None
) -> MeshData:
    """Jedes Dreieck in vier, so oft, bis auch die längste Kante kurz genug ist.

    Konform: es entsteht keine Naht, der Körper bleibt geschlossen. Der Preis
    sind Dreiecke, wo es längst fein genug war — bei einem Netz mit winzigen
    Bohrungsfacetten neben großen Grundflächen wird das teuer.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    for _step in range(MAX_SUBDIVISIONS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        lengths = np.asarray(body.edges_unique_length, dtype=float)
        if not len(lengths) or float(lengths.max()) <= edge:
            break
        if len(faces) * 4 > MAX_REMESH_TRIANGLES:
            raise _too_fine(mesh, edge, len(faces) * 4)
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body.merge_vertices()
    return transfer(MeshData.of(body), [mesh], tolerance=math.inf)


def estimated_triangles(mesh: MeshData, edge: float) -> int:
    """Wie viele Dreiecke eine Kantenlänge ungefähr ergibt.

    Ein gleichseitiges Dreieck der Kantenlänge ``edge`` deckt
    ``√3/4 · edge²`` ab; die Oberfläche geteilt durch diese Fläche ist die
    Zahl, um die es geht. Grob, und das genügt: gefragt ist, ob eine Eingabe
    in der Größenordnung des Machbaren liegt.

    Gebraucht wird sie **vor** dem ersten Schnitt. Ohne die Schätzung lief die
    Operation erst minutenlang und scheiterte dann — der teure Weg wurde
    gegangen, um festzustellen, dass er zu teuer ist.
    """
    if edge <= 0.0:
        return MAX_REMESH_TRIANGLES + 1
    per_triangle = math.sqrt(3.0) / 4.0 * edge * edge
    return int(float(mesh.raw.area) / max(per_triangle, 1e-12))


def _too_fine(mesh: MeshData, edge: float, would_be: int) -> ValidationError:
    """Sagt, welche Kantenlänge noch ginge — die Zahl kennt nur die Operation.

    „Ergäbe mehr Dreiecke, als sich noch rechnen lassen" allein schickt den
    Nutzer ins Raten: er hat eine Zahl eingetippt, sie war zu klein, und die
    nächste ist auch nur geraten. Jede Halbierung der Kantenlänge vervierfacht
    die Dreiecke, also lässt sich die erreichbare Länge ausrechnen.
    """
    growth = would_be / max(MAX_REMESH_TRIANGLES, 1)
    # Aufgerundet, nicht gerundet: bei 0,05 mm und knapp gerissener Decke ergab
    # das Runden auf zwei Stellen wieder 0,05 — der Vorschlag nannte exakt die
    # Zahl, die gerade abgelehnt worden war, und war damit keiner (Regel 17).
    # Aufwärts ist zudem die sichere Richtung: eine längere Kante ergibt
    # weniger Dreiecke, eine kürzere könnte erneut auflaufen.
    reachable = math.ceil(edge * math.sqrt(growth) * 100.0) / 100.0
    return ValidationError(
        field="edge",
        detail=_("Diese Kantenlänge ergäbe mehr Dreiecke, als sich noch rechnen lassen."),
        constraint="maximum",
        values={
            "triangles": would_be,
            "limit": MAX_REMESH_TRIANGLES,
            "reachable": reachable,
        },
        suggestions=(
            Action(id="use_reachable", label=_("Die kleinste Kantenlänge nehmen, die noch geht.")),
            Action(id="decimate_first", label=_("Vorher dezimieren.")),
        ),
    )


def remesh(mesh: MeshData, edge: float, *, cancelled: CancelToken | None = None) -> MeshData:
    """Teilt jede Kante, die länger als ``edge`` ist, bis keine mehr übrig ist.

    Kein vollwertiger Remesher — er unterteilt nur. Das ist, was eine Analyse
    braucht (eine gleichmäßige Abtastung der Oberfläche), und er verschiebt nie
    einen Punkt, es geht also nichts verloren. Dreiecke dort *gröber* zu
    machen, wo sie dicht sind, ist die Aufgabe der Dezimierung.

    **Zwei Wege, in dieser Reihenfolge** — wie die Rückfallkette der booleschen
    Operationen, und aus demselben Grund: der billige zuerst, der teure, wenn
    er muss.

    ``subdivide_to_size`` teilt nach Bedarf und ist damit sowohl billiger als
    auch genauer am Ziel. Er lässt aber an der Naht zwischen zwei verschieden
    oft geteilten Flächen einen Punkt auf einer Kante liegen, die ihn nicht
    kennt: bei einem Quader 40 x 30 x 10 waren das 192 offene Kanten und drei
    Komponenten, und die nächste boolesche Operation fiel darauf auf die
    Voxelstufe und rundete die Maße.

    ``trimesh.remesh.subdivide`` teilt jedes Dreieck in vier und lässt keine
    solche Naht entstehen — dafür zerteilt es die winzigen mit. Bei
    ``plate_holes`` (796 Dreiecke, feine Bohrungsfacetten neben großen Flächen)
    sind das 815 104 Dreiecke statt 63 040 für dasselbe Ziel.

    Also: nach Bedarf teilen, und nur wenn das Ergebnis aufgeht, gleichmäßig
    nachziehen. Ein Körper, der schon vorher offen war, kann dabei nichts
    verlieren — für ihn bleibt es beim billigen Weg.
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)

    on_demand = _subdivided_on_demand(mesh, edge)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if on_demand.is_watertight or not mesh.is_watertight:
        _log.info("remeshed %d to %d triangles", mesh.triangle_count, on_demand.triangle_count)
        return on_demand
    even = _subdivided_evenly(mesh, edge, cancelled)
    _log.info(
        "remeshed %d to %d triangles (evenly, on demand tore the mesh)",
        mesh.triangle_count,
        even.triangle_count,
    )
    return even


# --- gleichmäßig vernetzen und unterteilen ----------------------------------------
#
# Beides rechnet der exakte Netzkern, nicht ``trimesh``. Der Grund steht in
# ``uniform``: Ein Verfahren, das nur teilt, erreicht die *obere* Schranke der
# Kantenlänge und nie die untere — und Gleichmäßigkeit ist genau der Abstand
# zwischen beiden.


def _as_solid(mesh: MeshData) -> Any:
    """Das Netz als Körper des exakten Kerns, oder ein guter Satz dazu, warum
    nicht.

    Der Kern nimmt kein Netz an, das kein Volumen umschließt — er gibt
    wortlos einen leeren Körper zurück. Genau das ist in P16.2 an
    ``generated_figure.stl`` passiert: Die Datei trägt absichtlich die Fehler
    eines Generators, und heraus kam nichts. Ein Objekt, das beim Unterteilen
    verschwindet, ist die Sorte Fehler, die niemand mit seiner Ursache
    verbindet; also wird hier angehalten, mit dem Weg dorthin (Regel 17).
    """
    # ``Mesh64``, nicht ``Mesh``: der einfache Eingang nimmt ``float32``, und
    # der Kern rechnet in doppelter Genauigkeit (Regel 6). Bei einem Eckpunkt
    # auf 100 mm liegt zwischen zwei ``float32`` rund ein hundertstel
    # Mikrometer — unter jeder Fertigungstoleranz, aber es ist ein Verlust, den
    # niemand zu bezahlen hat, wenn der Kern die doppelte Breite selbst anbietet.
    solid = manifold3d.Manifold(
        manifold3d.Mesh64(
            np.asarray(mesh.raw.vertices, dtype=np.float64),
            np.asarray(mesh.raw.faces, dtype=np.uint64),
        )
    )
    if solid.is_empty():
        raise NotManifoldError(
            detail=_(
                "Dieser Körper umschließt kein Volumen — er lässt sich weder gleichmäßig "
                "vernetzen noch unterteilen. Erst reparieren, dann noch einmal."
            ),
            # Jede innere Kante trägt zwei Halbkanten, jede offene eine: aus
            # 3F = 2·E_innen + E_offen und E = E_innen + E_offen folgt
            # E_offen = 2E - 3F. Andersherum gerechnet kommt dieselbe Zahl mit
            # negativem Vorzeichen heraus, und ein Befund über minus achtzehn
            # offene Kanten ist schlimmer als keiner.
            open_edges=int(len(mesh.raw.edges_unique) * 2 - len(mesh.raw.faces) * 3),
        )
    return solid


def _as_mesh(mesh: MeshData, solid: Any) -> MeshData:
    """Zurück ins Netz — und die doppelten Eckpunkte wieder zusammen.

    Der Kern gibt an jeder scharfen Kante mehrere Eckpunkte an derselben
    Stelle heraus, einen je Normalenrichtung. Für einen Renderer ist das
    richtig; hier heißt es, dass ein tadelloser Würfel als sechs Komponenten
    mit offenen Kanten ankommt. Ohne das Verschweißen fällt jede Prüfung
    danach auf ein Netz herein, das nur so aussieht.
    """
    built = solid.to_mesh64()
    body = trimesh.Trimesh(
        vertices=np.asarray(built.vert_properties[:, :3], dtype=float),
        faces=np.asarray(built.tri_verts, dtype=np.int64),
        process=False,
    )
    body.merge_vertices()
    return transfer(MeshData.of(body), [mesh], tolerance=math.inf)


def refined(mesh: MeshData, edge: float) -> MeshData:
    """Jede Kante höchstens ``edge`` lang — konform, und jede Schale bleibt ihre eigene.

    Wie :func:`uniform` ohne Vereinfachung, nur ohne das Verschweißen danach:
    ``_as_mesh`` legt zusammenfallende Ecken zusammen, und zwei Schalen, die
    sich in einem Punkt berühren — zwei Zellen eines Musters am Feldrand —,
    hingen danach an einer Kante mit drei Dreiecken, und der Körper war
    nicht mehr geschlossen (22.09.2026: 29 Rippen, danach 23 Körper und ein
    Schnitt auf der Voxelstufe). Für ein Werkzeug, das gleich gebogen wird,
    zählt nur, dass jede Schale dicht bleibt.
    """
    built = _as_solid(mesh).refine_to_length(edge).to_mesh64()
    body = trimesh.Trimesh(
        vertices=np.asarray(built.vert_properties[:, :3], dtype=float),
        faces=np.asarray(built.tri_verts, dtype=np.int64),
        process=False,
    )
    return mesh.replacing(body)


def uniform(mesh: MeshData, edge: float, deviation: float) -> MeshData:
    """Gleichmäßige Kantenlängen — nach oben wie nach unten.

    Der Unterschied zu :func:`remesh`, gemessen an ``plate_holes``: Teilen
    allein lässt das Verhältnis zwischen längster und kürzester Kante, wie es
    war (Streuung 2,22 vorher wie nachher). Es macht das Netz feiner, nicht
    gleichmäßiger — und zahlt dafür 3 260 416 Dreiecke, weil es die winzigen
    Bohrungsfacetten mitzerteilt. Hier sind es rund 30 000 für dieselbe
    Zielkantenlänge.

    Zwei Schritte, und der erste ist der, den ``remesh`` nicht hat:
    ``simplify`` räumt die überflüssig feinen Stellen ab, und zwar in einer
    zugesagten Schranke — kein Punkt der Oberfläche wandert weiter als
    ``deviation``. Erst danach wird geteilt. Mit ``deviation = 0`` fällt der
    erste Schritt aus und die Form bleibt exakt.
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)
    solid = _as_solid(mesh)
    evened = _as_mesh(mesh, solid.simplify(deviation).refine_to_length(edge))
    _log.info("evened %d to %d triangles", mesh.triangle_count, evened.triangle_count)
    return evened


def subdivided(mesh: MeshData, edge: float, angle: float) -> MeshData:
    """Zwischen den Dreiecken interpolieren, scharfe Kanten stehen lassen.

    Reines Teilen setzt neue Punkte in die Ebene der Facette, aus der sie
    stammen — ein Vieleck bleibt ein Vieleck, nur mit mehr Dreiecken. Erst
    Tangenten an den Halbkanten heben die neuen Punkte auf die gekrümmte
    Fläche, die das Vieleck meint. Kanten steiler als ``angle`` bekommen keine
    und bleiben scharf.

    **Über die Normalen, nicht über die Flächen.** Der naheliegende Weg
    (``smooth_out``) leitet die Tangenten aus der Dreiecksgeometrie ab und
    fasst dabei je zwei koplanare Dreiecke zu einem Viereck zusammen, dessen
    Diagonale beim Verfeinern übersprungen wird. Bei einem CAD-Netz, in dem
    jede ebene Fläche aus genau zwei Dreiecken besteht, bricht das zusammen:
    ``plate_holes`` verlor damit ein Sechstel seines Volumens und bekam 2 772
    Kanten der Länge null — und meldete sich weiter als wasserdicht.
    ``smooth_by_normals`` liest stattdessen die zuvor gerechneten
    Eckpunktnormalen und kennt keine Vierecke. Die Kugel wird darüber genauso
    rund (33 436 mm³ von 33 510 möglichen).
    """
    wanted = estimated_triangles(mesh, edge)
    if wanted > MAX_REMESH_TRIANGLES:
        raise _too_fine(mesh, edge, wanted)
    solid = _as_solid(mesh)
    smoothed = solid.calculate_normals(0, angle).smooth_by_normals(0)
    return _as_mesh(mesh, smoothed.refine_to_length(edge))


# --- operations -------------------------------------------------------------------


#: Die zwei Wege von *Dreiecke verringern*. ``"measured"`` ist der der
#: Operation (:func:`_decimate_with_solver`, Abweichung gemessen und gemeldet)
#: und die Vorgabe — jedes vorhandene Projekt rechnet damit wie zuvor.
#: ``"fast"`` ist der Anzeigeweg (:func:`decimate_for_display`): Kern nach
#: Sehnenfehler, dann Raster, ohne Messung. Ihn nimmt die grobe Vorschau
#: (``app.ui.session``, Entscheidung Robert vom 23.09.2026); im Dialog steht
#: er hinten für jeden, dessen großes Netz nur noch zu sehen sein muss.
DECIMATE_METHODS: Final = ("measured", "fast")


@op_params
class DecimateParams(BaseParams):
    triangles: int = param(
        title=_("Dreiecke"),
        default=50_000,
        minimum=DECIMATE_FLOOR,
        maximum=5_000_000,
        doc=_("Zielzahl. Weniger heißt schneller und ungenauer — wie viel, sagt der Bericht."),
    )
    method: str = param(
        # „Methode" und nicht „Verfahren": Das Wort trägt im Katalog schon die
        # Drucktechnik (FDM, Harz), und ein Quelltext hat eine Übersetzung.
        title=_("Methode"),
        default="measured",
        choices=DECIMATE_METHODS,
        placement="advanced",
        doc=_(
            "Gemessen: die Abweichung wird geprüft und gemeldet. Schnell: vereinfacht "
            "wie die Anzeige, ohne Messung — für große Netze, die nur noch zu sehen "
            "sein müssen."
        ),
    )


@register_op(
    name="decimate_mesh",
    result_kind="mesh",
    # Nicht „Dezimieren". Das Wort ist der Fachbegriff und steht so in jedem
    # Netzwerkzeug — es sagt nur niemandem, der zum ersten Mal ein zu großes
    # Netz vor sich hat, worum es geht. Der Bezeichner bleibt, was er war;
    # geändert ist die Zeile im Menü.
    title=_("Dreiecke verringern"),
    category="mesh",
    params=DecimateParams,
    consumes=1,
    produces=1,
    doc=_(
        "Verringert die Dreieckszahl. Die größte Abweichung zur Ausgangsfläche "
        "wird gemessen und gemeldet."
    ),
    caveat=_(
        "Nicht auf einem Teil, das noch bemaßt wird: Dezimieren verschiebt Flächen, "
        "und eine Bohrung, die danach gesetzt wird, sitzt auf einer anderen Oberfläche "
        "als geplant. Zuerst konstruieren, zuletzt dezimieren."
    ),
    # „2" mit dem Parameter ``method``: Der gemessene Weg rechnet wie zuvor,
    # der Schlüssel alter Einträge passt aber nicht mehr zum neuen Schema.
    cache_version="2",
)
def decimate_mesh(ctx: OpContext) -> OpResult:
    params = cast(DecimateParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    if params.method == "fast":
        return _decimated_fast(source, before, params.triangles)
    after, solver, measured = _decimate_with_solver(before, params.triangles, ctx.cancelled)
    findings = _deviation_findings(
        before,
        after,
        source.id,
        moved=measured[0] if measured is not None else None,
    )
    # „exact" ist kein Rückfall: Es hat nur weggenommen, was die Form ohnehin
    # nicht beschrieb, und die gemessene Abweichung steht im Befund darüber.
    if solver == "manifold":
        findings.insert(
            0,
            Finding(
                code="mesh.simplification_fallback",
                severity="info",
                message=_(
                    "Das Netz wurde mit einer formtreuen Ersatzmethode vereinfacht, "
                    "weil das erste Verfahren das Ziel verfehlt oder den Körper "
                    "zerrissen hätte."
                ),
                object_id=source.id,
                values={
                    "solver": solver,
                    "attempted": "fast_simplification",
                    "target": params.triangles,
                    "before": before.triangle_count,
                    "after": after.triangle_count,
                    "deviation_mm": round(measured[1], 6) if measured is not None else 0.0,
                    "volume_change_mm3": round(after.volume - before.volume, 6),
                    "components": after.component_count,
                },
            ),
        )
    findings.extend(_simplification_findings(before, after, params.triangles, source.id))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=findings,
    )


def _decimated_fast(source: SceneObject, before: MeshData, target: int) -> OpResult:
    """*Dreiecke verringern* auf dem Anzeigeweg — :func:`decimate_for_display`, sonst nichts.

    Keine zweite Herleitung: Toleranz, Rückfall aufs Raster und Farbübertrag
    stehen dort. Was fehlt, fehlt mit Absicht — Messung der Abweichung,
    Dichtheit, Teilzahl. Am Weg der Operation kosteten genau die an der
    Lochplatte mit 815 104 Dreiecken 27 bis 30 s je grober Vorschau (Bericht
    Ansicht, 23.09.2026). Der Befund sagt, dass nicht gemessen wurde, statt
    „kaum verschoben" vorzutäuschen.
    """
    after = decimate_for_display(before, target)
    findings = (
        [
            Finding(
                code="mesh.simplified_unmeasured",
                severity="info",
                message=_("Schnell verringert — die Abweichung wurde nicht gemessen."),
                object_id=source.id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        ]
        if after is not before
        else []
    )
    findings.extend(_simplification_findings(before, after, target, source.id))
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


@op_params
class SmoothParams(BaseParams):
    iterations: int = param(
        title=_("Durchgänge"),
        default=5,
        minimum=1,
        maximum=50,
        doc=_("Mehr Durchgänge heißt glatter. Kanten verschwinden dabei mit."),
    )


@register_op(
    name="smooth_mesh",
    result_kind="mesh",
    title=_("Glätten"),
    category="mesh",
    params=SmoothParams,
    consumes=1,
    produces=1,
    doc=_(
        "Nimmt die Rauheit aus einer Oberfläche, ohne den Körper zu schrumpfen. "
        "Für erzeugte Netze mit Treppenstufen."
    ),
)
def smooth_mesh(ctx: OpContext) -> OpResult:
    params = cast(SmoothParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = smooth(before, params.iterations)
    # Die Messung danach kostet ein Vielfaches der Rechnung; wer abgebrochen
    # hat, wartet nicht auf sie (23.09.2026).
    ctx.cancelled.raise_if_cancelled()
    findings = _deviation_findings(before, after, source.id, cancelled=ctx.cancelled)
    findings.extend(_smoothing_cost(before, after, source.id, params.iterations))
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


def _smoothing_cost(
    before: MeshData, after: MeshData, object_id: str, iterations: int
) -> list[Finding]:
    """Was das Glätten am Körper selbst gekostet hat.

    Die Abweichungsmessung daneben sagt, wie weit die *Oberfläche* gewandert
    ist. Sie sagt nicht, dass vom Körper kaum etwas übrig ist — und genau das
    passiert an groben Netzen und dünnen Wänden.
    """
    old, new = float(before.volume), float(after.volume)
    if old <= 0.0:
        return []

    if new <= 0.0:
        # Umgestülpt: die Innenwand ist an der Außenwand vorbeigewandert. Das
        # Netz nennt sich weiter wasserdicht und misst minus neunzehntausend
        # Kubikmillimeter; jede Kennzahl danach ist falsch, und exportieren
        # ließ es sich auch. Kein Befund, ein Abbruch.
        raise ValidationError(
            field="iterations",
            detail=_(
                "Der Körper hat sich beim Glätten umgestülpt — für so viele Durchgänge "
                "ist seine Wand zu dünn."
            ),
            value=iterations,
            constraint="inverted",
            suggestions=(
                Action(id="fewer_iterations", label=_("Weniger Durchgänge nehmen.")),
                Action(
                    id="remesh_first", label=_("Vorher neu vernetzen — feiner glättet sanfter.")
                ),
            ),
        )

    lost = 1.0 - new / old
    if lost <= SMOOTH_LOSS_WARN:
        return []
    return [
        Finding(
            code="mesh.smooth_shrank",
            severity="warning",
            message=_(
                "Das Glätten hat den Körper deutlich verkleinert — an einem groben Netz "
                "zieht es die Ecken zusammen. Erst neu vernetzen, dann glätten."
            ),
            object_id=object_id,
            values={"lost": round(lost, 3), "before": round(old, 1), "after": round(new, 1)},
        )
    ]


@op_params
class RemeshParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_("Jede längere Kante wird geteilt. Kürzer heißt gleichmäßiger und größer."),
    )


@register_op(
    name="remesh_mesh",
    result_kind="mesh",
    title=_("Kanten verfeinern"),
    category="mesh",
    params=RemeshParams,
    consumes=1,
    produces=1,
    doc=_("Teilt lange Kanten, bis das Netz gleichmäßig ist. Die Form bleibt exakt."),
)
def remesh_mesh(ctx: OpContext) -> OpResult:
    params = cast(RemeshParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = remesh(before, params.edge, cancelled=ctx.cancelled)
    ctx.cancelled.raise_if_cancelled()
    findings = [
        Finding(
            code="mesh.remeshed",
            severity="info",
            message=_("Das Netz wurde feiner unterteilt; die Form ist unverändert."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    ]
    # Was der zweite Weg kostet, gehört gesagt. Er wird nur gegangen, wenn der
    # erste das Netz zerrissen hätte, und er zerteilt dabei auch die Dreiecke,
    # die längst fein genug waren. Danach ist jede weitere Operation langsamer,
    # und niemand wüsste warum.
    #
    # Wie teuer, hat der Sprung auf trimesh 5 verschoben: dieselbe Lochplatte
    # ging unter 4.12.2 von 796 Dreiecken auf 815 104 (Faktor 1024), unter
    # 5.0.0 auf 22 636 (Faktor 28). Die Schwelle bleibt, wo sie ist — sie
    # meint den Sprung, der eine Anzeige lahmlegt, und den gibt es weiter.
    # Nur löst der Regelfall sie nicht mehr von selbst aus, weshalb
    # `test_a_net_that_explodes_says_so` sie eigens herunterdreht.
    if after.triangle_count > before.triangle_count * DENSE_FACTOR:
        findings.append(
            Finding(
                code="mesh.remesh_dense",
                severity="info",
                message=_(
                    "Das Netz musste gleichmäßig geteilt werden, um geschlossen zu "
                    "bleiben — es trägt jetzt deutlich mehr Dreiecke."
                ),
                object_id=source.id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        )
    # Der Satz oben ist eine Zusicherung, und eine Zusicherung wird geprüft.
    # Solange sie nur dastand, hat sie einen zerrissenen Körper als heil
    # gemeldet — und der Fehler fiel erst zwei Operationen später auf, als die
    # Rückfallkette auf der Voxelstufe landete.
    if not after.is_watertight and before.is_watertight:
        findings.append(
            Finding(
                code="mesh.remesh_open",
                severity="warning",
                message=_(
                    "Das Netz ist beim Unterteilen aufgegangen — es ist nicht mehr "
                    "geschlossen. Reparieren, bevor es mit Vereinigen oder Abziehen "
                    "weitergeht."
                ),
                object_id=source.id,
                values={"components": after.component_count},
            )
        )
    elif not after.is_watertight:
        findings.append(
            Finding(
                code="mesh.remesh_open",
                severity="warning",
                message=_(
                    "Dieser Körper war schon vorher nicht geschlossen; das Unterteilen "
                    "ändert daran nichts."
                ),
                object_id=source.id,
                values={"components": after.component_count},
            )
        )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


@op_params
class UniformParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_(
            "Wie lang die Kanten danach ungefähr überall sind. Kürzer heißt feiner "
            "und größer — und feiner ist nur nötig, wo später geformt wird."
        ),
    )
    deviation: float = param(
        title=_("Zulässige Abweichung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        doc=_(
            "Wie weit die Fläche dafür wandern darf. Null lässt die Form unangetastet; "
            "erst darüber verschwinden auch die überflüssig feinen Stellen."
        ),
    )


@register_op(
    name="remesh_uniform",
    result_kind="mesh",
    title=_("Dreiecke angleichen"),
    category="mesh",
    params=UniformParams,
    consumes=1,
    produces=1,
    doc=_(
        "Bringt alle Dreiecke auf ungefähr dieselbe Größe — die groben werden geteilt, "
        "die überflüssig feinen zusammengefasst. Die Vorstufe zum Formen von Hand."
    ),
    caveat=_(
        "Nicht zum Verfeinern allein: Wer nur mehr Dreiecke will, ohne dass irgendwo "
        "welche verschwinden, nimmt „Kanten verfeinern“ — das teilt und fasst nie zusammen."
    ),
)
def remesh_uniform(ctx: OpContext) -> OpResult:
    """Gleichmäßige Dreiecke, damit ein Pinsel überall gleich wirkt.

    ``ctx.quality`` ändert hier bewusst nichts. Die Kantenlänge *ist* die
    Zusage dieser Operation; sie im Entwurf stillschweigend zu verdoppeln
    hieße, ein anderes Netz zu liefern als bestelltes — und was danach kommt,
    rechnet mit genau dieser Auflösung.
    """
    params = cast(UniformParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = uniform(before, params.edge, params.deviation)
    ctx.cancelled.raise_if_cancelled()
    findings = [
        Finding(
            code="mesh.evened",
            severity="info",
            message=_("Die Dreiecke liegen jetzt gleichmäßig über der Oberfläche."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    ]
    # Gemessen wird nur, wenn es etwas zu messen gibt. Ohne zugelassene
    # Abweichung wird kein Eckpunkt verschoben, und die Messung kostet eine
    # Abstandsabfrage über zehntausende Punkte — für eine Zahl, die null ist.
    if params.deviation > 0.0:
        findings.extend(_deviation_findings(before, after, source.id, cancelled=ctx.cancelled))
    else:
        findings.append(
            Finding(
                code="mesh.deviation",
                severity="info",
                message=_("Die Form ist dabei unverändert geblieben."),
                object_id=source.id,
                values={
                    "deviation_mm": 0.0,
                    "before": before.triangle_count,
                    "after": after.triangle_count,
                },
            )
        )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


@op_params
class SubdivideParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_("Wie fein die neue Fläche wird. Kürzer heißt runder und teurer."),
    )
    angle: float = param(
        title=_("Kantenwinkel"),
        default=52.5,
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=180.0,
        doc=_(
            "Ab welchem Winkel eine Kante scharf bleibt. Niedriger rundet mehr ab; "
            "über neunzig verliert auch ein Quader seine Ecken."
        ),
    )


@register_op(
    name="subdivide_surface",
    result_kind="mesh",
    title=_("Fläche unterteilen"),
    category="mesh",
    params=SubdivideParams,
    consumes=1,
    produces=1,
    doc=_(
        "Macht aus einer kantigen Fläche eine gekrümmte: Die neuen Punkte werden nicht "
        "in die Facette gesetzt, sondern auf die Rundung, die sie meint. Scharfe Kanten "
        "bleiben scharf."
    ),
    caveat=_(
        "Nicht als Ersatz für eine gröbere Vorlage: Was hier entsteht, ist eine "
        "Interpolation der vorhandenen Facetten, keine wiedergewonnene Konstruktion. "
        "Wo es auf ein Maß ankommt, gehört die Rundung in die Skizze."
    ),
)
def subdivide_surface(ctx: OpContext) -> OpResult:
    """Unterteilen als Glättungsverfahren, nicht als Vernetzungswerkzeug.

    ``ctx.quality`` bleibt auch hier ohne Wirkung, aus demselben Grund wie bei
    :func:`remesh_uniform`: Die Kantenlänge ist die Zusage.
    """
    params = cast(SubdivideParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = subdivided(before, params.edge, params.angle)
    ctx.cancelled.raise_if_cancelled()
    findings = _deviation_findings(before, after, source.id, cancelled=ctx.cancelled)
    findings.append(
        Finding(
            code="mesh.subdivided",
            severity="info",
            message=_("Die Fläche wurde zwischen ihren Facetten interpoliert."),
            object_id=source.id,
            values={"before": before.triangle_count, "after": after.triangle_count},
        )
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


#: Ab welchem **Vielfachen des Ziels** eine Vereinfachung eine Auskunft wert ist.
#:
#: Nicht „exakt verfehlt": Die Quadrik-Dezimierung landet regelmäßig ein paar
#: Dreiecke neben der Vorgabe, und daraus einen Befund zu machen hieße, bei
#: jedem zweiten Lauf etwas zu melden.
#:
#: **Die Zahl stand bis zum 31.08.2026 auf 0,95 und maß den Anteil des
#: Eingangs** — also, wie viel reduziert wurde, statt wie weit am Ziel vorbei.
#: Zwei verschiedene Achsen, und bei einem Körper mit Durchgangsloch fallen sie
#: auseinander: Ein Rohr aus 131 072 Dreiecken kommt bei jedem Ziel zwischen
#: 20 000 und 600 mit 74 592 heraus — um 43 Prozent reduziert, also weit unter
#: den fünf Prozent, ab denen gemeldet wurde, und dabei das 124-Fache der
#: verlangten Zahl. Wer 400 verlangte und 992 bekam, wurde gewarnt; wer 600
#: verlangte und 74 592 bekam, erfuhr nichts. Je weiter das Ziel verfehlt war,
#: desto seltener meldete es sich.
#:
#: **Und es ist der Alltagsfall.** Gemessen: Euler-Zahl 2 (Kugel, Quader)
#: trifft jedes Ziel exakt; Euler-Zahl 0 — ein Körper mit Durchgangsloch, also
#: jede Hülse, jeder Ring, jedes Gehäuse mit Durchbruch — bleibt stehen, ohne
#: entartete Dreiecke und ohne eine offene Kante.
#: Ein vollständig unverändertes Netz meldet sich unabhängig vom Verhältnis:
#: null Wirkung ist keine übliche Zielstreuung.
SIMPLIFY_MISSED = 1.5


def _simplification_findings(
    before: MeshData, after: MeshData, target: int, object_id: str
) -> list[Finding]:
    """Sagt es, wenn das Vereinfachen sein Ziel nicht erreicht hat.

    **Der Kunde bekam bisher „Die Fläche hat sich dabei kaum verschoben."** Das
    stimmt und ist vollkommen nebensächlich: Er hatte 400 Dreiecke verlangt und
    992 bekommen, im Verlauf steht ein Schritt, und im Bild dasselbe Teil. Wer
    das liest, sucht den Fehler bei sich.

    Dass nichts passiert, ist dabei nicht einmal falsch. Gemessen an der
    Halterung aus Weg 1: 992 Dreiecke, wasserdicht, eine Komponente, keine
    entarteten Dreiecke, Euler-Zahl minus acht — ein CAD-Teil mit fünf
    Durchbrüchen, das bereits minimal trianguliert ist. Jede Kante trennt dort
    zwei Ebenen, und
    eine solche Kante zusammenzuziehen hieße, die Form zu ändern. Dieselbe
    Rechnung erreicht an Kugel und Quader jedes Ziel exakt; sie gibt hier auf,
    weil es nichts zu holen gibt.

    Gemeldet wird deshalb als Auskunft und nicht als Warnung — nichts ist
    schiefgegangen, es gab nur nichts zu tun. Die Handlung dazu ist keine
    Reparatur, sondern die Einordnung: Wer die Dreieckszahl senken will, muss
    die Form vergröbern (Glätten) oder mit dem leben, was die Form kostet.

    **Gefragt wird, wie weit das Ergebnis am Ziel vorbeiliegt** — nicht, wie
    viel es gegenüber dem Eingang eingespart hat. Die zweite Frage ließ genau
    die Fälle durch, in denen kräftig reduziert und das Ziel trotzdem um
    Größenordnungen verfehlt wurde; die Begründung steht an ``SIMPLIFY_MISSED``.

    **Und davor steht der Fall, in dem es von vornherein nichts zu holen gab.**
    Das Ziel ist mit 50 000 vorbelegt, und die meisten Teile sind kleiner:
    Gemessen am 14.09.2026 über das Fenster kam an einem Körper mit 320
    Dreiecken ein Schritt in den Verlauf, im Bild dasselbe Teil und im Band
    „am Volumen ändert sich nichts". Der Eingang lag schon unter dem Ziel,
    und die erste Zeile unten kehrte leer zurück — dieselbe Antwort, die eine
    **geglückte** Vereinfachung bekommt, denn beide Male liegt das Ergebnis
    unter der verlangten Zahl. Unterscheiden lassen sich die zwei nur am
    Eingang, und deshalb wird der zuerst gefragt.
    """
    if before.triangle_count <= target:
        return [
            Finding(
                code="mesh.already_below_target",
                severity="info",
                message=_(
                    "Der Körper hat schon weniger Dreiecke als das Ziel — es gibt nichts zu "
                    "verringern. Ein Ziel unterhalb der vorhandenen Zahl gibt dem Schritt "
                    "etwas zu tun; sonst kann er wegbleiben."
                ),
                object_id=object_id,
                values={
                    "target": target,
                    "before": before.triangle_count,
                    "after": after.triangle_count,
                },
            )
        ]
    if after.triangle_count <= target or after.triangle_count > before.triangle_count:
        return []
    if (
        after.triangle_count < before.triangle_count
        and after.triangle_count < target * SIMPLIFY_MISSED
    ):
        return []
    return [
        Finding(
            code="mesh.not_simplified",
            severity="info",
            message=_(
                "Das Netz ließ sich nicht weiter vereinfachen — es trägt die Form "
                "schon mit den wenigsten Dreiecken."
            ),
            object_id=object_id,
            values={
                "target": target,
                "before": before.triangle_count,
                "after": after.triangle_count,
            },
        )
    ]


def _deviation_findings(
    before: MeshData,
    after: MeshData,
    object_id: str,
    *,
    moved: float | None = None,
    cancelled: CancelToken | None = None,
) -> list[Finding]:
    """Sagt, was es gekostet hat — gemessen an der Oberfläche, nicht aus
    Zahlen geraten.

    **Und ob der Körper dabei aufgegangen ist.** Die Abweichung allein
    beschreibt nur, wie weit sich Flächen verschoben haben; sie sagt nichts
    darüber, ob danach noch ein Körper da ist. Gemessen an einer
    heruntergeladenen Ente: *Netz vereinfachen* auf 60 000 Dreiecke machte aus
    einem geschlossenen Körper einen offenen, und im Prüfbericht stand dazu
    „Die Fläche hat sich dabei kaum verschoben" — richtig und vollkommen
    nebensächlich. Wer danach exportiert, bekommt den Befund erst dort, einen
    Arbeitsschritt zu spät.

    Die Kennung endet bewusst auf ``not_watertight``: Dieselbe Sache melden
    Einlesen, Export und Agentenzug, und die Familie trägt dieselben zwei
    Handlungen (``FINDING_ACTIONS``).
    """
    moved = deviation(before, after, cancelled=cancelled) if moved is None else moved
    limit = max(before.bounds.diagonal, 1.0) * DEVIATION_WARN
    severity: Severity = "warning" if moved > limit else "info"
    findings = [
        Finding(
            code="mesh.deviation",
            severity=severity,
            message=(
                _("Die Fläche hat sich dabei spürbar verschoben — Passungen neu prüfen.")
                if severity == "warning"
                else _("Die Fläche hat sich dabei kaum verschoben.")
            ),
            object_id=object_id,
            values={
                "deviation_mm": round(moved, 4),
                "before": before.triangle_count,
                "after": after.triangle_count,
            },
        )
    ]
    if before.is_watertight and not after.is_watertight:
        findings.append(
            Finding(
                code="mesh.not_watertight",
                severity="warning",
                message=_(
                    "Der Körper war geschlossen und ist es jetzt nicht mehr — "
                    "„Reparieren“ schließt die offenen Stellen."
                ),
                object_id=object_id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        )
    # **Offen und zerfallen sind zwei Dinge, und das zweite merkt der Kunde
    # erst im Slicer.** Am Voronoi-Spiderman machte *Dreiecke verringern* auf
    # 30 000 aus zwei Teilen zwölf, am Kumiko-Gitter aus einem 2 054 (RM-076);
    # der Bericht nannte die offene Naht und schwieg über die Stückzahl.
    # Reparieren hilft unterschiedlich weit — den Spiderman setzt es wieder
    # zusammen, vom Gitter bleiben 94 Teile und ein Drittel weniger Volumen —,
    # also verspricht der Satz nichts, sondern nennt beide Wege.
    if after.component_count > before.component_count:
        findings.append(
            Finding(
                code="mesh.components_split",
                severity="warning",
                message=_(
                    "Der Körper ist dabei in {count} Teile zerfallen. „Reparieren“ setzt "
                    "zusammen, was noch zusammenpasst; bleibt zu viel übrig, war das Ziel "
                    "zu niedrig.",
                    count=after.component_count,
                ),
                object_id=object_id,
                values={
                    "before_components": before.component_count,
                    "after_components": after.component_count,
                    "before": before.triangle_count,
                    "after": after.triangle_count,
                },
            )
        )
    return findings


# --- Aufdicken (Konzept P15 §7 Etappe 6, D15) -----------------------------------


@op_params
class ThickenParams(BaseParams):
    thickness: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.1,
        # **Nach oben begrenzt, nach unten nicht.** Zehn von zwölf Wandstärken
        # im Register tragen ein Maximum (`shell_exact` meint dasselbe und
        # liegt bei 50); `thicken` war die Ausnahme. Unten bleibt es offen,
        # weil der Prüfbericht dort die bessere Auskunft gibt als eine Grenze —
        # was zwei Extrusionsbahnen für **dieses** Material heißen, weiß er,
        # und eine Zahl im Schema wüsste es nicht.
        maximum=50.0,
        doc=_(
            "Wie dick die Wand wird. Unter zwei Extrusionsbahnen ist sie fragil — "
            "was das für dieses Material heißt, sagt der Prüfbericht."
        ),
    )


#: Warum *Offene Fläche schließen* an einem geschlossenen Körper nichts tut.
#: Als Konstante, weil das Menü denselben Satz sagt, bevor jemand klickt
#: (``requires_body="open"``, ``labels.body_requirement``) — zwei Fassungen
#: derselben Auskunft liefen auseinander.
ALREADY_CLOSED: Final = _(
    "Dieser Körper ist schon geschlossen — eine zweite Haut darüber wäre "
    "keine Wand, sondern eine Verdopplung. Eine einzelne Wand dicker "
    "macht „Fläche versetzen“; einen Hohlraum legt „Aushöhlen“ an."
)


@register_op(
    name="thicken",
    title=_("Offene Fläche schließen"),
    category="mesh",
    params=ThickenParams,
    consumes=1,
    produces=1,
    requires_body="open",
    doc=_(
        "Gibt einer offenen Fläche eine Wand und macht sie damit zu einem Körper. "
        "Der Weg für ein Netz, das als Fläche ankommt statt als Volumen."
    ),
)
def thicken(ctx: OpContext) -> OpResult:
    """Aus einer Fläche einen Körper machen.

    Sechs von 68 echten Modellen sind nicht geschlossen; das ist bei
    Community-Modellen normal, und bis hierher war es eine Sackgasse. Der
    Prüfbericht meldete es korrekt, und danach ging nichts mehr: eine
    Boolesche Operation braucht ein Volumen, und eine Fläche hat keines.

    Ein Körper, der schon einer ist, bekommt **keine** zweite Haut, sondern
    eine Meldung. Ihn stillschweigend zu verdoppeln wäre ein Ergebnis, das
    aussieht wie das Original und beim Schneiden auffällt. **Dasselbe gilt je
    Teil** (Review R6, 24.09.2026): Neben einem geschlossenen Würfel bekam ein
    loses Blatt seine Wand — und der Würfel eine zweite, positive Innenhaut,
    15 057 statt 8 115 mm³. Aufgetragen werden nur die offenen Teile
    (:func:`_thickened_open_parts`).
    """
    params = cast(ThickenParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    if before.raw.is_watertight:
        # **Der häufigste Griff daneben, und er kam vom Titel.** Bis zum
        # 23.08.2026 hieß diese Operation „Fläche aufdicken" und stand im
        # Menü neben „Fläche versetzen". Wer eine Fläche angeklickt hatte und
        # ihre Wand dicker haben wollte, nahm die erste — und bekam hier einen
        # Fehler, der nur „Abbrechen" anbot. Der Schritt blieb im Verlauf und
        # hielt die Auswertung an; in einem Protokoll vom selben Tag neunzehnmal
        # über sieben Minuten, dreimal hintereinander gelegt.
        raise ValidationError(
            "thickness",
            ALREADY_CLOSED,
            value=params.thickness,
            constraint="already_solid",
            suggestions=[
                dataclasses.replace(CORRECT_INPUT, label=_("Stattdessen Fläche versetzen")),
                CANCEL,
            ],
        )

    thickened = _thickened_open_parts(before, params.thickness)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=thickened, features={})],
        findings=[
            Finding(
                code="mesh.thickened",
                severity="info",
                message=_("Aus einer offenen Fläche wurde ein Körper mit Wandstärke."),
                object_id=source.id,
            )
        ],
    )


def _thickened_open_parts(mesh: MeshData, thickness: float) -> MeshData:
    """Nur die Teile mit offenem Rand auftragen; geschlossene bleiben, wie sie sind."""
    import numpy as np

    body = mesh.raw
    _unique, inverse, counts = unique_edges(
        np.asarray(body.edges, dtype=np.int64), return_inverse=True, return_counts=True
    )
    on_rim = np.zeros(len(body.faces), dtype=bool)
    on_rim[np.flatnonzero(counts[inverse] == 1) // 3] = True
    opened = np.zeros(len(body.faces), dtype=bool)
    for piece in face_components(body):
        if on_rim[piece].any():
            opened[piece] = True
    if opened.all() or not opened.any():
        return _thickened(mesh, thickness)

    def part(mask: np.ndarray) -> MeshData:
        chosen = np.flatnonzero(mask)
        raw = body.submesh([chosen], append=True, repair=False)
        slots = tuple(mesh.slots[int(index)] for index in chosen) if mesh.slots else ()
        return MeshData(raw=cast(trimesh.Trimesh, raw), slots=slots)

    kept, grown = part(~opened), _thickened(part(opened), thickness)
    joined = cast(trimesh.Trimesh, trimesh.util.concatenate([kept.raw, grown.raw]))
    slots = kept.slots + grown.slots if kept.slots and grown.slots else ()
    return MeshData(raw=joined, slots=slots)


def _thickened(mesh: MeshData, thickness: float) -> MeshData:
    """Die Fläche nach innen auftragen und die Ränder schließen.

    Drei Teile, und kein einziger boolescher Schnitt: die Fläche selbst bleibt
    die Außenseite, eine um die Wandstärke entlang der Punktnormalen versetzte
    Kopie mit umgedrehten Dreiecken wird die Innenseite, und für jede offene
    Kante schließt ein Viereck den Spalt dazwischen.

    Der naheliegende Weg — jedes Dreieck zu einem Prisma und alle vereinigen —
    war der erste Versuch und ist zweimal falsch: er kostet eine Boolesche
    Operation je Dreieck, und ohne sie bleiben die Innenflächen stehen. Das
    Ergebnis war ein Netz mit achtzig Flächen, das aussah wie ein Körper und
    keiner war.

    **Punktnormalen, nicht Flächennormalen.** Mit Flächennormalen bekommt jedes
    Dreieck seinen eigenen Versatz, und an jeder Kante klafft die Innenseite
    auseinander. Sie kommen aus ``stable_vertex_normals`` — dieselbe
    Winkelgewichtung wie bei ``trimesh``, aber auf jeder Maschine dieselben
    Bits: Aus jeder Normalen wird hier eine Ecke der Innenhaut (RM-187).

    **Und die Filamente reisen mit** (§20): Außen- und Innenhaut sind
    dieselben Dreiecke, und eine Randwand trägt den Slot des Dreiecks, an dessen
    Kante sie steht. Bis zum 22.09.2026 ging die Zuweisung verloren —
    ``replacing`` lässt sie bei einer anderen Dreieckszahl fallen, und ein
    zweifarbiges Schild kam einfarbig aus der Operation.
    """
    import numpy as np

    body = mesh.raw
    outer = np.asarray(body.vertices, dtype=float)
    inner = outer - stable_vertex_normals(body) * thickness
    count = len(outer)

    faces = np.asarray(body.faces, dtype=np.int64)
    # Innen läuft die Umlaufrichtung andersherum, sonst zeigen dort alle
    # Normalen in den Körper hinein.
    flipped = faces[:, ::-1] + count

    unique, inverse, counts = unique_edges(
        np.asarray(body.edges, dtype=np.int64), return_inverse=True, return_counts=True
    )
    # Welches Dreieck eine Kante trägt: ``edges`` läuft drei je Dreieck, in
    # Dreiecksreihenfolge — an einer Randkante gibt es genau eines.
    carrier = np.zeros(len(unique), dtype=np.int64)
    carrier[inverse] = np.arange(len(inverse), dtype=np.int64) // 3
    on_border = counts == 1
    border = unique[on_border]
    walls = [[first, second, second + count, first + count] for first, second in border.tolist()]
    quads = np.asarray(
        [[wall[0], wall[1], wall[2]] for wall in walls]
        + [[wall[0], wall[2], wall[3]] for wall in walls],
        dtype=np.int64,
    ).reshape(-1, 3)

    built = trimesh.Trimesh(
        vertices=np.vstack([outer, inner]),
        faces=np.vstack([faces, flipped, quads]) if len(quads) else np.vstack([faces, flipped]),
        process=True,
    )
    built.fix_normals()
    slots: tuple[int, ...] = ()
    if (
        mesh.slots
        and len(mesh.slots) == len(faces)
        and len(built.faces) == 2 * len(faces) + len(quads)
    ):
        own = np.asarray(mesh.slots, dtype=np.int64)
        wall = own[carrier[on_border]]
        slots = tuple(int(slot) for slot in np.concatenate([own, own, wall, wall]))
    return MeshData(raw=built, slots=slots)
