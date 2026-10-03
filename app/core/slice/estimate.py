"""Was ein Teil kostet, ohne es zu schneiden (Bauplan §22, §29).

Die Schichtanalyse weiß es genau und braucht dafür Sekunden. Für eine Zahl,
die *während* des Konstruierens danebensteht, ist das zu teuer: sie müsste bei
jedem gezogenen Parameter neu laufen, und §31 gibt das nicht her.

Hier steht deshalb die billige Antwort. Sie braucht zwei Zahlen, die jedes
ausgewertete Netz mitbringt — Volumen und Oberfläche — und rechnet daraus:

    Material = Schale + Füllung des Kerns
    Dicke    = 3 Volumen / Oberfläche      (die mittlere Wanddicke des Körpers)
    Kern     = Volumen mal ((Dicke - Wand) / Dicke)^3
    Schale   = Volumen minus Kern
    Zeit     = Materialvolumen / Volumenstrom

**Die Schale ist die Differenz zweier Körper, nicht Fläche mal Dicke.** Der
erste Ansatz nahm ``Oberfläche mal Wandstärke`` und zählte damit jede Kante
doppelt: Bei einem 20-mm-Würfel mit 1,26 mm Wand kommen so 3024 mm³ heraus,
wirklich sind es 2659. Der Fehler ist deshalb kein Rauschen, sondern ein
Aufschlag — gemessen gegen PrusaSlicer 2.9.6 lag die Schätzung an vier
analytischen Körpern 5 bis 22 Prozent zu hoch und an sieben Modellen des
Kundendurchgangs 10 bis 41 Prozent.

**Gerechnet wird über die mittlere Wanddicke** ``3V/A``. Für Kugel und Würfel
ist das genau der Inkugelradius, und ein um die Wandstärke nach innen
versetzter Körper ist in jeder Richtung um deren Anteil kleiner — daher die
dritte Potenz. Der Zahlenwert trägt die Form mit, ohne sie zu kennen: ein
Rahmen mit dünnen Stegen hat eine kleine mittlere Dicke und ist damit fast
ganz Schale, ein Klotz eine große und fast ganz Kern.

Ein Hüllquader statt der mittleren Dicke war der zweite Versuch und ist
gemessen der schlechteste: Er hält einen flachen Rahmen für einen flachen
Klotz. Alle drei Modelle an denselben sieben Modellen, gegen PrusaSlicer:

| Modell | gemessen | Fläche mal Dicke | Hüllquader | 3V/A |
|---|---|---|---|---|
| Querstangen 210 | 77,7 g | +16 % | -6 % | +7 % |
| Querstangen 220 | 82,0 g | +16 % | -5 % | +7 % |
| Querstangen ohne Kasten | 77,5 g | +16 % | -6 % | +7 % |
| Regalfuß | 140,4 g | +17 % | -41 % | +3 % |
| Auslegerarm | 128,7 g | +16 % | -49 % | +1 % |
| Kit-Card | 27,5 g | +41 % | -33 % | +20 % |
| Propellersatz | 44,2 g | +10 % | -46 % | -2 % |
| **Mittel** | | **19 %** | **27 %** | **7 %** |

Das ist eine **Schätzung und heißt auch so**. Die Befunde daraus tragen
``source="internal"`` und werden mit gemessenen Werten aus dem G-Code nie
vermischt (Regel 14, §22.5). Wer es genau braucht, slicet und liest die
Gegenprobe.

Was sie **nicht** kann: Stützen, Schürze, Rand, Fahrwege ohne Materialauftrag,
und alles, was ein Slicer aus Nahtstellen und Lückenfüllung macht. Sie ist
eine Näherung mit ausgewiesener Herkunft, keine Rechnung.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.errors import OPEN_PRINT_SETTINGS
from app.core.geom.mesh import MeshData, concatenated
from app.core.types import (
    CancelToken,
    Finding,
    LayerInfo,
    PrintSettings,
    Profile,
    SceneObject,
    SliceResult,
)
from app.core.units import EPS_GEOM, is_close
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.slice.gcode import GcodeMetrics

#: Anteil der Zeit, der nicht auf Materialauftrag entfällt — Fahrwege,
#: Rückzüge, Beschleunigung, Schichtwechsel.
#:
#: **Ein angenommener Wert, kein gemessener.** Ohne Aufschlag liegt die
#: Schätzung sichtbar zu niedrig, weil ein Drucker einen erheblichen Teil der
#: Zeit fährt, ohne etwas aufzutragen; ein Viertel ist die übliche
#: Größenordnung. Belegen lässt sich das erst gegen G-Code-Zeiten aus der
#: Gegenprobe (§28.2) — bis dahin ist die Zahl das, was sie ist, und die
#: Anzeige nennt ihre Herkunft.
TRAVEL_SHARE = 0.25


@dataclass(frozen=True, slots=True)
class Estimate:
    """Was ein Körper an Material und Zeit verlangt — geschätzt.

    Alle Angaben ohne Stützen und ohne Haftungshilfe: was davon anfällt,
    entscheidet die Orientierung, und die steht hier nicht zur Debatte.
    """

    material_mm3: float
    """Aufgetragenes Material in mm³ — Schale plus Füllung."""

    grams: float
    """Masse in Gramm, mit der Dichte des eingestellten Filaments."""

    seconds: float
    """Druckdauer in Sekunden, aus Volumenstrom und Fahrweganteil."""

    @property
    def material_cm3(self) -> float:
        return self.material_mm3 / 1000.0

    @property
    def minutes(self) -> float:
        return self.seconds / 60.0


def support_material(support_volume: float, settings: PrintSettings) -> float:
    """Was eine Stützsäule an Material kostet, in mm³ (§28.2).

    Die Schichtanalyse liefert einen **Raum**: die Säule unter den Überhängen,
    von der Unterseite bis zum nächsten Material oder zur Platte
    (:func:`app.core.slice.analysis.slice_body`). Der Drucker füllt diesen Raum
    nicht aus — er stellt ein Muster hinein, und wie dicht, sagt
    ``support.density``.

    **Das ist der Umrechnungsfaktor, der der Gegenprobe fehlte** (§22.5,
    Regel 14): Dort stand ein Rauminhalt gegen eine gemessene Fadenmenge, und
    zwei verschiedene Größen liegen immer auseinander — die Warnung kam bei
    jedem Lauf. Gemessen am Pilz (Hut 40 auf 40 über einem Stiel 10 auf 10,
    20 mm hoch, PrusaSlicer 2.9.6, 0,2 mm, Stützen an):

    | Größe | Wert |
    |---|---|
    | Säule, analytisch | 30 000 mm³ |
    | Säule, Schichtanalyse | 29 987 mm³ |
    | mit 15 % Dichte gerechnet | 4 498 mm³ |
    | im G-Code gemessen | 3 991 mm³ |
    | Abweichung | -13 % |

    Damit liegt die Gegenprobe erstmals innerhalb ihrer Schwelle von 15 %. Die
    verbleibenden dreizehn Prozent sind der ``xy_gap``, der die Säule schmaler
    macht als den Überhang darüber — dass sie stehen bleiben, ist richtig: Die
    Zahl bleibt eine Schätzung, und die Gegenprobe soll sie nicht bestätigen,
    sondern messen.

    Ohne Stützen kostet die Säule nichts. Das ist keine Schätzung von null,
    sondern die Auskunft, dass dort nichts gedruckt wird.
    """
    if settings.support.style == "none":
        return 0.0
    return max(support_volume, 0.0) * max(settings.support.density, 0.0)


def shell_thickness(settings: PrintSettings) -> float:
    """Wie dick die massive Haut wird: Wandzahl mal Bahnbreite.

    Deck- und Bodenlagen sind dicker (5 und 4 Lagen mal 0,2 mm gegen 3 Wände
    mal 0,42 mm), und beides getrennt zu rechnen war der zweite Versuch — er
    braucht die Hüllmaße, und die verfehlen jeden Rahmen. Über eine ganze
    Oberfläche gemittelt ist die Wandstärke die bessere Näherung: an einem
    gedruckten Teil ist mehr Fläche senkrecht als waagerecht, sobald es höher
    als flach ist.
    """
    return settings.shell.wall_count * settings.layers.line_width


def flow_rate(settings: PrintSettings, speed: float | None = None) -> float:
    """Volumenstrom in mm³/s bei einer Geschwindigkeit.

    Ohne Angabe die der Füllung. Gedeckelt auf das, was das Filament hergibt:
    ein Wert über ``max_flow`` beschreibt einen Drucker, der schneller
    schmilzt, als er kann (§29).
    """
    metres = settings.speed.infill if speed is None else speed
    rate = settings.layers.line_width * settings.layers.layer_height * metres
    return min(rate, settings.filament.max_flow) if settings.filament.max_flow > 0 else rate


def wall_speed(settings: PrintSettings) -> float:
    """Wie schnell die Schale entsteht — außen und innen gemittelt.

    Getrennt von der Füllung, weil der Unterschied groß ist: Außenwände laufen
    oft halb so schnell. Bei einem kleinen Teil *ist* die Schale fast alles,
    und eine Zeit, die alles mit Fülltempo rechnet, kommt entsprechend zu
    niedrig heraus.
    """
    return (settings.speed.outer_wall + settings.speed.inner_wall) / 2.0


def core_share(volume_mm3: float, area_mm2: float, settings: PrintSettings) -> float:
    """Welcher Anteil eines Körpers hinter der Schale liegt.

    Über die mittlere Wanddicke ``3V/A``: Für Kugel und Würfel ist das genau
    der Inkugelradius, und ein um die Wandstärke nach innen versetzter Körper
    ist in jeder Richtung um deren Anteil kleiner — daher die dritte Potenz.
    Beim 20er Würfel bleiben so 0,668 als Kern übrig, bei einem 2 mm dünnen
    Blech 0,17, bei einem Rahmen aus 3 mm Stegen 0,15.

    **Die Form steckt in der Zahl, ohne dass die Rechnung sie kennen muss.**
    Das ist der Grund, aus dem hier keine Hüllmaße stehen: Ein Hüllquader hält
    einen flachen Rahmen für einen flachen Klotz, und gemessen lag die
    Schätzung damit bei zwei Regalteilen 41 und 49 Prozent zu **niedrig**.

    Wo die Wand dicker ist als der Körper, bleibt **nichts** übrig, und das ist
    die richtige Antwort: ein solches Blech druckt massiv. Genau dafür stand
    hier vorher eine Deckelung auf das Volumen; sie ist jetzt der Normalfall
    der Rechnung und kein Sonderfall daneben.
    """
    if area_mm2 <= 0.0 or volume_mm3 <= 0.0:
        return 0.0
    thickness = 3.0 * volume_mm3 / area_mm2
    wall = shell_thickness(settings)
    return (max(thickness - wall, 0.0) / thickness) ** 3


def estimate(volume_mm3: float, area_mm2: float, settings: PrintSettings) -> Estimate:
    """Material und Zeit für einen Körper, aus Volumen und Oberfläche.

    Beide Zahlen bringt jedes ausgewertete Netz mit; gerechnet wird in
    Millimetern und doppelter Genauigkeit (Regel 6).
    """
    if volume_mm3 <= 0.0:
        return Estimate(material_mm3=0.0, grams=0.0, seconds=0.0)

    core = volume_mm3 * core_share(volume_mm3, area_mm2, settings)
    shell = max(volume_mm3 - core, 0.0)
    filling = core * settings.infill.density
    material = shell + filling

    grams = material / 1000.0 * settings.filament.density

    # Zwei Geschwindigkeiten, nicht eine: die Schale läuft langsamer als die
    # Füllung, und bei einem kleinen Teil ist sie fast alles. Mit einem
    # gemeinsamen Tempo kam die Zeit durchweg um die Hälfte zu niedrig heraus.
    shell_rate = flow_rate(settings, wall_speed(settings))
    core_rate = flow_rate(settings)
    seconds = 0.0
    if shell_rate > 0.0:
        seconds += shell / shell_rate
    if core_rate > 0.0:
        seconds += filling / core_rate
    seconds /= 1.0 - TRAVEL_SHARE

    return Estimate(material_mm3=material, grams=grams, seconds=seconds)


def total(bodies: list[tuple[float, float]], settings: PrintSettings) -> Estimate:
    """Dieselbe Schätzung über mehrere Körper — je Körper Volumen und Fläche.

    Summiert wird das Ergebnis und nicht die Eingabe: zwei kleine Körper haben
    zusammen mehr Schale als einer mit demselben Volumen, und genau das soll
    sich in der Zahl niederschlagen.
    """
    parts = [estimate(volume, area, settings) for volume, area in bodies]
    return Estimate(
        material_mm3=sum(part.material_mm3 for part in parts),
        grams=sum(part.grams for part in parts),
        seconds=sum(part.seconds for part in parts),
    )


@dataclass(frozen=True, slots=True)
class PlateComparison:
    """Kennzahlen genau einer ausgegebenen Platte; unbekannt ist nie null."""

    plate: int
    support_material_mm3: float | None
    model_layer_count: int | None
    support_reason: TranslatableText | str = ""
    layers_reason: TranslatableText | str = ""
    arrangement_dependent: bool = False


def plate_comparison(
    plate: int,
    parts: Sequence[tuple[SceneObject, MeshData, PrintSettings | None]],
    profile: Profile,
    *,
    keep_arrangement: bool,
    separate_objects: bool,
    cancelled: CancelToken | None = None,
) -> PlateComparison:
    """Vollständige Analyse der exportierten Netze mit deren wirksamen Teilwerten.

    Der Schreiber ruft diesen Weg erst nach der Auflösung aller Teilwerte auf.
    Eine gemeinsame Platte wird gemeinsam geschnitten: Material eines zweiten
    Körpers trägt die Stütze des ersten, und dieselbe Säule zählt nur einmal.
    Unbekannte Slicer-Anordnung oder überlappende unterschiedliche Stützregeln
    erlauben dagegen keine gemeinsame Stützmenge. Modelllagen bleiben prüfbar.
    """
    from app.core.knowledge import profiles
    from app.core.slice.analysis import model_support
    from app.core.slice.findings import analysed

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    missing = _("Die wirksamen Druckeinstellungen dieser Ausgabe sind unbekannt.")
    if not parts or any(settings is None for _entry, _mesh, settings in parts):
        return PlateComparison(plate, None, None, missing, missing)
    known = [(entry, mesh, settings) for entry, mesh, settings in parts if settings is not None]
    first = known[0][2]
    same_grid = all(
        is_close(settings.layers.layer_height, first.layers.layer_height)
        and is_close(settings.layers.first_layer_height, first.layers.first_layer_height)
        for _entry, _mesh, settings in known
    )
    meshes: list[MeshData] = []
    for _entry, mesh, _settings in known:
        # Bei getrennten Objekten ohne übernommene Anordnung setzt der Slicer
        # jedes Objekt aufs Bett. Ein gemeinsames STL wird als Ganzes versetzt.
        if separate_objects and not keep_arrangement:
            raw = mesh.raw.copy()
            raw.apply_translation((0.0, 0.0, -mesh.bounds.minimum[2]))
            mesh = MeshData.of(raw)
        meshes.append(mesh)

    def limits(indices: Sequence[int], settings: PrintSettings) -> tuple[float, float]:
        values = [
            profiles.analysis_limits(
                profiles.for_process(profile, settings, effective=True), known[index][0]
            )
            for index in indices
        ]
        # Die Gegenprobe folgt dem exportierten Stützwinkel. Materialproben
        # liefern weiterhin die Wandgrenze, dürfen aber den finalen Teilwert
        # hier nicht durch ihren Vorschlagswinkel ersetzen.
        return max(wall for wall, _angle in values), settings.support.threshold_angle

    def measure(indices: Sequence[int], settings: PrintSettings) -> SliceResult:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        mesh = (
            meshes[indices[0]]
            if len(indices) == 1
            else MeshData.of(concatenated([meshes[index].raw for index in indices]))
        )
        wall, angle = limits(indices, settings)
        return analysed(mesh, settings, angle, wall, cancelled=cancelled)

    all_indices = tuple(range(len(known)))
    arranged_apart = separate_objects and not keep_arrangement and len(known) > 1
    if same_grid and not arranged_apart:
        shared = measure(all_indices, first)
        model_layers = sum(layer.area > EPS_GEOM * EPS_GEOM for layer in shared.layers)
    else:
        shared = None

        # Bei unterschiedlichen Rastern ist jede tatsächlich belegte Z-Lage
        # der Platte einmal zu zählen. LayerInfo.z ist die Schnittmitte,
        # G-Code nennt dagegen die Oberkante der gedruckten Lage. Leerlagen
        # fehlen im Ergebnis; deshalb nicht über die Listenposition umrechnen.
        def printed_height(layer: LayerInfo, mesh: MeshData, settings: PrintSettings) -> float:
            first_top = mesh.bounds.minimum[2] + settings.layers.first_layer_height
            if layer.z < first_top + EPS_GEOM:
                return float(first_top)
            return layer.z + settings.layers.layer_height / 2.0

        heights = sorted(
            printed_height(layer, meshes[index], settings)
            for index, (_entry, _mesh, settings) in enumerate(known)
            for layer in measure((index,), settings).layers
            if layer.area > EPS_GEOM * EPS_GEOM
        )
        model_layers = 0
        previous: float | None = None
        for height in heights:
            if previous is None or not is_close(height, previous):
                model_layers += 1
                previous = height

    if all(settings.support.style == "none" for _entry, _mesh, settings in known):
        return PlateComparison(plate, 0.0, model_layers)
    if arranged_apart:
        return PlateComparison(
            plate,
            None,
            model_layers,
            _("Der Slicer bestimmt die gemeinsame Anordnung der Teile erst beim Slicen."),
        )

    # Gleicher Vertrag heißt gleiches Raster und gleiche Stützparameter, nicht
    # bloß dieselbe Dichte. Filamentdichte beeinflusst mm³ dagegen nicht.
    def same_support(settings: PrintSettings) -> bool:
        a, b = first.support, settings.support
        return (
            a.style == b.style
            and a.placement == b.placement
            and a.block_channels == b.block_channels
            and a.interface_layers == b.interface_layers
            and all(
                is_close(getattr(a, key), getattr(b, key))
                for key in ("density", "threshold_angle", "z_gap", "xy_gap")
            )
        )

    if same_grid and all(same_support(settings) for _entry, _mesh, settings in known):
        assert shared is not None
        groups = [(shared, first)]
    else:
        for index, mesh in enumerate(meshes):
            for other in meshes[index + 1 :]:
                if all(
                    mesh.bounds.minimum[axis] < other.bounds.maximum[axis] - EPS_GEOM
                    and other.bounds.minimum[axis] < mesh.bounds.maximum[axis] - EPS_GEOM
                    for axis in (0, 1)
                ):
                    return PlateComparison(
                        plate,
                        None,
                        model_layers,
                        _("Überlappende Teile haben unterschiedliche Stützeinstellungen."),
                    )
        groups = [
            (measure((index,), settings), settings)
            for index, (_entry, _mesh, settings) in enumerate(known)
        ]
    support = 0.0
    for result, settings in groups:
        if settings.support.style == "none":
            continue
        if settings.support.placement == "build_plate" or settings.support.block_channels:
            supported = model_support(result)
            if (
                settings.support.placement == "build_plate"
                and (
                    supported.open_area > EPS_GEOM
                    or supported.channels
                    or supported.island_on_model
                )
            ) or (settings.support.block_channels and supported.channels):
                return PlateComparison(
                    plate,
                    None,
                    model_layers,
                    _("Die gemeinsame Stützmenge mit diesen Stützbegrenzungen ist unbekannt."),
                )
        support += support_material(result.support_volume, settings)
    return PlateComparison(plate, support, model_layers, arrangement_dependent=len(known) > 1)


def plate_findings(
    expected: PlateComparison,
    measured: GcodeMetrics,
    *,
    rearranged: bool = False,
) -> list[Finding]:
    """Beide Herkünfte je Platte sichtbar halten, auch bei Übereinstimmung."""
    from app.core.slice.gcode import DEVIATION_LIMIT

    support = expected.support_material_mm3
    reason = expected.support_reason
    if rearranged and expected.arrangement_dependent:
        support = None
        reason = _("Der Slicer hat die Anordnung der Teile geändert.")
    measured_support = measured.support_mm3
    if "support" in measured.uncertain_material_roles:
        measured_support = None
        reason = _("Die Druckdatei weist die vollständige Stützmenge nicht eindeutig aus.")
    found: list[Finding] = []
    for quantity, estimate_value, measured_value, unit, missing_reason in (
        (_("Stützmaterial"), support, measured_support, "mm³", reason),
        (
            _("Modellschichten"),
            expected.model_layer_count,
            measured.model_layer_count,
            _("Schichten"),
            expected.layers_reason,
        ),
    ):
        values: dict[str, float | str | TranslatableText] = {
            "plate": expected.plate + 1,
            "what": quantity,
            "unit": unit,
            "estimated_source": "internal",
            "measured_source": "gcode",
        }
        if estimate_value is not None:
            values["estimated"] = estimate_value
        if measured_value is not None:
            values["measured"] = measured_value
        if estimate_value is None or measured_value is None:
            values["reason"] = missing_reason or _(
                "Die Druckdatei nennt für diese Größe keinen Messwert."
            )
            found.append(
                Finding(
                    code="gcode.plate_comparison_unknown",
                    severity="info",
                    message=_(
                        "Platte {plate}, {quantity}: Die Gegenprobe ist unvollständig. {reason}",
                        plate=expected.plate + 1,
                        quantity=quantity,
                        reason=values["reason"],
                    ),
                    values=values,
                    source="gcode",
                )
            )
            continue
        deviation = (
            abs(measured_value - estimate_value) / measured_value
            if measured_value > EPS_GEOM
            else (0.0 if estimate_value <= EPS_GEOM else 1.0)
        )
        differs = deviation > DEVIATION_LIMIT
        found.append(
            Finding(
                code="gcode.plate_deviation" if differs else "gcode.plate_comparison",
                severity="warning" if differs else "info",
                suggestions=(OPEN_PRINT_SETTINGS,) if differs else (),
                message=_(
                    "Platte {plate}, {quantity}: intern geschätzt {estimated} {unit}, "
                    "im G-Code {measured} {unit}. {result}",
                    plate=expected.plate + 1,
                    quantity=quantity,
                    estimated=round(estimate_value, 2),
                    measured=round(measured_value, 2),
                    unit=unit,
                    result=_("Die Werte weichen deutlich voneinander ab.")
                    if differs
                    else _("Die Werte stimmen innerhalb der Vergleichsgrenze überein."),
                ),
                values=values,
                source="gcode",
            )
        )
    return found


def plates_findings(
    expected: Sequence[PlateComparison],
    measured: Sequence[GcodeMetrics],
    rearranged: Sequence[bool],
) -> list[Finding]:
    """Nur vollständige, eindeutig zugeordnete Plattenvergleiche veröffentlichen."""
    if (
        len(expected) != len(measured)
        or len(expected) != len(rearranged)
        or len({entry.plate for entry in expected}) != len(expected)
    ):
        return [
            Finding(
                code="gcode.plate_comparison_unknown",
                severity="info",
                message=_(
                    "Die Druckdateien lassen sich nicht eindeutig den verglichenen "
                    "Platten zuordnen."
                ),
                source="gcode",
            )
        ]
    return [
        finding
        for snapshot, metrics, moved in zip(expected, measured, rearranged, strict=True)
        for finding in plate_findings(snapshot, metrics, rearranged=moved)
    ]
