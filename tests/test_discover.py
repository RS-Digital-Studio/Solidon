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
import stat
import sys
import urllib.request
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


def test_a_local_launcher_and_a_remote_address_are_remembered_together(tmp_path: Path) -> None:
    """ComfyUI ist beides; die App-Auswahl darf die Webadresse nicht überschreiben."""
    program = tmp_path / "Comfy Desktop.exe"
    program.write_text("")

    try:
        discover.remember_address("comfyui", "http://192.168.1.5:8188")
        discover.remember_path("comfyui", str(program))

        assert discover.service_url("comfyui", "http://127.0.0.1:8188") == (
            "http://192.168.1.5:8188"
        )
        assert discover.unpatched_find_program("comfyui", ("Comfy Desktop",)) == program

        discover.use_local_address("comfyui")
        assert discover.service_url("comfyui", "http://127.0.0.1:8188") == ("http://127.0.0.1:8188")
        assert discover.remembered_remote_address("comfyui") == "http://192.168.1.5:8188"

        discover.remember_address("comfyui", "http://192.168.1.5:8188")
        assert discover.service_url("comfyui", "http://127.0.0.1:8188") == (
            "http://192.168.1.5:8188"
        )
    finally:
        discover.remember_address("comfyui", "")
        discover.remember_path("comfyui", "")


def test_a_manually_selected_macos_app_bundle_is_a_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine ``.app`` ist auf dem Dateisystem ein Ordner, für den Nutzer aber die App."""
    bundle = tmp_path / "Comfy Desktop.app"
    bundle.mkdir()
    monkeypatch.setattr(discover, "remembered_path", lambda _tool_id: str(bundle))
    monkeypatch.setattr(discover.sys, "platform", "darwin")

    assert discover.unpatched_find_program("comfyui", ("Comfy Desktop",)) == bundle


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


def test_a_workspace_that_cannot_be_created_carries_a_suggestion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Volle Platte oder schreibgeschützter Cache: kein roher ``OSError``.

    Der liefe im Export-Arbeiter als abgerissener Thread ohne ein Wort aus —
    ``FileWriteError`` trägt den Grund des Betriebssystems und einen
    Handlungsvorschlag (Regel 17). Beide Anlegewege sind gefasst.
    """
    import tempfile

    from app.core import errors, paths

    def explode(*_args: object, **_kwargs: object) -> object:
        raise OSError("No space left on device")

    monkeypatch.setattr(tempfile, "TemporaryDirectory", explode)
    with (
        pytest.raises(errors.FileWriteError) as caught,
        discover.workspace_for(tmp_path / "openscad.exe", "probe-"),
    ):
        raise AssertionError("bis hierher kommt es nicht")
    assert caught.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“"
    assert "No space left" in str(caught.value.values.get("reason", ""))

    wrapper = Path("~/.local/share/flatpak/exports/bin/org.openscad.OpenSCAD").expanduser()
    monkeypatch.setattr(tempfile, "mkdtemp", explode)
    with pytest.raises(errors.FileWriteError) as caught, discover.workspace_for(wrapper, "probe-"):
        raise AssertionError("bis hierher kommt es nicht")
    assert str(paths.user_cache_dir()) in str(caught.value.values.get("target", ""))


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


def test_a_windows_path_where_an_address_belongs_is_unreachable() -> None:
    """Dasselbe Feld meint bei OpenSCAD einen Pfad und bei Ollama eine Adresse.

    Ein Kunde trug am 24.08.2026 seinen Modellordner ein. ``urlparse`` liest
    alles hinter ``C:`` als Port und wirft beim Zugriff darauf ``ValueError``;
    gefangen wurde nur ``OSError``, und der Arbeiter des Einrichtungsdialogs
    starb mitten in der Einrichtung. Eine unbrauchbare Adresse heißt „nicht
    erreichbar" und nicht „Absturz" (Regel 17).
    """
    assert discover.reachable(r"C:\Users\Jemand\.ollama\models") is False
    assert discover.reachable("http://localhost:1") is False, "ein zu-Port bleibt zu"


