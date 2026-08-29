"""Weiches Verschmelzen zweier Körper (Bauplan §25, Konzept P16 Entscheidung N).

Die gewöhnliche Vereinigung stößt zwei Oberflächen aneinander und lässt in
jeder Innenecke eine scharfe Kehle stehen. Gedruckt ist genau dort die
Sollbruchstelle, und mit keinem Werkzeug dieser Anwendung war sie zu
erreichen: Ein Pinsel kommt nicht an eine Innenkante, und eine Verrundung auf
Mesh-Kanten steht nicht ohne Grund auf der Nicht-bauen-Liste.

Deshalb rechnet diese Operation anders als alle anderen booleschen. Statt
Flächen zu schneiden legt sie beide Körper als **Abstandsfeld** auf ein
gemeinsames Raster, mischt die zwei Felder weich ineinander und zieht die neue
Oberfläche als Isofläche daraus. Der Übergang entsteht dabei nicht als
nachträgliche Verrundung, sondern als das, was das gemischte Feld ohnehin
beschreibt.

Der Preis ist ein Rasterverfahren: Was zwischen zwei Rasterpunkten liegt, wird
interpoliert, und scharfe Kanten der Ausgangskörper werden weicher, als sie
waren. Das wird ausgewiesen, nicht verschwiegen — genau wie die Voxelstufe der
Rückfallkette es tut (§17.3).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Final, cast

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from app.core.errors import Action, NotManifoldError, ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    ProgressFn,
)
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Rasterpunkte sich noch rechnen lassen. Darüber ist nicht die
#: Maschine zu langsam, sondern die Rasterweite falsch gewählt — die Meldung
#: sagt genau das und nennt die Weite, die noch geht.
MAX_SAMPLES: Final = 12_000_000

#: Wie weit das Raster über die Körper hinausreicht, in Rasterweiten. Der
#: Wulst wächst über die Hülle der Ausgangskörper hinaus, und Marching Cubes
#: braucht ringsherum eine Lage, in der das Feld eindeutig außen ist.
MARGIN_CELLS: Final = 3.0

#: Um wie viel Zelle das Raster gegenüber den Körpern versetzt liegt.
#:
#: Kein Beiwerk: Ein achsparalleler Quader mit runden Maßen legt seine Flächen
#: sonst genau auf die Rasterpunkte. Dort ist das Abstandsfeld exakt null,
#: Marching Cubes findet keinen Vorzeichenwechsel und spannt entartete
#: Dreiecke auf — gemessen an einem 40x30x20-Quader: 793 Bruchstücke statt
#: eines Körpers, und drei Prozent zu viel Volumen. Der Wert ist mit Absicht
#: kein einfacher Bruch; eine halbe Zelle träfe bei halben Maßen wieder.
GRID_OFFSET: Final = 0.37

#: Wie viel gröber das Raster im Entwurf ist. Anders als bei den
#: Vernetzungsoperationen ist die Rasterweite hier keine Zusage über das
#: Ergebnis, sondern der Preis für seine Genauigkeit — und im Entwurf wird
#: iteriert, nicht abgenommen.
DRAFT_FACTOR: Final = 2.0

#: Wie viele Rasterpunkte auf einmal gegen den Baum gefragt werden. Groß genug,
#: dass der Aufruf sich lohnt, klein genug, dass ein Abbruch in einem
#: Sekundenbruchteil ankommt — gemessen rund 0,3 s je Portion.
FIELD_CHUNK: Final = 400_000


def _surface_points(mesh: MeshData, spacing: float) -> tuple[np.ndarray, np.ndarray]:
    """Die Oberfläche als Punktwolke mit Normalen, dichter als das Raster.

    Deterministisch unterteilt, nicht zufällig abgetastet: Ein Startwert wäre
    hier eine Streuzahl in einer Operation, die ohne auskommt (Regel 9).

    Die Wolke muss feiner sein als das Raster, sonst misst der Abstand zum
    nächsten Punkt etwas anderes als den Abstand zur Fläche — an einem groben
    Dreieck liegt die Mitte weit von jeder Ecke.

    **Dreiecksmitten mit Flächennormalen, nicht Eckpunkte mit gemittelten
    Normalen.** Eine Eckpunktnormale ist der Mittelwert der angrenzenden
    Flächen; an der Deckkante eines Zylinders steht sie deshalb 45 Grad
    schräg, und für einen Punkt senkrecht über der Deckfläche kippt damit das
    Vorzeichen. Gemessen an einem Zylinder von 30 mm Länge: Die Hülle reichte
    von -54,9 bis -8,6 statt von -47 bis -17 — acht Millimeter Geometrie an
    beiden Enden, die es nicht gibt, und ein Volumen vier Prozent zu hoch. Eine
    Flächennormale gilt für ihre Fläche und für keine andere; über
    Dreiecksmitten gerechnet trifft dieselbe Hülle auf ein Zehntel genau.
    """
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(mesh.raw.vertices, dtype=float),
        np.asarray(mesh.raw.faces, dtype=np.int64),
        max_edge=spacing,
    )
    dense = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    dense.merge_vertices()
    return (
        np.asarray(dense.triangles_center, dtype=float),
        np.asarray(dense.face_normals, dtype=float),
    )


def distance_field(
    mesh: MeshData,
    grid: np.ndarray,
    spacing: float,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> np.ndarray:
    """Abstand zur Oberfläche für jeden Rasterpunkt: positiv innen, negativ außen.

    Welche Normale das sein muss, steht in :func:`_surface_points` — die
    Antwort hat ein Paket gekostet.

    **Das Vorzeichen kommt aus der Normale, nicht aus einem Strahl.** Der
    naheliegende Weg wäre ``Trimesh.contains``; der lief über ``rtree``, und
    ein Lauf über 75 000 Rasterpunkte endete in einer Zugriffsverletzung.
    Seit dem 24.08.2026 ist ``rtree`` ganz aus dem Prozess — heute bräche
    ``contains`` mit trimeshs ``ExceptionWrapper`` ab, nicht mit einer
    Korruption. Die Bauart hier bleibt richtig: kein Index, keine Abhängigkeit
    an einer Stelle, die 75 000 Fragen stellt.

    **Und nicht aus einem Belegungsgitter.** Der zweite naheliegende Weg,
    ``voxelized().fill()`` mit einer Distanztransformation darauf, ist billig
    und um eine halbe Zelle zu groß: Er markiert jede Zelle, die der Körper
    berührt, und misst danach ab Zellmitte. Gemessen an einer Kugel mit 25 mm
    Radius sind das acht Prozent zu viel Volumen — bei einem Verfahren, dessen
    Genauigkeit ohnehin am Raster hängt, ist das der falsche Ort zum Sparen.
    """
    points, normals = _surface_points(mesh, spacing)
    tree = cKDTree(points)
    field = np.empty(len(grid), dtype=float)
    # **In Portionen, damit ein Abbruch ankommt** (§15.6). Ein einziger
    # ``query`` über zehn Millionen Rasterpunkte ist ein nativer Aufruf und
    # kooperativ nicht zu unterbrechen: Verschmelzen mit Rasterweite 0,5
    # rechnete gemessen 9,2 Sekunden, in denen der Abbrechen-Knopf nichts tat.
    # Die Portionen kosten nichts messbares — ``workers=-1`` lastet die Kerne
    # innerhalb einer Portion genauso aus.
    for start in range(0, len(grid), FIELD_CHUNK):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        block = grid[start : start + FIELD_CHUNK]
        # Über alle Kerne: bei 356 000 Rasterpunkten sind es 1,5 statt 9,6
        # Sekunden, bei identischem Ergebnis.
        away, index = tree.query(block, workers=-1)
        outward = np.einsum("ij,ij->i", block - points[index], normals[index])
        field[start : start + len(block)] = np.where(outward > 0.0, -away, away)
        if progress is not None:
            done = min(start + FIELD_CHUNK, len(grid)) / max(len(grid), 1)
            progress(done, str(_("Abstandsfeld rechnen")))
    return field


def _share(progress: ProgressFn | None, offset: float) -> ProgressFn | None:
    """Die zweite Hälfte des Balkens für den zweiten Körper.

    Zwei Abstandsfelder, ein Fortschritt: Ohne die Verschiebung liefe der
    Balken zweimal von null bis eins, und das liest sich wie ein Neustart.
    """
    if progress is None:
        return None
    return lambda fraction, text: progress(offset + fraction / 2.0, text)


def _smooth_maximum(first: np.ndarray, second: np.ndarray, radius: float) -> np.ndarray:
    """Die weiche Vereinigung zweier Felder — innen ist positiv, also Maximum.

    Ohne Radius das gewöhnliche Maximum, und damit die gewöhnliche
    Vereinigung. Mit Radius wird zwischen beiden Feldern über eine Breite von
    ``radius`` überblendet und das Ergebnis in der Mitte um ``radius/4``
    angehoben; genau dort, wo beide Flächen sich treffen, wächst deshalb
    Material nach.
    """
    if radius <= 0.0:
        return np.asarray(np.maximum(first, second), dtype=float)
    share = np.clip(0.5 + 0.5 * (first - second) / radius, 0.0, 1.0)
    blended = second * (1.0 - share) + first * share
    return np.asarray(blended + radius * share * (1.0 - share), dtype=float)


def _too_fine(wanted: int, grid: float) -> ValidationError:
    """Sagt, welche Rasterweite noch ginge.

    Die Zahl kennt nur die Operation: Halbieren der Weite verachtfacht die
    Rasterpunkte, also lässt sich die erreichbare Weite ausrechnen. Aufgerundet
    auf zwei Stellen, damit der Vorschlag nicht die Zahl nennt, die er gerade
    abgelehnt hat.
    """
    reachable = math.ceil(grid * (wanted / MAX_SAMPLES) ** (1.0 / 3.0) * 100.0) / 100.0
    return ValidationError(
        field="grid",
        detail=_("Diese Rasterweite ergäbe mehr Punkte, als sich noch rechnen lassen."),
        value=grid,
        constraint="maximum",
        values={"samples": wanted, "limit": MAX_SAMPLES, "reachable": reachable},
        suggestions=(
            Action(id="use_reachable", label=_("Die feinste Rasterweite nehmen, die noch geht.")),
            Action(id="smaller_bodies", label=_("Die Körper einzeln verschmelzen.")),
        ),
    )


def blend_bodies(
    first: MeshData,
    second: MeshData,
    radius: float,
    grid: float,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> MeshData:
    """Beide Körper über ein gemeinsames Abstandsfeld weich vereinigen.

    ``progress`` und ``cancelled`` reichen bis in die Feldrechnung hinein und
    nicht nur bis vor sie: Dort liegt die Zeit, und ein Abbruch, der erst
    danach greift, ist keiner (§15.6).
    """
    for source in (first, second):
        if not source.raw.is_watertight or source.volume <= 0.0:
            raise NotManifoldError(
                detail=_(
                    "Dieser Körper umschließt kein Volumen — ohne ein Innen gibt es kein "
                    "Abstandsfeld und keinen weichen Übergang. Erst reparieren, dann noch "
                    "einmal."
                ),
                open_edges=int(len(source.raw.edges_unique) * 2 - len(source.raw.faces) * 3),
            )

    margin = radius + grid * MARGIN_CELLS
    low = np.minimum(first.raw.bounds[0], second.raw.bounds[0]) - margin + grid * GRID_OFFSET
    high = np.maximum(first.raw.bounds[1], second.raw.bounds[1]) + margin
    shape = tuple(math.ceil(value) + 1 for value in (high - low) / grid)

    wanted = int(np.prod(shape))
    if wanted > MAX_SAMPLES:
        raise _too_fine(wanted, grid)

    axes = [low[axis] + np.arange(shape[axis]) * grid for axis in range(3)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)

    merged = _smooth_maximum(
        distance_field(first, points, grid, progress=_share(progress, 0.0), cancelled=cancelled),
        distance_field(second, points, grid, progress=_share(progress, 0.5), cancelled=cancelled),
        radius,
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    # **Der Rand muss zu sein**, wie beim Gitter (`lattice.py`): Marching Cubes
    # zeichnet nur, wo das Feld sein Vorzeichen wechselt. Endet die Fläche am
    # Rand des Rasters, ist das Ergebnis offen — und ein offenes Netz fällt in
    # jeder folgenden booleschen Operation bis auf die Voxelstufe durch.
    field = np.pad(merged.reshape(shape), 1, constant_values=-(margin + grid))
    from skimage import measure

    vertices, faces, _normals, _values = measure.marching_cubes(
        field, 0.0, spacing=(grid, grid, grid)
    )
    # Die Polsterung verschiebt den Ursprung um einen Schritt je Achse zurück.
    body = trimesh.Trimesh(vertices=vertices + low - grid, faces=faces, process=True)
    body.fix_normals()
    _log.info(
        "blended %d and %d triangles into %d over %d samples",
        first.triangle_count,
        second.triangle_count,
        len(body.faces),
        wanted,
    )
    return first.replacing(body)


# --- operation --------------------------------------------------------------------


@op_params
class BlendParams(BaseParams):
    radius: float = param(
        title=_("Übergang"),
        default=3.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Wie breit die Kehle zwischen beiden Körpern zuwächst. Null gibt die "
            "gewöhnliche Vereinigung. Einen Spalt überbrückt er ab etwa dem Dreifachen "
            "seiner Breite."
        ),
    )
    grid: float = param(
        title=_("Rasterweite"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=10.0,
        doc=_(
            "Wie fein gerechnet wird. Kleiner heißt genauer und deutlich langsamer — "
            "Kanten unter dieser Weite gehen verloren."
        ),
    )


@register_op(
    name="blend_union",
    title=_("Weich verschmelzen"),
    category="boolean",
    params=BlendParams,
    consumes=2,
    produces=1,
    keeps_inputs=1,
    doc=_(
        "Vereinigt zwei Körper mit einem fließenden Übergang statt einer scharfen Kehle. "
        "Für Griffe, Verstrebungen und alles, was gedruckt nicht an der Innenecke reißen soll."
    ),
    caveat=_(
        "Nicht an einem Teil, dessen Maße zählen: Das Ergebnis entsteht auf einem Raster, "
        "und scharfe Kanten der Ausgangskörper werden dabei weicher. Wo eine Passung sitzt, "
        "gehört die gewöhnliche Vereinigung hin."
    ),
)
def blend_union(ctx: OpContext) -> OpResult:
    """Zwei Körper hinein, einer heraus — mit einem Wulst in der Naht."""
    params = cast(BlendParams, ctx.params)
    first, second = (as_mesh_data(entry.mesh) for entry in ctx.inputs[:2])
    grid = params.grid * (DRAFT_FACTOR if ctx.quality == "draft" else 1.0)

    merged = blend_bodies(
        first,
        second,
        params.radius,
        grid,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )

    findings = [
        Finding(
            code="blend.rastered",
            severity="info",
            message=_(
                "Der Übergang wurde auf einem Raster gerechnet — Kanten unter der "
                "Rasterweite sind dabei weicher geworden."
            ),
            object_id=ctx.inputs[0].id,
            values={"grid_mm": round(grid, 3), "radius_mm": round(params.radius, 3)},
        )
    ]
    if merged.component_count > 1:
        findings.append(
            Finding(
                code="blend.still_apart",
                severity="warning",
                message=_(
                    "Die Körper berühren sich nicht und liegen weiter auseinander als der "
                    "Übergang breit ist — sie sind nebeneinander geblieben, nicht verbunden."
                ),
                object_id=ctx.inputs[0].id,
                values={"components": merged.component_count},
            )
        )
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=merged, features={})],
        findings=findings,
    )
