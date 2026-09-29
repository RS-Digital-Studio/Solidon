"""Die Suite fahren, je Testdatei ein Prozess.

    python tools/run_suite_isolated.py [--release] [muster …]
    python tools/run_suite_isolated.py --release --ci-group windowed --shard-count 2 \
        --shard-index 0 --report-dir build/ci/windows-0

Der CI-Weg plant aus der aktuellen Sammlung, schreibt je Datei JUnit und
Protokoll und behält fehlende Berichte als Fehler. ``--plan-only`` sammelt
und verteilt ohne Testausführung; dafür ist ``--release`` nicht nötig.

Fenstertests laufen ausschließlich mit ``--release``; ohne das fährt jede
Datei ihre Tests ohne Fenster (``-m "not windowed"``). Leistungsprüfungen
bleiben auch dann dem getrennten Release-Lauf vorbehalten.

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

import argparse
import contextlib
import json
import math
import os
import platform
import secrets
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any

ROOT = Path(__file__).resolve().parent.parent
PYTHON = Path(sys.executable)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ci_shards import WINDOW_DURATIONS, balanced, read_durations  # noqa: E402

#: Wie lange eine einzelne Datei einschließlich ihres Abbaus laufen darf.
BUDGET_SECONDS = 900

CONTRACT_FILES = frozenset({"tests/test_print_settings_ui.py", "tests/test_render_factory.py"})
CI_MARKER = "windowed and not performance and not rendered"

#: Wie lange der Leser nach dem Prozessende noch auf den Rest der Ausgabe
#: wartet. Hält ein entkommener Enkel die Leitung offen, endet der Bericht
#: trotzdem; das Protokoll trägt dann, was bis dahin kam.
OUTPUT_DRAIN_SECONDS = 15.0


@dataclass(frozen=True)
class PlannedFile:
    """Eine aktuell gesammelte Datei mit Fallzahl und bloßer Zeitschätzung."""

    path: str
    expected_tests: int
    estimated_seconds: float


def plan_shards(
    counts: Mapping[str, int],
    weights: Mapping[str, float],
    fallback: float,
    *,
    group: str,
    shard_count: int,
) -> tuple[tuple[PlannedFile, ...], ...]:
    """Verteilt die gesammelte Menge vollständig, längste Datei zuerst; Pfade lösen Gleichstand."""
    if shard_count < 1 or (group == "contracts" and shard_count != 1):
        raise ValueError("Die Fensterverträge brauchen genau eine Gruppe; Shardanzahl prüfen.")
    if group not in {"contracts", "windowed"}:
        raise ValueError("Unbekannte CI-Gruppe; windowed oder contracts wählen.")
    if not counts.keys() >= CONTRACT_FILES:
        missing = ", ".join(sorted(CONTRACT_FILES - counts.keys()))
        raise ValueError(f"Fensterverträge fehlen in der aktuellen Sammlung: {missing}.")
    files = [
        PlannedFile(name, count, weights.get(name, fallback))
        for name, count in counts.items()
        if (name in CONTRACT_FILES) == (group == "contracts")
    ]
    if any(file.expected_tests < 1 for file in files):
        raise ValueError("Eine Datei enthält keine ausführbaren Fensterfälle; Sammlung prüfen.")
    if len(files) < shard_count:
        raise ValueError("Eine CI-Gruppe wäre leer; Sammlung und Shardanzahl prüfen.")
    by_path = {file.path: file for file in files}
    groups = balanced({file.path: file.estimated_seconds for file in files}, shard_count)
    return tuple(tuple(by_path[path] for path in group) for group in groups)


def junit_counts(path: Path) -> dict[str, int]:
    """Prüft Pytests JUnit-Bericht samt Fallzahl; eine grüne Textzeile ersetzt ihn nicht."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    if root.tag not in {"testsuite", "testsuites"} or not suites:
        raise ValueError("JUnit enthält keine Testsuite.")
    totals = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    for suite in suites:
        if suite.tag != "testsuite" or suite.find("testsuite") is not None:
            raise ValueError("JUnit enthält keine flache pytest-Testsuite.")
        counts = {name: int(suite.attrib[name]) for name in totals}
        cases = suite.findall("testcase")
        actual = {"tests": len(cases)}
        actual.update(
            {
                name: sum(case.find(tag) is not None for case in cases)
                for name, tag in (
                    ("failures", "failure"),
                    ("errors", "error"),
                    ("skipped", "skipped"),
                )
            }
        )
        if counts != actual or any(value < 0 for value in counts.values()):
            raise ValueError("JUnit-Fallzahlen widersprechen den enthaltenen Testfällen.")
        if sum(counts[name] for name in ("failures", "errors", "skipped")) > counts["tests"]:
            raise ValueError("JUnit meldet mehr Ergebnisse als Testfälle.")
        for name, value in counts.items():
            totals[name] += value
    totals["passed"] = totals["tests"] - sum(
        totals[name] for name in ("failures", "errors", "skipped")
    )
    return totals


