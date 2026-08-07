"""Erstinbetriebnahme, Fehlerbericht und Aktualisierungshinweis (Bauplan §38, §37.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import report as reports
from app.core import tools, updates
from app.core.backends import llm

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.ui.first_run import FirstRunDialog, should_run
from app.ui.main_window import MainWindow
from app.ui.report_dialog import ErrorReportDialog
from app.ui.session import Session
from app.ui.settings import UiSettings

# --- external programs (§38) ---------------------------------------------------------


def test_the_survey_names_every_tool_and_what_it_is_for() -> None:
    """§38: eingerichtet, nicht mitgeliefert — die Anwendung muss also sagen,
    was da ist.
    """
    found = tools.survey()

    assert {state.tool.id for state in found} == {"openscad", "slicer", "ollama", "comfyui"}
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


# --- the first run (§38) --------------------------------------------------------------


def test_the_first_run_happens_once(qt_app: QApplication) -> None:
    settings = UiSettings()

    assert should_run(settings)
    settings.first_run_done = True
    assert not should_run(settings)


def test_the_first_run_asks_the_four_things(qt_app: QApplication) -> None:
    """§38: language, printer, material, external programs."""
    dialog = FirstRunDialog(UiSettings())

    assert dialog.language.count() >= 2
    assert dialog.printer.count() >= 1
    assert dialog.material.count() >= 1
    # Die Programme stehen als Zeilen da, nicht mehr als ein Textblock: eine
    # je Programm, mit Zeichen, Zustand und Zweck.
    from PySide6.QtWidgets import QLabel

    shown = " ".join(label.text() for label in dialog.tools.findChildren(QLabel))
    assert "OpenSCAD" in shown
    assert dialog.open_button.text().startswith("Modell")


def test_the_first_run_offers_the_chat_setup(qt_app: QApplication) -> None:
    """Der Chat ist das Versprechen, mit dem die Anwendung antritt — der Weg
    dorthin gehört in den ersten Start, nicht nur in ein Panel, das ein neuer
    Nutzer noch nie gesehen hat.
    """
    dialog = FirstRunDialog(UiSettings())

    assert dialog.chat_button.text().startswith("Chat")
    assert dialog.chat_state.text().strip()


def test_the_chat_line_says_what_is_missing(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Zugang steht da, was fehlt und dass alles andere ohne funktioniert
    — nicht der Zustand der Entwicklermaschine.
    """
    monkeypatch.setattr(llm, "first_available", lambda: None)

    dialog = FirstRunDialog(UiSettings())

    assert "Sprachmodell" in dialog.chat_state.text()
    assert "funktioniert" in dialog.chat_state.text()


def test_the_chat_line_names_the_ready_backend(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein bereites Backend wird beim Namen genannt — „bereit" allein wäre
    eine Behauptung ohne Adresse.
    """
    monkeypatch.setattr(llm, "first_available", lambda: llm.OllamaBackend())

    dialog = FirstRunDialog(UiSettings())

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


# --- the error report (§37.2) ---------------------------------------------------------


def test_a_report_carries_the_versions() -> None:
    entry = reports.environment()

    assert entry["app"].startswith("Solidon")
    assert entry["python"]
    assert "trimesh" in entry


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


def test_the_dialog_offers_the_attachment_and_writes_a_folder(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "projekt.p3d"
    project.write_bytes(b"x")
    monkeypatch.setattr(reports, "user_data_dir", lambda: tmp_path)

    dialog = ErrorReportDialog(summary="Fehler", error=ValueError("kaputt"), project=project)
    dialog.with_project.setChecked(True)
    dialog._write()

    assert dialog.written is not None and dialog.written.is_dir()
    text = (dialog.written / "bericht.txt").read_text(encoding="utf-8")
    assert "kaputt" in text
    assert "Geometrie" in text


# --- the update notice (§37.2) --------------------------------------------------------


def test_a_newer_version_is_recognised() -> None:
    assert updates.Release(version="0.9.0").newer_than("0.0.1")
    assert not updates.Release(version="0.0.1").newer_than("0.0.1")
    assert not updates.Release(version="0.0.1").newer_than("0.1.0")


def test_the_check_reads_the_version_file() -> None:
    def answer(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {"version": "1.2.3", "url": "https://example.invalid/download"}

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


def test_the_check_is_off_until_it_is_switched_on() -> None:
    """§37.2: eine Anfrage, die den Rechner verlässt, ist eine Entscheidung,
    keine Vorgabe.
    """
    assert UiSettings().check_for_updates is False


def test_nothing_is_downloaded() -> None:
    """Ein Hinweis mit einem Link — nie ein automatisches Update."""
    import inspect

    source = inspect.getsource(updates)

    assert "urlretrieve" not in source
    assert "subprocess" not in source
