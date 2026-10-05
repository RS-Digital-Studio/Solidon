"""Gemeinsame sichtbare Grundlage des Druckziels und der Übergabebewertung (RM-090).

Hier werden vorhandene Profilangaben erklärt, keine Prüfungen nachgerechnet.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.export.readback import Readback
from app.core.geom.difference import SceneDifference
from app.core.knowledge import profiles
from app.core.scene import EvaluationResult
from app.core.types import CheckState, Document, Finding, Profile, Scene, SceneObject
from app.i18n import TranslatableText, _, tr
from app.ui.labels import length


@dataclass(frozen=True, slots=True)
class PrintTarget:
    """Tatsächliche Kennungen und fehlende Grundlagen einer geöffneten Sitzung."""

    _title: TranslatableText
    _details: tuple[TranslatableText, ...]
    _missing: tuple[TranslatableText, ...]
    _materials: tuple[str | TranslatableText, ...]

    @property
    def title(self) -> str:
        return str(self._title)

    @property
    def details(self) -> str:
        lines = [str(line) for line in self._details]
        lines.insert(
            1,
            tr(
                "Material: {names}",
                names=", ".join(map(str, self._materials)) or tr("nicht angegeben"),
            ),
        )
        return "\n".join(lines)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(map(str, self._missing))


def missing_profile_basis(document: Document) -> tuple[str, ...]:
    """Fehlende ursprüngliche Grundlagen für die Kernprüfung, ohne Ersatzprofil."""
    printer = profiles.printer_profiles().get(document.printer or "")
    material = profiles.material_profiles().get(document.material or "")
    missing = []
    if printer is None:
        missing.append("printer")
    if material is None or (printer is not None and not material.fits(printer)):
        missing.append("material")
    return tuple(missing)


def print_target(document: Document, result: EvaluationResult | None) -> PrintTarget:
    """Liest streng aus dem geladenen Bestand; Ersatzprofile belegen keine Grundlage."""
    printers = profiles.printer_profiles()
    materials = profiles.material_profiles()
    printer = printers.get(document.printer or "")
    material = materials.get(document.material or "")
    missing = []
    if printer is None:
        missing.append(
            _(
                "Druckerprofil fehlt oder ist unbekannt: {name}",
                name=document.printer or _("nicht angegeben"),
            )
        )
    if material is None:
        missing.append(
            _(
                "Materialprofil fehlt oder ist unbekannt: {name}",
                name=document.material or _("nicht angegeben"),
            )
        )
    if printer is not None and material is not None and not material.fits(printer):
        missing.append(_("Material und Druckverfahren passen nicht zusammen."))
    names: list[str | TranslatableText] = []
    if material is not None and (result is None or not result.scene.objects):
        names.append(material.title)
    if result is not None:
        for body in result.scene.objects.values():
            base = next((slot for slot in body.material_slots if slot.index == 0), None)
            slot_material = (
                profiles.material_id_for_type(base.material_type)
                if base is not None and base.material_type
                else ""
            )
            wanted = body.material or slot_material or document.material
            own = materials.get(wanted or "")
            if own is None or (printer is not None and not own.fits(printer)):
                missing.append(
                    _(
                        "Materialgrundlage für „{name}“ fehlt oder passt nicht zum Verfahren.",
                        name=body.name,
                    )
                )
            elif own.title not in names:
                names.append(own.title)
            used = set(body.mesh.slot_indices) or {0}
            for slot in body.material_slots:
                if slot.index not in used or not slot.material_type:
                    continue
                identifier = profiles.material_id_for_type(slot.material_type)
                assigned = materials.get(identifier)
                if assigned is None or (printer is not None and not assigned.fits(printer)):
                    missing.append(
                        _(
                            "Materialart „{material}“ für „{name}“ hat keine passende "
                            "Bewertungsgrundlage.",
                            material=slot.material_type,
                            name=body.name,
                        )
                    )
                elif assigned.title not in names:
                    names.append(assigned.title)
    process = (
        ("Resin" if printer.is_resin else "FDM")
        if printer is not None
        else _("Verfahren unbekannt")
    )
    printer_name = (
        printer.title if printer is not None else (document.printer or _("Druckziel fehlt"))
    )
    title = _("{printer} · {process}", printer=printer_name, process=process)
    if missing:
        title = _("{target} · unvollständig", target=title)
    details = [
        title,
        _("Orientierung: aktuelle Lage der Körper zum Druckbett."),
    ]
    if printer is not None:
        details.insert(
            1,
            _(
                "Bauraum: {x} × {y} × {z} mm",
                x=f"{printer.build_volume[0]:g}",
                y=f"{printer.build_volume[1]:g}",
                z=f"{printer.build_volume[2]:g}",
            ),
        )
    details.extend(dict.fromkeys(missing))
    return PrintTarget(title, tuple(details), tuple(dict.fromkeys(missing)), tuple(names))


def handoff_state(findings: Iterable[Finding], incomplete: Iterable[str]) -> str:
    """Schwere Befunde bleiben vorrangig; leere Befunde ersetzen keinen Prüfabschluss."""
    severities = {finding.severity for finding in findings}
    if "error" in severities:
        return tr("Übergabe nicht empfohlen")
    if tuple(incomplete):
        return tr("Bewertung unvollständig")
    if "warning" in severities:
        return tr("Entscheidung erforderlich")
    return tr("Bereit zur Übergabe")


def finding_consequence(finding: Finding) -> str:
    """Die Folge eines Befunds für das Druckziel, aus derselben Regel wie der Status.

    Ein Fehler lässt die Übergabe nicht empfehlen, eine Warnung verlangt eine
    Entscheidung, ein Hinweis ändert nichts daran (:func:`handoff_state`).
    """
    if finding.severity == "error":
        return tr("Folge: Die Übergabe wird für das gewählte Druckziel nicht empfohlen.")
    if finding.severity == "warning":
        return tr("Folge: Ein Risiko für den Druck, das Sie vor der Übergabe beurteilen.")
    return tr("Folge: Ein Hinweis; die Übergabe hängt nicht davon ab.")


def check_summary(
    states: Iterable[CheckState],
    names: Mapping[str, str] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Erklärt tatsächliche Prüfzustände; ein leerer Satz bleibt unvollständig."""
    titles = {
        "evaluation": tr("Operationsverlauf"),
        "scene.fits": tr("Passungen"),
        "scene.placement": tr("Lage im Bauraum"),
        "scene.coincident_bodies": tr("Deckungsgleiche Körper"),
        "scene.thin_walls": tr("Wände an erkannten Bohrungen"),
        "scene.form_deviation": tr("Abweichung erkannter Formen"),
        "slice.settings": tr("Grundlage der Schichtanalyse"),
        "slice.print_findings": tr("Schichtanalyse"),
    }
    labels = {
        "not_started": tr("noch nicht durchgeführt"),
        "running": tr("läuft"),
        "completed": tr("durchgeführt"),
        "cancelled": tr("abgebrochen"),
        "failed": tr("nicht abgeschlossen"),
        "not_applicable": tr("nicht zutreffend"),
    }
    checks = tuple(states)
    lines = []
    missing = []
    for check in checks:
        scope = (
            f" · {(names or {}).get(check.object_id, check.object_id)}" if check.object_id else ""
        )
        line = tr("{check}{scope}: {state}").format(
            check=titles.get(check.key, check.key), scope=scope, state=labels[check.state]
        )
        lines.append(line)
        if check.state not in ("completed", "not_applicable") or check.missing_basis:
            missing.append(line)
    if not checks:
        missing.append(tr("Die unterstützten Prüfungen sind noch nicht vollständig nachgewiesen."))
    return "\n".join(lines), tuple(missing)


