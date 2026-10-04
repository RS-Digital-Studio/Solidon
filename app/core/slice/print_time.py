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
- **Füllung**: Deck- und Bodenschalen an den ganzen Nachbarschichten, Brücke
  wo mehr als eine Bahnbreite über die Schicht darunter ragt, innere Brücke über
  dünner Füllung, dünne Füllung mit ihrer Dichte. Die Bahnzahl folgt aus der
  mittleren Sehne ``π·A/U`` (Cauchy), jede Bahn ein Trapez zwischen zwei Ecken.
- **Abbremsen**: Liegt die Schicht unter der Mindestschichtzeit, werden die
  Bahnen über Weg/Tempo gebremst, nie unter das **Mindestdrucktempo** des
  Herstellerprofils (:attr:`Motion.minimum_speed`) — gemessen am SuperSlicer-Pilz:
  7,03 s Stielschicht trotz 15 s Vorgabe. Die Beschleunigung kommt danach,
  bei den gebremsten Tempi, wie in den Slicern selbst.
- **Leerfahrt, Rückzug und Z-Hub** je Zugbeginn.

Was sie nicht kennt: Stützen, Haftungsränder, Lückenfüllung, die genaue
Reihenfolge der Bahnen. Sie trägt ``source="internal"`` und wird mit der Zeit
aus der Druckdatei verglichen, nie vermischt (Regel 14). Ohne belegtes
Mindestdrucktempo gibt es keine :class:`Motion` und damit keine Zahl —
eine Mindestdauer, die niemand belegt, wird nicht behauptet.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.types import CancelToken, PrintSettings, SliceResult


@dataclass(frozen=True, slots=True)
class Motion:
    """Was die Druckzeit bestimmt und nicht in den Druckeinstellungen steht.

    Gelesen aus dem Herstellerprofil des gewählten Slicers
    (:func:`app.core.export.manufacturer.base_settings`, :attr:`Foundation.motion`)
    oder aus der Cura-Druckerdefinition. ``None`` heißt: nicht belegt — dann
    gilt der nächstliegende Wert aus den Druckeinstellungen.
    """

    nozzle: float
    """Düsendurchmesser — die Bahnbreite einer Brücke."""
    minimum_speed: float
    """Tiefer bremst der Slicer für die Mindestschichtzeit nicht, in mm/s."""
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
    )


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


@dataclass(slots=True)
class _Layer:
    loops: list[_Loop] = field(default_factory=list)
    lines: list[_Lines] = field(default_factory=list)
    starts: int = 0
    travel: float = 0.0


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


def _rings(geometry: BaseGeometry) -> list[np.ndarray]:
    found: list[np.ndarray] = []
    for polygon in shapely.get_parts(geometry):
        if not isinstance(polygon, ShapelyPolygon) or polygon.is_empty:
            continue
        found.append(np.asarray(polygon.exterior.coords))
        found.extend(np.asarray(ring.coords) for ring in polygon.interiors)
    return found


def _pieces(geometry: BaseGeometry) -> int:
    return 0 if geometry.is_empty else int(shapely.get_num_geometries(geometry))


def _capped(speed: float, width: float, height: float, flow: float) -> float:
    if flow > 0.0 and width * height * speed > flow:
        return flow / (width * height)
    return speed


