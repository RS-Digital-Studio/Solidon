"""Was dieser Rechner für lokale KI mitbringt (RM-564, Bauplan §27).

**Auf Apple Silicon ist der Arbeitsspeicher auch der Grafikspeicher.** Ein
Sprachmodell, das Ollama dort ganz über Metal rechnet, muss in den Teil
passen, den macOS der Grafik überlässt; was nicht hineinpasst, rechnet der
Prozessor, und eine Antwort dauert Minuten statt Sekunden. Gemeldet von einem
Kunden mit MacBook M3: qwen3:14b stand nach 30 Minuten bei Schritt 4 von 12.
Der Satz dazu gehört vor das Herunterladen, nicht in die Fehlersuche danach.

Gefragt wird, was der Rechner selbst sagt: Prozessorart und Arbeitsspeicher
über das System, eine NVIDIA-Karte über ``nvidia-smi``, das ihr Treiber
mitbringt (§32: fester Arbeitsordner, Zeit- und Ausgabegrenze). Eine andere
Karte nennt Solidon nicht; ob sie rechnet, misst ``llm.ollama_speed`` mit dem
geladenen Modell — vorher wäre jede Zahl geraten.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, replace
from functools import cache
from typing import Final

from app.core.log import get_logger
from app.core.process import run_limited, trusted_cwd

_log = get_logger(__name__)

#: Wie viel Arbeitsspeicher macOS auf Apple Silicon der Grafik von sich aus
#: überlässt (``recommendedMaxWorkingSetSize``, nach dem Ollama über Metal
#: entscheidet, wie viel vom Modell auf die Grafik geht): zwei Drittel bis
#: 36 GB, darüber drei Viertel — ein MacBook mit 16 GB gibt der Grafik rund
#: 10,7 GB, eines mit 8 GB rund 5,3 GB.
APPLE_GRAPHICS_SHARE_SMALL: Final = 2.0 / 3.0
APPLE_GRAPHICS_SHARE_LARGE: Final = 3.0 / 4.0
APPLE_SHARE_LIMIT_GB: Final = 36.0

#: Was eine Grafikkarte unter Windows für Desktop und Fenster belegt, bevor ein
#: Modell lädt — gemessen 1,3 GB auf der RTX 4080 (Durchsicht 0.5.1,
#: ``llm.OLLAMA_SUGGESTIONS``). Ein Modell mit 7,4 GB passt deshalb nicht ganz
#: auf eine 8-GB-Karte, wohl aber auf eine mit 10 GB.
CARD_RESERVE_GB: Final = 1.3


@dataclass(frozen=True, slots=True)
class Machine:
    """Prozessorart und Arbeitsspeicher, in GB wie im Datenblatt (2³⁰ Byte)."""

    apple_silicon: bool = False
    memory_gb: float | None = None
    card_name: str = ""
    """Die NVIDIA-Karte, wie ``nvidia-smi`` sie nennt — leer, wenn keine erkannt ist."""
    card_gb: float | None = None
    """Ihr Grafikspeicher in GB."""
    card_asked: bool = True
    """Ob nach der Karte gefragt ist. ``False``, bevor ein Arbeiter
    :func:`probe_card` gefahren hat — dann sagt Solidon über sie nichts, statt
    „keine erkannt“ zu melden."""

    @property
    def graphics_gb(self) -> float | None:
        """Was ein Modell auf der Grafik belegen darf — ``None``, wenn unbekannt.

        Auf Apple Silicon der Anteil, den macOS der Grafik lässt; mit einer
        erkannten Karte ihr Speicher abzüglich :data:`CARD_RESERVE_GB`.
        """
        if self.card_gb is not None and not self.apple_silicon:
            return max(0.0, self.card_gb - CARD_RESERVE_GB)
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


def _nvidia_card() -> tuple[str, float] | None:
    """Name und Speicher der ersten NVIDIA-Karte — ``None`` ohne Treiber oder Antwort.

    Im eigenen Flatpak auf dem Rechner, nicht im Sandkasten (``discover.on_host``,
    Regel ``kern.md``): Dort liegt ``nvidia-smi`` nicht, und ein Kunde mit Karte
    läse „keine erkannt“ (Nachprüfung K, N3).
    """
    from app.core import discover

    query = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
    if not discover.in_flatpak():
        program = shutil.which("nvidia-smi")
        if program is None:
            return None
        query[0] = program
    try:
        answer = run_limited(
            discover.on_host(query),
            cwd=trusted_cwd(),
            timeout=5.0,
            output_limit=16 * 1024,
        )
    except (OSError, subprocess.SubprocessError) as problem:
        _log.info("nvidia-smi did not answer: %s", problem)
        return None
    lines = answer.stdout.decode("utf-8", errors="replace").strip().splitlines()
    if answer.returncode != 0 or not lines:
        return None
    name, _comma, mebibytes = lines[0].rpartition(",")
    try:
        gigabytes = float(mebibytes.strip()) / 1024.0
    except ValueError:
        return None
    printable = "".join(letter for letter in name.strip() if letter.isprintable())
    return printable[:60], gigabytes


def this_machine() -> Machine:
    """Dieser Rechner — der einzige Weg, auf dem Solidon danach fragt.

    **Startet nie einen Prozess** und darf deshalb im Hauptthread stehen: die
    Karte nur, wenn ein Arbeiter sie schon erhoben hat (:func:`probe_card`),
    sonst ohne (Nachprüfung K, N2). Die Suite setzt hier einen neutralen
    Rechner ein (``tests/conftest.py``).
    """
    found = detect()
    with _CARD_LOCK:
        if not _CARD:
            return replace(found, card_asked=found.apple_silicon)
        card = _CARD[0]
    if card is None:
        return found
    return replace(found, card_name=card[0], card_gb=card[1])


#: Die erhobene Karte: leer heißt noch nicht gefragt, ``[None]`` keine erkannt.
_CARD: list[tuple[str, float] | None] = []
_CARD_LOCK: Final = threading.Lock()


def probe_card() -> None:
    """Die Grafikkarte erheben — einmal je Prozess, **nur in einem Arbeiter** (ein
    ``nvidia-smi``-Aufruf mit 5 s Antwortgrenze; übersteht ein hängender Treiber auch
    das harte Beenden, wartet der Abbau bis :data:`process.PROCESS_KILL_SECONDS` auf
    sein Ende, unter Windows nach ``taskkill`` ein zweites Mal)."""
    with _CARD_LOCK:
        if _CARD:
            return
    card = None if detect().apple_silicon else _nvidia_card()
    with _CARD_LOCK:
        if not _CARD:
            _CARD.append(card)
            _log.info("graphics card: %s", card)


def forget_card() -> None:
    """Die erhobene Karte vergessen — für Tests."""
    with _CARD_LOCK:
        _CARD.clear()


@cache
def detect() -> Machine:
    """Prozessorart und Arbeitsspeicher, einmal je Prozess — ohne Prozess, also
    überall erlaubt. Die Karte erhebt :func:`probe_card`."""
    memory = _memory_bytes()
    found = Machine(apple_silicon=_is_apple_silicon(), memory_gb=memory / 2**30 if memory else None)
    _log.info("machine: apple_silicon=%s memory_gb=%s", found.apple_silicon, found.memory_gb)
    return found
