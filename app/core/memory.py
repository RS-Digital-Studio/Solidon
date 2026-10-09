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
import threading
from pathlib import Path
from typing import Any, Final

#: Wie tief verschachtelt gezählt wird — tiefer liegt in keinem Ergebnis
#: etwas Großes, und ein Zyklus endet spätestens hier.
DEPTH: Final = 12

#: Was ein Wert ohne erkennbaren Inhalt mindestens kostet (Objektkopf).
_HEADER: Final = 56


def physical_memory() -> int | None:
    """Wie viel Arbeitsspeicher dieser Prozess höchstens bekommt, in Bytes; ``None`` wenn unbekannt.

    Der eingebaute Arbeitsspeicher des Rechners — oder eine kleinere Grenze
    darüber (Review L, G4): unter Linux die Speichergrenze der cgroup (Docker,
    systemd ``MemoryMax``) und der Adressraum (``RLIMIT_AS``), unter macOS
    dieser, unter Windows die Grenze eines Jobs. Sonst bemäße sich das
    Achtel der Speicherebene am Wirt statt an dem, was der Prozess bekommt.
    """
    limits = [
        value
        for value in (_installed_memory(), *_process_limits())
        if value is not None and value > 0
    ]
    return min(limits) if limits else None


def _installed_memory() -> int | None:
    """Der eingebaute Arbeitsspeicher des Rechners in Bytes, ``None`` wenn unbekannt."""
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


#: Wo Linux die cgroups einhängt und wo ein Prozess seine eigene nachliest.
_CGROUP_ROOT: Final = Path("/sys/fs/cgroup")
_OWN_CGROUP: Final = Path("/proc/self/cgroup")


def _process_limits() -> list[int | None]:
    """Grenzen unterhalb des Rechners, die für diesen Prozess gelten."""
    if sys.platform == "win32":
        return [_job_limit()]
    limits = [_address_space_limit()]
    if sys.platform.startswith("linux"):
        limits.append(_cgroup_limit())
    return limits


def _cgroup_limit(root: Path = _CGROUP_ROOT, own: Path = _OWN_CGROUP) -> int | None:
    """Die kleinste Speichergrenze der cgroups dieses Prozesses, ``None`` ohne Grenze.

    cgroup v2 (``memory.max``) gilt für die eigene Gruppe und jede darüber;
    v1 (``memory/memory.limit_in_bytes``) für die eigene. Ein Container sieht
    seine Gruppe oft als Wurzel — die zählt deshalb immer mit. ``max`` und
    die riesige Zahl, mit der v1 „unbegrenzt“ schreibt, sind keine Grenze:
    Größer als der Rechner fällt sie in :func:`physical_memory` heraus.
    """
    try:
        lines = own.read_text(encoding="ascii", errors="replace").splitlines()
    except OSError:
        lines = []
    places = [root / "memory.max", root / "memory" / "memory.limit_in_bytes"]
    for line in lines:
        parts = line.strip().split(":", 2)
        if len(parts) != 3:
            continue
        hierarchy, controllers, path = parts
        relative = Path(path.strip().lstrip("/"))
        if hierarchy == "0" and not controllers:
            group = root / relative
            while group != root and root in group.parents:
                places.append(group / "memory.max")
                group = group.parent
        elif "memory" in controllers.split(","):
            places.append(root / "memory" / relative / "memory.limit_in_bytes")
    found = [value for value in map(_limit_in, places) if value is not None]
    return min(found) if found else None


def _limit_in(place: Path) -> int | None:
    try:
        text = place.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return None
    return int(text) if text.isdigit() and int(text) > 0 else None


def _address_space_limit() -> int | None:
    """Linux und macOS: die Grenze des Adressraums (``RLIMIT_AS``), ``None`` ohne Grenze."""
    if sys.platform == "win32":
        return None
    import resource

    try:
        soft, _hard = resource.getrlimit(resource.RLIMIT_AS)
    except OSError, ValueError:
        return None
    return int(soft) if soft not in (resource.RLIM_INFINITY, -1) and soft > 0 else None


