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
from subprocess import CompletedProcess

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


@pytest.fixture
def selection_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Ein reiner Sammlungskorpus; weder seine Fixtures noch Tests dürfen laufen."""
    import importlib

    from tools import affected_tests

    # Die Gesamtsuite importiert dieses Modul etwa über test_cache. Ohne
    # eigenes Wurzelpaket benutzte importlib für den Korpus denselben Namen
    # tests.conftest und verlor dadurch dessen mittelbare Fenster-Fixture.
    importlib.import_module("tests.conftest")
    _write(tmp_path, "__init__.py", "")
    _write(tmp_path, "tests/__init__.py", "")
    _write(
        tmp_path,
        "pytest.ini",
        "[pytest]\naddopts = --import-mode=importlib\nmarkers =\n"
        "    performance: Messung\n    windowed: Fenster im Kindprozess\n",
    )
    _write(
        tmp_path,
        "tests/conftest.py",
        "import pytest\n"
        "@pytest.fixture\n"
        "def qt_app():\n    raise AssertionError('fixture ran')\n"
        "@pytest.fixture\n"
        "def inherited(qt_app):\n    return qt_app\n",
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
    }
    monkeypatch.setattr(affected_tests, "ROOT", tmp_path)
    return files


@pytest.mark.parametrize("release", [False, True])
def test_commands_defer_windows_and_never_run_performance(
    selection_tree: dict[str, Path], release: bool
) -> None:
    """Auch gemischte Dateien folgen dem aufgelösten Fixture- und Markerbestand."""
    from tools.affected_tests import commands

    lines = commands(selection_tree.values(), release=release)

    assert len(lines) == (4 if release else 1)
    assert [argument for argument in lines[0] if argument.startswith("tests/")] == [
        "tests/test_plain.py"
    ]
    if release:
        assert [line[-1] for line in lines[1:]] == [
            "tests/test_marked.py",
            "tests/test_mixed.py",
            "tests/test_window.py",
        ]
    assert all("tests/test_performance.py" not in line for line in lines)


@pytest.mark.parametrize("source", ["environment", "configuration"])
@pytest.mark.parametrize(
    "filters",
    [
        "-k test_regular",
        "-k no_such_test",
        '-m "not windowed"',
        "-m performance",
        '-k test_regular -m "not performance and not windowed"',
        "--deselect=tests/test_window.py",
    ],
)
def test_file_groups_ignore_case_filters(
    selection_tree: dict[str, Path],
    source: str,
    filters: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Abwahl ändert weder Fensterbedarf noch die vorhandenen Kerndateien."""
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

    assert set(windowed) == {selection_tree[name] for name in ("window", "marked", "mixed")}
    assert plain == (selection_tree["plain"],)
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
def test_a_filtered_window_file_is_wholly_deferred(
    selection_tree: dict[str, Path],
    source: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Auch der ausdrücklich gewählte reine Fall einer Fensterdatei läuft erst im Release."""
    from tools import affected_tests

    window = selection_tree["marked"]
    filters = ["-k", "test_regular", "-m", "not windowed"]
    if source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", '-k test_regular -m "not windowed"')
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({window}, {window: "selbst geändert"})
    )
    monkeypatch.setattr(affected_tests, "run", lambda _: pytest.fail("a window file was started"))

    assert (
        affected_tests.main([str(window), "--run", *(filters if source == "command" else [])]) == 0
    )
    output = capsys.readouterr().out
    assert "tests/test_marked.py" in output
    assert "Zurückgestellt" in output
    assert "kein Testlauf gestartet" in output


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
    from tools import affected_tests

    window = selection_tree["window"]
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({window}, {window: "selbst geändert"})
    )
    monkeypatch.setattr(affected_tests, "run", lambda _: pytest.fail("a test process was started"))

    assert affected_tests.main([str(window), mode]) == 0

    output = capsys.readouterr().out
    assert "tests/test_window.py" in output
    if mode == "--why":
        assert "selbst geändert" in output
        assert "Zurückgestellt" not in output
    else:
        assert "Zurückgestellt" in output
        assert "kein Testlauf gestartet" in output


def test_an_only_performance_selection_does_not_start_empty_pytest(
    selection_tree: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tools import affected_tests

    performance = selection_tree["performance"]
    monkeypatch.setattr(
        affected_tests, "affected", lambda _: ({performance}, {performance: "selbst geändert"})
    )
    monkeypatch.setattr(affected_tests, "run", lambda _: pytest.fail("empty pytest was started"))

    assert affected_tests.main([str(performance), "--run", "--release"]) == 0
    assert "kein Testlauf gestartet" in capsys.readouterr().out


def test_a_truly_empty_collection_stays_an_error(tmp_path: Path) -> None:
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
    from tools import affected_tests, run_suite_isolated

    plain, window, performance = [tmp_path / name for name in ("plain", "window", "performance")]
    monkeypatch.setattr(run_suite_isolated, "chosen_files", lambda _: [plain, window, performance])
    monkeypatch.setattr(affected_tests, "split_windowed", lambda _: ([window], [plain]))
    calls: list[list[str]] = []

    def finish(arguments: list[str], **_options: object) -> CompletedProcess[str]:
        calls.append(arguments)
        return CompletedProcess(arguments, 0, "1 passed in 0.01s\n", "")

    monkeypatch.setattr(run_suite_isolated.subprocess, "run", finish)

    assert run_suite_isolated.main(["--release"] if release else []) == 0
    assert [line[-1] for line in calls] == [str(plain), *([str(window)] if release else [])]
    assert all(line[4:6] == ["-m", "not performance"] for line in calls)


@pytest.mark.parametrize("exit_code", [0, 5, 139])
def test_a_successful_summary_cannot_hide_the_process_exit(
    monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    from tools import affected_tests

    monkeypatch.setattr(
        affected_tests.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, exit_code, "1 passed in 0.01s\n", ""),
    )
    assert affected_tests.run([["python", "-m", "pytest", "tests/test_plain.py"]]) == (
        0 if exit_code == 0 else 1
    )
