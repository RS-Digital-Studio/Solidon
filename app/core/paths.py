"""Where user data lives (Bauplan §38).

Everything the application writes stays on this machine: profiles, log, cache,
own parts. Resolved without an extra dependency so the licence list stays short.
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
    """Profiles, own parts, recovery containers."""
    if sys.platform == "win32":
        return _windows_base("LOCALAPPDATA", "AppData/Local")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / APP_NAME


def user_config_dir() -> Path:
    """Settings the user changed. Credentials go to the system keyring instead."""
    if sys.platform == "win32":
        return _windows_base("APPDATA", "AppData/Roaming")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / APP_NAME
    root = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(root) / APP_NAME


def user_cache_dir() -> Path:
    """Disk cache over the op hash (§38). Safe to delete at any time."""
    if sys.platform == "win32":
        return _windows_base("LOCALAPPDATA", "AppData/Local") / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / APP_NAME
    root = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(root) / APP_NAME


def user_log_dir() -> Path:
    """Rotating local log (§33.2). Never sent anywhere."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    return user_data_dir() / "logs"


def user_parts_dir() -> Path:
    """Own parts (§24.5). Executable code comes from here or the installation —
    never from an opened project file."""
    return user_data_dir() / "parts"


def user_profiles_dir() -> Path:
    """Printer and material profiles derived from the shipped starting set (§38)."""
    return user_config_dir() / "profiles"


def ensure_dir(path: Path) -> Path:
    """Create a directory including parents and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
