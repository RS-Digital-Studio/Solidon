"""Slots auf eine Oberfläche malen (Bauplan §20, „Bemalen").

Ein Pinsel mit Radius, und Kantenerkennung — letztere macht ihn erst
brauchbar. Einen Radius ohne sie ins Netz zu malen heißt, dass die Farbe um
die Ecke auf die Rückseite des Teils läuft, und das von Hand aufzuräumen
kostet mehr, als das Malen gespart hat.

Also breitet sich der Pinsel über die Oberfläche aus statt durch den Raum: er
beginnt am angeklickten Dreieck und läuft zu Nachbarn, und er hält an einer
Kante an, die schärfer ist als ein gegebener Winkel. Die Oberseite eines
Deckels wird bemalt, die Seite nicht, ohne dass jemand eine Grenze zeichnet.

Die andere Hälfte von §20 — Textur zu Slots — steht in
:mod:`app.core.geom.texture`. Diese hier ist das manuelle Gegenstück: für die
Beschriftung, die keine Textur hat, und zum Korrigieren dessen, was die
Quantisierung falsch getroffen hat.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from typing import cast

import numpy as np

from app.core.geom.mesh import MeshData, as_mesh_data, distances_to_triangles
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, MaterialSlot, OpContext, OpResult, Vec3
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Über diesem Winkel zwischen zwei Dreiecken hält der Pinsel an. Dreißig Grad
#: halten ihn auf einer gerundeten Fläche und stoppen ihn an allem, was sich
#: wie eine Kante liest.
EDGE_ANGLE = 30.0

#: Wie viele Filamente eine Slotnummer benennen darf (§20, wie bei den
#: Farb-Operationen).
MAX_SLOTS = 8


@dataclasses.dataclass(frozen=True, slots=True)
class BrushResult:
    """Der bemalte Körper und wie viele Dreiecke der Pinsel wirklich traf.

    Getrennt, weil die zweite Zahl nirgends sonst herkommt: Wie viele Dreiecke
    am Ende in einem Slot sitzen, sagt :func:`app.core.geom.attributes.counts`
    — aber das ist der **Bestand** und nicht der Strich. Bei Slot 0 sind die
    beiden Zahlen so weit auseinander, wie sie nur sein können: Ein Netz ohne
    Slots gilt ganz als Slot 0, also meldete ein Klick ins Leere die volle
    Dreieckszahl als Erfolg.
    """

    mesh: MeshData
    painted: int


def brush(
    mesh: MeshData,
    point: Vec3,
    radius: float,
    slot: int,
    *,
    edge_angle: float = EDGE_ANGLE,
) -> BrushResult:
    """Bemalt jedes Dreieck um ``point``, das zur selben Oberfläche gehört.

    Erreicht über die Oberfläche, nicht durch die Luft: ein Lauf von Nachbar
    zu Nachbar, der an scharfen Kanten und am Radius endet. Beide Grenzen
    zählen — der Radius allein malte durch eine Wand, die Kante allein eine
    ganze Seite.

    **Gemessen wird zur Dreiecksfläche, nicht zum Schwerpunkt** (§18.5,
    :func:`app.core.geom.mesh.distance_to_triangles`). Die Deckfläche der
    Platte aus dem Korpus besteht aus zwei Dreiecken von 60 auf 40 Millimeter; ihr Schwerpunkt
    liegt gut zwanzig Millimeter von der Mitte entfernt. Ein Klick genau dorthin
    — die naheliegendste Geste überhaupt — fand mit einem Pinselradius von zehn
    Millimetern kein einziges Dreieck und meldete „keine Fläche zu treffen".
    Dieselbe Rechnung begrenzt den Umfang: Ein Radius, der an den Schwerpunkten
    gemessen wird, hört an einem großen Dreieck auf, bevor er es erreicht.
    """
    body = mesh.raw
    faces = len(body.faces)
    if not faces or radius <= EPS_GEOM:
        return BrushResult(mesh=mesh, painted=0)

    triangles = np.asarray(body.triangles, dtype=float)
    away = distances_to_triangles(triangles, np.asarray(point, dtype=float))
    start = int(np.argmin(away))
    if away[start] > radius:
        # Der Strich ist nicht auf dem Körper gelandet. Ein nächstes Dreieck
        # gibt es immer, und es zu bemalen, weil es das nächste war, setzte
        # Farbe auf die andere Seite des Teils als die, auf die jemand
        # geklickt hat.
        return BrushResult(mesh=mesh, painted=0)

    within = away <= radius
    reached = _walk(mesh, start, within, edge_angle)

    slots = list(mesh.slots) if mesh.slots else [0] * faces
    for index in reached:
        slots[index] = int(slot)
    _log.info("painted %d of %d faces into slot %d", len(reached), faces, slot)
    return BrushResult(mesh=MeshData(raw=body, slots=tuple(slots)), painted=len(reached))


def _walk(mesh: MeshData, start: int, within: np.ndarray, edge_angle: float) -> set[int]:
    """Flächen, die von ``start`` aus erreichbar sind, ohne eine Kante oder
    den Radius zu überschreiten.
    """
    adjacency = np.asarray(mesh.raw.face_adjacency)
    if not len(adjacency):
        return {start} if within[start] else set()

    angles = np.degrees(np.asarray(mesh.raw.face_adjacency_angles, dtype=float))
    passable = angles <= edge_angle

    neighbours: dict[int, list[int]] = {}
    for (first, second), open_edge in zip(adjacency, passable, strict=True):
        if not open_edge:
            continue
        neighbours.setdefault(int(first), []).append(int(second))
        neighbours.setdefault(int(second), []).append(int(first))

    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for other in neighbours.get(current, ()):
            if other in seen or not within[other]:
                continue
            seen.add(other)
            queue.append(other)
    return seen


@op_params
class PaintParams(BaseParams):
    slot: int = param(
        title=_("Slot"),
        default=1,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        doc=_("In welchen Materialslot der Pinsel malt."),
    )
    radius: float = param(
        title=_("Radius"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=500.0,
        doc=_("Wie weit der Strich um den Klickpunkt herum reicht."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        doc=_("Wo geklickt wurde. Beim Malen trägt der Klick die drei Werte selbst ein."),
        placement="advanced",
    )
    y: float = param(
        title=_("Position Y"),
        default=0.0,
        unit="mm",
        doc=_("Zweite Achse des Klickpunkts."),
        placement="advanced",
    )
    z: float = param(
        title=_("Position Z"),
        default=0.0,
        unit="mm",
        doc=_("Dritte Achse des Klickpunkts."),
        placement="advanced",
    )
    edge_angle: float = param(
        title=_("Kantenwinkel"),
        default=EDGE_ANGLE,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=180.0,
        placement="advanced",
        doc=_("Ab diesem Winkel hält der Pinsel an. 180 Grad heißt: über alles hinweg."),
    )
    name: str = param(
        title=_("Bezeichnung"),
        default="",
        placement="advanced",
        doc=_("Name des Slots, etwa das Filament. Erscheint im 3MF beim Farbwechsel."),
    )


@register_op(
    name="paint_slot",
    title=_("Bemalen"),
    category="colour",
    params=PaintParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Malt einen Materialslot auf die Fläche um einen Punkt. Der Pinsel läuft "
        "über die Oberfläche und hält an Kanten an, statt um die Ecke zu malen."
    ),
)
def paint_slot(ctx: OpContext) -> OpResult:
    params = cast(PaintParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    stroke = brush(
        mesh,
        (params.x, params.y, params.z),
        params.radius,
        params.slot,
        edge_angle=params.edge_angle,
    )
    covered = stroke.painted
    if not covered:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="colour.nothing_painted",
                    severity="warning",
                    message=_("An dieser Stelle war keine Fläche zu treffen."),
                    object_id=source.id,
                    values={"radius_mm": round(params.radius, 2)},
                )
            ],
        )

    known = {entry.index: entry for entry in source.material_slots}
    known.setdefault(
        params.slot,
        MaterialSlot(
            index=params.slot, name=params.name or f"{_('Slot').translate()} {params.slot}"
        ),
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=stroke.mesh,
                material_slots=[known[index] for index in sorted(known)],
            )
        ],
        findings=[
            Finding(
                code="colour.painted",
                severity="info",
                message=_("Die Fläche wurde bemalt."),
                object_id=source.id,
                values={"faces": covered, "slot": params.slot},
            )
        ],
    )
