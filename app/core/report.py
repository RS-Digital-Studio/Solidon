"""Error reports (Bauplan §37.2, §33.3).

No telemetry. Nothing leaves this machine unless the user sends it themselves —
that is the whole difference between a report and the thing the plan forbids.

What the dialog offers is a folder with three things: the error text, the
version data, and on request the project container. The container reproduces
the error exactly, including seeds and fallback stages (§16.2) — and it
contains the geometry, which is why the offer says so plainly rather than
quietly attaching it.
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

#: Where a report is put together. Next to the projects, not in a temp folder —
#: the user has to be able to find it again.
REPORT_DIRNAME = "reports"

#: How much of the log travels along. The last few hundred lines carry the run
#: that failed; the rest is yesterday.
LOG_LINES = 400


@dataclass(slots=True)
class ErrorReport:
    """One report, before it is written anywhere."""

    summary: str
    detail: str = ""
    traceback: str = ""
    include_project: bool = False
    include_log: bool = True
    files: list[Path] = field(default_factory=list)

    @property
    def contains_geometry(self) -> bool:
        """§37.2: the offer has to say that the model travels along."""
        return self.include_project


def environment() -> dict[str, str]:
    """Version data — what a report needs to be reproducible at all."""
    import importlib.metadata as metadata

    versions: dict[str, str] = {}
    for name in ("trimesh", "manifold3d", "numpy", "scipy", "shapely", "PySide6"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover - depends on the install
            versions[name] = "-"

    return {
        "app": f"{APP_NAME} {APP_VERSION}",
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "language": get_language(),
        **versions,
    }


def as_text(report: ErrorReport) -> str:
    """The report as one readable text — the part that goes into an email."""
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
    """Put the report together in a folder and return it.

    Nothing is sent. The folder is opened for the user, and what happens next is
    their decision (§37.2).
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
    """The tail of the log. It never left the machine before, and it only does
    now because someone attached it themselves (§33.2)."""
    source = log_path()
    if not source.is_file():
        return
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:]
    (target / "protokoll.txt").write_text("\n".join(lines), encoding="utf-8")
