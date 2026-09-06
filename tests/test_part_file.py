"""Tests für den sicheren lokalen Austausch von Bausteindateien."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import os
import stat
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import AppError, FileWriteError, ValidationError
from app.core.knowledge import profiles
from app.core.knowledge.parts import recipe, shared
from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
from app.core.knowledge.parts.registry import PartRegistry
from app.core.registry.registry import Registry
from app.core.scene.migrations import FORMAT_VERSION
from app.core.types import Document, Operation, Parameter, Source, SourceOrigin

HISTORICAL_RECIPE = Path(__file__).parent / "data" / "recipes" / "historical_box_v1.json"
MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture(scope="module")
def part() -> recipe.Recipe:
    """Erzeugt einmalig einen echten Baustein über denselben Weg wie die App."""

    load_operations()
    document = Document(
        format_version=FORMAT_VERSION,
        app_version="0.0.0-test",
        parameters={
            "width": Parameter(name="width", value=20.0, unit="mm"),
            "depth": Parameter(name="depth", value=18.0, unit="mm"),
            "height": Parameter(name="height", value=8.0, unit="mm"),
        },
        ops=[
            Operation(
                id=1,
                op="create_box",
                outputs=("obj_1",),
                params={
                    "width": "@width",
                    "depth": "@depth",
                    "height": "@height",
                    "anchor": "corner",
                    "name": "",
                },
            )
        ],
    )
    made = recipe.capture(
        document,
        {},
        name="pruefwuerfel",
        title="Prüfwürfel",
        group="structure",
        doc="Dokumentation unter https://example.invalid/teil",
        op_ids=(1,),
        exposed=(
            recipe.ExposedParam(
                name="width",
                title="Breite",
                default=20.0,
                minimum=5.0,
                maximum=100.0,
            ),
            recipe.ExposedParam(
                name="depth",
                title="Tiefe",
                default=18.0,
                minimum=5.0,
                maximum=100.0,
            ),
            recipe.ExposedParam(
                name="height",
                title="Höhe",
                default=8.0,
                minimum=2.0,
                maximum=50.0,
            ),
        ),
        features={"top": "face_top"},
        profile=profiles.make_profile(),
    )
    return dataclasses.replace(made, author="RS Digital <kontakt>", license="CC-BY-4.0")


@pytest.fixture(scope="module")
def part_payload(part: recipe.Recipe) -> bytes:
    return PartFileIO().export_file(part)


def test_export_and_validation_are_one_lossless_offline_path(
    part: recipe.Recipe,
) -> None:
    codec = PartFileIO()

    payload = codec.export_file(part)
    parsed = codec.validate(payload)

    assert parsed == part
    assert payload.endswith(b"\n")
    assert parsed.doc == "Dokumentation unter https://example.invalid/teil"
    assert parsed.author == "RS Digital <kontakt>"
    assert parsed.license == "CC-BY-4.0"
    assert b"http" in payload
    assert "urllib.request" not in Path("app/core/knowledge/parts/part_file.py").read_text("utf-8")


def test_external_export_uses_the_branded_suffix_and_roundtrips(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Die Kundendatei ist erkennbar, bleibt aber dasselbe geprüfte JSON-Format."""

    codec = PartFileIO()

    written = codec.export_to_file(part, tmp_path / "mein-baustein.json")

    assert written == tmp_path / f"mein-baustein{PART_FILE_SUFFIX}"
    assert not (tmp_path / "mein-baustein.json").exists()
    assert codec.validate(written.read_bytes()) == part


