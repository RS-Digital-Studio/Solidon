"""S8b: Wo liegt die Trägerbohrung wirklich, und wohin setzt _at_the_mouth die Buchse?"""

from __future__ import annotations

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.knowledge.parts import ops as part_ops  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.knowledge.profiles import make_profile  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

PROFILE = make_profile("centauri-carbon-2", "petg")
project = new_project("centauri-carbon-2", "petg")
doc = project.document
history = History(doc)
history.apply(
    "Quader",
    [OperationDraft(op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 10.0})],
)
history.apply(
    "Bohrung",
    [OperationDraft(op="drill_brep_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 10.0})],
)
result = evaluate(doc, PROFILE, sources=ProjectSources(project))
source = next(iter(result.scene.objects.values()))
for name, feature in source.features.items():
    if feature.kind == "hole":
        pr.out(f"{name}: {feature.params}  measure_sources={feature.measure_sources}")
solid = source.mesh
for z in (0.05, 0.5, 1.0, 5.0, 9.0, 9.5, 9.95):
    pr.out(f"  z={z}: Bohrung Ø {pr.hole_diameter(solid, (0.0, 0.0), z):.4f}")
pr.out(f"  Material auf der Achse bei z=0.2? {pr.inside(solid, (0.0, 0.0, 0.2))}")
spec = PARTS.get("heatset_m4")
params = REGISTRY.get("insert_heatset_m4").params(at_feature="hole_1", size="M4")
built = spec.fn(spec.params(size="M4")).mesh
anchor, direction = part_ops._anchor(source, params, spec, built)
z_range = f"{built.bounds.minimum[2]:.3f}..{built.bounds.maximum[2]:.3f}"
pr.out(f"  Anker {anchor} Richtung {direction}  Werkzeug-Bounds z {z_range}")
pr.out(f"  Befunde: {sorted({f.code for f in result.scene.report.findings})}")
