"""Rechnet einzelne Modelle des Korpuslaufs nach, einzeln und nacheinander.

Aufruf: python nachtrag.py <code-wurzel> <ergebnis.jsonl> <modell> [<modell> …]

Zwei Prozesse, die unter Windows an dieselbe Datei anhängen, überschreiben
sich gelegentlich: Anhängen ist dort Suchen ans Ende und Schreiben, nicht ein
Schritt. Was dabei verloren ging, wird hier allein in eine eigene Datei
nachgerechnet. Affinität wie im Korpuslauf ohne die Kerne 8 bis 11 (RM-272).
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = r"F:\3D Druck\.venv\Scripts\python.exe"


def main() -> int:
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 0xFFFFF0FF)
    root, out, models = sys.argv[1], sys.argv[2], sys.argv[3:]
    worst = 0
    for model in models:
        run = subprocess.run(
            [PY, str(HERE / "vorschlaege_korpus.py"), root, out, model],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        print(f"{model}\texit={run.returncode}", flush=True)
        if run.returncode:
            print(run.stderr[-1500:], flush=True)
            worst = run.returncode
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
