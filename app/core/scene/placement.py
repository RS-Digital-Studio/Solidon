"""Was ein angeklicktes Merkmal für die Parameter einer Operation
bedeutet (Bauplan §18.5, §25).

§25 verlangt „einen Baustein an ein erkanntes Merkmal setzen". Erkennen war
P3, Setzen war P5 — aber verbunden wurden die zwei nie: das Merkmal war im
Baum und in der Ansicht wählbar, und der Dialog, der sich als Nächstes
öffnete, wusste nichts davon. Wer eine Bohrung in der eben angeklickten
Fläche wollte, tippte ihre Koordinaten von Hand ab, von der Analysekarte.

Hier treffen sich die zwei — und zwar im Kern statt im Fenster, weil es eine
Regel über Geometrie und Parameter ist, nicht über Widgets: testbar ohne Qt,
und verfügbar für jede Oberfläche, der später eine Auswahl wächst. Heute ist
das Fenster der einzige Aufrufer: die Kommandozeile hat keine Auswahl, und
der Agent arbeitet vom Steckbrief (§26.1) — darum steht die Position jedes
Merkmals in diesem Steckbrief, statt hier ein zweites Mal hergeleitet zu
werden.

Nichts hier ändert das Dokument. Die Werte werden gewöhnliche Parameter der
Operation, der Stapel bleibt also eine reine Funktion dessen, was in ihm
steht (§11) — eine Auswahl ist ein Zustand der Oberfläche und hat in einer
Projektdatei nichts verloren. Darum nimmt eine Operation, die das Merkmal
*prüfen* will, stattdessen seinen Namen als Parameter: ``at_feature`` steht
in der Datei, und die Operation schlägt es bei jedem Rechnen der Szene nach.
"""

from __future__ import annotations

from typing import Any

from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.types import Feature, Vec3

_log = get_logger(__name__)

#: Der Parameter, mit dem ein Baustein das Merkmal benennt, an das er gehört.
#: Wo eine Operation ihn hat, ist das die ganze Antwort: die Position daneben
#: zählt als Versatz vom Merkmal und bleibt auf null.
FEATURE_FIELD = "at_feature"

#: Die Position, in der Reihenfolge, in der die Parameter überall heißen.
POSITION = ("x", "y", "z")

#: Eine freie Richtung, für die Operationen, die eine nehmen (§25, Beschriftung).
NORMAL = ("nx", "ny", "nz")

#: Der Parameter, der eine Fläche als **Ziel** benennt statt als Ort — die Höhe
#: einer Extrusion reicht bis dorthin (§30.1, D14). Wie ``at_feature`` eine
#: Kennung, aber kein Ersatz für die Position: die Skizze liegt woanders.
TARGET_FIELD = "up_to"

#: Der Durchmesser, um den eine Textur läuft. **Nicht** ``diameter``: eine
#: Senkung hat einen eigenen — den des Schraubenkopfs — und dürfte den der
#: Bohrung darunter nicht erben. Der Name sagt deshalb, dass er ein Bezug ist
#: und kein Maß; ihn am bloßen ``diameter`` festzumachen trug in
#: ``countersink_hole`` eine falsche Zahl ein, die wie eine gemessene aussah.
#: Der Test, der das verhindert, stand schon da.
DIAMETER_FIELD = "wrap_diameter"

#: Wie dominant eine Komponente sein muss, bevor die Richtung als Achse zählt.
#: Darunter steht das Merkmal schräg, und ihm eine Achse zu nennen wäre eine
#: Rundung, die jemand hinterher bemerken muss.
AXIS_CLARITY = 0.9


def values_for(spec: OperationSpec, feature: Feature) -> dict[str, Any]:
    """Die Parameter, die dieses Merkmal für diese Operation vorschlägt.

    Nur, was das Merkmal sicher sagt: wo es ist und wohin es schaut. Nicht
    seine Größe — eine Senkung nimmt den Durchmesser des Schraubenkopfs, nicht
    den der Bohrung, auf der sie sitzt, und eine hilfsbereit eingetragene 5,2
    wäre dort eine falsche Zahl, die wie eine gemessene aussieht.
    """
    names = {entry.name for entry in spec.params.spec()}
    if FEATURE_FIELD in names:
        return {FEATURE_FIELD: feature.id}

    values: dict[str, Any] = {}
    if TARGET_FIELD in names and feature.kind == "face":
        # „Bis zu dieser Fläche" — die Kennung reicht, den Rahmen rechnet die
        # Auswertung daraus (app.core.sketch.planes). Nur planare Flächen: bis
        # zu einer Bohrung zu extrudieren hat keine Bedeutung.
        values[TARGET_FIELD] = feature.id
    if DIAMETER_FIELD in names and feature.kind == "hole":
        diameter = feature.params.get("diameter")
        if diameter is not None:
            values[DIAMETER_FIELD] = round(float(diameter), 4)
    centre = _vector(feature.params.get("centre"))
    if centre is not None:
        for name, value in zip(POSITION, centre, strict=True):
            if name in names:
                values[name] = round(float(value), 4)

    direction = _vector(feature.params.get("normal")) or _vector(feature.params.get("axis"))
    if direction is not None:
        for name, value in zip(NORMAL, direction, strict=True):
            if name in names:
                values[name] = round(float(value), 4)
        axis = dominant_axis(direction)
        if axis is not None and "axis" in names and _allows(spec, "axis", axis):
            values["axis"] = axis

    _log.info("feature %s suggests %d parameter(s) for %s", feature.id, len(values), spec.name)
    return values


def dominant_axis(direction: Vec3) -> str | None:
    """``x``, ``y`` oder ``z``, wenn die Richtung wirklich eine ist —
    sonst ``None``."""
    length = sum(value * value for value in direction) ** 0.5
    if length <= 0.0:
        return None
    shares = [abs(value) / length for value in direction]
    best = max(range(3), key=lambda index: shares[index])
    return "xyz"[best] if shares[best] >= AXIS_CLARITY else None


def faces_up(feature: Feature) -> bool:
    """Liegt diese Fläche flach und schaut nach oben?

    Nicht bloß flach — das hat diese Funktion früher gefragt, und es war zu
    großzügig: die Decke eines Hohlraums ist auch flach, und sie zeigt nach
    unten. Als Höhe einer Öffnung gewählt, baute sie einen Deckel ins Innere
    der Box, auf 26,9 von 30 Millimetern, ohne ein Wort — denn ein Schnitt
    unterhalb dieser Ebene trifft ja die Wand, also sah für keinen der
    folgenden Schritte etwas falsch aus.

    Alles, was eine Öffnung verschließt, greift von ihr nach unten: die
    Platte sitzt auf dem Rand, der Kragen geht in den Hohlraum. Eine Fläche,
    die nach unten schaut, bräuchte all das gespiegelt — und das auf die
    Vermutung zu bauen, dass jemand das meinte, ist schlechter, als zu sagen,
    welche Fläche gewollt ist.
    """
    normal = _vector(feature.params.get("normal"))
    return normal is not None and dominant_axis(normal) == "z" and normal[2] > 0.0


def _allows(spec: OperationSpec, name: str, value: str) -> bool:
    """Ist das eine der Auswahlmöglichkeiten, die der Parameter anbietet?"""
    for entry in spec.params.spec():
        if entry.name == name:
            return not entry.choices or value in entry.choices
    return False


def _vector(value: object) -> Vec3 | None:
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