def _layers(
    result: SliceResult,
    settings: PrintSettings,
    roles: _Roles,
    motion: Motion,
    cancelled: CancelToken | None,
) -> list[_Layer]:
    """Die Bahnen jeder Schicht dieses Körpers, noch ohne Zeit."""
    regions = []
    for info in result.layers:
        if info.area <= 1e-6:
            continue
        shapes = [ShapelyPolygon(contour.outline, list(contour.holes)) for contour in info.contours]
        regions.append(unary_union(shapes).buffer(0) if shapes else ShapelyPolygon())
    layers = settings.layers
    shell = settings.shell
    width = layers.line_width
    first_width = layers.first_layer_line_width or width
    walls = shell.wall_count
    flow = settings.filament.max_flow
    count = len(regions)
    interiors = [
        region.buffer(-walls * (first_width if index == 0 else width), join_style=2)
        for index, region in enumerate(regions)
    ]
    built: list[_Layer] = []
    sparse_below: BaseGeometry | None = None
    for index, region in enumerate(regions):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first = index == 0
        height = layers.first_layer_height if first else layers.layer_height
        # Was mehr als eine Bahnbreite über die Schicht darunter hinausragt und
        # breiter als zwei Bahnen ist, trägt nichts: Brücke und Überhangwand.
        unsupported = (
            region.difference(regions[index - 1].buffer(width)).buffer(-width).buffer(width)
            if index > 0
            else None
        )
        layer = _Layer()
        for loop in range(walls):
            line = first_width if first else width
            offset = region.buffer(-(loop + 0.5) * line, join_style=2)
            if first:
                speed, accel = roles.first_wall, roles.a_first
            elif loop == 0:
                speed, accel = roles.outer, roles.a_outer
            else:
                speed, accel = roles.inner, roles.a_inner
            speed = _capped(speed, line, height, flow)
            for ring in _rings(offset):
                lengths, turns = _segments(ring)
                over = 0.0
                if unsupported is not None and not unsupported.is_empty:
                    over = LineString(ring).intersection(unsupported).length
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
                layer.starts += 1
        inside = interiors[index]
        parts: list[tuple[BaseGeometry, float, float, float, float]] = []
        if not inside.is_empty:
            neighbours = [
                regions[other] if 0 <= other < count else ShapelyPolygon()
                for other in (
                    *range(index + 1, index + 1 + shell.top_layers),
                    *range(index - 1, index - 1 - shell.bottom_layers, -1),
                )
            ]
            covered = inside
            for other in neighbours:
                covered = covered.intersection(other)
                if covered.is_empty:
                    break
            if shell.top_layers <= 0:
                top = ShapelyPolygon()
            else:
                top = inside.difference(regions[index + 1]) if index + 1 < count else inside
            internal = inside.difference(covered).difference(top)
            if first:
                # Ohne Bodenschicht ist auch die erste Schicht dünne Füllung.
                density = 1.0 if shell.bottom_layers > 0 else settings.infill.density
                parts.append((inside, first_width, density, roles.first_infill, roles.a_first))
            else:
                bridge = (
                    inside.intersection(unsupported)
                    if unsupported is not None
                    else ShapelyPolygon()
                )
                if not bridge.is_empty:
                    top = top.difference(bridge)
                    internal = internal.difference(bridge)
                    parts.append((bridge, motion.nozzle, 1.0, roles.bridge, roles.a_bridge))
                # Die erste volle Schicht über dünner Füllung ist eine innere Brücke.
                if sparse_below is not None and not sparse_below.is_empty:
                    inner = (
                        internal.union(top).intersection(sparse_below).buffer(-width).buffer(width)
                    )
                    if not inner.is_empty:
                        internal = internal.difference(inner)
                        top = top.difference(inner)
                        parts.append(
                            (inner, motion.nozzle, 1.0, roles.internal_bridge, roles.a_bridge)
                        )
                parts.append((top, width, 1.0, roles.top, roles.a_top))
                parts.append((internal, width, 1.0, roles.solid, roles.a_solid))
                parts.append(
                    (covered, width, settings.infill.density, roles.sparse, roles.a_sparse)
                )
            sparse_below = covered
        else:
            sparse_below = ShapelyPolygon()
        for area, line, density, speed, accel in parts:
            surface = float(area.area)
            if surface <= 1e-6 or density <= 0.0:
                continue
            speed = _capped(speed, line, height, flow)
            path = surface * density / line
            boundary = float(area.length)
            chord = max(math.pi * surface / boundary, line) if boundary > 0.0 else line
            number = max(1, round(path / chord))
            layer.lines.append(_Lines(number, path / number, speed, min(accel, roles.a_limit)))
            layer.starts += _pieces(area)
        layer.travel = math.sqrt(region.area) / 2.0 if region.area > 0.0 else 0.0
        built.append(layer)
    return built


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
        corner = corner_speed(speed, lines.acceleration, math.pi / 2.0, roles)
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
        travel = layer.starts * layer.travel / roles.travel if roles.travel > 0.0 else 0.0
        hop = layer.starts * 2.0 * roles.z_hop / roles.z_speed if roles.z_speed > 0.0 else 0.0
    else:
        travel = layer.starts * trapezoid(layer.travel, roles.travel, roles.a_travel)
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
    return _actual(layer, roles, scale, floor) + _fixed(layer, roles, nominal=False)


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
                together.starts += own.starts
                together.travel = max(together.travel, own.travel)
        total += _layer_seconds(
            together,
            roles_first,
            first_settings.cooling.minimum_layer_time,
            motion.minimum_speed,
        )
    return total
