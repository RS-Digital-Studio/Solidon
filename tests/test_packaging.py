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
import shutil
import struct
import subprocess
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


def test_every_optional_dependency_the_package_needs_is_a_hidden_import() -> None:
    """Was nur in einer Funktion importiert wird, sieht PyInstaller nicht.

    ``keyring`` fehlte, und das war kein Schönheitsfehler: ``backends/keys.py``
    importiert es innerhalb von ``_keyring()``, damit die Anwendung ohne es
    startet. Im gebauten Paket lag es damit nicht bei, ``keys.store()`` gab
    immer False zurück — **der Kunde konnte seinen Schlüssel nicht ablegen**,
    und der Rückfall war eine Umgebungsvariable, gedacht für einen Bauserver.

    Geprüft werden die Namen, die die Anwendung zur Laufzeit nachschlägt, und
    nicht die Liste in der Spec: Die kann nur zu kurz sein, und genau das war
    sie.
    """
    spec = SPEC.read_text(encoding="utf-8")
    from app.core import install

    for entry in install.REQUIREMENTS:
        if entry.kind != "package" or not entry.module:
            continue
        top = entry.module.split(".")[0]
        assert f'"{top}' in spec, (
            f"{entry.id}: {top} steht nicht in den hiddenimports von packaging/"
            f"solidon3d.spec — im Paket fehlt es dann, und die Anwendung hält es "
            f"für nicht installiert"
        )


