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
import hashlib
import json
import math
import os
import re
import sys
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import unquote_plus
from xml.etree import ElementTree as ET

from app.core import build_area, discover
from app.core.errors import CHECK_SLICER_PROFILE, ExternalToolError, ValidationError
from app.core.export import cura_linux, prusa_conditions
from app.core.export.slicer_keys import (
    CURA_JERK_LINKS,
    SlicerFlavour,
    for_the_nozzle,
    has_readable_profiles,
    has_user_profile_tree,
    native_key,
    normalise_chamber,
    normalise_filament_type,
)
from app.core.knowledge import profiles as knowledge_profiles
from app.core.log import get_logger
from app.core.types import CancelToken, PrinterProfile, QualityPreset
from app.core.units import EPS_GEOM, MAX_FACET_SAG, circle_point, inscribed_ratio, is_zero
from app.i18n import _

_log = get_logger(__name__)

ProfileKind = Literal["machine", "process", "filament"]


def _check_cancelled(cancelled: CancelToken | None) -> None:
    """Ein Dateischritt oder Profilabschnitt beginnt nur im noch gültigen Suchauftrag."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()


def _checked_paths(paths: Iterable[Path], cancelled: CancelToken | None) -> Iterator[Path]:
    """Auch das Einsammeln vor einer Sortierung bleibt zwischen Dateitreffern abbrechbar."""
    _check_cancelled(cancelled)
    for path in paths:
        _check_cancelled(cancelled)
        yield path


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

#: Die gelesenen Profildateien eines Durchgangs, Datei → Inhalt (``None`` für
#: Unlesbares). :func:`find_profiles` liest den Bestand einmal für die Auswahl
#: und ein zweites Mal für die Namensindizes und Erbketten; mit diesem Speicher
#: öffnet es jede Datei nur einmal (DRUCK-14, Durchsicht 0.5.1).
ProfileDocuments = dict[Path, dict[str, Any] | None]

#: Der laufende Lesedurchgang (:func:`single_read`) — je Thread, damit die
#: Profilsuche im Arbeiter nicht in den Durchgang des Fensters greift.
_SINGLE_READ: Final = threading.local()


@contextmanager
def single_read() -> Iterator[None]:
    """Ein Durchgang, in dem jede Profildatei einmal gelesen und jeder Ordner
    einmal indiziert wird — danach verfällt beides.

    Kommen im Druckdialog die Profile an, fragt er nach Prozessen, Filamenten,
    Modell und Grundlage, und jede Frage baute ihre Namensindizes und Erbketten
    neu. Gemessen an Roberts ElegooSlicer (08.10.2026): 14 327 Lesungen von
    1431 Dateien und 23 Ordnerindizes je Antwort, „fdm_filament_common" allein
    1136-mal, zusammen 2,5 s im Qt-Hauptthread. Länger als der Durchgang hält
    der Speicher nicht, denn der Kunde legt im Slicer Profile an und benennt sie
    um (:data:`ProfileIndexes`). Ausdrücklich übergebene Indizes und Dokumente
    gehen vor; verschachtelt gilt der äußere Durchgang.
    """
    if getattr(_SINGLE_READ, "documents", None) is not None:
        yield
        return
    _SINGLE_READ.documents = {}
    _SINGLE_READ.indexes = {}
    _SINGLE_READ.listings = {}
    try:
        yield
    finally:
        _SINGLE_READ.documents = None
        _SINGLE_READ.indexes = None
        _SINGLE_READ.listings = None


def _json_files(root: Path) -> list[Path]:
    """Die JSON-Dateien unter ``root``, sortiert — im Lesedurchgang einmal je
    Wurzel. Die Vorwahl ohne gemerkte Maschine liest erst die Maschinen, dann
    Prozesse und Filamente (``handover.standard_choice``); der zweite
    Durchlauf über ElegooSlicers zwölftausend Dateien kostete noch einmal
    0,36 s CPU-Zeit."""
    shared: dict[Path, list[Path]] | None = getattr(_SINGLE_READ, "listings", None)
    if shared is not None and root in shared:
        return shared[root]
    found = sorted(root.rglob("*.json"))
    if shared is not None:
        shared[root] = found
    return found


def _pass_documents(documents: ProfileDocuments | None) -> ProfileDocuments | None:
    """Die übergebenen Dokumente, sonst die des laufenden Durchgangs."""
    if documents is not None:
        return documents
    shared: ProfileDocuments | None = getattr(_SINGLE_READ, "documents", None)
    return shared


def _pass_indexes(indexes: ProfileIndexes | None) -> ProfileIndexes:
    """Die übergebenen Indizes, sonst die des laufenden Durchgangs, sonst neue."""
    if indexes is not None:
        return indexes
    shared: ProfileIndexes | None = getattr(_SINGLE_READ, "indexes", None)
    return shared if shared is not None else {}


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
    default_filament: str = ""
    """Nur bei Maschinenprofilen: das Filament, das der Hersteller für diese
    Maschine vorwählt (``default_filament_profile``) — bei Bambu „Bambu PLA
    Basic @BBL A1", bei Prusa „Prusament PLA @MK4S HF0.4"."""
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
    condition: str = ""
    """Nur bei Prusa-Prozessen und -Filamenten: ``compatible_printers_condition``,
    die Verträglichkeit als Bedingung über die Werte des Druckers
    (:mod:`app.core.export.prusa_conditions`)."""
    variables: tuple[tuple[str, str], ...] = ()
    """Nur bei Prusa-Maschinen: die Werte, die solche Bedingungen lesen
    (:data:`PRUSA_CONDITION_KEYS`), wie sie in der INI stehen."""
    default_materials: tuple[str, ...] = ()
    """Nur bei Prusa-Maschinen: die Filamente, die das Druckermodell im Bündel
    vorschlägt (``default_materials``), in ihrer Reihenfolge. Der MK4S erbt
    als ``default_filament_profile`` das PLA des MK4, das zu ihm nicht passt;
    sein Modell nennt „Prusament PLA @MK4S HF0.4"."""
    vendor: str = ""
    """Nur bei Prusa: der Hersteller, dem das Profil gehört — das Bündel, aus
    dem es stammt (``PrusaResearch``, ``Sovol``), bei einem eigenen Profil das
    seines ersten Vorfahren mit Hersteller. Leer bei Vorlagen
    (``templates_profile = 1``) und bei eigenen Profilen ohne Herstellerbasis
    (:meth:`_PrusaStore.vendor_of`)."""
    printer_id: str = ""
    """Solidons stabile Kennung einer Cura-Maschine, unabhängig vom Anzeigenamen."""
    cura_instance: Path | None = None
    """Der konfigurierte Maschinenstapel; seine Definition bleibt unter ``path``."""

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

    **Ein Flatpak trägt seinen Bestand nicht über dem Starter**, sondern in
    seinem eigenen ``/app`` (:func:`discover.flatpak_files`): nach FHS gebaut —
    Orca, PrusaSlicer und Bambu Studio auf Flathub — unter
    ``share/<Programm>/profiles``, Cura als ausgepacktes AppImage unter
    ``cura/share/cura``. Ein Slicer aus dem Paketverwalter der Distribution legt
    genauso nach FHS ab (``/usr/share/PrusaSlicer/profiles``).

    **Eine Cura als AppImage trägt ihn im Abbild**, das nur eingehängt lesbar
    ist; gelesen wird eine Kopie im Nutzer-Cache (:func:`cura_linux.appimage_resources`).
    Im Fensterfaden (:func:`cura_linux.never_wait_in`) heißt ``None`` dort „noch
    nicht kopiert“, nicht „kein Bestand“.
    """
    mark = discover.program_mark(executable.name)
    if mark == "cura" and cura_linux.is_appimage(executable):
        return cura_linux.appimage_resources(executable)
    app = discover.flatpak_app(executable)
    if mark == "cura" and app:
        # Curas AppDir bestimmt eine Stelle, für Bestand und Lader zugleich.
        appdir = cura_linux.flatpak_appdir(app)
        return appdir[0] / "share" / "cura" if appdir is not None else None
    files = discover.flatpak_files(app) if app else None
    if files is not None:
        try:
            inner = sorted(entry for entry in files.iterdir() if entry.is_dir())
        except OSError:
            inner = []
        for folder in (files, *inner):
            for candidate in _bundled(folder, mark):
                if candidate.is_dir():
                    return candidate
    for folder in (executable.parent, *executable.parents):
        for candidate in _bundled(folder, mark):
            # Gefragt wird über ``discover``: Läuft Solidon in einem Flatpak,
            # ist ``executable`` ein Host-Pfad, und ``is_dir()`` darauf sagt
            # zuverlässig nein. Für Cura hängt daran ``-j <definition>``, und
            # ohne die startet CuraEngine gar nicht.
            if discover.is_dir_on_host(candidate):
                return candidate
    return None


def _bundled(folder: Path, mark: str) -> Iterator[Path]:
    """Wo unter ``folder`` ein mitgelieferter Bestand liegen kann.

    ``share/<Programm>`` wird gelesen statt erraten, denn der Ordner trägt die
    Schreibweise des Herstellers (``OrcaSlicer``, ``BambuStudio``), das Programm
    die des Startnamens (``orca-slicer``). Das Debian-Paket von Anycubic Slicer
    Next legt eine Ebene tiefer ab: ``share/AnycubicSlicerNext/resources/profiles``.

    **``share/cura`` gehört Cura.** Aus dem Paketverwalter liegt es neben
    ``share/PrusaSlicer``. Angeboten wurde es jedem Programm, und PrusaSlicer
    und Orca bekamen Curas Ordner als Herstellerbestand — ohne einen ihrer
    Drucker.

    **Ein Mac-Bündel schreibt ``Contents/Resources`` groß.** Auf dem üblichen
    APFS trifft ``resources`` trotzdem, auf einem Volume mit Unterscheidung der
    Schreibweise nicht; gefragt wird deshalb zuerst die Schreibweise des Bündels.
    """
    if folder.name == "Contents" and folder.parent.suffix.lower() == ".app":
        yield folder / "Resources" / "profiles"
    yield folder / "resources" / "profiles"
    if mark == "cura":
        yield folder / "share" / "cura"
    try:
        shared = sorted((folder / "share").iterdir())
    except OSError:
        return
    for entry in shared:
        if discover.plain_name(entry.name) == mark:
            yield entry / "profiles"
            yield entry / "resources" / "profiles"


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


def config_base(executable: Path) -> str:
    """Wo **dieser** Slicer seine Konfiguration ablegt.

    Ein Slicer als Flatpak schreibt nicht nach ``~/.config``: Flatpak setzt
    sein ``XDG_CONFIG_HOME`` auf ``~/.var/app/<Kennung>/config``. Ein
    ``~/.config/OrcaSlicer`` daneben stammt dann von einer anderen Installation
    und wird nicht gelesen — sonst hieße der Drucker, den Solidon als zuletzt
    eingestellt meldet, wie einer, den der Kunde dort längst nicht mehr hat.
    """
    app = discover.flatpak_app(executable)
    if not app:
        return config_home(sys.platform)
    data = discover.flatpak_data(app)
    config = data / "config" if data is not None else None
    return str(config) if config is not None and config.is_dir() else ""


def user_roots(flavour: SlicerFlavour, executable: Path) -> list[Path]:
    """Wo die selbst angelegten Profile liegen.

    Die Orca-Familie legt sie unter ``<Konfiguration>/<Programm>/user/<Konto>/``
    ab. Der Programmname ist der der ausführbaren Datei, ohne Bindestriche —
    ``elegoo-slicer.exe`` schreibt nach ``ElegooSlicer``.
    """
    base = config_base(executable)
    if not base:
        return []
    if flavour == "cura":
        return _cura_user_roots(executable, Path(base))
    if flavour == "prusa":
        return _program_folders(Path(base), discover.program_mark(executable.name))
    if not has_user_profile_tree(flavour):
        return []

    found: list[Path] = []
    for folder in _program_folders(Path(base), discover.program_mark(executable.name)):
        user = folder / "user"
        if user.is_dir():
            found.extend(entry for entry in user.iterdir() if entry.is_dir())
    return found


def _program_folders(base: Path, mark: str) -> list[Path]:
    """Die Datenordner des Programms ``mark`` unter ``base``.

    Gewöhnlich ``<base>/<Programm>``, verglichen über die Programmmarke, nicht
    den ganzen Dateistamm: ``OrcaSlicer_Linux_V2.1.1`` legt seine Profile unter
    ``OrcaSlicer`` ab (Gesamtreview 05.09.2026, CORE-16).

    **Creality Print 7 legt unter seinem Anwendungsschlüssel ab**
    (``SLIC3R_APP_KEY "Creality"`` in seiner ``version.inc``) und darunter je
    Version: ``Creality/Creality Print/7.3`` mit ``Creality.conf``. Unter der
    Programmmarke gesucht, fand Solidon dort auf keiner Plattform die eigenen
    Drucker und den zuletzt gewählten. Es gilt die neueste Version.
    """
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return []
    found = [
        entry for entry in entries if entry.is_dir() and discover.plain_name(entry.name) == mark
    ]
    if mark == "crealityprint":
        try:
            versions = [
                entry
                for entry in (base / "Creality" / "Creality Print").iterdir()
                if entry.is_dir() and re.fullmatch(r"\d+(?:\.\d+)*", entry.name)
            ]
        except OSError:
            versions = []
        if versions:
            found.append(
                max(versions, key=lambda entry: tuple(int(part) for part in entry.name.split(".")))
            )
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
    if flavour == "cura":
        for root in user_roots(flavour, executable):
            active = _cura_active_id(root)
            for path in sorted((root / "machine_instances").glob("*.global.cfg")):
                parsed = _read_ini(path)
                if parsed is not None and parsed.has_section("general"):
                    general = parsed["general"]
                    if active and general.get("id", "").strip() == active:
                        return f"cura-instance:{active}"
        return ""
    if not has_user_profile_tree(flavour):
        return ""
    for root in user_roots(flavour, executable):
        # ``user/<Konto>`` — die Konfiguration liegt eine Ebene darüber und
        # heißt wie ihr Ordner, bei Creality Print wie der Anwendungsschlüssel
        # (``7.3/Creality.conf``, :func:`_program_folders`).
        folder = root.parent.parent
        config = next(
            (
                candidate
                for candidate in (folder / f"{folder.name}.conf", *sorted(folder.glob("*.conf")))
                if candidate.is_file()
            ),
            None,
        )
        if config is None:
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
    base = config_base(executable)
    if not base:
        return None
    for folder in _program_folders(Path(base), discover.program_mark(executable.name)):
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
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as problem:
        _log.debug("skipping Prusa file %s: %s", path.name, problem)
        return None
    # Native Prusa-Werte verwenden „=“. Mit dem ebenfalls erlaubten „:“
    # würde ein kaputter Abschnittskopf wie „[print:Name“ zu einem Wert.
    parsed = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
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


def _prusa_configured(
    executable: Path, cancelled: CancelToken | None = None
) -> tuple[SlicerFilament, ...]:
    """Die eingelegten Spulen von PrusaSlicer.

    **Der Name ist die sichere Auskunft, alles andere kommt nur, wo es
    dasteht.** Ein Herstellerpreset wohnt in einem Bündel mit Zehntausenden
    Abschnitten und einer Erbkette; ein selbst angelegtes liegt als eigene
    Datei unter ``filament/``, und die trägt Art und Farbe unmittelbar. Was
    sich nicht ohne Raten sagen lässt, bleibt leer — eine erfundene
    Materialart wäre schlechter als keine (Regel 21).
    """
    _check_cancelled(cancelled)
    presets = _prusa_presets(executable)
    if not presets:
        return ()
    profiles = {
        entry.name: entry
        for entry in _prusa_profiles(executable, frozenset(("filament",)), cancelled)
    }
    roots = profile_roots("prusa", executable)
    keys = ["filament", *(f"filament_{index}" for index in range(1, _PRUSA_EXTRUDERS))]
    found: list[SlicerFilament] = []
    for key in keys:
        _check_cancelled(cancelled)
        name = str(presets.get(key, "")).strip()
        if not name:
            continue
        entry = profiles.get(name)
        values = resolve_profile(entry, roots, cancelled=cancelled) if entry is not None else {}
        colour = str(values.get("filament_colour", "")).strip()
        found.append(
            SlicerFilament(
                profile=name,
                colour=colour if _COLOUR_LOOKS_RIGHT.match(colour) else "",
                material_type=str(values.get("filament_type", "")).strip(),
            )
        )
    _check_cancelled(cancelled)
    return tuple(found)


#: Der Farbvertrag der Anzeige: ``#RRGGBB``. Ein Profil darf etwas anderes
#: hineinschreiben; dann gilt es als keine Angabe.
_COLOUR_LOOKS_RIGHT: Final = re.compile(r"^#[0-9a-fA-F]{6}$")


def configured_filaments(
    flavour: SlicerFlavour, executable: Path, *, cancelled: CancelToken | None = None
) -> tuple[SlicerFilament, ...]:
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

    **Und Cura in seinen Stapeln** (Durchsicht 0.5.0): Die aktive Maschine
    steht in ``cura.cfg``, jedes Extruderfach ist ein ``*.extruder.cfg`` mit
    dem Material an seiner festen Stelle (:func:`_cura_configured`). Bis
    dahin blieb es für Cura bei ``()``.
    """
    _check_cancelled(cancelled)
    if flavour == "prusa":
        return _prusa_configured(executable, cancelled)
    if flavour == "cura":
        return _cura_configured(executable, cancelled)
    if not has_user_profile_tree(flavour):
        return ()
    roots = profile_roots(flavour, executable)
    seen_configs: set[Path] = set()
    result: list[SlicerFilament] = []
    seen_filaments: set[tuple[str, str]] = set()
    for root in user_roots(flavour, executable):
        _check_cancelled(cancelled)
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
            _check_cancelled(cancelled)
            path = _named_profile(executable, flavour, name, "filament", cancelled=cancelled)
            values = resolve_values(path, roots, cancelled=cancelled) if path is not None else {}
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
    _check_cancelled(cancelled)
    return tuple(result)


#: An welcher Stelle eines Cura-Stapels das Material steht
#: (``cura/Settings/CuraContainerStack.py``, ``_ContainerIndexes.Material``).
_CURA_MATERIAL_INDEX: Final = "4"

