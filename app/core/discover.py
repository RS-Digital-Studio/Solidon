"""Programme finden, die installiert sind, aber nicht im PATH stehen (§38).

``shutil.which`` beantwortet eine Frage — „steht das im PATH" — und unter
Windows ist das fast nie dieselbe Frage wie „ist das installiert". Das eine
Programm landet in ``Program Files`` und trägt nichts in den PATH ein; das
nächste meldet sich unter *App Paths* an und trägt ebenfalls nichts ein. Wer nur den
PATH fragt, sagt jemandem, das Programm in seinem Startmenü sei nicht da —
und bietet an, es ein zweites Mal zu installieren.

Ein Programm wird deshalb an fünf Stellen gesucht, die billigste zuerst:

1. der Pfad, den der Nutzer angegeben hat — der gewinnt immer, und deshalb ist
   eine portable Installation auf einem anderen Laufwerk keine Sackgasse;
2. der PATH, der unter Linux die richtige Antwort ist und unter Windows
   manchmal;
3. die Windows-Registry unter *App Paths*, wo Installationsprogramme ihre
   ausführbare Datei eintragen;
4. die Startprogramme, die **Flatpak** exportiert — sie heißen wie die
   Anwendung (``com.orcaslicer.OrcaSlicer``) und stehen ausdrücklich nicht im
   PATH;
5. die üblichen Installationsordner, zwei Ebenen tief, unter macOS auch in
   ``Contents/MacOS`` — dort liegen die Dateien auch dann, wenn sich nichts
   angemeldet hat;
6. der PATH **des Rechners**, gefragt über ``flatpak-spawn --host`` — nur
   wenn Solidon selbst in einem Flatpak läuft, und dort der einzige Weg, der
   überhaupt etwas finden kann.

**Punkt 6 kam am 27.08.2026 dazu, und er ist eine Selbstkorrektur.** Dieses
Modul beschreibt seit je, wie man einen Slicer findet, der als Flatpak
installiert ist — und übersah, dass die eigene Linux-Auslieferung eines ist.
Aus einem Sandkasten heraus ist **keiner** der Wege 3 bis 5 gültig: Es sind
Host-Pfade, und der Sandkasten sieht sie nicht. Die Slicer-Übergabe (§29) war
im Linux-Paket damit tot, ohne dass etwas abstürzt — sie fand einfach nichts.

**Die Punkte 4 und 5 kamen dazu, als das Installieren dazukam.** Solange nur
winget angesteuert wurde, reichte die Registry. Seit ein Knopf auch Homebrew
und Flatpak bedient, muss gefunden werden, was diese beiden ablegen — sonst
installiert Solidon ein Programm und führt es danach weiter als „nicht
gefunden". Das ist die schlechteste aller Antworten: Sie lässt den Nutzer an
seiner eigenen Handlung zweifeln.

    Dienste sind eine andere Frage und bekommen eine andere Antwort. Benutzbar
    sind ComfyUI und Ollama, wenn ihr Port antwortet; eine gefundene lokale App
    ist zusätzlich ein Startweg. Ein Dienst auf einem anderen Rechner braucht
    dagegen nur seine Adresse.

Die gemerkten Pfade liegen in einer kleinen Datei neben der übrigen
Nutzerkonfiguration. Nichts hiervon schreibt je in ein Projekt.
"""

from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from app.branding import APP_NAME
from app.core import errors
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir, user_config_dir
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wo die Antworten auf „nein, es liegt hier" aufbewahrt werden.
CHOICES_FILE: Final = "tools.json"

#: Wie lange ein Port antworten darf. Das läuft, während ein Fenster gebaut
#: wird (§31), und ein geschlossener Port antwortet sofort — teuer ist der
#: unerreichbare Rechner, und genau dort bringt Warten nichts.
PROBE_SECONDS: Final = 0.25

#: Endungen, unter denen ein Programm gesucht wird, in dieser Reihenfolge.
_SUFFIXES: Final = (".exe", ".com", "") if sys.platform == "win32" else ("",)


def parts_for(platform: str) -> tuple[str, ...]:
    """Unterpfade, in denen eine ausführbare Datei innerhalb eines
    Installationsordners liegt.

    ``Contents/MacOS`` ist der Grund, warum es diese Funktion gibt: Ein
    Homebrew-Cask legt ``/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer``
    ab, und gesucht wurde bis hierhin nur direkt im Ordner und in ``bin``. Der
    Knopf installierte damit ein Programm, das die Liste danach weiter als
    „nicht gefunden" führte — die schlechteste aller Antworten, weil sie den
    Nutzer an seiner eigenen Handlung zweifeln lässt.

    Eine Funktion und keine Zeile mit ``if sys.platform``, damit die Zuordnung
    von **jeder** Maschine aus prüfbar ist: Ein Test, der die Mac-Pfade nur auf
    einem Mac sehen kann, prüft sie nirgends.
    """
    if platform == "darwin":
        return (".", "bin", "Contents/MacOS")
    return (".", "bin")


_PARTS: Final = parts_for(sys.platform)

#: Wo Flatpak die Startprogramme installierter Anwendungen ablegt — die
#: Systeminstallation und die des Nutzers.
#:
#: **Diese Verzeichnisse stehen nicht im PATH**, und das ist Absicht von
#: Flatpak („we're not automatically overriding PATH"). Die Dateien darin heißen
#: wie die Anwendung, also in umgekehrter Domainschreibweise:
#: ``com.orcaslicer.OrcaSlicer``. Weder ``shutil.which("orcaslicer")`` noch ein
#: Durchgang durch ``/opt`` und ``/usr/local`` findet das — nach einer
#: Flatpak-Installation war das Programm für Solidon also nicht vorhanden.
_FLATPAK_EXPORTS: Final = (
    "~/.local/share/flatpak/exports/bin",
    "/var/lib/flatpak/exports/bin",
)


