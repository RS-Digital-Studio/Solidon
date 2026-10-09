"""Slicerbeleg RM-584 N1/N2: Pilz und Figur durch den Druckdialog und das echte Programm.

Aufruf (im Arbeitsbaum): python slicer_stil.py <ausgabe> <programm> <start> <wahl>

- ``programm``: ``cura`` oder ``elegooslicer`` (Name wie in tests/test_real_slicers.py)
- ``start``: eigene Wahl der Platte für ``support.style`` (``none``, ``auto``, ``tree``)
- ``wahl``: ``accept`` übernimmt die Zeile ``support.style``, ``decline`` lehnt sie ab,
  ``force:<art>`` übernimmt diese Art statt der Zeile (der alte Vorschlag zum Vergleich)

Gefragt wird der Arbeiter des Druckdialogs mit dem gefundenen Programm (keine
Attrappe), geschrieben über ``_prepare_plate`` und geschnitten über
``handover.slice_model`` wie *Slicen*. Gelesen wird der G-Code: Stützart im Kopf
(Cura ``support_structure``, Orca ``support_type``), Stützbahn und ihr Anteil am
Grundriss des Pilzhuts in den Schichten bis 1,6 mm darunter, Stützbahn bei der Figur.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

TREE = Path.cwd().resolve()
sys.path.insert(0, str(TREE))
import app  # noqa: E402

assert Path(app.__file__).resolve().parent.parent == TREE, app.__file__

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import numpy as np  # noqa: E402

from app.core import activation  # noqa: E402,F401
from app.core.export import handover, slicer_keys  # noqa: E402
from app.core.geom.transform import apply, translation  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.types import SceneObject  # noqa: E402
from app.ui import print_settings_dialog as dialog  # noqa: E402
from tests.helpers import brick, chin_over_chest, object_values, on_bed  # noqa: E402
from tests.test_real_slicers import PROGRAMS, _preselected  # noqa: E402

SLICERS = {
    "cura": Path(r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe"),
    "elegooslicer": Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"),
}
PRINTERS = {"cura": PROGRAMS["cura"], "elegooslicer": "centauri-carbon-2"}
TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")
SKIP = ("brim", "skirt", "prime", "wipe", "custom", "purge", "flush")
HAT_BOTTOM = 12.0
HAT_TOP = 14.0


def read(path: Path) -> tuple[np.ndarray, np.ndarray, str]:
    """Stützsegmente (x0, y0, x1, y1, z), Punkte der Modellbahnen (x, y, z), Kopftext."""
    support: list[tuple[float, float, float, float, float]] = []
    model: list[tuple[float, float, float]] = []
    x = y = z = 0.0
    e_abs = 0.0
    relative = False
    kind = ""
    head: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";"):
                found = TYPE.match(line.strip())
                if found:
                    kind = found.group(1).lower()
                elif "support" in line.lower():
                    head.append(line.strip())
                continue
            code = line.split(";", 1)[0].strip().upper()
            if code.startswith("M83"):
                relative = True
                continue
            if code.startswith("M82"):
                relative = False
                continue
            if code.startswith("G92"):
                for letter, value in WORD.findall(code):
                    if letter == "E":
                        e_abs = float(value)
                continue
            if not code.startswith(("G0", "G1")):
                continue
            values = dict(WORD.findall(code[2:]))
            nx = float(values.get("X", x))
            ny = float(values.get("Y", y))
            nz = float(values.get("Z", z))
            extruding = False
            if "E" in values:
                e = float(values["E"])
                delta = e if relative else e - e_abs
                if not relative:
                    e_abs = e
                extruding = delta > 1e-5
            if extruding and (nx != x or ny != y):
                if "support" in kind or "tree" in kind:
                    support.append((x, y, nx, ny, nz))
                elif kind and not any(word in kind for word in SKIP):
                    model.append((nx, ny, nz))
            x, y, z = nx, ny, nz
    return np.asarray(support).reshape(-1, 5), np.asarray(model).reshape(-1, 3), "\n".join(head)


def coverage(support: np.ndarray, model: np.ndarray) -> dict[str, object]:
    """Anteil des Pilzhuts (ohne Stiel) mit Stützbahn bis 1,6 mm darunter, auf 1 mm."""
    hat = model[(model[:, 2] > HAT_BOTTOM + 0.05) & (model[:, 2] <= HAT_TOP + 0.05)]
    xs = np.sort(hat[:, 0])
    gaps = np.diff(xs)
    split = (
        xs[int(np.argmax(gaps))] + gaps.max() / 2 if len(gaps) and gaps.max() > 5 else xs[-1] + 1
    )
    pilz = hat[hat[:, 0] < split]
    x0, y0 = pilz[:, 0].min(), pilz[:, 1].min()
    x1, y1 = pilz[:, 0].max(), pilz[:, 1].max()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    near = support[(support[:, 4] < HAT_BOTTOM) & (support[:, 4] >= HAT_BOTTOM - 1.6)]
    hit = set()
    for sx, sy, ex, ey, _z in near:
        steps = max(1, int(np.hypot(ex - sx, ey - sy) / 0.25))
        for t in np.linspace(0.0, 1.0, steps + 1):
            px, py = sx + (ex - sx) * t, sy + (ey - sy) * t
            hit.add((int(np.floor(px)), int(np.floor(py))))
    cells = [
        (i, j)
        for i in range(int(np.floor(x0)), int(np.ceil(x1)))
        for j in range(int(np.floor(y0)), int(np.ceil(y1)))
        if not (abs(i + 0.5 - cx) < 5 and abs(j + 0.5 - cy) < 5)
    ]
    under_pilz = support[(np.minimum(support[:, 0], support[:, 2]) < split)]
    beside = support[(np.minimum(support[:, 0], support[:, 2]) >= split)]
    length = lambda rows: float(np.hypot(rows[:, 2] - rows[:, 0], rows[:, 3] - rows[:, 1]).sum())  # noqa: E731
    return {
        "hut": [round(float(v), 1) for v in (x0, y0, x1, y1)],
        "huthoehe_gestuetzt": round(sum(cell in hit for cell in cells) / len(cells), 3),
        "stuetzbahn_pilz_mm": round(length(under_pilz)),
        "stuetzbahn_figur_mm": round(length(beside)),
    }


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    program, start, choice = sys.argv[2], sys.argv[3], sys.argv[4]
    folder = out / f"{program}-{start}-{choice.replace(':', '_')}"
    folder.mkdir(parents=True, exist_ok=True)
    from _pytest.monkeypatch import MonkeyPatch

    from tests.helpers import set_test_license

    set_test_license(MonkeyPatch(), active=True)
    profile = profiles.make_profile(PRINTERS[program], "pla")
    setup = _preselected(handover.detect(SLICERS[program]), profile)
    mushroom = on_bed(
        brick(8.0, 8.0, 12.0, (0.0, 0.0, 6.0)), brick(40.0, 40.0, 2.0, (0.0, 0.0, 13.0))
    )
    bodies = (
        SceneObject(id="obj_pilz", name="Pilz", mesh=mushroom),
        SceneObject(
            id="obj_figur",
            name="Figur",
            mesh=apply(chin_over_chest(), translation((70.0, 0.0, 0.0))),
        ),
    )
    settings = print_settings.resolve(profile)
    if start != "none":
        settings = print_settings.with_choice(settings, "support.style", start)
    else:
        settings = print_settings.with_choice(settings, "support.style", "none")

    def advice(current):
        worker = dialog._AdviceWorker(
            bodies, current, profile, setup, {}, (), (), {}, flavour=setup.flavour
        )
        got: list = []
        worker.done.connect(lambda entries, _results: got.append(entries))
        worker.work()
        return got[0], worker

    entries, worker = advice(settings)
    rows = [
        e
        for e in slicer_keys.offered(entries, slicer_keys.program_of(setup.executable))
        if e.path == "support.style"
    ]
    host = SimpleNamespace(_fields={field.path: field for field in dialog.FIELDS})
    report: dict[str, object] = {
        "programm": program,
        "drucker": PRINTERS[program],
        "start": start,
        "wahl": choice,
        "trees": sorted(getattr(worker, "trees", None) or []) or None,
        "zeile": [
            {
                "titel": dialog.PrintSettingsDialog._advice_title(host, row),
                "tooltip": dialog.PrintSettingsDialog._advice_parts(row),
                "was": row.was,
                "wert": row.value,
                "grund": str(row.reason),
            }
            for row in rows
        ],
    }
    if choice == "accept" and rows:
        settings = print_settings.with_accepted(settings, "support.style", rows[0].value)
    elif choice.startswith("force:"):
        settings = print_settings.with_accepted(settings, "support.style", choice.split(":", 1)[1])
    if settings.accepted:
        _entries, after = advice(settings)
        report["feld_teile"] = after.accepted_parts.get("support.style")
        report["feld_andere"] = getattr(after, "accepted_others", {}).get("support.style")
    job = dialog._PlateJob(
        objects=bodies,
        plates=(0,),
        folder=folder,
        name="stil",
        setup=setup,
        settings=settings,
        profile=profile,
        slot_profiles={},
    )
    run = dialog._prepare_plate(job, 0)
    commands: list[list[str]] = []
    original_run = handover._run_slicer

    def recording(command, *args, **kwargs):  # type: ignore[no-untyped-def]
        commands.append([str(part) for part in command])
        return original_run(command, *args, **kwargs)

    handover._run_slicer = recording  # type: ignore[assignment]
    outcome = handover.slice_model(
        [run.model],
        settings,
        profile,
        setup,
        output_dir=folder,
        timeout=900,
        keep_arrangement=run.keep_arrangement,
        slots=run.slots,
        model_height=run.model_height,
        model_meshes=run.meshes,
        expected_tools=run.used_tools,
    )
    gcode = Path(outcome.gcode_path)
    support, model, head = read(gcode)
    report["gcode"] = str(gcode)
    report["kopf"] = [
        line
        for line in head.splitlines()
        if re.search(r"support_(structure|type|style|enable)\b|enable_support", line)
    ][:12]
    if program == "cura":
        # CuraEngine bekommt die Platte als ``-s`` und schreibt keinen Kopf dazu.
        plate = handover.values_for(settings, profile, "cura")
        report["platte"] = {
            key: plate.get(key) for key in ("support_structure", "support_enable", "support_type")
        }
        report["aufruf_stuetze"] = [
            part
            for command in commands
            for part in command
            if part.startswith(("support_structure=", "support_enable=", "support_type="))
        ]
        report["netze"] = {
            mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(run.model)
        }
    else:
        values = object_values(run.model, "Metadata/model_settings.config")
        report["objektwerte"] = {
            name: {k: v for k, v in entry.items() if "support" in k}
            for name, entry in values.items()
        }
    report.update(coverage(support, model))
    (folder / "ergebnis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
