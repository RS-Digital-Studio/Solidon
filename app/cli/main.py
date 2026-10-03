"""Der Kommandozeilen-Einstieg (Bauplan §10, ROADMAP P0).

Die Befehle stehen hier nicht ausgeschrieben: sie kommen aus dem
Operationsregister — derselben Quelle, aus der Menü, Palette und
Agenten-Werkzeugschema kommen. Eine Operation, die es gibt, ist von der
Kommandozeile aus erreichbar, sobald sie deklariert ist.

``ask`` wird eine nummerierte Frage im Terminal, ``progress`` eine einzelne
Zeile, die sich selbst überschreibt — derselbe Vertrag, den die Oberfläche mit
einem Dialog und einer Statusleiste umsetzt.
"""

from __future__ import annotations

from app.core.log import install_crash_logging

if __name__ == "__main__":
    install_crash_logging()

# isort: split

import argparse
import difflib
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.branding import (
    APP_NAME,
    APP_VERSION,
    DISTRIBUTION_NAME,
    PLANNED_SALE_START,
    PROJECT_SUFFIX,
    SUPPORT_ADDRESS,
    WEBSITE_URL,
)
from app.core import activation, manual
from app.core.bootstrap import load_operations, load_user_parts
from app.core.errors import CANCEL, AppError, OperationCancelled, UserError, ValidationError
from app.core.export.writer import FORMAT_SUFFIX, plan_export, write_plan
from app.core.ingest.archive import is_archive, model_from_archive
from app.core.ingest.loader import (
    detect_unit,
    plausible_reach,
    read_local_payload,
    read_model,
)
from app.core.ingest.plan import import_plan, names_in_use
from app.core.knowledge import profiles
from app.core.log import configure
from app.core.paths import installed_language, user_config_dir
from app.core.perceive.local import forget_out_of_memory
from app.core.registry import REGISTRY, cli_commands, documentation
from app.core.registry.params import LIST_KINDS, NUMBER_KINDS, TEXT_KINDS
from app.core.scene import History, OperationDraft, ResultCache, disk_backed_cache, evaluate
from app.core.scene.history import RevisionPlan, recognition_reopenable
from app.core.scene.project import (
    Project,
    ProjectSources,
    embedded_source_path,
    load,
    new_project,
    next_source_id,
    save,
)
from app.core.scene.revision import commit as commit_revision
from app.core.scene.revision import dependencies as revision_dependencies
from app.core.scene.revision import revise
from app.core.types import Source
from app.core.units import format_length
from app.i18n import _, set_language, tr
from app.i18n.catalog import install_language

#: Wie die Kommandozeile den Text eines Arguments in einen Wert wandelt.
#:
#: **Abgeleitet und nicht aufgezählt**, denn eine zweite Liste altert. Hier
#: stand einmal ``{"float", "int", "str", "enum"}`` von Hand — und als
#: ``slot`` die Art ``filament`` bekam, fiel sie durch das ``.get(..., str)``
#: in den Textzweig: ``--slot 1`` kam als ``"1"`` an, und die Prüfung lehnte
#: mit „Hier wird eine Zahl erwartet" ab. ``assign_slot`` war über die
#: Kommandozeile damit gar nicht zu benutzen (Befund Robert, 08.09.2026).
#:
#: Es ist derselbe Fehler wie am 27.08.2026, eine Ebene weiter: Damals wurde
#: ``NUMBER_KINDS`` in :mod:`app.core.registry.params` ergänzt, diese Tabelle
#: aber nicht. Zwei Listen für eine Frage sind zwei Gelegenheiten,
#: auseinanderzulaufen; jetzt gibt es nur noch die eine.
_PARAM_TYPES: dict[str, Any] = {
    kind: (float if kind == "float" else int) for kind in NUMBER_KINDS
} | dict.fromkeys(TEXT_KINDS | LIST_KINDS, str)


# --- context implementations ----------------------------------------------------


class TerminalProgress:
    """Eine Zeile, die sich selbst überschreibt, und unter 0,2 s gar
    nichts (§2.8).

    Kurze Läufe bleiben still: ein Aufblitzen von Fortschritt für etwas, das
    eine Zehntelsekunde gedauert hat, ist Rauschen, keine Rückmeldung.
    """

    def __init__(self, delay: float = 0.2) -> None:
        self.delay = delay
        self.started: float | None = None
        self.shown = False

    def __call__(self, fraction: float, text: str) -> None:
        now = time.monotonic()
        if self.started is None:
            self.started = now
        if not text:
            if self.shown:
                sys.stderr.write("\r" + " " * 60 + "\r")
                sys.stderr.flush()
                self.shown = False
            self.started = None
            return
        if now - self.started < self.delay:
            return
        sys.stderr.write(f"\r{fraction * 100:3.0f}%  {text[:50]:<50}")
        sys.stderr.flush()
        self.shown = True


def terminal_ask(question: str, choices: list[str]) -> str:
    """Mehrdeutigkeit wird eine nummerierte Frage — nie eine
    Vermutung (Leitprinzip 6).

    Niemand am anderen Ende ist kein Sonderfall: in einer Pipe, einem Skript
    oder auf einem Bauserver liest ``input`` sofort EOF. Ungefangen endete das
    in einem Stapelabzug — die eine Sorte Ausgabe, die §33.1 dem Nutzer
    ausdrücklich erspart, und ausgerechnet für eine Frage, die sich auf der
    Kommandozeile beantworten lässt.
    """
    print(f"\n{question}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}) {choice}")
    while True:
        try:
            answer = input(tr("Auswahl [1-{count}]: ", count=len(choices))).strip()
        except EOFError as end:
            raise UserError(
                title=_("Diese Frage braucht eine Antwort, und hier ist niemand."),
                detail=_(
                    "Der Lauf hat keine Eingabe. Die Antwort lässt sich beim Einlesen "
                    "vorab mitgeben — die Einheit über „--unit“, das Modell aus einem "
                    "ZIP über „--entry“."
                ),
                values={"question": question, "choices": ", ".join(choices)},
                suggestions=(CANCEL,),
            ) from end
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        if answer in choices:
            return answer


# --- helpers --------------------------------------------------------------------


