"""Materialbedarf als Brücke zwischen Ausgabe, Projekt und Lager (§20, §29).

Eine Vorbereitung erkennt Wiederholungen, sie behauptet keinen erfolgten Druck.
Die Oberfläche bietet eine Buchung an; der Lagerkern schreibt sie atomar.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, fields, replace
from functools import cmp_to_key
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Literal

from app.core import expressions
from app.core.errors import AppError
from app.core.export import threemf
from app.core.export.handover import (
    SLOT_GROUPS,
    SlicerSetup,
    bind_object_profiles,
    configured_slots,
    override_for,
    settings_for_slot,
)
from app.core.geom import mesh as geom_mesh
from app.core.knowledge import print_settings, profiles
from app.core.scene.hashing import digest, profile_key
from app.core.scene.migrations import SAVED_IRONING
from app.core.scene.serialise import print_settings_to_data
from app.core.slice.estimate import estimate
from app.core.slice.gcode import GcodeMetrics
from app.core.types import (
    Document,
    MaterialSlot,
    ObjectId,
    Operation,
    OpId,
    Parameter,
    ParameterName,
    PrintSettings,
    Profile,
    SceneObject,
    SourceAccess,
    SpoolBinding,
)
from app.core.units import PRINT_LIMIT
from app.i18n import _, source_text

if TYPE_CHECKING:
    from app.core.knowledge.filaments import BookingPosition, CatalogueFilament
    from app.core.scene.project import Project

UsageSource = Literal["internal", "gcode", "manual"]

#: Die Einstellungsfelder, über die Solidon 0.5.3 den Abdruck einer Buchung
#: bildete, je Gruppe (RM-705, gelesen aus ``git show v0.5.3:app/core/types.py``).
#: Ein Feld, das danach dazukam, zählt nur, wo es vom Herstellerprofil abweichen
#: soll (:func:`_without_later_fields`) — sonst fände Solidon nach jedem Update
#: keine Buchung von davor. Die Menge wächst nie; der Test
#: ``test_filament_usage_fingerprint_history.py`` hält sie gegen den Tag.
FINGERPRINT_FIELDS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "layers": frozenset(
            {"first_layer_height", "first_layer_line_width", "layer_height", "line_width"}
        ),
        "shell": frozenset(
            {
                "bottom_layers",
                "ironing",
                "outer_wall_first",
                "precise_outer_wall",
                "scarf_seam",
                "seam_position",
                "top_layers",
                "wall_count",
                "wall_generator",
            }
        ),
        "infill": frozenset({"angle", "density", "pattern"}),
        "filament": frozenset(
            {"colour", "cost_per_kg", "density", "diameter", "flow_ratio", "max_flow"}
        ),
        "temperature": frozenset(
            {"bed", "bed_first_layer", "chamber", "nozzle", "nozzle_first_layer"}
        ),
        "cooling": frozenset(
            {
                "bridge_fan_speed",
                "disable_first_layers",
                "fan_below_layer_time",
                "fan_speed",
                "minimum_fan_speed",
                "minimum_layer_time",
            }
        ),
        "speed": frozenset(
            {
                "acceleration",
                "bridge",
                "first_layer",
                "infill",
                "inner_wall",
                "outer_wall",
                "outer_wall_acceleration",
                "top_surface",
                "travel",
            }
        ),
        "support": frozenset(
            {
                "block_channels",
                "density",
                "interface_layers",
                "placement",
                "style",
                "threshold_angle",
                "xy_gap",
                "z_gap",
            }
        ),
        "adhesion": frozenset(
            {
                "brim_gap",
                "brim_width",
                "kind",
                "raft_gap",
                "raft_layers",
                "skirt_distance",
                "skirt_loops",
            }
        ),
        "retraction": frozenset({"avoid_crossing_walls", "length", "speed", "wipe", "z_hop"}),
    }
)

#: Die Altkennungen: welche Brim-/Raftfelder fehlen und ob die Wahl der Platte
#: fehlt. 0.5.1 kannte weder die Abstände noch ``plate_choices`` (RM-705).
_LEGACY_SHAPES: Final = (
    ((), False),
    (("brim_gap",), False),
    (("raft_gap",), False),
    (("brim_gap", "raft_gap"), False),
    (("brim_gap", "raft_gap"), True),
)

#: Die Bildung des Abdrucks aus gespeicherten Eingängen (RM-706). Sie steht
#: vorn im Abdruck, damit er nie einem über ausgewertete Netze gleicht. Wer die
#: Bildung ändert, ändert jeden Abdruck und führt den alten als Vorabdruck mit
#: (Regel ``verbrauch.md``).
STORED_INPUTS: Final = "stored-inputs-1"

#: Steht vor jedem Abdruck aus gespeicherten Eingängen, lesbar im Lager: Eine
#: Buchung ohne dieses Zeichen stammt aus 0.5 und hängt an Netzbits, die eine
#: druckgleiche Beschleunigung umordnet (Review Altbuchung, M1). Das Lager
#: verlangt vom Abdruck nur einen nichtleeren Text; ein Formatschritt entfällt.
STORED_MARK: Final = "si1-"


def from_stored_inputs(fingerprint: str) -> bool:
    """Wurde dieser Abdruck aus gespeicherten Eingängen gebildet (ab 0.6.0)?"""
    return fingerprint.startswith(STORED_MARK)


@dataclass(frozen=True, slots=True)
class StoredInputs:
    """Was ein Projekt gespeichert hat, aus dem seine Körper entstehen (RM-706).

    Der Abdruck einer Buchung benennt einen Körper über seine Eingänge statt
    über die Bits seines ausgewerteten Netzes: Druckgleich (Bauplan §11.2)
    darf Punkte innerhalb der Druckgrenze verschieben, Dreiecke umsortieren
    und Netze schmaler halten, und jede solche Beschleunigung machte sonst aus
    einem gebuchten Druck einen neuen.

    ``sources`` liefert die Inhaltsprüfsumme einer Quelle auch vor dem ersten
    Speichern (``ProjectSources.identity``); ohne sie gilt die gespeicherte.
    ``stopped_at`` ist der Halt der Auswertung, aus der die Körper stammen —
    was danach steht, hat nicht gerechnet.
    """

    document: Document
    sources: SourceAccess | None = None
    stopped_at: OpId | None = None
    known: Mapping[ObjectId, str] | None = None
    """Schon gerechnete Abdrücke je Körper (:meth:`settled`)."""

    @classmethod
    def snapshot(
        cls,
        project: Project,
        *,
        base_dir: Path | None = None,
        stopped_at: OpId | None = None,
        document: Document | None = None,
    ) -> StoredInputs:
        """Ein fester Stand für einen Arbeiter: Das Fenster rechnet weiter, die
        Ausgabe liest das Dokument und die Quellen von jetzt. ``document`` ist
        eine schon gezogene Kopie, sonst wird eine gezogen."""
        from app.core.scene import project as container

        held = document if document is not None else deepcopy(project.document)
        copy = container.Project(document=held, sources=dict(project.sources))
        return cls(held, container.ProjectSources(copy, base_dir=base_dir), stopped_at)

    def bodies(self) -> dict[ObjectId, str]:
        """Je Körper des Endstands ein Abdruck seiner gespeicherten Eingänge."""
        if self.known is not None:
            return dict(self.known)
        return _stored_bodies(self)

    def settled(self) -> StoredInputs:
        """Derselbe Stand mit gerechneten Abdrücken — für einen Arbeiter, der je
        Platte bucht: Ein Gang über den Stapel liest jede verknüpfte Quelle ganz
        (Review RM-706, L5). Nur für einen festen Stand (:meth:`snapshot`)."""
        if self.known is not None:
            return self
        return replace(self, known=self.bodies())


def _stored_bodies(stored: StoredInputs) -> dict[ObjectId, str]:
    """Geht den Stapel wie die Auswertung durch, ohne ein Netz zu rechnen.

    Je Schritt gehen ein: Name, gespeicherte Werte, Startwert, die Abdrücke
    seiner Eingänge, was er an ihnen vorbei liest (:func:`_read_beside`), die
    Fassung eines Bausteins und die Entscheidungen seiner gespeicherten
    Antworten (:func:`_answers`). Nicht ein gehen, was nur ein Ergebnis
    beschreibt — Rückfallstufe, Übersetzungsvermerk —
    und keine Fassung einer Umsetzung (``cache_version``): Genau die steigt bei
    einer druckgleichen Beschleunigung. Ein Schritt, der nur benennt oder
    prüft (``unchanged_effect``), und ein unverändert durchgereichter Eingang
    (``leaves_inputs_unchanged``) behalten den Abdruck ihres Körpers.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _without_stray_inputs

    document = stored.document
    live: dict[ObjectId, str] = {}
    for operation in sorted(document.ops, key=lambda entry: entry.id):
        if operation.id == stored.stopped_at:
            break
        if operation.suppressed is not None:
            continue
        if not REGISTRY.has(operation.op):
            # Die Auswertung hält hier an (``evaluate.unknown_operation``).
            break
        spec = REGISTRY.get(operation.op)
        # Ein Erzeuger mit Eingängen aus einer alten Datei verliert sie, wie in
        # der Auswertung — dieselbe Funktion, kein Nachbau (Review RM-706, L1).
        operation, _stray = _without_stray_inputs(operation, spec)
        inputs = [live.get(name) or digest("absent", name) for name in operation.inputs]
        carried = dict(zip(operation.inputs, inputs, strict=True))
        step = (
            ""
            if spec.unchanged_effect
            else digest(
                STORED_INPUTS,
                operation.op,
                dict(operation.params),
                operation.seed,
                inputs,
                _read_beside(spec, operation, live, stored),
                _part_versions(operation),
                _answers(operation.matches),
            )
        )
        for name in operation.inputs:
            if name not in operation.outputs:
                live.pop(name, None)
        for index, name in enumerate(operation.outputs):
            if name in carried and (spec.unchanged_effect or spec.leaves_inputs_unchanged):
                live[name] = carried[name]
            elif spec.unchanged_effect:
                live[name] = inputs[index] if index < len(inputs) else digest("absent", name)
            else:
                live[name] = digest(step, index)
    return live


