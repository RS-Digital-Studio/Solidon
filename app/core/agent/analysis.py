"""Analysen als Werkzeugantwort (Bauplan §26.2, Konzept Agent-Vertiefung 3.3).

„Ist das so druckbar?" und „Wie lange druckt das?" konnte der Agent nicht
beantworten: Schichtanalyse, Schätzung, Einstellungsrat und Orientierungssuche
waren vollständig außerhalb seiner Reichweite, und er riet aus den zwei
Warnzeilen des Prüfberichts. ``read_analysis`` macht sie lesbar — nur lesbar:
gerechnet wird auf der Arbeitskopie, geändert wird nichts.

Zwei Regeln tragen dieses Modul:

* **Regel 14:** alles hier ist Schichtanalyse, nie G-Code. Jede Antwort
  beginnt mit ihrer Herkunft, damit die Zahl im Chat nicht als Slicer-Wahrheit
  weiterläuft.
* **Ein Deckel ist ein Ergebnis, kein Fehler:** ein Netz über der
  Dreiecksgrenze bekommt die Auskunft, dass die Analysekarte im Fenster der
  richtige Ort ist — statt den Zug minutenlang anzuhalten.

Sitzung und Fernsteuerung rufen dieselben Funktionen (Konzept 2.4).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Final

from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.print_settings import resolve
from app.core.slice import advise as advise_module
from app.core.slice.analysis import (
    island_layers,
    narrowest,
    slice_body,
    total_overhang,
    worst_overhang,
)
from app.core.slice.estimate import total as estimate_total
from app.core.slice.orientation import search
from app.core.types import CancelToken, Document, PrintSettings, Profile, Scene, SceneObject
from app.core.units import format_length
from app.i18n import tr

#: Was ``read_analysis`` kennt — das Enum im Werkzeugschema liest diese Liste.
ANALYSIS_KINDS: Final[tuple[str, ...]] = ("printability", "estimate", "advice", "orientation")

#: Ab dieser Dreieckszahl wird nicht im Zug gerechnet. Der Deckel ist hart und
#: vorab prüfbar — ein Zeitlimit mitten in einer laufenden Rechnung gäbe es
#: nur mit Gewalt gegen den Thread.
TRIANGLE_LIMIT: Final = 500_000

#: Wie viele Richtungen die Orientierungssuche im Zug probiert. Die volle
#: Suche gehört ins Fenster (§22.3) — hier reicht die Antwort, ob eine
#: deutlich bessere Lage existiert.
ORIENTATION_CANDIDATES: Final = 24

#: Startwert der Orientierungssuche im Zug: fest, damit zweimal fragen
#: zweimal dasselbe ergibt (Regel 9 — die Suche ist randomisiert, der Zug
#: hat keinen ``ctx.seed``, also steht der Wert hier mit Namen).
ORIENTATION_SEED: Final = 7


def analysis_text(
    kind: str,
    scene: Scene,
    document: Document,
    profile: Profile,
    objects: Collection[str] = (),
    cancelled: CancelToken | None = None,
) -> str:
    """Eine Analyse in Worten, mit Herkunft und Deckel.

    ``objects`` schränkt auf genannte Objekte ein; ohne Angabe rechnet die
    Analyse über die ganze Szene.
    """
    chosen = {
        object_id: entry
        for object_id, entry in scene.objects.items()
        if not objects or object_id in objects
    }
    if not chosen:
        return tr("Dazu gibt es kein Objekt in der Szene.")

    settings = document.print_settings or resolve(profile)
    source = tr("Herkunft: Schichtanalyse (geschätzt), nicht G-Code.")

    if kind == "printability":
        return "\n".join([source, *_printability(chosen, profile)])
    if kind == "estimate":
        return "\n".join([source, _estimate(chosen, settings)])
    if kind == "advice":
        return "\n".join([source, *_advice(chosen, document, profile, settings)])
    if kind == "orientation":
        return "\n".join([source, *_orientation(chosen, profile, cancelled)])
    known = ", ".join(ANALYSIS_KINDS)
    return f"{tr('Diese Analyse gibt es nicht')}: {kind} ({known})"


def _too_large(entry: SceneObject) -> bool:
    return entry.mesh.triangle_count > TRIANGLE_LIMIT


def _skipped(object_id: str) -> str:
    return f"{object_id}: " + tr(
        "übersprungen — das Netz ist zu groß für den Zug, die Analysekarte im Fenster kann es."
    )


def _printability(chosen: dict[str, SceneObject], profile: Profile) -> list[str]:
    """Überhang, Inseln, Brücken, dünnste Struktur — je Objekt eine Zeile."""
    lines: list[str] = []
    for object_id, entry in chosen.items():
        if _too_large(entry):
            lines.append(_skipped(object_id))
            continue
        result = slice_body(as_mesh_data(entry.mesh), layer_height=profile.printer.layer_height)
        islands = island_layers(result)
        thinnest = narrowest(result)
        spans = max((layer.bridge_width for layer in result.layers), default=0.0)
        facts = [
            f"{tr('Überhangfläche')} {total_overhang(result):.0f} mm²",
            f"{tr('steilste Schicht')} {worst_overhang(result):.0f} mm²",
            f"{tr('Stützvolumen')} {result.support_volume / 1000.0:.1f} cm³",
            f"{tr('erste Schicht')} {result.first_layer_area:.0f} mm²",
        ]
        if islands:
            heights = ", ".join(f"{value:.1f}" for value in islands[:3])
            facts.append(f"{len(islands)} {tr('Inseln (ab mm)')}: {heights}")
        if spans > 0.0:
            facts.append(f"{tr('längste Brücke')} {format_length(spans)}")
        if thinnest < profile.printer.nozzle_diameter * 2.0:
            facts.append(
                f"{tr('dünnste Struktur')} {format_length(thinnest)} "
                f"({tr('Düse')} {format_length(profile.printer.nozzle_diameter)})"
            )
        lines.append(f"{object_id}: " + ", ".join(facts))
    return lines


def _estimate(chosen: dict[str, SceneObject], settings: PrintSettings) -> str:
    """Zeit und Material über die gewählten Objekte zusammen."""
    bodies = [(float(entry.mesh.volume), float(entry.mesh.area)) for entry in chosen.values()]
    guess = estimate_total(bodies, settings)
    return (
        f"{tr('Druckzeit etwa')} {guess.minutes:.0f} min, "
        f"{tr('Material etwa')} {guess.grams:.0f} g ({guess.material_cm3:.1f} cm³) — "
        + tr("ohne Stützen und Haftungshilfe, die hängen an der Orientierung.")
    )


def _advice(
    chosen: dict[str, SceneObject],
    document: Document,
    profile: Profile,
    settings: PrintSettings,
) -> list[str]:
    """Einstellungsvorschläge mit Begründung (§28.2) — genannt, nie gesetzt.

    „Übernommen wird auf Klick, nie von allein" gilt auch für den Agenten:
    Druckeinstellungen reisen nicht in Transaktionen (die Grenze aus
    ``kern.md``), also gäbe es kein Undo, das einen gesetzten Wert mitnimmt —
    der Agent nennt den Vorschlag samt Grund, der Klick bleibt beim Nutzer.
    """
    first = next(iter(chosen.values()))
    result = (
        None
        if _too_large(first)
        else slice_body(as_mesh_data(first.mesh), layer_height=profile.printer.layer_height)
    )
    advice = advise_module.advise(
        settings,
        profile,
        result,
        bounds=first.mesh.bounds,
        fit_kinds=[fit.kind for fit in document.fits],
    )
    if not advice:
        return [tr("Die Einstellungen passen zu Teil, Material und Drucker.")]
    lines = [f"{entry.path}: {entry.was} → {entry.value} — {entry.reason}" for entry in advice]
    lines.append(tr("Nenne die Vorschläge samt Grund — geändert wird über den Druckdialog."))
    return lines


def _orientation(
    chosen: dict[str, SceneObject],
    profile: Profile,
    cancelled: CancelToken | None,
) -> list[str]:
    """Gibt es eine deutlich bessere Lage? Je Objekt eine Antwort."""
    lines: list[str] = []
    for object_id, entry in chosen.items():
        if _too_large(entry):
            lines.append(_skipped(object_id))
            continue
        found = search(
            as_mesh_data(entry.mesh),
            count=ORIENTATION_CANDIDATES,
            seed=ORIENTATION_SEED,
            layer_height=profile.printer.layer_height,
            cancelled=cancelled,
        )
        best = found.best
        current = found.baseline
        if best.support_volume >= current.support_volume * 0.95:
            lines.append(f"{object_id}: " + tr("die aktuelle Lage ist schon gut."))
            continue
        direction = ", ".join(f"{value:.2f}" for value in best.direction)
        lines.append(
            f"{object_id}: {tr('bessere Lage gefunden')} — {tr('Stützvolumen')} "
            f"{best.support_volume / 1000.0:.1f} cm³ {tr('statt')} "
            f"{current.support_volume / 1000.0:.1f} cm³ "
            f"({tr('Richtung')} ({direction}), {found.tried} {tr('Kandidaten')}). "
            + tr("Anwenden über orient_for_print.")
        )
    return lines
