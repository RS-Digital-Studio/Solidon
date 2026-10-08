"""Sonde für den Wegwerfzweig: Findet Solidon die installierten Slicer, ihre
Herstellerdrucker und die eigenen Drucker des Nutzers — und slict es mit ihnen?

Aufrufe:
    python probe_slicers.py seed               eigene Drucker anlegen (Orca-Familie)
    python probe_slicers.py <stufe> [--slice]  messen, Ergebnis nach $PROBE_OUT/<stufe>.json

``seed`` legt je gefundener Installation der Orca-Familie an, was der Slicer
selbst nach der Einrichtung hinterlässt: ein eigenes Druckerprofil, das von
einer Herstellermaschine erbt und die Druckhöhe ändert, die Konfiguration mit
diesem Drucker als zuletzt gewähltem und die Kopie des Herstellerbündels
unter ``system/``. Den Bestand eines AppImage liest es aus dem ausgepackten
Abbild, so wie der Slicer ihn beim ersten Start kopiert.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import replace
from pathlib import Path

import app
from app.core import discover, tools
from app.core.export import handover, slicer_keys
from app.core.export import slicer_profiles as sp

OUT = Path(os.environ.get("PROBE_OUT", "probe-out"))
OWN_HEIGHT = "123"
CONFIG_NAMES = {
    "orcaslicer": "OrcaSlicer",
    "bambustudio": "BambuStudio",
    "elegooslicer": "ElegooSlicer",
    "crealityprint": "Creality",
}
PREFERRED = ("Ender-3 V3", "Ender-3", "K1", "MK4", "Centauri", "0.4")


def kind_of(exe: Path) -> str:
    app_id = discover.flatpak_app(exe) if hasattr(discover, "flatpak_app") else ""
    if app_id or "flatpak" in exe.as_posix():
        return "Flatpak"
    if exe.suffix.lower() == ".appimage":
        return "AppImage"
    return "App"


def own_name(exe: Path) -> str:
    return f"Mein Drucker {kind_of(exe)}"


def found_slicers() -> tuple[Path, ...]:
    discover.forget_cache()
    return discover.find_programs("slicer", tools.SLICERS)


def vendor_root(exe: Path) -> Path | None:
    """Der Herstellerbestand — für ein AppImage aus dem ausgepackten Abbild."""
    root = sp.install_root(exe)
    if root is not None or exe.suffix.lower() != ".appimage":
        return root
    target = Path(tempfile.mkdtemp(prefix="extract-", dir=Path.home()))
    try:
        subprocess.run(
            [str(exe), "--appimage-extract"], cwd=target, capture_output=True, timeout=600, check=True
        )
    except (OSError, subprocess.SubprocessError) as problem:
        print(f"seed: {exe.name} lässt sich nicht auspacken: {problem}")
        return None
    for candidate in sorted((target / "squashfs-root").rglob("profiles")):
        if candidate.is_dir() and any(candidate.glob("*.json")):
            return candidate
    return None


def seed() -> None:
    for exe in found_slicers():
        flavour = slicer_keys.flavour_of(exe.name)
        mark = discover.program_mark(exe.name)
        name = CONFIG_NAMES.get(mark)
        if flavour != "orca" or name is None:
            print(f"seed: übersprungen {exe} ({flavour}, {mark})")
            continue
        root = vendor_root(exe)
        if root is None:
            print(f"seed: kein Herstellerbestand für {exe}")
            continue
        machine = None
        for path in sorted(root.glob("*/machine/**/*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if str(document.get("instantiation", "")).lower() == "true" and "0.4" in str(
                document.get("name", "")
            ):
                machine = (path, document)
                break
        if machine is None:
            print(f"seed: keine Herstellermaschine unter {root}")
            continue
        path, document = machine
        vendor = path.relative_to(root).parts[0]
        app_id = discover.flatpak_app(exe)
        if app_id:
            base = Path.home() / ".var" / "app" / app_id / "config"
        else:
            base = Path(sp.config_home(sys.platform) or str(Path.home() / ".config"))
        if mark == "crealityprint":
            config = base / "Creality" / "Creality Print" / "7.2"
        else:
            config = base / name
        user = config / "user" / "default" / "machine"
        user.mkdir(parents=True, exist_ok=True)
        own = own_name(exe)
        (user / f"{own}.json").write_text(
            json.dumps(
                {
                    "from": "User",
                    "inherits": document["name"],
                    "name": own,
                    "printable_height": OWN_HEIGHT,
                    "version": "2.3.0.0",
                }
            ),
            encoding="utf-8",
        )
        (config / f"{name}.conf").write_text(
            json.dumps({"presets": {"machine": own}}) + "\n# MD5 checksum 0\n", encoding="utf-8"
        )
        system = config / "system"
        system.mkdir(exist_ok=True)
        if (root / f"{vendor}.json").is_file():
            shutil.copy2(root / f"{vendor}.json", system / f"{vendor}.json")
        shutil.copytree(root / vendor, system / vendor, dirs_exist_ok=True)
        print(f"seed: {exe} → {config} ({own} erbt von {document['name']})")


def licence() -> None:
    """Wie ``tests.helpers.set_test_license`` — die Sonde misst den Slicer, nicht die Lizenz."""
    from datetime import date

    from app.core import activation
    from app.core.activation import key

    activation._cached = activation.Activation(
        licence=key.Licence(
            major=key.current_major(),
            purchased_on=date(2026, 8, 6),
            order="A-1234",
            holder="kaeufer@beispiel.de",
        ),
        certificate=activation.ActivationCertificate(
            licence_digest="test-licence",
            device_public=b"\x01" * 32,
            device_name="Prüfrechner",
            activation_id="test-activation",
            issued_on=date(2026, 8, 28),
        ),
    )


def pick(printers, chosen: str):
    """Der Drucker, mit dem geslict wird: der zuletzt gewählte, sonst ein bekannter."""
    titles = {printer.title: printer for printer in printers}
    if chosen in titles:
        return titles[chosen]
    for word in PREFERRED:
        for printer in printers:
            if word in printer.title:
                return printer
    return printers[0] if printers else None


def slice_with(exe: Path, flavour: str, printer) -> dict[str, object]:
    import trimesh

    from app.core.knowledge import print_settings, profiles

    machine = "" if flavour == "cura" else printer.title
    setup = replace(handover.detect(exe), machine_profile=machine)
    profile = replace(profiles.make_profile("centauri-carbon-2", "pla"), printer=printer)
    settings = print_settings.resolve(profile)
    work = Path(tempfile.mkdtemp(prefix="probe-", dir=Path.home()))
    cube = trimesh.creation.box((20.0, 20.0, 20.0))
    cube.apply_translation((0.0, 0.0, 10.0))
    model = work / "wuerfel.stl"
    cube.export(model)
    started = time.monotonic()
    try:
        outcome = handover.slice_model(
            model, settings, profile, setup, output_dir=work / "aus", timeout=900
        )
    except Exception as problem:  # noqa: BLE001 — die Sonde berichtet alles
        return {
            "ok": False,
            "printer": printer.title,
            "error": f"{type(problem).__name__}: {problem}"[:800],
            "values": {k: str(v)[:3000] for k, v in getattr(problem, "values", {}).items()},
            "trace": traceback.format_exc()[-2500:],
            "seconds": round(time.monotonic() - started, 1),
        }
    return {
        "ok": True,
        "printer": printer.title,
        "gcode": outcome.gcode_path.name,
        "bytes": outcome.gcode_path.stat().st_size,
        "seconds": round(outcome.seconds, 1),
        "findings": sorted({entry.code for entry in outcome.findings}),
    }


def probe(stage: str, slicing: bool) -> None:
    if slicing:
        licence()
    records: list[dict[str, object]] = []
    for exe in found_slicers():
        flavour = slicer_keys.flavour_of(exe.name) or "other"
        record: dict[str, object] = {
            "exe": str(exe),
            "kind": kind_of(exe),
            "flavour": flavour,
            "flatpak": discover.flatpak_app(exe) if hasattr(discover, "flatpak_app") else "?",
        }
        try:
            root = sp.install_root(exe)
            record["install_root"] = str(root) if root else None
            record["user_roots"] = [str(entry) for entry in sp.user_roots(flavour, exe)]
            record["chosen_machine"] = sp.chosen_machine(flavour, exe)
            started = time.monotonic()
            found = sp.find_profiles(exe, flavour)
            record["profile_seconds"] = round(time.monotonic() - started, 1)
            machines = [entry for entry in found if entry.kind == "machine"]
            record["machines"] = len(machines)
            record["processes"] = sum(1 for entry in found if entry.kind == "process")
            record["machine_sample"] = [entry.name for entry in machines[:3]]
            own = own_name(exe)
            record["own_listed"] = any(entry.name == own for entry in machines)
            printers = sp.discover_printers(exe, flavour)
            record["printers"] = len(printers)
            mine = [printer for printer in printers if printer.title == own]
            record["own_printer_volume"] = list(mine[0].build_volume) if mine else None
            if slicing and flavour != "other":
                printer = pick(printers, str(record["chosen_machine"]))
                record["slice"] = (
                    slice_with(exe, flavour, printer)
                    if printer is not None
                    else {"ok": False, "error": "kein Drucker"}
                )
        except Exception:  # noqa: BLE001
            record["error"] = traceback.format_exc()[-2000:]
        records.append(record)
        print(json.dumps(record, ensure_ascii=False))
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "stage": stage,
        "code": str(Path(app.__file__).parent),
        "in_flatpak": discover.in_flatpak(),
        "platform": sys.platform,
        "records": records,
    }
    (OUT / f"{stage}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"== {stage}: {len(records)} Slicer, Code aus {summary['code']}, im Flatpak: {summary['in_flatpak']}")
    for record in records:
        sliced = record.get("slice") or {}
        print(
            f"  {record['kind']:8} {Path(str(record['exe'])).name[:40]:40} "
            f"root={'ja' if record.get('install_root') else 'NEIN'} "
            f"Maschinen={record.get('machines')} Prozesse={record.get('processes')} "
            f"gewählt={record.get('chosen_machine')!r} eigener={record.get('own_listed')} "
            f"Höhe={record.get('own_printer_volume')} "
            f"Slice={'ok ' + str(sliced.get('printer')) if sliced.get('ok') else sliced.get('error', '-')!s:.160}"
        )


if __name__ == "__main__":
    if sys.argv[1] == "seed":
        seed()
    else:
        probe(sys.argv[1], "--slice" in sys.argv)
