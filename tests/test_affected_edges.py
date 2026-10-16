"""``tools/affected_tests.py`` — Kanten, die kein Import trägt (Nachprüfung CS0 Q).

``test_affected_tests.py`` hält die Grundregeln der Auswahl; hier stehen die Wege, auf denen
eine Änderung einen Test erreicht, ohne dass er die Datei importiert: ein Tupel mit
``*``-Element, ein Muster aus Daten, eine Python-Datei, die ein Modul über ihren Pfad liest, ein
verzögerter Export, was eine ``conftest.py`` lädt oder je Test ausführt, die Sperre zwischen
Anwendungsmodulen und die Leser eines Projektordners. Jede Kante hat eine Attrappe, an der eine
Mutation rot wird, und einen Fall am echten Baum, wo es einen gibt.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest

from tests.selection_trees import names, small_tree, write
from tools.affected_tests import ImportGraph, affected, module_name


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    return small_tree(tmp_path)


@pytest.fixture(scope="module")
def real_graph() -> ImportGraph:
    """Der Importgraph des echten Baums, einmal je Modul gebaut; kein Fall ändert ihn."""
    return ImportGraph()


def _all_tests(graph: ImportGraph) -> set[Path]:
    return {
        path
        for name, path in graph.modules.items()
        if name.startswith("tests.") and path.name.startswith("test_")
    }


# --------------------------------------------------------------------------- F-1, F-4


def test_a_starred_element_keeps_its_folders(tree: Path) -> None:
    """F-1: ``DELIVERY_ROOTS = (*asset_rights.APPLICATION_ROOTS, WEBSITE_ROOT)`` wurde zu
    ``website/`` allein — der Auflöser ließ das ``*``-Element still fallen, und ein neues Bild
    unter ``app/images`` wählte den Rechtekettenwächter nicht. Ein ``*``-Element trägt die
    Elemente seines Werts bei, auch aus einem anderen Modul und mit einem Element; was sich
    nicht auflösen lässt, bleibt offen."""
    write(
        tree,
        "tools/media.py",
        "from typing import Final\n"
        'ROOTS: Final = ("app/images/", "packaging/")\n'
        'ONE = ("app/x/",)\n',
    )
    write(
        tree,
        "tests/test_media.py",
        "from pathlib import Path\n"
        "from tools import media\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        'DELIVERY = (*media.ROOTS, "website/")\n'
        "def test_media():\n"
        "    return [p for root in DELIVERY for p in (ROOT / root).rglob('*')]\n",
    )
    write(
        tree,
        "tests/test_single.py",
        "from pathlib import Path\n"
        "from tools.media import ONE\n"
        "def test_single():\n"
        "    return [p for root in (*ONE,) for p in Path(root).rglob('*')]\n",
    )
    graph = ImportGraph(tree)

    files, reasons = affected([tree / "app" / "images" / "icon" / "new.svg"], graph)

    assert "tests/test_media.py" in names(files, tree)
    assert reasons[tree / "tests" / "test_media.py"] == (
        "liest app/images/**/* (tests/test_media.py:6)"
    )
    files, _reasons = affected([tree / "app" / "x" / "new.svg"], graph)
    assert "tests/test_single.py" in names(files, tree)
    files, _reasons = affected([tree / "docs" / "new.svg"], graph)
    assert "tests/test_media.py" not in names(files, tree)


def test_a_new_image_selects_the_rights_guard(real_graph: ImportGraph) -> None:
    """F-1 gegen den echten Baum: ``test_asset_rights`` liest jedes ausgelieferte Medium über
    ``(*asset_rights.APPLICATION_ROOTS, …)`` und wird rot, wenn eines ohne Rechtekette dazukommt
    — die Auswahl für ein neues Bild unter ``app/images`` muss ihn nennen."""
    root = real_graph.root
    new = root / "app" / "images" / "icon" / "zz_not_yet_there.svg"
    assert not new.exists()

    _files, reasons = affected([new], real_graph)

    reason = reasons.get(root / "tests" / "test_asset_rights.py", "")
    assert reason.startswith("liest app/images/"), reason


def test_a_pattern_that_cannot_be_resolved_reads_every_depth(tree: Path) -> None:
    """F-4: Ein Muster aus Daten (``app/**/*.py`` in einer JSON-Datei) galt als ``*`` und las
    eine Ebene; ``glob.glob`` damit galt gar nicht, weil der offene Ordner nur mit einem Muster
    zählte, das Python nennt. Ein Muster, das sich nicht auflösen lässt, liest jede Tiefe —
    über einem bekannten Ordner wie über dem Arbeitsordner. ``rglob("*")`` über einen offenen
    Ordner bleibt draußen (gemessen: Programme und Archive)."""
    write(tree, "tests/patterns.json", json.dumps({"pattern": "app/**/*.py"}))
    for name, text in (
        (
            "test_root_glob",
            "import json\nfrom pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "PATTERN = json.loads((ROOT / 'tests' / 'patterns.json').read_text())['pattern']\n"
            "def test_files():\n    return sorted(ROOT.glob(PATTERN))\n",
        ),
        (
            "test_glob_module",
            "import glob\nimport json\nfrom pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "PATTERN = json.loads((ROOT / 'tests' / 'patterns.json').read_text())['pattern']\n"
            "def test_files():\n    return glob.glob(PATTERN, recursive=True)\n",
        ),
        (
            "test_open_folder",
            "def test_files(folder):\n    return sorted(folder.rglob('*'))\n",
        ),
    ):
        write(tree, f"tests/{name}.py", text)

    files, reasons = affected([tree / "app" / "sub" / "deep.py"], ImportGraph(tree))

    chosen = names(files, tree)
    assert {"tests/test_root_glob.py", "tests/test_glob_module.py"} <= chosen
    assert "tests/test_open_folder.py" not in chosen
    assert reasons[tree / "tests" / "test_root_glob.py"] == (
        "liest **/* (tests/test_root_glob.py:6)"
    )


# --------------------------------------------------------------------------- F-2, F-3


def test_a_source_read_by_its_path_selects_the_readers_tests(tree: Path) -> None:
    """F-2: ``app/i18n/extract.py`` liest die Erzeuger unter ``tools/`` als Quelltext
    (``EXTRA_SOURCES``); ein neuer Text in ``tools/make_changelog.py`` machte
    ``test_translations`` rot, und die Auswahl wählte es nicht. Wer eine Python-Datei über einen
    Pfad mit ihrem Namen liest, liest sie — mit allen, die ihn mittelbar importieren; wer sie
    nicht nennt, nicht."""
    write(
        tree,
        "app/extract.py",
        "from pathlib import Path\n"
        "PACKAGE_DIR = Path(__file__).parent\n"
        "EXTRA = (PACKAGE_DIR.parent / 'tools' / 'gen.py',)\n"
        "def texts():\n    return [path.read_text() for path in EXTRA]\n",
    )
    write(tree, "app/catalog.py", "from app import extract\n")
    write(tree, "tools/gen.py", "TEXT = 'neu'\n")
    write(tree, "tools/other.py", "TEXT = 'alt'\n")
    write(tree, "tests/test_texts.py", "from app import catalog\n")

    files, reasons = affected([tree / "tools" / "gen.py"], ImportGraph(tree))

    assert reasons[tree / "tests" / "test_texts.py"] == "hängt an app/extract.py, das gen.py liest"
    files, _reasons = affected([tree / "tools" / "other.py"], ImportGraph(tree))
    assert "tests/test_texts.py" not in names(files, tree)


def test_a_new_text_in_a_generator_selects_the_translations(real_graph: ImportGraph) -> None:
    """F-2 gegen den echten Baum: ``tools/make_changelog.py`` steht in
    ``extract.EXTRA_SOURCES``; ``test_translations`` sammelt daraus die Texte."""
    root = real_graph.root

    _files, reasons = affected([root / "tools" / "make_changelog.py"], real_graph)

    reason = reasons.get(root / "tests" / "test_translations.py", "")
    assert "app/i18n/extract.py" in reason, reason


def test_a_lazy_export_is_an_edge(tree: Path) -> None:
    """F-3: ``from app.core.knowledge.parts import PARTS`` lädt ``parts/builtin.py`` über
    ``app.core.lazy.install``; keine Importanweisung nennt es, und 17 von 20 Nutzern fehlten bei
    einer Änderung dort. Ein verzögerter Export ist eine Kante, ebenso ``import_module`` mit
    einer Konstanten oder ``f"{__package__}.…"``."""
    write(tree, "app/lazy.py", "def install(package, exports):\n    pass\n")
    write(
        tree,
        "app/pkg/__init__.py",
        "from typing import Final\nfrom app.lazy import install\n"
        '_EXPORTS: Final = {"THING": ("impl", "THING")}\n'
        "install(__name__, _EXPORTS)\n",
    )
    write(tree, "app/pkg/impl.py", "THING = 1\n")
    write(
        tree,
        "app/pkg/loader.py",
        "import importlib\n"
        "def other():\n    return importlib.import_module(f'{__package__}.other')\n"
        "def far():\n    return importlib.import_module('app.far')\n",
    )
    write(tree, "app/pkg/other.py", "VALUE = 1\n")
    write(tree, "app/far.py", "VALUE = 1\n")
    write(tree, "tests/test_thing.py", "from app.pkg import THING\n")
    write(tree, "tests/test_loader.py", "from app.pkg import loader\n")
    graph = ImportGraph(tree)

    for changed, test in (
        ("app/pkg/impl.py", "tests/test_thing.py"),
        ("app/pkg/other.py", "tests/test_loader.py"),
        ("app/far.py", "tests/test_loader.py"),
    ):
        files, _reasons = affected([tree / changed], graph)
        assert test in names(files, tree), changed


def test_the_real_parts_library_reaches_every_test_that_takes_parts(
    real_graph: ImportGraph,
) -> None:
    """F-3 gegen den echten Baum: Jede Testdatei, die ``PARTS`` aus
    ``app.core.knowledge.parts`` bezieht, läuft bei einer Änderung an ``builtin.py`` mit."""
    root = real_graph.root
    takes = re.compile(r"from app\.core\.knowledge\.parts import [^\n]*\bPARTS\b")
    users = {
        path
        for path in _all_tests(real_graph)
        if takes.search(real_graph.text(module_name(path, root)))
    }
    assert len(users) >= 15, sorted(users)

    files, _reasons = affected(
        [root / "app" / "core" / "knowledge" / "parts" / "builtin.py"], real_graph
    )

    assert users <= files, sorted(path.name for path in users - files)


# --------------------------------------------------------------------------- CS-37, CS-38


def test_the_root_conftest_selects_every_test(tree: Path) -> None:
    """CS-37: Die ``conftest.py`` an der Wurzel lädt für jede Sitzung ``load_operations()``;
    eine Änderung daran wählte nur ihre Leser."""
    write(tree, "conftest.py", "from app import x\nx.VALUE\n")
    graph = ImportGraph(tree)

    files, reasons = affected([tree / "conftest.py"], graph)

    assert files == _all_tests(graph)
    assert reasons[tree / "tests" / "test_unrelated.py"] == "conftest.py betrifft jeden Test"


def test_what_a_conftest_runs_for_every_test_selects_every_test(tree: Path) -> None:
    """CS-38 (Entscheidung Koordinator, B): Was Haken und autouse-Fixtures einer
    ``conftest.py`` importieren oder über einen Namen der Modulebene benutzen, und was ihre
    Modulebene tut, wirkt auf jede Testdatei unter ihr. Was sie nur lädt, wählt seine Importeure
    — und alle erst, wenn sonst nichts liefe. Ermittelt aus der Datei: Eine neue
    autouse-Fixture zieht ihr Modul mit."""
    for module in ("hooked", "auto", "named", "loaded", "level", "effect", "fresh"):
        write(tree, f"app/{module}.py", "VALUE = 1\n")
    write(tree, "tools/plainly.py", "VALUE = 1\n")
    conftest = (
        "import pytest\n"
        "import app.effect\n"
        "from app import named, loaded, level\n"
        "level.VALUE\n"
        "def pytest_configure(config):\n    from app import hooked\n"
        "@pytest.fixture(autouse=True)\n"
        "def _every():\n    from app import auto\n    yield named.VALUE\n"
        "@pytest.fixture\n"
        "def plain():\n    from tools import plainly\n    return loaded.VALUE\n"
    )
    write(tree, "tests/conftest.py", conftest)
    write(tree, "tests/test_loaded.py", "from app import loaded\n")
    graph = ImportGraph(tree)
    every = _all_tests(graph)

    for module in ("hooked", "auto", "named", "level", "effect"):
        files, reasons = affected([tree / "app" / f"{module}.py"], graph)
        assert files == every, module
        assert reasons[tree / "tests" / "test_unrelated.py"] == (
            f"tests/conftest.py führt app.{module} für jeden Test aus"
        )
    files, _reasons = affected([tree / "app" / "loaded.py"], graph)
    assert names(files, tree) == {"tests/test_loaded.py", "tests/test_reader.py"}
    files, reasons = affected([tree / "tools" / "plainly.py"], graph)
    assert files == every, "sonst wählte nichts das Modul, das conftest.py lädt"
    assert reasons[tree / "tests" / "test_direct.py"] == (
        "tests/conftest.py lädt tools.plainly, und sonst wählte nichts"
    )

    write(
        tree,
        "tests/conftest.py",
        conftest + "@pytest.fixture(autouse=True)\ndef _fresh():\n    from app import fresh\n",
    )
    files, _reasons = affected([tree / "app" / "fresh.py"], ImportGraph(tree))
    assert files == every


@pytest.mark.parametrize(
    "module", ["app/ui/settings.py", "app/ui/labels.py", "tools/list_windowed_tests.py"]
)
def test_the_real_conftest_reaches_every_test_through_what_it_runs(
    real_graph: ImportGraph, module: str
) -> None:
    """CS-38 gegen den echten Baum (N-2): ``settings`` und ``labels`` laufen in autouse-Fixtures,
    ``list_windowed_tests`` in einem Haken von ``tests/conftest.py`` — in jedem Test."""
    files, _reasons = affected([real_graph.root / module], real_graph)

    assert files == _all_tests(real_graph)


# --------------------------------------------------------------------------- F-9, F-10


def test_an_application_reading_does_not_pass_to_other_application_modules(tree: Path) -> None:
    """F-9: Eine lesende Einheit unter ``app/`` geht an Module unter ``tools/`` und ``tests/``
    weiter, nicht an andere Module der Anwendung — sonst trüge der Stempel aus ``paths.py`` die
    Lesung in jede Funktion, die den Zwischenspeicher öffnet."""
    write(
        tree,
        "app/sources.py",
        "from pathlib import Path\nROOT = Path(__file__).resolve().parent\n"
        "def every():\n    return sorted(ROOT.rglob('*.py'))\n",
    )
    write(tree, "app/stamp.py", "from app import sources\ndef run():\n    return sources.every()\n")
    write(
        tree,
        "tools/stamp_tool.py",
        "from app import sources\ndef run():\n    return sources.every()\n",
    )
    write(tree, "tests/test_stamp.py", "from app import stamp\nX = stamp.run()\n")
    write(tree, "tests/test_stamp_tool.py", "from tools import stamp_tool\nX = stamp_tool.run()\n")

    files, reasons = affected([tree / "app" / "new_module.py"], ImportGraph(tree))

    assert reasons[tree / "tests" / "test_stamp_tool.py"] == (
        "liest app/**/*.py über app/sources.py:4"
    )
    assert "tests/test_stamp.py" not in names(files, tree)


def test_a_reader_of_a_project_folder_runs_the_operations_in_it(tree: Path) -> None:
    """F-10: Wer einen Ordner mit Projektdateien liest und lädt, rechnet jede Op darin; eine Op
    nur in ``stein.p3d`` wählt ihn, eine Op in keiner Projektdatei nicht."""
    for module, op in (("sculpt", "zz_sculpt"), ("lonely", "zz_lonely")):
        write(
            tree,
            f"app/{module}.py",
            "from app.registry import register_op\n"
            f"@register_op(name='{op}')\ndef run(ctx):\n    return ctx\n",
        )
    folder = tree / "website" / "teile"
    folder.mkdir(parents=True)
    for name, ops in (("stein.p3d", ["create_box", "zz_sculpt"]), ("leer.p3d", ["create_box"])):
        with zipfile.ZipFile(folder / name, "w") as archive:
            archive.writestr("project.json", json.dumps({"ops": [{"op": op} for op in ops]}))
    write(
        tree,
        "tests/test_site_parts.py",
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "def test_every_part():\n"
        "    return [load(path) for path in (ROOT / 'website' / 'teile').glob('*.p3d')]\n",
    )
    graph = ImportGraph(tree)

    files, reasons = affected([tree / "app" / "sculpt.py"], graph)
    assert reasons[tree / "tests" / "test_site_parts.py"] == (
        "liest website/teile/*.p3d (tests/test_site_parts.py:4)"
    )
    files, _reasons = affected([tree / "app" / "lonely.py"], graph)
    assert "tests/test_site_parts.py" not in names(files, tree)


# --------------------------------------------------------------------------- je lesender Einheit


@pytest.fixture
def corpus(tree: Path) -> Path:
    """Ein Helfer, der den Ordner ``tests/data/meshes`` nennt und zwei Dateien darin liest, und
    Testdateien, die je eine seiner Einheiten beziehen."""
    for name in ("plate.stl", "cube.stl"):
        write(tree, f"tests/data/meshes/{name}", "solid\n")
    write(
        tree,
        "tests/corpus_helpers.py",
        "import pytest\n"
        "from pathlib import Path\n"
        'MESHES = Path(__file__).parent / "data" / "meshes"\n'
        'PLATE = MESHES / "plate.stl"\n'
        "def plate():\n"
        '    return (MESHES / "plate.stl").read_bytes()\n'
        "def cube():\n"
        '    return (MESHES / "cube.stl").read_bytes()\n'
        "def mesh(name):\n"
        "    return (MESHES / name).read_bytes()\n"
        "def unrelated():\n"
        "    return 1\n"
        "@pytest.fixture\n"
        "def plate_fixture():\n"
        "    return plate()\n",
    )
    write(
        tree,
        "tests/import_helpers.py",
        "from pathlib import Path\n"
        'TABLE = (Path(__file__).parent / "data" / "meshes" / "plate.stl").read_bytes()\n',
    )
    write(tree, "tests/between_helpers.py", "from tests import import_helpers\n")
    write(
        tree,
        "tests/conftest.py",
        "import pytest\n"
        "from tests.corpus_helpers import plate\n"
        "@pytest.fixture\n"
        "def plate_window():\n"
        "    return plate()\n",
    )
    tests = {
        "test_uses_plate": "from tests.corpus_helpers import plate\ndef test_a():\n    plate()\n",
        "test_uses_cube": "from tests.corpus_helpers import cube\ndef test_a():\n    cube()\n",
        "test_mesh_plate": "from tests import corpus_helpers\n"
        "def test_a():\n    corpus_helpers.mesh('plate.stl')\n",
        "test_mesh_cube": "from tests.corpus_helpers import mesh\n"
        "def test_a():\n    mesh('cube.stl')\n",
        "test_mesh_open": "from tests.corpus_helpers import mesh\n"
        "def test_a(name):\n    mesh(name)\n",
        "test_unrelated_helper": "from tests.corpus_helpers import unrelated\n"
        "def test_a():\n    unrelated()\n",
        "test_constant": "from tests.corpus_helpers import PLATE\ndef test_a():\n    load(PLATE)\n",
        "test_own_path": "from tests.corpus_helpers import MESHES\n"
        "def test_a():\n    (MESHES / 'cube.stl').read_bytes()\n",
        "test_folder_passed": "from tests.corpus_helpers import MESHES\n"
        "def test_a():\n    scan(MESHES)\n",
        "test_fixture": "from tests.corpus_helpers import plate_fixture\n"
        "def test_a(plate_fixture):\n    pass\n",
        "test_conftest_fixture": "import pytest\n"
        "@pytest.mark.usefixtures('plate_window')\ndef test_a():\n    pass\n",
        "test_import_time": "from tests import between_helpers\n",
        "test_class_fixture": "import pytest\n"
        "@pytest.mark.usefixtures('plate_window')\n"
        "class TestPlate:\n    def test_a(self):\n        pass\n",
        "test_module_mark": "import pytest\n"
        "pytestmark = pytest.mark.usefixtures('plate_window')\n"
        "def test_a():\n    pass\n",
        "test_dynamic_fixture": "def test_a(request):\n"
        "    request.getfixturevalue('plate_window')\n",
    }
    for name, text in tests.items():
        write(tree, f"tests/{name}.py", text)
    return tree


def test_a_data_file_is_read_by_the_units_that_reach_it(corpus: Path) -> None:
    """Entscheidung Koordinator „je lesender Funktion“: ``plate_holes.stl`` wählte 289
    Testdateien, weil ``tests/helpers.py`` die Datei und ihren Ordner nennt und so jeder
    Importeur mitlief. Jetzt wählt eine Datei unter ``tests/data`` die Testdateien, deren
    Einheiten sie über einen Helfer erreichen: über den Namen, einen Pfad mit dem Wert des
    Arguments, eine Konstante, den Ordner als Ganzes, eine angeforderte Fixture — aus dem Helfer
    oder einer ``conftest.py``, als Parameter, über ``usefixtures`` an Funktion, Klasse oder
    ``pytestmark`` und über ``getfixturevalue`` — und die Modulebene eines Helfers, die sie
    beim Import liest.
    Wer eine andere Datei desselben Ordners liest oder eine Einheit bezieht, die sie nicht
    erreicht, bleibt draußen."""
    files, reasons = affected(
        [corpus / "tests" / "data" / "meshes" / "plate.stl"], ImportGraph(corpus)
    )

    chosen = names(files, corpus)
    assert {
        "tests/test_uses_plate.py",
        "tests/test_mesh_plate.py",
        "tests/test_mesh_open.py",
        "tests/test_constant.py",
        "tests/test_folder_passed.py",
        "tests/test_fixture.py",
        "tests/test_conftest_fixture.py",
        "tests/test_import_time.py",
        "tests/test_class_fixture.py",
        "tests/test_module_mark.py",
        "tests/test_dynamic_fixture.py",
    } <= chosen
    assert (
        not {
            "tests/test_uses_cube.py",
            "tests/test_mesh_cube.py",
            "tests/test_unrelated_helper.py",
            "tests/test_own_path.py",
        }
        & chosen
    )
    assert reasons[corpus / "tests" / "test_uses_plate.py"] == (
        "liest tests/data/meshes/plate.stl über tests/corpus_helpers.py:6"
    )
    assert reasons[corpus / "tests" / "test_import_time.py"] == (
        "über tests/import_helpers.py: liest tests/data/meshes/plate.stl beim Import"
    )


def test_an_autouse_fixture_reading_a_data_file_selects_every_test(corpus: Path) -> None:
    """Liest eine autouse-Fixture einer ``conftest.py`` die Datei, liest sie jeder Test darunter."""
    write(
        corpus,
        "tests/conftest.py",
        "import pytest\n"
        "from tests.corpus_helpers import plate\n"
        "@pytest.fixture(autouse=True)\n"
        "def _every_test():\n"
        "    yield plate()\n",
    )
    graph = ImportGraph(corpus)

    files, reasons = affected([corpus / "tests" / "data" / "meshes" / "plate.stl"], graph)

    assert files == _all_tests(graph)
    assert reasons[corpus / "tests" / "test_uses_cube.py"] == (
        "tests/conftest.py liest tests/data/meshes/plate.stl in einer autouse-Fixture"
    )


def test_the_real_corpus_file_is_read_by_the_helpers_units(real_graph: ImportGraph) -> None:
    """Gegen den echten Baum: ``plate_holes.stl`` erreichen ``test_round_surface_measurements``
    über ``helpers.surface_mesh`` und ``test_tool_offer`` über ``helpers.plate_project``;
    ``test_placement`` und ``test_history`` importieren aus ``tests/helpers.py`` nur Einheiten,
    die sie nicht erreichen, und liefen bisher über den Ordnerweg mit (289 Testdateien)."""
    root = real_graph.root

    files, reasons = affected([root / "tests" / "data" / "meshes" / "plate_holes.stl"], real_graph)

    for name in ("test_round_surface_measurements.py", "test_tool_offer.py"):
        assert "tests/helpers.py" in reasons.get(root / "tests" / name, ""), name
    for name in ("test_placement.py", "test_history.py"):
        assert root / "tests" / name not in files, (name, reasons.get(root / "tests" / name))


def test_naming_the_website_folder_reads_no_file_in_it(tree: Path) -> None:
    """Wie bisher der Ordnerweg: An der Wurzel und direkt unter ``website/`` liegt alles
    nebeneinander — wer den Ordner nennt oder als Pfad baut, liest damit nicht jede Datei darin.
    Wer die Datei nennt, liest sie."""
    icon = write(tree, "website/icon.svg", "<svg/>\n")
    write(
        tree,
        "tests/test_site_named.py",
        "from pathlib import Path\nURL = 'website/'\nSITE = Path('website')\n",
    )
    write(tree, "tests/test_icon_named.py", "ICON = 'website/icon.svg'\n")

    files, reasons = affected([icon], ImportGraph(tree))

    assert names(files, tree) == {"tests/test_icon_named.py"}
    assert reasons[tree / "tests" / "test_icon_named.py"] == (
        "nennt icon.svg (tests/test_icon_named.py:1)"
    )