def _install_roots() -> tuple[Path, ...]:
    """Ordner, die Installationsprogramme benutzen.

    Bei jedem Aufruf neu gelesen — eine Umgebung kann sich ändern.
    """
    if sys.platform == "win32":
        names = ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")
        roots = [Path(os.environ[name]) for name in names if os.environ.get(name)]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            roots.append(Path(local) / "Programs")
        return tuple(dict.fromkeys(roots))
    if sys.platform == "darwin":
        return (Path("/Applications"), Path.home() / "Applications", Path("/opt"))
    return (Path("/opt"), Path("/usr/local"), Path.home() / ".local" / "share")


# --- was der Nutzer angegeben hat -----------------------------------------------


def _choices_path() -> Path:
    return user_config_dir() / CHOICES_FILE


def _load() -> dict[str, str]:
    path = _choices_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _log.warning("could not read %s, ignoring it: %s", CHOICES_FILE, problem)
        return {}
    return {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}


def _store(entries: dict[str, str]) -> None:
    path = _choices_path()
    ensure_dir(path.parent)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def remembered(tool_id: str) -> str:
    """Was für dieses Programm von Hand gesetzt wurde, sonst eine leere Zeichenkette."""
    return _load().get(tool_id, "")


def remember(tool_id: str, value: str) -> None:
    """Einen Pfad oder eine Adresse merken. Ein leerer Wert vergisst sie wieder."""
    entries = _load()
    if value:
        entries[tool_id] = value
    else:
        entries.pop(tool_id, None)
    _store(entries)
    forget_cache()
    _log.info("external tool %s set to %r", tool_id, value)


def _typed_key(tool_id: str, kind: str) -> str:
    """Getrennter Speicherplatz für die zwei Seiten eines lokalen Dienstes."""
    return f"{tool_id}:{kind}"


def remembered_path(tool_id: str) -> str:
    """Der gewählte Programmpfad, mit Rückfall auf das alte gemeinsame Feld."""
    entries = _load()
    chosen = entries.get(_typed_key(tool_id, "path"), "")
    if chosen:
        return chosen
    legacy = entries.get(tool_id, "")
    return legacy if "://" not in legacy else ""


def _remote_address(entries: dict[str, str], tool_id: str) -> str:
    """Die gespeicherte Netzadresse aus dem neuen oder dem alten Feld."""
    chosen = entries.get(_typed_key(tool_id, "address"), "")
    if chosen:
        return chosen
    legacy = entries.get(tool_id, "")
    return legacy if "://" in legacy else ""


def remembered_remote_address(tool_id: str) -> str:
    """Die gespeicherte Netzadresse, auch wenn gerade lokal gearbeitet wird."""
    return _remote_address(_load(), tool_id)


def remembered_address(tool_id: str) -> str:
    """Die aktive Netzadresse; im lokalen Betrieb bleibt sie im Hintergrund erhalten."""
    entries = _load()
    remote = _remote_address(entries, tool_id)
    if entries.get(_typed_key(tool_id, "address_mode")) == "local":
        return ""
    return remote


def _remember_typed(tool_id: str, kind: str, value: str) -> None:
    """Eine Seite eines Dienstes ändern, ohne die andere zu verlieren."""
    entries = _load()
    key = _typed_key(tool_id, kind)
    if value:
        entries[key] = value
    else:
        entries.pop(key, None)
        legacy = entries.get(tool_id, "")
        is_address = "://" in legacy
        if (kind == "address") == is_address:
            entries.pop(tool_id, None)
    _store(entries)
    forget_cache()
    _log.info("external tool %s %s set to %r", tool_id, kind, value)


def remember_path(tool_id: str, value: str) -> None:
    """Den lokalen Startpfad eines Dienstes merken."""
    _remember_typed(tool_id, "path", value)


def remember_address(tool_id: str, value: str) -> None:
    """Eine Netzadresse speichern und als aktiven Dienstweg auswählen."""
    entries = _load()
    address_key = _typed_key(tool_id, "address")
    mode_key = _typed_key(tool_id, "address_mode")
    if value:
        entries[address_key] = value
        entries[mode_key] = "remote"
    else:
        entries.pop(address_key, None)
        entries.pop(mode_key, None)
        legacy = entries.get(tool_id, "")
        if "://" in legacy:
            entries.pop(tool_id, None)
    _store(entries)
    forget_cache()
    _log.info("external tool %s address set to %r", tool_id, value)


def use_local_address(tool_id: str) -> None:
    """Den lokalen Vorgabedienst aktivieren, ohne die Netzadresse zu vergessen."""
    entries = _load()
    mode_key = _typed_key(tool_id, "address_mode")
    if _remote_address(entries, tool_id):
        entries[mode_key] = "local"
    else:
        entries.pop(mode_key, None)
    _store(entries)
    _log.info("external tool %s switched to its local address", tool_id)


# --- Programme ------------------------------------------------------------------

#: Antworten aus dem Ordnerdurchgang, dem einzigen teuren Schritt. Wird nach
#: einer Installation geleert, damit ein gerade angekommenes Programm ohne
#: Neustart gesehen wird.
_cache: dict[str, Path | None] = {}


def forget_cache() -> None:
    """Beim nächsten Mal neu suchen. Nach einer Installation und nach einer Angabe."""
    _cache.clear()


