"""Was ins Paket muss, und dass alle Beteiligten denselben Namen meinen.

Diese Datei ist aus zwei Funden entstanden, und beide fielen erst auf, als
jemand das Paket bauen wollte — keine Suite hatte je hingesehen:

* Die Spec baute nach ``dist/Solidon``, ``tools/make_installer.py`` suchte
  unter ``dist/Solidon3D``. Die Umbenennung war überall angekommen außer in
  der Paketierung. Ergebnis: keine Setup-Datei, und im Installer zeigten
  Startmenüeintrag und Deinstallationssymbol auf eine ``.exe``, die es unter
  dem Namen nicht gab.
* Die Bildschirmfotos des Handbuchs standen nicht in den ``datas``. Das Paket
  startete, das Handbuch öffnete, und an jeder Abbildung stand eine Lücke.

Beide Male genügte es, dass eine Zeichenkette an zwei Stellen gepflegt wurde.
Hier steht die Prüfung dagegen: der Name kommt aus ``app/branding.py``, und
jedes Verzeichnis mit Dateien, die kein Python sind, muss im Paket landen.

Seit macOS dazugehört, prüft der zweite Teil dieselbe Sache eine Ebene
früher: dass die eingecheckten Symbole heil sind, dass die Spezifikation dort
etwas Startbares beschreibt — ein Ordner ist auf einem Mac keine Anwendung —
und dass der Arbeitsablauf beide Architekturen paketiert. Der Bau selbst
läuft nur in der CI und nur bei Tags; was hier durchrutscht, fällt sonst
frühestens dort auf und im schlimmsten Fall erst dem ersten Nutzer beim
Doppelklick.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Final

from app.branding import APP_NAME

ROOT: Final = Path(__file__).resolve().parent.parent
SPEC: Final = ROOT / "packaging" / "solidon3d.spec"
INSTALLER_SCRIPT: Final = ROOT / "packaging" / "solidon3d.iss"
WORKFLOW: Final = ROOT / ".github" / "workflows" / "build.yml"
ICNS: Final = ROOT / "packaging" / "solidon3d.icns"
ICO: Final = ROOT / "packaging" / "solidon3d.ico"

#: Was beim Suchen nach Datenverzeichnissen nicht zählt.
IGNORED: Final = ("__pycache__", ".pyc", ".pyo")

#: Der Beginn einer PNG-Datei. Die modernen ICNS-Blöcke tragen PNG, und einen
#: Block, der etwas anderes trägt, übergeht macOS — das Symbol fehlt dann in
#: genau dieser Größe, ohne Fehlermeldung.
PNG_MAGIC: Final = b"\x89PNG\r\n\x1a\n"


def _data_directories() -> set[Path]:
    """Jedes Verzeichnis unter ``app/``, in dem etwas liegt, das kein Python ist.

    Genau diese Dateien fehlen im Paket, wenn niemand sie in die ``datas``
    schreibt: PyInstaller sammelt Module, keine Daten.
    """
    found: set[Path] = set()
    for path in (ROOT / "app").rglob("*"):
        if not path.is_file() or path.suffix == ".py":
            continue
        if any(part in str(path) for part in IGNORED):
            continue
        found.add(path.parent.relative_to(ROOT))
    return found


def test_every_data_directory_travels_with_the_package() -> None:
    """Ein Verzeichnis gilt als gedeckt, wenn es selbst oder ein Elternteil
    davon in der Spec steht — ``app/images/manual`` deckt beide Sprachen."""
    spec = SPEC.read_text(encoding="utf-8")
    for directory in sorted(_data_directories()):
        covered = [directory, *directory.parents]
        assert any(f'"{parent.as_posix()}"' in spec for parent in covered if parent != Path()), (
            f"{directory.as_posix()} liegt im Paket nicht bei — Eintrag in packaging/"
            f"solidon3d.spec unter datas fehlt"
        )


def test_the_spec_names_the_application_from_branding() -> None:
    """Kein zweiter Ort für den Namen. Der erste hat schon eine Umbenennung
    verschlafen.

    Gesucht wird der Import, nicht seine Schreibweise: Seit das Bundle auch
    Kennung, Fassung und Urheberrecht braucht, holt dieselbe Zeile mehrere
    Namen. Eine wörtliche Prüfung wäre hier rot geworden, ohne dass am Namen
    etwas falsch gewesen wäre.
    """
    spec = SPEC.read_text(encoding="utf-8")
    assert re.search(r"^from app\.branding import .*\bAPP_NAME\b", spec, re.MULTILINE)
    assert "name=APP_NAME" in spec
    assert f'name="{APP_NAME}"' not in spec, "der Name steht fest verdrahtet in der Spec"


def test_the_installer_finds_what_the_spec_builds() -> None:
    """``make_installer`` sucht ``dist/<APP_NAME>/<APP_NAME>.exe`` — die Spec
    muss genau das bauen, sonst endet der Bau mit „Kein Bau unter …"."""
    from tools.make_installer import SOURCE_DIR

    assert SOURCE_DIR == ROOT / "dist" / APP_NAME
    installer = INSTALLER_SCRIPT.read_text(encoding="utf-8")
    # Der Installer verweist auf {#AppName}.exe: Startmenü, Desktop, Symbol
    # der Deinstallation. Alle drei zeigen ins Leere, wenn die Spec anders baut.
    assert "{app}\\{#AppName}.exe" in installer


