"""Die Profile finden, die ein installierter Slicer mitbringt (Bauplan §29).

Solidon schreibt die Druckeinstellungen, aber nicht das Maschinenwissen:
Bettform, Anfahrwege, Start- und Endcode, die Eigenheiten einer Kinematik
stehen im Profilbestand des Slicers und bleiben dort (§29). Was fehlte, war
der Zeiger darauf — die Orca-Familie bricht ohne beide Profile mit „process
not compatible with printer" ab, bevor sie das Modell ansieht.

Geraten wird dabei nichts. Ein Maschinenprofil sagt selbst, welchen Drucker es
meint (``printer_model``), welche Düse (``nozzle_diameter``) und welches
Prozessprofil zu ihm gehört (``default_print_profile``); ein Prozessprofil
sagt, mit welchen Druckern es verträglich ist (``compatible_printers``). Das
reicht, um die Zuordnung zu treffen, statt sie zu erfragen — eine gute Vorgabe
ist mehr wert als eine gute Einstellmöglichkeit (§2.4). Wählen kann man
trotzdem, denn ein umbenanntes oder selbst angelegtes Profil trifft keine
Heuristik.
"""

from __future__ import annotations

import configparser
import csv
import json
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, Literal
from xml.etree import ElementTree as ET

from app.core import discover
from app.core.errors import CHECK_SLICER_PROFILE, ExternalToolError, ValidationError
from app.core.export.slicer_keys import (
    SlicerFlavour,
    has_readable_profiles,
    has_user_profile_tree,
)
from app.core.log import get_logger
from app.core.types import PrinterProfile
from app.i18n import _

_log = get_logger(__name__)

ProfileKind = Literal["machine", "process", "filament"]

#: Der Namensindex einer Profilablage: je Wurzel und Art ein Name-auf-Pfad.
#:
#: **Er wird durchgereicht und nicht je Aufruf gebaut.** Ihn aufzustellen
#: heißt, jede JSON-Datei unterhalb der Wurzel zu lesen — beim ElegooSlicer
#: sind das 16 795 Dateien. Wer eine Erbkette je Filament auflöst und den
#: Index dabei jedes Mal neu baut, liest denselben Bestand so oft, wie es
#: Filamente gibt (Befund Robert, 09.09.2026: der Qt-Hauptthread stand 49 s).
#:
#: **Er gilt für einen Durchgang, nicht für die Lebensdauer eines Fensters.**
#: Der Bestand gehört dem Slicer, und der Kunde legt dort Profile an, benennt
#: sie um und löscht sie. Wer diesen Index an einem Dialog aufhebt, liefert
#: danach Pfade aus, die es nicht mehr gibt — die Ersparnis wiegt das nicht
#: auf. Wer ihn übergibt, hält ihn so kurz wie den Aufruf, in dem er entsteht.
ProfileIndexes = dict[tuple[Path, ProfileKind | None], dict[str, Path]]

#: Wie viele Dateien höchstens gelesen werden. Der ausgelieferte Bestand eines
#: Slicers umfasst einige tausend Profile über alle Hersteller; eine Zahl weit
#: darüber heißt, dass hier der falsche Ordner durchsucht wird.
MAX_FILES: Final = 20_000

#: Gesucht wird nur unter diesen Ordnernamen. Der Bestand von ElegooSlicer hat
#: elftausend JSON-Dateien, wovon viertausend Profile sind — der Rest sind
#: Filamente, Modelle und Beschreibungen, und jede davon zu öffnen kostet
#: Sekunden, die der Dialog nicht hat.
PROFILE_DIRS: Final[dict[str, ProfileKind]] = {
    "machine": "machine",
    "process": "process",
    "filament": "filament",
}


@dataclass(frozen=True, slots=True)
class SlicerProfile:
    """Ein Profil aus dem Bestand des Slicers."""

    path: Path
    name: str
    kind: ProfileKind
    printer_model: str = ""
    nozzle: float = 0.0
    compatible_printers: tuple[str, ...] = ()
    default_process: str = ""
    filament_type: str = ""
    """Nur bei Filamentprofilen: ``PETG``, ``PLA``, … — daran hängt die
    Zuordnung zum Material, das in Solidon eingestellt ist."""
    from_user: bool = False
    """Selbst angelegt statt mitgeliefert — solche Profile gewinnen bei
    Gleichstand, weil jemand sie absichtlich gemacht hat."""
    inherits: str = ""
    """Von welchem Systemprofil es abstammt. Selbst angelegte Profile tragen
    ihre Angaben nicht selbst; woher sie kommen, steht hier."""
    section: str = ""
    """Bei Prusa-Bündeln der Abschnitt; der Dateipfad allein ist nicht eindeutig."""

    def title(self, own: str = "eigenes") -> str:
        """Der Name für die Auswahl. Ein selbst angelegtes Profil wird
        ausgeschrieben gekennzeichnet und nicht mit einem Zeichen: das liest
        sich vor, überlebt jeden Zeichensatz und braucht keine Legende.
        """
        return f"{self.name} ({own})" if self.from_user else self.name


@dataclass(frozen=True, slots=True)
class SlicerFilament:
    """Ein gespeicherter Slicer-Platz als Vorschlag, kein Nachweis einer physischen Spule."""

    profile: str
    colour: str
    material_type: str = ""


def install_root(executable: Path) -> Path | None:
    """Der Ordner, unter dem die mitgelieferten Profile liegen.

    Von der Programmdatei aus nach oben gesucht statt fest eingetragen: die
    Ablage unterscheidet sich zwischen Windows, einem AppImage und einem
    Linux-Paket, und alle drei legen ``resources`` irgendwo über der ausführbaren
    Datei ab.
    """
    for folder in (executable.parent, *executable.parents):
        for candidate in (folder / "resources" / "profiles", folder / "share" / "cura"):
            # Gefragt wird über ``discover``: Läuft Solidon in einem Flatpak,
            # ist ``executable`` ein Host-Pfad, und ``is_dir()`` darauf sagt
            # zuverlässig nein. Für Cura hängt daran ``-j <definition>``, und
            # ohne die startet CuraEngine gar nicht.
            if discover.is_dir_on_host(candidate):
                return candidate
    return None


def config_home(platform: str) -> str:
    """Wo dieses System die Konfiguration fremder Programme ablegt.

    **Drei Quellen für drei Plattformen, und eine fehlte.** Hier standen
    ``APPDATA`` und ``XDG_CONFIG_HOME`` mit ``~/.config`` als Rückfall. Auf
    macOS ist keine der beiden Variablen gesetzt und ``~/.config`` gibt es
    typischerweise nicht — die Funktion gab dort **immer** eine leere Liste
    zurück, und damit fand Solidon auf einem Mac nie ein selbst angelegtes
    Profil. `chosen_machine()` lieferte ``""``, also genau die Auskunft, für
    die diese Datei gebaut wurde: „Slicer gefunden" und im selben Fenster ein
    Vorschlag aus dem Nichts.

    Die Orca-Familie legt auf macOS unter ``~/Library/Application Support`` ab.

    **Und in einem Flatpak zeigt ``XDG_CONFIG_HOME`` in den eigenen Sandkasten**
    (``~/.var/app/<id>/config``). Dort liegen die Profile eines fremden Slicers
    nie; gemeint ist das Konfigurationsverzeichnis des **Rechners**, und das
    ist ``~/.config``, auch wenn die Variable etwas anderes sagt.

    **Die Plattform kommt als Parameter, nicht aus ``sys.platform``** — aus
    zwei Gründen, und der zweite ist der wichtigere. Erstens sieht ``mypy``
    sonst auf Windows jeden Zweig darunter als tot an und meldet ihn; die CI
    prüft unter Linux und findet das nie, also ist der Code auf drei Maschinen
    rot und auf dem Bauserver grün. Zweitens — und deshalb steht dasselbe
    Muster in :func:`app.core.discover.parts_for` und
    :func:`app.core.backends.comfy_setup.guesses_for` — ist die Zuordnung so
    von **jeder** Maschine aus prüfbar: Ein Zweig, den nur ein Mac sehen kann,
    wird nirgends geprüft.
    """
    if platform == "win32":
        return os.environ.get("APPDATA", "")
    if platform == "darwin":
        support = Path.home() / "Library" / "Application Support"
        return str(support) if support.is_dir() else ""
    # Linux: die Variable gilt — außer sie zeigt in unseren eigenen Sandkasten.
    named = os.environ.get("XDG_CONFIG_HOME", "")
    if named and not discover.in_flatpak():
        return named
    home = Path.home() / ".config"
    return str(home) if home.is_dir() else ""


def user_roots(flavour: SlicerFlavour, executable: Path) -> list[Path]:
    """Wo die selbst angelegten Profile liegen.

    Die Orca-Familie legt sie unter ``<Konfiguration>/<Programm>/user/<Konto>/``
    ab. Der Programmname ist der der ausführbaren Datei, ohne Bindestriche —
    ``elegoo-slicer.exe`` schreibt nach ``ElegooSlicer``.
    """
    base = config_home(sys.platform)
    if not base:
        return []
    if flavour == "cura":
        return _cura_user_roots(executable, Path(base))
    if flavour == "prusa":
        stem = discover.program_mark(executable.name)
        return (
            [
                folder
                for folder in Path(base).iterdir()
                if folder.is_dir() and discover.plain_name(folder.name) == stem
            ]
            if Path(base).is_dir()
            else []
        )
    if not has_user_profile_tree(flavour):
        return []

    # Die Programmmarke, nicht der ganze Dateistamm: ``OrcaSlicer_Linux_V2.1.1``
    # legt seine Profile unter ``OrcaSlicer`` ab, und der Stamm traf diesen
    # Ordner nie — eigene Profile, gewählter Drucker und Filamente fehlten
    # nach jedem Update des AppImages (Gesamtreview 05.09.2026, CORE-16).
    stem = discover.program_mark(executable.name)
    found: list[Path] = []
    for folder in Path(base).iterdir() if Path(base).is_dir() else []:
        if not folder.is_dir() or discover.plain_name(folder.name) != stem:
            continue
        user = folder / "user"
        if user.is_dir():
            found.extend(entry for entry in user.iterdir() if entry.is_dir())
    return found


