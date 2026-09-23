"""Merkmale in Flucht bringen (Bauplan §18.11).

Einrasten, das etwas bedeutet: nicht „nah an einem Rasterpunkt", sondern
„diese Bohrung ist jetzt koaxial zu jener", „diese Fläche liegt plan auf
jener". Beides ist die Bewegung, die ein Mensch in Worten beschreibt, und
beides ist danach eine Operation — eine Matrix, die niemand lesen kann, ist
genau das, was §2.1 verbietet.

Die Rechnung ist in beiden Fällen dieselbe: eine Richtung auf eine andere
drehen, dann einen Punkt auf einen anderen schieben. Was sich unterscheidet,
ist, was als Richtung und Punkt zählt — bei einer Bohrung ihre Achse und ihre
Mitte, bei einer Fläche ihre Normale und ihr Mittelpunkt. Flächen werden
*aufeinander zu* gedreht, Bohrungen *miteinander* — das ist der Unterschied
zwischen Aufliegen und Hineingleiten.
"""

from __future__ import annotations

import math

import numpy as np

from app.core import units
from app.core.errors import Action, AppError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, composed, moved_points, translation
from app.core.geom.transform import rotation_between as shortest_rotation
from app.core.log import get_logger
from app.core.types import Feature, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)


def frame_of(feature: Feature) -> tuple[Vec3, Vec3]:
    """Richtung und Ankerpunkt eines Merkmals — seine Achse und seine Mitte.

    Eine Bohrung zeigt entlang ihrer Achse, eine Fläche entlang ihrer
    Normalen. Eine Kantenschleife hat weder noch, und das zu sagen schlägt,
    eine zu erfinden.
    """
    params = feature.params
    if feature.kind in ("hole", "pin"):
        # **Der Stift gehört dazu, und zwar von Anfang an.** Er trägt
        # dieselben zwei Werte wie die Bohrung — gemessen an einem
        # erkannten Zapfen: ``axis=(0, 0, 1)``, ``centre`` in seiner
        # Mitte. Ohne ihn lief er in den Zweig darunter und bekam
        # „trägt keine Achse und keine Fläche" zu lesen, was für einen
        # Stift schlicht nicht stimmt.
        #
        # Der Fall, um den es geht, ist der häufigste überhaupt: Auto
        # Split legt Stift/Loch-Paare an, und „den Stift ins Loch legen“
        # ist genau das, wofür diese Operation da ist. Ein Rechtsklick
        # auf einen erkannten Stift bot sie bis heute nicht einmal an.
        direction = params.get("axis")
        point = params.get("centre")
    elif feature.kind == "face":
        direction = params.get("normal")
        point = params.get("centre")
    else:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail=_(
                "Diese Art von Merkmal trägt keine Achse und keine Fläche — es "
                "gibt nichts, woran sich etwas ausrichten ließe."
            ),
            values={"feature": feature.id, "kind": feature.kind},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie eine Bohrung oder eine Fläche.")),
            ),
        )
    if direction is None or point is None:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail=_(
                "Zu diesem Merkmal ist keine Lage gespeichert: Es hat weder eine "
                "Richtung noch einen Mittelpunkt."
            ),
            values={"feature": feature.id},
            # **Derselbe Ausweg wie beim Zweig darüber.** Die drei Absagen
            # dieser Datei tragen denselben Titel; eine bekam ihren Vorschlag,
            # die zwei anderen blieben bei „geht nicht" (Regel 17). Der Fall ist
            # für den Kunden derselbe: Er hat etwas angeklickt, mit dem sich
            # nicht ausrichten lässt, und der nächste Schritt ist, etwas
            # anderes anzuklicken. Dass es hier an fehlenden Maßen liegt und
            # dort an der Merkmalsart, ändert daran nichts.
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie eine Bohrung oder eine Fläche.")),
            ),
        )
    return _unit(direction), (float(point[0]), float(point[1]), float(point[2]))