def test_external_export_never_leaves_a_partial_customer_file(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Abbruch hält die vorige Kundendatei bytegenau und räumt Tempdaten auf."""

    codec = PartFileIO()
    target = codec.export_to_file(part, tmp_path / f"mein-baustein{PART_FILE_SUFFIX}")
    before = target.read_bytes()
    changed = dataclasses.replace(part, doc="neuer Stand")
    original_write = recipe.os.write
    calls = 0

    def break_after_first_piece(descriptor: int, payload: bytes | memoryview) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            piece = bytes(payload[: max(1, len(payload) // 4)])
            return original_write(descriptor, piece)
        raise OSError("erzwungener Teilwrite")

    monkeypatch.setattr(recipe.os, "write", break_after_first_piece)

    with pytest.raises(FileWriteError) as raised:
        codec.export_to_file(changed, target)

    assert target.read_bytes() == before
    assert raised.value.values["target"] == target.name
    assert raised.value.values["reason"] == "write_failed"
    assert str(tmp_path) not in str(raised.value.as_dict())
    assert isinstance(raised.value.__cause__, OSError)
    assert not tuple(tmp_path.glob(recipe._temporary_pattern()))


def test_install_returns_success_after_late_directory_sync_error(
    part_payload: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine sichtbare und gebundene Installation wird nicht als Fehlschlag gemeldet."""

    parts = PartRegistry()
    registry = Registry()
    original_sync = recipe._sync_directory
    calls = 0

    def fail_once(directory: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("später Verzeichnisfehler")
        original_sync(directory)

    monkeypatch.setattr(recipe, "_sync_directory", fail_once)

    installed = PartFileIO().install_file(
        part_payload,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert installed.path.exists()
    assert parts.has(installed.recipe.name)
    assert registry.has(f"insert_{installed.recipe.name}")


def test_missing_rights_stay_empty_and_are_explicit_in_export(
    part: recipe.Recipe,
) -> None:
    private = dataclasses.replace(part, author="", license="")

    payload = PartFileIO().export_file(private)
    exported = json.loads(payload)
    parsed = PartFileIO().validate(payload)

    assert exported["author"] == ""
    assert exported["license"] == ""
    assert parsed.author == ""
    assert parsed.license == ""


def test_import_marks_exact_bytes_without_private_path_and_stays_foreign(
    part_payload: bytes,
    tmp_path: Path,
) -> None:
    codec = PartFileIO(clock=lambda: datetime(2026, 8, 31, 13, 45, 12, tzinfo=UTC))

    imported = codec.import_file(part_payload)

    digest = hashlib.sha256(part_payload).hexdigest()
    assert not hasattr(imported, "payload")
    assert imported.sha256 == digest
    assert imported.recipe.imported_origin == recipe.ImportedOrigin(
        source_sha256=digest,
        imported_at="2026-08-31T13:45:12Z",
    )
    assert set(dataclasses.asdict(imported.recipe.imported_origin)) == {
        "source_sha256",
        "imported_at",
    }
    recipe.save(imported.recipe, tmp_path)
    parts = PartRegistry()
    loaded = recipe.load_all(tmp_path, parts, Registry())
    assert loaded.loaded == (imported.recipe.name,)
    assert parts.get(imported.recipe.name).source == recipe.IMPORTED_SOURCE
    assert not parts.get(imported.recipe.name).own


def test_fresh_process_can_export_without_a_preloaded_operation_registry() -> None:
    """Der Export darf nicht von einem zuvor geöffneten Fenster abhängen."""

    script = textwrap.dedent(
        """
        from app.core.knowledge.parts.part_file import PartFileIO
        from app.core.knowledge.parts.recipe import Recipe
        from app.core.scene.migrations import FORMAT_VERSION
        from app.core.types import Document, Operation

        part = Recipe(
            name="fresh_box",
            title="Fresh box",
            group="structure",
            document=Document(
                format_version=FORMAT_VERSION,
                app_version="test",
                ops=[Operation(
                    id=1,
                    op="create_box",
                    outputs=("obj_1",),
                    params={
                        "width": 20.0,
                        "depth": 18.0,
                        "height": 8.0,
                        "anchor": "corner",
                        "name": "",
                    },
                )],
            ),
            features={"top": "face_top"},
        )
        payload = PartFileIO().export_file(part)
        assert b'"create_box"' in payload
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_install_is_fail_closed_on_name_collision_and_offers_a_free_name(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Eine fremde Datei ersetzt weder Katalog, Operation noch Kundendatei."""

    own = dataclasses.replace(part, doc="eigene Fassung")
    foreign = dataclasses.replace(part, doc="fremde Fassung")
    parts = PartRegistry()
    registry = Registry()
    recipe.register(own, parts, registry)
    recipe.save(own, tmp_path)
    before = (tmp_path / f"{own.name}.json").read_bytes()
    payload = PartFileIO().export_file(foreign)

    with pytest.raises(ValidationError, match="vorgeschlagenen") as raised:
        PartFileIO().install_file(
            payload,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    suggested = raised.value.values["suggested_name"]
    assert suggested == "pruefwuerfel_imported"
    assert parts.get(own.name).doc == "eigene Fassung"
    assert registry.has("insert_pruefwuerfel")
    assert (tmp_path / f"{own.name}.json").read_bytes() == before

    installed = PartFileIO().install_file(
        payload,
        name=suggested,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    assert installed.recipe.name == suggested
    assert installed.recipe.imported_origin is not None
    assert installed.path == tmp_path / f"{suggested}.json"
    stored = recipe.from_data(json.loads(installed.path.read_text("utf-8")))
    assert stored.imported_origin == installed.recipe.imported_origin
    assert stored.doc == "fremde Fassung"
    assert parts.get(suggested).source == recipe.IMPORTED_SOURCE


def test_install_treats_an_existing_operation_as_a_name_collision(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Auch ein verwaister Operationsname wird weder ersetzt noch verschleiert."""

    existing_parts = PartRegistry()
    registry = Registry()
    recipe.register(part, existing_parts, registry)
    existing_parts.remove(part.name)
    operation_name = f"insert_{part.name}"
    existing_operation = registry.get(operation_name)
    payload = PartFileIO().export_file(dataclasses.replace(part, doc="fremde Fassung"))

    with pytest.raises(ValidationError) as raised:
        PartFileIO().install_file(
            payload,
            parts=existing_parts,
            registry=registry,
            directory=tmp_path,
        )

    assert raised.value.values["suggested_name"] == "pruefwuerfel_imported"
    assert registry.get(operation_name) is existing_operation
    assert not existing_parts.has(part.name)
    assert not (tmp_path / f"{part.name}.json").exists()


def test_install_wraps_an_unusable_target_directory_as_an_actionable_error(
    part_payload: bytes,
    tmp_path: Path,
) -> None:
    """Ein Dateisystemfehler erreicht den Nutzer nie roh und ohne Ausweg."""

    target = tmp_path / "recipes"
    target.write_text("keine Ablage", encoding="utf-8")
    parts = PartRegistry()
    registry = Registry()

    with pytest.raises(FileWriteError) as raised:
        PartFileIO().install_file(
            part_payload,
            parts=parts,
            registry=registry,
            directory=target,
        )

    assert raised.value.suggestions
    assert raised.value.values["target"] == "pruefwuerfel.json"
    assert raised.value.values["reason"] == "write_failed"
    assert raised.value.detail
    assert str(target) not in str(raised.value.as_dict())
    assert "keine Ablage" not in str(raised.value.as_dict())
    assert isinstance(raised.value.__cause__, OSError)
    assert not parts.has("pruefwuerfel")
    assert not registry.has("insert_pruefwuerfel")


def test_install_removes_the_file_when_catalog_binding_fails(
    part_payload: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine fertige Datei wird bei einem Bindefehler wieder vollständig entfernt."""

    from app.core.knowledge.parts import ops as part_ops

    parts = PartRegistry()
    registry = Registry()
    original = part_ops.register_one

    def register_then_fail(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("erzwungener Bindefehler")

    monkeypatch.setattr(part_ops, "register_one", register_then_fail)

    with pytest.raises(RuntimeError, match="Bindefehler"):
        PartFileIO().install_file(
            part_payload,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert not (tmp_path / "pruefwuerfel.json").exists()
    assert not tuple(tmp_path.glob(".*.tmp"))
    assert not parts.has("pruefwuerfel")
    assert not registry.has("insert_pruefwuerfel")


def test_remove_and_restore_preserve_exact_recipe_file(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Bibliotheks-Undo stellt Bytes, Metadaten, Quelle und Bindungen wieder her."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    exact = (
        json.dumps(recipe.file_data(part), ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    path.write_bytes(exact)
    os.utime(path, ns=(1_725_000_000_000_000_000, 1_725_000_001_000_000_000))
    before = path.stat()

    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert removed.sha256 == hashlib.sha256(exact).hexdigest()
    assert removed.undo.payload == exact
    assert removed.undo.source == recipe.RECIPE_SOURCE
    assert removed.undo.file_mode == stat.S_IMODE(before.st_mode)
    assert removed.undo.mtime_ns == before.st_mtime_ns
    assert not path.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")

    restored = PartFileIO().restore_to_library(
        removed.undo,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert restored.path.read_bytes() == exact
    after = restored.path.stat()
    assert stat.S_IMODE(after.st_mode) == removed.undo.file_mode
    assert after.st_mtime_ns == removed.undo.mtime_ns
    assert parts.get(part.name).source == recipe.RECIPE_SOURCE
    assert registry.has(f"insert_{part.name}")


def test_import_removal_uses_the_stored_digest_and_restores_import_origin(
    part_payload: bytes,
    tmp_path: Path,
) -> None:
    """Import-Rückgängig bindet sich an die tatsächlich gespeicherten Bytes."""

    parts = PartRegistry()
    registry = Registry()
    codec = PartFileIO(clock=lambda: datetime(2026, 8, 31, 13, 45, 12, tzinfo=UTC))
    installed = codec.install_file(
        part_payload,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    stored = installed.path.read_bytes()

    assert installed.sha256 == hashlib.sha256(part_payload).hexdigest()
    assert installed.stored_sha256 == hashlib.sha256(stored).hexdigest()
    removed = codec.remove_from_library(
        installed.recipe.name,
        expected_sha256=installed.stored_sha256,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    codec.restore_to_library(
        removed.undo,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert installed.path.read_bytes() == stored
    assert parts.get(installed.recipe.name).source == recipe.IMPORTED_SOURCE
    restored = recipe.from_data(json.loads(stored))
    assert restored.imported_origin == installed.recipe.imported_origin


@pytest.mark.parametrize("source", ("shipped", recipe.TRAVELLED_SOURCE, "user"))
def test_remove_rejects_every_non_file_recipe_source(
    part: recipe.Recipe,
    tmp_path: Path,
    source: str,
) -> None:
    """Eingebaute, Python- und mitgereiste Bausteine bleiben außerhalb des Dateiwegs."""

    parts = PartRegistry()
    registry = Registry()
    recipe.register(part, parts, registry, source=source)

    with pytest.raises(AppError) as raised:
        PartFileIO().remove_from_library(
            part.name,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert raised.value.values == {"reason": "source"}
    assert raised.value.suggestions
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")


def test_expected_digest_prevents_removing_a_changed_recipe(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Ein altes Import-Undo löscht keinen später geänderten gleichnamigen Stand."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    before = path.read_bytes()

    with pytest.raises(AppError) as raised:
        PartFileIO().remove_from_library(
            part.name,
            expected_sha256="0" * 64,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert raised.value.values == {"reason": "changed"}
    assert path.read_bytes() == before
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")
    assert str(tmp_path) not in str(raised.value.as_dict())


def test_expected_digest_closes_an_external_replacement_race(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Geprüft wird der atomar quarantänisierte Eintrag, nicht ein früher gelesener Pfad."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    replacement = (
        json.dumps(recipe.file_data(part), ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    original_rename = Path.rename
    swapped = False

    def replace_immediately_before_quarantine(source: Path, target: Path) -> Path:
        nonlocal swapped
        if source == path and not swapped:
            swapped = True
            external = tmp_path / "external.json"
            external.write_bytes(replacement)
            external.replace(source)
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", replace_immediately_before_quarantine)

    with pytest.raises(AppError) as raised:
        PartFileIO().remove_from_library(
            part.name,
            expected_sha256=expected,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert raised.value.values == {"reason": "changed"}
    assert path.read_bytes() == replacement
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")
    assert not tuple(tmp_path.glob(".solidon-remove-*"))


def test_remove_unlink_failure_keeps_file_and_both_registries(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vor dem Plattenwechsel bleibt der vollständige alte Zustand sichtbar."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    before = path.read_bytes()

    original_rename = Path.rename

    def fail_first_rename(source: Path, target: Path) -> Path:
        if source == path:
            raise OSError("erzwungener Löschfehler")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_first_rename)

    with pytest.raises(AppError) as raised:
        PartFileIO().remove_from_library(
            part.name,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert path.read_bytes() == before
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")
    assert str(tmp_path) not in str(raised.value.as_dict())


def test_remove_interrupt_after_first_registry_swap_rolls_forward(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach dem Platten-Commit wird eine Unterbrechung vollständig vorwärts gerollt."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    original = registry.replace_state
    calls = 0

    def interrupt_once(prepared: Registry) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("erzwungene Unterbrechung")
        original(prepared)

    monkeypatch.setattr(registry, "replace_state", interrupt_once)

    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert not path.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")
    assert calls >= 2
    assert removed.undo.payload


def test_remove_directory_sync_failure_after_commit_rolls_forward(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch ein Dauerfehler nach dem Quarantäne-Commit lässt keinen halben Stand."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    original_sync = recipe._sync_directory
    calls = 0

    def fail_second_sync(directory: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("erzwungener Verzeichnisfehler")
        original_sync(directory)

    monkeypatch.setattr(recipe, "_sync_directory", fail_second_sync)

    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert not path.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")
    assert removed.undo.payload
    assert not tuple(tmp_path.glob(".solidon-remove-*.committed"))

    monkeypatch.setattr(recipe, "_sync_directory", original_sync)
    restarted_parts = PartRegistry()
    restarted_registry = Registry()
    loaded = recipe.load_all(tmp_path, restarted_parts, restarted_registry)
    assert loaded.loaded == ()
    assert not tuple(tmp_path.glob(".solidon-remove-*"))


def test_restart_restores_pending_removal_before_loading(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Ein Abbruch vor dem Commit wird beim nächsten Start zum alten Stand."""

    payload = recipe._encoded_file(part)
    pending = tmp_path / f".solidon-remove-999999-deadbeef.{part.name}.json.{'1' * 32}.pending"
    pending.write_bytes(payload)
    parts = PartRegistry()
    registry = Registry()

    loaded = recipe.load_all(tmp_path, parts, registry)

    target = tmp_path / f"{part.name}.json"
    assert loaded.loaded == (part.name,)
    assert target.read_bytes() == payload
    assert not pending.exists()
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")


def test_restart_discards_committed_removal_before_loading(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Ein Abbruch nach dem Commit bleibt auch nach dem Neustart entfernt."""

    committed = tmp_path / f".solidon-remove-999999-deadbeef.{part.name}.json.{'2' * 32}.committed"
    committed.write_bytes(recipe._encoded_file(part))
    parts = PartRegistry()
    registry = Registry()

    loaded = recipe.load_all(tmp_path, parts, registry)

    assert loaded.loaded == ()
    assert not committed.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")


def test_restore_write_failure_keeps_the_removed_state(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Fehler vor der Veröffentlichung erzeugt weder Datei noch Bindung."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    def fail_write(_descriptor: int, _payload: bytes | memoryview) -> int:
        raise OSError("erzwungener Schreibfehler")

    monkeypatch.setattr(recipe.os, "write", fail_write)

    with pytest.raises(AppError):
        PartFileIO().restore_to_library(
            removed.undo,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert not path.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")
    assert not tuple(tmp_path.glob(recipe._temporary_pattern()))


def test_restore_returns_success_after_late_directory_sync_error(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein vollständig veröffentlichter Restore behält seinen nutzbaren Undo-Erfolg."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    original_sync = recipe._sync_directory
    calls = 0

    def fail_once(directory: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("später Verzeichnisfehler")
        original_sync(directory)

    monkeypatch.setattr(recipe, "_sync_directory", fail_once)

    restored = PartFileIO().restore_to_library(
        removed.undo,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert restored.path == path
    assert path.read_bytes() == removed.undo.payload
    assert parts.has(part.name)
    assert registry.has(f"insert_{part.name}")


def test_restore_interrupt_after_first_registry_swap_rolls_forward(
    part: recipe.Recipe,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach der Dateiveröffentlichung wird Restore trotz Unterbrechung vollständig."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    original = registry.replace_state
    calls = 0

    def interrupt_once(prepared: Registry) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("erzwungene Unterbrechung")
        original(prepared)

    monkeypatch.setattr(registry, "replace_state", interrupt_once)

    restored = PartFileIO().restore_to_library(
        removed.undo,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )

    assert path.read_bytes() == removed.undo.payload
    assert parts.get(part.name).source == recipe.RECIPE_SOURCE
    assert registry.has(f"insert_{part.name}")
    assert calls >= 2
    assert restored.path == path


def test_restore_revalidates_tamper_before_touching_state(
    part: recipe.Recipe,
    tmp_path: Path,
) -> None:
    """Der Token ist Daten, keine Vollmacht für ungeprüfte Bytes."""

    parts = PartRegistry()
    registry = Registry()
    path = recipe.replace(part, parts, registry, tmp_path)
    removed = PartFileIO().remove_from_library(
        part.name,
        parts=parts,
        registry=registry,
        directory=tmp_path,
    )
    tampered = dataclasses.replace(removed.undo, payload=removed.undo.payload + b" ")

    with pytest.raises(AppError) as raised:
        PartFileIO().restore_to_library(
            tampered,
            parts=parts,
            registry=registry,
            directory=tmp_path,
        )

    assert raised.value.values == {"reason": "undo"}
    assert not path.exists()
    assert not parts.has(part.name)
    assert not registry.has(f"insert_{part.name}")


def test_reimport_replaces_only_immediate_origin(part_payload: bytes) -> None:
    first = PartFileIO(clock=lambda: datetime(2026, 8, 30, 10, 11, 12, tzinfo=UTC)).import_file(
        part_payload
    )
    forwarded = PartFileIO().export_file(first.recipe)

    second = PartFileIO(clock=lambda: datetime(2026, 8, 31, 13, 45, 12, tzinfo=UTC)).import_file(
        forwarded
    )

    assert second.recipe.imported_origin == recipe.ImportedOrigin(
        source_sha256=hashlib.sha256(forwarded).hexdigest(),
        imported_at="2026-08-31T13:45:12Z",
    )
    assert second.recipe.author == first.recipe.author
    assert second.recipe.license == first.recipe.license
    assert recipe.fingerprint(second.recipe) == recipe.fingerprint(first.recipe)


def test_embedded_model_data_and_its_provenance_survive_export(
    part: recipe.Recipe,
) -> None:
    model = (MESHES / "cube_clean.stl").read_bytes()
    source = Source(
        id="src_1",
        kind="generated",
        path="sources/model.stl",
        sha256=hashlib.sha256(model).hexdigest(),
        origin=SourceOrigin(
            url="http://example.invalid/source#historical-fragment",
            title="Erzeugte Form",
            author="Nutzer",
            licence="CC0-1.0",
            retrieved="2026-08-31T12:00:00Z",
            prompt="Eine Halterung",
            seed=42,
        ),
    )
    with_source = dataclasses.replace(
        part,
        document=dataclasses.replace(
            part.document,
            ops=[
                Operation(
                    id=1,
                    op="load",
                    outputs=("obj_1",),
                    params={
                        "source": source.id,
                        "unit": "mm",
                        "name": "",
                        "place_on_bed": False,
                        "weld": True,
                        "remove_degenerate": True,
                        "unify_normals": True,
                    },
                )
            ],
            sources={source.id: source},
        ),
        payloads={source.id: model},
        exposed=(),
        features={"surface": "face_1"},
    )

    parsed = PartFileIO().validate(PartFileIO().export_file(with_source))

    assert parsed.payloads == {source.id: model}
    assert parsed.document.sources[source.id] == source
    origin = parsed.document.sources[source.id].origin
    assert origin is not None
    assert origin.url == "http://example.invalid/source#historical-fragment"
    assert origin.prompt == "Eine Halterung"
    assert origin.seed == 42


def test_retired_public_origin_is_not_part_of_the_file_contract(part_payload: bytes) -> None:
    data = json.loads(part_payload)
    data["published_origin"] = {
        "server_id": "pruefwuerfel-1",
        "origin": "https://solidon3d.de",
        "source_sha256": "a" * 64,
        "retrieved": "2026-08-31T12:34:56Z",
    }

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "recipe"
    assert "published_origin" not in str(raised.value.as_dict())


def test_fixed_historical_recipe_migrates_opens_and_exports() -> None:
    payload = HISTORICAL_RECIPE.read_bytes()
    stored = json.loads(payload)
    assert stored["document"]["format_version"] == 1
    assert "chat" not in stored["document"]
    assert "print_settings" not in stored["document"]

    parsed = PartFileIO().validate(payload)

    assert parsed.document.format_version == FORMAT_VERSION
    assert stored["format_version"] == 1
    assert parsed.format_version == recipe.FORMAT_VERSION == 2
    assert parsed.dependencies == {}
    assert json.loads(payload) == stored, "die historische Datei wird nicht verändert"
    assert parsed.title == "Historischer Quader"
    assert PartFileIO().validate(PartFileIO().export_file(parsed)) == parsed


def _nested_part_data(part: recipe.Recipe) -> dict[str, Any]:
    """Eine echte zweistufige Konstruktion ohne Abhängigkeit vom Nutzerkatalog."""
    child = recipe.file_data(dataclasses.replace(part, name="review_inner"))
    parent = recipe.file_data(dataclasses.replace(part, name="review_outer"))
    parent["dependencies"] = {"review_inner": child}
    parent["document"]["ops"].append(
        {
            "id": 2,
            "op": "insert_review_inner",
            "in": ["obj_1"],
            "out": ["obj_1"],
            "params": {"x": 1, "z": 4},
        }
    )
    return parent


def test_nested_part_installs_and_reopens_in_a_fresh_receiver(part, tmp_path):
    payload = PartFileIO().export_file(recipe.from_data(_nested_part_data(part)))
    target = tmp_path / "nested.solidon-part"
    target.write_bytes(payload)
    isolation = tmp_path / "recipient"
    isolation.mkdir()
    env = dict(os.environ)
    for key in (
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        env[key] = str(isolation)
    script = textwrap.dedent("""
        import json, sys
        from pathlib import Path
        from app.core.bootstrap import load_operations
        from app.core.knowledge import profiles
        from app.core.knowledge.parts import recipe, PARTS
        from app.core.knowledge.parts.part_file import PartFileIO
        from app.core.registry import REGISTRY
        load_operations()
        assert Path(recipe.__file__).resolve().is_relative_to(Path.cwd())
        assert not PARTS.has("review_inner") and not PARTS.has("review_outer")
        installed = PartFileIO().install_file(Path(sys.argv[1]).read_bytes())
        result = PARTS.get("review_outer").fn(PARTS.get("review_outer").params())
        assert result.mesh.is_watertight and result.mesh.volume > 20 * 18 * 8
        assert not PARTS.has("review_inner"), "der private Anhang ersetzt keinen Katalogeintrag"
        PARTS.remove("review_outer")
        REGISTRY.remove("insert_review_outer")
        loaded = recipe.load_all()
        assert "review_outer" in loaded.loaded and not loaded.findings
        reopened = PARTS.get("review_outer").fn(PARTS.get("review_outer").params())
        assert abs(reopened.mesh.volume - result.mesh.volume) < 1e-7
        print(json.dumps({"volume": reopened.mesh.volume, "installed": str(installed.path)}))
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(target)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("problem", ["cycle", "nested", "count", "unknown", "budget", "shipped"])
def test_nested_recipe_boundaries_stop_before_build(part, monkeypatch, problem):
    data = _nested_part_data(part)
    inner = data["dependencies"]["review_inner"]
    if problem == "cycle":
        inner["document"]["ops"][0]["op"] = "insert_review_outer"
    elif problem == "nested":
        inner["dependencies"] = {"unexpected": {}}
    elif problem == "count":
        data["dependencies"] = {str(index): {} for index in range(recipe.MAX_DEPENDENCIES + 1)}
    elif problem == "unknown":
        inner["document"]["ops"][0]["op"] = "unknown_recipe_step"
    elif problem == "budget":
        data["document"]["ops"] = [data["document"]["ops"][-1]] * shared.MAX_OPERATIONS
    else:
        inner["name"] = "dowel"
        data["dependencies"] = {"dowel": inner}
        data["document"]["ops"][-1]["op"] = "insert_dowel"
    monkeypatch.setattr(
        recipe, "build", lambda *args, **kwargs: pytest.fail("kein Bau vor Prüfung")
    )
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())
    assert raised.value.suggestions


def test_embedded_recipe_does_not_replace_a_different_local_version(part):
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    data = _nested_part_data(part)
    expected = recipe.build(
        PartFileIO().validate(json.dumps(data).encode()), profile=profiles.make_profile()
    ).mesh.volume
    local = dataclasses.replace(
        part,
        name="review_inner",
        doc="lokaler eigener Stand",
        exposed=tuple(
            dataclasses.replace(entry, default=10) if entry.name == "width" else entry
            for entry in part.exposed
        ),
    )
    try:
        recipe.register(local)
        previous = PARTS.get("review_inner")
        imported = PartFileIO().validate(json.dumps(data).encode())
        assert recipe.build(imported, profile=profiles.make_profile()).mesh.volume == pytest.approx(
            expected
        )
        assert PARTS.get("review_inner") is previous
    finally:
        PARTS.remove("review_inner")
        REGISTRY.remove("insert_review_inner")


@pytest.mark.parametrize(
    "imported_origin",
    (
        {"source_sha256": "B" * 64, "imported_at": "2026-08-31T13:45:12Z"},
        {"source_sha256": "b" * 64, "imported_at": "2026-8-31T1:2:3Z"},
        {
            "source_sha256": "b" * 64,
            "imported_at": "2026-08-31T13:45:12Z",
            "path": "C:/privat/teil.json",
        },
    ),
)
def test_file_origin_is_closed_and_strict(
    part_payload: bytes,
    imported_origin: object,
) -> None:
    data = json.loads(part_payload)
    data["imported_origin"] = imported_origin

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


def test_unknown_operations_and_code_shaped_data_are_rejected(part_payload: bytes) -> None:
    data = json.loads(part_payload)
    data["document"]["ops"][0]["op"] = "execute_foreign_code"
    data["document"]["ops"][0]["params"] = {"source": "import os"}

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert "execute_foreign_code" not in str(raised.value.as_dict())


def test_unreferenced_executable_payload_is_rejected(part_payload: bytes) -> None:
    """Nur registrierte Quellenparameter dürfen eingebettete Daten erreichbar machen."""

    source_id = "plugin_source"
    payload = b"import os\n"
    data = json.loads(part_payload)
    data["document"]["sources"] = {
        source_id: {
            "type": "import",
            "path": "sources/plugin.py",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"] = {source_id: "aW1wb3J0IG9zCg=="}
    data["document"]["ops"][0]["params"]["name"] = source_id

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "sources"


def test_referenced_source_must_match_the_registered_import_path(part_payload: bytes) -> None:
    """Auch eine echte Quellenreferenz macht fremden Inhalt nicht ausführbar."""

    source_id = "model_source"
    payload = b"import os\n"
    data = json.loads(part_payload)
    data["document"]["sources"] = {
        source_id: {
            "type": "import",
            "path": "sources/model.stl",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"] = {source_id: "aW1wb3J0IG9zCg=="}
    data["document"]["ops"] = [
        {
            "id": 1,
            "op": "load",
            "in": [],
            "out": ["obj_1"],
            "params": {"source": source_id, "unit": "mm"},
            "solver": None,
            "seed": None,
            "matches": {},
            "translatable": [],
        }
    ]

    with pytest.raises(AppError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


@pytest.mark.parametrize(
    ("source_kind", "path"),
    (("image", "sources/model.stl"), ("import", "sources/model.step")),
)
def test_source_kind_and_suffix_must_match_the_registered_consumer(
    part_payload: bytes,
    source_kind: str,
    path: str,
) -> None:
    model = (MESHES / "cube_clean.stl").read_bytes()
    source_id = "model_source"
    data = json.loads(part_payload)
    data["document"]["sources"] = {
        source_id: {
            "type": source_kind,
            "path": path,
            "sha256": hashlib.sha256(model).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"] = {source_id: base64.b64encode(model).decode("ascii")}
    data["document"]["ops"] = [
        {
            "id": 1,
            "op": "load",
            "in": [],
            "out": ["obj_1"],
            "params": {"source": source_id, "unit": "mm"},
            "solver": None,
            "seed": None,
            "matches": {},
            "translatable": [],
        }
    ]

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


def test_randomized_operation_requires_a_stored_seed(part: recipe.Recipe) -> None:
    """Ein Rezept mit Zufallsoperation muss beim zweiten Lauf dasselbe ergeben."""

    def oriented(seed: int | None) -> recipe.Recipe:
        operation = Operation(
            id=2,
            op="orient_for_print",
            inputs=("obj_1",),
            outputs=("obj_2",),
            params={"thorough": False, "candidates": 24},
            seed=seed,
        )
        return dataclasses.replace(
            part,
            document=dataclasses.replace(
                part.document,
                ops=[*part.document.ops, operation],
            ),
        )

    with pytest.raises(ValidationError) as raised:
        PartFileIO().export_file(oriented(None))

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert (
        PartFileIO().validate(PartFileIO().export_file(oriented(987_654))).document.ops[-1].seed
        == 987_654
    )


@pytest.mark.parametrize(
    "path",
    (
        "C:\\private\\part.stl",
        "\\\\server\\share\\part.stl",
        "/private/part.stl",
        "../private/part.stl",
        "file:///private/part.stl",
    ),
)
def test_local_and_parent_source_paths_are_rejected(part_payload: bytes, path: str) -> None:
    data = json.loads(part_payload)
    model = b"hello"
    data["document"]["sources"] = {
        "src_1": {
            "type": "import",
            "path": path,
            "sha256": hashlib.sha256(model).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"]["src_1"] = "aGVsbG8="

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "sources.path"


@pytest.mark.parametrize(
    "source_id",
    (
        r"C:\Users\Robert\private.stl",
        "/Users/robert/private.stl",
        "private/model.stl",
        r"private\model.stl",
        "../private.stl",
    ),
)
def test_source_ids_cannot_carry_private_paths(
    part_payload: bytes,
    source_id: str,
) -> None:
    """Auch der Wörterbuchschlüssel darf keinen privaten Pfad verraten."""

    data = json.loads(part_payload)
    model = b"hello"
    data["document"]["sources"] = {
        source_id: {
            "type": "import",
            "path": "sources/model.stl",
            "sha256": hashlib.sha256(model).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"] = {source_id: "aGVsbG8="}

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "sources"
    assert all(source_id not in str(value) for value in raised.value.values.values())


def test_payload_ids_are_checked_before_a_mismatch_can_reflect_them(
    part_payload: bytes,
) -> None:
    """Auch ein allein eingeschmuggelter Payload-Schlüssel bleibt kein Pfadkanal."""

    source_id = r"C:\Users\Robert\private.stl"
    data = json.loads(part_payload)
    data["payloads"][source_id] = "aGVsbG8="

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "payloads"
    assert all(source_id not in str(value) for value in raised.value.values.values())


@pytest.mark.parametrize("kind", ("parameter", "source", "feature"))
def test_valid_foreign_identifiers_never_reach_the_serialized_error(
    part_payload: bytes,
    kind: str,
) -> None:
    """Auch formal gültige Kundenkennungen bleiben aus field und as_dict heraus."""

    private_id = f"customer_private_{kind}_identifier"
    data = json.loads(part_payload)
    if kind == "parameter":
        data["document"]["parameters"][private_id] = {"value": "not-a-number"}
    elif kind == "source":
        model = b"private-model"
        data["document"]["sources"] = {
            private_id: {
                "type": "private_kind",
                "path": "sources/model.stl",
                "sha256": hashlib.sha256(model).hexdigest(),
                "embedded": True,
                "ingest": {},
            }
        }
        data["payloads"] = {private_id: base64.b64encode(model).decode("ascii")}
    else:
        data["document"]["ops"][0]["matches"] = {
            private_id: {
                "kind": "private_kind",
                "relative": [0.0, 0.0, 0.0],
                "axis": [0.0, 0.0, 1.0],
                "diameter": 1.0,
                "directional": False,
            }
        }

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    serialized = json.dumps(raised.value.as_dict(), ensure_ascii=False, sort_keys=True)
    assert private_id not in raised.value.field
    assert private_id not in serialized


@pytest.mark.parametrize(
    ("location", "key"),
    (("document", "code"), ("operation", "extra_setting")),
)
def test_unknown_nested_fields_are_rejected(
    part_payload: bytes,
    location: str,
    key: str,
) -> None:
    data = json.loads(part_payload)
    if location == "document":
        data["document"][key] = "hidden"
    else:
        data["document"]["ops"][0]["params"][key] = 1

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.constraint == "recipe_format"


@pytest.mark.parametrize(
    ("location", "value"),
    (
        ("scene", []),
        ("numbering", []),
        ("features", []),
        ("exposed_name", []),
        ("op_id", True),
        ("op_in", "obj_1"),
        ("op_solver", []),
        ("op_seed", True),
        ("op_matches", []),
        ("op_translatable", "name"),
        ("parameter_value", "20"),
        ("parameter_unit", []),
        ("parameter_title", []),
        ("parameter_expression", []),
        ("parameter_minimum", True),
        ("parameter_translatable", 1),
        ("fits", {}),
        ("transactions", False),
        ("chat", ""),
        ("print_settings", {}),
        ("range_report", []),
        ("range_failures", {}),
    ),
)
def test_softly_coerced_nested_fields_are_rejected(
    part_payload: bytes,
    location: str,
    value: object,
) -> None:
    data = json.loads(part_payload)
    operation = data["document"]["ops"][0]
    parameter = data["document"]["parameters"]["width"]
    if location in {"scene", "numbering"}:
        data["document"][location] = value
    elif location == "features":
        data["features"]["top"] = value
    elif location == "exposed_name":
        data["exposed"][0]["name"] = value
    elif location.startswith("op_"):
        operation[location.removeprefix("op_")] = value
    elif location.startswith("parameter_"):
        key = {
            "parameter_value": "value",
            "parameter_unit": "unit",
            "parameter_title": "title",
            "parameter_expression": "expression",
            "parameter_minimum": "min",
            "parameter_translatable": "title_translatable",
        }[location]
        parameter[key] = value
    elif location in {"fits", "transactions", "chat", "print_settings"}:
        data["document"][location] = value
    elif location == "range_report":
        data["range_report"] = value
    else:
        data["range_report"] = {"checked": 1, "failures": value}

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


def test_duplicate_operation_ids_and_invalid_exposed_ranges_are_rejected(
    part_payload: bytes,
) -> None:
    data = json.loads(part_payload)
    duplicate = dict(data["document"]["ops"][0])
    duplicate["out"] = ["obj_2"]
    data["document"]["ops"].append(duplicate)
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())
    assert raised.value.constraint == "recipe_format"

    data = json.loads(part_payload)
    data["exposed"][0]["default"] = 500.0
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())
    assert raised.value.constraint == "recipe_format"

    data = json.loads(part_payload)
    data["exposed"][0]["name"] = "fehlt"
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())
    assert raised.value.constraint == "recipe_format"


@pytest.mark.parametrize("location", ("solver_strategy", "match_name", "match_kind"))
def test_solver_and_match_identifiers_have_a_hard_length_limit(
    part_payload: bytes,
    location: str,
) -> None:
    data = json.loads(part_payload)
    operation = data["document"]["ops"][0]
    oversized = "x" * (shared.MAX_TITLE_CHARS + 1)
    fingerprint = {
        "kind": "face",
        "relative": [0.0, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "diameter": 1.0,
        "directional": False,
    }
    if location == "solver_strategy":
        operation["solver"] = {
            "strategy": oversized,
            "attempted": [],
            "seed": None,
            "note": None,
        }
    elif location == "match_name":
        operation["matches"] = {oversized: fingerprint}
    else:
        operation["matches"] = {"face_top": {**fingerprint, "kind": oversized}}

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


@pytest.mark.parametrize("location", ("solver_strategy", "solver_attempted", "match_kind"))
def test_solver_and_match_kinds_use_the_registered_closed_vocabulary(
    part_payload: bytes,
    location: str,
) -> None:
    data = json.loads(part_payload)
    operation = data["document"]["ops"][0]
    if location.startswith("solver_"):
        operation["solver"] = {
            "strategy": "unknown" if location == "solver_strategy" else "direct",
            "attempted": ["unknown"] if location == "solver_attempted" else [],
            "seed": None,
            "note": None,
        }
    else:
        operation["matches"] = {
            "face_top": {
                "kind": "unknown",
                "relative": [0.0, 0.0, 0.0],
                "axis": [0.0, 0.0, 1.0],
                "diameter": 1.0,
                "directional": False,
            }
        }

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


def test_registered_solver_and_match_kinds_remain_valid(part_payload: bytes) -> None:
    data = json.loads(part_payload)
    operation = data["document"]["ops"][0]
    operation["solver"] = {
        "strategy": "direct",
        "attempted": ["direct"],
        "seed": None,
        "note": None,
    }
    operation["matches"] = {
        "face_top": {
            "kind": "face",
            "relative": [0.0, 0.0, 0.0],
            "axis": [0.0, 0.0, 1.0],
            "diameter": 1.0,
            "directional": False,
        }
    }

    parsed = PartFileIO().validate(json.dumps(data).encode())

    assert parsed.document.ops[0].solver is not None
    assert parsed.document.ops[0].solver.strategy == "direct"
    assert parsed.document.ops[0].matches["face_top"]["kind"] == "face"


def test_duplicate_json_keys_and_unreferenced_payloads_are_rejected(
    part_payload: bytes,
) -> None:
    duplicated = part_payload.replace(
        b'"name": "pruefwuerfel",',
        b'"name": "x",\n  "name": "pruefwuerfel",',
    )
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(duplicated)
    assert raised.value.constraint == "recipe_format"
    assert raised.value.values["reason"] == "invalid_json"

    data = json.loads(part_payload)
    data["payloads"]["hidden"] = "aGVsbG8="
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "payloads"


@pytest.mark.parametrize("location", ["operation", "parameter", "top_level"])
def test_foreign_keys_never_echo_private_paths(
    part_payload: bytes,
    location: str,
) -> None:
    """Ungültige fremde Kennungen werden neutral statt als private Daten gemeldet."""

    private = r"C:\Users\Robert\private\secret.py"
    data = json.loads(part_payload)
    operation = data["document"]["ops"][0]
    if location == "operation":
        operation["op"] = private
    elif location == "parameter":
        operation["params"][private] = operation["params"].pop("width")
    else:
        data[private] = True

    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(payload)

    public_error = json.dumps(raised.value.as_dict(), ensure_ascii=False, default=str)
    assert private not in public_error
    assert "Robert" not in public_error


def test_resource_limit_never_echoes_a_private_parameter_key(part_payload: bytes) -> None:
    """Auch die frühe Größenprüfung nennt nur den neutralen Parameterpfad."""

    private = "customer_secret_" + "x" * 160
    data = json.loads(part_payload)
    data["document"]["ops"][0]["params"][private] = "x" * (shared.MAX_VALUE_CHARS + 1)

    with pytest.raises(ValidationError, match="Komplexitätsgrenzen") as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.field == "ops.0.params"
    assert private not in json.dumps(raised.value.as_dict(), default=str)


def test_source_mismatch_never_echoes_a_valid_private_identifier(
    part_payload: bytes,
) -> None:
    """Eine syntaktisch gültige Quellenkennung bleibt auch im Abgleich privat."""

    private = "customer_project_secret_draft"
    data = json.loads(part_payload)
    data["payloads"][private] = "aGVsbG8="

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    public_error = json.dumps(raised.value.as_dict(), default=str)
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "payloads"
    assert raised.value.values["count"] == 1
    assert private not in public_error


@pytest.mark.parametrize("container", ("sources", "payloads"))
@pytest.mark.parametrize(
    "private_id",
    (
        r"C:\Users\Robert\secret.stl",
        "/Users/robert/secret.stl",
        r"\\server\private\secret.stl",
    ),
)
def test_duplicate_private_ids_are_never_reflected_by_the_json_parser(
    part_payload: bytes,
    container: str,
    private_id: str,
) -> None:
    """Doppelte Fremdschlüssel dürfen nicht zum Pfadkanal im Fehler werden."""

    data = json.loads(part_payload)
    encoded_id = json.dumps(private_id)
    payload = json.dumps(data)
    if container == "sources":
        payload = payload.replace(
            '"sources": {}',
            f'"sources": {{{encoded_id}: {{}}, {encoded_id}: {{}}}}',
            1,
        )
    else:
        payload = payload.replace(
            '"payloads": {}',
            f'"payloads": {{{encoded_id}: "", {encoded_id}: ""}}',
            1,
        )

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(payload.encode("utf-8"))

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert raised.value.values["reason"] == "invalid_json"
    assert private_id not in str(raised.value)
    assert all(private_id not in str(value) for value in raised.value.values.values())


def test_resource_limits_stop_before_recipe_build(
    part_payload: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = json.loads(part_payload)
    template = data["document"]["ops"][0]
    data["document"]["ops"] = [
        {**template, "id": index, "out": [f"obj_{index}"]}
        for index in range(shared.MAX_OPERATIONS + 1)
    ]
    built = False

    def forbidden_build(*_args: object, **_kwargs: object) -> None:
        nonlocal built
        built = True
        raise AssertionError("Ein übergroßes Rezept wurde gebaut.")

    monkeypatch.setattr(recipe, "build", forbidden_build)

    with pytest.raises(ValidationError, match="Komplexitätsgrenzen") as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert built is False
    assert raised.value.values["field"] == "ops"


def test_unexpected_recipe_build_errors_are_not_reported_as_invalid_files(
    part_payload: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interne Defekte gehören an die zentrale Fehlergrenze, nicht zum Nutzer."""

    def broken_build(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("interner Testdefekt")

    monkeypatch.setattr(recipe, "build", broken_build)

    with pytest.raises(RuntimeError, match="interner Testdefekt"):
        PartFileIO().validate(part_payload)


@pytest.mark.parametrize("location", ("root", "nested_value", "nested_key"))
def test_invalid_unicode_scalars_are_rejected_early(
    part_payload: bytes,
    location: str,
) -> None:
    data = json.loads(part_payload)
    if location == "root":
        data["title"] = "\ud800"
    elif location == "nested_value":
        data["document"]["scene"]["material"] = "\udfff"
    else:
        data["document"]["scene"]["\ud800"] = "Wert"

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode("utf-8"))

    assert raised.value.suggestions


def test_deep_json_is_rejected_without_recursion_error(part_payload: bytes) -> None:
    data = json.loads(part_payload)
    prefix = json.dumps(data)[:-1].encode()
    nested = prefix + b',"extra":' + b"[" * 5_000 + b"]" * 5_000 + b"}"

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(nested)

    assert raised.value.constraint == "json_depth"


def test_payload_hash_and_source_origin_are_strict(part_payload: bytes) -> None:
    data: dict[str, Any] = json.loads(part_payload)
    data["document"]["sources"] = {
        "src_1": {
            "type": "generated",
            "path": "sources/model.stl",
            "sha256": "0" * 64,
            "embedded": True,
            "ingest": {},
            "origin": {"url": "file:///private/model.stl"},
        }
    }
    data["payloads"]["src_1"] = "aGVsbG8="

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions


@pytest.mark.parametrize(
    "url",
    (
        "file:///private/model.stl",
        "https://user:pass@example.invalid/model.stl",
    ),
)
def test_source_origin_rejects_local_urls_and_credentials(
    part_payload: bytes,
    url: str,
) -> None:
    """Herkunftsmetadaten dürfen weder lokale Pfade noch Zugangsdaten verraten."""

    data: dict[str, Any] = json.loads(part_payload)
    model = b"hello"
    data["document"]["sources"] = {
        "src_1": {
            "type": "generated",
            "path": "sources/model.stl",
            "sha256": hashlib.sha256(model).hexdigest(),
            "embedded": True,
            "ingest": {},
            "origin": {"url": url},
        }
    }
    data["payloads"]["src_1"] = "aGVsbG8="

    with pytest.raises(ValidationError) as raised:
        PartFileIO().validate(json.dumps(data).encode())

    assert raised.value.suggestions
    assert raised.value.constraint == "recipe_format"
    assert raised.value.field == "sources.origin.url"
