"""Ein Deckel für eine Öffnung (Bauplan §25, §14).

Die häufigste zweite Hälfte eines Teils. Jemand hat eine Box — hier
modelliert, heruntergeladen oder gescannt — und braucht etwas, das sie
verschließt. Von Hand heißt das: den Hohlraum ausmessen, ihn einen Tick
kleiner nachzeichnen, und am Drucker herausfinden, um wie viel der Tick
falsch war.

Der Hohlraum wird nicht gemessen, er wird genommen: ein Schnitt durch die
Wand auf Höhe der Öffnung liefert die Außenkontur und das Loch darin, und der
Kragen ist dieses Loch, geschrumpft um das Spiel aus dem Materialprofil
(§12). Die Zahl, die entscheidet, ob der Deckel passt, ist also dieselbe, die
die Passungsprüfung benutzt — und eine Materialkalibrierung (§28.3) erreicht
einen Deckel, der vor ihr gebaut wurde.
"""

from __future__ import annotations

import dataclasses
import math
from itertools import pairwise
from typing import Any, Final, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError, ValidationError
from app.core.geom import lathe, transform
from app.core.geom.autosplit import upright_normal
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean, deepest, shared_volume
from app.core.geom.lid_hinge import HINGE_SIDES, HINGES
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.fasteners import CUSTOM_FORMS, MOST_STARTS
from app.core.knowledge.parts.shapes import (
    ThreadProfile,
    mesh_only,
    moved,
    ridge_depth,
    thread_body,
    turn_segments,
)
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.registry.params import ZERO_AUTOMATIC, ZERO_FROM_PROFILE, ZERO_NONE, ZERO_TOP_EDGE
from app.core.scene.placement import dominant_axis, faces_up
from app.core.slice.analysis import cross_section
from app.core.types import (
    BaseParams,
    BRepBody,
    CancelToken,
    Feature,
    Finding,
    OpContext,
    OpResult,
    Quality,
    SceneObject,
    SolverInfo,
    Vec3,
    vec3_or_none,
)
from app.core.units import COARSEST_PITCH, EPS_GEOM, LARGEST_THREAD
from app.i18n import _

_log = get_logger(__name__)

#: Wie weit unter dem Rand der Schnitt genommen wird. Exakt an der Oberkante
#: trifft ein Schnitt das Ende der Wand und liefert eine Linie statt eines
#: Rings; einen Zehntelmillimeter tiefer ist er sicher im Material.
BELOW_RIM = 0.1

#: Darunter ist ein Hohlraum eine Bohrung, keine Öffnung — 100 mm² sind ein
#: Loch von elf Millimetern, und niemand steckt einen Deckelkragen in ein
#: Schraubenloch. Darüber zählt jeder Ring, auch ein kleines Fach neben einem
#: großen: ein Schlitz von zwölf Millimetern im Quadrat nimmt einen Kragen
#: bestens, und Hohlräume gegeneinander statt gegen eine Größe zu messen
#: würfe ihn weg.
MIN_CAVITY = 100.0

#: Wie der Kragen zu seinem Maß kommt — und warum hier keine Zahl mehr steht.
#:
#: Es stand eine: ``COLLAR_RELIEF = 0.2``, „damit der Deckel nicht auf dem
#: Kragen sitzt statt auf dem Rand". Das ist eine Zahlenkonstante für eine
#: Toleranz, und genau die verbietet Regel 7 — sie untergräbt die
#: Kalibrierung (§28.3): Wer sein Material misst und 0,15 mm einträgt, bekam
#: trotzdem 0,55 mm Luft je Seite.
#:
#: Dass der Kragen nicht klemmt, ist die Aufgabe des Gleitspiels aus dem
#: Materialprofil. Dafür ist es da, und dafür wird es gemessen.
#:
#: **Und es ist ein Durchmessermaß**, wie überall sonst im Haus: Ein
#: Passstift bekommt seine Bohrung als ``diameter + play``
#: (``knowledge/parts/mechanics.py``), und die Passungsprüfung rechnet
#: ``hole_diameter - pin_diameter`` (``scene/fits.py``). Der Kragen wurde als
#: einziger radial eingezogen — der Deckel bekam damit das doppelte Spiel,
#: und die Passung des Beispiels „Dose mit Deckel" meldete bei jedem Öffnen
#: 0,90 mm statt 0,25 mm.

#: Die beiden Merkmale, die ein Deckel und seine Schachtel teilen. Sie tragen
#: feste Namen, weil eine Passung auf Namen zeigt und nicht auf Geometrie
#: (§14): der Ablauf kann das Paar damit anlegen, bevor irgendetwas gerechnet
#: ist. Ohne sie gäbe es nichts, worauf ein ``Fit`` verweisen könnte — und
#: genau deshalb trug ein Deckel bisher keine Passung.
COLLAR_FEATURE = "lid_collar"
CAVITY_FEATURE = "lid_cavity"

#: Das entsprechende Paar des Drehdeckels. Auch hier stehen die Namen vor der
#: Auswertung fest, damit der eine UI-Ablauf Geometrie und Passung in derselben
#: Transaktion anlegen kann.
NECK_THREAD_FEATURE = "lid_neck_thread"
CAP_THREAD_FEATURE = "lid_cap_thread"


def _area_of(cavities: list[Any]) -> float:
    """Wie viel Öffnung der Kragen ausfüllt."""
    return float(sum(cavity.area for cavity in cavities))


def _centre_of(cavities: list[Any], z: float) -> tuple[float, float, float]:
    """Die Mitte der Öffnung, auf Höhe des Schnitts.

    Bei mehreren Fächern der flächengewichtete Schwerpunkt — es ist eine
    Passung über die ganze Öffnung, nicht eine je Fach.
    """
    total = _area_of(cavities)
    if total <= EPS_GEOM:
        return (0.0, 0.0, z)
    x = sum(cavity.centroid.x * cavity.area for cavity in cavities) / total
    y = sum(cavity.centroid.y * cavity.area for cavity in cavities) / total
    return (float(x), float(y), float(z))


def _narrowest(cavities: list[Any]) -> float:
    """Die engste Weite der Öffnung — das Maß, an dem eine Passung hängt.

    Ein Deckel klemmt nicht an der Fläche, sondern an der schmalsten Stelle:
    dort sitzt der Kragen am nächsten an der Wand. Genommen wird die kürzere
    Seite des **kleinsten umschließenden Rechtecks in jeder Drehung**, bei
    mehreren Fächern die kleinste davon.

    Bis zum 22.09.2026 war es das achsparallele Hüllrechteck: An einem um
    45 Grad gedrehten quadratischen Fach von 30 mm stand damit 42,4 mm in der
    Passung, die Diagonale — ein Maß, das es am Teil nicht gibt.
    """
    widths: list[float] = []
    for cavity in cavities:
        if isinstance(cavity, _ExactCavity):
            # Am exakten Körper gemessen, als er geschnitten wurde (:func:`_exact_width`).
            widths.append(cavity.narrowest)
            continue
        side = _short_side(cavity)
        if side is None:
            # Ein entarteter Umriss hat keine Breite; das Hüllrechteck sagt dann
            # wenigstens die eine, die er hat.
            left, bottom, right, top = cavity.bounds
            widths.append(min(right - left, top - bottom))
            continue
        widths.append(side)
    return float(min(widths)) if widths else 0.0


def _short_side(shape: Any) -> float | None:
    """Die kürzere Seite des kleinsten umschließenden Rechtecks in jeder Drehung.

    ``None``, wenn es keines gibt — ein entarteter Umriss oder ein einzelner
    Punkt. Gefragt vom Polygon am Netz und von den Randpunkten einer exakten
    Öffnung (:func:`_exact_width`): eine Rechnung, nicht zwei.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    hull = shape.convex_hull.normalize()
    if not isinstance(hull, ShapelyPolygon) or hull.is_empty:
        return None
    # Eine Seite des flächenkleinsten Rechtecks liegt an einer Hüllkante.
    # Deren Projektionen liefern die beiden Maße unmittelbar. GEOS baut
    # stattdessen die vier Ecken zurück und meldet dabei auf macOS/arm64
    # schon für gültige Rechtecke Division durch null (GEOS #1235).
    # Wir brauchen nur die Maße, keine rekonstruierten Schnittpunkte.
    points = np.asarray(hull.exterior.coords, dtype=np.float64)
    local = points[:-1] - points[0]
    x, y = local[:, 0], local[:, 1]
    smallest_area = math.inf
    shortest = None
    for start, end in pairwise(points):
        # Die Richtung vor dem Zentrieren bestimmen: Nahe Randpunkte können
        # beim Abziehen eines weiter entfernten Ursprungs zusammenrunden.
        dx, dy = float(end[0] - start[0]), float(end[1] - start[1])
        length = math.hypot(dx, dy)
        along = x * (dx / length) + y * (dy / length)
        across = y * (dx / length) - x * (dy / length)
        width, height = float(np.ptp(along)), float(np.ptp(across))
        area = width * height
        if area < smallest_area:
            smallest_area = area
            shortest = min(width, height)
    return shortest


#: Wie fein :func:`_exact_width` die Kanten einer exakten Öffnung abtastet, in
#: Millimetern. An einem runden Rand liegt das Rechteck aus den Punkten um
#: höchstens das Doppelte innen; die Weite geht auf vier Stellen gerundet in
#: die Passung (``_measurable``).
WIDTH_SAG: Final = 1e-3


def _exact_width(faces: list[Any], *, cancelled: CancelToken | None = None) -> float:
    """Die schmale Seite ebener exakter Flächen in XY, in jeder Drehung — wie am Netz.

    Das kleinste umschließende Rechteck braucht Punkte; sie kommen von den
    Kanten der Flächen, nach Abweichung ``WIDTH_SAG`` abgetastet, die Ecken
    genau. Gerade Ränder bestimmt es damit exakt. An einem runden Rand läge
    es bis zu zweimal ``WIDTH_SAG`` innen — dort gilt das achsparallele
    Hüllrechteck, das ohne Kantentoleranz gemessen ist und nie schmaler als
    die Drehung: Eine runde Öffnung von 40 mm misst 40, ein um 45 Grad
    gedrehtes Quadrat von 30 mm misst 30 und nicht seine Diagonale.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from shapely.geometry import MultiPoint

    from app.core.brep.kernel import box_limits

    box = Bnd_Box()
    points: list[tuple[float, float]] = []
    for entry in faces:
        BRepBndLib.AddOptimal_s(entry, box, False, False)
        edges = TopExp_Explorer(entry, TopAbs_EDGE)
        while edges.More():
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            curve = BRepAdaptor_Curve(TopoDS.Edge(edges.Current()))
            sampler = GCPnts_QuasiUniformDeflection(curve, WIDTH_SAG)
            if sampler.IsDone():
                for index in range(1, sampler.NbPoints() + 1):
                    point = sampler.Value(index)
                    points.append((float(point.X()), float(point.Y())))
            edges.Next()
    low_x, low_y, _low_z, high_x, high_y, _high_z = box_limits(box)
    aligned = float(min(high_x - low_x, high_y - low_y))
    turned = _short_side(MultiPoint(points)) if len(points) >= 3 else None
    if turned is None or turned >= aligned - 2.0 * WIDTH_SAG:
        return aligned
    return turned


