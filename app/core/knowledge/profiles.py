"""Drucker- und Materialprofile (Bauplan §38).

Profile stehen nie fest im Code. Der mitgelieferte Startbestand liegt in
``data/*.toml`` und wird gelesen wie die Normteiltabelle; eigene Profile
leiten sich daraus ab und kommen aus dem Konfigurationsverzeichnis des
Nutzers.

Toleranzen sind Verweise, keine Zahlen (AGENTS.md Regel 7): eine Operation
speichert ``auto:petg``, und :func:`resolve_tolerance` schlägt es nach — genau
das lässt die Kalibrierung (§28.3) bestehende Projekte erreichen.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Collection, Mapping
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Final, cast, get_args

from app.core.errors import (
    ADOPT_PRINTER,
    CHOOSE_PRINTER,
    FileWriteError,
    ValidationError,
)
from app.core.knowledge.tables import read_table
from app.core.log import get_logger
from app.core.paths import user_profiles_dir
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    Finding,
    FitKind,
    MaterialProfile,
    PrinterProfile,
    PrintSettings,
    PrintTechnology,
    Profile,
    SceneObject,
    Tolerance,
)
from app.i18n import _, sort_key

_log = get_logger(__name__)

DEFAULT_PRINTER: Final = "generic-220"
DEFAULT_MATERIAL: Final = "pla"

#: Das allgemeine Resin-Gerät — die Vorlage, von der ein eigener Resin-Drucker
#: abgeleitet wird, wie ``DEFAULT_PRINTER`` für FDM.
DEFAULT_RESIN_PRINTER: Final = "generic-resin-130"

#: Das Material, mit dem ein neues Projekt an einem Resin-Drucker beginnt.
#: Ein Filament wäre dort eine FDM-Aussage vor dem ersten Klick.
DEFAULT_RESIN_MATERIAL: Final = "resin"

#: Vorgaben für ein Resin-Profil, dem die Tabelle nichts sagt — dieselbe Rolle
#: wie die 0,4er Düse und die 0,2er Schicht bei FDM: der Bestand der Tabelle
#: und der übliche Drucker. 50 µm Schicht und Pixel sind die Werkseinstellung
#: der verbreiteten MSLA-Geräte; 0,4 mm Wand ist die Untergrenze, die
#: Hersteller-Leitfäden für freistehende Wände nennen (Formlabs: 0,3 mm
#: gestützt, 0,4 mm ungestützt), nicht die, mit der ein Teil auch hält.
RESIN_LAYER_HEIGHT: Final = 0.05
RESIN_PIXEL_SIZE: Final = 0.05
RESIN_MINIMUM_WALL: Final = 0.4

_DATA_DIR: Final = Path(__file__).parent / "data"

_printers: dict[str, PrinterProfile] | None = None
_materials: dict[str, MaterialProfile] | None = None

#: Was das geöffnete Projekt an eigenen Profilen mitbringt (:func:`carry`).
#: Eine dritte Schicht unter den mitgelieferten und den eigenen: Sie füllt nur
#: Kennungen, die dieser Rechner nicht kennt.
_carried_printers: dict[str, PrinterProfile] = {}
_carried_materials: dict[str, MaterialProfile] = {}

#: Unter diesen Schlüsseln stehen die mitgebrachten Profile im Projekt.
CARRIED_PRINTERS: Final = "printers"
CARRIED_MATERIALS: Final = "materials"


def _read_table(path: Path) -> dict[str, dict[str, Any]]:
    # Derselbe Leser liest die mitgelieferten Tabellen und die des Nutzers —
    # und die zweiten sind von Hand geschrieben. Eine fehlende Klammer war
    # sonst ein Startabbruch mit rohem Stapelabzug, denn `printer_profiles()`
    # läuft beim Fensteraufbau (Regel 17, §33.1).
    return read_table(path, title=_("Diese Profildatei lässt sich nicht lesen."))


def _printer_from_table(identifier: str, table: Mapping[str, Any], source: Path) -> PrinterProfile:
    from app.core.build_area import printable_area, printable_height

    volume = table.get("build_volume")
    if not isinstance(volume, list) or len(volume) != 3:
        raise ValidationError(
            field=f"{identifier}.build_volume",
            detail=_("Der Bauraum muss aus drei Maßen bestehen."),
            values={"file": str(source)},
        )
    try:
        contour = _printer_contour(table.get("printable_area", ()))
        exclusions = tuple(_printer_contour(points) for points in table.get("bed_exclusions", ()))
        height = table.get("printable_height")
        height_limit = float(height) if height is not None else None
    except (TypeError, ValueError, IndexError) as exc:
        raise ValidationError(
            field=f"{identifier}.printable_area",
            detail=_("Die Druckkontur ist ungültig. Prüfen Sie das Druckerprofil."),
            values={"file": str(source)},
        ) from exc
    technology = str(table.get("technology", "fdm"))
    if technology not in get_args(PrintTechnology):
        raise ValidationError(
            field=f"{identifier}.technology",
            detail=_("Das Druckverfahren muss „fdm“ oder „resin“ sein."),
            values={"file": str(source), "technology": technology},
        )
    resin = technology == "resin"
    # Ein Resin-Drucker hat keine Düse und keine Bahn: Beide Zahlen stehen
    # auf null, damit ein Leser, der das Verfahren nicht fragt, nicht mit
    # einer 0,4er Düse rechnet, die es nicht gibt. Die Schichthöhe hat er —
    # eine andere, deshalb eine eigene Vorgabe.
    nozzle = 0.0 if resin else float(table.get("nozzle_diameter", 0.4))
    result = PrinterProfile(
        id=identifier,
        title=str(table.get("title", identifier)),
        build_volume=(float(volume[0]), float(volume[1]), float(volume[2])),
        nozzle_diameter=nozzle,
        layer_height=float(table.get("layer_height", RESIN_LAYER_HEIGHT if resin else 0.2)),
        extrusion_width=(
            0.0 if resin else float(table.get("extrusion_width", round(nozzle * 1.05, 3)))
        ),
        technology=cast(PrintTechnology, technology),
        pixel_size=float(table.get("pixel_size", RESIN_PIXEL_SIZE)) if resin else 0.0,
        minimum_wall=float(table.get("minimum_wall", RESIN_MINIMUM_WALL)) if resin else 0.0,
        enclosed=bool(table.get("enclosed", False)),
        # Und keine Heizung: Ein Harzbad hat weder Bett noch Düse zu wärmen.
        bed_temperature_max=0 if resin else int(table.get("bed_temperature_max", 100)),
        nozzle_temperature_max=0 if resin else int(table.get("nozzle_temperature_max", 260)),
        vendor=str(table.get("vendor", "")),
        printable_area=contour,
        bed_exclusions=exclusions,
        printable_height=height_limit,
        # Weniger als eine Düse druckt nichts; eine fehlende Angabe heißt
        # eine — das ist der Bestand der Tabelle und der übliche Drucker.
        nozzles=max(1, int(table.get("nozzles", 1))),
    )
    printable_area(result)
    printable_height(result)
    return result


def _printer_contour(points: Any) -> tuple[tuple[float, float], ...]:
    """Liest exakt zweidimensionale Profilpunkte; keine dritte Achse unterschlagen."""
    if any(len(point) != 2 for point in points):
        raise ValueError("expected two coordinates")
    return tuple((float(point[0]), float(point[1])) for point in points)


def _material_from_table(
    identifier: str, table: Mapping[str, Any], source: Path
) -> MaterialProfile:
    try:
        return MaterialProfile(
            id=identifier,
            title=str(table.get("title", identifier)),
            clearance=float(table["clearance"]),
            press=float(table["press"]),
            hole_compensation=float(table["hole_compensation"]),
            elephant_foot=float(table["elephant_foot"]),
            shrinkage=float(table.get("shrinkage", 0.0)),
            calibrated=bool(table.get("calibrated", False)),
            # Mechanik ohne Vorgabe: Ein fremdes Profil, das sie nicht führt,
            # bekommt 0 und damit „unbekannt". Ein geratener E-Modul stünde
            # sonst hinter jeder Federrechnung, ohne dass es jemand sähe.
            youngs_modulus=float(table.get("youngs_modulus", 0.0)),
            yield_strength=float(table.get("yield_strength", 0.0)),
            layer_bond_ratio=float(table.get("layer_bond_ratio", 0.0)),
            minimum_wall=(float(table["minimum_wall"]) if "minimum_wall" in table else None),
            overhang_angle=(float(table["overhang_angle"]) if "overhang_angle" in table else None),
            calibration_printer=str(table.get("calibration_printer", "")),
            calibration_nozzle_diameter=float(table.get("calibration_nozzle_diameter", 0.0)),
            calibration_layer_height=float(table.get("calibration_layer_height", 0.0)),
            calibration_extrusion_width=float(table.get("calibration_extrusion_width", 0.0)),
            technology=_material_technology(identifier, table, source),
        )
    except KeyError as missing:
        raise ValidationError(
            field=f"{identifier}.{missing.args[0]}",
            detail=_("Dem Materialprofil fehlt ein Toleranzwert."),
            values={"file": str(source)},
        ) from missing


def _load_printers() -> dict[str, PrinterProfile]:
    profiles: dict[str, PrinterProfile] = {}
    for path in (_DATA_DIR / "printers.toml", user_profiles_dir() / "printers.toml"):
        if not path.is_file():
            continue
        for identifier, table in _read_table(path).items():
            profiles[identifier] = _printer_from_table(identifier, table, path)
    for identifier, entry in _carried_printers.items():
        profiles.setdefault(identifier, entry)
    return _by_title(profiles)


def _load_materials() -> dict[str, MaterialProfile]:
    profiles: dict[str, MaterialProfile] = {}
    for path in (_DATA_DIR / "materials.toml", user_profiles_dir() / "materials.toml"):
        if not path.is_file():
            continue
        for identifier, table in _read_table(path).items():
            profiles[identifier] = _material_from_table(identifier, table, path)
    for identifier, entry in _carried_materials.items():
        profiles.setdefault(identifier, entry)
    return _by_title(profiles)


# --- Eigene Profile reisen mit dem Projekt -------------------------------------


def _shipped(table: str) -> frozenset[str]:
    """Die Kennungen des mitgelieferten Bestands — die reisen nie mit."""
    path = _DATA_DIR / table
    return frozenset(_read_table(path)) if path.is_file() else frozenset()


def printer_definition(profile: PrinterProfile) -> dict[str, Any]:
    """Ein Drucker als Tabelle, wie ``printers.toml`` und die Projektdatei ihn führen.

    Nur Maße, Zahlen und Namen: Bauraum, Düse, Verfahren, Schichthöhe,
    Kontur. Kein Pfad und kein Code — ein Druckerprofil kennt beides nicht,
    und :func:`carry` liest es mit demselben Prüfer wie eine eigene Datei.
    """
    return _as_table(profile)


def material_definition(profile: MaterialProfile) -> dict[str, Any]:
    """Ein Material als Tabelle — dieselbe Form wie ``materials.toml``."""
    return _as_table(profile)


def _as_table(profile: PrinterProfile | MaterialProfile) -> dict[str, Any]:
    """Die Felder eines Profils ohne Kennung, als reine JSON-Daten.

    Über ``json`` hin und zurück, damit Tupel zu Listen werden und nichts
    mitreist, was eine Projektdatei nicht tragen kann (``allow_nan=False``).
    """
    table: dict[str, Any] = json.loads(
        json.dumps(
            {
                key: value
                for key, value in asdict(profile).items()
                if key != "id" and value is not None
            },
            allow_nan=False,
        )
    )
    return table


def carried_definitions(
    printer_ids: Collection[str],
    material_ids: Collection[str],
    previous: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Was ein Projekt an eigenen Profilen mitnehmen muss, damit es woanders rechnet.

    **Der Anlass** (Durchsicht 0.5.0, Fund aus dem Paket „dialoge"): Ein
    Projekt mit einem eigenen Drucker, auf einem zweiten Rechner geöffnet,
    meldete nur „Dieses Druckerprofil ist nicht bekannt." — und rechnete
    nicht, und die Druckeinstellungen gingen nicht mehr auf. Der Drucker
    stand in einer Datei des ersten Rechners, und das Projekt nannte nur
    seine Kennung.

    Mitgenommen wird, was nicht zum Lieferumfang gehört: ein eigener Drucker
    oder ein eigenes Material, so wie dieser Rechner es kennt. Kennt er eine
    Kennung nicht, bleibt die Beschreibung, die das Projekt schon trug
    (``previous``) — sonst verlöre ein Projekt sie beim ersten Speichern auf
    einem Rechner, der sie nicht übernommen hat.
    """
    previous = previous or {}
    found: dict[str, dict[str, dict[str, Any]]] = {}
    shipped_printers = _shipped("printers.toml")
    known_printers = printer_profiles()
    earlier_printers = previous.get(CARRIED_PRINTERS) or {}
    for identifier in sorted({entry for entry in printer_ids if entry}):
        if identifier in shipped_printers:
            continue
        if identifier in known_printers:
            found.setdefault(CARRIED_PRINTERS, {})[identifier] = printer_definition(
                known_printers[identifier]
            )
        elif isinstance(earlier_printers.get(identifier), Mapping):
            found.setdefault(CARRIED_PRINTERS, {})[identifier] = dict(earlier_printers[identifier])
    shipped_materials = _shipped("materials.toml")
    known_materials = material_profiles()
    earlier_materials = previous.get(CARRIED_MATERIALS) or {}
    for identifier in sorted({entry for entry in material_ids if entry}):
        if identifier in shipped_materials:
            continue
        if identifier in known_materials:
            found.setdefault(CARRIED_MATERIALS, {})[identifier] = material_definition(
                known_materials[identifier]
            )
        elif isinstance(earlier_materials.get(identifier), Mapping):
            found.setdefault(CARRIED_MATERIALS, {})[identifier] = dict(
                earlier_materials[identifier]
            )
    return found


