"""Fährt druck.py, probe_features.py und probe_ops.py über den Minigolf-Satz, je Datei und Stufe ein Prozess.

Aufruf: python alle.py <ausgabeordner> [namensteil …]
"""

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
CORPUS = Path(r"F:\3D Dateien\Mini+Golf+All+Set-P1S_stls")
FEATURES = ROOT / ".claude" / ".state" / "merkmale-durchsicht-2026-09-15"
TIMEOUT = 40 * 60


def run(args: list[str], log) -> None:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        line = f"{Path(args[1]).name}\t{Path(args[2]).name}\texit={proc.returncode}\t{time.perf_counter() - started:.1f}s"
        if proc.returncode != 0:
            line += "\n" + proc.stderr[-3000:]
    except subprocess.TimeoutExpired:
        line = f"{Path(args[1]).name}\t{Path(args[2]).name}\tTIMEOUT nach {TIMEOUT}s"
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


def main() -> int:
    out = Path(sys.argv[1])
    only = sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    (out / "features").mkdir(exist_ok=True)
    (out / "ops").mkdir(exist_ok=True)
    files = sorted(CORPUS.glob("*.stl"), key=lambda p: p.stat().st_size)
    if only:
        files = [p for p in files if any(o in p.name for o in only)]
    with (out / "lauf.log").open("a", encoding="utf-8") as log:
        for number, path in enumerate(files, start=1):
            print(f"[{number}/{len(files)}] {path.name}", flush=True)
            stem = path.stem
            run([PY, str(HERE / "druck.py"), str(path), str(out / "druck.jsonl"), str(out / "work" / stem)], log)
            if not (out / "features" / f"{stem}.json").exists():
                run([PY, str(FEATURES / "probe_features.py"), str(path), str(out / "features" / f"{stem}.json")], log)
            if not (out / "ops" / f"{stem}.json").exists():
                run([PY, str(FEATURES / "probe_ops.py"), str(path), str(out / "ops" / f"{stem}.json"), "2"], log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
