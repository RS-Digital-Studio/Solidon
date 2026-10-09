"""Die CI verteilt vollständig und bleibt bei fehlender Abnahme rot — ohne Qt-Läufe."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import ci_shards, list_windowed_tests
from tools import run_suite_isolated as runner


@pytest.fixture(autouse=True)
def _outside_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jeder Test hier rechnet ohne die Umgebung des GitHub-Schritts, der ihn fährt.

    Unter GitHub Actions trägt jeder Schritt ``GITHUB_ACTIONS`` und
    ``GITHUB_STEP_SUMMARY``. Drei Tests riefen den Läufer mit dieser Umgebung
    und hängten ihre erfundenen Fenstergruppen — „Stand: failed", eine rote
    ``tests/test_a.py`` — an den Schrittbericht des Kernjobs, der sie fuhr.
    Wer die Umgebung braucht, setzt sie im Test selbst.
    """
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def _counts(**extra: int) -> dict[str, int]:
    """Die zwei vertraglich festen Dateien plus frei gewählte Prüffälle."""
    return {**dict.fromkeys(runner.CONTRACT_FILES, 1), **extra}


def test_these_tests_leave_the_step_summary_of_the_real_job_alone(tmp_path: Path) -> None:
    """Die Läufertests schreiben nichts in den Schrittbericht des Jobs, der sie fährt.

    Lokal fehlt ``GITHUB_STEP_SUMMARY``, und ohne die Fixture oben bliebe
    dieser Fehler deshalb überall außer in der CI unsichtbar. Gefahren werden
    die drei Tests, die dort ihre erfundenen Fenstergruppen hinterließen.
    """
    page = tmp_path / "step-summary.md"
    tests = (
        "test_planning_without_release_cannot_start_a_test_process",
        "test_a_failed_file_remains_failed_after_a_successful_file",
        "test_collection_failure_leaves_a_failed_report",
    )
    done = subprocess.run(
        [
            sys.executable,
            *("-m", "pytest", "-q", "-p", "no:cacheprovider"),
            *(f"tests/test_ci_runner.py::{name}" for name in tests),
        ],
        cwd=runner.ROOT,
        env={**os.environ, "GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(page)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "3 passed" in done.stdout, done.stdout
    assert not page.exists() or not page.read_text(encoding="utf-8"), page.read_text("utf-8")


def _junit(
    path: Path, *, tests: int = 1, failed: int = 0, errors: int = 0, skipped: int = 0
) -> None:
    """Erzeugt ein kleines vollständiges JUnit-Dokument aus unabhängigen Fallzahlen."""
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root,
        "testsuite",
        tests=str(tests),
        failures=str(failed),
        errors=str(errors),
        skipped=str(skipped),
    )
    for index in range(tests):
        case = ET.SubElement(suite, "testcase", name=f"test_{index}", classname="probe")
        for boundary, tag in (
            (failed, "failure"),
            (failed + errors, "error"),
            (failed + errors + skipped, "skipped"),
        ):
            if index < boundary:
                ET.SubElement(case, tag)
                break
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_partition_is_complete_disjoint_and_independent_of_collection_order() -> None:
    """Unbekanntes bleibt dabei, alte Gewichtseinträge schaffen dagegen keine Testdatei."""
    counts = _counts(**{"tests/test_a.py": 4, "tests/test_b.py": 2, "tests/test_new.py": 3})
    weights = {"tests/test_a.py": 9, "tests/test_b.py": 5, "tests/test_removed.py": 100}
    shards = runner.plan_shards(counts, weights, 7, group="windowed", shard_count=2)
    assert [[file.path for file in shard] for shard in shards] == [
        ["tests/test_a.py"],
        ["tests/test_new.py", "tests/test_b.py"],
    ]
    assert (
        runner.plan_shards(
            dict(reversed(list(counts.items()))), weights, 7, group="windowed", shard_count=2
        )
        == shards
    )
    contracts = runner.plan_shards(counts, weights, 7, group="contracts", shard_count=1)
    groups = [{file.path for file in shard} for shard in (*shards, *contracts)]
    assert set.union(*groups) == counts.keys()
    assert sum(map(len, groups)) == len(counts)
    assert sum(file.expected_tests for shard in (*shards, *contracts) for file in shard) == 11


def test_the_rendering_group_takes_every_file_but_the_contracts_with_its_own_marker() -> None:
    """Fensterverträge und Rendererfälle ergeben zusammen jeden Rendererfall, keinen doppelt.

    Die Gruppe ``rendering`` sammelt nur Rendererfälle ohne Fenster; die zwei
    Vertragsdateien fährt ``contracts`` auf jeder Plattform schon mit (RM-344).
    """
    counts = {
        "tests/test_render_factory.py": 3,
        "tests/test_render_contract.py": 24,
        "tests/test_new_renderer.py": 2,
    }
    (planned,) = runner.plan_shards(counts, {}, 5, group="rendering", shard_count=1)
    assert sorted(file.path for file in planned) == [
        "tests/test_new_renderer.py",
        "tests/test_render_contract.py",
    ]
    assert {file.marker for file in planned} == {runner.RENDERING_MARKER}
    command = runner.pytest_command(planned[0], Path("x.xml"))
    assert command[command.index("-m", 6) + 1] == runner.RENDERING_MARKER
    assert not any(runner.takes_file("rendering", path) for path in runner.CONTRACT_FILES)
    assert all(runner.takes_file("contracts", path) for path in runner.CONTRACT_FILES)
    (contracts,) = runner.plan_shards(_counts(), {}, 5, group="contracts", shard_count=1)
    assert {file.marker for file in contracts} == {runner.CI_MARKER}
    for broken, size in (({"tests/test_render_factory.py": 3}, 1), (counts, 2)):
        with pytest.raises(ValueError):
            runner.plan_shards(broken, {}, 5, group="rendering", shard_count=size)


def test_the_rendering_group_plans_from_its_own_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--ci-group rendering`` zählt Rendererfälle ohne Fenster und nennt seine Auswahl."""
    windows = {runner.ROOT / path: 1 for path in (*runner.CONTRACT_FILES, "tests/test_ui.py")}
    rendering = {
        runner.ROOT / "tests/test_render_factory.py": 3,
        runner.ROOT / "tests/test_a.py": 2,
    }
    monkeypatch.setattr(list_windowed_tests, "collect_ci_counts", lambda _: (windows, rendering))
    arguments = ["--ci-group", "rendering", "--report-dir", str(tmp_path), "--plan-only"]
    assert runner.main(arguments) == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["marker"] == runner.RENDERING_MARKER
    assert [file["path"] for file in summary["selected"]] == ["tests/test_a.py"]
    assert runner.RENDERING_MARKER in (tmp_path / "summary.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("red", ["contracts", "rendering", None])
def test_two_groups_share_one_collection_and_a_red_one_hides_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, red: str | None
) -> None:
    """Fensterverträge und Rendererfälle in einem Aufruf: eine Sammlung, je Gruppe ein
    Bericht, beide laufen, und eine rote Gruppe macht den Aufruf rot (G-10 aus dem
    Review von RM-344: die zweite Sammlung kostete je Läufer 10 bis 25 Sekunden)."""
    collections = []

    def collect(_: object) -> tuple[dict[Path, int], dict[Path, int]]:
        collections.append(1)
        return (
            {runner.ROOT / path: 1 for path in runner.CONTRACT_FILES},
            {runner.ROOT / "tests/test_a.py": 1},
        )

    monkeypatch.setattr(list_windowed_tests, "collect_ci_counts", collect)
    ran: list[tuple[str, str]] = []

    def run(file: runner.PlannedFile, directory: Path, *, timeout: float) -> dict[str, Any]:
        ran.append((directory.name, file.path))
        junit = directory / (file.path.replace("/", "__").removesuffix(".py") + ".xml")
        prepared = directory / f"prepared-{len(ran)}.xml"
        _junit(prepared)
        failing = int(directory.name == red)
        body = (
            f"import shutil; shutil.copyfile({str(prepared)!r}, {str(junit)!r}); "
            f"raise SystemExit({failing})"
        )
        return original(file, directory, timeout=timeout, command=[sys.executable, "-c", body])

    original = runner.run_ci_file
    monkeypatch.setattr(runner, "run_ci_file", run)
    arguments = ["--release", "--ci-group", "contracts", "--ci-group", "rendering"]
    assert runner.main([*arguments, "--report-dir", str(tmp_path)]) == int(red is not None)
    assert collections == [1]
    assert [group for group, _path in ran] == ["contracts", "contracts", "rendering"]
    for group, marker in (("contracts", runner.CI_MARKER), ("rendering", runner.RENDERING_MARKER)):
        summary = json.loads((tmp_path / group / "summary.json").read_text(encoding="utf-8"))
        assert summary["group"] == group and summary["marker"] == marker
        assert summary["status"] == ("failed" if group == red else "passed")
        assert summary["collection_seconds"] >= 0
    assert not (tmp_path / "summary.json").exists()


def test_a_group_named_twice_is_a_usage_error(tmp_path: Path) -> None:
    """Mit zweimal derselben Gruppe liefe jede ihrer Dateien doppelt (CI-01)."""
    arguments = ["--plan-only", "--ci-group", "rendering", "--ci-group", "rendering"]
    with pytest.raises(SystemExit) as error:
        runner.main([*arguments, "--report-dir", str(tmp_path)])
    assert error.value.code == 2


def test_tied_durations_use_the_path_and_then_the_shard_index() -> None:
    """Dasselbe vollständige Eingangsmaterial erzeugt auf beiden Runnern denselben Plan."""
    counts = _counts(**{f"tests/test_{name}.py": 1 for name in "dcba"})
    shards = runner.plan_shards(counts, {}, 4, group="windowed", shard_count=2)
    assert [[file.path for file in shard] for shard in shards] == [
        ["tests/test_a.py", "tests/test_c.py"],
        ["tests/test_b.py", "tests/test_d.py"],
    ]


@pytest.mark.parametrize(
    "counts,group,size",
    [
        ({}, "contracts", 1),
        (_counts(), "windowed", 1),
        (_counts(**{"tests/test_a.py": 1}), "windowed", 2),
        (_counts(**{"tests/test_a.py": 0}), "windowed", 1),
        (_counts(), "contracts", 2),
        (_counts(), "unknown", 1),
    ],
)
def test_an_incomplete_or_empty_plan_is_not_an_acceptance(
    counts: dict[str, int], group: str, size: int
) -> None:
    """Leere Shards und verschwundene Plattformverträge werden ausdrücklich abgelehnt."""
    with pytest.raises(ValueError):
        runner.plan_shards(counts, {}, 5, group=group, shard_count=size)


@pytest.mark.parametrize("table", sorted(ci_shards.TABLES))
def test_each_duration_table_names_its_origin_and_real_test_files(table: str) -> None:
    """Eine Tabelle ist ein nachlesbarer Messnachweis, keine handgepflegte Auswahlliste.

    Geprüft wird die Zusage, nicht der Stand: Hier stand die Lauf-ID, die
    Dateizahl und die Sekunden von ``test_ui.py`` — und jede neu erzeugte
    Tabelle (``tools/ci_shards.py``) wäre daran rot geworden.
    """
    path = ci_shards.TABLES[table]
    document = json.loads(path.read_text(encoding="utf-8"))
    weights, fallback = ci_shards.read_durations(path)
    assert document["source"], "die Tabelle sagt nicht, woher ihre Sekunden kommen"
    assert len(weights) > 20 and fallback > 0
    assert all(name.startswith("tests/test_") and name.endswith(".py") for name in weights)
    if table == "windows":
        missing = sorted(runner.CONTRACT_FILES - weights.keys())
        assert not missing, (
            f"der Fenstertabelle fehlen {missing}: Sie kommt aus den Windows-Gruppen "
            "und den Windows-Berichten der Fensterverträge (Aufruf in tools/ci_shards.py)"
        )


def test_the_documented_table_command_covers_every_windows_report() -> None:
    """Der beschriebene Aufruf erzeugt eine Fenstertabelle, die der Test oben annimmt.

    Dort stand nur ``tests-windows-*``. Die zwei Fensterverträge laufen unter
    Windows aber in ``tests-contracts-windows-latest`` — eine Tabelle nach
    dieser Anleitung hätte sie nicht getragen, und die erste erzeugte Fassung
    wäre an der Prüfung oben rot geworden, ohne dass jemand wüsste, warum.
    """
    documentation = ci_shards.__doc__ or ""
    assert "ci_shards.py windows" in documentation
    command = documentation.split("ci_shards.py windows", 1)[1].split("\n\n", 1)[0]
    assert "berichte/tests-windows-*/tests__*.xml" in command
    # Das Artefakt der Fensterverträge trägt seit RM-344 je Gruppe einen Ordner.
    assert "berichte/tests-contracts-windows-latest/contracts/tests__*.xml" in command


@pytest.mark.parametrize("value", [0, -1, True, "4", float("nan"), float("inf")])
def test_invalid_durations_cannot_silently_distort_the_plan(tmp_path: Path, value: Any) -> None:
    """Eine fehlerhafte Messdatei wird korrigiert, statt zufällig verteilt."""
    path = tmp_path / "times.json"
    path.write_text(
        json.dumps(
            {"schema": 1, "durations_seconds": {"test.py": value}, "unknown_file_seconds": 2}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ci_shards.read_durations(path)


def test_ci_collection_excludes_generated_and_performance_cases_but_keeps_mixed_files(
    tmp_path: Path,
) -> None:
    """Die Sammlung nutzt echte vererbte Fixtures; die Testkörper werden nie ausgeführt."""
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    windowed: probe\n    rendering: probe\n"
        "    performance: probe\n    rendered: probe\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        "import pytest\n@pytest.fixture\ndef qt_app():\n"
        "    raise AssertionError('collection only')\n"
        "@pytest.fixture\ndef indirect(qt_app):\n    return qt_app\n"
        "@pytest.fixture\ndef require_graphics_adapter():\n"
        "    raise AssertionError('render fixture ran during collection')\n"
        "@pytest.fixture\ndef indirect_renderer(require_graphics_adapter):\n"
        "    return require_graphics_adapter\n"
        "@pytest.fixture\ndef native_window_platform():\n"
        "    raise AssertionError('native probe ran during collection')\n",
        encoding="utf-8",
    )
    mixed = tmp_path / "test_ci_collection_mixed.py"
    mixed.write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_renderer_via_fixture(indirect_renderer, value): pass\n"
        "@pytest.mark.rendering\ndef test_direct_renderer(): pass\n"
        "@pytest.mark.parametrize('value', [1, 2])\ndef test_window(indirect, value): pass\n"
        "@pytest.mark.windowed\ndef test_external(): pass\n"
        "@pytest.mark.windowed\n@pytest.mark.rendering\ndef test_window_and_renderer(): pass\n"
        "def test_native_window(native_window_platform): pass\n"
        "@pytest.mark.rendered\ndef test_generated(indirect): pass\n"
        "@pytest.mark.performance\ndef test_budget(indirect): pass\n"
        "def test_plain(): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "test_generated.py").write_text(
        "import pytest\n@pytest.mark.rendered\ndef test_generated(qt_app): pass\n", encoding="utf-8"
    )
    # Fenster- und Rendererfälle: 8. Die Gruppe ``rendering``: echte Grafik ohne
    # Fenster, also die zwei Fälle über die geerbte Fixture und der direkt
    # markierte (RM-344).
    expected = ({mixed.resolve(): 8}, {mixed.resolve(): 3})
    assert list_windowed_tests.collect_ci_counts((tmp_path,), confcutdir=tmp_path) == expected
    # Gleichlauf: Was die Sammlung je Gruppe zählt, wählt pytest mit dem Marker
    # dieser Gruppe im frischen Prozess auch aus — dieselbe Markierung über den
    # Fixture-Graphen, dieselben Fälle.
    for marker, counted in zip((runner.CI_MARKER, runner.RENDERING_MARKER), expected, strict=True):
        assert _chosen_by_pytest(tmp_path, marker) == {
            path.name: count for path, count in counted.items()
        }, marker


def _chosen_by_pytest(folder: Path, marker: str) -> dict[str, int]:
    """Je Datei, wie viele Fälle ``pytest --collect-only -m marker`` wählt, mit der
    Markierung aus ``tools/list_windowed_tests.py`` wie im Lauf der CI."""
    done = subprocess.run(
        [
            sys.executable,
            *("-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"),
            *("-p", "tools.list_windowed_tests", "-c", str(folder / "pytest.ini")),
            *("--rootdir", str(folder), "-m", marker, str(folder)),
        ],
        cwd=runner.ROOT,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    chosen: dict[str, int] = {}
    for line in done.stdout.splitlines():
        if "::" in line:
            name = Path(line.split("::", 1)[0]).name
            chosen[name] = chosen.get(name, 0) + 1
    return chosen


def test_renderer_group_keeps_pure_cases_from_mixed_files(tmp_path: Path) -> None:
    """Indirekte Grafik und Direktmarker gehen ins Release; reine Fälle bleiben regulär."""
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    rendering: probe\n    windowed: probe\n    rendered: probe\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        "import pytest\n@pytest.fixture\ndef require_graphics_adapter():\n"
        "    raise AssertionError('collection only')\n"
        "@pytest.fixture\ndef qt_app():\n"
        "    raise AssertionError('collection only')\n"
        "@pytest.fixture\ndef renderer(require_graphics_adapter):\n"
        "    return require_graphics_adapter\n",
        encoding="utf-8",
    )
    mixed = tmp_path / "test_renderer_group_mixed.py"
    mixed.write_text(
        "import pytest\ndef test_plain(): pass\n"
        "def test_indirect(renderer): pass\n"
        "@pytest.mark.rendering\ndef test_direct(): pass\n",
        encoding="utf-8",
    )
    generated = tmp_path / "test_renderer_group_generated.py"
    generated.write_text(
        "import pytest\n@pytest.mark.rendered\ndef test_generated(): pass\n",
        encoding="utf-8",
    )
    combined = tmp_path / "test_renderer_group_rendered_combined.py"
    combined.write_text(
        "import pytest\n"
        "@pytest.mark.rendered\ndef test_rendered_window(qt_app): pass\n"
        "@pytest.mark.rendered\ndef test_rendered_renderer(require_graphics_adapter): pass\n",
        encoding="utf-8",
    )

    release, plain = list_windowed_tests.collect_test_groups(
        (mixed, generated, combined), confcutdir=tmp_path
    )
    release_with_generated, plain_with_generated = list_windowed_tests.collect_test_groups(
        (mixed, generated, combined), confcutdir=tmp_path, include_rendered=True
    )

    assert release == (mixed.resolve(),)
    assert plain == (mixed.resolve(),)
    assert release_with_generated == (mixed.resolve(), combined.resolve())
    assert plain_with_generated == (generated.resolve(), mixed.resolve())
    assert (
        list_windowed_tests.collect_windowed((mixed, generated, combined), confcutdir=tmp_path)
        == release_with_generated
    )
    assert list_windowed_tests.collect_ci_counts((mixed, generated, combined), confcutdir=tmp_path)[
        0
    ] == {mixed.resolve(): 2}
    assert list_windowed_tests.WINDOW_GROUPS == {
        "plain": "not windowed and not rendering",
        "windowed": "(windowed or rendering)",
    }


def test_an_empty_user_filter_keeps_pytests_nonzero_exit(tmp_path: Path) -> None:
    """Die Gruppenlogik darf eine ausdrücklich leere ``-k``-Wahl nicht grün färben."""
    config = tmp_path / "pytest.ini"
    config.write_text(
        "[pytest]\nmarkers =\n    rendering: probe\n    windowed: probe\n",
        encoding="utf-8",
    )
    probe = tmp_path / "test_empty_user_filter.py"
    probe.write_text("def test_plain(): pass\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tools.list_windowed_tests",
            "--window-group",
            "plain",
            "-k",
            "no_such_test",
            "-c",
            str(config),
            "--confcutdir",
            str(tmp_path),
            str(probe),
        ],
        cwd=runner.ROOT,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == pytest.ExitCode.NO_TESTS_COLLECTED, result.stdout + result.stderr


def test_graphics_adapter_probe_is_lazy_and_uses_the_selected_adapter(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Die geteilte Fixture fragt das Gerät erst nach ihrer Anforderung ab."""
    calls: list[str] = []
    adapter = object()

    def request_adapter_sync(*, power_preference: str) -> object:
        calls.append(power_preference)
        return adapter

    monkeypatch.setitem(
        sys.modules,
        "wgpu",
        SimpleNamespace(gpu=SimpleNamespace(request_adapter_sync=request_adapter_sync)),
    )

    conftest_path = Path(__file__).with_name("conftest.py").resolve()
    shared_conftest = next(
        plugin
        for plugin in request.config.pluginmanager.get_plugins()
        if getattr(plugin, "__file__", None) and Path(plugin.__file__).resolve() == conftest_path
    )
    assert shared_conftest._graphics_adapter_problem() is None
    assert calls == ["high-performance"]


def test_render_test_modules_do_not_query_a_device_during_import_or_collection() -> None:
    """Nur die gewählte Adapterfixture darf die Treiberfrage ausführen."""
    root = Path(__file__).resolve().parents[1]
    renderer_files = (
        "test_render_contract.py",
        "test_render_factory.py",
        "test_render_gizmo.py",
        "test_render_gfx_regressions.py",
        "test_feature_label_layout.py",
    )
    for name in renderer_files:
        source = (root / "tests" / name).read_text(encoding="utf-8")
        assert "request_adapter_sync" not in source, name
        assert "GFX_MISSING" not in source, name

    shared_source = (root / "tests" / "conftest.py").read_text(encoding="utf-8")
    tree = ast.parse(shared_source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "request_adapter_sync"
    ]
    assert len(calls) == 1
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    parent = parents[calls[0]]
    while not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        parent = parents[parent]
    assert parent.name == "_graphics_adapter_problem"


def test_renderer_collection_does_not_request_an_adapter() -> None:
    """Frische Sammlung echter Rendererfälle bleibt ohne Geräteabfrage und Ausführung."""
    root = Path(__file__).resolve().parents[1]
    script = """
import wgpu

calls = []
def request_adapter_sync(*, power_preference):
    calls.append(power_preference)
    return object()

wgpu.gpu.request_adapter_sync = request_adapter_sync
import pytest
result = pytest.main([
    "--collect-only", "-q", "-p", "no:cacheprovider", "-m", "rendering",
    "tests/test_render_contract.py",
])
assert int(result) == 0, result
assert calls == [], calls
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_real_renderer_entry_points_have_a_release_only_dependency() -> None:
    """Fixturewege und direkte Rendereraufbauten bleiben aus dem Entwicklungstor."""
    root = Path(__file__).resolve().parents[1] / "tests"
    cases = {
        "test_render_contract.py": {
            "renderer": "fixture",
            "test_labels_render_in_a_fresh_interpreter": "fixture",
        },
        "test_render_gizmo.py": {"scene": "fixture"},
        "test_render_gfx_regressions.py": {
            "renderer": "fixture",
            "test_the_steady_light_draws_the_stock_image_without_turning_each_frame": "fixture",
        },
        "test_render_factory.py": {
            "test_availability_is_a_plain_answer": "mark",
            "test_ci_has_a_working_graphics_adapter": "mark",
            "test_the_factory_builds_pygfx_without_a_window": "fixture",
            "test_native_qt_canvas_draws_and_releases_its_renderer": "fixture",
            "test_native_item_pick_slack_stays_constant_on_hidpi_screens": "fixture",
        },
        "test_feature_label_layout.py": {
            "test_gfx_label_field_covers_its_leader_without_covering_picks": "fixture",
        },
    }
    for filename, expected in cases.items():
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name, kind in expected.items():
            function = functions[name]
            decorators = [ast.unparse(decorator) for decorator in function.decorator_list]
            arguments = {
                argument.arg
                for argument in (
                    *function.args.posonlyargs,
                    *function.args.args,
                    *function.args.kwonlyargs,
                )
            }
            if kind == "fixture":
                assert "require_graphics_adapter" in arguments or any(
                    "usefixtures('require_graphics_adapter')" in decorator
                    or 'usefixtures("require_graphics_adapter")' in decorator
                    for decorator in decorators
                ), f"{filename}::{name} braucht die Adapterfixture"
            else:
                assert any("pytest.mark.rendering" in decorator for decorator in decorators), (
                    f"{filename}::{name} braucht den Marker rendering"
                )


def test_a_broken_collection_does_not_return_a_partial_plan(tmp_path: Path) -> None:
    """Ein importierbarer Nachbar darf eine kaputte Datei nicht verdecken.

    Die Meldung nennt den Fehler und nicht jeden gesammelten Fall davor: Über
    die ganze Suite waren das 1,9 MB Fallkennungen, mehr als GitHub im
    Schrittbericht eines Schritts annimmt (1 MiB) — der Grund des Abbruchs
    stand dann nur noch im Artefakt.
    """
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "test_many.py").write_text(
        "import pytest\n@pytest.mark.parametrize('n', range(40))\ndef test_case(n): pass\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="sammeln") as raised:
        list_windowed_tests.collect_ci_counts((tmp_path,), confcutdir=tmp_path)
    message = str(raised.value)
    assert "test_broken.py" in message and "SyntaxError" in message
    assert "test_case[" not in message, "die Meldung trägt die ganze Fallliste"


def test_each_real_pytest_command_preserves_the_fixed_ci_selection(tmp_path: Path) -> None:
    """Frische Python-Prozesse tragen Marker, JUnit, Dauerbericht und Hängerdiagnose."""
    command = runner.pytest_command(runner.PlannedFile("tests/test_x.py", 1, 3), tmp_path / "x.xml")
    assert command[:6] == [str(runner.PYTHON), "-u", "-X", "faulthandler", "-m", "pytest"]
    assert (
        command[command.index("-m", 6) + 1]
        == "(windowed or rendering) and not performance and not rendered"
    )
    # Die Rendererfälle ohne Fenster als Wert, nicht über die Konstante: Wer die
    # Gruppe verengt, schreibt CI-03 fort und diese Zeile mit.
    rendering = runner.PlannedFile("tests/test_x.py", 1, 3, runner.RENDERING_MARKER)
    command = runner.pytest_command(rendering, tmp_path / "x.xml")
    assert (
        command[command.index("-m", 6) + 1]
        == "rendering and not windowed and not performance and not rendered"
    )
    assert "faulthandler_timeout=120" in command and "--durations=30" in command
    assert "-n" not in command and command[-1] == "tests/test_x.py"
    assert f"--junitxml={tmp_path / 'x.xml'}" in command


@pytest.mark.parametrize("failed", [False, True])
def test_real_pytest_child_reports_success_and_assertion_failure(
    tmp_path: Path, failed: bool
) -> None:
    """Echter pytest-Prozess ohne Qt und ohne Repository-Fixtures liefert überprüfbares JUnit."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(f"def test_probe():\n    assert {not failed!r}\n", encoding="utf-8")
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    junit = tmp_path / "tests__test_probe.xml"
    result = runner.run_ci_file(
        runner.PlannedFile("tests/test_probe.py", 1, 1),
        tmp_path,
        timeout=30,
        command=[
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-c",
            str(config),
            "--confcutdir",
            str(tmp_path),
            f"--junitxml={junit}",
            str(probe),
        ],
    )
    assert result["success"] is not failed
    assert result["exit_code"] == int(failed)
    assert result["counts"]["tests"] == 1
    assert result["counts"]["failures"] == int(failed)
    assert result["process_seconds"] > 0
    assert (tmp_path / result["log"]).is_file()


@pytest.mark.parametrize(
    "case",
    ["missing", "malformed", "empty", "partial", "failed", "exit5", "crash", "crash_after_junit"],
)
def test_green_text_and_old_reports_cannot_hide_incomplete_children(
    tmp_path: Path, case: str
) -> None:
    """Kleine echte Prozesse decken fehlende Berichte und Abbruch nach einer grünen Zeile auf."""
    junit = tmp_path / "tests__test_probe.xml"
    _junit(junit)
    body = "print('1 passed in 0.01s', flush=True)\n"
    if case == "malformed":
        body += f"from pathlib import Path\nPath({str(junit)!r}).write_text('<broken')\n"
    elif case not in {"missing", "exit5", "crash"}:
        prepared = tmp_path / "prepared.xml"
        _junit(prepared, tests=0 if case == "empty" else 1, failed=int(case == "failed"))
        body += f"import shutil\nshutil.copyfile({str(prepared)!r}, {str(junit)!r})\n"
    if case in {"exit5", "crash", "crash_after_junit"}:
        body += f"import os\nos._exit({5 if case == 'exit5' else 139})\n"
    result = runner.run_ci_file(
        runner.PlannedFile("tests/test_probe.py", 2 if case == "partial" else 1, 1),
        tmp_path,
        timeout=10,
        command=[sys.executable, "-c", body],
    )
    assert not result["success"] and result["issues"]
    assert result["exit_code"] == (
        {"exit5": 5, "crash": 139, "crash_after_junit": 139}.get(case, 0)
    )
    if case == "crash_after_junit":
        assert result["counts"]["passed"] == 1
    assert "1 passed" in (tmp_path / result["log"]).read_text(encoding="utf-8")
    if case == "missing":
        assert not junit.exists(), "old JUnit survived a new process"


def test_timeout_waits_for_the_direct_child_to_end(tmp_path: Path) -> None:
    """Der Kindprozess schreibt vor dem Warten; nach der Zeitgrenze ist sein echter Exit bekannt."""
    result = runner.run_ci_file(
        runner.PlannedFile("tests/test_timeout.py", 1, 1),
        tmp_path,
        timeout=5,
        command=[sys.executable, "-u", "-c", "import time; print('started'); time.sleep(60)"],
    )
    assert not result["success"] and result["timed_out"]
    assert isinstance(result["exit_code"], int) and result["exit_code"] != 0
    assert result["process_seconds"] < 15
    assert "started" in (tmp_path / result["log"]).read_text(encoding="utf-8")


def _process_alive(pid: int) -> bool:
    """Fragt die Probe ab; bereits beendete POSIX-Zombies zählen nicht als laufend."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = Path(f"/proc/{pid}/stat")
    if not Path("/proc").is_dir():
        return True  # macOS: ohne /proc genügt die Antwort von ``kill``
    # Gelesen, nicht vorher gefragt: Der Prozess kann zwischen ``kill`` und dem
    # Lesen enden und abgeholt werden. Linux meldet das dann als
    # ``ProcessLookupError`` (ESRCH) oder als fehlende Datei — beides heißt
    # „nicht mehr am Leben“ (CI 0.5.1, ubuntu).
    try:
        return status.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError, ProcessLookupError:
        return False


def test_timeout_ends_children_and_grandchildren_without_qt(tmp_path: Path) -> None:
    """Der echte Prozessbaum hat drei Ebenen; nach Ablauf lebt keine davon weiter."""
    scripts = [tmp_path / f"probe_{index}.py" for index in range(3)]
    pids = [tmp_path / f"pid_{index}.txt" for index in range(3)]
    for index, script in reversed(list(enumerate(scripts))):
        body = "import os, subprocess, sys, time\nfrom pathlib import Path\n"
        body += f"Path({str(pids[index])!r}).write_text(str(os.getpid()))\n"
        if index < 2:
            body += f"child = subprocess.Popen([sys.executable, {str(scripts[index + 1])!r}])\n"
        body += "time.sleep(60)\n"
        script.write_text(body, encoding="utf-8")
    result = runner.run_ci_file(
        runner.PlannedFile("tests/test_tree.py", 1, 1),
        tmp_path,
        timeout=5,
        command=[sys.executable, str(scripts[0])],
    )
    assert result["timed_out"] and not result["success"]
    assert all(path.is_file() for path in pids), "probe did not finish starting before timeout"
    identifiers = [int(path.read_text()) for path in pids]
    deadline = time.monotonic() + 3
    alive = [pid for pid in identifiers if _process_alive(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(0.05)
        alive = [pid for pid in identifiers if _process_alive(pid)]
    assert not alive, f"processes survived timeout: {alive}"


def test_junit_totals_must_match_the_actual_cases(tmp_path: Path) -> None:
    """Eine formal gültige XML-Datei darf keine fehlenden Fälle versprechen."""
    path = tmp_path / "results.xml"
    _junit(path, tests=4, failed=1, errors=1, skipped=1)
    assert runner.junit_counts(path) == {
        "tests": 4,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "passed": 1,
    }
    path.write_text(
        path.read_text(encoding="utf-8").replace('tests="4"', 'tests="5"'), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Fallzahlen"):
        runner.junit_counts(path)


def _mock_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwei Dateifälle und beide Plattformverträge, ohne die echte Suite zu importieren."""
    counts = _counts(**{"tests/test_a.py": 1, "tests/test_b.py": 1})
    monkeypatch.setattr(
        list_windowed_tests,
        "collect_ci_counts",
        lambda _: ({runner.ROOT / path: count for path, count in counts.items()}, {}),
    )


def test_planning_without_release_cannot_start_a_test_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Plan ist reviewbar, ohne damit Fensterprüfungen freizugeben."""
    _mock_collection(monkeypatch)
    monkeypatch.setattr(
        runner, "run_ci_file", lambda *args, **kwargs: pytest.fail("plan executed a file")
    )
    assert (
        runner.main(
            [
                "--ci-group",
                "windowed",
                "--shard-count",
                "2",
                "--report-dir",
                str(tmp_path),
                "--plan-only",
            ]
        )
        == 0
    )
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "planned" and summary["results"] == []
    assert len(summary["plan"]) == 2 and len(summary["selected"]) == 1
    assert "grün" not in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_a_failed_file_remains_failed_after_a_successful_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beide Dateien laufen und werden berichtet; das letzte Grün ersetzt nie das erste Rot."""
    _mock_collection(monkeypatch)
    calls = []

    def run(file: runner.PlannedFile, directory: Path, *, timeout: float) -> dict[str, Any]:
        calls.append(file.path)
        junit = directory / (file.path.replace("/", "__").removesuffix(".py") + ".xml")
        prepared = directory / f"prepared-{len(calls)}.xml"
        _junit(prepared)
        body = (
            f"import shutil; shutil.copyfile({str(prepared)!r}, {str(junit)!r}); "
            f"raise SystemExit({int(len(calls) == 1)})"
        )
        return original(file, directory, timeout=timeout, command=[sys.executable, "-c", body])

    original = runner.run_ci_file
    monkeypatch.setattr(runner, "run_ci_file", run)
    assert runner.main(["--release", "--ci-group", "windowed", "--report-dir", str(tmp_path)]) == 1
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert len(calls) == 2 and summary["status"] == "failed"
    assert [result["exit_code"] for result in summary["results"]] == [1, 0]
    assert all(result["counts"]["tests"] == 1 for result in summary["results"])


def test_a_long_measured_file_gets_room_above_its_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Datei, die schon gemessen nahe an der festen Grenze liegt, riss sie
    je nach Runner (``test_ui.py`` unter Windows); sie bekommt Spielraum über
    ihrer Messung, eine kurze behält die Untergrenze."""
    _mock_collection(monkeypatch)
    monkeypatch.setattr(runner, "read_durations", lambda _path: ({"tests/test_a.py": 800.0}, 5.0))
    budgets: dict[str, float] = {}

    def run(file: runner.PlannedFile, directory: Path, *, timeout: float) -> dict[str, Any]:
        budgets[file.path] = timeout
        junit = directory / (file.path.replace("/", "__").removesuffix(".py") + ".xml")
        prepared = directory / f"prepared-{len(budgets)}.xml"
        _junit(prepared)
        body = f"import shutil; shutil.copyfile({str(prepared)!r}, {str(junit)!r})"
        return original(file, directory, timeout=timeout, command=[sys.executable, "-c", body])

    original = runner.run_ci_file
    monkeypatch.setattr(runner, "run_ci_file", run)
    assert runner.main(["--release", "--ci-group", "windowed", "--report-dir", str(tmp_path)]) == 0
    assert budgets["tests/test_a.py"] == pytest.approx(runner.BUDGET_HEADROOM * 800.0)
    assert budgets["tests/test_b.py"] == runner.BUDGET_SECONDS


def test_collection_failure_leaves_a_failed_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch vor dem ersten Datei-Prozess bleibt ein maschinenlesbarer Fehlernachweis."""

    def broken(_: object) -> tuple[dict[Path, int], dict[Path, int]]:
        raise RuntimeError("collection crashed")

    monkeypatch.setattr(list_windowed_tests, "collect_ci_counts", broken)
    assert (
        runner.main(["--plan-only", "--ci-group", "contracts", "--report-dir", str(tmp_path)]) == 1
    )
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed" and "collection crashed" in summary["issues"][0]
    assert summary["results"] == []


def test_a_collection_failure_stands_in_the_log_and_not_only_in_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Scheitert die Sammlung, sagt das CI-Protokoll warum — als Anmerkung und im Wortlaut.

    Vorher stand dort nur ``failed: …/summary.md``. Der Grund lag im Artefakt
    und im Schrittbericht — und dort, mit der ganzen Fallliste davor, über der
    Grenze von 1 MiB, die GitHub je Schritt annimmt. Die Ausgabe von pytest
    bleibt dabei Text, auch eine Zeile, die wie ein Workflow-Befehl aussieht.
    """

    def broken(_: object) -> tuple[dict[Path, int], dict[Path, int]]:
        raise RuntimeError(
            "Die Tests ließen sich nicht sammeln (Exit 2).\n"
            "::error::vorgetäuscht\n"
            "E   ImportError: kaputt"
        )

    monkeypatch.setattr(list_windowed_tests, "collect_ci_counts", broken)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert (
        runner.main(["--plan-only", "--ci-group", "contracts", "--report-dir", str(tmp_path)]) == 1
    )
    lines = capfd.readouterr().out.splitlines()
    stop = next(index for index, line in enumerate(lines) if line.startswith("::stop-commands::"))
    resume = lines.index(f"::{lines[stop].removeprefix('::stop-commands::')}::")
    assert stop < lines.index("::error::vorgetäuscht") < resume
    assert stop < lines.index("E   ImportError: kaputt") < resume
    headline = "CI-Auswahl oder Bericht prüfen: Die Tests ließen sich nicht sammeln (Exit 2)."
    assert f"::error title=CI-Gruppe contracts::{headline}" in lines[resume:]


def test_the_resume_token_gets_its_own_line_after_a_cut_off_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Ein Prozess, der mitten in einer Zeile endet, hält die Workflow-Befehle nicht an.

    ``pytest -v`` schreibt den Testnamen vor dem Ergebnis. Kommen Zeitgrenze
    oder ein Absturz ohne Traceback dazwischen, fehlt der Zeilenumbruch, und
    die Fortsetzung stand hinter dem Testnamen: GitHub erkannte sie nicht,
    und jede weitere Gruppe und Anmerkung des Jobs blieb Text — auch die rote
    Anmerkung der Datei, die gerade gescheitert war.
    """
    _mock_collection(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def run(file: runner.PlannedFile, directory: Path, *, timeout: float) -> dict[str, Any]:
        body = f"import sys; sys.stdout.write('{file.path}::test_hangs '); raise SystemExit(1)"
        return original(file, directory, timeout=timeout, command=[sys.executable, "-c", body])

    original = runner.run_ci_file
    monkeypatch.setattr(runner, "run_ci_file", run)
    assert runner.main(["--release", "--ci-group", "windowed", "--report-dir", str(tmp_path)]) == 1

    lines = capfd.readouterr().out.splitlines()
    tokens = [
        line.removeprefix("::stop-commands::")
        for line in lines
        if line.startswith("::stop-commands::")
    ]
    assert len(tokens) == 2
    assert all(f"::{token}::" in lines for token in tokens)
    assert lines.count("::endgroup::") == 2
    assert sum(line.startswith("::error title=tests/test_") for line in lines) == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ["--ci-group", "windowed"],
        ["--release", "--ci-group", "windowed"],
        ["--plan-only"],
        ["--plan-only", "--ci-group", "windowed", "--shard-index", "2", "--shard-count", "2"],
        # Ein Muster ohne Treffer: Fiele die Prüfung weg, endete der Lauf
        # ohne Prozess statt mit einem rekursiven Lauf dieser Datei.
        ["--timeout", "0", "no_file_matches_this"],
        ["--timeout", "nan", "no_file_matches_this"],
    ],
)
def test_invalid_cli_cannot_start_the_runner(tmp_path: Path, arguments: list[str]) -> None:
    """Releasefreigabe, Berichtsverzeichnis und Shardgrenzen werden vor Sammlung geprüft."""
    if "--shard-index" in arguments:
        arguments = [*arguments, "--report-dir", str(tmp_path)]
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2