def _job_limit() -> int | None:
    """Windows: die Speichergrenze des Jobs, in dem dieser Prozess läuft, ``None`` ohne."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = (
            ("per_process_user_time", ctypes.c_int64),
            ("per_job_user_time", ctypes.c_int64),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t),
            ("active_processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        )

    class _Extended(ctypes.Structure):
        _fields_ = (
            ("basic", _Basic),
            ("io", ctypes.c_ulonglong * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        )

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.QueryInformationJobObject
    query.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    query.restype = wintypes.BOOL
    info = _Extended()
    # JobObjectExtendedLimitInformation; ohne Job meldet Windows einen Fehler
    # oder keine Grenze.
    if not query(None, 9, ctypes.byref(info), ctypes.sizeof(info), None):
        return None
    limits = []
    if info.basic.limit_flags & _JOB_PROCESS_MEMORY:
        limits.append(int(info.process_memory))
    if info.basic.limit_flags & _JOB_JOB_MEMORY:
        limits.append(int(info.job_memory))
    found = [value for value in limits if value > 0]
    return min(found) if found else None


#: ``JOB_OBJECT_LIMIT_PROCESS_MEMORY`` und ``JOB_OBJECT_LIMIT_JOB_MEMORY``.
_JOB_PROCESS_MEMORY: Final = 0x100
_JOB_JOB_MEMORY: Final = 0x200


#: Was seit der letzten vollen Speicherbereinigung losgelassen wurde und in
#: Ringen hängen kann (RM-594) — siehe :func:`note_released`.
_released = 0
_released_lock = threading.Lock()


def note_released(count: int) -> None:
    """Meldet ``count`` Bytes, die nur die Speicherbereinigung freigibt (RM-594).

    Ein ``trimesh``-Netz hängt in Ringen an sich selbst (sein Cache, seine
    Anzeige, seine Suchstrukturen); was die Speicherebene schlank macht oder
    verdrängt, wird erst frei, wenn die Bereinigung der ältesten Generation
    läuft. Im Fensterprozess ruht die Automatik, und ihr Ersatz im Hauptfaden
    (``ui.leash``) erreichte die älteste Generation selten — am Spiderman
    warteten bis zu 735 MB. Er fragt hier, was gemeldet ist.
    """
    global _released
    if count > 0:
        with _released_lock:
            _released += count


def released_bytes() -> int:
    """Was seit :func:`forget_released` gemeldet wurde, in Bytes."""
    with _released_lock:
        return _released


def forget_released() -> None:
    """Nach einer vollen Bereinigung: Was gemeldet war, ist frei."""
    global _released
    with _released_lock:
        _released = 0


def held_bytes(value: object, seen: set[int] | None = None) -> int:
    """Wie viele Bytes ``value`` mit allem hält, was es erreicht — eine Schätzung.

    NumPy-Felder zählen mit ihrem Puffer, ein geteilter Puffer nur einmal je
    ``seen``. Punktfolgen zählen über ihre Länge (:func:`_sampled`),
    Shapely-Geometrien über ihre Koordinatenzahl. Was
    außerhalb von Python liegt und sich nicht zu erkennen gibt — ein nativer
    Suchbaum —, zählt mit seinem Objektkopf. Für eine Verdrängungsgrenze
    genau genug, für eine Abrechnung nicht.
    """
    return _held(value, set() if seen is None else seen, 0, None)


#: Ab welcher Größe :func:`held_parts` einen Behälter als eigenen Teil führt.
#: Darunter liegen die Kleinteile eines Merkmals — Kennung, Achse, Werte —, die
#: zwei Sätze nie teilen; darüber die Dreiecksnummern, die ein bewegtes
#: Merkmal mit seinem Vorgänger teilt.
PART_BYTES: Final = 1024


def held_parts(
    value: object, seen: set[int] | None = None
) -> tuple[int, dict[int, tuple[object, int]]]:
    """Was ``value`` hält, zerlegt in einen Rest und seine großen Behälter (Nachprüfung L, M-3).

    Der Rest ist, was nur ``value`` gehört; die Teile — je Kennung, wie
    :func:`held_bytes` sie in ``seen`` einträgt, der Behälter und seine Bytes
    ohne seine eigenen Teile — kann ein anderer Wert mit ihm teilen. Wer
    mehrere Werte zählt, addiert den Rest jedes Werts und jeden Teil nur, wenn
    seine Kennung noch nicht gezählt ist: dieselbe Summe wie :func:`held_bytes`
    über alle zusammen, bis auf die Kleinteile unter :data:`PART_BYTES`, ohne
    sie noch einmal zu durchlaufen. Die Teile halten ihre Behälter, damit
    keine Kennung frei und neu vergeben wird. Was in ``seen`` steht, zählt
    weder zum Rest noch zu den Teilen.
    """
    parts: dict[int, tuple[object, int]] = {}
    rest = _held(value, set() if seen is None else seen, 0, parts)
    return rest, parts


def mark_held(value: object, seen: set[int], depth: int = 0) -> None:
    """Trägt in ``seen`` ein, was ``value`` erreicht, ohne es zu zählen (Nachprüfung L, M-3).

    Für den, der danach nur wissen will, was ein zweiter Wert darüber hinaus
    hält (``held_parts(other, seen)``). Eine Folge, deren erstes Element eine
    Zahl, ein Text oder ein Zahlentupel ist, wird nicht durchlaufen — die
    Dreiecksnummern eines Merkmals, hunderttausend Zahlen, kosteten sonst so
    viel wie ihre Zählung. Was dabei unerkannt bleibt, zählt der zweite Wert
    mit: eher zu viel als zu wenig.
    """
    if value is None or isinstance(value, (bool, int, float, complex, str, bytes)):
        return
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if hasattr(value, "dtype"):
        seen.add(id(_array_root(value)))
        return
    if depth >= DEPTH or isinstance(value, type) or callable(value):
        return
    items: Any
    if isinstance(value, dict):
        items = list(dict(value).values())
    elif isinstance(value, (tuple, list, set, frozenset)):
        items = list(value)
        if items and (type(items[0]) in _FLAT or _points(items[:1])):
            return
    else:
        names = _field_names(type(value))
        if names is not None:
            items = [getattr(value, name, None) for name in names]
        else:
            attributes = getattr(value, "__dict__", None)
            items = [attributes] if isinstance(attributes, dict) else []
    for item in items:
        mark_held(item, seen, depth + 1)


def _held(
    value: object, seen: set[int], depth: int, parts: dict[int, tuple[object, int]] | None
) -> int:
    if value is None or isinstance(value, (bool, int, float, complex)):
        return sys.getsizeof(value)
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return sys.getsizeof(value)
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = _held_once(value, seen, depth, parts)
    if parts is None or size < PART_BYTES:
        return size
    # Ein Feld zählt :func:`_array_bytes` über seinen Grundpuffer; dessen
    # Kennung steht dann in ``seen``, und unter ihr teilt es sich.
    parts[id(_array_root(value)) if hasattr(value, "dtype") else identity] = (value, size)
    return 0


def _held_once(
    value: object, seen: set[int], depth: int, parts: dict[int, tuple[object, int]] | None
) -> int:
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
        return (
            sys.getsizeof(value)
            + _sampled(list(snapshot), seen, depth, parts)
            + _sampled(list(snapshot.values()), seen, depth, parts)
        )
    if isinstance(value, (tuple, list)):
        return sys.getsizeof(value) + _sampled(
            value if isinstance(value, tuple) else list(value), seen, depth, parts
        )
    if isinstance(value, (set, frozenset)):
        # Eine Menge wird ganz gezählt; ihre Folge hängt am Hash und damit
        # am Prozess.
        return sys.getsizeof(value) + _sampled(list(value), seen, depth, parts)
    if isinstance(value, type) or callable(value):
        return _HEADER
    total = sys.getsizeof(value)
    names = _field_names(type(value))
    if names is not None:
        return total + sum(
            _held(getattr(value, name, None), seen, depth + 1, parts) for name in names
        )
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return total + _held(attributes, seen, depth + 1, parts)
    return total


#: Die Feldnamen je Datenklasse — ``dataclasses.fields`` je Objekt kostete an
#: einer Schichtanalyse mit 20 000 Konturen den größten Teil der Zählung.
_FIELDS: dict[type, tuple[str, ...] | None] = {}


def _field_names(kind: type) -> tuple[str, ...] | None:
    """Die Felder einer Datenklasse in ihrer Folge, ``None`` für jede andere Klasse."""
    known = _FIELDS.get(kind, ())
    if known != ():
        return known
    names = (
        tuple(field.name for field in dataclasses.fields(kind))
        if dataclasses.is_dataclass(kind)
        else None
    )
    _FIELDS[kind] = names
    return names


def _sampled(
    items: tuple[object, ...] | list[object],
    seen: set[int],
    depth: int,
    parts: dict[int, tuple[object, int]] | None,
) -> int:
    """Die Summe der Elemente einer Folge.

    **Eine Punktfolge wird gerechnet, nicht durchlaufen**: Tupel aus Zahlen
    gleicher Länge, wie die Konturen einer Schichtanalyse sie tragen — am
    Eiffelturm 1,4 Millionen Punkte; einzeln durchlaufen kostete das bei
    jedem Ablegen im Cache eine Sekunde. Jede andere Folge wird ganz gezählt,
    ohne Stichprobe: Eine gemischte — die Merker der Erkennung, Hunderte
    kleine Einpassungen neben wenigen Stützpunktlesungen von Megabytes — traf
    eine Stichprobe je nach Reihenfolge mit 0,7 oder 39 statt 33 MB, und ein
    einzelnes großes Element unter vielen kleinen fehlt jeder Stichprobe
    (Review L, M1). Ein Wörterbuch zählt :func:`_held` ohnehin ganz.

    **Eine flache Folge zählt in einem Zug**: Zahlen und Zeichenketten trägt
    :func:`_held` nicht in ``seen`` ein, also ist ihre Summe dieselbe, ob
    einzeln oder über ``map`` gezählt. Einzeln kosteten die Merker der
    Erkennung am Spiderman 2,6 s je ``trim``.
    """
    if not items:
        return 0
    if set(map(type, items)) <= _FLAT:
        return sum(map(sys.getsizeof, items))
    if _points(items):
        first = items[0]
        assert isinstance(first, tuple)
        return len(items) * (sys.getsizeof(first) + sum(sys.getsizeof(value) for value in first))
    return sum(_held(item, seen, depth + 1, parts) for item in items)


#: Was :func:`_held` ohne ``seen`` mit ``sys.getsizeof`` zählt.
_FLAT: Final = frozenset({int, float, bool, complex, str, bytes, type(None)})


def _points(items: tuple[object, ...] | list[object]) -> bool:
    """Ob die Folge aus gleich langen Zahlentupeln besteht — geprüft an allen Elementen."""
    first = items[0]
    if type(first) is not tuple or not all(type(value) in (float, int) for value in first):
        return False
    size = len(first)
    return all(type(item) is tuple and len(item) == size for item in items)


def _array_bytes(value: object, seen: set[int]) -> int | None:
    """Der Puffer eines NumPy-Felds, ein geteilter nur einmal — sonst ``None``."""
    nbytes = getattr(value, "nbytes", None)
    if not isinstance(nbytes, int) or not hasattr(value, "dtype"):
        return None
    root = _array_root(value)
    if root is not value:
        if id(root) in seen:
            return 0
        seen.add(id(root))
        root_bytes = getattr(root, "nbytes", nbytes)
        return int(root_bytes) if isinstance(root_bytes, int) else nbytes
    return nbytes


def _array_root(value: object) -> Any:
    """Das Feld, dessen Puffer ``value`` zeigt — ``value`` selbst, wenn es keine Ansicht ist."""
    root: Any = value
    while getattr(root, "base", None) is not None and hasattr(root.base, "nbytes"):
        root = root.base
    return root


def _shapely_bytes(geometry: object) -> int:
    """Eine Shapely-Geometrie: zwei Zahlen je Koordinate und ihr Kopf in GEOS."""
    try:
        import shapely

        coordinates = int(shapely.get_num_coordinates(geometry))
    except ImportError, TypeError, ValueError:
        return _HEADER
    return _HEADER + 16 * coordinates
