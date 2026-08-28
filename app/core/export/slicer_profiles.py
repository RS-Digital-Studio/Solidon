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

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from app.core import discover
from app.core.export.slicer_keys import (
    SlicerFlavour,
    has_readable_profiles,
    has_user_profile_tree,
)
from app.core.log import get_logger
from app.core.types import PrinterProfile

_log = get_logger(__name__)

ProfileKind = Literal["machine", "process", "filament"]

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

    def title(self, own: str = "eigenes") -> str:
        """Der Name für die Auswahl. Ein selbst angelegtes Profil wird
        ausgeschrieben gekennzeichnet und nicht mit einem Zeichen: das liest
        sich vor, überlebt jeden Zeichensatz und braucht keine Legende.
        """
        return f"{self.name} ({own})" if self.from_user else self.name


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
    if not has_user_profile_tree(flavour):
        return []
    base = config_home(sys.platform)
    if not base:
        return []

    stem = executable.stem.replace("-", "").replace("_", "").casefold()
    found: list[Path] = []
    for folder in Path(base).iterdir() if Path(base).is_dir() else []:
        if not folder.is_dir() or folder.name.casefold() != stem:
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
    """
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


def printer_for(machine: str, known: Mapping[str, PrinterProfile]) -> str:
    """Welches Druckerprofil dieser Maschinenname meint — oder nichts.

    Der Name des Slicers trägt Düse und Zusätze („… 0.4 nozzle"), der von
    Solidon nicht; verglichen wird deshalb am Anfang. Trifft nichts, bleibt es
    leer: geraten wird hier so wenig wie in :func:`match`.
    """
    wanted = machine.casefold()
    hits = [
        identifier
        for identifier, profile in known.items()
        if profile.title and wanted.startswith(profile.title.casefold())
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
    except (TypeError, ValueError):
        return 0.0


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(entry) for entry in value]
    return [str(value)] if isinstance(value, str) else []


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

    Für ``prusa`` bleibt die Liste leer, und das ist kein Mangel: eine
    PrusaSlicer-``.ini`` läuft eigenständig, sobald Düse und Bettform darin
    stehen, und die schreibt Solidon selbst (§29).
    """
    if not has_readable_profiles(flavour):
        return []
    wanted = frozenset(kinds)

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
            # Version, die der Nutzer im Slicer selbst sieht.
            key = f"{profile.kind}:{profile.name}"
            if key in seen and not profile.from_user:
                continue
            seen.add(key)
            found.append(profile)

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
    """Der Ordner, unter dem die Vorfahren eines Profils zu finden sind.

    Gesucht wird nicht im ganzen Bestand: die Erbkette eines Filamentprofils
    bleibt innerhalb von ``filament/``, und dort sind es zweihundert Dateien
    statt elftausend.
    """
    for parent in path.parents:
        if parent.name.casefold() in PROFILE_DIRS:
            return parent
    return path.parent


def resolve_values(path: Path) -> dict[str, Any]:
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
    values: dict[str, Any] = {}
    for loaded in reversed(_chain(path)):  # Wurzel zuerst, Spezielles gewinnt
        values.update({key: value for key, value in loaded.items() if key not in DESCRIBING_KEYS})
    return values


def binding(path: Path) -> dict[str, Any]:
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
    for loaded in _chain(path):  # spezifisch zuerst
        for key in _BINDING:
            value = loaded.get(key)
            if key not in found and value:
                found[key] = value
    return found


def _chain(path: Path) -> list[dict[str, Any]]:
    """Die Profile der Erbkette, spezifisches zuerst.

    Roh, ohne Zusammenlegen und ohne Filter: Die beiden Auswertungen
    darüber brauchen Verschiedenes — :func:`resolve_values` die Werte
    ohne die beschreibenden Schlüssel, :func:`binding` ausgerechnet
    einen davon.
    """
    # Der Index läuft über den Profilnamen, nicht über den Dateinamen: darauf
    # zeigt ``inherits``. Bei Elegoo sind beide zufällig gleich
    # (`Elegoo PETG @base.json`), garantiert ist das nirgends — und wo es nicht
    # gilt, bräche die Kette nach der ersten Datei ab, ohne dass etwas fehlt
    # aussieht.
    index: dict[str, Path] = {}
    for entry in _family(path).rglob("*.json"):
        try:
            loaded = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict):
            index.setdefault(str(loaded.get("name", entry.stem)), entry)

    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current: Path | None = path
    for _step in range(MAX_INHERITANCE):
        if current is None or not current.is_file():
            break
        try:
            loaded = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, ValueError) as problem:
            _log.debug("stopping at %s: %s", current.name, problem)
            break
        if not isinstance(loaded, dict):
            break
        chain.append(loaded)
        parent = str(loaded.get("inherits", ""))
        if not parent or parent in seen:
            break
        seen.add(parent)
        current = index.get(parent)

    return chain


