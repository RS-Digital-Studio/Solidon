"""Was dieser Rechner für lokale KI mitbringt (RM-564, Bauplan §27).

**Auf Apple Silicon ist der Arbeitsspeicher auch der Grafikspeicher.** Ein
Sprachmodell, das Ollama dort ganz über Metal rechnet, muss in den Teil
passen, den macOS der Grafik überlässt; was nicht hineinpasst, rechnet der
Prozessor, und eine Antwort dauert Minuten statt Sekunden. Gemeldet von einem
Kunden mit MacBook M3: qwen3:14b stand nach 30 Minuten bei Schritt 4 von 12.
Der Satz dazu gehört vor das Herunterladen, nicht in die Fehlersuche danach.

Gefragt wird nur, was der Rechner ohne fremdes Programm sagt: Prozessorart und
Arbeitsspeicher. Eine Grafikkarte unter Windows oder Linux misst Solidon erst
mit dem geladenen Modell (``llm.ollama_speed``) — vorher wäre jede Zahl
geraten.
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass
from functools import cache
from typing import Final

from app.core.log import get_logger

_log = get_logger(__name__)

#: Wie viel Arbeitsspeicher macOS auf Apple Silicon der Grafik von sich aus
#: überlässt (``recommendedMaxWorkingSetSize``, nach dem Ollama über Metal
#: entscheidet, wie viel vom Modell auf die Grafik geht): zwei Drittel bis
#: 36 GB, darüber drei Viertel — ein MacBook mit 16 GB gibt der Grafik rund
#: 10,7 GB, eines mit 8 GB rund 5,3 GB.
APPLE_GRAPHICS_SHARE_SMALL: Final = 2.0 / 3.0
APPLE_GRAPHICS_SHARE_LARGE: Final = 3.0 / 4.0
APPLE_SHARE_LIMIT_GB: Final = 36.0


@dataclass(frozen=True, slots=True)
class Machine:
    """Prozessorart und Arbeitsspeicher, in GB wie im Datenblatt (2³⁰ Byte)."""

    apple_silicon: bool = False
    memory_gb: float | None = None

    @property
    def graphics_gb(self) -> float | None:
        """Was die Grafik auf Apple Silicon belegen darf — ``None`` anderswo.

        Unter Windows und Linux entscheidet eine eigene Karte, deren Speicher
        Solidon ohne Herstellerwerkzeug nicht kennt.
        """
        if not self.apple_silicon or self.memory_gb is None:
            return None
        share = (
            APPLE_GRAPHICS_SHARE_SMALL
            if self.memory_gb <= APPLE_SHARE_LIMIT_GB
            else APPLE_GRAPHICS_SHARE_LARGE
        )
        return self.memory_gb * share


class _MemoryStatus(ctypes.Structure):
    """``MEMORYSTATUSEX`` aus der Windows-API."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _memory_bytes() -> int | None:
    """Der eingebaute Arbeitsspeicher — ``None``, wenn das System schweigt."""
    if sys.platform == "win32":
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        windll = getattr(ctypes, "windll", None)
        if windll is None or not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys)
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except ValueError, OSError, AttributeError:
        return None


def _is_apple_silicon() -> bool:
    """Ein Mac mit Apple-Chip — auch unter Rosetta, wo Python ``x86_64`` sagt."""
    if sys.platform != "darwin":
        return False
    if platform.machine() == "arm64":
        return True
    try:
        # ``sysctl.proc_translated`` ist 1 unter Rosetta; ein Intel-Mac kennt
        # den Schlüssel nicht und antwortet mit einem Fehler.
        libc = ctypes.CDLL(None)
        value = ctypes.c_int(0)
        size = ctypes.c_size_t(ctypes.sizeof(value))
        found = libc.sysctlbyname(
            b"sysctl.proc_translated", ctypes.byref(value), ctypes.byref(size), None, 0
        )
    except OSError, AttributeError:
        return False
    return found == 0 and value.value == 1


def this_machine() -> Machine:
    """Dieser Rechner — der einzige Weg, auf dem Solidon danach fragt.

    Die Suite setzt hier einen neutralen Rechner ein (``tests/conftest.py``):
    Ein Mac mit 16 GB bekäme sonst eine andere Chat-Vorgabe als der Bauserver.
    """
    return detect()


@cache
def detect() -> Machine:
    """Dieser Rechner, einmal je Prozess erhoben."""
    memory = _memory_bytes()
    found = Machine(
        apple_silicon=_is_apple_silicon(),
        memory_gb=memory / 2**30 if memory else None,
    )
    _log.info("machine: apple_silicon=%s memory_gb=%s", found.apple_silicon, found.memory_gb)
    return found
