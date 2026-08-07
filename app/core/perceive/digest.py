"""Der Steckbrief der Szene für den Agenten (Bauplan §23).

Was der Agent zu sehen bekommt, in Worten: Objekte mit ihren Maßen, Merkmale
mit ihren Namen, die Parameter, die aktuelle Auswahl, der Stapel in Kurzform.
Der Agent bezieht sich auf diese Namen und nie auf Koordinaten (Leitprinzip
5) — dieser Text ist also das Vokabular, auf dem das ganze Gespräch läuft.

Er ist zum Lesen geschrieben. Eine Wand aus JSON trüge dieselben Fakten und
wäre schwerer zu durchdenken — für das Modell so gut wie für den Menschen, der
nachsieht, was dem Modell gesagt wurde.
"""

from __future__ import annotations

from app.core.types import Document, Feature, ObjectId, Scene, SceneObject
from app.core.units import format_length, round_display
from app.i18n import tr


def digest(
    scene: Scene,
    document: Document | None = None,
    selection: tuple[ObjectId, str] | None = None,
) -> str:
    """Die ganze Szene in der Form, die §23 beschreibt."""
    lines: list[str] = [_scene_line(scene)]

    if scene.parameters:
        values = " · ".join(
            f"{name}={round_display(parameter.value):g} {parameter.unit}"
            for name, parameter in scene.parameters.items()
        )
        lines.append(f"{tr('Parameter')}: {values}")

    if selection is not None:
        object_id, feature_id = selection
        lines.append(f"{tr('Auswahl')}: {object_id}" + (f" · {feature_id}" if feature_id else ""))

    for object_id, entry in scene.objects.items():
        lines.extend(_object_lines(object_id, entry))

    lines.extend(_finding_lines(scene))
    if document is not None:
        lines.extend(_stack_lines(document))
    return "\n".join(lines)


def _scene_line(scene: Scene) -> str:
    profile = scene.profile
    printer = profile.printer.id if profile else "-"
    material = profile.material.id if profile else "-"
    state = ""
    if profile is not None:
        state = f" ({tr('kalibriert') if profile.material.calibrated else tr('Startwert')})"
    return (
        f"{tr('Szene')}: {len(scene.objects)} {tr('Objekte')}, "
        f"{tr('Drucker')} {printer}, {tr('Material')} {material}{state}"
    )


def _object_lines(object_id: ObjectId, entry: SceneObject) -> list[str]:
    size = entry.mesh.bounds.size
    closed = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
    on_bed = tr("auf Bett") if abs(entry.mesh.bounds.minimum[2]) < 0.05 else ""
    facts = [
        f"{size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm",
        f"{entry.mesh.volume / 1000.0:.1f} cm³",
        closed,
    ]
    solidity = _solidity(entry)
    if solidity is not None:
        # Wie massiv das Teil ist, gemessen am Quader, den es einnimmt. Ein
        # Vollkörper liegt bei hundert Prozent, ein ausgehöhlter bei zwanzig,
        # ein gefüllter dazwischen — die eine Zahl, die sagt, wie viel Material
        # der Druck kostet, und sie steht schon in den beiden davor.
        facts.append(f"{solidity:.0%} {tr('massiv')}")
    if on_bed:
        facts.append(on_bed)
    if entry.material:
        # Nur, wenn es vom Projektmaterial abweicht — die Szenenzeile nennt
        # jenes bereits, und es an jedem Körper zu wiederholen wäre Rauschen (§26.1).
        facts.append(entry.material)

    lines = [f'{object_id}  "{entry.name}"  ' + ", ".join(facts)]
    for feature_id, feature in entry.features.items():
        lines.append("  " + _feature_line(feature_id, feature))
    return lines


def _solidity(entry: SceneObject) -> float | None:
    """Der Anteil des Hüllquaders, den der Körper wirklich ausfüllt.

    Nur, wo er etwas aussagt: ein offener Körper hat kein verlässliches
    Volumen, und ein Quader, der in einer Achse null misst, keinen Nenner.
    """
    size = entry.mesh.bounds.size
    box = size[0] * size[1] * size[2]
    if not entry.mesh.is_watertight or box <= 0.0:
        return None
    return float(entry.mesh.volume / box)


