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
Laufs). Exit 0: geschrieben (oder schon angewandt), 1: Beweis rot, 2: Zuschnitt oder Plan
abgewiesen.

**Zuschnittliste** (TOML, ``schema_version = 1``):

* gemeinsam: ``id``, ``mode`` (``module``, ``copies``, ``component``), ``[[aliases]]`` (``path``,
  ``module``, ``name``) — der Name, unter dem eine Datei ein Modul neu bindet, wenn der letzte Teil
  dort schon vergeben ist.
* ``module``: ``source`` (``app/…/x.py``), ``package_docstring`` (wenn die Quelle Paket wird),
  ``[[targets]]`` (``module``, ``docstring``, ``definitions``, ``over_limit``), ``duplicate``
  (Namen, die in jedes lesende Ziel kopiert werden, etwa ein Logger), ``[[renames]]`` (``name``,
  ``to``), ``[[identity]]`` (``name``, ``reason``: eine Definition, die ``__name__`` oder
  ``globals()`` liest), ``[[name_lists]]`` (``path``, ``value``, ``to``: Modul- und Namenslisten
  als Text, W6), ``[[source_readers]]`` (``path``, ``scope``, ``module``: Leser von
  ``Path(M.__file__)``).
* ``copies``: ``[[bindings]]`` (``module``, ``name``) — die Originale, deren Kopfkopien
  Modulzugriffe werden.
* ``component``: ``source``, ``host``, ``component`` (``modul:Klasse``), ``host_attribute``,
  ``host_protocol``, ``methods``, ``own_attributes``, ``host_members``, ``parent_members``,
  ``[[self_roles]]`` (``scope``, ``call``, ``argument``, ``role``), ``[[accesses]]`` (``path``,
  ``scope``, ``member``, ``decision``).

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
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.code_index import CACHE, Index  # noqa: E402
from tools.move_cut import Cut, CutError, load  # noqa: E402
from tools.move_edits import apply_text  # noqa: E402
from tools.move_proof import Proof, prove  # noqa: E402
from tools.move_refs import AlreadyAppliedError, Context, PlanError  # noqa: E402
from tools.move_source import AREAS  # noqa: E402

#: Größte Zeilenzahl eines neuen Moduls (Konzept 3.1, Regel 1); darüber nur mit ``over_limit``.
LINE_LIMIT = 2000


@dataclass
class Change:
    """Was ein Schnitt am Baum ändert: neue oder geänderte Dateien (Inhalt) und entfallende."""

    files: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


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
        change.files[path] = apply_text(ctx.source(path), rows)
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
    return problems


# ------------------------------------------------------------------------------ Schreiben


def write(root: Path, change: Change, tree: Path) -> None:
    """Übernimmt den bewiesenen Kandidaten in den Baum. Vorher: Jede berührte Datei hat noch die
    Bytes, gegen die geplant wurde. Scheitert ein Schritt, kommen die schon geschriebenen Dateien
    auf ihre alten Bytes zurück."""
    for path, digest in change.hashes.items():
        current = (root / path).read_bytes() if (root / path).is_file() else b""
        if hashlib.sha256(current).hexdigest() != digest:
            raise RuntimeError(
                f"{path} hat sich seit der Planung geändert — den Schnitt neu erzeugen"
            )
    for path in change.files:
        if path not in change.hashes and (root / path).exists():
            raise RuntimeError(f"{path} ist seit der Planung entstanden — den Schnitt neu erzeugen")
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
    """Plant, beweist und schreibt (außer ``check``) einen Schnitt."""
    index = Index.build(root, cache=cache)
    try:
        change = plan(cut, root, index)
    except AlreadyAppliedError as applied:
        return Result("applied", problems=[str(applied)])
    except PlanError as error:
        return Result("rejected", problems=error.problems)
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
        write(root, change, tree)
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
        return 2
    result = run(cut, root, check=args.check, work=args.work)
    for problem in result.problems:
        print(f"move_names: {problem}", file=sys.stderr)
    if result.proof is not None:
        text = result.proof.text()
        if args.proof is not None:
            args.proof.write_text(text, encoding="utf-8", newline="\n")
        print(text)
    print(f"move_names: {result.status}")
    return {"written": 0, "applied": 0, "proven": 0, "red": 1}.get(result.status, 2)


if __name__ == "__main__":
    raise SystemExit(main())
