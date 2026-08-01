"""Die Profile finden, die ein installierter Slicer mitbringt (Bauplan §29).

Formwerk schreibt die Druckeinstellungen, aber nicht das Maschinenwissen:
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from app.core.export.slicer_keys import SlicerFlavour
from app.core.log import get_logger
from app.core.types import PrinterProfile

_log = get_logger(__name__)

ProfileKind = Literal["machine", "process"]

#: Wie viele Dateien höchstens gelesen werden. Der ausgelieferte Bestand eines
#: Slicers umfasst einige tausend Profile über alle Hersteller; eine Zahl weit
#: darüber heißt, dass hier der falsche Ordner durchsucht wird.
MAX_FILES: Final = 20_000

#: Gesucht wird nur unter diesen Ordnernamen. Der Bestand von ElegooSlicer hat
#: elftausend JSON-Dateien, wovon viertausend Profile sind — der Rest sind
#: Filamente, Modelle und Beschreibungen, und jede davon zu öffnen kostet
#: Sekunden, die der Dialog nicht hat.
PROFILE_DIRS: Final[dict[str, ProfileKind]] = {"machine": "machine", "process": "process"}


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
            if candidate.is_dir():
                return candidate
    return None


def user_roots(flavour: SlicerFlavour, executable: Path) -> list[Path]:
    """Wo die selbst angelegten Profile liegen.

    Die Orca-Familie legt sie unter ``<Konfiguration>/<Programm>/user/<Konto>/``
    ab. Der Programmname ist der der ausführbaren Datei, ohne Bindestriche —
    ``elegoo-slicer.exe`` schreibt nach ``ElegooSlicer``.
    """
    if flavour != "orca":
        return []
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if not base:
        home = Path.home() / ".config"
        base = str(home) if home.is_dir() else ""
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
        from_user=from_user or own,
        inherits=str(loaded.get("inherits", "")),
    )


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


def find_profiles(executable: Path, flavour: SlicerFlavour) -> list[SlicerProfile]:
    """Alle benutzbaren Profile dieses Slicers, mitgelieferte und eigene.

    Für ``prusa`` bleibt die Liste leer, und das ist kein Mangel: eine
    PrusaSlicer-``.ini`` läuft eigenständig, sobald Düse und Bettform darin
    stehen, und die schreibt Formwerk selbst (§29).
    """
    if flavour == "prusa":
        return []

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
            if kind is None:
                continue
            count += 1
            if count > MAX_FILES:
                _log.warning("stopped after %d profile files below %s", MAX_FILES, root)
                break
            profile = _read(path, kind, from_user)
            if profile is None:
                continue
            # Eigene schlagen mitgelieferte gleichen Namens — sie sind die
            # Fassung, die der Nutzer im Slicer selbst sieht.
            key = f"{profile.kind}:{profile.name}"
            if key in seen and not profile.from_user:
                continue
            seen.add(key)
            found.append(profile)

    _log.info("found %d slicer profiles", len(found))
    return found


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


def processes(
    profiles: list[SlicerProfile], machine: SlicerProfile | None = None
) -> list[SlicerProfile]:
    """Die Prozessprofile, die zu diesem Drucker passen.

    Ohne Maschine alle. Mit Maschine nur die verträglichen — sonst führt die
    Liste genau in den Abbruch, den sie verhindern soll, und zwar unter
    zweitausend Einträgen.
    """
    entries = [entry for entry in profiles if entry.kind == "process"]
    if machine is None:
        return sorted(entries, key=lambda entry: entry.name)

    known = {entry.name: entry for entry in entries}
    fitting = [entry for entry in entries if machine.name in compatible_with(entry, known)]
    # Findet sich keine ausdrückliche Angabe, ist Zeigen besser als Verschweigen:
    # ein selbst angelegtes Profil ohne Verträglichkeitsliste soll wählbar sein.
    chosen = fitting or [entry for entry in entries if not compatible_with(entry, known)]
    return sorted(chosen, key=lambda entry: entry.name)


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
