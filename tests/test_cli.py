"""Die Kommandozeile liest dasselbe Register wie jede andere
Oberfläche (§10).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cli.main import main
from app.core.registry import REGISTRY
from app.core.scene.project import load

MESHES = Path(__file__).parent / "data" / "meshes"


def test_every_operation_is_reachable_from_the_command_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["ops"]) == 0
    printed = capsys.readouterr().out
    for spec in REGISTRY.all():
        assert spec.name in printed


def test_the_reference_is_generated_not_written(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs"]) == 0
    printed = capsys.readouterr().out
    assert "`load`" in printed
    assert "`rename_object`" in printed


def test_the_profile_list_shows_the_starting_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profiles"]) == 0
    printed = capsys.readouterr().out
    assert "centauri-carbon-2" in printed
    assert "256 x 256 x 256 mm" in printed
    assert "petg" in printed


def test_a_new_project_is_created_and_opens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    assert main(["new", str(path), "--printer", "centauri-carbon-2", "--material", "petg"]) == 0
    assert path.is_file()

    project = load(path)
    assert project.document.printer == "centauri-carbon-2"
    assert project.document.material == "petg"


def test_importing_a_model_lands_in_the_stack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    capsys.readouterr()

    assert main(["import", str(path), str(MESHES / "cube_clean.stl")]) == 0

    project = load(path)
    assert [entry.op for entry in project.document.ops] == ["load"]
    assert project.document.ops[0].params["unit"] == "mm", "a certain unit is stored, not asked"
    assert project.sources["src_1"], "the source travels inside the container"


def test_an_ambiguous_unit_is_asked_once_and_then_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    monkeypatch.setattr("builtins.input", lambda prompt="": "in")

    assert main(["import", str(path), str(MESHES / "bracket_inch.stl")]) == 0

    project = load(path)
    assert project.document.ops[0].params["unit"] == "in"

    # Eine zweite Auswertung darf nicht noch einmal fragen.
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked twice"))
    assert main(["info", str(path)]) == 0
    assert "101.6" in capsys.readouterr().out


def test_info_describes_the_evaluated_scene(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    capsys.readouterr()

    assert main(["info", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "cube_clean" in printed
    assert "20.0 x 20.0 x 20.0 mm" in printed
    assert "12" in printed


def test_an_operation_runs_from_the_registry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    capsys.readouterr()

    assert main(["run", "rename_object", str(path), "--on", "obj_1", "--name", "Deckel"]) == 0

    project = load(path)
    assert project.document.ops[-1].op == "rename_object"
    assert project.document.ops[-1].params["name"] == "Deckel"


def test_undo_takes_back_the_last_transaction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    main(["run", "rename_object", str(path), "--on", "obj_1", "--name", "Deckel"])
    capsys.readouterr()

    assert main(["undo", str(path)]) == 0
    assert [entry.op for entry in load(path).document.ops] == ["load"]

    assert main(["undo", str(path)]) == 0
    assert load(path).document.ops == []
    assert main(["undo", str(path)]) == 1


def test_an_error_states_what_is_possible_now(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["info", str(tmp_path / "gibtsnicht.p3d")]) == 1
    printed = capsys.readouterr().err
    assert "Projektdatei" in printed
    assert "-" in printed, "the suggestions are listed, not just the failure"
