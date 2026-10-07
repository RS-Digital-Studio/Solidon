"""Aktualisiert und deinstalliert das Windows-Setup wie ein Kunde (RM-055).

Der Schritt nach dem Erststart im Installer-Workflow
(``.github/workflows/windows-signed-installer.yml``). Er beginnt mit der frisch
installierten neuen Version, die der Schritt davor gestartet hat, und prüft
dann der Reihe nach:

1. **Deinstallieren** der frischen Installation: Programmordner, Eintrag unter
   *Apps*, Startmenü und Dateizuordnung sind danach weg.
2. **Die veröffentlichte Vorversion** aus ``website/version.json`` — die Datei,
   die Kunden heute haben, geholt über ihre Adresse und nur nach passender
   Größe und Prüfsumme gestartet — still installieren, wie ein Kunde mit den
   Vorgaben.
3. **Eigene Daten anlegen**: ein eigener Baustein, eine Einstellung, ein
   Profil und ein Filamentlager in genau den Ordnern, die die Anwendung
   benutzt (``app.core.paths``).
4. **Aktualisieren** mit den Schaltern, mit denen die Anwendung ihr eigenes
   Update startet (``updates.SETUP_ARGUMENTS``): dieselbe Stelle, die neue
   Version im Eintrag und im Starttest, und die Anwendung startet danach
   von selbst wieder — so verlangt es ``/RESTARTAPP=1``. Diese Instanz wird
   beendet; danach der Starttest (``check_frozen_start.py``).
5. **Deinstallieren** der aktualisierten Installation wie in 1.

Die eigenen Daten aus 3 müssen nach dem Update **und** nach der Deinstallation
Byte für Byte da sein: Ein Update darf keinen selbst angelegten Baustein
kosten, eine Deinstallation auch nicht (Frage Robert, 06.10.2026). Nach jeder
Installation muss alles da sein, was die Restprüfung sucht — sonst prüfte sie
nach der Deinstallation ins Leere. Ohne Versionssprung zwischen
veröffentlichter und neuer Version gibt es kein Update zu prüfen; das ist rot.

Aufruf::

    python tools/check_windows_update.py --setup <neues Setup> --work <Arbeitsordner>

Nur Standardbibliothek und die Module ``app.branding``, ``app.core.paths`` und
``app.core.http``, die selbst nur sie laden: Der Installer-Workflow installiert
die Abhängigkeiten der Anwendung nicht in jedem Lauf.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.branding import (  # noqa: E402
    APP_ID,
    APP_NAME,
    APP_VERSION,
    PART_FILE_SUFFIX,
    PROJECT_SUFFIX,
)
from app.core import paths  # noqa: E402
from app.core.http import apply_header_deadline, deadline_after, read_limited  # noqa: E402

#: Wo Inno Setup eine Installation für den angemeldeten Nutzer einträgt.
UNINSTALL_KEY: Final = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"

#: Die eigenen Schlüssel der Dateizuordnung (``packaging/solidon3d.iss``,
#: ``uninsdeletekey``); unter der Endung selbst stehen auch fremde Einträge.
#: Der Eintrag unter ``Applications`` hält die Anwendung im Dialog „Öffnen mit"
#: und entsteht auch ohne die Aufgabe *Dateizuordnung*.
ASSOCIATION_KEYS: Final = (
    rf"Software\Classes\{APP_ID}.project",
    rf"Software\Classes\{APP_ID}.part",
    rf"Software\Classes\Applications\{APP_NAME}.exe",
)

#: Die Werte, die das Setup unter der Endung der Bausteindatei setzt.
PART_SUFFIX_KEY: Final = rf"Software\Classes\{PART_FILE_SUFFIX}"

#: Schlüssel, die auch anderen Programmen gehören können: Das Setup nimmt
#: beim Deinstallieren nur die eigenen Werte und danach den Schlüssel, wenn er
#: leer ist (``uninsdeletekeyifempty``). Auf dem frischen Runner ist er es.
EMPTIED_KEYS: Final = (
    rf"Software\Classes\{PROJECT_SUFFIX}",
    rf"Software\Classes\{PROJECT_SUFFIX}\OpenWithProgids",
    rf"Software\Classes\{PART_FILE_SUFFIX}\OpenWithProgids",
    PART_SUFFIX_KEY,
)

#: Wie lange das Holen der Vorversion insgesamt dauern darf, und wie lange
#: eine einzelne Leseoperation, in Sekunden.
DOWNLOAD_SECONDS: Final = 900.0
READ_SECONDS: Final = 60.0

#: Wie lange ein Setup oder die Deinstallation höchstens rechnet, in Sekunden.
#: Der Runner prüft jede neue DLL mit dem Virenscanner.
SETUP_SECONDS: Final = 600.0

#: Wie lange die Anwendung nach dem Update höchstens braucht, um wieder da zu sein.
RESTART_SECONDS: Final = 120.0

#: Die Deinstallation kopiert sich nach ``%TEMP%`` und kehrt sofort zurück;
#: so lange wird auf ihr Ende gewartet, in Sekunden.
UNINSTALL_SECONDS: Final = 300.0

#: Die Schalter einer stillen Erstinstallation, wie ein Kunde mit den Vorgaben.
FIRST_INSTALL_ARGUMENTS: Final = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER")

#: Die Schalter der Deinstallation.
UNINSTALL_ARGUMENTS: Final = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")


class UpdateCheckError(RuntimeError):
    """Ein Schritt des Update-Wegs ist rot; die Meldung sagt, welcher und was fehlt."""


def setup_arguments(source: Path = ROOT / "app" / "core" / "updates.py") -> tuple[str, ...]:
    """``updates.SETUP_ARGUMENTS``, aus dem Quelltext gelesen statt importiert.

    Eine Quelle: Die Anwendung startet ihr Update mit genau diesen Schaltern,
    und genau diese prüft der Schritt. Importiert wird das Modul nicht, weil es
    die halbe Anwendung nachlädt.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        if isinstance(node.target, ast.Name) and node.target.id == "SETUP_ARGUMENTS":
            value = ast.literal_eval(node.value)
            if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
                return value
    raise UpdateCheckError(f"SETUP_ARGUMENTS fehlt in {source}.")