def chosen_machine(flavour: SlicerFlavour, executable: Path) -> str:
    """Welche Maschine im Slicer zuletzt eingestellt war (§29, §2.3).

    Die Orca-Familie schreibt sie in ihre Konfiguration neben die eigenen
    Profile, als ``presets.machine`` — etwa „Elegoo Centauri Carbon 2 0.4
    nozzle". Das ist die beste Auskunft darüber, vor welchem Drucker jemand
    sitzt, und sie kostet eine Datei statt einer Frage.

    Gebraucht wird sie bei der Ersteinrichtung: der Dialog meldete „Slicer
    gefunden" und schlug im selben Fenster den allgemeinen 220er und PLA vor,
    während der Bestand daneben den richtigen Drucker kannte.

    Leer heißt: nicht herauszufinden. Dann bleibt es bei der Vorgabe — eine
    falsche Vorauswahl sieht aus wie eine Entscheidung (§29).

    **PrusaSlicer sagt es ebenso**, nur in seiner ``PrusaSlicer.ini`` unter
    ``[presets] printer``. Es gibt keinen Grund, den Kunden dort nach einem
    Drucker zu fragen, den sein Slicer längst kennt.
    """
    if flavour == "prusa":
        return str(_prusa_presets(executable).get("printer", "")).strip()
    if not has_user_profile_tree(flavour):
        return ""
    for root in user_roots(flavour, executable):
        # ``user/<Konto>`` — die Konfiguration liegt eine Ebene darüber.
        config = root.parent.parent / f"{root.parent.parent.name}.conf"
        if not config.is_file():
            continue
        try:
            text = config.read_text(encoding="utf-8", errors="replace")
            # Die Datei trägt mehr als ein JSON-Dokument hintereinander; das
            # erste ist die Konfiguration, und ``raw_decode`` hört dort auf,
            # wo es endet.
            document, _end = json.JSONDecoder().raw_decode(text.lstrip())
        except (OSError, ValueError) as problem:
            _log.debug("could not read %s: %s", config.name, problem)
            continue
        presets = document.get("presets") if isinstance(document, dict) else None
        if isinstance(presets, dict):
            machine = presets.get("machine")
            if isinstance(machine, str) and machine.strip():
                _log.info("the slicer was last set to %s", machine)
                return machine.strip()
    return ""


#: Wie PrusaSlicer seine Anwendungskonfiguration nennt.
_PRUSA_CONFIG: Final = "PrusaSlicer.ini"

#: Wie viele Spulen höchstens gelesen werden. PrusaSlicer nummeriert sie ab
#: der zweiten — ``filament``, ``filament_1``, ``filament_2`` —, und acht ist
#: dieselbe Grenze wie ``MAX_SLOTS`` im Kern.
_PRUSA_EXTRUDERS: Final = 8


def prusa_config(executable: Path) -> Path | None:
    """Die Anwendungskonfiguration von PrusaSlicer, sofern sie dasteht.

    PrusaSlicer legt keine Profile je Konto ab wie die Orca-Familie: Es gibt
    einen Ordner unter der Konfiguration des Systems und darin eine
    ``PrusaSlicer.ini``. In ihrem Abschnitt ``[presets]`` steht, was zuletzt
    eingelegt und eingestellt war — dieselbe Auskunft, die bei Orca in
    ``presets.machine`` steht, nur in einem anderen Format.
    """
    base = config_home(sys.platform)
    if not base:
        return None
    stem = discover.program_mark(executable.name)
    for folder in Path(base).iterdir() if Path(base).is_dir() else []:
        if not folder.is_dir() or discover.plain_name(folder.name) != stem:
            continue
        config = folder / _PRUSA_CONFIG
        if config.is_file():
            return config
    return None


#: Der künstliche Abschnittsname für den kopflosen Anfang einer Prusa-INI.
#:
#: **Nicht ``DEFAULT``**, obwohl das naheläge: ConfigParser reicht dessen
#: Werte an *jeden* Abschnitt weiter, und ``[presets]`` trüge dann die
#: zweihundert Schlüssel des Kopfes mit.
_PRUSA_HEAD: Final = "solidon:head"