def align_matrix(source: Feature, target: Feature, flip: bool = False) -> np.ndarray:
    """Die Transformation, die ``source`` auf ``target`` legt.

    Zwei Flächen treffen sich Stirn an Stirn, also wird die Quellnormale auf
    die *invertierte* Zielnormale gedreht — sonst landeten die Teile Rücken an
    Rücken, und das ist das eine, was niemand mit „leg das auf jenes" meint.
    Zwei Bohrungen teilen eine Achse, werden also auf dieselbe Richtung
    gedreht. ``flip`` dreht das Ergebnis um, für den Fall, dass es andersherum
    gemeint war.
    """
    source_direction, source_point = frame_of(source)
    target_direction, target_point = frame_of(target)

    wanted = np.asarray(target_direction, dtype=float)
    if source.kind == "face" and target.kind == "face":
        wanted = -wanted
    if flip:
        wanted = -wanted

    turn = rotation_between(
        source_direction, (float(wanted[0]), float(wanted[1]), float(wanted[2]))
    )
    # Elementweise und über ``composed`` statt ``@`` (RM-187): Mit dieser
    # Matrix wird der Körper bewegt.
    moved_point = moved_points(np.array([source_point], dtype=float), turn)[0]
    offset = np.asarray(target_point, dtype=float) - moved_point
    return composed(translation((float(offset[0]), float(offset[1]), float(offset[2]))), turn)


def rotation_between(source: Vec3, target: Vec3) -> np.ndarray:
    """Die kürzeste Drehung, die eine Richtung auf eine andere bringt.

    **Die Rechnung steht einmal** — in :func:`app.core.geom.transform.rotation_between`,
    Rodrigues aus Grundrechenarten. Hier stand bis zum 22.09.2026 eine zweite
    Fassung über Achse und Winkel, mit ``math.acos``, ``sin`` und ``cos`` der
    Plattform und Matrixprodukten über BLAS: ein Zwilling, der auf jeder
    Maschine eine andere letzte Stelle drehte (RM-187).

    **Nur die Gegenrichtung ist eigen, und zwar mit Absicht.** Zeigen die
    Richtungen gegeneinander, dreht jede senkrechte Achse die eine auf die
    andere; welche, entscheidet über die Lage des Körpers **um** die Achse.
    Ausrichtungen, die in Projektdateien stehen, sind mit dieser Wahl gerechnet
    — X als Hilfsachse, bei einer Richtung nahe X die Y-Achse —, und dieselbe
    Datei soll dasselbe Teil ergeben (§11.3). Die halbe Drehung ist exakt
    ``2·a·aᵀ - I`` statt ``I + sin(π)·K + …`` mit ``sin(π) = 1,2·10⁻¹⁶``.
    """
    first = np.asarray(_unit(source), dtype=float)
    second = np.asarray(_unit(target), dtype=float)
    across = np.cross(first, second)
    sine = math.hypot(float(across[0]), float(across[1]), float(across[2]))
    if sine <= EPS_GEOM and units.dot3(first, second) < 0.0:
        helper = (1.0, 0.0, 0.0) if abs(first[0]) < 0.9 else (0.0, 1.0, 0.0)
        axis = np.cross(first, np.asarray(helper))
        axis = axis / math.hypot(float(axis[0]), float(axis[1]), float(axis[2]))
        matrix = np.eye(4)
        matrix[:3, :3] = 2.0 * np.outer(axis, axis) - np.eye(3)
        return matrix
    return shortest_rotation(first, second)


def align(mesh: MeshData, source: Feature, target: Feature, flip: bool = False) -> MeshData:
    """Bewegt einen Körper, bis sein Merkmal mit einem anderen fluchtet."""
    matrix = align_matrix(source, target, flip)
    _log.info("aligning %s onto %s", source.id, target.id)
    return apply(mesh, matrix)


def _unit(vector: object) -> Vec3:
    values = np.asarray(vector, dtype=float)
    # ``math.hypot`` statt ``np.linalg.norm`` (BLAS, RM-187).
    length = math.hypot(float(values[0]), float(values[1]), float(values[2]))
    if length <= EPS_GEOM:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail=_(
                "Die Richtung dieses Merkmals hat die Länge null — daraus lässt "
                "sich keine Achse bilden."
            ),
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie eine Bohrung oder eine Fläche.")),
            ),
        )
    values = values / length
    return (float(values[0]), float(values[1]), float(values[2]))
