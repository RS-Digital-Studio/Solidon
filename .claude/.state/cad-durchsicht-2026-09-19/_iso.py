"""Gemeinsamer Kopf der Sonden: Nutzerverzeichnisse isolieren, Baum vorn.

Die Sonden laufen mit der ``.venv`` des Hauptklons:

    .venv\\Scripts\\python.exe .claude/.state/cad-durchsicht-2026-09-19/s8_matrix.py

Sie schreiben nichts ins Projekt; die Nutzerverzeichnisse werden in einen
Unterordner ``iso`` neben den Sonden umgebogen, damit keine Sonde Roberts
echte Profile trifft.
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISO = Path(tempfile.gettempdir()) / "solidon-cad-durchsicht-iso"
ISO.mkdir(exist_ok=True)
for _v in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_v] = str(ISO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TREE = str(HERE.parents[2])
if sys.path[0] != TREE:
    sys.path.insert(0, TREE)
import app  # noqa: E402

assert app.__file__.lower().startswith(TREE.lower()), app.__file__
