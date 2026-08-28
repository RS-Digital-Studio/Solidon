"""Erstinbetriebnahme, Fehlerbericht und Aktualisierungshinweis (Bauplan §38, §37.2)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from app.core import activation, feedback, tools, updates
from app.core import report as reports
from app.core.backends import llm

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.ui import first_run
from app.ui.first_run import FirstRunDialog, should_run
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.support_dialog import SupportDialog

# ``accept_test_signatures`` wirkt durch den Import: pytest sammelt die Fixture
# aus dem Modulnamensraum, aufgerufen wird sie nie.
from tests.release_signing import accept_test_signatures, signed  # noqa: F401

# --- external programs (§38) ---------------------------------------------------------


def test_the_survey_names_every_tool_and_what_it_is_for() -> None:
    """§38: eingerichtet, nicht mitgeliefert — die Anwendung muss also sagen,
    was da ist.

    **Die Namen standen hier als Aufzählung**, und mit dem OpenSCAD-Ausbau am
    26.08.2026 wurde der Test rot, obwohl an der Zusage keine Silbe anders war.
    Ein Testname oder eine Liste, die einen Bestand *aufzählt*, altert mit ihm —
    und trägt den Namen des Entfernten nirgends, weshalb keine Suche sie findet.

    Verglichen wird deshalb gegen :data:`tools.TOOLS`. Das ist bewusst die
    Quelle der Erhebung und trotzdem kein Zirkelschluss: ``survey()`` fragt die
    **Maschine** ab und entscheidet dabei, was sie zurückgibt — die Zusage ist,
    dass sie dabei keines auslässt. Die drei inhaltlichen Prüfungen darunter
    tragen den Rest.
    """
    found = tools.survey()

    assert found, "ohne Erhebung prüft alles darunter nichts"
    assert {state.tool.id for state in found} == {tool.id for tool in tools.TOOLS}, (
        "die Erhebung lässt kein Programm aus"
    )
    for state in found:
        assert str(state.tool.what_for).strip(), state.tool.id
        assert state.tool.optional, "none of them is required (§24.1)"


def test_a_missing_tool_is_not_an_error() -> None:
    missing = tools.ExternalTool(id="x", title="X", what_for="y", executables=("gibtsnicht",))

    assert not missing.available
    assert missing.path() is None


def test_a_service_is_asked_on_its_port_not_looked_for_on_the_disk() -> None:
    """ComfyUI kann portabel in ``D:\\AI`` liegen — dort findet es keine Suche.

    Solidon startet es ohnehin nie, es redet über HTTP mit ihm. Die Frage ist
    also, ob etwas antwortet, und nicht, ob eine Datei existiert.
    """
    service = tools.ExternalTool(
        id="x", title="X", what_for="y", kind="service", url="http://127.0.0.1:9"
    )

    assert not service.available
    assert not service.running()


def test_a_service_that_answers_is_available() -> None:
    import socket

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        service = tools.ExternalTool(
            id="x", title="X", what_for="y", kind="service", url=f"http://127.0.0.1:{port}"
        )

        assert service.available


def test_installed_but_not_running_is_its_own_answer() -> None:
    """Der Satz dazwischen ist der, den jemand lesen muss, um weiterzukommen."""
    service = tools.ExternalTool(
        id="x", title="X", what_for="y", kind="service", url="http://127.0.0.1:9"
    )
    state = tools.ToolState(tool=service, path=Path("ollama.exe"), running=False)

    assert state.installed
    assert not state.available
    assert "läuft" in str(state.explain())


def test_every_state_explains_what_helps_next() -> None:
    """§33.1: kein Zustand ohne einen Satz, der sagt, was als Nächstes geht."""
    for state in tools.survey():
        assert str(state.explain()).strip(), state.tool.id


def test_a_tool_can_be_pointed_at_by_hand(tmp_path: Path) -> None:
    """Der Weg, der immer geht — sonst ist eine ungewöhnliche Installation eine Sackgasse."""
    program = tmp_path / "elegoo-slicer.exe"
    program.write_text("")
    tools.set_location("slicer", str(program))

    slicer = tools.by_id("slicer")
    assert slicer is not None
    assert slicer.path() == program

    tools.set_location("slicer", "")
    assert slicer.path() is None


# --- einen Dienst starten (§27, §38) -------------------------------------------------


def test_only_a_service_with_a_command_can_be_started() -> None:
    """Geraten wird nicht.

    Ollama startet mit ``ollama serve`` — derselbe Befehl, den ein Mensch
    eintippen würde. ComfyUI hat keinen: Es läuft aus seinem eigenen Ordner mit
    seinem eigenen Python, und eine Anwendung, die das errät, startet
    irgendwann das Falsche.
    """
    startable = {tool.id for tool in tools.TOOLS if tool.start_arguments}

    assert startable == {"ollama"}
    ollama = tools.by_id("ollama")
    assert ollama is not None and ollama.start_arguments == ("serve",)
    for tool in tools.TOOLS:
        if tool.start_arguments:
            assert tool.kind == "service", tool.id


def test_starting_something_that_is_not_installed_does_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne Datei gibt es nichts zu starten — und keinen Unterprozess."""
    started: list[object] = []
    monkeypatch.setattr(tools.subprocess, "Popen", lambda *a, **k: started.append(a))
    monkeypatch.setattr(tools.discover, "find_program", lambda *_a: None)

    ollama = tools.by_id("ollama")
    assert ollama is not None

    assert not tools.start(ollama)
    assert started == []


