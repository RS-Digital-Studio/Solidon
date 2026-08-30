"""Fehlendes installieren, aus der Anwendung heraus (§36, §38).

Der interessante Teil dieser Datei ist, was sie verbietet. Ein Installer, dem
sich sagen lässt, was er holen soll, ist ein Weg, beliebige Software auf
jemandes Rechner auszuführen — die Namen leben also im Quelltext, und nichts
sonst erreicht je eine Befehlszeile.

Der zweite Teil kam mit den drei Paketverwaltungen dazu. Geprüft wird jede von
Windows aus, mit gesetzter Plattform: Ein Lauf auf einem Mac steht hier nicht
zur Verfügung, die Befehlszeile, die dort entstünde, schon.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core import install, tools
from app.ui.install_dialog import InstallDialog


def by_id(identifier: str) -> install.Requirement:
    return next(entry for entry in install.REQUIREMENTS if entry.id == identifier)


class FakeProcess:
    """Ein Installer, der aus einem Skript antwortet statt aus dem Netz.

    Gebraucht wird die Form, die ``install._stream`` erwartet: ein
    Kontextmanager mit ``stdout`` zum Zeilenlesen und ``wait``. Gestartet wird
    seit dem streamenden Lauf über ``Popen`` — die Tests patchten ``run``, und
    damit prüfte „nichts startet von selbst" nichts mehr.
    """

    def __init__(self, lines: tuple[str, ...] = (), code: int = 0) -> None:
        self.stdout = iter(lines)
        self._code = code

    def __enter__(self) -> FakeProcess:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def wait(self) -> int:
        return self._code

    def kill(self) -> None:
        return None


def watch_popen(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> list[object]:
    """Merkt jeden Start und antwortet mit der Attrappe."""
    started: list[object] = []

    def fake(command: object, **_options: object) -> FakeProcess:
        started.append(command)
        return FakeProcess(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install.subprocess, "Popen", fake)
    return started


# --- Was wo ist -------------------------------------------------------------------


def test_a_package_that_is_here_is_found() -> None:
    assert install.present(by_id("keyring")), "the agent extra is installed in this environment"


def test_a_package_that_is_not_here_is_not_invented() -> None:
    absent = install.Requirement(
        id="ghost", title="Ghost", what_for="", kind="package", module="not_a_real_module"
    )

    assert not install.present(absent)


def test_missing_lists_only_what_is_absent() -> None:
    absent = install.missing()

    assert all(not install.present(entry) for entry in absent)
    assert set(absent) <= set(install.REQUIREMENTS)


def test_every_requirement_says_what_it_is_for_and_where_it_comes_from() -> None:
    for entry in install.REQUIREMENTS:
        assert str(entry.what_for), entry.id
        assert entry.url.startswith("https://"), entry.id
        assert entry.kind in ("package", "program"), entry.id


# --- die Kommandozeile ----------------------------------------------------------


def test_a_package_is_installed_into_this_interpreter() -> None:
    """Nie ein nacktes „pip": welche Umgebung das wäre, kann jeder raten."""
    import sys

    command = install._command(by_id("vhacd"))

    assert command[:4] == [sys.executable, "-m", "pip", "install"]
    assert command[-1] == "vhacdx"


def test_a_program_goes_through_the_system_package_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Plattform wird gesetzt, nicht vorausgesetzt.

    Ohne die beiden Zeilen prüfte dieser Test, was auf dem Rechner zufällig
    liegt. Auf dem Linux-Runner der CI liegt kein Flatpak, also gab es dort
    überhaupt keine Verwaltung, und ``_command`` warf ``ValueError`` statt zu
    antworten — ein roter Lauf ohne einen Befund, und seit dem 21.08.2026
    stand der Paketier-Job deshalb still. Der Rest der Datei setzt die
    Plattform seit jeher; der Modulkopf sagt auch, warum.
    """
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.setattr(install.shutil, "which", lambda name: name)

    command = install._command(by_id("slicer"))

    assert "winget" in command[0]
    assert "--id" in command and "SoftFever.OrcaSlicer" in command
    assert "--disable-interactivity" in command, "an installer must not wait for a keypress"


def names_of(entry: install.Requirement) -> set[str]:
    """Jede Kennung, die diese Datei diesem Eintrag gibt — über alle Verwaltungen."""
    return {
        part
        for part in (entry.package, entry.winget, entry.flatpak, *entry.brew)
        if part and not part.startswith("--")
    }


def test_a_silent_installer_still_hits_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """TIMEOUT_SECONDS griff nur, wenn der Installer etwas schrieb.

    Ein stiller winget oder brew hing unbegrenzt: Die Frist wurde erst nach
    der nächsten Zeile geprüft, und die kam nie — der Arbeiter-Thread
    überlebte sein Fenster. Jetzt wartet die Uhr, nicht die Zeile.
    """
    import subprocess
    import sys
    import time

    monkeypatch.setattr(install, "TIMEOUT_SECONDS", 0.5)
    begin = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        install._stream([sys.executable, "-c", "import time; time.sleep(5)"], lambda line: None)
    assert time.monotonic() - begin < 4.0, "die Frist beendet den Lauf, nicht das Kind"


def test_the_names_come_from_this_file_and_nowhere_else() -> None:
    """Die Regel, die dieses Feature sicher macht — als Test gehalten, nicht
    als Kommentar.

    Zwei Aussagen, und beide über jede Verwaltung: Im Befehl steht eine
    Kennung dieses Eintrags, und die eines anderen steht nicht darin. Eine
    Kennung, die allein unter Homebrew aus einer fremden Quelle stammte, wäre
    sonst nicht zu sehen — geprüft wurde bis hierhin nur ``winget``.
    """
    for chosen in install.MANAGERS:
        for entry in install.REQUIREMENTS:
            wanted = entry.identifier(chosen)
            if not wanted:
                continue
            # Die Flatpak-Kennung reist als Adresse einer Referenzdatei, ist
            # also Teil eines Wortes und nicht selbst eines. Gesucht wird
            # deshalb im Text und nicht in der Liste.
            command = " ".join(chosen.command(wanted))
            own = names_of(entry)
            assert any(name in command for name in own), f"{entry.id}/{chosen.id}: keine Kennung"
            for other in install.REQUIREMENTS:
                for name in names_of(other) - own:
                    assert name not in command, f"{entry.id}/{chosen.id}: fremdes {name}"


def test_a_package_never_goes_through_the_system_package_manager() -> None:
    """Ein Python-Paket geht in den Interpreter, nie an das System.

    Die Zuordnung hing an einem einzigen Feld: ``package`` trug den pip-Namen
    *und* die winget-Kennung. Beides auseinanderzuhalten ist keine Kosmetik —
    ``brew install keyring`` gibt es, und es wäre etwas anderes.
    """
    import sys

    for entry in install.REQUIREMENTS:
        if entry.kind != "package":
            continue
        for chosen in install.MANAGERS:
            assert not entry.identifier(chosen), f"{entry.id} hat eine Systemkennung"
        assert install._command(entry)[0] == sys.executable, entry.id


def test_every_platform_has_a_way_or_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auf macOS und Linux war der ganze Weg eine Sackgasse.

    ``installable`` hing allein an ``winget``; wer Solidon aus einem der
    Linux-Pakete oder von der Mac-Seite hatte, lag damit an jedem der vier
    Programme bei demselben Satz — „Auf diesem System ist keine Paketverwaltung
    gefunden worden" —, unabhängig davon, ob eine fehlte oder ob das Programm
    dort schlicht keine Kennung hat.
    """
    for platform, program in (("win32", "winget"), ("darwin", "brew"), ("linux", "flatpak")):
        monkeypatch.setattr(install.sys, "platform", platform)
        monkeypatch.setattr(
            install.shutil, "which", lambda name, hit=program: name if name == hit else None
        )

        chosen = install.manager()
        assert chosen is not None and chosen.program == program, platform

        offered = [
            entry
            for entry in install.REQUIREMENTS
            if entry.kind == "program" and install.installable(entry)
        ]
        assert offered, f"{platform}: kein einziges Programm installierbar"
        for entry in offered:
            assert install._command(entry)[0] == program, platform
        for entry in install.REQUIREMENTS:
            if entry.kind != "program" or install.installable(entry):
                continue
            assert str(install.why_not(entry)), f"{platform}/{entry.id}: kein Grund"