def test_the_workflow_carries_no_second_copy_of_the_name() -> None:
    """Die CI liest den Namen oder sucht mit Muster — sie schreibt ihn nicht.

    Sie tat es an vier Stellen (Signieren, Archiv, zwei Uploads), und nach der
    Umbenennung stimmte keine davon.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for wrong in (f"dist/{APP_NAME}-Setup-", "-C dist Solidon", "dist/Solidon/Solidon.exe"):
        assert wrong not in workflow, (
            f"{wrong!r} steht fest in build.yml statt aus branding zu kommen"
        )
    assert "from app.branding import APP_NAME" in workflow


def test_both_application_icons_exist() -> None:
    """Windows braucht das ICO, macOS das ICNS — beide liegen im Paketordner."""
    assert ICO.is_file(), "packaging/solidon3d.ico fehlt — tools/make_icon.py läuft nicht?"
    assert ICNS.is_file(), "packaging/solidon3d.icns fehlt — tools/make_icon.py läuft nicht?"


def test_the_icns_is_a_sound_container() -> None:
    """Das ICNS ist von der Kennung bis zum letzten Block in sich stimmig.

    Ein ICNS besteht aus Blöcken, die ihre Länge **einschließlich** der acht
    Kopfbytes angeben. Zählt eine Länge falsch, läuft das Lesen aus dem Tritt
    und die Datei gilt als beschädigt — dann zeigt macOS ein leeres Blatt
    statt des Symbols. Von außen sieht man einer solchen Datei nichts an,
    deshalb wird sie hier durchlaufen wie von einem Leser.
    """
    raw = ICNS.read_bytes()
    assert raw[:4] == b"icns", "Die Kennung am Anfang fehlt"
    assert struct.unpack(">I", raw[4:8])[0] == len(raw), "Die Länge im Kopf passt nicht zur Datei"

    position, kinds = 8, []
    while position < len(raw):
        kind = raw[position : position + 4].decode("ascii")
        length = struct.unpack(">I", raw[position + 4 : position + 8])[0]
        assert length > 8, f"Block {kind} hat keine Daten"
        assert raw[position + 8 : position + 16] == PNG_MAGIC, f"Block {kind} trägt kein PNG"
        kinds.append(kind)
        position += length
    assert position == len(raw), "Der letzte Block endet nicht am Dateiende"

    # Ohne den 1024er sieht das Symbol in der Übersicht des Finders unscharf
    # aus, ohne den 32er in der Menüleiste.
    assert {"icp5", "ic10"} <= set(kinds), f"Größen fehlen: {sorted(kinds)}"


def test_the_specification_builds_a_bundle_on_macos() -> None:
    """Die Spezifikation umschließt den Ordner auf macOS mit einem Bundle.

    COLLECT allein liefert dort einen Ordner, und ein Ordner ist auf einem Mac
    keine Anwendung: kein Start per Doppelklick, kein Symbol im Dock, nichts,
    was Gatekeeper prüfen könnte.
    """
    spec = SPEC.read_text(encoding="utf-8")
    assert "BUNDLE(" in spec
    assert 'sys.platform == "darwin"' in spec
    assert "bundle_identifier=APP_ID" in spec
    # Ohne diesen Eintrag rendert Qt auf einem Retina-Bildschirm halb aufgelöst.
    assert "NSHighResolutionCapable" in spec


def test_the_specification_picks_the_icon_for_its_platform() -> None:
    """Das ICO steht nicht mehr fest in der Spezifikation.

    PyInstaller nimmt auf macOS kein ICO an; stünde es dort weiter hart
    eingetragen, bräche der Bau erst auf dem Mac ab.
    """
    spec = SPEC.read_text(encoding="utf-8")
    assert "solidon3d.icns" in spec
    assert 'icon=str(ROOT / "packaging" / "solidon3d.ico")' not in spec


def test_the_workflow_packages_every_delivered_platform() -> None:
    """Der Arbeitsablauf baut Pakete für Windows, Linux und beide Macs.

    ``macos-13`` ist Intel, ``macos-latest`` Apple Silicon. Fehlt einer von
    beiden, fehlt die Hälfte der Mac-Nutzer — ein auf arm64 gebautes Paket
    startet auf einem Intel-Gerät nicht.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    matrix = next(line for line in workflow.splitlines() if "os: [windows-latest" in line)
    for runner in ("windows-latest", "ubuntu-latest", "macos-13", "macos-latest"):
        assert runner in matrix, f"{runner} fehlt in der Paket-Matrix"


