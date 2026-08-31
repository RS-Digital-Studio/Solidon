"""Lädt die mit Solidon ausgelieferten Bausteine genau einmal (§24.1)."""

from __future__ import annotations

import importlib
import sys
from threading import Lock
from typing import Final, cast

from app.core.knowledge.parts.registry import PartRegistry

SHIPPED_MODULES: Final[tuple[str, ...]] = (
    "fasteners",
    "mechanics",
    "mounting",
    "structure",
    "testbodies",
)

_lock = Lock()
_loaded = False


def load() -> PartRegistry:
    """Registriert die fünf mitgelieferten Gruppen und gibt ihr Register zurück.

    Der eigene Taktgeber ist nötig, weil der Paketimport selbst keine
    Untermodul-Locks halten darf. Der zweite Aufruf ist unschädlich; bei zwei
    gleichzeitigen Aufrufen gewinnt genau einer die Registrierung.
    """
    global _loaded
    if not _loaded:
        with _lock:
            if not _loaded:
                registry = importlib.import_module(f"{__package__}.registry")
                module_names = tuple(f"{__package__}.{name}" for name in SHIPPED_MODULES)
                for name in module_names:
                    try:
                        importlib.import_module(name)
                    except BaseException:
                        # Nur die gerade brechende Gruppe wird zurückgenommen.
                        # Eine frühere kann beim Snapshot schon in
                        # ``sys.modules`` gesteckt und parallel erst danach
                        # vollständig registriert worden sein. Deren Specs zu
                        # löschen, aber ihr fertiges Modul im Cache zu lassen,
                        # machte den nächsten Lauf still unvollständig.
                        for spec in registry.PARTS.all():
                            if spec.fn.__module__ == name:
                                registry.PARTS.remove(spec.name)
                        sys.modules.pop(name, None)
                        raise
                _loaded = True

    registry = importlib.import_module(f"{__package__}.registry")
    return cast(PartRegistry, registry.PARTS)


def changed_since(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Vergleicht gegen die mitgelieferte oder eine ausdrücklich genannte Bibliothek.

    Der öffentliche Helfer versprach vor dem Lazy-Umbau den vollständigen
    Bestand, weil schon sein Paketimport alle Gruppen registrierte. Ein
    übergebenes Test-Register bleibt dagegen absichtlich isoliert.
    """
    source = registry if registry is not None else load()
    implementation = importlib.import_module(f"{__package__}.registry")
    return cast(tuple[str, ...], implementation.changed_since(before, source))


def missing_parts(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Findet fehlende Bausteine in der vollständigen oder genannten Bibliothek."""
    source = registry if registry is not None else load()
    implementation = importlib.import_module(f"{__package__}.registry")
    return cast(tuple[str, ...], implementation.missing_parts(before, source))


def __getattr__(name: str) -> object:
    """Erhält ``from …parts import PARTS`` als öffentlichen Vertrag."""
    if name == "PARTS":
        return load()
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Zeigt den verzögerten öffentlichen Namen in Werkzeugen an."""
    return ["PARTS", "SHIPPED_MODULES", "changed_since", "load", "missing_parts"]