def test_what_a_person_types_into_an_address_field_is_checked_there() -> None:
    """**Ein Feld, das jede Eingabe annimmt, verschiebt den Fehler nur.**

    Der Einrichtungsdialog fragte „Adresse, unter der es erreichbar ist" und
    speicherte, was kam. Ein Kunde trug dort am 24.08.2026 den Ordner seiner
    Modelle ein und suchte den Fehler danach drei Stunden an anderer Stelle —
    die Meldung, die ihn erreichte, sprach von etwas ganz anderem.

    Die Sollwerte stehen hier als *Fall* und nicht als Satz: Welcher Satz
    zurückkommt, darf sich ändern; dass diese Eingaben abgelehnt und jene
    angenommen werden, nicht.
    """
    unbrauchbar = (
        r"C:\Users\Jemand\.ollama\models",
        "/home/jemand/modelle",
        "~/modelle",
        "file:///c:/modelle",
        "http://host:keinport",
        "http://:11434",
    )
    for eingabe in unbrauchbar:
        assert discover.unusable_address(eingabe) is not None, eingabe

    brauchbar = (
        "http://localhost:11434",
        "http://127.0.0.1:8188",
        "127.0.0.1:11434",
        "https://werkstatt.lan:11434/api/chat",
        "",
    )
    for eingabe in brauchbar:
        assert discover.unusable_address(eingabe) is None, eingabe


def test_an_empty_address_is_no_complaint_but_a_reset() -> None:
    """Leer heißt „wieder die Vorgabe" — ``remember`` behandelt es genauso."""
    assert discover.unusable_address("   ") is None


def test_no_probe_asks_the_own_machine_for_an_address_that_has_no_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Ein leerer Rechnername ist für ``socket`` nicht „nichts", sondern
    *localhost*.**

    Alle drei Erreichbarkeitsprüfungen des Projekts hatten denselben Rückfall —
    ``hostname or "127.0.0.1"`` und ``or "localhost"`` —, und damit fragte eine
    Adresse, die gar keine ist, den eigenen Rechner. Wo etwas auf dem Port
    lauscht, meldet das „erreichbar", wo nichts lauscht, nicht.

    Genau daran ist der Test zu ``mesh.reachable`` in der CI gescheitert,
    während er auf dieser Maschine grün war (24.08.2026). Gefunden wurde eine
    Stelle; geprüft werden hier alle drei.

    **Geprüft wird, dass keine Verbindung *versucht* wird**, nicht nur, dass
    ``False`` herauskommt: Ohne Webserver auf Port 80 wäre dieser Test auch
    ohne den Fix grün — er würde dann die Abwesenheit eines fremden Dienstes
    messen und nicht unseren Code.
    """
    import socket

    from app.core.backends import llm, mesh

    attempts: list[object] = []

    def note(*args: object, **kwargs: object) -> object:
        attempts.append(args)
        raise OSError("in diesem Test wird nicht wirklich verbunden")

    monkeypatch.setattr(socket, "create_connection", note)

    for address in (r"C:\Users\Jemand\models", "http:///nur/ein/pfad", "file:///tmp/x"):
        assert discover.reachable(address) is False, f"discover: {address}"
        assert mesh.reachable(address) is False, f"mesh: {address}"
        assert llm.OllamaBackend(url=address).available is False, f"llm: {address}"

    assert attempts == [], f"es wurde trotzdem eine Verbindung versucht: {attempts}"


# --- wenn Solidon selbst in einem Flatpak läuft ---------------------------------
#
# Die Frage, die dieses Modul zwei Fassungen lang nicht gestellt hat. Es
# beschreibt sorgfältig, wie man einen Slicer findet, der als Flatpak
# installiert ist — und übersah, dass die eigene Linux-Auslieferung eines ist.


def test_the_own_flatpak_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Erkannt an ``/.flatpak-info`` oder an ``FLATPAK_ID``.

    Zwei Wege, weil eine Umgebung die Variable setzen kann, ohne dass die
    Datei da ist — und weil ein Test die Datei nicht anlegen soll.
    """
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(discover.Path, "exists", lambda self: False)
    assert not discover.in_flatpak(), "auf einem gewöhnlichen Rechner nicht"

    monkeypatch.setenv("FLATPAK_ID", "de.rsdigital.solidon3d")
    assert discover.in_flatpak()


