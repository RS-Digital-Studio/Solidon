"""Der Beweis des Verschiebewerkzeugs (Plan Schritt 0, 2.7, Punkt 5) gegen Sollbäume von außen.

Jeder Fall vergleicht den alten Attrappenbaum mit einem **von Hand geschriebenen** neuen Baum —
ohne den Planer, der die Änderung sonst erzeugt. Der richtige Sollbaum muss bestehen, jeder
Mutant muss rot sein und die Stelle nennen: ein geänderter Rumpf, ein vergessener Importeur, ein
Pfad-Patch oder ``patch.object`` am alten Ziel, ein verlorener Kopfkommentar, eine Fassade im
Paket-``__init__``, eine vertauschte Registerfolge, eine Kopie statt eines Modulzugriffs, ein
zum Laufzeitimport gewordener Typimport, ein falsch umgeschriebener Schatten und eine Änderung
außerhalb des Schnitts. So belegt der Test, dass der Beweis nicht nur sich selbst bestätigt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_proof

EXPECTED = fx.changed_tree(fx.MODULE_OLD, fx.MODULE_NEW)


def _prove(
    tmp_path: Path,
    new_files: dict[str, str],
    *,
    cut_text: str = fx.MODULE_CUT,
    old_files: dict[str, str] = fx.MODULE_OLD,
) -> move_proof.Proof:
    old = fx.write_tree(tmp_path / "old", old_files)
    new = fx.write_tree(tmp_path / "new", new_files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut_text, encoding="utf-8")
    return move_proof.prove(move_cut.load(cut_file), old, new)


def test_the_hand_written_module_cut_is_proven(tmp_path: Path) -> None:
    """Der Sollbaum besteht, und der Beweis hat wirklich etwas verglichen: jede Definition, jede
    umgeschriebene Datei, jede Patch-Stelle, jede Lesermenge und den Registerabzug."""
    proof = _prove(tmp_path, EXPECTED)
    assert proof.ok, proof.text()
    assert proof.counts["definitions"] == 6
    assert proof.counts["changed_files"] == 4
    assert proof.counts["patch_sites"] == 6
    assert proof.counts["reach_keys"] == 4
    assert proof.counts["registry_bytes"] > 0
    assert proof.counts["references"] >= 9
    text = proof.text()
    assert "app.core.legacy:_adjust → app.core.legacy.rules:adjust" in text
    assert "Registerabzug byte-gleich" in text


def _mutants() -> list[tuple[str, dict[str, str], str]]:
    rules = "app/core/legacy/rules.py"
    tests = "tests/test_legacy.py"
    consumer = "app/core/consumer.py"
    return [
        (
            "rumpf",
            fx.edit(EXPECTED, rules, "return adjust(hidden)", "return adjust(hidden) + 0"),
            "Rule",
        ),
        (
            "vergessener-importeur",
            EXPECTED | {"tools/check_legacy.py": fx.MODULE_OLD["tools/check_legacy.py"]},
            "tools/check_legacy.py",
        ),
        (
            "textpatch-am-alten-ziel",
            fx.edit(EXPECTED, tests, '"app.core.legacy.rules.adjust"', '"app.core.legacy._adjust"'),
            "tests/test_legacy.py",
        ),
        (
            "patch-object-am-alten-ziel",
            fx.edit(
                fx.edit(
                    EXPECTED,
                    tests,
                    'patch.object(rules, "adjust"',
                    'patch.object(legacy, "_adjust"',
                ),
                tests,
                "from app.core.legacy import rules, state",
                "from app.core import legacy\nfrom app.core.legacy import rules, state",
            ),
            "tests/test_legacy.py",
        ),
        (
            "falsches-original",
            fx.edit(EXPECTED, consumer, "return rules.adjust(shape)", "return rules.Rule(shape)"),
            "app/core/consumer.py",
        ),
        (
            "kopfkommentar-fehlt",
            fx.edit(EXPECTED, rules, "# Kopfkommentar: gehört zu _adjust und wandert mit.\n", ""),
            "Kommentar",
        ),
        (
            "dekorator-geändert",
            fx.edit(EXPECTED, rules, 'check="points"', 'check="punkte"'),
            "adjust",
        ),
        (
            "fassade-im-init",
            EXPECTED
            | {
                "app/core/legacy/__init__.py": '"""Zähler, Regeln und eine Operation der '
                'Attrappe."""\n\nfrom app.core.legacy.rules import adjust\n'
            },
            "__init__.py",
        ),
        (
            "registerfolge",
            fx.edit(
                EXPECTED,
                "app/core/bootstrap.py",
                '    "app.core.legacy.rules",\n    "app.core.other",',
                '    "app.core.other",\n    "app.core.legacy.rules",',
            ),
            "Registerabzug",
        ),
        (
            "fremde-datei",
            fx.edit(EXPECTED, "app/core/other.py", "    return 2", "    return 2  # anders"),
            "app/core/other.py",
        ),
        (
            "kopie-statt-modulzugriff",
            fx.edit(
                fx.edit(EXPECTED, rules, "        state.bump()", "        bump()"),
                rules,
                "from app.core.legacy import state\n",
                "from app.core.legacy import state\nfrom app.core.legacy.state import bump\n",
            ),
            "bump",
        ),
        (
            "typimport-zur-laufzeit",
            fx.edit(
                fx.edit(
                    EXPECTED,
                    rules,
                    "if TYPE_CHECKING:\n    from app.core.shapes import Hidden\n",
                    "",
                ),
                rules,
                "from app.core.shapes import Shape\n",
                "from app.core.shapes import Hidden, Shape\n",
            ),
            "Hidden",
        ),
        (
            "schatten-umgeschrieben",
            fx.edit(
                EXPECTED,
                consumer,
                "    return module._adjust  # Parameter, kein Modul: bleibt",
                "    return rules.adjust  # Parameter, kein Modul: bleibt",
            ),
            "app/core/consumer.py",
        ),
        (
            "unbenutzter-import",
            fx.edit(
                EXPECTED,
                rules,
                "from typing import TYPE_CHECKING\n",
                "import logging\nfrom typing import TYPE_CHECKING\n",
            ),
            "logging",
        ),
        (
            "leser-am-alten-modul",
            fx.edit(
                fx.edit(
                    EXPECTED,
                    consumer,
                    "return app.core.legacy.state.read_count()",
                    "return app.core.legacy.read_count()",
                ),
                consumer,
                "import app.core.legacy.state\n",
                "import app.core.legacy\nimport app.core.legacy.state\n",
            ),
            "app/core/consumer.py",
        ),
    ]


