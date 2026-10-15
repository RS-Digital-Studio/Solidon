"""W5: Jeder Bezug auf ein Modul aus ``app/`` oder ``tools/`` löst sich statisch auf.

**Warum es diese Datei gibt** (Konzept Codestruktur 4.1, Plan Schritt 0, 2.5).
mypy prüft ``app/``, aber keine späten Importe in ``tools/`` und keine
Modulaliasse in Tests; ein Name, den ein Schnitt verschiebt, bricht dort erst,
wenn die Zeile läuft — in einem Werkzeug beim nächsten Release (RM-724). Geprüft
wird über ``tools/code_index.py`` in ``app/``, ``tools/`` und ``tests/``, auch in
Funktionen und unter ``TYPE_CHECKING``:

- jedes ``import app.…``/``import tools.…``, jedes ``from … import N`` und jedes
  ``importlib.import_module`` mit faltbarem Namen;
- jedes ``alias.N`` — gelesen, zugewiesen, gelöscht — mit einem Alias auf ein
  solches Modul; der Alias gilt je Funktion, Schatten werden beachtet;
- jedes ``getattr(alias, "N")`` ohne Vorgabe. Mit Vorgabe und ``hasattr`` fragt
  der Code nach einer Abwesenheit; das ist kein Fund.

Dieselben Regeln gelten in jedem Skript, das ein Test oder Werkzeug als Text an
``python -c`` gibt (``script:<art>``, CS-18, ein eigener Test): Ein verschobener
Name bräche dort erst im Kindprozess.

Lazy-Exporte, Literale eines ``__getattr__``, Stubs (``.pyi``) und ``type``
lösen auf; die Gegenproben dazu stehen in ``test_code_index.py``, die der
Skripte in ``test_code_scripts.py``.

**Scharf schalten** wie in ``test_patch_targets.py``: ``xfail(strict=True)`` mit
dem Paket, dessen Fix die Regel grün macht; ein XPASS ist rot, die Markierung
fällt im selben Commit.
"""

from __future__ import annotations

import pytest

from tools.code_index import Index, Unresolved, shared

#: Die Grundmenge aus dem Plan (2.5): mehr Importe als das.
LEAST_IMPORTS = 13000


def _index() -> Index:
    return shared()


def _report(found: list[Unresolved]) -> str:
    lines = [f"{len(found)} unaufgelöst:"]
    lines.extend(f"  {u.path}:{u.line}  [{u.kind}] {u.module}.{u.name}  {u.text}" for u in found)
    return "\n".join(lines)


def _of(*kinds: str) -> list[Unresolved]:
    return [item for item in _index().unresolved() if item.kind in kinds]


def test_the_ground_set_holds_every_import() -> None:
    """Ohne Importe wäre jede Regel grün, weil nichts geprüft wurde."""
    imports = _index().import_count()
    assert imports > LEAST_IMPORTS, imports


def test_every_import_of_an_own_module_resolves() -> None:
    """``import``, ``from … import`` und ``import_module`` mit faltbarem Namen."""
    found = _of("import", "from", "import_module")
    assert not found, _report(found)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="scharf, wenn P1 die 20 Zugriffe auf discover.unpatched_* und "
    "llm.unpatched_backends durch Fixtures ersetzt hat (Plan 1.6)",
)
def test_every_attribute_of_an_own_module_resolves() -> None:
    """``alias.N`` gelesen, zugewiesen oder gelöscht; eine Zuweisung auf einen fehlenden
    Namen legte ihn still an."""
    found = _of("attribute", "store", "delete")
    assert not found, _report(found)


def test_every_getattr_without_default_on_an_own_module_resolves() -> None:
    found = _of("getattr")
    assert not found, _report(found)


def test_every_reference_in_a_script_for_python_c_resolves() -> None:
    """Jede Art (``script:from``, ``script:attribute`` …) in einem Skript als Text (CS-18)."""
    found = [item for item in _index().unresolved() if item.kind.startswith("script:")]
    assert not found, _report(found)
