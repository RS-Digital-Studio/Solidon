"""Das Verschiebewerkzeug im Modulmodus (Plan Schritt 0, 2.7) an der Attrappe.

Positiv: Der Schnitt erzeugt den von Hand geschriebenen Sollbaum Byte für Byte, der Beweis ist
grün und nennt jede Definition; ``--check`` schreibt nichts; auf einem neueren Stand entsteht
derselbe Schnitt mit der neuen Änderung; ein angewandter Schnitt wird erkannt. Negativ: Jeder
unzulässige Schnitt wird **vor** dem Schreiben abgewiesen, mit Stelle und Ausweg — ein getrennter
``global``-Schreiber, gelesene Modulidentität, ein Kreis beim Import, eine Zeichenkette auf die
alte Datei, ein Patch auf eine Kopie der Quelle, ein gefaltetes Patch-Ziel, ein Modul als
Parameter; ein roter Beweis und ein Fehler beim Schreiben lassen den Baum unverändert.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names

EXPECTED = fx.changed_tree(fx.MODULE_OLD, fx.MODULE_NEW)
#: Eine Änderung, die ein anderer zwischen Planung und Schreiben macht.
FOREIGN = "\n# fremde Änderung\n".encode()


def _run(
    tmp_path: Path,
    files: dict[str, str] = fx.MODULE_OLD,
    cut_text: str = fx.MODULE_CUT,
    **options: object,
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut_text.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    result = move_names.run(move_cut.load(cut_file), root, work=work, cache=False, **options)  # type: ignore[arg-type]
    return root, result


def _expected_bytes(files: dict[str, str]) -> dict[str, bytes]:
    return {path: fx.text_of(text).encode("utf-8") for path, text in files.items()}


def test_the_module_cut_writes_the_hand_written_tree(tmp_path: Path) -> None:
    """M+1: Ziele, Paket-``__init__``, Leser in ``app/``, ``tools/`` und ``tests/``, Patch-Stellen
    als Text, über ``patch.object`` und als Dekorator, der Quelltextleser und die Namensliste —
    alles wie im Sollbaum, und der Beweis nennt jede der sechs Definitionen."""
    root, result = _run(tmp_path)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)
    assert result.proof is not None
    assert result.proof.counts["definitions"] == 6
    assert "Registerabzug byte-gleich" in result.proof.text()


def test_check_proves_without_writing(tmp_path: Path) -> None:
    root, result = _run(tmp_path, check=True)
    assert result.status == "proven", result.problems
    assert fx.tree_bytes(root) == _expected_bytes(fx.MODULE_OLD)


def test_a_red_proof_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Teilweise Ausgabe nach fehlgeschlagenem Beweis gibt es nicht."""
    original = move_names.prove

    def red(*args: object, **kwargs: object) -> move_names.Proof:
        proof = original(*args, **kwargs)  # type: ignore[arg-type]
        proof.error("Gegenprobe: rot gestellt")
        return proof

    monkeypatch.setattr(move_names, "prove", red)
    root, result = _run(tmp_path)
    assert result.status == "red"
    assert fx.tree_bytes(root) == _expected_bytes(fx.MODULE_OLD)


def test_a_failed_write_restores_every_written_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M−9: Bricht das Schreiben nach drei Dateien ab, stehen alle wieder auf ihren alten Bytes,
    neue Dateien sind fort, keine Zwischendatei bleibt liegen."""
    calls = {"n": 0}
    original = os.replace

    def failing(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        calls["n"] += 1
        if calls["n"] == 4:
            raise OSError("Gegenprobe: Schreibfehler")
        original(source, target)

    monkeypatch.setattr(move_names.os, "replace", failing)
    with pytest.raises(OSError, match="Gegenprobe"):
        _run(tmp_path)
    root = tmp_path / "tree"
    assert calls["n"] == 4
    assert fx.tree_bytes(root) == _expected_bytes(fx.MODULE_OLD)


def test_a_source_changed_after_planning_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M−9: Ändert jemand eine berührte Datei zwischen Planung und Schreiben, schreibt das
    Werkzeug nichts und sagt, dass der Schnitt neu zu erzeugen ist."""
    original = move_names.prove

    def meddle(*args: object, **kwargs: object) -> move_names.Proof:
        proof = original(*args, **kwargs)  # type: ignore[arg-type]
        consumer = tmp_path / "tree" / "app/core/consumer.py"
        consumer.write_bytes(consumer.read_bytes() + FOREIGN)
        return proof

    monkeypatch.setattr(move_names, "prove", meddle)
    with pytest.raises(RuntimeError, match="neu erzeugen"):
        _run(tmp_path)
    expected = _expected_bytes(fx.MODULE_OLD)
    expected["app/core/consumer.py"] += FOREIGN
    assert fx.tree_bytes(tmp_path / "tree") == expected


