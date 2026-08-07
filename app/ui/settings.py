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
    """Farben der Differenzansicht (§19.1). Rot/Grün gibt es, es ist nicht die Vorgabe."""
    display_unit: str = "mm"
    """Shown unit (§19.3). The core stays on millimetres either way."""
    language: str = SOURCE_LANGUAGE
    right_panel_visible: bool = True
    printer: str = ""
    material: str = ""
    print_quality: str = ""
    """Zuletzt gewählte Qualitätsstufe (§29). Leer heißt: die Vorgabe."""
    slicer_machine_profile: str = ""
    """Maschinenprofil aus dem Bestand des Slicers. Solidon kennt Bettform und
    Startcode nicht und schreibt sie deshalb nicht — es zeigt darauf (§29)."""
    slicer_base_process: str = ""
    """Prozessprofil, auf das die Solidon-Werte gelegt werden. Die Orca-Familie
    braucht es, sonst gilt der Prozess als unverträglich mit dem Drucker."""
    slicer_base_filament: str = ""
    """Filamentprofil, auf das die Solidon-Werte gelegt werden. Ohne es kennt
    der Slicer nur „PETG" und nicht, welches — und die Werte des Herstellers
    für dieses Filament kämen gar nicht zum Tragen."""
    first_run_done: bool = False
    shortcut_scheme: str = "default"
    """Welche Kürzelbelegung gilt (Konzept P15, E7). Die Vorgabe ist die des
    Registers; „fusion" legt einzelne Buchstaben darüber."""
    check_for_updates: bool = False
    """§37.2: ein Hinweis, nie eine selbsttätige Aktualisierung — und aus, bis
    es eingeschaltet wird."""
    remote_enabled: bool = False
    """Ob die MCP-Schnittstelle läuft (Konzept P15 §7 Etappe 9).

    Aus, bis jemand sie einschaltet. Eine offene Schnittstelle, die niemand
    eingeschaltet hat, ist eine offene Tür — und sie stünde auf jedem Rechner
    offen, auf dem die Anwendung installiert ist."""
    remote_port: int = 8787
    """Auf welchem Port. Nur an 127.0.0.1 gebunden; die Adresse ist keine
    Einstellung."""

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