@dataclass(frozen=True, slots=True)
class Published:
    """Die veröffentlichte Windows-Version, wie ``website/version.json`` sie nennt."""

    version: str
    url: str
    size: int
    sha256: str


def published(path: Path = ROOT / "website" / "version.json") -> Published:
    """Version, Adresse, Größe und Prüfsumme des veröffentlichten Setups."""
    data = json.loads(path.read_text(encoding="utf-8"))
    package = data["packages"]["windows"]
    return Published(
        version=str(data["version"]),
        url=str(package["url"]),
        size=int(package["size"]),
        sha256=str(package["sha256"]).lower(),
    )


def fetch(release: Published, target: Path, opener: Callable[[str], bytes] | None = None) -> Path:
    """Das veröffentlichte Setup holen; gestartet wird es nur bei passender Größe und Prüfsumme."""
    payload = opener(release.url) if opener is not None else _download(release.url, release.size)
    if len(payload) != release.size:
        raise UpdateCheckError(
            f"Die Vorversion {release.version} hat {len(payload)} statt {release.size} Byte."
        )
    digest = hashlib.sha256(payload).hexdigest()
    if digest != release.sha256:
        raise UpdateCheckError(f"Die Vorversion {release.version} hat eine andere Prüfsumme.")
    target.write_bytes(payload)
    return target


def _download(url: str, size: int) -> bytes:
    """Höchstens ``size`` Byte, mit Frist über Kopfzeilen und Rumpf (``app.core.http``)."""
    deadline = deadline_after(DOWNLOAD_SECONDS)
    opener = urllib.request.build_opener()
    apply_header_deadline(opener, deadline)
    with opener.open(url, timeout=READ_SECONDS) as response:
        return read_limited(response, limit=size, deadline=deadline)


