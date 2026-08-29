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

from app.core.deferred import trimesh
from app.core.errors import Action, ValidationError
from app.core.expressions import evaluate, is_expression, references
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Bone, Finding, OpContext, OpResult, Pose, Vec3
from app.i18n import _

_log = get_logger(__name__)

#: Wie weit über die Knochenlänge hinaus ein Knochen noch Eckpunkte an sich
#: bindet, als Anteil seiner Länge. Ohne diesen Rand hinge die Haut zwischen
#: zwei Knochen an keinem von beiden und bliebe beim Beugen stehen.
REACH: Final = 0.6

#: Wie scharf die Bindung mit dem Abstand abfällt. Größer heißt härtere
#: Übergänge zwischen zwei Knochen; kleiner zieht die Haut zu weit mit.
FALLOFF: Final = 2.0


def _closest_on_segment(points: np.ndarray, head: np.ndarray, tail: np.ndarray) -> np.ndarray:
    """Der Abstand jedes Punktes zum Knochen — zum *Segment*, nicht zur Achse.

    Eine unendliche Achse bände die Fußspitze an den Oberarm, sobald beide
    zufällig auf einer Geraden liegen. Ein Knochen hat zwei Enden, und dazwischen
    liegt er.
    """
    along = tail - head
    length = float(np.dot(along, along))
    if length < 1e-12:
        return np.asarray(np.linalg.norm(points - head, axis=1), dtype=float)
    share = np.clip(((points - head) @ along) / length, 0.0, 1.0)
    away = np.linalg.norm(points - (head + share[:, None] * along), axis=1)
    return np.asarray(away, dtype=float)


def weights(mesh: MeshData, bones: Sequence[Bone]) -> np.ndarray:
    """Wie stark jeder Eckpunkt an jedem Knochen hängt.

    Eine Zeile je Eckpunkt, eine Spalte je Knochen, zeilenweise auf eins
    normiert. Gerechnet aus dem Abstand zum Knochensegment: nah heißt stark,
    und jenseits von Knochenlänge plus :data:`REACH` heißt gar nicht.

    Ein Eckpunkt, den kein Knochen erreicht, hängt am nächstgelegenen — sonst
    bliebe er beim Posieren stehen, während sein Nachbar mitgeht, und das
    Netz risse genau dort auf.
    """
    points = np.asarray(mesh.raw.vertices, dtype=float)
    if not len(bones):
        return np.zeros((len(points), 0))

    field = np.zeros((len(points), len(bones)))
    for index, bone in enumerate(bones):
        head = np.asarray(bone.head, dtype=float)
        tail = np.asarray(bone.tail, dtype=float)
        away = _closest_on_segment(points, head, tail)
        reach = max(float(np.linalg.norm(tail - head)) * REACH, 1e-9)
        field[:, index] = np.exp(-FALLOFF * (away / reach) ** 2)

    total = field.sum(axis=1)
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
    """
    x, y, z = (math.radians(float(value)) for value in angles)
    cx, sx, cy, sy, cz, sz = (
        math.cos(x),
        math.sin(x),
        math.cos(y),
        math.sin(y),
        math.cos(z),
        math.sin(z),
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
        result[bone.name] = parent @ about @ local @ back
    return result


def posed(mesh: MeshData, bones: Sequence[Bone], poses: Sequence[Pose]) -> MeshData:
    """Den Körper in die Stellung bringen, die das Skelett beschreibt.

    Jeder Eckpunkt geht den gewichteten Mittelweg aller Knochenmatrizen —
    lineares Blend-Skinning. Es schnürt die Haut an stark gebeugten Gelenken
    ein; das ist der bekannte Preis des Verfahrens, und bei einer einzelnen
    Druckpose mit mäßigen Winkeln ist er kleiner als der Aufwand für die
    Alternativen.
    """
    if not bones or not poses:
        return mesh
    angles = {pose.bone: pose.angles for pose in poses}
    if not any(any(abs(value) > 1e-9 for value in turn) for turn in angles.values()):
        return mesh

    matrices = transforms(bones, angles)
    field = weights(mesh, bones)
    points = np.asarray(mesh.raw.vertices, dtype=float)
    homogeneous = np.hstack([points, np.ones((len(points), 1))])

    moved = np.zeros_like(points)
    for index, bone in enumerate(bones):
        share = field[:, index]
        if not share.any():
            continue
        matrix = matrices.get(bone.name, np.eye(4))
        moved += (homogeneous @ matrix.T)[:, :3] * share[:, None]

    built = trimesh.Trimesh(vertices=moved, faces=mesh.raw.faces, process=False)
    _log.info("posed %d vertices over %d bones", len(points), len(bones))
    return mesh.replacing(built)


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
                head=_vector(entry["h"]),
                tail=_vector(entry["t"]),
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


def pose_parameter_references(text: str) -> frozenset[str]:
    """Projektparameter, die die Winkel dieser Stellung lesen (§13, §15).

    Das Gegenstück zu :func:`app.core.sketch.serialize.sketch_parameter_references`
    und aus demselben Grund: Die Auswertung mischt die Werte in den
    Cache-Schlüssel der Operation. Ein Ausdruck steckt im JSON-Text und ist
    für ``resolve_params`` unsichtbar — die sieht die **oberste** Ebene eines
    Parametersatzes, und dort steht der ganze Text als ein Wert. Ohne diese
    Funktion bliebe nach einer Parameteränderung das alte Ergebnis im Cache:
    der Arm bliebe gebeugt, während die Zahl daneben schon die neue ist.

    Ein unlesbarer Text hat keine Abhängigkeiten; er scheitert beim Lauf der
    Operation mit seiner eigenen Meldung.

    **Auch das Skelett kommt hier vorbei**, denn beide Felder von
    ``PoseParams`` tragen ``kind="armature"``. Sein Text ist eine JSON-*Liste*
    statt eines Objekts, ``.values()`` gibt es darauf nicht, und der Fang
    darunter macht daraus ein leeres Ergebnis — richtig, denn ein Knochen ist
    eine Koordinate und kein Maß, das jemand an einen Parameter hängt. Es
    steht hier, weil ein stiller ``AttributeError`` als Entwurf aussieht und
    nicht als Entscheidung.
    """
    found: set[str] = set()
    try:
        for values in json.loads(text or "{}").values():
            for angle in values:
                if is_expression(angle):
                    found |= references(angle)
    except (ValueError, TypeError, AttributeError):
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
    except (ValueError, TypeError, AttributeError):
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


def _vector(values: Sequence[float]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


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
    return _vector(cast(Sequence[float], resolved))


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


@register_op(
    name="pose_armature",
    title=_("Stellung geben"),
    category="mesh",
    params=PoseParams,
    consumes=1,
    produces=1,
    doc=_(
        "Beugt einen Körper um ein Skelett. Eine Stellung, keine Bewegung — gedruckt "
        "wird ein Zustand."
    ),
    caveat=_(
        "Nicht für starke Beugungen: Die Haut wird an gebeugten Gelenken eingeschnürt, "
        "und ein ausgestreckter Arm ist ein Überhang. Was der Druck davon hält, sagt "
        "die Überhangkarte."
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

    after = posed(before, bones, poses)
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
        return [
            Finding(
                code="pose.no_armature",
                severity="info",
                message=_("Für eine Stellung fehlt noch das Skelett."),
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
