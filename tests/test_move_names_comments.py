"""Kommentare und Importe, die ein Schnitt nicht still verlieren darf (Review 1 über Paket M,
RM-M9 und RM-M10).

Modulmodus: Ein freier Kommentar vor einer Definition und einer hinter der letzten Anweisung
wandern mit (Planer) und zählen im Beweis; ein Kommentar im Importkopf der Quelle hat kein Ziel
und hält den Schnitt an. Jeder Import der Quelle landet in einem Ziel — einer, den keine
Definition liest (ein Seiteneffekt), hält den Schnitt an; ebenso ein Leser, der die Quelle nur um
ihrer Wirkung willen importiert. Komponentenmodus: In einer Leserdatei entfallen nur Importe von
Wirt oder Komponente, und nur, wenn sie vorher gelesen wurden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names, move_proof

SOURCE = "app/core/legacy.py"
STATE = "app/core/legacy/state.py"
RULES = "app/core/legacy/rules.py"
EXPECTED = fx.changed_tree(fx.MODULE_OLD, fx.MODULE_NEW)
FREE = "# Freier Kommentar: der Zähler beginnt bei null.\n\n"
TRAILING = "\n\n\n# Schluss: hier endet die alte Datei.\n"
SIDE = '"""Seiteneffekt beim Import."""\n\nimport os\n\nos.environ.setdefault("LEGACY_SIDE", "1")\n'


def _commented() -> tuple[dict[str, str], dict[str, str]]:
    old = fx.edit(fx.MODULE_OLD, SOURCE, "COUNT = 0\n", FREE + "COUNT = 0\n")
    old = fx.edit(
        old, SOURCE, "        return _adjust(hidden)\n", "        return _adjust(hidden)" + TRAILING
    )
    new = fx.edit(EXPECTED, STATE, "COUNT = 0\n", FREE + "COUNT = 0\n")
    new = fx.edit(
        new, RULES, "        return adjust(hidden)\n", "        return adjust(hidden)" + TRAILING
    )
    return old, new


COMMENTED_OLD, COMMENTED_NEW = _commented()


def _run(
    tmp_path: Path, files: dict[str, str], cut: str = fx.MODULE_CUT
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _prove(
    tmp_path: Path, old: dict[str, str], new: dict[str, str], cut: str = fx.MODULE_CUT
) -> move_proof.Proof:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut, encoding="utf-8")
    return move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", new),
    )


def _rejected(tmp_path: Path, files: dict[str, str], cut: str = fx.MODULE_CUT) -> str:
    root, result = _run(tmp_path, files, cut)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in files.items()}
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


# ------------------------------------------------------------------------------ Kommentare


def test_free_and_trailing_comments_travel_with_their_definitions(tmp_path: Path) -> None:
    """RM-M9: Der Planer nimmt die ganze Spanne mit — der Beweis vergleicht sie auch."""
    root, result = _run(tmp_path, COMMENTED_OLD)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == {
        p: fx.text_of(t).encode("utf-8") for p, t in COMMENTED_NEW.items()
    }


@pytest.mark.parametrize(
    ("label", "path", "old", "new"),
    [
        ("freier-kommentar", STATE, FREE + "COUNT = 0\n", "COUNT = 0\n"),
        ("kommentar-am-ende", RULES, TRAILING, "\n"),
    ],
)
def test_a_lost_free_comment_is_red(
    tmp_path: Path, label: str, path: str, old: str, new: str
) -> None:
    """RM-M9: Ein freier Kommentar (durch eine Leerzeile von der Definition getrennt) und einer
    hinter der letzten Anweisung, im Ziel verloren — der Beweis ist rot."""
    proof = _prove(tmp_path, COMMENTED_OLD, fx.edit(COMMENTED_NEW, path, old, new))
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any("Kommentar verloren oder neu" in error for error in proof.errors), proof.errors


def test_a_comment_in_the_head_of_the_source_stops_the_cut(tmp_path: Path) -> None:
    """Ein Kommentar im Importkopf der Quelle hätte kein Ziel: Der Planer hält an, und der
    Beweis eines Baums ohne ihn ist rot."""
    old = fx.edit(fx.MODULE_OLD, SOURCE, "import logging\n", "import logging  # Protokoll\n")
    assert "app/core/legacy.py:5: Kommentar im Kopf der Quelle" in _rejected(tmp_path / "a", old)
    proof = _prove(tmp_path / "b", old, EXPECTED)
    assert any("app/core/legacy.py:5: Kommentar im Kopf der Quelle" in e for e in proof.errors)


# ------------------------------------------------------------------------------ Importe


def test_an_import_of_the_source_that_no_definition_reads_stops_the_cut(tmp_path: Path) -> None:
    """RM-M10: Ein Seiteneffekt-Import der Quelle fiele beim Planen still weg; jetzt hält der
    Schnitt an, und ein Baum, in dem er in keinem Ziel steht, ist rot."""
    old = fx.edit(
        fx.MODULE_OLD | {"app/core/side.py": SIDE},
        SOURCE,
        "import logging\n",
        "import logging\n\nimport app.core.side\n",
    )
    message = _rejected(tmp_path / "a", old)
    assert "app/core/legacy.py:7: Import import app.core.side liest keine Definition" in message
    proof = _prove(tmp_path / "b", old, EXPECTED | {"app/core/side.py": SIDE})
    assert not proof.ok, proof.text()
    assert any("import app.core.side der Quelle steht in keinem Ziel" in e for e in proof.errors)


def test_a_reader_importing_the_source_only_for_its_effect_stops_the_cut(tmp_path: Path) -> None:
    """RM-M10: ``import app.core.legacy`` ohne Leser lüde nach dem Schnitt nur das Paket — die
    Wirkung der Definitionen (Register) fiele still weg."""
    reader = '"""Lädt die Operationen."""\n\nimport app.core.legacy  # noqa: F401\n'
    message = _rejected(tmp_path, fx.MODULE_OLD | {"tests/test_side.py": reader})
    assert "tests/test_side.py:3: importiert app.core.legacy nur um der Wirkung willen" in message


COMPONENT_EXPECTED = fx.changed_tree(fx.COMPONENT_OLD, fx.COMPONENT_NEW)
TOOLS = "app/ui/board_tools.py"


def test_a_component_reader_loses_only_imports_of_host_or_component(tmp_path: Path) -> None:
    """RM-M10: In einer Leserdatei entfällt im Komponentenmodus nur ein Import von Wirt oder
    Komponente, der vorher gelesen wurde — nicht ein Seiteneffekt-Import samt ``noqa``."""
    old = fx.edit(
        fx.COMPONENT_OLD | {"app/ui/side.py": SIDE},
        TOOLS,
        "from app.ui.toast import Toast\n",
        "from app.ui import side  # noqa: F401\nfrom app.ui.toast import Toast\n",
    )
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(fx.COMPONENT_CUT, encoding="utf-8")
    proof = move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", COMPONENT_EXPECTED | {"app/ui/side.py": SIDE}),
    )
    assert not proof.ok, proof.text()
    assert any(
        "Import from app.ui import side entfernt" in error and TOOLS in error
        for error in proof.errors
    ), proof.errors
