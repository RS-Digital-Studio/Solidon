"""RM-584: Kommt die Stützart nach Deckenform im Slicer an?

Aufruf: python stil_je_decke.py <ausgabe> <programm> …

Ein Körper mit flachem Arm über dem Bett und einem Kinn, das auf dem Modell
aufsetzt (wie ``tests/test_slice_findings.py::chin_over_chest`` mit Arm). Der
echte Rat schlägt Hybrid vor; übernommen wird, was er vorschlägt, und die
Übergabe schreibt es wie im Druckdialog (Ersatz je Programm über
``handover.offered_settings``). Gelesen wird der Kopf der Druckdatei: Stil und Art
der Stütze, dazu die Länge der Stützbahnen je Art.
Die Gegenprüfung aus ``F:/solidon-review-reports/gcode/rest`` liefert Programme
und Herstellerprofile wie in ``kontakt_je_teil.py``.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import re
import sys
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
#: Eine feste Stützart statt des Rats (``grid``, ``tree``, ``hybrid``) — zum Vergleich.
STYLE = os.environ.get("SONDE_STIL", "")
OUT = Path(sys.argv[1]).resolve() / (STYLE or "rat")
(OUT / "stil").mkdir(parents=True, exist_ok=True)
TREE = HERE.parents[2]
os.environ.update(PYTHONUTF8="1", ABZUG=str(TREE), GC=str(OUT), GP_LAUF="stil")
spec = importlib.util.spec_from_file_location(
    "gp", r"F:\solidon-review-reports\gcode\rest\gegenpruefung.py"
)
assert spec is not None and spec.loader is not None
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)
sys.path.insert(0, str(TREE))

from app.core.export import slicer_keys, writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.types import SceneObject  # noqa: E402
from tests.test_slice_findings import brick, chin, on_bed  # noqa: E402

h.SLICERS["anycubic"] = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
PROGRAMS = {
    "elegoo": ("elegooslicer", "slicer-orca-af8733f715e1dfb0606b"),
    "orca": ("orcaslicer", "slicer-orca-af8733f715e1dfb0606b"),
    "bambu": ("bambustudio", "bambu-p1s"),
    "creality": ("crealityprint", "creality-k1"),
    "anycubic": ("anycubicslicernext", "anycubic-kobra-2"),
    "prusa": ("prusaslicer", "prusa-mini"),
    "superslicer": ("superslicer", "prusa-mini"),
    "cura": ("cura", "sovol-sv06"),
}
#: Schlüssel im Kopf der Druckdatei, die Art und Stil der Stütze tragen.
HEADER = re.compile(
    r"^;\s*(support_style|support_type|enable_support|support_material_style|"
    r"support_material|support_structure|support_enable|support_base_pattern|"
    r"support_material_pattern)\s*=\s*(.*?)\s*$"
)
FEATURE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$")
MOVE = re.compile(r"^G1\b.*\bE")


def figure_with_arm() -> MeshData:
    """Flacher Arm über dem Bett, Kinn auf der Brust (Test ``with_arm``)."""
    return on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
        brick(28.0, 30.0, 3.0, (54.0, 0.0, 40.0)),
        brick(4.0, 30.0, 40.0, (38.0, 0.0, 20.0)),
    )


def header_and_paths(gcode: Path) -> tuple[dict[str, str], dict[str, int]]:
    """Kopfwerte zur Stütze und die Zahl der Extrusionen je Bahnart."""
    header: dict[str, str] = {}
    paths: Counter[str] = Counter()
    kind = ""
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            found = HEADER.match(line)
            if found:
                header[found.group(1)] = found.group(2)
                continue
            typed = FEATURE.match(line)
            if typed:
                kind = typed.group(1)
                continue
            if "support" in kind.casefold() and MOVE.match(line):
                paths[kind] += 1
    return header, dict(paths)


def object_style(project: Path) -> dict[str, str]:
    """Was die 3MF je Objekt zur Stütze trägt (Orca ``model_settings.config``,
    Prusa ``Slic3r_PE_model.config``)."""
    import zipfile
    from xml.etree import ElementTree as ET

    if not zipfile.is_zipfile(project):
        return {}
    found: dict[str, str] = {}
    with zipfile.ZipFile(project) as archive:
        for member in ("Metadata/model_settings.config", "Metadata/Slic3r_PE_model.config"):
            if member in archive.namelist():
                for node in ET.fromstring(archive.read(member)).iter("metadata"):
                    key = node.get("key", "")
                    if "support" in key and (
                        "style" in key
                        or "type" in key
                        or key in ("enable_support", "support_material")
                    ):
                        found[key] = node.get("value", "")
    return found


def run(name: str) -> dict[str, object]:
    _program, printer = PROGRAMS[name]
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {"program": name, "printer": printer}
    h.CAPTURE.clear()
    h.CAPTURE["copy_dir"] = str(folder)
    try:
        profile = h.profiles.make_profile(printer, "pla")
        setup, info = h.prepared(name, profile, "pla")
        if setup is None:
            raise RuntimeError(info)
        if setup.flavour != "cura":
            entries = h.found_profiles(setup.executable, setup.flavour, ("machine", "process"))
            machine, process = h.slicer_profiles.match(entries, profile.printer)
            if machine is None:
                raise RuntimeError("Kein Maschinenprofil des Herstellers")
            setup = dataclasses.replace(
                setup,
                machine_profile=h.slicer_profiles.identity(machine),
                base_process=h.slicer_profiles.identity(process) if process else "",
            )
        setup = h.manufacturer.for_stage(setup, profile, "standard")
        foundation = h.manufacturer.base_settings(profile, "standard", setup)
        settings = h.manufacturer.effective(None, foundation)
        body = SceneObject(id="figur", name="figur", mesh=figure_with_arm())
        result = h.slice_body(body.mesh, settings.layers.layer_height)
        advice = advise.advise(settings, profile, result, flavour=setup.flavour)
        advice = slicer_keys.offered(advice, slicer_keys.program_of(setup.executable))
        style = next((entry.value for entry in advice if entry.path == "support.style"), None)
        row["advice"] = style
        chosen = STYLE or style or "hybrid"
        replaced = slicer_keys.substitute(
            "support.style", chosen, slicer_keys.program_of(setup.executable)
        )
        chosen = replaced.value if replaced is not None else chosen
        row["style"] = chosen
        settings = h.print_settings.with_accepted(settings, "support.style", chosen)
        if STYLE:
            # Die erzwungene Art gilt dem Teil: Der Rat je Teil schweigt zur Art, und
            # die Übernahme geht als Objektwert an alle (``writer._unserved``).
            original = writer.part_advice

            def without_style(*args: object, **kwargs: object) -> list[object]:
                return [e for e in original(*args, **kwargs) if e.path != "support.style"]

            writer.part_advice = without_style  # type: ignore[assignment]
        project, findings = writer.write_assembly(
            [body],
            folder,
            project_name="stil",
            profile=profile,
            settings=settings,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
        )
        row["findings"] = [entry.code for entry in findings]
        outcome = h.handover.slice_model(
            [project],
            settings,
            profile,
            setup,
            output_dir=folder,
            timeout=900,
            keep_arrangement=True,
            model_height=64.0,
        )
        header, paths = header_and_paths(Path(outcome.gcode_path))
        row.update(gcode=str(outcome.gcode_path), header=header, support_paths=paths, ok=True)
        row["object_values"] = object_style(Path(project))
    except Exception as error:
        row.update(ok=False, error=f"{type(error).__name__}: {error}", trace=traceback.format_exc())
    (folder / "ergebnis.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    return row


if __name__ == "__main__":
    for name in sys.argv[2:]:
        result = run(name)
        if result.get("ok"):
            print(
                name,
                "Rat",
                result["advice"],
                "Stil",
                result["style"],
                "Objekt",
                result["object_values"],
                flush=True,
            )
            print("  Stützbahnen", result["support_paths"], flush=True)
        else:
            print(name, "FEHLER", result.get("error"), flush=True)
