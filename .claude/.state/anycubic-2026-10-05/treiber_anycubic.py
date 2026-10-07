"""Verteilt ``einheit_anycubic.py`` über die Modelle — Verifikation von Anycubic Slicer Next.

Auftrag Robert, 05.10.2026: Anycubic Slicer Next vollständig aufnehmen und über
alle Modelle verifizieren, mit allen unterstützten Druckern. Zwei Pläne:

``drucker``  die drei Abnahmemodelle der Slicer-Matrix (Minigolf-Platte,
             Wedge-Lock, Waschschüssel) an jedem der 39 Anycubic-Drucker
``modelle``  jedes Modell aus ``F:\3D Dateien`` (ohne „3D Drucker“, Dubletten
             nach Prüfsumme gestrichen) an Kobra S1 und Kobra S1 Max

Wieder aufnehmbar: Ein Modell, dessen Ergebnis ``done`` trägt, läuft nicht noch
einmal. Kerne wie in ``tools/matrix_driver.py`` (8 bis 11 bleiben aus, RM-272).
Aufruf aus der Wurzel: .venv/Scripts/python.exe .claude/.state/anycubic-2026-10-05/treiber_anycubic.py <ausgabeordner> <plan> [--arbeiter N]
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = Path(sys.argv[1]).resolve()
PLAN = sys.argv[2]
WORKERS = int(sys.argv[sys.argv.index("--arbeiter") + 1]) if "--arbeiter" in sys.argv else 3
CORPUS = Path(r"F:\3D Dateien")
MASKS = ["FF0000", "FF000000", "F000"]
PRINTER_PLAN = [
    # Die alte ``solidon-0936.3mf`` ging im örtlichen ``output/`` verloren; die neue
    # Platte liegt neben ihrer Quelle ``x.p3d`` im Korpus (RM-525).
    CORPUS / "Mini+Golf+All+Set-P1S_stls" / "minigolf-platte.3mf",
    CORPUS / "Wedge-Lock (Set).stl",
    CORPUS / "HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)" / "washing bowl v1.stl",  # noqa: RUF001
]
SUFFIXES = {".stl", ".3mf", ".step", ".stp", ".obj", ".glb", ".ply"}


def corpus() -> list[Path]:
    seen: dict[str, Path] = {}
    for path in sorted(CORPUS.rglob("*")):
        if "3D Drucker" in path.parts or path.suffix.lower() not in SUFFIXES or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        current = seen.get(digest)
        if current is None or ("(1)" in current.name and "(1)" not in path.name):
            seen[digest] = path.resolve()
    return sorted(seen.values(), key=lambda path: path.stat().st_size)


def units() -> list[tuple[Path, str]]:
    if PLAN == "drucker":
        return [(model, "alle") for model in PRINTER_PLAN]
    if PLAN == "modelle":
        return [(model, "heim") for model in corpus()]
    raise SystemExit(f"unbekannter Plan: {PLAN}")


def result_of(model: Path) -> Path:
    return OUT / (re.sub(r"[^\w.-]+", "_", model.stem)[:80] + ".json")


def finished(model: Path) -> bool:
    try:
        return bool(json.loads(result_of(model).read_text(encoding="utf-8")).get("done"))
    except (OSError, ValueError):
        return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    todo: queue.Queue[tuple[Path, str]] = queue.Queue()
    planned = units()
    for unit in planned:
        if not finished(unit[0]):
            todo.put(unit)
    log = (OUT / "treiber.log").open("a", encoding="utf-8", buffering=1)
    log.write(f"{time.strftime('%H:%M:%S')} Plan {PLAN}: {len(planned)} Modelle, offen {todo.qsize()}\n")

    def work(mask: str) -> None:
        while True:
            try:
                model, spec = todo.get_nowait()
            except queue.Empty:
                return
            env = {**os.environ, "GESAMT_KERNE": mask, "OPENBLAS_NUM_THREADS": "1", "PYTHONUTF8": "1"}
            started = time.time()
            with (OUT / "einheiten.log").open("a", encoding="utf-8") as stream:
                completed = subprocess.run(
                    [
                        sys.executable, "-u", str(HERE / "einheit_anycubic.py"),
                        str(ROOT), str(model), str(OUT), spec,
                    ],
                    env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=6 * 3600,
                )
            log.write(
                f"{time.strftime('%H:%M:%S')} {model.name}: Exit {completed.returncode}, "
                f"{time.time() - started:.0f} s, offen {todo.qsize()}\n"
            )

    threads = [threading.Thread(target=work, args=(MASKS[i % len(MASKS)],)) for i in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    log.write(f"{time.strftime('%H:%M:%S')} fertig\n")
    (OUT / ".status").write_text("complete", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
