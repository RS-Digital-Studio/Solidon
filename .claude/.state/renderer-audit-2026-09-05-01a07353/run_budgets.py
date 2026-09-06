"""Fährt die abschließenden Leistungsfälle nacheinander mit derselben festen Quelle."""

from pathlib import Path
import argparse
import json
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--name", required=True)
args = parser.parse_args()
source = args.source.resolve(strict=True)
destination = (root / args.name).resolve()
if destination.parent != root or destination.exists():
    raise ValueError("Die Messreihe braucht einen neuen direkten Audit-Unterordner")
destination.mkdir()
cases = [(0, "full", "product")]
cases += [(stage, "full", "solid-no-edges") for stage in (0, 1, 2)]
cases += [(stage, "lod", "product") for stage in (1, 2)]
records = []
for stage, display, appearance in cases:
    for renderer in ("gfx", "vtk"):
        name = f"{renderer}-s{stage}-{display}-{appearance}"
        print(f"START {name}", flush=True)
        command = [sys.executable, str(root / "budget_probe.py"),
                   "--renderer", renderer, "--stage", str(stage), "--display", display,
                   "--appearance", appearance, "--frames", "120", "--nvidia-smi",
                   "--codebase", str(source), "--output", str(destination / name)]
        started = time.time()
        with (destination / f"{name}.log").open("w", encoding="utf8") as output:
            run = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                 cwd=source, creationflags=subprocess.CREATE_NO_WINDOW)
        record = {"name": name, "exit": run.returncode, "command": command,
                  "started_at": started, "elapsed_seconds": time.time() - started}
        records.append(record)
        (destination / "processes.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps(record, ensure_ascii=True), flush=True)
        if run.returncode != 0:
            raise SystemExit(run.returncode)
raise SystemExit(0)
