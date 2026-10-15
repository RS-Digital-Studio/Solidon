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


@pytest.fixture(scope="module")
def real_graph() -> ImportGraph:
    """Der Importgraph des echten Baums, einmal je Modul gebaut.

    Ein Bau liest jede Datei unter ``app/``, ``tools/`` und ``tests/`` und kostet 15 bis
    25 s; sechs Fälle bauten ihn je einmal. Keiner ändert Graph oder Baum.
    """
    return ImportGraph()


def test_module_name_strips_init_and_uses_the_given_root(tmp_path: Path) -> None:
    """Ein Paket heißt nach seinem Ordner, ein Modul nach seiner Datei — relativ zur genannten
    Wurzel.
    """
    assert module_name(tmp_path / "app" / "core" / "__init__.py", tmp_path) == "app.core"
    assert module_name(tmp_path / "app" / "core" / "units.py", tmp_path) == "app.core.units"


def test_a_changed_module_selects_direct_indirect_typed_and_tree_readers(tree: Path) -> None:
    """Eine geänderte Kerndatei wählt, wer sie direkt, mittelbar oder nur für Typen importiert,
    dazu jeden, der ihren Ordner liest — und nennt je Datei den Grund.
    """
    files, reasons = affected([tree / "app" / "x.py"], ImportGraph(tree))

    assert _names(files, tree) == {
        "tests/test_direct.py",
        "tests/test_indirect.py",
        "tests/test_typed.py",
        "tests/test_reader.py",
    }
    assert reasons[tree / "tests" / "test_reader.py"] == (
        "liest app/**/*.py (tests/test_reader.py:2)"
    )
    assert reasons[tree / "tests" / "test_indirect.py"] == "importiert eine geänderte Datei"


def test_an_unrelated_module_selects_only_the_tree_readers(tree: Path) -> None:
    """``app.z`` importiert niemand außer ``test_unrelated`` — und der Baumleser sieht ``app/``."""
    files, _ = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py", "tests/test_reader.py"}


def test_a_flat_glob_reads_the_tree_too(tree: Path) -> None:
    """CS-6, RM-725: Wer den Baum über ``glob`` liest, statt ihn zu importieren, sieht eine
    Änderung in dem Ordner, den er liest — auch über das Modul ``glob``, auch unter anderem
    Namen, auch über ``os.walk`` und ``Path.walk`` (H-2)."""
    for name, text in (
        ("test_globber", "from pathlib import Path\nFILES = Path('app').glob('*.py')\n"),
        ("test_globmodule", "import glob\nFILES = glob.glob('app/*.py')\n"),
        ("test_renamed", "from glob import glob as find\nFILES = find('app/*.py')\n"),
        ("test_oswalk", "import os\nFILES = list(os.walk('app'))\n"),
        ("test_pathwalk", "from pathlib import Path\nFILES = list(Path('app').walk())\n"),
    ):
        _write(tree, f"tests/{name}.py", text)

    files, reasons = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert {
        "tests/test_globber.py",
        "tests/test_globmodule.py",
        "tests/test_renamed.py",
        "tests/test_oswalk.py",
        "tests/test_pathwalk.py",
    } <= _names(files, tree)
    assert reasons[tree / "tests" / "test_globber.py"] == (
        "liest app/*.py (tests/test_globber.py:2)"
    )


def test_only_a_glob_that_can_meet_python_reads_the_sources(tree: Path) -> None:
    """RQ-4: Ein ``glob`` auf Temp-Dateien oder Schriften liest keine Quellen und wählt bei
    einer Codeänderung nichts; ``ast.walk`` geht über einen Syntaxbaum, nicht über einen
    Ordner (H-2). Was ``*.py``, ``*`` oder ein offenes Muster in einem Ordner des Baums trifft,
    bleibt drin. Ein Ordner, der sich nicht auflösen lässt, zählt nur mit einem Muster, das
    Python nennt — ``rglob("*")`` über ihn geht über Programme und Archive —, wird aber
    an der Aufrufstelle zum Ordner, den das Argument nennt."""
    for name, text in (
        ("test_temp", "from pathlib import Path\nLEFT = Path('app').glob('*.tmp')\n"),
        ("test_fonts", "from pathlib import Path\nFONTS = Path('app').rglob('*.ttf')\n"),
        ("test_syntax", "import ast\nNODES = list(ast.walk(ast.parse('x')))\n"),
        ("test_any", "from pathlib import Path\nALL = Path('app').glob('*')\n"),
        ("test_open", "from pathlib import Path\nFOUND = Path('app').glob(f'{NAME}*')\n"),
        ("test_unknown_any", "def files(folder):\n    return sorted(folder.rglob('*'))\n"),
        ("test_unknown_py", "def files(folder):\n    return sorted(folder.rglob('*.py'))\n"),
        (
            "test_copies_app",
            "from pathlib import Path\nfrom tools.copy import copy\nX = copy(Path('app'))\n",
        ),
    ):
        _write(tree, f"tests/{name}.py", text)
    _write(tree, "tools/copy.py", "def copy(source):\n    return list(source.rglob('*'))\n")

    files, _ = affected([tree / "app" / "z.py"], ImportGraph(tree))

    names = _names(files, tree)
    assert (
        not {
            "tests/test_temp.py",
            "tests/test_fonts.py",
            "tests/test_syntax.py",
            "tests/test_unknown_any.py",
        }
        & names
    )
    assert {
        "tests/test_any.py",
        "tests/test_open.py",
        "tests/test_unknown_py.py",
        "tests/test_copies_app.py",
    } <= names