def test_the_two_reasons_a_program_is_missing_stay_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„Nicht eingerichtet" und „kennt es nicht" sind zwei Auskünfte.

    Zusammengeworfen sagte der Satz einem Mac-Nutzer, ihm fehle Homebrew — für
    ComfyUI, das dort auch mit Homebrew nicht liegt.
    """
    monkeypatch.setattr(install.sys, "platform", "darwin")
    monkeypatch.setattr(install.shutil, "which", lambda name: None)

    ohne_verwaltung = str(install.why_not(by_id("slicer")))
    ohne_kennung = str(install.why_not(by_id("comfyui")))

    assert "brew" in ohne_verwaltung, "der Name der Verwaltung gehört in die Auskunft"
    assert ohne_verwaltung != ohne_kennung, "zwei Ursachen, zwei Sätze"
    assert by_id("slicer").by_hand().startswith("brew install"), "der Befehl zum Abschreiben"
    assert not by_id("comfyui").by_hand(), "wo es keine Kennung gibt, gibt es keinen Befehl"


def test_a_manager_that_needs_a_password_is_not_used() -> None:
    """``apt`` und ``dnf`` fehlen mit Absicht.

    Eine Rechteerhöhung in einem Unterprozess, den niemand sieht, hängt an
    einer Passwortabfrage, bis das Zeitmaß abläuft. Flatpak installiert mit
    ``--user`` und braucht keine.
    """
    assert {entry.program for entry in install.MANAGERS} == {"winget", "brew", "flatpak"}
    flatpak = next(entry for entry in install.MANAGERS if entry.id == "flatpak")
    assert "--user" in flatpak.before, "ohne --user bräuchte es sudo"
    for entry in install.MANAGERS:
        assert "sudo" not in (entry.program, *entry.before, *entry.after)


def test_a_flathub_identifier_becomes_a_reference_file() -> None:
    """Ohne die Referenzdatei bräuchte Flatpak eine eingerichtete Quelle.

    Wer Flathub nicht als Remote hat — auf einer schlanken Installation der
    Normalfall — sähe „remote flathub not found" statt einer Installation. Die
    ``.flatpakref`` bringt Quelle und Laufzeitquelle mit.
    """
    flatpak = next(entry for entry in install.MANAGERS if entry.id == "flatpak")
    slicer = by_id("slicer")

    wanted = slicer.identifier(flatpak)

    assert wanted and wanted[0].endswith(".flatpakref")
    assert slicer.flatpak in wanted[0]
    assert "flathub" not in flatpak.before, "die Quelle steckt in der Datei, nicht im Befehl"


# --- Wenn es nicht geht -----------------------------------------------------------


def test_a_packaged_build_says_why_it_cannot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install, "packaged", lambda: True)
    requirement = by_id("brep")

    assert not install.installable(requirement)
    assert "Paketverwaltung" in str(install.why_not(requirement))


def test_without_a_package_manager_a_program_is_not_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install, "manager", lambda: None)

    assert not install.installable(by_id("slicer"))


def test_something_with_no_installer_at_all_names_its_page() -> None:
    comfy = by_id("comfyui")

    assert not any(comfy.identifier(entry) for entry in install.MANAGERS), "by hand everywhere"
    assert not install.installable(comfy)
    assert comfy.url


def test_installing_the_impossible_does_not_run_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install, "manager", lambda: None)
    ran = watch_popen(monkeypatch)

    result = install.install(by_id("slicer"))

    assert not result.installed
    assert result.reason
    assert ran == [], "nothing was started"


def test_what_is_already_there_is_not_installed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = watch_popen(monkeypatch)

    result = install.install(by_id("keyring"))

    assert result.installed
    assert ran == []


# --- der Dialog -----------------------------------------------------------------


def settled(dialog: InstallDialog, qt_app: QApplication) -> InstallDialog:
    """Wartet die Erhebung ab und lässt ihre Antwort ankommen.

    Über den Weg, den auch das Schließen nimmt, und nicht durch einen Aufruf
    von ``_surveyed``: Die Verbindung über die Thread-Grenze ist Teil dessen,
    was hier zu prüfen ist.
    """
    dialog.wait_for_survey()
    qt_app.processEvents()
    return dialog


def test_the_dialog_lists_everything_with_its_state(qt_app: QApplication) -> None:
    dialog = settled(InstallDialog(), qt_app)

    assert len(dialog.rows) == len(install.shown())
    for row in dialog.rows:
        marker = row.state.text()
        assert marker in ("+", "-"), "readable without colour (§19.1)"
        assert (marker == "+") == install.present(row.requirement)


def test_a_row_says_nothing_before_it_has_looked(qt_app: QApplication) -> None:
    """Vor der Erhebung behauptet die Zeile nichts.

    Sie stand auf „-" und trug einen Installieren-Knopf, ehe jemand
    nachgesehen hatte — bei einer Suche, die auf dieser Maschine drei Sekunden
    braucht, ist das ein Angebot, etwas ein zweites Mal zu installieren.
    """
    dialog = InstallDialog()

    for row in dialog.rows:
        assert row.state.text() == "?", row.requirement.id
        assert row.action.isHidden(), "kein Knopf auf eine Vermutung"
        assert row.status is None

    settled(dialog, qt_app)
    assert all(row.status is not None for row in dialog.rows)


def test_looking_does_not_happen_in_the_gui_thread(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§38: alles Rechnende in einen Arbeiter.

    Gemessen kostete das Öffnen 2,97 Sekunden — Registry, zwei Ebenen
    Installationsordner und je Dienst eine Socket-Probe, alles im
    Oberflächen-Thread und ohne ein Zeichen, dass etwas läuft.
    """
    import threading

    here = threading.get_ident()
    seen: list[int] = []
    real = install.statuses

    def watched() -> tuple[install.Status, ...]:
        seen.append(threading.get_ident())
        return real()

    monkeypatch.setattr(install, "statuses", watched)

    settled(InstallDialog(), qt_app)

    assert seen, "es wurde überhaupt nicht gesucht"
    assert here not in seen, "die Suche lief im Oberflächen-Thread"


