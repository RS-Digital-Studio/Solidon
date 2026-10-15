"""Verschiebewerkzeug (Codestruktur Schritt 0, Plan 2.7): verschiebt Namen nach einer Zuschnittliste
und beweist, dass nur verschoben wurde.

    .venv\\Scripts\\python.exe tools/move_names.py SCHNITT.toml          # planen, beweisen, ändern
    .venv\\Scripts\\python.exe tools/move_names.py SCHNITT.toml --check  # nur beweisen
    .venv\\Scripts\\python.exe tools/move_names.py --list-copies         # Originale mit Kopfkopien

Ablauf: Zuschnitt lesen (``tools/move_cut.py``), Index des Baums bauen (Paket R,
``tools/code_index.py``), den Schnitt planen (je Modus ``tools/move_module.py``,
``tools/move_copies.py``, ``tools/move_component.py``), ihn in einen **Kandidatenbaum** schreiben
(Verweise auf die unveränderten Dateien, die geänderten neu), dort Importe sortieren und
formatieren (``ruff``), den Beweis führen (``tools/move_proof.py``) — und erst wenn er grün ist,
den Baum selbst ändern. Ein roter Beweis schreibt nichts; ein Fehler beim Schreiben stellt jede
schon geschriebene Datei auf ihre alten Bytes zurück (es sind nur die eigenen Änderungen dieses
Laufs). Exit 0: geschrieben (oder schon angewandt, oder mit ``--check`` bewiesen), 1: Beweis rot,
2: Zuschnitt oder Plan abgewiesen, 3: der Baum änderte sich während Planung und Beweis (jede Datei
der Bereiche, auch eine unberührte; nichts geschrieben — neu erzeugen), 4: Schreiben gescheitert
(zurückgestellt), 5: Werkzeugfehler (Traceback). Jeder Ausgang außer 0 nennt seinen Ausweg.

**Zuschnittliste** (TOML, ``schema_version = 1``):

* gemeinsam: ``id``, ``mode`` (``module``, ``copies``, ``component``), ``[[aliases]]`` (``path``,
  ``module``, ``name``) — der Name, unter dem eine Datei ein Modul neu bindet, wenn der letzte Teil
  dort schon vergeben ist.
* ``module``: ``source`` (``app/…/x.py``), ``package_docstring`` (wenn die Quelle Paket wird),
  ``[[targets]]`` (``module``, ``docstring``, ``definitions``, ``over_limit``), ``duplicate``
  (Namen, die in jedes lesende Ziel kopiert werden, etwa ein Logger), ``[[renames]]`` (``name``,
  ``to``), ``[[identity]]`` (``name``, ``reason``: eine Definition, die ``__name__`` oder
  ``globals()`` liest), ``[[name_lists]]`` (``path``, ``value``, ``to``: Zeichenketten mit Modul,
  Datei oder Namen der Quelle, W6; ``to = [value]`` erklärt, dass sie bleibt),
  ``[[source_readers]]`` (``path``, ``scope``, ``module``: Leser von ``Path(M.__file__)``).
* ``copies``: ``[[bindings]]`` (``module``, ``name``) — die Originale, deren Kopfkopien
  Modulzugriffe werden (Vorschlag: ``--list-copies``).
* ``component``: ``source`` (Datei des Wirts), ``host`` (Klasse), ``component``
  (``modul:Klasse`` aus dem Gerüst-Commit), ``host_attribute`` (``self.<attr>`` im Wirt),
  ``host_protocol``, ``methods`` (wandern), ``own_attributes`` (Zustand der Komponente),
  ``host_members`` (über ``_host``), ``parent_members`` (von Qt ererbt, über ``_parent``),
  ``[[self_roles]]`` (``scope`` = ``Wirt.methode``, ``call`` wie im Quelltext, ``argument``
  Position oder Schlüsselwort, ``role`` = ``qt_parent``, ``owner``, ``event_filter`` oder
  ``flow_host``), ``[[accesses]]`` (``path``, ``scope`` als Qualname oder ``<module>``,
  ``member``, ``decision`` = ``component`` oder ``keep``).

Jedes Feld ist eine Erklärung, keine Ausnahme: Was sie nicht trifft, ist ein Fehler, und es gibt
keinen Schalter, der einen Fund übergeht (Konzept Codestruktur 4.1).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.code_index import CACHE, Index  # noqa: E402
from tools.move_cut import Cut, CutError, load  # noqa: E402
from tools.move_edits import EditError, apply_text  # noqa: E402
from tools.move_proof import Proof, prove  # noqa: E402
from tools.move_refs import AlreadyAppliedError, Context, PlanError  # noqa: E402
from tools.move_source import AREAS, LINE_LIMIT, path_of  # noqa: E402
from tools.move_trees import tree_files  # noqa: E402

#: Der Ausgang je Ergebnis; jeder Weg hinaus hat seinen eigenen (Modul-Docstring).
EXIT = {
    "written": 0,
    "applied": 0,
    "proven": 0,
    "red": 1,
    "rejected": 2,
    "stale": 3,
    "write_failed": 4,
    "tool_error": 5,
}


@dataclass
class Change:
    """Was ein Schnitt am Baum ändert: neue oder geänderte Dateien (Inhalt) und entfallende;
    ``snapshot`` ist der Stand jeder Datei der Bereiche beim Planen (Pfad → SHA-256)."""

    files: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    snapshot: dict[str, str] = field(default_factory=dict)


class StaleError(RuntimeError):
    """Der Baum hat sich seit dem Planen geändert; ``problems`` nennt jede Datei."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Result:
    status: str
    proof: Proof | None = None
    change: Change | None = None
    problems: list[str] = field(default_factory=list)