def refresh_path() -> bool:
    """Den PATH dieses Prozesses aus der Registry nachlesen (nur Windows).

    **Das ist der Grund, warum „nach einem Neustart" dastand.** Ein
    Installationsprogramm schreibt seinen Ordner in die Umgebung des
    *Systems*; der laufende Prozess hat seine Kopie beim Start bekommen und
    sieht die Änderung nie. Die Liste meldete deshalb „Installiert — nach
    einem Neustart von Solidon ist es zu sehen", und wer eben noch einen Knopf
    gedrückt hatte, sollte die Anwendung schließen.

    Nachgelesen werden beide Hälften, wie Windows sie selbst zusammensetzt:
    die des Rechners und die des Benutzers. Was schon im PATH steht, bleibt
    vorn — eine ``.venv``, die den Interpreter stellt, darf nicht hinter eine
    Systeminstallation rutschen.

    Gibt zurück, ob sich etwas geändert hat.
    """
    if sys.platform != "win32":
        return False
    import winreg

    places = (
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    )
    parts: list[str] = []
    for root, key_path in places:
        try:
            with winreg.OpenKey(root, key_path) as key:
                value = winreg.QueryValueEx(key, "Path")[0]
        except OSError:
            continue
        parts.extend(os.path.expandvars(str(value)).split(os.pathsep))

    before = os.environ.get("PATH", "")
    known = before.split(os.pathsep)
    added = [entry for entry in parts if entry and entry not in known]
    if not added:
        return False
    os.environ["PATH"] = os.pathsep.join([*known, *added])
    _log.info("PATH picked up %d new folders without a restart", len(added))
    return True


def find_program(tool_id: str, names: Iterable[str]) -> Path | None:
    """Wo dieses Programm liegt, oder ``None``. Reihenfolge siehe Modulkopf."""
    chosen = remembered_path(tool_id)
    if chosen and "://" not in chosen:
        # Die Bedingung schließt eine **Adresse** aus, und das ist keine
        # Feinheit: :func:`remember` legt beides im selben Speicher ab, und
        # :func:`service_url` liest die Adresse dort wieder. Eine URL ist keine
        # Datei, galt damit als verschwunden — und bei jedem Aufruf stand
        # zweimal „remembered path for comfyui is gone: http://127.0.0.1:8188"
        # im Protokoll, während der Dienst antwortete.
        #
        # **Folgenlos für die Funktion und trotzdem ein Fehler: Die Warnung
        # log.** Sie hat beim Handlauf am 23.08.2026 zehn Minuten gekostet, weil
        # sie für die Erklärung eines ganz anderen Befunds gehalten wurde, und
        # sie trifft den Kunden genauso: Wer die Adresse einträgt — der Text
        # bietet es ausdrücklich an —, findet danach im Protokoll, sein Eintrag
        # sei fort. Eine falsche Auskunft ist teurer als keine.
        path = Path(chosen)
        if path.is_file() or (
            sys.platform == "darwin" and path.suffix.lower() == ".app" and path.is_dir()
        ):
            return path
        # **Im Flatpak ist ein eingetragener Pfad ein Host-Pfad**, und
        # ``is_file()`` darauf sagt zuverlässig nein. Ihn hier als verschwunden
        # zu melden wäre dieselbe falsche Auskunft wie im Absatz darüber, nur
        # unter anderem Vorzeichen: Der Nutzer hat den Pfad gerade eingetragen,
        # und das Protokoll sagt ihm, er sei fort.
        if in_flatpak():
            return path
        # Ein gemerkter Pfad, den es nicht mehr gibt, ist schlimmer als keiner:
        # er hielte das Programm für „gefunden", während jeder Aufruf scheitert.
        # Einmal sagen, dann weitersuchen.
        _log.warning("remembered path for %s is gone: %s", tool_id, chosen)

    candidates = tuple(names)
    for name in candidates:
        found = shutil.which(name)
        if found:
            return Path(found)

    if tool_id in _cache:
        return _cache[tool_id]

    found_path = (
        _from_registry(candidates)
        or _from_flatpak(candidates)
        or _from_folders(candidates)
        or _from_appimage(candidates)
        or _from_host(candidates)
    )
    _cache[tool_id] = found_path
    if found_path is not None:
        _log.info("found %s outside the PATH: %s", tool_id, found_path)
    return found_path


def find_programs(tool_id: str, names: Iterable[str]) -> tuple[Path, ...]:
    """**Alle** installierten Fassungen dieses Programms, nicht nur die erste.

    :func:`find_program` beantwortet „wo liegt es" und hört beim ersten Treffer
    auf — richtig, solange es nur eine Antwort gibt. Auf einem Rechner mit drei
    Slicern ist die erste aber eine Zufallsentscheidung der Suchreihenfolge:
    Gemessen am 30.08.2026 fand Solidon ElegooSlicer und bot PrusaSlicer und
    Cura nicht an, obwohl beide danebenstanden — und als ElegooSlicers
    Kommandozeile nicht slicen wollte, war das eine Sackgasse statt einer Wahl.

    Der gemerkte Pfad steht vorn, sofern er noch existiert: Was der Nutzer
    gewählt hat, ist die erste Antwort und nicht eine unter mehreren.
    Doppelte Funde fallen weg — dieselbe Datei über PATH und über den
    Installationsordner ist ein Programm, keine zwei.
    """
    candidates = tuple(names)
    found: list[Path] = []

    def keep(entry: Path | None) -> None:
        if entry is None:
            return
        resolved = entry.resolve() if entry.exists() else entry
        if all(
            resolved != other.resolve() if other.exists() else resolved != other for other in found
        ):
            found.append(entry)

    chosen = remembered_path(tool_id)
    if chosen and "://" not in chosen and Path(chosen).is_file():
        keep(Path(chosen))

    for name in candidates:
        located = shutil.which(name)
        if located:
            keep(Path(located))

    keep(_from_registry(candidates))
    keep(_from_flatpak(candidates))
    for entry in _all_from_folders(candidates):
        keep(entry)
    keep(_from_appimage(candidates))
    keep(_from_host(candidates))
    return _one_per_installation(found, candidates)


