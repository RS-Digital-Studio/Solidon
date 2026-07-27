"""The project container: round trip, checksums, versions, autosave (§16, §32, §38)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.scene import History, OperationDraft
from app.core.scene.migrations import FORMAT_VERSION, Step, migrate
from app.core.scene.project import (
    PROJECT_ENTRY,
    Project,
    autosave_path,
    clear_autosave,
    find_recovery,
    load,
    new_project,
    project_data,
    save,
    write_autosave,
)
from app.core.types import (
    FeatureRef,
    Finding,
    Fit,
    IngestInfo,
    Operation,
    Origin,
    Parameter,
    Report,
    Source,
    SourceOrigin,
)
from app.i18n import _

MESH_PAYLOAD = b"solid test\nendsolid test\n"


EXAMPLE_FILE = Path(__file__).parent / "data" / "projects" / f"example_v{FORMAT_VERSION}.p3d"


@pytest.fixture
def filled() -> Project:
    return build_example_project()


def build_example_project() -> Project:
    """A project with everything the format has to carry.

    Also the source of the checked-in example file: every format version keeps
    one, so migrations can be tested against real files (§16.2).
    """
    project = new_project(printer="centauri-carbon-2", material="petg")
    document = project.document
    document.parameters["width"] = Parameter(
        name="width", value=84.0, unit="mm", minimum=40.0, maximum=200.0, title="Breite"
    )
    document.parameters["half"] = Parameter(name="half", value=42.0, expression="=@width/2")
    document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path="sources/halterung.stl",
        sha256="",
        ingest=IngestInfo(unit="mm", scale=1.0, welded=True, removed_triangles=4, components=2),
        origin=SourceOrigin(
            url="https://example.invalid/model",
            title="Halterung",
            author="Jemand",
            licence="CC BY-NC 4.0",
            retrieved="2026-07-20",
        ),
    )
    project.sources["src_1"] = MESH_PAYLOAD
    document.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_2", "op5.pin_1"),
            b=FeatureRef("obj_3", "op5.hole_1"),
            kind="clearance",
            tolerance="auto:petg",
        )
    )

    # One object has to exist before something can be done to it; the load
    # operation that will put it there is a later P0 step.
    document.ops.append(
        Operation(
            id=1, op="rename_object", inputs=(), outputs=("obj_1",), params={"name": "Halterung"}
        )
    )
    history = History(document)
    history.apply(
        _("Duplizieren"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "=@width"})],
        origin=Origin(by="agent", model="test", prompt_version="1", rules_version="7"),
    )
    project.report = Report(
        (Finding(code="ingest.welded", severity="info", message="Verschweißt.", op_id=1),)
    )
    project.thumbnail = b"\x89PNG\r\n\x1a\n"
    return project


def test_saving_and_loading_keeps_the_stack(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    reopened = load(path)

    assert reopened.document.ops == filled.document.ops
    assert [
        (entry.id, str(entry.title), entry.ops, entry.origin)
        for entry in reopened.document.transactions
    ] == [
        (entry.id, str(entry.title), entry.ops, entry.origin)
        for entry in filled.document.transactions
    ]
    assert reopened.document.parameters == filled.document.parameters
    assert reopened.document.fits == filled.document.fits
    assert reopened.document.printer == "centauri-carbon-2"
    assert reopened.sources["src_1"] == MESH_PAYLOAD
    assert reopened.thumbnail == filled.thumbnail
    assert reopened.report.findings[0].code == "ingest.welded"


def test_a_second_round_trip_writes_the_same_bytes(filled: Project, tmp_path: Path) -> None:
    """Bit-identical on save and load — the P0 acceptance criterion."""
    first = save(filled, tmp_path / "a.p3d")
    reopened = load(first)
    second = save(reopened, tmp_path / "b.p3d")

    assert project_data(first) == project_data(second)
    with zipfile.ZipFile(first) as one, zipfile.ZipFile(second) as two:
        assert one.read(PROJECT_ENTRY) == two.read(PROJECT_ENTRY)


def test_expressions_and_tolerance_references_survive(filled: Project, tmp_path: Path) -> None:
    reopened = load(save(filled, tmp_path / "projekt.p3d"))
    assert reopened.document.parameters["half"].expression == "=@width/2"
    assert reopened.document.fits[0].tolerance == "auto:petg"
    assert reopened.document.ops[-1].params["name"] == "=@width"


def test_provenance_of_a_transaction_survives(filled: Project, tmp_path: Path) -> None:
    reopened = load(save(filled, tmp_path / "projekt.p3d"))
    origin = reopened.document.transactions[0].origin
    assert origin.by == "agent"
    assert origin.model == "test"
    assert origin.rules_version == "7"


def test_the_licence_of_a_source_survives(filled: Project, tmp_path: Path) -> None:
    reopened = load(save(filled, tmp_path / "projekt.p3d"))
    origin = reopened.document.sources["src_1"].origin
    assert origin is not None
    assert origin.licence == "CC BY-NC 4.0"
    assert reopened.document.sources["src_1"].ingest.removed_triangles == 4


def test_checksums_are_written_and_verified(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    assert filled.document.sources["src_1"].sha256

    data = project_data(path)
    data["sources"]["src_1"]["sha256"] = "0" * 64
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_absolute_paths_are_refused(tmp_path: Path) -> None:
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="C:/somewhere/halterung.stl", sha256=""
    )
    project.sources["src_1"] = MESH_PAYLOAD

    with pytest.raises(ValidationError) as caught:
        save(project, tmp_path / "projekt.p3d")
    assert caught.value.constraint == "absolute_path"


def test_paths_leaving_the_container_are_refused(tmp_path: Path) -> None:
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="../outside.stl", sha256=""
    )
    project.sources["src_1"] = MESH_PAYLOAD

    with pytest.raises(ValidationError):
        save(project, tmp_path / "projekt.p3d")


def test_an_embedded_source_without_content_is_refused(tmp_path: Path) -> None:
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/a.stl", sha256=""
    )
    with pytest.raises(ValidationError) as caught:
        save(project, tmp_path / "projekt.p3d")
    assert caught.value.constraint == "missing_payload"


def test_a_newer_file_is_declined_in_a_friendly_way(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    data = project_data(path)
    data["format_version"] = FORMAT_VERSION + 5
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "too_new"
    assert caught.value.suggestions


def test_an_older_file_without_a_step_says_so() -> None:
    with pytest.raises(ValidationError) as caught:
        migrate({"format_version": 0}, target=1, steps=())
    assert caught.value.constraint == "no_migration"


def test_the_migration_chain_runs_step_by_step() -> None:
    def first(data: dict[str, object]) -> dict[str, object]:
        data["parts_version"] = "1"
        return data

    def second(data: dict[str, object]) -> dict[str, object]:
        data["libs"] = {"manifold3d": "3.2.1"}
        return data

    steps = (Step(0, 1, first), Step(1, 2, second))
    result = migrate({"format_version": 0}, target=2, steps=steps)

    assert result["format_version"] == 2
    assert result["parts_version"] == "1"
    assert result["libs"] == {"manifold3d": "3.2.1"}


def test_a_damaged_container_is_reported_not_raised_raw(tmp_path: Path) -> None:
    path = tmp_path / "kaputt.p3d"
    path.write_bytes(b"this is not a zip file")
    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "damaged"


def test_a_zip_without_a_project_is_not_a_project(tmp_path: Path) -> None:
    path = tmp_path / "leer.p3d"
    with zipfile.ZipFile(path, "w") as container:
        container.writestr("something.txt", "hello")
    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "not_a_project"


def test_a_missing_file_is_a_user_error(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as caught:
        load(tmp_path / "gibtsnicht.p3d")
    assert caught.value.constraint == "missing_file"


def test_saving_leaves_no_partial_file_behind(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    assert path.is_file()
    assert list(tmp_path.glob("*.part")) == []


def test_autosave_sits_next_to_the_project(filled: Project, tmp_path: Path) -> None:
    path = tmp_path / "projekt.p3d"
    save(filled, path)
    assert find_recovery(path) is None

    autosave = write_autosave(filled, path)
    assert autosave == autosave_path(path)
    assert autosave.parent == path.parent

    recovered = find_recovery(path)
    assert recovered is not None
    assert load(recovered).document.ops == filled.document.ops

    clear_autosave(path)
    assert find_recovery(path) is None


def test_an_autosave_older_than_the_project_is_not_offered(filled: Project, tmp_path: Path) -> None:
    path = tmp_path / "projekt.p3d"
    write_autosave(filled, path)
    save(filled, path)
    import os

    stamp = autosave_path(path).stat().st_mtime
    os.utime(path, (stamp + 10, stamp + 10))

    assert find_recovery(path) is None, "a saved project is newer than its autosave"


def test_the_checked_in_example_still_opens() -> None:
    """The regression net for the format: this file must keep opening (§16.2)."""
    project = load(EXAMPLE_FILE)

    assert project.document.format_version == FORMAT_VERSION
    assert project.document.printer == "centauri-carbon-2"
    assert [entry.op for entry in project.document.ops] == ["rename_object", "duplicate_object"]
    assert project.document.parameters["half"].expression == "=@width/2"
    assert project.document.fits[0].tolerance == "auto:petg"
    assert project.sources["src_1"] == MESH_PAYLOAD


def _rewrite_project_entry(path: Path, data: dict[str, object]) -> None:
    """Replace project.json inside an existing container."""
    with zipfile.ZipFile(path) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    entries[PROJECT_ENTRY] = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
        for name, payload in entries.items():
            container.writestr(name, payload)
