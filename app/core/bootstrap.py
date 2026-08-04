"""Das Füllen des Registers (Bauplan §10).

Operationen registrieren sich, wenn ihr Modul importiert wird. Dieser Import
passiert hier, ausdrücklich und an einer Stelle, statt als Nebenwirkung
irgendeines Paketimports — eine Oberfläche, die ihn vergisst, zeigte sonst ein
unvollständiges Menü, ohne dass irgendwo ein Fehler stünde.
"""

from __future__ import annotations

import importlib
from typing import Final

_OPERATION_MODULES: Final[tuple[str, ...]] = (
    "app.core.scene.ops",
    "app.core.ingest.ops",
    "app.core.geom.ops",
    "app.core.geom.prepare_ops",
    "app.core.geom.primitive_ops",
    "app.core.geom.colour_ops",
    "app.core.geom.paint",
    "app.core.geom.mesh_ops",
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
#: wird eine erzeugt (§24.1). Der Paketimport füllt das Bausteinregister, der
#: Aufruf danach macht aus jedem Eintrag eine Operation.
_PART_MODULE: Final = "app.core.knowledge.parts"

_loaded = False


def load_operations() -> None:
    """Importiert jedes Modul, das Operationen deklariert. Mehrfacher Aufruf
    ist unschädlich."""
    global _loaded
    if _loaded:
        return
    for name in _OPERATION_MODULES:
        importlib.import_module(name)
    importlib.import_module(_PART_MODULE)
    importlib.import_module(f"{_PART_MODULE}.ops").register_all()
    _loaded = True
