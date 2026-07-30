"""Programme finden, die nicht im PATH stehen (§38).

Der Fund, aus dem diese Datei entstanden ist: auf einem Rechner mit
``C:\\Program Files\\OpenSCAD\\openscad.exe`` und einem installierten Slicer
meldete die Erstinbetriebnahme beide als fehlend und bot an, sie zu
installieren — weil ``shutil.which`` nur den PATH kennt und Windows-Installer
dort nichts eintragen.

Die Suche selbst ist in der Suite abgeschaltet (siehe ``conftest.py``), damit
kein Testergebnis davon abhängt, was auf der Maschine liegt. Hier werden
deshalb die einzelnen Schritte direkt gefragt, gegen einen Ordner, den der
Test selbst gebaut hat.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.core import discover


@pytest.fixture
def install_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ein Installationsordner, wie ein Installationsprogramm ihn anlegt."""
    root = tmp_path / "Program Files"
    (root / "OpenSCAD").mkdir(parents=True)
    (root / "OpenSCAD" / f"openscad{'.exe' if sys.platform == 'win32' else ''}").write_text("")
    monkeypatch.setattr(discover, "_install_roots", lambda: (root,))
    discover.forget_cache()
    return root


# --- der Ordnerdurchgang ---------------------------------------------------------


def test_a_program_in_its_own_folder_is_found(install_folder: Path) -> None:
    found = discover._from_folders(("openscad",))

    assert found is not None
    assert found.parent.name == "OpenSCAD"


def test_a_program_that_is_not_there_stays_not_there(install_folder: Path) -> None:
    assert discover._from_folders(("definitely-not-installed",)) is None


def test_the_walk_stays_shallow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Ebene und ``bin`` — kein Lauf über eine ganze Festplatte."""
    root = tmp_path / "root"
    deep = root / "vendor" / "product" / "nested"
    deep.mkdir(parents=True)
    (deep / "openscad").write_text("")
    monkeypatch.setattr(discover, "_install_roots", lambda: (root,))
    discover.forget_cache()

    assert discover._from_folders(("openscad",)) is None


def test_a_bin_folder_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    (root / "product" / "bin").mkdir(parents=True)
    (root / "product" / "bin" / "openscad").write_text("")
    monkeypatch.setattr(discover, "_install_roots", lambda: (root,))
    discover.forget_cache()

    found = discover._from_folders(("openscad",))

    assert found is not None and found.name.startswith("openscad")


def test_an_unreadable_root_is_skipped_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Ordner, den es nicht gibt, ist kein Fehler — er ist nur leer."""
    monkeypatch.setattr(discover, "_install_roots", lambda: (tmp_path / "gibt-es-nicht",))
    discover.forget_cache()

    assert discover._from_folders(("openscad",)) is None


# --- was jemand angegeben hat ----------------------------------------------------


def test_a_chosen_path_wins(tmp_path: Path) -> None:
    program = tmp_path / "portable" / "comfy.exe"
    program.parent.mkdir()
    program.write_text("")
    discover.remember("comfyui", str(program))

    assert discover.find_program("comfyui", ("nothing-called-this",)) == program


def test_a_chosen_path_that_is_gone_does_not_keep_it_found(tmp_path: Path) -> None:
    """Sonst gilt das Programm als da, während jeder Aufruf scheitert."""
    discover.remember("comfyui", str(tmp_path / "weg.exe"))

    assert discover.find_program("comfyui", ("nothing-called-this",)) is None


def test_an_empty_choice_forgets_it(tmp_path: Path) -> None:
    program = tmp_path / "comfy.exe"
    program.write_text("")
    discover.remember("comfyui", str(program))
    discover.remember("comfyui", "")

    assert discover.remembered("comfyui") == ""


def test_choices_survive_a_restart(tmp_path: Path) -> None:
    """Die Datei ist der Zustand — nichts hiervon lebt nur im Prozess."""
    program = tmp_path / "comfy.exe"
    program.write_text("")
    discover.remember("comfyui", str(program))
    discover._cache.clear()

    assert discover.remembered("comfyui") == str(program)


def test_a_broken_choices_file_is_ignored_not_fatal() -> None:
    path = discover._choices_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{kaputt", encoding="utf-8")

    assert discover.remembered("comfyui") == ""


# --- Adressen --------------------------------------------------------------------


def test_a_service_falls_back_to_its_default_address() -> None:
    discover.remember("comfyui", "")

    assert discover.service_url("comfyui", "http://127.0.0.1:8188") == "http://127.0.0.1:8188"


def test_a_service_can_live_on_another_machine() -> None:
    discover.remember("comfyui", "http://192.168.1.5:8188")

    assert discover.service_url("comfyui", "http://127.0.0.1:8188") == "http://192.168.1.5:8188"


def test_a_closed_port_answers_false_quickly() -> None:
    """Auf einem Port, auf dem nichts lauscht — die Antwort ist Nein, kein Fehler."""
    assert not discover.reachable("http://127.0.0.1:9", seconds=0.2)


def test_an_address_without_a_scheme_is_still_understood() -> None:
    assert not discover.reachable("127.0.0.1:9", seconds=0.2)


def test_a_listening_port_is_seen() -> None:
    import socket

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        assert discover.reachable(f"http://127.0.0.1:{port}")