def _measurable(
    identifier: str, area: float, centre: tuple[float, float, float], width: float, *, inner: bool
) -> tuple[str, Feature]:
    """Ein Flächenmerkmal, das zusätzlich seine Weite kennt.

    Ohne die Weite ist die Passung zwar eingetragen, aber nicht prüfbar:
    ``fits.check`` sucht bei einer Spielpassung zwei Durchmesser und meldet
    sonst „lässt sich nicht messen". Eine Passung, die nur dasteht, ist die
    halbe Zusicherung — sie wirkt auf den Slicer und sagt nichts darüber, ob
    der Deckel passt.
    """
    key, feature = face(identifier, area, centre)
    params = dict(feature.params)
    params["diameter"] = round(width, 4)
    params["fit_role"] = "inner" if inner else "outer"
    return key, dataclasses.replace(feature, params=params)


def _collar_feature(
    cavities: list[Any], z: float, collar: float, clearance: float
) -> dict[str, Any]:
    """Das Kragenmerkmal des Deckels — und nichts, wenn es keinen Kragen gibt.

    ``build`` überspringt den Kragen bei ``collar <= EPS_GEOM``: „Null heißt:
    flacher Deckel ohne Kragen" steht so im Parameter. Das Merkmal wurde
    trotzdem eingetragen, mitsamt einer Weite. Eine Passung, die darauf zeigt,
    misst danach Geometrie, die es nicht gibt — und meldet sie als in Ordnung,
    denn die Zahlen im Merkmal stimmen ja. Ein Merkmal ohne Körper ist die
    schlechteste Sorte Zusicherung: Sie hält, bis jemand das Teil in der Hand
    hat.
    """
    if collar <= EPS_GEOM:
        return {}
    return dict(
        [
            _measurable(
                COLLAR_FEATURE,
                _area_of(cavities),
                _centre_of(cavities, z),
                # Der Kragen ist genau um Spiel und Entlastung schmaler als die
                # Öffnung — beidseitig, also zweimal. Dieselbe Rechnung, die
                # ``build`` mit ``buffer`` an der Kontur macht.
                _narrowest(cavities) - clearance,
                inner=False,
            )
        ]
    )


def _with_cavity(source: SceneObject, cavities: list[Any], z: float) -> dict[str, Any]:
    """Die Merkmale der Schachtel plus dem, auf das der Deckel passt.

    Die Öffnung war bis hierher namenlos: die Erkennung sieht einen Hohlraum,
    aber kein Merkmal, das eine Passung benennen könnte. Der Deckel weiß es
    besser — er hat gerade hineingeschnitten.
    """
    features = dict(source.features)
    key, feature = _measurable(
        CAVITY_FEATURE,
        _area_of(cavities),
        _centre_of(cavities, z),
        _narrowest(cavities),
        inner=True,
    )
    features[key] = feature
    return features


def opening(mesh: MeshData, z: float) -> tuple[Any, list[Any]]:
    """Der Wandring auf dieser Höhe, als gefüllter Umriss plus was darin offen
    ist.

    Der Schnitt selbst ist ein Ring — Wandmaterial mit dem Hohlraum als Loch.
    Der Deckel soll dieses Loch *bedecken*, also kommt als Umriss der
    aufgefüllte Ring zurück; den Schnitt zu nehmen, wie er ist, ergäbe einen
    Deckel mit herausgeschnittener Öffnung.

    Wirft, wenn es nichts zu schließen gibt: ein Körper, der hier massiv ist,
    hat keine Öffnung, und ein Deckel darüber wäre eine auf einen Block
    geklebte Platte.
    """
    from shapely.ops import unary_union

    section = cross_section(mesh, z)
    if section is None or section.is_empty:
        raise _no_section(z)

    parts = list(getattr(section, "geoms", [section]))
    cavities = [ring for part in parts for ring in _holes_of(part) if ring.area >= MIN_CAVITY]
    if not cavities:
        raise _no_cavity(z)
    return unary_union([_filled(part) for part in parts]), cavities


def _no_section(z: float) -> ValidationError:
    """Die Ebene trifft den Körper nicht — derselbe Satz für Netz und exakten Körper."""
    return ValidationError(
        field="z",
        detail=_("Auf dieser Höhe schneidet die Ebene den Körper nicht."),
        value=round(z, 2),
        constraint="no_section",
    )


def _no_cavity(z: float) -> ValidationError:
    """Der Körper ist auf der Höhe massiv — derselbe Satz für Netz und exakten Körper."""
    return ValidationError(
        field="z",
        detail=_("Der Körper ist auf dieser Höhe massiv — es gibt nichts zu verschließen."),
        value=round(z, 2),
        constraint="no_cavity",
    )


@dataclasses.dataclass(frozen=True, slots=True)
class _ExactCavity:
    """Ein Hohlraum am exakten Körper, mit den Maßen, nach denen die Merkmale fragen.

    ``_area_of`` und ``_centre_of`` lesen am Netz ein shapely-Polygon:
    ``area`` und ``centroid``. Der exakte Hohlraum antwortet unter denselben
    Namen aus seiner Fläche — Inhalt und Schwerpunkt als Integral, der
    Hüllquader ohne Kantentoleranz —, damit die Passungsmaße eine Rechnung
    bleiben und nicht zwei. Die schmale Seite in jeder Drehung
    (``narrowest``, :func:`_exact_width`) misst er beim Schneiden mit; am Netz
    rechnet :func:`_narrowest` sie aus dem Polygon.
    """

    face: Any
    area: float
    centroid: Any
    bounds: tuple[float, float, float, float]
    narrowest: float


def exact_opening(
    solid: Any, z: float, *, cancelled: CancelToken | None = None
) -> tuple[list[Any], list[_ExactCavity]]:
    """Die Öffnung am exakten Körper: gefüllte Umrisse und Hohlräume auf dieser Höhe.

    Das Gegenstück zu :func:`opening`, aus den Flächen statt aus der
    Vernetzung geschnitten (``brep.section.horizontal_regions``): Ein
    gerundeter Hohlraum bleibt gerundet, und der Kragen, der daraus entsteht,
    liegt an der echten Wand und nicht an ihrer Sehne. Dieselbe Grenze für
    eine Bohrung (``MIN_CAVITY``), dieselben Absagen.
    """
    from app.core.brep.section import horizontal_regions

    regions = horizontal_regions(solid, z, cancelled=cancelled)
    if not regions:
        raise _no_section(z)
    cavities: list[_ExactCavity] = []
    for region in regions:
        for hole in region.holes:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            measured = _measured(hole, cancelled=cancelled)
            if measured.area >= MIN_CAVITY:
                cavities.append(measured)
    if not cavities:
        raise _no_cavity(z)
    return [region.outline for region in regions], cavities


def _measured(face: Any, *, cancelled: CancelToken | None = None) -> _ExactCavity:
    """Inhalt, Schwerpunkt und Hüllrechteck einer ebenen Fläche in XY."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from shapely.geometry import Point

    from app.core.brep.kernel import box_limits
    from app.core.brep.properties import properties

    measured = properties(face, "surface", cancelled=cancelled)
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(face, box, False, False)
    low_x, low_y, _low_z, high_x, high_y, _high_z = box_limits(box)
    return _ExactCavity(
        face,
        float(measured.mass),
        Point(measured.centre[0], measured.centre[1]),
        (float(low_x), float(low_y), float(high_x), float(high_y)),
        _exact_width([face], cancelled=cancelled),
    )


def collar_footprints(cavities: list[Any], blocked: Any | None) -> list[Any]:
    """Wo ein Kragen hinab darf: der Hohlraum am Rand ohne das, was am Kragenboden im Weg steht.

    Geschnitten wird knapp unter dem Rand (``BELOW_RIM``) und am Boden des
    Kragens. Bei einem Deckelsitz, einer gefasten oder verrundeten Innenkante
    und einer Formschräge ist der Rand die weiteste Stelle; ein Kragen aus
    diesem Schnitt allein ragte darunter in die Wand. Der Grundriss ist
    deshalb der Hohlraum oben, vermindert um das Material unten — die engste
    Öffnung über die Kragentiefe, soweit zwei Schnitte sie zeigen. Was
    dazwischen vorsteht, fängt :func:`collar_collision`.
    """
    if blocked is None or blocked.is_empty:
        return list(cavities)
    free: list[Any] = []
    for cavity in cavities:
        rest = cavity.difference(blocked)
        pieces = [
            piece
            for piece in getattr(rest, "geoms", [rest])
            if piece.geom_type == "Polygon" and piece.area > EPS_GEOM
        ]
        # Bleibt nichts, liegt der Kragenboden im Boden des Hohlraums: Der
        # Hohlraum bleibt der Grundriss, und die Prüfung gegen den Körper
        # nennt die freie Tiefe. Den Kragen still wegzulassen wäre geraten.
        free.extend(pieces or [cavity])
    return free


def exact_footprints(
    cavities: list[_ExactCavity],
    solid: Any,
    z: float,
    top: float,
    *,
    cancelled: CancelToken | None = None,
) -> list[_ExactCavity]:
    """:func:`collar_footprints` am exakten Körper — das Material am Kragenboden abgezogen.

    ``z`` ist die Höhe des zweiten Schnitts, ``top`` die der Hohlräume. Die
    Flächen liegen in zwei Ebenen, und eine Boolesche zwischen ihnen fände
    nichts Gemeinsames: Das Material wird deshalb in die Ebene der Hohlräume
    gehoben, wie der Netzweg beide Schnitte in derselben Zeichenebene
    vergleicht. Trifft der zweite Schnitt nichts, bleibt der Hohlraum.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep import profiles
    from app.core.brep.section import horizontal_regions

    regions = horizontal_regions(solid, z, cancelled=cancelled)
    if not regions:
        return list(cavities)
    lift = gp_Trsf()
    lift.SetTranslation(gp_Vec(0.0, 0.0, top - z))
    material = BRepBuilderAPI_Transform(
        _compound([region.face for region in regions]), lift, True
    ).Shape()
    free: list[_ExactCavity] = []
    for cavity in cavities:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        rest = profiles.face_boolean("difference", cavity.face, material)
        pieces: list[_ExactCavity] = []
        walk = TopExp_Explorer(rest, TopAbs_FACE)
        while walk.More():
            piece = _measured(profiles.upward(TopoDS.Face(walk.Current())), cancelled=cancelled)
            walk.Next()
            if piece.area > EPS_GEOM:
                pieces.append(piece)
        # Wie am Netz: Bleibt nichts, bleibt der Hohlraum, und die Prüfung
        # gegen den Körper nennt die freie Tiefe (:func:`collar_footprints`).
        free.extend(pieces or [cavity])
    return free


def _compound(shapes: list[Any]) -> Any:
    """Mehrere Formen als ein Werkzeug für eine Boolesche."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def _collar_hits_wall(free: float, collar: float) -> ValidationError:
    """Der Kragen ragt in die Wand — mit der Tiefe, bis zu der er frei wäre."""
    return ValidationError(
        field="collar",
        detail=_(
            "Der Kragen stößt unter dem Rand auf die Wand. Wählen Sie eine "
            "Kragentiefe bis zur freien Tiefe oder null."
        ),
        value=round(collar, 2),
        constraint="collar_hits_wall",
        values={"free_depth_mm": round(max(free, 0.0), 2), "collar_mm": round(collar, 2)},
    )


def collar_collision(
    collars: list[Any], housing: Any, *, cancelled: CancelToken | None = None
) -> float | None:
    """Die höchste Stelle, an der ein exakter Kragen in die Wand ragt — ``None``, wenn keiner.

    Berührung zählt nicht: Erst ein gemeinsamer Teil mit mehr Volumen als
    eine Schicht von ``EPS_GEOM`` über der Kragenfläche ist ein Stoß. Die
    Frage geht über ``boolean_builder``: Das Gehäuse ist hier oft die Form
    des Eingangs selbst, und eine Boolesche ohne ``SetNonDestructive`` darf
    die Toleranzen ihrer Argumente ändern.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from app.core.brep.kernel import boolean_builder, box_limits

    highest: float | None = None
    for collar in collars:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        common = boolean_builder("intersection", collar.shape, housing.shape)
        common.Build()
        if not common.IsDone():
            continue
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common.Shape(), props)
        extent = collar.bounds.size
        if abs(float(props.Mass())) <= EPS_GEOM * float(extent[0]) * float(extent[1]):
            continue
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(common.Shape(), box, False, False)
        top = box_limits(box)[5]
        highest = top if highest is None else max(highest, top)
    return highest


