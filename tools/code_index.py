"""Statischer Auflöser für Namen, Importe und Patch-Ziele über ``app/``, ``tools/``, ``tests/``.

Gebaut für Schritt 0 der Codestruktur (``konzepte/konzept-codestruktur-2026-10.md``, 4.1): Die
Wächter W2 (``tests/test_patch_targets.py``) und W5 (``tests/test_import_resolution.py``) und das
Verschiebewerkzeug ``tools/move_names.py`` fragen ihn, statt je eine eigene Teilauflösung zu
bauen. Er liest nur Quelltext (``ast``), importiert nichts aus dem Baum und braucht nichts außer
der Standardbibliothek.

Dieser Stand ist das Gerüst: Typen und Signaturen stehen fest, die Rümpfe folgen.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]

#: Bereiche, deren Module der Index als Ziele prüft (W2 und W5).
INDEXED = ("app", "tools")
#: Bereiche, deren Dateien er liest; ``tests`` liefert Patch-Stellen und Importe.
AREAS = ("app", "tools", "tests")


class Val(NamedTuple):
    """Was ein Ausdruck statisch bedeutet.

    ``kind`` ist eines von ``module`` (Modul oder Paket unter ``app``, ``tools``, ``tests``;
    ``ref`` ist der Punktname), ``ext`` (Modul oder Name außerhalb, etwa ``numpy.linalg``),
    ``def`` und ``class`` (``ref`` ist ``modul:qualname``), ``const`` (``data`` ist der Wert),
    ``seq`` und ``map`` (``data`` sind die Elemente bzw. Paare), ``obj`` (ein Objekt, das kein
    Modul ist), ``missing`` (ein Modul oder Name in den eigenen Bereichen, den es nicht gibt;
    ``data`` ist ``(modul, name)``) und ``unknown`` (statisch nicht auflösbar, ``ref`` nennt den
    Grund).
    """

    kind: str
    ref: str
    data: object = None


class PatchTarget(NamedTuple):
    """Ein aufgelöstes Ziel einer Patch-Stelle, je Zeile der Konstantenfaltung eines.

    ``status``: ``module`` (Modul aus ``app``/``tools``), ``tests`` (Testmodul), ``foreign``
    (fremdes Modul oder Objekt darin), ``object`` (kein Modul), ``missing`` (Modulpfad in den
    eigenen Bereichen, den es nicht gibt) oder ``unknown`` (statisch nicht auflösbar).
    ``module`` ist der Punktname des Zielmoduls (bei ``unknown``/``object`` der Grund),
    ``name`` der gefaltete Attributname oder ``None``, wenn er sich nicht falten ließ.
    """

    status: str
    module: str
    name: str | None


class PatchSite(NamedTuple):
    """Eine Patch-Stelle in ``tests/``: ``monkeypatch.setattr``/``delattr`` (auch mit Pfad als
    Text), ``mock.patch`` (Aufruf, Dekorator, ``with``) und ``mock.patch.object``."""

    path: str
    line: int
    col: int
    scope: str
    form: str
    text: str
    raising: bool | None
    targets: tuple[PatchTarget, ...]


class Reader(NamedTuple):
    """Wer ``M.N`` zur Aufrufzeit erreicht: ``kind`` ist ``global`` (Funktion in ``M``, die ``N``
    als Global liest), ``attribute`` (``M.N`` über einen Modulalias), ``getattr`` oder
    ``import`` (später ``from M import N`` in einer Funktion)."""

    module: str
    qualname: str
    path: str
    line: int
    kind: str


class HeadCopy(NamedTuple):
    """Eine Kopfkopie: ``from M import N`` (``kind == "from"``) oder ``x = M.N``
    (``kind == "assign"``) zur Importzeit in ``app/`` oder ``tools/``, außerhalb von
    ``TYPE_CHECKING``. ``chain`` führt von ``(M, N)`` über Rückexporte bis zum Ursprung."""

    holder: str
    path: str
    line: int
    bound: str
    module: str
    name: str
    chain: tuple[tuple[str, str], ...]
    kind: str


class Reference(NamedTuple):
    """Ein aufgelöster Bezug auf ``module.name`` an einer Stelle des Baums.

    ``kind``: ``import`` (``import M``, dann ist ``name`` leer), ``from``, ``import_module``,
    ``attribute``, ``store``, ``delete``, ``getattr`` oder ``patch``. ``runtime`` sagt, ob der
    Bezug zur Aufrufzeit (in einer Funktion) läuft, ``checking``, ob er unter ``TYPE_CHECKING``
    steht.
    """

    path: str
    line: int
    col: int
    kind: str
    module: str
    name: str
    runtime: bool
    checking: bool


class Unresolved(NamedTuple):
    """Ein Bezug auf ``app``/``tools``, der sich nicht auflöst (W5)."""

    path: str
    line: int
    col: int
    kind: str
    module: str
    name: str
    text: str


class Finding(NamedTuple):
    """Ein Verstoß gegen eine Regel von W2 (``rule`` ist ``a`` bis ``e``, Plan 2.2)."""

    rule: str
    path: str
    line: int
    module: str
    name: str
    detail: str


class Index:
    """Der Index über einen Baum; gebaut mit :meth:`build`."""

    root: Path

    @classmethod
    def build(cls, root: Path | None = None, *, cache: bool = True) -> Index:
        """Liest ``app/``, ``tools/`` und ``tests/`` unter ``root`` (Vorgabe: dieses
        Repository); ``cache`` hält die Auszüge je Datei nach Inhaltshash vor."""
        raise NotImplementedError

    def resolve(self, path: str | Path, node: ast.AST) -> frozenset[Val]:
        """Was der Ausdruck ``node`` aus der Datei ``path`` statisch bedeutet. ``node`` stammt
        aus einem ``ast.parse`` derselben Datei; er wird über Lage und Typ gefunden."""
        raise NotImplementedError

    def patch_sites(self) -> tuple[PatchSite, ...]:
        """Alle Patch-Stellen in ``tests/``, nach Pfad und Zeile sortiert."""
        raise NotImplementedError

    def readers(self, module: str, name: str) -> tuple[Reader, ...]:
        """Die Lesermenge von ``module.name`` in ``app/`` und ``tools/``, sortiert."""
        raise NotImplementedError

    def head_copies(self) -> tuple[HeadCopy, ...]:
        """Alle Kopfkopien in ``app/`` und ``tools/``, die kein Modul binden."""
        raise NotImplementedError

    def unresolved(self) -> tuple[Unresolved, ...]:
        """Alle Bezüge auf ``app``/``tools``, die sich nicht auflösen (W5)."""
        raise NotImplementedError

    def reach_dump(self) -> dict[tuple[str, str], tuple[str, ...]]:
        """Je gepatchtem ``(M, N)`` die sortierte Lesermenge als ``modul:qualname``."""
        raise NotImplementedError

    def references(self, module: str, name: str) -> tuple[Reference, ...]:
        """Jeder aufgelöste Bezug auf ``module.name`` in ``app/``, ``tools/`` und ``tests/``."""
        raise NotImplementedError

    def patched_names(self) -> frozenset[tuple[str, str]]:
        """Die ``(M, N)`` aus ``app``/``tools``, die eine Patch-Stelle trifft."""
        raise NotImplementedError

    def patch_findings(self) -> dict[str, tuple[Finding, ...]]:
        """Die Verstöße gegen W2, je Regel ``a`` bis ``e`` (Plan 2.2)."""
        raise NotImplementedError

    def exists(self, module: str, name: str, *, checking: bool = False) -> bool:
        """Ob ``module.name`` zur Laufzeit existiert (mit ``checking`` auch nur für die
        Typprüfung)."""
        raise NotImplementedError