def open_project(path: Path) -> Project:
    project = load(path)
    # Eigene Drucker und Materialien, die das Projekt mitbringt, gelten hier
    # wie im Fenster (``profiles.carry``).
    profiles.carry(project.document.carried_profiles)
    return project


def profile_of(project: Project) -> Any:
    return profiles.scene_profile(
        project.document.printer or profiles.DEFAULT_PRINTER,
        project.document.material or profiles.DEFAULT_MATERIAL,
    )


_cache: ResultCache | None = None


def evaluation_cache() -> ResultCache:
    """Der Cache dieses Aufrufs, einmal gebaut.

    Die Kommandozeile übergab bis hierher **keinen** Cache, und das war die
    Stelle, an der es am meisten kostete: Jeder Aufruf ist ein eigener Prozess,
    also gibt es keinen Speicher, der über ihn hinaus hilft. Wer dieselbe Datei
    prüft, exportiert und noch einmal exportiert, rechnete den Stapel dreimal.
    Mit der Plattenebene rechnet ihn der erste Aufruf und die folgenden lesen
    ihn — genau der Fall, für den §38 die Ebene vorsieht.

    Einmal je Prozess, weil ein Befehl mehrfach auswerten kann (``export``
    zweimal): Zwei Bauer hießen zwei Ordnerprüfungen und zwei Speicherebenen,
    die einander nichts nützen.
    """
    global _cache
    if _cache is None:
        _cache = disk_backed_cache()
    return _cache


def run_evaluation(project: Project, path: Path, quiet: bool = False) -> Any:
    """Wertet aus und behält die Antworten für die übrigen Läufe des Befehls.

    ``export`` wertet zweimal aus, die Verlaufsbefehle dreimal; ohne das kam
    jede Frage — auch die vor der langen Vollerkennung eines großen Modells —
    je Befehl zwei- bis dreimal. Festgehalten wird wie im Fenster am Stapel;
    in die Datei gelangen die Antworten nur, wenn der Befehl sie speichert.
    """
    result = evaluate(
        project.document,
        profile_of(project),
        progress=(lambda fraction, text: None) if quiet else TerminalProgress(),
        ask=terminal_ask,
        sources=ProjectSources(project, base_dir=path.parent),
        cache=evaluation_cache(),
    )
    history = History(project.document)
    # Auch die Antworten der Operationen, wie im Fenster (``Session``): Eine
    # freie Stelle wird einmal gesucht und steht danach im Schritt (§17.1).
    history.record_answers(result.answers)
    if result.matches:
        history.record_matches(result.matches)
    return result


def print_findings(findings: Any) -> None:
    # Gleiche Sätze einmal, mit ihrer Zahl davor — wie im Prüfbericht
    # (``panels._bundled``). Der Export meldet eine Einstellung je Teil, und
    # zwölf Behälter auf zu kleiner Fläche ergäben sonst zwölf gleiche Zeilen.
    counted: dict[tuple[str, str], int] = {}
    for finding in findings:
        key = (finding.severity, str(finding.message))
        counted[key] = counted.get(key, 0) + 1
    for (severity, message), count in counted.items():
        # Nie Farbe allein (§19.1) — im Terminal trägt das Zeichen die Bedeutung.
        marker = {"info": "-", "warning": "!", "error": "X"}[severity]
        print(f"  {marker} {f'({count}) ' if count > 1 else ''}{message}")


def print_report(result: Any) -> None:
    print_findings(result.scene.report.findings)
    if result.stopped_at is not None:
        print(tr("Die Kette hält bei Operation {op} an.").replace("{op}", str(result.stopped_at)))


# --- commands -------------------------------------------------------------------


def command_ops(args: argparse.Namespace) -> int:
    for spec in REGISTRY.all():
        shortcut = f"  [{spec.shortcut}]" if spec.shortcut else ""
        print(f"{spec.name:<20} {spec.title}{shortcut}")
        print(f"{'':<20} {spec.doc}")
    return 0


def command_docs(args: argparse.Namespace) -> int:
    """Die Referenz, mit ``--manual`` das ganze Handbuch.

    Derselbe Text, den das Fenster zeigt: eine zweite Version wäre eine, die
    irgendwann etwas anderes sagt.
    """
    print(manual.as_markdown() if getattr(args, "manual", False) else documentation(), end="")
    return 0


def command_profiles(args: argparse.Namespace) -> int:
    print(tr("Drucker"))
    for identifier, printer in sorted(profiles.printer_profiles().items()):
        width, depth, height = printer.build_volume
        print(f"  {identifier:<24} {printer.title:<28} {width:.0f} x {depth:.0f} x {height:.0f} mm")
    print(tr("Material"))
    for identifier, material in sorted(profiles.material_profiles().items()):
        state = (
            tr("kalibriert") if material.calibrated else tr("Startwert", context="Kalibrierstand")
        )
        print(f"  {identifier:<24} {material.title:<28} {state}")
    return 0


def command_scad(args: argparse.Namespace) -> int:
    """Einen Baustein als OpenSCAD-Quelltext ausgeben (§24.1).

    **Geschrieben, nicht ausgeführt.** ``to_scad`` erzeugt eine Datei und ruft
    nichts auf; seit dem Ausbau von OpenSCAD (26.08.2026) gibt es dorthin auch
    keinen Weg mehr, und Regel 11 steht als Sperre. Wer einen baut, baut die
    Prüfung mit.

    Ohne ``--set`` stehen die Vorgaben des Bausteins darin, mit ``--set`` die
    genannten Werte — dieselbe Prüfung wie im Dialog, also mit Grenzen und
    Meldung statt einer stillen Übernahme.
    """
    from app.core.export.writer import export_part_scad
    from app.core.knowledge.parts import PARTS
    from app.core.registry import validate

    load_user_parts()
    known = set(PARTS.versions())
    if args.part not in known:
        raise UserError(
            detail=tr("Diesen Baustein gibt es nicht: {name}").format(name=args.part),
            suggestions=(CANCEL,),
            values={"known": ", ".join(sorted(known))},
        )
    spec = PARTS.get(args.part)
    kinds = {parameter.name: parameter.kind for parameter in spec.params.spec()}
    given: dict[str, Any] = {}
    for entry in args.set or ():
        name, _separator, raw = entry.partition("=")
        if not name or not raw:
            raise UserError(
                detail=tr("Schreiben Sie die Werte als Name=Wert, zum Beispiel length=30."),
                suggestions=(CANCEL,),
                values={"given": entry},
            )
        given[name.strip()] = _as_value(raw.strip(), boolean=kinds.get(name.strip()) == "bool")
    values = validate(spec.params, given) if given else spec.params()
    text = export_part_scad(spec, values)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(tr("Geschrieben: {path}").format(path=args.out))
    else:
        print(text, end="")
    return 0


