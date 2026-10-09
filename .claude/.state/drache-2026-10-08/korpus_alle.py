"""Fährt korpus_kanal.py über F:\\3D Dateien, je Datei ein Prozess.

Aufruf: python korpus_alle.py <code-wurzel> <ergebnis.jsonl> [nebeneinander=2]

Ohne den Ordner „3D Drucker“ und ohne Dubletten nach Prüfsumme; klein zuerst.
Die Kerne 8 bis 11 dieser Maschine rechnen zeitweise falsch (RM-272) und
bleiben aus.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = r"F:\3D Druck\.venv\Scripts\python.exe"
CORPUS = Path(r"F:\3D Dateien")
SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".step", ".stp", ".glb"}
TIMEOUT = 40 * 60


def pin() -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 0xFFF0FF)


def files() -> list[Path]:
    seen: dict[str, Path] = {}
    for path in sorted(CORPUS.rglob("*")):
        if "3D Drucker" in path.parts or path.suffix.lower() not in SUFFIXES or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in seen or ("(1)" in seen[digest].name and "(1)" not in path.name):
            seen[digest] = path
    return sorted(seen.values(), key=lambda path: path.stat().st_size)


def one(root: str, out: str, model: Path) -> None:
    started = time.perf_counter()
    try:
        run = subprocess.run(
            [PY, str(HERE / "korpus_kanal.py"), root, out, str(model)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        line = f"{model.name}\texit={run.returncode}\t{time.perf_counter() - started:.0f}s"
        if run.returncode:
            line += "\n" + run.stderr[-800:]
    except subprocess.TimeoutExpired:
        line = f"{model.name}\tTIMEOUT"
    print(line, flush=True)


def main() -> int:
    pin()
    root, out = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    found = files()
    print(f"{len(found)} Dateien", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda model: one(root, out, model), found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
