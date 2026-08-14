"""Displacement über ein Höhenfeld (Bauplan §25, Konzept P16 Entscheidung G).

Ein Bild wird zur Geometrie: Jeder Eckpunkt wandert entlang seiner Normale um
so viel, wie das Bild an seiner Stelle hell ist. Damit lässt sich ein Relief,
eine Prägung oder eine Struktur auf eine Fläche legen, für die keine Skizze
taugt — Holzmaserung, Leder, ein Wappen.

**Getrennt vom Pinsel, weil es einen anderen Charakter hat.** Es ist ein
*Wert*, kein Handgriff: Ein Displacement ändert man, indem man eine Zahl
ändert, und genau dafür ist der Stapel gemacht. Der Agent darf es deshalb auch
setzen — Leitprinzip 5 verbietet ihm Koordinaten, nicht Zahlen.

Es schließt an ``texture_ops`` an und ist zugleich dessen Gegenstück: Die
Texturen dort sind exakte Gitter aus gutem Grund („wer dieselbe Form über ein
Höhenfeld abtastet, bekommt an jeder Kante die Auflösung des Rasters"), hier
*ist* das Höhenfeld der Zweck. Dieselbe Prüfung gilt trotzdem für beide — ein
Relief flacher als eine Schichthöhe wird nicht gedruckt.
"""

from __future__ import annotations

import dataclasses
import io
import math
from typing import Final, cast

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS, Action, ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Feature, Finding, OpContext, OpResult
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Eckpunkte ein Netz mindestens haben muss, damit ein Höhenfeld
#: sich darauf zeigen kann — als Vielfaches der Bildpunkte je Achse. Unter
#: einem Eckpunkt je zwei Bildpunkten ist das Ergebnis nicht falsch, sondern
#: leer, und niemand wüsste warum.
POINTS_PER_PIXEL: Final = 0.5

#: Wie viele Schichthöhen ein Relief mindestens hoch sein muss. Eine halbe
#: Schicht druckt der Drucker nicht; er rundet sie weg, und übrig bleibt eine
#: glatte Fläche und eine Stunde Wartezeit.
MIN_LAYERS: Final = 1.0

#: Die vier Arten, ein rechteckiges Bild auf einen Körper zu legen.
PROJECTIONS: Final[tuple[str, ...]] = ("planar", "cylindrical", "spherical", "face")


def sample_image(payload: bytes) -> np.ndarray:
    """Das Bild als Feld zwischen null und eins.

    Grau statt Farbe: Ein Höhenfeld hat eine Zahl je Ort, und welche der drei
    Farbkanäle sie sein soll, ist eine Frage, die niemand beantworten will.
    Schwarz ist null, weiß ist eins; die Stärke der Operation macht daraus
    Millimeter.
    """
    if not payload:
        raise _no_image()
    import imageio.v3 as iio

    try:
        raw = iio.imread(io.BytesIO(payload), mode="L")
    except PROGRAMMING_ERRORS:
        # ``mode="L"`` ist ein Argument, das eine künftige Fassung anders nennen
        # kann. Ein TypeError daraus heißt nicht, dass das Bild kaputt ist.
        raise
    except Exception as stumble:  # imageio wirft je Format etwas anderes
        raise _unreadable(stumble) from stumble
    field = np.asarray(raw, dtype=float)
    if field.ndim != 2 or not field.size:
        raise _unreadable(None)
    low, high = float(field.min()), float(field.max())
    if high - low < 1e-9:
        # Ein einfarbiges Bild ist kein Fehler — es ist ein Relief der Höhe
        # null, und das ist eine gültige Antwort auf „was soll hier passieren".
        return np.zeros_like(field)
    return (field - low) / (high - low)


def at(field: np.ndarray, row: float, column: float) -> float:
    """Ein Wert zwischen den Bildpunkten, bilinear.

    Mit dem nächsten Nachbarn bekäme jedes Pixel eine Stufe, und aus einem
    weichen Relief würde eine Treppe mit der Auflösung des Bildes — genau der
    Vorwurf, den ``texture_ops`` an Höhenfelder richtet, und hier ist er zu
    vermeiden statt zu erben.
    """
    return float(_bilinear(field, np.array([row]), np.array([column]))[0])