def exact_build(
    outlines: list[Any],
    footprints: list[_ExactCavity],
    *,
    thickness: float,
    collar: float,
    clearance: float,
    z: float,
    lift: float,
    housing: Any,
    cancelled: CancelToken | None = None,
    keeps: list[Any | None] | None = None,
) -> Any:
    """Platte plus Kragen als exakter Körper — dieselbe Bauweise wie :func:`build`.

    Die Flächen liegen in der Schnittebene, ``lift`` darunter auf der Höhe
    ``z`` der Öffnung: Die Platte wächst von dort um ``thickness`` nach oben,
    jeder Kragen reicht ``collar`` hinab. Der Kragen ist sein Grundriss
    (:func:`exact_footprints`), um das halbe Spiel je Seite eingezogen
    (``profiles.shrunk_faces``); an einer einspringenden Ecke läuft er im
    Bogen um sie herum, wo die Gehrung des Netzwegs etwas mehr wegnimmt. Ragt
    ein Kragen trotzdem in das Gehäuse, entsteht kein Deckel, sondern die
    Absage mit der freien Tiefe.

    ``keeps`` schneidet jeden Kragen eines Scharnierdeckels auf den Raum, in
    dem er beim Öffnen frei bleibt (``lid_hinge.collar_keep``), je Grundriss.
    """
    from app.core.brep import edit, profiles

    plates = [profiles.prism(face, thickness, bottom=lift) for face in outlines]
    collars = []
    for index, footprint in enumerate(footprints if collar > EPS_GEOM else []):
        keep = keeps[index] if keeps else None
        for piece in profiles.shrunk_faces(footprint.face, clearance / 2.0):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            body = profiles.prism(piece, collar, bottom=lift - collar)
            if keep is not None:
                body = edit.boolean("intersection", [body, keep])
                if body.volume <= EPS_GEOM:
                    continue
            collars.append(body)
    top = collar_collision(collars, housing, cancelled=cancelled)
    if top is not None:
        raise _collar_hits_wall(z - top, collar)
    bodies = [*plates, *collars]
    if len(bodies) == 1:
        return bodies[0]
    return edit.unified(edit.boolean("union", bodies))


def _filled(part: Any) -> Any:
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon(part.exterior)


def _holes_of(part: Any) -> list[Any]:
    from shapely.geometry import Polygon as ShapelyPolygon

    return [ShapelyPolygon(ring) for ring in getattr(part, "interiors", [])]


def plane_of(source: SceneObject, name: str, stated: float | None) -> float:
    """Die Höhe, auf der die Öffnung liegt: aus der gewählten Fläche, oder aus
    der Zahl.

    Eine Fläche schlägt die Zahl, denn sie ist die spezifischere von beiden —
    ohne Zahl gilt die Oberkante des Körpers, was eine Vermutung ist, während
    eine Fläche das ist, was jemand angeklickt hat. Die Null ist eine Höhe
    wie jede andere, das Bett (RM-526); bis Format 46 hieß sie „Oberkante“,
    und die Migration leert sie (``migrations._empty_the_top_edge``). Beide stehen
    in der Datei — die Antwort hängt also nicht davon ab, was beim
    Wiederöffnen des Projekts gerade ausgewählt ist (§11).

    Eine Fläche, die nicht nach oben schaut, wird abgewiesen statt als Höhe
    gelesen. Jede Fläche hat einen Mittelpunkt mit einem Z darin, und die
    Decke eines Hohlraums einen, der im Teil liegt — als Öffnungshöhe
    genommen setzte er den Deckel mitten in die Box, auf 26,9 von 30
    Millimetern, und weiter unten fiel es niemandem auf, weil ein Schnitt
    unter dieser Ebene die Wand ja trifft.
    """
    if not name:
        return float(source.mesh.bounds.maximum[2]) if stated is None else stated

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if feature.kind != "face":
        raise ValidationError(
            field="at_feature",
            detail=_("Ein Deckel braucht eine Fläche, kein anderes Merkmal."),
            value=name,
            constraint="not_a_face",
            values={"kind": feature.kind},
        )
    if not faces_up(feature):
        raise ValidationError(
            field="at_feature",
            detail=_("Diese Fläche zeigt nicht nach oben — eine Öffnung für einen Deckel schon."),
            value=name,
            constraint="not_upright",
        )
    centre = feature.params.get("centre") or (0.0, 0.0, 0.0)
    return float(centre[2])


def reason_against(source: SceneObject, name: str) -> str | None:
    """Warum an dieser Fläche kein Deckel entsteht — oder ``None``.

    Derselbe Satz, den *Deckel erzeugen* und *Drehdeckel erzeugen* beim
    Rechnen werfen, nur **vor** dem Klick: Die Auswahlkarte fragt hier, bevor
    sie die zwei Knöpfe freigibt. Gemessen am 14.09.2026 an einer massiven
    Platte (Bedienweg-Durchsicht): beide an jeder Fläche bedienbar, und jeder
    Klick endete in „Der Körper ist auf dieser Höhe massiv" oder „Diese Fläche
    zeigt nicht nach oben" — während *Offene Fläche schließen* daneben seit
    RM-168 grau stand. Zwei Fragen in der Reihenfolge der Operation: Liegt
    die Fläche außen und zeigt sie nach einer Achse (:func:`opening_frame` —
    seit RM-087 auch eine Seite, nicht nur die Decke), und ist der Körper
    dahinter offen (:func:`opening`, ein Schnitt knapp unter dem Rand, im
    aufgerichteten Raum wie beim Bauen)? Wer die zweite an einem großen Netz
    nicht bezahlen will, fragt vorher nach der Dreieckszahl — das Fenster tut
    es über dieselbe Grenze wie bei den Körperfakten
    (``labels.BODY_FACTS_LIMIT``).
    """
    try:
        z, direction = opening_frame(source, name, None)
        mesh = as_mesh_data(source.mesh)
        if direction != _UP:
            mesh = transform.apply(mesh, upright_normal(direction))
        opening(mesh, z - BELOW_RIM)
    except ValidationError as refused:
        return str(refused.detail) if refused.detail is not None else str(refused.title)
    return None


#: Die Öffnung nach oben — die Richtung, in der ein Deckel schon immer lag.
_UP: Vec3 = (0.0, 0.0, 1.0)


def opening_frame(source: SceneObject, name: str, stated: float | None) -> tuple[float, Vec3]:
    """Wo die Öffnung liegt und wohin sie zeigt (RM-087).

    Das Gegenstück zu :func:`plane_of` für einen Deckel, der nicht nur oben
    liegt: Ein Puppenhaus, vorn ausgehöhlt, bekommt seine Front als Deckel.
    Zurück kommt die Höhe der Öffnung **im aufgerichteten Raum** — dem, in dem
    die gewählte Fläche nach oben zeigt — und die Richtung selbst. Ohne
    Fläche gilt, was immer galt: die Zahl oder, ohne Zahl, die Oberkante,
    nach oben.

    Angenommen wird jede Fläche, die nach einer Achse zeigt und **außen**
    liegt. Die Decke eines Hohlraums zeigt nach unten und liegt innen; als
    Öffnung genommen setzte sie den Deckel mitten in die Box (siehe
    :func:`plane_of`). Das Außen-Kriterium hält den Fall in jeder Richtung
    fest: Die Mitte der Fläche liegt am Rand des Hüllquaders in ihrer
    Normalenrichtung. Eine schräge Fläche wird abgewiesen — der Schnitt durch
    die Wand ist ein Ebenenschnitt, und ein Deckel auf einer geraden Seite ist
    das, was der Klick versprochen hat.
    """
    if not name:
        return plane_of(source, name, stated), _UP
    feature = _face_named(source, name)
    normal = vec3_or_none(feature.params.get("normal"))
    axis = dominant_axis(normal) if normal is not None else None
    if normal is None or axis is None:
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Diese Fläche ist schräg. Ein Deckel liegt auf einer geraden Seite — "
                "wählen Sie eine Fläche, die nach einer Achse zeigt."
            ),
            value=name,
            constraint="not_axis_aligned",
        )
    index = "xyz".index(axis)
    sign = 1.0 if normal[index] > 0.0 else -1.0
    direction = [0.0, 0.0, 0.0]
    direction[index] = sign
    centre = vec3_or_none(feature.params.get("centre")) or (0.0, 0.0, 0.0)
    bounds = source.mesh.bounds
    edge = bounds.maximum[index] if sign > 0.0 else bounds.minimum[index]
    # Die Toleranz ist die des Netzes, nicht der Anzeige: Eine Fläche, deren
    # Mitte einen Rasterschritt hinter dem Rand liegt, ist die Decke eines
    # ausgehöhlten Hohlraums und keine Außenseite.
    if abs(float(centre[index]) - float(edge)) > BELOW_RIM:
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Diese Fläche liegt im Inneren — eine Öffnung für einen Deckel "
                "liegt außen am Körper."
            ),
            value=name,
            constraint="not_outside",
        )
    return sign * float(centre[index]), (direction[0], direction[1], direction[2])


def _face_named(source: SceneObject, name: str) -> Feature:
    """Die Fläche dieses Namens an diesem Körper — oder die Absage, warum nicht."""
    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if feature.kind != "face":
        raise ValidationError(
            field="at_feature",
            detail=_("Ein Deckel braucht eine Fläche, kein anderes Merkmal."),
            value=name,
            constraint="not_a_face",
            values={"kind": feature.kind},
        )
    return feature


def build(
    outline: Any,
    footprints: list[Any],
    *,
    thickness: float,
    collar: float,
    clearance: float,
    z: float,
    housing: MeshData | None = None,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    keeps: list[Any | None] | None = None,
) -> tuple[MeshData, SolverInfo | None]:
    """Platte plus Kragen, stehend auf dem Rand der Öffnung.

    Die Platte deckt den ganzen Umriss ab, damit sie aussieht wie die Box, zu
    der sie gehört. Der Kragen greift in jeden Hohlraum hinab — eine
    unterteilte Box bekommt einen je Fach, denn genau das hält den Deckel vom
    Verdrehen ab. ``footprints`` sind die Grundrisse der Kragen
    (:func:`collar_footprints`); mit ``housing`` wird jeder Kragen gegen das
    Gehäuse geprüft, und ragt einer hinein, entsteht kein Deckel, sondern die
    Absage mit der freien Tiefe.
    """
    plates = [
        trimesh.creation.extrude_polygon(piece, height=thickness)
        for piece in getattr(outline, "geoms", [outline])
    ]
    for plate in plates:
        transform.moved(plate, transform.translation((0.0, 0.0, z)))

    collars = []
    stages: list[SolverInfo | None] = []
    for index, footprint in enumerate(footprints if collar > EPS_GEOM else []):
        # Halbes Spiel je Seite, denn ``clearance`` ist ein Durchmessermaß.
        shrunk = footprint.buffer(-clearance / 2.0, join_style=2)
        if shrunk.is_empty or shrunk.area <= EPS_GEOM:
            continue
        keep = keeps[index] if keeps else None
        for piece in getattr(shrunk, "geoms", [shrunk]):
            body = trimesh.creation.extrude_polygon(piece, height=collar)
            transform.moved(body, transform.translation((0.0, 0.0, z - collar)))
            if keep is not None:
                # Der Kragen eines Scharnierdeckels endet, wo er beim Öffnen
                # an die Gegenwand käme (``lid_hinge.collar_keep``).
                trimmed = boolean(
                    "intersection", [MeshData.of(body), keep], quality=quality, cancelled=cancelled
                )
                stages.append(trimmed.solver)
                if not trimmed.mesh.triangle_count:
                    continue
                body = trimmed.mesh.raw
            collars.append(body)
    if housing is not None:
        top = _mesh_collar_collision(collars, housing, quality=quality, cancelled=cancelled)
        if top is not None:
            raise _collar_hits_wall(z - top, collar)

    bodies = [*plates, *collars]
    if len(bodies) == 1:
        return MeshData.of(bodies[0]), deepest(stages) if stages else None
    joined = MeshData.of(bodies[0])
    for entry in bodies[1:]:
        outcome = boolean(
            "union", [joined, MeshData.of(entry)], quality=quality, cancelled=cancelled
        )
        joined = outcome.mesh
        stages.append(outcome.solver)
    return joined, deepest(stages)


