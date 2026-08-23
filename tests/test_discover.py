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

import logging
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


def test_a_folder_for_the_vendor_and_one_for_the_program_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prusa installiert nach ``Prusa3D\\PrusaSlicer\\`` — Firma, dann Programm.

    Eine Ebene tief gesucht, war PrusaSlicer auf dieser Maschine installiert
    und für Solidon trotzdem nicht vorhanden: die Übergabe an den Slicer bot
    ihn schlicht nicht an, und keine Meldung sagte warum.
    """
    root = tmp_path / "root"
    (root / "Prusa3D" / "PrusaSlicer").mkdir(parents=True)
    (root / "Prusa3D" / "PrusaSlicer" / "prusa-slicer").write_text("")
    monkeypatch.setattr(discover, "_install_roots", lambda: (root,))
    discover.forget_cache()

    found = discover._from_folders(("prusa-slicer",))

    assert found is not None
    assert found.parent.name == "PrusaSlicer"


def test_the_walk_stays_shallow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwei Ebenen und ``bin`` — kein Lauf über eine ganze Festplatte."""
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


def test_a_remembered_address_is_not_reported_as_a_missing_file(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Eine Adresse ist keine Datei — und keine verschwundene.

    ``remember`` legt Pfad **und** Adresse im selben Speicher ab; ``service_url``
    liest die Adresse dort wieder. ``find_program`` prüfte sie mit ``is_file()``
    und schrieb bei jedem Aufruf zweimal ``remembered path for comfyui is gone``
    ins Protokoll, während der Dienst antwortete.

    **Folgenlos für das Ergebnis und trotzdem ein Fehler: Die Warnung log.** Wer
    die Adresse einträgt — der Text bietet es an —, findet danach im Protokoll,
    sein Eintrag sei fort.
    """
    discover.remember("comfyui", "http://127.0.0.1:8188")

    with caplog.at_level(logging.WARNING, logger="app.core.discover"):
        found = discover.unpatched_find_program("comfyui", ("nothing-called-this",))

    assert found is None, "eine Adresse ist kein Programmpfad"
    assert not [r for r in caplog.records if "is gone" in r.getMessage()], (
        f"gewarnt, obwohl nichts fehlt: {[r.getMessage() for r in caplog.records]}"
    )


def test_a_chosen_path_that_is_gone_still_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Die Gegenrichtung: Ein echter Pfad, den es nicht mehr gibt, warnt weiter.

    Sonst hätte die Ausnahme für Adressen die Warnung ganz abgeräumt, und der
    Fall, für den sie da ist, wäre still geworden.
    """
    discover.remember("comfyui", str(tmp_path / "weg.exe"))

    with caplog.at_level(logging.WARNING, logger="app.core.discover"):
        discover.unpatched_find_program("comfyui", ("nothing-called-this",))

    assert [r for r in caplog.records if "is gone" in r.getMessage()]


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


# --- was Flatpak ablegt ---------------------------------------------------------


@pytest.fixture
def flatpak_exports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ein Exportverzeichnis, wie ``flatpak install --user`` es hinterlässt.

    Die Dateien darin heißen wie die Anwendung, in umgekehrter
    Domainschreibweise — nicht wie das Programm.
    """
    folder = tmp_path / ".local" / "share" / "flatpak" / "exports" / "bin"
    folder.mkdir(parents=True)
    for application in (
        "org.openscad.OpenSCAD",
        "com.orcaslicer.OrcaSlicer",
        "org.gnome.Calculator",
    ):
        (folder / application).write_text("#!/bin/sh\nexec flatpak run ...\n")
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(folder),))
    monkeypatch.setattr(discover.sys, "platform", "linux")
    discover.forget_cache()
    return folder


def test_a_flatpak_is_found_under_its_application_id(flatpak_exports: Path) -> None:
    """Nach ``flatpak install`` war das Programm für Solidon nicht vorhanden.

    Der Wrapper heißt ``org.openscad.OpenSCAD``, und sein Verzeichnis steht
    ausdrücklich nicht im PATH — Flatpak setzt ihn nicht. Weder
    ``shutil.which("openscad")`` noch der Durchgang durch ``/opt`` und
    ``/usr/local`` findet das. Die Liste bot danach an, OpenSCAD ein zweites
    Mal zu installieren.
    """
    found = discover._from_flatpak(("openscad",))

    assert found is not None
    assert found.name == "org.openscad.OpenSCAD"


def test_a_flatpak_matches_across_spellings(flatpak_exports: Path) -> None:
    """„orca-slicer" und „OrcaSlicer" sind dasselbe Programm.

    Der Slicer wird unter einer Handvoll Schreibweisen gesucht, und keine
    davon ist die der Anwendungskennung. Verglichen wird deshalb die nackte
    Form: klein, ohne Trenner.
    """
    for spelling in ("orca-slicer", "OrcaSlicer", "orcaslicer"):
        found = discover._from_flatpak((spelling,))
        assert found is not None, spelling
        assert found.name == "com.orcaslicer.OrcaSlicer"


def test_a_flatpak_nobody_asked_for_stays_untouched(flatpak_exports: Path) -> None:
    """Gesucht wird, wonach gefragt ist — der Rechner hat mehr installiert."""
    assert discover._from_flatpak(("openscad",)) is not None
    assert discover._from_flatpak(("calculator",)) is not None, "auch das, wenn danach gefragt wird"
    assert discover._from_flatpak(("cura",)) is None, "und nichts, wonach niemand fragt"


def test_a_flatpak_that_the_user_installed_himself_is_found_too(
    flatpak_exports: Path,
) -> None:
    """Die Kennung muss nicht in Solidon stehen.

    Wer PrusaSlicer als Flatpak hat, bekommt ihn gefunden, weil das letzte
    Stück seiner Kennung derselbe Name ist — eine gepflegte Liste wäre am Tag
    nach dem nächsten Slicer unvollständig.
    """
    (flatpak_exports / "com.prusa3d.PrusaSlicer").write_text("")

    found = discover._from_flatpak(("prusa-slicer",))

    assert found is not None
    assert found.name == "com.prusa3d.PrusaSlicer"


def test_flatpak_is_not_asked_on_other_systems(
    flatpak_exports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Verzeichnis dieses Namens auf einem Windows-Rechner sagt nichts."""
    monkeypatch.setattr(discover.sys, "platform", "win32")

    assert discover._from_flatpak(("openscad",)) is None


def test_a_missing_exports_folder_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Rechner ohne Flatpak ist der Normalfall, kein Sonderfall."""
    monkeypatch.setattr(discover.sys, "platform", "linux")
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", ("/gibt/es/nicht",))

    assert discover._from_flatpak(("openscad",)) is None


# --- was Homebrew ablegt --------------------------------------------------------


def test_a_mac_bundle_is_found_inside_its_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Cask legt ``OpenSCAD.app/Contents/MacOS/OpenSCAD`` ab.

    Gesucht wurde bis hierhin direkt im Ordner und in ``bin``. Der Knopf
    installierte damit ein Programm, das die Liste danach weiter als „nicht
    gefunden" führte.
    """
    applications = tmp_path / "Applications"
    binary = applications / "OpenSCAD.app" / "Contents" / "MacOS" / "OpenSCAD"
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    monkeypatch.setattr(discover, "_install_roots", lambda: (applications,))
    monkeypatch.setattr(discover, "_PARTS", (".", "bin", "Contents/MacOS"))
    discover.forget_cache()

    found = discover._from_folders(("OpenSCAD",))

    assert found == binary


def test_the_bundle_path_belongs_to_macos_and_nowhere_else() -> None:
    """Die Zuordnung selbst, von jeder Maschine aus prüfbar.

    Als Zeile mit ``if sys.platform`` wäre der Mac-Pfad nur auf einem Mac zu
    sehen — und damit nirgends geprüft. Der Test daneben zeigt, dass die Suche
    ihn benutzt; dieser zeigt, dass sie ihn dort **bekommt**.
    """
    assert "Contents/MacOS" in discover.parts_for("darwin")
    assert "Contents/MacOS" not in discover.parts_for("win32")
    assert "Contents/MacOS" not in discover.parts_for("linux")
    for platform in ("darwin", "win32", "linux"):
        assert discover.parts_for(platform)[:2] == (".", "bin"), platform
    assert discover.parts_for(sys.platform) == discover._PARTS, "die Konstante folgt der Funktion"


def test_the_plain_name_ignores_spelling() -> None:
    """Die eine Stelle, an der Schreibweisen zusammenfallen."""
    assert discover.plain_name("OrcaSlicer") == "orcaslicer"
    assert discover.plain_name("orca-slicer") == "orcaslicer"
    assert discover.plain_name("prusa_slicer") == "prusaslicer"
    assert discover.plain_name("openscad.exe") == "openscad"
    assert discover.plain_name("OpenSCAD.app") == "openscad"
    assert discover.plain_name("Ultimaker Cura") == "ultimakercura"


# --- der Arbeitsordner für ein eingesperrtes Programm ----------------------------


def test_a_normal_program_works_in_the_system_temp(tmp_path: Path) -> None:
    """Er wird zuverlässig aufgeräumt, auch wenn Solidon dabei abstürzt."""
    import tempfile

    with discover.workspace_for(tmp_path / "openscad.exe", "probe-") as workspace:
        assert workspace.is_dir()
        assert Path(tempfile.gettempdir()) in workspace.parents
        (workspace / "model.scad").write_text("cube(1);")

    assert not workspace.exists(), "danach ist er weg"


def test_a_flatpak_works_below_the_home_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Der Fall, der ohne das still scheitert.**

    Ein Flatpak hat sein eigenes ``/tmp``. Die Datei wäre geschrieben, der
    Aufruf käme an, und das Programm fände nichts: „Can't open input file" —
    unmittelbar nachdem der Nutzer es über einen Knopf installiert hat.

    Nachgesehen und nicht angenommen: Die Flathub-Pakete von OpenSCAD und
    OrcaSlicer geben ``--filesystem=home`` frei und kein Verzeichnis, in dem
    wir sonst schreiben würden.
    """
    from app.core import paths

    wrapper = Path("~/.local/share/flatpak/exports/bin/org.openscad.OpenSCAD").expanduser()

    assert discover.sandboxed(wrapper), "ein Wrapper aus dem Exportverzeichnis"
    with discover.workspace_for(wrapper, "probe-") as workspace:
        assert workspace.is_dir()
        # Gegen den Nutzer-Cache und nicht gegen ``gettempdir``: Die Suite
        # biegt die Nutzerverzeichnisse in einen Temp-Ordner um (§38), also
        # liegt dort in einem Testlauf beides untereinander. Die Aussage ist
        # ohnehin diese — im Betrieb liegt der Cache unter ``$HOME``, und
        # genau das gibt ``--filesystem=home`` frei.
        assert paths.user_cache_dir() in workspace.parents
        (workspace / "model.scad").write_text("cube(1);")
        kept = workspace

    assert not kept.exists(), "aufgeräumt wird hier selbst — kein Kontextmanager tut es für uns"


def test_the_cache_is_where_a_flatpak_may_look(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warum der Nutzer-Cache der richtige Ort ist.

    Die Freigabe der beiden Pakete lautet ``--filesystem=home`` — nachgelesen
    in den Flathub-Manifesten, nicht angenommen. Unter Linux entsteht der
    Cache-Pfad aus ``XDG_CACHE_HOME`` oder aus ``~/.cache``, und beides liegt
    unter dem Heimatverzeichnis. Geprüft wird die Regel und nicht der Pfad
    dieses Laufs: Die Suite biegt die Nutzerverzeichnisse für Testläufe um.
    """
    from app.core import paths

    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    if sys.platform.startswith("linux"):
        assert Path.home() in paths.user_cache_dir().parents
    monkeypatch.setenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    if sys.platform.startswith("linux"):
        assert Path.home() in paths.user_cache_dir().parents


def test_a_path_outside_the_exports_is_not_sandboxed(tmp_path: Path) -> None:
    """Der Wrapper wird am Ort erkannt, nicht am Namen.

    Ein selbst gebautes ``/opt/openscad/bin/openscad`` heißt genauso und läuft
    ohne Sandbox — und ein Arbeitsordner unter ``$HOME`` wäre dort nur langsamer
    aufgeräumt.
    """
    assert not discover.sandboxed(None)
    assert not discover.sandboxed(tmp_path / "openscad")
    assert not discover.sandboxed("/usr/local/bin/orca-slicer")
    assert not discover.sandboxed("/opt/OrcaSlicer/bin/orca-slicer")


def test_the_sandbox_folder_survives_a_second_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwei Läufe hintereinander sind zwei Ordner, nicht einer.

    ``mkdtemp`` und nicht ein fester Name: Ein zweiter Lauf, der in denselben
    Ordner schreibt, überschreibt die Datei des ersten — und bei zwei Objekten
    gleichzeitig wäre das ein Wettlauf um dieselben Namen.
    """
    wrapper = Path("~/.local/share/flatpak/exports/bin/org.openscad.OpenSCAD").expanduser()

    with (
        discover.workspace_for(wrapper, "probe-") as first,
        discover.workspace_for(wrapper, "probe-") as second,
    ):
        assert first != second
        assert first.parent == second.parent, "aber im selben Elternordner"
