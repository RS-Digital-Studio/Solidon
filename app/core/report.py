"""Fehlerberichte (Bauplan §37.2, §33.3).

Keine Telemetrie. Nichts verlässt diesen Rechner, außer der Nutzer sendet es
selbst — das ist der ganze Unterschied zwischen einem Bericht und dem, was der
Bauplan verbietet.

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
    include_project: bool = False
    include_log: bool = True
    files: list[Path] = field(default_factory=list)

    @property
    def contains_geometry(self) -> bool:
        """§37.2: das Angebot muss sagen, dass das Modell mitreist."""
        return self.include_project


def environment() -> dict[str, str]:
    """Versionsdaten — was ein Bericht braucht, um überhaupt reproduzierbar
    zu sein."""
    import importlib.metadata as metadata

    versions: dict[str, str] = {}
    for name in ("trimesh", "manifold3d", "numpy", "scipy", "shapely", "PySide6"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover - hängt an der Installation
            versions[name] = "-"

    return {
        "app": f"{APP_NAME} {APP_VERSION}",
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "language": get_language(),
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
