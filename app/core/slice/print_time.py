"""Druckzeit aus der Schichtanalyse — eine Schätzung mit Herkunft (§22.5, §28.2).

:mod:`app.core.slice.estimate` antwortet in Mikrosekunden aus Volumen und
Oberfläche und kennt keine Schicht. Für die **Gegenprobe nach dem Slicen**
reicht das nicht (RM-465): Gemessen an Würfel und Pilz in vier Slicern lag
sie 60 bis 80 Prozent unter der Druckdatei, weil ein kleines Teil fast nur
aus Mindestschichtzeit besteht und ein großes aus Beschleunigung.

Diese Rechnung nimmt deshalb die Schichten, die die Plattengegenprobe ohnehin
schneidet (:func:`app.core.slice.estimate.plate_comparison`), und rechnet je
Schicht, was jeder Slicer selbst rechnet, bevor er G-Code schreibt:

- **Wände** als versetzte Kontur, je Schleife mit Ecken: Das Ecktempo kommt
  aus der Junction-Deviation der Maschine, sonst aus dem Ruck; ein Vor- und ein
  Rückwärtslauf über die Ecken gibt jedem Stück sein Trapez.
- **Füllung**: Deck- und Bodenschalen an den ganzen Nachbarschichten, so
  viele, wie Schichtzahl und Mindestdicke des Profils verlangen; mit ganzen
  senkrechten Schalen (``ensure_vertical_shell_thickness``) auch dort voll, wo
  einer Schalenschicht die Füllfläche fehlt, geglättet wie in Orca. Brücke wo
  mehr als eine Bahnbreite über die Schicht darunter ragt, innere Brücke über
  dünner Füllung, dünne Füllung mit ihrer Dichte. Bahnbreite je Rolle aus dem
  Profil, Abstand nach ``Flow::spacing``. Die Bahnzahl folgt aus der mittleren
  Sehne ``π·A/U`` (Cauchy), jede Bahn ein Trapez zwischen zwei Ecken; die
  dünne Füllung verbindet ihre Enden am Rand (:data:`CONNECTION_SHARE`),
  schmale Vollfüllung läuft als Schleife (:func:`_narrow`).
- **Abbremsen**: Liegt die Schicht unter der Mindestschichtzeit, werden die
  Bahnen über Weg/Tempo gebremst, nie unter das **Mindestdrucktempo** der
  Einstellungen (``cooling.minimum_speed``: bei Prusa und der Orca-Familie aus dem
  Herstellerprofil, bei Cura Solidons Wert, den die Übergabe schreibt; nach einem
  übernommenen Vorschlag dessen Wert) —
  gemessen am SuperSlicer-Pilz: 7,03 s Stielschicht trotz 15 s Vorgabe. Die
  Beschleunigung kommt danach, bei den gebremsten Tempi, wie in den Slicern
  selbst.
- **Leerfahrt, Rückzug und Z-Hub** je Zugbeginn: je Insel einmal für ihre
  Wände, je Fläche und Stützstück einmal. Auch ein schräger Hub („Auto Lift“)
  kostet wie zwei senkrechte, weil die Z-Achse die Leerfahrt bremst (Minigolf
  und Seitenablage in ElegooSlicer: 0,24 bis 0,26 s je Anfahrt).
- **Stützen**: die Säulen unter dem ganzen Überstand je Schicht
  (:func:`_support_columns`), geschlossen wie im Slicer und ohne Krümel,
  darin das Muster mit der Dichte des Profils und seinen Verbindungen am Rand
  und die Kontaktschichten mit ihrer eigenen; ein Baum als Zug kurzer Stücke.
  Dieselben Säulen geben der Gegenprobe die Stützmenge
  (:func:`support_material`). Tempo, Beschleunigung und
  Art aus dem Herstellerprofil (:class:`Motion`). Die Mindestschichtzeit bremst
  und zählt sie nicht — gemessen am Pilz in fünf Slicern (04.10.2026): mit
  Abbremsen bis 28 % zu wenig, ohne höchstens 14 %.

Was sie nicht kennt: Haftungsränder, Lückenfüllung und ihre Anfahrten, die
genaue Reihenfolge der Bahnen, die Gestalt eines Baums (seine Menge folgt
keinem Umfang), Creality Prints Mindestschichtzeit, die Bögen nur mit ihrer
Sehne zählt, und welche Decke ein Profil ohne Brückenstützen als Brücke liest
(:func:`app.core.slice.estimate.plate_comparison`). Sie trägt
``source="internal"`` und wird mit der Zeit aus der Druckdatei verglichen, nie
vermischt (Regel 14). Ohne belegtes
Mindestdrucktempo gibt es keine :class:`Motion` und damit keine Zahl —
eine Mindestdauer, die niemand belegt, wird nicht behauptet.

**Sie ist eine Berichtsmessung und darf schnell rechnen** (``kern.md``):
Winkelfunktionen der Plattform (``math.tan`` in :func:`_support_columns`,
``np.arccos``, ``np.sin``, ``np.hypot``) und Clippers runde Versätze ändern
eine Zeit höchstens um ULP, weit unter den Schwellen 15 % und Faktor 2 der
Gegenprobe, und je Maschine bleibt sie bitgleich. Was über Absage oder
Ergebnis entscheidet, steht hier nicht; BLAS kommt trotzdem nicht vor.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

import manifold3d
import numpy as np
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.core.slice.analysis import _cross_shape, _material_cross
from app.core.types import CancelToken, PrintSettings, SliceResult
from app.core.units import EPS_GEOM


@dataclass(frozen=True, slots=True)
class Motion:
    """Was die Druckzeit bestimmt und nicht in den Druckeinstellungen steht.

    Gelesen aus dem Herstellerprofil des gewählten Slicers
    (:func:`app.core.export.manufacturer.base_settings`, :attr:`Foundation.motion`)
    oder aus der Cura-Druckerdefinition. ``None`` heißt: nicht belegt — dann
    gilt der nächstliegende Wert aus den Druckeinstellungen. Es gibt sie nur,
    wo das Profil ein Mindestdrucktempo nennt (RM-465); gerechnet wird mit
    ``cooling.minimum_speed`` der Einstellungen.
    """

    nozzle: float
    """Düsendurchmesser — die Bahnbreite einer Brücke."""
    first_layer_wall_speed: float | None = None
    first_layer_infill_speed: float | None = None
    solid_infill_speed: float | None = None
    internal_bridge_speed: float | None = None
    inner_wall_acceleration: float | None = None
    infill_acceleration: float | None = None
    solid_infill_acceleration: float | None = None
    top_surface_acceleration: float | None = None
    bridge_acceleration: float | None = None
    first_layer_acceleration: float | None = None
    travel_acceleration: float | None = None
    acceleration_limit: float | None = None
    """Höchste Beschleunigung beim Drucken, die die Maschine annimmt."""
    travel_acceleration_limit: float | None = None
    junction_deviation: float | None = None
    jerk: float | None = None
    z_speed: float | None = None
    z_acceleration: float | None = None
    retraction_speed: float | None = None
    deretraction_speed: float | None = None
    support_speed: float | None = None
    support_interface_speed: float | None = None
    support_acceleration: float | None = None
    support_interface_density: float | None = None
    """Bahnanteil der Kontaktschichten unter dem Überhang, aus dem Abstand des Profils."""
    support_tree: bool = False
    """Stützt das Herstellerprofil mit Bäumen, wenn Solidon „automatisch“ übergibt?"""
    support_hybrid: bool = False
    """Kennt der Slicer Hybridstützen (die Orca-Familie, RM-584)? Sonst geht
    ``hybrid`` als Gitter hinaus (``slicer_keys.NOT_OFFERED_BY_PROGRAM``)."""
    support_closing: float | None = None
    """Wie weit der Slicer benachbarte Stützflächen zusammenschließt, in mm
    (Prusa ``support_material_closing_radius``, Cura ``support_join_distance``,
    Orca fest 2 mm in ``SupportMaterial.cpp``); Bäume schließen nicht."""
    outer_wall_width: float | None = None
    """Bahnbreiten je Rolle aus dem Profil, in mm (Orca ``outer_wall_line_width``
    und Geschwister, Prusa ``external_perimeter_extrusion_width`` und
    Geschwister); ohne Wert die Bahnbreite der Einstellungen."""
    inner_wall_width: float | None = None
    sparse_width: float | None = None
    solid_width: float | None = None
    top_width: float | None = None
    flow_spacing: bool = False
    """Liegen nebeneinanderliegende Bahnen ``Breite - Höhe · (1 - π/4)`` auseinander
    (``Flow::spacing`` der Orca-Familie und PrusaSlicers) statt eine Breite?"""
    top_shell_thickness: float | None = None
    """Mindestdicke der Deckschalen in mm (Orca ``top_shell_thickness``, Prusa
    ``top_solid_min_thickness``): Reicht die Schichtzahl nicht, legt der Slicer
    Schichten zu."""
    bottom_shell_thickness: float | None = None
    vertical_shells: bool = False
    """Hält der Slicer die Schalendicke auch an schrägen Wänden
    (``ensure_vertical_shell_thickness`` ganz)? Dann wird voll gefüllt, wo die
    Füllfläche einer Nachbarschicht innerhalb der Schalenschichten fehlt."""
    minimum_sparse_area: float | None = None
    """Kleinere Flächen dünner Füllung füllt der Slicer voll, in mm²
    (Orca ``minimum_sparse_infill_area``, Prusa ``solid_infill_below_area``)."""
    narrow_solid_loops: bool = False
    """Füllt der Slicer schmale Vollfüllung in Schleifen entlang ihrer Form statt
    in kurzen Bahnen quer (Orca ``detect_narrow_internal_solid_infill``: schmaler
    als zwei Abstände nach innen; PrusaSlicer gemessen am Kegelstumpf)?"""
    sparse_pattern: str | None = None
    """Das Füllmuster des Slicers, wie er es nennt (``sparse_infill_pattern``,
    ``fill_pattern``) — es entscheidet, wie viel Verbindung am Rand entsteht
    (:data:`CONNECTION_SHARE`)."""


@dataclass(frozen=True, slots=True)
class _Roles:
    """Tempo und Beschleunigung je Bahnart, aus Einstellungen und Motion."""

    outer: float
    inner: float
    sparse: float
    solid: float
    top: float
    bridge: float
    internal_bridge: float
    first_wall: float
    first_infill: float
    travel: float
    a_default: float
    a_outer: float
    a_inner: float
    a_sparse: float
    a_solid: float
    a_top: float
    a_bridge: float
    a_first: float
    a_travel: float
    a_limit: float
    jd: float
    jerk: float
    z_speed: float
    z_accel: float
    retract: float
    retract_speed: float
    deretract_speed: float
    z_hop: float
    support: float
    support_interface: float
    a_support: float
    w_outer: float
    w_inner: float
    w_sparse: float
    w_solid: float
    w_top: float


def _roles(settings: PrintSettings, motion: Motion) -> _Roles:
    """Die eigene Wahl im Dialog gilt vor dem Herstellerwert derselben Rolle.

    Solidons Erstschichttempo schreibt beide Schlüssel der ersten Schicht, und
    seine Füllung bremst die innere Vollfüllung mit (``handover``): Ist eines
    davon gewählt, gilt es; sonst gelten die getrennten Herstellerwerte.
    """
    speed = settings.speed
    chosen = settings.explicit
    first_wall = motion.first_layer_wall_speed or speed.first_layer
    first_infill = motion.first_layer_infill_speed or speed.first_layer
    if "speed.first_layer" in chosen:
        first_wall = first_infill = speed.first_layer
    solid = motion.solid_infill_speed or speed.infill
    if "speed.infill" in chosen:
        solid = min(solid, speed.infill)
    default = speed.acceleration

    def accel(value: float | None) -> float:
        return value if value is not None and value > 0.0 else default

    limit = motion.acceleration_limit or math.inf
    travel_accel = accel(motion.travel_acceleration)
    if motion.travel_acceleration_limit:
        travel_accel = min(travel_accel, motion.travel_acceleration_limit)
    retract = settings.retraction
    # Eine gewählte Bahnbreite schreibt Solidon jeder Rolle (``slicer_keys``);
    # sonst fährt jede Rolle die Breite des Herstellerprofils.
    width = settings.layers.line_width
    own_width = "layers.line_width" in chosen

    def wide(value: float | None) -> float:
        return width if own_width or value is None or value <= 0.0 else value

    return _Roles(
        outer=speed.outer_wall,
        inner=speed.inner_wall,
        sparse=speed.infill,
        solid=solid,
        top=speed.top_surface,
        bridge=speed.bridge,
        internal_bridge=motion.internal_bridge_speed or speed.bridge,
        first_wall=first_wall,
        first_infill=first_infill,
        travel=speed.travel,
        a_default=default,
        a_outer=speed.outer_wall_acceleration or default,
        a_inner=accel(motion.inner_wall_acceleration),
        a_sparse=accel(motion.infill_acceleration),
        a_solid=accel(motion.solid_infill_acceleration or motion.infill_acceleration),
        a_top=accel(motion.top_surface_acceleration),
        a_bridge=accel(motion.bridge_acceleration),
        a_first=accel(motion.first_layer_acceleration),
        a_travel=travel_accel,
        a_limit=limit,
        jd=motion.junction_deviation or 0.0,
        jerk=motion.jerk or 0.0,
        z_speed=motion.z_speed or speed.travel,
        z_accel=motion.z_acceleration or default,
        retract=max(retract.length, 0.0),
        retract_speed=motion.retraction_speed or retract.speed,
        deretract_speed=motion.deretraction_speed or motion.retraction_speed or retract.speed,
        z_hop=max(retract.z_hop, 0.0),
        # Ohne Herstellerwert das Tempo, das Solidon Cura als ``speed_print``
        # schreibt (``slicer_keys``); dort folgt ``speed_support`` ihm, und die
        # Kontaktschichten laufen mit zwei Dritteln (``fdmprinter``).
        support=motion.support_speed or speed.inner_wall,
        support_interface=motion.support_interface_speed
        or (motion.support_speed or speed.inner_wall) / 1.5,
        a_support=accel(motion.support_acceleration),
        w_outer=wide(motion.outer_wall_width),
        w_inner=wide(motion.inner_wall_width),
        w_sparse=wide(motion.sparse_width),
        w_solid=wide(motion.solid_width),
        w_top=wide(motion.top_width),
    )


def spacing(width: float, height: float, motion: Motion) -> float:
    """Wie weit zwei Nachbarbahnen auseinanderliegen: in der Orca-Familie und
    bei PrusaSlicer ``Breite - Höhe · (1 - π/4)`` (``Flow::spacing``: ein
    Rechteck mit halbrunden Seiten), sonst die Breite (Cura)."""
    if motion.flow_spacing:
        narrower = width - height * (1.0 - math.pi / 4.0)
        if narrower > 0.0:
            return narrower
    return width


def shell_layers(layers: int, thickness: float | None, height: float) -> int:
    """Wie viele Schalenschichten der Slicer legt: die Zahl, mindestens aber so
    viele, dass die Mindestdicke erreicht ist (Orca ``discover_vertical_shells``:
    weiter, solange der Abstand unter der Dicke liegt). Ohne Schicht keine Schale."""
    if layers <= 0 or thickness is None or thickness <= 0.0 or height <= 0.0:
        return max(layers, 0)
    return max(layers, math.ceil(thickness / height - EPS_GEOM))


def trapezoid(
    length: float, speed: float, acceleration: float, entry: float = 0.0, exit_: float = 0.0
) -> float:
    """Zeit über ein Stück mit Anfangs- und Endtempo: Trapez oder Dreieck."""
    if length <= 0.0 or speed <= 0.0:
        return 0.0
    if acceleration <= 0.0 or not math.isfinite(acceleration):
        return length / speed
    entry = min(entry, speed)
    exit_ = min(exit_, speed)
    rise = (speed * speed - entry * entry) / (2.0 * acceleration)
    fall = (speed * speed - exit_ * exit_) / (2.0 * acceleration)
    if rise + fall <= length:
        return (
            (speed - entry) / acceleration
            + (speed - exit_) / acceleration
            + (length - rise - fall) / speed
        )
    peak = math.sqrt(max((2.0 * acceleration * length + entry * entry + exit_ * exit_) / 2.0, 0.0))
    return max(peak - entry, 0.0) / acceleration + max(peak - exit_, 0.0) / acceleration


def corner_speed(speed: float, acceleration: float, turn: float, roles: _Roles) -> float:
    """Das Tempo durch eine Ecke um ``turn`` (Bogenmaß).

    Mit Junction-Deviation ``v² = a·δ·sin(θ/2)/(1 - sin(θ/2))`` am Innenwinkel
    ``θ = π - turn`` (Marlin, Klipper); sonst der Ruck als größter Sprung.
    Ohne beides hält die Maschine an jeder Ecke.
    """
    if turn < 1e-9:
        return speed
    if roles.jd > 0.0:
        half = math.sin((math.pi - turn) / 2.0)
        if half >= 1.0 - 1e-12:
            return speed
        return min(speed, math.sqrt(acceleration * roles.jd * half / (1.0 - half)))
    if roles.jerk > 0.0:
        return min(speed, roles.jerk / max(2.0 * math.sin(turn / 2.0), 1e-9))
    return 0.0


@dataclass(slots=True)
class _Loop:
    lengths: np.ndarray
    turns: np.ndarray
    speed: float
    acceleration: float
    overhang: float = 0.0
    length: float = 0.0


@dataclass(slots=True)
class _Lines:
    count: int
    length: float
    speed: float
    acceleration: float
    turn: float = math.pi / 2.0
    """Der Knick zwischen zwei Bahnen: neunzig Grad im Zickzack, wenig im Baum."""


@dataclass(slots=True)
class _Layer:
    loops: list[_Loop] = field(default_factory=list)
    lines: list[_Lines] = field(default_factory=list)
    support: list[_Lines] = field(default_factory=list)
    """Stützbahnen: Sie laufen mit, aber die Mindestschichtzeit bremst sie nicht
    und zählt sie nicht (:func:`_layer_seconds`)."""
    starts: int = 0
    travel: float = 0.0
    steps: int = 0
    """Kurze Fahrten ohne Rückzug, von Schleife zu Schleife einer Insel."""
    step: float = 0.0
    """Ihre Länge: eine Bahnbreite."""


def _segments(ring: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = ring[:-1] if len(ring) > 1 and np.allclose(ring[0], ring[-1]) else ring
    step = np.roll(points, -1, axis=0) - points
    lengths = np.hypot(step[:, 0], step[:, 1])
    keep = lengths > 1e-6
    step, lengths = step[keep], lengths[keep]
    if len(lengths) == 0:
        return lengths, lengths
    direction = step / lengths[:, None]
    following = np.roll(direction, -1, axis=0)
    cosines = np.clip(
        direction[:, 0] * following[:, 0] + direction[:, 1] * following[:, 1], -1.0, 1.0
    )
    return lengths, np.arccos(cosines)


def _capped(speed: float, width: float, height: float, flow: float) -> float:
    if flow > 0.0 and width * height * speed > flow:
        return flow / (width * height)
    return speed


_Cross = manifold3d.CrossSection
_EMPTY: Final = manifold3d.CrossSection()

#: Gehrungsgrenze der Versätze, wie GEOS sie für ``join_style=mitre`` nimmt:
#: Spitze Ecken bleiben bis zum Fünffachen des Versatzes spitz.
MITRE_LIMIT: Final = 5.0


def _inset(section: manifold3d.CrossSection, distance: float) -> manifold3d.CrossSection:
    """Um ``distance`` nach außen (positiv) oder innen (negativ), mit Gehrung."""
    if distance == 0.0 or section.is_empty():
        return section
    return section.offset(distance, manifold3d.JoinType.Miter, MITRE_LIMIT)


def _rounded(section: manifold3d.CrossSection, distance: float) -> manifold3d.CrossSection:
    if distance == 0.0 or section.is_empty():
        return section
    return section.offset(distance, manifold3d.JoinType.Round)


def _shape(section: manifold3d.CrossSection) -> tuple[float, float, int]:
    """Fläche, Umfang aller Ringe und Zahl der Stücke (Hüllen) eines Querschnitts."""
    if section.is_empty():
        return 0.0, 0.0, 0
    boundary = 0.0
    pieces = 0
    for ring in section.to_polygons():
        points = np.asarray(ring, dtype=float)
        if len(points) < 3:
            continue
        step = np.roll(points, -1, axis=0) - points
        boundary += float(np.hypot(step[:, 0], step[:, 1]).sum())
        signed = float((points[:, 0] * np.roll(points[:, 1], -1)).sum())
        signed -= float((points[:, 1] * np.roll(points[:, 0], -1)).sum())
        pieces += signed > 0.0
    return float(section.area()), boundary, pieces


def _materials(result: SliceResult) -> list[manifold3d.CrossSection]:
    """Das Material jeder Schicht als gerichteter Clipper-Querschnitt.

    Die Flächenrechnung je Schicht läuft in Clipper, nicht in GEOS: An der
    Waschschüssel kosteten Differenz, Versatz und Schnitt in GEOS 45 von 50 s
    der Zeitgegenprobe (06.10.2026, cProfile)."""
    crosses: list[manifold3d.CrossSection] = []
    for info in result.layers:
        shapes = [ShapelyPolygon(contour.outline, list(contour.holes)) for contour in info.contours]
        crosses.append(_material_cross(unary_union(shapes).buffer(0)) if shapes else _EMPTY)
    return crosses


def _columns_of(
    result: SliceResult,
    settings: PrintSettings,
    motion: Motion,
    cancelled: CancelToken | None,
) -> tuple[list[manifold3d.CrossSection], list[manifold3d.CrossSection]]:
    """Material und Stützsäulen je Schicht, gemerkt je Messung.

    Die Plattengegenprobe fragt sie zweimal, für die Druckzeit und für die
    Stützmenge (:func:`support_material`); am Arbeitsplattenreiniger kostete
    die zweite Rechnung 7 s. Gemerkt wird wie in
    :func:`app.core.slice.analysis.model_support` am Schichttupel selbst
    (Identität) und an allem, was die Säulen bestimmt, für die letzten
    :data:`_COLUMNS_KEPT` Fragen."""
    key = (
        settings.support,
        settings.layers.line_width,
        motion.support_tree,
        motion.support_hybrid,
        motion.support_closing,
    )
    with _COLUMNS_LOCK:
        for layers, known, materials, columns in _COLUMNS:
            if layers is result.layers and known == key:
                return materials, columns
    materials = _materials(result)
    columns = _support_columns(result, materials, settings, motion, cancelled)
    with _COLUMNS_LOCK:
        _COLUMNS.append((result.layers, key, materials, columns))
        del _COLUMNS[:-_COLUMNS_KEPT]
    return materials, columns


#: Wie viele Messungen :func:`_columns_of` behält — die Platte, die gerade
#: gegengeprüft wird. Ihre Schichttupel bleiben dafür am Leben.
_COLUMNS_KEPT: Final = 2
_COLUMNS: list[
    tuple[
        tuple[object, ...],
        tuple[object, ...],
        list[manifold3d.CrossSection],
        list[manifold3d.CrossSection],
    ]
] = []
_COLUMNS_LOCK = threading.Lock()


def _layers(
    result: SliceResult,
    settings: PrintSettings,
    roles: _Roles,
    motion: Motion,
    cancelled: CancelToken | None,
) -> list[_Layer]:
    """Die Bahnen jeder Schicht dieses Körpers, noch ohne Zeit."""
    materials, columns = _columns_of(result, settings, motion, cancelled)
    kept = [index for index, info in enumerate(result.layers) if info.area > 1e-6]
    regions = [materials[index] for index in kept]
    supports = [columns[index] for index in kept]
    layers = settings.layers
    shell = settings.shell
    width = layers.line_width
    first_width = layers.first_layer_line_width or width
    walls = shell.wall_count
    flow = settings.filament.max_flow
    count = len(regions)
    height = layers.layer_height
    tops = shell_layers(shell.top_layers, motion.top_shell_thickness, height)
    bottoms = shell_layers(shell.bottom_layers, motion.bottom_shell_thickness, height)
    shelled = (
        walls * first_width,
        roles.w_outer + (walls - 1) * roles.w_inner if walls > 0 else 0.0,
    )
    interiors = [
        _inset(region, -shelled[0 if index == 0 else 1]) for index, region in enumerate(regions)
    ]
    share = connection_share(settings, motion)
    solid_gap = spacing(roles.w_solid, height, motion)
    built: list[_Layer] = []
    sparse_below = _EMPTY
    for index, region in enumerate(regions):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first = index == 0
        height = layers.first_layer_height if first else layers.layer_height
        # Was mehr als eine Bahnbreite über die Schicht darunter hinausragt und
        # breiter als zwei Bahnen ist, trägt nichts: Brücke und Überhangwand.
        unsupported = (
            _rounded(_rounded(region - _rounded(regions[index - 1], width), -width), width)
            if index > 0
            else _EMPTY
        )
        hanging = None if unsupported.is_empty() else _cross_shape(unsupported)
        layer = _Layer()
        for loop in range(walls):
            if first:
                line, middle = first_width, (loop + 0.5) * first_width
                speed, accel = roles.first_wall, roles.a_first
            elif loop == 0:
                line, middle = roles.w_outer, 0.5 * roles.w_outer
                speed, accel = roles.outer, roles.a_outer
            else:
                line, middle = roles.w_inner, roles.w_outer + (loop - 0.5) * roles.w_inner
                speed, accel = roles.inner, roles.a_inner
            speed = _capped(speed, line, height, flow)
            for ring in _inset(region, -middle).to_polygons():
                points = np.asarray(ring, dtype=float)
                if len(points) < 3:
                    continue
                lengths, turns = _segments(points)
                over = 0.0
                if hanging is not None:
                    over = LineString(np.vstack([points, points[:1]])).intersection(hanging).length
                layer.loops.append(
                    _Loop(
                        lengths,
                        turns,
                        speed,
                        min(accel, roles.a_limit),
                        over,
                        float(lengths.sum()),
                    )
                )
                # Die nächste Schleife derselben Insel liegt eine Bahn daneben:
                # unter ``retraction_minimum_travel``, ohne Rückzug und Hub,
                # aber eine kurze Fahrt mit ihrer Beschleunigung.
                if loop == 0:
                    layer.starts += 1
                else:
                    layer.steps += 1
                    layer.step = max(layer.step, line)
        inside = interiors[index]
        parts: list[tuple[manifold3d.CrossSection, float, float, float, float, float, float]] = []
        if not inside.is_empty():
            below = range(index - 1, index - 1 - bottoms, -1)
            above = range(index + 1, index + 1 + tops)
            if index - bottoms < 0 or index + tops >= count:
                # Eine Nachbarschicht der Schale fehlt: Hier ist alles Schale.
                covered = _EMPTY
            else:
                neighbours = [inside, *(regions[other] for other in (*above, *below))]
                if motion.vertical_shells:
                    # ``ensure_vertical_shell_thickness``: dünn gefüllt wird nur,
                    # was auch in den Schalenschichten darüber und darunter
                    # Füllfläche ist — an einer schrägen Wand liegt dort deren Wand.
                    neighbours += [
                        interiors[other]
                        for other in (
                            *range(index + 1, index + tops),
                            *range(index - 1, index - bottoms, -1),
                        )
                    ]
                covered = _Cross.batch_boolean(neighbours, manifold3d.OpType.Intersect)
            if motion.vertical_shells and not covered.is_empty():
                covered = _regular_sparse(inside, covered, solid_gap)
            covered = _without_small_sparse(covered, motion.minimum_sparse_area)
            if shell.top_layers <= 0:
                top = _EMPTY
            else:
                top = inside - regions[index + 1] if index + 1 < count else inside
            internal = inside - covered - top
            if first:
                # Ohne Bodenschicht ist auch die erste Schicht dünne Füllung.
                density = 1.0 if shell.bottom_layers > 0 else settings.infill.density
                parts.append(
                    (
                        inside,
                        first_width,
                        spacing(first_width, height, motion),
                        density,
                        roles.first_infill,
                        roles.a_first,
                        0.0,
                    )
                )
            else:
                bridge = inside ^ unsupported
                nozzle = motion.nozzle
                if not bridge.is_empty():
                    top = top - bridge
                    internal = internal - bridge
                    parts.append((bridge, nozzle, nozzle, 1.0, roles.bridge, roles.a_bridge, 0.0))
                # Die erste volle Schicht über dünner Füllung ist eine innere Brücke.
                if not sparse_below.is_empty():
                    inner = _rounded(_rounded((internal + top) ^ sparse_below, -width), width)
                    if not inner.is_empty():
                        internal = internal - inner
                        top = top - inner
                        parts.append(
                            (
                                inner,
                                nozzle,
                                nozzle,
                                1.0,
                                roles.internal_bridge,
                                roles.a_bridge,
                                0.0,
                            )
                        )
                top_width = roles.w_top
                parts.append(
                    (
                        top,
                        top_width,
                        spacing(top_width, height, motion),
                        1.0,
                        roles.top,
                        roles.a_top,
                        0.0,
                    )
                )
                if motion.narrow_solid_loops and not internal.is_empty():
                    narrow = _narrow(internal, solid_gap)
                    if not narrow.is_empty():
                        internal = internal - narrow
                        _narrow_loops(layer, narrow, roles, solid_gap, height, flow)
                parts.append(
                    (internal, roles.w_solid, solid_gap, 1.0, roles.solid, roles.a_solid, 0.0)
                )
                parts.append(
                    (
                        covered,
                        roles.w_sparse,
                        spacing(roles.w_sparse, height, motion),
                        settings.infill.density,
                        roles.sparse,
                        roles.a_sparse,
                        share,
                    )
                )
            sparse_below = covered
        else:
            sparse_below = _EMPTY
        for area, line, gap, density, speed, accel, joined in parts:
            if density <= 0.0:
                continue
            surface, boundary, pieces = _shape(area)
            if surface <= 1e-6:
                continue
            speed = _capped(speed, line, height, flow)
            accel = min(accel, roles.a_limit)
            path = surface * density / gap
            chord = max(math.pi * surface / boundary, gap) if boundary > 0.0 else gap
            number = max(1, round(path / chord))
            layer.lines.append(_Lines(number, path / number, speed, accel))
            if joined > 0.0 and boundary > 0.0:
                # Die Verbindungen am Rand: je Bahn ein kurzes Stück entlang der
                # Wand, zusammen der gemessene Anteil des Umfangs.
                layer.lines.append(_Lines(number, joined * boundary / number, speed, accel))
            layer.starts += pieces
        if not supports[index].is_empty():
            _support_lines(layer, supports, index, settings, roles, motion, height)
        area = region.area()
        layer.travel = math.sqrt(area) / 2.0 if area > 0.0 else 0.0
        built.append(layer)
    return built


def _core(area: manifold3d.CrossSection, gap: float) -> manifold3d.CrossSection:
    """Der Kern einer Vollfüllung, der in Bahnen quer gefüllt wird: geöffnet um
    zwei Abstände und um drei zurück, auf die Fläche begrenzt (Orca
    ``split_solid_surface``)."""
    return area ^ _inset(_inset(area, -2.0 * gap), 3.0 * gap)


def _narrow(internal: manifold3d.CrossSection, gap: float) -> manifold3d.CrossSection:
    """Was von einer Vollfüllung schmal ist und als Schleife läuft. Splitter
    schmaler als eine Bahn gehen zurück in die Bahnen quer (Orca: „Merge very
    small areas that is smaller than a single line width to the normal
    infill“); sonst zählte jeder Eckensplitter als eigene Anfahrt."""
    rest = internal - _core(internal, gap)
    if rest.is_empty():
        return rest
    loops = [piece for piece in rest.decompose() if not _inset(piece, -0.5 * gap).is_empty()]
    return _Cross.batch_boolean(loops, manifold3d.OpType.Add) if loops else _EMPTY


def _narrow_loops(
    layer: _Layer,
    narrow: manifold3d.CrossSection,
    roles: _Roles,
    gap: float,
    height: float,
    flow: float,
) -> None:
    """Schmale Vollfüllung als Schleifen entlang ihrer Form: der Weg Fläche
    durch Abstand, je Schleife etwa der halbe Umfang, ohne Ecken dazwischen."""
    surface, boundary, pieces = _shape(narrow)
    if surface <= EPS_GEOM:
        return
    path = surface / gap
    reach = max(boundary / 2.0, gap)
    number = max(pieces, round(path / reach), 1)
    speed = _capped(roles.solid, roles.w_solid, height, flow)
    accel = min(roles.a_solid, roles.a_limit)
    layer.lines.append(_Lines(number, path / number, speed, accel, math.pi))
    layer.starts += pieces


def _regular_sparse(
    inside: manifold3d.CrossSection, covered: manifold3d.CrossSection, gap: float
) -> manifold3d.CrossSection:
    """Was nach der Glättung der Vollfüllung dünn bleibt (Orca
    ``discover_vertical_shells``): Vollfüllung schmaler als 0,65 Abstände
    entfällt, Lücken der dünnen Füllung unter 1,2 Abständen werden voll, und die
    Vollfüllung greift 0,2 Abstände in die dünne — je mit 1,05 Abständen.
    Stücke unter 1,5 mm mal diesem Abstand verwirft Orca als Tropfen an glatten
    Flächen; am Rand des Arbeitsplattenreinigers waren es 500 je Schicht."""
    reach = 1.05 * gap
    narrow, closing, overlap = 0.5 * 0.65 * reach, 0.5 * 1.2 * reach, 0.2 * reach
    solid = inside - covered
    if solid.is_empty():
        return covered
    solid = _inset(_inset(_inset(solid, -narrow), narrow + closing), -(closing - overlap))
    drops = solid.decompose()
    kept = [piece for piece in drops if piece.area() >= 1.5 * reach]
    if len(kept) < len(drops):
        solid = _Cross.batch_boolean(kept, manifold3d.OpType.Add) if kept else _EMPTY
    return inside - solid


def _without_small_sparse(
    covered: manifold3d.CrossSection, smallest: float | None
) -> manifold3d.CrossSection:
    """Kleine Flächen dünner Füllung füllt der Slicer voll."""
    if smallest is None or smallest <= 0.0 or covered.is_empty():
        return covered
    parts = covered.decompose()
    kept = [part for part in parts if part.area() >= smallest]
    if len(kept) == len(parts):
        return covered
    return _Cross.batch_boolean(kept, manifold3d.OpType.Add) if kept else _EMPTY


#: Welcher Anteil des Umfangs der dünnen Füllung als Verbindung zwischen zwei
#: Bahnen entlang der Wand gedruckt wird, je Füllmuster des Slicers (Orca
#: ``connect_infill``: Bahnenden werden am Rand verbunden, sonst verankert).
#: Gemessen an Quader, Zylinder, Kegelstumpf, Kegel und Seitenablage
#: (06.10.2026; Bahnlänge der Druckdatei minus Fläche mal Dichte durch Abstand,
#: geteilt durch den Umfang der dünnen Füllung): Zickzack in ElegooSlicer 0,33
#: bis 0,44, Gitter in Bambu Studio, Creality Print und PrusaSlicer 0,23 bis
#: 0,42, Kreuzschraffur in OrcaSlicer 0,21 bis 0,38 — eingetragen je das
#: Mittel. Ein Muster ohne Messung bekommt keine Verbindung.
CONNECTION_SHARE: Final[dict[str, float]] = {
    "rectilinear": 0.40,
    "zig-zag": 0.40,
    "grid": 0.33,
    "crosshatch": 0.30,
}


def connection_share(settings: PrintSettings, motion: Motion) -> float:
    """Der Verbindungsanteil des Musters, das gedruckt wird.

    Cura verbindet seine Füllbahnen nur mit ``zig_zaggify_infill``, das
    Solidon nicht schreibt; dort bleibt es bei keiner Verbindung.
    """
    if not motion.flow_spacing:
        return 0.0
    pattern = motion.sparse_pattern
    if "infill.pattern" in settings.explicit or pattern is None:
        pattern = _WRITTEN_PATTERN.get(settings.infill.pattern)
    return CONNECTION_SHARE.get(pattern or "", 0.0)


#: Was Solidons Füllmuster im Slicer heißt, wenn Solidon es schreibt
#: (``slicer_keys``): Linien als Zickzack, das Gitter als Gitter.
_WRITTEN_PATTERN: Final[dict[str, str]] = {"lines": "rectilinear", "grid": "grid"}


#: Ein Baum ist ein Zug aus kurzen Stücken: Die Orca-Familie schreibt seine
#: Äste als Vieleck, im Mittel 0,38 bis 0,41 mm je Stück (Pilz und
#: Waschschüssel, ElegooSlicer und Bambu Studio, 04.10.2026).
TREE_SEGMENT: Final = 0.4

#: Der Knick zwischen zwei Stücken eines Astes. Gemessen an denselben Läufen:
#: Mit diesem Winkel trifft das Ecktempo aus dem Ruck der Maschine das, was
#: die Slicer für ihre Bäume rechnen (rund 35 mm/s im Mittel).
TREE_TURN: Final = 0.25


#: Wie genau die Säulen ihren Umriss behalten, in mm: ein Hundertstel der
#: Düse; sonst sammeln sie über hunderte Schichten Ecken (Waschschüssel).
SUPPORT_SIMPLIFY: Final = 0.005


def _support_columns(
    result: SliceResult,
    materials: Sequence[manifold3d.CrossSection],
    settings: PrintSettings,
    motion: Motion,
    cancelled: CancelToken | None,
) -> list[manifold3d.CrossSection]:
    """Der Raum, den die Stützen je Schicht füllen — von oben nach unten.

    Jedes Überhangstück steigt ab, bis es auf Material trifft: „überall“ setzt
    dort auf und trägt den Rest weiter, „nur vom Bett“ verwirft eine Säule,
    sobald sie Material berührt. Gefüllt wird mit dem seitlichen Abstand zum
    Modell (``support.xy_gap``), wie die Slicer ihn halten. Gerechnet wird in
    Clipper, nicht in GEOS: An der Waschschüssel (575 Schichten, 401
    Überhangstücke) kosteten Vereinigung, Differenz und das Zurückwandeln in
    GEOS-Flächen 27 s.

    **Ein Muster schließt seine Flächen**, bevor es sie füllt: Wo eine
    gewölbte Wand je Schicht nur einen Streifen überhängen lässt (Waschschüssel,
    Arbeitsplattenreiniger aus dem Korpus), legt der Slicer keine hundert
    Splitter an, sondern eine Fläche — ohne das rechnete die Gegenprobe am
    Reiniger 695 statt 73 Minuten Stütze, fast alles Anfahrten.
    """
    tree = uses_tree_supports(settings, motion)
    closing = 0.0 if tree else max(motion.support_closing or 0.0, 0.0)
    count = len(materials)
    columns = [manifold3d.CrossSection() for _ in range(count)]
    if settings.support.style == "none" or count < 2:
        return columns
    only_bed = settings.support.placement == "build_plate"
    gap = max(settings.support.xy_gap, 0.0)
    slope = math.tan(math.radians(settings.support.threshold_angle))
    carried = manifold3d.CrossSection()
    above: manifold3d.CrossSection | None = None
    for index in range(count - 1, 0, -1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        material = materials[index - 1]
        pieces = result.layers[index].overhangs
        if pieces:
            hanging = manifold3d.CrossSection.batch_boolean(
                [_material_cross(ShapelyPolygon(p.outline, list(p.holes))) for p in pieces],
                manifold3d.OpType.Add,
            )
            if above is None:
                above = materials[index]
            # Der ganze Überstand über die Schicht darunter, nicht nur der Teil
            # jenseits der zulässigen Überhangweite (Orca, Prusa
            # ``detect_overhangs``: „Offset the support regions back to a full
            # overhang … to increase size of the supporting columns below“).
            # Ohne das blieb an gewölbten Flächen je Schicht ein Splitter.
            reach = (result.layers[index].z - result.layers[index - 1].z) * slope
            if reach > 0.0:
                hanging = (hanging.offset(reach, manifold3d.JoinType.Miter) ^ above) - material
            carried = carried + hanging
        above = material
        if carried.is_empty():
            continue
        if closing > 0.0:
            carried = carried.offset(closing, manifold3d.JoinType.Miter).offset(
                -closing, manifold3d.JoinType.Miter
            )
        carried = carried.simplify(SUPPORT_SIMPLIFY)
        if material.is_empty():
            columns[index - 1] = carried
            continue
        if only_bed:
            free = [part for part in carried.decompose() if (part ^ material).is_empty()]
            carried = (
                manifold3d.CrossSection.batch_boolean(free, manifold3d.OpType.Add)
                if free
                else manifold3d.CrossSection()
            )
        else:
            carried = carried - material
        if carried.is_empty():
            continue
        filled = carried - material.offset(gap, manifold3d.JoinType.Miter) if gap > 0.0 else carried
        columns[index - 1] = _without_crumbs(filled, settings.layers.line_width)
    return columns


def _without_crumbs(section: manifold3d.CrossSection, width: float) -> manifold3d.CrossSection:
    """Ohne Stücke unter zwei Bahnen im Quadrat: Die druckt kein Slicer als
    Stütze (Orca ``support_remove_small_overhang``), und als eigene Anfahrt
    mit Rückzug und Z-Hub kosteten sie am Arbeitsplattenreiniger aus dem Korpus
    181 596 Anfahrten und 15 Stunden, die keine Druckdatei hat."""
    parts = section.decompose()
    smallest = 4.0 * width * width
    kept = [part for part in parts if part.area() >= smallest]
    if len(kept) == len(parts):
        return section
    if not kept:
        return manifold3d.CrossSection()
    return manifold3d.CrossSection.batch_boolean(kept, manifold3d.OpType.Add)


def _outline_length(section: manifold3d.CrossSection) -> float:
    """Der Umfang aller Ringe eines Clipper-Querschnitts."""
    total = 0.0
    for ring in section.to_polygons():
        points = np.asarray(ring, dtype=float)
        if len(points) < 2:
            continue
        step = np.roll(points, -1, axis=0) - points
        total += float(np.hypot(step[:, 0], step[:, 1]).sum())
    return total


#: Welcher Anteil des Umfangs einer Stützsäule je Schicht als Verbindung
#: zwischen den Bahnen eines Musters dazukommt (wie bei der Füllung,
#: :data:`CONNECTION_SHARE`). Gemessen an Pilz, Seitenablage, Wedge-Lock,
#: Arbeitsplattenreiniger und Waschschüssel (06.10.2026; Stützbahn der
#: Druckdatei minus Fläche mal Dichte durch Breite, geteilt durch den Umfang
#: der Säulen): PrusaSlicer 0,28 bis 0,63, CuraEngine 0,51 bis 0,68, Creality
#: Print 0 bis 1,46 — eingetragen das Mittel der dreizehn Läufe. Bäume folgen
#: keinem Umfang (Bambu Studio 0,28 bis 0,78 der geraden Bahn, ElegooSlicer
#: 0,65 bis 9,5); sie bleiben bei der geraden Bahn.
SUPPORT_CONNECTION_SHARE: Final = 0.6


def _support_parts(
    supports: Sequence[manifold3d.CrossSection],
    index: int,
    settings: PrintSettings,
) -> tuple[manifold3d.CrossSection, manifold3d.CrossSection]:
    """Muster und Kontaktschichten einer Schicht: Kontakt ist, was die
    Kontaktschichten darüber nicht mehr als Säule weitertragen — ohne die
    Säume, die eine Säule neben einer schrägen Wand von Schicht zu Schicht
    verliert: Am Arbeitsplattenreiniger zerfiel der Kontakt sonst in 250
    Splitter je Schicht, jeder mit Anfahrt, Rückzug und Hub (17 statt 0,4 h)."""
    support = supports[index]
    layers = max(settings.support.interface_layers, 0)
    width = settings.layers.line_width
    if layers == 0:
        contact = manifold3d.CrossSection()
    elif index + layers < len(supports):
        hollow = support - supports[index + layers]
        contact = _without_crumbs(_inset(_inset(hollow, -width), width), width)
    else:
        contact = support
    body = support - contact if not contact.is_empty() else support
    return body, contact


def uses_tree_supports(settings: PrintSettings, motion: Motion) -> bool:
    """Ob der Slicer mit diesen Werten Baumstützen setzt — gewählt, als Hybrid,
    wo er sie kennt (RM-584: Bäume an den Details, Gitter nur unter großen
    flachen Decken), oder als „automatisch“ seines Profils. Eine Antwort für
    Zeitmodell und Gegenprobe (``estimate.time_comparison_blocked``)."""
    style = settings.support.style
    return (
        style == "tree"
        or (style == "hybrid" and motion.support_hybrid)
        or (style == "auto" and motion.support_tree)
    )


def _contact_density(settings: PrintSettings, motion: Motion) -> float:
    """Wie dicht die Trennschicht liegt: aus der Lücke, die Solidon schreibt, wo
    sie gewählt oder übernommen ist (RM-583), sonst die des Herstellerprozesses."""
    width = settings.layers.line_width
    if "support.interface_spacing" in settings.chosen | settings.accepted and width > 0.0:
        return width / (width + max(settings.support.interface_spacing, 0.0))
    return motion.support_interface_density or 1.0


def _support_lines(
    layer: _Layer,
    supports: Sequence[manifold3d.CrossSection],
    index: int,
    settings: PrintSettings,
    roles: _Roles,
    motion: Motion,
    height: float,
) -> None:
    """Die Stützbahnen einer Schicht: Kontaktschichten unter dem Überhang,
    darunter das Muster mit der Dichte des Profils und seinen Verbindungen am
    Rand (:data:`SUPPORT_CONNECTION_SHARE`); ein Baum als Zug kurzer Stücke
    (:data:`TREE_SEGMENT`, :data:`TREE_TURN`)."""
    width = settings.layers.line_width
    flow = settings.filament.max_flow
    body, contact = _support_parts(supports, index, settings)
    tree = uses_tree_supports(settings, motion)
    density = max(settings.support.density, 0.0)
    contact_density = _contact_density(settings, motion)
    for area, share, speed, joined in (
        (body, density, roles.support, not tree),
        (contact, contact_density, roles.support_interface, False),
    ):
        surface = float(area.area())
        if surface <= 1e-6 or share <= 0.0:
            continue
        speed = _capped(speed, width, height, flow)
        accel = min(roles.a_support, roles.a_limit)
        path = surface * share / width
        if tree:
            number = max(1, round(path / TREE_SEGMENT))
            layer.support.append(_Lines(number, path / number, speed, accel, TREE_TURN))
        else:
            boundary = _outline_length(area)
            chord = max(math.pi * surface / boundary, width) if boundary > 0.0 else width
            number = max(1, round(path / chord))
            layer.support.append(_Lines(number, path / number, speed, accel))
            if joined and boundary > 0.0:
                edge = SUPPORT_CONNECTION_SHARE * _outline_length(supports[index])
                layer.support.append(_Lines(number, edge / number, speed, accel))
        # Nur Stücke, die ein Slicer druckt: Säume von Fläche null zwischen
        # Kontakt und Muster sind keine Anfahrt.
        smallest = 4.0 * width * width
        layer.starts += sum(1 for piece in area.decompose() if piece.area() >= smallest)


def support_material(
    result: SliceResult,
    settings: PrintSettings,
    motion: Motion,
    *,
    cancelled: CancelToken | None = None,
) -> float:
    """Das Stützmaterial dieser Säulen in mm³ — dieselben Säulen, die die
    Druckzeit fährt (:func:`_support_columns`): voller Überstand, geschlossen
    wie im Slicer, ohne Krümel; je Schicht das Muster mit seiner Dichte und
    seinen Verbindungen am Rand, die Kontaktschichten mit ihrer.

    Der Rauminhalt unter den Überhängen mal Dichte
    (:func:`app.core.slice.estimate.support_material`) lag an gewölbten Flächen
    ein Drittel bis ein Zwölftel unter der Druckdatei (Waschschüssel,
    Arbeitsplattenreiniger): Er stützt je Schicht nur den Splitter jenseits der
    Überhangweite.
    """
    if settings.support.style == "none":
        return 0.0
    _material, columns = _columns_of(result, settings, motion, cancelled)
    width = settings.layers.line_width
    density = max(settings.support.density, 0.0)
    contact_density = _contact_density(settings, motion)
    tree = uses_tree_supports(settings, motion)
    total = 0.0
    for index, column in enumerate(columns):
        if column.is_empty():
            continue
        height = (
            settings.layers.first_layer_height
            if index == 0
            else result.layers[index].z - result.layers[index - 1].z
        )
        body, contact = _support_parts(columns, index, settings)
        area = body.area() * density + contact.area() * contact_density
        if not tree:
            area += SUPPORT_CONNECTION_SHARE * _outline_length(column) * width
        total += area * height
    return total


def _nominal(layer: _Layer, roles: _Roles, scale: float, floor: float) -> float:
    """Weg durch Tempo bei skaliertem Tempo — die Größe, mit der die Slicer bremsen."""
    total = 0.0
    for loop in layer.loops:
        speed = max(loop.speed * scale, min(loop.speed, floor))
        total += loop.length / speed
        if loop.overhang > 0.0 and 0.0 < roles.bridge < speed:
            total += loop.overhang * (1.0 / roles.bridge - 1.0 / speed)
    for lines in layer.lines:
        speed = max(lines.speed * scale, min(lines.speed, floor))
        total += lines.count * lines.length / speed
    return total


def _actual(layer: _Layer, roles: _Roles, scale: float, floor: float) -> float:
    """Die Zeit mit Beschleunigung und Ecken, bei den gebremsten Tempi."""
    total = 0.0
    for loop in layer.loops:
        speed = max(loop.speed * scale, min(loop.speed, floor))
        total += _loop_time(loop, speed, roles)
        if loop.overhang > 0.0 and 0.0 < roles.bridge < speed:
            total += loop.overhang * (1.0 / roles.bridge - 1.0 / speed)
    for lines in layer.lines:
        speed = max(lines.speed * scale, min(lines.speed, floor))
        # Bahnen hängen im Zickzack aneinander: an jedem Ende zwei Ecken um
        # neunzig Grad, dort das Ecktempo der Maschine statt eines Halts.
        corner = corner_speed(speed, lines.acceleration, lines.turn, roles)
        total += lines.count * trapezoid(lines.length, speed, lines.acceleration, corner, corner)
    return total


def _corners(speed: float, acceleration: float, turns: np.ndarray, roles: _Roles) -> np.ndarray:
    """:func:`corner_speed` für alle Ecken einer Schleife auf einmal."""
    if roles.jd > 0.0:
        half = np.sin((np.pi - turns) / 2.0)
        open_ = half < 1.0 - 1e-12
        result = np.full(turns.shape, speed)
        ratio = half[open_] / (1.0 - half[open_])
        result[open_] = np.minimum(speed, np.sqrt(acceleration * roles.jd * ratio))
    elif roles.jerk > 0.0:
        sines = np.maximum(2.0 * np.sin(turns / 2.0), 1e-9)
        result = np.minimum(speed, roles.jerk / sines)
    else:
        result = np.where(turns < 1e-9, speed, 0.0)
    result[turns < 1e-9] = speed
    return result


def _loop_time(loop: _Loop, speed: float, roles: _Roles) -> float:
    """Ein Vorwärts- und ein Rückwärtslauf über die Ecken, dann je Stück ein Trapez."""
    lengths = loop.lengths
    count = len(lengths)
    if count == 0 or speed <= 0.0:
        return 0.0
    accel = loop.acceleration
    if accel <= 0.0 or not math.isfinite(accel):
        return loop.length / speed
    corners = _corners(speed, accel, loop.turns, roles).tolist()
    corners[-1] = 0.0
    reach = (2.0 * accel * lengths).tolist()
    entry = [0.0] * count
    exit_ = [0.0] * count
    current = 0.0
    for index in range(count):
        entry[index] = current
        current = min(speed, corners[index], math.sqrt(current * current + reach[index]))
        exit_[index] = current
    current = 0.0
    for index in range(count - 1, -1, -1):
        if exit_[index] > current:
            exit_[index] = current
        back = math.sqrt(current * current + reach[index])
        if entry[index] > back:
            entry[index] = back
        current = entry[index]
    start = np.asarray(entry)
    end = np.asarray(exit_)
    rise = (speed * speed - start * start) / (2.0 * accel)
    fall = (speed * speed - end * end) / (2.0 * accel)
    full = rise + fall <= lengths
    cruise = (speed - start) / accel + (speed - end) / accel + (lengths - rise - fall) / speed
    peak = np.sqrt(np.maximum((reach + start * start + end * end) / 2.0, 0.0))
    short = (np.maximum(peak - start, 0.0) + np.maximum(peak - end, 0.0)) / accel
    return float(np.where(full, cruise, short).sum())


def _fixed(layer: _Layer, roles: _Roles, *, nominal: bool) -> float:
    """Was das Abbremsen nicht ändert: Leerfahrt, Rückzug, Z-Hub."""
    if nominal:
        travel = (
            (layer.starts * layer.travel + layer.steps * layer.step) / roles.travel
            if roles.travel > 0.0
            else 0.0
        )
        hop = layer.starts * 2.0 * roles.z_hop / roles.z_speed if roles.z_speed > 0.0 else 0.0
    else:
        travel = layer.starts * trapezoid(layer.travel, roles.travel, roles.a_travel)
        travel += layer.steps * trapezoid(layer.step, roles.travel, roles.a_travel)
        hop = layer.starts * 2.0 * trapezoid(roles.z_hop, roles.z_speed, roles.z_accel)
    retract = 0.0
    if roles.retract > 0.0 and roles.retract_speed > 0.0 and roles.deretract_speed > 0.0:
        retract = layer.starts * (
            roles.retract / roles.retract_speed + roles.retract / roles.deretract_speed
        )
    return travel + hop + retract


def _layer_seconds(layer: _Layer, roles: _Roles, minimum_time: float, floor: float) -> float:
    """Erst bremsen wie der Kühlpuffer (Weg durch Tempo), dann die Zeit rechnen."""
    fixed = _fixed(layer, roles, nominal=True)
    scale = 1.0
    if minimum_time > 0.0 and _nominal(layer, roles, 1.0, floor) + fixed < minimum_time:
        wanted = minimum_time - fixed
        low, high = 1e-3, 1.0
        for _step in range(40):
            middle = (low + high) / 2.0
            if _nominal(layer, roles, middle, floor) > wanted:
                low = middle
            else:
                high = middle
        scale = high
    support = sum(
        lines.count
        * trapezoid(
            lines.length,
            lines.speed,
            lines.acceleration,
            corner_speed(lines.speed, lines.acceleration, lines.turn, roles),
            corner_speed(lines.speed, lines.acceleration, lines.turn, roles),
        )
        for lines in layer.support
    )
    return _actual(layer, roles, scale, floor) + support + _fixed(layer, roles, nominal=False)


def plate_seconds(
    parts: Sequence[tuple[SliceResult, PrintSettings]],
    motion: Motion,
    *,
    cancelled: CancelToken | None = None,
) -> float:
    """Die Druckzeit einer Platte ab der ersten Schicht, in Sekunden.

    Die Teile stehen auf demselben Raster vom Bett an; ihre Schichten gleicher
    Nummer werden zusammen gedruckt und zusammen gebremst — zwei kleine Teile
    sind zusammen schneller fertig als jedes für sich mit seiner Mindestzeit.
    Die Mindestschichtzeit gilt die der ersten Einstellungen, wie bei einem
    Slicer, der eine Platte mit einem Prozess schneidet.
    """
    if not parts:
        return 0.0
    first_settings = parts[0][1]
    roles_first = _roles(first_settings, motion)
    built = [
        _layers(result, settings, _roles(settings, motion), motion, cancelled)
        for result, settings in parts
    ]
    total = 0.0
    for index in range(max((len(layers) for layers in built), default=0)):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        together = _Layer()
        for layers in built:
            if index < len(layers):
                own = layers[index]
                together.loops.extend(own.loops)
                together.lines.extend(own.lines)
                together.support.extend(own.support)
                together.starts += own.starts
                together.steps += own.steps
                together.step = max(together.step, own.step)
                together.travel = max(together.travel, own.travel)
        total += _layer_seconds(
            together,
            roles_first,
            first_settings.cooling.minimum_layer_time,
            first_settings.cooling.minimum_speed,
        )
    return total
