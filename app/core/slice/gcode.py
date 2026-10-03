"""G-Code zurücklesen (Bauplan §28.1, §28.2).

Die Schichtanalyse (§22) sucht und beurteilt; der externe Slicer liefert die
Wahrheit für die Datei, die zum Drucker geht. Dieses Modul liest diese Wahrheit
zurück: Druckzeit, Material, **gemessenes** Stützvolumen, Schichtzahl,
Warnungen.

Das Verhältnis ist herum, wie §28.2 es beschreibt. Die Suche läuft intern über
hunderte Kandidaten; der externe Lauf bestätigt den Gewinner und liefert die
Kostenschätzung. Das hier ist also kein zweiter Slicer, es ist die
Endabnahme.

Jede Zahl, die hier herauskommt, trägt ``source="gcode"`` und wird nie mit
einer internen Schätzung vermischt (§22.5). Wo die zwei um mehr als ein
Sechstel auseinanderliegen, ist das ein Befund — und ein Hinweis, dass die
Schichtanalyse Arbeit braucht, kein Grund, eine von beiden still vorzuziehen.
Verbrauch aus dieser Datei ist für den Druck geplant, keine Messung an der
physischen Spule oder am fertigen Werkstück.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from io import StringIO
from itertools import pairwise
from typing import TYPE_CHECKING, Final

from app.core.errors import (
    CHECK_SLICER_PROFILE,
    SHOW_SLICER_OUTPUT,
    ValidationError,
)
from app.core.log import get_logger
from app.core.types import BoundingBox, CancelToken, Finding, MetricSource
from app.core.units import EPS_GEOM, EPS_SETTING
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

_log = get_logger(__name__)

#: Über diesem relativen Unterschied wird die Gegenprobe ein Befund (§28.2).
DEVIATION_LIMIT = 0.15

#: Historische Einmaterialkonstanten für bestehende Aufrufer, keine Parser-Vorgaben.
DEFAULT_DENSITY = 1.24

#: Historische Einmaterialvorgabe; vorbereitete Ausgaben tragen eigene Kennwerte.
DEFAULT_DIAMETER = 1.75

#: Querschnitt eines 1,75-mm-Filaments in mm².
FILAMENT_AREA = math.pi * (DEFAULT_DIAMETER / 2.0) ** 2

#: Speicherbudget für werkzeugweise Listen, keine behauptete Druckergrenze.
MAX_GCODE_TOOLS = 1024

#: Bambu-Firmwarebefehle ohne Filamentwechsel (GCodeProcessor::process_T).
_BAMBU_SPECIAL_TOOLS = frozenset({255, 1000, 1100})


@dataclass(slots=True)
class GcodeMetrics:
    """Was eine geslicete Datei über sich selbst sagt.

    Alles optional: Slicer schreiben verschiedene Kommentare, und ein
    fehlender Wert fehlt — er ist nicht null. Genau diese Unterscheidung ist
    der ganze Grund, die Datei zu lesen statt aus ihr zu raten.
    """

    slicer: str = ""
    print_seconds: float | None = None
    filament_mm: float | None = None
    filament_grams: float | None = None
    support_mm3: float | None = None
    layer_count: int | None = None
    layer_height: float | None = None
    warnings: tuple[str, ...] = ()
    source: MetricSource = "gcode"
    #: Index ist die Werkzeugnummer dieser Platte, einschließlich 0 und Lücken.
    filament_mm_by_tool: tuple[float | None, ...] = ()
    filament_grams_by_tool: tuple[float | None, ...] = ()
    #: Werkzeuge mit positiver Extrusion, einschließlich stationärer Reinigung.
    used_tools: tuple[int, ...] = ()
    #: Aufgelöste Einzelmengen des unveränderlichen Druckauftrags. ``None``
    #: heißt noch nicht aufgelöst; ein fehlender Einzelwert verhindert die Summe.
    resolved_filament_grams: tuple[float | None, ...] | None = None
    filament_diameters: tuple[float | None, ...] = ()
    filament_densities: tuple[float | None, ...] = ()
    #: Volumetrische E-Werte liefern ein Volumen auch ohne bekannten Durchmesser.
    filament_cm3_by_tool: tuple[float | None, ...] = ()
    #: Herkunft je Werkzeug: Kopfwert oder aus Extrusionsbewegungen berechnet.
    filament_mm_sources: tuple[str | None, ...] = ()
    #: Volumen einer Zusammenführung von Platten mit eigener Werkzeugbelegung.
    resolved_material_cm3: float | None = None
    #: Nur ein ausdrücklich genannter Modellzeitwert, keine interne Schätzung.
    model_print_seconds: float | None = None
    #: Aus tatsächlich extrudierten Modellrollen; Gesamtzahl bleibt separat.
    model_layer_count: int | None = None
    support_only_layer_count: int | None = None
    #: Rollen aus TYPE/FEATURE/FLUSH, je Rolle nach Werkzeugnummer aufgeteilt.
    #: Unbezeichnete Förderung bleibt unbekannt; Kopfwerte werden nicht verteilt.
    material_cm3_by_role: dict[str, tuple[float | None, ...]] = field(default_factory=dict)
    model_material_cm3: float | None = None
    purge_material_cm3: float | None = None
    unclassified_material_cm3: float | None = None
    #: Modellmasse einer Zusammenführung, ohne Werkzeugnummern der Platten zu vermischen.
    resolved_model_grams: float | None = None
    #: Gelesene Rollen mit bedingter oder nicht eindeutig aufgelöster Förderung.
    uncertain_material_roles: tuple[str, ...] = ()
    #: Nur bei vollständiger Rollenbilanz und ohne unbekannte/bedingte Förderung.
    #: False lässt die ausgewiesene Abschnittssumme stehen, behauptet aber
    #: keinen vollständig geplanten Spülverbrauch.
    purge_material_complete: bool = False

    @property
    def additional_seconds(self) -> float | None:
        """Zusatzzeit aus dem Modell-/Gesamtzeitpaar; keine belegte reine Startzeit."""
        if self.print_seconds is None or self.model_print_seconds is None:
            return None
        difference = self.print_seconds - self.model_print_seconds
        return difference if difference >= 0.0 else None

    @property
    def print_minutes(self) -> float | None:
        return None if self.print_seconds is None else self.print_seconds / 60.0

    @property
    def material_cm3(self) -> float | None:
        """Filamentlänge als Volumen — die Größe, die mit der Schätzung
        vergleichbar ist.
        """
        if self.resolved_material_cm3 is not None:
            return self.resolved_material_cm3
        if self.filament_cm3_by_tool:
            return _complete_sum(self.filament_cm3_by_tool)
        lengths = self.filament_mm_by_tool
        diameters = self.filament_diameters
        relevant = set(self.used_tools) | {
            tool for tool, value in enumerate(lengths) if value is None or value > 0.0
        }
        if not relevant:
            relevant = set(range(len(diameters)))
        areas = [_filament_area(_at(diameters, tool)) for tool in sorted(relevant)]
        # Bei gleichem Querschnitt gewinnt die ausdrückliche Gesamtlänge
        # weiterhin gegen gerundete Einzelwerte. Verschiedene Querschnitte
        # verlangen dagegen eine vollständige Werkzeugaufteilung.
        if (
            areas
            and (first := areas[0]) is not None
            and all(area is not None and math.isclose(area, first) for area in areas)
            and self.filament_mm is not None
        ):
            volume = self.filament_mm * first / 1000.0
            return volume if math.isfinite(volume) and volume >= 0.0 else None
        return _complete_sum(
            tuple(_volume(length, _at(diameters, tool)) for tool, length in enumerate(lengths))
        )

    def grams(self, density: float | None = None, diameter: float | None = None) -> float | None:
        """Eine belegte Gesamtmasse oder eine vollständige materialrichtige Auflösung.

        Explizite Grammwerte einschließlich null gewinnen. Eine vorbereitete
        Ausgabe bringt ihre Einzelmengen mit; spätere Dialogwerte verändern sie
        nicht. Dateieigene Durchmesser und Dichten gewinnen gegen Caller-Werte.
        Nur ein unaufgelöstes Einmaterialergebnis darf die ausdrücklich
        übergebene globale Dichte und den Durchmesser verwenden.
        """
        if self.filament_grams is not None:
            return (
                self.filament_grams
                if math.isfinite(self.filament_grams) and self.filament_grams >= 0.0
                else None
            )
        if self.resolved_filament_grams is not None:
            values = self.resolved_filament_grams
            if not values or any(
                value is None or not math.isfinite(value) or value < 0.0 for value in values
            ):
                return None
            return _complete_sum(values)
        count = max(
            len(self.filament_grams_by_tool),
            len(self.filament_mm_by_tool),
            len(self.filament_cm3_by_tool),
        )
        converted = _complete_sum(self.grams_by_tool())
        if converted is not None and all(tool < count for tool in self.used_tools):
            return converted
        if count > 1 or len(self.used_tools) > 1:
            return None
        length = self.filament_mm
        if length is None and len(self.filament_mm_by_tool) == 1:
            length = self.filament_mm_by_tool[0]
        tool = self.used_tools[0] if self.used_tools else 0
        density = _at(self.filament_densities, tool) or density
        diameter = _at(self.filament_diameters, tool) or diameter
        single = GcodeMetrics(filament_mm_by_tool=(length,))
        return single.grams_by_tool(densities=(density,), diameters=(diameter,))[0]

    def grams_by_tool(
        self,
        *,
        densities: Sequence[float | None] = (),
        diameters: Sequence[float | None] = (),
    ) -> tuple[float | None, ...]:
        """Geplante Masse je Werkzeug, mit ausdrücklich gewählter Umrechnung.

        Ein direkt genannter Grammwert gilt einschließlich null. Nur fehlende
        Grammwerte werden aus Länge, Dichte in g/cm³ und Durchmesser in mm
        berechnet. Dateieigene Materialdaten gewinnen gegen die übergebenen
        Werte. Alle Listen verwenden dieselben Werkzeugnummern; fehlende
        Materialangaben bleiben unbekannt, die Gesamtsumme füllt keine Lücke.
        """
        amounts: list[float | None] = []
        count = max(
            len(self.filament_grams_by_tool),
            len(self.filament_mm_by_tool),
            len(self.filament_cm3_by_tool),
        )
        for tool in range(count):
            stated = (
                self.filament_grams_by_tool[tool]
                if tool < len(self.filament_grams_by_tool)
                else None
            )
            if stated is not None:
                amounts.append(stated if math.isfinite(stated) and stated >= 0.0 else None)
                continue
            amount = None
            density = _at(self.filament_densities, tool) or _at(densities, tool)
            volume = _at(self.filament_cm3_by_tool, tool)
            if volume is not None and math.isfinite(volume) and volume >= 0.0:
                if volume <= 0.0:
                    amounts.append(0.0)
                    continue
                if density is not None and math.isfinite(density) and density > 0.0:
                    mass = volume * density
                    amounts.append(mass if math.isfinite(mass) else None)
                    continue
            if tool < len(self.filament_mm_by_tool):
                length = self.filament_mm_by_tool[tool]
                diameter = _at(self.filament_diameters, tool) or _at(diameters, tool)
                if length is not None and math.isfinite(length) and length <= 0.0:
                    amounts.append(0.0 if length >= 0.0 else None)
                    continue
                if (
                    length is not None
                    and math.isfinite(length)
                    and length >= 0.0
                    and density is not None
                    and math.isfinite(density)
                    and density > 0.0
                    and diameter is not None
                    and math.isfinite(diameter)
                    and diameter > 0.0
                ):
                    radius = diameter / 2.0
                    converted = length * math.pi * radius * radius / 1000.0 * density
                    amount = converted if math.isfinite(converted) else None
            amounts.append(amount)
        return tuple(amounts)

    def model_grams(self, density: float | None = None) -> float | None:
        """Nur Modellrollen, mit werkzeugrichtiger Dichte und belegtem Volumen.

        Eine ausdrücklich übergebene Ersatzdichte gilt nur beim Verbrauch
        genau eines Werkzeugs. Unbekannte Rollen oder Volumina werden nicht
        aus dem Gesamtverbrauch ergänzt.
        """
        if self.resolved_model_grams is not None:
            return self.resolved_model_grams
        if self.model_material_cm3 is None:
            return None
        volumes = self.material_cm3_by_role.get("model", ())
        supplied: tuple[float | None, ...] = ()
        if len(self.used_tools) == 1:
            tool = self.used_tools[0]
            supplied = (None,) * tool + (density,)
        amounts = GcodeMetrics(
            filament_cm3_by_tool=volumes,
            filament_densities=self.filament_densities,
        ).grams_by_tool(densities=supplied)
        return _complete_sum(amounts)


@dataclass(slots=True)
class GcodeAnalysis:
    """Alle Aussagen aus genau einem Durchlauf durch eine Druckdatei."""

    metrics: GcodeMetrics
    extrudes: bool
    extent: BoundingBox | None
    bed: BoundingBox | None
    settings: dict[str, str]
    bed_outline: tuple[tuple[float, float], ...] = ()
    excluded_areas: tuple[tuple[tuple[float, float], ...], ...] = ()
    paths_inside: bool | None = None
    firmware: str = ""
    #: Die erste Schicht (ab 1 gezählt), in der mit laufendem Bauteillüfter
    #: gedruckt wird, und dessen Stärke als Anteil — ``None``, wenn keine.
    #: Gezählt wird, was gedruckt wird, nicht was befohlen: Ein Lüfter, den
    #: der Startcode einschaltet und vor der ersten Bahn wieder aus, zählt nicht.
    fan_start: tuple[int, float] | None = None
    #: Die Befehle vor der ersten Schicht, ohne Kommentar und höchstens
    #: :data:`START_COMMANDS` — daran liest die Gegenprobe, ob der Startcode
    #: des Druckers ankam (Konzept Herstellerprofil, Entscheidung K).
    start: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GcodePath:
    """Eine aufgelöste Materialbahn für die Prüfung während des Lesens."""

    start: tuple[float | None, float | None, float | None]
    end: tuple[float | None, float | None, float | None]
    centre: tuple[float, float] | None = None
    clockwise: bool = False


def area_check(area: BaseGeometry) -> Callable[[GcodePath], bool]:
    """Prüft Geraden und Kreisbögen gegen eine vorbereitete freigegebene Fläche.

    Bögen werden an ihren analytischen Schnittwinkeln mit dem Polygonrand
    geteilt. Je offenem Winkelintervall liegt ein Prüfpunkt entweder ganz
    innerhalb oder ganz außerhalb; eine feste Abtastweite würde schmale
    Sperrflächen zwischen zwei Stützpunkten übersehen.
    """
    from shapely import get_parts
    from shapely.geometry import LineString, Point
    from shapely.prepared import prep

    prepared = prep(area)
    segments = [
        (start, end)
        for boundary in get_parts(area.boundary)
        for start, end in pairwise(boundary.coords)
    ]

    def check(path: GcodePath) -> bool:
        sx, sy = path.start[:2]
        ex, ey = path.end[:2]
        if ex is None or ey is None:
            return True
        if sx is None or sy is None:
            return bool(prepared.covers(Point(ex, ey)))
        if path.centre is None:
            return bool(prepared.covers(LineString(((sx, sy), (ex, ey)))))
        if not prepared.covers(Point(sx, sy)) or not prepared.covers(Point(ex, ey)):
            return False
        cx, cy = path.centre
        radius = math.hypot(sx - cx, sy - cy)
        if radius <= 0.0:
            return True
        start_angle = math.atan2(sy - cy, sx - cx)
        sweep = _arc_sweep(
            start_angle,
            math.atan2(ey - cy, ex - cx),
            clockwise=path.clockwise,
            full=math.isclose(sx, ex) and math.isclose(sy, ey),
        )
        angles = [0.0, sweep]
        for (ax, ay), (bx, by) in segments:
            dx, dy = bx - ax, by - ay
            squared = dx * dx + dy * dy
            if squared <= 0.0:
                continue
            projection = ((cx - ax) * dx + (cy - ay) * dy) / squared
            nearest_x, nearest_y = ax + projection * dx, ay + projection * dy
            radial_squared = radius * radius - (nearest_x - cx) ** 2 - (nearest_y - cy) ** 2
            if radial_squared < 0.0:
                continue
            offset = math.sqrt(radial_squared / squared)
            for along in (projection - offset, projection + offset):
                if not 0.0 <= along <= 1.0:
                    continue
                angle = math.atan2(ay + along * dy - cy, ax + along * dx - cx)
                delta = _arc_sweep(start_angle, angle, clockwise=path.clockwise, full=False)
                if delta < sweep:
                    angles.append(delta)
        angles.sort()
        direction = -1.0 if path.clockwise else 1.0
        for before, after in pairwise(angles):
            angle = start_angle + direction * (before + after) / 2.0
            if not prepared.covers(
                Point(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            ):
                return False
        return True

    return check


def _at(values: Sequence[float | None], index: int) -> float | None:
    """Ein Materialwert ohne erfundene Belegung hinter dem Listenende."""
    return values[index] if index < len(values) else None


def _filament_area(diameter: float | None) -> float | None:
    """Querschnitt eines belegten positiven Filamentdurchmessers in mm²."""
    if diameter is None or not math.isfinite(diameter) or diameter <= 0.0:
        return None
    radius = diameter / 2.0
    area = math.pi * radius * radius
    return area if math.isfinite(area) else None


def _volume(length: float | None, diameter: float | None) -> float | None:
    """Eine bekannte Filamentlänge mit belegtem Durchmesser als cm³."""
    if length is None or not math.isfinite(length) or length < 0.0:
        return None
    if length <= 0.0:
        return 0.0
    area = _filament_area(diameter)
    if area is None:
        return None
    volume = length * area / 1000.0
    return volume if math.isfinite(volume) else None


def _complete_sum(values: Sequence[float | None]) -> float | None:
    """Nur vollständige endliche Mengen ergeben eine bekannte Summe."""
    if not values or any(value is None or not math.isfinite(value) for value in values):
        return None
    result = sum(value for value in values if value is not None)
    return result if math.isfinite(result) else None


@dataclass(slots=True)
class _Extent:
    """Eine während des Lesens wachsende Hüllbox."""

    minimum: list[float] = field(default_factory=lambda: [float("inf")] * 3)
    maximum: list[float] = field(default_factory=lambda: [float("-inf")] * 3)
    seen: bool = False

    def add(self, *points: tuple[float | None, float | None, float | None]) -> None:
        for point in points:
            for axis, value in enumerate(point):
                if value is None or not math.isfinite(value):
                    continue
                self.minimum[axis] = min(self.minimum[axis], value)
                self.maximum[axis] = max(self.maximum[axis], value)
                self.seen = True

    def box(self) -> BoundingBox | None:
        if not self.seen:
            return None
        for axis in range(3):
            if self.minimum[axis] > self.maximum[axis]:
                self.minimum[axis] = self.maximum[axis] = 0.0
        return BoundingBox(
            (self.minimum[0], self.minimum[1], self.minimum[2]),
            (self.maximum[0], self.maximum[1], self.maximum[2]),
        )


@dataclass(slots=True)
class _ExtrusionState:
    """Extrusionsauswertung für einen Firmwaredialekt, ohne gespeicherte Bahnen.

    Manche Slicer nennen den Dialekt erst im Konfigurationsblock am Ende.
    Zwei kleine Zustände halten die beiden belegten G90/G91-Semantiken
    auseinander, ohne die Datei ein zweites Mal zu lesen oder aufzubewahren.
    """

    absolute: bool = True
    position: float = 0.0
    lengths: dict[int, float] = field(default_factory=dict)
    linear_lengths: dict[int, float] = field(default_factory=dict)
    volumes: dict[int, float] = field(default_factory=dict)
    unknown_volume_lengths: dict[int, float] = field(default_factory=dict)
    support: dict[int, float] = field(default_factory=dict)
    support_volumes: dict[int, float] = field(default_factory=dict)
    retracted: dict[int, tuple[float, bool]] = field(default_factory=dict)
    unknown_amounts: set[int] = field(default_factory=set)
    used_tools: set[int] = field(default_factory=set)
    all_extent: _Extent = field(default_factory=_Extent)
    model_extent: _Extent = field(default_factory=_Extent)
    all_paths_inside: bool = True
    model_paths_inside: bool = True
    role_lengths: dict[str, dict[int, float]] = field(default_factory=dict)
    role_volumes: dict[str, dict[int, float]] = field(default_factory=dict)
    model_layer_pending: bool = False
    model_heights: set[float] = field(default_factory=set)
    model_heights_known: bool = True
    support_layer_pending: bool = False
    support_heights: set[float] = field(default_factory=set)
    support_heights_known: bool = True
    model_complete: bool = True
    unmarked_unknown_motion: bool = False
    seen_model_role: bool = False
    uncertain_roles: set[str] = field(default_factory=set)
    role_position_uncertain: bool = False
    role_debt_uncertain: bool = False
    role_mode_uncertain: bool = False

    def classify(self, role: str, tool: int, amount: float, *, volumetric: bool) -> None:
        """Ordnet schon rückzugsbereinigte Förderung einer belegten Rolle zu."""
        amounts = (self.role_volumes if volumetric else self.role_lengths).setdefault(role, {})
        amounts[tool] = amounts.get(tool, 0.0) + amount

    def step(self, value: float) -> float:
        """Förderweg aus der E-Achse im aktuellen Extrusionsmodus."""
        if self.absolute:
            delta = value - self.position
            self.position = value
        else:
            delta = value
            self.position += value
        return delta

    def consume(self, tool: int, step: float, *, volumetric: bool, area: float | None) -> float:
        """Nur neue Förderung zählen; Rückzug und Wiederförderung gleichen sich je Werkzeug aus."""
        debt, was_volumetric = self.retracted.get(tool, (0.0, volumetric))
        if debt > 0.0 and was_volumetric != volumetric:
            if area is None:
                # Ohne Durchmesser lässt sich ein noch offener Rückzug nicht
                # zwischen Millimetern und Kubikmillimetern umrechnen.
                self.unknown_amounts.add(tool)
                debt = 0.0
            else:
                debt = debt * area if volumetric else debt / area
        remaining = step - debt
        self.retracted[tool] = (max(-remaining, 0.0), volumetric)
        return max(remaining, 0.0)


#: Kommentarzeilen, die die verbreiteten Slicer schreiben. Ein Muster je
#: Tatsache, nicht ein Parser je Slicer: ein neuer Slicer braucht meist nur
#: eine weitere Zeile hier.
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("print_seconds", r";\s*total estimated time\s*:\s*(?P<value>[0-9hmsd ]+)"),
    ("print_seconds", r";\s*estimated printing time.*?=\s*(?P<value>[0-9hmsd ]+)"),
    ("print_seconds", r";\s*TIME:\s*(?P<value>[0-9.]+)"),
    ("print_seconds", r";\s*total print time.*?:\s*(?P<value>[0-9hmsd ]+)"),
    ("model_print_seconds", r";\s*model printing time\s*:\s*(?P<value>[0-9hmsd ]+)"),
    (
        "filament_mm",
        r";\s*(?P<total>total )filament length \[(?P<unit>mm)\]\s*:\s*(?P<value>.*?)\s*$",
    ),
    (
        "filament_grams",
        r";\s*(?P<total>total )filament weight \[g\]\s*:\s*(?P<value>.*?)\s*$",
    ),
    (
        "filament_mm",
        r";\s*(?P<total>total )filament used \[(?P<unit>mm)\]\s*=\s*(?P<value>.*?)\s*$",
    ),
    ("filament_grams", r";\s*(?P<total>total )filament used \[g\]\s*=\s*(?P<value>.*?)\s*$"),
    ("filament_mm", r";\s*filament used \[(?P<unit>mm)\]\s*=\s*(?P<value>.*?)\s*$"),
    ("filament_mm", r";\s*Filament used:\s*(?P<value>.*?)\s*(?P<unit>m)\s*$"),
    ("filament_grams", r";\s*filament used \[g\]\s*=\s*(?P<value>.*?)\s*$"),
    ("layer_count", r";\s*(?:total )?layer count\s*[:=]\s*(?P<value>[0-9]+)"),
    ("layer_count", r";\s*LAYER_COUNT:\s*(?P<value>[0-9]+)"),
    ("layer_count", r";\s*total layer number\s*:\s*(?P<value>[0-9]+)"),
    ("layer_height", r";\s*layer_height\s*=\s*(?P<value>[0-9.]+)"),
    ("layer_height", r";\s*Layer height:\s*(?P<value>[0-9.]+)"),
    ("slicer", r";\s*(?:generated by|Generated with)\s*(?P<value>.+)"),
    ("slicer", r";\s*(?P<value>BambuStudio\s+[0-9.]+)\s*$"),
)

_SUPPORT_TOOL = re.compile(r";\s*(?:TYPE|FEATURE):\s*(?P<type>.+)", re.IGNORECASE)

# Belegte Rollen der Orca-, Prusa- und Cura-Familie. Eine neue fremde Rolle
# wird nicht stillschweigend zu Modellmaterial erklärt.
_MODEL_ROLES = frozenset(
    {
        "outer wall",
        "inner wall",
        "sparse infill",
        "internal solid infill",
        "top surface",
        "bottom surface",
        "bridge",
        "internal bridge",
        "overhang wall",
        "gap infill",
        "floating vertical shell",
        "ironing",
        "perimeter",
        "external perimeter",
        "internal perimeter",
        "overhang perimeter",
        "internal infill",
        "solid infill",
        "top solid infill",
        "bridge infill",
        "internal bridge infill",
        "thin wall",
        "thin walls",
        "wall-inner",
        "wall-outer",
        "fill",
        "skin",
        "wall-overhang",
    }
)
_PURGE_ROLES = frozenset({"prime tower", "wipe tower", "purge", "flush"})
_ADHESION_ROLES = frozenset({"skirt", "brim", "skirt/brim", "raft"})
_MATERIAL_ROLES = ("model", "purge", "support", "adhesion", "unknown")
_FLUSH_MARK = re.compile(r"^;\s*FLUSH_(START|END)\s*$", re.IGNORECASE)


def _material_role(value: str) -> str:
    """Eine positive Zuordnung; unbekannte Kommentartexte bleiben unbekannt."""
    value = value.casefold().strip()
    if value in _MODEL_ROLES:
        return "model"
    if value in _PURGE_ROLES:
        return "purge"
    if "support" in value:
        return "support"
    if value in _ADHESION_ROLES:
        return "adhesion"
    return "unknown"


def _distinct_layer_heights(values: set[float]) -> list[float]:
    """Gleiche physische Höhe bei mehreren Objekten und doppelten Marken nur einmal."""
    distinct: list[float] = []
    for value in sorted(values):
        if not distinct or not math.isclose(value, distinct[-1], rel_tol=0.0, abs_tol=EPS_GEOM):
            distinct.append(value)
    return distinct


#: Eine Bewegung — ``G0`` fährt leer, ``G1`` gerade, ``G2``/``G3`` im Bogen.
#: Die Bogenformen stehen mit dabei, weil eine Kreiswand mit Bogenanpassung
#: **nur** aus ihnen besteht: Wer sie überliest, verliert genau die Ausmaße
#: eines Zylinders.
_COMMAND = re.compile(
    r"^(?P<family>[GMT])\s*(?P<code>[0-9]+)(?P<fraction>\.[0-9]+)?(?![0-9.])", re.IGNORECASE
)
_WORD = re.compile(
    r"(?P<name>[A-Z])(?P<value>[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))",
    re.IGNORECASE,
)

#: Wo die erste Schicht anfängt — und damit, wo das Modell anfängt. Cura und
#: die Orca-Familie schreiben ``;LAYER:0``, PrusaSlicer ``;LAYER_CHANGE``.
#:
#: **Davor gehört die Datei der Maschine.** Der ElegooSlicer fährt dort seine
#: Reinigungsbahn, und die liegt bei ``Y -1,2`` — 1,2 mm vor dem Bett, das er
#: selbst als ``printable_area = 0x0,…`` nennt. Das ist kein Fehler des
#: Slicers, sondern der Startcode seines Maschinenprofils, den Solidon nicht
#: kennt und nicht beurteilt (§29). Gemessen wird deshalb ab der ersten
#: Schicht. Fehlt die Marke, wird alles gemessen: eine Datei ohne Schichtmarke
#: hat auch keinen Startcode, den man abtrennen könnte.
_FIRST_LAYER = re.compile(r"^;\s*(?:LAYER\s*:\s*0\b|LAYER_CHANGE\b|CHANGE_LAYER\b)", re.IGNORECASE)

#: Wie ein Slicer sein eigenes Bett in die Datei schreibt: Ecken als ``XxY``.
#: ``printable_area`` ist der Name der Orca-Familie, ``bed_shape`` der von
#: PrusaSlicer — die Orca-Familie schreibt beide.
_BED_SHAPE = re.compile(
    r";\s*(?:printable_area|bed_shape)\s*=\s*(?P<corners>[-0-9.x,\s]+)", re.IGNORECASE
)
#: Und die Höhe dazu, unter zwei Namen.
_BED_HEIGHT = re.compile(
    r";\s*(?:printable_height|max_print_height)\s*=\s*(?P<height>[0-9.]+)", re.IGNORECASE
)
_WARNING = re.compile(r";\s*(?:WARNING|Warnung)[:\s]\s*(?P<text>.+)", re.IGNORECASE)

#: Die Marke, mit der PrusaSlicer jeden Schichtwechsel ankündigt. Gezählt ist
#: sie die Schichtzahl, die er sonst nirgends nennt.
_LAYER_CHANGE = re.compile(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER)\s*$", re.IGNORECASE)
#: Jede Schichtmarke der drei Familien. Die Orca-Familie schreibt mit manchen
#: Druckern zwei je Schicht (``;LAYER_CHANGE`` und ``;LAYER:n`` aus dem
#: Druckerprofil); gezählt wird deshalb erst die erste Bahn nach einer Marke.
_LAYER_MARK = re.compile(
    r"^;\s*(?:LAYER\s*:\s*-?[0-9]+|LAYER_CHANGE|CHANGE_LAYER)\s*$", re.IGNORECASE
)
_TIME_ELAPSED = re.compile(r";\s*TIME_ELAPSED:\s*([0-9.]+)", re.IGNORECASE)
_SETTING_LINE = re.compile(r"^;\s*(?P<key>[a-z_0-9]+)\s*=\s*(?P<value>.*?)\s*$", re.IGNORECASE)
_MATERIAL_LINE = re.compile(
    r"^;\s*(?P<key>filament_diameter|filament_density|material_diameter|material_density)"
    r"\s*[:=]\s*(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
_FLAVOR = re.compile(r"^;\s*FLAVOR\s*:\s*(?P<value>.*?)\s*$", re.IGNORECASE)
#: Der Name der Maschine, wie CuraEngine ihn aus ``machine_name`` in den Kopf
#: schreibt (``;TARGET_MACHINE.NAME:SV06``).
_TARGET_MACHINE = re.compile(r"^;\s*TARGET_MACHINE\.NAME\s*:\s*(?P<value>.*?)\s*$", re.IGNORECASE)
#: So viele Befehle vor der ersten Schicht behält die Auswertung
#: (:attr:`GcodeAnalysis.start`). Bambu Studios Startcode ist mit rund 300
#: Zeilen der längste der Heimdrucker; die Grenze hält eine fremde Datei ohne
#: Schichtmarke davon ab, sich ganz in den Speicher zu schreiben.
START_COMMANDS: Final = 2000
_BAMBU_GENERATOR = re.compile(r"^;\s*(?:generated by\s+)?BambuStudio\b", re.IGNORECASE)
_BAMBU_FILAMENTS = re.compile(r"^;\s*filament\s*:\s*(?P<ids>[0-9,\s]+)$", re.IGNORECASE)


def _invalid_tool_number() -> ValidationError:
    """Ein verständlicher Fehler auch vor der Umwandlung sehr großer Zahlen."""
    return ValidationError(
        field="gcode.tool",
        detail=_("Die Werkzeugnummer ist ungültig oder für diese Auswertung zu groß."),
        suggestions=(CHECK_SLICER_PROFILE,),
    )


def _tool_number(value: int | float | str, *, one_based: bool = False) -> int:
    """Begrenzt Werkzeuglisten vor jeder Allokation aus einer fremden Datei."""
    if isinstance(value, str):
        text = value.strip().lstrip("0") or "0"
        if not text.isdigit() or len(text) > len(str(MAX_GCODE_TOOLS)):
            raise _invalid_tool_number()
        value = int(text)
    if one_based:
        value -= 1
    if (
        isinstance(value, float) and (not math.isfinite(value) or not value.is_integer())
    ) or not 0 <= value < MAX_GCODE_TOOLS:
        raise _invalid_tool_number()
    return int(value)


def _bambu_tool_numbers(value: str) -> tuple[int, ...]:
    """Liest die einsbasierten Filamentkennungen, bevor Ergebnislisten entstehen."""
    parts = value.split(",", MAX_GCODE_TOOLS)
    if len(parts) > MAX_GCODE_TOOLS or any(not part.strip().isdigit() for part in parts):
        raise _invalid_tool_number()
    ids = tuple(_tool_number(part, one_based=True) for part in parts)
    if len(set(ids)) != len(ids):
        raise ValidationError(
            field="gcode.tool",
            detail=_("Die Filamentliste nennt ein Werkzeug mehrfach. Prüfen Sie die Slicer-Datei."),
            suggestions=(CHECK_SLICER_PROFILE,),
        )
    return ids


def _bambu_amounts(
    metrics: GcodeMetrics,
    pattern_values: dict[int, tuple[str, str, bool]],
    tools: tuple[int, ...],
) -> None:
    """Ordnet komprimierte Bambu-Kopfwerte den ausdrücklich genannten Filamenten zu."""
    assigned: set[str] = set()
    for index, (name, _pattern) in enumerate(_PATTERNS):
        if name not in ("filament_mm", "filament_grams") or name in assigned:
            continue
        captured = pattern_values.get(index)
        if captured is None or not captured[2]:
            continue
        amounts = _filament_amounts(captured[0], captured[1])
        if len(amounts) != len(tools):
            continue
        ordered: list[float | None] = [0.0] * (max(tools) + 1)
        for tool, amount in zip(tools, amounts, strict=True):
            ordered[tool] = amount
        setattr(metrics, f"{name}_by_tool", tuple(ordered))
        assigned.add(name)


def analyze(
    text: str,
    *,
    cancelled: CancelToken | None = None,
    densities: Sequence[float | None] = (),
    diameters: Sequence[float | None] = (),
    firmware: str | None = None,
    path_check: Callable[[GcodePath], bool] | None = None,
) -> GcodeAnalysis:
    """Liest einen bereits vorliegenden Text ohne weitere Zeilenkopie."""
    return analyze_lines(
        StringIO(text),
        cancelled=cancelled,
        densities=densities,
        diameters=diameters,
        firmware=firmware,
        path_check=path_check,
    )


def analyze_lines(
    lines: Iterable[str],
    *,
    cancelled: CancelToken | None = None,
    densities: Sequence[float | None] = (),
    diameters: Sequence[float | None] = (),
    firmware: str | None = None,
    path_check: Callable[[GcodePath], bool] | None = None,
) -> GcodeAnalysis:
    """Liest eine Druckdatei zeilenweise, speicherbegrenzt und abbrechbar."""
    metrics = GcodeMetrics()
    warnings: list[str] = []
    pattern_values: dict[int, tuple[str, str, bool]] = {}
    settings: dict[str, str] = {}
    corners: list[tuple[float, float]] | None = None
    bed_invalid = False
    bed_height: float | None = None
    last_elapsed: float | None = None
    layer_changes = 0
    stated_material: dict[str, tuple[float | None, ...]] = {}
    volumetric = False
    commanded_diameters: dict[int, float] = {}

    position: list[float | None] = [None, None, None]
    axes_absolute = True
    arc_centres_absolute = False
    independent = _ExtrusionState()
    marlin = _ExtrusionState()
    extrusion_states = (independent, marlin)
    active_tool = 0
    tool_selected = False
    bambu_commands = False
    bambu_tools: tuple[int, ...] = ()
    active_support = False
    active_role = "unknown"
    flushing = False
    custom_role = False
    macro_purge_lengths: dict[float, float] = {}
    conditional_depth = 0
    restoring_filament = False
    role_tool_uncertain = False
    role_volume_mode_uncertain = False
    seen_type = False
    has_first_layer = False
    after_first_layer = False
    # Bauteillüfter als Anteil, die Schicht der letzten Bahn, und ob seitdem
    # eine Schichtmarke kam.
    part_fan = 0.0
    printed_layer = 0
    start_commands: list[str] = []
    layer_pending = False
    fan_start: tuple[int, float] | None = None

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    for line in lines:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        stripped = line.strip()
        first_layer = _FIRST_LAYER.match(stripped) is not None
        if first_layer:
            has_first_layer = True
            after_first_layer = True

        if stripped.startswith(";"):
            bambu_commands = bambu_commands or _BAMBU_GENERATOR.match(stripped) is not None
            filament_ids = _BAMBU_FILAMENTS.match(stripped)
            if bambu_commands and filament_ids is not None:
                bambu_tools = _bambu_tool_numbers(filament_ids["ids"])
                if len(bambu_tools) == 1 and not tool_selected:
                    # Ein ausdrücklicher Ein-Filament-Kopf belegt auch den
                    # Rückzug vor dem ersten T-Befehl im A1-Startcode.
                    active_tool = bambu_tools[0]
            for index, (_name, pattern) in enumerate(_PATTERNS):
                if index in pattern_values:
                    continue
                found = re.search(pattern, stripped, re.IGNORECASE)
                if found is not None:
                    pattern_values[index] = (
                        found.group("value").strip(),
                        found.groupdict().get("unit") or "",
                        bool(found.groupdict().get("total")),
                    )
            found_warning = _WARNING.match(stripped)
            if found_warning is not None:
                warnings.append(found_warning.group("text").strip())
            elapsed = _TIME_ELAPSED.search(stripped)
            if elapsed is not None:
                # ``1.2.3`` und ``.`` kommen durch das Muster. Ein fremder
                # Dialekt darf den Lauf nicht abreißen — die Zeile steht nach
                # dem gelungenen Slicen, und die Druckdatei läge dann in einem
                # Arbeitsordner, der gleich gelöscht wird.
                seconds = _number(elapsed.group(1))
                if seconds is not None and math.isfinite(seconds):
                    last_elapsed = seconds
            if _LAYER_CHANGE.fullmatch(stripped):
                layer_changes += 1
            if _LAYER_MARK.match(stripped):
                layer_pending = True
                for state in extrusion_states:
                    state.model_layer_pending = True
                    state.support_layer_pending = True
            setting = _SETTING_LINE.match(stripped)
            if setting is not None:
                settings.setdefault(setting.group("key").casefold(), setting.group("value"))
            material = _MATERIAL_LINE.match(stripped)
            if material is not None:
                key = material.group("key").casefold()
                settings.setdefault(key, material.group("value"))
                key = key.replace("material_", "filament_")
                stated_material.setdefault(key, _filament_amounts(material.group("value"), ""))
            flavor = _FLAVOR.match(stripped)
            if flavor is not None:
                settings.setdefault("gcode_flavor", flavor.group("value"))
            machine = _TARGET_MACHINE.match(stripped)
            if machine is not None:
                settings.setdefault("machine_name", machine.group("value"))
            kind = _SUPPORT_TOOL.match(stripped)
            if kind is not None:
                seen_type = True
                active_support = "support" in kind.group("type").casefold()
                active_role = _material_role(kind.group("type"))
                custom_role = kind.group("type").strip().casefold() == "custom"
                if active_role == "model":
                    for state in extrusion_states:
                        state.seen_model_role = True
            flush = _FLUSH_MARK.fullmatch(stripped)
            if flush is not None:
                flushing = flush[1].casefold() == "start"
            shape = _BED_SHAPE.match(stripped)
            if shape is not None and corners is None and not bed_invalid:
                corners, bed_invalid = _bed_corners(shape.group("corners"))
            tall = _BED_HEIGHT.match(stripped)
            if tall is not None and bed_height is None:
                bed_height = _number(tall.group("height"))
            continue

        command_text = stripped.split(";", 1)[0].strip()
        if not has_first_layer and command_text and len(start_commands) < START_COMMANDS:
            start_commands.append(command_text)
        command = _COMMAND.match(command_text)
        if command is None:
            continue
        family = command.group("family").upper()
        if family == "T" and len(command.group("code").lstrip("0")) > len(str(MAX_GCODE_TOOLS)):
            raise _invalid_tool_number()
        code = int(command.group("code").lstrip("0") or "0")
        fraction = command.group("fraction")
        if fraction is not None and any(digit != "0" for digit in fraction[1:]):
            # G90.1/G91.1 steuern den Mittelpunkt von Bögen. Sie zu G90/G91
            # abzuschneiden würde stattdessen den XYZ-Modus umschalten.
            fractional_command = fraction.rstrip("0")
            if family == "G" and code in (90, 91) and fractional_command == ".1":
                arc_centres_absolute = code == 90
            continue
        words = {
            found.group("name").upper(): float(found.group("value"))
            for found in _WORD.finditer(command_text)
        }
        if bambu_commands and family == "M" and code in (622, 623):
            conditional_depth = (
                conditional_depth + 1 if code == 622 else max(0, conditional_depth - 1)
            )
            continue
        if bambu_commands and family == "M" and code in (628, 629):
            # Wiederförderung nach dem Cutter-Rückzug: Eine noch aktive
            # Prime-tower-Rolle macht daraus keine belegte Spülmenge.
            restoring_filament = code == 628
            continue
        if family == "M" and code in (106, 107):
            # Der Bauteillüfter: ohne Nummer oder Nummer 0, bei Bambu Nummer 1
            # (2 und 3 sind dort Hilfs- und Bauraumlüfter). Marlins Skala geht
            # bis 255, ein ``M106`` ohne Wert heißt voll.
            fan = words.get("P", 0.0)
            if fan == 0.0 or (bambu_commands and fan == 1.0):
                speed = 0.0 if code == 107 else words.get("S", 255.0) / 255.0
                part_fan = min(max(speed, 0.0), 1.0)
            continue
        if family == "M" and code in (82, 83):
            for state in extrusion_states:
                state.absolute = code == 82
                state.role_mode_uncertain = conditional_depth > 0
            continue
        if family == "M" and code == 200:
            role_volume_mode_uncertain = conditional_depth > 0
            target_tool = _tool_number(words.get("T", active_tool))
            diameter = words.get("D")
            if diameter is not None:
                volumetric = diameter > 0.0
                if volumetric:
                    commanded_diameters[target_tool] = diameter
            # D0 schaltet auch zusammen mit S1 aus (Marlins M200-Vertrag).
            if "S" in words and (diameter is None or diameter > 0.0):
                volumetric = words["S"] > 0.0
            continue
        if family == "M" and code == 6211 and "L" in words and "T" in words:
            # CC2s eigenes Wechselmakro führt L Millimeter Spülfilament des
            # Zielwerkzeugs. Es verändert weder E-Modus noch E-Koordinate.
            # Die Herkunft kann erst im Profilblock am Dateiende stehen.
            # Die bestehende Gesamtverbrauchsbuchung bleibt davon unberührt.
            macro_tool = words["T"]
            amount = words["L"]
            if math.isfinite(amount) and amount > 0.0:
                macro_purge_lengths[macro_tool] = macro_purge_lengths.get(macro_tool, 0.0) + amount
            continue
        if family == "M" and code in (620, 621):
            bambu_commands = True
            continue
        if family == "T":
            if bambu_commands and code in _BAMBU_SPECIAL_TOOLS:
                continue
            active_tool = _tool_number(code)
            role_tool_uncertain = conditional_depth > 0
            tool_selected = True
            continue
        if family != "G":
            continue
        if code in (90, 91):
            axes_absolute = code == 90
            marlin.absolute = axes_absolute
            marlin.role_mode_uncertain = conditional_depth > 0
            continue
        if code == 92:
            for axis, name in enumerate("XYZ"):
                if name in words:
                    position[axis] = words[name]
            if "E" in words:
                for state in extrusion_states:
                    state.position = words["E"]
                    state.role_position_uncertain = conditional_depth > 0
            continue
        if code not in (0, 1, 2, 3):
            continue

        start = (position[0], position[1], position[2])
        endpoint = position.copy()
        for axis, name in enumerate("XYZ"):
            if name not in words:
                continue
            if axes_absolute:
                endpoint[axis] = words[name]
            elif (current := position[axis]) is not None:
                endpoint[axis] = current + words[name]
            else:
                endpoint[axis] = None
        position = endpoint

        steps = [state.step(words["E"]) for state in extrusion_states] if "E" in words else []
        if not steps:
            continue
        diameter = (
            commanded_diameters.get(active_tool)
            or _at(stated_material.get("filament_diameter", ()), active_tool)
            or _at(diameters, active_tool)
        )
        area = _filament_area(diameter)
        consumed = []
        # Material fließt auch ohne XY-Weg und bei G0. Erst die Prüfung der
        # Druckbahnen darunter schließt Reinigung und Leerfahrten aus.
        for state, step in zip(extrusion_states, steps, strict=True):
            if conditional_depth:
                state.role_position_uncertain = True
                if step < 0.0 or state.retracted.get(active_tool, (0.0, False))[0] > 0.0:
                    state.role_debt_uncertain = True
            amount = state.consume(active_tool, step, volumetric=volumetric, area=area)
            consumed.append(amount)
            if step > 0.0:
                state.used_tools.add(active_tool)
            if volumetric:
                state.volumes[active_tool] = state.volumes.get(active_tool, 0.0) + amount
                if area is None:
                    state.unknown_volume_lengths[active_tool] = (
                        state.unknown_volume_lengths.get(active_tool, 0.0) + amount
                    )
                else:
                    state.lengths[active_tool] = state.lengths.get(active_tool, 0.0) + amount / area
            else:
                state.lengths[active_tool] = state.lengths.get(active_tool, 0.0) + amount
                state.linear_lengths[active_tool] = (
                    state.linear_lengths.get(active_tool, 0.0) + amount
                )
        travelled = code in (2, 3) or any(
            name in words
            and (
                position_before is None
                or position_after is None
                or not math.isclose(position_before, position_after)
            )
            for name, position_before, position_after in zip("XY", start, endpoint, strict=False)
        )
        role = "unknown" if restoring_filament else "purge" if flushing else active_role
        # Eine stationäre Nachförderung ist keine Modellbahn. Ohne ausdrückliche
        # Spülmarkierung bleibt sie unbekannt, statt Material hinzuzuerfinden.
        if role == "model" and not travelled:
            role = "unknown"
        for state, amount in zip(extrusion_states, consumed, strict=True):
            # Der gelesene Zweig kann rechnerisch null liefern, während der
            # andere Zweig fördert. Unsicherheit gilt deshalb vor der Menge.
            if (
                conditional_depth
                or (state.absolute and state.role_position_uncertain)
                or state.role_debt_uncertain
                or state.role_mode_uncertain
                or role_tool_uncertain
                or role_volume_mode_uncertain
            ):
                state.uncertain_roles.add(role)
                if role == "model":
                    state.model_complete = False
                elif role == "support":
                    state.support_heights_known = False
            if amount <= 0.0:
                continue
            state.classify(role, active_tool, amount, volumetric=volumetric)
            if role == "model" and travelled:
                if state.model_layer_pending:
                    if endpoint[2] is not None:
                        state.model_heights.add(endpoint[2])
                    else:
                        state.model_heights_known = False
                    state.model_layer_pending = False
            elif role == "support" and travelled:
                if state.support_layer_pending:
                    if endpoint[2] is not None:
                        state.support_heights.add(endpoint[2])
                    else:
                        state.support_heights_known = False
                    state.support_layer_pending = False
            elif role == "unknown" and travelled and not custom_role:
                if after_first_layer:
                    state.model_complete = False
                else:
                    # Erst am Dateiende steht fest, ob eine spätere erste
                    # Schicht diese unbekannte Bahn als Startcode abtrennt.
                    state.unmarked_unknown_motion = True
        if code == 0 or not travelled:
            continue
        end = (endpoint[0], endpoint[1], endpoint[2])
        points = _path_points(
            code,
            start,
            end,
            words,
            arc_centres_absolute=arc_centres_absolute,
        )
        inside = True
        if path_check is not None and any(step > 0.0 for step in steps):
            centre = None
            sx, sy = start[:2]
            ex, ey = end[:2]
            if (
                code in (2, 3)
                and sx is not None
                and sy is not None
                and ex is not None
                and ey is not None
            ):
                centre = _arc_center(
                    (sx, sy),
                    (ex, ey),
                    words,
                    clockwise=code == 2,
                    centres_absolute=arc_centres_absolute,
                )
            inside = path_check(GcodePath(start, end, centre, code == 2))
        for state, step, amount in zip(extrusion_states, steps, consumed, strict=True):
            if step <= 0.0:
                continue
            if active_support:
                support_amounts = state.support_volumes if volumetric else state.support
                support_amounts[active_tool] = support_amounts.get(active_tool, 0.0) + amount
            state.all_extent.add(*points)
            state.all_paths_inside = state.all_paths_inside and inside
            if after_first_layer:
                state.model_extent.add(*points)
                state.model_paths_inside = state.model_paths_inside and inside
        # Nur was beide Dialekte als Druckbahn lesen — ein Rückzug in dem
        # einen ist keine Bahn im anderen.
        if all(step > 0.0 for step in steps):
            if layer_pending:
                printed_layer += 1
                layer_pending = False
            if fan_start is None and part_fan > 0.0 and printed_layer >= 1:
                fan_start = (printed_layer, part_fan)

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    for index, (name, _pattern) in enumerate(_PATTERNS):
        if (
            name not in ("filament_mm", "filament_grams")
            and getattr(metrics, name) is not None
            and getattr(metrics, name) != ""
        ):
            continue
        captured = pattern_values.get(index)
        if captured is not None:
            _set(metrics, name, *captured)
    if last_elapsed is not None:
        metrics.print_seconds = last_elapsed
    if metrics.layer_count is None:
        metrics.layer_count = layer_changes or None
    dialect = settings.get("gcode_flavor", firmware or "").casefold().strip()
    state = marlin if dialect in ("marlin", "marlin2", "marlin(legacy)") else independent
    if state.unmarked_unknown_motion and not has_first_layer:
        state.model_complete = False
    used_tools = state.used_tools
    if bambu_tools:
        _bambu_amounts(metrics, pattern_values, bambu_tools)
    stated_totals = {
        _PATTERNS[index][0]
        for index, captured in pattern_values.items()
        if captured[2]
        and len(amounts := _filament_amounts(captured[0], captured[1])) == 1
        and amounts[0] is not None
    }
    # Eine Gesamtsumme allein beweist kein Werkzeug. Genau eine tatsächlich
    # benutzte Werkzeugnummer belegt die Zuordnung hingegen, auch wenn der
    # Slicer zusätzliche ungenutzte Materialprofile in die Datei schreibt.
    if len(used_tools) == 1:
        tool = next(iter(used_tools))
        for name in stated_totals:
            if not getattr(metrics, f"{name}_by_tool"):
                setattr(metrics, f"{name}_by_tool", (0.0,) * tool + (getattr(metrics, name),))
    metrics.filament_diameters = _material_values(
        stated_material.get("filament_diameter", ()), diameters
    )
    if commanded_diameters:
        metrics.filament_diameters = _material_values(
            tuple(commanded_diameters.get(tool) for tool in range(max(commanded_diameters) + 1)),
            metrics.filament_diameters,
        )
    metrics.filament_densities = _material_values(
        stated_material.get("filament_density", ()), densities
    )
    if seen_type:
        volumes = tuple(
            _volume(length, _at(metrics.filament_diameters, tool))
            for tool, length in state.support.items()
        )
        support_cm3 = _complete_sum(volumes) if volumes else 0.0
        if support_cm3 is not None:
            support_cm3 += sum(state.support_volumes.values()) / 1000.0
        if state.unknown_amounts.intersection(state.support.keys() | state.support_volumes.keys()):
            support_cm3 = None
        metrics.support_mm3 = support_cm3 * 1000.0 if support_cm3 is not None else None
    motion_lengths: dict[int, float | None] = dict(state.lengths)
    for tool, volume in state.unknown_volume_lengths.items():
        area = _filament_area(_at(metrics.filament_diameters, tool))
        motion_lengths[tool] = (
            state.lengths.get(tool, 0.0) + volume / area if area is not None else None
        )
    for tool in state.unknown_amounts:
        motion_lengths[tool] = None
    _motion_fallback(
        metrics,
        motion_lengths,
        cura_placeholder=any(captured[1].casefold() == "m" for captured in pattern_values.values()),
    )
    if state.volumes:
        tool_volumes: list[float | None] = []
        for tool, length in enumerate(metrics.filament_mm_by_tool):
            if metrics.filament_mm_sources[tool] == "header":
                volume_cm3 = _volume(length, _at(metrics.filament_diameters, tool))
            elif tool in state.unknown_amounts:
                volume_cm3 = None
            else:
                volume_cm3 = _volume(
                    max(state.linear_lengths.get(tool, 0.0), 0.0),
                    _at(metrics.filament_diameters, tool),
                )
                if volume_cm3 is not None:
                    volume_cm3 += max(state.volumes.get(tool, 0.0), 0.0) / 1000.0
            tool_volumes.append(volume_cm3)
        metrics.filament_cm3_by_tool = tuple(tool_volumes)
    cc2_profile = any(
        "centauri carbon 2" in settings.get(key, "").casefold().replace("-", " ").replace("_", " ")
        for key in ("printer_model", "printer_settings_id")
    )
    if "elegoo" in metrics.slicer.casefold() or cc2_profile:
        for raw_tool, macro_length in macro_purge_lengths.items():
            state.classify("purge", _tool_number(raw_tool), macro_length, volumetric=False)
    role_tools = set(used_tools)
    for role_amounts in (*state.role_lengths.values(), *state.role_volumes.values()):
        role_tools.update(role_amounts)
    count = max(role_tools, default=-1) + 1
    for role in _MATERIAL_ROLES:
        values: list[float | None] = []
        for tool in range(count):
            length = state.role_lengths.get(role, {}).get(tool, 0.0)
            volume = state.role_volumes.get(role, {}).get(tool, 0.0)
            role_volume = (
                _volume(length, _at(metrics.filament_diameters, tool)) if length > 0.0 else 0.0
            )
            if role_volume is not None:
                role_volume += volume / 1000.0
            if tool in state.unknown_amounts and (length > 0.0 or volume > 0.0):
                role_volume = None
            values.append(role_volume)
        metrics.material_cm3_by_role[role] = tuple(values)
    if state.seen_model_role and state.model_complete:
        metrics.model_material_cm3 = _complete_sum(metrics.material_cm3_by_role["model"])
        model_heights = _distinct_layer_heights(state.model_heights)
        support_heights = _distinct_layer_heights(state.support_heights)
        metrics.model_layer_count = (
            len(model_heights) if has_first_layer and state.model_heights_known else None
        )
        if has_first_layer and state.model_heights_known and state.support_heights_known:
            model_index = 0
            support_only = 0
            for height in support_heights:
                while (
                    model_index < len(model_heights)
                    and model_heights[model_index] < height - EPS_GEOM
                ):
                    model_index += 1
                if model_index >= len(model_heights) or not math.isclose(
                    model_heights[model_index], height, rel_tol=0.0, abs_tol=EPS_GEOM
                ):
                    support_only += 1
            metrics.support_only_layer_count = support_only
    metrics.purge_material_cm3 = _complete_sum(metrics.material_cm3_by_role["purge"])
    metrics.unclassified_material_cm3 = _complete_sum(metrics.material_cm3_by_role["unknown"])
    metrics.uncertain_material_roles = tuple(sorted(state.uncertain_roles))
    role_total = _complete_sum(
        tuple(value for values in metrics.material_cm3_by_role.values() for value in values)
    )
    total_volume = metrics.material_cm3
    metrics.purge_material_complete = (
        metrics.purge_material_cm3 is not None
        and metrics.unclassified_material_cm3 is not None
        and metrics.unclassified_material_cm3 <= 0.0
        and not state.uncertain_roles
        and role_total is not None
        and total_volume is not None
        and math.isclose(role_total, total_volume, rel_tol=EPS_SETTING, abs_tol=0.0)
    )
    metrics.warnings = tuple(warnings)
    metrics.used_tools = tuple(sorted(used_tools))
    stated_weight_total = "filament_grams" in stated_totals
    # Eine Summe aus einer unvollständigen Werkzeugliste ist keine vollständige
    # Gewichtsangabe. Eine ausdrücklich genannte Gesamtsumme bleibt maßgeblich.
    if metrics.filament_grams_by_tool and not stated_weight_total:
        referenced = used_tools | {
            tool
            for tool, length in enumerate(metrics.filament_mm_by_tool)
            if length is None or length > 0.0
        }
        if any(
            tool >= len(metrics.filament_grams_by_tool)
            or metrics.filament_grams_by_tool[tool] is None
            for tool in referenced
        ):
            metrics.filament_grams = None
    bed = None if bed_invalid else _bed_box(corners, bed_height)
    extent = state.model_extent.box() if has_first_layer else state.all_extent.box()
    does_extrude = extent is not None
    _log.info("read g-code of %s", metrics.slicer or "unknown slicer")
    excluded_areas = []
    for value in settings.get("bed_exclude_area", "").split(";"):
        if value.strip():
            excluded, invalid = _bed_corners(value)
            if excluded and not invalid:
                excluded_areas.append(tuple(excluded))
    return GcodeAnalysis(
        metrics,
        does_extrude,
        extent,
        bed,
        settings,
        tuple(corners or ()) if not bed_invalid else (),
        tuple(excluded_areas),
        (state.model_paths_inside if has_first_layer else state.all_paths_inside)
        if path_check is not None
        else None,
        dialect,
        fan_start=fan_start,
        start=tuple(start_commands),
    )


def _material_values(
    stated: Sequence[float | None], supplied: Sequence[float | None]
) -> tuple[float | None, ...]:
    """Belegte Dateieigenschaften gewinnen; der Aufrufer füllt nur Fehlstellen."""
    result = []
    for tool in range(max(len(stated), len(supplied))):
        valid = None
        for candidate in (_at(stated, tool), _at(supplied, tool)):
            if candidate is not None and math.isfinite(candidate) and candidate > 0.0:
                valid = candidate
                break
        result.append(valid)
    return tuple(result)


def _motion_fallback(
    metrics: GcodeMetrics, lengths: dict[int, float | None], *, cura_placeholder: bool
) -> None:
    """Ergänzt Werkzeugmengen aus Bewegungen und verwirft Curas Vorlagenull."""
    amounts = list(metrics.filament_mm_by_tool)
    sources: list[str | None] = ["header" if value is not None else None for value in amounts]
    placeholder = (
        cura_placeholder
        and amounts
        and all(value is not None and value <= 0.0 for value in amounts)
    )
    replaced_placeholder = False
    if lengths:
        count = max(len(amounts), max(lengths) + 1)
        amounts.extend([None] * (count - len(amounts)))
        sources.extend([None] * (count - len(sources)))
        for tool in range(count):
            raw_motion = lengths.get(tool, 0.0)
            motion = max(raw_motion, 0.0) if raw_motion is not None else None
            replace_zero = placeholder and tool in lengths and (motion is None or motion > 0.0)
            if amounts[tool] is None or replace_zero:
                amounts[tool] = motion
                sources[tool] = "motion"
                replaced_placeholder = replaced_placeholder or bool(replace_zero)
    metrics.filament_mm_by_tool = tuple(amounts)
    metrics.filament_mm_sources = tuple(sources)
    total = _complete_sum(amounts)
    if metrics.filament_mm is None or replaced_placeholder:
        metrics.filament_mm = total


def _path_points(
    code: int,
    start: tuple[float | None, float | None, float | None],
    end: tuple[float | None, float | None, float | None],
    words: dict[str, float],
    *,
    arc_centres_absolute: bool = False,
) -> tuple[tuple[float | None, float | None, float | None], ...]:
    """Stützpunkte einer Materialbahn einschließlich der Bogenextrema."""
    points: list[tuple[float | None, float | None, float | None]] = [start, end]
    if code not in (2, 3):
        return tuple(points)
    sx, sy = start[:2]
    ex, ey = end[:2]
    if sx is None or sy is None or ex is None or ey is None:
        return tuple(points)
    center = _arc_center(
        (sx, sy),
        (ex, ey),
        words,
        clockwise=code == 2,
        centres_absolute=arc_centres_absolute,
    )
    if center is None:
        return tuple(points)
    cx, cy = center
    radius = math.hypot(sx - cx, sy - cy)
    if not math.isfinite(radius) or radius <= 0.0:
        return tuple(points)
    start_angle = math.atan2(sy - cy, sx - cx)
    end_angle = math.atan2(ey - cy, ex - cx)
    full = math.isclose(sx, ex) and math.isclose(sy, ey)
    sweep = _arc_sweep(start_angle, end_angle, clockwise=code == 2, full=full)
    for angle in (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
        delta = _arc_sweep(start_angle, angle, clockwise=code == 2, full=False)
        if delta < sweep or math.isclose(delta, sweep):
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle), None))
    return tuple(points)


def _arc_center(
    start: tuple[float, float],
    end: tuple[float, float],
    words: dict[str, float],
    *,
    clockwise: bool,
    centres_absolute: bool = False,
) -> tuple[float, float] | None:
    """Mittelpunkt eines Bogens aus I/J oder R; I/J hat nach G-Code Vorrang."""
    sx, sy = start
    ex, ey = end
    if "I" in words or "J" in words:
        if centres_absolute:
            return words.get("I", sx), words.get("J", sy)
        return sx + words.get("I", 0.0), sy + words.get("J", 0.0)
    stated_radius = words.get("R")
    if stated_radius is None:
        return None
    dx, dy = ex - sx, ey - sy
    chord = math.hypot(dx, dy)
    radius = abs(stated_radius)
    if chord <= 0.0 or radius < chord / 2.0:
        return None
    midpoint = ((sx + ex) / 2.0, (sy + ey) / 2.0)
    offset = math.sqrt(max(radius * radius - chord * chord / 4.0, 0.0))
    normal = (-dy / chord, dx / chord)
    candidates = (
        (midpoint[0] + normal[0] * offset, midpoint[1] + normal[1] * offset),
        (midpoint[0] - normal[0] * offset, midpoint[1] - normal[1] * offset),
    )
    want_major = stated_radius < 0.0

    def matches_radius_sign(center: tuple[float, float]) -> bool:
        start_angle = math.atan2(sy - center[1], sx - center[0])
        end_angle = math.atan2(ey - center[1], ex - center[0])
        sweep = _arc_sweep(start_angle, end_angle, clockwise=clockwise, full=False)
        is_major = sweep > math.pi and not math.isclose(sweep, math.pi)
        return is_major == want_major

    return next((center for center in candidates if matches_radius_sign(center)), candidates[0])


def _arc_sweep(start: float, end: float, *, clockwise: bool, full: bool) -> float:
    """Positiver Winkelweg vom Anfang zum Ende in der gewählten Richtung."""
    if full:
        return math.tau
    return (start - end) % math.tau if clockwise else (end - start) % math.tau


def _bed_corners(value: str) -> tuple[list[tuple[float, float]] | None, bool]:
    """Liest die Eckliste einer Bettangabe und weist beschädigte Angaben aus."""
    corners: list[tuple[float, float]] = []
    for corner in value.split(","):
        parts = corner.strip().split("x")
        if len(parts) != 2:
            return None, True
        try:
            point = (float(parts[0]), float(parts[1]))
        except ValueError:
            return None, True
        if not all(math.isfinite(coordinate) for coordinate in point):
            return None, True
        corners.append(point)
    if len(corners) < 3:
        return None, True
    return corners, False


def _bed_box(corners: list[tuple[float, float]] | None, height: float | None) -> BoundingBox | None:
    """Bildet aus gültigen Bettangaben deren Hüllbox."""
    if not corners:
        return None
    xs = [corner[0] for corner in corners]
    ys = [corner[1] for corner in corners]
    return BoundingBox(
        (min(xs), min(ys), 0.0),
        (max(xs), max(ys), height if height is not None else float("inf")),
    )


def _set(
    metrics: GcodeMetrics, name: str, value: str, unit: str = "", is_total: bool = False
) -> None:
    number: float | None
    if name == "slicer":
        metrics.slicer = value
        return
    if name in ("print_seconds", "model_print_seconds"):
        setattr(metrics, name, _seconds(value))
        return
    if name in ("filament_mm", "filament_grams"):
        # Die Kommas trennen Extruder, keine Dezimalstellen. Eine explizite
        # Gesamtsumme steht im Musterregister vor den gerundeten Einzelwerten.
        amounts = _filament_amounts(value, unit)
        if not is_total and not getattr(metrics, f"{name}_by_tool"):
            setattr(metrics, f"{name}_by_tool", amounts)
        if (
            getattr(metrics, name) is not None
            or not amounts
            or (is_total and len(amounts) != 1)
            or any(amount is None for amount in amounts)
        ):
            return
        number = sum(amount for amount in amounts if amount is not None)
        if math.isfinite(number):
            setattr(metrics, name, number)
        return
    else:
        number = _number(value)
    if number is None:
        return
    if name == "layer_count":
        metrics.layer_count = int(number)
    elif name == "layer_height":
        metrics.layer_height = number


def _filament_amounts(value: str, unit: str) -> tuple[float | None, ...]:
    """Liest vollständige Zahlenwerte; unbekannte Plätze bleiben erhalten."""
    if not value.strip():
        return ()
    amounts: list[float | None] = []
    for part in value.split(","):
        token = part.strip()
        if unit.casefold() == "m":
            token = token.casefold().removesuffix("m").strip()
        number = _number(token)
        if number is not None and unit:
            number = _length_mm(number, unit)
        if number is not None and (not math.isfinite(number) or number < 0.0):
            number = None
        amounts.append(number)
    return tuple(amounts)


#: Was ein Slicer als Einheit einer Filamentlänge schreibt, in Millimetern.
_LENGTH_UNITS: dict[str, float] = {"mm": 1.0, "cm": 10.0, "m": 1000.0}

#: Unter dieser Zahl hält der Rückfall eine Länge ohne Einheit für Meter.
GUESSED_METRES_BELOW = 100.0


def _length_mm(value: float, unit: str) -> float:
    """Eine Filamentlänge in Millimetern — die Einheit kommt aus der Zeile.

    Hier stand ``number * 1000.0 if number < 100.0 else number``: „Filament
    used: 3.42m" sind Meter, „filament used [mm] = 3420" nicht — und
    unterschieden wurden die beiden an der **Größe** der Zahl. Ein kleines
    Teil mit 95 mm Faden wurde damit zu 95 Metern: 283 Gramm statt 0,3, dazu
    eine Abweichungswarnung, die Solidon sich selbst gestellt hat.

    Die Größe einer Zahl sagt nichts über ihre Einheit. Das Muster, das sie
    gefunden hat, sagt alles darüber — beide Zeilen nennen ihre Einheit, und
    beide geben sie als Gruppe ``unit`` weiter.

    Der Rückfall bleibt für ein Muster, das einmal ohne Einheit dazukommt. Er
    ist dann eine Vermutung und steht als solche hier, statt als Regel im
    Auswerter.
    """
    factor = _LENGTH_UNITS.get(unit.strip().lower())
    if factor is not None:
        return value * factor
    return value * 1000.0 if value < GUESSED_METRES_BELOW else value


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _seconds(value: str) -> float | None:
    """``2h 14m 3s``, ``14m``, oder nackte Sekunden — alles davon kommt vor."""
    plain = _number(value)
    if plain is not None:
        return plain
    total = 0.0
    found = False
    for amount, unit in re.findall(r"(\d+)\s*([dhms])", value.lower()):
        found = True
        total += float(amount) * {"d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0}[unit]
    return total if found else None


@dataclass(slots=True)
class CrossCheck:
    """Die interne Schätzung gegen den gemessenen Wert (§28.2)."""

    what: str
    estimated: float
    measured: float
    findings: list[Finding] = field(default_factory=list)

    @property
    def deviation(self) -> float:
        """Relativer Unterschied. Positiv heißt: die Schätzung lag zu niedrig."""
        if self.measured <= 0.0:
            return 0.0
        return (self.measured - self.estimated) / self.measured

    @property
    def within_limit(self) -> bool:
        return abs(self.deviation) <= DEVIATION_LIMIT


#: Wie die drei Größen der Gegenprobe heißen, wenn sie jemand liest. Im
#: Tooltip des Prüfberichts stand „Was: material" und „Was: time" — der
#: Schlüssel, mit dem der Code rechnet, in einem deutschen Fenster; und seit
#: gleiche Sätze zu einer Zeile werden, ist der Tooltip die einzige Stelle,
#: die Material von Zeit trennt.
QUANTITY_TITLES: Final[dict[str, TranslatableText]] = {
    "support": _("Stützen"),
    "material": _("Material"),
    "time": _("Zeit"),
}


def compare(estimated: float, measured: float, what: str = "support") -> CrossCheck:
    """Prüft eine Größe gegen. Ein großer Unterschied ist ein Befund, keine
    Korrektur.

    §28.2: die interne Schätzung wird nicht still durch den gemessenen Wert
    ersetzt. Beide bleiben, beide behalten ihre Herkunft, und der Bericht sagt,
    dass sie sich widersprechen — das ist das Signal, dass die Schichtanalyse
    Arbeit braucht.
    """
    check = CrossCheck(what=what, estimated=estimated, measured=measured)
    # Im Befund steht die lesbare Größe; ``check.what`` bleibt der Schlüssel.
    named: TranslatableText | str = QUANTITY_TITLES.get(what, what)
    if measured <= 0.0:
        # Eine Null ist keine Messung, und `deviation` gäbe für sie glatt
        # null zurück — die größtmögliche Abweichung sähe aus wie die
        # perfekte Übereinstimmung. „Nicht vergleichbar" ist die ehrliche
        # Antwort, und sie trägt ihre Herkunft (Regel 14).
        #
        # **Und die Herkunft ist hier ``internal``.** Der Befund entsteht beim
        # Lesen des G-Code und trug deshalb ``source="gcode"`` — nur ist die
        # einzige Zahl darin die **Schätzung**, und die Datei nennt keinen
        # Messwert; das ist ja der Anlass. So ausgezeichnet stand eine interne
        # Zahl als gemessene da, genau die Verwechslung, die §22.5 verbietet.
        check.findings.append(
            Finding(
                code="gcode.no_measurement",
                severity="info",
                message=_("Die Druckdatei nennt für diese Größe keinen Messwert."),
                values={"what": named, "estimated": round(estimated, 2)},
                source="internal",
            )
        )
        return check
    if not check.within_limit:
        check.findings.append(
            Finding(
                code="gcode.deviation",
                severity="warning",
                message=_("Die Gegenprobe aus dem G-Code weicht deutlich von der Schätzung ab."),
                values={
                    "what": named,
                    "estimated": round(estimated, 2),
                    "measured": round(measured, 2),
                    "deviation": f"{check.deviation:+.0%}",
                },
                source="gcode",
            )
        )
    return check


def combine(parts: Sequence[GcodeMetrics]) -> GcodeMetrics:
    """Die Kennzahlen mehrerer Druckplatten als eine Auskunft.

    Ein Auftrag, der auf zwei Platten passt, wird zweimal gedruckt — Zeit und
    Material addieren sich also, und wer wissen will, was der Satz kostet, will
    diese Summe sehen. Alle Werte kommen aus derselben Quelle (G-Code), Regel 14
    ist damit gewahrt: hier wird nichts mit einer Schätzung vermischt.

    **Fehlt ein Wert bei einer Platte, fehlt die Summe.** Die Alternative wäre,
    ihn als null zu behandeln — und dann stünde eine Gesamtzeit da, die zu kurz
    ist, ohne dass jemand es sehen kann. Das ist derselbe Grundsatz, mit dem
    :class:`GcodeMetrics` seine Felder optional führt.

    Die Schichtzahl wird **nicht** summiert. Sie beschreibt eine Platte; über
    zwei addiert ergäbe sie eine Zahl, die es nirgends gibt. Sie steht deshalb
    nur da, wo es eine Platte ist. Ebenso bleiben Werkzeugmengen bei ihrer
    Platte: Dieselbe Werkzeugnummer belegt keine gemeinsame Spule. Die
    zusammengefasste Auskunft führt deshalb keine Werkzeugmengen.
    """
    if not parts:
        return GcodeMetrics()
    if len(parts) == 1:
        return parts[0]

    def total(pick: Callable[[GcodeMetrics], float | None]) -> float | None:
        values = [pick(entry) for entry in parts]
        return (
            None
            if any(value is None for value in values)
            else sum(value or 0.0 for value in values)
        )

    heights = {entry.layer_height for entry in parts if entry.layer_height is not None}
    warnings: list[str] = []
    for entry in parts:
        warnings += [text for text in entry.warnings if text not in warnings]

    return GcodeMetrics(
        slicer=parts[0].slicer,
        print_seconds=total(lambda entry: entry.print_seconds),
        model_print_seconds=total(lambda entry: entry.model_print_seconds),
        model_material_cm3=total(lambda entry: entry.model_material_cm3),
        purge_material_cm3=total(lambda entry: entry.purge_material_cm3),
        unclassified_material_cm3=total(lambda entry: entry.unclassified_material_cm3),
        resolved_model_grams=total(lambda entry: entry.model_grams()),
        uncertain_material_roles=tuple(
            sorted({role for entry in parts for role in entry.uncertain_material_roles})
        ),
        purge_material_complete=all(entry.purge_material_complete for entry in parts),
        filament_mm=total(lambda entry: entry.filament_mm),
        filament_grams=total(lambda entry: entry.filament_grams),
        support_mm3=total(lambda entry: entry.support_mm3),
        layer_count=None,
        layer_height=heights.pop() if len(heights) == 1 else None,
        warnings=tuple(warnings),
        source="gcode",
        resolved_filament_grams=(total(lambda entry: entry.grams(None, None)),),
        resolved_material_cm3=total(lambda entry: entry.material_cm3),
    )


def findings_for(metrics: GcodeMetrics) -> list[Finding]:
    """Was die geslicete Datei sagt, als Einträge für den Prüfbericht — als
    gemessen markiert.
    """
    findings: list[Finding] = []
    if metrics.print_minutes is not None:
        findings.append(
            Finding(
                code="gcode.print_time",
                severity="info",
                message=_("Druckzeit aus dem G-Code."),
                values={"minutes": round(metrics.print_minutes, 1)},
                source="gcode",
            )
        )
    elif metrics.model_print_seconds is not None:
        findings.append(
            Finding(
                code="gcode.model_time",
                severity="info",
                message=_("Modellzeit aus dem G-Code."),
                values={"minutes": round(metrics.model_print_seconds / 60.0, 1)},
                source="gcode",
            )
        )
    if metrics.purge_material_cm3 is not None and metrics.purge_material_cm3 > 0.0:
        findings.append(
            Finding(
                code="gcode.purge",
                severity="info",
                message=_(
                    "Aus ausgewiesenen G-Code-Abschnitten gelesenes Spülmaterial: {volume} cm³.",
                    volume=round(metrics.purge_material_cm3, 2),
                )
                if metrics.purge_material_complete
                else _(
                    "Spülmaterial aus lesbaren G-Code-Abschnitten: {volume} cm³. "
                    "Die vollständige Menge ist unbekannt.",
                    volume=round(metrics.purge_material_cm3, 2),
                ),
                values={
                    "volume_cm3": metrics.purge_material_cm3,
                },
                source="gcode",
            )
        )
    grams = metrics.grams(None, None)
    if grams is not None:
        findings.append(
            Finding(
                code="gcode.material",
                severity="info",
                message=_("Materialverbrauch aus dem G-Code."),
                values={"grams": round(grams, 1)},
                source="gcode",
            )
        )
    for warning in metrics.warnings:
        findings.append(
            Finding(
                code="gcode.warning",
                severity="warning",
                message=_("Der Slicer hat gewarnt."),
                values={"text": warning},
                source="gcode",
                # Regel 17: Was der Slicer gesagt hat, steht in den Werten; der Knopf zeigt sie.
                suggestions=(SHOW_SLICER_OUTPUT,),
            )
        )
    return findings
