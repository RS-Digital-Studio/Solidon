"""The project container: round trip, checksums, versions, autosave (§16, §32, §38)."""

from __future__ import annotations

import io
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

import app.core.scene.project as project_module
from app.branding import PROJECT_SUFFIX
from app.core import examples
from app.core.errors import ValidationError
from app.core.paths import user_data_dir
from app.core.scene import History, OperationDraft
from app.core.scene.migrations import FORMAT_VERSION, Step, migrate
from app.core.scene.project import (
    CONTAINER_TIMESTAMP,
    PROJECT_ENTRY,
    REPORT_ENTRY,
    Project,
    ProjectSources,
    autosave_path,
    clear_autosave,
    find_recovery,
    load,
    new_project,
    project_data,
    save,
    write_autosave,
)
from app.core.scene.serialise import finding_from_data, finding_to_data
from app.core.types import (
    ChatEntry,
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
from app.i18n import SOURCE_LANGUAGE, TranslatableText, _, install_catalog, set_language
from app.i18n.catalog import read_catalog

MESH_PAYLOAD = b"solid test\nendsolid test\n"


EXAMPLE_FILE = Path(__file__).parent / "data" / "projects" / f"example_v{FORMAT_VERSION}.p3d"


@pytest.fixture
def filled() -> Project:
    return build_example_project()


def build_example_project() -> Project:
    """Ein Projekt mit allem, was das Format tragen muss.

    Zugleich die Quelle der eingecheckten Beispieldatei: jede Formatversion
    behält eine, damit sich Migrationen gegen echte Dateien testen
    lassen (§16.2).
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
    # Auch eine erzeugte Quelle, damit die eingecheckte Datei wirklich trägt,
    # was Säule B hineinschreibt (§27): den Prompt und den Startwert.
    document.sources["src_2"] = Source(
        id="src_2",
        kind="generated",
        path="sources/figur.ply",
        sha256="",
        origin=SourceOrigin(
            title="Kleine Figur",
            author="comfyui",
            prompt="eine kleine Figur",
            seed=7,
            retrieved="2026-07-27",
        ),
    )
    project.sources["src_2"] = MESH_PAYLOAD
    document.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_2", "op5.pin_1"),
            b=FeatureRef("obj_3", "op5.hole_1"),
            kind="clearance",
            tolerance="auto:petg",
        )
    )

    # Ein Objekt muss existieren, bevor sich etwas damit tun lässt; die
    # load-Operation, die es dorthin bringt, ist ein späterer P0-Schritt.
    document.ops.append(
        Operation(
            id=1, op="rename_object", inputs=(), outputs=("obj_1",), params={"name": "Halterung"}
        )
    )
    history = History(document)
    agent = Origin(by="agent", model="test", prompt_version="1", rules_version="7")
    transaction = history.apply(
        _("Duplizieren"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "=@width"})],
        origin=agent,
    )
    # Das Gespräch gehört seit Version 2 zur Datei, und ein Agentenbeitrag
    # benennt die Transaktion, die er erzeugt hat (§26.3).
    document.chat.append(ChatEntry(id="c1", role="user", text="Bitte duplizieren."))
    document.chat.append(
        ChatEntry(
            id="c2",
            role="agent",
            text="Erledigt.",
            transaction_id=transaction.id,
            origin=agent,
        )
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


def test_a_deleted_step_stays_undoable_after_loading(filled: Project, tmp_path: Path) -> None:
    """Format v17 trägt die gelöschte und die wiederherstellbare Fassung."""
    history = History(filled.document)
    history.apply(
        _("Vorübergehend umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Falsch"})],
    )
    removed_id = history.operations[-1].id
    history.remove_operations((removed_id,))

    reopened = load(save(filled, tmp_path / "projekt.p3d"))
    reopened_history = History(reopened.document)

    assert removed_id not in {entry.id for entry in reopened_history.operations}
    reopened_history.undo()
    assert removed_id in {entry.id for entry in reopened_history.operations}
    reopened_history.redo()
    assert removed_id not in {entry.id for entry in reopened_history.operations}


def test_a_second_round_trip_writes_the_same_bytes(filled: Project, tmp_path: Path) -> None:
    """Bitgleich beim Speichern und Laden — das P0-Abnahmekriterium.

    **Der Name versprach mehr, als der Test prüfte.** Er verglich die
    *Einträge* im Container, und die waren immer gleich; die **Datei** war es
    nicht, denn ein ZIP schreibt je Eintrag ein Änderungsdatum aus der Uhr.
    Aufgefallen ist es nicht hier, sondern an ``tools/make_examples.py``: Jeder
    Lauf erzeugte neun geänderte Beispieldateien, obwohl sich an keinem
    Beispiel etwas geändert hatte. Seit ``CONTAINER_TIMESTAMP`` steht dort ein
    fester Wert, und der Test kann einlösen, was er heißt.
    """
    first = save(filled, tmp_path / "a.p3d")
    reopened = load(first)
    second = save(reopened, tmp_path / "b.p3d")

    assert project_data(first) == project_data(second)
    with zipfile.ZipFile(first) as one, zipfile.ZipFile(second) as two:
        assert one.read(PROJECT_ENTRY) == two.read(PROJECT_ENTRY)
    assert first.read_bytes() == second.read_bytes(), (
        "zweimal gespeichert muss zweimal dieselbe Datei ergeben, nicht nur denselben Inhalt"
    )


def test_the_container_carries_no_clock(filled: Project, tmp_path: Path) -> None:
    """Kein Eintrag im Container trägt eine Uhrzeit.

    Geprüft wird die Ursache und nicht nur ihre Wirkung: Der Test darüber
    würde auch grün, wenn zwei Läufe zufällig in dieselbe Sekunde fielen —
    und an einer schnellen Maschine tun sie das fast immer.
    """
    written = save(filled, tmp_path / "a.p3d")

    with zipfile.ZipFile(written) as container:
        stamps = {info.date_time for info in container.infolist()}

    assert stamps == {CONTAINER_TIMESTAMP}, f"aus der Uhr statt fest: {sorted(stamps)}"


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


def test_an_image_source_survives_the_round_trip(filled: Project, tmp_path: Path) -> None:
    """§25: Das Relief-Bild ist eine Quelle ohne load-Operation — Art und
    Nutzlast überleben die runde Reise, sonst öffnet das Projekt mit einem
    Feld „Bild", das auf nichts mehr zeigt."""
    payload = b"\x89PNG\r\n\x1a\nbild"
    filled.document.sources["src_9"] = Source(
        id="src_9", kind="image", path="sources/relief.png", sha256=""
    )
    filled.sources["src_9"] = payload

    reopened = load(save(filled, tmp_path / "projekt.p3d"))

    assert reopened.document.sources["src_9"].kind == "image"
    assert reopened.sources["src_9"] == payload


def test_the_licence_of_a_source_survives(filled: Project, tmp_path: Path) -> None:
    reopened = load(save(filled, tmp_path / "projekt.p3d"))
    origin = reopened.document.sources["src_1"].origin
    assert origin is not None
    assert origin.licence == "CC BY-NC 4.0"
    assert reopened.document.sources["src_1"].ingest.removed_triangles == 4


@pytest.mark.parametrize("declared", ["", "0" * 64])
def test_checksums_are_written_and_verified(
    filled: Project,
    tmp_path: Path,
    declared: str,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    assert filled.document.sources["src_1"].sha256

    data = project_data(path)
    data["sources"]["src_1"]["sha256"] = declared
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_a_linked_source_gets_a_checksum_when_saved(tmp_path: Path) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(MESH_PAYLOAD)
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256="",
        embedded=False,
    )

    path = save(project, tmp_path / "projekt.p3d")

    expected = project_module.checksum(MESH_PAYLOAD)
    assert project.document.sources["src_1"].sha256 == expected
    assert load(path).document.sources["src_1"].sha256 == expected


@pytest.mark.parametrize("method", ["read", "identity"])
def test_a_changed_linked_source_is_refused(
    tmp_path: Path,
    method: str,
) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(MESH_PAYLOAD)
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256="",
        embedded=False,
    )
    reopened = load(save(project, tmp_path / "projekt.p3d"))
    linked.write_bytes(b"ausgetauschter Inhalt")

    access = ProjectSources(reopened, base_dir=tmp_path)
    with pytest.raises(ValidationError) as caught:
        getattr(access, method)("src_1")

    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_a_linked_source_is_bounded_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(b"123")
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256=project_module.checksum(b"123"),
        embedded=False,
    )
    monkeypatch.setattr(project_module, "MAX_FILE_BYTES", 2)

    with pytest.raises(ValidationError) as caught:
        ProjectSources(project, base_dir=tmp_path).read("src_1")

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_a_linked_source_without_a_stored_checksum_is_refused(tmp_path: Path) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(MESH_PAYLOAD)
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256="",
        embedded=False,
    )

    with pytest.raises(ValidationError) as caught:
        ProjectSources(project, base_dir=tmp_path).read("src_1")

    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_loading_eagerly_verifies_a_linked_source_checksum(tmp_path: Path) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(MESH_PAYLOAD)
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256="",
        embedded=False,
    )
    path = save(project, tmp_path / "projekt.p3d")
    linked.write_bytes(b"ausgetauscht")

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_loading_bounds_all_linked_sources_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = new_project()
    for index in range(2):
        linked = tmp_path / f"linked-{index}.stl"
        linked.write_bytes(b"123")
        project.document.sources[f"src_{index}"] = Source(
            id=f"src_{index}",
            kind="import",
            path=linked.name,
            sha256="",
            embedded=False,
        )
    path = save(project, tmp_path / "projekt.p3d")
    monkeypatch.setattr(project_module, "MAX_LINKED_SOURCE_BYTES", 5)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_a_linked_source_must_not_escape_through_a_symbolic_link(tmp_path: Path) -> None:
    project_dir = tmp_path / "projekt"
    project_dir.mkdir()
    outside = tmp_path / "ausserhalb.stl"
    outside.write_bytes(MESH_PAYLOAD)
    link = project_dir / "verknuepft.stl"
    try:
        link.symlink_to(outside)
    except OSError as problem:
        pytest.skip(f"Symbolische Verknüpfungen sind nicht verfügbar: {problem}")

    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=link.name,
        sha256=project_module.checksum(MESH_PAYLOAD),
        embedded=False,
    )

    with pytest.raises(ValidationError) as caught:
        ProjectSources(project, base_dir=project_dir).read("src_1")

    assert caught.value.constraint == "absolute_path"
    assert caught.value.suggestions