@pytest.mark.parametrize(
    ("label", "files", "where"), _mutants(), ids=[mutant[0] for mutant in _mutants()]
)
def test_every_mutant_of_the_module_cut_is_red(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    """Jeder Mutant bricht den Beweis, und die Meldung nennt die Stelle."""
    proof = _prove(tmp_path, files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


def test_the_mutant_list_is_not_empty() -> None:
    """Die Grundmenge der Gegenproben (Plan 2.7) ist nicht leer."""
    assert len(_mutants()) >= 15


def test_a_cut_that_separates_a_global_writer_from_its_variable_is_red(tmp_path: Path) -> None:
    """Steht ``bump`` (``global COUNT``) in einem anderen Ziel als ``COUNT``, ist auch ein von
    Hand gebauter Kandidat rot: Der Schreiber legte im neuen Modul eine zweite Variable an."""
    cut = fx.MODULE_CUT.replace(
        'definitions = ["logger", "COUNT", "bump", "read_count"]',
        'definitions = ["logger", "COUNT", "read_count"]',
    ).replace('definitions = ["_adjust", "Rule"]', 'definitions = ["bump", "_adjust", "Rule"]')
    state = fx.text_of(EXPECTED["app/core/legacy/state.py"])
    bump = state[state.index("def bump") : state.index("def read_count")]
    files = EXPECTED | {
        "app/core/legacy/state.py": state.replace(bump, ""),
        "app/core/legacy/rules.py": fx.text_of(EXPECTED["app/core/legacy/rules.py"])
        .replace("        state.bump()", "        bump()")
        .replace(
            "# Kopfkommentar",
            bump.replace("logger.debug", "state.logger.debug") + "\n\n# Kopfkommentar",
        ),
    }
    proof = _prove(tmp_path, files, cut_text=cut)
    assert not proof.ok, proof.text()
    assert any("COUNT" in error for error in proof.errors), proof.errors
