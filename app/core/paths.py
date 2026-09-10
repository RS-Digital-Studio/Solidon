"""Wo Nutzerdaten liegen (Bauplan §38).

Alles, was die Anwendung schreibt, bleibt auf diesem Rechner: Profile,
Protokoll, Cache, eigene Bausteine. Ohne Zusatzabhängigkeit aufgelöst, damit
die Lizenzliste kurz bleibt.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from app.branding import APP_NAME, APP_VENDOR, APP_VERSION

_windows_ctypes: Any = None
_windows_msvcrt: Any = None
if os.name == "nt":
    import ctypes as _native_ctypes
    import msvcrt as _native_msvcrt

    _windows_ctypes = _native_ctypes
    _windows_msvcrt = _native_msvcrt


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


def opened_path(descriptor: int) -> Path | None:
    """Der kanonische Pfad hinter einem offenen Handle, oder ``None``.

    Zwei Stellen stellen dieselbe Frage, und beide fragen sie aus einem
    Sicherheitsgrund: ``scene.project`` will wissen, wohin eine verknüpfte
    Quelle wirklich zeigt, ``updates`` dasselbe für den Deskriptor, den es an
    den Installer weiterreicht. Sie standen bis zum 10.09.2026 zweimal da, und
    von zwei Kopien altert immer eine — hier war es die in ``updates``, der die
    Längengegenprobe unter Windows fehlte (siehe unten).

    ``None`` heißt „diese Plattform sagt es nicht" — und **nur** das. Eine
    Abfrage, die schiefgeht, wirft, weil die Aufrufer aus ``None`` „nicht
    prüfbar, also weiter" machen: ``updates`` hängt drei Sicherheitsprüfungen
    an ``if opened is not None and opened != …``. Ein ``None`` an der falschen
    Stelle schaltet sie ab, statt abzuweisen.

    Das war schon einmal beinahe der Fall: Die zusammengeführte Fassung gab
    zunächst auch beim gewachsenen Pfad ``None`` zurück. Die alte Fassung in
    ``updates`` warf dort **implizit** — sie nahm den abgeschnittenen Namen und
    lief damit in ``resolve(strict=True)``, das ihn nicht fand. Aus einer
    Abweisung wäre so ein stilles Durchlassen geworden; gefunden hat das ein
    Review am selben Tag.
    """
    if os.name == "nt":
        kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFinalPathNameByHandleW.argtypes = (
            _windows_ctypes.c_void_p,
            _windows_ctypes.c_wchar_p,
            _windows_ctypes.c_uint32,
            _windows_ctypes.c_uint32,
        )
        kernel32.GetFinalPathNameByHandleW.restype = _windows_ctypes.c_uint32
        handle = _windows_ctypes.c_void_p(_windows_msvcrt.get_osfhandle(descriptor))
        length = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not length:
            return None
        buffer = _windows_ctypes.create_unicode_buffer(length + 1)
        written = kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        # **Der zweite Wert wird gegen die Puffergröße gehalten, nicht nur
        # gegen Null.** Zwischen den beiden Aufrufen kann der Pfad wachsen —
        # ein umbenannter Ordner darüber genügt. Dann meldet der zweite Aufruf
        # nicht „geschrieben", sondern „so viel bräuchte ich", also einen Wert
        # ab Puffergröße, und ``buffer.value`` trägt einen abgeschnittenen
        # Pfad. Wer den ungeprüft weiterreicht, vergleicht eine gekürzte
        # Zeichenkette mit einem Ordner und bekommt die falsche Antwort auf
        # eine Sicherheitsfrage.
        #
        # **Geworfen und nicht `None`**, weil `None` bei den Aufrufern „nicht
        # prüfbar, also weiter" heißt. Die alte Fassung in `updates` warf hier
        # ohne es zu wissen: Sie nahm den abgeschnittenen Namen und lief damit
        # in `resolve(strict=True)`, das ihn nicht fand.
        if not written or written >= len(buffer):
            raise OSError(
                _windows_ctypes.get_last_error(),
                "Der Pfad hinter dem Handle ließ sich nicht vollständig lesen",
            )
        name = buffer.value
        if name.startswith("\\\\?\\UNC\\"):
            name = "\\\\" + name[8:]
        elif name.startswith("\\\\?\\"):
            name = name[4:]
        return Path(name).resolve(strict=True)

    # **Gefragt wird, ob der Deskriptorpfad wirklich woandershin zeigt.**
    # ``/dev/fd/N`` gibt es auch auf dem Mac, aber dort ist es kein Symlink:
    # ``resolve()`` gibt ``/dev/fd/N`` zurück, und der liegt unter keinem
    # Projektordner — jede verknüpfte Quelle galt damit als absoluter Pfad
    # (Tag-Lauf 0.3.0, 02.09.2026, acht Tests). Geprüft wird die Eigenschaft
    # und nicht die Plattform: ``if sys.platform == "darwin"`` vor dieser
    # Schleife macht den Rest auf dem Mac zu totem Code, und das meldet mypy
    # dort als Fehler — auf Windows sieht man es nie (``mypy --platform darwin``).
    for descriptor_root in (Path("/proc/self/fd"), Path("/dev/fd")):
        candidate = descriptor_root / str(descriptor)
        if not candidate.exists():
            continue
        resolved = candidate.resolve(strict=True)
        if resolved != candidate:
            return resolved
    if sys.platform == "darwin":
        # F_GETPATH (50) nennt den Pfad, den der Mac nicht verlinkt.
        fcntl = importlib.import_module("fcntl")

        # Genau 1024 Byte: Pythons ``fcntl`` nimmt nicht mehr als das
        # (``FCNTL_BUFSZ``) und wirft sonst „fcntl string arg too long", bevor
        # der Systemaufruf läuft — 4096 kosteten 23 rote Tests im Tag-Lauf 3
        # (03.09.2026). Und 1024 ist zugleich, was Darwin für ``F_GETPATH``
        # verlangt: ein Puffer von ``MAXPATHLEN``, und das ist dort PATH_MAX.
        raw = fcntl.fcntl(descriptor, 50, b"\0" * 1024)
        return Path(raw.split(b"\0", 1)[0].decode()).resolve(strict=True)
    return None