def _as_value(raw: str, *, boolean: bool = False) -> Any:
    """Zahl, Wahrheitswert oder Text — geraten wird nur die **Schreibweise**.

    Ob der Wert zum Parameter passt, entscheidet danach ``validate`` gegen das
    Schema; hier steht nur, dass „30" die Zahl 30 meint und nicht die
    Zeichenkette. Ein Wert, den das Schema als Text erwartet, kommt als Text
    an, weil er sich nicht als Zahl lesen lässt.
    """
    if raw.lower() in {"ja", "true", "wahr"}:
        return True
    if raw.lower() in {"nein", "false", "falsch"}:
        return False
    if boolean:
        if raw in {"0", "1"}:
            return raw == "1"
        raise UserError(
            detail=tr("Für Wahrheitswerte verwenden Sie true oder false (alternativ 1 oder 0)."),
            suggestions=(CANCEL,),
            values={"given": raw},
        )
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def command_new(args: argparse.Namespace) -> int:
    # Geprüft wird hier, nicht erst beim Rechnen. Ohne das nimmt „new" jeden
    # Namen an und legt eine Datei an, die beim nächsten Befehl mit „Dieses
    # Materialprofil ist nicht bekannt" stehen bleibt — eine Fehlermeldung
    # über einen Tippfehler, der zwei Befehle zurückliegt. Die Falle ist
    # zudem eingebaut: „profiles" zeigt den Titel PETG, die Kennung ist petg.
    _known("Material", args.material, profiles.material_profiles())
    _known("Drucker", args.printer, profiles.printer_profiles())
    project = new_project(printer=args.printer, material=args.material)
    path = save(project, Path(args.path))
    print(tr("Neues Projekt: {path}", path=path))
    return 0


def _known(what: str, chosen: str, known: Mapping[str, Any]) -> None:
    """Hält an, wenn es das Profil nicht gibt — und nennt die, die es gibt."""
    if not chosen or chosen in known:
        return
    near = [name for name in known if name.lower() == chosen.lower()]
    raise ValidationError(
        title=_("Dieses Profil gibt es nicht."),
        detail=(
            _("Profilkennungen werden kleingeschrieben — der Titel daneben nicht.")
            if near
            else _("„profiles“ zeigt, was zur Auswahl steht.")
        ),
        values={what.lower(): chosen, "gemeint": near[0] if near else ", ".join(sorted(known))},
    )


def command_info(args: argparse.Namespace) -> int:
    path = Path(args.path)
    project = open_project(path)
    document = project.document
    result = run_evaluation(project, path, quiet=True)

    print(tr("Projekt: {name}", name=path.name))
    print(
        tr("Drucker: {value}", value=document.printer or "-")
        + "   "
        + tr("Material: {value}", value=document.material or "-")
        + "   "
        + tr("Format: {version}", version=document.format_version)
    )
    if document.parameters:
        print(tr("Parameter"))
        for name, parameter in document.parameters.items():
            source = f"  = {parameter.expression}" if parameter.expression else ""
            print(f"  {name:<16} {format_length(parameter.value, 'mm')}{source}")
    print(tr("Objekte"))
    for object_id, entry in result.scene.objects.items():
        size = entry.mesh.bounds.size
        watertight = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
        print(
            # !s wie beim Titel darunter: ein übersetzbarer Name kennt
            # keine Formatbreite.
            f"  {object_id:<8} {entry.name!s:<24} "
            f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm   "
            f"{entry.mesh.triangle_count} {tr('Dreiecke', context='Anzahl')}, {watertight}"
        )
    print(tr("Verlauf"))
    for transaction in document.transactions:
        ops = ", ".join(str(entry) for entry in transaction.ops)
        # !s zuerst: ein übersetzbarer Titel kennt keine Formatbreite.
        print(f"  {transaction.id:<5} {transaction.title!s:<28} ({tr('Ops')} {ops})")
    resting = [entry for entry in document.ops if entry.suppressed is not None]
    if resting:
        # Was nicht rechnet, steht dabei (P7.3) — ohne das sähe das Teil aus,
        # als fehle ihm grundlos ein Schritt.
        print(tr("Ausgeschaltet"))
        for entry in resting:
            state = tr("aus") if entry.suppressed and entry.suppressed.chosen else tr("ruht")
            print(f"  {entry.id:<5} {entry.op:<28} ({state})")
    print_report(result)
    return 0 if result.complete else 1