def _read_beside(
    spec: Any, operation: Operation, live: Mapping[ObjectId, str], stored: StoredInputs
) -> dict[str, Any]:
    """Was ein Schritt außer seinen Eingängen liest — dieselben Lesarten wie
    ``evaluate._with_nested_context``, aus dem Dokument statt aus Netzen.

    Quellen gehen mit Inhaltsprüfsumme und Dateiname ein, Projektmaße mit ihrer
    gespeicherten Angabe samt allem, was ihr Ausdruck liest. Liest ein Schritt
    andere Körper — die Szene, ein benanntes Merkmal, die Ebene einer Skizze —,
    gehen **alle** lebenden Körper ein: Welcher Körper ein Merkmal trägt, sagt
    erst die Auswertung, und lieber kippt ein Abdruck einmal zu oft als dass
    zwei verschiedene Drucke denselben tragen.
    """
    from app.core.registry.params import reads_scene
    from app.core.scene.evaluate import SOURCE_KINDS, nested_references
    from app.core.scene.orphans import feature_ref_of_sketch

    params = operation.params
    context: dict[str, Any] = {}
    reads_bodies = spec.reads_other_bodies or reads_scene(spec.params, params)
    names: set[str] = set()
    # Ein unlesbarer Ausdruck hält die Auswertung an; sein Text steht oben.
    with suppress(AppError):
        names |= expressions.used_parameters(params.values())
    collectors = nested_references()
    for entry in spec.params.spec():
        value = params.get(entry.name)
        if entry.kind in SOURCE_KINDS:
            if isinstance(value, str) and value:
                context[f"#{entry.name}"] = _source_identity(stored, value)
            continue
        if value and (entry.kind in ("feature", "features") or entry.targets_feature):
            reads_bodies = True
        if entry.kind == "sketch" and isinstance(value, str) and value:
            reads_bodies = reads_bodies or feature_ref_of_sketch(value) is not None
        collect = collectors.get(entry.kind)
        if collect is not None and isinstance(value, str) and value:
            names |= collect(value)
    if reads_bodies:
        context["#scene"] = sorted(live.items())
    if names:
        context["@"] = _declared(stored.document.parameters, names)
    return context