def carry(carried: Mapping[str, Mapping[str, Any]] | None) -> tuple[str, ...]:
    """Macht die Profile bekannt, die das geöffnete Projekt mitbringt.

    Eine dritte Schicht: Sie füllt nur Kennungen, die dieser Rechner weder
    mitliefert noch selbst angelegt hat — ein eigener Drucker hier gewinnt
    gegen die Beschreibung aus dem Projekt. Jeder Aufruf ersetzt die vorige
    Schicht; ``None`` räumt sie. Was sich nicht lesen lässt, bleibt weg und
    steht im Protokoll: Die Tabelle kommt aus einer fremden Datei und geht
    durch denselben Prüfer wie eine eigene (:func:`_printer_from_table`).

    Zurück kommen die Drucker, die nur das Projekt kennt — die, die
    :func:`carried_findings` zum Übernehmen anbietet.
    """
    global _printers, _materials
    source = Path("project.json")
    printers: dict[str, PrinterProfile] = {}
    materials: dict[str, MaterialProfile] = {}
    carried = carried or {}
    for identifier, table in (carried.get(CARRIED_PRINTERS) or {}).items():
        try:
            printers[str(identifier)] = _printer_from_table(str(identifier), table, source)
        except (ValidationError, TypeError, ValueError, AttributeError) as problem:
            _log.warning("the project carries an unreadable printer %r: %s", identifier, problem)
    for identifier, table in (carried.get(CARRIED_MATERIALS) or {}).items():
        try:
            materials[str(identifier)] = _material_from_table(str(identifier), table, source)
        except (ValidationError, TypeError, ValueError, AttributeError) as problem:
            _log.warning("the project carries an unreadable material %r: %s", identifier, problem)
    _carried_printers.clear()
    _carried_printers.update(printers)
    _carried_materials.clear()
    _carried_materials.update(materials)
    _printers = None
    _materials = None
    return only_carried()


