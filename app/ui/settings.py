"""Oberflächen-Einstellungen in einer schlichten Datei (Bauplan §38).

Als JSON im Konfigurationsverzeichnis des Nutzers gehalten statt in einer
Plattform-Registry: das ist lesbar, portabel und leicht zurückzusetzen.
Zugangsdaten leben nie hier — die gehören in den System-Schlüsselbund.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir
from app.i18n import SOURCE_LANGUAGE

_log = get_logger(__name__)

SETTINGS_FILE = "settings.json"
MAX_RECENT = 10


@dataclass(slots=True)
class UiSettings:
    """Everything the window remembers between sessions."""

    recent: list[str] = field(default_factory=list)
    navigation: str = "slicer"
    theme: str = "dark"
    diff_palette: str = "blue_orange"
    """Colours of the difference view (§19.1). Red/green is available, not default."""
    display_unit: str = "mm"
    """Shown unit (§19.3). The core stays on millimetres either way."""
    language: str = SOURCE_LANGUAGE
    right_panel_visible: bool = True
    printer: str = ""
    material: str = ""
    print_quality: str = ""
    """Zuletzt gewählte Qualitätsstufe (§29). Leer heißt: die Vorgabe."""
    slicer_machine_profile: str = ""
    """Maschinenprofil aus dem Bestand des Slicers. Formwerk kennt Bettform und
    Startcode nicht und schreibt sie deshalb nicht — es zeigt darauf (§29)."""
    slicer_base_process: str = ""
    """Prozessprofil, auf das die Formwerk-Werte gelegt werden. Die Orca-Familie
    braucht es, sonst gilt der Prozess als unverträglich mit dem Drucker."""
    first_run_done: bool = False
    shortcut_scheme: str = "default"
    """Welche Kürzelbelegung gilt (Konzept P15, E7). Die Vorgabe ist die des
    Registers; „fusion" legt einzelne Buchstaben darüber."""
    check_for_updates: bool = False
    """§37.2: a notice, never an automatic update — and off until it is switched on."""

    def remember(self, path: Path) -> None:
        text = str(path)
        self.recent = [text, *(entry for entry in self.recent if entry != text)][:MAX_RECENT]

    def existing_recent(self) -> list[Path]:
        """Zuletzt geöffnete Projekte, die es noch gibt — ein toter Eintrag hilft
        niemandem.
        """
        return [Path(entry) for entry in self.recent if Path(entry).is_file()]


def settings_path() -> Path:
    return user_config_dir() / SETTINGS_FILE


def load_settings() -> UiSettings:
    path = settings_path()
    if not path.is_file():
        return UiSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UiSettings(**{key: data[key] for key in data if key in UiSettings.__slots__})
    except (OSError, ValueError, TypeError) as problem:
        _log.warning("could not read settings, starting from defaults: %s", problem)
        return UiSettings()


def save_settings(settings: UiSettings) -> Path:
    path = settings_path()
    ensure_dir(path.parent)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path