def pytest_command(file: PlannedFile, junit: Path) -> list[str]:
    """Eine Fensterdatei, ein frischer Prozess, derselbe feste CI-Marker."""
    return [
        str(PYTHON),
        "-u",
        "-X",
        "faulthandler",
        "-m",
        "pytest",
        "-v",
        "-o",
        "faulthandler_timeout=120",
        "--durations=30",
        f"--junitxml={junit}",
        "-m",
        CI_MARKER,
        file.path,
    ]


def stop_process_tree(child: subprocess.Popen[bytes]) -> str | None:
    """Beendet die isolierte Prozessgruppe samt nativen Fenster-Kindprozessen."""
    problem = None
    if sys.platform == "win32":
        try:
            stopped = subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if stopped.returncode != 0:
                problem = (
                    "Prozessbaum ließ sich nicht vollständig beenden "
                    f"(taskkill {stopped.returncode})."
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            problem = f"Prozessbaum ließ sich nicht vollständig beenden: {error}"
    else:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as error:
            problem = f"Prozessgruppe ließ sich nicht vollständig beenden: {error}"
    if child.poll() is None:
        child.kill()
    child.wait()
    return problem


def copy_output(
    source: IO[bytes],
    log: IO[bytes] | None,
    console: IO[bytes] | None,
    detached: threading.Event | None = None,
) -> None:
    """Schreibt die Ausgabe des Prüfprozesses ins Protokoll und zugleich in die Konsole.

    Die Konsole ist das CI-Protokoll: Dort steht der Test, an dem eine
    Datei hängt, noch bevor ein Bericht existiert — und nach einem Fristablauf
    des ganzen Jobs gibt es keinen.

    **Gelesen wird bis zum Ende, geschrieben nur, solange es geht.** Ein Ziel,
    das einen Schreibfehler wirft, fällt weg; hörte das Lesen mit ihm auf,
    stünde der Prüfprozess bei voller Leitung und fiele erst nach der
    Zeitgrenze durch statt mit seinem Ergebnis. Ist ``detached`` gesetzt,
    gehört die Leitung nur noch einem entkommenen Nachfahren: Sie wird weiter
    geleert, aber nirgends mehr hingeschrieben — und am Ende von hier
    geschlossen, denn ``Popen`` hat sie dann schon abgegeben.
    """
    try:
        _drain(source, log, console, detached)
    finally:
        closing = getattr(source, "close", None)
        if closing is not None:
            closing()


def _drain(
    source: IO[bytes],
    log: IO[bytes] | None,
    console: IO[bytes] | None,
    detached: threading.Event | None,
) -> None:
    """Liest die Leitung bis zu ihrem Ende; die Regeln stehen an :func:`copy_output`."""
    while True:
        try:
            chunk = source.read1(65536)  # type: ignore[attr-defined]
        except OSError, ValueError:
            return
        if not chunk:
            return
        if detached is not None and detached.is_set():
            continue
        if log is not None:
            try:
                log.write(chunk)
                log.flush()
            except OSError, ValueError:
                log = None
        if console is not None:
            try:
                console.write(chunk)
                console.flush()
            except OSError, ValueError:
                console = None


def run_ci_file(
    file: PlannedFile, report_dir: Path, *, timeout: float, command: Sequence[str] | None = None
) -> dict[str, Any]:
    """Hält Protokoll, wirklichen Exit und Bericht zusammen; Zeitablauf beendet den Prozessbaum."""
    stem = file.path.replace("/", "__").removesuffix(".py")
    log = report_dir / f"{stem}.log"
    junit = report_dir / f"{stem}.xml"
    # Ein alter Bericht darf einen neuen abgebrochenen Prozess nie retten.
    junit.unlink(missing_ok=True)
    argv = list(command) if command is not None else pytest_command(file, junit)
    result: dict[str, Any] = {
        **asdict(file),
        "command": argv,
        "exit_code": None,
        "timed_out": False,
        "counts": None,
        "log": log.name,
        "junit": junit.name,
        "issues": [],
        "notes": [],
    }
    started = time.monotonic()
    console = getattr(sys.stdout, "buffer", None)
    with log.open("wb") as output:
        try:
            with subprocess.Popen(
                argv,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1"},
                start_new_session=os.name != "nt",
            ) as child:
                assert child.stdout is not None
                detached = threading.Event()
                copier = threading.Thread(
                    target=copy_output,
                    args=(child.stdout, output, console, detached),
                    name=f"Ausgabe {file.path}",
                    daemon=True,
                )
                copier.start()
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    problem = stop_process_tree(child)
                    if problem:
                        result["issues"].append(problem)
                    result["timed_out"] = True
                    result["issues"].append(f"Zeitgrenze von {timeout:g} s überschritten.")
                except BaseException:
                    stop_process_tree(child)
                    raise
                copier.join(OUTPUT_DRAIN_SECONDS)
                if copier.is_alive():
                    # Der Faden blockiert im Lesen und hält dabei die Sperre des
                    # Lesers; ``Popen.__exit__`` schlösse ihn und wartete damit
                    # auf den Nachfahren. Die Leitung gehört jetzt dem Faden.
                    detached.set()
                    child.stdout = None
                    result["notes"].append(
                        "Ein Nachfahre hielt die Ausgabe nach dem Prozessende offen; "
                        "das Protokoll endet mit dem Bericht."
                    )
                result["exit_code"] = child.returncode
        except OSError as error:
            result["issues"].append(f"Prüfprozess konnte nicht starten: {error}")
    result["process_seconds"] = time.monotonic() - started
    if result["exit_code"] != 0:
        result["issues"].append(f"Prozessausgang {result['exit_code']} ist nicht erfolgreich.")
    try:
        counts = junit_counts(junit)
        result["counts"] = counts
        if counts["tests"] != file.expected_tests:
            result["issues"].append(
                f"JUnit nennt {counts['tests']} Einträge für {file.expected_tests} gesammelte "
                "Fälle; ein Fehler in Aufbau oder Abbau zählt als eigener Eintrag."
            )
        if counts["failures"] or counts["errors"]:
            result["issues"].append("JUnit enthält fehlgeschlagene Tests oder Fehler.")
    except (OSError, ET.ParseError, ValueError, KeyError) as error:
        result["issues"].append(f"JUnit-Bericht fehlt oder ist ungültig: {error}")
    result["success"] = not result["issues"]
    return result


def write_ci_summary(report_dir: Path, summary: dict[str, Any]) -> None:
    """Schreibt Zwischenstände; ein abgebrochener Lauf bleibt sichtbar unvollständig."""
    (report_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# CI-Fenstergruppe {summary['group']}",
        "",
        f"Stand: {summary['status']}; Shard {summary['shard_index'] + 1}/{summary['shard_count']}.",
        f"Commit: {summary['commit'] or 'lokal'}; Plattform: {summary['platform']}.",
        f"Geplant: {len(summary['selected'])} Dateien, "
        f"{sum(file['expected_tests'] for file in summary['selected'])} Fälle. "
        f"Abgeschlossen: {len(summary['results'])} Dateien.",
        "",
        "| Datei | Fälle (Soll/Ist) | Sekunden | Exit | Ergebnis |",
        "|---|---:|---:|---:|---|",
    ]
    details = []
    for result in summary["results"]:
        count = result["counts"]["tests"] if result["counts"] else "fehlt"
        outcome = "grün" if result["success"] else "rot"
        lines.append(
            f"| {result['path']} | {result['expected_tests']}/{count} | "
            f"{result['process_seconds']:.2f} | {result['exit_code']} | {outcome} |"
        )
        for issue in result["issues"]:
            details.append(f"{result['path']}: {issue}")
    completed = {result["path"] for result in summary["results"]}
    for file in summary["selected"]:
        if file["path"] not in completed:
            lines.append(
                f"| {file['path']} | {file['expected_tests']}/offen "
                "| offen | offen | nicht ausgeführt |"
            )
    lines.extend(f"\n{detail}" for detail in details)
    for issue in summary["issues"]:
        lines.append(f"\n{issue}")
    (report_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ci(arguments: argparse.Namespace) -> int:
    """Sammelt die gesamte CI-Menge, plant identisch in jedem Shard und fährt nur dessen Dateien."""
    from tools.list_windowed_tests import collect_ci_window_counts

    report_dir = arguments.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schema": 1,
        "group": arguments.ci_group,
        "shard_index": arguments.shard_index,
        "shard_count": arguments.shard_count,
        "commit": os.environ.get("GITHUB_SHA", ""),
        "platform": platform.platform(),
        "python": sys.version,
        "status": "collecting",
        "plan": [],
        "selected": [],
        "results": [],
        "issues": [],
    }
    started = time.monotonic()
    github = os.environ.get("GITHUB_ACTIONS") == "true"
    write_ci_summary(report_dir, summary)
    try:
        counts = {
            path.relative_to(ROOT).as_posix(): count
            for path, count in collect_ci_window_counts((ROOT / "tests",)).items()
        }
        weights, fallback = read_durations(WINDOW_DURATIONS)
        shards = plan_shards(
            counts, weights, fallback, group=arguments.ci_group, shard_count=arguments.shard_count
        )
        summary["plan"] = [[asdict(file) for file in shard] for shard in shards]
        selected = shards[arguments.shard_index]
        summary["selected"] = [asdict(file) for file in selected]
        summary["status"] = "planned" if arguments.plan_only else "running"
        write_ci_summary(report_dir, summary)
        if not arguments.plan_only:
            for file in selected:
                heading = f"{file.path} ({file.expected_tests} Fälle)"
                print(f"::group::{heading}" if github else f"Prüfe {heading}", flush=True)
                try:
                    with verbatim_output(github=github):
                        result = run_ci_file(file, report_dir, timeout=arguments.timeout)
                finally:
                    if github:
                        print("::endgroup::", flush=True)
                for note in result["notes"]:
                    print(annotation("warning", file.path, note, github=github), flush=True)
                if not result["success"]:
                    message = " ".join(result["issues"])
                    print(annotation("error", file.path, message, github=github), flush=True)
                summary["results"].append(result)
                write_ci_summary(report_dir, summary)
            summary["status"] = (
                "passed" if all(result["success"] for result in summary["results"]) else "failed"
            )
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        summary["issues"].append(f"CI-Auswahl oder Bericht prüfen: {error}")
        summary["status"] = "failed"
    summary["process_seconds"] = time.monotonic() - started
    write_ci_summary(report_dir, summary)
    # Ein Sammlungs- oder Planungsfehler gehört ins Protokoll, nicht nur in die
    # Übersicht: Dort stand sonst allein ``failed: …/summary.md``. Der Wortlaut
    # von pytest bleibt dabei Text, die erste Zeile wird die Anmerkung.
    for issue in summary["issues"]:
        headline, _, details = issue.partition("\n")
        if details:
            with verbatim_output(github=github):
                print(details, flush=True)
        title = f"CI-Gruppe {summary['group']}"
        print(annotation("error", title, headline, github=github), flush=True)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with Path(step_summary).open("a", encoding="utf-8") as page:
            page.write((report_dir / "summary.md").read_text(encoding="utf-8") + "\n")
    print(f"{summary['status']}: {report_dir / 'summary.md'}", flush=True)
    return int(summary["status"] == "failed")


@contextlib.contextmanager
def verbatim_output(*, github: bool) -> Iterator[None]:
    """Was darin ausgegeben wird, bleibt Text — auch eine Zeile mit ``::error::``.

    Unter GitHub hält ``::stop-commands::`` die Workflow-Befehle an, bis das
    Zeichen wiederkommt. **Das Zeichen braucht eine eigene Zeile.** Ein
    abgebrochener Prüfprozess endet oft mitten in einer: ``pytest -v``
    schreibt den Testnamen vor dem Ergebnis, und die Zeitgrenze oder ein
    Absturz ohne Traceback kommt dazwischen. Hinter dem Rest dieser Zeile
    erkennt GitHub die Fortsetzung nicht, und jede weitere Gruppe und
    Anmerkung des Jobs bliebe Text — auch die der Datei, die gerade rot wurde.
    """
    token = secrets.token_hex(16)
    if github:
        print(f"::stop-commands::{token}", flush=True)
    try:
        yield
    finally:
        print(flush=True)
        if github:
            print(f"::{token}::", flush=True)


def annotation(level: str, path: str, message: str, *, github: bool) -> str:
    """Eine Zeile für das Protokoll; unter GitHub als Anmerkung am Lauf.

    GitHub liest ``%``, Zeilenumbrüche und in den Eigenschaften auch ``:``
    und ``,`` als Steuerzeichen — maskiert nach dessen Regel.
    """
    if not github:
        return f"{'rot' if level == 'error' else 'Hinweis'}: {path}: {message}"
    text = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    title = path.replace("%", "%25").replace(":", "%3A").replace(",", "%2C")
    return f"::{level} title={title}::{text}"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("patterns", nargs="*", help="Dateinamensmuster; leer: alle Testdateien")
    parser.add_argument(
        "--release", action="store_true", help="beim Release auch Fensterdateien fahren"
    )
    parser.add_argument("--ci-group", choices=("windowed", "contracts"))
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--plan-only", action="store_true", help="nur sammeln und aufteilen")
    parser.add_argument(
        "--timeout",
        type=float,
        default=BUDGET_SECONDS,
        help="Sekunden je Datei einschließlich Abbau, lokal wie in der CI",
    )
    arguments = parser.parse_args(argv)
    if not math.isfinite(arguments.timeout) or arguments.timeout <= 0:
        parser.error("Die Zeitgrenze muss positiv und endlich sein.")
    if arguments.ci_group:
        if not arguments.release and not arguments.plan_only:
            parser.error("CI-Fensterläufe brauchen --release; nur --plan-only sammelt ohne Lauf.")
        if arguments.report_dir is None or arguments.patterns:
            parser.error("CI-Gruppen brauchen --report-dir und erlauben keine Dateifilter.")
        if not 0 <= arguments.shard_index < arguments.shard_count:
            parser.error("Shardindex muss zwischen 0 und Shardanzahl minus 1 liegen.")
        return run_ci(arguments)
    if (
        arguments.plan_only
        or arguments.report_dir
        or arguments.shard_count != 1
        or arguments.shard_index
    ):
        parser.error("Planung, Shards und Berichte brauchen eine --ci-group.")
    return run_local(
        tuple(arguments.patterns), release=arguments.release, timeout=arguments.timeout
    )


def run_local(patterns: tuple[str, ...], *, release: bool, timeout: float = BUDGET_SECONDS) -> int:
    """Bewahrt den lokalen Dateimusterlauf und seine bestehende Markerwahl."""
    from tools.affected_tests import split_windowed

    files = chosen_files(patterns)
    if not files:
        print("Keine Testdatei passt auf das Muster.")
        return 1

    windowed, plain = split_windowed(files)
    selected = sorted({*plain, *(windowed if release else [])})
    markexpr = "not performance" if release else "not performance and not windowed and not rendered"
    if not release and windowed:
        print("Zurückgestellt: die Fenstertests dieser Dateien nur mit --release.")
        for path in sorted(windowed):
            print(f"  {path.name}")
    only_performance = sorted(set(files) - set(plain) - set(windowed))
    if only_performance:
        print("Nur Leistungsprüfungen — separat beim Release:")
        for path in only_performance:
            print(f"  {path.name}")
    if not selected:
        print("Keine regulären Tests ausgewählt; kein Testlauf gestartet.")
        return 0
    files = selected

    print(f"{len(files)} Testdateien, je ein Prozess")
    failed: list[tuple[str, str]] = []
    total = 0
    start = time.monotonic()

    for path in files:
        try:
            finished = subprocess.run(
                [str(PYTHON), "-m", "pytest", "-q", "-m", markexpr, str(path)],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            failed.append((path.name, f"über {timeout:g} s"))
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
