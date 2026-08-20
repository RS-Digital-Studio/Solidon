"""Die Suite fahren, je Testdatei ein Prozess.

    .venv\\Scripts\\python.exe tools/run_suite_isolated.py [muster …]

**Wofür das da ist.** Ein Absturz reißt die Suite seit Tagen sporadisch ab —
eine Zugriffsverletzung ohne Traceback, die Roadmap führt ihn als offenen
Punkt. Am 18.08.2026 wurde er häufig: vier Läufe in Folge fielen, und zwar
nach 228, 480, 3698 und 3907 Tests. Vier völlig verschiedene Stellen, drei
davon beim Leeren einer ``QListWidget``, eine beim Erzeugen eines ``QThread``.

Das ist die Signatur einer Beschädigung, die **kumuliert**: Irgendwo wird ein
Qt-Objekt doppelt freigegeben, und der Schaden schlägt später zu — dort, wo
viel auf einmal freigegeben oder neu angefordert wird. Der Ort des Absturzes
sagt deshalb nichts über seine Ursache, und eine Bisektion über Tests findet
nichts, weil es den einen schuldigen Test nicht gibt.

**Und genau deshalb hilft dieses Werkzeug.** Was über Dateigrenzen hinweg
kumuliert, kann es nicht, wenn jede Datei ihren eigenen Prozess bekommt. Der
erste Lauf so: 130 Dateien, 4164 Tests, **kein einziger Absturz** — und mit
zwölf Minuten sogar schneller als der Lauf am Stück, weil ein Absturz keinen
Neustart mehr kostet.

Damit ist es zweierlei: eine benutzbare Suite, solange der Absturz offen ist,
und ein Beleg dafür, wo er *nicht* liegt — keine Datei fällt für sich allein.

**Kein Ersatz für ``pytest -q``.** Was hier nicht geprüft wird, ist genau das,
was zwischen den Dateien passiert: Ein Test, der einen Zustand hinterlässt, den
der nächste findet, fällt hier durch die Maschen. Auf POSIX macht
``pytest --forked`` dasselbe je Test; unter Windows gibt es das nicht, und
darum steht dieses Werkzeug hier.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

#: Wie lange eine einzelne Datei laufen darf. Großzügig: ``test_performance``
#: misst gegen das Budget aus §31 und braucht seine Zeit.
BUDGET_SECONDS = 900

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def chosen_files(patterns: tuple[str, ...]) -> list[Path]:
    """Welche Dateien laufen — alle, oder die, auf die ein Muster passt."""
    files = sorted((ROOT / "tests").glob("test_*.py"))
    if not patterns:
        return files
    return [path for path in files if any(part in path.name for part in patterns)]


def counted(output: str) -> int:
    """Wie viele Tests eine Datei gemeldet hat."""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line:
            first = line.split()[0] if line.split() else ""
            return int(first) if first.isdigit() else 0
    return 0


def main() -> int:
    files = chosen_files(tuple(sys.argv[1:]))
    if not files:
        print("Keine Testdatei passt auf das Muster.")
        return 1

    print(f"{len(files)} Testdateien, je ein Prozess")
    failed: list[tuple[str, str]] = []
    total = 0
    start = time.monotonic()

    for path in files:
        try:
            finished = subprocess.run(
                [str(PYTHON), "-m", "pytest", "-q", str(path)],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=BUDGET_SECONDS,
            )
        except subprocess.TimeoutExpired:
            failed.append((path.name, f"über {BUDGET_SECONDS} s"))
            print(f"  {path.name:42s} Zeitgrenze")
            continue

        output = finished.stdout + finished.stderr
        total += counted(output)
        if finished.returncode == 0 and "Windows fatal" not in output:
            continue
        # Ein Absturz sagt etwas anderes als ein roter Test, und die
        # Unterscheidung ist der halbe Ertrag dieses Werkzeugs.
        reason = "Absturz" if "Windows fatal" in output else f"Code {finished.returncode}"
        failed.append((path.name, reason))
        print(f"  {path.name:42s} {reason}")

    print()
    print(f"Fertig in {(time.monotonic() - start) / 60:.1f} min — {total} Tests")
    if not failed:
        print("Alle Dateien für sich grün.")
        return 0
    print(f"{len(failed)} Dateien gefallen:")
    for name, reason in failed:
        print(f"  {name}: {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