def _source_identity(stored: StoredInputs, source_id: str) -> list[str]:
    """Inhaltsprüfsumme und Dateiname einer Quelle, wie der Cache-Schlüssel sie liest."""
    source = stored.document.sources.get(source_id)
    identity = ""
    if stored.sources is not None:
        try:
            identity = stored.sources.identity(source_id)
        except AppError:
            # Eine verknüpfte Quelle, die gerade fehlt, behält ihren
            # gespeicherten Abdruck (``scene/CLAUDE.md``, „Verknüpfte Quellen“).
            identity = ""
    if not identity and source is not None:
        identity = source.sha256
    # Getrennt wird auf jeder Plattform gleich: Ein Pfad aus einer Windows-Datei
    # gäbe unter Linux sonst einen anderen Namen und einen anderen Abdruck.
    name = PurePosixPath(source.path.replace("\\", "/")).name if source is not None else ""
    return [identity, name]


def _declared(parameters: Mapping[ParameterName, Parameter], names: set[str]) -> dict[str, object]:
    """Die gelesenen Projektmaße, wie gespeichert: Ausdruck oder Zahl, samt Kette.

    Nicht der aufgelöste Wert — der Ausdruck selbst ist die Eingabe, und so
    hängt der Abdruck an keiner Rechnung, die auf einer Plattform anders runden
    könnte.
    """
    declared: dict[str, object] = {}
    waiting = sorted(names)
    while waiting:
        name = waiting.pop()
        if name in declared:
            continue
        parameter = parameters.get(name)
        if parameter is None:
            declared[name] = None
        elif parameter.expression:
            declared[name] = ["=", parameter.expression]
            with suppress(AppError):
                waiting.extend(sorted(expressions.references(parameter.expression)))
        else:
            declared[name] = parameter.value
    return declared