def test_a_command_goes_to_the_host_only_from_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    """``flatpak-spawn --host`` kommt davor, wenn es nötig ist — sonst nichts.

    Die Funktion darf deshalb bedingungslos um jeden Start gelegt werden; wer
    sie an eine eigene Bedingung knüpft, baut die zweite Stelle, an der der
    Fall vergessen werden kann.
    """
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    assert discover.on_host(["slicer", "--export"]) == ["slicer", "--export"]

    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    assert discover.on_host(["slicer", "--export"]) == [
        "flatpak-spawn",
        "--host",
        "slicer",
        "--export",
    ]


def test_the_workspace_leaves_tmp_when_we_are_the_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Läuft Solidon im Flatpak, sieht der Slicer **unser** ``/tmp`` nicht.

    Die Richtung des Satzes kehrt sich um, das Ergebnis bleibt: Der
    Arbeitsordner gehört unter ``$HOME``, wo beide hinsehen können. Ohne das
    bekäme ein Host-Slicer einen Pfad, den es für ihn nicht gibt — „Can't open
    input file", unmittelbar nach einem Klick auf *An den Slicer übergeben*.

    **Hier stand ``user_cache_dir() in workspace``, und das war zu kurz
    gedacht.** Im Flatpak *ist* der Nutzer-Cache ``~/.var/app/<id>/cache``, und
    genau den nimmt ``--filesystem=home`` aus. Die Zusicherung galt einem Ort
    statt der Sache; sie hätte den Fehler, den sie verhindern soll,
    festgeschrieben. Geprüft wird deshalb, was der fremde Sandkasten sehen
    kann — unter ``$HOME`` und nicht in einem App-Verzeichnis.
    """
    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    # Ein gewöhnliches Programm auf dem Rechner, kein Flatpak-Wrapper.
    assert discover.sandboxed(Path("/usr/bin/prusa-slicer")), (
        "wenn wir der Sandkasten sind, zählt das Zielprogramm nicht mehr"
    )
    with discover.workspace_for(Path("/usr/bin/prusa-slicer"), "probe-") as workspace:
        assert Path.home() in workspace.parents, f"außerhalb von $HOME: {workspace}"
        assert ".var" not in workspace.parts, f"im eigenen App-Verzeichnis: {workspace}"


def test_the_host_is_asked_last_and_only_from_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die sechste Suchstufe fragt den Rechner — aber nur aus dem Sandkasten.

    Und der Pfad, der zurückkommt, ist ein **Host**-Pfad: Er existiert im
    Sandkasten nicht, ``is_file()`` darauf ist falsch. Startbar ist er über
    :func:`discover.on_host`.
    """
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    assert discover._from_host(("prusa-slicer",)) is None, "draußen wird niemand gefragt"

    calls: list[list[str]] = []

    class Answer:
        returncode = 0
        stdout = "/usr/bin/prusa-slicer\n"

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(command))
        return Answer()

    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    monkeypatch.setattr(discover.subprocess, "run", fake_run)

    assert discover._from_host(("prusa-slicer",)) == Path("/usr/bin/prusa-slicer")
    assert calls == [["flatpak-spawn", "--host", "which", "prusa-slicer"]]


