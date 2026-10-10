"""Feine Schichten, wo das Modell feine Formen hat (RM-586).

Auf einer flachen Schräge legt jede Schicht eine Stufe, und ihre Breite ist
Schichthöhe durch Tangens der Neigung. Wird sie breiter als eine Bahn, sieht
man die Treppe: auf Kuppen, Schuppen, flachen Rücken. Senkrechte Wände haben
keine, ebene Deckflächen auch nicht. Hier wird gemessen, in welcher Höhe solche
Schrägen liegen, und daraus eine Höhenkurve für den Slicer gebaut — feine
Schichten nur dort, dazwischen die normale Höhe
(``konzepte/recherche-slicer-einstellungen-2026-10.md``, Nr. 9 und 10).

Jede Grenze folgt aus Schichthöhe und Bahnbreite des Drucks
(:func:`step_slope`, :func:`stepped_area_worth`, :func:`ramp`); die Bahn ist
die halbe Brückenbreite, mit der die Analyse schneidet
(``SliceResult.bridge_from``, zwei Bahnen).

Die Kurve hat die Form, die PrusaSlicer und die Orca-Familie in ihrer 3MF
führen (``layer_height_profile``): Paare aus Höhe über der Unterkante und
Schichthöhe, dazwischen linear, die erste Schicht fest, der letzte Punkt genau
auf der Oberkante — sonst verwirft der Slicer sie (``PrintObject::
update_layer_height_profile``). Cura nimmt keine Kurve, und seine Automatik
folgt dem flachsten Dreieck jeder Höhe; dorthin geht nichts
(``slicer_keys.NOT_TAKEN_BY``).

Alles in Millimetern; die Fläche eines schrägen Dreiecks wird genau auf die
Höhenbänder verteilt, die es schneidet (:func:`_spread`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Final

import numpy as np

from app.core.types import CancelToken, LayerInfo, PrintSettings, SliceResult
from app.core.units import EPS_GEOM

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData

#: Unter welcher Neigung eine Fläche eben ist, in Grad: Eine Deckfläche liegt
#: in einer Schicht und legt keine Treppe, auch wenn ihre Dreiecke aus einem
#: Float32-Netz um Tausendstel gekippt sind.
FLAT_SLOPE: Final = 1.0

#: Wie viele Stufen eine Schräge zeigen muss, damit man eine Treppe sieht: Eine
#: allein ist eine Kante (:func:`stepped_area_worth`).
STEPS_SEEN: Final = 2

#: Über wie viele normale Schichten die Höhe von normal zu fein wechselt.
#: PrusaSlicer und die Orca-Familie glätten ihre eigene Kurve über denselben
#: Radius (``HeightProfileSmoothingParams``, Vorgabe 5), statt zu springen.
RAMP_LAYERS: Final = 5

#: Die feine Schicht ist halb so hoch wie die normale ...
FINE_SHARE: Final = 0.5

#: ... aber nie unter einem Viertel der Düse: Darunter liegen die
#: Mindestschichthöhen der Maschinenprofile (Orca-Familie 0,08 mm, PrusaSlicer
#: 0,07 mm an der 0,4er Düse).
NOZZLE_SHARE: Final = 0.25

#: Ist die feine Schicht nicht wenigstens ein Viertel dünner als die normale,
#: lohnt der Wechsel nicht — die Stufe „Fein“ druckt schon fein genug.
WORTH_RATIO: Final = 0.75

#: Die Mindestdicke der Deckschichten, in mm (Recherche Nr. 10): Mit feinen
#: Schichten und fester Lagenzahl werden Deckflächen dünn und bekommen Löcher
#: oder Kissen. Cura führt 0,8 als Vorgabe, die Orca-Profile 0,6 bis 1,0.
TOP_SHELL_MINIMUM: Final = 0.8


def step_slope(layer_height: float, line: float) -> float:
    """Ab welcher Neigung gegen die Waagerechte eine Schräge keine sichtbare
    Stufe mehr legt, in Grad.

    Die Stufe ist ``h / tan(Neigung)`` breit. Ist sie breiter als eine Bahn,
    liegt auf jeder Stufe eine eigene Deckbahn, und man sieht die Treppe; bei
    0,2 mm Schicht und 0,42 mm Bahn unter 25,5°.
    """
    return math.degrees(math.atan2(layer_height, max(line, EPS_GEOM)))


def stepped_area_worth(layer_height: float, line: float) -> float:
    """Wie viel Schräge mit sichtbaren Stufen eine Höhe tragen muss, damit sie
    fein gedruckt wird, in mm² je mm Höhe.

    So viel trägt die kleinste Kuppe, auf der :data:`STEPS_SEEN`
    Stufen liegen: Eine Kugel vom Radius ``R`` hat je Millimeter Höhe ``2πR``
    Fläche, und ihr flacher Scheitel unter :func:`step_slope` ist
    ``R·(1 - cos Grenze)`` hoch. Zwei Stufen verlangen ``R = 2h / (1 - cos
    Grenze)`` — bei 0,2 mm Schicht 4,1 mm, also 26 mm² je mm. Was darunter
    bleibt, sind einzelne kleine Dreiecke, deren Stufe niemand sieht.
    """
    if layer_height <= EPS_GEOM:
        return math.inf
    rise = 1.0 - math.cos(math.radians(step_slope(layer_height, line)))
    return 2.0 * math.pi * STEPS_SEEN * layer_height / max(rise, EPS_GEOM)


def ramp(layer_height: float) -> float:
    """Wie lang der Übergang von normaler zu feiner Schicht ist, in mm
    (:data:`RAMP_LAYERS` normale Schichten).

    Dieselbe Länge trägt die Auswahl der Bereiche: Die Schrägfläche wird über
    sie gemittelt, ein kürzerer Bereich lohnt seine beiden Übergänge nicht, und
    eine kürzere Lücke als zwei Übergänge (hinaus und wieder hinein) wird
    mitgedruckt (:func:`fine_bands`).
    """
    return RAMP_LAYERS * layer_height


def fine_height(layer_height: float, nozzle: float) -> float | None:
    """Die feine Schichthöhe zu dieser normalen, oder ``None``, wo es keine
    lohnende gibt (:data:`FINE_SHARE`, :data:`NOZZLE_SHARE`, :data:`WORTH_RATIO`)."""
    if layer_height <= EPS_GEOM or nozzle <= EPS_GEOM:
        return None
    fine = max(FINE_SHARE * layer_height, NOZZLE_SHARE * nozzle)
    if fine > WORTH_RATIO * layer_height + EPS_GEOM:
        return None
    return round(fine, 3)


def stepped_areas(
    mesh: MeshData,
    edges: np.ndarray,
    layer_height: float,
    line: float,
    *,
    cancelled: CancelToken | None = None,
) -> np.ndarray:
    """Die Fläche aufwärts weisender Schrägen mit sichtbaren Stufen je Höhenband.

    ``edges`` sind die Grenzen der Bänder, aufsteigend; zurück kommt je Band
    ``[edges[i], edges[i + 1])`` die Fläche der Dreiecke zwischen
    :data:`FLAT_SLOPE` und :func:`step_slope`, genau auf die Bänder verteilt,
    die jedes schneidet. Nur aufwärts: Unter einer Unterseite steht die Stütze
    oder der Slicer legt eine Brücke, und feinere Schichten ändern daran nichts.
    """
    count = max(len(edges) - 1, 0)
    if count == 0 or mesh.triangle_count == 0:
        return np.zeros(count)
    raw = mesh.raw
    rising = np.asarray(raw.face_normals)[:, 2]
    chosen = np.flatnonzero(
        (rising > math.cos(math.radians(step_slope(layer_height, line))))
        & (rising <= math.cos(math.radians(FLAT_SLOPE)))
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not len(chosen):
        return np.zeros(count)
    corners = np.asarray(raw.vertices)[np.asarray(raw.faces)[chosen]]
    area = 0.5 * np.linalg.norm(
        np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1
    )
    heights = np.sort(corners[:, :, 2], axis=1)
    del corners
    return _spread(area, heights, np.asarray(edges, dtype=float), count)


def _spread(area: np.ndarray, heights: np.ndarray, edges: np.ndarray, count: int) -> np.ndarray:
    """Verteilt die Fläche jedes Dreiecks auf die Bänder, die es schneidet.

    Genau, nicht über die Mitte: Ein Kegel aus einem CAD-Export besteht aus
    Dreiecken vom Fuß bis zur Spitze, und über die Mitte läge seine ganze
    Mantelfläche auf einem Drittel der Höhe. Unter einer Ebene der Höhe ``t``
    liegt von einem Dreieck mit den Höhen ``z0 ≤ z1 ≤ z2`` der Anteil
    ``(t - z0)² / ((z2 - z0)(z1 - z0))`` bis ``z1`` und
    ``1 - (z2 - t)² / ((z2 - z0)(z2 - z1))`` darüber. Gebündelt je Schritt
    über die Bänder: Die Schleife läuft so oft, wie das höchste Dreieck Bänder
    schneidet, nicht je Dreieck.
    """
    low, middle, high = heights[:, 0], heights[:, 1], heights[:, 2]
    span = high - low
    below = span * (middle - low)
    above = span * (high - middle)

    def share(level: np.ndarray, pick: np.ndarray) -> np.ndarray:
        bottom, centre, top = low[pick], middle[pick], high[pick]
        level = np.clip(level, bottom, top)
        first = np.divide(
            (level - bottom) ** 2,
            below[pick],
            out=np.zeros(len(level)),
            where=below[pick] > 0.0,
        )
        second = 1.0 - np.divide(
            (top - level) ** 2,
            above[pick],
            out=np.zeros(len(level)),
            where=above[pick] > 0.0,
        )
        flat = span[pick] <= 0.0
        shares: np.ndarray = np.where(
            flat, (level >= top).astype(float), np.where(level <= centre, first, second)
        )
        return shares

    result = np.zeros(count)
    start = np.clip(np.searchsorted(edges, low, side="right") - 1, 0, count - 1)
    end = np.clip(np.searchsorted(edges, high, side="right") - 1, 0, count - 1)
    everyone = np.arange(len(area))
    done = share(np.full(len(area), edges[0]), everyone)
    for step in range(int((end - start).max(initial=0)) + 1):
        active = np.flatnonzero(start + step <= end)
        band = start[active] + step
        reached = share(edges[band + 1], active)
        np.add.at(result, band, area[active] * (reached - done[active]))
        done[active] = reached
    return result


def layer_bands(result: SliceResult, layer_height: float) -> tuple[tuple[float, float], ...]:
    """:func:`fine_bands` aus den Schichten einer Analyse, mit der Bahn, mit der
    sie geschnitten wurde (halbe ``bridge_from``). Leer ohne sie."""
    if result.bridge_from is None or not result.layers:
        return ()
    return fine_bands(
        [layer.z for layer in result.layers],
        [layer.stepped_area for layer in result.layers],
        layer_height,
        result.bridge_from / 2.0,
    )


def fine_bands(
    heights: Sequence[float] | np.ndarray,
    areas: Sequence[float] | np.ndarray,
    layer_height: float,
    line: float,
) -> tuple[tuple[float, float], ...]:
    """Die Höhenbereiche, die fein gedruckt werden sollen, in den Höhen der Schnitte.

    ``heights`` sind die Mitten der Schichten, aufsteigend, ``areas`` ihre
    Schrägfläche (:func:`stepped_areas`). Eine Schicht zählt, wo die
    Schrägfläche um sie herum, gemittelt über einen Übergang (:func:`ramp`),
    :func:`stepped_area_worth` erreicht; zusammenhängende Schichten werden ein
    Bereich, Lücken unter zwei Übergängen geschlossen, Bereiche kürzer als ein
    Übergang verworfen.
    """
    if not len(heights) or layer_height <= EPS_GEOM:
        return ()
    centres = np.asarray(heights, dtype=float)
    sloped = np.asarray(areas, dtype=float)
    if not np.any(sloped > 0.0):
        return ()
    window = ramp(layer_height)
    left = np.searchsorted(centres, centres - window / 2.0, side="left")
    right = np.searchsorted(centres, centres + window / 2.0, side="right")
    total = np.concatenate(([0.0], np.cumsum(sloped)))
    worth = (total[right] - total[left]) / window >= stepped_area_worth(layer_height, line)
    # Die Läufe zusammenhängender Schichten über ``worth`` als Feld, nicht je
    # Schicht: Anfang ist, wo es einschaltet, Ende, wo es ausschaltet.
    switches = np.diff(np.concatenate(([0], worth.astype(np.int8), [0])))
    starts = np.flatnonzero(switches == 1)
    ends = np.flatnonzero(switches == -1) - 1
    half = layer_height / 2.0
    bands: list[tuple[float, float]] = []
    for first, last in zip(starts, ends, strict=True):
        low, high = float(centres[first] - half), float(centres[last] + half)
        if bands and low - bands[-1][1] < 2.0 * window:
            bands[-1] = (bands[-1][0], high)
        else:
            bands.append((low, high))
    return tuple(band for band in bands if band[1] - band[0] >= window - EPS_GEOM)


def height_profile(
    bands: Sequence[tuple[float, float]],
    top: float,
    layer_height: float,
    fine: float,
    first_layer: float | None,
) -> tuple[float, ...]:
    """Die Höhenkurve des Slicers: ``z0, h0, z1, h1, …`` über der Unterkante.

    ``bands`` in Höhen über der Unterkante des Körpers, ``top`` seine Höhe.
    ``first_layer`` ist die feste erste Schicht; ``None`` heißt Raft, dann
    beginnt der Körper mit der normalen Schicht. Vor und nach jedem Bereich
    wechselt die Höhe über :func:`ramp`. Leer, wo kein Bereich bleibt — dann
    druckt der Slicer gleichmäßig.
    """
    start = first_layer if first_layer is not None else 0.0
    points: list[tuple[float, float]] = (
        [(0.0, first_layer), (first_layer, first_layer), (first_layer, layer_height)]
        if first_layer is not None
        else [(0.0, layer_height)]
    )
    transition = ramp(layer_height)
    used = False
    for band_low, band_high in bands:
        low = max(band_low, start)
        high = min(band_high, top)
        if high - low <= EPS_GEOM:
            continue
        used = True
        points.append((max(low - transition, points[-1][0]), layer_height))
        points.append((low, fine))
        points.append((high, fine))
        if high < top - EPS_GEOM:
            points.append((min(high + transition, top), layer_height))
    if not used:
        return ()
    if points[-1][0] < top - EPS_GEOM:
        points.append((top, layer_height))
    # Der letzte Punkt liegt genau auf der Oberkante, sonst verwerfen PrusaSlicer
    # und die Orca-Familie die Kurve (Toleranz 0,001 mm).
    points[-1] = (top, points[-1][1])
    flat: list[float] = []
    previous: tuple[float, float] | None = None
    for point in points:
        if (
            previous is not None
            and abs(point[0] - previous[0]) <= EPS_GEOM
            and abs(point[1] - previous[1]) <= EPS_GEOM
        ):
            continue
        flat += [point[0], point[1]]
        previous = point
    return tuple(flat)


def profile_for(
    mesh: MeshData,
    layer_height: float,
    fine: float,
    first_layer: float | None,
    line: float,
    *,
    cancelled: CancelToken | None = None,
) -> tuple[float, ...]:
    """Die Höhenkurve eines Körpers, so wie die Übergabe sie schreibt.

    Dasselbe Raster und dieselbe Bahn wie die Druckanalyse
    (``analysis.slice_body`` mit erster Schicht und ``bridge_from = 2·line``):
    die erste Schnittmitte auf halber erster Schicht, danach je eine normale
    Schicht — also dieselben Bereiche, deren Zeitanteil der Rat nennt, ohne
    den Körper noch einmal zu schneiden. Leer, wo nichts fein zu drucken ist
    oder ``fine`` nicht unter der normalen Höhe liegt.
    """
    if fine <= EPS_GEOM or fine >= layer_height - EPS_GEOM or mesh.triangle_count == 0:
        return ()
    bounds = mesh.bounds
    low, high = bounds.minimum[2], bounds.maximum[2]
    top = high - low
    first = first_layer if first_layer is not None else layer_height
    if top <= first + EPS_GEOM:
        return ()
    centres = np.concatenate(
        ([first / 2.0], np.arange(first + layer_height / 2.0, top, layer_height))
    )
    edges = np.concatenate(([0.0], (centres[1:] + centres[:-1]) / 2.0, [top + layer_height]))
    areas = stepped_areas(mesh, edges + low, layer_height, line, cancelled=cancelled)
    bands = fine_bands(centres, areas, layer_height, line)
    return height_profile(bands, top, layer_height, fine, first_layer)


def printed_layers(
    profile: Sequence[float], top: float, minimum: float
) -> list[tuple[float, float]]:
    """Die Schichten, die der Slicer aus der Kurve legt: ``(Unterkante, Höhe)``.

    Nachgebaut nach ``generate_object_layers`` von PrusaSlicer und der
    Orca-Familie: die Höhe am Schnitt eine halbe Mindestschicht über der
    Unterkante, linear zwischen den Punkten.
    """
    if len(profile) < 4:
        return []
    zs = profile[0::2]
    hs = profile[1::2]
    layers: list[tuple[float, float]] = []
    bottom = 0.0
    index = 0
    while True:
        probe = bottom + 0.5 * minimum
        if probe >= top:
            break
        while index + 1 < len(zs) and probe >= zs[index + 1]:
            index += 1
        height = hs[index]
        if index + 1 < len(zs) and zs[index + 1] - zs[index] > EPS_GEOM:
            share = (probe - zs[index]) / (zs[index + 1] - zs[index])
            height = hs[index] + (hs[index + 1] - hs[index]) * share
        if bottom + 0.5 * height >= top:
            break
        layers.append((bottom, height))
        bottom += height
    return layers


def _layer_seconds(layer: LayerInfo, settings: PrintSettings) -> float:
    """Eine grobe Druckzeit dieser Schicht: Wände und Füllung über ihr Tempo,
    gebremst wie im Slicer. Für den Anteil genügt das; die Druckzeit selbst
    rechnet der Slicer.

    **Mit Mindestschichtzeit, nie unter dem Mindesttempo**: Die feinen Schichten
    liegen meist an kleinen Querschnitten — der Kappe einer Kuppe —, und die
    druckt jeder Slicer nicht schneller als cooling.minimum_layer_time,
    bremst dafür aber nicht unter cooling.minimum_speed. Ohne die Bremse
    nannte der Rat an einer Halbkugel R 20 rund 4 %, ElegooSlicer druckte 7 %
    länger (ab Schicht 1); mit ihr nennt er 12 %, die Druckdatei zeigt ohne
    Beschleunigung 10 % (RM-586, Archiv)."""
    perimeter = 0.0
    for contour in layer.contours:
        for ring in (contour.outline, *contour.holes):
            if len(ring) > 1:
                perimeter += float(np.linalg.norm(np.diff(ring, axis=0), axis=1).sum())
    width = max(settings.layers.line_width, EPS_GEOM)
    walls = settings.shell.wall_count
    wall_seconds = 0.0
    if walls > 0:
        wall_seconds = perimeter / max(settings.speed.outer_wall, EPS_GEOM) + (
            (walls - 1) * perimeter / max(settings.speed.inner_wall, EPS_GEOM)
        )
    core = max(layer.area - walls * width * perimeter, 0.0)
    fill = core * settings.infill.density / width
    fill_seconds = fill / max(settings.speed.infill, EPS_GEOM)
    raw = wall_seconds + fill_seconds
    slowest = (walls * perimeter + fill) / max(settings.cooling.minimum_speed, EPS_GEOM)
    return max(raw, min(settings.cooling.minimum_layer_time, slowest))


def extra_time(
    layers: Sequence[LayerInfo],
    profile: Sequence[float],
    settings: PrintSettings,
    bottom: float,
) -> float:
    """Um welchen Anteil die Höhenkurve den Druck verlängert (0,2 heißt 20 %).

    Jede gedruckte Schicht kostet die Zeit der gemessenen Schicht, in deren
    Höhe sie liegt (:func:`_layer_seconds`); verglichen wird mit dem
    gleichmäßigen Raster der Analyse. ``bottom`` ist die Unterkante des
    Körpers in den Höhen der Schichten.
    """
    if not layers or len(profile) < 4:
        return 0.0
    seconds = np.array([_layer_seconds(layer, settings) for layer in layers])
    heights = np.array([layer.z for layer in layers], dtype=float) - bottom
    plain = float(seconds.sum())
    if plain <= EPS_GEOM:
        return 0.0
    closer, _middles = _nearest_layers(heights, profile)
    return max(float(seconds[closer].sum()) / plain - 1.0, 0.0)


def _nearest_layers(heights: np.ndarray, profile: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Je Schicht, die der Slicer aus der Kurve legt (:func:`printed_layers`),
    die gemessene Schicht, deren Mitte ihrer am nächsten liegt, und ihre Mitte.
    ``heights`` sind die Mitten der gemessenen Schichten über der Unterkante,
    aufsteigend."""
    top = float(profile[-2])
    printed = printed_layers(profile, top, min(profile[1::2]))
    middles = np.array([low + height / 2.0 for low, height in printed])
    nearest = np.clip(np.searchsorted(heights, middles), 0, len(heights) - 1)
    before = np.clip(nearest - 1, 0, len(heights) - 1)
    closer = np.where(
        np.abs(heights[before] - middles) < np.abs(heights[nearest] - middles), before, nearest
    )
    return closer, middles


def printed_tops(profile: Sequence[float]) -> list[float]:
    """Die Oberkanten der Schichten, die der Slicer aus der Kurve legt, über der
    Unterkante des Körpers — so zählt der G-Code seine Lagen."""
    if len(profile) < 4:
        return []
    layers = printed_layers(profile, float(profile[-2]), min(profile[1::2]))
    return [low + height for low, height in layers]


def printed_result(result: SliceResult, profile: Sequence[float], bottom: float) -> SliceResult:
    """Die Analyse so, wie der Slicer sie mit der Kurve druckt: je gedruckter
    Schicht die gemessene in ihrer Höhe, mit der Mitte der gedruckten
    (:func:`_nearest_layers`). Für die Druckzeit der Gegenprobe
    (``estimate.plate_comparison``); die Fläche jeder Schicht bleibt die
    gemessene. ``bottom`` ist die Unterkante des Körpers."""
    if not result.layers or len(profile) < 4:
        return result
    heights = np.array([layer.z for layer in result.layers], dtype=float) - bottom
    closer, middles = _nearest_layers(heights, profile)
    return replace(
        result,
        layers=tuple(
            replace(result.layers[int(index)], z=float(middle + bottom))
            for index, middle in zip(closer, middles, strict=True)
        ),
    )
