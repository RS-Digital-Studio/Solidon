"""Druckgleich über Korpus und Beispielprojekte: zwei Codestände gegeneinander (§11.2).

Ein Stand wird in seinem eigenen Baum aufgenommen, der andere in seinem; erst
die Abbilder treffen sich (``tests/print_equal.py``). Zwei Codestände laufen
nie im selben Prozess.

    python tools/check_print_equal.py shoot AUSGABE --examples
    python tools/check_print_equal.py shoot AUSGABE --tree F:\\stand-davor --model a.stl
    python tools/check_print_equal.py compare VORHER NACHHER

``shoot`` wertet jedes Beispielprojekt (``--examples``) und jede genannte
Modelldatei (``--model``, eingelesen wie *Öffnen* in Millimetern) im Baum
``--tree`` aus — Vorgabe ist der Baum dieses Werkzeugs — und legt je Fall ein
Abbild ab. ``--quick`` lässt Selbstdurchdringung, STL-Runde und Rundreise weg
(für Netze mit Millionen Dreiecken); das Urteil nennt sie dann ungeprüft.
``--cache`` nimmt den Stand nach dem Wiederöffnen auf: einmal in einen
Plattencache auswerten, dann mit frischem Speicher über demselben Ordner —
der Weg, den ein gespeichertes Projekt beim Öffnen nimmt.
Die Nutzerverzeichnisse liegen für den Lauf in einem Temp-Ordner (§38).

``compare`` hält gleichnamige Abbilder zweier Ordner gegeneinander, schreibt
je Fall das Urteil und am Ende die größte Abweichung. Exit-Code 0, wenn jeder
Fall druckgleich ist; 1 sonst.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent


def _helper() -> ModuleType:
    """``tests/print_equal.py`` aus dem Baum dieses Werkzeugs, gleich welcher Baum rechnet."""
    spec = importlib.util.spec_from_file_location("print_equal", ROOT / "tests" / "print_equal.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["print_equal"] = module
    spec.loader.exec_module(module)
    return module


def _use_tree(tree: Path) -> None:
    """Der rechnende Baum steht vorn, bevor irgendetwas ``app`` lädt (Editierinstallation)."""
    sys.path.insert(0, str(tree))
    import app

    loaded = Path(app.__file__).resolve().parent.parent
    if loaded != tree.resolve():
        raise SystemExit(f"app kommt aus {loaded}, nicht aus {tree}")


def _profile(project: Any) -> Any:
    from app.core.knowledge import profiles

    return profiles.make_profile(
        project.document.printer or "centauri-carbon-2", project.document.material or "petg"
    )


def _example(path: Path) -> Any:
    from app.core.scene.project import load

    return load(path)


def _model(path: Path) -> Any:
    """Ein Projekt mit dieser Datei, wie *Öffnen* sie einliest — in Millimetern, ohne Frage."""
    from app.core.ingest.plan import import_plan
    from app.core.scene import History
    from app.core.scene.project import embedded_source_path, new_project, next_source_id
    from app.core.types import Source

    project = new_project()
    payload = path.read_bytes()
    source_id = next_source_id(project.document.sources)
    project.document.sources[source_id] = Source(
        id=source_id, kind="import", path=embedded_source_path(path.name, source_id), sha256=""
    )
    project.sources[source_id] = payload
    plan = import_plan(source_id, path.name, payload, "mm", first_model=True)
    History(project.document).apply(plan.title, [plan.draft])
    return project


def _isolated(folder: str) -> None:
    """Die Nutzerverzeichnisse des rechnenden Baums in einen Temp-Ordner (§38)."""
    from app.core.paths import PROFILE_VARIABLES

    for variable in PROFILE_VARIABLES:
        os.environ[variable] = folder


def shoot(arguments: argparse.Namespace, folder: str) -> int:
    tree = Path(arguments.tree or ROOT)
    _use_tree(tree)
    _isolated(folder)
    helper = _helper()
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources

    load_operations()
    cases: list[tuple[str, Any]] = []
    if arguments.examples:
        cases += [
            (path.stem, lambda path=path: _example(path))
            for path in sorted((tree / "app" / "examples").glob("*.p3d"))
        ]
    cases += [
        (
            Path(name).stem,
            lambda path=Path(name): (_example if path.suffix == ".p3d" else _model)(path),
        )
        for name in arguments.model
    ]
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = (
        {"crossings": False, "weld": False, "exports": ()} if arguments.quick else {}
    )
    for name, opened in cases:
        project = opened()
        rounds: list[Any] = [None]
        if arguments.cache:
            disk = Path(folder) / "cache" / name
            rounds = [
                ResultCache(disk=DiskCache(codec=MeshCodec(), directory=disk)) for _ in range(2)
            ]
        for cache in rounds:
            questions = helper.QuestionLog()
            result = evaluate(
                project.document,
                _profile(project),
                sources=ProjectSources(project),
                ask=questions,
                cache=cache,
            )
        target = helper.save(helper.shot(result, questions=questions, **options), out / name)
        hits = f", Plattentreffer {rounds[-1].statistics.disk_hits}" if arguments.cache else ""
        print(f"{name}: {len(result.scene.objects)} Körper{hits} → {target}", flush=True)
    return 0


def compare(arguments: argparse.Namespace, folder: str) -> int:
    if arguments.tree:
        _use_tree(Path(arguments.tree))
    helper = _helper()
    before, after = Path(arguments.before), Path(arguments.after)
    names = sorted(path.name for path in before.glob("*.npz"))
    missing = sorted(set(names) ^ {path.name for path in after.glob("*.npz")})
    largest, where, failed = 0.0, "", list(missing)
    for name in names:
        if name in missing:
            continue
        verdict = helper.compare(helper.load(before / name), helper.load(after / name))
        print(f"{name}: {verdict.report()}", flush=True)
        if verdict.largest > largest:
            largest, where = verdict.largest, f"{name} {verdict.where}"
        if not verdict.print_equal:
            failed.append(name)
    print(f"Größte Abweichung: {helper.micrometres(largest)} ({where})")
    if missing:
        print(f"Nur auf einer Seite: {missing}")
    print(f"Nicht druckgleich: {failed}" if failed else "Alle Fälle druckgleich.")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    shooting = commands.add_parser("shoot")
    shooting.add_argument("out")
    shooting.add_argument("--tree", default=None)
    shooting.add_argument("--examples", action="store_true")
    shooting.add_argument("--model", action="append", default=[])
    shooting.add_argument("--quick", action="store_true")
    shooting.add_argument("--cache", action="store_true")
    shooting.set_defaults(handler=shoot)
    comparing = commands.add_parser("compare")
    comparing.add_argument("before")
    comparing.add_argument("after")
    comparing.add_argument("--tree", default=None)
    comparing.set_defaults(handler=compare)
    arguments = parser.parse_args(argv)
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory(prefix="solidon-print-equal-") as folder:
            return int(arguments.handler(arguments, folder))
    finally:
        os.environ.clear()
        os.environ.update(saved)


if __name__ == "__main__":
    sys.exit(main())
