r"""Übersetzt Ebenenschnitt und Konturverkettung (Bauplan §22.1, §31).

Aus ``app/core/slice/_chain.pyx`` entsteht daneben eine Erweiterung
(``.pyd``/``.so``). Liegt sie, nimmt ``analysis.py`` sie; liegt sie nicht,
laufen NumPy und GEOS weiter. **Das Ergebnis ist in beiden Fällen dasselbe** —
was sich ändert, ist die Zeit: gemessen an einer Kugel mit 327 680 Dreiecken
in 400 Schichten kostet die Verkettung 608 ms als Python-Schleife und 11 ms
übersetzt; der Ebenenschnitt fiel von 203 auf 27 bis 31 ms.

Aufruf:

    .venv\Scripts\python.exe tools/build_slice_core.py

Braucht Cython und einen C-Compiler — beides Bau-, keine Laufzeitabhängigkeit,
genau wie bei ``tools/build_licence_module.py``. Die Erweiterung ist nicht
eingecheckt: sie gehört zur Maschine, auf der sie gebaut wurde.

Wieder wegräumen: ``--clean``. Danach läuft die Suite über den GEOS-Weg, und
genau so prüft ``tests/test_slice_core.py`` beide gegeneinander.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Wo die Quelle liegt und wo die Erweiterung hingehört.
PACKAGE = ROOT / "app" / "core" / "slice"
SOURCE = PACKAGE / "_chain.pyx"

#: Eigener Zwischenordner. ``ROOT / "build"`` gehört auch PyInstaller; ein
#: ``--clean`` dieses Werkzeugs darf kein fast fertiges Kundenpaket löschen.
BUILD_TEMP = ROOT / "build" / "slice-core"


def built() -> list[Path]:
    """Was von einem früheren Lauf herumliegt."""
    return [
        path
        for pattern in ("_chain.*.so", "_chain.*.pyd", "_chain.c")
        for path in PACKAGE.glob(pattern)
    ]


def clean() -> None:
    for path in built():
        path.unlink()
        print(f"weg: {path.relative_to(ROOT)}")
    for leftover in (PACKAGE / "build", BUILD_TEMP):
        if leftover.is_dir():
            shutil.rmtree(leftover)


def build() -> int:
    try:
        from Cython.Build import cythonize
        from setuptools import setup
    except ImportError:
        print(
            'Cython und setuptools fehlen. Beide stecken im Extra „dev":\n'
            '  python -m pip install -c constraints.txt -e ".[dev]"',
            file=sys.stderr,
        )
        return 1

    if not SOURCE.is_file():
        print(f"Quelle fehlt: {SOURCE}", file=sys.stderr)
        return 1

    # In-place bauen heißt: neben die Quelle, damit der Import sie findet.
    # ``setup`` will dafür im Paketverzeichnis stehen.
    setup(
        name="solidon3d-slice-core",
        ext_modules=cythonize(str(SOURCE), quiet=True, language_level="3"),
        script_args=[
            "build_ext",
            "--inplace",
            "--build-temp",
            str(BUILD_TEMP / "temp"),
            "--build-lib",
            str(BUILD_TEMP / "lib"),
        ],
    )

    made = [path for path in built() if path.suffix in (".so", ".pyd")]
    if not made:
        print("übersetzt, aber nichts gefunden — bitte die Ausgabe oben lesen", file=sys.stderr)
        return 1
    for path in made:
        print(f"gebaut: {path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="Gebautes wieder entfernen")
    arguments = parser.parse_args()
    if arguments.clean:
        clean()
        return 0
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
