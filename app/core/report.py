"""Fehlerberichte (Bauplan §37.2).

Keine Telemetrie. Nichts verlässt diesen Rechner, außer der Nutzer sendet es
selbst — das ist der ganze Unterschied zwischen einem Bericht und dem, was der
Bauplan verbietet.

Dieses Modul **schreibt** den Bericht und schickt ihn nie: Der Ordner ist der
Weg, der ohne Netz auskommt. Wer ihn stattdessen abschicken will, geht über
:mod:`app.core.support` — dort hängt der Versand an einem Knopf, und nur dort.

Was der Dialog anbietet, ist ein Ordner mit drei Dingen: dem Fehlertext, den
Versionsdaten und auf Wunsch dem Projektcontainer. Der Container reproduziert
den Fehler exakt, samt Startwerten und Rückfallstufen (§16.2) — und er enthält
die Geometrie, weshalb das Angebot es klar sagt, statt sie still anzuhängen.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from app.branding import APP_NAME, APP_VERSION
from app.core.log import get_logger, log_path
from app.core.paths import ensure_dir, user_data_dir
from app.i18n import get_language, tr

_log = get_logger(__name__)

#: Wo ein Bericht zusammengestellt wird. Neben den Projekten, nicht in einem
#: Temp-Ordner — der Nutzer muss ihn wiederfinden können.
REPORT_DIRNAME = "reports"

#: Wie viel Protokoll mitreist. Die letzten paar hundert Zeilen tragen den
#: Lauf, der scheiterte; der Rest ist gestern.
LOG_LINES = 400


@dataclass(slots=True)
class ErrorReport:
    """Ein Bericht, bevor er irgendwohin geschrieben wird."""

    summary: str
    detail: str = ""
    traceback: str = ""
    #: Der Steckbrief der Szene (§23) — Objekte mit Maßen und Merkmalen,
    #: Parameter, Passungen und der Verlauf mit seinen Werten.
    #:
    #: **Der Mittelweg zwischen „nichts" und „das ganze Modell".** Ein
    #: Kundenprotokoll vom 23.08.2026 sagte zwar, dass die Auswertung anhielt,
    #: aber nicht, woran die Szene stand: Ein Bildschirmfoto zeigte drei Wülste
    #: mit 34,09, 34,06 und 34,03 mm, und ob das drei Kanten sind oder eine
    #: dreimal erkannte, war ohne die Maße nicht zu entscheiden. Die
    #: Projektdatei hätte es gesagt — sie enthält aber die Geometrie, und
    #: darum reist sie nur auf ausdrücklichen Wunsch mit (§37.2). Der
    #: Steckbrief ist Text: Er nennt Maße und Merkmale und gibt kein Modell
    #: preis.
    digest: str = ""
    include_project: bool = False
    include_log: bool = True
    files: list[Path] = field(default_factory=list)

    @property
    def contains_geometry(self) -> bool:
        """§37.2: das Angebot muss sagen, dass das Modell mitreist."""
        return self.include_project


#: Die Bibliotheken, deren Fassung ein Bericht nennt. Reihenfolge wie im Text.
REPORTED_PACKAGES: Final = ("trimesh", "manifold3d", "numpy", "scipy", "shapely", "PySide6")


def _version_of(name: str) -> str:
    """Die Fassung eines Pakets — erst am Modul, dann an seinen Metadaten.

    **Die Reihenfolge ist der ganze Punkt.** Hier stand nur
    ``importlib.metadata.version``, und das liest die ``.dist-info``-Ordner
    neben dem Paket. Die reisen in einem PyInstaller-Bau **nicht** mit: Im
    Bericht eines Kunden vom 27.08.2026 stand

        trimesh: 5.0.0 · numpy: 2.5.2
        manifold3d: - · scipy: - · shapely: - · PySide6: -

    Vier von sechs als „nicht installiert" — bei einem Programm, das ohne
    PySide6 kein Fenster öffnet. `trimesh` und `numpy` standen nur da, weil
    die Spec ihre Datendateien ausdrücklich einsammelt und die Metadaten
    dabei mitkommen.

    Das ist die gefährlichste Sorte Fehler in einem Fehlerbericht: **Er sagt
    nicht „unbekannt", er sagt etwas Falsches.** Wer damit eine Diagnose
    beginnt, sucht an einer Stelle, an der nichts ist — genau das ist beim
    Lesen dieses Berichts passiert.

    Fünf der sechs Pakete tragen ihre Fassung als ``__version__`` am Modul,
    und das überlebt jeden Bau. ``manifold3d`` hat keine; dort bleibt es beim
    Metadatenweg, und in einem Bau ohne sie beim ehrlichen Strich.
    """
    import importlib
    import importlib.metadata as metadata

    try:
        module = importlib.import_module(name)
    except Exception:  # pragma: no cover - ein fehlendes Paket ist der Normalfall dieses Zweigs
        module = None
    if module is not None:
        runtime = getattr(module, "__version__", "")
        if isinstance(runtime, str) and runtime:
            return runtime

    try:
        return metadata.version(name)
    except Exception:  # pragma: no cover - hängt an der Installation
        return "-"


#: Was die Fenstersitzung eines Linux-Rechners beschreibt. Auf Windows und
#: macOS ist nichts davon gesetzt, und dann steht die Zeile auch nicht da.
#:
#: **Warum sie überhaupt dasteht.** Simon Wenger meldete am 27.08.2026: „Es
#: war schwierig Solidon3D zum Laufen zu bringen. Es waren viele tweaks nötig,
#: wie auf x11 umschalten und weitere. Bis jetzt geht einiges nicht. So muss
#: ich z.B. diesen Text in einer anderen Anwendung schreiben und nach Solidon3D
#: copypasten." Sein Bericht enthielt alles über unsere Bibliotheken und nichts
#: über die Sitzung, in der das passierte — kein Wort darüber, ob Qt auf
#: Wayland oder über XWayland lief und welches Eingabemodul dabei aktiv war.
#:
#: Vier Variablen, die genau das beantworten, und keine davon kostet mehr als
#: einen Blick ins Environment. Der Kern liest sie selbst statt Qt zu fragen —
#: hier gibt es kein Qt (§8), und ``QT_QPA_PLATFORM`` sagt ohnehin, was der
#: Nutzer erzwungen hat, während Qt nur meldet, was daraus wurde.
SESSION_KEYS: Final = ("XDG_SESSION_TYPE", "QT_QPA_PLATFORM", "QT_IM_MODULE", "XCURSOR_SIZE")


def _session() -> dict[str, str]:
    """Wie die Fenstersitzung eingerichtet ist — nur, was wirklich dasteht."""
    import os

    found = {key.lower(): os.environ.get(key, "").strip() for key in SESSION_KEYS}
    if os.environ.get("WAYLAND_DISPLAY"):
        found.setdefault("xdg_session_type", "")
        found["xdg_session_type"] = found["xdg_session_type"] or "wayland (erkannt)"
    return {key: value for key, value in found.items() if value}


def environment() -> dict[str, str]:
    """Versionsdaten — was ein Bericht braucht, um überhaupt reproduzierbar
    zu sein."""
    versions = {name: _version_of(name) for name in REPORTED_PACKAGES}

    return {
        "app": f"{APP_NAME} {APP_VERSION}",
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "language": get_language(),
        **_session(),
        **versions,
    }


def as_text(report: ErrorReport) -> str:
    """Der Bericht als ein lesbarer Text — der Teil, der in eine E-Mail geht."""
    lines = [
        f"{APP_NAME} {APP_VERSION} — {tr('Fehlerbericht')}",
        datetime.now(UTC).isoformat(timespec="seconds"),
        "",
        report.summary,
    ]
    if report.detail:
        lines.extend(["", report.detail])
    if report.traceback:
        lines.extend(["", "--- traceback ---", report.traceback.strip()])

    if report.digest:
        lines.extend(["", "--- szene ---", report.digest.strip()])

    lines.extend(["", "--- system ---"])
    lines.extend(f"{name}: {value}" for name, value in environment().items())
    if report.contains_geometry:
        lines.extend(["", tr("Die Projektdatei liegt bei. Sie enthält die Geometrie des Modells.")])
    return "\n".join(lines)


def write(report: ErrorReport, project: Path | None = None, directory: Path | None = None) -> Path:
    """Stellt den Bericht in einem Ordner zusammen und gibt ihn zurück.

    Gesendet wird nichts. Der Ordner wird dem Nutzer geöffnet, und was dann
    passiert, ist seine Entscheidung (§37.2).
    """
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = (directory or user_data_dir() / REPORT_DIRNAME) / f"bericht-{stamp}"
    ensure_dir(target)

    (target / "bericht.txt").write_text(as_text(report), encoding="utf-8")

    if report.include_log:
        _copy_log(target)
    if report.include_project and project is not None and project.is_file():
        (target / project.name).write_bytes(project.read_bytes())
        report.files.append(target / project.name)

    _log.info("error report written to %s", target)
    return target


def _copy_log(target: Path) -> None:
    """Das Ende des Protokolls. Es hat den Rechner nie zuvor verlassen, und
    jetzt nur, weil jemand es selbst angehängt hat (§33.2)."""
    source = log_path()
    if not source.is_file():
        return
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:]
    (target / "protokoll.txt").write_text("\n".join(lines), encoding="utf-8")
