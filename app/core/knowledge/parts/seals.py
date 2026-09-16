"""Dichtnuten und getrennte Dichtungen aus einem geschlossenen gezeichneten Weg."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.geom.seal import seal_geometry
from app.core.knowledge.parts.registry import (
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.registry import op_params, param
from app.core.types import BaseParams, Feature, FeatureKind, PartResult
from app.core.units import EPS_GEOM
from app.i18n import _

_ADDED = PartChange("1", "2026-09-15", "Dichtnut und getrennte Dichtung mit gemeinsamem Dichtweg.")
if TYPE_CHECKING:
    from app.core.sketch.profile import Profile as SketchProfile

_DEFAULT_PATH = (
    '{"plane":"plane:xy","elements":[{"kind":"circle",'
    '"points":[[0.0,0.0],[20.0,0.0]]}],"constraints":['
    '{"kind":"distance","targets":[0,1],"value":"20.000000000"},'
    '{"kind":"fixed","targets":[0]}]}'
)


@op_params
class PathParams(BaseParams):
    path_sketch: str = param(
        title=_("Dichtweg"),
        default=_DEFAULT_PATH,
        kind="sketch",
        required=True,
        doc=_("Ein geschlossener gezeichneter Verlauf bildet die Mitte des Dichtrings."),
    )
    offset: float = param(
        title=_("Seitlicher Versatz"),
        default=0.0,
        minimum=-5.0,
        maximum=5.0,
        unit="mm",
        placement="advanced",
        doc=_("Positiv verschiebt den ganzen Dichtweg nach außen, negativ nach innen."),
    )


@op_params
class GrooveParams(PathParams):
    width: float = param(
        title=_("Nutbreite"),
        default=3.0,
        minimum=1.2,
        maximum=12.0,
        unit="mm",
        doc=_("Gesamte Breite der Nut quer zum Dichtweg."),
    )
    depth: float = param(
        title=_("Nuttiefe"),
        default=2.0,
        minimum=0.5,
        maximum=12.0,
        unit="mm",
        doc=_("Tiefe unter der angeklickten Mündung; der Nutboden liegt darunter."),
    )


@op_params
class GasketParams(PathParams):
    section: str = param(
        title=_("Dichtquerschnitt"),
        default="rectangle",
        choices=("rectangle", "round"),
        doc=_("Rechteckige Dichtung oder runde Schnur entlang desselben geschlossenen Wegs."),
    )
    width: float = param(
        title=_("Dichtungsbreite"),
        default=2.6,
        minimum=1.2,
        maximum=12.0,
        unit="mm",
        depends_on=("section", ("rectangle",)),
        doc=_("Breite des rechteckigen Querschnitts quer zum Dichtweg."),
    )
    height: float = param(
        title=_("Dichtungshöhe"),
        default=2.4,
        minimum=1.2,
        maximum=12.0,
        unit="mm",
        doc=_("Unverformte Höhe; beim runden Querschnitt zugleich der Schnurdurchmesser."),
    )


def _profile(text: str) -> SketchProfile:
    """Die gemeinsame Skizzengrammatik lösen; der Part-Kontext löst Ausdrücke vorher."""
    from app.core.sketch.profile import profile_of
    from app.core.sketch.serialize import sketch_from_text
    from app.core.sketch.solver import solve_sketch

    return profile_of(solve_sketch(sketch_from_text(text)))


def _surface(mesh: MeshData, name: str, mask: np.ndarray, kind: FeatureKind) -> Feature:
    """Nur tatsächliche Dreiecke und ihre flächengewichteten Maße benennen."""
    indices = np.flatnonzero(mask)
    raw = mesh.raw
    areas = raw.area_faces[indices]
    centre = np.average(raw.triangles_center[indices], weights=areas, axis=0)
    values = {"area": float(areas.sum()), "centre": tuple(float(v) for v in centre)}
    if kind == "face":
        values["normal"] = tuple(float(v) for v in raw.face_normals[indices[0]])
    return Feature(
        id=name,
        kind=kind,
        provenance="generated",
        params=values,
        face_indices=tuple(int(index) for index in indices),
        recognised=False,
    )


def seal_features(mesh: MeshData, *, gasket: bool, rounded: bool = False) -> dict[str, Feature]:
    """Geometrisch belegte Kontakt-, Boden- und Mantelbereiche eines neuen Rings."""
    normals = mesh.raw.face_normals
    if rounded:
        # Die runde Schnur berührt an einer Linie, nicht an einer Planfläche.
        # Oberes und unteres Band bleiben dennoch echte auswählbare Dreiecke.
        top, bottom = normals[:, 2] > EPS_GEOM, normals[:, 2] < -EPS_GEOM
        return {
            "gasket_contact": _surface(mesh, "gasket_contact", top, "curved_face"),
            "gasket_bottom": _surface(mesh, "gasket_bottom", bottom, "curved_face"),
        }
    top = normals[:, 2] >= 1 - EPS_GEOM
    bottom = normals[:, 2] <= -1 + EPS_GEOM
    side = np.abs(normals[:, 2]) < 1 - EPS_GEOM
    upper = "gasket_contact" if gasket else "groove_mouth"
    lower = "gasket_bottom" if gasket else "groove_floor"
    mantle = "gasket_walls" if gasket else "groove_walls"
    return {
        upper: _surface(mesh, upper, top, "face"),
        lower: _surface(mesh, lower, bottom, "face"),
        mantle: _surface(mesh, mantle, side, "curved_face"),
    }


@register_part(
    name="seal_groove",
    title=_("Dichtnut"),
    group="structure",
    params=GrooveParams,
    subtractive=True,
    features=("groove_mouth", "groove_floor", "groove_walls"),
    wall=WallRequirement.not_applicable("Abtragendes Werkzeug; Restwand wird am Träger geprüft."),
    changes=[_ADDED],
    doc=_("Schneidet eine durchgängige Nut unter der gewählten Fläche entlang einer Zeichnung."),
    caveat=_("Die Restwand unter und neben der Nut muss am Träger geprüft werden."),
)
def seal_groove(raw: BaseParams) -> PartResult:
    p = cast(GrooveParams, raw)
    geometry = seal_geometry(
        _profile(p.path_sketch),
        groove_width=p.width,
        groove_depth=p.depth,
        protrusion=0,
        gasket_width=p.width,
        offset=p.offset,
    )
    return PartResult(mesh=geometry.groove, features=seal_features(geometry.groove, gasket=False))


@register_part(
    name="seal_gasket",
    title=_("Separate Dichtung"),
    group="structure",
    params=GasketParams,
    standalone=True,
    separate_from_host=True,
    features=("gasket_contact", "gasket_bottom", "gasket_walls"),
    feature_requirements=(
        FeatureRequirement("gasket_contact"),
        FeatureRequirement("gasket_bottom"),
        FeatureRequirement("gasket_walls", when="section", equals="rectangle"),
    ),
    changes=[_ADDED],
    doc=_("Erzeugt eine eigenständige Dichtung mit rechteckigem oder rundem Querschnitt."),
    caveat=_("Die Geometrie beschreibt die unverformte Dichtung; sie belegt keine Dichtheit."),
)
def seal_gasket(raw: BaseParams) -> PartResult:
    p = cast(GasketParams, raw)
    geometry = seal_geometry(
        _profile(p.path_sketch),
        groove_width=max(p.width, p.height),
        groove_depth=p.height,
        protrusion=0,
        gasket_width=p.width,
        section=p.section,
        offset=p.offset,
    )
    shifted = geometry.gasket.raw.copy()
    shifted.apply_translation((0, 0, p.height))
    mesh = MeshData.of(shifted)
    return PartResult(
        mesh=mesh, features=seal_features(mesh, gasket=True, rounded=p.section == "round")
    )