#: An welcher Stelle derselbe Stapel die Düsenvariante führt
#: (``_ContainerIndexes.Variant``).
_CURA_VARIANT_INDEX: Final = "5"

#: An welcher Stelle der Maschinenstapel hält, was der Nutzer in den
#: Maschineneinstellungen ändert (``_ContainerIndexes.DefinitionChanges``).
_CURA_DEFINITION_CHANGES_INDEX: Final = "6"

#: So heißen leere Stellen eines Stapels — ein Fach ohne Spule, eine Maschine
#: ohne Düsenvarianten.
_CURA_EMPTY: Final = frozenset({"", "empty_material", "empty_variant"})


def _cura_active_id(root: Path) -> str:
    """Die Kennung der Maschine, die in diesem Cura-Konfigurationsordner aktiv ist.

    ``cura.cfg`` nennt sie unter ``[cura] active_machine``; leer heißt: keine.
    """
    preferences = _read_ini(root / "cura.cfg") if (root / "cura.cfg").is_file() else None
    if preferences is None or not preferences.has_section("cura"):
        return ""
    return preferences["cura"].get("active_machine", "").strip()


def _cura_trains(
    root: Path, machine: str, cancelled: CancelToken | None = None
) -> list[tuple[int, dict[str, str]]]:
    """Die Extruderstapel einer Maschine: Fach und ``[containers]``, nach Fach geordnet.

    Jedes Fach ist ein ``extruders/*.extruder.cfg`` mit ``machine`` und
    ``position`` in ``[metadata]``.
    """
    trains: list[tuple[int, dict[str, str]]] = []
    for stack in sorted((root / "extruders").glob("*.extruder.cfg")):
        _check_cancelled(cancelled)
        parsed = _read_ini(stack)
        if parsed is None or not parsed.has_section("metadata"):
            continue
        metadata = parsed["metadata"]
        if metadata.get("machine", "").strip() != machine:
            continue
        try:
            position = int(metadata.get("position", "0"))
        except ValueError:
            continue
        containers = parsed["containers"] if parsed.has_section("containers") else {}
        trains.append((position, {key: str(value).strip() for key, value in containers.items()}))
    return sorted(trains, key=lambda train: train[0])


def _cura_material_files(*folders: Path) -> dict[str, Path]:
    """Die Materialdateien dieser Ordner nach Kennung; ein späterer Ordner geht vor."""
    files: dict[str, Path] = {}
    for folder in folders:
        for candidate in sorted(folder.rglob("*.xml.fdm_material")) if folder.is_dir() else ():
            files[candidate.name.removesuffix(".xml.fdm_material")] = candidate
    return files


@dataclass(frozen=True, slots=True)
class CuraActiveMachine:
    """Der Drucker, der in Cura eingerichtet und zuletzt aktiv war.

    ``name`` ist der Anzeigename aus Cura, ``definition`` seine
    Druckerdefinition, ``variant`` der Name der Düse im ersten Fach
    („0.4mm Nozzle"), ``material_type`` die Art der Spule darin („PLA"). Leer
    heißt: Die Maschine hat keine Düsenvarianten, oder das Fach ist leer.
    ``bed`` ist Breite und Tiefe ihres Betts — ``None``, wenn die Erbkette sie
    nicht als Zahl führt.
    """

    name: str
    definition: Path
    variant: str = ""
    material_type: str = ""
    bed: tuple[float, float] | None = None


def cura_active_machine(executable: Path) -> CuraActiveMachine | None:
    """Welcher Drucker in Cura eingerichtet und zuletzt aktiv war — oder keiner.

    ``cura.cfg`` nennt ihn mit seiner Kennung; sein Stapel in
    ``machine_instances`` führt die Druckerdefinition an letzter Stelle, der
    Stapel seines ersten Fachs die Düse (Stelle 5) und die Spule (Stelle 4).
    Auf diese Maschine setzt Cura ein importiertes Profil um, und nur ihre
    Qualitätsstufen nimmt es an (:func:`cura_quality_types`).
    """
    base = config_base(executable)
    installed = install_root(executable)
    if not base or installed is None:
        return None
    resources = cura_resources(installed)
    for folder in _cura_user_roots(executable, Path(base)):
        machine = _cura_active_id(folder)
        if not machine:
            continue
        stack = _cura_machine_stack(folder, machine)
        numbered = sorted((key for key in stack if key.isdigit()), key=int)
        if not numbered:
            continue
        identifier = stack[numbered[-1]]
        definition = next(
            (
                candidate
                for candidate in (
                    resources / "definitions" / f"{identifier}.def.json",
                    folder / "definitions" / f"{identifier}.def.json",
                )
                if candidate.is_file()
            ),
            None,
        )
        if definition is None:
            _log.debug("the active Cura machine %s names no definition we find", machine)
            continue
        display_name = machine
        for path in sorted((folder / "machine_instances").glob("*.global.cfg")):
            parsed = _read_ini(path)
            if parsed is None or not parsed.has_section("general"):
                continue
            general = parsed["general"]
            if general.get("id", "").strip() == machine:
                display_name = general.get("name", "").strip() or machine
                break
        trains = _cura_trains(folder, machine)
        first = trains[0][1] if trains else {}
        return CuraActiveMachine(
            name=display_name,
            definition=definition,
            variant=_cura_variant_name(first.get(_CURA_VARIANT_INDEX, ""), resources, folder),
            material_type=_cura_material_type(
                first.get(_CURA_MATERIAL_INDEX, ""), resources, folder
            ),
            bed=_cura_bed(
                folder, stack.get(_CURA_DEFINITION_CHANGES_INDEX, ""), definition, installed
            ),
        )
    return None


def _cura_bed(
    folder: Path, changes: str, definition: Path, installed: Path
) -> tuple[float, float] | None:
    """Breite und Tiefe des Betts: die Maschineneinstellungen vor der Erbkette.

    Curas 3MF-Leser zieht beim Öffnen die halbe Bettgröße der aktiven Maschine
    ab (``ThreeMFReader._read``, Cura 5.13) — genau diese Werte, auch die, die
    der Nutzer selbst eingetragen hat.
    """
    values: dict[str, Any] = {}
    try:
        values.update(_cura_definition_values(definition, (installed,)))
    except ExternalToolError:
        _log.debug("the definition chain of %s does not resolve", definition.name)
    place = folder / "definition_changes"
    for path in sorted(place.glob("*.inst.cfg")) if place.is_dir() else ():
        if unquote_plus(path.name.removesuffix(".inst.cfg")) != changes:
            continue
        parsed = _read_ini(path)
        if parsed is not None and parsed.has_section("values"):
            values.update(parsed["values"])
    try:
        width, depth = float(values["machine_width"]), float(values["machine_depth"])
    except KeyError, TypeError, ValueError:
        return None
    return (width, depth) if width > 0.0 and depth > 0.0 else None


def _cura_machine_stack(folder: Path, machine: str) -> dict[str, str]:
    """``[containers]`` des Maschinenstapels mit dieser Kennung — sonst leer.

    Cura schreibt den Stapel unter einem kodierten Dateinamen
    (``Creality+K1+Max.global.cfg``); verglichen wird deshalb die Kennung in
    ``[general]``, nicht der Name der Datei.
    """
    place = folder / "machine_instances"
    for path in sorted(place.glob("*.global.cfg")) if place.is_dir() else ():
        parsed = _read_ini(path)
        if parsed is None or not parsed.has_section("general"):
            continue
        if parsed["general"].get("id", "").strip() != machine:
            continue
        if not parsed.has_section("containers"):
            return {}
        return {key: str(value).strip() for key, value in parsed["containers"].items()}
    return {}


def _cura_variant_name(variant: str, resources: Path, folder: Path) -> str:
    """Der Name einer Düsenvariante („0.4mm Nozzle") zu ihrer Stapelkennung.

    Die Kennung ist der Dateiname, kodiert, wie Cura ihn schreibt; verglichen
    wird deshalb dekodiert und nicht über ein Suchmuster, in dem eine Klammer
    etwas anderes hieße.
    """
    if variant in _CURA_EMPTY:
        return ""
    for place in (resources / "variants", folder / "variants"):
        for path in sorted(place.rglob("*.inst.cfg")) if place.is_dir() else ():
            if unquote_plus(path.name.removesuffix(".inst.cfg")) != variant:
                continue
            parsed = _read_ini(path)
            if parsed is not None and parsed.has_section("general"):
                return parsed["general"].get("name", "").strip()
    return ""


def _cura_material_type(material: str, resources: Path, folder: Path) -> str:
    """Die Materialart („PLA") zu einer Stapelkennung — leer, wenn das Fach leer ist."""
    if material in _CURA_EMPTY:
        return ""
    files = _cura_material_files(resources / "materials", folder / "materials")
    source = _cura_material_file(material, files)
    entry = _read_cura_material(source) if source is not None else None
    return entry.filament_type if entry is not None else ""


def _cura_configured(
    executable: Path, cancelled: CancelToken | None = None
) -> tuple[SlicerFilament, ...]:
    """Die Materialien der zuletzt aktiven Cura-Maschine, in Fachreihenfolge.

    Cura hält die Belegung nicht in einer Liste, sondern in seinen Stapeln:
    ``cura.cfg`` nennt unter ``[cura] active_machine`` die Maschine, jedes
    Extruderfach ist ein ``extruders/*.extruder.cfg`` mit ``machine`` und
    ``position`` in ``[metadata]``, und das eingelegte Material steht in
    ``[containers]`` an Stelle vier. Seine Farbe und Art stehen in der
    Materialdatei selbst (``*.xml.fdm_material``) — im eigenen Ordner oder im
    mitgelieferten Bestand. Ein Fach ohne Material oder ohne Farbe bleibt weg;
    ein Vorschlag ohne Farbe wäre keiner.
    """
    base = config_base(executable)
    if not base:
        return ()
    for root in _cura_user_roots(executable, Path(base)):
        _check_cancelled(cancelled)
        found = _cura_loaded_materials(root, executable, cancelled)
        if found:
            return found
    return ()


def _cura_loaded_materials(
    root: Path, executable: Path, cancelled: CancelToken | None
) -> tuple[SlicerFilament, ...]:
    """Die Materialien der aktiven Maschine in einem Cura-Konfigurationsordner."""
    machine = _cura_active_id(root)
    if not machine:
        return ()
    trays = [
        (position, material)
        for position, containers in _cura_trains(root, machine, cancelled)
        if (material := containers.get(_CURA_MATERIAL_INDEX, "")) not in _CURA_EMPTY
    ]
    if not trays:
        return ()
    installed = install_root(executable)
    files = _cura_material_files(
        *((cura_resources(installed) / "materials",) if installed is not None else ()),
        root / "materials",
    )
    result: list[SlicerFilament] = []
    for _position, material in sorted(trays):
        _check_cancelled(cancelled)
        source = _cura_material_file(material, files)
        if source is None:
            continue
        entry = _read_cura_material(source)
        colour = str(_cura_material_values(source).get("filament_colour", "")).strip()
        if entry is None or not _is_colour(colour):
            continue
        result.append(
            SlicerFilament(
                profile=entry.name, colour=colour.upper(), material_type=entry.filament_type
            )
        )
    return tuple(result)


def _cura_material_file(material: str, files: Mapping[str, Path]) -> Path | None:
    """Die Materialdatei zu einer Stapelkennung.

    Cura leitet für Maschinen mit eigenen Düsenvarianten Kennungen aus dem
    Dateinamen ab — ``generic_pla_175`` wird dort zu
    ``generic_pla_175_<maschine>_<düse>``. Gesucht wird deshalb erst genau,
    dann der längste Dateiname, der die Kennung bis zu einem ``_`` beginnt.
    """
    if material in files:
        return files[material]
    prefixes = [name for name in files if material.startswith(f"{name}_")]
    return files[max(prefixes, key=len)] if prefixes else None


def cura_setting_version(executable: Path) -> int | None:
    """Welche Einstellungsversion die installierte Cura-Fassung liest.

    Sie steht in ``fdmprinter.def.json`` unter ``metadata.setting_version``
    und in jedem mitgelieferten Qualitätsprofil; ein Profil mit einer anderen
    Zahl schickt Cura beim Import durch seine Versionsumstellung, und eine
    höhere kennt es nicht. ``None`` heißt: Die Installation trägt keine
    Definitionen, die sich lesen lassen.
    """
    installed = install_root(executable)
    if installed is None:
        return None
    definition = cura_resources(installed) / "definitions" / "fdmprinter.def.json"
    try:
        loaded = json.loads(definition.read_text(encoding="utf-8"))
        version = loaded["metadata"]["setting_version"]
    except (OSError, ValueError, KeyError, TypeError) as problem:
        _log.debug("no Cura setting version below %s: %s", installed, problem)
        return None
    return int(version) if isinstance(version, (int, str)) and str(version).isdigit() else None


def cura_quality_types(
    executable: Path, machine: Path | None, *, variant: str = "", material_type: str = ""
) -> dict[str, float]:
    """Die Qualitätsstufen, die Cura für diese Maschine kennt — Art auf Schichthöhe.

    Ein importiertes Profil muss eine davon nennen, sonst lehnt Cura es ab
    („Quality type … is not compatible", ``CuraContainerRegistry``). Welche
    gelten, steht in der Definition: ``has_machine_quality`` und
    ``quality_definition`` entlang der Erbkette, und ohne sie die allgemeinen
    Stufen von ``fdmprinter``.

    **Sichtbar ist nur, was es für Düse und Spule gibt.** Mit ``variant`` und
    ``material_type`` bleiben die Stufen, für die ein Qualitätsprofil dieser
    Düse und dieser Materialart liegt; eine andere importiert Cura, zeigt sie
    aber nicht an („not available for the current configuration"). Liegt für
    die Kombination keines, nimmt Cura die allgemeinen Stufen — dann bleiben
    alle (``MaterialNode._loadAll``, ``MachineNode.getQualityGroups``).
    """
    installed = install_root(executable)
    if installed is None:
        return {}
    resources = cura_resources(installed)
    definition = cura_quality_definition(executable, machine)
    found: dict[str, float] = {}
    specific: list[tuple[str, str, str]] = []
    for path in sorted((resources / "quality").rglob("*.inst.cfg")):
        parsed = _read_ini(path)
        if parsed is None or not parsed.has_section("metadata"):
            continue
        general = parsed["general"] if parsed.has_section("general") else {}
        metadata = parsed["metadata"]
        if (
            str(general.get("definition", "")).strip() != definition
            or str(metadata.get("type", "")).strip() != "quality"
        ):
            continue
        kind = str(metadata.get("quality_type", "")).strip()
        if str(metadata.get("global_quality", "")).strip().casefold() != "true":
            # Ein Profil für eine Düse und ein Material: Es macht eine Stufe
            # sichtbar, die Schichthöhe trägt die allgemeine.
            if kind:
                specific.append(
                    (
                        kind,
                        str(metadata.get("variant", "")).strip(),
                        str(metadata.get("material", "")).strip(),
                    )
                )
            continue
        values = parsed["values"] if parsed.has_section("values") else {}
        try:
            height = float(str(values.get("layer_height", "nan")))
        except ValueError:
            height = math.nan
        if kind and math.isfinite(height):
            found.setdefault(kind, height)
    if not (variant or material_type):
        return found
    available = _cura_available_qualities(resources, specific, variant, material_type)
    fitting = {kind: height for kind, height in found.items() if kind in available}
    return fitting or found


def _cura_available_qualities(
    resources: Path, specific: Sequence[tuple[str, str, str]], variant: str, material_type: str
) -> set[str]:
    """Die Qualitätsarten mit einem Profil für diese Düse und diese Materialart.

    Die Profile nennen ihr Material mit der Kennung der Grundmaterialdatei
    (``generic_pla``); eine eingelegte Spule derselben Art bekommt sie auch,
    wenn es für sie selbst keines gibt. Gelesen werden nur die Materialdateien,
    die ein Profil nennt.
    """
    files = _cura_material_files(resources / "materials")
    kinds: dict[str, str] = {}
    available: set[str] = set()
    for kind, own_variant, material in specific:
        if variant and own_variant != variant:
            continue
        if material_type:
            if material not in kinds:
                source = files.get(material)
                entry = _read_cura_material(source) if source is not None else None
                kinds[material] = entry.filament_type.casefold() if entry is not None else ""
            if kinds[material] != material_type.casefold():
                continue
        available.add(kind)
    return available


def cura_quality_definition(executable: Path, machine: Path | None) -> str:
    """Unter welcher Definition Cura die Qualitäten dieser Maschine führt.

    Ihre ``quality_definition``, wenn sie eigene Qualitäten hat, sonst
    ``fdmprinter`` — so setzt Cura ein importiertes Profil um. Die Erbkette
    reicht in den Bestand der Installation, auch von einer eigenen Definition
    im Konfigurationsordner aus.
    """
    installed = install_root(executable)
    if machine is None or installed is None:
        return "fdmprinter"
    own = _cura_quality_definition(machine, cura_resources(installed) / "definitions")
    return own or "fdmprinter"


def _cura_quality_definition(machine: Path, definitions: Path) -> str:
    """``quality_definition`` einer Maschine, wenn sie eigene Qualitäten hat — sonst leer."""
    current: Path | None = machine
    quality = ""
    own: bool | None = None
    for _step in range(MAX_INHERITANCE):
        if current is None:
            break
        try:
            loaded = json.loads(current.read_text(encoding="utf-8"))
        except OSError, ValueError:
            return ""
        metadata = loaded.get("metadata") if isinstance(loaded, dict) else None
        if isinstance(metadata, Mapping):
            if not quality and isinstance(metadata.get("quality_definition"), str):
                quality = str(metadata["quality_definition"])
            if own is None and isinstance(metadata.get("has_machine_quality"), bool):
                own = bool(metadata["has_machine_quality"])
        parent = loaded.get("inherits") if isinstance(loaded, dict) else None
        current = definitions / f"{parent}.def.json" if isinstance(parent, str) else None
    if not own:
        return ""
    return quality or cura_definition_id(machine)


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
    *,
    cancelled: CancelToken | None = None,
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
        for path in _checked_paths(root.rglob("*.json"), cancelled):
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
        found = _names_in(root, kind, cancelled=cancelled).get(name)
        if found is not None:
            return found
    return None