def test_the_spec_names_the_application_from_branding() -> None:
    """Kein zweiter Ort für den Namen. Der erste hat schon eine Umbenennung
    verschlafen.

    Gesucht wird der Import, nicht seine Schreibweise: Seit das Bundle auch
    Kennung, Version und Urheberrecht braucht, holt dieselbe Zeile mehrere
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

    ``macos-latest`` ist Apple Silicon, daneben muss ein Intel-Mac stehen:
    Fehlt einer von beiden, fehlt die Hälfte der Mac-Nutzer — ein auf arm64
    gebautes Paket startet auf einem Intel-Gerät nicht.

    Drei der vier Labels enden auf ``-latest`` und wandern mit. Für Intel gibt
    es das nicht; x64 läuft nur unter seiner Nummer, und die wechselt — erst
    ``macos-13``, dann ``macos-26-intel``. Ein festes Label hier hätte den
    Test nach dem nächsten Wechsel rot stehen lassen, ohne dass am Bau etwas
    fehlt. Geprüft wird deshalb, *dass* ein Intel-Mac dabei ist, nicht welche
    Nummer er trägt.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    matrix = next(line for line in workflow.splitlines() if "os: [windows-latest" in line)
    for runner in ("windows-latest", "ubuntu-latest", "macos-latest"):
        assert runner in matrix, f"{runner} fehlt in der Paket-Matrix"
    assert "-intel" in matrix, f"kein Intel-Mac in der Paket-Matrix: {matrix.strip()}"


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
        (tool.INSTALL_SCRIPT, tool.install_script()),
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


def test_every_platform_can_do_the_same_things() -> None:
    """Jede Berechtigung hat einen Grund, und Netz gehört seit dem 27.08.2026 dazu.

    **Hier stand das Gegenteil**, mit einer Begründung, die plausibel klang:
    Ohne Netz gebe es kein Konto, keine Telemetrie und keine Frage danach.

    Ein Kunde auf CachyOS hat gezeigt, was das kostet. Sein Fehlerbericht kam
    per Hand, weil die Anwendung ihn nicht senden konnte — im Protokoll steht
    ``[Errno -3] Temporärer Fehler bei der Namensauflösung``, bei jedem Start
    für die Aktualisierungsprüfung und einmal für die Sendung. Was für uns eine
    saubere Sandbox war, war für ihn eine Anwendung, deren Knöpfe nicht gehen.

    **Die Zusage hing nie an der Sandbox**, sondern an der Bauart:
    ``support.send()`` hat genau einen Aufrufer, und der sitzt an einem Knopf —
    ``test_support.py`` zählt ihn. Windows und macOS haben keine Sandbox und
    dieselbe Zusage. Eine Grenze, die nur auf einer der drei Plattformen steht,
    ist keine Zusage, sondern ein Unterschied.

    Entscheidung Robert, 27.08.2026: „jede plattform sollte das gleiche haben
    und alles funktionieren."
    """
    from app.branding import APP_ID
    from tools import make_linux_packages as tool

    manifest = tool.flatpak_manifest()

    assert f"id: {APP_ID}" in manifest
    assert "--share=network" in manifest, (
        "ohne Netz kann der Kunde weder eine Rückmeldung senden noch nach "
        "Aktualisierungen sehen — auf Windows und macOS kann er beides"
    )
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


def test_the_flatpak_source_is_the_app_and_not_the_output_folder() -> None:
    """Die Quelle darf nicht der Ordner sein, in den der Bau selbst schreibt.

    ``path: ../dist`` nahm alles unter ``dist`` mit — und dorthin schreiben
    ``build_flatpak`` (``flatpak-repo``, ``flatpak-build``) und
    ``build_appimage`` (``<APP_NAME>.AppDir``) ihre Ergebnisse. Der zweite Lauf
    hätte die Zwischenausgabe des ersten mit eingepackt, und nach einem
    AppImage-Bau eine vollständige zweite Kopie der Anwendung dazu.

    Aufgefallen ist es nie, weil kein Bau je gelaufen ist: Er braucht Linux und
    zwei externe Programme. Ein Rezept, das niemand ausführt, prüft nur ein
    Test.
    """
    from app.branding import APP_NAME
    from tools import make_linux_packages as tool

    manifest = tool.flatpak_manifest()
    quellen = [
        zeile.split("path:", 1)[1].strip() for zeile in manifest.splitlines() if "path:" in zeile
    ]
    # Ohne diese Zeile bestünde der Test auch dann, wenn das Manifest gar keine
    # Quelle nennt — ein Flatpak ohne Inhalt hat auch kein falsches Verzeichnis.
    assert quellen, "das Flatpak-Manifest nennt keine einzige Quelle"
    verzeichnis = [
        (tool.FLATPAK_MANIFEST.parent / pfad).resolve()
        for pfad in quellen
        if (tool.FLATPAK_MANIFEST.parent / pfad).resolve() == tool.OUTPUT_DIR
    ]

    assert not verzeichnis, f"die Quelle ist der Ausgabeordner: {verzeichnis}"
    assert f"path: ../dist/{APP_NAME}" in manifest, "die Anwendung selbst fehlt als Quelle"
    # ``dest`` hält das Unterverzeichnis, das die Baubefehle nennen — ohne es
    # läge der Inhalt flach im Bauordner und ``cp -r <APP_NAME>/*`` griffe ins Leere.
    assert f"dest: {APP_NAME}" in manifest
    assert f"cp -r {APP_NAME}/*" in manifest, "Quelle und Kopierbefehl sind auseinandergelaufen"


# --- Die zwei Fragen: Lizenzvertrag und Ort (§37.2) ------------------------------


def test_the_windows_installer_asks_both_questions() -> None:
    """Der Lizenzvertrag steht, und die Verzeichnisseite wird nicht übersprungen.

    Beides ist eine Zeile, und beide Zeilen fehlen leise: Ohne ``LicenseFile``
    installiert das Setup ohne einen gelesenen Vertrag, und ``DisableDirPage``
    steht ohne Angabe auf ``auto`` — dann verschwindet die Ortswahl, sobald der
    Installer eine frühere Installation findet. Wer seine Programme auf eine
    zweite Platte legt, merkt das erst, wenn es zu spät ist.
    """
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8")

    assert "LicenseFile={#LicenseFile}" in script, "die Lizenzseite fehlt"
    assert "DisableDirPage=no" in script, "die Verzeichnisseite darf nicht wegfallen"
    assert "DisableDirPage=yes" not in script


def test_the_windows_installer_speaks_every_language_the_application_does() -> None:
    """Sechs Sprachen in der Anwendung, sechs im Installer.

    Wer Solidon auf Portugiesisch benutzt, soll es nicht auf Englisch
    installieren müssen — und die Kataloge dafür liefert Inno Setup selbst.
    """
    from app.i18n.catalog import available_languages

    script = INSTALLER_SCRIPT.read_text(encoding="utf-8")
    names = {
        "de": "German",
        "en": "Default",
        "es": "Spanish",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
    }

    missing = [
        code
        for code in ({"de"} | set(available_languages()))
        if names.get(code, "") and f"{names[code]}.isl" not in script
    ]
    assert not missing, f"im Installer fehlen diese Sprachen: {sorted(missing)}"


def test_every_custom_message_speaks_a_language_the_installer_knows() -> None:
    """Jedes CustomMessages-Präfix ist ein Name aus [Languages].

    In Inno Setup ist ein unbekanntes Präfix ein Kompilierfehler, kein
    stiller Rückfall: Als [Languages] auf die Kürzel der Anwendung umzog
    (de, en, …), behielten die CustomMessages ihre alten Präfixe (german.,
    english., …), und ISCC brach mit „Unknown language name" ab — gemessen
    am 25.08.2026, und kein Test sah es, weil nur .isl-Dateien gezählt
    wurden.
    """
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8")

    def section(title: str) -> list[str]:
        lines: list[str] = []
        active = False
        for line in script.splitlines():
            bare = line.strip()
            if bare.startswith("["):
                active = bare == f"[{title}]"
                continue
            if active and bare and not bare.startswith(";"):
                lines.append(bare)
        return lines

    known = {line.split('"')[1] for line in section("Languages") if line.startswith("Name:")}
    prefixes = {
        line.split(".", 1)[0] for line in section("CustomMessages") if "." in line.split("=", 1)[0]
    }
    strangers = sorted(prefixes - known)
    assert not strangers, f"diese CustomMessages-Präfixe kennt [Languages] nicht: {strangers}"


def test_the_licence_the_installer_shows_is_the_agreement_and_not_the_notice() -> None:
    """Auf der Lizenzseite steht der Endnutzer-Lizenzvertrag.

    ``LICENSE`` ist eine Urheberrechtsnotiz und sagt dem Käufer nicht, was er
    erwirbt. Der Vertrag steht in ``EULA.md``; ``tools/make_legal.py`` legt die
    Textversion daneben, weil Inno Setup und der macOS-Installer die Datei roh
    anzeigen.
    """
    from tools import make_installer

    licence = ROOT / "packaging" / "eula.txt"
    assert licence.is_file(), "packaging/eula.txt fehlt — tools/make_legal.py"
    assert make_installer._licence_file() == licence
    assert "Lizenzvertrag" in licence.read_text(encoding="utf-8")[:400]


def test_the_linux_installer_asks_before_it_writes_anything() -> None:
    """Das Installationsskript fragt nach Zustimmung und nach dem Ort.

    Ein Archiv, das man irgendwohin auspackt, beantwortet die erste Frage gar
    nicht und die zweite ohne Vorschlag. Die Zustimmung darf dabei nicht
    stillschweigend angenommen werden, wenn niemand antworten kann: ohne
    Terminal und ohne ``--accept`` bricht es ab.
    """
    from tools import make_linux_packages as tool

    script = tool.install_script()

    assert script.startswith("#!/bin/sh"), "kein POSIX-Skript"
    assert "eula.txt" in script, "der Lizenzvertrag wird nicht gezeigt"
    assert "--accept" in script and "--prefix" in script
    assert "--uninstall" in script, "es fehlt der Weg zurück"
    assert "if [ ! -t 0 ]; then" in script, "ohne Terminal würde es einfach durchlaufen"
    assert "uninstall.sh" in script, "die Installation hinterlässt keinen Weg zurück"


def test_the_linux_archive_carries_what_the_installer_needs() -> None:
    """Das Archiv trägt Skript, Lizenz, Menüeintrag und Symbol — nicht nur den Bau.

    Der ``tar``-Aufruf, der in der CI stand, packte genau den Ordner aus
    ``dist``. Wer ihn auspackte, hatte ein Programm ohne Menüeintrag, ohne
    Symbol und ohne gelesenen Lizenzvertrag.
    """
    import inspect

    from tools import make_linux_packages as tool

    source = inspect.getsource(tool.build_tarball)

    for needed in ("install.sh", "eula.txt", "icon.svg", "DESKTOP_FILE", "METAINFO_FILE"):
        assert needed in source, f"das Archiv nimmt {needed} nicht mit"


def test_the_macos_package_shows_the_licence_and_lets_the_place_be_chosen() -> None:
    """Die ``.pkg`` stellt dieselben zwei Fragen wie die Setup-Datei.

    ``license`` ist die Seite mit „Akzeptieren", ``domains`` die mit der Wahl
    zwischen „für alle Benutzer", „nur für mich" und einem anderen Volume.
    Ohne die zweite Zeile installiert macOS ohne zu fragen ins System.
    """
    import xml.etree.ElementTree as ET

    from tools import make_macos_package as tool

    root = ET.fromstring(tool.distribution("arm64"))

    licence = root.find("license")
    assert licence is not None and licence.get("file") == "eula.txt"

    domains = root.find("domains")
    assert domains is not None, "ohne <domains> gibt es keine Zielwahl"
    assert domains.get("enable_localSystem") == "true"
    assert domains.get("enable_currentUserHome") == "true"
    assert domains.get("enable_anywhere") == "true"


def test_the_macos_package_keeps_the_two_architectures_apart() -> None:
    """Ein auf Apple Silicon gebautes Paket gehört nicht auf einen Intel-Mac.

    Ohne ``hostArchitectures`` installiert es sich dort anstandslos und startet
    dann nicht — und der Nutzer sucht den Fehler an seinem Rechner.
    """
    import xml.etree.ElementTree as ET

    from tools import make_macos_package as tool

    for architecture in ("arm64", "x86_64"):
        root = ET.fromstring(tool.distribution(architecture))
        options = root.find("options")
        assert options is not None
        assert options.get("hostArchitectures") == architecture


def test_the_macos_description_is_the_one_the_tool_writes() -> None:
    """Auch hier: eine erzeugte, eingecheckte Datei veraltet still.

    Sie trägt die Versionsnummer — läuft sie gegen ``app/branding.py``,
    installiert das Paket eine Version unter dem Namen einer anderen.
    """
    from tools import make_macos_package as tool

    path = tool.DISTRIBUTION_FILE
    assert path.is_file(), "macos-distribution.xml fehlt — tools/make_macos_package.py --files"
    drawn = tool.distribution("arm64")
    assert path.read_text(encoding="utf-8").replace("\r\n", "\n") == drawn, (
        "älter als app/branding.py\n\nNeu erzeugen: "
        ".venv\\Scripts\\python.exe tools/make_macos_package.py --files"
    )


def test_the_workflow_builds_the_macos_installer_package() -> None:
    """Was das Werkzeug kann, muss die CI auch aufrufen — und hochladen.

    Auf keinem Rechner hier läuft macOS; wenn die CI die ``.pkg`` nicht baut,
    baut sie niemand.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "make_macos_package.py" in workflow, "die CI ruft das Werkzeug nicht"
    assert "*-macos-*.pkg" in workflow, "die .pkg wird nicht hochgeladen"