def command_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    incoming = Path(args.file)
    project = open_project(path)

    if not incoming.is_file():
        print(tr("Die Datei gibt es nicht: {path}", path=incoming), file=sys.stderr)
        return 1

    payload = read_local_payload(incoming)
    name = incoming.name
    if is_archive(name):
        # Wie im Fenster: eingebettet wird das Modell im ZIP, nicht das
        # Archiv — und bei mehreren fragt das Terminal (Regel 21).
        # ``--entry`` ist dieselbe Antwort vorab, für Skripte ohne Terminal;
        # ein Name, der nicht im Archiv liegt, wird abgewiesen wie eine
        # falsche Antwort im Terminal.
        entry = args.entry
        ask = terminal_ask if entry is None else (lambda question, choices: entry)
        name, payload = model_from_archive(name, payload, ask)

    source_id = next_source_id(project.document.sources)
    project.document.sources[source_id] = Source(
        id=source_id,
        kind="import",
        path=embedded_source_path(name, source_id),
        sha256="",
    )
    project.sources[source_id] = payload

    # **Wie im Fenster, aus derselben Quelle.** Hier stand immer ``load``, und
    # damit konnte die Kommandozeile STEP, SVG und DXF nicht — Formate, die
    # dieselbe Anwendung im Fenster einliest. Geantwortet hat sie „Dieses
    # Dateiformat kann nicht gelesen werden.", also eine Unwahrheit.
    #
    # Die Einheitenfrage kommt erst nach dem Plan: nur ein Netz hat sie. STEP
    # trägt seine Einheit selbst, eine flache Zeichnung hat keine dritte
    # Dimension — dort wäre die Frage eine Zumutung ohne Zweck.
    # Das erste Modell eines Projekts kommt mittig auf die Platte, jedes weitere
    # an die freie Stelle nächst der Plattenmitte (§17.1, Schritt 6). Gefragt wird der Stapel und
    # nicht die Szene: Er steht fest, bevor irgendetwas ausgewertet ist, und die
    # Operation trägt die Entscheidung danach selbst.
    first_model = not project.document.ops
    # Und derselbe freie Name wie im Fenster: Zweimal dieselbe Datei ergibt
    # zwei Körper, die sich im Baum auseinanderhalten lassen.
    taken = names_in_use(project.document)
    plan = import_plan(source_id, name, payload, args.unit, first_model=first_model, taken=taken)
    if plan.asks_unit:
        plan = import_plan(
            source_id,
            name,
            payload,
            _chosen_unit(
                payload,
                name,
                args.unit,
                plausible_reach(profile_of(project).printer.build_volume),
            ),
            first_model=first_model,
            taken=taken,
        )
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(tr("Geladen: {name}", name=name))
    return 0


def _chosen_unit(payload: bytes, name: str, requested: str, reach: float) -> str:
    """Fragt, bevor die Operation geschrieben wird, damit die Antwort mit ihr
    gespeichert wird (§17.1).

    ``reach`` aus dem Drucker des Projekts, wie in der Operation
    (:func:`plausible_reach`). Ohne ihn nahm die Kommandozeile einen Helm in
    Metern still als Zoll, wo Fenster und Operation fragen (RM-420).
    """
    from app.core.ingest.ops import unit_question

    if requested != "auto":
        return requested
    bounds = read_model(payload, Path(name).suffix).bounds
    guess = detect_unit(bounds.diagonal, reach)
    if guess.unit is not None:
        return guess.unit
    # Dieselbe Frage wie im Fenster, mit der Größe je Antwort (§17.1).
    return terminal_ask(
        unit_question(bounds.size, guess.candidates),
        [str(candidate) for candidate in guess.candidates],
    )


def _revised(
    project: Project,
    path: Path,
    planned: Any,
) -> int:
    """Einen Umbau des Verlaufs rechnen und nur ein gültiges Ergebnis speichern (P7).

    Derselbe Weg wie im Fenster: Grundstand rechnen, planen, den Vorschlag
    isoliert auswerten (``scene.revision.revise``), dann übernehmen. Eine
    Absage kommt als ``AppError`` bis ins Hauptprogramm, und die Datei auf der
    Platte bleibt, wie sie war — ein ungültiger Vorschlag ändert nichts.
    """
    history = History(project.document)
    baseline = run_evaluation(project, path, quiet=True)
    context = revision_dependencies(project.document, baseline)
    plan: RevisionPlan = planned(history, context)

    def run(document: Any) -> Any:
        return evaluate(
            document,
            profile_of(project),
            progress=TerminalProgress(),
            ask=terminal_ask,
            sources=ProjectSources(project, base_dir=path.parent),
            cache=evaluation_cache(),
        )

    revision = revise(
        history, plan, evaluate=run, baseline=baseline, context=context, ask=terminal_ask
    )
    transaction = commit_revision(history, revision)
    print_findings(revision.findings)
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(tr("Übernommen: {title}", title=transaction.title))
    return 0


def command_move(args: argparse.Namespace) -> int:
    """Schritte an eine andere Stelle des Verlaufs (P7.2)."""
    path = Path(args.path)
    project = open_project(path)
    before = None if args.end else args.before
    return _revised(
        project,
        path,
        lambda history, context: history.plan_move(args.steps, before, context),
    )


def command_suppress(args: argparse.Namespace) -> int:
    """Schritte ausschalten, samt dem, was ohne sie nicht rechnet (P7.3)."""
    path = Path(args.path)
    project = open_project(path)
    return _revised(
        project, path, lambda history, context: history.plan_suppress(args.steps, context)
    )


def command_reactivate(args: argparse.Namespace) -> int:
    """Ausgeschaltete Schritte wieder einschalten (P7.3)."""
    path = Path(args.path)
    project = open_project(path)
    return _revised(
        project, path, lambda history, context: history.plan_reactivate(args.steps, context)
    )


def command_run(args: argparse.Namespace) -> int:
    path = Path(args.path)
    project = open_project(path)
    spec = REGISTRY.get(args.op)

    params = {
        entry.name: getattr(args, entry.name)
        for entry in spec.params.spec()
        if getattr(args, entry.name, None) is not None
    }
    inputs = tuple(args.on or ())
    if spec.takes_whole_scene and not inputs:
        # Anordnen und die Kollisionsprüfung arbeiten auf der ganzen Szene (§25);
        # ohne ``--on`` liefen sie sonst auf nichts.
        inputs = tuple(run_evaluation(project, path, quiet=True).scene.objects)

    draft = OperationDraft(op=spec.name, inputs=inputs, params=params, seed=args.seed)
    if args.before is not None:
        # Vor einen Schritt statt ans Ende (P7.1): geplant, isoliert gerechnet,
        # und nur ein gültiger Vorschlag landet in der Datei.
        return _revised(
            project,
            path,
            lambda history, _context: history.plan_insert(args.before, spec.title, [draft]),
        )
    history = History(project.document)
    history.apply(spec.title, [draft])
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(tr("Ausgeführt: {operation}", operation=spec.name))
    return 0


