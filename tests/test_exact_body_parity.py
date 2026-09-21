"""Jede registrierte Operation läuft erfolgreich durch Verlauf und Auswertung.

Eingaben, Parameter, Ausgabearten und Ergebnisinvarianten werden ausdrücklich
festgelegt. Gemeinsam gescheiterte Wege gelten nicht als Erfolg. Die erwartete
Körperart stammt niemals aus requires_kind des geprüften Registers.
"""

from __future__ import annotations

import dataclasses
import io
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.registry import REGISTRY, OperationSpec, Registry
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import BaseParams, Feature, OpContext, OpResult, Profile, SceneObject, Source

MESHES = Path(__file__).parent / "data" / "meshes"
# Ausdrückliche Zusagen für beide Darstellungen, unabhängig vom Op-Register.
KEEP = (("mesh", ("mesh",)), ("brep", ("brep",)))
MESH = (("mesh", ("mesh",)), ("brep", ("mesh",)))
EXACT = (("brep", ("brep",)),)
MESH_ONLY = (("mesh", ("mesh",)),)
CREATE_MESH = (("none", ("mesh",)),)
CREATE_EXACT = (("none", ("brep",)),)


@dataclasses.dataclass(frozen=True)
class Case:
    """Ein erfolgreicher Kundenauftrag mit einer vorab festgelegten Erwartung."""

    name: str
    source: str
    params: dict[str, Any]
    variants: tuple[tuple[str, tuple[str, ...]], ...]
    invariant: str
    expected: Any


def _circle(diameter: float) -> str:
    """Eine geschlossene Kreiszeichnung als gespeicherter Parameter."""
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import circle

    return sketch_to_text(circle(diameter))


def _rectangle(width: float, height: float) -> str:
    """Eine geschlossene Rechteckzeichnung als gespeicherter Parameter."""
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    return sketch_to_text(rectangle(width, height))


