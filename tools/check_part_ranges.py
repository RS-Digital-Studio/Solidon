"""Fährt den Bereichstest über die mitgelieferten Bausteine und schreibt den Nachweis (§24.3).

§24.3 verlangt für jeden Baustein den vollständigen kartesischen Grenzbereich —
wasserdicht, Mindestwand, keine Selbstdurchdringung, versprochene Merkmale —
und nennt einen Baustein ohne diesen Nachweis „nicht abgenommen". Der Lauf ist
seit dem 03.09.2026 kein Teil der Suite mehr (Entscheidung Robert: eine Minute
je Baustein, damals). Dieses Werkzeug fährt ihn und schreibt, was
herauskam, nach ``app/core/knowledge/data/part_ranges.toml`` — dort liest der
Katalog, ob er „über den ganzen Bereich geprüft" sagen darf, und
``test_every_shipped_part_carries_a_current_range_proof`` hält die Datei gegen
den heutigen Stand jedes Bausteins, ohne selbst zu rechnen.

    python tools/check_part_ranges.py                 # alle, die nicht mehr passen
    python tools/check_part_ranges.py --all           # alle, gleich ob sie passen
    python tools/check_part_ranges.py latch rib       # genau diese
    python tools/check_part_ranges.py --check         # nur vergleichen, nichts rechnen
    python tools/check_part_ranges.py --jobs 8        # Prozesse (Vorgabe: bis zu vier)

Jeder Baustein läuft in einem eigenen Prozess, wie ein Kunde ihn nie sähe: Der
Bereichstest sammelt native Netze, und ein Prozess je Baustein gibt sie mit
seinem Ende zurück. Der Lauf schreibt die Nutzerverzeichnisse in einen
Temp-Ordner um (§38) — eigene Bausteine des Entwicklers laden so nicht mit.

Exit-Code 0, wenn jeder gefahrene Baustein bestanden hat (bei ``--check``:
wenn der Nachweis zu jedem Baustein passt); 1 sonst. Die Datei wird auch bei
Fehlschlägen geschrieben — ein gebrochener Baustein steht dann als gebrochen
darin, und der Katalog warnt.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent


def _this_tree() -> None:
    """``app`` aus dem Baum dieses Werkzeugs, nicht aus der Editierinstallation.

    Die ``.venv`` installiert das Projekt editierbar auf den Hauptklon. Ohne
    diesen Pfad holte ``_isolate`` das Paket ``app`` von dort, bevor
    ``_registry`` den eigenen Baum vorn eintrug: In einem Worktree prüfte und
    schrieb der Lauf den Nachweis des Hauptklons.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


@contextmanager
def _isolate(parent: Path | None = None) -> Iterator[Path]:
    """Eigene Profile vor dem Import setzen und nach Erfolg oder Fehler wieder entfernen (§38)."""
    _this_tree()
    from app.core.paths import PROFILE_VARIABLES

    before = {variable: os.environ.get(variable) for variable in PROFILE_VARIABLES}
    with tempfile.TemporaryDirectory(prefix="solidon-part-ranges-", dir=parent) as isolated:
        try:
            for variable in PROFILE_VARIABLES:
                os.environ[variable] = isolated
            yield Path(isolated)
        finally:
            for variable, value in before.items():
                if value is None:
                    os.environ.pop(variable, None)
                else:
                    os.environ[variable] = value


