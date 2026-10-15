r"""Baut das Prüfmodul für die Auslieferung (Konzept §2 I H4/H5, V4c).

Zwei Dinge entstehen, beide unter ``packaging/build/``:

``activation/``
    Die Module aus ``app/core/activation`` als kompilierte Erweiterungen
    (``.pyd``/``.so``). Im Paket liegt damit kein Bytecode des Prüfmoduls,
    den man dekompiliert und um ein ``return True`` ergänzt — der Angriff
    wird Binär-Reversing (H5).

``licence.manifest``
    Das signierte Manifest über die vier Grenzdateien aus §2 C (H4). Die
    Prüfung dagegen steckt in ``integrity.py`` — und damit im eben
    kompilierten Maschinencode.

Das Paar, das das Manifest signiert, ist **je Bau frisch**: der öffentliche
Teil wird vor dem Übersetzen in die Kopie von ``integrity.py`` gesetzt, der
private nach dem Signieren verworfen. Er ist nicht der Lizenzschlüssel aus
§8 — der verlässt den Passwortmanager nie und wird beim Bauen nicht
gebraucht. Ein Angreifer, der das Manifest neu schreiben will, muss darum
zuerst den öffentlichen Schlüssel im kompilierten Modul austauschen.

Aufruf, vor ``pyinstaller packaging/solidon3d.spec``:

    python tools/build_licence_module.py

Braucht Cython und einen C-Compiler — beides Bau-, keine
Laufzeitabhängigkeit. Die Entwicklung und die Suite laufen weiter gegen die
Python-Quellen; dieses Werkzeug fasst ``app/`` nie an, es arbeitet auf einer
Kopie.

Findet setuptools den Compiler nicht, obwohl er installiert ist („Microsoft
Visual C++ 14.0 or greater is required" bei vorhandenem Visual Studio 18):
dessen ``vswhere`` kennt die Installation nicht. Dann die Umgebung von Hand
aktivieren und darin bauen::

    call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
    set DISTUTILS_USE_SDK=1
    set MSSdk=1
    .venv\Scripts\python.exe tools\build_licence_module.py
"""

from __future__ import annotations

import secrets
import shutil
import sys
import sysconfig
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import integrity
from tools.make_licence_keys import public_key, sign

ROOT = Path(__file__).resolve().parent.parent

#: Wohin gebaut wird — die Spec liest von hier.
BUILD_DIR = ROOT / "packaging" / "build"

#: Die Zeile in integrity.py, an deren Stelle der Bau-Schlüssel tritt. Wird
#: sie beim Ersetzen nicht gefunden, ist die Quelle umgebaut worden und der
#: Bau bricht ab — ein Manifest, das niemand prüft, wäre schlimmer als keins.
PLACEHOLDER = "MANIFEST_PUBLIC_KEY: bytes | None = None"

#: Das Paket, das kompiliert statt als Bytecode reist (H5).
PACKAGE = "app.core.activation"


def nested_modules(source_dir: Path) -> list[Path]:
    """Die Module des Prüfpakets, die nicht direkt im Paketordner liegen.

    Gelesen wird rekursiv, damit ein Unterordner auffällt, statt still
    übergangen zu werden: Ein vergessenes Modul bliebe Bytecode oder fehlte im
    Paket (W4).
    """
    return [path for path in sorted(source_dir.rglob("*.py")) if path.parent != source_dir]


def stage_sources(staging: Path, manifest_public: bytes, source_dir: Path | None = None) -> None:
    """Kopiert die Prüfmodul-Quellen und setzt den Bau-Schlüssel ein.

    Das Paket reist flach: Die Spec legt jede gebaute Erweiterung direkt nach
    ``app/core/activation``. Ein Modul in einem Unterordner hält den Bau an,
    statt an falscher Stelle oder gar nicht anzukommen.

    ``source_dir`` ist nur für die Suite da — der Bau liest immer aus dem
    Repository.
    """
    if source_dir is None:
        source_dir = ROOT / "app" / "core" / "activation"
    nested = nested_modules(source_dir)
    if nested:
        names = ", ".join(path.relative_to(source_dir).as_posix() for path in nested)
        raise SystemExit(
            f"Das Prüfmodul hat Module in Unterordnern ({names}), die Spec legt aber jede "
            "Erweiterung direkt nach app/core/activation. Die Module in den Paketordner "
            "ziehen oder Bau und Spec zusammen um Unterordner erweitern."
        )
    staging.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.rglob("*.py")):
        shutil.copy2(source, staging / source.name)

    integrity_copy = staging / "integrity.py"
    text = integrity_copy.read_text(encoding="utf-8")
    if PLACEHOLDER not in text:
        raise SystemExit(
            f"{PLACEHOLDER!r} steht nicht mehr in integrity.py — "
            "ohne die Stelle bliebe das Manifest ungeprüft."
        )
    replacement = (
        'MANIFEST_PUBLIC_KEY: bytes | None = bytes.fromhex("' + manifest_public.hex() + '")'
    )
    integrity_copy.write_text(text.replace(PLACEHOLDER, replacement), encoding="utf-8")