# Quellen: test_brep, test_prepare, test_features, test_missing_ops und die
# jeweiligen Familientests. Jede Zeile nennt einen konkreten gültigen Auftrag.
CASES = [
    Case(
        "align_to_feature",
        "alignment",
        {"feature": "top", "target": "obj_2:top"},
        MESH,
        "aligned",
        None,
    ),
    Case(
        "apply_texture",
        "box",
        {
            "pattern": "knurl_diamond",
            "width": 10.0,
            "height": 8.0,
            "pitch": 3.0,
            "depth": 0.8,
            "z": 10.0,
            "mode": "raised",
        },
        MESH,
        "greater",
        3200.0,
    ),
    Case(
        "arrange_bed",
        "overlapping",
        {"spacing": 5.0, "plates": 1},
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
        "arranged",
        5.0,
    ),
    Case(
        "assign_slot",
        "box",
        {"slot": 2, "name": "Prüfrot", "colour": "#ff0000", "material_type": "PLA"},
        KEEP,
        "assigned",
        2,
    ),
    Case("bead_edges", "box", {"radius": 0.8, "edges": "vertical"}, MESH, "greater", 3200.0),
    Case("blend_union", "overlapping", {"radius": 1.0, "grid": 1.0}, MESH, "greater", 4800.0),
    Case("brep_to_mesh", "box", {"deflection": 0.05}, (("brep", ("mesh",)),), "volume", 3200.0),
    Case("chamfer_edges", "box", {"distance": 1.0, "edges": "vertical"}, KEEP, "volume", 3180.0),
    Case(
        "check_collisions",
        "overlapping",
        {"clearance": 0.0},
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
        "collision",
        None,
    ),
    Case(
        "check_join_path",
        "separated",
        {"axis": "z", "distance": 20.0, "steps": 4},
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
        "join_clear",
        None,
    ),
    Case("clear_filament", "coloured", {}, KEEP, "cleared", None),
    Case("compensate_first_layer", "box", {"height": 0.6, "amount": 0.2}, MESH, "less", 3200.0),
    Case(
        "countersink_hole",
        "hole",
        {"diameter": 10.0, "x": -8.0, "y": 0.0, "z": 10.0, "axis": "z"},
        KEEP,
        "less",
        12000.0 - 90.0 * math.pi,
    ),
    Case(
        "create_box",
        "none",
        {"width": 20.0, "depth": 16.0, "height": 10.0},
        CREATE_MESH,
        "volume",
        3200.0,
    ),
    Case(
        "create_brep_box",
        "none",
        {"width": 20.0, "depth": 16.0, "height": 10.0},
        CREATE_EXACT,
        "volume",
        3200.0,
    ),
    Case(
        "create_brep_cylinder",
        "none",
        {"diameter": 10.0, "height": 12.0},
        CREATE_EXACT,
        "volume",
        300.0 * math.pi,
    ),
    Case(
        "create_cone",
        "none",
        {"bottom_diameter": 20.0, "top_diameter": 10.0, "height": 12.0, "segments": 96},
        CREATE_MESH,
        "volume",
        700.0 * math.pi,
    ),
    Case(
        "create_cylinder",
        "none",
        {"diameter": 10.0, "height": 12.0, "segments": 96},
        CREATE_MESH,
        "volume",
        300.0 * math.pi,
    ),
    Case(
        "create_label", "none", {"text": "H", "size": 8.0, "depth": 1.0}, CREATE_MESH, "height", 1.0
    ),
    Case(
        "create_lid",
        "housing",
        {"thickness": 2.4, "collar": 4.0},
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "mesh"))),
        "lid",
        (60.0, 40.0),
    ),
    Case(
        "create_organizer",
        "none",
        {"width": 60.0, "depth": 50.0, "height": 20.0, "wall": 2.0, "floor": 3.0, "radius": 3.0},
        CREATE_MESH,
        "organizer",
        (60.0, 50.0, 20.0),
    ),
    Case(
        "create_profile_clamp_set",
        "none",
        {
            "profile_shape": "round",
            "diameter": 16.0,
            "clamp_material": "petg",
            "liner_material": "tpu-95a",
            "depth": 20.0,
        },
        (("none", ("mesh",) * 4),),
        "clamp_roles",
        None,
    ),
    Case(
        "create_seal",
        "cube",
        {
            "path_sketch": _circle(10.0),
            "groove_width": 2.0,
            "groove_depth": 2.0,
            "gasket_width": 1.6,
            "protrusion": 0.4,
            "body_material": "petg",
            "gasket_material": "tpu-95a",
        },
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "mesh"))),
        "seal",
        None,
    ),
    Case(
        "create_sphere",
        "none",
        {"diameter": 10.0, "segments": 64},
        CREATE_MESH,
        "volume",
        500.0 * math.pi / 3.0,
    ),
    Case(
        "create_torus",
        "none",
        {"outer_diameter": 24.0, "tube_diameter": 4.0, "segments": 96},
        CREATE_MESH,
        "volume",
        80.0 * math.pi**2,
    ),
    Case(
        "cut_away", "box", {"axis": "z", "position": 5.0, "keep": "below"}, MESH, "volume", 1600.0
    ),
    Case("decimate_mesh", "sphere", {"triangles": 500}, MESH, "decimated", 500),
    Case("delete_object", "box", {}, (("mesh", ()), ("brep", ())), "deleted", None),
    Case(
        "detect_region",
        "unrecognised_hole",
        {"radius": 15.0},
        MESH_ONLY,
        "detected_hole",
        6.0,
    ),
    Case(
        "displace_image",
        "fine_box",
        {
            "source": "image",
            "strength": 1.0,
            "middle": 0.0,
            "projection": "face",
            "at_feature": "top",
        },
        MESH_ONLY,
        "greater",
        3200.0,
    ),
    Case("draft_faces", "box", {"angle": 3.0}, KEEP, "draft", None),
    Case(
        "drill_brep_hole",
        "box",
        {"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 10.0, "compensate": False},
        EXACT,
        "volume",
        3200.0 - 40.0 * math.pi,
    ),
    Case(
        "drill_hole",
        "box",
        {"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 10.0, "compensate": False},
        MESH,
        "volume",
        3200.0 - 40.0 * math.pi,
    ),
    Case(
        "duplicate_feature",
        "hole",
        {"at_feature": "hole", "x": 16.0, "y": 0.0, "z": 0.0},
        KEEP,
        "hole_count",
        2,
    ),
    Case(
        "duplicate_object",
        "box",
        {"count": 3},
        (("mesh", ("mesh",) * 3), ("brep", ("brep",) * 3)),
        "copies",
        3200.0,
    ),
    Case(
        "field_cut",
        "cube",
        {
            "region_sketch": _rectangle(18.0, 18.0),
            "diameter": 2.0,
            "spacing": 6.0,
            "margin": 1.0,
            "web": 1.0,
            "depth": 4.0,
        },
        KEEP,
        "field",
        None,
    ),
    Case(
        "fillet_edges",
        "box",
        {"radius": 1.0, "edges": "vertical"},
        KEEP,
        "volume",
        3200.0 - 40.0 + 10.0 * math.pi,
    ),
    Case("fit_to_size", "box", {"largest": 40.0}, KEEP, "volume", 25600.0),
    Case(
        "hollow_object", "box", {"wall": 2.0, "open_top": True, "vents": 0}, MESH, "hollow", 1664.0
    ),
    Case("intersect_objects", "overlapping", {}, KEEP, "volume", 1600.0),
    Case(
        "label_text",
        "box",
        {"text": "H", "size": 6.0, "depth": 0.8, "z": 10.0, "mode": "raised"},
        MESH,
        "greater",
        3200.0,
    ),
    Case(
        "lattice_fill",
        "closed_cavity",
        {"structure": "cubic", "cell": 8.0, "wall": 1.0},
        MESH,
        "greater",
        3904.0,
    ),
    Case(
        "load",
        "load_mesh",
        {"source": "mesh", "unit": "mm", "coordinates": "legacy_raw"},
        CREATE_MESH,
        "volume",
        8000.0,
    ),
    Case(
        "load_outline",
        "outline",
        {"source": "outline", "height": 3.0, "width": 20.0},
        CREATE_MESH,
        "volume",
        900.0,
    ),
    Case("load_step", "load_step", {"source": "step"}, CREATE_EXACT, "volume", 3200.0),
    Case(
        "mirror_object",
        "shifted",
        {"axis": "x", "about": "origin"},
        KEEP,
        "centre",
        (-25.0, 0.0, 25.0),
    ),
    Case(
        "move_feature",
        "hole",
        {"at_feature": "hole", "x": 0.0, "y": 0.0, "z": 5.0},
        KEEP,
        "hole_x",
        0.0,
    ),
    Case(
        "orient_for_print",
        "tilted",
        {"thorough": False, "candidates": 12, "arrange": False},
        KEEP,
        "on_bed",
        None,
    ),
    Case(
        "paint_slot",
        "box",
        {
            "slot": 3,
            "at_feature": "top",
            "colour": "#00ff00",
            "name": "Prüfgrün",
            "material_type": "PLA",
        },
        KEEP,
        "painted",
        3,
    ),
    Case(
        "pattern",
        "box",
        {"kind": "linear", "count": 3, "spacing": 30.0, "dx": 1.0, "dy": 0.0, "dz": 0.0},
        (("mesh", ("mesh",) * 3), ("brep", ("brep",) * 3)),
        "pattern",
        [0.0, 30.0, 60.0],
    ),
    Case("place_on_bed", "shifted", {}, KEEP, "on_bed", None),
    Case(
        "place_group_on_bed",
        "shifted_group",
        {},
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
        "group_on_bed",
        None,
    ),
    Case(
        "plug_hole",
        "hole",
        {
            "at_feature": "hole",
            "diameter": 6.0,
            "x": -8.0,
            "y": 0.0,
            "z": 10.0,
            "compensate": False,
        },
        KEEP,
        "volume",
        12000.0,
    ),
    Case(
        "pose_armature",
        "box",
        {"armature": "one_bone", "pose": "quarter_turn"},
        MESH,
        "posed",
        None,
    ),
    Case("push_face", "box", {"face": "top", "distance": 2.0}, KEEP, "volume", 3840.0),
    Case("remesh_mesh", "box", {"edge": 4.0}, MESH, "refined", 3200.0),
    Case("remesh_uniform", "box", {"edge": 4.0, "deviation": 0.0}, MESH, "refined", 3200.0),
    Case(
        "remove_feature",
        "hole",
        {"at_feature": "hole", "sections": "chain"},
        KEEP,
        "volume",
        12000.0,
    ),
    Case("rename_object", "box", {"name": "Geprüfter Körper"}, KEEP, "name", "Geprüfter Körper"),
    Case(
        "repair",
        "broken_box",
        {"fill_holes": True, "weld": True, "normals": True},
        MESH_ONLY,
        "repaired",
        3200.0,
    ),
    Case(
        "replace_profile_liners",
        "clamp_set",
        {
            "profile_shape": "round",
            "diameter": 14.0,
            "clamp_material": "petg",
            "liner_material": "tpu-95a",
            "minimum_wall": 2.0,
        },
        (("mesh", ("mesh",) * 4),),
        "replacement",
        None,
    ),
    Case(
        "resize_feature", "pin", {"at_feature": "pin", "diameter": 8.0}, MESH, "pin_diameter", 8.0
    ),
    Case(
        "resize_hole",
        "hole",
        {"at_feature": "hole", "diameter": 8.0, "compensate": False},
        KEEP,
        "hole_diameter",
        8.0,
    ),
    Case(
        "rotate_feature",
        "hole",
        {"at_feature": "hole", "axis": "y", "angle": 20.0},
        KEEP,
        "hole_tilted",
        None,
    ),
    Case(
        "rotate_object",
        "box",
        {"axis": "z", "angle": 90.0, "about": "origin"},
        KEEP,
        "size",
        (16.0, 20.0, 10.0),
    ),
    Case("scale_object", "box", {"factor": 2.0}, KEEP, "volume", 25600.0),
    Case(
        "screw_lid",
        "jar",
        {"height": 8.0, "pitch": 3.0, "thickness": 2.4, "wall": 2.4},
        (("mesh", ("mesh", "mesh")), ("brep", ("mesh", "mesh"))),
        "screw_cap",
        None,
    ),
    Case("sculpt_strokes", "sphere", {"strokes": "bump"}, MESH, "bump", None),
    Case("set_material", "box", {"material": "tpu-95a"}, KEEP, "material", "tpu-95a"),
    Case("shell_exact", "box", {"wall": 2.0}, EXACT, "less", 3200.0),
    Case(
        "sketch_extrude",
        "none",
        {"shape": "rectangle", "length": 20.0, "width": 10.0, "height": 6.0},
        CREATE_EXACT,
        "volume",
        1200.0,
    ),
    Case(
        "sketch_loft",
        "none",
        {"shape": "rectangle", "length": 20.0, "width": 10.0, "height": 12.0, "top_scale": 0.5},
        CREATE_EXACT,
        "volume",
        1400.0,
    ),
    Case(
        "sketch_pocket",
        "box",
        {"shape": "rectangle", "length": 8.0, "width": 6.0, "depth": 3.0, "z": 10.0},
        KEEP,
        "volume",
        3056.0,
    ),
    Case(
        "sketch_revolve",
        "none",
        {"shape": "rectangle", "length": 4.0, "width": 6.0, "offset": 10.0, "angle": 360.0},
        CREATE_EXACT,
        "volume",
        576.0 * math.pi,
    ),
    Case(
        "sketch_sweep",
        "none",
        {
            "shape": "circle",
            "length": 4.0,
            "width": 4.0,
            "along": "arc",
            "bend_radius": 12.0,
            "bend_angle": 90.0,
        },
        CREATE_EXACT,
        "volume",
        24.0 * math.pi**2,
    ),
    Case(
        "slot_hole",
        "hole",
        {"at_feature": "hole", "slot_length": 12.0, "slot_angle": 0.0},
        KEEP,
        "slot",
        12.0,
    ),
    Case("slots_from_texture", "textured", {"filaments": 2}, MESH_ONLY, "texture_slots", 2),
    Case("smooth_mesh", "sphere", {"iterations": 2}, MESH, "smoothed", None),
    Case(
        "split_bodies",
        "disconnected",
        {"count": 2, "keep_tiny": True},
        (("mesh", ("mesh", "mesh")), ("brep", ("mesh", "mesh"))),
        "split",
        6400.0,
    ),
    Case(
        "split_line",
        "box",
        {"position": 5.0, "pins": 0, "normal_x": 0.0, "normal_y": 0.0, "normal_z": 1.0},
        (("mesh", ("mesh", "mesh")), ("brep", ("mesh", "mesh"))),
        "split",
        3200.0,
    ),
    Case(
        "split_pinned",
        "box",
        {"axis": "z", "position": 5.0, "pins": 2, "diameter": 2.0, "play": 0.25},
        (("mesh", ("mesh", "mesh")), ("brep", ("mesh", "mesh"))),
        "pins",
        None,
    ),
    Case("subdivide_surface", "box", {"edge": 4.0, "angle": 30.0}, MESH, "refined", 3200.0),
    Case("subtract_objects", "overlapping", {}, KEEP, "volume", 1600.0),
    Case(
        "test_piece",
        "box",
        {"size": 8.0, "x": 0.0, "y": 0.0, "z": 5.0, "on_bed": True},
        MESH,
        "volume",
        512.0,
    ),
    Case("thicken", "open_surface", {"thickness": 2.0}, MESH_ONLY, "volume", 640.0),
    Case(
        "thread_exact",
        "none",
        {"diameter": 10.0, "pitch": 1.5, "length": 8.0},
        CREATE_EXACT,
        "thread",
        (10.0, 1.5, 8.0),
    ),
    Case(
        "translate_object",
        "box",
        {"dx": 7.0, "dy": -3.0, "dz": 2.0},
        KEEP,
        "centre",
        (7.0, -3.0, 7.0),
    ),
    Case("union_objects", "overlapping", {}, KEEP, "volume", 4800.0),
]

# Fachmaße und Wirkung je Baustein, ausdrücklich statt beliebiger Feldvorgaben.
# Die Gesamthöhe schließt Füße, Zapfen und bei der Einlage den Flansch ein.
PART_CASES = {
    "barrel_hinge": ({"pin": 4.0, "width": 24.0, "reach": 12.0, "wall": 2.5}, "greater", None),
    "bearing_seat": ({"size": "608", "removable": False}, "less", None),
    "cable_clip": ({"size": "cable-5", "width": 8.0, "wall": 2.0}, "greater", None),
    "cable_gland": ({"size": "cable-5", "wall": 3.0, "strain_relief": False}, "less", None),
    "dowel": ({"diameter": 4.0, "length": 8.0, "kind": "pin", "chamfer": 0.6}, "greater", None),
    "fit_ladder": (
        {"diameter": 6.0, "steps": 3, "height": 8.0, "first": 0.1, "step": 0.05},
        "greater",
        8.0 + 3.0,
    ),
    "foot": ({"kind": "foot", "diameter": 10.0, "height": 3.0}, "greater", None),
    "gusset": ({"legs": 12.0, "thickness": 2.0, "wall": 2.0}, "greater", None),
    "heatset_m4": ({"size": "M3", "lead_in": True, "extra_depth": 0.5}, "less", None),
    "hinge_eye": ({"pin": 3.0, "width": 8.0, "reach": 8.0, "wall": 2.0}, "greater", None),
    "keyhole": ({"size": "M4", "drop": 8.0, "depth": 4.0, "head_room": 2.5}, "less", None),
    "latch": ({"width": 6.0, "depth": 1.0, "height": 3.0, "negative": False}, "greater", None),
    "living_hinge": (
        {"width": 30.0, "leaf": 15.0, "thickness": 2.0, "film": 0.4, "gap": 1.5},
        "greater",
        None,
    ),
    "magnet_pocket": ({"size": "8x3", "cover": 0.0, "press_lip": False}, "less", None),
    "nut_trap": ({"size": "M3", "direction": "bottom", "screw_hole": True}, "less", None),
    "organizer_divider": ({"length": 30.0, "height": 15.0, "thickness": 3.0}, "greater", 15.0),
    "organizer_foot": (
        {"diameter": 18.0, "height": 11.0, "pin_diameter": 13.0, "pin_length": 8.0},
        "greater",
        11.0 + 8.0,
    ),
    "organizer_rim": (
        {"width": 40.0, "depth": 30.0, "height": 3.0, "thickness": 3.0, "radius": 4.0},
        "greater",
        3.0,
    ),
    "organizer_tray": (
        {"width": 40.0, "depth": 30.0, "height": 15.0, "wall": 3.0, "floor": 3.0, "radius": 4.0},
        "greater",
        15.0,
    ),
    "overhang_fan": (
        {"first": 20.0, "step": 10.0, "steps": 3, "width": 8.0, "length": 15.0},
        "greater",
        None,
    ),
    "pegboard_hook": (
        {"system": "skadis", "count": 1, "steps": 1, "upright": False, "latch": True},
        "greater",
        None,
    ),
    "printed_nut": ({"size": "M5"}, "greater", None),
    "printed_screw": ({"size": "M5", "length": 12.0, "countersunk": False}, "greater", None),
    "printed_thread": ({"size": "M6", "length": 8.0, "internal": False}, "greater", None),
    "profile_clamp_liner": (
        {"counter_sketch": _circle(16.0), "depth": 20.0, "liner_thickness": 2.0, "half": "lower"},
        "greater",
        20.0 - 2.0 + 1.5,
    ),
    "profile_clamp_shell": (
        {"seat_sketch": _circle(20.25), "depth": 20.0, "wall": 4.0, "half": "lower"},
        "greater",
        20.0,
    ),
    "profile_tongue": ({"size": "2020", "length": 20.0}, "greater", None),
    "rib": (
        {"length": 20.0, "height": 10.0, "wall": 2.0, "thickness": 2.0, "fillet": 1.0},
        "greater",
        None,
    ),
    "screw_hole": ({"size": "M3", "depth": 8.0, "countersink": True}, "less", None),
    "seal_gasket": (
        {"path_sketch": _circle(20.0), "section": "rectangle", "width": 2.6, "height": 2.4},
        "greater",
        2.4,
    ),
    "seal_groove": ({"path_sketch": _circle(20.0), "width": 3.0, "depth": 2.0}, "less", None),
    "snap_connector": ({"diameter": 6.0, "length": 9.0, "kind": "pin"}, "greater", None),
    "snap_fit": ({"width": 8.0, "length": 16.0, "thickness": 1.6, "hook": 1.2}, "greater", None),
    "wall_ladder": (
        {"extrusion": 0.42, "steps": 3, "height": 15.0, "length": 25.0},
        "greater",
        15.0 + 2.0,
    ),
    "wall_mount": (
        {"width": 30.0, "height": 25.0, "thickness": 3.0, "size": "M4", "holes": 2, "lip": 12.0},
        "greater",
        None,
    ),
}
STANDALONE = (
    "fit_ladder",
    "organizer_divider",
    "organizer_foot",
    "organizer_rim",
    "organizer_tray",
    "overhang_fan",
    "profile_clamp_liner",
    "profile_clamp_shell",
    "seal_gasket",
    "wall_ladder",
)
#: Die Bausteine, die an einem exakten Träger exakt bauen (P2.7) — die Abnahme je
#: Gruppe ist der Wechsel ihrer Zeilen von ``MESH`` nach ``KEEP``.
EXACT_PARTS = frozenset(
    {
        "screw_hole",
        "heatset_m4",
        "nut_trap",
        "printed_thread",
        "printed_screw",
        "printed_nut",
        "barrel_hinge",
        "bearing_seat",
        "dowel",
        "hinge_eye",
        "latch",
        "living_hinge",
        "snap_connector",
        "snap_fit",
        "foot",
        "keyhole",
        "magnet_pocket",
        "pegboard_hook",
        "wall_mount",
        "profile_clamp_liner",
        "profile_clamp_shell",
        "rib",
        "gusset",
        "profile_tongue",
        "cable_gland",
        "cable_clip",
        "organizer_tray",
        "organizer_divider",
        "organizer_rim",
        "organizer_foot",
    }
)
for _part, (_dimensions, _effect, _height) in PART_CASES.items():
    CASES.append(
        Case(
            f"insert_{_part}",
            "host",
            {**_dimensions, "x": 0.0, "y": 0.0, "z": 10.0, "nx": 0.0, "ny": 0.0, "nz": 1.0},
            KEEP if _part in EXACT_PARTS else MESH,
            _effect,
            100000.0,
        )
    )
for _part in STANDALONE:
    _dimensions, _effect, _height = PART_CASES[_part]
    CASES.append(
        Case(
            f"create_{_part}",
            "none",
            dict(_dimensions),
            CREATE_MESH,
            "height" if _height is not None else "overhang",
            _height,
        )
    )
CASE_BY_NAME = {case.name: case for case in CASES}


def _native_box(width=20.0, depth=16.0, height=10.0, shift=(0.0, 0.0, 0.0)):
    """Analytischer Eingang, unabhängig von der registrierten Erzeugeroperation."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from app.core.brep.kernel import Solid

    return Solid(
        BRepPrimAPI_MakeBox(
            gp_Pnt(-width / 2 + shift[0], -depth / 2 + shift[1], shift[2]), width, depth, height
        ).Shape()
    )


def _native_cylinder(radius, height, shift=(0.0, 0.0, 0.0)):
    """Ein analytischer Zylinder mit seinem Boden an der angegebenen Stelle."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.kernel import Solid

    return Solid(
        BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*shift), gp_Dir(0, 0, 1)), radius, height).Shape()
    )


