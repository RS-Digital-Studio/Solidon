"""Die Auswahl für Linux und macOS vor dem Merge — und wer einen echten Slicer fragen darf.

``tools/ci_selection.py`` bestimmt aus einem Diff die Fenster- und Slicertests,
die ``fenster-auswahl.yml`` und ``slicer-auswahl.yml`` auf den Läufern fahren
(Entscheidung Robert, 07.10.2026). Slicertests erkennt es am Marker
``slicer``. Ein Test, der die Maschine nach einem Slicer fragt, ohne den
Marker zu tragen, fiele aus dieser Auswahl heraus und liefe auf Linux und
macOS nie — der Wächter unten hält deshalb fest, dass das nur über die
Fixture ``installed_slicer`` geht.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path, PurePosixPath

import pytest

from tools import ci_selection

ROOT = Path(__file__).resolve().parent.parent

#: Wo Installationsprogramme ablegen. Wer dort selbst sucht, fragt die Maschine.
_INSTALL_ROOTS = frozenset({"C:/Program Files", "/Applications", "/usr/share", "/opt"})
#: Wer so einen Ort liest, ruft eine dieser Methoden auf ihm auf.
_READS = frozenset({"iterdir", "glob", "rglob", "is_dir", "exists", "is_file", "walk"})
#: Die echte Programmsuche ohne die Attrappe aus ``conftest.py``.
_REAL_SEARCH = frozenset({"unpatched_find_program", "unpatched_find_programs"})


def _slicer_ids() -> frozenset[str]:
    """Die Werkzeugkennung ``slicer`` und jede Programmbezeichnung eines Slicers."""
    from app.core import discover, tools

    return frozenset({"slicer", *(discover.program_mark(name) for name in tools.SLICERS)})


@pytest.mark.parametrize(
    ("path", "documentation"),
    [
        ("ROADMAP.md", True),
        ("app/core/CLAUDE.md", True),
        ("konzepte/begruendungen/regel-tests.md", True),
        ("konzepte/nachweise/lauf.json", True),
        ("app/i18n/locales/en.json", True),
        ("changelog/de.md", False),
        ("DATENSCHUTZ.md", False),
        ("THIRD-PARTY-NOTICES.md", False),
        ("app/i18n/__init__.py", False),
        ("app/ui/print_settings_dialog.py", False),
        ("app/core/knowledge/data/printers.toml", False),
    ],
)
def test_only_documents_and_catalogues_count_as_documentation(
    path: str, documentation: bool
) -> None:
    """Der Changelog zeigt das Update-Fenster; ein Katalog prüft ``test_translations``."""
    assert ci_selection.is_documentation(path) is documentation


def test_markdown_the_application_reads_is_named_where_the_selection_looks() -> None:
    """Jede ``.md``, die ``app/`` beim Namen liest, löst eine Auswahl aus (Review 1 P3, G-4).

    Die Datenschutzauskunft und die Lizenzbeilage zeigt ein Fenster; als
    Unterlage gelesen wählte eine Änderung dort keinen Fenstertest. Eine neue
    Datei dieser Art fehlte in der Liste genauso still — deshalb liest der
    Wächter die Namen aus dem Code.
    """
    named: set[str] = set()
    for path in sorted((ROOT / "app").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and PurePosixPath(node.value).suffix == ".md"
                and " " not in node.value
            ):
                named.add(PurePosixPath(node.value).name)
    assert named, "Voraussetzung: die Anwendung liest Markdown beim Namen"
    assert named == ci_selection.READ_BY_THE_APPLICATION
    for name in named:
        assert (ROOT / name).is_file(), name
        windows, _slicers = ci_selection.select([ROOT / name])
        assert windows, f"{name}: eine Änderung wählt keinen Fenstertest"


def test_documents_and_catalogues_select_neither_windows_nor_slicers() -> None:
    """Ein Katalog zöge über den Ordnerweg sonst jeden Test eines ``locales/``-Lesers mit."""
    changed = [
        ROOT / "ROADMAP.md",
        ROOT / "app" / "i18n" / "locales" / "fr.json",
        ROOT / "konzepte" / "README.md",
        ROOT / ".claude" / "rules" / "tests.md",
    ]

    assert ci_selection.select(changed) == ([], [])


def test_a_changed_test_file_lands_in_both_lists_by_its_cases(tmp_path: Path) -> None:
    """Fenster über die Fenstergruppe, Slicer über ``-m slicer`` — je Datei eine Auswahl."""
    for package in ("app", "tools", "tests"):
        (tmp_path / package).mkdir()
    probe = tmp_path / "tests" / "test_probe.py"
    probe.write_text(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.windowed
            def test_window():
                pass

            @pytest.mark.slicer("cura")
            def test_cura():
                pass

            def test_plain():
                pass
            """
        ),
        encoding="utf-8",
    )
    plain = tmp_path / "tests" / "test_quiet.py"
    plain.write_text("def test_plain():\n    pass\n", encoding="utf-8")

    windows, slicers = ci_selection.select([probe, plain], tmp_path)

    assert windows == ["tests/test_probe.py -p tools.list_windowed_tests --window-group windowed"]
    assert slicers == ["tests/test_probe.py -m slicer"]
    assert ci_selection.programs("; ".join(slicers), tmp_path) == ["cura"]