def _mesh_collar_collision(
    collars: list[Any],
    housing: MeshData,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> float | None:
    """:func:`collar_collision` am Netz: die höchste Stelle eines Stoßes oder ``None``."""
    highest: float | None = None
    for collar in collars:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        low, high = collar.bounds
        if shared_volume(collar, housing.raw) <= EPS_GEOM * float(high[0] - low[0]) * float(
            high[1] - low[1]
        ):
            continue
        common = boolean(
            "intersection",
            [MeshData.of(collar), housing],
            quality=quality,
            cancelled=cancelled,
        ).mesh
        top = float(common.bounds.maximum[2]) if common.triangle_count else float(high[2])
        highest = top if highest is None else max(highest, top)
    return highest


def _saved_top_edge_marker() -> Any:
    """Der Marker der Migration 46 → 47 an *Deckel erzeugen* und *Drehdeckel erzeugen*.

    Bis Format 46 hieß die Höhe null „Oberkante“. Eine Zahl null leert die
    Migration; ein **Ausdruck** wird erst bei der Auswertung zur Zahl, und ein
    Schritt aus einer solchen Datei liest sie mit dem Marker wie damals
    (:func:`stated_height`). Eine Änderung der Höhe rechnet wie heute.
    """
    return param(
        title=_("Höhe der Öffnung aus einem älteren Projekt"),
        default=False,
        placement="advanced",
        internal=True,
        # Nur die Höhe selbst hebt ihn auf: Wer an einem alten Deckel die Stärke
        # ändert, behält die Öffnung, wo sie war (Review RM-526, K8).
        dropped_on_change=("z",),
        doc=_(
            "Liest eine Höhe, die null ergibt, als Oberkante, wie Projekte bis Format 46. "
            "Eine neue Höhe rechnet wie heute."
        ),
    )


def stated_height(params: LidParams | ScrewLidParams) -> float | None:
    """Die Höhe der Öffnung, wie der Schritt sie meint — ``None`` heißt Oberkante.

    Leer heißt Oberkante, jede Zahl ist eine Welthöhe (RM-526). Nur ein Schritt
    mit ``legacy_zero_top`` liest eine Null noch als Oberkante: Sein Ausdruck
    stammt aus einem Projekt bis Format 46 und ergab dort die Oberkante.
    """
    # Genau die Lesart von damals (``stated or`` Oberkante), wie die Migration
    # sie für eine gespeicherte Zahl liest — keine zweite Regel mit Toleranz.
    if params.legacy_zero_top and params.z is not None and not params.z:
        return None
    return params.z


@op_params
class LidParams(BaseParams):
    thickness: float = param(
        title=_("Deckelstärke"),
        default=2.4,
        unit="mm",
        minimum=0.4,
        maximum=50.0,
        doc=_("Wie dick die Deckelplatte wird — der Kragen darunter kommt aus dem Hohlraum."),
    )
    collar: float = param(
        title=_("Kragentiefe"),
        default=4.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Kragen in die Öffnung reicht. Null heißt: flacher Deckel ohne Kragen."),
        placement="advanced",
        zero_text=ZERO_NONE,
    )
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        # **Kein ``required``, und das ist gemessen**: ``plane_of`` fällt
        # bei leerem Namen auf die Zahl zurück (ohne Zahl auf die
        # Oberkante), der Deckel entsteht also auch ohne Fläche. Am
        # 27.08.2026 stand hier einmal ``required=True`` — hergeleitet
        # daraus, dass die Datei ``ValidationError`` zu ``at_feature``
        # wirft. Sie wirft aber für ein **untaugliches** Merkmal, nicht
        # für ein fehlendes. Das ausgelieferte Beispiel mit dem Deckel
        # lässt es leer, und die Auswertung hielt daraufhin an.
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    # **Leer heißt Oberkante, und die Null ist eine Höhe** (RM-526): Die Höhe
    # ist eine Welthöhe, ein Körper darf unter dem Bett liegen, und Projekte
    # bis 0.5.2 tragen negative Höhen — ein Mindestwert null für den Namen
    # „Oberkante“ hielt sie an (Durchsicht 0.5.3, Fund 9). Als ``optional``
    # steht der Name am leeren Zustand, und jede Zahl bleibt eine Zahl.
    z: float | None = param(
        title=_("Höhe der Öffnung"),
        default=None,
        optional=True,
        unit="mm",
        doc=_("Leer heißt: die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
        placement="advanced",
        zero_text=ZERO_TOP_EDGE,
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: der Wert aus dem Materialprofil."),
        zero_text=ZERO_FROM_PROFILE,
    )
    hinge: str = param(
        title=_("Scharnier"),
        default="none",
        choices=HINGES,
        doc=_(
            "Ohne Scharnier liegt der Deckel lose auf. Mitgedruckt kommt er schon "
            "beweglich aus dem Drucker; mit Stift bekommen Gehäuse und Deckel Augen "
            "für einen Stift, der eigens entsteht."
        ),
    )
    hinge_side: str = param(
        title=_("Scharnierseite"),
        default="hinge_back",
        choices=HINGE_SIDES,
        placement="advanced",
        depends_on=("hinge", ("barrel", "loose_pin")),
        doc=_("An welcher Seite der Öffnung die Achse liegt, von der Öffnung aus gesehen."),
    )
    hinge_width: float = param(
        title=_("Scharnierbreite"),
        default=27.0,
        unit="mm",
        minimum=8.0,
        maximum=120.0,
        placement="advanced",
        depends_on=("hinge", ("barrel", "loose_pin")),
        doc=_("Gesamtbreite über alle Augen, längs der Achse gemessen."),
    )
    hinge_pin: float = param(
        title=_("Scharnierstift"),
        default=3.0,
        unit="mm",
        minimum=2.0,
        maximum=20.0,
        placement="advanced",
        depends_on=("hinge", ("barrel", "loose_pin")),
        doc=_("Durchmesser der Achse. Die Bohrungen darum sind um das Spiel weiter."),
    )
    hinge_wall: float = param(
        title=_("Scharnierwand"),
        default=2.5,
        unit="mm",
        minimum=1.0,
        maximum=15.0,
        placement="advanced",
        depends_on=("hinge", ("barrel", "loose_pin")),
        doc=_("Materialdicke um die Bohrung jedes Auges."),
    )
    opening_angle: float = param(
        title=_("Öffnungswinkel"),
        default=180.0,
        unit="°",
        minimum=0.0,
        maximum=180.0,
        placement="advanced",
        depends_on=("hinge", ("barrel",)),
        doc=_(
            "Wie weit der mitgedruckte Deckel aufgeklappt entsteht. Bei null liegt er "
            "auf dem Rand und verschweißt beim Drucken mit ihm."
        ),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )
    legacy_zero_top: bool = _saved_top_edge_marker()


@register_op(
    name="create_lid",
    # 3 seit dem Zusammenführen der Durchsicht 0.5.0: Die Weiten der Passung
    # sind die schmale Seite in jeder Drehung (``_narrowest``), nicht die des
    # Hüllrechtecks, und am exakten Gehäuse entsteht der Deckel exakt (P2.8).
    # 4: gemeinsame Weitenmessung ohne GEOS-Rechteckrekonstruktion.
    # 5: Platte und Kragen werden über ``transform.moved`` gehoben.
    # 6: Die Null der Höhe ist das Bett, leer die Oberkante (RM-526).
    cache_version="6",
    title=_("Deckel erzeugen"),
    category="parts",
    params=LidParams,
    consumes=1,
    produces=2,
    keeps_inputs=1,
    applies_to=["face"],
    doc=_(
        "Erzeugt zu einer Öffnung einen passenden Deckel mit Kragen. Der Hohlraum "
        "wird aus dem Körper geschnitten, nicht nachgemessen — das Spiel kommt aus "
        "dem Materialprofil."
    ),
)
def create_lid(ctx: OpContext) -> OpResult:
    """§25: die zweite Hälfte jeder Box.

    Der Deckel bleibt, wo die Öffnung ist, statt aufs Bett zu springen. Ob er
    die Box schließt, ist die Frage, die jemand in diesem Moment hat, und das
    sieht man nur an Ort und Stelle; das Anordnen für den Druck ist eine
    eigene Operation und kennt auch jeden anderen Körper.
    """
    params = cast(LidParams, ctx.params)
    source = ctx.inputs[0]
    # **Der Körper entscheidet** (P2.8, Konzept §10.1): Am exakten Gehäuse
    # entsteht der Deckel exakt, aus dessen Flächen geschnitten — bis zum
    # 23.09.2026 kam er dort als Netz heraus, und sein Kragen lag an den
    # Sehnen der Vernetzung statt an der Wand.
    exact = isinstance(source.mesh, BRepBody)

    # **Gebaut wird immer nach oben** — auch für eine Seitenöffnung (RM-087).
    # Der Körper wird so gedreht, dass die gewählte Fläche nach oben zeigt,
    # der Deckel entsteht wie eh und je, und am Ende dreht dieselbe Matrix
    # ihn zurück vor die Öffnung. Eine zweite Bauweise für Seitendeckel wäre
    # eine zweite Stelle, an der der Kragen sein Spiel bekommt.
    z, direction = opening_frame(source, params.at_feature, stated_height(params))
    # Dieselbe Drehung wie beim Trennen (``upright_normal``): Für die Decke
    # die Einheit, sonst eine Drehung, deren Transponierte zurückführt.
    turn = upright_normal(direction)
    turned_back = turn.T
    cavities: list[Any]
    footprints: list[Any]
    # Der zweite Schnitt liegt knapp über dem Kragenboden, wie der erste
    # knapp unter dem Rand; ein Kragen, der kaum tiefer reicht als dieser
    # Abstand, braucht ihn nicht.
    floor = z - params.collar + BELOW_RIM
    if exact:
        upright = _turned(source.mesh, turn, direction, cancelled=ctx.cancelled)
        outlines, cavities = exact_opening(upright, z - BELOW_RIM, cancelled=ctx.cancelled)
        footprints = (
            exact_footprints(cavities, upright, floor, z - BELOW_RIM, cancelled=ctx.cancelled)
            if params.collar > 2.0 * BELOW_RIM
            else list(cavities)
        )
    else:
        mesh = as_mesh_data(source.mesh)
        if direction != _UP:
            mesh = transform.apply(mesh, turn)
        outline, cavities = opening(mesh, z - BELOW_RIM)
        footprints = collar_footprints(
            cavities,
            cross_section(mesh, floor) if params.collar > 2.0 * BELOW_RIM else None,
        )

    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
            )
        clearance = for_object(ctx.profile, source).material.clearance

    # **Mit Scharnier** (RM-184, Audit §6): Achse, Augen und der Raum, in dem
    # jeder Kragen beim Öffnen frei bleibt, entstehen vor dem Deckel — der
    # Kragen wird gleich beim Bauen darauf geschnitten.
    plan = (
        _hinge_plan(
            as_mesh_data(upright) if exact else mesh,
            z,
            footprints,
            params,
            clearance,
            kernel="brep" if exact else "mesh",
            cancelled=ctx.cancelled,
        )
        if params.hinge != "none"
        else None
    )
    keeps = plan.keeps if plan is not None else None
    body: Any
    solver: SolverInfo | None = None
    if exact:
        body = exact_build(
            outlines,
            footprints,
            thickness=params.thickness,
            collar=params.collar,
            clearance=clearance,
            z=z,
            lift=BELOW_RIM,
            housing=upright,
            cancelled=ctx.cancelled,
            keeps=keeps,
        )
    else:
        body, solver = build(
            outline,
            footprints,
            thickness=params.thickness,
            collar=params.collar,
            clearance=clearance,
            z=z,
            housing=mesh,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
            keeps=keeps,
        )

    _log.info("lid over %d cavities at z=%.2f, clearance %.2f", len(cavities), z, clearance)
    cavity_features = _with_cavity(source, cavities, z)
    # Das Kragenmerkmal beschreibt den Kragen, der entstanden ist: Wo die
    # Öffnung darunter enger wird, ist er schmaler als der Hohlraum am Rand.
    collar_features = _collar_feature(footprints, z, params.collar, clearance) if footprints else {}
    housing_mesh: Any = source.mesh
    housing_features: dict[str, Feature] = {}
    if plan is not None:
        body, collar_features, housing_mesh, housing_features, joined = _hinged(
            plan,
            body,
            collar_features,
            source,
            turned_back,
            direction,
            exact=exact,
            opening_angle=params.opening_angle if params.hinge == "barrel" else 0.0,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
        )
        solver = deepest([solver, *joined])
    if direction != _UP:
        # Träge, weil ``geom`` die Wahrnehmung nicht eifrig laden darf
        # (Paketrichtung, ``test_core_package_direction``).
        from app.core.perceive.matching import moved_features

        body = (
            _turned(body, turned_back, direction, cancelled=ctx.cancelled)
            if exact
            else transform.apply(body, turned_back)
        )
        # Nur das neue Merkmal wird zurückgedreht — die übrigen des Gehäuses
        # haben den aufgerichteten Raum nie gesehen.
        cavity_features = {
            **source.features,
            **moved_features({CAVITY_FEATURE: cavity_features[CAVITY_FEATURE]}, _rows(turned_back)),
        }
        collar_features = moved_features(collar_features, _rows(turned_back))
    lid_features: dict[str, Feature] = dict(collar_features)
    if exact:
        # Ein exakter Körper bringt seine Merkmale aus der Topologie mit
        # (``evaluate._with_features`` erkennt an ihm nicht neu); der Kragen
        # bleibt das benannte Merkmal der Passung.
        from app.core.brep.features import features_of

        lid_features = {**features_of(body, cancelled=ctx.cancelled), **collar_features}
    # Das Gehäuse bleibt der erste Ausgang: eine Op mit consumes=1 ersetzt im
    # Stapel ihre Eingabe durch ihre Ausgaben — mit nur dem Deckel als Ausgang
    # fraß „Deckel erzeugen" das Gehäuse. Die Op-Tests riefen die Funktion
    # direkt auf und sahen es nie; der Ende-zu-Ende-Weg von P13 sah es sofort.
    housing = dataclasses.replace(source, features=cavity_features)
    if plan is not None:
        housing = _hinged_housing(
            source, housing_mesh, cavity_features, housing_features, exact, ctx.cancelled
        )
    return OpResult(
        solver=solver,
        outputs=[
            housing,
            SceneObject(
                id="",
                # **Kein Quellname und kein `.translate()`.** Beides war
                # eine Momentaufnahme: Der Quellname brach, sobald jemand die
                # Dose umbenannte („Dose Deckel" neben „Vorratsbehälter"), und
                # `.translate()` machte aus dem Wort eine feste Zeichenkette —
                # beim Sprachwechsel bei offenem Projekt blieb sie deutsch
                # stehen, während der Körper daneben mitwanderte.
                #
                # Ein Name, der eine Beziehung behauptet und sie nicht hält,
                # ist schlechter als keiner; der Zusammenhang steht im Verlauf.
                name=params.name or _("Deckel"),
                mesh=body,
                kind="brep" if exact else "mesh",
                material=source.material,
                features=lid_features,
            ),
        ],
        findings=[
            Finding(
                code="parts.lid",
                severity="info",
                message=_("Deckel erzeugt — das Spiel kommt aus dem Materialprofil."),
                values={
                    "cavities": len(cavities),
                    "clearance_mm": round(clearance, 3),
                    "z_mm": round(z, 2),
                    # Wohin die Öffnung zeigt, als Wort — „+z" ist die Decke,
                    # „-y" die Vorderseite eines Puppenhauses.
                    "opening": _direction_name(direction),
                },
            ),
            *(_hinge_findings(plan, params) if plan is not None else ()),
        ],
    )


@dataclasses.dataclass(frozen=True, slots=True)
class _HingePlan:
    """Was ein Scharnierdeckel vor dem Bauen weiß: Lage, Kragenraum, Augen."""

    kind: str
    side: str
    layout: Any
    keeps: list[Any | None]
    housing_parts: list[Any]
    lid_parts: list[Any]
    housing_features: dict[str, Feature]
    lid_features: dict[str, Feature]


def _hinge_plan(
    tessellated: MeshData,
    z: float,
    footprints: list[Any],
    params: LidParams,
    clearance: float,
    *,
    kernel: str,
    cancelled: CancelToken | None = None,
) -> _HingePlan:
    """Lage und Teile des Scharniers, im aufgerichteten Rahmen (RM-184, Audit §6).

    Gemessen wird an der Vernetzung des aufgerichteten Gehäuses, an beiden
    Kernen gleich: Umriss und Hohlräume am Rand, dieselben Kragengrundrisse wie
    beim Netzdeckel. Ein exakter Kragen findet seinen Raum über den
    Grundriss, in dem seine Mitte liegt. Gebaut wird im Scharnierrahmen
    (``lid_hinge.spin_of``) und um dieselbe Vierteldrehung zurück.
    """
    from shapely.geometry import Point

    from app.core.geom import lid_hinge
    from app.core.knowledge.parts import shapes

    angle = lid_hinge.spin_of(params.hinge_side)
    outline, cavities = opening(tessellated, z - BELOW_RIM)
    floor = z - params.collar + BELOW_RIM
    measured = collar_footprints(
        cavities,
        cross_section(tessellated, floor) if params.collar > 2.0 * BELOW_RIM else None,
    )
    hinge = lid_hinge.layout(
        lid_hinge.spun(outline, angle),
        [lid_hinge.spun(cavity, angle) for cavity in cavities],
        z=z,
        bottom=float(tessellated.bounds.minimum[2]),
        width=params.hinge_width,
        pin_diameter=params.hinge_pin,
        wall=params.hinge_wall,
        clearance=clearance,
    )

    def back(form: Any) -> Any:
        return shapes.turned(form, -angle, (0.0, 0.0, 1.0)) if angle else form

    with shapes.building(cast(Any, kernel)):
        spaces = [
            back(lid_hinge.collar_keep(lid_hinge.spun(footprint, angle), hinge))
            for footprint in measured
        ]
        housing_parts, lid_parts = lid_hinge.hinge_parts(
            params.hinge,
            hinge,
            pin_diameter=params.hinge_pin,
            wall=params.hinge_wall,
            clearance=clearance,
            cancelled=cancelled,
        )
        housing_parts = [back(part) for part in housing_parts]
        lid_parts = [back(part) for part in lid_parts]
    keeps: list[Any | None]
    if kernel == "brep":
        keeps = []
        for footprint in footprints:
            centre = Point(float(footprint.centroid.x), float(footprint.centroid.y))
            owner = next(
                (index for index, shape in enumerate(measured) if shape.contains(centre)), None
            )
            keeps.append(spaces[owner] if owner is not None else None)
    else:
        keeps = list(spaces)
    housing_features, lid_features = lid_hinge.hinge_features(
        params.hinge, hinge, pin_diameter=params.hinge_pin, clearance=clearance
    )
    if angle:
        from app.core.perceive.matching import moved_features

        spin_back = _rows(transform.rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), -angle))
        housing_features = moved_features(housing_features, spin_back)
        lid_features = moved_features(lid_features, spin_back)
    return _HingePlan(
        kind=params.hinge,
        side=params.hinge_side,
        layout=hinge,
        keeps=keeps,
        housing_parts=housing_parts,
        lid_parts=lid_parts,
        housing_features=housing_features,
        lid_features=lid_features,
    )


