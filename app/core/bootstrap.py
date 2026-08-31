"""Das Füllen des Registers (Bauplan §10).

Operationen registrieren sich, wenn ihr Modul importiert wird. Dieser Import
passiert hier, ausdrücklich und an einer Stelle, statt als Nebenwirkung
irgendeines Paketimports — eine Oberfläche, die ihn vergisst, zeigte sonst ein
unvollständiges Menü, ohne dass irgendwo ein Fehler stünde.
"""

from __future__ import annotations

import importlib
from threading import Lock
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.core.types import Finding

_OPERATION_MODULES: Final[tuple[str, ...]] = (
    "app.core.scene.ops",
    "app.core.ingest.ops",
    "app.core.geom.ops",
    "app.core.geom.prepare_ops",
    "app.core.geom.primitive_ops",
    "app.core.geom.colour_ops",
    "app.core.geom.paint",
    "app.core.geom.mesh_ops",
    "app.core.geom.blend",
    "app.core.geom.sculpt",
    "app.core.geom.displace",
    "app.core.geom.pose",
    "app.core.geom.label_ops",
    "app.core.geom.lattice",
    "app.core.geom.texture_ops",
    "app.core.geom.lid",
    # §30: der zweite Kern deklariert seine Operationen wie jedes andere Modul.
    # Ohne OpenCASCADE verweigern sie den Lauf, aber im Menü stehen sie immer —
    # ein Eintrag, der sagt, warum er ausgegraut ist, schlägt einen, den es
    # nicht gibt.
    "app.core.brep.ops",
    # §30.1: die Skizzen-Operationen — Grundformen über den Solver in den Kern.
    "app.core.sketch.ops",
)

#: Die Bausteinbibliothek deklariert selbst keine Operationen — je Baustein
#: wird eine erzeugt (§24.1). ``builtin.load`` füllt das Bausteinregister, der
#: Aufruf danach macht aus jedem Eintrag eine Operation.
_PART_MODULE: Final = "app.core.knowledge.parts"

_loaded = False
_load_lock = Lock()


def load_operations() -> None:
    """Importiert jedes Modul, das Operationen deklariert. Mehrfacher Aufruf
    ist unschädlich."""
    global _loaded
    with _load_lock:
        if _loaded:
            return
        for name in _OPERATION_MODULES:
            importlib.import_module(name)
        importlib.import_module(f"{_PART_MODULE}.builtin").load()
        importlib.import_module(f"{_PART_MODULE}.ops").register_all()
        _loaded = True


_user_loaded = False
_user_findings: tuple[Finding, ...] = ()
_user_operations: tuple[str, ...] = ()


def load_user_parts() -> tuple[Finding, ...]:
    """Liest die eigenen Bausteine aus dem Nutzerordner und macht aus jedem
    eine Operation (§24.5).

    Getrennt von :func:`load_operations`, mit Absicht: Das Register füllen
    auch die Suite und jedes Werkzeug — die eigenen Bausteine aber gehören
    zum **Anwendungsstart**. Ein Testlauf, der sie mitläse, prüfte gegen die
    Maschine des Entwicklers statt gegen die Anwendung (§38). Deshalb rufen
    Oberfläche und Kommandozeile diese Funktion zusätzlich — und sonst
    niemand. Bis es sie gab, rief sie überhaupt niemand, und §24.5 stand nur
    auf dem Papier: ``parts/user.py`` hatte keinen einzigen Aufrufer im
    Produkt.

    Gibt die Befunde des Ladens zurück — eine Datei, die sich nicht
    importieren lässt, wird gemeldet und übersprungen, nie zum Startabbruch.
    """
    global _user_loaded, _user_findings, _user_operations
    if _user_loaded:
        return _user_findings
    load_operations()
    user = importlib.import_module(f"{_PART_MODULE}.user")
    result = user.load()
    if result.loaded:
        # Auch ein eigener Baustein ist eine Operation (§24.1) — der zweite
        # Aufruf registriert nur, was neu dazukam. **Und genau das ist die
        # Auskunft, die die Oberfläche braucht**: Welche Operationen aus dem
        # Nutzerordner stammen, entsteht hier ohnehin und wurde bis zum
        # 24.08.2026 weggeworfen.
        _user_operations = importlib.import_module(f"{_PART_MODULE}.ops").register_all()
    # Die Rezepte danach (§24.5, seit dem 24.08.2026): eigene Bausteine als
    # Daten, aus demselben Nutzerordner. Sie registrieren sich einzeln —
    # Katalog und Palette lesen das Register, die Menüleiste lässt
    # ``user_operations()`` aus, und beides gilt für Rezepte wie für ``.py``s.
    recipes = importlib.import_module(f"{_PART_MODULE}.recipe").load_all()
    if recipes.loaded:
        ops = importlib.import_module(f"{_PART_MODULE}.ops")
        _user_operations = _user_operations + tuple(ops.op_name(name) for name in recipes.loaded)
    _user_loaded = True
    _user_findings = (*result.findings, *recipes.findings)
    return _user_findings


def user_operations() -> tuple[str, ...]:
    """Die Operationen, die aus eigenen Bausteinen des Nutzers entstanden sind.

    Leer, solange :func:`load_user_parts` nicht gelaufen ist — in der Suite
    also immer, und das ist Absicht (§38).

    **Wofür:** Sie gehören in Katalog und Befehlspalette, aber nicht in die
    Menüleiste. Jeder eigene Baustein wird eine Operation und damit ein
    Menüeintrag; zwanzig eigene Teile machen aus einem Menü eine Liste zum
    Absuchen. Die Grenze aus ``tests/test_interface_limits.py`` kann das nie
    sehen, weil die Suite den Nutzerordner bewusst nicht liest.
    """
    return _user_operations