def test_a_packaged_build_hides_the_rows_it_cannot_change(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Im Paket reisen die Python-Pakete mit — drei Zeilen ohne Handlung.

    Sie zeigten „vorhanden" und einen Knopf, der von Entwicklungsumgebungen
    sprach, vor den vier Zeilen, um die es geht. Was **fehlt**, bleibt
    sichtbar: Ein Paket ohne OpenCASCADE hat keine Fasen und kein STEP, und
    eine stille Lücke ist das Gegenteil von §36.
    """
    monkeypatch.setattr(install, "packaged", lambda: True)

    kinds = {entry.kind for entry in install.shown()}
    assert "program" in kinds
    for entry in install.shown():
        assert entry.kind == "program" or not install.present(entry), entry.id

    monkeypatch.setattr(install, "present", lambda _entry: False)
    assert len(install.shown()) == len(install.REQUIREMENTS), "eine Lücke wird gemeldet"


def test_a_row_that_cannot_install_explains_itself(qt_app: QApplication) -> None:
    dialog = settled(InstallDialog(), qt_app)

    for row in dialog.rows:
        if install.present(row.requirement) or install.installable(row.requirement):
            continue
        assert not row.action.isEnabled()
        assert row.action.toolTip(), row.requirement.id
        assert row.where.text(), "und sagt, was stattdessen hilft"


def test_nothing_starts_by_itself(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """Der ganze Sinn von §36: eine Anwendung installiert nichts ungefragt."""
    ran = watch_popen(monkeypatch)

    settled(InstallDialog(), qt_app)

    assert ran == []


def test_one_press_installs_everything_that_is_missing(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sieben Knöpfe einzeln zu drücken war die Arbeit, die diese Liste abnimmt.

    Jede Installation lädt herunter und braucht Minuten; wer vier fehlende
    Programme holen wollte, musste viermal wiederkommen. Der Sammelknopf
    ändert nichts an §36 — die Entscheidung bleibt ein Druck, er ordnet nur
    die Reihenfolge.
    """
    wanted = [entry for entry in install.shown() if entry.kind == "program"]
    started: list[str] = []

    def fake_install(requirement: install.Requirement, progress: object = None) -> object:
        started.append(requirement.id)
        return install.InstallResult(requirement=requirement, installed=True)

    monkeypatch.setattr(install, "present", lambda entry: entry.kind != "program")
    monkeypatch.setattr(
        tools,
        "state_of",
        lambda tool: tools.ToolState(tool=tool, path=None, running=False),
    )
    monkeypatch.setattr(install, "installable", lambda entry: entry.kind == "program")
    monkeypatch.setattr(install, "install", fake_install)

    dialog = settled(InstallDialog(), qt_app)
    assert not dialog.all_button.isHidden(), "bei mehr als einem Fehlenden steht er da"

    dialog.all_button.click()
    for _ in range(400):
        qt_app.processEvents()
        if dialog._worker is not None:
            dialog._worker.wait(50)
        if len(started) >= len(wanted):
            break

    assert started == [entry.id for entry in wanted], "jedes einmal, in der Reihenfolge der Liste"


def test_where_it_cannot_install_it_hands_over_the_command(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Auf diesem System geht es nicht" ist keine Auskunft, mit der jemand weiterkommt.

    Die Zeile, die es täte, kennt Solidon — sie steht in ``MANAGERS``. Also
    steht sie da, und ein Knopf legt sie in die Ablage.
    """
    monkeypatch.setattr(install.sys, "platform", "darwin")
    monkeypatch.setattr(install.shutil, "which", lambda name: None)

    dialog = settled(InstallDialog(), qt_app)
    row = next(entry for entry in dialog.rows if entry.requirement.id == "slicer")

    assert not row.copy.isHidden(), "der Befehl gehört an die Stelle, an der es nicht geht"
    assert "brew install" in row.where.text(), "und im Blick, nicht nur in der Ablage"
    row.copy.click()
    from PySide6.QtGui import QGuiApplication

    assert "orcaslicer" in (QGuiApplication.clipboard().text() or "")


def test_a_failed_install_says_what_went_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regel 17 gilt auch hier: „Das hat nicht geklappt." ist keine Antwort.

    Der Kern gab bei einem Fehlschlag nur ``installed=False`` und die rohe
    Ausgabe zurück; der Dialog machte daraus „Das hat nicht geklappt." und
    zeigte davor jede Zeile, die pip oder winget von sich geben. Wer das liest,
    weiß danach weniger als vorher.

    Der Rückgabewert der Paketverwaltung gehört zu den Einzelheiten, nicht in
    den Satz — dort steht er weiterhin, für den, der ihn weitergeben will.
    """
    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    watch_popen(
        monkeypatch,
        lines=("ERROR: Could not find a version that satisfies the requirement\n",),
        code=1,
    )

    result = install.install(by_id("vhacd"))

    assert not result.installed
    assert result.reason, "ein Fehlschlag ohne Grund sagt nur, dass etwas nicht ging"
    assert "1" in result.output, "der Rückgabewert gehört in die Einzelheiten"
    satz = str(result.reason)
    assert "ERROR:" not in satz, "die rohe Ausgabe gehört nicht in den Satz"


def test_a_package_manager_that_will_not_start_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch der Ausfall vor dem ersten Befehl trägt einen Satz."""

    def kaputt(*args: object, **kwargs: object) -> None:
        raise OSError("nicht gefunden")

    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    monkeypatch.setattr(install.subprocess, "Popen", kaputt)

    result = install.install(by_id("vhacd"))

    assert not result.installed
    assert result.reason


def test_hitting_the_deadline_is_not_the_same_as_never_starting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei Lagen, zwei Sätze — und eine davon dauert eine Viertelstunde.

    ``TimeoutExpired`` erbt von ``SubprocessError`` und fiel damit in dieselbe
    Klausel wie ein Fehlstart. Wer eine Installation anstieß und nach fünfzehn
    Minuten „Die Paketverwaltung ließ sich nicht starten." las, bekam die
    Auskunft, die am wenigsten zutraf: Sie war gestartet, sie lief, und sie ist
    mitten in der Arbeit beendet worden — womöglich mit einer halb fertigen
    Installation auf der Platte.

    Geprüft wird gegen den **anderen** Satz und nicht nur auf „irgendein
    Grund": Vor der Trennung war auch dieser Test grün gewesen.
    """
    import subprocess

    def hangs(*_args: object, **_options: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["winget"], timeout=install.TIMEOUT_SECONDS)

    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    monkeypatch.setattr(install.subprocess, "Popen", hangs)

    result = install.install(by_id("vhacd"))
    said = str(result.reason)

    assert not result.installed
    assert "starten" not in said, "sie ist gestartet — genau das ist der Unterschied"
    assert str(int(install.TIMEOUT_SECONDS // 60)) in said, "wie lange gewartet wurde, zählt"
    assert "halb fertig" in said, "eine angefangene Installation gehört benannt"
    assert "Versuch" in said, "Regel 17: was jetzt möglich ist"


def test_what_needs_a_second_step_says_so_and_has_a_button(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Installiert war bei zwei Einträgen erst die Hälfte.

    Ollama bringt kein Modell mit und läuft nicht zwangsläufig; ComfyUI kennt
    die Knoten nicht und hat das Modell nicht. Beides stand in einem Satz, und
    einer dieser Sätze nannte „«python tools/setup_comfyui.py»" — eine Datei,
    die im Paket nicht existiert.
    """
    monkeypatch.setattr(install, "present", lambda _entry: True)
    monkeypatch.setattr(
        tools,
        "state_of",
        lambda tool: tools.ToolState(tool=tool, path=Path(f"{tool.id}.exe"), running=False),
    )

    dialog = settled(InstallDialog(), qt_app)
    with_follow_up = {row.requirement.id for row in dialog.rows if not row.follow.isHidden()}

    assert with_follow_up == {"ollama", "comfyui"}
    for row in dialog.rows:
        if row.requirement.follow_up:
            assert str(row.requirement.follow_up_title), row.requirement.id
            assert row.follow.text() == str(row.requirement.follow_up_title)


def test_the_second_step_stays_hidden_until_the_first_is_done(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Etwas einzurichten, das nicht da ist, geht nicht — also steht der Knopf
    nicht da."""
    monkeypatch.setattr(install, "present", lambda _entry: False)
    monkeypatch.setattr(
        tools,
        "state_of",
        lambda tool: tools.ToolState(tool=tool, path=None, running=False),
    )

    dialog = settled(InstallDialog(), qt_app)

    assert all(row.follow.isHidden() for row in dialog.rows)


def test_every_follow_up_has_somebody_who_does_it() -> None:
    """Ein Knopf ohne Wirkung ist schlimmer als keiner.

    Der Kern benennt den zweiten Schritt, die Oberfläche führt ihn — geprüft
    wird, dass zu jeder Kennung ein Zweig steht.
    """
    import inspect

    from app.ui import install_dialog

    source = inspect.getsource(install_dialog.InstallDialog._follow_up)
    for entry in install.REQUIREMENTS:
        if entry.follow_up:
            assert f'"{entry.follow_up}"' in source, entry.id


def test_an_unexpected_error_does_not_leave_the_list_waiting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Arbeiter, der wirft, sendet sein Ergebnissignal nie.

    Ohne einen Weg heraus blieben die Zeilen auf „?" stehen und der Balken
    lief weiter — für immer. Der Kunde sitzt vor einer Liste, die nichts
    behauptet und nichts tut.
    """

    def refuse() -> tuple[install.Status, ...]:
        raise OSError(13, "Zugriff verweigert")

    monkeypatch.setattr(install, "statuses", refuse)

    dialog = settled(InstallDialog(), qt_app)

    assert dialog.progress.isHidden(), "der Balken behauptet keinen Vorgang mehr"
    assert "schiefgegangen" in dialog.state.text()
    assert not dialog.details_button.isHidden(), "und die Zeile steht hinter „Details“"


def test_an_unexpected_error_during_an_install_frees_the_buttons(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dasselbe während einer Installation: die Knöpfe waren gesperrt.

    ``_busy(True)`` sperrt jede Zeile, und ohne ein Ergebnissignal blieb es
    dabei — die Liste war für den Rest der Sitzung unbenutzbar.
    """
    monkeypatch.setattr(install, "present", lambda _entry: False)
    monkeypatch.setattr(install, "installable", lambda _entry: True)

    def refuse(requirement: object, progress: object = None) -> object:
        raise RuntimeError("winget ist verschwunden")

    monkeypatch.setattr(install, "install", refuse)
    dialog = settled(InstallDialog(), qt_app)
    row = dialog.rows[0]

    row.action.click()
    for _ in range(200):
        qt_app.processEvents()
        if dialog._worker is None:
            break
        dialog._worker.wait(20)
    qt_app.processEvents()

    assert "schiefgegangen" in dialog.state.text()
    assert dialog.progress.isHidden()
    assert not dialog._queue, "und die Reihe ist geleert, nicht halb abgearbeitet"


def test_the_installer_reports_while_it_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Vorher kam die Rückmeldung erst am Ende.**

    ``subprocess.run`` sammelt die Ausgabe und gibt sie zurück, wenn der
    Prozess fertig ist — die Fortschrittszeilen wurden also erst durchgereicht,
    wenn niemand sie mehr brauchte. Bei OrcaSlicer sind das mehrere Minuten, in
    denen ein unbestimmter Balken lief und sonst nichts geschah.
    """
    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    seen: list[str] = []

    def watched(command: object, **_options: object) -> FakeProcess:
        # Der Zeitpunkt ist die ganze Aussage: Was der Prozess sagt, ist beim
        # Aufrufer, bevor er fertig ist.
        return FakeProcess(lines=("30 %\r", "60 %\r", "fertig\n"))

    monkeypatch.setattr(install.subprocess, "Popen", watched)

    install.install(by_id("vhacd"), seen.append)

    # Die erste Zeile ist der Befehl selbst, danach kommt, was der Prozess sagt.
    assert seen[0].startswith(install._command(by_id("vhacd"))[0])
    assert seen[1:] == ["30 %", "60 %", "fertig"], "jede Zeile, in ihrer Reihenfolge"


def test_a_progress_bar_without_line_breaks_still_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """winget zeichnet mit Wagenrücklauf und ohne Zeilenumbruch.

    Das ist der Grund, aus dem im Textmodus gelesen wird: Er übersetzt ``\r``
    in ein Zeilenende, also kommt jede Aktualisierung als eigene Zeile an.
    Ohne das käme bis zum Schluss keine — und genau dort war der Kunde vorher.
    """
    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    seen: list[str] = []
    # So sieht es aus, wenn Pythons Textmodus die Wagenrückläufe schon in
    # Zeilenenden übersetzt hat — das tut er, und darauf baut ``_stream``.
    monkeypatch.setattr(
        install.subprocess,
        "Popen",
        lambda command, **options: FakeProcess(lines=("  \r", "10 %\r", "100 %\r")),
    )

    install.install(by_id("vhacd"), seen.append)

    assert "10 %" in seen and "100 %" in seen
    assert "" not in seen, "leere Zeilen sind kein Fortschritt"


def test_only_the_last_lines_travel_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Paketverwaltung schreibt hunderte Zeilen; weitergeben will man die
    letzten.
    """
    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    monkeypatch.setattr(
        install.subprocess,
        "Popen",
        lambda command, **options: FakeProcess(lines=tuple(f"Zeile {n}\n" for n in range(200))),
    )

    result = install.install(by_id("vhacd"))

    lines = result.output.splitlines()
    assert len(lines) <= 40
    assert lines[-1] == "Zeile 199", "und zwar die letzten"


def test_the_dialog_shows_that_something_is_happening(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein unbestimmter Balken unterscheidet „lädt" nicht von „hängt".

    Eine Installation dauert Minuten. Die rohe Ausgabe gehört hinter „Details"
    — was davor steht, ist die Zeit, und die sagt genau das, was jemand wissen
    will. Dasselbe Muster wie beim Erzeugen eines Modells (``mesh.py``).
    """
    monkeypatch.setattr(install, "present", lambda _entry: False)
    monkeypatch.setattr(install, "installable", lambda _entry: True)
    dialog = settled(InstallDialog(), qt_app)

    monkeypatch.setattr(
        install,
        "install",
        lambda requirement, progress=None: install.InstallResult(
            requirement=requirement, installed=True
        ),
    )
    dialog.rows[0].action.click()
    qt_app.processEvents()

    assert "(0 s)" in dialog.state.text(), "die Zeit steht von Anfang an da"
    assert dialog._tick.isActive(), "und sie wird nachgezogen"

    for _ in range(200):
        qt_app.processEvents()
        if dialog._worker is None:
            break
        dialog._worker.wait(20)
    qt_app.processEvents()

    assert not dialog._tick.isActive(), "danach nicht mehr"


# --- Was ein Neuling in ein Adressfeld tippt (24.08.2026) -------------------------


def test_the_address_question_shows_an_example_and_where_it_comes_from(
    qt_app: QApplication,
) -> None:
    """**„Adresse, unter der es erreichbar ist" war der ganze Hinweis.**

    Wer noch nie eine Dienstadresse eingetragen hat, weiß daraus weder, wie
    eine aussieht, noch woher er sie bekommt. Ein Kunde trug am 24.08.2026 den
    Ordner seiner Modelle ein — der Dialog nahm ihn an, und die Meldung, die
    ihn Stunden später erreichte, sprach von etwas ganz anderem.

    Das Beispiel kommt aus dem Werkzeug (``ExternalTool.url``) und nicht aus
    einer Zeichenkette im Dialog: So bleibt es richtig, wenn sich die Vorgabe
    ändert.
    """
    from app.ui.install_dialog import _Row

    row = _Row(by_id("ollama"))
    try:
        question = row._address_question()

        assert row.tool is not None
        assert row.tool.url in question, "ohne Beispiel weiß niemand, wie eine Adresse aussieht"
        assert "http" in question
        assert "Ordner" in question, "der häufigste Fehlgriff wird ausdrücklich genannt"
    finally:
        row.deleteLater()


def test_a_folder_never_reaches_the_settings(qt_app: QApplication, monkeypatch) -> None:
    """Der Dialog fragt noch einmal, statt Unsinn zu speichern — und der Grund
    steht dann über demselben Feld."""
    from app.ui import install_dialog
    from app.ui.install_dialog import _Row

    gefragt: list[str] = []
    gespeichert: list[tuple[str, str]] = []

    def antworten(*args: object, **kwargs: object) -> tuple[str, bool]:
        # Erst der Ordner, dann der Abbruch: ein echter Nutzer korrigiert oder
        # gibt auf, und beides darf nichts speichern.
        gefragt.append(str(args[2]) if len(args) > 2 else "")
        return (r"C:\Users\Jemand\.ollama\models", len(gefragt) == 1)

    monkeypatch.setattr(install_dialog.QInputDialog, "getText", antworten)
    monkeypatch.setattr(
        install_dialog.tools,
        "set_address",
        lambda tool_id, value: gespeichert.append((tool_id, value)),
    )

    row = _Row(by_id("ollama"))
    try:
        row._choose_address()
    finally:
        row.deleteLater()

    assert gespeichert == [], "ein Ordner ist keine Adresse und wird nicht gemerkt"
    assert len(gefragt) == 2, "es wird erneut gefragt, nicht stillschweigend verworfen"
    assert "Ordner" in gefragt[1], "beim zweiten Mal steht der Grund über dem Feld"


def test_comfyui_offers_a_local_app_and_a_network_address(qt_app: QApplication) -> None:
    """ComfyUI ist Dienst und lokale App — „Ort“ darf nicht nur eine URL meinen."""
    from app.ui.install_dialog import _Row

    row = _Row(by_id("comfyui"))
    try:
        menu = row.locate.menu()
        assert menu is not None, "ComfyUI bekam weiter nur den Adressdialog"
        texts = {action.text() for action in menu.actions()}
        assert any("App" in text for text in texts), texts
        assert any("adresse" in text.casefold() for text in texts), texts
    finally:
        row.deleteLater()


def test_an_installed_comfyui_that_is_not_running_gets_a_start_button(
    qt_app: QApplication,
) -> None:
    """Der Kunde startet den gefundenen Desktop aus derselben Zeile."""
    from app.ui.install_dialog import _Row

    requirement = by_id("comfyui")
    row = _Row(requirement)
    try:
        row.show_status(
            install.Status(
                requirement=requirement,
                present=True,
                location=r"C:\Programme\Comfy Desktop.exe",
                running=False,
                startable=True,
                address="http://127.0.0.1:8188",
            )
        )

        assert not row.launch.isHidden()
        assert row.launch.text() == "Lokal starten"
        assert "lokal" in row.where.text().casefold()
    finally:
        row.deleteLater()


def test_a_running_comfyui_needs_no_second_start_button(qt_app: QApplication) -> None:
    """Ein beantwortender Dienst wird nicht ein zweites Mal gestartet."""
    from app.ui.install_dialog import _Row

    requirement = by_id("comfyui")
    row = _Row(requirement)
    try:
        row.show_status(
            install.Status(
                requirement=requirement,
                present=True,
                location="http://127.0.0.1:8188",
                running=True,
                startable=False,
            )
        )

        assert row.launch.isHidden()
    finally:
        row.deleteLater()


def test_starting_comfyui_waits_outside_the_gui_thread(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Port darf zwanzig Sekunden brauchen, ohne das Fenster einzufrieren."""
    import threading

    here = threading.get_ident()
    seen: list[int] = []
    monkeypatch.setattr(
        tools.ExternalTool,
        "start_command",
        lambda _tool: ["Comfy Desktop.exe"],
    )

    def started(_tool: tools.ExternalTool, *_args: object, **_kwargs: object) -> tools.StartResult:
        # ``*_args``/``**_kwargs``: Der Arbeiter reicht seit dem 30.08.2026
        # ``cancelled`` mit — ein Patch mit fester Stelligkeit stünde sonst
        # als leere Liste da und meldete „läuft im Qt-Thread".
        seen.append(threading.get_ident())
        return tools.StartResult(launched=True, running=True)

    monkeypatch.setattr(tools, "start_detailed", started)
    dialog = settled(InstallDialog(), qt_app)
    row = next(entry for entry in dialog.rows if entry.requirement.id == "comfyui")
    row.show_status(
        install.Status(
            requirement=row.requirement,
            present=True,
            location="Comfy Desktop.exe",
            running=False,
            startable=True,
        )
    )

    row.launch.click()
    for _ in range(200):
        qt_app.processEvents()
        if dialog._launcher is None:
            break
        dialog._launcher.wait(20)
    qt_app.processEvents()

    assert seen and here not in seen
    dialog.release()


def test_each_external_status_probes_its_service_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Dialogzeile darf den gleichen Port nicht mehrfach hintereinander prüfen."""
    requirement = by_id("comfyui")
    tool = tools.by_id("comfyui")
    assert tool is not None
    calls: list[str] = []

    def state_of(given: tools.ExternalTool) -> tools.ToolState:
        calls.append(given.id)
        return tools.ToolState(tool=given, path=None, running=False)

    monkeypatch.setattr(tools, "state_of", state_of)
    monkeypatch.setattr(install, "installable", lambda _requirement: False)

    install.status_of(requirement)

    assert calls == ["comfyui"]


def test_a_failed_launch_says_that_the_program_was_not_opened(qt_app: QApplication) -> None:
    """Ein Rechtefehler darf nicht als erfolgreich geöffnete Desktop-App erscheinen."""
    dialog = settled(InstallDialog(), qt_app)
    requirement = by_id("comfyui")

    dialog._tool_started(
        (
            requirement,
            tools.StartResult(
                program=Path("Comfy Desktop.exe"),
                reason="Zugriff verweigert",
            ),
        )
    )

    assert "nicht geöffnet" in dialog.state.text()
    assert "Zugriff verweigert" in dialog.state.text()
    assert "erneut" in dialog.state.text()
    dialog.release()


def test_a_slow_service_says_how_long_it_will_take(qt_app: QApplication) -> None:
    """Wer zwei Minuten wartet, soll das vorher wissen — nicht danach raten.

    Bis zum 30.08.2026 galt für jeden Dienst dieselbe Zahl: zwanzig Sekunden.
    Für Ollama stimmt sie, es antwortet in wenigen. ComfyUI Desktop lädt in
    der Zeit noch seine Plugins — gemessen antwortete es nach gut zwei
    Minuten, und Solidon meldete nach zwanzig Sekunden einen Fehlschlag über
    einen laufenden Start.

    Die Erwartung steht **vom ersten Tick an** da und nicht erst nach einer
    Weile: Wer den Knopf drückt und sofort liest, dass es zwei Minuten dauert,
    wartet ruhig; wer es nach dreißig Sekunden erfährt, hat dreißig Sekunden
    gerätselt, ob etwas kaputt ist.
    """
    import time

    dialog = InstallDialog()
    for kennung, erwartet in (("comfyui", True), ("ollama", False)):
        werkzeug = tools.by_id(kennung)
        assert werkzeug is not None
        dialog._running_title = str(werkzeug.title)
        dialog._running_action = "start"
        dialog._expected_seconds = werkzeug.start_seconds
        dialog._started_at = time.monotonic() - 5
        dialog._show_elapsed()
        zeile = dialog.state.text()
        assert "(5 s)" in zeile, f"{kennung}: die verstrichene Zeit fehlt"
        gesagt = "ein bis zwei Minuten" in zeile
        assert gesagt is erwartet, (
            f"{kennung}: Erwartung {'fehlt' if erwartet else 'steht fälschlich'} in {zeile!r}"
        )


def test_a_long_wait_can_be_stopped_without_stopping_the_service(
    qt_app: QApplication,
) -> None:
    """Abbrechen gehört zu jeder Wartezeit über zwei Sekunden (`wartezeit.md`).

    Solange zwanzig Sekunden gewartet wurde, fiel der fehlende Ausgang nicht
    auf. Bei einem Dienst, der zwei Minuten hochfährt, ist ein Dialog ohne
    Ausstieg eine Sackgasse (§2.1).

    Und der Satz danach muss stimmen: Abgebrochen wird das **Warten**, nicht
    der Dienst — ein gestarteter Prozess gehört Solidon nicht und wird von ihm
    nie beendet. Der Text sagt außerdem, wer die Zusage einlöst; „findet
    Solidon von selbst" stand hier einen Entwurf lang und war zu stark, denn
    nachgesehen wird beim Öffnen des Erzeugen-Dialogs.
    """
    dialog = InstallDialog()
    dialog._running_title = "ComfyUI"
    dialog.stop_waiting.setVisible(True)

    dialog._stop_waiting()

    zeile = dialog.state.text()
    assert "ComfyUI" in zeile
    assert "Hintergrund" in zeile, "der Dienst läuft weiter — das muss dastehen"
    assert "Modell erzeugen" in zeile, "und wer die Zusage einlöst"
    assert not dialog.stop_waiting.isVisibleTo(dialog), (
        "der Knopf gehört weg, sobald nicht mehr gewartet wird"
    )


def test_every_service_carries_its_own_start_time() -> None:
    """Die Wartezeit steht am Dienst, nicht als gemeinsame Zahl im Modul.

    Ein Wert für alle war der Grund des Fehlers: Er kann nur entweder für den
    schnellen oder für den langsamen Dienst stimmen. Der Test hält beide Enden
    fest, damit niemand sie später wieder zusammenzieht.
    """
    zeiten = {tool.id: tool.start_seconds for tool in tools.TOOLS if tool.kind == "service"}
    assert zeiten, "keine Dienste — dann prüft der Test nichts"
    assert zeiten["ollama"] == tools.START_TIMEOUT_SECONDS, (
        "Ollama antwortet in Sekunden und bleibt beim gemeinsamen Wert"
    )
    assert zeiten["comfyui"] >= 120.0, "ComfyUI Desktop braucht gemessen über zwei Minuten"


def test_a_service_that_wins_the_race_does_not_swallow_the_next_failure(
    qt_app: QApplication,
) -> None:
    """Das Rennen zwischen Abbruch und Antwort darf nichts hinterlassen.

    Der Ablauf, den 3d-druck-4c beim Lesen des Diffs fand: Der Kunde drückt
    „Nicht mehr warten", aber der Dienst antwortet, bevor der Arbeiter das
    Abbruchzeichen sieht. Solange der Abbruch ein **Merkmal des Fensters** war,
    blieb es dabei stehen — der running-Zweig kehrt vorher zurück —, und beim
    nächsten **echten** Fehlschlag griff „abgebrochen, also kein Fehler": Der
    Balken verschwand, und kein Satz sagte, warum.

    Seit der Zustand am Ergebnis hängt (:attr:`StartResult.stopped`), kann das
    nicht mehr passieren: Ein Ergebnis trägt seine eigene Wahrheit.
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "comfyui"
    )

    # Erst gewinnt der Dienst das Rennen gegen den Abbruch.
    dialog._stop_waiting()
    dialog._tool_started((anforderung, tools.StartResult(launched=True, running=True)))
    assert "läuft jetzt" in dialog.state.text()

    # Und danach ein echter Fehlschlag — er muss zu sehen sein.
    dialog._tool_started((anforderung, tools.StartResult(launched=True, running=False)))
    zeile = dialog.state.text()
    assert "nicht geantwortet" in zeile, f"der Fehlschlag wurde verschluckt: {zeile!r}"


def test_a_late_reply_does_not_paint_over_a_newer_run(qt_app: QApplication) -> None:
    """Ein abgebrochener Arbeiter lebt weiter — seine Meldung gehört ihm allein.

    Nach dem Abbruch gibt der Dialog die Knöpfe sofort frei, während der alte
    Arbeiter noch bis zu seinem nächsten Poll läuft. Startet der Kunde
    inzwischen etwas anderes, träfe dessen Meldung einen fremden Lauf und
    überschriebe seinen Zustandstext.

    Verglichen wird der **Absender**, nicht der Inhalt — dasselbe Muster wie
    ``Session._outdated`` (`wartezeit.md`).
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "comfyui"
    )
    alt = object()
    dialog._launcher = None
    dialog.state.setText("Wird gestartet: Ollama (3 s)")

    dialog._tool_started((anforderung, tools.StartResult(launched=True, running=False), alt))

    assert dialog.state.text() == "Wird gestartet: Ollama (3 s)", (
        "die Meldung eines fremden Arbeiters hat den laufenden Text überschrieben"
    )


def test_a_service_that_does_not_answer_names_its_address(qt_app: QApplication) -> None:
    """Die Adresse lag vor und stand nirgends.

    „Sehen Sie in den ComfyUI-Protokollen nach" schickt den Kunden an einen
    Ort, den er nicht kennt. Ein Aufruf im Browser beantwortet dieselbe Frage
    in zwei Sekunden, und ``StartResult`` trägt die Adresse seit je.
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "comfyui"
    )

    dialog._tool_started(
        (
            anforderung,
            tools.StartResult(launched=True, running=False, address="http://127.0.0.1:8188"),
        )
    )

    zeile = dialog.state.text()
    assert "http://127.0.0.1:8188" in zeile, f"die Adresse fehlte: {zeile!r}"


def test_an_endpoint_is_not_offered_as_a_page(qt_app: QApplication) -> None:
    """Eine Adresse mit Pfad ist ein Endpunkt und keine Seite.

    Ollama horcht auf ``http://localhost:11434/api/chat``; ein Browseraufruf
    darauf antwortet mit einem Fehler. Wer den Kunden dorthin schickt, zeigt
    ihm eine Fehlerseite und lässt ihn glauben, der Dienst sei kaputt — der
    Hinweis wäre schlechter als keiner.
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "ollama"
    )

    dialog._tool_started(
        (
            anforderung,
            tools.StartResult(
                launched=True, running=False, address="http://localhost:11434/api/chat"
            ),
        )
    )

    zeile = dialog.state.text()
    assert "11434" not in zeile, f"ein Endpunkt wurde als Seite angeboten: {zeile!r}"
    assert zeile, "ohne Adresse bleibt der Satz trotzdem stehen"


def test_a_failed_start_keeps_its_command_for_the_details(qt_app: QApplication) -> None:
    """Was Solidon versucht hat, gehört in die Einzelheiten (§33.2).

    Der Startweg hatte den Knopf nie gefüllt, obwohl der Aufruf im Ergebnis
    steht. Wer meldet „es startet nicht", kann ihn kopieren und selbst
    ausführen — und sieht in einer Zeile, was das Programm dazu sagt. Ohne ihn
    bleibt einem Fehlerbericht nur „ging nicht".
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "comfyui"
    )

    dialog._tool_started(
        (
            anforderung,
            tools.StartResult(
                launched=True,
                running=False,
                command=("comfy.exe", "launch", "--background"),
                address="http://127.0.0.1:8188",
            ),
        )
    )

    assert dialog.details_button.isVisible() or dialog._details, "der Knopf blieb leer"
    assert "comfy.exe launch --background" in dialog._details
    assert "http://127.0.0.1:8188" in dialog._details


def test_starting_a_service_forgets_the_details_of_the_install(qt_app: QApplication) -> None:
    """Was zum vorigen Lauf gehört, gehört nicht zu diesem.

    Der Installationszweig räumt die Einzelheiten auf, der Startzweig tat es
    nicht: Wer erst installierte und dann startete, fand unter *Details
    anzeigen* noch die Ausgabe der Paketverwaltung — zu einem Vorgang, der
    längst vorbei war.
    """
    dialog = InstallDialog()
    anforderung = next(
        entry.requirement for entry in dialog.rows if entry.requirement.id == "comfyui"
    )
    dialog._details = "pip: could not find a version that satisfies the requirement"
    dialog.details_button.setVisible(True)

    dialog._start_tool(anforderung)

    assert "pip:" not in dialog._details, "die Ausgabe des vorigen Vorgangs stand noch da"


def test_the_text_never_names_a_button_that_is_not_there(qt_app: QApplication) -> None:
    """Ein Satz, der auf einen Knopf zeigt, muss dessen Bedingung teilen.

    Der Hinweis nannte „Lokal starten“, sobald ein Dienst da und nicht am
    Laufen war. Der Knopf hängt aber an ``startable`` — das verlangt
    zusätzlich ein gefundenes Startprogramm. Wer einen Dienst eingetragen
    hatte, dessen Startprogramm fehlt, las den Verweis auf einen Knopf, der
    nicht dastand (gemessen an beiden Diensten, 30.08.2026).
    """
    dialog = InstallDialog()
    zeile = next(entry for entry in dialog.rows if entry.requirement.id == "comfyui")

    ohne_starter = install.Status(
        requirement=zeile.requirement,
        present=True,
        location="C:/irgendwo",
        running=False,
        address="http://127.0.0.1:8188",
        startable=False,
    )
    text = zeile._where_text(ohne_starter)
    assert "Lokal starten" not in text, f"Verweis auf einen fehlenden Knopf: {text!r}"
    assert "Startprogramm" in text, "und der Grund fehlt auch noch"

    mit_starter = replace(ohne_starter, startable=True)

    assert "Lokal starten" in zeile._where_text(mit_starter), (
        "mit Knopf muss der Satz ihn auch nennen"
    )


def test_the_remote_branch_shares_the_same_condition(qt_app: QApplication) -> None:
    """Derselbe Fehler stand im Zweig darüber.

    Wer eine Netzadresse eingetragen hatte, die nicht antwortet, bekam
    denselben Verweis — ebenfalls ohne die Bedingung des Knopfes.
    """
    dialog = InstallDialog()
    zeile = next(entry for entry in dialog.rows if entry.requirement.id == "ollama")

    status = install.Status(
        requirement=zeile.requirement,
        present=True,
        location="C:/irgendwo",
        running=False,
        using_remote_address=True,
        address="http://fern:11434",
        startable=False,
    )

    assert "Lokal starten" not in zeile._where_text(status)