def own_files() -> dict[Path, bytes]:
    """Was ein Kunde selbst angelegt hat, je Datei mit Inhalt — als Probe, nicht als Format.

    Die Orte kommen aus ``app.core.paths``, dieselben, die die Anwendung
    benutzt: eigene Bausteine, Profile, Einstellungen; das Filamentlager liegt
    neben ``filaments.json`` im Einstellungsordner. Die Anwendung liest die
    Proben nicht zwingend; geprüft wird, dass ein Setup sie weder löscht noch
    ändert. Der Name sagt, wofür jede steht.
    """
    stamp = f"Probe RM-055, {APP_VERSION}\n".encode()
    config = paths.user_config_dir()
    return {
        paths.user_parts_dir() / f"eigener-baustein{PART_FILE_SUFFIX}": b"eigener Baustein\n"
        + stamp,
        config / "settings-probe.json": b'{"probe": "Einstellung"}\n',
        paths.user_profiles_dir() / "eigenes-profil.json": b'{"probe": "Profil"}\n',
        config / "filaments-probe.json": b'{"probe": "Filamentlager"}\n' + stamp,
    }


def plant(files: Mapping[Path, bytes]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def missing_or_changed(files: Mapping[Path, bytes]) -> list[str]:
    """Die eigenen Dateien, die fehlen oder nicht mehr dieselben Bytes tragen."""
    lost = []
    for path, content in files.items():
        if not path.is_file():
            lost.append(f"{path} fehlt")
        elif path.read_bytes() != content:
            lost.append(f"{path} ist verändert")
    return lost


#: Ein Registerleser: Wert ``name`` unter ``key`` in HKCU, oder ``None``, wenn
#: Schlüssel oder Wert fehlen; mit ``name=None`` nur die Frage, ob der Schlüssel da ist.
Registry = Callable[[str, str | None], str | None]


def current_user_registry(
    key: str, name: str | None
) -> str | None:  # pragma: no cover — nur Windows
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            if name is None:
                return ""
            value, _kind = winreg.QueryValueEx(handle, name)
            return str(value)
    except FileNotFoundError:
        return None


@dataclass(frozen=True, slots=True)
class Installed:
    """Was der Eintrag unter *Apps* über eine Installation sagt."""

    version: str
    location: Path
    uninstaller: Path


def installed(registry: Registry) -> Installed | None:
    if registry(UNINSTALL_KEY, None) is None:
        return None
    version = registry(UNINSTALL_KEY, "DisplayVersion") or ""
    location = registry(UNINSTALL_KEY, "InstallLocation") or ""
    uninstaller = (registry(UNINSTALL_KEY, "UninstallString") or "").strip().strip('"')
    return Installed(version=version, location=Path(location), uninstaller=Path(uninstaller))


def traces(
    location: Path,
    registry: Registry,
    start_menu: Path,
    *,
    exists: Callable[[Path], bool] = Path.exists,
) -> dict[str, bool]:
    """Alles, was eine Installation anlegt und eine Deinstallation entfernt — je Spur: da?

    Eine Liste für beide Fragen: Nach einer Installation muss jede Spur da
    sein, nach der Deinstallation keine. Fehlte eine schon nach der
    Installation, wäre die Prüfung auf Reste für sie stumm grün.
    """
    found = {
        f"Programmordner {location}": exists(location),
        f"Eintrag unter Apps ({UNINSTALL_KEY})": registry(UNINSTALL_KEY, None) is not None,
    }
    for key in ASSOCIATION_KEYS:
        found[f"Dateizuordnung {key}"] = registry(key, None) is not None
    for suffix, kind in ((PROJECT_SUFFIX, "project"), (PART_FILE_SUFFIX, "part")):
        found[f"Öffnen-mit-Eintrag unter {suffix}"] = (
            registry(rf"Software\Classes\{suffix}\OpenWithProgids", f"{APP_ID}.{kind}") is not None
        )
    found[f"Zuordnung der Endung {PART_FILE_SUFFIX}"] = (
        registry(PART_SUFFIX_KEY, "") == f"{APP_ID}.part"
    )
    found[f"Inhaltstyp der Endung {PART_FILE_SUFFIX}"] = (
        registry(PART_SUFFIX_KEY, "Content Type") is not None
    )
    for key in EMPTIED_KEYS:
        found[f"Schlüssel {key}"] = registry(key, None) is not None
    shortcut = start_menu / f"{APP_NAME}.lnk"
    found[f"Startmenü-Eintrag {shortcut}"] = exists(shortcut)
    return found


def leftovers(
    location: Path,
    registry: Registry,
    start_menu: Path,
    *,
    exists: Callable[[Path], bool] = Path.exists,
) -> list[str]:
    """Was eine Deinstallation stehen ließ, das sie hätte entfernen müssen."""
    return [
        name
        for name, present in traces(location, registry, start_menu, exists=exists).items()
        if present
    ]


def absent(
    location: Path,
    registry: Registry,
    start_menu: Path,
    *,
    exists: Callable[[Path], bool] = Path.exists,
) -> list[str]:
    """Was nach einer Installation fehlt — eine Spur, nach der die Restprüfung umsonst sähe."""
    return [
        name
        for name, present in traces(location, registry, start_menu, exists=exists).items()
        if not present
    ]


def _run(command: Sequence[str], seconds: float) -> int:
    finished = subprocess.run(list(command), timeout=seconds, check=False)
    return finished.returncode


def _wait_until(condition: Callable[[], bool], seconds: float, *, step: float = 1.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(step)
    return condition()


def _running_from(folder: Path) -> list[int]:  # pragma: no cover — nur Windows
    """Prozesse, deren Programm im Ordner ``folder`` liegt.

    Der Ordner geht über eine Umgebungsvariable hinein, nicht in den Text des
    Skripts — ein Apostroph im Pfad bräche sonst den String; und er endet mit
    dem Trenner, damit ``…\\Solidon3D-alt`` nicht als ``…\\Solidon3D`` zählt.
    """
    script = (
        "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and "
        "$_.ExecutablePath.StartsWith($env:SOLIDON_PROBE_FOLDER, "
        "[StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { $_.ProcessId }"
    )
    prefix = str(folder).rstrip("\\/") + "\\"
    output = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "SOLIDON_PROBE_FOLDER": prefix},
    ).stdout
    return [int(line) for line in output.split() if line.strip().isdigit()]


