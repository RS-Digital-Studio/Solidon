"""Wo Nutzerdaten liegen (Bauplan §38).

Alles, was die Anwendung schreibt, bleibt auf diesem Rechner: Profile,
Protokoll, Cache, eigene Bausteine. Ohne Zusatzabhängigkeit aufgelöst, damit
die Lizenzliste kurz bleibt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.branding import APP_NAME, APP_VENDOR


def _windows_base(variable: str, fallback: str) -> Path:
    root = os.environ.get(variable) or str(Path.home() / fallback)
    return Path(root) / APP_VENDOR / APP_NAME


def user_data_dir() -> Path:
    """Profile, eigene Bausteine, Wiederherstellungs-Container."""
    if sys.platform == "win32":
        return _windows_base("LOCALAPPDATA", "AppData/Local")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / APP_NAME


def user_config_dir() -> Path:
    """Einstellungen, die der Nutzer geändert hat. Zugangsdaten gehen
    stattdessen in den System-Schlüsselbund."""
    if sys.platform == "win32":
        return _windows_base("APPDATA", "AppData/Roaming")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / APP_NAME
    root = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(root) / APP_NAME


def user_cache_dir() -> Path:
    """Platten-Cache über den Op-Hash (§38). Darf jederzeit gelöscht werden."""
    if sys.platform == "win32":
        return _windows_base("LOCALAPPDATA", "AppData/Local") / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / APP_NAME
    root = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(root) / APP_NAME


def user_log_dir() -> Path:
    """Rotierendes lokales Protokoll (§33.2). Wird nie irgendwohin gesendet."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    return user_data_dir() / "logs"


def user_parts_dir() -> Path:
    """Eigene Bausteine (§24.5). Ausführbarer Code kommt von hier oder aus der
    Installation — nie aus einer geöffneten Projektdatei."""
    return user_data_dir() / "parts"


def user_profiles_dir() -> Path:
    """Drucker- und Materialprofile, abgeleitet vom mitgelieferten
    Startbestand (§38)."""
    return user_config_dir() / "profiles"


def ensure_dir(path: Path) -> Path:
    """Legt ein Verzeichnis samt Eltern an und gibt es zurück."""
    path.mkdir(parents=True, exist_ok=True)
    return path