def _hinged(
    plan: _HingePlan,
    body: Any,
    collar_features: dict[str, Feature],
    source: SceneObject,
    turned_back: Any,
    direction: Vec3,
    *,
    exact: bool,
    opening_angle: float,
    quality: Quality,
    cancelled: CancelToken | None,
) -> tuple[Any, dict[str, Feature], Any, dict[str, Feature], list[SolverInfo | None]]:
    """Augen an Deckel und Gehäuse, der Deckel aufgeklappt, wo er mitgedruckt wird.

    Zurück kommen Deckelkörper und -merkmale im aufgerichteten Rahmen (das
    Zurückdrehen vor die Öffnung macht :func:`create_lid` wie bisher) und das
    Gehäuse samt seinen Scharniermerkmalen schon im Raum der Szene.
    """
    from app.core.perceive.matching import moved_features

    stages: list[SolverInfo | None] = []
    body = _united(
        body, plan.lid_parts, exact=exact, quality=quality, cancelled=cancelled, stages=stages
    )
    features = {**collar_features, **plan.lid_features}
    if opening_angle:
        # Aufgeklappt um die Achse, im aufgerichteten Rahmen: dieselbe
        # Vierteldrehung zurück wie die Teile, dieselbe Richtung wie am
        # Klappdeckel des Behälters (der Deckel liegt auf der -y-Seite der Achse).
        from app.core.geom import lid_hinge

        spin = lid_hinge.spin_of(plan.side)
        axis_point = _quarter(plan.layout.axis, -spin)
        axis_direction = _quarter((1.0, 0.0, 0.0), -spin)
        opened = transform.rotation_about(axis_direction, axis_point, -opening_angle)
        body = (
            _edited(body, opened, cancelled=cancelled) if exact else transform.apply(body, opened)
        )
        features = moved_features(features, _rows(opened))
    parts = list(plan.housing_parts)
    housing_features = dict(plan.housing_features)
    if direction != _UP:
        parts = [
            _edited(part, turned_back, cancelled=cancelled)
            if exact
            else transform.apply(as_mesh_data(part), turned_back)
            for part in parts
        ]
        housing_features = moved_features(housing_features, _rows(turned_back))
    housing = _united(
        source.mesh, parts, exact=exact, quality=quality, cancelled=cancelled, stages=stages
    )
    return body, features, housing, housing_features, stages


def _quarter(point: Vec3, degrees: float) -> Vec3:
    """Einen Punkt um Z drehen, um ganze Vierteldrehungen ohne Rundungsfehler."""
    quarter = round(degrees / 90.0) % 4
    x, y, z = point
    turned = ((x, y), (-y, x), (-x, -y), (y, -x))[quarter]
    return (turned[0], turned[1], z)