def _appimage(folder: Path, name: str) -> Path:
    """Ein startbares AppImage mit dem unter Unix nötigen Ausführungsrecht."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"AI\x02ELF")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.mark.parametrize(
    ("filename", "wanted", "found"),
    [
        ("PrusaSlicer-2.8.1+linux-x64-GTK3.AppImage", "prusa-slicer", True),
        ("OrcaSlicer_Linux_V2.1.1.AppImage", "OrcaSlicer", True),
        ("UltiMaker-Cura-5.7.0-linux-X64.AppImage", "cura", True),
        ("BambuStudio_ubuntu-24.04_v01.09.AppImage", "bambu-studio", True),
        ("Cura.AppImage", "cura", True),
        # Der Fehlfang, gegen den die Segmentgrenze steht: Ohne sie faende
        # die Suche nach „git" das GitHub-Programm.
        ("GitHubDesktop.AppImage", "git", False),
        ("CuraEngineTest.AppImage", "cura", False),
        ("PrusaGcodeviewer-2.8.1.AppImage", "prusa-slicer", False),
    ],
)
def test_an_appimage_is_found_by_its_segments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    wanted: str,
    found: bool,
) -> None:
    """AppImages tragen Version und Plattform im Namen — verglichen wird je Segment.

    **Der haeufigste Linux-Fall.** PrusaSlicer, OrcaSlicer, Cura und
    BambuStudio liefern fuer Linux in erster Linie ein AppImage aus; keine der
    fuenf Stufen davor sucht etwas anderes als einen exakten Namen in einem
    Installationsordner.

    Die Faelle mit ``False`` sind die eigentliche Zusicherung: Eine Suche, die
    zu viel findet, gibt dem Aufrufer ein Programm, das er nie gemeint hat.
    """
    monkeypatch.setattr(discover.sys, "platform", "linux")
    monkeypatch.setattr(discover, "_APPIMAGE_FOLDERS", (str(tmp_path / "Applications"),))
    path = _appimage(tmp_path / "Applications", filename)

    result = discover._from_appimage((wanted,))
    assert (result == path) is found, f"{filename} fuer {wanted}: {result}"


def test_an_appimage_without_the_executable_bit_is_not_a_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ohne ``chmod +x`` ist es kein Programm, das man starten kann.

    Es als gefunden zu melden hiesse, den Fehler eine Stelle spaeter und
    unverstaendlicher auftauchen zu lassen — „Permission denied" mitten in der
    Uebergabe statt „nicht gefunden" in der Liste. Ins Protokoll geht es
    trotzdem: Das ist die Auskunft, die dem Support die Rueckfrage erspart.
    """
    monkeypatch.setattr(discover.sys, "platform", "linux")
    monkeypatch.setattr(discover, "_APPIMAGE_FOLDERS", (str(tmp_path / "Applications"),))
    _appimage(tmp_path / "Applications", "PrusaSlicer-2.8.1.AppImage")
    monkeypatch.setattr(discover.os, "access", lambda path, mode: False)

    with caplog.at_level(logging.INFO):
        assert discover._from_appimage(("prusa-slicer",)) is None
    assert "not executable" in caplog.text


def test_find_program_reaches_the_appimage_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und die Stufe haengt wirklich in der Kette.

    Die Zusicherung darueber prueft die Stufe; diese hier prueft, dass
    :func:`discover.find_program` sie **erreicht**. Eine Funktion, die richtig
    rechnet und die niemand ruft, ist der teuerste aller gruenen Tests.
    """
    monkeypatch.setattr(discover.sys, "platform", "linux")
    monkeypatch.setattr(discover, "_APPIMAGE_FOLDERS", (str(tmp_path / "Applications"),))
    monkeypatch.setattr(discover.shutil, "which", lambda name: None)
    monkeypatch.setattr(discover, "_load", dict)
    monkeypatch.setattr(discover, "_install_roots", tuple)
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", ())
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    discover.forget_cache()
    path = _appimage(tmp_path / "Applications", "OrcaSlicer_Linux_V2.1.1.AppImage")

    # Nicht ``discover.find_program`` — das ist in der Suite die Attrappe aus
    # ``conftest``, die nur zurückgibt, was ausdrücklich gesetzt wurde. Genau
    # sie würde diesen Test grün machen, ohne die Kette je zu betreten.
    assert discover.unpatched_find_program("orcaslicer", ("OrcaSlicer", "orca-slicer")) == path


def test_a_service_on_this_machine_does_not_go_through_the_company_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama und ComfyUI laufen hier — der Proxy kennt sie nicht.

    ``urlopen`` baut seinen Öffner aus ``getproxies()``, und das liest
    ``http_proxy`` und unter Windows und macOS die Systemeinstellung. Für die
    Update-Prüfung ist das genau richtig; für einen Dienst auf demselben
    Rechner genau falsch. Gemessen am 27.08.2026 mit gesetztem ``http_proxy``
    und ohne ``no_proxy``::

        proxy_bypass("localhost:11434")   False
        proxy_bypass("127.0.0.1:8188")    False

    Ergebnis wäre „Backend nicht erreichbar" für ein Programm, das läuft —
    dieselbe Sorte Auskunft wie „nicht gefunden" für ein installiertes
    Programm, und aus demselben Grund die schlechteste.
    """
    monkeypatch.setenv("http_proxy", "http://firma:8080")
    monkeypatch.setenv("https_proxy", "http://firma:8080")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)

    def proxies_of(url: str) -> dict[str, str]:
        for handler in discover.opener_for(url).handlers:
            if isinstance(handler, urllib.request.ProxyHandler):
                return dict(handler.proxies)
        return {}

    for local in (
        "http://localhost:11434/api/tags",
        "http://127.0.0.1:8188/prompt",
        "http://127.0.0.53:8080/x",
        "http://[::1]:11434/api/tags",
        "http://ollama.localhost/api/tags",
    ):
        assert proxies_of(local) == {}, f"{local} ging durch den Proxy"

    # Und die Gegenrichtung: Wer hinter einem Firmenproxy sitzt, erreicht die
    # Update-Prüfung nur durch ihn. Sie darf ihn also nicht verlieren.
    outside = proxies_of("https://solidon3d.de/version.json")
    assert outside, "der Proxy nach draußen muss bleiben"


