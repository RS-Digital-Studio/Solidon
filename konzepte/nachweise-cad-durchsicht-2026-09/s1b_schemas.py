"""S1b: Parameterschemata (Dataclass-Felder) der Ops für den Kundenweg."""

import dataclasses
import _iso  # noqa: F401

from app.core import bootstrap
from app.core.registry import REGISTRY

bootstrap.load_operations()
for op in (
    "create_brep_box", "drill_brep_hole", "drill_hole", "fillet_edges", "chamfer_edges", "shell_exact",
    "hollow_object", "insert_heatset_m4", "countersink_hole", "resize_hole", "slot_hole", "move_feature",
    "rotate_feature", "duplicate_feature", "remove_feature", "plug_hole", "assign_slot", "paint_slot",
    "slots_from_texture", "scale_object", "fit_to_size", "mirror_object", "create_torus", "create_cylinder",
    "sketch_pocket", "sketch_extrude", "draft_faces", "push_face",
):
    try:
        spec = REGISTRY.get(op)
    except Exception as e:  # noqa: BLE001
        print(op, "FEHLT", repr(e)[:80])
        continue
    fields = []
    for f in dataclasses.fields(spec.params):
        d = f.default if f.default is not dataclasses.MISSING else ("<factory>" if f.default_factory is not dataclasses.MISSING else "<PFLICHT>")
        fields.append(f"{f.name}={d!r}")
    print(f"{op} [{spec.category}] requires_kind={getattr(spec, 'requires_kind', None)} applies_to={spec.applies_to} produces={spec.produces} consumes={spec.consumes}")
    print("    ", ", ".join(fields))
