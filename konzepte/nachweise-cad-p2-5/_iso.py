"""Gemeinsamer Kopf der P2.5-Sonden: Nutzerverzeichnisse isolieren, Baum vorn.

    .venv/Scripts/python.exe konzepte/nachweise-cad-p2-5/s1_inventory.py

Die Sondenbibliothek ``_probe`` wird aus ``konzepte/nachweise-cad-p2-7``
geteilt statt kopiert (Zwillingsregel): exakte Formen über die vorhandene
API, Messen am Körper, STEP-Rundreise. Dieser Ordner ergänzt nur, was das
Gewinde braucht (``thread_probe``).
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISO = Path(tempfile.gettempdir()) / "solidon-p25-iso"
ISO.mkdir(exist_ok=True)
for _v in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_v] = str(ISO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONUTF8", "1")
TREE = str(HERE.parents[1])
if sys.path[0] != TREE:
    sys.path.insert(0, TREE)
SHARED = str(HERE.parent / "nachweise-cad-p2-7")
if SHARED not in sys.path:
    sys.path.insert(1, SHARED)
import app  # noqa: E402

assert app.__file__.lower().startswith(TREE.lower()), app.__file__