def test_the_local_run_keeps_the_time_limit_it_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--timeout`` galt nur den CI-Gruppen; lokal lief jede Datei still mit 900 s weiter."""
    from tools import affected_tests

    limits: list[float] = []

    def finished(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        limits.append(options["timeout"])
        return subprocess.CompletedProcess(command, 0, "1 passed in 0.01s\n", "")

    monkeypatch.setattr(
        affected_tests, "split_windowed", lambda files, *, release=False: ([], list(files))
    )
    monkeypatch.setattr(subprocess, "run", finished)
    assert runner.main(["--timeout", "42", "test_ci_runner"]) == 0
    assert limits == [42.0]


# --- Die Teile der Kernsuite (tools/ci_shards.py) ------------------------------


def test_the_core_partition_is_complete_disjoint_and_independent_of_order() -> None:
    """Jede Datei in genau einem Teil; dieselben Gewichte ergeben überall denselben Plan."""
    weights = {"tests/test_a.py": 9.0, "tests/test_b.py": 5.0, "tests/test_c.py": 4.0}
    weights |= {"tests/test_d.py": 4.0, "tests/test_e.py": 1.0}
    plan = ci_shards.balanced(weights, 3)
    assert plan == (
        ("tests/test_a.py",),
        ("tests/test_b.py", "tests/test_e.py"),
        ("tests/test_c.py", "tests/test_d.py"),
    )
    assert ci_shards.balanced(dict(reversed(list(weights.items()))), 3) == plan
    groups = [set(group) for group in plan]
    assert set.union(*groups) == weights.keys() and sum(map(len, groups)) == len(weights)
    with pytest.raises(ValueError):
        ci_shards.balanced(weights, 0)


@pytest.mark.parametrize("value", ["3/3", "0/0", "-1/3", "a/3", "1", "1/", "/3", "1/3/4"])
def test_a_shard_outside_its_range_is_a_usage_error(value: str) -> None:
    """``I/N`` mit ``0 <= I < N`` — alles andere hält den Lauf vor der Sammlung an."""

    class Config:
        def getoption(self, name: str, default: object = None) -> str:
            return value

        pluginmanager = None

    with pytest.raises(pytest.UsageError, match="CI-Teil"):
        ci_shards.register(Config())  # type: ignore[arg-type]


def _collected(*extra: str) -> list[str]:
    """Sammelt echte Testdateien über die echte ``conftest.py`` in einem frischen Prozess."""
    files = (
        "tests/test_ci_runner.py",
        "tests/test_affected_tests.py",
        "tests/test_suite_script.py",
        "tests/test_memory_index.py",
    )
    done = runner.subprocess.run(
        [
            sys.executable,
            *("-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"),
            *(
                "-m",
                "not windowed and not performance and not rendered and not rendering",
                *extra,
                *files,
            ),
        ],
        cwd=runner.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return [line for line in done.stdout.splitlines() if "::" in line]


def test_the_core_shards_collect_every_case_exactly_once_and_whole_files() -> None:
    """``--ci-shard`` am wirklichen Weg: kein Fall fehlt, keiner doppelt, keine Datei zerfällt."""
    everything = _collected()
    parts = [_collected("--ci-shard", f"{index}/2") for index in range(2)]
    assert everything and all(parts)
    assert sorted(parts[0] + parts[1]) == sorted(everything)
    files = [{case.split("::", 1)[0] for case in part} for part in parts]
    assert not files[0] & files[1]


def test_a_duration_table_is_rebuilt_from_junit_reports(tmp_path: Path) -> None:
    """Sekunden je Datei aus den Fällen, Klassen zählen zu ihrer Datei, nichts rundet auf null."""
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for classname, seconds in (
        ("tests.test_a", "1.5"),
        ("tests.test_a.TestInner", "2.25"),
        ("tests.test_b", "0.001"),
        ("tests.test_c", "40"),
    ):
        ET.SubElement(suite, "testcase", classname=classname, name="test_x", time=seconds)
    report = tmp_path / "junit.xml"
    ET.ElementTree(root).write(report, encoding="utf-8")

    seconds = ci_shards.junit_file_seconds([report])
    assert seconds == pytest.approx(
        {"tests/test_a.py": 3.75, "tests/test_b.py": 0.001, "tests/test_c.py": 40.0}
    )
    table = ci_shards.table_from(seconds, [report], "Probe")
    assert table["durations_seconds"]["tests/test_b.py"] == 0.01
    assert table["unknown_file_seconds"] == 40.0
    path = tmp_path / "table.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    assert ci_shards.read_durations(path)[0]["tests/test_a.py"] == 3.75

    suite.append(ET.Element("testcase", classname="helpers", name="x", time="1"))
    ET.ElementTree(root).write(report, encoding="utf-8")
    with pytest.raises(ValueError, match="Testmodul"):
        ci_shards.junit_file_seconds([report])


def test_a_github_annotation_keeps_its_text_in_one_command() -> None:
    """Prozent, Zeilenumbruch und in der Überschrift Doppelpunkt und Komma sind maskiert."""
    line = runner.annotation("error", "tests/a:b,c.py", "50 % rot\nzweite Zeile", github=True)
    assert line == "::error title=tests/a%3Ab%2Cc.py::50 %25 rot%0Azweite Zeile"
    assert runner.annotation("error", "tests/a.py", "x", github=False) == "rot: tests/a.py: x"


def test_the_console_shows_each_file_and_the_step_summary_the_whole_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Die Ausgabe steht im CI-Protokoll, nicht nur im Artefakt; die Tabelle im Schrittbericht."""
    _mock_collection(monkeypatch)
    step_summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
    calls = []

    def run(file: runner.PlannedFile, directory: Path, *, timeout: float) -> dict[str, Any]:
        calls.append(file.path)
        junit = directory / (file.path.replace("/", "__").removesuffix(".py") + ".xml")
        prepared = directory / f"prepared-{len(calls)}.xml"
        _junit(prepared)
        body = (
            f"import shutil; print('Ausgabe aus {file.path}', flush=True); "
            f"shutil.copyfile({str(prepared)!r}, {str(junit)!r}); "
            f"raise SystemExit({int(len(calls) == 1)})"
        )
        return original(file, directory, timeout=timeout, command=[sys.executable, "-c", body])

    original = runner.run_ci_file
    monkeypatch.setattr(runner, "run_ci_file", run)
    report_dir = tmp_path / "reports"
    assert (
        runner.main(["--release", "--ci-group", "windowed", "--report-dir", str(report_dir)]) == 1
    )

    output = capfd.readouterr().out
    first, second = calls
    assert f"::group::{first} (1 Fälle)" in output and f"Ausgabe aus {first}" in output
    assert f"Ausgabe aus {second}" in output and output.count("::endgroup::") == 2
    assert f"::error title={first}::" in output and f"::error title={second}::" not in output
    # Die Prüfausgabe steht zwischen Anhalten und Fortsetzen der Workflow-Befehle.
    lines = output.splitlines()
    stop = next(index for index, line in enumerate(lines) if line.startswith("::stop-commands::"))
    token = lines[stop].removeprefix("::stop-commands::")
    resume = lines.index(f"::{token}::")
    assert stop < lines.index(f"Ausgabe aus {first}") < resume < lines.index("::endgroup::")
    summary = step_summary.read_text(encoding="utf-8")
    assert summary == (report_dir / "summary.md").read_text(encoding="utf-8") + "\n"
    assert f"| {first} | 1/1 |" in summary