def test_starting_a_service_uses_its_own_command_and_lets_go(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """„«ollama serve» startet es" war die vollständige Auskunft an jemanden,
    der in einem Fenster sitzt und keine Konsole offen hat.

    Der Prozess gehört nicht Solidon: losgelassen, ohne Fenster, und niemals
    von Solidon beendet.
    """
    program = tmp_path / "ollama.exe"
    program.write_text("")
    tools.set_location("ollama", str(program))
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_popen(command: object, **options: object) -> object:
        calls.append((command, options))
        return object()

    monkeypatch.setattr(tools.subprocess, "Popen", fake_popen)
    ollama = tools.by_id("ollama")
    assert ollama is not None
    monkeypatch.setattr(type(ollama), "running", lambda _self: True)

    try:
        assert tools.start(ollama), "der Port antwortet, also gilt es als gestartet"
    finally:
        tools.set_location("ollama", "")

    command, options = calls[0]
    assert command == [str(program), "serve"]
    assert options["stdout"] == tools.subprocess.DEVNULL, "kein Konsolenfenster über der Anwendung"


def test_a_service_that_does_not_come_up_says_no(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gestartet ist nicht dasselbe wie erreichbar — zurück kommt die Antwort
    auf die Frage, die zählt.
    """
    program = tmp_path / "ollama.exe"
    program.write_text("")
    tools.set_location("ollama", str(program))
    monkeypatch.setattr(tools.subprocess, "Popen", lambda *a, **k: object())
    ollama = tools.by_id("ollama")
    assert ollama is not None
    monkeypatch.setattr(type(ollama), "running", lambda _self: False)

    try:
        assert not tools.start(ollama, wait_seconds=0.0)
    finally:
        tools.set_location("ollama", "")


# --- der Erstlauf (§38) ---------------------------------------------------------------


def settled(dialog: FirstRunDialog, qt_app: QApplication) -> FirstRunDialog:
    """Wartet die Erhebung ab und lässt ihre Antwort ankommen.

    Über denselben Weg, den auch das Schließen nimmt — die Verbindung über die
    Thread-Grenze ist Teil dessen, was hier zu prüfen ist.
    """
    dialog.wait_for_survey()
    qt_app.processEvents()
    return dialog


def test_the_answers_do_not_squeeze_the_questions(qt_app: QApplication) -> None:
    """Die nachgereichten Zeilen wachsen ins Fenster, nicht in die Felder.

    Die Erhebung tauscht „Wird nachgesehen …" gegen drei Programmzeilen und
    die Chat-Auskunft. Das Fenster blieb dabei auf seiner Aufmachgröße —
    das umbrochene Intro meldet der Layoutrechnung nur eine Zeile —, und der
    Fehlbetrag wurde aus den Auswahlfeldern gepresst: Sprache, Drucker und
    Material standen mit 16 von 28 Punkten da, die Schrift oben und unten
    abgeschnitten (Robert, 26.08.2026, mit Bild). Der Dialog wächst jetzt
    nach dem Eintragen der Antworten; geprüft wird die Wirkung an den
    Feldern, nicht die Fenstergröße — sie ist das Mittel, nicht die Zusage.
    """
    dialog = FirstRunDialog(UiSettings())
    dialog.show()
    qt_app.processEvents()
    settled(dialog, qt_app)
    # Der Wachstumsruf läuft über singleShot(0) — eine Runde später.
    qt_app.processEvents()
    qt_app.processEvents()

    for name in ("language", "printer", "material"):
        combo = getattr(dialog, name)
        assert combo.height() >= combo.minimumSizeHint().height(), (
            f"{name}: {combo.height()} von {combo.minimumSizeHint().height()} Punkten"
        )


def test_the_dialog_is_there_before_the_answers_are(qt_app: QApplication) -> None:
    """§38, §2.8: das Allererste, was ein Kunde sieht, wartet auf nichts.

    Gemessen brauchte der Dialog 1,88 Sekunden bis auf den Bildschirm — die
    Suche nach den externen Programmen, das Auslesen eines Slicer-Profils und eine
    HTTP-Frage an Ollama, alles im Oberflächen-Thread. Er zeigt jetzt sofort
    seine Fragen; wo eine Antwort fehlt, steht ein Satz und keine Behauptung.
    """
    dialog = FirstRunDialog(UiSettings())

    assert dialog.language.count() >= 2, "die Fragen stehen sofort"
    assert dialog.printer.count() >= 1
    assert "nachgesehen" in dialog.chat_state.text()
    assert not dialog.install_button.isEnabled(), "kein Knopf auf eine Vermutung"

    settled(dialog, qt_app)

    assert dialog.install_button.isEnabled()
    assert "nachgesehen" not in dialog.chat_state.text()


def test_looking_does_not_happen_in_the_gui_thread(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Erhebung selbst gehört in einen Arbeiter (§38)."""
    import threading

    here = threading.get_ident()
    seen: list[int] = []
    real = tools.survey

    def watched() -> tuple[tools.ToolState, ...]:
        seen.append(threading.get_ident())
        return real()

    monkeypatch.setattr(tools, "survey", watched)

    settled(FirstRunDialog(UiSettings()), qt_app)

    assert seen, "es wurde überhaupt nicht gesucht"
    assert here not in seen, "die Suche lief im Oberflächen-Thread"


def test_a_printer_the_user_chose_is_not_overwritten(qt_app: QApplication) -> None:
    """Eine Vorgabe, die eine getroffene Wahl überschreibt, ist keine (§2.4).

    Der Vorschlag aus dem Slicer-Profil kommt nachgereicht — und trifft
    vielleicht jemanden, der in der Zwischenzeit selbst gewählt hat.
    """
    dialog = FirstRunDialog(UiSettings())
    dialog.printer.setCurrentIndex(dialog.printer.count() - 1)
    chosen = dialog.printer.currentData()

    dialog._show(first_run.Findings(tools=(), missing="", chat="x", printer="prusa_mk4"))

    assert dialog.printer.currentData() == chosen, "die eigene Wahl bleibt stehen"


def test_a_suggestion_arrives_while_nobody_has_chosen(qt_app: QApplication) -> None:
    """Und wo niemand gewählt hat, trägt der Vorschlag."""
    dialog = FirstRunDialog(UiSettings())
    offered = {dialog.printer.itemData(index) for index in range(dialog.printer.count())}
    other = next(entry for entry in sorted(offered) if entry != dialog.printer.currentData())

    dialog._show(first_run.Findings(tools=(), missing="", chat="x", printer=other))

    assert dialog.printer.currentData() == other


def test_the_first_run_happens_once(qt_app: QApplication) -> None:
    settings = UiSettings()

    assert should_run(settings)
    settings.first_run_done = True
    assert not should_run(settings)


def test_the_first_run_asks_the_four_things(qt_app: QApplication) -> None:
    """§38: language, printer, material, external programs."""
    dialog = settled(FirstRunDialog(UiSettings()), qt_app)

    assert dialog.language.count() >= 2
    assert dialog.printer.count() >= 1
    assert dialog.material.count() >= 1
    # Die Programme stehen als Zeilen da, nicht mehr als ein Textblock: eine
    # je Programm, mit Zeichen, Zustand und Zweck. Geprüft an **jedem**, das
    # die Anwendung kennt, und nicht an einem herausgegriffenen Namen: Hier
    # stand „OpenSCAD", und der Test fiel mit dem Ausbau, ohne dass sich an
    # dieser Zusage etwas geändert hätte.
    from PySide6.QtWidgets import QLabel

    from app.core import tools as external_tools

    shown = " ".join(label.text() for label in dialog.tools.findChildren(QLabel))
    assert external_tools.TOOLS, "ohne Werkzeugliste prüft die Schleife nichts"
    for tool in external_tools.TOOLS:
        assert str(tool.title) in shown, f"{tool.id} fehlt in der Erstinbetriebnahme"
    assert dialog.open_button.text().startswith("Modell")


def test_the_first_run_offers_the_chat_setup(qt_app: QApplication) -> None:
    """Der Chat ist das Versprechen, mit dem die Anwendung antritt — der Weg
    dorthin gehört in den ersten Start, nicht nur in ein Panel, das ein neuer
    Nutzer noch nie gesehen hat.
    """
    dialog = FirstRunDialog(UiSettings())

    settled(dialog, qt_app)
    assert dialog.chat_button.text().startswith("Chat")
    assert dialog.chat_state.text().strip()


def test_the_chat_line_says_what_is_missing(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Zugang steht da, was fehlt und dass alles andere ohne funktioniert
    — nicht der Zustand der Entwicklermaschine.
    """
    monkeypatch.setattr(llm, "first_available", lambda: None)

    dialog = settled(FirstRunDialog(UiSettings()), qt_app)

    assert "Sprachmodell" in dialog.chat_state.text()
    assert "funktioniert" in dialog.chat_state.text()


def test_the_chat_line_names_the_ready_backend(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein bereites Backend wird beim Namen genannt — „bereit" allein wäre
    eine Behauptung ohne Adresse.
    """
    monkeypatch.setattr(llm, "first_available", lambda: llm.OllamaBackend())

    dialog = settled(FirstRunDialog(UiSettings()), qt_app)

    assert "ollama" in dialog.chat_state.text()
    assert llm.DEFAULT_OLLAMA_MODEL in dialog.chat_state.text()


def test_the_answers_land_in_the_settings(qt_app: QApplication) -> None:
    settings = UiSettings()
    dialog = FirstRunDialog(settings)
    dialog.printer.setCurrentIndex(0)

    dialog.apply_to(settings)

    assert settings.printer
    assert settings.material
    assert settings.first_run_done


def test_the_first_run_ends_at_the_first_import(qt_app: QApplication) -> None:
    """§2.3: die ersten fünf Minuten enden bei einem Import, nicht bei einem
    „Fertig"-Knopf.
    """
    asked: list[bool] = []
    dialog = FirstRunDialog(UiSettings())
    dialog.importRequested.connect(lambda: asked.append(True))

    dialog._open()

    assert asked == [True]


def test_a_window_does_not_open_a_dialog_by_itself(qt_app: QApplication) -> None:
    """Ein Fenster, das während seines Aufbaus einen modalen Dialog öffnet,
    lässt sich von nichts aufbauen, das kein Mensch ist — kein Test, kein
    Screenshot-Werkzeug, kein zweites Fenster.
    """
    settings = UiSettings()
    assert should_run(settings)

    window = MainWindow(Session(), settings)

    assert window.isVisible() is False
    assert not settings.first_run_done, "nothing happened until start() is called"


# --- der Fehlerbericht (§37.2) --------------------------------------------------------


def test_a_report_carries_the_versions() -> None:
    entry = reports.environment()

    assert entry["app"].startswith("Solidon")
    assert entry["python"]
    assert "trimesh" in entry


def test_a_report_describes_the_window_session_where_there_is_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auf Linux gehört in den Bericht, wie die Fenstersitzung eingerichtet ist.

    Simon Wenger meldete am 27.08.2026: „Es waren viele tweaks nötig, wie auf
    x11 umschalten … So muss ich diesen Text in einer anderen Anwendung
    schreiben und nach Solidon3D copypasten." Sein Bericht enthielt jede
    Bibliotheksfassung und **nichts** über die Sitzung, in der das geschah —
    kein Wort darüber, ob Qt auf Wayland oder über XWayland lief und welches
    Eingabemodul aktiv war. Beides erklärt genau die zwei Punkte, die er
    nennt, und beides steht in vier Umgebungsvariablen.

    Auf Windows und macOS ist keine davon gesetzt; dann bleibt die Zeile weg,
    statt einen Strich zu zeigen.
    """
    for key in (*reports.SESSION_KEYS, "WAYLAND_DISPLAY"):
        monkeypatch.delenv(key, raising=False)
    assert not any(key.lower() in reports.environment() for key in reports.SESSION_KEYS), (
        "wo nichts gesetzt ist, steht auch nichts"
    )

    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("QT_QPA_PLATFORM", "xcb")
    monkeypatch.setenv("QT_IM_MODULE", "ibus")
    entry = reports.environment()

    assert entry["xdg_session_type"] == "wayland"
    assert entry["qt_qpa_platform"] == "xcb", (
        "dass jemand auf X11 umgeschaltet hat, ist die Auskunft"
    )
    assert entry["qt_im_module"] == "ibus"

    # Und wenn nur der Wayland-Anschluss dasteht, ist auch das eine Antwort.
    monkeypatch.delenv("XDG_SESSION_TYPE")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert "wayland" in reports.environment()["xdg_session_type"]


def test_a_report_names_the_versions_even_without_package_metadata() -> None:
    """Im gebauten Paket gibt es keine ``.dist-info`` — die Fassung trotzdem.

    Im Bericht eines Kunden vom 27.08.2026 stand:

        trimesh: 5.0.0 · numpy: 2.5.2
        manifold3d: - · scipy: - · shapely: - · PySide6: -

    Vier von sechs als „nicht installiert", bei einem Programm, das ohne
    PySide6 kein Fenster öffnet. ``importlib.metadata`` liest die
    ``.dist-info``-Ordner, und die reisen in einem PyInstaller-Bau nicht mit;
    ``numpy`` stand da, weil es sein ``__version__`` wirklich selbst trägt.

    **Ein Fehlerbericht, der „nicht installiert" sagt, wo eine Bibliothek
    läuft, ist schlimmer als einer ohne die Zeile:** Er schickt die Diagnose an
    eine Stelle, an der nichts ist. Genau das ist beim Lesen dieses Berichts
    passiert.

    Gefragt wird deshalb zuerst das **Modul** — vier der sechs tragen ihre
    Fassung als ``__version__``, und das überlebt jeden Bau.

    **Was dieser Test nicht misst, und warum daneben ein zweiter steht:** Er
    nimmt ``metadata.version`` weg, *nachdem* die Suite ``trimesh`` längst
    importiert hat; dann steht ``trimesh.__version__`` schon auf seinem Wert.
    Im Bau wird es ohne Metadaten importiert und ist dann ``None`` — dieselbe
    Funktion, nur die Reihenfolge getauscht. Deshalb steht ``trimesh`` unten
    nicht in ``named``, und deshalb prüft
    :func:`test_the_spec_carries_metadata_for_what_has_no_own_version` die
    andere Hälfte.
    """
    import importlib.metadata as metadata

    def no_metadata(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    with mock.patch.object(metadata, "version", no_metadata):
        entry = reports.environment()

    # ``manifold3d`` hat kein ``__version__``; für es nimmt die Spec die
    # Metadaten ausdrücklich mit (``copy_metadata``), hier fehlen sie.
    named = {name: entry[name] for name in ("scipy", "shapely", "PySide6", "numpy")}
    assert all(value != "-" for value in named.values()), (
        f"ohne .dist-info bleibt die Fassung am Modul lesbar: {named}"
    )


#: Die Pakete aus dem Fehlerbericht, die ihre Fassung **nicht** selbst tragen.
#:
#: ``manifold3d`` hat gar kein ``__version__``; ``trimesh`` hat eines, aber es
#: ist selbst ein Metadatenaufruf (``trimesh/version.py`` ruft
#: ``importlib.metadata.version("trimesh")``) und liefert ohne ``.dist-info``
#: ``None``. Beide brauchen deshalb ``copy_metadata`` in der Spec.
#:
#: Nachmessen lässt sich die Liste so: ``python -c "import <paket>;
#: print(<paket>.__version__)"`` gegen einen Lauf, in dem
#: ``importlib.metadata.version`` wirft.
NEEDS_METADATA = ("manifold3d", "trimesh")


def test_the_spec_carries_metadata_for_what_has_no_own_version() -> None:
    """Wessen Fassung nicht am Modul steht, dessen ``.dist-info`` reist mit.

    Die Zusicherung darüber prüft, dass der Modulweg trägt; diese hier prüft
    die andere Hälfte — dass für die zwei, bei denen er es nicht tut, der
    Metadatenweg im Bau überhaupt offen ist.

    Hier stand bis zum 27.08.2026 die Annahme, ``collect_data_files`` nehme
    die Metadaten nebenbei mit. **Gemessen ist das falsch:** Von 24 Einträgen
    für ``trimesh`` und 495 für ``numpy`` trägt keiner eine ``dist-info`` —
    die Funktion sammelt nur Dateien *innerhalb* des Paketverzeichnisses.
    """
    spec = (Path(__file__).parent.parent / "packaging" / "solidon3d.spec").read_text(
        encoding="utf-8"
    )
    missing = [name for name in NEEDS_METADATA if f'copy_metadata("{name}")' not in spec]
    assert not missing, (
        f"diese Pakete tragen ihre Fassung nicht selbst und bekommen im Bau einen Strich: {missing}"
    )


def test_a_report_without_the_project_says_nothing_about_geometry() -> None:
    report = reports.ErrorReport(summary="x", detail="y")

    assert not report.contains_geometry
    assert "Geometrie" not in reports.as_text(report)


def test_a_report_with_the_project_says_what_travels_along() -> None:
    """§37.2: das Angebot sagt, dass das Modell angehängt wird — still wäre
    falsch.
    """
    report = reports.ErrorReport(summary="x", include_project=True)

    assert report.contains_geometry
    assert "Geometrie" in reports.as_text(report)


def test_a_report_carries_the_scene_without_the_geometry() -> None:
    """Der Steckbrief sagt, woran die Szene stand — die Projektdatei bleibt draußen.

    Aus dem Kundenprotokoll vom 23.08.2026: Es sagte, dass die Auswertung
    anhielt, aber nichts über die Szene. Ein Bildschirmfoto zeigte drei Wülste
    mit 34,09, 34,06 und 34,03 mm — ob das drei Kanten sind oder eine dreimal
    erkannte, war ohne die Maße nicht zu entscheiden. Der Steckbrief trägt sie
    und bleibt dabei Text: kein Modell, keine Dreiecke.
    """
    report = reports.ErrorReport(
        summary="x",
        digest="Objekt pad_v2  225 x 225 x 2 mm · Wulst Ø 34,09 mm",
    )

    text = reports.as_text(report)

    assert "Wulst" in text
    assert "34,09" in text
    # Und das Angebot bleibt ehrlich: ohne Projektdatei keine Geometrie (§37.2).
    assert not report.contains_geometry
    assert "Geometrie" not in text


def test_a_report_without_a_digest_stays_short() -> None:
    """Was leer ist, bekommt keine Überschrift — ein Abschnitt „szene" ohne
    Inhalt sähe aus wie eine Szene, über die nichts zu sagen war."""
    assert "--- szene ---" not in reports.as_text(reports.ErrorReport(summary="x"))


def test_a_report_is_written_as_a_folder(tmp_path: Path) -> None:
    report = reports.ErrorReport(summary="Etwas ging schief", detail="Details")

    target = reports.write(report, directory=tmp_path)

    assert (target / "bericht.txt").is_file()
    assert "Etwas ging schief" in (target / "bericht.txt").read_text(encoding="utf-8")


def test_the_project_is_attached_only_when_asked(tmp_path: Path) -> None:
    project = tmp_path / "projekt.p3d"
    project.write_bytes(b"PK\x03\x04nicht wirklich ein zip")

    without = reports.write(reports.ErrorReport(summary="x"), project, tmp_path / "a")
    with_it = reports.write(
        reports.ErrorReport(summary="x", include_project=True), project, tmp_path / "b"
    )

    assert not (without / project.name).exists()
    assert (with_it / project.name).is_file()


def test_nothing_is_sent(tmp_path: Path) -> None:
    """§37.2: keine Telemetrie. Der Bericht ist ein Ordner und bleibt einer."""
    import inspect

    source = inspect.getsource(reports)

    assert "urlopen" not in source
    assert "requests" not in source
    assert "post" not in source


def test_the_dialog_still_writes_a_folder(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§37.2 bleibt eingelöst, auch wenn es den Versand jetzt gibt.

    Der abgelegte Ordner ist kein Notausgang für einen gescheiterten Versand,
    sondern ein Weg neben ihm — wer nichts aus der Hand geben will, nimmt ihn.
    """
    monkeypatch.setattr("app.core.report.user_data_dir", lambda: tmp_path)

    dialog = SupportDialog(message="Der Deckel sitzt schief.", error=ValueError("kaputt"))
    dialog.with_log.setChecked(False)
    dialog._write_folder()

    assert dialog.written is not None and dialog.written.is_dir()
    text = (dialog.written / "bericht.txt").read_text(encoding="utf-8")
    assert "Der Deckel sitzt schief." in text
    assert "kaputt" in text, "der Stapelabzug reist mit, sonst ist der Bericht die halbe Miete"


# --- die Rückmeldung, die wirklich hinausgeht (§37.2) ---------------------------------


def test_the_dialog_sends_what_it_showed(qt_app: QApplication) -> None:
    """Was in der Vorschau steht, ist die Sendung — nicht ein Auszug davon."""
    seen: dict[str, object] = {}

    def sender(url: str, content_type: str, body: bytes) -> dict[str, object]:
        seen["body"] = body
        return {"ok": True, "reference": "S-1"}

    dialog = SupportDialog(
        message="Der Fasenwinkel fehlt.", screenshot=b"\x89PNGdaten", sender=sender
    )
    dialog.with_log.setChecked(False)
    dialog._start()
    assert dialog._worker is not None
    dialog._worker.wait(5000)
    qt_app.processEvents()

    assert dialog.receipt is not None and dialog.receipt.reference == "S-1"
    assert b"Der Fasenwinkel fehlt." in bytes(seen["body"])  # type: ignore[arg-type]
    assert b"bildschirmfoto.png" in bytes(seen["body"])  # type: ignore[arg-type]


def test_the_screenshot_is_only_attached_when_it_is_ticked(qt_app: QApplication) -> None:
    """Ein Bild des Fensters geht nur mit, wenn jemand das Kästchen stehen
    lässt — es zeigt, woran gerade gearbeitet wird."""
    dialog = SupportDialog(message="x", screenshot=b"\x89PNGdaten")

    assert dialog.with_shot.isChecked(), "wer meldet, will meistens zeigen"
    dialog.with_shot.setChecked(False)

    assert all(entry.name != "bildschirmfoto.png" for entry in dialog.ticket().attachments)


def test_a_dialog_without_a_screenshot_does_not_offer_one(qt_app: QApplication) -> None:
    dialog = SupportDialog(message="x")

    assert not dialog.with_shot.isEnabled()
    assert not dialog.with_shot.isChecked()


def test_a_failed_send_offers_the_two_ways_without_network(qt_app: QApplication) -> None:
    """Regel 17: kein „fehlgeschlagen", sondern zwei Wege, die ohne die
    Leitung auskommen, die gerade nicht wollte."""

    def sender(url: str, content_type: str, body: bytes) -> dict[str, object]:
        raise OSError("Netz weg")

    dialog = SupportDialog(message="x", sender=sender)
    dialog.with_log.setChecked(False)
    dialog._start()
    assert dialog._worker is not None
    dialog._worker.wait(5000)
    qt_app.processEvents()

    assert dialog.by_mail.isVisible() or not dialog.isVisible()
    assert "Netz weg" in dialog.state.text()
    assert dialog.save_folder.isEnabled(), "der abgelegte Ordner steht immer offen"


def test_an_empty_message_cannot_be_sent(qt_app: QApplication) -> None:
    """Kein toter Knopf: *Senden* gilt erst, wenn etwas dasteht."""
    dialog = SupportDialog()

    assert not dialog.send.isEnabled()
    dialog.message.setPlainText("Etwas ist schief.")
    assert dialog.send.isEnabled()


def test_a_survey_answer_can_be_sent_without_the_optional_fields(qt_app: QApplication) -> None:
    """Bewertung oder eine Antwort genügt; der freie Nachtrag bleibt freiwillig."""
    from app.core.support import KIND_SURVEY

    dialog = SupportDialog(kind=KIND_SURVEY)
    try:
        assert dialog.survey is not None
        assert not dialog.send.isEnabled(), "ein ganz leerer Bogen bleibt leer"

        dialog.survey.ratings.button(4).click()
        assert dialog.send.isEnabled(), "eine Bewertung darf nicht am leeren Nachtrag scheitern"

        dialog.survey.ratings.setExclusive(False)
        for button in dialog.survey.ratings.buttons():
            button.setChecked(False)
        dialog.survey.ratings.setExclusive(True)
        dialog.survey.fields["missing"].setPlainText("Die Auswahl ist zu klein.")
        assert dialog.send.isEnabled(), "auch eine einzelne Freitextantwort genügt"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_crash_can_be_sent_without_typing_anything(qt_app: QApplication) -> None:
    """Der Stapelabzug ist der Bericht — der Knopf wartet nicht auf einen Satz."""
    dialog = SupportDialog(kind="crash", error=ValueError("kaputt"))

    assert dialog.send.isEnabled()


def test_a_programme_error_arrives_as_a_crash_with_its_traceback(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§33.1: Ein Programmfehler bekommt den Dialog, der ihn melden kann —
    samt Stapelabzug, den der Nutzer nicht abtippen soll."""
    window = MainWindow(Session(), UiSettings())
    opened: dict[str, SupportDialog] = {}
    monkeypatch.setattr(SupportDialog, "exec", lambda self: opened.setdefault("dialog", self) and 0)

    try:
        raise ValueError("kaputt")
    except ValueError as problem:
        window.report_error(problem)

    dialog = opened["dialog"]
    assert dialog.ticket().kind == "crash"
    assert "kaputt" in dialog.detail
    assert "Traceback" in dialog.detail
    window.close()


# --- der Aktualisierungshinweis (§37.2) -----------------------------------------------


def test_a_newer_version_is_recognised() -> None:
    assert updates.Release(version="0.9.0").newer_than("0.0.1")
    assert not updates.Release(version="0.0.1").newer_than("0.0.1")
    assert not updates.Release(version="0.0.1").newer_than("0.1.0")


def test_the_check_reads_the_version_file() -> None:
    def answer(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        # Unterschrieben, weil ``check`` seit §37.2 nichts anderes ansieht —
        # die Fixture oben stellt den Schlüssel dafür.
        return signed({"version": "1.2.3", "url": "https://example.invalid/download"})

    release = updates.check(fetch=answer)

    assert release is not None
    assert release.version == "1.2.3"
    assert release.newer_than("0.0.1")


def test_a_server_that_does_not_answer_is_not_an_error() -> None:
    """Ein Start, der stolpert, weil ein Server nicht erreichbar war, wäre
    schlimmer als gar kein Hinweis.
    """

    def fail(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        raise OSError("no route to host")

    assert updates.check(fetch=fail) is None


def test_the_grenze_is_the_click_not_the_check() -> None:
    """§37.2 zieht die Grenze beim **Auslöser**, nicht beim Vorgang.

    Hier stand bis zum 23.08.2026 das Gegenteil: „eine Anfrage, die den Rechner
    verlässt, ist eine Entscheidung, keine Vorgabe" — und daraus folgte
    ``check_for_updates is False``. **Der Satz steht so nicht im Bauplan.**
    Dort heißt es: „Es lädt nichts von allein, es ersetzt sich nichts im
    Hintergrund, und es startet nichts ohne einen Klick." Alle drei Verbote
    gelten dem Herunterladen und dem Starten. Über die Frage, *ob es etwas
    Neues gibt*, sagt §37.2 nichts.

    **Der Test war also schärfer als der Bauplan** — genau der Fall, vor dem
    dieser im Nachtrag vom 22.08.2026 warnt: „Ein Test, der schärfer ist als
    der Bauplan, sieht wie Sicherheit aus, bis jemand den Bauplan für die
    Wahrheit nimmt und die Prüfung entfernt." Er hat hier nichts geschützt,
    sondern eine Zusage erfunden und sie zwei Monate lang gehalten.

    Geprüft wird deshalb, was der Bauplan wirklich verlangt: dass nichts ohne
    Klick geladen und nichts ohne Klick gestartet wird.
    """
    from app.ui import main_window

    quelle = Path(main_window.__file__).read_text(encoding="utf-8")
    beginn = quelle.index("def _update_answered")
    ende = quelle.index("def ", beginn + 10)
    antwort = quelle[beginn:ende]

    assert "start_installer" not in antwort, "gestartet wird erst nach dem Schließen"
    assert "_show_update" in antwort, "gezeigt wird ein Fenster, geladen wird darin auf Klick"


def test_nothing_runs_without_a_click() -> None:
    """§37.2: Die Grenze liegt beim Auslöser, nicht beim Vorgang.

    Der Test hieß „nichts wird geladen" und suchte ``subprocess`` im **ganzen**
    Modul. Damit verbot er die Funktion statt des selbsttätigen Ablaufs, und er
    wurde rot, als ``start_installer`` dazukam — ohne dass etwas kaputt war.
    §37.2 erlaubt Laden und Starten ausdrücklich: „Wer will, lädt das Paket aus
    der Anwendung heraus … Die Grenze liegt wie beim Fehlerbericht nicht beim
    Vorgang, sondern beim Auslöser."

    Geprüft wird darum die Kette, an der es wirklich hängt. Beim Start läuft von
    allein nur ``check``: Der fragt eine Datei ab und sonst nichts. ``download``
    hängt schon an einem Klick und **startet trotzdem nichts** — es holt und
    prüft, und wer es ruft, hat danach eine Datei und immer noch die Wahl. Und
    ``subprocess`` steht an genau einer Stelle: der, hinter der ein zweiter
    Klick liegt.
    """
    import inspect

    check = inspect.getsource(updates.check)
    download = inspect.getsource(updates.download)

    assert "urlretrieve" not in check
    assert "subprocess" not in check
    assert "start_installer" not in check
    assert "download(" not in check

    assert "subprocess" not in download
    assert "start_installer" not in download

    # Selbsttragend statt aufgezählt: Kommt eine zweite Funktion dazu, die ein
    # fremdes Programm startet, fällt sie hier auf, ohne dass jemand den Test
    # nachzieht.
    elsewhere = sorted(
        name
        for name, member in vars(updates).items()
        if inspect.isfunction(member)
        and getattr(member, "__module__", "") == updates.__name__
        and name != "start_installer"
        and "subprocess" in inspect.getsource(member)
    )

    assert not elsewhere, f"startet ein Programm, ohne dass ein Klick davor liegt: {elsewhere}"


def test_the_report_says_where_it_went_and_stays_open(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Bericht nannte den Ablageort und schloss sich im gleichen Augenblick.

    Das war der Fehler des abgelösten Berichtsfensters: Der Pfad ging in die
    Vorschau, die nächste Zeile war ``accept()``. Die Bitte, „den abgelegten
    Ordner" zu senden, zeigte damit auf etwas, das niemand mehr lesen konnte.

    Der Nachfolger löst beides anders und besser — die Zustandszeile nennt den
    Ort, und der Ordner geht von selbst auf. Was bleibt, ist die Zusage: Ablegen
    ist ein Weg neben dem Versand und nicht sein Ende, das Fenster bleibt offen.
    """
    from PySide6.QtCore import QUrl

    from app.ui import support_dialog as module

    monkeypatch.setattr("app.core.report.user_data_dir", lambda: tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(
        module.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toString())),
    )

    dialog = SupportDialog(message="Der Deckel sitzt schief.", error=ValueError("kaputt"))
    dialog.with_log.setChecked(False)
    dialog._write_folder()

    assert dialog.result() != SupportDialog.DialogCode.Accepted, (
        "der Dialog schließt sich, bevor der Ort gelesen werden kann"
    )
    assert dialog.written is not None
    assert str(dialog.written) in dialog.state.text(), "genannt wird nicht der Ordner"
    assert opened == [QUrl.fromLocalFile(str(dialog.written)).toString()], (
        "der abgelegte Ordner geht nicht auf — eine Pfadzeile allein wird abgetippt"
    )


def test_choosing_a_language_switches_the_dialog_at_once(qt_app: QApplication) -> None:
    """Wer die Sprache wechselt, kann den Text meistens nicht lesen.

    Hier stand ein Hinweis — „Die Oberfläche stellt sich gleich darauf um" —,
    und der kündigte an, was erst nach dem Bestätigen geschah: Der Dialog blieb
    deutsch. Für einen Italiener, der Solidon zum ersten Mal öffnet und
    „Italiano" wählt, ist eine Ankündigung auf Deutsch keine Hilfe.
    Entschieden von Robert am 26.08.2026: Sprache gewählt heißt Sprache
    umgestellt.

    Der Dialog übersetzt sich dabei nicht, er wird neu gebaut — deshalb prüft
    dieser Test **beide Hälften**: dass er sich mit ``LANGUAGE_CHANGED``
    schließt und die Wahl schon in den Einstellungen steht, und dass der
    nächste Aufbau wirklich in der neuen Sprache spricht.

    Verglichen werden **alle** sichtbaren Texte, nicht ein herausgegriffener:
    Ein ``retranslate``, das eines von neunzehn Widgets vergisst, fiele nur in
    einer Sprache auf, und genau das soll hier auffallen.
    """
    from PySide6.QtWidgets import QLabel, QPushButton

    from app.i18n import get_language, set_language
    from app.ui.first_run import LANGUAGE_CHANGED

    # **Die Sprache ist ein Prozesszustand, und hier wird sie wirklich
    # umgestellt.** Ohne das Zurücksetzen nimmt dieser Test jeden folgenden mit
    # — gemessen: ``test_an_unexpected_error_does_not_leave_the_first_run_waiting``
    # suchte danach vergeblich nach „schiefgegangen" in einem englischen Satz.
    #
    # Eine ``autouse``-Fixture in ``conftest.py`` wäre der übliche Weg (so hält
    # es die Anzeigeeinheit), und sie ist hier **gemessen untauglich**: Mit ihr
    # stirbt ``test_ui.py`` reproduzierbar an einer Zugriffsverletzung, ohne
    # sie läuft es mit 305 passed durch — und eine *leere* autouse-Fixture an
    # derselben Stelle stört nicht. Es liegt also am Setzen der Sprache in
    # jedem Test, nicht an der zusätzlichen Fixture. Warum, ist offen; bis
    # dahin räumt dieser eine Test hinter sich auf.
    spoken_before = get_language()

    def visible_texts(dialog: FirstRunDialog) -> list[str]:
        return [w.text() for w in dialog.findChildren(QLabel) if w.text().strip()] + [
            w.text() for w in dialog.findChildren(QPushButton) if w.text().strip()
        ]

    settings = UiSettings()
    settings.language = "de"
    before = FirstRunDialog(settings)
    spoken = visible_texts(before)
    assert len(spoken) > 5, "ohne Texte prüft der Vergleich darunter nichts"

    other = before.language.findData("en")
    assert other >= 0, "Englisch muss zur Auswahl stehen"
    before.language.setCurrentIndex(other)

    assert before.result() == LANGUAGE_CHANGED, "der Dialog schließt sich für den Neuaufbau"
    assert settings.language == "en", "und die Wahl steht schon in den Einstellungen"

    after = FirstRunDialog(settings)
    fresh = visible_texts(after)
    unchanged = [a for a, b in zip(spoken, fresh, strict=False) if a == b]
    assert len(unchanged) <= 1, f"diese Texte wechselten nicht mit: {unchanged}"
    assert any("Let" in text or "External" in text for text in fresh), (
        "der neue Dialog spricht die gewählte Sprache"
    )

    set_language(spoken_before)


def test_choosing_the_same_language_changes_nothing(qt_app: QApplication) -> None:
    """Die Schleife im Aufrufer endet, weil dieselbe Sprache nichts auslöst.

    ``action_first_run`` baut den Dialog neu, solange er sich mit
    ``LANGUAGE_CHANGED`` schließt. Was das begrenzt, ist kein Zähler, sondern
    diese Bedingung: Nach dem Wechsel steht die Sprache in den Einstellungen,
    und der nächste Dialog beginnt damit. Wer sie noch einmal wählt, wählt,
    was schon gilt.
    """
    settings = UiSettings()
    dialog = FirstRunDialog(settings)

    same = dialog.language.findData(settings.language)
    dialog.language.setCurrentIndex(same)

    assert not dialog.isHidden() or dialog.result() == 0, "kein Schließen ohne Wechsel"


def test_an_unexpected_error_does_not_leave_the_first_run_waiting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der erste Blick auf Solidon ist nicht der Ort für einen stillstehenden Dialog.

    Was hier fehlschlägt, kostet nichts: Die Liste der Programme ist ein Blick,
    keine Bedingung — der Weg zum ersten Modell führt daran vorbei.
    """

    def refuse() -> tuple[tools.ToolState, ...]:
        raise OSError(13, "Zugriff verweigert")

    monkeypatch.setattr(tools, "survey", refuse)

    dialog = settled(FirstRunDialog(UiSettings()), qt_app)

    assert dialog.install_button.isEnabled(), "der Weg zur Liste bleibt offen"
    assert "nachgesehen" not in dialog.chat_state.text(), "keine Zeile bleibt auf „wird“ stehen"
    assert "schiefgegangen" in dialog.chat_state.text()
    assert dialog.open_button.text().startswith("Modell"), "und der Weg hinaus steht da"


def test_the_session_attachment_names_the_parts_that_stay_behind(
    monkeypatch: pytest.MonkeyPatch, qt_app: QApplication
) -> None:
    """Der Support erfährt **vor** dem Öffnen, dass er das Projekt nicht rechnen
    kann (§24.5, Regel 13).

    Eine eigene ``.py`` reist nie in einer Projektdatei mit — sonst führte eine
    hereinkommende Datei Code aus (§32); ein **Rezept** reist seit dem
    26.08.2026 als Daten mit und braucht diese Warnung nicht. Ohne diesen Satz
    bekommt der Support
    ein Projekt, das bei ihm anhält, und die Ursache steht auf einem Rechner, an
    den niemand mehr herankommt.

    Geprüft wird die **Verdrahtung**, nicht die Erkennung: Was
    ``check_outgoing`` selbst findet, steht in ``tests/test_parts_catalog.py``.
    Hier zählt, dass der Dialog sie ruft und ihr Ergebnis in die Beschreibung
    des Anhangs trägt — die Beschreibung, die ``Ticket.as_text()`` in Vorschau,
    Sendung und abgelegten Ordner mitnimmt. Ein Ort, drei Wege hinaus.

    Entworfen von 3d-druck-b8 zusammen mit dem Anschluss.
    """
    from app.core.knowledge.parts import check as part_check
    from app.core.types import Finding

    monkeypatch.setattr(
        part_check,
        "check_outgoing",
        lambda document, registry=None: [
            Finding(
                code="parts.travelling",
                severity="warning",
                message="Dieses Projekt benutzt eigene Bausteine.",
                values={"parts": "eigenbau, magnettasche"},
            )
        ],
    )
    dialog = SupportDialog(message="Der Deckel sitzt schief.", session=Session())

    assert "eigenbau, magnettasche" in dialog._session_note(), (
        "der Support erfährt nicht, was ihm fehlt"
    )


def test_an_ordinary_project_gets_no_empty_addition(
    monkeypatch: pytest.MonkeyPatch, qt_app: QApplication
) -> None:
    """Die Gegenrichtung, und sie ist die wichtigere von beiden.

    Die allermeisten Projekte benutzen keinen eigenen Baustein. Stünde hinter
    ihrer Anhangsbeschreibung ein leerer Zusatz, fiele das niemandem auf — und
    ein Hinweis, der immer erscheint, ist keiner mehr. Geprüft wird deshalb auf
    **Gleichheit** und nicht auf „enthält".
    """
    from app.core.knowledge.parts import check as part_check
    from app.i18n import tr

    monkeypatch.setattr(part_check, "check_outgoing", lambda document, registry=None: [])
    dialog = SupportDialog(message="Der Deckel sitzt schief.", session=Session())

    assert dialog._session_note() == tr("Modell, Operationsstapel und Chat-Verlauf")


def test_the_update_check_is_on_and_reaches_older_installations(tmp_path: Path) -> None:
    """Robert am 23.08.2026: „wenn man die app startet sollte überprüft werden
    ob eine neue version vorhanden ist und diese dann bei bestätigung geladen
    werden."

    **Der Anlass ist ein Datum.** Die Demo endet am 30.10.2026, und am Tag des
    Artikels bei 3druck.com wurden 140 Pakete geladen. Stand der Schalter
    weiter aus, laufen diese Installationen an jenem Tag ab, ohne dass die
    Anwendung je einen Weg zur nächsten Fassung gezeigt hätte.

    **Die Vorgabe allein reicht nicht, und das ist der eigentliche Punkt.**
    ``save_settings`` schreibt jedes Feld, ``load_settings`` liest jedes
    vorhandene zurück — jede Installation, die einmal beendet wurde, trägt
    ``"check_for_updates": false`` wörtlich in ihrer Datei. Eine geänderte
    Vorgabe erreicht sie nie; der Wert in der Datei schlägt sie. Deshalb hebt
    das Laden den Wert **einmal** an und merkt sich, dass es das getan hat.

    Was §37.2 verlangt, bleibt: Geprüft wird beim Start, geladen erst auf
    Klick, gestartet erst nach dem Schließen. Die Bestätigung gilt dem Laden,
    nicht der Prüfung — so hat Robert es gesagt.
    """
    from app.ui import settings as settings_module

    assert UiSettings().check_for_updates is True, "neue Installationen prüfen"

    # Eine Datei aus 0.1.3: der Schalter steht wörtlich auf false.
    ziel = tmp_path / "settings.json"
    ziel.write_text(
        json.dumps({"check_for_updates": False, "display_unit": "in"}), encoding="utf-8"
    )
    with mock.patch.object(settings_module, "settings_path", lambda: ziel):
        geladen = settings_module.load_settings()
        assert geladen.check_for_updates is True, "die alte Datei wird einmal angehoben"
        assert geladen.display_unit == "in", "alles andere bleibt, wie es war"

        # Und wer ihn danach ausschaltet, behält ihn aus — sonst wäre die
        # Anhebung keine Migration, sondern eine Bevormundung bei jedem Start.
        geladen.check_for_updates = False
        settings_module.save_settings(geladen)
        assert settings_module.load_settings().check_for_updates is False


def test_the_report_carries_the_digest_of_the_scene(qt_app: QApplication) -> None:
    """Ohne Maße lässt sich ein Kundenfehler nicht entscheiden.

    **Roberts Auftrag vom 23.08.2026** zum ersten Kundenprotokoll: „wenn du
    mehr brauchst, passe die Fehlermeldung an." Gebraucht wurde es zweimal am
    selben Tag — der ``thicken``-Fehler war nur über das Bildschirmfoto zu
    finden, und ob drei Wülste (34,09 · 34,06 · 34,03 mm) drei Kanten sind oder
    eine dreimal erkannte, ließ sich gar nicht entscheiden: Die Maße standen
    nirgends.

    **Der Steckbrief und nicht die Projektdatei.** Er nennt Objekte mit Maßen,
    Merkmale, Parameter, Passungen und den Verlauf mit seinen Werten — als
    Text. Die Projektdatei sagte alles, enthält aber die Geometrie und reist
    deshalb nur auf ausdrücklichen Wunsch mit (§37.2). Der Mittelweg gibt uns
    die Diagnose und dem Kunden sein Modell.
    """
    import sys

    sys.path.insert(0, "tests")
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene
    from app.ui.support_dialog import KIND_BUG, SupportDialog
    from conftest import make_object

    session = Session()
    session.last_result = EvaluationResult(scene=Scene(objects={"o1": make_object(name="Halter")}))

    dialog = SupportDialog(kind=KIND_BUG, session=session)
    dialog.message.setPlainText("Etwas ging schief.")
    bericht = dialog.report()

    assert bericht.digest, "der Steckbrief fehlt im Bericht"
    assert "Halter" in bericht.digest, f"und er kennt die Szene nicht: {bericht.digest[:120]!r}"

    # **Und ohne Sitzung bleibt er leer, statt zu scheitern.** Der
    # Fehlerbericht ist der Weg, den jemand nimmt, wenn schon etwas kaputt ist;
    # er darf an einer fehlenden Auskunft nicht selbst scheitern.
    ohne = SupportDialog(kind=KIND_BUG, session=None)
    ohne.message.setPlainText("x")
    assert ohne.report().digest == ""
    dialog.release()
    ohne.release()


def test_the_preview_shows_the_log_it_sends(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Vorher sieht er, was mitgeht" gilt auch fürs vorangekreuzte Protokoll.

    In der Vorschau standen Name und Größe; mitgereist wären die Zeilen —
    samt Dateipfaden, in denen der Windows-Kontoname steht. Textanhänge
    stehen jetzt im Wortlaut in der Vorschau.
    """
    from app.ui import support_dialog
    from app.ui.support_dialog import KIND_BUG, SupportDialog

    zeile = "error report written to C:/Users/beispielkonto/bericht-1"
    monkeypatch.setattr(support_dialog, "log_tail", lambda: zeile.encode("utf-8"))

    dialog = SupportDialog(kind=KIND_BUG, session=None)
    dialog.message.setPlainText("Etwas ging schief.")
    dialog._refresh()
    try:
        assert dialog.with_log.isChecked(), "vorangekreuzt — genau darum geht es"
        assert zeile in dialog.preview.toPlainText()
    finally:
        dialog.release()


@pytest.fixture
def own_feedback_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Der Stand des Bogens gehört diesem Test allein.

    Die Suite biegt die Nutzerverzeichnisse schon in einen Temp-Ordner (§38),
    aber **alle** Tests teilen ihn — und ``feedback.json`` merkt sich, wie oft
    schon gefragt wurde. Ohne diese Zeile las der dritte Test, was der erste
    hinterlassen hatte, und die Reihenfolge entschied über den Ausgang.
    """
    monkeypatch.setattr(feedback, "user_config_dir", lambda: tmp_path)


def test_the_survey_asks_with_a_card_and_not_with_a_window(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, own_feedback_state: None
) -> None:
    """Der Bogen meldet sich nach dreißig Minuten Arbeit — und zwar leise.

    **Robert am 23.08.2026:** nach einer halben Stunde Nutzung ein kleiner
    Bogen, was gut ist und was bis zum Release fehlt.

    Drei Eigenschaften, und jede hat einen Grund:

    * **Kein Fenster, sondern eine Karte über der Ansicht.** Der Hinweis kommt
      mitten in die Arbeit, und ein Dialog hält sie an — er wird weggeklickt,
      ohne gelesen zu werden, und die Rückmeldung ist damit verloren.
    * **Der Bogen geht erst auf Klick auf.** Gefragt wird zuerst, ob überhaupt
      gefragt werden darf.
    * **Nur in der Demo** (``activation.state().in_demo``): Wer bezahlt hat,
      ist kein Testleser mehr.

    Geprüft wird am **gebauten Fenster** und nicht am Quelltext: Die erste
    Fassung dieses Tests las nach Zeichenketten, und was sie sicherte, war die
    Schreibweise und nicht das Verhalten.
    """
    from app.core.support import KIND_SURVEY

    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(days_left=68, deadline=date(2026, 10, 30)),
    )
    window = MainWindow(Session(), UiSettings())
    try:
        assert not window._survey_notice.isVisible(), "vor der Zeit steht nichts da"

        window._offer_survey()

        assert window._survey_notice.isVisibleTo(window.viewport), (
            "die Karte liegt über der Ansicht"
        )
        assert window._survey_dialog is None, "der Bogen geht erst auf Klick auf"

        opened: list[SupportDialog] = []
        monkeypatch.setattr(SupportDialog, "show", lambda self: opened.append(self))
        window._survey_notice.give.click()

        assert opened, "der Knopf öffnet den Bogen"
        assert opened[0].ticket().kind == KIND_SURVEY
        assert opened[0].survey is not None, "und zwar mit den Fragen darin"
        opened[0].release()
    finally:
        window.close()


def test_saying_no_to_the_survey_holds(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, own_feedback_state: None
) -> None:
    """*Nein danke* ist eine Antwort, und sie gilt dauerhaft."""
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(days_left=68, deadline=date(2026, 10, 30)),
    )
    window = MainWindow(Session(), UiSettings())
    try:
        window._offer_survey()
        window._survey_notice.no.click()

        assert not window._survey_notice.isVisible()
        assert feedback.read().declined, "gefragt wird nicht mehr"
        assert not feedback.due()
    finally:
        window.close()


def test_nobody_is_asked_while_the_window_is_calculating(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, own_feedback_state: None
) -> None:
    """Wer auf ein Ergebnis wartet, hat für eine Frage keinen Kopf.

    Und die Einladung ist damit nicht verbraucht: Die Uhr läuft weiter und
    meldet sich in einer Minute wieder. Ein Bogen, der ausgerechnet in eine
    lange Rechnung fällt, wäre sonst für die ganze Sitzung verloren.
    """
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(days_left=68, deadline=date(2026, 10, 30)),
    )
    window = MainWindow(Session(), UiSettings())
    try:
        monkeypatch.setattr(type(window.session), "busy", property(lambda self: True))

        window._offer_survey()

        assert not window._survey_notice.isVisibleTo(window.viewport), "nicht jetzt"
        assert feedback.read().invitations == 0, "und die Einladung ist nicht verbraucht"
    finally:
        window.close()


def test_the_language_from_the_first_steps_applies_at_once(qt_app: object) -> None:
    """§38: Wer beim ersten Start eine Sprache wählt, bekommt sie sofort.

    „Erste Schritte" fragt als Erstes nach der Sprache, und bis zum 25.08.2026
    stand darunter: „Eine andere Sprache erscheint beim nächsten Start." Wer
    Español wählte, sah weiter ein deutsches Fenster — ausgerechnet beim ersten
    Eindruck, und ausgerechnet der, der die Sprache am dringendsten braucht.

    **Übersetzen ließ sich das laufende Fenster nicht.** Die Oberfläche holt
    ihre Texte über ``tr()``, und das übersetzt sofort: Was einmal in einem
    Menüeintrag steht, bleibt stehen. Gemessen an einem gebauten Fenster waren
    nach einem Sprachwechsel **170 von 170** sichtbaren Texten unverändert.
    Deshalb baut ``rebuild_for_language`` das Fenster neu, mit derselben
    Sitzung — das Dokument überlebt.
    """
    from PySide6.QtWidgets import QApplication

    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.app import rebuild_for_language

    def menu_titles(win: MainWindow) -> list[str]:
        return [entry.text().replace("&", "") for entry in win.menuBar().actions()]

    install_language("de")
    set_language("de")
    settings = UiSettings()
    settings.language = "de"
    window = MainWindow(Session(), settings)
    try:
        german = menu_titles(window)
        assert "Datei" in german, german

        # Was der Dialog täte: die Wahl in die Einstellungen schreiben.
        settings.language = "pt"
        application = QApplication.instance()
        assert application is not None
        window = rebuild_for_language(application, window, settings)

        portuguese = menu_titles(window)
        assert "Datei" not in portuguese, (
            f"the menu bar still speaks German after switching: {portuguese}"
        )
        assert portuguese and portuguese != german, portuguese
    finally:
        window.close()
        window.deleteLater()
        install_language("de")
        set_language("de")


def test_the_rebuilt_window_keeps_the_work(qt_app: object) -> None:
    """Ein Sprachwechsel darf nichts wegwerfen.

    Das Fenster wird neu gebaut, die **Sitzung** nicht: Dokument, Stapel und
    Auswahl hängen an ihr und wandern mit. Ohne diese Zusage wäre der
    sofortige Wechsel schlimmer als der Hinweis, den er ersetzt — wer beim
    ersten Start etwas geladen und dann die Sprache umgestellt hätte, stünde
    vor einem leeren Fenster.
    """
    from PySide6.QtWidgets import QApplication

    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.app import rebuild_for_language

    install_language("de")
    set_language("de")
    settings = UiSettings()
    settings.language = "de"
    session = Session()
    window = MainWindow(session, settings)
    try:
        before = session.project.document

        settings.language = "fr"
        application = QApplication.instance()
        assert application is not None
        window = rebuild_for_language(application, window, settings)

        assert window.session is session, "the rebuilt window got a different session"
        assert window.session.project.document is before, "the document did not survive"
    finally:
        window.close()
        window.deleteLater()
        install_language("de")
        set_language("de")


def test_the_rebuilt_window_shows_the_work_it_kept(qt_app: object) -> None:
    """Behalten reicht nicht — zeigen.

    Die Sitzung wanderte mit, das Fenster zeigte sie nicht: Der Konstruktor
    endet auf dem Startbildschirm, und ``_connect_session`` verbindet nur
    künftige Signale. Nach einem Sprachwechsel mit offenem Projekt stand der
    Startbildschirm über einem unsichtbaren Dokument — bis zufällig die
    nächste Auswertung lief. ``rebuild_for_language`` übernimmt den Stand
    deshalb selbst: Ansicht statt Startbildschirm, Dokument in den Panels,
    letzte Auswertung im Baum.
    """
    from PySide6.QtWidgets import QApplication

    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.app import rebuild_for_language

    meshes = Path(__file__).parent / "data" / "meshes"

    install_language("de")
    set_language("de")
    settings = UiSettings()
    settings.language = "de"
    window = MainWindow(Session(), settings)
    try:
        window.open_path(meshes / "cube_clean.stl")
        window.session.wait_for_idle()
        assert window.session.last_result is not None, "ohne Auswertung prüft der Test nichts"

        settings.language = "it"
        application = QApplication.instance()
        assert application is not None
        window = rebuild_for_language(application, window, settings)

        assert window.stack.currentWidget() is window.overlay, (
            "das offene Projekt gehört in die Ansicht, nicht hinter den Startbildschirm"
        )
        assert window.object_tree.tree.topLevelItemCount() == 1, (
            "die letzte Auswertung fehlt im Objektbaum"
        )
        assert window.history_panel.list.count() > 0, "der Verlauf blieb leer"
    finally:
        # Kein ``close()``: Die Sitzung ist durch den Import „geändert", und
        # der ``closeEvent`` stellte die Ungesichert-Frage — modal, und im
        # Offscreen-Lauf beantwortet sie niemand (45 Minuten gemessen: nie).
        window.release()
        window.deleteLater()
        install_language("de")
        set_language("de")


def test_the_first_start_speaks_the_language_of_the_system(monkeypatch: Any) -> None:
    """Ein portugiesisches Windows bekommt keine deutsche Anwendung.

    Die Vorgabe war ``SOURCE_LANGUAGE`` — also Deutsch, gleich was das System
    spricht und gleich was der Installer gefragt hat. Wer den Installer auf
    Portugiesisch durchklickte, sah danach ein deutsches Fenster und wurde in
    „Erste Schritte" ein zweites Mal nach derselben Sache gefragt.

    Geprüft wird die Reihenfolge der drei Quellen, denn sie ist die Aussage:
    Was der Nutzer im Installer **gewählt** hat, wiegt schwerer als das, was
    sein System spricht.
    """
    from app.i18n import SOURCE_LANGUAGE
    from app.ui import settings as settings_module

    monkeypatch.setattr(settings_module, "system_language", lambda: "fr")
    monkeypatch.setattr(settings_module, "installed_language", lambda: None)
    assert settings_module.initial_language() == "fr", "the system language was ignored"

    monkeypatch.setattr(settings_module, "installed_language", lambda: "pt")
    assert settings_module.initial_language() == "pt", (
        "the installer's choice must outweigh the system — someone who set the "
        "installer to Portuguese on a French machine meant Portuguese"
    )

    # Eine Sprache, für die es keinen Katalog gibt, zählt nicht.
    monkeypatch.setattr(settings_module, "installed_language", lambda: "sv")
    assert settings_module.initial_language() == "fr", (
        "an unknown installer language must fall through to the system"
    )

    monkeypatch.setattr(settings_module, "system_language", lambda: None)
    monkeypatch.setattr(settings_module, "installed_language", lambda: None)
    assert settings_module.initial_language() == SOURCE_LANGUAGE


def test_the_system_language_is_only_taken_when_it_can_be_spoken(qt_app: object) -> None:
    """Eine Sprache ohne Katalog ist keine Wahl.

    ``QLocale.system().uiLanguages()`` liefert eine Liste von Kennungen
    (``['de-Latn-DE', 'de-DE', 'de-Latn', 'de']`` auf einem deutschen Windows),
    und gebraucht wird der Anfang. Fehlt der Katalog dazu, muss ``None``
    herauskommen — sonst startete die Anwendung mit einer Sprache, in der sie
    nichts zu sagen hat.
    """
    from app.i18n.catalog import available_languages
    from app.ui.settings import system_language

    found = system_language()
    assert found is None or found in set(available_languages()), (
        f"system_language() returned {found!r}, which has no catalogue"
    )


def test_the_installer_and_the_application_use_the_same_language_codes() -> None:
    """Zwischen Installer und Anwendung liegt keine Übersetzungstabelle.

    Die ``[Languages]``-Namen im Inno-Skript **sind** die Kürzel aus
    ``app/i18n/locales`` — nicht „german"/„english". Sonst bräuchte es eine
    Zuordnung, und die wäre beim siebten Katalog die Stelle, an der jemand das
    Nachziehen vergisst. Der Installer schreibt ``ActiveLanguage()`` roh in die
    Datei, die der erste Start liest.
    """
    import re

    from app.i18n.catalog import available_languages

    script = (Path(__file__).parent.parent / "packaging" / "solidon3d.iss").read_text(
        encoding="utf-8"
    )
    section = script.split("[Languages]", 1)[1].split("[", 1)[0]
    names = set(re.findall(r'Name:\s*"([^"]+)"', section))
    known = set(available_languages())

    assert names, "the installer offers no languages at all"
    assert names <= known, (
        f"the installer offers {sorted(names - known)}, which the application cannot speak"
    )
    assert known <= names, (
        f"the application speaks {sorted(known - names)}, which the installer does not offer"
    )


def test_a_language_change_from_the_settings_swaps_the_window(qt_app: object) -> None:
    """Derselbe Weg aus den Einstellungen, nur über ein Signal.

    Der Erststart-Weg kann die Sprache nach ``start()`` einfach ablesen; ein
    Wechsel mitten im Betrieb kommt dagegen aus einem Dialog des Fensters
    selbst. Deshalb meldet ``MainWindow.languageChanged``, und der Austausch
    wartet einen Ereignisdurchlauf ab: Ein Fenster, das sich mitten in einem
    Signal aus einem seiner eigenen Dialoge ersetzt, zöge dem Signal den Boden
    weg.

    Geprüft wird beides — dass getauscht wird, und dass der Halter danach am
    **neuen** Fenster hängt. Bliebe er am alten, wirkte der Wechsel genau
    einmal.
    """
    from PySide6.QtWidgets import QApplication

    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.app import _LanguageSwitch

    install_language("de")
    set_language("de")
    settings = UiSettings()
    settings.language = "de"
    window = MainWindow(Session(), settings)
    application = QApplication.instance()
    assert application is not None
    switch = _LanguageSwitch(application, window)
    window.languageChanged.connect(switch.arm)
    try:
        assert "Datei" in [a.text().replace("&", "") for a in window.menuBar().actions()]

        settings.language = "pt"
        window.languageChanged.emit()
        application.processEvents()

        fresh = switch._window
        assert fresh is not window, "the window was not swapped"
        titles = [a.text().replace("&", "") for a in fresh.menuBar().actions()]
        assert "Datei" not in titles, f"the new window still speaks German: {titles}"

        # Und der Halter hängt am neuen Fenster, nicht am abgebauten.
        settings.language = "fr"
        fresh.languageChanged.emit()
        application.processEvents()
        assert switch._window is not fresh, (
            "the holder stayed with the old window — the swap would work only once"
        )
        switch._window.close()
        switch._window.deleteLater()
    finally:
        install_language("de")
        set_language("de")