#: In welcher Folge die Felder eines gespeicherten Kandidaten ihn ordnen: die
#: Lage zuerst. Zwei Kandidaten einer Frage liegen an verschiedenen Stellen,
#: Richtung und Länge teilen sie oft bis aufs Bit.
_EDGE_ORDER: Final = ("middle", "direction", "extent", "length")
_FEATURE_ORDER: Final = ("relative", "axis", "diameter", "kind", "directional")


def _answers(matches: Mapping[str, Any]) -> list[object]:
    """Die gespeicherten Antworten eines Schritts als Entscheidung, nicht als
    Datensatz (Review RM-706, M1).

    Eine Kantenantwort wählt die Geometrie des Verbrauchers
    (``scene.edge_binding``), eine Merkmalszuordnung das Merkmal, nach dem ein
    späterer Schritt greift (§21.3) — eine andere Antwort ist ein anderer Druck.
    Ein geht, was entschieden ist: Domäne, Körper, Feld und Schlüssel stehen im
    Schlüssel des Datensatzes, dazu je Entscheidung der Rang des gewählten
    Kandidaten in der Ordnung nach seiner Lage, oder ``not_carried``. Nicht ein
    gehen ``scope`` (der Hash des Eingangs, er steigt mit ``cache_version``) und
    die Rohkoordinaten: Eine neu gestellte und gleich beantwortete Frage behält
    den Abdruck.
    """
    from app.core.perceive.match_records import (
        EDGE_DOMAIN,
        GROUP_DOMAIN,
        NATIVE_DOMAIN,
        RECOGNITION_DOMAIN,
        domain_of,
    )

    answers: list[object] = []
    for key in sorted(matches):
        record = matches[key]
        domain = domain_of(key)
        decided: object
        try:
            if domain == EDGE_DOMAIN:
                decided = {
                    name: _rank(record["candidates"][name], choice["candidate"], _EDGE_ORDER)
                    for name, choice in record["decisions"].items()
                }
            elif domain in (GROUP_DOMAIN, NATIVE_DOMAIN):
                found = [candidate["fingerprint"] for candidate in record["candidates"]]
                decided = {
                    name: "not_carried"
                    if choice.get("not_carried") is True
                    else _rank(found, choice["candidate"], _FEATURE_ORDER)
                    for name, choice in record["decisions"].items()
                }
            elif domain == RECOGNITION_DOMAIN:
                decided = [record["allowed"], record.get("out_of_memory", False)]
            else:
                decided = _without_scope(record)
        except KeyError, IndexError, TypeError, AttributeError, ValueError:
            # Ein Datensatz fremder Form geht ganz ein — ohne seinen Scope.
            decided = _without_scope(record)
        answers.append([key, decided])
    return answers


def _without_scope(record: object) -> object:
    if isinstance(record, Mapping):
        return {name: value for name, value in record.items() if name != "scope"}
    return record


def _rank(candidates: Sequence[Any], chosen: int, order: Sequence[str]) -> int:
    """Die Stelle des gewählten Kandidaten, wenn alle nach ihrer Lage geordnet sind.

    Zahlen, die näher als die Druckgrenze beieinanderliegen (``PRINT_LIMIT``), sind
    für die Ordnung gleich, und das nächste Feld entscheidet (Nachprüfung RM-706,
    N2): Liegen zwei Kanten eines Spalts in x bis auf Rauschen gleich, ordnet sie
    y, nicht das letzte Bit von x. Gerundet wird nicht — ein Raster kippt an seinen
    Kanten.
    """
    places = [_place(candidate, order) for candidate in candidates]

    def by_place(first: int, second: int) -> int:
        return _compare(places[first], places[second])

    ranked = sorted(range(len(candidates)), key=cmp_to_key(by_place))
    return ranked.index(chosen)


def _compare(first: Sequence[tuple[int, Any]], second: Sequence[tuple[int, Any]]) -> int:
    """Vergleicht zwei Folgen aus :func:`_leaves`, Zahlen bis auf die Druckgrenze."""
    for (kind, value), (other_kind, other) in zip(first, second, strict=False):
        if kind != other_kind:
            return -1 if kind < other_kind else 1
        if kind == 1 and abs(value - other) <= PRINT_LIMIT:
            continue
        if value != other:
            return -1 if value < other else 1
    if len(first) != len(second):
        return -1 if len(first) < len(second) else 1
    # Bis auf die Druckgrenze gleich: Die genauen Zahlen halten die Ordnung bestimmt.
    return (tuple(first) > tuple(second)) - (tuple(first) < tuple(second))