def _bilinear(field: np.ndarray, rows: np.ndarray, columns: np.ndarray) -> np.ndarray:
    """Dasselbe für viele Punkte auf einmal — die Form, die die Op braucht."""
    height, width = field.shape
    y = np.clip(rows, 0.0, 1.0) * (height - 1)
    x = np.clip(columns, 0.0, 1.0) * (width - 1)
    y0 = np.clip(np.floor(y).astype(int), 0, height - 1)
    x0 = np.clip(np.floor(x).astype(int), 0, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    x1 = np.minimum(x0 + 1, width - 1)
    dy, dx = y - y0, x - x0
    top = field[y0, x0] * (1.0 - dx) + field[y0, x1] * dx
    bottom = field[y1, x0] * (1.0 - dx) + field[y1, x1] * dx
    return np.asarray(top * (1.0 - dy) + bottom * dy, dtype=float)


def _face_frame(feature: Feature) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Zwei Richtungen in der Ebene einer erkannten Fläche, dazu ihr Mittelpunkt.

    Der Hilfsvektor kommt aus der schwächsten Achse der Normale — ein fester
    wäre genau dort entartet, wo er parallel zu ihr steht, also an jeder
    achsparallelen Fläche. Derselbe Griff wie beim Pinselring im Viewport, und
    aus demselben Grund.
    """
    normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    length = float(np.linalg.norm(normal))
    normal = normal / length if length > 1e-12 else np.array([0.0, 0.0, 1.0])
    other = np.zeros(3)
    other[int(np.argmin(np.abs(normal)))] = 1.0
    first = np.cross(normal, other)
    first /= np.linalg.norm(first)
    second = np.cross(normal, first)
    centre = np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    return first, second, centre


def _coordinates(
    mesh: MeshData, projection: str, face: Feature | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Wo jeder Eckpunkt im Bild liegt — Zeile und Spalte, je zwischen 0 und 1.

    Vier Arten, und jede beantwortet dieselbe Frage anders: Welche zwei Maße
    des Körpers sollen die zwei Maße des Bildes sein?
    """
    points = np.asarray(mesh.raw.vertices, dtype=float)
    low, high = points.min(axis=0), points.max(axis=0)
    size = np.maximum(high - low, 1e-9)

    if projection == "cylindrical":
        # Um die Z-Achse gewickelt: der Winkel ist die Bildbreite, die Höhe die
        # Bildhöhe. An einem Rohr ist das die einzige Projektion ohne Naht mit
        # doppeltem Relief.
        centre = (low + high) / 2.0
        angle = np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0])
        return (points[:, 2] - low[2]) / size[2], (angle + math.pi) / (2.0 * math.pi)
    if projection == "spherical":
        centre = (low + high) / 2.0
        towards = points - centre
        radius = np.maximum(np.linalg.norm(towards, axis=1), 1e-9)
        angle = np.arctan2(towards[:, 1], towards[:, 0])
        return np.arccos(np.clip(towards[:, 2] / radius, -1.0, 1.0)) / math.pi, (
            angle + math.pi
        ) / (2.0 * math.pi)
    if projection == "face" and face is not None:
        # Auf die Ebene einer erkannten Fläche: Das Bild liegt so darauf, wie
        # es aussähe, wenn man senkrecht daraufsieht. Die einzige Projektion,
        # die ein Merkmal braucht — und die einzige, die auf einer schrägen
        # Fläche nicht verzerrt.
        first, second, centre = _face_frame(face)
        towards = points - centre
        along = towards @ first
        across = towards @ second
        span = max(float(np.ptp(along)), float(np.ptp(across)), 1e-9)
        return (across - across.min()) / span, (along - along.min()) / span
    # Planar: von oben auf die XY-Ebene, die häufigste und einzige, bei der
    # ein rechteckiges Bild rechteckig bleibt.
    return (points[:, 1] - low[1]) / size[1], (points[:, 0] - low[0]) / size[0]


