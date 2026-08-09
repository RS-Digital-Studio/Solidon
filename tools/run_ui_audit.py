"""Den ganzen Bestand einmal durch die laufende Oberfläche schicken.

    .venv\\Scripts\\python.exe tools/run_ui_audit.py [ziel]

Öffnet jedes Projekt und liest jedes Modell, das auf dieser Maschine liegt —
die Beispiele, die echten Druckprojekte, den Testkorpus —, lässt die Szene
auswerten, sammelt die Befunde und geht bis zum geschriebenen Exportpaket.
Zum Schluss entsteht ein Projekt von Null, damit auch der Weg geprüft ist, den
ein neuer Nutzer nimmt.

**Warum durch die Oberfläche und nicht gegen den Kern.** Die Suite prüft den
Kern gründlich, und trotzdem ist der Kern nicht das, was jemand bedient. Was
hier zusätzlich mitläuft, sind die Arbeitsfäden, die Signale, der Viewport und
die Reihenfolge, in der beides passiert — genau die Stellen, an denen ein
Fehler erst auftritt, wenn ein Mensch davorsitzt.

Was **nicht** durch die Oberfläche geht, ist die Dateiauswahl: Zielpfade
kommen hier direkt, statt aus einem Systemdialog. Der Dialog gehört dem
Betriebssystem, nicht dieser Anwendung, und ein Test, der auf ihn wartet,
wartet für immer.

Das Ergebnis ist ein Bericht, kein bestanden/durchgefallen. Ein Modell aus dem
Netz, das nicht wasserdicht ist, ist ein Befund über das Modell — nicht über
die Anwendung. Unterschieden wird deshalb zwischen **Ausnahmen** (die
Anwendung ist gestolpert) und **Befunden** (die Anwendung hat etwas gemeldet,
und das war ihre Aufgabe).
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Vor allem, was Qt anfasst: die echte Plattform. Offscreen hat auf dieser
# Maschine keine Schriften, und der Viewport rendert dort nichts.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication, QDialog

#: Wie lange eine einzelne Auswertung dauern darf, in Sekunden.
#:
#: Großzügig: ein Netz mit hunderttausend Dreiecken braucht seine Zeit, und
#: ein Abbruch wegen Ungeduld wäre ein Befund über diese Datei, nicht über die
#: Anwendung. Wer die Grenze reißt, wird als solcher gemeldet.
BUDGET = 120.0

#: Wo gesucht wird. Ordner, die es nicht gibt, werden übersprungen.
PROJECT_DIRS = ("app/examples", "3D Drucker")
MODEL_DIRS = ("3D Drucker", "tests/data/meshes")

#: Modellendungen, die die Anwendung einlesen können soll.
MODEL_SUFFIXES = (".stl", ".3mf", ".step", ".stp", ".obj")


@dataclass
class Outcome:
    """Was bei einem Stück Bestand herauskam."""

    name: str
    kind: str
    seconds: float = 0.0
    objects: int = 0
    findings: list[str] = field(default_factory=list)
    exported: int = 0
    error: str = ""

    @property
    def broke(self) -> bool:
        return bool(self.error)


def settle(app: QApplication, rounds: int = 10) -> None:
    """Der Oberfläche Zeit geben, ihre Signale abzuarbeiten."""
    for _round in range(rounds):
        app.processEvents()


def await_result(app: QApplication, session: Any, previous: Any, seconds: float = BUDGET) -> bool:
    """Warten, bis **ein neues** Ergebnis da ist — nicht bloß irgendeins.

    Der Unterschied ist kein Feinschliff, sondern der zwischen Messen und
    Danebenmessen. ``last_result`` steht nach dem Anlegen eines Projekts
    bereits (auf der leeren Szene), und ``busy`` ist erst gesetzt, wenn der
    Arbeitsfaden wirklich angelaufen ist. Wer nur auf „vorhanden und nicht
    beschäftigt" wartet, kommt in dem Augenblick durch, in dem noch gar
    nichts passiert ist — und misst das Ergebnis von vorher.

    So gefunden: ein 177 KB großes Netz kam als „0 Objekte" zurück, und die
    Auswertung eines vollen Projekts angeblich in 0,2 Sekunden.

    Verglichen wird die Identität, nicht der Inhalt: jede Auswertung erzeugt
    ein neues ``EvaluationResult``, auch wenn dieselbe Szene herauskommt.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        current = session.last_result
        if current is not None and current is not previous and not session.busy:
            settle(app)
            return True
        time.sleep(0.02)
    return False


