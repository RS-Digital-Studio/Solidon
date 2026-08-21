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

import pytest
from PySide6.QtWidgets import QApplication

from app.core import install
from app.ui.install_dialog import InstallDialog


def by_id(identifier: str) -> install.Requirement:
    return next(entry for entry in install.REQUIREMENTS if entry.id == identifier)


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


def test_a_program_goes_through_the_system_package_manager() -> None:
    command = install._command(by_id("openscad"))

    assert "winget" in command[0]
    assert "--id" in command and "OpenSCAD.OpenSCAD" in command
    assert "--disable-interactivity" in command, "an installer must not wait for a keypress"


def names_of(entry: install.Requirement) -> set[str]:
    """Jede Kennung, die diese Datei diesem Eintrag gibt — über alle Verwaltungen."""
    return {
        part
        for part in (entry.package, entry.winget, entry.flatpak, *entry.brew)
        if part and not part.startswith("--")
    }


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

    ohne_verwaltung = str(install.why_not(by_id("openscad")))
    ohne_kennung = str(install.why_not(by_id("comfyui")))

    assert "brew" in ohne_verwaltung, "der Name der Verwaltung gehört in die Auskunft"
    assert ohne_verwaltung != ohne_kennung, "zwei Ursachen, zwei Sätze"
    assert by_id("openscad").by_hand().startswith("brew install"), "der Befehl zum Abschreiben"
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
    openscad = by_id("openscad")

    wanted = openscad.identifier(flatpak)

    assert wanted and wanted[0].endswith(".flatpakref")
    assert openscad.flatpak in wanted[0]
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

    assert not install.installable(by_id("openscad"))


def test_something_with_no_installer_at_all_names_its_page() -> None:
    comfy = by_id("comfyui")

    assert not any(comfy.identifier(entry) for entry in install.MANAGERS), "by hand everywhere"
    assert not install.installable(comfy)
    assert comfy.url


def test_installing_the_impossible_does_not_run_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install, "manager", lambda: None)
    ran: list[object] = []
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: ran.append(a))

    result = install.install(by_id("openscad"))

    assert not result.installed
    assert result.reason
    assert ran == [], "nothing was started"


def test_what_is_already_there_is_not_installed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[object] = []
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: ran.append(a))

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
    ran: list[object] = []
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: ran.append(a))

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
    row = next(entry for entry in dialog.rows if entry.requirement.id == "openscad")

    assert not row.copy.isHidden(), "der Befehl gehört an die Stelle, an der es nicht geht"
    assert "brew install" in row.where.text(), "und im Blick, nicht nur in der Ablage"
    row.copy.click()
    from PySide6.QtGui import QGuiApplication

    assert "openscad" in (QGuiApplication.clipboard().text() or "")


def test_a_failed_install_says_what_went_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regel 17 gilt auch hier: „Das hat nicht geklappt." ist keine Antwort.

    Der Kern gab bei einem Fehlschlag nur ``installed=False`` und die rohe
    Ausgabe zurück; der Dialog machte daraus „Das hat nicht geklappt." und
    zeigte davor jede Zeile, die pip oder winget von sich geben. Wer das liest,
    weiß danach weniger als vorher.

    Der Rückgabewert der Paketverwaltung gehört zu den Einzelheiten, nicht in
    den Satz — dort steht er weiterhin, für den, der ihn weitergeben will.
    """
    import subprocess

    class Fertig:
        returncode = 1
        stdout = "ERROR: Could not find a version that satisfies the requirement"
        stderr = ""

    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Fertig())

    result = install.install(by_id("vhacd"))

    assert not result.installed
    assert result.reason, "ein Fehlschlag ohne Grund sagt nur, dass etwas nicht ging"
    assert "1" in result.output, "der Rückgabewert gehört in die Einzelheiten"
    satz = str(result.reason)
    assert "ERROR:" not in satz, "die rohe Ausgabe gehört nicht in den Satz"


def test_a_package_manager_that_will_not_start_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch der Ausfall vor dem ersten Befehl trägt einen Satz."""
    import subprocess

    def kaputt(*args: object, **kwargs: object) -> None:
        raise OSError("nicht gefunden")

    monkeypatch.setattr(install, "present", lambda _requirement: False)
    monkeypatch.setattr(install, "installable", lambda _requirement: True)
    monkeypatch.setattr(subprocess, "run", kaputt)

    result = install.install(by_id("vhacd"))

    assert not result.installed
    assert result.reason


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
