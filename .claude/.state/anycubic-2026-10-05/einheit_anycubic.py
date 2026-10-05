"""``einheit.py`` der Slicer-Matrix für die Drucker, die Solidon aus Anycubic Slicer Next liest.

Der Kunde wählt seinen Anycubic-Drucker aus dem Slicer (``discover_printers``),
nicht aus Solidons eigener Tabelle, die nur den Kobra 2 kennt. Dieser
Vorschalter hängt die gelesenen Drucker in den Bestand des Prozesses, trägt
den Slicer als ``anycubic`` in ``matrix_config`` ein und führt dann
``einheit.py`` unverändert aus.

Aufruf: python einheit_anycubic.py <code-wurzel> <modell> <ausgabeordner> <kombis>
``<kombis>``: ``alle`` (jeder gelesene Drucker), ``heim`` (Kobra S1 und S1 Max,
je 0,4 mm) oder Druckertitel durch ``|`` getrennt.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "uebergabe-gesamt-2026-09-27" / "einheit.py"
EXE = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(TOOL.parent))

import matrix_config  # noqa: E402

from app.core.export import slicer_profiles  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

found = slicer_profiles.discover_printers(EXE, "orca")
table = dict(profiles.printer_profiles())
table.update({printer.id: printer for printer in found})
profiles._printers = table
by_title = {printer.title: printer.id for printer in found}
matrix_config.SLICERS["anycubic"] = str(EXE)
matrix_config.SLICER_FLAVOURS["anycubic"] = "orca"
matrix_config.HOME["anycubic"] = by_title["Anycubic Kobra S1 0.4 nozzle"]
spec = sys.argv[4] if len(sys.argv) > 4 else "heim"
if spec == "alle":
    titles = sorted(by_title)
elif spec == "heim":
    titles = ["Anycubic Kobra S1 0.4 nozzle", "Anycubic Kobra S1 Max 0.4 nozzle"]
else:
    titles = spec.split("|")
pairs = ",".join(f"anycubic:{by_title[title]}" for title in titles)
sys.argv = [str(TOOL), str(ROOT), sys.argv[2], sys.argv[3], pairs]
runpy.run_path(str(TOOL), run_name="__main__")