def until_quiet(app: QApplication, session: Any, seconds: float = 60.0) -> None:
    """Warten, bis die Sitzung nichts mehr rechnet.

    Gehört **vor** jedes Merken eines Ausgangsstands. ``start_new`` stößt
    selbst eine Auswertung an; wer unmittelbar danach ``last_result``
    festhält, hält den Stand von davor fest und vergleicht anschließend gegen
    ein Ergebnis, das gar nicht zur eigenen Änderung gehört.

    So gefunden: ein wasserdichtes Netz kam im Bericht als „0 Objekte"
    zurück, während derselbe Weg im Kern sauber ein Objekt lieferte. Nicht die
    Anwendung hat nichts geliefert — der Bericht hat zu früh hingesehen.

    Gewartet wird auf **ein Ergebnis** und nicht nur auf Ruhe: ``_reset_for``
    setzt ``last_result`` auf ``None`` und stößt die Auswertung sofort an, und
    der Arbeitsfaden meldet ``isRunning`` erst einen Wimpernschlag später. Wer
    bloß ``not busy`` abfragt, kommt genau in diesem Wimpernschlag durch — und
    der nächste Aufruf bricht die noch laufende Auswertung wieder ab, statt
    auf sie zu warten. Im Bericht standen daraufhin bei elf von fünfzehn
    Modellen null Objekte, obwohl dieselben Dateien im Kern sauber luden.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if session.last_result is not None and not session.busy:
            settle(app)
            return
        time.sleep(0.02)


def close_stray_dialogs(app: QApplication) -> int:
    """Alles wegräumen, was modal im Weg steht.

    Ein Sicherheitsnetz, kein Normalweg: die Anwendung soll hier gar nicht
    fragen, weil ``ask`` abgefangen ist. Steht trotzdem ein Fenster offen,
    hinge dieser Lauf sonst bis in alle Ewigkeit — und niemand wüsste, woran.
    """
    closed = 0
    for widget in list(app.topLevelWidgets()):
        if isinstance(widget, QDialog) and widget.isVisible():
            widget.reject()
            closed += 1
    if closed:
        settle(app)
    return closed


def silence_questions(session: Any, window: Any) -> None:
    """Rückfragen beantworten, statt sie anzuzeigen.

    Der Kern fragt über ``ctx.ask``, wenn er nicht raten darf (Regel 21) — in
    der Anwendung wird daraus ein Fenster. Hier nicht: die Verbindung dorthin
    wird gelöst und durch eine Antwort ersetzt, die immer die erste Auswahl
    nimmt. **Wichtig ist, dass die Fragen trotzdem gezählt werden**: ein
    Projekt, das beim Öffnen etwas wissen will, ist ein Befund, auch wenn er
    hier automatisch weggeklickt wird.
    """
    with contextlib.suppress(RuntimeError, TypeError):
        # Nicht verbunden — dann gibt es auch nichts zu lösen.
        session.askRequested.disconnect(window._on_ask)
    # **Mit ``window`` als Kontext, nicht als nacktes Lambda.**
    #
    # Das Signal kommt aus dem Arbeitsfaden, und der blockiert an einem
    # ``threading.Event``, bis geantwortet ist (siehe ``AskRequest``). Ohne
    # Kontextobjekt kennt Qt keine Thread-Zugehörigkeit für den Empfänger und
    # führt ihn dort aus, wo gesendet wurde — im Arbeitsfaden. Dieser
    # Empfänger fasst ``window`` an, ein Fenster; ein Zugriff darauf aus einem
    # fremden Faden beendet den Prozess ohne Ausnahme und ohne Rückverfolgung.
    #
    # Genau so gesehen: Exit 127, leeres Protokoll, und zwar beim **ersten**
    # Modell — während dieselben Modelle einzeln sauber durchliefen. Der
    # Unterschied war nicht die Datei, sondern diese Zeile.
    session.askRequested.connect(lambda request: _answer(request, window), window)


#: Die Fragen, die unterwegs aufkamen.
#:
#: Eine Liste im Modul und **kein Attribut am Fenster**: der Empfänger dieses
#: Signals hängt an einem Objekt, das der Oberfläche gehört, und was er
#: anfasst, sollte ihr nicht gehören.
ASKED: list[str] = []


def _answer(request: Any, window: Any) -> None:
    """Eine Rückfrage ohne Fenster beantworten."""
    ASKED.append(str(getattr(request, "question", request))[:80])
    options = list(getattr(request, "choices", ()) or ())
    reply = getattr(request, "reply", None)
    if callable(reply):
        reply(options[0] if options else "")


def collect(roots: tuple[str, ...], suffixes: tuple[str, ...], base: Path) -> list[Path]:
    """Alles einsammeln, was auf die Endungen passt — ohne Doppelte."""
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        directory = base / root
        if not directory.is_dir():
            continue
        for suffix in suffixes:
            for path in sorted(directory.rglob(f"*{suffix}")):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(path)
    return found


def describe(findings: list[Any]) -> list[str]:
    """Befunde auf das eindampfen, was in einen Bericht gehört."""
    lines = []
    for finding in findings:
        severity = getattr(finding, "severity", "?")
        code = getattr(finding, "code", "?")
        lines.append(f"{severity}:{code}")
    return lines


def export_round(session: Any, target: Path, name: str) -> tuple[int, list[str]]:
    """Vom ausgewerteten Stand bis zu geschriebenen Dateien.

    Der Weg, den ein Projekt am Ende wirklich nimmt: planen, prüfen,
    schreiben. Geprüft wird damit auch, was ``check_before_export`` meldet —
    nicht wasserdicht, zu nah am Rand, Lizenz der Quelle. Das sind Befunde
    über das Modell und gehören in den Bericht, nicht in die Fehlerspalte.
    """
    from app.core.export.writer import plan_export, write_plan

    result = session.last_result
    if result is None or not result.scene.objects:
        return 0, ["kein Ergebnis"]
    objects = list(result.scene.objects.values())
    plan = plan_export(
        objects,
        project_name=name,
        profile=session.profile,
        export_format="3mf",
        sources=dict(session.project.document.sources),
    )
    target.mkdir(parents=True, exist_ok=True)
    notes = describe(list(plan.findings))
    try:
        written = write_plan(plan, target, "3mf")
    except Exception as problem:
        # Das Schreiben verlangt eine Freischaltung (§2 C) — Planen und Prüfen
        # nicht. Fehlt sie, ist das ein Befund über diese Maschine und kein
        # Fehler der Anwendung; der geprüfte Plan steht trotzdem.
        return 0, [*notes, f"kein Schreiben: {type(problem).__name__}"]
    return len(written), notes


def walk_projects(app: QApplication, window: Any, session: Any, out: Path) -> list[Outcome]:
    """Jedes Projekt öffnen, auswerten, exportieren."""
    base = Path(__file__).resolve().parent.parent
    results: list[Outcome] = []
    for path in collect(PROJECT_DIRS, (".p3d",), base):
        name = path.stem
        outcome = Outcome(name=name, kind="Projekt")
        started = time.monotonic()
        try:
            before = session.last_result
            session.open_project(path)
            window._show_start_screen(False)
            if not await_result(app, session, before):
                outcome.error = f"Auswertung nicht fertig in {BUDGET:.0f} s"
            else:
                result = session.last_result
                outcome.objects = len(result.scene.objects)
                outcome.findings = describe(list(result.scene.report.findings))
                if not result.complete:
                    outcome.findings.insert(0, f"ABBRUCH@op{result.stopped_at}")
                count, extra = export_round(session, out / "projekte" / name, name)
                outcome.exported = count
                outcome.findings.extend(extra)
        except Exception as problem:
            outcome.error = f"{type(problem).__name__}: {problem}"[:160]
            traceback.print_exc(limit=3)
        outcome.seconds = time.monotonic() - started
        close_stray_dialogs(app)
        results.append(outcome)
        mark = "!!" if outcome.broke else "  "
        print(
            f"{mark} {name[:38]:40s} {outcome.seconds:6.1f} s  "
            f"{outcome.objects:2d} Objekte  {outcome.exported} Dateien  "
            f"{outcome.error or ' '.join(outcome.findings[:3])}",
            flush=True,
        )
    return results


def walk_models(
    app: QApplication,
    window: Any,
    session: Any,
    out: Path,
    first: int = 0,
    last: int = 10**6,
) -> list[Outcome]:
    """Jedes Modell einlesen, das auf dieser Maschine liegt.

    Über dieselbe Operation, die auch das Menü benutzt (``load``), und über
    eine echte Transaktion — nicht am Stapel vorbei. Ein Modell, das die
    Anwendung nicht öffnen kann, ist damit ein Befund über die Anwendung; ein
    Modell mit Löchern ist einer über das Modell.
    """
    base = Path(__file__).resolve().parent.parent
    results: list[Outcome] = []
    for index, path in enumerate(collect(MODEL_DIRS, MODEL_SUFFIXES, base)):
        if not first <= index < last:
            continue
        name = f"{index:02d} {path.name}"
        print(f"   .. {name}", flush=True)
        outcome = Outcome(name=name, kind="Modell")
        started = time.monotonic()
        try:
            session.start_new("centauri-carbon-2", "petg")
            window._show_start_screen(False)
            until_quiet(app, session)
            # Derselbe Weg wie „Modell einfügen" im Menü: er bettet die Datei
            # ein, wählt die passende Operation je Endung und zählt bei einer
            # 3MF-Baugruppe die Körper, bevor gerechnet wird. Die Einheit
            # bleibt auf „auto", damit auch die Einheitenerkennung mitläuft.
            before = session.last_result
            session.import_model(path, unit="auto")
            if not await_result(app, session, before):
                outcome.error = f"Auswertung nicht fertig in {BUDGET:.0f} s"
            else:
                result = session.last_result
                outcome.objects = len(result.scene.objects)
                outcome.findings = describe(list(result.scene.report.findings))
        except Exception as problem:
            outcome.error = f"{type(problem).__name__}: {problem}"[:160]
        outcome.seconds = time.monotonic() - started
        close_stray_dialogs(app)
        results.append(outcome)
        mark = "!!" if outcome.broke else "  "
        print(
            f"{mark} {name[:38]:40s} {outcome.seconds:6.1f} s  "
            f"{outcome.objects:2d} Objekte  "
            f"{outcome.error or ' '.join(outcome.findings[:3])}"
        )
    return results


def build_from_nothing(app: QApplication, window: Any, session: Any, out: Path) -> Outcome:
    """Der Weg eines neuen Nutzers: leere Szene bis geschriebenes Paket.

    Kein Beispielprojekt, keine geladene Datei — anlegen, formen, bohren,
    einen Baustein setzen, exportieren. Wenn dieser Weg hakt, hakt er für
    jeden beim ersten Mal.
    """
    from app.core.scene.history import OperationDraft

    outcome = Outcome(name="Neues Projekt", kind="Aufbau")
    started = time.monotonic()
    try:
        session.start_new("centauri-carbon-2", "petg")
        window._show_start_screen(False)
        until_quiet(app, session)

        steps = [
            (
                "Grundkörper",
                OperationDraft(
                    op="create_box", params={"width": 60.0, "depth": 40.0, "height": 12.0}
                ),
            ),
            (
                "Bohrung",
                OperationDraft(op="drill_hole", params={"diameter": 4.2, "x": 15.0, "y": 10.0}),
            ),
            (
                "Schraubenloch",
                OperationDraft(
                    op="insert_screw_hole", params={"size": "M4", "x": -15.0, "y": -10.0}
                ),
            ),
        ]
        for title, draft in steps:
            before = session.last_result
            session.apply(title, [draft])
            if not await_result(app, session, before):
                outcome.error = f"Schritt {title} wurde nicht fertig"
                break
        else:
            result = session.last_result
            outcome.objects = len(result.scene.objects)
            outcome.findings = describe(list(result.scene.report.findings))
            if not result.complete:
                outcome.findings.insert(0, f"ABBRUCH@op{result.stopped_at}")
            count, extra = export_round(session, out / "neu", "neues-projekt")
            outcome.exported = count
            outcome.findings.extend(extra)
    except Exception as problem:
        outcome.error = f"{type(problem).__name__}: {problem}"[:160]
        traceback.print_exc(limit=3)
    outcome.seconds = time.monotonic() - started
    close_stray_dialogs(app)
    return outcome


def report(groups: dict[str, list[Outcome]], questions: list[str]) -> int:
    """Den Bericht schreiben und sagen, ob etwas gebrochen ist."""
    print("\n" + "=" * 78)
    broken = []
    for title, entries in groups.items():
        if not entries:
            continue
        failed = [entry for entry in entries if entry.broke]
        broken.extend(failed)
        slowest = max(entries, key=lambda entry: entry.seconds)
        print(
            f"{title:12s} {len(entries):3d} Stück, {len(failed)} gestolpert, "
            f"langsamstes {slowest.name[:28]} mit {slowest.seconds:.1f} s"
        )

    kinds: dict[str, int] = {}
    for entries in groups.values():
        for entry in entries:
            for finding in entry.findings:
                kinds[finding] = kinds.get(finding, 0) + 1
    if kinds:
        print("\nBefunde nach Häufigkeit — Meldungen der Anwendung, keine Fehler:")
        for code, count in sorted(kinds.items(), key=lambda pair: -pair[1])[:15]:
            print(f"  {count:4d}x {code}")

    if questions:
        print(f"\nRückfragen ({len(questions)}) — hier automatisch beantwortet:")
        for question in questions[:10]:
            print(f"  {question}")

    if broken:
        print(f"\n{len(broken)} Stück haben die Anwendung stolpern lassen:")
        for entry in broken:
            print(f"  {entry.kind} {entry.name}: {entry.error}")
        return 1
    print("\nNichts ist gestolpert.")
    return 0


def main() -> int:
    from app.core.bootstrap import load_operations
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog
    from app.ui.app import install_qt_translations
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / "ui-audit"
    out.mkdir(parents=True, exist_ok=True)
    # Welche Gruppen dieser Lauf nimmt, und bei den Modellen welcher
    # Ausschnitt. Gebraucht, weil der Prozess den ganzen Bestand nicht am
    # Stück übersteht: er stirbt ohne Traceback und ohne Exit-Code, den man
    # deuten könnte, irgendwo zwischen dem zwanzigsten und dem
    # dreißigsten Netz. Das ist kein Grund, weniger zu prüfen — nur einer,
    # es in Portionen zu tun.
    wanted_groups = {arg for arg in sys.argv[2:] if not arg.isdigit()} or {
        "projekte",
        "modelle",
        "aufbau",
    }
    numbers = [int(arg) for arg in sys.argv[2:] if arg.isdigit()]
    window_from = numbers[0] if numbers else 0
    window_to = numbers[1] if len(numbers) > 1 else 10**6

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    apply_theme(app, "dark")
    install_catalog("de", read_catalog("de"))
    set_language("de")
    install_qt_translations(app, "de")

    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(1500, 950)
    # Sichtbar, weil der Viewport über OpenGL zeichnet und in ein nie
    # gezeigtes Fenster nichts malt — genau die Stelle, die geprüft werden
    # soll, bliebe sonst schwarz.
    window.show()
    settle(app, 40)
    silence_questions(session, window)

    groups: dict[str, list[Outcome]] = {}
    if "projekte" in wanted_groups:
        print("\n--- Projekte ---", flush=True)
        groups["Projekte"] = walk_projects(app, window, session, out)
    if "modelle" in wanted_groups:
        print(f"\n--- Modelle {window_from} bis {window_to} ---", flush=True)
        groups["Modelle"] = walk_models(app, window, session, out, window_from, window_to)
    if "aufbau" in wanted_groups:
        print("\n--- Aufbau von Null ---", flush=True)
        groups["Aufbau"] = [build_from_nothing(app, window, session, out)]

    code = report(groups, list(ASKED))
    window.close()
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    if plotter is not None:
        with contextlib.suppress(Exception):
            plotter.close()
        window.viewport.plotter = None
    print(f"\nGeschrieben nach: {out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