def test_a_listing_through_git_or_a_tool_loaded_by_path_reads_too(tree: Path) -> None:
    """Gemessen an der Lesemessung aller Testdateien: ``test_source_escapes`` liest jede
    ``.md`` über ``git ls-files``, ``test_delivery_tools`` den Baum über ein Werkzeug, das es
    mit ``spec_from_file_location`` lädt. Beide fehlten, sobald ein unbekannter Ordner nicht
    mehr jeden Ort liest. Eine Lesestelle zählt auch für eine geänderte Datei, die kein
    Python ist."""
    _write(
        tree,
        "tests/test_markdown.py",
        "import subprocess\n"
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "def test_markdown():\n"
        "    subprocess.run(['git', 'ls-files', '-co', '--', '*.md'], cwd=ROOT)\n",
    )
    _write(
        tree,
        "tests/test_app_files.py",
        "import subprocess\n"
        "def test_app():\n"
        "    subprocess.run(['git', 'ls-files', '-z', '--', 'app'])\n",
    )
    _write(
        tree,
        "tools/digest.py",
        "def code_digest(root):\n    return sorted((root / 'app').rglob('*'))\n",
    )
    _write(
        tree,
        "tests/test_loaded.py",
        "import importlib.util\n"
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "def test_digest():\n"
        "    script = ROOT / 'tools' / 'digest.py'\n"
        "    spec = importlib.util.spec_from_file_location('digest_copy', script)\n"
        "    driver = importlib.util.module_from_spec(spec)\n"
        "    assert driver.code_digest(ROOT)\n",
    )
    notes = _write(tree, "docs/NOTES.md", "# Notizen\n")
    graph = ImportGraph(tree)

    files, reasons = affected([tree / "app" / "z.py"], graph)

    assert {"tests/test_app_files.py", "tests/test_loaded.py"} <= _names(files, tree)
    assert "tests/test_markdown.py" not in _names(files, tree)
    assert reasons[tree / "tests" / "test_loaded.py"] == "liest app/**/* über tools/digest.py:2"

    files, reasons = affected([notes], graph)

    assert "tests/test_markdown.py" in _names(files, tree)
    assert reasons[tree / "tests" / "test_markdown.py"] == (
        "liest **/*.md (tests/test_markdown.py:5)"
    )


def test_a_test_reading_through_a_source_helper_is_a_tree_reader(tree: Path) -> None:
    """E5: Ein Wächter, der den Baum nur über einen gemeinsamen Helfer liest, steht in keinem
    eigenen Text als Baumleser — er wird über die Funktion gewählt, die er dort bezieht, auch
    über einen Zwischenhelfer und aus ``tools/``; der Ordner kommt aus seinem Argument. Der
    Helfer selbst sammelt keinen Test und gehört nicht in die Auswahl."""
    _write(
        tree,
        "tests/source_tree.py",
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parent.parent\n"
        "def files(folder):\n"
        "    return sorted((ROOT / folder).rglob('*.py'))\n",
    )
    _write(
        tree, "tests/test_guard.py", "from tests import source_tree\nX = source_tree.files('app')\n"
    )
    _write(tree, "tests/guard_helpers.py", "from tests.source_tree import files\n")
    _write(
        tree, "tests/test_far_guard.py", "from tests.guard_helpers import files\nX = files('app')\n"
    )
    _write(
        tree,
        "tests/test_tests_guard.py",
        "from tests import source_tree\nX = source_tree.files('tests')\n",
    )
    _write(tree, "tools/code_scan.py", "def scan(root):\n    return sorted(root.glob('**/*.py'))\n")
    _write(
        tree,
        "tests/test_scan_guard.py",
        "from pathlib import Path\nfrom tools.code_scan import scan\nX = scan(Path('app'))\n",
    )

    files, reasons = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert {
        "tests/test_guard.py",
        "tests/test_far_guard.py",
        "tests/test_scan_guard.py",
    } <= _names(files, tree)
    assert "tests/test_tests_guard.py" not in _names(files, tree), "liest nur tests/"
    assert reasons[tree / "tests" / "test_guard.py"] == (
        "liest app/**/*.py über tests/source_tree.py:4"
    )
    assert reasons[tree / "tests" / "test_scan_guard.py"] == (
        "liest app/**/*.py über tools/code_scan.py:2"
    )
    assert all(path.name.startswith("test_") for path in files), sorted(files)


def test_only_who_borrows_the_reading_function_reads_through_a_test_file(tree: Path) -> None:
    """RQ-3: Wie ``test_wording`` die Quellen über ``application_sources`` aus
    ``test_text_length`` liest, kann auch eine Testdatei ihren Baumgang verleihen — aber nur
    an den, der die lesende Funktion bezieht. ``test_boolean_empty_result`` leiht ``box`` aus
    ``test_boolean``, das an anderer Stelle ``rglob`` trägt; durch ``box`` liest es nichts."""
    _write(
        tree,
        "tests/test_lengths.py",
        "from pathlib import Path\n"
        "def application_sources():\n"
        "    return sorted(Path('app').rglob('*.py'))\n"
        "def box():\n"
        "    return None\n",
    )
    _write(
        tree,
        "tests/test_words.py",
        "from tests.test_lengths import application_sources\nX = application_sources()\n",
    )
    _write(tree, "tests/test_empty_result.py", "from tests.test_lengths import box\nX = box()\n")

    files, reasons = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert "tests/test_empty_result.py" not in _names(files, tree)
    assert reasons[tree / "tests" / "test_words.py"] == (
        "liest app/**/*.py über tests/test_lengths.py:3"
    )
    assert reasons[tree / "tests" / "test_lengths.py"] == (
        "liest app/**/*.py (tests/test_lengths.py:3)"
    )