def test_an_escaped_descendant_does_not_hold_the_report_past_the_drain_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Enkel mit geerbter Ausgabe hält die Leitung offen; der Bericht wartet nicht auf ihn.

    Gefunden in der Durchsicht: ``Popen.__exit__`` schloss den Leser, während
    der Kopierfaden in dessen Lesen blockierte, und wartete damit so lange wie
    der Enkel lebte — 40 s statt der Nachfrist.
    """
    monkeypatch.setattr(runner, "OUTPUT_DRAIN_SECONDS", 1.0)
    pid_file = tmp_path / "enkel.txt"
    body = (
        "import subprocess, sys; from pathlib import Path; "
        "enkel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        f"Path({str(pid_file)!r}).write_text(str(enkel.pid)); print('Kind fertig', flush=True)"
    )
    try:
        result = runner.run_ci_file(
            runner.PlannedFile("tests/test_escape.py", 1, 1),
            tmp_path,
            timeout=20,
            command=[sys.executable, "-c", body],
        )
        assert result["process_seconds"] < 10, result["process_seconds"]
        assert result["exit_code"] == 0 and result["notes"]
        assert "Kind fertig" in (tmp_path / result["log"]).read_text(encoding="utf-8")
    finally:
        if pid_file.is_file():
            pid = int(pid_file.read_text())
            if sys.platform == "win32":
                runner.subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                os.kill(pid, 9)
        # Nach dem Enkel endet die Leitung; der Faden schließt sie selbst.
        import threading

        for thread in threading.enumerate():
            if thread.name == "Ausgabe tests/test_escape.py":
                thread.join(10)
                assert not thread.is_alive(), "die übergebene Leitung wurde nie leer"


def test_a_failing_output_target_does_not_stop_draining_the_pipe() -> None:
    """Fällt Konsole oder Protokoll aus, wird weiter gelesen und ins andere geschrieben."""
    import io

    class Broken(io.BytesIO):
        def write(self, data: Any) -> int:
            raise OSError("Datenträger voll")

    chunks = [b"eins\n", b"zwei\n", b"drei\n"]

    class Source:
        def read1(self, size: int) -> bytes:
            return chunks.pop(0) if chunks else b""

    log = io.BytesIO()
    runner.copy_output(Source(), log, Broken())  # type: ignore[arg-type]
    assert log.getvalue() == b"eins\nzwei\ndrei\n" and not chunks

    chunks[:] = [b"eins\n", b"zwei\n"]
    console = io.BytesIO()
    runner.copy_output(Source(), Broken(), console)  # type: ignore[arg-type]
    assert console.getvalue() == b"eins\nzwei\n" and not chunks