def test_the_cut_repeated_on_a_newer_state_carries_the_change(tmp_path: Path) -> None:
    """M+5: Hat ein anderer Zweig die Quelle inzwischen geändert, entsteht derselbe Schnitt mit
    genau dieser Änderung im Zielmodul — erzeugt, nicht aus alten Diffs zusammengeführt."""
    newer = fx.edit(fx.MODULE_OLD, "app/core/legacy.py", "+ read_count()", "+ read_count() + 2")
    root, result = _run(tmp_path, newer)
    assert result.status == "written", result.problems
    expected = fx.edit(
        EXPECTED, "app/core/legacy/rules.py", "+ state.read_count()", "+ state.read_count() + 2"
    )
    assert fx.tree_bytes(root) == _expected_bytes(expected)


def test_an_applied_cut_is_recognised_and_changes_nothing(tmp_path: Path) -> None:
    root, result = _run(tmp_path, EXPECTED)
    assert result.status == "applied", result.problems
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)


# ---------------------------------------------------------------------- abgewiesen


def _rejected(tmp_path: Path, files: dict[str, str], cut_text: str = fx.MODULE_CUT) -> str:
    root, result = _run(tmp_path, files, cut_text)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(files), "abgewiesen, aber geschrieben"
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


def test_a_separated_global_writer_is_rejected_with_its_partners(tmp_path: Path) -> None:
    """M−4: ``bump`` schreibt ``COUNT`` über ``global`` — in ein anderes Ziel als ``COUNT`` und
    dessen Leser ``read_count`` gelegt, hält der Schnitt an und nennt die gekoppelten Namen."""
    cut = fx.MODULE_CUT.replace(
        'definitions = ["logger", "COUNT", "bump", "read_count"]',
        'definitions = ["logger", "COUNT", "read_count"]',
    ).replace('definitions = ["_adjust", "Rule"]', 'definitions = ["bump", "_adjust", "Rule"]')
    message = _rejected(tmp_path, fx.MODULE_OLD, cut)
    assert "'COUNT' über global" in message
    assert "bump" in message and "read_count" in message and "app.core.legacy.state" in message


def test_reading_the_module_identity_needs_a_declaration(tmp_path: Path) -> None:
    cut = fx.MODULE_CUT.replace(
        '[[identity]]\nname = "logger"\n', '[[identity_]]\nname = "logger"\n'
    )
    with pytest.raises(move_cut.CutError):
        _rejected(tmp_path, fx.MODULE_OLD, cut)
    start = cut.index("[[identity_]]")
    end = cut.index("[[name_lists]]")
    message = _rejected(tmp_path, fx.MODULE_OLD, cut[:start] + cut[end:])
    assert "Identität des Moduls (__name__)" in message


def test_a_cycle_read_at_import_time_is_rejected(tmp_path: Path) -> None:
    """``Rule`` erbt beim Import von einer Klasse aus ``state``, und ``state`` liest ``Rule`` —
    in zwei Zielen ein Kreis, der beim Import bricht."""
    files = fx.edit(
        fx.MODULE_OLD,
        "app/core/legacy.py",
        "class Rule:\n",
        "class Base:\n    pass\n\n\nclass Rule(Base):\n",
    )
    files = fx.edit(
        files,
        "app/core/legacy.py",
        "    return COUNT\n",
        "    return COUNT + len(Rule.__doc__ or '')\n",
    )
    cut = fx.MODULE_CUT.replace(
        'definitions = ["logger", "COUNT", "bump", "read_count"]',
        'definitions = ["logger", "COUNT", "bump", "read_count", "Base"]',
    )
    message = _rejected(tmp_path, files, cut)
    assert "beim Import" in message and "Base" in message


def test_an_undeclared_string_on_the_old_file_is_rejected(tmp_path: Path) -> None:
    files = fx.MODULE_OLD | {
        "tests/test_files.py": 'NAMES = ("app/core/legacy.py", "app.core.legacy.bump")\n'
    }
    message = _rejected(tmp_path, files)
    assert "tests/test_files.py:1" in message and "'app/core/legacy.py'" in message
    assert "'app.core.legacy.bump'" in message


def test_a_patch_on_a_copy_the_source_holds_is_rejected(tmp_path: Path) -> None:
    files = fx.MODULE_OLD | {
        "tests/test_copy.py": (
            "def test_copy(monkeypatch):\n"
            '    monkeypatch.setattr("app.core.legacy.Shape", object)\n'
        )
    }
    message = _rejected(tmp_path, files)
    assert "Kopie app.core.legacy.Shape" in message and "copies" in message


def test_a_folded_patch_target_is_rejected(tmp_path: Path) -> None:
    files = fx.MODULE_OLD | {
        "tests/test_folded.py": (
            "from app.core import legacy\n\n\n"
            "def test_folded(monkeypatch):\n"
            '    for name in ("bump", "read_count"):\n'
            "        monkeypatch.setattr(legacy, name, None)\n"
        )
    }
    message = _rejected(tmp_path, files)
    assert "tests/test_folded.py:6" in message and "gefaltetem Ziel" in message


