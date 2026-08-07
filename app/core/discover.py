"""Programme finden, die installiert sind, aber nicht im PATH stehen (§38).

``shutil.which`` beantwortet eine Frage — „steht das im PATH" — und unter
Windows ist das fast nie dieselbe Frage wie „ist das installiert". OpenSCAD
landet in ``Program Files`` und trägt nichts in den PATH ein; ein Slicer
meldet sich unter *App Paths* an und trägt ebenfalls nichts ein. Wer nur den
PATH fragt, sagt jemandem, das Programm in seinem Startmenü sei nicht da —
und bietet an, es ein zweites Mal zu installieren.

Ein Programm wird deshalb an vier Stellen gesucht, die billigste zuerst:

1. der Pfad, den der Nutzer angegeben hat — der gewinnt immer, und deshalb ist
   eine portable Installation auf einem anderen Laufwerk keine Sackgasse;
2. der PATH, der unter Linux die richtige Antwort ist und unter Windows
   manchmal;
3. die Windows-Registry unter *App Paths*, wo Installationsprogramme ihre
   ausführbare Datei eintragen;
4. die üblichen Installationsordner, eine Ebene tief — dort liegen die Dateien
   auch dann, wenn sich nichts angemeldet hat.

Dienste sind eine andere Frage und bekommen eine andere Antwort. Formwerk
startet ComfyUI und Ollama nie, es redet über HTTP mit ihnen — es zählt also,
ob auf dem Port etwas antwortet, und nicht, ob irgendwo eine Datei liegt. Ein
nach ``D:\\AI`` entpacktes ComfyUI hat keine ausführbare Datei zum Finden und
keinen Registry-Eintrag zum Lesen, und es funktioniert einwandfrei.

Die gemerkten Pfade liegen in einer kleinen Datei neben der übrigen
Nutzerkonfiguration. Nichts hiervon schreibt je in ein Projekt.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir

_log = get_logger(__name__)

#: Wo die Antworten auf „nein, es liegt hier" aufbewahrt werden.
CHOICES_FILE: Final = "tools.json"

#: Wie lange ein Port antworten darf. Das läuft, während ein Fenster gebaut
#: wird (§31), und ein geschlossener Port antwortet sofort — teuer ist der
#: unerreichbare Rechner, und genau dort bringt Warten nichts.
PROBE_SECONDS: Final = 0.25

#: Endungen, unter denen ein Programm gesucht wird, in dieser Reihenfolge.
_SUFFIXES: Final = (".exe", ".com", "") if sys.platform == "win32" else ("",)


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


def find_program(tool_id: str, names: Iterable[str]) -> Path | None:
    """Wo dieses Programm liegt, oder ``None``. Reihenfolge siehe Modulkopf."""
    chosen = remembered(tool_id)
    if chosen:
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

    found_path = _from_registry(candidates) or _from_folders(candidates)
    _cache[tool_id] = found_path
    if found_path is not None:
        _log.info("found %s outside the PATH: %s", tool_id, found_path)
    return found_path


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
    PrusaSlicer auf dieser Maschine installiert und für Formwerk trotzdem
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
        for part in (".", "bin")
    ]


# --- Dienste --------------------------------------------------------------------


def service_url(tool_id: str, default: str) -> str:
    """Die Adresse eines Dienstes: die von Hand gesetzte, sonst die vorgegebene."""
    return remembered(tool_id) or default


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """Hört jemand zu? Ein Socket, keine Anfrage — Begründung bei :data:`PROBE_SECONDS`."""
    address = urlparse(url if "://" in url else f"http://{url}")
    host = address.hostname or "127.0.0.1"
    port = address.port
    if port is None:
        port = 443 if address.scheme == "https" else 80
    try:
        with socket.create_connection((host, port), timeout=seconds):
            return True
    except OSError:
        return False