# --- Die Projektdatei gehört der Anwendung (Dateizuordnung) ---------------------


def test_the_windows_installer_registers_the_project_extension() -> None:
    """Ein Doppelklick auf ein Projekt muss hier landen, nicht im Nirgendwo.

    Fünf Einträge, und jeder einzelne macht die Zuordnung sonst wertlos: die
    Endung muss auf die Kennung zeigen, die Kennung einen Namen und ein Symbol
    haben, und der Öffnen-Befehl muss den Pfad als Argument weitergeben. Ohne
    ``"%1"`` startet die Anwendung mit leerem Fenster — der häufigste Fehler an
    dieser Stelle, und einer, den man erst nach dem Installieren sieht.
    """
    from app.branding import APP_ID, PROJECT_SUFFIX

    script = INSTALLER_SCRIPT.read_text(encoding="utf-8")

    assert "[Registry]" in script, "die Zuordnung fehlt ganz"
    assert "{#ProjectSuffix}\\OpenWithProgids" in script
    assert "{#AppId}.project" in script, "die Kennung steht fest verdrahtet statt als Define"
    assert '""%1""' in script, "der Öffnen-Befehl gibt den Pfad nicht weiter"
    assert "DefaultIcon" in script, "die Projektdatei bekäme ein leeres Symbol"
    assert "Tasks: associate" in script, "die Zuordnung hängt an keiner Aufgabe"
    # Und die Endung kommt aus branding, nicht aus dem Skript — sonst stünde
    # nach einer Änderung dort die alte und hier die neue.
    assert PROJECT_SUFFIX not in script, "die Endung steht fest im Installer"
    assert APP_ID not in script, "die Kennung steht fest im Installer"

    tool = (ROOT / "tools" / "make_installer.py").read_text(encoding="utf-8")
    assert "/DProjectSuffix={PROJECT_SUFFIX}" in tool, (
        "make_installer.py reicht die Endung nicht als Define herein — "
        "das Skript oben bekäme einen Kompilierfehler"
    )