def test_a_module_reached_through_a_parameter_is_rejected(tmp_path: Path) -> None:
    files = fx.MODULE_OLD | {
        "tests/test_fixture.py": (
            "import importlib\n\nimport pytest\n\n\n"
            "@pytest.fixture\n"
            "def mod():\n"
            '    return importlib.import_module("app.core.legacy")\n\n\n'
            "def test_through(mod):\n"
            "    assert mod.read_count() == 0\n"
        )
    }
    message = _rejected(tmp_path, files)
    assert "tests/test_fixture.py:12" in message
    assert "nicht über einen Import oder importlib.import_module gebunden" in message


@pytest.mark.parametrize(
    ("label", "head", "line"),
    [
        ("reload", "import importlib\n\n", "importlib.reload(legacy)"),
        ("dir", "", 'assert "Rule" in dir(legacy)'),
        ("vars", "", 'assert all(not name.startswith("tmp") for name in vars(legacy))'),
        ("getsource", "import inspect\n\n", 'assert "def bump" in inspect.getsource(legacy)'),
        ("namensraum", "", 'assert "bump" in legacy.__dict__'),
        ("offener-name", "", 'assert getattr(legacy, "bu" + "mp".strip(" ")) is not None'),
        ("als-argument", "", "assert check(legacy)"),
        ("über-alias", "", "alias = legacy\n    assert alias is not None"),
    ],
)
def test_the_source_read_as_a_value_is_rejected(
    tmp_path: Path, label: str, head: str, line: str
) -> None:
    """RM-M5: Ein Modul als Wert (``importlib.reload``, ``dir``, ``vars``,
    ``inspect.getsource``, ``__dict__``, ``getattr`` mit offenem Namen, als Argument) sähe nach
    dem Schnitt das Paket ohne Namen — abgewiesen, mit Ausweg, statt still zu schreiben."""
    text = (
        f"{head}from app.core import legacy\n\n\n"
        "def check(module: object) -> bool:\n    return module is not None\n\n\n"
        f"def test_value():\n    {line}\n"
    )
    message = _rejected(tmp_path, fx.MODULE_OLD | {"tests/test_value.py": text})
    assert "tests/test_value.py:" in message and "als Wert" in message, (label, message)


@pytest.mark.parametrize(
    ("label", "change", "where"),
    [
        (
            "anweisung-ohne-bindung",
            (
                "logger = logging.getLogger(__name__)\n",
                "logger = logging.getLogger(__name__)\nprint(logger)\n",
            ),
            "Anweisung ohne Bindung",
        ),
        (
            "import-zwischen-definitionen",
            ("\n\ndef read_count", "\n\nimport os\n\n\ndef read_count"),
            "Import zwischen den Definitionen",
        ),
        ("dunder-all", ("COUNT = 0\n", 'COUNT = 0\n__all__ = ["bump"]\n'), "__all__"),
        (
            "nicht-erklärte-definition",
            ("COUNT = 0\n", "COUNT = 0\nLIMIT = 3\n"),
            "LIMIT in keinem Ziel",
        ),
    ],
)
def test_a_source_the_cut_cannot_place_is_rejected(
    tmp_path: Path, label: str, change: tuple[str, str], where: str
) -> None:
    files = fx.edit(fx.MODULE_OLD, "app/core/legacy.py", *change)
    assert where in _rejected(tmp_path, files), label


@pytest.mark.parametrize(
    ("label", "old", "new", "where"),
    [
        (
            "unbenutzte-namensliste",
            'value = "app.core.legacy"',
            'value = "app.core.fehlt"',
            "steht nicht in",
        ),
        (
            "unbenutzter-leser",
            'scope = "test_source"',
            'scope = "test_paths"',
            "liest nichts die Quelle",
        ),
        (
            "fehlende-definition",
            '"read_count"]',
            '"read_count", "gibt_es_nicht"]',
            "nicht auf Modulebene",
        ),
    ],
)
def test_a_declaration_that_hits_nothing_is_rejected(
    tmp_path: Path, label: str, old: str, new: str, where: str
) -> None:
    assert old in fx.MODULE_CUT, label
    assert where in _rejected(tmp_path, fx.MODULE_OLD, fx.MODULE_CUT.replace(old, new)), label


def test_a_definition_in_two_targets_is_a_cut_error(tmp_path: Path) -> None:
    cut = fx.MODULE_CUT.replace(
        'definitions = ["_adjust", "Rule"]', 'definitions = ["_adjust", "Rule", "bump"]'
    )
    (tmp_path / "cut.toml").write_text(cut, encoding="utf-8")
    with pytest.raises(move_cut.CutError, match="'bump' steht in"):
        move_cut.load(tmp_path / "cut.toml")