def only_carried() -> tuple[str, ...]:
    """Die Drucker, die nur das geöffnete Projekt kennt, nach Kennung."""
    known = printer_profiles()
    return tuple(
        sorted(
            identifier
            for identifier, entry in _carried_printers.items()
            if known.get(identifier) is entry
        )
    )


def adopt_carried() -> tuple[str, ...]:
    """Übernimmt die mitgebrachten Drucker in die eigenen — zurück kommen ihre Kennungen."""
    adopted = only_carried()
    for identifier in adopted:
        save_printer(_carried_printers[identifier])
    return adopted


def carried_findings(printer_id: str, material_id: str = "") -> tuple[Finding, ...]:
    """Was der Prüfbericht nach dem Öffnen über den Drucker des Projekts sagt.

    Bringt das Projekt den Drucker mit, rechnet es mit dessen Beschreibung —
    und bietet an, ihn zu übernehmen oder einen eigenen zu wählen. Kennt der
    Rechner ihn gar nicht, rechnet es mit dem Standarddrucker, sagt das und
    bietet die Wahl an (:func:`scene_profile`); geraten wird dabei nichts
    still (Regel 21).
    """
    if printer_id and printer_id in only_carried():
        return (
            Finding(
                code="profile.carried_printer",
                severity="info",
                message=_(
                    "Dieses Projekt bringt seinen Drucker mit, der hier nicht eingerichtet "
                    "ist. Gerechnet wird mit der Beschreibung aus dem Projekt."
                ),
                values={"printer": printer_profiles()[printer_id].title},
                suggestions=(ADOPT_PRINTER, CHOOSE_PRINTER),
            ),
        )
    if printer_id and printer_id not in printer_profiles():
        # **Der Satz nennt den Drucker, mit dem gerechnet wird** — der
        # allgemeine desselben Verfahrens (:func:`_standard_printer_for`).
        # „Standarddrucker" ließ offen, welcher Bauraum gerade gilt.
        general = printer(_standard_printer_for(material_id)).title
        return (
            Finding(
                code="profile.printer_missing",
                severity="warning",
                message=_(
                    "Den Drucker dieses Projekts gibt es hier nicht. Gerechnet wird mit "
                    "„{printer}“, bis Sie einen wählen.",
                    printer=general,
                ),
                values={"printer": printer_id, "fallback_printer": general},
                suggestions=(CHOOSE_PRINTER,),
            ),
        )
    return ()


