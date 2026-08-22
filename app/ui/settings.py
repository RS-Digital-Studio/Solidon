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
    """Alles, was sich das Fenster über Sitzungen hinweg merkt."""

    recent: list[str] = field(default_factory=list)
    navigation: str = "slicer"
    theme: str = "dark"
    diff_palette: str = "blue_orange"
    """Farben der Differenzansicht (§19.1). Rot/Grün gibt es, es ist nicht die Vorgabe."""
    display_unit: str = "mm"
    """Die Anzeigeeinheit (§19.3). Der Kern bleibt in beiden Fällen bei
    Millimetern."""
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
    slicer_profile_printer: str = ""
    """Für welchen Drucker die drei Profile darüber gewählt wurden (§29).

    Ein Maschinenprofil gehört zu genau einem Drucker. Ohne diesen Vermerk
    trüge die 3MF eines Prusa-Projekts das Profil des Elegoo, mit dem zuletzt
    gearbeitet wurde — richtig gerechnet, falsch adressiert, und der Slicer
    lehnt den Prozess als unverträglich ab. Leer heißt „von früher", dann wird
    nicht verglichen: eine Einstellung aus einer älteren Version ist keine
    falsche."""
    slicer_filament_per_material: dict[str, str] = field(default_factory=dict)
    """Welche Spule zuletzt für welches Material gewählt wurde (§29).

    Solidon kennt „petg"; im Bestand des Slicers liegen sieben davon, und die
    fahren verschieden — PETG PRO 5 mm³/s, PETG HF 18. Geraten wird das nicht
    (eine falsche Vorauswahl sieht aus wie eine Entscheidung), aber wer es
    einmal gesagt hat, soll es nicht bei jedem Projekt wiederholen. Der eine
    zuletzt benutzte Wert daneben reichte dafür nicht: er galt über alle
    Materialien hinweg, und nach einem TPU-Teil stand er beim nächsten PETG."""
    window_geometry: str = ""
    """Größe und Lage des Fensters beim letzten Schließen, als Hex aus
    ``saveGeometry``. Leer heißt: erster Start, dann bildschirmfüllend —
    danach findet jeder das Fenster wieder, wie er es verlassen hat."""
    support_contact: str = ""
    """Die Rückadresse aus dem Rückmeldungsdialog (§37.2).

    Freiwillig und leer, bis jemand eine einträgt: Ohne sie geht die
    Rückmeldung trotzdem raus, es kommt nur keine Antwort zurück. Gemerkt
    wird sie, weil niemand seine Adresse zweimal tippen möchte — und sie
    steht hier und nicht im Schlüsselbund, weil eine E-Mail-Adresse kein
    Zugangsdatum ist."""
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
    auto_accept_reversible: bool = True
    """§26.5: ein Vorschlag aus eindeutig umkehrbaren Operationen wird ohne
    Nachfrage übernommen — Regel 19 kennt keine Bestätigung vor rücknehmbaren
    Handlungen. Abschaltbar, denn es ändert das gefühlte Verhalten des Chats;
    die vier Bedingungen prüft ``agent_apply.auto_acceptable``."""

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