def test_the_workflow_keeps_the_two_mac_packages_apart() -> None:
    """Beide Mac-Pakete kommen unter eigenem Namen an.

    Hießen die Artefakte gleich, überschriebe der zweite Lauf den ersten und
    übrig bliebe eines von beiden — ohne dass jemand sähe, welches.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "solidon3d-macos-${{ runner.arch }}" in workflow
    assert "macos-$(uname -m)" in workflow


def test_the_package_carries_qts_own_catalogues() -> None:
    """Die Standardknöpfe beschriftet Qt, nicht unser Katalog.

    ``install_qt_translations`` lädt ``qtbase_<sprache>.qm`` über
    ``QLibraryInfo.TranslationsPath``. In der Entwicklungsumgebung liegen die
    Dateien neben PySide6 und alle sechs Sprachen laden — im Paket hängt es
    daran, ob PyInstallers Hook sie einsammelt. Tut er es nicht, steht auf jedem
    zweiten Dialog „Cancel" statt „Abbrechen", und zwar **nur** im gebauten
    Programm: in der Entwicklung ist der Fehler unsichtbar.

    Geprüft wird die Absicht in der Spec, nicht das Ergebnis eines Baus — der
    läuft nur in der CI und nur bei Tags.
    """
    source = SPEC.read_text(encoding="utf-8")

    assert "qtbase_" in source, "die Spec nimmt Qts Sprachkataloge nicht ausdrücklich mit"
    assert "PySide6/translations" in source, "sie müssen dort landen, wo Qt sie sucht"
    # Die Liste darf nicht von Hand gepflegt sein — sie driftet sonst gegen
    # app/i18n/locales, wie schon die hiddenimports gegen den Bootstrap.
    assert 'glob("*.json")' in source, "die Sprachen kommen aus dem Katalogverzeichnis"
    # Und Deutsch muss dabeistehen: es ist die Quellsprache und hat dort keine
    # eigene Datei, wäre also ausgerechnet als Vorgabe englisch geblieben.
    assert '"de"' in source, "die Quellsprache braucht Qts Katalog genauso"


def test_qt_has_a_catalogue_for_every_language_we_offer() -> None:
    """Und die Kataloge müssen existieren, sonst nimmt die Spec nichts mit.

    Portugiesisch ist der Fall, an dem das auffällt: Qt liefert es nur als
    ``pt_BR``. Deshalb sucht die Spec mit Varianten — ``qtbase_pt.qm`` allein
    hätte für diese Sprache stillschweigend nichts eingepackt, und ``load``
    findet die Variante zur Laufzeit selbst.
    """
    import pytest

    pytest.importorskip("PySide6")
    import PySide6

    from app.i18n.catalog import available_languages

    catalogues = Path(PySide6.__file__).parent / "translations"
    missing = []
    for code in ("de", *available_languages()):
        if not sorted(catalogues.glob(f"qtbase_{code}*.qm")):
            missing.append(code)

    assert not missing, (
        f"Qt bringt für diese Sprachen keinen Katalog mit: {missing} — "
        "die Standardknöpfe bleiben dort englisch."
    )


def test_the_workflow_finds_every_file_that_builds_a_window() -> None:
    """Die CI gibt jeder Fensterdatei einen eigenen Prozess — sie muss sie finden.

    Der Absturz auf den Linux-Runnern hängt an der Zahl der VTK-Fenster, die ein
    Prozess nacheinander aufbaut; deshalb laufen die Fensterdateien einzeln. Die
    Liste wird gesucht und nicht gepflegt, und genau daran ist sie
    zurückgeblieben: Nach `MainWindow` allein fehlten `test_cursors.py` (acht
    Viewport-Aufbauten) und `test_plates.py` (einer) — neun Fenster mehr im
    großen Stapel, ohne dass es auffiel.

    Geprüft wird das Suchmuster aus dem Workflow gegen die Dateien, die
    wirklich eines **bauen**. Erwähnungen zählen nicht: ein Import oder die
    Lizenzliste bekämen sonst einen eigenen Prozess für nichts.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    found = re.search(r'windowed=\$\(grep -lE "([^"]+)"', workflow)
    assert found, "das Suchmuster der Fensterdateien steht nicht mehr im Workflow"
    pattern = re.compile(found.group(1))

    builders = re.compile(r"\b(MainWindow|Viewport|SketchPanel|OverlayHost|Plotter)\(")
    missed = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if not builders.search(source):
            continue
        if not pattern.search(source):
            missed.append(path.name)

    assert not missed, (
        f"Diese Dateien bauen ein Fenster und laufen trotzdem im großen Stapel: {missed}. "
        "Das Suchmuster in .github/workflows/build.yml findet sie nicht."
    )