@dataclass(slots=True)
class ExplainedDifference(SceneDifference):
    """Dieselbe Kerndifferenz mit einer Erklärung aus genau ihrem Vorher/Nachher.

    ``change`` ist die eine Zeile, die sagt, was sich ändert; ``notes`` sind
    die Meldungen der Vorschau selbst. ``explanation`` setzt beides mit dem
    Stand der Druckprüfung zusammen — so, wie es im Vorschauband steht.
    """

    explanation: str = ""
    change: str = ""
    notes: tuple[str, ...] = ()


def _size(body: SceneObject) -> str:
    """Das Außenmaß eines Körpers in der Anzeigeeinheit, die Einheit einmal am Ende."""
    x, y, z = (float(value) for value in body.mesh.bounds.size)
    return " × ".join((length(x, with_unit=False), length(y, with_unit=False), length(z)))


def explain_difference(
    difference: SceneDifference,
    before: Scene | None,
    after: Scene,
    goal: str,
    *,
    affected: Iterable[str] = (),
) -> ExplainedDifference:
    """Liest vorhandene Kennzahlen im Vorschauarbeiter, ohne eine Ersatzprüfung.

    **Eine Zeile nennt, was sich ändert** (RM-516): das Ziel, die betroffenen
    Körper und von Außenmaß, Körperzahl und Material nur, was nicht bleibt.
    Bis dahin standen sieben Zeilen im Band, darunter „Körperzahl: 1 → 1“ und
    ein Außenmaß mit drei Nachkommastellen und festem „mm“, das sich nicht
    änderte. Was gleich bleibt, ist mit dem Körpernamen gesagt.
    """
    old = before.objects if before is not None else {}
    keys = tuple(
        key
        for key in dict.fromkeys(
            (*difference.entries, *difference.created, *difference.deleted, *affected)
        )
        if key in old or key in after.objects
    )
    kept: list[str] = []
    changes: list[str] = []
    for key in keys:
        previous, following = old.get(key), after.objects.get(key)
        if previous is None:
            assert following is not None
            changes.append(
                tr("„{name}“ neu: {size}").format(name=following.name, size=_size(following))
            )
            continue
        name = str(previous.name if following is None else following.name)
        if following is None:
            changes.append(tr("„{name}“ entfällt").format(name=name))
            continue
        # Verglichen wird, was dasteht: zwei Maße, die gleich geschrieben
        # werden, ändern für den Leser nichts (und kein ``==`` auf Fließkomma).
        sizes = _size(previous), _size(following)
        if sizes[0] != sizes[1]:
            changes.append(
                tr("„{name}“: {before} → {after}").format(
                    name=name, before=sizes[0], after=sizes[1]
                )
            )
        else:
            kept.append(name)
        if previous.material != following.material:
            materials = profiles.material_profiles()
            material_names = [
                str(materials[body.material].title)
                if body.material is not None and body.material in materials
                else body.material or tr("Material des Projekts")
                for body in (previous, following)
            ]
            changes.append(
                tr("Material „{name}“: {before} → {after}").format(
                    name=name, before=material_names[0], after=material_names[1]
                )
            )
    if len(old) != len(after.objects):
        changes.append(
            tr("{before} → {after} Körper").format(before=len(old), after=len(after.objects))
        )
    parts = [
        goal,
        ", ".join(kept) if kept or changes else str(tr("keine geometrische Änderung")),
        *changes,
    ]
    change = " · ".join(part for part in parts if part)
    notes = tuple(
        dict.fromkeys(
            str(finding.message) for finding in difference.findings if finding.severity != "info"
        )
    )
    return ExplainedDifference(
        entries=difference.entries,
        created=difference.created,
        deleted=difference.deleted,
        findings=difference.findings,
        explanation=_explained(change, tr("Druckbefunde noch nicht geprüft"), notes),
        change=change,
        notes=notes,
    )


