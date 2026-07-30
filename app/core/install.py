"""Installing what is missing, from inside the application (Bauplan §36, §38).

Formwerk ships without OpenSCAD, without a slicer and without a B-Rep kernel —
for licence reasons in the first two cases and for size in the rest (§36). That
is a good decision and a bad experience: somebody who wants a fillet should not
have to read a README to find out which package to install.

So this lists what is missing and installs it, and it does that under three
rules that are not negotiable:

* **The names are constants in this file.** Nothing that arrives from a model,
  a project file or a web page is ever passed to an installer.
* **Only official sources.** Python packages from the index the interpreter is
  already configured for, programs through the system's own package manager.
  Formwerk downloads no installers of its own.
* **Never unasked.** The list is shown, the button is pressed by a person. An
  application that installs software because it thinks it needs it has taken a
  decision that was not its to take.

Where an install is impossible — a packaged build has no pip, a machine without
winget has no package manager — the answer is the download page and a sentence
saying why, not a silent failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

from app.core import discover, tools
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

Kind = Literal["package", "program"]

#: How long an install may take before it is given up on. Package managers
#: download; a minute is not enough and an hour helps nobody.
TIMEOUT_SECONDS = 900.0

ProgressFn = Callable[[str], None]


def _silent(line: str) -> None:
    del line


@dataclass(frozen=True, slots=True)
class Requirement:
    """One thing Formwerk can use, and how it gets onto the machine."""

    id: str
    title: TranslatableText | str
    what_for: TranslatableText | str
    kind: Kind
    package: str = ""
    """Distribution name for pip, or the winget identifier for a program."""
    module: str = ""
    """What to import to find out whether it is there. Packages only."""
    url: str = ""
    """The official page, for when installing from here is not possible."""


#: Everything the application can install. Names are fixed here on purpose —
#: see the module docstring.
REQUIREMENTS: Final[tuple[Requirement, ...]] = (
    Requirement(
        id="brep",
        title="OpenCASCADE",
        what_for=_("Exakte Kanten: Fasen, Verrundungen und STEP (§30)."),
        kind="package",
        package="cadquery-ocp-novtk",
        module="OCP.BRepPrimAPI",
        url="https://github.com/CadQuery/OCP",
    ),
    Requirement(
        id="vhacd",
        title="V-HACD",
        what_for=_("Hinweis, wo ein Körper von selbst auseinanderfällt (§22.3)."),
        kind="package",
        package="vhacdx",
        module="vhacdx",
        url="https://github.com/trimesh/vhacdx",
    ),
    Requirement(
        id="keyring",
        title=_("Schlüsselbund"),
        what_for=_("Legt den Zugang zum Sprachmodell im System ab (§27)."),
        kind="package",
        package="keyring",
        module="keyring",
        url="https://github.com/jaraco/keyring",
    ),
    Requirement(
        id="openscad",
        title="OpenSCAD",
        what_for=_("Rückfallebene für Formen, für die es keinen Baustein gibt."),
        kind="program",
        package="OpenSCAD.OpenSCAD",
        url="https://openscad.org/downloads.html",
    ),
    Requirement(
        id="slicer",
        # Nicht „OrcaSlicer": erkannt wird jeder der üblichen Slicer, und wer
        # ElegooSlicer oder PrusaSlicer benutzt, soll hier nicht lesen, ihm
        # fehle ein Programm. Installiert wird OrcaSlicer, weil eine Vorgabe
        # sein muss — dranstehen tut das am Knopf.
        title=_("Slicer"),
        what_for=_("Für die Druckdatei und die Gegenprobe aus dem G-Code."),
        kind="program",
        package="SoftFever.OrcaSlicer",
        url="https://orcaslicer.com",
    ),
    Requirement(
        id="ollama",
        title="Ollama",
        what_for=_("Sprachmodell lokal, statt mit eigenem Schlüssel."),
        kind="program",
        package="Ollama.Ollama",
        url="https://ollama.com/download",
    ),
    Requirement(
        id="comfyui",
        title="ComfyUI",
        what_for=_("Mesh-Erzeugung aus Text oder Bild."),
        kind="program",
        package="",
        url="https://www.comfy.org/download",
    ),
)


@dataclass(frozen=True, slots=True)
class InstallResult:
    """What happened. ``output`` is the tail of what the installer said."""

    requirement: Requirement
    installed: bool
    output: str = ""
    reason: TranslatableText | str = ""


def present(requirement: Requirement) -> bool:
    """Ist es schon da?

    Pakete werden importiert, Programme gesucht. Bei einem Dienst zählt hier
    „auf dem Rechner" und nicht „läuft gerade" — sonst böte diese Liste an, ein
    ComfyUI ein zweites Mal zu installieren, das nur nicht gestartet ist.
    """
    if requirement.kind == "package":
        if not requirement.module:
            return False
        try:
            __import__(requirement.module)
        except Exception:  # a compiled extension fails in more ways than ImportError
            return False
        return True

    tool = tools.by_id(requirement.id)
    return tools.state_of(tool).installed if tool is not None else False


def location_of(requirement: Requirement) -> str:
    """Wo es liegt oder unter welcher Adresse es erreichbar ist — für die Zeile daneben."""
    tool = tools.by_id(requirement.id)
    if tool is None:
        return ""
    found = tool.path()
    if found is not None:
        return str(found)
    return tool.address()


def missing() -> list[Requirement]:
    """Everything that is not on this machine. Missing is normal, not an error."""
    return [entry for entry in REQUIREMENTS if not present(entry)]


def packaged() -> bool:
    """Is this the built application? Then there is no pip to install with."""
    return bool(getattr(sys, "frozen", False))


def winget() -> str | None:
    """The system package manager, if this system has the one we can drive."""
    return shutil.which("winget")


def installable(requirement: Requirement) -> bool:
    """Can this be installed from here at all?"""
    if not requirement.package:
        return False
    if requirement.kind == "package":
        return not packaged()
    return winget() is not None


def why_not(requirement: Requirement) -> TranslatableText | str:
    """The sentence that goes with a button that cannot be pressed (§33.1)."""
    if not requirement.package:
        return _("Dieses Programm wird von Hand installiert — die Seite steht daneben.")
    if requirement.kind == "package" and packaged():
        return _(
            "Die gebaute Anwendung bringt keine Paketverwaltung mit. "
            "In einer Entwicklungsumgebung ginge es von hier aus."
        )
    return _("Auf diesem System ist keine Paketverwaltung gefunden worden, die das kann.")


def install(requirement: Requirement, progress: ProgressFn = _silent) -> InstallResult:
    """Install one thing. Called from a button, never on its own (see above)."""
    if present(requirement):
        return InstallResult(requirement=requirement, installed=True)
    if not installable(requirement):
        return InstallResult(requirement=requirement, installed=False, reason=why_not(requirement))

    command = _command(requirement)
    _log.info("installing %s", requirement.id)
    progress(" ".join(command))
    try:
        # The command is built from the constants above and from nothing else.
        finished = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as problem:
        return InstallResult(requirement=requirement, installed=False, output=str(problem))

    output = (finished.stdout or "") + (finished.stderr or "")
    for line in output.splitlines()[-20:]:
        progress(line)

    # Die Suche merkt sich, was sie nicht gefunden hat. Nach einer Installation
    # ist diese Antwort veraltet — sonst bliebe das gerade Installierte bis zum
    # nächsten Start unsichtbar.
    discover.forget_cache()

    done = finished.returncode == 0 and present(requirement)
    if finished.returncode == 0 and not done:
        # winget reports success and the program lands somewhere the current
        # process does not see yet; a restart finds it.
        return InstallResult(
            requirement=requirement,
            installed=False,
            output=output[-2000:],
            reason=_("Installiert — nach einem Neustart von Formwerk ist es zu sehen."),
        )
    _log.info("install of %s finished: %s", requirement.id, done)
    return InstallResult(requirement=requirement, installed=done, output=output[-2000:])


def _command(requirement: Requirement) -> list[str]:
    """The exact command line. Built from the constants in this file only."""
    if requirement.kind == "package":
        return [sys.executable, "-m", "pip", "install", "--upgrade", requirement.package]
    manager = winget() or "winget"
    return [
        manager,
        "install",
        "--exact",
        "--id",
        requirement.package,
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--disable-interactivity",
    ]
