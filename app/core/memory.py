"""Was der Rechner an Arbeitsspeicher hat und was ein Ergebnis davon hält (RM-567).

Zwei Fragen, die der Ergebniscache stellt (``scene.cache``): Wie groß ist der
Arbeitsspeicher dieses Rechners — daran bemisst sich, wie viel die
Speicherebene halten darf —, und wie viel hält ein Eintrag tatsächlich. Die
Dreieckszahl beantwortet die zweite Frage nicht: Ein Netz mit allem, was
``trimesh`` und die Erkennung an ihm gemerkt haben, hält am Laptop-Riser 644
Byte je Dreieck, ein frisches 36 (gemessen 08.10.2026, Paket L).

Ohne Qt und ohne Geometriekern; NumPy und Shapely werden nur erkannt, nie
importiert.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from typing import Any, Final

#: Ab wie vielen Elementen ein Behälter nur über eine Stichprobe gezählt wird,
#: und wie groß die Stichprobe ist. Eine Schichtanalyse hält ihre Konturen als
#: Tupel aus Punkt-Tupeln — am Eiffelturm 1,4 Millionen Punkte; jeden einzeln
#: zu zählen kostete bei jedem Ablegen im Cache eine Sekunde. Die Elemente
#: eines so langen Behälters sind gleich gebaut, und die Stichprobe trifft
#: ihre Größe auf wenige Prozent. **Ein Wörterbuch wird ganz gezählt**: Der
#: Cache eines Netzes hält ein paar Dutzend verschiedene Felder, und eine
#: Stichprobe über sie traf am Spiderman nur jedes zweite — 685 MB blieben
#: ungezählt (08.10.2026).
SAMPLE_FROM: Final = 64
SAMPLE: Final = 32

#: Wie tief verschachtelt gezählt wird — tiefer liegt in keinem Ergebnis
#: etwas Großes, und ein Zyklus endet spätestens hier.
DEPTH: Final = 12

#: Was ein Wert ohne erkennbaren Inhalt mindestens kostet (Objektkopf).
_HEADER: Final = 56


def physical_memory() -> int | None:
    """Der eingebaute Arbeitsspeicher dieses Rechners in Bytes, ``None`` wenn unbekannt."""
    # Die Weiche über ``sys.platform``: Nur sie lässt mypy auf Linux und macOS
    # den Rest überspringen, wo es ``ctypes.WinDLL`` nicht gibt; die
    # unerreichbaren Zweige erlaubt ``pyproject.toml`` für dieses Modul.
    if sys.platform != "win32":
        return _posix_memory()
    import ctypes
    from ctypes import wintypes

    class _Status(ctypes.Structure):
        _fields_ = (
            ("length", wintypes.DWORD),
            ("load", wintypes.DWORD),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        )

    status = _Status()
    status.length = ctypes.sizeof(_Status)
    query = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    query.argtypes = (ctypes.POINTER(_Status),)
    query.restype = wintypes.BOOL
    if not query(ctypes.byref(status)) or status.total_physical <= 0:
        return None
    return int(status.total_physical)


def _posix_memory() -> int | None:
    """Linux und macOS: Seitenzahl mal Seitengröße."""
    if sys.platform == "win32":
        return None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
    except AttributeError, OSError, ValueError:
        return None
    if pages <= 0 or size <= 0:
        return None
    return int(pages) * int(size)


def held_bytes(value: object, seen: set[int] | None = None) -> int:
    """Wie viele Bytes ``value`` mit allem hält, was es erreicht — eine Schätzung.

    NumPy-Felder zählen mit ihrem Puffer, ein geteilter Puffer nur einmal je
    ``seen``. Große Behälter zählen über eine gleichmäßige Stichprobe
    (:data:`SAMPLE_FROM`), Shapely-Geometrien über ihre Koordinatenzahl. Was
    außerhalb von Python liegt und sich nicht zu erkennen gibt — ein nativer
    Suchbaum —, zählt mit seinem Objektkopf. Für eine Verdrängungsgrenze
    genau genug, für eine Abrechnung nicht.
    """
    return _held(value, set() if seen is None else seen, 0)


def _held(value: object, seen: set[int], depth: int) -> int:
    if value is None or isinstance(value, (bool, int, float, complex)):
        return sys.getsizeof(value)
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return sys.getsizeof(value)
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    buffer = _array_bytes(value, seen)
    if buffer is not None:
        return buffer
    if depth >= DEPTH:
        return _HEADER
    module = type(value).__module__ or ""
    if module.startswith("shapely"):
        return _shapely_bytes(value)
    if isinstance(value, dict):
        # Erst kopieren, in einem Zug: Ein anderer Faden kann gerade etwas
        # hinzufügen (der Cache eines Netzes), und das Durchlaufen bräche ab.
        snapshot = dict(value)
        return sys.getsizeof(value) + sum(
            _held(item, seen, depth + 1) for pair in snapshot.items() for item in pair
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        return sys.getsizeof(value) + _sampled(
            value if isinstance(value, tuple) else list(value), seen, depth
        )
    if isinstance(value, type) or callable(value):
        return _HEADER
    total = sys.getsizeof(value)
    if dataclasses.is_dataclass(value):
        fields = [getattr(value, field.name, None) for field in dataclasses.fields(value)]
        return total + _sampled(fields, seen, depth)
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return total + _held(attributes, seen, depth + 1)
    return total


def _sampled(items: tuple[object, ...] | list[object], seen: set[int], depth: int) -> int:
    """Die Summe der Elemente — ab :data:`SAMPLE_FROM` hochgerechnet aus einer Stichprobe."""
    count = len(items)
    if count <= SAMPLE_FROM:
        return sum(_held(item, seen, depth + 1) for item in items)
    step = count / SAMPLE
    picked = sum(_held(items[int(index * step)], seen, depth + 1) for index in range(SAMPLE))
    return int(picked * count / SAMPLE)


def _array_bytes(value: object, seen: set[int]) -> int | None:
    """Der Puffer eines NumPy-Felds, ein geteilter nur einmal — sonst ``None``."""
    nbytes = getattr(value, "nbytes", None)
    if not isinstance(nbytes, int) or not hasattr(value, "dtype"):
        return None
    root: Any = value
    while getattr(root, "base", None) is not None and hasattr(root.base, "nbytes"):
        root = root.base
    if root is not value:
        if id(root) in seen:
            return 0
        seen.add(id(root))
        root_bytes = getattr(root, "nbytes", nbytes)
        return int(root_bytes) if isinstance(root_bytes, int) else nbytes
    return nbytes


def _shapely_bytes(geometry: object) -> int:
    """Eine Shapely-Geometrie: zwei Zahlen je Koordinate und ihr Kopf in GEOS."""
    try:
        import shapely

        coordinates = int(shapely.get_num_coordinates(geometry))
    except ImportError, TypeError, ValueError:
        return _HEADER
    return _HEADER + 16 * coordinates
