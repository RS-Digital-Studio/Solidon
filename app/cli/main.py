"""Command line entry point (Bauplan §10, ROADMAP P0).

The commands are not written out here: they come from the operation registry,
the same source the menu, the palette and the agent tool schema come from. An
operation that exists is reachable from the command line the moment it is
declared.

``ask`` becomes a numbered question on the terminal, ``progress`` a single line
that overwrites itself — the same contract the surface implements with a dialog
and a status bar.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from app.branding import APP_NAME, APP_VERSION, DISTRIBUTION_NAME, PROJECT_SUFFIX
from app.core import manual
from app.core.bootstrap import load_operations
from app.core.errors import AppError, OperationCancelled, ValidationError
from app.core.export import threemf
from app.core.export.writer import plan_export, write_plan
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import detect_unit
from app.core.knowledge import profiles
from app.core.log import configure
from app.core.registry import REGISTRY, cli_commands, documentation
from app.core.scene import History, OperationDraft, evaluate
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
from app.i18n import tr

_PARAM_TYPES: dict[str, Any] = {"float": float, "int": int, "str": str, "enum": str}


# --- context implementations ----------------------------------------------------


class TerminalProgress:
    """One line that overwrites itself, and nothing at all below 0.2 s (§2.8).

    Short runs stay quiet: a flicker of progress for something that took a tenth
    of a second is noise, not feedback.
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
    """Ambiguity becomes a numbered question — never a guess (Leitprinzip 6)."""
    print(f"\n{question}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}) {choice}")
    while True:
        answer = input(f"{tr('Auswahl')} [1-{len(choices)}]: ").strip()
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


def run_evaluation(project: Project, path: Path, quiet: bool = False) -> Any:
    return evaluate(
        project.document,
        profile_of(project),
        progress=(lambda fraction, text: None) if quiet else TerminalProgress(),
        ask=terminal_ask,
        sources=ProjectSources(project, base_dir=path.parent),
    )


def print_findings(findings: Any) -> None:
    for finding in findings:
        # Never colour alone (§19.1) — on a terminal the marker carries the meaning.
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

    Derselbe Text, den das Fenster zeigt: eine zweite Fassung wäre eine, die
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
    project = new_project(printer=args.printer, material=args.material)
    path = save(project, Path(args.path))
    print(f"{tr('Neues Projekt')}: {path}")
    return 0


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
            f"  {object_id:<8} {entry.name:<24} "
            f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm   "
            f"{entry.mesh.triangle_count} {tr('Dreiecke')}, {watertight}"
        )
    print(tr("Verlauf"))
    for transaction in document.transactions:
        ops = ", ".join(str(entry) for entry in transaction.ops)
        print(f"  {transaction.id:<5} {transaction.title:<28} ({tr('Ops')} {ops})")
    print_report(result)
    return 0 if result.complete else 1


def command_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    incoming = Path(args.file)
    project = open_project(path)

    if not incoming.is_file():
        print(f"{tr('Die Datei gibt es nicht')}: {incoming}", file=sys.stderr)
        return 1

    payload = incoming.read_bytes()
    unit = _chosen_unit(payload, incoming, args.unit)

    source_id = f"src_{len(project.document.sources) + 1}"
    project.document.sources[source_id] = Source(
        id=source_id,
        kind="import",
        path=embedded_source_path(incoming.name),
        sha256="",
    )
    project.sources[source_id] = payload

    # Same as the window does: a 3MF assembly needs its body count before the
    # stack hands out ids (§11).
    parts = threemf.count_objects(payload) if incoming.suffix.lower() == ".3mf" else 1
    history = History(project.document)
    history.apply(
        tr("Modell laden"),
        [
            OperationDraft(
                op="load", params={"source": source_id, "unit": unit}, produces=max(parts, 1)
            )
        ],
    )
    result = run_evaluation(project, path)
    print_report(result)
    if not result.complete:
        return 1
    save(project, path)
    print(f"{tr('Geladen')}: {incoming.name}")
    return 0


def _chosen_unit(payload: bytes, incoming: Path, requested: str) -> str:
    """Ask before the operation is written, so the answer is stored with it (§17.1)."""
    if requested != "auto":
        return requested
    guess = detect_unit(read_mesh(payload, incoming.suffix).bounds.diagonal)
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
        # Arranging and the collision check work on the whole scene (§25);
        # without ``--on`` they would otherwise run on nothing.
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
    """Write the scene out as printable files (§29).

    The command line could load a model, repair it and describe it, and then had
    no way to hand the result back — the writer existed and nothing reached it.
    A repair that cannot leave the project is a repair nobody can print.
    """
    path = Path(args.path)
    project = open_project(path)
    result = run_evaluation(project, path, quiet=True)

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
    # The check speaks before the files exist, so a warning is a warning about
    # what is being written and not about what was written (§29).
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
    export.add_argument("--format", dest="export_format", default="stl", choices=("stl", "3mf"))
    export.add_argument("--on", nargs="*", default=None, help=tr("Objekte, z. B. obj_1"))
    export.add_argument("--scheme", default=None, help=tr("Namensschema, siehe §29"))
    export.set_defaults(handler=command_export)

    run = commands.add_parser("run", help=tr("Eine Operation ausführen"))
    run_commands = run.add_subparsers(dest="op", required=True)
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
    """Let the console take every name a file can have.

    A Windows console encodes to cp1252, and ``print`` on a name outside it
    raises rather than writing something. That is not a corner case: the first
    real model handed to this command line was called ``埃菲尔铁塔18cm.stl``, the
    import ran through, and the run ended in an encoding traceback on the line
    that reports success. German umlauts survive cp1252, which is why nothing
    here noticed for a whole phase.

    ``backslashreplace`` rather than plain UTF-8: a console that cannot show the
    characters then prints their escapes instead of failing, and the name stays
    recognisable either way.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    _speak_utf8()
    load_operations()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure(debug=args.debug, to_console=False)
    try:
        result: int = args.handler(args)
        return result
    except OperationCancelled:
        print(tr("Abgebrochen."))
        return 130
    except AppError as error:
        # §2.7: what did not work, why, and what is possible now.
        print(f"\n{error.title}", file=sys.stderr)
        if error.detail:
            print(f"{error.detail}", file=sys.stderr)
        for action in error.suggestions:
            print(f"  - {action.label}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