# Drucker und Material teilen sich nur den Titel, und der genügt zum Sortieren.
def _by_title[P: (PrinterProfile, MaterialProfile)](profiles: dict[str, P]) -> dict[str, P]:
    """Nach dem Namen sortiert, den der Nutzer liest.

    In Dateireihenfolge stand die Druckerliste fast alphabetisch, mit dem
    Centauri an der Stelle, an der er nachgetragen wurde — und wer seinen
    Drucker sucht, sucht ihn dort, wo er alphabetisch hingehört. Die Ordnung
    hier statt in jeder Liste einzeln: es gibt vier, und eine davon vergisst
    es sonst.
    """
    return dict(sorted(profiles.items(), key=lambda pair: sort_key(pair[1].title)))


def printer_profiles() -> Mapping[str, PrinterProfile]:
    """Alle bekannten Druckerprofile — die mitgelieferten und die eigenen."""
    global _printers
    if _printers is None:
        _printers = _load_printers()
        _log.info("loaded %d printer profiles", len(_printers))
    return _printers


def user_printer_profiles() -> Mapping[str, PrinterProfile]:
    """Die selbst angelegten Drucker bleiben unabhängig vom Slicer auswählbar."""
    path = user_profiles_dir() / "printers.toml"
    identifiers = _read_table(path) if path.is_file() else {}
    known = printer_profiles()
    return {identifier: known[identifier] for identifier in identifiers if identifier in known}


