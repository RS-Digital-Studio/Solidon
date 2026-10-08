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

import math
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, cast

import manifold3d
import numpy as np
import shapely
from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.core.errors import ValidationError
from app.core.geom import kernel_process
from app.core.geom.mesh import MeshData
from app.core.knowledge.rules import OVERHANG_ANGLE_FACTOR, OVERHANG_LIMIT_DEGREES
from app.core.types import CancelToken, LayerInfo, Polygon, Ring, SliceResult
from app.core.units import EPS_GEOM, exact_cos, is_close, ring_area
from app.i18n import _

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

#: Die Fassung des Ebenenschnitts, die dieser Kern vom übersetzten Teil
#: verlangt — dieselbe Zahl wie ``_chain.PLANE_SEGMENTS_API``. Ein älterer Bau
#: nimmt den NumPy-Weg (seit 3: gerichtete Segmente, RM-485).
PLANE_SEGMENTS_API: Final = 3

#: Der kleinste Überhang, der nicht bloß Vernetzungsrauschen ist.
OVERHANG_MARGIN = 0.05

#: Bis zu welchem Spalt zwei Konturen derselben Schicht für den Slicer eine
#: sind, in mm: das Doppelte von ``slice_closing_radius``, mit dem PrusaSlicer
#: und die Orca-Familie jede Schicht schließen (Vorgabe 0,049 mm). Keine
#: Toleranz, die Solidon wählt, sondern was der Slicer tut — am
#: Bohrmaschinenhalter aus dem Korpus stehen die Buchstaben acht Millionstel
#: Millimeter neben der Wand, und im ElegooSlicer verschmelzen sie mit ihr
#: (KUNDE-01).
SLICER_CLOSING_GAP: Final = 2.0 * 0.049

#: Ab welchem Abstand zweier aufeinanderfolgender Schnitte sie nicht mehr
#: dieselbe Schicht sind. Ein Millionstel Millimeter: Senkrechte Wände treffen
#: jede Ebene an denselben Kanten und liefern dieselben Eckpunkte bis auf das
#: Rundungsrauschen der Schnittrechnung; eine Formschräge von einem Zehntel
#: Grad verschiebt die Wand je Schicht um Tausendstel und fällt heraus.
SAME_LAYER_TOLERANCE = EPS_GEOM

#: Schritte der binären Suche nach der kleinsten Strukturbreite. Sechs
#: Halbierungen einer ohnehin engen Klammer lassen unter zwei Prozent übrig.
WIDTH_STEPS = 6

#: Wie weit die Kontur vor dieser Suche vereinfacht werden darf — ein
#: hundertstel Millimeter ist ein Zehntel dessen, was die feinste Düse
#: ablegen kann.
WIDTH_SIMPLIFY = 0.01

#: Ab wie viel verlorener Fläche eine Öffnung eine Struktur getroffen hat und
#: nicht bloß gerechnet, in mm².
#:
#: Mit gefasten Ecken ist die Öffnung für alles, was breit genug ist, die
#: Identität: Eine dicke Form verliert nichts. Übrig bleibt ein Rechenrest, und
#: der lag am ganzen Testkorpus unter einem tausendstel Quadratmillimeter. Ein
#: hundertstel liegt eine Zehnerpotenz darüber und weit unter allem, was ein
#: Bericht je meldet — die feinste Düse legt so viel auf einem zwanzigstel
#: Millimeter Bahn ab.
WIDTH_LOST_FROM = 0.01

#: Wie viele Teile die Öffnung einzeln ansieht, bevor sie die ganze Form
#: fragt (RM-109).
#:
#: Der Teileweg beantwortet nur das **Nein** und kostet dafür im besten Fall
#: einen einzigen Puffer statt dreitausend. Übersteht die Schicht die Öffnung,
#: war er vergeblich — und diese Zahl ist die Obergrenze dafür: vierundsechzig
#: Konturen einer Rändelschicht sind gemessen sieben Millisekunden gegen die
#: dreihundert der ganzen Form.
WIDTH_SCAN_PARTS = 64

#: Über dieser Breite ist eine Struktur schlicht „dick" und wird nicht weiter
#: gemessen. Zwei Millimeter sind fünf Düsendurchmesser — keine Warnung in
#: §22.2 schaut darüber, und die Suche nach einem exakten Wert dort oben
#: kostete mehr als alles andere zusammen.
WIDTH_INTERESTING = 2.0

#: Der Keil (:func:`taper_length`): eine Wand, deren Stärke entlang der
#: Außenkontur stetig läuft. Gemessen wird alle ``TAPER_STEP`` Millimeter der
#: Abstand der Außenkontur zur nächsten Innenkontur. Ein Messpunkt gehört zum
#: Keil, wenn seine Stärke zwischen ``TAPER_FROM`` und ``TAPER_TO`` liegt und
#: sich gegenüber dem Punkt ``TAPER_WINDOW`` Millimeter weiter oder zurück —
#: der ebenfalls im Band liegt — um mindestens ``TAPER_RISE`` unterscheidet.
#: Eine zusammenhängende Strecke zählt ab ``TAPER_RUN``.
#:
#: Die Grenzen sind Geometrie, keine Bahnen: Unter 0,6 mm ist es eine dünne
#: Wand und die Frage eine andere (:func:`minimum_width`); über 4 mm füllt
#: jeder Slicer die Mitte mit Muster, und die Wandzahl ändert sich nicht mehr.
#: Der Becher im Organizer vom 20.09.2026 läuft von 1,0 auf 3,0 mm über
#: 24 mm, also um 0,25 auf vier Millimeter; verlangt wird ein Anstieg, den
#: eine Bahnbreite nicht erklärt. Verglichen wird über ein Fenster und nicht
#: von Punkt zu Punkt, weil ein Keil an seiner dünnsten Stelle für einen
#: Moment flach läuft — dort riss die Strecke sonst in zwei zu kurze Hälften.
#: Eine Trennwand, die rechtwinklig auf die Außenwand trifft, springt: Der
#: Partner vier Millimeter weiter liegt außerhalb des Bandes, der Vergleich
#: entfällt, und was an Zwischenwerten bleibt, ist kürzer als die Mindestlänge.
#: Eine gleichmäßige Wand hat keinen Anstieg, auch um eine Rundung herum.
TAPER_STEP = 1.0
TAPER_FROM = 0.6
TAPER_TO = 4.0
TAPER_WINDOW = 4.0
TAPER_RISE = 0.15
TAPER_RUN = 8.0

#: Der Keil wird an jeder so vielten **gemessenen** Schicht gesucht, die
#: dazwischen tragen den Wert der zuletzt gemessenen. Ein Keil ist eine
#: Eigenschaft der Wand über ihre Höhe — der Becher im Organizer steht auf
#: neun Zehnteln —, und wer ihn liest (``advise``), fragt nach einem Fünftel
#: aller Schichten: Fünf Schichten Unschärfe an jedem Ende ändern die
#: Antwort nicht. Was die Stichprobe spart: an einer Hohlkugel mit 400
#: Schichten kostete der Keil 136 ms, mit jeder fünften 57; an einer Vase mit
#: 1,15 Millionen Dreiecken 303 statt 36 — ein Drittel der ganzen Analyse
#: (21.09.2026). Was sie nicht mehr sieht: einen Keil, der kürzer ist als
#: ``TAPER_SAMPLE`` gemessene Schichten — der wird je nach Lage gar nicht oder
#: fünffach gezählt, und beides liegt unter jeder Schwelle, die ihn liest.
TAPER_SAMPLE = 5

#: Ab welcher Breite eine ungestützte Fläche als Brücke zählt und nicht mehr
#: als Überhang — **wenn kein Drucker bekannt ist**.
#:
#: Darunter kragt die Wandlinie selbst vor und liegt zur Hälfte auf der Schicht
#: darunter — das trägt sich. Darüber muss der Slicer die Fläche füllen, und
#: dafür legt er gerade Bahnen, die er quer über die Öffnung spannt statt
#: entlang der Kontur. Die Grenze sind **zwei Extrusionsbahnen**; der runde
#: Millimeter hier ist die Zahl für einen Aufrufer, der kein Profil mitbringt.
#:
#: **Wer einen Drucker kennt, gibt dessen Zahl herein** (Regel 7, RM-097).
#: ``Profile.minimum_wall_thickness`` *ist* diese zwei Bahnbreiten und ergibt
#: am Centauri 0,84 statt 1,0, an einer 0,8er Düse 1,68 — über
#: ``profiles.analysis_limits`` die größte Mindestwand der tatsächlich
#: verwendeten Materialien. Dass der runde Millimeter danebenlag, sagt seine
#: eigene Begründung: Zwei Bahnen einer 0,4er Düse sind 0,84 und nicht 1,0.
#:
#: Dieselbe Bauart wie ``overhang_angle`` daneben, und aus demselben Grund:
#: Die Schichtanalyse ist von Profilen bewusst entkoppelt und nimmt Zahlen.
BRIDGE_FROM = 1.0

#: Unter so vielen Schichten kostet das Auffächern mehr, als es spart — acht
#: Threads für zwanzig Polygone zu starten ist reiner Verwaltungsaufwand.
PARALLEL_FROM = 40

#: Bis zu zehn Ebenen spart der Segmentweg den vollständigen Körperaufbau.
#: Gemessen am Laptop, MiniGolf, Piratenschiff und Aushöhlprojekt: für eine
#: Ebene 0,001 bis 0,027 s statt 0,011 bis 0,389 s, auch bei zehn Ebenen schneller.
DIRECT_SECTIONS_ABOVE = 10

#: Obergrenze der Threads für die Stützsuche. Sechzehn statt acht brachten die
#: 200 Kandidaten auf dieser Maschine ans gemessene Minimum. Die vollständige
#: Analyse hat nach den Abkürzungen darunter kleinere Aufträge; dort sind zehn
#: schneller (Median 291 statt 304 ms bei exakt 200 000 Dreiecken).
#:
#: **Sechs statt zehn für die vollständige Messung** (19.09.2026). Schwere
#: Schichten vertragen weniger Nachbarn: Ein Gitterbecher mit 94 990 Dreiecken
#: und Schichten aus 7 000 Punkten brauchte mit 10 Arbeitern 11,4 s, mit 6 10,0,
#: mit 4 9,3 — während die glatte Kugel mit 327 680 Dreiecken mit 4 Arbeitern
#: 176 ms brauchte, mit 6 und 10 gleichermaßen 139. Sechs verliert an beiden
#: Enden am wenigsten; den wirklichen Engpass hinter der Sättigung kennt
#: weiterhin niemand (RM, 16.09.2026).
MAX_WORKERS = 16
FULL_WORKERS = 6

#: Wie viele Arbeiter die örtlichen Säulen- und Kanalfragen unter sich aufteilen.
SUPPORT_WORKERS = 6

#: So viele Schichten misst ein Arbeiter in einem Block (:func:`_measure_batch`).
#: Groß genug, dass jeder GEOS-Aufruf ein Feld statt einer Schicht fragt;
#: klein genug, dass sechs Arbeiter an 400 Schichten gleichmäßig zu tun haben
#: und ein Abbruch nach höchstens einem Block je Arbeiter greift.
BATCH_LAYERS = 16

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
    islands: ShapelyPolygon | None = None
    """Die Inseln selbst — damit der Ergebnisaufbau sie nicht ein zweites Mal schneidet."""
    taper_length: float = 0.0
    """Wie viel Außenkontur auf einem Keil liegt (:func:`taper_length`)."""