def _one_per_installation(found: list[Path], names: tuple[str, ...]) -> tuple[Path, ...]:
    """Je Installationsordner ein Eintrag — eine Wahl, keine Dateiliste.

    Eine Installation bringt mehrere Startprogramme mit: PrusaSlicer legt
    ``prusa-slicer.exe`` und ``prusa-slicer-console.exe`` nebeneinander, Cura
    das Fenster und ``CuraEngine.exe``. Das sind zwei Wege in dasselbe
    Programm und nicht zwei Programme — wer wählen soll, bekommt sonst fünf
    Zeilen für drei Slicer und muss raten, welche zusammengehören.

    Welcher Eintrag den Ordner vertritt, entscheidet die Reihenfolge in
    ``names``: Sie steht in :data:`app.core.tools.SLICERS` und nennt die
    Kommandozeilenfassung dort, wo eine gebraucht wird.
    """
    rank = {plain_name(name): index for index, name in enumerate(names)}
    best: dict[Path, Path] = {}
    for entry in found:
        folder = entry.parent
        current = best.get(folder)
        if current is None or rank.get(plain_name(entry.name), len(rank)) < rank.get(
            plain_name(current.name), len(rank)
        ):
            best[folder] = entry
    return tuple(best[folder] for folder in dict.fromkeys(entry.parent for entry in found))


def _all_from_folders(names: tuple[str, ...]) -> tuple[Path, ...]:
    """Wie :func:`_from_folders`, aber ohne beim ersten Treffer aufzuhören."""
    found: list[Path] = []
    for root in _install_roots():
        for folder in _folders_in(root):
            for candidate in _below(folder, names):
                if candidate.is_file():
                    found.append(candidate)
            for inner in _folders_in(folder):
                for candidate in _below(inner, names):
                    if candidate.is_file():
                        found.append(candidate)
    return tuple(found)


def plain_name(name: str) -> str:
    """Ein Programmname ohne Schreibweise: klein, ohne Trenner, ohne Endung.

    „orca-slicer", „OrcaSlicer" und das letzte Stück von
    „com.orcaslicer.OrcaSlicer" sind dasselbe Programm, und keine der drei
    Schreibweisen ist die richtige. Verglichen wird deshalb die nackte Form.
    """
    stem = name.rsplit("/", 1)[-1]
    for suffix in (".exe", ".com", ".app"):
        stem = stem.removesuffix(suffix)
    return stem.replace("-", "").replace("_", "").replace(" ", "").lower()


def _from_flatpak(names: tuple[str, ...]) -> Path | None:
    """Die Startprogramme, die Flatpak exportiert (siehe :data:`_FLATPAK_EXPORTS`).

    Verglichen wird das letzte Stück der Anwendungskennung:
    ``com.orcaslicer.OrcaSlicer`` ist ``orcaslicer``, und danach fragt der
    Aufrufer.
    Das trägt auch für Anwendungen, die niemand hier eingetragen hat — ein
    selbst installiertes ``com.prusa3d.PrusaSlicer`` wird gefunden, weil sein
    letztes Stück derselbe Name ist.

    Der Wrapper ist eine gewöhnliche ausführbare Datei; er startet
    ``flatpak run`` und nimmt dieselben Argumente. Für den Aufrufer ändert sich
    damit nichts — außer dass es ihn überhaupt gibt.
    """
    if not sys.platform.startswith("linux"):
        return None
    wanted = {plain_name(name) for name in names}
    for folder in _FLATPAK_EXPORTS:
        directory = Path(folder).expanduser()
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and plain_name(entry.name.rsplit(".", 1)[-1]) in wanted:
                return entry
    return None


def in_flatpak() -> bool:
    """Läuft **Solidon selbst** in einem Flatpak?

    **Die Frage, die dieses Modul zwei Fassungen lang nicht gestellt hat.** Es
    beschreibt sorgfältig, wie man einen Slicer findet, der als Flatpak
    installiert ist — und übersah, dass die eigene Linux-Auslieferung eines
    ist. Aus einem Sandkasten heraus ist **keiner** der fünf Suchwege gültig:
    ``/opt``, ``/usr/local``, ``~/.local/share`` und die Flatpak-Exporte des
    Rechners sind Host-Pfade, und der Sandkasten sieht sie nicht. Die
    Slicer-Übergabe (§29) war im Linux-Paket damit tot, und niemand hat es
    gemeldet, weil nichts abstürzt: Es findet einfach nichts.

    Erkannt an ``/.flatpak-info`` — die Datei legt Flatpak in jedem Sandkasten
    an, und sie ist die Auskunft, die auch ``flatpak-spawn`` selbst benutzt.
    ``FLATPAK_ID`` steht daneben und wird mitgeprüft, weil eine Umgebung sie
    setzen kann, ohne dass die Datei da ist.
    """
    return Path("/.flatpak-info").exists() or bool(os.environ.get("FLATPAK_ID"))


