"""Verteilt ``einheit.py`` über die Modelle — ein Prozess je Modell, mehrere nebeneinander.

Aufruf: python treiber.py <code-wurzel> <ausgabeordner> <plan> [--arbeiter N]

Pläne:

``drucker``  die drei Modelle der Abnahme (Minigolf-Platte, Wedge-Lock,
             Waschschüssel) über jede Kombination aus Slicer und Drucker
``modelle``  jedes Modell aus ``F:\\3D Dateien`` (ohne „3D Drucker“, Dubletten
             nach Prüfsumme gestrichen) über die Heimkombinationen, klein zuerst

Wieder aufnehmbar: Ein Modell, dessen Ergebnis ``done`` trägt, läuft nicht
noch einmal; ein halbes setzt bei der nächsten Kombination fort. Liegt die
Datei ``PAUSE`` im Ausgabeordner, startet nichts Neues, und laufende Einheiten
halten vor ihrer nächsten Kombination an — für die Leistungsprüfung der
Release-Sitzung.
"""
# ruff: noqa: E501

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
ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
PLAN = sys.argv[3]
WORKERS = int(sys.argv[sys.argv.index("--arbeiter") + 1]) if "--arbeiter" in sys.argv else 2
PYTHON = Path(sys.executable)
CORPUS = Path(r"F:\3D Dateien")
#: Je Arbeiter eigene Kerne, damit zwei Slicer sich nicht gegenseitig bremsen.
#: Die Kerne 8 bis 11 rechnen auf dieser Maschine zeitweise falsch (RM-272)
#: und bleiben aus; 0 bis 7 bleiben für Tor und Messungen frei.
MASKS = ["FF0000", "FF000000", "F000"]

PRINTER_PLAN = [
    Path(r"F:\3D Druck\output\review\minigolf-2026-09-27\druckauftrag\solidon-0936.3mf"),
    CORPUS / "Wedge-Lock (Set).stl",
    CORPUS / "HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)" / "washing bowl v1.stl",  # noqa: RUF001
]
MODEL_SUFFIXES = {".stl", ".3mf", ".step", ".stp", ".obj", ".glb", ".ply"}


def corpus() -> list[Path]:
    seen: dict[str, Path] = {}
    for path in sorted(CORPUS.rglob("*")):
        if "3D Drucker" in path.parts or path.suffix.lower() not in MODEL_SUFFIXES or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # Von zwei gleichen Dateien die ohne „(1)“ im Namen.
        current = seen.get(digest)
        if current is None or ("(1)" in current.name and "(1)" not in path.name):
            seen[digest] = path
    return sorted(seen.values(), key=lambda p: p.stat().st_size)


def units() -> list[tuple[Path, str]]:
    if PLAN == "drucker":
        return [(model, "alle") for model in PRINTER_PLAN]
    if PLAN == "modelle":
        return [(model, "heim") for model in corpus()]
    raise SystemExit(f"unbekannter Plan: {PLAN}")


def result_of(model: Path) -> Path:
    safe = re.sub(r"[^\w.-]+", "_", model.stem)[:80]
    return OUT / f"{safe}.json"


def done(model: Path) -> bool:
    path = result_of(model)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(data.get("done")) and data.get("code") == str(ROOT)


def log(text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    with (OUT / "treiber.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def worker(number: int, tasks: queue.Queue[tuple[int, Path, str]], total: int) -> None:
    mask = MASKS[number % len(MASKS)]
    while True:
        try:
            index, model, spec = tasks.get_nowait()
        except queue.Empty:
            return
        while (OUT / "PAUSE").exists():
            time.sleep(30)
        started = time.perf_counter()
        log(f"[{index}/{total}] Arbeiter {number} ({mask}) beginnt {model.name}")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "GESAMT_KERNE": mask,
            "GESAMT_PAUSE": str(OUT / "PAUSE"),
        }
        safe = re.sub(r"[^\w.-]+", "_", model.stem)[:80]
        with (OUT / "logs" / f"{safe}.log").open("a", encoding="utf-8") as output:
            try:
                completed = subprocess.run(
                    [str(PYTHON), "-u", str(HERE / "einheit.py"), str(ROOT), str(model), str(OUT), spec],
                    stdout=output, stderr=subprocess.STDOUT, env=environment, timeout=8 * 3600,
                )
                code: object = completed.returncode
            except subprocess.TimeoutExpired:
                code = "Zeitlimit"
        log(f"[{index}/{total}] Arbeiter {number} fertig mit {model.name}: {code} nach {time.perf_counter() - started:.0f} s")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)
    planned = units()
    tasks: queue.Queue[tuple[int, Path, str]] = queue.Queue()
    for index, (model, spec) in enumerate(planned, start=1):
        if not done(model):
            tasks.put((index, model, spec))
    log(f"Plan {PLAN}: {len(planned)} Modelle, offen {tasks.qsize()}, Code {ROOT}, {WORKERS} Arbeiter")
    threads = [threading.Thread(target=worker, args=(number, tasks, len(planned))) for number in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    log(f"Plan {PLAN} beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
