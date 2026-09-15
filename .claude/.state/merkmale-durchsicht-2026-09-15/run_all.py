"""Fährt probe_features.py über jede STL/3MF im Downloads-Ordner, ein Prozess je Datei."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = str(Path(__file__).resolve().parents[3] / ".venv" / "Scripts" / "python.exe")
DOWNLOADS = Path(os.environ.get("SOLIDON_KORPUS", Path.home() / "Downloads"))
OUT = HERE / "report"
OUT.mkdir(exist_ok=True)
TIMEOUT = 20 * 60

files = sorted(
    [p for p in DOWNLOADS.iterdir() if p.suffix.lower() in (".stl", ".3mf")],
    key=lambda p: p.stat().st_size,
)
only = sys.argv[1:]
if only:
    files = [p for p in files if any(o in p.name for o in only)]
log = (OUT / "run.log").open("a", encoding="utf-8")
for path in files:
    target = OUT / (
        path.stem.replace("+", "_").replace(" ", "_") + path.suffix.replace(".", "_") + ".json"
    )
    if target.exists() and not only:
        continue
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [PY, str(HERE / "probe_features.py"), str(path), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        line = f"{path.name}\texit={proc.returncode}\t{time.perf_counter() - t0:.1f}s\t{proc.stdout.strip()[-200:]}"
        if proc.returncode != 0:
            line += "\n" + proc.stderr[-2000:]
    except subprocess.TimeoutExpired:
        line = f"{path.name}\tTIMEOUT nach {TIMEOUT}s"
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()