# --- Die beiden Linux-Formate (§37.2) -------------------------------------------


def test_the_linux_descriptions_are_the_ones_the_tool_writes() -> None:
    """Die eingecheckten Beschreibungen sind die, die das Werkzeug heute schreibt.

    Dieselbe Prüfung wie bei den Handbuchabbildungen, und aus demselben Grund:
    Eine erzeugte Datei, die eingecheckt ist, veraltet still. Hier wäre der
    Schaden größer als ein falsches Bild — eine Versionsnummer im Manifest, die
    nicht zu `app/branding.py` passt, ergibt ein Paket, das außen neu aussieht
    und innen alt ist. Genau das steht als Begründung schon in
    ``tools/make_installer.py``.
    """
    from tools import make_linux_packages as tool

    stale = []
    for path, drawn in (
        (tool.DESKTOP_FILE, tool.desktop_entry()),
        (tool.FLATPAK_MANIFEST, tool.flatpak_manifest()),
        (tool.METAINFO_FILE, tool.metainfo()),
    ):
        assert path.is_file(), f"{path.name} fehlt — tools/make_linux_packages.py --files"
        if path.read_text(encoding="utf-8").replace("\r\n", "\n") != drawn:
            stale.append(path.name)

    assert not stale, (
        "älter als app/branding.py: "
        + ", ".join(stale)
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_linux_packages.py --files"
    )


