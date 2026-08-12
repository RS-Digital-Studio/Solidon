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
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from app.branding import APP_NAME

ROOT: Final = Path(__file__).resolve().parent.parent
SPEC: Final = ROOT / "packaging" / "solidon3d.spec"
INSTALLER_SCRIPT: Final = ROOT / "packaging" / "solidon3d.iss"
WORKFLOW: Final = ROOT / ".github" / "workflows" / "build.yml"

#: Was beim Suchen nach Datenverzeichnissen nicht zählt.
IGNORED: Final = ("__pycache__", ".pyc", ".pyo")


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
        assert any(f'"{parent.as_posix()}"' in spec for parent in covered if parent != Path(".")), (
            f"{directory.as_posix()} liegt im Paket nicht bei — Eintrag in packaging/"
            f"solidon3d.spec unter datas fehlt"
        )


def test_the_spec_names_the_application_from_branding() -> None:
    """Kein zweiter Ort für den Namen. Der erste hat schon eine Umbenennung
    verschlafen."""
    spec = SPEC.read_text(encoding="utf-8")
    assert "from app.branding import APP_NAME" in spec
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
