"""Materialbedarf als Brücke zwischen Ausgabe, Projekt und Lager (§20, §29).

Eine Vorbereitung erkennt Wiederholungen, sie behauptet keinen erfolgten Druck.
Die Oberfläche bietet eine Buchung an; der Lagerkern schreibt sie atomar.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from app.core.export import threemf
from app.core.export.handover import configured_slots, override_for, settings_for_slot
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import profiles
from app.core.scene.hashing import digest, profile_key
from app.core.scene.serialise import print_settings_to_data
from app.core.slice.estimate import estimate
from app.core.slice.gcode import GcodeMetrics
from app.core.types import MaterialSlot, PrintSettings, Profile, SceneObject, SpoolBinding
from app.i18n import _, source_text

if TYPE_CHECKING:
    from app.core.knowledge.filaments import BookingPosition, CatalogueFilament

UsageSource = Literal["internal", "gcode", "manual"]


@dataclass(frozen=True, slots=True)
class UsageLine:
    """Ein Druckfilament mit belegtem oder ausdrücklich unbekanntem Bedarf."""

    slot: MaterialSlot
    grams: float | None
    spool_identifier: str = ""
    source: UsageSource = "internal"
    density: float | None = None
    diameter: float | None = None
    converted_from_length: bool = False


@dataclass(frozen=True, slots=True)
class UsageRequest:
    """Eine einzelne Platte mit ihrem unveränderlichen Ausgabeumfang."""

    fingerprint: str
    project_name: str
    plate: int
    lines: tuple[UsageLine, ...]


def costs_for(
    positions: Sequence[BookingPosition], entries: Mapping[str, CatalogueFilament]
) -> dict[str, float] | None:
    """Berechnet belegte Spulenkosten je Währung ohne Dateizugriff oder Rundung.

    Ein fehlender oder ungültiger Einzelwert lässt die gesamte Auswahl unbekannt.
    Eine leere Auswahl bleibt leer; ein ausdrücklich gespeicherter Nullpreis zählt.
    """
    totals: dict[str, float] = {}
    for position in positions:
        entry = entries.get(position.spool_identifier)
        if (
            entry is None
            or entry.price is None
            or not math.isfinite(entry.price)
            or entry.price < 0.0
            or entry.spool_grams is None
            or not math.isfinite(entry.spool_grams)
            or entry.spool_grams <= 0.0
            or not entry.currency.strip()
            or not math.isfinite(position.grams)
            or position.grams < 0.0
        ):
            return None
        amount = entry.price * (position.grams / entry.spool_grams)
        total = totals.get(entry.currency, 0.0) + amount
        if not math.isfinite(total):
            return None
        totals[entry.currency] = total
    return totals


def spool_for(settings: PrintSettings, slot: MaterialSlot) -> str:
    """Nur eine ausdrücklich gespeicherte Bindung gilt als Spulenwahl."""
    matches = {
        binding.spool_identifier
        for binding in settings.spool_bindings
        if binding.key == threemf.slot_identity(slot)
    }
    return next(iter(matches)) if len(matches) == 1 else ""


def with_spool(settings: PrintSettings, slot: MaterialSlot, identifier: str) -> PrintSettings:
    """Bindet eine Spule, ohne Filamentwerte oder Extrudernummern zu verändern."""
    kept = tuple(one for one in settings.spool_bindings if one.key != threemf.slot_identity(slot))
    if not identifier:
        return replace(settings, spool_bindings=kept)
    binding = SpoolBinding(identifier, slot.name, slot.colour, slot.material, slot.material_type)
    return replace(settings, spool_bindings=(*kept, binding))


def _material_properties(
    settings: PrintSettings, slot: MaterialSlot
) -> tuple[float | None, float | None]:
    """Nur belegte Materialwerte dürfen aus Volumen oder Länge Gramm machen."""
    override = override_for(settings, slot)
    # Ein gebundenes Herstellerprofil kann andere Kennwerte tragen als seine
    # Materialart. Ohne ausdrücklich übernommene Werte kennt diese Vorbereitung
    # weder seine Dichte noch seinen Durchmesser; der Slicer liest sie extern.
    if (slot.material or not profiles.material_id_for_type(slot.material_type or "")) and (
        override is None or override.filament is None
    ):
        return None, None
    density, diameter = settings.filament.density, settings.filament.diameter
    return (
        density if math.isfinite(density) and density > 0.0 else None,
        diameter if math.isfinite(diameter) and diameter > 0.0 else None,
    )


def prepare(
    objects: Sequence[SceneObject],
    settings: PrintSettings,
    profile: Profile,
    project_name: str,
    *,
    slots_by_plate: Mapping[int, Sequence[MaterialSlot]] | None = None,
) -> tuple[UsageRequest, ...]:
    """Liest die tatsächlich ausgegebenen Körper, nie eine spätere Auswahl.

    Ein Mehrmaterialkörper hat keine aus Oberflächen ableitbare Volumenaufteilung.
    Seine Einzelmengen bleiben unbekannt, bis G-Code oder Nutzereingaben vorliegen.

    Die 3MF verwendet exportweite Werkzeugnummern. Ein einzelner Slicer-Lauf
    übergibt seine vollständigen, bereits mit Profilen belegten Slots in der
    lokalen ``merge_slots``-Reihenfolge über ``slots_by_plate``. Ungenutzte
    Slots entfallen erst bei den Bedarfzeilen, nie bei dieser Zuordnung.
    """
    whole_job = [
        threemf.AssemblyPart(as_mesh_data(body.mesh), slots=threemf.slots_for_object(body))
        for body in objects
    ]
    requests = []
    for plate in sorted({entry.plate for entry in objects}):
        bodies = [entry for entry in objects if entry.plate == plate]
        parts = [
            threemf.AssemblyPart(as_mesh_data(body.mesh), slots=threemf.slots_for_object(body))
            for body in bodies
        ]
        supplied = slots_by_plate.get(plate) if slots_by_plate is not None else None
        slots = threemf.merge_slots(parts, across=whole_job if supplied is None else None)
        configured = configured_slots(slots, settings) if supplied is None else supplied
        effective_slots = {
            threemf.slot_identity(original): actual
            for original, actual in zip(slots, configured, strict=True)
        }
        identities = {
            key: (source_text(slot.name), slot.colour, slot.material, slot.material_type)
            for key, slot in effective_slots.items()
        }
        amounts: dict[threemf.SlotKey, float | None] = {
            threemf.slot_identity(slot): 0.0 for slot in slots
        }
        active_keys: set[threemf.SlotKey] = set()
        geometry = []
        for body in bodies:
            mesh = as_mesh_data(body.mesh)
            checksum = hashlib.sha256(mesh.raw.vertices.tobytes())
            checksum.update(mesh.raw.faces.tobytes())
            used = set(mesh.slots) if mesh.slots else {0}
            body_slots = threemf.assembly_slots(
                threemf.AssemblyPart(mesh, slots=threemf.slots_for_object(body))
            )
            active = [slot for slot in body_slots if slot.index in used]
            # Die Materialliste allein erkennt keinen Tausch zwischen Körpern.
            # Jeder lokale Flächenslot trägt deshalb seine effektive Identität;
            # die Werkzeugnummer eines späteren Slicer-Laufs bleibt außen vor.
            assigned = sorted(
                (slot.index, identities[threemf.slot_identity(slot)]) for slot in active
            )
            geometry.append((str(body.id), checksum.hexdigest(), mesh.slots, assigned))
            keys = {threemf.slot_identity(slot) for slot in active}
            active_keys.update(keys)
            if len(keys) != 1:
                for key in keys:
                    amounts[key] = None
                continue
            slot = active[0]
            key = threemf.slot_identity(slot)
            previous = amounts.get(key)
            if previous is not None:
                actual = effective_slots[key]
                mine = settings_for_slot(settings, profile, actual)
                density, _diameter = _material_properties(mine, actual)
                amounts[key] = (
                    previous + estimate(mesh.volume, mesh.area, mine).grams
                    if density is not None
                    else None
                )
        lines = []
        effective = []
        for original in slots:
            key = threemf.slot_identity(original)
            if key not in active_keys:
                continue
            slot = effective_slots[key]
            mine = settings_for_slot(settings, profile, slot)
            density, diameter = _material_properties(mine, slot)
            values = print_settings_to_data(mine)
            # Die aufgelösten Werte stehen bereits in ``mine`` und ``slot``.
            # Unbenutzte Profil-/Wertelisten sowie eine andere Werkzeugnummer
            # dürfen aus 3MF und anschließendem Slicen keine zwei Drucke machen.
            for field in (
                "id",
                "title",
                "handover",
                "spool_bindings",
                "inventory_project_id",
                "slot_profiles",
                "slot_profile_bindings",
                "slot_overrides",
            ):
                values.pop(field, None)
            effective.append((identities[key], values))
            lines.append(
                UsageLine(
                    slot=slot,
                    grams=amounts.get(key),
                    spool_identifier=spool_for(settings, original),
                    density=density,
                    diameter=diameter,
                )
            )
        fingerprint = digest(
            settings.inventory_project_id,
            plate,
            sorted(geometry),
            sorted(effective, key=digest),
            profile_key(profile),
        )
        requests.append(UsageRequest(fingerprint, project_name, plate, tuple(lines)))
    return tuple(requests)


def _only_tool(metrics: GcodeMetrics, index: int) -> bool:
    """Andere genannte Werkzeuge müssen ausdrücklich unbenutzt sein.

    Ein einzelnes Modellmaterial schließt Stützmaterial aus dem Slicer nicht
    aus. Deshalb darf die Gesamtsumme keinen fremden oder fehlenden Einzelwert
    übernehmen; ein direkt genannter Grammwert gewinnt dabei vor der Länge.
    """
    if any(tool != index for tool in metrics.used_tools):
        return False
    weights, lengths = metrics.filament_grams_by_tool, metrics.filament_mm_by_tool
    for tool in range(max(len(weights), len(lengths))):
        if tool == index:
            continue
        amount = weights[tool] if tool < len(weights) else None
        if amount is None:
            amount = lengths[tool] if tool < len(lengths) else None
        if amount is None or not math.isfinite(amount) or abs(amount) > 0.0:
            return False
    return True


def from_gcode(request: UsageRequest, metrics: GcodeMetrics) -> UsageRequest:
    """Erhält Werkzeugnummern; ein Gesamtwert wird niemals aufgeteilt."""
    count = max(len(metrics.filament_grams_by_tool), len(metrics.filament_mm_by_tool))
    densities: list[float | None] = [None] * count
    diameters: list[float | None] = [None] * count
    for line in request.lines:
        if 0 <= line.slot.index < count:
            densities[line.slot.index] = line.density
            diameters[line.slot.index] = line.diameter
    weights = metrics.grams_by_tool(densities=densities, diameters=diameters)
    lines = []
    for line in request.lines:
        index = line.slot.index
        grams = weights[index] if index < len(weights) else None
        converted = grams is not None and (
            index >= len(metrics.filament_grams_by_tool)
            or metrics.filament_grams_by_tool[index] is None
        )
        if grams is None and len(request.lines) == 1 and _only_tool(metrics, index):
            single = GcodeMetrics(
                filament_grams_by_tool=(metrics.filament_grams,),
                filament_mm_by_tool=(metrics.filament_mm,),
            )
            grams = single.grams_by_tool(densities=(line.density,), diameters=(line.diameter,))[0]
            converted = grams is not None and metrics.filament_grams is None
        if grams is not None and (not math.isfinite(grams) or grams < 0.0):
            grams = None
            converted = False
        lines.append(replace(line, grams=grams, source="gcode", converted_from_length=converted))
    represented = {line.slot.index for line in request.lines}
    for index in sorted(set(range(len(weights))) | set(metrics.used_tools)):
        if index in represented:
            continue
        grams = weights[index] if index < len(weights) else None
        stated = (
            metrics.filament_grams_by_tool[index]
            if index < len(metrics.filament_grams_by_tool)
            else None
        )
        length = (
            metrics.filament_mm_by_tool[index] if index < len(metrics.filament_mm_by_tool) else None
        )
        evidence = stated if stated is not None else length
        if evidence is None and index not in metrics.used_tools:
            continue
        if evidence is not None and (not math.isfinite(evidence) or evidence <= 0.0):
            continue
        # Ein Slicer kann ein zusätzliches Stützfilament verwenden. Seine
        # Werkzeugnummer belegt keine Materialart und keine lokale Spule.
        # Auch eine belegte Länge erhält ohne Materialdaten keine Grammzahl.
        lines.append(
            UsageLine(
                slot=MaterialSlot(
                    index=index,
                    name=_("Zusätzliches Filament · Werkzeug {number}", number=index + 1),
                ),
                grams=grams
                if grams is not None and math.isfinite(grams) and grams >= 0.0
                else None,
                source="gcode",
            )
        )
    return replace(request, lines=tuple(lines))