def test_what_counts_as_this_machine() -> None:
    """Was lokal ist und was nur so aussieht.

    Die Grenze ist eng gezogen: ``127.`` deckt das ganze /8, weil
    systemd-resolved tatsächlich auf ``127.0.0.53`` sitzt. Ein Rechnername,
    der bloß *anfängt* wie einer der lokalen, gehört nicht dazu — sonst
    verlöre ``localhost.beispiel.de`` seinen Proxy, und das ist eine fremde
    Maschine.
    """
    for local in ("http://localhost:1", "http://127.0.0.1", "http://[::1]:2", "http://x.localhost"):
        assert discover.is_local_address(local), local
    for remote in (
        "https://solidon3d.de",
        "http://localhost.beispiel.de",
        "http://192.168.1.5:11434",
        "http://127x.de",
    ):
        assert not discover.is_local_address(remote), remote


def test_two_sandboxes_need_a_place_that_is_in_neither(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Läuft Solidon selbst als Flatpak, liegt sein Cache im eigenen Sandkasten.

    ``workspace_for`` legt den Arbeitsordner in den Nutzer-Cache, weil die
    Slicer-Pakete ``--filesystem=home`` freigeben. Das trägt genau so lange,
    wie **wir** kein Flatpak sind: Dann setzt Flatpak ``XDG_CACHE_HOME`` auf
    ``~/.var/app/<unsere-id>/cache``, und ``--filesystem=home`` nimmt ``~/.var``
    ausdrücklich aus — Flatpak blendet die App-Verzeichnisse gegeneinander aus.

    Die Folge wäre derselbe Fehler, den die Funktion verhindern soll, nur eine
    Ebene weiter: Der Ordner liegt in ``$HOME``, der Slicer darf ``$HOME``
    lesen, und die Datei ist trotzdem unsichtbar.
    """
    home = tmp_path / "home" / "rober"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    # Wie Flatpak es setzt: der Cache zeigt in unser eigenes App-Verzeichnis.
    sandbox_cache = home / ".var" / "app" / "de.rsdigital.solidon3d" / "cache"
    monkeypatch.setattr(discover, "user_cache_dir", lambda: sandbox_cache)

    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    outside = discover.exchange_dir()
    assert outside == sandbox_cache / "sandbox", "draußen bleibt es der Nutzer-Cache"

    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    inside = discover.exchange_dir()
    assert ".var" not in inside.parts, f"liegt im eigenen Sandkasten: {inside}"
    assert home in inside.parents, f"ein fremdes Flatpak sieht nur $HOME: {inside}"


def test_the_workspace_of_a_sandboxed_program_lands_where_it_can_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und der Arbeitsordner entsteht wirklich dort.

    Die Zusicherung darüber prüft die Antwort, diese hier prüft, dass
    :func:`discover.workspace_for` sie **benutzt** — sonst rechnete eine
    richtige Funktion ins Leere.
    """
    shared = tmp_path / "austausch"
    monkeypatch.setattr(discover, "exchange_dir", lambda: shared)
    monkeypatch.setattr(discover, "sandboxed", lambda program: True)

    with discover.workspace_for("/usr/bin/orca-slicer", "solidon-") as folder:
        assert folder.is_dir()
        assert folder.parent == shared, f"nicht im Austauschordner: {folder}"
        (folder / "platte.3mf").write_text("x")

    assert not folder.exists(), "der Ordner wird hinterher geräumt"
