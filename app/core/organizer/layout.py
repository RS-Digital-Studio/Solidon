"""Ein maßlicher Rahmen für Fächer, Wände, Modulnähte und Fußaufnahmen."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from app.core import expressions
from app.core.organizer.serialize import (
    MAX_COUNT,
    MAX_DIMENSION,
    MAX_LAYOUT_CELLS,
    LayoutSpec,
    Node,
    Number,
    invalid,
)
from app.core.units import EPS_GEOM
from app.i18n import _


@dataclass(frozen=True, slots=True)
class Rect:
    """Ein lokales XY-Rechteck mit ungerundeten Maßen."""

    x: float
    y: float
    width: float
    depth: float

    @property
    def size(self) -> tuple[float, float]:
        return self.width, self.depth

    @property
    def centre(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.depth / 2


@dataclass(frozen=True, slots=True)
class Cell:
    """Lichtes Fach und zugehöriger Modulrahmen, bis zur Mitte seiner Wände."""

    id: str
    rect: Rect
    module: Rect
    radius: float


@dataclass(frozen=True, slots=True)
class Wall:
    """Ein tatsächlich belegter Trennwandabschnitt; Höhe ab Körperunterseite."""

    id: str
    rect: Rect
    height: float
    radius: float
    axis: str


@dataclass(frozen=True, slots=True)
class OrganizerLayout:
    """Dieselbe unveränderliche Aufteilung für Bau, Vorschau und Folgeoperationen."""

    width: float
    depth: float
    height: float
    wall: float
    floor: float
    radius: float
    cells: tuple[Cell, ...]
    walls: tuple[Wall, ...]
    inactive_heights: tuple[str, ...] = ()

    def foot_positions(
        self, inset: float, *, each_cell: bool = False
    ) -> tuple[tuple[float, float], ...]:
        """Vier Punkte je Außen-/Modulrahmen; unpassende Abstände sichtbar ablehnen."""
        areas = (
            [cell.module for cell in self.cells]
            if each_cell
            else [Rect(-self.width / 2, -self.depth / 2, self.width, self.depth)]
        )
        if (
            not math.isfinite(inset)
            or inset <= EPS_GEOM
            or any(2 * inset >= min(area.size) - EPS_GEOM for area in areas)
        ):
            raise invalid(
                _(
                    "Die Füße passen mit diesem Randabstand nicht. "
                    "Verkleinern Sie den Abstand oder vergrößern Sie die Fächer."
                )
            )
        return tuple(
            (area.x + x, area.y + y)
            for area in areas
            for x in (inset, area.width - inset)
            for y in (inset, area.depth - inset)
        )


@dataclass(frozen=True, slots=True)
class _Resolved:
    """Ein einmal ausgewerteter Knoten mit natürlichem Innenmaß und Zellzahl."""

    source: Node
    width: float
    depth: float
    radius: float = 0.0
    wall: float = 0.0
    heights: tuple[tuple[int, float], ...] = ()
    children: tuple[_Resolved, ...] = ()
    count: int = 1
    cells: int = 1


def _value(raw: Number, values: Mapping[str, float], *, zero: bool = False) -> float:
    """Die gemeinsame Ausdruckssprache auswerten und reale Konstruktionsmaße prüfen."""
    if isinstance(raw, str):
        refs = expressions.references(raw)
        if any(isinstance(values.get(name), bool) for name in refs):
            raise invalid(
                _("Ein Fachmaß braucht eine endliche Zahl oder einen gültigen Maßausdruck.")
            )
        value = expressions.evaluate(raw, values)
    else:
        value = raw
    if (
        isinstance(value, bool)
        or not math.isfinite(value)
        or value > MAX_DIMENSION
        or value < (0.0 if zero else EPS_GEOM)
    ):
        raise invalid(
            _("Ein Fachmaß liegt außerhalb des gültigen Bereichs. Passen Sie das Maß an.")
        )
    return float(value)


def _resolve(
    node: Node, values: Mapping[str, float], *, inner: bool, height: float, floor: float
) -> _Resolved:
    if node.kind == "cell":
        return _Resolved(
            node,
            _value(node.width, values),
            _value(node.depth, values),
            _value(node.radius, values, zero=True),
        )
    wall = _value(node.wall, values)
    radius = _value(node.opening_radius, values, zero=True)
    heights = tuple((index, _value(value, values, zero=True)) for index, value in node.heights)
    if any(value < floor - EPS_GEOM or value > height + EPS_GEOM for _index, value in heights):
        raise invalid(
            _(
                "Eine Trennwandhöhe muss zwischen Bodenoberseite und "
                "Gesamthöhe liegen. Passen Sie die Höhe an."
            )
        )
    count_value = _value(node.count, values) if node.kind == "repeat" else 1.0
    if abs(count_value - round(count_value)) > EPS_GEOM or not 1 <= count_value <= MAX_COUNT:
        raise invalid(
            _("Die Fachzahl muss eine ganze Zahl zwischen 1 und 32 sein. Ändern Sie die Anzahl.")
        )
    children = tuple(
        _resolve(child, values, inner=inner, height=height, floor=floor) for child in node.children
    )
    count = round(count_value)
    cells = sum(child.cells for child in children) * count
    if cells > MAX_LAYOUT_CELLS:
        raise invalid(_("Die Aufteilung hat zu viele Fächer. Verringern Sie Reihen oder Spalten."))
    along = [child.width if node.axis == "x" else child.depth for child in children]
    across = [child.depth if node.axis == "x" else child.width for child in children]
    if inner and max(across) - min(across) > EPS_GEOM:
        raise invalid(
            _(
                "Die lichten Fachmaße passen an dieser Teilung nicht "
                "zusammen. Gleichen Sie die gemeinsame Breite oder Tiefe an."
            )
        )
    length = sum(along) * count + wall * (len(children) * count - 1)
    cross = max(across)
    width, depth = (length, cross) if node.axis == "x" else (cross, length)
    return _Resolved(node, width, depth, radius, wall, heights, children, count, cells)


def resolve_layout(
    spec: LayoutSpec,
    values: Mapping[str, float],
    *,
    width: float,
    depth: float,
    height: float,
    wall: float,
    floor: float,
    radius: float,
) -> OrganizerLayout:
    """Bezug auflösen und alle fachlichen Rechtecke aus genau einem Baum ableiten."""
    width, depth, height, wall, floor = (_value(v, {}) for v in (width, depth, height, wall, floor))
    radius = _value(radius, {}, zero=True)
    if floor >= height - EPS_GEOM:
        raise invalid(_("Der Boden ist so hoch wie der Organizer. Verringern Sie die Bodenstärke."))
    root = _resolve(spec.root, values, inner=spec.basis == "inner", height=height, floor=floor)
    if spec.basis == "inner":
        width, depth = root.width + 2 * wall, root.depth + 2 * wall
    if min(width, depth) <= 2 * wall + EPS_GEOM or max(width, depth) > MAX_DIMENSION:
        raise invalid(
            _(
                "Die Außenmaße lassen keinen freien Innenraum. Vergrößern "
                "Sie den Organizer oder verringern Sie die Wandstärke."
            )
        )
    if 2 * radius > min(width, depth) + EPS_GEOM:
        raise invalid(_("Der Außenradius ist zu groß. Verkleinern Sie den Radius."))
    cells: list[Cell] = []
    walls: list[Wall] = []
    outer = Rect(-width / 2, -depth / 2, width, depth)
    clear = Rect(outer.x + wall, outer.y + wall, width - 2 * wall, depth - 2 * wall)
    _place(root, clear, outer, "", height, cells, walls)
    overrides = {key: _value(value, values, zero=True) for key, value in spec.wall_heights}
    if any(value < floor - EPS_GEOM or value > height + EPS_GEOM for value in overrides.values()):
        raise invalid(
            _(
                "Eine Trennwandhöhe muss zwischen Bodenoberseite und "
                "Gesamthöhe liegen. Passen Sie die Höhe an."
            )
        )
    walls = [replace(entry, height=overrides.get(entry.id, entry.height)) for entry in walls]
    inactive = tuple(sorted(set(overrides) - {entry.id for entry in walls}))
    return OrganizerLayout(
        width, depth, height, wall, floor, radius, tuple(cells), tuple(walls), inactive
    )


def _place(
    node: _Resolved,
    rect: Rect,
    module: Rect,
    prefix: str,
    height: float,
    cells: list[Cell],
    walls: list[Wall],
) -> None:
    identifier = prefix + node.source.id
    if node.source.kind == "cell":
        if 2 * node.radius > min(rect.size) + EPS_GEOM:
            raise invalid(
                _(
                    "Ein Innenradius passt nicht in sein Fach. Verkleinern "
                    "Sie den Radius oder vergrößern Sie das Fach."
                )
            )
        cells.append(Cell(identifier, rect, module, node.radius))
        return
    axis = node.source.axis
    children = node.children * node.count
    lengths = [child.width if axis == "x" else child.depth for child in children]
    available = (rect.width if axis == "x" else rect.depth) - node.wall * (len(children) - 1)
    if available <= EPS_GEOM:
        raise invalid(
            _(
                "Die Trennwände füllen den Innenraum. Vergrößern Sie ihn "
                "oder wählen Sie weniger Fächer."
            )
        )
    sizes = [available * length / sum(lengths) for length in lengths]
    heights = dict(node.heights)
    offset = rect.x if axis == "x" else rect.y
    module_start = module.x if axis == "x" else module.y
    module_end = module_start + (module.width if axis == "x" else module.depth)
    for index, (child, size) in enumerate(zip(children, sizes, strict=True)):
        last = index == len(children) - 1
        end = module_end if last else offset + size + node.wall / 2
        child_rect = (
            Rect(offset, rect.y, size, rect.depth)
            if axis == "x"
            else Rect(rect.x, offset, rect.width, size)
        )
        child_module = (
            Rect(module_start, module.y, end - module_start, module.depth)
            if axis == "x"
            else Rect(module.x, module_start, module.width, end - module_start)
        )
        child_prefix = (
            f"{identifier}/{index + 1}/" if node.source.kind == "repeat" else f"{identifier}/"
        )
        _place(child, child_rect, child_module, child_prefix, height, cells, walls)
        if not last:
            boundary = (
                Rect(offset + size, rect.y, node.wall, rect.depth)
                if axis == "x"
                else Rect(rect.x, offset + size, rect.width, node.wall)
            )
            if 2 * node.radius > min(boundary.size) + EPS_GEOM:
                raise invalid(
                    _("Der Radius der Wandfreistellung ist zu groß. Verkleinern Sie ihn.")
                )
            walls.append(
                Wall(
                    f"{identifier}/wall_{index + 1}",
                    boundary,
                    heights.get(index + 1, height),
                    node.radius,
                    axis,
                )
            )
        offset += size + node.wall
        module_start = end
