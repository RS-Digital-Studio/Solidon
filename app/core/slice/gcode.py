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
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from io import StringIO

from app.core.log import get_logger
from app.core.types import BoundingBox, CancelToken, Finding, MetricSource
from app.i18n import _

_log = get_logger(__name__)

#: Über diesem relativen Unterschied wird die Gegenprobe ein Befund (§28.2).
DEVIATION_LIMIT = 0.15

#: Dichte der üblichen Filamente in g/cm³ — für das Gewicht aus der Länge.
DEFAULT_DENSITY = 1.24

#: Querschnitt eines 1,75-mm-Filaments in mm².
FILAMENT_AREA = 2.405


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

    @property
    def print_minutes(self) -> float | None:
        return None if self.print_seconds is None else self.print_seconds / 60.0

    @property
    def material_cm3(self) -> float | None:
        """Filamentlänge als Volumen — die Größe, die mit der Schätzung
        vergleichbar ist.
        """
        if self.filament_mm is None:
            return None
        return self.filament_mm * FILAMENT_AREA / 1000.0

    def grams(self, density: float = DEFAULT_DENSITY) -> float | None:
        # Nur ein Gewicht über null ist eine Messung — dieselbe Absicherung,
        # die `filament_mm` seit dem Cura-Vorfall hat: dessen Kopf schreibt
        # die Werte, *bevor* gerechnet wird, und eine Null gälte sonst als
        # perfekte Übereinstimmung.
        if self.filament_grams is not None and self.filament_grams > 0.0:
            return self.filament_grams
        volume = self.material_cm3
        return None if volume is None else volume * density


@dataclass(slots=True)
class GcodeAnalysis:
    """Alle Aussagen aus genau einem Durchlauf durch eine Druckdatei."""

    metrics: GcodeMetrics
    extrudes: bool
    extent: BoundingBox | None
    bed: BoundingBox | None
    settings: dict[str, str]


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


#: Kommentarzeilen, die die verbreiteten Slicer schreiben. Ein Muster je
#: Tatsache, nicht ein Parser je Slicer: ein neuer Slicer braucht meist nur
#: eine weitere Zeile hier.
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("print_seconds", r";\s*estimated printing time.*?=\s*(?P<value>[0-9hmsd ]+)"),
    ("print_seconds", r";\s*TIME:\s*(?P<value>[0-9.]+)"),
    ("print_seconds", r";\s*total print time.*?:\s*(?P<value>[0-9hmsd ]+)"),
    ("filament_mm", r";\s*total filament used \[(?P<unit>mm)\]\s*=\s*(?P<value>[0-9.]+)"),
    ("filament_grams", r";\s*total filament used \[g\]\s*=\s*(?P<value>[0-9.]+)"),
    ("filament_mm", r";\s*filament used \[(?P<unit>mm)\]\s*=\s*(?P<value>[0-9., ]+)"),
    ("filament_mm", r";\s*Filament used:\s*(?P<value>[0-9.]+)\s*(?P<unit>m)\b"),
    ("filament_grams", r";\s*filament used \[g\]\s*=\s*(?P<value>[0-9., ]+)"),
    ("layer_count", r";\s*(?:total )?layer count\s*[:=]\s*(?P<value>[0-9]+)"),
    ("layer_count", r";\s*LAYER_COUNT:\s*(?P<value>[0-9]+)"),
    ("layer_height", r";\s*layer_height\s*=\s*(?P<value>[0-9.]+)"),
    ("layer_height", r";\s*Layer height:\s*(?P<value>[0-9.]+)"),
    ("slicer", r";\s*(?:generated by|Generated with)\s*(?P<value>.+)"),
)

_SUPPORT_TOOL = re.compile(r";\s*TYPE:\s*(?P<type>.+)", re.IGNORECASE)