def _place(candidate: Mapping[str, Any], order: Sequence[str]) -> tuple[tuple[int, Any], ...]:
    """Die Felder eines Kandidaten als vergleichbare Folge, die genannten vorn."""
    names = [*order, *sorted(name for name in candidate if name not in order)]
    return _leaves([candidate.get(name) for name in names])


def _leaves(value: object) -> tuple[tuple[int, Any], ...]:
    """Flach und vergleichbar: Zahlen vor Texten, je mit eigener Marke."""
    if isinstance(value, Mapping):
        return tuple(leaf for name in sorted(value, key=str) for leaf in _leaves(value[name]))
    if isinstance(value, list | tuple):
        return tuple(leaf for entry in value for leaf in _leaves(entry))
    if value is None or isinstance(value, bool):
        return ((0, int(bool(value))),)
    if isinstance(value, int | float):
        return ((1, float(value)),)
    return ((2, str(value)),)


def _part_versions(operation: Operation) -> list[str]:
    """Die Fassung des Bausteins, den ein Schritt setzt: Maßänderungen tragen
    eine neue (``PartChange``), eigene Bausteine den Abdruck ihrer Datei."""
    from app.core.knowledge.parts import recipe
    from app.core.knowledge.parts.registry import PARTS, used_parts

    versions: list[str] = []
    pending = list(used_parts([operation]))
    seen: set[str] = set()
    while pending:
        name = pending.pop(0)
        if name in seen or not PARTS.has(name):
            continue
        seen.add(name)
        spec = PARTS.get(name)
        versions.append(spec.version)
        if spec.recipe_data is None:
            continue
        # Ein Rezept setzt Bibliotheksbausteine; deren Maßänderung ändert den
        # Druck, nicht aber das Rezept (Review RM-706, L3) — wie
        # ``recipe._collect_dependencies`` durch die Rezepte hindurch.
        try:
            nested = recipe.from_data(dict(spec.recipe_data)).document.ops
        except AppError, ValueError, KeyError, TypeError:
            continue
        pending.extend(used_parts(nested))
    return versions


#: Wie Format 51 das Bügeln speicherte (RM-588): als Schalter, ``True`` für
#: jede Oberseite. Der Abdruck einer Buchung aus 0.5.3 oder 0.6.0 trägt den
#: Schalter; dieselbe Wahl heißt seit Format 52 „none“ oder „top_surfaces“
#: und muss denselben Abdruck geben. „topmost“ gab es davor nicht. Die Umkehrung
#: der Migration, nicht eine zweite Tabelle (Integrationsreview welle4, T2-G2).
_SAVED_IRONING: Final[Mapping[str, bool]] = MappingProxyType(
    {choice: switch for switch, choice in SAVED_IRONING.items()}
)


def _as_saved(path: str, value: object) -> object:
    """Ein Wert im Abdruck so, wie ihn die Datei vor Format 52 trug (RM-588)."""
    if path == "shell.ironing" and isinstance(value, str):
        return _SAVED_IRONING.get(value, value)
    return value


def _saved_data(settings: PrintSettings) -> dict[str, Any]:
    """Die Einstellungen als Daten, das Bügeln so, wie Format 51 es trug (RM-588)."""
    data = print_settings_to_data(settings)
    data["shell"]["ironing"] = _as_saved("shell.ironing", data["shell"]["ironing"])
    data["plate_choices"] = {
        path: _as_saved(path, value) for path, value in data["plate_choices"].items()
    }
    return data


def _owned_settings(settings: PrintSettings, slot: MaterialSlot) -> dict[str, object]:
    """Was an den Einstellungen dieser Spule dem Projekt gehört (Review RM-705, N3).

    Stufe, eigene Wahl und übernommene Vorschläge (``explicit`` — woher ein
    Wert kommt, ändert den Druck nicht, H10), die Wahl der Platte und die
    eigenen Werte der Spule ohne ihre geerbten Felder (RM-707). Die Grundlage
    fehlt: Ein Update des Slicers oder eine neue Grundlage in Solidon
    (Cura, RM-583) benennt keinen anderen Druck.
    """
    override = override_for(settings, slot)
    spool: dict[str, dict[str, object]] = {}
    if override is not None:
        for group in SLOT_GROUPS:
            section = getattr(override, group)
            if section is None:
                continue
            spool[group] = {
                entry.name: getattr(section, entry.name)
                for entry in fields(section)
                if f"{group}.{entry.name}" not in override.inherited
            }
    return {
        "quality": settings.quality,
        "explicit": [
            [path, _as_saved(path, print_settings.read_path(settings, path))]
            for path in sorted(settings.explicit)
        ],
        "plate_choices": [(path, _as_saved(path, value)) for path, value in settings.plate_choices],
        "spool": spool,
    }


