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


def test_a_question_nobody_can_answer_ends_in_a_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """In einer Pipe, einem Skript oder auf einem Bauserver liest ``input``
    sofort EOF — und das ist der Normalfall, nicht die Ausnahme.

    Ungefangen endete die Einheitenfrage dort in einem Stapelabzug, also genau
    der Ausgabe, die §33.1 dem Nutzer erspart. Der Ausweg steht direkt daneben:
    „--unit" beantwortet dieselbe Frage vorab.
    """

    def no_one(prompt: str = "") -> str:
        raise EOFError

    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    monkeypatch.setattr("builtins.input", no_one)

    assert main(["import", str(path), str(MESHES / "bracket_inch.stl")]) != 0

    said = capsys.readouterr()
    text = said.out + said.err
    assert "--unit" in text, "der Ausweg wird genannt"
    assert "Traceback" not in text


def test_the_same_import_works_when_the_unit_is_given(tmp_path: Path) -> None:
    """Und derselbe Aufruf geht durch, sobald die Antwort mitkommt."""
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])

    assert main(["import", str(path), str(MESHES / "bracket_inch.stl"), "--unit", "in"]) == 0
    assert load(path).document.ops[0].params["unit"] == "in"


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


def test_export_refuses_a_halted_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Eine halbe Datei mit ganzem Namen ist schlimmer als keine — sie wird gedruckt.

    ``command_export`` wertete aus und schrieb das Ergebnis ungeprüft. Hält die
    Kette bei einer Operation an, enthält die Szene den Stand davor: Der Export
    schrieb ihn, meldete „Geschrieben: …" und gab 0 zurück. ``info`` sagte den
    Halt seit je — nur der Befehl, der etwas herausgibt, sah nicht hin.

    Die anhaltende Operation ist hier eine Schnittebene, die den Körper nicht
    trifft: 500 mm über einem 20-mm-Würfel.
    """
    path = tmp_path / "projekt.p3d"
    main(["new", str(path), "--printer", "centauri-carbon-2", "--material", "petg"])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    # Über das Register angelegt, nicht über ``run``: der Befehl wertet selbst
    # aus und würde den Halt schon dort melden. Geprüft werden soll der Export
    # auf einem Projekt, das den Halt **enthält**.
    from app.core.scene.project import save
    from app.core.types import Operation

    project = load(path)
    project.document.ops.append(
        Operation(
            id=99,
            op="split_plane",
            inputs=("obj_1",),
            params={"axis": "z", "position": 500.0},
        )
    )
    save(project, path)
    capsys.readouterr()

    code = main(["export", str(path), str(tmp_path / "out")])

    assert code == 1, "ein Export aus einer angehaltenen Kette ist kein Erfolg"
    printed = capsys.readouterr()
    assert "Nichts geschrieben" in printed.err
    assert "hält" in printed.out, "und der Bericht sagt, wo die Kette stehen bleibt"
    assert not list((tmp_path / "out").glob("*")), "geschrieben wurde wirklich nichts"