#: Eine Bewegung — ``G0`` fährt leer, ``G1`` gerade, ``G2``/``G3`` im Bogen.
#: Die Bogenformen stehen mit dabei, weil eine Kreiswand mit Bogenanpassung
#: **nur** aus ihnen besteht: Wer sie überliest, verliert genau die Ausmaße
#: eines Zylinders.
_COMMAND = re.compile(
    r"^(?P<family>[GMT])\s*(?P<code>[0-9]+)(?P<fraction>\.[0-9]+)?\b", re.IGNORECASE
)
_WORD = re.compile(
    r"(?P<name>[A-Z])(?P<value>[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:E[-+]?[0-9]+)?)",
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
_FIRST_LAYER = re.compile(r"^;\s*(?:LAYER\s*:\s*0\b|LAYER_CHANGE\b)", re.IGNORECASE)

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
_LAYER_CHANGE = re.compile(r"^;\s*LAYER_CHANGE\s*$", re.IGNORECASE)
_TIME_ELAPSED = re.compile(r";\s*TIME_ELAPSED:\s*([0-9.]+)", re.IGNORECASE)
_SETTING_LINE = re.compile(r"^;\s*(?P<key>[a-z_0-9]+)\s*=\s*(?P<value>.*?)\s*$", re.IGNORECASE)


def parse(text: str) -> GcodeMetrics:
    """Liest eine G-Code-Datei. Was nicht darin steht, bleibt unbekannt."""
    return analyze(text).metrics


def analyze(text: str, *, cancelled: CancelToken | None = None) -> GcodeAnalysis:
    """Liest einen bereits vorliegenden Text ohne weitere Zeilenkopie."""
    return analyze_lines(StringIO(text), cancelled=cancelled)


def analyze_lines(lines: Iterable[str], *, cancelled: CancelToken | None = None) -> GcodeAnalysis:
    """Liest eine Druckdatei zeilenweise, speicherbegrenzt und abbrechbar."""
    metrics = GcodeMetrics()
    warnings: list[str] = []
    pattern_values: dict[int, tuple[str, str]] = {}
    settings: dict[str, str] = {}
    corners: list[tuple[float, float]] | None = None
    bed_invalid = False
    bed_height: float | None = None
    last_elapsed: float | None = None
    layer_changes = 0

    position: list[float | None] = [None, None, None]
    axes_absolute = True
    arc_centres_absolute = False
    extrusion_absolute = True
    extrusion_position = 0.0
    active_support = False
    seen_type = False
    total = 0.0
    support = 0.0
    has_first_layer = False
    after_first_layer = False
    all_paths = False
    model_paths = False
    all_extent = _Extent()
    model_extent = _Extent()

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
            for index, (_name, pattern) in enumerate(_PATTERNS):
                if index in pattern_values:
                    continue
                found = re.search(pattern, stripped, re.IGNORECASE)
                if found is not None:
                    pattern_values[index] = (
                        found.group("value").strip(),
                        found.groupdict().get("unit") or "",
                    )
            found_warning = _WARNING.match(stripped)
            if found_warning is not None:
                warnings.append(found_warning.group("text").strip())
            elapsed = _TIME_ELAPSED.search(stripped)
            if elapsed is not None:
                last_elapsed = float(elapsed.group(1))
            if _LAYER_CHANGE.fullmatch(stripped):
                layer_changes += 1
            setting = _SETTING_LINE.match(stripped)
            if setting is not None:
                settings.setdefault(setting.group("key").casefold(), setting.group("value"))
            kind = _SUPPORT_TOOL.match(stripped)
            if kind is not None:
                seen_type = True
                active_support = "support" in kind.group("type").casefold()
            shape = _BED_SHAPE.match(stripped)
            if shape is not None and corners is None and not bed_invalid:
                corners, bed_invalid = _bed_corners(shape.group("corners"))
            tall = _BED_HEIGHT.match(stripped)
            if tall is not None and bed_height is None:
                bed_height = _number(tall.group("height"))
            continue

        command_text = stripped.split(";", 1)[0].strip()
        command = _COMMAND.match(command_text)
        if command is None:
            continue
        family = command.group("family").upper()
        code = int(command.group("code"))
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
        if family == "M" and code in (82, 83):
            extrusion_absolute = code == 82
            continue
        if family != "G":
            continue
        if code in (90, 91):
            axes_absolute = code == 90
            continue
        if code == 92:
            for axis, name in enumerate("XYZ"):
                if name in words:
                    position[axis] = words[name]
            if "E" in words:
                extrusion_position = words["E"]
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

        step: float | None = None
        if "E" in words:
            value = words["E"]
            if extrusion_absolute:
                step = value - extrusion_position
                extrusion_position = value
            else:
                step = value
                extrusion_position += value
        travelled = "X" in words or "Y" in words or code in (2, 3)
        if code == 0 or not travelled or step is None:
            continue
        total += step
        if active_support and step > 0.0:
            support += step
        if step <= 0.0:
            continue

        end = (endpoint[0], endpoint[1], endpoint[2])
        points = _path_points(
            code,
            start,
            end,
            words,
            arc_centres_absolute=arc_centres_absolute,
        )
        all_paths = True
        all_extent.add(*points)
        if after_first_layer:
            model_paths = True
            model_extent.add(*points)

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    for index, (name, _pattern) in enumerate(_PATTERNS):
        if getattr(metrics, name) is not None and getattr(metrics, name) != "":
            continue
        captured = pattern_values.get(index)
        if captured is not None:
            _set(metrics, name, *captured)
    if last_elapsed is not None:
        metrics.print_seconds = last_elapsed
    if metrics.layer_count is None:
        metrics.layer_count = layer_changes or None
    metrics.support_mm3 = support * FILAMENT_AREA if seen_type else None
    total = max(total, 0.0)
    if metrics.filament_mm is None or (metrics.filament_mm <= 0.0 and total > 0.0):
        metrics.filament_mm = total or None
    metrics.warnings = tuple(warnings)
    bed = None if bed_invalid else _bed_box(corners, bed_height)
    extent = model_extent.box() if has_first_layer else all_extent.box()
    does_extrude = model_paths if has_first_layer else all_paths
    _log.info("read g-code of %s", metrics.slicer or "unknown slicer")
    return GcodeAnalysis(metrics, does_extrude, extent, bed, settings)


def extrudes(text: str) -> bool:
    """Fördert diese Datei überhaupt Material?

    Format-unabhängig gefragt: nicht am Kommentar, den jeder Slicer anders
    schreibt, sondern an der Bewegung selbst. Eine Datei ohne eine einzige
    Bahn mit Vorschub ist kein Druck — sie ist ein Leerlauf über die Platte,
    und sie entsteht, wenn der Slicer das Modell nicht gefunden oder
    verworfen hat. Groß ist sie trotzdem, und ohne diese Frage sähe sie aus
    wie ein geglückter Lauf. Wo eine erste Schicht markiert ist, zählt erst der
    Modellbereich danach; eine bewegte Reinigungsbahn davor ist kein Modell.
    """
    return analyze(text).extrudes


def printed_extent(text: str) -> BoundingBox | None:
    """Wohin diese Datei wirklich druckt — aus den Bahnen, nicht aus dem Kopf.

    ``None``, wenn keine einzige Bahn Material fördert; dann sagt
    :func:`extrudes` das Nötige.

    **Warum aus den Bahnen.** Dieselbe Überlegung wie bei :func:`extrudes`: Der
    Kopf ist das, was ein Slicer über sich behauptet, die Bewegung ist, was der
    Drucker tut. CuraEngine schreibt in seinen Kopf ``;MINX:2.14748e+06`` — den
    unbesetzten Anfangswert —, weil dort sonst das Cura-Fenster nachträglich
    einträgt; von der Kommandozeile aus bleibt er stehen.

    **Und wozu.** Weil ein Slicer eine Datei schreiben kann, die neben der
    Platte druckt; wer davon nur aus dem Kopf erfährt, erfährt es nie.
    :func:`app.core.export.handover.off_the_bed` beurteilt das Maß, das hier
    herauskommt, und dort steht die Messung.

    Die Stelle wird über alle Bewegungen nachgeführt, auch über die leeren,
    denn Z steht so gut wie nie in derselben Zeile wie die Bahn. Relative
    Bewegungen werden nur dann aufgelöst, wenn ihr Ausgangspunkt bekannt ist.

    **Eine Bahn muss sich bewegen.** ``G1 E6 F120`` fördert sechs Millimeter
    Material, ohne einen Millimeter zu fahren — das ist die Reinigung vor dem
    Druck und keine Bahn. Der ElegooSlicer setzt sie an ``Y -1,2``, also
    außerhalb des Betts, das er selbst nennt; ohne diese Bedingung stand der
    ganze Druck 1,2 mm neben der Platte, und die Meldung dazu kam bei **jedem**
    Orca-Lauf.
    """
    return analyze(text).extent


def stated_bed(text: str) -> BoundingBox | None:
    """Das Bett, das die Datei **selbst** nennt — ``None``, wenn sie schweigt.

    Dieselbe Haltung wie bei :func:`verify`: Die einzige Auskunft, die vom
    Programm selbst kommt, ist die, die es in seine Datei schreibt. Gemessen an
    den drei Familien:

    * die Orca-Familie schreibt ``printable_area`` **und** ``bed_shape``, dazu
      ``printable_height``,
    * PrusaSlicer schreibt ``bed_shape`` und ``max_print_height`` — bei ihm
      genau das, was Solidon ihm gegeben hat,
    * CuraEngine schreibt nichts davon; dort bleibt es bei dem, was Solidon
      selbst gesetzt hat (:func:`app.core.export.handover.bed_box`).

    **Und das ist der Unterschied zwischen einer wahren und einer geratenen
    Aussage.** Bei der Orca-Familie kommt das Maschinenprofil aus dem Bestand
    des Slicers (§29: es wird nicht erfunden). Gegen Solidons eigenen Bauraum
    gemessen heißt „außerhalb des Bauraums" dort zweierlei — der Druck liegt
    daneben, oder die zwei Profile meinen verschiedene Maschinen —, und
    unterscheiden ließe sich das nicht.

    Die Ecken stehen als ``0x0,256x0,256x256,0x256``; gelesen wird die
    Hüllbox, nicht das Vieleck. Ein ausgeschnittenes Eck (``bed_exclude_area``)
    bleibt damit außen vor: Es ist eine Verbotszone innerhalb des Betts, und
    ein Druck, der sie berührt, ist ein anderer Befund als einer, der über den
    Rand hinausfährt.
    """
    return analyze(text).bed


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
            corners.append((float(parts[0]), float(parts[1])))
        except ValueError:
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


def _set(metrics: GcodeMetrics, name: str, value: str, unit: str = "") -> None:
    number: float | None
    if name == "slicer":
        metrics.slicer = value
        return
    if name == "print_seconds":
        metrics.print_seconds = _seconds(value)
        return
    if name in ("filament_mm", "filament_grams"):
        # Die Kommas trennen Extruder, keine Dezimalstellen. Eine explizite
        # Gesamtsumme steht im Musterregister vor den gerundeten Einzelwerten.
        amounts = [_number(part.strip()) for part in value.split(",")]
        if any(amount is None or not math.isfinite(amount) or amount < 0 for amount in amounts):
            return
        number = sum(amount for amount in amounts if amount is not None)
    else:
        number = _number(value)
    if number is None:
        return
    if name == "filament_mm":
        metrics.filament_mm = _length_mm(number, unit)
    elif name == "filament_grams":
        metrics.filament_grams = number
    elif name == "layer_count":
        metrics.layer_count = int(number)
    elif name == "layer_height":
        metrics.layer_height = number


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


def compare(estimated: float, measured: float, what: str = "support") -> CrossCheck:
    """Prüft eine Größe gegen. Ein großer Unterschied ist ein Befund, keine
    Korrektur.

    §28.2: die interne Schätzung wird nicht still durch den gemessenen Wert
    ersetzt. Beide bleiben, beide behalten ihre Herkunft, und der Bericht sagt,
    dass sie sich widersprechen — das ist das Signal, dass die Schichtanalyse
    Arbeit braucht.
    """
    check = CrossCheck(what=what, estimated=estimated, measured=measured)
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
                values={"what": what, "estimated": round(estimated, 2)},
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
                    "what": what,
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
    nur da, wo es eine Platte ist.
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
        filament_mm=total(lambda entry: entry.filament_mm),
        filament_grams=total(lambda entry: entry.filament_grams),
        support_mm3=total(lambda entry: entry.support_mm3),
        layer_count=None,
        layer_height=heights.pop() if len(heights) == 1 else None,
        warnings=tuple(warnings),
        source="gcode",
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
    grams = metrics.grams()
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
            )
        )
    return findings
