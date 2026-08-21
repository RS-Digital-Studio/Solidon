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
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.support_dialog import SupportDialog

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


# --- der Fehlerbericht (§37.2) --------------------------------------------------------


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


def test_the_first_run_says_the_language_waits_for_a_restart(qt_app: QApplication) -> None:
    """Der Erststart nahm eine andere Sprache stumm an.

    Der Katalog wird beim Start installiert; wer hier „Español" wählt, sieht
    danach weiter eine deutsche Oberfläche. Der Einstellungsdialog sagt das seit
    je mit demselben Satz — an der Stelle, an der die Sprache zum ersten Mal
    überhaupt gewählt wird, stand er nicht, und eine Einstellung ohne sichtbare
    Wirkung sieht kaputt aus, nicht aufgeschoben.

    Bei der eigenen Sprache bleibt der Hinweis weg: Wer nichts ändert, braucht
    keine Ankündigung.
    """
    settings = UiSettings()
    dialog = FirstRunDialog(settings)
    assert not dialog.language_note.isVisible(), "ohne Änderung gibt es nichts anzukündigen"

    other = next(
        index
        for index in range(dialog.language.count())
        if str(dialog.language.itemData(index)) != settings.language
    )
    dialog.language.setCurrentIndex(other)
    assert not dialog.language_note.isHidden(), "die andere Sprache wird stumm angenommen"

    back = dialog.language.findData(settings.language)
    dialog.language.setCurrentIndex(back)
    assert dialog.language_note.isHidden(), "zurückgestellt bleibt der Hinweis nicht stehen"
