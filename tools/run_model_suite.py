"""Die ganze Kette über einen Ordner echter Modelle laufen lassen (Bauplan
§34, §35).

Der Referenzkorpus in ``tests/data`` ist gebaut, um klein zu sein und je eine
Sache zu treffen. Was er nicht kann, kann ein Ordner mit Modellen, die jemand
wirklich gedruckt hat: die Formen bringen, auf die niemand kommt, wenn er
konstruiert — eine Katze mit dreihunderttausend Dreiecken, ein aus einem Slicer
exportierter Schaber, ein Bowlingspiel als eine 3MF mit zwölf Körpern darin.

Das hier ist also kein Test. Es ist das, was einem sagt, welchen Test man
schreiben muss: jedes Modell durch die Eingangsstufe, die Merkmalserkennung und
die Schichtanalyse, mit dem, was brach, und dem, was es kostete.

    python tools/run_model_suite.py "F:/3D Druck/3D Drucker"
    python tools/run_model_suite.py --limit 10 --skip-slice
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.bootstrap import load_operations
from app.core.errors import AppError
from app.core.ingest.loader import READABLE_SUFFIXES, normalise, read_model
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.slice.analysis import slice_body

#: Über so vielen Dreiecken wird die Schichtanalyse übersprungen, außer sie
#: wird verlangt — eine Katze mit zwei Millionen Dreiecken ist eine
#: Leistungsmessung, kein Rauchtest.
SLICE_LIMIT = 400_000


@dataclass(slots=True)
class Outcome:
    """Was ein Modell getan hat."""

    path: Path
    triangles: int = 0
    watertight: bool = False
    seconds: dict[str, float] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    failure: str = ""

    @property
    def ok(self) -> bool:
        return not self.failure


def run_one(path: Path, layer_height: float, skip_slice: bool) -> Outcome:
    """Lesen, normalisieren, erkennen, schneiden — und auffangen, was
    herauskommt.
    """
    outcome = Outcome(path=path)
    try:
        payload = path.read_bytes()

        start = time.perf_counter()
        raw = read_model(payload, path.suffix)
        outcome.seconds["read"] = time.perf_counter() - start

        start = time.perf_counter()
        ingested = normalise(raw, "mm")
        outcome.seconds["ingest"] = time.perf_counter() - start
        outcome.findings.extend(entry.code for entry in ingested.findings)

        mesh = ingested.mesh
        outcome.triangles = mesh.triangle_count
        outcome.watertight = mesh.is_watertight

        start = time.perf_counter()
        found = detect(mesh)
        outcome.seconds["detect"] = time.perf_counter() - start
        outcome.findings.append(f"features={len(found)}")

        if not skip_slice and mesh.triangle_count <= SLICE_LIMIT:
            start = time.perf_counter()
            slice_body(mesh, layer_height)
            outcome.seconds["slice"] = time.perf_counter() - start
    except AppError as problem:
        outcome.failure = f"{type(problem).__name__}: {problem.title}"
    except Exception as problem:  # ein Rauchtest will die unerwarteten am meisten
        outcome.failure = f"{type(problem).__name__}: {problem}"
        outcome.findings.append(traceback.format_exc(limit=3).strip().splitlines()[-1])
    return outcome


def models(folder: Path, limit: int) -> list[Path]:
    known = {*READABLE_SUFFIXES}
    found = sorted(
        entry for entry in folder.rglob("*") if entry.is_file() and entry.suffix.lower() in known
    )
    return found[:limit] if limit else found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, nargs="?", default=Path("3D Drucker"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--layer-height", type=float, default=0.2)
    parser.add_argument("--skip-slice", action="store_true")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"Diesen Ordner gibt es nicht: {args.folder}")
        return 2

    load_operations()
    profiles.make_profile("centauri-carbon-2", "petg")

    found = models(args.folder, args.limit)
    print(f"{len(found)} Modelle in {args.folder}\n")

    outcomes: list[Outcome] = []
    for index, path in enumerate(found, start=1):
        outcome = run_one(path, args.layer_height, args.skip_slice)
        outcomes.append(outcome)
        total = sum(outcome.seconds.values())
        state = "ok " if outcome.ok else "FEHL"
        closed = "zu" if outcome.watertight else "offen"
        print(
            f"{index:3}/{len(found)} {state} {path.name[:46]:46} "
            f"{outcome.triangles:>8} {closed:5} {total:6.2f}s"
        )
        if outcome.failure:
            print(f"        {outcome.failure}")

    broken = [entry for entry in outcomes if not entry.ok]
    print(f"\n{len(outcomes) - len(broken)} von {len(outcomes)} durchgelaufen")
    if broken:
        print("\nGescheitert:")
        for entry in broken:
            print(f"  {entry.path.name}: {entry.failure}")

    slowest = sorted(outcomes, key=lambda entry: -sum(entry.seconds.values()))[:5]
    print("\nLangsamste:")
    for entry in slowest:
        parts = " ".join(f"{name} {value:.2f}s" for name, value in entry.seconds.items())
        print(f"  {entry.path.name[:40]:40} {parts}")

    open_models = [entry for entry in outcomes if entry.ok and not entry.watertight]
    print(f"\nNicht geschlossen: {len(open_models)} von {len(outcomes) - len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