def test_the_desktop_entry_carries_what_a_launcher_needs() -> None:
    """Ohne diese vier Zeilen ist der Menüeintrag kaputt, und zwar leise.

    Ein fehlendes ``Exec`` startet nichts, ein fehlendes ``Icon`` zeigt ein
    graues Feld, und ohne ``StartupWMClass`` steht in der Leiste neben dem
    Starter ein zweites, namenloses Fenster.
    """
    from app.branding import APP_ID, APP_NAME
    from tools import make_linux_packages as tool

    entry = dict(
        line.split("=", 1)
        for line in tool.desktop_entry().splitlines()
        if "=" in line and not line.startswith("[")
    )

    assert entry["Type"] == "Application"
    assert entry["Name"] == APP_NAME
    assert entry["Exec"].startswith(APP_NAME)
    assert entry["Icon"] == APP_ID, "das Symbol heißt wie die Anwendungskennung"
    assert entry["StartupWMClass"] == APP_NAME
    assert entry["Terminal"] == "false", "eine Oberfläche öffnet kein Terminal"
    # Die Kategorienliste endet auf ein Semikolon — die Freedesktop-Spezifikation
    # verlangt es, und ohne es verschluckt mancher Starter den letzten Eintrag.
    assert entry["Categories"].endswith(";")


def test_the_flatpak_manifest_stays_inside_its_sandbox() -> None:
    """Jede Berechtigung hat einen Grund, und Netz gehört nicht dazu.

    ``--share=network`` wäre die bequemste Zeile und die falsche: Ohne Netz gibt
    es kein Konto, keine Telemetrie und keine Frage danach — das ist die Zusage,
    mit der die Anwendung antritt (§2.1). Wer den Chat gegen einen Dienst fahren
    will, bekommt die Berechtigung über die Software-Verwaltung dazu.
    """
    from app.branding import APP_ID
    from tools import make_linux_packages as tool

    manifest = tool.flatpak_manifest()

    assert f"id: {APP_ID}" in manifest
    assert "--share=network" not in manifest, "das Paket verspricht, ohne Netz zu laufen"
    # Der Viewport rechnet mit OpenGL, und der Schlüssel des Agenten liegt im
    # Schlüsselbund — beides braucht seine Zeile.
    assert "--device=dri" in manifest
    assert "--talk-name=org.freedesktop.secrets" in manifest
    # Und die Anwendung startet über ihren eigenen Namen, nicht über ein Skript.
    assert "command: " in manifest


def test_the_metainfo_is_well_formed_and_names_both_licences() -> None:
    """AppStream ohne Metainfo heißt: ein Eintrag ohne Text.

    Die zwei Lizenzfelder zu verwechseln ist der häufigste Fehler in diesen
    Dateien — ``metadata_license`` gilt für die Beschreibung, ``project_license``
    für das Programm. Ein Programm, das seine eigene Lizenz als CC0 ausweist,
    verschenkt sich versehentlich.
    """
    import xml.etree.ElementTree as ET

    from app.branding import APP_ID, APP_VERSION
    from tools import make_linux_packages as tool

    root = ET.fromstring(tool.metainfo())

    assert root.tag == "component"
    assert root.findtext("id") == APP_ID
    assert root.findtext("metadata_license") == "CC0-1.0"
    project = root.findtext("project_license") or ""
    assert project and project != "CC0-1.0", "die Anwendung ist nicht gemeinfrei"
    assert root.findtext("summary")
    assert root.find("description") is not None
    versions = [entry.get("version") for entry in root.iter("release")]
    assert versions == [APP_VERSION], f"Version im Manifest: {versions}"


def test_the_workflow_builds_both_linux_formats() -> None:
    """Was das Werkzeug kann, muss die CI auch aufrufen.

    Ein Paketierweg, den nur ein Mensch von Hand gehen kann, ist bei der
    nächsten Veröffentlichung der Weg, den niemand geht.
    """
    workflow = (Path(__file__).parent.parent / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )

    assert "make_linux_packages.py" in workflow, "die CI ruft das Werkzeug nicht"
    assert ".AppImage" in workflow, "das AppImage wird nicht mitgenommen"
    assert ".flatpak" in workflow, "das Flatpak wird nicht mitgenommen"