def slice_body(
    mesh: MeshData,
    layer_height: float = 0.2,
    detail: Detail = "full",
    *,
    footing_height: float | None = None,
    first_layer_height: float | None = None,
    overhang_angle: float | None = None,
    bridge_from: float | None = None,
    cancelled: CancelToken | None = None,
    support_volume: bool = True,
    with_layers: bool = True,
) -> SliceResult:
    """Schneidet den Körper in Schichten und misst jede (§22.1, §22.2).

    ``support_volume=False`` lässt die Stützsäulen aus (:func:`_support_volume`)
    und meldet null: Die Druckvorschläge lesen sie nicht, und an einem
    Gitterbecher mit 94 990 Dreiecken waren die Säulen 6,7 der 20 Sekunden,
    die der Druckdialog auf seine Vorschläge wartete (19.09.2026). Wer die Zahl
    braucht — Schätzung, Orientierungssuche, Analysekarte —, lässt den
    Schalter stehen; eine Null ist dort keine Aussage über den Körper, sondern
    eine über den Aufrufer, und sie steht deshalb nur da, wo niemand sie liest.

    ``detail="support"`` misst nur, was die Stützen brauchen: Überhänge,
    Inseln und die Flächen. Die Orientierungssuche ruft das zweihundertmal auf
    und liest genau eine Zahl daraus (§28.2) — Strukturbreiten für einen
    Körper zu rechnen, der gleich wieder gedreht wird, ist Arbeit, die niemand
    ansieht.

    ``footing_height`` ist die Höhe über der Unterkante, in der die
    **Aufstandsfläche** gemessen wird — und sie gehört nicht der Suche,
    sondern dem Druck. Ohne sie ist ``first_layer_area`` die Fläche des ersten
    Schnitts, und der liegt eine halbe *Such*-Schichthöhe über dem Boden: Eine
    Kugel mit R = 20 steht bei 1,0 mm Suchhöhe auf 54 mm² und bei 0,2 mm auf
    4,6 — dieselbe Kugel, dieselbe Lage, und ``stands()`` fällt einmal so und
    einmal anders aus (§22.3). Wer die Schichthöhe des Druckers kennt, gibt
    ihre Hälfte hier herein und bekommt eine Zahl, die nur noch am Körper
    hängt.

    ``bridge_from`` ist die Breite, ab der eine ungestützte Fläche als Brücke
    zählt — zwei Extrusionsbahnen, also ``Profile.minimum_wall_thickness``
    (Regel 7, RM-097). Ohne Angabe gilt :data:`BRIDGE_FROM`, der runde
    Millimeter für einen Aufrufer ohne Profil. Gelesen wird sie nur bei
    ``detail="full"``: Die Stützenmessung kennt keine Brücken.

    ``with_layers=False`` gibt nur die Zahlen zurück — Stützvolumen und
    Aufstandsfläche — und keine Schichten (``layers`` bleibt leer). Die
    Orientierungssuche und die Nahtsuche von *Modell teilen* lesen nichts
    anderes; die Schichten in Konturen zurückzuübersetzen kostete an der
    großen Hälfte des Laptop-Ständers ein Zehntel jeder Beurteilung (RM-266).
    Die Zahlen sind dieselben, bitgleich. Die Inselfrage bleibt: Sie auszulassen
    sparte an einer Hälfte der Waschschüssel drei Prozent der Messung.

    ``first_layer_height`` setzt zusätzlich das tatsächliche Druckraster:
    Die erste Schnittmitte liegt auf seiner halben Höhe, die zweite eine
    halbe normale Schicht über seiner Oberkante. Ohne Angabe bleibt das gleichmäßige Raster
    der Orientierungssuche unverändert. Eine explizite ``footing_height``
    darf die reine Standflächenmessung weiterhin unabhängig davon wählen.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
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
    if first_layer_height is not None and (
        not math.isfinite(first_layer_height) or first_layer_height <= EPS_GEOM
    ):
        raise ValidationError(
            "first_layer_height",
            _("Die Schichthöhe muss größer als null sein."),
            value=first_layer_height,
            constraint="layer_height",
        )

    angle = OVERHANG_LIMIT_DEGREES if overhang_angle is None else overhang_angle
    if not math.isfinite(angle) or not 0.0 < angle < 90.0:
        raise ValidationError(
            "overhang_angle",
            _("Wählen Sie für die Überhanggrenze einen Winkel zwischen 0 und 90 Grad."),
            constraint="range",
        )
    span = BRIDGE_FROM if bridge_from is None else bridge_from
    if not math.isfinite(span) or span <= 0.0:
        # Dieselbe Sorgfalt wie beim Winkel darüber: Die Zahl kommt aus einem
        # Profil, und ein eigenes ``materials.toml`` bringt diesen Fall bis in
        # die Oberfläche (Regel 17).
        raise ValidationError(
            "bridge_from",
            _("Die Brückenbreite muss größer als null sein."),
            value=bridge_from,
            constraint="range",
        )
    overhang_factor = math.tan(math.radians(angle))
    bounds = mesh.bounds
    low, high = bounds.minimum[2], bounds.maximum[2]
    if high - low <= EPS_GEOM:
        return SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")

    layers: list[LayerInfo] = []

    # Eine halbe Schicht über dem Boden: der erste Schnitt muss Material treffen.
    if first_layer_height is None:
        heights = np.arange(low + layer_height / 2.0, high, layer_height)
    else:
        first = low + first_layer_height / 2.0
        heights = np.concatenate(
            (
                np.array([first] if first < high else [], dtype=float),
                np.arange(low + first_layer_height + layer_height / 2.0, high, layer_height),
            )
        )
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
    sections, section_contours = _cross_sections(
        mesh, heights, capture_contours=with_layers, cancelled=cancelled
    )
    measured = _measure_all(
        sections,
        layer_height,
        detail,
        first_layer_height=first_layer_height,
        overhang_factor=overhang_factor,
        bridge_from=span,
        cancelled=cancelled,
    )
    support = (
        _support_volume(
            sections,
            measured,
            layer_height,
            first_layer_height=first_layer_height,
            cancelled=cancelled,
        )
        if support_volume
        else 0.0
    )

    if not with_layers:
        first_area = next(
            (
                metrics.area
                for shape, metrics in zip(sections, measured, strict=True)
                if shape is not None and not shape.is_empty and metrics is not None
            ),
            None,
        )
        return SliceResult(
            layers=(),
            support_volume=float(support),
            first_layer_area=_footing_area(
                mesh, low, footing_height, first_area, cancelled=cancelled
            ),
            source="internal",
        )

    for z, shape, metrics, contours in zip(
        heights, sections, measured, section_contours, strict=True
    ):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if shape is None or shape.is_empty or metrics is None:
            continue

        layers.append(
            LayerInfo(
                z=float(z),
                # Beim nativen Ein-Ring-Weg liegen genau diese Zahlen schon
                # vor. Sie erneut aus GEOS herauszukopieren kostete an 400
                # Kugelschichten rund 40 ms. Mehrteilige Schnitte bleiben auf
                # dem allgemeinen Weg und kommen ebenfalls hier fertig an.
                contours=_to_polygons(shape) if contours is None else contours,
                area=metrics.area,
                overhang_area=metrics.overhang_area,
                islands=()
                if metrics.island_area <= EPS_GEOM
                or metrics.islands is None
                or metrics.islands.is_empty
                else _to_polygons(metrics.islands),
                min_width=metrics.min_width,
                overhangs=()
                if metrics.overhang is None or metrics.overhang.is_empty
                else _to_polygons(metrics.overhang),
                bridge_width=metrics.bridge_width,
                taper_length=metrics.taper_length,
            )
        )

    return SliceResult(
        layers=tuple(layers),
        support_volume=float(support),
        first_layer_area=_footing_area(
            mesh, low, footing_height, layers[0].area if layers else None, cancelled=cancelled
        ),
        source="internal",
    )


def _footing_area(
    mesh: MeshData,
    low: float,
    footing_height: float | None,
    first_area: float | None,
    *,
    cancelled: CancelToken | None = None,
) -> float:
    """Die Fläche, auf der das Teil steht.

    ``first_area`` ist die Fläche der ersten Schicht mit Material, ``None``
    ohne eine. Ohne ``footing_height`` gilt sie — was die Suche ohnehin schon
    hat. Mit ``footing_height`` ein eigener Schnitt auf der
    genannten Höhe: Ein Schnitt mehr auf zweihundert Kandidaten fällt neben
    fünfzig bis zweihundert je Kandidat nicht auf, und er nimmt der Zahl die
    Abhängigkeit von der Suchauflösung.
    """
    if first_area is None:
        return 0.0
    if footing_height is None:
        return first_area
    sections, _ = _cross_sections(
        mesh,
        np.array([low + footing_height], dtype=float),
        capture_contours=False,
        cancelled=cancelled,
    )
    shape = sections[0]
    return 0.0 if shape is None or shape.is_empty else float(shape.area)


def _material_cross(shape: ShapelyPolygon | None) -> manifold3d.CrossSection:
    """Eine vorhandene Materialfläche als gerichtete Clipper-Konturen, ohne Vereinfachung."""
    if shape is None or shape.is_empty:
        return manifold3d.CrossSection()
    oriented = shapely.orient_polygons(shape, exterior_cw=False)
    rings = []
    for part in _areas_of(oriented):
        rings.append(np.asarray(part.exterior.coords, dtype=np.float64)[:-1])
        rings.extend(np.asarray(ring.coords, dtype=np.float64)[:-1] for ring in part.interiors)
    return manifold3d.CrossSection(rings, manifold3d.FillRule.Positive)


def _support_volume(
    sections: list[ShapelyPolygon | None],
    measured: list[LayerMetrics | None],
    layer_height: float,
    *,
    first_layer_height: float | None = None,
    cancelled: CancelToken | None = None,
) -> float:
    """Disjunkte Stützsäulen unabhängig bis zum Material oder Bett verfolgen.

    Ein neuer Überhang liegt im Material seiner Schicht; die älteren Säulen
    wurden dort schon abgeschnitten. Jede Säule kann deshalb unabhängig
    absteigen. Nur Schichten, die ihren ursprünglichen Umriss treffen,
    schneiden sie; freie Höhenabschnitte tragen dieselbe Fläche weiter.
    Clipper bleibt der einzige Differenzkern, ohne Konturvereinfachung.
    """
    starts = [
        index
        for index, metrics in reversed(list(enumerate(measured)))
        if metrics is not None and metrics.overhang is not None and not metrics.overhang.is_empty
    ]
    if not starts:
        return 0.0
    floors: list[manifold3d.CrossSection] = []
    outlines: list[ShapelyPolygon | None] = []
    for section in sections[: starts[0]]:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        floor = _material_cross(section)
        floors.append(floor)
        outlines.append(_cross_shape(floor))
    floor_shapes = np.asarray(outlines, dtype=object)
    first = layer_height if first_layer_height is None else first_layer_height

    def height_until(index: int) -> float:
        if index < 0:
            return 0.0
        if index == 0:
            return first / 2.0
        return first + (index - 0.5) * layer_height

    def volume_of(index: int) -> float:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        metrics = measured[index]
        assert metrics is not None
        body = _material_cross(metrics.overhang)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        outline = _cross_shape(body)
        if outline is None:
            return 0.0
        # Nur die Säule besitzt diesen vorbereiteten Index. Die übrigen
        # Arbeiter lesen die unveränderten Schichtflächen.
        shapely.prepare(outline)
        hits = np.flatnonzero(shapely.intersects(outline, floor_shapes[:index]))[::-1]
        area = float(body.area())
        upper = index
        volume = 0.0
        for lower in hits.tolist():
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            volume += area * (height_until(upper) - height_until(lower + 1))
            body = body - floors[lower]
            area = float(body.area())
            upper = lower + 1
            if body.is_empty():
                break
        return volume + area * height_until(upper)

    if len(sections) < PARALLEL_FROM or len(starts) < 2:
        return math.fsum(volume_of(index) for index in starts)
    from concurrent.futures import ThreadPoolExecutor

    workers = _workers(SUPPORT_WORKERS)
    volumes: list[float] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(starts), workers):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            volumes.extend(pool.map(volume_of, starts[start : start + workers]))
    return math.fsum(volumes)


def _layer_step(index: int, layer_height: float, first_layer_height: float | None) -> float:
    """Abstand zur vorigen Schnittmitte, ganz unten zum Bett."""
    first_height = layer_height if first_layer_height is None else first_layer_height
    if index == 0:
        return first_height / 2.0
    if index == 1:
        return (first_height + layer_height) / 2.0
    return layer_height


def _areas_of(shape: ShapelyPolygon) -> list[ShapelyPolygon]:
    """Die flächigen Teile einer Geometrie, einzeln.

    Eine Differenz kann Linien zurückgeben, wo zwei Flächen sich nur berühren.
    Die tragen keine Fläche und keine Säule.
    """
    parts = getattr(shape, "geoms", [shape])
    return [part for part in parts if part.geom_type == "Polygon" and not part.is_empty]


def _lines_of(shape: Any) -> list[Any]:
    """Die Linienstücke einer Geometrie, einzeln — ohne Punkte, an denen sich
    ein Rand und eine Fläche nur berühren."""
    return [
        part
        for part in shapely.get_parts(shape)
        if part.geom_type == "LineString" and not part.is_empty
    ]


def _merged_lines(shape: Any) -> list[Any]:
    """Die Linienstücke einer Geometrie, wo sie aneinanderstoßen zusammengefügt."""
    lines = _lines_of(shape)
    if len(lines) < 2:
        return lines
    return _lines_of(shapely.line_merge(shapely.multilinestrings(lines)))


def _same_layer(shape: ShapelyPolygon, previous: ShapelyPolygon) -> bool:
    """Ob zwei aufeinanderfolgende Schnitte dieselbe Fläche sind.

    Drei billige Fragen zuerst — Fläche, Umfang, Hüllbox —, dann der Vergleich
    der Ecken: Beide Konturen werden von Punkten befreit, die auf einer
    Geraden liegen (die Diagonale einer senkrechten Wand schneidet jede Ebene
    woanders, die Wand selbst nicht), kanonisch geordnet und Punkt für Punkt
    verglichen. Wählt die Vereinfachung knapp an ihrer Toleranz andere Ecken,
    belegt erst die gegenseitige Überdeckung innerhalb der Geometrietoleranz
    die Gleichheit. Diese seltene Gegenprobe nimmt die ursprünglichen Konturen.
    """
    tolerance = SAME_LAYER_TOLERANCE
    if abs(float(shape.area) - float(previous.area)) > tolerance * max(1.0, float(shape.area)):
        return False
    if abs(float(shape.length) - float(previous.length)) > tolerance * max(
        1.0, float(shape.length)
    ):
        return False
    if any(
        abs(mine - theirs) > tolerance
        for mine, theirs in zip(shape.bounds, previous.bounds, strict=True)
    ):
        return False
    mine = shapely.normalize(shape.simplify(tolerance))
    theirs = shapely.normalize(previous.simplify(tolerance))
    if shapely.equals_exact(mine, theirs, tolerance=tolerance):
        return True
    return bool(
        shape.buffer(tolerance, quad_segs=1).covers(previous)
        and previous.buffer(tolerance, quad_segs=1).covers(shape)
    )


def _repeated(source: LayerMetrics, shape: ShapelyPolygon) -> LayerMetrics:
    """Die Zahlen einer Schicht, die genauso aussieht wie die darunter.

    Gegen eine identische Schicht darunter gibt es keinen Überhang, keine
    Insel und keine Brücke — ``shape.difference(shape.buffer(reach))`` ist
    leer, und genau das rechnete :func:`_measure_batch` aus. Die Strukturbreite und
    die Konturzahl hängen nur an der Fläche selbst und sind die der Quelle.
    """
    return LayerMetrics(
        z=0.0,
        area=float(shape.area),
        overhang_area=0.0,
        island_area=0.0,
        min_width=source.min_width,
        bridge_width=0.0,
        contour_count=source.contour_count,
        taper_length=source.taper_length,
    )


def _measure_all(
    sections: list[ShapelyPolygon | None],
    layer_height: float,
    detail: Detail,
    *,
    first_layer_height: float | None = None,
    overhang_factor: float = OVERHANG_ANGLE_FACTOR,
    bridge_from: float = BRIDGE_FROM,
    cancelled: CancelToken | None = None,
) -> list[LayerMetrics | None]:
    """Misst jede Schicht, auf so vielen Threads wie die Maschine hat.

    **Und jede nur einmal, solange sie dieselbe bleibt.** Ein Gehäuse, ein
    Organizer, ein Kabelkanal sind über weite Strecken senkrecht: Schnitt für
    Schnitt dieselbe Fläche, und jede davon kostete die volle Messung —
    Breitensuche und Brückensuche aus lauter Puffern. Gemessen am 19.09.2026
    an einem Gitterbecher mit 94 990 Dreiecken und 476 Schichten: 19,8 s für
    die Vorschläge im Druckdialog (Befund Robert: „Vorschläge beim Slicen
    dauern ewig"). Eine Schicht, die :func:`_same_layer` ihrer Vorgängerin
    gleicht, bekommt deren Zahlen (:func:`_repeated`); gemessen wird nur, wo
    sich etwas ändert.

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

    **Der Keil wird an jeder :data:`TAPER_SAMPLE`. gemessenen Schicht
    gesucht**, die übrigen tragen den Wert der zuletzt gemessenen — die
    Schleife am Ende (``carried``) schreibt ihn fort, bevor die gleichen
    Schichten ihre Zahlen kopieren. Ein Keil ist eine Eigenschaft der Wand
    über ihre Höhe, und die Messung kostete an einer Vase ein Drittel der
    ganzen Analyse (:func:`taper_length`).
    """
    from concurrent.futures import ThreadPoolExecutor

    jobs: list[tuple[int, ShapelyPolygon, ShapelyPolygon | None, bool, bool]] = []
    # Schicht → die gemessene Schicht, deren Zahlen sie übernimmt.
    repeats: dict[int, int] = {}
    previous: ShapelyPolygon | None = None
    source = -1
    on_plate = True
    for index, shape in enumerate(sections):
        if shape is None or shape.is_empty:
            previous = None
            continue
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if previous is not None and source >= 0 and _same_layer(shape, previous):
            repeats[index] = source
        else:
            jobs.append((index, shape, previous, on_plate, len(jobs) % TAPER_SAMPLE == 0))
            source = index
        previous = shape
        on_plate = False

    results: list[LayerMetrics | None] = [None] * len(sections)
    if not jobs:
        return results

    def carried() -> list[LayerMetrics | None]:
        taper = 0.0
        for index, _shape, _below, _plate, sampled in jobs:
            measured = results[index]
            if measured is None:
                continue
            if sampled:
                taper = measured.taper_length
            elif taper > 0.0:
                results[index] = replace(measured, taper_length=taper)
        for index, origin in repeats.items():
            measured = results[origin]
            shape = sections[index]
            if measured is not None and shape is not None:
                results[index] = _repeated(measured, shape)
        return results

    def block(chunk: list[tuple[int, ShapelyPolygon, ShapelyPolygon | None, bool, bool]]) -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        measured = _measure_batch(
            [job[1] for job in chunk],
            [job[2] for job in chunk],
            [job[3] for job in chunk],
            [_layer_step(job[0], layer_height, first_layer_height) for job in chunk],
            detail,
            overhang_factor,
            bridge_from,
            [job[4] for job in chunk],
        )
        for job, metrics in zip(chunk, measured, strict=True):
            results[job[0]] = metrics

    if len(jobs) < PARALLEL_FROM:
        for start in range(0, len(jobs), BATCH_LAYERS):
            block(jobs[start : start + BATCH_LAYERS])
        return carried()

    # **Die Zahl der Arbeiter ist am Prüfkörper gemessen und trägt nicht
    # überall.** Gemessen am 16.09.2026 an einer 200 mm hohen Waschschüssel
    # (215 074 Dreiecke, 1000 Schichten): 60 s mit zehn Arbeitern, 49 s ganz
    # ohne, **39 s mit zweien**. Am Prüfkörper dieser Suite (200 000 Dreiecke,
    # 400 Schichten) ist es umgekehrt: 287 ms mit zehn, 460 ms mit zweien.
    #
    # Die Punktzahl je Schicht erklärt das nicht — 812 gegen 971 —, wohl aber
    # der Preis je Schicht: 39,5 ms gegen 0,72 ms, Faktor fünfzig. Eine
    # gekrümmte Wand macht `buffer` und `difference` teuer, und zehn solche
    # Aufrufe nebeneinander sättigen offenbar etwas anderes als die Kerne.
    # Bündeln in Blöcke half nicht (gemessen: 60,2 s statt 59,9 s), die
    # Warteschlange ist es also nicht.
    #
    # Eine Zahl, die beide Fälle gewinnt, gibt es damit nicht, und eine
    # Heuristik über die Schichtzahl wäre an zwei Punkten geraten. Die Marke
    # bleibt, bis jemand den wirklichen Engpass misst (RM, 16.09.2026).
    #
    # Seit dem 23.09.2026 (RM-201) bekommt jeder Arbeiter einen Block von
    # höchstens :data:`BATCH_LAYERS` Schichten, gestapelt gemessen
    # (:func:`_measure_batch`). Das Bündeln, das am 16.09. nichts brachte,
    # verteilte nur die Aufträge anders; jetzt fragt jeder GEOS-Aufruf einen
    # ganzen Block, und der Interpreter-Lock wird je Block statt je Schicht
    # verhandelt.
    workers = _workers(FULL_WORKERS if detail == "full" else MAX_WORKERS)
    size = max(1, min(BATCH_LAYERS, math.ceil(len(jobs) / (workers * 3))))
    chunks = [jobs[start : start + size] for start in range(0, len(jobs), size)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        if cancelled is None:
            list(pool.map(block, chunks))
        else:
            # Höchstens ein Block je Arbeiter liegt zwischen zwei Fragen.
            # Der Kontextmanager wartet beim Abbruch nur auf diesen begrenzten
            # Satz laufender GEOS-Aufrufe, nicht auf alle übrigen Schichten.
            for start in range(0, len(chunks), workers):
                cancelled.raise_if_cancelled()
                list(pool.map(block, chunks[start : start + workers]))
    return carried()


def _workers(limit: int) -> int:
    """Ein Thread je Kern, in Maßen. Mehr fügt nur Umschalten hinzu."""
    import os

    return max(1, min(limit, (os.cpu_count() or 2)))


def cross_section(mesh: MeshData, z: float) -> ShapelyPolygon | None:
    """Eine Ebene durch das Netz, als Polygon mit Löchern (§22.1).

    Öffentlich, weil die Analysekarten den Körper aus diesen Schnitten rastern
    (§18.4) — derselbe Schnitt, zweimal benutzt.
    """
    return cross_sections(mesh, np.array([z], dtype=float))[0]


def cross_sections(
    mesh: MeshData, heights: Any, *, cancelled: CancelToken | None = None
) -> list[ShapelyPolygon | None]:
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

    **Die Höhen dürfen in jeder Folge kommen.** Das Einsortieren sucht sie
    über ``searchsorted`` und verlangt sie aufsteigend; ungeordnet kamen
    Schnitte leer zurück, ohne Fehler (am Nachbau des Besenhalters, 0.5.2).
    Geschnitten wird deshalb hier aufsteigend, zurück kommt jeder Schnitt an
    der Stelle seiner Höhe.
    """
    wanted = np.asarray(heights, dtype=float)
    order = np.argsort(wanted, kind="stable")
    sections = _cross_sections(mesh, wanted[order], capture_contours=False, cancelled=cancelled)[0]
    result: list[ShapelyPolygon | None] = [None] * len(order)
    for target, section in zip(order, sections, strict=True):
        result[int(target)] = section
    return result


def _cross_sections(
    mesh: MeshData,
    heights: Any,
    *,
    capture_contours: bool,
    cancelled: CancelToken | None = None,
    shell_source: tuple[MeshData, np.ndarray] | None = None,
) -> tuple[list[ShapelyPolygon | None], list[tuple[Polygon, ...] | None]]:
    """Schnitte und optional ihre bereits vorhandenen Kernkonturen.

    ``cross_sections`` braucht nur GEOS-Geometrien. ``slice_body`` muss sie
    danach in :class:`Polygon` zurückübersetzen; beim häufigen Ein-Ring-Fall
    wären das dieselben Koordinaten zum zweiten Mal. Der private gemeinsame
    Weg hält sie deshalb nur für diesen Aufrufer fest.
    """
    heights = np.asarray(heights, dtype=float)
    empty: list[ShapelyPolygon | None] = [None] * len(heights)
    no_contours: list[tuple[Polygon, ...] | None] = [None] * len(heights)
    if not len(heights) or not len(mesh.raw.faces):
        return empty, no_contours

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    direct = _solid_sections(mesh, heights, cancelled=cancelled)
    if direct is not None:
        result: list[ShapelyPolygon | None] = []
        contours: list[tuple[Polygon, ...] | None] = []
        for rings in direct:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            shape = _shape_from_rings(rings)
            result.append(shape)
            contours.append(_to_polygons(shape) if capture_contours and shape is not None else None)
        return result, contours
    points, layers, nodes = _plane_segments(mesh, heights, cancelled=cancelled)
    if not len(points):
        return empty, no_contours

    # Beide Segmentwege liefern bereits schichtweise. Der native Kern füllt
    # dafür je Schicht einen eigenen Bereich und erspart hier den globalen
    # stabilen Sort über mehrere hunderttausend Segmente.
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
    result = []
    contours = []
    for start, end in zip(starts, ends, strict=True):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if end <= start:
            result.append(None)
            contours.append(None)
            continue
        shape, own = _polygon_with_contours(
            points[start:end],
            nodes[start:end],
            capture_contours=capture_contours,
            shell_ids=lambda edges: _shells_for_edges(mesh, edges, shell_source, cancelled),
        )
        result.append(shape)
        contours.append(own)
    return result, contours


def _shells_for_edges(
    mesh: MeshData,
    edges: np.ndarray,
    source: tuple[MeshData, np.ndarray] | None,
    cancelled: CancelToken | None,
) -> np.ndarray:
    """Netzschalen nur bei freier inverser Hülle, samt Herkunft eines Kontaktbands.

    Geteilt werden Kanten nach Eckennummern. Räumlich gleiche Kanten anderer
    Schalen bleiben getrennt. Im Netzcache liegen nur Felder, kein nativer Kern.
    """
    if source is not None:
        original, used = source
        ends = used[np.column_stack((edges // mesh.vertex_count, edges % mesh.vertex_count))]
        edges = ends.min(axis=1) * original.vertex_count + ends.max(axis=1)
        mesh = original
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    body = mesh.raw
    key = "solidon_slice_shell_edges"
    saved = body._cache[key]
    if saved is None:
        labels = kernel_process.run(
            "component_labels",
            {"edges": np.asarray(body.face_adjacency, dtype=np.int64)},
            {"count": mesh.triangle_count},
            weight=mesh.triangle_count,
            cancelled=cancelled,
        )[0]["labels"]
        unique = np.asarray(body.edges_unique, dtype=np.int64)
        owners = np.empty(len(unique), dtype=np.int64)
        owners[body.edges_unique_inverse] = np.repeat(labels, 3)
        codes = unique[:, 0] * mesh.vertex_count + unique[:, 1]
        order = np.argsort(codes)
        saved = codes[order], owners[order]
        body._cache[key] = saved
    codes, owners = saved
    return np.asarray(owners[np.searchsorted(codes, edges)], dtype=np.int64)


def _solid_sections(
    mesh: MeshData, heights: np.ndarray, *, cancelled: CancelToken | None = None
) -> list[list[np.ndarray]] | None:
    """Direkte Schnitte als Felder; große Kernaufrufe laufen im Hilfsprozess."""
    if len(heights) <= DIRECT_SECTIONS_ABOVE:
        return None
    # Ob der Volumenkern dieses Netz unverändert übernehmen darf, hängt
    # nicht von den Schnitthöhen ab. Abgelehnte Schalen brauchen diese
    # Umwandlung bis zur nächsten Netzänderung nicht erneut zu bezahlen.
    rejected_key = "solidon_slice_solid_rejected"
    if mesh.raw._cache[rejected_key] is True:
        return None
    # Kontaktprüfungen reichen offene Dreiecksbänder herein. Sie tragen
    # gültige Schnitte, aber keinen Volumenkern; dessen nativer Aufbau kann
    # an solchen Ausschnitten bereits vor der Statusantwort abbrechen.
    if not mesh.is_watertight or not mesh.raw.is_winding_consistent:
        return None
    arrays, values = kernel_process.run(
        "slice_sections",
        {
            "vertices": np.asarray(mesh.raw.vertices),
            "faces": np.asarray(mesh.raw.faces),
            "heights": heights,
        },
        {"volume": mesh.volume, "volume_band": EPS_GEOM * mesh.area},
        weight=mesh.triangle_count,
        cancelled=cancelled,
    )
    if not values["usable"]:
        mesh.raw._cache[rejected_key] = True
        return None
    rings = np.split(arrays["coordinates"], np.cumsum(arrays["sizes"])[:-1])
    result: list[list[np.ndarray]] = [[] for height in heights]
    for ring, owner in zip(rings if len(arrays["sizes"]) else [], arrays["owners"], strict=True):
        result[int(owner)].append(ring)
    return result


def _cross_shape(section: manifold3d.CrossSection) -> ShapelyPolygon | None:
    """Clipper-Ringe sind vereinigt und gerichtet; die Tiefe ordnet nur Löcher zu."""
    return _shape_from_rings(section.to_polygons())


def _shape_from_rings(rings: list[np.ndarray]) -> ShapelyPolygon | None:
    """Vereinigte Clipper-Ringe mit positiven Hüllen und negativen Löchern."""
    if not rings:
        return None
    if len(rings) == 1:
        return ShapelyPolygon(rings[0])
    coordinates = np.concatenate(rings)
    ring_of = np.repeat(np.arange(len(rings)), [len(ring) for ring in rings])
    if _chain is not None and hasattr(_chain, "ring_nesting"):
        metadata = _chain.ring_nesting(
            np.ascontiguousarray(coordinates, dtype=float),
            np.ascontiguousarray(ring_of, dtype=np.int64),
        )
        if metadata is not None:
            _starts, _ends, areas, depths, parents = metadata
            positive = areas > 0.0
            if np.array_equal(positive, depths % 2 == 0):
                parts = [
                    ShapelyPolygon(
                        rings[number],
                        [rings[hole] for hole in np.flatnonzero(parents == number)],
                    )
                    for number in np.flatnonzero(positive)
                ]
                candidate = parts[0] if len(parts) == 1 else MultiPolygon(parts)
                if candidate.is_valid:
                    return cast(ShapelyPolygon, candidate)
    outlines = shapely.polygons(shapely.linearrings(coordinates, indices=ring_of))
    positive = shapely.is_ccw(shapely.get_exterior_ring(outlines))
    shells = outlines[positive]
    holes = outlines[~positive]
    assigned: list[list[Any]] = [[] for shell in shells]
    if len(holes):
        # Ein Loch gehört zur kleinsten Hülle, die seine ganze Fläche trägt.
        # Ein Punkt allein könnte auf einer Materialinsel im Loch liegen.
        child, parent = shapely.STRtree(shells).query(holes, predicate="covered_by")
        areas = shapely.area(shells)
        for number, hole in enumerate(holes):
            candidates = parent[child == number]
            if len(candidates):
                owner = int(candidates[np.argmin(areas[candidates])])
                assigned[owner].append(hole.exterior)
    parts = [
        _repaired(ShapelyPolygon(shell.exterior, inner))
        for shell, inner in zip(shells, assigned, strict=True)
    ]
    if len(parts) == 1:
        return parts[0]
    # Clipper hat diese Flächen bereits vereinigt. Nur eine Reparatur an
    # einer Berührstelle kann ihre Trennung verändern; der gültige Regelfall
    # braucht deshalb keine zweite Boolesche Rechnung in GEOS.
    combined = MultiPolygon(shapely.get_parts(parts).tolist())
    return cast(ShapelyPolygon, combined if combined.is_valid else unary_union(parts))


def _plane_segments(
    mesh: MeshData, heights: Any, *, cancelled: CancelToken | None = None
) -> tuple[Any, Any, Any]:
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
    # Ein ignorierter lokaler Bau kann älter als die Quelle sein. Der
    # Quellklon bleibt dann funktionsfähig und sagt über die übersprungenen
    # Vergleichstests klar, dass ``build_slice_core.py`` erneut laufen muss.
    # Version 2 bestätigte den optionalen Abbruchrückruf als fünftes Argument,
    # Version 3 die gerichteten Segmente.
    if _chain is not None and getattr(_chain, "PLANE_SEGMENTS_API", None) == PLANE_SEGMENTS_API:
        # ``ascontiguousarray`` kann einen schreibgeschützten Puffer unverändert
        # zurückgeben; der übersetzte Kern braucht schreibbare Speicherbereiche.
        args = (
            np.require(mesh.raw.vertices, dtype=np.float64, requirements=["C", "W"]),
            np.require(mesh.raw.faces, dtype=np.int64, requirements=["C", "W"]),
            np.require(heights, dtype=np.float64, requirements=["C", "W"]),
            EPS_GEOM,
        )
        if cancelled is None:
            return cast(tuple[Any, Any, Any], _chain.plane_segments(*args))
        return cast(
            tuple[Any, Any, Any],
            _chain.plane_segments(*args, cancelled.raise_if_cancelled),
        )

    if cancelled is not None:
        return _plane_segments_in_chunks(mesh, heights, cancelled)

    return _plane_segments_numpy(mesh, heights)


def _plane_segments_in_chunks(
    mesh: MeshData, heights: Any, cancelled: CancelToken
) -> tuple[Any, Any, Any]:
    """NumPy-Rückfallweg in begrenzten, abbrechbaren Flächenblöcken."""
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    parts: list[tuple[Any, Any, Any]] = []
    for start in range(0, len(faces), 16_384):
        cancelled.raise_if_cancelled()
        parts.append(_plane_segments_numpy(mesh, heights, face_slice=slice(start, start + 16_384)))
    cancelled.raise_if_cancelled()
    nonempty = [part for part in parts if len(part[0])]
    if not nonempty:
        return _no_segments()
    points = np.concatenate([part[0] for part in nonempty])
    layers = np.concatenate([part[1] for part in nonempty])
    nodes = np.concatenate([part[2] for part in nonempty])
    order = np.argsort(layers, kind="stable")
    return points[order], layers[order], nodes[order]


def _plane_segments_numpy(
    mesh: MeshData, heights: Any, *, face_slice: slice | None = None
) -> tuple[Any, Any, Any]:
    """Vektorisierter Schnittweg, vollständig oder für einen Flächenblock."""
    all_faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    selected_faces = all_faces if face_slice is None else all_faces[face_slice]
    triangles = np.asarray(mesh.raw.vertices, dtype=float)[selected_faces]

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
    falls_first = above[keep]
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
    # :func:`_polygon_with_contours` nicht mehr zusammen: der Ring bleibt offen,
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
    corner_ids = selected_faces[faces[keep]]
    corner_from = corner_ids[rows, edges]
    corner_to = corner_ids[rows, (edges + 1) % 3]
    nodes = np.minimum(corner_from, corner_to) * len(mesh.raw.vertices) + np.maximum(
        corner_from, corner_to
    )

    # Die Richtung des Segments, wie im übersetzten Kern (RM-485): Es beginnt
    # auf der Kante, die im Umlauf des Dreiecks von oben nach unten führt. Bei
    # nach außen gerichteten Dreiecken liegt das Material dann links, ein
    # Außenring läuft gegen den Uhrzeigersinn und ein Hohlraum mit ihm.
    rising = ~falls_first[np.arange(len(edges)), edges[:, 0]]
    points[rising] = points[rising][:, ::-1]
    nodes[rising] = nodes[rising][:, ::-1]
    kept_points, kept_layers, kept_nodes = points, layers[keep], nodes
    order = np.argsort(kept_layers, kind="stable")
    return kept_points[order], kept_layers[order], kept_nodes[order]


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


def _pairs_up(ends: Any) -> Any | None:
    """Die Sortierung der Segmentenden, wenn jeder Knoten genau zwei trägt.

    Ein Sort genügt für drei Aufgaben: gleiche Knoten paaren, Grad zwei
    prüfen und ihre Nummern dicht machen. Vorher sortierte ``np.unique``
    zuerst die großen Kantennummern und ``argsort`` danach dieselben Enden
    noch einmal über ihre dichten Nummern — rund 20 ms für 400 Schichten.
    """
    if len(ends) < 6:
        return None
    order = np.argsort(ends, kind="stable")
    ordered = ends[order]
    if len(ordered) % 2 or np.any(ordered[0::2] != ordered[1::2]):
        return None
    # Vier gleiche Enden würden zwei scheinbar gültige Paare ergeben. Die
    # Grenze zwischen den Paaren deckt jeden Grad über zwei ab.
    if np.any(ordered[1:-1:2] == ordered[2::2]):
        return None
    return order


def _directions_agree(nodes: Any) -> bool:
    """Ob die gerichteten Segmente einer Schicht geschlossene Umläufe bilden.

    Jeder Knoten trägt genau zwei Segmente, und an jedem endet eines, während
    das andere beginnt. Nur dann hat die Umlaufzahl eines Punkts eine
    Bedeutung; eine offene Kante oder ein Dreieck gegen die Richtung seiner
    Nachbarn nimmt sie ihm (RM-485).
    """
    pairs = np.asarray(nodes, dtype=np.int64)
    if _pairs_up(pairs.reshape(-1)) is None:
        return False
    return bool(np.array_equal(np.sort(pairs[:, 0]), np.sort(pairs[:, 1])))


def _rings_from(points: Any, nodes: Any) -> tuple[Any, Any, bool, Any] | None:
    """Die geschlossenen Ringe einer Schicht, aus den Kantennummern verkettet.

    Ein Schnittpunkt gehört genau einer Kante, und eine Kante genau zwei
    Dreiecken. Damit trägt jeder Knoten genau zwei Segmente, und die Ringe
    sind schlicht die Zyklen dieser Zuordnung — kein Noden, keine
    Fließkommaentscheidung, keine Toleranz.

    ``None`` heißt „nicht hier entschieden": Die Voraussetzung trägt nicht,
    weil ein Knoten einen Grad ungleich zwei hat — eine offene Kante im Netz,
    ein verzweigtes Netz. Dann ist GEOS die richtige Antwort, denn es kommt
    auch mit dem zurecht, was hier nicht mehr eindeutig ist.

    Ohne ``_chain`` ordnet NumPy dieselben Zyklen nach Netzknoten
    (:func:`_numpy_rings`). Räumlich gleiche Punkte bleiben getrennt, wenn
    das Netz sie nicht verbindet — auch an einer Rücklaufnaht.

    Zurück kommen die Koordinaten in Ringreihenfolge, je Koordinate die
    Nummer ihres Rings — genau die Form, die ``shapely.linearrings`` erwartet —
    und ob jeder Ring in der Richtung seiner Segmente läuft. Nur dann sagt die
    Umlaufrichtung, wo Material ist. Zuletzt stehen die Kanten-IDs in derselben Reihenfolge.
    """
    ends = np.asarray(nodes, dtype=np.int64).reshape(-1)
    order = _pairs_up(ends)
    if order is None:
        return None
    if _chain is None:
        return _numpy_rings(points, nodes)

    dense_flat = np.empty(len(order), dtype=np.int64)
    dense_flat[order] = np.repeat(np.arange(len(order) // 2, dtype=np.int64), 2)
    dense = np.ascontiguousarray(dense_flat.reshape(-1, 2))

    # Je Knoten die beiden Segmente, die an ihm hängen. ``order`` nennt die
    # flachen Segmentenden; ganzzahlig durch zwei ist ihre Segmentnummer.
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
    #
    # Ein ungerader Schritt heißt: Ein Segment wurde von seinem Ende her
    # betreten, die Richtungen der Dreiecke widersprechen sich dort.
    oriented = not bool(np.any(walk[:written] & 1))
    return (
        np.round(points.reshape(-1, 2), 6)[walk[:written]],
        ring_of[:written],
        oriented,
        np.asarray(nodes).reshape(-1)[walk[:written]],
    )


def _numpy_rings(points: Any, nodes: Any) -> tuple[Any, Any, bool, Any] | None:
    """Gerichtete Zyklen rein aus Netzknoten, unabhängig von gleichen XY-Punkten.

    Zeigerverdopplung findet zuerst den kleinsten Segmentindex jedes Umlaufs,
    dann den Abstand zu diesem Anfang. Sortieren dieser Abstände ordnet die
    Ringe, ohne eine Python-Schleife je Segment und ohne räumliche Verkettung.
    Das erhält Rücklaufnähte und berührende Schalen genau wie der native Weg.
    """
    if not _directions_agree(nodes):
        return None
    count = len(points)
    ends = np.asarray(nodes, dtype=np.int64).reshape(-1)
    order = _pairs_up(ends)
    assert order is not None
    first, second = order[0::2], order[1::2]
    paired = np.empty(len(ends), dtype=np.int64)
    paired[first], paired[second] = second, first
    following = paired[1::2] // 2
    labels = np.arange(count)
    step = following.copy()
    for _level in range(count.bit_length()):
        labels = np.minimum(labels, labels[step])
        step = step[step]
    anchor = np.arange(count) == labels
    distance = np.where(anchor, 0, 1)
    step = np.where(anchor, np.arange(count), following)
    for _level in range(count.bit_length()):
        distance += distance[step]
        step = step[step]
    order = np.lexsort((-distance, labels))
    lengths = np.bincount(labels, minlength=count)
    order = order[lengths[labels[order]] >= 3]
    if not len(order):
        return None
    _, ring_of = np.unique(labels[order], return_inverse=True)
    return np.round(np.asarray(points)[order, 0], 6), ring_of, True, np.asarray(nodes)[order, 0]


def _positive_rings(
    coordinates: np.ndarray,
    ring_of: np.ndarray,
    edges: np.ndarray,
    shells: Callable[[np.ndarray], np.ndarray] | None,
) -> manifold3d.CrossSection | None:
    """Gerichtete Fläche; ein quer selbstschneidender Umlauf ist mehrdeutig.

    Eine Berührung oder eine zurücklaufende Naht kann dagegen eindeutig sein:
    Nur eine Seite der Umlaufzahl trägt Fläche. Belegt sind diese Nähte am
    Laptop-Ständer; die Acht mit zwei entgegengesetzten Lappen bleibt beim
    Reparaturweg über die losen Segmente.
    """
    starts = np.flatnonzero(np.r_[True, ring_of[1:] != ring_of[:-1]])
    rings = np.split(coordinates, starts[1:])
    linear_rings = shapely.linearrings(coordinates, indices=ring_of)
    simple = shapely.is_simple(linear_rings)
    for number in np.flatnonzero(~simple):
        ring = [rings[number]]
        positive = manifold3d.CrossSection(ring, manifold3d.FillRule.Positive)
        negative = manifold3d.CrossSection(ring, manifold3d.FillRule.Negative)
        if not positive.is_empty() and not negative.is_empty():
            return None
    outlines = shapely.polygons(linear_rings)
    following = np.arange(1, len(coordinates) + 1)
    following[np.r_[starts[1:], len(coordinates)] - 1] = starts
    x, y = coordinates[:, 0], coordinates[:, 1]
    positive_direction = np.add.reduceat(x * y[following] - x[following] * y, starts) > 0.0
    negative_indices = np.flatnonzero(~positive_direction)
    if len(negative_indices):
        positive_parts = [_repaired(outline) for outline in outlines[positive_direction]]
        positive_area = (
            positive_parts[0] if len(positive_parts) == 1 else unary_union(positive_parts)
        )
        free = [number for number in negative_indices if not positive_area.covers(outlines[number])]
        turn = np.zeros(len(rings), dtype=bool)
        turn[free] = True
        if free and len(rings) > 1:
            if shells is None:
                return None
            owners = shells(edges[starts])
            for owner in np.unique(owners[free]):
                own = owners == owner
                material = manifold3d.CrossSection(
                    [ring for ring, belongs in zip(rings, own, strict=True) if belongs],
                    manifold3d.FillRule.Negative,
                )
                for number in np.flatnonzero(positive_direction & ~own):
                    foreign = manifold3d.CrossSection([rings[number]], manifold3d.FillRule.Positive)
                    if not foreign.is_empty() and (foreign - material).is_empty():
                        # Getrennte inverse Innenwand oder Materialinsel?
                        # Ohne Herkunft ist das nicht entschieden. Die alte
                        # Verschachtelung bleibt der konservative Reparaturweg.
                        return None
            turn = np.isin(owners, owners[free])
        for number in np.flatnonzero(turn):
            rings[number] = rings[number][::-1]
    return manifold3d.CrossSection(rings, manifold3d.FillRule.Positive)


def _polygon_with_contours(
    points: Any,
    nodes: Any,
    *,
    capture_contours: bool,
    shell_ids: Callable[[np.ndarray], np.ndarray] | None = None,
) -> tuple[ShapelyPolygon | None, tuple[Polygon, ...] | None]:
    """Baut die gefüllte Fläche einer Schicht aus ihren losen Segmenten.

    Zuerst über die Kantennummern verkettet (:func:`_rings_from`); trägt deren
    Voraussetzung nicht, schließt GEOS die Ringe selbst aus den gerundeten
    Koordinaten. Gerichtete Ringe werden mit positiver Umlaufzahl vereinigt:
    Das Material liegt links, Hohlräume laufen andersherum als Außenränder.
    Ohne widerspruchsfreie Richtung bleibt die bisherige Verschachtelung
    mit Reparatur der losen Segmente.
    """
    chained = _rings_from(points, nodes)
    if chained is not None:
        coordinates, ring_of, oriented, edges = chained
        if oriented:
            nested = _nested(coordinates, ring_of, capture_contours=capture_contours, directed=True)
            if nested is not None:
                return nested
            section = _positive_rings(coordinates, ring_of, edges, shell_ids)
            if section is not None and not section.is_empty():
                shape = _cross_shape(section)
                return (
                    shape,
                    _to_polygons(shape) if capture_contours and shape is not None else None,
                )
        if len(ring_of) and ring_of[-1] == 0:
            # ``polygonize`` richtet einen einzelnen Außenring im Uhrzeigersinn
            # aus und schließt ihn. Beides ist hier ohne GEOS bekannt. Dieselbe
            # Reihenfolge hält Fläche, Kontur und Fließkommaergebnis bitgleich;
            # ein ungültiger Ring bleibt beim allgemeinen Reparaturweg.
            twice_area = np.sum(
                coordinates[:, 0] * np.roll(coordinates[:, 1], -1)
                - np.roll(coordinates[:, 0], -1) * coordinates[:, 1]
            )
            if twice_area > 0.0:
                coordinates = np.concatenate((coordinates[:1], coordinates[:0:-1]))
            shape = ShapelyPolygon(coordinates)
            if shape.is_valid:
                own: tuple[Polygon, ...] | None = None
                if capture_contours:
                    closed = np.vstack((coordinates, coordinates[0]))
                    own = (Polygon(outline=tuple(map(tuple, closed.tolist())), holes=()),)
                return shape, own
            # Eine Ebene genau durch eine Ecke kann einen Rand auf derselben
            # Linie hinaus- und zurückführen. Nach Kantenidentität ist das ein
            # geschlossener Ring, geometrisch aber eine Selbstberührung. Als
            # schon verketteten ``LinearRing`` kann ``polygonize`` die Stelle
            # nicht mehr auftrennen und liefert gar keine Fläche. Die losen
            # Segmente sind dafür der ausdrücklich vorgesehene GEOS-Weg.
            chained = None
        if chained is not None:
            nested = _nested(coordinates, ring_of, capture_contours=capture_contours)
            if nested is not None:
                return nested
            edges = shapely.linearrings(coordinates, indices=ring_of)
    if chained is None:
        rounded = np.round(points.reshape(-1, 2), 6)
        lengths = np.linalg.norm(rounded[1::2] - rounded[0::2], axis=1)
        usable = np.repeat(lengths > 0.0, 2)
        if not usable.any():
            return None, None
        kept = rounded[usable]
        edges = shapely.linestrings(kept, indices=np.repeat(np.arange(len(kept) // 2), 2))

    # polygonize verbindet Enden, teilt aber keine Kreuzung innerhalb einer
    # Kante. Dann verschwände etwa die Auflage des Kugelbandes vollständig,
    # oder neben einer gültigen Kontur nur ihr selbstschneidender Nachbar.
    network = shapely.multilinestrings(edges)
    if not shapely.is_simple(network):
        edges = shapely.get_parts(shapely.node(network))
    built = shapely.polygonize(edges)
    parts = [part for part in getattr(built, "geoms", []) if not part.is_empty]
    if not parts:
        return None, None
    if len(parts) == 1:
        shape = parts[0]
        return shape, _to_polygons(shape) if capture_contours else None

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
        return None, None
    shape = unary_union(solids)
    return shape, _to_polygons(shape) if capture_contours else None


def _nested(
    coordinates: np.ndarray,
    ring_of: np.ndarray,
    *,
    capture_contours: bool,
    directed: bool = False,
) -> tuple[ShapelyPolygon, tuple[Polygon, ...] | None] | None:
    """Mehrere verkettete Ringe zu Flächen mit Löchern — ohne ``polygonize``.

    Die Verkettung (:func:`_rings_from`) kennt die Ringe schon; was fehlt, ist
    nur, welcher in welchem liegt. Das beantwortet ein Punkt je Ring gegen die
    übrigen Ringe als Flächen, in einem Aufruf über einen räumlichen Index:
    gerade Tiefe ist Material, ungerade ein Loch, und ein Loch gehört dem
    Ring genau eine Ebene darüber. Ausgerichtet wird wie beim einzelnen Ring
    — Außenring im Uhrzeigersinn, Loch dagegen.

    **Warum nicht mehr über ``polygonize``.** An einer Hohlkugel hat jede
    Schicht zwei Ringe, und der allgemeine Weg baute daraus Flächen, prüfte
    Musterpunkte, vereinigte das Ergebnis und übersetzte es danach noch einmal
    in Konturen — 130 von 300 ms des Schnitts (23.09.2026, RM-201). Die
    Punkte sind dieselben; nur Anfangspunkt und Umlaufsinn eines Rings können
    sich von dem unterscheiden, was GEOS gewählt hätte, und das ändert eine
    Fläche höchstens in der letzten Stelle (``tests/test_slice_core.py``).

    ``None``, wenn das Ergebnis nicht gültig ist — ein Ring, der einen anderen
    berührt, eine Ebene durch eine Ecke —, dann bleibt der allgemeine Weg.
    """
    metadata = None
    if _chain is not None and hasattr(_chain, "ring_nesting"):
        metadata = _chain.ring_nesting(
            np.ascontiguousarray(coordinates, dtype=float),
            np.ascontiguousarray(ring_of, dtype=np.int64),
        )
    if metadata is None:
        starts = np.flatnonzero(np.r_[True, ring_of[1:] != ring_of[:-1]])
        ends = np.r_[starts[1:], len(ring_of)]
        if np.any(ends - starts < 3):
            return None
        following = np.arange(1, len(ring_of) + 1)
        following[ends - 1] = starts
        x, y = coordinates[:, 0], coordinates[:, 1]
        twice_area = np.add.reduceat(x * y[following] - x[following] * y, starts)
        outlines = shapely.polygons(shapely.linearrings(coordinates, indices=ring_of))
        held, holder = shapely.STRtree(outlines).query(
            shapely.points(coordinates[starts]), predicate="within"
        )
        inner = held != holder
        held, holder = held[inner], holder[inner]
        depth = np.bincount(held, minlength=len(starts))
        parent = np.full(len(starts), -1, dtype=np.int64)
        for child, container in zip(held.tolist(), holder.tolist(), strict=True):
            if depth[container] == depth[child] - 1:
                parent[child] = container
    else:
        starts, ends, twice_area, depth, parent = metadata
    rings = [coordinates[first:last] for first, last in zip(starts, ends, strict=True)]
    # Bei gerichteten Ringen muss auch die Materialseite zu ihrer Tiefe
    # passen. Zwei ineinanderliegende positive Hüllen sind kein Loch;
    # freie inverse Schalen und widersprüchliche Ränder bleiben bei Clipper.
    # Die abschließende Gültigkeitsprüfung belegt außerdem, dass die Ränder
    # weder sich selbst noch fremde Hüllen oder Löcher kreuzen.
    if directed and not np.array_equal(twice_area > 0.0, depth % 2 == 0):
        return None

    def turned(ring: np.ndarray, clockwise: bool, area: float) -> np.ndarray:
        if (area > 0.0) == clockwise:
            ring = np.concatenate((ring[:1], ring[:0:-1]))
        if directed:
            # Beide Verkettungen wählen andere Startkanten. Auch der doppelte
            # Schlusspunkt gehört zum Konturvertrag und muss derselbe sein.
            start = int(np.lexsort((ring[:, 1], ring[:, 0]))[0])
            ring = np.roll(ring, -start, axis=0)
        return ring

    shells = [number for number in range(len(rings)) if depth[number] % 2 == 0]
    holes: dict[int, list[np.ndarray]] = {number: [] for number in shells}
    for number in range(len(rings)):
        if depth[number] % 2:
            if parent[number] < 0 or int(parent[number]) not in holes:
                return None
            holes[int(parent[number])].append(
                turned(rings[number], False, float(twice_area[number]))
            )
    outer = {number: turned(rings[number], True, float(twice_area[number])) for number in shells}
    parts = [ShapelyPolygon(outer[number], holes[number]) for number in shells]
    shape = parts[0] if len(parts) == 1 else MultiPolygon(parts)
    if not shape.is_valid:
        return None
    if not capture_contours:
        return shape, None

    def closed(ring: np.ndarray) -> tuple[tuple[float, float], ...]:
        return tuple(map(tuple, np.vstack((ring, ring[:1])).tolist()))

    return shape, tuple(
        Polygon(outline=closed(outer[number]), holes=tuple(closed(hole) for hole in holes[number]))
        for number in shells
    )


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

    **Die Schnittfläche wird nur gerechnet, wo die Antwort offen ist.** Sie
    ist eine Überlagerung zweier fast gleicher Konturen, der teuerste Fall für
    GEOS: An einer Hohlkugelschicht kostete sie 2,8 bis 7 ms, je Schicht, für
    ein Ja, das niemand bezweifelte. Zwei billige Fragen entscheiden fast
    immer vorher. Berühren sich die Teile gar nicht, schwebt das obere. Und
    liegt ein Quadrat von zwei ``EPS_GEOM`` Kantenlänge um einen Punkt des
    oberen Teils ganz im Inneren beider, teilen sie mindestens diese Fläche —
    das Vierfache der Grenze. Beide Fragen stellt GEOS vektorisiert über alle
    Teile einer Schicht, zusammen unter 0,1 ms.
    """
    if previous is None or previous.is_empty:
        return shape
    return _islands_many(np.asarray([shape], dtype=object), np.asarray([previous], dtype=object))[0]


def _simplified(shape: ShapelyPolygon) -> ShapelyPolygon:
    """Die Kontur, so grob wie die Breitensuche sie verträgt.

    Ein hundertstel Millimeter ist ein Zehntel dessen, was die feinste Düse
    ablegen kann; was daran verschwindet, hat nie jemand gedruckt.

    **Vereinfacht wird die geordnete Kontur** (:func:`_canonical`), denn
    Douglas-Peucker hängt am Anfangspunkt eines Rings.
    """
    shape = _canonical(shape)
    coarse = shape.simplify(WIDTH_SIMPLIFY)
    return shape if coarse.is_empty or coarse.length <= EPS_GEOM else coarse


def _canonical(shape: ShapelyPolygon) -> ShapelyPolygon:
    """Dieselbe Fläche mit festgelegtem Anfangspunkt und Umlaufsinn jedes Rings.

    **Anfangspunkt und Umlaufsinn sind keine Eigenschaft des Schnitts**, sondern
    des Wegs, der ihn gebaut hat: Die Verkettung beginnt einen Ring an der
    ersten Kante in ihrer Liste, ``polygonize`` an einer eigenen. Die
    Vereinfachung vor der Breitensuche (Douglas-Peucker) und die Abtastung des
    Keils (alle Millimeter ab dem Anfangspunkt) hängen aber daran — gemessen
    am 23.09.2026: Derselbe Querschnitt mit anders begonnenen Ringen gab am
    Besteckeinsatz an 23 von 800 Schichten eine andere kleinste Breite und an
    65 einen anderen Keil. ``shapely.normalize`` legt beides fest, und damit
    rechnen der übersetzte und der GEOS-Weg dieselben Zahlen.
    """
    return shapely.normalize(shape)


def _width_outline(shape: ShapelyPolygon) -> ShapelyPolygon:
    """Die Kontur, an der :func:`minimum_width` öffnet — vereinfacht wie
    :func:`_simplified`, aber ohne die Topologie Punkt für Punkt zu hüten.

    Zwei Gründe, und beide sind gemessen (22.09.2026). Der erste ist die Zeit:
    Die topologietreue Vereinfachung kostete an einem Kugelschnitt mit 1 200
    Ecken 1,9 ms, Douglas-Peucker 0,14. Der zweite ist die Öffnung selbst:
    Ein ungeglätteter Schnitt trägt kurze Kanten zwischen zwei schwachen
    Knicken, die beim Erodieren verschwinden, und die Aufweitung setzt an ihre
    Stelle die Ecke der Nachbarn — die Öffnung ist dann nicht mehr die
    Identität, und jede Schicht müsste nachweisen, dass diese Ecken nichts
    verdecken (:func:`_protrusion`). Bis zu dieser Messung wurde die erste
    Frage deshalb am ungeglätteten Schnitt gestellt, die Suche danach am
    geglätteten; jetzt fragen beide dieselbe Kontur.

    Douglas-Peucker darf eine Struktur unter zwei Toleranzen Breite verlieren
    — die Suche löst sie ohnehin nicht auf. Wird das Ergebnis leer, ungültig
    oder eine andere Geometrieart, bleibt die topologietreue Vereinfachung.
    Über sieben Modelle aus ``F:\\3D Dateien`` und eine Kugel mit 200 000
    Dreiecken gab jede Schicht dieselbe Breite, bis auf eine um einen
    Halbierungsschritt; die Breitenmessung wurde dabei zwei- bis fünfmal
    schneller.
    """
    shape = _canonical(shape)
    coarse = shape.simplify(WIDTH_SIMPLIFY, preserve_topology=False)
    if coarse.is_empty or coarse.length <= EPS_GEOM or coarse.geom_type != shape.geom_type:
        return _simplified(shape)
    return coarse


def _without_slits(shape: ShapelyPolygon) -> ShapelyPolygon:
    """Dieselbe Fläche ohne Löcher, die schmaler sind als die
    Vereinfachungstoleranz.

    Ein Schnitt durch ein vernetztes Modell bringt gelegentlich einen Ring
    ohne Fläche mit — vier Punkte und ein milliardstel Quadratmillimeter, dort
    wo eine Kante sich selbst berührt. Für die Erosion ist so ein Ring kein
    Nichts: An einem Schlitz ohne Breite hat die gefaste Ecke keinen
    Schnittpunkt in der Nähe und schießt weit ins Material. Der Ringschnitt
    eines Pfostens aus dem Testkorpus verlor damit zwölf Quadratmillimeter,
    die es nicht gibt — und wäre als dünne Struktur gemeldet worden.

    Gemessen wird die mittlere Weite eines Lochs — vierfache Fläche über dem
    Umfang —, und zwar für alle Löcher einer Kontur in **einem** Aufruf. Eine
    Schicht durch eine Lochplatte bringt hundert Ringe mit; die einzeln zu
    fragen kostete mehr als die Messung, um die es geht.
    """
    parts = getattr(shape, "geoms", [shape])
    kept: list[ShapelyPolygon] = []
    changed = False
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        rings = _real_holes(part)
        if len(rings) == len(part.interiors):
            kept.append(part)
            continue
        changed = True
        kept.append(ShapelyPolygon(part.exterior, rings))
    if not changed:
        return shape
    if not kept:
        return ShapelyPolygon()
    return kept[0] if len(kept) == 1 else MultiPolygon(kept)


def _real_holes(part: ShapelyPolygon) -> list[Any]:
    """Die Ringe, die überhaupt eine Weite haben, die die Suche auflöst."""
    rings = list(part.interiors)
    if not rings:
        return rings
    holes = shapely.polygons(rings)
    wide = 4.0 * shapely.area(holes) >= WIDTH_SIMPLIFY * shapely.length(holes)
    return [ring for ring, keep in zip(rings, wide.tolist(), strict=True) if keep]


def _eroded(shape: ShapelyPolygon, radius: float) -> ShapelyPolygon:
    """Die Form, um ``radius`` nach innen gerückt — mit gefasten Ecken."""
    return shape.buffer(-radius, quad_segs=1, join_style="mitre")


def _narrow(material: ShapelyPolygon, bounds: tuple[float, float, float, float]) -> Any:
    """Der freie Raum um ``bounds``, zu eng für einen Kreis von ``CHANNEL_WIDTH``:
    das Material morphologisch um dessen Radius geschlossen (:func:`channel_space`)."""
    radius = CHANNEL_WIDTH / 2.0
    low_x, low_y, high_x, high_y = bounds
    near = shapely.clip_by_rect(
        material,
        low_x - 2.0 * radius,
        low_y - 2.0 * radius,
        high_x + 2.0 * radius,
        high_y + 2.0 * radius,
    )
    closed = near.buffer(radius, quad_segs=CHANNEL_QUAD_SEGMENTS).buffer(
        -radius, quad_segs=CHANNEL_QUAD_SEGMENTS
    )
    return closed.difference(material)


def _enclosed(material: ShapelyPolygon) -> Any:
    """Die Löcher der Fläche: freier Raum, ringsum von Material umschlossen."""
    return unary_union(
        [ShapelyPolygon(ring) for part in _areas_of(material) for ring in part.interiors]
    ).difference(material)


def _with_usable_holes(part: ShapelyPolygon, line_width: float) -> ShapelyPolygon:
    """Die Fläche ohne die Löcher, in denen keine Bahn samt Abstand Platz hat
    (:func:`channel_space`)."""
    holes = [
        ring for ring in part.interiors if not _eroded(ShapelyPolygon(ring), line_width).is_empty
    ]
    return ShapelyPolygon(part.exterior, holes)


def _opening_loss(shape: ShapelyPolygon, width: float, *, exact: bool = True) -> float:
    """Wie viel Fläche eine morphologische Öffnung dieser Breite wegnimmt.

    Öffnen heißt erodieren und wieder aufweiten. Mit gefasten Ecken
    (``mitre``) ist das für alles, was mindestens ``width`` breit ist, die
    Identität: Jede Kante wandert um dieselbe Strecke hinein und wieder
    heraus, jede Ecke kommt an ihren Schnittpunkt zurück. Übrig bleibt genau
    das, was schmaler war — und dessen Fläche ist die Antwort.

    **Die Öffnung liegt nicht immer in der Ausgangsform**, und das stand hier
    bis zum 22.09.2026 als Annahme. Wo die Erosion eine Stelle knapp
    übersteht, endet das erodierte Stück spitz, und die gefaste Aufweitung
    verlängert jede Spitze um bis zu fünf Radien — eine Nadel, die über die
    Form hinaus ins Freie ragt. In der Flächenbilanz gleicht sie den Verlust
    aus, den sie verdecken sollte: Am runden Ende eines Trennstegs verschwand
    so ein Ende unter einem Millimeter hinter 1,59 mm, an einer Hohlkugel
    wog die Bilanz eines fast vollständig abgetragenen Rings minus 35 mm².
    Und weil die Bilanz dabei nicht mehr monoton in der Weite ist, bestand
    ein Schreibtisch-Organizer die Frage bei 2,0 mm und scheiterte bei 0,5:
    Gemeldet wurde „mindestens 2 mm", gemessen sind 0,47. Zwei Dinge gelten
    deshalb:

    - **Splitter sind keine Struktur.** Ein erodiertes Stück, dessen mittlere
      Weite (vierfache Fläche über Umfang) unter :data:`WIDTH_SIMPLIFY`
      liegt, ist das, was von einer Wand genau auf der geprüften Weite übrig
      bleibt, und liegt unter der Auflösung der Suche. Es wird nicht
      aufgeweitet — das spart nebenbei die teuerste Aufweitung der ganzen
      Messung (168 Splitter einer Hohlkugelschicht, 54 ms für einen Puffer).
    - **Gezählt wird, was der Form fehlt**, nicht die Bilanz. Beide
      unterscheiden sich genau um das, was die Aufweitung außerhalb der Form
      dazugewinnt (:func:`_protrusion`). Die Bilanz ist also eine untere
      Schranke des Verlusts; reißt sie schon das Budget, steht das Nein fest.

    ``exact=False`` gibt nur die Bilanz zurück. Das genügt, wo allein ein
    **Nein** entschieden wird (der Teileweg in :func:`_survives_opening`).
    """
    return float(
        _opening_losses(np.asarray([shape], dtype=object), np.asarray([width]), exact=exact)[0]
    )


def _without_slivers(eroded: ShapelyPolygon) -> ShapelyPolygon:
    """Die erodierte Form ohne Stücke unter der Auflösung der Breitensuche.

    Dieselbe Grenze wie :func:`_real_holes` für Löcher, dieselbe mittlere
    Weite, in einem Aufruf über alle Stücke.
    """
    if eroded.is_empty:
        return eroded
    parts = np.asarray(list(getattr(eroded, "geoms", [eroded])), dtype=object)
    wide = 4.0 * shapely.area(parts) >= WIDTH_SIMPLIFY * shapely.length(parts)
    if wide.all():
        return eroded
    kept = [part for part, keep in zip(parts.tolist(), wide.tolist(), strict=True) if keep]
    if not kept:
        return ShapelyPolygon()
    return kept[0] if len(kept) == 1 else MultiPolygon(kept)


def _protrusion(
    opened: ShapelyPolygon, shape: ShapelyPolygon, allowance: float = math.inf
) -> float:
    """Die Fläche der Aufweitung außerhalb der Form, in mm².

    Im Normalfall ist die Öffnung die Identität: Jede Ecke kommt an ihre alte
    Stelle zurück, und beide Formen sind nach dem Ordnen Punkt für Punkt gleich
    — zehn Mikrosekunden an einem Ring mit 441 Ecken. Sonst werden die Ecken
    auf dem Raster von ``EPS_GEOM`` verglichen, und nur die ohne Entsprechung
    fragen nach ihrem Abstand zur Form. Wer draußen liegt, ist die Spitze einer
    Nadel.

    **Unter ``allowance`` genügt eine Schranke.** Die meisten Nadeln sind
    Rechenreste: Ein ungeglätteter Querschnitt durch eine Kugel mit 200 000
    Dreiecken verliert bei der Öffnung jede zehnte Ecke, weil kurze Kanten
    zwischen zwei schwachen Knicken verschwinden, und an ihrer Stelle steht
    die Ecke der Nachbarn um Zehntausendstel vor der Form. Jede
    zusammenhängende Folge äußerer Ecken liegt höchstens so weit draußen wie
    ihre fernste Ecke; ihre Fläche draußen ist nicht größer als dieser Abstand
    mal der Länge ihres Zugs samt der beiden Kanten zu den inneren Nachbarn.
    Reicht die Summe dieser Schranken nicht an ``allowance``, ist sie die
    Antwort — eine obere Schranke, die dieselbe Entscheidung trägt. Am Korpus
    (Kugel und sechs Modelle aus ``F:\\3D Dateien``, 1 654 Fragen, 22.09.2026)
    lag die echte Fläche nie darüber.

    **Sonst wird nur um die Nadeln herum gerechnet.** Eine Differenz über die
    ganze Form kostete an einem Baum mit Astspitzen 7 ms je Frage, und an
    seinen Spitzen stand in jeder Schicht eine Nadel. Jede Folge bekommt ein
    Fenster: die Hüllbox ihres Zugs, um ihren größten Abstand zur Form
    erweitert. Überlappende Fenster werden zusammengelegt, damit keine Fläche
    doppelt zählt.
    """
    if shapely.equals_exact(
        shapely.normalize(opened), shapely.normalize(shape), tolerance=EPS_GEOM
    ):
        return 0.0
    rings = shapely.get_rings(shapely.get_parts(opened))
    corners, ring_of = shapely.get_coordinates(rings, return_index=True)
    if not len(corners):
        return 0.0
    # Ein Ring wiederholt seinen ersten Punkt am Ende; für die Folgen zählt er
    # einmal.
    closing = np.r_[ring_of[1:] != ring_of[:-1], True]
    corners, ring_of = corners[~closing], ring_of[~closing]
    outside = _unknown_corners(corners, shapely.get_coordinates(shape))
    if outside.any():
        shapely.prepare(shape)
        candidates = np.flatnonzero(outside)
        outside[candidates] = ~shapely.dwithin(shape, shapely.points(corners[candidates]), EPS_GEOM)
    if not outside.any():
        return 0.0
    reach = np.zeros(len(corners))
    reach[outside] = shapely.distance(shape, shapely.points(corners[outside]))
    runs = _needle_runs(corners, ring_of, outside, reach)
    bound = float(np.dot(runs.reach, runs.length))
    if bound <= allowance:
        return bound
    margin = (runs.reach + EPS_GEOM)[:, None]
    windows = _disjoint_rectangles(np.hstack((runs.low - margin, runs.high + margin)))
    try:
        # ``clip_by_rect`` nimmt nur ein Rechteck je Aufruf.
        beyond = shapely.difference(
            np.asarray([shapely.clip_by_rect(opened, *window) for window in windows.tolist()]),
            np.asarray([shapely.clip_by_rect(shape, *window) for window in windows.tolist()]),
        )
    except shapely.errors.GEOSException:
        # Der schnelle Zuschnitt verspricht keine gültige Fläche, und eine
        # Aufweitung mit Nadeln liegt mit langen, fast parallelen Kanten an
        # der Form. Scheitert die Überlagerung daran, rechnet sie über das
        # Fenster als Fläche und auf dem Raster der Schnittpunkte (sechs
        # Nachkommastellen, :func:`_rings_from`), das ohnehin die Auflösung
        # der Konturen ist.
        boxes = shapely.box(*windows.T)
        try:
            beyond = shapely.difference(
                shapely.intersection(opened, boxes, grid_size=EPS_GEOM),
                shapely.intersection(shape, boxes, grid_size=EPS_GEOM),
                grid_size=EPS_GEOM,
            )
        except shapely.errors.GEOSException:
            # **Die Aufweitung selbst kann ungültig sein**: Zwei gefast
            # aufgeweitete Stücke überlappen sich, und ihr Multipolygon kreuzt
            # sich an einer Nadel. Dann scheitert auch das Raster („side
            # location conflict“), und die Ausnahme riss die ganze
            # Schichtanalyse mit (Wizard Tower, 04.10.2026). Als Fläche gültig
            # gemacht bleibt die Nadel, wo sie ist, und ihre Fläche zählt.
            valid = shapely.make_valid(opened, method="structure", keep_collapsed=False)
            beyond = shapely.difference(
                shapely.intersection(valid, boxes), shapely.intersection(shape, boxes)
            )
    return float(shapely.area(beyond).sum())


#: Bis zu welcher Koordinate die Rasterzellen einer Ecke als eine ganze Zahl
#: vergleichbar sind: 2³⁰ Zellen von ``EPS_GEOM``, gut ein Meter. Darüber
#: nimmt :func:`_unknown_corners` den langsameren Vergleich.
_GRID_REACH = float(2**30) * EPS_GEOM


def _unknown_corners(corners: np.ndarray, known: np.ndarray) -> np.ndarray:
    """Welche Ecken in keiner ``EPS_GEOM``-Zelle einer bekannten Ecke liegen.

    Zwei ganze Zahlen je Punkt werden zu einer zusammengelegt und über eine
    sortierte Liste gesucht; an 1 200 Ecken sind das 50 Mikrosekunden, ein
    Siebtel von ``np.isin`` über komplexe Schlüssel. Jenseits eines Meters
    reicht die Zahl dafür nicht, dann bleibt der komplexe Weg.
    """
    if max(float(np.abs(corners).max()), float(np.abs(known).max())) >= _GRID_REACH:
        return ~np.isin(_grid_keys(corners), _grid_keys(known))
    offset = 2**30
    shift = np.int64(2**31)

    def keys(points: np.ndarray) -> np.ndarray:
        cells = np.round(points / EPS_GEOM).astype(np.int64) + offset
        return cells[:, 0] * shift + cells[:, 1]

    table = np.sort(keys(known))
    wanted = keys(corners)
    found = np.minimum(np.searchsorted(table, wanted), len(table) - 1)
    return np.asarray(table[found] != wanted)


def _grid_keys(coordinates: np.ndarray) -> np.ndarray:
    """Je Punkt eine Zahl, gleich für Punkte in derselben ``EPS_GEOM``-Zelle.

    Komplex, weil ``np.isin`` darauf sortiert; über einen zusammengesetzten
    Datentyp war derselbe Vergleich viermal so teuer.
    """
    cells = np.round(coordinates / EPS_GEOM)
    return cells[:, 0] + 1j * cells[:, 1]


@dataclass(frozen=True, slots=True)
class _Runs:
    """Die Folgen äußerer Ecken einer Aufweitung (:func:`_needle_runs`)."""

    reach: np.ndarray
    """Je Folge der größte Abstand einer ihrer Ecken zur Form."""
    length: np.ndarray
    """Je Folge die Länge ihres Zugs samt der Kanten zu den inneren Nachbarn."""
    low: np.ndarray
    """Je Folge die untere linke Ecke der Hüllbox ihres Zugs."""
    high: np.ndarray
    """Je Folge die obere rechte Ecke der Hüllbox ihres Zugs."""


def _needle_runs(
    corners: np.ndarray, ring_of: np.ndarray, outside: np.ndarray, reach: np.ndarray
) -> _Runs:
    """Die zusammenhängenden Folgen äußerer Ecken, über alle Ringe in einem Zug.

    ``corners`` stehen ringweise in Umlaufreihenfolge, ohne den wiederholten
    Schlusspunkt. Jeder Ring wird so gedreht, dass er an einer inneren Ecke
    beginnt — dann zerfällt keine Folge am Ringschluss in zwei, und die
    Folgen sind zusammenhängende Abschnitte einer Liste. Ein Ring ganz
    draußen ist eine Folge; seine Nachbarn sind seine eigenen Enden.
    """
    count = len(corners)
    index = np.arange(count)
    first = np.r_[0, np.flatnonzero(np.diff(ring_of)) + 1]
    size = np.diff(np.r_[first, count])
    ring = np.repeat(np.arange(len(first)), size)
    start, length = first[ring], size[ring]
    position = index - start
    previous = start + (position - 1) % length
    following = start + (position + 1) % length

    # Je Ring die erste innere Ecke; ein Ring ganz draußen beginnt vorn.
    inside_rank = np.where(outside, count, position)
    offset = np.minimum.reduceat(inside_rank, first)
    offset[offset >= count] = 0
    rotated = start + (position + offset[ring]) % length
    flags = outside[rotated]
    opens = flags & ~np.r_[False, flags[:-1]]
    opens[first] = flags[first]
    members = rotated[flags]
    run_of = np.cumsum(opens)[flags] - 1
    heads = np.flatnonzero(np.r_[True, run_of[1:] != run_of[:-1]])
    tails = np.r_[heads[1:], len(members)] - 1

    entering = np.linalg.norm(corners[members] - corners[previous[members]], axis=1)
    leaving = np.linalg.norm(corners[following[members[tails]]] - corners[members[tails]], axis=1)
    chain_low = np.minimum.reduceat(corners[members], heads)
    chain_high = np.maximum.reduceat(corners[members], heads)
    for neighbour in (previous[members[heads]], following[members[tails]]):
        chain_low = np.minimum(chain_low, corners[neighbour])
        chain_high = np.maximum(chain_high, corners[neighbour])
    return _Runs(
        reach=np.maximum.reduceat(reach[members], heads),
        length=np.add.reduceat(entering, heads) + leaving,
        low=chain_low,
        high=chain_high,
    )


def _disjoint_rectangles(windows: np.ndarray) -> np.ndarray:
    """Überlappende Fenster zu ihrer gemeinsamen Hüllbox zusammengelegt, bis
    keine zwei sich mehr überlappen — sonst zählte eine Fläche doppelt.

    Ein Fenster bleibt ein Rechteck, weil der schnelle Zuschnitt
    (``clip_by_rect``) nur Rechtecke kennt; das zusammengelegte ist größer,
    aber die Fläche außerhalb der Form darin bleibt dieselbe. Es sind selten
    mehr als zwanzig, und der paarweise Vergleich in NumPy ist billiger als
    eine Vereinigung in GEOS.
    """
    windows = windows.copy()
    while len(windows) > 1:
        overlap = (
            (windows[:, None, 0] <= windows[None, :, 2])
            & (windows[None, :, 0] <= windows[:, None, 2])
            & (windows[:, None, 1] <= windows[None, :, 3])
            & (windows[None, :, 1] <= windows[:, None, 3])
        )
        np.fill_diagonal(overlap, False)
        if not overlap.any():
            break
        first, second = (int(number) for number in np.argwhere(overlap)[0])
        windows[first, :2] = np.minimum(windows[first, :2], windows[second, :2])
        windows[first, 2:] = np.maximum(windows[first, 2:], windows[second, 2:])
        windows = np.delete(windows, second, axis=0)
    return windows


def _survives_opening(shape: ShapelyPolygon, width: float) -> bool:
    """Übersteht die Form eine Öffnung dieser Breite, ohne Struktur zu
    verlieren?

    Die Schwelle muss **fest** sein und darf nicht mit der geprüften Breite
    wachsen, sonst ist die Frage nicht mehr monoton und die Suche darüber
    nicht mehr gültig: Eine Schwelle von ``width * width`` übersieht bei
    zwei Millimetern eine Rippe, die sie bei einem halben findet, und die
    Halbierung läuft an ihr vorbei.

    **Ein Nein steht fest, sobald ein einziges Teil zu viel verliert**
    (RM-109). Eine Rändelschicht besteht aus 2 898 getrennten Konturen mit
    zusammen 14 400 Punkten; sie alle zu puffern kostete je Frage 300
    Millisekunden, und die Halbierung stellt sieben davon. Gemessen am
    12.09.2026: 4,24 Sekunden für vierzehn Fragen, sechzig Prozent der ganzen
    Schichtanalyse — während die zweiunddreißig Vorprüfungen derselben Platte
    zusammen 1,8 Millisekunden brauchten. Der Aufwand lag nicht an der
    Vorprüfung, sondern an den wenigen Schichten, die überhaupt gemessen
    werden.

    Der Verlust ist eine **Summe** über die Teile, und jeder Summand ist
    nicht negativ: Wer das Budget schon nach dem ersten Teil überschreitet,
    überschreitet es auch mit allen. Die dünnsten zuerst — ein Teil, dessen
    mittlere Weite kleiner ist, verliert eher.

    **Und das Ja bleibt die ganze Form.** Die Öffnungen zweier Teile dürfen
    sich berühren, und eine geteilte Fläche zählt dann in der Summe doppelt:
    Der Teileweg unterschätzt den Verlust, taugt also für das Nein und nicht
    für das Ja. Wer das Budget nach :data:`WIDTH_SCAN_PARTS` Teilen noch
    nicht gerissen hat, bekommt die exakte Antwort über die ganze Form — mit
    einer Obergrenze für die vergebliche Arbeit statt einer Wette.
    """
    return bool(_survive_many(np.asarray([shape], dtype=object), np.asarray([width]))[0])


def _thinnest_first(shape: ShapelyPolygon) -> list[ShapelyPolygon]:
    """Die dünnsten :data:`WIDTH_SCAN_PARTS` Teile dieser Form, dünnste zuerst.

    Die mittlere Weite ordnet sie — vierfache Fläche über dem Umfang, dieselbe
    Zahl, mit der :func:`minimum_width` ihre Klammer beginnt. Ein Teil, dessen
    mittlere Weite kleiner ist, verliert bei einer Öffnung eher.

    **Gerechnet wird über alle Teile auf einmal.** Fläche und Umfang einzeln
    abzufragen kostete an einer Rändelschicht 15 Millisekunden je Frage — mehr
    als die Puffer, die danach nötig waren; Shapely rechnet beides über ein
    Feld in einem Zehntel davon. Eine Form ohne Teile beantwortet die Frage
    ohne Umweg: Dort gibt es nichts vorzusortieren, und der Weg über die ganze
    Form steht ohnehin dahinter.
    """
    parts = getattr(shape, "geoms", None)
    if parts is None or len(parts) <= 1:
        return []
    entries = np.asarray(list(parts), dtype=object)
    lengths = shapely.length(entries)
    ordered = np.argsort(
        np.where(
            lengths > EPS_GEOM, 4.0 * shapely.area(entries) / np.maximum(lengths, EPS_GEOM), 0.0
        )
    )
    return [entries[index] for index in ordered[:WIDTH_SCAN_PARTS]]


def minimum_width(shape: ShapelyPolygon, interesting_below: float = WIDTH_INTERESTING) -> float:
    """Die kleinste Strukturbreite dieser Schicht (§22.2).

    Prüfbar gegen den Düsendurchmesser, und dafür ist sie da.

    **Gemessen wird durch Öffnen, nicht durch Erodieren bis zum Verschwinden.**
    Der erste Anlauf fragte, ob ``shape.buffer(-r)`` leer ist, und das wird
    erst wahr, wenn auch die *dickste* Stelle weg ist — die Zahl war damit der
    einbeschriebene Kreis und nicht die schmalste Struktur. Gemessen an einer
    Platte 20 auf 20 auf 5 mit einer 0,3 mm dünnen Rippe: gemeldet wurden 2,0 mm,
    die bloße Berichtsgrenze; kein Befund über die Düse, kein Vorschlag zur
    Bahnbreite. Die Rippe, um die es ging, kam in keiner Zahl vor.

    Geöffnet wird stattdessen: erodieren und wieder aufweiten. Alles, was
    breiter ist als die geprüfte Weite, kommt zurück; was schmaler war, bleibt
    weg. Sobald dabei mehr verschwindet als eine Ecke
    (:func:`_survives_opening`), ist die geprüfte Weite zu groß — und die
    kleinste Breite liegt darunter. Bei einer konvexen Form ändert das nichts:
    Dort ist die Öffnung die Identität, bis die Erosion sie ganz auflöst, und
    das ist genau die alte Antwort.

    Drei Freiheiten werden fürs Tempo genommen, und keine davon ändert eine
    Antwort, auf die jemand handelt. Die Kontur wird vereinfacht
    (:func:`_width_outline`), die Erosion benutzt gefaste statt gerundeter
    Ecken — beides bleibt weit unter dem, was ein Drucker auflöst. Und eine
    Schicht, die eine Öffnung um
    ``interesting_below`` übersteht, wird als genau diese Breite gemeldet und
    nicht weiter gemessen: ob eine Wand vier oder neun Millimeter dick ist,
    fragt der Bericht nicht, und die Suche danach kostete mehr als der Rest
    der Analyse zusammen.

    ``interesting_below=0.0`` hebt diesen Deckel auf; dann wird die Klammer
    selbst gesucht.
    """
    if interesting_below > 0.0:
        return float(_minimum_widths([shape], interesting_below)[0])
    if shape.is_empty or shape.length <= EPS_GEOM:
        return 0.0
    coarse = _width_outline(_without_slits(shape))
    low = 0.0
    high = float(interesting_below) if interesting_below > 0.0 else _open_bracket(coarse)
    # Die vierfache Fläche über dem Umfang ist die mittlere Breite dieser
    # Form — bei einer Scheibe ihr Durchmesser, bei einem langen Streifen
    # knapp seine doppelte Breite. Ein Mittel liegt nie unter dem Kleinsten, taugt also
    # als Startpunkt; welche Seite der Klammer es besetzt, sagt ein Versuch.
    guess = 4.0 * float(coarse.area) / float(coarse.length)
    if EPS_GEOM < guess < high:
        if _survives_opening(coarse, guess):
            low = guess
        else:
            high = guess

    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        if _survives_opening(coarse, middle):
            low = middle
        else:
            high = middle
    return float(high)


def thinnest_spot(shape: ShapelyPolygon, width: float) -> tuple[float, float] | None:
    """Wo die schmalste Struktur einer Schicht liegt, als Punkt in XY (§22.2).

    :func:`minimum_width` sagt, **wie** schmal; der Prüfbericht braucht dazu
    das **Wo**, damit ein Klick hinfliegt. Es ist die Fläche, die eine
    Öffnung der gemeldeten Breite wegnimmt — dieselbe Öffnung wie in der
    Messung —, und davon das größte Stück. ``None``, wenn bei dieser Breite
    nichts verloren geht.
    """
    if shape.is_empty or width <= EPS_GEOM:
        return None
    coarse = _width_outline(_without_slits(shape))
    # Die Schicht kommt hier aus ihren gespeicherten Konturen zurück
    # (:func:`_layer_shape`), und an einer Stelle, wo sich zwei Teile
    # berühren, ist das nicht Punkt für Punkt der Schnitt, an dem gemessen
    # wurde: Am Baum mit Schale ergab dieselbe Schicht 0,1875 mm im Schnitt
    # und 0,21875 aus den Konturen — einen Halbierungsschritt daneben, und bei
    # 0,1875 ging aus den Konturen nichts verloren. Gesucht wird deshalb bis
    # zur nächsten Weite, bei der etwas verloren geht.
    for factor in (1.0, 1.25, 1.5, 2.0):
        radius = width * factor / 2.0
        eroded = _without_slivers(_eroded(coarse, radius))
        try:
            lost = (
                coarse
                if eroded.is_empty
                else coarse.difference(eroded.buffer(radius, quad_segs=1, join_style="mitre"))
            )
        except shapely.errors.GEOSException:
            lost = shapely.difference(
                coarse,
                eroded.buffer(radius, quad_segs=1, join_style="mitre"),
                grid_size=EPS_GEOM,
            )
        pieces = [part for part in shapely.get_parts(lost).tolist() if part.area > EPS_GEOM]
        if pieces:
            spot = max(pieces, key=lambda part: part.area).representative_point()
            return float(spot.x), float(spot.y)
    return None


def _open_bracket(shape: ShapelyPolygon) -> float:
    """Eine Weite, an der diese Form sicher Struktur verliert.

    Gebraucht nur ohne Deckel: Mit Deckel ist ``interesting_below`` die
    Klammer, denn dass die Form dort verliert, steht dann schon fest.
    """
    limit = _across(shape)
    width = 4.0 * float(shape.area) / float(shape.length)
    while width < limit and _survives_opening(shape, width):
        width *= 2.0
    return min(width, limit)


def _across(shape: ShapelyPolygon) -> float:
    """Die Diagonale der Hüllbox — weiter als das ist an dieser Form nichts."""
    left, bottom, right, top = shape.bounds
    return math.hypot(right - left, top - bottom)


def spanning_width(shape: ShapelyPolygon) -> float:
    """Der größte Kreis, der in diese Öffnung passt, als Durchmesser (§22.2).

    Die andere Frage als :func:`minimum_width`, und sie hat ihre eigene
    Antwort: Über einer Öffnung spannt der Slicer gerade Bahnen, und was ihn
    dabei fordert, ist die **weiteste** freie Stelle. Ein Ausläufer von einem
    Zehntelmillimeter macht eine Öffnung von 40 mm nicht leichter zu
    überbrücken — die kleinste Strukturbreite wäre hier also genau die
    falsche Zahl.

    Gefunden durch Erodieren, bis nichts mehr übrig ist.

    **Die Klammer wird geprüft, nicht angenommen.** ``2A/L`` ist bei einer
    Scheibe und bei einem Quadrat genau der einbeschriebene Radius, aber nur
    bei konvexen Formen eine obere Schranke: Ein Lüftergitter — Ø 40 mit vier
    schmalen Radialschlitzen — treibt den Umfang hoch, ohne viel Fläche zu
    nehmen, und die Klammer fiel unter den gesuchten Wert. Die Suche lief dann
    bis an ihren eigenen Anfang und meldete ihn; die Warnung über die Brücke
    blieb aus. Die Klammer wird deshalb verdoppelt, bis sie trägt, und die
    halbe Diagonale der Hüllbox deckelt sie.
    """
    if shape.is_empty or shape.length <= EPS_GEOM:
        return 0.0
    coarse = _simplified(_without_slits(shape))
    limit = _across(coarse) / 2.0
    high = 2.0 * float(coarse.area) / float(coarse.length)
    while high < limit and not _eroded(coarse, high).is_empty:
        high *= 2.0
    high = min(high, limit)

    low = 0.0
    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        if _eroded(coarse, middle).is_empty:
            high = middle
        else:
            low = middle
    return float(low * 2.0)


def _supported_span(shape: ShapelyPolygon, supported: ShapelyPolygon) -> float:
    """Die kürzeste geprüfte Bahnenrichtung mit Halt an beiden Enden.

    Der Inkreis genügt nur bei umlaufender Auflage. Ein Steg von 30 auf 3 mm
    über zwei Pfeilern muss die 30 mm überbrücken: Quer zur schmalen Seite
    liegen beide Bahnenden in der Luft. Kandidaten folgen den Konturkanten
    und ihren Normalen. Zwischen projizierten Ecken bleibt die Topologie der
    Schnittbahnen gleich; geprüft werden Mitte und beide Ränder jedes Bands.

    Es bleibt eine geometrische Schätzung, keine Slicer-Bahnplanung. Ohne
    eine beidseitig getragene Richtung gilt die Diagonale als konservatives
    Maß des freien Bereichs, niemals seine möglicherweise winzige Breite.

    **Gleiche Richtungen werden in einem Zug zusammengelegt**, nicht jede
    gegen jede vorige. Eine organische Fläche aus einem feinen Netz hat
    tausende Kanten: An einer Drachenfigur mit 2,3 Mio. Dreiecken hatte der
    freie Bereich einer Schicht 3 188 Ecken, der paarweise Vergleich kostete
    für diese eine Schicht 24 s und für den Körper 120 s — die Druckvorschläge
    warteten siebeneinhalb Minuten (Befund Robert, 19.09.2026). Sortiert nach
    Winkel ist dieselbe Menge in einem Durchlauf da; je Bündel bleibt wie
    zuvor die Kante, die in der Kontur zuerst kommt.
    """
    anchored = supported.buffer(EPS_GEOM)
    if anchored.covers(shape.boundary):
        return spanning_width(shape)
    # Tausende Bahnenden fragen dieselbe Fläche: vorbereitet antwortet sie
    # über ihren Index statt über die ganze Kontur.
    shapely.prepare(anchored)

    corners = np.asarray(shape.exterior.coords, dtype=float)
    edges = np.diff(corners, axis=0)
    lengths = np.linalg.norm(edges, axis=1)
    units = edges[lengths > EPS_GEOM] / lengths[lengths > EPS_GEOM, None]
    if not len(units):
        return _across(shape)
    # Kante und Normale, in Konturreihenfolge: erst die Kante, dann ihre Normale.
    candidates = np.empty((2 * len(units), 2), dtype=float)
    candidates[0::2] = units
    candidates[1::2] = np.stack((-units[:, 1], units[:, 0]), axis=1)
    # Richtung und Gegenrichtung sind dieselbe Bahn: der Winkel modulo pi.
    # Als eine Richtung gilt, was der frühere Vergleich |cos| >= 1 - EPS
    # zusammenlegte — gut ein Tausendstel Bogenmaß; der Kreis schließt sich
    # bei pi, die letzte und die erste können dasselbe Bündel sein.
    angles = np.mod(np.arctan2(candidates[:, 1], candidates[:, 0]), math.pi)
    order = np.argsort(angles, kind="stable")
    apart = math.acos(1.0 - EPS_GEOM)
    bundles: list[list[int]] = [[int(order[0])]]
    for index in order[1:]:
        if angles[index] - angles[bundles[-1][-1]] > apart:
            bundles.append([int(index)])
        else:
            bundles[-1].append(int(index))
    if len(bundles) > 1 and angles[bundles[0][0]] + math.pi - angles[bundles[-1][-1]] <= apart:
        bundles[0].extend(bundles.pop())
    directions: list[Any] = [candidates[min(bundle)] for bundle in sorted(bundles, key=min)]

    # **Die Bänder kommen aus der vereinfachten Kontur**, die Schnitte gehen
    # durch die echte. Zwischen zwei projizierten Ecken bleibt die Topologie
    # der Bahnen gleich, und zwei Ecken, die ein hundertstel Millimeter
    # auseinanderliegen (Vernetzungsrauschen einer Rundung), teilen kein Band,
    # das ein Drucker noch auflöste. An der Drachenfigur waren es 778 Bänder
    # je Richtung, also 2 334 Schnittbahnen — 22 s für eine Schicht.
    band_corners = np.asarray(_simplified(shape).exterior.coords, dtype=float)
    # Alle Kanten der Fläche, Außenring und Löcher, für die Abtastzeilen.
    rings = [np.asarray(shape.exterior.coords, dtype=float)] + [
        np.asarray(ring.coords, dtype=float) for ring in shape.interiors
    ]
    heads = np.concatenate([ring[:-1] for ring in rings])
    tails = np.concatenate([ring[1:] for ring in rings])
    best = _across(shape)
    for direction in directions:
        normal = np.array([-direction[1], direction[0]])
        levels = np.unique(band_corners @ normal)
        lower, upper = levels[:-1], levels[1:]
        keep = upper - lower > EPS_GEOM
        lower, upper = lower[keep], upper[keep]
        if not len(lower):
            continue
        inset = np.minimum(EPS_GEOM, (upper - lower) / 4.0)
        positions = np.concatenate((lower + inset, (lower + upper) / 2.0, upper - inset))
        # Die zentrale Bandmitte gehört ohnehin zum vollständigen Satz.
        # Trägt bereits diese Bahn nicht, kann die Richtung nichts gewinnen.
        # An einer offenen Halbscheibe entfallen so hunderttausende Schnitte,
        # ohne eine Richtung zusätzlich anzunehmen oder auszuschließen.
        middle = len(lower) + len(lower) // 2
        for samples in (positions[middle : middle + 1], positions):
            cuts = _cuts_along(heads, tails, direction, normal, samples)
            if cuts is None:
                break
            starts, ends, lengths = cuts
            if not np.all(shapely.covers(anchored, shapely.points(starts))) or not np.all(
                shapely.covers(anchored, shapely.points(ends))
            ):
                break
        else:
            best = min(best, float(lengths.max()))
    return best


def _cuts_along(
    heads: np.ndarray,
    tails: np.ndarray,
    direction: np.ndarray,
    normal: np.ndarray,
    positions: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Die Stücke der Geraden ``direction`` durch die Fläche, je Abtastlage.

    Was ``shapely.intersection(shape, line)`` liefert, nur ohne Overlay: Eine
    Gerade quer zur Normalen schneidet die Kanten der Fläche, und zwischen
    je zwei Schnittpunkten in Laufrichtung liegt abwechselnd Material und
    Luft — die Paritätsregel, für Außenring und Löcher zusammen. Die Lagen
    kommen aus den Bandmitten und -rändern, liegen also nie genau auf einer
    Ecke oder entlang einer Kante; die Reihenfolge der Schnittpunkte ist
    damit eindeutig.

    Warum nicht GEOS: Das Overlay knotet je Aufruf die ganze Kontur neu, und
    an einer Drachenschicht mit 4 700 Ecken kostete jede der 3 600 Bahnen
    2,5 ms — 9,7 s für eine Schicht. Hier sind es Feldoperationen über die
    Kanten, für alle Lagen einer Richtung auf einmal.

    Zurück kommen Anfangs- und Endpunkte aller Stücke länger als ``EPS_GEOM``
    und ihre Längen — oder ``None``, wenn es keine gibt.
    """
    across_head = heads @ normal
    across_tail = tails @ normal
    along_head = heads @ direction
    along_tail = tails @ direction
    if _chain is not None and hasattr(_chain, "cuts_along"):
        result = _chain.cuts_along(
            across_head,
            across_tail,
            along_head,
            along_tail,
            np.ascontiguousarray(positions),
            np.ascontiguousarray(normal),
            np.ascontiguousarray(direction),
            EPS_GEOM,
        )
        return cast(tuple[np.ndarray, np.ndarray, np.ndarray] | None, result)
    # Kanten, die eine Lage kreuzen (echt, nicht berührend): je Lage eine Spalte.
    crossing = (across_head[:, None] - positions[None, :]) * (
        across_tail[:, None] - positions[None, :]
    ) < 0.0
    if not crossing.any():
        return None
    span = across_tail - across_head
    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []
    lengths: list[np.ndarray] = []
    for column, position in enumerate(positions):
        hit = np.nonzero(crossing[:, column])[0]
        if len(hit) < 2:
            continue
        share = (position - across_head[hit]) / span[hit]
        along = np.sort(along_head[hit] + share * (along_tail[hit] - along_head[hit]))
        if len(along) % 2:
            # Ein ungerades Kreuzen gibt es an einer gültigen Fläche nur durch
            # Rundung genau an einer Ecke; das letzte Stück hätte kein Ende.
            along = along[:-1]
        first, second = along[0::2], along[1::2]
        long_enough = second - first > EPS_GEOM
        if not long_enough.any():
            continue
        first, second = first[long_enough], second[long_enough]
        starts.append(position * normal + first[:, None] * direction)
        ends.append(position * normal + second[:, None] * direction)
        lengths.append(second - first)
    if not lengths:
        return None
    return np.concatenate(starts), np.concatenate(ends), np.concatenate(lengths)


def _bridge_width(
    shape: ShapelyPolygon,
    previous: ShapelyPolygon | None,
    bridge_from: float = BRIDGE_FROM,
    touching: ShapelyPolygon | None = None,
) -> float:
    """Die längste freie Spannweite dieser Schicht — was überbrückt werden
    muss (§22.2). Mit ``touching`` nur die freien Flächen, die es berühren
    (:func:`open_bridge_width`).

    Zwei Fragen, in dieser Reihenfolge. Erst: ist die ungestützte Fläche
    überhaupt breiter als zwei Bahnen? Ein Kegel unter 45 Grad legt je Schicht
    einen halben Millimeter frei, und der trägt sich selbst — das ist ein
    Überhang und keine Brücke. Dann: wie weit hängen die Bahnen frei?

    Wie breit „zwei Bahnen" sind, sagt ``bridge_from`` — am Drucker gemessen
    und nicht im Code gesetzt (Regel 7, siehe :data:`BRIDGE_FROM`).

    Das ist nicht die Ausdehnung der ungestützten Fläche. Eine Ringschulter um
    eine Öffnung ist selbst nur drei Millimeter breit; frei hängt eine Bahn
    über der **Öffnung**, die sie umschließt. Genau diese Zahl war beim
    Gewürzbehälter der Schaden: eine 3-mm-Schulter, deren Bahnen 24 mm frei
    quer über den Becher liefen.

    **Ein umschlossener Ring ist aber nicht schon deshalb eine Öffnung.**
    Gezählt wurde jedes Loch der ungestützten Fläche, auch eines, unter dem
    massives Material steht. Ein Pilz mit tragendem Stiel — Hut 100 auf 100 auf
    einem Stiel 30 auf 30 — meldete damit eine Brücke von 29,7 mm über genau
    dem Stiel, der sie trägt. Gemessen wird deshalb der Teil des Rings, unter
    dem wirklich nichts steht: beim Pilz bleibt davon nichts, beim
    Gewürzbehälter der ganze Becher.

    **Und es ist auch nicht die längere Seite des Hüllrechtecks.** Gemessen
    wurde die größere Ausdehnung der Öffnung, und damit stand über einem
    Kabelkanal von 30 auf 8 mm eine Brücke von 30 mm im Bericht. Der Slicer
    legt seine Bahnen quer über die **schmale** Seite, wenn beide Enden dort
    Halt haben. Bei einem Steg nur auf zwei Pfeilern ist gerade die lange
    Seite die einzige getragene Richtung (:func:`_supported_span`).
    """
    if previous is None or previous.is_empty:
        return 0.0
    supported = previous.buffer(OVERHANG_MARGIN)
    free = shape.difference(supported)
    if touching is not None:
        free = unary_union([part for part in _areas_of(free) if part.intersects(touching)])
    # Brücken werden gegen die Schicht selbst gemessen, nicht gegen die
    # 45-Grad-Zugabe: was durch freie Luft spannt, ist eine Brücke, egal in
    # welchem Winkel.
    if free.is_empty:
        return 0.0
    # Eine einzelne Erosion statt einer Suche: gefragt ist nicht, wie breit die
    # Fläche ist, sondern ob sie über der Grenze liegt.
    if _eroded(free, bridge_from / 2.0).is_empty:
        return 0.0

    widest = 0.0
    for part in getattr(free, "geoms", [free]):
        if part.is_empty or not hasattr(part, "exterior"):
            continue
        # Umschließt der ungestützte Bereich eine Öffnung, ist deren freie
        # Weite die Spannweite; ist er selbst eine Fläche (eine Decke über
        # einem Hohlraum), zählt seine eigene.
        holes = [ShapelyPolygon(ring) for ring in part.interiors]
        if holes:
            spans = [hole.difference(supported) for hole in holes]
        else:
            # **Gemessen wird nur, was breiter als zwei Bahnen ist**, nicht
            # das ganze Stück. Die Frage oben gilt der Schicht, und ein Stück
            # besteht sie schon mit einer einzigen breiteren Stelle: An der
            # Waschschüssel (25.09.2026) war es ein 45-Grad-Streifen entlang
            # der Außenwand, 190 mm lang, fast überall schmaler als zwei Bahnen,
            # mit 0,65 mm² Kern. Ohne beidseitig getragene Richtung nahm
            # :func:`_supported_span` seine Diagonale, und der Bericht meldete
            # eine Decke von 258 mm. Der Streifen trägt sich selbst; übrig
            # bleibt die Stelle, die wirklich frei hängt.
            half = bridge_from / 2.0
            core = _eroded(part, half)
            if core.is_empty:
                continue
            spans = _areas_of(core.buffer(half, quad_segs=1, join_style="mitre").intersection(part))
        for span in spans:
            if not span.is_empty:
                widest = max(
                    widest,
                    spanning_width(span) if holes else _supported_span(span, supported),
                )
    return float(widest)


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


# --- Gestapelte Messung (RM-201) ---------------------------------------------------
#
# Eine Schicht nach der anderen zu messen hieß: je Schicht zwanzig bis vierzig
# kleine GEOS-Aufrufe, jeder mit seinem Weg durch den Interpreter. Auf einem
# Kern ist das billig; auf sechs Arbeitern warten die Aufrufe aufeinander, weil
# jeder für seine Mikrosekunden den Interpreter-Lock braucht. Gemessen am
# 23.09.2026 am Baum mit Schale (197 120 Dreiecke): die Breitensuche auf einem
# Kern 2,9 s, auf sechs Arbeitern 2,6 s — Faktor 1,1. Gestapelt fragt jeder
# Aufruf ein ganzes Feld von Schichten, GEOS rechnet ohne Lock durch, und die
# Arbeiter bekommen Blöcke statt Schichten. Jede Zahl entsteht aus derselben
# GEOS-Rechnung wie vorher einzeln; nur der Weg dorthin ist kürzer.


def _opening_losses(shapes: np.ndarray, widths: np.ndarray, *, exact: bool = True) -> np.ndarray:
    """:func:`_opening_loss` für ein Feld von Formen und Weiten in einem Zug."""
    radius = np.asarray(widths, dtype=float) / 2.0
    full = shapely.area(shapes)
    eroded = _without_slivers_many(shapely.buffer(shapes, -radius, quad_segs=1, join_style="mitre"))
    gone = shapely.is_empty(eroded)
    opened = shapely.buffer(eroded, radius, quad_segs=1, join_style="mitre")
    balance = np.where(gone, full, full - shapely.area(opened))
    if exact:
        open_question = np.flatnonzero(~gone & (balance <= WIDTH_LOST_FROM))
        if len(open_question):
            same = shapely.equals_exact(
                shapely.normalize(opened[open_question]),
                shapely.normalize(shapes[open_question]),
                tolerance=EPS_GEOM,
            )
            for number in open_question[~same].tolist():
                balance[number] += _protrusion(
                    opened[number], shapes[number], WIDTH_LOST_FROM - balance[number]
                )
    return cast(np.ndarray, np.maximum(balance, 0.0))


def _without_slivers_many(eroded: np.ndarray) -> np.ndarray:
    """:func:`_without_slivers` über ein Feld, die Stücke aller Formen in einem Zug."""
    parts, owner = shapely.get_parts(eroded, return_index=True)
    if not len(parts):
        return eroded
    wide = 4.0 * shapely.area(parts) >= WIDTH_SIMPLIFY * shapely.length(parts)
    if wide.all():
        return eroded
    result = eroded.copy()
    for number in np.unique(owner[~wide]).tolist():
        kept = parts[(owner == number) & wide].tolist()
        result[number] = (
            ShapelyPolygon() if not kept else kept[0] if len(kept) == 1 else MultiPolygon(kept)
        )
    return result


def _survive_many(shapes: np.ndarray, widths: np.ndarray, *, exact: bool = True) -> np.ndarray:
    """:func:`_survives_opening` für ein Feld von Formen und Weiten.

    ``exact=False`` fragt die ganze Form nur nach ihrer Bilanz: Ein Nein ist
    dann sicher, ein Ja nicht (:func:`_opening_loss`).

    Der Teileweg (RM-109) wird für alle Formen mit mehreren Teilen zugleich
    gefragt: die dünnsten :data:`WIDTH_SCAN_PARTS` Teile jeder Form, ihre
    Bilanz in einem Aufruf, je Form summiert. Die Entscheidung ist dieselbe
    wie beim Abbruch nach dem ersten Teil, das das Budget reißt — jede Bilanz
    ist nicht negativ, die Teilsummen steigen also nur. Was danach offen ist,
    fragt die ganze Form.
    """
    widths = np.asarray(widths, dtype=float)
    survives = np.ones(len(shapes), dtype=bool)
    parts, owner = shapely.get_parts(shapes, return_index=True)
    counts = np.bincount(owner, minlength=len(shapes)) if len(parts) else np.zeros(len(shapes))
    several = counts > 1
    if several.any():
        chosen = np.isin(owner, np.flatnonzero(several))
        parts, owner = parts[chosen], owner[chosen]
        lengths = shapely.length(parts)
        mean = np.where(
            lengths > EPS_GEOM, 4.0 * shapely.area(parts) / np.maximum(lengths, EPS_GEOM), 0.0
        )
        # Je Form die dünnsten zuerst, dieselbe Ordnung wie :func:`_thinnest_first`.
        order = np.lexsort((mean, owner))
        rank = np.empty(len(order), dtype=np.int64)
        starts = np.r_[0, np.flatnonzero(np.diff(owner[order])) + 1]
        rank[order] = np.arange(len(order)) - np.repeat(starts, np.diff(np.r_[starts, len(order)]))
        scanned = rank < WIDTH_SCAN_PARTS
        losses = _opening_losses(parts[scanned], widths[owner[scanned]], exact=False)
        lost = np.bincount(owner[scanned], weights=losses, minlength=len(shapes))
        survives[lost > WIDTH_LOST_FROM] = False
    open_question = np.flatnonzero(survives)
    if len(open_question):
        survives[open_question] = (
            _opening_losses(shapes[open_question], widths[open_question], exact=exact)
            <= WIDTH_LOST_FROM
        )
    return survives


def _minimum_widths(shapes: list[ShapelyPolygon], interesting_below: float) -> np.ndarray:
    """:func:`minimum_width` für viele Schichten, die Halbierung im Gleichschritt.

    Jede Schicht bekommt dieselben Fragen in derselben Reihenfolge wie einzeln
    — erst der Deckel, dann das Mittel, dann die Halbierungen —, nur stellt
    jede Runde sie allen offenen Schichten in einem Aufruf.

    **Genau gefragt wird zweimal je Schicht, nicht bei jedem Schritt.** Ein
    Nein ist schon aus der Bilanz sicher; nur ein Ja kann eine Nadel verdecken
    (:func:`_opening_loss`), und die genaue Antwort kostet dann eine
    Überlagerung. Die Halbierung läuft deshalb über die Bilanz, und am Ende
    wird die größte bestandene Weite genau nachgefragt. Hält sie, ist die
    Klammer gültig — jedes Nein darüber war ohnehin sicher. Hält sie nicht,
    hat irgendwo eine Nadel ein Ja erschlichen, und diese Schicht wird ganz
    genau neu gesucht. Am Baum mit Schale (849 Schichten, Nadeln an jeder
    Astspitze) fielen so die genauen Nachfragen von 825 auf eine je Schicht.
    """
    widths = np.zeros(len(shapes))
    usable = np.asarray(
        [
            number
            for number, shape in enumerate(shapes)
            if not shape.is_empty and shape.length > EPS_GEOM
        ],
        dtype=np.int64,
    )
    if not len(usable):
        return widths
    coarse = np.asarray(
        [_width_outline(_without_slits(shapes[number])) for number in usable.tolist()],
        dtype=object,
    )
    thick = _survive_many(coarse, np.full(len(usable), float(interesting_below)))
    widths[usable[thick]] = float(interesting_below)
    active = np.flatnonzero(~thick)
    if not len(active):
        return widths
    low, high = _halved(coarse[active], interesting_below, exact=False)
    checked = np.flatnonzero(low > 0.0)
    if len(checked):
        misled = checked[~_survive_many(coarse[active[checked]], low[checked])]
        if len(misled):
            low[misled], high[misled] = _halved(
                coarse[active[misled]], interesting_below, exact=True
            )
    widths[usable[active]] = high
    return widths


def _halved(
    coarse: np.ndarray, interesting_below: float, *, exact: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Die Klammer der Breitensuche für Formen, die den Deckel nicht halten.

    Das Mittel (vierfache Fläche über Umfang) als erster Versuch, dann
    :data:`WIDTH_STEPS` Halbierungen — die Schritte aus :func:`minimum_width`.
    """
    low = np.zeros(len(coarse))
    high = np.full(len(coarse), float(interesting_below))
    guess = 4.0 * shapely.area(coarse) / shapely.length(coarse)
    tried = np.flatnonzero((guess > EPS_GEOM) & (guess < high))
    if len(tried):
        passed = _survive_many(coarse[tried], guess[tried], exact=exact)
        low[tried[passed]] = guess[tried[passed]]
        high[tried[~passed]] = guess[tried[~passed]]
    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        passed = _survive_many(coarse, middle, exact=exact)
        low[passed] = middle[passed]
        high[~passed] = middle[~passed]
    return low, high


def _islands_many(shapes: np.ndarray, previous: np.ndarray) -> list[ShapelyPolygon]:
    """:func:`_islands` für ein Feld von Schichtpaaren; ``previous`` ist nie leer."""
    parts, owner = shapely.get_parts(shapes, return_index=True)
    result: list[ShapelyPolygon] = [ShapelyPolygon()] * len(shapes)
    if not len(parts):
        return result
    # Eine Vorgängerschicht trägt oft tausende Konturen. Den räumlichen
    # Index einmal aufbauen, statt ihn für jedes contains_properly neu zu
    # erzeugen; die Geometrie und die exakten Prädikate bleiben dieselben.
    shapely.prepare(previous)
    below = previous[owner]
    touching = shapely.intersects(parts, below)
    anchors = shapely.point_on_surface(parts)
    placed = ~shapely.is_empty(anchors)
    shared = np.zeros(len(parts), dtype=bool)
    if placed.any():
        spots = shapely.get_coordinates(anchors[placed])
        squares = shapely.box(
            spots[:, 0] - EPS_GEOM,
            spots[:, 1] - EPS_GEOM,
            spots[:, 0] + EPS_GEOM,
            spots[:, 1] + EPS_GEOM,
        )
        shared[placed] = shapely.contains_properly(
            below[placed], squares
        ) & shapely.contains_properly(parts[placed], squares)
    floating = ~touching
    unclear = np.flatnonzero(touching & ~shared)
    if len(unclear):
        floating[unclear] = (
            shapely.area(shapely.intersection(parts[unclear], below[unclear]))
            <= EPS_GEOM * EPS_GEOM
        )
    # **Und was seitlich an Getragenem anliegt, ist keine Insel** (KUNDE-01).
    # Der Slicer schließt jede Schicht und macht aus zwei Konturen mit einem
    # Spalt unter :data:`SLICER_CLOSING_GAP` eine: Die Schrift, die als eigene
    # Schale an einer Wand steht, beginnt dann nicht in der Luft, sondern hängt
    # als kleiner Überhang an der Wand. Weitergereicht wird über Ketten —
    # ein Buchstabe am Buchstaben an der Wand.
    for number in np.unique(owner[floating]).tolist():
        mine = owner == number
        held = mine & ~floating
        if not held.any():
            continue
        loose = np.flatnonzero(mine & floating)
        anchor = shapely.union_all(parts[held])
        while len(loose):
            near = shapely.dwithin(parts[loose], anchor, SLICER_CLOSING_GAP)
            if not near.any():
                break
            floating[loose[near]] = False
            anchor = shapely.union_all(np.asarray([anchor, *parts[loose[near]]], dtype=object))
            loose = loose[~near]
    for number in np.unique(owner[floating]).tolist():
        pieces = parts[(owner == number) & floating].tolist()
        result[number] = unary_union(pieces)
    return result


def _measure_batch(
    shapes: list[ShapelyPolygon],
    previous: list[ShapelyPolygon | None],
    on_plate: list[bool],
    steps: list[float],
    detail: Detail,
    overhang_factor: float,
    bridge_from: float,
    taper: list[bool],
) -> list[LayerMetrics]:
    """Die Kennzahlen vieler Schichten gegen ihre jeweils darunter, gestapelt.

    Je Schicht dieselben Zahlen wie eine Schicht allein; ``taper`` sagt je
    Schicht, ob der Keil (:func:`taper_length`) dort gesucht wird —
    :func:`_measure_all` fragt nur jede :data:`TAPER_SAMPLE`. und schreibt den
    Wert dazwischen fort.
    """
    count = len(shapes)
    body = np.asarray(shapes, dtype=object)
    areas = shapely.area(body)
    reach = np.maximum(np.asarray(steps, dtype=float) * overhang_factor, OVERHANG_MARGIN)
    regions: list[ShapelyPolygon | None] = [None] * count
    island_regions: list[ShapelyPolygon | None] = [None] * count
    overhang = np.zeros(count)
    islands = np.zeros(count)
    carried = [
        number
        for number in range(count)
        if not on_plate[number] and previous[number] is not None and not previous[number].is_empty  # type: ignore[union-attr]
    ]
    for number in range(count):
        if on_plate[number] or number in carried:
            continue
        # Nichts darunter: die ganze Schicht hängt in der Luft.
        regions[number] = shapes[number]
        island_regions[number] = shapes[number]
        overhang[number] = islands[number] = areas[number]
    if carried:
        index = np.asarray(carried)
        below = np.asarray([previous[number] for number in carried], dtype=object)
        free = shapely.difference(body[index], shapely.buffer(below, reach[index], quad_segs=16))
        overhang[index] = shapely.area(free)
        floating = _islands_many(body[index], below)
        islands[index] = shapely.area(np.asarray(floating, dtype=object))
        for position, number in enumerate(carried):
            regions[number] = free[position]
            island_regions[number] = floating[position]

    if detail == "support":
        return [
            LayerMetrics(
                z=0.0,
                area=float(areas[number]),
                overhang_area=float(overhang[number]),
                island_area=float(islands[number]),
                min_width=0.0,
                bridge_width=0.0,
                contour_count=0,
                overhang=regions[number],
                islands=island_regions[number],
            )
            for number in range(count)
        ]

    widths = _minimum_widths(shapes, WIDTH_INTERESTING)
    contours = shapely.get_num_geometries(body)
    metrics = []
    for number in range(count):
        below_shape = previous[number]
        region = regions[number]
        # Ist selbst jenseits der größeren Überhangzugabe nichts frei, kann in
        # dem schmalen Band bis zur kleineren Brückenzugabe keine druckrelevante
        # Spannweite liegen. Bei 0,2-mm-Schichten sind das höchstens 0,15 mm je
        # Seite, deutlich unter einer Brückenbreite. Damit entfallen an einer
        # glatten Kugel rund 340 zweite Buffer-/Differenzrechnungen. Bei groben
        # Schichten, deren Band selbst breit genug wäre, bleibt die vollständige
        # Messung.
        bridge_width = (
            0.0
            if below_shape is None
            or below_shape.is_empty
            or (
                region is not None
                and region.is_empty
                and reach[number] - OVERHANG_MARGIN < bridge_from / 2.0
            )
            else _bridge_width(shapes[number], below_shape, bridge_from)
        )
        metrics.append(
            LayerMetrics(
                z=0.0,
                area=float(areas[number]),
                overhang_area=float(overhang[number]),
                island_area=float(islands[number]),
                min_width=float(widths[number]),
                bridge_width=bridge_width,
                contour_count=int(contours[number]),
                overhang=region,
                islands=island_regions[number],
                taper_length=taper_length(shapes[number]) if taper[number] else 0.0,
            )
        )
    return metrics


# --- Urteile über den ganzen Körper ---------------------------------------------


def _field(shapes: Sequence[ShapelyPolygon]) -> float:
    """Die Fläche einer Decke als Feld (RM-570): ihre Stücke in der Aufsicht
    vereinigt, wo sie im Mittel breiter sind als :data:`OVERHANG_MARGIN`, das
    Vernetzungsrauschen — schmaler fängt die Wand sie in sich auf —, sonst das
    größte Stück. Vereinigt, nicht summiert: Stücke an derselben Stelle zählen
    einmal."""
    largest = max((float(shape.area) for shape in shapes), default=0.0)
    if len(shapes) < 2:
        return largest
    area = math.fsum(shape.area for shape in shapes)
    if area < OVERHANG_MARGIN * math.fsum(shape.length / 2.0 for shape in shapes):
        return largest
    return max(largest, float(unary_union(list(shapes)).area))


def largest_sloped_patch(
    result: SliceResult, *, without: frozenset[tuple[int, int]] = frozenset()
) -> float:
    """Die größte Decke als Feld (:func:`_field`, :class:`_Ceilings`), RM-570.

    Eine schräge Unterseite zerfällt im Schnitt in Streifen, je Schicht einen.
    Ein Kinn mit 18° flacher Unterseite (Review vom 08.10.2026, Bau wie
    ``jaw_in_a_pocket``) bringt 31 Streifen von höchstens 6,4 mm², zusammen
    189 mm²; das größte Stück blieb unter der Grenze für ein Feld, und der Rat
    sagte „keine Stützen“. In der Aufsicht ist es eine Fläche von 189 mm².
    """
    layers = result.layers
    materials: dict[int, ShapelyPolygon] = {}

    def material(index: int) -> ShapelyPolygon:
        if index not in materials:
            materials[index] = _material(layers[index])
        return materials[index]

    ceilings = _Ceilings(layers, material)
    seen: set[tuple[int, int]] = set()
    largest = 0.0
    for index, layer in enumerate(layers):
        for number in range(len(layer.overhangs)):
            name = (index, number)
            if name in seen or name in without or ceilings.floats(name):
                continue
            group = ceilings.of(name)
            seen |= group
            largest = max(
                largest, _field([ceilings.shape(member) for member in sorted(group - without)])
            )
    return largest


def total_overhang(
    result: SliceResult, *, without: frozenset[tuple[int, int]] = frozenset()
) -> float:
    """Die Überhangfläche aller Schichten, in mm².

    ``without`` nennt Stücke (Schicht, Stück), die nicht zählen — die
    Kanaldecken aus :func:`model_support`.
    """
    total = float(sum(layer.overhang_area for layer in result.layers))
    for index, number in without:
        total -= piece_area(result.layers[index].overhangs[number])
    return max(total, 0.0)


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


def largest_overhang_patch(
    result: SliceResult, *, without: frozenset[tuple[int, int]] = frozenset()
) -> float:
    """Die größte **zusammenhängende** Überhangfläche irgendwo im Körper (§22.2).

    Die Schichtsumme (:func:`worst_overhang`) kennt den Unterschied nicht,
    der über Stützen entscheidet: Ein Gitterbecher mit hexagonalen Stegen
    (20.09.2026) sammelt auf seiner schlimmsten Schicht 278 mm² Überhang — in
    56 Stücken zu je 5 mm², jedes die Unterseite eines Stegs, der sich über
    4,7 mm selbst trägt. Eine Decke von 138 mm² ist **ein** Stück, und die
    hängt durch. Dieselbe Summe, zwei Antworten; gefragt wird deshalb das
    Stück.

    Eine Schicht, die ihre Überhangfläche kennt, aber keine Stücke trägt —
    ein Ergebnis aus Kennzahlen, wie die Vorschlagstests es bauen —, gilt als
    ein Stück: Wer die Stücke nicht mitgibt, bekommt die Schichtsumme.

    Gerechnet wird mit :func:`app.core.units.ring_area`, ohne GEOS und ohne
    NumPy: Es sind tausende kleine Stücke, und keines ist eine
    Geometriefrage. Am Gitterbecher (476 Schichten mal 56 Stücke) kostete
    der NumPy-Weg 287 ms je Vorschlagsrechnung, dieser 19.

    ``without`` nennt Stücke (Schicht, Stück), die nicht zählen — die
    Kanaldecken aus :func:`model_support`.
    """
    largest = 0.0
    for index, layer in enumerate(result.layers):
        if layer.overhang_area <= EPS_GEOM:
            continue
        if not layer.overhangs:
            largest = max(largest, float(layer.overhang_area))
            continue
        for number, piece in enumerate(layer.overhangs):
            if (index, number) in without:
                continue
            largest = max(largest, piece_area(piece))
    return largest


def island_layers(result: SliceResult) -> tuple[float, ...]:
    """Höhen, auf denen eine Kontur in der Luft beginnt (§22.2)."""
    return tuple(layer.z for layer in result.layers if layer.islands)


#: Bis zu welcher lichten Weite ein Raum, in dem eine Stützsäule auf dem
#: Modell stünde, als **Kanal** gilt, in Millimetern (§22.2).
#:
#: Die Grenze ist eine Brücke, keine Toleranz: Eine Kanaldecke bis zu dieser
#: Weite schließt sich als Gewölbe oder Brücke über den beiden Wänden, mit
#: Durchhang, aber haltend — das Doppelte dessen, ab dem der Bericht eine
#: Decke meldet (``advise.SPAN_INTERESTING``). Eine Stütze darin bekäme man
#: nicht mehr heraus, und sie versperrt den Kanal. Gemessen an der
#: Waschschüssel (25.09.2026): Der Wasserkanal vom Becher zur Düse ist 22 mm
#: weit, und alle 412 mm² Überhang über Modellmaterial liegen darin. Zum
#: Vergleich an denselben Probekörpern: Tunnel 20 mm und Rohrbogen 20 mm sind
#: Kanäle; ein offener Kasten mit Innenregal (74 mm), ein verschlossener
#: Hohlkörper (54 mm) und ein breiter Tunnel (65 mm) sind es nicht — dort
#: trägt die Decke nicht und die Stütze ist erreichbar.
CHANNEL_WIDTH: Final = 30.0

#: Überhangfläche in mm², ab der Stützen mehr nützen als kosten. Darunter
#: trägt die Schicht darunter genug, dass ein Absacken in der Wand verschwindet.
OVERHANG_WORTH_SUPPORT: Final = 150.0

#: Und wie viel davon auf **einer** Schicht anfangen muss.
#:
#: Die Summe allein sprach ein Fehlurteil: ein Becher verteilt seine
#: zweihundertvierzig Quadratmillimeter über dreihundertachtunddreißig
#: Schichten, keine davon trägt mehr als knapp vier, und jede Wand fängt das in
#: sich auf — er bekam trotzdem dieselbe Stützenwarnung wie ein Deckel, dessen
#: Lochplatte mit achthundertfünfundvierzig auf einmal über einem Hohlraum
#: beginnt.
#:
#: Hundert ist die Fläche, die eine Düse nicht mehr überspannt: ein Kreis von
#: gut elf Millimetern, also das Doppelte dessen, was die Slicer als längste
#: freie Brücke zulassen.
OVERHANG_LAYER_WORTH_SUPPORT: Final = 100.0

#: Und wie viel je Schicht mindestens anfallen muss, damit die **Summe**
#: überhaupt zählt.
#:
#: Ohne diese Untergrenze wäre der Becher wieder drin: dreihundertachtunddreißig
#: Schichten mit weniger als vier Quadratmillimetern, die jede Wand in sich
#: auffängt. Zehn Quadratmillimeter sind ein Quadrat von gut drei Millimetern —
#: darunter ist ein Überhang eine Kante und kein Feld.
OVERHANG_LAYER_MINIMUM: Final = 10.0


def worth_support(patch: float, total: float) -> bool:
    """Lohnt dieser Überhang Stützen — mit ``patch`` mm² auf einer Schicht und
    ``total`` mm² insgesamt?

    Die zwei Wege des Stützbedarfs: viel auf einmal, oder viel insgesamt mit
    einem Feld darunter. Eine Stelle für den Körper (``advise``), den Rat zu
    „überall" und die Kanalsperre (:func:`_model_support`) — drei Abschriften
    hätten sich getrennt nachziehen lassen (Review vom 08.10.2026).
    """
    return patch > OVERHANG_LAYER_WORTH_SUPPORT or (
        total > OVERHANG_WORTH_SUPPORT and patch > OVERHANG_LAYER_MINIMUM
    )


#: Die Bogenauflösung der Kanalfrage und des Kanalraums, in Segmenten je
#: Viertelkreis — die von ``BaseGeometry.buffer``; ``shapely.buffer`` nimmt
#: ohne Angabe acht, und derselbe Umkreis kam damit um 6 mm² anders heraus.
#: Bei 15 mm Radius liegt das Vieleck um höchstens 0,02 mm innerhalb seines
#: Kreises; :func:`_in_channels` rechnet die umschriebene Scheibe daraus.
CHANNEL_QUAD_SEGMENTS: Final = 16

#: Welcher Anteil eines Deckengrundrisses in der Hülle seiner gehaltenen
#: Randstücke liegen muss, damit er zwischen ihnen liegt
#: (:meth:`_Ceilings.closes`). Brücke, U und Gewölbe liegen ganz darin, ein
#: Eckregal an zwei angrenzenden Wänden zur Hälfte (die ferne Ecke überspannt
#: keine Bahn), eine Platte mit einem Stift an der Wurzel ebenso. Drei Viertel
#: trennen beide mit Abstand.
CEILING_SPANNED: Final = 0.75

#: Die Höhe einer Scheibe des Kanalraums (:func:`channel_space`), in
#: Millimetern. Frei ist, was auf jeder Schicht der Scheibe frei ist, und jede
#: Scheibe reicht eine Scheibenhöhe in die Decke.
CHANNEL_SLAB: Final = 1.0


@dataclass(frozen=True, slots=True)
class ModelSupport:
    """Wo Stützsäulen auf dem **Modell** statt auf der Platte enden (§22.2).

    Getrennt nach außen und Kanal: Außen muss die Stütze auf dem Modell
    ansetzen dürfen, sonst sackt die Decke ab (der Tisch); im Kanal trägt
    sich die Decke selbst, und eine Stütze dort bleibt für immer darin (die
    Waschschüssel). Flächen in mm², Stücke als (Schicht, Stück) in
    ``LayerInfo.overhangs``.
    """

    open_patch: float = 0.0
    """Die größte Fläche eines Stücks, die außerhalb eines Kanals auf dem Modell aufsetzt —
    ohne Kanten, die sich selbst tragen (:func:`ledges`)."""
    open_area: float = 0.0
    """Wie viel außerhalb von Kanälen insgesamt auf dem Modell aufsetzt."""
    open_field: float = 0.0
    """Die größte Decke davon als Feld (:func:`_field`, RM-570), höchstens so viel,
    wie von ihr auf dem Modell aufsetzt; ``0.0``, wo es die Antwort nicht ändert."""
    channels: frozenset[tuple[int, int]] = frozenset()
    """Die Überhangstücke, deren Säule in einem Kanal auf dem Modell endet."""
    channel_layers: frozenset[int] = frozenset()
    """Schichten, deren Überhang ganz aus solchen Stücken besteht."""
    channel_area: float = 0.0
    channel_at: tuple[float, float, float] | None = None
    """Wo das größte Kanalstück hängt — für den Ort eines Befunds."""
    channel_columns: tuple[tuple[Polygon, float, float], ...] = ()
    """Je Kanalstück, dessen Decke ohne sich selbst zu schließen Stütze
    bräuchte, sein Grundriss mit der Höhe, auf der seine Säule aufsetzt, und der,
    auf der es hängt — daraus baut die Übergabe die Stützsperre."""
    island_on_model: bool = False
    """Setzt eine **Insel** auf dem Modell auf? Sie druckt ohne Stütze in die
    Luft, gleich wie klein sie ist, und ist deshalb nie eine Kanaldecke."""
    open_pieces: frozenset[tuple[int, int]] = frozenset()
    """Die Stücke, deren Säule außerhalb eines Kanals auf dem Modell aufsetzt —
    an ihnen fragt der Rat, ob eine lange Brücke ihre Stütze auf dem Modell
    braucht (:func:`open_bridge_width`)."""
    open_columns: tuple[tuple[Polygon, float, float], ...] = ()
    """Von diesen Stücken die, die selbst Stütze brauchen (Insel, oder ihre Decke
    genügt :func:`worth_support`), wie ``channel_columns``: Grundriss, Höhe der
    Auflage, Höhe des Stücks. Die Stützsperre spart ihre Säulen aus
    (:func:`channel_space`); leer ohne Sperre."""
    bed_columns: tuple[tuple[Polygon, float, float], ...] = ()
    """Ebenso die Stücke, deren Säule das Bett erreicht: Grundriss, Höhe der
    untersten Schicht, Höhe des Stücks."""


def overhang_outline(result: SliceResult) -> ShapelyPolygon | MultiPolygon | None:
    """Wo gestützt wird, in der Aufsicht: alle Überhänge des Körpers vereinigt (RM-312).

    Die Slicer setzen Stützen und ihren verbreiterten Fuß unter die Überhänge,
    nicht unter das ganze Teil. Gemessen an der Aufsicht bekam die
    Waschschüssel am Kobra 2 mit Stützen eine Warnung, der Stützfuß reiche über
    das Bett, während die erste Stützschicht im G-Code 15 mm vom Rand blieb.
    Ein Überhang über dem Modell steht mit darin — seine Säule endet auf dem
    Modell, nicht auf dem Bett; der Umriss ist damit eher zu groß als zu klein.
    ``None`` ohne Überhang: Dann stützt kein Slicer, und es gibt keinen Fuß.
    """
    pieces = [
        ShapelyPolygon(piece.outline, piece.holes)
        for layer in result.layers
        for piece in layer.overhangs
    ]
    if not pieces:
        return None
    joined = unary_union(pieces)
    if joined.is_empty:
        return None
    return joined if isinstance(joined, ShapelyPolygon | MultiPolygon) else None


def support_on_model(result: SliceResult) -> bool:
    """Endet eine Stützsäule außerhalb eines Kanals auf dem **Modell**? (§22.2)

    Die Kurzform von :func:`model_support` für den, der nur Ja oder Nein
    braucht.
    """
    return model_support(result).open_patch > EPS_GEOM


def open_bridge_width(
    result: SliceResult,
    model: ModelSupport,
    bridge_from: float = BRIDGE_FROM,
    *,
    above: float = 0.0,
) -> float:
    """Die längste Brücke, die über einem Stück außerhalb der Kanäle auf dem
    Modell hängt, in mm (§22.2).

    ``LayerInfo.bridge_width`` gilt der ganzen Schicht. An der Waschschüssel
    (04.10.2026, Cura-Raster) war die Brücke von 17,3 mm das Gewölbe des
    Kanals, und daneben hing auf derselben Schicht ein offenes Stück von
    9,9 mm²; je für sich spannten sie 7,9 und 11,5 mm. Gemessen wird deshalb
    nur die freie Fläche, die ein offenes Stück berührt, mit der Mindestwand,
    mit der die Schicht gemessen wurde. Schichten, deren ganze Brücke nicht
    über ``above`` reicht, werden nicht gefragt — ein Teil ihrer Fläche spannt
    nie weiter.
    """
    pieces: dict[int, list[ShapelyPolygon]] = {}
    for index, number in sorted(model.open_pieces):
        if index > 0 and result.layers[index].bridge_width > above:
            piece = result.layers[index].overhangs[number]
            pieces.setdefault(index, []).append(ShapelyPolygon(piece.outline, piece.holes))
    return max(
        (
            _bridge_width(
                _material(result.layers[index]),
                _material(result.layers[index - 1]),
                bridge_from,
                touching=unary_union(found),
            )
            for index, found in pieces.items()
        ),
        default=0.0,
    )


def model_support(
    result: SliceResult,
    channel_width: float = CHANNEL_WIDTH,
    *,
    only: frozenset[tuple[int, int]] | None = None,
) -> ModelSupport:
    """Welche Stützsäulen auf dem Modell enden, und ob in einem Kanal (§22.2).

    ``only`` fragt nur diese Stücke (Schicht, Stück). Keine Säule beschneidet
    eine andere, also bekommt jedes Stück dieselbe Antwort wie im ganzen
    Durchgang — nur ohne die übrigen sechzehntausend eines Gitterwerks, wenn
    jemand bloß wissen will, ob ein einzelnes Stück eine Kanaldecke ist
    (``findings.overhang_findings``).

    Die Frage, an der „Stützen nur von der Platte" hängt. Geschlossen wurde
    sie aus „keine Insel", und das ist etwas anderes: Ein Tisch — Bodenplatte
    40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte 40 auf 40 —
    hat keine einzige Insel und 1 492 mm² Überhang auf einer Schicht, und
    jede Stütze darunter steht auf der Bodenplatte. Der Vorschlag
    ``build_plate`` ließ die Tischplatte im Druck absacken.

    **Und nicht jede Säule auf dem Modell ist ein Grund für „überall".** Die
    Waschschüssel (25.09.2026) führt Wasser von einem Becher durch einen
    Kanal zu einer Düse; mit „Stützen überall" füllte der Slicer den Kanal
    auf 40 mm Höhe mit Stütze, die niemand mehr herausbekommt — Robert:
    „die Stützen sind sinnlos und gehen durch das Modell". Eine Säule steht
    in einem Kanal, wenn der freie Raum um sie herum auf halber Höhe keinen
    Kreis von ``channel_width`` fasst, der sie enthält (:func:`_in_channels`).

    Gerechnet wird derselbe Durchgang von oben nach unten wie beim
    Stützvolumen (:func:`_support_volume`), nur je Stück: Wo ein Teil einer
    Säule an Material verliert, setzt es dort auf, und dieser Ort wird
    einmal befragt. Der übliche Fall — alles erreicht die Platte — geht durch
    alle Schichten und stellt keine Kanalfrage.

    **Die ganze Frage wird je Messung gemerkt** (DRUCK-14, Durchsicht 0.5.1).
    Sie hängt nur an den Schichten, nicht an den Einstellungen — der
    Druckdialog stellte sie trotzdem bei jedem geänderten Feld und nach jeder
    nachgereichten Profilliste neu, an der Waschschüssel je 3,9 s. Gemerkt
    wird am Schichttupel selbst (Identität, nicht Gleichheit), für die letzten
    :data:`_ANSWERS_KEPT` Fragen. Die Stückauswahl (``only``) gehört zum
    Schlüssel, damit auch der Prüfbericht seine Kanalfrage nur einmal stellt.
    """
    with _ANSWERS_LOCK:
        for layers, width, selected, answer in _ANSWERS:
            if layers is result.layers and is_close(width, channel_width) and selected == only:
                return answer
    answer = _model_support(result, channel_width, only)
    with _ANSWERS_LOCK:
        _ANSWERS.append((result.layers, channel_width, only, answer))
        del _ANSWERS[:-_ANSWERS_KEPT]
    return answer


#: Wie viele beantwortete Kanalfragen :func:`model_support` behält — die
#: jüngsten, meist die Körper des offenen Druckdialogs. Ihre Schichttupel
#: bleiben dafür am Leben, und damit bleibt ihre Identität eindeutig.
_ANSWERS_KEPT: Final = 4
_ANSWERS: list[
    tuple[tuple[LayerInfo, ...], float, frozenset[tuple[int, int]] | None, ModelSupport]
] = []
_ANSWERS_LOCK = threading.Lock()


#: Wie weit eine Decke in der Aufsicht über das Material ragen darf, an dem sie
#: ansetzt, und sich noch selbst trägt, in Millimetern (:func:`ledges`).
LEDGE_REACH: Final = 3.0

#: Welcher Anteil einer Kante weiter als :data:`LEDGE_REACH` reichen darf —
#: die Rundung der Puffer und das Vernetzungsrauschen (:func:`_carried`).
LEDGE_SPILL: Final = 0.05


def ledges(result: SliceResult) -> frozenset[tuple[int, int]]:
    """Überhangstücke, deren Decke nicht weiter als :data:`LEDGE_REACH` über das
    Material ragt, an dem sie ansetzt — Kanten, die sich selbst tragen.

    Am Eiffelturm (08.10.2026, „一体无支撑“, ohne Stützen gedacht) verlangte
    der Rat Stützen wegen der Ränder der Plattformen: oben ein Kranz, der in
    drei Schichten 2,6 mm über den Schaft wächst, darunter Ränder unter 1 mm.
    Der ElegooSlicer stellte dafür 831 m Baumstütze außen am Turm hoch. Gemessen
    wird die ganze Decke (:class:`_Ceilings`), nicht das Stück: Die Streifen
    einer schrägen Unterseite ragen je Schicht kaum über die vorige, ein Kinn
    als Ganzes aber 18 mm über die Kehle. Wurzel ist die Schicht unter dem
    untersten Stück. Inseln sind nie Kanten. Gemerkt wie die Kanalfrage.
    """
    with _ANSWERS_LOCK:
        for layers, answer in _LEDGES:
            if layers is result.layers:
                return answer
    answer = _ledges(result)
    with _ANSWERS_LOCK:
        _LEDGES.append((result.layers, answer))
        del _LEDGES[:-_ANSWERS_KEPT]
    return answer


_LEDGES: list[tuple[tuple[LayerInfo, ...], frozenset[tuple[int, int]]]] = []


def _ledges(result: SliceResult) -> frozenset[tuple[int, int]]:
    """Die Kantenfrage selbst, ungemerkt (:func:`ledges`)."""
    layers = result.layers
    materials: dict[int, ShapelyPolygon] = {}

    def material(index: int) -> ShapelyPolygon:
        if index not in materials:
            materials[index] = _material(layers[index])
        return materials[index]

    ceilings = _Ceilings(layers, material)
    seen: set[tuple[int, int]] = set()
    found: set[tuple[int, int]] = set()
    for index, layer in enumerate(layers):
        for number in range(len(layer.overhangs)):
            name = (index, number)
            if name in seen or ceilings.floats(name):
                continue
            group = ceilings.of(name)
            seen |= group
            low = min(member[0] for member in group)
            if low < 1:
                continue
            field = unary_union([ceilings.shape(member) for member in sorted(group)])
            if _carried(field, material(low - 1)):
                found |= group
    return frozenset(found)


def ledge_space(
    result: SliceResult, line_width: float
) -> list[tuple[float, float, ShapelyPolygon]]:
    """Wo die Stützsperre Kanten freihält, die sich selbst tragen (:func:`ledges`):
    (unten, oben, Fläche) je :data:`CHANNEL_SLAB`.

    Gesperrt wird die Überhangfläche der Kanten selbst, um eine Bahnbreite
    hinaus — dort fragt der Slicer, ob er stützt; Stämme anderer Stützen laufen
    durch eine Sperre hindurch. Jede Scheibe reicht eine Scheibenhöhe unter ihre
    Kanten. Überhänge, die Stütze brauchen, bleiben frei: Ihre Fläche in dieser
    und der Scheibe darunter wird ausgespart, ebenfalls um eine Bahnbreite.
    """
    edges = ledges(result)
    if not edges:
        return []
    found: dict[int, list[ShapelyPolygon]] = {}
    needed: dict[int, list[ShapelyPolygon]] = {}
    for index, layer in enumerate(result.layers):
        slab = math.floor(layer.z / CHANNEL_SLAB)
        for number, piece in enumerate(layer.overhangs):
            shape = ShapelyPolygon(piece.outline, piece.holes)
            target = found if (index, number) in edges else needed
            target.setdefault(slab, []).append(shape)
    slabs: list[tuple[float, float, ShapelyPolygon]] = []
    for slab, shapes in sorted(found.items()):
        region = unary_union(shapes).buffer(line_width, join_style="mitre")
        nearby = needed.get(slab, []) + needed.get(slab - 1, [])
        if nearby:
            region = region.difference(unary_union(nearby).buffer(line_width, join_style="mitre"))
        if region.area <= EPS_GEOM:
            continue
        slabs.append(((slab - 1) * CHANNEL_SLAB, (slab + 1) * CHANNEL_SLAB, region))
    return slabs


def _carried(field: Any, root: ShapelyPolygon) -> bool:
    """Liegt ``field`` ganz innerhalb von :data:`LEDGE_REACH` um ``root``?

    Gefragt wird die Fläche, nicht der Rand: Eine flache Decke zwischen zwei
    Wänden hat alle Ecken auf den Wänden und spannt in der Mitte trotzdem weit.
    Was weiter liegt, darf :data:`LEDGE_SPILL` des Felds sein — am Kranz des
    Eiffelturms 1,0 von 214 mm², an einer Fase von 52° über 5 mm 124 von 281.
    Ein Saum entlang des Umfangs taugte nicht: Die Streifen einer Fase haben
    zusammen zehn Meter Rand.
    """
    if field.is_empty:
        return True
    low_x, low_y, high_x, high_y = field.bounds
    margin = 2.0 * LEDGE_REACH
    near = shapely.clip_by_rect(
        root, low_x - margin, low_y - margin, high_x + margin, high_y + margin
    )
    if near.is_empty:
        return False
    beyond = field.difference(near.buffer(LEDGE_REACH))
    return bool(beyond.area <= LEDGE_SPILL * field.area)


class _Ceilings:
    """Welche Überhangstücke zu einer Decke gehören (:func:`_model_support`).

    Eine schräge Decke zerfällt im Schnitt in Streifen, je Schicht einen: Jeder
    beginnt dort, wo die Schicht darunter mit ihrer Überhangzugabe endet.
    Zwei Stücke benachbarter Schichten gehören deshalb zusammen, wenn das
    untere dem oberen so nahe liegt wie das Material seiner Schicht überhaupt
    — bis auf :data:`OVERHANG_MARGIN`, das Vernetzungsrauschen. So braucht die
    Frage weder Winkel noch Schichthöhe, und die Abstände in benachbarten
    Streifen (an der Waschschüssel 0,1384 gegen 0,1386 mm) stimmen trotz der
    Kreisbögen der Zugabe überein. Inseln gehören zu keiner Decke: Sie hängen
    in der Luft, und ihr nächstes Material sagt nichts über ihren Anschluss.
    """

    def __init__(
        self, layers: tuple[LayerInfo, ...], material: Callable[[int], ShapelyPolygon]
    ) -> None:
        self._layers = layers
        self._material = material
        self._shapes: dict[tuple[int, int], ShapelyPolygon] = {}
        self._floating: dict[int, ShapelyPolygon] = {}
        self._gaps: dict[tuple[int, int], float] = {}
        self._known: dict[tuple[int, int], frozenset[tuple[int, int]]] = {}

    def shape(self, name: tuple[int, int]) -> ShapelyPolygon:
        """Das Stück ``name`` (Schicht, Nummer) als Fläche."""
        if name not in self._shapes:
            contour = self._layers[name[0]].overhangs[name[1]]
            self._shapes[name] = ShapelyPolygon(contour.outline, contour.holes)
        return self._shapes[name]

    def floats(self, name: tuple[int, int]) -> bool:
        """Liegt das Stück auf einer Insel seiner Schicht?"""
        layer = self._layers[name[0]]
        if not layer.islands:
            return False
        if name[0] not in self._floating:
            self._floating[name[0]] = unary_union(
                [ShapelyPolygon(item.outline, item.holes) for item in layer.islands]
            )
        return bool(self.shape(name).intersection(self._floating[name[0]]).area > EPS_GEOM)

    def _gap(self, name: tuple[int, int]) -> float:
        """Wie weit das Stück vom Material der Schicht darunter entfernt ist."""
        if name not in self._gaps:
            below = self._material(name[0] - 1)
            self._gaps[name] = (
                math.inf if below.is_empty else float(shapely.distance(self.shape(name), below))
            )
        return self._gaps[name]

    def _neighbours(self, name: tuple[int, int], index: int) -> list[tuple[int, int]]:
        """Die Stücke der Schicht ``index`` (darüber oder darunter), an die ``name`` anschließt."""
        others = [
            (index, number)
            for number in range(len(self._layers[index].overhangs))
            if not self.floats((index, number))
        ]
        if not others:
            return []
        # Ein Aufruf je Nachbarschicht statt je Paar.
        distances = shapely.distance(self.shape(name), [self.shape(other) for other in others])
        return [
            other
            for other, distance in zip(others, distances, strict=True)
            if float(distance) <= self._gap(name if index < name[0] else other) + OVERHANG_MARGIN
        ]

    def closes(self, ceiling: frozenset[tuple[int, int]]) -> bool:
        """Liegt die Decke auf wie eine Decke — ihr Grundriss in der Aufsicht
        zwischen seinen Auflagen auf dem Material darunter oder ringsum
        gehalten — und nicht wie eine Auskragung?

        Gehalten ist, was dem Material unter einem Stück so nahe liegt wie das
        Stück überhaupt (:meth:`_gap`, die Überhangzugabe), bis auf
        :data:`OVERHANG_MARGIN`. Die Streifen eines Gewölbes hängen je an einer
        Wand und liegen eine Zugabe auseinander; um diese Zugabe geschlossen ist
        ihr Grundriss das Band zwischen beiden Wänden. Eine Brücke liegt an
        zwei Stellen auf, die Decke einer Sackgasse an einem U aus drei Seiten
        — so der Wasserkanal der Waschschüssel in Drucklage —, die Decke über
        einem Hohlraum ringsum, ein Kiefer nur an der Kehle. Gefragt wird der
        Grundriss und nicht das einzelne Stück: In Dateilage ist derselbe Kanal
        ein gekrümmtes Band, und an seiner Mündung hängt im obersten Streifen
        ein Splitter an nur einer Wand. Rand- und Haltestücke unter der
        doppelten Zugabe sind Rauschen; entschieden wird nach Fläche
        (:meth:`_spans`).

        **Die Decke hält sich nicht an sich selbst** (Review vom 08.10.2026):
        Unter dem Streifen k+1 einer schrägen Unterseite liegen die Streifen
        1 bis k derselben Decke. Zählte dieses Material, galten die Seiten jeder
        Konsole als gehalten, und ein Kiefer mit gewölbter Unterseite wurde in
        einer engen Tasche Kanal. Gehalten wird deshalb nur von Material neben
        dem Grundriss der Decke.
        """
        names = sorted(ceiling)
        shapes = [self.shape(name) for name in names]
        reaches = {
            name: self._gap(name) + OVERHANG_MARGIN
            for name in names
            if math.isfinite(self._gap(name))
        }
        closing = max(reaches.values(), default=0.0)
        footprint = unary_union(shapes).buffer(closing).buffer(-closing)
        # Das eigene Material ist der geschlossene Grundriss, nicht nur die
        # Stücke: Zwischen den Streifen einer schrägen Unterseite liegt je
        # Schicht ein Band der Überhangzugabe, Material derselben Decke in
        # keinem Stück. Ab gut 15° Neigung (60°-Grenze der Orca-Familie) hielt
        # es die Seiten eines Kiefers wieder fest (Review 2 vom 08.10.2026).
        own = footprint.buffer(OVERHANG_MARGIN / 2.0)
        held: list[Any] = []
        for name, shape in zip(names, shapes, strict=True):
            if name not in reaches:
                continue
            reach = reaches[name]
            # Nur das Material in Reichweite aufweiten, nicht die ganze
            # Schicht — am Drachen hat eine Schicht tausende Ecken.
            low_x, low_y, high_x, high_y = shape.bounds
            near = shapely.clip_by_rect(
                self._material(name[0] - 1),
                low_x - 2.0 * reach,
                low_y - 2.0 * reach,
                high_x + 2.0 * reach,
                high_y + 2.0 * reach,
            ).difference(own)
            # Splitter in den Kerben des gerundet geschlossenen Grundrisses
            # sind Rauschen, kein Halt.
            kept = [part for part in _areas_of(near) if part.area > closing * closing]
            if kept:
                held.append(unary_union(kept).buffer(reach))
        if not held:
            return False
        anchored = unary_union(held)
        spanned = asked = 0.0
        for part in _areas_of(footprint):
            spans = self._spans(part, anchored, closing)
            if spans is None:
                continue
            asked += part.area
            spanned += part.area if spans else 0.0
        return spanned > 0.0 and 2.0 * spanned >= asked

    @staticmethod
    def _spans(part: ShapelyPolygon, anchored: Any, closing: float) -> bool | None:
        """Liegt dieser Teil des Grundrisses zwischen seinen Auflagen?

        Ringsum gehalten, oder zu :data:`CEILING_SPANNED` in der Hülle seiner
        gehaltenen Randstücke: eine Brücke zwischen zwei Stirnseiten, ein U, ein
        Gewölbe zwischen zwei Wänden. Ein Eckregal an zwei angrenzenden Wänden
        füllt seine Hülle nur zur Hälfte, ein Kiefer an der Kehle fast nicht.
        ``None`` für einen Teil ohne gehaltenen Rand: Seine Auflage liegt in der
        Aufsicht unter einem anderen Stück derselben Decke, und er entscheidet
        nicht mit.
        """
        rim = part.boundary
        # Zusammengefügt, bevor nach Länge gesiebt wird: Ein Lauf über den
        # Anfangspunkt des Rings kam sonst als zwei halbe heraus und fiel unter
        # die Rauschgrenze, je nachdem, wo GEOS den Ring beginnt (Review 2).
        loose = [
            line for line in _merged_lines(rim.difference(anchored)) if line.length > 2.0 * closing
        ]
        if not loose:
            return True
        held = [
            line
            for line in _merged_lines(rim.difference(unary_union(loose).buffer(EPS_GEOM)))
            if line.length > 2.0 * closing
        ]
        if not held:
            return None
        between = shapely.convex_hull(shapely.multilinestrings(held)).buffer(closing)
        return bool(part.intersection(between).area >= CEILING_SPANNED * part.area)

    def of(self, start: tuple[int, int]) -> frozenset[tuple[int, int]]:
        """Die Decke, zu der ``start`` gehört, samt ``start``."""
        if start in self._known:
            return self._known[start]
        if start[0] < 1 or self.floats(start):
            return frozenset({start})
        found = {start}
        waiting = [start]
        while waiting:
            name = waiting.pop()
            for index in (name[0] - 1, name[0] + 1):
                if not 1 <= index < len(self._layers):
                    continue
                for other in self._neighbours(name, index):
                    if other not in found:
                        found.add(other)
                        waiting.append(other)
        ceiling = frozenset(found)
        self._known.update(dict.fromkeys(ceiling, ceiling))
        return ceiling


def _model_support(
    result: SliceResult,
    channel_width: float,
    only: frozenset[tuple[int, int]] | None,
) -> ModelSupport:
    """Die Kanalfrage selbst, ungemerkt (:func:`model_support`)."""
    layers = result.layers
    # Material einmal je Schicht für alle Säulen und die unveränderte Kanalfrage.
    materials: dict[int, tuple[ShapelyPolygon, manifold3d.CrossSection]] = {}
    building = threading.Lock()

    def material_at(index: int) -> tuple[ShapelyPolygon, manifold3d.CrossSection]:
        with building:
            if index not in materials:
                shape = _material(layers[index])
                materials[index] = shape, _material_cross(shape)
            return materials[index]

    ceilings = _Ceilings(layers, lambda index: material_at(index)[0])
    # Einzelne Stücke bekommen dieselbe Antwort wie im ganzen Durchgang — und
    # die hängt seit der Decke als Ganzes an den Stücken ihrer Decke: Gefragt
    # wird deshalb jede Decke, zu der ein gewähltes Stück gehört.
    wanted: set[tuple[int, int]] | None = None
    if only is not None:
        wanted = set()
        for name in sorted(only):
            if name not in wanted:
                wanted |= ceilings.of(name)
    areas: list[float] = []
    names: list[tuple[int, int]] = []
    pieces: list[ShapelyPolygon] = []
    starts: dict[int, list[int]] = {}
    for index in range(len(layers) - 1, 0, -1):
        for number, contour in enumerate(layers[index].overhangs):
            if wanted is not None and (index, number) not in wanted:
                continue
            starts.setdefault(index, []).append(len(areas))
            names.append((index, number))
            areas.append(piece_area(contour))
            pieces.append(ceilings.shape((index, number)))
    if not starts:
        return ModelSupport()
    top = max(starts)

    # **Die Säulen verteilen sich auf Arbeiter**, wie beim Stützvolumen: Keine
    # beschneidet eine andere, also rechnet jede Gruppe denselben Durchgang
    # für die Stücke ihrer Schichten. Am Eiffelturm aus dem Korpus (16 323
    # Stücke) lief er einfädig 7,7 s.
    starting = sorted(starts, reverse=True)
    groups = min(_workers(SUPPORT_WORKERS), len(starting)) if len(layers) >= PARALLEL_FROM else 1
    member = {index: number % groups for number, index in enumerate(starting)}

    def descend(group: int) -> dict[int, tuple[int, float]]:
        pending: list[tuple[int, manifold3d.CrossSection]] = []
        landed: dict[int, tuple[int, float]] = {}
        for index in range(top, 0, -1):
            if member.get(index) == group:
                pending.extend((owner, _material_cross(pieces[owner])) for owner in starts[index])
            if not pending:
                continue
            _shared, below = material_at(index - 1)
            if below.is_empty():
                continue
            kept = []
            for owner, column in pending:
                remaining = column - below
                lost = float(column.area() - remaining.area())
                if lost > EPS_GEOM:
                    low, before = landed.get(owner, (index - 1, 0.0))
                    landed[owner] = (low, before + lost)
                if not remaining.is_empty():
                    kept.append((owner, remaining))
            pending = kept
        return landed

    if groups == 1:
        shares = [descend(0)]
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=groups) as pool:
            shares = list(pool.map(descend, range(groups)))
    # In der Folge der Stücke, nicht der Arbeiter: Jedes Stück gehört genau
    # einer Gruppe, und die Summen darunter hängen dann nicht daran, wer
    # zuerst fertig war.
    landed = {owner: share[owner] for share in shares for owner in share}
    landed = {owner: landed[owner] for owner in sorted(landed)}

    if not landed:
        return ModelSupport()
    islands: set[int] = set()
    channels: set[int] = set()
    places: dict[int, Any] = {}
    asked: dict[int, list[int]] = {}
    for owner, (low, _area) in landed.items():
        if ceilings.floats(names[owner]):
            # Eine Insel ist nie eine Decke, die sich selbst schließt: Sie
            # hat nichts unter sich, an dem eine Brücke ansetzen könnte.
            islands.add(owner)
            continue
        # **Gemessen wird unmittelbar unter der Decke**, nicht auf halber
        # Höhe der Säule. Die Frage ist, ob sich die Decke selbst schließt,
        # und das entscheidet die Weite, die sie überspannen muss: Der
        # Wasserkanal der Waschschüssel ist auf halber Höhe 42 mm weit und
        # unter seinem Gewölbe 22 mm. Eine flache Decke über einem weiten
        # Raum bleibt dabei weit — der Tisch, der Kasten mit Innenregal.
        # Gefragt wird am Stück selbst: Wo seine Säule aufsetzt, kann der
        # Raum weiter sein als unter der Decke (der Boden des Kanals).
        under = max(names[owner][0] - 1, low + 1)
        places[owner] = pieces[owner].representative_point()
        asked.setdefault(under, []).append(owner)

    # Eine Frage je Schicht, nicht je Säule (:func:`_in_channels`), und die
    # Schichten nebeneinander: Jede fragt nur ihre eigene Fläche.
    def answer(under: int) -> list[bool]:
        return _in_channels(
            material_at(under)[0], [places[owner] for owner in asked[under]], channel_width
        )

    if groups == 1 or len(asked) < 2:
        answers = [answer(under) for under in asked]
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=groups) as pool:
            answers = list(pool.map(answer, asked))
    for under, closed in zip(asked, answers, strict=True):
        channels.update(owner for owner, shut in zip(asked[under], closed, strict=True) if shut)

    # **Eine Decke ist als Ganzes Kanal oder Brücke** (Wedge-Lock, 05.10.2026).
    # Die Frage oben gilt dem Ort eines Stücks, und das erste Stück einer
    # schrägen Decke liegt oft an der Wand: An der 0,25er Düse (0,08 mm) waren
    # es zwei Ausrundungen von zusammen 0,0 mm² an den Beinen einer Brücke von
    # 25 mm, und an der Wand fasst der Raum keinen Kreis von ``channel_width``.
    # Die vier Schichten Brücke darüber hingen frei, verlangten Stützen, und
    # die Sperre um die zwei Ausrundungen nahm sie ihnen alle — bei 0,2 mm gab
    # es keine solche Schicht. Zusammen gehört, was in benachbarten Schichten
    # aneinander anschließt (:class:`_Ceilings`); liegt die Decke zum größeren
    # Teil außerhalb eines Kanals, ist keines ihrer Stücke einer. Andersherum nicht: Ein
    # offenes Stück an der Mündung eines Kanals (die Waschschüssel) bleibt
    # offen und behält seine Stütze.
    owner_of = {name: owner for owner, name in enumerate(names)}
    settled: set[int] = set()
    unblocked: set[int] = set()
    for owner in sorted(channels):
        if owner in settled:
            continue
        ceiling = sorted(owner_of[name] for name in ceilings.of(names[owner]))
        settled.update(ceiling)
        inside = math.fsum(areas[member] for member in ceiling if member in channels)
        hanging = math.fsum(areas[member] for member in ceiling if member not in channels)
        if hanging > inside:
            channels.difference_update(ceiling)
            continue
        # **Und sie liegt auf wie eine Decke, nicht wie eine Auskragung**
        # (Drache, 08.10.2026, :meth:`_Ceilings.closes`): Die Kreisfrage misst,
        # ob der Raum unter einem Stück schmal ist, nicht, ob die Decke darüber
        # Halt findet. Ein Kiefer über der Brust hängt nur an der Kehle.
        if not ceilings.closes(frozenset(names[member] for member in ceiling)):
            channels.difference_update(ceiling)
            continue
        # **Eine Sperre bekommt nur eine Decke, die ohne sich selbst zu
        # schließen Stütze bräuchte** — die zwei Wege von :func:`worth_support`,
        # gefragt am größten **Stück**, nicht am Feld wie Stützbedarf und
        # Aussparung: Wo eine Decke über Stütze oder keine entscheidet, fällt
        # der Zweifel auf Stütze. Als Feld sperrte der Drache bei 130 % eine
        # zweite Decke (149 mm² in 48 Streifen) und nahm fast doppelt so viel
        # stützbedürftige Fläche unter die Sperre, 451 statt 236 mm² (Review 3).
        # Nur dort stellte der Slicer nennenswert Stütze in den Kanal. Am
        # Drachen schlossen sich Taschen zwischen Schuppen, Stacheln und
        # Flügelhaut, die größte mit 96 mm²
        # insgesamt; ihre Sperren nahmen den Überhängen daneben die Stütze, und
        # im ElegooSlicer druckten Kopf und Flügel in die Luft. Der Wasserkanal
        # der Waschschüssel hängt mit 922 mm² (in Drucklage 176 mm², 86 mm² auf
        # einmal). Kanal bleibt die kleine Decke trotzdem: Sie trägt sich
        # selbst, wie die Schlitze eines Kotschiebers aus dem Korpus, und zählt
        # nicht zum Stützbedarf.
        largest = max(areas[member] for member in ceiling)
        total = math.fsum(areas[member] for member in ceiling)
        if not worth_support(largest, total):
            unblocked.update(ceiling)

    # Die Kanalstücke aller gefragten Decken, bevor die Auswahl sie kürzt: Die
    # Aussparung fragt eine Decke ohne sie, wie :func:`largest_sloped_patch`.
    in_channel = frozenset(names[owner] for owner in channels)
    # Gemeldet wird, wonach gefragt war; die übrigen Stücke ihrer Decken
    # haben nur mitentschieden.
    reported = set(landed) if only is None else {owner for owner in landed if names[owner] in only}
    channels &= reported
    landed = {owner: entry for owner, entry in landed.items() if owner in reported}
    islands &= reported
    # Kanten tragen sich selbst (:func:`ledges`) und verlangen keine Stütze auf
    # dem Modell — am Eiffelturm die Ränder der Plattformen.
    edges = ledges(result)
    bearing = {owner for owner in landed if owner not in channels and names[owner] not in edges}
    outside = [area for owner, (_low, area) in landed.items() if owner in bearing]
    open_patch = max(outside, default=0.0)
    open_area = math.fsum(outside)
    island_on_model = bool(islands)
    # **Und als Feld** (RM-570, Review 3): Ein Kinn mit schräger Unterseite
    # über der Brust zerfällt in Streifen unter 10 mm². Je Stück gefragt,
    # verlangte der Rat Stützen und zugleich „nur vom Bett“, und das Kinn
    # druckte weiter in die Luft. Gezählt wird, was auf dem Modell aufsetzt;
    # gefragt nur, wo ein Feld die Antwort ändern kann.
    open_field = 0.0
    if not worth_support(open_patch, open_area) and open_area > OVERHANG_LAYER_WORTH_SUPPORT:
        resting = {names[owner]: area for owner, (_low, area) in landed.items() if owner in bearing}
        seen: set[tuple[int, int]] = set()
        for name in sorted(resting):
            if name in seen:
                continue
            group = ceilings.of(name)
            seen |= group
            members = sorted(group & resting.keys())
            field = _field([ceilings.shape(member) for member in members])
            open_field = max(
                open_field, min(field, math.fsum(resting[member] for member in members))
            )

    chosen = frozenset(names[owner] for owner in channels)
    columns = tuple(
        (
            layers[names[owner][0]].overhangs[names[owner][1]],
            float(layers[landed[owner][0]].z),
            float(layers[names[owner][0]].z),
        )
        for owner in sorted(channels - unblocked, key=lambda owner: names[owner])
    )
    counted: dict[int, int] = {}
    for index, _number in chosen:
        counted[index] = counted.get(index, 0) + 1
    widest = max(channels, key=lambda owner: (areas[owner], names[owner]), default=None)
    at = None
    if widest is not None:
        point = places[widest]
        at = (float(point.x), float(point.y), float(layers[names[widest][0]].z))

    # **Ausgespart wird, was selbst Stütze braucht** (Waschschüssel, 08.10.2026):
    # eine Insel, oder ein Stück, dessen Decke ohne ihre Kanalstücke als Feld
    # (:func:`_field`) ``worth_support`` genügt — die Brücke am Wedge-Lock, der
    # Kiefer, die Flughaut, auch in Streifen zerfallen. Was Solidon für
    # selbsttragend hält, darf unter die Sperre: Ein Stachel neben einer
    # gesperrten Tasche (Feld 12 bis 24 mm²) verliert dort bis zu 81 % seiner
    # Unterseite (Review 2 und 3). An der Mündung des Wasserkanals hängt ein
    # offenes Stück von 11 mm², das sich selbst trägt; ausgespart, holte der
    # ElegooSlicer es mit einem Ast quer durch den Kanal (1,4 m Stütze darin).
    # Gefragt wird nur, wenn gesperrt wird — sonst kosten die Decken nichts.
    worth_of: dict[frozenset[tuple[int, int]], bool] = {}

    def needs_own(owner: int) -> bool:
        name = names[owner]
        if ceilings.floats(name):
            return True
        group = ceilings.of(name)
        if group not in worth_of:
            shapes = [ceilings.shape(member) for member in sorted(group - in_channel)]
            worth_of[group] = worth_support(
                _field(shapes), math.fsum(shape.area for shape in shapes)
            )
        return worth_of[group]

    spared = set() if not columns else {owner for owner in range(len(names)) if needs_own(owner)}
    return ModelSupport(
        open_patch=open_patch,
        open_area=open_area,
        open_field=open_field,
        channels=chosen,
        channel_layers=frozenset(
            index for index, count in counted.items() if count == len(layers[index].overhangs)
        ),
        channel_area=math.fsum(areas[owner] for owner in sorted(channels)),
        channel_at=at,
        channel_columns=columns,
        island_on_model=island_on_model,
        open_pieces=frozenset(names[owner] for owner in sorted(bearing)),
        open_columns=tuple(
            (
                layers[names[owner][0]].overhangs[names[owner][1]],
                float(layers[landed[owner][0]].z),
                float(layers[names[owner][0]].z),
            )
            for owner in sorted(landed, key=lambda owner: names[owner])
            if owner not in channels and owner in spared
        ),
        bed_columns=tuple(
            (
                layers[names[owner][0]].overhangs[names[owner][1]],
                float(layers[0].z),
                float(layers[names[owner][0]].z),
            )
            for owner in range(len(names))
            if owner not in landed and (only is None or names[owner] in only) and owner in spared
        ),
    )


def _material(layer: LayerInfo) -> ShapelyPolygon:
    """Die Fläche einer Schicht für Prädikate und Differenzen, ohne Vereinigung.

    Die Konturen kommen aus einer gültigen Fläche (:func:`_to_polygons`) und
    überschneiden sich nicht; :func:`_layer_shape` vereinigt sie trotzdem, und
    an der Waschschüssel mit zwanzig Konturen je Schicht kostete das
    0,4 s von 2,9 für eine Frage, die keine Vereinigung braucht.
    """
    parts = [ShapelyPolygon(contour.outline, contour.holes) for contour in layer.contours]
    if not parts:
        return ShapelyPolygon()
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def channel_space(
    result: SliceResult, model: ModelSupport, line_width: float
) -> list[tuple[float, float, ShapelyPolygon]]:
    """Der freie Raum der Kanäle, in Höhenscheiben: (unten, oben, Fläche) (§22.2).

    Die Stützsperre der Übergabe baut daraus ihren Körper. Die Grundrisse der
    Deckenstücke allein reichen dafür nicht: Der Slicer liest Überhänge mit
    seiner eigenen Regel und findet im Kanal mehr als Solidon. In Drucklage der
    Waschschüssel ließ eine Sperre nur unter den Deckenstücken im ElegooSlicer
    1,05 m Stütze im Wasserkanal stehen, die mit Umkreis 0,0 m, ohne Sperre
    9,7 m (08.10.2026). Gesperrt wird deshalb der Raum selbst: je Scheibe die
    freie Fläche im Umkreis ``CHANNEL_WIDTH / 2`` der Kanalsäulen innerhalb der
    Hülle des Teils, und davon nur, was mit einer Säule zusammenhängt — ein
    freier Raum jenseits der Wand bleibt frei, und ebenso die Luft vor einer
    Mündung.

    Der Raum greift eine Bahnbreite (``line_width``) über sich hinaus, damit
    auch der Rand darunter liegt, den der Slicer mit seinem eigenen Winkel noch
    als Überhang liest; doppelt so breit muss er sein, damit er gesperrt wird —
    eine Bahn samt Abstand. Fest auf die 0,4er Düse (0,5 mm) gerechnet, sperrte
    er an der 0,8er Spalten, in die keine Bahn passt, und ließe an der 0,25er
    welche offen — hergeleitet, nicht im Slicer gemessen (Review vom
    08.10.2026, Regel 8).

    Den Umkreis bekommt nur, was eine Sperre lohnt (``channel_columns``, Drache
    vom 08.10.2026): Um die Taschen einer Figur nahm er Kiefer, Kopf und
    Flügelbögen die Stütze.

    **Gemerkt wie die Kanalfrage** (:func:`model_support`), an Schichttupel und
    Antwort: Der Rat fragt je Prozess und nach jedem geänderten Feld, ob die
    Sperre Raum sperrt, die Schätzung je Gruppe zweimal, der Schreiber noch
    einmal — am Drachen bei 130 % je 2,0 s (Review vom 08.10.2026).
    """
    with _SPACES_LOCK:
        for layers, asked, width, known in _SPACES:
            if layers is result.layers and asked is model and abs(width - line_width) <= EPS_GEOM:
                return list(known)
    slabs = _channel_space(result, model, line_width)
    with _SPACES_LOCK:
        _SPACES.append((result.layers, model, line_width, tuple(slabs)))
        del _SPACES[:-_ANSWERS_KEPT]
    return slabs


_SPACES: list[
    tuple[
        tuple[LayerInfo, ...],
        ModelSupport,
        float,
        tuple[tuple[float, float, ShapelyPolygon], ...],
    ]
] = []
_SPACES_LOCK = threading.Lock()


def _channel_space(
    result: SliceResult, model: ModelSupport, line_width: float
) -> list[tuple[float, float, ShapelyPolygon]]:
    """:func:`channel_space`, ungemerkt."""
    columns = model.channel_columns
    if not columns:
        return []
    layers = result.layers
    heights = [layer.z for layer in layers]
    # Der Schritt einer gewöhnlichen Schicht; die erste ist dicker.
    step = heights[-1] - heights[-2] if len(heights) > 1 else CHANNEL_SLAB
    stride = max(1, round(CHANNEL_SLAB / max(step, EPS_GEOM)))
    footprints = np.asarray(
        [ShapelyPolygon(item.outline, item.holes) for item, _low, _high in columns], dtype=object
    )
    reaches = shapely.buffer(footprints, CHANNEL_WIDTH / 2.0, quad_segs=CHANNEL_QUAD_SEGMENTS)
    lows = np.array([low for _outline, low, _high in columns])
    highs = np.array([high for _outline, _low, high in columns])
    # **Die Sperre hält Stützen aus dem Kanal fern, nicht von einer Decke, die
    # sie braucht.** Am Wedge-Lock (04.10.2026, Cura-Raster) lag ein Kanalstück
    # von 7 mm² unter einer Brücke von 25 mm, deren Säule auf dem Modell
    # aufsetzt; die Sperre um das Kanalstück füllte denselben Raum, und Cura
    # stützte die Brücke gar nicht (0,0 statt 2,0 m). Die Säulen der Stücke,
    # die selbst Stütze brauchen, bleiben deshalb frei — auf dem Modell und zum
    # Bett (``open_columns``, ``bed_columns``). Genau, ohne Zuschlag: Mit einem
    # halben Millimeter um jedes Stück wurde in Drucklage der Waschschüssel aus
    # einem Krümel von 0,33 mm² im Kanal ein Loch, und der OrcaSlicer stellte
    # 1,5 m Stütze hindurch (08.10.2026).
    spared = (*model.open_columns, *model.bed_columns)
    others = np.asarray(
        [ShapelyPolygon(item.outline, item.holes) for item, _low, _high in spared], dtype=object
    )
    other_lows = np.array([low for _outline, low, _high in spared])
    other_highs = np.array([high for _outline, _low, high in spared])
    bottom = float(lows.min())
    top = float(highs.max())
    indices = [index for index, z in enumerate(heights) if bottom <= z <= top]
    chunks = [indices[start : start + stride] for start in range(0, len(indices), stride)]

    def slab_of(chunk: list[int]) -> tuple[float, float, ShapelyPolygon] | None:
        z_low, z_high = heights[chunk[0]], heights[chunk[-1]]
        active = (lows <= z_high) & (highs >= z_low)
        if not active.any():
            return None
        # Die Umkreise einzeln aufgeweitet und dann vereinigt — umgekehrt,
        # erst die Grundrisse vereinigt und dann einmal aufgeweitet, kostete
        # der Puffer über tausende Ecken am Eiffelturm aus dem Korpus 91 s
        # statt 9.
        seeds = shapely.union_all(footprints[active])
        reach = shapely.union_all(reaches[active])
        # Die engste Stelle der Scheibe zählt: frei ist, was auf jeder ihrer
        # Schichten frei ist.
        material = unary_union([_material(layers[index]) for index in chunk])
        # **Und nur innerhalb des Teils**, in seiner konvexen Hülle: An einer
        # Mündung hängt der Kanal mit der Luft davor zusammen, und ohne diese
        # Grenze reichte die Sperre an einem Tunnel 15 mm aus ihr heraus.
        free = reach.intersection(material.convex_hull).difference(material)
        # **Und nur Raum, an den man nicht hinkommt** (Drache in Cura,
        # 08.10.2026): zu eng für einen Kreis von ``CHANNEL_WIDTH`` — derselbe
        # Kreis wie in der Kanalfrage — oder ringsum von Material umschlossen.
        # In einer Falte des Flügels hing eine echte Tasche; ihr Umkreis lief aus
        # ihr heraus in den offenen Raum unter dem Flügel, und Cura stützte dort
        # 96,3 statt 100 % der Überhangfläche außerhalb der Kanaldecken. Den
        # Kanal hält das trotzdem frei: Die Schüssel in Dateilage verliert so den
        # Sperrraum unter halber Säulenhöhe (147 906 → 28 862 mm³), und dort
        # stellte weder der PrusaSlicer (vorher 140,6 m) noch der ElegooSlicer
        # Stütze hin — sie trug nur die Decke, und die ist gesperrt (Review 2).
        narrow = _narrow(material, reach.bounds)
        enclosed = _enclosed(material)
        free = free.intersection(unary_union([narrow, enclosed]))
        # **Gesperrt wird nur Raum, in dem Stütze stehen könnte**: mindestens
        # zwei Übergriffe breit, eine Bahn samt Abstand. Am Drachen bestand die
        # Sperre um die Zwickel zwischen Schwanz- und Kinnstacheln aus 60 000
        # Krümeln unter 100 mm³ — kein Slicer stellt in einen solchen Spalt
        # eine Stütze.
        kept = [
            part
            for part in _areas_of(free)
            if part.intersects(seeds) and not _eroded(part, line_width).is_empty
        ]
        if not kept:
            return None
        # **Der Zuschlag, bevor ausgespart wird** (Review vom 08.10.2026): Der
        # Schreiber schob den Umriss erst danach um diesen Zuschlag hinaus,
        # und damit wieder in die ausgesparten Säulen — über dem Balkon neben
        # dem Tunnel lagen 8 bis 13 mm² im Sperrkörper, Säulen unter 1 mm
        # Breite schlossen sich ganz.
        grown = unary_union(kept).buffer(line_width, join_style="mitre")
        crossing = (
            (other_lows <= z_high + CHANNEL_SLAB) & (other_highs >= z_low)
            if len(others)
            else np.zeros(0, dtype=bool)
        )
        if crossing.any():
            # **Nicht im umschlossenen Raum** (Waschschüssel, 08.10.2026): Eine
            # Stütze dort holt niemand heraus. Im Rohrbogen des Wasserkanals
            # hängt eine schräge Fläche, die selbst Stütze bräuchte; ausgespart,
            # holte der ElegooSlicer sie mit einem Ast quer durch den Kanal
            # (1,6 m), ohne Aussparung 0,0 m. Enger gefasst ließ es den Ast
            # wieder hinein: „eng und umschlossen“ 0,7 m — der Rohrbogen ist
            # weit —, „zur Hälfte überdacht“ nahm der Schüssel fast die ganze
            # Sperre, weil ihr Kanal in einem oben offenen Hohlraum liegt. Die
            # Grenze: Ein Sims in einem offenen Becher neben einem gesperrten
            # Kanal verliert so Stütze (Review 2, RM-571).
            spare = shapely.union_all(others[crossing]).difference(enclosed)
            grown = grown.difference(spare)
        # Ein Loch, in dem keine Bahn samt Abstand Platz hat, ist keine Säule:
        # Ausgespart, ließ ein Krümel von 0,33 mm² im Wasserkanal der
        # Waschschüssel den OrcaSlicer 1,5 m Stütze hindurchstellen.
        kept = [_with_usable_holes(part, line_width) for part in _areas_of(grown)]
        if not kept:
            return None
        # **Eine Scheibe höher, in die Decke hinein.** Der Slicer fragt die
        # Sperre an der Überhangfläche, in deren eigener Schicht — und dort ist
        # die Decke Material, also kein freier Raum. Endete die Sperre unter
        # ihr, hielt sie im ElegooSlicer an der Waschschüssel fast nichts fern
        # (Gitter „überall" 86,8 → 86,3 m im freien Kanalraum, Baum 21,0 →
        # 18,4 m); eine Scheibe höher 87,8 → 0,0 und 22,5 → 1,7 m im
        # Sperrkörper. Eine Sperre druckt nicht; dass sie in die Decke ragt,
        # kostet nichts.
        return (z_low - step / 2.0, z_high + step / 2.0 + CHANNEL_SLAB, unary_union(kept))

    # Jede Scheibe fragt nur ihre eigenen Schichten; nebeneinander gerechnet,
    # in der Folge der Höhe zurückgegeben.
    if len(chunks) < 2 or len(layers) < PARALLEL_FROM:
        found = [slab_of(chunk) for chunk in chunks]
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=_workers(SUPPORT_WORKERS)) as pool:
            found = list(pool.map(slab_of, chunks))
    return [entry for entry in found if entry is not None]


def _in_channels(shape: ShapelyPolygon, points: list[Any], width: float) -> list[bool]:
    """Fasst der freie Raum um jeden dieser Punkte keinen Kreis der Weite
    ``width``, der ihn enthält?

    Ein solcher Kreis hat seinen Mittelpunkt höchstens r vom Punkt entfernt
    und mindestens r vom Material. Liegt die Scheibe vom Radius r um den
    Punkt ganz im Material, aufgeweitet um r, gibt es keinen solchen
    Mittelpunkt: Der Punkt liegt in einem Kanal. Material weiter als 2r vom
    Punkt entfernt trägt dazu nichts bei, also wird auf die Punkte samt
    diesem Rand zugeschnitten.

    **Aufgeweitet wird einmal je Schicht, und Teil für Teil.** Gemessen am
    Eiffelturm aus dem Korpus (14 755 Fragen in 532 Schichten, 26.09.2026):
    je Punkt ein erodiertes Fenster 1818 s, die freie Fläche der Schicht auf
    einmal erodiert 12,4 s, jedes Teil gepuffert und danach vereinigt 1,9 s.
    GEOS knotet beim Puffern einer Fläche mit vielen Löchern alle Ringe in
    einem Zug; die Kaskade vereinigt stattdessen kleine Stücke.

    **Im Zweifel offen.** Beide Puffer sind Vielecke, deren Ecken auf dem
    Kreis liegen, also kleiner als ihr Kreis. Die Scheibe um den Punkt wird
    deshalb umschrieben angelegt: Passt sie ins aufgeweitete Material, passt
    der wahre Kreis erst recht. Eingeschrieben sagte sie an der Waschschüssel
    an fünf Stellen „Kanal", deren größter freier Kreis Ø 30,07 bis 30,14 mm
    misst. Umschrieben stimmen dort alle 89 Antworten mit der Erosion überein;
    am Eiffelturm weichen 7 von 14 755 ab, alle zur offenen Seite und alle
    dort, wo ein freier Kreis der Weite den Punkt um 0,014 bis 0,025 mm
    verfehlt — innerhalb des doppelten Bogenfehlers.
    """
    radius = width / 2.0
    reach = 2.0 * radius + OVERHANG_MARGIN
    around = radius / exact_cos(math.pi / (4 * CHANNEL_QUAD_SEGMENTS))
    xs = [float(point.x) for point in points]
    ys = [float(point.y) for point in points]
    material = shapely.clip_by_rect(
        shape, min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach
    )
    parts = shapely.get_parts(material)
    parts = parts[shapely.get_type_id(parts) == shapely.GeometryType.POLYGON]
    if not len(parts):
        return [False] * len(points)
    grown = shapely.union_all(shapely.buffer(parts, radius, quad_segs=CHANNEL_QUAD_SEGMENTS))
    shapely.prepare(grown)
    discs = shapely.buffer(
        np.asarray(points, dtype=object), around, quad_segs=CHANNEL_QUAD_SEGMENTS
    )
    return [bool(shut) for shut in shapely.contains(grown, discs)]


def _total_area(parts: list[ShapelyPolygon]) -> float:
    """Die Fläche einer Liste von Teilen, in einem Aufruf."""
    if not parts:
        return 0.0
    return float(shapely.area(np.asarray(parts, dtype=object)).sum())


def piece_area(piece: Polygon) -> float:
    """Die Fläche einer Kontur samt Löchern, ohne GEOS — für viele kleine
    Stücke schneller als der Umweg über ein Polygon (:func:`units.ring_area`)."""
    return ring_area(piece.outline) - sum(ring_area(hole) for hole in piece.holes)


def taper_length(shape: ShapelyPolygon) -> float:
    """Wie viel Außenkontur dieser Schicht auf einem Keil liegt, in mm (§22.2).

    Die Wandstärke entlang der Außenkontur ist der Abstand zur nächsten
    Innenkontur desselben Teils. Gemessen alle :data:`TAPER_STEP` Millimeter,
    vektorisiert in GEOS — ein Aufruf je Außenring, nicht je Punkt. Gezählt
    werden zusammenhängende Strecken von Messpunkten, deren Stärke zwischen
    :data:`TAPER_FROM` und :data:`TAPER_TO` liegt und sich gegenüber einem
    Partner :data:`TAPER_WINDOW` weiter oder zurück um :data:`TAPER_RISE`
    unterscheidet; kürzer als :data:`TAPER_RUN` zählt eine Strecke nicht.

    Was das unterscheidet: Eine gleichmäßige Wand hat keinen Anstieg, auch um
    eine Rundung herum. Eine Trennwand, die rechtwinklig anschließt, springt
    in zwei Messpunkten über :data:`TAPER_TO` hinaus, und ein Partner
    außerhalb des Bandes zählt nicht. Nur die stetig dicker werdende Wand —
    Becher an der Ecke, Rippe, die in einen Bogen ausläuft, runde Außenecke
    über einer scharfen Innenecke — liefert eine lange Strecke mit Anstieg,
    und genau dort wechselt ein Slicer mit variabler Bahnbreite die Wandzahl.

    Ein Teil ohne Innenkontur hat keine Wand in diesem Sinn und meldet null.
    """
    if shape.is_empty:
        return 0.0
    total = 0.0
    # Abgetastet wird ab dem Anfangspunkt des Rings; der ist festgelegt
    # (:func:`_canonical`), sonst hinge der Keil am Weg, der den Schnitt baute.
    shape = _canonical(shape)
    parts = shape.geoms if isinstance(shape, MultiPolygon) else (shape,)
    window = max(1, round(TAPER_WINDOW / TAPER_STEP))
    for part in parts:
        if not part.interiors:
            continue
        inner = shapely.multilinestrings(
            [shapely.linestrings(np.asarray(ring.coords)) for ring in part.interiors]
        )
        outer = shapely.linearrings(np.asarray(part.exterior.coords))
        length = float(shapely.length(outer))
        if length < TAPER_RUN:
            continue
        stations = np.arange(0.0, length, TAPER_STEP)
        points = shapely.line_interpolate_point(outer, stations)
        thickness = shapely.distance(points, inner)
        in_band = (thickness >= TAPER_FROM) & (thickness <= TAPER_TO)
        # Der Ring ist geschlossen: Der Partner des letzten Punkts liegt
        # hinter dem Ringschluss, ``roll`` holt ihn von vorn.
        ahead = np.roll(thickness, -window)
        behind = np.roll(thickness, window)
        rises = (np.roll(in_band, -window) & (np.abs(ahead - thickness) >= TAPER_RISE)) | (
            np.roll(in_band, window) & (np.abs(behind - thickness) >= TAPER_RISE)
        )
        tapered = in_band & rises
        if not tapered.any():
            continue
        if tapered.all():
            total += length
            continue
        # Zusammenhängende Strecken zählen — auch die, die über den
        # Ringschluss hinweg zusammenhängen. Der Ring wird deshalb an einem
        # nicht keilförmigen Punkt aufgeschnitten.
        start = int(np.argmin(tapered))
        rolled = np.roll(tapered, -start)
        run = 0
        for flag in rolled:
            if flag:
                run += 1
                continue
            if run * TAPER_STEP >= TAPER_RUN:
                total += run * TAPER_STEP
            run = 0
        if run * TAPER_STEP >= TAPER_RUN:
            total += run * TAPER_STEP
    return float(total)


def tapered_layers(result: SliceResult) -> int:
    """Wie viele Schichten eine Keilstrecke tragen (:func:`taper_length`).

    Gemessen ist der Keil an jeder :data:`TAPER_SAMPLE`. Schicht, die
    dazwischen tragen den Wert der zuletzt gemessenen; die Zahl ist damit auf
    ``TAPER_SAMPLE`` Schichten genau, und wer sie liest, fragt nach Anteilen
    (``advise.TAPERED_LAYERS_SHARE``), nicht nach einzelnen Schichten.
    """
    return sum(1 for layer in result.layers if layer.taper_length > EPS_GEOM)


#: Wie weit eine Außenkontur an einer Stelle abknicken darf und noch als glatt
#: gilt, in Grad: 180° weniger ``scarf_angle_threshold`` der Orca-Familie
#: (155°), an dem sie ihre bedingte Schrägnaht festmacht. Knickt eine Schleife
#: stärker, hat die Naht dort eine Ecke, in der sie verschwindet.
SMOOTH_TURN_DEGREES: Final = 25.0


def smooth_outline_height(result: SliceResult, min_length: float, arm: float) -> float:
    """Über wie viel Höhe der Körper eine glatte Außenkontur trägt, in mm.

    Glatt heißt: kein Knick über :data:`SMOOTH_TURN_DEGREES`, also keine Ecke,
    in der ein Slicer die Naht verstecken kann. Gemessen wird der Knick wie im
    Slicer über Arme von ``arm`` Länge, der Düsenbreite: Zwischen benachbarten
    Facetten gemessen, galt der Rumpf von Roberts Minigolf-Satz mit seinen
    engen Rundungen als glatt, während ElegooSlicer dort Ecken von 45° sah und
    keine Schrägnaht setzte. Gezählt werden Umrisse, keine Löcher, und nur
    solche ab ``min_length`` Umfang; die Höhe ist die Zahl der Schichten mit so
    einem Umriss mal ihrem Abstand.
    """
    if not result.layers:
        return 0.0
    heights = [layer.z for layer in result.layers]
    spacing = float(np.median(np.diff(heights))) if len(heights) > 1 else heights[0]
    smooth = sum(
        1
        for layer in result.layers
        if any(_smooth_ring(contour.outline, min_length, arm) for contour in layer.contours)
    )
    return smooth * spacing


def _smooth_ring(ring: Ring, min_length: float, arm: float) -> bool:
    """Ob dieser Umriss lang genug ist und nirgends über Arme von ``arm``
    stärker abknickt als :data:`SMOOTH_TURN_DEGREES`
    (:func:`smooth_outline_height`)."""
    points = np.asarray(ring, dtype=float)
    if len(points) > 1 and np.allclose(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 3:
        return False
    closed = np.vstack([points, points[:1]])
    along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(closed, axis=0).T))])
    total = float(along[-1])
    if total < min_length:
        return False

    def at(distance: np.ndarray) -> np.ndarray:
        wrapped = np.mod(distance, total)
        return np.column_stack(
            [np.interp(wrapped, along, closed[:, 0]), np.interp(wrapped, along, closed[:, 1])]
        )

    behind = points - at(along[:-1] - arm)
    ahead = at(along[:-1] + arm) - points
    cross = behind[:, 0] * ahead[:, 1] - behind[:, 1] * ahead[:, 0]
    turn = np.degrees(np.abs(np.arctan2(cross, (behind * ahead).sum(axis=1))))
    return bool(turn.max() <= SMOOTH_TURN_DEGREES)


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


def narrow_share(layer: LayerInfo, width: float) -> float:
    """Welcher Anteil einer Schicht in Stegen liegt, die schmaler sind als ``width``.

    Die Schicht wird mit dem halben Maß geöffnet (erst geschrumpft, dann wieder
    gewachsen): Was dabei verschwindet, ist schmaler. Gemessen am 27.09.2026 für
    die erste Schicht bei sechs Bahnbreiten (3 mm): Roberts Minigolf-Platte trägt
    22 % darin, der Wedge-Lock 4 %, die Waschschüssel auf ihren Füßen 2 %.
    """
    shape = _layer_shape(layer)
    area = float(shape.area)
    if shape.is_empty or area <= 0.0 or width <= 0.0:
        return 0.0
    radius = width / 2.0
    opened = shape.buffer(-radius, quad_segs=4).buffer(radius, quad_segs=4)
    kept = float(shapely.intersection(opened, shape).area)
    return min(1.0, max(0.0, 1.0 - kept / area))


def _layer_shape(layer: LayerInfo) -> ShapelyPolygon:
    """Die Konturen einer Schicht wieder als GEOS-Fläche.

    Der Rückweg zu :func:`_to_polygons`: dieselbe Fläche, mit denselben
    Koordinaten, denn dort sind sie unverändert herausgeschrieben worden.
    """
    parts = [ShapelyPolygon(contour.outline, contour.holes) for contour in layer.contours]
    if not parts:
        return ShapelyPolygon()
    return parts[0] if len(parts) == 1 else unary_union(parts)
