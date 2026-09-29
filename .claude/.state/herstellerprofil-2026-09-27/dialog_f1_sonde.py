"""Sonde: Review Stufe A+B, F1 und F2 im Druckdialog (offscreen, Bambu P1S).

Kein Test — die Fenstertests laufen beim Release. Geprüft am echten Bestand
von Bambu Studio:

F1: Bambus Stützdichte 0,168 steht als 17 % im Feld. Wer nur die Wandzahl
    ändert, darf danach nur die Wandzahl als eigene Wahl haben.
F2: Die Stufe „Fein" legt ihre Schichthöhe über den Standardprozess, der Satz
    zur Grundlage nennt beides, und die Wandzahl bleibt beim Hersteller.

Aufruf: python dialog_f1_sonde.py <code-wurzel>
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
scratch = Path(tempfile.mkdtemp(prefix="dialog-f1-sonde-"))
os.environ["APPDATA"] = str(scratch / "appdata")
os.environ["LOCALAPPDATA"] = str(scratch / "local")

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import discover  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.print_settings_dialog import PrintSettingsDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

BAMBU = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
qt = QApplication.instance() or QApplication([])
discover.remember_path("slicer", str(BAMBU))

session = Session()
session.change_scene_profile("bambu-p1s", "pla")
assert session.wait_for_idle()
dialog = PrintSettingsDialog(session, UiSettings())
assert dialog.wait_for_slicers(), "Slicersuche kam nicht zurück"


def settle(check, seconds: float = 120.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + seconds
    while not check() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.05)
    assert check(), "Zeitlimit"


settle(lambda: bool(dialog._profiles) and dialog._foundation is not None)
print("Prozess:", dialog.process_choice.currentText())
print("Grundlage:", dialog.foundation_note.text())
settings = dialog.settings
print("Stützdichte der Grundlage:", settings.support.density)
assert not settings.explicit, "ohne Eingabe keine eigene Wahl"

# F1 — nur die Wandzahl ändern.
editor = dialog._editors["shell.wall_count"]
editor.setValue(settings.shell.wall_count + 1)
qt.processEvents()
print("eigene Wahl nach der Wandzahl:", sorted(dialog.settings.chosen))
assert dialog.settings.chosen == {"shell.wall_count"}, dialog.settings.chosen
assert abs(dialog.settings.support.density - settings.support.density) < 1e-9
dialog._resets["shell.wall_count"].click()
qt.processEvents()
assert not dialog.settings.explicit

# F2 — Stufe „Fein".
index = dialog.quality.findData("fine")
assert index >= 0
dialog.quality.setCurrentIndex(index)
qt.processEvents()
settle(lambda: dialog._foundation is not None and bool(dialog._foundation.staged))
print("Grundlage mit Fein:", dialog.foundation_note.text())
print(
    "Schichthöhe",
    dialog.settings.layers.layer_height,
    "| Wände",
    dialog.settings.shell.wall_count,
    "| gestuft",
    sorted(dialog._foundation.staged),
)
assert abs(dialog.settings.layers.layer_height - 0.12) < 1e-9
assert "+" in dialog.foundation_note.text()
assert not dialog.settings.explicit, "die Stufe ist keine Eingabe in einem Feld"
print("Sonde bestanden.")
dialog.done(0)
dialog.release()