def _edited(solid: Any, matrix: Any, *, cancelled: CancelToken | None) -> Any:
    from app.core.brep import edit

    return edit.transformed(solid, _rows(matrix), cancelled=cancelled)


def _united(
    body: Any,
    parts: list[Any],
    *,
    exact: bool,
    quality: Quality,
    cancelled: CancelToken | None,
    stages: list[SolverInfo | None],
) -> Any:
    """Den Körper mit seinen Scharnierteilen vereinigen, je Kern."""
    if not parts:
        return body
    if exact:
        from app.core.brep import edit

        return edit.unified(edit.boolean("union", [body, *parts]))
    outcome = boolean(
        "union",
        [as_mesh_data(body), *(as_mesh_data(part) for part in parts)],
        quality=quality,
        cancelled=cancelled,
    )
    stages.append(outcome.solver)
    return outcome.mesh


def _hinged_housing(
    source: SceneObject,
    mesh: Any,
    cavity_features: dict[str, Feature],
    hinge_features: dict[str, Feature],
    exact: bool,
    cancelled: CancelToken | None,
) -> SceneObject:
    """Das Gehäuse mit seinen Augen — die benannten Merkmale bleiben, der Rest wird neu erkannt.

    Am Netz tragen die alten Merkmale Dreiecke eines Körpers, den es so nicht
    mehr gibt; die Auswertung erkennt sie am neuen wieder und behält ihre
    Namen. Benannt und ohne Dreiecke reisen nur Öffnung und Scharnier.
    """
    carried = {
        name: dataclasses.replace(feature, face_indices=(), surface_patches=())
        for name, feature in {
            CAVITY_FEATURE: cavity_features[CAVITY_FEATURE],
            **hinge_features,
        }.items()
    }
    features = carried
    if exact:
        from app.core.brep.features import features_of

        features = {**features_of(mesh, cancelled=cancelled), **carried}
    return dataclasses.replace(source, mesh=mesh, features=features)


def _hinge_findings(plan: _HingePlan, params: LidParams) -> list[Finding]:
    """Was der Kunde über das Scharnier wissen muss, bevor er druckt."""
    if plan.kind == "barrel":
        return [
            Finding(
                code="parts.lid_hinge",
                severity="info",
                message=_(
                    "Das Scharnier kommt beweglich aus dem Drucker. Der Kragen ist gekürzt, wo "
                    "er beim Öffnen anstieße."
                ),
                values={
                    "pin_mm": round(params.hinge_pin, 3),
                    "width_mm": round(plan.layout.width, 3),
                    "opening_deg": round(params.opening_angle, 1),
                },
            )
        ]
    return [
        Finding(
            code="parts.lid_hinge",
            severity="info",
            message=_(
                "Gehäuse und Deckel tragen Augen für einen Stift. „Stift für Bohrung“ baut ihn, "
                "Filament oder ein Nagel tun es auch."
            ),
            values={
                "pin_mm": round(params.hinge_pin, 3),
                "width_mm": round(plan.layout.width, 3),
            },
        )
    ]


def _turned(
    solid: Any, matrix: Any, direction: Vec3, *, cancelled: CancelToken | None = None
) -> Any:
    """Den exakten Körper mit dieser Matrix drehen — für die Decke gar nicht.

    ``direction`` ist die Richtung der Öffnung: Zeigt sie nach oben, ist die
    Drehung die Einheit, und der Körper bleibt, wie er ist. ``edit.transformed``
    kopiert und prüft, und das kostet an einem großen Gehäuse mehr als der
    ganze Deckel.
    """
    if direction == _UP:
        return solid
    from app.core.brep import edit

    return edit.transformed(solid, _rows(matrix), cancelled=cancelled)


def _rows(matrix: Any) -> Any:
    """Eine 4x4-Matrix als verschachtelte Tupel — die Form, die ``moved_features``
    als ``Transform`` liest."""
    return tuple(tuple(float(value) for value in row) for row in matrix)


def _direction_name(direction: Vec3) -> str:
    """``+z``, ``-y`` — die Achsrichtung als kurzes Wort für den Bericht."""
    index = max(range(3), key=lambda axis: abs(float(direction[axis])))
    return ("+" if float(direction[index]) > 0.0 else "-") + "xyz"[index]


# --- Der Drehdeckel --------------------------------------------------------------

#: Steigung eines gedruckten Grobgewindes. Grob mit Absicht: ein Glasdeckel
#: wird von Hand gedreht, und eine halbe Umdrehung soll ihn schließen — einen
#: feinen Grat rundet die Düse weg, bis nichts mehr greift.
DEFAULT_PITCH = 3.0

#: Um wie viel die Gewindeschürze des Deckels höher ist als der Hals, damit
#: der Deckel auf dem Rand aufsetzt und nicht auf dem Gewindeende.
SKIRT_RELIEF = 0.6

#: Segmente um einen gedrehten Körper. Gröber, und ein „runder" Hals ist ein
#: Vieleck, an dem der Deckel hakt.
NECK_SECTIONS = 96


def turn_sections(major: float, clearance: float) -> tuple[int, int]:
    """Sehnen je Umlauf für den Gang und für die Rundkörper — dieselben an Hals und Kappe.

    Der Gang folgt ``shapes.turn_segments`` am äußersten Radius; gerechnet wird
    mit dem ganzen Spiel, damit der Grund der Kappennut sicher darunter liegt. Die
    Rundkörper behalten mindestens ``NECK_SECTIONS`` und liegen auf den Winkeln
    des Gangs: achtundvierzig treffen jede zweite Ecke des 96-Ecks, darüber
    sind beide gleich. Bis zum 06.10.2026 hatte der Gang immer achtundvierzig;
    seit der Hals bis Ø 1000 reicht (``units.LARGEST_THREAD``), wären das dort
    1,07 mm Abweichung gewesen (r 500,2 · (1 - cos π/48)). Achtundvierzig bleiben,
    solange Halbmesser und Spiel zusammen unter 23,35 mm liegen — bei 0,2 mm
    Spiel bis Ø 46,3, bei 0,4 mm bis Ø 45,9.
    """
    turn = turn_segments(major / 2.0 + clearance)
    return turn, max(NECK_SECTIONS, turn)


def neck_diameters(outline_width: float, cavities: list[Any]) -> tuple[float, float]:
    """Außen- und Bohrungsdurchmesser eines Halses, der zu dieser Öffnung passt.

    Beide kommen von der schmaleren Seite, nicht aus einem eingepassten Kreis:
    bei einer runden Öffnung *ist* das der Durchmesser, bei einer eckigen der
    größte runde Hals, den die Wand noch tragen kann. Ein Kreis durch die
    Ecken eines Quadrats stünde über dessen Seiten hinaus.

    **Die schmale Seite in jeder Drehung** (:func:`_narrowest`): Bis zum
    22.09.2026 kam sie aus dem achsparallelen Hüllrechteck, und an einer um
    45 Grad gedrehten quadratischen Dose von 50 mm war das die Diagonale —
    ein Hals von 70,7 mm, zehn Millimeter über jeder Seite.
    ``outline_width`` ist die des Umrisses — am Netz aus dem Polygon, exakt
    aus den Flächen (:func:`_exact_width`).
    """
    widest = max(cavities, key=lambda ring: ring.area)
    return outline_width, _narrowest([widest])


def _pipe(
    outer: float,
    inner: float,
    height: float,
    z: float,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    *,
    sections: int = NECK_SECTIONS,
) -> MeshData:
    """Ein Materialring, stehend auf ``z``, ganz durchgehend offen."""
    shell = lathe.cylinder(radius=outer / 2.0, height=height, sections=sections)
    transform.moved(shell, transform.translation((0.0, 0.0, z + height / 2.0)))
    if inner <= EPS_GEOM:
        return MeshData.of(shell)
    bore = lathe.cylinder(
        radius=inner / 2.0, height=height + 2.0 * BOOLEAN_OVERLAP, sections=sections
    )
    transform.moved(bore, transform.translation((0.0, 0.0, z + height / 2.0)))
    # Dieselbe Stufe wie die vier anderen Booleschen des Drehdeckels: fest auf
    # „fine" konnte dieser eine Schnitt beim Iterieren bis zur Voxelstufe laufen,
    # während der Rest in Entwurfsqualität nach Stufe 2 endet (§17.2, §31).
    return boolean(
        "difference",
        [MeshData.of(shell), MeshData.of(bore)],
        quality=quality,
        cancelled=cancelled,
    ).mesh


def _lifted(body: MeshData, z: float) -> MeshData:
    raised = body.raw.copy()
    transform.moved(raised, transform.translation((0.0, 0.0, z)))
    return body.replacing(raised)


#: Die meisten Gänge je Zoll am Drehdeckel: so fein wie seine feinste Steigung, 1 mm.
MOST_LID_TPI: Final = 25.4