def displaced(
    mesh: MeshData,
    field: np.ndarray,
    *,
    strength: float,
    projection: str = "planar",
    middle: float = 0.0,
    smooth: int = 0,
    face: Feature | None = None,
) -> MeshData:
    """Jeden Eckpunkt entlang seiner Normale um den Bildwert verschieben.

    ``middle`` legt fest, welcher Grauwert die Fläche in Ruhe lässt: Bei null
    hebt das Bild nur an, bei 0,5 hebt weiß und senkt schwarz. Das ist der
    Unterschied zwischen einem Stempel und einer Prägung.

    Wie beim Pinsel ändert sich die Topologie nicht — es kommen keine Dreiecke
    dazu. Wer ein feines Relief auf ein grobes Netz legen will, braucht vorher
    Eckpunkte; die Operation misst das und sagt es (Entscheidung E).
    """
    body = mesh.raw
    if abs(strength) < 1e-12:
        return mesh
    rows, columns = _coordinates(mesh, projection, face)
    heights = _bilinear(field, rows, columns) - middle
    if smooth > 0:
        heights = _relaxed(body, heights, smooth)
    normals = np.asarray(body.vertex_normals, dtype=float)
    moved = np.asarray(body.vertices, dtype=float) + normals * (heights * strength)[:, None]
    built = trimesh.Trimesh(vertices=moved, faces=body.faces, process=False)
    _log.info("displaced %d vertices by up to %.3f mm", len(moved), abs(strength))
    return mesh.replacing(built)


def _relaxed(body: trimesh.Trimesh, heights: np.ndarray, rounds: int) -> np.ndarray:
    """Die Höhen über die Nachbarschaft mitteln, so oft wie verlangt.

    Geglättet wird das **Feld**, nicht der Körper: Ein Bild mit hartem Rand
    ergibt sonst eine Kante, die kein Drucker trifft, und den Körper danach zu
    glätten nähme auch das mit, was vorher da war.
    """
    edges = np.asarray(body.edges, dtype=np.int64)
    for _round in range(rounds):
        total = np.zeros(len(heights))
        seen = np.zeros(len(heights))
        np.add.at(total, edges[:, 0], heights[edges[:, 1]])
        np.add.at(seen, edges[:, 0], 1.0)
        heights = np.where(seen > 0, total / np.maximum(seen, 1.0), heights)
    return heights


def _no_image() -> ValidationError:
    return ValidationError(
        field="source",
        detail=_("Für ein Relief fehlt das Bild."),
        constraint="required",
        suggestions=(
            Action(id="pick_image", label=_("Ein Bild wählen.")),
            Action(id="use_texture", label=_("Stattdessen ein gerechnetes Muster nehmen.")),
        ),
    )


def _unreadable(stumble: object | None) -> ValidationError:
    return ValidationError(
        field="source",
        detail=_(
            "Diese Datei lässt sich nicht als Bild lesen. Ein Relief braucht ein "
            "Graustufenbild — PNG, JPEG oder TIFF."
        ),
        constraint="unreadable",
        values={"reason": str(stumble)[:120]} if stumble is not None else {},
        suggestions=(
            Action(id="pick_image", label=_("Ein anderes Bild wählen.")),
            Action(id="use_texture", label=_("Stattdessen ein gerechnetes Muster nehmen.")),
        ),
    )


# --- operation --------------------------------------------------------------------


@op_params
class DisplaceParams(BaseParams):
    source: str = param(
        title=_("Bild"),
        kind="source",
        doc=_("Das Graustufenbild, dessen Helligkeit zur Höhe wird. Hell steht hoch."),
    )
    strength: float = param(
        title=_("Höhe"),
        default=1.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_("Wie hoch das Relief wird — der Abstand zwischen schwarz und weiß."),
    )
    projection: str = param(
        title=_("Auflegen"),
        default="planar",
        choices=PROJECTIONS,
        doc=_(
            "Wie das rechteckige Bild auf den Körper kommt: von oben, um die Achse "
            "gewickelt oder über die Kugel."
        ),
    )
    at_feature: str = param(
        title=_("Fläche"),
        kind="feature",
        default="",
        placement="advanced",
        doc=_(
            "Auf welche erkannte Fläche das Bild gelegt wird. Nur für „Auf eine Fläche“ — "
            "die anderen Arten brauchen keine."
        ),
    )
    middle: float = param(
        title=_("Nulllage"),
        default=0.0,
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_(
            "Welcher Grauwert die Fläche in Ruhe lässt. Null trägt nur auf; ein halb "
            "hebt und senkt — der Unterschied zwischen Stempel und Prägung."
        ),
    )
    smooth: int = param(
        title=_("Weichzeichnen"),
        default=0,
        minimum=0,
        maximum=20,
        placement="advanced",
        doc=_(
            "Wie oft die Höhen über die Nachbarn gemittelt werden. Nimmt harte Ränder "
            "aus einem Bild, das für den Druck zu scharf gezeichnet ist."
        ),
    )