def plan(cut: Cut, root: Path, index: Index) -> Change:
    """Plant den Schnitt; ``PlanError`` nennt alle Funde."""
    ctx = Context(root, cut, index)
    change = Change()
    if cut.mode == "module":
        from tools.move_module import ModulePlanner

        result = ModulePlanner(ctx).plan()
        change.files.update(result.files)
        change.removed.extend(result.removed)
        edits = result.edits
    elif cut.mode == "copies":
        from tools.move_copies import CopiesPlanner

        edits = CopiesPlanner(ctx).plan()
    else:
        from tools.move_component import ComponentPlanner

        planned = ComponentPlanner(ctx).plan()
        edits = planned.edits
        change.notes.extend(planned.notes)
    for path, rows in edits.items():
        try:
            change.files[path] = apply_text(ctx.source(path), rows)
        except EditError as error:
            ctx.problem(
                f"{error} — die Tabelle lässt sich so nicht anwenden (Werkzeugfehler); die Stelle "
                "vor dem Schnitt einfacher schreiben und den Fall melden"
            )
            continue
        change.notes.extend(f"{path}:{row.line}: {row.rule}: {row.detail}" for row in rows)
    for path in [*change.files, *change.removed]:
        if (root / path).is_file():
            change.hashes[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    targets = {t.module: t for t in cut.targets}
    for path, text in change.files.items():
        lines = text.count("\n")
        module = path.removesuffix(".py").replace("/", ".")
        allowed = module in targets and targets[module].over_limit
        if lines > LINE_LIMIT and path not in change.hashes and not allowed:
            ctx.problem(
                f"{path}: {lines} Zeilen, mehr als {LINE_LIMIT} (Konzept 3.1, Regel 1) — feiner "
                "schneiden oder over_limit erklären und die Sperrklinke nachziehen"
            )
    component = path_of(cut.component_module) if cut.mode == "component" else ""
    if component in change.files:
        lines = change.files[component].count("\n")
        if lines > LINE_LIMIT:
            ctx.problem(
                f"{component}: {lines} Zeilen, mehr als {LINE_LIMIT} — die Komponente steht "
                f"unter {LINE_LIMIT} Zeilen (Konzept 4.5); weniger Methoden in diesen Schnitt "
                "nehmen oder eine zweite Komponente bilden"
            )
    ctx.raise_problems()
    return change


# ---------------------------------------------------------------------- Kandidatenbaum


def candidate(root: Path, change: Change, folder: Path) -> Path:
    """Ein Kandidatenbaum unter ``folder``: Verweise (Hardlinks) auf jede Datei der Bereiche,
    geänderte Dateien neu geschrieben. Ein Verweis wird vor dem Schreiben gelöst, damit der echte
    Baum unberührt bleibt; geht kein Hardlink, wird kopiert."""
    tree = folder / "tree"
    for area in AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for full in base.rglob("*"):
            relative = full.relative_to(root)
            if any(p == "__pycache__" or p.startswith(".") for p in relative.parts[:-1]):
                continue
            if not full.is_file():
                continue
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(full, target)
            except OSError:
                shutil.copy2(full, target)
    for name in ("pyproject.toml",):
        if (root / name).is_file():
            shutil.copy2(root / name, tree / name)
    if (root / CACHE).is_file():
        (tree / CACHE).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / CACHE, tree / CACHE)
    for path in change.removed:
        (tree / path).unlink()
    for path, text in change.files.items():
        target = tree / path
        if target.exists():
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    return tree


