"""Das Verschiebewerkzeug im Modus ``copies`` (Plan Schritt 0, 2.7 Punkt 7; E1) an der Attrappe.

Positiv: Der Schnitt erzeugt den von Hand geschriebenen Sollbaum Byte für Byte — Kopfkopien als
Import, mit ``as``, als Zuweisung und als Kopie einer Kopie werden Modulzugriffe, ein träger
Export bleibt der Leseweg, Patches auf Kopien zielen aufs Original, auch über ein mit
``importlib.import_module`` gebundenes Modul; der Beweis rechnet je Familie, wen das Original
danach erreicht. Auf neuerem Stand entsteht derselbe Schnitt, ein angewandter wird erkannt.
Gegenproben: Jeder Mutant des Sollbaums ist rot, und jeder unzulässige Schnitt wird vor dem
Schreiben abgewiesen, mit Stelle und Ausweg.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_copies, move_cut, move_names, move_proof
from tools.code_index import Index

EXPECTED = fx.changed_tree(fx.COPIES_OLD, fx.COPIES_NEW)
CONSUMER = "app/core/consumer.py"
TESTS = "tests/test_engine.py"


def _run(
    tmp_path: Path, files: dict[str, str] = fx.COPIES_OLD, cut_text: str = fx.COPIES_CUT
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut_text.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _expected_bytes(files: dict[str, str]) -> dict[str, bytes]:
    return {path: fx.text_of(text).encode("utf-8") for path, text in files.items()}


def _prove(tmp_path: Path, new_files: dict[str, str]) -> move_proof.Proof:
    old = fx.write_tree(tmp_path / "old", fx.COPIES_OLD)
    new = fx.write_tree(tmp_path / "new", new_files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(fx.COPIES_CUT, encoding="utf-8")
    return move_proof.prove(move_cut.load(cut_file), old, new)


# ------------------------------------------------------------------------------ positiv


def test_the_copies_cut_writes_the_hand_written_tree(tmp_path: Path) -> None:
    """C+1 bis C+3: sechs Kopien in vier Familien, fünf Patch-Stellen auf Kopien."""
    root, result = _run(tmp_path)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)
    assert result.proof is not None
    counts = result.proof.counts
    assert counts["copies"] == 6
    assert counts["patches_retargeted"] == 5
    assert counts["changed_files"] == 4
    assert counts["registry_bytes"] > 0


def test_the_proof_names_what_each_retargeted_patch_reaches(tmp_path: Path) -> None:
    """Plan 4: Ein Patch auf das Original erreicht danach absichtlich mehr Leser — das Protokoll
    nennt sie je Patch-Stelle, die Lesermenge je Familie ist genau die Vereinigung."""
    proof = _prove(tmp_path, EXPECTED)
    assert proof.ok, proof.text()
    text = proof.text()
    assert (
        "Patch tests/test_engine.py:11 auf app.core.consumer.operation → app.core.engine.compute: "
        "erreicht vorher 1, nachher 5, dazu app.core.consumer:late, app.core.engine:direct, "
        "app.core.relay:relay, tools.engine_tool:read"
    ) in text
    assert (
        "Leser app.core.kit.measure.measure → app.core.kit.measure.measure: 1 gleich "
        "(app.core.consumer:size)"
    ) in text
    assert "liest app.core.kit.measure; Patches → app.core.kit.measure.measure" in text


def test_the_cut_repeated_on_a_newer_state_carries_the_change(tmp_path: Path) -> None:
    """C+4: Hat sich das Original inzwischen geändert, bleibt es unberührt, der Schnitt ist
    derselbe."""
    newer = fx.edit(fx.COPIES_OLD, "app/core/engine.py", "return value + 1", "return value + 2")
    root, result = _run(tmp_path, newer)
    assert result.status == "written", result.problems
    expected = fx.changed_tree(newer, fx.COPIES_NEW)
    assert fx.tree_bytes(root) == _expected_bytes(expected)


def test_an_applied_copies_cut_is_recognised(tmp_path: Path) -> None:
    root, result = _run(tmp_path, EXPECTED)
    assert result.status == "applied", result.problems
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)


def test_list_copies_proposes_the_originals_w2_flags(tmp_path: Path) -> None:
    """``--list-copies`` schlägt genau die Originale vor, deren Kopien W2 c) beanstandet — hier
    ``compute``, den die Tests am Original patchen; das Ergebnis ist eine gültige Liste."""
    root = fx.write_tree(tmp_path / "tree", fx.COPIES_OLD)
    found = move_copies.list_copies(Index.build(root, cache=False))
    assert found == [("app.core.engine", "compute")]
    text = 'schema_version = 1\nid = "x"\nmode = "copies"\n\n' + move_copies.bindings_toml(found)
    cut = move_cut.parse(tomllib.loads(text), tmp_path / "cut.toml")
    assert [(b.module, b.name) for b in cut.bindings] == found


def test_a_hidden_original_is_read_through_its_lazy_package(tmp_path: Path) -> None:
    """``app.core.kit.measure`` liegt hinter dem gleichnamigen trägen Export: Ein Halter, der
    direkt daraus importiert, liest danach über das träge Paket, und ein Patch auf eine Kopie
    trifft das Original über ``importlib.import_module`` — ein Import bände die Funktion."""
    holder = (
        '"""Ein Halter am verdeckten Modul."""\n\nfrom app.core.kit.measure import measure\n\n\n'
        "def gauge(text: str) -> int:\n    return measure(text)\n"
    )
    helper = "def helper():\n    import importlib\n\n    return importlib\n\n\n"
    patch = (
        f"from app.core import consumer\n\n\n{helper}def test_kit(monkeypatch):\n"
        '    monkeypatch.setattr(consumer, "measure", len)\n'
    )
    files = fx.COPIES_OLD | {"app/core/gauge.py": holder, "tests/test_kit.py": patch}
    root, result = _run(tmp_path, files)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert (root / "app/core/gauge.py").read_text(encoding="utf-8") == (
        '"""Ein Halter am verdeckten Modul."""\n\nfrom app.core import kit\n\n\n'
        "def gauge(text: str) -> int:\n    return kit.measure(text)\n"
    )
    assert (root / "tests/test_kit.py").read_text(encoding="utf-8") == (
        f"import importlib\n\n\n{helper}def test_kit(monkeypatch):\n"
        '    monkeypatch.setattr(importlib.import_module("app.core.kit.measure"), "measure", len)\n'
    )


TOOL = '''\
"""Ein Werkzeug, das sich selbst auf den Pfad legt."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.engine import (  # noqa: E402
    LIMIT,
    scale,
)