def command_recognize(args: argparse.Namespace) -> int:
    """*Alle Merkmale erkennen* auf der Kommandozeile (§21.1).

    Der Befund nennt den Knopf aus dem Fenster, und das Terminal hatte kein
    Gegenstück: Eine gespeicherte Absage ließ sich dort nicht zurücknehmen
    (Review B10, 25.09.2026). Die Auswertung danach fragt wieder. Wer nicht
    antworten kann, lädt wie beim Import ohne Vollerkennung und hält nichts
    fest; die nächste Frage kommt dann im Fenster.

    **Genannte Körper bekommen die Auskunft des Fensters** (Review R7): jede
    Wahl am Ladeschritt, auch eine Zustimmung, deren Erkennung später am
    Arbeitsspeicher scheiterte — der Befund sagt dort „„Alle Merkmale
    erkennen“ versucht es erneut“, und der Befehl antwortete, es sei nichts
    ausgelassen. Ohne Angabe nimmt er nur die Absagen: Eine gelungene
    Erkennung neu zu erfragen wäre eine Frage ohne Anlass.
    """
    path = Path(args.path)
    project = open_project(path)
    document = project.document
    loaded = sorted(
        {object_id for entry in document.ops if entry.op == "load" for object_id in entry.outputs}
    )
    # Eine unbekannte Kennung geht nicht still unter, wie beim Export
    # (Review S6).
    known = sorted({object_id for entry in document.ops for object_id in entry.outputs})
    unknown = [object_id for object_id in args.on or () if object_id not in known]
    if unknown:
        raise ValidationError(
            field="on",
            detail=tr("Dieses Objekt gibt es in der Szene nicht."),
            constraint="unknown_object",
            values={"requested": ", ".join(unknown), "known": ", ".join(known)},
        )
    wanted = args.on or loaded
    chosen = [
        object_id
        for object_id in wanted
        if recognition_reopenable(document, object_id, declined_only=not args.on)
    ]
    if not chosen:
        standing = [
            object_id for object_id in loaded if recognition_reopenable(document, object_id)
        ]
        if args.on:
            print(
                tr("Für diese Objekte gibt es keine gespeicherte Wahl zur Merkmalserkennung."),
                file=sys.stderr,
            )
            if standing:
                print(
                    tr("Gemeint war vielleicht: {names}", names=", ".join(standing)),
                    file=sys.stderr,
                )
        else:
            print(
                tr("Für diese Objekte wurde keine Merkmalserkennung ausgelassen."), file=sys.stderr
            )
            if standing:
                print(
                    "  - "
                    + tr(
                        "Neu entscheiden: {command}",
                        command=(
                            f"{DISTRIBUTION_NAME} recognize {args.path} --on {' '.join(standing)}"
                        ),
                    ),
                    file=sys.stderr,
                )
        return 1
    History(document).reopen_recognition(chosen)
    forget_out_of_memory()
    result = run_evaluation(project, path)
    save(project, path)
    print_report(result)
    return 0 if result.complete else 1


def command_undo(args: argparse.Namespace) -> int:
    path = Path(args.path)
    project = open_project(path)
    history = History(project.document)
    transaction = history.undo()
    if transaction is None:
        print(tr("Es gibt nichts zurückzunehmen."))
        return 1
    save(project, path)
    print(tr("Zurückgenommen: {title}", title=transaction.title))
    return 0


def command_export(args: argparse.Namespace) -> int:
    """Schreibt die Szene als druckbare Dateien heraus (§29).

    Die Kommandozeile konnte ein Modell laden, reparieren und beschreiben — und
    hatte dann keinen Weg, das Ergebnis zurückzugeben: den Writer gab es, und
    nichts erreichte ihn. Eine Reparatur, die das Projekt nicht verlassen kann,
    ist eine Reparatur, die niemand drucken kann.
    """
    path = Path(args.path)
    project = open_project(path)
    result = run_evaluation(project, path, quiet=True)

    # **Eine angehaltene Kette wird nicht exportiert.** Hier stand nur die
    # Auswertung, und ihr Ergebnis wurde ungeprüft geschrieben: Hält die Kette
    # bei der dritten von sieben Operationen an, enthält die Szene den Stand
    # davor — der Export schrieb ihn, meldete „Geschrieben: …" und gab 0
    # zurück. Eine halbe Datei mit ganzem Namen ist schlimmer als keine, denn
    # sie wird gedruckt. ``command_info`` sagte den Halt seit je; nur der
    # Befehl, der etwas herausgibt, sah nicht hin.
    if not result.complete:
        print_report(result)
        print(
            tr(
                "Nichts geschrieben — die Kette hält an. Der Grund steht oben; "
                "nach der Behebung schreibt derselbe Aufruf die Dateien."
            ),
            file=sys.stderr,
        )
        return 1

    wanted = list(args.on or result.scene.objects)
    unknown = [entry for entry in wanted if entry not in result.scene.objects]
    if unknown:
        raise ValidationError(
            field="on",
            detail=tr("Dieses Objekt gibt es in der Szene nicht."),
            constraint="unknown_object",
            values={"requested": ", ".join(unknown), "known": ", ".join(result.scene.objects)},
        )

    plan = plan_export(
        [result.scene.objects[entry] for entry in wanted],
        project_name=path.stem,
        profile=profile_of(project),
        export_format=args.export_format,
        scheme=args.scheme,
        sources=project.document.sources,
        # Zwei der fünf Fragen aus §29 stehen nicht im einzelnen Körper: eine
        # verletzte Passung und eine Wand unter der Mindeststärke. Beide
        # brauchen die Szene, aus der die Körper kommen (RM-140).
        scene=result.scene,
        document=project.document,
        # Was die Auswertung schon fand und der Export weitersagt (RM-419).
        evaluated=result.scene.report.findings,
    )
    # Die Prüfung spricht, bevor die Dateien existieren — eine Warnung ist
    # also eine Warnung über das, was geschrieben wird, nicht über das, was
    # geschrieben wurde (§29).
    print_findings(plan.findings)

    written = write_plan(plan, Path(args.directory), args.export_format)
    for target in written:
        print(tr("Geschrieben: {path}", path=target))
    return 0


