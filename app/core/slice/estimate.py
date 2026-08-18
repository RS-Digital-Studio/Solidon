"""Was ein Teil kostet, ohne es zu schneiden (Bauplan §22, §29).

Die Schichtanalyse weiß es genau und braucht dafür Sekunden. Für eine Zahl,
die *während* des Konstruierens danebensteht, ist das zu teuer: sie müsste bei
jedem gezogenen Parameter neu laufen, und §31 gibt das nicht her.

Hier steht deshalb die billige Antwort. Sie braucht zwei Zahlen, die jedes
ausgewertete Netz ohnehin mitbringt — Volumen und Oberfläche — und rechnet
daraus, was der Drucker verbrauchen wird:

    Material = Schale + Füllung des Restes
    Schale   ≈ Oberfläche mal Wandstärke
    Zeit     ≈ Materialvolumen / Volumenstrom

Das ist eine **Schätzung und heißt auch so**. Die Befunde daraus tragen
``source="internal"`` und werden mit gemessenen Werten aus dem G-Code nie
vermischt (Regel 14, §22.5).
Wer es genau braucht, slicet und liest die Gegenprobe.

**Warum sie trotzdem taugt.** Der Fehler steckt in der Schale, und die Schale
ist der Teil, den die Oberfläche exakt beschreibt: ein ausgehöhltes Gehäuse
hat viel Fläche und wenig Volumen, ein massiver Klotz umgekehrt. Genau diesen
Unterschied verfehlt „Volumen mal Dichte", und genau er entscheidet, ob ein
Teil zwölf Gramm wiegt oder achtzig.

Was sie **nicht** kann: Stützen, Schürze, Rand, Fahrwege ohne Materialauftrag.
Sie ist eine Untergrenze, und das ist die ehrlichere Richtung — eine Schätzung,
die zu wenig verspricht, überrascht niemanden an der Kasse.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.types import PrintSettings

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


def shell_thickness(settings: PrintSettings) -> float:
    """Wie dick die massive Außenhaut wird.

    Die Wände tragen sie seitlich, Deck- und Bodenlagen oben und unten. Beides
    ist verschieden dick, und über eine ganze Oberfläche gemittelt ist die
    Wandstärke die bessere Näherung: an einem gedruckten Teil ist mehr Fläche
    senkrecht als waagerecht, sobald es höher als flach ist.
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


def estimate(volume_mm3: float, area_mm2: float, settings: PrintSettings) -> Estimate:
    """Material und Zeit für einen Körper, aus Volumen und Oberfläche.

    Beide Zahlen bringt jedes ausgewertete Netz mit; gerechnet wird in
    Millimetern und doppelter Genauigkeit (Regel 6).

    Ein Körper, dessen Schale dicker wäre als er selbst, wird massiv gedruckt —
    deshalb die Deckelung: ohne sie käme bei einem dünnen Blech mehr Material
    heraus, als es überhaupt Volumen hat.
    """
    if volume_mm3 <= 0.0:
        return Estimate(material_mm3=0.0, grams=0.0, seconds=0.0)

    shell = min(area_mm2 * shell_thickness(settings), volume_mm3)
    core = max(volume_mm3 - shell, 0.0)
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

    Summiert wird das Ergebnis und nicht die Eingabe: zwei Körper haben
    zusammen mehr Oberfläche als einer mit demselben Volumen, und genau das
    soll sich in der Zahl niederschlagen.
    """
    parts = [estimate(volume, area, settings) for volume, area in bodies]
    return Estimate(
        material_mm3=sum(part.material_mm3 for part in parts),
        grams=sum(part.grams for part in parts),
        seconds=sum(part.seconds for part in parts),
    )
