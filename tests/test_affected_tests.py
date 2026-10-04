"""``tools/affected_tests.py`` — die Auswahl liest den Graphen, nicht das Gefühl.

Ein Prüfwerkzeug ist auch nur Code (``tests.md``), und dieses entscheidet,
welche Tests nach einer Änderung *nicht* laufen. Ein Fehler darin fällt also
nie als roter Test auf, sondern als grüner Stand, der keiner ist. Deshalb ein
Baum aus fünf Dateien, in dem jeder Ausgang bekannt ist: Wer ``app.x`` ändert,
trifft den direkten Importeur, den mittelbaren und den Baumleser — und nicht
den, der mit alledem nichts zu tun hat.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from tools.affected_tests import (
    ImportGraph,
    affected,
    bare_local_imports,
    changed_files,
    module_name,
)


@pytest.fixture(autouse=True)
def _no_inherited_addopts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Kindläufe erben nichts vom äußeren Lauf.

    Wer die Suite mit ``PYTEST_ADDOPTS="-n 5"`` startet, gab das an jeden
    echten Kindprozess weiter: „1 passed“ statt „1 passed, 1 deselected“, und
    drei Fälle wurden rot, ohne dass sich am Werkzeug etwas geändert hatte.
    Ein Fall, der die Variable prüft, setzt sie selbst.
    """
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)


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
    """Ein Paket heißt nach seinem Ordner, ein Modul nach seiner Datei — relativ zur genannten
    Wurzel.
    """
    assert module_name(tmp_path / "app" / "core" / "__init__.py", tmp_path) == "app.core"
    assert module_name(tmp_path / "app" / "core" / "units.py", tmp_path) == "app.core.units"