def save_printer(profile: PrinterProfile) -> PrinterProfile:
    """Speichert einen eigenen Drucker atomar und erhält andere Nutzerprofile."""
    if not profile.id.strip() or not profile.title.strip():
        raise ValidationError(
            field="printer.title", detail=_("Geben Sie Ihrem Drucker einen Namen.")
        )
    measurements: tuple[float, ...]
    if profile.is_resin:
        measurements = (*profile.build_volume, profile.pixel_size, profile.minimum_wall)
        complaint = _("Bauraum, Pixelgröße und Mindestwand müssen größer als null sein.")
    else:
        measurements = (*profile.build_volume, profile.nozzle_diameter)
        complaint = _("Bauraum und Düsendurchmesser müssen größer als null sein.")
    if not all(math.isfinite(value) and value > 0 for value in measurements):
        raise ValidationError(field="printer.build_volume", detail=complaint)
    target = user_profiles_dir() / "printers.toml"
    table = _read_table(target) if target.is_file() else {}
    values = {
        key: value for key, value in asdict(profile).items() if key != "id" and value is not None
    }
    table[profile.id] = values
    lines: list[str] = []
    for identifier, entry in sorted(table.items()):
        lines.append(f"[{json.dumps(identifier, ensure_ascii=False)}]")
        for key, value in entry.items():
            lines.append(
                f"{json.dumps(key)} = {json.dumps(value, ensure_ascii=False, allow_nan=False)}"
            )
        lines.append("")
    scratch: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
        ) as stream:
            scratch = Path(stream.name)
            stream.write("\n".join(lines))
            stream.flush()
            os.fsync(stream.fileno())
        scratch.replace(target)
    except OSError as problem:
        raise FileWriteError(detail=str(problem)) from problem
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)
    global _printers
    _printers = None
    return printer_profiles()[profile.id]


