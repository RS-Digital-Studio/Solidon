"""S3: Die Fallmatrix — jeder STEP-Referenzkörper gegen den Prototyp.

Eingabe: ``step/<name>.step`` und die Sollwerte aus ``cases.json`` (beide von
``s2_reference.py``, die Sollwerte aus den Konstruktionsmaßen). Je Fall:

* fachliche Auskunft (gefunden/nicht, Teilung, Vorschub, Gangzahl, Händigkeit,
  Innen/Außen, Kamm-Ø, Gangtiefe, Achse, Länge) gegen den Sollwert —
  Teilung und Vorschub auf 1e-4, Radien auf 1e-3, Achse auf 1e-6 im
  Skalarprodukt, kein Spielraum darüber hinaus;
* Gegenfälle: keine Auskunft, und der Grund steht dabei;
* **Eingabeunveränderlichkeit**: Flächen, Kanten, Volumen und die
  Abtastpunkte der ersten Kandidatenkante sind vor und nach der Messung
  identisch;
* **Netzvergleich**: ``perceive.helix.find_helices`` an der Tessellation
  desselben Körpers — dieselbe fachliche Auskunft, soweit das Netz sie kennt
  (Teilung, Durchmesser, Innen/Außen); was es nicht kennt (Händigkeit,
  Gangzahl), wird als unbekannt ausgewiesen, nicht verglichen;
* **Abbruch**: ein Zähler, der nach n Aufrufen wirft, bricht die Messung ab.
"""

from __future__ import annotations

import json
from pathlib import Path

import _iso  # noqa: F401
import _probe as pr
import numpy as np

from app.core import bootstrap

bootstrap.load_operations()

import thread_probe as tp  # noqa: E402

from app.core.brep import step  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.perceive.helix import find_helices  # noqa: E402

HERE = Path(__file__).resolve().parent
cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


class CancelledError(Exception):
    pass


def counting_cancel(limit: int):  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def check() -> None:
        calls["n"] += 1
        if calls["n"] >= limit:
            raise CancelledError(f"nach {calls['n']} Prüfungen")

    return check, calls


def fingerprint(solid):  # type: ignore[no-untyped-def]
    chains = tp.candidate_chains(solid)
    first = chains[0].points.copy() if chains else np.zeros((0, 3))
    return solid.face_count, solid.edge_count, solid.volume, first


summary: list[tuple[str, str, str]] = []

