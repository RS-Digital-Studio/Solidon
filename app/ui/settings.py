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

# ``installed_language`` liegt im Kern, weil die Kommandozeile dieselbe Frage
# stellt und ``app/ui`` nicht anfassen darf (Regel 1). Hier steht der Name
# weiter im Modul, damit ``initial_language`` ihn wie bisher findet.
from app.core.paths import ensure_dir, installed_language, user_config_dir
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
    check_for_updates: bool = True
    """§37.2: ein Hinweis, nie eine selbsttätige Aktualisierung.

    **An, seit dem 23.08.2026.** Der Anlass ist ein Datum: Die Demo endet am
    30.10.2026, und am Tag des Artikels bei 3druck.com wurden 140 Pakete
    geladen. Stand der Schalter weiter aus, liefen diese Installationen an
    jenem Tag ab, ohne dass die Anwendung je einen Weg zur nächsten Fassung
    gezeigt hätte — entschieden von Robert: „wenn man die app startet sollte
    überprüft werden ob eine neue version vorhanden ist und diese dann bei
    bestätigung geladen werden."

    Was §37.2 verlangt, bleibt unangetastet: **Die Bestätigung gilt dem Laden,
    nicht der Prüfung.** Geladen wird auf Klick, gestartet erst nach dem
    Schließen des Fensters. Selbsttätig ist nur die Frage, ob es etwas Neues
    gibt."""
    update_default_lifted: bool = False
    """Ob die Vorgabe oben schon einmal in eine bestehende Datei getragen wurde.

    **Ohne dieses Feld erreicht die neue Vorgabe niemanden.** ``save_settings``
    schreibt jedes Feld, ``load_settings`` liest jedes vorhandene zurück —
    jede Installation, die einmal beendet wurde, trägt ``"check_for_updates":
    false`` wörtlich in ihrer Datei, und der Wert dort schlägt jede Vorgabe im
    Code. Wer nur die Vorgabe umlegt, erreicht ausschließlich Rechner, auf
    denen die Anwendung noch nie gelaufen ist.

    Der Merker unterscheidet „nie gefragt" von „bewusst aus": Angehoben wird
    genau einmal, danach gilt wieder, was der Nutzer einstellt."""
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


def system_language() -> str | None:
    """Die Sprache des Betriebssystems, wenn ein Katalog dazu vorliegt.

    Gefragt wird ``QLocale.system().uiLanguages()`` und nicht nur ``name()``:
    Ein deutsches Windows meldet dort ``['de-Latn-DE', 'de-DE', 'de-Latn',
    'de']``, und gebraucht wird davon der Anfang. Ein System, dessen Sprache
    die Anwendung nicht spricht, bekommt ``None`` und damit die Quellsprache.
    """
    from PySide6.QtCore import QLocale

    from app.i18n.catalog import available_languages

    known = set(available_languages())
    for tag in QLocale.system().uiLanguages():
        code = tag.replace("_", "-").split("-")[0].lower()
        if code in known:
            return code
    return None


def initial_language() -> str:
    """Womit die Anwendung startet, wenn sie noch nie gestartet wurde.

    Drei Quellen in dieser Reihenfolge, und die Reihenfolge ist die Aussage:
    Was der Nutzer im Installer **gewählt** hat, wiegt schwerer als das, was
    sein System spricht — wer auf einem deutschen Windows den Installer auf
    Spanisch stellt, meint Spanisch. Erst wenn beides nichts hergibt, bleibt
    die Quellsprache.
    """
    from app.i18n.catalog import available_languages

    known = set(available_languages())
    chosen = installed_language()
    if chosen and chosen in known:
        return chosen
    return system_language() or SOURCE_LANGUAGE


def load_settings() -> UiSettings:
    path = settings_path()
    if not path.is_file():
        # **Der allererste Start**, und nur er: Hier gibt es noch keine Wahl
        # des Nutzers, die man überschreiben könnte.
        return UiSettings(language=initial_language())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = UiSettings(**{key: data[key] for key in data if key in UiSettings.__slots__})
        # **Geprüft wird am rohen Wörterbuch, nicht am geladenen Feld.** Fehlt
        # der Schlüssel, setzt die Dataclass ihre Vorgabe ein, und die ist von
        # „steht auf false" nicht mehr zu unterscheiden. Nur die Datei weiß,
        # ob sie aus einer Fassung stammt, die das Feld noch nicht kannte.
        if "update_default_lifted" not in data:
            settings.check_for_updates = True
            settings.update_default_lifted = True
        return settings
    except (OSError, ValueError, TypeError) as problem:
        _log.warning("could not read settings, starting from defaults: %s", problem)
        return UiSettings()


def save_settings(settings: UiSettings) -> Path:
    path = settings_path()
    ensure_dir(path.parent)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path