def tidy(tree: Path, paths: Sequence[str], config: Path | None) -> list[str]:
    """Importe sortieren und formatieren (``ruff``) an den geänderten Dateien des Kandidaten.
    Zurück kommen die Meldungen, wenn ``ruff`` scheitert — dann gilt der Plan als abgewiesen."""
    if not paths:
        return []
    base = [sys.executable, "-m", "ruff"]
    settings = ["--config", str(config)] if config is not None else []
    problems: list[str] = []
    for command in (
        [*base, "check", "--select", "I", "--fix", "--quiet", *settings, *paths],
        [*base, "format", "--quiet", *settings, *paths],
    ):
        done = subprocess.run(
            command,
            cwd=tree,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if done.returncode != 0:
            problems.append(
                f"ruff ({' '.join(command[3:5])}): {(done.stdout + done.stderr).strip()}"
            )
    if problems:
        return problems
    # Danach gelten die Regeln des Projekts: Was der Schnitt hinterließe (eine zu lange Zeile in
    # einem f-String, ein ungelesener Import), hält ihn an, statt nach dem Schreiben rot zu sein.
    done = subprocess.run(
        [*base, "check", "--quiet", "--output-format", "concise", *settings, *paths],
        cwd=tree,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if done.returncode != 0:
        for line in (done.stdout + done.stderr).splitlines():
            if line.strip() and not line.startswith(("Found ", "[*]")):
                problems.append(
                    f"ruff check nach dem Umschreiben: {line.strip()} — die Stelle vor dem "
                    "Schnitt so schreiben, dass sie danach den Regeln genügt"
                )
    return problems


# ------------------------------------------------------------------------------ Schreiben


def snapshot(root: Path) -> dict[str, str]:
    """Der Stand jeder Datei der Bereiche (ohne ``__pycache__`` und Punktordner): Pfad →
    SHA-256 — dieselbe Menge, die der Beweis als Baum vergleicht."""
    return {path: hashlib.sha256(data).hexdigest() for path, data in tree_files(root).items()}


def stale(root: Path, change: Change) -> list[str]:
    """Jede Datei der Bereiche, die seit dem Planen entstand, verschwand oder sich änderte — auch
    eine, die der Schnitt nicht berührt: Ein neuer Leser der Quelle bliebe sonst stehen."""
    now = snapshot(root)
    before = change.snapshot
    found: list[str] = []
    for path in sorted(set(now) | set(before)):
        if path not in before:
            found.append(f"{path} ist seit der Planung entstanden")
        elif path not in now:
            found.append(f"{path} ist seit der Planung verschwunden")
        elif now[path] != before[path]:
            found.append(f"{path} hat sich seit der Planung geändert")
    return [f"{text} — den Schnitt neu erzeugen" for text in found]


def write(root: Path, change: Change, tree: Path) -> None:
    """Übernimmt den bewiesenen Kandidaten in den Baum. Vorher: Jede Datei der Bereiche hat noch
    den Stand, gegen den geplant wurde (sonst :class:`StaleError`). Scheitert ein Schritt,
    kommen die schon geschriebenen Dateien auf ihre alten Bytes zurück."""
    problems = stale(root, change)
    if problems:
        raise StaleError(problems)
    done: list[tuple[Path, bytes | None]] = []
    try:
        for path in change.files:
            target = root / path
            before = target.read_bytes() if target.is_file() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".move-names")
            temporary.write_bytes((tree / path).read_bytes())
            done.append((target, before))
            temporary.replace(target)
        for path in change.removed:
            target = root / path
            before = target.read_bytes()
            done.append((target, before))
            target.unlink()
    except BaseException:
        for target, before in reversed(done):
            if before is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(before)
            target.with_name(target.name + ".move-names").unlink(missing_ok=True)
        raise


# ------------------------------------------------------------------------------ Einstieg


def run(
    cut: Cut,
    root: Path,
    *,
    check: bool = False,
    work: Path | None = None,
    use_ruff: bool = True,
    registry: bool = True,
    cache: bool = True,
) -> Result:
    """Plant, beweist und schreibt (außer ``check``) einen Schnitt. Status: ``written``,
    ``applied``, ``proven`` (mit ``check``), ``red``, ``rejected`` oder ``stale`` (der Baum
    änderte sich, während geplant und bewiesen wurde; nichts geschrieben)."""
    state = snapshot(root)
    index = Index.build(root, cache=cache)
    try:
        change = plan(cut, root, index)
    except AlreadyAppliedError as applied:
        return Result("applied", problems=[str(applied)])
    except PlanError as error:
        return Result("rejected", problems=error.problems)
    change.snapshot = state
    with tempfile.TemporaryDirectory(prefix="move-names-", dir=work) as folder:
        tree = candidate(root, change, Path(folder))
        config = root / "pyproject.toml" if (root / "pyproject.toml").is_file() else None
        if use_ruff:
            problems = tidy(tree, sorted(change.files), config)
            if problems:
                return Result("rejected", change=change, problems=problems)
        new_index = Index.build(tree, cache=cache)
        proof = prove(cut, root, tree, old_index=index, new_index=new_index, registry=registry)
        if not proof.ok or check:
            return Result("proven" if proof.ok else "red", proof=proof, change=change)
        try:
            write(root, change, tree)
        except StaleError as error:
            return Result("stale", proof=proof, change=change, problems=error.problems)
    return Result("written", proof=proof, change=change)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cut", nargs="?", type=Path, help="die Zuschnittliste (TOML)")
    parser.add_argument("--root", type=Path, default=ROOT, help="Baum (Vorgabe: dieses Repository)")
    parser.add_argument("--check", action="store_true", help="nur planen und beweisen")
    parser.add_argument("--proof", type=Path, help="das Beweisprotokoll in diese Datei schreiben")
    parser.add_argument("--work", type=Path, help="Ordner für den Kandidatenbaum")
    parser.add_argument(
        "--list-copies", action="store_true", help="Originale mit Kopfkopien (W2 c)"
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.list_copies:
        from tools.move_copies import bindings_toml, list_copies

        print(bindings_toml(list_copies(Index.build(root))), end="")
        return 0
    if args.cut is None:
        parser.error("eine Zuschnittliste angeben")
    try:
        cut = load(args.cut)
    except CutError as error:
        print(f"move_names: {error}", file=sys.stderr)
        return EXIT["rejected"]
    try:
        result = run(cut, root, check=args.check, work=args.work)
    except OSError as error:
        print(
            f"move_names: Schreiben gescheitert ({error}) — jede schon geschriebene Datei steht "
            "wieder auf ihren alten Bytes; Ursache beheben (Rechte, Platz, Sperre) und den Schnitt "
            "neu erzeugen",
            file=sys.stderr,
        )
        return EXIT["write_failed"]
    except Exception:
        traceback.print_exc()
        print(
            "move_names: Werkzeugfehler (Traceback oben) — der Baum ist unverändert oder auf seine "
            "alten Bytes zurückgestellt; den Fall mit Zuschnitt und Traceback melden",
            file=sys.stderr,
        )
        return EXIT["tool_error"]
    for problem in result.problems:
        print(f"move_names: {problem}", file=sys.stderr)
    if result.proof is not None:
        text = result.proof.text()
        if args.proof is not None:
            args.proof.write_text(text, encoding="utf-8", newline="\n")
        print(text)
    print(f"move_names: {result.status}")
    return EXIT[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