def _read_prusa_ini(path: Path) -> configparser.ConfigParser | None:
    """Eine PrusaSlicer-INI — ihr Anfang hat keinen Abschnitt.

    Die Anwendungskonfiguration beginnt mit Schlüsseln ohne Überschrift, und
    ein Filamentprofil besteht sogar ausschließlich daraus. ConfigParser lehnt
    beides mit ``MissingSectionHeaderError`` ab; ein künstlicher Kopf macht
    daraus eine gültige Datei, ohne eine Zeile zu verändern.

    Genau daran ist der erste Versuch am 08.09.2026 gescheitert — der Leser
    fing den Fehler ab und gab eine leere Zuordnung zurück, und die sah aus
    wie „nichts eingelegt".
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as problem:
        _log.debug("skipping Prusa file %s: %s", path.name, problem)
        return None
    parsed = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parsed.read_string(f"[{_PRUSA_HEAD}]\n{text}")
    except configparser.Error as problem:
        _log.debug("skipping Prusa file %s: %s", path.name, problem)
        return None
    return parsed


def _prusa_presets(executable: Path) -> Mapping[str, str]:
    """Der Abschnitt ``[presets]`` — leer, wo nichts zu lesen ist."""
    config = prusa_config(executable)
    if config is None:
        return {}
    parsed = _read_prusa_ini(config)
    if parsed is None or not parsed.has_section("presets"):
        return {}
    return dict(parsed["presets"])


def _prusa_configured(executable: Path) -> tuple[SlicerFilament, ...]:
    """Die eingelegten Spulen von PrusaSlicer.

    **Der Name ist die sichere Auskunft, alles andere kommt nur, wo es
    dasteht.** Ein Herstellerpreset wohnt in einem Bündel mit Zehntausenden
    Abschnitten und einer Erbkette; ein selbst angelegtes liegt als eigene
    Datei unter ``filament/``, und die trägt Art und Farbe unmittelbar. Was
    sich nicht ohne Raten sagen lässt, bleibt leer — eine erfundene
    Materialart wäre schlechter als keine (Regel 21).
    """
    presets = _prusa_presets(executable)
    if not presets:
        return ()
    profiles = {entry.name: entry for entry in find_profiles(executable, "prusa", ("filament",))}
    roots = profile_roots("prusa", executable)
    keys = ["filament", *(f"filament_{index}" for index in range(1, _PRUSA_EXTRUDERS))]
    found: list[SlicerFilament] = []
    for key in keys:
        name = str(presets.get(key, "")).strip()
        if not name:
            continue
        entry = profiles.get(name)
        values = resolve_profile(entry, roots) if entry is not None else {}
        colour = str(values.get("filament_colour", "")).strip()
        found.append(
            SlicerFilament(
                profile=name,
                colour=colour if _COLOUR_LOOKS_RIGHT.match(colour) else "",
                material_type=str(values.get("filament_type", "")).strip(),
            )
        )
    return tuple(found)


#: Der Farbvertrag der Anzeige: ``#RRGGBB``. Ein Profil darf etwas anderes
#: hineinschreiben; dann gilt es als keine Angabe.
_COLOUR_LOOKS_RIGHT: Final = re.compile(r"^#[0-9a-fA-F]{6}$")


def configured_filaments(flavour: SlicerFlavour, executable: Path) -> tuple[SlicerFilament, ...]:
    """Die im Slicer eingelegten Filamente samt Farbe und Typ (§20, §29).

    Die Orca-Familie hält die physische Belegung nicht in den
    Filamentprofilen: Dort steht die Materialart, die Farbe dagegen in der
    Anwendungskonfiguration je Maschine. Beides wird deshalb hier wieder
    zusammengeführt. Es werden nur die Einträge der zuletzt gewählten Maschine
    gelesen — der ganze Profilbestand wäre ein Herstellerkatalog und kein
    Filamentregal.

    **PrusaSlicer führt dieselbe Auskunft an einer anderen Stelle** und in
    einem anderen Format: ``[presets]`` in seiner ``PrusaSlicer.ini``. Vor dem
    08.09.2026 blieb es hier bei ``()``, und damit war die Zusage aus §20 —
    die eingelegten Filamente werden als Vorwahl übernommen — nur für eine der
    drei Familien eingelöst.
    """
    if flavour == "prusa":
        return _prusa_configured(executable)
    if not has_user_profile_tree(flavour):
        return ()
    roots = profile_roots(flavour, executable)
    seen_configs: set[Path] = set()
    result: list[SlicerFilament] = []
    seen_filaments: set[tuple[str, str]] = set()
    for root in user_roots(flavour, executable):
        config = root.parent.parent / f"{root.parent.parent.name}.conf"
        if config in seen_configs or not config.is_file():
            continue
        seen_configs.add(config)
        document = _configuration(config)
        if document is None:
            continue
        presets = document.get("presets")
        machine = presets.get("machine") if isinstance(presets, dict) else None
        if not isinstance(machine, str) or not machine:
            continue
        state = _machine_state(document, machine)
        if state is None:
            continue
        names = _filament_names(state)
        colours = _filament_colours(state)
        for index, name in enumerate(names):
            path = _named_profile(executable, flavour, name, "filament")
            values = resolve_values(path, roots) if path is not None else {}
            colour = colours[index] if index < len(colours) else ""
            if not _is_colour(colour):
                colour = _first_string(values.get("filament_colour"))
            if not _is_colour(colour):
                continue
            material_type = _first_string(values.get("filament_type"))
            key = (name, colour.casefold())
            if key in seen_filaments:
                continue
            seen_filaments.add(key)
            result.append(
                SlicerFilament(
                    profile=name,
                    colour=colour.upper(),
                    material_type=material_type,
                )
            )
    return tuple(result)


def _configuration(path: Path) -> dict[str, Any] | None:
    """Das erste JSON-Dokument einer Slicer-Konfiguration."""
    try:
        document, _end = json.JSONDecoder().raw_decode(
            path.read_text(encoding="utf-8", errors="replace").lstrip()
        )
    except (OSError, ValueError) as problem:
        _log.debug("could not read slicer configuration %s: %s", path.name, problem)
        return None
    return document if isinstance(document, dict) else None


def _machine_state(document: Mapping[str, Any], machine: str) -> dict[str, Any] | None:
    """Die gespeicherte Belegung der gewählten Maschine.

    Elegoo, Bambu und Orca benennen die Liste mit ihrem Markennamen. Der
    Inhalt trägt dagegen überall ``machine``; daran wird erkannt statt an
    drei Herstellernamen.
    """
    for key, value in document.items():
        if not key.casefold().endswith("presets") or not isinstance(value, list):
            continue
        for entry in value:
            if isinstance(entry, dict) and entry.get("machine") == machine:
                return entry
    return None


def _filament_names(state: Mapping[str, Any]) -> list[str]:
    """``filament``, ``filament_01`` … in Extruderreihenfolge."""
    indexed: list[tuple[int, str]] = []
    for key, value in state.items():
        if not isinstance(value, str) or not value:
            continue
        if key == "filament":
            indexed.append((0, value))
        elif key.startswith("filament_") and key[9:].isdigit():
            indexed.append((int(key[9:]), value))
    return [value for _index, value in sorted(indexed)]


def _filament_colours(state: Mapping[str, Any]) -> list[str]:
    value = state.get("filament_colors")
    return [entry.strip() for entry in value.split(",")] if isinstance(value, str) else []


def _is_colour(value: str) -> bool:
    return (
        len(value) == 7
        and value.startswith("#")
        and all(letter in "0123456789abcdefABCDEF" for letter in value[1:])
    )


def _named_profile(
    executable: Path,
    flavour: SlicerFlavour,
    name: str,
    kind: ProfileKind,
) -> Path | None:
    """Eine Profil-Datei über ihren Namen, ohne den ganzen Bestand zu lesen.

    Der übliche Fall hat denselben Datei- und Profilnamen. Nur diese Dateien
    werden geöffnet; sechstausend Filamente einzulesen, um eine eingelegte
    Spule zu beschreiben, kostete am Elegoo-Bestand knapp sieben Sekunden.
    """
    # Das selbst angelegte Profil ist das, was der Nutzer im Slicer sieht.
    # Es gewinnt deshalb bei gleichem Namen gegen die mitgelieferte Vorlage —
    # dieselbe Regel wie in ``find_profiles`` und ``match_filament``.
    roots = list(user_roots(flavour, executable))
    installed = install_root(executable)
    if installed is not None:
        roots.append(installed)
    for root in roots:
        # Profilnamen können Schrägstriche oder Globzeichen enthalten. Sie
        # sind Identitäten und werden nie als Suchmuster interpretiert.
        for path in root.rglob("*.json"):
            if path.stem != name:
                continue
            if _kind_of(path, root) != kind:
                continue
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except OSError, ValueError:
                continue
            if isinstance(loaded, dict) and str(loaded.get("name", path.stem)) == name:
                return path
        # Noch innerhalb derselben Quelle suchen: Ein umbenanntes eigenes
        # Profil gewinnt auch gegen einen passend benannten Installationspfad.
        found = _names_in(root, kind).get(name)
        if found is not None:
            return found
    return None


def _names_the_printer(machine: str, title: str) -> bool:
    """Meint dieser Maschinenname diesen Drucker?

    Der Name des Slicers trägt Düse und Zusätze („… 0.4 nozzle"), der von
    Solidon nicht; verglichen wird deshalb am Anfang. Ein leerer Titel meint
    nichts — sonst passte er auf jede Maschine.

    Die eine Stelle für diesen Vergleich: :func:`printer_for` fragt „welcher
    meiner Drucker ist das", :func:`supports_printer` fragt „kennt dieser
    Slicer meinen Drucker". Zwei Formulierungen desselben Vergleichs würden
    auseinanderlaufen, sobald einer von beiden verfeinert wird.
    """

    def normalized(value: str) -> str:
        value = value.casefold().removeprefix("original ")
        return re.sub(r"^prusa mini(?:\+| is)?(?=\s|$)", "prusa mini", value)

    return bool(title) and normalized(machine).startswith(normalized(title))


def known_printers(flavour: SlicerFlavour, executable: Path) -> tuple[str, ...]:
    """Welche Drucker dieser Slicer überhaupt kennt (§29).

    **Nicht dasselbe wie** :func:`find_profiles` **mit** ``machine``: Dort
    geht es um die Auswahl eines Profils, und für PrusaSlicer gibt es die
    nicht — es braucht keines, Solidon beschreibt die Maschine selbst. Hier
    geht es um Wissen: Wer zwei Drucker und zwei Slicer hat, will sehen,
    welcher davon den vor ihm stehenden überhaupt kennt.

    PrusaSlicer führt seine Modelle in den Herstellerbündeln unter
    ``[printer_model:…]``. Gelesen wird zeilenweise und nicht über
    ConfigParser: 35 Bündel mit zusammen mehreren zehntausend Abschnitten
    kosten so 0,13 Sekunden für 261 Modelle.
    """
    if flavour == "prusa":
        return _prusa_printer_models(executable)
    return tuple(
        # Bei Cura ist der Anzeigename die Auskunft („Abax PRi3"); die
        # Orca-Familie trägt das Modell getrennt vom Profilnamen, der die
        # Düse mitnennt.
        entry.name if flavour == "cura" else (entry.printer_model or entry.name)
        for entry in find_profiles(executable, flavour, kinds=("machine",))
    )


def supports_printer(flavour: SlicerFlavour, executable: Path, title: str) -> bool:
    """Kennt dieser Slicer den Drucker mit diesem Titel?

    Die Umkehrung von :func:`printer_for` und über denselben Vergleich, damit
    beide dieselbe Antwort geben.
    """
    return any(_names_the_printer(name, title) for name in known_printers(flavour, executable))


def _prusa_printer_models(executable: Path) -> tuple[str, ...]:
    """Die Modellnamen aus den Herstellerbündeln von PrusaSlicer."""
    root = install_root(executable)
    if root is None:
        return ()
    found: list[str] = []
    for path in sorted(root.glob("*.ini")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as problem:
            _log.debug("skipping Prusa bundle %s: %s", path.name, problem)
            continue
        for index, line in enumerate(lines):
            if not line.startswith("[printer_model:"):
                continue
            # Der Name steht in den ersten Zeilen des Abschnitts; danach
            # folgen Varianten, Bettmodell und Vorschaubild.
            for following in lines[index + 1 : index + 6]:
                if following.startswith("name"):
                    name = following.split("=", 1)[-1].strip()
                    if name:
                        found.append(name)
                    break
    return tuple(found)


def printer_for(machine: str, known: Mapping[str, PrinterProfile]) -> str:
    """Welches Druckerprofil dieser Maschinenname meint — oder nichts.

    Der Name des Slicers trägt Düse und Zusätze („… 0.4 nozzle"), der von
    Solidon nicht; verglichen wird deshalb am Anfang. Trifft nichts, bleibt es
    leer: geraten wird hier so wenig wie in :func:`match`.
    """
    hits = [
        identifier
        for identifier, profile in known.items()
        if _names_the_printer(machine, profile.title)
    ]
    if not hits:
        return ""
    # Der längste Titel gewinnt: „Elegoo Neptune 4 Plus" vor „Elegoo Neptune 4".
    return max(hits, key=lambda identifier: len(known[identifier].title))


def _read(path: Path, kind: ProfileKind, from_user: bool) -> SlicerProfile | None:
    """Ein Profil aus seiner Datei. Was sich nicht lesen lässt, fehlt einfach.

    Ein kaputtes oder unbekanntes JSON im Bestand eines fremden Programms ist
    kein Grund, die Auswahl scheitern zu lassen — es ist ein Eintrag weniger.

    Die Art kommt aus dem Ordner und nicht aus dem Feld ``type``: selbst
    angelegte Profile tragen es gar nicht, sie erben bloß von einem
    Systemprofil. Genau die will man in der Liste haben.
    """
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _log.debug("skipping profile %s: %s", path.name, problem)
        return None
    if not isinstance(loaded, dict):
        return None

    # Zwischenstücke der Erbkette (`fdm_process_common` und Verwandte) sind im
    # Slicer selbst nicht wählbar und hier ebenso wenig. Erkennbar sind sie
    # daran, dass sie weder instanziierbar noch selbst angelegt sind.
    instantiable = str(loaded.get("instantiation", "")).casefold() == "true"
    own = str(loaded.get("from", "")).casefold() == "user"
    if not instantiable and not own:
        return None

    return SlicerProfile(
        path=path,
        name=str(loaded.get("name", path.stem)),
        kind=kind,
        printer_model=str(loaded.get("printer_model", "")),
        nozzle=_first_number(loaded.get("nozzle_diameter")),
        compatible_printers=tuple(_strings(loaded.get("compatible_printers"))),
        default_process=str(loaded.get("default_print_profile", "")),
        filament_type=_first_string(loaded.get("filament_type")),
        from_user=from_user or own,
        inherits=str(loaded.get("inherits", "")),
    )


def _first_string(value: Any) -> str:
    """Filamentwerte stehen als Liste, ein Eintrag je Platz."""
    if isinstance(value, list) and value:
        value = value[0]
    return str(value) if isinstance(value, str) else ""


def _first_number(value: Any) -> float:
    """Die Düse steht als Liste von Zeichenketten da — eine je Extruder."""
    if isinstance(value, list) and value:
        value = value[0]
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(entry) for entry in value]
    return [str(value)] if isinstance(value, str) else []


#: Curas Ordner und was darin liegt.
#:
#: **Der Bestand ist da, er liegt nur woanders und anders.** Die Orca-Familie
#: legt alles als JSON unter ``machine``/``process``/``filament`` ab; Cura
#: benennt seine Ordner anders und benutzt drei Formate — JSON für Drucker,
#: INI für Qualität, XML für Material. Die gemeinsame Suche fand deshalb
#: nichts: gemessen am 08.09.2026 an Cura 5.13 null Profile, während 615
#: Drucker, 281 Materialien und 6010 Qualitätsprofile danebenlagen.
_CURA_DIRS: Final[dict[str, tuple[ProfileKind, str]]] = {
    "definitions": ("machine", "*.def.json"),
    "quality": ("process", "*.inst.cfg"),
    "quality_changes": ("process", "*.inst.cfg"),
    "materials": ("filament", "*.xml.fdm_material"),
}

#: Der Namensraum, in dem eine Materialdatei ihre Felder trägt.
_CURA_MATERIAL_NS: Final = {"m": "http://www.ultimaker.com/material"}

#: Ein Farbname, der keine Farbe meint. Cura schreibt ihn, wo die Spule keine
#: eigene hat; im Namen sähe er aus wie eine Sorte („PLA Generic").
_CURA_UNSPECIFIC_COLOUR: Final = "generic"

#: Was im Qualitätsordner wirklich ein Prozessprofil ist. Daneben liegen dort
#: ``intent``-Dateien — Absichten wie „technisch" oder „optisch", die auf einem
#: Prozessprofil aufsetzen und ohne es nichts bedeuten.
_CURA_PROCESS_TYPES: Final = frozenset({"quality", "quality_changes"})


def _cura_profiles(executable: Path, wanted: frozenset[ProfileKind]) -> list[SlicerProfile]:
    """Curas Installation und eigener Bestand, eigene Profile gewinnen bei gleichem Namen."""
    found: dict[tuple[ProfileKind, str], SlicerProfile] = {}
    count = 0
    users = user_roots("cura", executable)
    for root in profile_roots("cura", executable):
        for folder, (kind, pattern) in _CURA_DIRS.items():
            if kind not in wanted:
                continue
            for path in sorted((_cura_resources(root) / folder).rglob(pattern)):
                count += 1
                if count > MAX_FILES:
                    _log.warning("stopped after %d Cura profile files below %s", MAX_FILES, root)
                    return list(found.values())
                profile = _read_cura(path, kind)
                if profile is not None:
                    # Gleicher Titel bei anderem Durchmesser ist eine andere
                    # native Datei und darf nicht still ersetzt werden.
                    found[(kind, path.name)] = replace(profile, from_user=root in users)
    _log.info("found %d Cura profiles", len(found))
    return list(found.values())


def _cura_user_roots(executable: Path, config: Path, *, platform: str | None = None) -> list[Path]:
    """Cura speichert je Programmversion, nicht je Nutzerkonto."""
    candidates = [config / "cura"]
    if (platform or sys.platform).startswith("linux"):
        named = os.environ.get("XDG_DATA_HOME", "")
        data = (
            Path(named) if named and not discover.in_flatpak() else Path.home() / ".local" / "share"
        )
        candidates.insert(0, data / "cura")
    version = next(
        (
            match.group(1)
            for parent in executable.parents
            if (match := re.search(r"cura[^\d]*(\d+\.\d+)", parent.name, re.IGNORECASE))
        ),
        "",
    )
    found: list[Path] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        versions = sorted(
            (
                folder
                for folder in candidate.iterdir()
                if folder.is_dir() and re.fullmatch(r"\d+\.\d+", folder.name)
            ),
            key=lambda folder: tuple(int(part) for part in folder.name.split(".")),
        )
        selected = (
            [folder for folder in versions if folder.name == version] if version else versions[-1:]
        )
        if not versions:
            selected = [candidate]
        found.extend(folder for folder in selected if folder not in found)
    return found


def _cura_resources(root: Path) -> Path:
    """Wo Curas Bestand unter der Installationswurzel liegt.

    :func:`install_root` endet bei Cura auf ``share/cura``, die Ordner selbst
    liegen eine Ebene tiefer unter ``resources``. Beide Formen werden geprüft,
    damit eine andere Ablage — Linux-Paket, AppImage — nicht am Zwischenstück
    scheitert; gefragt wird über ``discover``, weil ``is_dir()`` aus einem
    Flatpak heraus auf einen Host-Pfad zuverlässig nein sagt.
    """
    candidate = root / "resources"
    return candidate if discover.is_dir_on_host(candidate) else root


def _read_cura(path: Path, kind: ProfileKind) -> SlicerProfile | None:
    """Ein Cura-Profil aus seiner Datei — je Art ein anderes Format.

    Wie beim Orca-Leser gilt: Was sich nicht lesen lässt, fehlt einfach. Eine
    beschädigte Datei im Bestand eines fremden Programms ist ein Eintrag
    weniger und kein Grund, die Auswahl scheitern zu lassen.
    """
    if kind == "machine":
        return _read_cura_machine(path)
    if kind == "process":
        return _read_cura_process(path)
    return _read_cura_material(path)


def _read_cura_machine(path: Path) -> SlicerProfile | None:
    """Ein Drucker aus ``<name>.def.json``.

    ``metadata.visible`` ist Curas Gegenstück zu ``instantiation``: Damit
    trennt es die 615 wählbaren Drucker von den Zwischenstücken der Erbkette
    (``fdmprinter``, ``ultimaker``). Fehlt die Angabe, erbt Cura sie — hier
    zählt das als sichtbar, weil ein fälschlich angebotener Drucker
    verschmerzbar ist und ein fehlender nicht.

    **Die Düse steht meist nicht darin**, sondern eine Ebene höher in der
    Erbkette. Sie wird gelesen, wo sie steht, und bleibt sonst null — die
    Kette aufzulösen hieße, Cura nachzubauen.
    """
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _log.debug("skipping Cura definition %s: %s", path.name, problem)
        return None
    if not isinstance(loaded, dict):
        return None
    metadata = loaded.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("visible") is False:
        return None
    overrides = loaded.get("overrides")
    nozzle = 0.0
    if isinstance(overrides, Mapping):
        size = overrides.get("machine_nozzle_size")
        if isinstance(size, Mapping):
            nozzle = _first_number(size.get("default_value"))
    return SlicerProfile(
        path=path,
        name=str(loaded.get("name", path.stem)),
        kind="machine",
        # Curas Kennung des Druckers, nicht sein Anzeigename: Genau darauf
        # zeigt ``definition`` in jedem Qualitätsprofil, und darüber hängen
        # die beiden zusammen.
        printer_model=_cura_definition_id(path),
        nozzle=nozzle,
        inherits=str(loaded.get("inherits", "")),
    )


def _read_cura_process(path: Path) -> SlicerProfile | None:
    """Ein Qualitätsprofil aus ``*.inst.cfg`` — eine INI-Datei.

    Die Bindung an den Drucker steht in ``[general] definition`` und ist
    Curas Gegenstück zu ``compatible_printers``: ein Wert statt einer Liste,
    aber dieselbe Auskunft.
    """
    parsed = _read_ini(path)
    if parsed is None:
        return None
    general = parsed["general"] if parsed.has_section("general") else {}
    metadata = parsed["metadata"] if parsed.has_section("metadata") else {}
    if str(metadata.get("type", "")).strip() not in _CURA_PROCESS_TYPES:
        return None
    definition = str(general.get("definition", "")).strip()
    return SlicerProfile(
        path=path,
        name=str(general.get("name", path.stem)),
        kind="process",
        compatible_printers=(definition,) if definition else (),
    )


def _read_ini(path: Path) -> configparser.ConfigParser | None:
    """Eine Cura-INI, ohne dass ein ``%`` darin zum Fehler wird.

    ``interpolation=None``, weil Prozentzeichen in Werten stehen dürfen und
    ConfigParser sie sonst als Platzhalter liest.
    """
    parsed = configparser.ConfigParser(interpolation=None)
    try:
        parsed.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as problem:
        _log.debug("skipping Cura profile %s: %s", path.name, problem)
        return None
    return parsed


def _read_cura_material(path: Path) -> SlicerProfile | None:
    """Eine Spule aus ``*.xml.fdm_material``.

    Diese Dateien tragen genau die Felder, die ein Filament in Solidon
    ausmachen: Marke, Materialart, Farbname und Farbwert. Der Name wird daraus
    zusammengesetzt, wie Cura ihn auch anzeigt — „Best Filament PETG Orange" —,
    und ein Farbname, der keine Farbe meint, bleibt weg.
    """
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as problem:
        _log.debug("skipping Cura material %s: %s", path.name, problem)
        return None
    name = root.find("m:metadata/m:name", _CURA_MATERIAL_NS)
    if name is None:
        return None
    brand = (name.findtext("m:brand", "", _CURA_MATERIAL_NS) or "").strip()
    material = (name.findtext("m:material", "", _CURA_MATERIAL_NS) or "").strip()
    colour = (name.findtext("m:color", "", _CURA_MATERIAL_NS) or "").strip()
    if colour.casefold() == _CURA_UNSPECIFIC_COLOUR:
        colour = ""
    title = " ".join(part for part in (brand, material, colour) if part)
    if not title:
        return None
    return SlicerProfile(
        path=path,
        name=title,
        kind="filament",
        filament_type=material,
    )


def _cura_definition_id(path: Path) -> str:
    """Aus ``abax_pri3.def.json`` wird ``abax_pri3``.

    ``Path.stem`` allein reicht nicht: Es bleibt ``abax_pri3.def`` stehen, und
    unter diesem Namen findet kein Qualitätsprofil seinen Drucker.
    """
    return path.stem.removesuffix(".def")


def _cura_definition_values(path: Path, roots: Sequence[Path]) -> dict[str, Any]:
    """Definitionsvererbung als Daten; berechnete Eigenschaften bleiben unbekannt."""
    index = {
        _cura_definition_id(entry): entry
        for root in roots
        for entry in sorted((_cura_resources(root) / "definitions").glob("*.def.json"))
    }
    index.update(
        {_cura_definition_id(entry): entry for entry in sorted(path.parent.glob("*.def.json"))}
    )

    def read(current: Path, active: frozenset[Path]) -> dict[str, dict[str, Any]]:
        if current in active or len(active) >= MAX_INHERITANCE:
            raise _incomplete_profile(path)
        try:
            loaded = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, ValueError) as problem:
            raise _incomplete_profile(path) from problem
        if not isinstance(loaded, dict):
            raise _incomplete_profile(path)
        definitions: dict[str, dict[str, Any]] = {}
        parent = loaded.get("inherits")
        if parent:
            inherited = index.get(str(parent))
            if inherited is None:
                raise _incomplete_profile(path)
            definitions.update(read(inherited, active | {current}))

        def collect(items: Any) -> None:
            if not isinstance(items, dict):
                return
            for key, properties in items.items():
                if not isinstance(properties, dict):
                    continue
                definitions.setdefault(key, {}).update(properties)
                collect(properties.get("children"))

        collect(loaded.get("settings"))
        collect(loaded.get("overrides"))
        return definitions

    values: dict[str, Any] = {}
    for key, properties in read(path, frozenset()).items():
        # Eine Formel überlagert auch einen vorhandenen default_value. Der
        # Default ist dann gerade nicht der Wert, den Cura berechnet.
        if "value" in properties:
            value = properties["value"]
            if isinstance(value, str):
                continue
        else:
            value = properties.get("default_value")
        if value is not None:
            values[key] = value
    return values


_CURA_MATERIAL_KEYS: Final = {
    "print temperature": "material_print_temperature",
    "heated bed temperature": "material_bed_temperature",
    "build volume temperature": "build_volume_temperature",
    "print cooling": "cool_fan_speed",
    "retraction amount": "retraction_amount",
    "retraction speed": "retraction_speed",
}


def _cura_material_values(path: Path) -> dict[str, Any]:
    """Die allgemeinen XML-Materialwerte, ohne fremde Maschinenvarianten zu übernehmen."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as problem:
        _log.debug("skipping Cura material %s: %s", path.name, problem)
        return {}
    values: dict[str, Any] = {}
    for source, target in (
        ("metadata/name/material", "filament_type"),
        ("metadata/color_code", "filament_colour"),
        ("properties/density", "material_density"),
        ("properties/diameter", "material_diameter"),
    ):
        text = root.findtext(
            "/".join(f"m:{part}" for part in source.split("/")), "", _CURA_MATERIAL_NS
        )
        if text and text.strip():
            values[target] = text.strip()
    for item in root.findall("m:settings/m:setting", _CURA_MATERIAL_NS):
        key = _CURA_MATERIAL_KEYS.get(item.get("key", ""))
        if key and item.text and item.text.strip():
            values[key] = item.text.strip()
    return values


def _kind_of(path: Path, root: Path) -> ProfileKind | None:
    """Maschine oder Prozess — abgelesen am Ordner, in dem die Datei liegt.

    Die Ablage ist zwischen den Herstellern nicht einheitlich, deshalb wird
    der ganze Pfad unterhalb der Wurzel abgesucht statt einer festen Tiefe.
    """
    try:
        parts = path.relative_to(root).parts[:-1]
    except ValueError:
        return None
    for part in parts:
        found = PROFILE_DIRS.get(part.casefold())
        if found is not None:
            return found
    return None


#: Was gelesen wird, wenn nichts anderes verlangt ist. Filamentprofile bleiben
#: draußen, weil sie den Bestand vervielfachen: bei ElegooSlicer stehen 5962
#: Filamenten 3887 Maschinen- und Prozessprofile gegenüber, und das Lesen aller
#: dauert fünfzehn statt sechs Sekunden. Wer sie braucht, fragt danach — beim
#: Slicen fällt die Zeit neben dem Lauf selbst nicht auf.
DEFAULT_KINDS: Final[tuple[ProfileKind, ...]] = ("machine", "process")


def find_profiles(
    executable: Path,
    flavour: SlicerFlavour,
    kinds: Sequence[ProfileKind] = DEFAULT_KINDS,
) -> list[SlicerProfile]:
    """Alle benutzbaren Profile dieses Slicers, mitgelieferte und eigene.

    Prusa-Bündel behalten zusätzlich ihren Abschnittsnamen. Versteckte
    Erbbasen sind auflösbar, werden aber nicht als eigene Auswahl angeboten.
    """
    wanted = frozenset(kinds)
    if flavour == "prusa":
        return _prusa_profiles(executable, wanted)
    if not has_readable_profiles(flavour):
        return []
    if flavour == "cura":
        # Eigene Ordnernamen, drei Formate: die Suche darunter findet dort
        # nichts (:data:`_CURA_DIRS`).
        return _cura_profiles(executable, wanted)

    found: list[SlicerProfile] = []
    seen: set[str] = set()
    roots: list[tuple[Path, bool]] = []
    installed = install_root(executable)
    if installed is not None:
        roots.append((installed, False))
    roots.extend((folder, True) for folder in user_roots(flavour, executable))

    count = 0
    for root, from_user in roots:
        for path in sorted(root.rglob("*.json")):
            # Die Ordnertiefe ist nicht einheitlich: Bambu legt seine Profile
            # direkt in `machine/`, Elegoo eine Ebene tiefer in `machine/ECC2/`.
            # Gesucht wird deshalb nach dem Ordner irgendwo im Pfad, nicht nach
            # einer festen Form.
            kind = _kind_of(path, root)
            if kind is None or kind not in wanted:
                continue
            count += 1
            if count > MAX_FILES:
                _log.warning("stopped after %d profile files below %s", MAX_FILES, root)
                break
            profile = _read(path, kind, from_user)
            if profile is None:
                continue
            # Eigene schlagen mitgelieferte gleichen Namens — sie sind die
            # Version, die der Nutzer im Slicer selbst sieht. **Und zwar an
            # derselben Stelle**: Bis zum 05.09.2026 wurde das eigene nur
            # angehängt, das mitgelieferte blieb davor in der Liste stehen —
            # ``profile_file`` nahm den ersten Treffer und las die
            # Herstellerfassung statt der geänderten Temperatur des Nutzers
            # (Gesamtreview, CORE-15).
            key = f"{profile.kind}:{profile.name}"
            if key in seen:
                if not profile.from_user:
                    continue
                position = next(
                    (
                        index
                        for index, known in enumerate(found)
                        if f"{known.kind}:{known.name}" == key
                    ),
                    None,
                )
                if position is not None:
                    found[position] = profile
                    continue
            seen.add(key)
            found.append(profile)

    # Die Auswahl bleibt klein, ihr Wissen umfasst aber auch unsichtbare
    # Erbbasen. Pro Hersteller wird der Namensindex nur einmal gelesen.
    indexes: ProfileIndexes = {}
    all_roots = profile_roots(flavour, executable)
    incomplete: set[int] = set()
    for index, profile in enumerate(found):
        if profile.compatible_printers or not profile.inherits:
            continue
        try:
            chain = _chain(profile.path, all_roots, indexes=indexes)
        except ExternalToolError as problem:
            _log.warning("skipping incomplete profile %s: %s", profile.name, problem)
            incomplete.add(index)
            continue
        for loaded in chain:
            compatibility = tuple(_strings(loaded.get("compatible_printers")))
            if compatibility:
                found[index] = replace(profile, compatible_printers=compatibility)
                break
    found = [profile for index, profile in enumerate(found) if index not in incomplete]
    _log.info("found %d slicer profiles", len(found))
    return found


#: Felder, die das Profil beschreiben statt einen Wert zu setzen. Sie erben
#: sich nicht weiter — ein Name gilt für ein Profil, nicht für seine Kinder.
#: Woran die Orca-Familie die Verträglichkeit prüft — nicht Werte,
#: sondern die Frage, zu welchem Drucker ein Profil überhaupt gehört.
_BINDING = ("compatible_printers", "compatible_printers_condition")

DESCRIBING_KEYS: Final = frozenset(
    {
        "type",
        "name",
        "inherits",
        "include",
        "from",
        "instantiation",
        "setting_id",
        "filament_id",
        "compatible_printers",
        "compatible_printers_condition",
        "compatible_prints",
        "compatible_prints_condition",
        "renamed_from",
        "description",
        "version",
    }
)


def _family(path: Path) -> Path:
    """Der Ordner, unter dem die Vorfahren eines Profils **zuerst** gesucht
    werden.

    Die Erbkette eines mitgelieferten Filamentprofils bleibt innerhalb seines
    ``filament/``, und dort sind es zweihundert Dateien statt elftausend. Ein
    **eigenes** Profil erbt dagegen aus einem anderen Baum — dafür steht
    :func:`_store_roots` bereit, und die Kette fragt dort erst, wenn hier
    nichts gefunden wird.
    """
    for parent in path.parents:
        if parent.name.casefold() in PROFILE_DIRS:
            return parent
    return path.parent


def _kind_by_folder(path: Path) -> ProfileKind | None:
    """Die Art eines Profils, abgelesen an seinem Ordner — ohne Wurzel."""
    for parent in path.parents:
        found = PROFILE_DIRS.get(parent.name.casefold())
        if found is not None:
            return found
    return None


def profile_roots(flavour: SlicerFlavour, executable: Path) -> tuple[Path, ...]:
    """Alle Wurzeln des Profilbestands dieser Installation, mitgelieferte
    zuerst: ``resources/profiles`` neben dem Programm, die eigenen
    ``user/<Konto>`` und der ``system``-Bestand daneben, in den die
    Orca-Familie die gewählten Herstellerbündel kopiert.

    Die Erbkette eines eigenen Profils (:func:`resolve_values`) braucht sie:
    Ein im Slicer angelegtes Filament unter ``user/<Konto>/filament/`` erbt
    mit ``inherits`` von einer Herstellerdatei unter ``resources/profiles/``
    — und setzt selbst nur den Fluss. Temperatur und Materialtyp stehen in
    der Basis, und die lag in einem Baum, den die Kette nie ansah: Sie endete
    ohne Meldung beim Nutzerdelta, das ausgeschriebene Profil ging ohne
    Temperaturen zum Slicer (Gesamtreview 05.09.2026, CORE-14).
    """
    roots: list[Path] = []
    installed = install_root(executable)
    if installed is not None:
        roots.append(installed)
    for folder in user_roots(flavour, executable):
        roots.append(folder)
        if flavour in {"prusa", "cura"}:
            continue
        system = folder.parent.parent / "system"
        if system.is_dir() and system not in roots:
            roots.append(system)
    return tuple(roots)


_PRUSA_KINDS: Final[dict[str, ProfileKind]] = {
    "printer": "machine",
    "print": "process",
    "filament": "filament",
}


def _prusa_files(root: Path) -> list[Path]:
    """Aktive Bündel und eigene Profile; Update-Downloads unter cache bleiben draußen."""
    return sorted(
        {
            *root.glob("*.ini"),
            *(
                path
                for directory in (*_PRUSA_KINDS, "vendor")
                for path in (root / directory).glob("*.ini")
            ),
        }
    )


def _prusa_list(value: str) -> list[str]:
    """Prusa trennt Erbbasen mit Semikolon und erlaubt zitierte Namen."""
    try:
        return [
            item.strip()
            for item in next(
                csv.reader(
                    [value], delimiter=";", quotechar='"', escapechar="\\", skipinitialspace=True
                )
            )
            if item.strip()
        ]
    except csv.Error:
        return []


class _PrusaStore:
    """Ein Lesedurchgang: Abschnitte und aufgelöste Werte bleiben im Speicher."""

    def __init__(self, roots: Sequence[Path], *, eager: bool = True) -> None:
        self.roots = roots
        self.documents: dict[Path, configparser.ConfigParser] = {}
        self.entries: list[SlicerProfile] = []
        self.by_name: dict[tuple[ProfileKind, str], list[SlicerProfile]] = {}
        self.resolved: dict[tuple[Path, str], dict[str, Any]] = {}
        if not eager:
            return
        for root in roots:
            for path in _prusa_files(root):
                if len(self.documents) >= MAX_FILES:
                    return
                self.read(path)

    def find_parent(self, name: str, kind: ProfileKind) -> None:
        """Beim Einzelabruf nur die Bündel öffnen, die den Elternnamen tragen."""
        prefix = next(key for key, value in _PRUSA_KINDS.items() if value == kind)
        heading = f"[{prefix}:{name}]"
        for root in self.roots:
            for index, path in enumerate(_prusa_files(root)):
                if index >= MAX_FILES:
                    break
                if path in self.documents:
                    continue
                if path.parent.name == prefix and path.stem == name:
                    self.read(path)
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if heading in text.splitlines():
                    self.read(path)

    def read(self, path: Path) -> None:
        """Ein Bündel oder eine kopflose eigene Einzeldatei lesen."""
        if path in self.documents:
            return
        document = _read_prusa_ini(path)
        if document is None:
            return
        self.documents[path] = document
        start = len(self.entries)
        own_kind = _PRUSA_KINDS.get(path.parent.name)
        if own_kind and document[_PRUSA_HEAD]:
            self.entries.append(
                SlicerProfile(
                    path,
                    path.stem,
                    own_kind,
                    from_user=True,
                    section=_PRUSA_HEAD,
                    inherits=document[_PRUSA_HEAD].get("inherits", ""),
                )
            )
        for section in document.sections():
            prefix, separator, name = section.partition(":")
            kind = _PRUSA_KINDS.get(prefix)
            if separator and kind:
                self.entries.append(
                    SlicerProfile(
                        path,
                        name,
                        kind,
                        section=section,
                        inherits=document[section].get("inherits", ""),
                    )
                )
        for entry in self.entries[start:]:
            self.by_name.setdefault((entry.kind, entry.name), []).append(entry)

    def resolve(
        self, profile: SlicerProfile, active: frozenset[tuple[Path, str]] = frozenset()
    ) -> dict[str, Any]:
        """Innerhalb eines Bündels erben; eigene Dateien dürfen Herstellerbasen nutzen."""
        key = (profile.path, profile.section)
        if key in active or len(active) >= MAX_INHERITANCE:
            raise _incomplete_profile(profile.path)
        if key in self.resolved:
            return self.resolved[key]
        self.read(profile.path)
        document = self.documents.get(profile.path)
        section = profile.section or _PRUSA_HEAD
        if document is None or not document.has_section(section):
            return {}
        raw = dict(document[section])
        values: dict[str, Any] = {}
        for name in _prusa_list(raw.get("inherits", "")):
            if profile.from_user:
                self.find_parent(name, profile.kind)
            candidates = [
                entry
                for entry in self.by_name.get((profile.kind, name), ())
                if (entry.path, entry.section) != key
            ]
            local = [entry for entry in candidates if entry.path == profile.path]
            # Bündelbasen sind dateilokal; gleichnamige *common*-Abschnitte
            # anderer Hersteller sind ausdrücklich keine Ersatzbasis.
            choices = local or (candidates if profile.from_user else [])
            if not choices:
                raise _incomplete_profile(profile.path)
            parent = max(enumerate(choices), key=lambda item: (item[1].from_user, item[0]))[1]
            values.update(self.resolve(parent, active | {key}))
        values.update({name: value for name, value in raw.items() if name != "inherits"})
        self.resolved[key] = values
        return values


def _prusa_profiles(executable: Path, wanted: frozenset[ProfileKind]) -> list[SlicerProfile]:
    """Native Profile, mit aufgelöster Maschinenidentität und unsichtbaren Erbbasen."""
    store = _PrusaStore(profile_roots("prusa", executable))
    found: dict[tuple[ProfileKind, str], SlicerProfile] = {}
    for entry in store.entries:
        if entry.kind not in wanted or (entry.name.startswith("*") and entry.name.endswith("*")):
            continue
        try:
            values = store.resolve(entry)
        except ExternalToolError as problem:
            _log.warning("skipping incomplete Prusa profile %s: %s", entry.name, problem)
            continue
        if entry.kind == "machine" and values.get("printer_technology") == "SLA":
            continue
        model = str(values.get("printer_model", ""))
        section = f"printer_model:{model}"
        document = store.documents[entry.path]
        if document.has_section(section):
            model = document[section].get("name", model)
        profile = replace(
            entry,
            printer_model=model,
            nozzle=_first_number(str(values.get("nozzle_diameter", "")).split(",")[0]),
            default_process=str(values.get("default_print_profile", "")),
            filament_type=str(values.get("filament_type", "")),
            compatible_printers=tuple(_prusa_list(str(values.get("compatible_printers", "")))),
        )
        key = (profile.kind, profile.name)
        if key not in found or profile.from_user or not found[key].from_user:
            found[key] = profile
    return list(found.values())


def profile_by_name(
    executable: Path, flavour: SlicerFlavour, name: str, kind: ProfileKind
) -> SlicerProfile | None:
    """Portable Identität auflösen; Prusa behält den Abschnitt neben dem Pfad."""
    matches = [entry for entry in find_profiles(executable, flavour, (kind,)) if entry.name == name]
    choices = [entry for entry in matches if entry.from_user] or matches
    return choices[0] if len(choices) == 1 else None


def resolve_profile(
    profile: SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> dict[str, Any]:
    """Native Werte ausschreiben, ohne Formeln oder G-Code auszuführen.

    Prusa-Werte bleiben INI-serialisiert (auch ``\\n`` in G-Code), Cura und
    Orca behalten die Werttypen ihrer Dateien. Eine Prusa-Bündeldatei braucht
    zwingend die Abschnittsidentität aus :func:`profile_by_name`.
    """
    if profile.path.suffix == ".ini":
        store = _PrusaStore(roots, eager=False)
        return dict(store.resolve(profile))
    return resolve_values(profile.path, roots, indexes=indexes)


def _store_roots(path: Path, roots: Sequence[Path]) -> list[Path]:
    """Wo die Vorfahren eines Profils außerhalb seines eigenen Ordners liegen.

    Ausdrücklich genannte Wurzeln zuerst (:func:`profile_roots`), dann die am
    Pfad abgelesenen — für Aufrufer, die nur die Datei kennen: Ein eigenes
    Profil liegt unter ``<Programm>/user/<Konto>/``, und daneben liegt
    ``<Programm>/system/`` mit den kopierten Herstellerbündeln; ein
    mitgeliefertes liegt unter ``resources/profiles``.
    """
    found = [Path(root) for root in roots]
    for parent in path.parents:
        name = parent.name.casefold()
        if name == "user" and parent.parent != parent:
            for candidate in (parent.parent / "system", parent):
                if candidate.is_dir() and candidate not in found:
                    found.append(candidate)
            break
        if name == "profiles" and parent.parent.name.casefold() == "resources":
            if parent not in found:
                found.append(parent)
            break
    return found


def _names_in(root: Path, kind: ProfileKind | None) -> dict[str, Path]:
    """Profilname → Datei für alles unter ``root`` — bei ``kind`` nur die
    Profile dieser Art, gemessen am Ordner unterhalb der Wurzel.

    Der Index läuft über den Profilnamen, nicht über den Dateinamen: darauf
    zeigt ``inherits``. Bei Elegoo sind beide zufällig gleich
    (`Elegoo PETG @base.json`), garantiert ist das nirgends — und wo es nicht
    gilt, bräche die Kette nach der ersten Datei ab, ohne dass etwas fehlend
    aussieht.
    """
    index: dict[str, Path] = {}
    for count, entry in enumerate(sorted(root.rglob("*.json"))):
        if count >= MAX_FILES:
            break
        if kind is not None and _kind_of(entry, root) != kind:
            continue
        try:
            loaded = json.loads(entry.read_text(encoding="utf-8"))
        except OSError, ValueError:
            continue
        if isinstance(loaded, dict):
            index.setdefault(str(loaded.get("name", entry.stem)), entry)
    return index


def resolve_values(
    path: Path,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> dict[str, Any]:
    """Die Werte, mit denen dieses Profil tatsächlich fährt (§29).

    Die Hersteller staffeln in mehreren Ebenen — bei Elegoo etwa
    ``Elegoo PETG Translucent @ECC2`` → ``Elegoo PETG @base`` →
    ``fdm_filament_pet`` → ``fdm_filament_common``. Wer nur die oberste Datei
    liest, sieht drei Werte und hält den Rest für nicht gesetzt. Erst
    zusammengelegt steht da, was der Slicer fährt: 255 °C Düse bei 70 °C Bett.

    Die Zwischenstufen sind selbst nicht wählbar und tauchen deshalb in
    :func:`find_profiles` nicht auf. Hier werden sie gebraucht, also werden sie
    hier gelesen.
    """
    if path.name.endswith(".def.json"):
        return _cura_definition_values(path, roots)
    if path.name.endswith(".xml.fdm_material"):
        return _cura_material_values(path)
    if path.name.endswith(".inst.cfg"):
        parsed = _read_ini(path)
        if parsed is None or not parsed.has_section("values"):
            return {}
        return {
            key: value
            for key, value in parsed["values"].items()
            if not value.lstrip().startswith("=")
        }
    if path.suffix == ".ini":
        kind = _PRUSA_KINDS.get(path.parent.name)
        if kind is None:
            # Ein Bündel ist kein einzelnes Profil. Der Aufrufer braucht
            # dessen Abschnitt, statt zufällig den ersten zu übernehmen.
            raise _incomplete_profile(path)
        return resolve_profile(
            SlicerProfile(path, path.stem, kind, from_user=True), roots, indexes=indexes
        )
    values: dict[str, Any] = {}
    # Wurzel zuerst, Spezielles gewinnt
    for loaded in reversed(_chain(path, roots, indexes=indexes)):
        values.update({key: value for key, value in loaded.items() if key not in DESCRIBING_KEYS})
    return values


def binding(
    path: Path,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> dict[str, Any]:
    """Woran ein Profil seine Verträglichkeit knüpft (§29).

    :func:`resolve_values` lässt die beschreibenden Schlüssel aus
    (``DESCRIBING_KEYS``), und das ist für Werte richtig — ein geerbtes
    ``from: system`` wäre gelogen. Für **die Bindung** ist es falsch:
    ``compatible_printers`` steht selten in der obersten Datei.

    Gemessen am Elegoo-Bestand: ``0.12mm Fine @Elegoo C 0.4 nozzle``
    trägt es nicht, eine Stufe tiefer steht
    ``['Elegoo Centauri 0.4 nozzle']``. Wer die Kette auflöst und die
    Erbschaft wegwirft, verliert es — und der Slicer bricht mit
    „process not compatible with printer" ab, bevor er das Modell
    ansieht.

    Zurück kommt nur, was gesetzt und nicht leer ist: Die unteren
    Stufen führen ``compatible_printers: []`` als Platzhalter, und ein
    leerer Eintrag verträgt sich mit keinem Drucker.
    """
    found: dict[str, Any] = {}
    for loaded in _chain(path, roots, indexes=indexes):  # spezifisch zuerst
        for key in _BINDING:
            value = loaded.get(key)
            if key not in found and value:
                found[key] = value
    return found


def _chain(
    path: Path,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> list[dict[str, Any]]:
    """Die Profile der Erbkette, spezifisches zuerst.

    Roh, ohne Zusammenlegen und ohne Filter: Die beiden Auswertungen
    darüber brauchen Verschiedenes — :func:`resolve_values` die Werte
    ohne die beschreibenden Schlüssel, :func:`binding` ausgerechnet
    einen davon.

    Gesucht wird zuerst im eigenen Ordner (:func:`_family`) und erst bei
    einem Fehlschlag im ganzen Bestand (:func:`_store_roots`) — der ist
    tausende Dateien groß, und die meisten Ketten enden im eigenen Ordner.
    Eine Basis, die nirgends liegt, steht im Protokoll: Die Kette endet dann
    beim Delta, und wer das ausgeschriebene Profil liest, soll wissen, dass
    es unvollständig ist.
    """
    indexes = {} if indexes is None else indexes

    def lookup(current: Path, name: str) -> Path | None:
        family = _family(current)
        family_key = (family, None)
        if family_key not in indexes:
            indexes[family_key] = _names_in(family, None)
        local = indexes[family_key].get(name)
        if local is not None and local != current:
            return local
        for root in _store_roots(current, roots):
            key = (root, _kind_by_folder(current))
            if key not in indexes:
                indexes[key] = _names_in(root, key[1])
            found = indexes[key].get(name)
            if found is not None:
                return found
        return None

    def visit(current: Path, active: frozenset[Path], template: bool) -> list[dict[str, Any]]:
        if current in active or len(active) >= MAX_INHERITANCE:
            if template:
                raise _incomplete_profile(path)
            return []
        try:
            loaded = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, ValueError) as problem:
            _log.debug("stopping at %s: %s", current.name, problem)
            if template:
                raise _incomplete_profile(path) from problem
            return []
        if not isinstance(loaded, dict):
            if template:
                raise _incomplete_profile(path)
            return []
        active = active | {current}
        chain: list[dict[str, Any]] = []
        parent = str(loaded.get("inherits", ""))
        if parent:
            inherited = lookup(current, parent)
            if inherited is not None:
                chain.extend(visit(inherited, active, template))
            elif template:
                raise _incomplete_profile(path)
            else:
                _log.warning(
                    "profile %s inherits %r, which is nowhere in the store — "
                    "the resolved values stop at the child",
                    current.name,
                    parent,
                )
        includes = loaded.get("include", [])
        if not isinstance(includes, (str, list)) or (
            isinstance(includes, list) and any(not isinstance(item, str) for item in includes)
        ):
            raise _incomplete_profile(path)
        for name in _strings(includes):
            included = lookup(current, name)
            if included is None:
                raise _incomplete_profile(path)
            chain.extend(visit(included, active, True))
        chain.append(loaded)
        return chain

    # Bambu: Basis, Vorlagen in Listenreihenfolge, danach eigene Werte.
    return list(reversed(visit(path, frozenset(), False)))


def _incomplete_profile(path: Path) -> ExternalToolError:
    """Eine nicht auflösbare Vorlage darf keinen generischen Ablauf liefern."""
    return ExternalToolError(
        tool=path.name,
        detail=_(
            "Das Slicer-Profil „{name}“ ist unvollständig. Prüfen Sie seine Vorlagen im Slicer.",
            name=path.stem,
        ),
        suggestions=(CHECK_SLICER_PROFILE,),
    )


def machines(profiles: list[SlicerProfile]) -> list[SlicerProfile]:
    return sorted(
        (entry for entry in profiles if entry.kind == "machine"), key=lambda entry: entry.name
    )


#: So tief wird eine Erbkette verfolgt. Drei bis vier Stufen sind üblich; eine
#: Grenze schützt vor einem Kreis in einem selbst angelegten Profil.
MAX_INHERITANCE: Final = 12


def compatible_with(
    profile: SlicerProfile,
    known: dict[str, SlicerProfile],
    *,
    indexes: ProfileIndexes | None = None,
) -> tuple[str, ...]:
    """Für welche Drucker dieses Profil gilt — die eigene Angabe oder die
    geerbte.

    Nur ein Profil je Familie trägt die Liste wirklich; seine Geschwister
    erben sie über ``inherits``. Wer nur das eigene Feld liest, findet für
    einen Drucker genau ein Prozessprofil und hält alle anderen für
    unverträglich.
    """
    if profile.compatible_printers:
        return profile.compatible_printers
    if profile.path.is_file():
        return tuple(_strings(binding(profile.path, indexes=indexes).get("compatible_printers")))
    seen: set[str] = set()
    current: SlicerProfile | None = profile
    for _step in range(MAX_INHERITANCE):
        if current is None or current.name in seen:
            break
        if current.compatible_printers:
            return current.compatible_printers
        seen.add(current.name)
        current = known.get(current.inherits)
    return ()


def _of_kind(
    profiles: list[SlicerProfile],
    machine: SlicerProfile | None,
    kind: str,
    *,
    indexes: ProfileIndexes | None = None,
) -> list[SlicerProfile]:
    """Die Profile einer Art, die zu diesem Drucker passen.

    Ohne Maschine alle. Mit Maschine nur die verträglichen — sonst führt die
    Liste genau in den Abbruch, den sie verhindern soll, und zwar unter
    zweitausend Einträgen.

    Prozesse und Filamente unterschieden sich in dieser Auswahl nur durch die
    Art, nach der sie filtern. Trotzdem stand sie zweimal da, und die Begründung
    für den Rückfall nur einmal — bei den Filamenten traf derselbe Code
    dieselbe Entscheidung ohne einen Satz dazu.
    """
    entries = [entry for entry in profiles if entry.kind == kind]
    if machine is None:
        return sorted(entries, key=lambda entry: entry.name)

    known = {entry.name: entry for entry in entries}
    # **Ein Index für alle Einträge dieser Art.** ``compatible_with`` löst je
    # Profil eine Erbkette auf; ohne geteilten Index liest jede davon die ganze
    # Ablage neu. Beim ElegooSlicer sind das 16 795 Dateien mal der Zahl der
    # Prozesse — der Qt-Hauptthread stand damit 49 Sekunden, und die Zeile
    # darunter zahlte es ein zweites Mal (Befund Robert, 09.09.2026).
    if indexes is None:
        indexes = {}
    fitting = [
        entry for entry in entries if machine.name in compatible_with(entry, known, indexes=indexes)
    ]
    # Findet sich keine ausdrückliche Angabe, ist Zeigen besser als Verschweigen:
    # ein selbst angelegtes Profil ohne Verträglichkeitsliste soll wählbar sein.
    chosen = fitting or [
        entry for entry in entries if not compatible_with(entry, known, indexes=indexes)
    ]
    return sorted(chosen, key=lambda entry: entry.name)


def processes(
    profiles: list[SlicerProfile],
    machine: SlicerProfile | None = None,
    *,
    indexes: ProfileIndexes | None = None,
) -> list[SlicerProfile]:
    """Die Prozessprofile, die zu diesem Drucker passen."""
    return _of_kind(profiles, machine, "process", indexes=indexes)


def filaments(
    profiles: list[SlicerProfile],
    machine: SlicerProfile | None = None,
    *,
    indexes: ProfileIndexes | None = None,
) -> list[SlicerProfile]:
    """Die Filamentprofile, die zu diesem Drucker passen."""
    return _of_kind(profiles, machine, "filament", indexes=indexes)


def match_filament(
    profiles: list[SlicerProfile],
    machine: SlicerProfile | None,
    material_type: str,
    roots: Sequence[Path] = (),
) -> SlicerProfile | None:
    """Das Filamentprofil zu einem Material — die Vorgabe, nicht das Urteil.

    Von einem Material gibt es beim Hersteller mehrere Ausführungen: PETG
    liegt als Standard, HF, PRO, Translucent und CF im Bestand, und sie fahren
    verschieden — Translucent will 255 °C, PRO 240 °C bei halbem Volumenstrom.
    Gewählt wird deshalb der schlichteste Name, also die Grundausführung; wer
    eine besondere Spule hat, stellt sie ein. Eine Vorgabe zu raten, die
    genauer aussieht als sie ist, wäre schlechter als die einfache.

    **Ohne Drucker gibt es keine Vorgabe**, und das ist keine Bequemlichkeit.
    Ein Filamentprofil gilt für eine Maschine; ohne sie gäbe es nichts, wozu
    die Antwort passen könnte. Vor allem aber fällt damit die Einschränkung
    weg, auf der die Rechnung unten beruht: ``type_of`` löst je Profil eine
    Erbkette aus Dateien auf, und der Aufruf lief über **5962** Filamente
    statt über die 42, die zu einem Drucker gehören. Gemessen am Bestand des
    ElegooSlicer: 0,97 Sekunden mit Drucker, über zehn Minuten ohne — und
    weil der Aufruf im Qt-Hauptthread steht, stand mit ihm die ganze
    Anwendung. Ausgelöst hat das kein Sonderfall, sondern die Vorgabe: zum
    „Allgemeinen FDM-Drucker 220 mm" findet kein Slicer ein Profil.
    """
    if machine is None:
        return None
    wanted = material_type.casefold()
    # Der Typ steht wie die Verträglichkeit meist nicht in der obersten Datei,
    # sondern eine Ebene höher: von 42 verträglichen Filamentprofilen nennen
    # ihn sieben selbst. Aufgelöst wird deshalb über die Kette — und erst
    # nachdem die Verträglichkeit die Liste von tausenden auf Dutzende
    # gebracht hat, sonst kostete es Sekunden statt Zehntel.
    # **Ein Index für den ganzen Durchgang.** Ohne ihn liest jedes Profil die
    # Ablage neu — bei 16 795 Dateien und Dutzenden Filamenten stand der
    # Hauptthread 49 Sekunden (Befund Robert, 09.09.2026).
    indexes: ProfileIndexes = {}
    fitting = [
        entry
        for entry in filaments(profiles, machine, indexes=indexes)
        if type_of(entry, roots, indexes=indexes).casefold() == wanted
    ]
    if not fitting:
        return None
    return min(fitting, key=lambda entry: (not entry.from_user, len(entry.name), entry.name))


def type_of(
    profile: SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> str:
    """Welches Material dieses Filamentprofil meint — eigene Angabe oder geerbte.

    ``indexes`` gehört dem Aufrufer, der über mehrere Profile geht: Der
    Namensindex kostet einen Durchlauf durch die ganze Ablage, und ohne ihn
    zahlt jedes Profil ihn erneut (:data:`ProfileIndexes`).
    """
    if profile.filament_type:
        return profile.filament_type
    return _first_string(resolve_profile(profile, roots, indexes=indexes).get("filament_type"))


def match(
    profiles: list[SlicerProfile], printer: PrinterProfile
) -> tuple[SlicerProfile | None, SlicerProfile | None]:
    """Das Paar, das zu diesem Drucker gehört — Maschine und Prozess.

    Der Modellname trägt die Zuordnung, die Düse entscheidet zwischen den
    Varianten desselben Geräts. Trifft nichts, bleibt es leer: eine falsche
    Vorauswahl wäre schlimmer als keine, weil sie wie eine Entscheidung
    aussieht.
    """
    candidates = [
        entry
        for entry in machines(profiles)
        if _names_the_printer(entry.printer_model, printer.title)
        or _names_the_printer(entry.name, printer.title)
    ]
    if not candidates:
        return None, None

    exact = [entry for entry in candidates if abs(entry.nozzle - printer.nozzle_diameter) < 1e-6]
    chosen = min(
        exact or candidates,
        key=lambda entry: (not entry.from_user, abs(entry.nozzle - printer.nozzle_diameter)),
    )

    fitting = processes(profiles, chosen)
    named = [entry for entry in fitting if entry.name == chosen.default_process]
    return chosen, (named[0] if named else (fitting[0] if fitting else None))


#: Was ein Filamentprofil des Slicers über das Material sagt, in Solidons
#: Worten. Die Gegenrichtung zu :mod:`slicer_keys`, und mit Absicht kurz: hier
#: stehen nur die Werte, die *dem Filament* gehören und nicht der Maschine oder
#: dem Vorgehen.
#:
#: Warum es das braucht: Solidon kennt „PETG" und bringt dafür einen
#: Startbestand mit — 10 mm³/s, Bett 80. Elegoo kennt sieben PETG, und das
#: PRO fährt 5 mm³/s bei Bett 70. Der Unterschied ist kein Feinschliff: mit dem
#: falschen Volumenstrom rechnet die Beratung an der Grenze vorbei, die das
#: Material wirklich hat.
FILAMENT_READBACK: Final[tuple[tuple[str, str, type], ...]] = (
    ("temperature.nozzle", "nozzle_temperature", int),
    ("temperature.nozzle_first_layer", "nozzle_temperature_initial_layer", int),
    ("temperature.bed", "hot_plate_temp", int),
    ("temperature.bed_first_layer", "hot_plate_temp_initial_layer", int),
    ("temperature.chamber", "chamber_temperature", int),
    ("cooling.fan_speed", "fan_max_speed", float),
    ("cooling.bridge_fan_speed", "overhang_fan_speed", float),
    ("cooling.disable_first_layers", "close_fan_the_first_x_layers", int),
    ("cooling.minimum_layer_time", "slow_down_layer_time", float),
    ("filament.density", "filament_density", float),
    ("filament.flow_ratio", "filament_flow_ratio", float),
    ("filament.max_flow", "filament_max_volumetric_speed", float),
    ("filament.diameter", "filament_diameter", float),
    ("retraction.length", "filament_retraction_length", float),
    ("retraction.speed", "filament_retraction_speed", float),
    ("retraction.z_hop", "filament_z_hop", float),
)

#: Anteile stehen im Profil als ganze Prozent, in Solidon als Bruch.
_AS_FRACTION: Final = frozenset({"cooling.fan_speed", "cooling.bridge_fan_speed"})


#: Was ein Orca-Maschinenprofil über die Maschine sagt und Solidon nicht
#: ableiten kann.
#:
#: **Die Auswahl ist der ganze Punkt, und sie ist eng.** Bauraum, Düse und
#: Bauart stehen längst im eigenen Druckerprofil und werden gerechnet, nicht
#: übernommen — was hier steht, ist das, was nur der Hersteller weiß: wie die
#: Maschine anfährt, wie schnell sie beschleunigen darf, wie sie zurückzieht.
#: Ein Wert, den Solidon selbst kennt, gehört nicht in diese Liste; sonst
#: entstünden zwei Wahrheiten über dieselbe Zahl.
#:
#: **Übernommen wird roh.** Anders als bei den Filamenten (:data:`FILAMENT_READBACK`)
#: gibt es keine Solidon-Felder dafür — es *soll* keine geben: Niemand stellt
#: die Maximalbeschleunigung seiner Y-Achse in einem Konstruktionsprogramm
#: ein. Die Werte reisen unter ihrem Orca-Namen weiter und werden beim
#: Schreiben unverändert eingesetzt.
MACHINE_READBACK: Final[tuple[str, ...]] = (
    # Wie die Maschine anfängt und aufhört. Ohne das fährt kein Drucker los —
    # Homing, Bettausgleich, Düse reinigen, am Ende Kühlen und Parken.
    "machine_start_gcode",
    "machine_end_gcode",
    "before_layer_change_gcode",
    "layer_change_gcode",
    "change_filament_gcode",
    "machine_pause_gcode",
    "gcode_flavor",
    # Was die Mechanik aushält. Ein Wert zu hoch heißt übersprungene Schritte,
    # ein Wert zu niedrig heißt eine Stunde mehr Druckzeit.
    "machine_max_acceleration_x",
    "machine_max_acceleration_y",
    "machine_max_acceleration_z",
    "machine_max_acceleration_e",
    "machine_max_acceleration_extruding",
    "machine_max_acceleration_retracting",
    "machine_max_acceleration_travel",
    "machine_max_speed_x",
    "machine_max_speed_y",
    "machine_max_speed_z",
    "machine_max_speed_e",
    "machine_max_jerk_x",
    "machine_max_jerk_y",
    "machine_max_jerk_z",
    "machine_max_jerk_e",
    "machine_min_extruding_rate",
    "machine_min_travel_rate",
    # Wie der Extruder zurückzieht. Hängt an der Bauart des Hotends, nicht am
    # Filament — deshalb hier und nicht bei den Filamentwerten.
    "retraction_length",
    "retraction_speed",
    "deretraction_speed",
    "retract_lift_below",
    "retraction_minimum_travel",
    "retract_before_wipe",
    "wipe_distance",
    "z_hop",
    "z_hop_types",
    # Was der Bauraum an Bewegung erlaubt, über den Quader hinaus.
    "extruder_clearance_radius",
    "extruder_clearance_height_to_rod",
    "extruder_clearance_height_to_lid",
    "printer_technology",
    "printer_structure",
    "auxiliary_fan",
    "support_air_filtration",
)


def vendor_of(entry: SlicerProfile) -> str:
    """Der Hersteller eines Profils — der Ordner über ``filament`` im Bestand.

    Ein :class:`SlicerProfile` nennt ihn nicht, und in der Datei steht er auch
    nicht. Die Orca-Familie legt ihre Profile aber nach Hersteller ab
    (``profiles/<Hersteller>/filament/…``), und dieser Ordner ist die einzige
    Angabe, die **jedes** mitgelieferte Profil trägt: Gemessen an einem
    ElegooSlicer-Bestand sind es 5962 Filamentprofile aus 48 Herstellern,
    keines ohne (BBL 1997, Qidi 1113, Elegoo 221).

    Eigene Profile des Nutzers liegen unter seinem Konto statt unter einem
    Hersteller; dort stünde der Kontoname da, und das wäre eine erfundene
    Auskunft. Sie bekommen deshalb keinen — ``from_user`` sagt ohnehin mehr
    über sie als jeder Name.
    """
    if entry.from_user:
        return ""
    parts = list(entry.path.parts)
    if "filament" not in parts:
        return ""
    position = parts.index("filament")
    return parts[position - 1] if position else ""


def material_of(entry: SlicerProfile, known: Sequence[str]) -> str:
    """Die Materialart eines Profils, ohne die Erbkette aufzulösen.

    **Warum nicht aufgelöst wird.** ``filament_type`` steht in der Datei
    selbst nur bei 888 von 5962 Profilen; die übrigen erben es. Die Kette
    aufzulösen kostet gemessen 4 Sekunden für 221 Profile, also gut zwei
    Minuten für den ganzen Bestand — für einen Filter, der beim Tippen
    mitlaufen soll, ist das keine Antwort.

    **Woran es stattdessen erkannt wird.** Am Namen, und zwar nur an einer
    ganzen Wortmarke: ``Elegoo PLA @EC`` ist PLA, ``Anker Generic PLA-CF``
    ist es nicht — ein Kohlefaser-Filament fährt anders, und es unter PLA zu
    zeigen wäre schlimmer, als es dem Suchfeld zu überlassen. Damit sind
    4028 der 5962 Profile einer der Solidon-Materialarten zugeordnet; der
    Rest sind Materialien, die Solidon nicht führt (PA-CF, PC, PVA), und die
    bleiben über „alle Materialien" und die Suche erreichbar.

    ``known`` sind die Schreibweisen, nach denen gefragt wird — der Aufrufer
    kennt sie, dieses Modul soll sie nicht zum zweiten Mal wissen. Die
    längste passt zuerst, sonst gewänne ``PETG`` gegen ``PETG-CF``.
    """
    if entry.filament_type:
        return entry.filament_type
    upper = entry.name.upper()
    for candidate in sorted(known, key=len, reverse=True):
        if not candidate:
            continue
        marker = re.escape(candidate.upper())
        if re.search(rf"(?<![A-Z0-9-]){marker}(?![A-Z0-9-])", upper):
            return candidate
    return ""


def machine_values(path: Path, roots: Sequence[Path] = ()) -> dict[str, Any]:
    """Was dieses Maschinenprofil über die Maschine sagt (§29).

    **Der Gegenpart zu** :func:`filament_values`, und aus demselben Grund
    gebaut: Ein Hersteller staffelt seine Angaben über mehrere Ebenen, und wer
    nur die oberste Datei liest, sieht ein Dutzend Werte und hält den Rest für
    nicht gesetzt. Gemessen am Elegoo Centauri: 38 Schlüssel in der eigenen
    Datei, **83 in der aufgelösten Kette**.

    Zurück kommen die Schlüssel unter ihrem **Orca-Namen**, nicht übersetzt —
    die Begründung steht bei :data:`MACHINE_READBACK`.

    Was das Profil nicht nennt, fehlt auch hier. Ein Anfahrcode, den niemand
    gesetzt hat, ist keine Angabe des Herstellers, und ihn zu erfinden wäre
    schlimmer als ihn wegzulassen — bei G-Code sogar gefährlich: Ein geratener
    Homing-Befehl fährt die Düse ins Bett.

    **Sie hat keinen Aufrufer, und das ist kein Loch in der Übergabe.**
    :data:`MACHINE_READBACK` sagt, die Werte reisten „unter ihrem Orca-Namen
    weiter und werden beim Schreiben unverändert eingesetzt" — eingesetzt
    werden sie, nur nicht über diesen Weg: :func:`handover._orca_machine`
    schreibt das Maschinenprofil mit :func:`resolve_values` **vollständig**
    aus, und die enge Auswahl hier ist eine Teilmenge davon. Cura und
    PrusaSlicer bekommen umgekehrt gar keine Maschinenseite aus fremdem Profil
    (siehe :func:`handover.machine_for`).

    Was sie kann und niemand fragt: **eine Maschine beschreiben, ohne sie zu
    übernehmen** — die achtzig Werte hinter einem Profilnamen zeigen, statt ihn
    nur zu nennen. Wer das baut, hat sie schon.
    """
    resolved = resolve_values(path, roots)
    return {key: resolved[key] for key in MACHINE_READBACK if key in resolved}


_PRUSA_FILAMENT_READBACK: Final[tuple[tuple[str, str, type], ...]] = (
    ("temperature.nozzle", "temperature", int),
    ("temperature.nozzle_first_layer", "first_layer_temperature", int),
    ("temperature.bed", "bed_temperature", int),
    ("temperature.bed_first_layer", "first_layer_bed_temperature", int),
    ("temperature.chamber", "chamber_temperature", int),
    ("cooling.fan_speed", "max_fan_speed", float),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", float),
    ("cooling.disable_first_layers", "disable_fan_first_layers", int),
    ("cooling.minimum_layer_time", "slowdown_below_layer_time", float),
    ("filament.density", "filament_density", float),
    ("filament.diameter", "filament_diameter", float),
    ("filament.flow_ratio", "extrusion_multiplier", float),
    ("filament.max_flow", "filament_max_volumetric_speed", float),
    ("retraction.length", "filament_retract_length", float),
    ("retraction.speed", "filament_retract_speed", float),
    ("retraction.z_hop", "filament_retract_lift", float),
)

_CURA_FILAMENT_READBACK: Final[tuple[tuple[str, str, type], ...]] = (
    ("temperature.nozzle", "material_print_temperature", int),
    ("temperature.nozzle_first_layer", "material_print_temperature_layer_0", int),
    ("temperature.bed", "material_bed_temperature", int),
    ("temperature.bed_first_layer", "material_bed_temperature_layer_0", int),
    ("temperature.chamber", "build_volume_temperature", int),
    ("cooling.fan_speed", "cool_fan_speed", float),
    ("filament.density", "material_density", float),
    ("filament.diameter", "material_diameter", float),
    ("retraction.length", "retraction_amount", float),
    ("retraction.speed", "retraction_speed", float),
)


def filament_values(
    path: Path | SlicerProfile, roots: Sequence[Path] = ()
) -> dict[str, float | int]:
    """Was dieses Filamentprofil über sein Material sagt (§29).

    Die Erbkette wird aufgelöst — ein Profil bei Elegoo setzt selbst drei Werte
    und erbt fünfzig. Zurück kommen Solidon-Pfade, wie sie
    :func:`app.core.knowledge.print_settings.with_path` versteht.

    Was das Profil nicht nennt, fehlt auch hier: ein Wert, den niemand gesetzt
    hat, ist keine Angabe des Herstellers, und ihn zu erfinden wäre schlimmer
    als ihn wegzulassen.
    """
    resolved = (
        resolve_profile(path, roots)
        if isinstance(path, SlicerProfile)
        else resolve_values(path, roots)
    )
    source = path.path if isinstance(path, SlicerProfile) else path
    readback = FILAMENT_READBACK
    if source.suffix == ".ini":
        readback = _PRUSA_FILAMENT_READBACK
    elif source.name.endswith((".xml.fdm_material", ".inst.cfg")):
        readback = _CURA_FILAMENT_READBACK
    values: dict[str, float | int] = {}
    for solidon, native, kind in readback:
        raw = resolved.get(native)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw is None or raw == "" or raw == "nil":
            continue
        text = str(raw).strip().rstrip("%")
        if source.suffix == ".ini":
            text = text.split(",")[0]
        try:
            number = float(text)
        except ValueError:
            continue
        if not math.isfinite(number):
            raise ValidationError(
                field=solidon,
                detail=_("Dieser Profilwert muss eine endliche Zahl sein."),
                values={"file": path.name, "value": text},
            )
        if solidon == "filament.max_flow" and number <= 0:
            continue
        if solidon in _AS_FRACTION:
            number /= 100.0
        values[solidon] = kind(number)
    return values