@register_op(
    name="displace_image",
    title=_("Relief auflegen"),
    category="surface",
    params=DisplaceParams,
    consumes=1,
    produces=1,
    doc=_(
        "Macht aus der Helligkeit eines Bildes eine Höhe auf der Oberfläche. Für "
        "Maserung, Prägung und Wappen — alles, wofür keine Skizze taugt."
    ),
    caveat=_(
        "Nicht auf ein grobes Netz: Ein Relief zeigt sich nur, wo Eckpunkte sind, und "
        "unter einem Eckpunkt je zwei Bildpunkten bleibt vom Bild nichts übrig. Erst "
        "gleichmäßig vernetzen."
    ),
)
def displace_image(ctx: OpContext) -> OpResult:
    """Ein Bild als Geometrie — und die Frage, ob der Drucker es hergibt."""
    params = cast(DisplaceParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    field = sample_image(ctx.sources.read(params.source) if ctx.sources else b"")

    after = displaced(
        before,
        field,
        strength=params.strength,
        projection=params.projection,
        middle=params.middle,
        smooth=params.smooth,
        face=_chosen_face(source, params),
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=_displacement_findings(before, field, params, ctx, source.id),
    )


def _chosen_face(source: object, params: DisplaceParams) -> Feature | None:
    """Die Fläche, auf die projiziert wird — oder ein Satz, warum es keine gibt.

    Nur die eine Projektion braucht sie. Fehlt sie dort, ist das kein Grund für
    ein stilles Ausweichen auf „von oben": Das Ergebnis sähe fast richtig aus
    und läge auf der falschen Ebene.
    """
    if params.projection != "face":
        return None
    features = getattr(source, "features", {}) or {}
    found = features.get(params.at_feature) if params.at_feature else None
    if found is None:
        raise ValidationError(
            field="face",
            detail=_(
                "Für „Auf eine Fläche“ fehlt die Fläche. Klicken Sie eine an, bevor Sie "
                "das Relief auflegen."
            ),
            constraint="required",
            values={"known": sorted(features)},
            suggestions=(
                Action(id="pick_face", label=_("Eine Fläche anklicken.")),
                Action(id="use_planar", label=_("Stattdessen von oben auflegen.")),
            ),
        )
    return cast(Feature, found)


def _displacement_findings(
    before: MeshData,
    field: np.ndarray,
    params: DisplaceParams,
    ctx: OpContext,
    object_id: str,
) -> list[Finding]:
    """Zwei Fragen, die der Bildschirm nicht beantwortet.

    Ob das Netz das Bild überhaupt tragen kann, und ob der Drucker das Relief
    hergibt. Beides ist nichts, was man am Ergebnis sieht — die erste Antwort
    ist ein leeres Ergebnis, die zweite eine Stunde Wartezeit für eine glatte
    Fläche.
    """
    findings = [
        Finding(
            code="displace.applied",
            severity="info",
            message=_("Das Bild wurde als Höhe auf die Oberfläche gelegt."),
            object_id=object_id,
            values={"height_mm": round(params.strength, 3), "pixels": int(field.shape[0])},
        )
    ]

    wanted = max(field.shape) * POINTS_PER_PIXEL
    if before.vertex_count < wanted * wanted:
        findings.append(
            Finding(
                code="displace.too_coarse",
                severity="warning",
                message=_(
                    "Das Netz hat zu wenige Eckpunkte für dieses Bild — vom Relief bleibt "
                    "kaum etwas übrig. Erst gleichmäßig vernetzen."
                ),
                object_id=object_id,
                values={"vertices": before.vertex_count, "wanted": int(wanted * wanted)},
            )
        )

    layer = ctx.profile.printer.layer_height if ctx.profile else 0.2
    if 0.0 < params.strength < layer * MIN_LAYERS:
        findings.append(
            Finding(
                code="displace.too_shallow",
                severity="warning",
                message=_(
                    "Dieses Relief ist flacher als eine Druckschicht — es wird nicht sichtbar sein."
                ),
                object_id=object_id,
                values={"height_mm": round(params.strength, 3), "layer_mm": round(layer, 3)},
            )
        )
    return findings