def _base_choice(base: SlicerSetup | None) -> list[str] | None:
    """Welche Grundlage der Slicer nimmt — die Wahl, nicht ihr Inhalt (Review RM-706, M2).

    Ein eigener Prozess lässt die Stufe stehen und ändert Schichthöhe, Wände und
    Tempo; Maschine und Slicerart ebenso. Ihre Namen gehören zum Druck, ihre
    Werte nicht: Ein Slicer-Update unter denselben Namen benennt keinen anderen
    Druck. Wo der Slicer liegt, zählt nicht (:func:`_profile_name`).
    """
    if base is None:
        return None
    return [base.flavour, _profile_name(base.machine_profile), _profile_name(base.base_process)]


#: Was an einem Profildateinamen Endung ist, nicht Name — die längeren zuerst.
_PROFILE_SUFFIXES: Final = (".def.json", ".inst.cfg", ".json", ".ini", ".cfg")


def _profile_name(choice: str) -> str:
    """Der Name eines gewählten Profils, nie sein Pfad (Nachprüfung RM-706, N1; Regel 12).

    Die Orca-Familie kennt ein Profil am Pfad seiner Datei
    (``slicer_profiles.identity``), und Creality Print legt Installation und
    Nutzerdaten in Ordnern mit Fassungsnummer ab: Am Pfad gezählt, machte jedes
    Update jeden gebuchten Druck neu, ebenso ein anderer Rechner. Der Dateiname
    ist dort der Profilname. Prusa-Abschnitte und Cura-Instanzen tragen schon
    einen Namen und bleiben, wie sie sind.
    """
    if "/" not in choice and "\\" not in choice:
        return choice
    name = PurePosixPath(choice.replace("\\", "/")).name
    lowered = name.lower()
    for suffix in _PROFILE_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _fixed_profile(profile: Profile) -> str:
    """Drucker und Material, wie jeder Schritt sie liest (Review RM-706, S1).

    Dieselben festen Werte wie im Cache-Schlüssel (``profile_key`` ohne
    Prozesswerte): Spiel, Presssitz, Lochzugabe, Elefantenfuß, Schrumpf und die
    Mechanikwerte gehen in jede Geometrie mit einem ``auto:<material>``-Maß ein,
    und eine Kalibrierung (Bauplan §28.3) rechnet jedes Projekt danach neu — ein
    anderer Druck. Bewusst grob wie der Schlüssel: Auch ein schlichter Quader
    kippt mit, lieber einmal zu oft als zwei Drucke unter einem Namen. Die
    Prozesswerte fehlen; ihre Grundlage benennt die Wahl des Prozesses.
    """
    return profile_key(profile, process=False)


def _body_profile(profile: Profile, body: SceneObject) -> str:
    """Das feste Profil, mit dem dieser Körper rechnet: das eigene Material des
    Körpers oder seiner Spule, wo er eines hat (``profiles.for_object``)."""
    try:
        return _fixed_profile(profiles.for_object(profile, body))
    except AppError:
        # Ein Material, das dieser Rechner nicht kennt, rechnet hier nicht —
        # sein Name steht trotzdem für sich.
        return digest("unknown-material", body.material)


def _step_materials(profile: Profile, document: Document) -> list[str]:
    """Die festen Profile der Materialien, die ein Schritt benennt (Dichtung,
    Klemme; ``OperationSpec.material_params``) — wie der Cache-Schlüssel sie liest."""
    from app.core.registry import REGISTRY

    keys: set[str] = set()
    for operation in document.ops:
        if operation.suppressed is not None or not REGISTRY.has(operation.op):
            continue
        for name in REGISTRY.get(operation.op).material_params:
            chosen = operation.params.get(name)
            if not isinstance(chosen, str) or not chosen:
                continue
            try:
                material = profiles.material(chosen)
            except AppError:
                keys.add(digest("unknown-material", chosen))
                continue
            keys.add(_fixed_profile(Profile(printer=profile.printer, material=material)))
    return sorted(keys)


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
    legacy_fingerprints: tuple[str, ...] = ()
    """Mögliche Altkennungen vor Brim-/Raftfeldern (bis 0.5.1); niemals belegte Gleichheiten."""
    former_fingerprints: tuple[str, ...] = ()
    """Derselbe Druck nach der Bildung vor RM-706, über die ausgewerteten Netze.

    Anders als ``legacy_fingerprints`` eine **belegte Gleichheit**: So hieß
    dieser Druck von 0.5.2 bis 0.6.0, solange seine Netzbits gleich sind. Eine
    Buchung darunter ist derselbe Druck und behält ihren Abdruck."""

    @property
    def identities(self) -> tuple[str, ...]:
        """Jeder Abdruck, unter dem dieser Druck schon gebucht sein kann."""
        return (self.fingerprint, *self.former_fingerprints)


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


