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
from app.core.knowledge.parts import builtin
from app.core.registry import REGISTRY, OperationSpec, Registry
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import (
    BaseParams,
    Feature,
    OpContext,
    OpResult,
    Profile,
    Quality,
    SceneObject,
    Source,
)
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from tests.helpers import exact_kernel

MESHES = Path(__file__).parent / "data" / "meshes"
# Ausdrückliche Zusagen für beide Darstellungen, unabhängig vom Op-Register.
KEEP = (("mesh", ("mesh",)), ("brep", ("brep",)))
MESH = (("mesh", ("mesh",)), ("brep", ("mesh",)))
EXACT = (("brep", ("brep",)),)
MESH_ONLY = (("mesh", ("mesh",)),)
CREATE_MESH = (("none", ("mesh",)),)
CREATE_EXACT = (("none", ("brep",)),)
CONVERT_EXACT = (("mesh", ("brep",)),)


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
    # Der Einsatz entsteht aus Behälter und Deckel desselben Kerns; beide
    # Eingänge bleiben unverändert stehen (``keeps_inputs``).
    Case(
        "add_container_insert",
        "container",
        {"shape": "round", "diameter": 60.0, "height": 40.0},
        (("mesh", ("mesh", "mesh", "mesh")), ("brep", ("brep", "brep", "brep"))),
        "container_insert",
        (27.0, 3.0),
    ),
    # Ausrichten ist eine starre Bewegung wie Verschieben und Drehen; bis zum
    # 22.09.2026 machte es aus einem exakten Körper trotzdem ein Netz.
    Case(
        "align_to_feature",
        "alignment",
        {"feature": "top", "target": "obj_2:top"},
        KEEP,
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
        "create_brep_cone",
        "none",
        {"bottom_diameter": 20.0, "top_diameter": 10.0, "height": 12.0},
        CREATE_EXACT,
        "volume",
        700.0 * math.pi,
    ),
    Case(
        "create_brep_sphere",
        "none",
        {"diameter": 10.0},
        CREATE_EXACT,
        "volume",
        500.0 * math.pi / 3.0,
    ),
    Case(
        "create_brep_torus",
        "none",
        {"outer_diameter": 40.0, "tube_diameter": 8.0},
        CREATE_EXACT,
        "volume",
        2.0 * math.pi**2 * 16.0 * 16.0,
    ),
    Case(
        "create_brep_tube",
        "none",
        {"outer_diameter": 22.9, "inner_given": True, "inner_diameter": 16.9, "height": 30.0},
        CREATE_EXACT,
        "volume",
        math.pi / 4.0 * (22.9**2 - 16.9**2) * 30.0,
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
        "create_container",
        "none",
        {"shape": "round", "lid": "push", "diameter": 60.0, "height": 40.0},
        # Ohne Vorgabe rechnet der Behälter exakt, wo der Kern verfügbar ist.
        (("none", ("brep", "brep")),),
        "container",
        math.pi * (30.0**2 * 40.0 - 27.0**2 * 37.0),
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
        # P2.8: der Körper entscheidet — am exakten Gehäuse entsteht der Deckel exakt.
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
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
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
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
        "create_tube",
        "none",
        {"outer_diameter": 20.0, "wall": 2.0, "height": 20.0, "segments": 96},
        CREATE_MESH,
        "volume",
        math.pi / 4.0 * (20.0**2 - 16.0**2) * 20.0,
    ),
    Case(
        "cut_away", "box", {"axis": "z", "position": 5.0, "keep": "below"}, KEEP, "volume", 1600.0
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
        # Ein Relief ist ein Netz: Der exakte Körper geht hinein und kommt als
        # Netz heraus — das ist die Zusage, nicht ein Fehlen des Falls.
        MESH,
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
        # P2.8: die Körperart entscheidet — am exakten Körper bleibt die Bohrung exakt.
        KEEP,
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
        "hollow_object",
        "box",
        {"wall": 2.0, "open_top": True, "vents": 0},
        # P2.8: Oberseite offen ohne Entlüftung bleibt am exakten Körper exakt (§10.1).
        KEEP,
        "hollow",
        1664.0,
    ),
    Case("intersect_objects", "overlapping", {}, KEEP, "volume", 1600.0),
    Case(
        "label_text",
        "box",
        {"text": "H", "size": 6.0, "depth": 0.8, "z": 10.0, "mode": "raised"},
        KEEP,
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
    # P4.0: die einzige Operation, die aus einem Netz einen exakten Körper macht.
    # Am exakten Eingang steht sie grau (``requires_kind="mesh"``); dort gibt es
    # nichts umzuwandeln.
    Case("mesh_to_exact", "box", {"tolerance": 0.01}, CONVERT_EXACT, "volume", 3200.0),
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
        "group_pattern",
        "square_holes",
        # RM-504: drei durchgehende Vierkantlöcher (unter jeder Erkennungsschwelle)
        # werden an beiden Kernen ausdrücklich ein Muster; die Geometrie bleibt.
        {},
        KEEP,
        "grouped_cells",
        3,
    ),
    Case(
        "pattern_feature",
        "hole",
        # P6.7: das Merkmalsmuster bleibt am exakten Körper exakt.
        {"at_features": ["hole"], "kind": "linear", "count": 2, "spacing": 14.0, "dx": 1.0},
        KEEP,
        "hole_count",
        2,
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
    # Quader 20 x 16 x 10, Deckfläche um 2 mm hinaus: 20 x 16 x 12, sechs Flächen.
    Case(
        "push_face",
        "box",
        {"face": "top", "distance": 2.0},
        KEEP,
        "pushed",
        (3840.0, (192.0, 192.0, 240.0, 240.0, 320.0, 320.0)),
    ),
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
        KEEP,
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
        "resize_feature", "pin", {"at_feature": "pin", "diameter": 8.0}, KEEP, "pin_diameter", 8.0
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
        # P2.8: der Körper entscheidet — am exakten Gehäuse entstehen Hals und Kappe exakt.
        (("mesh", ("mesh", "mesh")), ("brep", ("brep", "brep"))),
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
    # Angefügt wird nur, was über den Körper hinausragt: 8 mal 6 von z = 10 bis 16.
    Case(
        "sketch_join",
        "box",
        {"shape": "rectangle", "length": 8.0, "width": 6.0, "height": 16.0},
        KEEP,
        "volume",
        3200.0 + 8.0 * 6.0 * 6.0,
    ),
    Case(
        "sketch_loft",
        "none",
        {"shape": "rectangle", "length": 20.0, "width": 10.0, "height": 12.0, "top_scale": 0.5},
        CREATE_EXACT,
        "volume",
        1400.0,
    ),
    # Stumpf 8 x 6 auf 4 x 3 über 6 mm: h/3 · (48 + 12 + 24) = 168 (P6.5c).
    Case(
        "sketch_loft_cut",
        "box",
        {"shape": "rectangle", "length": 8.0, "width": 6.0, "top_scale": 0.5, "depth": 6.0},
        KEEP,
        "volume",
        3200.0 - 168.0,
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
    # Ringnut in der Deckfläche: r 3 bis 5, 2 mm tief — π (5² - 3²) · 2 (P6.5a).
    Case(
        "sketch_revolve_cut",
        "box",
        {"shape": "rectangle", "length": 2.0, "width": 3.0, "offset": 3.0, "axis_z": 8.0},
        KEEP,
        "volume",
        3200.0 - 32.0 * math.pi,
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
    # Kanal Ø4 von der Deckfläche nach unten, Viertelbogen R6: π · 2² · (π/2 · 6) (P6.5b).
    Case(
        "sketch_sweep_cut",
        "box",
        {"shape": "circle", "length": 4.0, "along": "arc", "bend_radius": 6.0, "bend_angle": 90.0},
        KEEP,
        "volume",
        3200.0 - 12.0 * math.pi**2,
    ),
    Case(
        "slot_hole",
        "hole",
        {"at_feature": "hole", "slot_length": 12.0, "slot_angle": 0.0},
        KEEP,
        "slot",
        12.0,
    ),
    # Am exakten Körper gibt es keine Textur; er bleibt exakt und sagt es
    # (``colour.no_texture``) — die Invariante prüft je Bauart etwas anderes.
    Case("slots_from_texture", "textured", {"filaments": 2}, KEEP, "texture_slots", 2),
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
    # Der Kragen des Bajonetts: Einstecktiefe und Nockenhöhe, unabhängig vom Spiel.
    "bayonet": ({"kind": "plug", "diameter": 24.0, "lugs": 3}, "greater", 6.0 + 3.5),
    "bearing_seat": ({"size": "608", "removable": False}, "less", None),
    "cable_clip": ({"size": "cable-5", "width": 8.0, "wall": 2.0}, "greater", None),
    "cable_gland": ({"size": "cable-5", "wall": 3.0, "strain_relief": False}, "less", None),
    # Die Hülse der Kanalnaht steht auf ihrem Boden: Nahtwand und Kanalhöhe.
    "channel_joint": (
        {"style": "outer_sleeve", "width": 44.0, "height": 27.0, "wall": 2.0, "thickness": 1.2},
        "greater",
        1.2 + 27.0,
    ),
    # Die Drehscheibe mit ihrem Griffsteg: zwei Scheibendicken.
    "detent_disc": ({"kind": "disc", "diameter": 32.0, "thickness": 3.0}, "greater", 6.0),
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
    # Die Tülle wächst mehr auf, als ihr Durchgang aus der Wand nimmt.
    "hose_barb": (
        {"hose": 12.0, "grip": 1.0, "count": 3, "length": 24.0, "wall": 1.5, "through": 3.0},
        "greater",
        None,
    ),
    # Die Halter mit Klemme: Ihre Höhe ist die eingetragene, die Rückwand wächst
    # nicht; die Ablage trägt ihren Rand darüber.
    "holder_fork": (
        {"width": 10.0, "depth": 10.0, "height": 20.0, "mount": "clamp", "board": 10.0},
        "greater",
        20.0,
    ),
    "holder_ring": (
        {"diameter": 20.0, "height": 25.0, "mount": "clamp", "board": 10.0, "floor": True},
        "greater",
        25.0,
    ),
    "holder_shelf": (
        {"width": 30.0, "depth": 15.0, "height": 30.0, "lip": 5.0, "mount": "clamp", "board": 10.0},
        "greater",
        30.0 + 5.0,
    ),
    "holder_u": (
        {"width": 20.0, "depth": 15.0, "height": 30.0, "mount": "clamp", "board": 10.0},
        "greater",
        30.0,
    ),
    "keyhole": ({"size": "M4", "drop": 8.0, "depth": 4.0, "head_room": 2.5}, "less", None),
    "latch": ({"width": 6.0, "depth": 1.0, "height": 3.0, "negative": False}, "greater", None),
    "living_hinge": (
        {"width": 30.0, "leaf": 15.0, "thickness": 2.0, "film": 0.4, "gap": 1.5},
        "greater",
        None,
    ),
    "lug": ({"size": "M4", "width": 0.0, "length": 0.0, "thickness": 4.0}, "greater", None),
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
    "pipe_clamp": (
        {"size": "22", "width": 15.0, "wall": 3.0, "screw_size": "M4"},
        "greater",
        # Fuß (eine Wand), Ring (Rohr mit 0,25 Spiel aus PETG und zwei
        # Wänden) und darüber die Unterlegscheibe M4 (9,0).
        3.0 + (22.25 + 2.0 * 3.0) + 9.0,
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
    # Die Steckhülse: Boden und Einstecktiefe, unabhängig vom Spiel.
    "rod_connector": (
        {"layout": "sleeve", "rod": 16.0, "depth": 30.0, "wall": 3.0},
        "greater",
        3.0 + 30.0,
    ),
    # Die Raumplatten liegen flach: so hoch wie dick.
    "room_floor": ({"length": 120.0, "depth": 90.0, "thickness": 4.0, "wall": 4.0}, "greater", 4.0),
    "room_pane": ({"opening_width": 50.0, "opening_height": 40.0, "wall": 4.0}, "greater", 2.0),
    "room_wall": (
        {"role": "room_back", "width": 120.0, "height": 80.0, "wall": 4.0, "opening_width": 0.0},
        "greater",
        4.0,
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
    "bayonet",
    "channel_joint",
    "detent_disc",
    "fit_ladder",
    "holder_fork",
    "holder_ring",
    "holder_shelf",
    "holder_u",
    "organizer_divider",
    "organizer_foot",
    "organizer_rim",
    "organizer_tray",
    "overhang_fan",
    "pipe_clamp",
    "profile_clamp_liner",
    "profile_clamp_shell",
    "rod_connector",
    "room_floor",
    "room_pane",
    "room_wall",
    "seal_gasket",
    "wall_ladder",
)
# **Jeder Baustein baut an einem exakten Träger exakt** (P2.7, abgenommen für
# alle 35). Bis zum 21.09.2026 stand hier eine Liste ``EXACT_PARTS`` mit genau
# diesen 35 Namen und ein ``MESH``-Zweig für die übrigen — den es nicht mehr
# gab, und ein neuer Baustein wäre still in ihn gefallen. Jetzt ist ``KEEP``
# die Zusage für jeden, und wer einen Baustein baut, der sie nicht hält,
# bekommt hier den roten Fall.
for _part, (_dimensions, _effect, _height) in PART_CASES.items():
    CASES.append(
        Case(
            f"insert_{_part}",
            "host",
            {**_dimensions, "x": 0.0, "y": 0.0, "z": 10.0, "nx": 0.0, "ny": 0.0, "nz": 1.0},
            KEEP,
            _effect,
            100000.0,
        )
    )
# Eine Vorlage entsteht wie ein Grundkörper exakt (RM-443, ``ops._creates_exactly``);
# die übrigen Erzeuger bleiben beim Netz, wie ihre gespeicherten Schritte rechnen.
for _part in STANDALONE:
    _dimensions, _effect, _height = PART_CASES[_part]
    CASES.append(
        Case(
            f"create_{_part}",
            "none",
            dict(_dimensions),
            CREATE_EXACT if builtin.load().get(_part).template else CREATE_MESH,
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
    if source == "container":
        from app.core.scene.cancel import NeverCancelled
        from app.core.types import Scene

        spec = REGISTRY.get("create_container")
        made = spec.fn(
            OpContext(
                Scene(),
                [],
                spec.params(shape="round", lid="push", kernel=kind),
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
    if source == "square_holes":
        body = _native_box(40.0, 30.0, 10.0)
        for x in (-10.0, 0.0, 10.0):
            body = _native_difference(body, _native_box(4.0, 4.0, 12.0, (x, 0.0, -1.0)))
        return [_object(body, kind)]
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
    if kind == "brep" and source in {"fine_box", "textured"}:
        # Der exakte Körper trägt weder eine feinere Vernetzung noch Farben
        # je Dreieck; das Relief holt sich sein Bild aus der Quelle, die
        # Texturfrage bekommt den nackten Körper und muss das sagen.
        if source == "fine_box":
            _add_source(project, "image", ".png", _gradient_png(), "image")
        return [entry]
    if kind == "brep" and source == "broken_box":
        # Einen kaputten exakten Körper gibt es nicht — der Kern kennt keine
        # offenen Dreiecke. Die Reparatur bekommt den ganzen Körper und muss
        # ihn ganz lassen: exakt, mit Merkmalen, derselbe Körper.
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
        raw = raw.subdivide().subdivide().subdivide()
        _add_source(project, "image", ".png", _gradient_png(), "image")
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


def _gradient_png() -> bytes:
    """Ein Verlauf trägt echte Höhen; ein einfarbiges Bild bedeutet im
    Reliefvertrag ausdrücklich Höhe null."""
    from PIL import Image

    payload = io.BytesIO()
    Image.fromarray(np.tile(np.linspace(0, 255, 8, dtype=np.uint8), (8, 1))).save(
        payload, format="PNG"
    )
    return payload.getvalue()


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
    if case.name == "group_pattern":
        # Die zwölf Wände der drei Löcher: senkrecht und kleiner als jede Seite.
        params["at_features"] = sorted(
            name
            for name, feature in inputs[0].features.items()
            if feature.kind == "face"
            and abs(float(feature.params["normal"][2])) < 0.5
            and float(feature.params["area"]) < 50.0
        )
        assert len(params["at_features"]) == 12
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
    elif rule == "pushed":
        # RM-226: *Fläche versetzen* ließ am exakten Körper die angesetzte
        # Scheibe als eigene koplanare Fläche neben jeder Seitenwand stehen
        # (160 + 32 statt 192 mm²), das Netz nannte je Wand eine. Beide Kerne
        # nennen dieselben sechs ebenen Flächen mit denselben Inhalten.
        expected_volume, expected_areas = expected
        assert volume == pytest.approx(expected_volume, abs=1e-6)
        kinds = sorted(feature.kind for feature in first.features.values())
        assert kinds == ["face"] * len(expected_areas), kinds
        areas = sorted(feature.params["area"] for feature in first.features.values())
        assert areas == pytest.approx(expected_areas, abs=1e-6)
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

        if inputs[0].kind == "brep":
            # Kein Dreieck, keine Farbe je Dreieck: Der exakte Körper bleibt,
            # was er war, und der Bericht sagt, warum nichts zu verteilen war.
            assert first.kind == "brep"
            assert "colour.no_texture" in {f.code for f in result.scene.report.findings}
        else:
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
        if first.kind == "brep":
            # Nichts zu reparieren: Strg+Umschalt+R an einem STEP machte bis
            # zum 21.09.2026 aus dem Körper Dreiecke und sagte „nichts zu
            # reparieren“ — jetzt kommt derselbe exakte Körper zurück.
            assert first.mesh is inputs[0].mesh
            assert set(first.features) == set(inputs[0].features)
            assert any(
                entry.code == "repair.nothing_to_do" for entry in result.scene.report.findings
            )
        else:
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
    elif rule == "grouped_cells":
        grouped = [f for f in first.features.values() if f.kind == "pattern"]
        assert len(grouped) == 1 and grouped[0].params["grouped"] is True
        assert grouped[0].params["count"] == expected
        assert volume == pytest.approx(12000.0 - 3 * 16.0 * 10.0, rel=1e-6)
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
    elif rule == "container":
        body, cap = outputs
        assert body.mesh.bounds.size[:2] == pytest.approx((60.0, 60.0), abs=0.06)
        assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
        assert body.mesh.bounds.maximum[2] == pytest.approx(40.0, abs=1e-6)
        assert body.mesh.volume == pytest.approx(expected, rel=0.005)
        # Der Steckdeckel trägt 2,4 mm über dem Rand und greift in die Öffnung.
        assert cap.mesh.bounds.maximum[2] == pytest.approx(42.4, abs=1e-6)
        assert cap.mesh.bounds.minimum[2] < 40.0
    elif rule == "container_insert":
        inner, floor = expected
        body, cap, insert = outputs
        assert body.mesh.volume == pytest.approx(inputs[0].mesh.volume, rel=1e-9)
        assert cap.mesh.volume == pytest.approx(inputs[1].mesh.volume, rel=1e-9)
        bounds = insert.mesh.bounds
        assert max(abs(value) for value in (*bounds.minimum[:2], *bounds.maximum[:2])) < inner
        assert bounds.minimum[2] >= floor - EPS_GEOM
        assert bounds.maximum[2] <= cap.mesh.bounds.minimum[2] + EPS_GEOM
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


#: Operationen, die beide Bauarten annehmen (``requires_kind == ""``) und
#: trotzdem keinen Erfolgsfall am exakten Körper haben — jede mit dem Grund,
#: warum es dort keinen gibt. Wer hier eine Zeile streicht, gibt der Tabelle
#: oben eine ``brep``-Variante; wer eine hinzufügt, erklärt sie.
NO_EXACT_VARIANT = {
    # Aufdicken verlangt eine offene Fläche; ein exakter Körper ist immer
    # geschlossen und wird mit ``already_solid`` abgewiesen (Menüpunkt grau).
    "thicken": "ein exakter Körper ist nie eine offene Fläche",
    # Die vier Teile kommen aus ``create_profile_clamp_set`` und das baut
    # Netze (``CREATE_MESH``); einen exakten Klemmensatz gibt es nicht.
    "replace_profile_liners": "der Klemmensatz entsteht als Netz",
}


def test_every_registered_operation_has_an_explicit_success_case() -> None:
    """Erzeuger und ganze Szene gehören ohne Filter zur vollständigen Liste.

    Die Zahl der Operationen steht nicht mehr daneben: Sie stand bei 136 und
    sagte nichts, was die Mengengleichheit nicht sagt — außer, dass jede neue
    Operation diese Zeile mit anfassen musste.
    """
    load_operations()
    registered = {spec.name for spec in REGISTRY.all()}
    assert len(CASES) == len(CASE_BY_NAME), "Jede Operation braucht genau eine Fallzuordnung."
    assert set(CASE_BY_NAME) == registered
    assert all(case.variants and case.invariant for case in CASES)


def test_the_table_promises_no_more_and_no_less_than_the_register() -> None:
    """``requires_kind`` und die Varianten der Tabelle sagen dasselbe.

    Eine Operation, die beide Bauarten annimmt, hat einen Erfolgsfall am
    exakten Körper — oder steht mit Grund in :data:`NO_EXACT_VARIANT`. Eine,
    die nur Netze nimmt, hat keine ``brep``-Variante, eine, die nur exakte
    Körper nimmt, keine ``mesh``-Variante. Bis zum 21.09.2026 standen fünf
    Operationen mit ``requires_kind == ""`` als ``MESH_ONLY`` in der Tabelle,
    und niemand verglich die beiden Aussagen.
    """
    load_operations()
    specs = [spec for spec in REGISTRY.all() if spec.consumes >= 1 and not spec.whole_scene]
    assert specs, "ohne verbrauchende Operationen prüft dieser Test nichts"
    for spec in specs:
        kinds = {kind for kind, _outputs in CASE_BY_NAME[spec.name].variants}
        if spec.requires_kind == "mesh":
            assert "brep" not in kinds, f"{spec.name} nimmt nur Netze, die Tabelle fährt brep"
        elif spec.requires_kind == "brep":
            assert "mesh" not in kinds, (
                f"{spec.name} nimmt nur exakte Körper, die Tabelle fährt mesh"
            )
        elif spec.name in NO_EXACT_VARIANT:
            assert "brep" not in kinds, (
                f"{spec.name} hat eine brep-Variante — der Eintrag in NO_EXACT_VARIANT ist überholt"
            )
        else:
            assert "brep" in kinds, (
                f"{spec.name} verspricht beide Bauarten und läuft nie am exakten Körper"
            )
        # ``result_kind`` sagt dem Fenster vor der Rechnung, ob der exakte
        # Körper ein Netz wird; die Tabelle sagt es nach der Rechnung. Beide
        # müssen dasselbe sagen — sonst läuft eine Umwandlung ohne Vorschau
        # durch (22.09.2026, *Skelett stellen* am exakten Quader).
        exact_outputs = [
            outputs for kind, outputs in CASE_BY_NAME[spec.name].variants if kind == "brep"
        ]
        converts = bool(exact_outputs) and all(
            outputs and "brep" not in outputs for outputs in exact_outputs
        )
        assert (spec.result_kind == "mesh") is converts, (
            f"{spec.name}: result_kind={spec.result_kind!r}, die Tabelle sagt "
            f"{'Netz' if converts else 'exakt bleibt exakt'}"
        )


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
    exact_kernel()
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


# --- RM-226: dieselbe Fläche heißt an beiden Kernen gleich -------------------


def _arched_block(arc: float) -> Any:
    """Quader 40 x 8, dessen Oberseite ein Kreisbogen über die ganze Breite ist.

    Sehne 40, Öffnungswinkel ``arc``: Der Bogen trifft die senkrechten
    Seitenwände unter 90° − arc/2 und damit nie tangential. Gebaut aus Quader
    und Zylinder, unabhängig von Skizze und Extrusion; der Radius folgt aus
    der Sehne, 20 / sin(arc/2) — R 382,15 / 191,34 / 77,27 bei 6 / 12 / 30 Grad.
    """
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.kernel import Solid

    radius = 20.0 / math.sin(math.radians(arc / 2.0))
    rise = radius * (1.0 - math.cos(math.radians(arc / 2.0)))
    block = BRepPrimAPI_MakeBox(gp_Pnt(-20.0, -4.0, 0.0), 40.0, 8.0, 10.0 + rise + 1.0).Shape()
    drum = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(0.0, -5.0, 10.0 + rise - radius), gp_Dir(0.0, 1.0, 0.0)), radius, 10.0
    ).Shape()
    return Solid(BRepAlgoAPI_Common(block, drum).Shape())


def _arched_section(arc: float) -> float:
    """Querschnitt des gewölbten Quaders: Rechteck 40 x 10 plus Kreisabschnitt."""
    radius = 20.0 / math.sin(math.radians(arc / 2.0))
    angle = math.radians(arc)
    return 40.0 * 10.0 + radius * radius / 2.0 * (angle - math.sin(angle))


def _evaluated(
    op: str, params: dict[str, Any], inputs: list[SceneObject], profile: Profile
) -> list[SceneObject]:
    """Vorbereitete Eingaben durch Verlauf und Auswertung, wie im Falltest oben."""
    result, operation = _evaluation(op, params, inputs, profile)
    assert result.complete, [
        (finding.code, str(finding.message), finding.values)
        for finding in result.scene.report.findings
    ]
    return [result.scene.objects[identifier] for identifier in operation.outputs]


def _evaluation(
    op: str,
    params: dict[str, Any],
    inputs: list[SceneObject],
    profile: Profile,
    *,
    quality: Quality = "fine",
) -> tuple[Any, Any]:
    """Auswertung und geprüfter Schritt, ohne Urteil — auch für eine erwartete Absage."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(spec)

    def seed(ctx: OpContext) -> OpResult:
        """Die Referenzkörper betreten den echten Auswertungsweg."""
        return OpResult(outputs=[dataclasses.replace(entry, id="") for entry in inputs])

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
    history = History(project.document, registry=registry)
    history.apply("Referenzkörper", [OperationDraft(op="matrix_input")])
    history.apply(
        "Geprüfter Auftrag",
        [
            OperationDraft(
                op=op, inputs=tuple(entry.id for entry in inputs), params=params, seed=1234
            )
        ],
    )
    operation = project.document.ops[-1]
    result = evaluate(
        project.document,
        profile,
        quality=quality,
        registry=registry,
        sources=ProjectSources(project),
        ask=_unexpected_question,
    )
    return result, operation


@pytest.mark.parametrize("arc", [6.0, 12.0, 30.0])
def test_an_arched_top_is_one_curved_face_on_both_kernels(arc: float, profile: Profile) -> None:
    """Eine gewölbte Oberseite ist an beiden Kernen eine gekrümmte Fläche (RM-226).

    Der exakte Kern nannte jeden Zylinderausschnitt unter 300 Grad eine
    Verrundung — an diesem Quader „Verrundung R 382 / 191 / 77“ bei 6, 12
    und 30 Grad —, das Netz denselben Bogen eine gekrümmte Fläche. Am Netz
    entscheidet nicht ``replaces_an_edge`` (ein flacher Buckel mitten auf
    der Oberseite ersetzt auch keine Kante und heißt an beiden Kernen
    Verrundung), sondern die Frage, ob der Zylinder in seinen Körper passt:
    Ø 764 auf einem 40 mm breiten Quader ist keine Rundung. Jetzt fragt der
    exakte Kern dieselbe. Geprüft am Eingang auf denselben Dreiecken und nach
    *Fläche versetzen* an der Vorderseite, ohne Wechsel der Bauart (KEEP).
    """
    exact_kernel()
    from collections import Counter

    solid = _arched_block(arc)
    expected = {"face": 5, "curved_face": 1}
    tops: dict[str, set[int]] = {}
    for kind in ("mesh", "brep"):
        entry = _object(solid, kind)
        assert Counter(feature.kind for feature in entry.features.values()) == expected, kind
        (top,) = [feature for feature in entry.features.values() if feature.kind == "curved_face"]
        tops[kind] = set(top.face_indices)
        front = next(
            name
            for name, feature in entry.features.items()
            if feature.kind == "face" and feature.params["normal"][1] < -0.99
        )
        (pushed,) = _evaluated("push_face", {"face": front, "distance": 1.0}, [entry], profile)
        assert pushed.kind == kind
        assert Counter(feature.kind for feature in pushed.features.values()) == expected, kind
        # 9 mm tief statt 8; das Netz liegt mit seinen Sehnen innen.
        assert pushed.mesh.volume == pytest.approx(_arched_section(arc) * 9.0, rel=2e-3)
    # Die Vernetzung des exakten Körpers ist der Netzzwilling: dieselben Dreiecke.
    assert tops["brep"] == tops["mesh"]


def _rounded_all_over(shape: str, radius: float) -> Any:
    """Ein Körper, dessen Kanten alle mit ``radius`` verrundet sind (RM-226).

    ``box``: Quader 40 x 30 x 20 — zwölf Kanten, acht Ecken. ``tee``: Balken
    40 x 10 x 10 und Steg 10 x 10 x 40, vereinigt — 24 Kanten, davon die zwei
    Innenkanten als Kehlen, zwölf Ecken. ``unified`` legt die koplanaren
    Teilflächen der Vereinigung zusammen, die das Netz ohnehin als eine
    Facette liest; ohne es führte der exakte Kern die Vorderseite des T als
    vier Flächen.
    """
    from app.core.brep import edit

    if shape == "box":
        return edit.fillet(edit.box(40.0, 30.0, 20.0), radius, "all")
    joined = edit.unified(
        edit.boolean("union", [edit.box(40.0, 10.0, 10.0), edit.box(10.0, 10.0, 40.0)])
    )
    return edit.fillet(joined, radius, "all")


def _through_stl(mesh: MeshData) -> MeshData:
    """Dasselbe Netz als binäre STL hinaus und wie ein Import herein — Ecken in float32."""
    from app.core.geom.mesh import read_mesh

    stream = io.BytesIO()
    trimesh.Trimesh(
        vertices=np.asarray(mesh.raw.vertices), faces=np.asarray(mesh.raw.faces), process=False
    ).export(stream, file_type="stl")
    imported = read_mesh(stream.getvalue(), ".stl")
    # Die Dreiecksfolge bleibt beim Rundlauf, sonst wären die Nummern nicht vergleichbar.
    assert imported.triangle_count == mesh.triangle_count
    assert np.allclose(imported.raw.triangles_center, mesh.raw.triangles_center, atol=1e-4)
    return imported


@pytest.mark.parametrize("form", ["twin", "stl"])
@pytest.mark.parametrize(
    ("shape", "radius", "edges", "corners"),
    [("box", 3.0, 12, 8), ("box", 8.0, 12, 8), ("tee", 3.0, 24, 12), ("tee", 1.0, 24, 12)],
)
def test_a_body_rounded_all_over_carries_the_same_features_on_both_kernels(
    shape: str, radius: float, edges: int, corners: int, form: str
) -> None:
    """Rundungen, die tangential ineinander übergehen, trennt auch das Netz (RM-226).

    Kanten, Kugelecken und die ebenen Flächen zwischen ihnen gehen ohne Knick
    und mit demselben Radius ineinander über; am Netz stand der ganze Verbund
    deshalb als eine gekrümmte Fläche da — am gerundeten T 2 750 von 2 820
    Dreiecken —, am exakten Kern als 24 Kantenrundungen, zwölf Ecken und die
    Flächen dazwischen. Jetzt trennt das Netz an den Dreiecken, deren Ecken auf
    einem Zylinder liegen, und nennt jede Kugelecke, an der verrundete Kanten
    zusammenlaufen, wie der exakte Kern eine Verrundung.

    Geprüft wird die volle Parität: jedes Merkmal mit derselben Art auf
    denselben Dreiecken — die Vernetzung des exakten Körpers ist der
    Netzzwilling, einmal so und einmal nach dem Weg durch eine binäre STL wie
    beim Import — und jede Rundung mit dem gebauten Radius. Die Zahl der
    Kanten und Ecken folgt aus der Konstruktion.
    """
    exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    solid = _rounded_all_over(shape, radius)
    exact = features_of(solid)
    mesh = as_mesh_data(solid)
    found = detect(mesh if form == "twin" else _through_stl(mesh))

    def table(features: dict[str, Feature]) -> dict[tuple[str, frozenset[int]], Feature]:
        return {
            (feature.kind, frozenset(int(index) for index in feature.face_indices)): feature
            for feature in features.values()
        }

    native, twin = table(exact), table(found)
    only_twin = sorted((kind, len(faces)) for kind, faces in twin.keys() - native.keys())
    only_native = sorted((kind, len(faces)) for kind, faces in native.keys() - twin.keys())
    assert (only_twin, only_native) == ([], [])
    rounds = [key for key in native if key[0] == "fillet"]
    assert sum(1 for key in rounds if "axis" in native[key].params) == edges
    assert sum(1 for key in rounds if "axis" not in native[key].params) == corners
    for key in rounds:
        # Am Zwilling bis 1e-6 mm, nach der STL auf das float32-Raster der Ecken.
        assert twin[key].params["radius"] == pytest.approx(
            radius, abs=1e-6 if form == "twin" else 1e-4
        )
        assert ("axis" in twin[key].params) == ("axis" in native[key].params)


def _dome_between_rounded_edges() -> Any:
    """Quader 40 x 30 x 30, die vier senkrechten Kanten R 3, oben eine Kuppel R 60 (RM-226).

    Die Kugel um (0, 0, −32) schneidet jede Seite unter der Deckfläche — an den
    Ecken bei Z 22,5, mitten an der langen Seite bei 26,1, oben bei 28 —, die
    Kuppel ersetzt also die ganze Deckfläche und grenzt an die vier Seiten und
    an die vier verrundeten Kanten.
    """
    from app.core.brep import edit

    box = edit.box(40.0, 30.0, 30.0)
    upright = [
        edit.edge_key(item) for item in edit.edges_of(box) if abs(item.middle[2] - 15.0) <= EPS_GEOM
    ]
    assert len(upright) == 4
    rounded = edit.fillet(box, 3.0, "named", upright)
    ball = edit.moved(edit.sphere(120.0), (0.0, 0.0, -32.0))
    return edit.boolean("intersection", [rounded, ball])


def test_a_dome_between_rounded_edges_stays_a_sphere_on_both_kernels() -> None:
    """Eine Kuppel, an die verrundete Kanten stoßen, ist keine Ecke (RM-226).

    Eine Kugelecke entsteht, wo Kanten mit **demselben** Radius zusammenlaufen,
    und trägt deren Radius. Beide Kerne zählten nur, wie viele Zylinderstücke
    an einer Kugel liegen: Am Minigolfteil Gövde75 aus dem Korpus hieß so eine
    Kuppel Ø 178,6 zwischen Rundungen R 3 und R 7 „Verrundung R 89,3“. Hier
    stoßen vier Rundungen R 3 an eine Kuppel R 60 — sie bleibt an beiden
    Kernen die Kugel Ø 120, die Rundungen bleiben Kantenrundungen, und keine
    Ecke entsteht.
    """
    exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    solid = _dome_between_rounded_edges()
    for kind, found in (("brep", features_of(solid)), ("mesh", detect(as_mesh_data(solid)))):
        domes = [feature for feature in found.values() if feature.kind == "sphere"]
        assert [dome.params["diameter"] for dome in domes] == [pytest.approx(120.0, abs=1e-3)], kind
        rounds = [feature for feature in found.values() if feature.kind == "fillet"]
        assert [("axis" in item.params, item.params["radius"]) for item in rounds] == [
            (True, pytest.approx(3.0, abs=1e-3))
        ] * 4, kind


def _pin_with_a_cove(cove: float) -> Any:
    """Platte 60 x 60 x 6 mit Zapfen Ø 12 x 30, sein Fuß mit ``cove`` ausgekehlt (RM-022)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    from app.core.brep import edit

    plate = edit.moved(edit.box(60.0, 60.0, 6.0), (0.0, 0.0, -6.0))
    joined = edit.boolean("union", [plate, edit.cylinder(12.0, 30.0)])
    foot = []
    for item in edit.edges_of(joined):
        curve = BRepAdaptor_Curve(item.edge)
        if curve.GetType() != GeomAbs_Circle:
            continue
        circle = curve.Circle()
        if abs(circle.Radius() - 6.0) <= EPS_GEOM and abs(circle.Location().Z()) <= EPS_GEOM:
            foot.append(edit.edge_key(item))
    assert foot
    return edit.fillet(joined, cove, "named", foot)


@pytest.mark.parametrize("cove", [2.0, 3.0, 4.0])
def test_a_pin_with_a_cove_is_a_pin_and_a_ring_on_both_kernels(cove: float) -> None:
    """Ein Zapfen mit Hohlkehle am Fuß heißt am Netz Zapfen und Kehle (RM-226, RM-022).

    Mantel und Kehle gehen tangential ineinander über; am Netz lagen beide bei
    R 3 und R 4 in einer gekrümmten Fläche, und der Nachbau fand keinen
    Zapfen. Zapfen und Kehle tragen jetzt an beiden Kernen dieselben Maße aus
    der Konstruktion: Ø 12 und Ring Ø 12 + 2·R aus einer Röhre Ø 2·R. Die
    Kehle reicht am Netz nicht ganz bis an die Platte; ihre unterste Reihe
    liest die Ebenenregel als Facette — sie darf fehlen, aber nichts
    hinzunehmen.
    """
    exact_kernel()
    from collections import Counter

    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    solid = _pin_with_a_cove(cove)
    exact = features_of(solid)
    found = detect(as_mesh_data(solid))
    assert Counter(feature.kind for feature in found.values()) == Counter(
        feature.kind for feature in exact.values()
    )
    ((native_pin, twin_pin),) = [
        (left, right)
        for left in exact.values()
        if left.kind == "pin"
        for right in found.values()
        if right.kind == "pin"
    ]
    assert set(twin_pin.face_indices) == set(native_pin.face_indices)
    assert twin_pin.params["diameter"] == pytest.approx(12.0, abs=1e-6)
    ((native_ring, twin_ring),) = [
        (left, right)
        for left in exact.values()
        if left.kind == "torus"
        for right in found.values()
        if right.kind == "torus"
    ]
    assert set(twin_ring.face_indices) <= set(native_ring.face_indices)
    for ring in (native_ring, twin_ring):
        assert ring.params["diameter"] == pytest.approx(12.0 + 2.0 * cove, abs=1e-6)
        assert ring.params["tube_diameter"] == pytest.approx(2.0 * cove, abs=1e-6)
        assert ring.params["recess"] is True


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_corner_round_refuses_on_both_kernels_with_the_sentence_of_the_panel(
    kind: str, profile: Profile
) -> None:
    """An einer Kugelecke gibt es keine Kante zurückzurechnen — an beiden Kernen gleich gesagt.

    Die Ecke eines rundum verrundeten Quaders heißt an beiden Kernen
    Verrundung, hat aber keine Achse und keine zwei Ebenen neben sich. Das
    Merkmalfenster stellte *Entfernen* und *Radius ändern* trotzdem bereit;
    danach sagte der exakte Kern „Wählen Sie genau eine vollständige
    Rundungsfläche …“, und das Netz wäre an der fehlenden Achse gescheitert.
    Jetzt stehen beide Zeilen grau mit ``edges.NOT_BETWEEN_TWO_PLANES``, und
    die Operation sagt denselben Satz.
    """
    exact_kernel()
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES
    from app.core.perceive.actions import actions_for

    load_operations()
    entry = _object(_rounded_all_over("box", 3.0), kind)
    corner = next(
        feature
        for feature in entry.features.values()
        if feature.kind == "fillet" and "axis" not in feature.params
    )
    rows = {
        action.title: action
        for action in actions_for(corner, entry.features, mesh=as_mesh_data(entry.mesh))
    }
    for name in ("remove_feature", "resize_feature"):
        title = REGISTRY.get(name).title
        assert rows[title].op is None, name
        assert str(rows[title].reason) == str(NOT_BETWEEN_TWO_PLANES), name
    for operation, params in (
        ("remove_feature", {"at_feature": corner.id}),
        ("resize_feature", {"at_feature": corner.id, "diameter": 8.0}),
    ):
        result, _step = _evaluation(operation, params, [entry], profile)
        assert not result.complete, operation
        refusals = [
            str(finding.message)
            for finding in result.scene.report.findings
            if finding.code == f"op.{operation}.GeometryError"
        ]
        assert refusals == [str(NOT_BETWEEN_TWO_PLANES)], operation


@pytest.mark.parametrize("chamfer", [False, True])
def test_a_slot_through_a_sloped_plate_is_as_deep_on_both_kernels(chamfer: bool) -> None:
    """Ein Langloch durch eine schräge Platte ist an beiden Kernen gleich tief (RM-226).

    Die Platte 40 x 40 x 6 ist unten um 4 Grad geneigt, das Langloch Ø 6
    über 20 mm läuft quer zur Neigung hindurch; seine Wand reicht vom
    tiefsten Punkt des tieferen Bogens (y = -10, Z 2 - 10 tan 4°) bis zur
    Oberseite, mit Fase 0,75 an beiden Mündungen um 1,5 mm weniger. Der exakte
    Kern maß nur den ersten Bogen — 3,51 statt 4,70 mm, mit Fase 2,01 statt
    3,20 — und setzte die Mitte auf dessen halbe Höhe; das Netz misst die
    ganze Wand. Über beide Bögen gemessen lag der tiefere Bogen dann noch
    0,042 mm zu tief: Seine Parametergrenzen kamen aus der Näherung des
    schrägen Randes, jetzt misst der exakte Kern an der Form
    (``canonical._rims_on_grid``). Beide Kerne tragen dieselbe Tiefe und
    dieselbe Mitte. Die Fase erklärte den Unterschied nicht: Beide Kerne
    zählen sie nicht mit.
    """
    exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect
    from tests.helpers import sloped_slot_plate

    solid = sloped_slot_plate(chamfer=chamfer)
    expected = 6.0 - (2.0 - 10.0 * math.tan(math.radians(4.0))) - (1.5 if chamfer else 0.0)
    slots = {}
    for kind, found in (("brep", features_of(solid)), ("mesh", detect(as_mesh_data(solid)))):
        (slot,) = [feature for feature in found.values() if feature.kind == "slot"]
        slots[kind] = slot
        assert slot.params["depth"] == pytest.approx(expected, abs=1e-3), kind
    # Die Mitte des Netzes liest die Endringe der vernetzten Wand; an der
    # Fase liegen sie 0,0014 mm über der exakten — innerhalb der Durchbiegung
    # der Vernetzung, vorher 0,59 mm daneben.
    assert slots["brep"].params["centre"] == pytest.approx(
        slots["mesh"].params["centre"], abs=MAX_FACET_SAG
    )


def _plate_with_a_slot_near_the_side(ledge: bool) -> Any:
    """Platte 40 x 30 x 6 mit durchgehendem Langloch Ø 6 über 14 mm bei x = 10 (RM-226).

    ``ledge`` setzt am Rand einen Steg 6 x 30 x 6 auf (x 14 bis 20): Eine Kopie
    über die Seite trifft dann mit ihrer Achse Material und geht nicht mehr
    durch — die Lage des Teppichclips, an dem der Fund auffiel.
    """
    from app.core.brep import edit

    plate = edit.slot_bore(
        edit.box(40.0, 30.0, 6.0),
        position=(10.0, 0.0, 3.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=12.0,
        length=14.0,
        angle_deg=90.0,
        overlap=0.0,
    )
    if not ledge:
        return plate
    return edit.boolean("union", [plate, edit.moved(edit.box(6.0, 30.0, 6.0), (17.0, 0.0, 6.0))])


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(
    ("ledge", "shift", "said"),
    [
        (False, 9.0, ["bore.over_the_edge", "duplicate_feature.feature_lost"]),
        (
            False,
            14.0,
            ["boolean.without_effect", "bore.over_the_edge", "duplicate_feature.feature_lost"],
        ),
        (
            True,
            9.0,
            [
                "bore.over_the_edge",
                "duplicate_feature.feature_lost",
                "duplicate_feature.mouth_covered",
            ],
        ),
    ],
)
def test_a_slot_copied_over_the_side_says_the_same_on_both_kernels(
    kind: str, ledge: bool, shift: float, said: list[str], profile: Profile
) -> None:
    """Eine Langlochkopie über die Seite sagt an beiden Kernen dasselbe (RM-226).

    Am Teppichclip sagte der exakte Kern zur 12 mm quer verdoppelten
    Langlochkopie „nicht als eigenes Merkmal zu erkennen“, das Netz „geht
    nicht mehr durch“ und danach „nicht mehr automatisch wiederzuerkennen“:
    Am Netz prüfte ``_copies_found`` nur Bohrungen und Kegel nach, und den
    Durchgang fragte es auch an einer Kopie, die es nicht gibt. Neben der Seite
    (Verschiebung 12) stand die Kopie am Netz sogar als zweites Langloch im
    Baum. Jetzt nennen beide Kerne die Kante, die verlorene Kopie und — wo das
    Werkzeug ganz daneben liegt — den Schnitt ohne Wirkung, und im Baum steht
    an beiden nur das Original. Die Kopie berührt es nie (x 7 bis 13 gegen
    16 bis 22 und 21 bis 27). Unter dem Steg sagen beide zusätzlich, dass die
    Mündung der Kopie unter Material liegt — am Netz schwieg dieser Satz,
    weil „geht nicht mehr durch“ schon dastand.
    """
    exact_kernel()
    load_operations()
    entry = _object(_plate_with_a_slot_near_the_side(ledge), kind)
    (slot,) = [feature for feature in entry.features.values() if feature.kind == "slot"]
    centre = slot.params["centre"]
    result, step = _evaluation(
        "duplicate_feature",
        {
            "at_feature": slot.id,
            "x": float(centre[0]) + shift,
            "y": float(centre[1]),
            "z": float(centre[2]),
        },
        [entry],
        profile,
    )
    assert sorted(finding.code for finding in result.scene.report.findings) == said
    (output,) = [result.scene.objects[identifier] for identifier in step.outputs]
    assert [feature.kind for feature in output.features.values()].count("slot") == 1


def _sunk_cavity(lift: float) -> float:
    """Hohlraum der Senkbohrung an der schrägen Platte, bis ``lift`` über ihre Randebene.

    Bohrung Ø 6 bis z = 8, darüber der Kegel 90° (Radius ``z − 5``), oben die
    Ebene ``z = 10 + u/4 + lift`` (``u`` längs X ab der Achse). Innerhalb des
    Radius 3 steht die Säule bis zur Ebene, ``9π(10 + lift)``; außerhalb die Höhe
    ``5 + lift − kρ`` mit ``k = 1 − cos φ/4`` bis ``ρ = (5 + lift)/k``. Über den
    Radius integriert ``(5 + lift)³/(6k²) − 4,5(5 + lift) + 9k``, über den Winkel
    mit ∫dφ/k² = 2π/(15/16)^{3/2}.
    """
    head = 5.0 + lift
    turned = 2.0 * math.pi / (15.0 / 16.0) ** 1.5
    return (
        9.0 * math.pi * (10.0 + lift)
        + head**3 * turned / 6.0
        - 9.0 * math.pi * head
        + 18.0 * math.pi
    )


def _sunk_bore(plate: Any) -> Any:
    """Die Senkbohrung aus :func:`_sunk_cavity` auf der Achse x = y = 0 von ``plate``."""
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    outline = [(0.0, -1.0), (3.0, -1.0), (3.0, 8.0), (8.0, 13.0), (0.0, 13.0), (0.0, -1.0)]
    return edit.bore_profile(plate, outline, frame_of((0.0, 0.0, 1.0), (0, 0, 0)))


def _place_of(feature: Feature, targets: list[tuple[float, float]]) -> int | None:
    """Die Nummer des Platzes in ``targets``, auf dessen Achse ``feature`` liegt —
    seitlich bis zur Facettengrenze; ``None`` abseits aller."""
    x, y = (float(value) for value in feature.params["centre"][:2])
    for index, (u, v) in enumerate(targets):
        if math.hypot(x - u, y - v) <= MAX_FACET_SAG:
            return index
    return None


def _copy_twin(case: str) -> tuple[Any, tuple[float, float, float], list[str], float]:
    """Träger, Verschiebung, Befunde und Volumen danach für die Kopie einer Bohrung.

    Die Sollwerte kommen aus der Konstruktion: schräge Platte 40 x 20 (für die
    Kopie quer zur Schräge 40 x 40) mit mittlerer Höhe 10, Stufenplatte 10 000 mm³,
    Bohrung Ø 6 mit ``9π`` je Millimeter Säule. Eine Kopie ist starr: Sie endet an
    den mitbewegten Randebenen, die offene Mündung um die Zugabe aus §39
    (``FEATURE_OVERLAP``) längs ihrer Normale weiter — an der schrägen Ebene senkrecht
    ``FEATURE_OVERLAP · √(1 + 1/16)``. Wo diese Ebene im Material liegt, bleibt dort
    eine Haut, und der Satz heißt „geht nicht mehr durch“.
    """
    from app.core.brep import edit
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.helpers import slanted_plate, stepped_plate

    lift = FEATURE_OVERLAP * math.sqrt(1.0 + 1.0 / 16.0)
    covered = ["duplicate_feature.no_longer_through"]

    def bored(body: Any, x: float) -> Any:
        return edit.cut_bore(
            body, position=(x, 0.0, 5.0), direction=(0.0, 0.0, 1.0), diameter=6.0, depth=60.0
        )

    if case == "along_the_slope":
        bore_volume = 9.0 * math.pi * 10.0
        expected = 8000.0 - bore_volume - 9.0 * math.pi * (10.0 + lift)
        return bored(slanted_plate(), 0.0), (10.0, 0.0, 0.0), covered, expected
    if case == "sunk_along_the_slope":
        expected = 8000.0 - _sunk_cavity(0.0) - _sunk_cavity(lift)
        return _sunk_bore(slanted_plate()), (10.0, 0.0, 0.0), covered, expected
    if case == "across_the_slope":
        return bored(slanted_plate(40.0), 0.0), (0.0, 10.0, 0.0), [], 16000.0 - 180.0 * math.pi
    if case == "over_the_step":
        # Die obere Mündung lag an der Quelle frei; unter dem Aufsatz reicht die
        # Zugabe in ihn hinein.
        expected = 10000.0 - 90.0 * math.pi - 9.0 * math.pi * (10.0 + FEATURE_OVERLAP)
        return bored(stepped_plate(), -10.0), (20.0, 0.0, 0.0), covered, expected
    # Von der Stufe herab: 20 mm Säule durch Aufsatz und Grundplatte, die Kopie
    # trifft nur die 10 mm der Grundplatte und ragt darüber in die Luft.
    return bored(stepped_plate(), 10.0), (-20.0, 0.0, 0.0), [], 10000.0 - 270.0 * math.pi


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize(
    "case",
    [
        "along_the_slope",
        "sunk_along_the_slope",
        "across_the_slope",
        "over_the_step",
        "off_the_step",
    ],
)
def test_a_bore_copied_on_a_slanted_or_stepped_plate_is_the_same_copy_on_both_kernels(
    case: str, quality: Quality, profile: Profile
) -> None:
    """*Merkmal verdoppeln* setzt an beiden Kernen dieselbe Kopie (RM-226, Nachtrag).

    Längs der schrägen Oberseite (z = 10 + x/4) liegt die mitbewegte obere
    Mündung der Kopie im Material. Der exakte Kern führt die Bohrung als Zylinder
    bis zur um die Zugabe verschobenen Randebene, die Senkung als Kegel. Am Netz
    hob ``_past_the_mouths`` den Deckel längs seiner Normale: Die Wand der Kopie
    trug oben ein um 14° geschertes Band von 0,02 mm, das keine Zylinderwand ist.
    Vor der tangentialen Trennung (RM-226 Teil 2) las die Erkennung die ganze Wand
    deshalb als gekrümmte Fläche, und die Kopie hieß am Netz verloren; danach
    zählte sie das Band nicht mit — Tiefe 10,750 gegen 10,771 mm, die Senkung
    Ø 13,333 gegen 13,388 mm. Quer zur Schräge, über und von der Stufe herab sind
    die Zwillinge: Dort steht die Mündung frei oder senkrecht zur Achse.
    """
    exact_kernel()
    load_operations()
    body, travel, codes, expected = _copy_twin(case)
    _placed_alike_on_both_kernels(
        case, "duplicate_feature", body, travel, codes, expected, quality, profile
    )


def _placed_alike_on_both_kernels(
    case: str,
    op: str,
    body: Any,
    travel: tuple[float, float, float],
    codes: list[str],
    expected: float,
    quality: Quality,
    profile: Profile,
    *,
    count: int = 2,
) -> None:
    """``op`` setzt die engste Bohrung von ``body`` um ``travel`` an beiden Kernen gleich.

    Über den echten Auswertungsweg, je Kern: dieselben Befunde (``codes``),
    dieselben Merkmale auf der Achse am Ziel — Art, Durchmesser, Tiefe, Winkel,
    Durchgang und Mitte auf 0,001 mm —, das Volumen am Netz gegen den
    Netz-Zwilling des exakten Ergebnisses auf 0,1 mm³ und das des exakten
    Körpers gegen die Konstruktion (``expected``). Ein Muster setzt die Bohrung
    als Plätze 2 bis ``count`` einer Reihe in Richtung ``travel``; verglichen
    wird jeder Platz.
    """
    said: dict[str, list[str]] = {}
    placed: dict[str, list[Feature]] = {}
    volumes: dict[str, float] = {}
    for kind in ("mesh", "brep"):
        entry = _object(body, kind)
        bore = min(
            (feature for feature in entry.features.values() if feature.kind == "hole"),
            key=lambda feature: float(feature.params["diameter"]),
        )
        x, y, z = (float(value) for value in bore.params["centre"])
        targets = [(x + travel[0] * number, y + travel[1] * number) for number in range(1, count)]
        params: dict[str, Any] = (
            {
                "at_features": (bore.id,),
                "kind": "linear",
                "count": count,
                "spacing": math.hypot(*travel),
                "dx": travel[0],
                "dy": travel[1],
                "dz": travel[2],
            }
            if op == "pattern_feature"
            else {
                "at_feature": bore.id,
                "x": targets[0][0],
                "y": targets[0][1],
                "z": z + travel[2],
            }
        )
        result, step = _evaluation(op, params, [entry], profile, quality=quality)
        said[kind] = sorted(finding.code for finding in result.scene.report.findings)
        (output,) = [result.scene.objects[identifier] for identifier in step.outputs]
        found: list[tuple[int, str, Feature]] = []
        for feature in output.features.values():
            place = _place_of(feature, targets)
            if feature.kind in ("hole", "cone") and place is not None:
                found.append((place, feature.kind, feature))
        found.sort(key=lambda item: item[:2])
        placed[kind] = [feature for _place, _kind, feature in found]
        volumes[kind] = as_mesh_data(output.mesh).volume
        if kind == "brep":
            # Das Volumen des exakten Körpers aus dem Kern, gegen die Konstruktion.
            assert output.mesh.volume == pytest.approx(expected, abs=1e-3), case
    assert said["mesh"] == said["brep"] == codes, (case, said)
    kinds = {kind: [feature.kind for feature in found] for kind, found in placed.items()}
    assert kinds["mesh"] == kinds["brep"] and kinds["mesh"], (case, kinds)
    for mesh_bore, exact_bore in zip(placed["mesh"], placed["brep"], strict=True):
        for name in ("diameter", "depth", "angle"):
            if name in exact_bore.params:
                assert float(mesh_bore.params[name]) == pytest.approx(
                    float(exact_bore.params[name]), abs=1e-3
                ), (case, exact_bore.kind, name)
        assert mesh_bore.params.get("through") == exact_bore.params.get("through"), case
        assert [float(value) for value in mesh_bore.params["centre"]] == pytest.approx(
            [float(value) for value in exact_bore.params["centre"]], abs=1e-3
        ), (case, exact_bore.kind)
    # Volumen je Körper: das Netz gegen den Netz-Zwilling des exakten Ergebnisses.
    assert volumes["mesh"] == pytest.approx(volumes["brep"], abs=0.1), (case, volumes)


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("sunk", [False, True], ids=["bore", "sunk"])
@pytest.mark.parametrize("op", ["move_feature", "pattern_feature"])
def test_a_bore_moved_or_patterned_along_a_slanted_plate_is_the_same_on_both_kernels(
    op: str, sunk: bool, quality: Quality, profile: Profile
) -> None:
    """*Merkmal versetzen* und *Merkmal vervielfachen* längs der Schräge, Geschwister der Kopie.

    Dieselbe Platte (z = 10 + x/4), dieselben 10 mm längs X. Versetzt ist der
    Hohlraum an der alten Stelle zu; vervielfacht bleibt die Quelle und der Platz
    2 der Reihe trägt die Kopie. Beide setzen das Werkzeug der Quelle starr und
    sagen an beiden Kernen „geht nicht mehr durch“ — das Muster dazu, dass es
    steht.
    """
    exact_kernel()
    load_operations()
    body, travel, _codes, expected = _copy_twin(
        "sunk_along_the_slope" if sunk else "along_the_slope"
    )
    if op == "move_feature":
        # Die alte Stelle wird geschlossen: Es fehlt nur der versetzte Hohlraum.
        from app.core.geom.prepare import FEATURE_OVERLAP

        lift = FEATURE_OVERLAP * math.sqrt(1.0 + 1.0 / 16.0)
        expected = 8000.0 - (_sunk_cavity(lift) if sunk else 9.0 * math.pi * (10.0 + lift))
        codes = ["move_feature.no_longer_through"]
    else:
        codes = ["pattern_feature.done", "pattern_feature.no_longer_through"]
    _placed_alike_on_both_kernels(op, op, body, travel, codes, expected, quality, profile)


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_every_place_of_a_sunk_bore_pattern_along_a_slope_gets_its_own_finding(
    quality: Quality, profile: Profile
) -> None:
    """Drei Plätze einer Senkbohrung längs der Schräge, jede Kopie mit eigenem Satz (RM-226).

    Die Bohrung einer Senkbohrung mündet in ihren Kegel und heißt für die
    Erkennung durchgehend, auch wo der Kegel unter Material liegt; exakt fragt
    deshalb je Kopie die Säule (``_exact_through_checked``). Sie schwieg, sobald
    irgendein Satz desselben Codes dastand: Platz 3 blieb am exakten Kern
    durchgehend und ohne Satz, das Netz nannte ihn. Platz 3 liegt 5 mm unter der
    Oberseite und 3,3 mm vor der Stirn — ohne „über die Kante“
    (:func:`test_a_copy_under_the_top_is_not_over_the_edge_on_both_kernels`).
    """
    exact_kernel()
    load_operations()
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.helpers import slanted_plate

    lift = FEATURE_OVERLAP * math.sqrt(1.0 + 1.0 / 16.0)
    body = _sunk_bore(slanted_plate(length=60.0))
    # 60 x 20 bei mittlerer Höhe 10, die Quelle bis zur Oberseite, zwei Kopien
    # bis zur gehobenen Randebene.
    expected = 12000.0 - _sunk_cavity(0.0) - 2.0 * _sunk_cavity(lift)
    codes = ["pattern_feature.done", *["pattern_feature.no_longer_through"] * 2]
    _placed_alike_on_both_kernels(
        "three_places",
        "pattern_feature",
        body,
        (10.0, 0.0, 0.0),
        codes,
        expected,
        quality,
        profile,
        count=3,
    )


def _buried_source(shape: str) -> Any:
    """Die schräge Platte 60 x 20 mit einem Hohlraum bei x = 0, für eine Kopie unter Material.

    ``sink`` ist die Senkbohrung aus :func:`_sunk_cavity`, ``counterbore`` eine
    Bohrung Ø 6 mit Plansenkung Ø 10 ab z = 7, ``slot`` ein Langloch der Breite 6
    längs X mit 8 mm zwischen den Bogenmitten. Alle drei reichen durch.
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of
    from tests.helpers import slanted_plate

    plate = slanted_plate(length=60.0)
    if shape == "sink":
        return _sunk_bore(plate)
    if shape == "counterbore":
        outline = [
            (0.0, -1.0),
            (3.0, -1.0),
            (3.0, 7.0),
            (5.0, 7.0),
            (5.0, 13.0),
            (0.0, 13.0),
            (0.0, -1.0),
        ]
        return edit.bore_profile(plate, outline, frame_of((0.0, 0.0, 1.0), (0, 0, 0)))
    return edit.slot_bore(
        plate,
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=60.0,
        length=8.0,
        angle_deg=0.0,
        overlap=0.0,
    )


def _buried_copy_on_both_kernels(
    shape: str, op: str, travel: float, quality: Quality, profile: Profile
) -> tuple[dict[str, list[str]], dict[str, float]]:
    """Sätze und Volumen je Kern, wenn ``op`` den Hohlraum von :func:`_buried_source`
    um ``travel`` längs X setzt — ein Muster mit drei Plätzen im Abstand ``travel / 2``.
    """
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    body = _buried_source(shape)
    said: dict[str, list[str]] = {}
    volumes: dict[str, float] = {}
    for kind in ("mesh", "brep"):
        mesh = body if kind == "brep" else as_mesh_data(body)
        features = dict(features_of(body) if kind == "brep" else detect(mesh))
        entry = SceneObject(
            id="obj_1", name="Schräge Platte", mesh=mesh, kind=kind, features=features
        )
        wanted = "slot" if shape == "slot" else "hole"
        source = min(
            (feature for feature in features.values() if feature.kind == wanted),
            key=lambda feature: float(feature.params["diameter"]),
        )
        x, y, z = (float(value) for value in source.params["centre"])
        params: dict[str, Any] = (
            {
                "at_features": (source.id,),
                "kind": "linear",
                "count": 3,
                "spacing": travel / 2.0,
                "dx": 1.0,
                "dy": 0.0,
                "dz": 0.0,
            }
            if op == "pattern_feature"
            else {"at_feature": source.id, "x": x + travel, "y": y, "z": z}
        )
        result, step = _evaluation(op, params, [entry], profile, quality=quality)
        said[kind] = sorted(finding.code for finding in result.scene.report.findings)
        (output,) = [result.scene.objects[identifier] for identifier in step.outputs]
        volumes[kind] = as_mesh_data(output.mesh).volume
    return said, volumes


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize(
    ("shape", "op"),
    [
        ("sink", "duplicate_feature"),
        ("sink", "move_feature"),
        ("sink", "pattern_feature"),
        ("counterbore", "duplicate_feature"),
        ("slot", "duplicate_feature"),
    ],
)
def test_a_copy_under_the_top_is_not_over_the_edge_on_both_kernels(
    shape: str, op: str, quality: Quality, profile: Profile
) -> None:
    """Ein Hohlraum, der ganz im Material liegt, ragt nicht über die Kante (RM-226, Nachtrag).

    Die Quelle sitzt bei x = 0 der 60 mm langen schrägen Platte (z = 10 + x/4),
    die Kopie 20 mm bergauf: Ihre mitbewegte Mündung liegt 5 mm unter der
    Oberseite, und ihr Hohlraum endet vor der Stirn bei x = 30 — als Senkung mit
    dem weiten Ende bei x = 26,7, als Plansenkung bei x = 25, als Langloch bei
    x = 27. Die Kantenprüfung dachte den Kegel einer Senkung bis an die
    Oberseite, auch wo er unter der Haut endet, und sein Kranz reichte dort bis
    x = 33,3: Beide Kerne sagten „über die Kante“. Plansenkung und Langloch sind
    die Zwillinge der Prüfung (sie fragen mit ihrem eigenen Durchmesser und
    sagten es nie), Versetzen und Vervielfachen die der Operation. Gefragt:
    dieselben Sätze an beiden Kernen, keiner davon „über die Kante“, das Volumen
    am Netz auf 0,1 mm³ wie am Netz-Zwilling des exakten Ergebnisses.
    """
    exact_kernel()
    load_operations()
    said, volumes = _buried_copy_on_both_kernels(shape, op, 20.0, quality, profile)
    copies = 2 if op == "pattern_feature" else 1
    expected = [f"{op}.no_longer_through"] * copies
    if op == "pattern_feature":
        expected = [f"{op}.done", *expected]
    assert said["mesh"] == said["brep"] == expected, (shape, op, said)
    assert volumes["mesh"] == pytest.approx(volumes["brep"], abs=0.1), (shape, op, volumes)


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_a_buried_sink_reaching_past_the_end_is_over_the_edge_on_both_kernels(
    quality: Quality, profile: Profile
) -> None:
    """Die Gegenrichtung: Unter der Haut, aber seitlich hinaus, bleibt „über die Kante“.

    Um 24 mm verdoppelt reicht das weite Ende der vergrabenen Senkung bis
    x = 30,7 über die Stirn bei x = 30 und schneidet sie an: Die Kopie trägt
    0,48 mm³ weniger ab als ganz im Material. Die Frage nach der Haut
    (``_sink_under_a_skin``) gibt die Senkung nur frei, wenn ihr weites Ende
    ringsum im Material liegt; sonst fragt sie wie zuvor am Austritt.
    """
    exact_kernel()
    load_operations()
    said, volumes = _buried_copy_on_both_kernels(
        "sink", "duplicate_feature", 24.0, quality, profile
    )
    expected = ["bore.over_the_edge", "duplicate_feature.no_longer_through"]
    assert said["mesh"] == said["brep"] == expected, said
    assert volumes["mesh"] == pytest.approx(volumes["brep"], abs=0.1), volumes