def test_a_linked_source_must_not_escape_through_a_linked_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "projekt"
    project_dir.mkdir()
    outside = tmp_path / "ausserhalb"
    outside.mkdir()
    (outside / "modell.stl").write_bytes(MESH_PAYLOAD)
    link = project_dir / "verknuepft"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as problem:
        pytest.skip(f"Verzeichnisverknüpfungen sind nicht verfügbar: {problem}")

    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path="verknuepft/modell.stl",
        sha256=project_module.checksum(MESH_PAYLOAD),
        embedded=False,
    )

    with pytest.raises(ValidationError) as caught:
        ProjectSources(project, base_dir=project_dir).read("src_1")

    assert caught.value.constraint == "absolute_path"
    assert caught.value.suggestions


def test_a_stale_linked_checksum_stops_saving(tmp_path: Path) -> None:
    linked = tmp_path / "linked.stl"
    linked.write_bytes(MESH_PAYLOAD)
    project = new_project()
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=linked.name,
        sha256="0" * 64,
        embedded=False,
    )

    with pytest.raises(ValidationError) as caught:
        save(project, tmp_path / "projekt.p3d")

    assert caught.value.constraint == "checksum"
    assert caught.value.suggestions


def test_the_outer_project_size_is_checked_before_zip_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "zu-gross.p3d"
    path.write_bytes(b"kein ZIP")
    monkeypatch.setattr(project_module, "MAX_PROJECT_FILE_BYTES", path.stat().st_size - 1)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_too_many_archive_entries_are_refused_before_reading(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    with zipfile.ZipFile(path) as container:
        count = len(container.infolist())
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_ENTRIES", count - 1)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_duplicate_archive_entries_are_refused(
    filled: Project,
    tmp_path: Path,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    with zipfile.ZipFile(path) as container:
        project_payload = container.read(PROJECT_ENTRY)
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as container,
    ):
        container.writestr(PROJECT_ENTRY, project_payload)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "exists"
    assert caught.value.values["entry"] == PROJECT_ENTRY
    assert caught.value.suggestions