def test_a_changed_module_selects_direct_indirect_typed_and_tree_readers(tree: Path) -> None:
    """Eine geänderte Kerndatei wählt, wer sie direkt, mittelbar oder nur für Typen importiert,
    dazu jeden Baumleser — und nennt je Datei den Grund.
    """
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
    """Eine geänderte Testdatei ist selbst betroffen, und nur sie."""
    files, reasons = affected([tree / "tests" / "test_unrelated.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py"}
    assert reasons[tree / "tests" / "test_unrelated.py"] == "selbst geändert"


@pytest.mark.parametrize("deleted", [False, True])
@pytest.mark.parametrize("package", ["app", "app/nested", "app/nested/deeper"])
def test_package_initializers_select_submodule_importers(
    tree: Path, package: str, deleted: bool
) -> None:
    """Jeder Import führt zuerst die Elternpakete aus, auch ohne ausdrücklichen Paketimport.

    Nach dem Entfernen eines Initialisierers bleiben dessen bisherige Nutzer
    betroffen; ein Namensraum-Paket darf die Auswahl nicht leeren.
    """
    initializer = _write(tree, f"{package}/__init__.py", "VALUE = 1\n")
    _write(tree, "app/nested/deeper/leaf.py", "VALUE = 2\n")
    _write(tree, "tools/wrapper.py", "from app.nested.deeper.leaf import VALUE\n")
    _write(tree, "tests/test_nested.py", "import app.nested.deeper.leaf\n")
    _write(tree, "tests/test_wrapped.py", "from tools.wrapper import VALUE\n")
    if deleted:
        initializer.unlink()

    files, _ = affected([initializer], ImportGraph(tree))

    assert {"tests/test_nested.py", "tests/test_wrapped.py"} <= _names(files, tree)
    if package != "app":
        assert "tests/test_unrelated.py" not in _names(files, tree)


def test_a_deleted_test_helper_selects_its_importers(tree: Path) -> None:
    """Ein gelöschter Helfer unter tests/ betrifft seine Nutzer genauso wie Anwendungscode."""
    helper = _write(tree, "tests/probe.py", "VALUE = 1\n")
    _write(tree, "tests/test_probe.py", "from tests.probe import VALUE\n")
    helper.unlink()

    files, _ = affected([helper], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_probe.py"}


def test_git_paths_keep_unicode_spaces_and_both_sides_of_a_rename(tmp_path: Path) -> None:
    """Echtes Git: Pfade bleiben bytegetreu, eine Umbenennung enthält auch die gelöschte Quelle.

    core.quotePath erzwingt den üblichen Git-Standard auch auf Maschinen, die
    ihn abgeschaltet haben; sonst verdeckte die lokale Einstellung den Fehler.
    """

    def git(*arguments: str) -> None:
        subprocess.run(
            ["git", "-c", "core.hooksPath=unused-hooks", *arguments],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("config", "core.quotePath", "true")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    modified = _write(tmp_path, "daten/Änderung.txt", "vorher\n")
    staged = _write(tmp_path, "daten/Übernahme.txt", "vorher\n")
    before = _write(tmp_path, "tools/old.py", "VALUE = 1\n")
    git("add", ".")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "Ausgangsstand")
    modified.write_text("nachher\n", encoding="utf-8")
    staged.write_text("nachher\n", encoding="utf-8")
    git("add", "daten/Übernahme.txt")
    after = tmp_path / "tools/new.py"
    git("mv", "tools/old.py", "tools/new.py")
    new = _write(tmp_path, " Neuer Eintrag mit Umlaut ö.txt", "neu\n")

    assert set(changed_files(tmp_path)) == {modified, staged, before, after, new}


def test_conftest_selects_every_test(tree: Path) -> None:
    """``conftest.py`` lädt vor jeder Testdatei; eine Änderung daran betrifft alle."""
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


def test_a_script_outside_the_packages_selects_the_test_that_loads_it(tree: Path) -> None:
    """Ein Skript außerhalb von ``app/``, ``tools/`` und ``tests/`` importiert niemand.

    Seine Tests laden es über ``spec_from_file_location`` und nennen dabei den
    Dateinamen — so wie ``test_delivery_matrix_review.py`` den Matrixläufer
    unter ``.claude/.state/`` lädt. Ohne Rückfall auf die Namenssuche meldete
    die Auswahl „Keine Testdatei hängt an dieser Änderung“, und der Test, der
    rot würde, lief nicht.
    """
    _write(tree, ".claude/.state/durchsicht/einheit.py", "def main() -> int:\n    return 0\n")
    _write(tree, ".claude/.state/durchsicht/gcode_lesen.py", "LAYERS = 0\n")
    _write(
        tree,
        "tests/test_matrix.py",
        "from pathlib import Path\n"
        "RUN = Path('.claude/.state/durchsicht') / 'einheit.py'\n"
        "READ = Path('.claude/.state/durchsicht') / 'gcode_lesen.py'\n",
    )

    for script in ("einheit.py", "gcode_lesen.py"):
        files, reasons = affected(
            [tree / ".claude" / ".state" / "durchsicht" / script], ImportGraph(tree)
        )

        assert _names(files, tree) == {"tests/test_matrix.py"}, script
        assert reasons[tree / "tests" / "test_matrix.py"] == f"nennt {script}"


def test_the_real_graph_finds_the_test_of_the_shared_hook() -> None:
    """Gegen den echten Baum: Der Hook unter ``.claude/hooks/`` hat seinen Test.

    ``test_solidon3d_hooks.py`` lädt ihn über seinen Pfad; eine Änderung am
    Hook ohne diesen Test wäre ein grüner Stand, der keiner ist.
    """
    graph = ImportGraph()
    hook = graph.root / ".claude" / "hooks" / "solidon3d_hooks.py"
    assert hook.is_file()

    files, reasons = affected([hook], graph)

    expected = graph.root / "tests" / "test_solidon3d_hooks.py"
    assert expected in files
    assert reasons[expected] == "nennt solidon3d_hooks.py"


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


def test_a_bare_import_of_a_local_module_is_found(tree: Path) -> None:
    """Der Fall mit bekanntem Ausgang: Ein Helfer ohne ``tests.``-Präfix entgeht dem Graphen,
    und genau diese Stelle meldet die Suche — ``import conftest`` und der Präfixweg nicht.
    """
    _write(tree, "tests/fakes.py", "FAKE = 1\n")
    _write(tree, "tests/test_bare.py", "def f():\n    from fakes import FAKE\n")
    _write(tree, "tests/test_prefixed.py", "import conftest\nfrom tests.fakes import FAKE\n")
    graph = ImportGraph(tree)

    files, _ = affected([tree / "tests" / "fakes.py"], graph)

    assert _names(files, tree) == {"tests/test_prefixed.py"}
    assert bare_local_imports(graph) == ["tests/test_bare.py:2: fakes"]


def test_tests_and_tools_import_their_neighbours_with_the_package_prefix() -> None:
    """Wer einen Nachbarn aus ``tests/`` oder ``tools/`` ohne Präfix importiert, fehlt in jeder
    Auswahl zu dessen Änderung (``bare_local_imports``). Der Präfix ist die ganze Abhilfe.
    """
    graph = ImportGraph()
    assert sum(name.startswith("tests.test_") for name in graph.modules) > 300

    assert bare_local_imports(graph) == []


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


@pytest.fixture
def selection_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Ein reiner Sammlungskorpus; weder seine Fixtures noch Tests dürfen laufen."""
    import importlib

    from tools import affected_tests

    # Die Gesamtsuite importiert dieses Modul etwa über test_toolchain. Ohne
    # eigenes Wurzelpaket benutzte importlib für den Korpus denselben Namen
    # tests.conftest und verlor dadurch dessen mittelbare Fenster-Fixture.
    importlib.import_module("tests.conftest")
    _write(tmp_path, "__init__.py", "")
    _write(tmp_path, "tests/__init__.py", "")
    _write(
        tmp_path,
        "pytest.ini",
        "[pytest]\naddopts = --import-mode=importlib\nmarkers =\n"
        "    performance: Messung\n    windowed: Fenster im Kindprozess\n"
        "    rendering: echte Grafik\n",
    )
    _write(
        tmp_path,
        "tests/conftest.py",
        "import pytest\n"
        "@pytest.fixture\n"
        "def qt_app():\n    raise AssertionError('fixture ran')\n"
        "@pytest.fixture\n"
        "def inherited(qt_app):\n    return qt_app\n"
        "@pytest.fixture\n"
        "def require_graphics_adapter():\n    raise AssertionError('fixture ran')\n"
        "@pytest.fixture\n"
        "def inherited_renderer(require_graphics_adapter):\n"
        "    return require_graphics_adapter\n",
    )
    files = {
        "plain": _write(tmp_path, "tests/test_plain.py", "def test_plain():\n    assert False\n"),
        "window": _write(
            tmp_path,
            "tests/test_window.py",
            "def test_window(inherited):\n    assert False\n"
            "def test_regular():\n    assert False\n",
        ),
        "performance": _write(
            tmp_path,
            "tests/test_performance.py",
            "import pytest\n@pytest.mark.performance\n"
            "def test_measure(inherited):\n    assert False\n",
        ),
        "marked": _write(
            tmp_path,
            "tests/test_marked.py",
            "import pytest\n@pytest.mark.windowed\n"
            "def test_process_window():\n    assert False\n"
            "def test_regular():\n    assert False\n",
        ),
        "mixed": _write(
            tmp_path,
            "tests/test_mixed.py",
            "import pytest\ndef test_regular():\n    assert False\n"
            "@pytest.mark.performance\ndef test_measure(inherited):\n    assert False\n",
        ),
        "renderer": _write(
            tmp_path,
            "tests/test_renderer.py",
            "import pytest\ndef test_regular():\n    assert False\n"
            "def test_renderer(inherited_renderer):\n    assert False\n"
            "@pytest.mark.rendering\ndef test_direct_renderer():\n    assert False\n",
        ),
    }
    monkeypatch.setattr(affected_tests, "ROOT", tmp_path)
    return files


@pytest.mark.parametrize("release", [False, True])
def test_commands_defer_windows_and_never_run_performance(
    selection_tree: dict[str, Path], release: bool
) -> None:
    """Getrennt wird je Test: Entwicklungstests laufen immer,
    Fenster- und Rendererfälle nur beim Release, Leistung nie.

    Bis zum 22.09.2026 zog ein einziger Fenstertest seine ganze Datei ins
    Release — gemessen 1709 Tests ohne Fenster außerhalb jedes
    Entwicklungstors.
    """
    from tools.affected_tests import commands

    lines = commands(selection_tree.values(), release=release)

    assert len(lines) == (4 if release else 1)
    assert lines[0][lines[0].index("--window-group") + 1] == "plain"
    assert [argument for argument in lines[0] if argument.startswith("tests/")] == [
        "tests/test_marked.py",
        "tests/test_mixed.py",
        "tests/test_plain.py",
        "tests/test_renderer.py",
        "tests/test_window.py",
    ]
    if release:
        assert [line[-1] for line in lines[1:]] == [
            "tests/test_marked.py",
            "tests/test_renderer.py",
            "tests/test_window.py",
        ]
        assert all(line[line.index("--window-group") + 1] == "windowed" for line in lines[1:])
    assert all("tests/test_performance.py" not in line for line in lines)


@pytest.mark.parametrize("source", ["environment", "configuration"])
@pytest.mark.parametrize(
    "filters",
    [
        "-k test_regular",
        "-k no_such_test",
        '-m "not windowed"',
        '-m "not rendering"',
        "-m performance",
        '-k test_regular -m "not performance and not windowed and not rendering"',
        "--deselect=tests/test_window.py",
    ],
)
def test_file_groups_ignore_case_filters(
    selection_tree: dict[str, Path],
    source: str,
    filters: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Abwahl ändert weder Releasebedarf noch die vorhandenen Kerndateien."""
    import os

    from tools.list_windowed_tests import collect_test_groups

    root = selection_tree["plain"].parent.parent
    if source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", filters)
    else:
        configuration = root / "pytest.ini"
        configuration.write_text(
            configuration.read_text(encoding="utf-8").replace(
                "addopts = --import-mode=importlib", f"addopts = --import-mode=importlib {filters}"
            ),
            encoding="utf-8",
        )
    before = os.environ.get("PYTEST_ADDOPTS")

    windowed, plain = collect_test_groups(tuple(selection_tree.values()), confcutdir=root)

    # „mixed“ hat nur als Leistungstest ein Fenster — kein Fenstertest also.
    assert set(windowed) == {selection_tree[name] for name in ("window", "marked", "renderer")}
    assert set(plain) == {
        selection_tree[name] for name in ("plain", "window", "marked", "mixed", "renderer")
    }
    assert os.environ.get("PYTEST_ADDOPTS") == before


@pytest.mark.parametrize("filters", ["-k no_such_test", "--deselect=tests/test_plain.py"])
def test_file_classification_respects_the_explicit_file_selection(
    selection_tree: dict[str, Path], filters: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die vollständige Prüfung einer Datei nimmt keine benachbarte Datei hinzu."""
    from tools.list_windowed_tests import collect_test_groups

    plain = selection_tree["plain"]
    monkeypatch.setenv("PYTEST_ADDOPTS", filters)

    assert collect_test_groups((plain,), confcutdir=plain.parent.parent) == ((), (plain,))


@pytest.mark.parametrize("source", ["environment", "configuration", "command"])
def test_the_actual_core_process_keeps_case_filters(
    selection_tree: dict[str, Path],
    source: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Der echte Kindprozess führt genau den beauftragten Kernfall aus."""
    import os

    from tools import affected_tests

    plain = selection_tree["plain"]
    root = plain.parent.parent
    plain.write_text(
        "import pytest\n"
        "@pytest.mark.requested\ndef test_keep_requested():\n    assert True\n"
        "def test_keep_other():\n    raise AssertionError('marker filter lost')\n"
        "@pytest.mark.requested\ndef test_drop_requested():\n"
        "    raise AssertionError('keyword filter lost')\n"
        "@pytest.mark.performance\n@pytest.mark.requested\ndef test_keep_measure():\n"
        "    raise AssertionError('performance was run')\n",
        encoding="utf-8",
    )
    configuration = root / "pytest.ini"
    configuration.write_text(
        configuration.read_text(encoding="utf-8") + "    requested: Ausgewählter Fall\n",
        encoding="utf-8",
    )
    filters = ["-k", "keep", "-m", "requested"]
    if source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", " ".join(filters))
    elif source == "configuration":
        configuration.write_text(
            configuration.read_text(encoding="utf-8").replace(
                "addopts = --import-mode=importlib",
                "addopts = --import-mode=importlib " + " ".join(filters),
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(affected_tests, "affected", lambda _: ({plain}, {plain: "selbst geändert"}))
    # Im echten Lauf liegt tools/ unter cwd; der kleine Korpus liegt getrennt.
    module_root = str(Path(__file__).resolve().parent.parent)
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join((module_root, os.environ.get("PYTHONPATH", "")))
    )

    result = affected_tests.main([str(plain), "--run", *(filters if source == "command" else [])])

    assert result == 0, capsys.readouterr().out
    assert "1 passed, 3 deselected" in capsys.readouterr().out


@pytest.mark.parametrize("source", ["environment", "command"])
def test_the_plain_tests_of_a_window_file_run_and_its_windows_wait(
    selection_tree: dict[str, Path],
    source: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Der reine Fall einer Fensterdatei läuft sofort, ihr Fenstertest erst im Release."""
    from tools import affected_tests

    window = selection_tree["marked"]
    filters = ["-k", "test_regular"]
    if source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_regular")
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({window}, {window: "selbst geändert"})
    )
    started: list[list[str]] = []
    monkeypatch.setattr(affected_tests, "run", lambda lines: started.extend(lines) or 0)

    assert (
        affected_tests.main([str(window), "--run", *(filters if source == "command" else [])]) == 0
    )
    output = capsys.readouterr().out
    assert "Zurückgestellt" in output and "tests/test_marked.py" in output
    assert len(started) == 1
    assert started[0][-1] == "tests/test_marked.py"
    assert started[0][started[0].index("--window-group") + 1] == "plain"


def test_a_filtered_core_file_is_never_reported_as_deferred(
    selection_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ein Name ohne Treffer macht eine Kerndatei nicht zur Fenster- oder Leistungsdatei."""
    from tools import affected_tests

    plain = selection_tree["plain"]
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k no_such_test")
    monkeypatch.setattr(affected_tests, "affected", lambda _: ({plain}, {plain: "selbst geändert"}))

    assert affected_tests.main([str(plain), "--split"]) == 0
    output = capsys.readouterr().out
    assert "tests/test_plain.py" in output
    assert "Zurückgestellt" not in output
    assert "kein Testlauf gestartet" not in output


@pytest.mark.parametrize("mode", ["--run", "--split", "--why"])
def test_a_named_window_file_is_deferred_but_remains_visible(
    selection_tree: dict[str, Path],
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Die Fenstertests einer ausdrücklich genannten Datei werden bis zum Release
    zurückgestellt und stehen in der Ausgabe — mit Grund bei ``--why``; ihre Tests
    ohne Fenster laufen.
    """
    from tools import affected_tests

    window = selection_tree["window"]
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({window}, {window: "selbst geändert"})
    )
    started: list[list[str]] = []
    monkeypatch.setattr(affected_tests, "run", lambda lines: started.extend(lines) or 0)

    assert affected_tests.main([str(window), mode]) == 0

    output = capsys.readouterr().out
    assert "tests/test_window.py" in output
    if mode == "--why":
        assert "selbst geändert" in output
        assert "Zurückgestellt" not in output
    else:
        assert "Zurückgestellt" in output
        if mode == "--split":
            assert "--window-group plain tests/test_window.py" in output
        else:
            assert started and started[0][-1] == "tests/test_window.py"


def test_an_only_performance_selection_does_not_start_empty_pytest(
    selection_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Besteht die Auswahl nur aus Leistungstests, startet auch ``--release`` keinen leeren pytest-
    Lauf — der endete mit Exit 5 und sähe aus wie ein Fehler.
    """
    from tools import affected_tests

    performance = selection_tree["performance"]
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({performance}, {performance: "selbst geändert"})
    )
    monkeypatch.setattr(affected_tests, "run", lambda _: pytest.fail("empty pytest was started"))

    assert affected_tests.main([str(performance), "--run", "--release"]) == 0
    assert "kein Testlauf gestartet" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("rendering", "Zurückgestellt: Fenster- und Rendererfälle"),
        ("rendered", "Nur Erzeugnisvergleiche oder Leistungsprüfungen"),
    ],
)
def test_release_only_selection_does_not_start_an_empty_development_process(
    selection_tree: dict[str, Path],
    marker: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Renderer und Erzeugnisvergleiche bleiben sichtbar, ohne leere Kernläufe zu starten."""
    from tools import affected_tests

    path = _write(
        selection_tree["plain"].parent,
        "test_release_only.py",
        f"import pytest\n@pytest.mark.{marker}\ndef test_release_only(): pass\n",
    )
    monkeypatch.setattr(affected_tests, "affected", lambda _: ({path}, {path: "selbst geändert"}))
    monkeypatch.setattr(affected_tests, "run", lambda _: pytest.fail("leerer Lauf wurde gestartet"))

    assert affected_tests.main([str(path), "--run"]) == 0
    output = capsys.readouterr().out
    assert expected in output
    assert "tests/test_release_only.py" in output
    assert "kein Testlauf gestartet" in output


def test_isolated_runner_skips_files_without_development_cases(
    selection_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Der lokale Dateiläufer überspringt Renderer- und Erzeugnisdateien im Entwicklungstor."""
    from tools import run_suite_isolated

    renderer = _write(
        selection_tree["plain"].parent,
        "test_renderer_boundary_gfx_only.py",
        "import pytest\n@pytest.mark.rendering\ndef test_graphics(): pass\n",
    )
    generated = _write(
        selection_tree["plain"].parent,
        "test_renderer_boundary_artifacts_only.py",
        "import pytest\n@pytest.mark.rendered\ndef test_generated(): pass\n",
    )
    monkeypatch.setattr(run_suite_isolated, "chosen_files", lambda _: [renderer, generated])
    monkeypatch.setattr(
        run_suite_isolated.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("leerer Dateiprozess wurde gestartet"),
    )

    assert run_suite_isolated.run_local((), release=False) == 0
    output = capsys.readouterr().out
    assert "Zurückgestellt: Fenster- und Rendererfälle" in output
    assert "Nur Erzeugnisvergleiche oder Leistungsprüfungen" in output
    assert "Keine regulären Tests ausgewählt; kein Testlauf gestartet." in output


def test_a_truly_empty_collection_stays_an_error(tmp_path: Path) -> None:
    """Eine Datei ohne Tests sammelt nichts, und das bleibt ein Fehler (Exit 5), kein grüner
    Lauf."""
    from tools.list_windowed_tests import collect_test_groups

    empty = _write(tmp_path, "test_empty.py", "# Keine Tests vorhanden.\n")
    with pytest.raises(RuntimeError, match="Exit 5"):
        collect_test_groups((empty,), confcutdir=tmp_path)


def test_a_partly_broken_collection_stays_an_error(
    selection_tree: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schon gesammelte Kernfälle verdecken keinen anschließenden Importfehler."""
    from tools.list_windowed_tests import collect_test_groups

    plain = selection_tree["plain"]
    broken = _write(plain.parent, "test_broken.py", "raise RuntimeError('broken collection')\n")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_plain")
    with pytest.raises(RuntimeError, match="Exit 2"):
        collect_test_groups((plain, broken), confcutdir=plain.parent.parent)


@pytest.mark.parametrize("release", [False, True])
def test_the_isolated_runner_uses_the_same_release_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: bool
) -> None:
    """Der abgekoppelte Läufer trennt Fenster- von Kerndateien mit derselben Regel wie
    ``affected_tests``: ohne ``--release`` nur der Kern, mit beidem — und nie die Leistung.
    """
    from tools import affected_tests, run_suite_isolated

    plain, window, performance = [tmp_path / name for name in ("plain", "window", "performance")]
    monkeypatch.setattr(run_suite_isolated, "chosen_files", lambda _: [plain, window, performance])
    monkeypatch.setattr(
        affected_tests, "split_windowed", lambda _, *, release=False: ([window], [plain])
    )
    calls: list[list[str]] = []

    def finish(arguments: list[str], **_options: object) -> CompletedProcess[str]:
        calls.append(arguments)
        return CompletedProcess(arguments, 0, "1 passed in 0.01s\n", "")

    monkeypatch.setattr(run_suite_isolated.subprocess, "run", finish)

    assert run_suite_isolated.main(["--release"] if release else []) == 0
    assert [line[-1] for line in calls] == [str(plain), *([str(window)] if release else [])]
    expected = (
        "not performance"
        if release
        else "not performance and not windowed and not rendering and not rendered"
    )
    assert all(line[4:6] == ["-m", expected] for line in calls)


@pytest.mark.parametrize("release", [False, True])
def test_the_selection_leaves_out_generated_comparisons_like_the_gate(release: bool) -> None:
    """Ein Test mit ``rendered`` hängt an einem Erzeugerlauf, nicht am Code.

    Das Entwicklungstor wählt ihn ab (``suite-getrennt.sh``), das Release-Tor
    nimmt ihn mit. Die Auswahl tat bis zum 29.09.2026 beides nicht: Ein
    veraltetes Handbuchbild erschien in einer Schrittprüfung als roter Test,
    den kein Codefix grün macht. Geprüft am Plugin, das den Filter setzt, und am
    Aufruf, der es für das Release anders schaltet.
    """
    from types import SimpleNamespace

    from tools import list_windowed_tests
    from tools.affected_tests import _commands

    options = {"--window-group": "plain", "--with-rendered": release}
    config = SimpleNamespace(
        getoption=lambda name, default=None: options.get(name, default),
        option=SimpleNamespace(markexpr=""),
    )
    list_windowed_tests.pytest_configure(config)  # type: ignore[arg-type]

    assert ("not rendered" in config.option.markexpr) is not release
    assert "not performance" in config.option.markexpr
    assert "not rendering" in config.option.markexpr
    lines = _commands([], [Path("tests/test_plain.py").resolve()], release=release)
    assert ("--with-rendered" in lines[0]) is release


@pytest.mark.parametrize("exit_code", [0, 5, 139])
def test_a_successful_summary_cannot_hide_the_process_exit(
    monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    """„1 passed" in der Ausgabe rettet keinen Prozess, der mit 5 oder 139 endete: Der Exit-Code
    entscheidet, nicht die Schlusszeile.
    """
    from tools import affected_tests

    monkeypatch.setattr(
        affected_tests.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, exit_code, "1 passed in 0.01s\n", ""),
    )
    assert affected_tests.run([["python", "-m", "pytest", "tests/test_plain.py"]]) == (
        0 if exit_code == 0 else 1
    )


@pytest.mark.parametrize(("given", "expected"), [(None, "1"), ("6", "6")], ids=["frei", "gesetzt"])
def test_every_run_gets_one_blas_thread_unless_the_caller_chose(
    monkeypatch: pytest.MonkeyPatch, given: str | None, expected: str
) -> None:
    """OpenBLAS sagt beim Laden je Rechenkern einen Puffer zu — ein Testlauf bekommt einen Faden.

    Gemessen an 32 Kernen: 1,6 GB privater Speicher je Prozess nach numpy,
    scipy, trimesh und manifold3d, mit einem Faden 0,1 GB. Ein Wert des
    Aufrufers bleibt, und die eigene Umgebung ändert sich nicht.
    """
    from tools import affected_tests

    if given is None:
        monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    else:
        monkeypatch.setenv("OPENBLAS_NUM_THREADS", given)
    seen: list[str | None] = []

    def fake_run(arguments: list[str], **kwargs: dict[str, str]) -> CompletedProcess[str]:
        seen.append(kwargs["env"].get("OPENBLAS_NUM_THREADS"))
        return CompletedProcess(arguments, 0, "1 passed in 0.01s\n", "")

    monkeypatch.setattr(affected_tests.subprocess, "run", fake_run)
    lines = [
        ["python", "-m", "pytest", "tests/test_a.py"],
        ["python", "-m", "pytest", "tests/test_b.py"],
    ]

    assert affected_tests.run(lines) == 0
    assert seen == [expected, expected]
    assert affected_tests.os.environ.get("OPENBLAS_NUM_THREADS") == given


def test_the_real_core_process_runs_the_plain_half_of_a_window_file(
    selection_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Im echten Kindprozess: der Test ohne Fenster läuft, der mit Fenster nicht.

    Die Fixture ``qt_app`` des Korpus scheitert, sobald sie läuft — ein
    Fenstertest im regulären Lauf wäre hier rot.
    """
    import os

    from tools import affected_tests

    root = selection_tree["plain"].parent.parent
    both = _write(
        root,
        "tests/test_both.py",
        "def test_window(inherited):\n    raise AssertionError('window ran')\n"
        "def test_without_window():\n    assert True\n",
    )
    monkeypatch.setattr(affected_tests, "affected", lambda _: ({both}, {both: "selbst geändert"}))
    module_root = str(Path(__file__).resolve().parent.parent)
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join((module_root, os.environ.get("PYTHONPATH", "")))
    )

    assert affected_tests.main([str(both), "--run"]) == 0, capsys.readouterr().out
    assert "1 passed, 1 deselected" in capsys.readouterr().out