def on_host(command: Sequence[str]) -> list[str]:
    """Derselbe Befehl, aber auf dem Rechner statt im Sandkasten.

    Aus einem Flatpak heraus startet ``subprocess`` im Sandkasten, und dort
    gibt es keinen Slicer. ``flatpak-spawn --host`` reicht den Aufruf nach
    draußen; es liegt im Runtime und braucht keine Installation, wohl aber die
    Berechtigung ``--talk-name=org.freedesktop.Flatpak`` im Manifest.

    Außerhalb eines Flatpak bleibt der Befehl, wie er ist — die Funktion darf
    deshalb bedingungslos um jeden Start gelegt werden.
    """
    if not in_flatpak():
        return list(command)
    return ["flatpak-spawn", "--host", *command]


def is_dir_on_host(folder: Path) -> bool:
    """Gibt es dieses Verzeichnis — auf dem Rechner, nicht im Sandkasten?

    Außerhalb eines Flatpak ist das ``folder.is_dir()`` und sonst nichts.
    Darin ist es die einzig richtige Frage: Ein Host-Pfad existiert im
    Sandkasten nicht, und ``is_dir()`` darauf antwortet zuverlässig falsch.

    **Woran das hing.** ``slicer_profiles.install_root`` sucht von der
    Programmdatei aus nach oben nach ``resources/profiles`` — im Flatpak fand
    es nie etwas, und für Cura fällt damit ``-j <definition>`` weg. CuraEngine
    startet ohne Definition gar nicht: Die Übergabe war also auch nach dem
    Start-Fix noch tot, nur eine Ebene später.

    Ein Aufruf je Kandidat, und die Kandidatenliste ist kurz (der Pfad und
    seine Eltern). Draußen kostet es nichts.
    """
    if not in_flatpak():
        return folder.is_dir()
    try:
        answer = subprocess.run(
            ["flatpak-spawn", "--host", "test", "-d", str(folder)],
            capture_output=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as problem:
        _log.info("cannot ask the host about %s: %s", folder, problem)
        return False
    return answer.returncode == 0


#: Wo ein AppImage üblicherweise liegt. Es gibt keinen vorgeschriebenen Ort —
#: die Datei wird heruntergeladen, ausführbar gemacht und irgendwohin gelegt.
#: Diese fünf sind die Orte, die die Anbieter selbst nennen und die die
#: Integrationswerkzeuge (AppImageLauncher, Gear Lever) benutzen.
_APPIMAGE_FOLDERS: Final = (
    "~/Applications",
    "~/.local/bin",
    "~/bin",
    "~/Downloads",
    "/opt",
)


def _appimage_segments(stem: str) -> list[str]:
    """Der Dateiname eines AppImage, an seinen Trennern zerlegt.

    ``OrcaSlicer_Linux_V2.1.1`` wird zu ``orcaslicer linux v2 1 1``. Die
    Trenner sind die Grenze, und deshalb geht das **nicht** über
    :func:`plain_name`: Die entfernt sie, und danach ist ``orcaslicerlinux``
    ein Wort.
    """
    plain = stem
    for separator in ("-", "_", ".", "+"):
        plain = plain.replace(separator, " ")
    return [piece.lower() for piece in plain.split() if piece]


def _matches_appimage(stem: str, wanted: frozenset[str]) -> bool:
    """Ist ``stem`` ein AppImage eines der gesuchten Programme?

    Ein AppImage trägt Version und Plattform im Namen —
    ``PrusaSlicer-2.8.1+linux-x64-GTK3``, ``OrcaSlicer_Linux_V2.1.1``,
    ``BambuStudio_ubuntu-24.04_v01.09`` —, also kann der Vergleich nicht auf
    Gleichheit gehen. Er geht auf die **Segmente**: Der gesuchte Name muss eine
    zusammenhängende Folge davon genau ausfüllen.

    Das ist die Bedingung, die ``UltiMaker-Cura-5.7.0`` für „cura" gelten lässt
    und ``GitHubDesktop`` für „git" nicht. Ohne sie fände die Suche nach ``git``
    das GitHub-Programm, und der Aufrufer bekäme etwas, das er nie gemeint hat.

    Die erste Fassung verglich über :func:`plain_name` und einen Blick auf das
    nächste Zeichen. Sie fiel bei zwei von acht bekannten Namen um — genau
    denen mit einem Unterstrich, weil ``plain_name`` ihn entfernt.
    """
    segments = _appimage_segments(stem)
    for start in range(len(segments)):
        joined = ""
        for piece in segments[start:]:
            joined += piece
            if joined in wanted:
                return True
            if len(joined) > 40:
                break
    return False


def _from_appimage(names: tuple[str, ...]) -> Path | None:
    """AppImages in den üblichen Ablagen — **der häufigste Linux-Fall**.

    PrusaSlicer, OrcaSlicer, Cura und BambuStudio liefern für Linux in erster
    Linie ein AppImage aus. Es ist eine einzelne ausführbare Datei mit Version
    im Namen, steht in keinem Paketverwalter und liegt an keinem verabredeten
    Ort — die fünf Stufen davor suchen alle nach einem *exakten* Namen in einem
    Installationsordner und treffen davon keine einzige.

    Gefunden wird über den Anfang der nackten Form (:func:`plain_name`), und
    die Datei muss **ausführbar** sein: Ein heruntergeladenes AppImage ohne
    ``chmod +x`` ist keins, das man starten kann, und es als gefunden zu melden
    hieße, den Fehler eine Stelle später und unverständlicher auftauchen zu
    lassen.
    """
    if not sys.platform.startswith("linux"):
        return None
    wanted = frozenset(plain_name(name) for name in names)
    for folder in _APPIMAGE_FOLDERS:
        directory = Path(folder).expanduser()
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.suffix.lower() != ".appimage" or not entry.is_file():
                continue
            if not _matches_appimage(entry.stem, wanted):
                continue
            if not os.access(entry, os.X_OK):
                # Die Auskunft, die dem Support die Frage erspart: Die Datei
                # liegt da, sie ist nur nicht ausführbar.
                _log.info("appimage found but not executable: %s", entry)
                continue
            return entry
    return None


def _from_host(names: tuple[str, ...]) -> Path | None:
    """Was der Rechner draußen im PATH hat — die sechste Suchstufe.

    Nur aus einem Flatpak heraus, und dort die einzige, die überhaupt etwas
    finden kann. Der zurückgegebene Pfad ist ein **Host**-Pfad: Er existiert im
    Sandkasten nicht, und ``is_file()`` darauf ist falsch. Startbar ist er
    trotzdem — über :func:`on_host`.
    """
    if not in_flatpak():
        return None
    for name in names:
        try:
            # Fester Befehl, und die Namen kommen aus dem Register - keine
            # Zeichenkette aus Nutzerhand, keine Shell.
            answer = subprocess.run(
                ["flatpak-spawn", "--host", "which", name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as problem:
            _log.info("cannot ask the host for %s: %s", name, problem)
            return None
        found = answer.stdout.strip().splitlines()
        if answer.returncode == 0 and found:
            _log.info("found %s on the host: %s", name, found[0])
            return Path(found[0])
    return None


def sandboxed(program: Path | str | None) -> bool:
    """Läuft dieses Programm in einer Sandbox, die unser ``/tmp`` nicht sieht?

    Wahr für die Startprogramme, die Flatpak exportiert. Der Wrapper selbst ist
    eine gewöhnliche Datei; was dahinter startet, sieht ein eigenes ``/tmp``
    und vom Rechner nur, was das Paket sich freigeben ließ.

    **Und wahr, sobald Solidon selbst in einem Flatpak läuft** — dann ist es
    unser ``/tmp``, das der andere nicht sieht, und die Richtung des Satzes
    kehrt sich um. Das Ergebnis ist dasselbe: Der Arbeitsordner gehört unter
    ``$HOME``, wo beide hinsehen können.
    """
    if in_flatpak():
        return True
    if program is None:
        return False
    text = Path(program).as_posix()
    return any(Path(folder).expanduser().as_posix() in text for folder in _FLATPAK_EXPORTS)


def exchange_dir() -> Path:
    """Wo ein Arbeitsordner liegt, den ein **fremder** Sandkasten lesen kann.

    Draußen ist das der Nutzer-Cache und sonst nichts. Läuft Solidon selbst in
    einem Flatpak, ist es das nicht: Flatpak setzt ``XDG_CACHE_HOME`` auf
    ``~/.var/app/<unsere-id>/cache``, und ``--filesystem=home`` — das, was die
    Slicer-Pakete freigeben — nimmt ``~/.var`` ausdrücklich **aus**. Flatpak
    blendet die App-Verzeichnisse gegeneinander aus, damit keine App der
    anderen in die Daten greift.

    Die Folge wäre genau der Fehler, den :func:`workspace_for` verhindern soll,
    nur eine Ebene weiter: Der Ordner liegt in ``$HOME``, der Slicer darf
    ``$HOME`` lesen, und die Datei ist trotzdem unsichtbar. „Can't open input
    file", unmittelbar nach einer Installation über einen Knopf.

    ``$HOME`` selbst ist im Flatpak das **echte** Home, sobald die App
    Home-Zugriff hat (ohne ihn setzt Flatpak es auf ``~/.var/app/<id>``); unser
    Manifest gibt ``--filesystem=home``. Der Austauschordner liegt deshalb
    unter ``~/.cache`` — an derselben Stelle, an der ihn ein Programm ohne
    Sandkasten auch fände, und löschbar wie jeder Cache (§38).

    Dasselbe Muster wie in :func:`app.core.export.slicer_profiles.config_home`:
    **Im Flatpak gilt die XDG-Variable nicht, gemeint ist der Rechner.**
    """
    if not in_flatpak():
        return user_cache_dir() / "sandbox"
    return Path.home() / ".cache" / f"{APP_NAME}-exchange"


@contextmanager
def workspace_for(program: Path | str | None, prefix: str) -> Iterator[Path]:
    """Ein Arbeitsordner, den *dieses* Programm auch lesen kann.

    **Der Fall, der ohne das still scheitert.** Die Slicer bekommen eine
    Datei in einen temporären Ordner gelegt und werden darauf gerufen. Unter
    Linux legt ``tempfile`` nach ``/tmp`` — und ein Flatpak hat sein **eigenes**
    ``/tmp``. Der Aufruf käme also an, das Programm startete, und es fände die
    Datei nicht: „Can't open input file". Für den Nutzer sähe das aus wie ein
    Fehler von Solidon, unmittelbar nachdem er das Programm über einen Knopf
    installiert hat.

    Nachgesehen, nicht angenommen: Das Flathub-Paket von OrcaSlicer gibt
    ``--filesystem=home`` frei und sonst kein Verzeichnis, in dem wir schreiben
    würden. Der Arbeitsordner liegt für sie deshalb unter ``$HOME`` und darf
    jederzeit gelöscht werden (§38); **wo genau**, entscheidet
    :func:`exchange_dir` — und das ist nicht dieselbe Antwort, wenn Solidon
    selbst ein Flatpak ist.

    Für jedes andere Programm bleibt es beim Systemtemp: Er wird zuverlässig
    aufgeräumt, auch wenn Solidon dabei abstürzt.

    Und das Anlegen selbst kann scheitern — volle Platte, ein
    schreibgeschützter Cache. Ein roher ``OSError`` endet im Export-Arbeiter
    als abgerissener Thread ohne ein Wort (siehe
    :class:`~app.core.errors.FileWriteError`); hier wird er deshalb zu einem
    Fehler mit Handlungsvorschlag, und der Grund des Betriebssystems reist
    unübersetzt mit.
    """
    if not sandboxed(program):
        try:
            keeper = tempfile.TemporaryDirectory(prefix=prefix)
        except OSError as problem:
            raise _workspace_error(tempfile.gettempdir(), problem) from problem
        with keeper as directory:
            yield Path(directory)
        return
    shared = exchange_dir()
    try:
        home = ensure_dir(shared)
        directory = tempfile.mkdtemp(prefix=prefix, dir=home)
    except OSError as problem:
        raise _workspace_error(str(shared), problem) from problem
    try:
        yield Path(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _workspace_error(target: str, problem: OSError) -> errors.FileWriteError:
    """Der Arbeitsordner ließ sich nicht anlegen — als Fehler mit Vorschlag."""
    return errors.FileWriteError(
        target=target,
        detail=_("Der Arbeitsordner für das externe Programm ließ sich nicht anlegen."),
        values={"reason": str(problem)},
        suggestions=(errors.RETRY, errors.CANCEL),
    )


def _from_registry(names: tuple[str, ...]) -> Path | None:
    """Windows *App Paths*: wo ein Installationsprogramm seine Datei nennt."""
    if sys.platform != "win32":
        return None
    import winreg

    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for name in names:
            entry = name if name.lower().endswith(".exe") else f"{name}.exe"
            try:
                with winreg.OpenKey(root, f"{key_path}\\{entry}") as key:
                    value = winreg.QueryValueEx(key, "")[0]
            except OSError:
                continue
            path = Path(str(value).strip('"'))
            if path.is_file():
                return path
    return None


def _from_folders(names: tuple[str, ...]) -> Path | None:
    """Zwei Ebenen unter den üblichen Installationsordnern — kein rekursiver Lauf.

    Ein Installationsprogramm legt seine Dateien in einen eigenen Ordner; wie
    der heißt, ist seine Sache (``ElegooSlicer``, ``OrcaSlicer``, ``Ultimaker
    Cura 5.7``). Deshalb wird jeder Ordner angesehen und die ausführbare Datei
    beim Namen gefragt — eine Handvoll ``is_file``-Aufrufe statt eines Laufs
    über eine ganze Festplatte.

    **Zwei** Ebenen, nicht eine, und das ist keine Vorsichtsmaßnahme: Prusa
    installiert nach ``Program Files\\Prusa3D\\PrusaSlicer\\``, ein Ordner für
    die Firma und einer für das Programm. Eine Ebene tief gesucht, war
    PrusaSlicer auf dieser Maschine installiert und für Solidon trotzdem
    nicht vorhanden — die Übergabe an den Slicer bot ihn schlicht nicht an.
    """
    for root in _install_roots():
        for folder in _folders_in(root):
            for candidate in _below(folder, names):
                if candidate.is_file():
                    return candidate
            for inner in _folders_in(folder):
                for candidate in _below(inner, names):
                    if candidate.is_file():
                        return candidate
    return None


def _folders_in(root: Path) -> list[Path]:
    """Die Unterordner, oder nichts — ein Pfad ohne Leserecht hält nicht auf."""
    try:
        return [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return []


def _below(folder: Path, names: tuple[str, ...]) -> list[Path]:
    """Wo eine ausführbare Datei in diesem Ordner liegen könnte."""
    return [
        folder / part / f"{name}{suffix}"
        for name in names
        for suffix in _SUFFIXES
        for part in _PARTS
    ]


# --- Dienste --------------------------------------------------------------------

#: Was eine kaputte Adresse werfen kann — **ohne** die Netzfehler.
#:
#: ``ValueError`` kommt aus ``urllib.parse``, sobald der Teil hinter einem
#: Doppelpunkt als Port gelesen wird und keine Zahl ist; ``InvalidURL`` ist
#: derselbe Fall eine Schicht tiefer und erbt von ``http.client.HTTPException``
#: — also **von keiner der beiden anderen Familien**. Genau daran ist der Fall
#: vom 24.08.2026 durchgerutscht: Ein Kunde trug seinen Modellordner in ein
#: Adressfeld ein, eine Stelle fing den ``ValueError``, und drei weitere
#: bekamen ein ``InvalidURL``, das dort niemand erwartete.
BROKEN_ADDRESS: Final = (ValueError, http.client.HTTPException)

#: Dasselbe, plus „niemand hört zu" (``OSError`` deckt auch ``URLError``).
#:
#: Wer beides gleich behandelt — „von hier kommt keine Antwort" —, nimmt diese
#: Familie. Wer für einen nicht laufenden Dienst einen **eigenen** Satz hat,
#: nimmt :data:`BROKEN_ADDRESS` und lässt die Netzfehler an seiner eigenen
#: Klausel vorbeilaufen.
UNUSABLE_ADDRESS: Final = (OSError, *BROKEN_ADDRESS)


def unusable_address(text: str) -> TranslatableText | None:
    """Was an dieser Adresse nicht geht — ``None``, wenn nichts.

    **Ein Feld, das jede Eingabe annimmt, verschiebt den Fehler nur.** Der
    Einrichtungsdialog fragte „Adresse, unter der es erreichbar ist" und
    speicherte, was kam; ein Kunde trug dort am 24.08.2026 den Ordner seiner
    Modelle ein. Gemerkt hat er es erst Stunden später an einer Meldung, die
    von etwas ganz anderem sprach.

    Geprüft wird deshalb dort, wo die Eingabe hereinkommt — mit einem Satz, der
    sagt, was stattdessen hineingehört.
    """
    address = text.strip()
    if not address:
        # Leer heißt „wieder die Vorgabe" und ist kein Fehler.
        return None
    if Path(address).drive or address.startswith(("/", "\\", "~", "file:")):
        return _(
            "Das sieht nach einem Ordner oder einer Datei aus. Hier gehört die "
            "Adresse hin, unter der der Dienst im Netz antwortet — sie beginnt "
            "mit http:// und nennt Rechner und Port."
        )
    try:
        parts = urlparse(address if "://" in address else f"http://{address}")
        # Der Zugriff **ist** die Prüfung: ``urlsplit`` wirft erst hier.
        _port = parts.port
    except ValueError:
        return _(
            "Nach dem Doppelpunkt gehört die Portnummer, und dort steht keine "
            "Zahl. Eine Adresse sieht aus wie http://localhost:11434."
        )
    if not parts.hostname:
        return _(
            "Darin steht kein Rechnername. Eine Adresse sieht aus wie "
            "http://localhost:11434 — der Name des Rechners, dann der Port."
        )
    return None


#: Rechnernamen, hinter denen dieser Rechner selbst steht.
#:
#: Alles darunter hinaus liest :func:`is_local_address` als Adressliteral —
#: ``127.x.x.x`` und ``::1`` sind dieselbe Maschine, gleich wie sie
#: geschrieben stehen.
_LOCAL_NAMES: Final = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", ""})


def is_local_address(url: str) -> bool:
    """Zeigt diese Adresse auf diesen Rechner?"""
    try:
        host = (urlparse(url).hostname or "").strip().lower()
    except ValueError:
        return False
    if host in _LOCAL_NAMES or host.endswith(".localhost"):
        return True
    # ``127.0.0.53`` ist so lokal wie ``127.0.0.1`` — das ganze /8 gehört
    # diesem Rechner, und systemd-resolved sitzt tatsächlich dort.
    return host.startswith("127.")


def opener_for(url: str) -> urllib.request.OpenerDirector:
    """Ein Öffner für diese Adresse — **ohne Proxy, wenn sie hierher zeigt**.

    ``urlopen`` baut seinen Öffner aus :func:`urllib.request.getproxies`, und
    das liest ``http_proxy``/``https_proxy`` und unter Windows und macOS die
    Systemeinstellung. Für alles, was hinausgeht, ist das genau richtig: Ein
    Nutzer hinter einem Firmenproxy erreicht die Update-Prüfung nur so.

    **Für einen Dienst auf demselben Rechner ist es genau falsch.** Gemessen
    am 27.08.2026 mit gesetztem ``http_proxy`` und ohne ``no_proxy``:

        proxy_bypass("localhost:11434")   False
        proxy_bypass("127.0.0.1:8188")    False

    Die Abfrage an das eigene Ollama und der Auftrag an das eigene ComfyUI
    gingen damit an den Firmenproxy, und der kennt keinen von beiden. Das
    Ergebnis wäre „Backend nicht erreichbar" für ein Programm, das läuft —
    dieselbe Sorte Auskunft wie „nicht gefunden" für ein installiertes
    Programm, und aus demselben Grund die schlechteste: Sie lässt den Nutzer
    an seiner eigenen Handlung zweifeln.

    ``no_proxy=localhost`` zu setzen wäre die Aufgabe des Nutzers und ist die
    Antwort, die niemand kennt, bevor er das Problem hat.
    """
    if is_local_address(url):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def service_url(tool_id: str, default: str) -> str:
    """Die Adresse eines Dienstes: die von Hand gesetzte, sonst die vorgegebene."""
    return remembered_address(tool_id) or default


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """Hört jemand zu? Ein Socket, keine Anfrage — Begründung bei :data:`PROBE_SECONDS`.

    **Eine unbrauchbare Adresse ist „nicht erreichbar" und kein Absturz.** Was
    hier ankommt, hat jemand in ein Textfeld getippt, und dasselbe Feld meint
    beim Slicer einen Pfad und bei Ollama eine Adresse. Trägt jemand dort
    einen Windows-Pfad ein — am 24.08.2026 tat es ein Kunde mit seinem
    Modellordner —, dann liest ``urlparse`` alles hinter ``C:`` als Port und
    wirft beim Zugriff darauf ``ValueError``. Der fing hier niemand, und der
    Arbeiter des Einrichtungsdialogs starb mitten in der Einrichtung.
    """
    try:
        address = urlparse(url if "://" in url else f"http://{url}")
        port = address.port
    except ValueError:
        return False
    if not address.hostname:
        # **Ohne Rechnernamen wird gar nicht erst gefragt.** Hier stand
        # ``hostname or "127.0.0.1"``, und damit fragte eine Adresse, die gar
        # keine ist, den eigenen Rechner: ``C:\Users\…`` hat für
        # ``urlparse`` das Schema ``c`` und keinen Host. Auf einer Maschine, auf
        # der irgendetwas auf Port 80 lauscht, meldete das „erreichbar" — und
        # genau dort war der Test dazu grün, wo nichts lauschte. Gefunden hat
        # es die CI (24.08.2026), auf demselben Betriebssystem wie hier.
        return False
    host = address.hostname
    if port is None:
        port = 443 if address.scheme == "https" else 80
    try:
        with socket.create_connection((host, port), timeout=seconds):
            return True
    except OSError:
        return False
