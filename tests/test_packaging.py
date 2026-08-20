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