# --- argument parsing -----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=DISTRIBUTION_NAME,
        description=f"{APP_NAME} {APP_VERSION}",
    )
    parser.add_argument("--debug", action="store_true", help=tr("Ausführliches Protokoll"))
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("ops", help=tr("Alle Operationen auflisten"))
    listing.set_defaults(handler=command_ops)

    docs = commands.add_parser("docs", help=tr("Erzeugte Referenz ausgeben"))
    docs.add_argument(
        "--manual",
        action="store_true",
        help=tr("Das ganze Handbuch, nicht nur die Referenz"),
    )
    docs.set_defaults(handler=command_docs)

    profile_list = commands.add_parser("profiles", help=tr("Drucker- und Materialprofile"))
    profile_list.set_defaults(handler=command_profiles)

    scad = commands.add_parser("scad", help=tr("Baustein als OpenSCAD-Quelltext schreiben"))
    scad.add_argument("part", metavar="<baustein>", help=tr("Name des Bausteins"))
    scad.add_argument(
        "--set",
        action="append",
        metavar="NAME=WERT",
        help=tr(
            "Einen Parameterwert setzen, mehrfach möglich; Wahrheitswerte: true/false oder 1/0"
        ),
    )
    scad.add_argument("--out", help=tr("Zieldatei statt der Ausgabe"))
    scad.set_defaults(handler=command_scad)

    create = commands.add_parser("new", help=tr("Neues Projekt anlegen"))
    create.add_argument("path", help=f"{tr('Zieldatei')} ({PROJECT_SUFFIX})")
    create.add_argument("--printer", default=profiles.DEFAULT_PRINTER)
    create.add_argument("--material", default=profiles.DEFAULT_MATERIAL)
    create.set_defaults(handler=command_new)

    info = commands.add_parser("info", help=tr("Projekt auswerten und beschreiben"))
    info.add_argument("path")
    info.set_defaults(handler=command_info)

    importing = commands.add_parser("import", help=tr("Modelldatei einbetten und laden"))
    importing.add_argument("path")
    importing.add_argument("file")
    importing.add_argument("--unit", default="auto", choices=("auto", "mm", "cm", "in", "m"))
    importing.add_argument(
        "--entry", default=None, help=tr("Welches Modell aus einem ZIP-Archiv, Name wie darin")
    )
    importing.set_defaults(handler=command_import)

    recognize = commands.add_parser("recognize", help=tr("Alle Merkmale erkennen"))
    recognize.add_argument("path")
    recognize.add_argument("--on", nargs="*", default=None, help=tr("Objekte, z. B. obj_1"))
    recognize.set_defaults(handler=command_recognize)

    undo = commands.add_parser("undo", help=tr("Letzte Transaktion zurücknehmen"))
    undo.add_argument("path")
    undo.set_defaults(handler=command_undo)

    # Der Verlauf selbst (P7): verschieben, aus- und einschalten. Einfügen
    # geht über ``run … --before``, denn eingefügt wird eine Operation.
    move = commands.add_parser("move", help=tr("Schritte im Verlauf verschieben"))
    move.add_argument("path")
    move.add_argument("steps", type=int, nargs="+", help=tr("Schrittnummern, z. B. 4 5"))
    where = move.add_mutually_exclusive_group(required=True)
    where.add_argument("--before", type=int, help=tr("Vor diesen Schritt"))
    where.add_argument("--end", action="store_true", help=tr("Ans Ende des Verlaufs"))
    move.set_defaults(handler=command_move)

    suppress = commands.add_parser("suppress", help=tr("Schritte ausschalten"))
    suppress.add_argument("path")
    suppress.add_argument("steps", type=int, nargs="+", help=tr("Schrittnummern, z. B. 4 5"))
    suppress.set_defaults(handler=command_suppress)

    reactivate = commands.add_parser("reactivate", help=tr("Schritte wieder einschalten"))
    reactivate.add_argument("path")
    reactivate.add_argument("steps", type=int, nargs="+", help=tr("Schrittnummern, z. B. 4 5"))
    reactivate.set_defaults(handler=command_reactivate)

    export = commands.add_parser("export", help=tr("Objekte als Druckdatei schreiben"))
    export.add_argument("path")
    export.add_argument("directory", nargs="?", default=".")
    export.add_argument(
        "--format",
        dest="export_format",
        default="stl",
        # Aus dem Schreiber, nicht aus einer zweiten Liste: ein Format, das
        # er kann und die Kommandozeile nicht anbietet, gibt es sonst so
        # lange, bis jemand es vermisst.
        choices=tuple(FORMAT_SUFFIX),
    )
    export.add_argument("--on", nargs="*", default=None, help=tr("Objekte, z. B. obj_1"))
    export.add_argument("--scheme", default=None, help=tr("Namensschema für die Dateinamen"))
    export.set_defaults(handler=command_export)

    run = commands.add_parser("run", help=tr("Eine Operation ausführen"))
    # ``metavar`` gegen die Wand: ohne es schreibt argparse alle
    # vierundachtzig Operationsnamen in die Nutzungszeile — und bei einem
    # Tippfehler ein zweites Mal in die Fehlermeldung. Wer wissen will, welche
    # es gibt, fragt ``solidon3d ops``; das steht im Hinweis unten.
    run_commands = run.add_subparsers(dest="op", required=True, metavar="<operation>")
    for command in cli_commands():
        entry = run_commands.add_parser(command.name, help=command.help)
        entry.add_argument("path")
        entry.add_argument("--on", nargs="*", help=tr("Eingangsobjekte, z. B. obj_1"))
        entry.add_argument("--seed", type=int, default=None)
        entry.add_argument(
            "--before",
            type=int,
            default=None,
            help=tr("Vor diesem Schritt einfügen statt ans Ende"),
        )
        for argument in command.arguments:
            if argument.kind == "bool":
                # Beide Zustände, nicht nur der wahre: ``--compensate`` und
                # ``--no-compensate``. Mit ``store_true`` gab es für eine
                # standardmäßig wahre Vorgabe — ``compensate`` beim Bohren,
                # ``fill_holes`` beim Reparieren — keinen Aufruf, der sie
                # abschaltet; der Nennmaßweg war über die Kommandozeile nicht
                # erreichbar (Gesamtreview 05.09.2026, CORE-20). ``None``
                # bleibt „nicht gesagt", und das Schema entscheidet dann.
                entry.add_argument(
                    argument.flag,
                    dest=argument.name,
                    action=argparse.BooleanOptionalAction,
                    default=None,
                    help=argument.help,
                )
                continue
            entry.add_argument(
                argument.flag,
                dest=argument.name,
                type=_PARAM_TYPES.get(argument.kind, str),
                nargs="+" if argument.kind in LIST_KINDS else None,
                choices=list(argument.choices) or None,
                help=argument.help,
                default=None,
            )
        entry.set_defaults(handler=command_run)

    return parser