@op_params
class ScrewLidParams(BaseParams):
    height: float = param(
        title=_("Gewindehöhe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Wie hoch der Gewindehals wird. Zwei Umdrehungen halten, drei sitzen fest."),
    )
    # **Die benannte Ausnahme von ``units.FINEST_PITCH``**: Ein Schraubdeckel
    # greift feiner als 1 mm nicht mehr sicher, und die Kappe soll mit der Hand
    # aufgehen. Die übrigen Gewindewege beginnen bei 0,25. Seit RM-544 gilt sie
    # der metrischen Gewindeform; in Zoll stehen die Gänge je Zoll dafür.
    pitch: float = param(
        title=_("Steigung"),
        default=DEFAULT_PITCH,
        unit="mm",
        minimum=1.0,
        maximum=COARSEST_PITCH,
        depends_on=("form", ("metric",)),
        doc=_("Abstand benachbarter Gewindegänge entlang der Achse."),
    )
    tpi: float = param(
        title=_("Gänge je Zoll"),
        default=0.0,
        minimum=0.0,
        maximum=MOST_LID_TPI,
        depends_on=("form", ("whitworth", "unified")),
        doc=_(
            "Wie viele Gänge auf einem Zoll liegen, höchstens so fein wie 1 mm Steigung. "
            "Null nimmt G bei Whitworth und UNC bei Unified."
        ),
        zero_text=ZERO_AUTOMATIC,
    )
    thickness: float = param(
        title=_("Deckelstärke"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=50.0,
        doc=_("Dicke der Deckelplatte über dem Gewinde."),
        placement="advanced",
    )
    wall: float = param(
        title=_("Wandstärke des Deckels"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=20.0,
        doc=_(
            "Dicke des Rands, der das Gewinde trägt. Zu dünn reißt beim Aufschrauben "
            "entlang der Schichten auf."
        ),
        placement="advanced",
    )
    neck: float = param(
        title=_("Halsdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=LARGEST_THREAD,
        placement="advanced",
        doc=_("Null nimmt die schmalere Seite der Öffnung."),
        zero_text=ZERO_AUTOMATIC,
    )
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        # **Kein ``required``, und das ist gemessen**: ``plane_of`` fällt
        # bei leerem Namen auf die Zahl zurück (ohne Zahl auf die
        # Oberkante), der Deckel entsteht also auch ohne Fläche. Am
        # 27.08.2026 stand hier einmal ``required=True`` — hergeleitet
        # daraus, dass die Datei ``ValidationError`` zu ``at_feature``
        # wirft. Sie wirft aber für ein **untaugliches** Merkmal, nicht
        # für ein fehlendes. Das ausgelieferte Beispiel mit dem Deckel
        # lässt es leer, und die Auswertung hielt daraufhin an.
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    # Wie ``LidParams.z``: eine Welthöhe, auch unter dem Bett; leer heißt Oberkante.
    z: float | None = param(
        title=_("Höhe der Öffnung"),
        default=None,
        optional=True,
        unit="mm",
        doc=_("Leer heißt: die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
        placement="advanced",
        zero_text=ZERO_TOP_EDGE,
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: der Wert aus dem Materialprofil."),
        zero_text=ZERO_FROM_PROFILE,
    )
    form: str = param(
        title=_("Gewindeform"),
        default="metric",
        choices=CUSTOM_FORMS,
        placement="advanced",
        doc=_(
            "Metrisch mit der Steigung in Millimetern, Whitworth (55°, wie G) oder Unified "
            "(60°, wie UNC) mit Gängen je Zoll."
        ),
    )
    starts: int = param(
        title=_("Gangzahl"),
        default=1,
        minimum=1,
        maximum=MOST_STARTS,
        placement="advanced",
        doc=_(
            "Mehrere Gänge nebeneinander, wie an Flaschen: Der Deckel sitzt nach einem "
            "Bruchteil einer Umdrehung."
        ),
    )
    left_hand: bool = param(
        title=_("Linksgewinde"),
        default=False,
        placement="advanced",
        doc=_("Hals und Deckel drehen gegen den Uhrzeigersinn zu."),
    )
    legacy_zero_top: bool = _saved_top_edge_marker()


def lid_thread(params: ScrewLidParams, major: float) -> tuple[float, ThreadProfile]:
    """Steigung und Gangprofil des Drehdeckels aus seiner Gewindeform (RM-544).

    Metrisch die eingetragene Steigung im druckbaren Profil; Whitworth und
    Unified aus den Gängen je Zoll, null nimmt die Reihe G oder UNC beim
    Durchmesser des Halses (``standards.regular_tpi``).
    """
    from app.core.knowledge import standards

    form = getattr(params, "form", "metric")
    if form not in ("whitworth", "unified"):
        return params.pitch, "flat"
    series = "G" if form == "whitworth" else "UNC"
    count = params.tpi if params.tpi > 0.0 else standards.regular_tpi(major, series)
    pitch = max(25.4 / count, 1.0)
    return pitch, "whitworth" if form == "whitworth" else "flat"


def _lid_profile(params: ScrewLidParams) -> ThreadProfile:
    """Das Gangprofil der Gewindeform — für Rechnungen, die die Steigung schon kennen."""
    return "whitworth" if getattr(params, "form", "metric") == "whitworth" else "flat"


def _lid_lead(params: ScrewLidParams) -> float:
    """Der Vorschub je Umdrehung: so viele Steigungen, wie es Gänge sind."""
    return max(1, int(getattr(params, "starts", 1))) * params.pitch


@register_op(
    name="screw_lid",
    # 3 seit dem Zusammenführen der Durchsicht 0.5.0: Hals und Bohrung messen
    # die schmale Seite in jeder Drehung (``neck_diameters``), der Deckel heißt
    # in jeder Sprache, und am exakten Gehäuse entstehen Hals und Kappe exakt
    # (P2.8).
    # 4: gemeinsame Weitenmessung ohne GEOS-Rechteckrekonstruktion.
    # 5: Das Kappengewinde nennt seinen gebauten Durchmesser (RM-393).
    # 6: Hals und Kappe verwenden dieselben Winkelstationen des Netzes.
    # 7: Die Null der Höhe ist das Bett, leer die Oberkante (RM-526).
    # 8: Gang und Rundkörper über Ø 46 so fein wie die Facettenregel (``turn_sections``).
    # 9: Gewindeform, Gänge je Zoll, Gangzahl und Linksgewinde (RM-544).
    cache_version="9",
    title=_("Drehdeckel erzeugen"),
    category="parts",
    params=ScrewLidParams,
    consumes=1,
    produces=2,
    keeps_inputs=1,
    applies_to=["face"],
    doc=_(
        "Setzt einen Gewindehals auf die Öffnung und erzeugt den passenden "
        "Schraubdeckel. Beide Gewinde kommen aus derselben Steigung, das Spiel "
        "aus dem Materialprofil."
    ),
)
def screw_lid(ctx: OpContext) -> OpResult:
    """§25: der Zwilling des eingeschobenen Deckels.

    Zwei Paare im Modellkorpus sind genau das und nichts anderes:
    ``gewuerzbehaelter_body`` neben ``deckel_dreh``, und ``kartuschen_kaefig``
    neben ``kartuschen_deckel``. Als der Drehdeckel entstand, hatte die
    Bausteinbibliothek ein Gewinde nur in den Schraubengrößen M2 bis M8, und ein
    Glashals von vierzig Millimetern lag außerhalb ihrer Reichweite. Seit dem
    06.10.2026 baut sie jedes Maß; der Drehdeckel bleibt, weil er Hals und
    Kappe aus einer Öffnung zusammen setzt.

    Beide Hälften kommen aus einer Operation, weil sie eine Entscheidung
    sind. Ein Hals mit der einen Steigung und ein Deckel mit einer anderen
    sind nicht zwei Fehler — es ist der eine Fehler, der am leichtesten
    passiert, wenn die Hälften getrennt entstehen.
    """
    params = cast(ScrewLidParams, ctx.params)
    source = ctx.inputs[0]
    # **Der Körper entscheidet** (P2.8, Konzept §10.1): Am exakten Gehäuse
    # entstehen Hals und Kappe exakt — bis zum 23.09.2026 vernetzte diese
    # Operation das Gehäuse und gab beides als Netz zurück.
    exact = isinstance(source.mesh, BRepBody)

    # Dieselbe Drehung wie beim eingeschobenen Deckel (RM-087): Der Hals
    # wächst immer nach oben, und zurück vor die Seitenöffnung dreht ihn die
    # Transponierte. Die Kappe steht am Ursprung und dreht nicht mit — sie ist
    # ein eigenes Teil, und wo sie liegt, entscheidet das Anordnen.
    z, direction = opening_frame(source, params.at_feature, stated_height(params))
    turn = upright_normal(direction)
    turned_back = turn.T
    cavities: list[Any]
    if exact:
        upright = _turned(source.mesh, turn, direction, cancelled=ctx.cancelled)
        outlines, cavities = exact_opening(upright, z - BELOW_RIM, cancelled=ctx.cancelled)
        outline_width = _exact_width(outlines, cancelled=ctx.cancelled)
    else:
        mesh = as_mesh_data(source.mesh)
        if direction != _UP:
            mesh = transform.apply(mesh, turn)
        outline, cavities = opening(mesh, z - BELOW_RIM)
        outline_width = _narrowest([outline])

    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
            )
        clearance = for_object(ctx.profile, source).material.clearance

    major, bore = neck_diameters(outline_width, cavities)
    if params.neck:
        major = params.neck
    # Ab hier rechnet alles mit der Steigung der Gewindeform; Gangzahl und
    # Drehsinn reichen die Gewindebauten durch (RM-544).
    pitch, profile = lid_thread(params, major)
    params = cast(ScrewLidParams, dataclasses.replace(cast(Any, params), pitch=pitch))
    starts, left_hand = max(1, int(params.starts)), bool(params.left_hand)

    ridge = ridge_depth(params.pitch, profile)
    core = major - 2.0 * ridge

    if core - bore <= EPS_GEOM:
        raise ValidationError(
            field="pitch",
            detail=_("Die Wand ist für diese Steigung zu dünn — das Gewinde hätte keinen Kern."),
            constraint="too_coarse",
            values={"neck_mm": round(major, 2), "bore_mm": round(bore, 2)},
        )

    left, bottom, right, top = max(cavities, key=lambda ring: ring.area).bounds
    centre_x, centre_y = (left + right) / 2.0, (bottom + top) / 2.0
    threaded: Any
    lid: Any
    solver: SolverInfo | None = None
    neck_faces: tuple[int, ...] = ()
    cap_faces: tuple[int, ...] = ()
    if exact:
        threaded, neck_faces = exact_screw_neck(
            upright,
            major,
            bore,
            (centre_x, centre_y),
            z,
            params.height,
            params.pitch,
            cancelled=ctx.cancelled,
            profile=profile,
            starts=starts,
            left=left_hand,
        )
        lid, cap_faces = exact_screw_cap(major, params, clearance, cancelled=ctx.cancelled)
    else:
        # Der Kern trägt den Gang, ist also zwei Gangtiefen schmaler als das
        # Gewinde breit: auf einen Hals mit vollem Durchmesser vereinigt säße
        # der Gang im Material und änderte gar nichts.
        stations, sections = turn_sections(major, clearance)
        neck = _pipe(
            core + 2.0 * BOOLEAN_OVERLAP,
            bore,
            params.height,
            z,
            ctx.quality,
            ctx.cancelled,
            sections=sections,
        )
        bounded = boolean(
            "intersection",
            [
                mesh_only(
                    thread_body(
                        major,
                        params.pitch,
                        _thread_tool_height(params),
                        segments=stations,
                        profile=profile,
                        starts=starts,
                        left=left_hand,
                    )
                ),
                _pipe(major * 2.0, 0.0, params.height, 0.0),
            ],
            quality=ctx.quality,
            cancelled=ctx.cancelled,
        )
        turns = _lifted(bounded.mesh, z)
        neck = mesh_only(moved(neck, (centre_x, centre_y, 0.0)))
        turns = mesh_only(moved(turns, (centre_x, centre_y, 0.0)))
        with_neck = boolean("union", [mesh, neck], quality=ctx.quality, cancelled=ctx.cancelled)
        with_thread = boolean(
            "union", [with_neck.mesh, turns], quality=ctx.quality, cancelled=ctx.cancelled
        )
        threaded = with_thread.mesh
        lid, cap_solver = _screw_cap(major, params, clearance, ctx.quality, ctx.cancelled)
        solver = deepest([bounded.solver, with_neck.solver, with_thread.solver, cap_solver])

    turning = _turning(params, profile)
    neck_thread = Feature(
        id=NECK_THREAD_FEATURE,
        kind="thread",
        provenance="generated",
        params={
            **turning,
            "diameter": round(major, 4),
            "pitch": round(params.pitch, 4),
            "handedness": "left" if left_hand else "right",
            "centre": (centre_x, centre_y, z + params.height / 2.0),
            "axis": (0.0, 0.0, 1.0),
            "internal": False,
            # Die bewendelte Strecke — ohne sie hätten Ändern und Entfernen
            # (P2.6) am Halsgewinde keinen Ort, an dem ein Werkzeug ansetzt.
            "length": params.height,
        },
    )
    cap_thread = Feature(
        id=CAP_THREAD_FEATURE,
        kind="thread",
        provenance="generated",
        params={
            # **Der gebaute Durchmesser, nicht der des Halses** (RM-393). Die
            # Kappe ist um das Spiel weiter geschnitten (``_cap_sizes``: Kern
            # plus Spiel, die Nut eine Gangtiefe darüber); mit dem Nennmaß des
            # Halses maß die Passung 0,00 mm und meldete jeden frischen Deckel
            # als zu eng.
            **turning,
            "diameter": round(major + clearance, 4),
            "pitch": round(params.pitch, 4),
            "handedness": "left" if left_hand else "right",
            "centre": (0.0, 0.0, (params.height + SKIRT_RELIEF) / 2.0),
            "axis": (0.0, 0.0, 1.0),
            "internal": True,
            # Die Rille läuft über die ganze Schürze (``_screw_cap``): Höhe plus
            # Entlastung, und die Mitte liegt in ihrer Mitte.
            "length": params.height + SKIRT_RELIEF,
        },
    )

    _log.info("screw lid: neck %.2f, pitch %.2f, clearance %.2f", major, params.pitch, clearance)
    neck_features = {NECK_THREAD_FEATURE: neck_thread}
    if direction != _UP:
        from app.core.perceive.matching import moved_features

        if exact:
            from app.core.brep import edit

            threaded, face_map = edit.transformed_with_faces(
                threaded, _rows(turned_back), cancelled=ctx.cancelled
            )
            neck_faces = tuple(face_map[index] for index in neck_faces)
        else:
            threaded = transform.apply(threaded, turned_back)
        neck_features = moved_features(neck_features, _rows(turned_back))
    container_features: dict[str, Feature] = dict(neck_features)
    cap_features: dict[str, Feature] = {CAP_THREAD_FEATURE: cap_thread}
    if exact:
        # Beide Gewinde kennt die Operation genau: Sie werden an ihren Flächen
        # benannt und nicht noch einmal gelesen (``known_threads``, wie beim
        # Gewindebolzen). Die übrigen Merkmale kommen aus der Topologie.
        from app.core.brep.features import features_of

        known_neck = dataclasses.replace(
            neck_features[NECK_THREAD_FEATURE], face_indices=_triangles(threaded, neck_faces)
        )
        container_features = features_of(
            threaded, cancelled=ctx.cancelled, known_threads=(known_neck,)
        )
        known_cap = dataclasses.replace(cap_thread, face_indices=_triangles(lid, cap_faces))
        cap_features = features_of(lid, cancelled=ctx.cancelled, known_threads=(known_cap,))
    return OpResult(
        solver=solver,
        outputs=[
            dataclasses.replace(
                source,
                mesh=threaded,
                kind="brep" if exact else "mesh",
                features=container_features,
            ),
            SceneObject(
                id="",
                # Wie beim Deckel darüber: kein Quellbezug, kein
                # eingefrorenes Wort.
                name=ctx.scene.unused_name(_("Drehdeckel")),
                mesh=lid,
                kind="brep" if exact else "mesh",
                material=source.material,
                features=cap_features,
            ),
        ],
        findings=[
            Finding(
                code="parts.screw_lid",
                severity="info",
                message=_("Gewindehals und Deckel erzeugt — beide mit derselben Steigung."),
                values={
                    "neck_mm": round(major, 2),
                    "pitch_mm": round(params.pitch, 2),
                    "clearance_mm": round(clearance, 3),
                },
            )
        ],
    )


def _turning(params: ScrewLidParams, profile: ThreadProfile) -> dict[str, Any]:
    """Was die Gewindemerkmale über Gangzahl und Profil sagen, wo es vom Üblichen abweicht."""
    found: dict[str, Any] = {}
    if params.starts > 1:
        found["starts"] = int(params.starts)
        found["lead"] = round(_lid_lead(params), 4)
    if profile != "flat":
        found["profile"] = profile
    return found


def _screw_cap(
    major: float,
    params: ScrewLidParams,
    clearance: float,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> tuple[MeshData, SolverInfo | None]:
    """Der Deckel: eine Kappe, deren Innenseite das Gegenstück zum
    Halsgewinde trägt.

    Gebohrt auf den *Kern*-Durchmesser plus Spiel, nicht auf den
    Außendurchmesser. Das ist der ganze Unterschied zwischen Deckel und
    Hülse: auf den Außendurchmesser gebohrt bleibt nichts stehen, woran der
    Gang des Halses halten könnte, und der Deckel rutscht glatt ab. Dieselbe
    Regel wie bei der Mutter der Bausteinbibliothek, aus demselben Grund.

    Das offene Ende steht auf Z = 0 — so druckt er ohne jede Stütze.
    """
    skirt, inside, outer = _cap_sizes(major, params, clearance)
    stations, sections = turn_sections(major, clearance)

    body = lathe.cylinder(radius=outer / 2.0, height=skirt + params.thickness, sections=sections)
    transform.moved(body, transform.translation((0.0, 0.0, (skirt + params.thickness) / 2.0)))

    # Die zwei Formen, mit denen ein Gewindeloch geschnitten wird: die Bohrung
    # auf Kerndurchmesser, und die Nut, die von ihr bis zum Außendurchmesser
    # reicht.
    hollow = lathe.cylinder(
        radius=inside / 2.0 + BOOLEAN_OVERLAP,
        height=skirt + BOOLEAN_OVERLAP,
        sections=sections,
    )
    transform.moved(
        hollow, transform.translation((0.0, 0.0, (skirt + BOOLEAN_OVERLAP) / 2.0 - BOOLEAN_OVERLAP))
    )
    # Die Wendel wird vollständig aufgebaut und anschließend an der Decke
    # beschnitten. Eine kürzer aufgebaute Wendel ließe den letzten Nutumlauf
    # weg, obwohl das passende Außengewinde dort noch Material trägt.
    groove = mesh_only(
        thread_body(
            inside,
            params.pitch,
            _thread_tool_height(params),
            segments=stations,
            internal=True,
            profile=_lid_profile(params),
            starts=max(1, int(params.starts)),
            left=bool(params.left_hand),
        )
    )

    cutter = boolean("union", [MeshData.of(hollow), groove], quality=quality, cancelled=cancelled)
    bounded = boolean(
        "intersection",
        [cutter.mesh, _pipe(outer * 2.0, 0.0, skirt + BOOLEAN_OVERLAP, -BOOLEAN_OVERLAP)],
        quality=quality,
        cancelled=cancelled,
    )
    cut = boolean(
        "difference", [MeshData.of(body), bounded.mesh], quality=quality, cancelled=cancelled
    )
    return cut.mesh, deepest([cutter.solver, bounded.solver, cut.solver])


def _thread_tool_height(params: ScrewLidParams) -> float:
    """Beide Werkzeuge haben dieselben Winkelstationen, abgeschnitten wird danach.

    Unterschiedliche Wendelspannen erzeugen andere Sehnen. An breiten
    Halsgewinden verbrauchten diese Abweichungen das zugesagte Materialspiel.
    Ganze Umdrehungen reichen über die Schürze; Hals und Kappe nehmen aus
    diesem identischen Werkzeugraster ihre jeweils benötigte Höhe.
    """
    lead = _lid_lead(params)
    return math.ceil((params.height + SKIRT_RELIEF) / lead) * lead


def _cap_sizes(
    major: float, params: ScrewLidParams, clearance: float
) -> tuple[float, float, float]:
    """Schürzenhöhe, Kernbohrung und Außendurchmesser der Kappe — eine Rechnung für beide Kerne.

    Die Schürze ist um ``SKIRT_RELIEF`` höher als der Hals, die Bohrung der
    Kern des Halses plus Spiel (ein Durchmessermaß), der Mantel das Gewinde
    plus Spiel plus zweimal die Wand.
    """
    skirt = params.height + SKIRT_RELIEF
    inside = major - 2.0 * ridge_depth(params.pitch, _lid_profile(params)) + clearance
    outer = major + 2.0 * clearance + 2.0 * params.wall
    return skirt, inside, outer


def _helical_faces(solid: Any, *, above: float | None = None) -> tuple[int, ...]:
    """Die Flächen eines genähten Gewindes: alles, was weder eben noch ein Zylinder ist.

    ``profiles.helical_thread`` baut Kern, Flanken und Kamm aus Regelflächen
    zwischen Helixkanten (P2.7); eben sind nur die Schnitte auf Länge,
    zylindrisch nur Bohrung und Mantel. ``above`` beschränkt die Frage auf das,
    was darüber liegt — am Gehäuse den Hals über dem Rand, gefragt an der
    Mitte des Parameterbereichs jeder Fläche.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

    found: list[int] = []
    for index, native in enumerate(solid.faces()):
        adaptor = BRepAdaptor_Surface(native)
        if adaptor.GetType() in (GeomAbs_Plane, GeomAbs_Cylinder):
            continue
        if above is not None:
            first_u, last_u, first_v, last_v = BRepTools.UVBounds_s(native)
            middle = adaptor.Value((first_u + last_u) / 2.0, (first_v + last_v) / 2.0)
            if float(middle.Z()) <= above:
                continue
        found.append(index)
    return tuple(found)


def _triangles(solid: Any, faces: tuple[int, ...]) -> tuple[int, ...]:
    """Die Dreiecksnummern dieser Flächen in der Vernetzung des Körpers — die Merkmalsnummern."""
    return tuple(sorted({triangle for face in faces for triangle in solid.triangles_of_face(face)}))


def _exact_checked(solid: Any) -> Any:
    """Hals und Deckel sind je ein geschlossener Körper — sonst die Absage mit Vorschlag."""
    if not solid.is_closed or solid.solid_count != 1:
        raise GeometryError(
            detail=_(
                "Gewindehals und Deckel ließen sich exakt nicht bilden. "
                "Ändern Sie Steigung oder Gewindehöhe."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return solid


def exact_screw_neck(
    housing: Any,
    major: float,
    bore: float,
    centre: tuple[float, float],
    z: float,
    height: float,
    pitch: float,
    *,
    cancelled: CancelToken | None = None,
    profile: ThreadProfile = "flat",
    starts: int = 1,
    left: bool = False,
) -> tuple[Any, tuple[int, ...]]:
    """Den Gewindehals auf das exakte Gehäuse setzen — mit den Flächen seines Gewindes.

    Kern und Gang entstehen als ein genähter Körper (``build.threaded`` im
    exakten Kern, P2.7), gleich auf der Höhe der Öffnung; die Bohrung setzt
    den Hohlraum fort. Die Wendel beginnt eine Steigung unter ihrem unteren
    Ende, ihre Phase liegt am Rand also bei null — dieselbe wie die der Nut in
    der Kappe (:func:`exact_screw_cap`), und die Kappe geht ohne Drehen über
    den Hals.
    """
    from app.core.brep import edit
    from app.core.knowledge.parts.build import threaded as threaded_form
    from app.core.knowledge.parts.shapes import building

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    with building("brep"):
        rod = threaded_form(
            major, pitch, height, bottom=z, profile=profile, starts=starts, left=left
        )
    tool = edit.moved(edit.cylinder(bore, height + 2.0), (0.0, 0.0, z - 1.0))
    neck = edit.boolean("difference", [cast(Any, rod), tool])
    if abs(centre[0]) > EPS_GEOM or abs(centre[1]) > EPS_GEOM:
        neck = edit.moved(neck, (centre[0], centre[1], 0.0))
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    joined = _exact_checked(edit.unified(edit.boolean("union", [housing, neck])))
    return joined, _helical_faces(joined, above=z)


def exact_screw_cap(
    major: float,
    params: ScrewLidParams,
    clearance: float,
    *,
    cancelled: CancelToken | None = None,
) -> tuple[Any, tuple[int, ...]]:
    """Die Kappe als exakter Körper — Mantel minus Kernbohrung minus Nut, in einem Schnitt.

    Das Werkzeug ist ein Innengewinde aus dem exakten Kern (``build.threaded``
    mit ``internal``): die Bohrung auf Kern plus Spiel, der Gang nach außen.
    Es beginnt eine Steigung unter dem offenen Ende und reicht bis zur Decke
    der Schürze — die Nut läuft über die ganze Schürze, und ihre Phase am
    offenen Ende ist die des Halses am Rand.
    """
    from app.core.brep import edit
    from app.core.knowledge.parts.build import threaded as threaded_form
    from app.core.knowledge.parts.shapes import building

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    skirt, inside, outer = _cap_sizes(major, params, clearance)
    with building("brep"):
        lead = _lid_lead(params)
        cutter = threaded_form(
            inside,
            params.pitch,
            skirt + lead,
            internal=True,
            bottom=-lead,
            profile=_lid_profile(params),
            starts=max(1, int(params.starts)),
            left=bool(params.left_hand),
        )
    body = edit.cylinder(outer, skirt + params.thickness)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    cap = _exact_checked(edit.unified(edit.boolean("difference", [body, cast(Any, cutter)])))
    return cap, _helical_faces(cap)
