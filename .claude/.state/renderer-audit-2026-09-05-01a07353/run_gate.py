"""Protokolliert das vollständige Tor mit getrennten Ausgaben und echten Rückgabewerten."""

from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time


root = Path(__file__).resolve().parent
repository = root.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--manifest", type=Path, required=True)
args = parser.parse_args()
destination = (root / args.name).resolve()
if destination.parent != root or destination.exists():
    raise ValueError("Das Tor braucht einen neuen direkten Audit-Unterordner")
destination.mkdir()
manifest_path = args.manifest.resolve(strict=True)
manifest = json.loads(manifest_path.read_text(encoding="utf8"))


def hashes():
    """Hält die Inhalte der eigenen Dateien vor und nach dem Tor fest."""
    return {
        name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
        for name in manifest["files_sha256"]
    }


before = hashes()
environment = dict(os.environ)
environment.update(
    PYTHONIOENCODING="utf-8",
    SUITE_KERNE="1",
    SUITE_PYTHON=Path(sys.executable).as_posix(),
    S=f"Codex-01a07353-{args.name}",
)
commands = [
    ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
    ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("mypy", [sys.executable, "-m", "mypy"]),
    (
        "split-suite",
        [
            "C:/Program Files/Git/bin/bash.exe",
            ".claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh",
        ],
    ),
    ("performance", [sys.executable, "-m", "pytest", "-q", "-m", "performance"]),
]
records = []
for name, command in commands:
    print(f"START {name}", flush=True)
    started = time.time()
    with (destination / f"{name}.log").open("w", encoding="utf8") as output:
        run = subprocess.run(
            command,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=repository,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    record = {
        "name": name,
        "command": command,
        "exit": run.returncode,
        "started_at": started,
        "elapsed_seconds": time.time() - started,
    }
    records.append(record)
    (destination / "processes.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(record, ensure_ascii=False), flush=True)
after = hashes()
(destination / "source.json").write_text(
    json.dumps(
        {
            "repository": str(repository),
            "python": sys.executable,
            "before": before,
            "after": after,
            "unchanged": before == after,
            "shared_manifest": str(manifest_path),
            "matches_shared_snapshot": before == manifest["files_sha256"],
            "suite_workers": 1,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf8",
)
raise SystemExit(int(before != after or any(record["exit"] != 0 for record in records)))