def _printer_name(value: str) -> str:
    """Ein Druckername, vergleichbar gemacht: ohne Groß- und Kleinschreibung,
    ohne „Original " und mit einem MINI, gleich wie Prusa ihn nennt — auch
    „MINI && MINI+", wie PrusaSlicers Bündel das Modell führt."""
    value = value.casefold().removeprefix("original ")
    return re.sub(r"^prusa mini(?:\+| is)?(?: &&? mini\+)?(?=\s|$)", "prusa mini", value)


#: Die Düse am Ende eines Maschinennamens, in jeder Schreibweise der
#: installierten Bestände: „0.4 nozzle“, „(0.4 nozzle)“, „(0.2 mm nozzle)“,
#: „HF0.4 nozzle“, „0.4 HF nozzle“. Nur am Ende und nur nach einem Wortrand —
#: „(0.4+0.6 nozzle)“ und „0.4 nozzle (Dual)“ nennen eine andere Maschine.
_NOZZLE_IN_NAME: Final = re.compile(
    r"(?:\s+\(?|(?<=HF))\d+(?:[.,]\d+)?\s*(?:mm)?\s*(HF\s+)?nozzle\)?$", re.IGNORECASE
)


def model_name(name: str) -> str:
    """Der Maschinenname ohne die Düse seiner Variante: das Gerät, wie es der
    Kunde nennt („Bambu Lab A1 0.4 nozzle“ → „Bambu Lab A1“).

    **Eine andere Ausführung bleibt im Namen.** Ein High-Flow-Hotend ist keine
    Düsengröße: „Original Prusa MK4S HF0.4 nozzle“ wird „Original Prusa MK4S
    HF“, nicht „Original Prusa MK4S“. Ein Name ohne Düsenangabe bleibt, wie er
    ist; ein Trenner vor der Düse („AzteQ Industrial - 0.6 nozzle“) fällt mit.
    """
    found = _NOZZLE_IN_NAME.search(name)
    if found is None:
        return name
    rest = (name[: found.start()] + (" HF" if found.group(1) else "")).rstrip(" -\u2013\u2014:,")
    return rest or name


def _names_the_printer(machine: str, title: str) -> bool:
    """Meint dieser Maschinenname diesen Drucker?

    Der Name des Slicers trägt Düse und Zusätze („… 0.4 nozzle"), der von
    Solidon nicht; verglichen wird deshalb am Anfang. Ein leerer Titel meint
    nichts — sonst passte er auf jede Maschine.

    **Und der Anfang muss ein ganzes Wort sein.** „Creality K1" ist nicht
    „Creality K1C": Bis zum 27.09.2026 passte der Titel auf jeden Namen, der
    mit ihm begann, und OrcaSlicer führt neben dem K1 den K1C, den K1 SE, den
    K1 Max und ihre CFS-Ausführungen. Seit bei gleicher Düse der kürzeste Name
    gewinnt (:func:`match`), gewann „Creality K1C 0.4 nozzle" gegen „Creality
    K1 (0.4 nozzle)" — ein K1 bekam die Maschine eines anderen Geräts und den
    Prozess „0.08mm SuperDetail".

    **Und dahinter folgt nur die Düse** (:data:`_NOZZLE_AFTER`, RM-600). Ein
    Leerzeichen reichte bis zum 08.10.2026, und „Anycubic Kobra 2" meinte damit
    auch den Kobra 2 Max, „Elegoo Neptune 4" den Neptune 4 Pro und Max mit
    anderem Bauraum, „Creality K1" den K1 SE, „Sovol SV06" den SV06 Plus. Wo
    Solidon das längere Gerät nicht kennt, ging dessen Maschine samt Startcode
    an den kürzeren Drucker. Gemessen an den Beständen von ElegooSlicer,
    OrcaSlicer, Bambu Studio, Creality Print, Anycubic Slicer Next und PrusaSlicer:
    Die Grenze nimmt 35, 35, 10, 22, 4 und 35 Zuordnungen weg, jede zu einem
    anderen Gerät oder einer anderen Ausführung (MMU3, 2T, 5T, CFS-C, ACE,
    High-Speed), keine zum selben. Eine High-Flow-Düse ist kein anderes Gerät, und
    was ein Drucker in PrusaSlicers Bündel festhält, meint er weiter
    (:func:`names_the_printer_profile`).

    Die eine Stelle für diesen Vergleich: :func:`printer_for` fragt „welcher
    meiner Drucker ist das", :func:`supports_printer` fragt „kennt dieser
    Slicer meinen Drucker". Zwei Formulierungen desselben Vergleichs würden
    auseinanderlaufen, sobald einer von beiden verfeinert wird. Was davor
    galt, fragt :func:`related_printer`.
    """
    rest = _rest_after(machine, title)
    return rest is not None and (not rest.strip() or _NOZZLE_AFTER.match(rest) is not None)


#: Was im Maschinennamen auf den Drucker folgen darf: die Düse, in jeder
#: Schreibweise der Bestände — „ 0.4 nozzle", „ (0.4 nozzle)", „ - 0.6 nozzle",
#: auch als High-Flow-Düse („ HF0.4 nozzle", „ 0.4 HF nozzle"). HF ist eine
#: Düsenart wie im Druckdialog, kein anderes Gerät.
_NOZZLE_AFTER: Final = re.compile(
    r"\s*[-\u2013\u2014:,]?\s*\(?(?:HF\s*)?\d+(?:[.,]\d+)?\s*(?:mm)?\s*(?:HF\s+)?nozzle\b",
    re.IGNORECASE,
)


def _rest_after(machine: str, title: str) -> str | None:
    """Was im Maschinennamen auf den Drucker folgt — ``None``, wenn er nicht
    mit ihm als ganzem Wort beginnt."""
    wanted = _printer_name(title)
    name = _printer_name(machine)
    if not title or not name.startswith(wanted):
        return None
    rest = name[len(wanted) :]
    return rest if not rest or not rest[0].isalnum() else None


def names_the_printer_profile(machine: str, profile: PrinterProfile) -> bool:
    """Meint dieser Maschinenname diesen Drucker — über seinen Titel oder über das
    Profil, das er in PrusaSlicers Bündel festhält (``prusaslicer_printer``)?

    Dort steht hinter dem Titel mehr als die Düse: der MK4S hält „Original Prusa
    MK4S HF0.4 nozzle", der XL „… XL Input Shaper 0.4 nozzle", der MINI „… MINI
    && MINI+ Input Shaper". Verglichen wird ohne die Düse (:func:`model_name`),
    damit die Düsenschwestern desselben Profils dazugehören.
    """
    if _names_the_printer(machine, profile.title):
        return True
    bundle = profile.prusaslicer_printer
    return bool(bundle) and _device_name(machine) == _device_name(bundle)


def _device_name(name: str) -> str:
    """Das Gerät hinter einem Maschinennamen: ohne Düse und ohne High-Flow-Zusatz."""
    return re.sub(r"\s+hf$", "", _printer_name(model_name(name)))


def related_printer(machine: str, known: Mapping[str, PrinterProfile]) -> str:
    """Ein bekannter Drucker, mit dessen Namen die Maschine nur beginnt — ein
    Verwandter wie „Creality K1 SE" zum „Creality K1" —, sonst nichts.

    Seit hinter dem Drucker nur die Düse folgen darf (:func:`_names_the_printer`),
    gehört eine solche Maschine keinem bekannten Drucker. Wer daraus „ein
    eigenes Profil" schließt, gibt sie jedem Projekt
    (:func:`app.core.export.handover._fits_the_printer`); sie ist aber das Profil
    eines anderen Geräts.

    **Nur ein Name, der auf die Düse endet**, wie jedes Herstellerprofil. Ein
    eigenes Profil heißt, wie der Kunde will — „Creality K1 Garage" ist seins und
    kein Verwandter (Review RM-600, Runde 2).
    """
    if _NOZZLE_IN_NAME.search(machine) is None:
        return ""
    for identifier, profile in known.items():
        rest = _rest_after(machine, profile.title)
        if rest and not names_the_printer_profile(machine, profile):
            return identifier
    return ""


