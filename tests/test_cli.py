"""Die Kommandozeile liest dasselbe Register wie jede andere
Oberfläche (§10).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.cli.main import main
from app.core.registry import REGISTRY
from app.core.scene.project import load
from app.i18n.catalog import available_languages

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture(autouse=True)
def keep_command_unit_tests_inside_the_test_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prozessweite Hooks prüfen die echten Unterprozesse; Befehlstests ändern pytest nicht."""
    monkeypatch.setattr("app.cli.main.install_crash_logging", lambda: None)


def test_every_operation_is_reachable_from_the_command_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["ops"]) == 0
    printed = capsys.readouterr().out
    for spec in REGISTRY.all():
        assert spec.name in printed


@pytest.mark.parametrize("language", available_languages())
def test_cli_labels_keep_catalogue_punctuation_and_raw_values(
    language: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der echte Infobefehl erhält Kennungen, Pfadname und die drei Trenner."""
    import argparse
    from types import SimpleNamespace

    from app.cli import main as cli
    from app.core.scene.project import new_project
    from app.core.types import Scene
    from app.i18n import get_language, set_language, tr
    from app.i18n.catalog import install_language

    previous = get_language()
    install_language(language)
    set_language(language)
    try:
        project = new_project("Printer:12.5", "Material:PETG")
        result = SimpleNamespace(scene=Scene(), stopped_at=None, complete=True)
        monkeypatch.setattr(cli, "open_project", lambda _path: project)
        monkeypatch.setattr(cli, "run_evaluation", lambda *_args, **_kwargs: result)
        path = Path("pieces/12.5_box.p3d")
        assert cli.command_info(argparse.Namespace(path=str(path))) == 0
        lines = capsys.readouterr().out.splitlines()
        separator = " : " if language == "fr" else ": "
        assert lines[0] == tr("Projekt: {name}", name=path.name)
        assert lines[1] == (
            tr("Drucker")
            + separator
            + "Printer:12.5   "
            + tr("Material")
            + separator
            + "Material:PETG   "
            + tr("Format")
            + separator
            + str(project.document.format_version)
        )
        if language == "fr":
            assert lines[0] == "Projet : 12.5_box.p3d"
    finally:
        set_language(previous)


def test_french_cli_recovery_keeps_raw_paths_and_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pfadfehler und unbekannte Operation zeigen die echten unveränderten Befehle."""
    from app.cli import main as cli
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    previous = get_language()
    install_language("fr")
    set_language("fr")
    try:
        path = "pieces/12.5_box.stl"
        assert cli._mistyped_operation(["run", path]) == 1
        assert capsys.readouterr().err == (
            "\nCeci est un chemin de fichier, pas une opération : "
            + path
            + "\n  - Avec «run», l'opération vient d'abord, le chemin ensuite : "
            "solidon3d run create_box <pfad>\n"
        )
        assert cli._mistyped_operation(["run", "zz_unregistered:12.5"]) == 1
        assert capsys.readouterr().err == (
            "\nCette opération n'existe pas : zz_unregistered:12.5\n"
            "  - Lister toutes les opérations : solidon3d ops\n"
        )
    finally:
        set_language(previous)


def test_french_terminal_choice_keeps_range_spacing_and_selected_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der tatsächliche input-Aufruf übersetzt auch den nummerierten Präfix."""
    from app.cli import main as cli
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return "2"

    previous = get_language()
    install_language("fr")
    set_language("fr")
    monkeypatch.setattr("builtins.input", answer)
    try:
        assert cli.terminal_ask("Quelle pièce ?", ["piece:1.5", "piece:2.5"]) == "piece:2.5"
        assert prompts == ["Sélection [1-2] : "]
    finally:
        set_language(previous)


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
        assert "valores de partida" in printed or "calibrado" in printed
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


def test_importing_a_zip_asks_which_model_and_embeds_only_that(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein ZIP von der Modellseite: gewählt wird im Terminal, eingebettet das Modell."""
    import zipfile

    archive = tmp_path / "teile.zip"
    with zipfile.ZipFile(archive, "w") as container:
        container.writestr("boden.stl", (MESHES / "cube_clean.stl").read_bytes())
        container.writestr("deckel.stl", (MESHES / "cube_clean.stl").read_bytes())
        container.writestr("anleitung.pdf", b"%PDF")
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    assert main(["import", str(path), str(archive)]) == 0

    project = load(path)
    assert [entry.op for entry in project.document.ops] == ["load"]
    source = project.document.sources["src_1"]
    assert source.path.endswith("deckel.stl"), source.path
    assert project.sources["src_1"] == (MESHES / "cube_clean.stl").read_bytes()
    assert "boden.stl" in capsys.readouterr().out, "die Wahl stand im Terminal"


def test_a_zip_in_a_script_names_its_own_way_out_and_takes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ohne Terminal nannte die Absage „--unit" — für die Wahl im ZIP gab es
    keinen Ausweg. ``--entry`` beantwortet die Frage vorab."""
    import zipfile

    def no_one(prompt: str = "") -> str:
        raise EOFError

    archive = tmp_path / "teile.zip"
    with zipfile.ZipFile(archive, "w") as container:
        container.writestr("boden.stl", (MESHES / "cube_clean.stl").read_bytes())
        container.writestr("deckel.stl", (MESHES / "cube_clean.stl").read_bytes())
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    monkeypatch.setattr("builtins.input", no_one)

    assert main(["import", str(path), str(archive)]) != 0
    said = capsys.readouterr()
    assert "--entry" in said.out + said.err
    assert "Traceback" not in said.out + said.err

    assert main(["import", str(path), str(archive), "--entry", "fehlt.stl"]) != 0
    assert "Traceback" not in capsys.readouterr().err

    assert main(["import", str(path), str(archive), "--entry", "deckel.stl"]) == 0
    assert load(path).document.sources["src_1"].path.endswith("deckel.stl")


def test_the_same_import_works_when_the_unit_is_given(tmp_path: Path) -> None:
    """Und derselbe Aufruf geht durch, sobald die Antwort mitkommt."""
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])

    assert main(["import", str(path), str(MESHES / "bracket_inch.stl"), "--unit", "in"]) == 0
    assert load(path).document.ops[0].params["unit"] == "in"


def test_a_file_in_metres_is_not_read_as_inches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein Helm von 0,30 × 0,25 × 0,30 (Meter) kam als Zoll an (RM-420).

    Fenster und Operation fragen, weil die Meter-Lesart unter dem doppelten
    Drucker bleibt; die Kommandozeile rechnete ohne Drucker und nahm still
    Zoll. Jetzt fragt sie wie die Operation — ohne Terminal mit dem Ausweg
    „--unit“, mit ihm richtig.
    """
    import trimesh

    helmet = tmp_path / "helm.stl"
    trimesh.creation.box(extents=(0.30, 0.25, 0.30)).export(helmet)
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])

    def no_one(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", no_one)
    assert main(["import", str(path), str(helmet)]) != 0, "keine stille Lesart"
    said = capsys.readouterr()
    assert "--unit" in said.out + said.err
    assert not load(path).document.ops, "nichts gespeichert"

    assert main(["import", str(path), str(helmet), "--unit", "m"]) == 0
    assert load(path).document.ops[0].params["unit"] == "m"


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


def test_the_same_bytes_under_another_name_keep_their_own_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Durchsicht v0.5.1: Der Test darüber sah „deckel" statt „cube_clean",
    je nachdem, welcher Test vorher lief — ein anderer hatte dieselben Bytes
    als ``deckel.stl`` eingelesen, und der Plattencache kannte nur den Inhalt
    einer Quelle, nicht ihren Namen. Beim Kunden hieß eine umbenannte Kopie
    wie die Datei, die er Tage vorher geöffnet hatte."""
    lid = tmp_path / "deckel.stl"
    lid.write_bytes((MESHES / "cube_clean.stl").read_bytes())
    first = tmp_path / "erstes.p3d"
    main(["new", str(first)])
    main(["import", str(first), str(lid)])
    assert main(["info", str(first)]) == 0
    assert "deckel" in capsys.readouterr().out, "die erste Datei heißt wie sie selbst"

    second = tmp_path / "zweites.p3d"
    main(["new", str(second)])
    main(["import", str(second), str(MESHES / "cube_clean.stl")])
    capsys.readouterr()

    assert main(["info", str(second)]) == 0
    printed = capsys.readouterr().out
    assert "cube_clean" in printed
    assert "deckel" not in printed


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
    assert str(project.document.transactions[-1].title) == "Zeichnung hochziehen"

    # Und der Weg für STEP und DXF, ohne dafür ein echtes Modell zu brauchen:
    # geprüft wird die Entscheidung, nicht der Leser dahinter.
    #
    # **Aber nicht mehr mit leerer Nutzlast.** Seit ``loader.check_readable``
    # steht vor der Weiche eine Eingangsprüfung, und für sie ist eine Datei
    # ohne ein einziges Byte in jedem Format eine Absage — der abgebrochene
    # Download. Ein Kopf genügt: Die Weiche entscheidet an der Endung und
    # liest den Inhalt nicht. **Außer bei STEP, seit P7.4**: Der Plan zählt
    # die Körper der Baugruppe wie bei einer 3MF, also braucht er eine echte
    # Datei — die kleinste des STEP-Korpus.
    knapp_step = (Path(__file__).parent / "data" / "step" / "inch.step").read_bytes()
    knapp_dxf = b"0 SECTION"
    knapp_stl = bytes(80) + struct.pack("<I", 1) + bytes(50)

    assert import_plan("src_1", "teil.step", knapp_step).draft.op == "load_step"
    assert import_plan("src_1", "zeichnung.dxf", knapp_dxf).draft.op == "load_outline"
    assert import_plan("src_1", "modell.stl", knapp_stl).draft.op == "load"

    # Die Einheitenfrage hat nur ein Netz: STEP trägt seine Einheit selbst, und
    # eine Zeichnung hat keine dritte Dimension, bis jemand sie angibt.
    assert not import_plan("src_1", "teil.step", knapp_step).asks_unit
    assert not import_plan("src_1", "platte.svg", drawing.read_bytes()).asks_unit
    assert import_plan("src_1", "modell.stl", knapp_stl).asks_unit


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


EXAMPLES = Path(__file__).parent.parent / "app" / "examples"


@pytest.mark.parametrize("beispiel", sorted(EXAMPLES.glob("*.p3d")), ids=lambda p: p.stem)
def test_info_reads_every_shipped_example(
    beispiel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Jedes ausgelieferte Beispiel muss sich beschreiben lassen.

    Am 29.08.2026 brach ``info`` an **allen neun** mit einem Programmfehler ab:
    ``entry.name`` ist bei Objekten aus Bausteinen ein ``TranslatableText``, und
    der kennt keine Formatbreite. Drei Zeilen darunter stand der richtige Weg
    samt Begründung — ``{transaction.title!s:<28}``, mit dem Kommentar „ein
    übersetzbarer Titel kennt keine Formatbreite". Die Nachbarzeile war ihm
    nicht gefolgt.

    Der bestehende ``info``-Test hat es nicht gesehen, und der Grund ist die
    eigentliche Lehre: Er baut sein Projekt aus einer STL, und dort ist der
    Objektname eine gewöhnliche Zeichenkette. Ein selbst gebautes Projekt
    trifft die Fälle nicht, die ein ausgeliefertes mitbringt.
    """
    assert main(["info", str(beispiel)]) == 0, f"{beispiel.name} bricht ab"
    gedruckt = capsys.readouterr().out
    assert "Objekte" in gedruckt, f"{beispiel.name} beschreibt keine Objekte"
    assert "Verlauf" in gedruckt, f"{beispiel.name} zeigt keinen Verlauf"


def test_a_default_true_switch_can_be_turned_off_from_the_command_line() -> None:
    """Gesamtreview 05.09.2026, CORE-20: Jeder Bool-Parameter bekam nur ein
    ``store_true`` — für ``compensate`` (Vorgabe wahr) gab es keinen Aufruf,
    der es abschaltet; eine Bohrung mit Nennmaß war über die Kommandozeile
    nicht erreichbar. ``--no-compensate`` gibt es jetzt, und nicht gesagt
    bleibt nicht gesagt."""
    from app.cli.main import build_parser

    parser = build_parser()

    assert parser.parse_args(["run", "drill_hole", "x.p3d"]).compensate is None
    assert parser.parse_args(["run", "drill_hole", "x.p3d", "--compensate"]).compensate is True
    assert parser.parse_args(["run", "drill_hole", "x.p3d", "--no-compensate"]).compensate is False


def test_the_command_line_knows_every_parameter_kind() -> None:
    """Jede Art, die das Register kennt, wandelt die Kommandozeile auch.

    **Der Fall** (Robert, 08.09.2026): ``assign_slot`` war über die
    Kommandozeile gar nicht zu benutzen. ``--slot 1`` kam als Zeichenkette an,
    und die Prüfung lehnte mit „Hier wird eine Zahl erwartet" ab.

    Die Ursache war eine zweite Liste. ``_PARAM_TYPES`` zählte die Arten von
    Hand auf, und als ``slot`` die Art ``filament`` bekam, fiel sie über das
    ``.get(..., str)`` in den Textzweig. Es ist derselbe Fehler wie am
    27.08.2026, eine Ebene weiter: Damals wurde ``NUMBER_KINDS`` ergänzt,
    diese Tabelle nicht.

    Geprüft wird deshalb nicht „filament ist eine Zahl" — das wäre wieder eine
    Aufzählung, die altert —, sondern dass **keine** Art fehlt und dass die
    Zahlenarten auch Zahlen liefern.
    """
    from app.cli.main import _PARAM_TYPES
    from app.core.registry.params import LIST_KINDS, NUMBER_KINDS, TEXT_KINDS

    assert NUMBER_KINDS and TEXT_KINDS, "die Mengen kommen aus dem Register, nicht aus dem Nichts"

    fehlend = (NUMBER_KINDS | TEXT_KINDS | LIST_KINDS) - set(_PARAM_TYPES)
    assert not fehlend, f"die Kommandozeile kennt diese Arten nicht: {sorted(fehlend)}"

    for kind in NUMBER_KINDS:
        wert = _PARAM_TYPES[kind]("1")
        assert isinstance(wert, int | float) and not isinstance(wert, str), (
            f"{kind} muss eine Zahl ergeben, ergab {wert!r}"
        )
    for kind in TEXT_KINDS:
        assert _PARAM_TYPES[kind] is str, f"{kind} ist Text"


def test_feature_selection_from_cli_is_a_real_list_and_preserves_legacy_single_mode() -> None:
    """Mehrfachwerte werden einzeln angegeben; alte Einzelwerte und Ganzkörper bleiben möglich."""
    from app.cli.main import build_parser
    from app.core.registry import REGISTRY
    from app.core.registry.params import validate

    parser = build_parser()
    many = parser.parse_args(
        ["run", "clear_filament", "x.p3d", "--at-features", "face_1", "face_2"]
    )
    single = parser.parse_args(["run", "clear_filament", "x.p3d", "--at-feature", "face_1"])
    whole = parser.parse_args(["run", "clear_filament", "x.p3d"])
    assert many.at_features == ["face_1", "face_2"]
    assert many.at_feature is None
    assert single.at_feature == "face_1"
    assert single.at_features is None
    assert whole.at_features is None and whole.at_feature is None
    validated = validate(REGISTRY.get("clear_filament").params, {"at_features": many.at_features})
    assert validated.at_features == ("face_1", "face_2")


def test_assigning_a_filament_works_from_the_command_line(tmp_path: Path) -> None:
    """Und der Weg, an dem es aufgefallen ist, geht wieder.

    Der Test darüber prüft die Tabelle, dieser den Kundenweg: Ein Projekt
    anlegen, ein Modell laden, ein Filament zuweisen. Ohne den Fix hält die
    Kette bei der Zuweisung an.
    """
    from app.cli.main import main

    ziel = tmp_path / "probe.p3d"
    assert main(["new", str(ziel), "--material", "pla"]) == 0
    assert main(["import", str(ziel), str(MESHES / "cube_clean.stl"), "--unit", "mm"]) == 0
    assert main(["run", "assign_slot", str(ziel), "--on", "obj_1", "--slot", "1"]) == 0, (
        "eine Slotnummer ist eine Zahl, auch wenn sie über argparse kommt"
    )


def test_a_part_leaves_as_openscad_with_the_values_it_was_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E8: SCAD-Ausgabe mit den aktuellen Werten, ohne Ausführung (§24.1).

    `to_scad` gab es seit je, einen Weg dorthin nicht — weder Katalog noch
    Kommandozeile. Geschrieben wird eine Datei; ausgeführt wird nichts, und
    seit dem Ausbau von OpenSCAD (26.08.2026) gibt es dorthin auch keinen Weg
    mehr (Regel 11).
    """
    target = tmp_path / "rippe.scad"

    assert (
        main(["scad", "rib", "--set", "length=30", "--set", "height=8", "--out", str(target)]) == 0
    )

    text = target.read_text(encoding="utf-8")
    assert "length = 30.0;" in text, "der gesetzte Wert steht als lesbare Variable darin"
    assert "height = 8.0;" in text
    assert "module rib()" in text and "polyhedron(" in text
    assert "rib();" in text.splitlines()[-1], "die Datei ruft ihr eigenes Modul auf"
    assert str(target) in capsys.readouterr().out


def test_the_scad_command_says_which_parts_there_are(capsys: pytest.CaptureFixture[str]) -> None:
    """Ein Tippfehler endet in einem Satz mit einer Liste, nicht in einem Abzug."""
    assert main(["scad", "gibtsnicht"]) != 0

    printed = capsys.readouterr()
    assert "gibtsnicht" in printed.out + printed.err
    assert "rib" in printed.out + printed.err, "und die bekannten Namen stehen daneben"


def test_a_scad_value_goes_through_the_same_check_as_the_dialog(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Kein zweiter Weg an den Grenzen vorbei: dieselbe `validate`-Prüfung."""
    assert main(["scad", "rib", "--set", "length=99999"]) != 0

    printed = capsys.readouterr()
    assert "300" in printed.out + printed.err, "der Höchstwert des Schemas steht in der Absage"


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_scad_boolean_help_and_values_are_portable_across_languages(
    language: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import json

    from app.core.export import writer
    from app.i18n import SOURCE_LANGUAGE, set_language

    (tmp_path / "settings.json").write_text(json.dumps({"language": language}), encoding="utf-8")
    monkeypatch.setattr("app.cli.main.user_config_dir", lambda: tmp_path)
    seen: list[bool] = []

    def export(spec, values) -> str:
        assert spec.name == "heatset_m4"
        assert isinstance(values.lead_in, bool)
        seen.append(values.lead_in)
        return "// SCAD probe\n"

    monkeypatch.setattr(writer, "export_part_scad", export)
    try:
        with pytest.raises(SystemExit) as caught:
            main(["scad", "--help"])
        assert caught.value.code == 0
        help_text = capsys.readouterr().out
        assert "true/false" in help_text and "1/0" in help_text
        for value in ("true", "false", "1", "0"):
            assert main(["scad", "heatset_m4", "--set", f"lead_in={value}"]) == 0
        assert seen == [True, False, True, False]
        capsys.readouterr()
        assert main(["scad", "heatset_m4", "--set", "lead_in=oui"]) != 0
        error = capsys.readouterr().err
        assert "true" in error and "false" in error and "oui" in error
        assert len(seen) == 4, "invalid Boolean text must not reach the export"
    finally:
        set_language(SOURCE_LANGUAGE)


@pytest.mark.parametrize("raw", ["0", "1"])
def test_scad_numeric_values_are_not_reinterpreted_as_boolean(raw: str) -> None:
    from app.cli.main import _as_value

    value = _as_value(raw)
    assert type(value) is int
    assert value == int(raw)


def _entry_process(tmp_path: Path, entry: str, *, fail_import: bool = False):
    """Fährt den echten Moduleinstieg oder den konfigurierten Skriptaufruf kopflos."""
    import os
    import subprocess
    import sys
    import tomllib

    root = Path(__file__).resolve().parent.parent
    environment = dict(os.environ)
    for key in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
        environment[key] = str(tmp_path)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(root)
    startup = """
import atexit
import sys
atexit.register(lambda: print('HEADLESS=' + str('PySide6' not in sys.modules), flush=True))
"""
    if fail_import:
        startup += """
import importlib.abc
class RefuseImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'app.core.activation':
            raise RuntimeError('Authorization: Bearer beim_laden_geheim')
sys.meta_path.insert(0, RefuseImport())
"""
    (tmp_path / "sitecustomize.py").write_text(startup, encoding="utf-8")
    if entry == "module":
        arguments = ["-m", "app.cli.main", "ops"]
    elif entry == "script":
        configured = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        module, function = configured["project"]["scripts"]["solidon3d"].split(":")
        arguments = [
            "-c",
            f"from {module} import {function}; raise SystemExit({function}())",
            "ops",
        ]
    else:
        arguments = [
            "-c",
            "import sys, threading; "
            "before=(sys.excepthook,threading.excepthook); "
            "import app.cli, app.cli.main; "
            "assert before == (sys.excepthook,threading.excepthook)",
        ]
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )


@pytest.mark.parametrize("entry", ["module", "script"])
@pytest.mark.parametrize("fail_import", [False, True])
def test_both_cli_entries_capture_early_failures_without_loading_qt(
    tmp_path: Path, entry: str, fail_import: bool
) -> None:
    done = _entry_process(tmp_path, entry, fail_import=fail_import)
    assert done.returncode == (1 if fail_import else 0), done.stdout + done.stderr
    assert "HEADLESS=True" in done.stdout
    captures = list(tmp_path.rglob("crash-*.log"))
    assert len(captures) == 1
    written = captures[0].read_text(encoding="utf-8")
    if fail_import:
        assert "RuntimeError" in written and "find_spec" in written
        assert "beim_laden_geheim" not in written + done.stderr
        assert len(list(tmp_path.rglob("bericht.txt"))) == 1
    else:
        assert written == ""
        assert "create_box" in done.stdout


def test_importing_cli_modules_does_not_install_process_hooks(tmp_path: Path) -> None:
    done = _entry_process(tmp_path, "import")
    assert done.returncode == 0, done.stderr
    assert "HEADLESS=True" in done.stdout
    assert not list(tmp_path.rglob("crash-*.log"))


def _drilled_plate(path: Path) -> None:
    """Quader mit zwei Bohrungen und einer Vergrößerung der linken — über die Kommandozeile."""
    assert main(["new", str(path)]) == 0
    assert (
        main(["run", "create_box", str(path), "--width", "80", "--depth", "40", "--height", "10"])
        == 0
    )
    for x, seed in (("-20", "1"), ("20", "2")):
        assert (
            main(
                [
                    "run",
                    "drill_hole",
                    str(path),
                    "--on",
                    "obj_1",
                    "--seed",
                    seed,
                    "--diameter",
                    "5",
                    "--x",
                    x,
                    "--y",
                    "0",
                    "--z",
                    "10",
                    "--depth",
                    "10",
                ]
            )
            == 0
        )


def test_steps_are_switched_off_moved_and_on_again_from_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P7 auf der Kommandozeile: dieselben Handlungen wie im Verlauf, gespeichert nur bei Erfolg."""
    path = tmp_path / "platte.p3d"
    _drilled_plate(path)
    steps = [entry.id for entry in load(path).document.ops]
    assert main(["suppress", str(path), str(steps[1])]) == 0
    resting = {entry.id: entry.suppressed for entry in load(path).document.ops}
    assert resting[steps[1]] is not None and resting[steps[1]].chosen
    assert main(["reactivate", str(path), str(steps[1])]) == 0
    assert all(entry.suppressed is None for entry in load(path).document.ops)

    assert main(["move", str(path), str(steps[2]), "--before", str(steps[1])]) == 0
    moved = load(path).document
    assert [entry.params.get("x") for entry in moved.ops if entry.op == "drill_hole"] == [
        20.0,
        -20.0,
    ]
    assert moved.transactions[-1].revision == "move"


def test_an_invalid_move_leaves_the_file_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein ungültiger Vorschlag ändert nichts — auch nicht an der Datei auf der Platte."""
    path = tmp_path / "platte.p3d"
    _drilled_plate(path)
    before = path.read_bytes()
    steps = [entry.id for entry in load(path).document.ops]
    assert main(["move", str(path), str(steps[1]), "--before", str(steps[0])]) == 1
    assert path.read_bytes() == before
    assert "Schritt" in capsys.readouterr().err


def test_a_step_is_inserted_before_another_from_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P7.1: ``run … --before`` setzt den Schritt vor den genannten, nicht ans Ende."""
    path = tmp_path / "platte.p3d"
    _drilled_plate(path)
    steps = [entry.id for entry in load(path).document.ops]
    assert (
        main(
            [
                "run",
                "chamfer_edges",
                str(path),
                "--on",
                "obj_1",
                "--distance",
                "1",
                "--before",
                str(steps[1]),
            ]
        )
        == 0
    )
    ops = [entry.op for entry in load(path).document.ops]
    assert ops == ["create_box", "chamfer_edges", "drill_hole", "drill_hole"]


def test_the_command_line_keeps_an_answer_for_its_next_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Antwort gilt für die übrigen Auswertungen desselben Befehls (Review B10).

    ``export`` wertet zweimal aus; vorher kam die Frage vor der langen
    Vollerkennung je Befehl zwei- bis dreimal.
    """
    from types import SimpleNamespace

    from app.cli import main
    from app.core.perceive.match_records import recognition_answer_key
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft("create_box")])
    key = recognition_answer_key("obj_1")
    record = {"object_id": "obj_1", "scope": "a" * 32, "allowed": True}
    # Die Antworten der Operationen gelten ebenso — wie im Fenster; eine freie
    # Stelle wird so einmal gesucht und steht danach im Schritt (§17.1).
    answered = {1: {"width": 42.0}}
    monkeypatch.setattr(
        main,
        "evaluate",
        lambda *_args, **_kwargs: SimpleNamespace(matches={1: {key: record}}, answers=answered),
    )

    main.run_evaluation(project, tmp_path / "teil.p3d", quiet=True)

    assert project.document.ops[0].matches[key] == record
    assert project.document.ops[0].params["width"] == 42.0


