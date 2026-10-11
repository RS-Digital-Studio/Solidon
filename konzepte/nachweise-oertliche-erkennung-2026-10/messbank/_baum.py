"""Gemeinsamer Anfang der Messbank (RM-592): Baum eintragen, Nutzerordner isolieren, prüfen.

``setup(baum)`` setzt den Baum an ``sys.path[0]``, biegt die Nutzerverzeichnisse
in einen Temp-Ordner um, importiert ``app`` und bricht ab, wenn ``app`` nicht aus
dem Baum kommt — die ``.venv`` ist ein Editable-Install auf den Hauptbaum, und
ein Skript, das das nicht prüft, misst den falschen Stand. Erst danach darf eine
Sonde ``app.*`` importieren.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KUNDE = Path("F:/3D Dateien")


def setup(tree: str | Path) -> Path:
    """Baum eintragen, Nutzerordner isolieren, ``app`` prüfen; zurück kommt der Baum."""
    root = Path(tree).resolve()
    isolated = tempfile.mkdtemp(prefix="solidon-messbank-")
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        os.environ[variable] = isolated
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.dont_write_bytecode = True
    hauptbaum = "f:\\3d druck"
    sys.path[:] = [entry for entry in sys.path if entry.rstrip("\\/").lower() != hauptbaum]
    sys.path.insert(0, str(root))
    import app

    where = Path(app.__file__).resolve()
    if root not in where.parents:
        raise SystemExit(f"app kommt nicht aus {root}: {where}")
    # Die Arbeiter der Erkennung (RM-637) nur auf Verlangen: Die Messbank misst
    # sonst die CPU-Zeit eines Prozesses, und die verteilte Arbeit fehlte darin.
    try:
        from app.core.perceive import parallel
    except ImportError:
        pass
    else:
        parallel.use_workers(os.environ.get("MESSBANK_ARBEITER") == "1")
    if os.environ.get("MESSBANK_VORRANG") == "1" and os.name == "nt":
        # Unter fremder Volllast einen ruhigen Rechner nachbilden: Die Messung
        # bekommt ihre Kerne, die CPU-Zeit streut weniger (wie RM-496/RM-672).
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000080)
    return root


def activation_free() -> None:
    """Die Lizenzgrenze für die Sonde öffnen, wie die Suite es tut."""
    from app.core.activation import store as activation_store

    activation_store.DEMO_UNTIL = None
    activation_store.TRIAL_FROM = activation_store.DEMO_FROM
