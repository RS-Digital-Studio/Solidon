"""Surface settings in a plain file (Bauplan §38).

Kept as JSON in the user configuration directory rather than in a platform
registry: it is readable, portable and easy to reset. Credentials never live
here — those belong in the system keyring.
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
    display_unit: str = "mm"
    """Shown unit (§19.3). The core stays on millimetres either way."""
    language: str = SOURCE_LANGUAGE
    right_panel_visible: bool = True
    printer: str = ""
    material: str = ""
    first_run_done: bool = False

    def remember(self, path: Path) -> None:
        text = str(path)
        self.recent = [text, *(entry for entry in self.recent if entry != text)][:MAX_RECENT]

    def existing_recent(self) -> list[Path]:
        """Recent projects that are still there — a dead entry helps nobody."""
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
