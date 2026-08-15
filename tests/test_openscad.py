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


# --- den Quelltext lesen (§32) ------------------------------------------------------


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
        # Die veralteten Einbindungen laufen in OpenSCAD weiter — nur als
        # DEPRECATED gemeldet, nicht verweigert. Eine Prüfung, die sie nicht
        # kennt, prüft die Hälfte.
        'import_stl("/etc/passwd");',
        'import_dxf("C:/geheim.dxf");',
        'import_off("~/netz.off");',
        'dxf_linear_extrude(file="/etc/passwd", height=2);',
        'dxf_rotate_extrude(file="../aussen.dxf");',
        'linear_extrude(height=2, file="/etc/passwd");',
        'rotate_extrude(file="C:/kontur.dxf");',
    ],
)
def test_a_reference_out_of_the_folder_is_refused(source: str) -> None:
    """§32: include, use, import und surface nur relativ und unterhalb —
    einschließlich der veralteten Formen und jedes ``file=``."""
    check = openscad.check_source(source)

    assert not check.allowed
    assert check.refused
    assert check.findings[0].code == "scad.refused_reference"
    assert check.findings[0].severity == "error"


@pytest.mark.parametrize(
    "source",
    [
        'import_stl("teile/deckel.stl");',
        'linear_extrude(height=2, file="kontur.dxf");',
    ],
)
def test_a_relative_legacy_include_is_allowed(source: str) -> None:
    """Die Altformen folgen derselben Regel wie ``import``: relativ und
    unterhalb des Arbeitsordners ist in Ordnung."""
    check = openscad.check_source(source)

    assert check.allowed
    assert check.references


def test_a_file_argument_without_a_literal_is_refused() -> None:
    """``file=`` mit einem Ausdruck statt einer Zeichenkette ist nicht
    prüfbar — wohin es führt, stünde erst zur Laufzeit fest."""
    check = openscad.check_source('name = "x.dxf";\nlinear_extrude(height=2, file=name);')

    assert not check.allowed
    assert check.refused


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

    monkeypatch.setattr(openscad, "run_guarded", never)
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
    monkeypatch.setattr(openscad, "run_guarded", fake_run)

    result = openscad.render(SAFE)

    assert result.stl.startswith(b"solid")
    workspace = Path(str(seen["cwd"]))
    assert workspace.name.startswith("solidon-scad-")
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
    monkeypatch.setattr(openscad, "run_guarded", fake_run)

    result = openscad.render(SAFE)

    assert result.findings[0].code == "scad.rendered"


def test_a_failed_render_is_an_error_with_the_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class Completed:
        returncode = 1
        stderr = b"ERROR: syntax error"

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad, "run_guarded", lambda *a, **k: Completed())

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

    monkeypatch.setattr(openscad, "run_guarded", never)
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
    monkeypatch.setattr(openscad, "run_guarded", fake_run)

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


# --- Die Grenzen des Unterprozesses (§32) -----------------------------------------


def _environment() -> dict[str, str]:
    """So viel Umgebung, wie ein Python-Start braucht — mehr nicht."""
    import os

    keep = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE")
    return {name: os.environ[name] for name in keep if name in os.environ}


def test_the_memory_limit_actually_bites(tmp_path: Path) -> None:
    """§32 verlangt Zeit **und** Speicher. Geprüft wird die Wirkung.

    Ein Zeitlimit allein lässt einen Quelltext, der in Schleifen Geometrie
    aufhäuft, erst nach einer Minute los — und bis dahin hat er den
    Arbeitsspeicher. Der Beweis ist deshalb ein echter Unterprozess, der mehr
    verlangt als er darf, und daran scheitert.

    Gemessen an Python statt an OpenSCAD: die Grenze gehört dem Aufruf, nicht
    dem Programm, und OpenSCAD ist auf einem Bauserver nicht installiert.
    """
    import sys

    completed = openscad.run_guarded(
        [sys.executable, "-c", "bytearray(1024**3)"],
        cwd=tmp_path,
        env=_environment(),
        timeout=120.0,
        memory=384 * 1024**2,
    )

    assert completed.returncode != 0, "ein Gigabyte unter einer 384-MB-Grenze muss scheitern"


def test_the_limit_leaves_a_reasonable_run_alone(tmp_path: Path) -> None:
    """Die Gegenprobe: eine Grenze, die alles erschlägt, wäre keine."""
    import sys

    completed = openscad.run_guarded(
        [sys.executable, "-c", "bytearray(8 * 1024**2)"],
        cwd=tmp_path,
        env=_environment(),
        timeout=120.0,
        memory=384 * 1024**2,
    )

    assert completed.returncode == 0