def test_the_command_line_takes_back_a_skipped_recognition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``recognize`` ist *Alle Merkmale erkennen* im Terminal (Review B10).

    Der Befund nennt den Knopf aus dem Fenster; ohne diesen Befehl ließ sich
    eine gespeicherte Absage im Terminal nicht zurücknehmen.
    """
    from importlib import import_module

    from app.core.perceive.match_records import recognition_answer_key

    monkeypatch.setattr(import_module("app.core.scene.evaluate"), "FEATURE_LIMIT_TRIANGLES", 1)
    path = tmp_path / "projekt.p3d"
    main(["new", str(path)])
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    assert main(["import", str(path), str(MESHES / "cube_clean.stl")]) == 0
    key = recognition_answer_key("obj_1")
    assert load(path).document.ops[0].matches[key]["allowed"] is False
    capsys.readouterr()

    asked = []

    def confirm(prompt: str = "") -> str:
        asked.append(prompt)
        return "2"

    monkeypatch.setattr("builtins.input", confirm)
    assert main(["recognize", str(path)]) == 0
    assert asked, "the question came again"
    assert load(path).document.ops[0].matches[key]["allowed"] is True

    # Nichts mehr ausgelassen: Der Befehl sagt es, ändert nichts und nennt
    # den Weg zu einer neuen Entscheidung (Review R7).
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked again"))
    assert main(["recognize", str(path)]) == 1
    said = capsys.readouterr().err
    assert "keine Merkmalserkennung ausgelassen" in said
    assert f"solidon3d recognize {path} --on obj_1" in said
    assert load(path).document.ops[0].matches[key]["allowed"] is True

    # Genannt, fragt er wie der Knopf im Fenster auch nach einer Zustimmung —
    # dort, wo ihre Erkennung später am Arbeitsspeicher scheiterte.
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    assert main(["recognize", str(path), "--on", "obj_1"]) == 0
    assert load(path).document.ops[0].matches[key]["allowed"] is False

    # Eine Kennung, die es nicht gibt, geht nicht still unter (Review S6),
    # auch nicht neben einer, die es gibt.
    capsys.readouterr()
    assert main(["recognize", str(path), "--on", "obj_1", "obj_9"]) == 1
    said = capsys.readouterr().err
    assert "obj_9" in said
    assert load(path).document.ops[0].matches[key]["allowed"] is False


def test_a_setting_per_part_names_the_parts_and_the_setting(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RM-289, N4: Die Kommandozeile bündelte gleiche Sätze und nannte bei einer
    Einstellung je Teil weder Teil noch Einstellung. Feldname und Wert kommen
    aus derselben Tabelle wie im Druckdialog, die Teile beim Namen."""
    from app.cli.main import print_findings
    from app.core.types import Finding

    def part(object_id: str, value: object) -> Finding:
        return Finding(
            code="export.part_setting",
            severity="info",
            message="Nur für dieses Teil: Die Überhänge sind zu groß.",
            values={"setting": "support.style", "value": value},
            object_id=object_id,
        )

    print_findings(
        [part("obj_1", "auto"), part("obj_2", "auto"), part("obj_3", "tree")],
        {"obj_1": "Pilz", "obj_2": "Turm", "obj_3": "Baum"},
    )
    lines = capsys.readouterr().out.splitlines()

    assert len(lines) == 2, lines
    assert lines[0].startswith("  - (2) ")
    assert "Pilz, Turm" in lines[0] and "Stützen: Automatisch" in lines[0], lines[0]
    assert "Baum" in lines[1] and "Stützen: Baum" in lines[1], lines[1]
    assert not any("support.style" in line for line in lines)


def test_the_dialog_reads_the_same_field_table_as_the_command_line() -> None:
    """Eine Tabelle, nicht zwei: Der Dialog liest die Felder aus dem Kern."""
    from app.core.knowledge import print_fields
    from app.ui import print_settings_dialog

    assert print_settings_dialog.FIELDS is print_fields.FIELDS
    assert print_settings_dialog.setting_title("shell.wall_count") == (
        print_fields.setting_title("shell.wall_count")
    )
