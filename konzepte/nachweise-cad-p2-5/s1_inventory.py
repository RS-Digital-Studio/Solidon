"""S1: Der Bestand — was heute über ein Gewinde bekannt ist, und woher.

Drei Wege, dieselbe Geometrie (M6 x 1, Länge 12):

1. **Erzeuger** ``thread_exact``: das Merkmal ``thread_1`` kommt aus den
   Operationswerten (``provenance="generated"``, Händigkeit ``right`` als
   Wissen des Erzeugers).
2. **Import** über STEP: ``features_of`` liest die Topologie — was steht dann
   da, und was fehlt?
3. **Netzweg** ``perceive.features.detect`` an der Tessellation desselben
   Körpers: ``helix.find_helices`` misst Steigung, Durchmesser, Innen/Außen —
   und was es nicht misst.

Dazu die Normteiltabelle (welche Steigungen der Katalog kennt), der
Gegenstückweg (``counterpart``: braucht ``size``) und die Gewindebausteine
(``printed_thread`` mit dem Netzprofil) als Netz durch den Netzweg.
"""

from __future__ import annotations

import _iso  # noqa: F401
import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core import counterpart  # noqa: E402
from app.core.brep import step  # noqa: E402
from app.core.brep.features import features_of  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.knowledge import standards  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.knowledge.profiles import make_profile  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402
from app.core.perceive.helix import find_helices  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

PROFILE = make_profile("centauri-carbon-2", "petg")


def kinds(features) -> dict[str, int]:  # type: ignore[no-untyped-def]
    found: dict[str, int] = {}
    for feature in features.values():
        found[feature.kind] = found.get(feature.kind, 0) + 1
    return dict(sorted(found.items()))


pr.out("== 1. Erzeuger thread_exact: M6 x 1, Länge 12 ==")
project = new_project("centauri-carbon-2", "petg")
history = History(project.document)
with pr.Timed("thread_exact"):
    history.apply(
        "Bolzen",
        [OperationDraft(op="thread_exact", params={"diameter": 6.0, "pitch": 1.0, "length": 12.0})],
    )
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project))
bolt = next(iter(result.scene.objects.values()))
generated = bolt.features["thread_1"]
pr.check("Erzeuger: thread_1 mit provenance generated", generated.provenance == "generated")
pr.out(f"  Merkmale: {kinds(bolt.features)}")
pr.out(f"  thread_1: {generated.params}")
pr.out(f"  measure_sources: {generated.measure_sources}")
pr.check(
    "Erzeuger: Händigkeit ist Erzeugerwissen (right), keine Messung",
    generated.params.get("handedness") == "right" and "handedness" not in generated.measure_sources,
)
pr.check(
    "Erzeuger: weder Vorschub noch Gangzahl im Vertrag",
    "lead" not in generated.params and "starts" not in generated.params,
)

pr.out()
pr.out("== 2. Import über STEP: derselbe Körper ohne Erzeugerwissen ==")
back = step.read(step.write(bolt.mesh, "m6"))
imported = features_of(back)
pr.out(f"  features_of: {kinds(imported)}")
pr.check("Import: kein thread-Merkmal aus der Topologie", "thread" not in kinds(imported))
pins = [f for f in imported.values() if f.kind == "pin"]
pr.out("  Zapfen: " + ", ".join(f"Ø{f.params.get('diameter', 0):.4f}" for f in pins))
pr.check("Import: die Kernstücke werden als Zapfen gelesen (Konzept §3: 7 pin)", len(pins) >= 1)
pr.check(
    "Import: kein Merkmal kennt Steigung oder Händigkeit",
    all("pitch" not in f.params and "handedness" not in f.params for f in imported.values()),
)

pr.out()
pr.out("== 3. Netzweg an der Tessellation desselben Körpers ==")
mesh = as_mesh_data(back)
with pr.Timed("detect am Netz"):
    detected = detect(mesh)
