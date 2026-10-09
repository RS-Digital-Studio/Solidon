"""Matrixlauf mit organischen Bäumen: ``support_style`` für ``tree`` mitgeschrieben.

Aufruf: python matrix_organisch.py <code-wurzel> <modell> <ausgabe> <kombinationen> [<bambu-wert>]

Sonde, kein Code der Anwendung: Sie hängt an die Orca-Tabelle eine Zeile
``support.style → support_style`` (``tree`` → ``organic``) und übersetzt den
Wert für Bambu Studio (Vorgabe ``tree_organic``), dann läuft
``tools/matrix_unit.py`` unverändert.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

from app.core.export import slicer_keys  # noqa: E402

BAMBU = sys.argv[5] if len(sys.argv) > 5 else "tree_organic"

slicer_keys.TABLES["orca"] = (
    *slicer_keys.TABLES["orca"],
    slicer_keys.Entry("support.style", "support_style", slicer_keys._only({"tree": "organic"})),
)
slicer_keys.PROGRAM_VALUES.setdefault("bambustudio", {})["support_style"] = {"organic": BAMBU}

sys.argv = [str(ROOT / "tools" / "matrix_unit.py"), str(ROOT), *sys.argv[2:5]]
runpy.run_path(sys.argv[0], run_name="__main__")