def _registry() -> Any:
    """Die mitgelieferten Bausteine, ohne eigene aus dem Nutzerordner."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app.core.knowledge.parts import builtin

    return builtin.load()


def _run_one(name: str, temporary: Path | None = None) -> dict[str, Any]:
    """Ein Baustein, ein Prozess: den Bereichstest fahren und das Ergebnis melden."""
    with _isolate(temporary):
        registry = _registry()
        from app.core.knowledge.parts import range_check, range_proof

        spec = registry.get(name)
        profile = range_proof.reference_profile()
        started = time.perf_counter()
        report = range_check.check_part(spec, profile)
        return {
            "name": name,
            "version": spec.version,
            "fingerprint": range_proof.fingerprint(spec, profile),
            "corners": range_check.corner_count(spec.params),
            "checked": report.checked,
            "excluded": len(report.excluded),
            "failures": [(dict(failure.values), failure.reason) for failure in report.failures],
            "passed": report.passed,
            "seconds": time.perf_counter() - started,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("names", nargs="*", help="Bausteine; ohne Angabe alle, die nicht passen")
    parser.add_argument("--all", action="store_true", help="alle mitgelieferten Bausteine")
    parser.add_argument("--check", action="store_true", help="nur vergleichen, nichts rechnen")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args(argv)

    with _isolate() as temporary:
        return _run(args, temporary)


def _run(args: argparse.Namespace, profile_root: Path) -> int:
    """Plant und prüft innerhalb des Profils, das bis zum Ende aller Arbeiter lebt."""
    registry = _registry()
    from app.core.knowledge.parts import range_proof

    shipped = {spec.name: spec for spec in registry.all() if spec.source == "shipped"}
    unknown = sorted(set(args.names) - set(shipped))
    if unknown:
        print(f"Unbekannte Bausteine: {', '.join(unknown)}", file=sys.stderr)
        return 2
    profile = range_proof.reference_profile()
    proofs = range_proof.load()
    states = {name: range_proof.status(spec, profile, proofs) for name, spec in shipped.items()}
    if args.check:
        wrong = {name: state for name, state in states.items() if state != "proven"}
        for name, state in sorted(wrong.items()):
            print(f"{name}: {state}")
        print(f"{len(shipped) - len(wrong)} von {len(shipped)} Bausteinen nachgewiesen")
        return 1 if wrong else 0

    if args.names:
        wanted = sorted(args.names)
    elif args.all:
        wanted = sorted(shipped)
    else:
        wanted = sorted(name for name, state in states.items() if state != "proven")
    if not wanted:
        print("Der Nachweis passt zu jedem Baustein; nichts zu fahren.")
        return 0

    jobs = max(1, min(args.jobs, len(wanted)))
    parts = "Baustein" if len(wanted) == 1 else "Bausteine"
    processes = "Prozess" if jobs == 1 else "Prozessen"
    print(f"Fahre {len(wanted)} {parts} mit {jobs} {processes}: {', '.join(wanted)}")
    results: dict[str, dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=jobs, max_tasks_per_child=1) as pool:
        # Der Elternlauf besitzt auch die Arbeiterprofile und räumt sie nach
        # einem nativen Prozessabbruch, bei dem kein finally mehr laufen kann.
        futures = {pool.submit(_run_one, name, profile_root): name for name in wanted}
        for future in as_completed(futures):
            outcome = future.result()
            results[outcome["name"]] = outcome
            verdict = "bestanden" if outcome["passed"] else "GEBROCHEN"
            print(
                f"  {outcome['name']}: {outcome['checked']}/{outcome['corners']} Ecken, "
                f"{outcome['excluded']} erklärt ausgeschlossen, {verdict} "
                f"({outcome['seconds']:.1f} s)",
                flush=True,
            )
            for values, reason in outcome["failures"][:10]:
                print(f"      {values}: {reason}")

    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    entries = {name: entry for name, entry in proofs.items() if name in shipped}
    for name, outcome in results.items():
        entries[name] = range_proof.ProofEntry(
            name=name,
            version=str(outcome["version"]),
            fingerprint=str(outcome["fingerprint"]),
            corners=int(outcome["corners"]),
            checked=int(outcome["checked"]),
            excluded=int(outcome["excluded"]),
            failures=len(outcome["failures"]),
            passed=bool(outcome["passed"]),
            date=today,
        )
    target = range_proof.PROOF_FILE
    temporary = target.with_suffix(".toml.tmp")
    temporary.write_text(range_proof.render(entries, profile), encoding="utf-8", newline="\n")
    temporary.replace(target)
    broken = sorted(name for name, outcome in results.items() if not outcome["passed"])
    print(f"Nachweis geschrieben: {target.relative_to(ROOT).as_posix()}")
    if broken:
        print(f"Gebrochen: {', '.join(broken)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
