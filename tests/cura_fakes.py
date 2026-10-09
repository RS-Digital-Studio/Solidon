"""Nachgebaute Cura-Installationen für Kern- und Fenstertests (RM-521).

Eine Installation nach Cura 5.13 (``share/cura/resources/definitions`` und
``extruders``) mit ``fdmprinter``, einem K1 Max und seinem Extruderzug; dazu
Curas AppDir, wie Flathub und das AppImage es tragen, ein Flatpak-Starter und
ein AppImage: ein echtes Abbild dieses AppDir (``tests.squashfs_fakes``), aus
dem Solidon die Drucker liest, und ein Skript, das für den Lauf das Einhängen
nachstellt.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.core import discover
from app.core.export import cura_linux
from tests.squashfs_fakes import appimage_file, tree_of

#: Der Startcode des K1 Max in Cura 5.13 (``creality_k1max.def.json``), wörtlich.
K1_MAX_START = (
    "M140 S0\nM104 S0 \nSTART_PRINT EXTRUDER_TEMP={material_print_temperature_layer_0} "
    "BED_TEMP={material_bed_temperature_layer_0}\n"
)


def cura_installation(tmp_path: Path, start: str = K1_MAX_START, end: str = "END_PRINT") -> Path:
    """Eine Cura-Installation mit ``fdmprinter``, einem K1 Max und seinem Extruderzug."""
    install = tmp_path / "UltiMaker Cura 5.13.0"
    resources = install / "share" / "cura" / "resources"
    definitions = resources / "definitions"
    extruders = resources / "extruders"
    definitions.mkdir(parents=True)
    extruders.mkdir(parents=True)
    machine = {
        "machine_start_gcode": {
            "default_value": "G28 ;Home\nG1 Z15.0 F6000 ;Move the platform down 15mm"
        },
        "machine_end_gcode": {"default_value": "M104 S0\nM84"},
        "machine_depth": {"default_value": 100},
        "machine_name": {"default_value": "Unknown"},
        "gantry_height": {"default_value": 99999, "value": "machine_height"},
    }
    (definitions / "fdmprinter.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "FFF",
                "metadata": {
                    "setting_version": 27,
                    "machine_extruder_trains": {"0": "fdmextruder"},
                },
                "settings": {"machine_settings": {"children": machine}},
            }
        ),
        encoding="utf-8",
    )
    (definitions / "fdmextruder.def.json").write_text(
        json.dumps({"version": 2, "name": "Extruder", "settings": {}}), encoding="utf-8"
    )
    (definitions / "creality_k1max.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Creality K1 Max",
                "inherits": "fdmprinter",
                "metadata": {"machine_extruder_trains": {"0": "creality_k1max_extruder_0"}},
                "overrides": {
                    "machine_start_gcode": {"default_value": start},
                    "machine_end_gcode": {"default_value": end},
                    "machine_name": {"default_value": "Creality K1 Max"},
                    "gantry_height": {"value": 45},
                },
            }
        ),
        encoding="utf-8",
    )
    (extruders / "creality_k1max_extruder_0.def.json").write_text(
        json.dumps({"version": 2, "name": "Extruder 1", "inherits": "fdmextruder"}),
        encoding="utf-8",
    )
    engine = install / "CuraEngine.exe"
    engine.write_bytes(b"")
    return engine


#: ``AppRun.env`` der Cura 5.13 aus Flathub und AppImage, gemessen am Runner
#: (Lauf 37504088443); gekürzt auf die Zeilen, die der Lader braucht, und eine
#: daneben.
APPRUN_ENV = (
    "APPDIR=$ORIGIN\n"
    "APPDIR_EXEC_PATH=$APPDIR/UltiMaker-Cura\n"
    "APPDIR_LIBRARY_PATH=$APPDIR:$APPDIR/runtime/compat/:$APPDIR/usr/lib/x86_64-linux-gnu:"
    "$APPDIR/lib/x86_64-linux-gnu:$APPDIR/usr/lib\n"
    "XDG_DATA_DIRS=$APPDIR/usr/local/share:$APPDIR/usr/share:$XDG_DATA_DIRS\n"
    "APPDIR_LIBC_LIBRARY_PATH=$APPDIR/runtime/compat:$APPDIR/runtime/compat/lib/x86_64-linux-gnu:"
    "$APPDIR/runtime/compat/lib64:$APPDIR/runtime/compat/usr/lib/x86_64-linux-gnu\n"
    "APPDIR_LIBC_VERSION=2.35\n"
    "APPDIR_LIBC_LINKER_PATH={'lib64/ld-linux-x86-64.so.2'}\n"
)

#: Der Bibliothekspfad daraus für ``/app/cura``: erst Curas glibc, dann der Rest,
#: ``runtime/compat`` nur einmal.
FLATPAK_LIBRARIES = (
    "/app/cura/runtime/compat:/app/cura/runtime/compat/lib/x86_64-linux-gnu:"
    "/app/cura/runtime/compat/lib64:/app/cura/runtime/compat/usr/lib/x86_64-linux-gnu:"
    "/app/cura:/app/cura/usr/lib/x86_64-linux-gnu:/app/cura/lib/x86_64-linux-gnu:"
    "/app/cura/usr/lib"
)

#: Ein Einhängen wie ``--appimage-mount``: nach ``argv[2]`` Sekunden den Punkt
#: ``argv[1]`` nennen, dann warten. Ohne Punkt schweigt es.
MOUNT_SCRIPT = (
    "import sys, time\n"
    "if len(sys.argv) > 2:\n"
    "    time.sleep(float(sys.argv[2]))\n"
    "if len(sys.argv) > 1:\n"
    "    print(sys.argv[1], flush=True)\n"
    "time.sleep(120)\n"
)

#: Ein Einhängen, das scheitert, wie ohne FUSE: ein Satz auf stderr, Rückgabewert 127.
FAILING_MOUNT = "import sys\nsys.stderr.write('fuse: device not found\\n')\nsys.exit(127)\n"


def cura_appdir(
    folder: Path, tmp_path: Path, *, environment: bool = True, loader: bool = True
) -> Path:
    """Curas AppDir, wie Flathub es unter ``/app/cura`` und das AppImage im Abbild trägt."""
    template = cura_installation(tmp_path / "vorlage" / folder.name)
    shutil.copytree(template.parent / "share", folder / "share")
    (folder / "CuraEngine").write_bytes(b"")
    if environment:
        (folder / "AppRun.env").write_text(APPRUN_ENV, encoding="utf-8")
    if loader:
        found = folder / "runtime" / "compat" / "lib64" / "ld-linux-x86-64.so.2"
        found.parent.mkdir(parents=True)
        found.write_bytes(b"")
    return folder


def flatpak_cura(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    folder: str = "cura",
    installation: bool = True,
    **parts: bool,
) -> Path:
    """Cura aus Flathub: Starter in den Exporten, das AppDir unter ``files/<folder>``.

    Ohne ``installation`` sieht Solidon den Starter, aber nicht das Paket — wie aus
    dem eigenen Flatpak, dem die Freigabe fehlt."""
    system = tmp_path / "flatpak"
    launcher = system / "exports" / "bin" / "com.ultimaker.cura"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("")
    if installation:
        files = system / "app" / "com.ultimaker.cura" / "current" / "active" / "files"
        cura_appdir(files / folder, tmp_path, **parts)
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(launcher.parent),))
    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(system),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    return launcher


def appimage_cura(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mounts: list[Path],
    *,
    name: str = "UltiMaker-Cura-5.13.0-linux-X64.AppImage",
    delay: float = 0.0,
    copies: list[Path] | None = None,
    **parts: bool,
) -> tuple[Path, Path]:
    """Ein Cura-AppImage: Abbild des AppDir, gzip wie Cura 5.13.

    Für einen Lauf stellt ein Skript das Einhängen nach, ``mounts`` zählt mit;
    jedes Lesen der Drucker aus dem Abbild zählt ``copies``. ``delay`` hält
    beides auf, wie ein langsamer Datenträger."""
    appimage = tmp_path / "Applications" / name
    point = cura_appdir(tmp_path / "tmp" / f".mount_{appimage.stem[:10]}", tmp_path, **parts)
    appimage_file(appimage, tree_of(point), compression="gzip")
    script = tmp_path / "einhaengen.py"
    script.write_text(MOUNT_SCRIPT, encoding="utf-8")

    def command(image: Path) -> list[str]:
        mounts.append(image)
        return [sys.executable, str(script), str(point), str(delay)]

    reading = getattr(cura_linux._read_resources, "__wrapped__", cura_linux._read_resources)

    def read(image: Path, target: Path) -> bool | None:
        if copies is not None:
            copies.append(image)
        time.sleep(delay)
        return reading(image, target)

    read.__wrapped__ = reading  # type: ignore[attr-defined]
    monkeypatch.setattr(cura_linux, "mount_command", command)
    monkeypatch.setattr(cura_linux, "_read_resources", read)
    return appimage, point


def failing_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mounts: list[Path]) -> None:
    script = tmp_path / "scheitern.py"
    script.write_text(FAILING_MOUNT, encoding="utf-8")

    def command(image: Path) -> list[str]:
        mounts.append(image)
        return [sys.executable, str(script)]

    monkeypatch.setattr(cura_linux, "mount_command", command)


def ended_mounts(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[bytes]]:
    """Jeder Einhängeprozess, den ``cura_linux`` beendet hat."""
    ended: list[subprocess.Popen[bytes]] = []
    original = cura_linux.terminate_process_tree

    def terminate(process: subprocess.Popen[bytes], **kwargs: float) -> None:
        original(process, **kwargs)
        ended.append(process)

    monkeypatch.setattr(cura_linux, "terminate_process_tree", terminate)
    return ended