def double(value: int) -> int:
    return scale(value) + LIMIT
'''


def test_the_comment_after_the_bracket_stays_with_each_import(tmp_path: Path) -> None:
    """``from … import (  # noqa: E402`` hinter dem Pfadaufbau eines Werkzeugs: Der Kommentar
    gilt der Anweisung und steht danach an jeder, die aus ihr wird."""
    root, result = _run(tmp_path, fx.COPIES_OLD | {"tools/doubler.py": TOOL})
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    text = (root / "tools/doubler.py").read_text(encoding="utf-8")
    assert (
        "from app.core import engine  # noqa: E402\n"
        "from app.core.engine import LIMIT  # noqa: E402\n"
    ) in text
    assert "    return engine.scale(value) + LIMIT\n" in text


def test_a_comment_between_import_entries_is_rejected(tmp_path: Path) -> None:
    """Ein Kommentar an einem Eintrag ginge beim Umbau verloren: abgewiesen, mit Ausweg."""
    files = fx.COPIES_OLD | {
        "tools/doubler.py": TOOL.replace("    scale,\n", "    scale,  # verdoppelt\n")
    }
    assert "Kommentar in einer mehrzeiligen Importanweisung" in _rejected(tmp_path, files)


def _aliased(name: str) -> str:
    return fx.COPIES_CUT.replace(
        'mode = "copies"\n',
        'mode = "copies"\n\n[[aliases]]\npath = "app/core/consumer.py"\n'
        f'module = "app.core.engine"\nname = "{name}"\n',
    )


def test_the_module_name_avoids_names_the_holder_uses(tmp_path: Path) -> None:
    """Kennt der Halter den Namen ``engine`` schon (hier als Parameter), liest er über
    ``core_engine``; ein erklärter Name gilt vor dem Vorschlag."""
    files = fx.edit(
        fx.COPIES_OLD,
        CONSUMER,
        "def limit() -> int:\n",
        "def mix(engine: int) -> int:\n    return scale(engine)\n\n\ndef limit() -> int:\n",
    )
    root, result = _run(tmp_path / "a", files)
    assert result.status == "written", result.problems
    text = (root / CONSUMER).read_text(encoding="utf-8")
    assert "from app.core import engine as core_engine" in text
    assert "    return core_engine.scale(engine)\n" in text
    root, result = _run(tmp_path / "b", files, _aliased("engine_module"))
    assert result.status == "written", result.problems
    text = (root / CONSUMER).read_text(encoding="utf-8")
    assert "    return engine_module.scale(engine)\n" in text


def test_a_module_name_a_function_hides_is_rejected(tmp_path: Path) -> None:
    """Wird der Name einer wegfallenden Kopie (``scale``) zum Modulnamen erklärt, verdeckt ihn
    aber ein Parameter dort, wo gelesen wird, hält der Schnitt an."""
    files = fx.edit(
        fx.COPIES_OLD,
        CONSUMER,
        "def limit() -> int:\n",
        "def mix(scale: int) -> int:\n    return operation(scale)\n\n\ndef limit() -> int:\n",
    )
    message = _rejected(tmp_path, files, _aliased("scale"))
    assert "verdeckt ein lokaler Name 'scale'" in message and "[[aliases]]" in message


# ------------------------------------------------------------------------------ Mutanten


def _mutants() -> list[tuple[str, dict[str, str], str]]:
    return [
        (
            "vergessener-halter",
            EXPECTED | {"app/core/relay.py": fx.COPIES_OLD["app/core/relay.py"]},
            "app/core/relay.py: from-Bezug app.core.consumer.operation",
        ),
        (
            "vergessener-leser",
            fx.edit(
                EXPECTED,
                CONSUMER,
                "return engine.compute(value) + engine.scale(value)",
                "return operation(value) + engine.scale(value)",
            ),
            CONSUMER,
        ),
        (
            "falsches-original",
            fx.edit(
                EXPECTED,
                TESTS,
                'monkeypatch.setattr(engine, "compute", lambda value: 0)',
                'monkeypatch.setattr(engine, "scale", lambda value: 0)',
            ),
            TESTS,
        ),
        (
            "patch-am-alten-ziel",
            fx.edit(
                EXPECTED,
                TESTS,
                'monkeypatch.setattr("app.core.engine.compute", lambda value: 0)',
                'monkeypatch.setattr("app.core.relay.operation", lambda value: 0)',
            ),
            TESTS,
        ),
        (
            "vertauschte-familien",
            fx.edit(
                EXPECTED,
                CONSUMER,
                "return engine.compute(value) + engine.scale(value)",
                "return engine.scale(value) + engine.compute(value)",
            ),
            "liest danach nicht",
        ),
        (
            "kopie-bleibt",
            fx.edit(
                fx.edit(
                    EXPECTED,
                    CONSUMER,
                    "from app.core.engine import LIMIT\n",
                    "from app.core.engine import LIMIT, scale\n",
                ),
                CONSUMER,
                "engine.scale(value)",
                "scale(value)",
                count=2,
            ),
            "Kopfkopie scale",
        ),
        (
            "schatten-umgeschrieben",
            fx.edit(
                EXPECTED,
                CONSUMER,
                "def shadow(operation: object) -> object:\n    return operation\n",
                "def shadow(operation: object) -> object:\n    return engine.compute\n",
            ),
            CONSUMER,
        ),
        (
            "annotation-falsch",
            fx.edit(EXPECTED, CONSUMER, '"engine.Settings"', '"engine.scale"'),
            "Annotation",
        ),
        (
            "leseweg-am-original-vorbei",
            fx.edit(
                fx.edit(EXPECTED, CONSUMER, "return kit.measure(text)", "return len(text)"),
                CONSUMER,
                "from app.core import engine, kit\n",
                "from app.core import engine\n",
            ),
            CONSUMER,
        ),
        (
            "fremde-datei",
            fx.edit(EXPECTED, "app/core/other.py", "    return 2", "    return 2  # anders"),
            "app/core/other.py",
        ),
        (
            "zuweisung-bleibt-stehen",
            fx.edit(
                EXPECTED,
                "tools/engine_tool.py",
                "from app.core import engine\n",
                "from app.core import engine\n\noperation = engine.compute\n",
            ),
            "tools/engine_tool.py",
        ),
    ]


@pytest.mark.parametrize(
    ("label", "files", "where"), _mutants(), ids=[mutant[0] for mutant in _mutants()]
)
def test_every_mutant_of_the_copies_cut_is_red(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    proof = _prove(tmp_path, files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


def test_the_copies_mutant_list_is_not_empty() -> None:
    assert len(_mutants()) >= 10


# ------------------------------------------------------------------------------ abgewiesen


def _rejected(tmp_path: Path, files: dict[str, str], cut_text: str = fx.COPIES_CUT) -> str:
    root, result = _run(tmp_path, files, cut_text)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(files), "abgewiesen, aber geschrieben"
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


@pytest.mark.parametrize(
    ("label", "old", "new", "where"),
    [
        (
            "original-ist-kopie",
            'module = "app.core.engine"\nname = "scale"',
            'module = "app.core.consumer"\nname = "scale"',
            "ist selbst eine Kopie von app.core.engine.scale",
        ),
        (
            "original-fehlt",
            'module = "app.core.engine"\nname = "scale"',
            'module = "app.core.engine"\nname = "fehlt"',
            "gibt es nicht",
        ),
        (
            "original-ohne-kopie",
            'module = "app.core.engine"\nname = "scale"',
            'module = "app.core.engine"\nname = "direct"',
            "hat keine Kopfkopie",
        ),
    ],
)
def test_a_binding_the_cut_cannot_use_is_rejected(
    tmp_path: Path, label: str, old: str, new: str, where: str
) -> None:
    assert old in fx.COPIES_CUT, label
    assert where in _rejected(tmp_path, fx.COPIES_OLD, fx.COPIES_CUT.replace(old, new)), label


def _with_test(text: str) -> dict[str, str]:
    return fx.COPIES_OLD | {"tests/test_extra.py": text}


@pytest.mark.parametrize(
    ("label", "files", "where"),
    [
        (
            "setzen-der-kopie",
            _with_test(
                "from app.core import consumer\n\n\n"
                "def test_store():\n"
                "    consumer.operation = len\n"
            ),
            "tests/test_extra.py:5: setzt oder löscht die Kopie",
        ),
        (
            "global-schreiber",
            fx.edit(
                fx.COPIES_OLD,
                CONSUMER,
                "def limit() -> int:\n",
                "def reset() -> None:\n    global scale\n    scale = None\n\n\n"
                "def limit() -> int:\n",
            ),
            "scale wird geschrieben",
        ),
        (
            "zweite-bindung",
            fx.edit(
                fx.COPIES_OLD,
                CONSUMER,
                "from app.core.kit import measure\n",
                "from app.core.kit import measure\nfrom typing import TYPE_CHECKING\n\n"
                "if TYPE_CHECKING:\n    from app.core.engine import scale\n",
            ),
            "scale wird auf Modulebene 2-mal gebunden",
        ),
        (
            "umgebundene-kopie",
            fx.edit(
                fx.COPIES_OLD,
                CONSUMER,
                'TABLE = {"op": operation}\n',
                'TABLE = {"op": operation}\nscale = staticmethod(scale)\n',
            ),
            "app.core.engine.scale hat keine Kopfkopie",
        ),
        (
            "verdecktes-original-als-text",
            _with_test(
                "def test_kit(monkeypatch):\n"
                '    monkeypatch.setattr("app.core.consumer.measure", len)\n'
            ),
            "der Pfad app.core.kit.measure.measure als Text endete beim gleichnamigen trägen "
            "Export",
        ),
        (
            "geladene-kopie",
            _with_test(
                "import importlib.util\nfrom pathlib import Path\n\n\n"
                "def test_loaded(monkeypatch):\n"
                '    path = Path(__file__).parents[1] / "app" / "core" / "consumer.py"\n'
                '    spec = importlib.util.spec_from_file_location("c", path)\n'
                "    loaded = importlib.util.module_from_spec(spec)\n"
                '    monkeypatch.setattr(loaded, "operation", len)\n'
            ),
            "in einem über den Pfad geladenen Modul",
        ),
        (
            "gefaltete-patch-stelle",
            _with_test(
                "from app.core import consumer\n\n\n"
                "def test_folded(monkeypatch):\n"
                '    for name in ("operation", "scale"):\n'
                "        monkeypatch.setattr(consumer, name, len)\n"
            ),
            "gefaltetem Ziel",
        ),
        (
            "dunder-all",
            fx.edit(
                fx.COPIES_OLD,
                CONSUMER,
                'TABLE = {"op": operation}\n',
                'TABLE = {"op": operation}\n__all__ = ["scale"]\n',
            ),
            "steht in __all__",
        ),
        (
            "kopie-unter-neuem-namen",
            fx.edit(
                fx.COPIES_OLD,
                CONSUMER,
                'TABLE = {"op": operation}\n',
                'TABLE = {"op": operation}\nLIMIT_ALIAS: int = LIMIT\nSTEP = scale\n',
            ),
            "STEP = scale bindet die Kopie beim Import unter neuem Namen",
        ),
        (
            "zeichenkette-nennt-kopie",
            _with_test('NAMES = ("app.core.consumer.operation",)\n'),
            "tests/test_extra.py:1: Zeichenkette 'app.core.consumer.operation'",
        ),
        (
            "hasattr-auf-kopie",
            _with_test(
                "from app.core import consumer\n\n\n"
                "def test_has():\n"
                '    assert hasattr(consumer, "operation")\n'
            ),
            "fragt nach der Kopie",
        ),
        (
            "annotation-mit-praefix",
            fx.edit(fx.COPIES_OLD, CONSUMER, 'value: "Settings"', 'value: r"Settings"'),
            "Annotation als Zeichenkette nennt die Kopie Settings",
        ),
    ],
)
def test_a_copies_cut_that_cannot_be_proven_is_rejected(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    assert where in _rejected(tmp_path, files), label
