"""S1: Das Bausteinregister, wie es der Bootstrap wirklich lädt.

Zählt Bausteine, Gruppen, erzeugte Operationen und die Bauart jedes
Bausteinpfads an einem exakten Träger — dieselbe Grundlage wie
``s8_matrix.py`` der Durchsicht vom 19.09. (exakter Quader 40 x 30 x 10,
exakte Bohrung Ø 5), hier aber mit den Pflichtparametern, die dort fehlten,
damit auch die vier angehaltenen Pfade eine Bauartaussage bekommen.

Ausgabe: je Baustein Gruppe, Version, Flags, versprochene Merkmale, die
Bauart des Ergebnisses und die Befunde. Am Ende die Zählung gegen die
Konzeptangabe „35 Bausteine / 31 konvertierende Pfade".
"""

from __future__ import annotations

import dataclasses
import sys
from collections import Counter

import _iso  # noqa: F401

from app.core import bootstrap
from app.core.registry import REGISTRY

bootstrap.load_operations()

from app.core.knowledge.parts import ops as part_ops  # noqa: E402
from app.core.knowledge.parts.registry import LIBRARY_VERSION, PARTS  # noqa: E402
from app.core.knowledge.profiles import make_profile  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

PROFILE = make_profile("centauri-carbon-2", "petg")

#: Eine geschlossene Sitz- bzw. Gegenkontur für Klemmschale/Einlage und ein
#: Dichtweg — die vier Pfade, die in der Durchsicht ohne diese Pflichtwerte
#: anhielten. Gezeichnet wie in ``tests/test_profile_clamps.py``.
from app.core.sketch import shapes as sketch_shapes  # noqa: E402
from app.core.sketch.serialize import sketch_to_text  # noqa: E402

CLAMP_SEAT = sketch_to_text(sketch_shapes.circle(20.25))
CLAMP_COUNTER = sketch_to_text(sketch_shapes.circle(20.0))
SEAL_PATH = sketch_to_text(sketch_shapes.rectangle(20.0, 12.0))

OVERRIDES: dict[str, dict[str, object]] = {
    "insert_heatset_m4": {"size": "M4"},
    "insert_profile_clamp_liner": {"counter_sketch": CLAMP_COUNTER},
    "insert_profile_clamp_shell": {"seat_sketch": CLAMP_SEAT},
    "insert_seal_gasket": {"path_sketch": SEAL_PATH},
    "insert_seal_groove": {"path_sketch": SEAL_PATH},
    "create_profile_clamp_liner": {"counter_sketch": CLAMP_COUNTER},
    "create_profile_clamp_shell": {"seat_sketch": CLAMP_SEAT},
    "create_seal_gasket": {"path_sketch": SEAL_PATH},
}


def out(line: str) -> None:
    print(line)
    sys.stdout.flush()


def fresh():  # type: ignore[no-untyped-def]
    project = new_project("centauri-carbon-2", "petg")
    doc = project.document
    history = History(doc)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}
            )
        ],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 10.0}
            )
        ],
    )
    return project, doc, history


def state(project, doc):  # type: ignore[no-untyped-def]
    result = evaluate(doc, PROFILE, sources=ProjectSources(project))
    if not result.scene.objects:
        return None, result
    return list(result.scene.objects.values()), result


def first_feature(obj, kind: str) -> str:  # type: ignore[no-untyped-def]
    for feature in obj.features.values():
        if feature.kind == kind:
            return feature.id
    return ""


def field_names(spec) -> set[str]:  # type: ignore[no-untyped-def]
    try:
        return {field.name for field in dataclasses.fields(spec.params)}
    except TypeError:
        return set()


out(f"LIBRARY_VERSION = {LIBRARY_VERSION}")
parts = sorted(PARTS.all(), key=lambda s: (s.group, s.name))
out(f"Bausteine im Register: {len(parts)}")
out(f"Gruppen: {dict(Counter(s.group for s in parts))}")
part_ops_all = sorted((s for s in REGISTRY.all() if s.category == "parts"), key=lambda s: s.name)
out(f"Operationen der Kategorie parts: {len(part_ops_all)}")
inserts = [s.name for s in part_ops_all if s.name.startswith("insert_")]
creators = [s.name for s in part_ops_all if s.name.startswith("create_")]
out(f"  insert_*: {len(inserts)}   create_*: {len(creators)} -> {creators}")