def _unmarked_machine_searches(source: str, name: str) -> list[str]:
    """Stellen, die einen installierten Slicer an ``installed_slicer`` vorbei suchen."""
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        text = ast.get_source_segment(source, node) or ""
        parameters = {argument.arg for argument in node.args.args}
        decorators = " ".join(ast.unparse(decorator) for decorator in node.decorator_list)
        if "installed_slicer" in parameters and "mark.slicer" not in decorators:
            found.append(f"{name}:{node.lineno} {node.name}: installed_slicer ohne mark.slicer")
        isolated = "isolated_search" in parameters or "_install_roots" in text
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            called = inner.func
            if (
                isinstance(called, ast.Attribute)
                and called.attr in _REAL_SEARCH
                and not isolated
                and _asks_for_a_slicer(inner)
            ):
                found.append(f"{name}:{inner.lineno} {node.name}: {called.attr} ohne Isolation")
            if isinstance(called, ast.Attribute) and called.attr in _READS:
                receiver = ast.unparse(called.value)
                if _is_install_root(called.value):
                    found.append(f"{name}:{inner.lineno} {node.name}: liest {receiver}")
        for loop in ast.walk(node):
            if isinstance(loop, ast.For) and any(
                _is_install_root(part) for part in ast.walk(loop.iter)
            ):
                found.append(f"{name}:{loop.lineno} {node.name}: durchsucht feste Ablagen")
    return found


def _asks_for_a_slicer(call: ast.Call) -> bool:
    """Sucht dieser Aufruf einen Slicer — über die Kennung oder die Namensliste?

    Die Kennung allein reichte nicht: Mit ihr in einer Variablen und
    ``tools.SLICERS`` als Namen sah der Wächter die Suche nicht.
    """
    first = call.args[0] if call.args else None
    if isinstance(first, ast.Constant) and first.value in _slicer_ids():
        return True
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    return any("SLICERS" in ast.unparse(argument) for argument in arguments)


def _is_install_root(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in _INSTALL_ROOTS
    )


def test_the_guard_finds_each_way_past_the_fixture() -> None:
    """Erst am bekannten Ausgang: der alte Cura-Helfer, die nackte Suche, die Suche
    mit der Kennung in einer Variablen, der fehlende Marker."""
    source = textwrap.dedent(
        """
        def _installed_cura():
            for base in (Path("C:/Program Files"), Path("/usr/share")):
                if not base.is_dir():
                    continue

        def test_search():
            discover.unpatched_find_programs("slicer", SLICERS)

        def _found(kind):
            return discover.unpatched_find_programs(kind, tools.SLICERS)

        def test_isolated(isolated_search):
            discover.unpatched_find_programs("slicer", SLICERS)

        def test_other_tool():
            discover.unpatched_find_program("comfyui", ("Comfy Desktop",))

        def test_unmarked(installed_slicer):
            pass

        @pytest.mark.slicer("cura")
        def test_marked(installed_slicer):
            pass

        def test_compares():
            assert Path("/opt") in roots
        """
    )

    found = _unmarked_machine_searches(source, "probe.py")

    assert [entry.split(" ", 2)[1] for entry in found] == [
        "_installed_cura:",
        "test_search:",
        "_found:",
        "test_unmarked:",
    ], found


