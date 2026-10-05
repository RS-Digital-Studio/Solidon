"""Weiches Verschmelzen zweier Körper (Bauplan §25, Konzept P16 Entscheidung N).

Die gewöhnliche Vereinigung stößt zwei Oberflächen aneinander und lässt in
jeder Innenecke eine scharfe Kehle stehen. Gedruckt ist genau dort die
Sollbruchstelle.

**Verrunden erreicht sie inzwischen** — der Vorbehalt „Verrundungen auf
Mesh-Kanten" ist am 10.09.2026 gefallen, und die Naht ist ein gewöhnlicher
Kantenzug: An einer Platte mit aufgesetzter Rippe kommen aus ``edges_of``
24 Züge, vier davon konkav. Es ist trotzdem etwas anderes. Eine Verrundung
legt einen festen Radius an eine **gewählte** Kante, nachdem die Vereinigung
schon gerechnet ist; sie kennt nur noch das Ergebnis. Diese Operation lässt
den Übergang aus **beiden** Körpern zugleich entstehen — niemand wählt eine
Kante, und wo die Naht keine saubere Linie hergibt, gibt es trotzdem einen
Übergang.

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

from app.core.deferred import cKDTree, trimesh
from app.core.errors import (
    CORRECT_INPUT,
    Action,
    NotManifoldError,
    ValidationError,
)
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.registry.params import ZERO_NONE
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

#: Bis zu wie vielen Rasterpunkten der Entwurf fein rechnet (RM-379). Gröber
#: wurde vorher immer, und die Figur im Fenster wich bis 2 mm vom Export ab,
#: ohne dass jemand es sagte. Gemessen am Leistungsfall aus §31 (zwei
#: gekreuzte Rohre Ø 20, Übergang 6, Raster 1 mm): rund 243 000 Punkte in
#: 1,5 s — eine Wartezeit, die beim Formen noch trägt. Darüber greift der
#: Entwurfsfaktor, und der Befund ``blend.draft`` sagt es.
DRAFT_SAMPLES: Final = 250_000

#: Ab wie vielen Dreiecken beider Eingänge die Oberfläche im Budget mitzählt
#: (RM-427). Die Abstandsfelder kosten nicht nur je Rasterpunkt, sondern mit
#: der Oberfläche: gemessen (Review 02.10., ``v5g_rm379_schwer``) bei 241 200
#: Punkten an 81 920 Dreiecken 0,75 s, bei 244 800 Punkten an 327 680
#: Dreiecken 3,8 s — gegen 0,9 s mit dem Entwurfsfaktor. Bis hierher zählen
#: nur die Rasterpunkte; darüber wiegt jeder Punkt so viel mehr, wie die
#: Oberfläche größer ist.
DRAFT_SURFACE: Final = 100_000

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

    **Gemessen wird der Weg zur Ebene des nächsten Dreiecks, nicht zu seiner
    Mitte** (Befund Robert, 18.09.2026: „weich verschmelzen, fehlerhaft,
    abgefranste kanten" und „nach verschmelzen sind seiten auch in schichten
    zerfallen, eine seite 43 schichten"). Beides war dasselbe: Die
    Oberflächenwolke ist **diskret**, und der Weg zum nächsten *Punkt* fällt
    vor einer ebenen Wand je nach Lage des Rasterpunkts ein wenig zu lang aus
    — wellig, mit der Periode der Wolke. Gemessen an einem Quader von
    40 auf 30 auf 20 mit einem Turm darauf, Rasterweite 1,0: 0,031 mm
    Streuung, 2,015 Grad Normalenabweichung, und die linke Wand zerfiel in
    **67 koplanare Gruppen**. Die Erkennung liest daraus Streifen, der Kunde
    sieht Schichten, und die Kante dazwischen sieht ausgefranst aus.

    Der Weg zur **Ebene** ist an einer ebenen Wand exakt — dieselbe Wand kam
    danach mit 0,000 mm Streuung und als **eine** Fläche zurück. An einer
    gewölbten unterschätzt er um das, was das Rasterverfahren ohnehin rundet:
    Über zwei Kugeln, einen liegenden und einen stehenden Zylinder gemessen
    liegt der Volumenunterschied bei 0,006 bis 0,030 Prozent, alle drei
    geschlossen und einteilig — und die Hüllmaße treffen ihr Sollmaß jetzt
    genau (40 auf 40 auf 35 statt 40,028 auf 40,03 auf 35,036).

    Das Vorzeichen ändert sich dabei nicht: Es steckte schon in dieser
    Projektion, sie lieferte bisher nur das Vorzeichen und nicht den Betrag.
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
        _away, index = tree.query(block, workers=-1)
        outward = np.einsum("ij,ij->i", block - points[index], normals[index])
        field[start : start + len(block)] = -outward
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


def _grid(
    first: MeshData, second: MeshData, radius: float, grid: float
) -> tuple[np.ndarray, tuple[int, ...]]:
    """Prüft die Eingänge vor Ursprung und Punktzahl je Achse des gemeinsamen Rasters."""
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
    return low, tuple(math.ceil(value) + 1 for value in (high - low) / grid)


def draft_grid(first: MeshData, second: MeshData, radius: float, grid: float) -> float:
    """Die Rasterweite für den Entwurf: die feine, solange sie im Budget bleibt.

    Gröber nur, wo die feine Weite :data:`DRAFT_SAMPLES` übersteigt (RM-379),
    die Punkte gewogen mit der Oberfläche über :data:`DRAFT_SURFACE` (RM-427).
    Dieselbe Regel gilt für jede Operation mit Entwurfsfaktor; heute hat ihn
    nur diese — Kegel und Ring rechnen im Entwurf so fein wie beim Export.
    """
    _low, shape = _grid(first, second, radius, grid)
    surface = first.triangle_count + second.triangle_count
    weight = max(1.0, surface / DRAFT_SURFACE)
    if int(np.prod(shape)) * weight <= DRAFT_SAMPLES:
        return grid
    return grid * DRAFT_FACTOR


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
    low, shape = _grid(first, second, radius, grid)
    margin = radius + grid * MARGIN_CELLS
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
        zero_text=ZERO_NONE,
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
    result_kind="mesh",
    # Das Abstandsfeld misst seit dem 18.09.2026 zur Ebene des nächsten
    # Dreiecks statt zu seiner Mitte (siehe :func:`distance_field`). Ein
    # Ergebnis aus dem Cache trüge sonst weiter die gewellten Wände. 3 seit dem
    # 22.09.2026: Die Filamente beider Körper kommen mit (:func:`_with_filaments`).
    # 4: Auch die Entwurfsplanung prüft die Eingänge vor Bounds und Punktbudget.
    cache_version="5",
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
    grid = (
        draft_grid(first, second, params.radius, params.grid)
        if ctx.quality == "draft"
        else params.grid
    )

    merged = blend_bodies(
        first,
        second,
        params.radius,
        grid,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
    merged = _with_filaments(merged, first, second, params.radius + grid)

    findings = [
        Finding(
            code="blend.rastered",
            severity="info",
            message=_(
                "Der Übergang wurde auf einem Raster gerechnet — Kanten, die feiner "
                "sind als das Raster, sind dabei weicher geworden."
            ),
            object_id=ctx.inputs[0].id,
            values={"grid_mm": round(grid, 3), "radius_mm": round(params.radius, 3)},
        )
    ]
    if grid > params.grid:
        findings.append(
            Finding(
                code="blend.draft",
                severity="info",
                message=_(
                    "Im Fenster rechnet der Übergang in Entwurfsauflösung, damit das Formen "
                    "flüssig bleibt. Export und Druckvorbereitung rechnen fein."
                ),
                object_id=ctx.inputs[0].id,
                values={"grid_mm": round(grid, 3)},
            )
        )
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
                # Regel 17: Die Breite des Übergangs steht im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    from app.core.geom.ops import _material_slots_after_boolean

    return OpResult(
        outputs=[
            dataclasses.replace(
                ctx.inputs[0],
                mesh=merged,
                features={},
                material_slots=_material_slots_after_boolean(ctx, "union", merged),
            )
        ],
        findings=findings,
    )


def _with_filaments(merged: MeshData, first: MeshData, second: MeshData, reach: float) -> MeshData:
    """Die Filamente beider Körper auf die neue Oberfläche übertragen (§20).

    Das Rasterverfahren baut eine ganz neue Oberfläche, und
    :meth:`MeshData.replacing` lässt eine Slotliste fallen, die nicht mehr zur
    Dreieckszahl passt — bis zum 22.09.2026 kam jedes verschmolzene Teil
    einfarbig in Slot 0 heraus. Dieselbe Pflicht wie nach der Voxelstufe der
    Rückfallkette: Wer neu vernetzt, überträgt die Slots neu
    (``attributes.transfer``).

    ``reach`` ist, wie weit ein Dreieck von einer alten Oberfläche liegen darf
    und ihr Filament noch bekommt: Die Kehle wächst um bis zu ``radius`` aus
    der Naht, das Raster verschiebt jede Wand um bis zu eine Weite. Was
    weiter liegt, bekommt das häufigste Filament des ersten Körpers — er ist
    der, dessen Name und Material bleiben.
    """
    from app.core.geom.attributes import counts, transfer

    if not first.slots and not second.slots:
        return merged
    usual = counts(first)
    fallback = max(usual, key=lambda slot: (usual[slot], -slot))
    return transfer(merged, [first, second], cut_slot=fallback, tolerance=reach)
