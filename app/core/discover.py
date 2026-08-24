"""Programme finden, die installiert sind, aber nicht im PATH stehen (§38).

``shutil.which`` beantwortet eine Frage — „steht das im PATH" — und unter
Windows ist das fast nie dieselbe Frage wie „ist das installiert". OpenSCAD
landet in ``Program Files`` und trägt nichts in den PATH ein; ein Slicer
meldet sich unter *App Paths* an und trägt ebenfalls nichts ein. Wer nur den
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
   Anwendung (``org.openscad.OpenSCAD``) und stehen ausdrücklich nicht im
   PATH;
5. die üblichen Installationsordner, zwei Ebenen tief, unter macOS auch in
   ``Contents/MacOS`` — dort liegen die Dateien auch dann, wenn sich nichts
   angemeldet hat.

**Die Punkte 4 und 5 kamen dazu, als das Installieren dazukam.** Solange nur
winget angesteuert wurde, reichte die Registry. Seit ein Knopf auch Homebrew
und Flatpak bedient, muss gefunden werden, was diese beiden ablegen — sonst
installiert Solidon ein Programm und führt es danach weiter als „nicht
gefunden". Das ist die schlechteste aller Antworten: Sie lässt den Nutzer an
seiner eigenen Handlung zweifeln.

Dienste sind eine andere Frage und bekommen eine andere Antwort. Solidon
startet ComfyUI und Ollama nie, es redet über HTTP mit ihnen — es zählt also,
ob auf dem Port etwas antwortet, und nicht, ob irgendwo eine Datei liegt. Ein
nach ``D:\\AI`` entpacktes ComfyUI hat keine ausführbare Datei zum Finden und
keinen Registry-Eintrag zum Lesen, und es funktioniert einwandfrei.

Die gemerkten Pfade liegen in einer kleinen Datei neben der übrigen
Nutzerkonfiguration. Nichts hiervon schreibt je in ein Projekt.
"""

from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import sys
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

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
    Homebrew-Cask legt ``/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD``
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
#: ``org.openscad.OpenSCAD``. Weder ``shutil.which("openscad")`` noch ein
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
    chosen = remembered(tool_id)
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
        if path.is_file():
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
        _from_registry(candidates) or _from_flatpak(candidates) or _from_folders(candidates)
    )
    _cache[tool_id] = found_path
    if found_path is not None:
        _log.info("found %s outside the PATH: %s", tool_id, found_path)
    return found_path


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
    ``org.openscad.OpenSCAD`` ist ``openscad``, und danach fragt der Aufrufer.
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


def sandboxed(program: Path | str | None) -> bool:
    """Läuft dieses Programm in einer Sandbox, die unser ``/tmp`` nicht sieht?

    Wahr für die Startprogramme, die Flatpak exportiert. Der Wrapper selbst ist
    eine gewöhnliche Datei; was dahinter startet, sieht ein eigenes ``/tmp``
    und vom Rechner nur, was das Paket sich freigeben ließ.
    """
    if program is None:
        return False
    text = Path(program).as_posix()
    return any(Path(folder).expanduser().as_posix() in text for folder in _FLATPAK_EXPORTS)


@contextmanager
def workspace_for(program: Path | str | None, prefix: str) -> Iterator[Path]:
    """Ein Arbeitsordner, den *dieses* Programm auch lesen kann.

    **Der Fall, der ohne das still scheitert.** OpenSCAD und die Slicer bekommen
    eine Datei in einen temporären Ordner gelegt und werden darauf gerufen. Unter
    Linux legt ``tempfile`` nach ``/tmp`` — und ein Flatpak hat sein **eigenes**
    ``/tmp``. Der Aufruf käme also an, das Programm startete, und es fände die
    Datei nicht: „Can't open input file". Für den Nutzer sähe das aus wie ein
    Fehler von Solidon, unmittelbar nachdem er das Programm über einen Knopf
    installiert hat.

    Nachgesehen, nicht angenommen: Die Flathub-Pakete von OpenSCAD und
    OrcaSlicer geben beide ``--filesystem=home`` frei und sonst kein
    Verzeichnis, in dem wir schreiben würden. Der Arbeitsordner liegt für sie
    deshalb im Nutzer-Cache — der liegt unter ``$HOME``, ist an derselben
    Stelle sichtbar wie hier, und darf jederzeit gelöscht werden (§38).

    Für jedes andere Programm bleibt es beim Systemtemp: Er wird zuverlässig
    aufgeräumt, auch wenn Solidon dabei abstürzt.
    """
    if not sandboxed(program):
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            yield Path(directory)
        return
    home = ensure_dir(user_cache_dir() / "sandbox")
    directory = tempfile.mkdtemp(prefix=prefix, dir=home)
    try:
        yield Path(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


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
    der heißt, ist seine Sache (``ElegooSlicer``, ``OpenSCAD``, ``Ultimaker
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


def service_url(tool_id: str, default: str) -> str:
    """Die Adresse eines Dienstes: die von Hand gesetzte, sonst die vorgegebene."""
    return remembered(tool_id) or default


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """Hört jemand zu? Ein Socket, keine Anfrage — Begründung bei :data:`PROBE_SECONDS`.

    **Eine unbrauchbare Adresse ist „nicht erreichbar" und kein Absturz.** Was
    hier ankommt, hat jemand in ein Textfeld getippt, und dasselbe Feld meint
    bei OpenSCAD einen Pfad und bei Ollama eine Adresse. Trägt jemand dort
    einen Windows-Pfad ein — am 24.08.2026 tat es ein Kunde mit seinem
    Modellordner —, dann liest ``urlparse`` alles hinter ``C:`` als Port und
    wirft beim Zugriff darauf ``ValueError``. Der fing hier niemand, und der
    Arbeiter des Einrichtungsdialogs starb mitten in der Einrichtung.
    """
    try:
        address = urlparse(url if "://" in url else f"http://{url}")
        host = address.hostname or "127.0.0.1"
        port = address.port
    except ValueError:
        return False
    if port is None:
        port = 443 if address.scheme == "https" else 80
    try:
        with socket.create_connection((host, port), timeout=seconds):
            return True
    except OSError:
        return False
