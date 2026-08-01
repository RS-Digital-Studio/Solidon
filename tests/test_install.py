"""Fehlendes installieren, aus der Anwendung heraus (§36, §38).

Der interessante Teil dieser Datei ist, was sie verbietet. Ein Installer, dem
sich sagen lässt, was er holen soll, ist ein Weg, beliebige Software auf
jemandes Rechner auszuführen — die Namen leben also im Quelltext, und nichts
sonst erreicht je eine Befehlszeile.
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


# --- the command line -----------------------------------------------------------


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


def test_the_names_come_from_this_file_and_nowhere_else() -> None:
    """Die Regel, die dieses Feature sicher macht — als Test gehalten, nicht
    als Kommentar.
    """
    known = {entry.package for entry in install.REQUIREMENTS if entry.package}

    for entry in install.REQUIREMENTS:
        if not entry.package:
            continue
        command = install._command(entry)
        assert entry.package in command
        assert set(command) & known == {entry.package}, entry.id


# --- Wenn es nicht geht -----------------------------------------------------------


def test_a_packaged_build_says_why_it_cannot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install, "packaged", lambda: True)
    requirement = by_id("brep")

    assert not install.installable(requirement)
    assert "Paketverwaltung" in str(install.why_not(requirement))


def test_without_a_package_manager_a_program_is_not_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install, "winget", lambda: None)

    assert not install.installable(by_id("openscad"))


def test_something_with_no_installer_at_all_names_its_page() -> None:
    comfy = by_id("comfyui")

    assert not comfy.package, "ComfyUI is installed by hand"
    assert not install.installable(comfy)
    assert comfy.url


def test_installing_the_impossible_does_not_run_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install, "winget", lambda: None)
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


# --- the dialog -----------------------------------------------------------------


def test_the_dialog_lists_everything_with_its_state(qt_app: QApplication) -> None:
    dialog = InstallDialog()

    assert len(dialog.rows) == len(install.REQUIREMENTS)
    for row in dialog.rows:
        marker = row.state.text()
        assert marker in ("+", "-"), "readable without colour (§19.1)"
        assert (marker == "+") == install.present(row.requirement)


def test_a_row_that_cannot_install_explains_itself(qt_app: QApplication) -> None:
    dialog = InstallDialog()

    for row in dialog.rows:
        if install.present(row.requirement) or install.installable(row.requirement):
            continue
        assert not row.action.isEnabled()
        assert row.action.toolTip(), row.requirement.id


def test_nothing_starts_by_itself(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """Der ganze Sinn von §36: eine Anwendung installiert nichts ungefragt."""
    ran: list[object] = []
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: ran.append(a))

    InstallDialog()

    assert ran == []