def _explained(change: str, state: str, notes: Iterable[str], lines: Iterable[str] = ()) -> str:
    """Die Zeilen des Bands unter dem Titel: Änderung samt Prüfstand, Meldungen, Befunde."""
    head = " · ".join(part for part in (change, state) if part)
    return "\n".join(line for line in (head, *notes, *lines) if line)


def review_difference(
    difference: ExplainedDifference,
    reports: list[tuple[Finding, ...]],
    checked: list[tuple[CheckState, ...]],
) -> ExplainedDifference:
    """Erklärt zwei tatsächlich erneut geprüfte Stände mit derselben Druckgrundlage.

    **Genannt wird, was sich ändert, nicht der ganze Bericht zweimal.** Bis
    04.10.2026 stand jede Warnung beider Stände im Vorschauband — am
    Piratenschiff mit 32 Warnungen 64 Zeilen über dem Bild. Seit RM-516 auch
    keine Zählung „0 vorher, 0 nachher“ und keine Grundlagenzeile mehr: Ohne
    neuen oder behobenen Befund sagt die Änderungszeile „Druckbefunde
    unverändert“, sonst stehen höchstens drei Zeilen darunter.
    """
    before, after = (
        tuple(finding for finding in findings if finding.severity != "info") for findings in reports
    )
    missing = [note for states in checked for note in check_summary(states)[1]]
    known = {_identity(finding) for finding in before}
    lines = [
        tr("Neu: {finding}").format(finding=str(finding.message))
        for finding in after
        if _identity(finding) not in known
    ]
    if not missing:
        # Behoben heißt nur, was eine vollständige Gegenprüfung nicht mehr
        # findet; eine fehlende Meldung aus einer abgebrochenen ist keine.
        remaining = {finding.code for finding in after}
        lines.extend(
            tr("Behoben: {finding}").format(finding=message)
            for message in dict.fromkeys(
                str(finding.message) for finding in before if finding.code not in remaining
            )
        )
    state = (
        tr("Druckbefunde nicht vollständig geprüft")
        if missing
        else ""
        if lines
        else tr("Druckbefunde unverändert")
    )
    difference.explanation = _explained(difference.change, state, difference.notes, _at_most(lines))
    difference.findings += tuple(
        finding for finding in reports[1] if finding not in difference.findings
    )
    return difference


