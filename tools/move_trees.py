"""Bäume, Protokoll und Abbildung des Verschiebewerkzeugs — gemeinsam für Beweis und Planer.

``Trees`` hält den alten und den neuen Baum mit Dateien, Quellen und den Indizes aus Paket R,
``Proof`` sammelt Fehler, Protokollzeilen und Grundmengen, ``Mapping`` bildet alte Namen auf neue
ab (je Modus eine Unterklasse).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from tools.code_index import Index, PatchSite
from tools.move_cut import Cut
from tools.move_source import AREAS, Source


@dataclass
class Proof:
    """Ergebnis des Beweises: Fehler, Protokoll und Grundmengen."""

    cut: Cut
    errors: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, text: str) -> None:
        if text not in self.errors:
            self.errors.append(text)

    def note(self, text: str) -> None:
        self.lines.append(text)

    def text(self) -> str:
        head = [
            f"Beweis {self.cut.id} ({self.cut.mode}): "
            + ("grün" if self.ok else f"rot, {len(self.errors)} Abweichungen"),
            "Grundmengen: " + ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items())),
        ]
        body = [*head, "", *self.lines]
        if self.errors:
            body += ["", "Abweichungen:", *(f"  - {e}" for e in self.errors)]
        return "\n".join(body) + "\n"


# ------------------------------------------------------------------------------- Bäume


def tree_files(root: Path) -> dict[str, bytes]:
    """Jede Datei unter ``app/``, ``tools/``, ``tests/`` (ohne ``__pycache__`` und Punktordner)
    mit ihrem Inhalt."""
    found: dict[str, bytes] = {}
    for area in AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for full in base.rglob("*"):
            relative = full.relative_to(root)
            if any(p == "__pycache__" or p.startswith(".") for p in relative.parts[:-1]):
                continue
            if full.is_file():
                found[relative.as_posix()] = full.read_bytes()
    return dict(sorted(found.items()))


class Trees:
    """Beide Bäume mit Dateien, Quellen und Indizes."""

    def __init__(self, old_root: Path, new_root: Path, old_index: Index, new_index: Index) -> None:
        self.old_root = old_root
        self.new_root = new_root
        self.old_index = old_index
        self.new_index = new_index
        self.old_files = tree_files(old_root)
        self.new_files = tree_files(new_root)
        self.added = sorted(set(self.new_files) - set(self.old_files))
        self.removed = sorted(set(self.old_files) - set(self.new_files))
        self.changed = sorted(
            p
            for p in set(self.old_files) & set(self.new_files)
            if self.old_files[p] != self.new_files[p]
        )
        self._old: dict[str, Source] = {}
        self._new: dict[str, Source] = {}
        self._sites: dict[str, dict[tuple[str, int, int], PatchSite]] = {}

    def old(self, path: str) -> Source:
        if path not in self._old:
            self._old[path] = Source(path, self.old_files[path])
        return self._old[path]

    def new(self, path: str) -> Source:
        if path not in self._new:
            self._new[path] = Source(path, self.new_files[path])
        return self._new[path]

    def sites(self, which: str) -> dict[tuple[str, int, int], PatchSite]:
        if which not in self._sites:
            index = self.old_index if which == "old" else self.new_index
            self._sites[which] = {(s.path, s.line, s.col): s for s in index.patch_sites()}
        return self._sites[which]


class Mapping:
    """Abbildung alter Namen auf neue; je Modus überschrieben."""

    def ref(self, module: str, name: str) -> tuple[str, str]:
        return module, name

    def reader(self, module: str, qualname: str) -> tuple[str, str]:
        head, dot, rest = qualname.partition(".")
        new_module, new_head = self.ref(module, head)
        return new_module, f"{new_head}{dot}{rest}"

    def target(self, site: PatchSite, number: int) -> tuple[str, str, str | None]:
        """Das erwartete neue Ziel einer Patch-Stelle."""
        target = site.targets[number]
        if target.status == "module" and target.name is not None:
            module, name = self.ref(target.module, target.name)
            return target.status, module, name
        return target.status, target.module, target.name

    def expected_readers(self, trees: Trees, key: tuple[str, str]) -> set[str] | None:
        """Die erwartete neue Lesermenge des alten Namens ``key`` (``None``: Abbildung)."""
        return None

    def keys(self) -> Iterator[tuple[str, str]]:
        """Die alten Namen, deren Lesermenge zusätzlich zu den gepatchten geprüft wird."""
        return iter(())