def material_profiles() -> Mapping[str, MaterialProfile]:
    """Alle bekannten Materialprofile — die mitgelieferten und die eigenen."""
    global _materials
    if _materials is None:
        _materials = _load_materials()
        _log.info("loaded %d material profiles", len(_materials))
    return _materials


def material_id_for_type(material_type: str) -> str:
    """Die eindeutige Solidon-Kennung zu einer Materialart des Slicers.

    Slicer schreiben etwa ``PETG`` oder ``TPU``, Solidon hält ``petg`` und
    ``tpu-95a``. Die Umkehrung liegt hier bei den Profilen, damit Erststart und
    Slicerübergabe dieselbe Entscheidung treffen. Leer heißt bewusst: nichts
    oder mehr als ein Profil passt — dann wird nicht geraten.
    """
    from app.core.export import slicer_keys

    wanted = material_type.strip().casefold()
    if not wanted:
        return ""
    matches = [
        identifier
        for identifier in material_profiles()
        if slicer_keys.filament_type(identifier).casefold() == wanted
    ]
    return matches[0] if len(matches) == 1 else ""


def reload() -> None:
    """Verwirft den Cache, etwa nachdem der Nutzer ein Profil bearbeitet hat."""
    global _printers, _materials
    _printers = None
    _materials = None


def printer(identifier: str) -> PrinterProfile:
    profiles = printer_profiles()
    if identifier not in profiles:
        raise ValidationError(
            field="printer",
            detail=_("Dieses Druckerprofil ist nicht bekannt."),
            values={"requested": identifier, "known": sorted(profiles)},
        )
    return profiles[identifier]


def material(identifier: str) -> MaterialProfile:
    profiles = material_profiles()
    if identifier not in profiles:
        raise ValidationError(
            field="material",
            detail=_("Dieses Materialprofil ist nicht bekannt."),
            values={"requested": identifier, "known": sorted(profiles)},
        )
    return profiles[identifier]


def _material_technology(
    identifier: str, table: Mapping[str, Any], source: Path
) -> PrintTechnology:
    """Das Verfahren eines Materials; ohne Angabe ein Filament."""
    technology = str(table.get("technology", "fdm"))
    if technology not in get_args(PrintTechnology):
        raise ValidationError(
            field=f"{identifier}.technology",
            detail=_("Das Druckverfahren muss „fdm“ oder „resin“ sein."),
            values={"file": str(source), "technology": technology},
        )
    return cast(PrintTechnology, technology)


def make_profile(printer_id: str = DEFAULT_PRINTER, material_id: str = DEFAULT_MATERIAL) -> Profile:
    """Das Paar, für das eine Szene gerechnet wird."""
    return Profile(printer=printer(printer_id), material=material(material_id))


def _standard_printer_for(material_id: str) -> str:
    """Der Drucker, mit dem gerechnet wird, wenn der des Projekts fehlt.

    Ein Resin-Projekt bleibt am Resin-Gerät: Ein Harz an einer Düse wäre ein
    zweiter Fehler, der den ersten verdeckt.
    """
    known = material_profiles().get(material_id)
    return (
        DEFAULT_RESIN_PRINTER
        if known is not None and known.technology == "resin"
        else DEFAULT_PRINTER
    )


