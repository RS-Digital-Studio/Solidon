"""Katalog, Vorschau, SCAD-Ausgabe, eigene Bausteine, Versionierung (Bauplan §24.3–24.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.knowledge.parts import PARTS, preview, scad, user
from app.core.knowledge.parts import check as part_check
from app.core.knowledge.parts.registry import LIBRARY_VERSION, PartRegistry, used_parts
from app.core.scene import History, OperationDraft
from app.core.scene.project import load, new_project, save
from app.core.types import Document, Source

MESHES = Path(__file__).parent / "data" / "meshes"


# --- previews (§24.3) --------------------------------------------------------------


@pytest.mark.parametrize("spec", PARTS.all(), ids=lambda spec: spec.name)
def test_every_part_renders_a_preview(spec: object) -> None:
    """§24.3: die Bilder kommen aus den Bausteinen, nicht aus einem Ordner."""
    image = preview.render(spec)  # type: ignore[arg-type]

    assert image.svg.startswith("<svg")
    assert image.svg.count("<polygon") == image.triangles
    assert image.triangles > 0


def test_a_subtractive_part_looks_different() -> None:
    """Eine Form, die Material wegnimmt, wird nicht gezeichnet wie eine, die
    welches hinzufügt (§19.1).
    """
    hole = preview.render(PARTS.get("screw_hole"))
    rib = preview.render(PARTS.get("rib"))

    assert hole.svg != rib.svg


def test_a_preview_can_be_written(tmp_path: Path) -> None:
    path = tmp_path / "rib.svg"
    preview.render(PARTS.get("rib")).write(path)

    assert path.read_text(encoding="utf-8").startswith("<svg")


# --- SCAD output (§24.1) ------------------------------------------------------------


def test_a_part_can_be_written_as_scad() -> None:
    text = scad.to_scad(PARTS.get("latch"))

    assert "module latch()" in text
    assert "polyhedron(" in text
    assert text.rstrip().endswith("latch();")


def test_the_scad_file_names_its_parameters() -> None:
    """Die Werte stehen in der Datei zum Lesen, auch wenn der Körper ein
    festes Netz ist.
    """
    text = scad.to_scad(PARTS.get("screw_hole"))

    assert 'size = "M3";' in text
    assert "countersink = true;" in text
    assert "kein parametrischer Nachbau" in text, "and it says what it is not"


def test_scad_follows_the_parameters() -> None:
    spec = PARTS.get("dowel")
    thin = scad.to_scad(spec, spec.params(diameter=3.0))
    thick = scad.to_scad(spec, spec.params(diameter=8.0))

    assert thin != thick


# --- own parts (§24.5) ---------------------------------------------------------------


OWN_PART = '''
"""An own part, as a user would write it."""

from app.core.knowledge.parts.build import bore, result
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.knowledge.parts.shapes import cylinder
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult


@op_params
class OwnParams(BaseParams):
    diameter: float = param(title="Durchmesser", default=6.0, unit="mm", minimum=1.0)


@register_part(
    name="eigenbau",
    title="Eigenbau",
    group="fasteners",
    params=OwnParams,
    subtractive=True,
    features=["bore"],
    doc="Ein selbst geschriebener Baustein.",
    changes=[PartChange(version="1", date="2026-07-28", reason="Erste Fassung.")],
)
def eigenbau(raw: BaseParams) -> PartResult:
    body = cylinder(raw.diameter, 10.0)
    return result(body, bore("bore_1", raw.diameter, (0.0, 0.0, 5.0), depth=10.0))
'''


def test_an_own_part_is_loaded_and_marked(tmp_path: Path) -> None:
    """§24.5: dieselbe Registrierung, aber der Katalog sagt, woher er kam."""
    (tmp_path / "eigenbau.py").write_text(OWN_PART, encoding="utf-8")
    registry = PartRegistry()

    import app.core.knowledge.parts.registry as registry_module

    original = registry_module.PARTS
    try:
        registry_module.PARTS = registry  # type: ignore[misc]
        result = user.load(tmp_path, registry)
    finally:
        registry_module.PARTS = original  # type: ignore[misc]

    assert result.loaded == ("eigenbau",)
    assert registry.get("eigenbau").own
    assert registry.get("eigenbau").source == "user"


def test_a_broken_own_part_is_reported_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "kaputt.py").write_text("this is not python", encoding="utf-8")

    result = user.load(tmp_path, PartRegistry())

    assert result.loaded == ()
    assert result.findings and result.findings[0].code == "parts.user_failed"


def test_a_missing_directory_is_not_an_error(tmp_path: Path) -> None:
    assert user.load(tmp_path / "gibtsnicht", PartRegistry()).loaded == ()


def test_an_own_part_never_travels_with_the_project(tmp_path: Path) -> None:
    """§24.5, §32: eine hereinkommende Datei darf keinen Code tragen — also
    trägt sie keinen.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    path = save(project, tmp_path / "projekt.p3d")
    import zipfile

    with zipfile.ZipFile(path) as container:
        names = container.namelist()

    assert not [name for name in names if name.endswith(".py")], "no code in a project file"


# --- versioning (§24.4) ---------------------------------------------------------------


def test_saving_records_the_library_version(tmp_path: Path) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document.parts_version = "0"

    save(project, tmp_path / "projekt.p3d")

    assert project.document.parts_version == LIBRARY_VERSION
    assert load(tmp_path / "projekt.p3d").document.parts_version == LIBRARY_VERSION


def test_the_used_parts_are_read_off_the_stack() -> None:
    """§24.4: welche Bausteine ein Projekt benutzt, folgt aus seinem Stapel
    und sonst nichts.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1")
    document.ops = [
        Operation(id=1, op="load", outputs=("obj_1",)),
        Operation(id=2, op="insert_screw_hole", inputs=("obj_1",), outputs=("obj_1",)),
        Operation(id=3, op="insert_rib", inputs=("obj_1",), outputs=("obj_1",)),
    ]

    assert used_parts(document.ops) == ("rib", "screw_hole")


def test_a_project_from_an_older_library_is_told_what_moved() -> None:
    """§24.4: welche *benutzten* Bausteine sich geändert haben, nicht nur dass
    sich etwas geändert hat.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version="0")
    document.ops = [
        Operation(id=1, op="load", outputs=("obj_1",)),
        Operation(id=2, op="insert_screw_hole", inputs=("obj_1",), outputs=("obj_1",)),
    ]

    findings = part_check.check(document)

    assert [finding.code for finding in findings] == ["parts.changed"]
    assert "screw_hole" in str(findings[0].values["parts"])


def test_a_project_of_the_current_library_says_nothing() -> None:
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version=LIBRARY_VERSION)
    document.ops = [Operation(id=2, op="insert_rib", inputs=("obj_1",), outputs=("obj_1",))]

    assert part_check.check(document) == []


def test_a_project_with_an_unknown_part_is_an_error() -> None:
    """§24.5: ein eigener Baustein von einer anderen Maschine hält die Kette
    an — still ist keine Option.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version=LIBRARY_VERSION)
    document.ops = [Operation(id=2, op="insert_eigenbau", inputs=("obj_1",), outputs=("obj_1",))]

    findings = part_check.check(document)

    assert findings[0].code == "parts.missing"
    assert findings[0].severity == "error"
    assert "eigenbau" in str(findings[0].values["parts"])