def test_only_installed_slicer_asks_the_machine_for_a_slicer() -> None:
    """Jeder Test mit echtem Slicer geht über die Fixture und trägt damit den Marker.

    Sonst wählt ``tools/ci_selection.py`` ihn nicht, und auf Linux und macOS
    läuft er nie. ``conftest.py`` ist die Fixture selbst.
    """
    found: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        found += _unmarked_machine_searches(path.read_text(encoding="utf-8"), path.name)

    assert not found, "Slicer an installed_slicer vorbei gesucht:\n" + "\n".join(found)


# --- Die Basis der Auswahl beim Push nach main (CI-09, N-1 der Nachprüfung) ---------------


def _run(number: int, sha: str, *, status: str = "completed") -> dict[str, object]:
    return {
        "id": number,
        "head_sha": sha,
        "head_branch": "main",
        "event": "push",
        "status": status,
    }


def _jobs(
    window: str = "success", slicer: str = "skipped", chose: str = "success"
) -> list[dict[str, object]]:
    """Die Jobs eines main-Laufs, wie die API sie nennt; gerufene als ``<Name> / <Job>``."""
    jobs: list[dict[str, object]] = [
        {"name": "Stil und Format", "status": "completed", "conclusion": "success"},
        {"name": ci_selection.SELECTION_JOB, "status": "completed", "conclusion": chose},
    ]
    window_name, slicer_name = ci_selection.SELECTION_RUNS
    for part in range(2):
        jobs.append(
            {
                "name": f"{window_name} / Fensterauswahl (macos-latest, Teil {part})",
                "status": "completed" if window != "in_progress" else "in_progress",
                "conclusion": None if window == "in_progress" else window,
            }
        )
    jobs.append({"name": slicer_name, "status": "completed", "conclusion": slicer})
    return jobs


def test_the_selection_base_is_the_last_main_run_that_finished_its_selection() -> None:
    """Ein ersetzter Lauf (keine Jobs), ein abgebrochener, ein noch laufender und der
    eigene Lauf zählen nicht; ein roter, der seine Auswahl gefahren hat, schon."""
    runs = [
        _run(9, "eigener", status="in_progress"),
        _run(8, "ersetzt"),
        _run(7, "abgebrochen"),
        _run(6, "laeuft-noch", status="in_progress"),
        _run(5, "rot-aber-gefahren"),
        _run(4, "aelter"),
    ]
    jobs = {
        8: [],
        7: _jobs(window="cancelled"),
        6: _jobs(window="in_progress"),
        5: _jobs(window="failure"),
        4: _jobs(),
    }
    assert ci_selection.checked_base(runs, lambda run: jobs.get(int(str(run)), []), "9") == (
        "rot-aber-gefahren"
    )
    assert ci_selection.checked_base(runs[:4], lambda run: jobs.get(int(str(run)), [])) is None
    # Eine gescheiterte Auswahl hat nichts gewählt; ein Lauf von einem anderen Zweig zählt nicht.
    assert not ci_selection.checked_run(_jobs(chose="failure"))
    other = [{**_run(3, "zweig"), "head_branch": "paket/x"}]
    assert ci_selection.checked_base(other, lambda _run: _jobs()) is None


def test_the_selection_job_names_are_those_of_the_workflow() -> None:
    """Die Namen, an denen die Basis einen fertigen Lauf erkennt, stehen so in build.yml."""
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    for name in (ci_selection.SELECTION_JOB, *ci_selection.SELECTION_RUNS):
        assert f"\n    name: {name}\n" in workflow, name