def _without_later_fields(
    values: dict[str, Any], settings: PrintSettings, slot: MaterialSlot, profile: Profile
) -> None:
    """Nimmt jedes Feld nach 0.5.3 aus dem Abdruck, das nur Grundlage ist (RM-705).

    Unter 0.5.3 kannte Solidon diese Felder nicht, der Slicer nahm sie aus dem
    Herstellerprofil. Als Grundlage sagen sie dasselbe — auch wenn der Wert
    nicht die Vorgabe der Dataclass ist: Der ElegooSlicer bringt
    ``cooling.minimum_speed`` 20 statt 10 mit. Es zählt nur, was abweichen
    soll: eigene Wahl und übernommener Vorschlag (``explicit``) oder ein Wert
    der Spule, der vom Wert ohne die Spule abweicht — **dieselbe Frage wie
    ``handover._for_the_slot``**, ohne Slicer gerechnet: Mit einem eigenen
    Filamentprofil der Spule kann die Übergabe anders antworten, der Abdruck
    bleibt dafür auf jedem Rechner gleich. Ein Feld, das die Datei einer Spule
    aus 0.5.3 nicht kannte, folgt dem Wert ohne Spule
    (``SlotOverride.inherited``, RM-707) und fällt so heraus.
    """
    override = override_for(settings, slot)
    reference: PrintSettings | None = None
    if override is not None and not override.empty:
        without = replace(
            settings,
            slot_overrides=tuple(one for one in settings.slot_overrides if one is not override),
        )
        reference = settings_for_slot(without, profile, slot)
    for group in print_settings.GROUPS:
        section = values.get(group)
        if not isinstance(section, dict):
            continue
        known = FINGERPRINT_FIELDS.get(group, frozenset())
        for name in [name for name in section if name not in known]:
            path = f"{group}.{name}"
            if path in settings.explicit:
                continue
            if (
                reference is not None
                and getattr(override, group, None) is not None
                and not print_settings.same_value(
                    section[name], print_settings.read_path(reference, path)
                )
            ):
                continue
            del section[name]
        if not section and group not in FINGERPRINT_FIELDS:
            del values[group]


