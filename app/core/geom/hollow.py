"""Aushöhlen, mit den Entlüftungen, die es druckbar machen (Bauplan §25).

Ein massives Teil ist Material und Stunden, die niemand braucht. Es
auszuhöhlen ist eine gute Idee mit einer Bedingung: Harz und ungeschmolzenes
Pulver beiseite — ein FDM-Druck mit geschlossenem Hohlraum sperrt Luft ein,
und die erste Brücke darüber sackt durch. Die Entlüftung ist hier also keine
Option — sie ist die zweite Hälfte der Operation, und die Vorgabe.

Wie die Innenwand gefunden wird: der Körper kommt auf dasselbe Raster wie die
Analysekarten (§18.4), das Raster wird um die Wandstärke erodiert, und was
übrig bleibt, wird neu vernetzt. Das ist die Voxelstufe aus §17.2 mit ihrer
Genauigkeit und ihrer Ehrlichkeit — die Wand stimmt auf einen halben
Rasterschritt, und der Bericht sagt es.

Ein Versatz auf den Dreiecken selbst wäre exakt und faltete sich an jeder
konkaven Ecke ein — genau dort, wo ein hohles Teil die Wand am nötigsten
braucht.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Finding, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie fein das Raster ist, relativ zur stehenbleibenden Wand. Ein Drittel der
#: Wand heißt: die Wand stimmt auf ein Sechstel ihrer selbst.
PITCH_SHARE = 1.0 / 3.0

#: Nie feiner als das — ein Raster aus hundert Millionen Zellen hilft niemandem.
MIN_PITCH = 0.3

#: Vorgabe-Durchmesser der Entlüftung. Weit genug, damit Luft entweicht, eng
#: genug, dass das Loch danach nicht verschlossen werden muss.
VENT_DIAMETER = 4.0


@dataclass(slots=True)
class HollowResult:
    """Der hohle Körper, und was dazu zu sagen war."""

    mesh: MeshData
    removed: float = 0.0
    """Volumen, das entfernt wurde, in mm³."""
    vents: tuple[Vec3, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def hollow(
    mesh: MeshData,
    wall: float,
    *,
    vents: int = 1,
    vent_diameter: float = VENT_DIAMETER,
    open_top: bool = False,
) -> HollowResult:
    """Lässt eine Wand von ``wall`` Millimetern stehen und nimmt den Rest
    heraus.

    ``open_top`` nimmt zusätzlich die Decke über dem Hohlraum weg. Damit ist
    das Ergebnis eine Dose statt eines geschlossenen Körpers, und *Deckel
    erzeugen* findet die Öffnung, die es verlangt — der Weg dorthin führte
    sonst über zwei Zylinder und eine Differenz.
    """
    if wall <= EPS_GEOM:
        raise ValueError("a wall thickness has to be positive")

    field = _inner_field(mesh, wall)
    cavity = _meshed(field[0], field[1], field[2], mesh) if field is not None else None
    if cavity is None or cavity.triangle_count == 0:
        return HollowResult(
            mesh=mesh,
            findings=[
                Finding(
                    code="hollow.too_thin",
                    severity="warning",
                    message=_("Für diese Wandstärke bleibt kein Hohlraum übrig."),
                    values={"wall_mm": round(wall, 2)},
                )
            ],
        )

    before = mesh.volume
    outcome = boolean("difference", [mesh, cavity])
    body = outcome.mesh
    findings = list(outcome.findings)

    if open_top and field is not None:
        opening = _mouth(field[0])
        tool = _meshed(opening, field[1], field[2], mesh) if opening is not None else None
        if tool is None:
            findings.append(
                Finding(
                    code="hollow.no_opening",
                    severity="warning",
                    message=_(
                        "Die Decke ließ sich nicht öffnen — der Hohlraum reicht "
                        "nicht bis unter die Oberseite."
                    ),
                )
            )
        else:
            opened = boolean("difference", [body, tool])
            body = opened.mesh
            findings.extend(opened.findings)

    placed: tuple[Vec3, ...] = ()
    # Eine offene Dose ist ihre eigene Entlüftung. Ein Loch im Boden wäre dort
    # kein Schutz vor der durchsackenden Decke, sondern ein Loch im Boden.
    if vents > 0 and not open_top:
        body, placed = _vent(body, cavity, vent_diameter, vents)
        if not placed:
            findings.append(
                Finding(
                    code="hollow.no_vent",
                    severity="warning",
                    message=_(
                        "Es war keine Stelle für eine Entlüftung zu finden — "
                        "ein geschlossener Hohlraum drückt beim Drucken die Decke hoch."
                    ),
                )
            )

    removed = before - body.volume
    _log.info("hollowed out %.1f mm³ behind a %.2f mm wall", removed, wall)
    findings.append(
        Finding(
            code="hollow.done",
            severity="info",
            message=_("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."),
            values={
                "wall_mm": round(wall, 2),
                "removed_cm3": round(removed / 1000.0, 1),
                "vents": len(placed),
            },
        )
    )
    return HollowResult(mesh=body, removed=removed, vents=placed, findings=findings)


def _inner_field(mesh: MeshData, wall: float) -> tuple[np.ndarray, Vec3, float] | None:
    """Das Raster des Körpers, eingezogen um die Wandstärke.

    Getrennt von der Vernetzung, weil zwei Dinge daraus entstehen: der
    Hohlraum, der herausgeschnitten wird, und die Öffnung, die ihn nach oben
    freilegt. Zweimal zu rastern wäre derselbe Lauf über dieselben Dreiecke.
    """
    from scipy import ndimage

    from app.core.perceive.maps import solid_field

    pitch = max(wall * PITCH_SHARE, MIN_PITCH)
    field = solid_field(mesh, pitch)
    steps = max(1, round(wall / pitch))
    inner = ndimage.binary_erosion(field.filled, iterations=steps)
    if not inner.any():
        return None
    return inner, field.origin, pitch


def _meshed(matrix: np.ndarray, origin: Vec3, pitch: float, like: MeshData) -> MeshData | None:
    """Ein Rasterkörper als Netz, an seinem Platz."""
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=matrix, pitch=pitch)
    body.apply_translation(np.asarray(origin, dtype=float))
    return like.replacing(body) if len(body.faces) else None


def _cavity(mesh: MeshData, wall: float) -> MeshData | None:
    """Das Innere des Körpers, eingezogen um die Wandstärke."""
    inner = _inner_field(mesh, wall)
    if inner is None:
        return None
    return _meshed(inner[0], inner[1], inner[2], mesh)


def _mouth(matrix: np.ndarray) -> np.ndarray | None:
    """Das Raster der Öffnung: der oberste Querschnitt des Hohlraums, nach oben
    durchgezogen.

    Der oberste und nicht die Vereinigung aller — eine Dose soll ihre Decke
    verlieren, nicht ihre Schulter. Wo der Hohlraum nach oben zuläuft, wird die
    Öffnung entsprechend enger; das ist bei einer Kugel wenig sinnvoll und bei
    allem, was wie ein Behälter aussieht, genau richtig.

    Nach oben bis an den Rand des Rasters, und der liegt eine Zelle über dem
    Körper (``solid_field`` legt ihn dort hin). Damit ragt das Werkzeug hinaus,
    statt eine Fläche mit dem Deckel zu teilen (§39).
    """
    levels = np.flatnonzero(matrix.any(axis=(0, 1)))
    if not len(levels):
        return None
    top = int(levels[-1])
    opening = np.zeros_like(matrix)
    opening[:, :, top:] = matrix[:, :, top][:, :, None]
    return opening if opening.any() else None


def _vent(
    body: MeshData, cavity: MeshData, diameter: float, count: int
) -> tuple[MeshData, tuple[Vec3, ...]]:
    """Bohrt vom Hohlraum nach unten durch den Boden.

    Nach unten mit Absicht: eine Entlüftung in der Bodenfläche sitzt auf der
    Druckplatte, wo sie weder zu sehen noch im Weg ist, und die Luft entweicht
    in der Richtung, in der der Druck wächst.
    """
    from app.core.geom.transform import apply, translation

    inside = cavity.bounds
    outside = body.bounds
    if inside.size[2] <= EPS_GEOM:
        return body, ()

    spots: list[Vec3] = []
    for index in range(count):
        # Entlang X über die Mitte des Hohlraums verteilt, damit mehrere
        # Entlüftungen nicht in derselben Ecke landen.
        share = (2 * index + 1) / (2 * count)
        x = inside.minimum[0] + inside.size[0] * share
        spots.append((float(x), float(inside.centre[1]), 0.0))

    drilled = body
    placed: list[Vec3] = []
    height = float(outside.size[2]) + 4.0
    for spot in spots:
        tool = trimesh.creation.cylinder(radius=diameter / 2.0, height=height)
        tool = apply(
            MeshData.of(tool),
            translation((spot[0], spot[1], float(outside.minimum[2]) + height / 2.0 - 2.0)),
        )
        try:
            drilled = boolean("difference", [drilled, tool]).mesh
        except PROGRAMMING_ERRORS:
            raise
        except Exception as problem:  # eine Entlüftung, die nicht geht, ist nicht fatal
            _log.info("vent at %s failed: %s", spot, problem)
            continue
        placed.append(spot)
    return drilled, tuple(placed)
