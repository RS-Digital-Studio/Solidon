"""Das Verschiebewerkzeug im Modulmodus an Randformen (Plan Schritt 0, 2.7 Punkt 4).

Leser über ``importlib.import_module`` (gebunden in einer Funktion, auf Modulebene und als
Ausdruck), ``import … as``, ein Import unter ``TYPE_CHECKING``, ein Patch auf eine Klasse über den
Pfad als Text und über das Klassenobjekt, ``hasattr``, eine Zeichenkette, die erklärt bleibt, und
eine überladene Funktion in der Quelle: Der Schnitt erzeugt den von Hand geschriebenen Sollbaum,
jeder Mutant ist rot, und was sich nicht sicher umstellen lässt, wird vor dem Schreiben
abgewiesen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names, move_proof

FORMS = "tests/test_forms.py"
STATE = "app/core/legacy/state.py"


def _run(
    tmp_path: Path, files: dict[str, str] = fx.FORMS_OLD, cut_text: str = fx.FORMS_CUT
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut_text.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _bytes(files: dict[str, str]) -> dict[str, bytes]:
    return {path: fx.text_of(text).encode("utf-8") for path, text in files.items()}


def _prove(tmp_path: Path, new_files: dict[str, str]) -> move_proof.Proof:
    old = fx.write_tree(tmp_path / "old", fx.FORMS_OLD)
    new = fx.write_tree(tmp_path / "new", new_files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(fx.FORMS_CUT, encoding="utf-8")
    return move_proof.prove(move_cut.load(cut_file), old, new)


def test_the_forms_cut_writes_the_hand_written_tree(tmp_path: Path) -> None:
    root, result = _run(tmp_path)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _bytes(fx.FORMS_NEW)
    assert result.proof is not None
    assert result.proof.counts["definitions"] == 9  # sechs, dazu pick dreifach


def test_the_proof_names_each_form(tmp_path: Path) -> None:
    proof = _prove(tmp_path, fx.FORMS_NEW)
    assert proof.ok, proof.text()
    text = proof.text()
    for expected in (
        "Definition app.core.legacy:pick → app.core.legacy.state:pick",
        'importlib.import_module("app.core.legacy").read_count → '
        'importlib.import_module("app.core.legacy.state").read_count',
        'hasattr(lg, "bump") → hasattr(state, "bump")',
        'entfällt EVALUATION = importlib.import_module("app.core.legacy")',
        "Patch monkeypatch.setattr('app.core.legacy.Rule.apply', lambda self, hidden: 1) → "
        "monkeypatch.setattr('app.core.legacy.rules.Rule.apply', lambda self, hidden: 1)",
    ):
        assert expected in text, expected


def _mutants() -> list[tuple[str, dict[str, str], str]]:
    new = fx.FORMS_NEW
    return [
        (
            "bleibende-zeichenkette-geändert",
            fx.edit(
                new, FORMS, 'KNOWN = ("app.core.legacy",)', 'KNOWN = ("app.core.legacy.state",)'
            ),
            FORMS,
        ),
        (
            "klassenpfad-am-alten-ziel",
            fx.edit(
                new, FORMS, '"app.core.legacy.rules.Rule.apply"', '"app.core.legacy.Rule.apply"'
            ),
            FORMS,
        ),
        (
            "hasattr-falsches-modul",
            fx.edit(new, FORMS, 'hasattr(state, "bump")', 'hasattr(rules, "bump")'),
            FORMS,
        ),
        (
            "import-module-falsches-ziel",
            fx.edit(
                new,
                FORMS,
                '"app.core.legacy.state").read_count',
                '"app.core.legacy.rules").read_count',
            ),
            FORMS,
        ),
        (
            "typimport-zur-laufzeit",
            fx.edit(
                fx.edit(
                    new,
                    FORMS,
                    "if TYPE_CHECKING:\n    from app.core.legacy.rules import Rule\n",
                    "",
                ),
                FORMS,
                "from app.core.legacy import rules, state\n",
                "from app.core.legacy import rules, state\n"
                "from app.core.legacy.rules import Rule\n",
            ),
            FORMS,
        ),
        (
            "überladung-verloren",
            fx.edit(new, STATE, "@overload\ndef pick(value: str) -> str: ...\n\n\n", ""),
            STATE,
        ),
        (
            "überladung-vertauscht",
            fx.edit(
                fx.edit(
                    new, STATE, "def pick(value: int) -> int: ...", "def pick(value: X) -> X: ..."
                ),
                STATE,
                "def pick(value: str) -> str: ...",
                "def pick(value: int) -> int: ...",
            ),
            STATE,
        ),
    ]


@pytest.mark.parametrize(("label", "files", "where"), _mutants(), ids=[m[0] for m in _mutants()])
def test_every_mutant_of_the_forms_cut_is_red(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    proof = _prove(tmp_path, files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


def _rejected(tmp_path: Path, files: dict[str, str], cut_text: str = fx.FORMS_CUT) -> str:
    root, result = _run(tmp_path, files, cut_text)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _bytes(files), "abgewiesen, aber geschrieben"
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


def test_a_string_on_the_old_module_needs_a_declaration(tmp_path: Path) -> None:
    """Eine Zeichenkette gleich dem alten Modul (``"app.core.legacy"``) bleibt nicht still stehen:
    ohne Erklärung hält der Schnitt an."""
    start = fx.FORMS_CUT.index('\n[[name_lists]]\npath = "tests/test_forms.py"')
    message = _rejected(tmp_path, fx.FORMS_OLD, fx.FORMS_CUT[:start] + "\n")
    assert "tests/test_forms.py:14: Zeichenkette 'app.core.legacy'" in message


@pytest.mark.parametrize(
    ("label", "text", "where"),
    [
        (
            "sys-modules",
            "import sys\n\n\ndef test_loaded():\n"
            '    assert sys.modules["app.core.legacy"].read_count() == 0\n',
            "sys.modules['app.core.legacy']",
        ),
        (
            "pfad-mit-backslash",
            'PATH = "app\\\\core\\\\legacy.py"\n',
            "Zeichenkette 'app\\\\core\\\\legacy.py'",
        ),
    ],
)
def test_a_form_that_cannot_follow_is_rejected(
    tmp_path: Path, label: str, text: str, where: str
) -> None:
    files = fx.FORMS_OLD | {"tests/test_extra.py": text}
    assert where in _rejected(tmp_path, files), label