def test_a_run_over_its_time_is_stopped(tmp_path: Path) -> None:
    """Das Zeitlimit bleibt, was es war — und der Prozess überlebt es nicht."""
    import subprocess
    import sys

    with pytest.raises(subprocess.TimeoutExpired):
        openscad.run_guarded(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            env=_environment(),
            timeout=1.0,
        )


def test_no_core_path_needs_openscad() -> None:
    """§24.1: Bausteine bauen gegen manifold3d, die Bibliothek funktioniert
    also ohne.
    """
    from app.core.knowledge.parts import PARTS

    for spec in PARTS.all():
        result = spec.fn(spec.params())
        assert result.mesh.is_watertight, spec.name


def test_a_computed_path_is_refused() -> None:
    """§32: OpenSCAD nimmt an dieser Stelle jeden Ausdruck, nicht nur eine
    Zeichenkette.

    Die Literal-Suche fand einen berechneten Pfad gar nicht — sie meldete
    „kein Verweis" und gab den Lauf frei. Eine Prüfung, die eine
    Zeichenkettenverkettung umgeht, ist keine.
    """
    check = openscad.check_source('p = str("/e", "tc/passwd"); surface(file = p);')

    assert not check.allowed
    assert check.refused


def test_a_computed_import_is_refused() -> None:
    check = openscad.check_source("import(concat(a, b));")

    assert not check.allowed


def test_a_written_out_path_still_works() -> None:
    """Die Sperre darf den geraden Weg nicht mitnehmen."""
    check = openscad.check_source('import("teil.stl");\ninclude <lib.scad>\ncube(10);')

    assert check.allowed
    assert set(check.references) == {"teil.stl", "lib.scad"}


# --- was der Körper wert ist, wenn er ankommt ---------------------------------------


def test_a_body_from_openscad_arrives_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenSCAD schreibt STL, und STL kennt keine gemeinsamen Punkte.

    Über ``load`` verschweißt die Eingangsstufe sie und sagt es; dieser Weg
    ging daran vorbei. Ein Ø-12-Zylinder kam als 252 einzelne Dreiecke in der
    Szene an — nicht geschlossen, und die nächste boolesche Operation musste
    ihn erst retten.
    """
    import trimesh

    from app.core.registry import REGISTRY

    body = trimesh.creation.cylinder(radius=6.0, height=12.0, sections=64)

    class Completed:
        returncode = 0
        stderr = b""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        Path(command[2]).write_bytes(body.export(file_type="stl"))
        return Completed()

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad, "run_guarded", fake_run)

    spec = REGISTRY.get("create_from_scad")
    result = spec.fn(_context(spec, source="cylinder(h = 12, r = 6);"))

    mesh = result.outputs[0].mesh
    assert mesh.is_watertight, (
        "ein offener Körper zwingt die nächste Operation auf die Rückfallkette"
    )
    assert mesh.component_count == 1
    assert mesh.volume == pytest.approx(body.volume, rel=1e-6)


def test_an_empty_source_says_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Dialog geht mit leerem Feld auf; wer bestätigt, hat nichts
    geschrieben — und keinen Übersetzungsfehler gemacht.
    """
    from app.core.registry import REGISTRY

    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("ohne Quelltext gibt es nichts zu übersetzen")

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad, "run_guarded", never)

    spec = REGISTRY.get("create_from_scad")
    with pytest.raises(AppError) as raised:
        spec.fn(_context(spec, source="   "))

    assert raised.value.suggestions
    assert "übersetzen" not in str(raised.value.detail)


def _context(spec: object, **params: object) -> object:
    from app.core.knowledge import profiles
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    return OpContext(
        scene=Scene(),
        inputs=[],
        params=spec.params(**params),  # type: ignore[attr-defined]
        profile=profiles.make_profile(),
        quality="fine",
        seed=None,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )


def test_a_run_that_takes_too_long_is_an_error_with_a_way_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das Zeitlimit aus §32 greift — und muss ankommen wie jeder andere Fehler.

    ``sphere(r = 50, $fn = 2000)`` ist keine Bosheit, sondern ein Vertipper,
    und OpenSCAD rechnet daran länger als die Minute, die es bekommt. Heraus
    kam ``subprocess.TimeoutExpired``: kein ``AppError``, kein Titel, kein
    Vorschlag — ein Stapelabzug für einen Fall, den die Anwendung erwartet
    (Regel 17).
    """
    import subprocess

    def zu_langsam(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="openscad", timeout=60.0)

    monkeypatch.setattr(openscad, "executable", lambda: "openscad")
    monkeypatch.setattr(openscad, "run_guarded", zu_langsam)

    with pytest.raises(AppError) as raised:
        openscad.render(SAFE)

    assert raised.value.suggestions
    assert "60" in str(raised.value.values.get("seconds", ""))