def scene_profile(printer_id: str, material_id: str) -> Profile:
    """Das Paar eines geöffneten Projekts — auch wenn dieser Rechner es nicht kennt.

    Ein unbekannter Drucker oder ein unbekanntes Material hielt vorher alles
    an: keine Szene, keine Druckeinstellungen, nur „Dieses Druckerprofil ist
    nicht bekannt." Gerechnet wird dann mit der Vorgabe — und der Prüfbericht
    sagt es mit dem Weg zur Wahl (:func:`carried_findings`). Das Projekt
    selbst behält seine Kennung, bis jemand einen anderen Drucker wählt.
    """
    known_printers = printer_profiles()
    chosen_printer = (
        printer_id if printer_id in known_printers else _standard_printer_for(material_id)
    )
    known_materials = material_profiles()
    chosen_material = (
        material_id if material_id in known_materials else default_material_for(chosen_printer)
    )
    return make_profile(chosen_printer, chosen_material)


def default_material_for(printer_id: str) -> str:
    """Das Material, mit dem ein neues Projekt an diesem Drucker beginnt.

    PLA an einem FDM-Drucker, Harz an einem Resin-Drucker — und ein
    unbekannter Drucker bleibt bei PLA, denn dann rechnet die Szene ohnehin
    mit dem allgemeinen FDM-Gerät. Erststart und Druckerwechsel fragen hier,
    damit ein Resin-Projekt nicht mit einem Filament beginnt, das es nie
    druckt (Resin-Konzept §4).
    """
    known = printer_profiles().get(printer_id)
    if known is not None and known.is_resin:
        return DEFAULT_RESIN_MATERIAL
    return DEFAULT_MATERIAL


def material_for(printer_id: str, current: str) -> str:
    """Das Material, das an diesem Drucker gilt: das bisherige, wenn es zu
    seinem Verfahren passt, sonst die Vorgabe des Verfahrens.

    Wer die Maschine wechselt, wechselt nicht das Filament — solange die neue
    Maschine ein Filament druckt. Von FDM auf Resin umgestellt bliebe PLA in
    einem Harzbad stehen, und jeder Satz über das Material wäre falsch.
    """
    known = printer_profiles().get(printer_id)
    chosen = material_profiles().get(current)
    if known is None:
        return current or DEFAULT_MATERIAL
    if chosen is not None and chosen.fits(known):
        return current
    return default_material_for(printer_id)


def for_process(profile: Profile, settings: PrintSettings | None) -> Profile:
    """Bezieht Prozessmessungen auf das tatsächliche Druckraster des Projekts.

    Bei Resin bleibt das Profil, wie es ist: Dort gibt es kein Bahnraster,
    das eine Messung binden könnte, und die Werte des FDM-Satzes würden die
    Nullen einer Düse überschreiben, die es nicht gibt.
    """
    if settings is None or profile.printer.is_resin:
        return profile
    return replace(
        profile,
        printer=replace(
            profile.printer,
            layer_height=settings.layers.layer_height,
            extrusion_width=settings.layers.line_width,
        ),
    )


def for_object(profile: Profile, entry: SceneObject | None) -> Profile:
    """Das Profil, mit dem dieser eine Körper gedruckt wird (§12).

    Derselbe Drucker, das eigene Material des Körpers, wo er eines hat. Alles,
    was aus dem Material eine Länge rechnet — Spiel, Schrumpf, Elefantenfuß —
    geht hier durch statt ``profile.material`` zu lesen: eine Dichtung aus TPU
    wird also nicht gerechnet, als wäre sie das Gehäuse um sie herum.

    **Und wo nichts am Körper steht, fragt es die Spule** — „das Material kommt
    ja auch aus dem Filament" (Robert, 30.08.2026). Die Rangfolge ist
    Entscheidung vor Herleitung: Ein ausdrücklich gesetztes ``entry.material``
    gewinnt, denn es hat jemand gewählt; der Materialtyp der Spule ist die
    Antwort für alle anderen. Gemessen kostet die Frage 0,05 mm Spiel
    (PETG 0,25, PLA 0,20) — klein, aber an einer Passung spürbar.
    """
    if entry is None:
        return profile
    chosen = entry.material or _material_of_spool(entry)
    if chosen is None or chosen == profile.material.id:
        return profile
    return Profile(printer=profile.printer, material=material(chosen))


