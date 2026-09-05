"""``tools/affected_tests.py`` — die Auswahl liest den Graphen, nicht das Gefühl.

Ein Prüfwerkzeug ist auch nur Code (``tests.md``), und dieses entscheidet,
welche Tests nach einer Änderung *nicht* laufen. Ein Fehler darin fällt also
nie als roter Test auf, sondern als grüner Stand, der keiner ist. Deshalb ein
Baum aus fünf Dateien, in dem jeder Ausgang bekannt ist: Wer ``app.x`` ändert,
trifft den direkten Importeur, den mittelbaren und den Baumleser — und nicht
den, der mit alledem nichts zu tun hat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.affected_tests import ImportGraph, affected, module_name


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/x.py", "VALUE = 1\n")
    _write(tmp_path, "app/y.py", "from app.x import VALUE\n")
    _write(tmp_path, "app/z.py", "OTHER = 2\n")
    _write(tmp_path, "tests/__init__.py", "")
    _write(tmp_path, "tests/conftest.py", "")
    _write(tmp_path, "tests/test_direct.py", "from app import x\n")
    _write(tmp_path, "tests/test_indirect.py", "def f():\n    from app.y import VALUE\n")
    _write(
        tmp_path,
        "tests/test_typed.py",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.x import VALUE\n",
    )
    _write(
        tmp_path,
        "tests/test_reader.py",
        "from pathlib import Path\nSOURCES = Path('app').rglob('*.py')\n",
    )
    _write(tmp_path, "tests/test_unrelated.py", "from app.z import OTHER\n")
    _write(tmp_path, "tests/test_roadmap.py", "TEXT = 'ROADMAP.md'\n")
    _write(tmp_path, "ROADMAP.md", "# Liste\n")
    return tmp_path


def _names(files: set[Path], root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in files}


def test_module_name_strips_init_and_uses_the_given_root(tmp_path: Path) -> None:
    assert module_name(tmp_path / "app" / "core" / "__init__.py", tmp_path) == "app.core"
    assert module_name(tmp_path / "app" / "core" / "units.py", tmp_path) == "app.core.units"


def test_a_changed_module_selects_direct_indirect_typed_and_tree_readers(tree: Path) -> None:
    files, reasons = affected([tree / "app" / "x.py"], ImportGraph(tree))

    assert _names(files, tree) == {
        "tests/test_direct.py",
        "tests/test_indirect.py",
        "tests/test_typed.py",
        "tests/test_reader.py",
    }
    assert reasons[tree / "tests" / "test_reader.py"] == "liest den ganzen Baum"
    assert reasons[tree / "tests" / "test_indirect.py"] == "importiert eine geänderte Datei"


def test_an_unrelated_module_selects_only_the_tree_readers(tree: Path) -> None:
    """``app.z`` importiert niemand außer ``test_unrelated`` — und der Baumleser sieht alles."""
    files, _ = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py", "tests/test_reader.py"}


def test_a_changed_test_file_selects_itself(tree: Path) -> None:
    files, reasons = affected([tree / "tests" / "test_unrelated.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py"}
    assert reasons[tree / "tests" / "test_unrelated.py"] == "selbst geändert"


def test_conftest_selects_every_test(tree: Path) -> None:
    files, _ = affected([tree / "tests" / "conftest.py"], ImportGraph(tree))

    assert _names(files, tree) == {
        "tests/test_direct.py",
        "tests/test_indirect.py",
        "tests/test_typed.py",
        "tests/test_reader.py",
        "tests/test_unrelated.py",
        "tests/test_roadmap.py",
    }


def test_a_named_text_file_selects_the_test_that_names_it(tree: Path) -> None:
    """Eine Markdown-Datei importiert niemand; wer sie prüft, nennt sie beim Namen."""
    files, reasons = affected([tree / "ROADMAP.md"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_roadmap.py"}
    assert reasons[tree / "tests" / "test_roadmap.py"] == "nennt ROADMAP.md"


def test_a_data_file_selects_the_tests_of_the_module_that_reads_it(tree: Path) -> None:
    """Wer eine Datendatei über ein Werkzeug liest, nennt sie nie beim Namen.

    Am 03.09.2026 hat genau das eine CI-Runde gekostet: Für eine geänderte
    ``changelog/de.md`` nannte die Auswahl ``test_changelog`` und
    ``test_changes_view``, aber nicht ``test_changelog_website`` — und der
    wurde rot, weil die erzeugten Seiten fehlten. Diese Datei liest den
    Changelog nicht selbst; sie ruft ``tools.make_changelog``, und dort
    entsteht der Pfad aus ``available_languages()``. Eine Namenssuche findet
    so etwas nie.

    Gesucht wird deshalb auch über den **Ordner**: Wer ihn im Quelltext
    nennt, liest die Datei, und wessen Tests ihn importieren, hängt an ihr.
    """
    _write(tree, "app/reader.py", 'from pathlib import Path\nDIR = Path("daten")\n')
    _write(tree, "tests/test_reader.py", "from app import reader\n")
    _write(tree, "daten/tabelle.toml", "wert = 1\n")

    files, reasons = affected([tree / "daten" / "tabelle.toml"], ImportGraph(tree))

    assert "tests/test_reader.py" in _names(files, tree), (
        "der Test des Moduls, das den Ordner liest, fehlt in der Auswahl"
    )
    # Und der Grund sagt den *zweiten* Weg an: Diese Datei nennt `tabelle.toml`
    # nirgends — sie hängt an einem Modul, das den Ordner liest. Bis zum
    # 03.09.2026 stand hier „nennt tabelle.toml", und wer dem nachging, suchte
    # einen Namen, den die Datei nicht enthält.
    assert reasons[tree / "tests" / "test_reader.py"] == "hängt an einem Modul, das daten/ liest"


def test_a_data_file_does_not_drag_in_the_whole_tree(tree: Path) -> None:
    """Und die Gegenrichtung: Die Kette wird **nicht** weiterverfolgt.

    Die erste Fassung des Fixes nahm die transitive Hülle und machte aus zwei
    Testdateien fünfundvierzig — über ``app/ui/update_dialog.py`` hängt am
    Changelog fast jede Datei der Oberfläche. Formal richtig, praktisch
    wertlos: Eine Auswahl, die zur Suite wird, sagt nichts mehr.
    """
    _write(tree, "app/reader.py", 'from pathlib import Path\nDIR = Path("daten")\n')
    _write(tree, "app/far.py", "from app import reader\n")
    _write(tree, "tests/test_far.py", "from app import far\n")
    _write(tree, "daten/tabelle.toml", "wert = 1\n")

    files, _ = affected([tree / "daten" / "tabelle.toml"], ImportGraph(tree))

    assert "tests/test_far.py" not in _names(files, tree), (
        "ein Test zwei Glieder weiter gehört nicht in die Auswahl einer Datendatei"
    )


def test_a_syntax_error_in_the_tree_does_not_stop_the_selection(tree: Path) -> None:
    """Ein fremder Zwischenstand im geteilten Baum darf die Auswahl nicht abbrechen."""
    _write(tree, "app/broken.py", "def (\n")

    files, _ = affected([tree / "app" / "x.py"], ImportGraph(tree))

    assert "tests/test_direct.py" in _names(files, tree)


def test_the_real_graph_knows_this_file() -> None:
    """Gegen den echten Baum: Das Werkzeug findet sich selbst über seinen Test."""
    graph = ImportGraph()
    files, reasons = affected([graph.root / "tools" / "affected_tests.py"], graph)

    assert graph.root / "tests" / "test_affected_tests.py" in files
    assert reasons[graph.root / "tests" / "test_affected_tests.py"] == (
        "importiert eine geänderte Datei"
    )


def test_a_deleted_module_still_counts_as_a_code_change(tree: Path) -> None:
    """B-14 aus dem Gesamtreview vom 05.09.2026: Ein gelöschtes Modul stand
    in keinem Graphen mehr, also fiel weder sein Name noch ``touches_code``
    an — die Auswahl war leer, obwohl der fachliche Test schon beim Import
    scheitern würde."""
    removed = tree / "app" / "x.py"
    removed.unlink()

    files, reasons = affected([removed], ImportGraph(tree))

    names = _names(files, tree)
    assert "tests/test_typed.py" in names, "nennt app.x im Quelltext"
    assert "tests/test_reader.py" in names, "eine Codeänderung erreicht die Baumleser"
    assert any("gelöscht" in reason for reason in reasons.values())