def _feature_line(feature_id: str, feature: Feature) -> str:
    """Ein Merkmal, mit dem Ort, an dem es sitzt.

    Die Position fehlte hier, und das machte den Steckbrief zu einer
    Beschreibung, auf die der Agent nicht handeln konnte: er las Durchmesser
    und Achse einer Bohrung und hatte nichts, was sagte, *wo* sie ist. Für
    „setz einen Baustein an hole_1" reicht der Name, für „bohr daneben"
    nicht. Die Oberfläche kennt die Position, seit sie anklickbar ist (§18.5)
    — der Agent sieht nur diesen Text (§26.1).
    """
    params = feature.params
    at = _place(params.get("centre"))
    if feature.kind == "hole":
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        through = tr("Durchgang") if params.get("through") else tr("Sackloch")
        return (
            f"{feature_id}  Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Achse')} {axis}, {through}{at}"
        )
    if feature.kind == "face":
        normal = _axis_name(params.get("normal", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {tr('planar')} {float(params.get('area', 0.0)):.0f} mm², "
            f"{tr('Normale')} {normal}{at}"
        )
    if feature.kind == "edge_loop":
        return f"{feature_id}  {params.get('open_edges', 0)} {tr('offene Kanten')}"
    return f"{feature_id}  {feature.kind}{at}"


def _place(centre: object) -> str:
    """``, bei (25, -15, 8)`` — oder nichts, bei einem Merkmal ohne Ort."""
    if not isinstance(centre, list | tuple) or len(centre) != 3:
        return ""
    try:
        numbers = ", ".join(_rounded(float(value)) for value in centre)
    except (TypeError, ValueError):
        return ""
    return f", {tr('bei')} ({numbers})"


def _rounded(value: float) -> str:
    """Eine Null bleibt eine Null.

    Die Mittelpunkte kommen aus einer Rechnung, und ein zentrierter Quader
    landet dabei nicht auf 0, sondern auf -1.11022e-16. Für den Steckbrief ist
    das schädlich: der Agent liest ihn als Text und nimmt eine
    Zehn-hoch-minus-sechzehn für einen Wert, der etwas bedeutet — er ist
    darauf angewiesen, dass dasteht, was gemeint ist. Ein Zehntausendstel
    Millimeter unterschreitet jede Fertigungstoleranz, die dieses Gerät
    einhalten kann; darunter ist es Rechenrauschen.
    """
    return f"{0.0 if abs(value) < 1e-4 else value:g}"


def _axis_name(vector: tuple[float, float, float]) -> str:
    """Macht aus einer Richtung etwas Lesbares: +Z statt (0, 0, 1)."""
    names = ("X", "Y", "Z")
    largest = max(range(3), key=lambda index: abs(vector[index]))
    sign = "+" if vector[largest] >= 0 else "-"
    return f"{sign}{names[largest]}"


def _finding_lines(scene: Scene) -> list[str]:
    """Warnungen und Hinweise gehören in den Steckbrief — der Agent muss
    wissen, worauf er steht (§17.3, §26.1).
    """
    lines: list[str] = []
    for finding in scene.report.findings:
        if finding.severity == "info":
            continue
        marker = tr("Warnung") if finding.severity == "warning" else tr("Fehler")
        lines.append(f"  {marker.lower()} {finding.message}")
    return lines


def _stack_lines(document: Document) -> list[str]:
    if not document.transactions:
        return []
    parts = []
    for transaction in document.transactions:
        numbers = ", ".join(str(entry) for entry in transaction.ops)
        by = tr("Agent") if transaction.origin.by == "agent" else tr("Nutzer")
        parts.append(f'{transaction.id} "{transaction.title}" ({tr("Ops")} {numbers}, {by})')
    return [f"{tr('Verlauf')}: " + " · ".join(parts)]