def _native_difference(outer, cutter):
    """Der Testkörper entsteht aus angegebenen Volumen, nicht aus der geprüften Op."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    from app.core.brep.kernel import Solid

    return Solid(BRepAlgoAPI_Cut(outer.shape, cutter.shape).Shape())


def _object(body, kind: str, index: int = 1, *, recognise: bool = True) -> SceneObject:
    """Beide Darstellungen derselben Eingabe mit stabil benannten Zielmerkmalen."""
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    mesh = body if kind == "brep" else as_mesh_data(body)
    found = dict(features_of(body) if kind == "brep" else detect(mesh)) if recognise else {}
    features = {}
    for key, feature in found.items():
        name = key
        if feature.kind == "hole":
            name = "hole"
        elif feature.kind == "pin":
            name = "pin"
        elif feature.kind == "face":
            normal = feature.params.get("normal", ())
            if len(normal) == 3 and normal[2] > 0.99:
                name = "top"
        features[name] = dataclasses.replace(feature, id=name)
    return SceneObject(
        id=f"obj_{index}", name=f"Prüfkörper {index}", mesh=mesh, kind=kind, features=features
    )


def _add_source(
    project: Project, identifier: str, suffix: str, payload: bytes, kind="import"
) -> None:
    """Die Datei reist über denselben Quellenzugriff wie ein geöffnetes Projekt."""
    import hashlib

    project.sources[identifier] = payload
    project.document.sources[identifier] = Source(
        id=identifier,
        kind=kind,
        path=f"sources/{identifier}{suffix}",
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _inputs(case: Case, kind: str, project: Project, profile: Profile) -> list[SceneObject]:
    """Die in der vollständigen Falltabelle benannten, gezielt gebauten Eingaben."""
    source = case.source
    if source in {"none", "load_mesh", "load_step", "outline"}:
        if source == "load_mesh":
            _add_source(project, "mesh", ".stl", (MESHES / "cube_clean.stl").read_bytes())
        elif source == "load_step":
            from app.core.brep.step import write

            _add_source(project, "step", ".step", write(_native_box()))
        elif source == "outline":
            _add_source(
                project,
                "outline",
                ".svg",
                b'<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
                b'viewBox="0 0 20 20"><path d="M0,0 L20,0 L20,20 L0,20 Z '
                b'M5,5 L5,15 L15,15 L15,5 Z"/></svg>',
            )
        return []
    if source == "clamp_set":
        from app.core.scene.cancel import NeverCancelled
        from app.core.types import Scene

        spec = REGISTRY.get("create_profile_clamp_set")
        made = spec.fn(
            OpContext(
                Scene(),
                [],
                spec.params(clamp_material="petg", liner_material="tpu-95a", depth=20.0),
                profile,
                "fine",
                None,
                lambda *_: None,
                _unexpected_question,
                NeverCancelled(),
            )
        )
        return [
            dataclasses.replace(entry, id=f"obj_{i}") for i, entry in enumerate(made.outputs, 1)
        ]
    if source == "cube":
        return [_object(_native_box(20.0, 20.0, 20.0, (0.0, 0.0, -10.0)), kind)]
    if source == "host":
        return [_object(_native_box(100.0, 100.0, 10.0), kind)]
    if source == "shifted":
        return [_object(_native_box(shift=(25.0, 0.0, 20.0)), kind)]
    if source == "shifted_group":
        return [
            _object(_native_box(shift=(25.0, 0.0, -8.0)), kind),
            _object(_native_box(shift=(-15.0, 3.0, 5.0)), kind, 2),
        ]
    if source in {"overlapping", "separated", "alignment"}:
        distance = 10.0 if source == "overlapping" else 40.0
        return [
            _object(_native_box(), kind),
            _object(_native_box(shift=(distance, 0.0, 0.0)), kind, 2),
        ]
    if source in {"hole", "unrecognised_hole"}:
        body = _native_difference(
            _native_box(40.0, 30.0, 10.0), _native_cylinder(3.0, 12.0, (-8.0, 0.0, -1.0))
        )
        return [_object(body, kind, recognise=source != "unrecognised_hole")]
    if source == "housing":
        body = _native_difference(
            _native_box(60.0, 40.0, 30.0), _native_box(54.0, 34.0, 28.0, (0.0, 0.0, 3.0))
        )
        return [_object(body, kind)]
    if source == "closed_cavity":
        body = _native_difference(
            _native_box(20.0, 20.0, 20.0), _native_box(16.0, 16.0, 16.0, (0.0, 0.0, 2.0))
        )
        return [_object(body, kind)]
    if source == "pin":
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

        from app.core.brep.kernel import Solid

        body = Solid(
            BRepAlgoAPI_Fuse(
                _native_box(40.0, 30.0, 10.0).shape,
                _native_cylinder(3.0, 6.0, (0.0, 0.0, 10.0)).shape,
            ).Shape()
        )
        return [_object(body, kind)]
    if source == "jar":
        body = _native_difference(
            _native_cylinder(20.0, 40.0), _native_cylinder(17.0, 40.0, (0.0, 0.0, 3.0))
        )
        return [_object(body, kind)]
    if source == "sphere":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere

        from app.core.brep.kernel import Solid

        if kind == "brep":
            return [_object(Solid(BRepPrimAPI_MakeSphere(10.0).Shape()), kind)]
        return [
            SceneObject(
                "obj_1",
                "Kugel",
                MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=10.0)),
            )
        ]
    if source == "disconnected":
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound

        from app.core.brep.kernel import Solid

        compound, builder = TopoDS_Compound(), BRep_Builder()
        builder.MakeCompound(compound)
        builder.Add(compound, _native_box().shape)
        builder.Add(compound, _native_box(shift=(40.0, 0.0, 0.0)).shape)
        return [_object(Solid(compound), kind)]
    if source == "tilted":
        from app.core.brep import edit
        from app.core.geom.transform import rotation

        return [_object(edit.transformed(_native_box(), rotation("x", 35.0)), kind)]
    entry = _object(_native_box(), kind)
    if source == "box":
        return [entry]
    raw = as_mesh_data(entry.mesh).raw.copy()
    if source == "broken_box":
        raw.update_faces(np.arange(len(raw.faces)) != 0)
        return [dataclasses.replace(entry, mesh=MeshData.of(raw), features={})]
    if source == "open_surface":
        raw.update_faces(raw.face_normals[:, 2] > 0.99)
        raw.remove_unreferenced_vertices()
        return [dataclasses.replace(entry, mesh=MeshData.of(raw), features={})]
    if source == "coloured":
        from app.core.geom.attributes import with_slots
        from app.core.types import MaterialSlot

        return [
            dataclasses.replace(
                entry,
                mesh=with_slots(entry.mesh, (2,) * entry.mesh.triangle_count),
                material_slots=[
                    MaterialSlot(index=2, name="Rot", colour="#ff0000", material_type="PLA")
                ],
            )
        ]
    if source == "fine_box":
        from PIL import Image

        raw = raw.subdivide().subdivide().subdivide()
        payload = io.BytesIO()
        # Ein Verlauf trägt echte Höhen; ein einfarbiges Bild bedeutet im
        # Reliefvertrag ausdrücklich Höhe null.
        Image.fromarray(np.tile(np.linspace(0, 255, 8, dtype=np.uint8), (8, 1))).save(
            payload, format="PNG"
        )
        _add_source(project, "image", ".png", payload.getvalue(), "image")
        top = Feature(
            "top",
            "face",
            "detected",
            params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 10.0), "area": 320.0},
            face_indices=tuple(int(i) for i in np.flatnonzero(raw.face_normals[:, 2] > 0.99)),
        )
        return [dataclasses.replace(entry, mesh=MeshData.of(raw), features={"top": top})]
    if source == "textured":
        raw = raw.subdivide().subdivide()
        colours = np.zeros((len(raw.faces), 4), dtype=np.uint8)
        colours[:, 3] = 255
        colours[raw.triangles_center[:, 0] < 0, 0] = 255
        colours[raw.triangles_center[:, 0] >= 0, 2] = 255
        raw.visual.face_colors = colours
        return [dataclasses.replace(entry, mesh=MeshData.of(raw), features={})]
    raise AssertionError(f"Die Quelle {source!r} hat keinen ausdrücklichen Aufbau.")


def _unexpected_question(question: str, choices: list[str]) -> str:
    """Ein gültiger vorbereiteter Fall enthält alle nötigen Entscheidungen."""
    pytest.fail(f"Unerwartete Rückfrage: {question}; Antworten: {choices}")


def _parameters(case: Case, inputs: list[SceneObject]) -> dict[str, Any]:
    """Nur ausdrücklich bezeichnete strukturierte Parameter serialisieren."""
    params = dict(case.params)
    if case.name == "detect_region":
        raw = as_mesh_data(inputs[0].mesh).raw
        # Alle Eckpunkte liegen auf dem bekannten Bohrungsradius. Der Klick
        # trifft ein echtes Wanddreieck und nicht die ideale Zylinderfläche.
        radial = np.linalg.norm(raw.triangles[:, :, :2] - (-8.0, 0.0), axis=2)
        wall = np.flatnonzero(np.all(np.isclose(radial, 3.0, atol=1e-5), axis=1))
        assert len(wall) > 0
        face = int(wall[0])
        point, normal = raw.triangles_center[face], raw.face_normals[face]
        params.update(
            x=float(point[0]),
            y=float(point[1]),
            z=float(point[2]),
            nx=float(normal[0]),
            ny=float(normal[1]),
            nz=float(normal[2]),
            seed_face=face,
        )
    if case.name == "pose_armature":
        from app.core.geom.pose import armature_to_text, pose_to_text
        from app.core.types import Bone, Pose

        params["armature"] = armature_to_text([Bone("root", (0.0, 0.0, 0.0), (0.0, 0.0, 10.0))])
        params["pose"] = pose_to_text([Pose("root", (0.0, 0.0, 90.0))])
    if case.name == "sculpt_strokes":
        from app.core.geom.sculpt import strokes_to_text
        from app.core.types import Stroke

        params["strokes"] = strokes_to_text([Stroke((10.0, 0.0, 0.0), (1.0, 0.0, 0.0), 4.0, 1.0)])
    return params


def _holes(entry: SceneObject) -> list[Feature]:
    """Unabhängige Erkennung prüft die fertig ausgewertete Geometrie."""
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import detect

    found = (
        features_of(entry.mesh)
        if isinstance(entry.mesh, Solid)
        else detect(as_mesh_data(entry.mesh))
    )
    return [feature for feature in found.values() if feature.kind == "hole"]


def _assert_invariant(
    case: Case, outputs: list[SceneObject], inputs: list[SceneObject], result
) -> None:
    """Jede Tabellenzeile muss ihre eigene, nicht aus dem Register gelesene Zusage einlösen."""
    rule, expected = case.invariant, case.expected
    if rule == "deleted":
        assert not outputs and not result.scene.objects
        return
    first = outputs[0]
    mesh = as_mesh_data(first.mesh)
    volume = first.mesh.volume
    if rule == "volume":
        tolerance = max(abs(expected) * 0.004, 0.01)
        if len(inputs) == 1 and as_mesh_data(inputs[0].mesh).is_watertight:
            difference = abs(expected - inputs[0].mesh.volume)
            if difference > 1e-5:
                # Auch ein kleiner Abtrag muss außerhalb der Toleranz liegen:
                # Der unveränderte Quader darf keine Verrundung bestehen.
                tolerance = min(tolerance, difference / 4)
        assert volume == pytest.approx(expected, rel=0.0, abs=tolerance)
    elif rule == "greater":
        assert volume > expected + 0.1
        if case.name == "lattice_fill":
            assert volume < 8000.0
    elif rule == "less":
        assert 0.0 < volume < expected - 0.1
    elif rule == "height":
        assert first.mesh.bounds.size[2] == pytest.approx(expected, abs=0.03)
    elif rule == "size":
        assert first.mesh.bounds.size == pytest.approx(expected, abs=1e-5)
    elif rule == "centre":
        assert first.mesh.bounds.centre == pytest.approx(expected, abs=1e-5)
        assert volume == pytest.approx(3200.0, rel=1e-6)
    elif rule == "copies":
        assert all(entry.mesh.volume == pytest.approx(expected, rel=1e-6) for entry in outputs)
    elif rule == "pattern":
        assert sorted(entry.mesh.bounds.centre[0] for entry in outputs) == pytest.approx(expected)
    elif rule == "on_bed":
        assert first.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
        assert volume == pytest.approx(3200.0, rel=1e-6)
    elif rule == "group_on_bed":
        assert [entry.mesh.bounds.minimum[2] for entry in outputs] == pytest.approx((0.0, 13.0))
        for original, placed in zip(inputs, outputs, strict=True):
            assert placed.mesh.volume == pytest.approx(3200.0, rel=1e-6)
            for key, feature in original.features.items():
                current = placed.features[key]
                assert current.kind == feature.kind
                assert np.subtract(
                    current.params["centre"], feature.params["centre"]
                ) == pytest.approx((0.0, 0.0, 8.0), abs=1e-6)
                assert current.params["area"] == pytest.approx(feature.params["area"], abs=1e-6)
                assert current.params["normal"] == pytest.approx(feature.params["normal"], abs=1e-6)
            assert np.subtract(
                placed.mesh.bounds.centre, original.mesh.bounds.centre
            ) == pytest.approx((0.0, 0.0, 8.0), abs=1e-6)
    elif rule == "arranged":
        a, b = [entry.mesh.bounds for entry in outputs]
        assert (
            a.maximum[0] + expected <= b.minimum[0] + 1e-5
            or b.maximum[0] + expected <= a.minimum[0] + 1e-5
            or a.maximum[1] + expected <= b.minimum[1] + 1e-5
            or b.maximum[1] + expected <= a.minimum[1] + 1e-5
        )
        assert all(
            entry.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6) for entry in outputs
        )
    elif rule == "aligned":
        assert first.mesh.bounds.centre[:2] == pytest.approx((40.0, 0.0), abs=1e-5)
    elif rule == "collision":
        findings = [
            finding
            for finding in result.scene.report.findings
            if finding.code == "arrange.collision"
        ]
        assert len(findings) == 1
        assert all(entry.mesh.volume == pytest.approx(3200.0, rel=1e-6) for entry in outputs)
    elif rule == "join_clear":
        findings = [
            finding for finding in result.scene.report.findings if finding.code.startswith("join.")
        ]
        assert [finding.code for finding in findings] == ["join.clear"]
        assert [entry.mesh.bounds.centre[0] for entry in outputs] == pytest.approx([0.0, 40.0])
    elif rule == "assigned":
        from app.core.geom.attributes import used_slots

        assert used_slots(mesh) == (expected,)
        assert any(
            slot.index == expected and slot.name == "Prüfrot" for slot in first.material_slots
        )
        assert volume == pytest.approx(3200.0)
    elif rule == "painted":
        from app.core.geom.attributes import used_slots

        assert set(used_slots(mesh)) == {0, expected}
        assert any(
            slot.index == expected and slot.name == "Prüfgrün" for slot in first.material_slots
        )
    elif rule == "cleared":
        from app.core.geom.attributes import used_slots

        assert used_slots(mesh) == (0,)
        assert not first.material_slots
        assert volume == pytest.approx(3200.0)
    elif rule == "texture_slots":
        from app.core.geom.attributes import used_slots

        assert len(used_slots(mesh)) == expected
        assert len(first.material_slots) == expected
        assert volume == pytest.approx(3200.0)
    elif rule == "material":
        assert first.material == expected
        assert volume == pytest.approx(3200.0)
    elif rule == "name":
        assert first.name == expected
        assert volume == pytest.approx(3200.0)
    elif rule == "decimated":
        assert mesh.triangle_count == expected
        assert volume == pytest.approx(4000.0 * math.pi / 3.0, rel=0.08)
    elif rule == "refined":
        assert mesh.triangle_count > 12
        assert volume == pytest.approx(expected, rel=1e-6)
    elif rule == "repaired":
        assert mesh.is_watertight
        assert volume == pytest.approx(expected, rel=1e-6)
        assert not as_mesh_data(inputs[0].mesh).is_watertight
    elif rule == "smoothed":
        assert not np.array_equal(mesh.raw.vertices, as_mesh_data(inputs[0].mesh).raw.vertices)
        assert mesh.triangle_count == as_mesh_data(inputs[0].mesh).triangle_count
        assert volume == pytest.approx(inputs[0].mesh.volume, rel=0.03)
    elif rule == "bump":
        assert first.mesh.bounds.maximum[0] > 10.1
        assert first.mesh.bounds.minimum[0] == pytest.approx(
            as_mesh_data(inputs[0].mesh).bounds.minimum[0], abs=1e-8
        )
    elif rule == "posed":
        assert first.mesh.bounds.size == pytest.approx((16.0, 20.0, 10.0), abs=0.01)
        assert volume == pytest.approx(3200.0, rel=1e-6)
    elif rule == "hollow":
        from app.core.geom.mesh import on_surface

        # Das dokumentierte Raster sichert die Wand auf ein Sechstel ihres
        # Sollmaßes. Die analytischen Grenzkästen geben das Volumenintervall.
        lower_wall, upper_wall = 2.0 - 2.0 / 6.0, 2.0 + 2.0 / 6.0
        lower_volume = 3200.0 - (20 - 2 * lower_wall) * (16 - 2 * lower_wall) * (10 - lower_wall)
        upper_volume = 3200.0 - (20 - 2 * upper_wall) * (16 - 2 * upper_wall) * (10 - upper_wall)
        assert lower_volume < expected < upper_volume
        assert lower_volume < volume < upper_volume
        points = np.asarray([(0, 0, 1), (9, 0, 5), (0, 0, 5), (0, 0, 9), (10.5, 0, 5)])
        nearest, _distances, triangles = on_surface(mesh.raw, points)
        signed = np.einsum("ij,ij->i", points - nearest, mesh.raw.face_normals[triangles])
        assert (signed < 0).tolist() == [True, True, False, False, False]
    elif rule == "pin_diameter":
        from app.core.perceive.features import detect

        pins = [feature for feature in detect(mesh).values() if feature.kind == "pin"]
        assert len(pins) == 1
        assert pins[0].params["diameter"] == pytest.approx(expected, abs=0.03)
        assert volume > 12000.0 + 54.0 * math.pi
    elif rule in {"hole_count", "hole_x", "hole_diameter", "hole_tilted"}:
        holes = _holes(first)
        if rule == "hole_count":
            assert len(holes) == expected
        else:
            assert len(holes) == 1
            if rule == "hole_x":
                assert holes[0].params["centre"][0] == pytest.approx(expected, abs=0.03)
            elif rule == "hole_diameter":
                assert holes[0].params["diameter"] == pytest.approx(expected, abs=0.03)
            else:
                assert abs(holes[0].params["axis"][0]) > 0.2
    elif rule == "detected_hole":
        assert not inputs[0].features
        holes = [feature for feature in first.features.values() if feature.kind == "hole"]
        assert holes and holes[0].params["diameter"] == pytest.approx(expected, abs=0.03)
    elif rule == "slot":
        slots = [feature for feature in first.features.values() if feature.kind == "slot"]
        assert len(slots) == 1
        assert slots[0].params["length"] == pytest.approx(expected, abs=0.03)
    elif rule == "draft":
        assert not math.isclose(volume, 3200.0, rel_tol=1e-3)
        assert first.mesh.bounds.size[2] == pytest.approx(10.0, abs=1e-5)
    elif rule == "split":
        assert sum(entry.mesh.volume for entry in outputs) == pytest.approx(expected, rel=1e-5)
        assert all(as_mesh_data(entry.mesh).component_count == 1 for entry in outputs)
    elif rule == "pins":
        pins = [feature for feature in outputs[0].features.values() if feature.kind == "pin"]
        holes = [feature for feature in outputs[1].features.values() if feature.kind == "hole"]
        assert len(pins) == len(holes) == 2
        assert [pin.params["diameter"] for pin in pins] == pytest.approx([2.0, 2.0])
        assert [hole.params["diameter"] for hole in holes] == pytest.approx([2.25, 2.25])
        assert outputs[0].mesh.volume > 1600.0
        assert 1400.0 < outputs[1].mesh.volume < 1600.0
    elif rule == "lid":
        lid = outputs[1]
        assert lid.mesh.bounds.size[:2] == pytest.approx(expected, abs=0.03)
        assert lid.mesh.volume > expected[0] * expected[1] * 2.4
    elif rule == "screw_cap":
        assert outputs[1].mesh.volume > 1000.0
        assert any(
            feature.kind == "thread" for entry in outputs for feature in entry.features.values()
        )
    elif rule == "field":
        assert 8000.0 - volume == pytest.approx(36.0 * math.pi, rel=0.003)
        assert len([feature for feature in first.features.values() if feature.kind == "hole"]) == 9
    elif rule == "seal":
        assert 8000.0 - volume == pytest.approx(40.0 * math.pi, rel=0.003)
        assert outputs[1].mesh.volume == pytest.approx(38.4 * math.pi, rel=0.003)
        assert [entry.material for entry in outputs] == ["petg", "tpu-95a"]
    elif rule == "clamp_roles":
        assert [entry.material for entry in outputs] == ["petg", "petg", "tpu-95a", "tpu-95a"]
        assert [entry.features["front"].params["profile_clamp"]["role"] for entry in outputs] == [
            "shell_lower",
            "shell_upper",
            "liner_lower",
            "liner_upper",
        ]
    elif rule == "replacement":
        assert [entry.material for entry in outputs] == ["petg", "petg", "tpu-95a", "tpu-95a"]
        for before, after in zip(inputs[:2], outputs[:2], strict=True):
            assert before.mesh.volume == pytest.approx(after.mesh.volume, rel=1e-8)
        assert all(
            after.mesh.volume > before.mesh.volume
            for before, after in zip(inputs[2:], outputs[2:], strict=True)
        )
    elif rule == "organizer":
        assert first.mesh.bounds.size == pytest.approx(expected, abs=0.03)
        assert 0.0 < volume < math.prod(expected)
    elif rule == "thread":
        features = [feature for feature in first.features.values() if feature.kind == "thread"]
        assert len(features) == 1
        assert features[0].params["diameter"] == pytest.approx(expected[0])
        assert features[0].params["pitch"] == pytest.approx(expected[1])
        assert first.mesh.bounds.size[2] == pytest.approx(expected[2], abs=0.05)
    elif rule == "overhang":
        assert mesh.component_count == 1
        assert mesh.bounds.size[0] >= 3 * 8.0
        assert mesh.bounds.size[2] > 5.0
    else:
        raise AssertionError(f"Die Invariante {rule!r} ist nicht umgesetzt.")


def test_every_registered_operation_has_an_explicit_success_case() -> None:
    """Erzeuger und ganze Szene gehören ohne Filter zur vollständigen Liste."""
    load_operations()
    registered = {spec.name for spec in REGISTRY.all()}
    assert len(CASES) == len(CASE_BY_NAME), "Jede Operation braucht genau eine Fallzuordnung."
    assert set(CASE_BY_NAME) == registered
    assert len(registered) == 133
    assert all(case.variants and case.invariant for case in CASES)


@pytest.mark.parametrize(
    "case,kind,expected_kinds",
    [
        pytest.param(case, kind, outputs, id=f"{case.name}-{kind}")
        for case in CASES
        for kind, outputs in case.variants
    ],
)
def test_every_operation_completes_with_its_declared_result(
    case: Case,
    kind: str,
    expected_kinds: tuple[str, ...],
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein gültiger Auftrag wird geplant, vollständig ausgewertet und fachlich gemessen."""
    pytest.importorskip("OCP")
    from app.core.brep.kernel import Solid

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    inputs = _inputs(case, kind, project, profile)
    if case.name == "detect_region" and kind == "mesh":
        import importlib

        # Die globale Erkennung bleibt wie beim großen Kundenmodell aus.
        # Nur die geprüfte lokale Op darf das bisher unbekannte Loch finden.
        # Eine kleine Eingabe prüft denselben Zweig ohne einen Leistungslauf.
        evaluation = importlib.import_module("app.core.scene.evaluate")
        monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(spec)

    def seed(ctx: OpContext) -> OpResult:
        """Vorbereitete Referenzkörper betreten den echten Auswertungsweg."""
        return OpResult(outputs=[dataclasses.replace(entry, id="") for entry in inputs])

    history = History(project.document, registry=registry)
    if inputs:
        registry.register(
            OperationSpec(
                name="matrix_input",
                title="Referenzkörper",
                category="primitive",
                params=BaseParams,
                fn=seed,
                consumes=0,
                produces=len(inputs),
            )
        )
        history.apply("Referenzkörper", [OperationDraft(op="matrix_input")])
    wanted_inputs = tuple(entry.id for entry in inputs)
    if case.name == "align_to_feature":
        wanted_inputs = ("obj_1",)
    history.apply(
        "Geprüfter Auftrag",
        [
            OperationDraft(
                op=case.name, inputs=wanted_inputs, params=_parameters(case, inputs), seed=1234
            )
        ],
    )
    operation = project.document.ops[-1]
    assert len(operation.outputs) == len(expected_kinds)
    result = evaluate(
        project.document,
        profile,
        registry=registry,
        sources=ProjectSources(project),
        ask=_unexpected_question,
    )
    assert result.complete, [
        (finding.code, str(finding.message), finding.values)
        for finding in result.scene.report.findings
    ]
    assert operation.id in result.completed
    outputs = [result.scene.objects[identifier] for identifier in operation.outputs]
    assert len(outputs) == len(expected_kinds)
    for entry, expected_kind in zip(outputs, expected_kinds, strict=True):
        assert entry.kind == expected_kind
        assert isinstance(entry.mesh, Solid if expected_kind == "brep" else MeshData)
        assert math.isfinite(entry.mesh.volume) and entry.mesh.volume > 0.0
        assert as_mesh_data(entry.mesh).is_watertight
    _assert_invariant(case, outputs, inputs, result)