def uninstall(registry: Registry, start_menu: Path) -> None:  # pragma: no cover — nur Windows
    """Die eingetragene Installation still entfernen und auf Reste prüfen."""
    present = installed(registry)
    if present is None:
        raise UpdateCheckError("Es ist keine Installation eingetragen, die sich entfernen ließe.")
    code = _run([str(present.uninstaller), *UNINSTALL_ARGUMENTS], SETUP_SECONDS)
    if code != 0:
        raise UpdateCheckError(f"Die Deinstallation endete mit {code}.")
    # Die Deinstallation läuft als Kopie in %TEMP% weiter; fertig ist sie, wenn
    # ihr Eintrag und der Programmordner verschwunden sind.
    _wait_until(lambda: not leftovers(present.location, registry, start_menu), UNINSTALL_SECONDS)
    rest = leftovers(present.location, registry, start_menu)
    if rest:
        raise UpdateCheckError("Nach der Deinstallation blieb: " + "; ".join(rest))


def without_version_jump(published_version: str, new_version: str) -> str | None:
    """Warum es kein Update zu prüfen gibt — oder ``None``, wenn die Versionen sich unterscheiden.

    Gleiche Versionen machen aus dem Update ein Neuinstallieren derselben
    Dateien: Weder der Eintrag unter *Apps* noch der Starttest sähen, ob das
    Setup etwas ersetzt hat. Beim Release trägt ``website/version.json`` noch
    die veröffentlichte Version, die neue steht schon in ``app.branding``.
    """
    if published_version != new_version:
        return None
    return (
        f"Veröffentlicht und neu ist dieselbe Version {new_version}; ohne Versionssprung "
        "prüft der Schritt kein Update. website/version.json nennt schon die neue Version."
    )


def _require_all_traces(
    location: Path, registry: Registry, start_menu: Path, when: str
) -> None:  # pragma: no cover — nur Windows
    missing = absent(location, registry, start_menu)
    if missing:
        raise UpdateCheckError(
            f"Nach {when} fehlt: " + "; ".join(missing) + " — die Restprüfung sähe dort umsonst."
        )