def extension_modules(staging: Path) -> list[tuple[str, Path]]:
    """Je Quelle im Bauordner der volle Modulname, unter dem sie übersetzt wird.

    Der Name ist der **volle** (``app.core.activation.key``): er steckt im
    Init-Symbol der gebauten Datei, und ein falscher lädt nicht. Das Paket
    selbst heißt nach seinem Paketnamen — CPython sucht das Symbol nach dem
    Modulnamen, nicht nach dem Dateinamen.
    """
    modules: list[tuple[str, Path]] = []
    for source in sorted(staging.rglob("*.py")):
        parts = source.relative_to(staging).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules.append((".".join((PACKAGE, *parts)), source))
    return modules


def compile_extensions(staging: Path, target: Path) -> list[Path]:
    """Übersetzt die Kopien nach C und baut sie zu Erweiterungen.

    Die Namen kommen aus :func:`extension_modules`; das Paket selbst wird als
    ``__init__`` abgelegt.
    """
    from Cython.Build import cythonize
    from setuptools import Extension
    from setuptools.dist import Distribution

    extensions = [Extension(name, [str(source)]) for name, source in extension_modules(staging)]

    with tempfile.TemporaryDirectory(prefix="solidon-licence-build-") as scratch:
        distribution = Distribution(
            {
                "ext_modules": cythonize(
                    extensions,
                    language_level=3,
                    build_dir=str(Path(scratch) / "c"),
                    quiet=True,
                )
            }
        )
        command = distribution.get_command_obj("build_ext")
        command.build_lib = str(Path(scratch) / "lib")
        command.build_temp = str(Path(scratch) / "tmp")
        command.ensure_finalized()
        command.run()

        suffix = sysconfig.get_config_var("EXT_SUFFIX")
        built_dir = Path(command.build_lib) / "app" / "core"
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob("*"):
            stale.unlink()
        written: list[Path] = []
        for built in sorted(built_dir.rglob(f"*{suffix}")):
            # ``app.core.activation`` selbst kommt als ``activation<suffix>``
            # heraus und muss als ``__init__`` ins Paketverzeichnis.
            wanted = "__init__" if built.parent.name == "core" else built.name.split(".")[0]
            destination = target / f"{wanted}{suffix}"
            shutil.copy2(built, destination)
            written.append(destination)
    return written


def write_manifest(destination: Path, seed: bytes) -> None:
    """Hasht die vier Grenzdateien und legt das signierte Manifest ab.

    Gehasht werden die Quellen im Repository — dieselben Dateien, die die
    Spec als Quelltext ins Paket legt (``module_collection_mode``). Nutzlast
    und Ablageform kommen aus :mod:`integrity`, damit Bau und Prüfung nie
    auseinanderlaufen können.
    """
    import json

    files = integrity.boundary_hashes()
    missing = [name for name, digest in files.items() if not digest]
    if missing:
        raise SystemExit(f"Grenzdateien nicht lesbar: {missing}")
    manifest = {
        "files": files,
        "signature": sign(seed, integrity.manifest_payload(files)).hex(),
    }
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    seed = secrets.token_bytes(32)
    manifest_public = public_key(seed)

    with tempfile.TemporaryDirectory(prefix="solidon-licence-staging-") as raw:
        staging = Path(raw) / "activation"
        stage_sources(staging, manifest_public)
        written = compile_extensions(staging, BUILD_DIR / "activation")

    write_manifest(BUILD_DIR / "licence.manifest", seed)
    # ``seed`` verlässt die Funktion nicht: kein Ablegen, kein Ausgeben. Nach
    # dem Prozessende kann dieses Manifest niemand mehr neu signieren.

    for entry in written:
        print(f"gebaut: {entry.relative_to(ROOT)}")
    print(f"signiert: {(BUILD_DIR / 'licence.manifest').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
