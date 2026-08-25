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


def test_the_cli_speaks_the_settings_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Die Kommandozeile liest dieselbe Sprachwahl wie das Fenster.

    Vorher installierte sie nie eine Sprache: Ein spanischer Kunde bekam
    deutsche Hilfe- und Fehlertexte, obwohl die Übersetzungen längst in den
    Katalogen liegen.
    """
    from app.cli import main as cli
    from app.i18n import SOURCE_LANGUAGE, get_language, set_language

    (tmp_path / "settings.json").write_text('{"language": "en"}', encoding="utf-8")
    monkeypatch.setattr(cli, "user_config_dir", lambda: tmp_path)
    try:
        assert main(["ops"]) == 0
        assert get_language() == "en"
        assert "There is no such operation" not in capsys.readouterr().err
    finally:
        set_language(SOURCE_LANGUAGE)


def test_the_first_run_speaks_the_language_from_the_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der allererste Aufruf, und nur er: Es gibt noch keine ``settings.json``.

    Der Installer fragt sechs Sprachen ab und legt die Wahl neben die
    Anwendung. Gelesen hat sie nur das Fenster — ``installed_language`` lag in
    ``app/ui``, und der Kern darf das nicht anfassen (Regel 1). Ein spanischer
    Kunde bekam damit bei seinem ersten Aufruf deutsche Ausgabe, obwohl er die
    Frage längst beantwortet hatte.

    Geprüft wird die **übersetzte Ausgabe** und nicht ``get_language()``:
    Laden und Aktivieren sind zwei Schritte, und ein gesetztes Kürzel ohne
    geladenen Katalog gibt weiter deutsche Texte aus.
    """
    from app.i18n import SOURCE_LANGUAGE, set_language
    from app.i18n.catalog import install_language

    beside_the_app = tmp_path / "app"
    beside_the_app.mkdir()
    (beside_the_app / "install-language.txt").write_text("es", encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    assert not (config / "settings.json").exists(), "der erste Start hat keine Einstellungen"

    # Die gebaute Anwendung liegt neben ihrer Datei — derselbe Weg, den
    # ``installed_language`` im Paket geht, ohne in den Quellbaum zu schreiben.
    monkeypatch.setattr("app.cli.main.user_config_dir", lambda: config)
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(beside_the_app / "solidon3d.exe"))
    try:
        assert main(["profiles"]) == 0
        printed = capsys.readouterr().out
        # Die Überschrift, nicht irgendein Vorkommen: „Drucker" steht auch im
        # Titel eines Profils („Allgemeiner FDM-Drucker"), und der wird nicht
        # übersetzt.
        assert printed.splitlines()[0] == "Impresora", (
            f"deutsche Ausgabe trotz Installer-Wahl: {printed[:80]!r}"
        )
        assert "Valor de partida" in printed or "calibrado" in printed
    finally:
        install_language(SOURCE_LANGUAGE)
        set_language(SOURCE_LANGUAGE)


def test_a_broken_settings_file_does_not_take_the_start_with_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``null`` und ``[]`` sind gültiges JSON und kein Objekt.

    ``json.loads(raw).get(...)`` warf darauf ``AttributeError`` — und zwar
    **vor** dem ``try`` des Hauptprogramms, also als roher Stapelabzug für eine
    Datei, die niemand von Hand geschrieben hat.
    """
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr("app.cli.main.user_config_dir", lambda: config)
    for content in ("null", "[]", '{"language": 7}', "kein JSON"):
        (config / "settings.json").write_text(content, encoding="utf-8")
        assert main(["ops"]) == 0, f"an {content!r} gescheitert"
        capsys.readouterr()


def test_a_recipe_that_will_not_load_says_which_one_and_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§2.7 gilt auch für einen Befund beim Start.

    Gedruckt wurde allein ``message`` — „Ein eigenes Rezept ließ sich nicht
    laden." ohne Dateinamen und ohne Grund, obwohl der Befund beides trägt.
    Der Kunde durchsuchte danach seinen Bausteinordner von Hand.
    """
    from app.cli import main as cli
    from app.core.types import Finding

    broken = Finding(
        code="parts.recipe_failed",
        severity="warning",
        message="Ein eigenes Rezept ließ sich nicht laden.",
        values={"file": "halter.json", "reason": "Zeile 3: unbekannte Operation"},
    )
    monkeypatch.setattr(cli, "load_user_parts", lambda: (broken,))

    assert main(["ops"]) == 0
    said = capsys.readouterr().err

    assert "halter.json" in said, "ohne den Namen sucht der Kunde die Datei selbst"
    assert "Zeile 3: unbekannte Operation" in said


def test_an_unexpected_error_ends_in_a_sentence_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Das letzte Netz der Kommandozeile (Regel 17).

    Sechs naheliegende Fehlerpfade enden sauber — ein unerwarteter erreichte
    den Kunden als roher Stapelabzug. Jetzt gibt es einen Satz, den Grund und
    einen Berichtsordner; gesendet wird nichts.
    """
    from app.cli import main as cli

    def explode(_args: object) -> int:
        raise RuntimeError("kaputt auf neue Art")

    monkeypatch.setattr(cli, "command_ops", explode)
    code = main(["ops"])
    said = capsys.readouterr().err
    assert code != 0
    assert "Traceback" not in said
    assert "kaputt auf neue Art" in said
    assert "bericht-" in said, "der Berichtsordner wird genannt"


def test_even_a_report_that_cannot_be_written_leaves_a_way_out(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regel 17 am letzten Netz: Ein volles oder schreibgeschütztes Profil
    hinterließ ``except OSError: pass`` — Satz, Grund, und danach nichts.

    Das ist genau die Lage, in der ein Kunde etwas braucht: Der Bericht, der
    sonst alles erklärt, ist gerade der, der fehlt. Übrig bleiben das
    Protokoll, das schon geschrieben ist, und eine Adresse.
    """
    from app.branding import SUPPORT_ADDRESS
    from app.cli import main as cli
    from app.core import report

    def explode(_args: object) -> int:
        raise RuntimeError("kaputt auf neue Art")

    def refuse(_report: object) -> object:
        raise OSError("Kein Platz auf dem Gerät")

    monkeypatch.setattr(cli, "command_ops", explode)
    monkeypatch.setattr(report, "write", refuse)

    code = main(["ops"])
    said = capsys.readouterr().err

    assert code != 0
    assert "Traceback" not in said
    assert "Kein Platz auf dem Gerät" in said, "der Grund gehört dazu"
    assert SUPPORT_ADDRESS in said, "ein Fehler endet nie ohne einen nächsten Schritt"
    assert "logs" in said.replace(chr(92), "/").lower(), "das Protokoll wird beim Pfad genannt"


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
            op="split_pinned",
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
