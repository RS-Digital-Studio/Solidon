"""Liest die Herstellerprofile der Slicer und schreibt je Druckfeld den kleinsten und größten Wert.

    python tools/scan_vendor_values.py                  # Standardorte unter Windows
    python tools/scan_vendor_values.py <wurzel> ...     # andere Profilordner

Ein Feld des Druckdialogs zeigt den Wert, den die Grundlage trägt — und die
Grundlage ist das Herstellerprofil des Slicers. Liegt ein solcher Wert außerhalb
der Grenzen des Felds, darf das Feld ihn nicht kürzen (FD-197, FD-203: der
Brückenfluss 180 % der Creality Hi stand als „150 %“, die 40 000 mm/s² des Sovol
Zero als „30000“). Welche Werte die Hersteller tragen, weiß nur ihr Bestand, und
den hat die Suite nicht: Dieses Werkzeug liest ihn einmal und schreibt das
Ergebnis nach ``tests/data/vendor_print_values.json``; der Wächter
``tests/test_vendor_field_values.py`` prüft die Feldgrenzen gegen die Datei, ohne
fremde Dateien zu öffnen.

Gelesen wird wie die Rücklesung der Grundlage (``export.manufacturer``): Prozess-
und Filamentprofile der Orca-Familie mit den Schlüsseln, die das jeweilige
Programm schreibt, der Rückzug aus der Maschine, dazu die Abschnitte der
PrusaSlicer-Bündel. Jede Datei zählt mit dem, was sie selbst setzt; die Erbkette
wird nicht aufgelöst, denn jeder geerbte Wert steht in einer anderen Datei des
Bestands. Ausgabe in Solidons Modelleinheit (Anteile als Anteil).
"""

from __future__ import annotations

import argparse
import configparser
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.export import manufacturer  # noqa: E402
from app.core.knowledge import print_fields  # noqa: E402

TARGET = ROOT / "tests" / "data" / "vendor_print_values.json"

#: Profilordner und Programmmarke (``discover.program_mark``) je Slicer.
ORCA_FAMILY: tuple[tuple[str, str], ...] = (
    (r"C:\Program Files\OrcaSlicer\resources\profiles", "orcaslicer"),
    (r"C:\Program Files\Creality\Creality Print 7.2\resources\profiles", "crealityprint"),
    (r"C:\Program Files\ElegooSlicer\resources\profiles", "elegooslicer"),
    (r"C:\Program Files\AnycubicSlicerNext\resources\profiles", "anycubicslicernext"),
    (r"C:\Program Files\Bambu Studio\resources\profiles", "bambustudio"),
)
PRUSA_BUNDLES = r"C:\Program Files\Prusa3D\PrusaSlicer\resources\profiles"

#: Kein Druckfeld, aber dieselbe Frage: Das Düsenfeld des Druckdialogs zeigt den
#: Durchmesser der Maschine (``_NOZZLE_RANGE_MM``).
NOZZLE = "printer.nozzle_diameter"


def _nozzles(raw: object) -> dict[str, object]:
    """Der größte Düsendurchmesser einer Maschine, aus Liste oder Prusas Kommaliste."""
    items = raw if isinstance(raw, list) else str(raw or "").split(",")
    sizes = []
    for item in items:
        try:
            sizes.append(float(str(item).strip().strip('"')))
        except ValueError:
            continue
    positive = [size for size in sizes if size > 0.0]
    return {NOZZLE: max(positive)} if positive else {}


class Extremes:
    """Kleinster und größter Wert je Pfad, mit der Datei, die ihn trägt."""

    def __init__(self) -> None:
        self.found: dict[str, dict[str, Any]] = {}
        self.files = 0
        self.values = 0

    def take(self, read: dict[str, object], source: str) -> None:
        for path, value in read.items():
            field = print_fields.field_of(path)
            if path != NOZZLE and (field is None or field.kind not in ("float", "int")):
                continue
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            number = float(value)
            self.values += 1
            entry = self.found.setdefault(
                path, {"min": number, "min_from": source, "max": number, "max_from": source}
            )
            if number < entry["min"]:
                entry["min"], entry["min_from"] = number, source
            if number > entry["max"]:
                entry["max"], entry["max_from"] = number, source


def _orca(root: Path, program: str, extremes: Extremes) -> None:
    context = manufacturer._Context(nozzle=0.4)
    for file in sorted(root.rglob("*.json")):
        kind = next((part for part in file.parts if part in ("process", "filament", "machine")), "")
        if not kind:
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except ValueError, UnicodeError:
            continue
        if not isinstance(data, dict):
            continue
        source = f"{program}/{file.relative_to(root).as_posix()}"
        extremes.files += 1
        if kind == "process":
            read, _foreign = manufacturer._read_process(data, context, {}, program_name=program)
        elif kind == "filament":
            read, _refuses = manufacturer._read_filament(data, {}, "", file, program)
        else:
            read, _refuses = manufacturer._read_filament({}, data, "", file, program)
            read.update(_nozzles(data.get("nozzle_diameter")))
        extremes.take(read, source)


def _prusa(root: Path, extremes: Extremes) -> None:
    context = manufacturer._Context(nozzle=0.4)
    for file in sorted(root.glob("*.ini")):
        parsed = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parsed.read_string(file.read_text(encoding="utf-8"), source=str(file))
        except configparser.Error, UnicodeError:
            continue
        for section in parsed.sections():
            if not section.startswith(("print:", "filament:", "printer:")):
                continue
            extremes.files += 1
            values = dict(parsed[section])
            read, _foreign = manufacturer._read_prusa(values, context)
            if section.startswith("printer:"):
                read.update(_nozzles(values.get("nozzle_diameter")))
            extremes.take(read, f"prusaslicer/{file.name}[{section}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "roots", nargs="*", help="Profilordner der Orca-Familie (Programmmarke=Pfad)"
    )
    arguments = parser.parse_args(argv)
    orca = [(Path(text.partition("=")[2]), text.partition("=")[0]) for text in arguments.roots] or [
        (Path(folder), program) for folder, program in ORCA_FAMILY
    ]
    extremes = Extremes()
    scanned: list[str] = []
    for folder, program in orca:
        if folder.is_dir():
            _orca(folder, program, extremes)
            scanned.append(program)
    if not arguments.roots and Path(PRUSA_BUNDLES).is_dir():
        _prusa(Path(PRUSA_BUNDLES), extremes)
        scanned.append("prusaslicer")
    if extremes.files < 100:
        print(f"nur {extremes.files} Profile gefunden — nichts geschrieben", file=sys.stderr)
        return 1
    document = {
        "generated_by": "tools/scan_vendor_values.py",
        "programs": scanned,
        "files": extremes.files,
        "values": extremes.values,
        "paths": dict(sorted(extremes.found.items())),
    }
    text = json.dumps(document, indent=1, ensure_ascii=False) + "\n"
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    found = len(extremes.found)
    print(f"{extremes.files} Profile, {extremes.values} Werte, {found} Felder → {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
