"""Gemeinsamer Kopf der Sonden: Nutzerverzeichnisse isolieren, Baum vorn.

Die Sonden laufen mit der ``.venv`` des Hauptklons:

    .venv\\Scripts\\python.exe konzepte/nachweise-cad-p2-7/s1_register.py

Sie schreiben nichts ins Projekt; die Nutzerverzeichnisse werden in einen
Temp-Ordner umgebogen, damit keine Sonde Roberts echte Profile trifft (§38).
Der Projektbaum steht vorn im Suchpfad und wird über ``app.__file__``
geprüft — ein Skript im Unterordner lädt sonst ein fremdes ``app``.
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISO = Path(tempfile.gettempdir()) / "solidon-p27-iso"
ISO.mkdir(exist_ok=True)
for _v in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_v] = str(ISO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONUTF8", "1")
TREE = str(HERE.parents[1])
if sys.path[0] != TREE:
    sys.path.insert(0, TREE)
import app  # noqa: E402

assert app.__file__.lower().startswith(TREE.lower()), app.__file__
