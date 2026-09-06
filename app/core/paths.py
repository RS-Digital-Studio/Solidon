"""Wo Nutzerdaten liegen (Bauplan §38).

Alles, was die Anwendung schreibt, bleibt auf diesem Rechner: Profile,
Protokoll, Cache, eigene Bausteine. Ohne Zusatzabhängigkeit aufgelöst, damit
die Lizenzliste kurz bleibt.
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import suppress
from pathlib import Path

from app.branding import APP_NAME, APP_VENDOR, APP_VERSION


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


def results_cache_dir() -> Path:
    """Der Ergebnis-Cache über den Op-Hash (§38) — eigener Ordner, je Fassung.

    Zwei Gründe, warum er nicht in :func:`user_cache_dir` selbst liegt.

    **Er hat Nachbarn.** In derselben Wurzel wohnen die Arbeitsordner der
    externen Programme, die heruntergeladenen Update-Pakete und der
    Stil-Cache. Der Ergebnis-Cache
    führt ein Budget und räumt auf, wenn es reißt — täte er das in der Wurzel,
    zählte er fremde Daten in sein Budget und löschte fremde Ordner, um es
    einzuhalten. Ein Update-Paket, das gerade geprüft werden soll, ist kein
    Platz für Netze.

    **Er überlebt sonst ein Update.** Der Schlüssel eines Eintrags ist der
    Operations-Hash, und der nimmt Op-Name, Parameter, Eingänge, Profil,
    Qualität und Startwert — nicht die *Umsetzung*. Im Speicher ist das
    gleichgültig, dort lebt der Cache so lang wie die Sitzung. Auf der Platte
    hieße es: Die nächste Fassung behebt eine Boolesche Rückfallstufe, und der
    Cache liefert weiter das Netz, das die alte gerechnet hat. Deshalb steht
    die Fassung im Pfad. Ein Update fängt kalt an — richtig, und billiger als
    jede Prüfung, die dasselbe erkennen müsste.

    Zwei Dinge ändern den Ordner außerdem, und jedes hat seinen Grund bei sich:
    der Stand des Kerns, wenn aus den Quellen gefahren wird
    (:func:`_build_stamp`), und der Stand der eigenen Bausteine
    (:func:`_own_parts_stamp`). Beides ist Code, der ein Ergebnis rechnet und
    den keine Fassungsnummer begleitet.
    """
    return user_cache_dir() / "results" / (APP_VERSION + _build_stamp() + _own_parts_stamp())


def _build_stamp() -> str:
    """Ein Kürzel für den Stand des Kerns, wenn aus den Quellen gefahren wird.

    Die Fassung im Pfad hält für einen Kunden: Er bekommt neuen Code nur mit
    einem Update, und ein Update hebt `APP_VERSION`. Sie hält **nicht** für
    den, der aus dem Arbeitsbaum fährt — und das ist heute der einzige
    Benutzer. Zwischen zwei Starts wird hier eine Boolesche Rückfallstufe
    geändert, eine Erkennung berichtigt, ein Netzweg umgebaut, und `APP_VERSION`
    bleibt „0.1.2". Ohne diese Zeile liefert der Cache danach das Netz, das der
    alte Code gerechnet hat, und die Berichtigung wäre stillschweigend
    ausgehebelt. Genau der Fall, den die Fassung im Pfad verhindern sollte, nur
    auf der Maschine, auf der er wirklich vorkommt.

    Genommen wird die jüngste Änderungszeit unter ``app/core`` — dort steht
    alles, was ein Ergebnis rechnet (die Oberfläche rechnet nichts, Regel 2).
    Eine Änderung setzt die Zeit einer Datei auf jetzt, und jetzt ist größer als
    jedes vorherige Maximum; auch ein Zurücknehmen über Git zählt so. Ein Gang
    über die 156 Dateien kostet gemessen eine Millisekunde.

    Ein **gebautes** Paket überspringt das: Dort gibt es keine Quelldateien, die
    sich ändern könnten, und die Fassung ist die ganze Wahrheit.
    """
    if getattr(sys, "frozen", False):
        return ""
    core = Path(__file__).resolve().parent
    newest = 0
    for path in core.rglob("*.py"):
        with suppress(OSError):
            newest = max(newest, path.stat().st_mtime_ns)
    if not newest:
        return ""
    return "+" + hashlib.sha256(str(newest).encode("utf-8")).hexdigest()[:6]


def _own_parts_stamp() -> str:
    """Ein Kürzel für den Stand der eigenen Bausteine, oder nichts.

    Die Fassung im Pfad deckt alles ab, was mit einer Auslieferung kommt —
    Operationen, mitgelieferte Bausteine, Bibliotheken. Sie deckt **nicht** ab,
    was der Nutzer selbst schreibt: Ein eigener Baustein aus
    ``<Nutzerdaten>/parts/`` (§24.5) — als ``.py`` oder als Rezept unter
    ``recipes/*.json`` — ist eine Operation wie jede andere, und ändert er
    sich, bleiben Op-Name und Parameter gleich. Der Operations-Hash sieht die
    Änderung nicht.

    Im Speicher war das gleichgültig, dort lebt der Cache so lang wie die
    Sitzung. Auf der Platte hieße es: Wer an seinem eigenen Baustein ein Maß
    ändert, bekommt beim nächsten Öffnen weiter die alte Geometrie — und
    gemeldet würde es nicht. ``changed_since_library`` vergleicht gepflegte
    Änderungsverläufe, und die pflegt beim Ausprobieren niemand.

    Deshalb hängt der Stand der eigenen Bausteine am Ordnernamen. Wer keine
    hat — die meisten —, merkt davon nichts: Das Kürzel ist leer, der Pfad
    bleibt die Fassung. Wer an einem arbeitet, fängt bei jedem Speichern kalt
    an. Das ist der teurere Weg und der richtige: Ein Cache, der die eigene
    Änderung verschweigt, ist schlimmer als einer, der sie neu rechnet. Die
    alten Ordner räumt ``drop_other_versions`` weg.
    """
    folder = user_parts_dir()
    if not folder.is_dir():
        return ""
    stamps = []
    # ``rglob`` und nicht ``glob``: Bausteine liest der Lader oben auf, aber ein
    # Baustein darf einen Helfer daneben legen, und der rechnet mit.
    #
    # **Und ``.json`` gehört dazu, nicht nur ``.py``.** Ein Rezept (§24.5) ist
    # eine Datendatei unter ``recipes/`` und wird trotzdem eine Operation wie
    # jede andere. Wer daran ein Maß ändert, ändert weder Op-Name noch
    # Parameter — der Operations-Hash sieht nichts, und der Plattencache gab
    # weiter die alte Geometrie heraus. Genau der Fall, gegen den dieser
    # Stempel gebaut ist, nur in der anderen Dateiendung.
    for entry in sorted(path for suffix in ("*.py", "*.json") for path in folder.rglob(suffix)):
        with suppress(OSError):
            state = entry.stat()
            stamps.append(f"{entry.name}:{state.st_mtime_ns}:{state.st_size}")
    if not stamps:
        return ""
    return "+" + hashlib.sha256("|".join(stamps).encode("utf-8")).hexdigest()[:6]


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


#: Wohin der Installer seine Sprachwahl legt, neben die Anwendung.
#:
#: Eine Zeile, ein Sprachkürzel. Der Installer fragt sechs Sprachen ab und
#: zeigt sich selbst darin; bis zum 25.08.2026 war das die einzige Wirkung —
#: die Anwendung startete danach auf Deutsch, gleich was gewählt wurde, und
#: fragte in „Erste Schritte" ein zweites Mal.
INSTALL_LANGUAGE_FILE = "install-language.txt"


def installed_language() -> str | None:
    """Was der Installer gewählt hat, oder ``None``.

    Die Datei liegt neben der Anwendung und nicht im Nutzerprofil: Sie gehört
    zur Installation und nicht zum Nutzer, und sie wird genau einmal gelesen —
    beim allerersten Start, bevor es Einstellungen gibt. Wer die Sprache danach
    umstellt, hat die Einstellungen, und die haben Vorrang.

    **Sie steht im Kern und nicht in der Oberfläche, wo sie entstanden ist.**
    Dieselbe Frage stellt die Kommandozeile, und die darf ``app/ui`` nicht
    anfassen (Regel 1) — für sie war die Antwort damit unerreichbar, und ein
    spanischer Kunde bekam beim allerersten Aufruf deutsche Hilfe- und
    Fehlertexte, obwohl er den Installer auf Spanisch gestellt hatte. Eine
    zweite Fassung daneben wäre der nächste Fehler: Von zwei Kopien altert
    immer eine.

    Geprüft wird das Kürzel gegen die vorliegenden Kataloge. Ein Kürzel ohne
    Katalog ist keine Wahl, sondern eine Anwendung, die nichts zu sagen hätte;
    ``ValueError`` fängt dabei den ``UnicodeDecodeError`` einer beschädigten
    Datei mit ab — die freundliche Richtung ist hier die Quellsprache.
    """
    # Erst beim Aufruf: ``app.i18n.catalog`` liest über ``app.core.log`` dieses
    # Modul, und ein Import oben wäre ein Kreis.
    from app.i18n.catalog import available_languages

    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        # Im Quellbaum: das Projektverzeichnis, damit sich die Sache von Hand
        # ausprobieren lässt, ohne ein Paket zu bauen.
        base = Path(__file__).resolve().parent.parent.parent
    try:
        text = (base / INSTALL_LANGUAGE_FILE).read_text(encoding="utf-8").strip()
    except OSError, ValueError:
        return None
    return text if text in set(available_languages()) else None


def ensure_dir(path: Path) -> Path:
    """Legt ein Verzeichnis samt Eltern an und gibt es zurück."""
    path.mkdir(parents=True, exist_ok=True)
    return path
