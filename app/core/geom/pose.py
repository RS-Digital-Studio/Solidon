"""Posing: ein Skelett, eine Stellung (Bauplan §25, Konzept P16 Entscheidung I).

Ein Knochenbaum liegt im Körper, jeder Knochen bekommt drei Winkel, und die
Eckpunkte folgen. Drei Streichungen machen das gegenüber einem
Animationsprogramm klein, und alle drei sind Absicht:

* **Eine Pose, keine Animation.** Gedruckt wird ein Zustand. Keine Zeitachse,
  keine Interpolation, keine Kurven — das ist der größte Streichposten.
* **Vorwärtskinematik reicht.** Inverse Kinematik ist Komfort beim Animieren
  langer Ketten; bei einer einzigen Pose an einem Modell mit acht Knochen ist
  sie es nicht wert.
* **Gewichte werden gerechnet, nicht gespeichert.** Aus dem Abstand zum
  Knochensegment mit einem Abfall darüber. Gespeicherte Gewichte wären ein
  zweiter Dokumentbegriff neben dem Stapel — und beim nächsten Vernetzen
  darunter falsch, ohne dass jemand es merkt.

Der Punkt, an dem Posing hierher gehört und nicht zu Blender, ist der vierte:
**ein Gelenkwinkel darf ein Projektparameter sein.** ``=@arm_angle`` in einer
Pose, und die Passung am Sockel rechnet mit.
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping, Sequence
from typing import Final, cast

import numpy as np

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import Action, ValidationError
from app.core.expressions import evaluate, is_expression, references
from app.core.geom import transform
from app.core.geom.mesh import MeshData, as_mesh_data, ray_hits_batch
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Bone, Finding, OpContext, OpResult, Pose, Vec3, as_vec3
from app.i18n import _

_log = get_logger(__name__)

#: Wie weit über die Knochenlänge hinaus ein Knochen noch Eckpunkte an sich
#: bindet, als Anteil seiner Länge. Ohne diesen Rand hinge die Haut zwischen
#: zwei Knochen an keinem von beiden und bliebe beim Beugen stehen.
REACH: Final = 0.6

#: Wie scharf die Bindung mit dem Abstand abfällt. Größer heißt härtere
#: Übergänge zwischen zwei Knochen; kleiner zieht die Haut zu weit mit.
FALLOFF: Final = 2.0

#: Wo der feste Rumpf zu halten beginnt und wo er allein hält, in Vielfachen
#: der Reichweite des nächsten Knochens (RM-561). Bis zur ersten Grenze folgt
#: die Haut ihren Knochen ganz wie bisher, hinter der zweiten bleibt sie
#: stehen, und dazwischen gleitet es kubisch, ohne Knick und ohne Riss.
REST_NEAR: Final = 1.0
REST_FAR: Final = 3.0


def _closest_on_segment(points: np.ndarray, head: np.ndarray, tail: np.ndarray) -> np.ndarray:
    """Der Abstand jedes Punktes zum Knochen — zum *Segment*, nicht zur Achse.

    Eine unendliche Achse bände die Fußspitze an den Oberarm, sobald beide
    zufällig auf einer Geraden liegen. Ein Knochen hat zwei Enden, und dazwischen
    liegt er.

    Gerechnet elementweise (``units.dot3``, ``transform.along``) und nicht
    über ``np.dot`` und ``@``: Aus dem Abstand wird das Gewicht und daraus die
    Lage jeder Ecke, und die soll auf jeder Maschine dieselbe sein (RM-187).
    """
    along = tail - head
    length = units.dot3(along, along)
    if length < 1e-12:
        return np.asarray(np.linalg.norm(points - head, axis=1), dtype=float)
    share = np.clip(transform.along(points - head, along) / length, 0.0, 1.0)
    away = np.linalg.norm(points - (head + share[:, None] * along), axis=1)
    return np.asarray(away, dtype=float)


#: ``ln 2`` in zwei Teilen (Cody-Waite): Der obere trägt nur 32 Bit Mantisse,
#: also ist ``k · LN2_HIGH`` für jedes ``|k| < 2²¹`` exakt, und der untere
#: trägt den Rest.
_LN2_HIGH: Final = 0.6931471803691238
_LN2_LOW: Final = 1.9082149292705877e-10
_INVERSE_LN2: Final = 1.4426950408889634
#: Taylorkoeffizienten ``1/n!`` bis ``n = 13`` — genug für ``|r| ≤ ln 2 / 2``:
#: Der erste weggelassene Term liegt unter 10⁻¹⁷.
_EXP_TERMS: Final = tuple(1.0 / math.factorial(order) for order in range(14))


#: Wie weit ein Klick neben dem Netz liegen darf und noch auf der Haut gilt —
#: der Sehnenfehler einer feinen Rundung, nicht mehr.
ON_THE_SKIN: Final = 0.05

#: Unter welchem Winkel zur Fläche ein Blick noch hineinführt (Kosinus). Ein
#: streifender Blick trifft die Gegenwand irgendwo weit hinten.
GRAZING: Final = 0.2


def inside_the_body(mesh: MeshData, point: Vec3, direction: Vec3) -> Vec3:
    """Wohin ein Gelenk gehört, wenn auf die Haut geklickt wurde (RM-367, W4-7).

    Ein Klick trifft die Oberfläche; ein Knochen dort lag auf der Haut statt im
    Gelenk, und die Beugung wurde einseitig (+60° Volumen 0,841, -60° 1,013).
    Von der Stelle aus geht der Blick weiter in den Körper bis zur Gegenwand;
    das Gelenk sitzt in der Mitte dazwischen — unter dem Klick, in der Tiefe
    des Glieds, wie es der Kunde von vorn sieht. Liegt der Punkt nicht auf der
    Haut, schaut der Blick streifend oder trifft er nichts, bleibt der Punkt.
    """
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=float)
    faces = np.asarray(raw.faces, dtype=np.int64)
    if not len(vertices) or not len(faces):
        return point
    here = np.asarray(point, dtype=float)
    found = _surface_normal_at(vertices, faces, here)
    if found is None:
        return point
    normal, start, gap = found
    if gap > ON_THE_SKIN:
        return point
    ray = np.asarray(direction, dtype=float)
    length = float(np.sqrt((ray * ray).sum()))
    if length <= units.EPS_GEOM:
        return point
    ray = ray / length
    if float((ray * normal).sum()) > -GRAZING:
        return point
    # Das eigene Dreieck und seine Nachbarn am Startpunkt sind kein Gegenüber:
    # Ein Klick auf eine Ecke trifft sie bei null. Ein Hundertstel Millimeter
    # ist dünner als jede druckbare Wand.
    depth, _hit = ray_hits_batch(
        vertices[faces],
        start[None, :],
        ray[None, :],
        edge_margin=units.EPS_GEOM,
        minimum_travel=units.EPS_DISPLAY,
    )
    reach = float(depth[0])
    if not math.isfinite(reach):
        return point
    inside = start + ray * (reach / 2.0)
    return (float(inside[0]), float(inside[1]), float(inside[2]))


def _surface_normal_at(
    vertices: np.ndarray, faces: np.ndarray, point: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float] | None:
    """Normale, Fußpunkt und Abstand des Dreiecks, auf dem ``point`` liegt — oder ``None``.

    Nicht die Normale des nächsten Eckpunkts: An einem Zylinder liegen die
    Eckpunkte nur an den Enden, und deren Normale zeigt halb nach unten.
    Gesucht wird das Dreieck, in dessen Ebene der Punkt liegt und dessen
    Fläche ihn enthält; elementweise gerechnet, dasselbe auf jeder Maschine.
    """
    a = vertices[faces[:, 0]]
    ab = vertices[faces[:, 1]] - a
    ac = vertices[faces[:, 2]] - a
    cross = np.stack(
        (
            ab[:, 1] * ac[:, 2] - ab[:, 2] * ac[:, 1],
            ab[:, 2] * ac[:, 0] - ab[:, 0] * ac[:, 2],
            ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0],
        ),
        axis=1,
    )
    length = np.sqrt((cross * cross).sum(axis=1))
    usable = length > units.EPS_GEOM
    if not usable.any():
        return None
    unit = np.zeros_like(cross)
    unit[usable] = cross[usable] / length[usable, None]
    offset = point - a
    distance = (offset * unit).sum(axis=1)
    flat = offset - distance[:, None] * unit
    d00 = (ab * ab).sum(axis=1)
    d01 = (ab * ac).sum(axis=1)
    d11 = (ac * ac).sum(axis=1)
    d20 = (flat * ab).sum(axis=1)
    d21 = (flat * ac).sum(axis=1)
    denominator = d00 * d11 - d01 * d01
    safe = np.where(np.abs(denominator) > units.EPS_GEOM, denominator, 1.0)
    v = (d11 * d20 - d01 * d21) / safe
    w = (d00 * d21 - d01 * d20) / safe
    slack = 1e-6
    inside = usable & (v >= -slack) & (w >= -slack) & (v + w <= 1.0 + slack)
    if not inside.any():
        return None
    candidates = np.flatnonzero(inside)
    closest = float(np.min(np.abs(distance[candidates])))
    touching = candidates[np.abs(distance[candidates]) <= closest + units.EPS_GEOM]
    # Liegt der Klick auf einer Kante oder Ecke, tragen ihn mehrere Dreiecke;
    # ihre Normalen gemittelt, nach Fläche gewichtet — sonst entschiede die
    # Dreiecksnummer, und an einer Spitze zeigte die Normale quer.
    mean = (cross[touching]).sum(axis=0)
    size = float(np.sqrt((mean * mean).sum()))
    if size <= units.EPS_GEOM:
        return None
    normal = mean / size
    best = int(touching[0])
    # Zurück kommt auch der Punkt in der Ebene des Dreiecks: Ein Klick auf
    # eine gekrümmte Fläche liegt um den Sehnenfehler daneben.
    return normal, point - distance[best] * unit[best], abs(float(distance[best]))


def _falloff(values: np.ndarray) -> np.ndarray:
    """``exp(x)`` für ``x ≤ 0`` — auf jeder Maschine dieselben Bits.

    **Nicht ``np.exp``** (RM-187): Die Exponentialfunktion wählt ihre
    Umsetzung nach der CPU — SVML mit AVX-512 auf Linux, NEON auf dem Mac,
    die Bibliothek der Plattform sonst —, und die runden die letzte Stelle
    verschieden. Aus dem Gewicht wird hier die Lage jeder Ecke einer Stellung.

    Gerechnet wird mit Grundrechenarten, jede als eigene NumPy-Operation und
    damit nach IEEE-754 gerundet: erst ``x = k·ln 2 + r`` mit ganzem ``k``
    (Cody-Waite, exakt), dann ``exp(r)`` als Taylorpolynom im Horner-Schema,
    dann ``·2ᵏ`` über ``ldexp``, das nur den Exponenten setzt. Die Abweichung
    von der wahren Funktion liegt bei einer Einheit der letzten Stelle.
    """
    # Unter -746 ist ``exp`` in doppelter Genauigkeit null; so weit unten
    # bleibt ``k`` im Bereich von ``ldexp`` und ``r`` klein.
    x = np.maximum(np.asarray(values, dtype=np.float64), -746.0)
    k = np.rint(x * _INVERSE_LN2)
    r = (x - k * _LN2_HIGH) - k * _LN2_LOW
    total = np.full_like(r, _EXP_TERMS[-1])
    for coefficient in reversed(_EXP_TERMS[:-1]):
        total = total * r + coefficient
    # Ein ``nan`` bleibt ``nan`` — über ``total``, nicht über den Exponenten.
    exponent = np.where(np.isfinite(k), k, 0.0).astype(np.int64)
    return np.asarray(np.ldexp(total, exponent), dtype=np.float64)


def weights(mesh: MeshData, bones: Sequence[Bone], *, fixed_rest: bool = False) -> np.ndarray:
    """Wie stark jeder Eckpunkt an jedem Knochen hängt.

    Eine Zeile je Eckpunkt, eine Spalte je Knochen. Gerechnet aus dem Abstand
    zum Knochensegment: nah heißt stark, und jenseits von Knochenlänge plus
    :data:`REACH` heißt kaum noch.

    Mit ``fixed_rest`` (ab Format 49, RM-561) hält ein unsichtbarer fester
    Rumpf, was weit von allen Knochen liegt: Die Zeile summiert sich auf den
    Anteil, den die Knochen halten — eins bis :data:`REST_NEAR` Reichweiten
    vom nächsten Knochen, null ab :data:`REST_FAR`, dazwischen ein glatter
    Übergang —, und der Rest bleibt stehen. Wer nur einen Arm setzt und
    beugt, beugt den Arm und nicht den ganzen Körper.

    Ohne ``fixed_rest`` ist jede Zeile auf eins normiert, und ein Eckpunkt,
    den kein Knochen erreicht, hängt am nächstgelegenen — sonst bliebe er
    stehen, während sein Nachbar mitgeht, und das Netz risse dort auf. So
    rechneten Stellungen bis Format 48.
    """
    points = np.asarray(mesh.raw.vertices, dtype=float)
    if not len(bones):
        return np.zeros((len(points), 0))

    field = np.zeros((len(points), len(bones)))
    nearest = np.full(len(points), np.inf)
    for index, bone in enumerate(bones):
        head = np.asarray(bone.head, dtype=float)
        tail = np.asarray(bone.tail, dtype=float)
        away = _closest_on_segment(points, head, tail)
        span = tail - head
        reach = max(math.hypot(float(span[0]), float(span[1]), float(span[2])) * REACH, 1e-9)
        ratio = away / reach
        nearest = np.minimum(nearest, ratio)
        field[:, index] = _falloff(-FALLOFF * (ratio * ratio))

    total = field.sum(axis=1)
    if fixed_rest:
        share = np.clip((REST_FAR - nearest) / (REST_FAR - REST_NEAR), 0.0, 1.0)
        held = share * share * (3.0 - 2.0 * share)
        safe = np.where(total > 0.0, total, 1.0)
        return np.asarray(field / safe[:, None] * held[:, None], dtype=float)
    orphan = total < 1e-9
    if orphan.any():
        nearest = np.argmin(
            np.stack(
                [
                    _closest_on_segment(
                        points[orphan],
                        np.asarray(bone.head, dtype=float),
                        np.asarray(bone.tail, dtype=float),
                    )
                    for bone in bones
                ],
                axis=1,
            ),
            axis=1,
        )
        field[np.where(orphan)[0], nearest] = 1.0
        total = field.sum(axis=1)
    return np.asarray(field / total[:, None], dtype=float)


def _rotation(angles: Vec3) -> np.ndarray:
    """Drei Winkel in Grad als Drehmatrix, in der Reihenfolge X, Y, Z.

    Eine feste Reihenfolge und keine Quaternionen: Wer eine Pose von Hand
    einstellt, dreht um eine Achse nach der anderen und will die Zahl
    wiederfinden, die er eingetippt hat.

    Aus den exakten Winkelfunktionen in Grad (``units.exact_cos_degrees``,
    RM-187) und nicht aus ``math.cos(math.radians(…))``: dieselbe Stellung,
    dieselben Bits auf jeder Maschine, und ein rechter Winkel ist exakt.
    """
    x, y, z = (float(value) for value in angles)
    cx, sx, cy, sy, cz, sz = (
        units.exact_cos_degrees(x),
        units.exact_sin_degrees(x),
        units.exact_cos_degrees(y),
        units.exact_sin_degrees(y),
        units.exact_cos_degrees(z),
        units.exact_sin_degrees(z),
    )
    return np.array(
        [
            [cy * cz, -cy * sz, sy],
            [sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz, -sx * cy],
            [-cx * sy * cz + sx * sz, cx * sy * sz + sx * cz, cx * cy],
        ]
    )


def _ordered(bones: Sequence[Bone]) -> list[Bone]:
    """Eltern vor Kindern — ohne diese Reihenfolge rechnet die Kette falsch.

    Ein Kind, das vor seinem Elternteil verarbeitet wird, erbt dessen
    Drehung nicht, und der Unterarm bleibt stehen, während der Oberarm sich
    hebt. Ein Zyklus im Baum hält an, statt endlos zu laufen.
    """
    by_name = {bone.name: bone for bone in bones}
    ordered: list[Bone] = []
    seen: set[str] = set()

    def place(bone: Bone, chain: tuple[str, ...]) -> None:
        if bone.name in seen:
            return
        if bone.name in chain:
            raise _circular((*chain, bone.name))
        parent = by_name.get(bone.parent)
        if parent is not None:
            place(parent, (*chain, bone.name))
        seen.add(bone.name)
        ordered.append(bone)

    for bone in bones:
        place(bone, ())
    return ordered


def transforms(bones: Sequence[Bone], poses: Mapping[str, Vec3]) -> dict[str, np.ndarray]:
    """Für jeden Knochen die Matrix, die seine Haut mitnimmt.

    **Vorwärtskinematik**: Die Drehung eines Knochens geschieht um seinen Kopf
    und erbt alles, was seine Eltern schon getan haben. Wer den Oberarm hebt,
    hebt den Unterarm mit, ohne ihn zu nennen.
    """
    result: dict[str, np.ndarray] = {}
    for bone in _ordered(bones):
        parent = result.get(bone.parent, np.eye(4))
        head = np.asarray(bone.head, dtype=float)
        local = np.eye(4)
        local[:3, :3] = _rotation(poses.get(bone.name, (0.0, 0.0, 0.0)))
        # Um den Kopf des Knochens, nicht um den Ursprung: Ein Arm, der sich um
        # den Weltursprung dreht, fliegt vom Körper weg.
        about = np.eye(4)
        about[:3, 3] = head
        back = np.eye(4)
        back[:3, 3] = -head
        # ``composed`` statt ``@`` (BLAS, RM-187): Diese Matrix bewegt die Haut.
        result[bone.name] = transform.composed(parent, about, local, back)
    return result


class Skin:
    """Ein Körper an seinem Skelett: Gewichte einmal, Stellungen beliebig oft.

    Die Gewichte hängen nur an Netz und Knochen; wer beim Beugen mit der Maus
    jede Bewegung zeigt, rechnet sie nicht je Bewegung neu (RM-561). Die
    Operation geht denselben Weg (:func:`posed`) — Vorschau und Ergebnis
    sind dieselbe Rechnung.
    """

    def __init__(self, mesh: MeshData, bones: Sequence[Bone], *, fixed_rest: bool = False) -> None:
        self.mesh = mesh
        self.bones = list(bones)
        self.fixed_rest = fixed_rest
        self.points = np.asarray(mesh.raw.vertices, dtype=float)
        self.field = weights(mesh, self.bones, fixed_rest=fixed_rest)

    def posed(self, angles: Mapping[str, Vec3]) -> MeshData:
        """Der Körper in dieser Stellung — ``angles`` je Knochenname drei Winkel."""
        if not self.bones or not any(
            any(abs(value) > 1e-9 for value in turn) for turn in angles.values()
        ):
            return self.mesh
        matrices = transforms(self.bones, angles)
        points, field = self.points, self.field
        moved = np.zeros_like(points)
        for index, bone in enumerate(self.bones):
            share = field[:, index]
            if not share.any():
                continue
            matrix = matrices.get(bone.name, np.eye(4))
            # Elementweise bewegt (``transform.moved_points``), nicht über BLAS.
            moved += transform.moved_points(points, matrix) * share[:, None]
        if self.fixed_rest:
            moved += points * (1.0 - field.sum(axis=1))[:, None]
        built = trimesh.Trimesh(vertices=moved, faces=self.mesh.raw.faces, process=False)
        _log.info("posed %d vertices over %d bones", len(points), len(self.bones))
        return self.mesh.replacing(built)


def posed(
    mesh: MeshData, bones: Sequence[Bone], poses: Sequence[Pose], *, fixed_rest: bool = False
) -> MeshData:
    """Den Körper in die Stellung bringen, die das Skelett beschreibt.

    Jeder Eckpunkt geht den gewichteten Mittelweg aller Knochenmatrizen —
    lineares Blend-Skinning. Es schnürt die Haut an stark gebeugten Gelenken
    ein; das ist der bekannte Preis des Verfahrens, und bei einer einzelnen
    Druckpose mit mäßigen Winkeln ist er kleiner als der Aufwand für die
    Alternativen. Mit ``fixed_rest`` bleibt, was kein Knochen hält, stehen
    (:func:`weights`).
    """
    if not bones or not poses:
        return mesh
    angles = {pose.bone: pose.angles for pose in poses}
    if not any(any(abs(value) > 1e-9 for value in turn) for turn in angles.values()):
        return mesh
    return Skin(mesh, bones, fixed_rest=fixed_rest).posed(angles)


def posed_bones(bones: Sequence[Bone], angles: Mapping[str, Vec3]) -> list[tuple[Vec3, Vec3]]:
    """Kopf und Fuß jedes Knochens in der Stellung — was das Bild beim Beugen zeigt."""
    matrices = transforms(bones, angles)
    found: list[tuple[Vec3, Vec3]] = []
    for bone in bones:
        ends = transform.moved_points(
            np.asarray([bone.head, bone.tail], dtype=float), matrices.get(bone.name, np.eye(4))
        )
        found.append((as_vec3(ends[0]), as_vec3(ends[1])))
    return found


def bent(
    bones: Sequence[Bone], angles: Mapping[str, Vec3], name: str, axis: Vec3, degrees: float
) -> Vec3:
    """Die drei Winkel von ``name``, nachdem er in der Stellung um ``degrees`` um
    ``axis`` gedreht wurde — um seinen Kopf, wie ihn das Bild zeigt (RM-561).

    Das Ziehen an einem Gelenk dreht den Knochen, der dort endet, in der
    Bildebene; geschrieben wird dasselbe ``pose``-Feld wie im Dialog (Regel
    2: die Geste wird ein Parameterwert). Die Drehung geschieht in der Welt
    nach der Stellung der Eltern; im Knochen steht sie davor, also
    ``R' = Pᵀ · Δ · P · R`` mit der Drehung ``P`` der Eltern.
    """
    bone = next(entry for entry in bones if entry.name == name)
    matrices = transforms(bones, angles)
    parent = matrices.get(bone.parent, np.eye(4))[:3, :3]
    turn = _about(axis, degrees)
    own = _rotation(angles.get(name, (0.0, 0.0, 0.0)))
    return _angles_of(_times(_times(_times(parent.T, turn), parent), own))


def _times(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """3x3 mal 3x3 über :func:`transform.composed` — ohne BLAS (RM-187)."""
    a, b = np.eye(4), np.eye(4)
    a[:3, :3], b[:3, :3] = left, right
    return np.asarray(transform.composed(a, b)[:3, :3], dtype=float)


def _about(axis: Vec3, degrees: float) -> np.ndarray:
    """Die Drehung um eine Achse durch den Ursprung (Rodrigues)."""
    way = np.asarray(axis, dtype=float)
    length = float(np.sqrt((way * way).sum()))
    if length <= units.EPS_GEOM:
        return np.eye(3)
    x, y, z = (float(value) for value in way / length)
    c, s = units.exact_cos_degrees(degrees), units.exact_sin_degrees(degrees)
    t = 1.0 - c
    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ]
    )


def _angles_of(matrix: np.ndarray) -> Vec3:
    """Die Winkel X, Y, Z in Grad, aus denen :func:`_rotation` diese Matrix baut.

    Auf hundertstel Grad gerundet — eine Stellung, die der Kunde im Dialog
    liest, soll keine vierzehn Nachkommastellen tragen. In der Sperrlage
    (Y = ±90°) ist Z null, und X trägt die ganze Drehung.
    """
    sine = min(1.0, max(-1.0, float(matrix[0, 2])))
    y = math.degrees(math.asin(sine))
    if abs(sine) < 1.0 - 1e-9:
        x = math.degrees(math.atan2(-float(matrix[1, 2]), float(matrix[2, 2])))
        z = math.degrees(math.atan2(-float(matrix[0, 1]), float(matrix[0, 0])))
    else:
        x = math.degrees(math.atan2(float(matrix[2, 1]), float(matrix[1, 1])))
        z = 0.0
    return (round(x, 2) + 0.0, round(y, 2) + 0.0, round(z, 2) + 0.0)


def _circular(chain: tuple[str, ...]) -> ValidationError:
    return ValidationError(
        field="armature",
        detail=_("Im Skelett hängt ein Knochen an sich selbst — die Kette schließt sich."),
        constraint="cycle",
        values={"chain": list(chain)},
        suggestions=(
            Action(id="fix_parent", label=_("Die Verbindung an einer Stelle auftrennen.")),
        ),
    )


# --- Serialisierung -------------------------------------------------------------


def armature_to_text(bones: Sequence[Bone]) -> str:
    """Das Skelett als JSON-Text, wie es im Parameter liegt."""
    return json.dumps(
        [
            {
                "n": bone.name,
                "h": [round(value, 6) for value in bone.head],
                "t": [round(value, 6) for value in bone.tail],
                "p": bone.parent,
            }
            for bone in bones
        ],
        separators=(",", ":"),
    )


def armature_from_text(text: str) -> list[Bone]:
    try:
        if not text.strip():
            return []
        return [
            Bone(
                name=str(entry["n"]),
                head=as_vec3(entry["h"]),
                tail=as_vec3(entry["t"]),
                parent=str(entry.get("p", "")),
            )
            for entry in json.loads(text)
        ]
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as problem:
        # Der Text kommt aus einer Projektdatei oder einem Dialogfeld — beides
        # fremde Eingabe. Ohne diesen Fang stirbt der Auswertungs-Thread an
        # einem rohen JSONDecodeError, und die Sitzung meldet Erfolg.
        raise ValidationError(
            title=_("Dieses Skelett lässt sich nicht lesen."),
            field="armature",
            detail=_(
                "Erwartet wird eine Liste von Knochen mit Name, Kopf und Schwanz — "
                "gesetzt im Skeletteditor, nicht getippt."
            ),
            value=text,
            constraint="unreadable",
        ) from problem


def pose_to_text(poses: Sequence[Pose]) -> str:
    """Die gerechnete Stellung als JSON-Text — je Knochen drei Zahlen."""
    return pose_text({pose.bone: [round(value, 6) for value in pose.angles] for pose in poses})


def pose_text(angles: Mapping[str, Sequence[float | str]]) -> str:
    """Dasselbe Format, aber für Winkel, die auch ein Ausdruck sein dürfen.

    **Ein Schreiber je Format**, und der steht im Kern — das stand schon als
    Vorsatz im Dialog, und der Dialog hielt ihn trotzdem nicht: Sobald ein
    Feld einen Ausdruck trug, fiel ``ArmatureField.value`` auf ein eigenes
    ``json.dumps`` zurück, weil :func:`pose_to_text` nur ``Pose`` nimmt und
    ``Pose.angles`` drei Zahlen sind. Zwei Schreiber für ein Format driften;
    hier ist der zweite wieder eingesammelt.

    Ein Ausdruck bleibt **wörtlich** stehen. Ihn beim Schreiben auszurechnen
    hieße, die Bindung beim ersten Speichern zu verlieren, ohne dass es
    jemand sähe.
    """
    return json.dumps(
        {bone: list(values) for bone, values in angles.items()}, separators=(",", ":")
    )


def pose_parameter_references(text: str, *, strict: bool = False) -> frozenset[str]:
    """Projektparameter, die die Winkel dieser Stellung lesen (§13, §15).

    Das Gegenstück zu :func:`app.core.sketch.serialize.sketch_parameter_references`
    und aus demselben Grund: Die Auswertung mischt die Werte in den
    Cache-Schlüssel der Operation. Ein Ausdruck steckt im JSON-Text und ist
    für ``resolve_params`` unsichtbar — die sieht die **oberste** Ebene eines
    Parametersatzes, und dort steht der ganze Text als ein Wert. Ohne diese
    Funktion bliebe nach einer Parameteränderung das alte Ergebnis im Cache:
    der Arm bliebe gebeugt, während die Zahl daneben schon die neue ist.

    Ein unlesbarer Text hat standardmäßig keine Abhängigkeiten; er scheitert
    beim Lauf der Operation mit seiner eigenen Meldung. ``strict`` reicht
    diesen Fehler sofort weiter, damit er nicht als „ungenutzt“ gezählt wird.

    **Auch das Skelett kommt hier vorbei**, denn beide Felder von
    ``PoseParams`` tragen ``kind="armature"``. Sein Text ist eine JSON-*Liste*
    statt eines Objekts und trägt keine Parametermaße: Ein Knochen ist eine
    Koordinate. Die Liste wird ausdrücklich als Skelett erkannt, nicht erst
    am fehlenden ``.values()``. Das gilt auch bei strenger Verwendungsprüfung.
    """
    found: set[str] = set()
    try:
        payload = json.loads(text.strip() or "{}")
        if isinstance(payload, list):
            return frozenset()
        for values in payload.values():
            if strict:
                # Dieselbe Zahlenlesart wie bei der Stellung, ohne Auswertung
                # der Ausdrücke oder eine zweite JSON-Runde.
                as_vec3([0.0 if is_expression(angle) else angle for angle in values])
            for angle in values:
                if is_expression(angle):
                    found |= references(angle)
    except (ValueError, TypeError, AttributeError, IndexError, RecursionError) as problem:
        if strict:
            raise ValidationError(
                title=_("Diese Stellung lässt sich nicht lesen."),
                field="pose",
                detail=_(
                    "Je Knochen drei Winkel: der Knochenname auf eine Liste aus drei "
                    "Zahlen, etwa [0, 30, 0]."
                ),
                value=text,
                constraint="unreadable",
            ) from problem
        return frozenset()
    return frozenset(found)


def pose_angles(text: str) -> dict[str, tuple[float | str, ...]]:
    """Die Winkel, wie sie dastehen — Zahl oder Ausdruck, nichts aufgelöst.

    Für den Dialog, und deshalb **ohne Fehler**: Ein unlesbarer Text ist dort
    ein leeres Raster und kein Abbruch. Der Dialog soll aufgehen; was nicht zu
    lesen war, wird beim Übernehmen ohnehin überschrieben.

    Sie ist der fehlende Rückweg. Der Dialog schrieb einen Ausdruck wörtlich —
    das sagte sein Docstring zu, und beim Schreiben stimmte es. Gelesen wurde
    über :func:`pose_from_text`, und die gibt drei **Zahlen**: Ein Ausdruck
    liess sie scheitern, der Fang machte daraus ein leeres Raster, und alle
    drei Winkel des Knochens standen auf null. Ein Rundlauf durch den Dialog
    verlor damit genau die Bindung, die er zu erhalten versprach.
    """
    found: dict[str, tuple[float | str, ...]] = {}
    try:
        for name, entry in json.loads(text or "{}").items():
            found[str(name)] = tuple(
                value if is_expression(value) else float(value) for value in entry
            )
    except ValueError, TypeError, AttributeError:
        return {}
    return found


def pose_from_text(text: str, values: Mapping[str, float] | None = None) -> list[Pose]:
    """Die Stellung, gelesen und gegen die Projektparameter aufgelöst.

    ``values`` ist eine **Vorgabe und keine Pflicht**: Wer keine Parameter
    reicht, bekommt weiter, was er immer bekam — sonst müsste jeder Aufrufer
    mitziehen, auch die, die nie einen Ausdruck sehen.

    **Ohne Erhöhung der ``format_version``, und das ist eine Entscheidung.**
    Das Schema ändert sich nicht: Ein Pose-Winkel stand schon immer als Wert
    im JSON, und dass dort jetzt auch ein Ausdruck stehen darf, ist ein
    größerer Wertebereich und kein neues Feld. Alte Dateien tragen nur Zahlen
    und lesen unverändert. Rückwärts gilt es nicht — eine Datei mit ``=@x``
    im Winkel scheitert in einer älteren Version an ``float()`` —, und das ist
    derselbe Fall wie bei jeder Datei, die eine neuere Operation benutzt. Eine
    Erhöhung würde stattdessen **jede** neue Datei für die alte Version
    sperren, auch die ohne einen einzigen Ausdruck; das wäre der teurere
    Irrtum. Die Kette in ``migrations.py`` erhöht für Schemaänderungen, nicht
    für Fähigkeiten.
    """
    try:
        if not text.strip():
            return []
        return [
            Pose(bone=str(name), angles=_angles(entry, values or {}))
            for name, entry in json.loads(text).items()
        ]
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as problem:
        # Die naheliegendste Handeingabe — „b1: 0,30,0" — ist kein JSON. Sie
        # bekommt einen Satz mit der erwarteten Form, keinen toten Thread.
        raise ValidationError(
            title=_("Diese Stellung lässt sich nicht lesen."),
            field="pose",
            detail=_(
                "Je Knochen drei Winkel: der Knochenname auf eine Liste aus drei "
                "Zahlen, etwa [0, 30, 0]."
            ),
            value=text,
            constraint="unreadable",
        ) from problem


def _angles(entry: Sequence[float | str], values: Mapping[str, float]) -> Vec3:
    """Drei Winkel, jeder eine Zahl oder ein Ausdruck darauf.

    Aufgelöst wird **hier** und nicht später: ``Pose.angles`` ist ein Tripel
    aus Zahlen, und das soll es bleiben — der Text ist die Quelle, der
    geparste Typ ist das Ergebnis. Dasselbe Verhältnis wie beim Skizzentext,
    den der Löser auflöst und nicht die Serialisierung.

    Ein Ausdruck auf einen Parameter, den es nicht gibt, wirft die Meldung des
    Auswerters — **nicht** die des unlesbaren Textes. Die Stellung ist ja
    gelesen; was fehlt, ist ein Name, und wer den falschen Satz liest, sucht
    am JSON statt am Parameter.
    """
    resolved = [evaluate(angle, values) if is_expression(angle) else angle for angle in entry]
    return as_vec3(cast(Sequence[float], resolved))


# --- operation --------------------------------------------------------------------


@op_params
class PoseParams(BaseParams):
    armature: str = param(
        title=_("Skelett"),
        kind="armature",
        default="",
        placement="advanced",
        doc=_(
            "Die Knochen, an denen der Körper hängt. Sie werden gesetzt, nicht getippt — "
            "dieses Feld zeigt nur, was dabei entstanden ist."
        ),
    )
    pose: str = param(
        title=_("Stellung"),
        kind="armature",
        default="",
        placement="advanced",
        doc=_("Je Knochen drei Winkel. Ein Winkel darf ein Projektparameter sein."),
    )
    fixed_rest: bool = param(
        title=_("Ohne Knochen bleibt stehen"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_(
            "Was kein Knochen erreicht, bleibt beim Beugen stehen. Ohne Haken folgt es "
            "dem nächsten Knochen, wie in älteren Projekten."
        ),
    )


@register_op(
    name="pose_armature",
    result_kind="mesh",
    title=_("Stellung geben"),
    category="mesh",
    params=PoseParams,
    consumes=1,
    produces=1,
    # 1: Ohne Knochen bleibt stehen (``fixed_rest``, RM-561).
    cache_version="1",
    doc=_(
        "Beugt einen Körper um ein Skelett. Eine Stellung, keine Bewegung — gedruckt "
        "wird ein Zustand."
    ),
    caveat=_(
        "Für starke Beugungen, denn an gebeugten Gelenken schnürt sich die Haut ein. Was der "
        "Druck hält, zeigt die Überhangkarte."
    ),
)
def pose_armature(ctx: OpContext) -> OpResult:
    """Skelett und Stellung als ein Schritt im Verlauf."""
    params = cast(PoseParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    bones = armature_from_text(params.armature)
    # Derselbe Weg wie bei der gezeichneten Skizze (``sketch/ops.py``): Ein
    # Winkel wie ``=@arm_winkel`` rechnet hier mit denselben Werten wie
    # überall (§13). Über ``resolve_params`` kommt er nicht — die sieht die
    # oberste Ebene des Parametersatzes, und dort steht der ganze Text.
    values = {name: entry.value for name, entry in ctx.scene.parameters.items()}
    poses = pose_from_text(params.pose, values)

    after = posed(before, bones, poses, fixed_rest=params.fixed_rest)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=_pose_findings(before, after, bones, poses, source.id),
    )


def _pose_findings(
    before: MeshData,
    after: MeshData,
    bones: Sequence[Bone],
    poses: Sequence[Pose],
    object_id: str,
) -> list[Finding]:
    """Was die Stellung gekostet hat — und was der Drucker davon hält."""
    if not bones:
        # **Eine Warnung und keine Auskunft** (Fund vom 14.09.2026, gemessen
        # über das Fenster): Ohne Knochen kann dieser Schritt nichts bewegen,
        # heute nicht und bei keiner Auswertung danach. Als ``info`` kam der
        # Satz nirgends an — ``Session._warning_of`` reicht nur Warnungen und
        # Fehler ins Band, und dort stand deshalb weiter „am Volumen ändert
        # sich nichts". Der Kunde las eine Zahl statt des Grundes.
        #
        # **Und trotzdem keine Ausnahme.** Die zwei Geschwister mit
        # gesammelten Parametern antworten genauso: ``sculpt.empty`` für eine
        # Sitzung ohne Zug, ``repair.nothing_to_do`` für ein heiles Netz — ein
        # Befund, und der Schritt bleibt stehen. Er ist ja der Träger des
        # Skeletts: Wer ihn öffnet und Knochen setzt, füllt genau diesen
        # Parameter. Eine geworfene Ausnahme hielte stattdessen die ganze
        # Kette an (§15.3), und hinter einem angehaltenen Schritt rechnet
        # nichts mehr — für etwas, das noch nicht ausgefüllt ist.
        return [
            Finding(
                code="pose.no_armature",
                severity="warning",
                message=_(
                    "Für eine Stellung fehlt das Skelett, der Schritt bewegt nichts. Im "
                    "Skeletteditor setzt jeder Klick ein Gelenk."
                ),
                object_id=object_id,
            )
        ]

    findings = [
        Finding(
            code="pose.applied",
            severity="info",
            message=_("Der Körper folgt jetzt der eingestellten Stellung."),
            object_id=object_id,
            values={"bones": len(bones), "posed": len(poses)},
        )
    ]
    # Lineares Blend-Skinning schnürt ein; das Volumen ist die Zahl, an der es
    # auffällt, bevor jemand das Ergebnis von Hand nachmisst.
    if before.volume > 0.0 and after.volume < before.volume * 0.9:
        findings.append(
            Finding(
                code="pose.pinched",
                severity="warning",
                message=_(
                    "An den gebeugten Gelenken schnürt sich die Haut ein — für diese "
                    "Winkel ist das Netz dort zu grob."
                ),
                object_id=object_id,
                values={
                    "before": round(before.volume, 1),
                    "after": round(after.volume, 1),
                },
            )
        )
    return findings
