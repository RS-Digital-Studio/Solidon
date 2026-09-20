"""S2: Referenzkörper bauen, als STEP schreiben, Sollwerte festhalten.

Jeder Fall: Konstruktion aus benannten Maßen (``reference.py``), STEP nach
``step/<name>.step``, frisch eingelesen und geprüft, dass **kein**
Erzeugermerkmal mitkommt (``features_of`` kennt kein ``thread``; der Körper
trägt keine Namen). Die Sollwerte stehen in ``cases.json`` — sie kommen aus
den Konstruktionsmaßen, nicht aus dem Prüfling — und werden von
``s3_matrix.py`` gegen den Prototyp gehalten.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import _iso  # noqa: F401
import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

import reference as ref  # noqa: E402

from app.core.brep import step  # noqa: E402
from app.core.brep.features import features_of  # noqa: E402

HERE = Path(__file__).resolve().parent
STEP_DIR = HERE / "step"
STEP_DIR.mkdir(exist_ok=True)

cases: dict[str, dict[str, object]] = {}


def keep(name: str, solid, expect: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    """STEP schreiben, zurücklesen, Erzeugerfreiheit prüfen, Sollwerte merken."""
    payload = step.write(solid, name)
    (STEP_DIR / f"{name}.step").write_bytes(payload)
    back = step.read(payload)
    info = pr.expect_solid(f"{name}: importiert", back, solids=int(str(expect.get("solids", 1))))
    found = features_of(back)
    kinds = sorted({feature.kind for feature in found.values()})
    pr.check(
        f"{name}: kein Erzeugermerkmal nach dem Import (kein thread, keine generated-Herkunft)",
        "thread" not in kinds and all(f.provenance == "detected" for f in found.values()),
        f"Merkmale {kinds}",
    )
    if expect.get("found"):
        # **Die Voraussetzung des Falls wird hergestellt, nicht angenommen.**
        # Der kurze Bolzen kam anfangs aus ``threaded_rod(6, 1, 2.5)`` und
        # trug keinen Gang (B3); die Sonde meldete dann einen Prototypfehler
        # („Kamm ohne Rille"), der keiner war. Die Flanken eines Sweeps sind
        # B-Spline-Flächen — ohne sie gibt es nichts zu messen.
        pr.check(
            f"{name}: der Körper trägt Wendelflächen (B-Spline-Flächen >= 2)",
            int(info["types"].get("bspline", 0)) >= 2,
            f"Flächenarten {dict(info['types'])}",
        )
    expect = {**expect, "faces": info["faces"], "volume": info["volume"], "types": info["types"]}
    cases[name] = expect
    shown = {k: v for k, v in expect.items() if k != "types"}
    pr.out(f"  Sollwerte: {shown}")


pr.out("== Rechtsgewinde M6 x 1, Länge 12 ==")
with pr.Timed("threaded_rod M6"):
    m6 = ref.rod(6.0, 1.0, 12.0)
keep(
    "m6_rechts",
    m6,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE * 1.0,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== Rechtsgewinde M10 x 1,5, Länge 20 ==")
with pr.Timed("threaded_rod M10"):
    m10 = ref.rod(10.0, 1.5, 20.0)
keep(
    "m10_rechts",
    m10,
    {
        "pitch": 1.5,
        "lead": 1.5,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 10.0,
        "depth": ref.ISO_DEPTH_SHARE * 1.5,
        "length": 20.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== Linksgewinde M6 x 1 (Spiegelung an XZ) ==")
keep(
    "m6_links",
    ref.mirrored(m6),
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "left",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE * 1.0,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== Innengewinde M8 x 1,25 im Block, Spiel 0,2, Tiefe 10 ==")
with pr.Timed("Block minus Bolzen"):
    inner = ref.internal_block(8.0, 1.25, 10.0, 0.2)
keep(
    "m8_innen",
    inner,
    {
        "pitch": 1.25,
        "lead": 1.25,
        "starts": 1,
        "handedness": "right",
        "internal": True,
        "diameter": 8.2,
        "depth": ref.ISO_DEPTH_SHARE * 1.25,
        "length": 10.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== zweigängig: Ø8, Teilung 1,0, Vorschub 2,0, Länge 12 ==")
with pr.Timed("zwei Gänge"):
    two = ref.multi_start(8.0, 1.0, 2, 12.0)
keep(
    "zweigaengig",
    two,
    {
        "pitch": 1.0,
        "lead": 2.0,
        "starts": 2,
        "handedness": "right",
        "internal": False,
        "diameter": 8.0,
        # Der Kern sitzt 0,01 über dem Fuß des Profils (multi_start), damit
        # die Vereinigung eine Naht hat; sichtbar bleibt eine Rille von 0,54.
        "depth": 0.55 - 0.01,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== gedreht 37° um (1, 1, 0) und verschoben (12, -7, 3) ==")
keep(
    "m6_gedreht",
    ref.placed(m6, 37.0, (1.0, 1.0, 0.0), (12.0, -7.0, 3.0)),
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 12.0,
        "axis": ref.rotated_axis(37.0, (1.0, 1.0, 0.0)),
        "found": True,
    },
)

pr.out()
pr.out("== angeschnitten: alles unter x = -1 fehlt ==")
with pr.Timed("halbiert"):
    half = ref.halved(m6, -1.0)
keep(
    "m6_angeschnitten",
    half,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
        "partial": True,
    },
)

pr.out()
pr.out("== kurzes Teilgewinde: M6 x 1, Stück z 4,75..7,25 (2,5 Umläufe) ==")
with pr.Timed("kurzer Bolzen"):
    short = ref.segment(m6, 4.75, 7.25)
core_only = math.pi * (3.0 - ref.ISO_DEPTH_SHARE) ** 2 * 2.5
pr.check(
    "kurzer Bolzen: mehr Volumen als sein Kern allein (der Gang ist da)",
    short.volume > core_only + 1.0,
    f"{short.volume:.3f} gegen Kern {core_only:.3f}",
)
keep(
    "m6_kurz",
    short,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 2.5,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== beschädigte Flanken: Sektor 60° über z 4..8 ab r = 2,6 fehlt ==")
with pr.Timed("beschädigt"):
    broken = ref.damaged(m6, 4.0, 8.0, 60.0, 2.6)
keep(
    "m6_beschaedigt",
    broken,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
        "partial": True,
    },
)

pr.out()
pr.out("== geteilte Trägerflächen: Ebene z = 6 teilt Flächen und Kanten ==")
with pr.Timed("Splitter"):
    split = ref.split_faces(m6, 6.0)
keep(
    "m6_geteilt",
    split,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== neue Parametrisierung: alles als NURBS (BRepBuilderAPI_NurbsConvert) ==")
with pr.Timed("NurbsConvert"):
    nurbs = ref.reparametrised(m6)
keep(
    "m6_nurbs",
    nurbs,
    {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ref.ISO_DEPTH_SHARE,
        "length": 12.0,
        "axis": (0.0, 0.0, 1.0),
        "found": True,
    },
)

pr.out()
pr.out("== Gegenfälle ==")
keep("gegen_zylinder", ref.smooth_cylinder(6.0, 12.0), {"found": False, "why": "glatter Zylinder"})
with pr.Timed("Ringrillen"):
    grooves = ref.ring_grooves(6.0, 12.0, 4, 0.4)
keep(
    "gegen_ringrillen",
    grooves,
    {"found": False, "why": "Ringrillen (Tori), periodisch, nicht schraubenförmig"},
)
with pr.Timed("Rändel"):
    knurled = ref.knurl(6.0, 12.0, 12, 0.3)
keep("gegen_raendel", knurled, {"found": False, "why": "Längsrillen, alle Kanten gerade"})
with pr.Timed("Wellenprofil"):
    waves = ref.wave_profile(6.0, 12.0, 0.3, 6)
keep("gegen_welle", waves, {"found": False, "why": "gewellter Drehkörper, Spline-Meridian"})
with pr.Timed("Naht"):
    seam = ref.seam_helix(6.0, 12.0, 1.0, 0.02)
keep("gegen_naht", seam, {"found": False, "why": "Wendel ohne Rille (Tiefe 0,02 mm)"})
with pr.Timed("Viertelgang"):
    piece = ref.sector_piece(m6, 3.0, 3.4, 90.0)
keep("gegen_viertelgang", piece, {"found": False, "why": "ein Ausschnitt unter einer Umdrehung"})

(HERE / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")
pr.out(
    f"\n{len(cases)} Fälle nach {STEP_DIR.relative_to(HERE.parents[1])} und cases.json geschrieben"
)
pr.finish("S2 Referenzkörper")