for name, expect in cases.items():
    pr.out()
    pr.out(f"== {name} ==")
    solid = step.read((HERE / "step" / f"{name}.step").read_bytes())
    before = fingerprint(solid)
    with pr.Timed(f"{name}: Messung"):
        reading = tp.read_thread(solid)
    after = fingerprint(solid)
    pr.check(
        f"{name}: Eingabe unverändert (Flächen, Kanten, Volumen, Abtastpunkte)",
        before[0] == after[0]
        and before[1] == after[1]
        and abs(before[2] - after[2]) < 1e-12
        and np.array_equal(before[3], after[3]),
    )
    pr.out(f"  Auskunft: {tp.describe(reading)}")
    if not expect["found"]:
        pr.check(
            f"{name}: kein Gewinde gemeldet ({expect.get('why', '')})",
            not reading.found,
            reading.reason,
        )
        summary.append((name, "nein", reading.reason))
        continue
    pr.check(f"{name}: Gewinde gefunden", reading.found, reading.reason)
    if not reading.found:
        summary.append((name, "FEHLT", reading.reason))
        continue
    assert reading.pitch is not None and reading.lead is not None and reading.axis is not None
    pr.close(f"{name}: Teilung", reading.pitch, float(expect["pitch"]), 1e-4)
    pr.close(f"{name}: Vorschub je Umdrehung", reading.lead, float(expect["lead"]), 1e-4)
    pr.check(
        f"{name}: Gangzahl {expect['starts']}",
        reading.starts == expect["starts"],
        f"ist {reading.starts}",
    )
    pr.check(
        f"{name}: Händigkeit {expect['handedness']}",
        reading.handedness == expect["handedness"],
        f"ist {reading.handedness}",
    )
    pr.check(
        f"{name}: {'innen' if expect['internal'] else 'außen'}",
        reading.internal == expect["internal"],
        f"ist internal={reading.internal}",
    )
    assert reading.diameter is not None and reading.depth is not None
    pr.close(
        f"{name}: Nenn-Ø (außen Kamm, innen Grund)",
        reading.diameter,
        float(expect["diameter"]),
        1e-3,
    )
    pr.close(f"{name}: Gangtiefe", reading.depth, float(expect["depth"]), 1e-3)
    dot = abs(float(np.dot(reading.axis, np.asarray(expect["axis"], dtype=float))))
    pr.close(f"{name}: Achse (Skalarprodukt)", dot, 1.0, 1e-6)
    if not expect.get("partial"):
        assert reading.length is not None
        pr.close(f"{name}: Länge der Wendel", reading.length, float(expect["length"]), 1e-3)
    assert reading.uncertainty is not None
    # Die Wendelabweichung ist der größte Punktabstand von der idealen Wendel —
    # bei M10 sind es 4,3 µm an **einem** Punkt einer Fußkante (Boolesche Naht
    # des Referenzkörpers, RMS 1,4e-4), sonst unter 3e-5. Sie wird gemeldet,
    # nicht verschluckt; die Grenze hier ist ein Hundertstel der Teilung.
    pr.check(
        f"{name}: Wendelabweichung unter 1 % der Teilung",
        reading.uncertainty < 0.01 * reading.pitch,
        f"{reading.uncertainty:.2e}",
    )
    side = "innen" if reading.internal else "außen"
    summary.append(
        (
            name,
            "ja",
            f"p={reading.pitch:.4f} L={reading.lead:.4f} n={reading.starts} "
            f"{reading.handedness} {side} Ø{reading.diameter:.4f}",
        )
    )

    # Netzvergleich: dieselbe Auskunft, soweit das Netz sie kennt.
    mesh = as_mesh_data(solid)
    helices = find_helices(mesh)
    pr.out(f"  Netz (find_helices): {len(helices)} Wendel(n)")
    if helices:
        h = max(helices, key=lambda entry: entry.turns)
        pr.out(
            f"    Netz: Ø {h.diameter:.4f} p {h.pitch:.4f} innen={h.internal} "
            f"Länge {h.length:.3f} Umläufe {h.turns:.2f}"
        )
        pr.close(
            f"{name}: Netz-Teilung = exakte Teilung (Raster 0,01)", h.pitch, reading.pitch, 0.011
        )
        pr.check(f"{name}: Netz innen/außen wie exakt", h.internal == reading.internal)
        # Gleiches gegen Gleiches: Kammradius gegen Kammradius, Tiefe gegen
        # Tiefe — der Nenn-Ø des Netzwegs ist beim Innengewinde Kamm plus
        # Tiefe, und die Tiefe misst das Netz an Facetten.
        assert reading.crest_radius is not None
        pr.ratio(
            f"{name}: Netz-Kammradius gegen exakten Kammradius (Facettierung)",
            h.crest_radius,
            reading.crest_radius,
            0.03,
        )
        pr.out(
            f"    Netz-Tiefe {h.depth:.4f} gegen exakt {reading.depth:.4f} "
            f"({h.depth / reading.depth:.3f}) — Beobachtung, Netz-Nenn-Ø {h.diameter:.4f}"
        )
        pr.out("    Netz kennt weder Händigkeit noch Gangzahl — unbekannt, nicht verglichen")
    else:
        pr.out(
            "    Netz: keine Wendel gefunden (Beobachtung; der Netzweg verlangt "
            "5 Umläufe und 200 scharfe Kanten)"
        )

pr.out()
pr.out("== Abbruch: der Zähler wirft nach 50 Prüfungen ==")
solid = step.read((HERE / "step" / "m6_rechts.step").read_bytes())
check, calls = counting_cancel(50)
try:
    tp.read_thread(solid, check_cancelled=check)
    pr.check("Abbruch propagiert", False, "keine Ausnahme")
except CancelledError as stop:
    pr.check("Abbruch propagiert aus der Messung", True, str(stop))
check, calls = counting_cancel(10**9)
tp.read_thread(solid, check_cancelled=check)
pr.check(
    "Abbruchprüfung wird laufend aufgerufen (Kanten, Fit, Züge)",
    calls["n"] > 100,
    f"{calls['n']} Aufrufe",
)

pr.out()
pr.out("== Matrix ==")
for name, found, detail in summary:
    pr.out(f"  {name:20} {found:6} {detail}")
pr.finish("S3 Fallmatrix")
