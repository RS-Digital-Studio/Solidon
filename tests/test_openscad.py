"""OpenSCAD als geprüfte Rückfallebene (Bauplan §32, §36, §40 für P6).

Das Abnahmekriterium ist unmissverständlich: abgelehnter Quelltext wird
**nachweislich nicht ausgeführt**. Die Tests prüfen also nicht, dass ein Lauf
scheitert — sie prüfen, dass kein Lauf stattfindet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.backends import openscad
from app.core.errors import AppError

SAFE = """
$fn = 64;
difference() {
  cube([20, 20, 5], center = true);
  cylinder(h = 10, d = 4, center = true);
}
"""


# --- reading the source (§32) -------------------------------------------------------


def test_a_plain_source_is_allowed() -> None:
    check = openscad.check_source(SAFE)

    assert check.allowed
    assert not check.has_references


def test_a_relative_include_below_the_folder_is_allowed() -> None:
    check = openscad.check_source("include <parts/screw.scad>\ncube(1);")

    assert check.allowed
    assert check.references == ("parts/screw.scad",)


@pytest.mark.parametrize(
    "source",
    [
        "include <../../etc/passwd>",
        "include </etc/passwd>",
        "use <C:/Windows/system.ini>",
        "use <~/geheim.scad>",
        'import("../../modell.stl");',
        'surface(file = "/etc/hosts");',
        "include <https://example.invalid/x.scad>",
    ],
)
def test_a_reference_out_of_the_folder_is_refused(source: str) -> None:
    """§32: include, use, import und surface nur relativ und unterhalb."""
    check = openscad.check_source(source)

    assert not check.allowed
    assert check.refused
    assert check.findings[0].code == "scad.refused_reference"
    assert check.findings[0].severity == "error"


def test_the_finding_names_what_was_refused() -> None:
    check = openscad.check_source("include <../../geheim.scad>")

    assert "../../geheim.scad" in str(check.findings[0].values["reference"])


def test_a_mixture_is_refused_as_a_whole() -> None:
    """Ein schlechter Verweis genügt — der Rest wird nicht „so weit wie
    möglich" gelaufen.
    """
    check = openscad.check_source("include <lokal.scad>\ninclude </etc/passwd>\ncube(1);")

    assert not check.allowed
    assert check.references == ("lokal.scad",)
    assert check.refused == ("/etc/passwd",)


# --- Und der Lauf findet nie statt ------------------------------------------------


def test_refused_source_is_never_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    """§40 für P6: der Beweis ist, dass kein Prozess gestartet wird."""
    started: list[object] = []

    def never(*args: object, **kwargs: object) -> object:
        started.append(args)
        raise AssertionError("a refused source must not reach OpenSCAD")

    monkeypatch.setattr(openscad.subprocess, "run", never)
    monkeypatch.setattr(openscad, "executable", lambda: "openscad")

    with pytest.raises(openscad.UnsafeSource):
        openscad.render("include </etc/passwd>\ncube(1);")

    assert started == [], "no process was started"


def test_the_error_carries_a_way_out() -> None:
    """§33.1: jede Ausnahme nennt mindestens eine Sache zum Tun."""
    with pytest.raises(AppError) as raised:
        openscad.render("include </etc/passwd>")

    assert raised.value.suggestions


def test_without_an_installation_it_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """§36: OpenSCAD wird aufgerufen, nie mitgeliefert — es darf also fehlen."""
    monkeypatch.setattr(openscad, "executable", lambda: None)

    with pytest.raises(openscad.ScadUnavailable):
        openscad.render(SAFE)


def test_a_run_gets_its_own_folder_and_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """§32: fester Arbeitsordner je Lauf, kein Weg hinaus."""
    seen: dict[str, object] = {}

    class Completed:
        returncode = 0
        stderr = b""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        seen["command"] = command
        seen["cwd"] = kwargs.get("cwd")
        seen["env"] = kwargs.get("env")
        seen["timeout"] = kwargs.get("timeout")
        Path(command[2]).write_bytes(b"solid x\nendsolid x\n")
        return Completed()

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad.subprocess, "run", fake_run)

    result = openscad.render(SAFE)

    assert result.stl.startswith(b"solid")
    workspace = Path(str(seen["cwd"]))
    assert workspace.name.startswith("formwerk-scad-")
    environment = seen["env"]
    assert isinstance(environment, dict)
    assert environment["OPENSCADPATH"] == str(workspace)
    assert environment["HTTP_PROXY"] == "127.0.0.1:0"
    assert "APPDATA" not in environment, "the environment is trimmed, not passed on"
    assert seen["timeout"] == openscad.TIMEOUT_SECONDS


def test_a_render_says_where_the_body_came_from(monkeypatch: pytest.MonkeyPatch) -> None:
    """§26.4 dem Sinne nach: ein Körper aus OpenSCAD ist kein Körper aus der
    Bibliothek.
    """

    class Completed:
        returncode = 0
        stderr = b""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        Path(command[2]).write_bytes(b"solid x\nendsolid x\n")
        return Completed()

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad.subprocess, "run", fake_run)

    result = openscad.render(SAFE)

    assert result.findings[0].code == "scad.rendered"


def test_a_failed_render_is_an_error_with_the_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class Completed:
        returncode = 1
        stderr = b"ERROR: syntax error"

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad.subprocess, "run", lambda *a, **k: Completed())

    with pytest.raises(AppError) as raised:
        openscad.render("cube(")

    assert "syntax error" in str(raised.value.detail)
    assert raised.value.suggestions


def test_the_operation_checks_before_it_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """``create_from_scad`` ist die Rückfallebene — und sie prüft zuerst (§32)."""
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    spec = REGISTRY.get("create_from_scad")
    assert spec.consumes == 0 and spec.category == "primitive"

    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("a refused source must not reach OpenSCAD")

    monkeypatch.setattr(openscad.subprocess, "run", never)
    monkeypatch.setattr(openscad, "executable", lambda: "openscad")

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "SCAD",
        [OperationDraft(op="create_from_scad", params={"source": "include </etc/passwd>"})],
    )

    from app.core.knowledge import profiles

    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )

    assert not result.complete, "the chain stops instead of running it anyway"


def test_a_checked_source_becomes_a_body(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    class Completed:
        returncode = 0
        stderr = b""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        import trimesh

        body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        Path(command[2]).write_bytes(trimesh.exchange.stl.export_stl(body))
        return Completed()

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad.subprocess, "run", fake_run)

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "SCAD", [OperationDraft(op="create_from_scad", params={"source": "cube(10);"})]
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(1000.0, rel=0.01)
    assert "scad.rendered" in {finding.code for finding in result.scene.report.findings}


def test_no_core_path_needs_openscad() -> None:
    """§24.1: Bausteine bauen gegen manifold3d, die Bibliothek funktioniert
    also ohne.
    """
    from app.core.knowledge.parts import PARTS

    for spec in PARTS.all():
        result = spec.fn(spec.params())
        assert result.mesh.is_watertight, spec.name
