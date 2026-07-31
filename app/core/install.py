"""Fehlendes installieren, aus der Anwendung heraus (Bauplan §36, §38).

Formwerk kommt ohne OpenSCAD, ohne Slicer und ohne B-Rep-Kern — bei den ersten
beiden aus Lizenzgründen, beim Rest wegen der Größe (§36). Das ist eine gute
Entscheidung und eine schlechte Erfahrung: wer eine Verrundung will, soll kein
README lesen müssen, um herauszufinden, welches Paket zu installieren ist.

Also zählt dieses Modul auf, was fehlt, und installiert es — unter drei
Regeln, die nicht verhandelbar sind:

* **Die Namen sind Konstanten in dieser Datei.** Nichts, was aus einem Modell,
  einer Projektdatei oder einer Webseite ankommt, wird je an einen Installer
  übergeben.
* **Nur offizielle Quellen.** Python-Pakete aus dem Index, für den der
  Interpreter ohnehin eingerichtet ist, Programme über die Paketverwaltung des
  Systems. Formwerk lädt keine eigenen Installer herunter.
* **Nie ungefragt.** Die Liste wird gezeigt, den Knopf drückt ein Mensch. Eine
  Anwendung, die Software installiert, weil sie glaubt, sie zu brauchen, hat
  eine Entscheidung getroffen, die nicht ihre war.

Wo eine Installation unmöglich ist — eine paketierte Anwendung hat kein pip,
ein Rechner ohne winget keine Paketverwaltung — ist die Antwort die
Download-Seite und ein Satz, der sagt warum. Kein stilles Scheitern.
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

#: Wie lange eine Installation dauern darf, bevor sie aufgegeben wird.
#: Paketverwaltungen laden herunter; eine Minute reicht nicht, und eine
#: Stunde hilft niemandem.
TIMEOUT_SECONDS = 900.0

ProgressFn = Callable[[str], None]


def _silent(line: str) -> None:
    del line


@dataclass(frozen=True, slots=True)
class Requirement:
    """Eine Sache, die Formwerk benutzen kann, und wie sie auf den Rechner kommt."""

    id: str
    title: TranslatableText | str
    what_for: TranslatableText | str
    kind: Kind
    package: str = ""
    """Distributionsname für pip, oder die winget-Kennung eines Programms."""
    module: str = ""
    """Was importiert wird, um festzustellen, ob es da ist. Nur bei Paketen."""
    url: str = ""
    """Die offizielle Seite, für wenn Installieren von hier nicht geht."""


#: Alles, was die Anwendung installieren kann. Die Namen stehen mit Absicht
#: fest hier — siehe Modul-Docstring.
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
    """Was passiert ist. ``output`` ist das Ende dessen, was der Installer
    gesagt hat."""

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
        except Exception:  # eine kompilierte Erweiterung scheitert vielfältiger als ImportError
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
    """Alles, was auf diesem Rechner fehlt. Fehlen ist normal, kein Fehler."""
    return [entry for entry in REQUIREMENTS if not present(entry)]


def packaged() -> bool:
    """Ist das die gebaute Anwendung? Dann gibt es kein pip zum Installieren."""
    return bool(getattr(sys, "frozen", False))


def winget() -> str | None:
    """Die System-Paketverwaltung, wenn dieses System die hat, die wir
    ansteuern können."""
    return shutil.which("winget")


def installable(requirement: Requirement) -> bool:
    """Lässt sich das von hier aus überhaupt installieren?"""
    if not requirement.package:
        return False
    if requirement.kind == "package":
        return not packaged()
    return winget() is not None


def why_not(requirement: Requirement) -> TranslatableText | str:
    """Der Satz neben einem Knopf, der sich nicht drücken lässt (§33.1)."""
    if not requirement.package:
        return _("Dieses Programm wird von Hand installiert — die Seite steht daneben.")
    if requirement.kind == "package" and packaged():
        return _(
            "Die gebaute Anwendung bringt keine Paketverwaltung mit. "
            "In einer Entwicklungsumgebung ginge es von hier aus."
        )
    return _("Auf diesem System ist keine Paketverwaltung gefunden worden, die das kann.")


def install(requirement: Requirement, progress: ProgressFn = _silent) -> InstallResult:
    """Installiert eine Sache. Von einem Knopf aufgerufen, nie von allein
    (siehe oben)."""
    if present(requirement):
        return InstallResult(requirement=requirement, installed=True)
    if not installable(requirement):
        return InstallResult(requirement=requirement, installed=False, reason=why_not(requirement))

    command = _command(requirement)
    _log.info("installing %s", requirement.id)
    progress(" ".join(command))
    try:
        # Der Befehl entsteht aus den Konstanten oben und aus sonst nichts.
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
        # winget meldet Erfolg, und das Programm landet an einer Stelle, die
        # der laufende Prozess noch nicht sieht; ein Neustart findet es.
        return InstallResult(
            requirement=requirement,
            installed=False,
            output=output[-2000:],
            reason=_("Installiert — nach einem Neustart von Formwerk ist es zu sehen."),
        )
    _log.info("install of %s finished: %s", requirement.id, done)
    return InstallResult(requirement=requirement, installed=done, output=output[-2000:])


def _command(requirement: Requirement) -> list[str]:
    """Die genaue Befehlszeile. Gebaut allein aus den Konstanten dieser Datei."""
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
