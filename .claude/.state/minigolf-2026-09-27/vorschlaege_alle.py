"""Fährt vorschlaege_korpus.py über F:\\3D Dateien, je Datei ein Prozess, mehrere nebeneinander.

Aufruf: python vorschlaege_alle.py <code-wurzel> <ergebnis.jsonl> [nebeneinander=3]

Die Kerne 8 bis 11 dieser Maschine rechnen zeitweise falsch (RM-272); der
Treiber setzt deshalb seine Affinität ohne sie, und die Kinder erben sie.
"""

import ctypes
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = r"F:\3D Druck\.venv\Scripts\python.exe"
CORPUS = Path(r"F:\3D Dateien")
SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".step", ".stp"}
TIMEOUT = 30 * 60


def pin() -> None:
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 0xFFFFF0FF)


def one(root: str, out: str, model: Path) -> str:
    started = time.perf_counter()
    try:
        run = subprocess.run(
            [PY, str(HERE / "vorschlaege_korpus.py"), root, out, str(model)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        line = f"{model.relative_to(CORPUS)}\texit={run.returncode}\t{time.perf_counter() - started:.1f}s"
        if run.returncode != 0:
            line += "\n" + run.stderr[-1500:]
    except subprocess.TimeoutExpired:
        line = f"{model.relative_to(CORPUS)}\tTIMEOUT"
    print(line, flush=True)
    return line


def main() -> int:
    pin()
    root, out = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    files = sorted(
        (p for p in CORPUS.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES and p.stat().st_size < 150_000_000),
        key=lambda p: p.stat().st_size,
    )
    print(f"{len(files)} Dateien, {workers} nebeneinander", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda model: one(root, out, model), files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
