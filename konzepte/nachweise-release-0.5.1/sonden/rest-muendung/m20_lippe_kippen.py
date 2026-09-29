"""RM-262: Was liest die Erkennung an der gekippten Magnettasche mit Lippe — heute, an beiden Kernen?

Die Absage ``narrowing_reason`` für *Merkmal drehen* ist in dieser Sonde
abgeschaltet; gekippt wird über den Drehweg aus ``prepare_ops_mit_drehen.patch``
(auf den heutigen Stand übernommen). Quader 40 × 40 × 10, Magnettasche 8x3 mittig
oben (Tasche Ø 8,25, Lippe auf 7,95). Je Kern und Winkel: Merkmale im Baum
nach der Auswertung, frisch erkannt, und die Knickwinkel im Hohlraum.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import TREE, as_mesh_data, np  # noqa: E402

sys.path.insert(0, TREE)
from app.core.brep.features import features_of  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import actions  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

out = open(Path(__file__).with_name("m20_lippe_kippen.txt"), "w", encoding="utf-8", buffering=1)
original = actions.narrowing_reason
actions.narrowing_reason = lambda op, chain: None if op == "rotate_feature" else original(op, chain)
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


def say(*parts):
    print(*parts, flush=True)
    print(*parts, file=out)


def pocket(box: str):
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op=box, params={"width": 40.0, "depth": 40.0, "height": 10.0})])
    history.apply(
        "Magnet",
        [OperationDraft(op="insert_magnet_pocket", inputs=("obj_1",), params={"size": "8x3", "x": 0.0, "y": 0.0, "z": 10.0})],
    )
    return project, history


def describe(features, label):
    rows = []
    for name, f in sorted(features.items()):
        if f.kind in ("face",):
            continue
        rows.append(
            f"{name}:{f.kind} Ø{float(f.params.get('diameter', 0) or 0):.3f}"
            f"{' eng' if f.params.get('narrowing') else ''}{' teil' if f.params.get('partial') else ''}"
            f"{' Öffnung ' + format(float(f.params['opening']), '.3f') if 'opening' in f.params else ''}"
            f" △{len(f.face_indices)}"
        )
    say(f"      {label}: {', '.join(rows)}")


for box in ("create_brep_box", "create_box"):
    for angle in (10.0, 30.0):
        project, history = pocket(box)
        history.apply(
            "Drehen",
            [OperationDraft(op="rotate_feature", inputs=("obj_1",), params={"at_feature": "magnet_pocket_pocket_1", "axis": "x", "angle": angle})],
        )
        result = evaluate(project.document, PROFILE, sources=ProjectSources(project))
        say(f"== {box} {angle:g}°: vollständig {result.complete}")
        if not result.complete:
            say("   Befunde:", [str(f.message)[:160] for f in result.scene.report.findings if f.severity in ("warning", "error")])
            continue
        entry = result.scene.objects["obj_1"]
        data = as_mesh_data(entry.mesh)
        say(f"   Volumen {40 * 40 * 10 - abs(float(entry.mesh.volume)):.3f} abgetragen, Dreiecke {len(data.raw.faces)}, dicht {data.is_watertight}")
        describe(entry.features, "im Baum")
        forget_cache()
        describe(detect(data), "Netz frisch")
        if box == "create_brep_box":
            describe(features_of(entry.mesh), "exakt frisch")
        raw = data.raw
        centres = raw.triangles_center
        near = np.hypot(centres[:, 0], centres[:, 1]) < 5.5
        pairs = raw.face_adjacency
        angles = np.degrees(raw.face_adjacency_angles)
        keep = near[pairs[:, 0]] & near[pairs[:, 1]]
        counts, edges = np.histogram(angles[keep], bins=[0, 1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 180])
        say("      Knicke im Hohlraum: " + ", ".join(f"{edges[i]:.0f}-{edges[i + 1]:.0f}: {counts[i]}" for i in range(len(counts))))

# Danach: was sagt die nächste Handlung an der gekippten Tasche?
from app.core.perceive.relations import cavity_chain_state_at  # noqa: E402

for box in ("create_brep_box", "create_box"):
    project, history = pocket(box)
    history.apply(
        "Drehen",
        [OperationDraft(op="rotate_feature", inputs=("obj_1",), params={"at_feature": "magnet_pocket_pocket_1", "axis": "x", "angle": 10.0})],
    )
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project))
    entry = result.scene.objects["obj_1"]
    holes = [f for f in entry.features.values() if f.kind == "hole" and f.face_indices]
    for hole in holes:
        state = cavity_chain_state_at(hole, entry.features, as_mesh_data(entry.mesh))
        say(f"== {box} 10° danach: {hole.id} Kette {None if state.chain is None else [f.id for f in state.chain]}, berührt {state.touches_other} {state.reason}")
        centre = [float(v) for v in hole.params["centre"]]
        history.apply(
            "Versetzen",
            [OperationDraft(op="move_feature", inputs=("obj_1",), params={"at_feature": hole.id, "x": centre[0] + 5.0, "y": centre[1], "z": centre[2]})],
        )
        after = evaluate(project.document, PROFILE, sources=ProjectSources(project))
        say(f"   Versetzen: vollständig {after.complete}; " + "; ".join(str(f.message)[:140] for f in after.scene.report.findings if f.severity in ("warning", "error")))
    if not holes:
        say(f"== {box} 10° danach: keine Bohrung mit Dreiecken im Baum")