def test_the_bundle_owns_the_project_type_on_macos() -> None:
    """Das Bundle meldet den Dokumenttyp an — und erklärt ihn auch.

    Beide Einträge werden gebraucht: Die Deklaration sagt dem System, dass es
    den Typ gibt und woran es ihn erkennt, der Dokumenttyp sagt, wer ihn
    öffnet. Fehlt die Deklaration, kennt macOS die Endung nicht und ordnet sie
    niemandem zu.
    """
    from app.branding import APP_ID, PROJECT_SUFFIX

    spec = SPEC.read_text(encoding="utf-8")

    assert "CFBundleDocumentTypes" in spec
    assert "UTExportedTypeDeclarations" in spec
    assert f"{APP_ID}.project" not in spec or 'f"{APP_ID}.project"' in spec
    assert '"LSHandlerRank": "Owner"' in spec, "wir wären nur ein Programm unter vielen"
    # Eine Projektdatei ist ein ZIP (§16.1) — ohne diese Zeile hält der Finder
    # sie für ein Archiv.
    assert "public.zip-archive" in spec
    assert 'PROJECT_SUFFIX.lstrip(".")' in spec, "die Endung steht fest in der Spec"
    assert PROJECT_SUFFIX not in spec.replace("PROJECT_SUFFIX", "")


