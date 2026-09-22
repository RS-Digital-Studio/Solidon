"""S2: Exakte Spiegelung und Skalierung über den vollen Auswertungsweg."""

import dataclasses
import _iso  # noqa: F401
from app.core import bootstrap

bootstrap.load_operations()

from app.core.knowledge.profiles import make_profile
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project


def probe(creator: str, op: str, params: dict) -> None:
    profile = make_profile("centauri-carbon-2", "petg")
    project = new_project("centauri-carbon-2", "petg")
    doc = project.document
    h = History(doc)
    h.apply("Quader", [OperationDraft(op=creator, params={"width": 40.0, "depth": 30.0, "height": 10.0})])
    r0 = evaluate(doc, profile, sources=ProjectSources(project))
    o0 = next(iter(r0.scene.objects.values()))
    h.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    r1 = evaluate(doc, profile, sources=ProjectSources(project))
    if not r1.scene.objects:
        print(f"{creator} + {op}{params}: ANGEHALTEN bei {r1.stopped_at}")
        for f in r1.scene.report.findings:
            print("   ", f.code, getattr(f, "severity", ""), getattr(f, "title", ""))
        return
    o1 = next(iter(r1.scene.objects.values()))

    def summary(o):
        kinds = {}
        for f in o.features.values():
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        return f"kind={o.kind} features={len(o.features)} {kinds} vol={o.mesh.volume:.3f}"

    print(f"{creator} + {op}{params}:")
    print("   vorher :", summary(o0))
    print("   nachher:", summary(o1))
    codes = [f.code for f in r1.scene.report.findings]
    print("   Befunde:", codes)
    # Flächeninhalte, sofern das Merkmal sie trägt
    for name, o in (("vorher", o0), ("nachher", o1)):
        rows = []
        for f in o.features.values():
            d = dataclasses.asdict(f) if dataclasses.is_dataclass(f) else vars(f)
            area = d.get("area") or (d.get("params") or {}).get("area") if isinstance(d.get("params"), dict) else d.get("area")
            centre = d.get("centre") or d.get("center") or (d.get("params") or {}).get("centre")
            rows.append((f.id, f.kind, area, centre))
        print(f"   {name} Details:", rows[:14])


probe("create_brep_box", "mirror_object", {})
probe("create_box", "mirror_object", {})
probe("create_brep_box", "scale_object", {"factor": 2.0})
probe("create_box", "scale_object", {"factor": 2.0})