def _material_of_spool(entry: SceneObject) -> str | None:
    """Die Materialkennung aus der Spule des Körpers — oder ``None``.

    **Slot 0 und nicht der größte Flächenanteil.** Slot 0 ist das unbemalte
    Teil (§20), also der Körper selbst; jeder weitere Slot ist Bemalung. Ein
    Gehäuse mit einem Schriftzug in anderer Farbe bohrt ins Gehäuse, und ein zu
    sechzig Prozent bemaltes Teil tut das auch — die Flächenrechnung wäre
    teurer und im Randfall falsch.

    ``None`` heißt: Es bleibt beim Material des Projekts. Das ist kein
    Sonderfall, sondern der häufigste Weg — eine frisch eingelesene STL hat
    **keine** Spulen, und Weg 1 fängt genau dort an. Geraten wird dabei nie
    (Regel 21): ``material_id_for_type`` gibt leer zurück, wo nichts oder mehr
    als ein Profil passt.
    """
    slot = next((spool for spool in entry.material_slots if spool.index == 0), None)
    if slot is None or not slot.material_type:
        return None
    return material_id_for_type(slot.material_type) or None


def analysis_limits(profile: Profile, entry: SceneObject) -> tuple[float, float]:
    """Mindestwand und Überhanggrenze für die tatsächlich verwendeten Materialien.

    Eine gemeinsame Geometrieprüfung nimmt die größte Mindestwand und den
    kleinsten Überhangwinkel. Eine unbekannte Materialart bleibt bei den
    unkalibrierten Startregeln, statt eine fremde Messung zu übernehmen.
    """
    from app.core.export.threemf import AssemblyPart, assembly_slots, slots_for_object
    from app.core.geom.attributes import used_slots
    from app.core.geom.mesh import as_mesh_data

    mesh = as_mesh_data(entry.mesh)
    if not entry.material_slots and not mesh.slots:
        own = for_object(profile, entry)
        return own.minimum_wall_thickness, own.overhang_limit_degrees
    present = set(used_slots(mesh))
    used = []
    unknown = False
    for slot in assembly_slots(AssemblyPart(mesh=mesh, slots=slots_for_object(entry))):
        if slot.index not in present:
            continue
        identifier = material_id_for_type(slot.material_type or "")
        if identifier:
            used.append(Profile(profile.printer, material(identifier)))
        else:
            unknown = True
    walls = [item.minimum_wall_thickness for item in used]
    angles = [item.overhang_limit_degrees for item in used]
    if unknown:
        uncalibrated = Profile(profile.printer, replace(profile.material, calibration_printer=""))
        walls.append(uncalibrated.minimum_wall_thickness)
        angles.append(uncalibrated.overhang_limit_degrees)
    return (
        max(walls, default=profile.minimum_wall_thickness),
        min(angles, default=profile.overhang_limit_degrees),
    )


#: Welche Materialgröße eine Passungsart liest (§14). Hier dokumentiert,
#: nicht verstreut.
_FIT_FIELD: Final[dict[FitKind, str]] = {
    "clearance": "clearance",
    "press": "press",
    "thread": "hole_compensation",
    "flush": "",
}


def resolve_tolerance(value: Tolerance, kind: FitKind, profile: Profile) -> float:
    """Macht aus einem Toleranzverweis Millimeter.

    Eine Zahl geht durch. ``auto:`` nimmt das Szenenmaterial, ``auto:petg`` ein
    benanntes — ein Projekt kann also eine Passung für ein Material halten, auf
    das es gerade nicht eingestellt ist.
    """
    if isinstance(value, int | float):
        return float(value)
    if not value.startswith(AUTO_TOLERANCE_PREFIX):
        raise ValidationError(
            field="tolerance",
            detail=_("Eine Toleranz ist entweder eine Zahl oder ein Verweis auf ein Material."),
            values={"value": value},
        )
    name = value[len(AUTO_TOLERANCE_PREFIX) :] or profile.material.id
    chosen = profile.material if name == profile.material.id else material(name)
    field_name = _FIT_FIELD[kind]
    return float(getattr(chosen, field_name)) if field_name else 0.0