def test_the_linux_type_is_defined_and_not_only_claimed() -> None:
    """Der Menüeintrag nannte einen Typ, den niemand definiert hatte.

    Eine ``MimeType``-Zeile ordnet nichts zu, solange das System den Typ nicht
    kennt: Eine Projektdatei ist ein ZIP, und ohne eigene Beschreibung erkennt
    shared-mime-info sie als Archiv — der Doppelklick landete beim
    Archivierungsprogramm.
    """
    import xml.etree.ElementTree as ET

    from app.branding import PROJECT_SUFFIX
    from tools import make_linux_packages as tool

    root = ET.fromstring(tool.mime_definition())
    space = "{http://www.freedesktop.org/standards/shared-mime-info}"

    entry = root.find(f"{space}mime-type")
    assert entry is not None and entry.get("type") == tool.MIME_TYPE

    glob = entry.find(f"{space}glob")
    assert glob is not None and glob.get("pattern") == f"*{PROJECT_SUFFIX}"

    parent = entry.find(f"{space}sub-class-of")
    assert parent is not None and parent.get("type") == "application/zip", (
        "ohne diese Zeile gewinnt die Inhaltserkennung, und die sieht ein ZIP"
    )

    # Menüeintrag und Beschreibung müssen denselben Typ meinen.
    assert f"MimeType={tool.MIME_TYPE};" in tool.desktop_entry()

    # Und der Dateimanager nennt ihn in jeder Sprache, die die Anwendung spricht.
    from app.i18n.catalog import available_languages

    named = {node.get("{http://www.w3.org/XML/1998/namespace}lang") for node in entry}
    missing = sorted(set(available_languages()) - named - {"en"})
    assert not missing, f"der Typ bleibt in diesen Sprachen englisch: {missing}"


def test_the_linux_installer_registers_the_type() -> None:
    """Die Beschreibung liegt nur dann richtig, wenn sie auch eingetragen wird.

    Kopieren allein genügt nicht: Ohne ``update-mime-database`` liegt die Datei
    da und gilt nicht.
    """
    from tools import make_linux_packages as tool

    script = tool.install_script()

    assert "$MIME_DIR/packages/" in script, "die Typbeschreibung wird nicht installiert"
    assert "update-mime-database" in script, "die Datenbank wird nicht neu gebaut"
    assert script.count("update-mime-database") >= 2, (
        "beim Entfernen muss sie ebenfalls neu gebaut werden"
    )
    assert "$MIME_DIR/packages/$IDENTIFIER.xml" in tool.install_script()

    # Und im Flatpak reist sie mit — dort trägt die Installation sie selbst ein.
    manifest = tool.flatpak_manifest()
    assert "/app/share/mime/packages/" in manifest