def known_printers(flavour: SlicerFlavour, executable: Path) -> tuple[str, ...]:
    """Welche Drucker dieser Slicer überhaupt kennt (§29).

    **Nicht dasselbe wie** :func:`find_profiles` **mit** ``machine``: Dort
    geht es um die Auswahl eines Profils mit Düse und Variante. Hier geht es
    um Wissen: Wer zwei Drucker und zwei Slicer hat, will sehen, welcher davon
    den vor ihm stehenden überhaupt kennt.

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


def discover_printers(executable: Path, flavour: SlicerFlavour) -> tuple[PrinterProfile, ...]:
    """Belegte Drucker des Slicers, ohne sie im Nutzerbestand zu speichern.

    Die native Profilidentität bleibt erhalten, auch bei gleicher Maschine
    mit anderer Düse. Unvollständige Erbketten, Formeln statt Maßen und kaputte
    Konturen ergeben kein scheinbar brauchbares Druckerprofil. Die Auswahl
    speichert später ausschließlich das ausdrücklich gewählte Profil.
    """
    roots = profile_roots(flavour, executable)
    indexes: ProfileIndexes = {}
    documents: ProfileDocuments = {}
    known = knowledge_profiles.printer_profiles()
    found: dict[str, PrinterProfile] = {}
    for entry in find_profiles(executable, flavour, kinds=("machine",)):
        try:
            values = resolve_profile(
                entry, roots, indexes=indexes, documents=documents, strict=True
            )
            printer = _discovered_printer(
                entry, flavour, values, known, discover.program_mark(executable.name)
            )
            area = build_area.printable_area(printer)
            if area.is_empty:
                raise _incomplete_profile(entry.path)
        except (
            ExternalToolError,
            ValidationError,
            ValueError,
            TypeError,
            OverflowError,
        ) as problem:
            _log.debug("skipping incomplete printer %s: %s", entry.name, problem)
            continue
        found[printer.id] = printer
    return tuple(sorted(found.values(), key=lambda printer: (printer.title.casefold(), printer.id)))


#: Was ein Slicer einsetzt, wenn ein Maschinenprofil samt Erbkette einen
#: Schlüssel gar nicht nennt — seine eingebaute Vorgabe (Entscheidung Robert,
#: 05.10.2026). Orca-Familie: ``set_default_value`` in ``PrintConfig.cpp``,
#: gleich in OrcaSlicer, Bambu Studio, ElegooSlicer, Creality Print und
#: Anycubic Slicer Next; Prusa-Familie: ``--save`` von PrusaSlicer 2.9.6 und
#: SuperSlicer 2.5.59.13. Ein vorhandener, aber unbrauchbarer Wert bleibt eine
#: Absage. Betroffen waren CR-20 und i3 Mega bei PrusaSlicer, M3D Enabler bei
#: Orca.
MACHINE_DEFAULTS: Final[Mapping[str, Mapping[str, object]]] = {
    "orca": {
        "printable_area": ["0x0", "200x0", "200x200", "0x200"],
        "printable_height": "100",
        "nozzle_diameter": ["0.4"],
    },
    "prusa": {
        "bed_shape": "0x0,200x0,200x200,0x200",
        "max_print_height": "200",
        "nozzle_diameter": "0.4",
    },
}


def _machine_value(values: Mapping[str, Any], key: str, flavour: SlicerFlavour) -> Any:
    """Der Wert aus der Kette oder, wenn sie ihn gar nicht nennt, die Vorgabe des Slicers."""
    return values[key] if key in values else MACHINE_DEFAULTS.get(flavour, {}).get(key)


def _profile_numbers(value: Any) -> tuple[float, ...]:
    """Native Zahlenlisten; ein leerer oder ungültiger Wert ist eine Absage."""
    raw = value if isinstance(value, (list, tuple)) else str(value).split(",")
    if any(isinstance(item, bool) for item in raw):
        raise ValueError("boolean dimension")
    numbers = tuple(float(item) for item in raw)
    if not numbers or any(not math.isfinite(item) or item <= 0.0 for item in numbers):
        raise ValueError("missing or invalid dimension")
    return numbers


def _cura_machine_instances(
    roots: Sequence[Path],
    indexes: ProfileIndexes,
    documents: ProfileDocuments,
    *,
    resolve_jerk: bool = False,
    cura_raft_contact: dict[str, Any] | None = None,
) -> Iterator[tuple[SlicerProfile, dict[str, Any]]]:
    """Eigene Cura-Maschinen einschließlich ihrer Maschinen- und Düsencontainer.

    In der Stapelfolge steht die kleinste Nummer oben. Hardware kommt aus
    Definition, Variante und Nutzerwerten; Jerk zusätzlich aus den gewählten
    Prozesscontainern und dem Extruder. Andere Prozesswerte bleiben draußen.
    Ein referenzierter, aber fehlender Container macht die Maschine unbekannt.
    """
    definitions: dict[str, Path] = {}
    installed_containers: dict[str, Path] = {}
    for root in roots:
        resources = cura_resources(root)
        for kind in ("definitions", "extruders"):
            definitions.update(
                {
                    cura_definition_id(path): path
                    for path in sorted((resources / kind).glob("*.def.json"))
                }
            )
        for kind in ("variants", "quality", "intent"):
            installed_containers.update(
                {
                    unquote_plus(path.name.removesuffix(".inst.cfg")): path
                    for path in sorted((resources / kind).rglob("*.inst.cfg"))
                }
            )
    for folder in roots:
        if not (folder / "machine_instances").is_dir():
            continue
        containers = dict(installed_containers)
        for kind in (
            "definition_changes",
            "variants",
            "quality",
            "intent",
            "quality_changes",
            "user",
        ):
            containers.update(
                {
                    unquote_plus(path.name.removesuffix(".inst.cfg")): path
                    for path in sorted((folder / kind).rglob("*.inst.cfg"))
                }
            )

        def changes(
            stack: Mapping[str, str],
            source: Path,
            paths: Mapping[str, Path] = containers,
            *,
            motion: bool = False,
            raft_contact: bool = False,
        ) -> dict[str, Any]:
            values: dict[str, Any] = {}
            positions: tuple[str, ...] = (_CURA_DEFINITION_CHANGES_INDEX, _CURA_VARIANT_INDEX)
            positions += ("3", "2", "1", "0") if motion or raft_contact else ("0",)
            for position in positions:
                identifier = stack.get(position, "").strip()
                if not identifier or identifier.startswith("empty_"):
                    continue
                path = paths.get(identifier)
                parsed = _read_ini(path) if path is not None else None
                if parsed is None:
                    raise _incomplete_profile(source)
                if parsed.has_section("values"):
                    if raft_contact:
                        # Die Herkunft bleibt auch in gewählten Prozesscontainern
                        # erhalten; andere Prozesswerte werden hier nicht übernommen.
                        values.update(
                            (key, value)
                            for key, value in parsed["values"].items()
                            if key in {"raft_airgap", "layer_0_z_overlap"}
                        )
                        continue
                    # Formeln bleiben als ungültiger Wert stehen; sie dürfen
                    # keinen vorhandenen Default wieder sichtbar machen.
                    values.update(
                        (key, value)
                        for key, value in parsed["values"].items()
                        if not motion
                        or key.startswith("jerk_")
                        or key.endswith("_jerk")
                        or key == "magic_spiralize"
                    )
            return values

        for path in sorted((folder / "machine_instances").glob("*.global.cfg")):
            parsed = _read_ini(path)
            if parsed is None or not all(
                parsed.has_section(name) for name in ("general", "containers")
            ):
                continue
            general, stack = parsed["general"], parsed["containers"]
            machine = general.get("id", "").strip()
            definition = definitions.get(stack.get("7", ""))
            if not machine or definition is None:
                continue
            try:
                overrides = changes(stack, path)
                native = _cura_definition_values(
                    definition,
                    roots,
                    strict=True,
                    indexes=indexes,
                    documents=documents,
                    overrides=overrides,
                    resolve_jerk=False,
                    cura_raft_contact=cura_raft_contact,
                )
                if cura_raft_contact is not None:
                    cura_raft_contact.update(changes(stack, path, raft_contact=True))
                if resolve_jerk:
                    overrides.update(changes(stack, path, motion=True))
                trains = _cura_trains(folder, machine)
                train_motion: list[dict[str, Any]] = []
                if trains:
                    if [position for position, _stack in trains] != list(range(len(trains))):
                        raise _incomplete_profile(path)
                    nozzle_values = []
                    for _position, train in trains:
                        extruder = definitions.get(train.get("7", ""))
                        if extruder is None:
                            raise _incomplete_profile(path)
                        hardware = _cura_definition_values(
                            extruder,
                            roots,
                            strict=True,
                            indexes=indexes,
                            documents=documents,
                            overrides=changes(train, path),
                            resolve_jerk=False,
                        )
                        if resolve_jerk:
                            train_motion.append(changes(train, path, motion=True))
                        nozzle_values.append(
                            _profile_numbers(
                                hardware.get(
                                    "machine_nozzle_size", native.get("machine_nozzle_size")
                                )
                            )[0]
                        )
                    count = _profile_numbers(native.get("machine_extruder_count", len(trains)))[0]
                    if not count.is_integer() or int(count) != len(trains):
                        raise _incomplete_profile(path)
                    native["machine_nozzle_size"] = nozzle_values
                    native["machine_extruder_count"] = len(trains)
                if resolve_jerk:
                    resolved = _cura_definition_values(
                        definition,
                        roots,
                        strict=True,
                        indexes=indexes,
                        documents=documents,
                        overrides=overrides,
                        extruder_overrides=train_motion,
                        resolve_jerk=True,
                    )
                    native = {
                        key: value
                        for key, value in native.items()
                        if not (key.startswith("jerk_") or key.endswith("_jerk"))
                    }
                    native.update(
                        (key, value)
                        for key, value in resolved.items()
                        if key.startswith("jerk_") or key.endswith("_jerk")
                    )
                yield (
                    SlicerProfile(
                        definition,
                        general.get("name", machine).strip(),
                        "machine",
                        printer_model=cura_definition_id(definition),
                        nozzle=_profile_numbers(native.get("machine_nozzle_size"))[0],
                        section=machine,
                        from_user=True,
                        cura_instance=path,
                    ),
                    native,
                )
            except (ExternalToolError, ValueError, TypeError, OverflowError) as problem:
                _log.debug("skipping incomplete Cura stack %s: %s", machine, problem)


#: Was ``std::istringstream >> double`` von einer Koordinate liest: die Zahl am
#: Anfang, bis zum ersten Zeichen, das keine mehr fortsetzt, sonst null.
_STREAM_NUMBER: Final = re.compile(
    r"\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
)


def _stream_point(text: str) -> tuple[float, float]:
    """Ein Punkt ``AxB``, wie Orca und PrusaSlicer ihn lesen.

    ``ConfigOptionPoints::deserialize`` trennt am ``x`` und liest jede Hälfte
    aus einem ``istringstream``; was dort nicht als Zahl beginnt, bleibt null.
    PrusaSlicers Bündel führt den AnkerMake M5 mit ``235-0`` — der Slicer liest
    235 mal 0, und so liest es Solidon auch.
    """
    first, separator, rest = text.partition("x")
    found = [_STREAM_NUMBER.match(part) for part in (first, rest.split("x", 1)[0])]
    numbers = [float(match.group(1)) if match else 0.0 for match in found]
    return numbers[0], numbers[1] if separator else 0.0


def _profile_points(value: Any) -> tuple[tuple[float, float], ...]:
    """Orca-/Prusa-Koordinaten und Curas JSON-Konturen als reine Daten.

    Orca hängt die Einträge einer Punktliste mit Komma aneinander, bevor es sie
    liest (``ConfigBase::load_from_json``): ``["0x0,11x0,11x16,0x16"]`` sind
    vier Punkte, wie Qidis Profile für Q2 und X-Max 4 sie schreiben.
    """
    if isinstance(value, str):
        value = json.loads(value) if value.lstrip().startswith("[") else [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError("invalid contour")
    points: list[tuple[float, float]] = []
    for item in value:
        if isinstance(item, str):
            read = [_stream_point(token) for token in (item.split(",") if item else ())]
        else:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("invalid contour point")
            if any(isinstance(number, bool) for number in item):
                raise ValueError("boolean coordinate")
            read = [(float(item[0]), float(item[1]))]
        # Für beide Schreibweisen: ``1e999`` liest auch der Strom als unendlich.
        if not all(math.isfinite(number) for point in read for number in point):
            raise ValueError("nonfinite coordinate")
        points.extend(read)
    return tuple(points)


def _convex_hull(points: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Die konvexe Hülle gegen den Uhrzeigersinn ab dem kleinsten Punkt, leer ohne Fläche.

    Monotone Kette über eine Handvoll Punkte, in fester Folge gerechnet — auf
    jeder Maschine dieselbe Ecke zuerst.
    """
    unique = sorted(set(points))

    def turn(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    chains: list[list[tuple[float, float]]] = []
    for ordered in (unique, unique[::-1]):
        chain: list[tuple[float, float]] = []
        for point in ordered:
            while len(chain) >= 2 and turn(chain[-2], chain[-1], point) <= 0.0:
                chain.pop()
            chain.append(point)
        chains.append(chain[:-1])
    hull = (*chains[0], *chains[1])
    return hull if len(hull) >= 3 else ()


def _discovered_printer(
    entry: SlicerProfile,
    flavour: SlicerFlavour,
    values: Mapping[str, Any],
    known: Mapping[str, PrinterProfile],
    source: str,
) -> PrinterProfile:
    """Native Bettkoordinaten einmal in Solidons zentrierte Kontur übersetzen."""
    if str(values.get("printer_technology", "FFF")).upper() not in {"FFF", "FDM"}:
        raise _incomplete_profile(entry.path)
    exclusions: tuple[tuple[tuple[float, float], ...], ...] = ()
    if flavour == "cura":
        width = _profile_numbers(values.get("machine_width"))[0]
        depth = _profile_numbers(values.get("machine_depth"))[0]
        height = _profile_numbers(values.get("machine_height"))[0]
        nozzles = _profile_numbers(values.get("machine_nozzle_size"))
        count = _profile_numbers(values.get("machine_extruder_count", 1))[0]
        if not count.is_integer():
            raise _incomplete_profile(entry.path)
        # Curas ``BuildVolume`` fragt nur ``elliptic``; jede andere Angabe ist
        # ein Rechteck — auch Leapfrogs ``Rectangular``.
        if str(values.get("machine_shape", "rectangular")) == "elliptic":
            sections = 4
            while max(width, depth) / 2.0 * (1.0 - inscribed_ratio(sections)) > MAX_FACET_SAG:
                sections *= 2
            contour = tuple(
                (x * width / 2.0, y * depth / 2.0)
                for x, y in (circle_point(sections, index) for index in range(sections))
            )
        else:
            contour = ()
        # Cura definiert Sperrzonen relativ zur Bettmitte, unabhängig vom
        # G-Code-Ursprung (machine_center_is_zero), und sperrt von jeder die
        # konvexe Hülle (``Polygon.getMinkowskiHull``).
        blocked = values.get("machine_disallowed_areas", [])
        if isinstance(blocked, str):
            blocked = json.loads(blocked)
        if not isinstance(blocked, (list, tuple)):
            raise _incomplete_profile(entry.path)
        exclusions = tuple(
            hull for hull in (_convex_hull(_profile_points(points)) for points in blocked) if hull
        )
        # Curas Ursprung liegt an der Ecke oder in der Mitte — dieselbe
        # Lesart wie ``handover._cura_machine`` (RM-330, RM-424).
        centred = str(values.get("machine_center_is_zero", "")).strip().lower() == "true"
        origin: tuple[float, float] | None = (0.0, 0.0) if centred else None
    else:
        contour = _profile_points(
            _machine_value(values, "bed_shape" if flavour == "prusa" else "printable_area", flavour)
        )
        if len(contour) < 3:
            raise _incomplete_profile(entry.path)
        left, right = min(x for x, _y in contour), max(x for x, _y in contour)
        front, back = min(y for _x, y in contour), max(y for _x, y in contour)
        width, depth = right - left, back - front
        if width <= 0.0 or depth <= 0.0:
            raise _incomplete_profile(entry.path)
        height = _profile_numbers(
            _machine_value(
                values, "max_print_height" if flavour == "prusa" else "printable_height", flavour
            )
        )[0]
        nozzles = _profile_numbers(_machine_value(values, "nozzle_diameter", flavour))
        count = float(len(nozzles))
        cx, cy = (left + right) / 2.0, (front + back) / 2.0
        contour = tuple((x - cx, y - cy) for x, y in contour)
        # **Der Ursprung bleibt erhalten** (RM-424). Zentriert wird die
        # Kontur, und bis dahin ging dabei verloren, wo die Maschine ihre
        # Null hat: Die Übergabe nahm jede von der Ecke, und am Dremel 3D45
        # (-127,5 bis 97,5) lag ein Würfel aus der Bettmitte am hinteren Rand.
        # Ein Bett ab der Ecke bleibt ohne Angabe, wie jedes ältere Profil.
        origin = (
            None
            if is_zero(left) and is_zero(front)
            else (0.0 if is_zero(cx) else -cx, 0.0 if is_zero(cy) else -cy)
        )
        # Sperrzonen kennt nur die Orca-Familie; PrusaSlicer übergeht den
        # Schlüssel, den QIDIs und Snapmakers Bündel trotzdem tragen.
        blocked = values.get("bed_exclude_area", []) if flavour == "orca" else []
        if blocked:
            exclusions = tuple(
                tuple((x - cx, y - cy) for x, y in corners)
                for corners in build_area.exclusion_boxes(_profile_points(blocked))
            )
    vendor = entry.vendor or ("" if entry.from_user else _vendor_of(entry.path, "machine"))
    # Bahnbreite und Schichthöhe sind Arbeitsvorgaben, keine Herstellermaße;
    # sie folgen der belegten Düse, wie beim eigenen Druckerprofil.
    model = (
        entry.name
        if flavour == "cura"
        else entry.printer_model or str(values.get("printer_model", "")) or entry.name
    )
    if flavour == "cura" and entry.section:
        definition = _read_cura_machine(entry.path)
        model = definition.name if definition is not None else model
    matched = known.get(printer_for(model, known))
    # Ein Namenspräfix genügt für eine Vorauswahl, nicht für die Übernahme
    # von Hardwarewissen: K1 Max ist kein K1. Düsenabhängige Vorgaben bleiben
    # ebenfalls beim passenden Durchmesser.
    if matched is not None and (
        _printer_name(model) != _printer_name(matched.title)
        or abs(matched.nozzle_diameter - nozzles[0]) > EPS_GEOM
    ):
        matched = None
    base = matched or PrinterProfile(id="", title="", build_volume=(width, depth, height))
    return replace(
        base,
        id=_printer_identifier(entry, flavour, source),
        title=entry.name,
        build_volume=(width, depth, height),
        nozzle_diameter=nozzles[0],
        nozzles=int(count),
        layer_height=min(0.2, nozzles[0] / 2.0),
        extrusion_width=round(nozzles[0] * 1.05, 3),
        vendor=vendor,
        printable_area=contour,
        bed_exclusions=exclusions,
        printable_height=None,
        bed_origin=origin,
        cura_definition=entry.printer_model if flavour == "cura" else "",
        prusaslicer_printer=entry.name if flavour == "prusa" else "",
    )


def _printer_identifier(entry: SlicerProfile, flavour: SlicerFlavour, source: str) -> str:
    """Cura-Instanzen behalten ihre Kennung bei geändertem Anzeigenamen."""
    vendor = entry.vendor or ("" if entry.from_user else _vendor_of(entry.path, "machine"))
    native_id = entry.section or (entry.printer_model if flavour == "cura" else entry.name)
    identity: tuple[str, ...] = (source, flavour, vendor, native_id)
    if flavour != "cura" or entry.cura_instance is None:
        identity += (entry.name,)
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()[
        :20
    ]
    return f"slicer-{flavour}-{digest}"


def _legacy_cura_printer_identifier(entry: SlicerProfile, source: str, title: str) -> str:
    """Eine gespeicherte Cura-Kennung mit Namensanteil berechnen."""
    vendor = entry.vendor or ("" if entry.from_user else _vendor_of(entry.path, "machine"))
    native_id = entry.section or entry.printer_model
    identity = (source, "cura", vendor, native_id, title)
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"slicer-cura-{digest[:20]}"


def matches_saved_cura_printer(entry: SlicerProfile, printer: PrinterProfile, source: str) -> bool:
    """Ordnet eine gespeicherte Cura-Kennung ihrer nativen Instanz zu.

    Der historische Hash enthält den gespeicherten Anzeigenamen. Zusätzlich
    muss die Cura-Druckerdefinition exakt übereinstimmen; Ähnlichkeit reicht
    nicht.
    """
    return (
        entry.cura_instance is not None
        and bool(entry.section)
        and printer.id.startswith("slicer-cura-")
        and bool(printer.cura_definition)
        and printer.cura_definition == entry.printer_model
        and _legacy_cura_printer_identifier(entry, source, printer.title) == printer.id
    )


def cura_instance_is_present(executable: Path, printer: PrinterProfile) -> bool:
    """Ob eine gespeicherte Cura-Instanz noch im lokalen Bestand steht.

    Die Maschinenwerte können unvollständig sein und die Instanz damit aus
    :func:`find_profiles` fallen. Ihre native Kennung bleibt trotzdem lesbar
    und trennt diesen Fall von einem Drucker, der auf diesem Rechner fehlt.
    """
    if not printer.id.startswith("slicer-cura-"):
        return False
    source = discover.program_mark(executable.name)
    for root in user_roots("cura", executable):
        for path in sorted((root / "machine_instances").glob("*.global.cfg")):
            parsed = _read_ini(path)
            if parsed is None or not parsed.has_section("general"):
                continue
            general = parsed["general"]
            section = general.get("id", "").strip()
            if not section:
                continue
            containers = parsed["containers"] if parsed.has_section("containers") else {}
            entry = SlicerProfile(
                path=path,
                name=general.get("name", "").strip() or section,
                kind="machine",
                printer_model=containers.get("7", "").strip() or printer.cura_definition,
                section=section,
                from_user=True,
                cura_instance=path,
            )
            if _printer_identifier(
                entry, "cura", source
            ) == printer.id or matches_saved_cura_printer(entry, printer, source):
                return True
    return False


def chosen_printer(
    flavour: SlicerFlavour,
    executable: Path,
    known: Mapping[str, PrinterProfile],
    *,
    prefer: str = "",
) -> str:
    """Die aktive Maschine mit ihrer Identität, auch bei gleichem Cura-Anzeigenamen.

    ``prefer`` wie bei :func:`printer_for`: derselbe Drucker unter zweiter
    Identität gilt als der gemeinte. Cura unterscheidet seine Instanzen
    selbst und braucht es nicht.
    """
    chosen = chosen_machine(flavour, executable)
    if flavour == "cura":
        entry = profile_by_name(executable, flavour, chosen, "machine") if chosen else None
        if entry is None:
            return ""
        source = discover.program_mark(executable.name)
        saved = [
            identifier
            for identifier, printer in known.items()
            if matches_saved_cura_printer(entry, printer, source)
        ]
        if len(saved) == 1:
            return saved[0]
        if entry.printer_id in known:
            return entry.printer_id
        # Die Werksdefinition bezeichnet eine Modellfamilie, keine konfigurierte
        # Cura-Instanz. Zwei Instanzen derselben Familie bleiben getrennt.
        if entry.cura_instance is not None:
            return ""
        definitions = [
            identifier
            for identifier, printer in known.items()
            if entry.printer_model and printer.cura_definition == entry.printer_model
        ]
        return definitions[0] if len(definitions) == 1 else ""
    return printer_for(chosen, known, prefer=prefer)


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


def printer_for(machine: str, known: Mapping[str, PrinterProfile], *, prefer: str = "") -> str:
    """Welches Druckerprofil dieser Maschinenname meint — oder nichts.

    Der Name des Slicers trägt Düse und Zusätze („… 0.4 nozzle"), der von
    Solidon nicht; verglichen wird deshalb am Anfang. Trifft nichts, bleibt es
    leer: geraten wird hier so wenig wie in :func:`match`.

    **Ein Gerät kann zweimal bekannt sein**: eingebaut („Elegoo Centauri
    Carbon 2") und aus dem Slicer übernommen („Elegoo Centauri Carbon 2 0.4
    nozzle"). Dann gewann der längere Titel, und wer fragte „gehört diese
    Maschine meinem Projektdrucker?", bekam den Zwilling zur Antwort (RM-600).
    ``prefer`` nennt den gemeinten Drucker; er gewinnt, wenn er dasselbe Gerät
    ist wie der Treffer — gleicher Name ohne Düse — und dieser Name die
    Maschine meint. Ein anderes Gerät gewinnt nie: „Elegoo Neptune 4" bleibt
    hinter „Elegoo Neptune 4 Plus".
    """
    hits = [
        identifier
        for identifier, profile in known.items()
        if names_the_printer_profile(machine, profile)
    ]
    if not hits:
        return ""
    # Der längste Titel gewinnt: „Elegoo Neptune 4 Plus" vor „Elegoo Neptune 4".
    best = max(hits, key=lambda identifier: len(known[identifier].title))
    wanted = known.get(prefer) if prefer else None
    # Dasselbe Gerät heißt hier wie bei den Treffern: Titel oder Bündelprofil,
    # ohne Düse und High-Flow-Zusatz. Über ``model_name`` allein blieben die
    # eingebauten Prusa-Drucker draußen — der MK4S hält „… MK4S HF0.4 nozzle“
    # (Review RM-600, Runde 2).
    if (
        wanted is not None
        and (
            _names_the_printer(machine, model_name(wanted.title))
            or names_the_printer_profile(machine, wanted)
        )
        and _devices(wanted) & _devices(known[best])
    ):
        return prefer
    return best


def _devices(profile: PrinterProfile) -> set[str]:
    """Die Geräte, die ein Drucker meint: sein Titel und sein Bündelprofil."""
    return {_device_name(name) for name in (profile.title, profile.prusaslicer_printer) if name}


def machine_with_nozzle(
    machine: str,
    flavour: SlicerFlavour,
    executable: Path,
    printer: PrinterProfile,
    *,
    available: Sequence[SlicerProfile] | None = None,
) -> str:
    """Dieselbe Maschine, aber mit der Düse, für die das Projekt rechnet.

    **Warum das eine eigene Frage ist.** Ein Maschinenname nennt den Drucker
    *und* seine Düse („Elegoo Centauri Carbon 2 0.2 nozzle"), und
    :func:`printer_for` vergleicht nur den Drucker — der Name trägt die Düse
    am Ende, der von Solidon trägt sie gar nicht. Wer allein danach geht, hält
    die 0,2er Variante für dasselbe Gerät wie die 0,4er. Sie ist es auch, nur
    rechnet das Projekt dann mit der falschen Bahnbreite.

    Gemessen am 16.09.2026: ElegooSlicer stand auf „… 0.2 nozzle", das Projekt
    auf einem Centauri Carbon 2 mit 0,4. Solidon übergab die Maschinenseite
    der 0,2er Düse und daneben einen Prozess mit ``line_width`` 0,42 — ein in
    sich widersprüchlicher Auftrag. Der Slicer nahm ihn nicht an und fiel auf
    seine Vorgaben zurück: **jede** Linienbreite stand auf null, und er meldete
    „zu geringe Linienbreite". Von Solidons Werten kam keiner an.

    Passt die eingestellte Maschine, bleibt sie. Sonst gilt dieselbe Regel wie
    in :func:`match`: unter den Varianten **desselben** Geräts entscheidet die
    Düse. Findet sich keine, bleibt es leer — das ist Regel 21, denn eine
    fremde Maschine brächte den Startcode eines anderen Druckers mit.
    """
    # **Eine Datei, die schon passt, braucht keinen Bestand.** Der Druckdialog
    # reicht die gewählte Maschine als Pfad weiter, und unten fände der
    # Vergleich über den Namen sie ohnehin nicht — gesucht wurde trotzdem in
    # jedem Maschinenprofil des Slicers, gemessen 0,35 Sekunden je Aufruf, und
    # die Grundlage aus dem Herstellerprofil fragt bei jeder Profilwahl.
    direct = Path(machine)
    if direct.suffix == ".json" and direct.is_file():
        own = _read(direct, "machine", False)
        if own is not None and abs(own.nozzle - printer.nozzle_diameter) < 1e-6:
            return machine
    machines_here = [
        entry
        for entry in (
            available if available is not None else find_profiles(executable, flavour, ("machine",))
        )
        if entry.kind == "machine"
    ]
    fits = [entry for entry in machines_here if abs(entry.nozzle - printer.nozzle_diameter) < 1e-6]
    current = [entry for entry in machines_here if identity(entry) == machine]
    if not current:
        named = [entry for entry in machines_here if entry.name == machine]
        current = named if len(named) == 1 else []
    if current and any(entry in fits for entry in current):
        return machine
    if not current or all(entry.nozzle <= 0.0 for entry in current):
        # Die eingestellte Maschine ist gar nicht (mehr) lesbar, oder sie
        # nennt keine Düse. Beides ist **keine** Aussage über die Düse, und
        # aus einer fehlenden Angabe eine Abweichung zu machen hieße raten
        # (Regel 21): Die bisherige Prüfung über den Drucker bleibt dann die
        # ganze Auskunft.
        return machine
    current_machine = current[0]
    same_printer = [
        entry
        for entry in fits
        if identity(entry) == identity(current_machine)
        or same_printer_model(entry, current_machine)
    ]
    chosen = sister_variant(same_printer, current_machine, printer.nozzle_diameter)
    if chosen is None:
        return ""
    # Namen können bei verschiedenen Herstellern gleich sein. Die nächste
    # Stufe schreibt das Profil aus; sie braucht deshalb dessen Kennung.
    return identity(chosen)


def sister_variant(
    machines_here: Sequence[SlicerProfile], reference: SlicerProfile, nozzle: float
) -> SlicerProfile | None:
    """Die Variante desselben Geräts mit dieser Düse — oder keine.

    **Eine Stelle für Druckdialog und Übergabe** (:func:`match`,
    :func:`machine_with_nozzle`): Beide fragen nach einem Düsenwechsel, welche
    Schwester gemeint ist. Bis dahin nahm der eine den kürzesten, der andere
    den alphabetisch ersten Namen — am SV06 zwei verschiedene Maschinen.

    Vorrang haben eigene Profile, dann **dieselbe Ausführung**
    (:func:`model_name`: aus „MK4S HF0.4“ wird bei 0,6 „MK4S HF0.6“, nicht die
    gewöhnliche Düse, die zuerst im Alphabet steht), dann die schlichteste.
    """
    fitting = [
        entry
        for entry in machines_here
        if abs(entry.nozzle - nozzle) < 1e-6
        and (identity(entry) == identity(reference) or same_printer_model(entry, reference))
    ]
    return min(fitting, key=variant_order(reference, nozzle), default=None)


def variant_order(
    reference: SlicerProfile | None, nozzle: float
) -> Callable[[SlicerProfile], tuple[bool, float, bool, int, str]]:
    """Die Reihenfolge unter Maschinenvarianten: eigene zuerst, dann die Düse,
    dann dieselbe Ausführung wie ``reference``, dann der kürzeste Name.

    Der kürzeste Name ist die Grundausführung: OrcaSlicer führt den Sovol SV06
    als „0.4 nozzle“ und als „0.4 High-Speed nozzle“, und ohne diese Regel
    entschied die Reihenfolge im Ordner — ein gewöhnlicher SV06 bekam den
    High-Speed-Prozess (27.09.2026).
    """
    kind = model_name(reference.name) if reference is not None else ""

    def order(entry: SlicerProfile) -> tuple[bool, float, bool, int, str]:
        return (
            not entry.from_user,
            abs(entry.nozzle - nozzle),
            bool(kind) and model_name(entry.name) != kind,
            len(entry.name),
            entry.name,
        )

    return order


def _load(path: Path, documents: ProfileDocuments | None = None) -> dict[str, Any] | None:
    """Der Inhalt einer Profildatei — ``None``, wenn sie sich nicht lesen lässt
    oder kein JSON-Objekt ist. Mit ``documents`` einmal je Durchgang."""
    documents = _pass_documents(documents)
    if documents is not None and path in documents:
        return documents[path]
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _log.debug("unreadable profile %s: %s", path.name, problem)
        loaded = None
    document = loaded if isinstance(loaded, dict) else None
    if documents is not None:
        documents[path] = document
    return document


def _read(
    path: Path,
    kind: ProfileKind,
    from_user: bool,
    documents: ProfileDocuments | None = None,
) -> SlicerProfile | None:
    """Ein Profil aus seiner Datei. Was sich nicht lesen lässt, fehlt einfach.

    Ein kaputtes oder unbekanntes JSON im Bestand eines fremden Programms ist
    kein Grund, die Auswahl scheitern zu lassen — es ist ein Eintrag weniger.

    Die Art kommt aus dem Ordner und nicht aus dem Feld ``type``: selbst
    angelegte Profile tragen es gar nicht, sie erben bloß von einem
    Systemprofil. Genau die will man in der Liste haben.
    """
    loaded = _load(path, documents)
    if loaded is None:
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
        default_filament=_first_string(loaded.get("default_filament_profile")),
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


def variant_index(
    values: Mapping[str, Any],
    variant_key: str,
    extruder_key: str,
    variant_name: str,
    extruder_id: str,
) -> tuple[int, int] | None:
    """Ordnet eine aktive Variante der passenden Liste im Profil zu."""
    variants = _strings(values.get(variant_key))
    if not variants:
        return None
    if not variant_name:
        return (0, len(variants))
    matches = [
        index for index, name in enumerate(variants) if name.casefold() == variant_name.casefold()
    ]
    ids = _strings(values.get(extruder_key))
    if extruder_id and len(ids) == len(variants):
        matches = [index for index in matches if ids[index] == extruder_id]
    return (matches[0], len(variants)) if len(matches) == 1 else None


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
            for path in sorted((cura_resources(root) / folder).rglob(pattern)):
                count += 1
                if count > MAX_FILES:
                    _log.warning("stopped after %d Cura profile files below %s", MAX_FILES, root)
                    return list(found.values())
                profile = _read_cura(path, kind)
                if profile is not None:
                    # Gleicher Titel bei anderem Durchmesser ist eine andere
                    # native Datei und darf nicht still ersetzt werden.
                    found[(kind, path.name)] = replace(profile, from_user=root in users)
    if "machine" in wanted:
        for entry, _native in _cura_machine_instances(profile_roots("cura", executable), {}, {}):
            found[("machine", identity(entry))] = entry
    source = discover.program_mark(executable.name)
    found = {
        key: replace(entry, printer_id=_printer_identifier(entry, "cura", source))
        if entry.kind == "machine"
        else entry
        for key, entry in found.items()
    }
    _log.info("found %d Cura profiles", len(found))
    return list(found.values())


def _cura_user_roots(executable: Path, config: Path, *, platform: str | None = None) -> list[Path]:
    """Cura speichert je Programmversion, nicht je Nutzerkonto.

    Ein Cura als Flatpak legt Daten wie Konfiguration in seinem eigenen
    ``~/.var/app/<Kennung>`` ab (:func:`config_base`).
    """
    candidates = [config / "cura"]
    if (platform or sys.platform).startswith("linux"):
        app = discover.flatpak_app(executable)
        if app:
            own = discover.flatpak_data(app)
            data = own / "data" if own is not None else None
        else:
            named = os.environ.get("XDG_DATA_HOME", "")
            data = (
                Path(named)
                if named and not discover.in_flatpak()
                else Path.home() / ".local" / "share"
            )
        if data is not None:
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


def cura_resources(root: Path) -> Path:
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
        printer_model=cura_definition_id(path),
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
    except (OSError, configparser.Error, UnicodeDecodeError) as problem:
        # ``UnicodeDecodeError`` dazu: Eine Datei in fremder Kodierung riss
        # die Filamentsuche des Druckdialogs ab (Durchsicht 0.5.0).
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


def cura_definition_id(path: Path) -> str:
    """Aus ``abax_pri3.def.json`` wird ``abax_pri3``.

    ``Path.stem`` allein reicht nicht: Es bleibt ``abax_pri3.def`` stehen, und
    unter diesem Namen findet kein Qualitätsprofil seinen Drucker.
    """
    return path.stem.removesuffix(".def")


def _cura_literal(key: str, formula: str) -> Any:
    """Was Cura aus einer Formel ohne Rechnung liest, oder ``None``.

    Zwei Hersteller schreiben Konstanten als Formel: UltiMaker Method die
    Sperrflächen als Listenliteral, AnkerMake M5C die Form als
    ``rectangular`` — für Curas Auswerter ein unbekannter Name, der mit 0
    endet (``SettingFunction.__call__``), und 0 ist für ``BuildVolume`` ein
    Rechteck. Beides gilt, ohne dass etwas ausgeführt wird (Regel 10); jede
    andere Formel bleibt unbekannt.
    """
    text = formula.strip()
    if key == "machine_shape" and text == "rectangular":
        return text
    if key != "machine_disallowed_areas":
        return None
    try:
        areas = json.loads(text)
    except ValueError:
        return None
    if not isinstance(areas, list):
        return None
    for area in areas:
        if not isinstance(area, list):
            return None
        for point in area:
            if not (
                isinstance(point, list)
                and len(point) == 2
                and all(
                    isinstance(number, (int, float)) and not isinstance(number, bool)
                    for number in point
                )
            ):
                return None
    return areas


def _cura_definition_values(
    path: Path,
    roots: Sequence[Path],
    *,
    strict: bool = False,
    indexes: ProfileIndexes | None = None,
    documents: ProfileDocuments | None = None,
    overrides: Mapping[str, Any] | None = None,
    extruder_overrides: Sequence[Mapping[str, Any]] = (),
    resolve_jerk: bool = False,
    cura_raft_contact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Definitionsdaten und bekannte Jerk-Beziehungen; fremde Ausdrücke bleiben unbekannt."""
    indexes = _pass_indexes(indexes)
    index: dict[str, Path] = {}
    for folder in [*(cura_resources(root) / "definitions" for root in roots), path.parent]:
        index_key: tuple[Path, ProfileKind | None] = (folder, "machine")
        if index_key not in indexes:
            indexes[index_key] = {
                cura_definition_id(entry): entry for entry in sorted(folder.glob("*.def.json"))
            }
        index.update(indexes[index_key])

    def read(current: Path, active: frozenset[Path]) -> dict[str, dict[str, Any]]:
        if current in active or len(active) >= MAX_INHERITANCE:
            raise _incomplete_profile(path)
        loaded = _load(current, documents)
        if loaded is None:
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
    definitions = read(path, frozenset())
    if cura_raft_contact is not None:
        cura_raft_contact.clear()
    for key, properties in definitions.items():
        if cura_raft_contact is not None and key in {"raft_airgap", "layer_0_z_overlap"}:
            cura_raft_contact[key] = (
                overrides[key]
                if overrides is not None and key in overrides
                else properties.get("value", properties.get("default_value"))
            )
        if overrides is not None and key in overrides:
            values[key] = overrides[key]
            continue
        # Eine Formel überlagert auch einen vorhandenen default_value. Der
        # Default ist dann gerade nicht der Wert, den Cura berechnet.
        if "value" in properties:
            value = properties["value"]
            if isinstance(value, str) and re.fullmatch(
                r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value.strip()
            ):
                # Einige Hersteller schreiben Zahlen als Ausdruckstext.
                # Nur ein endliches Zahlenliteral gilt; gerechnet wird hier nicht.
                number = float(value)
                value = number if math.isfinite(number) else None
            elif isinstance(value, str) and (literal := _cura_literal(key, value)) is not None:
                value = literal
            elif isinstance(value, str):
                if strict and key in {
                    "machine_width",
                    "machine_depth",
                    "machine_height",
                    "machine_shape",
                    "machine_disallowed_areas",
                    "machine_nozzle_size",
                    "machine_extruder_count",
                }:
                    raise _incomplete_profile(path)
                continue
        else:
            value = properties.get("default_value")
        if value is not None:
            values[key] = value
    if overrides is not None:
        values.update(overrides)
        if cura_raft_contact is not None:
            cura_raft_contact.update(
                {
                    key: value
                    for key, value in overrides.items()
                    if key in {"raft_airgap", "layer_0_z_overlap"}
                }
            )
    if resolve_jerk:
        motion = []
        for train in extruder_overrides or ({},):
            selected = dict(overrides or {})
            for key, value in train.items():
                # Cura registriert die Vorgabe True. Explizit globale Werte
                # umgehen laut ExtruderStack auch alte Extruder-Restwerte.
                allowed = definitions.get(key, {}).get("settable_per_extruder", True)
                if not isinstance(allowed, bool):
                    raise _incomplete_profile(path)
                if allowed:
                    selected[key] = value
            motion.append(_cura_jerk_values(path, definitions, values | selected, selected))
        # Erst die wirksamen Rollen vergleichen: Bei ausgeschalteter Steuerung
        # sind unterschiedliche alte Rollenwerte keine Mehrdeutigkeit.
        if any(item != motion[0] for item in motion[1:]):
            raise _incomplete_profile(path)
        # Die strenge Übergabe erhält ausschließlich wirksame Rollen. Sonst
        # würden inaktive Rohwerte trotz der Prüfung wieder geschrieben.
        values = {
            key: value
            for key, value in values.items()
            if not (key.startswith("jerk_") or key.endswith("_jerk"))
        }
        values.update(motion[0])
    return values


def _cura_jerk_values(
    path: Path,
    definitions: Mapping[str, Mapping[str, Any]],
    values: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Belegte Jerk-Beziehungen als eigener Code, ohne native Formeln auszuführen.

    Nur die unten ausdrücklich zugeordneten Ausdrücke gelten. Eine fremde
    oder unvollständige Beziehung lässt die eingeschaltete Steuerung anhalten,
    statt CuraEngines abweichende Vorgabewerte wieder sichtbar zu machen.
    """
    if "jerk_enabled" not in definitions and "jerk_enabled" not in overrides:
        return {}

    def boolean(key: str) -> bool:
        value = str(values.get(key, "")).strip().casefold()
        if value not in {"true", "false"}:
            raise _incomplete_profile(path)
        return value == "true"

    enabled = boolean("jerk_enabled")
    result: dict[str, Any] = {"jerk_enabled": enabled}
    if not enabled:
        return result
    result["jerk_travel_enabled"] = boolean("jerk_travel_enabled")
    active: set[str] = set()

    def number(key: str) -> float:
        if key in result:
            return float(result[key])
        if key in active:
            raise _incomplete_profile(path)
        active.add(key)
        raw = overrides.get(key, definitions.get(key, {}).get("value", values.get(key)))
        value: Any = raw
        if isinstance(raw, str) and key not in overrides:
            if raw == CURA_JERK_LINKS.get(key):
                value = number(raw)
            elif key == "jerk_travel" and raw == "jerk_print * 2":
                value = number("jerk_print") * 2
            elif key == "jerk_travel" and raw == "jerk_print if magic_spiralize else 30":
                value = number("jerk_print") if boolean("magic_spiralize") else 30.0
            elif key == "jerk_travel_layer_0" and raw == "jerk_travel":
                value = number("jerk_travel")
            elif key == "jerk_travel_layer_0" and raw == "jerk_layer_0 * jerk_travel / jerk_print":
                printing = number("jerk_print")
                if printing <= 0.0:
                    raise _incomplete_profile(path)
                value = number("jerk_layer_0") * number("jerk_travel") / printing
            elif key in {"jerk_support_roof", "jerk_support_bottom"} and raw == (
                "extruderValue(support_roof_extruder_nr, 'jerk_support_interface')"
            ):
                # Erst bei genau einer Düse ist der Verweis unabhängig vom
                # Extruderindex eindeutig. Mehrere Züge bleiben unbekannt.
                if str(values.get("machine_extruder_count")) not in {"1", "1.0"}:
                    raise _incomplete_profile(path)
                value = number("jerk_support_interface")
        try:
            parsed = float(value)
        except (TypeError, ValueError, OverflowError) as problem:
            raise _incomplete_profile(path) from problem
        if isinstance(value, bool) or not math.isfinite(parsed) or parsed < 0.0:
            raise _incomplete_profile(path)
        result[key] = parsed
        active.remove(key)
        return parsed

    number("jerk_print")
    for key in definitions.keys() | overrides.keys():
        if (key.startswith("jerk_") or key.endswith("_jerk")) and not key.endswith("enabled"):
            if not result["jerk_travel_enabled"] and key in {
                "jerk_travel",
                "jerk_travel_layer_0",
            }:
                continue
            number(key)
    return result


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


#: Beide Trenner, die ein Pfad unter Windows tragen kann (:func:`_kind_of`).
_SEPARATORS: Final = re.compile(r"[\\/]")


def _kind_of(path: Path, root: Path) -> ProfileKind | None:
    """Maschine oder Prozess — abgelesen am Ordner, in dem die Datei liegt.

    Die Ablage ist zwischen den Herstellern nicht einheitlich, deshalb wird
    der ganze Pfad unterhalb der Wurzel abgesucht statt einer festen Tiefe.

    Was unter der Wurzel gefunden wurde, beginnt mit ihr als Zeichenkette;
    dann genügt ein Schnitt. ``relative_to`` kostete an ElegooSlicers
    24 000 Aufrufen je Profilsuche eine Sekunde (DRUCK-14).
    """
    text, base = str(path), str(root)
    parts: tuple[str, ...]
    if text.startswith(base) and text[len(base) : len(base) + 1] in (os.sep, "/"):
        parts = tuple(_SEPARATORS.split(text[len(base) + 1 :]))[:-1]
    else:
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


def _stated_nozzle(chain: Sequence[Mapping[str, Any]], flavour: SlicerFlavour) -> float:
    """Die Düse, die die Erbkette zuerst nennt — sonst die, mit der der Slicer
    dann rechnet (:data:`MACHINE_DEFAULTS`), wie bei der Druckererhebung."""
    stated = next((loaded for loaded in chain if "nozzle_diameter" in loaded), {})
    return _first_number(_machine_value(stated, "nozzle_diameter", flavour))


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
    users = user_roots(flavour, executable)
    roots.extend((folder, True) for folder in users)
    if installed is None:
        # Ein AppImage trägt seinen Bestand im Abbild, das nur während seines
        # Laufs eingehängt ist — unter Linux der Normalfall für Orca, Bambu,
        # Elegoo und Creality. Die Orca-Familie kopiert die Bündel der
        # eingerichteten Drucker nach ``system/`` neben ``user/``, und dort
        # stehen genau die Drucker des Kunden.
        for system in dict.fromkeys(folder.parent.parent / "system" for folder in users):
            if system.is_dir():
                roots.append((system, False))

    count = 0
    documents: ProfileDocuments = {}
    for root, from_user in roots:
        for path in _json_files(root):
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
            profile = _read(path, kind, from_user, documents)
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
        # Die Düse kann allein in einer Erbbasis stehen: OrcaSlicers „Rolohaun
        # Delta Flyer Refit 0.4 nozzle“ erbt sie vom Rook MK1 LDO. Gelesen als
        # 0 fand der Druckdialog keine Maschine zu ihrem Drucker (RM-524).
        unknown_nozzle = profile.kind == "machine" and not profile.nozzle > 0.0
        if not profile.inherits:
            if unknown_nozzle:
                found[index] = replace(profile, nozzle=_stated_nozzle((), flavour))
            continue
        if profile.compatible_printers and not unknown_nozzle:
            continue
        try:
            chain = _chain(profile.path, all_roots, indexes=indexes, documents=documents)
        except ExternalToolError as problem:
            _log.warning("skipping incomplete profile %s: %s", profile.name, problem)
            incomplete.add(index)
            continue
        if unknown_nozzle:
            profile = found[index] = replace(profile, nozzle=_stated_nozzle(chain, flavour))
        if profile.compatible_printers:
            continue
        for loaded in chain:
            compatibility = tuple(_strings(loaded.get("compatible_printers")))
            if compatibility:
                found[index] = replace(profile, compatible_printers=compatibility)
                break
    found = [profile for index, profile in enumerate(found) if index not in incomplete]
    # Die gelesenen Dateien gehen hier, nicht erst mit dem nächsten Aufräumen:
    # Die Erbkette hält sie über ihre rekursiven Hilfsfunktionen im Ring, und
    # am ElegooSlicer sind das 70 MiB, die sonst bis zum nächsten GC-Lauf
    # blieben.
    documents.clear()
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
        # Verwaltungsfelder, die ``ConfigBase::load_from_json`` nur als
        # Zeichenkette nimmt; Anycubics Profile tragen ``is_custom_defined``.
        "is_custom_defined",
        "url",
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


def _prusa_files(root: Path, cancelled: CancelToken | None = None) -> list[Path]:
    """Aktive Bündel und eigene Profile; Update-Downloads unter cache bleiben draußen."""
    return sorted(
        {
            *_checked_paths(root.glob("*.ini"), cancelled),
            *(
                path
                for directory in (*_PRUSA_KINDS, "vendor")
                for path in _checked_paths((root / directory).glob("*.ini"), cancelled)
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

    def __init__(
        self,
        roots: Sequence[Path],
        *,
        eager: bool = True,
        cancelled: CancelToken | None = None,
    ) -> None:
        self.roots = roots
        self.documents: dict[Path, configparser.ConfigParser] = {}
        self.entries: list[SlicerProfile] = []
        self.by_name: dict[tuple[ProfileKind, str], list[SlicerProfile]] = {}
        self.resolved: dict[tuple[Path, str], dict[str, Any]] = {}
        if not eager:
            return
        for root in roots:
            for path in _prusa_files(root, cancelled):
                _check_cancelled(cancelled)
                if len(self.documents) >= MAX_FILES:
                    return
                self.read(path, cancelled=cancelled)

    def find_parent(
        self, name: str, kind: ProfileKind, *, cancelled: CancelToken | None = None
    ) -> None:
        """Beim Einzelabruf nur die Bündel öffnen, die den Elternnamen tragen."""
        prefix = next(key for key, value in _PRUSA_KINDS.items() if value == kind)
        heading = f"[{prefix}:{name}]"
        for root in self.roots:
            for index, path in enumerate(_prusa_files(root, cancelled)):
                _check_cancelled(cancelled)
                if index >= MAX_FILES:
                    break
                if path in self.documents:
                    continue
                if path.parent.name == prefix and path.stem == name:
                    self.read(path, cancelled=cancelled)
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if heading in text.splitlines():
                    self.read(path, cancelled=cancelled)

    def read(self, path: Path, *, cancelled: CancelToken | None = None) -> None:
        """Ein Bündel oder eine kopflose eigene Einzeldatei lesen."""
        _check_cancelled(cancelled)
        if path in self.documents:
            return
        document = _read_prusa_ini(path)
        if document is None:
            return
        entries: list[SlicerProfile] = []
        own_kind = _PRUSA_KINDS.get(path.parent.name)
        if own_kind and document[_PRUSA_HEAD]:
            entries.append(
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
            _check_cancelled(cancelled)
            prefix, separator, name = section.partition(":")
            kind = _PRUSA_KINDS.get(prefix)
            if separator and kind:
                entries.append(
                    SlicerProfile(
                        path,
                        name,
                        kind,
                        section=section,
                        inherits=document[section].get("inherits", ""),
                    )
                )
        # Ein abgebrochenes Nachlesen darf keinen halben Namensindex im
        # geteilten Bestand hinterlassen. Der Abbruch gehört nur diesem Abruf.
        _check_cancelled(cancelled)
        self.documents[path] = document
        self.entries.extend(entries)
        for entry in entries:
            self.by_name.setdefault((entry.kind, entry.name), []).append(entry)

    def resolve(
        self,
        profile: SlicerProfile,
        active: frozenset[tuple[Path, str]] = frozenset(),
        *,
        cancelled: CancelToken | None = None,
    ) -> dict[str, Any]:
        """Innerhalb eines Bündels erben; eigene Dateien dürfen Herstellerbasen nutzen."""
        _check_cancelled(cancelled)
        key = (profile.path, profile.section)
        if key in active or len(active) >= MAX_INHERITANCE:
            raise _incomplete_profile(profile.path)
        if key in self.resolved:
            return self.resolved[key]
        self.read(profile.path, cancelled=cancelled)
        document = self.documents.get(profile.path)
        section = profile.section or _PRUSA_HEAD
        if document is None or not document.has_section(section):
            # Die Bestandsauflistung überspringt unlesbare Dateien. Hier
            # wurde dieses Profil ausdrücklich gewählt; fehlend ist nicht
            # dasselbe wie ein vorhandenes gültiges leeres Delta.
            raise _incomplete_profile(profile.path)
        raw = dict(document[section])
        values: dict[str, Any] = {}
        for name in _prusa_list(raw.get("inherits", "")):
            if profile.from_user:
                self.find_parent(name, profile.kind, cancelled=cancelled)
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
            values.update(self.resolve(parent, active | {key}, cancelled=cancelled))
        values.update({name: value for name, value in raw.items() if name != "inherits"})
        self.resolved[key] = values
        return values

    def vendor_of(
        self, profile: SlicerProfile, active: frozenset[tuple[Path, str]] = frozenset()
    ) -> str:
        """Der Hersteller eines Profils, wie PrusaSlicer ihn zuordnet.

        Ein Abschnitt eines Bündels gehört dessen Hersteller, benannt nach der
        Datei wie bei PrusaSlicer (``VendorProfile::id``). Ein eigenes Profil
        gehört dem Hersteller seines ersten Vorfahren, der einen hat
        (``get_preset_with_vendor_profile``). Leer bleibt es bei einem Bündel
        mit ``templates_profile = 1`` — Vorlagen passen zu jedem Hersteller —
        und bei eigenen Profilen ohne Herstellerbasis.
        """
        document = self.documents.get(profile.path)
        if document is None:
            return ""
        if document.has_section("vendor"):
            if document["vendor"].get("templates_profile", "").strip() == "1":
                return ""
            return profile.path.stem
        key = (profile.path, profile.section)
        section = profile.section or _PRUSA_HEAD
        if key in active or len(active) >= MAX_INHERITANCE or not document.has_section(section):
            return ""
        for name in _prusa_list(document[section].get("inherits", "")):
            for parent in self.by_name.get((profile.kind, name), ()):
                if (parent.path, parent.section) == key:
                    continue
                vendor = self.vendor_of(parent, active | {key})
                if vendor:
                    return vendor
        return ""


@dataclass(slots=True)
class _PrusaCache:
    """Ein gelesener Prusa-Bestand und woran er erkannt wird."""

    key: tuple[tuple[Path, ...], tuple[tuple[str, int, int], ...]]
    store: _PrusaStore
    profiles: list[SlicerProfile] | None = None


#: **Der zuletzt gelesene Prusa-Bestand.** PrusaResearch.ini allein trägt über
#: neuntausend Abschnitte; den Bestand zu lesen und jeden Abschnitt aufzulösen
#: kostet 1,5 Sekunden, ein Name über :func:`profile_by_name` 1,1 und die
#: Auflösung einer Kette 0,6 (gemessen 27.09.2026, PrusaSlicer 2.9.6). Die
#: Grundlage fragt bei jeder Profilwahl im Druckdialog nach Drucker, Prozess
#: und Filament — ungespeichert stand der Dialog dafür fünf Sekunden.
#:
#: Anders als :data:`ProfileIndexes` lebt dieser Speicher über einen Aufruf
#: hinaus, und das darf er nur, weil er vor jeder Antwort nachsieht: Jede
#: Bündeldatei geht mit Größe und Zeitstempel in seinen Schlüssel. Legt der
#: Kunde ein Profil an, benennt eines um oder aktualisiert PrusaSlicer seine
#: Bündel, passt der Schlüssel nicht mehr, und der Bestand wird neu gelesen.
_PRUSA_LOCK: Final = threading.RLock()
_prusa_cache: _PrusaCache | None = None


def _prusa_signature(
    roots: Sequence[Path], extra_file: Path | None = None
) -> tuple[tuple[str, int, int], ...]:
    """Woran ein Prusa-Bestand erkannt wird: jede Datei mit Größe und Zeitstempel."""
    signature: list[tuple[str, int, int]] = []
    paths = {path for root in roots for path in _prusa_files(root)}
    if extra_file is not None:
        # Die ausdrücklich gewählte Einzeldatei darf außerhalb des Bestands
        # liegen. Ihr Ordner wird dadurch keine weitere Suchwurzel.
        paths.add(extra_file)
    for path in sorted(paths):
        try:
            status = path.stat()
        except OSError:
            continue
        signature.append((str(path), status.st_mtime_ns, status.st_size))
    return tuple(signature)


def _prusa_store(
    roots: Sequence[Path], cancelled: CancelToken | None = None, *, extra_file: Path | None = None
) -> _PrusaCache:
    """Der gelesene Bestand zu diesen Wurzeln — aus dem Speicher, solange er stimmt."""
    global _prusa_cache
    _check_cancelled(cancelled)
    key = (tuple(roots), _prusa_signature(roots, extra_file))
    with _PRUSA_LOCK:
        _check_cancelled(cancelled)
        if _prusa_cache is not None and _prusa_cache.key == key:
            return _prusa_cache
    # Gelesen wird außerhalb der Sperre: Das dauert, und ein abgebrochener
    # Suchauftrag hinterlässt so keinen halben Bestand im Speicher.
    cache = _PrusaCache(key, _PrusaStore(roots, cancelled=cancelled))
    with _PRUSA_LOCK:
        _check_cancelled(cancelled)
        _prusa_cache = cache
    return cache


#: Die Werte eines Prusa-Druckers, die die Verträglichkeitsbedingungen der
#: Bündel lesen — gezählt über alle Bündel von PrusaSlicer 2.9.6 (27.09.2026).
#: ``num_extruders`` leitet der Auswerter aus ``nozzle_diameter`` ab.
PRUSA_CONDITION_KEYS: Final = (
    "printer_model",
    "printer_notes",
    "printer_variant",
    "printer_technology",
    "nozzle_diameter",
    "nozzle_high_flow",
    "single_extruder_multi_material",
)


def _prusa_profiles(
    executable: Path, wanted: frozenset[ProfileKind], cancelled: CancelToken | None = None
) -> list[SlicerProfile]:
    """Native Profile, mit aufgelöster Maschinenidentität und unsichtbaren Erbbasen.

    Die Liste gilt für alle drei Arten und wird mit dem Bestand gespeichert
    (:func:`_prusa_store`); gefiltert wird je Aufruf.
    """
    cache = _prusa_store(profile_roots("prusa", executable), cancelled)
    # Unter der Sperre, damit zwei Aufrufer den Bestand nicht zugleich
    # auflösen; ein Abbruch lässt die Liste leer statt halb.
    with _PRUSA_LOCK:
        _check_cancelled(cancelled)
        if cache.profiles is None:
            cache.profiles = _prusa_listing(cache.store, cancelled)
        listed = cache.profiles
    return [entry for entry in listed if entry.kind in wanted]


def _prusa_listing(store: _PrusaStore, cancelled: CancelToken | None) -> list[SlicerProfile]:
    """Alle wählbaren Profile eines gelesenen Bestands, je Art und Name eines."""
    found: dict[tuple[ProfileKind, str], SlicerProfile] = {}
    for entry in store.entries:
        _check_cancelled(cancelled)
        if entry.name.startswith("*") and entry.name.endswith("*"):
            continue
        try:
            values = store.resolve(entry, cancelled=cancelled)
        except ExternalToolError as problem:
            _log.warning("skipping incomplete Prusa profile %s: %s", entry.name, problem)
            continue
        if entry.kind == "machine" and values.get("printer_technology") == "SLA":
            continue
        model = str(values.get("printer_model", ""))
        section = f"printer_model:{model}"
        document = store.documents[entry.path]
        materials: tuple[str, ...] = ()
        if document.has_section(section):
            model = document[section].get("name", model)
            materials = tuple(
                name.strip()
                for name in document[section].get("default_materials", "").split(";")
                if name.strip()
            )
        profile = replace(
            entry,
            printer_model=model,
            nozzle=_first_number(
                str(_machine_value(values, "nozzle_diameter", "prusa")).split(",")[0]
            ),
            default_process=str(values.get("default_print_profile", "")),
            default_filament=next(
                iter(_prusa_list(str(values.get("default_filament_profile", "")))), ""
            ),
            filament_type=str(values.get("filament_type", "")),
            compatible_printers=tuple(_prusa_list(str(values.get("compatible_printers", "")))),
            condition=(
                str(values.get("compatible_printers_condition", "")).strip()
                if entry.kind != "machine"
                else ""
            ),
            variables=(
                tuple((key, str(values[key])) for key in PRUSA_CONDITION_KEYS if key in values)
                if entry.kind == "machine"
                else ()
            ),
            default_materials=materials if entry.kind == "machine" else (),
            vendor=store.vendor_of(entry),
        )
        key = (profile.kind, profile.name)
        if key not in found or profile.from_user or not found[key].from_user:
            found[key] = profile
    return list(found.values())


def identity(entry: SlicerProfile) -> str:
    """Woran eine Auswahl ein Profil wiedererkennt: der Pfad seiner Datei, bei
    einem Abschnitt eines Prusa-Bündels sein Name.

    Ein Bündel trägt tausende Profile in einer Datei, PrusaResearch.ini allein
    über neuntausend. Am Pfad erkannt, wäre jedes davon dasselbe, und die
    Auswahl zeigte den gewählten Drucker über dem ersten Abschnitt der Datei.
    Der Name ist dort eindeutig (:func:`_prusa_listing` führt je Art und Name
    eines), reist wie jeder Profilname in die Projektdatei (Regel 12), und
    :func:`app.core.export.handover.profile_source` löst ihn auf.
    """
    if entry.cura_instance is not None:
        return f"cura-instance:{entry.section}"
    if entry.section and entry.section != _PRUSA_HEAD:
        return entry.name
    return str(entry.path)


def profile_by_name(
    executable: Path, flavour: SlicerFlavour, name: str, kind: ProfileKind
) -> SlicerProfile | None:
    """Portable Identität auflösen; Prusa behält den Abschnitt neben dem Pfad."""
    matches = [
        entry
        for entry in find_profiles(executable, flavour, (kind,))
        if entry.name == name or identity(entry) == name
    ]
    choices = [entry for entry in matches if entry.from_user] or matches
    return choices[0] if len(choices) == 1 else None


def resolve_profile(
    profile: SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
    cancelled: CancelToken | None = None,
    strict: bool = False,
    documents: ProfileDocuments | None = None,
    cura_motion: bool = False,
    cura_raft_contact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Native Werte ausschreiben, ohne Formeln oder G-Code auszuführen.

    Prusa-Werte bleiben INI-serialisiert (auch ``\\n`` in G-Code), Cura und
    Orca behalten die Werttypen ihrer Dateien. Eine Prusa-Bündeldatei braucht
    zwingend die Abschnittsidentität aus :func:`profile_by_name`.
    ``strict`` lehnt fehlende Erbbasen und unbelegte Cura-Maschinenmaße ab;
    ``documents`` teilt gelesene Dateien innerhalb einer Erhebung.
    ``cura_motion`` prüft zusätzlich die gewählte Bewegungssteuerung vor der
    Übergabe. Unbekannte Bewegung nimmt der Druckerauswahl keine bekannten Maße.
    """
    _check_cancelled(cancelled)
    if profile.cura_instance is not None:
        folders = tuple(
            dict.fromkeys((*roots, profile.path.parent.parent, profile.cura_instance.parent.parent))
        )
        for entry, native in _cura_machine_instances(
            folders,
            indexes if indexes is not None else {},
            documents if documents is not None else {},
            resolve_jerk=cura_motion,
            cura_raft_contact=cura_raft_contact,
        ):
            if entry.cura_instance == profile.cura_instance and entry.section == profile.section:
                return native
        raise _incomplete_profile(profile.cura_instance)
    if profile.path.suffix == ".ini":
        store = _prusa_store(roots, cancelled, extra_file=profile.path).store
        # Unter der Sperre: Eine Datei außerhalb der Wurzeln liest der Bestand
        # beim Auflösen nach, und zwei Aufrufer dürfen ihn dabei nicht teilen.
        with _PRUSA_LOCK:
            return dict(store.resolve(profile, cancelled=cancelled))
    return resolve_values(
        profile.path,
        roots,
        indexes=indexes,
        cancelled=cancelled,
        strict=strict,
        documents=documents,
        cura_motion=cura_motion,
        cura_raft_contact=cura_raft_contact,
    )


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


def _names_in(
    root: Path,
    kind: ProfileKind | None,
    *,
    cancelled: CancelToken | None = None,
    documents: ProfileDocuments | None = None,
) -> dict[str, Path]:
    """Profilname → Datei für alles unter ``root`` — bei ``kind`` nur die
    Profile dieser Art, gemessen am Ordner unterhalb der Wurzel.

    Der Index läuft über den Profilnamen, nicht über den Dateinamen: darauf
    zeigt ``inherits``. Bei Elegoo sind beide zufällig gleich
    (`Elegoo PETG @base.json`), garantiert ist das nirgends — und wo es nicht
    gilt, bräche die Kette nach der ersten Datei ab, ohne dass etwas fehlend
    aussieht.
    """
    index: dict[str, Path] = {}
    for count, entry in enumerate(sorted(_checked_paths(root.rglob("*.json"), cancelled))):
        _check_cancelled(cancelled)
        if count >= MAX_FILES:
            break
        if kind is not None and _kind_of(entry, root) != kind:
            continue
        loaded = _load(entry, documents)
        if loaded is not None:
            index.setdefault(str(loaded.get("name", entry.stem)), entry)
    return index


def resolve_values(
    path: Path,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
    cancelled: CancelToken | None = None,
    strict: bool = False,
    documents: ProfileDocuments | None = None,
    cura_motion: bool = False,
    cura_raft_contact: dict[str, Any] | None = None,
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
    _check_cancelled(cancelled)
    if path.name.endswith(".def.json"):
        return _cura_definition_values(
            path,
            roots,
            strict=strict,
            indexes=indexes,
            documents=documents,
            resolve_jerk=cura_motion,
            cura_raft_contact=cura_raft_contact,
        )
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
            SlicerProfile(path, path.stem, kind, from_user=True),
            roots,
            indexes=indexes,
            cancelled=cancelled,
        )
    values: dict[str, Any] = {}
    # Wurzel zuerst, Spezielles gewinnt
    for loaded in reversed(
        _chain(
            path, roots, indexes=indexes, cancelled=cancelled, strict=strict, documents=documents
        )
    ):
        values.update({key: value for key, value in loaded.items() if key not in DESCRIBING_KEYS})
    return values


def binding(
    path: Path,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
    documents: ProfileDocuments | None = None,
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
    for loaded in _chain(path, roots, indexes=indexes, documents=documents):  # spezifisch zuerst
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
    cancelled: CancelToken | None = None,
    documents: ProfileDocuments | None = None,
    strict: bool = False,
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
    indexes = _pass_indexes(indexes)
    documents = _pass_documents(documents)

    def lookup(current: Path, name: str) -> Path | None:
        _check_cancelled(cancelled)
        family = _family(current)
        family_key = (family, None)
        if family_key not in indexes:
            indexes[family_key] = _names_in(family, None, cancelled=cancelled, documents=documents)
        local = indexes[family_key].get(name)
        if local is not None and local != current:
            return local
        for root in _store_roots(current, roots):
            key = (root, _kind_by_folder(current))
            if key not in indexes:
                indexes[key] = _names_in(root, key[1], cancelled=cancelled, documents=documents)
            found = indexes[key].get(name)
            if found is not None:
                return found
        return None

    def visit(current: Path, active: frozenset[Path], template: bool) -> list[dict[str, Any]]:
        _check_cancelled(cancelled)
        if current in active or len(active) >= MAX_INHERITANCE:
            if template:
                raise _incomplete_profile(path)
            return []
        loaded = _load(current, documents)
        if loaded is None:
            _log.debug("stopping at %s", current.name)
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
    return list(reversed(visit(path, frozenset(), strict)))


def _incomplete_profile(path: Path) -> ExternalToolError:
    """Eine nicht auflösbare Vorlage darf keinen generischen Ablauf liefern."""
    return ExternalToolError(
        tool=path.name,
        detail=_(
            "Das Slicer-Profil „{name}“ ist unvollständig. Prüfen Sie seine Vorlagen im Slicer.",
            name=_shown_name(path),
        ),
        suggestions=(CHECK_SLICER_PROFILE,),
    )


#: Curas doppelte Dateiendungen; ``Path.stem`` nähme nur die letzte ab.
_CURA_SUFFIXES: Final = (".def.json", ".global.cfg", ".extruder.cfg", ".inst.cfg")


def _shown_name(path: Path) -> str:
    """Der Profilname aus dem Dateinamen, ganz — auch mit Punkten darin.

    „Snapmaker 2.0 A350“ bleibt so stehen: Abgenommen wird nur die Endung,
    bei Cura die doppelte. Curas Stapeldateien tragen ihren Namen kodiert
    (``Snapmaker+2.0+A350.global.cfg``).
    """
    for suffix in _CURA_SUFFIXES:
        if path.name.endswith(suffix):
            name = path.name.removesuffix(suffix)
            return unquote_plus(name) if suffix.endswith(".cfg") else name
    return path.stem


def machines(profiles: list[SlicerProfile]) -> list[SlicerProfile]:
    return sorted(
        (entry for entry in profiles if entry.kind == "machine"), key=lambda entry: entry.name
    )


#: Übliche Düsen, wenn der Slicer für das gewählte Gerät keine Varianten kennt.
COMMON_NOZZLE_SIZES: Final[tuple[float, ...]] = (0.2, 0.4, 0.6, 0.8)


def machine_for_name(profiles: list[SlicerProfile], name: str) -> SlicerProfile | None:
    """Das Maschinenprofil, das der Slicer als aktiv meldet, sofern es eindeutig ist."""
    if not name:
        return None
    found = [
        entry
        for entry in machines(profiles)
        if entry.name == name or identity(entry) == name or entry.printer_id == name
    ]
    return found[0] if len(found) == 1 else None


def same_printer_model(first: SlicerProfile, second: SlicerProfile) -> bool:
    """Ob zwei Maschinenvarianten dasselbe Modell und denselben Hersteller führen.

    Das Modell steht im Modellfeld oder im Namen ohne Düse (:func:`model_name`):
    Bambu Studio führt „Creality K1 0.8 nozzle“ mit dem Modellfeld des K1 Max,
    und am K1 fehlte dann die 0,8. Nach dem Namen zählt nur, wer eine Düse im
    Namen trägt — sonst wären zwei gleich benannte Profile schon Geschwister.
    """
    first_vendor = machine_vendor(first)
    second_vendor = machine_vendor(second)
    if not (first_vendor and second_vendor and first_vendor.casefold() == second_vendor.casefold()):
        return False
    if (
        first.printer_model
        and second.printer_model
        and _printer_name(first.printer_model) == _printer_name(second.printer_model)
    ):
        return True
    first_model = model_name(first.name)
    second_model = model_name(second.name)
    return (
        first_model != first.name
        and second_model != second.name
        and _printer_name(first_model) == _printer_name(second_model)
    )


def _nozzle_is_a_value(entry: SlicerProfile) -> bool:
    """Ob die Düse an dieser Maschine ein Wert ist statt einer eigenen Profildatei.

    Cura führt eine Maschine als Definition oder eingerichtete Instanz und die
    Düse darin als ``machine_nozzle_size``; seine Düsenvarianten sind Zusätze,
    keine Maschinen. Die Übergabe schreibt Solidons Durchmesser darüber. Orca-
    und Prusa-Bestände führen dagegen je Düse ein eigenes Maschinenprofil.
    """
    return entry.cura_instance is not None or entry.path.name.endswith(".def.json")


def machine_vendor(entry: SlicerProfile) -> str:
    """Der belegte Hersteller des Maschinenprofils; eigene Profile bleiben offen."""
    return entry.vendor.strip() or ("" if entry.from_user else _vendor_of(entry.path, "machine"))


def nozzle_sizes_for_machine(
    profiles: list[SlicerProfile], machine: SlicerProfile | None
) -> tuple[float, ...]:
    """Die verschiedenen Düsengrößen dieses Slicer-Modells, sonst die üblichen.

    Die Maschine selbst ist die Quelle: Namen wie „0.4 High-Speed nozzle"
    dürfen nicht versehentlich ein zweites Maß ergeben, und ein fremdes Modell
    gehört nicht in dieselbe Auswahl. Ein einzelner Wert ist keine
    Variantenliste; dann bleibt die Auswahl bei den üblichen Größen.
    """
    if machine is None or not machine.printer_model:
        return COMMON_NOZZLE_SIZES
    values = sorted(
        entry.nozzle
        for entry in machines(profiles)
        if same_printer_model(entry, machine) and math.isfinite(entry.nozzle) and entry.nozzle > 0.0
    )
    unique: list[float] = []
    for value in values:
        if not any(math.isclose(value, known, rel_tol=0.0, abs_tol=1e-6) for known in unique):
            unique.append(value)
    return tuple(unique) if len(unique) > 1 else COMMON_NOZZLE_SIZES


#: So tief wird eine Erbkette verfolgt. Drei bis vier Stufen sind üblich; eine
#: Grenze schützt vor einem Kreis in einem selbst angelegten Profil.
MAX_INHERITANCE: Final = 12


def compatible_with(
    profile: SlicerProfile,
    known: dict[str, SlicerProfile],
    *,
    indexes: ProfileIndexes | None = None,
    documents: ProfileDocuments | None = None,
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
        return tuple(
            _strings(
                binding(profile.path, indexes=indexes, documents=documents).get(
                    "compatible_printers"
                )
            )
        )
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
    if machine.variables:
        # **PrusaSlicer bindet über Bedingungen**, nicht über Listen: Ohne sie
        # galten am MK4S 6740 von 6772 Filamenten als verträglich, und die
        # Suche stand 43 Sekunden (27.09.2026). Hier gibt es keinen Rückfall
        # auf „alle ohne Angabe" — ein Profil ohne Liste und ohne Bedingung
        # passt ohnehin zu jedem Drucker.
        values = dict(machine.variables)
        return sorted(
            (entry for entry in entries if _prusa_fits(entry, machine, values)),
            key=lambda entry: entry.name,
        )

    known = {entry.name: entry for entry in entries}
    # **Ein Index für alle Einträge dieser Art.** ``compatible_with`` löst je
    # Profil eine Erbkette auf; ohne geteilten Index liest jede davon die ganze
    # Ablage neu. Beim ElegooSlicer sind das 16 795 Dateien mal der Zahl der
    # Prozesse — der Qt-Hauptthread stand damit 49 Sekunden, und die Zeile
    # darunter zahlte es ein zweites Mal (Befund Robert, 09.09.2026).
    #
    # **Und ein Dokumentenspeicher dazu**: Der Index fand die Eltern, gelesen
    # wurden sie trotzdem je Kette neu. Gemessen an Roberts ElegooSlicer
    # (08.10.2026): 14 327 Lesungen von 1431 Dateien je Profilantwort des
    # Druckdialogs, „fdm_filament_common" allein 1136-mal, zusammen 2,5 s im
    # Qt-Hauptthread.
    indexes = _pass_indexes(indexes)
    documents = _pass_documents(None)
    if documents is None:
        documents = {}
    fitting = [
        entry
        for entry in entries
        if machine.name in compatible_with(entry, known, indexes=indexes, documents=documents)
    ]
    # Findet sich keine ausdrückliche Angabe, ist Zeigen besser als Verschweigen:
    # ein selbst angelegtes Profil ohne Verträglichkeitsliste soll wählbar sein.
    chosen = fitting or [
        entry
        for entry in entries
        if not compatible_with(entry, known, indexes=indexes, documents=documents)
    ]
    return sorted(chosen, key=lambda entry: entry.name)


def _prusa_fits(entry: SlicerProfile, machine: SlicerProfile, values: Mapping[str, str]) -> bool:
    """PrusaSlicers Regel: erst der Hersteller, dann gewinnt eine Liste, sonst
    die Bedingung, sonst passt es.

    **Der Hersteller zuerst** (``is_compatible_with_printer``, PrusaSlicer
    2.9.6): Ein Profil aus dem Bündel eines anderen Herstellers passt nie, auch
    ohne Liste und Bedingung. Ohne diese Prüfung standen am MK4S HF0.4 Prozesse
    von BIBO2, LulzBot, Trimaker und Zonestar zur Wahl und Sovols PLA unter den
    Filamenten (27.09.2026). Vorlagen und eigene Profile ohne Herstellerbasis
    tragen keinen (:attr:`SlicerProfile.vendor`) und gehen weiter nach
    Bedingung.

    Eine Bedingung, die sich nicht auswerten lässt, schließt das Profil aus
    (:class:`~app.core.export.prusa_conditions.ConditionError`): Eine Auswahl zu
    wenig lässt sich im Dialog erweitern, eine unpassende druckt falsch.
    """
    if entry.vendor and entry.vendor != machine.vendor:
        return False
    if entry.compatible_printers:
        return machine.name in entry.compatible_printers
    try:
        return prusa_conditions.holds(entry.condition, values)
    except prusa_conditions.ConditionError as problem:
        _log.debug("Prusa condition of %s not evaluated: %s", entry.name, problem)
        return False


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
    wanted = normalise_filament_type(material_type)
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
        if normalise_filament_type(type_of(entry, roots, indexes=indexes)) == wanted
    ]
    if not fitting:
        return None
    # **Das Filament des Herstellers vor dem kürzesten Namen.** Der kürzeste
    # Name ist die Grundausführung *innerhalb einer Marke* (PETG vor PETG
    # PRO) — über Marken hinweg ist er Zufall: Bis zum 27.09.2026 bekam ein
    # Bambu A1 „eSUN PLA+ @BBL A1" statt „Bambu PLA Basic @BBL A1" und ein
    # SV06 „FilAr PLA Oro". Seit das Herstellerprofil die Grundlage ist,
    # sind das Temperatur, Kühlung und Volumenstrom des ganzen Drucks. Zuerst
    # zählt deshalb, was die Maschine selbst vorwählt, dann die Marke der
    # Maschine.
    # Danach zählt, was das Druckermodell vorschlägt: Der MK4S erbt als
    # Standard das PLA des MK4, das laut eigener Bedingung nicht zu ihm passt,
    # und ohne diese Stufe gewann der kürzeste Name, „Generic PLA @SOVOL" aus
    # Sovols Bündel (27.09.2026). Die Orca-Familie führt die Liste im
    # Modellprofil neben der Maschine (RM-464).
    suggested = {name: rank for rank, name in enumerate(suggested_filaments(machine, roots))}
    # **Die Marke ist die Angabe des Filaments** (``filament_vendor``), nicht
    # der Herstellerordner: In ``BBL/filament/`` liegen addnorth, BETA und
    # eSUN neben Bambu, und alle zählten als Marke der Maschine. Ohne Vorschlag
    # des Modells gehen Generic und die Marke des Druckers jeder Fremdmarke
    # vor; erst dann entscheidet die Namenslänge (RM-464).
    # Innerhalb einer Stufe die schlichteste Ausführung: Wörter neben Marke und
    # Material („Kevlar“, „UV Resistant“, „HF“) machen eine Spule besonders,
    # und die Länge allein wählte am MK4 „Kimya ABS Kevlar“.
    # Je Eintrag, nicht je Datei: Ein Prusa-Bündel trägt alle Filamente in einer.
    brands = {id(entry): brand_of(entry, roots, indexes=indexes) for entry in fitting}
    return min(
        fitting,
        key=lambda entry: (
            not entry.from_user,
            entry.name != machine.default_filament,
            suggested.get(entry.name, len(suggested)),
            not _own_brand(brands[id(entry)], machine),
            _extra_words(entry.name, brands[id(entry)], wanted),
            len(entry.name),
            entry.name,
        ),
    )


def suggested_filaments(machine: SlicerProfile, roots: Sequence[Path] = ()) -> tuple[str, ...]:
    """Die Filamente, die das Druckermodell vorschlägt, in ihrer Reihenfolge.

    PrusaSlicer führt sie am Modell im Bündel (``SlicerProfile.default_materials``),
    die Orca-Familie im Modellprofil neben der Maschine (``"type":
    "machine_model"``), als eine Zeile mit Semikolons.
    """
    if machine.default_materials or machine.path.suffix != ".json" or not machine.printer_model:
        return machine.default_materials
    listed = machine_model(machine.path, machine.printer_model, tuple(roots)).get(
        "default_materials", ""
    )
    names = listed if isinstance(listed, list) else str(listed).split(";")
    return tuple(name.strip() for name in names if isinstance(name, str) and name.strip())


def brand_of(
    profile: SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    indexes: ProfileIndexes | None = None,
) -> str:
    """Die Marke eines Filamentprofils (``filament_vendor``), eigene oder geerbte."""
    return _first_string(
        resolve_profile(profile, roots, indexes=indexes).get("filament_vendor")
    ).strip()


def _own_brand(brand: str, machine: SlicerProfile) -> bool:
    """Generic oder die Marke des Druckers — keine Fremdmarke.

    Verglichen werden die Wörter der Marke mit denen von Maschinenname und
    Modell: „Bambu Lab“ gehört zum „Bambu Lab A1“, „Prusa Polymers“ zum
    „Original Prusa MK4S“, „Elegoo“ zum Centauri Carbon 2.
    """
    if not brand:
        return False
    own = _words(brand)
    if own[:1] == ["generic"]:
        return True
    machine_words = set(_words(machine.name, machine.printer_model, machine.vendor))
    # Das erste Wort, oder ein tragendes dahinter: „Made for Prusa“ ist Prusas
    # eigene Linie.
    return own[0] in machine_words or any(
        len(word) >= 4 and word in machine_words for word in own[1:]
    )


def _words(*texts: str) -> list[str]:
    """Die Wörter eines Namens, klein geschrieben."""
    return [word.casefold() for text in texts for word in re.split(r"[^\w]+", text) if word]


def _extra_words(name: str, brand: str, material: str) -> int:
    """Wie viele Wörter ein Filamentname neben Marke und Material trägt."""
    plain = set(_words(brand)) | set(_words(material))
    return sum(1 for word in _words(name.partition("@")[0]) if word not in plain)


def machine_model(
    machine_file: Path, model_name: str, roots: tuple[Path, ...] = ()
) -> dict[str, Any]:
    """Die Modelldatei zu einem Maschinenprofil der Orca-Familie — im
    Herstellerordner daneben, sonst irgendwo im Bestand.

    Eine eigene Vorlage liegt unter ``user/``, das Modell ihres Druckers beim
    Hersteller. Gesucht nur neben der Vorlage, fand Solidon für „Mein P1S" keine
    Standardplatte und riet die glatte (Review Stufe A+B, R4).
    """
    if not model_name:
        return {}
    beside = _machine_model_beside(machine_file, model_name)
    if beside:
        return beside
    for folder in roots:
        for candidate in sorted(folder.glob("*/machine/**/*.json")):
            if candidate.stem != model_name:
                continue
            loaded = _load(candidate)
            if (
                loaded is not None
                and loaded.get("type") == "machine_model"
                and loaded.get("name") == model_name
            ):
                return loaded
    return {}


def _machine_model_beside(machine_file: Path, model_name: str) -> dict[str, Any]:
    """Die Modelldatei im Maschinenordner neben dem Profil."""
    for parent in machine_file.parents:
        if parent.name.casefold() != "machine":
            continue
        for candidate in sorted(parent.glob("*.json")):
            loaded = _load(candidate)
            if (
                loaded is not None
                and loaded.get("type") == "machine_model"
                and loaded.get("name") == model_name
            ):
                return loaded
        break
    return {}


def _vendor_of(path: Path, kind: str) -> str:
    """Der Hersteller eines Profils: der Ordner über dem Ordner seiner Art, bei
    PrusaSlicer die Bündeldatei (``PrusaResearch``, ``Sovol``). Leer, wo es
    keinen gibt (eigene Profile)."""
    if path.suffix == ".ini":
        return path.stem
    parts = list(path.parts)
    if kind not in parts:
        return ""
    position = parts.index(kind)
    return parts[position - 1] if position else ""


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
    profiles: list[SlicerProfile], printer: PrinterProfile, *, source: str = ""
) -> tuple[SlicerProfile | None, SlicerProfile | None]:
    """Das Paar, das zu diesem Drucker gehört — Maschine und Prozess.

    Der Modellname trägt die Zuordnung, die Düse entscheidet zwischen den
    Varianten desselben Geräts. Trifft nichts, bleibt es leer: eine falsche
    Vorauswahl wäre schlimmer als keine, weil sie wie eine Entscheidung
    aussieht.

    Nennt der Drucker sein Profil in PrusaSlicers Bündel
    (``PrinterProfile.prusaslicer_printer``) und steht es im Bestand, gilt
    dieses. Die Namenssuche traf dort am MINI und XL die abgelösten Profile
    ohne Input Shaper und den SV06 gar nicht (27.09.2026).
    """
    all_machines = machines(profiles)
    native = [entry for entry in all_machines if entry.printer_id == printer.id]
    if not native and source:
        native = [
            entry for entry in all_machines if matches_saved_cura_printer(entry, printer, source)
        ]
    if (
        printer.id.startswith("slicer-cura-")
        and any(entry.printer_id.startswith("slicer-cura-") for entry in profiles)
        and not native
    ):
        return None, None
    named_in_bundle = [
        entry
        for entry in all_machines
        if printer.prusaslicer_printer and entry.name == printer.prusaslicer_printer
    ]
    defined_in_cura = [
        entry
        for entry in all_machines
        if printer.cura_definition
        and entry.printer_model == printer.cura_definition
        and entry.path.name.endswith(".def.json")
        and entry.cura_instance is None
    ]
    source_machine = machine_for_name(profiles, printer.title)
    source_family = (
        [
            entry
            for entry in all_machines
            if identity(entry) == identity(source_machine)
            or same_printer_model(entry, source_machine)
        ]
        if source_machine is not None
        else []
    )
    native_instance = next((entry for entry in native if entry.cura_instance is not None), None)
    # Nur die gespeicherte native Kennung darf eine exakte Cura-Definition
    # überstimmen. Ein Anzeigename ist änderbar und kann mit einer anderen
    # Maschine kollidieren.
    cura_instance = native_instance
    candidates = (
        [cura_instance]
        if cura_instance is not None
        else (
            native
            or named_in_bundle
            or defined_in_cura
            or source_family
            or [
                entry
                for entry in all_machines
                if _names_the_printer(entry.printer_model, printer.title)
                or _names_the_printer(entry.name, printer.title)
            ]
        )
    )
    if not candidates:
        return None, None
    # **Das Gerät selbst vor seinen Verwandten.** „Creality K1" beginnt auch
    # „Creality K1 Max" und „Creality K1_CFS-C"; wo eine Maschine genau dieses
    # Modell nennt, zählt nur sie.
    own_model = [
        entry
        for entry in candidates
        if entry.printer_model
        and _printer_name(entry.printer_model) == _printer_name(printer.title)
    ]
    candidates = own_model or candidates

    exact = [entry for entry in candidates if abs(entry.nozzle - printer.nozzle_diameter) < 1e-6]
    variable = any(_nozzle_is_a_value(entry) for entry in candidates)
    # **Eine festgelegte Variante mit anderer Düse meint ihre Schwester.** Ein
    # Drucker aus PrusaSlicers Bündel nennt seine Variante beim Namen
    # (``prusaslicer_printer``); stellt der Druckdialog die Düse um, liegt das
    # gemeinte Profil neben ihr. Bis dahin blieb die Wahl dann leer — am
    # CR-10 von 0,4 auf 0,6 wie an jedem zweiten Wechsel im Bestand.
    pinned = (native or named_in_bundle) if cura_instance is None else []
    reference = pinned[0] if len(pinned) == 1 else source_machine
    if pinned and reference is not None and not exact and not variable:
        sister = sister_variant(all_machines, reference, printer.nozzle_diameter)
        if sister is None:
            return None, None
        return sister, standard_process(processes(profiles, sister), sister, printer)
    if source_family and not exact and not variable:
        # Ein exakt erkanntes importiertes Profil belegt seine Gerätefamilie,
        # aber nicht, welche fremde Düse an diesem Gerät aufgeschraubt ist.
        # Ohne passende Variante bleibt die Auswahl leer statt am Nachbarmaß
        # weiterzurechnen. Das gilt nur, wo jede Düse ein eigenes
        # Maschinenprofil hat; an einer Cura-Maschine gibt es keine Variante
        # zu verfehlen (RM-329).
        return None, None
    # Bei gleicher Düse dieselbe Ausführung, sonst die Grundausführung
    # (:func:`variant_order`).
    chosen = min(exact or candidates, key=variant_order(reference, printer.nozzle_diameter))

    return chosen, standard_process(processes(profiles, chosen), chosen, printer)


def standard_process(
    fitting: Sequence[SlicerProfile], machine: SlicerProfile, printer: PrinterProfile
) -> SlicerProfile | None:
    """Der Standardprozess einer Maschine unter den passenden: der, den sie
    nennt (``default_print_profile``), sonst der, den ihr Hersteller Standard
    nennt (:func:`_standard_process`). Die Stufe „Standard" meint ihn, und die
    übrigen Stufen suchen von ihm aus (:func:`stage_process`).

    **Fehlt der genannte, gilt seine Schichthöhe.** Anycubics Kobra 4 0,8 nennt
    „0.40mm Standard @Anycubic Kobra X 0.8 nozzle“ — einen Prozess, der nicht
    zu ihm passt. Die Schichthöhe des Druckers (0,2 mm) traf keinen seiner
    Prozesse, und gedruckt wurde still mit Solidons Tabelle (Anycubic-Matrix,
    B3). Die Höhe im genannten Namen ist die Angabe des Herstellers; erst ohne
    sie gilt die des Druckers."""
    named = [entry for entry in fitting if entry.name == machine.default_process]
    if named:
        return named[0]
    stated = layer_in_name(machine.default_process)
    found = _standard_process(fitting, stated) if stated is not None else None
    return found or _standard_process(fitting, printer.layer_height)


#: Die Schichthöhe am Anfang eines Prozessnamens, wie alle Hersteller ihn
#: schreiben: „0.20mm Standard @…", „0.2mm Standard @…", „0.20mm SPEED @…".
_LAYER_IN_NAME: Final = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*mm\b", re.IGNORECASE)


def layer_in_name(name: str) -> float | None:
    """Die Schichthöhe am Anfang eines Prozessnamens — ``None``, wo keine steht."""
    found = _LAYER_IN_NAME.match(name)
    return float(found.group(1)) if found else None


#: Woran ein Hersteller im Namen sagt, welcher Stufe ein Prozess dient (Konzept
#: Herstellerprofil, Entscheidung I). Gezählt an den Beständen von
#: ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print und PrusaSlicer 2.9.6
#: (27.09.2026): „Fine", „High Quality", „DETAIL", „FastDetail"; „Draft",
#: „Extra Draft", „DRAFT"; „Strength", „STRUCTURAL". Die Reihenfolge ist der
#: Vorrang bei gleicher Schichthöhe — Bambus „0.12mm Fine" vor „0.12mm High
#: Quality". Creality Print nennt jeden Prozess „Standard"; dort findet sich
#: keiner, und die Stufe liegt über dem Standardprozess.
STAGE_WORDS: Final[dict[str, tuple[str, ...]]] = {
    "fine": ("fine", "detail", "quality"),
    "draft": ("draft",),
    "strong": ("strength", "structural"),
}

#: Wie weit „Belastbar" von der Schichthöhe des Standards abweichen darf, in
#: Millimetern. Die Hersteller legen die Stufe auf sie — Prusas „0.20mm
#: STRUCTURAL", Bambus „0.20mm Strength"; ein „0.25mm STRUCTURAL" ist eine
#: gröbere Wahl, keine belastbarere.
STRONG_LAYER_TOLERANCE: Final = 0.02


def names_stage(name: str, quality: QualityPreset) -> bool:
    """Nennt dieser Prozessname die Stufe (:data:`STAGE_WORDS`)?"""
    text = name.casefold()
    return any(word in text for word in STAGE_WORDS.get(quality, ()))


def stage_process(
    fitting: Sequence[SlicerProfile],
    standard: SlicerProfile,
    quality: QualityPreset,
    stage_layer: float,
) -> SlicerProfile | None:
    """Der Prozess des Herstellers für eine Stufe (Entscheidung I).

    „Standard" ist der Standardprozess der Maschine. „Fein", „Entwurf" und
    „Belastbar" sind der Prozess, dessen Name die Stufe nennt: Fein feiner als
    der Standard, Entwurf gröber, beide mit der Schichthöhe, die
    ``stage_layer`` — der von Solidons Stufe — am nächsten liegt; Belastbar bei
    der Schichthöhe des Standards. Mitgelieferte Profile gehen eigenen vor:
    Eine Kopie hat ihren eigenen Zweck und ist keine Stufe.

    Gemessen an den Abnahmedruckern (27.09.2026): Centauri Carbon 2 und P1S
    „0.12mm Fine", „0.28mm Extra Draft", „0.20mm Strength"; MK4S HF0.4 „0.10mm
    FAST DETAIL", „0.28mm DRAFT", „0.20mm STRUCTURAL".

    ``None``, wo keiner passt — dann bleibt der Standardprozess, und die Stufe
    liegt über ihm (``manufacturer.STAGE_PATHS``).
    """
    if quality == "standard":
        return standard
    words = STAGE_WORDS.get(quality, ())
    base = layer_in_name(standard.name)
    if not words or base is None:
        return None
    ranked: list[tuple[tuple[bool, float, int, int, str], SlicerProfile]] = []
    for entry in fitting:
        layer = layer_in_name(entry.name)
        if layer is None or entry.name == standard.name:
            continue
        text = entry.name.casefold()
        rank = next((index for index, word in enumerate(words) if word in text), None)
        if rank is None:
            continue
        if quality == "strong":
            distance = abs(layer - base)
            wrong_side = distance > STRONG_LAYER_TOLERANCE
        else:
            distance = abs(layer - stage_layer)
            wrong_side = layer > base - EPS_GEOM if quality == "fine" else layer < base + EPS_GEOM
        if not wrong_side:
            ranked.append(((entry.from_user, distance, rank, len(entry.name), entry.name), entry))
    return min(ranked, key=lambda item: item[0])[1] if ranked else None


def _standard_process(
    fitting: Sequence[SlicerProfile], layer_height: float
) -> SlicerProfile | None:
    """Der Standardprozess, wenn die Maschine keinen nennt, den es gibt.

    OrcaSlicers Ender-3 V3 nennt als Standard „0.20mm Standard @Creality
    Ender3 V3"; im Bestand 2.4.2 heißt er „…@Creality Ender-3 V3". Genommen
    wurde bis zum 27.09.2026 der erste passende Prozess im Ordner, und das war
    „0.12mm Fine" — eine andere Schichthöhe, als der Drucker vorgibt, und seit
    das Herstellerprofil die Grundlage ist, der ganze Druck.

    Gesucht wird deshalb, was ein Hersteller Standard nennt: die Schichthöhe
    ``layer_height`` und „Standard" im Namen, sonst die Schichthöhe allein.
    Findet sich nichts, bleibt es leer — der Druckdialog fragt, statt zu raten
    (Regel 21).
    """

    same = [
        entry
        for entry in fitting
        if (height := layer_in_name(entry.name)) is not None and abs(height - layer_height) < 1e-6
    ]
    standard = [entry for entry in same if "standard" in entry.name.casefold()]
    pool = standard or same
    if not pool:
        return None
    return min(pool, key=lambda entry: (not entry.from_user, len(entry.name), entry.name))


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
    # Das untere Ende der Lüfterkurve und ihre Schwelle. Ohne sie las Solidon
    # von Elegoo PLA @ECC2 nur die 100 % und schrieb sie an beide Enden — aus
    # 50 bis 100 % wurde fest 100 (Befund Robert, 23.09.2026).
    ("cooling.minimum_fan_speed", "fan_min_speed", float),
    ("cooling.fan_below_layer_time", "fan_cooling_layer_time", float),
    ("cooling.bridge_fan_speed", "overhang_fan_speed", float),
    ("cooling.disable_first_layers", "close_fan_the_first_x_layers", int),
    ("cooling.minimum_layer_time", "slow_down_layer_time", float),
    ("cooling.minimum_speed", "slow_down_min_speed", float),
    ("filament.density", "filament_density", float),
    ("filament.flow_ratio", "filament_flow_ratio", float),
    ("filament.max_flow", "filament_max_volumetric_speed", float),
    ("filament.diameter", "filament_diameter", float),
    ("retraction.length", "filament_retraction_length", float),
    ("retraction.speed", "filament_retraction_speed", float),
    ("retraction.z_hop", "filament_z_hop", float),
)

#: Anteile stehen im Profil als ganze Prozent, in Solidon als Bruch.
_AS_FRACTION: Final = frozenset(
    {"cooling.fan_speed", "cooling.minimum_fan_speed", "cooling.bridge_fan_speed"}
)


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


PRUSA_FILAMENT_READBACK: Final[tuple[tuple[str, str, type], ...]] = (
    ("temperature.nozzle", "temperature", int),
    ("temperature.nozzle_first_layer", "first_layer_temperature", int),
    ("temperature.bed", "bed_temperature", int),
    ("temperature.bed_first_layer", "first_layer_bed_temperature", int),
    ("temperature.chamber", "chamber_temperature", int),
    ("cooling.fan_speed", "max_fan_speed", float),
    ("cooling.minimum_fan_speed", "min_fan_speed", float),
    ("cooling.fan_below_layer_time", "fan_below_layer_time", float),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", float),
    ("cooling.disable_first_layers", "disable_fan_first_layers", int),
    ("cooling.minimum_layer_time", "slowdown_below_layer_time", float),
    ("cooling.minimum_speed", "min_print_speed", float),
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
    ("cooling.minimum_fan_speed", "cool_fan_speed_min", float),
    ("cooling.fan_below_layer_time", "cool_min_layer_time_fan_speed_max", float),
    ("filament.density", "material_density", float),
    ("filament.diameter", "material_diameter", float),
    ("retraction.length", "retraction_amount", float),
    ("retraction.speed", "retraction_speed", float),
)


@dataclass(frozen=True, slots=True)
class FilamentReadback:
    """Materialwerte und ob die aktive Düsenvariante sicher zugeordnet ist."""

    values: dict[str, float | int]
    variant_resolved: bool


def filament_readback(
    path: Path | SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    variant_name: str = "",
    extruder_id: str = "",
    program: str = "",
    nozzle_type: str = "",
) -> FilamentReadback:
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
    if _strings(resolved.get("filament_extruder_variant")):
        position = variant_index(
            resolved,
            "filament_extruder_variant",
            "filament_extruder_id",
            variant_name,
            extruder_id,
        )
        if position is None:
            return FilamentReadback({}, False)
        index, count = position
        resolved = {
            key: value[index] if isinstance(value, list) and len(value) == count else value
            for key, value in resolved.items()
        }
    readback = FILAMENT_READBACK
    if source.suffix == ".ini":
        readback = PRUSA_FILAMENT_READBACK
    elif source.name.endswith((".xml.fdm_material", ".inst.cfg")):
        readback = _CURA_FILAMENT_READBACK
    else:
        # ``nozzle_type`` der Maschine wählt die Düsenart-Fassung, die gedruckt wird.
        resolved = for_the_nozzle(normalise_chamber(resolved, program), program, nozzle_type)
        readback = tuple((path, native_key(key, program), kind) for path, key, kind in readback)
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
    return FilamentReadback(values, True)


def filament_values(
    path: Path | SlicerProfile,
    roots: Sequence[Path] = (),
    *,
    variant_name: str = "",
    extruder_id: str = "",
    program: str = "",
) -> dict[str, float | int]:
    """Liest bekannte Materialwerte, wenn die Profilvariante eindeutig ist."""
    return filament_readback(
        path, roots, variant_name=variant_name, extruder_id=extruder_id, program=program
    ).values
