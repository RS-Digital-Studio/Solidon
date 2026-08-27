"""Ein Paket, dessen Namen erst beim Zugriff geladen werden (PEP 562).

**Der Anlass ist ein Deadlock, kein Startzeit-Thema.** Ein ``__init__``, das
Untermodule importiert, gibt es zwei Wege zu demselben Namen — und die nehmen
ihre Locks in umgekehrter Reihenfolge:

    from app.core.scene import History          # erst Paket, dann Untermodul
    from app.core.scene.history import History  # erst Untermodul, dann Paket

Zwei Threads, die gleichzeitig an diesen beiden Stellen einsteigen, verklemmen
sich. Am 23.08.2026 gemessen: **fünf von fünf Läufen** endeten mit
``_DeadlockError: deadlock detected by _ModuleLock(…)``, und zwar in **jedem**
Kernpaket, dessen ``__init__`` etwas lädt — ``scene``, ``registry``,
``sketch``, ``agent``, ``brep`` und ``activation``. Die Pakete mit einer Zeile
Docstring als ``__init__`` (``geom``, ``perceive``, ``knowledge``) sind sauber.

Mit dem verzögerten Zugriff ist ``__init__`` fertig, **bevor** das erste
Untermodul geladen wird — die beiden Locks werden nie gleichzeitig gehalten,
und damit gibt es keine Reihenfolge, die sich verklemmen kann.

**Warum eine Modulklasse und nicht das einfache ``__getattr__``:** Ein
``__getattr__`` auf Modulebene läuft nur, wenn das Attribut **fehlt**. Es fehlt
aber nicht immer: Sobald irgendwer ``app.core.scene.evaluate`` importiert,
setzt Python das **Untermodul** als Attribut des Pakets — und es heißt genauso
wie die Funktion darin. 34 Tests bekamen daraufhin das Modul statt der Funktion
(``TypeError: 'module' object is not callable``). Dass das vorher nie auffiel,
lag am eifrigen ``from …evaluate import evaluate``: Es überschrieb das
Modulattribut, solange es als Letztes lief — **dieselbe Abhängigkeit von der
Importreihenfolge, die schon den Deadlock verursacht hat**, nur an anderer
Stelle sichtbar. Was hier eingetragen ist, gewinnt deshalb immer.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from types import ModuleType
from typing import Any

#: Ein Eintrag ist ``Name im Paket -> (Untermodul, Name darin)``. Die beiden
#: Namen weichen selten ab; ``scene.build_variants`` heißt in ``variants``
#: schlicht ``build``.
Exports = Mapping[str, tuple[str, str]]


def install(package: str, exports: Exports) -> None:
    """Macht die Namen aus ``exports`` in ``package`` verzögert erreichbar.

    Aufgerufen wird das am Ende des ``__init__``, wenn das Modul schon in
    ``sys.modules`` steht. Für Aufrufer ändert sich nichts: ``from <package>
    import <Name>`` funktioniert unverändert, und ``dir()`` zeigt dieselben
    Namen. Was sich ändert: ``import <package>`` allein lädt nichts weiter.

    Untermodule, die **nicht** in ``exports`` stehen, erreicht man wie bisher —
    der Aufruf nimmt ihnen nichts weg, er stellt nur die genannten Namen davor.
    """
    module = sys.modules[package]

    class LazyPackage(ModuleType):
        """Löst die eingetragenen Namen beim Zugriff auf."""

        def __getattribute__(self, name: str) -> Any:
            # Doppelte Unterstriche gehören der Modulmaschinerie: ``__name__``,
            # ``__path__``, ``__spec__``. Sie hier abzufangen hieße, den Import
            # selbst umzubiegen.
            if not name.startswith("_"):
                entry = exports.get(name)
                if entry is not None:
                    submodule, attribute = entry
                    return getattr(importlib.import_module(f"{package}.{submodule}"), attribute)
            return ModuleType.__getattribute__(self, name)

        def __dir__(self) -> list[str]:
            """Ohne das fehlten die verzögerten Namen in ``dir()`` — und damit
            in der Vervollständigung des Editors und in ``help()``."""
            return sorted({*exports, *ModuleType.__dir__(self)})

    module.__class__ = LazyPackage