detected_map = detected
pr.out(f"  detect: {kinds(detected_map)}")
threads = [f for f in detected_map.values() if f.kind == "thread"]
pr.check("Netzweg: genau ein thread", len(threads) == 1, str(len(threads)))
if threads:
    thread = threads[0]
    pr.out(f"  thread: {thread.params}")
    pr.out(f"  measure_sources: {thread.measure_sources}")
    pr.close("Netzweg: Steigung 1,0 (Raster 0,01)", float(thread.params["pitch"]), 1.0, 0.011)
    pr.ratio("Netzweg: Ø 6 (Facettierung)", float(thread.params["diameter"]), 6.0, 0.03)
    pr.check("Netzweg: außen", thread.params.get("internal") is False)
    pr.check(
        "Netzweg: keine Händigkeit, kein Vorschub, keine Gangzahl",
        all(key not in thread.params for key in ("handedness", "lead", "starts")),
    )

pr.out()
pr.out("== 3b. Netzweg an einem Linksgewinde (Spiegelung derselben Tessellation) ==")
import numpy as np  # noqa: E402

from app.core.geom import transform  # noqa: E402

left_mesh = transform.apply(mesh, np.diag([1.0, -1.0, 1.0, 1.0]))
helices_left = find_helices(left_mesh)
helices_right = find_helices(mesh)
pr.out(f"  rechts: {len(helices_right)} Wendel(n); links: {len(helices_left)} Wendel(n)")
if helices_left and helices_right:
    left = helices_left[0]
    pr.out(f"  links: p {left.pitch:.4f} Ø {left.diameter:.4f} innen={left.internal}")
    pr.check(
        "Netzweg findet das Linksgewinde mit derselben Steigung — ohne es links zu nennen",
        abs(helices_left[0].pitch - helices_right[0].pitch) < 0.011,
    )
else:
    pr.check(
        "BEFUND Netzweg: Linksgewinde wird nicht gefunden",
        not helices_left,
        "Konzentration z - p·θ/2π setzt Rechtsgang voraus",
    )

pr.out()
pr.out("== 4. Normteiltabelle: bekannte Steigungen ==")
for size in standards.screw_sizes():
    screw = standards.screw(size)
    pr.out(f"  {size:5} nominal {screw.nominal:5.2f} pitch {screw.pitch:5.3f} tap {screw.tap:5.2f}")
pr.out(
    "  Es gibt keine Funktion Steigung -> Größe; size_for_thread ordnet nur einen Bohrungs-Ø zu."
)
pr.out("  Eine gemessene Teilung 1,0 bei Ø 6 passt zu M6, 1,25 bei Ø 8 zu M8 — eine Zuordnung")
pr.out("  bleibt ein Vorschlag mit Toleranz, keine Antwort (Konzept §13.4).")

pr.out()
pr.out("== 5. Gegenstück: das Paar screw_and_nut teilt size und play ==")
pair = counterpart.pair_named("screw_and_nut")
pr.out(f"  {pair.key}: {pair.part_a} + {pair.part_b}, geteilt {pair.shared}, Passung {pair.kind}")
pr.check(
    "Gegenstück braucht eine Normgröße; ein Importgewinde ohne size hat heute keinen Weg (P2.6)",
    "size" in pair.shared,
)

pr.out()
pr.out("== 6. Gewindebausteine (Netzprofil) durch den Netzweg ==")
spec = PARTS.get("printed_thread")
for internal in (False, True):
    produced = spec.fn(
        spec.params(size="M6", length=12.0, internal=internal, play=0.2 if internal else 0.0)
    )
    found = find_helices(as_mesh_data(produced.mesh))
    label = "innen" if internal else "außen"
    pr.out(f"  printed_thread {label}: {len(found)} Wendel(n)")
    if found:
        h = found[0]
        pr.out(f"    p {h.pitch:.4f} Ø {h.diameter:.4f} innen={h.internal} Umläufe {h.turns:.1f}")
        pr.close(f"Baustein {label}: Steigung 1,0", h.pitch, 1.0, 0.011)
        # Der Innenbaustein ist ein **Werkzeug** (Kern plus Gang nach außen, wird
        # abgezogen): geometrisch ein Außengewindekörper. Ein Innengewinde
        # entsteht erst am Träger — S2/S3 messen es dort (m8_innen).
        pr.check(
            f"Baustein {label}: der Körper selbst trägt sein Material innen (Werkzeug)",
            h.internal is False,
        )
    else:
        pr.check(f"Baustein {label}: Netzweg findet das Bausteingewinde", False, "keine Wendel")

pr.finish("S1 Bestand")
