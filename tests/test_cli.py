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


def test_import_reads_every_format_the_window_reads(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """„Dieses Dateiformat kann nicht gelesen werden." war eine Unwahrheit.

    Das Fenster entscheidet an der Endung: STEP nimmt den exakten Kern, eine
    flache Zeichnung wird extrudiert, alles andere ist ein Netz. Die
    Kommandozeile legte immer ``load`` auf den Stapel — und antwortete deshalb
    auf STEP, SVG und DXF, das Format sei nicht lesbar. Dieselbe Anwendung liest
    alle drei.

    Die Entscheidung steht jetzt im Kern (``ingest.plan``), und beide Aufrufer
    fragen dort: zwei Wege können nicht mehr auseinanderlaufen. Geprüft wird mit
    einem SVG, weil es sich ohne Fremdbibliothek erzeugen lässt — für STEP
    genügt die Zusicherung, dass der Plan dorthin führt.
    """
    from app.core.ingest.plan import import_plan

    drawing = tmp_path / "platte.svg"
    drawing.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        '<rect x="0" y="0" width="40" height="20"/></svg>',
        encoding="utf-8",
    )
    path = tmp_path / "projekt.p3d"
    main(["new", str(path), "--printer", "centauri-carbon-2", "--material", "petg"])
    capsys.readouterr()

    assert main(["import", str(path), str(drawing)]) == 0, capsys.readouterr().err

    project = load(path)
    assert [entry.op for entry in project.document.ops] == ["load_outline"]
    assert str(project.document.transactions[-1].title) == "Zeichnung extrudieren"

    # Und der Weg für STEP und DXF, ohne dafür eine Datei zu brauchen: geprüft
    # wird die Entscheidung, nicht der Leser dahinter.
    assert import_plan("src_1", "teil.step", b"").draft.op == "load_step"
    assert import_plan("src_1", "zeichnung.dxf", b"").draft.op == "load_outline"
    assert import_plan("src_1", "modell.stl", b"").draft.op == "load"

    # Die Einheitenfrage hat nur ein Netz: STEP trägt seine Einheit selbst, und
    # eine Zeichnung hat keine dritte Dimension, bis jemand sie angibt.
    assert not import_plan("src_1", "teil.step", b"").asks_unit
    assert not import_plan("src_1", "platte.svg", b"").asks_unit
    assert import_plan("src_1", "modell.stl", b"").asks_unit


def test_a_write_that_cannot_work_says_so_instead_of_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein Stapelabzug ist im Nutzerdialog verboten (§2.7, §33.1).

    Der Schreiber im Kern ließ jeden ``OSError`` weiterlaufen. Ein Export in
    ein Ziel, das schon eine Datei ist, endete deshalb mit
    ``FileExistsError [WinError 183]`` und einem Stapelabzug — ohne einen
    Hinweis, was jetzt hilft.

    Im Fenster war derselbe Fehler stiller und schlimmer: Der Export-Arbeiter
    fängt ``AppError``, ein ``OSError`` riss den Thread ab, und danach geschah
    gar nichts mehr. Behoben ist er deshalb im Kern, nicht in einer der beiden
    Oberflächen.
    """
    path = tmp_path / "projekt.p3d"
    main(["new", str(path), "--printer", "centauri-carbon-2", "--material", "petg"])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    capsys.readouterr()

    code = main(["export", str(path), str(blocker)])

    printed = capsys.readouterr()
    assert code == 1
    assert "Traceback" not in printed.err
    assert "schreiben" in printed.err, printed.err
    assert "  - " in printed.err, "und ein Ausweg steht dabei"


def test_a_mistyped_operation_gets_a_suggestion_not_a_wall(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Vierundachtzig Namen, zweimal, englisch, ohne Vorschlag.

    argparse antwortete auf ``run drill_hol`` mit der vollen Liste — einmal in
    der Nutzungszeile, einmal in der Fehlermeldung. Zwei Bildschirme Text auf
    einen fehlenden Buchstaben, und kein Wort dazu, was gemeint sein könnte.
    """
    code = main(["run", "drill_hol", "irgendwas.p3d"])

    printed = capsys.readouterr()
    assert code == 1
    assert "drill_hole" in printed.err, "der naheliegende Name fehlt"
    assert printed.err.count("insert_") == 0, "die ganze Liste steht wieder da"
    assert "solidon3d ops" in printed.err, "und der Weg zur Liste, wer sie will"


def test_an_error_carries_its_numbers_into_the_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """„Dieses Objekt gibt es nicht" ohne die Liste der Objekte ist halb.

    Die Zahlen stehen im Fehler und kamen hier nie an; das Fenster zeigt sie
    seit je. Mit den Schlüsseln, nicht mit Beschriftungen: die Tabelle dafür
    zieht Qt mit, und die Kommandozeile läuft ohne.
    """
    path = tmp_path / "projekt.p3d"
    main(["new", str(path), "--printer", "centauri-carbon-2", "--material", "petg"])
    main(["import", str(path), str(MESHES / "cube_clean.stl")])
    capsys.readouterr()

    assert main(["export", str(path), str(tmp_path / "aus"), "--on", "obj_9"]) == 1

    printed = capsys.readouterr().err
    assert "obj_9" in printed, "das angefragte Objekt fehlt"
    assert "obj_1" in printed, "und die, die es gibt, auch"


def test_a_swapped_path_says_the_order_instead_of_listing_operations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Der häufigste Fehler ist kein Tippfehler, sondern die Reihenfolge.**

    ``new``, ``info``, ``import``, ``undo`` und ``export`` nehmen den Pfad
    zuerst — ``run`` nimmt die Operation zuerst. Wer das verwechselt, las
    „Diese Operation gibt es nicht: C:/…/halter.p3d" und daneben den Vorschlag,
    sich die Operationen auflisten zu lassen: beides wahr und beides nutzlos.
    Gefunden beim Nachfahren der Kommandozeile aus Kundensicht.
    """
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    capsys.readouterr()

    assert main(["run", str(path), "create_box", "--width", "40"]) == 1

    gesagt = capsys.readouterr().err
    assert "Dateipfad" in gesagt
    assert "Operation zuerst" in gesagt, "Regel 17: was jetzt hilft"
    assert "solidon3d ops" not in gesagt, "der alte Vorschlag passt hier nicht"


def test_a_real_typo_still_gets_suggestions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Die neue Erkennung darf die alte nicht verdecken."""
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    capsys.readouterr()

    assert main(["run", "create_bo", str(path)]) == 1

    gesagt = capsys.readouterr().err
    assert "Gemeint war vielleicht" in gesagt
    assert "create_box" in gesagt


def test_the_right_order_just_works(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Und der richtige Aufruf bleibt richtig."""
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    capsys.readouterr()

    assert main(["run", "create_box", str(path), "--width", "40"]) == 0
