"""Review-Sonde: Wie stehen die neuen Befundwerte im Tooltip?"""

import os
import sys

sys.path.insert(0, r"F:\3D Druck")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.labels import value_line  # noqa: E402

for code in ("open", "winding", "flat", "self", "cavity", "kernel"):
    print("reason", code, "->", repr(value_line("reason", code)))
print(repr(value_line("tolerance_mm", 0.000123)))
print(repr(value_line("holes", 3)))
print(repr(value_line("parts", 2)))