#: Wie viele Zeilen neue und behobene Befunde zusammen höchstens belegen (RM-516).
_SHOWN_LINES: Final = 3


def _identity(finding: Finding) -> tuple[str, str | None, str]:
    """Derselbe Befund in zwei Ständen: Kennung, Körper und Satz."""
    return finding.code, finding.object_id, str(finding.message)


def _at_most(lines: list[str], shown: int = _SHOWN_LINES) -> list[str]:
    """Höchstens ``shown`` Zeilen — die letzte zählt, was nicht mehr hineinpasst."""
    if len(lines) <= shown:
        return lines
    rest = len(lines) - (shown - 1)
    return [*lines[: shown - 1], tr("… und {count} weitere.").format(count=rest)]


def handoff_receipt(
    *,
    document: Document | None,
    profile: Profile,
    objects: Iterable[SceneObject],
    written: Iterable[Path],
    findings: Iterable[Finding],
    with_settings: bool,
    status: str,
    slicer: str = "",
    opened: Iterable[Path] = (),
    total_objects: int | None = None,
    checked: Readback | None = None,
) -> Finding:
    """Ein Beleg ausschließlich aus dem eingefrorenen Auftrag und echten Ausgabepfaden.

    ``checked`` ist die Gegenprobe des Kerns an den geschriebenen Dateien
    (``export.readback``). Ohne sie sagt der Beleg ausdrücklich, dass keine
    stattfand; weicht eine Datei ab, wird der Beleg selbst zur Warnung.
    """
    bodies = tuple(objects)
    paths = tuple(written)
    launched = tuple(opened)
    evidence = tuple(findings)
    if document is not None:
        basis = print_target(
            document, EvaluationResult(Scene(objects={b.id: b for b in bodies}))
        ).details
    else:
        basis = tr("Druckziel: {printer} · {material}").format(
            printer=str(profile.printer.title), material=str(profile.material.title)
        )
    details = [
        status,
        basis,
        tr("Umfang: {count} von {total} Körpern des eingefrorenen Auftrags.").format(
            count=len(bodies), total=total_objects if total_objects is not None else len(bodies)
        ),
        tr("Übergebene Körper: {names}").format(names=", ".join(str(body.name) for body in bodies)),
        tr("Platten: {plates}").format(
            plates=", ".join(str(p + 1) for p in sorted({b.plate for b in bodies}))
        ),
        tr("Geschriebene Dateien: {files}").format(
            files="\n".join(str(p) for p in paths) or tr("keine")
        ),
        tr("Format: {formats}; Koordinaten in Millimetern.").format(
            formats=", ".join(dict.fromkeys(p.suffix.lstrip(".").upper() for p in paths))
            or tr("keine Datei")
        ),
        tr("Druckeinstellungen: mitgegeben")
        if with_settings
        else tr("Druckeinstellungen: nicht mitgegeben"),
        tr("Orientierung: Lage des eingefrorenen Übergabeauftrags."),
        *_readback_lines(checked),
        tr(
            "Zahlen stammen aus Solidons Auftrag und Dateiausgabe. "
            "Eine G-Code-Prüfung ist ein eigener Schritt."
        ),
    ]
    if slicer:
        details.append(
            tr("Slicer: {name}; erfolgreich geöffnete Dateien: {count}").format(
                name=slicer, count=len(launched)
            )
        )
    risks = [str(f.message) for f in evidence if f.severity in ("warning", "error")]
    details.append(
        tr("Gemeldete Eigenschaftenverluste und Risiken: {risks}").format(
            risks="\n".join(dict.fromkeys(risks))
            or tr("keine gemeldet; dies ersetzt keine Gegenprüfung")
        )
    )
    deviated = checked is not None and checked.state == "deviated"
    return Finding(
        "ui.handoff_receipt",
        "warning" if deviated else "info",
        tr(
            "Beleg der letzten Übergabe: Die erneut eingelesene Datei weicht ab. "
            "Exportieren Sie erneut oder wählen Sie ein anderes Format."
        )
        if deviated
        else tr("Beleg der letzten Übergabe"),
        values={"detail": "\n".join(details)},
    )


def _readback_lines(checked: Readback | None) -> list[str]:
    """Die Gegenprobe, wie der Kern sie gemeldet hat — oder ausdrücklich keine."""
    if checked is None:
        return [
            tr(
                "Datei erneut eingelesen und verglichen: nicht durchgeführt; "
                "für diesen Weg liegt kein Gegenprüfergebnis vor."
            )
        ]
    lines = [str(checked.summary())]
    if checked.state == "deviated":
        lines.extend(str(note) for note in checked.notes)
    return lines