def _speak_utf8() -> None:
    """Lässt die Konsole jeden Namen annehmen, den eine Datei haben kann.

    Eine Windows-Konsole kodiert nach cp1252, und ``print`` auf einem Namen
    außerhalb davon wirft, statt etwas zu schreiben. Das ist kein Randfall: das
    erste echte Modell, das dieser Kommandozeile übergeben wurde, hieß
    ``埃菲尔铁塔18cm.stl``, der Import lief durch, und der Lauf endete in einem
    Encoding-Traceback auf der Zeile, die den Erfolg meldet. Deutsche Umlaute
    überleben cp1252 — darum ist es hier eine ganze Phase lang niemandem
    aufgefallen.

    ``backslashreplace`` statt schlichtem UTF-8: eine Konsole, die die Zeichen
    nicht darstellen kann, druckt dann ihre Escapes, statt zu scheitern, und
    der Name bleibt so oder so wiedererkennbar.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _demo_is_over() -> bool:
    """Sagt und protokolliert, dass diese Demo abgelaufen ist.

    Die Kommandozeile bekommt dieselbe Grenze wie das Fenster (Demo-Konzept
    §2 B2) — ohne sie wäre sie der offene Weg an einem Ende vorbei, das für
    die Oberfläche gilt.

    Die Sätze stehen hier noch einmal und nicht in einer gemeinsamen Funktion:
    die des Fensters wohnen in ``app.ui.dialogs``, und die Kommandozeile darf
    nichts aus ``app.ui`` importieren — sie läuft auf Rechnern ohne Qt. Gleich
    sind die drei Aussagen: was abgelaufen ist, wo es weitergeht, und dass die
    eigenen Dateien davon unberührt bleiben.
    """
    state = activation.state()
    if not state.over:
        return False
    last_day = state.deadline.strftime("%d.%m.%Y") if state.deadline else ""
    # Dieselben Sätze wie im Fenster (``dialogs.expired_demo_text``) und
    # dieselbe Wahl: vor dem geplanten Verkaufsstart das Datum, danach der
    # Verweis auf die Website — die Verfügbarkeit behauptet keiner von beiden
    # (RM-061). Hier stand „Die aktuelle Version gibt es auf …", und am
    # 31.10. gibt es dort keine.
    if datetime.now(UTC) < PLANNED_SALE_START:
        lines = (
            tr("Diese Demo war bis einschließlich {date} nutzbar.").format(date=last_day),
            tr(
                "{app} 1.0 ist für den {start} um 10:00 Uhr deutscher Zeit geplant; "
                "den Tag davor bereiten wir die Verkaufsversion vor."
            ).format(app=APP_NAME, start=PLANNED_SALE_START.strftime("%d.%m.%Y")),
            tr(
                "Ihre gespeicherten Projekte bleiben erhalten. Auf {url} finden Sie den "
                "aktuellen Stand und danach die Installation von 1.0."
            ).format(url=WEBSITE_URL),
        )
    else:
        lines = (
            tr("Diese Demo ist beendet. Ob {app} 1.0 schon verfügbar ist, steht auf {url}.").format(
                app=APP_NAME, url=WEBSITE_URL
            ),
            tr(
                "Installieren Sie dort die aktuelle Version. Zum Bearbeiten und "
                "Exportieren brauchen Sie eine Lizenz."
            ),
            tr("Ihre gespeicherten Projekte bleiben erhalten."),
        )
    for line in lines:
        print(line, file=sys.stderr)
    return True


def _mistyped_operation(argv: list[str]) -> int | None:
    """Bei einem Tippfehler in ``run`` ein Vorschlag statt vierundachtzig Namen.

    argparse antwortet auf ``run drill_hol`` mit der vollen Liste — einmal in
    der Nutzungszeile, einmal in der Fehlermeldung, beide Male englisch und
    ohne einen Hinweis, was gemeint sein könnte. Zwei Bildschirme Text auf
    einen fehlenden Buchstaben.

    Geprüft wird vor argparse, weil danach der Name schon verloren ist: Die
    Meldung entsteht tief in ``_check_value``, und der Ausstieg ist ein
    ``SystemExit`` ohne den falschen Wert.

    Gibt ``None`` zurück, wenn nichts zu sagen ist — dann läuft alles wie
    vorher.
    """
    if len(argv) < 2 or argv[0] != "run":
        return None
    wanted = argv[1]
    if wanted.startswith("-") or REGISTRY.has(wanted):
        return None
    # **Der häufigste Fall ist kein Tippfehler, sondern die Reihenfolge.**
    # ``new``, ``info``, ``import``, ``undo`` und ``export`` nehmen den Pfad
    # zuerst — ``run`` nimmt die Operation zuerst. Wer das verwechselt, las
    # „Diese Operation gibt es nicht: C:/…/halter.p3d" und daneben den
    # Vorschlag, sich die Operationen auflisten zu lassen: beides wahr und
    # beides nutzlos. Erkannt wird der Pfad am Namen und nicht am Dateisystem —
    # ein vertippter Pfad ist derselbe Fall und verdient dieselbe Antwort.
    if wanted.lower().endswith((".p3d", ".stl", ".3mf", ".obj", ".step")) or "/" in wanted:
        print(
            "\n" + tr("Das ist ein Dateipfad und keine Operation: {path}", path=wanted),
            file=sys.stderr,
        )
        print(
            "  - "
            + tr(
                "Bei «run» kommt die Operation zuerst, der Pfad danach: {command}",
                command="solidon3d run create_box <pfad>",
            ),
            file=sys.stderr,
        )
        return 1
    near = difflib.get_close_matches(wanted, [spec.name for spec in REGISTRY.all()], n=3)
    print(
        "\n" + tr("Diese Operation gibt es nicht: {operation}", operation=wanted),
        file=sys.stderr,
    )
    if near:
        print(tr("Gemeint war vielleicht: {names}", names=", ".join(near)), file=sys.stderr)
    print(
        "  - " + tr("Alle Operationen auflisten: {command}", command="solidon3d ops"),
        file=sys.stderr,
    )
    return 1


def _install_language() -> None:
    """Die Sprache des Nutzers, wie das Fenster sie liest (Gesamtreview L-4).

    Zwei Quellen in derselben Reihenfolge wie ``ui.settings.initial_language``:
    die Einstellungen des Nutzers, dann die Wahl aus dem Installer. Was das
    Fenster als dritte Quelle hat — die Sprache des Betriebssystems — fragt Qt,
    und die Kommandozeile steht auf dem Kern (Karte in CLAUDE.md); ohne beide
    bleibt es bei der Quellsprache.

    **Der Installer war die Lücke.** Er fragt sechs Sprachen ab und notiert die
    Wahl neben der Anwendung; gelesen hat sie nur das Fenster, weil
    ``installed_language`` in ``app/ui`` lag. Der allererste Aufruf der
    Kommandozeile — also der, bei dem es noch keine ``settings.json`` gibt —
    antwortete damit deutsch, obwohl die Wahl längst getroffen war.

    Fehlt die Datei oder ist sie beschädigt, bleibt es bei der Quellsprache —
    dieselbe freundliche Richtung wie in ``load_settings``. Beschädigt heißt
    dabei auch: gültiges JSON, das kein Objekt ist. ``null`` und ``[]`` kennen
    kein ``get``, und der ``AttributeError`` daraus entstand **vor** dem
    ``try`` des Hauptprogramms — ein Stapelabzug für eine Datei, die niemand
    von Hand geschrieben hat.
    """
    import json

    language = ""
    try:
        raw = (user_config_dir() / "settings.json").read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError, ValueError:
        data = None
    if isinstance(data, dict):
        chosen = data.get("language", "")
        language = chosen if isinstance(chosen, str) else ""
    if not language:
        language = installed_language() or ""
    if language:
        install_language(language)
        set_language(language)


def main(argv: list[str] | None = None) -> int:
    install_crash_logging()
    _speak_utf8()
    _install_language()
    if _demo_is_over():
        return 1
    load_operations()
    # Die eigenen Bausteine gelten auch hier (§24.5): ein Skript, das einen
    # eigenen Baustein setzt, ist derselbe Anwendungsfall wie das Menü. Ihre
    # Befunde gehen ins Protokoll — die Kommandozeile hat keinen Prüfbericht
    # vor dem ersten Lauf.
    #
    # **Mit den Werten**, und aus demselben Grund wie im ``AppError``-Zweig
    # unten: „Ein eigenes Rezept ließ sich nicht laden." nennt weder die Datei
    # noch den Grund, und beides steht im Befund (``file``, ``reason``). Ohne
    # sie durchsucht der Kunde seinen Bausteinordner von Hand.
    for finding in load_user_parts():
        print(f"{finding.message}", file=sys.stderr)
        for key, value in finding.values.items():
            if value in (None, ""):
                continue
            print(f"  {key}: {value}", file=sys.stderr)
    parser = build_parser()
    mistyped = _mistyped_operation(argv if argv is not None else sys.argv[1:])
    if mistyped is not None:
        return mistyped
    args = parser.parse_args(argv)
    configure(debug=args.debug, to_console=False)
    try:
        result: int = args.handler(args)
        return result
    except OperationCancelled:
        print(tr("Abgebrochen."))
        return 130
    except AppError as error:
        # §2.7: was nicht ging, warum, und was jetzt möglich ist.
        print(f"\n{error.title}", file=sys.stderr)
        if error.detail:
            print(f"{error.detail}", file=sys.stderr)
        # **Und die Zahlen dazu.** Sie standen im Fehler und kamen hier nie an:
        # „Dieses Objekt gibt es in der Szene nicht." ohne die Liste der
        # Objekte, die es gibt, ist die halbe Antwort. Das Fenster zeigt sie
        # seit je — im Prüfbericht und im Fehlerdialog über ``value_line``.
        #
        # Mit den Schlüsseln und nicht mit Beschriftungen: Die
        # Beschriftungstabelle lebt in ``app/ui/labels.py`` und zieht Qt mit,
        # die Kommandozeile läuft ohne. Englische Schlüssel sind hier ohnehin
        # das Richtige — sie sind der Vertrag, den ein Skript liest (§4.2).
        for key, value in error.values.items():
            if value in (None, ""):
                continue
            print(f"  {key}: {value}", file=sys.stderr)
        for action in error.suggestions:
            print(f"  - {action.label}", file=sys.stderr)
        return 1
    except Exception as problem:  # das letzte Netz (Gesamtreview L-11)
        # Ein Stapelabzug ist keine Antwort an einen Kunden (Regel 17): ein
        # Satz, der Grund, und der Bericht als Ordner — geschrieben wie im
        # Fenster, gesendet wird nichts (§37.2).
        from app.core.errors import InternalError
        from app.core.report import exception_report, write

        report = exception_report(problem, context="CLI")
        print(file=sys.stderr)
        print(str(InternalError.default_title), file=sys.stderr)
        print(f"  {type(problem).__name__}: {report.detail}", file=sys.stderr)
        try:
            folder = write(report)
        except Exception as denied:
            # **Das letzte Netz bekommt kein Loch.** Ein ``pass`` hier hieß:
            # ein Satz, ein Grund — und dann nichts, was jemand tun kann
            # (Regel 17). Wer den Bericht nicht schreiben kann, hat trotzdem
            # das Protokoll und eine Adresse; beide stehen sonst nirgends in
            # dieser Ausgabe.
            from app.core.paths import user_log_dir

            print(
                "  "
                + tr(
                    "Der Fehlerbericht ließ sich nicht ablegen: {reason}",
                    reason=exception_report(denied).detail,
                ),
                file=sys.stderr,
            )
            print(
                "  - " + tr("Das Protokoll liegt hier: {path}", path=user_log_dir()),
                file=sys.stderr,
            )
            print(
                "  - " + tr("Damit hilft der Support weiter: {address}", address=SUPPORT_ADDRESS),
                file=sys.stderr,
            )
        else:
            print(
                "  - " + tr("Der Fehlerbericht liegt hier: {folder}", folder=folder),
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