def test_a_helper_listing_a_foreign_tree_is_no_source_reader(tree: Path) -> None:
    """Die Gegenrichtung zu E5: Ein Helfer, der ein Paketarchiv in einem Temp-Ordner
    durchgeht (``rglob("*")``), liest keine Quellen. Seine Importeure laufen bei einer
    Änderung an ``app/`` nicht mit — sonst zöge ``tests/helpers.py`` jede zweite Testdatei
    hinein —, und er selbst steht auch dann nicht in der Auswahl, wenn er das Wort ``rglob``
    trägt."""
    _write(tree, "tests/archive.py", "def pack(tree):\n    return sorted(tree.rglob('*'))\n")
    _write(
        tree,
        "tests/test_archive.py",
        "from tests.archive import pack\ndef test_pack(tmp_path):\n    pack(tmp_path / 'x')\n",
    )

    files, _ = affected([tree / "app" / "z.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py", "tests/test_reader.py"}


def test_a_file_named_by_a_helper_selects_the_tests_behind_it(tree: Path) -> None:
    """Nennt ein Helfer unter ``tests/`` eine Datei, zählen die Testdateien, die ihn
    importieren — der Helfer allein sammelt keinen Test, und sein Importeur liefe nicht."""
    _write(tree, "tests/roadmap_helper.py", "TEXT = 'ROADMAP.md'\n")
    _write(tree, "tests/test_roadmap_view.py", "from tests.roadmap_helper import TEXT\n")

    files, reasons = affected([tree / "ROADMAP.md"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_roadmap.py", "tests/test_roadmap_view.py"}
    assert reasons[tree / "tests" / "test_roadmap_view.py"] == (
        "über tests/roadmap_helper.py: nennt ROADMAP.md"
    )
    assert reasons[tree / "tests" / "test_roadmap.py"] == "nennt ROADMAP.md"


def test_a_tool_or_a_deleted_module_named_by_a_helper_selects_the_tests_behind_it(
    tree: Path,
) -> None:
    """Dieselbe Regel für die zwei anderen Namenswege: ein Werkzeug, das seine Tests über den
    Pfad laden, und ein gelöschtes Modul, das nur noch als Text vorkommt — nennt es ein
    Helfer, zählen dessen Importeure, nicht er."""
    tool = _write(tree, "tools/runner_unit.py", "VALUE = 1\n")
    _write(tree, "tests/runner_loader.py", "SCRIPT = 'runner_unit.py'\n")
    _write(tree, "tests/test_runner.py", "from tests.runner_loader import SCRIPT\n")
    _write(tree, "tests/module_names.py", "NAME = 'app.x'\n")
    _write(tree, "tests/test_module_names.py", "from tests.module_names import NAME\n")

    files, reasons = affected([tool], ImportGraph(tree))

    assert reasons[tree / "tests" / "test_runner.py"] == (
        "über tests/runner_loader.py: nennt runner_unit.py"
    )
    assert all(path.name.startswith("test_") for path in files), sorted(files)

    removed = tree / "app" / "x.py"
    removed.unlink()
    files, reasons = affected([removed], ImportGraph(tree))

    assert reasons[tree / "tests" / "test_module_names.py"] == (
        "über tests/module_names.py: nennt app.x, und die Datei ist gelöscht"
    )
    assert all(path.name.startswith("test_") for path in files), sorted(files)


def test_a_helper_names_a_file_in_strings_and_for_its_direct_importers_only(tree: Path) -> None:
    """RQ-2: ``tests/php_probe.py`` nannte ``build.yml`` nur im Docstring und in einer
    Fehlermeldung, und über ``tests/helpers.py`` hingen 189 Testdateien daran. Ein Kommentar
    oder Docstring nennt nichts; was ein Helfer in einer Zeichenkette nennt, liest er für
    die Testdateien, die ihn direkt importieren — ein Zwischenhelfer trägt es nicht weiter."""
    workflow = _write(tree, ".github/workflows/build.yml", "name: Bau\n")
    _write(
        tree,
        "tests/php_probe.py",
        '"""Liest, was build.yml dem Lauf mitgibt."""\n# siehe build.yml\nVALUE = 1\n',
    )
    _write(tree, "tests/test_probe_user.py", "from tests.php_probe import VALUE\n")
    _write(tree, "tests/reader_helper.py", "WORKFLOW = 'build.yml'\n")
    _write(tree, "tests/between.py", "from tests.reader_helper import WORKFLOW\n")
    _write(tree, "tests/test_direct_user.py", "from tests.reader_helper import WORKFLOW\n")
    _write(tree, "tests/test_far_user.py", "from tests.between import WORKFLOW\n")
    _write(tree, "tests/test_comment.py", "# build.yml steht hier nur im Kommentar\nX = 1\n")
    _write(tree, "tests/test_names_it.py", "NAME = 'build.yml'\n")

    files, reasons = affected([workflow], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_direct_user.py", "tests/test_names_it.py"}
    assert reasons[tree / "tests" / "test_direct_user.py"] == (
        "über tests/reader_helper.py: nennt build.yml"
    )


def test_a_data_folder_counts_by_its_path_not_by_its_last_name(tree: Path) -> None:
    """RQ-5: Eine Datei unter ``app/core/knowledge/data`` wählte jedes Modul, das irgendeinen
    Ordner ``data`` nennt — ``tests/data``, ``geom/data/fonts``, Temp-Ordner. Jetzt zählt, wohin
    ein Pfadausdruck zeigt, auch über eine Konstante (``EXAMPLES_DIRNAME``) und auch, wenn er
    eine Ebene über dem Ordner offen bleibt (``ROOT / "website" / sprache``); ein Text zählt,
    wenn seine Teile zum Pfad passen. Ein bloßes ``"data"`` liest nichts."""
    rules = _write(tree, "app/core/knowledge/data/rules.toml", "version = 1\n")
    _write(tree, "app/core/__init__.py", "")
    _write(tree, "app/core/knowledge/__init__.py", "")
    for module, text in (
        ("rules", "from pathlib import Path\nDATA = Path(__file__).parent / 'data'\n"),
        (
            "tables",
            "from pathlib import Path\nDIRNAME = 'data'\nDIR = Path(__file__).parent / DIRNAME\n",
        ),
        (
            "pick",
            "from pathlib import Path\nHERE = Path(__file__).parent.parent / 'knowledge'\n"
            "def table(kind):\n    return HERE / kind\n",
        ),
    ):
        _write(tree, f"app/core/knowledge/{module}.py", text)
        _write(tree, f"tests/test_{module}.py", f"from app.core.knowledge import {module}\n")
    _write(
        tree,
        "tests/corpus.py",
        "from pathlib import Path\nDATA = Path(__file__).parent / 'data'\n",
    )
    _write(tree, "tests/test_corpus.py", "from tests.corpus import DATA\n")
    _write(tree, "tests/test_text_path.py", "WHERE = 'knowledge/data/'\n")
    _write(tree, "tests/test_other_text.py", "WHERE = 'tests/data/'\n")
    _write(tree, "tests/test_bare.py", "ROW = {'data': 1}\n")

    files, reasons = affected([rules], ImportGraph(tree))

    assert _names(files, tree) == {
        "tests/test_rules.py",
        "tests/test_tables.py",
        "tests/test_pick.py",
        "tests/test_text_path.py",
    }
    assert reasons[tree / "tests" / "test_rules.py"] == (
        "hängt an einem Modul, das app/core/knowledge/data/ liest"
    )


def test_an_operation_module_selects_the_tests_that_name_its_operations(tree: Path) -> None:
    """CS-31: ``chamber_ops`` lädt nur eine Namensliste in ``bootstrap``; ``test_chamber_ops``
    ruft die Op über das Register und importiert das Modul nie. Die Namen der registrierten
    Ops und Bausteine, statisch gelesen, sind die Kante — genau der Name als Zeichenkette,
    nicht ein längerer, nicht ein Kommentar und nicht der Argumentname von ``parametrize``
    (``test_slicer_placement`` hieß über ``parametrize("pattern", …)`` Leser von
    ``scene.ops``)."""
    module = _write(
        tree,
        "app/chamber_ops.py",
        "from app.registry import register_op\n"
        "NAME = 'zz_resize_chamber'\n"
        "@register_op(name=NAME, title='Kammer')\n"
        "def resize(ctx):\n    return ctx\n",
    )
    _write(
        tree,
        "app/panels.py",
        "from app.parts import register_part\n"
        "@register_part(name='zz_panel', title='Platte')\n"
        "def panel(ctx):\n    return ctx\n",
    )
    _write(tree, "tests/test_chamber.py", "RESULT = run_op('zz_resize_chamber')\n")
    _write(tree, "tests/test_longer.py", "RESULT = run_op('zz_resize_chamber_twice')\n")
    _write(tree, "tests/test_mentioned.py", "# zz_resize_chamber\nX = 1\n")
    _write(
        tree,
        "tests/test_argument.py",
        "import pytest\n"
        "@pytest.mark.parametrize('zz_resize_chamber', [1])\n"
        "def test_one(zz_resize_chamber):\n    pass\n"
        "@pytest.mark.parametrize(('zz_resize_chamber', 'b'), [(1, 2)])\n"
        "def test_two(zz_resize_chamber, b):\n    pass\n"
        "@pytest.mark.parametrize(argnames='zz_resize_chamber', argvalues=[1])\n"
        "def test_three(zz_resize_chamber):\n    pass\n",
    )
    _write(tree, "tests/test_panel.py", "PART = 'zz_panel'\n")

    files, reasons = affected([module], ImportGraph(tree))

    assert {"tests/test_chamber.py"} <= _names(files, tree)
    assert not {
        "tests/test_longer.py",
        "tests/test_mentioned.py",
        "tests/test_argument.py",
        "tests/test_panel.py",
    } & (_names(files, tree))
    assert reasons[tree / "tests" / "test_chamber.py"] == ("nennt die Operation zz_resize_chamber")
    files, reasons = affected([tree / "app" / "panels.py"], ImportGraph(tree))
    assert reasons[tree / "tests" / "test_panel.py"] == "nennt den Baustein zz_panel"


def test_an_operation_module_reaches_the_tests_of_the_ops_that_import_it(tree: Path) -> None:
    """``closure_ops`` importiert ``chamber_ops``; ``test_closure_ops`` nennt nur
    ``resize_closure`` und lief bei einer Änderung an ``chamber_ops`` nicht mit, obwohl jede
    Verschlussop die Kammer rechnet (Messung gegen die Ausführung)."""
    chamber = _write(
        tree,
        "app/chamber_ops.py",
        "from app.registry import register_op\n"
        "@register_op(name='zz_resize_chamber')\ndef resize(ctx):\n    return ctx\n",
    )
    _write(
        tree,
        "app/closure_ops.py",
        "from app.chamber_ops import resize\nfrom app.registry import register_op\n"
        "@register_op(name='zz_resize_closure')\ndef close(ctx):\n    return resize(ctx)\n",
    )
    _write(tree, "tests/test_closure.py", "RESULT = run_op('zz_resize_closure')\n")

    _files, reasons = affected([chamber], ImportGraph(tree))

    assert reasons[tree / "tests" / "test_closure.py"] == "nennt die Operation zz_resize_closure"


def test_a_test_over_the_whole_registry_or_the_examples_runs_for_every_operation_module(
    tree: Path,
) -> None:
    """``test_registry_consistency`` geht über ``REGISTRY.all()``, ``test_examples`` rechnet die
    Beispielprojekte — beide führen ``chamber_ops`` aus, ohne ``resize_chamber`` zu nennen
    (Entscheidung Koordinator). Eine Frage nach einem Namen, ein Register als Gegenstand von
    ``setattr`` und eine bloße Liste der Beispieldateien gehen nicht über alles; ein Modul, das
    keine Op registriert, wählt keinen dieser Tests."""
    chamber = _write(
        tree,
        "app/chamber_ops.py",
        "from app.registry import register_op\n"
        "@register_op(name='zz_resize_chamber')\ndef resize(ctx):\n    return ctx\n",
    )
    registry = "from app.core.registry import REGISTRY, PARTS\n"
    over = {
        "test_all": "NAMES = [spec.name for spec in REGISTRY.all()]\n",
        "test_groups": "def test_groups():\n    for group in PARTS.by_group():\n        pass\n",
        "test_passed": "ROWS = rows(registry=REGISTRY)\n",
        "test_looped": "NAMES = [spec for spec in REGISTRY]\n",
        "test_example_import": "from app.core import examples\n",
        "test_example_load": "from pathlib import Path\n"
        "from app.core.scene.project import load\n"
        "PROJECTS = [load(p) for p in Path('app/examples').glob('*.p3d')]\n",
    }
    single = {
        "test_get": registry + "SPEC = REGISTRY.get('zz_other')\nKNOWN = REGISTRY.has('zz_x')\n",
        "test_patch": registry + "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(REGISTRY, '_ops', {})\n",
        "test_example_list": "from pathlib import Path\n"
        "FILES = sorted(Path('app/examples').glob('*.p3d'))\n",
    }
    for name, text in over.items():
        _write(tree, f"tests/{name}.py", (registry if "REGISTRY" in text else "") + text)
    for name, text in single.items():
        _write(tree, f"tests/{name}.py", text)
    _write(
        tree,
        "tests/helpers_registry.py",
        registry + "def every():\n    return REGISTRY.in_registration_order()\n",
    )
    _write(tree, "tests/test_helped.py", "from tests import helpers_registry\n")
    graph = ImportGraph(tree)

    files, reasons = affected([chamber], graph)

    chosen = _names(files, tree)
    assert {f"tests/{name}.py" for name in over} | {"tests/test_helped.py"} <= chosen
    assert not {f"tests/{name}.py" for name in single} & chosen
    assert reasons[tree / "tests" / "test_all.py"] == "geht über das ganze Register"
    assert reasons[tree / "tests" / "test_example_import.py"] == "rechnet die Beispielprojekte"
    files, _reasons = affected([tree / "app" / "z.py"], graph)
    assert not {f"tests/{name}.py" for name in over} & _names(files, tree)


def test_a_data_file_under_app_counts_as_a_change_to_the_module_that_reads_it(
    tree: Path,
) -> None:
    """``materials.toml`` liest ``knowledge/profiles.py``, und 33 von 78 Testdateien, die sie
    gemessen öffnen, erreichen ``profiles`` erst über eine Op (Entscheidung Koordinator: wie
    eine Änderung am Leser). Gelesen wird über den Pfad der Datei, über einen offenen Namen
    im Ordner, wenn das Modul die Datei nennt, oder über eine Lesestelle, deren Muster sie
    deckt — nicht über die gleichnamige Datei im Nutzerordner und nicht über eine Kopie des
    ganzen Baums (``make_installer`` über ``app/**/*``)."""
    _write(
        tree,
        "app/knowledge/profiles.py",
        "from pathlib import Path\nDATA = Path(__file__).parent / 'data'\n"
        "def printers():\n    return (DATA / 'printers.toml').read_text()\n"
        "def shipped(table):\n    return (DATA / table).read_text()\n"
        "MATERIALS = shipped('materials.toml')\n",
    )
    _write(
        tree,
        "app/knowledge/user.py",
        "from pathlib import Path\nOWN = Path.home() / 'knowledge' / 'data'\n"
        "def own():\n    return (OWN / 'colours.toml').read_text()\n",
    )
    _write(
        tree,
        "app/catalog.py",
        "from pathlib import Path\nLOCALES = Path(__file__).parent / 'locales'\n"
        "def languages():\n    return sorted(LOCALES.glob('*.json'))\n",
    )
    _write(
        tree,
        "tools/installer.py",
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        "def stage():\n    return sorted((ROOT / 'app').rglob('*'))\n",
    )
    _write(tree, "tools/release.py", "from tools import installer\n")
    _write(tree, "app/ops.py", "from app.knowledge import profiles\nfrom app import catalog\n")
    _write(tree, "tests/test_deep.py", "from app.ops import profiles\n")
    _write(tree, "tests/test_user.py", "from app.knowledge import user\n")
    _write(tree, "tests/test_release.py", "from tools import release\n")
    for name in ("materials.toml", "printers.toml", "colours.toml"):
        _write(tree, f"app/knowledge/data/{name}", "[x]\n")
    _write(tree, "app/locales/en.json", "{}\n")
    graph = ImportGraph(tree)

    for changed in ("materials.toml", "printers.toml"):
        files, reasons = affected([tree / "app" / "knowledge" / "data" / changed], graph)
        assert reasons[tree / "tests" / "test_deep.py"] == (
            f"hängt an app/knowledge/profiles.py, das {changed} liest"
        )
        assert not {"tests/test_user.py", "tests/test_release.py"} & _names(files, tree)
    files, _reasons = affected([tree / "app" / "knowledge" / "data" / "colours.toml"], graph)
    assert "tests/test_deep.py" not in _names(files, tree)
    files, reasons = affected([tree / "app" / "locales" / "en.json"], graph)
    assert reasons[tree / "tests" / "test_deep.py"] == "hängt an app/catalog.py, das en.json liest"
    _write(tree, "app/defaults.toml", "[x]\n")
    files, _reasons = affected([tree / "app" / "defaults.toml"], graph)
    assert "tests/test_release.py" not in _names(files, tree)


def test_an_operation_reached_through_a_created_step_or_a_project_file_selects_its_tests(
    tree: Path,
) -> None:
    """Gemessen gegen die Ausführung fehlten zehn Paare (Entscheidung Koordinator: 0 von 990):
    ``test_import_placement`` ruft nur ``import_plan``, und ``ingest/plan.py`` legt den Schritt
    ``load`` oder ``load_step`` an; ``test_platform_identity`` nennt ``insert_pipe_clamp``, die
    Op des Bausteins ``pipe_clamp``; ``test_orphans`` lädt ``weg4-stein-formen.p3d``, die
    ``sculpt_strokes`` rechnet. Ein Vergleich mit dem Namen legt keinen Schritt an, und eine
    Projektdatei ohne die Op lädt sie nicht."""
    import json
    import zipfile

    loading = _write(
        tree,
        "app/load_ops.py",
        "from app.registry import register_op\n"
        "@register_op(name='zz_load')\ndef load(ctx):\n    return ctx\n"
        "@register_op(name='zz_load_step')\ndef load_step(ctx):\n    return ctx\n",
    )
    _write(
        tree,
        "app/plan.py",
        "def loader(suffix):\n    if suffix == '.step':\n        return 'zz_load_step'\n"
        "    return 'zz_other'\n"
        "def draft():\n    return OperationDraft(op='zz_load')\n",
    )
    _write(tree, "app/history.py", "def special(entry):\n    return entry.op == 'zz_load'\n")
    _write(tree, "tests/test_import.py", "from app import plan\n")
    _write(tree, "tests/test_history_only.py", "from app import history\n")
    part = _write(
        tree,
        "app/mounting.py",
        "from app.parts import register_part\n"
        "@register_part(name='zz_pipe_clamp')\ndef clamp(ctx):\n    return ctx\n",
    )
    _write(tree, "tests/test_part_op.py", "STEP = run_op('insert_zz_pipe_clamp')\n")
    sculpt = _write(
        tree,
        "app/sculpt.py",
        "from app.registry import register_op\n"
        "@register_op(name='zz_sculpt')\ndef sculpt(ctx):\n    return ctx\n",
    )
    for name, ops in (("stein.p3d", ["create_box", "zz_sculpt"]), ("leer.p3d", ["create_box"])):
        path = tree / "website" / "teile" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("project.json", json.dumps({"ops": [{"op": op} for op in ops]}))
    _write(tree, "tests/test_stone.py", "PROJECT = ('website', 'teile', 'stein.p3d')\n")
    _write(tree, "tests/test_empty.py", "PROJECT = ('website', 'teile', 'leer.p3d')\n")
    graph = ImportGraph(tree)

    files, reasons = affected([loading], graph)
    assert reasons[tree / "tests" / "test_import.py"] == (
        "über app/plan.py: legt einen Schritt zz_load an"
    )
    assert "tests/test_history_only.py" not in _names(files, tree)
    _files, reasons = affected([part], graph)
    assert reasons[tree / "tests" / "test_part_op.py"] == (
        "nennt die Operation insert_zz_pipe_clamp"
    )
    files, reasons = affected([sculpt], graph)
    assert reasons[tree / "tests" / "test_stone.py"] == "lädt stein.p3d mit zz_sculpt"
    assert "tests/test_empty.py" not in _names(files, tree)


def test_a_data_file_under_tests_or_website_counts_as_a_change_to_its_reader(tree: Path) -> None:
    """``tests/data/function_scenes.toml`` liest ``tools/function_scenes.py``, und
    ``test_function_export_preparation`` erreicht es über ``tools/function_bench.py``;
    ``website/site.js`` liest ``tools/make_changelog.py`` für ``test_changelog_website``
    (Entscheidung Koordinator: dieselbe Regel wie unter ``app/``)."""
    _write(
        tree,
        "tools/scenes.py",
        "from pathlib import Path\n"
        "SCENES = Path(__file__).resolve().parents[1] / 'tests' / 'data' / 'scenes.toml'\n"
        "def load():\n    return SCENES.read_text()\n",
    )
    _write(tree, "tools/bench.py", "from tools import scenes\n")
    _write(
        tree,
        "tools/changelog.py",
        "from pathlib import Path\n"
        "SITE = Path(__file__).resolve().parents[1] / 'website'\n"
        "def script():\n    return (SITE / 'site.js').read_text()\n",
    )
    _write(tree, "tests/test_bench.py", "from tools import bench\n")
    _write(tree, "tests/test_changelog_pages.py", "from tools import changelog\n")
    _write(tree, "tests/data/scenes.toml", "[x]\n")
    _write(tree, "website/site.js", "x = 1;\n")
    graph = ImportGraph(tree)

    _files, reasons = affected([tree / "tests" / "data" / "scenes.toml"], graph)
    assert reasons[tree / "tests" / "test_bench.py"] == (
        "hängt an tools/scenes.py, das scenes.toml liest"
    )
    _files, reasons = affected([tree / "website" / "site.js"], graph)
    assert reasons[tree / "tests" / "test_changelog_pages.py"] == (
        "hängt an tools/changelog.py, das site.js liest"
    )


def test_an_application_module_reading_its_own_tree_lends_that_reading(tree: Path) -> None:
    """CS-32: ``app/i18n/extract.py`` liest die Quellen unter ``app/`` nach ``tr()``-Schlüsseln;
    ``tools/registry_dump.py`` ruft es, und ``test_registry_dump`` fehlte bei einem neuen Text
    unter ``app/ui``. Unter ``app/`` zählt nur ein Ordner im Repository — ein Nutzerordner,
    eine Umgebungsvariable oder ein offener Parameter zählte sonst bei jeder Änderung."""
    _write(
        tree,
        "app/extract.py",
        "from pathlib import Path\n"
        "import os\n"
        "PACKAGE_DIR = Path(__file__).resolve().parent\n"
        "def message_ids():\n"
        "    return sorted(PACKAGE_DIR.rglob('*.py'))\n"
        "def user_parts():\n"
        "    return sorted((Path.home() / 'parts').rglob('*.py'))\n"
        "def profiles():\n"
        "    return sorted(Path(os.environ['APPDATA']).rglob('*.py'))\n"
        "def anything(folder):\n"
        "    return sorted(folder.rglob('*.py'))\n",
    )
    _write(
        tree,
        "tools/dump.py",
        "from app import extract\ndef registered():\n    return extract.message_ids()\n",
    )
    _write(tree, "tests/test_dump.py", "from tools import dump\nX = dump.registered()\n")
    _write(
        tree,
        "tests/test_user_parts.py",
        "from app import extract\nX = extract.user_parts()\nY = extract.profiles()\n"
        "Z = extract.anything(None)\n",
    )

    files, reasons = affected([tree / "app" / "ui_new.py"], ImportGraph(tree))

    assert "tests/test_dump.py" in _names(files, tree)
    assert reasons[tree / "tests" / "test_dump.py"] == "liest app/**/*.py über app/extract.py:5"
    assert "tests/test_user_parts.py" not in _names(files, tree)


def test_the_real_extraction_of_texts_reaches_the_registry_dump(real_graph: ImportGraph) -> None:
    """CS-32 gegen den echten Baum: Ein neuer Text unter ``app/ui`` ändert, was
    ``app/i18n/extract.py`` einsammelt, und ``tools/registry_dump.py`` schreibt es in den Abzug.
    ``test_registry_dump`` importiert ``gizmo`` nicht und lief bei einer Änderung dort nicht mit."""
    changed = real_graph.root / "app" / "ui" / "render" / "gizmo.py"

    _files, reasons = affected([changed], real_graph)

    reason = reasons.get(real_graph.root / "tests" / "test_registry_dump.py", "")
    assert reason.startswith("liest app/") and "app/i18n/extract.py" in reason, reason


def test_the_real_operation_modules_reach_the_tests_that_name_their_operations(
    real_graph: ImportGraph,
) -> None:
    """CS-31 gegen den echten Baum: ``chamber_ops``, ``closure_ops``, ``counter_form_ops`` und
    ``scene.ops`` lädt nur ``bootstrap`` über eine Namensliste; ihre Tests rufen die Ops beim
    Namen. ``test_slicer_placement`` nennt ``"pattern"`` nur als Argumentnamen von
    ``parametrize`` und bleibt draußen."""
    for module, test in (
        ("app/core/geom/chamber_ops.py", "test_chamber_ops.py"),
        ("app/core/geom/closure_ops.py", "test_closure_ops.py"),
        ("app/core/geom/counter_form_ops.py", "test_counter_form.py"),
        ("app/core/scene/ops.py", "test_scene_ops.py"),
    ):
        files, reasons = affected([real_graph.root / module], real_graph)

        reason = reasons.get(real_graph.root / "tests" / test, "")
        assert reason.startswith("nennt die Operation "), (module, reason)
    assert real_graph.root / "tests" / "test_slicer_placement.py" not in files, reasons.get(
        real_graph.root / "tests" / "test_slicer_placement.py"
    )


def test_the_real_operation_and_data_changes_reach_what_runs_them(
    real_graph: ImportGraph,
) -> None:
    """Gegen den echten Baum und die Messung der Ausführung: ``chamber_ops`` führen
    ``test_registry_consistency`` (ganzes Register), ``test_examples`` (Beispielprojekte) und
    ``test_closure_ops`` (über ``closure_ops``) aus, ohne ``resize_chamber`` zu nennen;
    ``materials.toml`` öffnen ``test_bore_mouth_resize`` und ``test_cli`` über eine Op und
    ``knowledge.profiles``. Die letzten zehn Paare der Messung: ``load_step`` über
    ``import_plan`` (``test_paint``), ``pipe_clamp`` als ``insert_pipe_clamp``
    (``test_platform_identity``), ``sculpt_strokes`` in ``weg4-stein-formen.p3d``
    (``test_orphans``); die letzten vier Lesungen: ``function_scenes.toml`` über
    ``tools.function_scenes``, ``icon.svg`` über ``tools.make_changelog``."""
    root = real_graph.root
    for module, tests in (
        (
            "app/core/geom/chamber_ops.py",
            ("test_registry_consistency.py", "test_examples.py", "test_closure_ops.py"),
        ),
        ("app/core/ingest/step_ops.py", ("test_paint.py", "test_exact_patterns.py")),
        ("app/core/knowledge/parts/mounting.py", ("test_platform_identity.py",)),
        ("app/core/geom/sculpt.py", ("test_orphans.py",)),
        ("app/core/knowledge/data/materials.toml", ("test_bore_mouth_resize.py", "test_cli.py")),
        ("tests/data/function_scenes.toml", ("test_function_export_preparation.py",)),
        ("website/icon.svg", ("test_changelog_website.py",)),
    ):
        files, _reasons = affected([root / module], real_graph)
        for test in tests:
            assert root / "tests" / test in files, (module, test)


def test_the_real_guards_are_chosen_for_any_change_under_app(real_graph: ImportGraph) -> None:
    """Gegen den echten Baum (E5, RM-725): Die Wächter, die den Baum über
    ``tools/code_index.py``, ``tests/source_tree.py`` oder eine andere Testdatei lesen,
    laufen bei einer Änderung an einem Modul mit, das sie nicht importieren — und kein
    Helfer steht in der Auswahl. Ohne den mittelbaren Weg fehlten ``test_leash``,
    ``test_native_keys`` und ``test_widget_lifetime``, seit sie über den Helfer lesen.

    Geändert ist ein Modul, das es nicht gibt — gelöscht oder noch nicht angelegt —
    und das deshalb niemand importiert: So hängt die Auswahl an keiner Importkante
    des heutigen Baums, nur am Lesen. Und nur an dem Ordner, den ein Wächter liest: Die
    Verbotsprüfungen über ``app/ui`` laufen bei einer Änderung unter ``perceive`` nicht mit,
    die über ``perceive`` schon."""
    graph = real_graph
    surface = graph.root / "app" / "ui" / "render" / "zz_not_yet_imported.py"
    perceive = graph.root / "app" / "core" / "perceive" / "zz_not_yet_imported.py"
    assert not surface.exists() and not perceive.exists()

    everywhere = (
        "test_patch_targets.py",
        "test_import_resolution.py",
        "test_wording.py",
        "test_source_readers.py",
    )
    surface_guards = ("test_leash.py", "test_native_keys.py", "test_widget_lifetime.py")
    core_guards = ("test_core_package_direction.py", "test_features.py")
    for changed, guards, others in (
        (surface, surface_guards, (*core_guards[:1], "test_activation.py")),
        (perceive, core_guards, (*surface_guards, "test_activation.py")),
    ):
        files, reasons = affected([changed], graph)

        # Zugesichert wird die Eigenschaft, nicht der Wortlaut: Liest eine Datei den Ordner
        # später an einer zweiten Stelle, ändert sich ihr Grund, nicht die Auswahl (RQ-9).
        for name in (*everywhere, *guards):
            assert reasons.get(graph.root / "tests" / name, "").startswith("liest "), name
        for name in others:
            assert graph.root / "tests" / name not in files, (name, changed)
        assert all(path.name.startswith("test_") for path in files)
        # Wer aus einer Testdatei nur einen Körper leiht, liest durch sie nichts (RQ-3).
        for name in ("test_boolean_empty_result.py", "test_surface_placement.py"):
            assert graph.root / "tests" / name not in files, name


def test_the_real_guards_over_tests_are_chosen_for_a_change_to_a_test(
    real_graph: ImportGraph,
) -> None:
    """Gegen den echten Baum: Eine reine Teständerung wählt die Wächter, die ``tests/``
    lesen — Querimporte und doppelte Definitionen, Sperrklinke, Verzeichniskarten und W4 —,
    aber keinen, der nur ``app/`` liest (RQ-1). Vorher wählte sie alle rund 150 Baumleser,
    und ``ci_selection`` fuhr dafür 47 Fensterprozesse auf Linux und macOS."""
    graph = real_graph
    changed = graph.root / "tests" / "test_wording.py"
    assert changed.is_file()

    files, _ = affected([changed], graph)

    for name in (
        "test_toolchain.py",
        "test_size_ratchet.py",
        "test_directory_docs.py",
        "test_source_readers.py",
    ):
        assert graph.root / "tests" / name in files, name
    for name in ("test_leash.py", "test_features.py", "test_ui.py", "test_widget_lifetime.py"):
        assert graph.root / "tests" / name not in files, name


def test_a_changed_test_file_selects_itself(tree: Path) -> None:
    """Eine geänderte Testdatei ist selbst betroffen — der Baumleser über ``app/`` nicht."""
    files, reasons = affected([tree / "tests" / "test_unrelated.py"], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_unrelated.py"}
    assert reasons[tree / "tests" / "test_unrelated.py"] == "selbst geändert"


def test_a_change_under_tests_reaches_the_readers_of_tests_only(tree: Path) -> None:
    """RQ-1: Auch ``tests/`` ist Baum. Private Querimporte, eine neue Definition in einer Datei
    der Sperrklinke oder ein flaches ``glob`` entstehen gerade in einer Teständerung, und die
    Wächter dafür importieren die geänderte Datei nicht. Gewählt wird, wessen Lesebereich
    ``tests/`` einschließt — selbst, über ein Werkzeug oder mit einem Muster, das die Datei
    trifft —, für eine Testdatei wie für einen Helfer, geändert oder gelöscht. Wer nur
    ``app/`` liest, bleibt draußen."""
    _write(
        tree,
        "tools/sizes.py",
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parent.parent\n"
        "def sizes(areas=('app', 'tests')):\n"
        "    return [path for area in areas for path in (ROOT / area).rglob('*.py')]\n",
    )
    _write(tree, "tests/test_sizes.py", "from tools.sizes import sizes\nX = sizes()\n")
    _write(
        tree,
        "tests/test_own_files.py",
        "from pathlib import Path\nHERE = Path(__file__).parent\nX = HERE.glob('test_*.py')\n",
    )
    helper = _write(tree, "tests/fakes.py", "FAKE = 1\n")
    graph = ImportGraph(tree)

    files, reasons = affected([tree / "tests" / "test_direct.py"], graph)

    assert {"tests/test_sizes.py", "tests/test_own_files.py"} <= _names(files, tree)
    assert "tests/test_reader.py" not in _names(files, tree), "liest nur app/"
    assert reasons[tree / "tests" / "test_sizes.py"] == "liest tests/**/*.py über tools/sizes.py:4"

    files, _ = affected([helper], graph)

    assert "tests/test_sizes.py" in _names(files, tree)
    assert "tests/test_own_files.py" not in _names(files, tree), "test_*.py trifft fakes.py nicht"
    assert "tests/test_reader.py" not in _names(files, tree)

    helper.unlink()
    files, _ = affected([helper], ImportGraph(tree))

    assert "tests/test_sizes.py" in _names(files, tree)


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


def test_a_helper_of_a_data_reader_stays_out_and_drags_in_nothing(tree: Path) -> None:
    """Der Ordnerweg bleibt auch über einen Helfer bei einem Glied: ``tests/helpers.py``
    importiert ein Modul, das ``changelog/`` nennt, und zöge sonst jede Testdatei, die ihn
    benutzt, in die Auswahl einer Changelog-Datei. Der Helfer selbst sammelt keinen Test
    und steht deshalb auch nicht darin."""
    _write(tree, "app/reader.py", 'from pathlib import Path\nDIR = Path("daten")\n')
    _write(tree, "tests/shared.py", "from app import reader\n")
    _write(tree, "tests/test_shared.py", "from tests.shared import reader\n")
    _write(tree, "daten/tabelle.toml", "wert = 1\n")

    files, _ = affected([tree / "daten" / "tabelle.toml"], ImportGraph(tree))

    assert _names(files, tree) == set()


def test_a_folder_named_by_a_test_or_a_test_helper_selects_its_readers(tree: Path) -> None:
    """RPL-1 (Review des Plattformpakets): Nach dem Schnitt nennt nur
    ``tests/packaging_helpers.py`` den Ordner ``.github/workflows``, und der
    Workflow-Wächter in ``test_packaging_platform.py`` fehlte bei drei Workflows in der
    Auswahl. Ein Helfer unter ``tests/``, der den Ordner nennt, liest ihn für seine
    Importeure; eine Testdatei, die ihn nennt, liest ihn selbst. Attrappe, weil die
    Plattformdateien in diesem Zweig noch fehlen."""
    workflow = _write(tree, ".github/workflows/mac-netz.yml", "name: Mac\n")
    _write(
        tree,
        "tests/packaging_helpers.py",
        "from pathlib import Path\nWORKFLOWS = Path('.github/workflows')\n",
    )
    _write(tree, "tests/test_packaging_platform.py", "from tests.packaging_helpers import X\n")
    _write(tree, "tests/test_ci_files.py", "WORKFLOWS = '.github/workflows/'\n")

    files, reasons = affected([workflow], ImportGraph(tree))

    assert _names(files, tree) == {"tests/test_packaging_platform.py", "tests/test_ci_files.py"}
    assert reasons[tree / "tests" / "test_packaging_platform.py"] == (
        "hängt an einem Modul, das .github/workflows/ liest"
    )
    assert reasons[tree / "tests" / "test_ci_files.py"] == "nennt den Ordner .github/workflows/"


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


def test_the_real_graph_finds_the_test_of_the_shared_hook(real_graph: ImportGraph) -> None:
    """Gegen den echten Baum: Der Hook unter ``.claude/hooks/`` hat seinen Test.

    ``test_solidon3d_hooks.py`` lädt ihn über seinen Pfad; eine Änderung am
    Hook ohne diesen Test wäre ein grüner Stand, der keiner ist.
    """
    graph = real_graph
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


def test_the_real_graph_knows_this_file(real_graph: ImportGraph) -> None:
    """Gegen den echten Baum: Das Werkzeug findet sich selbst über seinen Test."""
    graph = real_graph
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
    # Jede Form, die die Textvorauswahl durchlassen muss: nach Semikolon, nach Doppelpunkt,
    # in einer Liste mit Alias. Ein Name nur in einem Text ist kein Import.
    _write(
        tree,
        "tests/test_forms.py",
        "x = 1; import fakes\nif x: import fakes\nimport os as o, fakes as f\n"
        "TEXT = 'import fakes'\n",
    )
    graph = ImportGraph(tree)

    files, _ = affected([tree / "tests" / "fakes.py"], graph)

    # Der Baumleser liest nur app/ und bleibt draußen; test_bare fehlt.
    assert _names(files, tree) == {"tests/test_prefixed.py"}
    assert bare_local_imports(graph) == [
        "tests/test_bare.py:2: fakes",
        "tests/test_forms.py:1: fakes",
        "tests/test_forms.py:2: fakes",
        "tests/test_forms.py:3: fakes",
    ]


def test_tests_and_tools_import_their_neighbours_with_the_package_prefix(
    real_graph: ImportGraph,
) -> None:
    """Wer einen Nachbarn aus ``tests/`` oder ``tools/`` ohne Präfix importiert, fehlt in jeder
    Auswahl zu dessen Änderung (``bare_local_imports``). Der Präfix ist die ganze Abhilfe.
    """
    graph = real_graph
    assert sum(name.startswith("tests.test_") for name in graph.modules) > 300

    assert bare_local_imports(graph) == []


def test_a_tool_its_tests_load_by_path_selects_those_tests(real_graph: ImportGraph) -> None:
    """Review 06.10.2026, M3: Ein Werkzeug, das beim Import ``sys.argv`` liest,
    laden seine Tests über den Pfad — ohne Importkante. Seit die Matrix in
    ``tools/`` liegt, fehlte ``test_delivery_matrix_review.py`` in jeder
    Auswahl zu ihr."""
    root = Path(__file__).resolve().parents[1]

    files, reasons = affected([root / "tools" / "matrix_unit.py"], real_graph)

    names = {path.name for path in files}
    assert {"test_delivery_matrix_review.py", "test_delivery_tools.py"} <= names
    chosen = next(path for path in files if path.name == "test_delivery_matrix_review.py")
    assert reasons[chosen] == "nennt matrix_unit.py"


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


def test_run_spreads_a_large_plain_group_over_a_fixed_number_of_workers() -> None:
    """``--run`` fuhr die Gruppe ``plain`` in einem Prozess; eine Auswahl über ``viewport`` lief
    so 1 bis 1,5 Stunden, das Tor mit Arbeitern dieselbe Menge in 18 Minuten (Zusatzauftrag Q).
    Ab ``PARALLEL_FROM`` Dateien bekommt sie eine feste Zahl Arbeiter mit ``worksteal``, nie
    ``-n auto``; darunter kostet der Start der Arbeiter mehr, als sie sparen, und ``--workers 0``
    fährt seriell. Eine Arbeiterzahl, die keine ganze Zahl ab 0 ist, lehnt die Kommandozeile
    ab."""
    from tools import affected_tests
    from tools.affected_tests import PARALLEL_FROM, WORKERS, _commands

    def files(count: int) -> list[Path]:
        return [Path(f"tests/test_probe_{index}.py").resolve() for index in range(count)]

    def options(line: list[str]) -> list[str]:
        return line[: line.index("--window-group")]

    assert WORKERS == 4
    assert "-n" not in options(_commands([], files(PARALLEL_FROM - 1), release=False)[0])
    large = options(_commands([], files(PARALLEL_FROM), release=False)[0])
    start = large.index("-n")
    assert large[start : start + 4] == ["-n", "4", "--dist", "worksteal"]
    assert "-n" not in options(_commands([], files(PARALLEL_FROM), release=False, workers=0)[0])
    two = options(_commands([], files(PARALLEL_FROM), release=False, workers=2)[0])
    assert two[two.index("-n") : two.index("-n") + 2] == ["-n", "2"]
    windowed = _commands(files(PARALLEL_FROM), [], release=True)
    assert all("-n" not in line for line in windowed)
    for wrong in ("auto", "-1", "zwei"):
        with pytest.raises(SystemExit):
            affected_tests.main(["--workers", wrong, "--split", "ROADMAP.md"])


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
