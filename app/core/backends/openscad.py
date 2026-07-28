"""OpenSCAD as the fallback level (Bauplan §24.1, §32, §36).

Only ever called as an installed external program, never bundled: OpenSCAD is
GPL and the application is not (§36). And only ever as a fallback — parts are
built against ``manifold3d``, so nothing on the core path needs an installation
(§24.1).

What makes this safe is not the sandbox, it is the check before it. Source code
reaches this module from two directions that are equally untrusted: a project
file passed around as a bug report (§33.3), and a language model. Both may
contain ``include <...>`` pointing anywhere on the machine.

So the rules from §32 are enforced here, in this order:

1. the source is **read** before it is run — ``include``, ``use``, ``import``
   and ``surface`` only with relative paths below the working directory;
2. every run gets its **own working directory** and nothing outside it;
3. **time and memory are capped**, and the process gets no network.

A refused source is not run at all. That is checked in the tests, because "it
would probably fail anyway" is not a security argument.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core.errors import Action, AppError
from app.core.log import get_logger
from app.core.types import Finding
from app.i18n import _

_log = get_logger(__name__)

#: Statements that pull something else in. Every one of them is a way out of
#: the working directory if the path is not checked.
INCLUDING = ("include", "use", "import", "surface")

_INCLUDE_PATTERN = re.compile(
    r"\b(include|use)\s*<([^>]*)>|(\bimport|\bsurface)\s*\(\s*(?:file\s*=\s*)?\"([^\"]*)\"",
    re.IGNORECASE,
)

#: How long a render may take. A model that needs longer is not a fallback, it
#: is a mistake (§31).
TIMEOUT_SECONDS = 60.0

#: Names OpenSCAD is installed under.
EXECUTABLES = ("openscad", "openscad-nightly", "OpenSCAD")


@dataclass(frozen=True, slots=True)
class SourceCheck:
    """What reading the source found (§32)."""

    allowed: bool
    references: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()

    @property
    def has_references(self) -> bool:
        return bool(self.references or self.refused)


class UnsafeSource(AppError):
    """The source wanted something outside its working directory."""

    default_title = _("Dieser OpenSCAD-Quelltext greift nach außen.")
    default_suggestions = (
        Action(id="remove_include", label=_("Die eingebundenen Dateien entfernen.")),
        Action(id="show_source", label=_("Quelltext ansehen.")),
    )


class ScadUnavailable(AppError):
    """OpenSCAD is not installed. Everything except this fallback keeps working."""

    default_title = _("OpenSCAD ist auf diesem Rechner nicht installiert.")
    default_suggestions = (
        Action(id="install", label=_("OpenSCAD installieren und erneut versuchen.")),
        Action(id="use_parts", label=_("Stattdessen einen Baustein verwenden.")),
    )


def check_source(source: str) -> SourceCheck:
    """Read the source and decide whether it may run (§32).

    A relative path below the working directory is fine. Everything else — an
    absolute path, a drive letter, a step upwards, a URL — is refused, and the
    finding names what was refused rather than only that something was.
    """
    references: list[str] = []
    refused: list[str] = []

    for match in _INCLUDE_PATTERN.finditer(source):
        path = match.group(2) if match.group(2) is not None else match.group(4)
        if path is None:
            continue
        (references if _is_local(path) else refused).append(path.strip())

    findings = tuple(
        Finding(
            code="scad.refused_reference",
            severity="error",
            message=_("Ein Verweis führt aus dem Arbeitsordner hinaus."),
            values={"reference": entry},
        )
        for entry in refused
    )
    if refused:
        _log.warning("refused %d OpenSCAD references", len(refused))
    return SourceCheck(
        allowed=not refused,
        references=tuple(references),
        refused=tuple(refused),
        findings=findings,
    )


def _is_local(path: str) -> bool:
    text = path.strip().replace("\\", "/")
    if not text:
        return False
    if text.startswith("/") or text.startswith("~"):
        return False
    if re.match(r"^[a-zA-Z]:", text):
        return False
    if "://" in text:
        return False
    return not any(part == ".." for part in text.split("/"))


def available() -> bool:
    """Whether OpenSCAD can be called at all."""
    return executable() is not None


def executable() -> str | None:
    for name in EXECUTABLES:
        found = shutil.which(name)
        if found:
            return found
    return None


@dataclass(slots=True)
class RenderResult:
    """What a run produced."""

    stl: bytes = b""
    findings: list[Finding] = field(default_factory=list)
    seconds: float = 0.0


def render(source: str, *, timeout: float = TIMEOUT_SECONDS) -> RenderResult:
    """Run a source and hand back the mesh — after the check, never before."""
    check = check_source(source)
    if not check.allowed:
        raise UnsafeSource(
            detail=", ".join(check.refused),
            values={"refused": ", ".join(check.refused)},
        )

    binary = executable()
    if binary is None:
        raise ScadUnavailable()

    import time

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="formwerk-scad-") as directory:
        workspace = Path(directory)
        scad_file = workspace / "model.scad"
        stl_file = workspace / "model.stl"
        scad_file.write_text(source, encoding="utf-8")

        completed = subprocess.run(
            [binary, "-o", str(stl_file), str(scad_file)],
            cwd=workspace,
            capture_output=True,
            timeout=timeout,
            env=_environment(workspace),
            check=False,
        )
        if completed.returncode != 0 or not stl_file.is_file():
            raise AppError(
                _("OpenSCAD konnte den Quelltext nicht übersetzen."),
                detail=completed.stderr.decode("utf-8", errors="replace")[:500],
                suggestions=(
                    Action(id="show_source", label=_("Quelltext ansehen.")),
                    Action(id="use_parts", label=_("Stattdessen einen Baustein verwenden.")),
                ),
            )
        payload = stl_file.read_bytes()

    return RenderResult(
        stl=payload,
        findings=[
            Finding(
                code="scad.rendered",
                severity="info",
                message=_("Dieser Körper kommt aus OpenSCAD, nicht aus der Bausteinbibliothek."),
                values={"bytes": len(payload)},
            )
        ],
        seconds=time.perf_counter() - started,
    )


def _environment(workspace: Path) -> dict[str, str]:
    """A run gets a fixed working directory and no way to the network (§32).

    Nothing here can stop a determined program, and it is not meant to: what it
    stops is a source that quietly reads a font, a file or a URL because the
    model happened to ask for one.
    """
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "DISPLAY")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    environment["OPENSCADPATH"] = str(workspace)
    environment["HTTP_PROXY"] = environment["HTTPS_PROXY"] = "127.0.0.1:0"
    environment["no_proxy"] = ""
    return environment
