"""Sonde für den Wegwerfzweig ``diagnose/druckerliste``: erst der Slicer, dann
seine Drucker — unter Linux und macOS mit dem echten Anycubic Slicer Next.

Geprüft wird, was ein Kunde mit Kobra S1 und S1 Max erlebt: Solidon findet das
Programm und nennt es wie auf der Packung, liest seine Drucker, und Erststart,
Einstellungen und Druckdialog bieten dieselben Anycubic-Drucker an. Im
Druckdialog bietet der Knopf den Drucker an, auf den der Slicer eingestellt
ist; eine Wahl speichert den Drucker, und ein Würfel lässt sich mit ihm slicen.

Aufruf: ``python probe_druckerliste.py <stufe>`` — Ergebnis nach
``$PROBE_OUT/<stufe>.json``, Exit 1, sobald eine Prüfung scheitert.
Solidons eigene Ordner liegen im Temp, der Slicer liest seine echten.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import traceback
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HOME = Path(tempfile.mkdtemp(prefix="sonde-druckerliste-"))

from app.core import paths  # noqa: E402

paths.user_config_dir = lambda: HOME / "config"  # type: ignore[assignment]
paths.user_data_dir = lambda: HOME / "data"  # type: ignore[assignment]
paths.user_cache_dir = lambda: HOME / "cache"  # type: ignore[assignment]

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

import app.ui  # noqa: E402,F401 — Qt-Typen vor dem ersten Fenster
from app.core import discover, tools  # noqa: E402
from app.core.export import handover  # noqa: E402
from app.core.export import slicer_profiles as sp  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.ui.first_run import FirstRunDialog, select_program  # noqa: E402
from app.ui.labels import printer_title, slicer_title  # noqa: E402
from app.ui.print_settings_dialog import PrintSettingsDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402
from app.ui.settings_dialog import SettingsDialog  # noqa: E402

OUT = Path(os.environ.get("PROBE_OUT", "probe-out"))
WAIT = 180_000
S1 = "Anycubic Kobra S1"
S1_MAX = "Anycubic Kobra S1 Max"
checks: list[dict[str, object]] = []
record: dict[str, object] = {
    "platform": platform.platform(),
    "machine": platform.machine(),
    "solidon_home": str(HOME),
}


def check(name: str, ok: bool, detail: object = "") -> bool:
    checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:1500]})
    print(f"{'OK  ' if ok else 'FEHL'} {name}: {str(detail)[:300]}", flush=True)
    return bool(ok)


def anycubic_rows(box: QComboBox) -> list[str]:
    return sorted(
        box.itemText(row) for row in range(box.count()) if "anycubic" in box.itemText(row).lower()
    )


def row_of(box: QComboBox, text: str) -> int:
    return next((row for row in range(box.count()) if box.itemText(row) == text), -1)


def settle(qt: QApplication) -> None:
    for _round in range(6):
        qt.processEvents()
        time.sleep(0.05)


def licence() -> None:
    """Wie ``tests.helpers.set_test_license`` — gemessen wird der Slicer, nicht die Lizenz."""
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


def seed_active_machine(exe: Path, machine: str) -> Path:
    """Was der Slicer nach seiner Einrichtung hinterlässt: die zuletzt gewählte Maschine."""
    base = Path(sp.config_home(sys.platform) or str(Path.home() / ".config"))
    config = base / "AnycubicSlicerNext"
    conf = config / "AnycubicSlicerNext.conf"
    if conf.exists():
        raise SystemExit(f"{conf} gibt es schon — die Sonde überschreibt keine echte Einrichtung")
    # Gelesen wird über die Nutzerordner ``user/<Konto>`` (``sp.user_roots``).
    (config / "user" / "default").mkdir(parents=True, exist_ok=True)
    conf.write_text(
        json.dumps({"presets": {"machine": machine}}) + "\n# MD5 checksum 0\n", encoding="utf-8"
    )
    return conf


def slice_cube(exe: Path, printer: object) -> dict[str, object]:
    import trimesh

    setup = replace(handover.detect(exe), machine_profile=printer.title)  # type: ignore[attr-defined]
    profile = replace(profiles.make_profile(printer.id, "pla"), printer=printer)  # type: ignore[attr-defined]
    settings = print_settings.resolve(profile)
    work = Path(tempfile.mkdtemp(prefix="wuerfel-"))
    cube = trimesh.creation.box((20.0, 20.0, 20.0))
    cube.apply_translation((0.0, 0.0, 10.0))
    model = work / "wuerfel.stl"
    cube.export(model)
    outcome = handover.slice_model(
        model, settings, profile, setup, output_dir=work / "aus", timeout=900
    )
    return {
        "gcode": outcome.gcode_path.name,
        "bytes": outcome.gcode_path.stat().st_size,
        "seconds": round(outcome.seconds, 1),
        "findings": sorted({entry.code for entry in outcome.findings}),
    }


def probe(stage: str) -> int:
    qt = QApplication.instance() or QApplication([])
    discover.forget_cache()
    slicers = discover.find_programs("slicer", tools.SLICERS)
    record["slicers"] = [str(path) for path in slicers]
    anycubic = [path for path in slicers if "anycubic" in str(path).lower()]
    if not check("Solidon findet Anycubic Slicer Next", bool(anycubic), record["slicers"]):
        return finish(stage)
    exe = anycubic[0]
    record["exe"] = str(exe)
    check(
        "Name wie auf der Packung", slicer_title(exe) == "Anycubic Slicer Next", slicer_title(exe)
    )
    flavour = handover.detect(exe).flavour
    check("Familie Orca", flavour == "orca", flavour)
    root = sp.install_root(exe)
    check("Herstellerbestand gefunden", root is not None, root)
    found = sp.discover_printers(exe, flavour)
    models = sorted({printer_title(entry) for entry in found})
    record["profiles"] = len(found)
    record["models"] = models
    check("Drucker gelesen", len(found) >= 30, f"{len(found)} Profile, {len(models)} Modelle")
    check("Kobra S1 und S1 Max darunter", {S1, S1_MAX} <= set(models), models)

    conf = seed_active_machine(exe, "Anycubic Kobra S1 Max 0.4 nozzle")
    check(
        "Slicer auf S1 Max eingestellt",
        sp.chosen_machine(flavour, exe) == "Anycubic Kobra S1 Max 0.4 nozzle",
        conf,
    )

    first = FirstRunDialog(UiSettings())
    try:
        first.wait_for_survey(WAIT)
        check("Erststart bietet den Slicer an", select_program(first.slicer, str(exe)), exe)
        first.wait_for_survey(WAIT)
        settle(qt)
        first_rows = anycubic_rows(first.printer)
        record["first_run"] = first_rows
        check("Erststart: Anycubic-Drucker", {S1, S1_MAX} <= set(first_rows), first_rows)
        check(
            "Erststart schlägt S1 Max vor",
            first.printer.currentText() == S1_MAX,
            first.printer.currentText(),
        )
    finally:
        first.release()

    discover.remember_path("slicer", str(exe))
    settings_dialog = SettingsDialog(UiSettings())
    try:
        settings_dialog.wait_for_survey(WAIT)
        settle(qt)
        settings_rows = anycubic_rows(settings_dialog.printer)
        record["settings"] = settings_rows
        check("Einstellungen: dieselben Drucker", settings_rows == first_rows, settings_rows)
    finally:
        settings_dialog.release()

    session = Session()
    ui_settings = UiSettings()
    dialog = PrintSettingsDialog(session, ui_settings)
    try:
        check("Druckdialog: Slicersuche", dialog.wait_for_slicers(WAIT))
        check("Druckdialog: Drucker des Slicers", dialog.wait_for_printer_survey(WAIT))
        dialog._leash.wait_all(WAIT)
        settle(qt)
        print_rows = anycubic_rows(dialog.printer_choice)
        record["print_dialog"] = print_rows
        record["print_dialog_all"] = [
            dialog.printer_choice.itemText(row) for row in range(dialog.printer_choice.count())
        ]
        check("Druckdialog: dieselben Drucker", print_rows == first_rows, print_rows)
        check(
            "Druckdialog: Slicer heißt wie auf der Packung",
            dialog.slicer_choice.currentText() == "Anycubic Slicer Next",
            dialog.slicer_choice.currentText(),
        )
        offered = not dialog.adopt_printer.isHidden()
        check(
            "Druckdialog bietet den Drucker des Slicers an",
            offered and dialog.adopt_printer.text() == f"{S1_MAX} übernehmen",
            (offered, dialog.adopt_printer.text(), dialog.profile_note.text()),
        )
        if offered:
            dialog.adopt_printer.click()
            settle(qt)
            check(
                "Übernehmen stellt das Projekt auf S1 Max",
                printer_title(session.profile.printer) == S1_MAX,
                session.profile.printer.title,
            )
        row = row_of(dialog.printer_choice, S1)
        if check("Kobra S1 steht zur Wahl", row >= 0, print_rows):
            dialog.printer_choice.setCurrentIndex(row)
            dialog.printer_choice.activated.emit(row)
            settle(qt)
            chosen = session.profile.printer
            check("Wahl stellt das Projekt auf S1", printer_title(chosen) == S1, chosen.title)
            check(
                "Wahl speichert den Drucker",
                chosen.id in profiles.user_printer_profiles(),
                chosen.id,
            )
            check(
                "Wahl wird Vorgabe neuer Projekte",
                ui_settings.printer == chosen.id,
                ui_settings.printer,
            )
            dialog._leash.wait_all(WAIT)
            settle(qt)
            check(
                "Maschinenprofil passt zum S1",
                dialog.machine_choice.currentText().startswith("Anycubic Kobra S1 0.4"),
                dialog.machine_choice.currentText(),
            )
            licence()
            try:
                sliced = slice_cube(exe, chosen)
                record["slice"] = sliced
                check("Würfel mit Kobra S1 geslicet", int(sliced["bytes"]) > 1000, sliced)
            except Exception as problem:
                record["slice_error"] = traceback.format_exc()[-3000:]
                check("Würfel mit Kobra S1 geslicet", False, f"{type(problem).__name__}: {problem}")
    finally:
        session.wait_for_idle()
        dialog.release()
    return finish(stage)


def finish(stage: str) -> int:
    record["checks"] = checks
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{stage}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = [entry["check"] for entry in checks if not entry["ok"]]
    print(f"== {stage}: {len(checks) - len(failed)} von {len(checks)} Prüfungen bestanden")
    for name in failed:
        print(f"   gescheitert: {name}")
    return 1 if failed or not checks else 0


if __name__ == "__main__":
    try:
        code = probe(sys.argv[1])
    except Exception:
        record["error"] = traceback.format_exc()[-4000:]
        print(record["error"])
        check("Sonde lief durch", False, record["error"])
        code = finish(sys.argv[1])
    sys.exit(code)