out("")
out("Baustein | Gruppe | v | Flags | Merkmale")
for spec in parts:
    flags = []
    for name in (
        "subtractive",
        "at_hole",
        "at_hole_mouth",
        "separate_from_host",
        "joined_by_host",
        "standalone",
        "lies_flat",
        "keeps_up",
    ):
        if getattr(spec, name, False):
            flags.append(name)
    if spec.host_cut is not None:
        flags.append("host_cut")
    if spec.host_add is not None:
        flags.append("host_add")
    if spec.bodies != 1:
        flags.append(f"bodies={spec.bodies}")
    if not spec.at_face:
        flags.append("not_at_face")
    out(
        f"{spec.name:24} {spec.group:12} {spec.version:>3} "
        f"{','.join(flags) or '-':60} {','.join(spec.features)}"
    )

out("")
out("Bauart je Bausteinpfad am exakten Träger:")
project, doc, history = fresh()
objs, result = state(project, doc)
assert objs is not None
base = objs[0]
HOLE = first_feature(base, "hole")
FACE = first_feature(base, "face")
out(f"Grundlage kind={base.kind} HOLE={HOLE} FACE={FACE}")

rows: list[tuple[str, str, str, str]] = []
for spec in part_ops_all:
    name = spec.name
    params: dict[str, object] = {}
    fields = field_names(spec)
    if spec.consumes == 0:
        params.update(OVERRIDES.get(name, {}))
        project = new_project("centauri-carbon-2", "petg")
        doc = project.document
        history = History(doc)
        try:
            history.apply(name, [OperationDraft(op=name, params=params)])
            objs, result = state(project, doc)
            if objs is None or getattr(result, "stopped_at", None) is not None:
                rows.append((name, "ANGEHALTEN", "-", str(result.stopped_at)[:100]))
            else:
                kinds = sorted({o.kind for o in objs})
                rows.append((name, "erzeugt:" + "/".join(kinds), str(len(objs)), ""))
        except Exception as error:
            rows.append((name, "FEHLER", "-", f"{type(error).__name__}: {error}"[:120]))
        out(f"{rows[-1][0]:32} {rows[-1][1]:16} {rows[-1][2]:4} {rows[-1][3]}")
        continue
    if "at_feature" in fields:
        want = HOLE if ("hole" in spec.applies_to or not spec.applies_to) else ""
        if not want and "face" in spec.applies_to:
            want = FACE
        params["at_feature"] = want or HOLE
    params.update(OVERRIDES.get(name, {}))
    project, doc, history = fresh()
    try:
        history.apply(name, [OperationDraft(op=name, inputs=("obj_1",), params=params)])
        objs, result = state(project, doc)
        if objs is None or getattr(result, "stopped_at", None) is not None:
            titles = [getattr(f, "title", "") for f in result.scene.report.findings][:2]
            rows.append((name, "ANGEHALTEN", "-", f"{result.stopped_at} {titles}"[:140]))
        else:
            kinds = [o.kind for o in objs]
            verdict = (
                "exakt"
                if all(k == "brep" for k in kinds)
                else ("netz" if all(k == "mesh" for k in kinds) else "gemischt")
            )
            codes = sorted(
                {f.code for f in result.scene.report.findings if f.code != "arrange.below_bed"}
            )
            rows.append(
                (name, verdict, f"{kinds}/{[len(o.features) for o in objs]}", ",".join(codes))
            )
    except Exception as error:
        rows.append((name, "FEHLER", "-", f"{type(error).__name__}: {error}"[:120]))
    out(f"{rows[-1][0]:32} {rows[-1][1]:16} {rows[-1][2]:22} {rows[-1][3][:110]}")

out("")
summary = Counter(r[1] for r in rows)
out(f"Zusammenfassung: {dict(summary)}")
converting = [r[0] for r in rows if r[1] == "netz"]
out(f"konvertierende insert_-Pfade: {len(converting)}")
out(f"  {converting}")
halted = [r[0] for r in rows if r[1] == "ANGEHALTEN"]
out(f"angehalten: {halted}")
out("")
out("Konzeptangabe: 35 Bausteine / 31 konvertierende Pfade")
out(
    f"Gemessen:     {len(parts)} Bausteine / {len(converting)} konvertierende insert_-Pfade "
    f"+ {sum(1 for r in rows if r[1].startswith('erzeugt:mesh'))} netzerzeugende create_-Pfade"
)
parts_without_op = [s.name for s in parts if part_ops.op_name(s.name) not in inserts]
out(f"Bausteine ohne insert_-Operation: {parts_without_op}")