def test_a_manifest_that_no_longer_covers_the_boundary_files_stops_the_build() -> None:
    """Ein Paket, das startet und in dem nichts geht, darf nicht entstehen.

    Das Manifest deckt die vier Grenzdateien aus §2 C und wird beim Übersetzen
    des Prüfmoduls signiert. Ändert danach jemand eine davon und lässt nur
    PyInstaller neu laufen, ist die Auslieferung gesperrt: Ändern, Exportieren,
    Slicen und Chat — alles zu, und von außen sieht das Paket tadellos aus.

    Genau das ist am 20.08.2026 passiert und erst im Protokoll einer
    Testinstallation aufgefallen. Geprüft wird gegen ein Manifest mit einer
    verstellten Prüfsumme; das echte muss zugleich sauber durchgehen, sonst
    prüfte dieser Test nur seine eigene Attrappe.
    """
    import json

    from tools import make_installer

    real = ROOT / "packaging" / "build" / "licence.manifest"
    if not real.is_file():
        import pytest

        pytest.skip("kein gebautes Prüfmodul — nichts zu vergleichen")

    assert make_installer.manifest_reason(real) == "", (
        "das eingecheckte Manifest passt nicht zu den Grenzdateien — "
        "python tools/build_licence_module.py"
    )

    import tempfile

    signed = json.loads(real.read_text(encoding="utf-8"))
    name = next(iter(signed["files"]))
    signed["files"][name] = "0" * 64
    with tempfile.TemporaryDirectory() as scratch:
        fake = Path(scratch) / "licence.manifest"
        fake.write_text(json.dumps(signed), encoding="utf-8")
        reason = make_installer.manifest_reason(fake)

    assert name in reason, f"die verstellte Datei wird nicht genannt: {reason!r}"
    assert "build_licence_module" in reason, "ohne den Weg zurück ist es eine Absage"


def test_the_linux_installer_never_deletes_a_shared_directory(tmp_path: Path) -> None:
    """Was das Skript löscht, muss ihm auch gehören.

    Es prüfte ``$TARGET/$NAME`` und löschte ``$TARGET`` — bei den Vorgaben
    (``/opt/solidon3d``) ist das genau richtig. Nur heißt der Schalter
    ``--prefix``, und wer den von autotools kennt, gibt ``/usr/local`` an: Der
    erste Lauf legt dort ``Solidon3D`` ab, der zweite findet es und räumt
    ``/usr/local`` ab — mit allem, was sonst darin liegt.

    Geprüft wird die Rechnung selbst, nicht ihr Wortlaut: Der Abschnitt wird
    aus dem erzeugten Skript geschnitten und mit ``sh`` gefahren.
    """
    from tools import make_linux_packages as tool

    script = tool.install_script()
    found = re.search(r"\ncase \"\$TARGET\" in\n  \*/\"\$SHORT\"\).*?\nesac\n", script, re.DOTALL)
    assert found is not None, (
        "Das Skript normalisiert das Ziel nicht mehr auf ein eigenes Verzeichnis. "
        "Ohne diesen Abschnitt trifft das rm -rf darunter, was der Nutzer angibt."
    )

    shared = tmp_path / "usr-local"
    (shared / "bin").mkdir(parents=True)
    (shared / "bin" / "andere-anwendung").write_text("wichtig", encoding="utf-8")

    sh = shutil.which("sh")
    assert sh is not None, "ohne sh lässt sich ein sh-Skript nicht prüfen"
    done = subprocess.run(
        [
            sh,
            "-c",
            f'SHORT=solidon3d\nTARGET="{shared.as_posix()}"\n{found.group(0)}\nprintf %s "$TARGET"',
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout == f"{shared.as_posix()}/solidon3d", (
        f"„{done.stdout}“ ist das Verzeichnis des Nutzers, nicht das der Anwendung — "
        "und genau das würde gelöscht."
    )
    assert (shared / "bin" / "andere-anwendung").is_file()


def test_the_linux_installer_keeps_its_own_directory_as_it_is() -> None:
    """Die Vorgaben enden schon auf den eigenen Namen und dürfen ihn nicht
    doppelt bekommen.

    Sonst läge die Anwendung nach dem Fix in ``/opt/solidon3d/solidon3d``, und
    die Deinstallation räumte an der falschen Stelle.
    """
    from tools import make_linux_packages as tool

    script = tool.install_script()
    found = re.search(r"\ncase \"\$TARGET\" in\n  \*/\"\$SHORT\"\).*?\nesac\n", script, re.DOTALL)
    assert found is not None

    sh = shutil.which("sh")
    assert sh is not None
    done = subprocess.run(
        [
            sh,
            "-c",
            f'SHORT=solidon3d\nTARGET=/opt/solidon3d\n{found.group(0)}\nprintf %s "$TARGET"',
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert done.stdout == "/opt/solidon3d", f"aus der Vorgabe wurde {done.stdout}"
