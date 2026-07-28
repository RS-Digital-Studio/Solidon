"""External programs (Bauplan §38, §37.2).

OpenSCAD, the slicer, Ollama and ComfyUI are not shipped — they are configured.
That is a licence decision for OpenSCAD and the slicers (§36, both GPL) and a
size decision for the rest, and it means the application has to be able to say
clearly which of them is there and which is not.

Nothing here is required. Every one of them is a fallback or an extra, so a
machine without any of them runs the whole core path (§24.1). What the first
run does with this list is show it — not demand it.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.backends import llm, openscad
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ExternalTool:
    """One program the application can use if it is there."""

    id: str
    title: TranslatableText | str
    what_for: TranslatableText | str
    executables: tuple[str, ...] = ()
    optional: bool = True

    def path(self) -> Path | None:
        for name in self.executables:
            found = shutil.which(name)
            if found:
                return Path(found)
        return None

    @property
    def available(self) -> bool:
        return self.path() is not None


#: Slicers that write G-code. Only needed for the cross-check (§28.1) and for
#: sending a model on — never for computing one.
SLICERS: Final = (
    "prusa-slicer",
    "PrusaSlicer",
    "orca-slicer",
    "OrcaSlicer",
    "cura",
    "bambu-studio",
)

TOOLS: Final[tuple[ExternalTool, ...]] = (
    ExternalTool(
        id="openscad",
        title="OpenSCAD",
        what_for=_("Rückfallebene für Formen, für die es keinen Baustein gibt."),
        executables=openscad.EXECUTABLES,
    ),
    ExternalTool(
        id="slicer",
        title=_("Slicer"),
        what_for=_("Für die Druckdatei und die Gegenprobe aus dem G-Code."),
        executables=SLICERS,
    ),
    ExternalTool(
        id="ollama",
        title="Ollama",
        what_for=_("Sprachmodell lokal, statt mit eigenem Schlüssel."),
        executables=("ollama",),
    ),
    ExternalTool(
        id="comfyui",
        title="ComfyUI",
        what_for=_("Mesh-Erzeugung aus Text oder Bild."),
        executables=("comfyui", "comfy"),
    ),
)


@dataclass(frozen=True, slots=True)
class ToolState:
    """What was found, for the first run and the settings."""

    tool: ExternalTool
    path: Path | None

    @property
    def available(self) -> bool:
        return self.path is not None


def survey() -> tuple[ToolState, ...]:
    """Look for every external program once. Missing is normal, not an error."""
    found = tuple(ToolState(tool=tool, path=tool.path()) for tool in TOOLS)
    _log.info("found %d of %d external tools", sum(1 for e in found if e.available), len(found))
    return found


def language_model_available() -> bool:
    """§27: with a key or a local server the chat works, otherwise it is off."""
    return llm.first_available() is not None