def prepare(
    objects: Sequence[SceneObject],
    settings: PrintSettings,
    profile: Profile,
    project_name: str,
    *,
    slots_by_plate: Mapping[int, Sequence[MaterialSlot]] | None = None,
    inputs: StoredInputs | None = None,
    base: SlicerSetup | None = None,
) -> tuple[UsageRequest, ...]:
    """Liest die tatsächlich ausgegebenen Körper, nie eine spätere Auswahl.

    **Der Abdruck** kommt aus ``inputs``, den gespeicherten Eingängen des
    Projekts (RM-706): je Körper :meth:`StoredInputs.bodies`, dazu was an den
    Einstellungen dem Projekt gehört (:func:`_owned_settings`) und die Wahl der
    Grundlage im Slicer (``base``, :func:`_base_choice`). Der Abdruck
    über die ausgewerteten Netze und die wirksamen Einstellungen (RM-705)
    steht dann in ``former_fingerprints``. Ohne ``inputs`` ist er selbst der
    Abdruck — nur für Mengen ohne Buchung und für Prüfungen ohne Projekt; wer
    bucht, gibt die Eingänge mit.

    Ein Mehrmaterialkörper hat keine aus Oberflächen ableitbare Volumenaufteilung.
    Seine Einzelmengen bleiben unbekannt, bis G-Code oder Nutzereingaben vorliegen.

    Die 3MF verwendet exportweite Werkzeugnummern. Ein einzelner Slicer-Lauf
    übergibt seine vollständigen, bereits mit Profilen belegten Slots in der
    lokalen ``merge_slots``-Reihenfolge über ``slots_by_plate``. Unbenutzte
    Altspulen entfallen wie in der Ausgabe; verwendete Spulen anderer Platten
    behalten ihre Werkzeugnummer. Alte Profilplätze werden vorher gebunden.
    """
    settings = bind_object_profiles(settings, objects)
    stored_bodies = inputs.bodies() if inputs is not None else None
    step_materials = _step_materials(profile, inputs.document) if inputs is not None else []
    whole_job = [
        threemf.AssemblyPart(
            geom_mesh.as_mesh_data(body.mesh), slots=threemf.slots_for_object(body)
        )
        for body in objects
    ]
    requests = []
    for plate in sorted({entry.plate for entry in objects}):
        bodies = [entry for entry in objects if entry.plate == plate]
        parts = [
            threemf.AssemblyPart(
                geom_mesh.as_mesh_data(body.mesh), slots=threemf.slots_for_object(body)
            )
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
        stored_geometry = []
        for body in bodies:
            mesh = geom_mesh.as_mesh_data(body.mesh)
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
            if stored_bodies is not None:
                # Die Flächenbelegung steckt in den Schritten; ``mesh.slots``
                # folgt der Dreiecksreihenfolge und bleibt deshalb draußen.
                stored_geometry.append(
                    (
                        str(body.id),
                        stored_bodies.get(body.id) or digest("unstored", checksum.hexdigest()),
                        _body_profile(profile, body),
                        assigned,
                    )
                )
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
        owned = []
        legacy_effective: list[list[object]] = [[] for _shape in _LEGACY_SHAPES]
        for original in slots:
            key = threemf.slot_identity(original)
            if key not in active_keys:
                continue
            slot = effective_slots[key]
            mine = settings_for_slot(settings, profile, slot)
            density, diameter = _material_properties(mine, slot)
            values = _saved_data(mine)
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
                # Woher ein Wert kommt, ändert den Druck nicht: dieselbe Zahl
                # als eigene Wahl und als übernommener Vorschlag ist ein Druck
                # (Review Stufe A+B, H10).
                "chosen",
                "accepted",
            ):
                values.pop(field, None)
            _without_later_fields(values, settings, slot, profile)
            # Alle Kennungen teilen dieselben gebundenen Werte. Unbekannte
            # oder sicher abgeschaltete Rafts bleiben ohne Feld; Auto ist offen.
            if values["adhesion"].get("raft_gap") is None or (
                "adhesion.kind" in mine.explicit
                and mine.adhesion.kind in {"none", "skirt", "brim", "skirt_brim"}
            ):
                values["adhesion"].pop("raft_gap", None)
            for (omitted, no_plate), entries in zip(_LEGACY_SHAPES, legacy_effective, strict=True):
                legacy = {
                    **values,
                    "adhesion": {
                        name: value
                        for name, value in values["adhesion"].items()
                        if name not in omitted
                    },
                }
                # Eine leere Wahl der Platte ist derselbe Druck wie vor ihr.
                if no_plate and not legacy.get("plate_choices"):
                    legacy.pop("plate_choices", None)
                entries.append((identities[key], legacy))
            # Genau der additive Vorgabewert null behält die alte Kennung.
            # Sein früher roh geschriebenes Feld bleibt oben ein Altkandidat.
            brim_gap = values["adhesion"].get("brim_gap")
            if brim_gap is not None and abs(brim_gap) <= 0.0:
                values["adhesion"].pop("brim_gap")
            effective.append((identities[key], values))
            owned.append((identities[key], _owned_settings(settings, slot)))
            lines.append(
                UsageLine(
                    slot=slot,
                    grams=amounts.get(key),
                    spool_identifier=spool_for(settings, original),
                    density=density,
                    diameter=diameter,
                )
            )
        evaluated = digest(
            settings.inventory_project_id,
            plate,
            sorted(geometry),
            sorted(effective, key=digest),
            profile_key(profile),
        )
        former: tuple[str, ...] = ()
        if stored_bodies is None:
            fingerprint = evaluated
        else:
            fingerprint = STORED_MARK + digest(
                STORED_INPUTS,
                settings.inventory_project_id,
                plate,
                sorted(stored_geometry),
                sorted(owned, key=digest),
                _fixed_profile(profile),
                step_materials,
                _base_choice(base),
            )
            former = (evaluated,)
        legacy_fingerprints = dict.fromkeys(
            digest(
                settings.inventory_project_id,
                plate,
                sorted(geometry),
                sorted(entries, key=digest),
                profile_key(profile),
            )
            for entries in legacy_effective
        )
        requests.append(
            UsageRequest(
                fingerprint,
                project_name,
                plate,
                tuple(lines),
                tuple(
                    key
                    for key in legacy_fingerprints
                    if key and key != fingerprint and key not in former
                ),
                former,
            )
        )
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