def check(setup: Path, work: Path) -> None:  # pragma: no cover — nur Windows
    registry = current_user_registry
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    work.mkdir(parents=True, exist_ok=True)
    release = published()
    reason = without_version_jump(release.version, APP_VERSION)
    if reason is not None:
        raise UpdateCheckError(reason)

    print("1. Die frisch installierte Version deinstallieren …", flush=True)
    uninstall(registry, start_menu)

    print(f"2. Die veröffentlichte Vorversion {release.version} installieren …", flush=True)
    old_setup = fetch(release, work / f"{APP_NAME}-Setup-{release.version}.exe")
    code = _run([str(old_setup), *FIRST_INSTALL_ARGUMENTS], SETUP_SECONDS)
    old = installed(registry)
    if code != 0 or old is None or old.version != release.version:
        raise UpdateCheckError(
            f"Die Vorversion {release.version} installierte sich nicht (Rückgabe {code}, "
            f"Eintrag {old.version if old else 'fehlt'})."
        )
    _require_all_traces(old.location, registry, start_menu, f"der Installation von {old.version}")

    print("3. Eigene Daten anlegen …", flush=True)
    own = own_files()
    plant(own)

    arguments = setup_arguments()
    print(f"4. Auf {APP_VERSION} aktualisieren mit {' '.join(arguments)} …", flush=True)
    code = _run([str(setup), *arguments], SETUP_SECONDS)
    new = installed(registry)
    if code != 0 or new is None:
        raise UpdateCheckError(f"Das Update endete mit {code}, Eintrag {'da' if new else 'fehlt'}.")
    if new.version != APP_VERSION:
        raise UpdateCheckError(
            f"Nach dem Update steht {new.version} statt {APP_VERSION} unter Apps."
        )
    if os.path.normcase(str(new.location)) != os.path.normcase(str(old.location)):
        raise UpdateCheckError(
            f"Das Update installierte nach {new.location} statt nach {old.location}."
        )
    _require_all_traces(new.location, registry, start_menu, f"dem Update auf {APP_VERSION}")
    # Die Anwendung trägt keine Versionsressource; welche Version läuft, sagt
    # der Starttest unten (sein Bericht muss ``APP_VERSION`` nennen).
    executable = new.location / f"{APP_NAME}.exe"
    if not _wait_until(lambda: bool(_running_from(new.location)), RESTART_SECONDS):
        raise UpdateCheckError(
            "Nach dem Update startete die Anwendung nicht wieder (/RESTARTAPP=1)."
        )
    for pid in _running_from(new.location):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    if not _wait_until(lambda: not _running_from(new.location), 60.0):
        raise UpdateCheckError(
            "Die nach dem Update gestartete Anwendung ließ sich nicht beenden; "
            "die Deinstallation danach hätte den falschen Grund gemeldet."
        )
    lost = missing_or_changed(own)
    if lost:
        raise UpdateCheckError("Das Update kostete eigene Daten: " + "; ".join(lost))
    started = _run(
        [
            sys.executable,
            str(ROOT / "tools" / "check_frozen_start.py"),
            "--executable",
            str(executable),
        ],
        SETUP_SECONDS,
    )
    if started != 0:
        raise UpdateCheckError("Der Starttest der aktualisierten Anwendung ist rot.")

    print("5. Die aktualisierte Version deinstallieren …", flush=True)
    uninstall(registry, start_menu)
    lost = missing_or_changed(own)
    if lost:
        raise UpdateCheckError("Die Deinstallation kostete eigene Daten: " + "; ".join(lost))
    print(
        f"Update von {release.version} auf {APP_VERSION} und Deinstallation in Ordnung.", flush=True
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--setup", required=True, help="das neue Setup")
    parser.add_argument("--work", required=True, help="Arbeitsordner für die Vorversion")
    args = parser.parse_args(argv)
    if os.name != "nt":
        print("::error::Der Update-Weg des Windows-Setups läuft nur unter Windows.")
        return 1
    try:
        check(Path(args.setup), Path(args.work))
    except (UpdateCheckError, OSError, subprocess.TimeoutExpired) as error:
        print(f"::error::{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