def machines(profiles: list[SlicerProfile]) -> list[SlicerProfile]:
    return sorted(
        (entry for entry in profiles if entry.kind == "machine"), key=lambda entry: entry.name
    )


#: So tief wird eine Erbkette verfolgt. Drei bis vier Stufen sind üblich; eine
#: Grenze schützt vor einem Kreis in einem selbst angelegten Profil.
MAX_INHERITANCE: Final = 12


def compatible_with(profile: SlicerProfile, known: dict[str, SlicerProfile]) -> tuple[str, ...]:
    """Für welche Drucker dieses Profil gilt — die eigene Angabe oder die
    geerbte.

    Nur ein Profil je Familie trägt die Liste wirklich; seine Geschwister
    erben sie über ``inherits``. Wer nur das eigene Feld liest, findet für
    einen Drucker genau ein Prozessprofil und hält alle anderen für
    unverträglich.
    """
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
    profiles: list[SlicerProfile], machine: SlicerProfile | None, kind: str
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
    fitting = [entry for entry in entries if machine.name in compatible_with(entry, known)]
    # Findet sich keine ausdrückliche Angabe, ist Zeigen besser als Verschweigen:
    # ein selbst angelegtes Profil ohne Verträglichkeitsliste soll wählbar sein.
    chosen = fitting or [entry for entry in entries if not compatible_with(entry, known)]
    return sorted(chosen, key=lambda entry: entry.name)


def processes(
    profiles: list[SlicerProfile], machine: SlicerProfile | None = None
) -> list[SlicerProfile]:
    """Die Prozessprofile, die zu diesem Drucker passen."""
    return _of_kind(profiles, machine, "process")


def filaments(
    profiles: list[SlicerProfile], machine: SlicerProfile | None = None
) -> list[SlicerProfile]:
    """Die Filamentprofile, die zu diesem Drucker passen."""
    return _of_kind(profiles, machine, "filament")


def match_filament(
    profiles: list[SlicerProfile], machine: SlicerProfile | None, material_type: str
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
    fitting = [
        entry for entry in filaments(profiles, machine) if type_of(entry).casefold() == wanted
    ]
    if not fitting:
        return None
    return min(fitting, key=lambda entry: (not entry.from_user, len(entry.name), entry.name))


def type_of(profile: SlicerProfile) -> str:
    """Welches Material dieses Filamentprofil meint — eigene Angabe oder geerbte."""
    if profile.filament_type:
        return profile.filament_type
    return _first_string(resolve_values(profile.path).get("filament_type"))


def match(
    profiles: list[SlicerProfile], printer: PrinterProfile
) -> tuple[SlicerProfile | None, SlicerProfile | None]:
    """Das Paar, das zu diesem Drucker gehört — Maschine und Prozess.

    Der Modellname trägt die Zuordnung, die Düse entscheidet zwischen den
    Varianten desselben Geräts. Trifft nichts, bleibt es leer: eine falsche
    Vorauswahl wäre schlimmer als keine, weil sie wie eine Entscheidung
    aussieht.
    """
    wanted = printer.title.casefold()
    candidates = [
        entry
        for entry in machines(profiles)
        if entry.printer_model.casefold() == wanted or entry.name.casefold().startswith(wanted)
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


def machine_values(path: Path) -> dict[str, Any]:
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
    """
    resolved = resolve_values(path)
    return {key: resolved[key] for key in MACHINE_READBACK if key in resolved}


def filament_values(path: Path) -> dict[str, float | int]:
    """Was dieses Filamentprofil über sein Material sagt (§29).

    Die Erbkette wird aufgelöst — ein Profil bei Elegoo setzt selbst drei Werte
    und erbt fünfzig. Zurück kommen Solidon-Pfade, wie sie
    :func:`app.core.knowledge.print_settings.with_path` versteht.

    Was das Profil nicht nennt, fehlt auch hier: ein Wert, den niemand gesetzt
    hat, ist keine Angabe des Herstellers, und ihn zu erfinden wäre schlimmer
    als ihn wegzulassen.
    """
    resolved = resolve_values(path)
    values: dict[str, float | int] = {}
    for solidon, orca, kind in FILAMENT_READBACK:
        raw = resolved.get(orca)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw is None or raw == "" or raw == "nil":
            continue
        text = str(raw).strip().rstrip("%")
        try:
            number = float(text)
        except ValueError:
            continue
        if solidon in _AS_FRACTION:
            number /= 100.0
        values[solidon] = kind(number)
    return values
