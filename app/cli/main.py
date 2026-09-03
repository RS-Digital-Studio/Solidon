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

import argparse
import difflib
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.branding import (
    APP_NAME,
    APP_VERSION,
    DISTRIBUTION_NAME,
    PROJECT_SUFFIX,
    SUPPORT_ADDRESS,
    WEBSITE_URL,
)
from app.core import activation, manual
from app.core.bootstrap import load_operations, load_user_parts
from app.core.errors import CANCEL, AppError, OperationCancelled, UserError, ValidationError
from app.core.export.writer import FORMAT_SUFFIX, plan_export, write_plan
from app.core.ingest.loader import detect_unit, read_local_payload, read_model
from app.core.ingest.plan import import_plan
from app.core.knowledge import profiles
from app.core.log import configure
from app.core.paths import installed_language, user_config_dir
from app.core.registry import REGISTRY, cli_commands, documentation
from app.core.scene import History, OperationDraft, ResultCache, disk_backed_cache, evaluate
from app.core.scene.project import (
    Project,
    ProjectSources,
    embedded_source_path,
    load,
    new_project,
    save,
)
from app.core.types import Source
from app.core.units import format_length
from app.i18n import _, set_language, tr
from app.i18n.catalog import install_language

_PARAM_TYPES: dict[str, Any] = {"float": float, "int": int, "str": str, "enum": str}


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
            answer = input(f"{tr('Auswahl')} [1-{len(choices)}]: ").strip()
        except EOFError as end:
            raise UserError(
                title=_("Diese Frage braucht eine Antwort, und hier ist niemand."),
                detail=_(
                    "Der Lauf hat keine Eingabe. Die Antwort lässt sich vorab "
                    "mitgeben — beim Einlesen etwa über „--unit“."
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
    return load(path)


def profile_of(project: Project) -> Any:
    return profiles.make_profile(
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
    return evaluate(
        project.document,
        profile_of(project),
        progress=(lambda fraction, text: None) if quiet else TerminalProgress(),
        ask=terminal_ask,
        sources=ProjectSources(project, base_dir=path.parent),
        cache=evaluation_cache(),
    )


def print_findings(findings: Any) -> None:
    for finding in findings:
        # Nie Farbe allein (§19.1) — im Terminal trägt das Zeichen die Bedeutung.
        marker = {"info": "-", "warning": "!", "error": "X"}[finding.severity]
        print(f"  {marker} {finding.message}")


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
        state = tr("kalibriert") if material.calibrated else tr("Startwert")
        print(f"  {identifier:<24} {material.title:<28} {state}")
    return 0


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
    print(f"{tr('Neues Projekt')}: {path}")
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

    print(f"{tr('Projekt')}: {path.name}")
    print(
        f"{tr('Drucker')}: {document.printer or '-'}   "
        f"{tr('Material')}: {document.material or '-'}   "
        f"{tr('Format')}: {document.format_version}"
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
            f"{entry.mesh.triangle_count} {tr('Dreiecke')}, {watertight}"
        )
    print(tr("Verlauf"))
    for transaction in document.transactions:
        ops = ", ".join(str(entry) for entry in transaction.ops)
        # !s zuerst: ein übersetzbarer Titel kennt keine Formatbreite.
        print(f"  {transaction.id:<5} {transaction.title!s:<28} ({tr('Ops')} {ops})")
    print_report(result)
    return 0 if result.complete else 1


def command_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    incoming = Path(args.file)
    project = open_project(path)

    if not incoming.is_file():
        print(f"{tr('Die Datei gibt es nicht')}: {incoming}", file=sys.stderr)
        return 1

    payload = read_local_payload(incoming)

    source_id = f"src_{len(project.document.sources) + 1}"
    project.document.sources[source_id] = Source(
        id=source_id,
        kind="import",
        path=embedded_source_path(incoming.name, source_id),
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
    # Das erste Modell eines Projekts kommt mittig auf die Platte (§17.1,
    # Schritt 6). Gefragt wird der Stapel und nicht die Szene: Er steht fest,
    # bevor irgendetwas ausgewertet ist, und die Operation trägt die
    # Entscheidung danach selbst.
    first_model = not project.document.ops
    plan = import_plan(source_id, incoming.name, payload, args.unit, first_model=first_model)
    if plan.asks_unit:
        plan = import_plan(
            source_id,
            incoming.name,
            payload,
            _chosen_unit(payload, incoming, args.unit),
            first_model=first_model,
        )
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(f"{tr('Geladen')}: {incoming.name}")
    return 0


def _chosen_unit(payload: bytes, incoming: Path, requested: str) -> str:
    """Fragt, bevor die Operation geschrieben wird, damit die Antwort mit ihr
    gespeichert wird (§17.1).
    """
    if requested != "auto":
        return requested
    guess = detect_unit(read_model(payload, incoming.suffix).bounds.diagonal)
    if guess.unit is not None:
        return guess.unit
    return terminal_ask(
        tr("In welcher Einheit ist diese Datei gespeichert?"),
        [str(candidate) for candidate in guess.candidates],
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

    history = History(project.document)
    history.apply(
        spec.title,
        [OperationDraft(op=spec.name, inputs=inputs, params=params, seed=args.seed)],
    )
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(f"{tr('Ausgeführt')}: {spec.name}")
    return 0


def command_undo(args: argparse.Namespace) -> int:
    path = Path(args.path)
    project = open_project(path)
    history = History(project.document)
    transaction = history.undo()
    if transaction is None:
        print(tr("Es gibt nichts zurückzunehmen."))
        return 1
    save(project, path)
    print(f"{tr('Zurückgenommen')}: {transaction.title}")
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
    )
    # Die Prüfung spricht, bevor die Dateien existieren — eine Warnung ist
    # also eine Warnung über das, was geschrieben wird, nicht über das, was
    # geschrieben wurde (§29).
    print_findings(plan.findings)

    written = write_plan(plan, Path(args.directory), args.export_format)
    for target in written:
        print(f"{tr('Geschrieben')}: {target}")
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
    importing.set_defaults(handler=command_import)

    undo = commands.add_parser("undo", help=tr("Letzte Transaktion zurücknehmen"))
    undo.add_argument("path")
    undo.set_defaults(handler=command_undo)

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
        for argument in command.arguments:
            if argument.kind == "bool":
                entry.add_argument(
                    argument.flag,
                    dest=argument.name,
                    action="store_true",
                    default=None,
                    help=argument.help,
                )
                continue
            entry.add_argument(
                argument.flag,
                dest=argument.name,
                type=_PARAM_TYPES.get(argument.kind, str),
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
    print(
        tr("Diese Demo von {app} lief bis zum {date} und lässt sich nicht mehr starten.").format(
            app=APP_NAME, date=last_day
        ),
        file=sys.stderr,
    )
    print(tr("Die aktuelle Version gibt es auf {url}.").format(url=WEBSITE_URL), file=sys.stderr)
    print(
        tr(
            "Ihre Projektdateien bleiben lesbar — eine Projektdatei ist ein "
            "ZIP-Archiv mit JSON darin."
        ),
        file=sys.stderr,
    )
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
        print(f"\n{tr('Das ist ein Dateipfad und keine Operation')}: {wanted}", file=sys.stderr)
        print(
            f"  - {tr('Bei «run» kommt die Operation zuerst, der Pfad danach')}: "
            "solidon3d run create_box <pfad>",
            file=sys.stderr,
        )
        return 1
    near = difflib.get_close_matches(wanted, [spec.name for spec in REGISTRY.all()], n=3)
    print(f"\n{tr('Diese Operation gibt es nicht')}: {wanted}", file=sys.stderr)
    if near:
        print(f"{tr('Gemeint war vielleicht')}: {', '.join(near)}", file=sys.stderr)
    print(f"  - {tr('Alle Operationen auflisten')}: solidon3d ops", file=sys.stderr)
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
    except (OSError, ValueError):
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
        import traceback

        from app.core.errors import InternalError
        from app.core.report import ErrorReport, write

        print(file=sys.stderr)
        print(str(InternalError.default_title), file=sys.stderr)
        print(f"  {type(problem).__name__}: {problem}", file=sys.stderr)
        try:
            folder = write(
                ErrorReport(
                    summary=f"CLI: {type(problem).__name__}",
                    detail=str(problem),
                    traceback=traceback.format_exc(),
                )
            )
        except OSError as denied:
            # **Das letzte Netz bekommt kein Loch.** Ein ``pass`` hier hieß:
            # ein Satz, ein Grund — und dann nichts, was jemand tun kann
            # (Regel 17). Wer den Bericht nicht schreiben kann, hat trotzdem
            # das Protokoll und eine Adresse; beide stehen sonst nirgends in
            # dieser Ausgabe.
            from app.core.paths import user_log_dir

            print(f"  {tr('Der Fehlerbericht ließ sich nicht ablegen')}: {denied}", file=sys.stderr)
            print(f"  - {tr('Das Protokoll liegt hier')}: {user_log_dir()}", file=sys.stderr)
            print(
                f"  - {tr('Damit hilft der Support weiter')}: {SUPPORT_ADDRESS}",
                file=sys.stderr,
            )
        else:
            print(f"  - {tr('Der Fehlerbericht liegt hier')}: {folder}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