@pytest.mark.parametrize(
    ("entry", "limit_name", "payload"),
    [
        (PROJECT_ENTRY, "MAX_PROJECT_JSON_BYTES", None),
        ("sources/halterung.stl", "MAX_ARCHIVE_ENTRY_BYTES", None),
        ("sources/gathered/attack.json", "MAX_GATHERED_BYTES", b"{}"),
        ("recipes/attack.json", "MAX_RECIPE_BYTES", b"{}"),
        ("report.json", "MAX_REPORT_BYTES", None),
        ("thumb.png", "MAX_THUMBNAIL_BYTES", None),
    ],
)
def test_every_project_payload_has_its_own_limit(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    limit_name: str,
    payload: bytes | None,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    if payload is not None:
        _append_archive_entry(path, entry, payload)
    with zipfile.ZipFile(path) as container:
        size = container.getinfo(entry).file_size
    monkeypatch.setattr(project_module, limit_name, size - 1)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.values["entry"] == entry
    assert caught.value.suggestions


def test_the_total_unpacked_project_size_is_bounded(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    with zipfile.ZipFile(path) as container:
        unpacked = sum(info.file_size for info in container.infolist())
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_UNPACKED_BYTES", unpacked - 1)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.values["limit"] == unpacked - 1
    assert caught.value.suggestions


def test_an_extreme_compression_ratio_is_refused(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    payload = b"0" * 100_000
    _append_archive_entry(path, "bomb.bin", payload)
    monkeypatch.setattr(project_module, "MIN_RATIO_ENTRY_BYTES", 10_000)
    monkeypatch.setattr(project_module, "MAX_COMPRESSION_RATIO", 2.0)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.values["entry"] == "bomb.bin"
    assert caught.value.suggestions


def test_the_total_compression_ratio_cannot_be_evaded_with_small_entries(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    for index in range(3):
        _append_archive_entry(path, f"small-{index}.bin", b"0" * 5_000)
    monkeypatch.setattr(project_module, "MIN_RATIO_ENTRY_BYTES", 10_000)
    monkeypatch.setattr(project_module, "MAX_COMPRESSION_RATIO", 2.0)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert "entry" not in caught.value.values
    assert caught.value.suggestions


def test_an_entry_at_the_compression_ratio_limit_is_accepted(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    payload = b"0" * 100_000
    _append_archive_entry(path, "dense.bin", payload)
    with zipfile.ZipFile(path) as container:
        info = container.getinfo("dense.bin")
        ratio = info.file_size / info.compress_size
    monkeypatch.setattr(project_module, "MIN_RATIO_ENTRY_BYTES", info.file_size)
    monkeypatch.setattr(project_module, "MAX_COMPRESSION_RATIO", ratio)

    assert load(path).document == filled.document


def test_the_bounded_reader_does_not_trust_the_declared_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LyingContainer:
        def open(self, info: zipfile.ZipInfo, mode: str) -> io.BytesIO:
            assert mode == "r"
            return io.BytesIO(b"123")

    info = zipfile.ZipInfo("payload.bin")
    info.file_size = 1
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_ENTRY_BYTES", 2)

    with pytest.raises(ValidationError) as caught:
        project_module._read_archive_entry(LyingContainer(), info)  # type: ignore[arg-type]

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_a_lone_surrogate_in_a_project_value_is_refused(
    filled: Project,
    tmp_path: Path,
) -> None:
    path = save(filled, tmp_path / "surrogat-wert.p3d")
    data = project_data(path)
    data["app_version"] = "ungültig-\ud800"
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert "unicode_scalar" in str(caught.value.values.get("reason", ""))
    assert caught.value.suggestions


def test_a_lone_surrogate_in_a_report_key_is_refused(
    filled: Project,
    tmp_path: Path,
) -> None:
    path = save(filled, tmp_path / "surrogat-schlüssel.p3d")
    with zipfile.ZipFile(path) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    report_data = json.loads(entries[REPORT_ENTRY])
    report_data["\udfff"] = "ungültig"
    entries[REPORT_ENTRY] = json.dumps(report_data).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
        for name, payload in entries.items():
            container.writestr(name, payload)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert "unicode_scalar" in str(caught.value.values.get("reason", ""))
    assert caught.value.suggestions


def test_a_valid_non_bmp_character_in_a_project_is_accepted(
    filled: Project,
    tmp_path: Path,
) -> None:
    path = save(filled, tmp_path / "nicht-bmp.p3d")
    data = project_data(path)
    data["app_version"] = "Version-\U00020000"
    _rewrite_project_entry(path, data)

    reopened = load(path)

    assert reopened.document.app_version == "Version-\U00020000"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_project_numbers_are_refused(
    filled: Project,
    tmp_path: Path,
    value: float,
) -> None:
    path = save(filled, tmp_path / "nicht-endlich.p3d")
    data = project_data(path)
    data["parameters"]["width"]["value"] = value
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert caught.value.suggestions


def test_excessive_json_depth_is_refused(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "zu-tief.p3d")
    data = project_data(path)
    nested: list[object] = []
    data["unknown"] = nested
    for _index in range(project_module.MAX_JSON_DEPTH + 1):
        child: list[object] = []
        nested.append(child)
        nested = child
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert caught.value.suggestions


def test_project_object_limit_accepts_the_boundary_and_refuses_one_more(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "objekte.p3d")
    data = project_data(path)
    monkeypatch.setattr(project_module, "MAX_PROJECT_OBJECTS", 2)
    data["ops"] = [
        {"id": index, "op": "rename_object", "in": [], "out": [f"obj_{index}"], "params": {}}
        for index in range(1, 3)
    ]
    data["transactions"] = []
    _rewrite_project_entry(path, data)

    assert len(load(path).document.ops) == 2

    data["ops"].append({"id": 3, "op": "rename_object", "in": [], "out": ["obj_3"], "params": {}})
    _rewrite_project_entry(path, data)
    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("scene", []),
        ("parameters", []),
        ("sources", []),
        ("fits", {}),
        ("transactions", {}),
        ("ops", {}),
        ("chat", {}),
        ("numbering", []),
    ],
)
def test_project_schema_collection_types_are_enforced(
    filled: Project,
    tmp_path: Path,
    field: str,
    invalid: object,
) -> None:
    path = save(filled, tmp_path / f"schema-{field}.p3d")
    data = project_data(path)
    data[field] = invalid
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert caught.value.suggestions


def test_operation_schema_rejects_a_non_string_object_id(
    filled: Project,
    tmp_path: Path,
) -> None:
    path = save(filled, tmp_path / "schema-op.p3d")
    data = project_data(path)
    data["ops"][0]["out"] = [7]
    _rewrite_project_entry(path, data)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert caught.value.suggestions


def test_report_schema_requires_a_finding_list(filled: Project, tmp_path: Path) -> None:
    path = save(filled, tmp_path / "schema-report.p3d")
    with zipfile.ZipFile(path) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    entries[REPORT_ENTRY] = b'{"findings": {}}'
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
        for name, payload in entries.items():
            container.writestr(name, payload)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert caught.value.suggestions


def test_exact_archive_limits_still_open(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = save(filled, tmp_path / "projekt.p3d")
    with zipfile.ZipFile(path) as container:
        infos = container.infolist()
        by_name = {info.filename: info for info in infos}
        source_size = max(
            by_name[source.path].file_size
            for source in filled.document.sources.values()
            if source.embedded
        )
    monkeypatch.setattr(project_module, "MAX_PROJECT_FILE_BYTES", path.stat().st_size)
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_ENTRIES", len(infos))
    monkeypatch.setattr(
        project_module,
        "MAX_ARCHIVE_UNPACKED_BYTES",
        sum(info.file_size for info in infos),
    )
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_ENTRY_BYTES", source_size)
    monkeypatch.setattr(
        project_module,
        "MAX_PROJECT_JSON_BYTES",
        by_name[PROJECT_ENTRY].file_size,
    )
    monkeypatch.setattr(project_module, "MAX_REPORT_BYTES", by_name["report.json"].file_size)
    monkeypatch.setattr(project_module, "MAX_THUMBNAIL_BYTES", by_name["thumb.png"].file_size)

    assert load(path).document == filled.document


def test_saving_refuses_an_oversized_embedded_source(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_module, "MAX_ARCHIVE_ENTRY_BYTES", len(MESH_PAYLOAD) - 1)

    with pytest.raises(ValidationError) as caught:
        save(filled, tmp_path / "projekt.p3d")

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def test_saving_refuses_an_oversized_container_without_leaving_a_partial_file(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_module, "MAX_PROJECT_FILE_BYTES", 1)

    with pytest.raises(ValidationError) as caught:
        save(filled, tmp_path / "projekt.p3d")

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions
    assert not list(tmp_path.glob("*.part"))


def test_saving_never_uses_the_predictable_part_path(filled: Project, tmp_path: Path) -> None:
    predictable = tmp_path / "projekt.p3d.part"
    predictable.write_bytes(b"fremder Inhalt")

    save(filled, tmp_path / "projekt.p3d")

    assert predictable.read_bytes() == b"fremder Inhalt"


def test_saving_does_not_follow_a_predictable_part_symlink(
    filled: Project,
    tmp_path: Path,
) -> None:
    victim = tmp_path / "nicht-ueberschreiben"
    victim.write_bytes(b"wichtig")
    predictable = tmp_path / "projekt.p3d.part"
    try:
        predictable.symlink_to(victim)
    except OSError as problem:
        pytest.skip(f"Symbolische Verknüpfungen sind nicht verfügbar: {problem}")

    save(filled, tmp_path / "projekt.p3d")

    assert victim.read_bytes() == b"wichtig"
    assert predictable.is_symlink()


@pytest.mark.parametrize(
    "path",
    [
        # Beide Konventionen, denn die Datei reist: „C:/…" ist auf POSIX nur
        # ein Ordnername, ein Laufwerk ohne Schrägstrich und ein UNC-Pfad
        # sind trotzdem absolut.
        "C:/somewhere/halterung.stl",
        "C:halterung.stl",
        "//server/share/halterung.stl",
        "/somewhere/halterung.stl",
    ],
)
def test_absolute_paths_are_refused(tmp_path: Path, path: str) -> None:
    project = new_project()
    project.document.sources["src_1"] = Source(id="src_1", kind="import", path=path, sha256="")
    project.sources["src_1"] = MESH_PAYLOAD

    with pytest.raises(ValidationError) as caught:
        save(project, tmp_path / "projekt.p3d")
    assert caught.value.constraint == "absolute_path"


@pytest.mark.parametrize("path", ["../outside.stl", "..\\outside.stl"])
def test_paths_leaving_the_container_are_refused(tmp_path: Path, path: str) -> None:
    project = new_project()
    project.document.sources["src_1"] = Source(id="src_1", kind="import", path=path, sha256="")
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


def test_v14_moves_to_the_filament_metadata_format_without_guessing() -> None:
    """14 → 15 schützt neue Filamentfelder, ändert alte Schritte aber nicht.

    Vor Version 15 kannten ``assign_slot`` und ``paint_slot`` weder Typ noch
    Slicer-Profil. Beides leer nachzutragen wäre zwar möglich, aber unnötig:
    die Schema-Vorgaben sagen bereits genau das. Die Migration muss deshalb
    nur die Formatgrenze ziehen und alle Kundenwerte wörtlich bewahren.
    """
    old = {
        "format_version": 14,
        "ops": [
            {
                "id": 1,
                "op": "assign_slot",
                "in": ["obj_1"],
                "out": ["obj_2"],
                "params": {"slot": 1, "name": "PLA Weiß", "colour": "#ffffff"},
            }
        ],
    }

    migrated = migrate(old, target=15)

    assert migrated["format_version"] == 15
    assert migrated["ops"] == old["ops"], "optionale Felder werden nicht erfunden"


def test_v15_moves_to_actionable_findings_without_inventing_data() -> None:
    """15 → 16 markiert das neue Befundfeld; die alten Daten bleiben wörtlich.

    Die Befunde liegen in einem eigenen Container-Eintrag und entstehen beim
    Rechnen neu. Eine Migration von ``project.json`` darf deshalb keine
    Handlungen raten oder bestehende Schritte anfassen.
    """
    old = {
        "format_version": 15,
        "ops": [{"id": 1, "op": "load", "params": {"source": "src_1"}}],
    }

    migrated = migrate(old, target=16)

    assert migrated["format_version"] == 16
    assert migrated["ops"] == old["ops"]


def test_a_damaged_container_is_reported_not_raised_raw(tmp_path: Path) -> None:
    path = tmp_path / "kaputt.p3d"
    path.write_bytes(b"this is not a zip file")
    with pytest.raises(ValidationError) as caught:
        load(path)
    assert caught.value.constraint == "damaged"


@pytest.mark.skipif(os.name != "posix", reason="Umask und Dateirechte gibt es nur auf POSIX")
def test_a_saved_project_gets_the_permissions_of_a_normal_file(
    filled: Project,
    tmp_path: Path,
) -> None:
    """Ein gespeichertes Projekt trägt die Rechte, die die Umask vorgibt.

    Geschrieben wird über ``mkstemp``, und das legt mit 0600 an — beim
    Umbenennen reisen diese Rechte mit. Auf Linux und macOS gehörte die
    ``.p3d`` danach allein dem Nutzer: keine Gruppe, kein zweites Konto, auch
    wo die Umask des Systems etwas anderes sagt.
    """
    mask = os.umask(0o022)
    try:
        path = save(filled, tmp_path / "rechte.p3d")
    finally:
        os.umask(mask)

    assert stat.S_IMODE(path.stat().st_mode) == 0o644, (
        f"gespeichert mit {stat.S_IMODE(path.stat().st_mode):04o} statt 0644 — "
        "die Rechte des Zwischenstands sind mitgereist"
    )


def test_a_programming_error_while_reading_is_not_a_damaged_file(
    filled: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein falscher Aufruf im Leser sieht aus wie eine kaputte Datei — und ist keiner.

    ``load`` fing ``TypeError`` und ``AttributeError`` mit ein und meldete
    „Der Projektinhalt ist beschädigt". Damit las der Kunde, seine Datei sei
    hin, während in Wahrheit unser Code falsch aufgerufen wurde — kein
    Fehlerbericht, keine Spur, und die Datei öffnet auf keinem Rechner
    (``errors.PROGRAMMING_ERRORS``).
    """
    path = save(filled, tmp_path / "programmfehler.p3d")

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("document_from_data() got an unexpected keyword argument")

    monkeypatch.setattr(project_module, "document_from_data", wrong)

    with pytest.raises(TypeError):
        load(path)


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


def test_a_locked_autosave_does_not_stop_the_window_from_closing(
    filled: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Sicherung, die sich nicht löschen lässt, ist kein Grund zum Werfen.

    ``clear_autosave`` läuft seit „Verworfen heißt verworfen" auch aus dem
    ``closeEvent`` — und auf Windows hält ein Virenscanner eine gerade
    geschriebene Datei gern noch einen Moment fest. Ein ``PermissionError`` von
    dort wäre ein Fenster, das sich nicht schließen lässt, wegen einer Datei,
    die niemanden mehr interessiert.
    """
    path = tmp_path / "projekt.p3d"
    save(filled, path)
    write_autosave(filled, path)

    def refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError(32, "Der Prozess kann nicht auf die Datei zugreifen")

    monkeypatch.setattr(Path, "unlink", refuse)

    clear_autosave(path)  # wirft nicht

    # Und die Sicherung liegt noch da — das ist der Preis, und er ist der
    # kleinere: eine überflüssige Frage beim nächsten Öffnen.
    assert autosave_path(path).is_file()


def test_an_autosave_older_than_the_project_is_not_offered(filled: Project, tmp_path: Path) -> None:
    path = tmp_path / "projekt.p3d"
    write_autosave(filled, path)
    save(filled, path)
    import os

    stamp = autosave_path(path).stat().st_mtime
    os.utime(path, (stamp + 10, stamp + 10))

    assert find_recovery(path) is None, "a saved project is newer than its autosave"


def test_an_autosave_at_the_same_second_is_still_offered(filled: Project, tmp_path: Path) -> None:
    """Gleichstand ist keine Auskunft — und wird zur sicheren Seite entschieden.

    So gefunden: ``test_autosave_sits_next_to_the_project`` schlug in einem
    vollen Lauf fehl und ließ sich außerhalb von pytest nachstellen. Beide
    Dateien trugen dieselbe Zeit, auf die letzte Stelle genau — die Dateizeit
    löst hier rund 16 Millisekunden auf, und Speichern plus Sichern dauert
    weniger. Der Test hing damit an der Rechnerlast; die Anwendung hätte im
    selben Fall die Wiederherstellung verschwiegen.

    Hier stehen die Zeiten deshalb fest, statt gemessen zu werden: Ein Test,
    der eine Zeitauflösung prüft, prüft die Maschine und nicht die Anwendung.
    """
    import os

    path = tmp_path / "projekt.p3d"
    save(filled, path)
    autosave = write_autosave(filled, path)
    stamp = path.stat().st_mtime
    os.utime(autosave, (stamp, stamp))

    assert find_recovery(path) == autosave, "gleiche Zeit heißt nicht älter"


def test_the_checked_in_example_still_opens() -> None:
    """Das Regressionsnetz des Formats: diese Datei muss sich weiter öffnen
    lassen (§16.2).
    """
    project = load(EXAMPLE_FILE)

    assert project.document.format_version == FORMAT_VERSION
    assert project.document.printer == "centauri-carbon-2"
    assert [entry.op for entry in project.document.ops] == ["rename_object", "duplicate_object"]
    assert project.document.parameters["half"].expression == "=@width/2"
    assert project.document.fits[0].tolerance == "auto:petg"
    assert project.sources["src_1"] == MESH_PAYLOAD
    assert [entry.role for entry in project.document.chat] == ["user", "agent"]
    assert project.document.chat[1].transaction_id, "§26.3: a turn names what it changed"
    assert isinstance(project.document.transactions[0].title, TranslatableText), (
        "ein Titel aus dem Code reist seit Version 6 als Message-ID"
    )

    generated = project.document.sources["src_2"].origin
    assert generated is not None
    assert (generated.prompt, generated.seed) == ("eine kleine Figur", 7)


def test_every_older_example_migrates_to_today() -> None:
    """§16.2 behält ein Beispiel je Version, und jedes davon muss hier
    ankommen.
    """
    examples = sorted((Path(__file__).parent / "data" / "projects").glob("example_v*.p3d"))

    assert len(examples) >= FORMAT_VERSION, "one checked-in file per format version"
    for path in examples:
        project = load(path)
        assert project.document.format_version == FORMAT_VERSION, path.name
        assert [entry.op for entry in project.document.ops] == [
            "rename_object",
            "duplicate_object",
        ], path.name


def test_a_point_stroke_from_before_the_filament_rebuild_still_opens() -> None:
    """13 → 14: ``paint_slot`` malt nicht mehr um einen Punkt, die Datei bleibt.

    Dieselbe Zusage wie beim Schritt darunter, aus demselben Grund: Ein alter
    Bemal-Schritt trägt einen Klickpunkt und einen Radius, und daraus lässt
    sich das gemeinte Merkmal nicht zurückrechnen — die Erkennung von heute
    kann an derselben Stelle eine andere Fläche finden als die von damals.
    Geraten wäre schlimmer als angehalten: Eine Farbe, die nach dem Update auf
    der falschen Fläche sitzt, sieht der Kunde erst im Slicer.

    Die Datei ist am 26.08.2026 mit dem alten Pfad erzeugt worden, kurz bevor
    er entfiel — danach kann kein Code sie mehr bauen.
    """
    from app.core.knowledge import profiles
    from app.core.scene.evaluate import evaluate

    project = load(Path(__file__).parent / "data" / "projects" / "painted_v13.p3d")

    assert project.document.format_version == FORMAT_VERSION
    steps = [entry.op for entry in project.document.ops]
    assert steps == ["load", "paint_slot"], "der Schritt bleibt stehen"
    assert project.document.ops[1].params["radius"] == 12.0, (
        "und seine Werte mit ihm — sie sind die Arbeit des Kunden"
    )

    result = evaluate(project.document, profiles.make_profile("centauri-carbon-2", "petg"))

    codes = {finding.code for finding in result.scene.report.findings}
    assert codes, "eine Datei, die nicht rechnen kann, sagt es"
    assert not any(code.startswith("internal") for code in codes), (
        "ein Zustand, mit dem zu rechnen war, ist kein Programmfehler"
    )


def test_a_file_with_a_step_this_version_cannot_run_still_opens() -> None:
    """12 → 13: ``create_from_scad`` gibt es nicht mehr, die Datei schon.

    **Geprüft wird, dass sie ehrlich degradiert — nicht, dass sie rechnet.**
    Die Checkliste in ``AGENTS.md`` verlangt „alte Datei öffnet und rechnet
    korrekt"; hier kann sie es nicht, und die Zusage ist deshalb eine andere:
    Der Schritt bleibt stehen, sein Quelltext auch, und wer die Datei
    auswertet, bekommt einen Satz statt eines Programmfehlers.

    Vor dem 26.08.2026 kam an dieser Stelle ``InternalError: Im Programm ist
    ein unerwarteter Fehler aufgetreten`` — mitsamt dem Knopf für den
    Fehlerbericht, für eine Datei, die der Kunde selbst angelegt hatte.
    """
    from app.core.knowledge import profiles
    from app.core.scene.evaluate import evaluate

    project = load(Path(__file__).parent / "data" / "projects" / "scad_v12.p3d")

    assert project.document.format_version == FORMAT_VERSION
    steps = [entry.op for entry in project.document.ops]
    assert steps == ["create_box", "create_from_scad"], "der Schritt bleibt stehen"
    assert "cylinder" in str(project.document.ops[1].params["source"]), (
        "und sein Quelltext mit ihm — er ist Arbeit des Kunden"
    )

    result = evaluate(project.document, profiles.make_profile("centauri-carbon-2", "petg"))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "evaluate.unknown_operation" in codes
    finding = next(
        entry
        for entry in result.scene.report.findings
        if entry.code == "evaluate.unknown_operation"
    )
    assert finding.op_id == 2, "der Befund nennt den Schritt, nicht bloß die Datei"
    assert finding.values["operation"] == "create_from_scad"
    assert "unerwarteter Fehler" not in str(finding.message), (
        "ein Zustand, mit dem zu rechnen war, ist kein Programmfehler"
    )

    # Regel 17: nie nur ein Befund, immer ein Weg. Der Satz sagte bis zum
    # 26.08.2026 „alles andere im Projekt rechnet weiter" — zwei Zeilen unter
    # dem ``break``, das die Auswertung beendet. Wer das las, suchte den Fehler
    # bei sich und hatte keine Handhabe.
    satz = str(finding.message)
    assert "Verlauf" in satz, "der Befund nennt, wo die Werte zu sehen sind"
    assert "verwirft" in satz, "und wie der Schritt loszuwerden ist"
    assert "rechnet weiter" not in satz, (
        "ab hier rechnet nichts mehr — der Satz sagte das Gegenteil"
    )

    # Und der genannte Weg muss auch bedienbar sein: Rückgängig hängt an den
    # Transaktionen des **Dokuments**, nicht an denen dieser Sitzung. Sonst
    # wäre der Vorschlag ein Verweis auf etwas, das es nach dem Öffnen einer
    # Datei gar nicht gibt.
    from app.core.scene.history import History

    assert History(project.document).can_undo, "der vorgeschlagene Weg steht nach dem Öffnen offen"


def test_a_title_from_an_older_file_stays_literal(tmp_path: Path) -> None:
    """5 → 6: was eine ältere Datei als Titel trägt, bleibt wörtlich.

    Ob der Text damals aus dem Code kam oder vom Nutzer getippt wurde, steht
    nirgends — also wird er nicht zur Message-ID erklärt und nie übersetzt.
    Auch ein erneutes Speichern im neuen Format ändert daran nichts.
    """
    project = load(Path(__file__).parent / "data" / "projects" / "example_v5.p3d")

    title = project.document.transactions[0].title
    assert isinstance(title, str)
    assert title == "Duplizieren"

    reopened = load(save(project, tmp_path / "wieder.p3d"))
    assert isinstance(reopened.document.transactions[0].title, str)


def test_a_translatable_title_survives_the_round_trip(filled: Project, tmp_path: Path) -> None:
    """Ein Titel aus dem Code reist als Message-ID und löst sich erst bei der
    Anzeige auf — auch nach Speichern und Öffnen (§4.1)."""
    reopened = load(save(filled, tmp_path / "projekt.p3d"))

    title = reopened.document.transactions[0].title
    assert isinstance(title, TranslatableText)
    assert title.msgid == "Duplizieren"


def test_a_file_from_before_the_agent_gets_an_empty_conversation() -> None:
    """1 → 2: kein Chat ist keine kaputte Datei, sondern eine aus der Zeit vor
    dem Chat.
    """
    project = load(Path(__file__).parent / "data" / "projects" / "example_v1.p3d")

    assert project.document.chat == []


def test_a_bore_from_an_older_file_stays_where_it_was() -> None:
    """6 → 7: die Position einer Bohrung ist seither ihre Mündung (§25).

    Die eingecheckte Datei bohrt drei Millimeter tief auf die Oberseite einer
    Platte. Bis Version 6 lag die *Mitte* der Bohrung dort, sie ging also nur
    anderthalb Millimeter ins Material und der Rest stand in der Luft. Genau
    das muss sie weiter tun: eine alte Datei rechnet, wie sie gerechnet hat.

    Gemessen wird das Volumen, nicht der Parameter — dass ``anchor`` gesetzt
    ist, sagt noch nicht, dass es wirkt.
    """
    from app.core.knowledge import profiles
    from app.core.scene import evaluate

    project = load(Path(__file__).parent / "data" / "projects" / "drilled_v6.p3d")

    assert project.document.format_version == FORMAT_VERSION
    assert project.document.ops[-1].params["anchor"] == "centre"

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(31276.892, abs=0.01)


def test_a_file_that_split_at_a_plane_still_splits_the_same() -> None:
    """10 → 11: *An Ebene teilen* ist in *Teilen* aufgegangen (§25).

    Die eingecheckte Datei schneidet einen 20er-Würfel bei z = 2 — vier
    Fünftel unten, ein Fünftel oben. Sie tut es mit ``split_plane``, der
    Operation, die es nicht mehr gibt.

    **Gemessen werden die Hälften, nicht der Operationsname.** Dass in der
    Datei jetzt ``split_pinned`` steht, sagt noch nicht, dass dasselbe
    herauskommt: Das Feld *Passstifte* hat als Vorgabe zwei Stifte, und wer
    die Null in der Migration vergäße, bekäme aus einem alten Projekt ein
    verstiftetes Teil — zwei Bohrungen und zwei Zapfen, die dort nie waren.
    Deshalb steht hier ein Volumen und keine Zeichenkette.
    """
    from app.core.knowledge import profiles
    from app.core.scene import evaluate

    project = load(Path(__file__).parent / "data" / "projects" / "split_v10.p3d")

    assert project.document.format_version == FORMAT_VERSION
    assert [entry.op for entry in project.document.ops] == ["load", "split_pinned"]
    assert project.document.ops[-1].params["pins"] == 0

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, "eine migrierte Datei muss durchrechnen, nicht nur öffnen"
    volumes = sorted(entry.mesh.volume for entry in result.scene.objects.values())
    assert volumes == [pytest.approx(3200.0, rel=1e-6), pytest.approx(4800.0, rel=1e-6)]
    for entry in result.scene.objects.values():
        assert entry.mesh.is_watertight
    # Keine Stifte heißt: keine Stiftmerkmale. Der Beleg dafür, dass die Null
    # angekommen ist — Volumen allein fängt einen Zapfen samt Gegenbohrung
    # nicht, die beiden heben sich fast auf.
    for entry in result.scene.objects.values():
        assert not [name for name in entry.features if "pin" in name or "bore" in name]


def test_a_file_from_before_the_print_settings_has_none() -> None:
    """3 → 4: keine eigenen Druckeinstellungen heißt nicht „alles auf null",
    sondern „noch nichts entschieden" — es gilt weiter, was sich aus Stufe,
    Material und Drucker ergibt (§29).
    """
    project = load(Path(__file__).parent / "data" / "projects" / "example_v3.p3d")

    assert project.document.print_settings is None


def test_print_settings_survive_the_round_trip(tmp_path: Path) -> None:
    """Was eingestellt wurde, muss beim nächsten Öffnen noch da sein — sonst
    ist der Dialog eine Sitzung lang gültig und danach vergessen."""
    project = load(Path(__file__).parent / "data" / "projects" / "example_v4.p3d")
    settings = project.document.print_settings
    assert settings is not None

    reopened = load(save(project, tmp_path / "wieder.p3d"))

    assert reopened.document.print_settings == settings


def test_a_file_from_before_pillar_b_has_no_generated_sources() -> None:
    """2 → 3: damals wurde nichts erzeugt, also trägt nichts einen Prompt."""
    project = load(Path(__file__).parent / "data" / "projects" / "example_v2.p3d")

    assert all(entry.kind != "generated" for entry in project.document.sources.values())
    assert all(
        entry.origin is None or entry.origin.prompt is None
        for entry in project.document.sources.values()
    )


def _rewrite_project_entry(path: Path, data: dict[str, object]) -> None:
    """Replace project.json inside an existing container."""
    with zipfile.ZipFile(path) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    entries[PROJECT_ENTRY] = json.dumps(data, indent=2).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
        for name, payload in entries.items():
            container.writestr(name, payload)


def _append_archive_entry(path: Path, name: str, payload: bytes) -> None:
    """Fügt einem Testcontainer eine komprimierte Beilage hinzu."""
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(name, payload)


def test_an_example_never_gets_an_autosave_beside_it() -> None:
    """Die Installation ist kein Ablageort (§37.2, §38).

    Zwei Sicherungen neben zwei Beispielen haben genau das angerichtet, wovor
    diese Regel schützt: der Tour-Test blieb in einem Wiederherstellungsdialog
    stehen, und ein hängender Test sagt nicht, warum er hängt. Unter
    „Programme" wäre das Schreiben ohnehin verboten gewesen.

    Der Name bleibt eindeutig — er trägt den des Beispiels —, damit zwei
    offene Beispiele nicht dieselbe Sicherung überschreiben.
    """
    example = examples.directory() / f"weg1-halterung-anpassen{PROJECT_SUFFIX}"
    target = autosave_path(example)
    assert target.parent != example.parent
    assert target.parent == user_data_dir() / "recovery"
    assert example.name in target.name

    ordinary = Path("irgendwo") / f"projekt{PROJECT_SUFFIX}"
    assert autosave_path(ordinary).parent == ordinary.parent


# --- Befunde über die Sprachgrenze ------------------------------------------------


def test_a_finding_keeps_its_message_id_instead_of_its_translation() -> None:
    """Ein Befund aus dem Cache trug die Sprache, in der er entstanden ist.

    Hier stand ``str(finding.message)``, und das löst sofort auf. Gemeldet von
    Robert am 23.08.2026 an zwei Sätzen, die er in **jeder** Sprache deutsch
    las: „Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters." und
    „Deckel erzeugt — das Spiel kommt aus dem Materialprofil."

    **Warum ausgerechnet die zwei:** Aushöhlen und Deckelerzeugen sind teuer,
    ihre Ergebnisse liegen im Plattencache, und die mitgelieferten Beispiele
    sind auf Deutsch erzeugt worden.
    """
    finding = Finding(
        code="hollow.done",
        severity="info",
        message=TranslatableText("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."),
    )

    # **Abgelegt wird in einer anderen Sprache als der Quellsprache**, und genau
    # daran hängt dieser Test: Auf Deutsch sind Message-ID und Übersetzung
    # dieselbe Zeichenkette, also unterscheidet dort kein Vergleich zwischen
    # „ID abgelegt" und „aufgelöst abgelegt". Die erste Fassung dieses Tests tat
    # es nicht und blieb in der Gegenprobe grün — sie prüfte nichts.
    install_catalog("en", read_catalog("en"))
    set_language("en")
    try:
        written = finding_to_data(finding)
    finally:
        set_language(SOURCE_LANGUAGE)

    assert written["message"] == "Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters.", (
        f"abgelegt wird die Message-ID, nicht die Übersetzung: {written['message']!r}"
    )
    assert isinstance(finding_from_data(written).message, TranslatableText), (
        "sonst ist der Satz in der Sprache eingefroren, in der er entstand"
    )


def test_a_restored_finding_speaks_the_language_it_is_read_in() -> None:
    """Die Anschlussfrage: nicht „die Daten tragen die ID", sondern „der Kunde
    liest seine Sprache".

    **Geschrieben in einer Sprache, gelesen in einer dritten** — das ist der
    echte Fall, und nur er ist scharf: Läge die *Übersetzung* in der Datei,
    stünde beim Lesen die englische da, wo die französische hingehört. Ein Test,
    der auf Deutsch schreibt und auf Englisch liest, bliebe dagegen grün, weil
    ohne Katalogtreffer die Message-ID selbst zurückkommt und zufällig richtig
    aussieht.

    Sichtbar wird der Fehler ohnehin nur bei **warmem** Cache; in der Suite
    läuft jeder Test kalt, und darum stand er wochenlang da.
    """
    install_catalog("en", read_catalog("en"))
    set_language("en")
    try:
        written = finding_to_data(
            Finding(
                code="hollow.done",
                severity="info",
                message=TranslatableText(
                    "Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."
                ),
            )
        )
        install_catalog("fr", read_catalog("fr"))
        set_language("fr")
        in_french = str(finding_from_data(written).message)
    finally:
        set_language(SOURCE_LANGUAGE)

    assert in_french == str(
        TranslatableText("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters.").translate("fr")
    ), f"in der Sprache des Schreibers eingefroren: {in_french!r}"


def test_a_plain_message_stays_plain() -> None:
    """Was ein Aufrufer als Zeichenkette übergibt, wird nicht übersetzt — und
    ein Befund aus einer älteren Datei ohne die Kennzeichnung ebenso wenig."""
    restored = finding_from_data(
        finding_to_data(Finding(code="x", severity="info", message="roher Text"))
    )

    assert restored.message == "roher Text"
    assert not isinstance(restored.message, TranslatableText)


def test_a_findings_actions_survive_the_round_trip() -> None:
    """Ein Befund aus Projekt oder Plattencache behält seine Auswege.

    Ein Fehler einer Operation wird vor dem Prüfbericht abgefangen. Seine
    Handlungen gingen dabei verloren; nach einem warmen Cache wäre selbst ein
    flüchtiger Fix wieder verschwunden. Deshalb prüft die Runde neben Kennung
    und Reihenfolge auch übersetzbare Beschriftung und Hervorhebung.
    """
    from app.core.errors import REPAIR_AND_RETRY, SHOW_LOCATIONS

    finding = Finding(
        code="op.difference.BooleanFailedError",
        severity="error",
        message="Die Differenz ist nicht durchgelaufen.",
        suggestions=(REPAIR_AND_RETRY, SHOW_LOCATIONS),
    )

    restored = finding_from_data(finding_to_data(finding))

    assert [action.id for action in restored.suggestions] == [
        "repair_and_retry",
        "show_locations",
    ]
    assert isinstance(restored.suggestions[0].label, TranslatableText)
    assert restored.suggestions[0].primary


def test_two_sources_with_the_same_filename_survive_the_round_trip(tmp_path: Path) -> None:
    """``bracket.stl`` aus zwei Ordnern: Beide Quellen bekamen denselben
    Containerpfad, die zweite überschrieb die erste, und das Wiederöffnen
    endete an der Prüfsumme — heil geschrieben und trotzdem verloren (Fund
    des Gesamtreviews vom 25.08.2026). Die Kennung gehört in den Pfad.
    """
    from app.core.scene.project import embedded_source_path

    document = new_project(printer="centauri-carbon-2", material="petg").document
    payload_one = b"erste Fassung"
    payload_two = b"zweite, andere Fassung"
    document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=embedded_source_path("bracket.stl", "src_1"),
        sha256="",
    )
    document.sources["src_2"] = Source(
        id="src_2",
        kind="import",
        path=embedded_source_path("bracket.stl", "src_2"),
        sha256="",
    )
    assert document.sources["src_1"].path != document.sources["src_2"].path

    project = Project(document=document, sources={"src_1": payload_one, "src_2": payload_two})
    target = tmp_path / "gleichnamig.p3d"
    save(project, target)
    loaded = load(target)
    assert loaded.sources["src_1"] == payload_one
    assert loaded.sources["src_2"] == payload_two


def test_a_legacy_duplicate_path_stops_the_save_instead_of_losing_data(
    tmp_path: Path,
) -> None:
    """Der Altbestand kann zwei Quellen mit demselben Pfad tragen — dann hält
    das Speichern an, statt heil auszusehen und die erste zu verlieren."""
    document = new_project(printer="centauri-carbon-2", material="petg").document
    for source_id in ("src_1", "src_2"):
        document.sources[source_id] = Source(
            id=source_id, kind="import", path="sources/bracket.stl", sha256=""
        )
    project = Project(document=document, sources={"src_1": b"a", "src_2": b"b"})
    with pytest.raises(ValidationError) as caught:
        save(project, tmp_path / "doppelt.p3d")
    assert "sources/bracket.stl" in str(caught.value.values.get("path", ""))


def test_broken_but_valid_json_is_a_finding_not_a_traceback(tmp_path: Path) -> None:
    """Syntaktisch gültiges, strukturell kaputtes JSON: fünf Wege verließen
    ``load()`` als rohe KeyError/ValueError/TypeError ohne Handlungsvorschlag
    (Regel 17; Fund des Gesamtreviews vom 25.08.2026)."""
    import zipfile as zf

    document = new_project(printer="centauri-carbon-2", material="petg").document
    target = tmp_path / "kaputt.p3d"
    save(Project(document=document), target)

    import json as json_module

    with zf.ZipFile(target) as container:
        data = json_module.loads(container.read("project.json"))
    data["ops"] = [{"op": "create_box"}]  # ohne id/outputs — Pflichtschlüssel fehlen
    broken = tmp_path / "kaputt2.p3d"
    with zf.ZipFile(target) as source, zf.ZipFile(broken, "w") as out:
        for name in source.namelist():
            if name == "project.json":
                out.writestr(name, json_module.dumps(data))
            else:
                out.writestr(name, source.read(name))

    with pytest.raises(ValidationError) as caught:
        load(broken)
    assert caught.value.suggestions, "Regel 17: auch die kaputte Struktur trägt einen Vorschlag"


def test_an_unknown_fit_kind_is_refused_when_reading(tmp_path: Path) -> None:
    """``"type": "banane"`` riss die Auswertung mit einer rohen KeyError ab —
    ``check_fits`` steht außerhalb jedes try. Abgewiesen wird beim Lesen."""
    from app.core.scene.serialise import fit_from_data

    with pytest.raises(ValidationError) as caught:
        fit_from_data({"name": "krumm", "a": "obj_1:hole_1", "b": "obj_2:pin_1", "type": "banane"})
    assert caught.value.values.get("kind") == "banane"


def test_a_code_parameter_title_travels_as_message_id(tmp_path: Path) -> None:
    """Dasselbe Muster wie beim Transaktionstitel: ``str(title)`` fror die
    Sprache des Speicherzeitpunkts ein — das mitgelieferte Beispiel zeigte
    einem englischen Kunden „Breite/Tiefe/Höhe/Wandstärke"."""
    from app.core.scene.serialise import parameter_from_data, parameter_to_data
    from app.i18n import TranslatableText

    coded = Parameter(name="w", value=30.0, title=TranslatableText("Breite", None))
    data = parameter_to_data(coded)
    assert data["title"] == "Breite" and data.get("title_translatable") is True

    back = parameter_from_data("w", data)
    assert isinstance(back.title, TranslatableText), "die Anzeige löst erst beim Zeigen auf"

    typed = Parameter(name="w", value=30.0, title="meine Breite")
    plain = parameter_to_data(typed)
    assert plain.get("title_translatable") is None, "Getipptes wird nie übersetzt"


def test_a_circle_measured_before_the_diameter_rebuild_keeps_its_size() -> None:
    """18 → 19: Der Radius heißt Radius, und der Kreis bleibt derselbe.

    **Der Kunde denkt in Durchmesser, der Kreis maß Radius.** Bis v18 wurde ein
    Kreis über eine ``distance`` zwischen Mittelpunkt und Randpunkt bemaßt, und
    die Oberfläche nannte das „Abstand". Wer für eine M3-Bohrung 3,2 tippte,
    bekam ein Loch mit 6,4 mm — das Wort „Radius" kam in der ganzen Bedienung
    nicht vor, es gab also nicht einmal einen Anlass zu stutzen.

    Was diese Migration **nicht** tut, ist der Kern der Zusage: Sie ändert
    keine gespeicherte Zahl. Aus 3,2 wird nicht 6,4 — aus „Abstand 3,2" wird
    „R 3,2", und die Geometrie bleibt Punkt für Punkt dieselbe. Eine Migration,
    die Kundenwerte verdoppelt, wäre der teurere Weg gewesen: Ein Fehler in der
    Erkennung verdoppelte eine Bohrung, und das sieht niemand vor dem Druck.

    Die Datei ist am 31.08.2026 mit der v18-Anwendung erzeugt worden, auf dem
    Weg, den die Anwendung selbst nimmt — ``SketchCanvas.place_measured``, also
    dieselbe Methode wie ein Klick in der Zeichenfläche. Danach konnte kein
    Code sie mehr bauen.
    """
    import json
    import math

    from app.core.sketch.serialize import sketch_from_text
    from app.core.sketch.solver import solve_sketch

    project = load(Path(__file__).parent / "data" / "projects" / "circle_v18.p3d")
    assert project.document.format_version == FORMAT_VERSION

    text = project.document.ops[0].params["sketch"]
    raw = json.loads(text)
    kinds = [entry["kind"] for entry in raw["constraints"]]
    assert kinds == ["radius"], f"die Bemaßung heißt noch {kinds}"
    assert [entry["value"] for entry in raw["constraints"]] == ["3.200000000"], (
        "die gespeicherte Zahl hat sich geändert — die Migration deutet um, sie rechnet nicht"
    )

    # Und die Geometrie: Der gelöste Kreis hat weiterhin 3,2 Radius, nicht 1,6
    # und nicht 6,4. Das ist die Zusage „öffnet und rechnet korrekt" (§16.2) —
    # der Name allein sagte nichts darüber, was der Löser daraus macht.
    solved = solve_sketch(sketch_from_text(text), {})
    circle = next(entry for entry in solved.elements if entry.kind == "circle")
    centre, rim = circle.points
    span = math.hypot(rim[0] - centre[0], rim[1] - centre[1])
    assert abs(span - 3.2) < 1e-6, f"der Kreis misst {span:.4f} statt 3,2"


def test_the_migration_leaves_a_distance_alone_when_it_is_not_a_circle() -> None:
    """Im Zweifel bleibt „Abstand" stehen — eine falsche Beschriftung ist teurer.

    Umgedeutet wird nur, was **eindeutig** Mittelpunkt und Randpunkt desselben
    Kreises ist. Alles andere behält seine Art: ein Abstand zwischen zwei
    Linienpunkten, einer zwischen zwei Kreisen, einer in umgekehrter
    Reihenfolge. Ein stehen gebliebenes ``distance`` ist eine kosmetische
    Restzweisprachigkeit im Einzelfall; ein falsch umgedeutetes wäre eine
    falsche Beschriftung an einer Kundenbemaßung, und die fällt niemandem auf.
    """
    import json

    from app.core.scene.migrations import _rename_circle_measures

    def constraints(text: str) -> list[str]:
        return [entry["kind"] for entry in json.loads(text)["constraints"]]

    def sketch(elements: list[dict[str, object]], targets: list[int]) -> str:
        return json.dumps(
            {
                "plane": "xy",
                "elements": elements,
                "constraints": [{"kind": "distance", "targets": targets, "value": "3.2"}],
            }
        )

    circle = {"kind": "circle", "points": [[0.0, 0.0], [3.2, 0.0]]}
    line = {"kind": "line", "points": [[0.0, 0.0], [5.0, 0.0]]}

    assert constraints(_rename_circle_measures(sketch([circle], [0, 1]))) == ["radius"], (
        "der eindeutige Fall wird nicht umgedeutet"
    )
    assert constraints(_rename_circle_measures(sketch([line], [0, 1]))) == ["distance"], (
        "eine Linienlänge ist kein Radius"
    )
    assert constraints(_rename_circle_measures(sketch([circle], [1, 0]))) == ["distance"], (
        "verkehrte Reihenfolge: der zweite Punkt ist der Mittelpunkt, nicht der Rand"
    )
    assert constraints(_rename_circle_measures(sketch([circle, circle], [1, 2]))) == ["distance"], (
        "quer über zwei Kreise gemessen ist kein Radius"
    )
    assert constraints(_rename_circle_measures(sketch([line, circle], [2, 3]))) == ["radius"], (
        "der Kreis dahinter wird nicht gefunden — die Punktzählung stimmt nicht"
    )
